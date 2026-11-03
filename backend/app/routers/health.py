"""Foundation health router."""
from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter(tags=["foundation"])

HEALTH_SERVICE = "turnos-api"


class HealthOut(BaseModel):
    status: str
    service: str
    version: str


@router.get("/api/health", response_model=HealthOut)
def health(request: Request) -> HealthOut:
    settings = request.app.state.settings
    return HealthOut(status="UP", service=settings.app_name, version=settings.app_version)
