import { Search, FileText } from "lucide-react";
import { useState } from "react";
import type { WellData } from "../workspace/Workspace";

export default function WellsPanelNew({
  wells = [],
  selectedWell,
  onWellSelect,
  activeWellName,
}: {
  wells?: WellData[];
  selectedWell?: WellData | null;
  onWellSelect?: (well: WellData) => void;
  activeWellName?: string | null;
}) {
  const [searchTerm, setSearchTerm] = useState("");

  const filteredWells = wells.filter(well => 
    well.name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="flex flex-col h-full p-2" style={{ fontSize: 'var(--font-size-well-list, 14px)' }}>
      <div className="relative mb-2">
        <Search className="absolute left-2 top-1/2 transform -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
        <input
          type="text"
          placeholder="Search..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="w-full h-8 pl-8 pr-3 bg-background border border-border rounded focus:outline-none focus:ring-2 focus:ring-ring"
          data-testid="input-search-wells"
        />
      </div>
      
      <div className="flex-1 overflow-auto">
        {wells.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
            <FileText className="w-12 h-12 mb-2 opacity-30" />
            <p>No wells available</p>
          </div>
        ) : filteredWells.length === 0 ? (
          <div className="flex items-center justify-center h-full text-muted-foreground">
            No wells match your search
          </div>
        ) : (
          <div className="space-y-1">
            {filteredWells.map((well) => (
              <div
                key={well.id}
                onClick={() => onWellSelect?.(well)}
                className={`flex items-center gap-2 p-2 hover:bg-accent rounded cursor-pointer transition-colors ${
                  selectedWell?.id === well.id ? 'bg-primary/20 border border-primary' : ''
                }`}
                title={well.path}
              >
                <FileText className={`w-4 h-4 flex-shrink-0 ${
                  selectedWell?.id === well.id ? 'text-primary' : 'text-muted-foreground'
                }`} />
                <span className="truncate font-medium">{well.name}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
