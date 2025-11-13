import os
import secrets
import logging
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from pathlib import Path

from routers import workspace, projects, directories, data, wells, sessions, well_sessions, cli, storage_inspector, file_upload, workspace_sync, tops, settings
from utils.file_well_storage import initialize_file_well_storage
from dependencies import WORKSPACE_ROOT


IS_PRODUCTION = os.environ.get('NODE_ENV') == 'production'
MAX_UPLOAD_SIZE = 500 * 1024 * 1024  # 500 MB limit for large LAS files


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan hook for FastAPI application.
    Handles startup and shutdown events.
    """
    # STARTUP: Index well files (.ptrc) at application startup
    print("=" * 60)
    print("[STARTUP] Initializing File-Based Well Storage...")
    print("=" * 60)
    
    try:
        initialize_file_well_storage(WORKSPACE_ROOT)
        print("[STARTUP] Well file indexing complete. App is ready.")
    except Exception as e:
        print(f"[STARTUP] Warning: Failed to index well files: {e}")
        import traceback
        traceback.print_exc()
    
    print("=" * 60)
    
    yield  # App starts serving requests
    
    # SHUTDOWN: Cleanup if needed
    print("[SHUTDOWN] Server shutting down...")


def create_app():
    """Create and configure the FastAPI application"""
    app = FastAPI(
        title="Petrophysics Workspace API",
        description="API for petrophysics data analysis and visualization",
        version="2.0.0",
        docs_url="/docs" if not IS_PRODUCTION else None,
        redoc_url="/redoc" if not IS_PRODUCTION else None,
        lifespan=lifespan
    )
    
    logging.basicConfig(
        level=logging.DEBUG if not IS_PRODUCTION else logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        stream=sys.stdout
    )
    
    cors_origins = ['http://localhost:5000', 'http://0.0.0.0:5000']
    if not IS_PRODUCTION:
        cors_origins = ["*"]
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))
    app.add_middleware(
        SessionMiddleware,
        secret_key=secret_key,
        max_age=86400 * 30,
        same_site="none" if not IS_PRODUCTION else "lax",
        https_only=IS_PRODUCTION
    )
    
    @app.middleware("http")
    async def check_content_length(request: Request, call_next):
        """Middleware to check request size and provide better error messages"""
        if request.method in ["POST", "PUT", "PATCH"]:
            content_length = request.headers.get("content-length")
            if content_length and int(content_length) > MAX_UPLOAD_SIZE:
                return JSONResponse(
                    status_code=413,
                    content={
                        "detail": f"File too large. Maximum upload size is {MAX_UPLOAD_SIZE // (1024 * 1024)} MB"
                    }
                )
        response = await call_next(request)
        return response
    
    @app.get("/health")
    async def health():
        return {"status": "ok"}
    
    app.include_router(workspace.router, prefix="/api")
    app.include_router(projects.router, prefix="/api")
    app.include_router(directories.router, prefix="/api")
    app.include_router(data.router, prefix="/api")
    app.include_router(wells.router, prefix="/api")
    app.include_router(sessions.router, prefix="/api")
    app.include_router(well_sessions.router, prefix="/api")
    app.include_router(cli.router, prefix="/api")
    app.include_router(storage_inspector.router, prefix="/api")
    app.include_router(file_upload.router, prefix="/api")
    app.include_router(workspace_sync.router, prefix="/api")
    app.include_router(tops.router, prefix="/api")
    app.include_router(settings.router, prefix="/api")
    
    if IS_PRODUCTION:
        static_folder = Path(__file__).parent.parent / "dist" / "public"
        if static_folder.exists():
            app.mount("/", StaticFiles(directory=str(static_folder), html=True), name="static")
    
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.environ.get('FLASK_PORT', 5001))
    host = '0.0.0.0' if IS_PRODUCTION else 'localhost'
    
    print(f"FastAPI server starting on http://{host}:{port}")
    print(f"Mode: {'PRODUCTION' if IS_PRODUCTION else 'DEVELOPMENT'}")
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=not IS_PRODUCTION,
        log_level="info" if IS_PRODUCTION else "debug"
    )
