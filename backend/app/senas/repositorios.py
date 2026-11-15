"""Repositorios SQLAlchemy de señas y pagos — C-11 §6–§8 (locks reales).

Adaptadores de persistencia de los puertos de `puertos.py` sobre una `Session`
compartida. Existen por una razón concreta: **los locks no existen en memoria**
(D11). `bloquear` es `SELECT … FOR UPDATE` sobre la fila de la seña, y
`transicionar` es un `UPDATE … WHERE estado = <esperado>` condicional; sin esas
dos cosas, la carrera acreditación ↔ expiración no se puede probar ni garantizar.

Reglas que respeta cada método:

- `set_config('app.tenant_id', …, true)` antes de tocar `senas`/`pagos_mp`, para
  que la RLS forzada de la 009 aplique con el rol de la aplicación.
- Filtro explícito `tenant_id = :tenant` en **todas** las consultas: la RLS es la
  segunda línea de defensa, no la única (regla dura: ninguna query sin tenant).
- `mp_payment_id` y `token_hash` son únicos **globales**: la colisión se resuelve
  en el `INSERT` (`ON CONFLICT DO NOTHING`), nunca con una lectura cross-tenant.
- `moneda` guarda la moneda real que informa la pasarela (`ARS`, `USD`, …); el
  `CHECK` de la 009 sólo prohíbe el vacío y exige mayúsculas.
"""
from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import replace
from datetime import datetime
from typing import Any, cast

from sqlalchemy import select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.sena import PagoMP as PagoMPModel
from app.models.sena import Sena as SenaModel
from app.models.turno import Turno as TurnoModel
from app.senas.puertos import (
    EstadoPagoMP,
    EstadoSena,
    PagoMP,
    ResultadoPagoMP,
    Sena,
    SenaDuplicada,
    SenaInvalida,
    TokenDuplicado,
    TransicionTurnoInvalida,
    TurnoRef,
    rango_estado,
)
from app.turnos.servicio import NoEncontrado


def _rowcount(resultado: Any) -> int:
    return int(getattr(resultado, "rowcount", 0))

__all__ = [
    "PagoMPRepositorioSQL",
    "SenaRepositorioSQL",
    "TurnosSenaSQL",
]

_UNIQUE_TURNO = "senas_tenant_turno_unique"
_UNIQUE_TOKEN = "senas_token_hash_unique"


def _uuid(valor: str) -> uuid.UUID:
    return uuid.UUID(valor)


def _mensaje(exc: IntegrityError) -> str:
    return str(getattr(exc, "orig", exc))


def _fijar_tenant(session: Session, tenant_id: str) -> None:
    """Fija `app.tenant_id` para la RLS fail-closed de la 009 (transacción local)."""
    session.execute(
        text("SELECT set_config('app.tenant_id', :tenant, true)"),
        {"tenant": tenant_id},
    )


# ---------------------------------------------------------------------------
# Señas
# ---------------------------------------------------------------------------


def _sena(fila: SenaModel) -> Sena:
    return Sena(
        id=str(fila.id),
        tenant_id=str(fila.tenant_id),
        turno_id=str(fila.turno_id),
        monto_centavos=fila.monto_centavos,
        estado=cast(EstadoSena, fila.estado),
        regla_modo=cast(Any, fila.regla_modo),
        regla_valor=fila.regla_valor,
        precio_base_centavos=fila.precio_base_centavos,
        anticipacion_cancelacion_h=fila.anticipacion_cancelacion_h,
        expira_at=fila.expira_at,
        token_hash=fila.token_hash,
        creado_en=fila.creado_en,
        mp_preference_id=fila.mp_preference_id,
        mp_init_point=fila.mp_init_point,
        preferencia_estado=cast(Any, fila.preferencia_estado),
        intentos_preferencia=fila.intentos_preferencia,
        proximo_reintento_at=fila.proximo_reintento_at,
        token_rotado_en=fila.token_rotado_en,
        acreditada_en=fila.acreditada_en,
        aplicada_en=fila.aplicada_en,
        liberada_en=fila.liberada_en,
        devuelta_en=fila.devuelta_en,
        motivo_liberacion=fila.motivo_liberacion,
        concepto_aplicacion=cast(Any, fila.concepto_aplicacion),
        devuelta_por=str(fila.devuelta_por) if fila.devuelta_por is not None else None,
        motivo_devolucion=fila.motivo_devolucion,
        movimiento_caja_id=(
            str(fila.movimiento_caja_id) if fila.movimiento_caja_id is not None else None
        ),
    )


class SenaRepositorioSQL:
    """`SenaRepositorio` sobre `senas`: lock de fila y transición condicional."""

    def __init__(self, session: Session) -> None:
        self._session = session

    # -- lectura --------------------------------------------------------

    def obtener(self, *, tenant_id: str, sena_id: str) -> Sena | None:
        _fijar_tenant(self._session, tenant_id)
        fila = self._session.get(SenaModel, _uuid(sena_id))
        if fila is None or str(fila.tenant_id) != tenant_id:
            return None
        return _sena(fila)

    def por_turno(self, *, tenant_id: str, turno_id: str) -> Sena | None:
        _fijar_tenant(self._session, tenant_id)
        fila = self._session.scalars(
            select(SenaModel).where(
                SenaModel.tenant_id == _uuid(tenant_id),
                SenaModel.turno_id == _uuid(turno_id),
            )
        ).first()
        return None if fila is None else _sena(fila)

    def por_token(self, *, tenant_id: str, token_hash: str) -> Sena | None:
        _fijar_tenant(self._session, tenant_id)
        fila = self._session.scalars(
            select(SenaModel).where(
                SenaModel.tenant_id == _uuid(tenant_id),
                SenaModel.token_hash == token_hash,
            )
        ).first()
        return None if fila is None else _sena(fila)

    def listar(
        self,
        *,
        tenant_id: str,
        desde: datetime | None = None,
        hasta: datetime | None = None,
    ) -> list[Sena]:
        """Señas del tenant ordenadas y filtradas por `turno.inicio` (C11-OQ-10)."""
        _fijar_tenant(self._session, tenant_id)
        consulta = (
            select(SenaModel, TurnoModel)
            .join(TurnoModel, TurnoModel.id == SenaModel.turno_id)
            .where(SenaModel.tenant_id == _uuid(tenant_id))
        )
        if desde is not None:
            consulta = consulta.where(TurnoModel.inicio >= desde)
        if hasta is not None:
            consulta = consulta.where(TurnoModel.inicio < hasta)
        filas = self._session.execute(
            consulta.order_by(TurnoModel.inicio, SenaModel.id)
        ).all()
        return [_sena_con_turno(sena, turno) for sena, turno in filas]

    def vencidas(self, *, tenant_id: str, ahora: datetime) -> list[Sena]:
        _fijar_tenant(self._session, tenant_id)
        filas = self._session.scalars(
            select(SenaModel)
            .where(
                SenaModel.tenant_id == _uuid(tenant_id),
                SenaModel.estado == "PENDIENTE",
                SenaModel.expira_at <= ahora,
            )
            .order_by(SenaModel.expira_at, SenaModel.id)
        ).all()
        return [_sena(fila) for fila in filas]

    def bloquear(self, *, tenant_id: str, sena_id: str) -> Sena:
        """`SELECT … FOR UPDATE`: punto único de serialización (D11)."""
        _fijar_tenant(self._session, tenant_id)
        fila = self._session.get(
            SenaModel, _uuid(sena_id), with_for_update=True
        )
        if fila is None or str(fila.tenant_id) != tenant_id:
            raise NoEncontrado("seña no encontrada")
        return _sena(fila)

    # -- escritura ------------------------------------------------------

    def crear(
        self,
        *,
        tenant_id: str,
        turno_id: str,
        monto_centavos: int,
        regla_modo: Any,
        regla_valor: int,
        precio_base_centavos: int,
        anticipacion_cancelacion_h: int,
        expira_at: datetime,
        token_hash: str,
        ahora: datetime | None = None,
        turno_inicio: datetime | None = None,
        turno_fin: datetime | None = None,
        turno_prestacion: str | None = None,
    ) -> Sena:
        del turno_inicio, turno_fin, turno_prestacion  # proyección, no columnas
        if monto_centavos <= 0:
            raise SenaInvalida("el monto de la seña debe ser positivo")
        _fijar_tenant(self._session, tenant_id)
        fila = SenaModel(
            tenant_id=_uuid(tenant_id),
            turno_id=_uuid(turno_id),
            monto_centavos=monto_centavos,
            estado="PENDIENTE",
            regla_modo=cast(str, regla_modo),
            regla_valor=regla_valor,
            precio_base_centavos=precio_base_centavos,
            anticipacion_cancelacion_h=anticipacion_cancelacion_h,
            expira_at=expira_at,
            token_hash=token_hash,
        )
        if ahora is not None:
            fila.creado_en = ahora
        self._session.add(fila)
        try:
            self._session.flush()
        except IntegrityError as exc:
            mensaje = _mensaje(exc)
            if _UNIQUE_TOKEN in mensaje:
                raise TokenDuplicado("el token_hash ya existe") from exc
            if _UNIQUE_TURNO in mensaje:
                raise SenaDuplicada("el turno ya tiene seña") from exc
            raise
        return _sena(fila)

    def transicionar(
        self,
        *,
        tenant_id: str,
        sena_id: str,
        desde: EstadoSena,
        hacia: EstadoSena,
        campos: Mapping[str, Any] | None = None,
    ) -> Sena | None:
        """Transición condicional: `None` si la seña ya no está en `desde`."""
        _fijar_tenant(self._session, tenant_id)
        valores: dict[str, Any] = dict(campos or {})
        valores["estado"] = hacia
        resultado = self._session.execute(
            update(SenaModel)
            .where(
                SenaModel.tenant_id == _uuid(tenant_id),
                SenaModel.id == _uuid(sena_id),
                SenaModel.estado == desde,
            )
            .values(**valores)
        )
        if _rowcount(resultado) != 1:
            return None
        self._session.flush()
        return self.obtener(tenant_id=tenant_id, sena_id=sena_id)

    def actualizar(
        self,
        *,
        tenant_id: str,
        sena_id: str,
        campos: Mapping[str, Any],
        desde: EstadoSena | None = None,
    ) -> Sena | None:
        datos = dict(campos)
        if "estado" in datos:
            raise SenaInvalida("usá transicionar para cambiar el estado")
        # Metadatos de proyección del adaptador en memoria: no son columnas.
        for proyeccion in ("turno_inicio", "turno_fin", "turno_prestacion"):
            datos.pop(proyeccion, None)
        _fijar_tenant(self._session, tenant_id)
        condiciones = [
            SenaModel.tenant_id == _uuid(tenant_id),
            SenaModel.id == _uuid(sena_id),
        ]
        if desde is not None:
            condiciones.append(SenaModel.estado == desde)
        resultado = self._session.execute(
            update(SenaModel).where(*condiciones).values(**datos)
        )
        if _rowcount(resultado) != 1:
            if self.obtener(tenant_id=tenant_id, sena_id=sena_id) is None:
                raise NoEncontrado("seña no encontrada")
            return None
        self._session.flush()
        return self.obtener(tenant_id=tenant_id, sena_id=sena_id)

    def reemitir_token(
        self,
        *,
        tenant_id: str,
        sena_id: str,
        token_hash: str,
        ahora: datetime | None = None,
    ) -> Sena:
        if not token_hash:
            raise SenaInvalida("la seña exige token")
        _fijar_tenant(self._session, tenant_id)
        try:
            resultado = self._session.execute(
                update(SenaModel)
                .where(
                    SenaModel.tenant_id == _uuid(tenant_id),
                    SenaModel.id == _uuid(sena_id),
                )
                .values(token_hash=token_hash, token_rotado_en=ahora)
            )
        except IntegrityError as exc:
            raise TokenDuplicado("el token_hash ya existe") from exc
        if _rowcount(resultado) != 1:
            raise NoEncontrado("seña no encontrada")
        self._session.flush()
        actual = self.obtener(tenant_id=tenant_id, sena_id=sena_id)
        if actual is None:
            raise NoEncontrado("seña no encontrada")
        return actual


def _sena_con_turno(sena: SenaModel, turno: TurnoModel) -> Sena:
    return replace(
        _sena(sena),
        turno_inicio=turno.inicio,
        turno_fin=turno.fin,
        turno_prestacion=str(turno.prestacion_id),
    )


# ---------------------------------------------------------------------------
# Pagos
# ---------------------------------------------------------------------------


def _pago(fila: PagoMPModel) -> PagoMP:
    return PagoMP(
        id=str(fila.id),
        tenant_id=str(fila.tenant_id),
        mp_payment_id=fila.mp_payment_id,
        sena_id=str(fila.sena_id),
        monto_centavos=fila.monto_centavos,
        moneda=fila.moneda,
        estado=cast(EstadoPagoMP, fila.estado),
        resultado=cast(ResultadoPagoMP, fila.resultado),
        raw_json=cast(Mapping[str, Any], fila.raw_json or {}),
        recibido_en=fila.recibido_en,
        actualizado_en=fila.actualizado_en,
        aprobado_en=fila.aprobado_en,
    )


class PagoMPRepositorioSQL:
    """`PagoMPRepositorio`: libro de idempotencia con `ON CONFLICT DO NOTHING`."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def obtener(self, *, tenant_id: str, mp_payment_id: str) -> PagoMP | None:
        _fijar_tenant(self._session, tenant_id)
        fila = self._session.scalars(
            select(PagoMPModel).where(
                PagoMPModel.tenant_id == _uuid(tenant_id),
                PagoMPModel.mp_payment_id == mp_payment_id,
            )
        ).first()
        return None if fila is None else _pago(fila)

    def listar(self, *, tenant_id: str, sena_id: str | None = None) -> list[PagoMP]:
        _fijar_tenant(self._session, tenant_id)
        consulta = select(PagoMPModel).where(PagoMPModel.tenant_id == _uuid(tenant_id))
        if sena_id is not None:
            consulta = consulta.where(PagoMPModel.sena_id == _uuid(sena_id))
        filas = self._session.scalars(
            consulta.order_by(PagoMPModel.recibido_en, PagoMPModel.id)
        ).all()
        return [_pago(fila) for fila in filas]

    def registrar_o_actualizar(
        self,
        *,
        tenant_id: str,
        sena_id: str,
        mp_payment_id: str,
        monto_centavos: int,
        moneda: str,
        estado: EstadoPagoMP,
        resultado: ResultadoPagoMP | None = None,
        raw_json: Mapping[str, Any],
        aprobado_en: datetime | None = None,
        ahora: datetime | None = None,
    ) -> PagoMP:
        if monto_centavos <= 0:
            raise SenaInvalida("el monto del pago debe ser positivo")
        if not moneda or moneda != moneda.upper():
            raise SenaInvalida("la moneda del pago debe venir normalizada")
        _fijar_tenant(self._session, tenant_id)
        valores: dict[str, Any] = {
            "tenant_id": _uuid(tenant_id),
            "sena_id": _uuid(sena_id),
            "mp_payment_id": mp_payment_id,
            "monto_centavos": monto_centavos,
            "moneda": moneda,
            "estado": estado,
            "resultado": resultado or "IGNORADO",
            "raw_json": dict(raw_json),
            "aprobado_en": aprobado_en,
        }
        if ahora is not None:
            valores["recibido_en"] = ahora
            valores["actualizado_en"] = ahora
        insertado = self._session.execute(
            pg_insert(PagoMPModel)
            .values(**valores)
            .on_conflict_do_nothing(index_elements=["mp_payment_id"])
        )
        if _rowcount(insertado) == 1:
            self._session.flush()
            creado = self.obtener(tenant_id=tenant_id, mp_payment_id=mp_payment_id)
            if creado is None:  # pragma: no cover - el INSERT acaba de commitear
                raise SenaInvalida("no se pudo registrar el pago")
            return creado

        existente = self.obtener(tenant_id=tenant_id, mp_payment_id=mp_payment_id)
        if existente is None:
            # La fila ganadora del UNIQUE global es de otro tenant: no se lee ni
            # se reescribe (F-04/F-05); el webhook responde `500`.
            raise SenaInvalida("el pago pertenece a otro tenant")
        estado_final = (
            estado
            if rango_estado(estado) > rango_estado(existente.estado)
            else existente.estado
        )
        self._session.execute(
            update(PagoMPModel)
            .where(
                PagoMPModel.tenant_id == _uuid(tenant_id),
                PagoMPModel.mp_payment_id == mp_payment_id,
            )
            .values(
                estado=estado_final,
                resultado=resultado if resultado is not None else existente.resultado,
                raw_json=dict(raw_json),
                actualizado_en=ahora,
                aprobado_en=(
                    aprobado_en if aprobado_en is not None else existente.aprobado_en
                ),
            )
        )
        self._session.flush()
        actualizado = self.obtener(tenant_id=tenant_id, mp_payment_id=mp_payment_id)
        if actualizado is None:  # pragma: no cover - la fila existe por definición
            raise SenaInvalida("no se pudo actualizar el pago")
        return actualizado


# ---------------------------------------------------------------------------
# Turnos (extensión mínima de C-05)
# ---------------------------------------------------------------------------


class TurnosSenaSQL:
    """`TurnoPort`: confirmar/cancelar por seña desde `PENDIENTE`, sin tocar C-05."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def turno_de(self, *, tenant_id: str, turno_id: str) -> TurnoRef | None:
        _fijar_tenant(self._session, tenant_id)
        fila = self._session.get(TurnoModel, _uuid(turno_id))
        if fila is None or str(fila.tenant_id) != tenant_id:
            return None
        return TurnoRef(
            id=str(fila.id),
            tenant_id=str(fila.tenant_id),
            estado=fila.estado,
            inicio=fila.inicio,
            fin=fila.fin,
            paciente_id=str(fila.paciente_id),
        )

    def confirmar_por_sena(
        self, *, tenant_id: str, turno_id: str, ahora: datetime
    ) -> None:
        self._transicionar(
            tenant_id=tenant_id, turno_id=turno_id, hacia="CONFIRMADO", ahora=ahora
        )

    def cancelar_por_sena(
        self,
        *,
        tenant_id: str,
        turno_id: str,
        motivo: str,
        ahora: datetime,
    ) -> None:
        del motivo  # el motivo de cancelación no es una columna de `turnos`
        self._transicionar(
            tenant_id=tenant_id, turno_id=turno_id, hacia="CANCELADO", ahora=ahora
        )

    def _transicionar(
        self, *, tenant_id: str, turno_id: str, hacia: str, ahora: datetime
    ) -> None:
        del ahora
        _fijar_tenant(self._session, tenant_id)
        resultado = self._session.execute(
            update(TurnoModel)
            .where(
                TurnoModel.tenant_id == _uuid(tenant_id),
                TurnoModel.id == _uuid(turno_id),
                TurnoModel.estado == "PENDIENTE",
            )
            .values(estado=hacia)
        )
        if _rowcount(resultado) == 1:
            self._session.flush()
            return
        actual = self.turno_de(tenant_id=tenant_id, turno_id=turno_id)
        if actual is None:
            raise NoEncontrado("turno no encontrado")
        raise TransicionTurnoInvalida(
            f"el turno no está PENDIENTE (está {actual.estado})"
        )
