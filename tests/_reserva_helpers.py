"""Helpers compartidos por los tests de C-06 (no recolectados por pytest).

Construye un `ServicioReservasPublicas` completamente cableado con adaptadores en
memoria y un reloj congelado mutable, y expone los adaptadores para sembrar datos
y aseverar auditoría/contadores/tokens. Todo dato es ficticio (R1).
"""
from __future__ import annotations

from datetime import datetime, time

from conftest import P1, P2, S1, S2, T1, T2, dt
from fastapi.testclient import TestClient

from app.reservas.antispam import ContadorMemoria, VerificadorMemoria
from app.reservas.puertos import (
    AuditoriaMemoria,
    CatalogoMemoria,
    HorarioSemanal,
    NotificadorNulo,
    PacienteMemoria,
    Prestacion,
    Profesional,
    Sillon,
    TenantMemoria,
)
from app.reservas.servicio import ServicioReservasPublicas
from app.reservas.tokens import TokenRepositorioEnMemoria
from app.routers.reservas_publicas import crear_app_publica
from app.turnos.servicio import ServicioTurnos

T3 = "a0000000-0000-4000-8000-000000000003"

PREST30 = "PREST-30"
PREST45 = "PREST-45"


class Harness:
    """Servicio público + TestClient con adaptadores en memoria expuestos."""

    def __init__(
        self,
        *,
        rate_limit_max: int = 1000,
        rate_limit_ventana_s: int = 60,
        horizonte_dias: int = 7,
        ttl_min: int = 10,
        canal: str = "captcha",
        anticipacion_min_horas: float = 24.0,
        reloj_inicial: datetime | None = None,
        catalogo: CatalogoMemoria | None = None,
        pacientes: PacienteMemoria | None = None,
        tenants: TenantMemoria | None = None,
    ) -> None:
        self.turnos = ServicioTurnos(anticipacion_min_horas=anticipacion_min_horas)
        self.catalogo = catalogo or CatalogoMemoria()
        self.pacientes = pacientes or PacienteMemoria()
        self.tenants = tenants or TenantMemoria({"t1": (T1, True), "t2": (T2, True), "t3": (T3, False)})
        self.tokens = TokenRepositorioEnMemoria()
        self.contador = ContadorMemoria()
        self.verificador = VerificadorMemoria(ttl_min=ttl_min, canal=canal)
        self.auditoria = AuditoriaMemoria()
        self._reloj = {"ahora": reloj_inicial or dt("2026-10-05", 9)}

        self.svc = ServicioReservasPublicas(
            self.turnos,
            self.catalogo,
            self.pacientes,
            self.tenants,
            self.tokens,
            self.contador,
            self.verificador,
            self.auditoria,
            NotificadorNulo(),
            rate_limit_max=rate_limit_max,
            rate_limit_ventana_s=rate_limit_ventana_s,
            horizonte_dias=horizonte_dias,
            reloj=lambda: self._reloj["ahora"],
        )
        self.client = TestClient(crear_app_publica(self.svc))

    @property
    def ahora_actual(self) -> datetime:
        return self._reloj["ahora"]

    def fijar_ahora(self, dia: str, hora: int = 9, minuto: int = 0) -> datetime:
        self._reloj["ahora"] = dt(dia, hora, minuto)
        return self._reloj["ahora"]


def catalogo_estandar(
    harness: Harness,
    *,
    tenant: str = T1,
    dias: tuple[int, ...] = (1, 2, 3, 4, 5, 6, 7),
    profesionales: tuple[str, ...] = (P1, P2),
    sillones: tuple[str, ...] = (S1, S2),
) -> None:
    """Siembra PREST30/PREST45, profesionales, sillones y horarios 09–12 / 08–18."""
    c = harness.catalogo
    c.agregar_prestacion(Prestacion(id=PREST30, tenant_id=tenant, duracion_min=30))
    c.agregar_prestacion(Prestacion(id=PREST45, tenant_id=tenant, duracion_min=45))
    for p in profesionales:
        c.agregar_profesional(Profesional(id=p, tenant_id=tenant))
    for s in sillones:
        c.agregar_sillon(Sillon(id=s, tenant_id=tenant))
    for dia in dias:
        for p in profesionales:
            c.agregar_horario(
                HorarioSemanal(
                    tenant_id=tenant, dia=dia, desde=time(9, 0), hasta=time(12, 0), profesional_id=p
                )
            )
        c.agregar_horario(
            HorarioSemanal(tenant_id=tenant, dia=dia, desde=time(8, 0), hasta=time(18, 0), profesional_id=None)
        )
    for p in profesionales:
        c.agregar_habilitado(tenant, p, PREST30)
        c.agregar_habilitado(tenant, p, PREST45)


def reserva_payload(**overrides):
    base = {
        "prestacion": PREST30,
        "profesional": P1,
        "inicio": "2026-10-06T10:00:00+00:00",
        "nombre": "Paciente Demo",
        "telefono": "+5491130551234",
    }
    base.update(overrides)
    return base


def emitir(h: Harness, accion: str = "reservar", tenant: str = "t1") -> str:
    """Emite una verificación por HTTP y devuelve el `verificacion_id`."""
    r = h.client.post(f"/api/publico/{tenant}/verificacion", json={"accion": accion})
    assert r.status_code == 201, r.text
    return r.json()["verificacion_id"]


def reservar(h: Harness, tenant: str = "t1", **overrides):
    """Emite verificación y POSTea una reserva; devuelve el `Response`."""
    vid = emitir(h, tenant=tenant)
    payload = reserva_payload(**overrides)
    payload["verificacion_id"] = vid
    return h.client.post(f"/api/publico/{tenant}/reservas", json=payload)
