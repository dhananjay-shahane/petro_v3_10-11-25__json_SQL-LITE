import { Folder, Database, Layers } from "lucide-react";

interface ProjectInfoBarProps {
  projectPath: string;
  projectName: string;
  wellCount: number;
  selectedLayout?: { name: string } | null;
  selectedDataset?: { name: string } | null;
}

export default function ProjectInfoBar({
  projectPath,
  projectName,
  wellCount,
  selectedLayout,
  selectedDataset,
}: ProjectInfoBarProps) {
  return (
    <div className="h-8 bg-muted/50 border-b border-border flex items-center px-2 md:px-4 gap-2 md:gap-6 text-xs md:text-sm overflow-x-auto">
      <div className="flex items-center gap-1 md:gap-2 flex-shrink-0">
        <Folder className="w-3 h-3 md:w-4 md:h-4 text-muted-foreground" />
        <span className="text-muted-foreground hidden md:inline">Project:</span>
        <span className="font-medium text-foreground cursor-help" title={projectPath}>
          {projectName || "No project"}
        </span>
      </div>
      
      <div className="flex items-center gap-1 md:gap-2 flex-shrink-0">
        <Database className="w-3 h-3 md:w-4 md:h-4 text-muted-foreground" />
        <span className="text-muted-foreground">Wells:</span>
        <span className="font-semibold text-foreground">{wellCount}</span>
      </div>
      
      {selectedLayout && (
        <div className="flex items-center gap-1 md:gap-2 flex-shrink-0">
          <Layers className="w-3 h-3 md:w-4 md:h-4 text-muted-foreground" />
          <span className="text-muted-foreground hidden md:inline">Selected Layout:</span>
          <span className="font-medium text-primary">{selectedLayout.name}</span>
        </div>
      )}
      
      {selectedDataset && (
        <div className="flex items-center gap-1 md:gap-2 flex-shrink-0">
          <Layers className="w-3 h-3 md:w-4 md:h-4 text-muted-foreground" />
          <span className="text-muted-foreground hidden md:inline">Dataset:</span>
          <span className="font-medium text-primary">{selectedDataset.name}</span>
        </div>
      )}
    </div>
  );
}
