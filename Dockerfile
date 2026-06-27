FROM python:3.12-slim
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir yt-dlp flask gunicorn
WORKDIR /app
COPY server.py .
CMD gunicorn -b 0.0.0.0:$PORT -t 300 server:app

FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN pip install --no-cache-dir flask yt-dlp gunicorn

COPY server.py .

ENV PORT=8080
CMD gunicorn -b 0.0.0.0:$PORT -t 300 server:app
