# main.py
"""
AM & FM Communication Systems Laboratory
=========================================
Application Launcher & Professional Landing Screen.
"""

import sys
import os
from pyqtgraph.Qt import QtWidgets, QtCore, QtGui
from dashboard import (
    MainWindow, BG_MAIN, BG_CARD,
    COLOR_CYAN, COLOR_GREEN, COLOR_GOLD, COLOR_PINK, COLOR_PURPLE,
    COLOR_ORANGE, COLOR_TEXT, COLOR_MUTED,
)

# ── Palette extensions (local to landing screen) ─────────────
_BG_SURFACE  = '#0a0e1f'
_BORDER_DIM  = '#151d3a'
_BORDER_MED  = '#1e2a55'
_TEXT_DIM     = '#4a5a80'
_TEXT_MID     = '#8899bb'


def _pill(text: str, fg: str, bg: str) -> QtWidgets.QLabel:
    """Small rounded capability badge."""
    lbl = QtWidgets.QLabel(text)
    lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
    lbl.setStyleSheet(
        f"color:{fg}; background:{bg}; border:1px solid {fg}40;"
        f"border-radius:3px; padding:2px 8px;"
        f"font-family:Consolas; font-size:8px; font-weight:bold;"
    )
    lbl.setSizePolicy(QtWidgets.QSizePolicy.Policy.Maximum,
                      QtWidgets.QSizePolicy.Policy.Fixed)
    return lbl


class LandingScreen(QtWidgets.QDialog):
    """Professional engineering-software entry screen."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AM & FM Communication Systems Laboratory")
        self.setMinimumSize(820, 540)
        self.resize(860, 580)
        self.setStyleSheet(
            f"background-color:{BG_MAIN}; color:{COLOR_TEXT};"
        )
        self.selected_tab = 0
        self._build()

    # ─── Layout ──────────────────────────────────────────────
    def _build(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 18)
        root.setSpacing(0)

        # ── 1. Title Block ───────────────────────────────────
        root.addLayout(self._title_block())
        root.addSpacing(16)

        # ── 2. Main content: Flow Diagram | Buttons ──────────
        body = QtWidgets.QHBoxLayout()
        body.setSpacing(18)

        body.addWidget(self._flow_diagram(), stretch=0)
        body.addLayout(self._button_column(), stretch=1)

        root.addLayout(body, stretch=1)
        root.addSpacing(14)

        # ── 3. Capability Strip ──────────────────────────────
        root.addWidget(self._capability_strip())
        root.addSpacing(10)

        # ── 4. Footer ────────────────────────────────────────
        footer = QtWidgets.QLabel(
            "Python + PyQt6 + PyQtGraph + SciPy + NumPy"
        )
        footer.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        footer.setStyleSheet(
            f"color:{_TEXT_DIM}; font-size:8px; font-family:Consolas;"
        )
        root.addWidget(footer)

    # ─── Title ───────────────────────────────────────────────
    def _title_block(self) -> QtWidgets.QVBoxLayout:
        box = QtWidgets.QVBoxLayout()
        box.setSpacing(3)

        title = QtWidgets.QLabel("AM & FM COMMUNICATION SYSTEMS LABORATORY")
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            f"color:{COLOR_CYAN}; font-size:16px; font-weight:bold;"
            f"font-family:Consolas; letter-spacing:1px;"
        )
        box.addWidget(title)

        sub = QtWidgets.QLabel(
            "Interactive Modulation, Demodulation & Signal Analysis"
        )
        sub.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet(
            f"color:{_TEXT_MID}; font-size:10px; font-family:sans-serif;"
        )
        box.addWidget(sub)

        return box

    # ─── Flow Diagram ────────────────────────────────────────
    def _flow_diagram(self) -> QtWidgets.QFrame:
        card = QtWidgets.QFrame()
        card.setFixedWidth(170)
        card.setStyleSheet(
            f"QFrame{{"
            f"  background:{_BG_SURFACE};"
            f"  border:1px solid {_BORDER_DIM};"
            f"  border-radius:6px;"
            f"}}"
        )
        col = QtWidgets.QVBoxLayout(card)
        col.setContentsMargins(12, 14, 12, 14)
        col.setSpacing(0)

        # Header
        hdr = QtWidgets.QLabel("SIGNAL FLOW")
        hdr.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        hdr.setStyleSheet(
            f"color:{COLOR_MUTED}; font-size:8px; font-weight:bold;"
            f"font-family:Consolas; letter-spacing:1px;"
            f"border:none; padding-bottom:6px;"
        )
        col.addWidget(hdr)

        stages = [
            ("MESSAGE",          COLOR_GREEN),
            ("MODULATION",       COLOR_GOLD),
            ("CHANNEL + NOISE",  COLOR_ORANGE),
            ("DEMODULATION",     COLOR_PINK),
            ("RECOVERED SIGNAL", COLOR_CYAN),
            ("SPECTRUM / PERF",  COLOR_PURPLE),
        ]

        for i, (label, color) in enumerate(stages):
            # Stage box
            stage = QtWidgets.QLabel(label)
            stage.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            stage.setStyleSheet(
                f"color:{color}; background:{color}0c;"
                f"border:1px solid {color}30; border-radius:3px;"
                f"padding:4px 6px;"
                f"font-family:Consolas; font-size:8px; font-weight:bold;"
            )
            col.addWidget(stage)

            # Arrow between stages (skip after last)
            if i < len(stages) - 1:
                arrow = QtWidgets.QLabel("\u2193")  # ↓
                arrow.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                arrow.setStyleSheet(
                    f"color:{_TEXT_DIM}; font-size:11px;"
                    f"border:none; padding:1px 0;"
                )
                col.addWidget(arrow)

        col.addStretch(1)
        return card

    # ─── Button Column ───────────────────────────────────────
    def _button_column(self) -> QtWidgets.QVBoxLayout:
        col = QtWidgets.QVBoxLayout()
        col.setSpacing(10)

        # ── Primary: START SIMULATOR (dominant) ──────────────
        start_btn = QtWidgets.QPushButton("START SIMULATOR")
        start_btn.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        start_btn.setMinimumHeight(72)
        start_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 {COLOR_CYAN}18, stop:1 {COLOR_CYAN}08
                );
                color: {COLOR_CYAN};
                border: 1.5px solid {COLOR_CYAN}88;
                border-radius: 6px;
                font-family: Consolas;
                font-size: 15px;
                font-weight: bold;
                letter-spacing: 2px;
                padding-bottom: 2px;
            }}
            QPushButton:hover {{
                background: {COLOR_CYAN}22;
                border: 1.5px solid {COLOR_CYAN};
            }}
            QPushButton:pressed {{
                background: {COLOR_CYAN}30;
            }}
        """)
        start_btn.setToolTip(
            "Launch the 8-panel real-time oscilloscope,\n"
            "spectrum analyzer, and measurement dashboard."
        )
        start_btn.clicked.connect(lambda: self._launch(0))

        # Subtitle under the big button
        start_hint = QtWidgets.QLabel(
            "Real-time oscilloscopes, RF spectrum, waterfall, "
            "channel noise, and live telemetry"
        )
        start_hint.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        start_hint.setStyleSheet(
            f"color:{_TEXT_DIM}; font-size:8px; font-family:sans-serif;"
        )

        col.addWidget(start_btn)
        col.addWidget(start_hint)
        col.addSpacing(4)

        # ── Secondary row: 3 buttons ─────────────────────────
        row1 = QtWidgets.QHBoxLayout()
        row1.setSpacing(8)

        row1.addWidget(self._option_btn(
            "EXPERIMENT LAB", COLOR_GREEN, 1,
            "10 automated ECE experiments with\n"
            "measurements, validation & conclusions"
        ))
        row1.addWidget(self._option_btn(
            "AM vs FM", COLOR_GOLD, 2,
            "Side-by-side performance comparison\n"
            "and live Monte-Carlo SNR sweep"
        ))
        row1.addWidget(self._option_btn(
            "3D / SPECTROGRAM", COLOR_PURPLE, 3,
            "Time-frequency spectrogram analysis\n"
            "and parameter sweep surfaces"
        ))

        col.addLayout(row1)

        # ── Tertiary row: 2 buttons ──────────────────────────
        row2 = QtWidgets.QHBoxLayout()
        row2.setSpacing(8)

        row2.addWidget(self._option_btn(
            "VIVA / DEMO", COLOR_PINK, 4,
            "Guided 2-minute step-by-step\n"
            "presentation walkthrough"
        ))
        row2.addWidget(self._option_btn(
            "THEORY & HELP", "#55ddbb", 5,
            "Mathematical formulas, equations,\n"
            "and communication-systems reference"
        ))

        col.addLayout(row2)
        col.addStretch(1)

        return col

    def _option_btn(
        self, text: str, color: str, tab_idx: int, tooltip: str
    ) -> QtWidgets.QPushButton:
        """Secondary / tertiary navigation button."""
        btn = QtWidgets.QPushButton(text)
        btn.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        btn.setMinimumHeight(44)
        btn.setToolTip(tooltip)
        btn.setStyleSheet(f"""
            QPushButton {{
                background: {_BG_SURFACE};
                color: {color};
                border: 1px solid {color}35;
                border-radius: 5px;
                font-family: Consolas;
                font-size: 10px;
                font-weight: bold;
                letter-spacing: 0.5px;
            }}
            QPushButton:hover {{
                background: {color}12;
                border: 1px solid {color}90;
            }}
            QPushButton:pressed {{
                background: {color}20;
            }}
        """)
        btn.clicked.connect(lambda: self._launch(tab_idx))
        return btn

    # ─── Capability Strip ────────────────────────────────────
    def _capability_strip(self) -> QtWidgets.QFrame:
        bar = QtWidgets.QFrame()
        bar.setStyleSheet(
            f"QFrame{{background:transparent; border:none;}}"
        )
        row = QtWidgets.QHBoxLayout(bar)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)

        row.addStretch(1)

        caps = [
            ("AM",           COLOR_GOLD),
            ("FM",           COLOR_PINK),
            ("FFT",          COLOR_PURPLE),
            ("AWGN",         COLOR_ORANGE),
            ("DEMODULATION", COLOR_GREEN),
            ("SNR",          COLOR_CYAN),
            ("BANDWIDTH",    _TEXT_MID),
        ]
        for label, color in caps:
            row.addWidget(_pill(label, color, f"{color}0a"))

        row.addStretch(1)
        return bar

    # ─── Actions ─────────────────────────────────────────────
    def _launch(self, tab_idx: int):
        self.selected_tab = tab_idx
        self.accept()


# ═════════════════════════════════════════════════════════════
#  APPLICATION ENTRY POINT
# ═════════════════════════════════════════════════════════════

def main():
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("AM/FM Communication Systems Laboratory")

    landing = LandingScreen()
    if landing.exec() == QtWidgets.QDialog.DialogCode.Accepted:
        win = MainWindow()
        win._tab_stack.setCurrentIndex(landing.selected_tab)
        win.show()
        sys.exit(app.exec())


if __name__ == "__main__":
    main()
