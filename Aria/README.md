# Aria
Auto update repo for Aria selfbot!

Install the Python runtime dependencies from this directory with:

```bash
python -m pip install -r requirements.txt
```

Real slash command bot setup: see `REAL_SLASH_SETUP.md`.

## MongoDB backend

Aria can store hot runtime state in MongoDB instead of repeatedly writing JSON files.

Enable it in `config.json`:

```json
{
	"mongo_enabled": true,
	"mongo_uri": "mongodb://127.0.0.1:27017",
	"mongo_database": "aria",
	"mongo_collection": "app_state",
	"mongo_timeout_ms": 1500
}
```

Install the driver in the active Python environment:

```bash
pip install pymongo
```

Current Mongo-backed runtime datasets:

- `history_data`
- `account_stats`
- `analytics`
- `dashboard_users`
- `access_requests`

If MongoDB is disabled or unavailable, Aria falls back to the existing JSON files automatically.

## Electron desktop app

Public browser and mobile access notes are on the website's `/docs` page.

The Electron app opens only the protected dashboard at `/dashboard`; public pages such as `/`, `/home`, `/features`, `/get-token`, `/terms`, and `/privacy` remain website pages and open in the regular browser. Both the dashboard and website remain available on the local web server at `http://127.0.0.1:8080` (or the next available port through `8084`).

For development, install the Python dependencies above, then run:

```bash
npm install
npm start
```

The desktop app starts the Aria bot executable when packaged (or `aria.py` during development) if no dashboard is already running. When it starts its own backend, Electron signs into that local dashboard as the owner automatically; an already-running web panel keeps its normal login. On first launch, a token setup window opens. Remembered tokens are saved through Aria's encrypted config; if you turn off **Remember token**, Aria uses it only for the current run. The token is never sent to renderer storage or printed to a terminal. Use **Aria > Set / Change Token...** to update it later, **Open Dashboard in Browser** for `/dashboard`, or **Open Aria Website** for the public home page. Closing the desktop app stops a backend it started, but does not stop a backend that was already running.

Electron prints startup and backend output when launched from a terminal. It also writes `logs/aria-desktop.log` under Electron's user data folder; the full path is printed during startup and shown if startup fails.

### Build the Windows installer (.exe), step by step

Follow these steps on a Windows PC connected to the internet. Build from Windows; this project does not create the Windows installer from Linux or macOS.

#### 1. Install the build tools

Install these tools before opening PowerShell:

- **Git for Windows**, if you still need to download the project.
- **Node.js LTS**, version 22.12 or newer. npm is included with Node.js.
- **Python 3.11**. Keep the Python Launcher (`py`) enabled in the installer.

After installing them, close and reopen PowerShell. Check that the commands are available:

```powershell
node --version
npm --version
py -3.11 --version
```

Each command should print a version. If `node`, `npm`, or `py` is not recognized, finish its installation and reopen PowerShell before continuing.

#### 2. Download the project and enter the app folder

If the project is not on your PC yet, open PowerShell and clone it:

```powershell
git clone https://github.com/misconsiderations/Aria.git
cd Aria
```

This repository keeps the desktop app in a second folder also named `Aria`. Enter that folder, then confirm it is the one containing `package.json`:

```powershell
cd .\Aria
Test-Path .\package.json
```

The last command should print `True`. If you already downloaded the project, use `cd` to enter that same inner `Aria` folder instead.

#### 3. Create the Python build environment

Run these commands from the folder where `Test-Path .\package.json` printed `True`:

```powershell
py -3.11 -m venv .venv-build
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv-build\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt aiohttp curl-cffi colorama pyinstaller
```

The execution-policy command only changes this PowerShell window. The `(.venv-build)` prefix in the prompt means the build environment is active.

#### 4. Install Electron and build the installer

Still in the same folder, run:

```powershell
npm install
npm run dist
```

The first build downloads dependencies and freezes the Python backend, so it can take several minutes. Keep the internet connection active and wait for the command to finish without closing PowerShell.

#### 5. Find and install the `.exe`

The installer is written to the `release` folder. Check for it with:

```powershell
Get-ChildItem .\release\*.exe
```

For this version, the file is named `Aria Setup 1.0.0.exe`. Open it and follow the installer prompts. Only run an installer you built yourself or obtained from a source you trust; an unsigned personal build may show a Windows publisher warning.

#### 6. Start Aria for the first time

Launch Aria from the Start menu. The app includes its own frozen Python backend, so Python and Node.js are not needed on PCs where you install the finished app. When prompted, enter your Aria token and choose whether to remember it. If Electron starts its own backend, it opens the dashboard as owner without asking for the web-panel login. If a web panel was already running before Electron opened, that panel keeps its normal login.

#### 7. View startup logs

For live terminal output while developing, run `npm start` from the app folder in PowerShell. The installed Windows app always writes `aria-desktop.log` under its Electron user-data folder. To find the exact path, search the usual Windows app-data folders:

```powershell
Get-ChildItem "$env:APPDATA", "$env:LOCALAPPDATA" -Filter aria-desktop.log -Recurse -ErrorAction SilentlyContinue |
	Select-Object -First 1 -ExpandProperty FullName
```

To follow the log live after finding it, run `Get-Content "FULL_PATH_FROM_PREVIOUS_COMMAND" -Wait`.

The installer bundles the backend and app together. The packaged backend and its runtime data are copied to the user's writable application-data folder, and existing JSON, text, and database state is retained when the app version changes.

#### Common fixes

- If PowerShell says script execution is disabled, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in that window and activate `.venv-build` again.
- If `npm run dist` says Python or PyInstaller is missing, make sure `(.venv-build)` appears in the prompt, then rerun the Python install commands in step 3.
- If Node, npm, or Python was installed while PowerShell was open, close PowerShell, open it again, and repeat the version checks in step 1.

## Dashboard session key

The web dashboard creates a private 256-bit session-signing key in
`Aria/.aria_webpanel_secret` on first start and reuses it across restarts. Keep
this runtime file private and out of backups shared with others. To provide a
managed key instead, set `ARIA_WEBPANEL_SECRET` in the process environment.

## RPC presets and message logger

Aria supports named activity presets and timed rotations through the existing
RPC engine:

```text
<prefix>rpc preset save desk
<prefix>rpc preset list
<prefix>rpc preset load desk
<prefix>rpc rotation set 45 desk,away
<prefix>rpc rotation start
<prefix>rpc rotation stop
```

Message logging is disabled by default. Enable it with `<prefix>logger on`, add
terms with `<prefix>logger add release notes`, and set an optional scope with
`<prefix>logger scope dms`, `guilds`, `guild <id>`, or `channel <id>`. The
dashboard can also configure mention, edit, delete, and own-message filtering.
The live feed is bounded to 400 events and held in memory; only its settings
are written to `Aria/message_logger.json`.

These RPC profile and logger workflows are inspired by
[Beyond](https://github.com/kzfq/beyond), which is MIT-licensed. Aria keeps its
own Discord API and gateway implementation.
