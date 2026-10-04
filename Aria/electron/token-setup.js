const form = document.getElementById("token-form");
const tokenInput = document.getElementById("token");
const rememberInput = document.getElementById("remember-token");
const storageNote = document.getElementById("storage-note");
const status = document.getElementById("status");
const submitButton = document.getElementById("submit");

document.querySelectorAll("[data-window-action]").forEach((button) => {
  button.addEventListener("click", () => {
    window.ariaDesktop.perform(button.dataset.windowAction);
  });
});

function markConnectStep(index) {
  document.querySelectorAll("#connect-steps li").forEach((step, stepIndex) => {
    step.classList.toggle("is-done", stepIndex < index);
    step.classList.toggle("is-active", stepIndex === index);
  });
}

document.getElementById("reveal-token").addEventListener("click", (event) => {
  const reveal = tokenInput.type === "password";
  tokenInput.type = reveal ? "text" : "password";
  event.currentTarget.textContent = reveal ? "Hide" : "Show";
  event.currentTarget.setAttribute("aria-pressed", reveal ? "true" : "false");
  event.currentTarget.setAttribute("aria-label", reveal ? "Hide token" : "Show token");
});

document.getElementById("cancel").addEventListener("click", () => window.ariaSetup.cancel());
tokenInput.addEventListener("input", () => markConnectStep(tokenInput.value.trim() ? 1 : 0));
rememberInput.addEventListener("change", () => {
  storageNote.textContent = rememberInput.checked
    ? "Saved encrypted in Aria's local config."
    : "Used only until you close Aria; it will not be saved.";
  if (tokenInput.value.trim()) markConnectStep(1);
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const token = tokenInput.value.trim();
  if (!token) {
    status.textContent = "Enter your token to continue.";
    return;
  }

  submitButton.disabled = true;
  markConnectStep(2);
  status.dataset.state = "pending";
  status.textContent = "Verifying your account and detecting the owner...";
  try {
    const result = await window.ariaSetup.saveToken(
      token,
      rememberInput.checked,
      document.getElementById("captcha-key").value.trim(),
      document.getElementById("captcha-provider").value,
    );
    if (!result.ok) throw new Error(result.error || "Could not save the token.");
    tokenInput.value = "";
    document.getElementById("captcha-key").value = "";
  } catch (error) {
    status.dataset.state = "error";
    status.textContent = error.message;
    submitButton.disabled = false;
  }
});
