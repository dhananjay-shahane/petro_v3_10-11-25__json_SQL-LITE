import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import type { WellData } from "../workspace/Workspace";

export default function LogPlotPanel({ 
  selectedWell,
  selectedDataset,
  onDatasetSelect,
}: { 
  selectedWell?: WellData | null;
  selectedDataset?: any;
  onDatasetSelect?: (dataset: any) => void;
}) {

  // Prepare log plot data from selected well
  let plotData: any[] = [];
  let depthKey = "depth";
  const curvesToPlot: string[] = [];
  const colors = ["#8b5cf6", "#0ea5e9", "#10b981", "#f59e0b", "#ef4444"];
  
  if (selectedWell?.data && Array.isArray(selectedWell.data) && selectedWell.data.length > 0) {
    const logs = selectedWell.logs || [];
    depthKey = logs.find((c: string) => c === 'DEPT' || c === 'DEPTH') || 'DEPT';
    
    // Get up to 3 curves to plot (excluding depth)
    const availableCurves = logs.filter((c: string) => c !== 'DEPT' && c !== 'DEPTH').slice(0, 3);
    curvesToPlot.push(...availableCurves);
    
    plotData = selectedWell.data.filter((point: any) => isFinite(point[depthKey]));
  }

  return (
    <div className="h-full flex flex-col bg-background p-4">
      {!selectedWell ? (
        <div className="flex-1 flex items-center justify-center text-muted-foreground">
          <div className="text-center">
            <p className="text-lg">No well selected</p>
            <p className="text-sm mt-2">Select a well from the Wells panel to display log plot</p>
          </div>
        </div>
      ) : plotData.length === 0 ? (
        <div className="flex-1 flex items-center justify-center text-muted-foreground">
          <div className="text-center">
            <p className="text-lg">Loading well data...</p>
            <p className="text-sm mt-2">{selectedWell.name}</p>
          </div>
        </div>
      ) : (
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={plotData} margin={{ top: 20, right: 30, left: 40, bottom: 40 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis 
              dataKey={curvesToPlot[0] || "value"} 
              label={{ value: curvesToPlot[0] || 'Value', position: 'bottom', offset: 0 }}
            />
            <YAxis 
              dataKey={depthKey} 
              reversed
              label={{ value: 'Depth', angle: -90, position: 'insideLeft' }}
            />
            <Tooltip />
            <Legend />
            {curvesToPlot.map((curve, index) => (
              <Line 
                key={curve}
                type="monotone" 
                dataKey={curve} 
                stroke={colors[index % colors.length]} 
                name={curve} 
                strokeWidth={2}
                dot={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
