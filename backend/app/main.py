"""Uvicorn entrypoint for local and container starts."""
from app.app import create_app

app = create_app()
