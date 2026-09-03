# demodulator.py
"""
Demodulation and Reconstruction Engine
======================================
Implements practical and theoretical receiver demodulators:
  - AM Envelope Detector (Analytic Hilbert & Diode RC Peak Detector)
  - AM Coherent Synchronous Detector (Product Mixer + LPF)
  - FM Instantaneous Phase Discriminator (with stateful phase unwrapping)
  - Reconstruction Error Analyzer (MSE, RMSE, Correlation, Peak SNR)
"""

import numpy as np
from scipy.signal import hilbert, butter, lfilter, lfilter_zi


class StatefulLPF:
    """IIR Butterworth Low-Pass Filter with continuous state carryover across frames."""
    def __init__(self, cutoff_hz: float, sr: float, order: int = 4):
        self.sr = float(sr)
        self.cutoff_hz = float(cutoff_hz)
        self.order = int(order)
        self._update_coeffs()

    def _update_coeffs(self):
        nyq = self.sr / 2.0
        norm_cutoff = min(max(self.cutoff_hz / nyq, 0.001), 0.95)
        self.b, self.a = butter(self.order, norm_cutoff, btype='low')
        self.zi = lfilter_zi(self.b, self.a) * 0.0

    def set_cutoff(self, cutoff_hz: float):
        if abs(cutoff_hz - self.cutoff_hz) > 1.0:
            self.cutoff_hz = float(cutoff_hz)
            self._update_coeffs()

    def process(self, data: np.ndarray) -> np.ndarray:
        if len(data) == 0:
            return data
        y, self.zi = lfilter(self.b, self.a, data, zi=self.zi)
        return y.astype(np.float32)


class AMDemodulator:
    """
    AM Demodulator supporting:
      - 'ENVELOPE': Hilbert analytic magnitude |z(t)| + DC removal + LPF
      - 'DIODE_RC': Diode peak rectifier with RC decay time constant
      - 'COHERENT' : Product detection (s_AM(t) * cos(2*pi*fc*t)) + LPF
    """
    def __init__(self, method: str = 'ENVELOPE', fc: float = 10000.0,
                 fm_max: float = 4000.0, sr: float = 44100.0):
        self.method = method.upper().strip()
        self.fc = float(fc)
        self.fm_max = float(fm_max)
        self.sr = float(sr)
        self.lpf = StatefulLPF(self.fm_max, self.sr, order=4)
        self._rc_val = 0.0  # capacitor memory for diode RC

    def set_params(self, method: str = None, fc: float = None, fm_max: float = None):
        if method is not None:
            self.method = method.upper().strip()
        if fc is not None:
            self.fc = float(fc)
        if fm_max is not None:
            self.fm_max = float(fm_max)
            self.lpf.set_cutoff(self.fm_max)

    def process(self, am_signal: np.ndarray, carrier_ref: np.ndarray = None) -> np.ndarray:
        """
        Demodulate incoming AM signal.
        """
        if len(am_signal) == 0:
            return np.empty(0, dtype=np.float32)

        if self.method == 'COHERENT' and carrier_ref is not None:
            # Synchronous Product Detector: mix with carrier and low-pass filter
            mixed = am_signal * carrier_ref
            demod = self.lpf.process(mixed)
            # Remove DC component
            demod = demod - np.mean(demod)
        elif self.method == 'DIODE_RC':
            # Diode Half-Wave Rectifier + RC Low-Pass Filter
            dt = 1.0 / self.sr
            rc_tau = 1.0 / (2.0 * np.pi * self.fm_max * 1.5)  # optimized discharge
            decay = np.exp(-dt / rc_tau)
            
            demod = np.zeros_like(am_signal)
            v_cap = self._rc_val
            for k in range(len(am_signal)):
                v_in = max(0.0, float(am_signal[k]))  # ideal diode
                if v_in > v_cap:
                    v_cap = v_in  # fast charge
                else:
                    v_cap = v_cap * decay  # exponential discharge
                demod[k] = v_cap
            self._rc_val = v_cap
            
            # Post filter & DC removal
            demod = self.lpf.process(demod)
            demod = demod - np.mean(demod)
        else:
            # Default: Envelope detector via Hilbert Analytic Signal
            analytic = hilbert(am_signal.astype(np.float64))
            envelope = np.abs(analytic).astype(np.float32)
            # Remove DC carrier bias
            envelope_ac = envelope - np.mean(envelope)
            demod = self.lpf.process(envelope_ac)

        # Scale output matching standard level
        std = np.std(demod)
        if std > 1e-6:
            demod = demod / (std * np.sqrt(2.0))

        return demod.astype(np.float32)


class FMDemodulator:
    """
    FM Demodulator:
      Extracts instantaneous frequency deviation via analytic phase derivative:
      f_inst(t) = (1 / 2*pi) * d(unwrap(angle(z(t)))) / dt
    """
    def __init__(self, fm_max: float = 4000.0, sr: float = 44100.0):
        self.fm_max = float(fm_max)
        self.sr = float(sr)
        self.lpf = StatefulLPF(self.fm_max, self.sr, order=4)
        self._last_phase = 0.0

    def set_params(self, fm_max: float = None):
        if fm_max is not None:
            self.fm_max = float(fm_max)
            self.lpf.set_cutoff(self.fm_max)

    def process(self, fm_signal: np.ndarray) -> np.ndarray:
        """
        Demodulate incoming FM signal.
        """
        if len(fm_signal) == 0:
            return np.empty(0, dtype=np.float32)

        # 1. Analytic Signal
        analytic = hilbert(fm_signal.astype(np.float64))
        
        # 2. Instantaneous unwrapped phase with continuous boundary stitching
        raw_phase = np.angle(analytic)
        # Stitch: adjust so raw_phase[0] is continuous with _last_phase
        phase_offset = self._last_phase - raw_phase[0]
        # Round to nearest 2*pi multiple to preserve the unwrapped structure
        phase_offset = np.round(phase_offset / (2.0 * np.pi)) * (2.0 * np.pi)
        adjusted = raw_phase + phase_offset
        unwrapped = np.unwrap(adjusted)
        
        # Prepend last phase to keep derivative length equal to signal length
        stitched_for_diff = np.insert(unwrapped, 0, self._last_phase)
        self._last_phase = unwrapped[-1]

        # 3. Discrete Phase Derivative: dphi / dt
        d_phase = np.diff(stitched_for_diff)
        inst_freq = d_phase * (self.sr / (2.0 * np.pi))

        # 4. Remove DC carrier frequency and apply low-pass reconstruction filter
        inst_freq_ac = inst_freq - np.mean(inst_freq)
        demod = self.lpf.process(inst_freq_ac.astype(np.float32))

        # Standardize amplitude scale
        std = np.std(demod)
        if std > 1e-6:
            demod = demod / (std * np.sqrt(2.0))

        return demod.astype(np.float32)


def compute_reconstruction_metrics(original: np.ndarray, recovered: np.ndarray) -> dict:
    """
    Computes rigorous signal reconstruction error metrics:
      - Mean Squared Error (MSE)
      - Root Mean Squared Error (RMSE)
      - Pearson Correlation Coefficient (rho)
      - Peak Signal-to-Noise Ratio (PSNR in dB)
      - Reconstruction Error Percentage (%)
    """
    n = min(len(original), len(recovered))
    if n < 10:
        return {'mse': 0.0, 'rmse': 0.0, 'correlation': 1.0, 'error_pct': 0.0, 'psnr_db': 100.0}

    orig = original[:n].astype(np.float64)
    rec = recovered[:n].astype(np.float64)

    # Best-fit delay alignment (cross-correlation peak)
    max_lag = min(150, n // 4)
    
    orig_std = np.std(orig)
    rec_std = np.std(rec)
    if orig_std > 1e-6 and rec_std > 1e-6:
        norm_rec = rec * (orig_std / rec_std)
    else:
        norm_rec = rec

    from scipy.signal import correlate
    corr_full = correlate(orig, norm_rec, mode='full')
    norm = np.sqrt(np.sum(orig**2) * np.sum(norm_rec**2))
    if norm > 0:
        corr_full /= norm
        
    mid = len(orig) - 1
    search_start = max(0, mid - max_lag)
    search_end = min(len(corr_full), mid + max_lag + 1)
    
    best_idx = search_start + np.argmax(corr_full[search_start:search_end])
    best_lag = best_idx - mid
    best_corr = float(corr_full[best_idx])
    
    if best_lag < 0:
        o_sub = orig[-best_lag:]
        r_sub = norm_rec[:best_lag]
    elif best_lag > 0:
        o_sub = orig[:-best_lag]
        r_sub = norm_rec[best_lag:]
    else:
        o_sub = orig
        r_sub = norm_rec
        
    mse = float(np.mean((o_sub - r_sub) ** 2))
    rmse = np.sqrt(mse)
    p_orig = np.mean(orig ** 2)
    error_pct = (rmse / max(np.sqrt(p_orig), 1e-6)) * 100.0
    psnr_db = 10.0 * np.log10(max(np.max(orig)**2, 1e-6) / max(mse, 1e-12))

    return {
        'mse': float(mse),
        'rmse': float(rmse),
        'correlation': float(best_corr),
        'error_pct': float(error_pct),
        'psnr_db': float(psnr_db)
    }

