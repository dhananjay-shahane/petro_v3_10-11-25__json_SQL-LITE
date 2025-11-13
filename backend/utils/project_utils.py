import os
from pathlib import Path
from typing import Dict, List

def create_project_structure(project_name: str, parent_path: str) -> Dict:
    """
    Create a new project with the standard petrophysics folder structure.
    
    Args:
        project_name: Name of the project
        parent_path: Parent directory where project will be created
    
    Returns:
        Dictionary with project details and created folders
    """
    
    # Folder structure from GitHub repository: Project_Manager.py
    standard_folders = [
        "01-OUTPUT",
        "01-OUTPUT/Reports and Presentations",
        "02-INPUT_LAS_FOLDER",
        "03-DEVIATION",
        "04-WELL_HEADER",
        "05-TOPS_FOLDER",
        "06-ZONES_FOLDER",
        "07-DATA_EXPORTS",
        "08-VOL_MODELS",
        "09-SPECS",
        "10-WELLS"
    ]
    
    project_path = os.path.join(parent_path, project_name)
    
    if os.path.exists(project_path):
        raise ValueError(f"Project '{project_name}' already exists at {project_path}")
    
    Path(project_path).mkdir(parents=True, exist_ok=True)
    
    created_folders = []
    for folder in standard_folders:
        folder_path = os.path.join(project_path, folder)
        Path(folder_path).mkdir(parents=True, exist_ok=True)
        created_folders.append(folder)
    
    return {
        'success': True,
        'projectName': project_name,
        'projectPath': project_path,
        'folders': created_folders,
        'message': f'Project "{project_name}" created successfully with {len(created_folders)} standard folders'
    }
