"""
Export & Reporting Module
=========================
Export simulation results as images, CSV data, and HTML reports.
"""
import os
import csv
import json
import datetime
import numpy as np


class Exporter:
    """
    Exports simulation data in various formats.
    """
    
    def __init__(self, output_dir: str = None):
        self.output_dir = output_dir or os.path.join(os.path.dirname(__file__), 'exports')
        os.makedirs(self.output_dir, exist_ok=True)
    
    def export_csv(self, data: list, filename: str, headers: list = None) -> str:
        """
        Export tabular data to CSV.
        
        Args:
            data: list of dicts or list of lists
            filename: output filename (without path)
            headers: column headers (auto-detected from dict keys if data is list of dicts)
        
        Returns: full path to created file
        """
        path = os.path.join(self.output_dir, filename)
        with open(path, 'w', newline='', encoding='utf-8') as f:
            if data and isinstance(data[0], dict):
                headers = headers or list(data[0].keys())
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()
                writer.writerows(data)
            else:
                writer = csv.writer(f)
                if headers:
                    writer.writerow(headers)
                writer.writerows(data)
        return path
    
    def export_json(self, data: dict, filename: str) -> str:
        """
        Export structured data to JSON.
        """
        path = os.path.join(self.output_dir, filename)
        
        def default_serializer(obj):
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            if isinstance(obj, (np.float32, np.float64)):
                return float(obj)
            if isinstance(obj, (np.int32, np.int64)):
                return int(obj)
            if isinstance(obj, np.bool_):
                return bool(obj)
            return str(obj)
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, default=default_serializer)
        return path
    
    def export_waveform_plot(self, time_ms: np.ndarray, signals: dict,
                             title: str, filename: str) -> str:
        """
        Export a time-domain waveform plot as PNG.
        
        Args:
            time_ms: time axis in milliseconds
            signals: dict of {label: (data_array, color_hex)}
            title: plot title
            filename: output filename
        
        Returns: full path to created file
        """
        import matplotlib
        matplotlib.use('Agg')  # Non-interactive backend
        import matplotlib.pyplot as plt
        
        fig, ax = plt.subplots(figsize=(10, 4))
        fig.patch.set_facecolor('#070913')
        ax.set_facecolor('#080a18')
        
        for label, (data, color) in signals.items():
            n = min(len(time_ms), len(data))
            ax.plot(time_ms[:n], data[:n], color=color, linewidth=1.0, label=label)
        
        ax.set_title(title, color='#00e5ff', fontfamily='monospace', fontweight='bold')
        ax.set_xlabel('Time (ms)', color='#8899bb')
        ax.set_ylabel('Amplitude', color='#8899bb')
        ax.tick_params(colors='#6c7a9c')
        ax.legend(facecolor='#0d1124', edgecolor='#1a2244', labelcolor='#d0d8f0')
        ax.grid(True, alpha=0.2, color='#2a3a5a')
        
        path = os.path.join(self.output_dir, filename)
        fig.savefig(path, dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor())
        plt.close(fig)
        return path
    
    def export_spectrum_plot(self, freq_hz: np.ndarray, psd_dbm: np.ndarray,
                              title: str, filename: str,
                              f_max: float = None) -> str:
        """
        Export a frequency-domain spectrum plot as PNG.
        """
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        
        fig, ax = plt.subplots(figsize=(10, 4))
        fig.patch.set_facecolor('#070913')
        ax.set_facecolor('#080a18')
        
        if f_max:
            mask = freq_hz <= f_max
            freq_hz = freq_hz[mask]
            psd_dbm = psd_dbm[mask]
        
        ax.plot(freq_hz, psd_dbm, color='#ff7700', linewidth=1.0)
        ax.fill_between(freq_hz, psd_dbm, -100, alpha=0.15, color='#ff7700')
        
        ax.set_title(title, color='#00e5ff', fontfamily='monospace', fontweight='bold')
        ax.set_xlabel('Frequency (Hz)', color='#8899bb')
        ax.set_ylabel('Power (dBm)', color='#8899bb')
        ax.tick_params(colors='#6c7a9c')
        ax.grid(True, alpha=0.2, color='#2a3a5a')
        ax.set_ylim(bottom=-80)
        
        path = os.path.join(self.output_dir, filename)
        fig.savefig(path, dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor())
        plt.close(fig)
        return path
    
    def export_measurement_table(self, measurements: list, filename: str) -> str:
        """
        Export a measurement comparison table to CSV.
        Each entry should have: param_name, theoretical, measured, error_pct, validated
        """
        return self.export_csv(measurements, filename,
                               headers=['param_name', 'theoretical', 'measured',
                                        'abs_error', 'pct_error', 'validated'])
    
    def generate_experiment_report(self, experiment_result: dict,
                                    params: dict = None,
                                    filename: str = 'experiment_report.html') -> str:
        """
        Generate an HTML experiment report.
        
        Args:
            experiment_result: dict from ExperimentRunner.run_experiment()
            params: simulation parameters dict
            filename: output filename
        
        Returns: full path to created file
        """
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        title = experiment_result.get('title', 'Experiment Report')
        conclusion = experiment_result.get('conclusion', 'N/A')
        
        # Build data table HTML
        table_html = ''
        data = experiment_result.get('data', [])
        if data and isinstance(data[0], dict):
            headers = list(data[0].keys())
            table_html += '<table><thead><tr>'
            for h in headers:
                table_html += f'<th>{h.replace("_", " ").upper()}</th>'
            table_html += '</tr></thead><tbody>'
            for row in data:
                table_html += '<tr>'
                for h in headers:
                    val = row[h]
                    if isinstance(val, float):
                        table_html += f'<td>{val:.4f}</td>'
                    else:
                        table_html += f'<td>{val}</td>'
                table_html += '</tr>'
            table_html += '</tbody></table>'
        
        # Build params HTML
        params_html = ''
        if params:
            params_html = '<h3>Simulation Parameters</h3><ul>'
            for k, v in params.items():
                params_html += f'<li><b>{k}:</b> {v}</li>'
            params_html += '</ul>'
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
  body {{ background: #070913; color: #d0d8f0; font-family: 'Consolas', monospace; padding: 20px; }}
  h1 {{ color: #00e5ff; border-bottom: 2px solid #1a2244; padding-bottom: 10px; }}
  h2 {{ color: #00ff88; }}
  h3 {{ color: #ffd700; }}
  table {{ border-collapse: collapse; width: 100%; margin: 10px 0; }}
  th {{ background: #101630; color: #00e5ff; padding: 8px; text-align: left; border: 1px solid #1a2244; }}
  td {{ padding: 6px 8px; border: 1px solid #1a2244; }}
  tr:nth-child(even) {{ background: #0a0e1f; }}
  .conclusion {{ background: #050711; border: 1px solid #ffd70044; border-radius: 6px; padding: 12px; color: #ffd700; margin: 15px 0; }}
  .footer {{ color: #4a5a80; font-size: 0.8em; margin-top: 30px; border-top: 1px solid #1a2244; padding-top: 10px; }}
  .label {{ background: #00e5ff22; color: #00e5ff; padding: 2px 8px; border-radius: 3px; font-size: 0.8em; }}
</style>
</head>
<body>
<h1>AM & FM Communication Systems Laboratory</h1>
<span class="label">EXPERIMENT REPORT</span>
<h2>{title}</h2>
<p><b>Generated:</b> {timestamp}</p>
{params_html}
<h3>Measurement Results</h3>
{table_html}
<div class="conclusion">
  <h3>Engineering Conclusion</h3>
  <p>{conclusion}</p>
</div>
<div class="footer">
  <p>Generated by AM & FM Communication Systems Laboratory - Python + PyQt6 + NumPy + SciPy</p>
  <p>All measurements are simulation-based. Not validated against physical hardware.</p>
</div>
</body>
</html>
"""
        path = os.path.join(self.output_dir, filename)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(html)
        return path
