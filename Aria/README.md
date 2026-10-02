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

The desktop app opens a branded startup window immediately, then expands that same window into the dashboard when the backend is ready. During token setup and startup with a remembered token, Aria verifies the account profile and saves that account's ID as the local panel owner; it never prints or logs the token. When Electron starts its own backend, it signs into that dashboard as **Owner**, not merely Admin, and the owner account is not treated as an unlinked hosted client. An already-running web panel keeps its normal login. Remembered tokens are saved through Aria's encrypted config; if you turn off **Remember token**, Aria uses it only for the current run. Hosted clients each load their own copied config and RPC profile store; the controller's RPC presets are not copied into child instances. Each hosted instance has one active child process, with up to three automatic restarts only after that child exits. Use **Aria Desktop > Set / Change Token...** to update the token later, **Open Dashboard in Browser** for `/dashboard`, or **Open Aria Website** for the public home page. Closing the desktop app stops a backend it started, but does not stop a backend that was already running.

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

#### 2. Get into the project and app folder

If you do not already have the project source on your PC, open PowerShell and clone it:

```powershell
git clone https://github.com/misconsiderations/Aria.git
cd Aria
```

If you already have the project source, do not clone it again. In PowerShell, change to its folder instead. For example, replace this sample path with the folder where you keep your copy:

```powershell
cd "C:\path\to\your\Aria"
```

The repository has an outer project folder and an inner `Aria` app folder. This command detects which one you opened and enters the app folder if needed:

```powershell
if (-not (Test-Path .\package.json)) {
	if (Test-Path .\Aria\package.json) {
		Set-Location .\Aria
	} else {
		throw "This is not the Aria source folder. Open the folder containing package.json."
	}
}
Test-Path .\package.json
```

The last command must print `True`. If you only have the installed Aria app and not its source folder, follow the clone steps above; the installed app does not contain the files needed to build a new installer.

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

The installer and Windows app use the Aria favicon as their icon. The installer is written to the `release` folder. Check for it with:

```powershell
Get-ChildItem .\release\*.exe
```

For this version, the file is named `Aria Setup 1.0.0.exe`. Open it and follow the installer prompts. Only run an installer you built yourself or obtained from a source you trust; an unsigned personal build may show a Windows publisher warning.

#### 6. Start Aria for the first time

Launch Aria from the Start menu. The app includes its own frozen Python backend, so Python and Node.js are not needed on PCs where you install the finished app. When prompted, enter your Aria token and choose whether to remember it. Aria verifies the account and records its ID as the local owner. If a token was already saved, Aria refreshes that identity before starting its backend. If Electron starts its own backend, it opens the dashboard as owner without asking for the web-panel login. If a web panel was already running before Electron opened, that panel keeps its normal login.

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

### Update Aria on an existing Windows PC

Updating the source folder does not update an already-installed `.exe`. First, the new source changes must be committed and pushed to the GitHub branch you use. Then close Aria on the Windows PC and open PowerShell inside your existing Git checkout.

Pull the published changes and enter the app folder if PowerShell opened in the outer repository folder:

```powershell
git pull
if (-not (Test-Path .\package.json)) {
	if (Test-Path .\Aria\package.json) {
		Set-Location .\Aria
	} else {
		throw "Open the Aria repository folder containing package.json."
	}
}
Test-Path .\package.json
```

The last command must print `True`. Before publishing a desktop update, increase the app version in `package.json` and the root entry in `package-lock.json` (for example, `1.0.0` to `1.0.1`) and push that version change with the source. The packaged backend uses this version to decide whether it must be refreshed. If the branch you pulled already has a higher version, do not bump it again on the PC.

Activate the existing build environment, rebuild, and install the new setup file:

```powershell
.\.venv-build\Scripts\Activate.ps1
python -m pip install -r requirements.txt aiohttp curl-cffi colorama pyinstaller
npm install
npm run dist
Get-ChildItem .\release\*.exe
```

Run the new `Aria Setup <version>.exe` and install it over the existing Aria installation. Use the same Windows account so Aria can retain its saved settings and runtime data. If you only need updated source files and do not need a new installed app, stop after `git pull`.

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
