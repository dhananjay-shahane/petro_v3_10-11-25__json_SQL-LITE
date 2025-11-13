"""
Professional Matplotlib Well Log Plotting Module
Adapted from Logs_CPI_TempelatesTwo.py for Linux/Replit environment
Generates publication-quality PDF/PNG plots with professional styling
"""

import os
import io
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.colors import ListedColormap, BoundaryNorm
from matplotlib.patches import Rectangle
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional, Dict, List, Tuple

# Set default font size
plt.rcParams['font.size'] = 8
plt.rcParams['font.family'] = 'sans-serif'


class MatplotlibCPIPlotter:
    """
    Creates professional well log plots using matplotlib with CPI layout styling
    """
    
    def __init__(self):
        self.layout_config = None
        
    def calculate_fig_height(self, depth_meters: float, scale: int = 200) -> float:
        """
        Calculate figure height in inches for depth plots where:
        - depth_meters: Total depth in meters
        - scale: 1 cm on plot = [scale] cm in reality (e.g., 200 means 1cm=200cm)
        
        Args:
            depth_meters: Total depth in meters
            scale: 1 cm on plot = [scale] cm in reality (default: 200)
        
        Returns:
            float: Figure height in inches (for matplotlib's figsize)
        """
        # Convert depth from meters to cm
        depth_cm = depth_meters * 100
        
        # Calculate plot height in cm: (real depth cm) / scale
        plot_height_cm = depth_cm / scale
        
        # Convert cm to inches (1 inch = 2.54 cm)
        plot_height_inches = plot_height_cm / 2.54
        
        return plot_height_inches
    
    def derive_tick_intervals(self, depth_scale: int) -> Tuple[int, int]:
        """
        Derive major and minor tick intervals based on depth scale
        
        Args:
            depth_scale: The depth scale value
            
        Returns:
            Tuple of (major_interval, minor_interval)
        """
        tick_map = {
            200: (5, 1),
            500: (25, 5),
            640: (25, 5),
            1000: (50, 10),
            2000: (100, 25),
            10000: (200, 50),
        }
        
        closest_scale = min(tick_map.keys(), key=lambda k: abs(k - depth_scale))
        return tick_map.get(closest_scale, (25, 5))
    
    def configure_depth_axis(self, ax, depth_min: float, depth_max: float, 
                            major_tick: int, minor_tick: int):
        """
        Configure depth axis with professional styling
        
        Args:
            ax: Matplotlib axis object
            depth_min: Minimum depth
            depth_max: Maximum depth
            major_tick: Major tick interval
            minor_tick: Minor tick interval
        """
        # Set inverted depth scale (depth increases downward)
        ax.set_ylim(depth_max, depth_min)
        
        # Generate ticks
        first_major = np.ceil(depth_min / major_tick) * major_tick
        last_major = np.floor(depth_max / major_tick) * major_tick
        major_ticks = np.arange(first_major, last_major + major_tick, major_tick)
        
        ax.set_yticks(major_ticks)
        ax.set_yticklabels([f"{int(t)}" for t in major_ticks], fontsize=9)
        
        # Minor ticks
        first_minor = np.ceil(depth_min / minor_tick) * minor_tick
        last_minor = np.floor(depth_max / minor_tick) * minor_tick
        minor_ticks = np.arange(first_minor, last_minor + minor_tick, minor_tick)
        minor_ticks = [t for t in minor_ticks if t not in major_ticks]
        ax.set_yticks(minor_ticks, minor=True)
        
        # Grid styling - professional appearance
        ax.grid(which='major', axis='y', color='black', linestyle='-', linewidth=1.5, zorder=0)
        ax.grid(which='minor', axis='y', color='#666666', linestyle='-', linewidth=0.8, zorder=0)
        
        # Tick styling
        ax.tick_params(axis='y', which='both', left=False, right=False, labelleft=True)
        ax.tick_params(axis='x', which='both', bottom=False, top=True, labelbottom=False, labeltop=True)
    
    def plot_wireline_track(self, ax, df_logs: pd.DataFrame, depth_col: str, 
                           curve_configs: List[Dict], depth_min: float, depth_max: float):
        """
        Plot wireline track with multiple curves
        
        Args:
            ax: Matplotlib axis
            df_logs: DataFrame with log data
            depth_col: Name of depth column
            curve_configs: List of curve configuration dicts
            depth_min: Minimum depth
            depth_max: Maximum depth
        """
        for curve_config in curve_configs:
            curve_name = curve_config['name']
            
            if curve_name not in df_logs.columns:
                continue
            
            curve_data = df_logs[curve_name].values
            depth_data = df_logs[depth_col].values
            
            # Filter valid data
            valid_mask = ~np.isnan(curve_data) & ~np.isnan(depth_data)
            valid_curve = curve_data[valid_mask]
            valid_depth = depth_data[valid_mask]
            
            if len(valid_curve) == 0:
                continue
            
            # Plot curve
            color = curve_config.get('color', 'blue')
            linestyle = curve_config.get('linestyle', 'solid')
            linewidth = curve_config.get('line_thickness', 1)
            
            linestyle_map = {'solid': '-', 'dashed': '--', 'dotted': ':'}
            ls = linestyle_map.get(linestyle, '-')
            
            ax.plot(valid_curve, valid_depth, color=color, linestyle=ls, linewidth=linewidth)
            
            # Handle fill
            baseline = curve_config.get('baseline')
            if baseline is not None:
                left_fill = curve_config.get('left_fill_color')
                right_fill = curve_config.get('right_fill_color')
                
                if right_fill:
                    ax.fill_betweenx(valid_depth, baseline, valid_curve, 
                                    where=(valid_curve >= baseline),
                                    facecolor=right_fill, alpha=0.3, interpolate=True)
                if left_fill:
                    ax.fill_betweenx(valid_depth, baseline, valid_curve,
                                    where=(valid_curve < baseline),
                                    facecolor=left_fill, alpha=0.3, interpolate=True)
        
        # Set x-axis limits from first curve config with min/max
        for curve_config in curve_configs:
            x_min = curve_config.get('min')
            x_max = curve_config.get('max')
            if x_min is not None and x_max is not None:
                ax.set_xlim(x_min, x_max)
                break
    
    def create_cpi_plot_from_xml(self, df_logs: pd.DataFrame, xml_layout_path: str,
                                 well_name: str, output_path: str, 
                                 df_tops: Optional[pd.DataFrame] = None,
                                 output_format: str = 'pdf') -> str:
        """
        Create professional CPI layout plot from XML configuration
        
        Args:
            df_logs: DataFrame with log data (must have DEPTH column)
            xml_layout_path: Path to XML layout file
            well_name: Well name for title
            output_path: Output file path
            df_tops: Optional DataFrame with tops data
            output_format: 'pdf' or 'png'
            
        Returns:
            Path to generated file
        """
        # Parse XML layout
        tree = ET.parse(xml_layout_path)
        root = tree.getroot()
        
        # Get global properties
        depth_scale = int(root.get('depth_scale', '640'))
        major_tick = int(root.get('major_y_tick', '25'))
        minor_tick = int(root.get('minor_y_tick', '5'))
        grid_color = root.get('grid_color', 'lightgray')
        wh_font_size = int(root.get('wh_font_size', '12'))
        
        # Parse tracks
        tracks = []
        for track_elem in root.findall('Track'):
            track = {
                'name': track_elem.get('name'),
                'type': track_elem.get('type', 'wireline'),
                'width': float(track_elem.get('width', '0.5')),
                'curves': []
            }
            
            for curve_elem in track_elem.findall('Curve'):
                curve = {
                    'name': curve_elem.get('name'),
                    'color': curve_elem.get('color', 'blue'),
                    'linestyle': curve_elem.get('linestyle', 'solid'),
                    'line_thickness': float(curve_elem.get('line_thickness', '1')),
                    'min': float(curve_elem.get('min')) if curve_elem.get('min') else None,
                    'max': float(curve_elem.get('max')) if curve_elem.get('max') else None,
                    'baseline': float(curve_elem.get('baseline')) if curve_elem.get('baseline') else None,
                    'left_fill_color': curve_elem.get('left_fill_color'),
                    'right_fill_color': curve_elem.get('right_fill_color'),
                }
                track['curves'].append(curve)
            
            tracks.append(track)
        
        # Get depth range
        depth_col = 'DEPTH'
        if depth_col not in df_logs.columns:
            raise ValueError(f"Column '{depth_col}' not found in data")
        
        depth_data = df_logs[depth_col].dropna()
        depth_min = depth_data.min()
        depth_max = depth_data.max()
        depth_range = depth_max - depth_min
        
        # Calculate figure dimensions
        fig_height = self.calculate_fig_height(depth_range, depth_scale)
        fig_height = max(8, min(fig_height, 20))  # Clamp between 8 and 20 inches
        
        num_tracks = len(tracks)
        track_widths = [t['width'] for t in tracks]
        total_width = sum(track_widths)
        widths_ratios = [w / total_width for w in track_widths]
        
        fig_width = 11  # Standard letter width
        
        # Create figure
        fig = plt.figure(figsize=(fig_width, fig_height))
        
        # Add main title with professional styling
        fig.suptitle(f'WELL LOG PLOT - {well_name}', 
                    fontsize=wh_font_size + 4, fontweight='bold', y=0.985,
                    bbox=dict(boxstyle='square,pad=0.5', facecolor='lightgray', edgecolor='black', linewidth=2))
        
        # Create grid spec with tighter spacing for professional appearance
        gs = GridSpec(1, num_tracks, figure=fig, width_ratios=widths_ratios,
                     left=0.05, right=0.98, top=0.93, bottom=0.04, wspace=0.001)
        
        # Plot each track
        axes = []
        for idx, track in enumerate(tracks):
            ax = fig.add_subplot(gs[0, idx])
            axes.append(ax)
            
            # Set track title with professional styling
            ax.set_title(track['name'], fontsize=9, fontweight='bold', pad=8,
                        bbox=dict(boxstyle='square,pad=0.3', facecolor='#e0e0e0', 
                                 edgecolor='black', linewidth=1.5))
            
            # Configure depth axis
            if idx == 0:
                self.configure_depth_axis(ax, depth_min, depth_max, major_tick, minor_tick)
                ax.set_ylabel('Depth (m)', fontsize=11, fontweight='bold')
            else:
                self.configure_depth_axis(ax, depth_min, depth_max, major_tick, minor_tick)
                ax.set_yticklabels([])  # Hide labels for non-first tracks
            
            # Plot based on track type
            track_type = track['type']
            
            if track_type == 'wireline' and track['curves']:
                self.plot_wireline_track(ax, df_logs, depth_col, track['curves'], 
                                        depth_min, depth_max)
            elif track_type == 'scale':
                # Depth scale track - just show grid
                ax.set_xlim(0, 1)
                ax.set_xticks([])
            elif track_type == 'TOPS' and df_tops is not None:
                self.plot_tops_track(ax, df_tops, depth_min, depth_max)
            
            # Add professional thick borders
            for spine in ax.spines.values():
                spine.set_linewidth(3)
                spine.set_color('black')
                spine.set_zorder(10)
            
            # Add vertical grid lines between tracks for professional table appearance
            if track_type == 'wireline' and track['curves']:
                for curve_config in track['curves']:
                    x_min = curve_config.get('min')
                    x_max = curve_config.get('max')
                    if x_min is not None and x_max is not None:
                        ax.grid(which='major', axis='x', color='#cccccc', linestyle='-', linewidth=0.8, alpha=0.7)
                        break
        
        # Save figure
        output_file = f"{output_path}.{output_format}"
        
        if output_format == 'pdf':
            with PdfPages(output_file) as pdf:
                pdf.savefig(fig, dpi=300, bbox_inches='tight')
        else:  # PNG
            fig.savefig(output_file, dpi=300, bbox_inches='tight', facecolor='white')
        
        plt.close(fig)
        
        print(f"[Matplotlib CPI] Plot saved to: {output_file}")
        return output_file
    
    def plot_tops_track(self, ax, df_tops: pd.DataFrame, depth_min: float, depth_max: float):
        """Plot formation tops"""
        ax.set_xlim(0, 1)
        ax.set_xticks([])
        
        if df_tops.empty:
            return
        
        # Filter tops in range
        tops_in_range = df_tops[
            (df_tops['depth'] >= depth_min) & 
            (df_tops['depth'] <= depth_max)
        ]
        
        for _, top_row in tops_in_range.iterrows():
            depth = top_row['depth']
            top_name = top_row.get('top_name', top_row.get('TOP', 'Unknown'))
            
            # Draw horizontal line
            ax.axhline(y=depth, color='green', linestyle='--', linewidth=2)
            
            # Add label
            ax.text(0.5, depth, top_name, ha='center', va='bottom',
                   fontsize=9, fontweight='bold', color='green',
                   bbox=dict(boxstyle='round,pad=0.3', facecolor='white', 
                            edgecolor='green', alpha=0.8))
