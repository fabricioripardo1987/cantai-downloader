FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1
ENV POT_PROVIDER_URL=http://127.0.0.1:4416

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    ca-certificates \
    curl \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Node 22 para o bgutil provider
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get update \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -U pip \
    && pip install --no-cache-dir -r requirements.txt

# Servidor HTTP do PO Token
RUN git clone --single-branch --branch 1.3.1 https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git /opt/bgutil-ytdlp-pot-provider \
    && cd /opt/bgutil-ytdlp-pot-provider/server \
    && npm ci \
    && npx tsc

COPY server.py .

EXPOSE 8080

CMD sh -c 'cd /opt/bgutil-ytdlp-pot-provider/server && node build/main.js --port 4416 & exec gunicorn server:app --bind 0.0.0.0:${PORT:-8080} --workers 1 --threads 4 --timeout 240'
