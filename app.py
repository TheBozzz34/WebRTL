from __future__ import annotations

import random
from dataclasses import dataclass, field

from flask import Flask, jsonify, request, send_from_directory


@dataclass
class SDRSettings:
    frequency: float = 101.9
    sample_rate: float = 2.4
    gain: int = 28
    mode: str = "FM"


@dataclass
class SDRState:
    status: str = "disconnected"
    settings: SDRSettings = field(default_factory=SDRSettings)
    last_scan: str | None = None


app = Flask(__name__, static_folder=".")
state = SDRState()


@app.get("/")
def index():
    return send_from_directory(".", "index.html")


@app.get("/api/status")
def status():
    return jsonify(
        {
            "status": state.status,
            "settings": {
                "frequency": state.settings.frequency,
                "sample_rate": state.settings.sample_rate,
                "gain": state.settings.gain,
                "mode": state.settings.mode,
            },
            "last_scan": state.last_scan,
        }
    )


@app.post("/api/settings")
def update_settings():
    payload = request.get_json(silent=True) or {}
    state.settings.frequency = float(payload.get("frequency", state.settings.frequency))
    state.settings.sample_rate = float(
        payload.get("sample_rate", state.settings.sample_rate)
    )
    state.settings.gain = int(payload.get("gain", state.settings.gain))
    state.settings.mode = str(payload.get("mode", state.settings.mode))
    return jsonify({"ok": True})


@app.post("/api/connect")
def connect():
    state.status = "connected" if state.status == "disconnected" else "disconnected"
    return jsonify({"status": state.status})


@app.post("/api/scan")
def scan():
    station = random.choice(
        [
            "Public Safety",
            "Aviation",
            "NOAA Weather",
            "FM Broadcast",
            "Amateur Radio",
        ]
    )
    state.last_scan = f"Detected {station}"
    return jsonify({"status": "scanning", "result": state.last_scan})


@app.get("/<path:path>")
def static_proxy(path: str):
    return send_from_directory(".", path)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
