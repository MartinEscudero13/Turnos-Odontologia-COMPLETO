"""Casos de uso de la seña — alta, preferencia y token público (C-11 §4–§5).

Orden de eventos (D5, no negociable): **primero** se persiste la seña y se
"commitea" (`SenaRepositorio.crear`), **después** se pide la preferencia a la
pasarela. Así un webhook de Mercado Pago nunca puede llegar antes de que exista
la fila que tiene que acreditar.

Si la pasarela está caída, el alta **no falla**: la seña queda `PENDIENTE` con
`preferencia_estado=FALLIDA`, `intentos_preferencia` y `proximo_reintento_at`
(backoff `min(2**intentos, 15)` minutos, C11-OQ-05 provisional), y el paciente
reintenta on-demand desde su link. Nunca se responde `500` por MP caído
(RN-IN-03) ni se pierde la reserva.

Una seña con `expira_at <= ahora` **no** pide una preferencia nueva
(`409 SENA_VENCIDA`) aunque siga `PENDIENTE`: la guarda se decide antes de tocar
la red (F-09).

El token público es opaco y se busca por hash **dentro del tenant** del slug; un
token de otro tenant, uno inexistente y uno rotado responden el mismo `404`
(D6). Sin PHI: la vista pública sólo lleva ids, montos, instantes y política.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Literal

from app.core.logging import get_logger
from app.reservas.servicio import DemasiadasSolicitudes
from app.senas.puertos import (
    MOTIVO_CANCELACION,
    AccionSena,
    AuditoriaPort,
    ConfiguracionSenaPort,
    ContadorSenaPort,
    EstadoPreferencia,
    EstadoSena,
    PasarelaNoDisponible,
    PasarelaPagosPort,
    PoliticaSena,
    Reloj,
    ResolutorTenantPort,
    Sena,
    SenaCreada,
    SenaDuplicada,
    SenaInvalida,
    SenaRepositorio,
    SenaTransferida,
    TokenDuplicado,
    TransaccionNula,
    UnidadDeTrabajoPort,
)
from app.senas.regla import resolver_regla
from app.senas.token import generar_token, hash_token
from app.turnos.servicio import Invalido, NoEncontrado, TurnoError

__all__ = [
    "ANTICIPACION_DEFAULT_H",
    "CODIGO_SENA_DUPLICADA",
    "CODIGO_SENA_VENCIDA",
    "DESCRIPCION_PREFERENCIA",
    "SENA_TTL_DEFAULT_H",
    "ConflictoSena",
    "ResultadoPreferencia",
    "SenaPublica",
    "SenaVencida",
    "ServicioSenas",
    "TurnoSenaVista",
]

logger = get_logger("app.senas")

SENA_TTL_DEFAULT_H = 24
ANTICIPACION_DEFAULT_H = 24
# F-17: el checkout de MP es una superficie de terceros; nunca lleva la
# prestación, el profesional ni datos del paciente.
DESCRIPCION_PREFERENCIA = "Seña de turno"

BACKOFF_BASE = 2
BACKOFF_MAX_MIN = 15

CODIGO_SENA_VENCIDA = "SENA_VENCIDA"
CODIGO_SENA_DUPLICADA = "SENA_DUPLICADA"
CODIGO_TOKEN_DUPLICADO = "TOKEN_DUPLICADO"
CODIGO_ESTADO_INVALIDO = "ESTADO_INVALIDO"

ResultadoPreferenciaEstado = Literal["EXISTENTE", "CREADA", "BACKOFF"]


# ---------------------------------------------------------------------------
# Errores de dominio (código HTTP + código observable por el borde)
# ---------------------------------------------------------------------------


class ConflictoSena(TurnoError):
    """`409` de señas con código de dominio (`SENA_VENCIDA`, `ESTADO_INVALIDO`, …)."""

    codigo = 409

    def __init__(self, codigo_dominio: str, mensaje: str) -> None:
        super().__init__(mensaje)
        self.codigo_dominio: str = codigo_dominio


class SenaVencida(ConflictoSena):
    """La seña pasó su `expira_at`: no se pide preferencia ni se cobra."""

    def __init__(self, mensaje: str = "la seña está vencida") -> None:
        super().__init__(CODIGO_SENA_VENCIDA, mensaje)


# ---------------------------------------------------------------------------
# Vistas de lectura / resultados
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TurnoSenaVista:
    """Datos del turno que la página de pago necesita (sin PHI)."""

    inicio: datetime
    fin: datetime
    prestacion: str


@dataclass(frozen=True)
class SenaPublica:
    """Allow-list de `GET /api/publico/{tokenTenant}/senas/{token}` (D6)."""

    sena_id: str
    estado: EstadoSena
    monto_centavos: int
    expira_at: datetime
    preferencia_estado: EstadoPreferencia
    init_point: str | None
    turno: TurnoSenaVista
    politica: PoliticaSena


@dataclass(frozen=True)
class ResultadoPreferencia:
    """Resultado de `POST .../preferencia`: existente (`200`), creada (`201`) o backoff (`202`)."""

    resultado: ResultadoPreferenciaEstado
    vista: SenaPublica
    reintentar_en: datetime | None = None


class ServicioSenas:
    """Alta de la seña, preferencia de pago y lectura pública por token."""

    def __init__(
        self,
        senas: SenaRepositorio,
        configuracion: ConfiguracionSenaPort,
        pasarela: PasarelaPagosPort,
        auditoria: AuditoriaPort,
        *,
        tenants: ResolutorTenantPort | None = None,
        contador: ContadorSenaPort | None = None,
        sena_ttl_h: int = SENA_TTL_DEFAULT_H,
        anticipacion_cancelacion_h: int = ANTICIPACION_DEFAULT_H,
        rate_limit_max: int = 10,
        rate_limit_ventana_s: int = 60,
        url_pago_base: str = "",
        url_webhook: str = "",
        reloj: Reloj | None = None,
        uow_factory: Callable[[], UnidadDeTrabajoPort] | None = None,
    ) -> None:
        self._senas = senas
        self._configuracion = configuracion
        self._pasarela = pasarela
        self._auditoria = auditoria
        self._tenants = tenants
        self._contador = contador
        self._sena_ttl_h = sena_ttl_h
        self._anticipacion_cancelacion_h = anticipacion_cancelacion_h
        self._rate_limit_max = rate_limit_max
        self._rate_limit_ventana_s = rate_limit_ventana_s
        self._url_pago_base = url_pago_base.rstrip("/")
        self._url_webhook = url_webhook
        self._reloj = reloj
        self._uow_factory: Callable[[], UnidadDeTrabajoPort] = (
            uow_factory if uow_factory is not None else TransaccionNula
        )

    # -- alta -----------------------------------------------------------

    def crear_si_corresponde(
        self,
        *,
        tenant_id: str,
        turno_id: str,
        prestacion_id: str,
        turno_inicio: datetime,
        turno_fin: datetime | None = None,
        ahora: datetime | None = None,
    ) -> SenaCreada | None:
        """Crea la seña `PENDIENTE` si la regla la exige y pide la preferencia.

        Devuelve `None` cuando la regla efectiva es `SIN_SENA` (o el monto es
        cero): la reserva sigue su contrato de C-06 sin bloque `sena`.
        """
        momento = self._momento(ahora)
        prestacion = self._configuracion.prestacion(
            tenant_id=tenant_id, prestacion_id=prestacion_id
        )
        if prestacion is None:
            raise NoEncontrado("prestación no encontrada")
        regla = resolver_regla(
            tenant_id=tenant_id,
            prestacion=prestacion,
            parametros=self._configuracion.parametros(tenant_id=tenant_id),
        )
        if not regla.exige_sena:
            return None
        if regla.valor is None or regla.modo == "SIN_SENA":
            # Fail-open a no cobrar: una regla imposible no rompe la reserva (D1).
            return None

        expira_at = min(
            momento + timedelta(hours=self._sena_ttl_h),
            turno_inicio,
        )
        token = generar_token()
        try:
            # 1) La seña existe (y se commitea) ANTES de hablar con la pasarela.
            sena = self._senas.crear(
                tenant_id=tenant_id,
                turno_id=turno_id,
                monto_centavos=regla.monto_centavos,
                regla_modo=regla.modo,
                regla_valor=regla.valor,
                precio_base_centavos=regla.precio_base_centavos,
                anticipacion_cancelacion_h=self._anticipacion_cancelacion_h,
                expira_at=expira_at,
                token_hash=hash_token(token),
                ahora=momento,
                turno_inicio=turno_inicio,
                turno_fin=turno_fin,
                turno_prestacion=prestacion_id,
            )
        except SenaDuplicada as exc:
            raise ConflictoSena(
                CODIGO_SENA_DUPLICADA, "el turno ya tiene una seña"
            ) from exc
        except TokenDuplicado as exc:  # colisión global astronómica del UNIQUE
            raise ConflictoSena(
                CODIGO_TOKEN_DUPLICADO, "no se pudo emitir el token de pago"
            ) from exc
        except SenaInvalida as exc:
            raise Invalido(str(exc)) from exc

        self._auditar(
            tenant_id=tenant_id,
            accion="SENA_CREADA",
            sena=sena,
            despues={
                "estado": sena.estado,
                "turno_id": sena.turno_id,
                "monto_centavos": sena.monto_centavos,
                "regla_modo": sena.regla_modo,
                "regla_valor": sena.regla_valor,
                "expira_at": sena.expira_at.isoformat(),
            },
        )
        # 2) Recién ahora la preferencia, en una transacción corta aparte.
        actual = self._intentar_preferencia(sena=sena, token=token, momento=momento)
        return SenaCreada(
            sena=actual,
            token_sena=token,
            politica=self._politica(actual),
        )

    def _intentar_preferencia(
        self, *, sena: Sena, token: str, momento: datetime
    ) -> Sena:
        """Pide la preferencia; un fallo de MP deja la seña `FALLIDA`, no un `500`."""
        try:
            preferencia = self._pasarela.crear_preferencia(
                tenant_id=sena.tenant_id,
                sena_id=sena.id,
                turno_id=sena.turno_id,
                monto_centavos=sena.monto_centavos,
                descripcion=DESCRIPCION_PREFERENCIA,
                expira_at=sena.expira_at,
                url_pago=self._url_de_pago(token),
                url_webhook=self._url_webhook,
            )
        except PasarelaNoDisponible:
            return self._preferencia_fallida(sena=sena, momento=momento)

        actualizada = self._senas.actualizar(
            tenant_id=sena.tenant_id,
            sena_id=sena.id,
            desde="PENDIENTE",
            campos={
                "preferencia_estado": "CREADA",
                "mp_preference_id": preferencia.mp_preference_id,
                "mp_init_point": preferencia.init_point,
                "proximo_reintento_at": None,
            },
        )
        actual = actualizada or self._recargar(sena)
        self._auditar(
            tenant_id=sena.tenant_id,
            accion="SENA_PREFERENCIA_CREADA",
            sena=actual,
            despues={
                "mp_preference_id": preferencia.mp_preference_id,
                "intento": actual.intentos_preferencia,
                "monto_centavos": actual.monto_centavos,
            },
        )
        return actual

    def _preferencia_fallida(self, *, sena: Sena, momento: datetime) -> Sena:
        intentos = sena.intentos_preferencia + 1
        proximo = momento + timedelta(minutes=min(BACKOFF_BASE**intentos, BACKOFF_MAX_MIN))
        actualizada = self._senas.actualizar(
            tenant_id=sena.tenant_id,
            sena_id=sena.id,
            desde="PENDIENTE",
            campos={
                "preferencia_estado": "FALLIDA",
                "mp_preference_id": None,
                "mp_init_point": None,
                "intentos_preferencia": intentos,
                "proximo_reintento_at": proximo,
            },
        )
        actual = actualizada or self._recargar(sena)
        logger.warning(
            "sena_preferencia_fallida tenant_id=%s sena_id=%s intentos=%s",
            sena.tenant_id,
            sena.id,
            intentos,
        )
        self._auditar(
            tenant_id=sena.tenant_id,
            accion="SENA_PREFERENCIA_FALLIDA",
            sena=actual,
            despues={
                "intento": intentos,
                "motivo": "pasarela_no_disponible",
                "monto_centavos": actual.monto_centavos,
            },
        )
        return actual

    # -- §10: cancelación y reprogramación (D12) --------------------------

    def anticipacion_de_sena(self, *, tenant_id: str, turno_id: str) -> int | None:
        """Snapshot de la política que firmó la seña de ese turno (`F-19`).

        C-06 autoriza la cancelación/reprogramación con este valor y no con la
        configuración viva: un cambio de parámetro no reescribe lo prometido.
        """
        sena = self._senas.por_turno(tenant_id=tenant_id, turno_id=turno_id)
        return None if sena is None else sena.anticipacion_cancelacion_h

    def cancelar_con_sena(
        self, *, tenant_id: str, turno_id: str, ahora: datetime | None = None
    ) -> Sena | None:
        """Efecto de una cancelación con anticipación suficiente (D12).

        `PENDIENTE` ⇒ `LIBERADA` (no se cobró nada); `ACREDITADA` ⇒ `DEVUELTA`
        con `motivo_devolucion='POLITICA_CANCELACION'` y `devuelta_por=NULL`.
        `APLICADA`/`DEVUELTA`/`LIBERADA` no cambian: la plata ya está en caja o
        la seña ya está resuelta.
        """
        momento = self._momento(ahora)
        with self._uow_factory():
            sena = self._senas.por_turno(tenant_id=tenant_id, turno_id=turno_id)
            if sena is None:
                return None
            if sena.estado == "PENDIENTE":
                liberada = self._senas.transicionar(
                    tenant_id=tenant_id,
                    sena_id=sena.id,
                    desde="PENDIENTE",
                    hacia="LIBERADA",
                    campos={
                        "liberada_en": momento,
                        "motivo_liberacion": MOTIVO_CANCELACION,
                    },
                )
                if liberada is None:
                    return None
                self._auditar(
                    tenant_id=tenant_id,
                    accion="SENA_LIBERADA",
                    sena=liberada,
                    antes={"estado": "PENDIENTE"},
                    despues={
                        "estado": "LIBERADA",
                        "motivo_liberacion": MOTIVO_CANCELACION,
                        "turno_id": liberada.turno_id,
                        "monto_centavos": liberada.monto_centavos,
                    },
                )
                return liberada
            if sena.estado == "ACREDITADA":
                devuelta = self._senas.transicionar(
                    tenant_id=tenant_id,
                    sena_id=sena.id,
                    desde="ACREDITADA",
                    hacia="DEVUELTA",
                    campos={
                        "devuelta_en": momento,
                        "motivo_devolucion": "POLITICA_CANCELACION",
                        "devuelta_por": None,
                    },
                )
                if devuelta is None:
                    return None
                self._auditar(
                    tenant_id=tenant_id,
                    accion="SENA_DEVUELTA",
                    sena=devuelta,
                    antes={"estado": "ACREDITADA"},
                    despues={
                        "estado": "DEVUELTA",
                        "motivo_devolucion": "POLITICA_CANCELACION",
                        "devuelta_por": None,
                        "monto_centavos": devuelta.monto_centavos,
                    },
                )
                return devuelta
            return None

    def transferir_a_turno(
        self,
        *,
        tenant_id: str,
        turno_anterior: str,
        turno_nuevo: str,
        turno_inicio: datetime,
        turno_fin: datetime | None = None,
        ahora: datetime | None = None,
    ) -> SenaTransferida | None:
        """Mueve la seña al turno nuevo sin cobrar dos veces (C11-OQ-04).

        `PENDIENTE` recalcula `expira_at = min(ahora + SENA_TTL_H, nuevo.inicio)`;
        el token se conserva si no venció y se reemite si venció (`F-16`).
        `ACREDITADA` se transfiere igual y sin cambiar de estado. `APLICADA`,
        `DEVUELTA` y `LIBERADA` no se transfieren y se audita el motivo.
        """
        momento = self._momento(ahora)
        with self._uow_factory():
            sena = self._senas.por_turno(
                tenant_id=tenant_id, turno_id=turno_anterior
            )
            if sena is None:
                return None

            if sena.estado in ("APLICADA", "DEVUELTA", "LIBERADA"):
                self._auditar(
                    tenant_id=tenant_id,
                    accion="SENA_NO_TRANSFERIDA",
                    sena=sena,
                    antes={"turno_id": turno_anterior, "estado": sena.estado},
                    despues={
                        "turno_id": turno_anterior,
                        "turno_nuevo": turno_nuevo,
                        "motivo": f"ESTADO_{sena.estado}",
                        "monto_centavos": sena.monto_centavos,
                    },
                )
                return None

            expira_nueva = min(
                momento + timedelta(hours=self._sena_ttl_h), turno_inicio
            )
            campos: dict[str, Any] = {
                "turno_id": turno_nuevo,
                "expira_at": expira_nueva,
                # Proyección del turno para la vista pública (memoria); en SQL el
                # join de `listar` es la fuente y estas claves no son columnas.
                "turno_inicio": turno_inicio,
            }
            if turno_fin is not None:
                campos["turno_fin"] = turno_fin
            actualizada = self._senas.actualizar(
                tenant_id=tenant_id,
                sena_id=sena.id,
                campos=campos,
            )
            if actualizada is None:
                return None

            token: str | None = None
            reemitido = False
            if sena.estado == "PENDIENTE" and sena.expira_at <= momento:
                token = generar_token()
                actualizada = self._senas.reemitir_token(
                    tenant_id=tenant_id,
                    sena_id=sena.id,
                    token_hash=hash_token(token),
                    ahora=momento,
                )
                reemitido = True

            self._auditar(
                tenant_id=tenant_id,
                accion="SENA_TRANSFERIDA",
                sena=actualizada,
                antes={
                    "turno_id": turno_anterior,
                    "expira_at": sena.expira_at.isoformat(),
                },
                despues={
                    "turno_id": turno_nuevo,
                    "expira_at": actualizada.expira_at.isoformat(),
                    "estado": actualizada.estado,
                    "monto_centavos": actualizada.monto_centavos,
                    "token_reemitido": reemitido,
                },
            )
            logger.info(
                "sena_transferida tenant_id=%s sena_id=%s turno_anterior=%s"
                " turno_nuevo=%s token_reemitido=%s",
                tenant_id,
                actualizada.id,
                turno_anterior,
                turno_nuevo,
                reemitido,
            )
            return SenaTransferida(
                sena=actualizada, token_sena=token, token_reemitido=reemitido
            )

    # -- superficie pública --------------------------------------------

    def leer_publica(
        self,
        *,
        token_tenant: str,
        token: str,
        ip: str,
        ahora: datetime | None = None,
    ) -> SenaPublica:
        """`GET .../senas/{token}`: allow-list pública, sin login y con rate-limit."""
        momento = self._momento(ahora)
        tenant_id = self._resolver_tenant(token_tenant)
        self._chequear_rate_limit(tenant_id=tenant_id, accion="sena", ip=ip)
        sena = self._por_token_publico(tenant_id=tenant_id, token=token)
        logger.info(
            "sena_publica_leida tenant_id=%s sena_id=%s estado=%s",
            tenant_id,
            sena.id,
            sena.estado,
        )
        return self._vista(sena, momento)

    def pedir_preferencia(
        self,
        *,
        token_tenant: str,
        token: str,
        ip: str,
        ahora: datetime | None = None,
    ) -> ResultadoPreferencia:
        """`POST .../senas/{token}/preferencia`: idempotente y con guarda de vencimiento."""
        momento = self._momento(ahora)
        tenant_id = self._resolver_tenant(token_tenant)
        self._chequear_rate_limit(tenant_id=tenant_id, accion="preferencia_sena", ip=ip)
        sena = self._por_token_publico(tenant_id=tenant_id, token=token)

        if sena.estado != "PENDIENTE":
            raise ConflictoSena(
                CODIGO_ESTADO_INVALIDO, f"la seña está {sena.estado}"
            )
        # F-09: la guarda decide antes de la red, aunque la seña siga PENDIENTE.
        if sena.expira_at <= momento:
            raise SenaVencida()
        if sena.preferencia_estado == "CREADA" and sena.mp_init_point is not None:
            return ResultadoPreferencia(resultado="EXISTENTE", vista=self._vista(sena, momento))
        if sena.proximo_reintento_at is not None and sena.proximo_reintento_at > momento:
            return ResultadoPreferencia(
                resultado="BACKOFF",
                vista=self._vista(sena, momento),
                reintentar_en=sena.proximo_reintento_at,
            )

        actual = self._intentar_preferencia(sena=sena, token=token, momento=momento)
        if actual.preferencia_estado == "CREADA":
            return ResultadoPreferencia(resultado="CREADA", vista=self._vista(actual, momento))
        return ResultadoPreferencia(
            resultado="BACKOFF",
            vista=self._vista(actual, momento),
            reintentar_en=actual.proximo_reintento_at,
        )

    # -- helpers --------------------------------------------------------

    def _momento(self, ahora: datetime | None) -> datetime:
        if ahora is not None:
            return ahora
        if self._reloj is not None:
            return self._reloj()
        raise RuntimeError("ServicioSenas requiere un reloj inyectado o `ahora`")

    def _resolver_tenant(self, token_tenant: str) -> str:
        tenant_id = self._tenants.resolver(token_tenant) if self._tenants is not None else None
        if tenant_id is None:
            raise NoEncontrado("recurso no encontrado")
        return tenant_id

    def _chequear_rate_limit(self, *, tenant_id: str, accion: str, ip: str) -> None:
        if self._contador is None:
            return
        clave_ip = f"ip:{tenant_id}:{ip}"
        clave_accion = f"accion:{tenant_id}:{accion}"
        n_ip = self._contador.incrementar(clave_ip, self._rate_limit_ventana_s)
        n_accion = self._contador.incrementar(clave_accion, self._rate_limit_ventana_s)
        if n_ip > self._rate_limit_max or n_accion > self._rate_limit_max:
            retry = max(self._contador.ttl_s(clave_ip), self._contador.ttl_s(clave_accion))
            raise DemasiadasSolicitudes("demasiadas solicitudes", retry)

    def _por_token_publico(self, *, tenant_id: str, token: str) -> Sena:
        """Resuelve por hash **dentro del tenant**; cualquier fallo es el mismo `404`."""
        sena = self._senas.por_token(tenant_id=tenant_id, token_hash=hash_token(token))
        if sena is None:
            raise NoEncontrado("recurso no encontrado")
        return sena

    def _recargar(self, sena: Sena) -> Sena:
        actual = self._senas.obtener(tenant_id=sena.tenant_id, sena_id=sena.id)
        return actual if actual is not None else sena

    def _url_de_pago(self, token: str) -> str:
        if not self._url_pago_base:
            return ""
        return f"{self._url_pago_base}/{token}"

    def _politica(self, sena: Sena) -> PoliticaSena:
        return PoliticaSena(
            anticipacion_cancelacion_h=sena.anticipacion_cancelacion_h,
            # La promesa no depende del estado (D12/F-01).
            reembolsable=True,
            hay_pago_acreditado=sena.estado == "ACREDITADA",
        )

    def _vista(self, sena: Sena, momento: datetime) -> SenaPublica:
        vigente = sena.estado == "PENDIENTE" and sena.expira_at > momento
        return SenaPublica(
            sena_id=sena.id,
            estado=sena.estado,
            monto_centavos=sena.monto_centavos,
            expira_at=sena.expira_at,
            preferencia_estado=sena.preferencia_estado,
            init_point=sena.mp_init_point if vigente else None,
            turno=TurnoSenaVista(
                inicio=sena.turno_inicio or sena.creado_en,
                fin=sena.turno_fin or sena.expira_at,
                prestacion=sena.turno_prestacion or "",
            ),
            politica=self._politica(sena),
        )

    def _auditar(
        self,
        *,
        tenant_id: str,
        accion: AccionSena,
        sena: Sena,
        antes: Mapping[str, Any] | None = None,
        despues: Mapping[str, Any] | None = None,
        actor: str = "publico",
    ) -> None:
        self._auditoria.registrar(
            tenant_id=tenant_id,
            accion=accion,
            actor=actor,
            entidad="sena",
            entidad_id=sena.id,
            antes=antes,
            despues=despues,
        )
