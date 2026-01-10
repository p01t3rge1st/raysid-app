# Raysid App

Desktop app for Raysid gamma spectrometer. BLE connection, spectrum plot, CPS/dose readout.

![Spectrum view](docs/images/screenshot.png)

![CPS view](docs/images/screenshot2.png)

## Install

### Windows

Download portable executable from [Releases](https://github.com/p01t3rge1st/raysid-app/releases/latest):

1. Download `raysid-app-windows-x64.zip`
2. Extract to any folder
3. Run `raysid-app.exe`

**Requirements:** Windows 10/11 (64-bit), Bluetooth adapter

### Linux / macOS

```bash
curl -fsSL https://raw.githubusercontent.com/p01t3rge1st/raysid-app/master/install.sh | bash
```

Requires Python 3.10+.

## Run

**Windows:** Double-click `raysid-app.exe`

**Linux/macOS:**
```bash
raysid-app
```

## Known Issues

**Bluetooth can be unstable.** Connection drops happen. If device won't connect, toggle Bluetooth off/on and retry.

**Random crashes occur.** The app may crash unexpectedly during spectrum updates or BLE operations. Just restart it.

**Linux BLE permissions.** You may need to run with sudo or add user to `bluetooth` group.

**Windows Bluetooth.** May require "Allow apps to access Bluetooth" in Windows Settings → Privacy & security → Bluetooth.

## Manual Install (Linux/macOS)

If the script fails:

```bash
pipx install git+https://github.com/p01t3rge1st/raysid-app.git
```

Or with pip:

```bash
pip install --user git+https://github.com/p01t3rge1st/raysid-app.git
```

## Uninstall

**Windows:** Delete the extracted folder

**Linux/macOS:**
```bash
pipx uninstall raysid-app
```

## Development

Build Windows executable locally:

```bash
pip install -r requirements-build.txt
pyinstaller --clean --noconfirm raysid-app.spec
```

Output: `dist/raysid-app/raysid-app.exe`

## License

MIT
