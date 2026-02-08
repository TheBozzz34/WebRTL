const frequencyInput = document.querySelector("#frequency");
const sampleRateSelect = document.querySelector("#sampleRate");
const gainInput = document.querySelector("#gain");
const gainValue = document.querySelector("#gainValue");
const gainMode = document.querySelector("#gainMode");
const modeSelect = document.querySelector("#mode");
const bandwidthSelect = document.querySelector("#bandwidth");
const connectButton = document.querySelector("#connectButton");
const scanButton = document.querySelector("#scanButton");
const statusLabel = document.querySelector("#deviceStatus");
const statusDot = document.querySelector(".status-dot");
const lastScan = document.querySelector("#lastScan");
const noiseFloor = document.querySelector("#noiseFloor");
const signalPeak = document.querySelector("#signalPeak");
const bandwidthValue = document.querySelector("#bandwidthValue");
const waterfall = document.querySelector("#waterfall");
const volumeControl = document.querySelector("#volume");
const muteToggle = document.querySelector("#muteToggle");
const audioStatus = document.querySelector("#audioStatus");

const bandwidthOptions = {
  AM: [2400, 5000, 10000],
  FM: [12000, 25000],
  NFM: [12000, 25000],
  WFM: [200000],
  USB: [2400, 5000, 8000],
  LSB: [2400, 5000, 8000],
};

let audioContext;
let audioNode;
let gainNode;
let audioQueue = [];
let isMuted = false;
let ws;
let isScanning = false;

const setStatus = (state) => {
  if (state === "connected") {
    statusLabel.textContent = "Connected · Streaming";
    statusDot.style.background = "#66e5d3";
    statusDot.style.boxShadow = "0 0 0 6px rgba(102, 229, 211, 0.3)";
    connectButton.textContent = "Disconnect";
    connectButton.classList.remove("primary");
    connectButton.classList.add("ghost");
  } else {
    statusLabel.textContent = "Disconnected";
    statusDot.style.background = "#ff9f9f";
    statusDot.style.boxShadow = "0 0 0 6px rgba(255, 159, 159, 0.3)";
    connectButton.textContent = "Connect";
    connectButton.classList.remove("ghost");
    connectButton.classList.add("primary");
  }
};

const setAudioStatus = (message) => {
  audioStatus.textContent = message;
};

const ensureAudio = () => {
  if (audioContext) {
    return;
  }
  audioContext = new AudioContext();
  gainNode = audioContext.createGain();
  gainNode.gain.value = Number(volumeControl.value);
  audioNode = audioContext.createScriptProcessor(4096, 1, 1);
  audioNode.onaudioprocess = (event) => {
    const output = event.outputBuffer.getChannelData(0);
    output.fill(0);
    if (!audioQueue.length) {
      return;
    }
    const chunk = audioQueue.shift();
    output.set(chunk.subarray(0, output.length));
  };
  audioNode.connect(gainNode);
  gainNode.connect(audioContext.destination);
};

const updateGain = () => {
  gainValue.textContent = `${gainInput.value} dB`;
};

const updateBandwidthOptions = () => {
  const mode = modeSelect.value;
  const options = bandwidthOptions[mode] || [12000];
  const current = bandwidthSelect.value;
  bandwidthSelect.innerHTML = "";
  options.forEach((value) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value >= 1000 ? `${value / 1000} kHz` : `${value} Hz`;
    bandwidthSelect.append(option);
  });
  if (options.map(String).includes(current)) {
    bandwidthSelect.value = current;
  }
};

const updateSettings = async () => {
  const payload = {
    frequency: Number.parseFloat(frequencyInput.value),
    sample_rate: Number.parseFloat(sampleRateSelect.value),
    gain: gainMode.value === "auto" ? null : Number.parseInt(gainInput.value, 10),
    gain_mode: gainMode.value,
    mode: modeSelect.value,
    bandwidth: Number.parseFloat(bandwidthSelect.value),
  };

  await fetch("/api/settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
};

const drawWaterfall = (spectrum) => {
  const ctx = waterfall.getContext("2d");
  const { width, height } = waterfall;
  const imageData = ctx.getImageData(0, 0, width, height);
  ctx.putImageData(imageData, 0, 1);
  const row = ctx.createImageData(width, 1);
  const max = Math.max(...spectrum);
  const min = Math.min(...spectrum);
  for (let x = 0; x < width; x += 1) {
    const index = Math.floor((x / width) * spectrum.length);
    const value = (spectrum[index] - min) / (max - min + 1e-6);
    const color = Math.floor(value * 255);
    row.data[x * 4] = color;
    row.data[x * 4 + 1] = 80;
    row.data[x * 4 + 2] = 255 - color;
    row.data[x * 4 + 3] = 255;
  }
  ctx.putImageData(row, 0, 0);
};

const startStream = () => {
  if (ws) {
    ws.close();
  }
  ensureAudio();
  audioContext.resume().catch(() => {});
  ws = new WebSocket(`ws://${window.location.host}/ws/stream`);
  ws.binaryType = "arraybuffer";
  ws.onopen = () => {
    isScanning = true;
    scanButton.textContent = "Stop Scan";
    setAudioStatus("Audio stream active.");
  };
  ws.onmessage = (event) => {
    if (typeof event.data === "string") {
      const payload = JSON.parse(event.data);
      if (payload.type === "fft") {
        drawWaterfall(payload.data);
        noiseFloor.textContent = `${payload.noise_floor.toFixed(1)} dB`;
        signalPeak.textContent = `${payload.signal_peak.toFixed(1)} dB`;
        bandwidthValue.textContent = `${Math.round(payload.bandwidth)} Hz`;
      } else if (payload.type === "status") {
        lastScan.textContent = payload.message;
      }
    } else {
      const data = new Int16Array(event.data);
      const floatData = new Float32Array(data.length);
      for (let i = 0; i < data.length; i += 1) {
        floatData[i] = data[i] / 32768;
      }
      audioQueue.push(floatData);
    }
  };
  ws.onclose = () => {
    isScanning = false;
    scanButton.textContent = "Start Scan";
    setAudioStatus("Stream stopped.");
  };
};

const stopStream = () => {
  if (ws) {
    ws.close();
    ws = null;
  }
  isScanning = false;
};

connectButton.addEventListener("click", async () => {
  const response = await fetch("/api/connect", { method: "POST" });
  const data = await response.json();
  setStatus(data.status);
  if (data.error) {
    lastScan.textContent = data.error;
  }
  if (data.status !== "connected") {
    stopStream();
    setAudioStatus("Connect to start streaming audio.");
  }
});

scanButton.addEventListener("click", async () => {
  if (isScanning) {
    stopStream();
    return;
  }
  if (statusLabel.textContent.includes("Disconnected")) {
    lastScan.textContent = "Connect to the RTL-SDR before starting a scan.";
    return;
  }
  await updateSettings();
  startStream();
});

volumeControl.addEventListener("input", () => {
  if (!gainNode) {
    return;
  }
  gainNode.gain.value = Number(volumeControl.value);
});

muteToggle.addEventListener("click", () => {
  isMuted = !isMuted;
  if (gainNode) {
    gainNode.gain.value = isMuted ? 0 : Number(volumeControl.value);
  }
  muteToggle.textContent = isMuted ? "Unmute" : "Mute";
});

gainInput.addEventListener("input", updateGain);
gainInput.addEventListener("change", updateSettings);
frequencyInput.addEventListener("change", updateSettings);
sampleRateSelect.addEventListener("change", updateSettings);
gainMode.addEventListener("change", () => {
  gainInput.disabled = gainMode.value === "auto";
  updateSettings();
});
modeSelect.addEventListener("change", () => {
  updateBandwidthOptions();
  updateSettings();
});
bandwidthSelect.addEventListener("change", updateSettings);

const bootstrap = async () => {
  updateBandwidthOptions();
  const response = await fetch("/api/status");
  const data = await response.json();
  setStatus(data.status);
  frequencyInput.value = data.settings.frequency;
  sampleRateSelect.value = data.settings.sample_rate.toString();
  gainInput.value = data.settings.gain ?? 0;
  gainMode.value = data.settings.gain_mode || "manual";
  gainInput.disabled = gainMode.value === "auto";
  modeSelect.value = data.settings.mode;
  updateBandwidthOptions();
  bandwidthSelect.value = data.settings.bandwidth.toString();
  updateGain();
  if (data.last_error) {
    lastScan.textContent = data.last_error;
  }
};

bootstrap();
