# Raysid App - Copilot Instructions

## Project Overview
Raysid is a PyQt5 desktop application for interfacing with Raysid gamma spectrometer devices via Bluetooth Low Energy (BLE).

## Technology Stack
- Python 3.10+
- PyQt5 for GUI
- qasync for asyncio integration with Qt
- bleak for BLE communication
- matplotlib for spectrum visualization
- scipy for signal processing (peak detection, smoothing)

## Project Structure
```
raysid-app/
├── src/
│   └── raysid/
│       ├── __init__.py
│       ├── __main__.py
│       ├── ble_worker.py
│       └── widgets/
│           ├── __init__.py
│           ├── main_window.py
│           ├── spectrum_widget.py
│           └── cps_widget.py
├── pyproject.toml
├── setup.py
├── requirements.txt
├── README.md
└── LICENSE
```

## Development Guidelines
- Use async/await for BLE operations
- Emit Qt signals for thread-safe GUI updates
- Follow PEP 8 style guidelines
- Use type hints where appropriate
