"""Registro del barrido de expiraciones en el runner de workers — C-11 §7.9.

Sin este wiring una seña vencida **no libera el turno** y RN-SE-01 no se cumple
en producción: es una dependencia operativa declarada del change (F-15), no un
detalle del dominio.

El dominio (`ServicioSenasExpulsion`) exige `tenant_id` y un reloj inyectado; el
runner es el que itera tenants y aporta el intervalo. El intervalo es
**configuración del runner** (DD-08: cron/Redis), no del dominio, así que C-11 no
inventa un número: se recibe como parámetro obligatorio y se expone para que el
scheduler real lo consuma en el follow-up de infraestructura.

`RegistroJobs` es el seam mínimo del scheduler: en producción lo implementa el
runner de workers; en tests basta con registrar y ejecutar el job en proceso.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime

from app.senas.puertos import Reloj, Sena
from app.senas.worker import ServicioSenasExpulsion

__all__ = ["JOB_EXPIRACIONES", "RegistroJobs", "RunnerSenas"]

JOB_EXPIRACIONES = "senas:expiraciones"


class RegistroJobs:
    """Registro in-process de jobs (seam del scheduler de DD-08)."""

    def __init__(self) -> None:
        self._jobs: dict[str, Callable[[], object]] = {}

    def registrar(self, nombre: str, job: Callable[[], object]) -> None:
        self._jobs[nombre] = job

    def ejecutar(self, nombre: str) -> object:
        return self._jobs[nombre]()

    def nombres(self) -> tuple[str, ...]:
        return tuple(sorted(self._jobs))


class RunnerSenas:
    """Registra y ejecuta el barrido de expiraciones por tenant."""

    def __init__(
        self,
        worker: ServicioSenasExpulsion,
        tenants: Callable[[], Sequence[str]],
        *,
        intervalo_s: int,
        registro: RegistroJobs | None = None,
        reloj: Reloj | None = None,
    ) -> None:
        if intervalo_s <= 0:
            raise ValueError("el intervalo del barrido debe ser positivo")
        self._worker = worker
        self._tenants = tenants
        self._intervalo_s = intervalo_s
        self._registro = registro if registro is not None else RegistroJobs()
        self._reloj = reloj

    @property
    def intervalo_s(self) -> int:
        """Intervalo configurado del barrido (lo consume el scheduler)."""
        return self._intervalo_s

    @property
    def registro(self) -> RegistroJobs:
        return self._registro

    def registrar(self) -> str:
        """Registra `senas:expiraciones` y devuelve el nombre del job."""
        self._registro.registrar(JOB_EXPIRACIONES, self.ejecutar)
        return JOB_EXPIRACIONES

    def ejecutar(self, ahora: datetime | None = None) -> list[Sena]:
        """Corre el barrido en cada tenant; devuelve todas las señas liberadas."""
        momento = ahora
        if momento is None and self._reloj is not None:
            momento = self._reloj()
        liberadas: list[Sena] = []
        for tenant_id in self._tenants():
            liberadas.extend(
                self._worker.procesar_expiraciones(tenant_id=tenant_id, ahora=momento)
            )
        return liberadas
