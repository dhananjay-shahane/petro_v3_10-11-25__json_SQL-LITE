import os
from fastapi import APIRouter, HTTPException, Request
from models import SessionProjectSave, SessionProjectResponse
from dependencies import validate_path


router = APIRouter(prefix="/session", tags=["sessions"])


@router.post("/project", response_model=SessionProjectResponse)
async def save_project_session(data: SessionProjectSave, request: Request):
    """Save current project path to session"""
    try:
        project_path = data.projectPath
        project_name = data.projectName
        created_at = data.createdAt
        
        if not project_path:
            raise HTTPException(status_code=400, detail="Project path is required")
        
        resolved_path = os.path.abspath(project_path)
        if not validate_path(resolved_path):
            raise HTTPException(
                status_code=403,
                detail="Access denied: path outside petrophysics-workplace"
            )
        
        request.session['project_path'] = project_path
        request.session['project_name'] = project_name
        request.session['created_at'] = created_at
        
        return {
            "success": True,
            "message": "Project saved to session",
            "projectPath": project_path,
            "projectName": project_name
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/project", response_model=SessionProjectResponse)
async def get_project_session(request: Request):
    """Get current project path from session"""
    try:
        project_path = request.session.get('project_path')
        project_name = request.session.get('project_name')
        created_at = request.session.get('created_at')
        
        if not project_path:
            return {
                "success": True,
                "hasProject": False,
                "projectPath": None,
                "projectName": None,
                "createdAt": None
            }
        
        return {
            "success": True,
            "hasProject": True,
            "projectPath": project_path,
            "projectName": project_name,
            "createdAt": created_at
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/clear", response_model=SessionProjectResponse)
async def clear_session(request: Request):
    """Clear the session"""
    try:
        request.session.clear()
        return {
            "success": True,
            "message": "Session cleared"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
