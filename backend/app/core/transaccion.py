"""Unidad de trabajo SQLAlchemy compartida — C-10 §5 (M4).

La aceptación de C-09 y la escritura de caja (movimiento, pendiente o cuenta por
cobrar OS) tienen que vivir en la **misma** unidad de trabajo: si la caja falla,
C-09 no persiste la aceptación (D6.7/M4).

El patrón es de propiedad por anidamiento:

- la unidad de trabajo **más externa** es la dueña: commitea en éxito y hace
  `rollback` en error;
- las que se abren adentro (el adaptador de caja dentro de C-09) se **unen** y
  sólo hacen `flush`;
- si algo falla, la excepción propaga y la dueña revierte todo.

La propiedad se lleva por profundidad en `Session.info`, no por
`Session.in_transaction()`: C-09 lee el presupuesto **antes** de abrir su unidad
de trabajo, y esa lectura abre una transacción implícita que no debe convertir
a la dueña en invitada.
"""
from __future__ import annotations

from types import TracebackType

from sqlalchemy.orm import Session

__all__ = ["TransaccionSQL"]

_CLAVE_PROFUNDIDAD = "uow_sql_profundidad"


class TransaccionSQL:
    """Commit si es la unidad de trabajo más externa; `flush` si está anidada.

    Debe entrarse con el mismo `Session` en todas las capas de un mismo caso de
    uso. Una transacción implícita abierta por una lectura previa se adopta y se
    cierra con el commit de la dueña.
    """

    def __init__(self, session: Session) -> None:
        self._session = session
        self._propia = False

    @property
    def session(self) -> Session:
        """Sesión cubierta por la unidad de trabajo."""
        return self._session

    def __enter__(self) -> TransaccionSQL:
        profundidad = int(self._session.info.get(_CLAVE_PROFUNDIDAD, 0))
        self._propia = profundidad == 0
        self._session.info[_CLAVE_PROFUNDIDAD] = profundidad + 1
        if self._propia and not self._session.in_transaction():
            self._session.begin()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        profundidad = int(self._session.info.get(_CLAVE_PROFUNDIDAD, 1)) - 1
        self._session.info[_CLAVE_PROFUNDIDAD] = max(profundidad, 0)
        if not self._propia:
            # Invitada: no commitea ni revierte; la dueña decide.
            if exc_type is None:
                self._session.flush()
            return
        if exc_type is not None:
            self._session.rollback()
            return
        self._session.flush()
        self._session.commit()
