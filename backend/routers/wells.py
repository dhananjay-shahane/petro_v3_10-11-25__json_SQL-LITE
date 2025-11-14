import os
import tempfile
import traceback
import shutil
import lasio
import hashlib
import json
import time
import asyncio
from pathlib import Path
from datetime import datetime
from uuid import uuid4
from typing import List
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from werkzeug.utils import secure_filename

from models import (
    LASPreviewRequest, LASPreviewResponse, WellCreateResponse,
    WellLoadResponse, WellDataResponse, DatasetDetailsResponse,
    WellListResponse, WellDatasetsResponse, LogPlotRequest,
    LogPlotResponse, CrossPlotRequest, CrossPlotResponse, LogMessage,
    LASBatchPreviewItem, LASBatchPreviewResponse, LASBatchImportRequest,
    LASBatchImportFileResult, LASBatchImportSummary, LASBatchImportResponse
)
from dependencies import (
    WORKSPACE_ROOT, validate_path, allowed_file, sanitize_list
)
from utils.fe_data_objects import Well, Dataset, Constant
from utils.LogPlot import LogPlotManager
from utils.CPI import CrossPlotManager
from utils.cpi_plotly import CPIPlotlyManager
from utils.matplotlib_cpi_plot import MatplotlibCPIPlotter
from utils.file_well_storage import get_file_well_storage, CACHE_LOCK
from utils.sqlite_storage import SQLiteStorageService
from utils.data_import_export import ImportLasFileCommand

# Keep SQLite for non-well data (sessions, projects, etc.)
session_storage = SQLiteStorageService()


router = APIRouter(prefix="/wells", tags=["wells"])


def get_project_session_id(project_path: str) -> str:
    """Generate a consistent session ID for a project path"""
    normalized_path = os.path.normpath(project_path)
    hash_object = hashlib.md5(normalized_path.encode())
    return f"project_{hash_object.hexdigest()}"


def store_well_in_session(well_path: str, well_data: dict):
    """Store well data in session metadata (not in SQLite - wells use file storage)"""
    try:
        project_path = os.path.dirname(os.path.dirname(well_path))
        session_id = get_project_session_id(project_path)
        well_name = os.path.basename(well_path).replace('.ptrc', '')
        
        # Use session_storage for session metadata (not well data)
        existing_session = session_storage.load_session(session_id)
        
        if existing_session:
            wells = existing_session.get("wells", {})
            metadata = existing_session.get("metadata", {})
        else:
            wells = {}
            metadata = {
                "project_path": project_path,
                "project_name": os.path.basename(project_path),
                "modified_wells": []
            }
        
        wells[well_name] = well_data
        
        session_storage.store_session(session_id, wells, metadata)
        print(f"[Storage] Stored well metadata in session {session_id}")
        
        return session_id
    except Exception as e:
        print(f"[Storage] Error storing well in session: {e}")
        return None


async def fetch_well_data(project_path: str, well_id: str):
    """
    Fetch well data from cache ONLY - no disk access.
    Returns tuple of (Well object, well_data dict, source)
    
    This helper ensures all endpoints use consistent data retrieval logic.
    Source will be: "memory-preload", "memory-lazy", or "memory-saved"
    
    NOTE: This function ONLY serves data from cache. There is NO disk fallback.
    If data is not cached, an HTTP 404 exception is raised.
    """
    # Get the file-based storage service
    storage = get_file_well_storage()
    
    # Get data from cache only (NO disk access)
    well_data = await asyncio.to_thread(storage.get_cached_well_data, project_path, well_id)
    
    if well_data:
        # Data was served from cache (memory)
        file_key = storage.get_file_key(project_path, well_id)
        with CACHE_LOCK:
            cache_entry = storage.cache.get(file_key, {})
            source = cache_entry.get("source", "unknown")
        print(f"[WellFetch] Served well '{well_id}' from memory ({source})")
        
        # Reconstruct Well object from data (non-blocking)
        well = await asyncio.to_thread(Well.from_dict, well_data)
        return well, well_data, f"memory-{source}"
    
    # Well not found in cache - raise 404
    print(f"[WellFetch] ERROR: Well '{well_id}' not found in cache for project '{project_path}'")
    raise HTTPException(
        status_code=404, 
        detail=f"Well '{well_id}' not found in cache. The well may not be preloaded. Try switching to a different project."
    )


def get_batch_session_dir(session_id: str) -> Path:
    """Get the temp directory for a batch session"""
    batch_root = Path(WORKSPACE_ROOT) / ".tmp" / "las-batch"
    session_dir = batch_root / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir


def save_batch_metadata(session_id: str, metadata: dict):
    """Save metadata for a batch session"""
    session_dir = get_batch_session_dir(session_id)
    metadata_file = session_dir / "metadata.json"
    with open(metadata_file, 'w') as f:
        json.dump(metadata, f)


def load_batch_metadata(session_id: str) -> dict:
    """Load metadata for a batch session"""
    session_dir = get_batch_session_dir(session_id)
    metadata_file = session_dir / "metadata.json"
    if metadata_file.exists():
        with open(metadata_file, 'r') as f:
            return json.load(f)
    return {}


def cleanup_old_batch_sessions(ttl_hours: int = 1):
    """Remove batch session directories older than TTL"""
    batch_root = Path(WORKSPACE_ROOT) / ".tmp" / "las-batch"
    if not batch_root.exists():
        return
    
    now = time.time()
    ttl_seconds = ttl_hours * 3600
    
    for session_dir in batch_root.iterdir():
        if session_dir.is_dir():
            dir_age = now - session_dir.stat().st_mtime
            if dir_age > ttl_seconds:
                try:
                    shutil.rmtree(session_dir)
                    print(f"[Cleanup] Removed old batch session: {session_dir.name}")
                except Exception as e:
                    print(f"[Cleanup] Failed to remove {session_dir.name}: {e}")


@router.post("/preview-las", response_model=LASPreviewResponse)
async def preview_las(data: LASPreviewRequest):
    """Preview LAS file content without saving"""
    try:
        las_content = data.lasContent
        filename = data.filename
        
        if not las_content:
            raise HTTPException(status_code=400, detail="LAS content is required")
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.las', delete=False) as tmp_file:
            tmp_file.write(las_content)
            tmp_path = tmp_file.name
        
        try:
            las = lasio.read(tmp_path)
            
            well_name = None
            
            try:
                if hasattr(las.well, 'WELL'):
                    well_obj = las.well.WELL
                    if well_obj and well_obj.value:
                        well_name = str(well_obj.value).strip()
            except:
                pass
            
            if not well_name:
                for item in las.well:
                    if item.mnemonic.upper() == 'WELL' and item.value:
                        well_name = str(item.value).strip()
                        break
            
            if not well_name:
                well_name = Path(filename).stem if filename and filename != 'UNKNOWN' else 'UNKNOWN'
            
            uwi = ""
            try:
                if hasattr(las.well, 'UWI'):
                    uwi_obj = las.well.UWI
                    if uwi_obj and uwi_obj.value:
                        uwi = str(uwi_obj.value).strip()
            except:
                pass
            
            preview_info = {
                "wellName": well_name,
                "uwi": uwi,
                "company": str(las.well.COMP.value).strip() if hasattr(las.well, 'COMP') and las.well.COMP and las.well.COMP.value else "",
                "field": str(las.well.FLD.value).strip() if hasattr(las.well, 'FLD') and las.well.FLD and las.well.FLD.value else "",
                "location": str(las.well.LOC.value).strip() if hasattr(las.well, 'LOC') and las.well.LOC and las.well.LOC.value else "",
                "startDepth": float(las.well.STRT.value) if hasattr(las.well, 'STRT') and las.well.STRT and las.well.STRT.value is not None else None,
                "stopDepth": float(las.well.STOP.value) if hasattr(las.well, 'STOP') and las.well.STOP and las.well.STOP.value is not None else None,
                "step": float(las.well.STEP.value) if hasattr(las.well, 'STEP') and las.well.STEP and las.well.STEP.value is not None else None,
                "curveNames": [curve.mnemonic for curve in las.curves],
                "dataPoints": len(las.data) if las.data is not None else 0
            }
            
            return preview_info
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/create-from-las", response_model=WellCreateResponse, status_code=201)
async def create_from_las(
    lasFile: UploadFile = File(...),
    projectPath: str = Form(...),
    setName: str = Form(None),
    datasetType: str = Form("CONTINUOUS")
):
    """Upload LAS file and create well in project"""
    logs = []
    try:
        logs.append({"message": "Starting LAS file upload...", "type": "info"})
        
        if not projectPath:
            raise HTTPException(status_code=400, detail="Project path is required")
        
        if not lasFile.filename:
            raise HTTPException(status_code=400, detail="No file selected")
        
        logs.append({"message": f"File selected: {lasFile.filename}", "type": "info"})
        
        if not allowed_file(lasFile.filename):
            logs.append({"message": "ERROR: Invalid file type. Only .las files are allowed", "type": "error"})
            raise HTTPException(
                status_code=400,
                detail="Invalid file type. Only .las files are allowed"
            )
        
        resolved_project_path = os.path.abspath(projectPath)
        if not validate_path(resolved_project_path):
            logs.append({"message": "ERROR: Access denied - path outside workspace", "type": "error"})
            raise HTTPException(
                status_code=403,
                detail="Access denied: path outside petrophysics-workplace"
            )
        
        if not os.path.exists(resolved_project_path):
            logs.append({"message": "ERROR: Project path does not exist", "type": "error"})
            raise HTTPException(status_code=404, detail="Project path does not exist")
        
        filename = secure_filename(lasFile.filename)
        logs.append({"message": f"Saving file as: {filename}", "type": "info"})
        
        # Validate file size while reading (500 MB limit)
        MAX_FILE_SIZE = 500 * 1024 * 1024
        total_size = 0
        tmp_las_path = None
        
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.las', delete=False) as tmp_file:
            tmp_las_path = tmp_file.name
            # Read file in chunks to validate size without loading all into memory
            chunk_size = 1024 * 1024  # 1 MB chunks
            while True:
                chunk = await lasFile.read(chunk_size)
                if not chunk:
                    break
                total_size += len(chunk)
                if total_size > MAX_FILE_SIZE:
                    logs.append({"message": f"ERROR: File too large. Maximum size is {MAX_FILE_SIZE // (1024 * 1024)} MB", "type": "error"})
                    # Clean up partial file immediately before raising
                    tmp_file.close()
                    if tmp_las_path and os.path.exists(tmp_las_path):
                        os.unlink(tmp_las_path)
                        tmp_las_path = None  # Prevent double cleanup in finally block
                    raise HTTPException(
                        status_code=413,
                        detail=f"File too large. Maximum upload size is {MAX_FILE_SIZE // (1024 * 1024)} MB"
                    )
                tmp_file.write(chunk)
        
        try:
            logs.append({"message": "Parsing LAS file...", "type": "info"})
            
            las = lasio.read(tmp_las_path)
            
            well_name = None
            
            try:
                if hasattr(las.well, 'WELL'):
                    well_obj = las.well.WELL
                    if well_obj and well_obj.value:
                        well_name = str(well_obj.value).strip()
            except:
                pass
            
            if not well_name:
                for item in las.well:
                    if item.mnemonic.upper() == 'WELL' and item.value:
                        well_name = str(item.value).strip()
                        break
            
            if not well_name:
                well_name = Path(filename).stem
            
            logs.append({"message": f"Extracted well name: {well_name}", "type": "info"})
            
            # Determine dataset name: custom setName > LAS SET parameter > default "MAIN"
            dataset_name = 'MAIN'
            if setName and setName.strip():
                dataset_name = setName.strip()
                logs.append({"message": f"Using custom dataset name: {dataset_name}", "type": "info"})
            else:
                try:
                    if hasattr(las.params, 'SET') and las.params.SET.value:
                        dataset_name = str(las.params.SET.value).strip()
                        logs.append({"message": f"Using SET parameter from LAS file: {dataset_name}", "type": "info"})
                except:
                    pass
            
            logs.append({"message": f"Dataset name: {dataset_name}", "type": "info"})
            
            # Normalize dataset type
            dataset_type_normalized = 'Cont' if datasetType.upper() == 'CONTINUOUS' else 'Point'
            logs.append({"message": f"Dataset type: {datasetType} (normalized to {dataset_type_normalized})", "type": "info"})
            
            top = las.well.STRT.value
            bottom = las.well.STOP.value
            
            dataset = Dataset.from_las(
                filename=tmp_las_path,
                dataset_name=dataset_name,
                dataset_type=dataset_type_normalized,
                well_name=well_name
            )
            
            logs.append({"message": "LAS file parsed successfully", "type": "success"})
            logs.append({"message": f"Found {len(dataset.well_logs)} log curves", "type": "info"})
            
            wells_folder = os.path.join(resolved_project_path, '10-WELLS')
            os.makedirs(wells_folder, exist_ok=True)
            
            well_file_path = os.path.join(wells_folder, f'{well_name}.ptrc')
            
            if os.path.exists(well_file_path):
                logs.append({"message": f"Well \"{well_name}\" already exists, checking for duplicates...", "type": "info"})
                
                # Use cache-only fetch to load existing well
                storage = get_file_well_storage()
                well_data = storage.get_cached_well_data(resolved_project_path, well_name)
                if not well_data:
                    raise HTTPException(
                        status_code=500, 
                        detail=f"Well '{well_name}' exists on disk but not loaded in cache. Please reload the project."
                    )
                well = Well.from_dict(well_data)
                
                # Implement versioning: if dataset name exists, auto-increment (MAIN, MAIN_1, MAIN_2, etc.)
                existing_dataset_names = [dtst.name for dtst in well.datasets]
                original_dataset_name = dataset_name
                if dataset_name in existing_dataset_names:
                    logs.append({"message": f"Dataset \"{dataset_name}\" already exists, applying versioning...", "type": "info"})
                    version = 1
                    while f"{original_dataset_name}_{version}" in existing_dataset_names:
                        version += 1
                    dataset_name = f"{original_dataset_name}_{version}"
                    dataset.name = dataset_name
                    logs.append({"message": f"Versioned dataset name: {dataset_name}", "type": "info"})
                
                well.datasets.append(dataset)
                logs.append({"message": f"Dataset \"{dataset_name}\" appended to existing well", "type": "success"})
            else:
                logs.append({"message": f"Creating new well \"{well_name}\"...", "type": "info"})
                well = Well(
                    date_created=datetime.now(),
                    well_name=well_name,
                    well_type='Dev'
                )
                
                ref = Dataset.reference(
                    top=0,
                    bottom=bottom,
                    dataset_name='REFERENCE',
                    dataset_type='REFERENCE',
                    well_name=well_name
                )
                
                wh = Dataset.well_header(
                    dataset_name='WELL_HEADER',
                    dataset_type='WELL_HEADER',
                    well_name=well_name
                )
                const = Constant(name='WELL_NAME', value=well.well_name, tag=well.well_name)
                wh.constants.append(const)
                
                well.datasets.append(ref)
                well.datasets.append(wh)
                well.datasets.append(dataset)
                
                logs.append({"message": "New well created with REFERENCE and WELL_HEADER datasets", "type": "success"})
            
            logs.append({"message": "Saving well to project...", "type": "info"})
            
            # Save to file-based storage (updates BOTH disk and cache atomically)
            well_data = well.to_dict()
            storage = get_file_well_storage()
            if storage.save_well_data(well_data, resolved_project_path):
                logs.append({"message": "Well saved to file storage and cache updated", "type": "success"})
                store_well_in_session(well_file_path, well_data)
                logs.append({"message": "Project marked as modified", "type": "success"})
            else:
                logs.append({"message": "ERROR: Failed to save well", "type": "error"})
                raise HTTPException(status_code=500, detail="Failed to save well data")
            
            logs.append({"message": f"SUCCESS: Well saved to: {well_file_path}", "type": "success"})
            
            las_folder = os.path.join(resolved_project_path, '02-INPUT_LAS_FOLDER')
            os.makedirs(las_folder, exist_ok=True)
            las_destination = os.path.join(las_folder, filename)
            shutil.copy2(tmp_las_path, las_destination)
            
            logs.append({"message": f"SUCCESS: LAS file copied to: {las_destination}", "type": "success"})
            logs.append({"message": f"Well \"{well_name}\" created successfully!", "type": "success"})
            
            return {
                "success": True,
                "message": f"Well \"{well_name}\" created successfully",
                "well": {
                    "id": well_name,
                    "name": well_name,
                    "type": well.well_type
                },
                "filePath": well_file_path,
                "lasFilePath": las_destination,
                "logs": logs
            }
            
        finally:
            if tmp_las_path and os.path.exists(tmp_las_path):
                os.unlink(tmp_las_path)
                
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        logs.append({"message": f"ERROR: {str(e)}", "type": "error"})
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/preview-las-batch", response_model=LASBatchPreviewResponse)
async def preview_las_batch(
    projectPath: str = Form(...),
    files: List[UploadFile] = File(...)
):
    """Preview multiple LAS files before importing"""
    cleanup_old_batch_sessions()
    
    if not projectPath:
        raise HTTPException(status_code=400, detail="Project path is required")
    
    resolved_project_path = os.path.abspath(projectPath)
    if not validate_path(resolved_project_path):
        raise HTTPException(status_code=403, detail="Access denied: path outside workspace")
    
    if not os.path.exists(resolved_project_path):
        raise HTTPException(status_code=404, detail="Project path does not exist")
    
    session_id = get_project_session_id(projectPath)
    session_dir = get_batch_session_dir(session_id)
    
    MAX_FILE_SIZE = 500 * 1024 * 1024  # 500 MB
    MAX_FILES = 100
    
    if len(files) > MAX_FILES:
        raise HTTPException(status_code=400, detail=f"Too many files. Maximum is {MAX_FILES}")
    
    preview_items = []
    metadata = {}
    total_files = len(files)
    valid_files = 0
    duplicates = 0
    errors = 0
    
    wells_folder = os.path.join(resolved_project_path, "10-WELLS")
    os.makedirs(wells_folder, exist_ok=True)
    
    for file in files:
        item = LASBatchPreviewItem(
            filename=file.filename or "unknown.las",
            fileSize=0,
            validationErrors=[]
        )
        
        try:
            if not file.filename or not (file.filename.lower().endswith('.las')):
                item.validationErrors.append("Invalid file type. Only .las files allowed")
                errors += 1
                preview_items.append(item)
                continue
            
            filename = secure_filename(file.filename)
            temp_file_id = f"{session_id}:{uuid4()}"
            temp_file_path = session_dir / f"{uuid4()}.las"
            
            total_size = 0
            with open(temp_file_path, 'wb') as f:
                while True:
                    chunk = await file.read(1024 * 1024)
                    if not chunk:
                        break
                    total_size += len(chunk)
                    if total_size > MAX_FILE_SIZE:
                        item.validationErrors.append(f"File too large ({total_size // (1024 * 1024)} MB). Max is 500 MB")
                        errors += 1
                        temp_file_path.unlink()
                        break
                    f.write(chunk)
            
            if item.validationErrors:
                preview_items.append(item)
                continue
            
            item.fileSize = total_size
            
            try:
                las = lasio.read(str(temp_file_path))
                
                well_name = None
                for key in ['WELL', 'well', 'Well']:
                    if hasattr(las.well, key):
                        well_obj = getattr(las.well, key)
                        if well_obj and well_obj.value:
                            well_name = str(well_obj.value).strip()
                            break
                
                if not well_name:
                    for item_obj in las.well:
                        if item_obj.mnemonic.upper() == 'WELL' and item_obj.value:
                            well_name = str(item_obj.value).strip()
                            break
                
                if not well_name:
                    item.validationErrors.append("No WELL name found in LAS header")
                    errors += 1
                else:
                    item.wellName = well_name
                    
                    well_file = os.path.join(wells_folder, f"{well_name}.ptrc")
                    if os.path.exists(well_file):
                        item.isDuplicate = True
                        duplicates += 1
                    
                    company = None
                    location = None
                    for item_obj in las.well:
                        if item_obj.mnemonic.upper() in ['COMP', 'COMPANY']:
                            company = str(item_obj.value)
                        elif item_obj.mnemonic.upper() in ['LOC', 'LOCATION', 'LOCA']:
                            location = str(item_obj.value)
                    
                    item.company = company
                    item.location = location
                    
                    if hasattr(las, 'curves'):
                        item.curveNames = [c.mnemonic for c in las.curves]
                    
                    if hasattr(las, 'data') and las.data is not None:
                        item.dataPoints = len(las.data)
                    
                    if hasattr(las.well, 'START'):
                        item.startDepth = float(las.well.START.value) if las.well.START.value else None
                    if hasattr(las.well, 'STOP'):
                        item.stopDepth = float(las.well.STOP.value) if las.well.STOP.value else None
                    
                    item.tempFileId = temp_file_id
                    metadata[temp_file_id] = {
                        "filename": filename,
                        "temp_path": str(temp_file_path),
                        "well_name": well_name
                    }
                    valid_files += 1
                    
            except Exception as parse_error:
                item.validationErrors.append(f"Failed to parse LAS file: {str(parse_error)}")
                errors += 1
                if temp_file_path.exists():
                    temp_file_path.unlink()
                    
        except Exception as e:
            item.validationErrors.append(f"Error processing file: {str(e)}")
            errors += 1
        
        preview_items.append(item)
    
    save_batch_metadata(session_id, metadata)
    
    return {
        "success": True,
        "message": f"Previewed {total_files} files: {valid_files} valid, {duplicates} duplicates, {errors} errors",
        "files": preview_items,
        "totalFiles": total_files,
        "validFiles": valid_files,
        "duplicates": duplicates,
        "errors": errors
    }


@router.post("/import-las-batch", response_model=LASBatchImportResponse)
async def import_las_batch(request: LASBatchImportRequest):
    """Import multiple LAS files that were previously previewed"""
    try:
        projectPath = request.projectPath
        
        if not projectPath:
            raise HTTPException(status_code=400, detail="Project path is required")
        
        resolved_project_path = os.path.abspath(projectPath)
        if not validate_path(resolved_project_path):
            raise HTTPException(status_code=403, detail="Access denied: path outside workspace")
        
        if not os.path.exists(resolved_project_path):
            raise HTTPException(status_code=404, detail="Project path does not exist")
        
        session_id = get_project_session_id(projectPath)
        metadata = load_batch_metadata(session_id)
        
        if not metadata:
            raise HTTPException(status_code=400, detail="No preview metadata found. Please preview files first")
        
        results = []
        wells_created = set()
        wells_updated = set()
        datasets_added = 0
        failed = 0
        
        for file_ref in request.files:
            temp_file_id = file_ref.tempFileId
            file_meta = metadata.get(temp_file_id)
            
            if not file_meta:
                results.append(LASBatchImportFileResult(
                    filename=temp_file_id,
                    status="failed",
                    message="File metadata not found",
                    error="Preview data expired or not found"
                ))
                failed += 1
                continue
            
            filename = file_meta["filename"]
            temp_path = file_meta["temp_path"]
            
            if not os.path.exists(temp_path):
                results.append(LASBatchImportFileResult(
                    filename=filename,
                    status="failed",
                    message="Temp file not found",
                    error="File may have been cleaned up"
                ))
                failed += 1
                continue
            
            dataset_type_map = {
                "CONTINUOUS": "Cont",
                "POINT": "Point"
            }
            
            dataset_type = file_ref.datasetType or request.defaultDatasetType or "CONTINUOUS"
            normalized_type = dataset_type_map.get(dataset_type.upper(), "Cont")
            
            dataset_suffix = file_ref.datasetName or request.defaultDatasetSuffix or ''
            
            # Use ImportLasFileCommand from data_import_export.py
            las_import_cmd = ImportLasFileCommand()
            context = {'project_path': resolved_project_path}
            args = {
                'las_file_path': temp_path,
                'suffix': dataset_suffix
            }
            
            success, message, result = las_import_cmd.execute(args, context)
            
            if success and result:
                well_name = result.get('well_name')
                was_created = result.get('well_created', False)
                dataset_name = result.get('dataset_name', '')
                well_file_path = result.get('well_file_path')
                
                if was_created:
                    wells_created.add(well_name)
                else:
                    wells_updated.add(well_name)
                
                datasets_added += 1
                
                # Update file storage cache after the import wrote to disk
                try:
                    if well_file_path and os.path.exists(well_file_path):
                        storage = get_file_well_storage()
                        
                        # Reload the fresh well data from disk (the import just wrote it)
                        with open(well_file_path, "r", encoding="utf-8") as f:
                            well_data = json.load(f)
                        
                        # Update cache with the fresh data
                        project_name = os.path.basename(resolved_project_path)
                        file_key = f"{project_name}::{well_name}"
                        
                        # Update cache entry with fresh data from disk
                        if file_key in storage.cache:
                            storage.cache.move_to_end(file_key)
                            storage.cache[file_key]["data"] = well_data
                            print(f"[BatchImport] Updated cache entry for: {file_key}")
                        else:
                            storage.cache[file_key] = {
                                "data": well_data,
                                "source": "saved",
                                "project": project_name
                            }
                            print(f"[BatchImport] Added cache entry for: {file_key}")
                        
                        print(f"[BatchImport] Cache synchronized with disk for well: {well_name}")
                except Exception as storage_err:
                    print(f"[BatchImport] Warning: Failed to update file storage for {well_name}: {storage_err}")
                
                results.append(LASBatchImportFileResult(
                    filename=filename,
                    wellName=well_name,
                    status="created" if was_created else "updated",
                    message=message,
                    datasetName=dataset_name
                ))
                
                try:
                    if os.path.exists(temp_path):
                        os.unlink(temp_path)
                except Exception as cleanup_err:
                    print(f"Warning: Failed to cleanup temp file {temp_path}: {cleanup_err}")
                    
            else:
                results.append(LASBatchImportFileResult(
                    filename=filename,
                    status="failed",
                    message="Import failed",
                    error=message
                ))
                failed += 1
        
        summary = LASBatchImportSummary(
            totalFiles=len(request.files),
            wellsCreated=len(wells_created),
            wellsUpdated=len(wells_updated),
            datasetsAdded=datasets_added,
            failed=failed
        )
        
        success_count = len(wells_created) + len(wells_updated)
        message_parts = [
            f"Imported {success_count}/{len(request.files)} files successfully"
        ]
        if wells_created:
            message_parts.append(f"{len(wells_created)} wells created")
        if wells_updated:
            message_parts.append(f"{len(wells_updated)} wells updated")
        if failed:
            message_parts.append(f"{failed} failed")
        
        return {
            "success": success_count > 0,
            "message": ", ".join(message_parts),
            "results": results,
            "summary": summary
        }
        
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/load", response_model=WellLoadResponse)
async def load_well(filePath: str):
    """Load well data from .ptrc file"""
    try:
        if not filePath:
            raise HTTPException(status_code=400, detail="File path is required")
        
        resolved_path = os.path.abspath(filePath)
        if not validate_path(resolved_path):
            raise HTTPException(
                status_code=403,
                detail="Access denied: path outside petrophysics-workplace"
            )
        
        if not os.path.exists(resolved_path):
            raise HTTPException(status_code=404, detail="Well file not found")
        
        if not resolved_path.endswith('.ptrc'):
            raise HTTPException(
                status_code=400,
                detail="Invalid file type. Only .ptrc files are supported"
            )
        
        # Use cache-backed fetch instead of direct file read
        well_name = os.path.basename(resolved_path).replace('.ptrc', '')
        project_path = os.path.dirname(os.path.dirname(resolved_path))
        well, well_data, source = await fetch_well_data(project_path, well_name)
        
        well_data = well.to_dict()
        store_well_in_session(resolved_path, well_data)
        
        datasets = []
        for dataset in well.datasets:
            logs = []
            for log in dataset.well_logs:
                preview_values = log.log[:100] if hasattr(log, 'log') else []
                logs.append({
                    "name": log.name,
                    "date": str(log.date) if hasattr(log, 'date') else '',
                    "description": log.description if hasattr(log, 'description') else '',
                    "dataset": log.dtst if hasattr(log, 'dtst') else dataset.name,
                    "interpolation": log.interpolation if hasattr(log, 'interpolation') else '',
                    "logType": log.log_type if hasattr(log, 'log_type') else '',
                    "values": sanitize_list(preview_values)
                })
            
            constants = []
            if hasattr(dataset, 'constants') and dataset.constants:
                for const in dataset.constants:
                    constants.append({
                        "name": const.name if hasattr(const, 'name') else '',
                        "value": str(const.value) if hasattr(const, 'value') else '',
                        "tag": const.tag if hasattr(const, 'tag') else ''
                    })
            
            datasets.append({
                "name": dataset.name,
                "type": dataset.type,
                "wellname": dataset.wellname,
                "indexName": dataset.index_name if hasattr(dataset, 'index_name') else 'DEPTH',
                "logs": logs,
                "constants": constants
            })
        
        return {
            "success": True,
            "well": {
                "name": well.well_name,
                "type": well.well_type,
                "dateCreated": str(well.date_created) if hasattr(well, 'date_created') else '',
                "datasets": datasets
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/data", response_model=WellDataResponse)
async def get_well_data(wellPath: str):
    """Get complete well dataset data for data browser - prefers SQLite, falls back to disk"""
    try:
        if not wellPath:
            raise HTTPException(status_code=400, detail="Well path is required")
        
        resolved_path = os.path.abspath(wellPath)
        if not validate_path(resolved_path):
            raise HTTPException(
                status_code=403,
                detail="Access denied: path outside petrophysics-workplace"
            )
        
        well_name = os.path.basename(resolved_path).replace('.ptrc', '')
        project_path = os.path.dirname(os.path.dirname(resolved_path))
        
        # Use cache-backed fetch instead of multiple paths
        well, well_data, source = await fetch_well_data(project_path, well_name)
        
        store_well_in_session(resolved_path, well_data)
        
        datasets = []
        for dataset in well.datasets:
            logs = []
            for log in dataset.well_logs:
                logs.append({
                    "name": log.name,
                    "date": str(log.date) if hasattr(log, 'date') else '',
                    "description": log.description if hasattr(log, 'description') else '',
                    "dtst": log.dtst if hasattr(log, 'dtst') else dataset.name,
                    "interpolation": log.interpolation if hasattr(log, 'interpolation') else '',
                    "log_type": log.log_type if hasattr(log, 'log_type') else '',
                    "log": sanitize_list(log.log) if hasattr(log, 'log') else []
                })
            
            constants = []
            if hasattr(dataset, 'constants') and dataset.constants:
                for const in dataset.constants:
                    constants.append({
                        "name": const.name if hasattr(const, 'name') else '',
                        "value": const.value if hasattr(const, 'value') else '',
                        "tag": const.tag if hasattr(const, 'tag') else ''
                    })
            
            datasets.append({
                "name": dataset.name,
                "type": dataset.type,
                "wellname": dataset.wellname,
                "index_name": dataset.index_name if hasattr(dataset, 'index_name') else 'DEPTH',
                "index_log": sanitize_list(dataset.index_log) if hasattr(dataset, 'index_log') else [],
                "well_logs": logs,
                "constants": constants
            })
        
        return {
            "success": True,
            "wellName": well.well_name if hasattr(well, 'well_name') else os.path.basename(resolved_path).replace('.ptrc', ''),
            "datasets": datasets
        }
        
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dataset-details", response_model=DatasetDetailsResponse)
async def get_dataset_details(wellPath: str, datasetName: str):
    """Get specific dataset details for data browser"""
    try:
        if not wellPath:
            raise HTTPException(status_code=400, detail="Well path is required")
        
        if not datasetName:
            raise HTTPException(status_code=400, detail="Dataset name is required")
        
        resolved_path = os.path.abspath(wellPath)
        if not validate_path(resolved_path):
            raise HTTPException(
                status_code=403,
                detail="Access denied: path outside petrophysics-workplace"
            )
        
        if not os.path.exists(resolved_path):
            raise HTTPException(status_code=404, detail="Well file not found")
        
        # Use cache-backed fetch instead of direct file read
        well_name = os.path.basename(resolved_path).replace('.ptrc', '')
        project_path = os.path.dirname(os.path.dirname(resolved_path))
        well, well_data, source = await fetch_well_data(project_path, well_name)
        
        target_dataset = None
        for dataset in well.datasets:
            if dataset.name == datasetName:
                target_dataset = dataset
                break
        
        if not target_dataset:
            raise HTTPException(status_code=404, detail=f"Dataset \"{datasetName}\" not found")
        
        logs = []
        for log in target_dataset.well_logs:
            logs.append({
                "name": log.name,
                "date": str(log.date) if hasattr(log, 'date') else '',
                "description": log.description if hasattr(log, 'description') else '',
                "dtst": log.dtst if hasattr(log, 'dtst') else target_dataset.name,
                "interpolation": log.interpolation if hasattr(log, 'interpolation') else '',
                "log_type": log.log_type if hasattr(log, 'log_type') else '',
                "log": sanitize_list(log.log) if hasattr(log, 'log') else []
            })
        
        constants = []
        if hasattr(target_dataset, 'constants') and target_dataset.constants:
            for const in target_dataset.constants:
                constants.append({
                    "name": const.name if hasattr(const, 'name') else '',
                    "value": const.value if hasattr(const, 'value') else '',
                    "tag": const.tag if hasattr(const, 'tag') else ''
                })
        
        dataset_details = {
            "name": target_dataset.name,
            "type": target_dataset.type,
            "wellname": target_dataset.wellname,
            "index_name": target_dataset.index_name if hasattr(target_dataset, 'index_name') else 'DEPTH',
            "index_log": sanitize_list(target_dataset.index_log) if hasattr(target_dataset, 'index_log') else [],
            "well_logs": logs,
            "constants": constants
        }
        
        return {
            "success": True,
            "dataset": dataset_details
        }
        
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list", response_model=WellListResponse)
async def list_wells(projectPath: str):
    """List all wells in a project (reads from SQLite first, falls back to .ptrc files)"""
    try:
        if not projectPath:
            raise HTTPException(status_code=400, detail="Project path is required")
        
        resolved_path = os.path.abspath(projectPath)
        if not validate_path(resolved_path):
            raise HTTPException(
                status_code=403,
                detail="Access denied: path outside petrophysics-workplace"
            )
        
        # If project doesn't exist, return empty list with helpful message
        if not os.path.exists(resolved_path):
            print(f"[Wells API] Project path does not exist: {resolved_path}")
            return {"wells": []}
        
        # Get wells from file storage index
        storage = get_file_well_storage()
        well_ids = storage.list_wells_in_project(resolved_path)
        
        if well_ids:
            print(f"[Wells API] Found {len(well_ids)} wells in file index")
            wells = []
            for well_id in well_ids:
                # Load minimal well data from cache only (already in memory - no I/O)
                well_data = storage.get_cached_well_data(resolved_path, well_id)
                if well_data:
                    wells.append({
                        "id": well_id,
                        "name": well_data.get('name', well_id),
                        "type": well_data.get('well_type', 'Dev'),
                        "path": os.path.join(resolved_path, "10-WELLS", f"{well_id}.ptrc"),
                        "created_at": well_data.get('date_created'),
                        "datasets": len(well_data.get('datasets', []))  # Keep just the count
                    })
            wells.sort(key=lambda x: x['name'])
            return {"wells": wells}
        
        # No wells found in cache index - return empty list
        print(f"[Wells API] No wells found in cache for project: {resolved_path}")
        return {"wells": []}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/datasets", response_model=WellDatasetsResponse)
async def get_well_datasets(projectPath: str, wellName: str):
    """Get all datasets for a well"""
    try:
        if not projectPath or not wellName:
            raise HTTPException(
                status_code=400,
                detail="Project path and well name are required"
            )
        
        resolved_path = os.path.abspath(projectPath)
        if not validate_path(resolved_path):
            raise HTTPException(
                status_code=403,
                detail="Access denied: path outside petrophysics-workplace"
            )
        
        wells_folder = os.path.join(resolved_path, "10-WELLS")
        well_file = os.path.join(wells_folder, f"{wellName}.ptrc")
        
        if not os.path.exists(well_file):
            raise HTTPException(status_code=404, detail=f"Well {wellName} not found")
        
        # Use cache-backed fetch instead of direct file read
        well, well_data, source = await fetch_well_data(resolved_path, wellName)
        
        # well_data is already available from fetch_well_data
        store_well_in_session(well_file, well_data)
        
        datasets = []
        seen_logs = set()
        
        for dataset in well.datasets:
            logs = []
            for well_log in dataset.well_logs:
                logs.append({
                    "name": well_log.name,
                    "date": str(well_log.date) if hasattr(well_log, 'date') else '',
                    "description": well_log.description if hasattr(well_log, 'description') else '',
                    "dtst": well_log.dtst if hasattr(well_log, 'dtst') else dataset.name,
                    "interpolation": well_log.interpolation if hasattr(well_log, 'interpolation') else '',
                    "log_type": well_log.log_type if hasattr(well_log, 'log_type') else '',
                })
            
            datasets.append({
                "name": dataset.name,
                "type": dataset.type,
                "wellname": dataset.wellname,
                "indexName": dataset.index_name if hasattr(dataset, 'index_name') else 'DEPTH',
                "index_name": dataset.index_name if hasattr(dataset, 'index_name') else 'DEPTH',
                "index_log": [],
                "logs": logs,
                "well_logs": logs,
                "constants": [],
                "date_created": dataset.date_created.isoformat() if dataset.date_created else None,
                "description": None
            })
            
            for well_log in dataset.well_logs:
                if well_log.name not in seen_logs:
                    seen_logs.add(well_log.name)
                    datasets.append({
                        "name": well_log.name,
                        "type": 'Cont' if well_log.log_type == 'float' else dataset.type,
                        "wellname": None,
                        "indexName": "DEPTH",
                        "index_name": "DEPTH",
                        "index_log": [],
                        "logs": [],
                        "well_logs": [],
                        "constants": [],
                        "date_created": None,
                        "description": well_log.description if hasattr(well_log, 'description') else ''
                    })
        
        return {
            "success": True,
            "wellName": well.well_name,
            "datasets": datasets
        }
        
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{well_id}/log-plot", response_model=LogPlotResponse)
async def generate_log_plot(well_id: str, data: LogPlotRequest):
    """Generate a well log plot for specified logs"""
    try:
        print(f"[LOG PLOT] Starting log plot generation for well: {well_id}")
        project_path = data.projectPath
        log_names = data.logNames
        
        if not project_path:
            print("[LOG PLOT] Error: Project path is required")
            raise HTTPException(status_code=400, detail="Project path is required")
        
        if not log_names or len(log_names) == 0:
            print("[LOG PLOT] Error: No log names provided")
            raise HTTPException(status_code=400, detail="At least one log name is required")
        
        print(f"[LOG PLOT] Plotting logs: {', '.join(log_names)}")
        
        resolved_path = os.path.abspath(project_path)
        if not validate_path(resolved_path):
            print("[LOG PLOT] Error: Path validation failed")
            raise HTTPException(
                status_code=403,
                detail="Access denied: path outside petrophysics-workplace"
            )
        
        # Fetch well data from cache only
        well, well_data, source = await fetch_well_data(resolved_path, well_id)
        print(f"[LOG PLOT] Well loaded successfully: {well.well_name}")
        print(f"[LOG PLOT] Number of datasets: {len(well.datasets)}")
        
        print("[LOG PLOT] Initializing LogPlotManager...")
        plot_manager = LogPlotManager()
        
        # Check if XML layout is requested
        xml_layout_path = None
        if data.layoutName:
            layout_file = os.path.join(os.path.dirname(__file__), '..', 'layouts', f'{data.layoutName}.xml')
            if os.path.exists(layout_file):
                xml_layout_path = layout_file
                print(f"[LOG PLOT] Using XML layout: {layout_file}")
            else:
                print(f"[LOG PLOT] Warning: XML layout '{data.layoutName}' not found, using default plotting")
        
        print("[LOG PLOT] Creating log plot with Plotly...")
        plotly_json = plot_manager.create_log_plot(well, log_names, xml_layout_path=xml_layout_path)
        
        if not plotly_json:
            print("[LOG PLOT] Error: Plot generation failed")
            raise HTTPException(status_code=500, detail="Failed to generate plot")
        
        print("[LOG PLOT] Plot generated successfully!")
        print(f"[LOG PLOT] Plotly JSON size: {len(plotly_json)} characters")
        
        return {
            "success": True,
            "plotly_json": plotly_json,
            "format": "plotly",
            "logs": [
                f"Starting log plot generation for well: {well_id}",
                f"Plotting logs: {', '.join(log_names)}",
                f"Well loaded: {well.well_name}",
                f"Number of datasets: {len(well.datasets)}",
                "Plot generated successfully with Plotly!"
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[LOG PLOT] Error: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{well_id}/cross-plot", response_model=CrossPlotResponse)
async def generate_cross_plot(well_id: str, data: CrossPlotRequest):
    """Generate a cross plot of two logs"""
    try:
        print(f"[CROSS PLOT] Starting cross plot generation for well: {well_id}")
        project_path = data.projectPath
        x_log_name = data.xLog
        y_log_name = data.yLog
        
        if not project_path or not x_log_name or not y_log_name:
            print("[CROSS PLOT] Error: Missing required parameters")
            raise HTTPException(
                status_code=400,
                detail="Project path, x log, and y log are required"
            )
        
        print(f"[CROSS PLOT] X-axis log: {x_log_name}")
        print(f"[CROSS PLOT] Y-axis log: {y_log_name}")
        
        resolved_path = os.path.abspath(project_path)
        if not validate_path(resolved_path):
            print("[CROSS PLOT] Error: Path validation failed")
            raise HTTPException(
                status_code=403,
                detail="Access denied: path outside petrophysics-workplace"
            )
        
        wells_folder = os.path.join(resolved_path, "10-WELLS")
        well_file = os.path.join(wells_folder, f"{well_id}.ptrc")
        
        print(f"[CROSS PLOT] Loading well from: {well_file}")
        if not os.path.exists(well_file):
            print("[CROSS PLOT] Error: Well file not found")
            raise HTTPException(status_code=404, detail=f"Well {well_id} not found")
        
        # Use cache-backed fetch instead of direct file read
        well, well_data, source = await fetch_well_data(resolved_path, well_id)
        print(f"[CROSS PLOT] Well loaded successfully from {source}: {well.well_name}")
        print(f"[CROSS PLOT] Number of datasets: {len(well.datasets)}")
        
        print("[CROSS PLOT] Initializing CrossPlotManager...")
        manager = CrossPlotManager()
        
        print("[CROSS PLOT] Creating cross plot with matplotlib...")
        plot_image = manager.create_cross_plot(well, x_log_name, y_log_name)
        
        if plot_image is None:
            print("[CROSS PLOT] Error: Failed to generate plot")
            raise HTTPException(
                status_code=404,
                detail="Failed to generate cross plot - logs not found or no valid data"
            )
        
        print("[CROSS PLOT] Cross plot generated successfully!")
        print(f"[CROSS PLOT] Image size: {len(plot_image)} characters (base64)")
        
        return {
            "success": True,
            "image": plot_image,
            "format": "png",
            "encoding": "base64",
            "logs": [
                f"Starting cross plot generation for well: {well_id}",
                f"X-axis log: {x_log_name}",
                f"Y-axis log: {y_log_name}",
                f"Well loaded: {well.well_name}",
                f"Number of datasets: {len(well.datasets)}",
                "Cross plot generated successfully!"
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{well_id}/cpi-plot", response_model=LogPlotResponse)
async def generate_cpi_plot(well_id: str, data: LogPlotRequest):
    """Generate a CPI layout well log plot using Plotly (interactive)"""
    try:
        print(f"[CPI PLOT] Starting CPI plot generation for well: {well_id}")
        project_path = data.projectPath
        layout_name = data.layoutName
        
        if not project_path:
            raise HTTPException(status_code=400, detail="Project path is required")
        
        if not layout_name:
            raise HTTPException(status_code=400, detail="Layout name is required for CPI plots")
        
        print(f"[CPI PLOT] Using layout: {layout_name}")
        
        resolved_path = os.path.abspath(project_path)
        if not validate_path(resolved_path):
            raise HTTPException(
                status_code=403,
                detail="Access denied: path outside petrophysics-workplace"
            )
        
        # Load well
        wells_folder = os.path.join(resolved_path, "10-WELLS")
        well_file = os.path.join(wells_folder, f"{well_id}.ptrc")
        
        print(f"[CPI PLOT] Loading well from: {well_file}")
        if not os.path.exists(well_file):
            raise HTTPException(status_code=404, detail=f"Well {well_id} not found")
        
        # Use cache-backed fetch instead of direct file read
        well, well_data, source = await fetch_well_data(resolved_path, well_id)
        print(f"[CPI PLOT] Well loaded from {source}: {well.well_name}")
        
        # Find XML layout file
        layouts_folder = os.path.join(Path(__file__).parent.parent, "layouts")
        xml_path = os.path.join(layouts_folder, f"{layout_name}.xml")
        
        if not os.path.exists(xml_path):
            raise HTTPException(status_code=404, detail=f"Layout {layout_name} not found")
        
        print(f"[CPI PLOT] Using layout file: {xml_path}")
        
        # Convert well data to DataFrame
        import pandas as pd
        
        # Collect all logs into a DataFrame
        all_logs = {}
        depth_log = None
        
        for dataset in well.datasets:
            # Get depth/index log
            if hasattr(dataset, 'index_log') and dataset.index_log:
                if depth_log is None:
                    depth_log = dataset.index_log
                    all_logs['DEPTH'] = dataset.index_log
            
            # Get well logs
            for wlog in dataset.well_logs:
                all_logs[wlog.name] = wlog.log
        
        if not all_logs or 'DEPTH' not in all_logs:
            raise HTTPException(status_code=400, detail="Well data must contain DEPTH log")
        
        df_logs = pd.DataFrame(all_logs)
        print(f"[CPI PLOT] DataFrame created with {len(df_logs)} rows and {len(df_logs.columns)} columns")
        
        # Load TOPS if available
        df_tops = None
        tops_found = False
        for dataset in well.datasets:
            if dataset.type.upper() == 'TOPS' or dataset.name.upper() == 'TOPS':
                tops_data = {}
                for wlog in dataset.well_logs:
                    if wlog.name.upper() == 'TOP':
                        tops_data['top_name'] = wlog.log
                        tops_found = True
                    elif 'DEPTH' in wlog.name.upper():
                        tops_data['depth'] = wlog.log
                
                if tops_found and 'depth' in tops_data:
                    df_tops = pd.DataFrame(tops_data)
                    print(f"[CPI PLOT] TOPS data found: {len(df_tops)} tops")
                break
        
        # Initialize CPI Plotly Manager
        print("[CPI PLOT] Initializing CPIPlotlyManager...")
        manager = CPIPlotlyManager()
        
        # Create the plot
        print("[CPI PLOT] Generating interactive CPI plot with Plotly...")
        plot_json = manager.create_cpi_plot(
            df_logs=df_logs,
            xml_layout_path=xml_path,
            well_name=well.well_name,
            df_tops=df_tops,
            df_perfs=None,  # TODO: Load perforation data if available
            spec_folder=None  # TODO: Add spec folder path if needed
        )
        
        print("[CPI PLOT] CPI plot generated successfully!")
        
        return {
            "success": True,
            "plotly_json": plot_json,
            "format": "plotly",
            "encoding": "json",
            "logs": [
                f"Starting CPI plot generation for well: {well_id}",
                f"Using layout: {layout_name}",
                f"Well loaded: {well.well_name}",
                f"DataFrame: {len(df_logs)} rows, {len(df_logs.columns)} columns",
                f"TOPS: {'Found' if df_tops is not None else 'Not found'}",
                "CPI plot generated successfully!"
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
