"""
Parameter Sweep Engine
======================
Single and dual-variable parameter sweeps using the actual simulation pipeline.
All results are computed from real DSP processing, never fabricated.
"""
import numpy as np
from waveforms import generate_waveform
from modulator import AMModulator, FMModulator
from channel import Channel
from demodulator import AMDemodulator, FMDemodulator, compute_reconstruction_metrics
from spectrum import SpectrumAnalyzer
from measurements import SystemMetrics


class ParameterSweep:
    """
    Runs parameter sweeps by varying one or two parameters and recording
    simulation results at each point.
    """
    
    def __init__(self, sr: float = 44100.0, n_samples: int = 4096):
        self.sr = sr
        self.n_samples = n_samples
    
    def sweep_single(self, param_name: str, values: list,
                     base_params: dict = None) -> dict:
        """
        Single-variable sweep.
        
        Args:
            param_name: One of 'fm', 'fc', 'm', 'delta_f', 'beta', 'snr_db'
            values: List of values to sweep
            base_params: Dict of fixed parameters (defaults provided)
        
        Returns:
            dict with 'param_name', 'values', 'results' (list of metric dicts)
        """
        defaults = {
            'fm': 1000.0, 'fc': 10000.0, 'ac': 1.0, 'am': 1.0,
            'm': 0.8, 'delta_f': 4000.0,
            'noise_enabled': False, 'snr_db': 25.0,
            'msg_type': 'sine'
        }
        if base_params:
            defaults.update(base_params)
        
        results = []
        for val in values:
            params = dict(defaults)
            if param_name == 'beta':
                params['delta_f'] = val * params['fm']
            else:
                params[param_name] = val
            
            result = self._run_point(params)
            result['sweep_value'] = val
            results.append(result)
        
        return {
            'param_name': param_name,
            'values': list(values),
            'results': results
        }
    
    def sweep_dual(self, param1_name: str, param1_values: list,
                   param2_name: str, param2_values: list,
                   base_params: dict = None) -> dict:
        """
        Two-variable sweep. Returns a 2D grid of results.
        """
        defaults = {
            'fm': 1000.0, 'fc': 10000.0, 'ac': 1.0, 'am': 1.0,
            'm': 0.8, 'delta_f': 4000.0,
            'noise_enabled': False, 'snr_db': 25.0,
            'msg_type': 'sine'
        }
        if base_params:
            defaults.update(base_params)
        
        grid = []
        for v1 in param1_values:
            row = []
            for v2 in param2_values:
                params = dict(defaults)
                params[param1_name] = v1
                params[param2_name] = v2
                result = self._run_point(params)
                result['sweep_v1'] = v1
                result['sweep_v2'] = v2
                row.append(result)
            grid.append(row)
        
        return {
            'param1_name': param1_name,
            'param1_values': list(param1_values),
            'param2_name': param2_name,
            'param2_values': list(param2_values),
            'grid': grid
        }
    
    def _run_point(self, params: dict) -> dict:
        """Run one simulation point and return all metrics."""
        msg = generate_waveform(params.get('msg_type', 'sine'),
                                params['fm'], params.get('am', 1.0), 0.0,
                                self.n_samples, self.sr)
        
        # AM
        am_mod = AMModulator(params['fc'], params['ac'], params['m'], 'DSB-FC', self.sr)
        am_out, _, _, am_meta = am_mod.process(msg)
        
        # FM
        fm_mod = FMModulator(params['fc'], params['ac'], params['delta_f'], self.sr)
        fm_out, _, inst_freq, fm_meta = fm_mod.process(msg, params['fm'])
        
        # Channel
        ch = Channel(self.sr)
        if params.get('noise_enabled', False):
            ch.set_params(noise_enabled=True, snr_db=params['snr_db'])
        
        am_chan, ch_am = ch.process(am_out)
        fm_chan, ch_fm = ch.process(fm_out)
        
        # Demodulation
        am_demod = AMDemodulator('ENVELOPE', params['fc'], params['fm'] * 1.5, self.sr)
        fm_demod = FMDemodulator(params['fm'] * 1.5, self.sr)
        
        am_rec = am_demod.process(am_chan)
        fm_rec = fm_demod.process(fm_chan)
        
        # Metrics
        spec = SpectrumAnalyzer(self.sr, min(self.n_samples, 4096))
        _, _, _, _, spec_am = spec.process(am_out)
        _, _, _, _, spec_fm = spec.process(fm_out)
        
        am_sys = SystemMetrics.analyze_am(am_out, msg, params['fc'], params['fm'],
                                           params['m'], params['ac'],
                                           spec_am['obw_99_hz'])
        fm_sys = SystemMetrics.analyze_fm(fm_out, inst_freq, params['fc'], params['fm'],
                                           params['delta_f'], params['ac'],
                                           spec_fm['obw_99_hz'])
        
        recon_am = compute_reconstruction_metrics(msg, am_rec)
        recon_fm = compute_reconstruction_metrics(msg, fm_rec)
        
        return {
            'am_bw': am_sys['bw_theory_hz'],
            'fm_bw': fm_sys['carson_bw_theory_hz'],
            'am_efficiency': am_sys['efficiency_pct'],
            'am_m': params['m'],
            'fm_beta': fm_meta['beta'],
            'fm_delta_f': params['delta_f'],
            'am_correlation': recon_am['correlation'],
            'fm_correlation': recon_fm['correlation'],
            'am_mse': recon_am['mse'],
            'fm_mse': recon_fm['mse'],
            'am_psnr': recon_am['psnr_db'],
            'fm_psnr': recon_fm['psnr_db'],
            'snr_db': params.get('snr_db', float('inf')),
            'am_overmod': am_sys['is_overmodulated'],
        }
