import json
import os
import socket
import threading
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request

load_dotenv()

app = Flask(__name__)

LOG_FILE = Path(__file__).resolve().parent / "sms_log.txt"
API_KEY = os.environ.get("SMS_API_KEY")  # opsional: set env buat wajibkan X-Api-Key

_write_lock = threading.Lock()
_seen: set[tuple] = set()


def _load_seen() -> None:
    for entry in _read_log():
        _seen.add(_key(entry))


def _key(entry: dict) -> tuple:
    return (entry.get("sender"), entry.get("message"), entry.get("timestamp"))


def _read_log() -> list[dict]:
    if not LOG_FILE.exists():
        return []
    entries = []
    with LOG_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def _check_api_key():
    if not API_KEY:
        return None
    if request.headers.get("X-Api-Key") != API_KEY:
        return jsonify(status="error", error="API key salah atau tidak ada"), 401
    return None


@app.get("/api/health")
def health():
    return jsonify(status="ok")


@app.post("/api/sms")
def receive_sms():
    denied = _check_api_key()
    if denied:
        return denied

    data = request.get_json(silent=True) or {}
    sender = data.get("sender")
    message = data.get("message")
    timestamp = data.get("timestamp")
    gateway_id = data.get("gateway_id", "")

    errors = []
    if not isinstance(sender, str) or not sender.strip():
        errors.append("sender wajib string non-kosong")
    if not isinstance(message, str) or not message.strip():
        errors.append("message wajib string non-kosong")
    if timestamp is not None and not isinstance(timestamp, int):
        errors.append("timestamp harus integer (epoch ms)")
    if errors:
        return jsonify(status="error", errors=errors), 400

    entry = {
        "received_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "gateway_id": gateway_id,
        "sender": sender.strip(),
        "message": message,
        "timestamp": timestamp,
    }

    key = _key(entry)
    with _write_lock:
        if key in _seen:
            return jsonify(status="ok", saved=0, duplicate=True), 200
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        _seen.add(key)

    return jsonify(status="ok", saved=1), 201


@app.get("/api/sms")
def list_sms():
    denied = _check_api_key()
    if denied:
        return denied

    try:
        limit = max(1, min(int(request.args.get("limit", 50)), 500))
        offset = max(0, int(request.args.get("offset", 0)))
    except ValueError:
        return jsonify(status="error", error="limit/offset harus angka"), 400

    sender_filter = request.args.get("sender")
    entries = _read_log()
    if sender_filter:
        entries = [e for e in entries if e.get("sender") == sender_filter]

    entries.reverse()  # terbaru dulu
    total = len(entries)
    page = entries[offset : offset + limit]
    return jsonify(status="success", total=total, count=len(page), data=page)


def _lan_ip() -> str:
    """IP laptop di jaringan lokal (buat diisi di app HP)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


if __name__ == "__main__":
    _load_seen()
    ip = _lan_ip()
    print(f"Backend SMS: http://{ip}:5000  <- pakai alamat ini dari HP")
    print(f"(0.0.0.0 = hanya untuk listen, JANGAN dipakai sebagai tujuan)")
    app.run(debug=True, host="0.0.0.0", port=5000)
