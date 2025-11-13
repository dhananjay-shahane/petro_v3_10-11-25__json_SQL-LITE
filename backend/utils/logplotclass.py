"""
Log Plot Classes (Flask/Web adapted from PyQt logplotclass.py)
Contains matplotlib-based plotting classes for well logs
"""

import matplotlib
matplotlib.use('Agg')  # Non-GUI backend
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
import io
import base64
import numpy as np


class MainFigureWidget:
    """
    Main figure widget for well log plotting
    Adapted from PyQt version for Flask backend
    """
    
    def __init__(self):
        self.figure = Figure(figsize=(10, 12))
        self.canvas = FigureCanvasAgg(self.figure)
        self.axes = []
    
    def plot(self, data=None):
        """
        Create initial plot
        
        Args:
            data: Optional data to plot
        """
        ax = self.figure.add_subplot(111)
        
        if data:
            ax.plot(data.get('x', [1, 2, 3]), data.get('y', [1, 4, 9]), label='Main Data')
        else:
            ax.plot([1, 2, 3], [1, 4, 9], label='Main Data')
        
        ax.set_title("Main Plot")
        ax.set_ylabel("Common Y-Axis")
        ax.legend()
        self.axes.append(ax)
        
        return ax
    
    def to_base64(self):
        """Convert figure to base64 PNG"""
        buf = io.BytesIO()
        self.figure.savefig(buf, format='png', dpi=100, bbox_inches='tight')
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode('utf-8')
        buf.close()
        return img_base64


class MatplotlibDockWidget:
    """
    Dock widget for individual log track
    Adapted from PyQt version for Flask backend
    """
    
    def __init__(self, title, shared_axis=None):
        self.title = title
        self.shared_axis = shared_axis
        self.figure = None
        self.canvas = None
        self.frame_data = {}
    
    def create_frame(self, log_data, index_data):
        """
        Create a matplotlib figure for a single log track
        
        Args:
            log_data: Log values to plot
            index_data: Depth/index values
            
        Returns:
            Dictionary with figure data
        """
        # Create figure for this track
        height_in_inches = 200 / 2.54  # Convert 200 cm to inches
        self.figure = Figure(figsize=(4, height_in_inches))
        self.canvas = FigureCanvasAgg(self.figure)
        
        # Create subplot
        ax = self.figure.add_subplot(111)
        
        # Adjust margins
        self.figure.subplots_adjust(left=0.15, right=0.95, top=0.95, bottom=0.05)
        
        # Filter valid data
        valid_data = [(idx, val) for idx, val in zip(index_data, log_data) 
                     if val is not None and not np.isnan(val)]
        
        if valid_data:
            valid_idx, valid_vals = zip(*valid_data)
            
            # Plot
            ax.plot(valid_vals, valid_idx, linewidth=1, color='blue')
            ax.set_title(self.title, fontsize=10)
            ax.set_ylabel("Depth")
            
            # Move x-axis to top
            ax.xaxis.set_ticks_position('top')
            ax.xaxis.tick_top()
            
            # Invert y-axis (depth increases downward)
            ax.invert_yaxis()
            
            # Grid
            ax.grid(True, alpha=0.3)
        
        self.frame_data = {
            'title': self.title,
            'figure': self.figure,
            'ax': ax
        }
        
        return self.frame_data
    
    def to_base64(self):
        """Convert dock figure to base64 PNG"""
        if self.figure:
            buf = io.BytesIO()
            self.figure.savefig(buf, format='png', dpi=100, bbox_inches='tight')
            buf.seek(0)
            img_base64 = base64.b64encode(buf.read()).decode('utf-8')
            buf.close()
            return img_base64
        return None


class FigureWidget:
    """
    Figure widget for rendering matplotlib plots
    Adapted from PyQt version for Flask backend
    """
    
    def __init__(self, shared_axis=None):
        self.shared_axis = shared_axis
        self.figure = Figure(figsize=(10, 12))
        self.canvas = FigureCanvasAgg(self.figure)
    
    def plot(self, log_data, index_data, title="Log Plot"):
        """
        Plot log data
        
        Args:
            log_data: Log values
            index_data: Depth/index values
            title: Plot title
        """
        ax = self.figure.add_subplot(111)
        
        # Adjust margins
        self.figure.subplots_adjust(left=0.1, right=0.9, top=0.9, bottom=0.1)
        
        # Filter valid data
        valid_data = [(idx, val) for idx, val in zip(index_data, log_data) 
                     if val is not None and not np.isnan(val)]
        
        if valid_data:
            valid_idx, valid_vals = zip(*valid_data)
            
            # Plot
            ax.plot(valid_vals, valid_idx, label=title, linewidth=1)
            ax.set_title(title)
            ax.set_ylabel("Depth")
            ax.legend()
            
            # Move x-axis to top
            ax.xaxis.set_ticks_position('top')
            ax.xaxis.tick_top()
            
            # Invert y-axis
            ax.invert_yaxis()
            
            # Grid
            ax.grid(True, alpha=0.3)
    
    def to_base64(self):
        """Convert figure to base64 PNG"""
        buf = io.BytesIO()
        self.figure.savefig(buf, format='png', dpi=100, bbox_inches='tight')
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode('utf-8')
        buf.close()
        return img_base64


def create_multi_track_plot(tracks_data, figsize=(12, 10)):
    """
    Create a multi-track well log plot
    
    Args:
        tracks_data: List of dicts with 'name', 'log', 'index' keys
        figsize: Figure size tuple
        
    Returns:
        Base64 encoded PNG image
    """
    if not tracks_data:
        return None
    
    num_tracks = len(tracks_data)
    fig = Figure(figsize=figsize)
    
    # Determine shared index
    shared_index = None
    for track in tracks_data:
        if track.get('index') is not None:
            shared_index = track['index']
            break
    
    if shared_index is None:
        return None
    
    # Create subplots with shared y-axis
    axes = []
    for i, track in enumerate(tracks_data):
        if i == 0:
            ax = fig.add_subplot(1, num_tracks, i + 1)
        else:
            ax = fig.add_subplot(1, num_tracks, i + 1, sharey=axes[0])
        
        axes.append(ax)
        
        # Plot
        log_values = track.get('log', [])
        index_values = track.get('index', shared_index)
        
        valid_data = [(idx, val) for idx, val in zip(index_values, log_values) 
                     if val is not None and not np.isnan(val)]
        
        if valid_data:
            valid_idx, valid_vals = zip(*valid_data)
            ax.plot(valid_vals, valid_idx, linewidth=1, color='blue')
            
            # Configure axes
            ax.set_xlabel(track.get('name', f'Track {i+1}'), fontsize=10)
            ax.xaxis.set_label_position('top')
            ax.xaxis.tick_top()
            
            if i == 0:
                ax.invert_yaxis()
                ax.set_ylabel(track.get('index_name', 'DEPTH'), fontsize=10)
            else:
                ax.tick_params(axis='y', labelleft=False)
            
            ax.grid(True, alpha=0.3)
    
    # Convert to base64
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=100, bbox_inches='tight')
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode('utf-8')
    buf.close()
    plt.close(fig)
    
    return img_base64
