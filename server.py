import os
import io
import json
import uuid
import shutil
import tempfile
import traceback
import subprocess
from flask import Flask, request, jsonify, send_file

app = Flask(__name__)

COOKIES_ENV = os.environ.get("YT_COOKIES", "").strip()
COOKIES_PATH = "/tmp/yt_cookies.txt"
COOKIES_ERROR = None

if COOKIES_ENV:
    try:
        with open(COOKIES_PATH, "w", encoding="utf-8") as f:
            f.write(COOKIES_ENV)
    except Exception as e:
        COOKIES_ERROR = str(e)


def base_opts(outtmpl):
    opts = {
        "format": "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best",
        "outtmpl": outtmpl,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
        "extractor_args": {
            "youtube": {
                "player_client": ["web", "mweb", "android"],
            },
            "youtubepot-bgutilhttp": {
                "base_url": ["http://127.0.0.1:4416"],
            },
        },
    }
    if COOKIES_ENV and os.path.exists(COOKIES_PATH):
        opts["cookiefile"] = COOKIES_PATH
    return opts


@app.get("/health")
def health():
    return jsonify({
        "ok": True,
        "cookies": bool(COOKIES_ENV),
        "cookies_error": COOKIES_ERROR,
    })


@app.get("/diag")
def diag():
    import yt_dlp
    ffmpeg = shutil.which("ffmpeg")
    try:
        ff_ver = subprocess.check_output([ffmpeg, "-version"], text=True).splitlines()[0] if ffmpeg else None
    except Exception:
        ff_ver = None
    # check PO token provider
    pot_ok = False
    try:
        import urllib.request
        urllib.request.urlopen("http://127.0.0.1:4416/ping", timeout=2)
        pot_ok = True
    except Exception:
        pot_ok = False
    return jsonify({
        "yt_dlp": yt_dlp.version.__version__,
        "ffmpeg": ff_ver,
        "cookies": bool(COOKIES_ENV),
        "pot_provider": pot_ok,
    })


@app.get("/download")
def download():
    url = request.args.get("url", "").strip()
    if not url:
        return jsonify({"error": "missing url"}), 400

    import yt_dlp
    work = tempfile.mkdtemp(prefix="ytdl_")
    outtmpl = os.path.join(work, f"{uuid.uuid4().hex}.%(ext)s")
    try:
        opts = base_opts(outtmpl)
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)

        # localizar mp3 gerado
        mp3 = None
        for f in os.listdir(work):
            if f.endswith(".mp3"):
                mp3 = os.path.join(work, f)
                break
        if not mp3:
            return jsonify({"error": "mp3 not produced"}), 500

        with open(mp3, "rb") as fh:
            data = fh.read()

        title = info.get("title", "audio")
        safe = "".join(c for c in title if c.isalnum() or c in " -_.")[:80] or "audio"
        return send_file(
            io.BytesIO(data),
            mimetype="audio/mpeg",
            as_attachment=True,
            download_name=f"{safe}.mp3",
        )
    except Exception as e:
        return jsonify({
            "error": str(e),
            "trace": traceback.format_exc(),
        }), 500
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
