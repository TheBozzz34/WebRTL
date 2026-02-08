from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

import numpy as np
from flask import Flask, Response, jsonify, request, send_from_directory
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


def decimate(signal: np.ndarray, factor: int) -> np.ndarray:
    if factor <= 1:
        return signal
    return signal[::factor]


def fm_demod(samples: np.ndarray) -> np.ndarray:
    angles = np.angle(samples)
    return np.diff(np.unwrap(angles))


def am_demod(samples: np.ndarray) -> np.ndarray:
    return np.abs(samples) - np.mean(np.abs(samples))


def to_pcm(samples: np.ndarray) -> bytes:
    audio = np.clip(samples, -1.0, 1.0)
    audio_int16 = (audio * 32767).astype(np.int16)
    return audio_int16.tobytes()


def wav_header(sample_rate: int) -> bytes:
    byte_rate = sample_rate * 2
    block_align = 2
    data_size = 0xFFFFFFFF
    riff_size = data_size + 36
    return (
        b"RIFF"
        + riff_size.to_bytes(4, "little", signed=False)
        + b"WAVEfmt "
        + (16).to_bytes(4, "little", signed=False)
        + (1).to_bytes(2, "little", signed=False)
        + (1).to_bytes(2, "little", signed=False)
        + sample_rate.to_bytes(4, "little", signed=False)
        + byte_rate.to_bytes(4, "little", signed=False)
        + block_align.to_bytes(2, "little", signed=False)
        + (16).to_bytes(2, "little", signed=False)
        + b"data"
        + data_size.to_bytes(4, "little", signed=False)
    )


def iter_audio_chunks(mode: str) -> Iterable[bytes]:
    if state.sdr is None:
        return
    sample_rate = int(state.settings.sample_rate * 1_000_000)
    audio_rate = 48_000
    decimation = max(1, sample_rate // audio_rate)
    output_rate = sample_rate // decimation

    while state.sdr is not None:
        samples = state.sdr.read_samples(256 * 1024)
        if mode in {"FM", "NFM", "WFM"}:
            demodulated = fm_demod(samples)
        else:
            demodulated = am_demod(samples)
        demodulated = decimate(demodulated, decimation)
        max_val = np.max(np.abs(demodulated)) or 1.0
        demodulated = demodulated / max_val
        if output_rate != audio_rate:
            ratio = output_rate / audio_rate
            indices = (np.arange(0, len(demodulated) / ratio)).astype(int)
            indices = indices[indices < len(demodulated)]
            demodulated = demodulated[indices]
            output_rate = audio_rate
        yield to_pcm(demodulated.astype(np.float32))


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


@app.get("/api/audio")
def audio():
    if state.sdr is None:
        return jsonify({"error": "Device not connected."}), 400
    mode = request.args.get("mode", state.settings.mode)
    def generate():
        yield wav_header(48_000)
        for chunk in iter_audio_chunks(mode):
            yield chunk

    return Response(generate(), mimetype="audio/wav")


@app.get("/<path:path>")
def static_proxy(path: str):
    return send_from_directory(".", path)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
