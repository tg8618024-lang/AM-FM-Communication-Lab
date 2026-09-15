// AM FM PRO - Precision Simulator Controller v4.0
// Inspired by Keysight, Rohde & Schwarz, Tektronix test equipment.
// High-performance reactive state management, interactive cursors,
// presets, PNG capture, smart engineering insights, Web Audio API.
// Complete responsive shell, drawer/resizable panel, graph focus mode.

document.addEventListener('DOMContentLoaded', () => {
  // ==================== CONSTANTS ====================
  const SR = 44100;
  const DISPLAY_DURATION = 0.005;  // 5ms base calibrated oscilloscope window
  const N_SAMPLES = 4096;          // DSP buffer size

  // ==================== INSTRUMENT STATE ====================
  let state = {
    msgType: 'sine',
    fm: 1000, am: 1.0,
    fc: 10000, ac: 1.0,
    m: 0.80, deltaF: 4000,
    amMode: 'DSB-FC',
    snr: 25,
    amEnabled: true, fmEnabled: true,
    noiseEnabled: false,
    // Hardware RF link budget parameters
    txPower: 0,       // dBW
    distance: 1.0,    // km
    noiseFigure: 6,   // dB
    rxBandwidth: 10,  // kHz
    frozen: false,    // Freeze / Run waveform view
    // Display & Scope Settings
    timeScale: 1.0,   // 0.5x, 1x, 2x, 5x
    showGrid: true,   // Graticule grid visibility
    currentMode: 'all' // 'all', 'am', 'fm', 'channel', 'audio'
  };

  // Audio stream state
  let audioFileBuffer = null;
  let audioFileOffset = 0;
  let micActive = false;
  let micStream = null;
  let micBuffer = new Float32Array(N_SAMPLES);
  let micProcessorNode = null;

  // Cached signals for audio playback & inspection
  let lastMsg = new Float32Array(N_SAMPLES);
  let lastAmRec = new Float32Array(N_SAMPLES);
  let lastFmRec = new Float32Array(N_SAMPLES);

  // Audio Context
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
    specFm:   document.getElementById('spec-fm')
  };

  // Bind interactive cursor inspection to each canvas
  Object.values(canvases).forEach(canvas => {
    if (canvas) Renderer.bindCursor(canvas, () => computeAndRender(true));
  });

  // ==================== ACCORDION CONTROLS ====================
  const accordionHeaders = document.querySelectorAll('.accordion-header');
  accordionHeaders.forEach(header => {
    header.addEventListener('click', (e) => {
      e.preventDefault();
      const card = header.closest('.accordion-card');
      if (!card) return;
      const isCollapsed = card.classList.toggle('collapsed');
      header.setAttribute('aria-expanded', !isCollapsed);
      const arrow = header.querySelector('.accordion-arrow');
      if (arrow) arrow.textContent = isCollapsed ? '▶' : '▼';
    });
  });

  // ==================== RESIZABLE CONTROL PANEL (DESKTOP) ====================
  const resizer = document.getElementById('panel-resizer');
  const rack = document.getElementById('inst-rack');
  const instShell = document.querySelector('.inst-shell');

  if (resizer && rack) {
    let isResizing = false;

    // Restore saved width from localStorage
    const savedWidth = localStorage.getItem('am_fm_panel_width');
    if (savedWidth && window.innerWidth > 1024) {
      const w = Math.max(280, Math.min(480, parseInt(savedWidth, 10)));
      rack.style.width = `${w}px`;
    }

    resizer.addEventListener('mousedown', (e) => {
      if (window.innerWidth <= 1024) return;
      isResizing = true;
      resizer.classList.add('resizing');
      document.body.style.cursor = 'col-resize';
      document.body.style.userSelect = 'none';
    });

    window.addEventListener('mousemove', (e) => {
      if (!isResizing) return;
      const newWidth = Math.max(280, Math.min(480, e.clientX));
      rack.style.width = `${newWidth}px`;
      localStorage.setItem('am_fm_panel_width', newWidth);
    });

    window.addEventListener('mouseup', () => {
      if (isResizing) {
        isResizing = false;
        resizer.classList.remove('resizing');
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
        computeAndRender();
      }
    });
  }

  // ==================== DRAWER / COLLAPSE PANEL TOGGLE ====================
  const btnToggleDrawer = document.getElementById('btn-toggle-drawer');
  const btnCloseDrawer = document.getElementById('btn-close-drawer');
  const drawerOverlay = document.getElementById('drawer-overlay');

  function openDrawer() {
    if (rack) rack.classList.add('drawer-open');
    if (drawerOverlay) drawerOverlay.classList.add('active');
  }

  function closeDrawer() {
    if (rack) rack.classList.remove('drawer-open');
    if (drawerOverlay) drawerOverlay.classList.remove('active');
  }

  function toggleControlPanel() {
    if (window.innerWidth <= 1024) {
      if (rack && rack.classList.contains('drawer-open')) {
        closeDrawer();
      } else {
        openDrawer();
      }
    } else {
      // Desktop toggle: collapse/expand panel to give waveforms full width
      if (instShell) {
        instShell.classList.toggle('panel-collapsed');
        if (btnToggleDrawer) {
          btnToggleDrawer.classList.toggle('active', !instShell.classList.contains('panel-collapsed'));
        }
        computeAndRender();
      }
    }
  }

  if (btnToggleDrawer) btnToggleDrawer.addEventListener('click', toggleControlPanel);
  if (btnCloseDrawer) btnCloseDrawer.addEventListener('click', closeDrawer);
  if (drawerOverlay) drawerOverlay.addEventListener('click', closeDrawer);

  // ==================== AM / FM / ALL MODE SELECTOR ====================
  const headerModeTabs = document.querySelectorAll('#header-mode-selector .btn-mode-tab');
  const workflowTabBtns = document.querySelectorAll('.tab-btn');

  function setAppMode(mode) {
    state.currentMode = mode;
    document.body.setAttribute('data-view', mode);

    // Sync header tabs
    headerModeTabs.forEach(btn => {
      btn.classList.toggle('active', btn.getAttribute('data-mode') === mode);
    });

    // Sync workflow tabs
    workflowTabBtns.forEach(btn => {
      btn.classList.toggle('active', btn.getAttribute('data-tab') === mode);
    });

    computeAndRender();
  }

  headerModeTabs.forEach(btn => {
    btn.addEventListener('click', () => {
      const mode = btn.getAttribute('data-mode');
      setAppMode(mode);
    });
  });

  workflowTabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const tab = btn.getAttribute('data-tab');
      setAppMode(tab);
    });
  });

  // ==================== GRAPH FOCUS / MAXIMIZE CONTROLS ====================
  const scopeGrid = document.getElementById('scope-grid');
  const spectrumRow = document.getElementById('spectrum-row');
  const focusButtons = document.querySelectorAll('.btn-scope-focus');

  function toggleFocus(bezel) {
    if (!bezel) return;
    const isAlreadyFocused = bezel.classList.contains('is-focused');

    // Unfocus all
    document.querySelectorAll('.scope-bezel.is-focused').forEach(b => {
      b.classList.remove('is-focused');
      const btn = b.querySelector('.btn-scope-focus');
      if (btn) btn.textContent = '⛶ Focus';
    });

    if (scopeGrid) scopeGrid.classList.remove('has-focused-scope');
    if (spectrumRow) spectrumRow.classList.remove('has-focused-scope');

    if (!isAlreadyFocused) {
      bezel.classList.add('is-focused');
      if (scopeGrid) scopeGrid.classList.add('has-focused-scope');
      if (spectrumRow) spectrumRow.classList.add('has-focused-scope');
      const btn = bezel.querySelector('.btn-scope-focus');
      if (btn) btn.textContent = '✕ Restore';
    }

    // Immediate canvas resize & redraw
    computeAndRender();
  }

  focusButtons.forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const bezel = btn.closest('.scope-bezel');
      toggleFocus(bezel);
    });
  });

  // ==================== FULLSCREEN CONTROLLER ====================
  const btnFullscreen = document.getElementById('btn-fullscreen');
  if (btnFullscreen) {
    btnFullscreen.addEventListener('click', () => {
      if (!document.fullscreenElement) {
        document.documentElement.requestFullscreen().catch(err => {
          console.warn('Fullscreen request failed:', err);
        });
      } else {
        document.exitFullscreen().catch(err => {
          console.warn('Exit fullscreen failed:', err);
        });
      }
    });

    document.addEventListener('fullscreenchange', () => {
      if (document.fullscreenElement) {
        btnFullscreen.textContent = '⛶ Exit Fullscreen';
        btnFullscreen.classList.add('active');
      } else {
        btnFullscreen.textContent = '⛶ Fullscreen';
        btnFullscreen.classList.remove('active');
      }
      setTimeout(() => computeAndRender(), 80);
    });
  }

  // ==================== DISPLAY & SCALE SETTINGS ====================
  const timeZoomBtns = document.querySelectorAll('#time-zoom-group .seg-btn');
  timeZoomBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      timeZoomBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.timeScale = parseFloat(btn.getAttribute('data-scale')) || 1.0;

      // Update scale tags
      const effMs = (DISPLAY_DURATION / state.timeScale * 1000).toFixed(1);
      const tagMsg = document.getElementById('tag-msg-scale');
      if (tagMsg) tagMsg.textContent = `${(effMs / 10).toFixed(2)}ms/div | 0.5V/div`;
      const tagAm = document.getElementById('tag-am-scale');
      if (tagAm) tagAm.textContent = `${(effMs / 10).toFixed(2)}ms/div | 1.0V/div`;

      computeAndRender();
    });
  });

  const btnToggleGrid = document.getElementById('btn-toggle-grid');
  if (btnToggleGrid) {
    btnToggleGrid.addEventListener('click', () => {
      state.showGrid = !state.showGrid;
      btnToggleGrid.classList.toggle('active', state.showGrid);
      btnToggleGrid.textContent = state.showGrid ? '▦ Graticule Grid: ON' : '▦ Graticule Grid: OFF';
      computeAndRender();
    });
  }

  const btnAutoscale = document.getElementById('btn-autoscale');
  if (btnAutoscale) {
    btnAutoscale.addEventListener('click', () => {
      state.timeScale = 1.0;
      state.showGrid = true;
      timeZoomBtns.forEach(b => b.classList.toggle('active', b.getAttribute('data-scale') === '1.0'));
      if (btnToggleGrid) {
        btnToggleGrid.classList.add('active');
        btnToggleGrid.textContent = '▦ Graticule Grid: ON';
      }
      computeAndRender();
    });
  }

  // ==================== KEYBOARD NAVIGATION ====================
  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      // Exit graph focus if active
      const focusedBezel = document.querySelector('.scope-bezel.is-focused');
      if (focusedBezel) {
        toggleFocus(focusedBezel);
        return;
      }
      // Close drawer if open
      closeDrawer();
      // Close theory modal if open
      if (modalTheory && modalTheory.classList.contains('open')) {
        modalTheory.classList.remove('open');
      }
    } else if (e.code === 'Space' && e.target.tagName !== 'INPUT' && e.target.tagName !== 'SELECT') {
      e.preventDefault();
      toggleFreeze();
    }
  });

  // ==================== AUDIO FILE UPLOAD ====================
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
        const arrayBuffer = await file.arrayBuffer();
        const ctx = getAudioContext();
        const audioBuffer = await ctx.decodeAudioData(arrayBuffer);

        const raw = audioBuffer.getChannelData(0);
        const fileSr = audioBuffer.sampleRate;

        // Resample to SR if necessary
        if (fileSr !== SR) {
          const ratio = SR / fileSr;
          const newLen = Math.floor(raw.length * ratio);
          audioFileBuffer = new Float32Array(newLen);
          for (let i = 0; i < newLen; i++) {
            const srcIdx = i / ratio;
            const idx0 = Math.floor(srcIdx);
            const idx1 = Math.min(idx0 + 1, raw.length - 1);
            const frac = srcIdx - idx0;
            audioFileBuffer[i] = raw[idx0] * (1 - frac) + raw[idx1] * frac;
          }
        } else {
          audioFileBuffer = new Float32Array(raw);
        }

        // Normalize
        let maxAbs = 0;
        for (let i = 0; i < audioFileBuffer.length; i++) {
          const a = Math.abs(audioFileBuffer[i]);
          if (a > maxAbs) maxAbs = a;
        }
        if (maxAbs > 0) {
          for (let i = 0; i < audioFileBuffer.length; i++) {
            audioFileBuffer[i] /= maxAbs;
          }
        }

        audioFileOffset = 0;
        if (audioFileName) audioFileName.textContent = `✓ ${file.name} (${(audioFileBuffer.length / SR).toFixed(1)}s)`;
        computeAndRender();
      } catch (err) {
        console.error('Failed to load audio file:', err);
        if (audioFileName) audioFileName.textContent = '❌ Failed to decode audio';
      }
    });
  }

  // ==================== LIVE MICROPHONE ====================
  const btnToggleMic = document.getElementById('btn-toggle-mic');
  const micStatus = document.getElementById('mic-status');
  const micControls = document.getElementById('mic-controls');

  async function startMic() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
      micStream = stream;
      const ctx = getAudioContext();
      const source = ctx.createMediaStreamSource(stream);

      const processor = ctx.createScriptProcessor(4096, 1, 1);
      processor.onaudioprocess = (e) => {
        const input = e.inputBuffer.getChannelData(0);
        micBuffer.set(input);
        if (state.msgType === 'mic' && !state.frozen) {
          computeAndRender();
        }
      };

      source.connect(processor);
      processor.connect(ctx.destination);
      micProcessorNode = processor;
      micActive = true;

      if (btnToggleMic) {
        btnToggleMic.textContent = '⏹ Stop Microphone';
        btnToggleMic.classList.add('active');
      }
      if (micStatus) micStatus.textContent = 'Mic: Streaming Live';
    } catch (err) {
      console.error('Microphone access denied:', err);
      if (micStatus) micStatus.textContent = 'Mic: Access Denied';
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
      btnToggleMic.textContent = '🎤 Enable Microphone';
      btnToggleMic.classList.remove('active');
    }
    if (micStatus) micStatus.textContent = 'Mic: Idle';
  }

  if (btnToggleMic) {
    btnToggleMic.addEventListener('click', () => {
      if (micActive) stopMic();
      else startMic();
    });
  }

  // ==================== AUDIO SPEAKER MONITOR ====================
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
    if (btnPlayMsg) btnPlayMsg.classList.remove('active');
    if (btnPlayAm) btnPlayAm.classList.remove('active');
    if (btnPlayFm) btnPlayFm.classList.remove('active');
    if (audioStatus) audioStatus.textContent = 'Speaker: Idle';
  }

  function playSignal(samples, label, activeBtn) {
    stopSpeaker();
    if (!samples || samples.length === 0) return;

    try {
      const ctx = getAudioContext();
      let playLen = samples.length;
      let repeatCount = 1;
      if (playLen < SR * 2) {
        repeatCount = Math.ceil((SR * 2) / playLen);
      }

      const buffer = ctx.createBuffer(1, playLen * repeatCount, SR);
      const out = buffer.getChannelData(0);

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

      if (activeBtn) activeBtn.classList.add('active');
      if (audioStatus) audioStatus.textContent = `Playing ${label} 🔊`;
    } catch (err) {
      console.error('Audio playback error:', err);
      if (audioStatus) audioStatus.textContent = 'Playback Error';
    }
  }

  if (btnPlayMsg) btnPlayMsg.addEventListener('click', () => playSignal(lastMsg, 'Message', btnPlayMsg));
  if (btnPlayAm) btnPlayAm.addEventListener('click', () => playSignal(lastAmRec, 'AM Demod', btnPlayAm));
  if (btnPlayFm) btnPlayFm.addEventListener('click', () => playSignal(lastFmRec, 'FM Demod', btnPlayFm));
  if (btnStopAudio) btnStopAudio.addEventListener('click', stopSpeaker);

  // ==================== FREEZE / RUN CONTROLLER ====================
  const btnFreeze = document.getElementById('btn-freeze');
  const freezeIcon = document.getElementById('freeze-icon');
  const freezeText = document.getElementById('freeze-text');

  function toggleFreeze() {
    state.frozen = !state.frozen;
    if (btnFreeze) btnFreeze.classList.toggle('active', state.frozen);
    if (freezeIcon) freezeIcon.textContent = state.frozen ? '▶' : '⏸';
    if (freezeText) freezeText.textContent = state.frozen ? 'Run' : 'Pause';
    computeAndRender();
  }

  if (btnFreeze) btnFreeze.addEventListener('click', toggleFreeze);

  // ==================== THEORY MODAL ====================
  const modalTheory = document.getElementById('modal-theory');
  const btnTheoryModal = document.getElementById('btn-theory-modal');
  const btnCloseTheory = document.getElementById('btn-close-theory');

  if (btnTheoryModal && modalTheory) {
    btnTheoryModal.addEventListener('click', () => modalTheory.classList.add('open'));
  }
  if (btnCloseTheory && modalTheory) {
    btnCloseTheory.addEventListener('click', () => modalTheory.classList.remove('open'));
  }
  if (modalTheory) {
    modalTheory.addEventListener('click', (e) => {
      if (e.target === modalTheory) modalTheory.classList.remove('open');
    });
  }

  // ==================== EXPORT HIGH-RES PNG ====================
  const btnExportPng = document.getElementById('btn-export-png');
  if (btnExportPng) {
    btnExportPng.addEventListener('click', () => {
      const activeCanvas = canvases.amMod || canvases.message;
      if (!activeCanvas) return;
      const link = document.createElement('a');
      link.download = `AM_FM_PRO_Capture_${Date.now()}.png`;
      link.href = activeCanvas.toDataURL('image/png');
      link.click();
    });
  }

  // ==================== MAIN COMPUTE + RENDER ====================

  function computeAndRender(isCursorRefresh = false) {
    const t0 = performance.now();

    const effDuration = DISPLAY_DURATION / (state.timeScale || 1.0);
    const nDisplay = Math.min(N_SAMPLES, Math.floor(SR * effDuration));

    // 1. Generate or fetch message signal
    let msg = null;
    if (state.msgType === 'audio-file' && audioFileBuffer && audioFileBuffer.length > 0) {
      msg = new Float32Array(N_SAMPLES);
      for (let i = 0; i < N_SAMPLES; i++) {
        const idx = (audioFileOffset + i) % audioFileBuffer.length;
        msg[i] = audioFileBuffer[idx] * state.am;
      }
      if (!state.frozen) {
        audioFileOffset = (audioFileOffset + N_SAMPLES) % audioFileBuffer.length;
      }
    } else if (state.msgType === 'mic' && micActive) {
      msg = new Float32Array(N_SAMPLES);
      for (let i = 0; i < N_SAMPLES; i++) {
        msg[i] = micBuffer[i] * state.am * 3.0;
      }
    } else {
      msg = DSP.generateWaveform(state.msgType, state.fm, state.am, 0, N_SAMPLES, SR);
    }

    lastMsg.set(msg);

    // 2. Generate carrier
    const carrier = DSP.generateSine(state.fc, state.ac, 0, nDisplay, SR);
    const fullCarrier = DSP.generateSine(state.fc, state.ac, 0, N_SAMPLES, SR);

    // 3. Compute link budget (hardware RF parameters)
    let lb = null;
    if (state.noiseEnabled) {
      lb = DSP.linkBudget(
        state.txPower,
        state.distance,
        state.fc,
        state.noiseFigure,
        state.rxBandwidth * 1000
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

    // 6. Draw Oscilloscope Scopes
    const showGrid = state.showGrid !== false;
    Renderer.drawWaveform(canvases.message, msg.slice(0, nDisplay), Renderer.COLORS.message, `MESSAGE x(t) [${state.msgType.toUpperCase()}]`, 'V', effDuration, state.frozen, showGrid);
    Renderer.drawWaveform(canvases.carrier, carrier, Renderer.COLORS.carrier, 'CARRIER c(t) [NCO]', 'V', effDuration, state.frozen, showGrid);

    if (state.amEnabled && amResult) {
      const amLabel = state.amMode === 'DSB-SC' ? 'AM s(t) [DSB-SC COHERENT]' : 'AM s(t) [DSB-FC ENVELOPE]';
      Renderer.drawWaveform(canvases.amMod, amResult.signal.slice(0, nDisplay), Renderer.COLORS.am, amLabel, 'V', effDuration, state.frozen, showGrid);
      Renderer.drawWaveform(canvases.amDemod, amRec.slice(0, nDisplay), Renderer.COLORS.amDemod, 'AM RECOVERED y(t)', 'V', effDuration, state.frozen, showGrid);
      const amNF = (state.noiseEnabled && amChan.meta) ? amChan.meta.noiseFloorDb : null;
      Renderer.drawSpectrum(canvases.specAm, amSpec.freqs, amSpec.magnitudes, Renderer.COLORS.spectrumAm, 'AM RF SPECTRUM', state.fc * 2.2, amNF, state.fc, state.fm, null, showGrid);
    } else {
      Renderer.drawWaveform(canvases.amMod, null, Renderer.COLORS.am, 'AM TRANSMITTED [OFF]', 'V', effDuration, false, showGrid);
      Renderer.drawWaveform(canvases.amDemod, null, Renderer.COLORS.amDemod, 'AM RECOVERED [OFF]', 'V', effDuration, false, showGrid);
      Renderer.drawSpectrum(canvases.specAm, null, null, Renderer.COLORS.spectrumAm, 'AM SPECTRUM [OFF]', 20000, null, null, null, null, showGrid);
    }

    if (state.fmEnabled && fmResult) {
      Renderer.drawWaveform(canvases.fmMod, fmResult.signal.slice(0, nDisplay), Renderer.COLORS.fm, 'FM TRANSMITTED s(t)', 'V', effDuration, state.frozen, showGrid);
      Renderer.drawWaveform(canvases.fmDemod, fmRec.slice(0, nDisplay), Renderer.COLORS.fmDemod, 'FM RECOVERED y(t)', 'V', effDuration, state.frozen, showGrid);
      const fmNF = (state.noiseEnabled && fmChan.meta) ? fmChan.meta.noiseFloorDb : null;
      Renderer.drawSpectrum(canvases.specFm, fmSpec.freqs, fmSpec.magnitudes, Renderer.COLORS.spectrumFm, 'FM RF SPECTRUM', state.fc * 2.2, fmNF, state.fc, state.fm, fmResult.meta.carsonBW, showGrid);
    } else {
      Renderer.drawWaveform(canvases.fmMod, null, Renderer.COLORS.fm, 'FM TRANSMITTED [OFF]', 'V', effDuration, false, showGrid);
      Renderer.drawWaveform(canvases.fmDemod, null, Renderer.COLORS.fmDemod, 'FM RECOVERED [OFF]', 'V', effDuration, false, showGrid);
      Renderer.drawSpectrum(canvases.specFm, null, null, Renderer.COLORS.spectrumFm, 'FM SPECTRUM [OFF]', 20000, null, null, null, null, showGrid);
    }

    // 7. Update Telemetry & Insights
    const elapsed = performance.now() - t0;
    const statLatency = document.getElementById('stat-latency');
    if (statLatency) statLatency.textContent = `<${Math.max(1, elapsed.toFixed(1))}ms`;

    updateAnalytics(amResult, fmResult, amMetrics, fmMetrics, amChan, fmChan, lb);
  }

  // ==================== ANALYTICS & INSIGHT GENERATOR ====================

  function setText(id, val) {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
  }

  function updateAnalytics(amResult, fmResult, amMetrics, fmMetrics, amChan, fmChan, lb) {
    // 1. AM Live Power Table
    if (amResult && amResult.meta) {
      setText('pwr-pc', amResult.meta.pc.toFixed(2) + ' W');
      setText('pwr-psb', amResult.meta.psb.toFixed(2) + ' W');
      setText('pwr-pt', amResult.meta.pt.toFixed(2) + ' W');
      setText('pwr-eff', amResult.meta.efficiency.toFixed(1) + '%');

      setText('met-am-m', state.m.toFixed(2));
      setText('met-am-eff', amResult.meta.efficiency.toFixed(1) + '%');
      setText('met-am-bw', (2 * state.fm).toFixed(0) + ' Hz');
      setText('met-am-corr', amMetrics ? amMetrics.correlation.toFixed(3) : '---');

      const isOver = amResult.meta.isOvermod;
      const statusEl = document.getElementById('met-am-status');
      if (statusEl) {
        statusEl.textContent = isOver ? 'OVERMOD' : (state.amMode === 'DSB-SC' ? 'DSB-SC' : 'LINEAR OK');
        statusEl.className = 'm-cell-val ' + (isOver ? 'danger' : 'good');
      }

      const alertOvermod = document.getElementById('alert-overmod');
      if (alertOvermod) alertOvermod.style.display = isOver ? 'flex' : 'none';
    }

    // 2. FM Power & Carson Table
    if (fmResult && fmResult.meta) {
      setText('pwr-beta', fmResult.meta.beta.toFixed(2));
      setText('pwr-carson', (fmResult.meta.carsonBW / 1000).toFixed(1) + ' kHz');
      setText('pwr-fm-regime', fmResult.meta.isNBFM ? 'NBFM' : 'WBFM');

      setText('met-fm-beta', fmResult.meta.beta.toFixed(2));
      setText('met-fm-df', state.deltaF.toFixed(0) + ' Hz');
      setText('met-fm-bw', fmResult.meta.carsonBW.toFixed(0) + ' Hz');
      setText('met-fm-type', fmResult.meta.isNBFM ? 'NBFM' : 'WBFM');
      setText('met-fm-corr', fmMetrics ? fmMetrics.correlation.toFixed(3) : '---');

      const beta = fmResult.meta.beta;
      const fmGain = 10 * Math.log10(3 * beta * beta * (beta + 1) + 1e-12);
      setText('pwr-fm-gain', `+${Math.max(0, fmGain).toFixed(1)} dB`);
      setText('snr-fm-gain', `+${Math.max(0, fmGain).toFixed(1)} dB`);
    }

    // 3. Channel Telemetry
    setText('met-snr', state.noiseEnabled ? `${state.snr.toFixed(0)} dB` : 'OFF (Inf)');

    const chan = (amChan && amChan.meta && amChan.meta.pSig > 0) ? amChan :
                (fmChan && fmChan.meta && fmChan.meta.pSig > 0) ? fmChan : null;

    if (chan && chan.meta && state.noiseEnabled) {
      setText('snr-measured', `${chan.meta.measuredSnr.toFixed(1)} dB`);
      const delta = chan.meta.measuredSnr - chan.meta.snrDb;
      const deltaEl = document.getElementById('snr-delta');
      if (deltaEl) {
        deltaEl.textContent = `${delta >= 0 ? '+' : ''}${delta.toFixed(1)} dB`;
        deltaEl.className = 'm-cell-val ' + (Math.abs(delta) < 2 ? 'good' : 'warn');
      }
    } else {
      setText('snr-measured', '---');
      setText('snr-delta', '---');
    }

    // 4. Link Budget Strip
    const lbEl = document.getElementById('link-budget');
    if (lbEl) {
      if (state.noiseEnabled && lb) {
        lbEl.classList.remove('hidden');
        setText('lb-tx', `${lb.txPowerDbw.toFixed(1)} dBW`);
        setText('lb-fspl', `${lb.fsplDb.toFixed(1)} dB`);
        setText('lb-rx', `${lb.rxPowerDbw.toFixed(1)} dBW`);
        setText('lb-ktb', `${lb.kTBDbw.toFixed(1)} dBW`);
        setText('lb-nf', `${lb.noiseFigureDb.toFixed(0)} dB`);
        const snrInEl = document.getElementById('lb-snr-in');
        if (snrInEl) {
          snrInEl.textContent = `${lb.snrIn >= 0 ? '+' : ''}${lb.snrIn.toFixed(1)} dB`;
          snrInEl.style.color = lb.snrIn >= 10 ? 'var(--state-normal)' : (lb.snrIn >= 0 ? 'var(--state-warn)' : 'var(--state-danger)');
        }
      } else {
        lbEl.classList.add('hidden');
      }
    }

    // 5. Signal Flow Nodes status update
    setText('flow-msg-stat', `${(state.fm / 1000).toFixed(1)} kHz ${state.msgType.toUpperCase()}`);
    setText('flow-chan-stat', state.noiseEnabled ? `AWGN SNR: ${state.snr}dB` : 'Clean Channel');
    const chanNode = document.getElementById('node-chan');
    if (chanNode) chanNode.classList.toggle('active', state.noiseEnabled);

    // 6. Pedagogical Smart Engineering Insight
    const titleEl = document.getElementById('insight-title');
    const descEl = document.getElementById('insight-desc');
    const iconEl = document.getElementById('insight-icon');

    if (state.m > 1.0 && state.amMode === 'DSB-FC') {
      if (titleEl) titleEl.textContent = 'CRITICAL: AM OVERMODULATION DETECTED (m > 1.0)';
      if (descEl) descEl.textContent = `Modulation index m = ${state.m.toFixed(2)} exceeds 1.00. The envelope crosses zero, causing carrier phase reversal. Standard envelope detectors (diode/peak) will produce severe clipping distortion.`;
      if (iconEl) iconEl.textContent = '⚠️';
    } else if (state.amMode === 'DSB-SC') {
      if (titleEl) titleEl.textContent = 'OPTIMIZED: DOUBLE-SIDEBAND SUPPRESSED-CARRIER (DSB-SC)';
      if (descEl) descEl.textContent = `Carrier has been suppressed, achieving 100% transmission efficiency. Notice the absence of the central fc spike in the AM spectrum. Demodulation requires synchronous coherent carrier recovery.`;
      if (iconEl) iconEl.textContent = '⚡';
    } else if (state.noiseEnabled && state.snr < 10) {
      if (titleEl) titleEl.textContent = 'CHANNEL IMPAIRMENT: LOW CARRIER-TO-NOISE RATIO (SNR < 10 dB)';
      if (descEl) descEl.textContent = `Channel SNR is ${state.snr} dB. FM performance drops below the capture threshold (~10 dB), causing FM threshold breakdown (click noise) where WBFM quieting advantage diminishes.`;
      if (iconEl) iconEl.textContent = '🌧️';
    } else if (state.fmEnabled && state.deltaF >= 4000) {
      if (titleEl) titleEl.textContent = 'WIDEBAND FM: HIGH FIDELITY WITH SNR QUIETING GAIN';
      if (descEl) descEl.textContent = `Carson bandwidth BT = ${(2 * (state.deltaF + state.fm) / 1000).toFixed(1)} kHz. Wideband FM trades excess RF bandwidth for a +${(10 * Math.log10(3 * Math.pow(state.deltaF/state.fm, 2) * (state.deltaF/state.fm + 1))).toFixed(1)} dB post-detection SNR improvement over AM.`;
      if (iconEl) iconEl.textContent = '📡';
    } else {
      if (titleEl) titleEl.textContent = 'ENGINEERING DIAGNOSTICS: NOMINAL SPECIFICATION';
      if (descEl) descEl.textContent = `Carrier frequency fc = ${state.fc} Hz is adequately separated from message bandwidth (fc >> fm). Reconstruction correlation r > 0.99 verifies high mathematical accuracy.`;
      if (iconEl) iconEl.textContent = '✅';
    }
  }

  // ==================== SLIDER & NUMERIC STEPPER BINDING ====================

  function bindDualInput(sliderId, numId, textId, stateKey, transform, invTransform, formatter) {
    const slider = document.getElementById(sliderId);
    const num = document.getElementById(numId);
    const textEl = document.getElementById(textId);

    if (!slider) return;

    function updateVal(rawVal) {
      const val = transform ? transform(rawVal) : rawVal;
      state[stateKey] = val;

      const formatted = formatter ? formatter(val) : (Number.isInteger(val) ? val.toString() : val.toFixed(2));
      if (textEl) textEl.textContent = formatted;
      if (num && num !== document.activeElement) num.value = val;
      if (slider && slider !== document.activeElement) slider.value = invTransform ? invTransform(val) : val;

      computeAndRender();
    }

    slider.addEventListener('input', (e) => updateVal(parseFloat(e.target.value)));
    if (num) {
      num.addEventListener('input', (e) => {
        const v = parseFloat(e.target.value);
        if (!isNaN(v)) updateVal(v);
      });
    }
  }

  bindDualInput('slider-fm', 'num-fm', 'val-fm', 'fm', null, null, v => v.toFixed(0));
  bindDualInput('slider-am', 'num-am', 'val-am', 'am', v => v / 100, v => v * 100, v => v.toFixed(2));
  bindDualInput('slider-fc', 'num-fc', 'val-fc', 'fc', null, null, v => v.toFixed(0));
  bindDualInput('slider-ac', 'num-ac', 'val-ac', 'ac', v => v / 100, v => v * 100, v => v.toFixed(2));
  bindDualInput('slider-m', 'num-m', 'val-m', 'm', v => v / 100, v => v * 100, v => v.toFixed(2));
  bindDualInput('slider-df', 'num-df', 'val-df', 'deltaF', null, null, v => v.toFixed(0));
  bindDualInput('slider-snr', 'num-snr', 'val-snr', 'snr', null, null, v => v.toFixed(0));

  // Additional single sliders
  function bindSimpleSlider(sliderId, textId, stateKey, formatter) {
    const el = document.getElementById(sliderId);
    const tel = document.getElementById(textId);
    if (!el) return;
    el.addEventListener('input', (e) => {
      const val = parseFloat(e.target.value);
      state[stateKey] = val;
      if (tel) tel.textContent = formatter ? formatter(val) : val.toString();
      computeAndRender();
    });
  }

  bindSimpleSlider('slider-txpow', 'val-txpow', 'txPower', v => v.toFixed(0));
  bindSimpleSlider('slider-dist', 'val-dist', 'distance', v => v.toFixed(1));
  bindSimpleSlider('slider-nf', 'val-nf', 'noiseFigure', v => v.toFixed(0));
  bindSimpleSlider('slider-bw', 'val-bw', 'rxBandwidth', v => v.toFixed(0));

  // Toggles
  function bindToggle(toggleId, stateKey, labelOn, labelOff) {
    const btn = document.getElementById(toggleId);
    if (!btn) return;
    btn.addEventListener('click', () => {
      state[stateKey] = !state[stateKey];
      btn.classList.toggle('active', state[stateKey]);
      btn.textContent = state[stateKey] ? labelOn : labelOff;
      computeAndRender();
    });
  }

  bindToggle('toggle-am', 'amEnabled', 'AM ON', 'AM OFF');
  bindToggle('toggle-fm', 'fmEnabled', 'FM ON', 'FM OFF');
  bindToggle('toggle-noise', 'noiseEnabled', 'NOISE ON', 'NOISE OFF');

  // AM Mode Segmented Buttons
  const btnModeDsbfc = document.getElementById('btn-mode-dsbfc');
  const btnModeDsbsc = document.getElementById('btn-mode-dsbsc');

  function setAmMode(mode) {
    state.amMode = mode;
    if (btnModeDsbfc) btnModeDsbfc.classList.toggle('active', mode === 'DSB-FC');
    if (btnModeDsbsc) btnModeDsbsc.classList.toggle('active', mode === 'DSB-SC');
    computeAndRender();
  }

  if (btnModeDsbfc) btnModeDsbfc.addEventListener('click', () => setAmMode('DSB-FC'));
  if (btnModeDsbsc) btnModeDsbsc.addEventListener('click', () => setAmMode('DSB-SC'));

  // Message Source Selector
  const msgTypeEl = document.getElementById('msg-type');
  if (msgTypeEl) {
    msgTypeEl.addEventListener('change', (e) => {
      state.msgType = e.target.value;
      if (audioFileControls) audioFileControls.style.display = (state.msgType === 'audio-file') ? 'block' : 'none';
      if (micControls) micControls.style.display = (state.msgType === 'mic') ? 'block' : 'none';
      if (state.msgType !== 'mic' && micActive) stopMic();
      computeAndRender();
    });
  }

  // ==================== PRESET SELECTOR ====================
  const selPreset = document.getElementById('sel-preset');
  if (selPreset) {
    selPreset.addEventListener('change', (e) => {
      const p = e.target.value;
      if (p === 'default') {
        state.m = 0.80; state.fc = 10000; state.fm = 1000; state.amMode = 'DSB-FC'; state.noiseEnabled = false;
      } else if (p === 'am-overmod') {
        state.m = 1.35; state.fc = 10000; state.fm = 1000; state.amMode = 'DSB-FC'; state.noiseEnabled = false;
      } else if (p === 'am-dsbsc') {
        state.m = 1.00; state.fc = 10000; state.fm = 1000; state.amMode = 'DSB-SC'; state.noiseEnabled = false;
      } else if (p === 'fm-wbfm') {
        state.deltaF = 5000; state.fm = 1000; state.fc = 10000; state.noiseEnabled = false;
      } else if (p === 'fm-nbfm') {
        state.deltaF = 800; state.fm = 1000; state.fc = 10000; state.noiseEnabled = false;
      } else if (p === 'chan-noisy') {
        state.noiseEnabled = true; state.snr = 5;
      } else if (p === 'chan-weak') {
        state.noiseEnabled = true; state.distance = 50.0; state.txPower = -10;
      }

      // Sync UI controls
      const tNoise = document.getElementById('toggle-noise');
      if (tNoise) {
        tNoise.classList.toggle('active', state.noiseEnabled);
        tNoise.textContent = state.noiseEnabled ? 'NOISE ON' : 'NOISE OFF';
      }
      setAmMode(state.amMode);

      const setEl = (sId, nId, tId, val, fmt) => {
        const s = document.getElementById(sId);
        const n = document.getElementById(nId);
        const t = document.getElementById(tId);
        if (s) s.value = val;
        if (n) n.value = val;
        if (t) t.textContent = fmt ? fmt(val) : val;
      };

      setEl('slider-fm', 'num-fm', 'val-fm', state.fm, v => v.toFixed(0));
      setEl('slider-fc', 'num-fc', 'val-fc', state.fc, v => v.toFixed(0));
      setEl('slider-m', 'num-m', 'val-m', state.m * 100, v => (v/100).toFixed(2));
      const numM = document.getElementById('num-m');
      if (numM) numM.value = state.m.toFixed(2);
      setEl('slider-df', 'num-df', 'val-df', state.deltaF, v => v.toFixed(0));
      setEl('slider-snr', 'num-snr', 'val-snr', state.snr, v => v.toFixed(0));

      computeAndRender();
    });
  }

  // ==================== RESET INSTRUMENT ====================
  const btnReset = document.getElementById('btn-reset');
  if (btnReset) {
    btnReset.addEventListener('click', () => {
      stopSpeaker();
      stopMic();

      state = {
        msgType: 'sine', fm: 1000, am: 1.0, fc: 10000, ac: 1.0,
        m: 0.80, deltaF: 4000, amMode: 'DSB-FC', snr: 25,
        amEnabled: true, fmEnabled: true, noiseEnabled: false,
        txPower: 0, distance: 1.0, noiseFigure: 6, rxBandwidth: 10,
        frozen: false, timeScale: 1.0, showGrid: true, currentMode: 'all'
      };

      if (selPreset) selPreset.value = 'default';
      if (msgTypeEl) msgTypeEl.value = 'sine';
      if (audioFileControls) audioFileControls.style.display = 'none';
      if (micControls) micControls.style.display = 'none';

      setAmMode('DSB-FC');
      setAppMode('all');

      const tAm = document.getElementById('toggle-am');
      if (tAm) { tAm.classList.add('active'); tAm.textContent = 'AM ON'; }
      const tFm = document.getElementById('toggle-fm');
      if (tFm) { tFm.classList.add('active'); tFm.textContent = 'FM ON'; }
      const tNoise = document.getElementById('toggle-noise');
      if (tNoise) { tNoise.classList.remove('active'); tNoise.textContent = 'NOISE OFF'; }

      timeZoomBtns.forEach(b => b.classList.toggle('active', b.getAttribute('data-scale') === '1.0'));
      if (btnToggleGrid) {
        btnToggleGrid.classList.add('active');
        btnToggleGrid.textContent = '▦ Graticule Grid: ON';
      }

      computeAndRender();
    });
  }

  // Window resize handler with debounce
  let resizeTimer = null;
  window.addEventListener('resize', () => {
    if (resizeTimer) clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => computeAndRender(), 80);
  });

  // Initial boot render
  requestAnimationFrame(() => {
    requestAnimationFrame(() => computeAndRender());
  });
});
