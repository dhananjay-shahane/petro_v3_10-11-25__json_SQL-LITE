import os
import uuid
from pathlib import Path
from fastapi import APIRouter, File, UploadFile, Form, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from dependencies import validate_path
from utils.zonation_utils import ZonationData

router = APIRouter(prefix="/tops", tags=["tops"])

# Define the directory for tops files within each project
TOPS_FOLDER_NAME = "05-TOPS_FOLDER"


class TopsFileInfo(BaseModel):
    filename: str
    path: str
    size: int


class TopsUploadResponse(BaseModel):
    success: bool
    message: str
    file: TopsFileInfo


class TopsListResponse(BaseModel):
    success: bool
    files: List[TopsFileInfo]
    message: str


class ZoneData(BaseModel):
    zone: str
    depth: float


class ZonesResponse(BaseModel):
    success: bool
    zones: List[str]
    message: str


class WellZonesResponse(BaseModel):
    success: bool
    zones: List[ZoneData]
    message: str


class FileSummaryResponse(BaseModel):
    success: bool
    summary: Dict[str, Any]
    message: str


@router.post("/upload", response_model=TopsUploadResponse)
async def upload_tops_file(
    file: UploadFile = File(...),
    project_path: str = Form(...)
):
    """
    Upload a tops file and store it in the project's 05-TOPS_FOLDER directory.
    """
    try:
        validate_path(project_path)
        
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")
        
        # Create tops folder in project directory
        tops_dir = Path(project_path) / TOPS_FOLDER_NAME
        tops_dir.mkdir(parents=True, exist_ok=True)
        
        # Save the file
        file_path = tops_dir / file.filename
        
        print(f"[TopsUpload] Uploading {file.filename} to {file_path}")
        
        # Write file content
        total_size = 0
        chunk_size = 1024 * 1024  # 1 MB chunks
        with open(file_path, "wb") as buffer:
            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break
                total_size += len(chunk)
                buffer.write(chunk)
        
        print(f"[TopsUpload] Successfully uploaded {file.filename} ({total_size / 1024:.2f} KB)")
        
        return {
            "success": True,
            "message": "Tops file uploaded successfully",
            "file": {
                "filename": file.filename,
                "path": str(file_path),
                "size": total_size
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"[TopsUpload] Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to upload tops file: {str(e)}")


@router.get("/list", response_model=TopsListResponse)
async def list_tops_files(project_path: str):
    """
    List all tops files in the project's 05-TOPS_FOLDER directory.
    """
    try:
        validate_path(project_path)
        
        tops_dir = Path(project_path) / TOPS_FOLDER_NAME
        
        if not tops_dir.exists():
            return {
                "success": True,
                "files": [],
                "message": "No tops folder found"
            }
        
        # List all files in the tops directory
        files = []
        for file_path in tops_dir.iterdir():
            if file_path.is_file():
                files.append({
                    "filename": file_path.name,
                    "path": str(file_path),
                    "size": file_path.stat().st_size
                })
        
        print(f"[TopsList] Found {len(files)} tops files in {tops_dir}")
        
        return {
            "success": True,
            "files": files,
            "message": f"Found {len(files)} tops files"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"[TopsList] Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to list tops files: {str(e)}")


@router.delete("/delete")
async def delete_tops_file(project_path: str, filename: str):
    """
    Delete a tops file from the project's 05-TOPS_FOLDER directory.
    """
    try:
        validate_path(project_path)
        
        tops_dir = Path(project_path) / TOPS_FOLDER_NAME
        file_path = tops_dir / filename
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Tops file not found")
        
        # Ensure the file is within the tops directory (security check)
        if not str(file_path.resolve()).startswith(str(tops_dir.resolve())):
            raise HTTPException(status_code=403, detail="Invalid file path")
        
        file_path.unlink()
        
        print(f"[TopsDelete] Deleted {filename} from {tops_dir}")
        
        return {
            "success": True,
            "message": f"Tops file {filename} deleted successfully"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"[TopsDelete] Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete tops file: {str(e)}")


@router.get("/zones", response_model=ZonesResponse)
async def get_unique_zones(project_path: str, filename: str):
    """
    Get list of unique zones from a tops file.
    
    Args:
        project_path: Path to the project
        filename: Name of the tops file
        
    Returns:
        List of unique zone names
    """
    try:
        validate_path(project_path)
        
        tops_dir = Path(project_path) / TOPS_FOLDER_NAME
        file_path = tops_dir / filename
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Tops file not found")
        
        # Get unique zones
        zones = ZonationData.get_unique_zones(str(file_path))
        
        print(f"[TopsZones] Found {len(zones)} unique zones in {filename}")
        
        return {
            "success": True,
            "zones": zones,
            "message": f"Found {len(zones)} unique zones"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"[TopsZones] Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get zones: {str(e)}")


@router.get("/zones/well", response_model=WellZonesResponse)
async def get_zones_for_well(project_path: str, filename: str, well_name: str):
    """
    Get zones for a specific well from a tops file.
    
    Args:
        project_path: Path to the project
        filename: Name of the tops file
        well_name: Name of the well
        
    Returns:
        List of zone data with depths for the specified well
    """
    try:
        validate_path(project_path)
        
        tops_dir = Path(project_path) / TOPS_FOLDER_NAME
        file_path = tops_dir / filename
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Tops file not found")
        
        # Get zones for well
        zones_data = ZonationData.get_zones_for_well(str(file_path), well_name)
        
        print(f"[TopsWellZones] Found {len(zones_data)} zones for well '{well_name}' in {filename}")
        
        return {
            "success": True,
            "zones": zones_data,
            "message": f"Found {len(zones_data)} zones for well {well_name}"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"[TopsWellZones] Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get zones for well: {str(e)}")


@router.get("/summary", response_model=FileSummaryResponse)
async def get_file_summary(project_path: str, filename: str):
    """
    Get summary information about a tops file including wells, zones, and metadata.
    
    Args:
        project_path: Path to the project
        filename: Name of the tops file
        
    Returns:
        Dictionary containing file summary information
    """
    try:
        validate_path(project_path)
        
        tops_dir = Path(project_path) / TOPS_FOLDER_NAME
        file_path = tops_dir / filename
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Tops file not found")
        
        # Get file summary
        summary = ZonationData.get_file_summary(str(file_path))
        
        print(f"[TopsSummary] Retrieved summary for {filename}: {summary.get('well_count', 0)} wells, {summary.get('zone_count', 0)} zones")
        
        return {
            "success": True,
            "summary": summary,
            "message": "File summary retrieved successfully"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"[TopsSummary] Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get file summary: {str(e)}")
