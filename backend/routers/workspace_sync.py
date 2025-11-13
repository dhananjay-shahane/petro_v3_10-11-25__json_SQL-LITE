import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse
from typing import Optional

router = APIRouter()

WORKSPACE_ROOT = Path("/home/runner/workspace/petrophysics-workplace")


def validate_path(path: Path) -> bool:
    """Ensure path is within workspace root"""
    try:
        resolved = path.resolve()
        workspace_resolved = WORKSPACE_ROOT.resolve()
        return str(resolved).startswith(str(workspace_resolved))
    except Exception:
        return False


@router.get("/workspace/download")
async def download_workspace(project_name: Optional[str] = None):
    """
    Download workspace folder or specific project as a zip file.
    
    Args:
        project_name: Optional project name. If provided, downloads only that project.
                     If not provided, downloads entire workspace.
    """
    try:
        if project_name:
            # Download specific project
            project_path = WORKSPACE_ROOT / project_name
            if not project_path.exists():
                raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found")
            
            if not validate_path(project_path):
                raise HTTPException(status_code=403, detail="Access denied")
            
            source_path = project_path
            zip_filename = f"{project_name}.zip"
        else:
            # Download entire workspace
            if not WORKSPACE_ROOT.exists():
                raise HTTPException(status_code=404, detail="Workspace folder not found")
            
            source_path = WORKSPACE_ROOT
            zip_filename = "petrophysics-workplace.zip"
        
        # Create temporary zip file
        temp_dir = tempfile.mkdtemp()
        zip_path = Path(temp_dir) / zip_filename
        
        print(f"[WorkspaceSync] Creating zip archive: {zip_path}")
        
        # Create zip file
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(source_path):
                # Skip hidden directories and temp files
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                
                for file in files:
                    if file.startswith('.') or file.endswith('.tmp'):
                        continue
                    
                    file_path = Path(root) / file
                    # Calculate relative path for archive
                    if project_name:
                        arcname = str(file_path.relative_to(project_path.parent))
                    else:
                        arcname = str(file_path.relative_to(WORKSPACE_ROOT.parent))
                    
                    zipf.write(file_path, arcname)
        
        print(f"[WorkspaceSync] Zip created successfully, size: {zip_path.stat().st_size} bytes")
        
        # Return zip file and clean up after sending
        return FileResponse(
            path=str(zip_path),
            media_type='application/zip',
            filename=zip_filename,
            background=None  # Don't delete immediately, cleanup will happen later
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[WorkspaceSync] Error creating zip: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create zip archive: {str(e)}")


@router.post("/workspace/upload")
async def upload_workspace(
    file: UploadFile = File(...),
    overwrite: bool = False
):
    """
    Upload and extract a workspace zip file.
    
    Args:
        file: The zip file to upload
        overwrite: If True, overwrites existing files. If False, raises error if conflicts exist.
    """
    try:
        if not file.filename or not file.filename.endswith('.zip'):
            raise HTTPException(status_code=400, detail="Only .zip files are allowed")
        
        # Create temporary directory for extraction
        temp_dir = tempfile.mkdtemp()
        zip_path = Path(temp_dir) / file.filename
        
        # Save uploaded zip
        with open(zip_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        print(f"[WorkspaceSync] Uploaded zip file: {zip_path}")
        
        # Extract zip to temporary location first
        extract_dir = Path(temp_dir) / "extracted"
        extract_dir.mkdir(exist_ok=True)
        
        with zipfile.ZipFile(zip_path, 'r') as zipf:
            zipf.extractall(extract_dir)
        
        # Find the workspace folder in extracted content
        # It could be at root or nested
        workspace_folder = None
        for item in extract_dir.iterdir():
            if item.name == "petrophysics-workplace":
                workspace_folder = item
                break
        
        if not workspace_folder:
            # Check if we're directly in a project folder
            # Look for typical project structure (10-WELLS folder)
            has_wells_folder = any(
                (extract_dir / item).is_dir() and "WELLS" in item.upper()
                for item in os.listdir(extract_dir)
            )
            
            if has_wells_folder:
                # This is a project folder, extract it as a project
                project_name = file.filename.replace('.zip', '')
                target_path = WORKSPACE_ROOT / project_name
                
                if target_path.exists() and not overwrite:
                    raise HTTPException(
                        status_code=409,
                        detail=f"Project '{project_name}' already exists. Set overwrite=true to replace."
                    )
                
                # Copy project folder
                if target_path.exists():
                    shutil.rmtree(target_path)
                shutil.copytree(extract_dir, target_path)
                
                # Cleanup
                shutil.rmtree(temp_dir)
                
                return JSONResponse({
                    "success": True,
                    "message": f"Project '{project_name}' uploaded successfully",
                    "type": "project"
                })
        
        if not workspace_folder:
            raise HTTPException(
                status_code=400,
                detail="Invalid workspace zip file. Could not find 'petrophysics-workplace' folder or valid project structure."
            )
        
        # Check for conflicts
        conflicts = []
        for item in workspace_folder.iterdir():
            target = WORKSPACE_ROOT / item.name
            if target.exists():
                conflicts.append(item.name)
        
        if conflicts and not overwrite:
            raise HTTPException(
                status_code=409,
                detail=f"Conflicts detected: {', '.join(conflicts)}. Set overwrite=true to replace."
            )
        
        # Copy workspace contents
        for item in workspace_folder.iterdir():
            target = WORKSPACE_ROOT / item.name
            
            if target.exists():
                if target.is_dir():
                    shutil.rmtree(target)
                else:
                    target.unlink()
            
            if item.is_dir():
                shutil.copytree(item, target)
            else:
                shutil.copy2(item, target)
        
        # Cleanup
        shutil.rmtree(temp_dir)
        
        print(f"[WorkspaceSync] Workspace uploaded and extracted successfully")
        
        return JSONResponse({
            "success": True,
            "message": "Workspace uploaded successfully",
            "type": "workspace"
        })
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[WorkspaceSync] Error uploading workspace: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to upload workspace: {str(e)}")
    finally:
        await file.close()


@router.get("/workspace/projects")
async def list_projects():
    """List all projects in the workspace"""
    try:
        if not WORKSPACE_ROOT.exists():
            return JSONResponse({"projects": []})
        
        projects = []
        for item in WORKSPACE_ROOT.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                # Check if it has a WELLS folder (typical project structure)
                has_wells = any(
                    (item / subitem).is_dir() and "WELLS" in subitem.upper()
                    for subitem in os.listdir(item)
                    if (item / subitem).is_dir()
                )
                
                if has_wells:
                    projects.append({
                        "name": item.name,
                        "path": str(item),
                        "size": sum(f.stat().st_size for f in item.rglob('*') if f.is_file())
                    })
        
        return JSONResponse({"projects": projects})
        
    except Exception as e:
        print(f"[WorkspaceSync] Error listing projects: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
