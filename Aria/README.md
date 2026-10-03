# Aria

Aria is a Python Discord client with a local web dashboard, hosted-instance
management, RPC activity tools, analytics, and message logging.

> **Account and platform notice:** Aria connects using Discord account
> credentials. Keep tokens private, use the app only with accounts you control,
> and review Discord's current terms and policies before connecting. A token
> grants access to its account and must be handled like a password.

## Project layout

The repository contains the Aria application in the `Aria` subdirectory:

- `main.py`, `aria.py`, and related Python modules implement the runtime.
- `webpanel.py` provides the local dashboard API and browser dashboard.
- `web_ui/` contains the browser dashboard.
- `electron/` contains the desktop launcher and setup resources.
- `Aria.Native/` contains the Windows WinUI dashboard.
- `host.py` manages hosted client processes.

Run commands below from the application directory—the directory containing
`package.json` and `requirements.txt`.

## Requirements

For the Python runtime:

- Python 3.11 or later
- The Python packages in `requirements.txt`

For desktop development:

- Node.js 22.12 or later and npm
- On Windows, the .NET 8 SDK or later to build the native WinUI dashboard
- On Windows, Python 3.11 and PyInstaller to package the backend

The finished Windows installer includes the Python backend and native
dashboard. Users installing that installer do not need to install Python, Node,
or the .NET SDK.

## Run Aria from source

From the application directory, create and activate a virtual environment and
install the runtime dependencies:

```bash
python -m venv .venv
```

On Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python aria.py
```

On macOS or Linux:

```bash
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python aria.py
```

Aria reads its account and runtime settings from its local configuration.
Follow the prompts shown by the application and do not publish configuration
files containing tokens or other credentials.

## Dashboard and desktop app

### Browser dashboard

The Python service serves the browser dashboard locally, usually at
`http://127.0.0.1:8080`. If that port is occupied, Aria tries ports 8081 through
8084. Sign in with the dashboard account for the relevant instance. Public
website pages and the protected dashboard are separate; public browser and
mobile-access information is available from the website's `/docs` page.

The browser dashboard remains HTML-based and is available independently of the
desktop app.

### Windows native desktop app

On Windows, Aria's dashboard is a **native WinUI application**. It is built
from XAML and uses Windows controls; it does not embed or render the HTML
dashboard. The Python service still runs locally to provide the Discord
runtime and authenticated API.

Current native dashboard sections:

- **Overview:** runtime connection, account, uptime, command, and hosted-client
  summary.
- **Hosted instances:** connect, view, restart, and disconnect hosted clients.
- **Owner tools:** account summary and password-reset request review.

Other sections in the browser dashboard have not yet been ported to WinUI. They
remain available in the browser dashboard.

The Windows desktop application uses Aria's icon and a native token setup
screen. Token setup verifies the account, then sends the token to the local
launcher through a short-lived, authenticated localhost channel. The token is
not written to application logs. Choose **Remember token** to save it in
Aria's encrypted local configuration; otherwise it is used only for the
current run. A token's verified account ID is used to identify the desktop
runtime owner. The configured secondary owner ID is
`465513550312505344`.

If a local Aria service is already running, the desktop app connects to it.
Sign in with the dashboard account if that service does not have a desktop
owner session.

### Linux and macOS desktop

Linux and macOS use the existing Electron dashboard shell. The native WinUI
dashboard is Windows-only; a non-Windows build does not produce a WinUI
executable.

To start the desktop shell during development:

```bash
npm install
npm start
```

## Hosted instances and owner access

Hosted clients run as separate processes. Their command permissions are scoped
to the requester and token account for that client, rather than granting every
hosted client the main bot's global-owner access. The main instance retains
configured global-owner controls.

The hosted-process watchdog retries after exits and failed launches, using
interruptible exponential backoff capped at five minutes. A restart is not
guaranteed to connect successfully; check the hosted-client status and runtime
logs if a client continues failing.

Hosted instances use their own runtime configuration and RPC profile store.
The controller's RPC presets are not copied into child instances.

## Build the Windows installer

Build the Windows installer on a Windows PC. The WinUI XAML compiler is
Windows-only, so building this target from Linux or macOS is not supported.

### 1. Install build tools

Install:

- Git for Windows, if you need to clone the repository
- Node.js 22.12 or later (npm is included)
- Python 3.11 with the Python Launcher (`py`)
- The .NET 8 SDK or later

Open a new PowerShell window and check that the commands are available:

```powershell
node --version
npm --version
py -3.11 --version
dotnet --version
```

### 2. Open the application directory

Clone the repository if needed, or open your existing checkout:

```powershell
git clone https://github.com/misconsiderations/Aria.git
cd Aria
```

The repository has an outer folder and an inner application folder. Enter the
inner folder when `package.json` is not in the current directory:

```powershell
if (-not (Test-Path .\package.json)) {
    if (Test-Path .\Aria\package.json) {
        Set-Location .\Aria
    } else {
        throw "Open the Aria application folder containing package.json."
    }
}
Test-Path .\package.json
```

The final command should print `True`.

### 3. Install Python build dependencies

Create and activate an isolated build environment:

```powershell
py -3.11 -m venv .venv-build
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv-build\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pyinstaller
```

The execution-policy command only applies to the current PowerShell window.
Check that `(.venv-build)` appears in the prompt before continuing.

### 4. Build the installer

From the same application directory:

```powershell
npm install
npm run dist
```

This builds the Python backend, publishes the native WinUI app, and packages
the Windows installer. The first build downloads dependencies and may take
several minutes. Keep the internet connection active.

To build just the native WinUI dashboard:

```powershell
npm run build:native
```

### 5. Install and launch

The installer is written to `release`. Find the generated file with:

```powershell
Get-ChildItem .\release\*.exe
```

The filename includes the application version, for example
`Aria Setup 1.0.0.exe`. The NSIS installer allows you to choose an installation
directory and creates Aria shortcuts in the Start menu and on the desktop.
Run the installer and follow its prompts. An unsigned personal build may show
a Windows publisher warning; only install builds from sources you trust.

Launch Aria from the Start menu or desktop shortcut. On first launch, enter the
account token in the native setup window and select whether to remember it.
The app then starts its local Python service and opens the native dashboard.
After installation, Python, Node.js, and the .NET SDK are not needed to run the
packaged application.

## Logs and local data

When launched from a terminal during development, Electron writes startup and
backend output to the terminal. It also writes `aria-desktop.log` in its
Electron user-data directory. Search for the log in PowerShell with:

```powershell
Get-ChildItem "$env:APPDATA", "$env:LOCALAPPDATA" -Filter aria-desktop.log -Recurse -ErrorAction SilentlyContinue |
    Select-Object -First 1 -ExpandProperty FullName
```

To find and follow the log in one step:

```powershell
$log = Get-ChildItem "$env:APPDATA", "$env:LOCALAPPDATA" -Filter aria-desktop.log -Recurse -ErrorAction SilentlyContinue |
    Select-Object -First 1 -ExpandProperty FullName
if ($log) { Get-Content $log -Wait } else { Write-Error "Aria log file was not found." }
```

Do not paste logs or configuration files publicly without checking them for
account identifiers, local paths, or other private information. Aria's
dashboard session-signing key is stored in
`Aria/.aria_webpanel_secret` and is reused across restarts. Keep this runtime
file private. A managed key can be supplied through the `ARIA_WEBPANEL_SECRET`
environment variable.

The packaged backend and its runtime data are kept in the user's writable
application-data folder. When the packaged app version changes, Aria stages
the new backend and retains existing supported data files.

## MongoDB backend (optional)

MongoDB can store selected frequently updated runtime state. MongoDB is
optional; if disabled or unavailable, Aria falls back to its existing JSON
storage.

Install the driver if it is not already present in the active environment:

```bash
python -m pip install pymongo
```

Example configuration:

```json
{
  "mongo_enabled": true,
  "mongo_uri": "mongodb://127.0.0.1:27017",
  "mongo_database": "aria",
  "mongo_collection": "app_state",
  "mongo_timeout_ms": 1500
}
```

Mongo-backed datasets currently include `history_data`, `account_stats`,
`analytics`, `dashboard_users`, and `access_requests`.

## RPC presets and message logger

RPC presets and timed rotations use the existing command engine. Replace
`<prefix>` with the command prefix configured for your instance:

```text
<prefix>rpc preset save desk
<prefix>rpc preset list
<prefix>rpc preset load desk
<prefix>rpc rotation set 45 desk,away
<prefix>rpc rotation start
<prefix>rpc rotation stop
```

Message logging is disabled by default. Enable it with `<prefix>logger on`,
add terms with `<prefix>logger add release notes`, and optionally scope it
with `<prefix>logger scope dms`, `guilds`, `guild <id>`, or `channel <id>`.
The dashboard can configure mention, edit, delete, and own-message filtering.
The live feed is bounded to 400 in-memory events; only its settings are written
to `Aria/message_logger.json`.

## Updating an installed Windows app

Pulling source changes does not update an already-installed application. To
publish an update, update the version in `package.json` and the root entry in
`package-lock.json`, then build and distribute a new installer. The packaged
backend uses the application version to determine when it should be refreshed.

On the target Windows PC, close Aria and update the source checkout:

```powershell
git pull
```

If needed, enter the inner application directory using the folder-detection
commands from the installer instructions. Then rebuild:

```powershell
.\.venv-build\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip install pyinstaller
npm install
npm run dist
Get-ChildItem .\release\*.exe
```

Run the new `Aria Setup <version>.exe` under the same Windows account and
install it over the existing app to retain that account's application data.

## Credits

The RPC profile and message-logger workflows were informed by the
[Beyond project](https://github.com/kzfq/beyond), which is MIT-licensed. Aria
maintains its own implementation.
