// AM FM PRO - Precision Canvas Instrument Renderer v3.0
// Inspired by Keysight / Tektronix / Rohde & Schwarz test equipment.
// High-DPI, calibrated graticule, cursor inspection, RF markers.

const Renderer = (() => {
  const COLORS = {
    bg: '#05070d',           // Deep instrument graticule viewport
    gridMajor: '#182236',    // Major graticule lines
    gridMinor: '#0f1624',    // Minor graticule lines
    crosshair: '#253554',    // Center baseline crosshair
    text: '#94a3b8',         // Standard graticule labels
    textDim: '#475569',      // Minor ticks
    cursor: '#38bdf8',       // Active inspection cursor
    cursorBg: '#0f172a',     // Cursor readout badge
    noiseFloor: '#ff1744',   // Calibrated noise floor line
    marker: '#ffd700',       // Spectrum peak marker
    // Semantic signal traces
    message: '#00e5ff',
    carrier: '#00e676',
    am: '#ffb300',
    amDemod: '#ff6090',
    fm: '#b388ff',
    fmDemod: '#00e676',
    instFreq: '#7c4dff',
    spectrumAm: '#ffb300',
    spectrumFm: '#00e5ff'
  };

  // Active cursor inspection state
  const cursorState = {};

  function setupCanvas(canvas) {
    if (!canvas) return null;
    const rect = canvas.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0) return null;
    const dpr = window.devicePixelRatio || 1;

    const targetW = Math.round(rect.width * dpr);
    const targetH = Math.round(rect.height * dpr);

    if (canvas.width !== targetW || canvas.height !== targetH) {
      canvas.width = targetW;
      canvas.height = targetH;
    }

    const ctx = canvas.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    return { ctx, width: rect.width, height: rect.height };
  }

  /**
   * Draw Oscilloscope Time-Domain Waveform with calibrated graticule
   */
  function drawWaveform(canvas, data, color, label, yUnit = 'V', durationSec = 0.005, isFrozen = false) {
    const setup = setupCanvas(canvas);
    if (!setup) return;
    const { ctx, width, height } = setup;

    // 1. Clear display
    ctx.fillStyle = COLORS.bg;
    ctx.fillRect(0, 0, width, height);

    // Margins for calibrated graticule scale
    const ml = 46, mr = 12, mt = 18, mb = 22;
    const pw = width - ml - mr;
    const ph = height - mt - mb;

    if (pw <= 0 || ph <= 0) return;

    // 2. Compute dynamic Y scale or default to [-1.5, +1.5]
    let yMin = -1.2, yMax = 1.2;
    let vpp = 0, vrms = 0;

    if (data && data.length > 0) {
      let dMin = data[0], dMax = data[0], sumSq = 0;
      for (let i = 0; i < data.length; i++) {
        const v = data[i];
        if (v < dMin) dMin = v;
        if (v > dMax) dMax = v;
        sumSq += v * v;
      }
      vpp = dMax - dMin;
      vrms = Math.sqrt(sumSq / data.length);

      const span = Math.max(dMax - dMin, 0.4);
      const pad = span * 0.15;
      yMin = dMin - pad;
      yMax = dMax + pad;
    }

    // 3. Draw Sub-divided Oscilloscope Graticule (10 divs horizontal x 8 divs vertical)
    const nDivX = 10;
    const nDivY = 8;

    // Minor dotted grid
    ctx.strokeStyle = COLORS.gridMinor;
    ctx.lineWidth = 0.5;
    ctx.setLineDash([2, 4]);

    for (let i = 1; i < nDivY; i++) {
      const y = mt + (ph * i / nDivY);
      ctx.beginPath();
      ctx.moveTo(ml, y);
      ctx.lineTo(ml + pw, y);
      ctx.stroke();
    }

    for (let i = 1; i < nDivX; i++) {
      const x = ml + (pw * i / nDivX);
      ctx.beginPath();
      ctx.moveTo(x, mt);
      ctx.lineTo(x, mt + ph);
      ctx.stroke();
    }

    // Major center crosshair (division 4 horizontal, division 5 vertical)
    ctx.setLineDash([]);
    ctx.strokeStyle = COLORS.crosshair;
    ctx.lineWidth = 1.0;

    const midY = mt + ph / 2;
    ctx.beginPath();
    ctx.moveTo(ml, midY);
    ctx.lineTo(ml + pw, midY);
    ctx.stroke();

    const midX = ml + pw / 2;
    ctx.beginPath();
    ctx.moveTo(midX, mt);
    ctx.lineTo(midX, mt + ph);
    ctx.stroke();

    // Graticule boundary border
    ctx.strokeStyle = COLORS.gridMajor;
    ctx.strokeRect(ml, mt, pw, ph);

    // 4. Y-axis calibration values
    ctx.fillStyle = COLORS.text;
    ctx.font = '9px "JetBrains Mono", Consolas, monospace';
    ctx.textAlign = 'right';

    for (let i = 0; i <= 4; i++) {
      const y = mt + (ph * i / 4);
      const val = yMax - (yMax - yMin) * i / 4;
      ctx.fillText(`${val >= 0 ? '+' : ''}${val.toFixed(2)}${yUnit}`, ml - 4, y + 3);
    }

    // 5. X-axis time calibration values (in ms)
    ctx.textAlign = 'center';
    const totalMs = durationSec * 1000;
    for (let i = 0; i <= 4; i++) {
      const x = ml + (pw * i / 4);
      const t = (totalMs * i / 4).toFixed(1);
      ctx.fillText(`${t}ms`, x, height - 6);
    }
    ctx.textAlign = 'left';

    // 6. Channel header & telemetry tag
    ctx.fillStyle = color;
    ctx.font = '10px "JetBrains Mono", Consolas, monospace';
    ctx.fillText(`CH1: ${label}`, ml + 6, mt - 5);

    if (data && data.length > 0) {
      ctx.fillStyle = COLORS.textDim;
      ctx.textAlign = 'right';
      ctx.fillText(`Vpp: ${vpp.toFixed(2)}V | Vrms: ${vrms.toFixed(2)}V`, ml + pw - 4, mt - 5);
      ctx.textAlign = 'left';
    }

    // 7. Render Signal Trace
    if (data && data.length > 0) {
      ctx.strokeStyle = color;
      ctx.lineWidth = 1.5;
      ctx.shadowColor = color;
      ctx.shadowBlur = 3;

      ctx.beginPath();
      const nPts = data.length;
      const step = pw / (nPts - 1);

      for (let i = 0; i < nPts; i++) {
        const x = ml + i * step;
        const norm = (data[i] - yMin) / (yMax - yMin);
        const y = mt + ph * (1 - Math.max(0, Math.min(1, norm)));
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
      ctx.shadowBlur = 0;
    } else {
      // Trace off
      ctx.fillStyle = COLORS.textDim;
      ctx.font = '11px "JetBrains Mono", monospace';
      ctx.textAlign = 'center';
      ctx.fillText('[CHANNEL INACTIVE]', ml + pw / 2, mt + ph / 2);
    }

    // 8. Frozen indicator badge
    if (isFrozen) {
      ctx.fillStyle = '#ff9100';
      ctx.font = '9px "JetBrains Mono", monospace';
      ctx.fillText('⏸ FREEZE', ml + 8, mt + 16);
    }

    // 9. Interactive Cursor Readout (if hovering)
    const cursor = cursorState[canvas.id];
    if (cursor && cursor.active && cursor.x >= ml && cursor.x <= ml + pw) {
      const curX = cursor.x;
      const curRatio = (curX - ml) / pw;
      const curTimeMs = curRatio * totalMs;

      // Vertical cursor line
      ctx.strokeStyle = COLORS.cursor;
      ctx.lineWidth = 1;
      ctx.setLineDash([3, 3]);
      ctx.beginPath();
      ctx.moveTo(curX, mt);
      ctx.lineTo(curX, mt + ph);
      ctx.stroke();
      ctx.setLineDash([]);

      // Interpolate voltage at cursor
      if (data && data.length > 0) {
        const idx = Math.min(Math.floor(curRatio * data.length), data.length - 1);
        const curV = data[idx];
        const curY = mt + ph * (1 - (curV - yMin) / (yMax - yMin));

        // Cursor tracking circle
        ctx.fillStyle = COLORS.cursor;
        ctx.beginPath();
        ctx.arc(curX, curY, 3.5, 0, Math.PI * 2);
        ctx.fill();

        // Cursor tooltip box
        const tipText = `t: ${curTimeMs.toFixed(2)}ms | V: ${curV.toFixed(2)}V`;
        ctx.font = '9px "JetBrains Mono", monospace';
        const tipW = ctx.measureText(tipText).width + 8;
        const tipX = Math.min(curX + 6, ml + pw - tipW - 2);
        const tipY = Math.max(curY - 14, mt + 4);

        ctx.fillStyle = COLORS.cursorBg;
        ctx.fillRect(tipX, tipY, tipW, 14);
        ctx.strokeStyle = COLORS.cursor;
        ctx.strokeRect(tipX, tipY, tipW, 14);
        ctx.fillStyle = '#ffffff';
        ctx.fillText(tipText, tipX + 4, tipY + 10);
      }
    }
  }

  /**
   * Draw Calibrated RF Spectrum Analyzer with sidebands & noise floor
   */
  function drawSpectrum(canvas, freqs, magnitudes, color, label, fMax = 22050, noiseFloorDb = null, fc = null, fm = null, carsonBw = null) {
    const setup = setupCanvas(canvas);
    if (!setup) return;
    const { ctx, width, height } = setup;

    ctx.fillStyle = COLORS.bg;
    ctx.fillRect(0, 0, width, height);

    const ml = 46, mr = 12, mt = 18, mb = 22;
    const pw = width - ml - mr;
    const ph = height - mt - mb;

    if (pw <= 0 || ph <= 0) return;

    const dbMin = -90, dbMax = 0;

    // 1. Graticule
    ctx.strokeStyle = COLORS.gridMinor;
    ctx.lineWidth = 0.5;
    ctx.setLineDash([2, 4]);

    for (let i = 1; i < 6; i++) {
      const y = mt + (ph * i / 6);
      ctx.beginPath();
      ctx.moveTo(ml, y);
      ctx.lineTo(ml + pw, y);
      ctx.stroke();
    }

    for (let i = 1; i < 8; i++) {
      const x = ml + (pw * i / 8);
      ctx.beginPath();
      ctx.moveTo(x, mt);
      ctx.lineTo(x, mt + ph);
      ctx.stroke();
    }

    ctx.setLineDash([]);
    ctx.strokeStyle = COLORS.gridMajor;
    ctx.strokeRect(ml, mt, pw, ph);

    // 2. Y-Axis in dBFS
    ctx.fillStyle = COLORS.text;
    ctx.font = '9px "JetBrains Mono", Consolas, monospace';
    ctx.textAlign = 'right';

    for (let i = 0; i <= 6; i++) {
      const y = mt + (ph * i / 6);
      const db = dbMax - (dbMax - dbMin) * i / 6;
      ctx.fillText(`${db.toFixed(0)}dB`, ml - 4, y + 3);
    }

    // 3. X-Axis in kHz
    ctx.textAlign = 'center';
    for (let i = 0; i <= 4; i++) {
      const x = ml + (pw * i / 4);
      const fKhz = (fMax * i / 4) / 1000;
      ctx.fillText(`${fKhz.toFixed(1)}k`, x, height - 6);
    }
    ctx.textAlign = 'left';

    // 4. Header title
    ctx.fillStyle = color;
    ctx.font = '10px "JetBrains Mono", monospace';
    ctx.fillText(`FFT SPECTRUM: ${label} [RBW: 10.7 Hz]`, ml + 6, mt - 5);

    if (!freqs || freqs.length === 0 || !magnitudes || magnitudes.length === 0) {
      ctx.fillStyle = COLORS.textDim;
      ctx.textAlign = 'center';
      ctx.fillText('[SPECTRUM IDLE]', ml + pw / 2, mt + ph / 2);
      return;
    }

    // Find max frequency cutoff
    let maxIdx = freqs.length;
    for (let i = 0; i < freqs.length; i++) {
      if (freqs[i] > fMax) { maxIdx = i; break; }
    }

    // 5. Draw Carson Bandwidth Bracket for FM if provided
    if (fc && carsonBw && carsonBw > 0) {
      const fStart = Math.max(0, fc - carsonBw / 2);
      const fEnd = Math.min(fMax, fc + carsonBw / 2);
      const x1 = ml + (fStart / fMax) * pw;
      const x2 = ml + (fEnd / fMax) * pw;

      ctx.fillStyle = 'rgba(179, 136, 255, 0.08)';
      ctx.fillRect(x1, mt, x2 - x1, ph);

      ctx.strokeStyle = 'rgba(179, 136, 255, 0.45)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(x1, mt + 12);
      ctx.lineTo(x1, mt + 4);
      ctx.lineTo(x2, mt + 4);
      ctx.lineTo(x2, mt + 12);
      ctx.stroke();

      ctx.fillStyle = COLORS.fm;
      ctx.font = '8px "JetBrains Mono", monospace';
      ctx.textAlign = 'center';
      ctx.fillText(`Carson BW: ${(carsonBw / 1000).toFixed(1)} kHz`, (x1 + x2) / 2, mt + 14);
    }

    // 6. Draw Noise Floor Dashed Line if present
    if (noiseFloorDb !== null && isFinite(noiseFloorDb)) {
      const clampedNF = Math.max(dbMin, Math.min(dbMax, noiseFloorDb));
      const nfY = mt + ph * (1 - (clampedNF - dbMin) / (dbMax - dbMin));

      ctx.strokeStyle = COLORS.noiseFloor;
      ctx.lineWidth = 1.0;
      ctx.setLineDash([4, 3]);
      ctx.beginPath();
      ctx.moveTo(ml, nfY);
      ctx.lineTo(ml + pw, nfY);
      ctx.stroke();
      ctx.setLineDash([]);

      ctx.fillStyle = '#ff6b81';
      ctx.font = '8px "JetBrains Mono", monospace';
      ctx.textAlign = 'right';
      ctx.fillText(`Thermal Floor: ${clampedNF.toFixed(1)} dBFS`, ml + pw - 4, nfY - 3);
      ctx.textAlign = 'left';
    }

    // 7. Render Spectrum Magnitude Trace
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.5;
    ctx.shadowColor = color;
    ctx.shadowBlur = 2;

    ctx.beginPath();
    for (let px = 0; px < pw; px++) {
      const idx = Math.floor(px * maxIdx / pw);
      if (idx >= magnitudes.length) break;
      const mag = Math.max(dbMin, Math.min(dbMax, magnitudes[idx]));
      const y = mt + ph * (1 - (mag - dbMin) / (dbMax - dbMin));
      if (px === 0) ctx.moveTo(ml + px, y);
      else ctx.lineTo(ml + px, y);
    }
    ctx.stroke();
    ctx.shadowBlur = 0;

    // Fill under curve
    ctx.lineTo(ml + pw, mt + ph);
    ctx.lineTo(ml, mt + ph);
    ctx.closePath();
    ctx.globalAlpha = 0.08;
    ctx.fillStyle = color;
    ctx.fill();
    ctx.globalAlpha = 1.0;

    // 8. Carrier & Sideband RF Markers (fc, fc-fm, fc+fm)
    if (fc && fc <= fMax) {
      const xFc = ml + (fc / fMax) * pw;
      ctx.strokeStyle = COLORS.marker;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(xFc, mt);
      ctx.lineTo(xFc, mt + ph);
      ctx.stroke();

      ctx.fillStyle = COLORS.marker;
      ctx.font = '8px "JetBrains Mono", monospace';
      ctx.textAlign = 'center';
      ctx.fillText(`▼ fc: ${(fc / 1000).toFixed(1)}k`, xFc, mt - 2);

      // Sidebands for AM
      if (fm && (fc + fm) <= fMax) {
        const xUSB = ml + ((fc + fm) / fMax) * pw;
        const xLSB = ml + ((fc - fm) / fMax) * pw;

        ctx.fillStyle = '#ffb300cc';
        ctx.fillText(`USB`, xUSB, mt + 20);
        ctx.fillText(`LSB`, xLSB, mt + 20);
      }
    }
  }

  /**
   * Bind interactive mouse / touch cursor to a canvas
   */
  function bindCursor(canvas, onUpdateCallback) {
    if (!canvas) return;

    function handleMove(clientX) {
      const rect = canvas.getBoundingClientRect();
      const x = clientX - rect.left;
      cursorState[canvas.id] = { active: true, x };
      if (onUpdateCallback) onUpdateCallback();
    }

    canvas.addEventListener('mousemove', (e) => handleMove(e.clientX));
    canvas.addEventListener('mouseleave', () => {
      cursorState[canvas.id] = { active: false, x: -1 };
      if (onUpdateCallback) onUpdateCallback();
    });

    canvas.addEventListener('touchmove', (e) => {
      if (e.touches && e.touches[0]) {
        handleMove(e.touches[0].clientX);
      }
    }, { passive: true });

    canvas.addEventListener('touchend', () => {
      cursorState[canvas.id] = { active: false, x: -1 };
      if (onUpdateCallback) onUpdateCallback();
    });
  }

  return { setupCanvas, drawWaveform, drawSpectrum, bindCursor, COLORS };
})();
