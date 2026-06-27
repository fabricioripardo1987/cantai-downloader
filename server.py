import os
import shutil
import tempfile
import traceback
from pathlib import Path

from flask import Flask, request, jsonify, send_file
import yt_dlp

app = Flask(__name__)

COOKIES_PATH = None
COOKIES_ERROR = None


def load_cookies():
    raw = os.environ.get("YT_COOKIES", "").strip()
    if not raw:
        return None

    # Caso o Railway salve quebras de linha como texto "\n"
    if "\\n" in raw and "\n" not in raw:
        raw = raw.replace("\\n", "\n")

    path = "/tmp/cookies.txt"
    with open(path, "w", encoding="utf-8") as f:
        f.write(raw)
        if not raw.endswith("\n"):
            f.write("\n")

    return path


try:
    COOKIES_PATH = load_cookies()
except Exception as e:
    COOKIES_ERROR = str(e)


@app.get("/health")
def health():
    return jsonify(
        {
            "ok": True,
            "cookies": bool(COOKIES_PATH),
            "cookies_error": COOKIES_ERROR,
        }
    )


@app.get("/diag")
def diag():
    return jsonify(
        {
            "ok": True,
            "cookies": bool(COOKIES_PATH),
            "cookies_error": COOKIES_ERROR,
            "ffmpeg": shutil.which("ffmpeg"),
            "yt_dlp_version": getattr(yt_dlp.version, "__version__", "unknown"),
        }
    )


FORMAT_ATTEMPTS = [
    {
        "format": "bestaudio[acodec!=none]/bestaudio/best[acodec!=none]/best",
        "player_client": ["tv_simply", "mweb"],
    },
    {
        "format": "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best",
        "player_client": ["default", "tv_simply", "mweb"],
    },
    {
        "format": "best",
        "player_client": ["default", "tv_simply"],
    },
]


def make_opts(tmpdir, attempt):
    opts = {
        "format": attempt["format"],
        "outtmpl": os.path.join(tmpdir, "%(title).180B.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": False,
        "windowsfilenames": True,
        "check_formats": False,
        "retries": 5,
        "fragment_retries": 5,
        "socket_timeout": 30,
        "extractor_args": {
            "youtube": {
                "player_client": attempt["player_client"],
                "formats": ["missing_pot"],
            }
        },
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
    }

    if COOKIES_PATH:
        opts["cookiefile"] = COOKIES_PATH

    return opts


@app.get("/download")
def download():
    url = request.args.get("url", "").strip()

    if not url:
        return jsonify({"error": "Missing url"}), 400

    if "youtube.com" not in url and "youtu.be" not in url:
        return jsonify({"error": "Only YouTube URLs are allowed"}), 400

    tmpdir = tempfile.mkdtemp(prefix="cantai-yt-")
    attempts_log = []
    last_error = None
    last_trace = None

    try:
        for attempt in FORMAT_ATTEMPTS:
            try:
                opts = make_opts(tmpdir, attempt)

                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=True)

                mp3_files = sorted(
                    Path(tmpdir).glob("*.mp3"),
                    key=lambda p: p.stat().st_size,
                    reverse=True,
                )

                if not mp3_files:
                    raise RuntimeError("Download terminou, mas nenhum MP3 foi gerado.")

                mp3_path = mp3_files[0]
                title = info.get("title") or "youtube-audio"

                return send_file(
                    str(mp3_path),
                    as_attachment=True,
                    download_name=f"{title}.mp3",
                    mimetype="audio/mpeg",
                )

            except Exception as e:
                last_error = str(e)
                last_trace = traceback.format_exc()
                attempts_log.append(
                    {
                        "format": attempt["format"],
                        "player_client": attempt["player_client"],
                        "error": str(e)[:500],
                    }
                )

        return jsonify(
            {
                "error": last_error or "Não foi possível baixar o áudio.",
                "attempts": attempts_log,
                "trace": (last_trace or "")[-1200:],
            }
        ), 500

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
