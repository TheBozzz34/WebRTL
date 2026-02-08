from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from flask import Flask, jsonify, request, send_from_directory
from rtlsdr import RtlSdr


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
    last_error: str | None = None
    sdr: RtlSdr | None = None


app = Flask(__name__, static_folder=".")
state = SDRState()


def apply_settings() -> None:
    if state.sdr is None:
        return
    state.sdr.center_freq = state.settings.frequency * 1_000_000
    state.sdr.sample_rate = state.settings.sample_rate * 1_000_000
    state.sdr.gain = state.settings.gain


def compute_spectrum(samples: np.ndarray) -> tuple[float, float]:
    window = np.hanning(len(samples))
    spectrum = np.fft.fftshift(np.fft.fft(samples * window))
    power = 20 * np.log10(np.abs(spectrum) + 1e-12)
    noise_floor = float(np.percentile(power, 10))
    peak = float(np.max(power))
    return noise_floor, peak


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
            "last_error": state.last_error,
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
    apply_settings()
    return jsonify({"ok": True})


@app.post("/api/connect")
def connect():
    if state.status == "disconnected":
        try:
            state.sdr = RtlSdr()
            apply_settings()
            state.status = "connected"
            state.last_error = None
        except RuntimeError as exc:
            state.status = "disconnected"
            state.last_error = str(exc)
    else:
        if state.sdr is not None:
            state.sdr.close()
        state.sdr = None
        state.status = "disconnected"
    return jsonify({"status": state.status, "error": state.last_error})


@app.post("/api/scan")
def scan():
    if state.sdr is None:
        return jsonify({"error": "Device not connected."}), 400
    try:
        samples = state.sdr.read_samples(256 * 1024)
        noise_floor, peak = compute_spectrum(samples)
        bandwidth = state.settings.sample_rate * 1_000_000
        state.last_scan = (
            f"Peak {peak:.1f} dB at {state.settings.frequency:.2f} MHz"
        )
        return jsonify(
            {
                "status": "scanned",
                "result": state.last_scan,
                "noise_floor": noise_floor,
                "signal_peak": peak,
                "bandwidth": bandwidth,
            }
        )
    except RuntimeError as exc:
        state.last_error = str(exc)
        return jsonify({"error": state.last_error}), 500


@app.get("/<path:path>")
def static_proxy(path: str):
    return send_from_directory(".", path)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
