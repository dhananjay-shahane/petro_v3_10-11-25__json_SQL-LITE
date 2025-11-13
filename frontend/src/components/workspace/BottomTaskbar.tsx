import { Button } from "@/components/ui/button";
import { Maximize2 } from "lucide-react";

interface MinimizedPanel {
  id: string;
  title: string;
}

interface BottomTaskbarProps {
  minimizedPanels: MinimizedPanel[];
  onMaximize: (panelId: string) => void;
}

export default function BottomTaskbar({ minimizedPanels, onMaximize }: BottomTaskbarProps) {
  if (minimizedPanels.length === 0) {
    return null;
  }

  return (
    <div className="sticky bottom-0 left-0 right-0 z-50 bg-secondary/95 dark:bg-card/95 backdrop-blur-sm border-t border-border dark:border-card-border shadow-lg">
      <div className="flex items-center gap-1 px-2 py-1 h-10 overflow-x-auto">
        {minimizedPanels.map((panel) => (
          <Button
            key={panel.id}
            variant="outline"
            size="sm"
            className="h-8 px-3 gap-2 bg-background/50 hover:bg-background border-border dark:border-card-border"
            onClick={() => onMaximize(panel.id)}
          >
            <span className="text-sm font-medium truncate max-w-[150px]">
              {panel.title}
            </span>
            <Maximize2 className="w-3.5 h-3.5 flex-shrink-0" />
          </Button>
        ))}
      </div>
    </div>
  );
}
