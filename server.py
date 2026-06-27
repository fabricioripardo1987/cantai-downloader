from flask import Flask, request, Response, jsonify
import yt_dlp, tempfile, os

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
            "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}],
            "quiet": True,
        }
        if COOKIES_PATH:
            ydl_opts["cookiefile"] = COOKIES_PATH

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

        mp3 = os.path.join(tmp, "audio.mp3")
        if not os.path.exists(mp3):
            return jsonify({"error": "mp3 not produced"}), 500
        data = open(mp3, "rb").read()
        title = info.get("title", "audio").replace('"', "'")
    return Response(
        data,
        mimetype="audio/mpeg",
        headers={"Content-Disposition": f'attachment; filename="{title}.mp3"'},
    )
