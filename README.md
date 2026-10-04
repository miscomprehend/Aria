# Aria

A Discord selfbot with advanced features including activity control, analytics, and automation.

## Download & Run

Download the latest Electron desktop app from
[GitHub Releases](https://github.com/miscomprehend/Aria/releases/latest), then choose the installer for your platform:

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

On first launch, enter your account token in Aria's setup window. Releases are
built by [`release.yml`](.github/workflows/release.yml) when a `v*` tag is
pushed.

## Features

- **Activity Control**: Set custom Discord activities, VR presence, and more
- **Analytics**: Track messages, commands, and bot performance
- **Web Dashboard**: Modern web interface for bot management
- **Proxy Support**: Built-in proxy rotation for safety
- **Captcha Solving**: Automatic captcha solving for uninterrupted operation

## Captcha Integration

Aria includes automatic captcha solving to handle Discord's captcha challenges. When enabled, the bot will automatically solve captchas using supported services.

### Setup

1. Get an API key from [2Captcha](https://2captcha.com/)
2. Edit `config.json`:
```json
{
  "captcha_enabled": true,
  "captcha_api_key": "your_2captcha_api_key_here",
  "captcha_service": "2captcha"
}
```

### Supported Services

- **2Captcha** (recommended)
- AntiCaptcha
- CapMonster

### Web Dashboard

Configure captcha settings through the web dashboard at `http://localhost:8080` under the Settings section.

### How it Works

When Discord presents a captcha challenge (HTTP 400 with captcha data), Aria will:
1. Detect the captcha type (hCaptcha, reCAPTCHA, or Cloudflare Turnstile)
2. Send the challenge to your configured captcha service
3. Wait for the solution
4. Retry the request with the solved captcha token

This ensures your bot continues operating even when Discord requires captcha verification.