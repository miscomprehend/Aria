# Aria

Aria is a Python Discord client with an Electron desktop app, a local browser
dashboard, hosted-instance management, presence tools, analytics, and message
logging.

> **Account and platform notice:** Aria connects with account credentials.
> Use it only with accounts you control, follow Discord's current terms and
> policies, and treat an account token like a password. Never paste a token
> into an issue, chat, screenshot, log, or source file.

## Contents

- [Download & Run](#download--run)
- [What is included](#what-is-included)
- [Requirements](#requirements)
- [Quick start: desktop app](#quick-start-desktop-app)
- [Run the Python runtime directly](#run-the-python-runtime-directly)
- [Dashboard guide](#dashboard-guide)
- [Build a Windows Electron installer](#build-a-windows-electron-installer)
- [Test and verify changes](#test-and-verify-changes)
- [Configuration and local data](#configuration-and-local-data)
- [Optional MongoDB storage](#optional-mongodb-storage)
- [Feature walkthroughs](#feature-walkthroughs)
- [Update the source checkout](#update-the-source-checkout)
- [Update an installed Windows app](#update-an-installed-windows-app)
- [Clean old files or uninstall Aria](#clean-old-files-or-uninstall-aria)
- [Troubleshooting](#troubleshooting)
- [Project layout](#project-layout)

## Download & Run

Download the latest Electron desktop app from
[GitHub Releases](https://github.com/miscomprehend/Aria/releases/latest), then choose the package for your platform:

| Platform | Release file | Instructions |
| --- | --- | --- |
| Windows x64 Installer | `Aria-Windows-x64-Setup-<version>.exe` | Run the installer and follow the prompts. It creates Start menu and desktop shortcuts. |
| Windows x64 Portable | `Aria-Windows-x64-Portable-<version>.exe` | Download and run the file. No installation is needed. |
| macOS Apple Silicon | `Aria-MacOS-arm64-<version>.dmg` | Open the DMG and drag Aria to Applications. If macOS blocks it, run the quarantine-removal command below. |
| Linux x86_64 Installer | `Aria-Linux-x86_64-<version>.deb` | Install the Debian package with the command below. |
| Linux x86_64 Portable | `Aria-Linux-x86_64-<version>.AppImage` | Make the AppImage executable and run it with the commands below. |

On macOS, remove the quarantine attribute if needed:

```bash
xattr -dr com.apple.quarantine /Applications/Aria.app
```

On Debian/Ubuntu, install the package:

```bash
sudo apt install ./Aria-Linux-x86_64-<version>.deb
```

On any other Linux x86_64 distribution, run the AppImage:

```bash
chmod +x Aria-Linux-x86_64-<version>.AppImage
./Aria-Linux-x86_64-<version>.AppImage
```

Every download above is the Electron desktop app. Electron is bundled, so you
do not need to install it separately. For a source checkout, install the
project's local Electron dependency with `npm ci` and start it with
`npm start`.

On first launch, enter your account token in Aria's setup window. Releases are
built by [`release.yml`](../.github/workflows/release.yml) when a `v*` tag is
pushed.

## What is included

Aria has three parts that can run together:

1. **Python runtime:** connects the configured account and hosts command and
   activity features.
2. **Local web service:** serves the authenticated dashboard API, browser
   dashboard, and public information pages.
3. **Desktop shell:** Electron manages startup and setup, then shows the
   Aria web dashboard in its own window on Windows, Linux and macOS.
Use its **Browser panel** and **Website** buttons to open the full browser
dashboard or public site in your system browser.

Some useful runtime modules:

- RPC activities and presets: `main.py`, `rpc_activity.py`, and
  `rpc_profiles.py`.
- Message logging: `main.py` and `message_logger.py`.
- Profile editing: `profile_avatar.py` and `profile_details.py`.
- Group-DM protection and friend tools: `anti_gc_trap.py` and
  `friends_tools.py`.
- Group, guild, and reaction utilities: `group_chat_tools.py`,
  `guild_tools.py`, and `superreact_commands.py`.
- Hosted processes: `host.py` and `self_hosting.py`.

Command Controls manages anti-GC settings and opt-in per-user auto-replies for
the active runtime. Those automation settings are session-local; auto-replies
are cleared when the runtime stops. Message-logger settings are persisted
separately. Bulk relationship removal and mass group-chat removal are not
exposed in the main command surface.

## Requirements

### Running from source

- Python 3.11 or later, with `venv` support.
- Node.js 22.12 or later and npm for the desktop shell.
- Internet access for first-time dependency installation and account
  connection.

On Windows, `install.ps1` currently checks for the .NET 8 SDK or later as a
preflight requirement. The Electron app and packaged releases do not use .NET;
manual source setup does not require it.

The packaged desktop releases include Electron and the Python backend. End
users do not need to install Python, Node.js, Electron, or .NET to run a
release build.

### Runtime and optional component dependencies

The main runtime uses packages from `requirements.txt`. Pillow is included for
image-editing commands. The separate modules in `aria_backend/` use a
different dependency set and are not the backend started by the current
desktop launcher. To install those optional/separate components:

```bash
python -m pip install -r aria_backend/requirements.txt
```

That file pins `modifyself` to a source revision because it is not published
on PyPI. Keep this dependency separate from the main runtime environment
unless you intend to work on those components.

## Quick start: desktop app

This is the complete setup from a fresh source checkout. Install Python 3.11+
and Node.js 22.12+ with npm first. Clone the repository and enter the inner
application directory, which contains `package.json` and `requirements.txt`:

```bash
git clone https://github.com/miscomprehend/Aria.git
cd Aria/Aria
```

Then follow the setup steps for your operating system below. The setup scripts
install the Python and npm dependencies and launch the Electron desktop app;
they do not install system prerequisites such as Python or Node.js.

### Windows PowerShell

1. Install Python 3.11+ and Node.js 22.12+. If you use `install.ps1`, also
   install the .NET 8 SDK or later for its preflight check.
2. Open PowerShell in the application directory.
3. Run the development setup script. If your PowerShell policy blocks local
   scripts, the process-scoped bypass below does not change the machine policy:

   ```powershell
   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
   .\install.ps1
   ```

   The script creates `.venv`, installs Python and npm dependencies, builds
   Electron dependencies, and starts the desktop app. It does not install
   system packages or request administrator access.
4. On first launch, enter the account token in Aria's setup window. Choose
   whether to remember it on this device. Aria verifies the account before
   starting the runtime.
5. When startup completes, use the Electron desktop app. Open the browser
   dashboard from its menu when you need the full browser-based control
   surface.

To perform setup manually instead of running the script:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
npm ci
npm start
```

`npm start` starts the Electron desktop app, which starts or discovers the
local service and opens the dashboard.

### Linux or macOS

1. Install Python 3.11+, Node.js 22.12+, and npm using your operating system's
   preferred package manager.
2. Open a terminal in the application directory.
3. Run the setup script:

   ```bash
   bash install.sh
   ```

   It creates `.venv`, installs Python and npm dependencies, and starts the
   Electron desktop shell. It does not install operating-system packages.
4. Complete the account setup in the desktop window.
5. Open the browser dashboard from Aria's desktop menu when you need the
   browser-based control surface.

To set up and run manually:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
npm ci
npm start
```

`npm ci` installs Electron into this project's `node_modules`; it does not
install Electron system-wide. Remove `node_modules` as described in **B** if
you want to remove the source checkout's Electron and other npm dependencies.

### Start without the desktop shell

To run only the Python runtime, install `requirements.txt` in an active
environment and run:

```bash
python aria.py
```

The runtime reads local `config.json` settings and may prompt for initial
configuration. Its dashboard, if started by the runtime, is usually available
at `http://127.0.0.1:8080`. If that port is busy, Aria tries ports 8081 through
8084. Do not commit `config.json`; it may contain credentials.

## Dashboard guide

### Browser dashboard and public pages

The local service hosts both public information pages and an authenticated
dashboard. The dashboard is available at:

```text
http://127.0.0.1:8080/dashboard
```

If the service selected another port, use that port instead. Sign in using the
dashboard account for that instance. Public pages such as the home page and
documentation are separate from the protected dashboard.

The browser dashboard remains HTML-based and can be used independently of the
Electron desktop app. The desktop app opens this dashboard in its own window;
use the in-app menu to open it in your system browser when needed.

### Where account tokens are stored

Selecting **Remember token** saves the token in Aria's local encrypted
configuration. Unchecking it uses the token for the current run but does not
save it in `config.json`. Treat the application-data directory as private
regardless: it contains account and runtime state. Do not send its contents to
other people.

## Build a Windows Electron installer

Build the Electron installer on Windows. The installer bundles the Electron
desktop app and its Python backend; no separate dashboard build is needed.

### 1. Install build tools

Install:

- Git for Windows, if you need to clone the repository.
- Node.js 22.12 or later (npm is included).
- Python 3.11 and the Python Launcher (`py`).

Open a new PowerShell window and verify the tools:

```powershell
node --version
npm --version
py -3.11 --version
```

### 2. Clone the repository and enter the application directory

```powershell
git clone https://github.com/miscomprehend/Aria.git
Set-Location .\Aria\Aria
```

For an existing clone, change into its inner `Aria` directory. Confirm that
the expected manifests are present:

```powershell
Test-Path .\package.json
Test-Path .\requirements.txt
```

Both commands should print `True`. Do not run the following build commands
from the repository's outer directory.

### 3. Create an isolated Python build environment

```powershell
py -3.11 -m venv .venv-build
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv-build\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pyinstaller
```

Check that `(.venv-build)` appears in the PowerShell prompt, then verify that
the environment is the one you expect:

```powershell
python --version
python -m pip show pyinstaller
```

The packaged backend is built from this environment.

### 4. Install Node dependencies

```powershell
npm ci
```

`npm ci` installs the exact dependency versions in `package-lock.json`. If
you intentionally changed `package.json`, update the lockfile with `npm
install` and commit both files.

### 5. Build and package

```powershell
npm run dist
```

The script builds the Python backend with PyInstaller and packages the
Electron app with electron-builder. The first build may download dependencies
and take several minutes. To build only the Python backend:

```powershell
npm run build:backend
```

The complete installer is written to `release`. Confirm that an installer
exists:

```powershell
Get-ChildItem .\release\*.exe
```

### 6. Install and launch the result

Run the generated `Aria Setup <version>.exe` and follow the installer. The
NSIS installer allows a custom installation directory and creates Start menu
and desktop shortcuts. An unsigned personal build can display a Windows
publisher warning; install only builds you trust.

Launch Aria from a shortcut. On first launch, complete token setup. The
installed application includes Electron and its Python backend; the build
tools are not required on the target PC.

### Automated Windows build

The repository workflow at
[`../.github/workflows/windows-desktop.yml`](../.github/workflows/windows-desktop.yml)
runs on Windows for relevant pushes, pull requests, or manual dispatch. It
checks icon assets, runs the Python unittest suite, builds the installer with
`npm run dist`, and uploads the generated installer as a workflow artifact.
Inspect the workflow run and download the artifact from its **Artifacts**
section.

## Test and verify changes

Run the commands from the application directory.

### Python tests

Activate the project environment, then run the complete unittest suite:

```bash
python -m unittest discover
```

On Windows, use `.\.venv\Scripts\Activate.ps1` first. On Linux/macOS, use
`. .venv/bin/activate`.

To run the focused dashboard/security tests:

```bash
python -m unittest test_webpanel_controls test_panel_security
```

### Desktop and static checks

Check Electron JavaScript syntax:

```bash
node --check electron/main.cjs
node --check electron/preload.cjs
```

Check the web dashboard JavaScript:

```bash
node --check web_ui/static/js/script.js
node --check web_ui/static/js/docs_index.js
```

On Windows, `npm run dist` builds and packages the Electron desktop app.

Before sending changes for review, inspect the working tree and check patch
whitespace:

```bash
git status --short
git diff --check
```

## Configuration and local data

Aria creates local configuration and runtime-state files as it runs.
`config.json` can contain an account token and must remain private. The
dashboard session-signing key is stored in `.aria_webpanel_secret`; keep it
private and stable across restarts. For deployments that manage secrets via
environment variables, set `ARIA_WEBPANEL_SECRET` before starting Aria.
If you enable automatic Discord captcha retries for profile updates, quest
flows, invites, or other write endpoints, configure one of these optional
provider keys:

- `NOCAPTCHAAI_API_KEY` (preferred)
- `YES_CAPTCHA_API_KEY` (fallback)

These retries also cover Nitro gift redemption and giveaway-entry actions
(button interactions and reaction joins) because they use the shared API
request path.

Do not commit tokens, passwords, session secrets, database files, runtime
state, logs, or generated builds. The repository's `.gitignore` excludes
common local/generated files, but verify `git status` before committing.

The packaged application keeps its writable backend and runtime data in the
current user's application-data directory. On an application-version change,
the launcher stages the updated bundled backend and carries forward supported
runtime data. Do not manually edit or delete those files while Aria is
running.

### Desktop logs

During development, Electron startup and backend output appears in the
terminal. Hosted process output is also written under
`hosted_logs/hosted_<id>.log`.

The packaged desktop log is named `aria-desktop.log` under Electron's
user-data directory. Find it with PowerShell:

```powershell
Get-ChildItem "$env:APPDATA", "$env:LOCALAPPDATA" `
    -Filter aria-desktop.log -Recurse -ErrorAction SilentlyContinue |
    Select-Object -First 1 -ExpandProperty FullName
```

Find and follow it:

```powershell
$log = Get-ChildItem "$env:APPDATA", "$env:LOCALAPPDATA" `
    -Filter aria-desktop.log -Recurse -ErrorAction SilentlyContinue |
    Select-Object -First 1 -ExpandProperty FullName
if ($log) {
    Get-Content $log -Wait
} else {
    Write-Error "Aria log file was not found."
}
```

Inspect logs before sharing them; they can contain account identifiers,
machine paths, and other private information.

### Optional separate backend components

The desktop launcher starts `aria.py`; it does not start the separate
`aria_backend/` implementation. To develop those components, install their
dependencies into the intended Python environment:

```bash
python -m pip install -r aria_backend/requirements.txt
```

Their dependency list includes a pinned Git revision of `modifyself`. Avoid
installing that backend dependency set into a production environment unless
those components are required.

## Optional MongoDB storage

MongoDB is optional. If it is disabled or unavailable, Aria uses its existing
JSON-backed storage. To use MongoDB:

1. Install and start a MongoDB server that Aria can reach.
2. Install the Python driver in Aria's active environment:

   ```bash
   python -m pip install pymongo
   ```

3. Add the following settings to the **private local** `config.json`:

   ```json
   {
     "mongo_enabled": true,
     "mongo_uri": "mongodb://127.0.0.1:27017",
     "mongo_database": "aria",
     "mongo_collection": "app_state",
     "mongo_timeout_ms": 1500
   }
   ```

4. Restart Aria and check its runtime log for MongoDB connection errors.

Mongo-backed datasets currently include `history_data`, `account_stats`,
`analytics`, `dashboard_users`, and `access_requests`.

## Feature walkthroughs

### Quest status

Aria can fetch and display the quest state and progress returned by the
service. These commands are read-only: they do not enroll, simulate activity,
claim rewards, or send progress updates.

```text
<prefix>quest list
<prefix>quest status
<prefix>quest info <id or name>
<prefix>quest refresh
```

`quest` and `quests` are equivalent. The list shows up to eight quests;
use `quest info` to inspect a matching quest. Quest availability and returned
progress depend on the connected account and the service response.

### RPC presets and rotation

Replace `<prefix>` with the command prefix configured for the active instance.
These commands save an activity, list saved presets, load one, and rotate
between presets every 45 minutes:

```text
<prefix>rpc preset save desk
<prefix>rpc preset list
<prefix>rpc preset load desk
<prefix>rpc rotation set 45 desk,away
<prefix>rpc rotation start
<prefix>rpc rotation stop
```

Each hosted instance has its own RPC profile store; presets are not copied
automatically from the controller into hosted clients.

### Message logger

Message logging is disabled by default. Enable it and add terms:

```text
<prefix>logger on
<prefix>logger add release notes
```

Optional scope examples:

```text
<prefix>logger scope dms
<prefix>logger scope guilds
<prefix>logger scope guild <guild-id>
<prefix>logger scope channel <channel-id>
```

The dashboard can configure mention, edit, delete, and own-message filtering.
The live feed is limited to 400 in-memory events; the logger's settings are
persisted separately in `message_logger.json`.

### Hosted-instance permissions and recovery

Hosted clients run as separate processes and use their own runtime
configuration. Their commands are scoped to the requester and hosted account;
they do not inherit the main runtime's global-owner permissions. The watchdog
retries failed launches and process exits with interruptible backoff capped
at five minutes. A restart request does not guarantee that the account will
connect successfully. Check the hosted-client status and its runtime log if
it remains offline.

## Update the source checkout

1. Stop Aria cleanly.
2. Open a terminal in the repository checkout.
3. Pull the intended branch:

   ```bash
   git pull --ff-only
   ```

4. Enter the application directory:

   ```bash
   cd Aria
   ```

   If your terminal is already in the inner application directory, do not
   change directories again.
5. Update Python dependencies in the active virtual environment:

   ```bash
   python -m pip install -r requirements.txt
   ```

6. Update npm dependencies when `package.json` or `package-lock.json` changed:

   ```bash
   npm ci
   ```

7. Start Aria with `npm start` for the desktop, or `python aria.py` for the
   Python runtime only.

`git pull` updates source only. It does not update an already-installed
Windows application.

## Update an installed Windows app

To publish a new Windows build, keep the versions in `package.json`,
`package-lock.json`, `formatter.py`, and `Aria.Native/Aria.Native.csproj`
aligned. The launcher uses the app version to decide when to stage the new
bundled backend.

1. Close Aria on the build PC and update the source checkout:

   ```powershell
   git pull --ff-only
   if (Test-Path .\Aria\package.json) {
       Set-Location .\Aria
   } elseif (-not (Test-Path .\package.json)) {
       throw "Open the repository or application directory first."
   }
   ```

2. Activate the build environment:

   ```powershell
   .\.venv-build\Scripts\Activate.ps1
   ```

3. Refresh build dependencies:

   ```powershell
   python -m pip install -r requirements.txt
   python -m pip install pyinstaller
   npm ci
   ```

4. Build a new installer:

   ```powershell
   npm run dist
   Get-ChildItem .\release\*.exe
   ```

5. Install the new `Aria Setup <version>.exe` under the same Windows user
   account. This allows the app to continue using that user's application
   data.

## Clean old files or uninstall Aria

First decide what you want to remove:

- To clear old build files only, follow **A**.
- To reinstall development dependencies too, follow **A** and **B**.
- To remove an installed desktop app, follow **C**.
- To erase saved settings and account data as well, follow **C** and **D**.

Close Aria before starting. Steps **A** and **B** are for a source checkout,
not an installed app. They preserve your source and configuration.

### A. Remove generated build files from a source checkout

1. Open PowerShell (Windows) or a terminal (Linux/macOS).
2. Change directory to Aria's inner application directory, the one
   containing `package.json`. For a checkout in `C:\Projects\Aria`, for
   example:

   ```powershell
   cd C:\Projects\Aria\Aria
   ```

   On Linux/macOS, use the corresponding path, for example:

   ```bash
   cd ~/Projects/Aria/Aria
   ```

3. Confirm you are in the right place before deleting anything:

   PowerShell:

   ```powershell
   Get-Location
   if (-not (Test-Path -LiteralPath .\package.json)) {
       throw "Stop: package.json was not found. Change to Aria's inner application directory."
   }
   ```

   Linux/macOS:

   ```bash
   pwd
   test -f package.json || { echo "Stop: package.json was not found. Change to Aria's inner application directory." >&2; exit 1; }
   ```

4. Remove generated build output. This does not remove source code,
   configuration, or saved runtime data:

   PowerShell:

   ```powershell
   @("build", "dist", "release", "Aria.Native\bin", "Aria.Native\obj") |
       ForEach-Object {
           if (Test-Path -LiteralPath $_) {
               Remove-Item -LiteralPath $_ -Recurse -Force
           }
       }
   ```

   Linux/macOS:

   ```bash
   rm -rf build dist release Aria.Native/bin Aria.Native/obj
   ```

5. Start Aria again or rebuild it. The build folders will be recreated as
   needed.

### B. Reinstall development dependencies from scratch

Do this only if you also want to remove and reinstall Python/npm dependencies.
Complete steps 1–3 in **A** first, so you are in the inner application
directory and have verified that `package.json` exists.

1. Remove the local virtual environment and npm dependency directory:

   PowerShell:

   ```powershell
   @(".venv", "node_modules") | ForEach-Object {
       if (Test-Path -LiteralPath $_) {
           Remove-Item -LiteralPath $_ -Recurse -Force
       }
   }
   ```

   Linux/macOS:

   ```bash
   rm -rf .venv node_modules
   ```

2. Recreate the dependencies by following the setup steps in
   [Quick start: desktop app](#quick-start-desktop-app), or run the relevant
   commands from the application directory:

   Windows PowerShell:

   ```powershell
   py -3.11 -m venv .venv
   .\.venv\Scripts\python.exe -m pip install --upgrade pip
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   npm ci
   ```

   Linux/macOS:

   ```bash
   python3 -m venv .venv
   .venv/bin/python -m pip install --upgrade pip
   .venv/bin/python -m pip install -r requirements.txt
   npm ci
   ```

`npm ci` reads `package-lock.json` to install the locked npm dependencies. Do
not delete `package-lock.json`.

### C. Uninstall the installed desktop app

1. Quit Aria.
2. Uninstall or remove it for your operating system:
   - **Windows:** Open **Settings > Apps > Installed apps**. Find **Aria**,
     select the menu beside it, choose **Uninstall**, and follow the prompts.
     If Aria is not listed, open its installation folder and run its
     uninstaller. Delete any leftover shortcuts separately if desired.
       For the Windows portable build, quit Aria and delete the downloaded
       `Aria-Windows-x64-Portable-<version>.exe` file and any shortcuts you
       created.
   - **macOS:** Open **Applications** in Finder, drag **Aria** to the Trash,
     then empty the Trash if you want to permanently remove the app.
    - **Linux `.deb`:** Remove the installed package:

       ```bash
       sudo apt remove aria-desktop
       ```

   - **Linux AppImage:** Delete the downloaded Aria `.AppImage` file. Also
     remove any shortcut you created.
3. If you only want to uninstall the app, stop here. Continue to **D** only
   if you also want to erase saved data.

Uninstalling the app does not necessarily remove its per-user data. Keeping
that data allows settings to remain if you reinstall Aria later.

### D. Optionally erase saved Aria data

This step is optional and irreversible. It can remove `config.json` (which
may contain your account token), session secrets, settings, runtime state,
databases, hosted-instance data, and logs. Back up anything you want to keep.

1. Quit Aria.
2. Find the data directory:
   - **Source checkout:** Local files such as `config.json`,
     `message_logger.json`, `.aria_webpanel_secret`, `hosted_logs`, and
     runtime databases are inside the application directory. Do not treat
     the application directory itself as the data directory.
   - **Windows installed app:** Find `aria-desktop.log` by following
     [Desktop logs](#desktop-logs). Its parent folder is `logs`; the parent
     of `logs` is the Electron user-data directory.
   - **macOS:** Look in `~/Library/Application Support` for Aria's
     application-data directory.
   - **Linux:** Look in `~/.config` or `~/.local/share` for Aria's
     application-data directory.
3. Open the identified directory in File Explorer or your file manager.
   Confirm it belongs to Aria and back up any files you want to keep.
4. Delete saved data:
   - **Source checkout:** In the application directory, remove only the
     Aria data files and folders you have chosen to erase, such as
     `config.json`, `.aria_webpanel_secret`, `message_logger.json`, or
     `hosted_logs`. Do not delete the application directory or source code.
   - **Installed app:** Delete only the Aria Electron user-data directory
     identified above if you want to erase all saved data for that user. Do
     not delete the entire `Application Support`, `.config`, or
     `.local/share` directory.
5. If Aria is still installed, uninstall it using **C**. If it is already
   uninstalled, the cleanup is complete.

Do not delete application data to fix a build problem. Use **A** or **B**
instead.

## Troubleshooting

| Symptom | Steps to try |
| --- | --- |
| PowerShell says scripts are disabled | Run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in that PowerShell window, then retry `.\install.ps1`. |
| `package.json` or `requirements.txt` is not found | Change into the inner application directory (`Aria/Aria`) and retry. |
| Python dependency installation fails | Confirm the correct virtual environment is active, run `python --version`, upgrade pip, and retry the install command. |
| Electron cannot find Python | Set `ARIA_PYTHON` to the absolute path of the project's virtual-environment interpreter before `npm start`. |
| Dashboard does not start | Check whether ports 8080–8084 are in use, then inspect the terminal or `aria-desktop.log`. |
| Dashboard opens but requires login | This is expected when Aria connects to an already-running service. Sign in with that service's dashboard account. |
| Electron window does not open | Check the terminal output or `aria-desktop.log`, then confirm the release package finished building successfully. |
| Hosted account remains offline after restart | Refresh Hosted instances, read the instance's connection error, and inspect `hosted_logs/hosted_<id>.log`. |
| Installer is missing | Confirm `npm run dist` completed successfully, then inspect `build/` and `release/` for build errors or output. |

When asking for help, include the exact command and relevant error text, but
remove tokens, passwords, session cookies, user identifiers, and private
paths first.

## Project layout

The repository has an outer checkout directory and an inner application
directory. Run application commands from the inner directory.

```text
repository/
├── .github/workflows/       Windows CI workflow
└── Aria/                    Application directory
    ├── aria.py              Runtime bootstrap
    ├── main.py              Runtime and command implementation
    ├── webpanel.py          Local dashboard API and web routes
    ├── web_ui/              Browser dashboard and static assets
    ├── electron/            Desktop launcher, setup, and preload
    ├── aria_backend/        Separate backend components
    ├── host.py              Hosted process manager
    ├── install.ps1          Windows development setup and launch
    ├── install.sh           Linux/macOS development setup and launch
    ├── package.json         Electron scripts and packaging
    └── requirements.txt     Main Python runtime dependencies
```

## Credits

Aria is maintained by Misconsideration.
