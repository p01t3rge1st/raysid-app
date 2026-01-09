#!/usr/bin/env python3
"""
Raysid Gamma Spectrometer - PyQt5 Application

Desktop GUI for interfacing with Raysid gamma spectrometer devices via BLE:
- BLE device scanning and connection
- Real-time CPS / dose rate display
- Live spectrum plot with peak detection
- Battery / temperature status
"""
import os
import sys
import signal
import asyncio


def _ensure_qt_platform_plugin():
    """
    Ensure Qt can find platform plugins (xcb, wayland, etc.) when installed via pip.
    
    PyQt5 bundles its own Qt plugins. We find them by locating PyQt5's install path
    and pointing QT_QPA_PLATFORM_PLUGIN_PATH there. This works regardless of whether
    the package is installed in a venv, user site-packages, or system-wide.
    """
    if "QT_QPA_PLATFORM_PLUGIN_PATH" in os.environ:
        return  # User already set it, don't override
    
    try:
        import PyQt5
        pyqt5_path = os.path.dirname(PyQt5.__file__)
        plugins_path = os.path.join(pyqt5_path, "Qt5", "plugins", "platforms")
        
        if os.path.isdir(plugins_path):
            os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = plugins_path
    except ImportError:
        pass  # PyQt5 not installed, will fail later with clear error


# Must be called before importing any PyQt5 modules
_ensure_qt_platform_plugin()

from PyQt5.QtWidgets import QApplication
import qasync

from raysid.widgets.main_window import MainWindow

# Global references for signal handler
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
    """Entry point for raysid-app command."""
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
