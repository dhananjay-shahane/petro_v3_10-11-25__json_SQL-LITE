import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Layout, FolderOpen, ChevronRight, Sparkles, Trash2 } from "lucide-react";
import { useState } from "react";
import { useToast } from "@/hooks/use-toast";
import axios from "axios";

interface LoadLayoutDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  layouts: string[];
  onLoad: (layoutName: string) => void;
  onDelete?: (layoutName: string) => void;
  projectPath?: string;
}

export default function LoadLayoutDialog({
  open,
  onOpenChange,
  layouts,
  onLoad,
  onDelete,
  projectPath,
}: LoadLayoutDialogProps) {
  const [deletingLayout, setDeletingLayout] = useState<string | null>(null);
  const { toast } = useToast();

  const handleLoad = (layoutName: string) => {
    onLoad(layoutName);
    onOpenChange(false);
  };

  const handleDelete = async (layoutName: string, e: React.MouseEvent) => {
    e.stopPropagation();
    
    if (!projectPath) {
      toast({
        title: "Error",
        description: "No project path provided",
        variant: "destructive",
      });
      return;
    }

    setDeletingLayout(layoutName);
    
    try {
      await axios.delete(`/api/workspace/layout`, {
        params: {
          projectPath: projectPath,
          layoutName: layoutName,
        },
      });

      toast({
        title: "Layout Deleted",
        description: `Layout "${layoutName}" has been deleted`,
      });

      if (onDelete) {
        onDelete(layoutName);
      }
    } catch (error: any) {
      console.error("[LoadLayout] Error deleting layout:", error);
      toast({
        title: "Error",
        description: error.response?.data?.detail || "Failed to delete layout",
        variant: "destructive",
      });
    } finally {
      setDeletingLayout(null);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[540px]">
        <DialogHeader>
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-primary/10 rounded-lg">
              <FolderOpen className="h-5 w-5 text-primary" />
            </div>
            <div>
              <DialogTitle className="text-xl">Load Workspace Layout</DialogTitle>
              <DialogDescription className="mt-1">
                Restore a previously saved window arrangement and panel configuration
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>
        
        <div className="py-4">
          <ScrollArea className="max-h-[400px] pr-4">
            {layouts.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <div className="p-4 bg-muted/50 rounded-full mb-4">
                  <Layout className="h-12 w-12 text-muted-foreground/50" />
                </div>
                <p className="text-base font-medium text-foreground mb-1">
                  No saved layouts yet
                </p>
                <p className="text-sm text-muted-foreground max-w-[280px]">
                  Save your first layout from the Dock menu to restore it later
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                <div className="flex items-center gap-2 mb-3 px-1">
                  <Sparkles className="h-3.5 w-3.5 text-muted-foreground" />
                  <p className="text-xs text-muted-foreground font-medium">
                    {layouts.length} saved layout{layouts.length !== 1 ? 's' : ''} available
                  </p>
                </div>
                
                {layouts.map((layoutName, index) => (
                  <div
                    key={layoutName}
                    className="group relative flex items-center justify-between p-4 border border-border rounded-lg hover:border-primary/50 hover:bg-accent/50 transition-all cursor-pointer"
                    onClick={() => handleLoad(layoutName)}
                  >
                    <div className="flex items-center gap-3 flex-1 min-w-0">
                      <div className="p-2 bg-primary/10 rounded-md group-hover:bg-primary/20 transition-colors">
                        <Layout className="h-4 w-4 text-primary" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-foreground truncate">
                          {layoutName}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          Layout #{index + 1}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {layoutName !== "default" && (
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={(e) => handleDelete(layoutName, e)}
                          disabled={deletingLayout === layoutName}
                          className="opacity-0 group-hover:opacity-100 transition-opacity hover:bg-destructive hover:text-destructive-foreground"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      )}
                      <Button 
                        size="sm" 
                        variant="ghost"
                        className="group-hover:bg-primary group-hover:text-primary-foreground transition-colors"
                      >
                        Load
                        <ChevronRight className="h-3.5 w-3.5 ml-1" />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </ScrollArea>
        </div>
      </DialogContent>
    </Dialog>
  );
}
