const status = document.getElementById("startup-status");
const state = document.getElementById("runtime-state");

window.setAriaStartupStatus = (message) => {
  status.textContent = String(message || "Preparing your workspace...");
  state.textContent = "STARTING";
};
