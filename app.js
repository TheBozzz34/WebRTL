const gainInput = document.querySelector("#gain");
const gainValue = document.querySelector("#gainValue");
const connectButton = document.querySelector("#connectButton");
const statusLabel = document.querySelector("#deviceStatus");
const statusDot = document.querySelector(".status-dot");
const scanButton = document.querySelector("#scanButton");
const frequencyInput = document.querySelector("#frequency");
const sampleRateInput = document.querySelector("#sampleRate");
const modeSelect = document.querySelector("#mode");
const lastScan = document.querySelector("#lastScan");
const noiseFloor = document.querySelector("#noiseFloor");
const signalPeak = document.querySelector("#signalPeak");
const bandwidth = document.querySelector("#bandwidth");
const audioStream = document.querySelector("#audioStream");

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

const updateSettings = async () => {
  const payload = {
    frequency: Number.parseFloat(frequencyInput.value),
    sample_rate: Number.parseFloat(sampleRateInput.value),
    gain: Number.parseInt(gainInput.value, 10),
    mode: modeSelect.value,
  };

  await fetch("/api/settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (audioStream.src) {
    audioStream.src = `/api/audio?mode=${encodeURIComponent(modeSelect.value)}`;
    audioStream.play().catch(() => {});
  }
};

gainInput.addEventListener("input", (event) => {
  gainValue.textContent = `${event.target.value} dB`;
});

gainInput.addEventListener("change", updateSettings);
frequencyInput.addEventListener("change", updateSettings);
sampleRateInput.addEventListener("change", updateSettings);
modeSelect.addEventListener("change", updateSettings);

connectButton.addEventListener("click", async () => {
  const response = await fetch("/api/connect", { method: "POST" });
  const data = await response.json();
  setStatus(data.status);
  if (data.error) {
    lastScan.textContent = data.error;
  }
  if (data.status === "connected") {
    audioStream.src = `/api/audio?mode=${encodeURIComponent(modeSelect.value)}`;
    audioStream.play().catch(() => {});
  } else {
    audioStream.removeAttribute("src");
    audioStream.load();
  }
});

scanButton.addEventListener("click", async () => {
  scanButton.textContent = "Scanning...";
  scanButton.disabled = true;

  const response = await fetch("/api/scan", { method: "POST" });
  const data = await response.json();
  if (!response.ok) {
    lastScan.textContent = data.error || "Scan failed.";
  } else {
    lastScan.textContent = data.result;
    noiseFloor.textContent = `${data.noise_floor.toFixed(1)} dB`;
    signalPeak.textContent = `${data.signal_peak.toFixed(1)} dB`;
    bandwidth.textContent = `${Math.round(data.bandwidth)} Hz`;
  }
  scanButton.textContent = "Scan Band";
  scanButton.disabled = false;
});

const bootstrap = async () => {
  const response = await fetch("/api/status");
  const data = await response.json();
  setStatus(data.status);
  frequencyInput.value = data.settings.frequency;
  sampleRateInput.value = data.settings.sample_rate;
  gainInput.value = data.settings.gain;
  gainValue.textContent = `${data.settings.gain} dB`;
  modeSelect.value = data.settings.mode;
  if (data.last_scan) {
    lastScan.textContent = data.last_scan;
  }
  if (data.last_error) {
    lastScan.textContent = data.last_error;
  }
};

bootstrap();
