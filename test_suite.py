# test_suite.py
"""
Automated Mathematical Correctness Test Suite
==============================================
Validates core DSP and analog communication modules:
  - Waveform synthesis
  - AM DSB-FC / DSB-SC / SSB modulation
  - FM frequency deviation & continuous phase
  - AWGN channel SNR calibration
  - Demodulation fidelity & reconstruction metrics
  - Carson's bandwidth & transmission efficiency
"""

import os
import sys
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from waveforms import generate_waveform
from nco import NCO
from modulator import AMModulator, FMModulator
from channel import Channel
from demodulator import AMDemodulator, FMDemodulator, compute_reconstruction_metrics
from measurements import SystemMetrics
from spectrum import SpectrumAnalyzer


SR = 44100.0


def test_waveform_generation():
    """Verify waveform shape, amplitude, and sampling."""
    n = 1000
    sine = generate_waveform('sine', 1000.0, 1.0, 0.0, n, SR)
    assert len(sine) == n
    assert abs(np.max(sine) - 1.0) < 0.05
    assert abs(np.min(sine) - (-1.0)) < 0.05

    square = generate_waveform('square', 1000.0, 1.0, 0.0, n, SR)
    assert np.all(np.abs(square) <= 1.05)
    print("  [PASS] test_waveform_generation")


def test_nco_phase_continuity():
    """Verify NCO advances phase without discontinuities."""
    nco = NCO(10000.0, SR)
    c1, _ = nco.generate(100)
    c2, _ = nco.generate(100)
    t = np.arange(200) / SR
    expected = np.cos(2 * np.pi * 10000.0 * t)
    combined = np.concatenate([c1, c2])
    assert np.allclose(combined, expected, atol=1e-3)
    print("  [PASS] test_nco_phase_continuity")


def test_am_modulation_and_efficiency():
    """Verify AM single-tone transmission efficiency formula: eta = m^2 / (2 + m^2)."""
    fc, fm, m = 10000.0, 1000.0, 0.8
    msg = generate_waveform('sine', fm, 1.0, 0.0, 4096, SR)
    am_mod = AMModulator(fc, 1.0, m, 'DSB-FC', SR)
    am_sig, _, _, meta = am_mod.process(msg)

    expected_eff = (0.8 ** 2) / (2.0 + 0.8 ** 2) * 100.0
    assert abs(meta['efficiency_theory'] - expected_eff) < 1e-4
    assert len(am_sig) == 4096
    print(f"  [PASS] test_am_modulation_and_efficiency (Efficiency = {expected_eff:.2f}%)")


def test_fm_carson_bandwidth():
    """Verify FM Carson bandwidth: BW = 2 * (Delta_f + fm)."""
    fc, fm, delta_f = 10000.0, 1000.0, 4000.0
    msg = generate_waveform('sine', fm, 1.0, 0.0, 4096, SR)
    fm_mod = FMModulator(fc, 1.0, delta_f, SR)
    fm_sig, _, _, meta = fm_mod.process(msg, fm)

    expected_bw = 2.0 * (delta_f + fm)
    assert abs(meta['carson_bw'] - expected_bw) < 1e-4
    assert meta['beta'] == 4.0
    assert not meta['is_nbfm']
    print(f"  [PASS] test_fm_carson_bandwidth (Carson BW = {expected_bw:.1f} Hz, beta = 4.0)")


def test_channel_awgn_snr():
    """Verify channel calibrated noise matches requested SNR in dB."""
    chan = Channel(SR)
    chan.set_params(noise_enabled=True, snr_db=20.0)
    sig = np.sin(2 * np.pi * 1000.0 * np.arange(20000) / SR).astype(np.float32)
    
    noisy, meta = chan.process(sig)
    measured_snr = meta['measured_snr_db']
    assert abs(measured_snr - 20.0) < 1.0
    print(f"  [PASS] test_channel_awgn_snr (Target = 20 dB, Measured = {measured_snr:.2f} dB)")


def test_demodulation_reconstruction():
    """Verify AM and FM demodulate with high correlation on clean channels."""
    fc, fm = 10000.0, 1000.0
    msg = generate_waveform('sine', fm, 1.0, 0.0, 4096, SR)

    # AM Test
    am_mod = AMModulator(fc, 1.0, 0.8, 'DSB-FC', SR)
    am_sig, car, _, _ = am_mod.process(msg)
    am_demod = AMDemodulator('ENVELOPE', fc, 4000.0, SR)
    rec_am = am_demod.process(am_sig, car)
    metrics_am = compute_reconstruction_metrics(msg, rec_am)
    assert metrics_am['correlation'] > 0.95
    print(f"  [PASS] test_demodulation_reconstruction (AM Correlation = {metrics_am['correlation']:.3f})")

    # FM Test
    fm_mod = FMModulator(fc, 1.0, 4000.0, SR)
    fm_sig, _, _, _ = fm_mod.process(msg, fm)
    fm_demod = FMDemodulator(4000.0, SR)
    rec_fm = fm_demod.process(fm_sig)
    metrics_fm = compute_reconstruction_metrics(msg, rec_fm)
    assert metrics_fm['correlation'] > 0.90
    print(f"  [PASS] test_demodulation_reconstruction (FM Correlation = {metrics_fm['correlation']:.3f})")


def test_waveform_phase_continuity():
    """Generate two consecutive blocks of 1024 samples using t_offset. Verify no phase jump."""
    n = 1024
    b1 = generate_waveform('sine', 1000.0, 1.0, 0.0, n, SR, t_offset=0.0)
    b2 = generate_waveform('sine', 1000.0, 1.0, 0.0, n, SR, t_offset=n/SR)
    b_full = generate_waveform('sine', 1000.0, 1.0, 0.0, 2*n, SR, t_offset=0.0)
    
    assert abs(b2[0] - b_full[n]) < 1e-4, "Phase discontinuity detected"
    print("  [PASS] test_waveform_phase_continuity")


def test_waveform_nyquist_validation():
    """Call generate_waveform with fm >= sr/2 and fm <= 0."""
    try:
        w = generate_waveform('sine', SR, 1.0, 0.0, 100, SR)
        assert len(w) == 100
    except Exception as e:
        assert False, f"Crashed on Nyquist limit: {e}"
        
    try:
        generate_waveform('sine', 0, 1.0, 0.0, 100, SR)
        assert False, "Should have raised ValueError for fm <= 0"
    except ValueError:
        pass
    print("  [PASS] test_waveform_nyquist_validation")


def test_waveform_types():
    """Generate all 5 types, verify each returns float32 array of correct length."""
    types = ['sine', 'square', 'triangle', 'sawtooth', 'chirp']
    n = 512
    for wt in types:
        w = generate_waveform(wt, 1000.0, 1.0, 0.0, n, SR)
        assert len(w) == n, f"{wt} length mismatch"
        assert w.dtype == np.float32, f"{wt} dtype mismatch"
    print("  [PASS] test_waveform_types")


def test_am_overmodulation_envelope():
    """Create AM signal with m=1.5. Verify the envelope is always >= 0."""
    fc, fm, m = 10000.0, 1000.0, 1.5
    msg = generate_waveform('sine', fm, 1.0, 0.0, 1024, SR)
    am_mod = AMModulator(fc, 1.0, m, 'DSB-FC', SR)
    _, _, env, _ = am_mod.process(msg)
    assert np.all(env >= 0.0), "Envelope should be >= 0"
    print("  [PASS] test_am_overmodulation_envelope")


def test_am_dsb_sc_mode():
    """Test DSB-SC mode produces zero carrier component."""
    fc, fm, m = 10000.0, 1000.0, 1.0
    msg = generate_waveform('sine', fm, 1.0, 0.0, 4096, SR)
    am_mod = AMModulator(fc, 1.0, m, 'DSB-SC', SR)
    am_sig, _, _, _ = am_mod.process(msg)
    
    freqs = np.fft.rfftfreq(len(am_sig), 1.0/SR)
    fft_vals = np.abs(np.fft.rfft(am_sig))
    fc_idx = np.argmin(np.abs(freqs - fc))
    assert fft_vals[fc_idx] < 0.1 * np.max(fft_vals), "Carrier present in DSB-SC"
    print("  [PASS] test_am_dsb_sc_mode")


def test_fm_carrier_reference_clean():
    """Verify the carrier_ref is a clean sinusoid."""
    fc, fm = 10000.0, 1000.0
    msg = generate_waveform('sine', fm, 1.0, 0.0, 4096, SR)
    fm_mod = FMModulator(fc, 1.0, 2000.0, SR)
    _, car_ref, _, _ = fm_mod.process(msg, fm)
    
    freqs = np.fft.rfftfreq(len(car_ref), 1.0/SR)
    fft_vals = np.abs(np.fft.rfft(car_ref))
    fc_idx = np.argmin(np.abs(freqs - fc))
    peak_idx = np.argmax(fft_vals)
    assert fc_idx == peak_idx, "Peak is not at fc"
    assert fft_vals[peak_idx] > 10 * np.mean(fft_vals), "Carrier ref not a clean sinusoid"
    print("  [PASS] test_fm_carrier_reference_clean")


def test_fm_demod_block_continuity():
    """Run FMDemodulator.process() on two consecutive blocks. Verify no spike."""
    fc, fm = 10000.0, 1000.0
    msg = generate_waveform('sine', fm, 1.0, 0.0, 2048, SR)
    fm_mod = FMModulator(fc, 1.0, 2000.0, SR)
    fm_sig, _, _, _ = fm_mod.process(msg, fm)
    
    fm_demod = FMDemodulator(2000.0, SR)
    block1 = fm_demod.process(fm_sig[:1024])
    block2 = fm_demod.process(fm_sig[1024:])
    
    diff1 = np.abs(block2[0] - block1[-1])
    diff_median = np.median(np.abs(np.diff(block1)))
    assert diff1 < 5.0 * diff_median + 1e-3, f"Spike detected: diff={diff1}, median={diff_median}"
    print("  [PASS] test_fm_demod_block_continuity")


def test_am_measured_modulation_index():
    """Generate AM with m=0.5 and m=0.8, m_measured within 15%."""
    fc, fm = 10000.0, 1000.0
    for m in [0.5, 0.8]:
        msg = generate_waveform('sine', fm, 1.0, 0.0, 4096, SR)
        am_mod = AMModulator(fc, 1.0, m, 'DSB-FC', SR)
        am_sig, _, _, _ = am_mod.process(msg)
        
        metrics = SystemMetrics.analyze_am(am_sig, msg, fc, fm, m)
        m_meas = metrics['m_measured']
        assert abs(m_meas - m) / m < 0.15, f"m_measured {m_meas} not within 15% of {m}"
    print("  [PASS] test_am_measured_modulation_index")


def test_spectrum_peak_frequency():
    """SpectrumAnalyzer peak_freq within 50 Hz."""
    sig = generate_waveform('sine', 5000.0, 1.0, 0.0, 4096, SR)
    spec = SpectrumAnalyzer(SR)
    _, _, _, _, metrics = spec.process(sig)
    assert abs(metrics['peak_freq_hz'] - 5000.0) < 50.0, f"Peak freq {metrics['peak_freq_hz']} != 5000"
    print("  [PASS] test_spectrum_peak_frequency")


def test_spectrum_bandwidth():
    """SpectrumAnalyzer 99% OBW between 1500 and 3000."""
    fc, fm, m = 10000.0, 1000.0, 0.8
    msg = generate_waveform('sine', fm, 1.0, 0.0, 4096, SR)
    am_mod = AMModulator(fc, 1.0, m, 'DSB-FC', SR)
    am_sig, _, _, _ = am_mod.process(msg)
    
    spec = SpectrumAnalyzer(SR)
    _, _, _, _, metrics = spec.process(am_sig)
    obw = metrics['obw_99_hz']
    assert 1500.0 <= obw <= 3000.0, f"OBW {obw} not in [1500, 3000]"
    print("  [PASS] test_spectrum_bandwidth")


def test_channel_interference():
    """Channel interference at 7500 Hz."""
    chan = Channel(SR)
    chan.set_params(interference_enabled=True, f_interference=7500.0, interference_sir_db=0.0)
    
    # We need a small non-zero signal so interference power is computed non-zero based on SIR
    sig = generate_waveform('sine', 1000.0, 1.0, 0.0, 4096, SR)
    out, meta = chan.process(sig)
    
    assert meta.get('interference_enabled') is True, "Meta missing interference_enabled"
    spec = SpectrumAnalyzer(SR)
    _, _, _, _, metrics = spec.process(out)
    
    # Interefence is at 7500, signal is at 1000. Let's make sure both are present or 7500 is found.
    # Since SIR is 0 dB, they have roughly equal power, so peak might be 1000 or 7500.
    # We can check if either is the peak, or just find it in the peaks list.
    _, _, _, peaks, _ = spec.process(out)
    freqs = [p['freq'] for p in peaks]
    found = any(abs(f - 7500.0) < 50.0 for f in freqs)
    assert found, f"Interference tone 7500 not found in peaks: {freqs}"
    print("  [PASS] test_channel_interference")


def test_reconstruction_metrics_vectorized():
    """compute_reconstruction_metrics returns corr > 0.99."""
    msg = generate_waveform('sine', 1000.0, 1.0, 0.0, 4096, SR)
    lag = 5
    rec = np.zeros_like(msg)
    rec[lag:] = msg[:-lag]
    
    metrics = compute_reconstruction_metrics(msg, rec)
    assert metrics['correlation'] > 0.99, f"Correlation {metrics['correlation']} too low"
    print("  [PASS] test_reconstruction_metrics_vectorized")


def test_signal_quality_diagnostics():
    """diagnose_quality with overmodulated AM metrics."""
    am_metrics = {'is_overmodulated': True, 'm_theory': 1.5}
    diagnostics = SystemMetrics.diagnose_quality(am_metrics=am_metrics)
    assert len(diagnostics) > 0, "No diagnostics returned"
    found = any("Overmodulation" in d['issue'] for d in diagnostics)
    assert found, "Overmodulation issue not reported"
    print("  [PASS] test_signal_quality_diagnostics")


def run_all_tests():
    tests = [
        test_waveform_generation,
        test_nco_phase_continuity,
        test_am_modulation_and_efficiency,
        test_fm_carson_bandwidth,
        test_channel_awgn_snr,
        test_demodulation_reconstruction,
        test_waveform_phase_continuity,
        test_waveform_nyquist_validation,
        test_waveform_types,
        test_am_overmodulation_envelope,
        test_am_dsb_sc_mode,
        test_fm_carrier_reference_clean,
        test_fm_demod_block_continuity,
        test_am_measured_modulation_index,
        test_spectrum_peak_frequency,
        test_spectrum_bandwidth,
        test_channel_interference,
        test_reconstruction_metrics_vectorized,
        test_signal_quality_diagnostics
    ]
    
    passed = 0
    failed = 0
    
    print("=" * 60)
    print(" RUNNING AUTOMATED ECE LABORATORY MATHEMATICAL TESTS")
    print("=" * 60)
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {test.__name__}: {e}")
            failed += 1
            
    print("=" * 60)
    print(f" TOTAL PASSED: {passed}")
    print(f" TOTAL FAILED: {failed}")
    if failed == 0:
        print(" ALL TESTS PASSED! 100% MATHEMATICAL & DSP ACCURACY VERIFIED.")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()
