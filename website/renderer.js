const Renderer = (() => {
  const COLORS = {
    cyan: '#00e5ff',
    green: '#00ff88',
    gold: '#ffd700',
    pink: '#ff2d78',
    purple: '#bf00ff',
    orange: '#ff7700',
    red: '#ff1744',
    grid: '#1a2244',
    gridLight: '#252f55',
    bg: '#080a18',
    text: '#6c7a9c',
    axisText: '#8899bb',
    noiseFloor: '#ff174480'
  };

  function setupCanvas(canvas) {
    const rect = canvas.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0) return null;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    const ctx = canvas.getContext('2d');
    ctx.scale(dpr, dpr);
    return { ctx, width: rect.width, height: rect.height };
  }

  function drawWaveform(canvas, data, color, label, yLabel) {
    const setup = setupCanvas(canvas);
    if (!setup) return;
    const { ctx, width, height } = setup;

    ctx.fillStyle = COLORS.bg;
    ctx.fillRect(0, 0, width, height);

    const ml = 45, mr = 10, mt = 24, mb = 20;
    const pw = width - ml - mr;
    const ph = height - mt - mb;

    ctx.fillStyle = color;
    ctx.font = '11px JetBrains Mono, Consolas, monospace';
    ctx.fillText(label, ml, 14);

    ctx.strokeStyle = COLORS.grid;
    ctx.lineWidth = 0.5;
    for (let i = 0; i <= 4; i++) {
      const y = mt + (ph * i / 4);
      ctx.beginPath();
      ctx.moveTo(ml, y);
      ctx.lineTo(ml + pw, y);
      ctx.stroke();
    }
    for (let i = 0; i <= 4; i++) {
      const x = ml + (pw * i / 4);
      ctx.beginPath();
      ctx.moveTo(x, mt);
      ctx.lineTo(x, mt + ph);
      ctx.stroke();
    }

    if (!data || data.length === 0) return;

    let yMin = data[0], yMax = data[0];
    for (let i = 1; i < data.length; i++) {
      if (data[i] < yMin) yMin = data[i];
      if (data[i] > yMax) yMax = data[i];
    }
    const yRange = Math.max(yMax - yMin, 0.001);
    const yPad = yRange * 0.1;
    yMin -= yPad;
    yMax += yPad;

    ctx.fillStyle = COLORS.text;
    ctx.font = '9px Consolas, monospace';
    ctx.textAlign = 'right';
    for (let i = 0; i <= 4; i++) {
      const val = yMax - (yMax - yMin) * i / 4;
      const y = mt + (ph * i / 4);
      ctx.fillText(val.toFixed(2), ml - 4, y + 3);
    }
    ctx.textAlign = 'left';

    ctx.strokeStyle = color;
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    for (let px = 0; px < pw; px++) {
      const idx = Math.floor(px * data.length / pw);
      const y = mt + ph * (1 - (data[idx] - yMin) / (yMax - yMin));
      px === 0 ? ctx.moveTo(ml + px, y) : ctx.lineTo(ml + px, y);
    }
    ctx.stroke();
  }

  function drawSpectrum(canvas, freqs, magnitudes, color, label, fMax, noiseFloorDb) {
    const setup = setupCanvas(canvas);
    if (!setup) return;
    const { ctx, width, height } = setup;

    ctx.fillStyle = COLORS.bg;
    ctx.fillRect(0, 0, width, height);

    const ml = 45, mr = 10, mt = 24, mb = 24;
    const pw = width - ml - mr;
    const ph = height - mt - mb;

    ctx.fillStyle = color;
    ctx.font = '11px JetBrains Mono, Consolas, monospace';
    ctx.fillText(label, ml, 14);

    if (!freqs || freqs.length === 0) return;

    const maxFreq = fMax || freqs[freqs.length - 1];
    // Fix: findIndex can return 0 which is falsy, use explicit check
    let maxIdx = freqs.length;
    for (let i = 0; i < freqs.length; i++) {
      if (freqs[i] > maxFreq) { maxIdx = i; break; }
    }

    const dbMin = -80, dbMax = 0;

    ctx.strokeStyle = COLORS.grid;
    ctx.lineWidth = 0.5;
    for (let i = 0; i <= 4; i++) {
      const y = mt + (ph * i / 4);
      ctx.beginPath();
      ctx.moveTo(ml, y); ctx.lineTo(ml + pw, y); ctx.stroke();
      ctx.fillStyle = COLORS.text;
      ctx.font = '9px Consolas, monospace';
      ctx.textAlign = 'right';
      const db = dbMax - (dbMax - dbMin) * i / 4;
      ctx.fillText(db.toFixed(0) + ' dB', ml - 4, y + 3);
    }

    ctx.textAlign = 'center';
    ctx.fillStyle = COLORS.text;
    for (let i = 0; i <= 4; i++) {
      const x = ml + (pw * i / 4);
      const f = (maxFreq * i / 4);
      ctx.fillText((f / 1000).toFixed(1) + 'k', x, height - 4);
    }
    ctx.textAlign = 'left';

    // Draw noise floor line if provided
    if (noiseFloorDb !== undefined && noiseFloorDb !== null && isFinite(noiseFloorDb)) {
      const clampedNF = Math.max(dbMin, Math.min(dbMax, noiseFloorDb));
      const nfY = mt + ph * (1 - (clampedNF - dbMin) / (dbMax - dbMin));
      ctx.strokeStyle = COLORS.noiseFloor;
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 3]);
      ctx.beginPath();
      ctx.moveTo(ml, nfY);
      ctx.lineTo(ml + pw, nfY);
      ctx.stroke();
      ctx.setLineDash([]);

      // Noise floor label
      ctx.fillStyle = '#ff174499';
      ctx.font = '8px Consolas, monospace';
      ctx.textAlign = 'right';
      ctx.fillText('NF ' + clampedNF.toFixed(0) + 'dB', ml + pw - 2, nfY - 3);
      ctx.textAlign = 'left';
    }

    ctx.strokeStyle = color;
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    for (let px = 0; px < pw; px++) {
      const idx = Math.floor(px * maxIdx / pw);
      if (idx >= magnitudes.length) break;
      const db = Math.max(dbMin, Math.min(dbMax, magnitudes[idx]));
      const y = mt + ph * (1 - (db - dbMin) / (dbMax - dbMin));
      px === 0 ? ctx.moveTo(ml + px, y) : ctx.lineTo(ml + px, y);
    }
    ctx.stroke();

    ctx.lineTo(ml + pw, mt + ph);
    ctx.lineTo(ml, mt + ph);
    ctx.closePath();
    ctx.globalAlpha = 0.1;
    ctx.fillStyle = color;
    ctx.fill();
    ctx.globalAlpha = 1.0;
  }

  return { setupCanvas, drawWaveform, drawSpectrum, COLORS };
})();
