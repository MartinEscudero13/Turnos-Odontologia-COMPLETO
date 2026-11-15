"""Casos de uso de C-12: obras sociales, coberturas y liquidación.

Reglas aplicadas:
- RN-OS-01: cobertura configurable por `(OS × prestación)`; v1 no valida en vivo.
- RN-OS-02: liquidación por período con detalle por turno atendido y CSV.
- RN-OS-03: el catálogo arranca con 3–5 obras sociales ficticias por tenant.
- RN-AU-01/RN-AU-02: RBAC por rol y auditoría append-only de cada cambio.
"""
from __future__ import annotations

import csv
import io
from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import cast

from app.obras_sociales.puertos import (
    CODIGO_LIQUIDACION_CERRADA,
    CODIGO_OBRA_SOCIAL_DUPLICADA,
    CODIGO_SIN_TURNOS,
    AuditoriaPort,
    Cobertura,
    CoberturaRepositorio,
    Conflicto,
    Liquidacion,
    LiquidacionDuplicada,
    LiquidacionRepositorio,
    ModoCobertura,
    ObraSocial,
    ObraSocialDuplicada,
    ObraSocialRepositorio,
    PacienteObraSocialPort,
    PrestacionPrecioPort,
    TramoCobertura,
    TurnoAtendido,
    TurnosAtendidosPort,
)
from app.turnos.servicio import Actor, Invalido, NoAutenticado, NoEncontrado, Prohibido

_ADMIN = frozenset({"ADMIN"})
_GESTION = frozenset({"ADMIN", "RECEPCION"})
_MODOS: frozenset[str] = frozenset({"PORCENTAJE", "MONTO"})
_CABECERA_CSV = ("turno_id", "fecha", "paciente_id", "prestacion_id", "monto_centavos")

Reloj = Callable[[], datetime]


class ServicioObrasSociales:
    """Catálogo, coberturas, cálculo de tramos y liquidación por período."""

    def __init__(
        self,
        obras: ObraSocialRepositorio,
        coberturas: CoberturaRepositorio,
        liquidaciones: LiquidacionRepositorio,
        atendidos: TurnosAtendidosPort,
        pacientes: PacienteObraSocialPort,
        prestaciones: PrestacionPrecioPort,
        auditoria: AuditoriaPort,
        *,
        reloj: Reloj | None = None,
    ) -> None:
        self._obras = obras
        self._coberturas = coberturas
        self._liquidaciones = liquidaciones
        self._atendidos = atendidos
        self._pacientes = pacientes
        self._prestaciones = prestaciones
        self._auditoria = auditoria
        self._reloj: Reloj = reloj or (lambda: datetime.now(UTC))

    def _momento(self) -> datetime:
        return self._reloj()

    # ------------------------------------------------------------------
    # Catálogo
    # ------------------------------------------------------------------

    def crear_obra_social(self, actor: Actor, *, nombre: str) -> ObraSocial:
        self._exigir_admin(actor)
        limpio = nombre.strip()
        if not limpio:
            raise Invalido("el nombre de la obra social es obligatorio")
        try:
            creada = self._obras.crear(
                tenant_id=actor.tenant_id, nombre=limpio, ahora=self._momento()
            )
        except ObraSocialDuplicada as exc:
            raise Conflicto(
                CODIGO_OBRA_SOCIAL_DUPLICADA,
                "ya existe una obra social con ese nombre",
            ) from exc
        self._auditar(actor, "OBRA_SOCIAL_CREADA", "obra_social", creada.id, despues={"nombre": limpio})
        return creada

    def listar_obras_sociales(
        self, actor: Actor, *, solo_activas: bool = False
    ) -> list[ObraSocial]:
        self._exigir_lectura(actor)
        return self._obras.listar(tenant_id=actor.tenant_id, solo_activas=solo_activas)

    def cambiar_estado(
        self, actor: Actor, *, obra_social_id: str, activa: bool
    ) -> ObraSocial:
        self._exigir_admin(actor)
        actual = self._obras.obtener(tenant_id=actor.tenant_id, obra_social_id=obra_social_id)
        if actual is None:
            raise NoEncontrado("obra social no encontrada")
        try:
            actualizada = self._obras.cambiar_estado(
                tenant_id=actor.tenant_id,
                obra_social_id=obra_social_id,
                activa=activa,
                ahora=self._momento(),
            )
        except KeyError as exc:
            raise NoEncontrado("obra social no encontrada") from exc
        self._auditar(
            actor,
            "OBRA_SOCIAL_ESTADO",
            "obra_social",
            obra_social_id,
            antes={"activa": actual.activa},
            despues={"activa": actualizada.activa},
        )
        return actualizada

    # ------------------------------------------------------------------
    # Coberturas
    # ------------------------------------------------------------------

    def configurar_cobertura(
        self,
        actor: Actor,
        *,
        obra_social_id: str,
        prestacion_id: str,
        modo: str,
        valor: int,
        tope_centavos: int | None = None,
    ) -> Cobertura:
        self._exigir_admin(actor)
        modo_validado = self._validar_modo(modo)
        self._validar_valor(modo_validado, valor)
        if tope_centavos is not None and tope_centavos < 0:
            raise Invalido("el tope no puede ser negativo")
        if self._obras.obtener(tenant_id=actor.tenant_id, obra_social_id=obra_social_id) is None:
            raise NoEncontrado("obra social no encontrada")
        if self._prestaciones.precio_base(
            tenant_id=actor.tenant_id, prestacion_id=prestacion_id
        ) is None:
            raise NoEncontrado("prestación no encontrada")
        antes = self._coberturas.obtener(
            tenant_id=actor.tenant_id,
            obra_social_id=obra_social_id,
            prestacion_id=prestacion_id,
        )
        cobertura = self._coberturas.upsert(
            tenant_id=actor.tenant_id,
            obra_social_id=obra_social_id,
            prestacion_id=prestacion_id,
            modo=modo_validado,
            valor=valor,
            tope_centavos=tope_centavos,
            ahora=self._momento(),
        )
        self._auditar(
            actor,
            "COBERTURA_CONFIGURADA",
            "cobertura",
            cobertura.id,
            antes=None if antes is None else {"modo": antes.modo, "valor": antes.valor},
            despues={
                "modo": cobertura.modo,
                "valor": cobertura.valor,
                "tope_centavos": cobertura.tope_centavos,
            },
        )
        return cobertura

    def listar_coberturas(
        self, actor: Actor, *, obra_social_id: str | None = None
    ) -> list[Cobertura]:
        self._exigir_lectura(actor)
        return self._coberturas.listar(tenant_id=actor.tenant_id, obra_social_id=obra_social_id)

    def cobertura_para(
        self, *, tenant_id: str, obra_social_id: str, prestacion_id: str
    ) -> Cobertura | None:
        """Lectura interna para el adaptador de C-09 (sin actor)."""
        return self._coberturas.obtener(
            tenant_id=tenant_id,
            obra_social_id=obra_social_id,
            prestacion_id=prestacion_id,
        )

    def preview_cobertura(
        self, actor: Actor, *, paciente_id: str, prestacion_id: str
    ) -> TramoCobertura:
        self._exigir_lectura(actor)
        return self.tramo(
            tenant_id=actor.tenant_id, paciente_id=paciente_id, prestacion_id=prestacion_id
        )

    def tramo(self, *, tenant_id: str, paciente_id: str, prestacion_id: str) -> TramoCobertura:
        if not self._pacientes.existe(tenant_id=tenant_id, paciente_id=paciente_id):
            raise NoEncontrado("paciente no encontrado")
        precio = self._prestaciones.precio_base(
            tenant_id=tenant_id, prestacion_id=prestacion_id
        )
        if precio is None:
            raise NoEncontrado("prestación no encontrada")
        obra_social_id = self._pacientes.obra_social(
            tenant_id=tenant_id, paciente_id=paciente_id
        )
        cobertura = (
            None
            if obra_social_id is None
            else self._coberturas.obtener(
                tenant_id=tenant_id,
                obra_social_id=obra_social_id,
                prestacion_id=prestacion_id,
            )
        )
        cubierto = self._monto_cobertura(precio, cobertura)
        return TramoCobertura(
            precio_base_centavos=precio,
            cobertura_os=cubierto,
            a_cargo_paciente=precio - cubierto,
            origen="CONFIGURADA" if cubierto > 0 else "SIN_COBERTURA",
        )

    # ------------------------------------------------------------------
    # Liquidación
    # ------------------------------------------------------------------

    def generar_liquidacion(
        self,
        actor: Actor,
        *,
        obra_social_id: str,
        desde: date,
        hasta: date,
    ) -> Liquidacion:
        self._exigir_gestion(actor)
        self._validar_periodo(desde, hasta)
        if self._obras.obtener(tenant_id=actor.tenant_id, obra_social_id=obra_social_id) is None:
            raise NoEncontrado("obra social no encontrada")

        existente = self._liquidaciones.buscar(
            tenant_id=actor.tenant_id,
            obra_social_id=obra_social_id,
            desde=desde,
            hasta=hasta,
        )
        if existente is not None and existente.estado == "CERRADA":
            raise Conflicto(
                CODIGO_LIQUIDACION_CERRADA,
                "la liquidación del período ya está cerrada",
            )

        lineas = self._recolectar_lineas(
            tenant_id=actor.tenant_id,
            obra_social_id=obra_social_id,
            desde=desde,
            hasta=hasta,
        )
        if not lineas:
            raise Conflicto(
                CODIGO_SIN_TURNOS,
                "no hay turnos atendidos con cobertura en el período",
            )

        liquidacion = self._persistir(
            tenant_id=actor.tenant_id,
            obra_social_id=obra_social_id,
            desde=desde,
            hasta=hasta,
            lineas=lineas,
        )
        self._auditar(
            actor,
            "LIQUIDACION_GENERADA",
            "liquidacion",
            liquidacion.id,
            despues={
                "obra_social_id": obra_social_id,
                "periodo_desde": desde.isoformat(),
                "periodo_hasta": hasta.isoformat(),
                "total_centavos": liquidacion.total_centavos,
            },
        )
        return liquidacion

    def cerrar_liquidacion(self, actor: Actor, *, liquidacion_id: str) -> Liquidacion:
        self._exigir_gestion(actor)
        actual = self._obtener_detalle(actor.tenant_id, liquidacion_id)
        if actual.estado == "CERRADA":
            raise Conflicto(CODIGO_LIQUIDACION_CERRADA, "la liquidación ya está cerrada")
        if not actual.lineas:
            raise Conflicto(CODIGO_SIN_TURNOS, "la liquidación no tiene líneas")
        cerrada = self._liquidaciones.cerrar(
            tenant_id=actor.tenant_id,
            liquidacion_id=liquidacion_id,
            ahora=self._momento(),
        )
        self._auditar(
            actor,
            "LIQUIDACION_CERRADA",
            "liquidacion",
            liquidacion_id,
            antes={"estado": actual.estado},
            despues={"estado": cerrada.estado, "total_centavos": cerrada.total_centavos},
        )
        return cerrada

    def obtener_liquidacion(self, actor: Actor, *, liquidacion_id: str) -> Liquidacion:
        self._exigir_lectura(actor)
        return self._obtener_detalle(actor.tenant_id, liquidacion_id)

    def listar_liquidaciones(
        self,
        actor: Actor,
        *,
        obra_social_id: str | None = None,
        desde: date | None = None,
        hasta: date | None = None,
    ) -> list[Liquidacion]:
        self._exigir_lectura(actor)
        return self._liquidaciones.listar(
            tenant_id=actor.tenant_id,
            obra_social_id=obra_social_id,
            desde=desde,
            hasta=hasta,
        )

    def exportar_liquidacion_csv(self, actor: Actor, *, liquidacion_id: str) -> str:
        liquidacion = self.obtener_liquidacion(actor, liquidacion_id=liquidacion_id)
        buffer = io.StringIO()
        writer = csv.writer(buffer, lineterminator="\n")
        writer.writerow(_CABECERA_CSV)
        for linea in liquidacion.lineas:
            writer.writerow(
                (
                    linea.turno_id,
                    linea.fecha.isoformat(),
                    linea.paciente_id,
                    linea.prestacion_id,
                    linea.monto_centavos,
                )
            )
        return buffer.getvalue()

    # ------------------------------------------------------------------
    # Internos
    # ------------------------------------------------------------------

    def _recolectar_lineas(
        self, *, tenant_id: str, obra_social_id: str, desde: date, hasta: date
    ) -> list[tuple[TurnoAtendido, int]]:
        pendientes: list[tuple[TurnoAtendido, int]] = []
        for turno in self._atendidos.atendidos(
            tenant_id=tenant_id,
            obra_social_id=obra_social_id,
            desde=desde,
            hasta=hasta,
        ):
            cobertura = self._coberturas.obtener(
                tenant_id=tenant_id,
                obra_social_id=obra_social_id,
                prestacion_id=turno.prestacion_id,
            )
            monto = self._monto_cobertura(turno.precio_base_centavos, cobertura)
            if monto > 0:
                pendientes.append((turno, monto))
        return pendientes

    def _persistir(
        self,
        *,
        tenant_id: str,
        obra_social_id: str,
        desde: date,
        hasta: date,
        lineas: list[tuple[TurnoAtendido, int]],
    ) -> Liquidacion:
        existente = self._liquidaciones.buscar(
            tenant_id=tenant_id, obra_social_id=obra_social_id, desde=desde, hasta=hasta
        )
        if existente is not None:
            return self._liquidaciones.reemplazar_lineas(
                tenant_id=tenant_id, liquidacion_id=existente.id, lineas=lineas
            )
        try:
            creada = self._liquidaciones.crear(
                tenant_id=tenant_id,
                obra_social_id=obra_social_id,
                desde=desde,
                hasta=hasta,
                ahora=self._momento(),
            )
        except LiquidacionDuplicada:
            # Carrera: otro pedido la creó. Se devuelve la existente si sigue en BORRADOR.
            existente = self._liquidaciones.buscar(
                tenant_id=tenant_id,
                obra_social_id=obra_social_id,
                desde=desde,
                hasta=hasta,
            )
            if existente is None:
                raise
            if existente.estado == "CERRADA":
                raise Conflicto(
                    CODIGO_LIQUIDACION_CERRADA,
                    "la liquidación del período ya está cerrada",
                ) from None
            return self._liquidaciones.reemplazar_lineas(
                tenant_id=tenant_id, liquidacion_id=existente.id, lineas=lineas
            )
        return self._liquidaciones.reemplazar_lineas(
            tenant_id=tenant_id, liquidacion_id=creada.id, lineas=lineas
        )

    def _obtener_detalle(self, tenant_id: str, liquidacion_id: str) -> Liquidacion:
        liquidacion = self._liquidaciones.obtener(
            tenant_id=tenant_id, liquidacion_id=liquidacion_id
        )
        if liquidacion is None:
            raise NoEncontrado("liquidación no encontrada")
        return liquidacion

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

    @staticmethod
    def _monto_cobertura(precio_base: int, cobertura: Cobertura | None) -> int:
        if cobertura is None or precio_base <= 0:
            return 0
        if cobertura.modo == "PORCENTAJE":
            bruto = precio_base * cobertura.valor // 100
        else:
            bruto = cobertura.valor
        if cobertura.tope_centavos is not None:
            bruto = min(bruto, cobertura.tope_centavos)
        return max(0, min(bruto, precio_base))

    @staticmethod
    def _validar_modo(modo: str) -> ModoCobertura:
        if modo not in _MODOS:
            raise Invalido("modo de cobertura inválido")
        return cast(ModoCobertura, modo)

    @staticmethod
    def _validar_valor(modo: ModoCobertura, valor: int) -> None:
        if valor <= 0:
            raise Invalido("el valor de la cobertura debe ser positivo")
        if modo == "PORCENTAJE" and not 1 <= valor <= 100:
            raise Invalido("el porcentaje debe estar entre 1 y 100")

    @staticmethod
    def _validar_periodo(desde: date, hasta: date) -> None:
        if desde > hasta:
            raise Invalido("el período es inválido: desde es posterior a hasta")

    @staticmethod
    def _exigir_admin(actor: Actor) -> None:
        if actor.rol == "PACIENTE":
            raise NoAutenticado("sesión interna requerida")
        if actor.rol not in _ADMIN:
            raise Prohibido("sólo un administrador configura obras sociales")

    @staticmethod
    def _exigir_gestion(actor: Actor) -> None:
        if actor.rol == "PACIENTE":
            raise NoAutenticado("sesión interna requerida")
        if actor.rol not in _GESTION:
            raise Prohibido("rol sin permiso para liquidar")

    @staticmethod
    def _exigir_lectura(actor: Actor) -> None:
        if actor.rol == "PACIENTE":
            raise NoAutenticado("sesión interna requerida")
        if actor.rol not in _GESTION:
            raise Prohibido("rol sin permiso para leer obras sociales")

