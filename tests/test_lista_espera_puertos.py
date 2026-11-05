"""Task 2.1 — puertos y adaptadores en memoria: RLS lógico scoped por tenant."""
from __future__ import annotations

import pytest
from conftest import T1, T2, dt

from app.lista_espera.puertos import EntradaDuplicada, ListaEsperaMemoria, OfertaMemoria


def test_repositorio_memoria_scoped_por_tenant():
    repo = ListaEsperaMemoria()
    e = repo.alta(tenant_id=T1, paciente_id="paciente-1", prestacion_id="PREST-30", ahora=dt(hora=9))

    # alta en T1 es visible en T1…
    assert repo.listar(tenant_id=T1) == [e]
    # …pero no en T2 (RLS lógico).
    assert repo.listar(tenant_id=T2) == []
    assert repo.obtener(tenant_id=T2, entrada_id=e.id) is None
    assert repo.obtener(tenant_id=T1, entrada_id=e.id) == e


def test_alta_duplicada_activa_levanta_entrada_duplicada():
    repo = ListaEsperaMemoria()
    repo.alta(tenant_id=T1, paciente_id="paciente-1", prestacion_id="PREST-30", ahora=dt(hora=9))
    with pytest.raises(EntradaDuplicada):
        repo.alta(tenant_id=T1, paciente_id="paciente-1", prestacion_id="PREST-30", ahora=dt(hora=9))
    # otra prestación sí es una entrada distinta.
    repo.alta(tenant_id=T1, paciente_id="paciente-1", prestacion_id="PREST-45", ahora=dt(hora=9))
    assert len(repo.listar(tenant_id=T1)) == 2


def test_ofertas_memoria_scoped_por_tenant():
    repo = OfertaMemoria()
    o = repo.crear(
        tenant_id=T1,
        entrada_id="entrada-1",
        hueco_turno_id="turno-1",
        expira_at=dt(hora=12),
        token="tok-1",
    )
    assert repo.por_token(tenant_id=T1, token="tok-1") == o
    assert repo.por_token(tenant_id=T2, token="tok-1") is None
    assert repo.pendientes(tenant_id=T2) == []
