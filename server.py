import os
import tempfile
import traceback
from flask import Flask, request, jsonify, send_file
import yt_dlp

app = Flask(__name__)

COOKIES_PATH = None
COOKIES_ERROR = None

try:
    raw = os.environ.get("YT_COOKIES")
    if raw:
        path = "/tmp/cookies.txt"
        with open(path, "w", encoding="utf-8") as f:
            f.write(raw)
        COOKIES_PATH = path
except Exception as e:
    COOKIES_ERROR = str(e)


@app.get("/health")
def health():
    return jsonify({
        "ok": True,
        "cookies": bool(COOKIES_PATH),
        "cookies_error": COOKIES_ERROR,
    })


@app.get("/diag")
def diag():
    import shutil
    return jsonify({
        "ffmpeg": shutil.which("ffmpeg"),
        "cookies": bool(COOKIES_PATH),
    })


@app.get("/download")
def download():
    url = request.args.get("url")
    if not url:
        return jsonify({"error": "missing url"}), 400

    tmpdir = tempfile.mkdtemp()
    outtmpl = os.path.join(tmpdir, "%(id)s.%(ext)s")

    ydl_opts = {
        "format": "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best",
        "outtmpl": outtmpl,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
        "extractor_args": {
            "youtube": {"player_client": ["android", "web"]},
        },
    }

    if COOKIES_PATH:
        ydl_opts["cookiefile"] = COOKIES_PATH

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get("title", "audio")
            vid = info.get("id")
            mp3_path = os.path.join(tmpdir, f"{vid}.mp3")
            if not os.path.exists(mp3_path):
                for f in os.listdir(tmpdir):
                    if f.endswith(".mp3"):
                        mp3_path = os.path.join(tmpdir, f)
                        break
        return send_file(mp3_path, as_attachment=True, download_name=f"{title}.mp3", mimetype="audio/mpeg")
    except Exception as e:
        return jsonify({"error": str(e), "trace": traceback.format_exc()[-800:]}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
