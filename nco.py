# nco.py
"""
Numerically Controlled Oscillator (NCO)
========================================
Generates a phase-continuous quadrature carrier at arbitrary frequency:
  I(t) = cos(2*pi*fc*t + phi0)
  Q(t) = sin(2*pi*fc*t + phi0)
"""

import numpy as np


class NCO:
    """
    Phase-continuous sinusoidal signal generator across arbitrary block sizes.
    """
    def __init__(self, fc: float = 10000.0, sr: float = 44100.0, initial_phase: float = 0.0):
        self.sr = float(sr)
        self.fc = float(fc)
        self._phase = float(initial_phase) % (2.0 * np.pi)

    def set_frequency(self, fc: float):
        """Update carrier frequency without causing instantaneous phase discontinuity."""
        self.fc = float(fc)

    def set_phase(self, phase_rad: float):
        """Set absolute carrier phase in radians."""
        self._phase = float(phase_rad) % (2.0 * np.pi)

    def generate(self, n: int) -> tuple[np.ndarray, np.ndarray]:
        """
        Generate next n samples of in-phase (cos) and quadrature (sin) carrier.
        
        Returns:
            (cos_out, sin_out) : tuple of np.ndarray of shape (n,)
        """
        if n <= 0:
            return np.empty(0, dtype=np.float32), np.empty(0, dtype=np.float32)

        t_steps = np.arange(n, dtype=np.float64)
        phases = self._phase + (2.0 * np.pi * self.fc / self.sr) * t_steps
        
        # Advance phase accumulator for the next frame
        self._phase = (phases[-1] + 2.0 * np.pi * self.fc / self.sr) % (2.0 * np.pi)

        cos_out = np.cos(phases).astype(np.float32)
        sin_out = np.sin(phases).astype(np.float32)
        return cos_out, sin_out
