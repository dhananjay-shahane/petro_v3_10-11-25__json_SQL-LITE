"""
CLI Import/Export Commands Module
Contains all CLI commands related to importing and exporting data (LAS files, TOPS, etc.)
"""

import os
import tempfile
import shutil
from typing import Dict, Any, List, Tuple
from datetime import datetime
import pandas as pd

from utils.fe_data_objects import Well, Dataset, WellLog, Constant
from utils.las_file_io import create_well_from_las


def generate_unique_name(existing_names: List[str], base_name: str) -> str:
    """
    Generate a unique name by appending _1, _2, etc. if base_name already exists.
    
    Args:
        existing_names: List of existing dataset/log names
        base_name: The base name to make unique
        
    Returns:
        Unique name (e.g., 'TOPS', 'TOPS_1', 'TOPS_2')
    """
    if base_name not in existing_names:
        return base_name
    
    counter = 1
    while f"{base_name}_{counter}" in existing_names:
        counter += 1
    
    return f"{base_name}_{counter}"


class CLICommand:
    """Base class for CLI commands."""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
    
    def execute(self, args: Dict[str, Any], context: Dict[str, Any]) -> Tuple[bool, str, Any]:
        """
        Execute the command.
        
        Args:
            args: Command arguments
            context: Execution context (project_path, current_well, etc.)
            
        Returns:
            Tuple of (success, message, result_data)
        """
        raise NotImplementedError


class ImportLasFileCommand(CLICommand):
    """Import a LAS file into a well with optional suffix. Well name is always extracted from LAS file metadata."""
    
    def __init__(self):
        super().__init__(
            "IMPORT_LAS_FILE",
            "Import a single LAS file. Usage: IMPORT_LAS_FILE <file_path> [suffix]. Well name is extracted from the WELL field inside the LAS file, NOT from filename."
        )
    
    def execute(self, args: Dict[str, Any], context: Dict[str, Any]) -> Tuple[bool, str, Any]:
        las_file_path = args.get('well_name') or args.get('las_file_path')
        suffix = args.get('las_file_path') if args.get('well_name') else args.get('suffix', '')
        
        if not las_file_path:
            return False, "Missing required argument: las_file_path", None
        
        project_path = context.get('project_path')
        if not project_path:
            return False, "No project loaded", None
        
        # Make path absolute (relative paths are resolved from project directory)
        if not os.path.isabs(las_file_path):
            las_file_path = os.path.join(project_path, las_file_path)
        
        las_file_path = os.path.abspath(las_file_path)
        
        # Use the shared create_well_from_las function (same logic as API endpoint)
        success, message, result = create_well_from_las(
            las_file_path=las_file_path,
            project_path=project_path,
            dataset_suffix=suffix,
            copy_las_to_project=False  # Don't copy, as CLI users manage their own files
        )
        
        # Cleanup temporary uploaded file if it's in temp las_uploads directory
        if success:
            temp_uploads_dir = os.path.join(tempfile.gettempdir(), 'las_uploads')
            if temp_uploads_dir in las_file_path:
                try:
                    session_dir = os.path.dirname(las_file_path)
                    if os.path.exists(session_dir):
                        shutil.rmtree(session_dir)
                        print(f"[CLI] Cleaned up temporary upload directory: {session_dir}")
                except Exception as cleanup_error:
                    print(f"[CLI] Warning: Failed to cleanup temp files: {cleanup_error}")
        
        return success, message, result


class ImportLasFilesFromFolderCommand(CLICommand):
    """Import all LAS files from a folder. Well name is always extracted from LAS file metadata."""
    
    def __init__(self):
        super().__init__(
            "IMPORT_LAS_FILES_FROM_FOLDER",
            "Import multiple LAS files from a folder (use file picker to select multiple .las files). Usage: IMPORT_LAS_FILES_FROM_FOLDER <folder_path>. Well name is extracted from the WELL field inside each LAS file."
        )
    
    def execute(self, args: Dict[str, Any], context: Dict[str, Any]) -> Tuple[bool, str, Any]:
        folder_path = args.get('well_name') or args.get('folder_path')
        
        if not folder_path:
            return False, "Missing required argument: folder_path", None
        
        project_path = context.get('project_path')
        if not project_path:
            return False, "No project loaded", None
        
        # Make path absolute (relative paths are resolved from project directory)
        if not os.path.isabs(folder_path):
            folder_path = os.path.join(project_path, folder_path)
        
        folder_path = os.path.abspath(folder_path)
        
        # Verify folder exists
        if not os.path.exists(folder_path):
            return False, f"Folder not found: {folder_path}", None
        
        # Get list of LAS files
        las_files = [f for f in os.listdir(folder_path) if f.lower().endswith('.las')]
        
        if not las_files:
            return False, f"No LAS files found in folder: {folder_path}", None
        
        try:
            wells_created = set()
            wells_updated = set()
            imported_files = []
            total_datasets = 0
            failed_files = []
            
            # Process each LAS file individually using the shared function
            for las_file in las_files:
                las_file_path = os.path.join(folder_path, las_file)
                
                # Use the shared create_well_from_las function (same logic as API endpoint)
                success, message, result = create_well_from_las(
                    las_file_path=las_file_path,
                    project_path=project_path,
                    dataset_suffix='',
                    copy_las_to_project=False  # Don't copy, as CLI users manage their own files
                )
                
                if success and result:
                    well_name = result.get('well_name')
                    if result.get('well_created'):
                        wells_created.add(well_name)
                    else:
                        wells_updated.add(well_name)
                    
                    imported_files.append(las_file)
                    total_datasets += 1  # Each file creates one dataset
                else:
                    failed_files.append((las_file, message))
                    print(f"Warning: Failed to import {las_file}: {message}")
            
            # Build status message
            if not imported_files:
                return False, "No LAS files could be imported", None
            
            total_wells = len(wells_created) + len(wells_updated)
            status_parts = [
                f"✓ Imported {len(imported_files)} LAS files ({total_datasets} datasets) into {total_wells} well(s)"
            ]
            
            if wells_created:
                status_parts.append(f"Created {len(wells_created)} new well(s): {', '.join(sorted(wells_created))}")
            
            if wells_updated:
                status_parts.append(f"Updated {len(wells_updated)} existing well(s): {', '.join(sorted(wells_updated))}")
            
            if failed_files:
                status_parts.append(f"Failed to import {len(failed_files)} file(s): {', '.join([f[0] for f in failed_files])}")
            
            status_msg = "\n".join(status_parts)
            
            # Cleanup temporary uploaded folder if it's in temp las_uploads directory
            temp_uploads_dir = os.path.join(tempfile.gettempdir(), 'las_uploads')
            if temp_uploads_dir in folder_path:
                try:
                    if os.path.exists(folder_path):
                        shutil.rmtree(folder_path)
                        print(f"[CLI] Cleaned up temporary upload directory: {folder_path}")
                except Exception as cleanup_error:
                    print(f"[CLI] Warning: Failed to cleanup temp files: {cleanup_error}")
            
            return True, status_msg, {
                'wells_created': list(wells_created),
                'wells_updated': list(wells_updated),
                'folder': folder_path,
                'files_imported': imported_files,
                'files_failed': failed_files,
                'total_datasets': total_datasets
            }
        except Exception as e:
            return False, f"Error importing LAS files: {str(e)}", None


class LoadTopsCommand(CLICommand):
    """Load TOPS data from a CSV/TSV file into a well."""
    
    def __init__(self):
        super().__init__(
            "LOAD_TOPS",
            "Load TOPS (geological markers) from a CSV/TSV file. Usage: LOAD_TOPS well_name file_path"
        )
    
    def execute(self, args: Dict[str, Any], context: Dict[str, Any]) -> Tuple[bool, str, Any]:
        well_name = args.get('well_name')
        csv_file_path = args.get('csv_file_path')
        
        if not all([well_name, csv_file_path]):
            return False, "Missing required arguments: well_name, csv_file_path", None
        
        project_path = context.get('project_path')
        if not project_path:
            return False, "No project loaded", None
        
        file_abs_path = os.path.realpath(os.path.join(project_path, csv_file_path))
        project_abs_path = os.path.realpath(project_path) + os.sep
        
        if not file_abs_path.startswith(project_abs_path):
            return False, f"Access denied: file path outside project directory", None
        
        if not os.path.exists(file_abs_path):
            return False, f"CSV/TSV file not found: {csv_file_path}", None
        
        well_path = os.path.join(project_path, '10-WELLS', f'{well_name}.ptrc')
        
        if not os.path.exists(well_path):
            return False, f"Well '{well_name}' not found", None
        
        try:
            well = Well.deserialize(well_path)
            
            # Auto-detect delimiter (tab or comma)
            with open(file_abs_path, 'r') as f:
                first_line = f.readline()
                delimiter = '\t' if '\t' in first_line else ','
            
            df = pd.read_csv(file_abs_path, sep=delimiter)
            print(df)
            
            # Check if this is a multi-well file (has WELL column)
            if 'WELL' in df.columns:
                # Filter for this specific well
                df = df[df['WELL'].str.strip() == well_name.strip()].copy()
                if df.empty:
                    return False, f"No data found for well '{well_name}' in the TOPS file", None
                # Drop the WELL column as we don't need it anymore
                df = df.drop(columns=['WELL'])
                print(df)
            required_columns = ['DEPTH', 'TOP']
            for col in required_columns:
                if col not in df.columns:
                    return False, f"File must contain '{col}' column", None
            
            # Generate unique dataset name to avoid conflicts
            existing_dataset_names = [dataset.name for dataset in well.datasets]
            dataset_name = generate_unique_name(existing_dataset_names, 'TOPS')
            
            dataset = Dataset(
                date_created=datetime.now(),
                name=dataset_name,
                type='Tops',
                wellname=well_name,
                index_log=df['DEPTH'].tolist(),
                index_name='DEPTH',
                well_logs=[],
                constants=[],
                metadata={'source': f'Loaded from {csv_file_path}'}
            )
            
            for col in df.columns:
                if col == 'DEPTH':
                    log_type = 'float'
                    depth_values = df[col].tolist()
                    depth_log = WellLog(
                        name=col.upper(),
                        date=datetime.now().isoformat(),
                        description=f'Loaded from {csv_file_path}',
                        interpolation='TOP',
                        log_type=log_type,
                        log=depth_values,
                        dtst=dataset.name
                        )
                    dataset.well_logs.append(depth_log)
                if col == 'TOP':
                    log_type = 'str'
                    log_values = df[col].tolist()
                    well_log = WellLog(
                        name=col.upper(),
                        date=datetime.now().isoformat(),
                        description=f'Loaded from {csv_file_path}',
                        interpolation='TOP',
                        log_type=log_type,
                        log=log_values,
                        dtst=dataset.name
                    )
                    dataset.well_logs.append(well_log)
            
            well.add_dataset(dataset)
            well.serialize(well_path)
            
            return True, f"TOPS data loaded from '{csv_file_path}' into well '{well_name}' as dataset '{dataset_name}' ({len(df)} markers)", {
                'well_name': well_name,
                'dataset_name': dataset_name,
                'csv_file': csv_file_path,
                'num_markers': len(df)
            }
        except Exception as e:
            return False, f"Error loading TOPS: {str(e)}", None


class LoadTopsBulkCommand(CLICommand):
    """Load TOPS data from a multi-well CSV/TSV file into multiple wells."""
    
    def __init__(self):
        super().__init__(
            "LOAD_TOPS_BULK",
            "Load TOPS from a multi-well file (with WELL column). Usage: LOAD_TOPS_BULK file_path"
        )
    
    def execute(self, args: Dict[str, Any], context: Dict[str, Any]) -> Tuple[bool, str, Any]:
        csv_file_path = args.get('csv_file_path')
        
        if not csv_file_path:
            return False, "Missing required argument: csv_file_path", None
        
        project_path = context.get('project_path')
        if not project_path:
            return False, "No project loaded", None
        
        file_abs_path = os.path.realpath(os.path.join(project_path, csv_file_path))
        project_abs_path = os.path.realpath(project_path) + os.sep
        
        if not file_abs_path.startswith(project_abs_path):
            return False, f"Access denied: file path outside project directory", None
        
        if not os.path.exists(file_abs_path):
            return False, f"CSV/TSV file not found: {csv_file_path}", None
        
        try:
            # Auto-detect delimiter (tab or comma)
            with open(file_abs_path, 'r') as f:
                first_line = f.readline()
                delimiter = '\t' if '\t' in first_line else ','
            
            df = pd.read_csv(file_abs_path, sep=delimiter)
            
            required_columns = ['WELL', 'TOP', 'DEPTH']
            for col in required_columns:
                if col not in df.columns:
                    return False, f"File must contain '{col}' column for bulk loading", None
            
            # Group by well name
            wells_data = df.groupby('WELL')
            wells_folder = os.path.join(project_path, '10-WELLS')
            
            loaded_wells = []
            skipped_wells = []
            total_markers = 0
            
            for well_name, well_df in wells_data:
                well_name = well_name.strip()
                well_path = os.path.join(wells_folder, f'{well_name}.ptrc')
                
                if not os.path.exists(well_path):
                    skipped_wells.append(well_name)
                    continue
                
                try:
                    well = Well.deserialize(well_path)
                    
                    # Remove WELL column for dataset
                    tops_df = well_df.drop(columns=['WELL']).copy()
                    
                    # Generate unique dataset name to avoid conflicts
                    existing_dataset_names = [dataset.name for dataset in well.datasets]
                    dataset_name = generate_unique_name(existing_dataset_names, 'TOPS')
                    
                    dataset = Dataset(
                        date_created=datetime.now(),
                        name=dataset_name,
                        type='Tops',
                        wellname=well_name,
                        index_log=tops_df['DEPTH'].tolist(),
                        index_name='DEPTH',
                        well_logs=[],
                        constants=[],
                        metadata={'source': f'Bulk loaded from {csv_file_path}'}
                    )
                    
                    for col in tops_df.columns:
                        if col == 'DEPTH':
                            continue
                            
                        log_type = 'str' if col == 'TOP' else 'float'
                        log_values = tops_df[col].tolist()
                        
                        well_log = WellLog(
                            name=col.upper(),
                            date=datetime.now().isoformat(),
                            description=f'Bulk loaded from {csv_file_path}',
                            interpolation='TOP',
                            log_type=log_type,
                            log=log_values,
                            dtst=dataset.name
                        )
                        dataset.well_logs.append(well_log)
                    
                    well.add_dataset(dataset)
                    well.serialize(well_path)
                    
                    loaded_wells.append(well_name)
                    total_markers += len(tops_df)
                except Exception as e:
                    print(f"Warning: Failed to load TOPS for well '{well_name}': {e}")
                    skipped_wells.append(well_name)
            
            summary = f"Bulk TOPS loading complete: {len(loaded_wells)} wells loaded ({total_markers} total markers)"
            if skipped_wells:
                summary += f", {len(skipped_wells)} wells skipped (not found)"
            
            return True, summary, {
                'csv_file': csv_file_path,
                'loaded_wells': loaded_wells,
                'skipped_wells': skipped_wells,
                'total_markers': total_markers
            }
        except Exception as e:
            return False, f"Error bulk loading TOPS: {str(e)}", None


class ExportTopsCommand(CLICommand):
    """Export TOPS data from a well to a CSV file."""
    
    def __init__(self):
        super().__init__(
            "EXPORT_TOPS",
            "Export TOPS (geological markers) to a CSV file. Usage: EXPORT_TOPS well_name output_csv_path"
        )
    
    def execute(self, args: Dict[str, Any], context: Dict[str, Any]) -> Tuple[bool, str, Any]:
        well_name = args.get('well_name')
        output_csv_path = args.get('output_csv_path')
        
        if not all([well_name, output_csv_path]):
            return False, "Missing required arguments: well_name, output_csv_path", None
        
        project_path = context.get('project_path')
        if not project_path:
            return False, "No project loaded", None
        
        file_abs_path = os.path.realpath(os.path.join(project_path, output_csv_path))
        project_abs_path = os.path.realpath(project_path) + os.sep
        
        if not file_abs_path.startswith(project_abs_path):
            return False, f"Access denied: file path outside project directory", None
        
        well_path = os.path.join(project_path, '10-WELLS', f'{well_name}.ptrc')
        
        if not os.path.exists(well_path):
            return False, f"Well '{well_name}' not found", None
        
        try:
            well = Well.deserialize(well_path)
            
            tops_dataset = None
            for dataset in well.datasets:
                if dataset.type == 'Tops' or dataset.name == 'TOPS':
                    tops_dataset = dataset
                    break
            
            if not tops_dataset:
                return False, f"No TOPS data found in well '{well_name}'", None
            
            df = tops_dataset.to_dataframe()
            
            os.makedirs(os.path.dirname(file_abs_path), exist_ok=True)
            df.to_csv(file_abs_path, index=True)
            
            return True, f"TOPS data exported from well '{well_name}' to '{output_csv_path}' ({len(df)} markers)", {
                'well_name': well_name,
                'output_file': output_csv_path,
                'num_markers': len(df)
            }
        except Exception as e:
            return False, f"Error exporting TOPS: {str(e)}", None


class ExportToLasCommand(CLICommand):
    """Export a dataset to a LAS file."""
    
    def __init__(self):
        super().__init__(
            "EXPORT_TO_LAS",
            "Export a dataset to a LAS file. Usage: EXPORT_TO_LAS well_name dataset_name output_las_path"
        )
    
    def execute(self, args: Dict[str, Any], context: Dict[str, Any]) -> Tuple[bool, str, Any]:
        well_name = args.get('well_name')
        dataset_name = args.get('dataset_name')
        output_las_path = args.get('output_las_path')
        
        if not all([well_name, dataset_name, output_las_path]):
            return False, "Missing required arguments: well_name, dataset_name, output_las_path", None
        
        project_path = context.get('project_path')
        if not project_path:
            return False, "No project loaded", None
        
        file_abs_path = os.path.realpath(os.path.join(project_path, output_las_path))
        project_abs_path = os.path.realpath(project_path) + os.sep
        
        if not file_abs_path.startswith(project_abs_path):
            return False, f"Access denied: file path outside project directory", None
        
        well_path = os.path.join(project_path, '10-WELLS', f'{well_name}.ptrc')
        
        if not os.path.exists(well_path):
            return False, f"Well '{well_name}' not found", None
        
        try:
            well = Well.deserialize(well_path)
            
            dataset = well.get_dataset(dataset_name)
            
            os.makedirs(os.path.dirname(file_abs_path), exist_ok=True)
            
            success = dataset.export_to_las(file_abs_path, well_name)
            
            if success:
                return True, f"Dataset '{dataset_name}' exported to LAS file '{output_las_path}'", {
                    'well_name': well_name,
                    'dataset_name': dataset_name,
                    'output_file': output_las_path
                }
            else:
                return False, f"Failed to export dataset '{dataset_name}' to LAS", None
        except ValueError as e:
            return False, str(e), None
        except Exception as e:
            return False, f"Error exporting to LAS: {str(e)}", None
