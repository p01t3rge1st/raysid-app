"""CPS and dose rate display widget."""
from __future__ import annotations

from typing import Dict, List
from collections import deque

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import numpy as np


class CPSWidget(QWidget):
    """Widget displaying CPS (counts per second) and dose rate."""

    HISTORY_SIZE = 120  # seconds of history

    def __init__(self):
        super().__init__()
        self.cps_history = deque(maxlen=self.HISTORY_SIZE)
        self.dose_history = deque(maxlen=self.HISTORY_SIZE)

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Big numbers display
        numbers_frame = QFrame()
        numbers_frame.setFrameStyle(QFrame.StyledPanel)
        numbers_layout = QHBoxLayout(numbers_frame)

        big_font = QFont()
        big_font.setPointSize(48)
        big_font.setBold(True)

        # CPS
        cps_box = QVBoxLayout()
        cps_title = QLabel("CPS")
        cps_title.setAlignment(Qt.AlignCenter)
        cps_box.addWidget(cps_title)
        self.cps_label = QLabel("---")
        self.cps_label.setFont(big_font)
        self.cps_label.setAlignment(Qt.AlignCenter)
        cps_box.addWidget(self.cps_label)
        numbers_layout.addLayout(cps_box)

        # Dose rate
        dose_box = QVBoxLayout()
        dose_title = QLabel("Dose Rate (µSv/h)")
        dose_title.setAlignment(Qt.AlignCenter)
        dose_box.addWidget(dose_title)
        self.dose_label = QLabel("---")
        self.dose_label.setFont(big_font)
        self.dose_label.setAlignment(Qt.AlignCenter)
        dose_box.addWidget(self.dose_label)
        numbers_layout.addLayout(dose_box)

        layout.addWidget(numbers_frame)

        # History plot
        self.figure = Figure(figsize=(10, 3), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        layout.addWidget(self.canvas)

        self.ax = self.figure.add_subplot(111)
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("CPS")
        self.ax.set_title("CPS History")
        self.ax.set_xlim(-self.HISTORY_SIZE, 0)
        self.ax.set_ylim(0, 100)
        self.ax.grid(True, alpha=0.3)

        self.line, = self.ax.plot([], [], 'g-', linewidth=1)
        self.figure.tight_layout()

    def update_cps(self, pkt: Dict):
        """Update from a parsed CPS packet."""
        cps = pkt.get("cps", 0)
        dose = pkt.get("dose_rate", 0)

        self.cps_label.setText(f"{cps:.0f}")
        self.dose_label.setText(f"{dose:.3f}")

        self.cps_history.append(cps)
        self._redraw()

    def _redraw(self):
        n = len(self.cps_history)
        if n == 0:
            return
        x = np.arange(-n + 1, 1)
        y = np.array(self.cps_history)
        self.line.set_data(x, y)
        max_cps = max(y.max(), 10)
        self.ax.set_ylim(0, max_cps * 1.1)
        self.canvas.draw_idle()
