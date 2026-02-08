from __future__ import annotations

import json
import time
from dataclasses import dataclass, field

import numpy as np
from flask import Flask, jsonify, request, send_from_directory
from flask_sock import Sock
from rtlsdr import RtlSdr


@dataclass
class SDRSettings:
    frequency: float = 101.9
    sample_rate: float = 2.4
    gain: int | None = 28
    gain_mode: str = "manual"
    mode: str = "FM"
    bandwidth: float = 12000.0


@dataclass
class SDRState:
    status: str = "disconnected"
    settings: SDRSettings = field(default_factory=SDRSettings)
    last_error: str | None = None
    sdr: RtlSdr | None = None


app = Flask(__name__, static_folder=".")
sock = Sock(app)
state = SDRState()


def apply_settings() -> None:
    if state.sdr is None:
        return
    state.sdr.center_freq = state.settings.frequency * 1_000_000
    state.sdr.sample_rate = state.settings.sample_rate * 1_000_000
    if state.settings.gain_mode == "auto" or state.settings.gain is None:
        state.sdr.gain = "auto"
    else:
        state.sdr.gain = state.settings.gain


def compute_spectrum(samples: np.ndarray) -> tuple[np.ndarray, float, float]:
    fft_size = 2048
    window = np.hanning(fft_size)
    spectrum = np.fft.fftshift(np.fft.fft(samples[:fft_size] * window))
    power = 20 * np.log10(np.abs(spectrum) + 1e-12)
    noise_floor = float(np.percentile(power, 10))
    peak = float(np.max(power))
    return power, noise_floor, peak


def lowpass(signal: np.ndarray, cutoff: float, sample_rate: float) -> np.ndarray:
    if cutoff <= 0:
        return signal
    normalized = cutoff / sample_rate
    taps = 101
    t = np.arange(taps) - (taps - 1) / 2
    kernel = np.sinc(2 * normalized * t) * np.hanning(taps)
    kernel /= np.sum(kernel)
    return np.convolve(signal, kernel, mode="same")


def fm_demod(samples: np.ndarray) -> np.ndarray:
    angles = np.angle(samples)
    return np.diff(np.unwrap(angles))


def am_demod(samples: np.ndarray) -> np.ndarray:
    return np.abs(samples) - np.mean(np.abs(samples))


def ssb_demod(samples: np.ndarray, mode: str) -> np.ndarray:
    return np.real(samples) if mode == "USB" else np.imag(samples)


def to_pcm(samples: np.ndarray) -> bytes:
    audio = np.clip(samples, -1.0, 1.0)
    audio_int16 = (audio * 32767).astype(np.int16)
    return audio_int16.tobytes()


def process_audio(samples: np.ndarray, mode: str, sample_rate: float) -> bytes:
    if mode in {"FM", "NFM", "WFM"}:
        audio = fm_demod(samples)
    elif mode == "AM":
        audio = am_demod(samples)
    else:
        audio = ssb_demod(samples, mode)
    audio = lowpass(audio, state.settings.bandwidth, sample_rate)
    audio_rate = 48_000
    decimation = max(1, int(sample_rate // audio_rate))
    audio = audio[::decimation]
    audio = audio / (np.max(np.abs(audio)) or 1.0)
    return to_pcm(audio.astype(np.float32))


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
                "gain_mode": state.settings.gain_mode,
                "mode": state.settings.mode,
                "bandwidth": state.settings.bandwidth,
            },
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
    state.settings.gain = (
        int(payload["gain"]) if payload.get("gain") is not None else None
    )
    state.settings.gain_mode = str(payload.get("gain_mode", state.settings.gain_mode))
    state.settings.mode = str(payload.get("mode", state.settings.mode))
    state.settings.bandwidth = float(
        payload.get("bandwidth", state.settings.bandwidth)
    )
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


@sock.route("/ws/stream")
def stream(ws):
    if state.sdr is None:
        ws.send(json.dumps({"type": "status", "message": "Device not connected."}))
        return
    sample_rate = state.settings.sample_rate * 1_000_000
    ws.send(json.dumps({"type": "status", "message": "Streaming started."}))
    while True:
        try:
            samples = state.sdr.read_samples(4096 * 4)
        except RuntimeError as exc:
            ws.send(json.dumps({"type": "status", "message": str(exc)}))
            break
        power, noise_floor, peak = compute_spectrum(samples)
        ws.send(
            json.dumps(
                {
                    "type": "fft",
                    "data": power.tolist(),
                    "noise_floor": noise_floor,
                    "signal_peak": peak,
                    "bandwidth": sample_rate,
                }
            )
        )
        audio = process_audio(samples, state.settings.mode, sample_rate)
        ws.send(audio, binary=True)
        time.sleep(0.03)


@app.get("/<path:path>")
def static_proxy(path: str):
    return send_from_directory(".", path)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
