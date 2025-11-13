"""
Well Log Plotting Module with XML Layout Support
Provides functionality for creating well log plots with Plotly based on XML layout definitions
"""

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import json
import xml.etree.ElementTree as ET
from pathlib import Path


class LogPlotManager:
    """
    Manages well log plotting functionality with XML layout support
    Creates interactive Plotly plots matching XML-defined layouts
    """
    
    def __init__(self):
        self.docks = []
        self.shared_axis = None
        self.main_figure = None
        self.layout_config = None
    
    def load_xml_layout(self, xml_path):
        """
        Load and parse XML layout configuration
        
        Args:
            xml_path: Path to XML layout file
            
        Returns:
            Dictionary with layout configuration
        """
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()
            
            config = {
                'depth_scale': int(root.get('depth_scale', '640')),
                'major_y_tick': int(root.get('major_y_tick', '25')),
                'minor_y_tick': int(root.get('minor_y_tick', '5')),
                'grid_color': root.get('grid_color', 'lightgray'),
                'tracks': []
            }
            
            # Parse each track
            for track_elem in root.findall('Track'):
                track = {
                    'name': track_elem.get('name'),
                    'type': track_elem.get('type', 'wireline'),
                    'width': float(track_elem.get('width', '0.5')),
                    'ygrid': track_elem.get('ygrid', 'True') == 'True',
                    'xgrid': track_elem.get('xgrid', 'True') == 'True',
                    'curves': []
                }
                
                # Parse curves within track
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
                        'shading_left': curve_elem.get('shading_left'),
                        'shading_right': curve_elem.get('shading_right')
                    }
                    track['curves'].append(curve)
                
                config['tracks'].append(track)
            
            self.layout_config = config
            return config
            
        except Exception as e:
            print(f"[LogPlot] Error loading XML layout: {e}")
            return None
    
    def create_log_plot_from_xml(self, well_data, xml_layout_path, index_name='DEPTH'):
        """
        Create a well log plot based on XML layout configuration
        
        Args:
            well_data: Well object with datasets
            xml_layout_path: Path to XML layout file
            index_name: Name of the index (typically 'DEPTH')
            
        Returns:
            Plotly figure as JSON string
        """
        # Load XML layout
        config = self.load_xml_layout(xml_layout_path)
        if not config:
            print("[LogPlot] Failed to load XML layout, using default plotting")
            return None
        
        print(f"[LogPlot] Creating plot with {len(config['tracks'])} tracks from XML layout")
        
        # Collect available logs from well data
        available_logs = {}
        shared_index = None
        
        for dataset in well_data.datasets:
            for well_log in dataset.well_logs:
                available_logs[well_log.name] = {
                    'log': well_log.log,
                    'index': dataset.index_log,
                    'index_name': dataset.index_name or index_name
                }
                if shared_index is None and dataset.index_log:
                    shared_index = dataset.index_log
        
        if shared_index is None:
            print("[LogPlot] ERROR: No shared index (DEPTH) found")
            return None
        
        # Keep ALL tracks from XML, even if no data available
        # This creates the complete layout structure
        all_tracks = config['tracks']
        
        # Track which ones have data for logging
        tracks_with_data = 0
        for track in all_tracks:
            for curve in track['curves']:
                if curve['name'] in available_logs:
                    tracks_with_data += 1
                    break
        
        num_tracks = len(all_tracks)
        print(f"[LogPlot] Rendering all {num_tracks} XML tracks ({tracks_with_data} have data, {num_tracks - tracks_with_data} will be empty)")
        
        # Calculate column widths based on XML track widths
        total_width = sum(t['width'] for t in all_tracks)
        column_widths = [t['width'] / total_width for t in all_tracks]
        
        # Create subplot titles
        subplot_titles = [track['name'] for track in all_tracks]
        
        # Create subplots
        fig = make_subplots(
            rows=1,
            cols=num_tracks,
            shared_yaxes=True,
            subplot_titles=subplot_titles,
            horizontal_spacing=0.01,
            column_widths=column_widths,
            vertical_spacing=0.1
        )
        
        # Process each track
        for track_idx, track in enumerate(all_tracks):
            current_col = track_idx + 1
            track_has_any_data = False
            
            # Process curves in this track
            previous_curve_data = None
            
            for curve_idx, curve_config in enumerate(track['curves']):
                curve_name = curve_config['name']
                
                if curve_name not in available_logs:
                    continue
                
                track_has_any_data = True
                
                log_data = available_logs[curve_name]
                log_values = log_data['log']
                index_values = log_data['index'] or shared_index
                
                # Filter valid data
                valid_data = [(idx, val) for idx, val in zip(index_values, log_values)
                             if val is not None and not np.isnan(val)]
                
                if not valid_data:
                    continue
                
                valid_idx, valid_vals = zip(*valid_data)
                
                # Convert line style
                dash_style = 'solid'
                if curve_config['linestyle'] == 'dashed':
                    dash_style = 'dash'
                elif curve_config['linestyle'] == 'dotted':
                    dash_style = 'dot'
                
                # Add main curve trace
                fig.add_trace(
                    go.Scatter(
                        x=valid_vals,
                        y=valid_idx,
                        mode='lines',
                        name=curve_name,
                        line=dict(
                            color=curve_config['color'],
                            width=curve_config['line_thickness'],
                            dash=dash_style
                        ),
                        showlegend=False,
                        hovertemplate=f"{curve_name}: %{{x:.2f}}<br>Depth: %{{y:.2f}}<extra></extra>"
                    ),
                    row=1,
                    col=current_col
                )
                
                # Handle fill areas
                if curve_config['baseline'] is not None:
                    # Fill between curve and baseline
                    baseline_vals = [curve_config['baseline']] * len(valid_idx)
                    
                    # Determine fill direction and color
                    if curve_config['left_fill_color'] and curve_config['right_fill_color']:
                        # Create two fill areas split at baseline
                        # Left fill (values < baseline)
                        fig.add_trace(
                            go.Scatter(
                                x=[curve_config['baseline']] + list(valid_vals) + [curve_config['baseline']],
                                y=[valid_idx[0]] + list(valid_idx) + [valid_idx[-1]],
                                fill='toself',
                                fillcolor=curve_config['left_fill_color'],
                                opacity=0.3,
                                line=dict(width=0),
                                showlegend=False,
                                hoverinfo='skip'
                            ),
                            row=1,
                            col=current_col
                        )
                
                # Handle shading between curves
                if curve_config['shading_left'] == 'previous' and previous_curve_data:
                    # Fill between this curve and previous curve
                    prev_idx, prev_vals = previous_curve_data
                    
                    # Find common depth range
                    min_depth = max(min(valid_idx), min(prev_idx))
                    max_depth = min(max(valid_idx), max(prev_idx))
                    
                    # Create fill
                    x_combined = list(valid_vals) + list(reversed(prev_vals))
                    y_combined = list(valid_idx) + list(reversed(prev_idx))
                    
                    fill_color = curve_config['left_fill_color'] or 'lightblue'
                    
                    fig.add_trace(
                        go.Scatter(
                            x=x_combined,
                            y=y_combined,
                            fill='toself',
                            fillcolor=fill_color,
                            opacity=0.3,
                            line=dict(width=0),
                            showlegend=False,
                            hoverinfo='skip'
                        ),
                        row=1,
                        col=current_col
                    )
                
                if curve_config['shading_right'] == 'right_limit' or curve_config['shading_left'] == 'left_limit':
                    # Fill to axis limit
                    axis_limit = curve_config['max'] if curve_config['shading_right'] == 'right_limit' else curve_config['min']
                    
                    if axis_limit is not None:
                        x_fill = list(valid_vals) + [axis_limit, axis_limit]
                        y_fill = list(valid_idx) + [valid_idx[-1], valid_idx[0]]
                        
                        fill_color = curve_config['right_fill_color'] or curve_config['left_fill_color'] or 'lightgray'
                        
                        fig.add_trace(
                            go.Scatter(
                                x=x_fill,
                                y=y_fill,
                                fill='toself',
                                fillcolor=fill_color,
                                opacity=0.3,
                                line=dict(width=0),
                                showlegend=False,
                                hoverinfo='skip'
                            ),
                            row=1,
                            col=current_col
                        )
                
                # Store for potential shading with next curve
                previous_curve_data = (valid_idx, valid_vals)
            
            # If track has no data, add an empty placeholder trace to maintain grid
            if not track_has_any_data:
                # Add invisible trace to create the subplot structure
                fig.add_trace(
                    go.Scatter(
                        x=[],
                        y=[],
                        mode='lines',
                        showlegend=False,
                        hoverinfo='skip'
                    ),
                    row=1,
                    col=current_col
                )
            
            # Configure x-axis for this track
            xaxis_name = f"xaxis{current_col}" if current_col > 1 else "xaxis"
            
            # Check if any curve in track is resistivity (use log scale)
            is_resistivity = any('RES' in c['name'].upper() for c in track['curves'])
            axis_type = "log" if is_resistivity else "linear"
            
            # Get axis range from first curve with min/max defined
            x_min, x_max = None, None
            for curve in track['curves']:
                if curve['min'] is not None:
                    x_min = curve['min']
                if curve['max'] is not None:
                    x_max = curve['max']
                if x_min is not None and x_max is not None:
                    break
            
            fig.update_layout({
                xaxis_name: dict(
                    title=track['name'],
                    type=axis_type,
                    side='top',
                    showgrid=track['xgrid'],
                    gridcolor=config['grid_color'],
                    gridwidth=0.5,
                    zeroline=False,
                    range=[x_min, x_max] if x_min is not None and x_max is not None else None
                )
            })
            
            # Configure y-axis (only for first track, others share it)
            if track_idx == 0:
                fig.update_yaxes(
                    title_text=index_name,
                    autorange='reversed',  # Depth increases downward
                    showgrid=True,
                    gridcolor=config['grid_color'],
                    gridwidth=0.5,
                    dtick=config['major_y_tick'],
                    row=1,
                    col=current_col
                )
        
        # Apply overall layout settings
        layout_height = 1000 if num_tracks > 6 else 900
        
        fig.update_layout(
            height=layout_height,
            title_text="",
            showlegend=False,
            hovermode='closest',
            plot_bgcolor='white',
            paper_bgcolor='white',
            margin=dict(l=80, r=40, t=100, b=60),
            dragmode='pan'
        )
        
        # Update subplot title font size
        for annotation in fig.layout.annotations:
            annotation.font.size = 11
            annotation.y = annotation.y + 0.02
        
        # Add vertical lines between tracks using actual subplot domains
        # This ensures borders appear correctly regardless of spacing
        shapes = []
        for i in range(1, num_tracks):  # Start from track 2 to draw line before each track
            try:
                # Get the x-axis name for this track (1-indexed for Plotly)
                xaxis_key = 'xaxis' if i == 1 else f'xaxis{i}'
                
                # Access the domain from the layout
                xaxis_obj = getattr(fig.layout, xaxis_key, None)
                if xaxis_obj and hasattr(xaxis_obj, 'domain') and xaxis_obj.domain:
                    left_edge = xaxis_obj.domain[0]
                    
                    # Add vertical line at the left edge of this track
                    shapes.append(
                        dict(
                            type='line',
                            xref='paper',
                            yref='paper',
                            x0=left_edge,
                            y0=0,
                            x1=left_edge,
                            y1=1,
                            line=dict(
                                color='black',
                                width=2
                            ),
                            layer='above'
                        )
                    )
                    print(f"[LogPlot] Added border at x={left_edge} for track {i}")
            except Exception as e:
                print(f"[LogPlot] Warning: Could not add border for track {i}: {e}")
        
        # Add shapes to layout
        if shapes:
            fig.update_layout(shapes=shapes)
            print(f"[LogPlot] Added {len(shapes)} vertical borders between tracks")
        
        # Return as JSON for frontend rendering
        fig_json = fig.to_json()
        print(f"[LogPlot] Plotly figure created successfully from XML layout, JSON size: {len(fig_json)} characters")
        
        return fig_json
    
    def create_log_plot(self, well_data, log_names, index_name='DEPTH', xml_layout_path=None):
        """
        Create a well log plot with multiple tracks using Plotly
        
        Args:
            well_data: Well object with datasets
            log_names: List of log names to plot (used if no XML layout)
            index_name: Name of the index (typically 'DEPTH')
            xml_layout_path: Optional path to XML layout file
            
        Returns:
            Plotly figure as JSON string
        """
        # If XML layout provided, use layout-driven plotting
        if xml_layout_path and Path(xml_layout_path).exists():
            return self.create_log_plot_from_xml(well_data, xml_layout_path, index_name)
        
        # Otherwise, use simple plotting
        print(f"[LogPlot] Creating Plotly log plot for {len(log_names)} logs: {log_names}")
        
        if not log_names:
            print("[LogPlot] No log names provided")
            return None
        
        # Number of tracks (one per log)
        num_tracks = len(log_names)
        
        print(f"[LogPlot] Creating figure with {num_tracks} tracks")
        
        # Collect log data
        tracks_data = []
        shared_index = None
        
        for log_name in log_names:
            print(f"[LogPlot] Searching for log: {log_name}")
            # Search through all datasets
            for dataset in well_data.datasets:
                # Look for the log in dataset's well_logs
                for well_log in dataset.well_logs:
                    if well_log.name == log_name:
                        tracks_data.append({
                            'name': log_name,
                            'log': well_log.log,
                            'index': dataset.index_log,
                            'index_name': dataset.index_name or index_name
                        })
                        if shared_index is None and dataset.index_log:
                            shared_index = dataset.index_log
                        print(f"[LogPlot] Found {log_name} with {len(well_log.log)} points")
                        break
                if tracks_data and tracks_data[-1]['name'] == log_name:
                    break
        
        if not tracks_data:
            print("[LogPlot] ERROR: No track data found")
            return None
            
        if shared_index is None:
            print("[LogPlot] ERROR: No shared index (DEPTH) found")
            return None
        
        print(f"[LogPlot] Successfully collected {len(tracks_data)} tracks")
        
        # Create subplot titles
        subplot_titles = [track['name'] for track in tracks_data]
        
        # Create subplots with shared y-axis (depth)
        fig = make_subplots(
            rows=1, 
            cols=num_tracks,
            shared_yaxes=True,
            subplot_titles=subplot_titles,
            horizontal_spacing=0.05,
            column_widths=[1/num_tracks] * num_tracks,
            vertical_spacing=0.1
        )
        
        # Iterate through tracks and add curves (traces)
        for i, track in enumerate(tracks_data):
            current_col = i + 1  # Plotly uses 1-based indexing
            
            # Get log values and index values
            log_values = track['log']
            index_values = track['index'] or shared_index
            
            # Filter valid data
            valid_data = [(idx, val) for idx, val in zip(index_values, log_values) 
                         if val is not None and not np.isnan(val)]
            
            if valid_data:
                valid_idx, valid_vals = zip(*valid_data)
                
                # Add trace to subplot
                # Note: In well logs, depth is on y-axis and log values on x-axis
                fig.add_trace(
                    go.Scatter(
                        x=valid_vals,
                        y=valid_idx,
                        mode='lines',
                        name=track['name'],
                        line=dict(color='blue', width=1),
                        showlegend=False
                    ),
                    row=1,
                    col=current_col
                )
                
                # Update x-axis for this track
                xaxis_name = f"xaxis{current_col}" if current_col > 1 else "xaxis"
                
                # Check if this is a resistivity log (should use log scale)
                is_resistivity = any(keyword in track['name'].upper() 
                                   for keyword in ['RES', 'RESIST', 'ILD', 'ILM', 'LLD', 'LLS'])
                
                axis_type = "log" if is_resistivity else "linear"
                
                # Configure x-axis
                fig.update_layout({
                    xaxis_name: dict(
                        title=track['name'],
                        type=axis_type,
                        side='top',
                        showgrid=True,
                        gridcolor='lightgray',
                        gridwidth=0.5,
                        zeroline=False
                    )
                })
                
                # Configure y-axis (only for first track, others share it)
                if i == 0:
                    fig.update_yaxes(
                        title_text=track['index_name'],
                        autorange='reversed',  # Depth increases downward
                        showgrid=True,
                        gridcolor='lightgray',
                        gridwidth=0.5,
                        row=1,
                        col=current_col
                    )
        
        # Apply overall layout settings
        layout_height = 1000 if num_tracks > 6 else 900
        
        fig.update_layout(
            height=layout_height,
            title_text="",
            showlegend=False,
            hovermode='closest',
            plot_bgcolor='white',
            paper_bgcolor='white',
            margin=dict(l=80, r=40, t=100, b=60),
            dragmode='pan'
        )
        
        # Update subplot title font size and position
        for annotation in fig.layout.annotations:
            annotation.font.size = 11
            annotation.y = annotation.y + 0.02
        
        # Return as JSON for frontend rendering
        fig_json = fig.to_json()
        print(f"[LogPlot] Plotly figure created successfully, JSON size: {len(fig_json)} characters")
        
        return fig_json
    
    def add_dock(self, log_name, log_data, shared_axis):
        """
        Add a dock/track for a log
        
        Args:
            log_name: Name of the log
            log_data: Log data array
            shared_axis: Shared axis (depth) for alignment
        """
        dock_data = {
            'name': log_name,
            'data': log_data,
            'shared_axis': shared_axis
        }
        self.docks.append(dock_data)
        return dock_data
    
    def remove_dock(self, dock_index=None):
        """Remove a dock/track"""
        if self.docks:
            if dock_index is not None and 0 <= dock_index < len(self.docks):
                self.docks.pop(dock_index)
            else:
                self.docks.pop()
    
    def clear_docks(self):
        """Clear all docks/tracks"""
        self.docks = []
