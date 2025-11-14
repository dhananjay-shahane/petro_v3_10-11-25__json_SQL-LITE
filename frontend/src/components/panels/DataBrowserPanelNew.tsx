import { Button } from "@/components/ui/button";
import { useState, useEffect, useMemo, useCallback } from "react";
import { WellData } from "../workspace/Workspace";
import axios from "axios";
import { useToast } from "@/hooks/use-toast";
import { LinkIcon, Unlink, ChevronDown, ChevronRight } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import LogValuesVirtualTable from "./LogValuesVirtualTable";

interface WellLog {
  name: string;
  date: string;
  description: string;
  dtst: string;
  interpolation: string;
  log_type: string;
  log: any[];
}

interface Constant {
  name: string;
  value: any;
  tag: string;
}

interface Dataset {
  name: string;
  type: string;
  wellname: string;
  well_logs: WellLog[];
  constants: Constant[];
  index_log: any[];
  index_name: string;
}

export default function DataBrowserPanelNew({
  selectedWell,
  projectPath,
  onGeneratePlot,
  selectedDataset: selectedDatasetProp,
  onDatasetSelect,
  isLocked,
  onToggleLock,
  onRequestWellRefresh,
}: {
  selectedWell?: WellData | null;
  projectPath?: string;
  onGeneratePlot?: (logNames: string[]) => void;
  selectedDataset?: Dataset | null;
  onDatasetSelect?: (dataset: Dataset) => void;
  isLocked?: boolean;
  onToggleLock?: () => void;
  onRequestWellRefresh?: (wellName: string) => Promise<void>;
}) {
  const { toast } = useToast();
  const [activeTab, setActiveTab] = useState("logs");
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [selectedDataset, setSelectedDataset] = useState<Dataset | null>(null);
  const [expandedTypes, setExpandedTypes] = useState<Set<string>>(
    new Set(["Special", "Point", "Continuous", "Tops"]),
  );
  const [checkedLogs, setCheckedLogs] = useState<Set<string>>(new Set());
  const [checkedConstants, setCheckedConstants] = useState<Set<string>>(
    new Set(),
  );

  // Dialog states
  const [showAddLogDialog, setShowAddLogDialog] = useState(false);
  const [showAddConstantDialog, setShowAddConstantDialog] = useState(false);
  const [newLogName, setNewLogName] = useState("");
  const [newLogDescription, setNewLogDescription] = useState("");
  const [newLogType, setNewLogType] = useState("float");
  const [newConstantName, setNewConstantName] = useState("");
  const [newConstantValue, setNewConstantValue] = useState("");
  const [newConstantTag, setNewConstantTag] = useState("");

  const DATASET_COLORS = {
    Special: "bg-orange-100 dark:bg-orange-900/30",
    Point: "bg-green-100 dark:bg-green-900/30",
    Continuous: "bg-blue-100 dark:bg-blue-900/30",
    Tops: "bg-purple-100 dark:bg-purple-900/30",
  };

  useEffect(() => {
    const abortController = new AbortController();
    let timeoutId: NodeJS.Timeout | null = null;
    let isTimeout = false;

    // ALWAYS clear data immediately when well or project changes to prevent stale data
    setDatasets([]);
    setSelectedDataset(null);
    setCheckedLogs(new Set());
    setCheckedConstants(new Set());

    // Early exit if no well selected
    if (!selectedWell?.path) {
      return;
    }

    // Critical check: verify the well belongs to the current project BEFORE fetching data
    if (selectedWell.path && projectPath) {
      const wellBelongsToProject =
        selectedWell.path === projectPath ||
        selectedWell.path.startsWith(projectPath + "/") ||
        selectedWell.path.startsWith(projectPath + "\\");

      if (!wellBelongsToProject) {
        console.log(
          "[DataBrowser] Well doesn't belong to current project - clearing and returning. Well path:",
          selectedWell.path,
          "Project path:",
          projectPath,
        );
        return;
      }
    }

    // Use datasets from Workspace if already loaded (avoids duplicate API call)
    // Check for timestamp to confirm data was actually fetched (handles empty dataset arrays correctly)
    const hasLoadedData =
      (selectedWell as any)?._dataLoadTimestamp ||
      (selectedWell as any)?._refreshTimestamp;
    const hasDatasets = Array.isArray((selectedWell as any).datasets);

    console.log("[DataBrowser] Debug:", {
      wellName: selectedWell?.name,
      hasLoadedData,
      hasDatasets,
      datasetCount: hasDatasets ? (selectedWell as any).datasets.length : 0,
      timestamp: hasLoadedData,
    });

    if (hasLoadedData && hasDatasets) {
      console.log(
        "[DataBrowser] ✅ Using datasets from Workspace (already loaded in memory)",
      );
      const wellDatasets = (selectedWell as any).datasets as Dataset[];
      setDatasets(wellDatasets);

      // Select dataset with priority: selectedDatasetProp → first dataset
      if (selectedDatasetProp) {
        setSelectedDataset(selectedDatasetProp);
      } else if (wellDatasets.length > 0) {
        setSelectedDataset(wellDatasets[0]);
      }

      return; // Skip API fetch - data already available from Workspace
    }

    console.log(
      "[DataBrowser] ⚠️ Datasets not available from Workspace, fetching from API...",
    );

    const loadWellData = async () => {
      if (!selectedWell?.path) {
        return;
      }

      try {
        // Set up timeout for large datasets (5 minutes)
        timeoutId = setTimeout(() => {
          isTimeout = true;
          abortController.abort();
        }, 300000);

        const response = await fetch(
          `/api/wells/data?wellPath=${encodeURIComponent(selectedWell.path)}`,
          { signal: abortController.signal },
        );

        // Clear timeout on successful response
        if (timeoutId) clearTimeout(timeoutId);

        const contentType = response.headers.get("content-type");
        if (contentType && contentType.includes("application/json")) {
          const data = await response.json();

          if (response.ok && data.datasets && Array.isArray(data.datasets)) {
            setDatasets(data.datasets);
            if (data.datasets.length > 0) {
              setSelectedDataset(data.datasets[0]);
            }
          } else if (!response.ok) {
            console.error(
              "Error loading well data:",
              data.error || "Unknown error",
            );
            toast({
              title: "Error loading well data",
              description: data.error || "Failed to load well datasets",
              variant: "destructive",
            });
          }
        } else {
          const text = await response.text();
          console.error(
            "Error loading well data: Server returned non-JSON response",
            text.substring(0, 100),
          );
        }
      } catch (error: any) {
        // Clear timeout on error
        if (timeoutId) clearTimeout(timeoutId);

        if (error.name === "AbortError" && isTimeout) {
          console.error("Error loading well data: Request timed out");
          toast({
            title: "Timeout Error",
            description:
              "Loading well data took too long. The dataset may be very large.",
            variant: "destructive",
          });
        } else if (error.name === "AbortError") {
          // Silently ignore - request was aborted when switching wells (expected behavior)
          return;
        } else {
          console.error("Error loading well data:", error);
          toast({
            title: "Error",
            description: "Failed to load well data. Please try again.",
            variant: "destructive",
          });
        }
      }
    };

    loadWellData();

    return () => {
      if (timeoutId) clearTimeout(timeoutId);
      abortController.abort();
    };
  }, [
    selectedWell,
    projectPath,
    (selectedWell as any)?._dataLoadTimestamp,
    (selectedWell as any)?._refreshTimestamp,
  ]);

  const tabs = [
    { id: "logs", label: "Logs" },
    { id: "logValues", label: "Log Values" },
    { id: "constants", label: "Constants" },
  ];

  const groupedDatasets = useMemo(() => {
    return datasets.reduce(
      (acc, dataset) => {
        if (!acc[dataset.type]) {
          acc[dataset.type] = [];
        }
        acc[dataset.type].push(dataset);
        return acc;
      },
      {} as Record<string, Dataset[]>,
    );
  }, [datasets]);

  const toggleType = (type: string) => {
    const newExpanded = new Set(expandedTypes);
    if (newExpanded.has(type)) {
      newExpanded.delete(type);
    } else {
      newExpanded.add(type);
    }
    setExpandedTypes(newExpanded);
  };

  const handleDatasetClick = useCallback(
    (dataset: Dataset) => {
      setSelectedDataset(dataset);
      setCheckedLogs(new Set());
      setCheckedConstants(new Set());

      // Log dataset selection to feedback panel
      const wellName = selectedWell?.name || "Unknown well";
      const message = `Data Browser: Selected dataset "${dataset.name}" (${dataset.type}) for well "${wellName}"`;
      if ((window as any).addAppLog) {
        (window as any).addAppLog(message, "info");
      }
      console.log(`[DataBrowser] ${message}`);
    },
    [selectedWell?.name],
  );

  const handleLogCheckboxChange = useCallback((logName: string) => {
    setCheckedLogs((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(logName)) {
        newSet.delete(logName);
      } else {
        newSet.add(logName);
      }
      console.log("[DataBrowser] Checked logs:", Array.from(newSet));
      return newSet;
    });
  }, []);

  // Notify parent when dataset selection changes (moved to useEffect to avoid setState during render warning)
  useEffect(() => {
    if (selectedDataset && onDatasetSelect) {
      onDatasetSelect(selectedDataset);
    }
  }, [selectedDataset, onDatasetSelect]);

  // Auto-generate plot when logs are selected (moved to useEffect to avoid setState during render warning)
  useEffect(() => {
    const selectedLogNames = Array.from(checkedLogs);
    if (selectedLogNames.length > 0 && onGeneratePlot) {
      console.log("[DataBrowser] Auto-generating plot for:", selectedLogNames);
      onGeneratePlot(selectedLogNames);
    }
  }, [checkedLogs, onGeneratePlot]);

  const handleConstantCheckboxChange = useCallback((constantName: string) => {
    setCheckedConstants((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(constantName)) {
        newSet.delete(constantName);
      } else {
        newSet.add(constantName);
      }
      return newSet;
    });
  }, []);

  const handleGeneratePlot = useCallback(() => {
    const selectedLogNames = Array.from(checkedLogs);
    console.log(
      "[DataBrowser] Generate plot clicked with logs:",
      selectedLogNames,
    );
    if (selectedLogNames.length > 0 && onGeneratePlot) {
      onGeneratePlot(selectedLogNames);
    } else {
      console.log(
        "[DataBrowser] Cannot generate: no logs selected or no callback",
      );
    }
  }, [checkedLogs, onGeneratePlot]);

  const handleAddLog = async () => {
    if (!selectedWell || !projectPath) {
      toast({
        title: "Cannot Add Log",
        description: "No well selected",
        variant: "destructive",
      });
      return;
    }

    if (!newLogName.trim()) {
      toast({
        title: "Validation Error",
        description: "Log name is required",
        variant: "destructive",
      });
      return;
    }

    try {
      const command = `INSERT_LOG ${selectedWell.name} ${newLogName} "${newLogDescription}" ${newLogType}`;
      const response = await axios.post("/api/cli/execute", {
        command,
        projectPath,
      });

      if (response.data.success) {
        toast({
          title: "Log Added",
          description: `Log '${newLogName}' has been added`,
        });

        // Reset form
        setNewLogName("");
        setNewLogDescription("");
        setNewLogType("float");
        setShowAddLogDialog(false);

        // Request Workspace to refresh well data
        if (onRequestWellRefresh) {
          await onRequestWellRefresh(selectedWell.name);
        }
      } else {
        toast({
          title: "Add Failed",
          description: response.data.message || "Unknown error",
          variant: "destructive",
        });
      }
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.message || "Failed to add log",
        variant: "destructive",
      });
    }
  };

  const handleAddConstant = async () => {
    if (!selectedWell || !projectPath) {
      toast({
        title: "Cannot Add Constant",
        description: "No well selected",
        variant: "destructive",
      });
      return;
    }

    if (!newConstantName.trim() || !newConstantValue.trim()) {
      toast({
        title: "Validation Error",
        description: "Constant name and value are required",
        variant: "destructive",
      });
      return;
    }

    try {
      const command = `INSERT_CONSTANT ${selectedWell.name} ${newConstantName} ${newConstantValue} ${newConstantTag} "${newConstantTag}"`;
      const response = await axios.post("/api/cli/execute", {
        command,
        projectPath,
      });

      if (response.data.success) {
        toast({
          title: "Constant Added",
          description: `Constant '${newConstantName}' has been added`,
        });

        // Reset form
        setNewConstantName("");
        setNewConstantValue("");
        setNewConstantTag("");
        setShowAddConstantDialog(false);

        // Request Workspace to refresh well data
        if (onRequestWellRefresh) {
          await onRequestWellRefresh(selectedWell.name);
        }
      } else {
        toast({
          title: "Add Failed",
          description: response.data.message || "Unknown error",
          variant: "destructive",
        });
      }
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.message || "Failed to add constant",
        variant: "destructive",
      });
    }
  };

  const handleAdd = () => {
    if (activeTab === "logs") {
      setShowAddLogDialog(true);
    } else if (activeTab === "constants") {
      setShowAddConstantDialog(true);
    }
  };

  const handleExport = async () => {
    if (!selectedWell || !projectPath || !selectedDataset) {
      toast({
        title: "Cannot Export",
        description: "Please select a dataset to export",
        variant: "destructive",
      });
      return;
    }

    try {
      let command: string;
      let outputPath: string;
      let fileExtension: string;

      // Check if this is a TOPS dataset
      const isTopsDataset =
        selectedDataset.type === "Tops" ||
        selectedDataset.type === "Point" ||
        selectedDataset.name === "TOPS";

      if (isTopsDataset) {
        // Export TOPS to CSV
        fileExtension = "csv";
        outputPath = `04-OUTPUT/${selectedWell.name}_${selectedDataset.name}.csv`;
        command = `EXPORT_TOPS ${selectedWell.name} ${outputPath}`;
      } else {
        // Export regular dataset to LAS
        fileExtension = "las";
        outputPath = `04-OUTPUT/${selectedWell.name}_${selectedDataset.name}.las`;
        command = `EXPORT_TO_LAS ${selectedWell.name} ${selectedDataset.name} ${outputPath}`;
      }

      const response = await axios.post("/api/cli/execute", {
        command,
        projectPath,
      });

      if (response.data.success) {
        toast({
          title: "Export Successful",
          description: `Dataset exported to ${outputPath}`,
        });
      } else {
        toast({
          title: "Export Failed",
          description: response.data.message || "Unknown error",
          variant: "destructive",
        });
      }
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.message || "Failed to export dataset",
        variant: "destructive",
      });
    }
  };

  const renderLogsTab = () => {
    if (!selectedDataset?.well_logs) {
      return (
        <div className="text-center text-muted-foreground py-8">
          No logs available
        </div>
      );
    }

    return (
      <table className="w-full max-w-24">
        <thead className="sticky top-0 bg-muted dark:bg-card border-b border-border">
          <tr className="h-10">
            <th className="w-8 px-2"></th>
            <th className="px-4 py-2 text-left font-semibold text-foreground">
              Name
            </th>
            <th className="px-4 py-2 text-left font-semibold text-foreground">
              Date
            </th>
            <th className="px-4 py-2 text-left font-semibold text-foreground">
              Description
            </th>
            <th className="px-4 py-2 text-left font-semibold text-foreground">
              DTST
            </th>
            <th className="px-4 py-2 text-left font-semibold text-foreground">
              Interpolation
            </th>
            <th className="px-4 py-2 text-left font-semibold text-foreground">
              Type
            </th>
          </tr>
        </thead>
        <tbody>
          {selectedDataset.well_logs.map((log, index) => (
            <tr key={index} className="border-b border-border hover:bg-accent">
              <td className="px-2">
                <input
                  type="checkbox"
                  className="cursor-pointer"
                  checked={checkedLogs.has(log.name)}
                  onChange={() => handleLogCheckboxChange(log.name)}
                />
              </td>
              <td
                className="px-4 py-2 text-foreground cursor-move hover:bg-primary/10"
                draggable={true}
                onDragStart={(e) => {
                  e.dataTransfer.effectAllowed = "copy";
                  e.dataTransfer.setData("application/x-log-name", log.name);
                  e.dataTransfer.setData("text/plain", log.name);
                }}
                title="Drag to Well Log Plot to add"
              >
                {log.name}
              </td>
              <td className="px-4 py-2 text-foreground">{log.date}</td>
              <td className="px-4 py-2 text-foreground">{log.description}</td>
              <td className="px-4 py-2 text-foreground">{log.dtst}</td>
              <td className="px-4 py-2 text-foreground">{log.interpolation}</td>
              <td className="px-4 py-2 text-foreground">{log.log_type}</td>
            </tr>
          ))}
        </tbody>
      </table>
    );
  };

  const renderLogValuesTab = () => {
    if (!selectedDataset?.well_logs || selectedDataset.well_logs.length === 0) {
      return (
        <div className="text-center text-muted-foreground py-8">
          No log values available
        </div>
      );
    }

    const logs = selectedDataset?.well_logs ?? [];
    const numReadings = logs.length > 0
      ? Math.max(...logs.map(log => log.log?.length || 0), 0)
      : 0;

    return (
      <LogValuesVirtualTable
        logs={logs}
        rowCount={numReadings}
        height={600}
      />
    );
  };

  const renderConstantsTab = () => {
    if (!selectedDataset?.constants || selectedDataset.constants.length === 0) {
      return (
        <div className="text-center text-muted-foreground py-8">
          No constants available
        </div>
      );
    }

    return (
      <table className="w-full">
        <thead className="sticky top-0 bg-muted dark:bg-card border-b border-border">
          <tr className="h-10">
            <th className="w-8 px-2"></th>
            <th className="px-4 py-2 text-left font-semibold text-foreground">
              Name
            </th>
            <th className="px-4 py-2 text-left font-semibold text-foreground">
              Value
            </th>
            <th className="px-4 py-2 text-left font-semibold text-foreground">
              Tag
            </th>
          </tr>
        </thead>
        <tbody>
          {selectedDataset.constants.map((constant, index) => (
            <tr key={index} className="border-b border-border hover:bg-accent">
              <td className="px-2">
                <input
                  type="checkbox"
                  className="cursor-pointer"
                  checked={checkedConstants.has(constant.name)}
                  onChange={() => handleConstantCheckboxChange(constant.name)}
                />
              </td>
              <td className="px-4 py-2 text-foreground">{constant.name}</td>
              <td className="px-4 py-2 text-foreground">{constant.value}</td>
              <td className="px-4 py-2 text-foreground">{constant.tag}</td>
            </tr>
          ))}
        </tbody>
      </table>
    );
  };

  const wellBelongsToProject =
    selectedWell &&
    selectedWell.path &&
    projectPath &&
    (selectedWell.path === projectPath ||
      selectedWell.path.startsWith(projectPath + "/") ||
      selectedWell.path.startsWith(projectPath + "\\"));

  // Show empty state when no well is selected
  if (!selectedWell || !wellBelongsToProject) {
    return (
      <div className="flex h-full items-center justify-center bg-muted/20">
        <div className="text-center p-8">
          <div className="text-6xl mb-4 text-muted-foreground/40">📊</div>
          <h3 className="text-lg font-medium text-foreground mb-2">
            No Well Selected
          </h3>
          <p className="text-sm text-muted-foreground max-w-md">
            Please select a well from the Wells panel to view its data, logs,
            and constants.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div
      className="flex h-full overflow-scroll"
      style={{ fontSize: "var(--font-size-data-browser, 14px)" }}
    >
      <div className="w-64 border-r border-border bg-muted dark:bg-card/50 flex flex-col">
        <div className="p-3 border-b border-border">
          <div className="flex items-center justify-between gap-2">
            <div className="font-medium text-foreground truncate">
              {selectedWell.name}
            </div>
            {onToggleLock && (
              <button
                onClick={onToggleLock}
                className="flex items-center gap-1 px-2 py-1 text-xs rounded-md border border-border hover:border-foreground/30 transition-colors shrink-0 group"
                title={
                  isLocked
                    ? "Linked - Follows global well selection. Click to unlink"
                    : "Unlinked - Stays on current well. Click to link"
                }
              >
                <span
                  key={isLocked ? "linked" : "unlinked"}
                  className="inline-block animate-in fade-in zoom-in duration-300"
                  style={{
                    animation: "spin-scale 0.5s ease-out",
                  }}
                >
                  {isLocked ? (
                    <LinkIcon className="w-4 h-4 text-green-500 group-hover:scale-110 transition-transform" />
                  ) : (
                    <Unlink className="w-4 h-4 text-gray-500 group-hover:scale-110 transition-transform" />
                  )}
                </span>
              </button>
            )}
          </div>
        </div>

        <div className="flex-1 overflow-auto p-3 space-y-2">
          {Object.entries(groupedDatasets).map(([type, typeDatasets]) => (
            <div key={type} className="group">
              <button
                onClick={() => toggleType(type)}
                className={`w-full px-3 py-2.5 flex items-center justify-between rounded-md transition-colors ${DATASET_COLORS[type as keyof typeof DATASET_COLORS] || "bg-accent"} hover:opacity-90`}
              >
                <div className="flex items-center gap-2">
                  <ChevronRight
                    className="w-4 h-4 text-foreground/70 transition-transform duration-200"
                    style={{
                      transform: expandedTypes.has(type)
                        ? "rotate(90deg)"
                        : "rotate(0deg)",
                    }}
                  />
                  <span className="font-medium text-sm text-foreground">
                    {type}
                  </span>
                </div>
                <span className="text-xs px-2 py-0.5 rounded-md bg-background/60 text-foreground/70 font-medium">
                  {typeDatasets.length}
                </span>
              </button>

              {expandedTypes.has(type) && (
                <div className="mt-1 ml-6 space-y-0.5 animate-in fade-in slide-in-from-top-1 duration-200">
                  {typeDatasets.map((dataset, index) => (
                    <button
                      key={index}
                      onClick={() => handleDatasetClick(dataset)}
                      className={`w-full text-left px-3 py-2 rounded-md text-sm transition-all ${
                        selectedDataset === dataset
                          ? "bg-primary text-primary-foreground font-medium"
                          : "text-foreground hover:bg-accent/50"
                      }`}
                    >
                      {dataset.name}
                    </button>
                  ))}
                </div>
              )}
            </div>
          ))}
          {datasets.length === 0 && (
            <div className="text-sm text-muted-foreground p-3 text-center">
              No datasets available
            </div>
          )}
        </div>
      </div>

      <div className="flex-1 flex flex-col min-h-0">
        <div className="flex h-10 bg-secondary dark:bg-card border-b border-border shrink-0">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              className={`px-6 py-2 text-sm font-medium border-r border-border transition-colors ${
                activeTab === tab.id
                  ? "bg-white dark:bg-background text-foreground"
                  : "text-muted-foreground hover:bg-accent"
              }`}
              onClick={() => setActiveTab(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className="flex gap-2 p-2 bg-muted dark:bg-card/30 border-b border-border shrink-0">
          <Button size="sm" variant="outline" disabled={!selectedDataset}>
            Delete
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={handleAdd}
            disabled={
              !selectedWell ||
              (activeTab !== "logs" && activeTab !== "constants")
            }
          >
            Add
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={handleExport}
            disabled={!selectedDataset}
          >
            Export
          </Button>
        </div>

        <div className="flex-1 overflow-auto bg-white dark:bg-background min-h-0">
          {activeTab === "logs" && renderLogsTab()}
          {activeTab === "logValues" && renderLogValuesTab()}
          {activeTab === "constants" && renderConstantsTab()}
        </div>
      </div>

      {/* Add Log Dialog */}
      <Dialog open={showAddLogDialog} onOpenChange={setShowAddLogDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add New Log</DialogTitle>
            <DialogDescription>
              Add a new empty log to {selectedWell?.name}
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="logName">Log Name *</Label>
              <Input
                id="logName"
                value={newLogName}
                onChange={(e) => setNewLogName(e.target.value)}
                placeholder="e.g., GAMMA_RAY"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="logDescription">Description</Label>
              <Input
                id="logDescription"
                value={newLogDescription}
                onChange={(e) => setNewLogDescription(e.target.value)}
                placeholder="e.g., Gamma ray log"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="logType">Log Type</Label>
              <select
                id="logType"
                value={newLogType}
                onChange={(e) => setNewLogType(e.target.value)}
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              >
                <option value="float">Float</option>
                <option value="str">String</option>
              </select>
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowAddLogDialog(false)}
            >
              Cancel
            </Button>
            <Button onClick={handleAddLog}>Add Log</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Add Constant Dialog */}
      <Dialog
        open={showAddConstantDialog}
        onOpenChange={setShowAddConstantDialog}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add New Constant</DialogTitle>
            <DialogDescription>
              Add a new constant to {selectedWell?.name}
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="constantName">Constant Name *</Label>
              <Input
                id="constantName"
                value={newConstantName}
                onChange={(e) => setNewConstantName(e.target.value)}
                placeholder="e.g., API_GRAVITY"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="constantValue">Value *</Label>
              <Input
                id="constantValue"
                value={newConstantValue}
                onChange={(e) => setNewConstantValue(e.target.value)}
                placeholder="e.g., 45.2"
                type="number"
                step="any"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="constantTag">Tag</Label>
              <Input
                id="constantTag"
                value={newConstantTag}
                onChange={(e) => setNewConstantTag(e.target.value)}
                placeholder="e.g., API"
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowAddConstantDialog(false)}
            >
              Cancel
            </Button>
            <Button onClick={handleAddConstant}>Add Constant</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
