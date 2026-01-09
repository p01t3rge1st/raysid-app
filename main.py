#!/usr/bin/env python3
"""
Raysid Gamma Spectrometer - PyQt5 Application

Demonstrates the raysid_api library with a modern GUI:
- BLE device scanning and connection
- Real-time CPS / dose rate display
- Live spectrum plot with peak detection
- Battery / temperature status
"""
import os
import sys
import signal
import asyncio
from pathlib import Path

# Fix Qt platform plugin path for pip-installed PyQt5 in virtualenvs
def _ensure_qt_platform_plugin():
    pyver = f"python{sys.version_info.major}.{sys.version_info.minor}"
    project_root = Path(__file__).resolve().parent
    # Don't resolve() sys.executable - it follows symlinks to system Python
    venv_root = Path(sys.executable).parent.parent

    candidates = [
        venv_root / "lib" / pyver / "site-packages" / "PyQt5" / "Qt5" / "plugins" / "platforms",
        project_root / ".venv" / "lib" / pyver / "site-packages" / "PyQt5" / "Qt5" / "plugins" / "platforms",
        project_root / "venv" / "lib" / pyver / "site-packages" / "PyQt5" / "Qt5" / "plugins" / "platforms",
    ]

    for path in candidates:
        if path.exists():
            os.environ.setdefault("QT_QPA_PLATFORM_PLUGIN_PATH", str(path))
            break


_ensure_qt_platform_plugin()

from PyQt5.QtWidgets import QApplication
import qasync

# Ensure raysid_api is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from widgets.main_window import MainWindow

# Global reference for signal handler
_window = None
_loop = None


def signal_handler(sig, frame):
    """Handle SIGINT/SIGTERM for clean shutdown."""
    print(f"\nReceived signal {sig}, shutting down...")
    if _window:
        _window.force_cleanup()
    if _loop:
        _loop.call_soon_threadsafe(_loop.stop)
    sys.exit(0)


def main():
    global _window, _loop
    
    app = QApplication(sys.argv)
    app.setApplicationName("Raysid Gamma Spectrometer")
    app.setOrganizationName("Raysid")

    # Use qasync for proper Qt-asyncio integration
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)
    _loop = loop

    window = MainWindow(loop)
    _window = window
    window.show()

    # Setup signal handlers for clean shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        with loop:
            loop.run_forever()
    except KeyboardInterrupt:
        print("\nKeyboard interrupt, cleaning up...")
        window.force_cleanup()
    finally:
        # Ensure BLE is disconnected
        if window.ble_worker and window.ble_worker.connected:
            try:
                loop.run_until_complete(window.ble_worker.disconnect())
            except:
                pass


if __name__ == "__main__":
    main()
