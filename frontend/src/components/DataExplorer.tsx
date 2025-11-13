import { useState, useEffect } from "react";
import {
  Dialog,
  DialogContent,
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
import { Folder, FolderOpen, File, ArrowUp, FolderPlus, Pencil, Trash2, List, Grid3x3, FileText } from "lucide-react";
import { useToast } from "@/hooks/use-toast";

interface DataExplorerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

interface FileItem {
  name: string;
  path: string;
  type: "file" | "directory";
  hasFiles?: boolean;
}

interface DataResponse {
  currentPath: string;
  parentPath: string;
  items: FileItem[];
  canGoUp?: boolean;
}

type ViewMode = "grid" | "list";

export default function DataExplorer({
  open,
  onOpenChange,
}: DataExplorerProps) {
  const workspaceRoot = "/home/runner/workspace/petrophysics-workplace";
  const [currentPath, setCurrentPath] = useState(workspaceRoot);
  const [parentPath, setParentPath] = useState("");
  const [items, setItems] = useState<FileItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [canGoUp, setCanGoUp] = useState(false);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [newFolderName, setNewFolderName] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [showRenameDialog, setShowRenameDialog] = useState(false);
  const [selectedItem, setSelectedItem] = useState<FileItem | null>(null);
  const [renameItemName, setRenameItemName] = useState("");
  const [isDeleting, setIsDeleting] = useState(false);
  const [isRenaming, setIsRenaming] = useState(false);
  const [viewMode, setViewMode] = useState<ViewMode>("grid");
  const [showFilePreview, setShowFilePreview] = useState(false);
  const [fileContent, setFileContent] = useState<string>("");
  const [selectedFile, setSelectedFile] = useState<FileItem | null>(null);
  const [isLoadingFile, setIsLoadingFile] = useState(false);
  const { toast } = useToast();

  const loadData = async (path: string) => {
    setIsLoading(true);
    try {
      const response = await fetch(
        `/api/data/list?path=${encodeURIComponent(path)}`,
      );

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || "Failed to load data");
      }

      const data: DataResponse = await response.json();
      setCurrentPath(data.currentPath);
      setParentPath(data.parentPath);
      setItems(data.items);
      setCanGoUp(data.canGoUp ?? true);
    } catch (error) {
      toast({
        title: "Error",
        description:
          error instanceof Error ? error.message : "Failed to load data",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (open) {
      loadData(workspaceRoot);
    }
  }, [open]);

  const handleSelectItem = async (item: FileItem) => {
    if (item.type === "directory") {
      loadData(item.path);
    } else {
      // Load file content
      await loadFileContent(item);
    }
  };

  const loadFileContent = async (file: FileItem) => {
    setIsLoadingFile(true);
    setSelectedFile(file);
    setShowFilePreview(true);
    
    try {
      const response = await fetch(
        `/api/data/file?path=${encodeURIComponent(file.path)}`
      );

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || "Failed to load file");
      }

      const data = await response.json();
      
      // Format content for display
      if (typeof data.content === 'object') {
        setFileContent(JSON.stringify(data.content, null, 2));
      } else {
        setFileContent(data.content);
      }
    } catch (error) {
      toast({
        title: "Error",
        description:
          error instanceof Error ? error.message : "Failed to load file",
        variant: "destructive",
      });
      setShowFilePreview(false);
    } finally {
      setIsLoadingFile(false);
    }
  };

  const handleGoUp = () => {
    if (canGoUp && parentPath) {
      loadData(parentPath);
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
      loadData(currentPath);
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

  const handleDeleteItem = async () => {
    if (!selectedItem) return;

    setIsDeleting(true);
    try {
      const response = await fetch("/api/directories/delete", {
        method: "DELETE",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          folderPath: selectedItem.path,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || "Failed to delete item");
      }

      toast({
        title: "Success",
        description: `${selectedItem.type === 'directory' ? 'Folder' : 'File'} deleted successfully`,
      });

      setShowDeleteDialog(false);
      setSelectedItem(null);
      loadData(currentPath);
    } catch (error) {
      toast({
        title: "Error",
        description:
          error instanceof Error ? error.message : "Failed to delete item",
        variant: "destructive",
      });
    } finally {
      setIsDeleting(false);
    }
  };

  const handleRenameItem = async () => {
    if (!selectedItem || !renameItemName.trim()) return;

    setIsRenaming(true);
    try {
      const response = await fetch("/api/directories/rename", {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          folderPath: selectedItem.path,
          newName: renameItemName.trim(),
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || "Failed to rename item");
      }

      toast({
        title: "Success",
        description: `${selectedItem.type === 'directory' ? 'Folder' : 'File'} renamed successfully`,
      });

      setShowRenameDialog(false);
      setSelectedItem(null);
      setRenameItemName("");
      loadData(currentPath);
    } catch (error) {
      toast({
        title: "Error",
        description:
          error instanceof Error ? error.message : "Failed to rename item",
        variant: "destructive",
      });
    } finally {
      setIsRenaming(false);
    }
  };

  const openRenameDialog = (item: FileItem) => {
    setSelectedItem(item);
    setRenameItemName(item.name);
    setShowRenameDialog(true);
  };

  const openDeleteDialog = (item: FileItem) => {
    setSelectedItem(item);
    setShowDeleteDialog(true);
  };

  const getDisplayPath = () => {
    return currentPath.replace(workspaceRoot + '/', '');
  };

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="max-w-5xl h-full flex flex-col p-0">
          <DialogHeader className="px-6 pt-6 pb-0">
            <DialogTitle className="sr-only">Data Explorer</DialogTitle>
          </DialogHeader>

          <div className="flex items-center justify-between px-6 py-4 border-b">
            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                size="icon"
                onClick={handleGoUp}
                disabled={!canGoUp || isLoading}
                className="h-8 w-8"
              >
                <ArrowUp className="w-4 h-4" />
              </Button>
              <span className="text-sm font-medium text-muted-foreground">
                {getDisplayPath()}
              </span>
            </div>

            <div className="flex items-center gap-2">
              <div className="flex border rounded-md">
                <Button
                  variant={viewMode === "grid" ? "secondary" : "ghost"}
                  size="sm"
                  onClick={() => setViewMode("grid")}
                  className="h-8 rounded-r-none"
                >
                  <Grid3x3 className="w-4 h-4" />
                </Button>
                <Button
                  variant={viewMode === "list" ? "secondary" : "ghost"}
                  size="sm"
                  onClick={() => setViewMode("list")}
                  className="h-8 rounded-l-none"
                >
                  <List className="w-4 h-4" />
                </Button>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowCreateDialog(true)}
                disabled={isLoading}
                className="h-8"
              >
                <FolderPlus className="w-4 h-4 mr-2" />
                New Folder
              </Button>
            </div>
          </div>

          <ScrollArea className="flex-1 px-6">
            {isLoading ? (
              <div className="flex items-center justify-center h-64 text-muted-foreground">
                Loading...
              </div>
            ) : items.length === 0 ? (
              <div className="flex items-center justify-center h-64 text-muted-foreground">
                No items found
              </div>
            ) : viewMode === "grid" ? (
              <div className="grid grid-cols-6 gap-4 py-6">
                {items.map((item) => (
                  <ContextMenu key={item.path}>
                    <ContextMenuTrigger>
                      <div
                        className="flex flex-col items-center gap-2 p-4 rounded-lg hover:bg-accent cursor-pointer transition-colors"
                        onClick={() => handleSelectItem(item)}
                      >
                        {item.type === "directory" ? (
                          <div className="w-16 h-16 rounded-2xl bg-blue-100 dark:bg-blue-900/20 flex items-center justify-center relative">
                            {item.hasFiles ? (
                              <FolderOpen className="w-10 h-10 text-blue-500" />
                            ) : (
                              <Folder className="w-10 h-10 text-blue-400" />
                            )}
                            {item.hasFiles && (
                              <div className="absolute bottom-1 right-1 bg-white dark:bg-slate-900 rounded-full p-0.5">
                                <FileText className="w-3 h-3 text-blue-600" />
                              </div>
                            )}
                          </div>
                        ) : (
                          <div className="w-16 h-16 rounded-2xl bg-gray-100 dark:bg-gray-800 flex items-center justify-center">
                            <FileText className="w-8 h-8 text-gray-500" />
                          </div>
                        )}
                        <span className="text-sm text-center truncate w-full">
                          {item.name}
                        </span>
                      </div>
                    </ContextMenuTrigger>
                    <ContextMenuContent>
                      <ContextMenuItem onClick={() => openRenameDialog(item)}>
                        <Pencil className="w-4 h-4 mr-2" />
                        Rename
                      </ContextMenuItem>
                      <ContextMenuItem 
                        onClick={() => openDeleteDialog(item)}
                        className="text-destructive focus:text-destructive"
                      >
                        <Trash2 className="w-4 h-4 mr-2" />
                        Delete
                      </ContextMenuItem>
                    </ContextMenuContent>
                  </ContextMenu>
                ))}
              </div>
            ) : (
              <div className="py-4 space-y-1">
                {items.map((item) => (
                  <ContextMenu key={item.path}>
                    <ContextMenuTrigger>
                      <div
                        className="flex items-center gap-3 p-2 rounded hover:bg-accent cursor-pointer"
                        onClick={() => handleSelectItem(item)}
                      >
                        {item.type === "directory" ? (
                          <div className="relative">
                            {item.hasFiles ? (
                              <FolderOpen className="w-5 h-5 text-blue-500" />
                            ) : (
                              <Folder className="w-5 h-5 text-blue-400" />
                            )}
                            {item.hasFiles && (
                              <div className="absolute -bottom-0.5 -right-0.5 bg-white dark:bg-slate-900 rounded-full p-0.5">
                                <FileText className="w-2 h-2 text-blue-600" />
                              </div>
                            )}
                          </div>
                        ) : (
                          <File className="w-5 h-5 text-gray-500" />
                        )}
                        <span className="text-sm">{item.name}</span>
                      </div>
                    </ContextMenuTrigger>
                    <ContextMenuContent>
                      <ContextMenuItem onClick={() => openRenameDialog(item)}>
                        <Pencil className="w-4 h-4 mr-2" />
                        Rename
                      </ContextMenuItem>
                      <ContextMenuItem 
                        onClick={() => openDeleteDialog(item)}
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
          </ScrollArea>
        </DialogContent>
      </Dialog>

      <AlertDialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Create New Folder</AlertDialogTitle>
            <AlertDialogDescription>
              Enter a name for the new folder
            </AlertDialogDescription>
          </AlertDialogHeader>
          <Input
            value={newFolderName}
            onChange={(e) => setNewFolderName(e.target.value)}
            placeholder="Folder name"
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                handleCreateFolder();
              }
            }}
          />
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleCreateFolder} disabled={isCreating}>
              {isCreating ? "Creating..." : "Create"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={showRenameDialog} onOpenChange={setShowRenameDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Rename {selectedItem?.type === 'directory' ? 'Folder' : 'File'}</AlertDialogTitle>
            <AlertDialogDescription>
              Enter a new name for "{selectedItem?.name}"
            </AlertDialogDescription>
          </AlertDialogHeader>
          <Input
            value={renameItemName}
            onChange={(e) => setRenameItemName(e.target.value)}
            placeholder="New name"
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                handleRenameItem();
              }
            }}
          />
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleRenameItem} disabled={isRenaming}>
              {isRenaming ? "Renaming..." : "Rename"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete {selectedItem?.type === 'directory' ? 'Folder' : 'File'}</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete "{selectedItem?.name}"? This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteItem}
              disabled={isDeleting}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {isDeleting ? "Deleting..." : "Delete"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <Dialog open={showFilePreview} onOpenChange={setShowFilePreview}>
        <DialogContent className="max-w-4xl h-[600px] flex flex-col p-0">
          <DialogHeader className="px-6 pt-6 pb-4 border-b">
            <DialogTitle className="flex items-center gap-2">
              <FileText className="w-5 h-5" />
              {selectedFile?.name}
            </DialogTitle>
          </DialogHeader>

          <ScrollArea className="flex-1 px-6 py-4">
            {isLoadingFile ? (
              <div className="flex items-center justify-center h-full text-muted-foreground">
                Loading file...
              </div>
            ) : (
              <pre className="text-sm bg-muted p-4 rounded-lg overflow-x-auto">
                <code>{fileContent}</code>
              </pre>
            )}
          </ScrollArea>

          <div className="px-6 py-4 border-t flex justify-end">
            <Button onClick={() => setShowFilePreview(false)}>
              Close
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
