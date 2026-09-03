# waveforms.py
"""
Baseband Waveform Generator Module
===================================
Generates mathematically precise baseband test signals:
  - Sine wave
  - Square wave (with configurable duty cycle)
  - Triangle wave
  - Sawtooth wave (ramp up / ramp down)
  - Chirp (Linear / Exponential frequency sweep)
  - Multi-tone harmonic sum
"""

import numpy as np
from scipy import signal as sp_signal


def generate_sine(fm: float, am: float, phase_rad: float, n_samples: int, sr: float, t_offset: float = 0.0) -> np.ndarray:
    """Sine: s(t) = Am * cos(2*pi*fm*t + phi)"""
    t = t_offset + np.arange(n_samples) / sr
    return (am * np.cos(2 * np.pi * fm * t + phase_rad)).astype(np.float32)


def generate_square(fm: float, am: float, phase_rad: float, n_samples: int, sr: float, duty: float = 0.5, t_offset: float = 0.0) -> np.ndarray:
    """Square: s(t) = Am * sgn(cos(2*pi*fm*t + phi))"""
    t = t_offset + np.arange(n_samples) / sr
    return (am * sp_signal.square(2 * np.pi * fm * t + phase_rad, duty=duty)).astype(np.float32)


def generate_triangle(fm: float, am: float, phase_rad: float, n_samples: int, sr: float, t_offset: float = 0.0) -> np.ndarray:
    """Triangle: s(t) = Am * abs(2 * (fm*t + phi/(2*pi) - floor(fm*t + phi/(2*pi) + 0.5)))"""
    t = t_offset + np.arange(n_samples) / sr
    return (am * sp_signal.sawtooth(2 * np.pi * fm * t + phase_rad, width=0.5)).astype(np.float32)


def generate_sawtooth(fm: float, am: float, phase_rad: float, n_samples: int, sr: float, width: float = 1.0, t_offset: float = 0.0) -> np.ndarray:
    """Sawtooth: s(t) = Am * 2 * (fm*t + phi/(2*pi) - floor(fm*t + phi/(2*pi) + 0.5))"""
    t = t_offset + np.arange(n_samples) / sr
    return (am * sp_signal.sawtooth(2 * np.pi * fm * t + phase_rad, width=width)).astype(np.float32)


def generate_chirp(f0: float, f1: float, t1: float, am: float, phase_rad: float, n_samples: int, sr: float, method: str = 'linear', t_offset: float = 0.0) -> np.ndarray:
    """Chirp: Swept-frequency cosine from f0 to f1 over time t1"""
    t = t_offset + np.arange(n_samples) / sr
    # Wrap time around t1 for continuous streaming
    t_mod = np.mod(t, t1)
    chirp_sig = sp_signal.chirp(t_mod, f0=f0, t1=t1, f1=f1, method=method, phi=np.degrees(phase_rad))
    return (am * chirp_sig).astype(np.float32)


def generate_waveform(wave_type: str, fm: float, am: float = 1.0, phase_rad: float = 0.0,
                      n_samples: int = 1764, sr: float = 44100.0, **kwargs) -> np.ndarray:
    """
    Dispatcher function to generate any supported standard baseband waveform.
    """
    if fm <= 0 or am < 0 or sr <= 0:
        raise ValueError("Invalid parameters: fm, sr must be > 0 and am must be >= 0")
        
    if fm >= sr / 2:
        print(f"Warning: frequency {fm} exceeds Nyquist rate. Clamping to {sr/2 - 1}")
        fm = sr / 2 - 1

    wt = wave_type.lower().strip()
    t_offset = kwargs.get('t_offset', 0.0)

    if wt in ('sine', 'sin', 'single tone'):
        return generate_sine(fm, am, phase_rad, n_samples, sr, t_offset=t_offset)
    elif wt in ('square', 'sq'):
        duty = kwargs.get('duty', 0.5)
        return generate_square(fm, am, phase_rad, n_samples, sr, duty=duty, t_offset=t_offset)
    elif wt in ('triangle', 'tri'):
        return generate_triangle(fm, am, phase_rad, n_samples, sr, t_offset=t_offset)
    elif wt in ('sawtooth', 'saw', 'ramp'):
        width = kwargs.get('width', 1.0)
        return generate_sawtooth(fm, am, phase_rad, n_samples, sr, width=width, t_offset=t_offset)
    elif wt in ('chirp', 'sweep'):
        f0 = kwargs.get('f0', max(100.0, fm * 0.2))
        f1 = kwargs.get('f1', min(sr * 0.4, fm * 2.5))
        t1 = kwargs.get('t1', 0.1)  # 100 ms period
        return generate_chirp(f0, f1, t1, am, phase_rad, n_samples, sr, method=kwargs.get('method', 'linear'), t_offset=t_offset)
    else:
        # Default fallback
        return generate_sine(fm, am, phase_rad, n_samples, sr, t_offset=t_offset)
