import os
import shutil
import uuid
import tempfile
from pathlib import Path
from typing import List
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from fastapi.responses import JSONResponse

router = APIRouter()

# Use cross-platform temp directory (works on Windows, Linux, macOS)
UPLOAD_DIR = Path(tempfile.gettempdir()) / "las_uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/upload/las-file")
async def upload_las_file(
    file: UploadFile = File(...),
    project_path: str = Form(...)
):
    """
    Upload a single LAS file from user's local PC for use with IMPORT_LAS_FILE command.
    The file is saved to a temporary location and the server path is returned.
    """
    file_path = None
    try:
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")
        
        if not file.filename.lower().endswith('.las'):
            raise HTTPException(
                status_code=400,
                detail="Only .las files are allowed"
            )
        
        # Validate file size (500 MB limit) while reading
        MAX_FILE_SIZE = 500 * 1024 * 1024  # 500 MB
        total_size = 0
        
        # Create a unique subdirectory for this upload session (using UUID to avoid collisions)
        session_id = str(uuid.uuid4())
        upload_session_dir = UPLOAD_DIR / f"session_{session_id}"
        upload_session_dir.mkdir(parents=True, exist_ok=True)
        
        # Save the uploaded file
        file_path = upload_session_dir / file.filename
        
        print(f"[FileUpload] Uploading {file.filename} to {file_path}")
        
        # Read and write file in chunks to validate size without loading all into memory
        chunk_size = 1024 * 1024  # 1 MB chunks
        with open(file_path, "wb") as buffer:
            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break
                total_size += len(chunk)
                if total_size > MAX_FILE_SIZE:
                    # Clean up partial file immediately
                    buffer.close()
                    if file_path.exists():
                        file_path.unlink()
                    raise HTTPException(
                        status_code=413,
                        detail=f"File too large. Maximum upload size is 500 MB"
                    )
                buffer.write(chunk)
        
        # Verify file was written successfully
        if not file_path.exists():
            raise HTTPException(status_code=500, detail="File upload failed - file not saved")
        
        file_size_mb = total_size / (1024 * 1024)
        print(f"[FileUpload] Successfully uploaded {file.filename} ({file_size_mb:.2f} MB) to {file_path}")
        print(f"[FileUpload] File exists check: {file_path.exists()}")
        print(f"[FileUpload] File path (absolute): {file_path.absolute()}")
        
        return JSONResponse({
            "success": True,
            "filename": file.filename,
            "server_path": str(file_path.absolute()),  # Use absolute path
            "session_id": session_id,
            "file_size_mb": round(file_size_mb, 2),
            "message": f"File '{file.filename}' uploaded successfully ({file_size_mb:.2f} MB)"
        })
    
    except HTTPException:
        raise
    except Exception as e:
        # Clean up partial file on error
        if file_path and file_path.exists():
            try:
                file_path.unlink()
                print(f"[FileUpload] Cleaned up partial file after error")
            except:
                pass
        print(f"[FileUpload] Error uploading file: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
    finally:
        await file.close()


@router.post("/upload/las-files")
async def upload_las_files(
    files: List[UploadFile] = File(...),
    project_path: str = Form(...)
):
    """
    Upload multiple LAS files from user's local PC for use with IMPORT_LAS_FILES_FROM_FOLDER.
    Files are saved to a temporary folder and the folder path is returned.
    """
    upload_session_dir = None
    try:
        if not files:
            raise HTTPException(status_code=400, detail="No files provided")
        
        # Validate file size (500 MB limit per file)
        MAX_FILE_SIZE = 500 * 1024 * 1024  # 500 MB
        
        # Create a unique subdirectory for this upload session (using UUID to avoid collisions)
        session_id = str(uuid.uuid4())
        upload_session_dir = UPLOAD_DIR / f"folder_session_{session_id}"
        upload_session_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"[FileUpload] Created upload session directory: {upload_session_dir}")
        
        uploaded_files = []
        skipped_files = []
        
        for file in files:
            if not file.filename:
                continue
            
            if not file.filename.lower().endswith('.las'):
                skipped_files.append(file.filename)
                print(f"[FileUpload] Skipped non-LAS file: {file.filename}")
                continue
            
            file_path = upload_session_dir / file.filename
            total_size = 0
            
            print(f"[FileUpload] Uploading {file.filename}...")
            
            # Read and write file in chunks to validate size
            chunk_size = 1024 * 1024  # 1 MB chunks
            try:
                with open(file_path, "wb") as buffer:
                    while True:
                        chunk = await file.read(chunk_size)
                        if not chunk:
                            break
                        total_size += len(chunk)
                        if total_size > MAX_FILE_SIZE:
                            # Clean up partial file
                            buffer.close()
                            if file_path.exists():
                                file_path.unlink()
                            skipped_files.append(f"{file.filename} (too large)")
                            print(f"[FileUpload] Skipped {file.filename} - file too large ({total_size / (1024 * 1024):.2f} MB)")
                            break
                        buffer.write(chunk)
                
                # Only count as uploaded if file was completely written
                if file_path.exists() and total_size <= MAX_FILE_SIZE:
                    uploaded_files.append(file.filename)
                    file_size_mb = total_size / (1024 * 1024)
                    print(f"[FileUpload] Successfully uploaded {file.filename} ({file_size_mb:.2f} MB)")
            
            except Exception as file_error:
                # Clean up partial file on error
                if file_path.exists():
                    try:
                        file_path.unlink()
                    except:
                        pass
                skipped_files.append(f"{file.filename} (error)")
                print(f"[FileUpload] Error uploading {file.filename}: {file_error}")
        
        if not uploaded_files:
            # Clean up empty directory
            if upload_session_dir.exists():
                shutil.rmtree(upload_session_dir)
            raise HTTPException(
                status_code=400,
                detail="No valid .las files were uploaded"
            )
        
        print(f"[FileUpload] Upload session complete: {len(uploaded_files)} files uploaded")
        print(f"[FileUpload] Folder path (absolute): {upload_session_dir.absolute()}")
        
        return JSONResponse({
            "success": True,
            "uploaded_count": len(uploaded_files),
            "uploaded_files": uploaded_files,
            "skipped_files": skipped_files,
            "folder_path": str(upload_session_dir.absolute()),  # Use absolute path
            "session_id": session_id,
            "message": f"Uploaded {len(uploaded_files)} file(s) successfully"
        })
    
    except HTTPException:
        raise
    except Exception as e:
        # Clean up directory on error
        if upload_session_dir and upload_session_dir.exists():
            try:
                shutil.rmtree(upload_session_dir)
                print(f"[FileUpload] Cleaned up upload directory after error")
            except:
                pass
        print(f"[FileUpload] Error uploading files: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
    finally:
        for file in files:
            await file.close()


@router.post("/upload/cleanup")
async def cleanup_uploads():
    """
    Clean up temporary upload files.
    This can be called periodically or after imports are complete.
    """
    try:
        if UPLOAD_DIR.exists():
            shutil.rmtree(UPLOAD_DIR)
            UPLOAD_DIR.mkdir(exist_ok=True)
        
        return JSONResponse({
            "success": True,
            "message": "Upload directory cleaned up"
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")
