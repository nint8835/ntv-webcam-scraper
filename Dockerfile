FROM ghcr.io/astral-sh/uv:python3.12-alpine

RUN apk add --no-cache ffmpeg --repository=https://dl-cdn.alpinelinux.org/alpine/latest-stable/community
WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen
ENV PATH="/app/.venv/bin:$PATH"

COPY . .

CMD ["python", "-m", "ntvwebcamscraper", "run"]
