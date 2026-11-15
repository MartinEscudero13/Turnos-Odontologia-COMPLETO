"""Tests de dominio de C-12 con adaptadores en memoria (sin DB).

Datos ficticios (RN-GL-03): tenant T1/T2, pacientes P1/P2, prestaciones con
precio base en centavos y coberturas declaradas. El reloj es fijo.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

import pytest

from app.obras_sociales.puertos import (
    CODIGO_LIQUIDACION_CERRADA,
    CODIGO_OBRA_SOCIAL_DUPLICADA,
    CODIGO_SIN_TURNOS,
    AuditoriaMemoria,
    CoberturaMemoria,
    Conflicto,
    LiquidacionMemoria,
    ObraSocialMemoria,
    PacienteObraSocialMemoria,
    PrestacionPrecioMemoria,
    TramoCobertura,
    TurnoAtendido,
    TurnosAtendidosMemoria,
)
from app.obras_sociales.servicio import ServicioObrasSociales
from app.turnos.servicio import Actor, Invalido, NoEncontrado, Prohibido

TZ = timezone(timedelta(hours=-3))
AHORA = datetime(2026, 11, 15, 9, 0, tzinfo=TZ)
T1 = "a0000000-0000-4000-8000-000000000001"
T2 = "a0000000-0000-4000-8000-000000000002"
P1 = "paciente-1"
P2 = "paciente-2"
CONSULTA = "prestacion-consulta"
LIMPIEZA = "prestacion-limpieza"
PRECIO_CONSULTA = 10000
PRECIO_LIMPIEZA = 15000


def actor(rol: str = "ADMIN", tenant: str = T1, user_id: str = "usuario-1") -> Actor:
    return Actor(tenant_id=tenant, rol=rol, user_id=user_id)


@dataclass
class Harness:
    svc: ServicioObrasSociales
    obras: ObraSocialMemoria
    coberturas: CoberturaMemoria
    liquidaciones: LiquidacionMemoria
    atendidos: TurnosAtendidosMemoria
    pacientes: PacienteObraSocialMemoria
    prestaciones: PrestacionPrecioMemoria
    auditoria: AuditoriaMemoria

    def seed(self) -> dict[str, str]:
        """OS Norte (50% consulta, tope 4000; monto 8000 limpieza) y OS Sur (30% consulta)."""
        norte = self.svc.crear_obra_social(actor(), nombre="OS Norte")
        sur = self.svc.crear_obra_social(actor(), nombre="OS Sur")
        self.svc.configurar_cobertura(
            actor(),
            obra_social_id=norte.id,
            prestacion_id=CONSULTA,
            modo="PORCENTAJE",
            valor=50,
            tope_centavos=4000,
        )
        self.svc.configurar_cobertura(
            actor(),
            obra_social_id=norte.id,
            prestacion_id=LIMPIEZA,
            modo="MONTO",
            valor=8000,
        )
        self.svc.configurar_cobertura(
            actor(),
            obra_social_id=sur.id,
            prestacion_id=CONSULTA,
            modo="PORCENTAJE",
            valor=30,
        )
        self.pacientes.agregar(T1, P1, norte.id)
        self.pacientes.agregar(T1, P2, sur.id)
        return {"norte": norte.id, "sur": sur.id}


def nuevo_harness() -> Harness:
    obras = ObraSocialMemoria()
    coberturas = CoberturaMemoria()
    liquidaciones = LiquidacionMemoria()
    atendidos = TurnosAtendidosMemoria()
    pacientes = PacienteObraSocialMemoria()
    prestaciones = PrestacionPrecioMemoria()
    prestaciones.agregar(T1, CONSULTA, PRECIO_CONSULTA)
    prestaciones.agregar(T1, LIMPIEZA, PRECIO_LIMPIEZA)
    auditoria = AuditoriaMemoria()
    svc = ServicioObrasSociales(
        obras,
        coberturas,
        liquidaciones,
        atendidos,
        pacientes,
        prestaciones,
        auditoria,
        reloj=lambda: AHORA,
    )
    return Harness(
        svc=svc,
        obras=obras,
        coberturas=coberturas,
        liquidaciones=liquidaciones,
        atendidos=atendidos,
        pacientes=pacientes,
        prestaciones=prestaciones,
        auditoria=auditoria,
    )


def sembrar_atendido(
    h: Harness,
    *,
    turno_id: str,
    paciente_id: str,
    prestacion_id: str,
    obra_social_id: str,
    inicio: datetime,
    precio: int,
    tenant: str = T1,
) -> None:
    h.atendidos.agregar(
        TurnoAtendido(
            turno_id=turno_id,
            paciente_id=paciente_id,
            prestacion_id=prestacion_id,
            inicio=inicio,
            precio_base_centavos=precio,
        ),
        tenant_id=tenant,
        obra_social_id=obra_social_id,
    )


# ---------------------------------------------------------------------------
# Catálogo
# ---------------------------------------------------------------------------


def test_crear_y_listar_obras_sociales() -> None:
    h = nuevo_harness()

    creada = h.svc.crear_obra_social(actor(), nombre="  OS Norte  ")
    assert creada.nombre == "OS Norte"
    assert creada.activa is True

    listado = h.svc.listar_obras_sociales(actor())
    assert [obra.nombre for obra in listado] == ["OS Norte"]


def test_obra_social_duplicada_es_conflicto() -> None:
    h = nuevo_harness()
    h.svc.crear_obra_social(actor(), nombre="OS Norte")

    with pytest.raises(Conflicto) as excinfo:
        h.svc.crear_obra_social(actor(), nombre="OS Norte")

    assert excinfo.value.codigo_dominio == CODIGO_OBRA_SOCIAL_DUPLICADA
    assert len(h.svc.listar_obras_sociales(actor())) == 1


def test_recepcion_no_configura_catalogo() -> None:
    h = nuevo_harness()

    with pytest.raises(Prohibido):
        h.svc.crear_obra_social(actor("RECEPCION"), nombre="OS Norte")


def test_cambiar_estado_se_audita() -> None:
    h = nuevo_harness()
    obra = h.svc.crear_obra_social(actor(), nombre="OS Norte")

    desactivada = h.svc.cambiar_estado(actor(), obra_social_id=obra.id, activa=False)

    assert desactivada.activa is False
    assert [e.accion for e in h.auditoria.entradas] == [
        "OBRA_SOCIAL_CREADA",
        "OBRA_SOCIAL_ESTADO",
    ]


# ---------------------------------------------------------------------------
# Coberturas
# ---------------------------------------------------------------------------


def test_cobertura_upsert_y_listado() -> None:
    h = nuevo_harness()
    obra = h.svc.crear_obra_social(actor(), nombre="OS Norte")

    primera = h.svc.configurar_cobertura(
        actor(),
        obra_social_id=obra.id,
        prestacion_id=CONSULTA,
        modo="PORCENTAJE",
        valor=50,
    )
    segunda = h.svc.configurar_cobertura(
        actor(),
        obra_social_id=obra.id,
        prestacion_id=CONSULTA,
        modo="PORCENTAJE",
        valor=30,
    )

    assert primera.id == segunda.id
    listado = h.svc.listar_coberturas(actor())
    assert len(listado) == 1
    assert listado[0].valor == 30
    assert listado[0].validada_en_vivo is False


@pytest.mark.parametrize("valor", [0, 101, -5])
def test_porcentaje_invalido_no_persiste(valor: int) -> None:
    h = nuevo_harness()
    obra = h.svc.crear_obra_social(actor(), nombre="OS Norte")

    with pytest.raises(Invalido):
        h.svc.configurar_cobertura(
            actor(),
            obra_social_id=obra.id,
            prestacion_id=CONSULTA,
            modo="PORCENTAJE",
            valor=valor,
        )

    assert h.svc.listar_coberturas(actor()) == []


def test_monto_y_tope_invalidos() -> None:
    h = nuevo_harness()
    obra = h.svc.crear_obra_social(actor(), nombre="OS Norte")

    with pytest.raises(Invalido):
        h.svc.configurar_cobertura(
            actor(), obra_social_id=obra.id, prestacion_id=CONSULTA, modo="MONTO", valor=0
        )
    with pytest.raises(Invalido):
        h.svc.configurar_cobertura(
            actor(),
            obra_social_id=obra.id,
            prestacion_id=CONSULTA,
            modo="MONTO",
            valor=100,
            tope_centavos=-1,
        )


def test_cobertura_de_prestacion_inexistente_es_404() -> None:
    h = nuevo_harness()
    obra = h.svc.crear_obra_social(actor(), nombre="OS Norte")

    with pytest.raises(NoEncontrado):
        h.svc.configurar_cobertura(
            actor(),
            obra_social_id=obra.id,
            prestacion_id="prestacion-fantasma",
            modo="PORCENTAJE",
            valor=50,
        )


# ---------------------------------------------------------------------------
# Tramo
# ---------------------------------------------------------------------------


def test_tramo_porcentaje_con_tope() -> None:
    h = nuevo_harness()
    ids = h.seed()
    h.coberturas.upsert(
        tenant_id=T1,
        obra_social_id=ids["norte"],
        prestacion_id=CONSULTA,
        modo="PORCENTAJE",
        valor=80,
        tope_centavos=7000,
        ahora=AHORA,
    )

    tramo = h.svc.preview_cobertura(actor(), paciente_id=P1, prestacion_id=CONSULTA)

    assert tramo == TramoCobertura(
        precio_base_centavos=10000,
        cobertura_os=7000,
        a_cargo_paciente=3000,
        origen="CONFIGURADA",
        validada_en_vivo=False,
    )


def test_tramo_monto_capeado_por_precio() -> None:
    h = nuevo_harness()
    ids = h.seed()
    h.prestaciones.agregar(T1, CONSULTA, 5000)
    h.coberturas.upsert(
        tenant_id=T1,
        obra_social_id=ids["norte"],
        prestacion_id=CONSULTA,
        modo="MONTO",
        valor=8000,
        tope_centavos=None,
        ahora=AHORA,
    )

    tramo = h.svc.preview_cobertura(actor(), paciente_id=P1, prestacion_id=CONSULTA)

    assert (tramo.cobertura_os, tramo.a_cargo_paciente) == (5000, 0)


def test_tramo_sin_obra_social_paga_todo() -> None:
    h = nuevo_harness()
    h.seed()
    h.pacientes.agregar(T1, "paciente-sin-os", None)

    tramo = h.svc.preview_cobertura(
        actor(), paciente_id="paciente-sin-os", prestacion_id=CONSULTA
    )

    assert tramo.cobertura_os == 0
    assert tramo.a_cargo_paciente == PRECIO_CONSULTA
    assert tramo.origen == "SIN_COBERTURA"


def test_tramo_sin_cobertura_configurada() -> None:
    h = nuevo_harness()
    h.seed()
    h.prestaciones.agregar(T1, "prestacion-sin-cobertura", 4000)

    tramo = h.svc.preview_cobertura(
        actor(), paciente_id=P1, prestacion_id="prestacion-sin-cobertura"
    )

    assert tramo.cobertura_os == 0
    assert tramo.a_cargo_paciente == 4000


def test_preview_paciente_inexistente_es_404() -> None:
    h = nuevo_harness()
    h.seed()

    with pytest.raises(NoEncontrado):
        h.svc.preview_cobertura(
            actor(), paciente_id="paciente-fantasma", prestacion_id=CONSULTA
        )


# ---------------------------------------------------------------------------
# Liquidación
# ---------------------------------------------------------------------------


def test_liquidacion_agrupa_solo_atendidos_con_cobertura() -> None:
    h = nuevo_harness()
    ids = h.seed()
    desde = date(2026, 11, 1)
    hasta = date(2026, 12, 1)
    sembrar_atendido(
        h, turno_id="t-1", paciente_id=P1, prestacion_id=CONSULTA,
        obra_social_id=ids["norte"], inicio=datetime(2026, 11, 3, 10, tzinfo=TZ),
        precio=PRECIO_CONSULTA,
    )
    sembrar_atendido(
        h, turno_id="t-2", paciente_id=P1, prestacion_id=LIMPIEZA,
        obra_social_id=ids["norte"], inicio=datetime(2026, 11, 4, 10, tzinfo=TZ),
        precio=PRECIO_LIMPIEZA,
    )
    # Otra OS: no entra en la liquidación de Norte.
    sembrar_atendido(
        h, turno_id="t-3", paciente_id=P2, prestacion_id=CONSULTA,
        obra_social_id=ids["sur"], inicio=datetime(2026, 11, 5, 10, tzinfo=TZ),
        precio=PRECIO_CONSULTA,
    )

    liquidacion = h.svc.generar_liquidacion(
        actor(), obra_social_id=ids["norte"], desde=desde, hasta=hasta
    )

    assert [linea.turno_id for linea in liquidacion.lineas] == ["t-1", "t-2"]
    assert [linea.monto_centavos for linea in liquidacion.lineas] == [4000, 8000]
    assert liquidacion.total_centavos == 12000
    assert liquidacion.estado == "BORRADOR"


def test_liquidacion_excluye_fuera_de_periodo() -> None:
    h = nuevo_harness()
    ids = h.seed()
    sembrar_atendido(
        h, turno_id="t-fuera", paciente_id=P1, prestacion_id=CONSULTA,
        obra_social_id=ids["norte"], inicio=datetime(2026, 12, 2, 10, tzinfo=TZ),
        precio=PRECIO_CONSULTA,
    )
    with pytest.raises(Conflicto) as excinfo:
        h.svc.generar_liquidacion(
            actor(), obra_social_id=ids["norte"], desde=date(2026, 11, 1), hasta=date(2026, 12, 1)
        )
    assert excinfo.value.codigo_dominio == CODIGO_SIN_TURNOS

def test_liquidacion_sin_elegibles_es_conflicto() -> None:
    h = nuevo_harness()
    ids = h.seed()
    with pytest.raises(Conflicto) as excinfo:
        h.svc.generar_liquidacion(
            actor(), obra_social_id=ids["norte"], desde=date(2026, 11, 1), hasta=date(2026, 12, 1)
        )
    assert excinfo.value.codigo_dominio == CODIGO_SIN_TURNOS
    assert h.svc.listar_liquidaciones(actor()) == []


def test_regenerar_borrador_reemplaza_lineas() -> None:
    h = nuevo_harness()
    ids = h.seed()
    desde, hasta = date(2026, 11, 1), date(2026, 12, 1)
    sembrar_atendido(
        h, turno_id="t-1", paciente_id=P1, prestacion_id=CONSULTA,
        obra_social_id=ids["norte"], inicio=datetime(2026, 11, 3, 10, tzinfo=TZ),
        precio=PRECIO_CONSULTA,
    )
    primera = h.svc.generar_liquidacion(
        actor(), obra_social_id=ids["norte"], desde=desde, hasta=hasta
    )
    sembrar_atendido(
        h, turno_id="t-2", paciente_id=P1, prestacion_id=LIMPIEZA,
        obra_social_id=ids["norte"], inicio=datetime(2026, 11, 4, 10, tzinfo=TZ),
        precio=PRECIO_LIMPIEZA,
    )

    segunda = h.svc.generar_liquidacion(
        actor(), obra_social_id=ids["norte"], desde=desde, hasta=hasta
    )

    assert segunda.id == primera.id
    assert len(segunda.lineas) == 2
    assert segunda.total_centavos == 12000


def test_cerrar_es_inmutable() -> None:
    h = nuevo_harness()
    ids = h.seed()
    desde, hasta = date(2026, 11, 1), date(2026, 12, 1)
    sembrar_atendido(
        h, turno_id="t-1", paciente_id=P1, prestacion_id=CONSULTA,
        obra_social_id=ids["norte"], inicio=datetime(2026, 11, 3, 10, tzinfo=TZ),
        precio=PRECIO_CONSULTA,
    )
    liquidacion = h.svc.generar_liquidacion(
        actor(), obra_social_id=ids["norte"], desde=desde, hasta=hasta
    )

    cerrada = h.svc.cerrar_liquidacion(actor(), liquidacion_id=liquidacion.id)
    assert cerrada.estado == "CERRADA"
    assert cerrada.cerrada_en is not None

    with pytest.raises(Conflicto) as excinfo:
        h.svc.generar_liquidacion(
            actor(), obra_social_id=ids["norte"], desde=desde, hasta=hasta
        )
    assert excinfo.value.codigo_dominio == CODIGO_LIQUIDACION_CERRADA

    with pytest.raises(Conflicto):
        h.svc.cerrar_liquidacion(actor(), liquidacion_id=liquidacion.id)


def test_odontologo_no_liquida() -> None:
    h = nuevo_harness()
    ids = h.seed()

    with pytest.raises(Prohibido):
        h.svc.generar_liquidacion(
            actor("ODONTOLOGO"), obra_social_id=ids["norte"], desde=date(2026, 11, 1),
            hasta=date(2026, 12, 1),
        )


def test_aislamiento_entre_tenants() -> None:
    h = nuevo_harness()
    ids = h.seed()
    desde, hasta = date(2026, 11, 1), date(2026, 12, 1)
    sembrar_atendido(
        h, turno_id="t-1", paciente_id=P1, prestacion_id=CONSULTA,
        obra_social_id=ids["norte"], inicio=datetime(2026, 11, 3, 10, tzinfo=TZ),
        precio=PRECIO_CONSULTA,
    )
    liquidacion = h.svc.generar_liquidacion(
        actor(), obra_social_id=ids["norte"], desde=desde, hasta=hasta
    )

    assert h.svc.listar_obras_sociales(actor(tenant=T2)) == []
    assert h.svc.listar_liquidaciones(actor(tenant=T2)) == []
    with pytest.raises(NoEncontrado):
        h.svc.obtener_liquidacion(actor(tenant=T2), liquidacion_id=liquidacion.id)


# ---------------------------------------------------------------------------
# Exportación y auditoría
# ---------------------------------------------------------------------------


def test_exportar_csv_con_centavos_enteros() -> None:
    h = nuevo_harness()
    ids = h.seed()
    desde, hasta = date(2026, 11, 1), date(2026, 12, 1)
    for indice, (prestacion, precio) in enumerate(
        ((CONSULTA, PRECIO_CONSULTA), (LIMPIEZA, PRECIO_LIMPIEZA)), start=1
    ):
        sembrar_atendido(
            h, turno_id=f"t-{indice}", paciente_id=P1, prestacion_id=prestacion,
            obra_social_id=ids["norte"],
            inicio=datetime(2026, 11, indice + 2, 10, tzinfo=TZ), precio=precio,
        )
    liquidacion = h.svc.generar_liquidacion(
        actor(), obra_social_id=ids["norte"], desde=desde, hasta=hasta
    )

    csv_texto = h.svc.exportar_liquidacion_csv(actor(), liquidacion_id=liquidacion.id)
    lineas = csv_texto.strip().splitlines()

    assert lineas[0] == "turno_id,fecha,paciente_id,prestacion_id,monto_centavos"
    assert len(lineas) == 3
    assert lineas[1].split(",")[-1] == "4000"
    assert lineas[2].split(",")[-1] == "8000"


def test_auditoria_solo_de_exitos() -> None:
    h = nuevo_harness()
    ids = h.seed()
    desde, hasta = date(2026, 11, 1), date(2026, 12, 1)
    with pytest.raises(Conflicto):
        h.svc.generar_liquidacion(
            actor(), obra_social_id=ids["norte"], desde=desde, hasta=hasta
        )
    acciones = [entrada.accion for entrada in h.auditoria.entradas]
    assert "LIQUIDACION_GENERADA" not in acciones

    sembrar_atendido(
        h, turno_id="t-1", paciente_id=P1, prestacion_id=CONSULTA,
        obra_social_id=ids["norte"], inicio=datetime(2026, 11, 3, 10, tzinfo=TZ),
        precio=PRECIO_CONSULTA,
    )
    liquidacion = h.svc.generar_liquidacion(
        actor(), obra_social_id=ids["norte"], desde=desde, hasta=hasta
    )
    h.svc.cerrar_liquidacion(actor(), liquidacion_id=liquidacion.id)

    acciones = [entrada.accion for entrada in h.auditoria.entradas]
    assert acciones[-2:] == ["LIQUIDACION_GENERADA", "LIQUIDACION_CERRADA"]
    assert all(entrada.tenant_id == T1 for entrada in h.auditoria.entradas)


def test_periodo_invalido_es_422() -> None:
    h = nuevo_harness()
    ids = h.seed()

    with pytest.raises(Invalido):
        h.svc.generar_liquidacion(
            actor(), obra_social_id=ids["norte"], desde=date(2026, 12, 1),
            hasta=date(2026, 11, 1),
        )
