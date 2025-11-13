import os
from typing import Dict, Optional, List, Any
from datetime import datetime
from pathlib import Path

from utils.fe_data_objects import Well, Dataset


class WellSessionManager:
    """
    Manages loading, working with, and saving a batch of Well objects.
    Wells are kept in memory during the session and only saved on commit.
    """
    
    def __init__(self, project_path: str, initial_well_data: Optional[Dict[str, dict]] = None):
        """
        Initializes the session manager.
        
        Args:
            project_path: Path to the project directory
            initial_well_data: Optional dict of well data loaded from JSON storage cache
        """
        self.project_path = project_path
        self.wells_folder = os.path.join(project_path, '10-WELLS')
        
        self.session_wells: Dict[str, Well] = {}
        self.modified_wells: set = set()
        
        if initial_well_data:
            for well_name, well_dict in initial_well_data.items():
                self.session_wells[well_name] = Well.from_dict(well_dict)
    
    def _get_well_file_path(self, well_name: str) -> str:
        """Get the file path for a well."""
        return os.path.join(self.wells_folder, f"{well_name}.ptrc")
    
    def load_wells(self, well_names: List[str]) -> Dict[str, bool]:
        """
        Loads specified wells from .ptrc files into the session.
        
        Args:
            well_names: List of well names to load
            
        Returns:
            Dict mapping well names to success status
        """
        results = {}
        
        for well_name in well_names:
            file_path = self._get_well_file_path(well_name)
            
            if not os.path.exists(file_path):
                print(f"  [SESSION] Well '{well_name}' not found at {file_path}")
                results[well_name] = False
                continue
            
            try:
                well = Well.deserialize(filepath=file_path)
                self.session_wells[well_name] = well
                results[well_name] = True
                print(f"  [SESSION] Loaded well '{well_name}'")
            except Exception as e:
                print(f"  [SESSION] Error loading well '{well_name}': {e}")
                results[well_name] = False
        
        return results
    
    def get_well(self, well_name: str) -> Optional[Well]:
        """Get a well from the session."""
        return self.session_wells.get(well_name)
    
    def get_all_wells(self) -> Dict[str, Well]:
        """Get all wells in the session."""
        return self.session_wells
    
    def mark_modified(self, well_name: str):
        """Mark a well as modified."""
        if well_name in self.session_wells:
            self.modified_wells.add(well_name)
            print(f"  [SESSION] Well '{well_name}' marked as modified")
    
    def add_dataset_to_well(self, well_name: str, dataset: Dataset):
        """Add a dataset to a well and mark it as modified."""
        well = self.get_well(well_name)
        if well:
            well.add_dataset(dataset)
            self.mark_modified(well_name)
    
    def remove_dataset_from_well(self, well_name: str, dataset_name: str):
        """Remove a dataset from a well and mark it as modified."""
        well = self.get_well(well_name)
        if well:
            well.remove_dataset(dataset_name)
            self.mark_modified(well_name)
    
    def update_well_property(self, well_name: str, property_name: str, value: Any):
        """Update a well property and mark it as modified."""
        well = self.get_well(well_name)
        if well and hasattr(well, property_name):
            setattr(well, property_name, value)
            self.mark_modified(well_name)
    
    def commit_changes(self) -> Dict[str, bool]:
        """
        Saves all modified wells back to their .ptrc files.
        
        Returns:
            Dict mapping well names to save success status
        """
        results = {}
        
        os.makedirs(self.wells_folder, exist_ok=True)
        
        for well_name in self.modified_wells:
            well = self.session_wells.get(well_name)
            if not well:
                results[well_name] = False
                continue
            
            file_path = self._get_well_file_path(well_name)
            
            try:
                well.serialize(filename=file_path)
                results[well_name] = True
                print(f"  [SESSION] Saved well '{well_name}' to {file_path}")
            except Exception as e:
                print(f"  [SESSION] Error saving well '{well_name}': {e}")
                results[well_name] = False
        
        if not self.modified_wells:
            print("  [SESSION] No modified wells to save")
        
        return results
    
    def clear_session(self):
        """Clear all wells from the session."""
        self.session_wells.clear()
        self.modified_wells.clear()
        print("  [SESSION] Session cleared")
    
    def get_session_well_data(self) -> Dict[str, dict]:
        """
        Collects the current state as dictionaries for caching in JSON storage.
        
        Returns:
            Dict mapping well names to well data dictionaries
        """
        return {
            well_name: well.to_dict()
            for well_name, well in self.session_wells.items()
        }
    
    def get_metadata(self) -> dict:
        """
        Get session metadata for JSON storage storage.
        
        Returns:
            Dict containing project_path and modified_wells
        """
        return {
            "project_path": self.project_path,
            "modified_wells": list(self.modified_wells)
        }
    
    def restore_metadata(self, metadata: dict):
        """
        Restore session metadata from JSON storage.
        
        Args:
            metadata: Dict containing project_path and modified_wells
        """
        if "modified_wells" in metadata:
            self.modified_wells = set(metadata["modified_wells"])
    
    def get_session_summary(self) -> dict:
        """Get a summary of the current session."""
        return {
            "project_path": self.project_path,
            "total_wells": len(self.session_wells),
            "well_names": list(self.session_wells.keys()),
            "modified_wells": list(self.modified_wells),
            "modified_count": len(self.modified_wells)
        }
