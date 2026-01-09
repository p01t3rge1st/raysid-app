"""Main application window."""
from __future__ import annotations

import asyncio
import logging
from typing import Optional, List, Dict

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QGroupBox, QStatusBar,
    QTabWidget, QSplitter, QFrame, QMessageBox, QToolButton
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject, QSettings
from PyQt5.QtGui import QIcon

from raysid.widgets.spectrum_widget import SpectrumWidget
from raysid.widgets.cps_widget import CPSWidget
from raysid.widgets.settings_dialog import SettingsDialog
from raysid.ble_worker import BleWorker


class MainWindow(QMainWindow):
    """Main application window with tabs for Spectrum and CPS views."""

    def __init__(self, loop: asyncio.AbstractEventLoop):
        super().__init__()
        self.loop = loop
        self.logger = logging.getLogger("raysid.app")
        logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(message)s")

        # QSettings for persistence
        self.settings = QSettings("Raysid", "GammaSpectrometer")

        self.ble_worker: Optional[BleWorker] = None
        self.connected = False
        self.scanned_devices: List[Dict] = []
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 3

        self._init_ui()
        self._connect_signals()
        self._load_last_device()

        # Periodic ping timer (every 10s when connected to spectrum tab)
        self.ping_timer = QTimer(self)
        self.ping_timer.timeout.connect(self._send_ping)
        self.ping_interval_ms = 10000

    def _init_ui(self):
        self.setWindowTitle("Raysid Gamma Spectrometer")
        self.setMinimumSize(1000, 700)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # --- Connection bar ---
        conn_group = QGroupBox("Connection")
        conn_layout = QHBoxLayout(conn_group)

        self.device_combo = QComboBox()
        self.device_combo.setMinimumWidth(300)
        self.device_combo.setPlaceholderText("Select device...")
        conn_layout.addWidget(self.device_combo)

        self.scan_btn = QPushButton("Scan")
        conn_layout.addWidget(self.scan_btn)

        self.connect_btn = QPushButton("Connect")
        conn_layout.addWidget(self.connect_btn)

        self.disconnect_btn = QPushButton("Disconnect")
        self.disconnect_btn.setEnabled(False)
        conn_layout.addWidget(self.disconnect_btn)

        conn_layout.addStretch()

        # Status labels
        self.battery_label = QLabel("Battery: --")
        self.temp_label = QLabel("Temp: --")
        conn_layout.addWidget(self.battery_label)
        conn_layout.addWidget(self.temp_label)

        # Settings button
        self.settings_btn = QToolButton()
        self.settings_btn.setText("⚙")
        self.settings_btn.setToolTip("Settings")
        self.settings_btn.setStyleSheet("QToolButton { font-size: 18px; padding: 4px 8px; }")
        conn_layout.addWidget(self.settings_btn)

        layout.addWidget(conn_group)

        # --- Tabs ---
        self.tabs = QTabWidget()

        # Spectrum tab
        self.spectrum_widget = SpectrumWidget()
        self.tabs.addTab(self.spectrum_widget, "Spectrum")

        # CPS tab
        self.cps_widget = CPSWidget()
        self.tabs.addTab(self.cps_widget, "CPS / Dose")

        layout.addWidget(self.tabs, stretch=1)

        # --- Status bar ---
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready. Scan for devices to connect.")

    def _connect_signals(self):
        self.scan_btn.clicked.connect(self._on_scan)
        self.connect_btn.clicked.connect(self._on_connect)
        self.settings_btn.clicked.connect(self._on_settings)
        self.disconnect_btn.clicked.connect(self._on_disconnect)
        self.tabs.currentChanged.connect(self._on_tab_changed)

    # --- Actions ---

    def _on_scan(self):
        self.status_bar.showMessage("Scanning for BLE devices...")
        self.scan_btn.setEnabled(False)
        self.device_combo.clear()
        asyncio.ensure_future(self._do_scan())

    async def _do_scan(self):
        try:
            from bleak import BleakScanner
            devices = await BleakScanner.discover(timeout=5.0)
            raysid_devs = [
                {"name": d.name or "Unknown", "address": d.address}
                for d in devices if d.name and "Raysid" in d.name
            ]
            self.scanned_devices = raysid_devs
            for dev in raysid_devs:
                self.device_combo.addItem(f"{dev['name']} ({dev['address']})", dev['address'])
            self.status_bar.showMessage(f"Found {len(raysid_devs)} Raysid device(s)")
        except Exception as e:
            self.status_bar.showMessage(f"Scan failed: {e}")
        finally:
            self.scan_btn.setEnabled(True)

    def _on_connect(self):
        addr = self.device_combo.currentData()
        if not addr:
            QMessageBox.warning(self, "No device", "Please scan and select a device first.")
            return

        self.status_bar.showMessage(f"Connecting to {addr}...")
        self.connect_btn.setEnabled(False)

        self.ble_worker = BleWorker(addr, self.loop)
        self.ble_worker.packet_received.connect(self._on_packet)
        self.ble_worker.connection_lost.connect(self._on_connection_lost)

        asyncio.ensure_future(self._do_connect())

    async def _do_connect(self):
        try:
            await self.ble_worker.connect()
            self.connected = True
            self.status_bar.showMessage("Connected!")
            self.connect_btn.setEnabled(False)
            self.disconnect_btn.setEnabled(True)
            self.scan_btn.setEnabled(False)
            # Save device for next time
            self._save_last_device()
            # Start ping timer
            self.ping_timer.start(self.ping_interval_ms)
            # Send initial ping for current tab
            self._send_ping()
        except Exception as e:
            self.status_bar.showMessage(f"Connection failed: {e}")
            self.connect_btn.setEnabled(True)

    def _on_disconnect(self):
        self.ping_timer.stop()
        if self.ble_worker:
            asyncio.ensure_future(self.ble_worker.disconnect())
        self._reset_ui()
        self.status_bar.showMessage("Disconnected")

    def _on_connection_lost(self):
        self.ping_timer.stop()
        self._reset_ui()
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 3
        self.status_bar.showMessage("Connection lost - will try reconnect in 10s...")
        # Wait longer to let BlueZ clean up properly
        QTimer.singleShot(10000, self._attempt_reconnect)
    
    def _attempt_reconnect(self):
        """Attempt to reconnect to the last device."""
        if self.connected:
            return  # Already reconnected
        if not self.ble_worker or not self.ble_worker.device_address:
            self.status_bar.showMessage("Cannot reconnect - no device address")
            return
        
        self._reconnect_attempts += 1
        if self._reconnect_attempts > self._max_reconnect_attempts:
            self.status_bar.showMessage(f"Reconnect failed after {self._max_reconnect_attempts} attempts. Please reconnect manually.")
            return
        
        self.status_bar.showMessage(f"Reconnecting ({self._reconnect_attempts}/{self._max_reconnect_attempts})...")
        asyncio.ensure_future(self._do_reconnect())
    
    async def _do_reconnect(self):
        """Perform the actual reconnection."""
        try:
            # Wait a bit before reconnecting to let BlueZ clean up
            await asyncio.sleep(2)
            
            await self.ble_worker.connect(self.ble_worker.device_address)
            self.connected = True
            self._reconnect_attempts = 0
            self.status_bar.showMessage("Reconnected!")
            self.connect_btn.setEnabled(False)
            self.disconnect_btn.setEnabled(True)
            self.scan_btn.setEnabled(False)
            self.ping_timer.start(self.ping_interval_ms)
            self._send_ping()
        except Exception as e:
            self.logger.warning(f"Reconnect attempt {self._reconnect_attempts} failed: {e}")
            self.status_bar.showMessage(f"Reconnect failed - retrying in 15s...")
            QTimer.singleShot(15000, self._attempt_reconnect)

    def _reset_ui(self):
        self.connected = False
        self.connect_btn.setEnabled(True)
        self.disconnect_btn.setEnabled(False)
        self.scan_btn.setEnabled(True)
        self.battery_label.setText("Battery: --")
        self.temp_label.setText("Temp: --")

    def _load_last_device(self):
        """Load last connected device from settings."""
        addr = self.settings.value("device/last_address", "")
        name = self.settings.value("device/last_name", "")
        if addr:
            self.device_combo.addItem(f"{name} ({addr})", addr)
            self.device_combo.setCurrentIndex(0)
            self.status_bar.showMessage(f"Last device: {name}. Press Connect or Scan for others.")

    def _save_last_device(self):
        """Save current device to settings."""
        addr = self.device_combo.currentData()
        text = self.device_combo.currentText()
        # Extract name from "Name (address)" format
        name = text.split(" (")[0] if " (" in text else text
        if addr:
            self.settings.setValue("device/last_address", addr)
            self.settings.setValue("device/last_name", name)
            self.settings.sync()
            self.logger.info(f"Saved device: {name} ({addr})")

    def _on_settings(self):
        """Open settings dialog."""
        dialog = SettingsDialog(self)
        if dialog.exec_():
            # Apply settings to spectrum widget
            self.spectrum_widget.set_peak_sensitivity(dialog.get_peak_sensitivity())
            self.spectrum_widget.set_smooth_window(dialog.get_smooth_window())
            self.spectrum_widget._redraw()

    def _on_tab_changed(self, index: int):
        # Send ping with appropriate tab value
        self._send_ping()

    def _send_ping(self):
        if not self.connected or not self.ble_worker:
            return
        # tab=1 for spectrum, tab=0 for CPS
        tab = 1 if self.tabs.currentIndex() == 0 else 0
        asyncio.ensure_future(self.ble_worker.send_ping(tab))
        self.logger.debug(f"Sent PING tab={tab}")

    def _on_packet(self, pkt: dict):
        ptype = pkt.get("type")
        if ptype == "cps":
            self.cps_widget.update_cps(pkt)
        elif ptype == "battery":
            self.battery_label.setText(f"Battery: {pkt.get('level', '--')}%")
            temp = pkt.get('temperature')
            if temp is not None:
                self.temp_label.setText(f"Temp: {temp:.1f}°C")
        elif ptype == "spectrum":
            self.spectrum_widget.update_spectrum(pkt)

    def force_cleanup(self):
        """Force synchronous cleanup of BLE connection."""
        self.ping_timer.stop()
        self.connected = False
        if self.ble_worker and self.ble_worker.client:
            try:
                # Try synchronous disconnect
                if self.ble_worker.client.is_connected:
                    future = asyncio.ensure_future(self.ble_worker.disconnect())
                    # Give it a short time to complete
                    self.loop.run_until_complete(asyncio.wait_for(future, timeout=2.0))
            except Exception as e:
                self.logger.warning(f"Cleanup disconnect error: {e}")
            finally:
                self.ble_worker = None

    def closeEvent(self, event):
        """Handle window close - ensure BLE is properly disconnected."""
        self.ping_timer.stop()
        self.connected = False
        
        if self.ble_worker:
            try:
                # Schedule disconnect and wait briefly
                if self.ble_worker.client and self.ble_worker.client.is_connected:
                    future = asyncio.ensure_future(self.ble_worker.disconnect())
                    # Use QTimer to delay actual close until disconnect completes
                    self.loop.run_until_complete(asyncio.wait_for(future, timeout=2.0))
            except Exception as e:
                self.logger.warning(f"Close disconnect error: {e}")
            finally:
                self.ble_worker = None
        
        event.accept()
