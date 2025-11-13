from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Dict, Optional
from pathlib import Path
import json
import os
from utils.sqlite_storage import SQLiteStorageService

router = APIRouter(tags=["settings"])
cache_service = SQLiteStorageService()

# Use data folder for application settings (global settings)
APPLICATION_SETTINGS_FILE = Path(__file__).parent.parent.parent / "data" / "application_setting.json"

class FontSizeSettings(BaseModel):
    dataBrowser: int = 14
    wellList: int = 14
    feedbackLog: int = 13
    zonationList: int = 14
    cliTerminal: int = 13

class SettingsPayload(BaseModel):
    fontSizes: FontSizeSettings
    projectPath: Optional[str] = None

def load_application_settings() -> Dict:
    """Load application settings from JSON file"""
    if not APPLICATION_SETTINGS_FILE.exists():
        return {}
    
    try:
        with open(APPLICATION_SETTINGS_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading application settings: {e}")
        return {}

def save_application_settings(settings: Dict):
    """Save application settings to JSON file"""
    try:
        # Ensure data directory exists
        APPLICATION_SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        with open(APPLICATION_SETTINGS_FILE, "w") as f:
            json.dump(settings, f, indent=2)
    except Exception as e:
        print(f"Error saving application settings: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save settings: {str(e)}")

def load_settings() -> Dict:
    """Load font size settings from application_setting.json layout section"""
    app_settings = load_application_settings()
    
    # Get font sizes from the layout section, fallback to defaults if not found
    layout = app_settings.get("layout", {})
    font_sizes = layout.get("fontSizes", FontSizeSettings().model_dump())
    
    return {"fontSizes": font_sizes}

def save_settings(settings: Dict):
    """Save font size settings to application_setting.json under layout section"""
    app_settings = load_application_settings()
    
    # Ensure layout section exists
    if "layout" not in app_settings:
        app_settings["layout"] = {}
    
    # Save font sizes under layout section
    if "fontSizes" in settings:
        app_settings["layout"]["fontSizes"] = settings["fontSizes"]
    
    save_application_settings(app_settings)

@router.get("/settings/font-sizes")
async def get_font_sizes(projectPath: Optional[str] = Query(None)):
    """Get current font size settings from SQLite layout table only"""
    default_font_sizes = FontSizeSettings().model_dump()
    
    if not projectPath:
        print(f"[Settings] No projectPath provided, returning default font sizes")
        return {"fontSizes": default_font_sizes}
    
    # Load from SQLite layout table only
    try:
        layout_data = cache_service.load_layout(projectPath, "default")
        if layout_data and "fontSizes" in layout_data:
            font_sizes = layout_data.get("fontSizes")
            # If fontSizes exists and is not empty, return it
            if font_sizes and isinstance(font_sizes, dict) and len(font_sizes) > 0:
                print(f"[Settings] ✓ Loaded font sizes from SQLite layout table: {font_sizes}")
                return {"fontSizes": font_sizes}
            else:
                print(f"[Settings] Layout exists but fontSizes is empty, returning defaults")
        else:
            print(f"[Settings] No layout found in SQLite, returning defaults")
    except Exception as e:
        print(f"[Settings] Error loading font sizes from SQLite: {e}")
    
    # Return defaults if nothing found in SQLite
    return {"fontSizes": default_font_sizes}

@router.post("/settings/font-sizes")
async def update_font_sizes(payload: SettingsPayload):
    """Update font size settings - saves to SQLite layout table only"""
    try:
        font_sizes_dict = payload.fontSizes.model_dump()
        print(f"[Settings] Saving font sizes to SQLite: {font_sizes_dict}")
        
        # Require projectPath - font sizes are stored per-project in SQLite only
        if not payload.projectPath:
            raise HTTPException(status_code=400, detail="projectPath is required to save font sizes")
        
        # Load current layout from SQLite
        layout_data = cache_service.load_layout(payload.projectPath, "default")
        
        if layout_data:
            # Update existing layout with new font sizes
            print(f"[Settings] Updating existing SQLite layout with font sizes")
            cache_service.save_layout(
                payload.projectPath,
                layout_data.get("layout", {}),
                layout_data.get("visiblePanels", []),
                "default",
                layout_data.get("windowLinks", {}),
                font_sizes_dict
            )
            print(f"[Settings] ✓ Font sizes saved to SQLite layout table: {font_sizes_dict}")
        else:
            # Create new layout with default panels and font sizes
            print(f"[Settings] Creating new SQLite layout with font sizes")
            default_panels = ["wells", "zonation", "dataBrowser", "feedback", "cli"]
            cache_service.save_layout(
                payload.projectPath,
                {},
                default_panels,
                "default",
                {},
                font_sizes_dict
            )
            print(f"[Settings] ✓ Created new SQLite layout with font sizes: {font_sizes_dict}")
        
        return {"success": True, "message": "Font sizes saved to SQLite layout table", "fontSizes": font_sizes_dict}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[Settings] ✗ Error saving font sizes to SQLite: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
