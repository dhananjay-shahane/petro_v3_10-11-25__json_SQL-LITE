import os
from fastapi import APIRouter, HTTPException
from typing import List, Optional
from pydantic import BaseModel
from models import WorkspaceInfo, LayoutSaveRequest, LayoutResponse, LayoutListResponse
from dependencies import WORKSPACE_ROOT, validate_path
from utils.sqlite_storage import SQLiteStorageService

cache_service = SQLiteStorageService()


class WindowDataRequest(BaseModel):
    projectPath: str
    window_count: int
    active_window_id: Optional[str]
    window_ids: List[str]
    window_links: dict


class WindowDataResponse(BaseModel):
    success: bool
    window_count: int
    active_window_id: Optional[str]
    window_ids: List[str]
    window_links: dict
    message: str


class WindowActionRequest(BaseModel):
    projectPath: str
    window_id: str


class WindowLinkRequest(BaseModel):
    projectPath: str
    window_id1: str
    window_id2: str


router = APIRouter(prefix="/workspace", tags=["workspace"])


@router.get("/info", response_model=WorkspaceInfo)
async def get_workspace_info():
    """Get workspace information including current opened project from SQLite storage"""
    # Normalize path to use forward slashes for cross-platform compatibility
    abs_path = os.path.abspath(WORKSPACE_ROOT)
    # Convert Windows backslashes to forward slashes for consistency
    normalized_path = abs_path.replace('\\', '/')
    
    current_project = cache_service.load_current_project()
    
    current_project_path = None
    current_project_name = None
    has_open_project = False
    
    if current_project:
        project_path = current_project.get("projectPath")
        if project_path:
            # Resolve relative paths against workspace root
            if not os.path.isabs(project_path):
                project_path = os.path.join(WORKSPACE_ROOT, project_path)
            
            # Check if resolved path exists
            if os.path.exists(project_path) and os.path.isdir(project_path):
                current_project_path = project_path
                current_project_name = current_project.get("projectName")
                has_open_project = True
            else:
                print(f"  [WORKSPACE] Project path does not exist: {project_path}")
                # Don't immediately delete - the project might be valid but temporarily inaccessible
    
    return {
        "workspaceRoot": WORKSPACE_ROOT,
        "absolutePath": normalized_path,
        "exists": os.path.exists(WORKSPACE_ROOT),
        "currentProjectPath": current_project_path,
        "currentProjectName": current_project_name,
        "hasOpenProject": has_open_project
    }


@router.get("/layout", response_model=LayoutResponse)
async def get_layout(projectPath: str, layoutName: str = "default"):
    """Get saved layout for a project by name"""
    try:
        validate_path(projectPath)
        
        # Default font sizes from settings
        default_font_sizes = {
            "dataBrowser": 14,
            "wellList": 14,
            "feedbackLog": 13,
            "zonationList": 14,
            "cliTerminal": 13
        }
        
        layout_data = cache_service.load_layout(projectPath, layoutName)
        
        if layout_data:
            print(f"  [STORAGE] Layout '{layoutName}' loaded from SQLite storage")
            # Get font sizes from layout, use defaults if empty or missing
            stored_font_sizes = layout_data.get("fontSizes", {})
            font_sizes = stored_font_sizes if stored_font_sizes and len(stored_font_sizes) > 0 else default_font_sizes
            
            return {
                "success": True,
                "layout": layout_data.get("layout"),
                "visiblePanels": layout_data.get("visiblePanels", []),
                "windowLinks": layout_data.get("windowLinks", {}),
                "fontSizes": font_sizes,
                "message": f"Layout '{layoutName}' loaded successfully"
            }
        else:
            print(f"  [STORAGE] No layout '{layoutName}' found for project")
            return {
                "success": False,
                "layout": None,
                "visiblePanels": None,
                "windowLinks": None,
                "fontSizes": None,
                "message": "No saved layout found"
            }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load layout: {str(e)}")


@router.post("/layout", response_model=LayoutResponse)
async def save_layout(request: LayoutSaveRequest):
    """Save layout for a project with name, window link states, and font sizes"""
    try:
        validate_path(request.projectPath)
        
        layout_name = request.layoutName or "default"
        
        cache_service.save_layout(
            request.projectPath,
            request.layout,
            request.visiblePanels,
            layout_name,
            request.windowLinks or {},
            request.fontSizes or {}
        )
        
        print(f"  [STORAGE] Layout '{layout_name}' saved to SQLite storage with window links and font sizes")
        
        return {
            "success": True,
            "layout": request.layout,
            "visiblePanels": request.visiblePanels,
            "windowLinks": request.windowLinks,
            "fontSizes": request.fontSizes,
            "message": f"Layout '{layout_name}' saved successfully"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save layout: {str(e)}")


@router.get("/layouts/list", response_model=LayoutListResponse)
async def get_layout_list(projectPath: str):
    """Get list of all saved layout names for a project"""
    try:
        validate_path(projectPath)
        
        layout_names = cache_service.get_saved_layout_names(projectPath)
        
        return {
            "success": True,
            "layouts": layout_names,
            "message": f"Found {len(layout_names)} saved layouts"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get layout list: {str(e)}")


@router.delete("/layout", response_model=LayoutResponse)
async def delete_layout(projectPath: str, layoutName: str = "default"):
    """Delete saved layout for a project"""
    try:
        validate_path(projectPath)
        
        cache_service.delete_layout(projectPath, layoutName)
        
        return {
            "success": True,
            "layout": None,
            "visiblePanels": None,
            "windowLinks": None,
            "message": f"Layout '{layoutName}' deleted successfully"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete layout: {str(e)}")


# Temporarily disabled: window management methods not yet implemented in SQLiteStorageService
# @router.get("/windows", response_model=WindowDataResponse)
# async def get_window_data(projectPath: str):
#     """Get window management data for a specific project"""
#     try:
#         validate_path(projectPath)
#         window_data = cache_service.load_window_data(projectPath)
#         return {
#             "success": True,
#             "window_count": window_data.get("count", 0),
#             "active_window_id": window_data.get("active_window_id"),
#             "window_ids": window_data.get("window_ids", []),
#             "window_links": window_data.get("window_links", {}),
#             "message": "Window data loaded successfully"
#         }
#     except ValueError as e:
#         raise HTTPException(status_code=400, detail=str(e))
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Failed to load window data: {str(e)}")


# @router.post("/windows", response_model=WindowDataResponse)
# async def save_window_data(request: WindowDataRequest):
#     """Save complete window management data for a specific project"""
#     try:
#         validate_path(request.projectPath)
#         cache_service.save_window_data(
#             project_path=request.projectPath,
#             window_count=request.window_count,
#             active_window_id=request.active_window_id,
#             window_ids=request.window_ids,
#             window_links=request.window_links
#         )
#         
#         return {
#             "success": True,
#             "window_count": request.window_count,
#             "active_window_id": request.active_window_id,
#             "window_ids": request.window_ids,
#             "window_links": request.window_links,
#             "message": "Window data saved successfully"
#         }
#     except ValueError as e:
#         raise HTTPException(status_code=400, detail=str(e))
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Failed to save window data: {str(e)}")


# @router.post("/windows/add")
# async def add_window(request: WindowActionRequest):
#     """Add a new window for a specific project"""
#     try:
#         validate_path(request.projectPath)
#         cache_service.add_window(request.projectPath, request.window_id)
#         window_data = cache_service.load_window_data(request.projectPath)
#         return {
#             "success": True,
#             "window_id": request.window_id,
#             "window_count": window_data.get("count", 0),
#             "message": f"Window {request.window_id} added successfully"
#         }
#     except ValueError as e:
#         raise HTTPException(status_code=400, detail=str(e))
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Failed to add window: {str(e)}")


# @router.post("/windows/remove")
# async def remove_window(request: WindowActionRequest):
#     """Remove a window from a specific project"""
#     try:
#         validate_path(request.projectPath)
#         cache_service.remove_window(request.projectPath, request.window_id)
#         window_data = cache_service.load_window_data(request.projectPath)
#         return {
#             "success": True,
#             "window_id": request.window_id,
#             "window_count": window_data.get("count", 0),
#             "message": f"Window {request.window_id} removed successfully"
#         }
#     except ValueError as e:
#         raise HTTPException(status_code=400, detail=str(e))
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Failed to remove window: {str(e)}")


@router.post("/windows/set-active")
async def set_active_window(request: WindowActionRequest):
    """Set the active window for a specific project"""
    try:
        validate_path(request.projectPath)
        cache_service.update_active_window(request.projectPath, request.window_id)
        return {
            "success": True,
            "window_id": request.window_id,
            "message": f"Active window set to {request.window_id}"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to set active window: {str(e)}")


@router.post("/windows/link")
async def link_windows(request: WindowLinkRequest):
    """Link two windows together for a specific project"""
    try:
        validate_path(request.projectPath)
        cache_service.link_windows(request.projectPath, request.window_id1, request.window_id2)
        return {
            "success": True,
            "window_id1": request.window_id1,
            "window_id2": request.window_id2,
            "message": f"Windows {request.window_id1} and {request.window_id2} linked successfully"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to link windows: {str(e)}")


@router.post("/windows/unlink")
async def unlink_windows(request: WindowLinkRequest):
    """Unlink two windows for a specific project"""
    try:
        validate_path(request.projectPath)
        cache_service.unlink_windows(request.projectPath, request.window_id1, request.window_id2)
        return {
            "success": True,
            "window_id1": request.window_id1,
            "window_id2": request.window_id2,
            "message": f"Windows {request.window_id1} and {request.window_id2} unlinked successfully"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to unlink windows: {str(e)}")


@router.get("/windows/{window_id}/linked")
async def get_linked_windows(window_id: str, projectPath: str):
    """Get all windows linked to a specific window for a specific project"""
    try:
        validate_path(projectPath)
        linked_windows = cache_service.get_linked_windows(projectPath, window_id)
        return {
            "success": True,
            "window_id": window_id,
            "linked_windows": linked_windows,
            "message": f"Found {len(linked_windows)} linked windows"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get linked windows: {str(e)}")
