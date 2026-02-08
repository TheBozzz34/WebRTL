const gainInput = document.querySelector("#gain");
const gainValue = document.querySelector("#gainValue");
const connectButton = document.querySelector("#connectButton");
const statusLabel = document.querySelector("#deviceStatus");
const statusDot = document.querySelector(".status-dot");
const scanButton = document.querySelector("#scanButton");
const frequencyInput = document.querySelector("#frequency");
const sampleRateInput = document.querySelector("#sampleRate");
const modeSelect = document.querySelector("#mode");

const setStatus = (state) => {
  if (state === "connected") {
    statusLabel.textContent = "Connected · Streaming";
    statusDot.style.background = "#b9f3e4";
    statusDot.style.boxShadow = "0 0 0 6px rgba(185, 243, 228, 0.45)";
    connectButton.textContent = "Disconnect";
    connectButton.classList.remove("primary");
    connectButton.classList.add("ghost");
  } else {
    statusLabel.textContent = "Disconnected";
    statusDot.style.background = "#ffd9c7";
    statusDot.style.boxShadow = "0 0 0 6px rgba(255, 217, 199, 0.4)";
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
});

scanButton.addEventListener("click", async () => {
  scanButton.textContent = "Scanning...";
  scanButton.disabled = true;

  await fetch("/api/scan", { method: "POST" });

  window.setTimeout(() => {
    scanButton.textContent = "Scan Band";
    scanButton.disabled = false;
  }, 1800);
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
};

bootstrap();
