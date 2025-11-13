import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Download, FileImage } from 'lucide-react';
import { useToast } from "@/hooks/use-toast";
import type { WellData } from "../workspace/Workspace";

interface Dataset {
  name: string;
  type: string;
}

export default function CrossPlotControlPanel({
  selectedWell,
  projectPath,
  panelId,
  targetWindowId,
  initialXLog,
  initialYLog,
  onPlotConfigChange,
}: {
  selectedWell?: WellData | null;
  projectPath?: string;
  panelId?: string;
  targetWindowId?: string | null;
  initialXLog?: string;
  initialYLog?: string;
  onPlotConfigChange?: (windowId: string, xLog: string, yLog: string) => void;
}) {
  const { toast } = useToast();
  const [selectedXLog, setSelectedXLog] = useState('');
  const [selectedYLog, setSelectedYLog] = useState('');
  const [availableLogs, setAvailableLogs] = useState<any[]>([]);
  const [isInitialized, setIsInitialized] = useState(false);

  useEffect(() => {
    if (!selectedWell) {
      setAvailableLogs([]);
      setSelectedXLog('');
      setSelectedYLog('');
      return;
    }

    const fetchAvailableLogs = async () => {
      try {
        const wellId = selectedWell.id || selectedWell.name;
        const path = projectPath || '';
        
        const response = await fetch(`/api/wells/datasets?projectPath=${encodeURIComponent(path)}&wellName=${encodeURIComponent(wellId)}`);
        
        if (!response.ok) {
          throw new Error('Failed to fetch datasets');
        }
        
        const data = await response.json();
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
        setAvailableLogs(logs);
        
        // Hydrate from initial values if available (from workspace state)
        if (initialXLog && initialYLog && logs.some(l => l.name === initialXLog) && logs.some(l => l.name === initialYLog)) {
          setSelectedXLog(initialXLog);
          setSelectedYLog(initialYLog);
          setIsInitialized(true);
        }
        // Otherwise auto-select first two logs only if no initial values
        else if (!initialXLog && !initialYLog && logs.length >= 2) {
          const xLogName = logs[0].name;
          const yLogName = logs[1].name;
          setSelectedXLog(xLogName);
          setSelectedYLog(yLogName);
          setIsInitialized(true);
          // Only fire change event for new selections
          if (onPlotConfigChange && targetWindowId) {
            onPlotConfigChange(targetWindowId, xLogName, yLogName);
          }
        } else if (!initialXLog && logs.length === 1) {
          setSelectedXLog(logs[0].name);
          setIsInitialized(true);
        } else {
          setIsInitialized(true);
        }
      } catch (err: any) {
        console.error('Error fetching datasets:', err);
        toast({
          title: "Error",
          description: "Failed to load available logs",
          variant: "destructive",
        });
      }
    };

    fetchAvailableLogs();
  }, [selectedWell, projectPath]);

  const handleXLogChange = (value: string) => {
    console.log('[CrossPlotControl] X-log changed to:', value, 'target:', targetWindowId);
    setSelectedXLog(value);
    if (value && selectedYLog && onPlotConfigChange && targetWindowId) {
      console.log('[CrossPlotControl] Calling onPlotConfigChange with:', {targetWindowId, xLog: value, yLog: selectedYLog});
      onPlotConfigChange(targetWindowId, value, selectedYLog);
    }
  };

  const handleYLogChange = (value: string) => {
    console.log('[CrossPlotControl] Y-log changed to:', value, 'target:', targetWindowId);
    setSelectedYLog(value);
    if (selectedXLog && value && onPlotConfigChange && targetWindowId) {
      console.log('[CrossPlotControl] Calling onPlotConfigChange with:', {targetWindowId, xLog: selectedXLog, yLog: value});
      onPlotConfigChange(targetWindowId, selectedXLog, value);
    }
  };

  const showDownloadMessage = () => {
    toast({
      title: "Download from Cross Plot Panel",
      description: "Right-click on the cross plot image and use the download options there",
    });
  };

  return (
    <div className="w-full h-full flex flex-col bg-background">
      {/* Compact Header */}
      <div className="border-b px-3 py-2 bg-muted/20 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h3 className="font-medium text-sm">Cross Plot Control</h3>
          {selectedWell && (
            <span className="text-xs text-muted-foreground">
              • {selectedWell.name}
            </span>
          )}
        </div>
        {targetWindowId && (
          <span className="text-xs text-muted-foreground font-mono bg-primary/10 px-2 py-0.5 rounded">
            Target: {targetWindowId}
          </span>
        )}
      </div>

      {/* Compact Content */}
      <div className="flex-1 overflow-auto p-3 space-y-3">
        
        {/* Select Logs - Compact */}
        <div className="bg-card border rounded p-3 space-y-2">
          <div className="grid grid-cols-2 gap-2">
            <div className="space-y-1">
              <Label className="text-xs font-medium">X-Axis</Label>
              <Select value={selectedXLog} onValueChange={handleXLogChange}>
                <SelectTrigger className="h-8 text-xs">
                  <SelectValue placeholder="Select..." />
                </SelectTrigger>
                <SelectContent position="popper" className="z-[99999]" sideOffset={4}>
                  {availableLogs.map((log) => (
                    <SelectItem key={log.name} value={log.name} className="text-xs">
                      {log.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1">
              <Label className="text-xs font-medium">Y-Axis</Label>
              <Select value={selectedYLog} onValueChange={handleYLogChange}>
                <SelectTrigger className="h-8 text-xs">
                  <SelectValue placeholder="Select..." />
                </SelectTrigger>
                <SelectContent position="popper" className="z-[99999]" sideOffset={4}>
                  {availableLogs.map((log) => (
                    <SelectItem key={log.name} value={log.name} className="text-xs">
                      {log.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Status */}
          {selectedXLog && selectedYLog && (
            <div className="text-xs bg-green-50 dark:bg-green-950/20 text-green-700 dark:text-green-400 px-2 py-1.5 rounded font-medium">
              ✓ {selectedYLog} vs {selectedXLog}
            </div>
          )}
        </div>

        {/* Info message */}
        <div className="bg-muted/50 border rounded p-3">
          <p className="text-xs text-muted-foreground text-center">
            View the plot in the Cross Plot panel. Right-click to download.
          </p>
        </div>
      </div>
    </div>
  );
}
