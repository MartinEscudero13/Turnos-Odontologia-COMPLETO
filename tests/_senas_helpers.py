"""Harness de señas cableado en memoria — C-11 §4–§8 (no recolectado por pytest).

Todo dato es ficticio (RN-GL-03): tenant T1/T2, prestación `PREST-1` de
`precio_base=10000`, `PORCENTAJE=30` ⇒ `3000`, reloj inyectado en `-03:00`.
Ningún camino abre sockets: la pasarela es `AdaptadorPasarelaFake`.

Tres harness:

- `HarnessSenas`: dominio de señas + app pública (token y preferencia), sin C-06.
- `HarnessReservaConSena`: C-06 real (`ServicioReservasPublicas`) con el enganche
  de C-11, compartiendo reloj y resolución de tenant entre ambos servicios.
- `HarnessSenaCiclo`: webhook firmado (§6), expiración con auto-oferta (§7) y el
  runner del barrido (§7.9) sobre los mismos adaptadores en memoria. La
  atomicidad del release se emula con `UnidadDeTrabajoMemoria` (rollback por
  instantánea); la garantía real de los locks vive en los tests PG (§8).
"""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, timezone
from typing import Any

from _reserva_helpers import Harness as HarnessReserva
from _reserva_helpers import catalogo_estandar
from conftest import T1, T2
from fastapi.testclient import TestClient

from app.caja.puertos import (
    AjustePostCierreMemoria,
    AuditoriaMemoria,
    CierreMemoria,
    CobroPendienteMemoria,
    CuentaPorCobrarOSMemoria,
    MovimientoMemoria,
    TurnoMemoria,
    UsuarioMemoria,
)
from app.caja.puertos import (
    UnidadDeTrabajoMemoria as UowCajaMemoria,
)
from app.caja.servicio import ServicioCaja
from app.lista_espera.puertos import HuecoLiberadoMemoria
from app.reservas.antispam import ContadorMemoria
from app.reservas.puertos import TenantMemoria
from app.routers.caja import crear_app as crear_app_caja
from app.routers.senas import crear_app_senas
from app.routers.senas_internas import crear_app_senas_internas
from app.routers.webhooks_mp import crear_app_webhooks
from app.senas.adaptadores import AplicacionCajaServicio
from app.senas.aplicacion import ServicioSenasAplicacion
from app.senas.consulta import ServicioSenasConsulta
from app.senas.puertos import (
    AdaptadorPasarelaFake,
    AuditoriaSenaMemoria,
    ConfiguracionSenaMemoria,
    EstadoSena,
    PagoMP,
    PagoMPMemoria,
    PresupuestosMemoria,
    Sena,
    SenaCreada,
    SenaMemoria,
    TurnoMemoriaSena,
    UnidadDeTrabajoMemoria,
)
from app.senas.runner import RegistroJobs, RunnerSenas
from app.senas.servicio import ServicioSenas
from app.senas.webhook import ServicioSenasWebhook, firma_esperada, manifiesto
from app.senas.worker import ServicioSenasExpulsion
from app.turnos.servicio import Actor

TZ = timezone(timedelta(hours=-3))
AHORA = datetime(2026, 11, 13, 9, 0, tzinfo=TZ)

TUR1 = "turno-1"
TUR2 = "turno-2"
PREST1 = "PREST-1"
PREST30 = "PREST-30"
PACI1 = "paciente-1"
PACI9 = "paciente-9"
U1 = "usuario-1"
U2 = "usuario-2"
U3 = "usuario-3"

# Secreto **ficticio**: los tests nunca usan credenciales reales (regla dura).
SECRETO_WEBHOOK = "secreto-webhook-ficticio-c11"
REQUEST_ID = "req-ficticio-1"
TS_FIRMA = "1763035200"

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


def firmar(
    data_id: str,
    *,
    request_id: str = REQUEST_ID,
    ts: str = TS_FIRMA,
    secreto: str = SECRETO_WEBHOOK,
) -> str:
    """Header `x-signature` correcto para el manifiesto de MP (D7)."""
    firmado = firma_esperada(
        secreto=secreto,
        manifiesto_=manifiesto(data_id=data_id, request_id=request_id, ts=ts),
    )
    return f"ts={ts},v1={firmado}"


class HarnessSenaCiclo:
    """Webhook firmado, expiración con auto-oferta y runner sobre memoria.

    Comparte reloj con todos los adaptadores: ningún test duerme ni lee el reloj
    del sistema (D10). El `UnidadDeTrabajoMemoria` reproduce el "todo o nada" de
    la transacción por seña para poder probar el rollback de §7 (F-14).
    """

    def __init__(
        self,
        *,
        ahora: datetime | None = None,
        secreto: str | None = SECRETO_WEBHOOK,
        inicio: datetime | None = None,
        intervalo_s: int = 60,
    ) -> None:
        self.ahora = ahora or AHORA
        self.inicio = inicio or d3()
        self.senas = SenaMemoria(reloj=lambda: self.ahora)
        self.pagos = PagoMPMemoria(reloj=lambda: self.ahora)
        self.turnos = TurnoMemoriaSena()
        self.pasarela = AdaptadorPasarelaFake()
        self.auditoria = AuditoriaSenaMemoria()
        self.huecos = HuecoLiberadoMemoria()
        self._siguiente_token = 1
        self.webhook = ServicioSenasWebhook(
            self.senas,
            self.pagos,
            self.turnos,
            self.pasarela,
            self.auditoria,
            secreto=secreto,
            reloj=lambda: self.ahora,
            uow_factory=lambda: UnidadDeTrabajoMemoria(
                self.senas, self.pagos, self.turnos, self.auditoria
            ),
        )
        self.worker = ServicioSenasExpulsion(
            self.senas,
            self.turnos,
            self.huecos,
            self.auditoria,
            reloj=lambda: self.ahora,
            uow_factory=lambda: UnidadDeTrabajoMemoria(
                self.senas, self.turnos, self.auditoria
            ),
        )
        self.registro = RegistroJobs()
        self.runner = RunnerSenas(
            self.worker,
            lambda: [T1],
            intervalo_s=intervalo_s,
            registro=self.registro,
            reloj=lambda: self.ahora,
        )
        self.client = TestClient(crear_app_webhooks(self.webhook))

    # -- siembra ---------------------------------------------------------

    def sembrar_sena(
        self,
        *,
        tenant_id: str = T1,
        turno_id: str = TUR1,
        monto_centavos: int = 3000,
        estado: EstadoSena = "PENDIENTE",
        expira_at: datetime | None = None,
        turno_estado: str = "PENDIENTE",
        inicio: datetime | None = None,
        ahora: datetime | None = None,
        paciente_id: str | None = PACI1,
    ) -> Sena:
        """Crea el turno y la seña en el estado pedido (datos ficticios)."""
        momento = ahora or self.ahora
        comienzo = inicio or self.inicio
        self.turnos.agregar(
            tenant_id=tenant_id,
            turno_id=turno_id,
            inicio=comienzo,
            estado=turno_estado,
            paciente_id=paciente_id,
        )
        sena = self.senas.crear(
            tenant_id=tenant_id,
            turno_id=turno_id,
            monto_centavos=monto_centavos,
            regla_modo="PORCENTAJE",
            regla_valor=30,
            precio_base_centavos=10000,
            anticipacion_cancelacion_h=24,
            expira_at=expira_at or momento + timedelta(hours=24),
            token_hash=f"hash-ficticio-{self._siguiente_token}",
            ahora=momento,
            turno_inicio=comienzo,
            turno_fin=comienzo + timedelta(minutes=30),
            turno_prestacion=PREST1,
        )
        self._siguiente_token += 1
        return self._forzar(sena, estado, momento)

    def _forzar(self, sena: Sena, estado: EstadoSena, momento: datetime) -> Sena:
        if estado == "PENDIENTE":
            return sena
        campos: dict[str, Any] = {"acreditada_en": momento}
        if estado == "LIBERADA":
            campos = {"liberada_en": momento, "motivo_liberacion": "EXPIRACION"}
        elif estado == "DEVUELTA":
            campos = {
                "devuelta_en": momento,
                "motivo_devolucion": "POLITICA_CANCELACION",
                "devuelta_por": None,
            }
        elif estado == "APLICADA":
            campos = {
                "acreditada_en": momento,
                "aplicada_en": momento,
                "movimiento_caja_id": "movimiento-mp-1",
                "concepto_aplicacion": "TRATAMIENTO",
            }
        actual = self.senas.transicionar(
            tenant_id=sena.tenant_id,
            sena_id=sena.id,
            desde="PENDIENTE",
            hacia=estado,
            campos=campos,
        )
        assert actual is not None
        return actual

    # -- notificación ----------------------------------------------------

    def notificar(
        self,
        *,
        sena: Sena,
        mp_payment_id: str = "PAG-1",
        estado: str = "APPROVED",
        monto_centavos: int | None = None,
        moneda: str = "ARS",
        tipo: str = "payment",
        firma: str = "valida",
        request_id: str = REQUEST_ID,
        tenant_id: str | None = None,
        sena_id: str | None = None,
        turno_id: str | None = None,
        aprobado_en: datetime | None = None,
        cuerpo: dict[str, Any] | None = None,
    ) -> Any:
        """Programa el pago en la pasarela fake y POSTea la notificación firmada."""
        if tipo == "payment":
            self.pasarela.programar(
                mp_payment_id=mp_payment_id,
                estado=estado,  # type: ignore[arg-type]
                sena_id=sena_id or sena.id,
                monto_centavos=monto_centavos or sena.monto_centavos,
                moneda=moneda,
                tenant_id=tenant_id or sena.tenant_id,
                turno_id=turno_id or sena.turno_id,
                aprobado_en=aprobado_en,
            )
        headers: dict[str, str] = {"x-request-id": request_id}
        if firma == "valida":
            headers["x-signature"] = firmar(mp_payment_id, request_id=request_id)
        elif firma == "invalida":
            headers["x-signature"] = f"ts={TS_FIRMA},v1={'0' * 64}"
        elif firma == "otro_secreto":
            headers["x-signature"] = firmar(
                mp_payment_id, request_id=request_id, secreto="otro-secreto-ficticio"
            )
        return self.client.post(
            f"/api/webhooks/mercadopago?data.id={mp_payment_id}&type={tipo}",
            json=cuerpo or {"type": tipo, "data": {"id": mp_payment_id}},
            headers=headers,
        )

    # -- consultas -------------------------------------------------------

    def sena(self, sena: Sena) -> Sena:
        actual = self.senas.obtener(tenant_id=sena.tenant_id, sena_id=sena.id)
        assert actual is not None
        return actual

    def pago(self, mp_payment_id: str, *, tenant_id: str = T1) -> PagoMP | None:
        return self.pagos.obtener(tenant_id=tenant_id, mp_payment_id=mp_payment_id)

    def obligaciones(self, *, tenant_id: str = T1) -> list[PagoMP]:
        """Pagos que dejaron una obligación de devolución visible (D3/F-11)."""
        return [
            pago
            for pago in self.pagos.listar(tenant_id=tenant_id)
            if pago.resultado
            in ("MONTO_DISTINTO", "PAGO_EXCEDENTE", "REEMBOLSO_AJUSTE_CAJA")
        ]

    def eventos_hueco(self) -> list[tuple[str, str]]:
        return list(self.huecos.eventos)


class HarnessSenaAplicacion:
    """Aplicación al cobro y devolución con **C-10 real en memoria** (§9–§10).

    El movimiento no lo fabrica un espía: lo crea `ServicioCaja` con sus mismas
    reglas (día cerrado, `tramo`, totales del día). Lo único simulado es la
    persistencia y los locks; la Carrera real vive en `test_sena_carreras_pg.py`.
    """

    def __init__(self, *, ahora: datetime | None = None) -> None:
        self.ahora = ahora or AHORA
        self.senas = SenaMemoria(reloj=lambda: self.ahora)
        self.pagos = PagoMPMemoria(reloj=lambda: self.ahora)
        self.turnos = TurnoMemoriaSena()
        self.auditoria = AuditoriaSenaMemoria()
        self.presupuestos = PresupuestosMemoria()
        # C-10 real en memoria (misma puerta que producción: registrar_movimiento).
        self.movimientos = MovimientoMemoria()
        self.cuentas = CuentaPorCobrarOSMemoria()
        self.cierres = CierreMemoria(self.movimientos, self.cuentas)
        self.pendientes = CobroPendienteMemoria()
        self.ajustes = AjustePostCierreMemoria()
        self.caja_turnos = TurnoMemoria([(T1, TUR1), (T1, TUR2)])
        self.caja_usuarios = UsuarioMemoria([(T1, U2), (T1, U1)])
        self.auditoria_caja = AuditoriaMemoria()
        self.uow_caja = lambda: UowCajaMemoria(
            [
                self.movimientos,
                self.cierres,
                self.pendientes,
                self.ajustes,
                self.cuentas,
                self.auditoria_caja,
            ],
            self.movimientos,
        )
        self.caja = ServicioCaja(
            self.movimientos,
            self.cierres,
            self.pendientes,
            self.ajustes,
            self.cuentas,
            self.caja_turnos,
            self.auditoria_caja,
            usuarios=self.caja_usuarios,
            uow_factory=self.uow_caja,
            reloj=lambda: self.ahora,
        )
        self.caja_port = AplicacionCajaServicio(self.caja)
        self.svc = ServicioSenasAplicacion(
            self.senas,
            self.turnos,
            self.caja_port,
            self.presupuestos,
            self.auditoria,
            reloj=lambda: self.ahora,
            uow_factory=lambda: UnidadDeTrabajoMemoria(self.senas, self.auditoria),
        )
        self.client_caja = TestClient(crear_app_caja(self.caja))
        self.consulta = ServicioSenasConsulta(
            self.senas, self.pagos, reloj=lambda: self.ahora
        )
        self.client_interno = TestClient(
            crear_app_senas_internas(self.consulta, self.svc)
        )

    # -- siembra ---------------------------------------------------------

    def fijar_ahora(self, momento: datetime) -> datetime:
        self.ahora = momento
        return momento

    def sembrar_sena(
        self,
        *,
        tenant_id: str = T1,
        turno_id: str = TUR1,
        estado: EstadoSena = "ACREDITADA",
        monto_centavos: int = 3000,
        turno_inicio: datetime | None = None,
        turno_estado: str = "CONFIRMADO",
        paciente_id: str = PACI1,
        acreditada_en: datetime | None = None,
        expira_at: datetime | None = None,
    ) -> Sena:
        """Crea turno + seña en el estado pedido (datos ficticios, sin PHI)."""
        inicio = turno_inicio or AHORA + timedelta(days=2)
        self.turnos.agregar(
            tenant_id=tenant_id,
            turno_id=turno_id,
            inicio=inicio,
            estado=turno_estado,
            paciente_id=paciente_id,
        )
        self.caja_turnos.agregar(tenant_id, turno_id)
        sena = self.senas.crear(
            tenant_id=tenant_id,
            turno_id=turno_id,
            monto_centavos=monto_centavos,
            regla_modo="PORCENTAJE",
            regla_valor=30,
            precio_base_centavos=10000,
            anticipacion_cancelacion_h=24,
            expira_at=expira_at or AHORA + timedelta(days=1),
            token_hash=f"hash-aplicacion-{turno_id}",
            ahora=acreditada_en or AHORA - timedelta(days=3),
            turno_inicio=inicio,
            turno_fin=inicio + timedelta(minutes=30),
            turno_prestacion=PREST1,
        )
        if estado == "PENDIENTE":
            return sena
        campos: dict[str, Any] = {"acreditada_en": acreditada_en or AHORA}
        if estado == "LIBERADA":
            campos = {"liberada_en": AHORA, "motivo_liberacion": "EXPIRACION"}
        elif estado == "DEVUELTA":
            campos = {
                "devuelta_en": AHORA,
                "motivo_devolucion": "POLITICA_CANCELACION",
                "devuelta_por": None,
            }
        elif estado == "APLICADA":
            campos = {
                "acreditada_en": acreditada_en or AHORA,
                "aplicada_en": AHORA,
                "movimiento_caja_id": "movimiento-mp-sembrado",
                "concepto_aplicacion": "TRATAMIENTO",
            }
        actual = self.senas.transicionar(
            tenant_id=tenant_id,
            sena_id=sena.id,
            desde="PENDIENTE",
            hacia=estado,
            campos=campos,
        )
        assert actual is not None
        return actual

    # -- consultas -------------------------------------------------------

    def sena(self, sena: Sena) -> Sena:
        actual = self.senas.obtener(tenant_id=sena.tenant_id, sena_id=sena.id)
        assert actual is not None
        return actual

    def movimientos_del_dia(self, fecha: date) -> list[Any]:
        return self.movimientos.listar_por_fecha(tenant_id=T1, fecha=fecha)

    def movimientos_http(self, fecha: date, *, rol: str = "RECEPCION", usuario: str = U1) -> Any:
        return self.client_caja.get(
            "/api/caja/movimientos",
            params={"fecha": fecha.isoformat()},
            headers={
                "x-tenant-id": T1,
                "x-user-id": usuario,
                "x-rol": rol,
            },
        )

    def cerrar_dia(self, fecha: date | None = None) -> None:
        self.caja.cerrar_dia(
            Actor(tenant_id=T1, rol="ADMIN", user_id=U2),
            fecha=fecha or self.ahora.date(),
            efectivo_contado=0,
            responsable_id=U2,
        )
