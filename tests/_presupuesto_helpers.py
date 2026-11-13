"""Helpers compartidos por los tests del presupuesto — C-09 (no recolectado).

Cablea `ServicioPresupuesto` con adaptadores en memoria, datos ficticios
("Paciente Demo", P1, "Conducto Demo" con `precio_base=150000` centavos, obras
sociales `OS-1`/`OS-2`) y reloj inyectado (`d3`, `-03:00`). La unidad de trabajo
cubre presupuestos, líneas, aceptaciones y auditoría: si el caso de uso falla no
queda aceptación, ni cambio de estado, ni rastro de auditoría (la imputación es
un puerto externo y no la revierte la unidad de trabajo, ver D4).
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from _odontograma_helpers import (
    PAC1,
    PAC9,
    PRECIO_CONDUCTO,
    PREST1,
    PREST9,
    actor,
    d3,
)
from conftest import T1, T2

from app.ficha_clinica.puertos import ConsentimientoMemoria
from app.presupuesto.puertos import (
    AceptacionMemoria,
    AuditoriaMemoria,
    CoberturaConfigurada,
    CoberturaMemoria,
    ImputacionMemoria,
    ImputacionPort,
    Linea,
    LineaMemoria,
    ModoCobertura,
    PacienteMemoria,
    PrestacionMemoria,
    Presupuesto,
    PresupuestoMemoria,
    UnidadDeTrabajo,
    UnidadDeTrabajoMemoria,
)
from app.presupuesto.servicio import (
    CalculadoraCobertura,
    DecisionRegistrada,
    ServicioPresupuesto,
)
from app.turnos.servicio import Actor

OS1 = "OS-1"
OS2 = "OS-2"
PAC2 = "paciente-2"


class HarnessPresupuesto:
    """Dominio de presupuesto cableado en memoria, con semillas ficticias de T1."""

    def __init__(
        self,
        *,
        imputacion: ImputacionPort | None = None,
        calculadora: CalculadoraCobertura | None = None,
    ) -> None:
        self.presupuestos = PresupuestoMemoria()
        self.lineas = LineaMemoria()
        self.aceptaciones = AceptacionMemoria()
        self.prestaciones = PrestacionMemoria()
        self.pacientes = PacienteMemoria()
        self.coberturas = CoberturaMemoria()
        self.imputacion = imputacion if imputacion is not None else ImputacionMemoria()
        self.auditoria = AuditoriaMemoria()
        self.consentimientos = ConsentimientoMemoria()
        self._calculadora = calculadora
        self.uow = self.nueva_uow()
        self.svc = self._servicio(self.nueva_uow)
        self.pacientes.agregar(T1, PAC1, OS1)
        self.pacientes.agregar(T1, PAC2, None)
        self.pacientes.agregar(T2, PAC9, OS1)
        self.prestaciones.agregar(T1, PREST1, PRECIO_CONDUCTO)
        self.prestaciones.agregar(T2, PREST9, PRECIO_CONDUCTO)

    # -- cableado -------------------------------------------------------

    def nueva_uow(self) -> UnidadDeTrabajoMemoria:
        return UnidadDeTrabajoMemoria(
            [self.presupuestos, self.lineas, self.aceptaciones, self.auditoria],
            self.lineas,
        )

    def _servicio(
        self, factory: Callable[[], UnidadDeTrabajo]
    ) -> ServicioPresupuesto:
        return ServicioPresupuesto(
            self.presupuestos,
            self.lineas,
            self.aceptaciones,
            self.prestaciones,
            self.pacientes,
            self.coberturas,
            self.imputacion,
            self.auditoria,
            consentimientos=self.consentimientos,
            uow_factory=factory,
            reloj=d3,
            calculadora=self._calculadora,
        )

    def cablear_uow(self, factory: Callable[[], UnidadDeTrabajo]) -> None:
        """Reemplaza la unidad de trabajo (test de orden lock/revalidación)."""
        self.svc = self._servicio(factory)

    # -- semillas -------------------------------------------------------

    def dar_consentimiento(self, paciente_id: str = PAC1, tenant: str = T1) -> None:
        self.consentimientos.registrar(
            tenant_id=tenant,
            paciente_id=paciente_id,
            timestamp=d3("2026-11-09", hora=9),
            canal="móvil",
            ahora=d3("2026-11-09", hora=9),
        )

    def seed_cobertura(
        self,
        *,
        modo: ModoCobertura = "PORCENTAJE",
        valor: int = 50,
        tope: int | None = None,
        obra_social_id: str = OS1,
        prestacion_id: str = PREST1,
        tenant: str = T1,
    ) -> CoberturaConfigurada:
        config = CoberturaConfigurada(modo=modo, valor=valor, tope=tope)
        self.coberturas.agregar(tenant, obra_social_id, prestacion_id, config)
        return config


# ---------------------------------------------------------------------------
# Casos de uso frecuentes
# ---------------------------------------------------------------------------


def crear_borrador(
    h: HarnessPresupuesto,
    *,
    paciente_id: str = PAC1,
    ahora: datetime | None = None,
    rol: str = "RECEPCION",
) -> Presupuesto:
    return h.svc.crear(
        actor(rol),
        paciente_id=paciente_id,
        ahora=d3() if ahora is None else ahora,
    )


def agregar_linea(
    h: HarnessPresupuesto,
    presupuesto_id: str,
    *,
    monto: object = 100000,
    pieza_fdi: object | None = None,
    prestacion_id: str = PREST1,
    ahora: datetime | None = None,
) -> Linea:
    return h.svc.agregar_linea(
        actor("RECEPCION"),
        presupuesto_id=presupuesto_id,
        prestacion_id=prestacion_id,
        monto=monto,  # type: ignore[arg-type]  # los tests pasan valores inválidos a propósito
        pieza_fdi=pieza_fdi,
        ahora=d3() if ahora is None else ahora,
    )


def emitir(
    h: HarnessPresupuesto,
    presupuesto_id: str,
    *,
    vence_en: object = None,
    ahora: datetime | None = None,
) -> Presupuesto:
    return h.svc.emitir(
        actor("RECEPCION"),
        presupuesto_id=presupuesto_id,
        vence_en=vence_en,
        ahora=d3() if ahora is None else ahora,
    )


def presupuesto_vigente(
    h: HarnessPresupuesto,
    *,
    cantidad_lineas: int = 1,
    monto: int = 100000,
    vence_en: object = None,
    ahora_emision: datetime | None = None,
) -> tuple[str, list[str]]:
    """Crea un presupuesto `VIGENTE` con `cantidad_lineas` líneas de `monto`."""
    momento = d3() if ahora_emision is None else ahora_emision
    borrador = crear_borrador(h, ahora=momento)
    for _ in range(cantidad_lineas):
        agregar_linea(h, borrador.id, monto=monto, ahora=momento)
    emitir(h, borrador.id, vence_en=vence_en, ahora=momento)
    lineas = h.lineas.listar(tenant_id=T1, presupuesto_id=borrador.id)
    return borrador.id, [linea.id for linea in lineas]


def registrar_aceptacion(
    h: HarnessPresupuesto,
    presupuesto_id: str,
    linea_id: str,
    *,
    acepta: bool = True,
    canal: object = "CONSULTORIO",
    medio: object = None,
    ahora: datetime | None = None,
    rol: str = "RECEPCION",
    actor_: Actor | None = None,
) -> DecisionRegistrada:
    return h.svc.registrar_aceptacion(
        actor(rol) if actor_ is None else actor_,
        presupuesto_id=presupuesto_id,
        linea_id=linea_id,
        acepta=acepta,
        canal=canal,
        medio=medio,  # type: ignore[arg-type]  # los tests pasan valores inválidos a propósito
        ahora=d3() if ahora is None else ahora,
    )
