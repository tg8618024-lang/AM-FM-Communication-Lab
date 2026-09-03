import os
import base64

target_dir = r'C:\Users\tg861\.gemini\antigravity\brain\39b9bd19-c2cb-4b7e-8761-210c01c403b0\am_fm_pro'
os.chdir(target_dir)

engine_code = '''from dataclasses import dataclass, field
import numpy as np

from modulator import AMModulator, FMModulator
from channel import Channel
from demodulator import AMDemodulator, FMDemodulator, compute_reconstruction_metrics
from spectrum import SpectrumAnalyzer
from measurements import SystemMetrics
from nco import NCO

@dataclass
class FrameResult:
    msg: np.ndarray = None
    carrier: np.ndarray = None
    am_out: np.ndarray = None
    fm_out: np.ndarray = None
    am_chan: np.ndarray = None
    fm_chan: np.ndarray = None
    am_rec: np.ndarray = None
    fm_rec: np.ndarray = None
    inst_freq: np.ndarray = None
    
    freq_axis: np.ndarray = None
    psd_am: np.ndarray = None
    psd_fm: np.ndarray = None
    waterfall_am: np.ndarray = None
    waterfall_fm: np.ndarray = None
    
    am_metrics: dict = field(default_factory=dict)
    fm_metrics: dict = field(default_factory=dict)
    ch_metrics_am: dict = field(default_factory=dict)
    ch_metrics_fm: dict = field(default_factory=dict)
    spec_metrics_am: dict = field(default_factory=dict)
    spec_metrics_fm: dict = field(default_factory=dict)
    recon_am: dict = field(default_factory=dict)
    recon_fm: dict = field(default_factory=dict)
    am_sys_metrics: dict = field(default_factory=dict)
    fm_sys_metrics: dict = field(default_factory=dict)
    diagnostics: list = field(default_factory=list)

class SimulationEngine:
    def __init__(self, sr=44100.0, fft_size=4096):
        self.sr = sr
        self.fft_size = fft_size
        self._dirty = True
        
        self._fc = 10000.0
        self._ac = 1.0
        self._fm = 1000.0
        self._am_m = 0.8
        self._am_mode = 'DSB-FC'
        self._fm_delta_f = 4000.0
        
        self._carrier_nco = NCO(self._fc, self.sr, 0.0)
        self._am_mod = AMModulator(self._fc, self._ac, self._am_m, self._am_mode, self.sr)
        self._fm_mod = FMModulator(self._fc, self._ac, self._fm_delta_f, self.sr)
        self._channel = Channel(self.sr)
        self._am_demod = AMDemodulator('ENVELOPE', self._fc, 4000.0, self.sr)
        self._fm_demod = FMDemodulator(4000.0, self.sr)
        self._spec_am = SpectrumAnalyzer(self.sr, self.fft_size, waterfall_n=80)
        self._spec_fm = SpectrumAnalyzer(self.sr, self.fft_size, waterfall_n=80)
        
        self._input_adapter = None
        self._output_adapter = None

    def update_params(self, **kwargs):
        for k, v in kwargs.items():
            if k == 'fc':
                self._fc = v
                self._carrier_nco.set_frequency(v)
                self._am_mod.set_params(fc=v)
                self._fm_mod.set_params(fc=v)
                self._am_demod.fc = v
            elif k == 'ac':
                self._ac = v
                self._am_mod.set_params(ac=v)
                self._fm_mod.set_params(ac=v)
            elif k == 'fm':
                self._fm = v
            elif k == 'am_m':
                self._am_m = v
                self._am_mod.set_params(m=v)
            elif k == 'am_mode':
                self._am_mode = v
                self._am_mod.set_params(mode=v)
            elif k == 'fm_delta_f':
                self._fm_delta_f = v
                self._fm_mod.set_params(delta_f=v)
            elif k == 'phase_c':
                self._carrier_nco.set_phase(np.radians(v))
            elif k in ['noise_enabled', 'snr_db', 'attenuation_db', 'interference_enabled']:
                self._channel.set_params(**{k: v})
        self._dirty = True

    def process_frame(self, msg: np.ndarray, am_enabled=True, fm_enabled=True) -> FrameResult:
        result = FrameResult()
        result.msg = msg
        
        result.carrier, _ = self._carrier_nco.generate(len(msg))
        
        if am_enabled:
            result.am_out, _, _, am_meta = self._am_mod.process(msg)
            result.am_chan, result.ch_metrics_am = self._channel.process(result.am_out)
            result.am_rec = self._am_demod.process(result.am_chan, result.carrier)
            fa, psd, wf, _, sm = self._spec_am.process(result.am_chan)
            result.freq_axis = fa
            result.psd_am = psd
            result.waterfall_am = wf
            result.spec_metrics_am = sm
            result.am_sys_metrics = SystemMetrics.analyze_am(result.am_out, msg, self._fc, self._fm, self._am_m, self._ac, sm['obw_99_hz'])
            result.recon_am = compute_reconstruction_metrics(msg, result.am_rec)
            result.am_metrics = am_meta
        
        if fm_enabled:
            result.fm_out, _, result.inst_freq, fm_meta = self._fm_mod.process(msg, self._fm)
            result.fm_chan, result.ch_metrics_fm = self._channel.process(result.fm_out)
            result.fm_rec = self._fm_demod.process(result.fm_chan)
            ff, psd, wf, _, sm = self._spec_fm.process(result.fm_chan)
            if result.freq_axis is None:
                result.freq_axis = ff
            result.psd_fm = psd
            result.waterfall_fm = wf
            result.spec_metrics_fm = sm
            result.fm_sys_metrics = SystemMetrics.analyze_fm(result.fm_out, result.inst_freq, self._fc, self._fm, self._fm_delta_f, self._ac, sm['obw_99_hz'])
            result.recon_fm = compute_reconstruction_metrics(msg, result.fm_rec)
            result.fm_metrics = fm_meta
        
        result.diagnostics = SystemMetrics.diagnose_quality(
            result.recon_am.get('psnr_db', 0) if am_enabled else 0,
            result.recon_fm.get('psnr_db', 0) if fm_enabled else 0,
            self._channel.snr_db if self._channel.noise_enabled else float('inf')
        )
        
        return result
    
    def set_input_adapter(self, adapter):
        self._input_adapter = adapter
    
    def set_output_adapter(self, adapter):
        self._output_adapter = adapter
'''

with open('simulation_engine.py', 'w', encoding='utf-8') as f:
    f.write(engine_code)

with open('dashboard.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
'''from experiments import EXPERIMENT_LIST, ExperimentRunner
from nco import NCO

# ── Constants & DSP Configuration ────────────────────────────''',
'''from experiments import EXPERIMENT_LIST, ExperimentRunner
from nco import NCO
from simulation_engine import SimulationEngine, FrameResult

# ── Constants & DSP Configuration ────────────────────────────''')

content = content.replace(
'''        elif self._msg_type == 'wav':
            self._src = WaveformSource('sine', self._fm, self._am, sr=SR)''',
'''        elif self._msg_type == 'wav':
            path, _ = QtWidgets.QFileDialog.getOpenFileName(
                self, 'Select Audio File', '', 'Audio Files (*.wav *.mp3 *.flac);;All Files (*)'
            )
            if path:
                self._src = WavSource(path, sr=SR)
            else:
                self._src = WaveformSource('sine', self._fm, self._am, sr=SR)''')

workers_code = '''
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


# ═════════════════════════════════════════════════════════════
#  MAIN LAB WORKBENCH WINDOW
# ═════════════════════════════════════════════════════════════'''

content = content.replace(
'''# ═════════════════════════════════════════════════════════════
#  MAIN LAB WORKBENCH WINDOW
# ═════════════════════════════════════════════════════════════''', workers_code)

old_run_exp = '''    def _run_current_experiment(self):
        row = self._exp_list_widget.currentRow()
        exp_id = row + 1
        res = self._exp_runner.run_experiment(exp_id)
        
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

        self._exp_conclusion_box.setText(res.get('conclusion', 'Experiment Completed.'))'''

new_run_exp = '''    def _run_current_experiment(self):
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

        self._exp_conclusion_box.setText(res.get('conclusion', 'Experiment Completed.'))'''

content = content.replace(old_run_exp, new_run_exp)

old_sweep = '''    def _run_snr_sweep(self):
        """Runs live Monte-Carlo SNR sweep comparing AM and FM."""
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

        self._curve_snr_am.setData(snr_in, am_out_snr)
        self._curve_snr_fm.setData(snr_in, fm_out_snr)'''

new_sweep = '''    def _run_snr_sweep(self):
        """Runs live Monte-Carlo SNR sweep comparing AM and FM."""
        self._sweep_worker = _SweepWorker()
        self._sweep_worker.finished.connect(self._on_sweep_finished)
        self._sweep_worker.start()

    def _on_sweep_finished(self, snr_in, am_out_snr, fm_out_snr):
        self._curve_snr_am.setData(snr_in, am_out_snr)
        self._curve_snr_fm.setData(snr_in, fm_out_snr)'''

content = content.replace(old_sweep, new_sweep)

content = content.replace(
'''        # 6. Spectral Analysis (Windowed FFT + dBm + Waterfall)
        fa, psd_am, wf_am, _, spec_meta_am = self._spec_am.process(am_out)
        ff, psd_fm, wf_fm, _, spec_meta_fm = self._spec_fm.process(fm_out)''',
'''        # 6. Spectral Analysis (Windowed FFT + dBm + Waterfall)
        fa, psd_am, wf_am, _, spec_meta_am = self._spec_am.process(am_chan)
        ff, psd_fm, wf_fm, _, spec_meta_fm = self._spec_fm.process(fm_chan)''')

with open('dashboard.py', 'w', encoding='utf-8') as f:
    f.write(content)
