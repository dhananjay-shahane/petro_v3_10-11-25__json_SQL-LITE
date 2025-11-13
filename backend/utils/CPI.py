"""
Cross Plot Module (Flask/Web adapted for petrophysics)
Provides functionality for creating cross plots between two well logs with matplotlib
Based on the same pattern as LogPlot.py from GitHub repo
"""

import matplotlib
matplotlib.use('Agg')  # Use non-GUI backend for web
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
import io
import base64
import numpy as np


class CrossPlotManager:
    """
    Manages cross plot functionality for well logs
    Adapted for Flask web backend
    """
    
    def __init__(self):
        self.figure = None
    
    def create_cross_plot(self, well_data, x_log_name, y_log_name):
        """
        Create a cross plot between two logs
        Uses the same data search pattern as LogPlot.py
        
        Args:
            well_data: Well object with datasets
            x_log_name: Name of X-axis log
            y_log_name: Name of Y-axis log
            
        Returns:
            Base64 encoded PNG image
        """
        print(f"[CrossPlot] Creating cross plot: {y_log_name} vs {x_log_name}")
        
        # Search for logs using same pattern as LogPlot.py
        x_log_data = None
        y_log_data = None
        
        print(f"[CrossPlot] Searching for X-log: {x_log_name}")
        for dataset in well_data.datasets:
            for well_log in dataset.well_logs:
                if well_log.name == x_log_name:
                    x_log_data = well_log.log
                    print(f"[CrossPlot] Found X-log: {x_log_name} with {len(x_log_data)} points")
                    break
            if x_log_data is not None:
                break
        
        print(f"[CrossPlot] Searching for Y-log: {y_log_name}")
        for dataset in well_data.datasets:
            for well_log in dataset.well_logs:
                if well_log.name == y_log_name:
                    y_log_data = well_log.log
                    print(f"[CrossPlot] Found Y-log: {y_log_name} with {len(y_log_data)} points")
                    break
            if y_log_data is not None:
                break
        
        if x_log_data is None:
            print(f"[CrossPlot] Error: X-log '{x_log_name}' not found")
            return None
        
        if y_log_data is None:
            print(f"[CrossPlot] Error: Y-log '{y_log_name}' not found")
            return None
        
        # Ensure both logs have the same length
        if len(x_log_data) != len(y_log_data):
            min_len = min(len(x_log_data), len(y_log_data))
            print(f"[CrossPlot] Warning: Logs have different lengths, truncating to {min_len}")
            x_log_data = x_log_data[:min_len]
            y_log_data = y_log_data[:min_len]
        
        # Filter out NaN and None values
        valid_indices = []
        for i in range(len(x_log_data)):
            x_val = x_log_data[i]
            y_val = y_log_data[i]
            if (x_val is not None and y_val is not None and 
                not np.isnan(x_val) and not np.isnan(y_val) and
                np.isfinite(x_val) and np.isfinite(y_val)):
                valid_indices.append(i)
        
        if not valid_indices:
            print("[CrossPlot] Error: No valid data points found")
            return None
        
        x_valid = [x_log_data[i] for i in valid_indices]
        y_valid = [y_log_data[i] for i in valid_indices]
        
        print(f"[CrossPlot] Valid data points: {len(valid_indices)} out of {len(x_log_data)}")
        
        # Create the figure
        fig = Figure(figsize=(8, 8))
        ax = fig.add_subplot(111)
        
        # Scatter plot
        ax.scatter(x_valid, y_valid, alpha=0.5, s=10, color='#2563eb', edgecolors='none')
        
        # Add trend line if we have enough points
        if len(x_valid) > 1:
            try:
                # Calculate linear regression
                coeffs = np.polyfit(x_valid, y_valid, 1)
                poly_func = np.poly1d(coeffs)
                
                # Create trend line
                x_trend = np.linspace(min(x_valid), max(x_valid), 100)
                y_trend = poly_func(x_trend)
                
                ax.plot(x_trend, y_trend, 'r--', linewidth=2, alpha=0.8, 
                       label=f'y = {coeffs[0]:.4f}x + {coeffs[1]:.4f}')
                
                # Calculate R-squared
                y_pred = poly_func(x_valid)
                ss_res = np.sum((np.array(y_valid) - y_pred) ** 2)
                ss_tot = np.sum((np.array(y_valid) - np.mean(y_valid)) ** 2)
                r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
                
                print(f"[CrossPlot] Trend line: y = {coeffs[0]:.4f}x + {coeffs[1]:.4f}, R² = {r_squared:.4f}")
                
                # Add R-squared to the plot
                ax.text(0.05, 0.95, f'R² = {r_squared:.4f}', 
                       transform=ax.transAxes, fontsize=10,
                       verticalalignment='top',
                       bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
                
                ax.legend(loc='lower right', fontsize=9)
            except Exception as e:
                print(f"[CrossPlot] Warning: Could not create trend line: {e}")
        
        # Styling
        ax.set_xlabel(x_log_name, fontsize=12, fontweight='bold')
        ax.set_ylabel(y_log_name, fontsize=12, fontweight='bold')
        ax.set_title(f'{y_log_name} vs {x_log_name}', fontsize=14, fontweight='bold', pad=20)
        ax.grid(True, alpha=0.3, linestyle='--', linewidth=0.5)
        
        # Set background
        ax.set_facecolor('#f8fafc')
        fig.patch.set_facecolor('white')
        
        # Tight layout
        fig.tight_layout()
        
        # Convert to base64 PNG
        buffer = io.BytesIO()
        fig.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.read()).decode()
        plt.close(fig)
        
        print(f"[CrossPlot] Plot generated successfully, image size: {len(image_base64)} characters")
        return image_base64
