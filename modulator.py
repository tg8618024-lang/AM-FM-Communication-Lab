# modulator.py
"""
Analog Modulation Engine
========================
Mathematically precise modulators for:
  - Conventional AM (DSB-FC / Standard AM)
  - DSB-SC (Double-Sideband Suppressed-Carrier)
  - SSB (Single-Sideband: USB / LSB via Hilbert Transform)
  - FM (Frequency Modulation with configurable peak deviation Δf)
"""

import numpy as np
from scipy.signal import hilbert
from nco import NCO


class AMModulator:
    """
    Amplitude Modulator supporting:
      1. 'DSB-FC' (Conventional AM): s(t) = Ac * [1 + m * x(t)] * cos(2*pi*fc*t + phi)
      2. 'DSB-SC'                  : s(t) = Ac * x(t) * cos(2*pi*fc*t + phi)
      3. 'SSB-USB'                 : s(t) = Ac * [x(t)*cos(2*pi*fc*t) - x_hat(t)*sin(2*pi*fc*t)]
      4. 'SSB-LSB'                 : s(t) = Ac * [x(t)*cos(2*pi*fc*t) + x_hat(t)*sin(2*pi*fc*t)]
    """
    def __init__(self, fc: float = 10000.0, ac: float = 1.0, m: float = 0.8,
                 mode: str = 'DSB-FC', sr: float = 44100.0):
        self.fc = float(fc)
        self.ac = float(ac)
        self.m = float(m)
        self.mode = mode.upper().strip()
        self.sr = float(sr)
        self.nco = NCO(self.fc, self.sr)

    def set_params(self, fc: float = None, ac: float = None, m: float = None, mode: str = None):
        if fc is not None:
            self.fc = float(fc)
            self.nco.set_frequency(self.fc)
        if ac is not None:
            self.ac = float(ac)
        if m is not None:
            self.m = float(m)
        if mode is not None:
            self.mode = mode.upper().strip()

    def process(self, msg: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict]:
        """
        Modulate normalized message signal.

        Returns:
            am_out   : np.ndarray (modulated signal)
            carrier  : np.ndarray (unmodulated carrier reference)
            envelope : np.ndarray (instantaneous theoretical envelope)
            meta     : dict of theoretical metrics
        """
        n = len(msg)
        if n == 0:
            return np.empty(0), np.empty(0), np.empty(0), {}

        car_cos, car_sin = self.nco.generate(n)
        car_cos = (self.ac * car_cos).astype(np.float32)
        car_sin = (self.ac * car_sin).astype(np.float32)

        # Theoretical envelope
        envelope_raw = self.ac * (1.0 + self.m * msg)
        envelope = np.abs(envelope_raw).astype(np.float32)

        if self.mode == 'DSB-FC':
            # Conventional AM
            am_out = (1.0 + self.m * msg) * car_cos
        elif self.mode == 'DSB-SC':
            # Suppressed carrier
            am_out = msg * car_cos
            envelope = np.abs(self.ac * msg).astype(np.float32)
        elif self.mode in ('SSB-USB', 'USB'):
            # Upper Sideband via Hilbert transform
            x_hat = np.imag(hilbert(msg)).astype(np.float32)
            am_out = (msg * car_cos - x_hat * car_sin) * 0.5
            envelope = (0.5 * np.sqrt(msg**2 + x_hat**2)).astype(np.float32)
        elif self.mode in ('SSB-LSB', 'LSB'):
            # Lower Sideband
            x_hat = np.imag(hilbert(msg)).astype(np.float32)
            am_out = (msg * car_cos + x_hat * car_sin) * 0.5
            envelope = (0.5 * np.sqrt(msg**2 + x_hat**2)).astype(np.float32)
        else:
            # Default to DSB-FC
            am_out = (1.0 + self.m * msg) * car_cos

        # Theoretical power calculations for single tone:
        # P_c = Ac^2 / 2
        # P_sb = P_c * m^2 / 2 = Ac^2 * m^2 / 4
        # P_T = P_c * (1 + m^2 / 2)
        # Efficiency eta = m^2 / (2 + m^2) * 100%
        p_c = (self.ac ** 2) / 2.0
        p_sb = p_c * (self.m ** 2) / 2.0
        p_total = p_c * (1.0 + (self.m ** 2) / 2.0)
        efficiency = (self.m ** 2) / (2.0 + self.m ** 2) * 100.0

        meta = {
            'fc': self.fc,
            'm': self.m,
            'mode': self.mode,
            'p_carrier_theory': p_c,
            'p_sideband_theory': p_sb,
            'p_total_theory': p_total,
            'efficiency_theory': efficiency,
            'is_overmodulated': self.m > 1.0
        }

        return am_out.astype(np.float32), car_cos, envelope, meta


class FMModulator:
    """
    Frequency Modulator:
      s_FM(t) = Ac * cos( 2*pi*fc*t + 2*pi*kf * integral(x(tau) dtau) )
      where Delta f = kf * max|x(t)|
      beta = Delta f / fm
    """
    def __init__(self, fc: float = 10000.0, ac: float = 1.0, delta_f: float = 5000.0,
                 sr: float = 44100.0):
        self.fc = float(fc)
        self.ac = float(ac)
        self.delta_f = float(delta_f)  # Peak frequency deviation in Hz
        self.sr = float(sr)
        self._phase_acc = 0.0         # Continuous phase accumulator
        self._carrier_ref_nco = NCO(self.fc, self.sr)

    def set_params(self, fc: float = None, ac: float = None, delta_f: float = None):
        if fc is not None:
            self.fc = float(fc)
            self._carrier_ref_nco.set_frequency(self.fc)
        if ac is not None:
            self.ac = float(ac)
        if delta_f is not None:
            self.delta_f = float(delta_f)

    def process(self, msg: np.ndarray, fm_est: float = 1000.0) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict]:
        """
        Modulate normalized message signal.

        Returns:
            fm_out      : np.ndarray (modulated signal)
            carrier_ref : np.ndarray (reference unmodulated carrier)
            inst_freq   : np.ndarray (instantaneous frequency in Hz)
            meta        : dict of theoretical metrics (Carson BW, Beta, etc.)
        """
        n = len(msg)
        if n == 0:
            return np.empty(0), np.empty(0), np.empty(0), {}

        dt = 1.0 / self.sr
        t_steps = np.arange(n, dtype=np.float64) * dt

        # Instantaneous frequency: f_inst(t) = fc + delta_f * msg(t)
        inst_freq = self.fc + self.delta_f * msg.astype(np.float64)

        # Trapezoidal numerical phase integration:
        # phi[k] = phi[k-1] + 2*pi * (f_inst[k-1] + f_inst[k])/2 * dt
        d_phase = 2.0 * np.pi * inst_freq * dt
        phases = self._phase_acc + np.cumsum(d_phase)
        
        # Keep phase accumulator within [0, 2*pi) to prevent precision degradation
        self._phase_acc = float(phases[-1]) % (2.0 * np.pi)

        fm_out = (self.ac * np.cos(phases)).astype(np.float32)

        # Synchronized continuous reference carrier
        carrier_ref_raw, _ = self._carrier_ref_nco.generate(n)
        carrier_ref = (self.ac * carrier_ref_raw).astype(np.float32)

        # Modulation index beta = Delta f / fm
        beta = self.delta_f / max(fm_est, 1.0)
        # Carson's rule bandwidth: BW = 2 * (Delta f + fm) = 2 * fm * (1 + beta)
        carson_bw = 2.0 * (self.delta_f + max(fm_est, 1.0))

        meta = {
            'fc': self.fc,
            'delta_f': self.delta_f,
            'beta': beta,
            'carson_bw': carson_bw,
            'is_nbfm': beta < 1.0,
            'p_total_theory': (self.ac ** 2) / 2.0
        }

        return fm_out, carrier_ref, inst_freq.astype(np.float32), meta
