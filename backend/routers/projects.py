import os
import hashlib
import shutil
from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from models import ProjectCreate, ProjectResponse, ErrorResponse
from dependencies import WORKSPACE_ROOT, validate_path
from utils.project_utils import create_project_structure
from utils.fe_data_objects import Well
from utils.sqlite_storage import SQLiteStorageService
from utils.file_well_storage import get_file_well_storage

cache_service = SQLiteStorageService()


router = APIRouter(prefix="/projects", tags=["projects"])


class ProjectExistsResponse(BaseModel):
    exists: bool
    path: str
    isValid: bool


class LoadAllWellsRequest(BaseModel):
    projectPath: str


class LoadAllWellsResponse(BaseModel):
    success: bool
    sessionId: str
    totalWells: int
    loadedWells: int
    failedWells: list
    message: str


class SetCurrentProjectRequest(BaseModel):
    projectPath: str
    projectName: str


class SetCurrentProjectResponse(BaseModel):
    success: bool
    message: str
    projectPath: str
    projectName: str


class DeleteProjectRequest(BaseModel):
    projectPath: str


class DeleteProjectResponse(BaseModel):
    success: bool
    message: str


class MigrateWellsRequest(BaseModel):
    projectPath: str


class MigrateWellsResponse(BaseModel):
    success: bool
    message: str
    totalWells: int
    migratedWells: int
    failedWells: list


def get_project_session_id(project_path: str) -> str:
    """Generate a consistent session ID for a project path"""
    normalized_path = os.path.normpath(project_path)
    hash_object = hashlib.md5(normalized_path.encode())
    return f"project_{hash_object.hexdigest()}"


@router.get("/exists", response_model=ProjectExistsResponse)
async def check_project_exists(projectPath: str):
    """Check if a project directory exists and is valid"""
    try:
        if not projectPath:
            return ProjectExistsResponse(exists=False, path="", isValid=False)
        
        resolved_path = os.path.abspath(projectPath)
        
        # Check if path is valid (within workspace)
        is_valid = validate_path(resolved_path)
        
        # Check if directory exists
        exists = os.path.exists(resolved_path) and os.path.isdir(resolved_path)
        
        return ProjectExistsResponse(
            exists=exists,
            path=resolved_path,
            isValid=is_valid
        )
    except Exception as e:
        return ProjectExistsResponse(exists=False, path=projectPath, isValid=False)


@router.post("/create", response_model=ProjectResponse, status_code=201)
async def create_project(project: ProjectCreate):
    """Create a new project with folder structure"""
    try:
        project_name = project.name.strip()
        parent_path = project.path.strip() if project.path else WORKSPACE_ROOT
        
        if not project_name:
            raise HTTPException(status_code=400, detail="Project name is required")
        
        if not project_name.replace('-', '').replace('_', '').replace(' ', '').isalnum():
            raise HTTPException(
                status_code=400,
                detail="Project name can only contain letters, numbers, hyphens, underscores, and spaces"
            )
        
        # Normalize path separators for cross-platform compatibility (Windows/Unix)
        normalized_parent = os.path.normpath(parent_path)
        resolved_parent = os.path.abspath(normalized_parent)
        
        # Check if parent directory exists
        if not os.path.exists(resolved_parent):
            raise HTTPException(
                status_code=400, 
                detail=f"Parent directory does not exist: {resolved_parent}"
            )
        
        # Check if it's a directory
        if not os.path.isdir(resolved_parent):
            raise HTTPException(
                status_code=400,
                detail=f"Path is not a directory: {resolved_parent}"
            )
        
        result = create_project_structure(project_name, resolved_parent)
        
        # Initialize JSON storage data for the new project
        try:
            project_path = result['projectPath']
            
            # Initialize empty/default layout in JSON storage
            default_layout = {
                "layout": {},
                "visiblePanels": ["wells", "zonation", "dataBrowser", "feedback", "cli"],
                "savedAt": None
            }
            cache_service.save_layout(project_path, default_layout["layout"], default_layout["visiblePanels"])
            
            # Initialize empty selected wells list
            cache_service.save_selected_wells(project_path, [])
            
            # Set this project as the current project in JSON storage
            cache_service.save_current_project(project_path, project_name)
            
            print(f"[Projects] Initialized JSON storage data for new project: {project_path}")
        except Exception as storage_error:
            # Don't fail project creation if JSON storage init fails
            print(f"[Projects] Warning: Could not initialize JSON storage data: {storage_error}")
        
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create project: {str(e)}")


@router.post("/load-all-wells", response_model=LoadAllWellsResponse)
async def load_all_wells(request: LoadAllWellsRequest):
    """
    Load ALL wells from a project into JSON storage cache for eager loading.
    
    This endpoint:
    1. Validates the project path
    2. Enumerates all .ptrc wells in the project
    3. Deserializes each well from disk
    4. Stores all wells in JSON storage with project-based session ID
    5. Returns summary of loaded wells
    """
    try:
        project_path = os.path.abspath(request.projectPath)
        if not validate_path(project_path):
            raise HTTPException(
                status_code=403,
                detail="Access denied: path outside petrophysics-workplace"
            )
        
        if not os.path.exists(project_path):
            raise HTTPException(status_code=404, detail="Project path does not exist")
        
        wells_folder = os.path.join(project_path, "10-WELLS")
        
        if not os.path.exists(wells_folder):
            return {
                "success": True,
                "sessionId": get_project_session_id(project_path),
                "totalWells": 0,
                "loadedWells": 0,
                "failedWells": [],
                "message": "No wells folder found in project"
            }
        
        session_id = get_project_session_id(project_path)
        project_name = os.path.basename(project_path)
        
        wells_dict = {}
        failed_wells = []
        total_count = 0
        loaded_count = 0
        
        # Use FileWellStorage cache instead of reading from disk
        file_storage = get_file_well_storage()
        
        for filename in os.listdir(wells_folder):
            if filename.endswith('.ptrc'):
                total_count += 1
                well_name = filename.replace('.ptrc', '')
                
                try:
                    # Fetch from cache (already preloaded at startup)
                    well_data_dict = file_storage.load_well_data(project_path, well_name)
                    if well_data_dict:
                        wells_dict[well_name] = well_data_dict
                        loaded_count += 1
                        print(f"[LoadAllWells] Loaded well '{well_name}' from cache")
                    else:
                        failed_wells.append({"well": well_name, "error": "Well not found in cache"})
                        print(f"[LoadAllWells] Failed to load well '{well_name}': not in cache")
                except Exception as e:
                    failed_wells.append({"well": well_name, "error": str(e)})
                    print(f"[LoadAllWells] Failed to load well '{well_name}': {e}")
        
        metadata = {
            "project_path": project_path,
            "project_name": project_name,
            "modified_wells": []
        }
        
        cache_service.store_session(session_id, wells_dict, metadata)
        print(f"[LoadAllWells] Stored {loaded_count} wells in JSON storage session {session_id}")
        
        return {
            "success": True,
            "sessionId": session_id,
            "totalWells": total_count,
            "loadedWells": loaded_count,
            "failedWells": failed_wells,
            "message": f"Successfully loaded {loaded_count} of {total_count} wells into JSON storage"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[LoadAllWells] Error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load wells: {str(e)}")


@router.post("/set-current", response_model=SetCurrentProjectResponse)
async def set_current_project(request: SetCurrentProjectRequest):
    """
    Set the current opened project in JSON storage memory.
    This is called when a user opens an existing project.
    Also triggers eager loading of all wells for the new project.
    """
    try:
        project_path = os.path.abspath(request.projectPath)
        
        if not validate_path(project_path):
            raise HTTPException(
                status_code=403,
                detail="Access denied: path outside petrophysics-workplace"
            )
        
        if not os.path.exists(project_path):
            raise HTTPException(status_code=404, detail="Project path does not exist")
        
        if not os.path.isdir(project_path):
            raise HTTPException(status_code=400, detail="Path is not a directory")
        
        # Save current project
        cache_service.save_current_project(project_path, request.projectName)
        
        print(f"[Projects] Current project set to: {request.projectName} at {project_path}")
        
        # EAGER LOADING: Preload all wells for the new project
        try:
            file_storage = get_file_well_storage()
            
            # Clear previous project cache (optional - saves memory)
            # We could skip this if we want to keep multiple projects in cache
            
            # Preload the new project
            stats = await file_storage.preload_project(project_path)
            print(f"[Projects] Preloaded {stats['loaded_wells']}/{stats['total_wells']} wells for new project")
        except Exception as e:
            print(f"[Projects] Warning: Failed to preload wells: {e}")
            # Don't fail the request if preload fails - wells will lazy load instead
        
        return {
            "success": True,
            "message": f"Current project set to {request.projectName}",
            "projectPath": project_path,
            "projectName": request.projectName
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to set current project: {str(e)}")


@router.post("/migrate-wells", response_model=MigrateWellsResponse)
async def migrate_wells_to_sqlite(request: MigrateWellsRequest = Body(...)):
    """
    DEPRECATED: Wells are now stored in .ptrc files only, not SQLite.
    This endpoint is kept for backwards compatibility but does nothing.
    """
    try:
        project_path = os.path.abspath(request.projectPath)
        
        if not validate_path(project_path):
            raise HTTPException(
                status_code=403,
                detail="Access denied: path outside petrophysics-workplace"
            )
        
        if not os.path.exists(project_path):
            raise HTTPException(status_code=404, detail="Project path does not exist")
        
        wells_folder = os.path.join(project_path, "10-WELLS")
        
        total_count = 0
        if os.path.exists(wells_folder):
            for filename in os.listdir(wells_folder):
                if filename.endswith('.ptrc'):
                    total_count += 1
        
        print(f"[MigrateWells] DEPRECATED: Wells are stored in .ptrc files, no migration needed")
        
        return {
            "success": True,
            "message": f"Wells are stored in .ptrc files ({total_count} found). No migration needed.",
            "totalWells": total_count,
            "migratedWells": total_count,  # Report all as "migrated" (already in files)
            "failedWells": []
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[MigrateWells] Error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to check wells: {str(e)}")


@router.delete("/delete", response_model=DeleteProjectResponse)
async def delete_project(request: DeleteProjectRequest = Body(...)):
    """
    Delete a project and clean up all associated JSON storage data.
    This removes: layout, selected wells, active well, CLI history, sessions, and current project.
    """
    try:
        project_path = os.path.abspath(request.projectPath)
        
        if not validate_path(project_path):
            raise HTTPException(
                status_code=403,
                detail="Access denied: path outside petrophysics-workplace"
            )
        
        if not os.path.exists(project_path):
            raise HTTPException(status_code=404, detail="Project not found")
        
        if not os.path.isdir(project_path):
            raise HTTPException(status_code=400, detail="Path is not a directory")
        
        if project_path == WORKSPACE_ROOT:
            raise HTTPException(status_code=403, detail="Cannot delete workspace root")
        
        project_name = os.path.basename(project_path)
        
        shutil.rmtree(project_path)
        
        cache_service.delete_all_project_data(project_path)
        
        print(f"[Projects] Deleted project: {project_name} at {project_path}")
        
        return {
            "success": True,
            "message": f"Project '{project_name}' deleted successfully",
            "deletedPath": project_path
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete project: {str(e)}")
