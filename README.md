# Raysid Gamma Spectrometer

Raysid is a cross-platform desktop application for interfacing with Raysid gamma spectrometer devices via Bluetooth Low Energy (BLE). The application provides real-time CPS and dose rate readouts, spectrum visualization, and device status monitoring through a modern PyQt5 user interface.

## Features
- BLE device discovery and connection management
- Real-time spectrum plotting with optional peak detection and smoothing
- CPS (counts per second) and dose rate (µSv/h) display
- Battery level and temperature monitoring
- Clean PyQt5-based GUI with asyncio integration via qasync

## Supported Platforms
- Linux (X11/Wayland)
- Windows 10/11
- macOS (Apple Silicon and Intel)

## Requirements
- Python 3.10 or newer
- BLE-capable adapter and drivers (BlueZ on Linux)
- Display server (X11/Wayland on Linux; native on Windows/macOS)

Python dependencies are installed automatically via `pip`:
- PyQt5 ≥ 5.15
- qasync ≥ 0.24
- bleak ≥ 0.21
- matplotlib ≥ 3.5
- numpy ≥ 1.21
- scipy ≥ 1.7

## Installation

### Quick Install (Linux)
Installs system libraries, the application, and a desktop entry with icon.

```bash
curl -fsSL https://raw.githubusercontent.com/p01t3rge1st/raysid-app/main/install.sh | bash
```

After installation, launch from the application menu or run `raysid-app` in the terminal.

### Manual Installation

#### Linux system libraries
Install required X11/XCB/OpenGL libraries before installing the application.

Ubuntu/Debian:
```bash
sudo apt update && sudo apt install -y python3-pip libxcb-xinerama0 libxcb-cursor0 libxcb-icccm4 libxcb-keysyms1 libxcb-image0 libxcb-render-util0 libxkbcommon-x11-0 libgl1
```

Fedora/RHEL:
```bash
sudo dnf install -y python3-pip libxcb xcb-util xcb-util-image xcb-util-renderutil xcb-util-keysyms libxkbcommon-x11 mesa-libGL
```

Arch Linux:
```bash
sudo pacman -S python-pip libxcb xcb-util xcb-util-image xcb-util-renderutil xcb-util-keysyms libxkbcommon-x11 mesa
```

#### Application (all platforms)
```bash
pip install git+https://github.com/p01t3rge1st/raysid-app.git
```

## Usage
Launch the application and connect to a Raysid device:

```bash
raysid-app
```

Steps:
- Enable Bluetooth on the computer
- Power on the Raysid spectrometer
- Click Scan to discover devices
- Select a device and click Connect

## Troubleshooting

### Linux: "Could not find the Qt platform plugin xcb"
Install the system libraries listed in the Linux section above. The application also sets `QT_QPA_PLATFORM_PLUGIN_PATH` automatically based on the PyQt5 installation.

### Linux: Bluetooth permissions
Add the user to the `bluetooth` group and re-login:
```bash
sudo usermod -aG bluetooth $USER
```

### Headless environments (CI)
Use a virtual display:
```bash
xvfb-run -s "-screen 0 1280x720x24" raysid-app
```

## Development

Editable install for local development:
```bash
git clone https://github.com/p01t3rge1st/raysid-app.git
cd raysid-app
pip install -e .
```

## License
MIT License. See LICENSE for details.

# 🔬 Raysid Gamma Spectrometer

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/platform-Linux%20%7C%20Windows%20%7C%20macOS-lightgrey.svg" alt="Cross-platform">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="MIT License">
  <img src="https://img.shields.io/badge/BLE-Bluetooth%20Low%20Energy-blue.svg" alt="BLE">
</p>

<p align="center">
  <b>Desktop application for interfacing with Raysid gamma spectrometer via Bluetooth Low Energy</b>
</p>

---

## ✨ Features

- 📡 **BLE Device Discovery** — Automatic scanning and connection to Raysid devices
- 📊 **Real-time Spectrum Plot** — Live visualization with peak detection and smoothing
- ⚡ **CPS & Dose Rate Display** — Counts per second and µSv/h measurements
- 🔋 **Device Status Monitoring** — Battery level and temperature readout
- 🎨 **Modern PyQt5 Interface** — Clean, responsive GUI

---

## 🚀 Installation

### Quick Install (Linux)

One command to install everything (system dependencies, app, and desktop icon):

```bash
curl -fsSL https://raw.githubusercontent.com/p01t3rge1st/raysid-app/main/install.sh | bash
```

Then run: `raysid-app` or find "Raysid Gamma Spectrometer" in your application menu.

---

### Manual Installation

#### Linux

**Step 1: Install system dependencies**

Ubuntu / Debian:
```bash
sudo apt update && sudo apt install -y python3-pip libxcb-xinerama0 libxcb-cursor0 libxcb-icccm4 libxcb-keysyms1 libxcb-image0 libxcb-render-util0 libxkbcommon-x11-0 libgl1
```

Fedora / RHEL:
```bash
sudo dnf install -y python3-pip libxcb xcb-util xcb-util-image xcb-util-renderutil xcb-util-keysyms libxkbcommon-x11 mesa-libGL
```

Arch Linux:
```bash
sudo pacman -S python-pip libxcb xcb-util xcb-util-image xcb-util-renderutil xcb-util-keysyms libxkbcommon-x11 mesa
```

**Step 2: Install the application**
```bash
pip install git+https://github.com/p01t3rge1st/raysid-app.git
```

**Step 3: Run**
```bash
raysid-app
```

### Windows

```powershell
pip install git+https://github.com/p01t3rge1st/raysid-app.git
raysid-app
```

### macOS

```bash
pip install git+https://github.com/p01t3rge1st/raysid-app.git
raysid-app
```

---

## 📦 Installation from Source

```bash
git clone https://github.com/p01t3rge1st/raysid-app.git
cd raysid-app
pip install .
raysid-app
```

### Development Mode

```bash
git clone https://github.com/p01t3rge1st/raysid-app.git
cd raysid-app
pip install -e .
```

---

## 🔧 Requirements

| Requirement | Version |
|-------------|---------|
| Python | 3.10+ |
| Bluetooth | BLE-capable adapter |
| Display | X11, Wayland, Windows, or macOS |

### Python Dependencies (installed automatically)

- PyQt5 ≥ 5.15
- qasync ≥ 0.24
- bleak ≥ 0.21
- matplotlib ≥ 3.5
- numpy ≥ 1.21
- scipy ≥ 1.7

---

## 🖥️ Usage

1. Enable Bluetooth on your computer
2. Power on your Raysid spectrometer
3. Launch `raysid-app`
4. Click **Scan** to discover nearby devices
5. Select your device and click **Connect**
6. View real-time spectrum and measurements

---

## 🐛 Troubleshooting

### "Could not find the Qt platform plugin xcb" (Linux only)

Install the required system libraries listed in the Linux installation section.

### "Permission denied" when accessing Bluetooth (Linux)

```bash
sudo usermod -aG bluetooth $USER
```
Log out and log back in for the change to take effect.

### Running in headless environments

```bash
xvfb-run -s "-screen 0 1280x720x24" raysid-app
```

---

## 📄 License

MIT License — see [LICENSE](LICENSE)

---
