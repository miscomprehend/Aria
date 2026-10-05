const status = document.getElementById("startup-status");
const state = document.getElementById("runtime-state");
const title = document.getElementById("startup-title");
const bootStartedAt = Date.now();
const bootSteps = [
  { match: /looking for a local|checking for an aria/i, progress: 22, title: "Looking for your dashboard" },
  { match: /starting your private|starting aria/i, progress: 48, title: "Starting your runtime" },
  { match: /signing into/i, progress: 72, title: "Signing you in" },
  { match: /opening your dashboard/i, progress: 94, title: "Opening your dashboard" },
];
const stepStartedAt = {};
const stepDuration = {};

document.querySelectorAll("[data-window-action]").forEach((button) => {
  button.addEventListener("click", () => {
    window.ariaDesktop.perform(button.dataset.windowAction);
  });
});

function markBootStep(message) {
  const steps = Array.from(document.querySelectorAll("#boot-steps li"));
  const failed = /could not|couldn't|failed|error/i.test(message);
  const activeIndex = Math.max(0, bootSteps.findIndex((step) => step.match.test(message)));
  const now = Date.now();
  steps.forEach((step, index) => {
    if (index === activeIndex && stepStartedAt[index] === undefined) stepStartedAt[index] = now;
    if (index < activeIndex && stepStartedAt[index] !== undefined && stepDuration[index] === undefined) {
      stepDuration[index] = ((now - stepStartedAt[index]) / 1000).toFixed(1);
    }
    step.classList.toggle("is-done", !failed && index < activeIndex);
    step.classList.toggle("is-active", !failed && index === activeIndex);
    step.classList.toggle("is-failed", failed && index === activeIndex);
    const time = step.querySelector("em");
    if (time) time.textContent = stepDuration[index] !== undefined ? `${stepDuration[index]}s` : "";
  });
  title.textContent = failed ? "Needs attention" : bootSteps[activeIndex].title;
  const fill = document.getElementById("startup-fill");
  if (fill) fill.style.width = `${failed ? 100 : bootSteps[activeIndex].progress}%`;
}

window.setAriaStartupStatus = (message) => {
  const text = String(message || "Preparing your workspace...");
  status.textContent = text;
  state.textContent = /could not|couldn't|failed|error/i.test(text) ? "desktop · needs attention" : "desktop · starting";
  markBootStep(text);
};

setInterval(() => {
  const seconds = Math.floor((Date.now() - bootStartedAt) / 1000);
  const elapsed = document.getElementById("startup-elapsed");
  if (elapsed) {
    elapsed.textContent = `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
  }
}, 1000);
markBootStep("Checking for an Aria dashboard...");
