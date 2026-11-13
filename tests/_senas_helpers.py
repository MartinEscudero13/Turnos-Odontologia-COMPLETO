"""Harness de señas cableado en memoria — C-11 §4–§5 (no recolectado por pytest).

Todo dato es ficticio (RN-GL-03): tenant T1/T2, prestación `PREST-1` de
`precio_base=10000`, `PORCENTAJE=30` ⇒ `3000`, reloj inyectado en `-03:00`.
Ningún camino abre sockets: la pasarela es `AdaptadorPasarelaFake`.

Dos harness:

- `HarnessSenas`: dominio de señas + app pública (token y preferencia), sin C-06.
- `HarnessReservaConSena`: C-06 real (`ServicioReservasPublicas`) con el enganche
  de C-11, compartiendo reloj y resolución de tenant entre ambos servicios.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

from _reserva_helpers import Harness as HarnessReserva
from _reserva_helpers import catalogo_estandar
from conftest import T1, T2
from fastapi.testclient import TestClient

from app.reservas.antispam import ContadorMemoria
from app.reservas.puertos import TenantMemoria
from app.routers.senas import crear_app_senas
from app.senas.puertos import (
    AdaptadorPasarelaFake,
    AuditoriaSenaMemoria,
    ConfiguracionSenaMemoria,
    PagoMPMemoria,
    SenaCreada,
    SenaMemoria,
)
from app.senas.servicio import ServicioSenas

TZ = timezone(timedelta(hours=-3))
AHORA = datetime(2026, 11, 13, 9, 0, tzinfo=TZ)

TUR1 = "turno-1"
TUR2 = "turno-2"
PREST1 = "PREST-1"
PREST30 = "PREST-30"

SLUGS: dict[str, tuple[str, bool]] = {"t1": (T1, True), "t2": (T2, True)}


def d3(dia: str = "2026-11-20", hora: int = 10, minuto: int = 0) -> datetime:
    """Instante ficticio en `-03:00` (RN-GL-03)."""
    y, m, d = (int(x) for x in dia.split("-"))
    return datetime(y, m, d, hora, minuto, tzinfo=TZ)


class HarnessSenas:
    """Dominio de señas + borde público, sin la reserva pública de C-06."""

    def __init__(
        self,
        *,
        ahora: datetime | None = None,
        sena_ttl_h: int = 24,
        anticipacion_cancelacion_h: int = 24,
        rate_limit_max: int = 1000,
        rate_limit_ventana_s: int = 60,
        pasarela: AdaptadorPasarelaFake | None = None,
        senas: SenaMemoria | None = None,
    ) -> None:
        self.ahora = ahora or AHORA
        self.senas = senas or SenaMemoria(reloj=lambda: self.ahora)
        self.pagos = PagoMPMemoria(reloj=lambda: self.ahora)
        self.configuracion = ConfiguracionSenaMemoria()
        self.pasarela = pasarela or AdaptadorPasarelaFake()
        self.auditoria = AuditoriaSenaMemoria()
        self.contador = ContadorMemoria()
        self.tenants = TenantMemoria(dict(SLUGS))
        self.svc = ServicioSenas(
            self.senas,
            self.configuracion,
            self.pasarela,
            self.auditoria,
            tenants=self.tenants,
            contador=self.contador,
            sena_ttl_h=sena_ttl_h,
            anticipacion_cancelacion_h=anticipacion_cancelacion_h,
            rate_limit_max=rate_limit_max,
            rate_limit_ventana_s=rate_limit_ventana_s,
            url_pago_base="https://app.test/pagar",
            url_webhook="https://app.test/api/webhooks/mercadopago",
            reloj=lambda: self.ahora,
        )
        self.client = TestClient(crear_app_senas(self.svc))

    # -- siembra ---------------------------------------------------------

    def configurar(
        self,
        *,
        tenant_id: str = T1,
        prestacion_id: str = PREST1,
        precio_base_centavos: int = 10000,
        modo: str = "PORCENTAJE",
        valor: int | None = 30,
        sena_modo: str | None = None,
        sena_valor: int | None = None,
    ) -> None:
        """Configura la regla del tenant y la prestación (sin override por default)."""
        self.configuracion.configurar(tenant_id=tenant_id, modo=modo, valor=valor)
        self.configuracion.agregar_prestacion(
            tenant_id=tenant_id,
            prestacion_id=prestacion_id,
            precio_base_centavos=precio_base_centavos,
            sena_modo=sena_modo,
            sena_valor=sena_valor,
        )

    # -- casos de uso ----------------------------------------------------

    def crear(
        self,
        *,
        tenant_id: str = T1,
        turno_id: str = TUR1,
        prestacion_id: str = PREST1,
        inicio: datetime | None = None,
        fin: datetime | None = None,
        ahora: datetime | None = None,
    ) -> SenaCreada:
        momento = ahora if ahora is not None else self.ahora
        inicio = inicio or d3()
        return self.svc.crear_si_corresponde(
            tenant_id=tenant_id,
            turno_id=turno_id,
            prestacion_id=prestacion_id,
            turno_inicio=inicio,
            turno_fin=fin or inicio + timedelta(minutes=30),
            ahora=momento,
        )

    def fijar_ahora(self, momento: datetime) -> datetime:
        self.ahora = momento
        return self.ahora


class HarnessReservaConSena:
    """C-06 real con el enganche de C-11 y reloj/tenant compartidos."""

    def __init__(
        self,
        *,
        reloj_inicial: datetime | None = None,
        rate_limit_max: int = 1000,
        rate_limit_ventana_s: int = 60,
        anticipacion_min_horas: float = 24.0,
        sena_ttl_h: int = 24,
        anticipacion_cancelacion_h: int = 24,
        pasarela: AdaptadorPasarelaFake | None = None,
    ) -> None:
        self.reloj: dict[str, datetime] = {
            "ahora": reloj_inicial or datetime(2026, 10, 5, 9, 0, tzinfo=UTC)
        }
        self.tenants = TenantMemoria(dict(SLUGS))
        self.senas = SenaMemoria(reloj=lambda: self.reloj["ahora"])
        self.pagos = PagoMPMemoria(reloj=lambda: self.reloj["ahora"])
        self.configuracion = ConfiguracionSenaMemoria()
        self.pasarela = pasarela or AdaptadorPasarelaFake()
        self.auditoria_senas = AuditoriaSenaMemoria()
        self.contador_senas = ContadorMemoria()
        self.svc_senas = ServicioSenas(
            self.senas,
            self.configuracion,
            self.pasarela,
            self.auditoria_senas,
            tenants=self.tenants,
            contador=self.contador_senas,
            sena_ttl_h=sena_ttl_h,
            anticipacion_cancelacion_h=anticipacion_cancelacion_h,
            rate_limit_max=1000,
            rate_limit_ventana_s=rate_limit_ventana_s,
            url_pago_base="https://app.test/pagar",
            url_webhook="https://app.test/api/webhooks/mercadopago",
            reloj=lambda: self.reloj["ahora"],
        )
        self.base = HarnessReserva(
            rate_limit_max=rate_limit_max,
            rate_limit_ventana_s=rate_limit_ventana_s,
            anticipacion_min_horas=anticipacion_min_horas,
            reloj=self.reloj,
            tenants=self.tenants,
            sena_port=self.svc_senas,
        )
        catalogo_estandar(self.base)
        self.configuracion.configurar(tenant_id=T1, modo="PORCENTAJE", valor=30)
        self.configuracion.agregar_prestacion(
            tenant_id=T1,
            prestacion_id=PREST30,
            precio_base_centavos=10000,
        )
        self.client = self.base.client
        self.client_senas = TestClient(crear_app_senas(self.svc_senas))
        self.turnos = self.base.turnos

    @property
    def ahora_actual(self) -> datetime:
        return self.reloj["ahora"]

    def fijar_ahora(self, dia: str, hora: int = 9, minuto: int = 0) -> datetime:
        self.reloj["ahora"] = self.base.fijar_ahora(dia, hora, minuto)
        return self.reloj["ahora"]
