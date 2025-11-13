import { useState, useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { FileText, Calendar } from "lucide-react";

interface Project {
  fileName: string;
  name: string;
  path: string;
  wellCount: number;
  createdAt: string;
  updatedAt: string;
}

interface ProjectListDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSelectProject: (fileName: string) => Promise<any>;
}

export default function ProjectListDialog({
  open,
  onOpenChange,
  onSelectProject,
}: ProjectListDialogProps) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (open) {
      fetchProjects();
    }
  }, [open]);

  const fetchProjects = async () => {
    setLoading(true);
    try {
      const response = await fetch('/api/projects/list');
      const result = await response.json();
      if (result.success) {
        setProjects(result.projects);
      }
    } catch (error) {
      console.error('Error fetching projects:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSelect = async (fileName: string) => {
    try {
      await onSelectProject(fileName);
      onOpenChange(false);
    } catch (error) {
      console.error('Error selecting project:', error);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[600px]">
        <DialogHeader>
          <DialogTitle>Load Project</DialogTitle>
          <DialogDescription>
            Select a project to load from the database folder
          </DialogDescription>
        </DialogHeader>
        
        <div className="mt-4 max-h-[400px] overflow-y-auto">
          {loading ? (
            <div className="text-center py-8 text-muted-foreground">
              Loading projects...
            </div>
          ) : projects.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              No saved projects found
            </div>
          ) : (
            <div className="space-y-2">
              {projects.map((project) => (
                <div
                  key={project.fileName}
                  className="border rounded-lg p-4 hover:bg-accent cursor-pointer transition-colors"
                  onClick={() => handleSelect(project.fileName)}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <FileText className="w-4 h-4 text-primary" />
                        <h3 className="font-semibold">{project.name}</h3>
                      </div>
                      <p className="text-sm text-muted-foreground truncate">
                        {project.path}
                      </p>
                      <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
                        <span>{project.wellCount} wells</span>
                        <div className="flex items-center gap-1">
                          <Calendar className="w-3 h-3" />
                          <span>{new Date(project.updatedAt).toLocaleDateString()}</span>
                        </div>
                      </div>
                    </div>
                    <Button size="sm" variant="outline">
                      Load
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
