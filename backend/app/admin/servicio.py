"""Casos de uso de C-15: configuración, usuarios, exportación y KPIs del tenant."""
from __future__ import annotations

import csv
import io
import json
from collections.abc import Callable
from datetime import UTC, date, datetime

from app.admin.puertos import (
    CODIGO_AUTO_DESACTIVACION,
    CODIGO_USUARIO_DUPLICADO,
    AuditoriaPort,
    ConfigRepositorio,
    ConflictoAdmin,
    ExportacionRepositorio,
    Kpis,
    ReportesRepositorio,
    UsuarioAdmin,
    UsuarioAdminRepositorio,
    UsuarioDuplicado,
)
from app.auth.security import hash_password
from app.turnos.servicio import Actor, Invalido, NoAutenticado, NoEncontrado, Prohibido

_ADMIN = frozenset({"ADMIN"})
_KPIS = frozenset({"ADMIN", "RECEPCION"})
_ROLES = frozenset({"ADMIN", "RECEPCION", "ODONTOLOGO"})
_CLAVES = frozenset(
    {
        "anticipacion_cancelacion_h",
        "sena_modo",
        "sena_valor",
        "recordatorios_habilitados",
    }
)
Reloj = Callable[[], datetime]


class ServicioAdmin:
    def __init__(
        self,
        config: ConfigRepositorio,
        usuarios: UsuarioAdminRepositorio,
        exportacion: ExportacionRepositorio,
        reportes: ReportesRepositorio,
        auditoria: AuditoriaPort,
        *,
        reloj: Reloj | None = None,
    ) -> None:
        self._config = config
        self._usuarios = usuarios
        self._exportacion = exportacion
        self._reportes = reportes
        self._auditoria = auditoria
        self._reloj: Reloj = reloj or (lambda: datetime.now(UTC))

    # ------------------------------------------------------------------
    # Configuración
    # ------------------------------------------------------------------

    def obtener_config(self, actor: Actor) -> dict[str, object]:
        self._exigir_admin(actor)
        return self._config.obtener(tenant_id=actor.tenant_id)

    def actualizar_config(
        self, actor: Actor, *, valores: dict[str, object]
    ) -> dict[str, object]:
        self._exigir_admin(actor)
        limpios = {clave: self._validar(clave, valor) for clave, valor in valores.items()}
        antes = self._config.obtener(tenant_id=actor.tenant_id)
        despues = self._config.actualizar(
            tenant_id=actor.tenant_id, valores=limpios, ahora=self._reloj()
        )
        self._auditar(
            actor,
            "CONFIG_ACTUALIZADA",
            "tenant_config",
            actor.tenant_id,
            antes=antes,
            despues=limpios,
        )
        return despues

    # ------------------------------------------------------------------
    # Usuarios
    # ------------------------------------------------------------------

    def listar_usuarios(self, actor: Actor) -> list[UsuarioAdmin]:
        self._exigir_admin(actor)
        return self._usuarios.listar(tenant_id=actor.tenant_id)

    def crear_usuario(
        self,
        actor: Actor,
        *,
        nombre: str,
        email: str,
        password: str,
        rol: str,
    ) -> UsuarioAdmin:
        self._exigir_admin(actor)
        nombre_limpio = nombre.strip()
        email_limpio = self._validar_email(email)
        if rol not in _ROLES:
            raise Invalido("rol inválido")
        if len(password) < 8:
            raise Invalido("la contraseña debe tener al menos 8 caracteres")
        try:
            usuario = self._usuarios.crear(
                tenant_id=actor.tenant_id,
                nombre=nombre_limpio,
                email=email_limpio,
                password_hash=hash_password(password),
                rol=rol,
                ahora=self._reloj(),
            )
        except UsuarioDuplicado as exc:
            raise ConflictoAdmin(
                CODIGO_USUARIO_DUPLICADO, "el email ya está registrado en el tenant"
            ) from exc
        self._auditar(
            actor, "USUARIO_CREADO", "usuario", usuario.id, despues={"email": email_limpio, "rol": rol}
        )
        return usuario

    def cambiar_estado_usuario(
        self, actor: Actor, *, usuario_id: str, activo: bool
    ) -> UsuarioAdmin:
        self._exigir_admin(actor)
        actual = self._usuarios.obtener(tenant_id=actor.tenant_id, usuario_id=usuario_id)
        if actual is None:
            raise NoEncontrado("usuario no encontrado")
        if not activo and usuario_id == actor.user_id:
            raise ConflictoAdmin(
                CODIGO_AUTO_DESACTIVACION, "un administrador no puede desactivarse a sí mismo"
            )
        actualizado = self._usuarios.cambiar_activo(
            tenant_id=actor.tenant_id, usuario_id=usuario_id, activo=activo
        )
        self._auditar(
            actor,
            "USUARIO_ESTADO",
            "usuario",
            usuario_id,
            antes={"activo": actual.activo},
            despues={"activo": actualizado.activo},
        )
        return actualizado

    # ------------------------------------------------------------------
    # Exportación
    # ------------------------------------------------------------------

    def exportar(self, actor: Actor, *, formato: str) -> tuple[str, str]:
        self._exigir_admin(actor)
        formato_limpio = formato.strip().lower()
        if formato_limpio not in ("json", "csv"):
            raise Invalido("formato de exportación inválido")
        datos = self._exportacion.exportar(tenant_id=actor.tenant_id)
        datos = self._sanear(datos)
        if formato_limpio == "json":
            contenido = json.dumps(
                {
                    "tenant_id": actor.tenant_id,
                    "secciones": {seccion: len(filas) for seccion, filas in datos.items()},
                    "datos": datos,
                },
                ensure_ascii=False,
                default=str,
                indent=2,
            )
            media_type = "application/json"
        else:
            contenido = self._csv(datos)
            media_type = "text/csv"
        self._auditar(
            actor,
            "EXPORTACION_GENERADA",
            "exportacion",
            actor.tenant_id,
            despues={
                "formato": formato_limpio,
                "secciones": {seccion: len(filas) for seccion, filas in datos.items()},
            },
        )
        return media_type, contenido

    def _csv(self, datos: dict[str, list[dict[str, object]]]) -> str:
        buffer = io.StringIO()
        writer = csv.writer(buffer, lineterminator="\n")
        writer.writerow(("seccion", "id", "json"))
        for seccion, filas in datos.items():
            for fila in filas:
                writer.writerow(
                    (
                        seccion,
                        fila.get("id", ""),
                        json.dumps(fila, ensure_ascii=False, default=str),
                    )
                )
        return buffer.getvalue()

    @staticmethod
    def _sanear(
        datos: dict[str, list[dict[str, object]]]
    ) -> dict[str, list[dict[str, object]]]:
        prohibidas = {
            "password_hash",
            "oauth_ref",
            "two_factor_secret",
            "dni_cifrado",
            "raw_json",
            "token_hash",
        }
        return {
            seccion: [
                {clave: valor for clave, valor in fila.items() if clave not in prohibidas}
                for fila in filas
            ]
            for seccion, filas in datos.items()
        }

    # ------------------------------------------------------------------
    # KPIs
    # ------------------------------------------------------------------

    def kpis(self, actor: Actor, *, desde: date, hasta: date) -> Kpis:
        self._exigir_kpis(actor)
        if desde > hasta:
            raise Invalido("el período es inválido: desde es posterior a hasta")
        datos = self._reportes.datos(
            tenant_id=actor.tenant_id, desde=desde, hasta=hasta
        )
        return Kpis(
            desde=desde,
            hasta=hasta,
            total_turnos=datos.total_turnos,
            turnos_por_estado=dict(datos.por_estado),
            ausentismo_pct=self._pct(
                datos.por_estado.get("AUSENTE", 0),
                datos.por_estado.get("PRESENTE", 0) + datos.por_estado.get("AUSENTE", 0),
            ),
            reservas_online_pct=self._pct(datos.online, datos.total_turnos),
            facturacion_por_profesional=datos.facturacion_por_profesional,
            reasignados_2h=datos.reasignados_2h,
            ocupacion_pct=self._pct(datos.minutos_ocupados, datos.minutos_disponibles),
        )

    # ------------------------------------------------------------------
    # Internos
    # ------------------------------------------------------------------

    @staticmethod
    def _pct(numerador: int, denominador: int) -> float:
        if denominador <= 0:
            return 0.0
        return round(numerador * 100 / denominador, 2)

    @staticmethod
    def _validar(clave: str, valor: object) -> object:
        if clave not in _CLAVES:
            raise Invalido(f"clave de configuración desconocida: {clave}")
        if clave == "anticipacion_cancelacion_h":
            if isinstance(valor, bool) or not isinstance(valor, int) or not 0 <= valor <= 168:
                raise Invalido("anticipacion_cancelacion_h debe ser un entero entre 0 y 168")
            return valor
        if clave == "sena_modo":
            if valor is not None and valor not in ("SIN_SENA", "PORCENTAJE", "MONTO_FIJO"):
                raise Invalido("sena_modo inválido")
            return valor
        if clave == "sena_valor":
            if valor is not None and (
                isinstance(valor, bool) or not isinstance(valor, int) or valor < 0
            ):
                raise Invalido("sena_valor debe ser un entero no negativo o null")
            return valor
        if not isinstance(valor, bool):
            raise Invalido("recordatorios_habilitados debe ser booleano")
        return valor

    @staticmethod
    def _validar_email(email: str) -> str:
        limpio = email.strip().lower()
        if limpio.count("@") != 1 or "." not in limpio.split("@", 1)[1]:
            raise Invalido("email inválido")
        return limpio

    @staticmethod
    def _exigir_admin(actor: Actor) -> None:
        if actor.rol == "PACIENTE":
            raise NoAutenticado("sesión interna requerida")
        if actor.rol not in _ADMIN:
            raise Prohibido("sólo un administrador accede a esta sección")

    @staticmethod
    def _exigir_kpis(actor: Actor) -> None:
        if actor.rol == "PACIENTE":
            raise NoAutenticado("sesión interna requerida")
        if actor.rol not in _KPIS:
            raise Prohibido("rol sin permiso para ver reportes")

    def _auditar(
        self,
        actor: Actor,
        accion: str,
        entidad: str,
        entidad_id: str,
        *,
        antes: dict[str, object] | None = None,
        despues: dict[str, object] | None = None,
    ) -> None:
        self._auditoria.registrar(
            tenant_id=actor.tenant_id,
            accion=accion,
            actor=actor.user_id,
            entidad=entidad,
            entidad_id=entidad_id,
            antes=antes,
            despues=despues,
        )
