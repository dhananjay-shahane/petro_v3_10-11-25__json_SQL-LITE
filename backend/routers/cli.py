"""
CLI API endpoints for executing commands.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Any, List
import json

from utils.cli_service import cli_service
from dependencies import validate_path
# JSON storage client removed - using JSON storage instead
import os


router = APIRouter(prefix="/cli", tags=["cli"])


class CLIExecuteRequest(BaseModel):
    command: str
    projectPath: str
    currentWell: Optional[str] = None
    deletePermissionEnabled: Optional[bool] = False


class CLIExecuteResponse(BaseModel):
    success: bool
    message: str
    result: Optional[Any] = None
    command: str


class CLIHelpRequest(BaseModel):
    command: Optional[str] = None


class CLIHelpResponse(BaseModel):
    success: bool
    help: Optional[dict] = None
    message: Optional[str] = None


@router.post("/execute", response_model=CLIExecuteResponse)
async def execute_command(request: CLIExecuteRequest):
    """
    Execute a CLI command.
    
    Example commands:
    - INSERT_CONSTANT well1 API_GRAVITY 45.2 API 'Oil gravity'
    - INSERT_LOG well1 GAMMA_RAY API 'Gamma ray log'
    - CREATE_EMPTY_WELL well2 Dev
    - DELETE_DATASET well1 OLD_LOG
    - IMPORT_LAS_FILE well1 path/to/file.las 1
    - IMPORT_LAS_FILES_FROM_FOLDER well1 path/to/folder
    - LOAD_MULTIPLE_DATASETS well1 path/to/folder
    """
    try:
        # Handle path normalization - convert any path to server format
        raw_path = request.projectPath
        
        # Normalize the path to Unix format and make it absolute
        project_path = os.path.abspath(raw_path.replace('\\', '/'))
        
        if not validate_path(project_path):
            raise HTTPException(
                status_code=403,
                detail=f"Access denied: path outside petrophysics-workplace. Received: {raw_path}"
            )
        
        if not os.path.exists(project_path):
            raise HTTPException(status_code=404, detail=f"Project path does not exist: {project_path}")
        
        context = {
            'project_path': project_path,
            'current_well': request.currentWell,
            'delete_permission_enabled': request.deletePermissionEnabled
        }
        
        success, message, result = cli_service.execute(request.command, context)
        
        return {
            'success': success,
            'message': message,
            'result': result,
            'command': request.command
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/help", response_model=CLIHelpResponse)
async def get_help(request: CLIHelpRequest):
    """Get help text for CLI commands."""
    try:
        if not request.command:
            return {
                'success': False,
                'message': 'No command specified'
            }
        
        cmd_name = request.command.upper()
        cmd = cli_service.commands.get(cmd_name)
        
        if not cmd:
            return {
                'success': False,
                'message': f'Unknown command: {request.command}'
            }
        
        # Parse description to extract usage and create structured help
        description_text = cmd.description
        
        # Extract usage from description (format: "Description. Usage: <usage>")
        if "Usage:" in description_text:
            parts = description_text.split("Usage:", 1)
            desc = parts[0].strip()
            syntax = parts[1].strip() if len(parts) > 1 else description_text
        else:
            desc = description_text
            syntax = cmd_name
        
        # Create example based on command type
        examples = {
            'INSERT_CONSTANT': 'INSERT_CONSTANT MyWell API_GRAVITY 45.2 API "Oil gravity"',
            'INSERT_LOG': 'INSERT_LOG MyWell GAMMA_RAY "Gamma ray log" float',
            'CREATE_EMPTY_WELL': 'CREATE_EMPTY_WELL MyWell Dev',
            'DELETE_DATASET': 'DELETE_DATASET MyWell MANUAL_DATA',
            'IMPORT_LAS_FILE': 'IMPORT_LAS_FILE MyWell 02-INPUT_LAS_FOLDER/data.las 1',
            'IMPORT_LAS_FILES_FROM_FOLDER': 'IMPORT_LAS_FILES_FROM_FOLDER MyWell 02-INPUT_LAS_FOLDER',
            'LOAD_MULTIPLE_DATASETS': 'LOAD_MULTIPLE_DATASETS MyWell 02-INPUT_LAS_FOLDER',
            'LOAD_TOPS': 'LOAD_TOPS MyWell 03-INPUT_TOPS/tops.csv',
            'EXPORT_TOPS': 'EXPORT_TOPS MyWell 04-OUTPUT/tops.csv',
            'EXPORT_TO_LAS': 'EXPORT_TO_LAS MyWell MAIN 04-OUTPUT/main.las',
        }
        
        example = examples.get(cmd_name, syntax)
        
        return {
            'success': True,
            'help': {
                'command': cmd_name,
                'description': desc,
                'syntax': syntax,
                'example': example
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/commands")
async def list_commands():
    """List all available CLI commands."""
    try:
        commands = []
        for cmd_name, cmd in cli_service.commands.items():
            commands.append({
                'name': cmd_name,
                'description': cmd.description
            })
        
        return {
            'success': True,
            'commands': commands
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/selected-wells/{project_name}")
async def get_selected_wells(project_name: str):
    """Get the selected wells for a project from storage."""
    try:
        from dependencies import WORKSPACE_ROOT
        from utils.sqlite_storage import SQLiteStorageService
        cache_service = SQLiteStorageService()
        
        project_path = os.path.join(WORKSPACE_ROOT, project_name)
        
        selected_wells = cache_service.load_selected_wells(project_path)
        
        if selected_wells:
            return {
                'success': True,
                'selected_wells': selected_wells,
                'project_path': project_path
            }
        else:
            return {
                'success': True,
                'selected_wells': [],
                'message': 'No well selection saved for this project'
            }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/active-well/{project_name}")
async def get_active_well(project_name: str):
    """Get the active well from storage for a project."""
    try:
        from dependencies import WORKSPACE_ROOT
        from utils.sqlite_storage import SQLiteStorageService
        cache_service = SQLiteStorageService()
        
        project_path = os.path.join(WORKSPACE_ROOT, project_name)
        
        active_well = cache_service.load_active_well(project_path)
        
        if active_well:
            return {
                'success': True,
                'active_well': active_well,
                'project_path': project_path
            }
        else:
            return {
                'success': True,
                'active_well': None
            }
        
    except Exception as e:
        print(f"[CLI API] Error getting active well: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class CLIHistorySaveRequest(BaseModel):
    projectPath: str
    commandHistory: str


class CLIHistoryResponse(BaseModel):
    success: bool
    message: str
    commandHistory: Optional[str] = None


@router.post("/history/save", response_model=CLIHistoryResponse)
async def save_cli_history(request: CLIHistorySaveRequest):
    """Save CLI command history to storage for a project."""
    try:
        from utils.sqlite_storage import SQLiteStorageService
        cache_service = SQLiteStorageService()
        
        # Normalize the path
        project_path = os.path.abspath(request.projectPath.replace('\\', '/'))
        
        if not validate_path(project_path):
            raise HTTPException(
                status_code=403,
                detail="Access denied: path outside petrophysics-workplace"
            )
        
        # Store history using cache service with safe key
        cache_service.save_cli_history(project_path, request.commandHistory)
        
        return {
            'success': True,
            'message': 'CLI history saved successfully'
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/load")
async def load_cli_history(projectPath: str):
    """Load CLI command history from storage for a project."""
    try:
        from utils.sqlite_storage import SQLiteStorageService
        cache_service = SQLiteStorageService()
        
        # Normalize the path
        project_path = os.path.abspath(projectPath.replace('\\', '/'))
        
        if not validate_path(project_path):
            raise HTTPException(
                status_code=403,
                detail="Access denied: path outside petrophysics-workplace"
            )
        
        # Retrieve history using cache service with safe key
        command_history = cache_service.load_cli_history(project_path) or ''
        
        return {
            'success': True,
            'commandHistory': command_history if command_history else '',
            'message': 'CLI history loaded successfully' if command_history else 'No history found'
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
