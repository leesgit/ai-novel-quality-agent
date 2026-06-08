# adk web (QualityAnalyst) — Python + Node (for npx @arizeai/phoenix-mcp)
FROM python:3.11-slim

# Node.js for the phoenix-mcp stdio server (npx), plus build deps for Pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
      curl ca-certificates gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python deps (ADK + MCP). Pillow for deterministic continuity metrics.
COPY requirements-adk.txt .
RUN pip install --no-cache-dir -r requirements-adk.txt Pillow

# Pre-fetch the partner MCP server so cold start doesn't pull from npm at request time
RUN npm install -g @arizeai/phoenix-mcp@latest

# App code (agents_dir entry point loads adk/ package)
COPY adk ./adk
COPY agents_dir ./agents_dir
COPY assets ./assets

ENV PYTHONPATH=/app \
    PHOENIX_BASE_URL=http://phoenix:6006 \
    PORT=8000

EXPOSE 8000

# adk web binds the QualityAnalyst agent. Host 0.0.0.0 so the container is reachable.
CMD ["python", "-m", "google.adk.cli", "web", "agents_dir", "--host", "0.0.0.0", "--port", "8000"]
# (Phoenix is seeded by the separate `seeder` service in docker-compose.yml.)
