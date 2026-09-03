# dashboard.py
"""
AM & FM Communication Systems Simulator
========================================
Interactive Modulation, Demodulation & Signal Analysis Laboratory
Complete ECE Undergraduate Communication Systems Virtual Lab Workbench.
"""

import sys
import os
import time
import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt import QtWidgets, QtCore, QtGui
import scipy.signal
import matplotlib
matplotlib.use('QtAgg')
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

sys.path.insert(0, os.path.dirname(__file__))
from waveforms import generate_waveform
from signal_sources import WaveformSource, MicSource, WavSource, ToneSource
from modulator import AMModulator, FMModulator
from channel import Channel
from demodulator import AMDemodulator, FMDemodulator, compute_reconstruction_metrics
from spectrum import SpectrumAnalyzer
from measurements import SystemMetrics
from experiments import EXPERIMENT_LIST, ExperimentRunner
from nco import NCO
from simulation_engine import SimulationEngine, FrameResult
from sweep_engine import ParameterSweep

# ── Constants & DSP Configuration ────────────────────────────
SR = 44100.0
DISP_SECS = 0.04
DISP_N = int(SR * DISP_SECS)
FC_DEFAULT = 10000.0
FM_DEFAULT = 1000.0
FFT_SIZE = 4096

# ECE Lab Palette (Clean Dark Engineering Theme)
BG_MAIN = '#070913'
BG_CARD = '#0d1124'
BG_SIDEBAR = '#0a0e20'
BG_PLOT = '#080a18'

COLOR_CYAN = '#00e5ff'
COLOR_GREEN = '#00ff88'
COLOR_GOLD = '#ffd700'
COLOR_PINK = '#ff2d78'
COLOR_PURPLE = '#bf00ff'
COLOR_ORANGE = '#ff7700'
COLOR_RED = '#ff1744'
COLOR_TEXT = '#d0d8f0'
COLOR_MUTED = '#6c7a9c'


def make_neon_pen(hex_color: str, width: float = 1.5, style=QtCore.Qt.PenStyle.SolidLine):
    return pg.mkPen(hex_color, width=width, style=style)


# ═════════════════════════════════════════════════════════════
#  CUSTOM ECE LAB UI COMPONENTS
# ═════════════════════════════════════════════════════════════

class ECECard(QtWidgets.QFrame):
    """Clean card container with subtle glowing border."""
    def __init__(self, border_color: str = '#1a2244', bg_color: str = BG_CARD, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: 6px;
            }}
        """)


class MetricBadge(QtWidgets.QFrame):
    """Digital LCD-style measurement badge."""
    def __init__(self, label: str, value: str = "---", unit: str = "",
                 color: str = COLOR_CYAN, parent=None):
        super().__init__(parent)
        self._label = label
        self._unit = unit
        self._color = color
        self.setStyleSheet(f"""
            QFrame {{
                background-color: #050711;
                border: 1px solid {color}44;
                border-radius: 4px;
                padding: 2px 5px;
            }}
        """)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(1)

        self._lbl_title = QtWidgets.QLabel(label.upper())
        self._lbl_title.setStyleSheet(f"color: {COLOR_MUTED}; font-size: 8px; font-weight: bold; font-family: Consolas;")
        layout.addWidget(self._lbl_title)

        self._lbl_val = QtWidgets.QLabel(f"{value} {unit}".strip())
        self._lbl_val.setStyleSheet(f"color: {color}; font-size: 11px; font-weight: bold; font-family: Consolas;")
        layout.addWidget(self._lbl_val)

    def set_value(self, value: str, custom_color: str = None):
        c = custom_color or self._color
        self._lbl_val.setText(f"{value} {self._unit}".strip())
        self._lbl_val.setStyleSheet(f"color: {c}; font-size: 11px; font-weight: bold; font-family: Consolas;")


class LabSlider(QtWidgets.QWidget):
    """
    Precise engineering slider with direct numerical feedback and efficient parameter dispatch.
    """
    valueChanged = QtCore.pyqtSignal(float)

    def __init__(self, label: str, min_val: float, max_val: float, init_val: float,
                 scale: float = 1.0, unit: str = "", color: str = COLOR_CYAN, parent=None):
        super().__init__(parent)
        self._scale = scale
        self._unit = unit
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 1, 0, 1)
        layout.setSpacing(6)

        lbl = QtWidgets.QLabel(label)
        lbl.setStyleSheet(f"color: {COLOR_TEXT}; font-size: 9px; font-family: Consolas; font-weight: bold;")
        lbl.setFixedWidth(75)
        layout.addWidget(lbl)

        self._slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self._slider.setRange(int(min_val / scale), int(max_val / scale))
        self._slider.setValue(int(init_val / scale))
        self._slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                height: 4px;
                background: #141a33;
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background: {color};
                border: 1px solid #ffffff;
                width: 12px; height: 12px;
                margin: -4px 0;
                border-radius: 6px;
            }}
            QSlider::sub-page:horizontal {{
                background: {color}88;
                border-radius: 2px;
            }}
        """)
        self._slider.valueChanged.connect(self._on_change)
        layout.addWidget(self._slider)

        self._val_lbl = QtWidgets.QLabel(f"{init_val:.2f} {unit}".strip())
        self._val_lbl.setStyleSheet(f"color: {color}; font-size: 9px; font-family: Consolas; font-weight: bold;")
        self._val_lbl.setFixedWidth(60)
        self._val_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self._val_lbl)

    def _on_change(self, v):
        real = v * self._scale
        if abs(real) >= 1000:
            txt = f"{real:.0f} {self._unit}"
        elif abs(real) >= 10:
            txt = f"{real:.1f} {self._unit}"
        else:
            txt = f"{real:.2f} {self._unit}"
        self._val_lbl.setText(txt.strip())
        self.valueChanged.emit(real)

    def value(self) -> float:
        return self._slider.value() * self._scale

    def set_value(self, val: float):
        self._slider.blockSignals(True)
        self._slider.setValue(int(val / self._scale))
        self._slider.blockSignals(False)
        real = self.value()
        if abs(real) >= 1000:
            txt = f"{real:.0f} {self._unit}"
        elif abs(real) >= 10:
            txt = f"{real:.1f} {self._unit}"
        else:
            txt = f"{real:.2f} {self._unit}"
        self._val_lbl.setText(txt.strip())



# ═════════════════════════════════════════════════════════════
#  WORKERS
# ═════════════════════════════════════════════════════════════
class _ExperimentWorker(QtCore.QThread):
    finished = QtCore.pyqtSignal(dict)
    def __init__(self, runner, exp_id):
        super().__init__()
        self._runner = runner
        self._exp_id = exp_id
    def run(self):
        result = self._runner.run_experiment(self._exp_id)
        self.finished.emit(result)

class _SweepWorker(QtCore.QThread):
    finished = QtCore.pyqtSignal(object, object, object)
    def __init__(self):
        super().__init__()
    def run(self):
        snr_in = np.arange(5, 41, 5)
        am_out_snr = []
        fm_out_snr = []

        msg = generate_waveform('sine', 1000.0, 1.0, 0.0, 4096, SR)
        am_mod = AMModulator(10000.0, 1.0, 0.8, 'DSB-FC', SR)
        fm_mod = FMModulator(10000.0, 1.0, 4000.0, SR)
        am_sig, _, _, _ = am_mod.process(msg)
        fm_sig, _, _, _ = fm_mod.process(msg, 1000.0)

        am_demod = AMDemodulator('ENVELOPE', 10000.0, 4000.0, SR)
        fm_demod = FMDemodulator(4000.0, SR)

        for s in snr_in:
            ch = Channel(SR)
            ch.set_params(noise_enabled=True, snr_db=float(s))

            n_am, _ = ch.process(am_sig)
            r_am = am_demod.process(n_am)
            m_am = compute_reconstruction_metrics(msg, r_am)
            am_out_snr.append(m_am['psnr_db'])

            n_fm, _ = ch.process(fm_sig)
            r_fm = fm_demod.process(n_fm)
            m_fm = compute_reconstruction_metrics(msg, r_fm)
            fm_out_snr.append(m_fm['psnr_db'])

        self.finished.emit(snr_in, am_out_snr, fm_out_snr)



class _Sweep3DWorker(QtCore.QThread):
    finished = QtCore.pyqtSignal(object, object, object)
    
    def run(self):
        m_vals = np.linspace(0.1, 1.5, 8)
        snr_vals = np.linspace(5, 35, 7)
        
        M, S = np.meshgrid(m_vals, snr_vals)
        Z = np.zeros_like(M)
        
        # Generate clean msg
        msg = generate_waveform('sine', 1000.0, 1.0, 0.0, 4096, SR)
        demod = AMDemodulator('ENVELOPE', 10000.0, 4000.0, SR)
        
        for i in range(M.shape[0]):
            for j in range(M.shape[1]):
                m = M[i, j]
                snr = S[i, j]
                
                mod = AMModulator(10000.0, 1.0, float(m), 'DSB-FC', SR)
                sig, _, _, _ = mod.process(msg)
                
                ch = Channel(SR)
                ch.set_params(noise_enabled=True, snr_db=float(snr))
                n_sig, _ = ch.process(sig)
                
                rec = demod.process(n_sig)
                metrics = compute_reconstruction_metrics(msg, rec)
                
                Z[i, j] = metrics['correlation']
                
        self.finished.emit(M, S, Z)

# ═════════════════════════════════════════════════════════════
#  MAIN LAB WORKBENCH WINDOW

# ═════════════════════════════════════════════════════════════

class MainWindow(QtWidgets.QMainWindow):
    """
    Complete ECE Communication Systems Laboratory Dashboard.
    Layout Structure:
      - TOP: Navigation header, Presets, Simulation control, Communication Flow bar
      - LEFT: Organized parameter and control panels
      - CENTER/RIGHT: Real-time multi-viewport visualization area
      - BOTTOM: Measurements, theoretical validation, and performance area
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AM & FM Communication Systems Laboratory")
        self.setMinimumSize(1420, 880)
        self.setStyleSheet(f"background-color: {BG_MAIN}; color: {COLOR_TEXT};")

        # Global PyQtGraph configuration
        pg.setConfigOptions(antialias=True, background=BG_PLOT, foreground=COLOR_MUTED)

        # ── State & Simulation Control ─────────────────────────
        self._is_paused = False
        self._display_filter = 'All'  # 'All' | 'Time' | 'Freq' | 'AM' | 'FM'
        self._am_enabled = True
        self._fm_enabled = True

        # ── Parameters ─────────────────────────────────────────
        self._fc = FC_DEFAULT
        self._ac = 1.0
        self._phase_c = 0.0
        self._fm = FM_DEFAULT
        self._am = 1.0
        self._phase_m = 0.0
        self._msg_type = 'sine'
        self._am_m = 0.8
        self._am_mode = 'DSB-FC'
        self._fm_delta_f = 4000.0

        # ── DSP Engines ────────────────────────────────────────
        self._src = WaveformSource('sine', self._fm, self._am, self._phase_m, sr=SR)
        self._carrier_nco = NCO(self._fc, SR, self._phase_c)
        self._am_mod = AMModulator(self._fc, self._ac, self._am_m, self._am_mode, SR)
        self._fm_mod = FMModulator(self._fc, self._ac, self._fm_delta_f, SR)
        self._channel = Channel(SR)
        self._am_demod = AMDemodulator('ENVELOPE', self._fc, 4000.0, SR)
        self._fm_demod = FMDemodulator(4000.0, SR)
        self._spec_am = SpectrumAnalyzer(SR, FFT_SIZE, waterfall_n=80)
        self._spec_fm = SpectrumAnalyzer(SR, FFT_SIZE, waterfall_n=80)
        self._exp_runner = ExperimentRunner(SR)

        self._time_axis_ms = np.linspace(0, DISP_SECS * 1000.0, DISP_N)

        # Build complete UI
        self._build_ui()
        self._src.start()

        # Real-time refresh loop (30 FPS)
        self._timer = QtCore.QTimer()
        self._timer.timeout.connect(self._on_tick)
        self._timer.start(int(1000.0 / 30.0))

    # ─────────────────────────────────────────────────────────
    #  UI LAYOUT CONSTRUCTION
    # ─────────────────────────────────────────────────────────
    def _build_ui(self):
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        root = QtWidgets.QVBoxLayout(central)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(4)

        # 1. Header Bar with Navigation Tabs
        root.addWidget(self._build_header_bar())

        # 2. Communication Signal Flow Indicator
        root.addWidget(self._build_flow_indicator())

        # 3. Main Stacked Views (Simulator, Experiments, AM vs FM, 3D, Demo, Theory)
        self._tab_stack = QtWidgets.QStackedWidget()
        root.addWidget(self._tab_stack, stretch=1)

        # Tab 0: Primary Engineering Simulator View (Left Control Panel + Center Scopes + Bottom Telemetry)
        self._sim_view = self._build_simulator_view()
        self._tab_stack.addWidget(self._sim_view)

        # Tab 1: Experiment Laboratory View
        self._exp_view = self._build_experiment_view()
        self._tab_stack.addWidget(self._exp_view)

        # Tab 2: AM vs FM Performance Comparison View
        self._comp_view = self._build_comparison_view()
        self._tab_stack.addWidget(self._comp_view)

        # Tab 3: Advanced 3D & Time-Frequency View
        self._adv_view = self._build_advanced_view()
        self._tab_stack.addWidget(self._adv_view)

        # Tab 4: Viva / Demo Mode View
        self._demo_view = self._build_demo_view()
        self._tab_stack.addWidget(self._demo_view)

        # Tab 5: Theory & Educational Help
        self._theory_view = self._build_theory_view()
        self._tab_stack.addWidget(self._theory_view)

    def _build_header_bar(self) -> QtWidgets.QWidget:
        header = ECECard(border_color='#1d264a')
        layout = QtWidgets.QHBoxLayout(header)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(10)

        # Title & Subtitle
        title_box = QtWidgets.QVBoxLayout()
        title_box.setSpacing(1)
        lbl_title = QtWidgets.QLabel("AM & FM COMMUNICATION SYSTEMS LABORATORY")
        lbl_title.setStyleSheet(f"color: {COLOR_CYAN}; font-size: 12px; font-weight: bold; font-family: Consolas;")
        lbl_sub = QtWidgets.QLabel("Real-Time Modulation, Channel Noise, Demodulation & Spectrum Analysis Workbench")
        lbl_sub.setStyleSheet(f"color: {COLOR_MUTED}; font-size: 8px; font-family: sans-serif;")
        title_box.addWidget(lbl_title)
        title_box.addWidget(lbl_sub)
        layout.addLayout(title_box)

        layout.addStretch()

        # Presets Menu
        layout.addWidget(QtWidgets.QLabel("<b style='color:#a0b0d0;font-size:9px;'>PRESETS:</b>"))
        self._preset_combo = QtWidgets.QComboBox()
        self._preset_combo.addItems([
            "Select Preset...",
            "AM: 50% Mod (Clean)",
            "AM: 100% Mod (Optimal)",
            "AM: Overmodulated (m=1.6)",
            "FM: Narrowband (NBFM)",
            "FM: Wideband (WBFM)",
            "Channel: High Noise (10dB)",
            "Reset Defaults"
        ])
        self._preset_combo.setStyleSheet("background:#10152b; color:#d0d8f0; border:1px solid #304070; padding:2px 6px; font-family:Consolas; font-size:9px;")
        self._preset_combo.currentIndexChanged.connect(self._on_preset_selected)
        layout.addWidget(self._preset_combo)

        layout.addSpacing(10)

        # Navigation Tab Buttons
        nav_tabs = [
            ("🔬 Simulator", 0),
            ("🧪 Experiment Lab", 1),
            ("⚖️ AM vs FM", 2),
            ("🧊 3D / Spectrogram", 3),
            ("🎯 Viva Demo", 4),
            ("📖 Theory & Help", 5),
        ]
        self._nav_btn_group = QtWidgets.QButtonGroup(self)
        for title, idx in nav_tabs:
            btn = QtWidgets.QPushButton(title)
            btn.setCheckable(True)
            btn.setChecked(idx == 0)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: #141b38; color: {COLOR_TEXT}; border: 1px solid #253366;
                    border-radius: 4px; padding: 4px 10px; font-size: 9px; font-family: Consolas; font-weight: bold;
                }}
                QPushButton:hover {{
                    background: #1e2850; border: 1px solid {COLOR_CYAN};
                }}
                QPushButton:checked {{
                    background: #00e5ff33; color: {COLOR_CYAN}; border: 1px solid {COLOR_CYAN};
                }}
            """)
            btn.clicked.connect(lambda checked, i=idx: self._tab_stack.setCurrentIndex(i))
            self._nav_btn_group.addButton(btn)
            layout.addWidget(btn)

        return header

    def _build_flow_indicator(self) -> QtWidgets.QWidget:
        """Visual stage indicator for the communication pipeline."""
        strip = ECECard(border_color='#151d38', bg_color='#060814')
        layout = QtWidgets.QHBoxLayout(strip)
        layout.setContentsMargins(10, 2, 10, 2)
        layout.setSpacing(6)

        stages = [
            ("1. MESSAGE m(t)", COLOR_GREEN),
            ("➔", COLOR_MUTED),
            ("2. MODULATION s(t)", COLOR_GOLD),
            ("➔", COLOR_MUTED),
            ("3. CHANNEL (+AWGN) r(t)", COLOR_ORANGE),
            ("➔", COLOR_MUTED),
            ("4. DEMODULATION m̂(t)", COLOR_PINK),
            ("➔", COLOR_MUTED),
            ("5. RECOVERED OUTPUT & SPECTRUM", COLOR_CYAN),
        ]
        for text, col in stages:
            lbl = QtWidgets.QLabel(text)
            lbl.setStyleSheet(f"color:{col}; font-size:8px; font-weight:bold; font-family:Consolas;")
            layout.addWidget(lbl)

        layout.addStretch()
        return strip

    # ─────────────────────────────────────────────────────────
    #  TAB 0: PRIMARY SIMULATOR VIEW
    #  (LEFT: Controls | CENTER: Plots | BOTTOM: Measurements)
    # ─────────────────────────────────────────────────────────
    def _build_simulator_view(self) -> QtWidgets.QWidget:
        view = QtWidgets.QWidget()
        main_layout = QtWidgets.QVBoxLayout(view)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(4)

        # Upper region: Splitter between Left Control Panel and Center Visualization
        split_widget = QtWidgets.QWidget()
        split_layout = QtWidgets.QHBoxLayout(split_widget)
        split_layout.setContentsMargins(0, 0, 0, 0)
        split_layout.setSpacing(6)

        # ── LEFT: Control / Parameter Panel ───────────────────
        left_panel = self._build_left_control_panel()
        split_layout.addWidget(left_panel, stretch=0)

        # ── CENTER/RIGHT: Real-Time Visualization Area ────────
        center_panel = self._build_center_visualization_area()
        split_layout.addWidget(center_panel, stretch=1)

        main_layout.addWidget(split_widget, stretch=1)

        # ── BOTTOM: Live Measurements & Performance Area ──────
        bottom_panel = self._build_bottom_measurement_area()
        main_layout.addWidget(bottom_panel, stretch=0)

        return view

    def _build_left_control_panel(self) -> QtWidgets.QWidget:
        """Left parameter and control panel."""
        scroll = QtWidgets.QScrollArea()
        scroll.setFixedWidth(330)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"""
            QScrollArea {{
                background-color: {BG_SIDEBAR};
                border: 1px solid #1a2244;
                border-radius: 6px;
            }}
            QScrollBar:vertical {{
                background: #080c1e;
                width: 6px;
            }}
            QScrollBar::handle:vertical {{
                background: #202b55;
                border-radius: 3px;
            }}
        """)

        container = QtWidgets.QWidget()
        container.setStyleSheet(f"background-color: {BG_SIDEBAR};")
        layout = QtWidgets.QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # 1. Simulation Control (Run, Pause, Reset)
        layout.addWidget(self._build_sim_ctrl_card())

        # 2. Display View Filter
        layout.addWidget(self._build_display_filter_card())

        # 3. Message Signal Controls
        layout.addWidget(self._build_message_ctrl_card())

        # 4. Carrier Controls
        layout.addWidget(self._build_carrier_ctrl_card())

        # 5. AM Controls
        layout.addWidget(self._build_am_ctrl_card())

        # 6. FM Controls
        layout.addWidget(self._build_fm_ctrl_card())

        # 7. Channel & Noise Controls
        layout.addWidget(self._build_channel_ctrl_card())

        layout.addStretch()
        scroll.setWidget(container)
        return scroll

    def _build_sim_ctrl_card(self) -> QtWidgets.QFrame:
        card = ECECard(border_color='#253366', bg_color='#0b1028')
        lay = QtWidgets.QVBoxLayout(card)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(4)

        lay.addWidget(QtWidgets.QLabel("<b style='color:#00e5ff;font-size:9px;'>⚡ SIMULATION CONTROL</b>"))

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.setSpacing(4)

        self._btn_run = QtWidgets.QPushButton("▶ RUN")
        self._btn_run.setStyleSheet("""
            QPushButton { background: #00ff8822; color: #00ff88; border: 1px solid #00ff88; border-radius: 3px; font-weight: bold; font-family: Consolas; font-size: 9px; padding: 4px; }
            QPushButton:hover { background: #00ff8844; }
        """)
        self._btn_run.clicked.connect(self._on_sim_run)

        self._btn_pause = QtWidgets.QPushButton("⏸ PAUSE")
        self._btn_pause.setStyleSheet("""
            QPushButton { background: #ffd70022; color: #ffd700; border: 1px solid #ffd700; border-radius: 3px; font-weight: bold; font-family: Consolas; font-size: 9px; padding: 4px; }
            QPushButton:hover { background: #ffd70044; }
        """)
        self._btn_pause.clicked.connect(self._on_sim_pause)

        self._btn_reset = QtWidgets.QPushButton("🔄 RESET")
        self._btn_reset.setStyleSheet("""
            QPushButton { background: #ff2d7822; color: #ff2d78; border: 1px solid #ff2d78; border-radius: 3px; font-weight: bold; font-family: Consolas; font-size: 9px; padding: 4px; }
            QPushButton:hover { background: #ff2d7844; }
        """)
        self._btn_reset.clicked.connect(self._on_sim_reset)

        btn_row.addWidget(self._btn_run)
        btn_row.addWidget(self._btn_pause)
        btn_row.addWidget(self._btn_reset)
        lay.addLayout(btn_row)

        return card

    def _build_display_filter_card(self) -> QtWidgets.QFrame:
        card = ECECard(border_color='#1a2448', bg_color='#0b1028')
        lay = QtWidgets.QVBoxLayout(card)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(4)

        lay.addWidget(QtWidgets.QLabel("<b style='color:#a0b0d0;font-size:9px;'>👁️ DISPLAY FILTER</b>"))
        self._display_combo = QtWidgets.QComboBox()
        self._display_combo.addItems([
            "All Plots (Full Lab Grid)",
            "Time-Domain Scopes Only",
            "Frequency Spectrum & Waterfall Only",
            "AM Modulation Pipeline Focus",
            "FM Modulation Pipeline Focus"
        ])
        self._display_combo.setStyleSheet("background:#080d20; color:#d0d8f0; border:1px solid #203060; padding:2px 4px; font-family:Consolas; font-size:9px;")
        self._display_combo.currentIndexChanged.connect(self._on_display_filter_changed)
        lay.addWidget(self._display_combo)
        return card

    def _build_message_ctrl_card(self) -> QtWidgets.QFrame:
        card = ECECard(border_color='#00ff8844', bg_color='#091024')
        lay = QtWidgets.QVBoxLayout(card)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(4)

        lay.addWidget(QtWidgets.QLabel("<b style='color:#00ff88;font-size:9px;'>1. MESSAGE SIGNAL m(t)</b>"))

        # Waveform type selector
        type_row = QtWidgets.QHBoxLayout()
        type_row.addWidget(QtWidgets.QLabel("<span style='color:#a0b0d0;font-size:9px;'>Type:</span>"))
        self._msg_type_combo = QtWidgets.QComboBox()
        self._msg_type_combo.addItems(["Sine", "Square", "Triangle", "Sawtooth", "Chirp", "Multi-Tone", "Live Mic", "Audio File"])
        self._msg_type_combo.setStyleSheet("background:#080d20; color:#00ff88; border:1px solid #00ff8855; padding:2px 4px; font-family:Consolas; font-size:9px;")
        self._msg_type_combo.currentIndexChanged.connect(self._on_msg_type_changed)
        type_row.addWidget(self._msg_type_combo)
        lay.addLayout(type_row)

        # Message Frequency
        self._sl_fm = LabSlider("Freq (fm):", 100.0, 5000.0, self._fm, scale=50.0, unit="Hz", color=COLOR_GREEN)
        self._sl_fm.valueChanged.connect(self._on_fm_changed)
        lay.addWidget(self._sl_fm)

        # Message Amplitude
        self._sl_am = LabSlider("Amp (Am):", 0.1, 2.0, self._am, scale=0.05, unit="V", color=COLOR_GREEN)
        self._sl_am.valueChanged.connect(self._on_am_amp_changed)
        lay.addWidget(self._sl_am)

        # Message Phase
        self._sl_phase_m = LabSlider("Phase (φm):", 0.0, 360.0, 0.0, scale=10.0, unit="°", color=COLOR_GREEN)
        self._sl_phase_m.valueChanged.connect(self._on_phase_m_changed)
        lay.addWidget(self._sl_phase_m)

        return card

    def _build_carrier_ctrl_card(self) -> QtWidgets.QFrame:
        card = ECECard(border_color='#00e5ff44', bg_color='#091024')
        lay = QtWidgets.QVBoxLayout(card)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(4)

        lay.addWidget(QtWidgets.QLabel("<b style='color:#00e5ff;font-size:9px;'>2. CARRIER SIGNAL c(t)</b>"))

        # Carrier Frequency
        self._sl_fc = LabSlider("Freq (fc):", 2000.0, 18000.0, self._fc, scale=100.0, unit="Hz", color=COLOR_CYAN)
        self._sl_fc.valueChanged.connect(self._on_fc_changed)
        lay.addWidget(self._sl_fc)

        # Carrier Amplitude
        self._sl_ac = LabSlider("Amp (Ac):", 0.1, 2.0, self._ac, scale=0.05, unit="V", color=COLOR_CYAN)
        self._sl_ac.valueChanged.connect(self._on_ac_amp_changed)
        lay.addWidget(self._sl_ac)

        # Carrier Phase
        self._sl_phase_c = LabSlider("Phase (φc):", 0.0, 360.0, 0.0, scale=10.0, unit="°", color=COLOR_CYAN)
        self._sl_phase_c.valueChanged.connect(self._on_phase_c_changed)
        lay.addWidget(self._sl_phase_c)

        return card

    def _build_am_ctrl_card(self) -> QtWidgets.QFrame:
        card = ECECard(border_color='#ffd70044', bg_color='#091024')
        lay = QtWidgets.QVBoxLayout(card)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(4)

        hdr_row = QtWidgets.QHBoxLayout()
        self._chk_am = QtWidgets.QCheckBox("AM ENABLED")
        self._chk_am.setChecked(True)
        self._chk_am.setStyleSheet("color:#ffd700; font-family:Consolas; font-weight:bold; font-size:9px;")
        self._chk_am.stateChanged.connect(lambda s: self._set_am_enabled(s == 2))
        hdr_row.addWidget(self._chk_am)
        hdr_row.addStretch()
        lay.addLayout(hdr_row)

        # AM Mode (DSB-FC, DSB-SC, SSB-USB, SSB-LSB)
        mode_row = QtWidgets.QHBoxLayout()
        mode_row.addWidget(QtWidgets.QLabel("<span style='color:#a0b0d0;font-size:9px;'>Mode:</span>"))
        self._am_mode_combo = QtWidgets.QComboBox()
        self._am_mode_combo.addItems(["DSB-FC (Standard)", "DSB-SC (Suppressed)", "SSB-USB (Upper)", "SSB-LSB (Lower)"])
        self._am_mode_combo.setStyleSheet("background:#080d20; color:#ffd700; border:1px solid #ffd70055; padding:2px 4px; font-family:Consolas; font-size:9px;")
        self._am_mode_combo.currentIndexChanged.connect(self._on_am_mode_changed)
        mode_row.addWidget(self._am_mode_combo)
        lay.addLayout(mode_row)

        # Modulation Index m
        self._sl_am_m = LabSlider("Index (m):", 0.0, 2.5, self._am_m, scale=0.05, unit="", color=COLOR_GOLD)
        self._sl_am_m.valueChanged.connect(self._on_am_m_changed)
        lay.addWidget(self._sl_am_m)

        return card

    def _build_fm_ctrl_card(self) -> QtWidgets.QFrame:
        card = ECECard(border_color='#ff2d7844', bg_color='#091024')
        lay = QtWidgets.QVBoxLayout(card)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(4)

        hdr_row = QtWidgets.QHBoxLayout()
        self._chk_fm = QtWidgets.QCheckBox("FM ENABLED")
        self._chk_fm.setChecked(True)
        self._chk_fm.setStyleSheet("color:#ff2d78; font-family:Consolas; font-weight:bold; font-size:9px;")
        self._chk_fm.stateChanged.connect(lambda s: self._set_fm_enabled(s == 2))
        hdr_row.addWidget(self._chk_fm)
        hdr_row.addStretch()
        lay.addLayout(hdr_row)

        # Frequency Deviation Δf
        self._sl_fm_df = LabSlider("Dev (Δf):", 500.0, 10000.0, self._fm_delta_f, scale=250.0, unit="Hz", color=COLOR_PINK)
        self._sl_fm_df.valueChanged.connect(self._on_fm_df_changed)
        lay.addWidget(self._sl_fm_df)

        return card

    def _build_channel_ctrl_card(self) -> QtWidgets.QFrame:
        card = ECECard(border_color='#ff770044', bg_color='#091024')
        lay = QtWidgets.QVBoxLayout(card)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(4)

        lay.addWidget(QtWidgets.QLabel("<b style='color:#ff7700;font-size:9px;'>3. CHANNEL & NOISE</b>"))

        # AWGN Noise toggle
        self._noise_chk = QtWidgets.QCheckBox("AWGN Noise Generator")
        self._noise_chk.setStyleSheet("color:#ff7700; font-family:Consolas; font-weight:bold; font-size:9px;")
        self._noise_chk.stateChanged.connect(lambda s: self._channel.set_params(noise_enabled=(s == 2)))
        lay.addWidget(self._noise_chk)

        # SNR in dB
        self._sl_snr = LabSlider("SNR (dB):", 5.0, 40.0, 25.0, scale=1.0, unit="dB", color=COLOR_ORANGE)
        self._sl_snr.valueChanged.connect(lambda v: self._channel.set_params(snr_db=v))
        lay.addWidget(self._sl_snr)

        # Attenuation in dB
        self._sl_atten = LabSlider("Path Loss:", 0.0, 30.0, 0.0, scale=1.0, unit="dB", color='#ffaa44')
        self._sl_atten.valueChanged.connect(lambda v: self._channel.set_params(attenuation_db=v))
        lay.addWidget(self._sl_atten)

        # Interference
        self._interf_chk = QtWidgets.QCheckBox("Interference Tone (7.5kHz)")
        self._interf_chk.setStyleSheet("color:#aa88ff; font-family:Consolas; font-size:8px;")
        self._interf_chk.stateChanged.connect(lambda s: self._channel.set_params(interference_enabled=(s == 2)))
        lay.addWidget(self._interf_chk)

        return card

    # ─────────────────────────────────────────────────────────
    #  CENTER/RIGHT: VISUALIZATION AREA (8 Modular Plots)
    # ─────────────────────────────────────────────────────────
    def _build_center_visualization_area(self) -> QtWidgets.QWidget:
        center_card = ECECard(border_color='#182244', bg_color=BG_PLOT)
        lay = QtWidgets.QVBoxLayout(center_card)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(2)

        self._sim_plot_widget = pg.GraphicsLayoutWidget()
        self._sim_plot_widget.setBackground(BG_PLOT)
        lay.addWidget(self._sim_plot_widget, stretch=1)

        self._init_plots()
        return center_card

    def _init_plots(self):
        """Initializes the 8 primary engineering oscilloscope and spectrum viewports."""
        self._sim_plots = {}
        self._sim_curves = {}
        self._sim_wf_imgs = {}

        def add_scope(title: str, color: str, row: int, col: int):
            p = self._sim_plot_widget.addPlot(row=row, col=col)
            p.setTitle(f"<span style='color:{color};font-family:Consolas;font-size:8pt;font-weight:bold;'>{title}</span>")
            p.showGrid(x=True, y=True, alpha=0.2)
            p.getAxis('left').setStyle(tickFont=QtGui.QFont('Consolas', 7))
            p.getAxis('bottom').setStyle(tickFont=QtGui.QFont('Consolas', 7))
            p.getAxis('left').setPen(pg.mkPen(color + '33', width=1))
            p.getAxis('bottom').setPen(pg.mkPen(color + '33', width=1))
            p.getViewBox().setBorder(pg.mkPen(color + '33', width=1))
            c = p.plot(pen=make_neon_pen(color, width=1.5))
            return p, c

        # Row 0: 1. Message & 2. Carrier
        p_msg, c_msg = add_scope("1. MESSAGE SIGNAL m(t)", COLOR_GREEN, 0, 0)
        p_car, c_car = add_scope("2. CARRIER SIGNAL c(t) = Ac·cos(2π·fc·t)", COLOR_CYAN, 0, 1)

        # Row 1: 3. Modulated Signals (AM and FM)
        p_am, c_am = add_scope("3. AM MODULATED RF s_AM(t)", COLOR_GOLD, 1, 0)
        p_fm, c_fm = add_scope("4. FM MODULATED RF s_FM(t)", COLOR_PINK, 1, 1)

        # Row 2: 5. RF Power Spectrum (dBm) & Waterfall
        p_ams = self._sim_plot_widget.addPlot(row=2, col=0)
        p_ams.setTitle(f"<span style='color:{COLOR_ORANGE};font-family:Consolas;font-size:8pt;font-weight:bold;'>5. AM RF SPECTRUM (dBm)</span>")
        p_ams.showGrid(x=True, y=True, alpha=0.2)
        c_ams = p_ams.plot(pen=make_neon_pen(COLOR_ORANGE, width=1.6))
        img_am = pg.ImageItem()
        img_am.setColorMap(pg.colormap.get('inferno'))
        p_ams.addItem(img_am)

        p_fms = self._sim_plot_widget.addPlot(row=2, col=1)
        p_fms.setTitle(f"<span style='color:{COLOR_PURPLE};font-family:Consolas;font-size:8pt;font-weight:bold;'>6. FM RF SPECTRUM (dBm)</span>")
        p_fms.showGrid(x=True, y=True, alpha=0.2)
        c_fms = p_fms.plot(pen=make_neon_pen(COLOR_PURPLE, width=1.6))
        img_fm = pg.ImageItem()
        img_fm.setColorMap(pg.colormap.get('viridis'))
        p_fms.addItem(img_fm)

        # Row 3: 7. AM Demodulated vs Original & 8. FM Demodulated vs Original
        p_dam, c_dam = add_scope("7. AM DEMODULATED (m̂_AM) vs ORIGINAL m(t)", COLOR_GREEN, 3, 0)
        c_dam_orig = p_dam.plot(pen=pg.mkPen('#ffffff', width=1.0, style=QtCore.Qt.PenStyle.DashLine))

        p_dfm, c_dfm = add_scope("8. FM DEMODULATED (m̂_FM) vs ORIGINAL m(t)", COLOR_PINK, 3, 1)
        c_dfm_orig = p_dfm.plot(pen=pg.mkPen('#ffffff', width=1.0, style=QtCore.Qt.PenStyle.DashLine))

        self._sim_plots = {
            'msg': p_msg, 'car': p_car, 'am': p_am, 'fm': p_fm,
            'ams': p_ams, 'fms': p_fms, 'dam': p_dam, 'dfm': p_dfm
        }
        self._sim_curves = {
            'msg': c_msg, 'car': c_car, 'am': c_am, 'fm': c_fm,
            'spec_am': c_ams, 'spec_fm': c_fms,
            'dam': c_dam, 'dam_orig': c_dam_orig,
            'dfm': c_dfm, 'dfm_orig': c_dfm_orig
        }
        self._sim_wf_imgs = {'am': img_am, 'fm': img_fm}

        # Set row stretch factors
        self._sim_plot_widget.ci.layout.setRowStretchFactor(0, 1)
        self._sim_plot_widget.ci.layout.setRowStretchFactor(1, 1)
        self._sim_plot_widget.ci.layout.setRowStretchFactor(2, 2)
        self._sim_plot_widget.ci.layout.setRowStretchFactor(3, 1)

    # ─────────────────────────────────────────────────────────
    #  BOTTOM: LIVE MEASUREMENT & STATUS AREA
    # ─────────────────────────────────────────────────────────
    def _build_bottom_measurement_area(self) -> QtWidgets.QWidget:
        card = ECECard(border_color='#161e3d', bg_color='#060814')
        layout = QtWidgets.QHBoxLayout(card)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(6)

        self._b_fm_freq = MetricBadge("Msg Freq (fm)", f"{self._fm:.0f}", "Hz", COLOR_GREEN)
        self._b_fc_freq = MetricBadge("Carrier (fc)", f"{self._fc:.0f}", "Hz", COLOR_CYAN)
        self._b_am_m = MetricBadge("AM Index (m)", f"{self._am_m:.2f}", "", COLOR_GOLD)
        self._b_am_eff = MetricBadge("AM Efficiency (η)", "---", "%", COLOR_GOLD)
        self._b_am_bw = MetricBadge("AM Bandwidth", "---", "Hz", COLOR_GOLD)
        self._b_fm_df = MetricBadge("FM Dev (Δf)", f"{self._fm_delta_f:.0f}", "Hz", COLOR_PINK)
        self._b_fm_beta = MetricBadge("FM Beta (β)", "---", "", COLOR_PINK)
        self._b_fm_bw = MetricBadge("Carson BW", "---", "Hz", COLOR_PINK)
        self._b_snr = MetricBadge("Channel SNR", "Off", "dB", COLOR_ORANGE)
        self._b_am_corr = MetricBadge("AM Error (ρ)", "---", "", COLOR_GREEN)
        self._b_fm_corr = MetricBadge("FM Error (ρ)", "---", "", COLOR_GREEN)
        self._b_overmod = MetricBadge("AM Status", "UNDERMOD", "", COLOR_CYAN)

        badges = [
            self._b_fm_freq, self._b_fc_freq, self._b_am_m, self._b_am_eff,
            self._b_am_bw, self._b_fm_df, self._b_fm_beta, self._b_fm_bw,
            self._b_snr, self._b_am_corr, self._b_fm_corr, self._b_overmod
        ]
        for b in badges:
            layout.addWidget(b)

        return card

    # ─────────────────────────────────────────────────────────
    #  TAB 1: EXPERIMENT LABORATORY VIEW
    # ─────────────────────────────────────────────────────────
    def _build_experiment_view(self) -> QtWidgets.QWidget:
        view = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(view)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(10)

        left_card = ECECard(border_color='#202c5c')
        left_layout = QtWidgets.QVBoxLayout(left_card)
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_layout.setSpacing(8)

        left_layout.addWidget(QtWidgets.QLabel("<b style='color:#00e5ff; font-size:11px;'>10 ECE PREDEFINED EXPERIMENTS</b>"))

        self._exp_list_widget = QtWidgets.QListWidget()
        self._exp_list_widget.setStyleSheet("""
            QListWidget {
                background: #080c1e; color: #d0d8f0; border: 1px solid #1a2244;
                border-radius: 4px; font-family: Consolas; font-size: 10px;
            }
            QListWidget::item { padding: 6px; border-bottom: 1px solid #101630; }
            QListWidget::item:selected { background: #00e5ff22; color: #00e5ff; font-weight: bold; }
        """)
        for exp in EXPERIMENT_LIST:
            self._exp_list_widget.addItem(f"{exp['title']}")
        self._exp_list_widget.setCurrentRow(0)
        self._exp_list_widget.currentRowChanged.connect(self._on_exp_selected)
        left_layout.addWidget(self._exp_list_widget, stretch=1)

        self._exp_desc_lbl = QtWidgets.QLabel()
        self._exp_desc_lbl.setWordWrap(True)
        self._exp_desc_lbl.setStyleSheet("color:#a0b0d0; font-size:10px; background:#0a0f26; padding:8px; border-radius:4px;")
        left_layout.addWidget(self._exp_desc_lbl)

        self._btn_run_exp = QtWidgets.QPushButton("▶ EXECUTE EXPERIMENT")
        self._btn_run_exp.setStyleSheet("""
            QPushButton {
                background: #00e5ff; color: #000000; font-weight: bold; font-family: Consolas;
                padding: 8px; border-radius: 4px; font-size: 11px;
            }
            QPushButton:hover { background: #50f0ff; }
        """)
        self._btn_run_exp.clicked.connect(self._run_current_experiment)
        left_layout.addWidget(self._btn_run_exp)

        layout.addWidget(left_card, stretch=1)

        right_card = ECECard(border_color='#202c5c')
        right_layout = QtWidgets.QVBoxLayout(right_card)
        right_layout.setContentsMargins(10, 10, 10, 10)
        right_layout.setSpacing(8)

        right_layout.addWidget(QtWidgets.QLabel("<b style='color:#00ff88; font-size:11px;'>MEASUREMENT RESULTS & ENGINEERING CONCLUSION</b>"))

        self._exp_table = QtWidgets.QTableWidget()
        self._exp_table.setStyleSheet("""
            QTableWidget {
                background: #080c1e; color: #d0d8f0; border: 1px solid #1a2244;
                gridline-color: #1a2244; font-family: Consolas; font-size: 10px;
            }
            QHeaderView::section { background: #101630; color: #00e5ff; font-weight: bold; padding: 4px; }
        """)
        right_layout.addWidget(self._exp_table, stretch=1)

        self._exp_conclusion_box = QtWidgets.QTextEdit()
        self._exp_conclusion_box.setReadOnly(True)
        self._exp_conclusion_box.setStyleSheet("""
            QTextEdit {
                background: #050711; color: #ffd700; border: 1px solid #ffd70044;
                border-radius: 4px; font-family: Consolas; font-size: 10px; padding: 6px;
            }
        """)
        self._exp_conclusion_box.setFixedHeight(90)
        right_layout.addWidget(self._exp_conclusion_box)

        layout.addWidget(right_card, stretch=2)

        self._on_exp_selected(0)
        return view

    def _on_exp_selected(self, row: int):
        if 0 <= row < len(EXPERIMENT_LIST):
            exp = EXPERIMENT_LIST[row]
            self._exp_desc_lbl.setText(f"<b>Objective:</b><br>{exp['desc']}")

    def _run_current_experiment(self):
        row = self._exp_list_widget.currentRow()
        exp_id = row + 1
        self._btn_run_exp.setEnabled(False)
        self._exp_worker = _ExperimentWorker(self._exp_runner, exp_id)
        self._exp_worker.finished.connect(self._on_exp_finished)
        self._exp_worker.start()

    def _on_exp_finished(self, res):
        self._btn_run_exp.setEnabled(True)
        exp_id = self._exp_list_widget.currentRow() + 1
        if 'data' in res and len(res['data']) > 0:
            data = res['data']
            headers = list(data[0].keys())
            self._exp_table.setColumnCount(len(headers))
            self._exp_table.setRowCount(len(data))
            self._exp_table.setHorizontalHeaderLabels([h.replace('_', ' ').upper() for h in headers])

            for r_idx, row_dict in enumerate(data):
                for c_idx, key in enumerate(headers):
                    val = row_dict[key]
                    if isinstance(val, float):
                        txt = f"{val:.3f}" if abs(val) < 10 else f"{val:.1f}"
                    else:
                        txt = str(val)
                    item = QtWidgets.QTableWidgetItem(txt)
                    item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                    self._exp_table.setItem(r_idx, c_idx, item)
            self._exp_table.resizeColumnsToContents()
        elif exp_id == 10:
            self._exp_table.setColumnCount(4)
            self._exp_table.setRowCount(6)
            self._exp_table.setHorizontalHeaderLabels(["PARAMETER", "THEORETICAL", "MEASURED", "ERROR %"])
            
            am = res['am_metrics']
            fm = res['fm_metrics']
            rows = [
                ("AM Bandwidth (Hz)", f"{am['bw_theory_hz']:.1f}", f"{am['bw_measured_hz']:.1f}", f"{am['bw_error_pct']:.1f}%"),
                ("AM Efficiency (%)", f"{am['efficiency_pct']:.1f}%", f"{am['efficiency_pct']:.1f}%", "0.0%"),
                ("AM Mod Index", f"{am['m_theory']:.2f}", f"{am['m_measured']:.2f}", "0.0%"),
                ("FM Carson BW (Hz)", f"{fm['carson_bw_theory_hz']:.1f}", f"{fm['bw_measured_hz']:.1f}", f"{fm['bw_error_pct']:.1f}%"),
                ("FM Deviation Δf (Hz)", f"{fm['delta_f_theory_hz']:.1f}", f"{fm['delta_f_measured_hz']:.1f}", "0.0%"),
                ("FM Mod Index β", f"{fm['beta_theory']:.2f}", f"{fm['beta_measured']:.2f}", "0.0%"),
            ]
            for r_idx, r_data in enumerate(rows):
                for c_idx, val in enumerate(r_data):
                    item = QtWidgets.QTableWidgetItem(val)
                    item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                    self._exp_table.setItem(r_idx, c_idx, item)
            self._exp_table.resizeColumnsToContents()

        self._exp_conclusion_box.setText(res.get('conclusion', 'Experiment Completed.'))

    # ─────────────────────────────────────────────────────────
    #  TAB 2: AM vs FM PERFORMANCE COMPARISON
    # ─────────────────────────────────────────────────────────
    def _build_comparison_view(self) -> QtWidgets.QWidget:
        view = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(view)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        table_card = ECECard(border_color='#253366')
        t_layout = QtWidgets.QVBoxLayout(table_card)
        t_layout.setContentsMargins(10, 10, 10, 10)

        lbl = QtWidgets.QLabel("<b style='color:#00e5ff; font-size:11px;'>THEORETICAL & ARCHITECTURAL COMPARISON: AM vs FM</b>")
        t_layout.addWidget(lbl)

        comp_table = QtWidgets.QTableWidget(8, 4)
        comp_table.setHorizontalHeaderLabels(["PARAMETER", "AM (DSB-FC)", "FM (WIDEBAND)", "ENGINEERING TRADE-OFF"])
        comp_table.setStyleSheet("background:#080c1e; color:#d0d8f0; gridline-color:#1a2244; font-family:Consolas; font-size:10px;")

        tradeoffs = [
            ("Information Encoding", "Carrier Amplitude Envelope A(t)", "Carrier Instantaneous Frequency f(t)", "AM is linear; FM is non-linear"),
            ("Modulation Index", "m = Am / Ac (m ≤ 1.0)", "β = Δf / fm", "Overmodulation in AM clips; in FM it only widens BW"),
            ("Bandwidth Requirement", "BW = 2 * fm (Narrow)", "BW ≈ 2(Δf + fm) (Wide)", "FM trades bandwidth for superior noise immunity"),
            ("Transmission Efficiency", "η ≤ 33.3% for single tone", "100% of power in information", "AM wastes 66.7%+ power on unmodulated carrier"),
            ("Noise Susceptibility", "Linear degradation (High)", "Low (FM Capture Effect)", "FM suppresses amplitude noise via limiters"),
            ("Transmitter Complexity", "Simpler, lower cost", "Requires linear VCO / NCO", "FM circuits require higher frequency stability"),
            ("Receiver Complexity", "Simple Diode Envelope Detector", "PLL / Frequency Discriminator", "AM envelope detector is extremely inexpensive"),
            ("Standard Application", "Long-range broadcast, Aviation", "High-Fidelity Audio, Broadcast", "AM for distance/narrowband; FM for fidelity"),
        ]
        for r, row in enumerate(tradeoffs):
            for c, val in enumerate(row):
                item = QtWidgets.QTableWidgetItem(val)
                comp_table.setItem(r, c, item)
        comp_table.resizeColumnsToContents()
        t_layout.addWidget(comp_table)

        layout.addWidget(table_card, stretch=1)

        plot_card = ECECard(border_color='#253366')
        p_layout = QtWidgets.QVBoxLayout(plot_card)
        p_layout.setContentsMargins(10, 10, 10, 10)

        btn_sweep = QtWidgets.QPushButton("▶ EXECUTE LIVE SNR SWEEP BENCHMARK (5 dB → 40 dB)")
        btn_sweep.setStyleSheet("background:#00ff88; color:#000000; font-weight:bold; font-family:Consolas; padding:6px; border-radius:4px;")
        p_layout.addWidget(btn_sweep)

        self._comp_plot = pg.PlotWidget()
        self._comp_plot.setBackground(BG_PLOT)
        self._comp_plot.setTitle("<span style='color:#00ff88; font-family:Consolas;'>OUTPUT SNR vs CHANNEL INPUT SNR (AM vs FM)</span>")
        self._comp_plot.setLabel('left', 'Output SNR (dB)', color='#8899aa')
        self._comp_plot.setLabel('bottom', 'Channel Input SNR (dB)', color='#8899aa')
        self._comp_plot.showGrid(x=True, y=True, alpha=0.3)
        self._comp_plot.addLegend()
        
        self._curve_snr_am = self._comp_plot.plot(pen=pg.mkPen(COLOR_GOLD, width=2.0), name="AM (m=0.8)")
        self._curve_snr_fm = self._comp_plot.plot(pen=pg.mkPen(COLOR_PINK, width=2.0), name="FM (β=4.0)")

        btn_sweep.clicked.connect(self._run_snr_sweep)
        p_layout.addWidget(self._comp_plot, stretch=1)

        layout.addWidget(plot_card, stretch=1)
        return view

    def _run_snr_sweep(self):
        """Runs live Monte-Carlo SNR sweep comparing AM and FM."""
        self._sweep_worker = _SweepWorker()
        self._sweep_worker.finished.connect(self._on_sweep_finished)
        self._sweep_worker.start()

    def _on_sweep_finished(self, snr_in, am_out_snr, fm_out_snr):
        self._curve_snr_am.setData(snr_in, am_out_snr)
        self._curve_snr_fm.setData(snr_in, fm_out_snr)

    # ─────────────────────────────────────────────────────────
    #  TAB 3: ADVANCED 3D & TIME-FREQUENCY ANALYSIS
    # ─────────────────────────────────────────────────────────
    def _build_advanced_view(self) -> QtWidgets.QWidget:
        # Dummy image items to avoid breaking _on_tick() when this tab is selected
        self._adv_img_am = pg.ImageItem()
        self._adv_img_fm = pg.ImageItem()

        view = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(view)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        card = ECECard(border_color='#1a2448')
        c_layout = QtWidgets.QHBoxLayout(card)
        c_layout.addWidget(QtWidgets.QLabel("<b style='color:#00e5ff;'>ADVANCED TIME-FREQUENCY & PARAMETER SWEEP ANALYSIS</b>"))
        
        self._sig_combo = QtWidgets.QComboBox()
        self._sig_combo.addItems(["AM Signal", "FM Signal"])
        self._sig_combo.setStyleSheet("background:#080d20; color:#00e5ff; border:1px solid #00e5ff55; padding:4px 8px; font-family:Consolas; font-weight:bold; border-radius:4px;")
        c_layout.addWidget(self._sig_combo)

        btn_spec = QtWidgets.QPushButton("📊 GENERATE SPECTROGRAM")
        btn_spec.setStyleSheet("background:#ff7700; color:#000000; font-family:Consolas; font-weight:bold; padding:5px 10px; border-radius:4px;")
        btn_spec.clicked.connect(self._generate_spectrogram)
        c_layout.addWidget(btn_spec)

        btn_3d_sweep = QtWidgets.QPushButton("⚡ GENERATE 3D AM PARAMETER SURFACE")
        btn_3d_sweep.setStyleSheet("background:#bf00ff; color:#ffffff; font-family:Consolas; font-weight:bold; padding:5px 10px; border-radius:4px;")
        btn_3d_sweep.clicked.connect(self._plot_3d_am_surface)
        c_layout.addWidget(btn_3d_sweep)
        layout.addWidget(card)

        # Matplotlib figure area
        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        
        # Spectrogram Figure
        self._fig_spec = Figure(facecolor='#070913')
        self._canvas_spec = FigureCanvasQTAgg(self._fig_spec)
        splitter.addWidget(self._canvas_spec)
        
        # 3D Surface Figure
        self._fig_3d = Figure(facecolor='#070913')
        self._canvas_3d = FigureCanvasQTAgg(self._fig_3d)
        splitter.addWidget(self._canvas_3d)

        layout.addWidget(splitter, stretch=1)
        return view

    def _generate_spectrogram(self):
        if not hasattr(self, '_src') or not self._src:
            return
            
        msg = self._src.read_last(8192).astype(np.float32)
        if len(msg) < 8192:
            return
            
        # Get appropriate signal based on selection
        is_am = (self._sig_combo.currentIndex() == 0)
        
        if is_am:
            sig, _, _, _ = self._am_mod.process(msg)
            title = 'AM Signal Spectrogram'
            cmap = 'inferno'
            color = '#ffd700'
        else:
            sig, _, _, _ = self._fm_mod.process(msg, self._fm)
            title = 'FM Signal Spectrogram'
            cmap = 'cividis'
            color = '#ff2d78'
            
        self._fig_spec.clear()
        ax = self._fig_spec.add_subplot(111)
        ax.set_facecolor('#0d1124')
        
        # Compute STFT
        f, t, Sxx = scipy.signal.spectrogram(sig, fs=SR, nperseg=256, noverlap=192)
        
        # Plot
        pm = ax.pcolormesh(t, f, 10 * np.log10(Sxx + 1e-12), cmap=cmap, shading='gouraud')
        
        ax.set_title(title, color=color, pad=10)
        ax.set_xlabel('Time (s)', color='#d0d8f0')
        ax.set_ylabel('Frequency (Hz)', color='#d0d8f0')
        ax.tick_params(colors='#6c7a9c')
        
        cb = self._fig_spec.colorbar(pm, ax=ax)
        cb.set_label('Power (dB)', color='#d0d8f0')
        cb.ax.yaxis.set_tick_params(color='#6c7a9c')
        cb.ax.yaxis.set_ticklabels(cb.ax.yaxis.get_ticklabels(), color='#6c7a9c')
        
        self._canvas_spec.draw()

    def _plot_3d_am_surface(self):
        # Run sweep in thread to avoid freezing
        self._btn_3d_sweep = self.sender()
        if self._btn_3d_sweep:
            self._btn_3d_sweep.setEnabled(False)
            self._btn_3d_sweep.setText("⏳ SWEEPING...")
            
        self._sweep_3d_worker = _Sweep3DWorker()
        self._sweep_3d_worker.finished.connect(self._on_3d_sweep_finished)
        self._sweep_3d_worker.start()

    def _on_3d_sweep_finished(self, M, S, Z):
        self._fig_3d.clear()
        ax = self._fig_3d.add_subplot(111, projection='3d')
        ax.set_facecolor('#070913')
        
        surf = ax.plot_surface(M, S, Z, cmap='viridis', linewidth=0, antialiased=True)
        
        ax.set_title('AM Reconstruction vs Mod Index & SNR', color='#00e5ff', pad=10)
        ax.set_xlabel('Modulation Index m', color='#d0d8f0')
        ax.set_ylabel('SNR (dB)', color='#d0d8f0')
        ax.set_zlabel('Correlation ρ', color='#d0d8f0')
        
        ax.xaxis.set_tick_params(colors='#6c7a9c')
        ax.yaxis.set_tick_params(colors='#6c7a9c')
        ax.zaxis.set_tick_params(colors='#6c7a9c')
        
        # Transparent panes
        ax.xaxis.pane.fill = False
        ax.yaxis.pane.fill = False
        ax.zaxis.pane.fill = False
        ax.xaxis.pane.set_edgecolor('#1a2448')
        ax.yaxis.pane.set_edgecolor('#1a2448')
        ax.zaxis.pane.set_edgecolor('#1a2448')
        
        self._canvas_3d.draw()
        
        if hasattr(self, '_btn_3d_sweep') and self._btn_3d_sweep:
            self._btn_3d_sweep.setEnabled(True)
            self._btn_3d_sweep.setText("⚡ GENERATE 3D AM PARAMETER SURFACE")

    # ─────────────────────────────────────────────────────────
    #  TAB 4: VIVA / DEMO WALKTHROUGH MODE
    # ─────────────────────────────────────────────────────────
    def _build_demo_view(self) -> QtWidgets.QWidget:
        view = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(view)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        card = ECECard(border_color='#00e5ff44')
        c_layout = QtWidgets.QVBoxLayout(card)
        c_layout.setContentsMargins(16, 16, 16, 16)
        c_layout.setSpacing(10)

        c_layout.addWidget(QtWidgets.QLabel("<b style='color:#00e5ff; font-size:13px;'>🎯 AUTOMATED 2-MINUTE VIVA DEMONSTRATION WALKTHROUGH</b>"))
        c_layout.addWidget(QtWidgets.QLabel(
            "This guided sequence steps through the communication chain systematically to demonstrate "
            "all core learning objectives to an examiner or interviewer."
        ))

        demo_steps = [
            "1. Baseband Message Synthesis (Sine, Square, Audio Ingest)",
            "2. Carrier Generation via Phase-Continuous NCO",
            "3. AM Double-Sideband Full-Carrier (DSB-FC) Modulation & Envelope",
            "4. AM Power Distribution & 33.3% Theoretical Efficiency Limit",
            "5. AM Overmodulation Phenomenon (m > 1.0) & Rectifier Distortion",
            "6. Wideband FM Generation & Peak Frequency Deviation (Δf)",
            "7. FM Carson Bandwidth Rule BW ≈ 2(Δf + fm) Validation",
            "8. AWGN Channel Impairment & Real-Time SNR Calibration",
            "9. Demodulation Fidelity (Hilbert Envelope vs. Phase Discriminator)",
            "10. Quantitative Reconstruction Error (MSE, RMSE, Pearson Correlation ρ)"
        ]
        for s in demo_steps:
            lbl = QtWidgets.QLabel(f"<span style='color:#00ff88; font-family:Consolas;'>{s}</span>")
            c_layout.addWidget(lbl)

        btn_auto_step = QtWidgets.QPushButton("▶ LAUNCH AUTO DEMO IN SIMULATOR")
        btn_auto_step.setStyleSheet("background:#00e5ff; color:#000000; font-weight:bold; font-family:Consolas; padding:8px; border-radius:4px; font-size:11px;")
        btn_auto_step.clicked.connect(self._launch_auto_demo)
        c_layout.addWidget(btn_auto_step)

        layout.addWidget(card)
        layout.addStretch()
        return view

    def _launch_auto_demo(self):
        self._tab_stack.setCurrentIndex(0)
        self._sl_am_m.set_value(0.5)
        self._noise_chk.setChecked(False)

    # ─────────────────────────────────────────────────────────
    #  TAB 5: THEORY & HELP GUIDE
    # ─────────────────────────────────────────────────────────
    def _build_theory_view(self) -> QtWidgets.QWidget:
        view = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(view)
        layout.setContentsMargins(12, 12, 12, 12)

        card = ECECard(border_color='#1a2448')
        c_layout = QtWidgets.QVBoxLayout(card)
        c_layout.setContentsMargins(16, 16, 16, 16)

        txt = QtWidgets.QTextBrowser()
        txt.setStyleSheet("background:#050711; color:#d0d8f0; border:none; font-family:Consolas; font-size:11px;")
        txt.setHtml("""
        <h2 style='color:#00e5ff;'>ECE Communication Systems Theoretical Foundations</h2>
        
        <h3 style='color:#ffd700;'>1. Amplitude Modulation (Conventional AM / DSB-FC)</h3>
        <p>Mathematical Formula:</p>
        <pre style='color:#00ff88;'>s_AM(t) = Ac · [1 + m · x(t)] · cos(2π·fc·t)</pre>
        <ul>
          <li><b>Modulation Index:</b> m = Am / Ac</li>
          <li><b>Bandwidth:</b> BW_AM = 2 · fm</li>
          <li><b>Total Power:</b> P_T = P_c · (1 + m²/2) = (Ac²/2) · (1 + m²/2)</li>
          <li><b>Transmission Efficiency:</b> η = (P_sideband / P_total) = m² / (2 + m²) × 100%</li>
          <li><b>Overmodulation (m > 1.0):</b> The envelope crosses zero, causing 180° phase reversals. Diode envelope detectors cannot track negative excursions, resulting in severe harmonic distortion.</li>
        </ul>

        <h3 style='color:#ff2d78;'>2. Frequency Modulation (FM)</h3>
        <p>Mathematical Formula:</p>
        <pre style='color:#ff2d78;'>s_FM(t) = Ac · cos( 2π·fc·t + 2π·kf · ∫ x(τ) dtau )</pre>
        <ul>
          <li><b>Peak Frequency Deviation:</b> Δf = kf · max|x(t)|</li>
          <li><b>Modulation Index:</b> β = Δf / fm</li>
          <li><b>Carson's Rule Bandwidth:</b> BW_FM ≈ 2 · (Δf + fm) = 2 · fm · (1 + β)</li>
          <li><b>Narrowband FM (β &lt; 1):</b> Single sideband pair dominant (BW ≈ 2·fm).</li>
          <li><b>Wideband FM (β ≥ 1):</b> Multiple Bessel harmonic sideband pairs at fc ± n·fm.</li>
        </ul>

        <h3 style='color:#00ff88;'>3. Reconstruction Error & SNR Metrics</h3>
        <ul>
          <li><b>Mean Squared Error (MSE):</b> (1/N) · ∑ |x[n] - x̂[n]|²</li>
          <li><b>Pearson Correlation (ρ):</b> Cov(x, x̂) / (σ_x · σ_x̂)</li>
          <li><b>Channel AWGN Calibration:</b> P_noise = P_sig / 10^(SNR_dB / 10)</li>
        </ul>
        """)
        c_layout.addWidget(txt)
        layout.addWidget(card)
        return view

    # ─────────────────────────────────────────────────────────
    #  EVENT HANDLERS & PARAMETER DISPATCH
    # ─────────────────────────────────────────────────────────
    def _on_sim_run(self):
        self._is_paused = False
        if not self._timer.isActive():
            self._timer.start(int(1000.0 / 30.0))

    def _on_sim_pause(self):
        self._is_paused = True

    def _on_sim_reset(self):
        self._sl_fm.set_value(FM_DEFAULT)
        self._sl_am.set_value(1.0)
        self._sl_phase_m.set_value(0.0)
        self._sl_fc.set_value(FC_DEFAULT)
        self._sl_ac.set_value(1.0)
        self._sl_phase_c.set_value(0.0)
        self._sl_am_m.set_value(0.8)
        self._sl_fm_df.set_value(4000.0)
        self._sl_snr.set_value(25.0)
        self._sl_atten.set_value(0.0)
        self._noise_chk.setChecked(False)
        self._interf_chk.setChecked(False)
        self._chk_am.setChecked(True)
        self._chk_fm.setChecked(True)
        self._msg_type_combo.setCurrentIndex(0)
        self._am_mode_combo.setCurrentIndex(0)
        self._display_combo.setCurrentIndex(0)

    def _set_am_enabled(self, enabled: bool):
        self._am_enabled = enabled
        self._sim_plots['am'].setVisible(enabled)
        self._sim_plots['ams'].setVisible(enabled)
        self._sim_plots['dam'].setVisible(enabled)

    def _set_fm_enabled(self, enabled: bool):
        self._fm_enabled = enabled
        self._sim_plots['fm'].setVisible(enabled)
        self._sim_plots['fms'].setVisible(enabled)
        self._sim_plots['dfm'].setVisible(enabled)

    def _on_display_filter_changed(self, idx: int):
        # 0: All Plots, 1: Time Only, 2: Freq Only, 3: AM Only, 4: FM Only
        if idx == 0:
            for p in self._sim_plots.values():
                p.setVisible(True)
        elif idx == 1:
            for k, p in self._sim_plots.items():
                p.setVisible(k not in ('ams', 'fms'))
        elif idx == 2:
            for k, p in self._sim_plots.items():
                p.setVisible(k in ('ams', 'fms', 'msg'))
        elif idx == 3:
            for k, p in self._sim_plots.items():
                p.setVisible(k in ('msg', 'car', 'am', 'ams', 'dam'))
        elif idx == 4:
            for k, p in self._sim_plots.items():
                p.setVisible(k in ('msg', 'car', 'fm', 'fms', 'dfm'))

    def _on_msg_type_changed(self, idx: int):
        types = ['sine', 'square', 'triangle', 'sawtooth', 'chirp', 'tone', 'mic', 'wav']
        self._msg_type = types[min(idx, len(types)-1)]
        
        self._src.stop()
        if self._msg_type in ('sine', 'square', 'triangle', 'sawtooth', 'chirp'):
            self._src = WaveformSource(self._msg_type, self._fm, self._am, np.radians(self._phase_m), sr=SR)
        elif self._msg_type == 'tone':
            self._src = ToneSource(tones=[(self._fm, 0.6), (self._fm*2, 0.3), (self._fm*3, 0.1)], sr=SR)
        elif self._msg_type == 'mic':
            self._src = MicSource(sr=SR)
        elif self._msg_type == 'wav':
            path, _ = QtWidgets.QFileDialog.getOpenFileName(
                self, 'Select Audio File', '', 'Audio Files (*.wav *.mp3 *.flac);;All Files (*)'
            )
            if path:
                self._src = WavSource(path, sr=SR)
            else:
                self._src = WaveformSource('sine', self._fm, self._am, sr=SR)
        self._src.start()

    def _on_fm_changed(self, val: float):
        self._fm = val
        if hasattr(self._src, 'set_params'):
            self._src.set_params(fm=self._fm)

    def _on_am_amp_changed(self, val: float):
        self._am = val
        if hasattr(self._src, 'set_params'):
            self._src.set_params(am=self._am)

    def _on_phase_m_changed(self, val: float):
        self._phase_m = val
        if hasattr(self._src, 'set_params'):
            self._src.set_params(phase_rad=np.radians(self._phase_m))

    def _on_fc_changed(self, val: float):
        self._fc = val
        self._am_mod.set_params(fc=self._fc)
        self._fm_mod.set_params(fc=self._fc)
        self._carrier_nco.set_frequency(self._fc)

    def _on_ac_amp_changed(self, val: float):
        self._ac = val
        self._am_mod.set_params(ac=self._ac)
        self._fm_mod.set_params(ac=self._ac)

    def _on_phase_c_changed(self, val: float):
        self._phase_c = val
        self._carrier_nco.set_phase(np.radians(self._phase_c))

    def _on_am_mode_changed(self, idx: int):
        modes = ['DSB-FC', 'DSB-SC', 'SSB-USB', 'SSB-LSB']
        self._am_mode = modes[min(idx, len(modes)-1)]
        self._am_mod.set_params(mode=self._am_mode)

    def _on_am_m_changed(self, val: float):
        self._am_m = val
        self._am_mod.set_params(m=self._am_m)

    def _on_fm_df_changed(self, val: float):
        self._fm_delta_f = val
        self._fm_mod.set_params(delta_f=self._fm_delta_f)

    def _on_preset_selected(self, idx: int):
        if idx == 1:   # 50%
            self._sl_am_m.set_value(0.5)
            self._noise_chk.setChecked(False)
        elif idx == 2: # 100%
            self._sl_am_m.set_value(1.0)
            self._noise_chk.setChecked(False)
        elif idx == 3: # Overmod
            self._sl_am_m.set_value(1.6)
            self._noise_chk.setChecked(False)
        elif idx == 4: # NBFM
            self._sl_fm_df.set_value(500.0)
            self._sl_fm.set_value(1000.0)
        elif idx == 5: # WBFM
            self._sl_fm_df.set_value(5000.0)
            self._sl_fm.set_value(1000.0)
        elif idx == 6: # Noisy
            self._noise_chk.setChecked(True)
            self._sl_snr.set_value(10.0)
        elif idx == 7: # Reset
            self._on_sim_reset()

    # ─────────────────────────────────────────────────────────
    #  MAIN REAL-TIME TELEMETRY & PLOT REFRESH LOOP
    # ─────────────────────────────────────────────────────────
    def _on_tick(self):
        if self._is_paused or not self._src or not self._src.active:
            return

        # 1. Pull latest message chunk from ring buffer
        msg = self._src.read_last(DISP_N).astype(np.float32)
        if len(msg) < DISP_N:
            return

        self._frame_count = getattr(self, '_frame_count', 0) + 1

        # 2. Continuous carrier generation
        car_cos, _ = self._carrier_nco.generate(DISP_N)

        # Plot decimation step
        step = max(1, len(msg) // 800)
        t = self._time_axis_ms

        am_chan = None
        fm_chan = None

        # 3-5 & 7. AM Pipeline
        if self._am_enabled:
            am_out, _, _, _ = self._am_mod.process(msg)
            am_chan, ch_meta_am = self._channel.process(am_out)
            am_rec = self._am_demod.process(am_chan, car_cos)
            
            # Reconstruction metrics (debounced to 10 FPS)
            if self._frame_count % 3 == 0:
                self._cached_recon_am = compute_reconstruction_metrics(msg, am_rec)
            err_am = getattr(self, '_cached_recon_am', {'correlation': 0.0})
            
            # AM Spec meta
            am_obw = getattr(self, '_cached_spec_meta_am', {}).get('obw_99_hz', 0.0)
            m_am = SystemMetrics.analyze_am(am_out, msg, self._fc, self._fm, self._am_m, self._ac, am_obw)

            # AM Badges
            self._b_am_m.set_value(f"{m_am['m_theory']:.2f}")
            self._b_am_eff.set_value(f"{m_am['efficiency_pct']:.1f}%")
            self._b_am_bw.set_value(f"{m_am['bw_theory_hz']:.0f}")
            self._b_am_corr.set_value(f"{err_am['correlation']:.3f}", COLOR_GOLD if err_am.get('correlation', 0) > 0.9 else COLOR_RED)
            self._b_overmod.set_value("OVERMOD" if m_am['is_overmodulated'] else "NORMAL", COLOR_RED if m_am['is_overmodulated'] else COLOR_CYAN)

            # AM Curves
            self._sim_curves['am'].setData(t[::step], am_chan[::step] if self._channel.noise_enabled else am_out[::step])
            self._sim_curves['dam'].setData(t[::step], am_rec[::step])
            self._sim_curves['dam_orig'].setData(t[::step], msg[::step])
        else:
            self._b_am_m.set_value("---")
            self._b_am_eff.set_value("---")
            self._b_am_bw.set_value("---")
            self._b_am_corr.set_value("---")
            self._b_overmod.set_value("---", COLOR_MUTED)
            self._sim_curves['am'].setData([], [])
            self._sim_curves['dam'].setData([], [])
            self._sim_curves['dam_orig'].setData([], [])

        # 3-5 & 7. FM Pipeline
        if self._fm_enabled:
            fm_out, _, inst_freq, fm_meta = self._fm_mod.process(msg, self._fm)
            fm_chan, ch_meta_fm = self._channel.process(fm_out)
            fm_rec = self._fm_demod.process(fm_chan)

            # Reconstruction metrics (debounced to 10 FPS)
            if self._frame_count % 3 == 0:
                self._cached_recon_fm = compute_reconstruction_metrics(msg, fm_rec)
            err_fm = getattr(self, '_cached_recon_fm', {'correlation': 0.0})

            # FM Spec meta
            fm_obw = getattr(self, '_cached_spec_meta_fm', {}).get('obw_99_hz', 0.0)
            m_fm = SystemMetrics.analyze_fm(fm_out, inst_freq, self._fc, self._fm, self._fm_delta_f, self._ac, fm_obw)

            # FM Badges
            self._b_fm_freq.set_value(f"{self._fm:.0f}")
            self._b_fc_freq.set_value(f"{self._fc:.0f}")
            self._b_fm_df.set_value(f"{self._fm_delta_f:.0f}")
            self._b_fm_beta.set_value(f"{m_fm['beta_theory']:.2f}")
            self._b_fm_bw.set_value(f"{m_fm['carson_bw_theory_hz']:.0f}")
            self._b_fm_corr.set_value(f"{err_fm['correlation']:.3f}", COLOR_PINK if err_fm.get('correlation', 0) > 0.9 else COLOR_RED)

            # FM Curves
            self._sim_curves['fm'].setData(t[::step], fm_chan[::step] if self._channel.noise_enabled else fm_out[::step])
            self._sim_curves['dfm'].setData(t[::step], fm_rec[::step])
            self._sim_curves['dfm_orig'].setData(t[::step], msg[::step])
        else:
            self._b_fm_freq.set_value("---")
            self._b_fc_freq.set_value("---")
            self._b_fm_df.set_value("---")
            self._b_fm_beta.set_value("---")
            self._b_fm_bw.set_value("---")
            self._b_fm_corr.set_value("---")
            self._sim_curves['fm'].setData([], [])
            self._sim_curves['dfm'].setData([], [])
            self._sim_curves['dfm_orig'].setData([], [])

        # Shared/Global Badges & Curves
        self._b_snr.set_value(f"{self._channel.snr_db:.0f}" if self._channel.noise_enabled else "Off")
        self._sim_curves['msg'].setData(t[::step], msg[::step])
        self._sim_curves['car'].setData(t[::step], car_cos[::step])

        # 6. Spectral Analysis (debounced to 15 FPS)
        if self._frame_count % 2 == 0:
            if self._am_enabled and am_chan is not None:
                self._cached_fa, self._cached_psd_am, self._cached_wf_am, _, self._cached_spec_meta_am = self._spec_am.process(am_chan)
            if self._fm_enabled and fm_chan is not None:
                self._cached_ff, self._cached_psd_fm, self._cached_wf_fm, _, self._cached_spec_meta_fm = self._spec_fm.process(fm_chan)

        # 10. Update Spectra & Waterfalls
        if self._am_enabled and hasattr(self, '_cached_fa'):
            f_max = min(self._fc * 2.5, SR / 2.0)
            mask_am = self._cached_fa <= f_max
            self._sim_curves['spec_am'].setData(self._cached_fa[mask_am], self._cached_psd_am[mask_am])
            wf_am_c = np.clip(self._cached_wf_am[:, mask_am], -80, 0)
            self._sim_wf_imgs['am'].setImage(((wf_am_c + 80) / 80).T, autoLevels=False, levels=(0, 1))
            
            if self._tab_stack.currentIndex() == 3:
                self._adv_img_am.setImage(((wf_am_c + 80) / 80).T, autoLevels=False, levels=(0, 1))
        elif not self._am_enabled:
            self._sim_curves['spec_am'].setData([], [])
            self._sim_wf_imgs['am'].clear()
            if self._tab_stack.currentIndex() == 3:
                self._adv_img_am.clear()

        if self._fm_enabled and hasattr(self, '_cached_ff'):
            f_max = min(self._fc * 2.5, SR / 2.0)
            mask_fm = self._cached_ff <= f_max
            self._sim_curves['spec_fm'].setData(self._cached_ff[mask_fm], self._cached_psd_fm[mask_fm])
            wf_fm_c = np.clip(self._cached_wf_fm[:, mask_fm], -80, 0)
            self._sim_wf_imgs['fm'].setImage(((wf_fm_c + 80) / 80).T, autoLevels=False, levels=(0, 1))
            
            if self._tab_stack.currentIndex() == 3:
                self._adv_img_fm.setImage(((wf_fm_c + 80) / 80).T, autoLevels=False, levels=(0, 1))
        elif not self._fm_enabled:
            self._sim_curves['spec_fm'].setData([], [])
            self._sim_wf_imgs['fm'].clear()
            if self._tab_stack.currentIndex() == 3:
                self._adv_img_fm.clear()

    def closeEvent(self, event):
        self._timer.stop()
        if self._src:
            self._src.stop()
        super().closeEvent(event)
