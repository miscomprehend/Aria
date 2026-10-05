const { app, BrowserWindow, Menu, dialog, ipcMain, session, shell } = require("electron");
const crypto = require("node:crypto");
const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");
const { spawn } = require("node:child_process");

const HOST = "127.0.0.1";
const PORTS = [8080, 8081, 8082, 8083, 8084];
const APP_ID = "com.aria.desktop";
const DATA_EXTENSIONS = new Set([".db", ".json", ".sqlite", ".sqlite3", ".txt"]);
const PUBLIC_SITE_PATHS = new Set([
  "/",
  "/home",
  "/features",
  "/docs",
  "/llms.txt",
  "/get-token",
  "/tos",
  "/terms",
  "/privacy",
]);

let backendProcess = null;
let backendStartError = null;
let backendConfigPath = null;
let backendContext = null;
let dashboardUrl = null;
let mainWindow = null;
let tokenWindow = null;
let desktopAuthToken = null;
let desktopOwnerId = null;
let logFilePath = null;
let nativeDashboardProcess = null;
let nativeControlServer = null;
let nativeControlToken = null;
let isQuitting = false;

if (process.platform === "win32") app.setAppUserModelId(APP_ID);

function logMessage(level, message) {
  const line = `${new Date().toISOString()} [${level}] ${message}`;
  if (level === "ERROR") console.error(line);
  else console.log(line);
  if (logFilePath) {
    try {
      fs.appendFileSync(logFilePath, `${line}\n`, "utf8");
    } catch (error) {
      console.error(`Could not write Aria log: ${error.message}`);
    }
  }
}

function initializeLogging() {
  logFilePath = path.join(app.getPath("userData"), "logs", "aria-desktop.log");
  fs.mkdirSync(path.dirname(logFilePath), { recursive: true });
  logMessage("INFO", `Desktop log: ${logFilePath}`);
}

function attachProcessOutput(stream, source, level) {
  let pending = "";
  stream.on("data", (chunk) => {
    const lines = `${pending}${chunk.toString()}`.split(/\r?\n/);
    pending = lines.pop() || "";
    for (const line of lines) {
      if (line.trim()) logMessage(level, `[${source}] ${line.trim()}`);
    }
  });
  stream.on("end", () => {
    if (pending.trim()) logMessage(level, `[${source}] ${pending.trim()}`);
  });
}

function requestDashboard(port) {
  return new Promise((resolve) => {
    const request = http.get({ hostname: HOST, port, path: "/", timeout: 1200 }, (response) => {
      let html = "";
      response.setEncoding("utf8");
      response.on("data", (chunk) => {
        if (html.length < 8192) html += chunk;
      });
      response.on("end", () => {
        resolve(response.statusCode === 200 && html.includes("<title>Aria |")
          ? `http://${HOST}:${port}`
          : null);
      });
      response.on("error", () => resolve(null));
    });
    request.on("timeout", () => request.destroy());
    request.on("error", () => resolve(null));
  });
}

async function findDashboard() {
  const results = await Promise.all(PORTS.map(requestDashboard));
  return results.find(Boolean) || null;
}

function copyRuntimeData(source, destination) {
  if (!fs.existsSync(source)) return;

  for (const entry of fs.readdirSync(source, { withFileTypes: true })) {
    const sourcePath = path.join(source, entry.name);
    const destinationPath = path.join(destination, entry.name);
    if (entry.isDirectory()) {
      copyRuntimeData(sourcePath, destinationPath);
    } else if (
      DATA_EXTENSIONS.has(path.extname(entry.name).toLowerCase()) ||
      entry.name === ".aria_webpanel_secret" ||
      entry.name === ".aria_key"
    ) {
      fs.mkdirSync(destination, { recursive: true });
      fs.copyFileSync(sourcePath, destinationPath);
    }
  }
}

function preparePackagedBackend() {
  const bundledBackend = path.join(process.resourcesPath, "aria-backend");
  const writableBackend = path.join(app.getPath("userData"), "backend");
  const versionFile = path.join(writableBackend, ".electron-backend-version");
  const installedVersion = fs.existsSync(versionFile)
    ? fs.readFileSync(versionFile, "utf8").trim()
    : "";

  if (installedVersion === app.getVersion()) return writableBackend;
  if (!fs.existsSync(bundledBackend)) {
    throw new Error("The bundled Aria backend is missing. Rebuild the desktop app with npm run dist.");
  }

  const stagedBackend = `${writableBackend}.new`;
  fs.rmSync(stagedBackend, { recursive: true, force: true });
  fs.cpSync(bundledBackend, stagedBackend, { recursive: true });
  copyRuntimeData(writableBackend, stagedBackend);
  fs.writeFileSync(path.join(stagedBackend, ".electron-backend-version"), app.getVersion());
  fs.rmSync(writableBackend, { recursive: true, force: true });
  fs.renameSync(stagedBackend, writableBackend);
  return writableBackend;
}

function getBackendContext() {
  if (backendContext) return backendContext;

  const projectRoot = path.resolve(__dirname, "..");
  const cwd = app.isPackaged ? preparePackagedBackend() : projectRoot;
  const bundledDirectory = path.join(cwd, "_internal");
  backendContext = {
    cwd,
    command: app.isPackaged
      ? path.join(cwd, process.platform === "win32" ? "Aria.exe" : "Aria")
      : process.env.ARIA_PYTHON || (process.platform === "win32" ? "python" : "python3"),
    configPath: path.join(
      app.isPackaged && fs.existsSync(bundledDirectory) ? bundledDirectory : cwd,
      "config.json",
    ),
  };
  backendConfigPath = backendContext.configPath;
  return backendContext;
}

function runBackendScript(scriptName, args = [], options = {}) {
  const context = getBackendContext();
  const scriptArgs = app.isPackaged
    ? ["--aria-run-script", scriptName, ...args]
    : [path.join(context.cwd, scriptName), ...args];
  return spawn(context.command, scriptArgs, {
    cwd: context.cwd,
    env: {
      ...process.env,
      ARIA_DESKTOP_MODE: "1",
      PYTHONUNBUFFERED: "1",
      PYTHONUTF8: "1",
      PYTHONIOENCODING: "utf-8",
      ...options.env,
    },
    stdio: options.stdio || ["ignore", "ignore", "pipe"],
    windowsHide: true,
  });
}

function startBackend(runtimeToken = null, ownerId = desktopOwnerId) {
  backendStartError = null;
  desktopAuthToken = crypto.randomBytes(32).toString("hex");
  logMessage("INFO", "Starting Aria backend.");
  backendProcess = runBackendScript("aria.py", [], {
    env: {
      ARIA_TOKEN_STDIN: runtimeToken ? "1" : "0",
      ARIA_ELECTRON_AUTH_TOKEN: desktopAuthToken,
      ARIA_DESKTOP_OWNER_ID: ownerId || "",
    },
    stdio: ["pipe", "pipe", "pipe"],
  });
  attachProcessOutput(backendProcess.stdout, "backend", "INFO");
  attachProcessOutput(backendProcess.stderr, "backend", "ERROR");
  backendProcess.stdin.on("error", () => {});
  backendProcess.stdin.end(runtimeToken ? `${runtimeToken}\n` : "");
  backendProcess.once("error", (error) => {
    backendStartError = error;
    logMessage("ERROR", `Could not start the Aria backend: ${error.message}`);
  });
  const child = backendProcess;
  child.once("exit", (code, signal) => {
    logMessage(code === 0 ? "INFO" : "ERROR", `Aria backend exited (${code ?? signal}).`);
    const intentional = isQuitting || backendProcess !== child || signal === "SIGTERM";
    if (!intentional && code !== 0 && dashboardUrl) {
      dialog.showErrorBox(
        "Aria backend stopped",
        `The Aria backend exited unexpectedly (${code ?? signal}). Restart Aria to continue.\n\nLog file: ${logFilePath || "unavailable"}`,
      );
    }
  });
}

function requestOwnerSession(port, token) {
  return new Promise((resolve, reject) => {
    const payload = JSON.stringify({ token });
    const request = http.request({
      hostname: HOST,
      port,
      path: "/__electron__/owner-session",
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Content-Length": Buffer.byteLength(payload),
      },
    }, (response) => {
      let body = "";
      response.setEncoding("utf8");
      response.on("data", (chunk) => { body += chunk; });
      response.on("end", () => {
        if (response.statusCode !== 200) {
          reject(new Error(`Owner sign-in failed with HTTP ${response.statusCode}.`));
          return;
        }
        const cookie = (response.headers["set-cookie"] || [])
          .map((value) => value.split(";", 1)[0])
          .map((value) => value.match(/^([^=]+)=(.*)$/))
          .find(Boolean);
        if (!cookie) {
          reject(new Error("The dashboard did not return an owner session cookie."));
          return;
        }
        resolve({ name: cookie[1], value: cookie[2] });
      });
    });
    request.on("error", reject);
    request.end(payload);
  });
}

async function authenticateElectronOwner() {
  if (!desktopAuthToken || !dashboardUrl) return;
  const port = Number(new URL(dashboardUrl).port);
  const cookie = await requestOwnerSession(port, desktopAuthToken);
  await session.defaultSession.cookies.set({
    url: dashboardUrl,
    name: cookie.name,
    value: cookie.value,
    path: "/",
    httpOnly: true,
    sameSite: "lax",
  });
  desktopAuthToken = null;
  logMessage("INFO", "Signed in to the locally launched dashboard as owner.");
}

async function launchNativeDashboard() {
  const executable = app.isPackaged
    ? path.join(process.resourcesPath, "aria-native", "Aria.Native.exe")
    : path.resolve(__dirname, "..", "build", "native", "Aria.Native.exe");
  if (!fs.existsSync(executable)) {
    throw new Error("The native Aria dashboard is missing. Build the Windows app with npm run build:native.");
  }

  await ensureNativeControlServer();
  logMessage("INFO", `Launching native dashboard: ${executable}`);
  nativeDashboardProcess = spawn(executable, [], {
    cwd: path.dirname(executable),
    env: {
      ...process.env,
      ARIA_DASHBOARD_URL: dashboardUrl,
      ARIA_ELECTRON_AUTH_TOKEN: desktopAuthToken || "",
      ARIA_NEEDS_TOKEN_SETUP: backendProcess && !hasSavedToken() ? "1" : "0",
      ARIA_NATIVE_CONTROL_URL: `http://${HOST}:${nativeControlServer.address().port}/`,
      ARIA_NATIVE_CONTROL_TOKEN: nativeControlToken,
    },
    stdio: ["ignore", "pipe", "pipe"],
    windowsHide: false,
  });
  attachProcessOutput(nativeDashboardProcess.stdout, "native dashboard", "INFO");
  attachProcessOutput(nativeDashboardProcess.stderr, "native dashboard", "ERROR");
  desktopAuthToken = null;
  nativeDashboardProcess.once("error", (error) => {
    logMessage("ERROR", `Could not start the native dashboard: ${error.message}`);
    dialog.showErrorBox("Aria could not start", `The native dashboard failed to launch.\n\n${error.message}`);
    app.quit();
  });
  nativeDashboardProcess.once("exit", (code, signal) => {
    nativeDashboardProcess = null;
    logMessage(code === 0 ? "INFO" : "ERROR", `Native dashboard exited (${code ?? signal}).`);
    if (code !== 0 && !isQuitting) {
      dialog.showErrorBox(
        "Aria dashboard closed unexpectedly",
        `The native dashboard exited (${code ?? signal}). Check the desktop log for details:\n\n${logFilePath || "Log file unavailable"}`,
      );
    }
    app.quit();
  });
  if (mainWindow && !mainWindow.isDestroyed()) mainWindow.close();
}

function ensureNativeControlServer() {
  if (nativeControlServer?.listening) return Promise.resolve();
  nativeControlToken = crypto.randomBytes(32).toString("hex");
  nativeControlServer = http.createServer(async (request, response) => {
    const remoteAddress = request.socket.remoteAddress || "";
    if (remoteAddress !== "127.0.0.1" && remoteAddress !== "::1" && remoteAddress !== "::ffff:127.0.0.1") {
      response.writeHead(403).end();
      return;
    }
    if (request.method !== "POST" || request.url !== "/") {
      response.writeHead(404).end();
      return;
    }
    if (request.headers.authorization !== `Bearer ${nativeControlToken}`) {
      response.writeHead(403).end();
      return;
    }

    let body = "";
    request.setEncoding("utf8");
    request.on("data", (chunk) => {
      body += chunk;
      if (body.length > 8192) {
        response.writeHead(413).end(JSON.stringify({ ok: false, error: "Setup request is too large." }));
        request.destroy();
      }
    });
    request.on("end", async () => {
      if (response.writableEnded) return;
      response.setHeader("Content-Type", "application/json");
      try {
        const payload = JSON.parse(body);
        if (payload.action !== "save-token") throw new Error("Unknown desktop setup action.");
        const token = typeof payload.token === "string" ? payload.token.trim() : "";
        if (!token || token.length > 4096 || /[\r\n]/.test(token)) {
          throw new Error("Enter a valid token.");
        }

        const identity = await saveTokenConfig(token, payload.remember === true, normalizeCaptcha(payload));
        desktopOwnerId = String(identity.id || "");
        await stopBackend();
        startBackend(payload.remember === true ? null : token, desktopOwnerId);
        dashboardUrl = await waitForDashboard();
        const authToken = desktopAuthToken;
        desktopAuthToken = null;
        const result = JSON.stringify({
          ok: true,
          dashboardUrl,
          authToken,
          ownerUsername: identity.username,
          ownerId: desktopOwnerId,
        });
        response.writeHead(200).end(result);
        const setupServer = nativeControlServer;
        nativeControlServer = null;
        nativeControlToken = null;
        setupServer?.close();
      } catch (error) {
        logMessage("ERROR", `Native token setup failed: ${error.stack || error.message}`);
        if (!response.headersSent) response.writeHead(400);
        response.end(JSON.stringify({ ok: false, error: error.message || "Could not configure Aria." }));
      }
    });
  });
  return new Promise((resolve, reject) => {
    nativeControlServer.once("error", reject);
    nativeControlServer.listen(0, HOST, resolve);
  });
}

async function waitForDashboard() {
  const deadline = Date.now() + 45000;
  while (Date.now() < deadline) {
    if (backendStartError) throw backendStartError;
    if (backendProcess.exitCode !== null || backendProcess.signalCode !== null) {
      if (backendProcess.exitCode === 0 && !hasSavedToken()) {
        logMessage("INFO", "Backend is ready for first-time token setup; opening the desktop setup screen.");
        return `http://${HOST}:${PORTS[0]}`;
      }
      throw new Error(`Aria backend exited with code ${backendProcess.exitCode ?? backendProcess.signalCode}. Check its Python dependencies and config.`);
    }
    const url = await findDashboard();
    if (url) {
      logMessage("INFO", `Dashboard is ready at ${url}.`);
      return url;
    }
    await new Promise((resolve) => setTimeout(resolve, 350));
  }
  throw new Error("Aria's dashboard did not start on ports 8080-8084.");
}

function hasSavedToken() {
  try {
    const config = JSON.parse(fs.readFileSync(backendConfigPath, "utf8"));
    const token = config.token;
    return typeof token === "string" && token.trim() !== "" && token !== "token here";
  } catch {
    return false;
  }
}

function stopBackend() {
  const child = backendProcess;
  backendProcess = null;
  if (!child || child.exitCode !== null || child.signalCode !== null) return Promise.resolve();

  return new Promise((resolve) => {
    const finish = () => {
      clearTimeout(timeout);
      resolve();
    };
    const timeout = setTimeout(finish, 5000);
    child.once("exit", finish);
    child.kill();
  });
}

function runTokenConfig(action, token = "", captcha = {}) {
  return new Promise((resolve, reject) => {
    const child = runBackendScript("token_config.py", [action], {
      stdio: ["pipe", "pipe", "pipe"],
    });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk) => {
      stdout = (stdout + chunk.toString()).slice(-4000);
    });
    child.stderr.on("data", (chunk) => {
      stderr = (stderr + chunk.toString()).slice(-4000);
    });
    child.once("error", reject);
    child.once("exit", (code, signal) => {
      if (code !== 0) {
        reject(new Error(stderr.trim() || `Token configuration helper exited (${code ?? signal}).`));
        return;
      }
      try {
        const result = JSON.parse(stdout.trim());
        if (!result.owner?.id) throw new Error("No verified account identity was returned.");
        resolve(result.owner);
      } catch (error) {
        reject(new Error(`Could not read the verified account identity: ${error.message}`));
      }
    });
    child.once("spawn", () => child.stdin.end(action === "identify" ? "" : `${token}\n${captcha.key || ""}\n${captcha.provider || ""}\n`));
    child.stdin.on("error", () => {});
  });
}

function normalizeCaptcha(payload) {
  const key = typeof payload?.captchaKey === "string" ? payload.captchaKey.trim() : "";
  if (key.length > 512 || /[\r\n]/.test(key)) throw new Error("Enter a valid captcha API key.");
  const provider = payload?.captchaProvider === "yescaptcha" ? "yescaptcha" : "nocaptchaai";
  return { key, provider };
}

function saveTokenConfig(token, remember, captcha = {}) {
  return runTokenConfig(remember ? "save" : "clear", token, captcha);
}

function identifySavedTokenOwner() {
  return runTokenConfig("identify");
}

function isDashboardUrl(value) {
  try {
    const url = new URL(value);
    return url.protocol === "http:"
      && url.hostname === HOST
      && PORTS.includes(Number(url.port))
      && !PUBLIC_SITE_PATHS.has(url.pathname);
  } catch {
    return false;
  }
}

function isPublicWebsiteUrl(value) {
  try {
    const url = new URL(value);
    return url.protocol === "http:"
      && url.hostname === HOST
      && PORTS.includes(Number(url.port))
      && PUBLIC_SITE_PATHS.has(url.pathname);
  } catch {
    return false;
  }
}

function openExternalHttps(value) {
  try {
    const url = new URL(value);
    if (url.protocol === "https:" && !url.username && !url.password) {
      shell.openExternal(url.toString());
    }
  } catch {
    return;
  }
}

function createTokenWindow() {
  if (!backendContext) return;
  if (tokenWindow && !tokenWindow.isDestroyed()) {
    tokenWindow.focus();
    return;
  }

  const options = {
    width: 900,
    height: 580,
    minWidth: 760,
    minHeight: 520,
    frame: false,
    autoHideMenuBar: true,
    backgroundColor: "#070a10",
    resizable: true,
    show: false,
    title: "Aria Desktop Setup",
    icon: path.join(__dirname, "aria.ico"),
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  };
  if (mainWindow) {
    options.parent = mainWindow;
    options.modal = true;
  }

  tokenWindow = new BrowserWindow(options);
  tokenWindow.once("ready-to-show", () => tokenWindow.show());
  tokenWindow.loadFile(path.join(__dirname, "token-setup.html"));
  tokenWindow.on("closed", () => {
    tokenWindow = null;
  });
}

function updateStartupStatus(message) {
  if (!mainWindow || mainWindow.isDestroyed()) return;
  const pageUrl = mainWindow.webContents.getURL();
  if (!pageUrl.startsWith("file:")) return;
  mainWindow.webContents.executeJavaScript(
    `window.setAriaStartupStatus(${JSON.stringify(message)})`,
  ).catch(() => {});
}

function createLoadingWindow() {
  if (mainWindow && !mainWindow.isDestroyed()) return Promise.resolve();
  mainWindow = new BrowserWindow({
    width: 640,
    height: 560,
    minWidth: 540,
    minHeight: 390,
    frame: false,
    autoHideMenuBar: true,
    backgroundColor: "#070a10",
    resizable: false,
    show: false,
    title: "Aria Desktop",
    icon: path.join(__dirname, "aria.ico"),
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });
  mainWindow.once("ready-to-show", () => mainWindow?.show());
  mainWindow.on("closed", () => {
    mainWindow = null;
  });
  return mainWindow.loadFile(path.join(__dirname, "startup.html"));
}

ipcMain.handle("setup:save-token", async (event, payload) => {
  if (!tokenWindow || event.sender !== tokenWindow.webContents) {
    return { ok: false, error: "Token setup window is not available." };
  }
  if (!backendContext) return { ok: false, error: "Aria did not start this dashboard." };

  const token = typeof payload?.token === "string" ? payload.token.trim() : "";
  const remember = payload?.remember === true;
  if (!token || token.length > 4096 || /[\r\n]/.test(token)) {
    return { ok: false, error: "Enter a valid token." };
  }

  try {
    const ownerIdentity = await saveTokenConfig(token, remember, normalizeCaptcha(payload));
    logMessage("INFO", `Verified ${ownerIdentity.username} (${ownerIdentity.id}) as the desktop owner.`);
    await stopBackend();
    logMessage("INFO", "Restarting Aria with the updated token setting.");
    startBackend(remember ? null : token);
    dashboardUrl = await waitForDashboard();
    await authenticateElectronOwner();
    if (mainWindow) await mainWindow.loadURL(new URL("/dashboard", dashboardUrl).toString());
    else createWindow();
    if (tokenWindow && !tokenWindow.isDestroyed()) tokenWindow.close();
    return { ok: true };
  } catch (error) {
    logMessage("ERROR", `Token setup failed: ${error.stack || error.message}`);
    return { ok: false, error: error.message || "Could not save the token." };
  }
});

ipcMain.on("setup:cancel", (event) => {
  if (tokenWindow && event.sender === tokenWindow.webContents) tokenWindow.close();
});

ipcMain.handle("desktop:action", async (event, action) => {
  const senderWindow = BrowserWindow.fromWebContents(event.sender);
  if (!senderWindow || (senderWindow !== mainWindow && senderWindow !== tokenWindow)) {
    return { ok: false, error: "Aria Desktop window is not available." };
  }

  switch (action) {
    case "minimize":
      senderWindow.minimize();
      return { ok: true };
    case "toggle-maximize":
      if (senderWindow !== mainWindow || !senderWindow.isMaximizable()) {
        return { ok: false, error: "This window cannot be maximized." };
      }
      if (senderWindow.isMaximized()) senderWindow.unmaximize();
      else senderWindow.maximize();
      return { ok: true, maximized: senderWindow.isMaximized() };
    case "close":
      senderWindow.close();
      return { ok: true };
    case "refresh":
      if (senderWindow !== mainWindow || !isDashboardUrl(senderWindow.webContents.getURL())) {
        return { ok: false, error: "The dashboard is not ready to refresh." };
      }
      senderWindow.webContents.reload();
      return { ok: true };
    case "set-token":
      if (senderWindow !== mainWindow || !backendProcess || !backendContext) {
        return { ok: false, error: "Token setup is available only for a dashboard started by Aria Desktop." };
      }
      createTokenWindow();
      return { ok: true };
    case "open-dashboard":
      if (senderWindow !== mainWindow || !dashboardUrl) {
        return { ok: false, error: "The dashboard is not available yet." };
      }
      await shell.openExternal(new URL("/dashboard", dashboardUrl).toString());
      return { ok: true };
    case "quit":
      if (senderWindow !== mainWindow) return { ok: false, error: "This action is unavailable in setup." };
      app.quit();
      return { ok: true };
    default:
      return { ok: false, error: "Unknown desktop action." };
  }
});

function createWindow() {
  if (!mainWindow || mainWindow.isDestroyed()) {
    mainWindow = new BrowserWindow({
      width: 1280,
      height: 820,
      minWidth: 760,
      minHeight: 520,
      frame: false,
      autoHideMenuBar: true,
      backgroundColor: "#070a10",
      title: "Aria Desktop",
      icon: path.join(__dirname, "aria.ico"),
      webPreferences: {
        preload: path.join(__dirname, "preload.cjs"),
        contextIsolation: true,
        nodeIntegration: false,
        sandbox: true,
      },
    });
    mainWindow.on("closed", () => {
      mainWindow = null;
    });
  } else {
    mainWindow.setResizable(true);
    mainWindow.setMinimumSize(760, 560);
    mainWindow.setSize(1280, 820);
    mainWindow.center();
  }

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (isPublicWebsiteUrl(url)) shell.openExternal(url);
    else openExternalHttps(url);
    return { action: "deny" };
  });
  mainWindow.webContents.on("will-navigate", (event, url) => {
    if (isDashboardUrl(url)) return;
    event.preventDefault();
    if (isPublicWebsiteUrl(url)) shell.openExternal(url);
    else openExternalHttps(url);
  });
  mainWindow.webContents.on("page-title-updated", (event) => {
    event.preventDefault();
    mainWindow.setTitle("Aria Desktop");
  });
  let loadRetries = 0;
  mainWindow.webContents.on("did-fail-load", (event, errorCode, errorDescription, validatedURL, isMainFrame) => {
    // -3 is a navigation aborted by a newer load; not a real failure.
    if (!isMainFrame || errorCode === -3 || loadRetries >= 5) return;
    loadRetries += 1;
    logMessage("WARN", `Dashboard load failed (${errorDescription}); retry ${loadRetries}/5.`);
    setTimeout(() => {
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.loadURL(new URL("/dashboard", dashboardUrl).toString());
      }
    }, 1000 * loadRetries);
  });
  mainWindow.webContents.on("did-finish-load", () => {
    loadRetries = 0;
  });
  mainWindow.loadURL(new URL("/dashboard", dashboardUrl).toString());
}

function installMenu() {
  Menu.setApplicationMenu(Menu.buildFromTemplate([
    {
      label: "Aria Desktop",
      submenu: [
        {
          label: "Set / Change Token...",
          click: async () => {
            if (!backendProcess || !backendContext) {
              await dialog.showMessageBox({
                type: "info",
                message: "Aria is using a dashboard that was already running.",
                detail: "Start Aria from this app to configure its token here.",
              });
              return;
            }
            createTokenWindow();
          },
        },
        {
          label: "Open Dashboard in Browser",
          click: () => dashboardUrl && shell.openExternal(new URL("/dashboard", dashboardUrl).toString()),
        },
        {
          label: "Open Aria Website",
          click: () => dashboardUrl && shell.openExternal(dashboardUrl),
        },
        { type: "separator" },
        { role: "quit" },
      ],
    },
    { role: "editMenu" },
    { role: "viewMenu" },
    { role: "windowMenu" },
  ]));
}

app.whenReady().then(async () => {
  try {
    initializeLogging();
    logMessage("INFO", "Starting Aria desktop.");
    installMenu();
    await createLoadingWindow();
    logMessage("INFO", "Checking for an existing Aria web panel.");
    updateStartupStatus("Looking for a local Aria dashboard...");
    dashboardUrl = await findDashboard();
    if (!dashboardUrl) {
      logMessage("INFO", "No existing panel found; starting a private backend.");
      updateStartupStatus("Starting your private Aria runtime...");
      getBackendContext();
      if (hasSavedToken()) {
        try {
          const ownerIdentity = await identifySavedTokenOwner();
          desktopOwnerId = String(ownerIdentity.id || "");
          logMessage("INFO", `Verified saved account ${ownerIdentity.username} (${ownerIdentity.id}) as the desktop owner.`);
        } catch (error) {
          logMessage("ERROR", `Could not refresh the saved token owner identity: ${error.message}`);
        }
      }
      startBackend();
      dashboardUrl = await waitForDashboard();
      updateStartupStatus("Signing into your owner dashboard...");
      await authenticateElectronOwner();
    } else {
      logMessage("INFO", `Using existing panel at ${dashboardUrl}; its normal login remains enabled.`);
    }
    updateStartupStatus("Opening your dashboard...");
    createWindow();
    if (backendProcess && !hasSavedToken()) {
      logMessage("INFO", "No saved token found; opening token setup.");
      createTokenWindow();
    }
  } catch (error) {
    logMessage("ERROR", `Aria could not start: ${error.stack || error.message}`);
    dialog.showErrorBox("Aria could not start", `${error.message}\n\nLog file: ${logFilePath || "unavailable"}`);
    app.quit();
  }
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0 && dashboardUrl) createWindow();
});

app.on("before-quit", () => {
  isQuitting = true;
  logMessage("INFO", "Closing Aria desktop.");
  nativeControlServer?.close();
  if (nativeDashboardProcess && nativeDashboardProcess.exitCode === null) nativeDashboardProcess.kill();
  if (backendProcess && backendProcess.exitCode === null) backendProcess.kill();
});

app.on("window-all-closed", () => {
  if (nativeDashboardProcess) return;
  if (process.platform !== "darwin") app.quit();
});