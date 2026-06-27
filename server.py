from flask import Flask, request, Response, jsonify
import yt_dlp, tempfile, os, shutil, subprocess, traceback

app = Flask(__name__)

COOKIES_PATH = None
COOKIES_ERROR = None
try:
    if os.environ.get("YT_COOKIES"):
        COOKIES_PATH = "/tmp/cookies.txt"
        with open(COOKIES_PATH, "w") as f:
            f.write(os.environ["YT_COOKIES"])
except Exception as e:
    COOKIES_ERROR = str(e)
    COOKIES_PATH = None


@app.get("/")
def root():
    return jsonify({"ok": True, "service": "cantai-downloader"})


@app.get("/health")
def health():
    return jsonify({"ok": True, "cookies": bool(COOKIES_PATH), "cookies_error": COOKIES_ERROR})


@app.get("/diag")
def diag():
    ff = shutil.which("ffmpeg")
    ver = ""
    if ff:
        try:
            ver = subprocess.run([ff, "-version"], capture_output=True, text=True).stdout.split("\n")[0]
        except Exception as e:
            ver = f"erro: {e}"
    return jsonify({"ffmpeg_path": ff, "ffmpeg_version": ver, "cookies": bool(COOKIES_PATH), "cookies_error": COOKIES_ERROR})


@app.get("/download")
def download():
    url = request.args.get("url")
    if not url:
        return jsonify({"error": "missing url"}), 400
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "audio.%(ext)s")
        ydl_opts = {
           "format": "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best",
            "outtmpl": out,
            "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}],
            "quiet": True,
            "noplaylist": True,
        }
        if COOKIES_PATH:
            ydl_opts["cookiefile"] = COOKIES_PATH
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
        except Exception as e:
            return jsonify({"error": str(e), "trace": traceback.format_exc()[-500:]}), 500
        mp3 = os.path.join(tmp, "audio.mp3")
        if not os.path.exists(mp3):
            return jsonify({"error": "mp3 not produced"}), 500
        data = open(mp3, "rb").read()
        title = info.get("title", "audio").replace('"', "'")
    return Response(data, mimetype="audio/mpeg",
        headers={"Content-Disposition": f'attachment; filename="{title}.mp3"'})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
