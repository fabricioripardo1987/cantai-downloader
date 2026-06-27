import os
import re
import sys
import json
import shutil
import tempfile
import traceback
import subprocess
from pathlib import Path

from flask import Flask, request, jsonify, send_file, after_this_request
import yt_dlp


app = Flask(__name__)

POT_PROVIDER_URL = os.environ.get("POT_PROVIDER_URL", "http://127.0.0.1:4416")


class MemoryLogger:
    def __init__(self):
        self.lines = []

    def debug(self, msg):
        self.lines.append(str(msg))

    def warning(self, msg):
        self.lines.append("WARNING: " + str(msg))

    def error(self, msg):
        self.lines.append("ERROR: " + str(msg))

    def tail(self, n=120):
        return self.lines[-n:]


def write_cookies_file(work_dir: str):
    raw = os.environ.get("YT_COOKIES", "").strip()
    if not raw:
        return None, None

    try:
        # Aceita cookie colado com \n literal ou quebra real de linha
        raw = raw.replace("\\n", "\n")

        cookie_path = os.path.join(work_dir, "cookies.txt")
        with open(cookie_path, "w", encoding="utf-8") as f:
            f.write(raw)
            if not raw.endswith("\n"):
                f.write("\n")

        return cookie_path, None
    except Exception as e:
        return None, str(e)


def command_exists(cmd):
    return shutil.which(cmd) is not None


def pot_provider_reachable():
    try:
        import requests

        res = requests.get(POT_PROVIDER_URL, timeout=3)
        return True, res.status_code
    except Exception as e:
        return False, str(e)


def ytdlp_version():
    try:
        return yt_dlp.version.__version__
    except Exception:
        return None


def run_ytdlp_verbose_probe(video_url):
    try:
        cmd = [
            sys.executable,
            "-m",
            "yt_dlp",
            "-v",
            "--simulate",
            "--skip-download",
            "--extractor-args",
            f"youtubepot-bgutilhttp:base_url={POT_PROVIDER_URL}",
            video_url,
        ]

        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=45,
        )

        output = (completed.stdout or "") + "\n" + (completed.stderr or "")

        return {
            "ok": completed.returncode == 0,
            "returncode": completed.returncode,
            "has_bgutil_provider": "bgutil" in output.lower(),
            "has_po_token_line": "PO Token Providers" in output,
            "tail": output[-5000:],
        }
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
        }


@app.get("/health")
def health():
    cookie_path, cookie_error = write_cookies_file(tempfile.mkdtemp(prefix="health-"))
    reachable, provider_status = pot_provider_reachable()

    return jsonify(
        {
            "ok": True,
            "cookies": bool(os.environ.get("YT_COOKIES", "").strip()),
            "cookies_error": cookie_error,
            "ffmpeg": command_exists("ffmpeg"),
            "node": command_exists("node"),
            "yt_dlp": ytdlp_version(),
            "pot_provider_url": POT_PROVIDER_URL,
            "pot_provider_reachable": reachable,
            "pot_provider_status": provider_status,
        }
    )


@app.get("/diag")
def diag():
    video_id = request.args.get("v", "BaW_jenozKc")
    if not re.match(r"^[A-Za-z0-9_-]{6,20}$", video_id):
        video_id = "BaW_jenozKc"

    video_url = f"https://www.youtube.com/watch?v={video_id}"
    reachable, provider_status = pot_provider_reachable()
    probe = run_ytdlp_verbose_probe(video_url)

    return jsonify(
        {
            "ok": True,
            "video": video_url,
            "ffmpeg": command_exists("ffmpeg"),
            "node": command_exists("node"),
            "yt_dlp": ytdlp_version(),
            "cookies": bool(os.environ.get("YT_COOKIES", "").strip()),
            "pot_provider_url": POT_PROVIDER_URL,
            "pot_provider_reachable": reachable,
            "pot_provider_status": provider_status,
            "probe": probe,
        }
    )


def build_opts(work, cookiefile, attempt, logger):
    opts = {
        "outtmpl": os.path.join(work, "%(title).180B [%(id)s].%(ext)s"),
        "noplaylist": True,
        "quiet": False,
        "no_warnings": False,
        "verbose": True,
        "logger": logger,
        "socket_timeout": 45,
        "retries": 5,
        "fragment_retries": 5,
        "ignoreerrors": False,
        "nocheckcertificate": True,
        "prefer_ffmpeg": True,
        "ffmpeg_location": "/usr/bin/ffmpeg",
        "format": attempt["format"],
        "extractor_args": attempt["extractor_args"],
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
    }

    if cookiefile:
        opts["cookiefile"] = cookiefile

    return opts


def find_mp3(work):
    files = list(Path(work).glob("*.mp3"))
    if not files:
        files = list(Path(work).rglob("*.mp3"))

    if not files:
        return None

    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return str(files[0])


@app.get("/download")
def download():
    url = request.args.get("url", "").strip()

    if not url:
        return jsonify({"error": "URL ausente"}), 400

    if "youtube.com" not in url and "youtu.be" not in url:
        return jsonify({"error": "URL do YouTube inválida"}), 400

    work = tempfile.mkdtemp(prefix="yt-")
    cookiefile, cookie_error = write_cookies_file(work)

    if cookie_error:
        shutil.rmtree(work, ignore_errors=True)
        return jsonify({"error": "Erro ao criar cookies.txt", "details": cookie_error}), 500

    attempts = [
        {
            "format": "bestaudio[acodec!=none]/bestaudio/best[acodec!=none]/best",
            "extractor_args": {
                "youtube": {
                    # Evita tv_simply. Usa clients mais compatíveis com o provider.
                    "player_client": ["web", "web_safari", "mweb", "tv"],
                },
                "youtubepot-bgutilhttp": {
                    "base_url": [POT_PROVIDER_URL],
                },
            },
        },
        {
            "format": "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best",
            "extractor_args": {
                "youtube": {
                    "player_client": ["web", "mweb", "web_safari"],
                },
                "youtubepot-bgutilhttp": {
                    "base_url": [POT_PROVIDER_URL],
                    "disable_innertube": ["1"],
                },
            },
        },
        {
            "format": "best",
            "extractor_args": {
                "youtube": {
                    "player_client": ["web"],
                },
                "youtubepot-bgutilhttp": {
                    "base_url": [POT_PROVIDER_URL],
                },
            },
        },
    ]

    errors = []

    try:
        for attempt in attempts:
            logger = MemoryLogger()

            try:
                opts = build_opts(work, cookiefile, attempt, logger)

                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=True)

                mp3 = find_mp3(work)

                if not mp3:
                    raise RuntimeError("Download terminou, mas nenhum MP3 foi gerado.")

                title = info.get("title") or "youtube-audio"
                safe_title = re.sub(r"[^A-Za-z0-9À-ÿ._ -]+", "", title).strip() or "youtube-audio"
                filename = f"{safe_title[:120]}.mp3"

                @after_this_request
                def cleanup(response):
                    shutil.rmtree(work, ignore_errors=True)
                    return response

                return send_file(
                    mp3,
                    mimetype="audio/mpeg",
                    as_attachment=True,
                    download_name=filename,
                )

            except Exception as e:
                errors.append(
                    {
                        "format": attempt["format"],
                        "player_client": attempt["extractor_args"].get("youtube", {}).get("player_client"),
                        "error": str(e),
                        "log_tail": logger.tail(),
                    }
                )

        return (
            jsonify(
                {
                    "error": errors[-1]["error"] if errors else "Falha ao baixar",
                    "attempts": errors,
                    "hint": "Se todos os formatos falharam, confira /diag. O campo probe.has_bgutil_provider precisa ser true e o log precisa mostrar 'PO Token Providers: bgutil'.",
                }
            ),
            500,
        )

    except Exception as e:
        return (
            jsonify(
                {
                    "error": str(e),
                    "trace": traceback.format_exc(),
                }
            ),
            500,
        )

    finally:
        # Se send_file foi usado, o cleanup real acontece em after_this_request.
        # Se houve erro, remove aqui.
        if not list(Path(work).glob("*.mp3")):
            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
