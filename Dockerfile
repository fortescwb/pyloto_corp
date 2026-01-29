FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYLOTO_DOCS_DIR=/app/docs

WORKDIR /app

COPY pyproject.toml README.md /app/
COPY src /app/src
COPY docs /app/docs

RUN pip install --upgrade pip \
  && pip install .

EXPOSE 8080

CMD ["sh", "-c", "uvicorn pyloto_corp.api.app_async:app --host 0.0.0.0 --port ${PORT:-8080}"]
