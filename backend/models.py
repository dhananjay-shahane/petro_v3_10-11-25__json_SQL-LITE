from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Any
from datetime import datetime


class CustomBase(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        validate_assignment=True,
        str_strip_whitespace=True
    )


class WorkspaceInfo(CustomBase):
    workspaceRoot: str
    absolutePath: str
    exists: bool
    currentProjectPath: Optional[str] = None
    currentProjectName: Optional[str] = None
    hasOpenProject: bool = False


class ProjectCreate(CustomBase):
    name: str = Field(min_length=1)
    path: Optional[str] = None


class ProjectResponse(CustomBase):
    success: bool
    message: str
    projectPath: str
    projectName: str


class DirectoryItem(CustomBase):
    name: str
    path: str


class DirectoryListResponse(CustomBase):
    currentPath: str
    parentPath: str
    directories: List[DirectoryItem]
    canGoUp: bool


class DirectoryCreate(CustomBase):
    parentPath: str
    folderName: str = Field(min_length=1)


class DirectoryDelete(CustomBase):
    folderPath: str = Field(min_length=1)


class DirectoryRename(CustomBase):
    folderPath: str = Field(min_length=1)
    newName: str = Field(min_length=1)


class DirectoryResponse(CustomBase):
    success: bool
    message: str
    path: str
    name: Optional[str] = None
    oldPath: Optional[str] = None
    newPath: Optional[str] = None
    newName: Optional[str] = None


class DataItem(CustomBase):
    name: str
    path: str
    type: str
    hasFiles: bool = False


class DataListResponse(CustomBase):
    currentPath: str
    parentPath: str
    items: List[DataItem]
    canGoUp: bool


class FileContentResponse(CustomBase):
    content: Any


class LASPreviewRequest(CustomBase):
    lasContent: str
    filename: Optional[str] = "UNKNOWN"


class LASPreviewResponse(CustomBase):
    wellName: str
    uwi: Optional[str] = ""
    company: Optional[str] = ""
    field: Optional[str] = ""
    location: Optional[str] = ""
    startDepth: Optional[float] = None
    stopDepth: Optional[float] = None
    step: Optional[float] = None
    curveNames: List[str]
    dataPoints: int


class LogMessage(CustomBase):
    message: str
    type: str


class WellInfo(CustomBase):
    id: str
    name: str
    type: str


class WellCreateResponse(CustomBase):
    success: bool
    message: str
    well: WellInfo
    filePath: str
    lasFilePath: str
    logs: List[LogMessage]


class WellLogInfo(CustomBase):
    name: str
    date: str
    description: str
    dataset: Optional[str] = None
    dtst: Optional[str] = None
    interpolation: str
    logType: Optional[str] = None
    log_type: Optional[str] = None
    values: Optional[List[Any]] = None
    log: Optional[List[Any]] = None


class ConstantInfo(CustomBase):
    name: str
    value: Any
    tag: str


class DatasetInfo(CustomBase):
    name: str
    type: str
    wellname: Optional[str] = None
    indexName: Optional[str] = "DEPTH"
    index_name: Optional[str] = "DEPTH"
    index_log: Optional[List[Any]] = []
    logs: Optional[List[WellLogInfo]] = []
    well_logs: Optional[List[WellLogInfo]] = []
    constants: List[ConstantInfo] = []
    date_created: Optional[str] = None
    description: Optional[str] = None


class WellData(CustomBase):
    name: str
    type: str
    dateCreated: str
    datasets: List[DatasetInfo]


class WellLoadResponse(CustomBase):
    success: bool
    well: WellData


class WellDataResponse(CustomBase):
    success: bool
    datasets: List[DatasetInfo]


class DatasetDetailsResponse(CustomBase):
    success: bool
    dataset: DatasetInfo


class WellListItem(CustomBase):
    id: str
    name: str
    type: str
    path: str
    created_at: Optional[str] = None
    datasets: int


class WellListResponse(CustomBase):
    wells: List[WellListItem]


class SessionProjectSave(CustomBase):
    projectPath: str
    projectName: Optional[str] = None
    createdAt: Optional[str] = None


class SessionProjectResponse(CustomBase):
    success: bool
    hasProject: Optional[bool] = None
    projectPath: Optional[str] = None
    projectName: Optional[str] = None
    createdAt: Optional[str] = None
    message: Optional[str] = None


class WellDatasetsResponse(CustomBase):
    success: bool
    wellName: str
    datasets: List[DatasetInfo]


class LogPlotRequest(CustomBase):
    projectPath: str
    logNames: List[str] = Field(min_length=1)
    layoutName: Optional[str] = None  # Optional XML layout name (e.g., "perfs_cpi_logplot_layout")


class LogPlotResponse(CustomBase):
    success: bool
    plotly_json: Optional[str] = None
    image: Optional[str] = None
    format: str
    encoding: Optional[str] = None
    logs: List[str]


class CrossPlotRequest(CustomBase):
    projectPath: str
    xLog: str
    yLog: str


class CrossPlotResponse(CustomBase):
    success: bool
    image: str
    format: str
    encoding: str
    logs: List[str]


class ErrorResponse(CustomBase):
    error: str
    logs: Optional[List[LogMessage]] = None


class SessionCreateRequest(CustomBase):
    projectPath: str
    wellNames: List[str] = Field(min_length=1)


class SessionCreateResponse(CustomBase):
    success: bool
    sessionId: str
    message: str
    loadedWells: dict
    summary: dict


class SessionInfoResponse(CustomBase):
    success: bool
    sessionId: str
    exists: bool
    ttl: Optional[int] = None
    summary: Optional[dict] = None


class SessionUpdateRequest(CustomBase):
    wellName: str
    action: str
    data: Optional[dict] = None


class SessionUpdateResponse(CustomBase):
    success: bool
    message: str
    wellName: str


class SessionCommitResponse(CustomBase):
    success: bool
    message: str
    savedWells: dict
    summary: dict


class LayoutSaveRequest(CustomBase):
    projectPath: str
    layout: dict
    visiblePanels: List[str]
    layoutName: Optional[str] = "default"
    windowLinks: Optional[dict] = None
    fontSizes: Optional[dict] = None


class LayoutResponse(CustomBase):
    success: bool
    layout: Optional[dict] = None
    visiblePanels: Optional[List[str]] = None
    windowLinks: Optional[dict] = None
    fontSizes: Optional[dict] = None
    message: Optional[str] = None


class LayoutListResponse(CustomBase):
    success: bool
    layouts: List[str]
    message: Optional[str] = None
