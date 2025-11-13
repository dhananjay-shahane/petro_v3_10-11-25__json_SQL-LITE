import DockPanel from "./DockPanel";
import { Button } from "@/components/ui/button";
import { FolderOpen, Search } from "lucide-react";

export default function ProjectPanel({ onClose }: { onClose?: () => void }) {
  return (
    <DockPanel title="Project" onClose={onClose}>
      <div className="flex flex-col h-full">
        <div className="flex items-center gap-2 p-2 border-b border-card-border">
          <Button size="icon" variant="ghost" className="h-8 w-8" data-testid="button-open-folder">
            <FolderOpen className="w-4 h-4" />
          </Button>
          <div className="flex-1 relative">
            <Search className="absolute left-2 top-1/2 transform -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search files..."
              className="w-full h-8 pl-8 pr-3 text-sm bg-background border border-border rounded focus:outline-none focus:ring-2 focus:ring-ring"
              data-testid="input-search-files"
            />
          </div>
        </div>
        <div className="flex-1 overflow-auto p-2">
          <div className="text-sm text-muted-foreground text-center py-8">
            No project selected
          </div>
        </div>
      </div>
    </DockPanel>
  );
}
