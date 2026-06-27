from flask import Flask, request, Response, jsonify
import yt_dlp, tempfile, os, shutil, subprocess

app = Flask(__name__)

# Materializa cookies da env var em um arquivo, se existir
COOKIES_PATH = None
if os.environ.get("YT_COOKIES"):
    COOKIES_PATH = "/tmp/cookies.txt"
    with open(COOKIES_PATH, "w") as f:
        f.write(os.environ["YT_COOKIES"])


@app.get("/health")
def health():
    return jsonify({"ok": True, "cookies": bool(COOKIES_PATH)})


@app.get("/diag")
def diag():
    ff = shutil.which("ffmpeg")
    ver = ""
    if ff:
        try:
            ver = subprocess.run(
                [ff, "-version"], capture_output=True, text=True
            ).stdout.split("\n")[0]
        except Exception as e:
            ver = f"erro: {e}"
    return jsonify({
        "ffmpeg_path": ff,
        "ffmpeg_version": ver,
        "cookies": bool(COOKIES_PATH),
    })


@app.get("/download")
def download():
    url = request.args.get("url")
    if not url:
        return jsonify({"error": "missing url"}), 400

    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "audio.%(ext)s")
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": out,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
            "quiet": True,
            "noplaylist": True,
        }
        if COOKIES_PATH:
            ydl_opts["cookiefile"] = COOKIES_PATH

        try:
