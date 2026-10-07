const form = document.getElementById("token-form");
const tokenInput = document.getElementById("token");
const captchaInput = document.getElementById("captcha-key");
const captchaProviderInput = document.getElementById("captcha-provider");
const captchaUrlInput = document.getElementById("captcha-url");
const captchaUrlLabel = document.getElementById("captcha-url-label");
const rememberInput = document.getElementById("remember-token");
const storageNote = document.getElementById("storage-note");
const status = document.getElementById("status");
const submitButton = document.getElementById("submit");
const backButton = document.getElementById("back");
const keyHint = document.getElementById("key-hint");
const panels = [...document.querySelectorAll("[data-panel]")];
const LAST_STEP = panels.length - 1;
let step = 0;

captchaProviderInput.addEventListener("change", () => {
  const customProvider = captchaProviderInput.value === "twocaptcha-compatible";
  captchaUrlInput.hidden = !customProvider;
  captchaUrlLabel.hidden = !customProvider;
});

document.querySelectorAll("[data-window-action]").forEach((button) => {
  button.addEventListener("click", () => {
    window.ariaDesktop.perform(button.dataset.windowAction);
  });
});

function showStep(index) {
  step = index;
  panels.forEach((panel, i) => { panel.hidden = i !== index; });
  document.querySelectorAll("#connect-steps li").forEach((item, i) => {
    item.classList.toggle("is-done", i < index);
    item.classList.toggle("is-active", i === index);
  });
  backButton.hidden = index === 0;
  submitButton.textContent = index === LAST_STEP ? "Save and start Aria" : "Continue";
  keyHint.textContent = index === LAST_STEP ? "" : "Enter to continue";
  status.textContent = "";
  status.dataset.state = "";
  panels[index].querySelector("input:not([type=checkbox])")?.focus();
}

document.getElementById("reveal-token").addEventListener("click", (event) => {
  const reveal = tokenInput.type === "password";
  tokenInput.type = reveal ? "text" : "password";
  event.currentTarget.textContent = reveal ? "hide" : "show";
  event.currentTarget.setAttribute("aria-pressed", reveal ? "true" : "false");
  event.currentTarget.setAttribute("aria-label", reveal ? "Hide token" : "Show token");
});

document.querySelectorAll("#connect-steps li").forEach((item) => {
  item.addEventListener("click", () => {
    const target = Number(item.dataset.step);
    if (target <= step || tokenInput.value.trim()) showStep(target);
  });
});

document.getElementById("cancel").addEventListener("click", () => window.ariaSetup.cancel());
backButton.addEventListener("click", () => showStep(step - 1));
rememberInput.addEventListener("change", () => {
  storageNote.textContent = rememberInput.checked
    ? "Saved encrypted in Aria's local config."
    : "Used only until you close Aria; it will not be saved.";
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const token = tokenInput.value.trim();
  if (!token) {
    showStep(0);
    status.dataset.state = "error";
    status.textContent = "Enter your token to continue.";
    return;
  }
  if (step < LAST_STEP) {
    showStep(step + 1);
    return;
  }

  submitButton.disabled = true;
  backButton.disabled = true;
  status.dataset.state = "pending";
  status.textContent = "Verifying your account and detecting the owner...";
  try {
    const provider = captchaProviderInput.value;
    // The backend stores both native 2Captcha and compatible hosts under the
    // "twocaptcha" provider; a non-empty URL selects the compatible protocol.
    const normalizedProvider = provider === "twocaptcha-compatible" ? "twocaptcha" : provider;
    const normalizedUrl = provider === "twocaptcha-compatible" ? captchaUrlInput.value.trim() : "";
    const result = await window.ariaSetup.saveToken(
      token,
      rememberInput.checked,
      captchaInput.value.trim(),
      normalizedProvider,
      normalizedUrl,
    );
    if (!result.ok) throw new Error(result.error || "Could not save the token.");
    tokenInput.value = "";
    captchaInput.value = "";
  } catch (error) {
    status.dataset.state = "error";
    status.textContent = error.message;
    submitButton.disabled = false;
    backButton.disabled = false;
  }
});

showStep(0);
