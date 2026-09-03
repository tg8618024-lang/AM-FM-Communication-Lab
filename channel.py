# channel.py
"""
Communication Channel Simulation Module
=======================================
Simulates physical transmission channel impairments:
  - Additive White Gaussian Noise (AWGN) with exact SNR (dB) calibration
    Equation: SNR_dB = 10 * log10(P_sig / P_noise)
  - Channel Path Attenuation (dB)
    Equation: P_out = P_in * 10^(-Loss_dB / 10)
  - Narrowband Co-Channel / Adjacent-Channel Interference
    Equation: S(t) = S(t) + A * cos(2*pi*f*t + phi)
  - Impulse Noise Burst Simulation
    Equation: S(t) = +/- A with probability P
  - Flat Fading
    Equation: G(t) = 1 - (1 - 10^(-Depth/20)) * 0.5 * (1 + sin(2*pi*0.5*t))
"""

import numpy as np


class Channel:
    """
    Simulates real-world transmission channel effects.
    """
    def __init__(self, sr: float = 44100.0):
        self.sr = float(sr)
        self.noise_enabled = False
        self.snr_db = 30.0               # Signal-to-Noise Ratio in dB
        self.attenuation_db = 0.0         # Path loss in dB (0 = no loss)
        self.interference_enabled = False
        self.f_interference = 7500.0     # Interference frequency in Hz
        self.interference_sir_db = 10.0  # Signal-to-Interference Ratio in dB
        self._interf_phase = 0.0
        
        # New parameters
        self.impulse_enabled = False
        self.impulse_prob = 0.001
        self.impulse_amplitude = 5.0
        
        self.fading_enabled = False
        self.fading_depth_db = 6.0
        self._fading_t = 0.0
        
        self.rng = np.random.RandomState(None)

    def set_params(self, noise_enabled: bool = None, snr_db: float = None,
                   attenuation_db: float = None, interference_enabled: bool = None,
                   f_interference: float = None, interference_sir_db: float = None,
                   impulse_enabled: bool = None, impulse_prob: float = None,
                   impulse_amplitude: float = None, seed: int = None,
                   fading_enabled: bool = None, fading_depth_db: float = None):
        """Update channel parameters dynamically."""
        if noise_enabled is not None:
            self.noise_enabled = bool(noise_enabled)
        if snr_db is not None:
            self.snr_db = float(snr_db)
        if attenuation_db is not None:
            self.attenuation_db = float(attenuation_db)
        if interference_enabled is not None:
            self.interference_enabled = bool(interference_enabled)
        if f_interference is not None:
            self.f_interference = float(f_interference)
        if interference_sir_db is not None:
            self.interference_sir_db = float(interference_sir_db)
        if impulse_enabled is not None:
            self.impulse_enabled = bool(impulse_enabled)
        if impulse_prob is not None:
            self.impulse_prob = float(impulse_prob)
        if impulse_amplitude is not None:
            self.impulse_amplitude = float(impulse_amplitude)
        if seed is not None:
            self.rng = np.random.RandomState(seed)
        if fading_enabled is not None:
            self.fading_enabled = bool(fading_enabled)
        if fading_depth_db is not None:
            self.fading_depth_db = float(fading_depth_db)

    def process(self, signal: np.ndarray) -> tuple[np.ndarray, dict]:
        """
        Pass a signal through the channel.

        Returns:
            noisy_signal : np.ndarray
            metrics      : dict with true measured P_signal, P_noise, true_snr_db
        """
        if len(signal) == 0:
            return signal, {'p_sig': 0.0, 'p_noise': 0.0, 'snr_db': self.snr_db}

        out = signal.astype(np.float64)

        # 1. Channel Attenuation (Path Loss)
        if self.attenuation_db > 0.0:
            gain_linear = 10.0 ** (-self.attenuation_db / 20.0)
            out = out * gain_linear

        # 1.5 Flat Fading
        if self.fading_enabled:
            n_samples = len(out)
            t_steps = self._fading_t + np.arange(n_samples) / self.sr
            self._fading_t = (t_steps[-1] + 1.0 / self.sr)
            
            depth = self.fading_depth_db
            fading_gain = 1.0 - (1.0 - 10.0**(-depth/20.0)) * 0.5 * (1.0 + np.sin(2.0 * np.pi * 0.5 * t_steps))
            out = out * fading_gain

        p_sig = float(np.mean(out ** 2))
        p_noise = 0.0
        metrics = {}

        # 2. Narrowband Interference
        if self.interference_enabled:
            sir_linear = 10.0 ** (self.interference_sir_db / 10.0)
            p_interf_target = max(p_sig / sir_linear, 1e-9)
            a_interf = np.sqrt(2.0 * p_interf_target)
            
            n_samples = len(out)
            t_steps = np.arange(n_samples) / self.sr
            phases = self._interf_phase + 2.0 * np.pi * self.f_interference * t_steps
            self._interf_phase = (phases[-1] + 2.0 * np.pi * self.f_interference / self.sr) % (2.0 * np.pi)
            
            interference = a_interf * np.cos(phases)
            out = out + interference
            
            p_interf_actual = float(np.mean(interference ** 2))
            p_noise += p_interf_actual
            metrics['p_interference'] = p_interf_actual

        # 3. Additive White Gaussian Noise (AWGN)
        if self.noise_enabled:
            # Calibrate noise power: SNR_dB = 10 * log10(P_sig / P_noise_awgn)
            snr_linear = 10.0 ** (self.snr_db / 10.0)
            target_p_noise = max(p_sig / snr_linear, 1e-12)
            noise_std = np.sqrt(target_p_noise)
            
            noise = self.rng.normal(0.0, noise_std, size=len(out))
            out = out + noise
            p_noise += float(np.mean(noise ** 2))

        # 4. Impulse Noise
        if self.impulse_enabled:
            impulse_mask = self.rng.random(size=len(out)) < self.impulse_prob
            signs = self.rng.choice([-1.0, 1.0], size=len(out))
            out_before = out.copy()
            out[impulse_mask] = signs[impulse_mask] * self.impulse_amplitude
            impulse_noise = out - out_before
            p_noise += float(np.mean(impulse_noise ** 2))

        actual_snr_db = 10.0 * np.log10(p_sig / (p_noise + 1e-15)) if p_noise > 0 else 100.0

        metrics.update({
            'p_sig': p_sig,
            'p_noise': p_noise,
            'snr_db': self.snr_db if self.noise_enabled else 100.0,
            'measured_snr_db': actual_snr_db if p_noise > 0 else 100.0,
            'attenuation_db': self.attenuation_db,
            'interference_enabled': self.interference_enabled,
            'impulse_enabled': self.impulse_enabled,
            'fading_enabled': self.fading_enabled,
            'fading_depth_db': self.fading_depth_db
        })

        return out.astype(np.float32), metrics
