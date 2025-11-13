"""
CPI Layout Plotting Module with Plotly
Converts matplotlib-based CPI well log layouts to interactive Plotly visualizations
"""

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
import json
import os
from typing import Dict, List, Optional, Tuple
import xml.etree.ElementTree as ET


class CPIPlotlyManager:
    """
    Manages CPI (Complete Petrophysical Interpretation) layout plotting with Plotly.
    Converts complex multi-track well log displays from matplotlib to interactive Plotly.
    """
    
    def __init__(self):
        self.layout_config = None
        self.track_dict = {}
        self.controlling_track_name = None
        self.controlling_depth_log = None
        
    def parse_xml_layout(self, xml_path: str) -> Dict:
        """
        Parse XML layout configuration file for CPI plots.
        
        Args:
            xml_path: Path to XML layout file
            
        Returns:
            Dictionary with complete layout configuration
        """
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()
            
            # Parse global properties
            global_props = {
                'depth_scale': int(root.get('depth_scale', '640')),
                'major_y_tick': int(root.get('major_y_tick', '25')),
                'minor_y_tick': int(root.get('minor_y_tick', '5')),
                'grid_color': root.get('grid_color', 'lightgray'),
                'wh_font_size': int(root.get('wh_font_size', '12')),
                'wh_color': root.get('wh_color', 'black'),
                'th_font_size': int(root.get('th_font_size', '10')),
                'curve_names_font_size': int(root.get('curve_names_font_size', '8')),
                'lr_limits_font_size': int(root.get('lr_limits_font_size', '8')),
                'fluid_color_file_name': root.get('fluid_color_file_name', None),
            }
            
            tracks = []
            # Parse each track
            for track_elem in root.findall('Track'):
                track = {
                    'name': track_elem.get('name'),
                    'type': track_elem.get('type', 'wireline'),
                    'width': float(track_elem.get('width', '0.5')),
                    'controls': track_elem.get('controls', 'false').lower() == 'true',
                    'ygrid': track_elem.get('ygrid', 'true').lower() == 'true',
                    'xgrid': track_elem.get('xgrid', 'true').lower() == 'true',
                    'vgrid': track_elem.get('vgrid', 'true').lower() == 'true',
                    'curves': []
                }
                
                # Parse curves within track
                for curve_elem in track_elem.findall('Curve'):
                    curve = {
                        'name': curve_elem.get('name'),
                        'color': curve_elem.get('color', 'blue'),
                        'linestyle': curve_elem.get('linestyle', 'solid'),
                        'line_thickness': float(curve_elem.get('line_thickness') or 1),
                        'min': float(curve_elem.get('min')) if curve_elem.get('min') is not None else None,
                        'max': float(curve_elem.get('max')) if curve_elem.get('max') is not None else None,
                        'log_scale': str(curve_elem.get('log_scale', 'false')).lower() == 'true',
                        'reversed': str(curve_elem.get('reversed', 'false')).lower() == 'true',
                        'baseline': float(curve_elem.get('baseline')) if curve_elem.get('baseline') is not None else None,
                        'left_fill_color': curve_elem.get('left_fill_color'),
                        'right_fill_color': curve_elem.get('right_fill_color'),
                        'plot': curve_elem.get('plot', 'line'),
                        'zone_label_spacing': int(curve_elem.get('zone_label_spacing') or 15),
                        'decimals': int(curve_elem.get('decimals') or 2),
                    }
                    track['curves'].append(curve)
                
                tracks.append(track)
            
            return {
                'global_properties': global_props,
                'tracks': tracks
            }
            
        except Exception as e:
            print(f"Error parsing XML layout: {e}")
            raise
    
    def consolidate_tracks(self, layout: Dict) -> None:
        """
        Consolidate track information and find the controlling track.
        
        Args:
            layout: Parsed XML layout dictionary
        """
        self.track_dict = {}
        
        for track in layout.get('tracks', []):
            track_name = track['name']
            if track_name not in self.track_dict:
                self.track_dict[track_name] = track
            else:
                # Extend curves if track with same name exists
                self.track_dict[track_name]['curves'].extend(track['curves'])
            
            # Find controlling track
            if track.get('controls', False):
                if self.controlling_track_name is not None:
                    raise ValueError("Only one track can be marked as 'controls=True'")
                self.controlling_track_name = track_name
                if 'curves' in track and track['curves']:
                    self.controlling_depth_log = track['curves'][0]['name']
        
        if self.controlling_track_name is None:
            raise ValueError("No track with 'controls=True' found in layout")
    
    def create_cpi_plot(
        self,
        df_logs: pd.DataFrame,
        xml_layout_path: str,
        well_name: str,
        df_tops: Optional[pd.DataFrame] = None,
        df_perfs: Optional[pd.DataFrame] = None,
        spec_folder: Optional[str] = None
    ) -> str:
        """
        Create a complete CPI layout plot with Plotly.
        
        Args:
            df_logs: DataFrame containing well log data (must have DEPTH column)
            xml_layout_path: Path to XML layout configuration file
            well_name: Name of the well
            df_tops: Optional DataFrame with formation tops (columns: top_name, depth)
            df_perfs: Optional DataFrame with perforation data
            spec_folder: Optional folder containing color specification files
            
        Returns:
            JSON string of Plotly figure
        """
        print('[CPI Plotly] Creating CPI layout plot...')
        
        # Parse layout
        layout = self.parse_xml_layout(xml_layout_path)
        self.consolidate_tracks(layout)
        
        global_props = layout['global_properties']
        
        # Get depth range from controlling log
        if self.controlling_depth_log not in df_logs.columns:
            raise ValueError(f"Controlling depth log '{self.controlling_depth_log}' not found in data")
        
        depth_data = df_logs[self.controlling_depth_log].dropna()
        depth_min = depth_data.min()
        depth_max = depth_data.max()
        depth_range = depth_max - depth_min
        
        print(f'[CPI Plotly] Depth range: {depth_min:.2f} - {depth_max:.2f} m ({depth_range:.2f} m)')
        
        # Calculate track layout
        track_names_ordered = list(self.track_dict.keys())
        track_widths = [self.track_dict[name]['width'] for name in track_names_ordered]
        total_width = sum(track_widths)
        column_widths = [w / total_width for w in track_widths]
        
        num_tracks = len(track_names_ordered)
        print(f'[CPI Plotly] Creating {num_tracks} tracks: {track_names_ordered}')
        
        # Create subplots with shared Y-axis
        subplot_titles = track_names_ordered
        
        fig = make_subplots(
            rows=1,
            cols=num_tracks,
            shared_yaxes=True,
            column_widths=column_widths,
            subplot_titles=subplot_titles,
            horizontal_spacing=0.001,
            vertical_spacing=0.01
        )
        
        # Update subplot titles to be more professional with background boxes
        for annotation in fig.layout.annotations:
            annotation.font.size = global_props['th_font_size'] + 3
            annotation.font.family = 'Arial Black'
            annotation.font.color = 'black'
            annotation.y = annotation.y + 0.015
            annotation.bgcolor = '#e0e0e0'
            annotation.bordercolor = 'black'
            annotation.borderwidth = 2
            annotation.borderpad = 4
        
        # Plot each track
        for col_idx, track_name in enumerate(track_names_ordered, start=1):
            track_data = self.track_dict[track_name]
            track_type = track_data.get('type', 'wireline')
            
            print(f'[CPI Plotly] Plotting track {col_idx}: {track_name} (type: {track_type})')
            
            if track_type == 'wireline':
                self._plot_wireline_track(
                    fig, col_idx, track_data, df_logs, pd.Series(depth_data), global_props
                )
            elif track_type == 'scale':
                self._plot_scale_track(
                    fig, col_idx, track_data, df_logs, pd.Series(depth_data), global_props
                )
            elif track_type == 'TOPS' and df_tops is not None:
                self._plot_tops_track(
                    fig, col_idx, track_data, df_tops, float(depth_min), float(depth_max)
                )
            elif track_type == 'FLUID':
                self._plot_fluid_track(
                    fig, col_idx, track_data, df_logs, pd.Series(depth_data), spec_folder, global_props
                )
            elif track_type == 'PERF' and df_perfs is not None:
                self._plot_perf_track(
                    fig, col_idx, track_data, df_perfs, float(depth_min), float(depth_max)
                )
            elif track_type == 'TEXT':
                self._plot_text_track(
                    fig, col_idx, track_data, df_logs, pd.Series(depth_data)
                )
            
            # Add professional x-axis styling for each track
            xaxis_key = f'xaxis{col_idx}' if col_idx > 1 else 'xaxis'
            fig.update_layout({
                xaxis_key: dict(
                    showline=True,
                    linewidth=3,
                    linecolor='black',
                    mirror=True,
                    ticks='outside',
                    ticklen=6,
                    tickwidth=2,
                    tickcolor='black',
                    tickfont=dict(size=global_props['curve_names_font_size'] + 2, family='Arial', color='black'),
                    showgrid=True,
                    gridcolor='#cccccc',
                    gridwidth=1
                )
            })
        
        # Calculate professional figure height based on depth scale
        # depth_scale represents cm in real depth per cm on plot
        depth_scale = global_props.get('depth_scale', 640)
        # Convert to appropriate figure height
        depth_cm = depth_range * 100  # Convert meters to cm
        plot_height_cm = depth_cm / depth_scale
        plot_height_inches = plot_height_cm / 2.54
        plot_height_px = int(plot_height_inches * 96)  # 96 DPI
        
        # Ensure reasonable bounds
        plot_height_px = max(600, min(plot_height_px, 2000))
        
        print(f'[CPI Plotly] Calculated plot height: {plot_height_px}px (depth_scale={depth_scale})')
        
        # Update layout with professional styling
        fig.update_layout(
            title=dict(
                text=f'<b>WELL LOG PLOT - {well_name}</b>',
                x=0.5,
                xanchor='center',
                font=dict(size=global_props['wh_font_size'] + 4, color=global_props['wh_color'], family='Arial Black'),
                pad=dict(t=10, b=10)
            ),
            height=plot_height_px,
            showlegend=False,
            plot_bgcolor='white',
            paper_bgcolor='#f5f5f5',
            margin=dict(l=70, r=70, t=130, b=70),
            font=dict(family='Arial, sans-serif', size=11, color='black')
        )
        
        # Configure all Y-axes (shared, inverted for depth) with professional styling
        fig.update_yaxes(
            autorange='reversed',  # Depth increases downward
            title_text='<b>Depth (m)</b>',
            title_font=dict(size=12, family='Arial Black'),
            showgrid=True,
            gridcolor='black',
            gridwidth=1.5,
            dtick=global_props['major_y_tick'],
            minor=dict(
                showgrid=True,
                gridcolor='#666666',
                gridwidth=1,
                dtick=global_props['minor_y_tick']
            ),
            tickfont=dict(size=10, color='black', family='Arial'),
            showline=True,
            linewidth=3,
            linecolor='black',
            mirror=True,
            row=1,
            col=1
        )
        
        # Hide Y-axis for other columns (shared) but keep grid
        for col_idx in range(2, num_tracks + 1):
            fig.update_yaxes(
                showticklabels=False,
                showgrid=True,
                gridcolor='black',
                gridwidth=1.5,
                showline=True,
                linewidth=3,
                linecolor='black',
                mirror=True,
                row=1,
                col=col_idx
            )
        
        # Add professional vertical borders between tracks
        shapes = []
        annotations = []
        
        # Get track positions for borders
        for i in range(1, num_tracks + 1):
            xaxis_key = 'xaxis' if i == 1 else f'xaxis{i}'
            xaxis_obj = getattr(fig.layout, xaxis_key, None)
            
            if xaxis_obj and hasattr(xaxis_obj, 'domain') and xaxis_obj.domain:
                left_edge = xaxis_obj.domain[0]
                right_edge = xaxis_obj.domain[1]
                
                # Add left border (except for first track)
                if i > 1:
                    shapes.append(
                        dict(
                            type='line',
                            xref='paper',
                            yref='paper',
                            x0=left_edge,
                            y0=0,
                            x1=left_edge,
                            y1=1,
                            line=dict(color='black', width=3),
                            layer='above'
                        )
                    )
                
                # Add right border for last track
                if i == num_tracks:
                    shapes.append(
                        dict(
                            type='line',
                            xref='paper',
                            yref='paper',
                            x0=right_edge,
                            y0=0,
                            x1=right_edge,
                            y1=1,
                            line=dict(color='black', width=3),
                            layer='above'
                        )
                    )
        
        # Add top and bottom borders
        shapes.append(
            dict(
                type='line',
                xref='paper',
                yref='paper',
                x0=0,
                y0=1,
                x1=1,
                y1=1,
                line=dict(color='black', width=3),
                layer='above'
            )
        )
        shapes.append(
            dict(
                type='line',
                xref='paper',
                yref='paper',
                x0=0,
                y0=0,
                x1=1,
                y1=0,
                line=dict(color='black', width=3),
                layer='above'
            )
        )
        
        if shapes:
            fig.update_layout(shapes=shapes)
            print(f'[CPI Plotly] Added {len(shapes)} professional borders')
        
        print('[CPI Plotly] Plot created successfully')
        return json.dumps(fig.to_dict())
    
    def _plot_wireline_track(
        self,
        fig: go.Figure,
        col_idx: int,
        track_data: Dict,
        df_logs: pd.DataFrame,
        depth_data: pd.Series,
        global_props: Dict
    ) -> None:
        """Plot wireline track with multiple curves."""
        curves = track_data.get('curves', [])
        
        # Track last curve info for axis configuration
        last_curve_info = None
        log_scale = False
        
        for curve_info in curves:
            last_curve_info = curve_info
            curve_name = curve_info['name']
            
            # Find curve in dataframe
            if curve_name not in df_logs.columns:
                print(f'[CPI Plotly] Warning: Curve {curve_name} not found in data')
                continue
            
            curve_data = df_logs[curve_name]
            
            # Get curve properties
            color = curve_info.get('color', 'blue')
            line_thickness = curve_info.get('line_thickness', 1)
            linestyle = curve_info.get('linestyle', 'solid')
            log_scale = bool(curve_info.get('log_scale', False))
            
            # Convert linestyle
            dash_map = {'solid': 'solid', 'dashed': 'dash', 'dotted': 'dot'}
            dash = dash_map.get(linestyle, 'solid')
            
            # Add trace
            fig.add_trace(
                go.Scatter(
                    x=curve_data,
                    y=depth_data,
                    mode='lines',
                    name=curve_name,
                    line=dict(color=color, width=line_thickness, dash=dash),
                    hovertemplate=f'{curve_name}: %{{x:.2f}}<br>Depth: %{{y:.2f}} m<extra></extra>'
                ),
                row=1,
                col=col_idx
            )
            
            # Handle fill areas if baseline is specified
            baseline = curve_info.get('baseline')
            if baseline is not None:
                left_fill = curve_info.get('left_fill_color')
                right_fill = curve_info.get('right_fill_color')
                
                if right_fill:
                    # Fill area where curve > baseline
                    fig.add_trace(
                        go.Scatter(
                            x=curve_data.where(curve_data >= baseline, baseline),
                            y=depth_data,
                            fill='tonextx',
                            fillcolor=right_fill,
                            line=dict(width=0),
                            showlegend=False,
                            hoverinfo='skip'
                        ),
                        row=1,
                        col=col_idx
                    )
                    
                    # Add baseline reference
                    fig.add_trace(
                        go.Scatter(
                            x=[baseline] * len(depth_data),
                            y=depth_data,
                            line=dict(width=0),
                            showlegend=False,
                            hoverinfo='skip'
                        ),
                        row=1,
                        col=col_idx
                    )
        
        # Update X-axis for this track (use last curve info if available)
        if last_curve_info is not None:
            x_min = last_curve_info.get('min')
            x_max = last_curve_info.get('max')
            
            if x_min is not None and x_max is not None:
                if log_scale:
                    fig.update_xaxes(
                        type='log',
                        range=[np.log10(x_min), np.log10(x_max)],
                        showgrid=track_data.get('xgrid', True),
                        gridcolor='lightgray',
                        gridwidth=1,
                        row=1,
                        col=col_idx
                    )
                else:
                    fig.update_xaxes(
                        range=[x_min, x_max],
                        showgrid=track_data.get('xgrid', True),
                        gridcolor='lightgray',
                        gridwidth=1,
                        row=1,
                        col=col_idx
                    )
                
                # Add scale annotation showing min/max values
                curve_names = [c['name'] for c in curves if c['name'] in df_logs.columns]
                scale_text = f"{x_min} - {x_max}"
                
                xaxis_key = f'x{col_idx}' if col_idx > 1 else 'x'
                fig.add_annotation(
                    text=f"<b>{scale_text}</b>",
                    xref=xaxis_key,
                    yref='paper',
                    x=(x_min + x_max) / 2 if not log_scale else np.sqrt(x_min * x_max),
                    y=1.05,
                    showarrow=False,
                    font=dict(size=global_props['lr_limits_font_size'] + 1, color='black', family='Arial'),
                    xanchor='center',
                    yanchor='bottom'
                )
    
    def _plot_scale_track(
        self,
        fig: go.Figure,
        col_idx: int,
        track_data: Dict,
        df_logs: pd.DataFrame,
        depth_data: pd.Series,
        global_props: Dict
    ) -> None:
        """Plot depth scale track."""
        # For controlling depth track, just show the grid
        if track_data.get('controls'):
            # Empty trace to maintain layout
            fig.add_trace(
                go.Scatter(
                    x=[0],
                    y=[depth_data.mean()],
                    mode='markers',
                    marker=dict(size=0),
                    showlegend=False,
                    hoverinfo='skip'
                ),
                row=1,
                col=col_idx
            )
            
            fig.update_xaxes(
                showticklabels=False,
                showgrid=False,
                row=1,
                col=col_idx
            )
    
    def _plot_tops_track(
        self,
        fig: go.Figure,
        col_idx: int,
        track_data: Dict,
        df_tops: pd.DataFrame,
        depth_min: float,
        depth_max: float
    ) -> None:
        """Plot formation tops as horizontal lines with labels."""
        if df_tops.empty:
            return
        
        # Filter tops within depth range
        tops_in_range = df_tops[
            (df_tops['depth'] >= depth_min) & 
            (df_tops['depth'] <= depth_max)
        ]
        
        for _, top_row in tops_in_range.iterrows():
            depth = top_row['depth']
            top_name = top_row.get('top_name', top_row.get('TOP', 'Unknown'))
            
            # Add horizontal line
            fig.add_shape(
                type="line",
                x0=0, x1=1,
                y0=depth, y1=depth,
                line=dict(color='black', width=2, dash='dash'),
                xref=f'x{col_idx}' if col_idx > 1 else 'x',
                yref='y',
                row=1,
                col=col_idx
            )
            
            # Add text annotation
            fig.add_annotation(
                x=0.5,
                y=depth,
                text=top_name,
                showarrow=False,
                font=dict(size=10, color='green'),
                xref=f'x{col_idx}' if col_idx > 1 else 'x',
                yref='y',
                xanchor='center',
                yanchor='bottom'
            )
        
        # Configure X-axis
        fig.update_xaxes(
            range=[0, 1],
            showticklabels=False,
            showgrid=False,
            row=1,
            col=col_idx
        )
    
    def _plot_fluid_track(
        self,
        fig: go.Figure,
        col_idx: int,
        track_data: Dict,
        df_logs: pd.DataFrame,
        depth_data: pd.Series,
        spec_folder: Optional[str],
        global_props: Dict
    ) -> None:
        """Plot fluid type track with color mapping."""
        if 'FLUID' not in df_logs.columns:
            print('[CPI Plotly] Warning: FLUID column not found')
            return
        
        fluid_data = df_logs['FLUID']
        
        # Load color map if available
        color_map = self._load_fluid_color_map(spec_folder, global_props)
        
        # Create colored segments
        for fluid_val in fluid_data.dropna().unique():
            mask = fluid_data == fluid_val
            color = color_map.get(int(fluid_val), 'gray') if color_map else 'gray'
            
            fig.add_trace(
                go.Scatter(
                    x=[0.5] * len(depth_data[mask]),
                    y=depth_data[mask],
                    mode='markers',
                    marker=dict(
                        color=color,
                        size=20,
                        symbol='square',
                        line=dict(width=0)
                    ),
                    name=f'Fluid {int(fluid_val)}',
                    showlegend=False,
                    hovertemplate=f'Fluid: {int(fluid_val)}<br>Depth: %{{y:.2f}} m<extra></extra>'
                ),
                row=1,
                col=col_idx
            )
        
        fig.update_xaxes(
            range=[0, 1],
            showticklabels=False,
            showgrid=False,
            row=1,
            col=col_idx
        )
    
    def _plot_perf_track(
        self,
        fig: go.Figure,
        col_idx: int,
        track_data: Dict,
        df_perfs: pd.DataFrame,
        depth_min: float,
        depth_max: float
    ) -> None:
        """Plot perforation intervals."""
        # Filter perfs within depth range
        perfs_in_range = df_perfs[
            (df_perfs['top'] >= depth_min) & 
            (df_perfs['bottom'] <= depth_max)
        ]
        
        for _, perf in perfs_in_range.iterrows():
            top = perf['top']
            bottom = perf['bottom']
            
            # Add rectangle for perforation interval
            fig.add_shape(
                type="rect",
                x0=0.2, x1=0.8,
                y0=top, y1=bottom,
                fillcolor='red',
                opacity=0.5,
                line=dict(color='darkred', width=1),
                xref=f'x{col_idx}' if col_idx > 1 else 'x',
                yref='y',
                row=1,
                col=col_idx
            )
        
        fig.update_xaxes(
            range=[0, 1],
            showticklabels=False,
            showgrid=False,
            row=1,
            col=col_idx
        )
    
    def _plot_text_track(
        self,
        fig: go.Figure,
        col_idx: int,
        track_data: Dict,
        df_logs: pd.DataFrame,
        depth_data: pd.Series
    ) -> None:
        """Plot text annotations track."""
        curves = track_data.get('curves', [])
        if not curves:
            return
        
        text_curve_name = curves[0]['name']
        if text_curve_name not in df_logs.columns:
            print(f'[CPI Plotly] Warning: Text curve {text_curve_name} not found')
            return
        
        text_data = df_logs[text_curve_name]
        color = curves[0].get('color', 'black')
        decimals = curves[0].get('decimals', 2)
        
        # Add text annotations at intervals
        interval = max(1, len(text_data) // 50)  # Limit number of labels
        
        for i in range(0, len(text_data), interval):
            if pd.notna(text_data.iloc[i]):
                fig.add_annotation(
                    x=0.5,
                    y=depth_data.iloc[i],
                    text=f'{text_data.iloc[i]:.{decimals}f}',
                    showarrow=False,
                    font=dict(size=8, color=color),
                    xref=f'x{col_idx}' if col_idx > 1 else 'x',
                    yref='y',
                    xanchor='center',
                    yanchor='middle'
                )
        
        fig.update_xaxes(
            range=[0, 1],
            showticklabels=False,
            showgrid=False,
            row=1,
            col=col_idx
        )
    
    def _load_fluid_color_map(self, spec_folder: Optional[str], global_props: Dict) -> Optional[Dict]:
        """Load fluid color mapping from CSV file."""
        fluid_color_file_name = global_props.get('fluid_color_file_name')
        if not fluid_color_file_name or not spec_folder:
            return None
        
        try:
            color_file = os.path.join(spec_folder, f'{fluid_color_file_name}.csv')
            if not os.path.exists(color_file):
                return None
            
            df_colors = pd.read_csv(color_file)
            df_colors.sort_values(by='FLUID_VALUE', inplace=True)
            
            color_map = {}
            for _, row in df_colors.iterrows():
                fluid_val = int(row['FLUID_VALUE'])
                hex_color = str(row['COLOR_HEX']).strip()
                color_map[fluid_val] = hex_color
            
            return color_map
            
        except Exception as e:
            print(f'[CPI Plotly] Error loading fluid colors: {e}')
            return None
