import os
import json
from fastapi import APIRouter, HTTPException
from models import DataListResponse, FileContentResponse
from dependencies import WORKSPACE_ROOT, validate_path


router = APIRouter(prefix="/data", tags=["data"])


@router.get("/list", response_model=DataListResponse)
async def list_data(path: str):
    """List files and directories in a given path"""
    try:
        dir_path = path
        
        if not dir_path:
            raise HTTPException(status_code=400, detail="Path is required")
        
        if not os.path.exists(dir_path):
            dir_path = WORKSPACE_ROOT
        
        resolved_path = os.path.abspath(dir_path)
        if not validate_path(resolved_path):
            resolved_path = os.path.abspath(WORKSPACE_ROOT)
        
        if not os.path.isdir(resolved_path):
            raise HTTPException(status_code=400, detail="Path is not a directory")
        
        items = []
        for item in os.listdir(resolved_path):
            if not item.startswith('.'):
                item_path = os.path.join(resolved_path, item)
                is_dir = os.path.isdir(item_path)
                
                has_files = False
                if is_dir:
                    try:
                        has_files = any(os.path.isfile(os.path.join(item_path, f))
                                      for f in os.listdir(item_path))
                    except:
                        pass
                
                items.append({
                    "name": item,
                    "path": item_path,
                    "type": "directory" if is_dir else "file",
                    "hasFiles": has_files
                })
        
        items.sort(key=lambda x: (x['type'] != 'directory', x['name']))
        can_go_up = resolved_path != WORKSPACE_ROOT
        
        return {
            "currentPath": resolved_path,
            "parentPath": os.path.dirname(resolved_path) if can_go_up else resolved_path,
            "items": items,
            "canGoUp": can_go_up
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/file", response_model=FileContentResponse)
async def read_file(path: str):
    """Read file content"""
    try:
        if not path:
            raise HTTPException(status_code=400, detail="File path is required")
        
        resolved_path = os.path.abspath(path)
        if not validate_path(resolved_path):
            raise HTTPException(
                status_code=403,
                detail="Access denied: path outside petrophysics-workplace"
            )
        
        if not os.path.isfile(resolved_path):
            raise HTTPException(status_code=400, detail="Path is not a file")
        
        with open(resolved_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        try:
            json_content = json.loads(content)
            return {"content": json_content}
        except:
            return {"content": content}
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read file: {str(e)}")
