import { useState, useEffect, useRef } from "react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
} from "@/components/ui/dropdown-menu";
import { Check, Sun, Moon, Menu, X, Shield, ShieldOff, Clock, Download, Upload, Settings2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";
import NewProjectDialog from "../dialogs/NewProjectDialog";
import DataExplorer from "../DataExplorer";
import SaveLayoutDialog from "../dialogs/SaveLayoutDialog";
import LoadLayoutDialog from "../dialogs/LoadLayoutDialog";
import axios from "axios";

interface MenuBarProps {
  onTogglePanel: (panelId: string) => void;
  onOpenFloatingWindow?: (panelId: any) => void;
  onToggleWellLogPlotFloating?: () => void;
  wellLogPlotFloatingOpen?: boolean;
  visiblePanels: Set<string>;
  onSaveLayout: (layoutName?: string) => void;
  onLoadLayout: (layoutName?: string) => void;
  onResetLayout: () => void;
  theme: "light" | "dark";
  onToggleTheme: () => void;
  feedbackAutoScroll: boolean;
  onToggleFeedbackAutoScroll: () => void;
  projectPath: string;
  wellCount: number;
  onProjectPathChange: (path: string) => void;
  onSaveProject?: () => Promise<any>;
  onOpenProjectList?: () => void;
  onOpenImportPicker?: () => void;
  onOpenProjectPicker?: () => void;
  onNewWell?: () => void;
  onToggleMobileSidebar?: () => void;
  isMobileSidebarOpen?: boolean;
  currentLayoutName?: string;
}

export default function MenuBar({
  onTogglePanel,
  onOpenFloatingWindow,
  onToggleWellLogPlotFloating,
  wellLogPlotFloatingOpen,
  visiblePanels,
  onSaveLayout,
  onLoadLayout,
  onResetLayout,
  theme,
  onToggleTheme,
  feedbackAutoScroll,
  onToggleFeedbackAutoScroll,
  projectPath,
  wellCount,
  onProjectPathChange,
  onSaveProject,
  onOpenProjectList,
  onOpenImportPicker,
  onOpenProjectPicker,
  onNewWell,
  onToggleMobileSidebar,
  isMobileSidebarOpen,
  currentLayoutName = "default",
}: MenuBarProps) {
  const { toast } = useToast();
  const [newProjectDialogOpen, setNewProjectDialogOpen] = useState(false);
  const [dataExplorerOpen, setDataExplorerOpen] = useState(false);
  const [saveLayoutDialogOpen, setSaveLayoutDialogOpen] = useState(false);
  const [loadLayoutDialogOpen, setLoadLayoutDialogOpen] = useState(false);
  const [savedLayouts, setSavedLayouts] = useState<string[]>([]);
  const [deletePermissionEnabled, setDeletePermissionEnabled] = useState(false);
  const [permissionTimeLeft, setPermissionTimeLeft] = useState(0);
  const [sessionTimeLeft, setSessionTimeLeft] = useState(4 * 60 * 60); // 4 hours in seconds
  const [autoSaveTriggered, setAutoSaveTriggered] = useState(false);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const sessionTimerRef = useRef<NodeJS.Timeout | null>(null);

  // Load saved layouts when project path changes
  useEffect(() => {
    if (projectPath) {
      loadSavedLayoutsList();
    }
  }, [projectPath]);

  const loadSavedLayoutsList = async () => {
    if (!projectPath) {
      setSavedLayouts(['default']);
      return;
    }
    
    try {
      const response = await axios.get(`/api/workspace/layouts/list?projectPath=${encodeURIComponent(projectPath)}`);
      
      if (response.data && response.data.success === true) {
        const layouts = Array.isArray(response.data.layouts) ? response.data.layouts : [];
        if (layouts.length === 0) {
          setSavedLayouts(['default']);
        } else if (!layouts.includes('default')) {
          setSavedLayouts(['default', ...layouts]);
        } else {
          setSavedLayouts(layouts);
        }
      } else {
        console.warn('[MenuBar] API returned non-success response:', response.data);
        setSavedLayouts(['default']);
      }
    } catch (error) {
      console.error('[MenuBar] Error loading saved layouts:', error);
      setSavedLayouts(['default']);
    }
  };

  const handleSaveLayout = async (layoutName: string) => {
    await onSaveLayout(layoutName);
    await loadSavedLayoutsList(); // Refresh the list
  };

  const handleSaveCurrentLayout = async () => {
    await onSaveLayout(currentLayoutName);
    await loadSavedLayoutsList();
    toast({
      title: "Layout Saved",
      description: `Layout "${currentLayoutName}" has been saved successfully.`,
    });
  };

  const handleLoadLayout = async (layoutName: string) => {
    await onLoadLayout(layoutName);
  };

  useEffect(() => {
    if (deletePermissionEnabled && permissionTimeLeft > 0) {
      timerRef.current = setInterval(() => {
        setPermissionTimeLeft((prev) => {
          if (prev <= 1) {
            setDeletePermissionEnabled(false);
            if (timerRef.current) clearInterval(timerRef.current);
            toast({
              title: "Permission Expired",
              description: "Delete permission has been automatically disabled.",
            });
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
      return () => {
        if (timerRef.current) clearInterval(timerRef.current);
      };
    }
  }, [deletePermissionEnabled, permissionTimeLeft, toast]);

  const toggleDeletePermission = () => {
    if (!deletePermissionEnabled) {
      setDeletePermissionEnabled(true);
      setPermissionTimeLeft(60);
      toast({
        title: "Delete Permission Enabled",
        description: "You have 60 seconds to execute delete commands.",
      });
    } else {
      setDeletePermissionEnabled(false);
      setPermissionTimeLeft(0);
      if (timerRef.current) clearInterval(timerRef.current);
      toast({
        title: "Delete Permission Disabled",
        description: "Delete commands are now blocked.",
      });
    }
  };

  useEffect(() => {
    (window as any).deletePermissionEnabled = deletePermissionEnabled;
  }, [deletePermissionEnabled]);

  // Auto-save project data when session is about to expire
  const autoSaveProjectData = async () => {
    if (onSaveProject && !autoSaveTriggered) {
      try {
        await onSaveProject();
        toast({
          title: "Auto-Save Complete",
          description: "Project data automatically saved before session expires.",
        });
        setAutoSaveTriggered(true);
      } catch (error) {
        toast({
          title: "Auto-Save Failed",
          description: error instanceof Error ? error.message : "Failed to auto-save project",
          variant: "destructive",
        });
      }
    }
  };

  // Session timeout countdown
  useEffect(() => {
    sessionTimerRef.current = setInterval(() => {
      setSessionTimeLeft((prev) => {
        const newTime = prev - 1;
        
        // Auto-save when 5 minutes remaining
        if (newTime === 5 * 60 && !autoSaveTriggered) {
          autoSaveProjectData();
          toast({
            title: "Session Expiring Soon",
            description: "Session will expire in 5 minutes. Auto-saving project data...",
            variant: "destructive",
          });
        }
        
        // Warning at 2 minutes
        if (newTime === 2 * 60) {
          toast({
            title: "Session Expiring",
            description: "Session will expire in 2 minutes.",
            variant: "destructive",
          });
        }
        
        // Session expired
        if (newTime <= 1) {
          toast({
            title: "Session Expired",
            description: "Your well data session has expired. Please reload wells.",
            variant: "destructive",
          });
          setAutoSaveTriggered(false);
          return 4 * 60 * 60; // Reset to 4 hours
        }
        
        return newTime;
      });
    }, 1000);
    
    return () => {
      if (sessionTimerRef.current) clearInterval(sessionTimerRef.current);
    };
  }, [toast, autoSaveTriggered]);

  // Format session time
  const formatSessionTime = (seconds: number): string => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    return `${hours}h ${minutes}m ${secs}s`;
  };

  // Get session time styling based on remaining time
  const getSessionTimeStyle = (seconds: number) => {
    if (seconds > 2 * 60 * 60) {
      // > 2 hours - Green, safe and modern
      return {
        containerClass: "bg-gradient-to-br from-emerald-50 via-green-50 to-teal-50 dark:from-emerald-950/30 dark:via-green-950/30 dark:to-teal-950/30 border border-emerald-200 dark:border-emerald-800 shadow-lg shadow-emerald-100/50 dark:shadow-emerald-900/20 backdrop-blur-sm",
        iconClass: "text-emerald-600 dark:text-emerald-400",
        textClass: "text-emerald-900 dark:text-emerald-100 font-bold tracking-tight",
        label: "Session Active",
        labelClass: "text-emerald-600 dark:text-emerald-400 font-semibold",
        badge: "bg-emerald-500 dark:bg-emerald-500"
      };
    } else if (seconds > 30 * 60) {
      // 30 min - 2 hours - Amber warning with glow
      return {
        containerClass: "bg-gradient-to-br from-amber-50 via-yellow-50 to-orange-50 dark:from-amber-950/40 dark:via-yellow-950/40 dark:to-orange-950/40 border-2 border-amber-300 dark:border-amber-700 shadow-xl shadow-amber-200/60 dark:shadow-amber-900/30 backdrop-blur-sm",
        iconClass: "text-amber-600 dark:text-amber-400 animate-pulse",
        textClass: "text-amber-900 dark:text-amber-100 font-bold tracking-tight",
        label: "Session Expiring",
        labelClass: "text-amber-700 dark:text-amber-300 font-bold",
        badge: "bg-amber-500 dark:bg-amber-500 animate-pulse"
      };
    } else {
      // < 30 min - Critical red with intense glow and animation
      return {
        containerClass: "bg-gradient-to-br from-red-100 via-rose-100 to-pink-100 dark:from-red-950/50 dark:via-rose-950/50 dark:to-pink-950/50 border-2 border-red-500 dark:border-red-600 shadow-2xl shadow-red-400/70 dark:shadow-red-900/50 animate-pulse backdrop-blur-sm ring-2 ring-red-300/50 dark:ring-red-700/50",
        iconClass: "text-red-700 dark:text-red-300 animate-pulse",
        textClass: "text-red-950 dark:text-red-50 font-extrabold tracking-tight",
        label: "⚠ EXPIRING SOON",
        labelClass: "text-red-700 dark:text-red-300 font-extrabold animate-pulse",
        badge: "bg-red-600 dark:bg-red-500 animate-pulse"
      };
    }
  };

  const handleNewProject = () => {
    setNewProjectDialogOpen(true);
  };

  const handleOpen = () => {
    if (onOpenProjectPicker) {
      onOpenProjectPicker();
    }
  };

  const handleSave = async () => {
    if (onSaveProject) {
      try {
        await onSaveProject();
        toast({
          title: "Project Saved",
          description: "Your project data has been saved to database folder.",
        });
      } catch (error) {
        toast({
          title: "Save Failed",
          description: error instanceof Error ? error.message : "Failed to save project",
          variant: "destructive",
        });
      }
    } else {
      onSaveLayout();
      toast({
        title: "Layout Saved",
        description: "Your layout has been saved successfully.",
      });
    }
  };

  const handleImport = () => {
    if (onOpenImportPicker) {
      onOpenImportPicker();
    }
  };

  const handleExport = () => {
    const data = { layout: "current", timestamp: new Date().toISOString() };
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `project_${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
    toast({
      title: "Project Exported",
      description: "Your project has been exported successfully.",
    });
  };

  const handleDownloadWorkspace = async () => {
    try {
      toast({
        title: "Downloading Workspace",
        description: "Preparing workspace download...",
      });

      const response = await fetch('/api/workspace/download');
      
      if (!response.ok) {
        throw new Error('Failed to download workspace');
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'petrophysics-workplace.zip';
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

      toast({
        title: "Workspace Downloaded",
        description: "Workspace has been downloaded successfully.",
      });
    } catch (error) {
      toast({
        title: "Download Failed",
        description: error instanceof Error ? error.message : "Failed to download workspace",
        variant: "destructive",
      });
    }
  };

  const handleDownloadProject = async () => {
    if (!projectPath) {
      toast({
        title: "No Project Selected",
        description: "Please select a project first.",
        variant: "destructive",
      });
      return;
    }

    try {
      const projectName = projectPath.split('/').pop();
      
      toast({
        title: "Downloading Project",
        description: `Preparing ${projectName} download...`,
      });

      const response = await fetch(`/api/workspace/download?project_name=${encodeURIComponent(projectName || '')}`);
      
      if (!response.ok) {
        throw new Error('Failed to download project');
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${projectName}.zip`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

      toast({
        title: "Project Downloaded",
        description: `Project ${projectName} has been downloaded successfully.`,
      });
    } catch (error) {
      toast({
        title: "Download Failed",
        description: error instanceof Error ? error.message : "Failed to download project",
        variant: "destructive",
      });
    }
  };

  const handleUploadWorkspace = () => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.zip';
    input.onchange = async (e: any) => {
      const file = e.target.files?.[0];
      if (!file) return;

      const formData = new FormData();
      formData.append('file', file);
      formData.append('overwrite', 'false');

      try {
        toast({
          title: "Uploading Workspace",
          description: "Uploading and extracting workspace...",
        });

        const response = await fetch('/api/workspace/upload', {
          method: 'POST',
          body: formData,
        });

        if (!response.ok) {
          const error = await response.json();
          throw new Error(error.detail || 'Upload failed');
        }

        const result = await response.json();
        
        toast({
          title: "Upload Successful",
          description: result.message || "Workspace has been uploaded successfully.",
        });

        // Refresh the page to show updated workspace
        window.location.reload();
      } catch (error) {
        toast({
          title: "Upload Failed",
          description: error instanceof Error ? error.message : "Failed to upload workspace",
          variant: "destructive",
        });
      }
    };
    input.click();
  };

  return (
    <>
      <div className="h-10 bg-white dark:bg-card border-b border-border flex items-center justify-between px-1 md:px-2 gap-1">
        <div className="flex items-center gap-0.5 md:gap-1">
          {/* Mobile Sidebar Toggle */}
          <Button
            variant="ghost"
            size="icon"
            className="md:hidden h-8 w-8"
            onClick={onToggleMobileSidebar}
          >
            {isMobileSidebarOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
          </Button>
          
          <DropdownMenu>
          <DropdownMenuTrigger className="px-2 md:px-3 py-1 text-xs md:text-sm font-medium text-foreground hover-elevate rounded" data-testid="menu-project">
            Project
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start">
            <DropdownMenuItem onClick={handleNewProject} data-testid="menu-new">New</DropdownMenuItem>
            <DropdownMenuItem onClick={handleOpen} data-testid="menu-open">Open</DropdownMenuItem>
            <DropdownMenuItem onClick={handleSave} data-testid="menu-save">Save</DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={onNewWell} data-testid="menu-new-well">Load Well</DropdownMenuItem>
            <DropdownMenuItem onClick={() => setDataExplorerOpen(true)} data-testid="menu-reveal-data">Reveal Data</DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={() => onTogglePanel("dataBrowser")} data-testid="menu-new-dockable">New Dockable Window</DropdownMenuItem>
            <DropdownMenuItem data-testid="menu-remove-widget">Remove Central Widget</DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem data-testid="menu-exit">Exit</DropdownMenuItem>
          </DropdownMenuContent>
          </DropdownMenu>

          <DropdownMenu>
            <DropdownMenuTrigger className="px-2 md:px-3 py-1 text-xs md:text-sm font-medium text-foreground hover-elevate rounded" data-testid="menu-file">
              File
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start">
              <DropdownMenuItem onClick={handleImport} data-testid="menu-import">Import</DropdownMenuItem>
              <DropdownMenuItem onClick={handleExport} data-testid="menu-export">Export</DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={handleDownloadWorkspace} data-testid="menu-download-workspace">
                <Download className="w-4 h-4 mr-2" />
                Download Workspace
              </DropdownMenuItem>
              <DropdownMenuItem onClick={handleDownloadProject} data-testid="menu-download-project">
                <Download className="w-4 h-4 mr-2" />
                Download Current Project
              </DropdownMenuItem>
              <DropdownMenuItem onClick={handleUploadWorkspace} data-testid="menu-upload-workspace">
                <Upload className="w-4 h-4 mr-2" />
                Upload Workspace
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

          <DropdownMenu>
            <DropdownMenuTrigger className="px-2 md:px-3 py-1 text-xs md:text-sm font-medium text-foreground hover-elevate rounded" data-testid="menu-petrophysics">
              <span className="hidden md:inline">Petrophysics</span><span className="md:hidden">Petro</span>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start">
              <DropdownMenuItem onClick={() => toast({ title: "Analysis Tools", description: "Opening analysis tools..." })} data-testid="menu-analysis">Analysis Tools</DropdownMenuItem>
              <DropdownMenuItem onClick={() => toast({ title: "Calculations", description: "Opening calculations..." })} data-testid="menu-calculations">Calculations</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

          <DropdownMenu>
            <DropdownMenuTrigger className="px-2 md:px-3 py-1 text-xs md:text-sm font-medium text-foreground hover-elevate rounded" data-testid="menu-view">
              View
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start">
              <DropdownMenuItem onClick={() => onOpenFloatingWindow?.("wellLogPlot")} data-testid="menu-well-log-plot">Well Log Plot (New Window)</DropdownMenuItem>
              <DropdownMenuItem onClick={() => onOpenFloatingWindow?.("crossPlot")} data-testid="menu-cross-plot">Cross Plot (New Window)</DropdownMenuItem>
              <DropdownMenuItem onClick={() => onOpenFloatingWindow?.("logPlot")} data-testid="menu-log-plot">Log Plot (New Window)</DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={onToggleFeedbackAutoScroll} data-testid="menu-toggle-autoscroll">
                {feedbackAutoScroll && <Check className="w-4 h-4 mr-2" />}
                {!feedbackAutoScroll && <span className="w-4 mr-2" />}
                Auto-scroll Feedback
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

          <DropdownMenu>
            <DropdownMenuTrigger className="px-2 md:px-3 py-1 text-xs md:text-sm font-medium text-foreground hover-elevate rounded" data-testid="menu-geolog">
              Petrophysics AI
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start">
              <DropdownMenuItem onClick={() => toast({ title: "Geolog Utilities", description: "Opening Geolog utilities..." })} data-testid="menu-geolog-utilities">Open Geolog Utilities</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

          <DropdownMenu>
            <DropdownMenuTrigger className="px-2 md:px-3 py-1 text-xs md:text-sm font-medium text-foreground hover-elevate rounded flex items-center gap-1" data-testid="menu-data">
              Data
              {deletePermissionEnabled && permissionTimeLeft > 0 && (
                <span className="ml-1 px-1.5 py-0.5 text-xs bg-red-100 dark:bg-red-900 text-red-700 dark:text-red-200 rounded font-mono">
                  {permissionTimeLeft}s
                </span>
              )}
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start">
              <DropdownMenuItem onClick={toggleDeletePermission} data-testid="menu-delete-permission">
                {deletePermissionEnabled ? (
                  <>
                    <ShieldOff className="w-4 h-4 mr-2 text-red-500" />
                    Disable Delete Permission
                    {permissionTimeLeft > 0 && (
                      <span className="ml-auto text-xs text-muted-foreground flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {permissionTimeLeft}s
                      </span>
                    )}
                  </>
                ) : (
                  <>
                    <Shield className="w-4 h-4 mr-2 text-green-500" />
                    Enable Delete Permission (60s)
                  </>
                )}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

          <DropdownMenu>
            <DropdownMenuTrigger className="px-2 md:px-3 py-1 text-xs md:text-sm font-medium text-foreground hover-elevate rounded" data-testid="menu-dock">
              Dock
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start">
              <DropdownMenuItem onClick={() => onTogglePanel("wells")} data-testid="menu-toggle-wells">
                {visiblePanels.has("wells") && <Check className="w-4 h-4 mr-2" />}
                {!visiblePanels.has("wells") && <span className="w-4 mr-2" />}
                Toggle Wells
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => onTogglePanel("zonation")} data-testid="menu-toggle-zonation">
                {visiblePanels.has("zonation") && <Check className="w-4 h-4 mr-2" />}
                {!visiblePanels.has("zonation") && <span className="w-4 mr-2" />}
                Toggle Tops
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => onTogglePanel("dataBrowser")} data-testid="menu-toggle-databrowser">
                {visiblePanels.has("dataBrowser") && <Check className="w-4 h-4 mr-2" />}
                {!visiblePanels.has("dataBrowser") && <span className="w-4 mr-2" />}
                Toggle DatasetBrowser
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => onTogglePanel("feedback")} data-testid="menu-toggle-feedback">
                {visiblePanels.has("feedback") && <Check className="w-4 h-4 mr-2" />}
                {!visiblePanels.has("feedback") && <span className="w-4 mr-2" />}
                Toggle Feedback
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={handleSaveCurrentLayout} data-testid="menu-save-layout">
                Save Layout
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => setSaveLayoutDialogOpen(true)} data-testid="menu-save-as-layout">
                Save As Layout
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => setLoadLayoutDialogOpen(true)} data-testid="menu-load-layout">
                Load Layout
              </DropdownMenuItem>
              <DropdownMenuItem onClick={onResetLayout} data-testid="menu-reset-layout">
                Default Layout
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
        
        <div className="flex items-center gap-2">
          {/* Session Timeout Indicator - Compact */}
          {(() => {
            const style = getSessionTimeStyle(sessionTimeLeft);
            return (
              <div 
                className={`hidden md:flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg transition-all duration-500 ${style.containerClass}`}
                title="Session expires in this time. Auto-saves at 5 minutes remaining."
              >
                <div className="relative">
                  <div className={`absolute -top-0.5 -right-0.5 w-1.5 h-1.5 rounded-full ${style.badge}`}></div>
                  <Clock className={`h-4 w-4 ${style.iconClass}`} />
                </div>
                <span className={`text-xs font-mono font-bold ${style.textClass}`}>
                  {formatSessionTime(sessionTimeLeft)}
                </span>
              </div>
            );
          })()}
          
          <Button
            variant="ghost"
            size="icon"
            onClick={() => onTogglePanel("settings")}
            className="h-8 w-8"
            title="Settings"
          >
            <Settings2 className="h-4 w-4" />
          </Button>
          
          <Button
            variant="ghost"
            size="icon"
            onClick={onToggleTheme}
            className="h-8 w-8"
            data-testid="button-toggle-theme"
          >
            {theme === "light" ? (
              <Moon className="h-4 w-4" />
            ) : (
              <Sun className="h-4 w-4" />
            )}
          </Button>
        </div>
      </div>
      
      <NewProjectDialog 
        open={newProjectDialogOpen}
        onOpenChange={setNewProjectDialogOpen}
      />
      
      <DataExplorer
        open={dataExplorerOpen}
        onOpenChange={setDataExplorerOpen}
      />

      <SaveLayoutDialog
        open={saveLayoutDialogOpen}
        onOpenChange={setSaveLayoutDialogOpen}
        onSave={handleSaveLayout}
        existingLayouts={savedLayouts}
        currentLayoutName={currentLayoutName}
      />

      <LoadLayoutDialog
        open={loadLayoutDialogOpen}
        onOpenChange={setLoadLayoutDialogOpen}
        layouts={savedLayouts}
        onLoad={handleLoadLayout}
        projectPath={projectPath}
        onDelete={loadSavedLayoutsList}
      />
    </>
  );
}
