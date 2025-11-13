"""
CLI Service for executing well and dataset operations via command-line interface.
Supports operations like INSERT_CONSTANT, IMPORT_LAS_FILE, DELETE_DATASET, etc.
"""

import os
import re
import sqlite3
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from pathlib import Path
import pandas as pd

from utils.fe_data_objects import Well, Dataset, WellLog, Constant
from utils.las_file_io import read_las_file, get_well_name_from_las, create_well_from_las
from utils.data_import_export import (ImportLasFileCommand,
                                      ImportLasFilesFromFolderCommand,
                                      LoadTopsCommand, LoadTopsBulkCommand,
                                      ExportTopsCommand, ExportToLasCommand)
import csv


class CLICommand:
    """Base class for CLI commands."""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    def execute(self, args: Dict[str, Any],
                context: Dict[str, Any]) -> Tuple[bool, str, Any]:
        """
        Execute the command.
        
        Args:
            args: Command arguments
            context: Execution context (project_path, current_well, etc.)
            
        Returns:
            Tuple of (success, message, result_data)
        """
        raise NotImplementedError


class InsertConstantCommand(CLICommand):
    """Insert a constant into an existing well."""

    def __init__(self):
        super().__init__(
            "INSERT_CONSTANT",
            "Insert a constant into an existing well. Usage: INSERT_CONSTANT well_name const_name value [tag]"
        )

    def execute(self, args: Dict[str, Any],
                context: Dict[str, Any]) -> Tuple[bool, str, Any]:
        well_name = args.get('well_name')
        const_name = args.get('const_name')
        value = args.get('value')
        tag = args.get('tag', '')

        if not all([well_name, const_name, value is not None]):
            return False, "Missing required arguments: well_name, const_name, value", None

        project_path = context.get('project_path')
        if not project_path:
            return False, "No project loaded", None

        well_path = os.path.join(project_path, '10-WELLS', f'{well_name}.ptrc')

        if not os.path.exists(well_path):
            return False, f"Well '{well_name}' not found", None

        try:
            well = Well.deserialize(well_path)

            constant = Constant(name=const_name, value=value, tag=tag)

            target_dataset = None
            for dataset in well.datasets:
                if dataset.name == 'WELL_HEADER':
                    target_dataset = dataset
                    break

            if target_dataset is None:
                target_dataset = Dataset(date_created=datetime.now(),
                                         name='WELL_HEADER',
                                         type='WELL_HEADER',
                                         wellname=well_name,
                                         constants=[],
                                         index_log=[],
                                         index_name='DEPTH',
                                         well_logs=[],
                                         metadata={})
                well.add_dataset(target_dataset)

            target_dataset.constants.append(constant)
            well.serialize(well_path)
            # check if constant if allready exists then add suffix _1, _2, etc. similar done when add log
            return True, f"✓ Constant '{const_name}' = {value} added to well '{well_name}'", {
                'well_name': well_name,
                'const_name': const_name,
                'value': value,
                'tag': tag
            }
        except PermissionError:
            return False, f"❌ Permission denied: Cannot write to well file '{well_name}'. Please check file permissions.", None
        except FileNotFoundError:
            return False, f"❌ Well file not found: '{well_name}'. The well may have been deleted.", None
        except Exception as e:
            error_msg = str(e)
            if "serialize" in error_msg.lower():
                return False, f"❌ Failed to save changes to well '{well_name}'. The well file may be corrupted.", None
            elif "deserialize" in error_msg.lower():
                return False, f"❌ Failed to read well '{well_name}'. The well file may be corrupted or in use by another program.", None
            else:
                return False, f"❌ Error adding constant: {error_msg}", None


class InsertLogCommand(CLICommand):
    """Insert an empty log into an existing well."""

    def __init__(self):
        super().__init__(
            "INSERT_LOG",
            "Insert an empty log into a well. Usage: INSERT_LOG well_name log_name [description] [log_type]"
        )

    def execute(self, args: Dict[str, Any],
                context: Dict[str, Any]) -> Tuple[bool, str, Any]:
        well_name = args.get('well_name')
        log_name = args.get('log_name')
        description = args.get('description', '')
        log_type = args.get('log_type', 'float')

        if not all([well_name, log_name]):
            return False, "Missing required arguments: well_name, log_name", None

        project_path = context.get('project_path')
        if not project_path:
            return False, "No project loaded", None

        well_path = os.path.join(project_path, '10-WELLS', f'{well_name}.ptrc')

        if not os.path.exists(well_path):
            return False, f"Well '{well_name}' not found", None

        try:
            well = Well.deserialize(well_path)

            log = WellLog(
                name=log_name,
                date=datetime.now().isoformat(),
                description=description,
                interpolation='CONTINUOUS',
                log_type=log_type if log_type in ['str', 'float'] else 'float',
                log=[],
                dtst='MANUAL_DATA')

            manual_dataset = None
            for dataset in well.datasets:
                if dataset.name == 'MANUAL_DATA':
                    manual_dataset = dataset
                    break

            if manual_dataset is None:
                manual_dataset = Dataset(date_created=datetime.now(),
                                         name='MANUAL_DATA',
                                         type='MANUAL',
                                         wellname=well_name,
                                         constants=[],
                                         index_log=[],
                                         index_name='DEPTH',
                                         well_logs=[],
                                         metadata={})
                well.add_dataset(manual_dataset)

            manual_dataset.well_logs.append(log)
            well.serialize(well_path)

            return True, f"Empty log '{log_name}' ({log_type}) added to well '{well_name}'", {
                'well_name': well_name,
                'log_name': log_name,
                'log_type': log_type
            }
        except Exception as e:
            return False, f"Error adding log: {str(e)}", None


class CreateEmptyWellCommand(CLICommand):
    """Create a new empty well."""

    def __init__(self):
        super().__init__(
            "CREATE_EMPTY_WELL",
            "Create a new empty well. Usage: CREATE_EMPTY_WELL well_name [well_type]"
        )

    def execute(self, args: Dict[str, Any],
                context: Dict[str, Any]) -> Tuple[bool, str, Any]:
        well_name = args.get('well_name')
        well_type = args.get('well_type', 'Dev')

        if not well_name:
            return False, "Missing required argument: well_name", None

        project_path = context.get('project_path')
        if not project_path:
            return False, "No project loaded", None

        wells_dir = os.path.join(project_path, '10-WELLS')
        os.makedirs(wells_dir, exist_ok=True)

        well_path = os.path.join(wells_dir, f'{well_name}.ptrc')

        if os.path.exists(well_path):
            return False, f"Well '{well_name}' already exists", None

        try:
            well = Well(date_created=datetime.now(),
                        well_name=well_name,
                        well_type=well_type,
                        datasets=[])

            well.serialize(well_path)

            return True, f"Empty well '{well_name}' created successfully", {
                'well_name': well_name,
                'well_type': well_type,
                'well_path': well_path
            }
        except Exception as e:
            return False, f"Error creating well: {str(e)}", None


class DeleteDatasetCommand(CLICommand):
    """Delete a dataset from a well."""

    def __init__(self):
        super().__init__(
            "DELETE_DATASET",
            "Delete a dataset from a well. Usage: DELETE_DATASET well_name dataset_name"
        )

    def execute(self, args: Dict[str, Any],
                context: Dict[str, Any]) -> Tuple[bool, str, Any]:
        well_name = args.get('well_name')
        dataset_name = args.get('dataset_name')

        if not all([well_name, dataset_name]):
            return False, "Missing required arguments: well_name, dataset_name", None

        project_path = context.get('project_path')
        if not project_path:
            return False, "No project loaded", None

        well_path = os.path.join(project_path, '10-WELLS', f'{well_name}.ptrc')

        if not os.path.exists(well_path):
            return False, f"Well '{well_name}' not found", None

        try:
            well = Well.deserialize(well_path)

            dataset = well.get_dataset(dataset_name)
            if not dataset:
                return False, f"Dataset '{dataset_name}' not found in well '{well_name}'", None

            well.remove_dataset(dataset_name)
            well.serialize(well_path)

            return True, f"Dataset '{dataset_name}' deleted from well '{well_name}'", {
                'well_name': well_name,
                'dataset_name': dataset_name
            }
        except Exception as e:
            return False, f"Error deleting dataset: {str(e)}", None


class SelectWellsCommand(CLICommand):
    """Filter the well list to show only specified wells."""

    def __init__(self):
        super().__init__(
            "SELECT_WELLS",
            "Filter the well list to show only specified wells. Usage: SELECT_WELLS well1 well2 well3 ..."
        )

    def execute(self, args: Dict[str, Any],
                context: Dict[str, Any]) -> Tuple[bool, str, Any]:
        from utils.sqlite_storage import SQLiteStorageService
        cache_service = SQLiteStorageService()

        well_names = args.get('well_names', [])

        if not well_names:
            return False, "No well names provided. Usage: SELECT_WELLS well1 well2 well3 ...", None

        project_path = context.get('project_path')
        if not project_path:
            return False, "No project loaded", None

        wells_dir = os.path.join(project_path, '10-WELLS')

        if not os.path.exists(wells_dir):
            return False, "Wells directory not found", None

        try:
            found_wells = []
            not_found_wells = []

            for well_name in well_names:
                well_path = os.path.join(wells_dir, f'{well_name}.ptrc')
                if os.path.exists(well_path):
                    found_wells.append(well_name)
                else:
                    not_found_wells.append(well_name)

            if not found_wells:
                return False, f"None of the specified wells were found: {', '.join(well_names)}", None

            # Use cache service to save selected wells with proper key format
            cache_service.save_selected_wells(project_path, found_wells)
            print(
                f"  [CLI] Saved {len(found_wells)} selected wells to JSON storage for project: {project_path}"
            )

            message_parts = [
                f"✓ Well list filtered to show {len(found_wells)} well(s): {', '.join(found_wells)}"
            ]
            message_parts.append(
                f"✓ Selection saved to storage and will be restored when project loads"
            )
            message_parts.append(
                f"✓ Wells panel will update automatically to show only selected wells"
            )

            if not_found_wells:
                message_parts.append(
                    f"⚠ Wells not found: {', '.join(not_found_wells)}")

            return True, "\n".join(message_parts), {
                'selected_wells': found_wells,
                'not_found_wells': not_found_wells,
                'total_selected': len(found_wells)
            }
        except Exception as e:
            return False, f"Error filtering wells: {str(e)}", None


class ActiveWellCommand(CLICommand):
    """Activate a well for viewing in the Data Browser without filtering the wells list."""

    def __init__(self):
        super().__init__(
            "ACTIVE_WELL",
            "Activate a well for viewing in Data Browser (does not filter wells list). Usage: ACTIVE_WELL well_name"
        )

    def execute(self, args: Dict[str, Any],
                context: Dict[str, Any]) -> Tuple[bool, str, Any]:
        from utils.sqlite_storage import SQLiteStorageService
        cache_service = SQLiteStorageService()

        well_name = args.get('well_name')

        if not well_name:
            return False, "Missing required argument: well_name. Usage: ACTIVE_WELL well_name", None

        project_path = context.get('project_path')
        if not project_path:
            return False, "No project loaded", None

        wells_dir = os.path.join(project_path, '10-WELLS')
        well_path = os.path.join(wells_dir, f'{well_name}.ptrc')

        if not os.path.exists(well_path):
            return False, f"Well '{well_name}' not found in project", None

        try:
            # Save the active well (does NOT filter the wells list)
            cache_service.save_active_well(project_path, well_name)

            print(
                f"  [CLI] Set '{well_name}' as active well in JSON storage for project: {project_path}"
            )

            return True, f"✓ Well '{well_name}' is now active in Data Browser.\n✓ All wells remain visible in the wells list.\n✓ Use SELECT_WELLS to filter the wells list.", {
                'active_well': well_name,
                'active': True
            }
        except Exception as e:
            return False, f"Error activating well: {str(e)}", None


class ListAllWellsCommand(CLICommand):
    """List all wells in the project."""

    def __init__(self):
        super().__init__(
            "LIST_ALL_WELLS",
            "List all wells in the current project. Usage: LIST_ALL_WELLS")

    def execute(self, args: Dict[str, Any],
                context: Dict[str, Any]) -> Tuple[bool, str, Any]:
        project_path = context.get('project_path')
        if not project_path:
            return False, "No project loaded", None

        wells_dir = os.path.join(project_path, '10-WELLS')

        if not os.path.exists(wells_dir):
            return False, "Wells directory not found", None

        try:
            well_files = [
                f for f in os.listdir(wells_dir) if f.endswith('.ptrc')
            ]
            well_names = [f.replace('.ptrc', '') for f in well_files]

            if not well_names:
                return True, "No wells found in project", {'wells': []}

            wells_info = []
            for well_name in sorted(well_names):
                well_path = os.path.join(wells_dir, f'{well_name}.ptrc')
                try:
                    well = Well.deserialize(well_path)
                    dataset_count = len(well.datasets) if hasattr(
                        well, 'datasets') else 0
                    wells_info.append({
                        'name': well_name,
                        'datasets': dataset_count
                    })
                except Exception as e:
                    wells_info.append({
                        'name': well_name,
                        'datasets': 'error',
                        'error': str(e)
                    })

            message_parts = [f"Found {len(well_names)} well(s) in project:"]
            for info in wells_info:
                if info.get('error'):
                    message_parts.append(f"  - {info['name']} (error loading)")
                else:
                    message_parts.append(
                        f"  - {info['name']} ({info['datasets']} datasets)")

            return True, "\n".join(message_parts), {
                'wells': wells_info,
                'count': len(well_names)
            }
        except Exception as e:
            return False, f"Error listing wells: {str(e)}", None


class ListOfDatasetCommand(CLICommand):
    """List all datasets in a well."""

    def __init__(self):
        super().__init__(
            "LIST_OF_DATASET",
            "List all datasets in a specific well. Usage: LIST_OF_DATASET well_name"
        )

    def execute(self, args: Dict[str, Any],
                context: Dict[str, Any]) -> Tuple[bool, str, Any]:
        well_name = args.get('well_name')

        if not well_name:
            return False, "Missing required argument: well_name", None

        project_path = context.get('project_path')
        if not project_path:
            return False, "No project loaded", None

        well_path = os.path.join(project_path, '10-WELLS', f'{well_name}.ptrc')

        if not os.path.exists(well_path):
            return False, f"Well '{well_name}' not found", None

        try:
            well = Well.deserialize(well_path)

            if not well.datasets:
                return True, f"Well '{well_name}' has no datasets", {
                    'datasets': []
                }

            datasets_info = []
            for dataset in well.datasets:
                log_count = len(dataset.well_logs) if hasattr(
                    dataset, 'well_logs') else 0
                const_count = len(dataset.constants) if hasattr(
                    dataset, 'constants') else 0
                datasets_info.append({
                    'name':
                    dataset.name,
                    'type':
                    dataset.type if hasattr(dataset, 'type') else 'unknown',
                    'logs':
                    log_count,
                    'constants':
                    const_count
                })

            message_parts = [
                f"Well '{well_name}' has {len(datasets_info)} dataset(s):"
            ]
            for info in datasets_info:
                message_parts.append(
                    f"  - {info['name']} (type: {info['type']}, {info['logs']} logs, {info['constants']} constants)"
                )

            return True, "\n".join(message_parts), {
                'datasets': datasets_info,
                'count': len(datasets_info)
            }
        except Exception as e:
            return False, f"Error reading well '{well_name}': {str(e)}", None


class FindWithDatasetCommand(CLICommand):
    """Find wells that contain a specific dataset."""

    def __init__(self):
        super().__init__(
            "FIND_WITH_DATASET",
            "Find all wells containing a specific dataset. Usage: FIND_WITH_DATASET dataset_name"
        )

    def execute(self, args: Dict[str, Any],
                context: Dict[str, Any]) -> Tuple[bool, str, Any]:
        dataset_name = args.get('dataset_name')

        if not dataset_name:
            return False, "Missing required argument: dataset_name", None

        project_path = context.get('project_path')
        if not project_path:
            return False, "No project loaded", None

        wells_dir = os.path.join(project_path, '10-WELLS')

        if not os.path.exists(wells_dir):
            return False, "Wells directory not found", None

        try:
            well_files = [
                f for f in os.listdir(wells_dir) if f.endswith('.ptrc')
            ]
            matching_wells = []

            for well_file in well_files:
                well_name = well_file.replace('.ptrc', '')
                well_path = os.path.join(wells_dir, well_file)

                try:
                    well = Well.deserialize(well_path)
                    for dataset in well.datasets:
                        if dataset.name == dataset_name:
                            log_count = len(dataset.well_logs) if hasattr(
                                dataset, 'well_logs') else 0
                            matching_wells.append({
                                'well_name': well_name,
                                'logs': log_count
                            })
                            break
                except Exception:
                    continue

            if not matching_wells:
                return True, f"No wells found with dataset '{dataset_name}'", {
                    'wells': []
                }

            message_parts = [
                f"Found {len(matching_wells)} well(s) with dataset '{dataset_name}':"
            ]
            for info in matching_wells:
                message_parts.append(
                    f"  - {info['well_name']} ({info['logs']} logs)")

            return True, "\n".join(message_parts), {
                'wells': matching_wells,
                'count': len(matching_wells)
            }
        except Exception as e:
            return False, f"Error searching for dataset '{dataset_name}': {str(e)}", None


class DeleteWellCommand(CLICommand):
    """Delete a well from the project (requires permission)."""

    def __init__(self):
        super().__init__(
            "DELETE_WELL",
            "Delete a well from the project. Requires delete permission to be enabled. Usage: DELETE_WELL well_name"
        )

    def execute(self, args: Dict[str, Any],
                context: Dict[str, Any]) -> Tuple[bool, str, Any]:
        well_name = args.get('well_name')

        if not well_name:
            return False, "Missing required argument: well_name", None

        # Check if delete permission is enabled
        permission_enabled = args.get('delete_permission_enabled', False)
        if not permission_enabled:
            return False, "Delete permission is not enabled. Please enable it from the Data menu first.", None

        project_path = context.get('project_path')
        if not project_path:
            return False, "No project loaded", None

        well_path = os.path.join(project_path, '10-WELLS', f'{well_name}.ptrc')

        if not os.path.exists(well_path):
            return False, f"Well '{well_name}' not found", None

        try:
            os.remove(well_path)
            return True, f"Well '{well_name}' has been permanently deleted", {
                'well_name': well_name,
                'deleted': True
            }
        except Exception as e:
            return False, f"Error deleting well '{well_name}': {str(e)}", None


class DBListProjectsCommand(CLICommand):
    """List all projects in SQLite database."""

    def __init__(self):
        super().__init__(
            "DB_LIST_PROJECTS",
            "List all projects stored in the SQLite database. Usage: DB_LIST_PROJECTS"
        )

    def execute(self, args: Dict[str, Any],
                context: Dict[str, Any]) -> Tuple[bool, str, Any]:
        try:
            db_path = Path(__file__).parent.parent.parent / "data" / "petrophysics.db"
            if not db_path.exists():
                return False, "Database file not found", None
            
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT session_id, project_name, project_path, updated_at, created_at
                FROM projects
                ORDER BY updated_at DESC
            """)
            
            projects = cursor.fetchall()
            conn.close()
            
            if not projects:
                return True, "No projects found in database", {'projects': []}
            
            message_parts = [f"Found {len(projects)} project(s) in database:\n"]
            project_list = []
            
            for p in projects:
                session_id = p['session_id'][:12] + "..." if p['session_id'] else "N/A"
                name = p['project_name'] or "Unnamed"
                path = p['project_path'] or "N/A"
                updated = p['updated_at'] or "N/A"
                
                message_parts.append(f"  • {name}")
                message_parts.append(f"    Path: {path}")
                message_parts.append(f"    Session: {session_id}")
                message_parts.append(f"    Updated: {updated}\n")
                
                project_list.append({
                    'name': name,
                    'path': path,
                    'session_id': p['session_id'],
                    'updated_at': updated
                })
            
            return True, "\n".join(message_parts), {'projects': project_list, 'count': len(projects)}
            
        except Exception as e:
            return False, f"Error querying database: {str(e)}", None


class DBListWellsCommand(CLICommand):
    """List all wells in SQLite database."""

    def __init__(self):
        super().__init__(
            "DB_LIST_WELLS",
            "List all wells stored in the SQLite database. Usage: DB_LIST_WELLS [project_name]"
        )

    def execute(self, args: Dict[str, Any],
                context: Dict[str, Any]) -> Tuple[bool, str, Any]:
        try:
            project_name_filter = args.get('project_name')
            
            db_path = Path(__file__).parent.parent.parent / "data" / "petrophysics.db"
            if not db_path.exists():
                return False, "Database file not found", None
            
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            if project_name_filter:
                cursor.execute("""
                    SELECT project_name, well_name, updated_date
                    FROM wells
                    WHERE project_name = ?
                    ORDER BY updated_date DESC
                """, (project_name_filter,))
            else:
                cursor.execute("""
                    SELECT project_name, well_name, updated_date
                    FROM wells
                    ORDER BY updated_date DESC
                """)
            
            wells = cursor.fetchall()
            conn.close()
            
            if not wells:
                filter_msg = f" for project '{project_name_filter}'" if project_name_filter else ""
                return True, f"No wells found in database{filter_msg}", {'wells': []}
            
            filter_msg = f" (filtered by project: {project_name_filter})" if project_name_filter else ""
            message_parts = [f"Found {len(wells)} well(s) in database{filter_msg}:\n"]
            well_list = []
            
            for w in wells:
                project = w['project_name'] or "N/A"
                well = w['well_name'] or "N/A"
                updated = w['updated_date'] or "N/A"
                
                message_parts.append(f"  • {well} (Project: {project})")
                message_parts.append(f"    Updated: {updated}\n")
                
                well_list.append({
                    'well_name': well,
                    'project_name': project,
                    'updated_date': updated
                })
            
            return True, "\n".join(message_parts), {'wells': well_list, 'count': len(wells)}
            
        except Exception as e:
            return False, f"Error querying database: {str(e)}", None


class DBProjectInfoCommand(CLICommand):
    """Get detailed information about a specific project."""

    def __init__(self):
        super().__init__(
            "DB_PROJECT_INFO",
            "Get detailed information about a specific project. Usage: DB_PROJECT_INFO project_name"
        )

    def execute(self, args: Dict[str, Any],
                context: Dict[str, Any]) -> Tuple[bool, str, Any]:
        project_name = args.get('project_name')
        
        if not project_name:
            return False, "Missing required argument: project_name", None
        
        try:
            db_path = Path(__file__).parent.parent.parent / "data" / "petrophysics.db"
            if not db_path.exists():
                return False, "Database file not found", None
            
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT *
                FROM projects
                WHERE project_name = ?
            """, (project_name,))
            
            project = cursor.fetchone()
            
            if not project:
                conn.close()
                return False, f"Project '{project_name}' not found in database", None
            
            cursor.execute("""
                SELECT COUNT(*) as well_count
                FROM wells
                WHERE project_name = ?
            """, (project_name,))
            
            well_count_row = cursor.fetchone()
            well_count = well_count_row['well_count'] if well_count_row else 0
            
            conn.close()
            
            message_parts = [f"Project Information: {project_name}\n"]
            message_parts.append(f"  Path: {project['project_path']}")
            message_parts.append(f"  Session ID: {project['session_id']}")
            message_parts.append(f"  Active Well: {project['active_well'] or 'None'}")
            message_parts.append(f"  Wells in DB: {well_count}")
            message_parts.append(f"  Created: {project['created_at'] or 'N/A'}")
            message_parts.append(f"  Updated: {project['updated_at'] or 'N/A'}")
            
            return True, "\n".join(message_parts), {
                'project_name': project_name,
                'path': project['project_path'],
                'session_id': project['session_id'],
                'active_well': project['active_well'],
                'well_count': well_count,
                'created_at': project['created_at'],
                'updated_at': project['updated_at']
            }
            
        except Exception as e:
            return False, f"Error querying database: {str(e)}", None


class DBWellInfoCommand(CLICommand):
    """Get detailed information about a specific well."""

    def __init__(self):
        super().__init__(
            "DB_WELL_INFO",
            "Get detailed information about a specific well. Usage: DB_WELL_INFO well_name [project_name]"
        )

    def execute(self, args: Dict[str, Any],
                context: Dict[str, Any]) -> Tuple[bool, str, Any]:
        well_name = args.get('well_name')
        project_name = args.get('project_name')
        
        if not well_name:
            return False, "Missing required argument: well_name", None
        
        try:
            db_path = Path(__file__).parent.parent.parent / "data" / "petrophysics.db"
            if not db_path.exists():
                return False, "Database file not found", None
            
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            if project_name:
                cursor.execute("""
                    SELECT *
                    FROM wells
                    WHERE well_name = ? AND project_name = ?
                """, (well_name, project_name))
            else:
                cursor.execute("""
                    SELECT *
                    FROM wells
                    WHERE well_name = ?
                """, (well_name,))
            
            well = cursor.fetchone()
            conn.close()
            
            if not well:
                filter_msg = f" in project '{project_name}'" if project_name else ""
                return False, f"Well '{well_name}' not found in database{filter_msg}", None
            
            import json
            datasets = json.loads(well['datasets']) if well['datasets'] else {}
            dataset_list = datasets.get('datasets', [])
            
            message_parts = [f"Well Information: {well_name}\n"]
            message_parts.append(f"  Project: {well['project_name']}")
            message_parts.append(f"  Project Path: {well['project_path']}")
            message_parts.append(f"  Datasets: {len(dataset_list)}")
            
            if dataset_list:
                message_parts.append("\n  Dataset Details:")
                for ds in dataset_list[:5]:
                    ds_name = ds.get('name', 'N/A')
                    ds_type = ds.get('type', 'N/A')
                    log_count = len(ds.get('well_logs', []))
                    message_parts.append(f"    • {ds_name} ({ds_type}) - {log_count} logs")
                
                if len(dataset_list) > 5:
                    message_parts.append(f"    ... and {len(dataset_list) - 5} more")
            
            message_parts.append(f"\n  Updated: {well['updated_date'] or 'N/A'}")
            
            return True, "\n".join(message_parts), {
                'well_name': well_name,
                'project_name': well['project_name'],
                'project_path': well['project_path'],
                'dataset_count': len(dataset_list),
                'updated_date': well['updated_date']
            }
            
        except Exception as e:
            return False, f"Error querying database: {str(e)}", None


class DBStatsCommand(CLICommand):
    """Get database statistics."""

    def __init__(self):
        super().__init__(
            "DB_STATS",
            "Get overall database statistics. Usage: DB_STATS"
        )

    def execute(self, args: Dict[str, Any],
                context: Dict[str, Any]) -> Tuple[bool, str, Any]:
        try:
            db_path = Path(__file__).parent.parent.parent / "data" / "petrophysics.db"
            if not db_path.exists():
                return False, "Database file not found", None
            
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) as count FROM projects")
            project_count = cursor.fetchone()['count']
            
            cursor.execute("SELECT COUNT(*) as count FROM wells")
            well_count = cursor.fetchone()['count']
            
            cursor.execute("SELECT COUNT(*) as count FROM layouts")
            layout_count = cursor.fetchone()['count']
            
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row['name'] for row in cursor.fetchall()]
            
            file_size = db_path.stat().st_size
            file_size_mb = file_size / (1024 * 1024)
            
            conn.close()
            
            message_parts = ["SQLite Database Statistics:\n"]
            message_parts.append(f"  Database Path: {str(db_path)}")
            message_parts.append(f"  File Size: {file_size_mb:.2f} MB")
            message_parts.append(f"  Tables: {len(tables)}")
            message_parts.append(f"\nData Counts:")
            message_parts.append(f"  Projects: {project_count}")
            message_parts.append(f"  Wells: {well_count}")
            message_parts.append(f"  Layouts: {layout_count}")
            message_parts.append(f"\nTable List:")
            for table in tables:
                message_parts.append(f"  • {table}")
            
            return True, "\n".join(message_parts), {
                'db_path': str(db_path),
                'file_size_mb': file_size_mb,
                'project_count': project_count,
                'well_count': well_count,
                'layout_count': layout_count,
                'tables': tables
            }
            
        except Exception as e:
            return False, f"Error querying database: {str(e)}", None


class LoadMultipleDatasetsCommand(CLICommand):
    """Load multiple LAS files as separate datasets into a single well."""

    def __init__(self):
        super().__init__(
            "LOAD_MULTIPLE_DATASETS",
            "Load multiple LAS files as separate datasets into a single well. Usage: LOAD_MULTIPLE_DATASETS well_name folder_path"
        )

    def execute(self, args: Dict[str, Any],
                context: Dict[str, Any]) -> Tuple[bool, str, Any]:
        well_name = args.get('well_name')
        folder_path = args.get('folder_path')

        if not all([well_name, folder_path]):
            return False, "Missing required arguments: well_name, folder_path", None

        project_path = context.get('project_path')
        if not project_path:
            return False, "No project loaded", None

        # Make path absolute (relative paths are resolved from project directory)
        if not os.path.isabs(folder_path):
            folder_path = os.path.join(project_path, folder_path)

        folder_path = os.path.abspath(folder_path)

        # Verify folder exists
        if not os.path.exists(folder_path):
            return False, f"Folder not found: {folder_path}", None

        if not os.path.isdir(folder_path):
            return False, f"Path is not a directory: {folder_path}", None

        # Get list of LAS files
        las_files = sorted(
            [f for f in os.listdir(folder_path) if f.lower().endswith('.las')])

        if not las_files:
            return False, f"No LAS files found in folder: {folder_path}", None

        # Check if well exists, create if it doesn't
        well_path = os.path.join(project_path, '10-WELLS', f'{well_name}.ptrc')
        well_created = False

        try:
            if os.path.exists(well_path):
                well = Well.deserialize(well_path)
            else:
                # Create new well
                well = Well(date_created=datetime.now(),
                            well_name=well_name,
                            well_type='Dev',
                            datasets=[])
                well_created = True

            # Process each LAS file and add as a dataset with suffix
            imported_files = []
            failed_files = []
            datasets_added = 0

            for idx, las_file in enumerate(las_files, start=1):
                las_file_path = os.path.join(folder_path, las_file)
                suffix = str(idx)

                try:
                    # Check file size (500 MB limit)
                    MAX_FILE_SIZE = 500 * 1024 * 1024  # 500 MB
                    file_size = os.path.getsize(las_file_path)

                    if file_size > MAX_FILE_SIZE:
                        failed_files.append((
                            las_file,
                            f"File too large: {file_size / (1024 * 1024):.2f} MB"
                        ))
                        continue

                    # Read the LAS file to get datasets
                    datasets = read_las_file(las_file_path)

                    # Add each dataset to the well with suffix
                    for dataset in datasets:
                        # Apply suffix to dataset name
                        dataset.name = f"{dataset.name}_{suffix}"
                        dataset.wellname = well_name

                        # Add suffix to all well log dtst fields
                        for log in dataset.well_logs:
                            if log.dtst:
                                log.dtst = f"{log.dtst}_{suffix}"
                            else:
                                log.dtst = f"WIRE_{suffix}"

                        # Add dataset to well
                        well.add_dataset(dataset)
                        datasets_added += 1

                    imported_files.append(las_file)

                except Exception as e:
                    failed_files.append((las_file, str(e)))
                    continue

            # Save the well
            if datasets_added > 0:
                os.makedirs(os.path.dirname(well_path), exist_ok=True)
                well.serialize(well_path)
            else:
                return False, "No datasets were successfully imported", None

            # Build status message
            status_parts = []

            if well_created:
                status_parts.append(f"✓ Created new well '{well_name}'")
            else:
                status_parts.append(f"✓ Updated existing well '{well_name}'")

            status_parts.append(
                f"✓ Loaded {datasets_added} dataset(s) from {len(imported_files)} LAS file(s)"
            )

            if imported_files:
                status_parts.append(
                    f"  Files imported: {', '.join(imported_files)}")

            if failed_files:
                status_parts.append(f"  Failed: {len(failed_files)} file(s)")
                for file, error in failed_files[:3]:  # Show first 3 errors
                    status_parts.append(f"    - {file}: {error}")

            status_msg = "\n".join(status_parts)

            return True, status_msg, {
                'well_name': well_name,
                'well_created': well_created,
                'datasets_added': datasets_added,
                'files_imported': imported_files,
                'files_failed': failed_files,
                'folder': folder_path
            }

        except Exception as e:
            return False, f"Error loading datasets: {str(e)}", None


class CLIService:
    """Service for executing CLI commands."""

    def __init__(self):
        self.commands: Dict[str, CLICommand] = {}
        self._register_commands()

    def _register_commands(self):
        """Register all available commands."""
        commands = [
            InsertConstantCommand(),
            InsertLogCommand(),
            CreateEmptyWellCommand(),
            DeleteDatasetCommand(),
            ImportLasFileCommand(),
            ImportLasFilesFromFolderCommand(),
            LoadTopsCommand(),
            LoadTopsBulkCommand(),
            ExportTopsCommand(),
            ExportToLasCommand(),
            SelectWellsCommand(),
            ActiveWellCommand(),
            ListAllWellsCommand(),
            ListOfDatasetCommand(),
            FindWithDatasetCommand(),
            DeleteWellCommand(),
            DBListProjectsCommand(),
            DBListWellsCommand(),
            DBProjectInfoCommand(),
            DBWellInfoCommand(),
            DBStatsCommand(),
            LoadMultipleDatasetsCommand(),
        ]

        for cmd in commands:
            self.commands[cmd.name] = cmd

    def parse_command(
            self, command_str: str) -> Tuple[Optional[str], Dict[str, Any]]:
        """
        Parse a command string into command name and arguments.
        
        Example:
            "INSERT_CONSTANT well1 API_GRAVITY 45.2 API 'Oil gravity'"
            -> ('INSERT_CONSTANT', {'well_name': 'well1', 'const_name': 'API_GRAVITY', 
                'value': '45.2', 'unit': 'API', 'description': 'Oil gravity'})
        """
        parts = self._split_command(command_str)

        if not parts:
            return None, {}

        cmd_name = parts[0].upper()

        if cmd_name not in self.commands:
            return None, {}

        args = {}

        if cmd_name == "INSERT_CONSTANT":
            if len(parts) >= 4:
                args = {
                    'well_name': parts[1],
                    'const_name': parts[2],
                    'value': parts[3],
                    'unit': parts[4] if len(parts) > 4 else '',
                    'description': parts[5] if len(parts) > 5 else ''
                }

        elif cmd_name == "INSERT_LOG":
            if len(parts) >= 3:
                args = {
                    'well_name': parts[1],
                    'log_name': parts[2],
                    'unit': parts[3] if len(parts) > 3 else '',
                    'description': parts[4] if len(parts) > 4 else ''
                }

        elif cmd_name == "CREATE_EMPTY_WELL":
            if len(parts) >= 2:
                args = {
                    'well_name': parts[1],
                    'well_type': parts[2] if len(parts) > 2 else 'Dev'
                }

        elif cmd_name == "DELETE_DATASET":
            if len(parts) >= 3:
                args = {'well_name': parts[1], 'dataset_name': parts[2]}

        elif cmd_name == "IMPORT_LAS_FILE":
            if len(parts) >= 2:
                # Support both formats:
                # IMPORT_LAS_FILE las_file_path [suffix]  (well_name extracted from LAS)
                # IMPORT_LAS_FILE well_name las_file_path [suffix]
                if len(parts) == 2:
                    # Only file path provided
                    args = {'las_file_path': parts[1], 'suffix': ''}
                else:
                    # well_name and las_file_path provided
                    args = {
                        'well_name': parts[1],
                        'las_file_path': parts[2],
                        'suffix': parts[3] if len(parts) > 3 else ''
                    }

        elif cmd_name == "IMPORT_LAS_FILES_FROM_FOLDER":
            if len(parts) >= 2:
                # Support both formats:
                # IMPORT_LAS_FILES_FROM_FOLDER folder_path  (well_name extracted from first LAS)
                # IMPORT_LAS_FILES_FROM_FOLDER well_name folder_path
                if len(parts) == 2:
                    # Only folder path provided
                    args = {'folder_path': parts[1]}
                else:
                    # well_name and folder_path provided
                    args = {'well_name': parts[1], 'folder_path': parts[2]}

        elif cmd_name == "LOAD_TOPS":
            if len(parts) >= 3:
                args = {'well_name': parts[1], 'csv_file_path': parts[2]}

        elif cmd_name == "LOAD_TOPS_BULK":
            if len(parts) >= 2:
                args = {'csv_file_path': parts[1]}

        elif cmd_name == "EXPORT_TOPS":
            if len(parts) >= 3:
                args = {'well_name': parts[1], 'output_csv_path': parts[2]}

        elif cmd_name == "EXPORT_TO_LAS":
            if len(parts) >= 4:
                args = {
                    'well_name': parts[1],
                    'dataset_name': parts[2],
                    'output_las_path': parts[3]
                }

        elif cmd_name == "SELECT_WELLS":
            if len(parts) >= 2:
                args = {'well_names': parts[1:]}

        elif cmd_name == "ACTIVE_WELL":
            if len(parts) >= 2:
                args = {'well_name': parts[1]}

        elif cmd_name == "LIST_ALL_WELLS":
            # No arguments needed
            args = {}

        elif cmd_name == "LIST_OF_DATASET":
            if len(parts) >= 2:
                args = {'well_name': parts[1]}

        elif cmd_name == "FIND_WITH_DATASET":
            if len(parts) >= 2:
                args = {'dataset_name': parts[1]}

        elif cmd_name == "DELETE_WELL":
            if len(parts) >= 2:
                args = {'well_name': parts[1]}

        elif cmd_name == "DB_LIST_PROJECTS":
            # No arguments needed
            args = {}

        elif cmd_name == "DB_LIST_WELLS":
            # Optional project_name filter
            if len(parts) >= 2:
                args = {'project_name': parts[1]}
            else:
                args = {}

        elif cmd_name == "DB_PROJECT_INFO":
            if len(parts) >= 2:
                args = {'project_name': parts[1]}

        elif cmd_name == "DB_WELL_INFO":
            if len(parts) >= 2:
                args = {'well_name': parts[1]}
                if len(parts) >= 3:
                    args['project_name'] = parts[2]

        elif cmd_name == "DB_STATS":
            # No arguments needed
            args = {}

        elif cmd_name == "LOAD_MULTIPLE_DATASETS":
            if len(parts) >= 3:
                args = {'well_name': parts[1], 'folder_path': parts[2]}

        return cmd_name, args

    def _split_command(self, command_str: str) -> List[str]:
        """Split command string preserving quoted strings."""
        pattern = r'''(?:[^\s"']+|"[^"]*"|'[^']*')+'''
        parts = re.findall(pattern, command_str)
        return [p.strip('"\'') for p in parts]

    def execute(self, command_str: str,
                context: Dict[str, Any]) -> Tuple[bool, str, Any]:
        """
        Execute a command string.
        
        Args:
            command_str: Command string to execute
            context: Execution context (project_path, current_well, etc.)
            
        Returns:
            Tuple of (success, message, result_data)
        """
        command_str = command_str.strip()

        if not command_str:
            return False, "Empty command", None

        cmd_name, args = self.parse_command(command_str)

        if not cmd_name:
            return False, f"Unknown command. Available commands: {', '.join(self.commands.keys())}", None

        if cmd_name not in self.commands:
            return False, f"Command '{cmd_name}' not found", None

        # Add delete permission to args if executing DELETE_WELL command
        if cmd_name == "DELETE_WELL":
            args['delete_permission_enabled'] = context.get(
                'delete_permission_enabled', False)

        command = self.commands[cmd_name]

        return command.execute(args, context)

    def get_help(self, command_name: Optional[str] = None) -> str:
        """Get help text for a command or all commands."""
        if command_name:
            cmd = self.commands.get(command_name.upper())
            if cmd:
                return cmd.description
            return f"Unknown command: {command_name}"

        help_text = "Available commands:\n\n"
        for cmd in self.commands.values():
            help_text += f"  {cmd.name}:\n    {cmd.description}\n\n"

        return help_text


cli_service = CLIService()
