import os
from fastapi import APIRouter, HTTPException
from typing import Optional

from models import (
    SessionCreateRequest, SessionCreateResponse,
    SessionInfoResponse, SessionUpdateRequest,
    SessionUpdateResponse, SessionCommitResponse
)
from dependencies import validate_path
from utils.sqlite_storage import SQLiteStorageService
from utils.well_session_manager import WellSessionManager
from utils.fe_data_objects import Dataset, WellLog, Constant
from datetime import datetime

cache_service = SQLiteStorageService()


router = APIRouter(prefix="/well-sessions", tags=["well-sessions"])


@router.post("/create", response_model=SessionCreateResponse, status_code=201)
async def create_session(request: SessionCreateRequest):
    """
    Create a new well session and load selected wells into JSON storage.
    
    This endpoint:
    1. Validates the project path
    2. Creates a new session ID
    3. Loads specified wells from .ptrc files
    4. Stores them in JSON storage
    5. Returns session ID and summary
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
        
        session_id = cache_service.generate_session_id()
        project_name = os.path.basename(project_path)
        
        manager = WellSessionManager(
            project_path=project_path,
            project_name=project_name,
            session_id=session_id
        )
        
        loaded_wells = manager.load_wells(request.wellNames)
        
        session_data = manager.get_session_well_data()
        metadata = manager.get_metadata()
        cache_service.store_session(session_id, session_data, metadata)
        
        summary = manager.get_session_summary()
        
        return {
            "success": True,
            "sessionId": session_id,
            "message": f"Session created with {summary['total_wells']} wells loaded",
            "loadedWells": loaded_wells,
            "summary": summary
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{session_id}", response_model=SessionInfoResponse)
async def get_session_info(session_id: str):
    """
    Get information about a session including TTL and summary.
    """
    try:
        if not cache_service.session_exists(session_id):
            return {
                "success": True,
                "sessionId": session_id,
                "exists": False,
                "ttl": None,
                "summary": None
            }
        
        full_session = cache_service.load_session(session_id)
        if not full_session:
            return {
                "success": True,
                "sessionId": session_id,
                "exists": False,
                "ttl": None,
                "summary": None
            }
        
        ttl = cache_service.get_session_ttl(session_id)
        
        wells_data = full_session.get("wells", {})
        metadata = full_session.get("metadata", {})
        well_names = list(wells_data.keys())
        
        summary = {
            "total_wells": len(well_names),
            "well_names": well_names,
            "modified_wells": metadata.get("modified_wells", []),
            "project_path": metadata.get("project_path"),
            "ttl_seconds": ttl
        }
        
        return {
            "success": True,
            "sessionId": session_id,
            "exists": True,
            "ttl": ttl,
            "summary": summary
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{session_id}/extend")
async def extend_session(session_id: str):
    """Extend session expiry by another 4 hours."""
    try:
        if not cache_service.session_exists(session_id):
            raise HTTPException(status_code=404, detail="Session not found or expired")
        
        cache_service.extend_session(session_id)
        
        return {
            "success": True,
            "message": "Session expiry extended by 4 hours"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{session_id}/update", response_model=SessionUpdateResponse)
async def update_well_in_session(session_id: str, request: SessionUpdateRequest):
    """
    Update a well in the session (add/remove datasets, update properties, etc.).
    
    Supported actions:
    - 'mark_modified': Mark a well as modified
    - 'update_property': Update a well property (data: {property_name, value})
    - 'add_dataset': Add a dataset to a well (data: dataset dict)
    - 'remove_dataset': Remove a dataset from a well (data: {dataset_name})
    """
    try:
        full_session = cache_service.load_session(session_id)
        if not full_session:
            raise HTTPException(status_code=404, detail="Session not found or expired")
        
        wells_data = full_session.get("wells", {})
        metadata = full_session.get("metadata", {})
        
        project_path = metadata.get("project_path")
        if not project_path:
            raise HTTPException(
                status_code=500,
                detail="Session metadata corrupted: missing project_path"
            )
        
        manager = WellSessionManager(
            project_path=project_path,
            initial_well_data=wells_data
        )
        
        manager.restore_metadata(metadata)
        
        well = manager.get_well(request.wellName)
        if not well:
            raise HTTPException(
                status_code=404,
                detail=f"Well '{request.wellName}' not found in session"
            )
        
        if request.action == "mark_modified":
            manager.mark_modified(request.wellName)
            message = f"Well '{request.wellName}' marked as modified"
            
        elif request.action == "update_property":
            if not request.data or 'property_name' not in request.data:
                raise HTTPException(
                    status_code=400,
                    detail="property_name required in data"
                )
            property_name = request.data['property_name']
            value = request.data.get('value')
            manager.update_well_property(request.wellName, property_name, value)
            message = f"Updated {property_name} for well '{request.wellName}'"
            
        elif request.action == "add_dataset":
            if not request.data:
                raise HTTPException(status_code=400, detail="Dataset data required")
            
            dataset = Dataset.from_dict(request.data)
            manager.add_dataset_to_well(request.wellName, dataset)
            message = f"Added dataset to well '{request.wellName}'"
            
        elif request.action == "remove_dataset":
            if not request.data or 'dataset_name' not in request.data:
                raise HTTPException(
                    status_code=400,
                    detail="dataset_name required in data"
                )
            dataset_name = request.data['dataset_name']
            manager.remove_dataset_from_well(request.wellName, dataset_name)
            message = f"Removed dataset '{dataset_name}' from well '{request.wellName}'"
            
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported action: {request.action}"
            )
        
        updated_session_data = manager.get_session_well_data()
        updated_metadata = manager.get_metadata()
        cache_service.store_session(session_id, updated_session_data, updated_metadata)
        
        return {
            "success": True,
            "message": message,
            "wellName": request.wellName
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{session_id}/commit", response_model=SessionCommitResponse)
async def commit_session(session_id: str, project_path: Optional[str] = None):
    """
    Commit the session: save all modified wells to .ptrc files and delete session from JSON storage.
    """
    try:
        full_session = cache_service.load_session(session_id)
        if not full_session:
            raise HTTPException(status_code=404, detail="Session not found or expired")
        
        wells_data = full_session.get("wells", {})
        metadata = full_session.get("metadata", {})
        
        stored_project_path = metadata.get("project_path")
        if project_path:
            resolved_project_path = os.path.abspath(project_path)
        elif stored_project_path:
            resolved_project_path = os.path.abspath(stored_project_path)
        else:
            raise HTTPException(
                status_code=400,
                detail="project_path required (not found in session metadata)"
            )
        
        if not validate_path(resolved_project_path):
            raise HTTPException(
                status_code=403,
                detail="Access denied: path outside petrophysics-workplace"
            )
        
        manager = WellSessionManager(
            project_path=resolved_project_path,
            initial_well_data=wells_data
        )
        
        manager.restore_metadata(metadata)
        
        save_results = manager.commit_changes()
        
        cache_service.delete_session(session_id)
        
        summary = manager.get_session_summary()
        
        return {
            "success": True,
            "message": f"Session committed. Saved {len(save_results)} wells permanently.",
            "savedWells": save_results,
            "summary": summary
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{session_id}")
async def delete_session(session_id: str):
    """Delete a session from JSON storage without saving changes."""
    try:
        if not cache_service.session_exists(session_id):
            raise HTTPException(status_code=404, detail="Session not found or expired")
        
        cache_service.delete_session(session_id)
        
        return {
            "success": True,
            "message": "Session deleted without saving changes"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{session_id}/wells")
async def get_session_wells(session_id: str):
    """Get all wells in the session with their current state."""
    try:
        full_session = cache_service.load_session(session_id)
        if not full_session:
            raise HTTPException(status_code=404, detail="Session not found or expired")
        
        wells_data = full_session.get("wells", {})
        metadata = full_session.get("metadata", {})
        
        well_summaries = []
        modified_wells = set(metadata.get("modified_wells", []))
        
        for well_name, well_dict in wells_data.items():
            datasets = well_dict.get('datasets', [])
            well_summaries.append({
                "name": well_name,
                "type": well_dict.get('well_type'),
                "created": well_dict.get('date_created'),
                "datasets_count": len(datasets),
                "datasets": [d.get('name') for d in datasets],
                "is_modified": well_name in modified_wells
            })
        
        return {
            "success": True,
            "sessionId": session_id,
            "wells": well_summaries,
            "total": len(well_summaries),
            "modified_count": len(modified_wells)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
