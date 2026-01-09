"""Spectrum visualization widget with matplotlib."""
from __future__ import annotations

from typing import Dict, List

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QCheckBox
from PyQt5.QtCore import Qt, QSettings

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import numpy as np

try:
    from scipy.signal import find_peaks, savgol_filter
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False


class SpectrumWidget(QWidget):
    """Widget displaying the gamma spectrum plot."""

    # Base calibration for 0x32 (div=9):
    # Cs-137 peak (662 keV) appears at channel ~165
    # KEV_PER_CHANNEL_BASE = 662/165 ≈ 4.01 for div=9
    # For other divs: KEV_PER_CHANNEL = KEV_PER_CHANNEL_BASE * 9 / div
    CHANNELS = 1800  # Max channels (for 0x30)
    KEV_PER_CHANNEL_BASE = 4.01  # For div=9 (0x32)
    MAX_KEV = 1000  # Display range: 0-1000 keV

    def __init__(self):
        super().__init__()
        self.spectrum = np.zeros(self.CHANNELS, dtype=np.float64)
        self.filled_channels = set()
        self.peak_annotations = []
        
        # Configurable settings
        self.settings = QSettings("Raysid", "GammaSpectrometer")
        self.peak_sensitivity = self.settings.value("peak/sensitivity", 50, type=int)
        self.smooth_window = self.settings.value("smooth/window", 21, type=int)

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Toolbar
        toolbar = QHBoxLayout()
        self.clear_btn = QPushButton("Clear Spectrum")
        self.clear_btn.clicked.connect(self.clear_spectrum)
        toolbar.addWidget(self.clear_btn)

        # Peak detection checkbox
        self.peak_checkbox = QCheckBox("Detect Peaks")
        self.peak_checkbox.setChecked(True)
        self.peak_checkbox.stateChanged.connect(self._redraw)
        toolbar.addWidget(self.peak_checkbox)
        
        # Smoothing checkbox
        self.smooth_checkbox = QCheckBox("Smooth")
        self.smooth_checkbox.setChecked(False)
        self.smooth_checkbox.stateChanged.connect(self._redraw)
        toolbar.addWidget(self.smooth_checkbox)

        self.status_label = QLabel(f"Channels: 0 / {self.CHANNELS}")
        toolbar.addStretch()
        toolbar.addWidget(self.status_label)

        layout.addLayout(toolbar)

        # Matplotlib figure
        self.figure = Figure(figsize=(10, 5), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        layout.addWidget(self.canvas)

        self.ax = self.figure.add_subplot(111)
        self.ax.set_xlabel("Energy (keV)")
        self.ax.set_ylabel("Counts")
        self.ax.set_title("Gamma Spectrum")
        self.ax.set_xlim(0, self.MAX_KEV)
        self.ax.set_ylim(0, 100)
        self.ax.grid(True, alpha=0.3)

        # Initial x values - will be updated when div changes
        self.x_vals = np.arange(self.CHANNELS) * self._get_kev_per_channel()
        self.line, = self.ax.plot(self.x_vals, self.spectrum, 'b-', linewidth=0.5)
        
        # For smoothed line (optional)
        self.smooth_line, = self.ax.plot([], [], 'r-', linewidth=1.0, alpha=0.7)

        self.figure.tight_layout()
    
    def _get_kev_per_channel(self) -> float:
        """Get keV per channel for full resolution spectrum.
        
        Spectrum is always stored in full resolution (1800 channels).
        Cs-137 peak (662 keV) appears at channel ~1485 (165 * 9).
        KEV_PER_CHANNEL = 662 / 1485 ≈ 0.446
        
        This is equivalent to: BASE (4.01) / 9 = 0.446
        """
        return self.KEV_PER_CHANNEL_BASE / 9.0

    def clear_spectrum(self):
        self.spectrum.fill(0)
        self.filled_channels.clear()
        self._clear_annotations()
        self._redraw()
        self.status_label.setText(f"Channels: 0 / {self.CHANNELS}")

    def _clear_annotations(self):
        """Remove all peak annotations."""
        for ann in self.peak_annotations:
            ann.remove()
        self.peak_annotations.clear()

    def update_spectrum(self, pkt: Dict):
        """Update spectrum from a parsed spectrum packet.
        
        Different packet types have different channel density:
        - 0x32 (div=9): ~200 channels, low resolution, FULL spectrum
        - 0x31 (div=3): ~600 channels, medium resolution, FRAGMENT
        - 0x30 (div=1): ~1800 channels, full resolution, FRAGMENT
        
        Parser returns channels in COMPRESSED indices (divided by div).
        We expand them here to full resolution (1800 channels).
        Each compressed channel maps to 'div' consecutive full-res channels.
        """
        bins = pkt.get("bins", {})
        div = pkt.get("div", 9)
        
        for ch, val in bins.items():
            ch = int(ch)
            # Map compressed channel to full resolution spectrum
            # ch=10 with div=3 → real channels 30-32 (10*3 to 10*3+2)
            base_ch = ch * div
            for i in range(div):
                real_ch = base_ch + i
                if 0 <= real_ch < self.CHANNELS:
                    self.spectrum[real_ch] = val
                    self.filled_channels.add(real_ch)

        self.status_label.setText(f"Channels: {len(self.filled_channels)} (div={div})")
        self._redraw()

    def _find_peaks(self, data: np.ndarray) -> List[int]:
        """Find peaks in spectrum data."""
        if not HAS_SCIPY:
            return []
        
        kev_per_ch = self._get_kev_per_channel()
        
        # Only look within displayed range
        max_ch = int(self.MAX_KEV / kev_per_ch)
        max_ch = min(max_ch, len(data))
        data_range = data[:max_ch]
        
        if len(data_range) == 0 or data_range.max() < 5:
            return []
        
        # Use configurable sensitivity (1-100 maps to 10%-1% of max for threshold)
        # Higher sensitivity = lower threshold = more peaks detected
        sensitivity_factor = (101 - self.peak_sensitivity) / 100.0  # 0.01 to 1.0
        height_threshold = max(data_range.max() * sensitivity_factor * 0.1, 3)
        prominence = max(data_range.max() * sensitivity_factor * 0.05, 2)
        
        peaks, properties = find_peaks(
            data_range,
            height=height_threshold,
            prominence=prominence,
            distance=10,  # Minimum distance between peaks (channels)
            width=2,      # Minimum peak width
        )
        
        return list(peaks)

    def _smooth_spectrum(self, data: np.ndarray) -> np.ndarray:
        """Apply Savitzky-Golay filter for smoothing."""
        if not HAS_SCIPY:
            return data
        
        # Use configurable window size, must be odd and smaller than data
        window = min(self.smooth_window, len(data) // 4)
        if window % 2 == 0:
            window -= 1
        if window < 5:
            return data
        
        return savgol_filter(data, window, 3)

    def set_peak_sensitivity(self, value: int):
        """Set peak detection sensitivity (1-100)."""
        self.peak_sensitivity = max(1, min(100, value))
        self.settings.setValue("peak/sensitivity", self.peak_sensitivity)

    def set_smooth_window(self, value: int):
        """Set smoothing window size (odd number 5-51)."""
        if value % 2 == 0:
            value += 1
        self.smooth_window = max(5, min(51, value))
        self.settings.setValue("smooth/window", self.smooth_window)

    def _redraw(self):
        # Clear old annotations
        self._clear_annotations()
        
        kev_per_ch = self._get_kev_per_channel()
        
        # Update x values for current div
        self.x_vals = np.arange(self.CHANNELS) * kev_per_ch
        
        # Get display data
        display_data = self.spectrum.copy()
        
        # Apply smoothing if enabled
        if self.smooth_checkbox.isChecked() and HAS_SCIPY:
            smoothed = self._smooth_spectrum(display_data)
            self.smooth_line.set_data(self.x_vals, smoothed)
            self.line.set_alpha(0.3)
        else:
            self.smooth_line.set_data([], [])
            self.line.set_alpha(1.0)
        
        self.line.set_data(self.x_vals, display_data)
        
        # Find and annotate peaks
        if self.peak_checkbox.isChecked():
            # Use smoothed data for peak detection if smoothing enabled
            peak_data = smoothed if (self.smooth_checkbox.isChecked() and HAS_SCIPY) else display_data
            peaks = self._find_peaks(peak_data)
            
            for ch in peaks:
                energy = ch * kev_per_ch
                count = display_data[ch]
                
                # Create annotation with channel and energy
                ann = self.ax.annotate(
                    f'ch{ch}\n{energy:.0f}keV',
                    xy=(energy, count),
                    xytext=(0, 15),
                    textcoords='offset points',
                    ha='center',
                    va='bottom',
                    fontsize=8,
                    color='red',
                    arrowprops=dict(arrowstyle='->', color='red', lw=0.5)
                )
                self.peak_annotations.append(ann)
        
        # Update Y limits based on visible range
        max_ch = int(self.MAX_KEV / kev_per_ch)
        max_ch = min(max_ch, len(display_data))
        visible_max = max(display_data[:max_ch].max() if max_ch > 0 else 10, 10)
        self.ax.set_ylim(0, visible_max * 1.15)
        
        self.canvas.draw_idle()
