FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --no-cache-dir yt-dlp flask gunicorn

COPY server.py .

ENV PORT=8080

CMD gunicorn -b 0.0.0.0:$PORT -w 2 --threads 4 -t 300 server:app
