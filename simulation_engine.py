from dataclasses import dataclass, field
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
