# mcp-kong-deploy-http: HTTP-transport MCP server for Kong API Gateway.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    KONG_MCP_HOST=0.0.0.0 \
    KONG_MCP_PORT=8770

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# OpenAPI specs and other working files are mounted under /opt/kong at runtime.
RUN mkdir -p /opt/kong

COPY server.py config.properties ./

EXPOSE 8770
CMD ["python", "server.py"]
