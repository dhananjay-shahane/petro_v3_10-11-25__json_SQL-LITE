"""
Zonation Utilities for Petrophysics Workspace

This module provides utilities for reading, parsing, and managing zonation/tops data
from CSV and TSV files. It handles both single-well and multi-well file formats.
"""

import pandas as pd
from pathlib import Path
from typing import List, Dict, Optional, Tuple


class ZonationData:
    """Class to handle zonation/tops data operations"""
    
    @staticmethod
    def detect_delimiter(file_path: str) -> str:
        """
        Auto-detect delimiter (comma or tab) from file
        
        Args:
            file_path: Path to the tops file
            
        Returns:
            Detected delimiter (',' or '\t')
        """
        with open(file_path, 'r') as f:
            first_line = f.readline()
            if '\t' in first_line:
                return '\t'
            return ','
    
    @staticmethod
    def read_tops_file(file_path: str) -> pd.DataFrame:
        """
        Read a tops file and return as DataFrame
        
        Args:
            file_path: Path to the tops file (CSV or TSV)
            
        Returns:
            DataFrame containing tops data
            
        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file format is invalid
        """
        if not Path(file_path).exists():
            raise FileNotFoundError(f"Tops file not found: {file_path}")
        
        try:
            # Detect delimiter
            delimiter = ZonationData.detect_delimiter(file_path)
            
            # Read file
            df = pd.read_csv(file_path, delimiter=delimiter, header=0)
            
            # Normalize column names (case-insensitive)
            df.columns = df.columns.str.strip().str.upper()
            
            # Validate required columns
            if 'DEPTH' not in df.columns and 'DEPTH' not in df.columns:
                raise ValueError("Tops file must contain 'DEPTH' column")
            
            # Handle different column name variations
            if 'TOP' in df.columns and 'ZONE' not in df.columns:
                df = df.rename(columns={'TOP': 'ZONE'})
            elif 'ZONE' not in df.columns and 'TOP' not in df.columns:
                raise ValueError("Tops file must contain 'ZONE' or 'TOP' column")
            
            return df
            
        except Exception as e:
            raise ValueError(f"Error reading tops file: {str(e)}")
    
    @staticmethod
    def get_unique_zones(file_path: str) -> List[str]:
        """
        Get list of unique zones from a tops file
        
        Args:
            file_path: Path to the tops file
            
        Returns:
            List of unique zone names
        """
        df = ZonationData.read_tops_file(file_path)
        
        # Get unique zones
        if 'ZONE' in df.columns:
            zones = df['ZONE'].dropna().unique().tolist()
        else:
            zones = []
        
        return sorted(zones)
    
    @staticmethod
    def get_zones_for_well(file_path: str, well_name: str) -> List[Dict[str, any]]:
        """
        Get zones for a specific well from a tops file
        
        Args:
            file_path: Path to the tops file
            well_name: Name of the well
            
        Returns:
            List of dictionaries containing zone data [{'zone': 'name', 'depth': 123.45}, ...]
        """
        df = ZonationData.read_tops_file(file_path)
        
        # Check if file has WELL column (multi-well format)
        if 'WELL' in df.columns:
            # Filter by well name
            well_df = df[df['WELL'].str.strip() == well_name.strip()]
        else:
            # Single-well format - use all data
            well_df = df
        
        # Extract zones and depths
        zones_data = []
        if 'ZONE' in well_df.columns and 'DEPTH' in well_df.columns:
            for _, row in well_df.iterrows():
                zones_data.append({
                    'zone': str(row['ZONE']).strip(),
                    'depth': float(row['DEPTH'])
                })
        
        return zones_data
    
    @staticmethod
    def get_all_wells_from_file(file_path: str) -> List[str]:
        """
        Get list of all unique well names from a multi-well tops file
        
        Args:
            file_path: Path to the tops file
            
        Returns:
            List of unique well names
        """
        df = ZonationData.read_tops_file(file_path)
        
        if 'WELL' in df.columns:
            wells = df['WELL'].dropna().str.strip().unique().tolist()
            return sorted(wells)
        
        return []
    
    @staticmethod
    def check_zone_in_well(file_path: str, zone_name: str, well_name: str) -> bool:
        """
        Check if a specific zone exists for a given well
        
        Args:
            file_path: Path to the tops file
            zone_name: Name of the zone to check
            well_name: Name of the well
            
        Returns:
            True if zone exists for the well, False otherwise
        """
        zones = ZonationData.get_zones_for_well(file_path, well_name)
        zone_names = [z['zone'] for z in zones]
        return zone_name in zone_names
    
    @staticmethod
    def get_file_summary(file_path: str) -> Dict[str, any]:
        """
        Get summary information about a tops file
        
        Args:
            file_path: Path to the tops file
            
        Returns:
            Dictionary containing file summary information
        """
        df = ZonationData.read_tops_file(file_path)
        
        is_multi_well = 'WELL' in df.columns
        
        summary = {
            'filename': Path(file_path).name,
            'total_rows': len(df),
            'is_multi_well': is_multi_well,
            'columns': df.columns.tolist()
        }
        
        if is_multi_well:
            wells = df['WELL'].dropna().str.strip().unique().tolist()
            summary['wells'] = sorted(wells)
            summary['well_count'] = len(wells)
        else:
            summary['wells'] = []
            summary['well_count'] = 0
        
        if 'ZONE' in df.columns:
            zones = df['ZONE'].dropna().unique().tolist()
            summary['unique_zones'] = sorted([str(z) for z in zones])
            summary['zone_count'] = len(zones)
        else:
            summary['unique_zones'] = []
            summary['zone_count'] = 0
        
        return summary
