import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { FolderOpen } from "lucide-react";
import DirectoryPicker from "./DirectoryPicker";

interface NewProjectDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export default function NewProjectDialog({ open, onOpenChange }: NewProjectDialogProps) {
  const [projectName, setProjectName] = useState("");
  const [projectPath, setProjectPath] = useState("/home/runner/workspace/petrophysics-workplace");
  const [isCreating, setIsCreating] = useState(false);
  const [showDirectoryPicker, setShowDirectoryPicker] = useState(false);
  const { toast } = useToast();

  const getFullProjectPath = () => {
    if (projectName.trim() && projectPath.trim()) {
      return `${projectPath.trim()}/${projectName.trim()}`;
    }
    if (projectPath.trim()) {
      return `${projectPath.trim()}/[project-name]`;
    }
    return "/path/to/project/[project-name]";
  };

  const handleCreateProject = async () => {
    if (!projectName.trim()) {
      toast({
        title: "Error",
        description: "Please enter a project name",
        variant: "destructive",
      });
      return;
    }

    if (!projectPath.trim()) {
      toast({
        title: "Error",
        description: "Please enter a project path",
        variant: "destructive",
      });
      return;
    }

    if (!/^[a-zA-Z0-9_-]+$/.test(projectName.trim())) {
      toast({
        title: "Error",
        description: "Project name can only contain letters, numbers, hyphens, and underscores",
        variant: "destructive",
      });
      return;
    }

    setIsCreating(true);

    try {
      const response = await fetch("/api/projects/create", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          name: projectName,
          path: projectPath,
        }),
      });

      if (!response.ok) {
        throw new Error("Failed to create project");
      }

      const result = await response.json();

      toast({
        title: "Success",
        description: `Project "${projectName}" created successfully. Opening project...`,
      });

      setProjectName("");
      onOpenChange(false);
      
      // Reload page to load the newly created project
      setTimeout(() => {
        window.location.reload();
      }, 500);
    } catch (error: any) {
      const errorMessage = error.message || "Failed to create project. Please try again.";
      toast({
        title: "Error",
        description: errorMessage,
        variant: "destructive",
      });
    } finally {
      setIsCreating(false);
    }
  };

  const handleDialogClose = (open: boolean) => {
    if (!open && !isCreating) {
      setProjectName("");
      setProjectPath("/home/runner/workspace/petrophysics-workplace");
    }
    onOpenChange(open);
  };

  const handleChoosePath = () => {
    setShowDirectoryPicker(true);
  };

  const handlePathSelected = (path: string) => {
    setProjectPath(path);
  };

  return (
    <Dialog open={open} onOpenChange={handleDialogClose}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>Create New Project</DialogTitle>
          <DialogDescription>
            Enter a project name to create a new project with the standard folder structure.
          </DialogDescription>
        </DialogHeader>
        
        <div className="grid gap-4 py-4">
          <div className="grid gap-2">
            <Label htmlFor="project-name">Project Name</Label>
            <Input
              id="project-name"
              placeholder="Enter project name (e.g., MyProject)"
              value={projectName}
              onChange={(e) => setProjectName(e.target.value)}
              disabled={isCreating}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !isCreating) {
                  handleCreateProject();
                }
              }}
            />
          </div>

          <div className="grid gap-2">
            <Label htmlFor="project-path">Project Path</Label>
            <div className="flex gap-2">
              <Input
                id="project-path"
                placeholder="Enter or choose project path"
                value={projectPath}
                onChange={(e) => setProjectPath(e.target.value)}
                disabled={isCreating}
                className="font-mono text-sm flex-1"
              />
              <Button
                type="button"
                variant="outline"
                size="icon"
                onClick={handleChoosePath}
                disabled={isCreating}
                title="Choose file path"
              >
                <FolderOpen className="w-4 h-4" />
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">
              Full path: <span className="font-mono">{getFullProjectPath()}</span>
            </p>
          </div>
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={isCreating}
          >
            Cancel
          </Button>
          <Button onClick={handleCreateProject} disabled={isCreating}>
            {isCreating ? "Creating..." : "Create Project"}
          </Button>
        </DialogFooter>
      </DialogContent>

      <DirectoryPicker
        open={showDirectoryPicker}
        onOpenChange={setShowDirectoryPicker}
        onSelectPath={handlePathSelected}
        initialPath={projectPath}
      />
    </Dialog>
  );
}
