import { useEffect, useState } from "react";
import type { WellData } from "../workspace/Workspace";
import { parseResponse, handleApiError } from "@/lib/api-utils";
import { Button } from "@/components/ui/button";
import { LinkIcon, Unlink } from 'lucide-react';
import {
  ContextMenu,
  ContextMenuContent,
  ContextMenuItem,
  ContextMenuTrigger,
} from "@/components/ui/context-menu";

interface Dataset {
  name: string;
  type: string;
}

export default function CrossPlotPanel({ 
  selectedWell,
  projectPath,
  selectedDataset,
  onDatasetSelect,
  isLocked,
  onToggleLock,
  onOpenControlWindow,
  externalXLog,
  externalYLog,
}: { 
  selectedWell?: WellData | null;
  projectPath?: string;
  selectedDataset?: any;
  onDatasetSelect?: (dataset: any) => void;
  isLocked?: boolean;
  onToggleLock?: () => void;
  onOpenControlWindow?: () => void;
  externalXLog?: string;
  externalYLog?: string;
}) {
  const [plotImage, setPlotImage] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [availableDatasets, setAvailableDatasets] = useState<Dataset[]>([]);
  const [availableLogs, setAvailableLogs] = useState<Dataset[]>([]);
  const [xLog, setXLog] = useState<string>('');
  const [yLog, setYLog] = useState<string>('');
  const [localSelectedDataset, setLocalSelectedDataset] = useState<string>('');
  
  // Generate unique panel ID
  const [panelId] = useState<string>(() => {
    return `CrossPlot-Panel-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
  });

  // Focus notification for CrossPlot panel
  useEffect(() => {
    const handlePanelClick = () => {
      const wellName = selectedWell?.name || 'No well';
      const message = `CrossPlot Panel [${panelId}] focused: ${wellName}`;
      
      if ((window as any).addAppLog) {
        (window as any).addAppLog(message, 'info');
      }
      
      console.log(`[CrossPlotPanel] ${message}`);
    };

    // Add click listener to detect focus
    const panelElement = document.getElementById('crossplot-panel-container');
    if (panelElement) {
      panelElement.addEventListener('click', handlePanelClick);
      
      return () => {
        panelElement.removeEventListener('click', handlePanelClick);
      };
    }
  }, [selectedWell?.name, panelId]);

  const generateCrossPlot = async (wellId: string, path: string, xLogName: string, yLogName: string) => {
    if (!xLogName || !yLogName) return;

    setIsLoading(true);
    setError(null);
    
    try {
      const response = await fetch(`/api/wells/${encodeURIComponent(wellId)}/cross-plot`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          projectPath: path,
          xLog: xLogName,
          yLog: yLogName
        })
      });
      
      const contentType = response.headers.get("content-type");
      
      if (!response.ok) {
        let errorMessage = 'Failed to generate cross plot';
        if (contentType && contentType.includes("application/json")) {
          const errorData = await response.json();
          errorMessage = errorData.error || errorMessage;
        } else {
          const text = await response.text();
          errorMessage = `Server error: ${text.substring(0, 200)}`;
        }
        throw new Error(errorMessage);
      }
      
      const data = contentType && contentType.includes("application/json") 
        ? await response.json()
        : { error: 'Invalid response format' };
      setPlotImage(data.image);
      
    } catch (err: any) {
      console.error('Error generating cross plot:', err);
      setError(err.message || 'Failed to generate cross plot');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (!selectedWell) {
      setPlotImage(null);
      setError(null);
      setAvailableDatasets([]);
      setAvailableLogs([]);
      setXLog('');
      setYLog('');
      setLocalSelectedDataset('');
      return;
    }

    const fetchAvailableLogs = async () => {
      try {
        const wellId = selectedWell.id || selectedWell.name;
        const path = projectPath || '';
        
        const response = await fetch(`/api/wells/datasets?projectPath=${encodeURIComponent(path)}&wellName=${encodeURIComponent(wellId)}`);
        
        if (!response.ok) {
          await handleApiError(response);
        }
        
        const data = await parseResponse<{ datasets: any[] }>(response);
        const allDatasets = data.datasets || [];
        
        // Get all log names from continuous datasets
        const logNames: string[] = [];
        allDatasets.forEach((dataset: any) => {
          if (dataset.type === 'Cont' || dataset.type === 'continuous') {
            if (dataset.well_logs && dataset.well_logs.length > 0) {
              // Extract log names from well_logs array
              dataset.well_logs.forEach((log: any) => {
                if (log.name && !logNames.includes(log.name)) {
                  logNames.push(log.name);
                }
              });
            }
          }
        });
        
        const logs = logNames.map(name => ({ name, type: 'Cont' }));
        
        setAvailableDatasets(allDatasets);
        setAvailableLogs(logs);
        
        // Initialize local selected dataset from prop or default to 'All'
        if (selectedDataset && selectedDataset.name) {
          setLocalSelectedDataset(selectedDataset.name);
        } else {
          setLocalSelectedDataset('All');
        }
        
        // Auto-select first two logs for cross plot
        if (logs.length >= 2) {
          const xLogName = logs[0].name;
          const yLogName = logs[1].name;
          setXLog(xLogName);
          setYLog(yLogName);
          
          // Auto-generate cross plot
          generateCrossPlot(wellId, path, xLogName, yLogName);
        } else if (logs.length === 1) {
          setXLog(logs[0].name);
        }
      } catch (err: any) {
        console.error('Error fetching datasets:', err);
        setError(err.message || 'Failed to fetch datasets');
      }
    };

    fetchAvailableLogs();
  }, [selectedWell, projectPath, selectedDataset]);

  // Listen for external log changes from CrossPlotControlPanel
  useEffect(() => {
    if (!selectedWell || !externalXLog || !externalYLog) return;
    
    console.log('[CrossPlotPanel] External log change:', {externalXLog, externalYLog, currentXLog: xLog, currentYLog: yLog});
    
    // Always update when external values change, even if same as current
    // This ensures plot refreshes when control panel makes selections
    const wellId = selectedWell.id || selectedWell.name;
    const path = projectPath || '';
    console.log('[CrossPlotPanel] Updating cross plot from external selection');
    setXLog(externalXLog);
    setYLog(externalYLog);
    generateCrossPlot(wellId, path, externalXLog, externalYLog);
  }, [externalXLog, externalYLog, selectedWell, projectPath]);

  const handleLogChange = (axis: 'x' | 'y', logName: string) => {
    if (axis === 'x') {
      setXLog(logName);
      if (logName && yLog && selectedWell) {
        const wellId = selectedWell.id || selectedWell.name;
        const path = projectPath || '';
        generateCrossPlot(wellId, path, logName, yLog);
      }
    } else {
      setYLog(logName);
      if (xLog && logName && selectedWell) {
        const wellId = selectedWell.id || selectedWell.name;
        const path = projectPath || '';
        generateCrossPlot(wellId, path, xLog, logName);
      }
    }
  };

  const handleDatasetChange = (datasetName: string) => {
    setLocalSelectedDataset(datasetName);
    if (onDatasetSelect) {
      const dataset = availableDatasets.find(d => d.name === datasetName);
      onDatasetSelect(dataset || null);
    }
  };

  const handleApplyControlData = (newXLog: string, newYLog: string) => {
    if (selectedWell && newXLog && newYLog) {
      const wellId = selectedWell.id || selectedWell.name;
      const path = projectPath || '';
      setXLog(newXLog);
      setYLog(newYLog);
      generateCrossPlot(wellId, path, newXLog, newYLog);
    }
  };

  const downloadImage = (format: 'png' | 'jpg') => {
    if (!plotImage) return;

    try {
      if (format === 'png') {
        const link = document.createElement('a');
        link.href = `data:image/png;base64,${plotImage}`;
        link.download = `cross_plot_${xLog}_vs_${yLog}.png`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
      } else if (format === 'jpg') {
        const img = new Image();
        img.onload = () => {
          const canvas = document.createElement('canvas');
          canvas.width = img.width;
          canvas.height = img.height;
          
          const ctx = canvas.getContext('2d');
          if (!ctx) return;
          
          ctx.fillStyle = '#FFFFFF';
          ctx.fillRect(0, 0, canvas.width, canvas.height);
          ctx.drawImage(img, 0, 0);
          
          canvas.toBlob((blob) => {
            if (!blob) return;
            
            const url = URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            link.download = `cross_plot_${xLog}_vs_${yLog}.jpg`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            URL.revokeObjectURL(url);
          }, 'image/jpeg', 0.95);
        };
        
        img.src = `data:image/png;base64,${plotImage}`;
      }
    } catch (error) {
      console.error('Download error:', error);
    }
  };

  return (
    <div id="crossplot-panel-container" className="w-full h-full flex flex-col bg-background">
      {/* Header with Lock Toggle */}
      <div className="border-b p-3 flex items-center justify-between gap-2">
        <h3 className="font-semibold text-lg">Cross Plot</h3>
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

      {/* Plot Display Area with Context Menu */}
      <div className="flex-1 overflow-auto p-4">
        {!selectedWell ? (
          <div className="w-full h-full flex items-center justify-center">
            <div className="text-center text-muted-foreground">
              <p className="text-lg font-medium">No well selected</p>
              <p className="text-sm mt-2">Select a well from the Wells panel to display cross plot</p>
            </div>
          </div>
        ) : isLoading ? (
          <div className="w-full h-full flex items-center justify-center">
            <p className="text-muted-foreground">Generating cross plot...</p>
          </div>
        ) : error ? (
          <div className="w-full h-full flex items-center justify-center">
            <div className="text-center text-destructive">
              <p className="text-lg font-medium">Error</p>
              <p className="text-sm mt-2">{error}</p>
            </div>
          </div>
        ) : !xLog || !yLog ? (
          <div className="w-full h-full flex items-center justify-center">
            <div className="text-center">
              <p className="text-muted-foreground mb-4">Right-click to configure cross plot axes</p>
              <Button onClick={onOpenControlWindow} variant="outline">
                Control Data
              </Button>
            </div>
          </div>
        ) : plotImage ? (
          <ContextMenu>
            <ContextMenuTrigger asChild>
              <div className="flex justify-center cursor-context-menu">
                <img 
                  src={`data:image/png;base64,${plotImage}`} 
                  alt="Cross Plot"
                  className="max-w-full h-auto"
                />
              </div>
            </ContextMenuTrigger>
            <ContextMenuContent className="w-56">
              <ContextMenuItem onClick={onOpenControlWindow}>
                Control Data
              </ContextMenuItem>
              <ContextMenuItem onClick={() => downloadImage('png')}>
                Download as PNG
              </ContextMenuItem>
              <ContextMenuItem onClick={() => downloadImage('jpg')}>
                Download as JPG
              </ContextMenuItem>
            </ContextMenuContent>
          </ContextMenu>
        ) : null}
      </div>
    </div>
  );

}
