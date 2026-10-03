const status = document.getElementById("startup-status");
const state = document.getElementById("runtime-state");

document.querySelectorAll("[data-window-action]").forEach((button) => {
  button.addEventListener("click", () => {
    window.ariaDesktop.perform(button.dataset.windowAction);
  });
});

window.setAriaStartupStatus = (message) => {
  status.textContent = String(message || "Preparing your workspace...");
  state.textContent = "STARTING";
};
