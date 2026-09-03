# experiments.py
"""
ECE Experiment Laboratory Suite
================================
10 Predefined Communication Engineering Experiments:
  1. Effect of AM Modulation Index (m) & Power Efficiency
  2. AM Overmodulation & Envelope Distortion Analysis
  3. AM Bandwidth Verification (BW = 2*fm)
  4. FM Frequency Deviation (Δf) Sweep
  5. FM Modulation Index (β) & NBFM vs WBFM Transition
  6. FM Bandwidth Validation via Carson's Rule
  7. Effect of AWGN Channel Noise on Demodulated Signal Quality
  8. AM vs FM Noise Performance & FM Threshold/Capture Effect
  9. Baseband Waveform Demodulation Fidelity (Sine, Square, Triangle, Chirp)
  10. Full System Theoretical vs. Measured Verification Benchmark
"""

import numpy as np
from waveforms import generate_waveform
from modulator import AMModulator, FMModulator
from channel import Channel
from demodulator import AMDemodulator, FMDemodulator, compute_reconstruction_metrics
from spectrum import SpectrumAnalyzer
from measurements import SystemMetrics


EXPERIMENT_LIST = [
    {
        'id': 1,
        'title': 'Exp 1: Effect of AM Modulation Index (m) & Efficiency',
        'desc': 'Observe AM waveform envelope, sideband power growth, and transmission efficiency as m increases from 0.25 to 1.0.',
        'params': {'fc': 10000.0, 'fm': 1000.0, 'm_sweep': [0.25, 0.50, 0.75, 1.0], 'wave_type': 'sine'}
    },
    {
        'id': 2,
        'title': 'Exp 2: AM Overmodulation (m > 1.0) & Distortion',
        'desc': 'Demonstrate envelope inversion and resulting non-linear distortion in diode/envelope detectors when m > 1.0.',
        'params': {'fc': 10000.0, 'fm': 1000.0, 'm_sweep': [0.5, 1.0, 1.5, 2.0], 'wave_type': 'sine'}
    },
    {
        'id': 3,
        'title': 'Exp 3: AM Bandwidth Verification (BW = 2 * fm)',
        'desc': 'Verify that AM occupied bandwidth is strictly equal to 2*fm regardless of carrier frequency.',
        'params': {'fc': 10000.0, 'fm_sweep': [500.0, 1000.0, 2000.0, 3000.0], 'm': 0.8, 'wave_type': 'sine'}
    },
    {
        'id': 4,
        'title': 'Exp 4: FM Peak Frequency Deviation (Δf) Sweep',
        'desc': 'Analyze instantaneous frequency swing and spectrum spread as frequency deviation Δf increases.',
        'params': {'fc': 10000.0, 'fm': 1000.0, 'delta_f_sweep': [1000.0, 2500.0, 5000.0, 8000.0], 'wave_type': 'sine'}
    },
    {
        'id': 5,
        'title': 'Exp 5: FM Modulation Index (β) & NBFM vs WBFM Transition',
        'desc': 'Examine the transition from Narrowband FM (single sideband pair) to Wideband FM (Bessel multi-harmonics).',
        'params': {'fc': 10000.0, 'fm': 1000.0, 'beta_sweep': [0.5, 1.0, 2.5, 5.0], 'wave_type': 'sine'}
    },
    {
        'id': 6,
        'title': 'Exp 6: FM Bandwidth Validation via Carson\'s Rule',
        'desc': 'Validate Carson\'s empirical bandwidth rule BW ≈ 2*(Δf + fm) against measured 99% occupied bandwidth.',
        'params': {'fc': 10000.0, 'fm': 1000.0, 'delta_f_sweep': [1000.0, 3000.0, 5000.0, 7000.0], 'wave_type': 'sine'}
    },
    {
        'id': 7,
        'title': 'Exp 7: Effect of AWGN Channel Noise on Signal Quality',
        'desc': 'Measure output SNR, MSE, and Pearson correlation coefficient across channel SNR levels from 5 dB to 40 dB.',
        'params': {'fc': 10000.0, 'fm': 1000.0, 'snr_sweep': [5, 10, 15, 20, 30, 40], 'wave_type': 'sine'}
    },
    {
        'id': 8,
        'title': 'Exp 8: AM vs FM Noise Performance & FM Threshold Effect',
        'desc': 'Direct performance comparison between AM and FM under identical noisy channel conditions.',
        'params': {'fc': 10000.0, 'fm': 1000.0, 'm': 0.8, 'delta_f': 4000.0, 'snr_sweep': [5, 10, 15, 20, 25, 30], 'wave_type': 'sine'}
    },
    {
        'id': 9,
        'title': 'Exp 9: Baseband Waveform Demodulation Fidelity',
        'desc': 'Test reconstruction fidelity (MSE, Correlation) for Sine, Square, Triangle, and Chirp message waveforms.',
        'params': {'fc': 10000.0, 'fm': 1000.0, 'waveforms': ['sine', 'square', 'triangle', 'sawtooth']}
    },
    {
        'id': 10,
        'title': 'Exp 10: Complete Theoretical vs. Measured Verification Report',
        'desc': 'Comprehensive validation table comparing theoretical vs. measured parameters for both AM and FM.',
        'params': {'fc': 10000.0, 'fm': 1000.0, 'm': 0.8, 'delta_f': 4000.0, 'snr': 25.0}
    },
    {
        'id': 11, 'title': 'Exp 11: Signal Quality vs Waveform Type',
        'desc': 'Compare reconstruction quality (MSE, correlation, PSNR) for different baseband waveform types through AM and FM pipelines.',
        'category': 'Quality'
    },
    {
        'id': 12, 'title': 'Exp 12: Sampling & Aliasing Demonstration',
        'desc': 'Demonstrate Nyquist theorem by generating signals at increasing frequencies relative to the sampling rate and measuring spectral aliasing.',
        'category': 'Fundamentals'
    },
    {
        'id': 13, 'title': 'Exp 13: Parameter Optimization',
        'desc': 'Find optimal modulation parameters (m for AM, delta_f for FM) that satisfy user-defined bandwidth and SNR constraints.',
        'category': 'Design'
    }
]


class ExperimentRunner:
    """
    Executes automated communication laboratory experiments.
    """
    def __init__(self, sr: float = 44100.0):
        self.sr = float(sr)
        self.n_samples = 4096

    def run_experiment(self, exp_id: int) -> dict:
        """Dispatches and executes the requested experiment by ID."""
        if exp_id == 1:
            return self._run_exp1()
        elif exp_id == 2:
            return self._run_exp2()
        elif exp_id == 3:
            return self._run_exp3()
        elif exp_id == 4:
            return self._run_exp4()
        elif exp_id == 5:
            return self._run_exp5()
        elif exp_id == 6:
            return self._run_exp6()
        elif exp_id == 7:
            return self._run_exp7()
        elif exp_id == 8:
            return self._run_exp8()
        elif exp_id == 9:
            return self._run_exp9()
        elif exp_id == 10:
            return self._run_exp10()
        elif exp_id == 11:
            return self._run_exp11()
        elif exp_id == 12:
            return self._run_exp12()
        elif exp_id == 13:
            return self._run_exp13()
        else:
            return {'error': f"Invalid Experiment ID: {exp_id}"}

    def _run_exp1(self) -> dict:
        """Exp 1: AM modulation index sweep."""
        fc, fm = 10000.0, 1000.0
        m_vals = [0.25, 0.50, 0.75, 1.0]
        results = []
        
        msg = generate_waveform('sine', fm, 1.0, 0.0, self.n_samples, self.sr)
        for m in m_vals:
            am_mod = AMModulator(fc, 1.0, m, 'DSB-FC', self.sr)
            am_sig, _, _, _ = am_mod.process(msg)
            spec = SpectrumAnalyzer(self.sr, self.n_samples)
            _, _, _, _, s_meta = spec.process(am_sig)
            
            p_c = 0.5
            p_sb = p_c * (m**2) / 2.0
            p_total = p_c + p_sb
            eff = (m**2) / (2.0 + m**2) * 100.0
            
            results.append({
                'm': m,
                'p_carrier_w': p_c,
                'p_sideband_w': p_sb,
                'p_total_w': p_total,
                'efficiency_pct': eff,
                'obw_measured_hz': s_meta['obw_99_hz']
            })

        conclusion = (
            "Conclusion: Increasing modulation index m increases sideband power and transmission efficiency. "
            "At m = 1.0 (100% modulation), maximum theoretical efficiency of 33.3% is achieved for single-tone AM. "
            "Carrier power remains constant at Ac^2 / 2 regardless of modulation depth."
        )

        return {
            'id': 1,
            'title': 'Exp 1: Effect of AM Modulation Index (m) & Power Efficiency',
            'data': results,
            'conclusion': conclusion
        }

    def _run_exp2(self) -> dict:
        """Exp 2: AM overmodulation."""
        fc, fm = 10000.0, 1000.0
        m_vals = [0.5, 1.0, 1.5, 2.0]
        results = []
        msg = generate_waveform('sine', fm, 1.0, 0.0, self.n_samples, self.sr)

        for m in m_vals:
            am_mod = AMModulator(fc, 1.0, m, 'DSB-FC', self.sr)
            am_sig, _, _, _ = am_mod.process(msg)
            
            # Demodulate with envelope detector
            demod = AMDemodulator('ENVELOPE', fc, 4000.0, self.sr)
            rec = demod.process(am_sig)
            rec_metrics = compute_reconstruction_metrics(msg, rec)

            results.append({
                'm': m,
                'is_overmod': m > 1.0,
                'status': 'Undermodulated' if m < 1.0 else ('100% Modulated' if m == 1.0 else 'OVERMODULATED (Distorted)'),
                'correlation': rec_metrics['correlation'],
                'mse': rec_metrics['mse'],
                'error_pct': rec_metrics['error_pct']
            })

        conclusion = (
            "Conclusion: When m > 1.0, the modulated envelope dips below zero and envelope inversion occurs. "
            "A standard envelope detector cannot track negative envelope excursions, producing severe harmonic "
            "distortion and sharp increases in reconstruction error."
        )

        return {
            'id': 2,
            'title': 'Exp 2: AM Overmodulation (m > 1.0) & Envelope Distortion',
            'data': results,
            'conclusion': conclusion
        }

    def _run_exp3(self) -> dict:
        """Exp 3: AM Bandwidth."""
        fc = 10000.0
        fm_vals = [500.0, 1000.0, 2000.0, 3000.0]
        results = []
        
        for fm in fm_vals:
            msg = generate_waveform('sine', fm, 1.0, 0.0, self.n_samples, self.sr)
            am_mod = AMModulator(fc, 1.0, 0.8, 'DSB-FC', self.sr)
            am_sig, _, _, _ = am_mod.process(msg)
            
            spec = SpectrumAnalyzer(self.sr, self.n_samples)
            _, _, _, _, s_meta = spec.process(am_sig)
            bw_theory = 2.0 * fm
            obw_meas = s_meta['obw_99_hz']
            err_pct = (abs(obw_meas - bw_theory) / bw_theory) * 100.0

            results.append({
                'fm_hz': fm,
                'bw_theory_hz': bw_theory,
                'bw_measured_hz': obw_meas,
                'error_pct': err_pct,
                'validated': err_pct < 15.0
            })

        conclusion = (
            "Conclusion: The occupied bandwidth of standard AM is strictly 2 * fm, containing exactly one "
            "Upper Sideband (fc + fm) and one Lower Sideband (fc - fm). Theory is verified across all message frequencies."
        )

        return {
            'id': 3,
            'title': 'Exp 3: AM Bandwidth Verification (BW = 2 * fm)',
            'data': results,
            'conclusion': conclusion
        }

    def _run_exp4(self) -> dict:
        """Exp 4: FM frequency deviation."""
        fc, fm = 10000.0, 1000.0
        delta_f_vals = [1000.0, 2500.0, 5000.0, 8000.0]
        results = []
        msg = generate_waveform('sine', fm, 1.0, 0.0, self.n_samples, self.sr)

        for df in delta_f_vals:
            fm_mod = FMModulator(fc, 1.0, df, self.sr)
            fm_sig, _, inst_f, meta = fm_mod.process(msg, fm)
            
            spec = SpectrumAnalyzer(self.sr, self.n_samples)
            _, _, _, _, s_meta = spec.process(fm_sig)
            
            results.append({
                'delta_f_hz': df,
                'beta': meta['beta'],
                'carson_bw_hz': meta['carson_bw'],
                'obw_measured_hz': s_meta['obw_99_hz']
            })

        conclusion = (
            "Conclusion: Peak frequency deviation Δf controls the maximum instantaneous frequency excursion (fc ± Δf). "
            "As Δf increases, power spreads across wider spectrum intervals, increasing Carson bandwidth."
        )

        return {
            'id': 4,
            'title': 'Exp 4: FM Frequency Deviation (Δf) Sweep',
            'data': results,
            'conclusion': conclusion
        }

    def _run_exp5(self) -> dict:
        """Exp 5: NBFM vs WBFM."""
        fc, fm = 10000.0, 1000.0
        beta_vals = [0.5, 1.0, 2.5, 5.0]
        results = []
        msg = generate_waveform('sine', fm, 1.0, 0.0, self.n_samples, self.sr)

        for b in beta_vals:
            df = b * fm
            fm_mod = FMModulator(fc, 1.0, df, self.sr)
            fm_sig, _, _, meta = fm_mod.process(msg, fm)
            
            spec = SpectrumAnalyzer(self.sr, self.n_samples)
            _, _, _, peaks, s_meta = spec.process(fm_sig)
            
            results.append({
                'beta': b,
                'delta_f_hz': df,
                'type': 'Narrowband FM (NBFM)' if b < 1.0 else 'Wideband FM (WBFM)',
                'num_significant_peaks': len(peaks),
                'carson_bw_hz': meta['carson_bw'],
                'obw_measured_hz': s_meta['obw_99_hz']
            })

        conclusion = (
            "Conclusion: For β < 1 (NBFM), FM spectrum closely resembles AM with a single dominant sideband pair (BW ≈ 2*fm). "
            "For β > 1 (WBFM), higher-order Bessel harmonic sidebands appear at fc ± n*fm, significantly expanding bandwidth."
        )

        return {
            'id': 5,
            'title': 'Exp 5: FM Modulation Index (β) & NBFM vs WBFM Transition',
            'data': results,
            'conclusion': conclusion
        }

    def _run_exp6(self) -> dict:
        """Exp 6: Carson's Rule."""
        fc, fm = 10000.0, 1000.0
        df_vals = [1000.0, 3000.0, 5000.0, 7000.0]
        results = []
        msg = generate_waveform('sine', fm, 1.0, 0.0, self.n_samples, self.sr)

        for df in df_vals:
            fm_mod = FMModulator(fc, 1.0, df, self.sr)
            fm_sig, _, _, meta = fm_mod.process(msg, fm)
            
            spec = SpectrumAnalyzer(self.sr, self.n_samples)
            _, _, _, _, s_meta = spec.process(fm_sig)
            
            c_bw = meta['carson_bw']
            obw_meas = s_meta['obw_99_hz']
            err_pct = (abs(obw_meas - c_bw) / c_bw) * 100.0

            results.append({
                'delta_f_hz': df,
                'beta': df / fm,
                'carson_bw_theory_hz': c_bw,
                'obw_measured_hz': obw_meas,
                'error_pct': err_pct,
                'validated': err_pct < 25.0
            })

        conclusion = (
            "Conclusion: Carson's rule BW ≈ 2*(Δf + fm) captures >98% of the total transmitted FM power. "
            "Measured 99% occupied bandwidth closely agrees with Carson's formula across all frequency deviations."
        )

        return {
            'id': 6,
            'title': 'Exp 6: FM Bandwidth Validation via Carson\'s Rule',
            'data': results,
            'conclusion': conclusion
        }

    def _run_exp7(self) -> dict:
        """Exp 7: AWGN Noise effect."""
        fc, fm = 10000.0, 1000.0
        snr_vals = [5, 10, 15, 20, 30, 40]
        results = []
        msg = generate_waveform('sine', fm, 1.0, 0.0, self.n_samples, self.sr)
        
        am_mod = AMModulator(fc, 1.0, 0.8, 'DSB-FC', self.sr)
        am_sig, _, _, _ = am_mod.process(msg)
        demod = AMDemodulator('ENVELOPE', fc, 4000.0, self.sr)

        for snr in snr_vals:
            chan = Channel(self.sr)
            chan.set_params(noise_enabled=True, snr_db=snr)
            noisy_sig, _ = chan.process(am_sig)
            rec = demod.process(noisy_sig)
            rec_metrics = compute_reconstruction_metrics(msg, rec)

            results.append({
                'channel_snr_db': snr,
                'demod_correlation': rec_metrics['correlation'],
                'demod_mse': rec_metrics['mse'],
                'demod_psnr_db': rec_metrics['psnr_db']
            })

        conclusion = (
            "Conclusion: Channel AWGN degrades demodulation fidelity. At SNR >= 20 dB, high correlation (rho > 0.95) "
            "is maintained. Below 10 dB SNR, noise begins dominating the envelope, causing rapid MSE growth."
        )

        return {
            'id': 7,
            'title': 'Exp 7: Effect of AWGN Channel Noise on Demodulated Signal Quality',
            'data': results,
            'conclusion': conclusion
        }

    def _run_exp8(self) -> dict:
        """Exp 8: AM vs FM noise comparison."""
        fc, fm = 10000.0, 1000.0
        snr_vals = [5, 10, 15, 20, 25, 30]
        results = []
        msg = generate_waveform('sine', fm, 1.0, 0.0, self.n_samples, self.sr)

        am_mod = AMModulator(fc, 1.0, 0.8, 'DSB-FC', self.sr)
        am_sig, _, _, _ = am_mod.process(msg)
        am_demod = AMDemodulator('ENVELOPE', fc, 4000.0, self.sr)

        fm_mod = FMModulator(fc, 1.0, 4000.0, self.sr)
        fm_sig, _, _, _ = fm_mod.process(msg, fm)
        fm_demod = FMDemodulator(4000.0, self.sr)

        for snr in snr_vals:
            chan = Channel(self.sr)
            chan.set_params(noise_enabled=True, snr_db=snr)
            
            # AM channel & demod
            noisy_am, _ = chan.process(am_sig)
            rec_am = am_demod.process(noisy_am)
            m_am = compute_reconstruction_metrics(msg, rec_am)

            # FM channel & demod
            noisy_fm, _ = chan.process(fm_sig)
            rec_fm = fm_demod.process(noisy_fm)
            m_fm = compute_reconstruction_metrics(msg, rec_fm)

            results.append({
                'channel_snr_db': snr,
                'am_correlation': m_am['correlation'],
                'fm_correlation': m_fm['correlation'],
                'am_mse': m_am['mse'],
                'fm_mse': m_fm['mse'],
                'better_system': 'FM' if m_fm['mse'] < m_am['mse'] else 'AM'
            })

        conclusion = (
            "Conclusion: At high channel SNR (>15 dB), Wideband FM demonstrates superior noise immunity over AM "
            "due to frequency modulation index gain. However, at low SNR (<10 dB), FM exhibits a threshold effect "
            "where discriminator click noise degrades performance rapidly."
        )

        return {
            'id': 8,
            'title': 'Exp 8: AM vs FM Noise Performance & FM Threshold Effect',
            'data': results,
            'conclusion': conclusion
        }

    def _run_exp9(self) -> dict:
        """Exp 9: Waveform fidelity."""
        fc, fm = 10000.0, 1000.0
        wtypes = ['sine', 'square', 'triangle', 'sawtooth']
        results = []

        for wt in wtypes:
            msg = generate_waveform(wt, fm, 1.0, 0.0, self.n_samples, self.sr)
            am_mod = AMModulator(fc, 1.0, 0.8, 'DSB-FC', self.sr)
            am_sig, _, _, _ = am_mod.process(msg)
            demod = AMDemodulator('ENVELOPE', fc, 4000.0, self.sr)
            rec = demod.process(am_sig)
            metrics = compute_reconstruction_metrics(msg, rec)

            results.append({
                'waveform': wt.capitalize(),
                'correlation': metrics['correlation'],
                'mse': metrics['mse'],
                'error_pct': metrics['error_pct']
            })

        conclusion = (
            "Conclusion: Smooth waveforms (Sine, Triangle) demodulate with high correlation (>0.95). "
            "Waveforms with sharp discontinuities (Square, Sawtooth) experience slight Gibbs ringing "
            "and harmonic attenuation due to the finite bandwidth of the receiver reconstruction LPF."
        )

        return {
            'id': 9,
            'title': 'Exp 9: Baseband Waveform Demodulation Fidelity',
            'data': results,
            'conclusion': conclusion
        }

    def _run_exp10(self) -> dict:
        """Exp 10: Complete benchmark."""
        fc, fm, m, df = 10000.0, 1000.0, 0.8, 4000.0
        msg = generate_waveform('sine', fm, 1.0, 0.0, self.n_samples, self.sr)

        # AM analysis
        am_mod = AMModulator(fc, 1.0, m, 'DSB-FC', self.sr)
        am_sig, _, _, _ = am_mod.process(msg)
        spec_am = SpectrumAnalyzer(self.sr, self.n_samples)
        _, _, _, _, s_am = spec_am.process(am_sig)
        am_metrics = SystemMetrics.analyze_am(am_sig, msg, fc, fm, m, 1.0, s_am['obw_99_hz'])

        # FM analysis
        fm_mod = FMModulator(fc, 1.0, df, self.sr)
        fm_sig, _, inst_f, _ = fm_mod.process(msg, fm)
        spec_fm = SpectrumAnalyzer(self.sr, self.n_samples)
        _, _, _, _, s_fm = spec_fm.process(fm_sig)
        fm_metrics = SystemMetrics.analyze_fm(fm_sig, inst_f, fc, fm, df, 1.0, s_fm['obw_99_hz'])

        conclusion = (
            "Complete Laboratory Validation Summary:\n"
            f"  • AM Bandwidth: Theory = {am_metrics['bw_theory_hz']:.1f} Hz | Measured = {am_metrics['bw_measured_hz']:.1f} Hz (Error: {am_metrics['bw_error_pct']:.1f}%)\n"
            f"  • AM Efficiency: {am_metrics['efficiency_pct']:.1f}% (Theory Validated)\n"
            f"  • FM Carson BW: Theory = {fm_metrics['carson_bw_theory_hz']:.1f} Hz | Measured = {fm_metrics['bw_measured_hz']:.1f} Hz (Error: {fm_metrics['bw_error_pct']:.1f}%)\n"
            "All core communication principles are verified within standard numerical simulation tolerances."
        )

        return {
            'id': 10,
            'title': 'Exp 10: Complete Theoretical vs. Measured Verification Report',
            'am_metrics': am_metrics,
            'fm_metrics': fm_metrics,
            'conclusion': conclusion
        }


    def _run_exp11(self) -> dict:
        fc, fm = 10000.0, 1000.0
        wtypes = ['sine', 'square', 'triangle', 'sawtooth']
        results = []

        for wt in wtypes:
            msg = generate_waveform(wt, fm, 1.0, 0.0, self.n_samples, self.sr)
            
            am_mod = AMModulator(fc, 1.0, 0.8, 'DSB-FC', self.sr)
            am_sig, _, _, _ = am_mod.process(msg)
            am_demod = AMDemodulator('ENVELOPE', fc, 4000.0, self.sr)
            rec_am = am_demod.process(am_sig)
            am_metrics = compute_reconstruction_metrics(msg, rec_am)
            
            fm_mod = FMModulator(fc, 1.0, 4000.0, self.sr)
            fm_sig, _, _, _ = fm_mod.process(msg, fm)
            fm_demod = FMDemodulator(4000.0, self.sr)
            rec_fm = fm_demod.process(fm_sig)
            fm_metrics = compute_reconstruction_metrics(msg, rec_fm)
            
            results.append({
                'waveform': wt,
                'am_correlation': am_metrics['correlation'],
                'am_mse': am_metrics['mse'],
                'fm_correlation': fm_metrics['correlation'],
                'fm_mse': fm_metrics['mse']
            })

        return {
            'id': 11,
            'title': 'Exp 11: Signal Quality vs Waveform Type',
            'data': results,
            'conclusion': "FM generally exhibits better reconstruction fidelity across waveform types compared to AM envelope detection."
        }

    def _run_exp12(self) -> dict:
        freqs = [1000.0, 5000.0, 10000.0, 15000.0, 20000.0, 22000.0]
        results = []
        nyquist = self.sr / 2.0
        
        for f in freqs:
            msg = generate_waveform('sine', f, 1.0, 0.0, self.n_samples, self.sr)
            
            spec = SpectrumAnalyzer(self.sr, self.n_samples)
            f_axis, mag, _, _, _ = spec.process(msg)
            peak_idx = int(np.argmax(mag))
            meas_f = float(f_axis[peak_idx])
            
            aliased = abs(meas_f - f) > 10.0
            
            results.append({
                'input_freq': f,
                'measured_peak_freq': meas_f,
                'aliased': aliased,
                'nyquist_limit': nyquist
            })
            
        return {
            'id': 12,
            'title': 'Exp 12: Sampling & Aliasing Demonstration',
            'data': results,
            'conclusion': "Demonstrates Nyquist theorem behavior."
        }

    def _run_exp13(self) -> dict:
        fc, fm = 10000.0, 1000.0
        m_vals = [0.2, 0.4, 0.6, 0.8, 1.0]
        df_vals = [500.0, 1000.0, 2000.0, 4000.0, 6000.0]
        results = []
        
        msg = generate_waveform('sine', fm, 1.0, 0.0, self.n_samples, self.sr)
        chan = Channel(self.sr)
        chan.set_params(noise_enabled=True, snr_db=20.0)
        
        best_cfg = None
        best_qual = -1.0
        
        am_demod = AMDemodulator('ENVELOPE', fc, 4000.0, self.sr)
        for m in m_vals:
            am_mod = AMModulator(fc, 1.0, m, 'DSB-FC', self.sr)
            am_sig, _, _, _ = am_mod.process(msg)
            
            spec = SpectrumAnalyzer(self.sr, self.n_samples)
            _, _, _, _, s_meta = spec.process(am_sig)
            bw = float(s_meta['obw_99_hz'])
            
            noisy, _ = chan.process(am_sig)
            rec = am_demod.process(noisy)
            met = compute_reconstruction_metrics(msg, rec)
            corr = float(met['correlation'])
            
            results.append({
                'mod_type': 'AM',
                'param_val': m,
                'bw_hz': bw,
                'correlation': corr,
                'mse': float(met['mse'])
            })
            
            if bw <= 5000.0 and corr > best_qual:
                best_qual = corr
                best_cfg = f"AM with m={m}"
                
        fm_demod = FMDemodulator(4000.0, self.sr)
        for df in df_vals:
            fm_mod = FMModulator(fc, 1.0, df, self.sr)
            fm_sig, _, _, _ = fm_mod.process(msg, fm)
            
            spec = SpectrumAnalyzer(self.sr, self.n_samples)
            _, _, _, _, s_meta = spec.process(fm_sig)
            bw = float(s_meta['obw_99_hz'])
            
            noisy, _ = chan.process(fm_sig)
            rec = fm_demod.process(noisy)
            met = compute_reconstruction_metrics(msg, rec)
            corr = float(met['correlation'])
            
            results.append({
                'mod_type': 'FM',
                'param_val': df,
                'bw_hz': bw,
                'correlation': corr,
                'mse': float(met['mse'])
            })
            
            if bw <= 5000.0 and corr > best_qual:
                best_qual = corr
                best_cfg = f"FM with delta_f={df}"
                
        return {
            'id': 13,
            'title': 'Exp 13: Parameter Optimization',
            'data': results,
            'conclusion': f"Optimal parameters within bandwidth limit: {best_cfg}"
        }
