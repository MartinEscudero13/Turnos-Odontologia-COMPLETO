"""Servicio de presupuesto — C-09 (secciones 4 y 5).

Dominio puro: programa contra los puertos de `puertos.py` y no toca DB ni red.
Reproduce el contrato de la migración 007 y de la KB:

- D5: estados `BORRADOR → VIGENTE → PARCIAL → ACEPTADO` y `VENCIDO`; `vence_en`
  se fija al emitir (crear con `vence_en` ⇒ `422`, emitir con fecha pasada ⇒
  `422`); el `GET` reporta `VENCIDO` sin persistir y el `POST /aceptar` lo
  persiste auditado y responde `409`; un `PARCIAL` no vence por reloj en v1.
- D6/M1/M2/M6: cobertura por `(tenant, paciente.obra_social_id, prestación)`,
  sin obra social no se consulta, validación de la configuración y del
  resultado con fallback 100 % particular visible, y `origen_cobertura`/
  `validada_en_vivo` persistidos al crear y **nunca** recalculados al leer.
- D4/B1/RN-CL-02: aceptación parcial por línea; sólo lo aceptado imputa; una
  línea se imputa una sola vez y la exclusión se garantiza con el lock de fila
  (`bloquear_linea`) más la revalidación post-lock —nunca con el chequeo previo
  a secas, que es TOCTOU—.
- D8.1/M5: sólo alta de líneas con el presupuesto en `BORRADOR`; no hay
  `PATCH`/`DELETE` de líneas en v1.
- D12/RN-AU-02: auditoría append-only sin texto clínico ni datos personales.

Fuera de esta tanda (no implementado acá): RBAC de borde y routers (§6/§7),
auditoría HTTP (§9) y UI (§8, diferida a `C-09-UI`). El gate de consentimiento
para líneas clínicas también llega en §6.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast

from app.core.logging import get_logger
from app.ficha_clinica.servicio import ConsentimientoRequerido
from app.odontograma.fdi import validar_monto, validar_pieza_fdi
from app.presupuesto.puertos import (
    AccionPresupuesto,
    Aceptacion,
    AceptacionRepositorio,
    AuditoriaPort,
    CoberturaConfigurada,
    CoberturaPort,
    ConsentimientoPort,
    EstadoPresupuesto,
    ImputacionPort,
    Linea,
    LineaRepositorio,
    MedioPago,
    OrigenCobertura,
    PacientePort,
    PrestacionPort,
    Presupuesto,
    PresupuestoRepositorio,
    Reloj,
    UnidadDeTrabajo,
)
from app.turnos.servicio import Actor, Invalido, NoAutenticado, NoEncontrado, Prohibido, TurnoError

logger = get_logger("app.presupuesto")

__all__ = [
    "CalculadoraCobertura",
    "Conflicto",
    "DecisionRegistrada",
    "LineaConDecision",
    "PresupuestoConsultado",
    "ServicioNoDisponible",
    "ServicioPresupuesto",
    "TramoCobertura",
    "calcular_tramos",
]

_CREA_PRESUPUESTO = frozenset({"ADMIN", "ODONTOLOGO", "RECEPCION"})
_LEE_PRESUPUESTO = frozenset({"ADMIN", "ODONTOLOGO", "RECEPCION"})
_REGISTRA_ACEPTACION = frozenset({"ADMIN", "RECEPCION"})
_MEDIOS: frozenset[str] = frozenset({"EFECTIVO", "TRANSFERENCIA", "MP", "OS"})
_MODOS: frozenset[str] = frozenset({"PORCENTAJE", "MONTO"})
_ACEPTA_DECISION = frozenset({"VIGENTE", "PARCIAL"})


class Conflicto(TurnoError):
    """409 — conflicto de estado (vencido, fuera de BORRADOR, línea ya decidida)."""

    codigo = 409


class ServicioNoDisponible(TurnoError):
    """503 — falló un puerto externo de imputación (la transacción revierte)."""

    codigo = 503


@dataclass(frozen=True)
class TramoCobertura:
    """Resultado del cálculo de cobertura: los dos tramos ya separados (D6/B3)."""

    cobertura_os: int
    a_cargo_paciente: int
    origen_cobertura: OrigenCobertura


@dataclass(frozen=True)
class LineaConDecision:
    """Línea consultable para recupero junto a su última decisión (o `None`)."""

    linea: Linea
    aceptacion: Aceptacion | None


@dataclass(frozen=True)
class PresupuestoConsultado:
    """Lectura: estado reportado (puede ser `VENCIDO` sin persistir) y líneas."""

    presupuesto: Presupuesto
    estado_reportado: EstadoPresupuesto
    lineas: tuple[LineaConDecision, ...]


@dataclass(frozen=True)
class DecisionRegistrada:
    presupuesto: Presupuesto
    aceptacion: Aceptacion


CalculadoraCobertura = Callable[[int, CoberturaConfigurada], TramoCobertura]


class _FalloImputacion(Exception):
    """Señal interna: un puerto de imputación falló (se traduce a 503)."""


def calcular_tramos(monto: int, config: CoberturaConfigurada) -> TramoCobertura:
    """Calcula los dos tramos de una cobertura ya validada (D6).

    El cociente de un porcentaje se trunca y el resto queda a cargo del paciente:
    nunca se crea dinero (la política exacta es C09-OQ-6).
    """
    calculado = monto * config.valor // 100 if config.modo == "PORCENTAJE" else config.valor
    cobertura = max(min(calculado, monto), 0)
    if config.tope is not None:
        cobertura = max(min(cobertura, config.tope), 0)
    return TramoCobertura(
        cobertura_os=cobertura,
        a_cargo_paciente=monto - cobertura,
        origen_cobertura="CONFIGURADA",
    )


class ServicioPresupuesto:
    """Casos de uso del presupuesto (alta, líneas, emisión y aceptación)."""

    def __init__(
        self,
        presupuestos: PresupuestoRepositorio,
        lineas: LineaRepositorio,
        aceptaciones: AceptacionRepositorio,
        prestaciones: PrestacionPort,
        pacientes: PacientePort,
        coberturas: CoberturaPort,
        imputacion: ImputacionPort,
        auditoria: AuditoriaPort,
        *,
        consentimientos: ConsentimientoPort,
        uow_factory: Callable[[], UnidadDeTrabajo],
        reloj: Reloj | None = None,
        calculadora: CalculadoraCobertura | None = None,
    ) -> None:
        self._presupuestos = presupuestos
        self._lineas = lineas
        self._aceptaciones = aceptaciones
        self._prestaciones = prestaciones
        self._pacientes = pacientes
        self._coberturas = coberturas
        self._imputacion = imputacion
        self._auditoria = auditoria
        self._consentimientos = consentimientos
        self._uow_factory = uow_factory
        self._reloj: Reloj = reloj or (lambda: datetime.now(UTC))
        self._calculadora: CalculadoraCobertura = calculadora or calcular_tramos

    # ------------------------------------------------------------------
    # Creación y lectura
    # ------------------------------------------------------------------

    def crear(
        self,
        actor: Actor,
        *,
        paciente_id: str,
        vence_en: object | None = None,
        ahora: datetime | None = None,
    ) -> Presupuesto:
        """Crea un presupuesto `BORRADOR`; el vencimiento sólo se fija al emitir."""
        self._exigir_rol(actor, _CREA_PRESUPUESTO)
        if vence_en is not None:
            # Espeja el `extra="forbid"` del borde (§7): el campo no se admite.
            raise Invalido("vence_en no se admite al crear: se fija al emitir")
        tenant_id = actor.tenant_id
        if not self._pacientes.existe(tenant_id=tenant_id, paciente_id=paciente_id):
            raise NoEncontrado("paciente no encontrado")
        momento = self._momento(ahora)
        with self._uow_factory():
            creado = self._presupuestos.crear(
                tenant_id=tenant_id, paciente_id=paciente_id, ahora=momento
            )
            self._auditar(
                tenant_id,
                "PRESUPUESTO_CREADO",
                actor.user_id,
                "presupuesto",
                creado.id,
                despues={"paciente_id": paciente_id, "estado": creado.estado},
            )
        return creado

    def obtener(
        self,
        actor: Actor,
        *,
        presupuesto_id: str,
        ahora: datetime | None = None,
    ) -> PresupuestoConsultado:
        """Lectura pura: reporta `VENCIDO` sin persistir ni auditar (D5)."""
        self._exigir_rol(actor, _LEE_PRESUPUESTO)
        tenant_id = actor.tenant_id
        presupuesto = self._presupuestos.obtener(
            tenant_id=tenant_id, presupuesto_id=presupuesto_id
        )
        if presupuesto is None:
            raise NoEncontrado("presupuesto no encontrado")
        lineas = tuple(
            LineaConDecision(
                linea=linea,
                aceptacion=self._aceptaciones.ultima_por_linea(
                    tenant_id=tenant_id, linea_id=linea.id
                ),
            )
            for linea in self._lineas.listar(
                tenant_id=tenant_id, presupuesto_id=presupuesto_id
            )
        )
        return PresupuestoConsultado(
            presupuesto=presupuesto,
            estado_reportado=self._estado_reportado(presupuesto, self._momento(ahora)),
            lineas=lineas,
        )

    def listar(
        self,
        actor: Actor,
        *,
        paciente_id: str,
        ahora: datetime | None = None,
    ) -> list[PresupuestoConsultado]:
        """Presupuestos del paciente en el tenant, tenant-scoped y sin PHI."""
        self._exigir_rol(actor, _LEE_PRESUPUESTO)
        tenant_id = actor.tenant_id
        return [
            self.obtener(actor, presupuesto_id=p.id, ahora=ahora)
            for p in self._presupuestos.listar(
                tenant_id=tenant_id, paciente_id=paciente_id
            )
        ]

    # ------------------------------------------------------------------
    # Líneas
    # ------------------------------------------------------------------

    def agregar_linea(
        self,
        actor: Actor,
        *,
        presupuesto_id: str,
        prestacion_id: str,
        monto: object | None = None,
        pieza_fdi: object | None = None,
        hallazgo_id: str | None = None,
        ahora: datetime | None = None,
    ) -> Linea:
        """Agrega una línea con cobertura calculada; sólo con el presupuesto en BORRADOR.

        Si se omite `monto` se usa el `precio_base` de la prestación (centavos).
        """
        self._exigir_rol(actor, _CREA_PRESUPUESTO)
        tenant_id = actor.tenant_id
        presupuesto = self._presupuestos.obtener(
            tenant_id=tenant_id, presupuesto_id=presupuesto_id
        )
        if presupuesto is None:
            raise NoEncontrado("presupuesto no encontrado")
        if presupuesto.estado != "BORRADOR":
            raise Conflicto("sólo se agregan líneas con el presupuesto en BORRADOR")
        precio_base = self._prestaciones.precio_base(
            tenant_id=tenant_id, prestacion_id=prestacion_id
        )
        if precio_base is None:
            raise NoEncontrado("prestación no encontrada")
        monto_efectivo = validar_monto(precio_base if monto is None else monto)
        pieza = validar_pieza_fdi(pieza_fdi) if pieza_fdi is not None else None
        if pieza is not None or hallazgo_id is not None:
            # D11: una línea clínica exige el consentimiento de C-08; una línea
            # administrativa (sin pieza ni hallazgo) no queda sujeta al gate.
            self._exigir_consentimiento(tenant_id, presupuesto.paciente_id)
        momento = self._momento(ahora)
        with self._uow_factory():
            tramo = self._cobertura_de_linea(
                tenant_id=tenant_id,
                paciente_id=presupuesto.paciente_id,
                prestacion_id=prestacion_id,
                monto=monto_efectivo,
                actor_id=actor.user_id,
                presupuesto_id=presupuesto_id,
            )
            linea = self._lineas.agregar(
                tenant_id=tenant_id,
                presupuesto_id=presupuesto_id,
                prestacion_id=prestacion_id,
                monto=monto_efectivo,
                cobertura_os=tramo.cobertura_os,
                a_cargo_paciente=tramo.a_cargo_paciente,
                origen_cobertura=tramo.origen_cobertura,
                validada_en_vivo=False,
                pieza_fdi=pieza,
                hallazgo_id=hallazgo_id,
                ahora=momento,
            )
            self._auditar(
                tenant_id,
                "LINEA_PRESUPESTADA",
                actor.user_id,
                "presupuesto",
                presupuesto_id,
                despues={
                    "linea_id": linea.id,
                    "prestacion_id": prestacion_id,
                    "pieza_fdi": pieza,
                    "monto_centavos": monto_efectivo,
                    "cobertura_os": tramo.cobertura_os,
                    "a_cargo_paciente": tramo.a_cargo_paciente,
                    "origen_cobertura": tramo.origen_cobertura,
                },
            )
        return linea

    # ------------------------------------------------------------------
    # Emisión
    # ------------------------------------------------------------------

    def emitir(
        self,
        actor: Actor,
        *,
        presupuesto_id: str,
        vence_en: object = None,
        ahora: datetime | None = None,
    ) -> Presupuesto:
        """Pasa a `VIGENTE` exigiendo al menos una línea y un `vence_en` futuro."""
        self._exigir_rol(actor, _CREA_PRESUPUESTO)
        tenant_id = actor.tenant_id
        presupuesto = self._presupuestos.obtener(
            tenant_id=tenant_id, presupuesto_id=presupuesto_id
        )
        if presupuesto is None:
            raise NoEncontrado("presupuesto no encontrado")
        if presupuesto.estado != "BORRADOR":
            raise Conflicto("sólo se emite un presupuesto en BORRADOR")
        if not self._lineas.listar(tenant_id=tenant_id, presupuesto_id=presupuesto_id):
            raise Conflicto("no se emite un presupuesto sin líneas")
        momento = self._momento(ahora)
        vencimiento: datetime | None = None
        if vence_en is not None:
            if not isinstance(vence_en, datetime):
                raise Invalido("vence_en debe ser una fecha con zona horaria")
            self._exigir_aware(vence_en)
            if vence_en <= momento:
                raise Invalido("vence_en debe ser posterior a ahora")
            vencimiento = vence_en
        with self._uow_factory():
            emitido = self._presupuestos.emitir(
                tenant_id=tenant_id,
                presupuesto_id=presupuesto_id,
                vence_en=vencimiento,
                ahora=momento,
            )
            self._auditar(
                tenant_id,
                "PRESUPUESTO_EMITIDO",
                actor.user_id,
                "presupuesto",
                presupuesto_id,
                antes={"estado": presupuesto.estado},
                despues={
                    "estado": emitido.estado,
                    "vence_en": vencimiento.isoformat() if vencimiento else None,
                },
            )
        return emitido

    # ------------------------------------------------------------------
    # Aceptación parcial y total
    # ------------------------------------------------------------------

    def registrar_aceptacion(
        self,
        actor: Actor,
        *,
        presupuesto_id: str,
        linea_id: str,
        acepta: bool,
        canal: object = None,
        medio: object = None,
        ahora: datetime | None = None,
    ) -> DecisionRegistrada:
        """Registra la decisión de una línea e imputa sólo lo aceptado (D4).

        La línea se bloquea con `bloquear_linea` **antes** de revalidar y de
        llamar a cualquier puerto: sin el lock, dos transacciones leerían "sin
        decisión" y ambas imputarían (TOCTOU). La garantía real se prueba con
        dos conexiones a PostgreSQL.
        """
        self._exigir_rol(actor, _REGISTRA_ACEPTACION)
        canal_limpio = self._validar_canal(canal)
        medio_limpio = self._validar_medio(medio)
        tenant_id = actor.tenant_id
        presupuesto = self._presupuestos.obtener(
            tenant_id=tenant_id, presupuesto_id=presupuesto_id
        )
        if presupuesto is None:
            raise NoEncontrado("presupuesto no encontrado")
        momento = self._momento(ahora)

        if presupuesto.estado == "VENCIDO":
            # Ya persistido: no se vuelve a escribir ni a auditar (D5).
            raise Conflicto("presupuesto vencido")
        if self._estado_reportado(presupuesto, momento) == "VENCIDO":
            self._persistir_vencido(actor, presupuesto, momento)
            raise Conflicto("presupuesto vencido")
        if presupuesto.estado not in _ACEPTA_DECISION:
            raise Conflicto(f"no se acepta un presupuesto en {presupuesto.estado}")

        try:
            with self._uow_factory() as uow:
                # Lock de fila (D4/B1): a partir de acá la segunda transacción
                # espera y, al revalidar, ya ve la decisión persistida.
                linea = uow.bloquear_linea(tenant_id=tenant_id, linea_id=linea_id)
                if linea.presupuesto_id != presupuesto_id:
                    raise NoEncontrado("línea no encontrada en el presupuesto")
                if (
                    self._aceptaciones.ultima_por_linea(
                        tenant_id=tenant_id, linea_id=linea_id
                    )
                    is not None
                ):
                    raise Conflicto("la línea ya tiene una decisión registrada")
                aceptacion = self._aceptaciones.registrar(
                    tenant_id=tenant_id,
                    linea_id=linea_id,
                    acepta=acepta,
                    fecha=momento,
                    canal=canal_limpio,
                    medio=medio_limpio,
                    ahora=momento,
                )
                self._auditar(
                    tenant_id,
                    "ACEPTACION_REGISTRADA",
                    actor.user_id,
                    "presupuesto",
                    presupuesto_id,
                    despues={
                        "linea_id": linea_id,
                        "acepta": acepta,
                        "canal": canal_limpio,
                        "medio": medio_limpio,
                        "monto_centavos": linea.monto,
                    },
                )
                if acepta:
                    self._imputar_linea(actor, presupuesto, linea, medio_limpio)
                    self._auditar(
                        tenant_id,
                        "IMPUTACION_REGISTRADA",
                        actor.user_id,
                        "presupuesto",
                        presupuesto_id,
                        despues={
                            "linea_id": linea_id,
                            "monto_paciente_centavos": linea.a_cargo_paciente,
                            "monto_os_centavos": linea.cobertura_os,
                        },
                    )
                estado = self._estado_tras_decision(
                    tenant_id=tenant_id, presupuesto=presupuesto
                )
                actualizado = (
                    self._presupuestos.actualizar_estado(
                        tenant_id=tenant_id,
                        presupuesto_id=presupuesto_id,
                        estado=estado,
                        ahora=momento,
                    )
                    if estado != presupuesto.estado
                    else presupuesto
                )
            # RN-CL-04: sólo ids y montos; nunca nombre, teléfono ni texto clínico.
            logger.info(
                "aceptacion_registrada tenant_id=%s presupuesto_id=%s linea_id=%s "
                "estado=%s acepta=%s monto_centavos=%s",
                tenant_id,
                presupuesto_id,
                linea_id,
                estado,
                acepta,
                linea.monto,
            )
        except _FalloImputacion:
            raise ServicioNoDisponible(
                "no se pudo registrar la imputación de la línea"
            ) from None
        return DecisionRegistrada(presupuesto=actualizado, aceptacion=aceptacion)

    # ------------------------------------------------------------------
    # Cobertura (D6)
    # ------------------------------------------------------------------

    def _cobertura_de_linea(
        self,
        *,
        tenant_id: str,
        paciente_id: str,
        prestacion_id: str,
        monto: int,
        actor_id: str,
        presupuesto_id: str,
    ) -> TramoCobertura:
        obra_social_id = self._pacientes.obra_social_id(
            tenant_id=tenant_id, paciente_id=paciente_id
        )
        if obra_social_id is None:
            # M1: sin obra social no se consulta ninguna cobertura.
            return self._particular(monto)
        config = self._coberturas.cobertura(
            tenant_id=tenant_id,
            obra_social_id=obra_social_id,
            prestacion_id=prestacion_id,
        )
        if config is None:
            return self._particular(monto)
        motivo = _motivo_configuracion(config)
        if motivo is not None:
            self._auditar_descarte(
                tenant_id=tenant_id,
                actor_id=actor_id,
                presupuesto_id=presupuesto_id,
                prestacion_id=prestacion_id,
                obra_social_id=obra_social_id,
                motivo=motivo,
            )
            return self._particular(monto)
        tramo = self._calculadora(monto, config)
        motivo = _motivo_resultado(tramo, monto)
        if motivo is not None:
            self._auditar_descarte(
                tenant_id=tenant_id,
                actor_id=actor_id,
                presupuesto_id=presupuesto_id,
                prestacion_id=prestacion_id,
                obra_social_id=obra_social_id,
                motivo=motivo,
            )
            return self._particular(monto)
        return TramoCobertura(
            cobertura_os=tramo.cobertura_os,
            a_cargo_paciente=tramo.a_cargo_paciente,
            origen_cobertura="CONFIGURADA",
        )

    @staticmethod
    def _particular(monto: int) -> TramoCobertura:
        return TramoCobertura(
            cobertura_os=0, a_cargo_paciente=monto, origen_cobertura="SIN_COBERTURA"
        )

    def _auditar_descarte(
        self,
        *,
        tenant_id: str,
        actor_id: str,
        presupuesto_id: str,
        prestacion_id: str,
        obra_social_id: str,
        motivo: str,
    ) -> None:
        self._auditar(
            tenant_id,
            "COBERTURA_INVALIDA_DESCARTADA",
            actor_id,
            "presupuesto",
            presupuesto_id,
            despues={
                "prestacion_id": prestacion_id,
                "obra_social_id": obra_social_id,
                "motivo": motivo,
            },
        )

    # ------------------------------------------------------------------
    # Imputación (D4/M10)
    # ------------------------------------------------------------------

    def _imputar_linea(
        self, actor: Actor, presupuesto: Presupuesto, linea: Linea, medio: MedioPago | None
    ) -> None:
        """Caja primero y agenda después: si caja falla no queda intención de agenda."""
        try:
            self._imputacion.imputar_caja(
                tenant_id=presupuesto.tenant_id,
                presupuesto_id=presupuesto.id,
                linea_id=linea.id,
                paciente_id=presupuesto.paciente_id,
                prestacion_id=linea.prestacion_id,
                monto_paciente_centavos=linea.a_cargo_paciente,
                monto_os_centavos=linea.cobertura_os,
                actor_id=actor.user_id,
                turno_id=None,
                medio=medio,
            )
            self._imputacion.imputar_agenda(
                tenant_id=presupuesto.tenant_id,
                presupuesto_id=presupuesto.id,
                linea_id=linea.id,
                paciente_id=presupuesto.paciente_id,
                prestacion_id=linea.prestacion_id,
                monto_centavos=linea.monto,
            )
        except Exception as exc:  # noqa: BLE001 - el puerto puede fallar de cualquier forma
            raise _FalloImputacion from exc

    # ------------------------------------------------------------------
    # Estados
    # ------------------------------------------------------------------

    def _estado_reportado(
        self, presupuesto: Presupuesto, momento: datetime
    ) -> EstadoPresupuesto:
        """`VENCIDO` se reporta sin persistir y sólo para un `VIGENTE` (D5)."""
        if (
            presupuesto.estado == "VIGENTE"
            and presupuesto.vence_en is not None
            and presupuesto.vence_en < momento
        ):
            return "VENCIDO"
        return presupuesto.estado

    def _estado_tras_decision(
        self, *, tenant_id: str, presupuesto: Presupuesto
    ) -> EstadoPresupuesto:
        """Aceptadas + pendientes/rechazadas ⇒ PARCIAL; todas aceptadas ⇒ ACEPTADO.

        Con 0 líneas aceptadas conserva el estado anterior y nunca pasa a
        `ACEPTADO`; una línea rechazada impide `ACEPTADO` (D4/D5, C09-OQ-3).
        """
        lineas = self._lineas.listar(
            tenant_id=tenant_id, presupuesto_id=presupuesto.id
        )
        aceptadas = 0
        for linea in lineas:
            decision = self._aceptaciones.ultima_por_linea(
                tenant_id=tenant_id, linea_id=linea.id
            )
            if decision is not None and decision.acepta:
                aceptadas += 1
        if aceptadas == 0:
            return presupuesto.estado
        if aceptadas == len(lineas):
            return "ACEPTADO"
        return "PARCIAL"

    def _persistir_vencido(
        self, actor: Actor, presupuesto: Presupuesto, momento: datetime
    ) -> None:
        """El `POST /aceptar` persiste `VENCIDO` auditado en su propia transacción."""
        with self._uow_factory():
            self._presupuestos.actualizar_estado(
                tenant_id=presupuesto.tenant_id,
                presupuesto_id=presupuesto.id,
                estado="VENCIDO",
                ahora=momento,
            )
            self._auditar(
                presupuesto.tenant_id,
                "PRESUPUESTO_VENCIDO",
                actor.user_id,
                "presupuesto",
                presupuesto.id,
                antes={"estado": presupuesto.estado},
                despues={
                    "estado": "VENCIDO",
                    "vence_en": (
                        presupuesto.vence_en.isoformat()
                        if presupuesto.vence_en is not None
                        else None
                    ),
                },
            )

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _momento(self, ahora: datetime | None) -> datetime:
        return ahora if ahora is not None else self._reloj()

    @staticmethod
    def _validar_canal(canal: object) -> str:
        if not isinstance(canal, str) or not canal.strip():
            raise Invalido("canal requerido")
        return canal

    @staticmethod
    def _validar_medio(medio: object) -> MedioPago | None:
        if medio is None:
            return None
        if not isinstance(medio, str) or medio not in _MEDIOS:
            raise Invalido("medio inválido")
        return cast(MedioPago, medio)

    @staticmethod
    def _exigir_rol(actor: Actor, roles: frozenset[str]) -> None:
        if actor.rol == "PACIENTE":
            # v1 no tiene sesión de paciente (D13): 401, no 403.
            raise NoAutenticado("sesión interna requerida")
        if actor.rol not in roles:
            raise Prohibido("rol sin permiso")

    def _exigir_consentimiento(self, tenant_id: str, paciente_id: str) -> None:
        if not self._consentimientos.firmado(
            tenant_id=tenant_id, paciente_id=paciente_id
        ):
            raise ConsentimientoRequerido("CONSENTIMIENTO_REQUERIDO")

    @staticmethod
    def _exigir_aware(valor: datetime) -> None:
        if valor.tzinfo is None or valor.tzinfo.utcoffset(valor) is None:
            raise Invalido("vence_en debe ser timezone-aware")

    def _auditar(
        self,
        tenant_id: str,
        accion: AccionPresupuesto,
        actor_id: str,
        entidad: str,
        entidad_id: str,
        *,
        antes: dict[str, object] | None = None,
        despues: dict[str, object] | None = None,
    ) -> None:
        self._auditoria.registrar(
            tenant_id=tenant_id,
            accion=accion,
            actor=actor_id,
            entidad=entidad,
            entidad_id=entidad_id,
            antes=antes,
            despues=despues,
        )


def _entero(valor: object) -> int | None:
    if isinstance(valor, bool) or not isinstance(valor, int):
        return None
    return valor


def _motivo_configuracion(config: CoberturaConfigurada) -> str | None:
    """D6.1: valida la configuración **antes** de calcular; `None` = válida."""
    if config.modo not in _MODOS:
        return "MODO_INVALIDO"
    valor = _entero(config.valor)
    if valor is None:
        return "VALOR_NO_ENTERO"
    if config.modo == "PORCENTAJE" and not 0 <= valor <= 100:
        return "PORCENTAJE_FUERA_DE_RANGO"
    if config.modo == "MONTO" and valor < 0:
        return "MONTO_NEGATIVO"
    if config.tope is not None:
        tope = _entero(config.tope)
        if tope is None:
            return "TOPE_NO_ENTERO"
        if tope < 0:
            return "TOPE_NEGATIVO"
    return None


def _motivo_resultado(tramo: TramoCobertura, monto: int) -> str | None:
    """D6.2: valida el **resultado** antes de persistir; `None` = consistente."""
    cobertura = _entero(tramo.cobertura_os)
    a_cargo = _entero(tramo.a_cargo_paciente)
    if cobertura is None or a_cargo is None:
        return "RESULTADO_NO_ENTERO"
    if cobertura < 0:
        return "COBERTURA_NEGATIVA"
    if a_cargo < 0:
        return "A_CARGO_NEGATIVO"
    if cobertura + a_cargo != monto:
        return "SUMA_INCONSISTENTE"
    return None
