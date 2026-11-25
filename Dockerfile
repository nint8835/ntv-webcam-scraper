FROM ghcr.io/astral-sh/uv:python3.15-alpine

RUN apk add --no-cache ffmpeg
WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen
ENV PATH="/app/.venv/bin:$PATH"

COPY . .

CMD ["python", "-m", "ntvwebcamscraper", "run"]
