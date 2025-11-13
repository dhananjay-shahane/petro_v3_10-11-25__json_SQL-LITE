"""
CLI Import/Export Commands Module
Contains all CLI commands related to importing and exporting data (LAS files, TOPS, etc.)
"""

import os
import tempfile
import shutil
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime
import pandas as pd
import lasio
import hashlib

from utils.fe_data_objects import Well, Dataset, WellLog, Constant
from utils.las_file_io import get_well_name_from_las


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


def create_well_from_las(
    las_file_path: str,
    project_path: str,
    dataset_suffix: str = '',
    copy_las_to_project: bool = True,
    dataset_type: str = 'Cont',
    enable_versioning: bool = True
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Create or update a well from a LAS file. This is the shared logic used by both 
    the API endpoint and CLI commands.
    
    Args:
        las_file_path: Full path to the LAS file
        project_path: Project directory path
        dataset_suffix: Optional suffix to append to dataset names
        copy_las_to_project: Whether to copy the LAS file to project's 02-INPUT_LAS_FOLDER
        dataset_type: Type of dataset ('Cont' for continuous, 'Point' for variable interval)
        enable_versioning: If True, auto-increment duplicate names (MAIN, MAIN_1, MAIN_2). If False, reject duplicates.
        
    Returns:
        Tuple of (success, message, result_data)
    """
    try:
        # Normalize and validate file path
        las_file_path = os.path.normpath(las_file_path)
        filename = os.path.basename(las_file_path)
        
        print(f"[LAS Import] Attempting to import file: {las_file_path}")
        print(f"[LAS Import] File exists check: {os.path.exists(las_file_path)}")
        
        # Verify file exists with detailed error message
        if not os.path.exists(las_file_path):
            # Provide helpful debugging information
            parent_dir = os.path.dirname(las_file_path)
            if os.path.exists(parent_dir):
                available_files = os.listdir(parent_dir) if os.path.isdir(parent_dir) else []
                print(f"[LAS Import] Parent directory exists: {parent_dir}")
                print(f"[LAS Import] Available files in directory: {available_files[:10]}")  # Show first 10 files
                return False, f"❌ File not found: '{filename}' in directory '{parent_dir}'", None
            else:
                print(f"[LAS Import] Parent directory does not exist: {parent_dir}")
                return False, f"❌ Directory not found: '{parent_dir}'. File path: '{las_file_path}'", None
        
        if not las_file_path.lower().endswith('.las'):
            return False, f"❌ Invalid file type: '{filename}' is not a LAS file", None
        
        # Check file permissions - ensure we can read the file
        if not os.access(las_file_path, os.R_OK):
            print(f"[LAS Import] File exists but is not readable: {las_file_path}")
            return False, f"❌ Permission denied: Cannot read file '{filename}'", None
        
        # Check file size (500 MB limit)
        MAX_FILE_SIZE = 500 * 1024 * 1024  # 500 MB
        RECOMMENDED_SIZE = 50 * 1024 * 1024  # 50 MB
        
        try:
            file_size = os.path.getsize(las_file_path)
        except OSError as e:
            print(f"[LAS Import] Error getting file size: {e}")
            return False, f"❌ Cannot access file '{filename}': {str(e)}", None
        
        file_size_mb = file_size / (1024 * 1024)
        print(f"[LAS Import] File size: {file_size_mb:.2f} MB")
        
        if file_size == 0:
            return False, f"❌ File is empty: '{filename}'", None
        
        if file_size > MAX_FILE_SIZE:
            return False, f"❌ File too large: {file_size_mb:.2f} MB. Maximum allowed is 500 MB.", None
        
        # Warn if file is large but within limits
        if file_size > RECOMMENDED_SIZE:
            print(f"⚠️  Large file warning: {file_size_mb:.2f} MB. Processing may take longer. Recommended size is up to 50 MB for optimal performance.")
        
        # Parse LAS file with detailed error handling
        print(f"[LAS Import] Parsing LAS file...")
        try:
            las = lasio.read(las_file_path)
        except FileNotFoundError:
            # This should not happen as we already checked, but just in case
            print(f"[LAS Import] FileNotFoundError during LAS parsing: {las_file_path}")
            return False, f"❌ File not found during parsing: '{filename}'", None
        except PermissionError:
            print(f"[LAS Import] PermissionError during LAS parsing: {las_file_path}")
            return False, f"❌ Permission denied while reading file: '{filename}'", None
        except Exception as las_error:
            print(f"[LAS Import] Error parsing LAS file: {las_error}")
            return False, f"❌ Invalid LAS file format in '{filename}': {str(las_error)}", None
        
        print(f"[LAS Import] LAS file parsed successfully")
        
        # Extract well name from parsed LAS object (WELL field in LAS metadata)
        print(f"[LAS Import] Extracting well name from LAS file metadata...")
        well_name = get_well_name_from_las(las_file_path, las_object=las)
        if not well_name:
            return False, f"❌ Cannot extract well name from LAS file '{filename}'", None
        
        print(f"[LAS Import] Well name extracted: '{well_name}'")
        
        # Get dataset name from LAS file or use default
        # Priority: 1) dataset_suffix if provided, 2) LAS SET parameter, 3) default "MAIN"
        dataset_name = 'MAIN'
        if dataset_suffix and dataset_suffix.strip():
            # If suffix is provided, use it as the dataset name
            dataset_name = dataset_suffix.strip()
            print(f"[LAS Import] Using provided dataset suffix as name: {dataset_name}")
        else:
            # Otherwise try to get from LAS SET parameter
            try:
                if hasattr(las.params, 'SET') and las.params.SET.value:
                    dataset_name = str(las.params.SET.value).strip()
                    if dataset_name:
                        print(f"[LAS Import] Using SET parameter from LAS file: {dataset_name}")
            except:
                pass
        
        # Get depth range
        top = 0
        bottom = 0
        try:
            top = las.well.STRT.value if hasattr(las.well, 'STRT') else 0
            bottom = las.well.STOP.value if hasattr(las.well, 'STOP') else 0
        except:
            pass
        
        # Create dataset from LAS file
        dataset = Dataset.from_las(
            filename=las_file_path,
            dataset_name=dataset_name,
            dataset_type=dataset_type,
            well_name=well_name
        )
        
        # Setup wells directory
        wells_folder = os.path.join(project_path, '10-WELLS')
        os.makedirs(wells_folder, exist_ok=True)
        
        well_file_path = os.path.join(wells_folder, f'{well_name}.ptrc')
        
        # Check if well already exists
        well_created = False
        dataset_merged = False
        skipped_duplicate = False
        new_curves_added = []
        duplicate_curves = []
        
        if os.path.exists(well_file_path):
            # Load existing well
            well = Well.deserialize(filepath=well_file_path)
            
            # Get curve names from the new dataset
            new_curve_names = set(log.name for log in dataset.well_logs)
            print(f"[LAS Import] New dataset contains {len(new_curve_names)} curves: {list(new_curve_names)}")
            
            # Find the BEST matching dataset by checking curves (highest overlap ratio)
            matching_dataset = None
            best_overlap_ratio = 0
            best_common_curves = []
            best_unique_curves = []
            
            for existing_dataset in well.datasets:
                # Skip system datasets (REFERENCE, WELL_HEADER)
                if existing_dataset.type in ['REFERENCE', 'WELL_HEADER']:
                    continue
                
                existing_curve_names = set(log.name for log in existing_dataset.well_logs)
                
                # Calculate curve overlap
                common_curves = new_curve_names.intersection(existing_curve_names)
                unique_new_curves = new_curve_names - existing_curve_names
                
                # Calculate overlap ratio (what percentage of new curves already exist in this dataset)
                if len(new_curve_names) > 0:
                    overlap_ratio = len(common_curves) / len(new_curve_names)
                else:
                    overlap_ratio = 0
                
                # If there's overlap and it's better than previous best, update best match
                # Require at least 50% overlap to consider it a match
                if overlap_ratio >= 0.5 and overlap_ratio > best_overlap_ratio:
                    best_overlap_ratio = overlap_ratio
                    matching_dataset = existing_dataset
                    best_common_curves = list(common_curves)
                    best_unique_curves = list(unique_new_curves)
                    print(f"[LAS Import] Found better match: dataset '{existing_dataset.name}' with {len(common_curves)} common curves ({overlap_ratio*100:.1f}% overlap)")
            
            # Use the best match found
            if matching_dataset:
                duplicate_curves = best_common_curves
                new_curves_added = best_unique_curves
                print(f"[LAS Import] Best matching dataset: '{matching_dataset.name}' with {best_overlap_ratio*100:.1f}% overlap")
            
            if matching_dataset:
                # Case 1: All curves already exist - complete duplicate
                if len(new_curves_added) == 0:
                    skipped_duplicate = True
                    status_msg = f"ℹ️ Dataset already available: All {len(duplicate_curves)} curves from '{os.path.basename(las_file_path)}' already exist in dataset '{matching_dataset.name}' of well '{well_name}'"
                    print(f"[LAS Import] Skipping duplicate - all curves already exist")
                    print(f"[LAS Import] Duplicate curves: {duplicate_curves}")
                    return True, status_msg, {
                        'well_name': well_name,
                        'dataset_name': matching_dataset.name,
                        'well_file_path': well_file_path,
                        'las_file_path': las_file_path,
                        'las_destination': None,
                        'well_created': False,
                        'dataset_merged': False,
                        'skipped_duplicate': True,
                        'duplicate_curves': duplicate_curves,
                        'new_curves_added': [],
                        'curves_count': len(dataset.well_logs)
                    }
                
                # Case 2: Some curves are new - merge them
                else:
                    dataset_merged = True
                    print(f"[LAS Import] Merging {len(new_curves_added)} new curves into existing dataset '{matching_dataset.name}'")
                    print(f"[LAS Import] New curves: {new_curves_added}")
                    print(f"[LAS Import] Skipping duplicate curves: {duplicate_curves}")
                    
                    # Add only the new curves to the existing dataset
                    for log in dataset.well_logs:
                        if log.name in new_curves_added:
                            matching_dataset.well_logs.append(log)
                            print(f"[LAS Import] Added new curve '{log.name}' to dataset '{matching_dataset.name}'")
                    
                    # Update the dataset's metadata to track the merge
                    if 'merge_history' not in matching_dataset.metadata:
                        matching_dataset.metadata['merge_history'] = []
                    matching_dataset.metadata['merge_history'].append({
                        'date': datetime.now().isoformat(),
                        'source_file': os.path.basename(las_file_path),
                        'curves_added': new_curves_added,
                        'curves_skipped': duplicate_curves
                    })
            else:
                # Case 3: No matching dataset found - check for name collision and handle versioning
                existing_dataset_names = [dtst.name for dtst in well.datasets]
                original_dataset_name = dataset_name
                if dataset_name in existing_dataset_names:
                    if enable_versioning:
                        # Auto-increment version: MAIN, MAIN_1, MAIN_2, etc.
                        version = 1
                        while f"{original_dataset_name}_{version}" in existing_dataset_names:
                            version += 1
                        dataset_name = f"{original_dataset_name}_{version}"
                        dataset.name = dataset_name
                        print(f"✓ Dataset versioned: {original_dataset_name} → {dataset_name}")
                    else:
                        return False, f"❌ Dataset '{dataset_name}' already exists in well '{well_name}'", None
                
                # Append new dataset
                well.datasets.append(dataset)
                print(f"[LAS Import] Added new dataset '{dataset_name}' to well '{well_name}'")
        else:
            # Create new well with REFERENCE and WELL_HEADER datasets
            well = Well(
                date_created=datetime.now(),
                well_name=well_name,
                well_type='Dev'
            )
            
            # Create REFERENCE dataset
            ref = Dataset.reference(
                top=0,
                bottom=bottom,
                dataset_name='REFERENCE',
                dataset_type='REFERENCE',
                well_name=well_name
            )
            
            # Create WELL_HEADER dataset with WELL_NAME constant
            wh = Dataset.well_header(
                dataset_name='WELL_HEADER',
                dataset_type='WELL_HEADER',
                well_name=well_name
            )
            const = Constant(name='WELL_NAME', value=well.well_name, tag=well.well_name)
            wh.constants.append(const)
            
            well.datasets.append(ref)
            well.datasets.append(wh)
            well.datasets.append(dataset)
            well_created = True
        
        # Save well to file
        well.serialize(filename=well_file_path)
        
        # Copy LAS file to project folder if requested
        las_destination = None
        if copy_las_to_project:
            las_folder = os.path.join(project_path, '02-INPUT_LAS_FOLDER')
            os.makedirs(las_folder, exist_ok=True)
            las_filename = os.path.basename(las_file_path)
            las_destination = os.path.join(las_folder, las_filename)
            
            # Only copy if it's not already in the project folder
            if os.path.abspath(las_file_path) != os.path.abspath(las_destination):
                shutil.copy2(las_file_path, las_destination)
        
        # Build success message
        if dataset_merged:
            status_msg = f"✓ Merged {len(new_curves_added)} new curves from '{os.path.basename(las_file_path)}' into dataset '{dataset_name}' of well '{well_name}'"
            status_msg += f" (skipped {len(duplicate_curves)} duplicate curves)"
        else:
            status_msg = f"✓ Imported dataset '{dataset_name}' from '{os.path.basename(las_file_path)}' into well '{well_name}'"
            if well_created:
                status_msg += " (new well created)"
        
        # Store well in storage session
        try:
            from utils.sqlite_storage import SQLiteStorageService
            cache_service = SQLiteStorageService()
            
            normalized_path = os.path.normpath(project_path)
            hash_object = hashlib.md5(normalized_path.encode())
            session_id = f"project_{hash_object.hexdigest()}"
            
            existing_session = cache_service.load_session(session_id)
            
            if existing_session:
                wells = existing_session.get("wells", {})
                metadata = existing_session.get("metadata", {})
            else:
                wells = {}
                metadata = {
                    "project_path": project_path,
                    "project_name": os.path.basename(project_path),
                    "modified_wells": []
                }
            
            wells[well_name] = well.to_dict()
            cache_service.store_session(session_id, wells, metadata)
        except Exception as storage_error:
            print(f"[Warning] Failed to update JSON storage: {storage_error}")
        
        return True, status_msg, {
            'well_name': well_name,
            'dataset_name': dataset_name,
            'well_file_path': well_file_path,
            'las_file_path': las_file_path,
            'las_destination': las_destination,
            'well_created': well_created,
            'dataset_merged': dataset_merged,
            'skipped_duplicate': skipped_duplicate,
            'new_curves_added': new_curves_added,
            'duplicate_curves': duplicate_curves,
            'curves_count': len(dataset.well_logs)
        }
        
    except PermissionError:
        return False, f"❌ Permission denied: Cannot write to project directory", None
    except Exception as e:
        return False, f"❌ Error creating well from LAS: {str(e)}", None


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
