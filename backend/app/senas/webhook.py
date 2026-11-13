"""Webhook de Mercado Pago — autenticidad, idempotencia y acreditación (C-11 §6).

Contrato no negociable (D7/D8, RN-SE-03):

1. **Firma primero**: `x-signature` es `ts=…,v1=…` y `v1` es el
   `HMAC-SHA256(MP_WEBHOOK_SECRET, manifiesto)` en hexadecimal, con
   `manifiesto = "id:{data.id};request-id:{x-request-id};ts:{ts};"`. Se compara
   con `hmac.compare_digest`. Ausente o distinta ⇒ `401` y **nada** se persiste
   (ni se consulta la pasarela).
2. **Sin secreto configurado ⇒ `503 WEBHOOK_NO_CONFIGURADO`** (fail-closed). Un
   webhook de dinero no se procesa "porque estamos en dev".
3. **El cuerpo no acredita**: del cuerpo sólo se toma `data.id` para saber qué
   pago re-consultar. Estado, monto, moneda y metadata se leen de
   `PasarelaPagosPort.obtener_pago`. Nadie "declara" un pago aprobado mandando
   un JSON, y el `tenant_id`/`sena_id` usados son los de la respuesta de MP, no
   los de un header (`F-26`).
4. **Serialización**: `SELECT … FOR UPDATE` sobre la seña y transiciones
   condicionales (`UPDATE … WHERE estado = <esperado>`). Gana la primera
   transacción que commitea (D11); la perdedora ve el estado nuevo y no escribe.
5. **Idempotencia**: `mp_payment_id` es único global. La misma notificación dos
   veces responde `200` con `resultado=DUPLICADO` y no toca la seña. Un pago
   **distinto** sobre una seña que ya no está `PENDIENTE` es `PAGO_EXCEDENTE`,
   nunca `DUPLICADO` (D3).
6. **La plata no se descarta**: monto o moneda distintos ⇒ `MONTO_DISTINTO`; un
   pago que no resuelve a una seña del tenant ⇒ `500` con **log estructurado**
   (no hay entidad ni actor para una fila de auditoría) para que MP reintente.

Sin PHI (RN-CL-04): `raw_json` guarda sólo id, estado, detalle, monto, moneda,
fecha de aprobación, referencia y metadata de seña/turno/tenant. Nunca datos
del pagador, tarjeta, cuotas ni el link de pago.
"""
from __future__ import annotations

import hmac
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from typing import Any

from app.core.logging import get_logger
from app.senas.puertos import (
    AccionSena,
    AuditoriaPort,
    EstadoPagoMP,
    PagoExterno,
    PagoMP,
    PagoMPRepositorio,
    PagoNoEncontrado,
    PasarelaNoDisponible,
    PasarelaPagosPort,
    Reloj,
    ResultadoPagoMP,
    Sena,
    SenaInvalida,
    SenaRepositorio,
    TransaccionNula,
    TurnoPort,
    UnidadDeTrabajoPort,
)
from app.turnos.servicio import NoEncontrado, TurnoError

__all__ = [
    "ACTOR_WEBHOOK",
    "CODIGO_FIRMA_INVALIDA",
    "CODIGO_MP_NO_DISPONIBLE",
    "CODIGO_PAGO_NO_ASOCIABLE",
    "CODIGO_WEBHOOK_NO_CONFIGURADO",
    "FirmaInvalida",
    "PagoNoAsociable",
    "ResultadoWebhook",
    "ServicioNoDisponibleWebhook",
    "ServicioSenasWebhook",
    "WebhookNoConfigurado",
    "firma_esperada",
    "manifiesto",
    "parsear_firma",
    "verificar_firma",
]

logger = get_logger("app.senas.webhook")

CODIGO_FIRMA_INVALIDA = "FIRMA_INVALIDA"
CODIGO_WEBHOOK_NO_CONFIGURADO = "WEBHOOK_NO_CONFIGURADO"
CODIGO_PAGO_NO_ASOCIABLE = "PAGO_NO_ASOCIABLE"
CODIGO_MP_NO_DISPONIBLE = "MP_NO_DISPONIBLE"

ACTOR_WEBHOOK = "webhook-mp"
TIPO_PAGO = "payment"
MONEDA_ACREDITABLE = "ARS"
MOTIVO_FUERA_DE_TIEMPO = "PAGO_FUERA_DE_TIEMPO"
MOTIVO_REEMBOLSO_MP = "REEMBOLSO_MP"
MOTIVO_TURNO_NO_CONFIRMABLE = "TURNO_NO_CONFIRMABLE"

# Estados del turno en los que la plata de la seña se puede retener. `PENDIENTE`
# además se confirma; `CONFIRMADO`/`PRESENTE` ya no necesitan la transición, pero
# devolver la seña de un turno vivo sería regalar el hueco (D4).
_TURNO_CONFIRMABLE = "PENDIENTE"
_TURNOS_VIVOS = frozenset({"PENDIENTE", "CONFIRMADO", "PRESENTE"})
_ESTADOS_SIN_ACREDITAR = frozenset({"ACREDITADA", "APLICADA", "DEVUELTA"})


# ---------------------------------------------------------------------------
# Errores de dominio (código HTTP observable por el borde)
# ---------------------------------------------------------------------------


class FirmaInvalida(TurnoError):
    """`401` — `x-signature` ausente, mal formada o que no coincide."""

    codigo = 401
    codigo_dominio = CODIGO_FIRMA_INVALIDA


class WebhookNoConfigurado(TurnoError):
    """`503` — no hay `MP_WEBHOOK_SECRET`: fail-closed, no se acepta nada."""

    codigo = 503
    codigo_dominio = CODIGO_WEBHOOK_NO_CONFIGURADO


class ServicioNoDisponibleWebhook(TurnoError):
    """`503` — MP no responde al re-consultar el pago: que reintente."""

    codigo = 503
    codigo_dominio = CODIGO_MP_NO_DISPONIBLE


class PagoNoAsociable(TurnoError):
    """`500` — la notificación no resuelve a una seña del tenant.

    No se persiste nada y se deja un log estructurado: no hay entidad ni actor
    de tenant para una fila de auditoría (`F-25`). Mercado Pago reintenta, así
    que la plata nunca se descarta.
    """

    codigo = 500
    codigo_dominio = CODIGO_PAGO_NO_ASOCIABLE


# ---------------------------------------------------------------------------
# Firma HMAC (D7)
# ---------------------------------------------------------------------------


def manifiesto(*, data_id: str, request_id: str, ts: str) -> str:
    """Cadena firmada por Mercado Pago (misma que documenta la pasarela)."""
    return f"id:{data_id};request-id:{request_id};ts:{ts};"


def firma_esperada(*, secreto: str, manifiesto_: str) -> str:
    """`v1` esperado: HMAC-SHA256 hexadecimal del manifiesto con el secreto."""
    return hmac.new(
        secreto.encode("utf-8"), manifiesto_.encode("utf-8"), sha256
    ).hexdigest()


def parsear_firma(x_signature: str | None) -> tuple[str, str] | None:
    """`(ts, v1)` del header `ts=…,v1=…`; `None` si falta o está mal formado."""
    if not x_signature:
        return None
    partes: dict[str, str] = {}
    for trozo in x_signature.split(","):
        clave, separador, valor = trozo.strip().partition("=")
        if separador and clave:
            partes[clave] = valor
    ts = partes.get("ts")
    v1 = partes.get("v1")
    if not ts or not v1:
        return None
    return ts, v1


def verificar_firma(
    *,
    secreto: str,
    x_signature: str | None,
    request_id: str | None,
    data_id: str | None,
) -> None:
    """Verifica la firma en tiempo constante; cualquier duda es `401`.

    No se rechaza por antigüedad del `ts`: no hay tolerancia en la KB y no hace
    falta, porque el efecto es idempotente y la fuente de verdad se re-consulta
    (D7). Inventar una ventana sólo agregaría un número sin respaldo.
    """
    if not data_id or not request_id:
        raise FirmaInvalida("la notificación no trae data.id o x-request-id")
    firma = parsear_firma(x_signature)
    if firma is None:
        raise FirmaInvalida("falta x-signature o está mal formada")
    ts, v1 = firma
    esperado = firma_esperada(
        secreto=secreto,
        manifiesto_=manifiesto(data_id=data_id, request_id=request_id, ts=ts),
    )
    if not hmac.compare_digest(v1, esperado):
        raise FirmaInvalida("la firma no coincide")


# ---------------------------------------------------------------------------
# Resultado
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ResultadoWebhook:
    """Resultado de una notificación ya autenticada (`200` en todos estos casos)."""

    resultado: ResultadoPagoMP
    mp_payment_id: str
    sena_id: str | None = None
    estado_pago: EstadoPagoMP | None = None
    pago: PagoMP | None = None


# ---------------------------------------------------------------------------
# Caso de uso
# ---------------------------------------------------------------------------


class ServicioSenasWebhook:
    """Procesa la notificación de MP: firma, re-consulta, lock y efecto único."""

    def __init__(
        self,
        senas: SenaRepositorio,
        pagos: PagoMPRepositorio,
        turnos: TurnoPort,
        pasarela: PasarelaPagosPort,
        auditoria: AuditoriaPort,
        *,
        secreto: str | None,
        reloj: Reloj | None = None,
        uow_factory: Callable[[], UnidadDeTrabajoPort] | None = None,
    ) -> None:
        self._senas = senas
        self._pagos = pagos
        self._turnos = turnos
        self._pasarela = pasarela
        self._auditoria = auditoria
        self._secreto = secreto
        self._reloj = reloj
        self._uow_factory: Callable[[], UnidadDeTrabajoPort] = (
            uow_factory if uow_factory is not None else TransaccionNula
        )

    # -- entrypoint -----------------------------------------------------

    def procesar(
        self,
        *,
        x_signature: str | None,
        request_id: str | None,
        data_id: str | None,
        tipo: str | None = None,
        ahora: datetime | None = None,
    ) -> ResultadoWebhook:
        """Procesa una notificación firmada. Todo efecto ocurre en una transacción."""
        if not self._secreto:
            # Fail-closed: sin secreto no se acepta NINGÚN payload (D7).
            raise WebhookNoConfigurado(
                "el webhook de Mercado Pago no está configurado"
            )
        momento = self._momento(ahora)
        # La firma se verifica SIEMPRE antes de mirar el tipo o el cuerpo.
        verificar_firma(
            secreto=self._secreto,
            x_signature=x_signature,
            request_id=request_id,
            data_id=data_id,
        )
        if tipo is not None and tipo != TIPO_PAGO:
            # `merchant_order` y cualquier otro tipo: 200 sin tocar nada.
            logger.info("webhook_mp_tipo_ignorado tipo=%s", tipo)
            return ResultadoWebhook(
                resultado="IGNORADO", mp_payment_id=data_id or "", sena_id=None
            )
        assert data_id is not None  # garantizado por `verificar_firma`
        pago_externo = self._re_consultar(data_id)

        with self._uow_factory():
            return self._aplicar(pago_externo=pago_externo, momento=momento)

    # -- pasos ----------------------------------------------------------

    def _re_consultar(self, mp_payment_id: str) -> PagoExterno:
        """La fuente de verdad es MP, nunca el cuerpo de la notificación."""
        try:
            return self._pasarela.obtener_pago(mp_payment_id=mp_payment_id)
        except PasarelaNoDisponible as exc:
            logger.warning(
                "webhook_mp_pasarela_caida mp_payment_id=%s", mp_payment_id
            )
            raise ServicioNoDisponibleWebhook(
                "Mercado Pago no responde; reintentá la notificación"
            ) from exc
        except PagoNoEncontrado as exc:
            self._log_no_asociable(
                mp_payment_id=mp_payment_id,
                tenant_id=None,
                sena_id=None,
                motivo="pago_inexistente",
            )
            raise PagoNoAsociable("la notificación no resuelve a una seña") from exc

    def _aplicar(self, *, pago_externo: PagoExterno, momento: datetime) -> ResultadoWebhook:
        tenant_id, sena_id = self._resolver_destino(pago_externo)
        sena = self._bloquear(tenant_id=tenant_id, sena_id=sena_id, pago=pago_externo)
        # OJO: el pago se busca DESPUÉS del lock. Si la transacción ganadora ya
        # commiteó, esto ve su fila y responde DUPLICADO de forma determinista.
        existente = self._pagos.obtener(
            tenant_id=tenant_id, mp_payment_id=pago_externo.mp_payment_id
        )
        if existente is not None and not self._es_reembolso_nuevo(existente, pago_externo):
            self._pagos.registrar_o_actualizar(
                tenant_id=tenant_id,
                sena_id=sena.id,
                mp_payment_id=pago_externo.mp_payment_id,
                monto_centavos=pago_externo.monto_centavos,
                moneda=pago_externo.moneda,
                estado=pago_externo.estado,
                resultado=None,  # conserva el efecto ya aplicado
                raw_json=self._raw_json(pago_externo),
                aprobado_en=pago_externo.aprobado_en,
                ahora=momento,
            )
            return ResultadoWebhook(
                resultado="DUPLICADO",
                mp_payment_id=pago_externo.mp_payment_id,
                sena_id=sena.id,
                estado_pago=pago_externo.estado,
            )

        resultado, sena_final = self._decidir_efecto(
            sena=sena, pago=pago_externo, momento=momento
        )
        pago = self._pagos.registrar_o_actualizar(
            tenant_id=tenant_id,
            sena_id=sena.id,
            mp_payment_id=pago_externo.mp_payment_id,
            monto_centavos=pago_externo.monto_centavos,
            moneda=pago_externo.moneda,
            estado=pago_externo.estado,
            resultado=resultado,
            raw_json=self._raw_json(pago_externo),
            aprobado_en=pago_externo.aprobado_en,
            ahora=momento,
        )
        logger.info(
            "webhook_mp_procesado tenant_id=%s sena_id=%s mp_payment_id=%s"
            " estado=%s resultado=%s",
            tenant_id,
            sena.id,
            pago_externo.mp_payment_id,
            pago_externo.estado,
            resultado,
        )
        return ResultadoWebhook(
            resultado=resultado,
            mp_payment_id=pago_externo.mp_payment_id,
            sena_id=sena_final.id if sena_final is not None else sena.id,
            estado_pago=pago_externo.estado,
            pago=pago,
        )

    def _decidir_efecto(
        self, *, sena: Sena, pago: PagoExterno, momento: datetime
    ) -> tuple[ResultadoPagoMP, Sena | None]:
        """Decide el resultado y, si corresponde, aplica la transición única."""
        if pago.estado == "REFUNDED":
            return self._reembolso(sena=sena, pago=pago, momento=momento)

        if pago.estado != "APPROVED":
            # PENDING/IN_PROCESS/REJECTED/CANCELLED: se registra y no se acredita.
            return "IGNORADO", None

        if sena.estado == "LIBERADA":
            # Pago tardío: la plata se devuelve; el turno NO se reabre (C11-OQ-07).
            return self._devolver(
                sena=sena,
                motivo=MOTIVO_FUERA_DE_TIEMPO,
                resultado="FUERA_DE_TIEMPO",
                pago=pago,
                momento=momento,
            )

        if sena.estado == "PENDIENTE":
            if pago.monto_centavos != sena.monto_centavos or pago.moneda != MONEDA_ACREDITABLE:
                # Entró plata que no corresponde: se registra y queda visible la
                # obligación de devolución; la seña no cambia (D8 paso 7).
                return "MONTO_DISTINTO", None
            return self._acreditar(sena=sena, pago=pago, momento=momento)

        if sena.estado in _ESTADOS_SIN_ACREDITAR:
            # Pago distinto sobre una seña ya resuelta: NUNCA `DUPLICADO`.
            return "PAGO_EXCEDENTE", None

        # Estado inesperado: no se inventa un efecto sobre la plata.
        return "IGNORADO", None

    def _acreditar(
        self, *, sena: Sena, pago: PagoExterno, momento: datetime
    ) -> tuple[ResultadoPagoMP, Sena | None]:
        turno = self._turnos.turno_de(tenant_id=sena.tenant_id, turno_id=sena.turno_id)
        if turno is None or turno.estado not in _TURNOS_VIVOS:
            return self._devolver(
                sena=sena,
                motivo=MOTIVO_TURNO_NO_CONFIRMABLE,
                resultado="TURNO_NO_CONFIRMABLE",
                pago=pago,
                momento=momento,
            )

        acreditada = self._senas.transicionar(
            tenant_id=sena.tenant_id,
            sena_id=sena.id,
            desde="PENDIENTE",
            hacia="ACREDITADA",
            campos={"acreditada_en": momento},
        )
        if acreditada is None:
            # Otra transacción ganó la carrera: la perdedora no escribe.
            actual = self._senas.obtener(tenant_id=sena.tenant_id, sena_id=sena.id)
            return ("PAGO_EXCEDENTE" if actual is not None else "IGNORADO"), None

        if turno.estado == _TURNO_CONFIRMABLE:
            self._turnos.confirmar_por_sena(
                tenant_id=sena.tenant_id, turno_id=sena.turno_id, ahora=momento
            )
        self._auditar(
            sena=acreditada,
            accion="SENA_ACREDITADA",
            antes={"estado": "PENDIENTE"},
            despues={
                "estado": "ACREDITADA",
                "mp_payment_id": pago.mp_payment_id,
                "monto_centavos": pago.monto_centavos,
            },
        )
        return "ACREDITADA", acreditada

    def _devolver(
        self,
        *,
        sena: Sena,
        motivo: str,
        resultado: ResultadoPagoMP,
        pago: PagoExterno,
        momento: datetime,
    ) -> tuple[ResultadoPagoMP, Sena | None]:
        devuelta = self._senas.transicionar(
            tenant_id=sena.tenant_id,
            sena_id=sena.id,
            desde=sena.estado,
            hacia="DEVUELTA",
            campos={
                "devuelta_en": momento,
                "motivo_devolucion": motivo,
                "devuelta_por": None,
            },
        )
        if devuelta is None:
            return resultado, None
        self._auditar(
            sena=devuelta,
            accion="SENA_DEVUELTA",
            antes={"estado": sena.estado},
            despues={
                "estado": "DEVUELTA",
                "motivo_devolucion": motivo,
                "mp_payment_id": pago.mp_payment_id,
                "resultado": resultado,
            },
        )
        return resultado, devuelta

    def _reembolso(
        self, *, sena: Sena, pago: PagoExterno, momento: datetime
    ) -> tuple[ResultadoPagoMP, Sena | None]:
        """`REFUNDED` de MP: cierra la obligación o pide un ajuste de caja."""
        if sena.estado == "ACREDITADA":
            resultado, devuelta = self._devolver(
                sena=sena,
                motivo=MOTIVO_REEMBOLSO_MP,
                resultado="REEMBOLSADO",
                pago=pago,
                momento=momento,
            )
            self._auditar(
                sena=devuelta or sena,
                accion="SENA_REEMBOLSO_MP",
                antes={"estado": "ACREDITADA"},
                despues={
                    "estado": "DEVUELTA",
                    "mp_payment_id": pago.mp_payment_id,
                    "resultado": "REEMBOLSADO",
                },
            )
            return resultado, devuelta
        if sena.estado == "APLICADA":
            # La plata ya está en caja: no se revierte la seña, queda el ajuste
            # pendiente de ADMIN (anulación con motivo, C-10).
            self._auditar(
                sena=sena,
                accion="SENA_REEMBOLSO_MP",
                antes={"estado": "APLICADA"},
                despues={
                    "estado": "APLICADA",
                    "mp_payment_id": pago.mp_payment_id,
                    "resultado": "REEMBOLSO_AJUSTE_CAJA",
                },
            )
            return "REEMBOLSO_AJUSTE_CAJA", None
        return "IGNORADO", None

    # -- resolución -----------------------------------------------------

    def _es_reembolso_nuevo(self, existente: PagoMP, pago: PagoExterno) -> bool:
        """Un `REFUNDED` del **mismo** pago es un hecho nuevo, no una renotificación.

        `mp_payment_id` sigue siendo la clave de idempotencia: la segunda
        notificación de un pago ya acreditado es `DUPLICADO`. Pero el reembolso
        de ese mismo pago tiene que poder cerrar la obligación (D8 paso 10), así
        que se procesa una única vez, cuando el resultado todavía no lo refleja.
        """
        return pago.estado == "REFUNDED" and existente.resultado not in (
            "REEMBOLSADO",
            "REEMBOLSO_AJUSTE_CAJA",
        )

    def _resolver_destino(self, pago: PagoExterno) -> tuple[str, str]:
        """Tenant y seña desde la **respuesta de MP** (nunca del cuerpo)."""
        tenant_id = pago.metadata.get("tenant_id")
        sena_id = pago.metadata.get("sena_id") or pago.external_reference
        if not tenant_id or not sena_id:
            self._log_no_asociable(
                mp_payment_id=pago.mp_payment_id,
                tenant_id=tenant_id,
                sena_id=sena_id,
                motivo="metadata_incompleta",
            )
            raise PagoNoAsociable("la notificación no resuelve a una seña")
        return tenant_id, sena_id

    def _bloquear(self, *, tenant_id: str, sena_id: str, pago: PagoExterno) -> Sena:
        try:
            return self._senas.bloquear(tenant_id=tenant_id, sena_id=sena_id)
        except (NoEncontrado, SenaInvalida) as exc:
            self._log_no_asociable(
                mp_payment_id=pago.mp_payment_id,
                tenant_id=tenant_id,
                sena_id=sena_id,
                motivo="sena_no_encontrada_en_el_tenant",
            )
            raise PagoNoAsociable("la notificación no resuelve a una seña") from exc

    def _log_no_asociable(
        self,
        *,
        mp_payment_id: str,
        tenant_id: str | None,
        sena_id: str | None,
        motivo: str,
    ) -> None:
        """Log estructurado con ids y motivo: no es auditoría (no hay actor)."""
        logger.error(
            "webhook_mp_pago_no_asociable mp_payment_id=%s tenant_id=%s sena_id=%s motivo=%s",
            mp_payment_id,
            tenant_id or "-",
            sena_id or "-",
            motivo,
            extra={
                "codigo": CODIGO_PAGO_NO_ASOCIABLE,
                "mp_payment_id": mp_payment_id,
                "tenant_id": tenant_id,
                "sena_id": sena_id,
                "motivo": motivo,
            },
        )

    # -- helpers --------------------------------------------------------

    def _raw_json(self, pago: PagoExterno) -> Mapping[str, Any]:
        """Allow-list mínima del pago: sin pagador, tarjeta ni cuotas (D15)."""
        metadata = {
            clave: pago.metadata[clave]
            for clave in ("sena_id", "turno_id", "tenant_id")
            if clave in pago.metadata
        }
        return {
            "id": pago.mp_payment_id,
            "status": pago.estado,
            "transaction_amount": pago.monto_centavos,
            "currency_id": pago.moneda,
            "date_approved": (
                pago.aprobado_en.isoformat() if pago.aprobado_en is not None else None
            ),
            "external_reference": pago.external_reference,
            "metadata": metadata,
        }

    def _auditar(
        self,
        *,
        sena: Sena,
        accion: AccionSena,
        antes: Mapping[str, Any] | None,
        despues: Mapping[str, Any] | None,
    ) -> None:
        self._auditoria.registrar(
            tenant_id=sena.tenant_id,
            accion=accion,
            actor=ACTOR_WEBHOOK,
            entidad="sena",
            entidad_id=sena.id,
            antes=antes,
            despues=despues,
        )

    def _momento(self, ahora: datetime | None) -> datetime:
        if ahora is not None:
            return ahora
        if self._reloj is not None:
            return self._reloj()
        raise RuntimeError("ServicioSenasWebhook requiere un reloj inyectado o `ahora`")
