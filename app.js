const gainInput = document.querySelector("#gain");
const gainValue = document.querySelector("#gainValue");
const connectButton = document.querySelector("#connectButton");
const statusLabel = document.querySelector("#deviceStatus");
const statusDot = document.querySelector(".status-dot");
const scanButton = document.querySelector("#scanButton");

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

gainInput.addEventListener("input", (event) => {
  gainValue.textContent = `${event.target.value} dB`;
});

connectButton.addEventListener("click", () => {
  const isConnected = statusLabel.textContent.includes("Connected");
  setStatus(isConnected ? "disconnected" : "connected");
});

scanButton.addEventListener("click", () => {
  scanButton.textContent = "Scanning...";
  scanButton.disabled = true;

  window.setTimeout(() => {
    scanButton.textContent = "Scan Band";
    scanButton.disabled = false;
  }, 1800);
});
