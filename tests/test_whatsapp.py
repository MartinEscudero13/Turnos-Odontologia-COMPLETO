"""Tests de dominio de C-13 con adaptadores en memoria (sin red ni DB)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

import pytest

from app.admin.puertos import ConfigMemoria as ConfigAdminMemoria
from app.lista_espera.puertos import HuecoLiberadoMemoria
from app.reservas.puertos import Paciente, PacienteMemoria
from app.turnos.servicio import Actor, NoAutenticado, NoEncontrado, Prohibido
from app.whatsapp.adaptadores import ConfigWhatsAppAdmin
from app.whatsapp.puertos import (
    AuditoriaMemoria,
    ConfigWhatsAppMemoria,
    EmailFake,
    MensajeMemoria,
    PasarelaWhatsAppFake,
    TurnosWhatsAppMemoria,
)
from app.whatsapp.servicio import ServicioWhatsApp

T1 = "a0000000-0000-4000-8000-000000000001"
T2 = "a0000000-0000-4000-8000-000000000002"
P1 = "e1000000-0000-4000-8000-000000000001"
P2 = "e1000000-0000-4000-8000-000000000002"
AHORA = datetime(2026, 11, 16, 9, 0, tzinfo=UTC)
INICIO = AHORA + timedelta(hours=2)


def actor(rol: str = "ADMIN", tenant: str = T1, user_id: str = "usuario-1") -> Actor:
    return Actor(tenant_id=tenant, rol=rol, user_id=user_id)


@dataclass
class Harness:
    svc: ServicioWhatsApp
    mensajes: MensajeMemoria
    pasarela: PasarelaWhatsAppFake
    email: EmailFake
    turnos: object
    hueco: HuecoLiberadoMemoria
    auditoria: AuditoriaMemoria

    def crear_turno(self, *, paciente_id: str = P1, inicio: datetime = INICIO) -> str:
        turno = self.turnos.crear(  # type: ignore[attr-defined]
            actor("RECEPCION"),
            profesional_id="prof-1",
            sillon_id="sillon-1",
            paciente_id=paciente_id,
            prestacion_id="Consulta",
            inicio=inicio,
            duracion_min=30,
        )
        return str(turno.id)


def nuevo_harness(*, pacientes: list[Paciente] | None = None) -> Harness:
    from app.turnos.servicio import ServicioTurnos

    turnos = ServicioTurnos(anticipacion_min_horas=0.0)
    base = pacientes or [
        Paciente(id=P1, tenant_id=T1, nombre="Paciente Demo", telefono="+5491130551001"),
        Paciente(id=P2, tenant_id=T1, nombre="Sin Teléfono", telefono=""),
    ]
    pacientes_port = PacienteMemoria(base)
    hueco = HuecoLiberadoMemoria()
    mensajes = MensajeMemoria()
    pasarela = PasarelaWhatsAppFake()
    email = EmailFake()
    auditoria = AuditoriaMemoria()
    svc = ServicioWhatsApp(
        mensajes,
        TurnosWhatsAppMemoria(turnos, pacientes_port, hueco),
        pasarela,
        email,
        ConfigWhatsAppMemoria(
            {T1: {"recordatorios_habilitados": True, "anticipacion_h": 24}}
        ),
        auditoria,
        url_confirmacion="https://demo.local/confirmar",
        reloj=lambda: AHORA,
    )
    return Harness(svc, mensajes, pasarela, email, turnos, hueco, auditoria)


# ---------------------------------------------------------------------------
# Recordatorios
# ---------------------------------------------------------------------------


def test_programa_recordatorio_idempotente() -> None:
    h = nuevo_harness()
    turno_id = h.crear_turno()

    primero = h.svc.programar_recordatorios(actor())
    segundo = h.svc.programar_recordatorios(actor())

    assert primero.enviados == 1
    assert segundo.enviados == 0
    mensajes = h.svc.listar_mensajes(actor())
    assert len([m for m in mensajes if m.plantilla == "RECORDATORIO"]) == 1
    assert mensajes[0].estado == "ENVIADO"
    assert mensajes[0].provider_message_id == "SM0001"
    assert h.pasarela.enviados[0]["turno_id"] == turno_id


def test_paciente_sin_telefono_se_saltea() -> None:
    h = nuevo_harness()
    h.crear_turno(paciente_id=P2)

    resultado = h.svc.programar_recordatorios(actor())

    assert resultado.enviados == 0
    assert h.pasarela.enviados == []


def test_fallo_wa_hace_fallback_email() -> None:
    h = nuevo_harness()
    h.crear_turno()
    h.pasarela.fallar = True

    resultado = h.svc.programar_recordatorios(actor())

    assert resultado.fallidos == 1
    mensajes = h.svc.listar_mensajes(actor())
    wa = [m for m in mensajes if m.canal == "WA"][0]
    email = [m for m in mensajes if m.canal == "EMAIL"][0]
    assert wa.estado == "FALLIDO"
    assert email.estado == "ENVIADO"
    assert len(h.email.enviados) == 1


def test_reintento_exitoso() -> None:
    h = nuevo_harness()
    h.crear_turno()
    h.pasarela.fallar = True
    h.svc.programar_recordatorios(actor())
    h.pasarela.fallar = False

    resultado = h.svc.procesar_pendientes(actor())

    assert resultado.enviados == 1
    wa = [m for m in h.svc.listar_mensajes(actor()) if m.canal == "WA"][0]
    assert wa.estado == "ENVIADO"


def test_reintentos_agotados_no_duplican() -> None:
    h = nuevo_harness()
    h.crear_turno()
    h.pasarela.fallar = True
    h.svc.programar_recordatorios(actor())
    for _ in range(3):
        h.svc.procesar_pendientes(actor())

    pendientes = h.mensajes.pendientes(tenant_id=T1)
    assert pendientes == []


# ---------------------------------------------------------------------------
# Webhook
# ---------------------------------------------------------------------------


def _mensaje_enviado(h: Harness) -> str:
    h.crear_turno()
    resultado = h.svc.programar_recordatorios(actor())
    assert resultado.mensajes
    provider_id = resultado.mensajes[0].provider_message_id
    assert provider_id is not None
    return provider_id


def test_webhook_estado_entregado() -> None:
    h = nuevo_harness()
    provider_id = _mensaje_enviado(h)

    resultado = h.svc.recibir_webhook(
        {"MessageSid": provider_id, "MessageStatus": "delivered"}
    )

    assert resultado.estado == "ENTREGADO"
    assert h.svc.listar_mensajes(actor())[0].estado == "ENTREGADO"


def test_webhook_si_confirma_turno() -> None:
    h = nuevo_harness()
    provider_id = _mensaje_enviado(h)

    resultado = h.svc.recibir_webhook({"MessageSid": provider_id, "Body": "Sí"})

    assert resultado.respuesta == "SI"
    assert h.turnos.obtener(actor(), resultado.turno_id).estado == "CONFIRMADO"  # type: ignore[attr-defined]


def test_webhook_no_cancela_y_libera_hueco() -> None:
    h = nuevo_harness()
    provider_id = _mensaje_enviado(h)

    resultado = h.svc.recibir_webhook({"MessageSid": provider_id, "Body": "NO"})

    assert resultado.respuesta == "NO"
    assert h.turnos.obtener(actor(), resultado.turno_id).estado == "CANCELADO"  # type: ignore[attr-defined]
    assert h.hueco.eventos and h.hueco.eventos[0][1] == resultado.turno_id


def test_webhook_ambiguo_devuelve_link() -> None:
    h = nuevo_harness()
    provider_id = _mensaje_enviado(h)

    resultado = h.svc.recibir_webhook({"MessageSid": provider_id, "Body": "hola?"})

    assert resultado.respuesta == "AMBIGUA"
    assert resultado.link_confirmacion is not None


def test_webhook_mensaje_inexistente() -> None:
    h = nuevo_harness()

    with pytest.raises(NoEncontrado):
        h.svc.recibir_webhook({"MessageSid": "SM-inexistente"})


def test_webhook_resuelve_respuesta_por_telefono() -> None:
    h = nuevo_harness()
    _mensaje_enviado(h)

    # Meta no siempre manda el id del mensaje citado: se resuelve por el teléfono.
    resultado = h.svc.recibir_webhook(
        {"MessageSid": "wamid.inbound", "Body": "SI", "From": "+5491130551001"},
        tenant_id=T1,
        origen="meta",
    )

    assert resultado.respuesta == "SI"
    assert resultado.turno_id is not None
    assert h.turnos.obtener(actor(), resultado.turno_id).estado == "CONFIRMADO"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Recall y RBAC
# ---------------------------------------------------------------------------


def test_recall_clinico() -> None:
    h = nuevo_harness()

    mensaje = h.svc.crear_recall(
        actor("ODONTOLOGO"),
        paciente_id=P1,
        motivo="Control post-tratamiento",
        fecha_objetivo=date(2027, 1, 15),
    )

    assert mensaje.plantilla == "RECALL"
    assert mensaje.estado == "ENVIADO"
    assert "Control post-tratamiento" in mensaje.cuerpo


def test_recall_rechaza_recepcion() -> None:
    h = nuevo_harness()

    with pytest.raises(Prohibido):
        h.svc.crear_recall(
            actor("RECEPCION"),
            paciente_id=P1,
            motivo="Control",
            fecha_objetivo=date(2027, 1, 15),
        )


def test_rbac_recordatorios() -> None:
    h = nuevo_harness()

    with pytest.raises(Prohibido):
        h.svc.programar_recordatorios(actor("ODONTOLOGO"))
    with pytest.raises(NoAutenticado):
        h.svc.listar_mensajes(actor("PACIENTE"))


def test_config_de_admin_gobierna_whatsapp() -> None:
    config = ConfigAdminMemoria({T1: {"recordatorios_habilitados": False}})
    adapter = ConfigWhatsAppAdmin(config)

    assert adapter.habilitado(tenant_id=T1) is False

    config.actualizar(
        tenant_id=T1,
        valores={"recordatorios_habilitados": True, "recordatorio_anticipacion_h": 48},
        ahora=datetime.now(UTC),
    )

    assert adapter.habilitado(tenant_id=T1) is True
    assert adapter.anticipacion_h(tenant_id=T1) == 48
