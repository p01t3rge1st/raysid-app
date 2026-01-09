"""Settings dialog for spectrum analysis parameters."""
from __future__ import annotations

import os
import subprocess
import sys
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QSlider, QPushButton, QGroupBox, QMessageBox, QComboBox
)
from PyQt5.QtCore import Qt, QSettings


def detect_system_theme() -> str:
    """Detect system theme preference. Returns 'light' or 'dark'."""
    try:
        if sys.platform == "darwin":  # macOS
            result = subprocess.run(
                ["defaults", "read", "-g", "AppleInterfaceStyle"],
                capture_output=True, text=True, timeout=5
            )
            return "dark" if result.returncode == 0 else "light"
        
        elif sys.platform == "win32":  # Windows
            result = subprocess.run(
                ["reg", "query", "HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize", "/v", "AppsUseLightTheme"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and "0x0" in result.stdout:
                return "dark"
            return "light"
        
        else:  # Linux and others
            # Check common environment variables
            if os.environ.get("GTK_THEME", "").lower().find("dark") != -1:
                return "dark"
            if os.environ.get("QT_QPA_PLATFORMTHEME", "").lower().find("dark") != -1:
                return "dark"
            # Default to light
            return "light"
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return "light"


class SettingsDialog(QDialog):
    """Dialog for configuring spectrum analysis settings."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = QSettings("Raysid", "GammaSpectrometer")
        self._init_ui()
        self._load_settings()

    def _init_ui(self):
        self.setWindowTitle("Settings")
        self.setMinimumWidth(400)
        layout = QVBoxLayout(self)

        # --- Theme Group ---
        theme_group = QGroupBox("Appearance")
        theme_layout = QFormLayout(theme_group)

        self.theme_combo = QComboBox()
        self.theme_combo.addItem("Light", "light")
        self.theme_combo.addItem("Dark", "dark")
        self.theme_combo.addItem("System", "system")
        theme_layout.addRow("Theme:", self.theme_combo)

        layout.addWidget(theme_group)

        # --- Peak Detection Group ---
        peak_group = QGroupBox("Peak Detection")
        peak_layout = QFormLayout(peak_group)

        # Sensitivity slider (1-100, higher = more sensitive)
        self.sensitivity_slider = QSlider(Qt.Horizontal)
        self.sensitivity_slider.setRange(1, 100)
        self.sensitivity_slider.setValue(50)
        self.sensitivity_slider.setTickPosition(QSlider.TicksBelow)
        self.sensitivity_slider.setTickInterval(10)
        self.sensitivity_label = QLabel("50%")
        self.sensitivity_slider.valueChanged.connect(
            lambda v: self.sensitivity_label.setText(f"{v}%")
        )
        
        sens_row = QHBoxLayout()
        sens_row.addWidget(self.sensitivity_slider)
        sens_row.addWidget(self.sensitivity_label)
        peak_layout.addRow("Sensitivity:", sens_row)

        layout.addWidget(peak_group)

        # --- Smoothing Group ---
        smooth_group = QGroupBox("Spectrum Smoothing")
        smooth_layout = QFormLayout(smooth_group)

        # Smoothing window slider (5-51, odd values only)
        self.smooth_slider = QSlider(Qt.Horizontal)
        self.smooth_slider.setRange(5, 51)
        self.smooth_slider.setValue(21)
        self.smooth_slider.setSingleStep(2)
        self.smooth_slider.setTickPosition(QSlider.TicksBelow)
        self.smooth_slider.setTickInterval(10)
        self.smooth_label = QLabel("21")
        self.smooth_slider.valueChanged.connect(self._on_smooth_changed)
        
        smooth_row = QHBoxLayout()
        smooth_row.addWidget(self.smooth_slider)
        smooth_row.addWidget(self.smooth_label)
        smooth_layout.addRow("Window size:", smooth_row)

        layout.addWidget(smooth_group)

        # --- Buttons ---
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self._save_and_close)
        btn_layout.addWidget(self.save_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        layout.addLayout(btn_layout)

    def _on_smooth_changed(self, value: int):
        # Ensure odd values only
        if value % 2 == 0:
            value += 1
            self.smooth_slider.blockSignals(True)
            self.smooth_slider.setValue(value)
            self.smooth_slider.blockSignals(False)
        self.smooth_label.setText(str(value))

    def _load_settings(self):
        """Load settings from QSettings."""
        sensitivity = self.settings.value("peak/sensitivity", 50, type=int)
        smooth_window = self.settings.value("smooth/window", 21, type=int)
        theme = self.settings.value("ui/theme", "system", type=str)

        self.sensitivity_slider.setValue(sensitivity)
        self.smooth_slider.setValue(smooth_window)
        
        # Set theme combo
        index = self.theme_combo.findData(theme)
        if index >= 0:
            self.theme_combo.setCurrentIndex(index)
        else:
            self.theme_combo.setCurrentIndex(2)  # Default to system

    def _save_and_close(self):
        """Save settings and close dialog."""
        self.settings.setValue("peak/sensitivity", self.sensitivity_slider.value())
        self.settings.setValue("smooth/window", self.smooth_slider.value())
        self.settings.setValue("ui/theme", self.theme_combo.currentData())
        self.settings.sync()
        self.accept()

    def get_peak_sensitivity(self) -> int:
        """Get peak detection sensitivity (1-100)."""
        return self.sensitivity_slider.value()

    def get_smooth_window(self) -> int:
        """Get smoothing window size (odd number 5-51)."""
        return self.smooth_slider.value()

    def get_theme(self) -> str:
        """Get selected theme ('light', 'dark', or 'system')."""
        return self.theme_combo.currentData()
