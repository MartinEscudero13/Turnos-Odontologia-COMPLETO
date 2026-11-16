"""Repositorios SQLAlchemy de C-15: config, usuarios, exportación y KPIs."""
from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.admin.puertos import (
    DatosReporte,
    UsuarioAdmin,
    UsuarioDuplicado,
)
from app.models.caja import MovimientoCaja
from app.models.calendario import CalendarLink
from app.models.catalogos import HorarioSemanal, Paciente, Prestacion, Profesional
from app.models.obras_sociales import Cobertura, Liquidacion, ObraSocial
from app.models.sena import Sena
from app.models.tenant import ParametroTenant
from app.models.turno import Turno
from app.models.usuario import Usuario

__all__ = ["ConfigSQL", "ExportacionSQL", "ReportesSQL", "UsuariosSQL"]

TZ_OPERATIVA = timezone(timedelta(hours=-3))


def _uuid(valor: str) -> uuid.UUID:
    return uuid.UUID(valor)


def _fijar_tenant(session: Session, tenant_id: str) -> None:
    session.execute(
        text("SELECT set_config('app.tenant_id', :tenant, true)"), {"tenant": tenant_id}
    )


def _a_usuario(modelo: Usuario) -> UsuarioAdmin:
    return UsuarioAdmin(
        id=str(modelo.id),
        tenant_id=str(modelo.tenant_id),
        nombre=modelo.nombre,
        email=modelo.email,
        rol=modelo.rol,
        activo=modelo.activo,
        creado_en=modelo.creado_en,
    )


class ConfigSQL:
    def __init__(self, session: Session) -> None:
        self._session = session

    def obtener(self, *, tenant_id: str) -> dict[str, object]:
        _fijar_tenant(self._session, tenant_id)
        filas = self._session.scalars(
            select(ParametroTenant).where(ParametroTenant.tenant_id == _uuid(tenant_id))
        )
        return {fila.clave: fila.valor for fila in filas}

    def actualizar(
        self, *, tenant_id: str, valores: dict[str, object], ahora: datetime
    ) -> dict[str, object]:
        _fijar_tenant(self._session, tenant_id)
        for clave, valor in valores.items():
            fila = self._session.get(ParametroTenant, (_uuid(tenant_id), clave))
            if fila is None:
                self._session.add(
                    ParametroTenant(
                        tenant_id=_uuid(tenant_id),
                        clave=clave,
                        valor=valor,
                        actualizado_en=ahora,
                    )
                )
            else:
                fila.valor = valor
                fila.actualizado_en = ahora
        self._session.flush()
        return self.obtener(tenant_id=tenant_id)


class UsuariosSQL:
    def __init__(self, session: Session) -> None:
        self._session = session

    def listar(self, *, tenant_id: str) -> list[UsuarioAdmin]:
        _fijar_tenant(self._session, tenant_id)
        return [
            _a_usuario(modelo)
            for modelo in self._session.scalars(
                select(Usuario)
                .where(Usuario.tenant_id == _uuid(tenant_id))
                .order_by(Usuario.email)
            )
        ]

    def obtener(self, *, tenant_id: str, usuario_id: str) -> UsuarioAdmin | None:
        _fijar_tenant(self._session, tenant_id)
        modelo = self._session.scalar(
            select(Usuario).where(
                Usuario.id == _uuid(usuario_id), Usuario.tenant_id == _uuid(tenant_id)
            )
        )
        return None if modelo is None else _a_usuario(modelo)

    def por_email(self, *, tenant_id: str, email: str) -> UsuarioAdmin | None:
        _fijar_tenant(self._session, tenant_id)
        modelo = self._session.scalar(
            select(Usuario).where(
                Usuario.tenant_id == _uuid(tenant_id), Usuario.email == email
            )
        )
        return None if modelo is None else _a_usuario(modelo)

    def crear(
        self,
        *,
        tenant_id: str,
        nombre: str,
        email: str,
        password_hash: str,
        rol: str,
        ahora: datetime,
    ) -> UsuarioAdmin:
        _fijar_tenant(self._session, tenant_id)
        modelo = Usuario(
            tenant_id=_uuid(tenant_id),
            nombre=nombre,
            email=email,
            password_hash=password_hash,
            rol=rol,
            two_factor=False,
            activo=True,
            creado_en=ahora,
        )
        try:
            with self._session.begin_nested():
                self._session.add(modelo)
                self._session.flush()
        except IntegrityError as exc:
            raise UsuarioDuplicado(email) from exc
        return _a_usuario(modelo)

    def cambiar_activo(
        self, *, tenant_id: str, usuario_id: str, activo: bool
    ) -> UsuarioAdmin:
        _fijar_tenant(self._session, tenant_id)
        modelo = self._session.scalar(
            select(Usuario).where(
                Usuario.id == _uuid(usuario_id), Usuario.tenant_id == _uuid(tenant_id)
            )
        )
        if modelo is None:
            raise KeyError(usuario_id)
        modelo.activo = activo
        self._session.flush()
        return _a_usuario(modelo)


class ExportacionSQL:
    """Allow-list de tablas; nunca exporta hashes, tokens ni configuraciones OAuth."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def exportar(self, *, tenant_id: str) -> dict[str, list[dict[str, object]]]:
        _fijar_tenant(self._session, tenant_id)
        t = _uuid(tenant_id)
        secciones: dict[str, list[dict[str, object]]] = {}

        secciones["pacientes"] = [
            {
                "id": str(p.id),
                "nombre": p.nombre,
                "telefono": p.telefono,
                "email": p.email,
                "obra_social_id": None if p.obra_social_id is None else str(p.obra_social_id),
                "nro_afiliado": p.nro_afiliado,
                "consentimiento_ok": p.consentimiento_ok,
                "creado_en": p.creado_en,
            }
            for p in self._session.scalars(select(Paciente).where(Paciente.tenant_id == t))
        ]
        secciones["profesionales"] = [
            {
                "id": str(p.id),
                "nombre": p.nombre,
                "especialidad": p.especialidad,
                "matricula": p.matricula,
                "activo": p.activo,
            }
            for p in self._session.scalars(select(Profesional).where(Profesional.tenant_id == t))
        ]
        secciones["prestaciones"] = [
            {
                "id": str(p.id),
                "nombre": p.nombre,
                "duracion_min": p.duracion_min,
                "precio_base": p.precio_base,
                "activa": p.activa,
            }
            for p in self._session.scalars(select(Prestacion).where(Prestacion.tenant_id == t))
        ]
        secciones["turnos"] = [
            {
                "id": str(x.id),
                "profesional_id": str(x.profesional_id),
                "sillon_id": str(x.sillon_id),
                "paciente_id": str(x.paciente_id),
                "prestacion_id": str(x.prestacion_id),
                "inicio": x.inicio,
                "fin": x.fin,
                "estado": x.estado,
                "origen": x.origen,
                "sobreturno": x.sobreturno,
            }
            for x in self._session.scalars(select(Turno).where(Turno.tenant_id == t))
        ]
        secciones["movimientos_caja"] = [
            {
                "id": str(x.id),
                "fecha": x.fecha,
                "medio": x.medio,
                "monto": x.monto,
                "tipo": x.tipo,
                "turno_id": None if x.turno_id is None else str(x.turno_id),
                "usuario_id": x.usuario_id,
                "anulado": x.anulado,
            }
            for x in self._session.scalars(
                select(MovimientoCaja).where(MovimientoCaja.tenant_id == t)
            )
        ]
        secciones["senas"] = [
            {
                "id": str(x.id),
                "turno_id": str(x.turno_id),
                "monto_centavos": x.monto_centavos,
                "estado": x.estado,
                "expira_at": x.expira_at,
            }
            for x in self._session.scalars(select(Sena).where(Sena.tenant_id == t))
        ]
        secciones["obras_sociales"] = [
            {"id": str(x.id), "nombre": x.nombre, "activa": x.activa}
            for x in self._session.scalars(select(ObraSocial).where(ObraSocial.tenant_id == t))
        ]
        secciones["coberturas"] = [
            {
                "id": str(x.id),
                "obra_social_id": str(x.obra_social_id),
                "prestacion_id": str(x.prestacion_id),
                "modo": x.modo,
                "valor": x.valor,
                "tope_centavos": x.tope_centavos,
            }
            for x in self._session.scalars(select(Cobertura).where(Cobertura.tenant_id == t))
        ]
        secciones["liquidaciones"] = [
            {
                "id": str(x.id),
                "obra_social_id": str(x.obra_social_id),
                "periodo_desde": x.periodo_desde,
                "periodo_hasta": x.periodo_hasta,
                "estado": x.estado,
                "total_centavos": x.total_centavos,
            }
            for x in self._session.scalars(select(Liquidacion).where(Liquidacion.tenant_id == t))
        ]
        secciones["calendar_links"] = [
            {
                "id": str(x.id),
                "profesional_id": str(x.profesional_id),
                "gcal_calendar_id": x.gcal_calendar_id,
                "estado": x.estado,
            }
            for x in self._session.scalars(select(CalendarLink).where(CalendarLink.tenant_id == t))
        ]
        return secciones


class ReportesSQL:
    def __init__(self, session: Session) -> None:
        self._session = session

    def datos(self, *, tenant_id: str, desde: date, hasta: date) -> DatosReporte:
        _fijar_tenant(self._session, tenant_id)
        t = _uuid(tenant_id)
        inicio = datetime.combine(desde, time.min, tzinfo=TZ_OPERATIVA)
        fin = datetime.combine(hasta, time.min, tzinfo=TZ_OPERATIVA) + timedelta(days=1)
        turnos = list(
            self._session.execute(
                select(
                    Turno.estado, Turno.origen, Turno.creado_en, Turno.inicio, Turno.fin
                ).where(
                    Turno.tenant_id == t, Turno.inicio >= inicio, Turno.inicio < fin
                )
            ).all()
        )
        por_estado: dict[str, int] = {}
        for estado, _, _, _, _ in turnos:
            por_estado[estado] = por_estado.get(estado, 0) + 1
        online = sum(1 for _, origen, _, _, _ in turnos if origen == "RESERVA_ONLINE")
        reasignados = sum(
            1
            for _, origen, creado_en, inicio_turno, _ in turnos
            if origen == "LISTA_ESPERA" and creado_en >= inicio_turno - timedelta(hours=2)
        )
        # Ocupación: minutos de turnos que bloquean agenda sobre la capacidad
        # semanal ofrecida por los profesionales en el período.
        minutos_ocupados = sum(
            int((fin_turno - inicio_turno).total_seconds() // 60)
            for estado, _, _, inicio_turno, fin_turno in turnos
            if estado in ("PENDIENTE", "CONFIRMADO", "PRESENTE", "AUSENTE")
        )
        capacidad = {
            (profesional, dia): int(
                (
                    datetime.combine(date.min, hasta_h)
                    - datetime.combine(date.min, desde_h)
                ).total_seconds()
                // 60
            )
            for profesional, dia, desde_h, hasta_h in self._session.execute(
                select(
                    HorarioSemanal.profesional_id,
                    HorarioSemanal.dia,
                    HorarioSemanal.desde,
                    HorarioSemanal.hasta,
                ).where(HorarioSemanal.tenant_id == t)
            ).all()
        }
        minutos_disponibles = 0
        dia_actual = desde
        while dia_actual <= hasta:
            dia_semana = dia_actual.isoweekday()
            minutos_disponibles += sum(
                minutos
                for (_, dia), minutos in capacidad.items()
                if dia == dia_semana
            )
            dia_actual += timedelta(days=1)
        facturacion = self._session.execute(
            select(Turno.profesional_id, func.sum(MovimientoCaja.monto))
            .join(Turno, Turno.id == MovimientoCaja.turno_id)
            .where(
                MovimientoCaja.tenant_id == t,
                MovimientoCaja.tipo == "INGRESO",
                MovimientoCaja.anulado.is_(False),
                MovimientoCaja.fecha >= desde,
                MovimientoCaja.fecha <= hasta,
            )
            .group_by(Turno.profesional_id)
            .order_by(Turno.profesional_id)
        ).all()
        return DatosReporte(
            total_turnos=len(turnos),
            por_estado=por_estado,
            online=online,
            facturacion_por_profesional=tuple(
                (str(profesional), int(total or 0)) for profesional, total in facturacion
            ),
            reasignados_2h=reasignados,
            minutos_ocupados=minutos_ocupados,
            minutos_disponibles=minutos_disponibles,
        )
