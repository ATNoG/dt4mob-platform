FROM alpine:edge
COPY --from=docker.io/astral/uv:latest /uv /uvx /bin/

RUN apk add --no-cache python3 && \
    ln -sf python3 /usr/bin/python

WORKDIR /app

COPY . .

RUN uv sync

CMD ["uv", "run", "main.py"]
