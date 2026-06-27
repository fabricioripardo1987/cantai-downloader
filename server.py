from flask import Flask, request, Response, jsonify
import yt_dlp, tempfile, os

app = Flask(__name__)

@app.get("/health")
def health(): return "ok"

@app.get("/download")
def download():
    url = request.args.get("url")
    if not url: return jsonify({"error":"missing url"}), 400
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "audio.%(ext)s")
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": out,
            "postprocessors": [{"key":"FFmpegExtractAudio","preferredcodec":"mp3","preferredquality":"192"}],
            "quiet": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
        mp3 = os.path.join(tmp, "audio.mp3")
        data = open(mp3, "rb").read()
        title = info.get("title","audio").replace('"',"'")
    return Response(data, mimetype="audio/mpeg",
        headers={"Content-Disposition": f'attachment; filename="{title}.mp3"'})
