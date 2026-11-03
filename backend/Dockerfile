# syntax=docker/dockerfile:1.7
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY backend/requirements.txt ./requirements.txt
RUN pip install --target=/install -r requirements.txt

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/usr/local/lib/python3.12/site-packages

RUN groupadd --gid 10001 turnos && useradd --uid 10001 --gid turnos --no-create-home --shell /usr/sbin/nologin turnos
WORKDIR /app
COPY --from=builder /install /usr/local/lib/python3.12/site-packages
COPY backend/app ./app
COPY backend/alembic ./alembic
COPY backend/alembic.ini ./alembic.ini
USER turnos
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --retries=5 --start-period=10s \
  CMD python -c "from urllib.request import urlopen; urlopen('http://127.0.0.1:8000/api/health', timeout=2).read()"
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
