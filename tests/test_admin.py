"""Tests de dominio de C-15 con adaptadores en memoria (sin DB)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime

import pytest

from app.admin.puertos import (
    CODIGO_AUTO_DESACTIVACION,
    CODIGO_USUARIO_DUPLICADO,
    AuditoriaMemoria,
    ConfigMemoria,
    ConflictoAdmin,
    DatosReporte,
    ExportacionMemoria,
    ReportesMemoria,
    UsuarioAdmin,
    UsuariosMemoria,
)
from app.admin.servicio import ServicioAdmin
from app.turnos.servicio import Actor, Invalido, NoAutenticado, Prohibido

UTC = UTC
AHORA = datetime(2026, 11, 15, 9, 0, tzinfo=UTC)
T1 = "a0000000-0000-4000-8000-000000000001"
T2 = "a0000000-0000-4000-8000-000000000002"
ADMIN_ID = "usuario-admin"
RECEP_ID = "usuario-recep"


def actor(rol: str = "ADMIN", tenant: str = T1, user_id: str = ADMIN_ID) -> Actor:
    return Actor(tenant_id=tenant, rol=rol, user_id=user_id)


@dataclass
class Harness:
    svc: ServicioAdmin
    config: ConfigMemoria
    usuarios: UsuariosMemoria
    exportacion: ExportacionMemoria
    reportes: ReportesMemoria
    auditoria: AuditoriaMemoria


def nuevo_harness() -> Harness:
    config = ConfigMemoria(
        {
            T1: {
                "anticipacion_cancelacion_h": 24,
                "sena_modo": "PORCENTAJE",
                "sena_valor": 30,
            },
            T2: {"anticipacion_cancelacion_h": 48},
        }
    )
    usuarios = UsuariosMemoria(
        [
            UsuarioAdmin(ADMIN_ID, T1, "Admin Demo", "admin@demo.test", "ADMIN", True, AHORA),
            UsuarioAdmin(RECEP_ID, T1, "Recep Demo", "recep@demo.test", "RECEPCION", True, AHORA),
            UsuarioAdmin("usuario-otro", T2, "Admin Otro", "admin@otro.test", "ADMIN", True, AHORA),
        ]
    )
    exportacion = ExportacionMemoria(
        {
            T1: {
                "pacientes": [
                    {
                        "id": "paciente-1",
                        "nombre": "Paciente Demo",
                        "password_hash": "no-debe-salir",
                        "oauth_ref": "no-debe-salir",
                    }
                ],
                "turnos": [{"id": "turno-1", "estado": "PRESENTE"}],
            },
            T2: {"pacientes": [{"id": "paciente-ajeno"}]},
        }
    )
    reportes = ReportesMemoria(
        {
            T1: DatosReporte(
                total_turnos=4,
                por_estado={"PRESENTE": 2, "AUSENTE": 1, "PENDIENTE": 1},
                online=1,
                facturacion_por_profesional=(("profesional-1", 12000),),
                reasignados_2h=1,
                minutos_ocupados=540,
                minutos_disponibles=1440,
            )
        }
    )
    auditoria = AuditoriaMemoria()
    svc = ServicioAdmin(
        config, usuarios, exportacion, reportes, auditoria, reloj=lambda: AHORA
    )
    return Harness(svc, config, usuarios, exportacion, reportes, auditoria)


# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------


def test_obtener_config() -> None:
    h = nuevo_harness()

    config = h.svc.obtener_config(actor())

    assert config["anticipacion_cancelacion_h"] == 24
    assert config["sena_modo"] == "PORCENTAJE"


def test_actualizar_config_parcial_y_audita() -> None:
    h = nuevo_harness()

    actualizada = h.svc.actualizar_config(
        actor(), valores={"anticipacion_cancelacion_h": 48, "recordatorios_habilitados": True}
    )

    assert actualizada["anticipacion_cancelacion_h"] == 48
    assert actualizada["recordatorios_habilitados"] is True
    assert actualizada["sena_modo"] == "PORCENTAJE"
    entrada = h.auditoria.entradas[-1]
    assert entrada["accion"] == "CONFIG_ACTUALIZADA"
    assert entrada["antes"] == {
        "anticipacion_cancelacion_h": 24,
        "sena_modo": "PORCENTAJE",
        "sena_valor": 30,
    }


@pytest.mark.parametrize(
    ("clave", "valor"),
    [
        ("descuento_secreto", 10),
        ("anticipacion_cancelacion_h", 500),
        ("anticipacion_cancelacion_h", "24"),
        ("sena_modo", "MITAD"),
        ("sena_valor", -1),
        ("recordatorios_habilitados", "si"),
    ],
)
def test_config_invalida_no_persiste(clave: str, valor: object) -> None:
    h = nuevo_harness()

    with pytest.raises(Invalido):
        h.svc.actualizar_config(actor(), valores={clave: valor})

    assert h.config.obtener(tenant_id=T1) == {
        "anticipacion_cancelacion_h": 24,
        "sena_modo": "PORCENTAJE",
        "sena_valor": 30,
    }
    assert [e["accion"] for e in h.auditoria.entradas] == []


def test_config_aislada_por_tenant() -> None:
    h = nuevo_harness()

    assert h.svc.obtener_config(actor(tenant=T2)) == {"anticipacion_cancelacion_h": 48}


# ---------------------------------------------------------------------------
# Usuarios
# ---------------------------------------------------------------------------


def test_listar_usuarios_del_tenant() -> None:
    h = nuevo_harness()

    usuarios = h.svc.listar_usuarios(actor())

    assert [u.email for u in usuarios] == ["admin@demo.test", "recep@demo.test"]
    assert all(u.tenant_id == T1 for u in usuarios)


def test_crear_usuario_normaliza_email_y_audita() -> None:
    h = nuevo_harness()

    usuario = h.svc.crear_usuario(
        actor(),
        nombre="Nuevo Odontólogo",
        email="  Odonto@Demo.Test ",
        password="secreto-123",
        rol="ODONTOLOGO",
    )

    assert usuario.email == "odonto@demo.test"
    assert usuario.activo is True
    assert h.auditoria.entradas[-1]["accion"] == "USUARIO_CREADO"


def test_usuario_duplicado() -> None:
    h = nuevo_harness()

    with pytest.raises(ConflictoAdmin) as excinfo:
        h.svc.crear_usuario(
            actor(),
            nombre="Otro",
            email="admin@demo.test",
            password="secreto-123",
            rol="ADMIN",
        )

    assert excinfo.value.codigo_dominio == CODIGO_USUARIO_DUPLICADO


@pytest.mark.parametrize(
    ("email", "password", "rol"),
    [
        ("sin-arroba", "secreto-123", "ADMIN"),
        ("ok@demo.test", "corta", "ADMIN"),
        ("ok@demo.test", "secreto-123", "SUPERADMIN"),
    ],
)
def test_usuario_invalido(email: str, password: str, rol: str) -> None:
    h = nuevo_harness()

    with pytest.raises(Invalido):
        h.svc.crear_usuario(
            actor(), nombre="X", email=email, password=password, rol=rol
        )


def test_admin_no_puede_desactivarse() -> None:
    h = nuevo_harness()

    with pytest.raises(ConflictoAdmin) as excinfo:
        h.svc.cambiar_estado_usuario(actor(), usuario_id=ADMIN_ID, activo=False)

    assert excinfo.value.codigo_dominio == CODIGO_AUTO_DESACTIVACION
    assert h.usuarios.obtener(tenant_id=T1, usuario_id=ADMIN_ID).activo is True


def test_desactivar_a_otro_usuario() -> None:
    h = nuevo_harness()

    usuario = h.svc.cambiar_estado_usuario(actor(), usuario_id=RECEP_ID, activo=False)

    assert usuario.activo is False
    assert h.auditoria.entradas[-1]["accion"] == "USUARIO_ESTADO"


# ---------------------------------------------------------------------------
# Exportación
# ---------------------------------------------------------------------------


def test_exportar_json_sin_secretos() -> None:
    h = nuevo_harness()

    media, contenido = h.svc.exportar(actor(), formato="json")

    assert media == "application/json"
    assert "paciente-1" in contenido
    assert "no-debe-salir" not in contenido
    assert "password_hash" not in contenido
    assert "oauth_ref" not in contenido


def test_exportar_csv() -> None:
    h = nuevo_harness()

    media, contenido = h.svc.exportar(actor(), formato="csv")

    assert media == "text/csv"
    lineas = contenido.strip().splitlines()
    assert lineas[0] == "seccion,id,json"
    assert any(linea.startswith("pacientes,paciente-1,") for linea in lineas)
    assert any(linea.startswith("turnos,turno-1,") for linea in lineas)


def test_exportar_formato_invalido() -> None:
    h = nuevo_harness()

    with pytest.raises(Invalido):
        h.svc.exportar(actor(), formato="xml")


def test_exportar_solo_del_tenant() -> None:
    h = nuevo_harness()
    _, contenido = h.svc.exportar(actor(), formato="json")

    assert "paciente-ajeno" not in contenido


# ---------------------------------------------------------------------------
# KPIs
# ---------------------------------------------------------------------------


def test_kpis_calculados() -> None:
    h = nuevo_harness()

    kpis = h.svc.kpis(actor(), desde=date(2026, 11, 1), hasta=date(2026, 12, 1))

    assert kpis.total_turnos == 4
    assert kpis.turnos_por_estado == {"PRESENTE": 2, "AUSENTE": 1, "PENDIENTE": 1}
    assert kpis.ausentismo_pct == 33.33
    assert kpis.reservas_online_pct == 25.0
    assert kpis.facturacion_por_profesional == (("profesional-1", 12000),)
    assert kpis.reasignados_2h == 1
    assert kpis.ocupacion_pct == 37.5


def test_kpis_sin_turnos_no_divide_por_cero() -> None:
    h = nuevo_harness()
    h.reportes._items[T1] = DatosReporte(0, {}, 0, (), 0)

    kpis = h.svc.kpis(actor(), desde=date(2026, 11, 1), hasta=date(2026, 12, 1))

    assert kpis.ausentismo_pct == 0.0
    assert kpis.reservas_online_pct == 0.0


def test_kpis_periodo_invalido() -> None:
    h = nuevo_harness()

    with pytest.raises(Invalido):
        h.svc.kpis(actor(), desde=date(2026, 12, 1), hasta=date(2026, 11, 1))


# ---------------------------------------------------------------------------
# RBAC
# ---------------------------------------------------------------------------


def test_recepcion_no_administra_pero_ve_kpis() -> None:
    h = nuevo_harness()

    with pytest.raises(Prohibido):
        h.svc.obtener_config(actor("RECEPCION"))
    with pytest.raises(Prohibido):
        h.svc.exportar(actor("RECEPCION"), formato="json")

    assert h.svc.kpis(
        actor("RECEPCION"), desde=date(2026, 11, 1), hasta=date(2026, 12, 1)
    ).total_turnos == 4


def test_odontologo_y_paciente_sin_acceso() -> None:
    h = nuevo_harness()

    with pytest.raises(Prohibido):
        h.svc.obtener_config(actor("ODONTOLOGO"))
    with pytest.raises(NoAutenticado):
        h.svc.obtener_config(actor("PACIENTE"))
    with pytest.raises(NoAutenticado):
        h.svc.kpis(actor("PACIENTE"), desde=date(2026, 11, 1), hasta=date(2026, 12, 1))
