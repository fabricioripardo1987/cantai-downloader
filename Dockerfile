FROM python:3.12-slim

# Dependências do sistema: ffmpeg (extrair áudio), nodejs (PO Token provider), git
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        curl \
        git \
        ca-certificates \
        gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# PO Token provider (bgutil) — roda em :4416
RUN git clone https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git /opt/bgutil \
    && cd /opt/bgutil/server \
    && npm install \
    && npx tsc

# App
COPY . .

ENV PORT=8080
EXPOSE 8080

# Sobe provider em background e Gunicorn em foreground
CMD sh -c "node /opt/bgutil/server/build/main.js & \
           gunicorn --bind 0.0.0.0:${PORT} --workers 2 --threads 4 --timeout 300 server:app"
