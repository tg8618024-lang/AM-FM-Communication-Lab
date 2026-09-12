// AM FM PRO - Browser DSP Engine v2.0
// Pure JavaScript implementation of communication systems + hardware SNR math.
// No external dependencies.

const DSP = (() => {
  const TWO_PI = 2 * Math.PI;
  const K_BOLTZMANN = 1.38064852e-23;  // Boltzmann constant (J/K)
  const T0 = 290;                       // Standard noise temperature (K)
  const C = 3e8;                        // Speed of light (m/s)

  // ==================== SIGNAL GENERATION ====================

  function generateSine(freq, amp, phase, nSamples, sr) {
    // s(t) = A * cos(2*pi*f*t + phi)
    const out = new Float32Array(nSamples);
    for (let i = 0; i < nSamples; i++) {
      out[i] = amp * Math.cos(TWO_PI * freq * i / sr + phase);
    }
    return out;
  }

  function generateSquare(freq, amp, phase, nSamples, sr) {
    const out = new Float32Array(nSamples);
    for (let i = 0; i < nSamples; i++) {
      const t = i / sr;
      out[i] = amp * Math.sign(Math.sin(TWO_PI * freq * t + phase));
    }
    return out;
  }

  function generateTriangle(freq, amp, phase, nSamples, sr) {
    // Triangle: 2*A/pi * arcsin(sin(2*pi*f*t + phi))
    const out = new Float32Array(nSamples);
    for (let i = 0; i < nSamples; i++) {
      const t = i / sr;
      out[i] = amp * (2 / Math.PI) * Math.asin(Math.sin(TWO_PI * freq * t + phase));
    }
    return out;
  }

  function generateSawtooth(freq, amp, phase, nSamples, sr) {
    // Sawtooth: 2*A * (t*f - floor(t*f + 0.5))
    const out = new Float32Array(nSamples);
    for (let i = 0; i < nSamples; i++) {
      const t = i / sr;
      const p = freq * t + phase / TWO_PI;
      out[i] = amp * 2 * (p - Math.floor(p + 0.5));
    }
    return out;
  }

  function generateWaveform(type, freq, amp, phase, nSamples, sr) {
    switch (type) {
      case 'square': return generateSquare(freq, amp, phase, nSamples, sr);
      case 'triangle': return generateTriangle(freq, amp, phase, nSamples, sr);
      case 'sawtooth': return generateSawtooth(freq, amp, phase, nSamples, sr);
      default: return generateSine(freq, amp, phase, nSamples, sr);
    }
  }

  // ==================== AM MODULATION ====================

  function amModulate(msg, fc, ac, m, sr) {
    // s_AM(t) = Ac * [1 + m*x(t)] * cos(2*pi*fc*t)
    const n = msg.length;
    const signal = new Float32Array(n);
    const carrier = new Float32Array(n);
    const envelope = new Float32Array(n);

    for (let i = 0; i < n; i++) {
      const t = i / sr;
      const car = Math.cos(TWO_PI * fc * t);
      carrier[i] = ac * car;
      const envRaw = ac * (1 + m * msg[i]);
      envelope[i] = Math.abs(envRaw);  // True envelope magnitude
      signal[i] = envRaw * car;
    }

    // Theoretical power calculations
    const pc = ac * ac / 2;              // Carrier power
    const psb = pc * m * m / 2;          // Sideband power (for sinusoidal message)
    const pt = pc * (1 + m * m / 2);     // Total AM power
    const efficiency = (m * m / (2 + m * m)) * 100;  // Power efficiency %
    const isOvermod = m > 1.0;
    const bw = 2 * sr;  // Placeholder; actual BW = 2*fm

    return {
      signal, carrier, envelope,
      meta: { fc, m, pc, psb, pt, efficiency, isOvermod }
    };
  }

  // ==================== FM MODULATION ====================

  function fmModulate(msg, fc, ac, deltaF, fm, sr) {
    // s_FM(t) = Ac * cos(2*pi*fc*t + 2*pi*deltaF * integral(x(t)))
    const n = msg.length;
    const signal = new Float32Array(n);
    const carrier = new Float32Array(n);
    const instFreq = new Float32Array(n);

    let phaseAcc = 0;
    const dt = 1 / sr;

    for (let i = 0; i < n; i++) {
      const t = i / sr;
      carrier[i] = ac * Math.cos(TWO_PI * fc * t);

      const fInst = fc + deltaF * msg[i];
      instFreq[i] = fInst;
      phaseAcc += TWO_PI * fInst * dt;
      signal[i] = ac * Math.cos(phaseAcc);
    }

    const beta = deltaF / Math.max(fm, 1);
    const carsonBW = 2 * (deltaF + fm);
    const pt = ac * ac / 2;
    const isNBFM = beta <= 1;

    return {
      signal, carrier, instFreq,
      meta: { fc, deltaF, beta, carsonBW, pt, isNBFM }
    };
  }

  // ==================== CHANNEL (AWGN) with Full Power Analysis ====================

  function addAWGN(signal, snrDb) {
    const n = signal.length;
    const out = new Float32Array(n);
    const noiseArr = new Float32Array(n);

    // Measure input (Tx) signal power
    let pSig = 0;
    for (let i = 0; i < n; i++) pSig += signal[i] * signal[i];
    pSig /= n;

    // Target noise power from SNR
    const pNoiseTarget = pSig / Math.pow(10, snrDb / 10);
    const sigma = Math.sqrt(Math.max(pNoiseTarget, 1e-20));

    // Box-Muller Gaussian noise generation
    for (let i = 0; i < n; i++) {
      const u1 = Math.random() || 1e-10;
      const u2 = Math.random();
      noiseArr[i] = sigma * Math.sqrt(-2 * Math.log(u1)) * Math.cos(TWO_PI * u2);
      out[i] = signal[i] + noiseArr[i];
    }

    // Measure actual noise power
    let pNoiseActual = 0;
    for (let i = 0; i < n; i++) pNoiseActual += noiseArr[i] * noiseArr[i];
    pNoiseActual /= n;

    // Measure received (Rx) power (signal + noise)
    let pRx = 0;
    for (let i = 0; i < n; i++) pRx += out[i] * out[i];
    pRx /= n;

    // Convert to dB scale
    const measuredSnr = 10 * Math.log10(pSig / (pNoiseActual + 1e-30));
    const pSigDb = 10 * Math.log10(pSig + 1e-30);
    const pNoiseDb = 10 * Math.log10(pNoiseActual + 1e-30);
    const pRxDb = 10 * Math.log10(pRx + 1e-30);

    return {
      signal: out,
      noise: noiseArr,
      meta: {
        snrDb,
        measuredSnr,
        pSig,
        pNoise: pNoiseActual,
        pRx,
        pSigDb,
        pNoiseDb,
        pRxDb,
        noiseFloorDb: pNoiseDb
      }
    };
  }

  // ==================== HARDWARE SNR: LINK BUDGET ====================

  /**
   * Free-Space Path Loss (FSPL)
   * FSPL(dB) = 20*log10(d) + 20*log10(f) + 20*log10(4*pi/c)
   * @param {number} distKm - distance in kilometers
   * @param {number} freqHz - carrier frequency in Hz
   * @returns {number} path loss in dB (positive number)
   */
  function freeSpacePathLoss(distKm, freqHz) {
    if (distKm <= 0 || freqHz <= 0) return 0;
    const d = distKm * 1000; // Convert to meters
    const fspl = 20 * Math.log10(d) + 20 * Math.log10(freqHz) +
                 20 * Math.log10(4 * Math.PI / C);
    return Math.max(fspl, 0);
  }

  /**
   * Thermal Noise Power
   * N = k * T * B  (in Watts)
   * N(dBW) = 10*log10(k*T*B) = -228.6 + 10*log10(T) + 10*log10(B)
   * @param {number} bwHz - receiver bandwidth in Hz
   * @param {number} tempK - noise temperature (default 290K)
   * @returns {{ linear: number, dB: number }}
   */
  function thermalNoisePower(bwHz, tempK) {
    const t = tempK || T0;
    const nLinear = K_BOLTZMANN * t * bwHz;
    const nDb = 10 * Math.log10(nLinear + 1e-30);
    return { linear: nLinear, dB: nDb };
  }

  /**
   * Complete Link Budget Calculation
   * @param {number} txPowerDbw - transmitter power in dBW
   * @param {number} distKm - distance in km
   * @param {number} freqHz - carrier frequency in Hz
   * @param {number} noiseFigureDb - receiver noise figure in dB
   * @param {number} bwHz - receiver bandwidth in Hz
   * @returns {object} link budget parameters
   */
  function linkBudget(txPowerDbw, distKm, freqHz, noiseFigureDb, bwHz) {
    const fspl = freeSpacePathLoss(distKm, freqHz);
    const rxPowerDbw = txPowerDbw - fspl;

    const kTB = thermalNoisePower(bwHz);
    const totalNoiseDbw = kTB.dB + noiseFigureDb;
    const snrIn = rxPowerDbw - totalNoiseDbw;

    return {
      txPowerDbw,
      fsplDb: fspl,
      rxPowerDbw,
      kTBDbw: kTB.dB,
      noiseFigureDb,
      totalNoiseDbw,
      snrIn  // Input SNR before demodulation
    };
  }

  /**
   * FM SNR Improvement Factor
   * For WBFM: SNR_out / SNR_in = 3 * beta^2 * (beta + 1)
   * This is the FM advantage over AM at the same input SNR.
   * Valid above FM threshold (SNR_in > ~10 dB).
   * @param {number} beta - modulation index
   * @param {number} snrInDb - input SNR in dB
   * @returns {{ gainDb: number, snrOutDb: number, aboveThreshold: boolean }}
   */
  function fmImprovementFactor(beta, snrInDb) {
    const gainLinear = 3 * beta * beta * (beta + 1);
    const gainDb = 10 * Math.log10(gainLinear + 1e-15);
    const snrOutDb = snrInDb + gainDb;
    // FM threshold is approximately 10 dB input SNR
    const aboveThreshold = snrInDb >= 10;
    return { gainDb, snrOutDb, aboveThreshold };
  }

  /**
   * AM SNR output
   * For DSB-FC: SNR_out = (m^2 / (2 + m^2)) * SNR_in
   * @param {number} m - modulation index
   * @param {number} snrInDb - input SNR in dB
   * @returns {{ gainDb: number, snrOutDb: number }}
   */
  function amOutputSNR(m, snrInDb) {
    const factor = (m * m) / (2 + m * m);
    const gainDb = 10 * Math.log10(factor + 1e-15);
    const snrOutDb = snrInDb + gainDb;
    return { gainDb, snrOutDb };
  }

  // ==================== SIGNAL POWER MEASUREMENT ====================

  function measurePower(signal) {
    if (!signal || signal.length === 0) return { linear: 0, dB: -Infinity };
    let p = 0;
    for (let i = 0; i < signal.length; i++) p += signal[i] * signal[i];
    p /= signal.length;
    return { linear: p, dB: 10 * Math.log10(p + 1e-30) };
  }

  // ==================== DEMODULATION ====================

  function amDemodulate(amSignal, sr, fmMax) {
    // Envelope detector via Hilbert transform
    const n = amSignal.length;
    const analytic = hilbertTransform(amSignal);
    const envelope = new Float32Array(n);

    for (let i = 0; i < n; i++) {
      envelope[i] = Math.sqrt(
        analytic.real[i] * analytic.real[i] +
        analytic.imag[i] * analytic.imag[i]
      );
    }

    // Remove DC (carrier component)
    let mean = 0;
    for (let i = 0; i < n; i++) mean += envelope[i];
    mean /= n;

    const recovered = new Float32Array(n);
    for (let i = 0; i < n; i++) recovered[i] = envelope[i] - mean;

    // Normalize to unit RMS
    let rms = 0;
    for (let i = 0; i < n; i++) rms += recovered[i] * recovered[i];
    rms = Math.sqrt(rms / n);
    if (rms > 1e-10) {
      for (let i = 0; i < n; i++) recovered[i] /= (rms * Math.sqrt(2));
    }

    return recovered;
  }

  function fmDemodulate(fmSignal, sr, fmMax) {
    // FM demodulation via instantaneous frequency (phase derivative)
    const n = fmSignal.length;
    const analytic = hilbertTransform(fmSignal);
    const phase = new Float32Array(n);

    // Compute instantaneous phase
    for (let i = 0; i < n; i++) {
      phase[i] = Math.atan2(analytic.imag[i], analytic.real[i]);
    }

    // Phase unwrapping (cumulative, no mod 2pi)
    for (let i = 1; i < n; i++) {
      let diff = phase[i] - phase[i - 1];
      while (diff > Math.PI) diff -= TWO_PI;
      while (diff < -Math.PI) diff += TWO_PI;
      phase[i] = phase[i - 1] + diff;
    }

    // Differentiate for instantaneous frequency
    const instFreq = new Float32Array(n);
    for (let i = 1; i < n; i++) {
      instFreq[i] = (phase[i] - phase[i - 1]) * sr / TWO_PI;
    }
    instFreq[0] = instFreq[1];

    // Remove DC (carrier frequency)
    let mean = 0;
    for (let i = 0; i < n; i++) mean += instFreq[i];
    mean /= n;

    const recovered = new Float32Array(n);
    for (let i = 0; i < n; i++) recovered[i] = instFreq[i] - mean;

    // Normalize
    let rms = 0;
    for (let i = 0; i < n; i++) rms += recovered[i] * recovered[i];
    rms = Math.sqrt(rms / n);
    if (rms > 1e-10) {
      for (let i = 0; i < n; i++) recovered[i] /= (rms * Math.sqrt(2));
    }

    return recovered;
  }

  // ==================== FFT (Radix-2 Cooley-Tukey) ====================

  function fft(real, imag) {
    const n = real.length;
    if (n <= 1) return;

    // Bit-reversal permutation
    let j = 0;
    for (let i = 1; i < n; i++) {
      let bit = n >> 1;
      while (j & bit) { j ^= bit; bit >>= 1; }
      j ^= bit;
      if (i < j) {
        [real[i], real[j]] = [real[j], real[i]];
        [imag[i], imag[j]] = [imag[j], imag[i]];
      }
    }

    // Butterfly stages
    for (let len = 2; len <= n; len *= 2) {
      const halfLen = len / 2;
      const angle = -TWO_PI / len;
      const wReal = Math.cos(angle);
      const wImag = Math.sin(angle);

      for (let i = 0; i < n; i += len) {
        let curReal = 1, curImag = 0;
        for (let k = 0; k < halfLen; k++) {
          const tReal = curReal * real[i + k + halfLen] - curImag * imag[i + k + halfLen];
          const tImag = curReal * imag[i + k + halfLen] + curImag * real[i + k + halfLen];

          real[i + k + halfLen] = real[i + k] - tReal;
          imag[i + k + halfLen] = imag[i + k] - tImag;
          real[i + k] += tReal;
          imag[i + k] += tImag;

          const newCurReal = curReal * wReal - curImag * wImag;
          curImag = curReal * wImag + curImag * wReal;
          curReal = newCurReal;
        }
      }
    }
  }

  function hilbertTransform(signal) {
    // FFT-based Hilbert transform for analytic signal
    let n = signal.length;
    let nfft = 1;
    while (nfft < n) nfft *= 2;

    const real = new Float64Array(nfft);
    const imag = new Float64Array(nfft);
    for (let i = 0; i < n; i++) real[i] = signal[i];

    fft(real, imag);

    // Zero negative frequencies, double positive
    for (let i = 1; i < nfft / 2; i++) {
      real[i] *= 2;
      imag[i] *= 2;
    }
    for (let i = nfft / 2 + 1; i < nfft; i++) {
      real[i] = 0;
      imag[i] = 0;
    }

    // Inverse FFT via conjugate trick
    for (let i = 0; i < nfft; i++) imag[i] = -imag[i];
    fft(real, imag);
    for (let i = 0; i < nfft; i++) {
      real[i] /= nfft;
      imag[i] = -imag[i] / nfft;
    }

    return {
      real: real.slice(0, n),
      imag: imag.slice(0, n)
    };
  }

  function computeSpectrum(signal, sr) {
    // Magnitude spectrum with Hanning window, in dB
    let n = signal.length;
    let nfft = 1;
    while (nfft < n) nfft *= 2;
    if (nfft < 4096) nfft = 4096;

    const real = new Float64Array(nfft);
    const imag = new Float64Array(nfft);

    // Apply Hanning window
    for (let i = 0; i < n; i++) {
      const w = 0.5 * (1 - Math.cos(TWO_PI * i / (n - 1)));
      real[i] = signal[i] * w;
    }

    fft(real, imag);

    // One-sided magnitude spectrum
    const nBins = nfft / 2 + 1;
    const freqs = new Float32Array(nBins);
    const magnitudes = new Float32Array(nBins);
    const df = sr / nfft;

    for (let i = 0; i < nBins; i++) {
      freqs[i] = i * df;
      const mag = Math.sqrt(real[i] * real[i] + imag[i] * imag[i]) / n;
      magnitudes[i] = 20 * Math.log10(mag + 1e-12);
    }

    return { freqs, magnitudes, nfft };
  }

  // ==================== METRICS ====================

  function computeMetrics(original, recovered) {
    const n = Math.min(original.length, recovered.length);

    // Compute RMS of both signals
    let rmsOrig = 0, rmsRec = 0;
    for (let i = 0; i < n; i++) {
      rmsOrig += original[i] * original[i];
      rmsRec += recovered[i] * recovered[i];
    }
    rmsOrig = Math.sqrt(rmsOrig / n);
    rmsRec = Math.sqrt(rmsRec / n);

    if (rmsOrig < 1e-10 || rmsRec < 1e-10) {
      return { mse: 1, rmse: 1, correlation: 0, psnr: 0, errorPct: 100 };
    }

    // Normalize to unit RMS
    const normOrig = new Float32Array(n);
    const normRec = new Float32Array(n);
    for (let i = 0; i < n; i++) {
      normOrig[i] = original[i] / rmsOrig;
      normRec[i] = recovered[i] / rmsRec;
    }

    // Cross-correlation search for best alignment (+/- maxLag samples)
    let bestCorr = -1;
    let bestLag = 0;
    const maxLag = Math.min(100, Math.floor(n / 4));

    for (let lag = -maxLag; lag <= maxLag; lag++) {
      let sum = 0, count = 0;
      for (let i = 0; i < n; i++) {
        const j = i + lag;
        if (j >= 0 && j < n) {
          sum += normOrig[i] * normRec[j];
          count++;
        }
      }
      const corr = Math.abs(sum / count);
      if (corr > bestCorr) { bestCorr = corr; bestLag = lag; }
    }

    // MSE with best alignment
    let mse = 0, count = 0;
    for (let i = 0; i < n; i++) {
      const j = i + bestLag;
      if (j >= 0 && j < n) {
        const diff = normOrig[i] - normRec[j];
        mse += diff * diff;
        count++;
      }
    }
    mse /= count;

    const rmse = Math.sqrt(mse);
    const psnr = mse > 0 ? 10 * Math.log10(1 / mse) : 60;
    const errorPct = rmse * 100;

    return { mse, rmse, correlation: bestCorr, psnr, errorPct };
  }

  // ==================== PUBLIC API ====================

  return {
    // Signal generation
    generateWaveform, generateSine, generateSquare, generateTriangle, generateSawtooth,
    // Modulation
    amModulate, fmModulate,
    // Channel
    addAWGN,
    // Demodulation
    amDemodulate, fmDemodulate,
    // Analysis
    computeSpectrum, computeMetrics, measurePower,
    // Hardware SNR
    freeSpacePathLoss, thermalNoisePower, linkBudget,
    fmImprovementFactor, amOutputSNR,
    // Constants
    K_BOLTZMANN, T0, C
  };
})();
