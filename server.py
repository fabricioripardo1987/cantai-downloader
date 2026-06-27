import os, tempfile, subprocess
from flask import Flask, request, send_file, jsonify

app = Flask(__name__)

# Materializa cookies do env var em um arquivo, se existir
COOKIES_PATH = None
if os.environ.get("YT_COOKIES"):
    COOKIES_PATH = "/tmp/cookies.txt"
    with open(COOKIES_PATH, "w") as f:
        f.write(os.environ["YT_COOKIES"])

@app.get("/health")
def health():
    return {"ok": True, "cookies": bool(COOKIES_PATH)}

@app.get("/download")
def download():
    url = request.args.get("url")
    if not url:
        return jsonify({"error": "missing url"}), 400

    out = tempfile.mktemp(suffix=".mp3")
    cmd = [
        "yt-dlp",
        "-x", "--audio-format", "mp3",
        "-o", out,
        "--no-playlist",
    ]
    if COOKIES_PATH:
        cmd += ["--cookies", COOKIES_PATH]
    cmd.append(url)

    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=180)
        return send_file(out, mimetype="audio/mpeg", as_attachment=True,
                         download_name="audio.mp3")
    except subprocess.CalledProcessError as e:
        return jsonify({"error": "download failed",
                        "detail": e.stderr.decode()[-500:]}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
