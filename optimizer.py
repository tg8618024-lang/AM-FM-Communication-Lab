"""
Engineering Design Optimization Mode
====================================
Finds optimal modulation parameters subject to user-defined constraints.
All recommendations are SIMULATION-BASED and clearly labeled as such.
"""
import numpy as np
from sweep_engine import ParameterSweep


class DesignOptimizer:
    """
    Searches parameter space to find configurations that satisfy
    engineering constraints.
    
    All results are labeled as SIMULATION-BASED RECOMMENDATION.
    No claims of real-world certification or guaranteed RF performance.
    """
    
    def __init__(self, sr: float = 44100.0):
        self.sr = sr
        self._sweep = ParameterSweep(sr)
    
    def optimize(self, constraints: dict) -> dict:
        """
        Find optimal parameters subject to constraints.
        
        Args:
            constraints: dict with optional keys:
                'max_bw_hz': maximum occupied bandwidth
                'min_output_snr_db': minimum acceptable output SNR (via PSNR)
                'max_rmse': maximum acceptable RMSE
                'min_correlation': minimum acceptable reconstruction correlation
                'max_transmit_power_w': maximum total transmit power
                'noise_enabled': whether to include AWGN
                'snr_db': channel SNR for testing
        
        Returns:
            dict with:
                'status': 'SOLUTION_FOUND' or 'NO_FEASIBLE_SOLUTION'
                'label': 'SIMULATION-BASED RECOMMENDATION'
                'am_best': best AM config dict or None
                'fm_best': best FM config dict or None
                'recommendation': str describing the best option
                'all_candidates': list of all evaluated configs
        """
        max_bw = constraints.get('max_bw_hz', 20000.0)
        min_corr = constraints.get('min_correlation', 0.8)
        max_rmse = constraints.get('max_rmse', 0.5)
        noise = constraints.get('noise_enabled', True)
        snr = constraints.get('snr_db', 20.0)
        
        # AM search grid
        m_values = np.arange(0.1, 1.55, 0.1)
        fm_values = [500.0, 1000.0, 2000.0, 3000.0]
        
        # FM search grid
        df_values = np.arange(500, 8001, 500)
        
        base = {'noise_enabled': noise, 'snr_db': snr, 'fc': 10000.0}
        
        am_candidates = []
        fm_candidates = []
        
        # Sweep AM
        for m_val in m_values:
            for fm_val in fm_values:
                params = dict(base, m=float(m_val), fm=float(fm_val), delta_f=4000.0)
                result = self._sweep._run_point(params)
                result['m'] = float(m_val)
                result['fm'] = float(fm_val)
                
                # Check constraints
                feasible = True
                if result['am_bw'] > max_bw:
                    feasible = False
                if result['am_correlation'] < min_corr:
                    feasible = False
                if result.get('am_mse', 1.0) > max_rmse ** 2:
                    feasible = False
                
                result['feasible'] = feasible
                result['mod_type'] = 'AM'
                am_candidates.append(result)
        
        # Sweep FM
        for df_val in df_values:
            for fm_val in fm_values:
                params = dict(base, m=0.8, fm=float(fm_val), delta_f=float(df_val))
                result = self._sweep._run_point(params)
                result['delta_f'] = float(df_val)
                result['fm'] = float(fm_val)
                
                feasible = True
                if result['fm_bw'] > max_bw:
                    feasible = False
                if result['fm_correlation'] < min_corr:
                    feasible = False
                if result.get('fm_mse', 1.0) > max_rmse ** 2:
                    feasible = False
                
                result['feasible'] = feasible
                result['mod_type'] = 'FM'
                fm_candidates.append(result)
        
        # Find best AM (highest correlation among feasible)
        feasible_am = [c for c in am_candidates if c['feasible']]
        feasible_fm = [c for c in fm_candidates if c['feasible']]
        
        am_best = max(feasible_am, key=lambda x: x['am_correlation']) if feasible_am else None
        fm_best = max(feasible_fm, key=lambda x: x['fm_correlation']) if feasible_fm else None
        
        # Determine recommendation
        if am_best and fm_best:
            if fm_best['fm_correlation'] > am_best['am_correlation']:
                rec = (f"FM recommended: delta_f={fm_best['delta_f']:.0f} Hz, fm={fm_best['fm']:.0f} Hz. "
                       f"Correlation={fm_best['fm_correlation']:.4f}, BW={fm_best['fm_bw']:.0f} Hz. "
                       f"FM provides better noise immunity at this SNR.")
            else:
                rec = (f"AM recommended: m={am_best['m']:.2f}, fm={am_best['fm']:.0f} Hz. "
                       f"Correlation={am_best['am_correlation']:.4f}, BW={am_best['am_bw']:.0f} Hz. "
                       f"AM provides adequate quality with narrower bandwidth.")
        elif am_best:
            rec = f"Only AM feasible: m={am_best['m']:.2f}, fm={am_best['fm']:.0f} Hz."
        elif fm_best:
            rec = f"Only FM feasible: delta_f={fm_best['delta_f']:.0f} Hz, fm={fm_best['fm']:.0f} Hz."
        else:
            rec = "No feasible solution found. Relax constraints."
        
        return {
            'status': 'SOLUTION_FOUND' if (am_best or fm_best) else 'NO_FEASIBLE_SOLUTION',
            'label': 'SIMULATION-BASED RECOMMENDATION',
            'am_best': am_best,
            'fm_best': fm_best,
            'recommendation': rec,
            'all_candidates': am_candidates + fm_candidates
        }
