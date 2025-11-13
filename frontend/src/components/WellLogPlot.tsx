import { useEffect, useState, useRef } from "react";
import { parseResponse, handleApiError } from "@/lib/api-utils";
import Plot from 'react-plotly.js';
import { LinkIcon, Unlink, X } from 'lucide-react';

interface Dataset {
  name: string;
  type: string;
}

interface WellData {
  id?: string;
  name: string;
  well_name?: string;
  path?: string;
  projectPath?: string;
  data?: any;
  logs?: string[];
  metadata?: any;
}

interface WellLogPlotProps {
  selectedWell?: WellData | null;
  projectPath?: string;
  initialSelectedLogs?: string[];
  selectedDataset?: any;
  onDatasetSelect?: (dataset: any) => void;
  isLocked?: boolean;
  onToggleLock?: () => void;
}

export default function WellLogPlot({
  selectedWell,
  projectPath,
  initialSelectedLogs,
  selectedDataset,
  onDatasetSelect,
  isLocked = true,
  onToggleLock,
}: WellLogPlotProps) {
  const [plotData, setPlotData] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [availableLogs, setAvailableLogs] = useState<Dataset[]>([]);
  const [selectedLogs, setSelectedLogs] = useState<string[]>([]);
  const [selectedLayout, setSelectedLayout] = useState<string>("");
  const [broadcastedWell, setBroadcastedWell] = useState<WellData | null>(null);
  
  // Generate unique panel ID
  const [panelId] = useState<string>(() => {
    return `LogPlot-Panel-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
  });
  
  // Track current well and project to prevent stale plot updates
  const currentContextRef = useRef({ wellId: '', projectPath: '' });
  const containerRef = useRef<HTMLDivElement>(null);

  // Listen for well selection broadcasts from other windows (for new Chrome windows opened by rc-dock)
  useEffect(() => {
    if (!isLocked) return;

    const channel = new BroadcastChannel('well-selection-channel');
    
    const handleMessage = (event: MessageEvent) => {
      if (event.data.type === 'WELL_SELECTED' && isLocked) {
        const newWell = event.data.well;
        console.log('[WellLogPlot] Received well selection broadcast:', newWell);
        setBroadcastedWell(newWell);
      }
    };

    channel.addEventListener('message', handleMessage);

    return () => {
      channel.removeEventListener('message', handleMessage);
      channel.close();
    };
  }, [isLocked]);

  // Use broadcasted well if available and linked, otherwise use prop
  const currentWell = broadcastedWell || selectedWell;
  const currentProjectPath = broadcastedWell?.projectPath || projectPath;

  // Focus notification for WellLogPlot panel
  useEffect(() => {
    const handlePanelClick = () => {
      const wellName = currentWell?.name || 'No well';
      const message = `LogPlot Panel [${panelId}] focused: ${wellName}`;
      
      if ((window as any).addAppLog) {
        (window as any).addAppLog(message, 'info');
      }
      
      console.log(`[WellLogPlot] ${message}`);
    };

    const container = containerRef.current;
    if (container) {
      container.addEventListener('click', handlePanelClick);
      
      return () => {
        container.removeEventListener('click', handlePanelClick);
      };
    }
  }, [currentWell?.name, panelId]);

  const generatePlot = async (
    wellId: string,
    path: string,
    logNames: string[],
    layoutName?: string,
  ) => {
    if (logNames.length === 0) return;

    setIsLoading(true);
    setError(null);
    
    // Store the context this plot is being generated for
    const plotContext = { wellId, projectPath: path };

    try {
      const requestBody: any = {
        projectPath: path,
        logNames: logNames,
      };
      
      // Add layoutName if provided
      if (layoutName) {
        requestBody.layoutName = layoutName;
      }
      
      const response = await fetch(
        `/api/wells/${encodeURIComponent(wellId)}/log-plot`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(requestBody),
        },
      );

      // Check if context is still current before processing response
      if (currentContextRef.current.wellId !== plotContext.wellId || 
          currentContextRef.current.projectPath !== plotContext.projectPath) {
        console.log('[WellLogPlot] Ignoring stale plot response - context changed');
        setIsLoading(false);
        return;
      }

      const contentType = response.headers.get("content-type");

      if (!response.ok) {
        let errorMessage = "Failed to generate plot";
        if (contentType && contentType.includes("application/json")) {
          const errorData = await response.json();
          errorMessage = errorData.error || errorMessage;
        } else {
          const text = await response.text();
          errorMessage = `Server error: ${text.substring(0, 200)}`;
        }
        throw new Error(errorMessage);
      }

      const data =
        contentType && contentType.includes("application/json")
          ? await response.json()
          : { error: "Invalid response format" };
      
      // Final check before applying plot data
      if (currentContextRef.current.wellId === plotContext.wellId && 
          currentContextRef.current.projectPath === plotContext.projectPath) {
        // Parse the Plotly JSON
        if (data.plotly_json) {
          const plotlyData = JSON.parse(data.plotly_json);
          setPlotData(plotlyData);
        } else {
          throw new Error("No plot data received");
        }
      } else {
        console.log('[WellLogPlot] Ignoring stale plot data - context changed');
      }
    } catch (err: any) {
      // Only show error if context is still current
      if (currentContextRef.current.wellId === plotContext.wellId && 
          currentContextRef.current.projectPath === plotContext.projectPath) {
        console.error("Error generating plot:", err);
        setError(err.message || "Failed to generate plot");
      }
    } finally {
      // Only clear loading if context is still current
      if (currentContextRef.current.wellId === plotContext.wellId && 
          currentContextRef.current.projectPath === plotContext.projectPath) {
        setIsLoading(false);
      }
    }
  };

  useEffect(() => {
    let isCurrent = true;
    
    console.log("[WellLogPlot] useEffect triggered", {
      selectedWell,
      projectPath,
      broadcastedWell,
      currentWell,
      currentProjectPath,
    });

    // ALWAYS clear data immediately when well or project changes to prevent stale data
    setPlotData(null);
    setError(null);
    setAvailableLogs([]);
    setSelectedLogs([]);
    setIsLoading(false);
    
    // Update current context ref to prevent stale plot updates
    const wellId = currentWell ? (currentWell.id || currentWell.well_name || currentWell.name) : '';
    const path = currentProjectPath || (currentWell ? currentWell.projectPath : '') || '';
    currentContextRef.current = { wellId, projectPath: path };
    console.log('[WellLogPlot] Updated context:', currentContextRef.current);

    if (!currentWell) {
      return;
    }
    
    // Critical check: verify the well belongs to the current project BEFORE fetching data
    if (currentWell.path && path) {
      const wellBelongsToProject = 
        currentWell.path === path || 
        currentWell.path.startsWith(path + '/') || 
        currentWell.path.startsWith(path + '\\');
      
      if (!wellBelongsToProject) {
        console.log(
          "[WellLogPlot] Well doesn't belong to current project - clearing and returning. Well path:",
          currentWell.path,
          "Project path:",
          path
        );
        return;
      }
    }

    const fetchAvailableLogs = async () => {
      try {

        const wellBelongsToProject = currentWell.path && (
          currentWell.path === path || 
          currentWell.path.startsWith(path + '/') || 
          currentWell.path.startsWith(path + '\\')
        );

        if (currentWell.path && path && !wellBelongsToProject) {
          console.log(
            "[WellLogPlot] Well path mismatch - well doesn't belong to current project. Clearing data.",
          );
          return;
        }

        console.log(
          "[WellLogPlot] Fetching datasets for well:",
          wellId,
          "path:",
          path,
        );

        const response = await fetch(
          `/api/wells/datasets?projectPath=${encodeURIComponent(path)}&wellName=${encodeURIComponent(wellId)}`,
        );

        // Only apply results if this effect is still current
        if (!isCurrent) {
          console.log("[WellLogPlot] Ignoring stale response for old well/project");
          return;
        }

        if (!response.ok) {
          await handleApiError(response);
        }

        const data = await parseResponse<{ datasets: Dataset[] }>(response);
        console.log("[WellLogPlot] Datasets response:", data);

        // Check again before applying results
        if (!isCurrent) {
          console.log("[WellLogPlot] Ignoring stale data");
          return;
        }

        // Filter for individual log entries (type='Cont' with empty well_logs array)
        // These represent actual logs, not dataset containers
        const logs =
          data.datasets?.filter(
            (d: any) => (d.type === "Cont" || d.type === "continuous") &&
            (!d.well_logs || d.well_logs.length === 0)
          ) || [];
        console.log("[WellLogPlot] Continuous logs found:", logs.length, logs);
        setAvailableLogs(logs);

        // Use initialSelectedLogs if provided, otherwise auto-select first 3 logs
        if (logs.length > 0 && isCurrent) {
          let logsToPlot: string[];
          
          if (initialSelectedLogs && initialSelectedLogs.length > 0) {
            // Use logs from Data Browser
            logsToPlot = initialSelectedLogs;
            console.log("[WellLogPlot] Using logs from Data Browser:", logsToPlot);
          } else {
            // Auto-select first 3 logs
            logsToPlot = logs.slice(0, 3).map((l: Dataset) => l.name);
            console.log("[WellLogPlot] Auto-selecting first 3 logs:", logsToPlot);
          }
          
          setSelectedLogs(logsToPlot);
          console.log("[WellLogPlot] Generating plot for logs:", logsToPlot);
          generatePlot(wellId, path, logsToPlot, selectedLayout);
        } else {
          console.log(
            "[WellLogPlot] No continuous logs found, skipping plot generation",
          );
        }
      } catch (err: any) {
        if (isCurrent) {
          console.error("[WellLogPlot] Error fetching datasets:", err);
          setError(err.message || "Failed to fetch datasets");
        }
      }
    };

    fetchAvailableLogs();
    
    return () => {
      isCurrent = false;
    };
  }, [currentWell, currentProjectPath, initialSelectedLogs]);

  const toggleLog = (logName: string) => {
    const newSelectedLogs = selectedLogs.includes(logName)
      ? selectedLogs.filter((l) => l !== logName)
      : [...selectedLogs, logName];

    setSelectedLogs(newSelectedLogs);

    // Auto-regenerate plot when logs change
    if (selectedWell && newSelectedLogs.length > 0) {
      const wellId =
        selectedWell.id || selectedWell.well_name || selectedWell.name;
      const path = projectPath || selectedWell.projectPath || "";
      generatePlot(wellId, path, newSelectedLogs, selectedLayout);
    } else {
      setPlotData(null);
    }
  };

  const removeLog = (logName: string) => {
    const newSelectedLogs = selectedLogs.filter((l) => l !== logName);
    setSelectedLogs(newSelectedLogs);

    // Auto-regenerate plot when logs change
    if (selectedWell && newSelectedLogs.length > 0) {
      const wellId =
        selectedWell.id || selectedWell.well_name || selectedWell.name;
      const path = projectPath || selectedWell.projectPath || "";
      generatePlot(wellId, path, newSelectedLogs, selectedLayout);
    } else {
      setPlotData(null);
    }
  };

  // Drag and drop handlers
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'copy';
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const logName = e.dataTransfer.getData('application/x-log-name') || e.dataTransfer.getData('text/plain');
    
    if (logName && !selectedLogs.includes(logName)) {
      // Check if the log is in the available logs list
      const logExists = availableLogs.some(log => log.name === logName);
      
      if (logExists) {
        const newSelectedLogs = [...selectedLogs, logName];
        setSelectedLogs(newSelectedLogs);
        
        // Auto-regenerate plot when log is added via drag-drop
        if (selectedWell) {
          const wellId = selectedWell.id || selectedWell.well_name || selectedWell.name;
          const path = projectPath || selectedWell.projectPath || "";
          generatePlot(wellId, path, newSelectedLogs, selectedLayout);
        }
      }
    }
  };

  const handleLayoutChange = (layoutName: string) => {
    setSelectedLayout(layoutName);
    
    // For CPI layout, auto-select ALL available logs
    if (layoutName === "perfs_cpi_logplot_layout" && availableLogs.length > 0) {
      const allLogNames = availableLogs.map((log) => log.name);
      setSelectedLogs(allLogNames);
      
      if (selectedWell) {
        const wellId = selectedWell.id || selectedWell.well_name || selectedWell.name;
        const path = projectPath || selectedWell.projectPath || "";
        generatePlot(wellId, path, allLogNames, layoutName);
      }
    } else {
      // For default layout, regenerate with current selection
      if (selectedWell && selectedLogs.length > 0) {
        const wellId = selectedWell.id || selectedWell.well_name || selectedWell.name;
        const path = projectPath || selectedWell.projectPath || "";
        generatePlot(wellId, path, selectedLogs, layoutName);
      }
    }
  };

  if (!selectedWell) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-background">
        <div className="text-center text-muted-foreground">
          <p className="text-lg font-medium">No well selected</p>
          <p className="text-sm mt-2">
            Select a well from the Wells panel to display the log plot
          </p>
        </div>
      </div>
    );
  }

  const wellBelongsToProject = selectedWell && selectedWell.path && projectPath && (
    selectedWell.path === projectPath || 
    selectedWell.path.startsWith(projectPath + '/') || 
    selectedWell.path.startsWith(projectPath + '\\')
  );

  return (
    <div 
      ref={containerRef}
      className="w-full h-full flex flex-col bg-background"
      onDragOver={handleDragOver}
      onDrop={handleDrop}
    >
      {/* Control Panel */}
      <div className="border-b p-2 sm:p-4 space-y-2 sm:space-y-3 shrink-0">
        <div className="flex items-center justify-between gap-2">
          <h3 className="text-sm sm:text-base font-semibold truncate">
            {wellBelongsToProject ? `Well: ${selectedWell.well_name || selectedWell.name}` : 'No well selected'}
          </h3>
          {onToggleLock && (
            <button
              onClick={onToggleLock}
              className="flex items-center gap-1 px-2 py-1 text-xs rounded-md border border-border hover:border-foreground/30 transition-colors group"
              title={isLocked ? "Linked - Follows global well selection. Click to unlink" : "Unlinked - Stays on current well. Click to link"}
            >
              <span 
                key={isLocked ? 'linked' : 'unlinked'}
                className="inline-block animate-in fade-in zoom-in duration-300" 
                style={{ 
                  animation: 'spin-scale 0.5s ease-out'
                }}
              >
                {isLocked ? (
                  <LinkIcon className="w-4 h-4 text-green-500 group-hover:scale-110 transition-transform" />
                ) : (
                  <Unlink className="w-4 h-4 text-gray-500 group-hover:scale-110 transition-transform" />
                )}
              </span>
              <span className={`hidden sm:inline font-medium transition-colors ${isLocked ? 'text-green-500' : 'text-gray-500'}`}>
                {isLocked ? "Linked" : "Unlinked"}
              </span>
            </button>
          )}
        </div>

        {/* Layout Selection */}
        <div className="space-y-1 sm:space-y-2">
          <p className="text-xs sm:text-sm text-muted-foreground">
            Layout:
          </p>
          <div className="flex gap-2">
            <button
              onClick={() => handleLayoutChange("")}
              className={`px-3 py-1 text-xs rounded-md border transition-colors ${
                selectedLayout === ""
                  ? "bg-primary text-primary-foreground border-primary"
                  : "bg-background hover:bg-accent border-border"
              }`}
            >
              Default
            </button>
            <button
              onClick={() => handleLayoutChange("perfs_cpi_logplot_layout")}
              className={`px-3 py-1 text-xs rounded-md border transition-colors ${
                selectedLayout === "perfs_cpi_logplot_layout"
                  ? "bg-primary text-primary-foreground border-primary"
                  : "bg-background hover:bg-accent border-border"
              }`}
            >
              CPI Layout
            </button>
          </div>
        </div>

        {/* Selected Logs - Show which logs are currently plotted */}
        {selectedLogs.length > 0 && selectedLayout !== "perfs_cpi_logplot_layout" && (
          <div className="space-y-1 sm:space-y-2">
            <p className="text-xs sm:text-sm text-muted-foreground">
              Selected logs ({selectedLogs.length}):
            </p>
            <div className="flex flex-wrap gap-1 sm:gap-2">
              {selectedLogs.map((logName) => (
                <div
                  key={logName}
                  className="flex items-center gap-1 px-2 sm:px-3 py-0.5 sm:py-1 text-xs rounded-md bg-primary text-primary-foreground border border-primary"
                >
                  <span>{logName}</span>
                  <button
                    onClick={() => removeLog(logName)}
                    className="hover:bg-primary-foreground/20 rounded p-0.5"
                    title="Remove log from plot"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Log Selection - Only show for Default layout */}
        {availableLogs.length > 0 && selectedLayout !== "perfs_cpi_logplot_layout" && (
          <div className="space-y-1 sm:space-y-2">
            <p className="text-xs sm:text-sm text-muted-foreground">
              Available logs:
            </p>
            <div className="flex flex-wrap gap-1 sm:gap-2">
              {availableLogs.map((log) => (
                <button
                  key={log.name}
                  onClick={() => toggleLog(log.name)}
                  disabled={selectedLogs.includes(log.name)}
                  className={`px-2 sm:px-3 py-0.5 sm:py-1 text-xs rounded-md border transition-colors ${
                    selectedLogs.includes(log.name)
                      ? "bg-muted text-muted-foreground border-border opacity-50 cursor-not-allowed"
                      : "bg-background hover:bg-accent border-border"
                  }`}
                >
                  {log.name}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* CPI Layout Info */}
        {selectedLayout === "perfs_cpi_logplot_layout" && (
          <div className="text-xs sm:text-sm text-muted-foreground bg-muted p-2 rounded">
            <p>CPI Layout: Displaying all available logs in multi-track format</p>
          </div>
        )}
      </div>

      {/* Plot Display Area */}
      <div className="flex-1 overflow-hidden p-2 sm:p-4 flex flex-col">
        {isLoading && (
          <div className="w-full h-full flex items-center justify-center">
            <p className="text-sm text-muted-foreground">Generating plot...</p>
          </div>
        )}

        {error && (
          <div className="w-full h-full flex items-center justify-center">
            <div className="text-center text-destructive px-2">
              <p className="text-base sm:text-lg font-medium">Error</p>
              <p className="text-xs sm:text-sm mt-2">{error}</p>
            </div>
          </div>
        )}

        {!isLoading && !error && !plotData && selectedLogs.length === 0 && (
          <div className="w-full h-full flex items-center justify-center px-2">
            <p className="text-xs sm:text-sm text-muted-foreground text-center">
              Select at least one log to view the plot
            </p>
          </div>
        )}

        {!isLoading && plotData && (
          <div className="flex-1 flex justify-center w-full overflow-auto">
            <Plot
              data={plotData.data}
              layout={{
                ...plotData.layout,
                autosize: true,
                // Ensure shapes are rendered on top
                shapes: plotData.layout.shapes || []
              }}
              config={{
                responsive: true,
                displayModeBar: true,
                displaylogo: false,
                scrollZoom: false,
                modeBarButtonsToRemove: ['lasso2d', 'select2d', 'zoomIn2d', 'zoomOut2d', 'autoScale2d', 'resetScale2d'],
                modeBarButtonsToAdd: [],
                staticPlot: false,
                editable: false
              }}
              style={{ 
                width: '100%', 
                height: '100%',
              }}
              useResizeHandler={true}
              className="plotly-well-log"
            />
          </div>
        )}
      </div>
    </div>
  );
}
