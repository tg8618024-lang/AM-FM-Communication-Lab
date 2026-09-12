// AM FM PRO - Simulator Application v3.0
// Controller: connects UI controls to DSP engine and Canvas renderer.
// Includes:
// - Hardware SNR link budget, FM improvement factor, visual noise floor
// - Audio File Input (WAV/MP3 upload & decode)
// - Live Microphone Input (getUserMedia stream)
// - Audio Monitor Speaker (Listen to Message, AM Demod, FM Demod)
// - AM Modulation Modes (DSB-FC Standard vs DSB-SC Suppressed Carrier)

document.addEventListener('DOMContentLoaded', () => {
  // ==================== CONSTANTS ====================
  const SR = 44100;
  const DISPLAY_DURATION = 0.005;  // 5ms display window
  const N_SAMPLES = 4096;          // DSP block size
  const N_DISPLAY = Math.floor(SR * DISPLAY_DURATION);

  // ==================== STATE ====================
  let state = {
    msgType: 'sine',
    fm: 1000, am: 1.0,
    fc: 10000, ac: 1.0,
    m: 0.80, deltaF: 4000,
    amMode: 'DSB-FC',
    snr: 25,
    amEnabled: true, fmEnabled: true,
    noiseEnabled: false,
    // Hardware SNR parameters
    txPower: 0,       // dBW
    distance: 1.0,    // km
    noiseFigure: 6,   // dB
    rxBandwidth: 10,  // kHz
    running: true
  };

  // Audio buffers & streaming state
  let audioFileBuffer = null;      // Float32Array from uploaded file
  let audioFileOffset = 0;
  let micActive = false;
  let micStream = null;
  let micBuffer = new Float32Array(N_SAMPLES);
  let micProcessorNode = null;

  // Cached signals for audio speaker playback
  let lastMsg = new Float32Array(N_SAMPLES);
  let lastAmRec = new Float32Array(N_SAMPLES);
  let lastFmRec = new Float32Array(N_SAMPLES);

  // Web Audio Context for playback & decoding
  let audioCtx = null;
  let currentSourceNode = null;

  function getAudioContext() {
    if (!audioCtx) {
      audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    }
    if (audioCtx.state === 'suspended') {
      audioCtx.resume();
    }
    return audioCtx;
  }

  // ==================== DOM REFERENCES ====================
  const canvases = {
    message:  document.getElementById('scope-msg'),
    carrier:  document.getElementById('scope-carrier'),
    amMod:    document.getElementById('scope-am'),
    fmMod:    document.getElementById('scope-fm'),
    amDemod:  document.getElementById('scope-am-demod'),
    fmDemod:  document.getElementById('scope-fm-demod'),
    specAm:   document.getElementById('spec-am'),
    specFm:   document.getElementById('spec-fm'),
  };

  // ==================== AUDIO FILE INPUT ====================
  const fileInput = document.getElementById('audio-file-input');
  const btnChooseFile = document.getElementById('btn-choose-file');
  const audioFileName = document.getElementById('audio-file-name');
  const audioFileControls = document.getElementById('audio-file-controls');

  if (btnChooseFile && fileInput) {
    btnChooseFile.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', async (e) => {
      const file = e.target.files[0];
      if (!file) return;

      if (audioFileName) audioFileName.textContent = `Loading ${file.name}...`;

      try {
        const arrayBuf = await file.arrayBuffer();
        const ctx = getAudioContext();
        const audioBuf = await ctx.decodeAudioData(arrayBuf);
        // Extract first channel as Float32Array
        audioFileBuffer = audioBuf.getChannelData(0);
        audioFileOffset = 0;
        if (audioFileName) audioFileName.textContent = `Loaded: ${file.name} (${audioBuf.duration.toFixed(1)}s)`;
        computeAndRender();
      } catch (err) {
        console.error('Failed to decode audio file:', err);
        if (audioFileName) audioFileName.textContent = 'Error decoding audio file';
      }
    });
  }

  // ==================== LIVE MICROPHONE INPUT ====================
  const micControls = document.getElementById('mic-controls');
  const btnToggleMic = document.getElementById('btn-toggle-mic');
  const micStatus = document.getElementById('mic-status');

  async function startMic() {
    try {
      const ctx = getAudioContext();
      micStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
      const micSource = ctx.createMediaStreamSource(micStream);

      // Buffer audio samples
      micProcessorNode = ctx.createScriptProcessor(4096, 1, 1);
      micProcessorNode.onaudioprocess = (evt) => {
        if (!micActive) return;
        const inputData = evt.inputBuffer.getChannelData(0);
        micBuffer.set(inputData);
        computeAndRender();
      };

      micSource.connect(micProcessorNode);
      micProcessorNode.connect(ctx.destination);

      micActive = true;
      if (btnToggleMic) {
        btnToggleMic.textContent = '⏹ Stop Microphone';
        btnToggleMic.className = 'btn btn-primary btn-sm';
      }
      if (micStatus) micStatus.textContent = 'Mic: Streaming LIVE 🎙';
      computeAndRender();
    } catch (err) {
      console.error('Microphone access denied:', err);
      if (micStatus) micStatus.textContent = 'Mic permission denied';
      micActive = false;
    }
  }

  function stopMic() {
    micActive = false;
    if (micStream) {
      micStream.getTracks().forEach(t => t.stop());
      micStream = null;
    }
    if (micProcessorNode) {
      micProcessorNode.disconnect();
      micProcessorNode = null;
    }
    if (btnToggleMic) {
      btnToggleMic.textContent = '🎤 Start Microphone';
      btnToggleMic.className = 'btn btn-secondary btn-sm';
    }
    if (micStatus) micStatus.textContent = 'Mic: Inactive';
  }

  if (btnToggleMic) {
    btnToggleMic.addEventListener('click', () => {
      if (micActive) stopMic();
      else startMic();
    });
  }

  // ==================== AUDIO SPEAKER PLAYBACK ====================
  const audioStatus = document.getElementById('audio-status');
  const btnPlayMsg = document.getElementById('btn-play-msg');
  const btnPlayAm = document.getElementById('btn-play-am');
  const btnPlayFm = document.getElementById('btn-play-fm');
  const btnStopAudio = document.getElementById('btn-stop-audio');

  function stopSpeaker() {
    if (currentSourceNode) {
      try { currentSourceNode.stop(); } catch(e) {}
      currentSourceNode = null;
    }
    if (audioStatus) audioStatus.textContent = 'Speaker: Idle';
  }

  function playSignal(samples, label) {
    stopSpeaker();
    if (!samples || samples.length === 0) return;

    try {
      const ctx = getAudioContext();
      // Repeat/extend to at least 2 seconds if too short for a pleasant loop
      let playLen = samples.length;
      let repeatCount = 1;
      if (playLen < SR * 2) {
        repeatCount = Math.ceil((SR * 2) / playLen);
      }

      const buffer = ctx.createBuffer(1, playLen * repeatCount, SR);
      const out = buffer.getChannelData(0);

      // Measure max amplitude for safe normalization
      let maxAbs = 0;
      for (let i = 0; i < samples.length; i++) {
        const a = Math.abs(samples[i]);
        if (a > maxAbs) maxAbs = a;
      }
      const gain = maxAbs > 1e-5 ? 0.85 / maxAbs : 1.0;

      for (let r = 0; r < repeatCount; r++) {
        const offset = r * playLen;
        for (let i = 0; i < playLen; i++) {
          out[offset + i] = samples[i] * gain;
        }
      }

      const src = ctx.createBufferSource();
      src.buffer = buffer;
      src.loop = true;
      src.connect(ctx.destination);
      src.start(0);
      currentSourceNode = src;

      if (audioStatus) {
        audioStatus.textContent = `Playing: ${label} (Looping 🔊)`;
        audioStatus.style.color = 'var(--color-green)';
      }
    } catch (err) {
      console.error('Audio playback error:', err);
      if (audioStatus) audioStatus.textContent = 'Speaker: Playback error';
    }
  }

  if (btnPlayMsg) btnPlayMsg.addEventListener('click', () => playSignal(lastMsg, 'Message'));
  if (btnPlayAm) btnPlayAm.addEventListener('click', () => playSignal(lastAmRec, 'AM Demodulated'));
  if (btnPlayFm) btnPlayFm.addEventListener('click', () => playSignal(lastFmRec, 'FM Demodulated'));
  if (btnStopAudio) btnStopAudio.addEventListener('click', stopSpeaker);

  // ==================== MAIN COMPUTE + RENDER ====================

  function computeAndRender() {
    // 1. Generate or fetch message signal
    let msg = null;

    if (state.msgType === 'audio-file' && audioFileBuffer && audioFileBuffer.length > 0) {
      msg = new Float32Array(N_SAMPLES);
      for (let i = 0; i < N_SAMPLES; i++) {
        const idx = (audioFileOffset + i) % audioFileBuffer.length;
        msg[i] = audioFileBuffer[idx] * state.am;
      }
      audioFileOffset = (audioFileOffset + N_SAMPLES) % audioFileBuffer.length;
    } else if (state.msgType === 'mic' && micActive) {
      msg = new Float32Array(N_SAMPLES);
      for (let i = 0; i < N_SAMPLES; i++) {
        msg[i] = micBuffer[i] * state.am * 3.0; // Boost mic level
      }
    } else {
      msg = DSP.generateWaveform(state.msgType, state.fm, state.am, 0, N_SAMPLES, SR);
    }

    lastMsg.set(msg);

    // 2. Generate carrier
    const carrier = DSP.generateSine(state.fc, state.ac, 0, N_DISPLAY, SR);
    const fullCarrier = DSP.generateSine(state.fc, state.ac, 0, N_SAMPLES, SR);

    // 3. Compute link budget (hardware SNR)
    let lb = null;
    if (state.noiseEnabled) {
      lb = DSP.linkBudget(
        state.txPower,
        state.distance,
        state.fc,
        state.noiseFigure,
        state.rxBandwidth * 1000  // Convert kHz to Hz
      );
    }

    // 4. AM pipeline
    let amResult = null, amChan = null, amRec = null, amSpec = null, amMetrics = null;
    if (state.amEnabled) {
      amResult = DSP.amModulate(msg, state.fc, state.ac, state.m, SR, state.amMode);

      if (state.noiseEnabled) {
        amChan = DSP.addAWGN(amResult.signal, state.snr);
      } else {
        amChan = {
          signal: amResult.signal, noise: null,
          meta: { snrDb: Infinity, measuredSnr: Infinity, pSig: 0, pNoise: 0, pRx: 0,
                  pSigDb: -Infinity, pNoiseDb: -Infinity, pRxDb: -Infinity, noiseFloorDb: null }
        };
      }

      amRec = DSP.amDemodulate(amChan.signal, SR, state.fm * 1.5, fullCarrier, state.amMode);
      lastAmRec.set(amRec);
      amSpec = DSP.computeSpectrum(amChan.signal, SR);
      amMetrics = DSP.computeMetrics(msg, amRec);
    }

    // 5. FM pipeline
    let fmResult = null, fmChan = null, fmRec = null, fmSpec = null, fmMetrics = null;
    if (state.fmEnabled) {
      fmResult = DSP.fmModulate(msg, state.fc, state.ac, state.deltaF, state.fm, SR);

      if (state.noiseEnabled) {
        fmChan = DSP.addAWGN(fmResult.signal, state.snr);
      } else {
        fmChan = {
          signal: fmResult.signal, noise: null,
          meta: { snrDb: Infinity, measuredSnr: Infinity, pSig: 0, pNoise: 0, pRx: 0,
                  pSigDb: -Infinity, pNoiseDb: -Infinity, pRxDb: -Infinity, noiseFloorDb: null }
        };
      }

      fmRec = DSP.fmDemodulate(fmChan.signal, SR, state.fm * 1.5);
      lastFmRec.set(fmRec);
      fmSpec = DSP.computeSpectrum(fmChan.signal, SR);
      fmMetrics = DSP.computeMetrics(msg, fmRec);
    }

    // 6. Render waveforms
    Renderer.drawWaveform(canvases.message, msg.slice(0, N_DISPLAY), Renderer.COLORS.cyan, `MESSAGE (${state.msgType.toUpperCase()})`, 'V');
    Renderer.drawWaveform(canvases.carrier, carrier, Renderer.COLORS.green, 'CARRIER NCO', 'V');

    if (state.amEnabled && amResult) {
      const amLabel = state.amMode === 'DSB-SC' ? 'AM MODULATED (DSB-SC)' : 'AM MODULATED (DSB-FC)';
      Renderer.drawWaveform(canvases.amMod, amResult.signal.slice(0, N_DISPLAY), Renderer.COLORS.gold, amLabel, 'V');
      Renderer.drawWaveform(canvases.amDemod, amRec.slice(0, N_DISPLAY), Renderer.COLORS.pink, 'AM DEMODULATED', 'V');
      const amNF = (state.noiseEnabled && amChan.meta) ? amChan.meta.noiseFloorDb : null;
      Renderer.drawSpectrum(canvases.specAm, amSpec.freqs, amSpec.magnitudes, Renderer.COLORS.orange, 'AM SPECTRUM', state.fc * 2.5, amNF);
    } else {
      Renderer.drawWaveform(canvases.amMod, null, Renderer.COLORS.gold, 'AM MODULATED [OFF]', 'V');
      Renderer.drawWaveform(canvases.amDemod, null, Renderer.COLORS.pink, 'AM DEMODULATED [OFF]', 'V');
      Renderer.drawSpectrum(canvases.specAm, null, null, Renderer.COLORS.orange, 'AM SPECTRUM [OFF]', 20000);
    }

    if (state.fmEnabled && fmResult) {
      Renderer.drawWaveform(canvases.fmMod, fmResult.signal.slice(0, N_DISPLAY), Renderer.COLORS.purple, 'FM MODULATED', 'V');
      Renderer.drawWaveform(canvases.fmDemod, fmRec.slice(0, N_DISPLAY), Renderer.COLORS.green, 'FM DEMODULATED', 'V');
      const fmNF = (state.noiseEnabled && fmChan.meta) ? fmChan.meta.noiseFloorDb : null;
      Renderer.drawSpectrum(canvases.specFm, fmSpec.freqs, fmSpec.magnitudes, Renderer.COLORS.cyan, 'FM SPECTRUM', state.fc * 2.5, fmNF);
    } else {
      Renderer.drawWaveform(canvases.fmMod, null, Renderer.COLORS.purple, 'FM MODULATED [OFF]', 'V');
      Renderer.drawWaveform(canvases.fmDemod, null, Renderer.COLORS.green, 'FM DEMODULATED [OFF]', 'V');
      Renderer.drawSpectrum(canvases.specFm, null, null, Renderer.COLORS.cyan, 'FM SPECTRUM [OFF]', 20000);
    }

    // 7. Update all metric displays
    updateMetrics(amResult, fmResult, amMetrics, fmMetrics, amChan, fmChan);
    updateSNRBudget(amChan, fmChan);
    updateLinkBudget(lb);
  }

  // ==================== METRICS DISPLAY ====================

  function setText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
  }

  function updateMetrics(amResult, fmResult, amMetrics, fmMetrics, amChan, fmChan) {
    if (amResult && amResult.meta) {
      setText('met-am-m', state.m.toFixed(2));
      setText('met-am-eff', amResult.meta.efficiency.toFixed(1) + '%');
      setText('met-am-bw', (2 * state.fm).toFixed(0) + ' Hz');

      const statusEl = document.getElementById('met-am-status');
      if (statusEl) {
        statusEl.textContent = amResult.meta.isOvermod ? 'OVERMOD' : (state.amMode === 'DSB-SC' ? 'DSB-SC' : 'OK');
        statusEl.className = 'metric-value' + (amResult.meta.isOvermod ? ' danger' : '');
      }
      setText('met-am-corr', amMetrics ? amMetrics.correlation.toFixed(3) : '---');
    } else {
      setText('met-am-m', '---');
      setText('met-am-eff', '---');
      setText('met-am-bw', '---');
      setText('met-am-status', '---');
      setText('met-am-corr', '---');
    }

    if (fmResult && fmResult.meta) {
      setText('met-fm-beta', fmResult.meta.beta.toFixed(2));
      setText('met-fm-df', state.deltaF.toFixed(0) + ' Hz');
      setText('met-fm-bw', fmResult.meta.carsonBW.toFixed(0) + ' Hz');
      setText('met-fm-type', fmResult.meta.isNBFM ? 'NBFM' : 'WBFM');
      setText('met-fm-corr', fmMetrics ? fmMetrics.correlation.toFixed(3) : '---');
    } else {
      setText('met-fm-beta', '---');
      setText('met-fm-df', '---');
      setText('met-fm-bw', '---');
      setText('met-fm-type', '---');
      setText('met-fm-corr', '---');
    }

    setText('met-snr', state.noiseEnabled ? state.snr.toFixed(0) + ' dB' : 'OFF');
  }

  // ==================== SNR BUDGET DISPLAY ====================

  function updateSNRBudget(amChan, fmChan) {
    const budgetEl = document.getElementById('snr-budget');
    if (!budgetEl) return;

    if (!state.noiseEnabled) {
      budgetEl.classList.add('hidden');
      return;
    }
    budgetEl.classList.remove('hidden');

    const chan = (amChan && amChan.meta && amChan.meta.pSig > 0) ? amChan :
                (fmChan && fmChan.meta && fmChan.meta.pSig > 0) ? fmChan : null;

    if (chan && chan.meta) {
      const m = chan.meta;
      setText('snr-tx-power', m.pSigDb.toFixed(1) + ' dB');
      setText('snr-noise-power', m.pNoiseDb.toFixed(1) + ' dB');
      setText('snr-rx-power', m.pRxDb.toFixed(1) + ' dB');
      setText('snr-theoretical', m.snrDb.toFixed(1) + ' dB');
      setText('snr-measured', m.measuredSnr.toFixed(1) + ' dB');

      const delta = m.measuredSnr - m.snrDb;
      const deltaEl = document.getElementById('snr-delta');
      if (deltaEl) {
        deltaEl.textContent = (delta >= 0 ? '+' : '') + delta.toFixed(1) + ' dB';
        deltaEl.className = 'snr-comp-value ' + (Math.abs(delta) < 2 ? 'good' : 'poor');
      }

      const measEl = document.getElementById('snr-measured');
      if (measEl) {
        measEl.className = 'snr-comp-value ' + (m.measuredSnr >= m.snrDb - 2 ? 'good' : 'poor');
      }

      const beta = state.fmEnabled ? (state.deltaF / Math.max(state.fm, 1)) : 0;
      if (beta > 0) {
        const fmImprove = DSP.fmImprovementFactor(beta, state.snr);
        const fmGainEl = document.getElementById('snr-fm-gain');
        if (fmGainEl) {
          fmGainEl.textContent = '+' + fmImprove.gainDb.toFixed(1) + ' dB';
          fmGainEl.className = 'snr-comp-value fm-improve' +
            (fmImprove.aboveThreshold ? '' : ' poor');
        }
      } else {
        setText('snr-fm-gain', '---');
      }
    } else {
      setText('snr-tx-power', '---');
      setText('snr-noise-power', '---');
      setText('snr-rx-power', '---');
      setText('snr-theoretical', '---');
      setText('snr-measured', '---');
      setText('snr-delta', '---');
      setText('snr-fm-gain', '---');
    }
  }

  // ==================== LINK BUDGET DISPLAY ====================

  function updateLinkBudget(lb) {
    const lbEl = document.getElementById('link-budget');
    if (!lbEl) return;

    if (!state.noiseEnabled || !lb) {
      lbEl.classList.add('hidden');
      return;
    }
    lbEl.classList.remove('hidden');

    setText('lb-tx', lb.txPowerDbw.toFixed(1) + ' dBW');
    setText('lb-fspl', lb.fsplDb.toFixed(1) + ' dB');
    setText('lb-rx', lb.rxPowerDbw.toFixed(1) + ' dBW');
    setText('lb-ktb', lb.kTBDbw.toFixed(1) + ' dBW');
    setText('lb-nf', lb.noiseFigureDb.toFixed(0) + ' dB');
    setText('lb-ntotal', lb.totalNoiseDbw.toFixed(1) + ' dBW');

    const snrInEl = document.getElementById('lb-snr-in');
    if (snrInEl) {
      snrInEl.textContent = lb.snrIn.toFixed(1) + ' dB';
      snrInEl.style.color = lb.snrIn >= 10 ? 'var(--color-green)' :
                            lb.snrIn >= 0  ? 'var(--color-gold)' : 'var(--color-red)';
    }
  }

  // ==================== SLIDER & TOGGLE BINDINGS ====================

  function bindSlider(sliderId, valueId, stateKey, transform, formatter) {
    const slider = document.getElementById(sliderId);
    const valueEl = document.getElementById(valueId);
    if (!slider) return;

    slider.addEventListener('input', (e) => {
      const raw = parseFloat(e.target.value);
      const val = transform ? transform(raw) : raw;
      state[stateKey] = val;
      if (valueEl) {
        valueEl.textContent = formatter ? formatter(val) : (
          Number.isInteger(val) ? val.toString() : val.toFixed(2)
        );
      }
      computeAndRender();
    });
  }

  function bindToggle(toggleId, stateKey) {
    const toggle = document.getElementById(toggleId);
    if (!toggle) return;
    toggle.addEventListener('click', () => {
      state[stateKey] = !state[stateKey];
      toggle.classList.toggle('active', state[stateKey]);
      toggle.textContent = state[stateKey] ? 'ON' : 'OFF';
      computeAndRender();
    });
  }

  // Waveform type selector
  const msgTypeEl = document.getElementById('msg-type');
  if (msgTypeEl) {
    msgTypeEl.addEventListener('change', (e) => {
      state.msgType = e.target.value;

      // Conditional UI visibility
      if (audioFileControls) {
        audioFileControls.style.display = (state.msgType === 'audio-file') ? 'block' : 'none';
      }
      if (micControls) {
        micControls.style.display = (state.msgType === 'mic') ? 'block' : 'none';
      }
      if (state.msgType !== 'mic' && micActive) {
        stopMic();
      }

      computeAndRender();
    });
  }

  // AM Mode selector
  const amModeEl = document.getElementById('am-mode');
  if (amModeEl) {
    amModeEl.addEventListener('change', (e) => {
      state.amMode = e.target.value;
      computeAndRender();
    });
  }

  // Sliders
  bindSlider('slider-fm', 'val-fm', 'fm', null, v => v.toFixed(0));
  bindSlider('slider-am', 'val-am', 'am', v => v / 100, v => v.toFixed(2));
  bindSlider('slider-fc', 'val-fc', 'fc', null, v => v.toFixed(0));
  bindSlider('slider-ac', 'val-ac', 'ac', v => v / 100, v => v.toFixed(2));
  bindSlider('slider-m', 'val-m', 'm', v => v / 100, v => v.toFixed(2));
  bindSlider('slider-df', 'val-df', 'deltaF', null, v => v.toFixed(0));
  bindSlider('slider-snr', 'val-snr', 'snr', null, v => v.toFixed(0));
  bindSlider('slider-txpow', 'val-txpow', 'txPower', null, v => v.toFixed(0));
  bindSlider('slider-dist', 'val-dist', 'distance', null, v => v.toFixed(1));
  bindSlider('slider-nf', 'val-nf', 'noiseFigure', null, v => v.toFixed(0));
  bindSlider('slider-bw', 'val-bw', 'rxBandwidth', null, v => v.toFixed(0));

  // Toggles
  bindToggle('toggle-am', 'amEnabled');
  bindToggle('toggle-fm', 'fmEnabled');
  bindToggle('toggle-noise', 'noiseEnabled');

  // Reset All
  const resetBtn = document.getElementById('btn-reset');
  if (resetBtn) {
    resetBtn.addEventListener('click', () => {
      stopSpeaker();
      stopMic();

      state = {
        msgType: 'sine', fm: 1000, am: 1.0, fc: 10000, ac: 1.0,
        m: 0.80, deltaF: 4000, amMode: 'DSB-FC', snr: 25,
        amEnabled: true, fmEnabled: true, noiseEnabled: false,
        txPower: 0, distance: 1.0, noiseFigure: 6, rxBandwidth: 10,
        running: true
      };

      const setSlider = (id, val, textId, textVal) => {
        const el = document.getElementById(id);
        if (el) el.value = val;
        const tel = document.getElementById(textId);
        if (tel) tel.textContent = textVal;
      };

      if (msgTypeEl) msgTypeEl.value = 'sine';
      if (amModeEl) amModeEl.value = 'DSB-FC';
      if (audioFileControls) audioFileControls.style.display = 'none';
      if (micControls) micControls.style.display = 'none';

      setSlider('slider-fm', 1000, 'val-fm', '1000');
      setSlider('slider-am', 100, 'val-am', '1.00');
      setSlider('slider-fc', 10000, 'val-fc', '10000');
      setSlider('slider-ac', 100, 'val-ac', '1.00');
      setSlider('slider-m', 80, 'val-m', '0.80');
      setSlider('slider-df', 4000, 'val-df', '4000');
      setSlider('slider-snr', 25, 'val-snr', '25');
      setSlider('slider-txpow', 0, 'val-txpow', '0');
      setSlider('slider-dist', 1, 'val-dist', '1.0');
      setSlider('slider-nf', 6, 'val-nf', '6');
      setSlider('slider-bw', 10, 'val-bw', '10');

      const tAm = document.getElementById('toggle-am');
      if (tAm) { tAm.classList.add('active'); tAm.textContent = 'ON'; }
      const tFm = document.getElementById('toggle-fm');
      if (tFm) { tFm.classList.add('active'); tFm.textContent = 'ON'; }
      const tNoise = document.getElementById('toggle-noise');
      if (tNoise) { tNoise.classList.remove('active'); tNoise.textContent = 'OFF'; }

      computeAndRender();
    });
  }

  // Resize handler
  let resizeTimeout = null;
  window.addEventListener('resize', () => {
    if (resizeTimeout) clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(() => computeAndRender(), 100);
  });

  // Initial render
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      computeAndRender();
    });
  });
});
