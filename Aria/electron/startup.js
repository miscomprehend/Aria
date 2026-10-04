const status = document.getElementById("startup-status");
const state = document.getElementById("runtime-state");
const bootStartedAt = Date.now();
const bootSteps = [
  { match: /looking for a local|checking for an aria/i, progress: 22 },
  { match: /starting your private|starting aria/i, progress: 48 },
  { match: /signing into/i, progress: 72 },
  { match: /opening your dashboard/i, progress: 94 },
];

document.querySelectorAll("[data-window-action]").forEach((button) => {
  button.addEventListener("click", () => {
    window.ariaDesktop.perform(button.dataset.windowAction);
  });
});

function markBootStep(message) {
  const steps = Array.from(document.querySelectorAll("#boot-steps li"));
  const failed = /could not|couldn't|failed|error/i.test(message);
  const activeIndex = Math.max(0, bootSteps.findIndex((step) => step.match.test(message)));
  steps.forEach((step, index) => {
    step.classList.toggle("is-done", !failed && index < activeIndex);
    step.classList.toggle("is-active", index === activeIndex);
    step.classList.toggle("is-failed", failed && index === activeIndex);
  });
  const fill = document.getElementById("startup-fill");
  if (fill) fill.style.width = `${failed ? 100 : bootSteps[activeIndex].progress}%`;
}

window.setAriaStartupStatus = (message) => {
  const text = String(message || "Preparing your workspace...");
  status.textContent = text;
  state.textContent = /could not|couldn't|failed|error/i.test(text) ? "NEEDS ATTENTION" : "STARTING";
  markBootStep(text);
};

setInterval(() => {
  const elapsed = document.getElementById("startup-elapsed");
  if (elapsed) elapsed.textContent = `${Math.floor((Date.now() - bootStartedAt) / 1000)}s`;
}, 1000);
markBootStep("Checking for an Aria dashboard...");
