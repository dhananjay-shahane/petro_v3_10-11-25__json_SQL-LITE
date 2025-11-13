import os
import math
from pathlib import Path
from fastapi import HTTPException


WORKSPACE_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "petrophysics-workplace")
ALLOWED_EXTENSIONS = {'las', 'LAS'}


Path(WORKSPACE_ROOT).mkdir(parents=True, exist_ok=True)


def validate_path(path_str: str) -> bool:
    """
    Validate that a path exists and is accessible.
    Returns True if valid, False otherwise.
    
    Note: Allows paths outside WORKSPACE_ROOT to support user's local projects on their PC.
    """
    try:
        # Normalize path separators for cross-platform compatibility
        normalized_path = os.path.normpath(path_str)
        target_path = Path(normalized_path).resolve()
        # Just check if the path exists and is accessible
        return target_path.exists()
    except (OSError, ValueError, TypeError):
        return False


def sanitize_value(value):
    """Convert NaN, Infinity, and other non-JSON values to None"""
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
    return value


def sanitize_list(lst):
    """Convert all NaN values in a list to None"""
    if not lst:
        return []
    return [sanitize_value(v) for v in lst]


def allowed_file(filename: str) -> bool:
    """Check if a file has an allowed extension"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def validate_and_resolve_path(path_str: str, error_msg: str = "Access denied: path outside petrophysics-workplace") -> str:
    """
    Validate and resolve a path, raising HTTPException if invalid.
    Returns the resolved absolute path.
    """
    resolved_path = os.path.abspath(path_str)
    if not validate_path(resolved_path):
        raise HTTPException(status_code=403, detail=error_msg)
    return resolved_path
