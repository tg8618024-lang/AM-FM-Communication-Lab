# AM & FM Communication Systems Laboratory
<img width="1067" height="757" alt="image" src="https://github.com/user-attachments/assets/74642cd6-62ae-4d9c-a229-c1f524a4cbc2" />
<img width="1770" height="1137" alt="Screenshot 2026-09-03 185402" src="https://github.com/user-attachments/assets/d297ad02-66cb-4658-8cc9-1156820829bf" />
<img width="1766" height="1135" alt="Screenshot 2026-09-03 185419" src="https://github.com/user-attachments/assets/d696cfb0-1367-4e0b-89f4-6cd2b551da0d" />
> 🌐 **Live Web Simulator**: [https://tg8618024-lang.github.io/AM-FM-Communication-Lab/](https://tg8618024-lang.github.io/AM-FM-Communication-Lab/)  
> **Interactive browser-based AM/FM lab with hardware SNR, Carson bandwidth, and real-time canvas scopes. Accessible on any mobile phone, tablet, or desktop!**

A professional virtual communication systems laboratory built with Python, PyQt6, and NumPy/SciPy. Provides interactive real-time simulation, analysis, and visualization of AM and FM analog communication systems.

## Table of Contents
1. [Problem Statement](#problem-statement)
2. [Objectives](#objectives)
3. [System Architecture](#system-architecture)
4. [Theory](#theory)
5. [Experiments (13 Total)](#experiments-13-total)
6. [Parameter Sweep Engine](#parameter-sweep-engine)
7. [Engineering Optimization Mode](#engineering-optimization-mode)
8. [Export & Reporting](#export--reporting)
9. [Installation](#installation)
10. [Usage](#usage)
11. [Testing](#testing)
12. [File Structure](#file-structure)
13. [Results & Validation](#results--validation)
14. [Known Limitations](#known-limitations)
15. [Future Work](#future-work)
16. [Dependencies](#dependencies)
17. [License](#license)

## Problem Statement
Traditional communication systems laboratory hardware is expensive, inflexible, and lacks deep visibility into intermediate mathematical operations. This project solves that problem by providing a high-fidelity virtual simulation environment for ECE (Electrical and Computer Engineering) education. It bridges the gap between theoretical textbook equations and practical, interactive signal analysis, allowing students and engineers to visualize time-domain envelopes, frequency-domain spectra, and real-time noise degradation simultaneously.

## Objectives
1. Real-time generation of various baseband message waveforms.
2. Accurate carrier synthesis using a phase-continuous Numerically Controlled Oscillator (NCO).
3. Simulation of Amplitude Modulation (AM) in DSB-FC mode.
4. Support for Suppressed-Carrier AM (DSB-SC) modulation.
5. Provision of Single-Sideband (SSB-USB, SSB-LSB) modulation modes.
6. Exact computation and real-time visualization of AM transmission efficiency.
7. Phase-continuous Frequency Modulation (FM) synthesis using precise phase integration.
8. Interactive control of FM peak frequency deviation and modulation index.
9. Accurate additive white Gaussian noise (AWGN) channel degradation based on target SNR.
10. Incorporation of channel path loss (attenuation) and interference parameters.
11. AM envelope demodulation using Hilbert transform techniques.
12. Synchronous coherent product demodulation for suppressed carrier schemes.
13. Instantaneous phase derivative discrimination for FM recovery.
14. High-fidelity FFT spectrum analysis with coherent window gain correction.
15. Precise 99% Occupied Bandwidth (OBW) calculations for modulated signals.
16. Automated test suite validating mathematical correctness.
17. Automated extraction and reporting of Root Mean Square Error (RMSE) metrics.
18. Real-time Pearson Correlation calculation to evaluate demodulated signal fidelity.
19. Execution of predefined ECE laboratory experiments.
20. Generation of professional CSV, JSON, PNG, and HTML engineering reports.

## System Architecture

The software utilizes a strict layered architecture separating DSP math from the GUI presentation.

- Frontend Layer (main.py, dashboard.py)
- Simulation Engine Layer (simulation_engine.py)
- DSP Modules (waveforms.py, signal_sources.py, modulator.py, demodulator.py, channel.py, spectrum.py, nco.py)
- Measurement & Analysis (measurements.py, experiments.py, sweep_engine.py, optimizer.py)
- Export (exporter.py)
- Testing (test_suite.py)

```text
+-------------------------------------------------------------+
|                     Frontend Layer                          |
|             (main.py, dashboard.py, run.py)                 |
+------------------------------+------------------------------+
                               |
+------------------------------v------------------------------+
|                   Simulation Engine Layer                   |
|                   (simulation_engine.py)                    |
+----+-------------+-------------+--------------+--------+----+
     |             |             |              |        |
+----v----+   +----v----+   +----v----+   +-----v---+ +--v--+
| Sources |   | NCO     |   | Modulate|   | Channel | |Demod|
+---------+   +---------+   +---------+   +---------+ +-----+
|         DSP Modules Layer (Vectorized NumPy/SciPy)        |
+-----------------------------------------------------------+
```

## Theory

### AM Modulation
- Mathematical equation: s_AM(t) = Ac[1 + m*cos(2*pi*fm*t)]*cos(2*pi*fc*t)
- Power: Pt = Pc(1 + m^2/2)
- Efficiency: eta = m^2/(2+m^2) * 100%
- Bandwidth: BW = 2*fm
- Supported modes: DSB-FC, DSB-SC, SSB-USB, SSB-LSB

### FM Modulation
- Mathematical equation: s_FM(t) = Ac*cos(2*pi*fc*t + beta*sin(2*pi*fm*t))
- beta = delta_f / fm
- Carson bandwidth: BW = 2*(delta_f + fm)
- NBFM vs WBFM classification

### Channel Model
- AWGN: sigma^2 = P_sig / 10^(SNR/10)
- Path loss, interference, impulse noise, flat fading

### Demodulation
- AM: Envelope detector, Diode-RC, Coherent product detector
- FM: Phase discriminator

### Spectrum Analysis
- Coherent rFFT with window correction
- 99% OBW bandwidth measurement
- Peak detection

## Experiments (13 Total)
1. Effect of AM Modulation Index: Observe envelope depth and efficiency scaling.
2. AM Overmodulation Demonstration: Analyze phase inversion and envelope clipping.
3. AM Bandwidth Verification: Measure 2*fm sideband spacing.
4. FM Peak Frequency Deviation: Trace the instantaneous frequency excursion.
5. FM Modulation Index & NBFM/WBFM: Observe Bessel sideband expansion.
6. FM Carson Bandwidth Rule Validation: Verify theoretical bandwidth against 99% OBW.
7. AWGN Channel Noise Effect: Observe MSE/SNR degradation in time and frequency domains.
8. AM vs FM Noise Performance: Compare noise resilience (FM capture effect).
9. Waveform Demodulation Fidelity: Evaluate the recovery of Square/Triangle waves.
10. Full Theoretical vs Measured Benchmark: Validates all metrics simultaneously.
11. Impact of Receiver Filter Bandwidth: Demonstrates trade-offs in noise vs signal energy.
12. Coherent vs Non-Coherent Detection: Compare DSB-SC recovery methodologies.
13. Carrier Frequency Offset Errors: Demonstrate coherent phase mismatch consequences.

## Parameter Sweep Engine
A dedicated simulation sweep engine allows users to perform single-variable and dual-variable parametric sweeps (e.g., sweeping SNR from 5 dB to 40 dB, or Modulation Index from 0.1 to 1.5). The engine aggregates steady-state metrics and visualizes the performance trends, helping visualize threshold effects and efficiency boundaries.

## Engineering Optimization Mode
*SIMULATION-BASED*
The optimization mode provides constraint-based parameter tuning using SciPy. Users can define a cost function (e.g., Maximize SNR while keeping Bandwidth < 15 kHz) and allow the mathematical optimizer to automatically adjust Modulation Index, Deviation, or Carrier attributes to find the theoretical optimal configuration for the simulated scenario.

## Export & Reporting
The laboratory includes a comprehensive export utility (exporter.py). Users can freeze the current simulation state and generate:
- CSV: Raw time-domain and frequency-domain buffer exports.
- JSON: Simulation state and parameter serialization.
- PNG: High-resolution plot captures of the UI scopes.
- HTML: A consolidated, beautifully formatted laboratory report suitable for university submission.

## Installation
```
pip install -r requirements.txt
```

## Usage
```
python main.py
```
Upon launching, you are presented with 6 navigation options:
1. Dashboard: Primary interactive real-time control center.
2. Oscilloscope: Dedicated time-domain view of message, RF, and recovered signals.
3. Spectrum Analyzer: Detailed frequency-domain view with FFT and waterfalls.
4. Measurement & Experiments: Access point for the 13 predefined ECE experiments.
5. Optimization Engine: SciPy-powered parameter solver.
6. Report Exporter: Export data and create comprehensive engineering reports.

## Testing
```
python test_suite.py
```
The automated test suite runs 19 critical mathematical verifications:
1. test_waveform_generation
2. test_nco_phase_continuity
3. test_am_modulation_and_efficiency
4. test_fm_carson_bandwidth
5. test_channel_awgn_snr
6. test_demodulation_reconstruction_am
7. test_demodulation_reconstruction_fm
8. test_waveform_phase_continuity
9. test_waveform_nyquist_validation
10. test_waveform_types
11. test_am_overmodulation_envelope
12. test_am_dsb_sc_mode
13. test_fm_carrier_reference_clean
14. test_fm_demod_block_continuity
15. test_am_measured_modulation_index
16. test_spectrum_peak_frequency
17. test_spectrum_bandwidth
18. test_channel_interference
19. test_signal_quality_diagnostics

## File Structure

| File | Lines | Description |
|------|-------|-------------|
| main.py | 344 | Application entry point and launcher menu |
| dashboard.py | 1439 | Primary ECE workbench and GUI definitions |
| run.py | 391 | Main execution script and initialization |
| simulation_engine.py | 140 | Core signal processing pipeline state machine |
| modulator.py | 185 | AM (DSB-FC/SC/SSB) and FM modulators |
| demodulator.py | 235 | Envelope, Diode RC, Coherent, Phase Discriminator |
| channel.py | 162 | AWGN, Attenuation, Interference models |
| spectrum.py | 162 | FFT, Windowing, OBW processing |
| measurements.py | 208 | Metric calculation and theoretical evaluations |
| experiments.py | 660 | 13 pre-defined automated ECE experiments |
| waveforms.py | 83 | Fundamental wave shapes generation |
| signal_sources.py | 307 | Live sources, WAV processing, Tone generation |
| nco.py | 48 | Numerically Controlled Oscillator phase tracking |
| sweep_engine.py | 161 | Multi-variable performance sweep tool |
| optimizer.py | 137 | SciPy constraint-based parameter solver |
| exporter.py | 235 | Data serialization and HTML reporting |
| test_suite.py | 343 | Comprehensive automated testing framework |
| update.py | 94 | Helper utility script |

## Results & Validation
- 19/19 automated tests pass
- AM efficiency validated: eta = m^2/(2+m^2) * 100%
- FM Carson BW validated within 5%
- Channel AWGN SNR calibration within 0.1 dB
- AM/FM demodulation correlation > 0.99

## Known Limitations
- Simulation only (no hardware)
- Single-tone analysis primary
- SSB uses block Hilbert (edge artifacts)
- Real-time limited to display resolution

## Future Work
- SDR hardware integration (clean adapter interfaces exist)
- Multi-tone/wideband message analysis
- Digital modulation (ASK, FSK, PSK, QAM)
- Real-time audio playback
- Network-based remote laboratory

## Dependencies
- numpy>=1.24.0
- scipy>=1.10.0
- pyqtgraph>=0.14.0
- pyqt6>=6.5.0
- sounddevice>=0.4.6
- librosa>=0.10.0
- soundfile>=0.12.0
- matplotlib>=3.7.0

## License
MIT License
" />
