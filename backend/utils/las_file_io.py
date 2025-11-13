"""
Utility for reading LAS files and converting to Dataset objects.
"""

from typing import List, Optional, Tuple, Dict, Any
import lasio
from datetime import datetime
import math
import os
import shutil
from pathlib import Path

from utils.fe_data_objects import Dataset, WellLog, Well, Constant


def get_well_name_from_las(las_file_path: str, las_object=None) -> Optional[str]:
    """
    Extract well name from LAS file METADATA (WELL field inside the LAS file).
    This extracts the well name from INSIDE the LAS file data, NOT from the file path.
    Matches the exact logic from the create_from_las API endpoint.
    
    Args:
        las_file_path: Path to the LAS file (only used for error messages and fallback)
        las_object: Optional pre-parsed lasio object (to avoid re-parsing)
        
    Returns:
        Well name from LAS file WELL field in metadata. Falls back to filename stem only if not found.
    """
    try:
        # Use provided LAS object or parse the file
        if las_object is None:
            las = lasio.read(las_file_path)
        else:
            las = las_object
        
        well_name = None
        
        # PRIORITY 1: Try to get well name from WELL field using direct access
        try:
            if hasattr(las.well, 'WELL'):
                well_obj = las.well.WELL
                if well_obj and well_obj.value:
                    well_name = str(well_obj.value).strip()
                    if well_name:  # Ensure it's not empty string
                        print(f"[LAS Import] Extracted well name from WELL field: {well_name}")
                        return well_name
        except Exception as e:
            print(f"[LAS Import] Error accessing WELL field directly: {e}")
        
        # PRIORITY 2: Try iterating through well items looking for WELL mnemonic
        if not well_name:
            try:
                for item in las.well:
                    if item.mnemonic.upper() == 'WELL' and item.value:
                        well_name = str(item.value).strip()
                        if well_name:  # Ensure it's not empty string
                            print(f"[LAS Import] Extracted well name from well items: {well_name}")
                            return well_name
            except Exception as e:
                print(f"[LAS Import] Error iterating well items: {e}")
        
        # LAST RESORT: If no well name found in LAS metadata, use filename without extension
        filename_stem = Path(las_file_path).stem
        print(f"[LAS Import] No WELL field found in LAS metadata, using filename: {filename_stem}")
        return filename_stem
        
    except Exception as e:
        # If reading fails, return filename without extension
        base_name = Path(las_file_path).stem
        print(f"[LAS Import] Error reading LAS file: {e}, using filename: {base_name}")
        return base_name


def read_las_file(filename: str) -> List[Dataset]:
    """
    Read a LAS file and convert it to Dataset objects.
    
    Args:
        filename: Path to the LAS file
        
    Returns:
        List of Dataset objects (typically one MAIN dataset with all curves)
    """
    las = lasio.read(filename)
    df = las.df()
    df.reset_index(inplace=True)
    
    possible_index = ['DEPT', 'DEPTH']
    found_index = list(filter(lambda x: x in df.columns, possible_index))
    
    if not found_index:
        raise ValueError(f"LAS file must contain a depth column (DEPT or DEPTH)")
    
    index_name = found_index[0]
    index_log = df[index_name].tolist()
    index_log = [None if (isinstance(v, float) and math.isnan(v)) else v for v in index_log]
    
    interp = "CONTINUOUS"
    logs = []
    
    for col_index, column in enumerate(df.columns):
        log_values = df.iloc[:, col_index].tolist()
        log_values = [None if (isinstance(v, float) and math.isnan(v)) else v for v in log_values]
        log_type = 'float'
        
        well_log = WellLog(
            name=column,
            date=datetime.now().isoformat(),
            description='',
            interpolation=interp,
            log_type=log_type,
            log=log_values,
            dtst='WIRE'
        )
        logs.append(well_log)
    
    dataset = Dataset(
        date_created=datetime.now(),
        name='MAIN',
        type='CONTINUOUS',
        wellname='',
        index_log=index_log,
        index_name=index_name,
        well_logs=logs,
        metadata={'source': 'LAS import'}
    )
    
    return [dataset]


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
        if os.path.exists(well_file_path):
            # Load existing well
            well = Well.deserialize(filepath=well_file_path)
            
            # Check for duplicate dataset and handle versioning
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
        status_msg = f"✓ Imported dataset '{dataset_name}' from '{os.path.basename(las_file_path)}' into well '{well_name}'"
        if well_created:
            status_msg += " (new well created)"
        
        # Store well in storage session
        try:
            from utils.sqlite_storage import SQLiteStorageService
            import hashlib
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
            'curves_count': len(dataset.well_logs)
        }
        
    except PermissionError:
        return False, f"❌ Permission denied: Cannot write to project directory", None
    except Exception as e:
        return False, f"❌ Error creating well from LAS: {str(e)}", None
