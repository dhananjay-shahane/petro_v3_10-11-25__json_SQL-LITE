import WellLogPlot from "../WellLogPlot";
import type { WellData } from "../workspace/Workspace";

export default function WellLogPlotPanel({ 
  selectedWell,
  projectPath,
  selectedLogsForPlot,
  selectedDataset,
  onDatasetSelect,
  isLocked,
  onToggleLock,
}: { 
  selectedWell?: WellData | null;
  projectPath?: string;
  selectedLogsForPlot?: string[];
  selectedDataset?: any;
  onDatasetSelect?: (dataset: any) => void;
  isLocked?: boolean;
  onToggleLock?: () => void;
}) {
  return (
    <WellLogPlot 
      selectedWell={selectedWell} 
      projectPath={projectPath} 
      initialSelectedLogs={selectedLogsForPlot}
      selectedDataset={selectedDataset}
      onDatasetSelect={onDatasetSelect}
      isLocked={isLocked}
      onToggleLock={onToggleLock}
    />
  );
}
