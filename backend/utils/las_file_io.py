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


