import os
import shutil
from pathlib import Path
from fastapi import APIRouter, HTTPException
from models import (
    DirectoryListResponse, DirectoryCreate, DirectoryDelete,
    DirectoryRename, DirectoryResponse, DirectoryItem
)
from dependencies import WORKSPACE_ROOT, validate_path


router = APIRouter(prefix="/directories", tags=["directories"])


@router.get("/list", response_model=DirectoryListResponse)
async def list_directories(path: str = WORKSPACE_ROOT):
    """List directories in a given path"""
    try:
        dir_path = path
        
        if not dir_path or not os.path.exists(dir_path):
            dir_path = WORKSPACE_ROOT
        
        resolved_path = os.path.abspath(dir_path)
        
        if not validate_path(resolved_path):
            resolved_path = os.path.abspath(WORKSPACE_ROOT)
        
        if not os.path.exists(resolved_path):
            Path(WORKSPACE_ROOT).mkdir(parents=True, exist_ok=True)
            return {
                "currentPath": WORKSPACE_ROOT,
                "parentPath": WORKSPACE_ROOT,
                "directories": [],
                "canGoUp": False
            }
        
        if not os.path.isdir(resolved_path):
            raise HTTPException(status_code=400, detail="Path is not a directory")
        
        items = []
        for item in os.listdir(resolved_path):
            if not item.startswith('.'):
                item_path = os.path.join(resolved_path, item)
                if os.path.isdir(item_path):
                    items.append({"name": item, "path": item_path})
        
        items.sort(key=lambda x: x['name'])
        can_go_up = resolved_path != WORKSPACE_ROOT
        
        return {
            "currentPath": resolved_path,
            "parentPath": os.path.dirname(resolved_path) if can_go_up else resolved_path,
            "directories": items,
            "canGoUp": can_go_up
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/create", response_model=DirectoryResponse)
async def create_directory(data: DirectoryCreate):
    """Create a new directory"""
    try:
        parent_path = data.parentPath
        folder_name = data.folderName.strip()
        
        if not folder_name:
            raise HTTPException(status_code=400, detail="Folder name is required")
        
        if not folder_name.replace('-', '').replace('_', '').isalnum():
            raise HTTPException(
                status_code=400,
                detail="Folder name can only contain letters, numbers, hyphens, and underscores"
            )
        
        resolved_parent = os.path.abspath(parent_path)
        if not validate_path(resolved_parent):
            raise HTTPException(
                status_code=403,
                detail="Access denied: path outside petrophysics-workplace"
            )
        
        new_folder_path = os.path.join(resolved_parent, folder_name)
        
        if os.path.exists(new_folder_path):
            raise HTTPException(status_code=400, detail="Folder already exists")
        
        os.makedirs(new_folder_path)
        
        return {
            "success": True,
            "message": "Folder created successfully",
            "path": new_folder_path,
            "name": folder_name
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/delete", response_model=DirectoryResponse)
async def delete_directory(data: DirectoryDelete):
    """Delete a directory"""
    try:
        folder_path = data.folderPath.strip()
        
        if not folder_path:
            raise HTTPException(status_code=400, detail="Folder path is required")
        
        resolved_path = os.path.abspath(folder_path)
        if not validate_path(resolved_path):
            raise HTTPException(
                status_code=403,
                detail="Access denied: path outside petrophysics-workplace"
            )
        
        if resolved_path == WORKSPACE_ROOT:
            raise HTTPException(status_code=403, detail="Cannot delete workspace root")
        
        if not os.path.exists(resolved_path):
            raise HTTPException(status_code=404, detail="Folder not found")
        
        if not os.path.isdir(resolved_path):
            raise HTTPException(status_code=400, detail="Path is not a directory")
        
        shutil.rmtree(resolved_path)
        
        return {
            "success": True,
            "message": "Folder deleted successfully",
            "path": resolved_path
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/rename", response_model=DirectoryResponse)
async def rename_directory(data: DirectoryRename):
    """Rename a directory"""
    try:
        folder_path = data.folderPath.strip()
        new_name = data.newName.strip()
        
        if not folder_path:
            raise HTTPException(status_code=400, detail="Folder path is required")
        
        if not new_name:
            raise HTTPException(status_code=400, detail="New folder name is required")
        
        if not new_name.replace('-', '').replace('_', '').isalnum():
            raise HTTPException(
                status_code=400,
                detail="Folder name can only contain letters, numbers, hyphens, and underscores"
            )
        
        resolved_path = os.path.abspath(folder_path)
        if not validate_path(resolved_path):
            raise HTTPException(
                status_code=403,
                detail="Access denied: path outside petrophysics-workplace"
            )
        
        if resolved_path == WORKSPACE_ROOT:
            raise HTTPException(status_code=403, detail="Cannot rename workspace root")
        
        if not os.path.exists(resolved_path):
            raise HTTPException(status_code=404, detail="Folder not found")
        
        if not os.path.isdir(resolved_path):
            raise HTTPException(status_code=400, detail="Path is not a directory")
        
        parent_dir = os.path.dirname(resolved_path)
        new_path = os.path.join(parent_dir, new_name)
        
        if os.path.exists(new_path):
            raise HTTPException(status_code=400, detail="A folder with this name already exists")
        
        os.rename(resolved_path, new_path)
        
        return {
            "success": True,
            "message": "Folder renamed successfully",
            "oldPath": resolved_path,
            "newPath": new_path,
            "newName": new_name,
            "path": new_path
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
