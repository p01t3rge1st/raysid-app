"""Settings dialog for spectrum analysis parameters."""
from __future__ import annotations

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QSlider, QPushButton, QGroupBox, QMessageBox
)
from PyQt5.QtCore import Qt, QSettings


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

        # --- Device Group ---
        device_group = QGroupBox("Saved Device")
        device_layout = QVBoxLayout(device_group)

        self.saved_device_label = QLabel("No saved device")
        device_layout.addWidget(self.saved_device_label)

        self.forget_btn = QPushButton("Forget Saved Device")
        self.forget_btn.clicked.connect(self._on_forget_device)
        device_layout.addWidget(self.forget_btn)

        layout.addWidget(device_group)

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
        saved_device = self.settings.value("device/last_address", "")
        saved_name = self.settings.value("device/last_name", "")

        self.sensitivity_slider.setValue(sensitivity)
        self.smooth_slider.setValue(smooth_window)
        
        if saved_device:
            self.saved_device_label.setText(f"{saved_name}\n({saved_device})")
            self.forget_btn.setEnabled(True)
        else:
            self.saved_device_label.setText("No saved device")
            self.forget_btn.setEnabled(False)

    def _save_and_close(self):
        """Save settings and close dialog."""
        self.settings.setValue("peak/sensitivity", self.sensitivity_slider.value())
        self.settings.setValue("smooth/window", self.smooth_slider.value())
        self.settings.sync()
        self.accept()

    def _on_forget_device(self):
        """Clear saved device."""
        self.settings.remove("device/last_address")
        self.settings.remove("device/last_name")
        self.settings.sync()
        self.saved_device_label.setText("No saved device")
        self.forget_btn.setEnabled(False)
        QMessageBox.information(self, "Device Forgotten", "Saved device has been cleared.")

    def get_peak_sensitivity(self) -> int:
        """Get peak detection sensitivity (1-100)."""
        return self.sensitivity_slider.value()

    def get_smooth_window(self) -> int:
        """Get smoothing window size (odd number 5-51)."""
        return self.smooth_slider.value()
