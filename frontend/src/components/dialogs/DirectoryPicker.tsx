import { useState, useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  ContextMenu,
  ContextMenuContent,
  ContextMenuItem,
  ContextMenuTrigger,
} from "@/components/ui/context-menu";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Folder, ArrowUp, FolderPlus, Pencil, Trash2 } from "lucide-react";
import { useToast } from "@/hooks/use-toast";

interface DirectoryPickerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSelectPath: (path: string) => void;
  initialPath?: string;
  currentProjectPath?: string;
  onProjectDeleted?: () => void;
}

interface Directory {
  name: string;
  path: string;
}

interface DirectoryResponse {
  currentPath: string;
  parentPath: string;
  directories: Directory[];
  canGoUp?: boolean;
}

export default function DirectoryPicker({
  open,
  onOpenChange,
  onSelectPath,
  initialPath,
  currentProjectPath,
  onProjectDeleted,
}: DirectoryPickerProps) {
  // Support multiple OS paths with fallback
  const getWorkspaceRoot = () => {
    // Detect OS based on path format or use default
    if (typeof window !== 'undefined') {
      // Check if Windows path (starts with C:\ or similar)
      const isWindows = navigator.platform.toLowerCase().includes('win');
      if (isWindows) {
        return "C:\\petrophysics-workplace";
      }
    }
    // Default to Linux/Unix path
    return "/home/runner/workspace/petrophysics-workplace";
  };
  
  // Alternative paths to try if primary fails
  const alternativePaths = [
    "/home/runner/workspace/petrophysics-workplace",
    "C:\\petrophysics-workplace",
    "/root/petrophysics-workplace",
    "./petrophysics-workplace",
  ];
  
  const [workspaceRoot, setWorkspaceRoot] = useState(getWorkspaceRoot());
  const [currentPath, setCurrentPath] = useState(initialPath || workspaceRoot);
  const [parentPath, setParentPath] = useState("");
  const [directories, setDirectories] = useState<Directory[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [canGoUp, setCanGoUp] = useState(false);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [newFolderName, setNewFolderName] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [showRenameDialog, setShowRenameDialog] = useState(false);
  const [selectedFolder, setSelectedFolder] = useState<Directory | null>(null);
  const [selectedFolderForPick, setSelectedFolderForPick] = useState<Directory | null>(null);
  const [renameFolderName, setRenameFolderName] = useState("");
  const [isDeleting, setIsDeleting] = useState(false);
  const [isRenaming, setIsRenaming] = useState(false);
  const { toast } = useToast();

  const loadDirectories = async (path: string, tryAlternatives: boolean = false) => {
    setIsLoading(true);
    try {
      const response = await fetch(
        `/api/directories/list?path=${encodeURIComponent(path)}`,
      );

      if (!response.ok) {
        const errorData = await response.json();
        
        // If path fails and we haven't tried alternatives yet, try them
        if (tryAlternatives && response.status === 403) {
          for (const altPath of alternativePaths) {
            if (altPath === path) continue; // Skip the path we just tried
            
            try {
              const altResponse = await fetch(
                `/api/directories/list?path=${encodeURIComponent(altPath)}`,
              );
              
              if (altResponse.ok) {
                const altData: DirectoryResponse = await altResponse.json();
                setWorkspaceRoot(altPath);
                setCurrentPath(altData.currentPath);
                setParentPath(altData.parentPath);
                setDirectories(altData.directories);
                setCanGoUp(altData.canGoUp ?? true);
                
                toast({
                  title: "Path Updated",
                  description: `Using alternative path: ${altPath}`,
                });
                setIsLoading(false);
                return; // Success, exit function
              }
            } catch (e) {
              // Continue to next alternative
              continue;
            }
          }
        }
        
        throw new Error(errorData.error || "Failed to load directories");
      }

      const data: DirectoryResponse = await response.json();
      setCurrentPath(data.currentPath);
      setParentPath(data.parentPath);
      setDirectories(data.directories);
      setCanGoUp(data.canGoUp ?? true);
    } catch (error) {
      toast({
        title: "Error",
        description:
          error instanceof Error ? error.message : "Failed to load directories",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (open) {
      const pathToLoad = initialPath || workspaceRoot;
      
      // If initialPath is provided and it's a project folder (not workspace root),
      // navigate to parent directory
      if (initialPath && initialPath !== workspaceRoot && initialPath !== "") {
        // Normalize path separators (handle both / and \)
        const normalizedPath = initialPath.replace(/\\/g, '/');
        const pathParts = normalizedPath.split('/').filter(p => p);
        
        // Construct parent path preserving the leading separator
        const isAbsolutePath = normalizedPath.startsWith('/');
        const parentPathParts = pathParts.slice(0, -1);
        const parentPath = (isAbsolutePath ? '/' : '') + parentPathParts.join('/');
        
        if (parentPath && parentPath !== normalizedPath && parentPathParts.length > 0) {
          // Load parent directory (selection will happen in separate effect)
          loadDirectories(parentPath, true);
        } else {
          // If we can't determine parent, just load the path
          loadDirectories(pathToLoad, true);
        }
      } else {
        // Try alternative paths if initial path fails
        loadDirectories(pathToLoad, true);
      }
    }
  }, [open]);

  // Separate effect to select the project folder after directories are loaded
  useEffect(() => {
    if (open && initialPath && initialPath !== workspaceRoot && initialPath !== "" && directories.length > 0) {
      // Normalize path and extract folder name
      const normalizedPath = initialPath.replace(/\\/g, '/');
      const pathParts = normalizedPath.split('/').filter(p => p);
      const folderName = pathParts[pathParts.length - 1];
      
      const projectFolder = directories.find(dir => 
        dir.name === folderName || dir.path === initialPath || dir.path === normalizedPath
      );
      
      if (projectFolder) {
        setSelectedFolderForPick(projectFolder);
      }
    }
  }, [open, initialPath, directories]);

  const handleSelectDirectory = (dirPath: string) => {
    loadDirectories(dirPath);
  };

  const handleGoUp = () => {
    if (canGoUp && parentPath) {
      loadDirectories(parentPath);
    }
  };

  const handleCreateFolder = async () => {
    if (!newFolderName.trim()) {
      toast({
        title: "Error",
        description: "Please enter a folder name",
        variant: "destructive",
      });
      return;
    }

    setIsCreating(true);
    try {
      const response = await fetch("/api/directories/create", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          parentPath: currentPath,
          folderName: newFolderName.trim(),
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || "Failed to create folder");
      }

      toast({
        title: "Success",
        description: "Folder created successfully",
      });

      setNewFolderName("");
      setShowCreateDialog(false);
      loadDirectories(currentPath);
    } catch (error) {
      toast({
        title: "Error",
        description:
          error instanceof Error ? error.message : "Failed to create folder",
        variant: "destructive",
      });
    } finally {
      setIsCreating(false);
    }
  };

  const handleConfirm = () => {
    // Use selected folder if one is chosen, otherwise use current path
    const pathToSelect = selectedFolderForPick ? selectedFolderForPick.path : currentPath;
    onSelectPath(pathToSelect);
    onOpenChange(false);
    setSelectedFolderForPick(null);
  };

  const handleFolderClick = (dir: Directory) => {
    // Single click to select folder
    setSelectedFolderForPick(dir);
  };

  const handleFolderDoubleClick = (dir: Directory) => {
    // Double click to navigate into folder
    loadDirectories(dir.path);
    setSelectedFolderForPick(null);
  };

  const handleDeleteFolder = async () => {
    if (!selectedFolder) return;

    const isCurrentProject = currentProjectPath && 
      (selectedFolder.path === currentProjectPath || 
       currentProjectPath.startsWith(selectedFolder.path + '/'));

    setIsDeleting(true);
    try {
      const response = await fetch("/api/directories/delete", {
        method: "DELETE",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          folderPath: selectedFolder.path,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || "Failed to delete folder");
      }

      toast({
        title: "Success",
        description: "Folder deleted successfully",
      });

      // If the deleted folder is the current project, notify parent to reload
      if (isCurrentProject && onProjectDeleted) {
        onProjectDeleted();
      }

      setShowDeleteDialog(false);
      setSelectedFolder(null);
      loadDirectories(currentPath);
    } catch (error) {
      toast({
        title: "Error",
        description:
          error instanceof Error ? error.message : "Failed to delete folder",
        variant: "destructive",
      });
    } finally {
      setIsDeleting(false);
    }
  };

  const handleRenameFolder = async () => {
    if (!selectedFolder || !renameFolderName.trim()) {
      toast({
        title: "Error",
        description: "Please enter a new folder name",
        variant: "destructive",
      });
      return;
    }

    setIsRenaming(true);
    try {
      const response = await fetch("/api/directories/rename", {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          folderPath: selectedFolder.path,
          newName: renameFolderName.trim(),
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || "Failed to rename folder");
      }

      toast({
        title: "Success",
        description: "Folder renamed successfully",
      });

      setRenameFolderName("");
      setShowRenameDialog(false);
      setSelectedFolder(null);
      loadDirectories(currentPath);
    } catch (error) {
      toast({
        title: "Error",
        description:
          error instanceof Error ? error.message : "Failed to rename folder",
        variant: "destructive",
      });
    } finally {
      setIsRenaming(false);
    }
  };

  const handleContextMenuRename = (dir: Directory) => {
    setSelectedFolder(dir);
    setRenameFolderName(dir.name);
    setShowRenameDialog(true);
  };

  const handleContextMenuDelete = (dir: Directory) => {
    setSelectedFolder(dir);
    setShowDeleteDialog(true);
  };

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="w-[95vw] max-w-[95vw] sm:max-w-[80vw] md:max-w-[70vw] lg:max-w-[60vw] max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="text-base sm:text-lg">Select Folder</DialogTitle>
            <DialogDescription className="text-xs sm:text-sm">
              Click to select a folder, double-click to navigate into it
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-3 sm:gap-4 py-2 sm:py-4">
            <div className="flex items-center gap-1 sm:gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={handleGoUp}
                disabled={isLoading || !canGoUp}
                title="Go up one level"
                className="h-8 w-8 p-0 shrink-0"
              >
                <ArrowUp className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
              </Button>
              <div className="flex-1 px-2 sm:px-3 py-1.5 sm:py-2 bg-muted rounded-md font-mono text-[10px] sm:text-xs truncate">
                {currentPath === workspaceRoot 
                  ? "petrophysics-workplace" 
                  : currentPath.replace(workspaceRoot + "/", "")}
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowCreateDialog(true)}
                disabled={isLoading}
                title="Create new folder"
                className="h-8 px-2 sm:px-3 shrink-0"
              >
                <FolderPlus className="w-3.5 h-3.5 sm:w-4 sm:h-4 sm:mr-2" />
                <span className="hidden sm:inline">New Folder</span>
              </Button>
            </div>

            <ScrollArea className="h-[250px] sm:h-[350px] border rounded-md">
              <div className="p-2 sm:p-4">
                {isLoading ? (
                  <div className="text-center py-8 sm:py-12 text-muted-foreground text-xs sm:text-sm">
                    Loading directories...
                  </div>
                ) : directories.length === 0 ? (
                  <div className="text-center py-8 sm:py-12 text-muted-foreground">
                    <Folder className="w-8 h-8 sm:w-12 sm:h-12 mx-auto mb-2 sm:mb-3 opacity-50" />
                    <p className="text-xs sm:text-sm">No folders found</p>
                    <p className="text-[10px] sm:text-sm mt-1">
                      Create a new folder to get started
                    </p>
                  </div>
                ) : (
                  <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2 sm:gap-3">
                    {directories.map((dir) => (
                      <ContextMenu key={dir.path}>
                        <ContextMenuTrigger>
                          <button
                            onClick={() => handleFolderClick(dir)}
                            onDoubleClick={() => handleFolderDoubleClick(dir)}
                            className={`
                              flex flex-col items-center gap-1.5 sm:gap-2 p-1.5 sm:p-2 text-center 
                              rounded-lg sm:rounded-xl transition-all duration-200 w-full min-h-[80px] sm:min-h-[100px]
                              ${selectedFolderForPick?.path === dir.path 
                                ? 'bg-primary/10 border-2 border-primary shadow-lg scale-105' 
                                : 'bg-background hover:bg-accent border-2 border-transparent hover:border-primary/20'
                              }
                            `}
                          >
                            <div className={`
                              p-2 sm:p-3 rounded-full transition-colors
                              ${selectedFolderForPick?.path === dir.path 
                                ? 'bg-primary/20' 
                                : 'bg-blue-500/10'
                              }
                            `}>
                              <Folder className={`
                                w-8 h-8 sm:w-12 sm:h-12 flex-shrink-0 transition-colors
                                ${selectedFolderForPick?.path === dir.path 
                                  ? 'text-primary' 
                                  : 'text-blue-500'
                                }
                              `} />
                            </div>
                            <span
                              className={`
                                text-xs sm:text-sm font-medium w-full break-words line-clamp-2
                                ${selectedFolderForPick?.path === dir.path 
                                  ? 'text-primary font-semibold' 
                                  : ''
                                }
                              `}
                              title={dir.name}
                            >
                              {dir.name}
                            </span>
                          </button>
                        </ContextMenuTrigger>
                        <ContextMenuContent>
                          <ContextMenuItem
                            onClick={() => handleContextMenuRename(dir)}
                          >
                            <Pencil className="w-4 h-4 mr-2" />
                            Rename
                          </ContextMenuItem>
                          <ContextMenuItem
                            onClick={() => handleContextMenuDelete(dir)}
                            className="text-destructive focus:text-destructive"
                          >
                            <Trash2 className="w-4 h-4 mr-2" />
                            Delete
                          </ContextMenuItem>
                        </ContextMenuContent>
                      </ContextMenu>
                    ))}
                  </div>
                )}
              </div>
            </ScrollArea>
          </div>

          <DialogFooter className="flex-col sm:flex-row gap-2 sm:gap-0">
            <Button
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={isLoading}
              className="w-full sm:w-auto text-xs sm:text-sm"
            >
              Cancel
            </Button>
            <Button onClick={handleConfirm} disabled={isLoading} className="w-full sm:w-auto text-xs sm:text-sm">
              {selectedFolderForPick ? `Select "${selectedFolderForPick.name}"` : 'Select Current Folder'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>Create New Folder</DialogTitle>
            <DialogDescription>
              Enter a name for the new folder (letters, numbers, hyphens, and
              underscores only)
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <Input
              placeholder="Folder name"
              value={newFolderName}
              onChange={(e) => setNewFolderName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !isCreating) {
                  handleCreateFolder();
                }
              }}
              disabled={isCreating}
            />
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setShowCreateDialog(false);
                setNewFolderName("");
              }}
              disabled={isCreating}
            >
              Cancel
            </Button>
            <Button onClick={handleCreateFolder} disabled={isCreating}>
              {isCreating ? "Creating..." : "Create Folder"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={showRenameDialog} onOpenChange={setShowRenameDialog}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>Rename Folder</DialogTitle>
            <DialogDescription>
              Enter a new name for the folder (letters, numbers, hyphens, and
              underscores only)
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <Input
              placeholder="New folder name"
              value={renameFolderName}
              onChange={(e) => setRenameFolderName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !isRenaming) {
                  handleRenameFolder();
                }
              }}
              disabled={isRenaming}
            />
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setShowRenameDialog(false);
                setRenameFolderName("");
                setSelectedFolder(null);
              }}
              disabled={isRenaming}
            >
              Cancel
            </Button>
            <Button onClick={handleRenameFolder} disabled={isRenaming}>
              {isRenaming ? "Renaming..." : "Rename"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Folder</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete "{selectedFolder?.name}"? This
              action cannot be undone and will permanently delete the folder and
              all its contents.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel
              onClick={() => {
                setShowDeleteDialog(false);
                setSelectedFolder(null);
              }}
              disabled={isDeleting}
            >
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteFolder}
              disabled={isDeleting}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {isDeleting ? "Deleting..." : "Delete"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
