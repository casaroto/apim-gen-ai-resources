# mcp-spectral-api-tests: stdio MCP server bundling Spectral and OWASP API rules.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SPECTRAL_DEFAULT_API_PATH=/app/assets/branchesmock_1.0.0.yaml \
    SPECTRAL_MCP_TRANSPORT=stdio

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates nodejs npm \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY package.json package-lock.json ./
RUN npm ci

COPY .spectral.yaml server.py README.md ./
COPY assets/ ./assets/

CMD ["python", "server.py"]
