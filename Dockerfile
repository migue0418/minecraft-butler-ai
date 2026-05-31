FROM python:3.13-slim AS backend-runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# ffmpeg requerido por faster-whisper para decodificar audio (webm, mp3, ogg, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install production dependencies only (excludes [dependency-groups] dev)
COPY ./pyproject.toml ./uv.lock ./
RUN uv sync --frozen --no-dev --no-cache

COPY ./ /app/./

ENV PATH="/app/./.venv/bin:$PATH"

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
