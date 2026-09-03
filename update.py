import sys

def modify_spectrum():
    with open(r'spectrum.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 1. flattop import and WINDOWS
    content = content.replace('from scipy.signal import find_peaks as sp_find_peaks', 'from scipy.signal import find_peaks as sp_find_peaks\nfrom scipy.signal.windows import flattop as _flattop_win')
    content = content.replace('\'flattop\'  : np.kaiser,', '\'flattop\'  : _flattop_win,')
    content = content.replace('from collections import deque\n', '')
    
    # 2. waterfall init
    old_init = '''        n_bins = self.fft_size // 2 + 1\n        self.freq_axis = np.fft.rfftfreq(self.fft_size, d=1.0 / self.sr)\n        # Allocate independent array copies for waterfall buffer\n        self.waterfall = deque(\n            [np.full(n_bins, -100.0, dtype=np.float32) for _ in range(self.waterfall_n)],\n            maxlen=self.waterfall_n\n        )'''
    new_init = '''        n_bins = self.fft_size // 2 + 1\n        self.freq_axis = np.fft.rfftfreq(self.fft_size, d=1.0 / self.sr)\n        self._wf_buf = np.full((self.waterfall_n, n_bins), -80.0, dtype=np.float32)\n        self._wf_idx = 0'''
    content = content.replace(old_init, new_init)
    
    # 3. waterfall process
    old_process = '''        # Update waterfall (append copy)\n        self.waterfall.appendleft(psd_dbm.astype(np.float32).copy())\n        waterfall_matrix = np.array(self.waterfall)'''
    new_process = '''        # Update waterfall\n        self._wf_buf[self._wf_idx] = psd_dbm.astype(np.float32)\n        self._wf_idx = (self._wf_idx + 1) % self.waterfall_n\n        waterfall_matrix = np.roll(self._wf_buf, -self._wf_idx, axis=0)'''
    content = content.replace(old_process, new_process)
    
    # 4. _compute_3db_bw
    old_3db = '''    def _compute_3db_bw(self, psd_dbm: np.ndarray) -> float:\n        \"\"\"Computes -3 dB bandwidth around peak.\"\"\"\n        pk_idx = np.argmax(psd_dbm)\n        pk_val = psd_dbm[pk_idx]\n        mask = psd_dbm >= (pk_val - 3.0)\n        idxs = np.where(mask)[0]\n        if len(idxs) < 2:\n            return 0.0\n        return float(self.freq_axis[idxs[-1]] - self.freq_axis[idxs[0]])'''
    new_3db = '''    def _compute_3db_bw(self, psd_dbm: np.ndarray) -> float:\n        \"\"\"Computes -3 dB bandwidth around peak.\"\"\"\n        pk_idx = np.argmax(psd_dbm)\n        pk_val = psd_dbm[pk_idx]\n        threshold = pk_val - 3.0\n        # Search outward from peak\n        left = pk_idx\n        while left > 0 and psd_dbm[left] >= threshold:\n            left -= 1\n        right = pk_idx\n        while right < len(psd_dbm) - 1 and psd_dbm[right] >= threshold:\n            right += 1\n        bw = (right - left) * (self.sr / self.fft_size)\n        return float(bw)'''
    content = content.replace(old_3db, new_3db)
    
    with open(r'spectrum.py', 'w', encoding='utf-8') as f:
        f.write(content)

def modify_measurements():
    with open(r'measurements.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 1. fix analytic env
    old_env = '''            # Minimum envelope valley (around carrier zero crossings)\n            analytic_env = np.abs(np.fft.ifft(np.fft.fft(am_signal) * 2.0))[:len(am_signal)]\n            v_min = float(np.min(analytic_env))'''
    new_env = '''            # Minimum envelope valley (around carrier zero crossings)\n            from scipy.signal import hilbert\n            analytic = hilbert(am_signal.astype(np.float64))\n            analytic_env = np.abs(analytic).astype(np.float64)\n            v_min = float(np.min(analytic_env))'''
    content = content.replace(old_env, new_env)
    
    # 2. diagnose_quality
    diagnose_method = '''
    @staticmethod
    def diagnose_quality(am_metrics: dict = None, fm_metrics: dict = None,
                         recon_am: dict = None, recon_fm: dict = None,
                         channel_snr_db: float = None) -> list:
        \"\"\"
        Diagnose poor signal recovery. Returns list of dicts with:
        'issue', 'evidence', 'recommendation'
        \"\"\"
        diagnostics = []
        
        if am_metrics and am_metrics.get('is_overmodulated'):
            diagnostics.append({
                'issue': 'AM Overmodulation',
                'evidence': f\"m = {am_metrics.get('m_theory', '?'):.2f} > 1.0\",
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
                'evidence': f\"Correlation = {recon_am['correlation']:.3f} < 0.8\",
                'recommendation': 'Check for overmodulation, reduce noise, or verify demodulator settings'
            })
        
        if recon_fm and recon_fm.get('correlation', 1.0) < 0.8:
            diagnostics.append({
                'issue': 'Poor FM Reconstruction',
                'evidence': f\"Correlation = {recon_fm['correlation']:.3f} < 0.8\",
                'recommendation': 'Reduce frequency deviation or increase SNR'
            })
        
        if fm_metrics and fm_metrics.get('beta_theory', 0) > 10:
            diagnostics.append({
                'issue': 'Excessive FM Deviation',
                'evidence': f\"Beta = {fm_metrics['beta_theory']:.1f} > 10\",
                'recommendation': 'Reduce frequency deviation to limit occupied bandwidth'
            })
        
        return diagnostics
'''
    content += diagnose_method
    
    with open(r'measurements.py', 'w', encoding='utf-8') as f:
        f.write(content)

modify_spectrum()
modify_measurements()
