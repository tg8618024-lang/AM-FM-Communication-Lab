# measurements.py
"""
Communication Systems Automated Measurements & Theory Verification Engine
===========================================================================
Calculates live technical parameters and validates theoretical models:
  - AM Power, Efficiency, Modulation Index & Overmodulation Detection
  - FM Deviation, Modulation Index Beta & Carson's Bandwidth
  - Theory vs. Measured Comparison with % Error Validation
  - Channel SNR, Noise Degradation, MSE, RMSE & Correlation
"""

import numpy as np


class TheoryComparison:
    @staticmethod
    def compare(param_name: str, theoretical: float, measured: float, tolerance_pct: float = 5.0) -> dict:
        """
        Compare theoretical vs measured values.
        Returns dict with: param_name, theoretical, measured, abs_error, pct_error, validated, within_tolerance
        Error% = |Measured - Theoretical| / |Theoretical| * 100
        """
        abs_error = abs(measured - theoretical)
        pct_error = (abs_error / abs(theoretical) * 100.0) if abs(theoretical) > 1e-12 else 0.0
        return {
            'param_name': param_name,
            'theoretical': theoretical,
            'measured': measured,
            'abs_error': abs_error,
            'pct_error': pct_error,
            'validated': pct_error <= tolerance_pct,
            'within_tolerance': pct_error <= tolerance_pct
        }

class SystemMetrics:
    """
    Real-time calculation of communication metrics and theoretical validation.
    """
    @staticmethod
    def analyze_am(am_signal: np.ndarray, msg_signal: np.ndarray,
                   fc_theory: float, fm_theory: float, m_theory: float,
                   ac_theory: float = 1.0, obw_measured: float = 0.0) -> dict:
        """
        Calculates all theoretical and measured AM metrics.
        """
        # 1. Theoretical calculations
        p_c_theory = (ac_theory ** 2) / 2.0
        p_sb_theory = p_c_theory * (m_theory ** 2) / 2.0
        p_total_theory = p_c_theory * (1.0 + (m_theory ** 2) / 2.0)
        efficiency_theory = (m_theory ** 2) / (2.0 + m_theory ** 2) * 100.0
        bw_theory = 2.0 * max(fm_theory, 10.0)

        # 2. Measured calculations from waveform
        if len(am_signal) > 0:
            p_total_meas = float(np.mean(am_signal ** 2))
            
            # Envelope extrema for measured modulation index
            # Using positive peak and valley
            v_max = float(np.max(np.abs(am_signal)))
            # Minimum envelope valley (around carrier zero crossings)
            from scipy.signal import hilbert
            analytic = hilbert(am_signal.astype(np.float64))
            analytic_env = np.abs(analytic).astype(np.float64)
            v_min = float(np.min(analytic_env))
            
            if (v_max + v_min) > 1e-6 and m_theory <= 1.0:
                m_measured = (v_max - v_min) / (v_max + v_min)
            else:
                m_measured = m_theory  # when overmodulated envelope dips below 0
        else:
            p_total_meas = p_total_theory
            m_measured = m_theory

        # 3. Validation & Errors
        bw_error_pct = (abs(obw_measured - bw_theory) / max(bw_theory, 1.0)) * 100.0 if obw_measured > 0 else 0.0
        p_error_pct = (abs(p_total_meas - p_total_theory) / max(p_total_theory, 1e-6)) * 100.0

        is_overmod = m_theory > 1.0
        if is_overmod:
            mod_status = "OVERMODULATION (Envelope Inversion / Clipping)"
            status_color = "#ff1744"  # Red
        elif abs(m_theory - 1.0) < 0.02:
            mod_status = "100% MODULATION (Maximum Efficiency without Distortion)"
            status_color = "#ffd700"  # Gold
        else:
            mod_status = "UNDERMODULATION (Linear Envelope Detector Compatible)"
            status_color = "#00e5ff"  # Cyan

        return {
            'fc_hz': fc_theory,
            'fm_hz': fm_theory,
            'm_theory': m_theory,
            'm_measured': m_measured,
            'p_carrier_w': p_c_theory,
            'p_sideband_w': p_sb_theory,
            'p_total_theory_w': p_total_theory,
            'p_total_measured_w': p_total_meas,
            'efficiency_pct': efficiency_theory,
            'bw_theory_hz': bw_theory,
            'bw_measured_hz': obw_measured,
            'bw_error_pct': bw_error_pct,
            'bw_validated': bw_error_pct < 20.0,
            'is_overmodulated': is_overmod,
            'mod_status': mod_status,
            'status_color': status_color
        }

    @staticmethod
    def analyze_fm(fm_signal: np.ndarray, inst_freq: np.ndarray,
                   fc_theory: float, fm_theory: float, delta_f_theory: float,
                   ac_theory: float = 1.0, obw_measured: float = 0.0) -> dict:
        """
        Calculates all theoretical and measured FM metrics.
        """
        # 1. Theoretical calculations
        beta_theory = delta_f_theory / max(fm_theory, 1.0)
        carson_bw_theory = 2.0 * (delta_f_theory + max(fm_theory, 1.0))
        p_total_theory = (ac_theory ** 2) / 2.0

        # 2. Measured calculations
        if len(inst_freq) > 0:
            measured_delta_f = float(np.max(np.abs(inst_freq - fc_theory)))
            measured_beta = measured_delta_f / max(fm_theory, 1.0)
        else:
            measured_delta_f = delta_f_theory
            measured_beta = beta_theory

        if len(fm_signal) > 0:
            p_total_meas = float(np.mean(fm_signal ** 2))
        else:
            p_total_meas = p_total_theory

        # 3. Validation & Errors
        bw_error_pct = (abs(obw_measured - carson_bw_theory) / max(carson_bw_theory, 1.0)) * 100.0 if obw_measured > 0 else 0.0
        delta_f_error_pct = (abs(measured_delta_f - delta_f_theory) / max(delta_f_theory, 1.0)) * 100.0

        is_nbfm = beta_theory < 1.0
        if is_nbfm:
            fm_type = "NBFM (Narrowband FM: Single Sideband Pair Dominant)"
            status_color = "#00e5ff"
        else:
            fm_type = "WBFM (Wideband FM: Multi-Harmonic Bessel Sidebands)"
            status_color = "#bf00ff"

        return {
            'fc_hz': fc_theory,
            'fm_hz': fm_theory,
            'delta_f_theory_hz': delta_f_theory,
            'delta_f_measured_hz': measured_delta_f,
            'beta_theory': beta_theory,
            'beta_measured': measured_beta,
            'carson_bw_theory_hz': carson_bw_theory,
            'bw_measured_hz': obw_measured,
            'bw_error_pct': bw_error_pct,
            'bw_validated': bw_error_pct < 25.0,
            'p_total_theory_w': p_total_theory,
            'p_total_measured_w': p_total_meas,
            'is_nbfm': is_nbfm,
            'fm_type': fm_type,
            'status_color': status_color
        }

    @staticmethod
    def diagnose_quality(am_metrics: dict = None, fm_metrics: dict = None,
                         recon_am: dict = None, recon_fm: dict = None,
                         channel_snr_db: float = None) -> list:
        """
        Diagnose poor signal recovery. Returns list of dicts with:
        'issue', 'evidence', 'recommendation'
        """
        diagnostics = []
        
        if am_metrics and am_metrics.get('is_overmodulated'):
            diagnostics.append({
                'issue': 'AM Overmodulation',
                'evidence': f"m = {am_metrics.get('m_theory', '?'):.2f} > 1.0",
                'recommendation': 'Reduce modulation index below 1.0 to prevent envelope distortion'
            })
        
        if channel_snr_db is not None and channel_snr_db < 10:
            diagnostics.append({
                'issue': 'Low Channel SNR',
                'evidence': f'SNR = {channel_snr_db:.1f} dB < 10 dB',
                'recommendation': 'Increase transmit power or reduce channel noise'
            })
        
        if recon_am and recon_am.get('correlation', 1.0) < 0.8:
            diagnostics.append({
                'issue': 'Poor AM Reconstruction',
                'evidence': f"Correlation = {recon_am['correlation']:.3f} < 0.8",
                'recommendation': 'Check for overmodulation, reduce noise, or verify demodulator settings'
            })
        
        if recon_fm and recon_fm.get('correlation', 1.0) < 0.8:
            diagnostics.append({
                'issue': 'Poor FM Reconstruction',
                'evidence': f"Correlation = {recon_fm['correlation']:.3f} < 0.8",
                'recommendation': 'Reduce frequency deviation or increase SNR'
            })
        
        if fm_metrics and fm_metrics.get('beta_theory', 0) > 10:
            diagnostics.append({
                'issue': 'Excessive FM Deviation',
                'evidence': f"Beta = {fm_metrics['beta_theory']:.1f} > 10",
                'recommendation': 'Reduce frequency deviation to limit occupied bandwidth'
            })
        
        return diagnostics
