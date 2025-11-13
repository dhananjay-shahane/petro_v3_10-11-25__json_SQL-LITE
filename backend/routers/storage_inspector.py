import json
from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List
from utils.sqlite_storage import SQLiteStorageService

storage_service = SQLiteStorageService()
router = APIRouter(prefix="/storage", tags=["storage-inspector"])


@router.get("/keys")
async def list_all_keys():
    """List all keys currently stored in JSON storage"""
    try:
        keys = storage_service.get_all_keys()
        return {
            "success": True,
            "total_keys": len(keys),
            "keys": keys,
            "message": f"Found {len(keys)} keys in JSON storage"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/inspect/{key_type}/{key_id}")
async def inspect_key(key_type: str, key_id: str):
    """Inspect a specific key in storage - view its data and metadata"""
    try:
        result = None
        
        if key_type == "session":
            result = storage_service.load_session(key_id)
        elif key_type == "project":
            result = storage_service.load_project_data(key_id)
        elif key_type == "current_project":
            result = storage_service.load_current_project()
        else:
            raise HTTPException(status_code=400, detail=f"Invalid key type: {key_type}")
        
        if result is None:
            raise HTTPException(status_code=404, detail=f"Key '{key_type}:{key_id}' not found in storage")
        
        # Calculate approximate size
        size_bytes = len(json.dumps(result, default=str))
        
        return {
            "success": True,
            "key": f"{key_type}:{key_id}",
            "type": key_type,
            "data": result,
            "size_bytes": size_bytes,
            "message": f"Key '{key_type}:{key_id}' inspected successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/all")
async def list_all_sessions():
    """List all well sessions currently in storage"""
    try:
        from datetime import datetime
        
        sessions = []
        all_sessions = storage_service.get_all_sessions()
        
        for session_id, session_data in all_sessions.items():
            try:
                well_count = 0
                well_names = []
                
                if isinstance(session_data, dict):
                    if "wells" in session_data:
                        wells = session_data.get("wells", {})
                        well_count = len(wells)
                        well_names = list(wells.keys())
                    if "metadata" in session_data:
                        metadata = session_data.get("metadata", {})
                        well_count = metadata.get("total_wells", well_count)
                        well_names = metadata.get("well_names", well_names)
                
                # Calculate TTL
                expires_at_str = session_data.get("expires_at")
                ttl_seconds = -1
                if expires_at_str:
                    try:
                        expires_at = datetime.fromisoformat(expires_at_str)
                        ttl = (expires_at - datetime.now()).total_seconds()
                        ttl_seconds = int(ttl) if ttl > 0 else -2
                    except:
                        pass
                
                size_bytes = len(json.dumps(session_data, default=str))
                
                sessions.append({
                    "session_id": session_id,
                    "ttl_seconds": ttl_seconds,
                    "ttl_hours": round(ttl_seconds / 3600, 2) if ttl_seconds > 0 else None,
                    "well_count": well_count,
                    "well_names": well_names,
                    "size_bytes": size_bytes
                })
            except Exception as e:
                continue
        
        return {
            "success": True,
            "total_sessions": len(sessions),
            "sessions": sessions,
            "message": f"Found {len(sessions)} active sessions in storage"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/info")
async def storage_info():
    """Get JSON storage statistics and information"""
    try:
        info = storage_service.get_storage_info()
        
        return {
            "success": True,
            "storage": {
                "file_path": info["file_path"],
                "file_size_bytes": info["file_size_bytes"],
                "file_size_kb": info["file_size_kb"],
                "total_sessions": info["total_sessions"],
                "total_projects": info["total_projects"],
            },
            "current_project": info.get("current_project"),
            "message": "Storage information retrieved"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/clear-all")
async def clear_all_storage_data():
    """DANGER: Clear all data from JSON storage (use for testing/debugging only)"""
    try:
        storage_service.clear_all_data()
        return {
            "success": True,
            "message": "All storage data cleared"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
