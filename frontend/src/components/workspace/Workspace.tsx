import { useState, useEffect, useRef, useMemo } from "react";
import DockLayout from "rc-dock";
import "rc-dock/dist/rc-dock.css";
import axios from "axios";
import MenuBar from "./MenuBar";
import ProjectInfoBar from "./ProjectInfoBar";
import ProjectListDialog from "../dialogs/ProjectListDialog";
import DirectoryPicker from "../dialogs/DirectoryPicker";
import NewWellDialog from "../dialogs/NewWellDialog";
import WellsPanelNew from "../panels/WellsPanelNew";
import ZonationPanelNew from "../panels/ZonationPanelNew";
import DataBrowserPanelNew from "../panels/DataBrowserPanelNew";
import FeedbackPanelNew from "../panels/FeedbackPanelNew";
import WellLogPlotPanel from "../panels/WellLogPlotPanel";
import CrossPlotPanel from "../panels/CrossPlotPanel";
import CrossPlotControlPanel from "../panels/CrossPlotControlPanel";
import LogPlotPanel from "../panels/LogPlotPanel";
import CLIPanel from "../panels/CLIPanel";
import SettingsPanel from "../panels/SettingsPanel";
import { useToast } from "@/hooks/use-toast";
import { Layers, Maximize2, Minimize2, Square } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";

type PanelId =
  | "wells"
  | "zonation"
  | "dataBrowser"
  | "feedback"
  | "wellLogPlot"
  | "crossPlot"
  | "crossPlotControl"
  | "logPlot"
  | "cli"
  | "settings";

export interface WellData {
  id: string;
  name: string;
  path: string;
  projectPath?: string;
  data?: any;
  logs?: string[];
  metadata?: any;
}

export interface ProjectData {
  name: string;
  path: string;
  wells: WellData[];
  createdAt: string;
  updatedAt: string;
}

const PANEL_TITLES: Record<PanelId, string> = {
  wells: "Wells",
  zonation: "Zonation",
  dataBrowser: "Data Browser",
  feedback: "Feedback Logs",
  wellLogPlot: "Well Log Plot",
  crossPlot: "Cross Plot",
  crossPlotControl: "Cross Plot Control",
  logPlot: "Log Plot",
  cli: "CLI Terminal",
  settings: "Settings",
};

export default function Workspace() {
  const { toast } = useToast();
  const dockRef = useRef<DockLayout>(null);

  const [theme, setTheme] = useState<"light" | "dark">("light");
  const [projectPath, setProjectPath] = useState<string>("");
  const [projectName, setProjectName] = useState<string>("");
  const [wells, setWells] = useState<WellData[]>([]);
  const [selectedWell, setSelectedWell] = useState<WellData | null>(null);
  const [projectCreatedAt, setProjectCreatedAt] = useState<string>("");
  const [projectListOpen, setProjectListOpen] = useState(false);
  const [directoryPickerOpen, setDirectoryPickerOpen] = useState(false);
  const [directoryPickerMode, setDirectoryPickerMode] = useState<
    "import" | "open"
  >("open");
  const [newWellDialogOpen, setNewWellDialogOpen] = useState(false);
  const [mobilePanelSelectorOpen, setMobilePanelSelectorOpen] = useState(false);
  const [selectedLogsForPlot, setSelectedLogsForPlot] = useState<string[]>([]);
  const [visiblePanels, setVisiblePanels] = useState<Set<string>>(
    new Set([
      "wells",
      "zonation",
      "emptyDock",
      "dataBrowser",
      "feedback",
      "cli",
    ]),
  );
  const [selectedDatasetByWell, setSelectedDatasetByWell] = useState<
    Map<string, any>
  >(new Map());
  const [wellLogPlotFloatingOpen, setWellLogPlotFloatingOpen] = useState(false);
  const [feedbackAutoScroll, setFeedbackAutoScroll] = useState(true);
  const [activeWellName, setActiveWellName] = useState<string | null>(null);
  const [currentLayoutName, setCurrentLayoutName] = useState<string>("default");

  // Multiple window tracking
  const [plotWindowCounter, setPlotWindowCounter] = useState(1);
  const [crossPlotWindowCounter, setCrossPlotWindowCounter] = useState(1);
  const [activeWindowId, setActiveWindowId] = useState<string | null>(null);

  // Cross plot selections state - keyed by window ID
  const [crossPlotSelections, setCrossPlotSelections] = useState<{
    [windowId: string]: { xLog: string; yLog: string };
  }>({});

  // Target window ID for Cross Plot Control panel
  const [crossPlotControlTargetId, setCrossPlotControlTargetId] = useState<
    string | null
  >(null);

  // Window well lock state - tracks which windows are locked to a specific well
  // isLocked=true means LINKED (follows global well selection)
  // isLocked=false means UNLINKED (stays on lockedWell)
  const [windowWellLocks, setWindowWellLocks] = useState<
    Map<string, { isLocked: boolean; lockedWell: WellData | null }>
  >(() => {
    return new Map();
  });

  // Rehydrate window locks from localStorage after wells are loaded
  useEffect(() => {
    if (wells.length === 0) return;

    try {
      const saved = localStorage.getItem("windowWellLocks");
      if (saved) {
        const parsed = JSON.parse(saved);
        const rehydrated = new Map<
          string,
          { isLocked: boolean; lockedWell: WellData | null }
        >();

        Object.entries(parsed).forEach(([key, value]: [string, any]) => {
          const isLocked = value.isLocked !== false;
          let lockedWell: WellData | null = null;

          // Rehydrate well from current wells list using stored well ID/path
          if (!isLocked && value.lockedWellId) {
            lockedWell =
              wells.find(
                (w) =>
                  w.id === value.lockedWellId ||
                  w.name === value.lockedWellId ||
                  w.path === value.lockedWellPath,
              ) || null;
          }

          rehydrated.set(key, { isLocked, lockedWell });
        });

        setWindowWellLocks(rehydrated);
        console.log("[Workspace] Rehydrated window locks from localStorage");
      }
    } catch (e) {
      console.error("Error loading window locks from localStorage:", e);
    }
  }, [wells]);

  // Save window lock state to localStorage whenever it changes (store only IDs, not full objects)
  useEffect(() => {
    try {
      const obj: Record<string, any> = {};
      windowWellLocks.forEach((value, key) => {
        obj[key] = {
          isLocked: value.isLocked,
          lockedWellId: value.lockedWell?.id || value.lockedWell?.name || null,
          lockedWellPath: value.lockedWell?.path || null,
        };
      });
      localStorage.setItem("windowWellLocks", JSON.stringify(obj));
    } catch (e) {
      console.error("Error saving window locks to localStorage:", e);
      // If quota exceeded, clear old data and try again
      if (e instanceof DOMException && e.name === "QuotaExceededError") {
        console.warn(
          "[Workspace] localStorage quota exceeded, clearing window locks",
        );
        localStorage.removeItem("windowWellLocks");
        toast({
          title: "Storage Limit Reached",
          description:
            "Window link states could not be saved. Some preferences may be lost on reload.",
          variant: "destructive",
        });
      }
    }
  }, [windowWellLocks]);

  // Force tab updates when lock state changes
  useEffect(() => {
    if (dockRef.current) {
      const layout = dockRef.current.getLayout();

      // Helper to find tab in layout and get its title
      const findTabTitle = (box: any, tabId: string): string | null => {
        if (box?.tabs) {
          const tab = box.tabs.find((t: any) => t.id === tabId);
          if (tab) return tab.title;
        }
        if (box?.children) {
          for (const child of box.children) {
            const title = findTabTitle(child, tabId);
            if (title) return title;
          }
        }
        return null;
      };

      windowWellLocks.forEach((lockState, windowId) => {
        // Find the current title from the layout
        let title = null;
        if (layout?.dockbox) {
          title = findTabTitle(layout.dockbox, windowId);
        }
        if (!title && layout?.floatbox) {
          title = findTabTitle(layout.floatbox, windowId);
        }

        // Preserve the title when updating
        const tabData = loadTab({
          id: windowId,
          title: title || PANEL_TITLES[windowId as PanelId] || windowId,
        });
        dockRef.current?.updateTab(windowId, tabData);
      });
    }
  }, [windowWellLocks]);

  // Force tab updates when selected well changes (for LINKED windows only)
  useEffect(() => {
    if (dockRef.current && selectedWell) {
      const layout = dockRef.current.getLayout();

      // Helper to find tab in layout and get its title
      const findTabTitle = (box: any, tabId: string): string | null => {
        if (box?.tabs) {
          const tab = box.tabs.find((t: any) => t.id === tabId);
          if (tab) return tab.title;
        }
        if (box?.children) {
          for (const child of box.children) {
            const title = findTabTitle(child, tabId);
            if (title) return title;
          }
        }
        return null;
      };

      // Helper to collect all tab IDs from layout
      const collectAllTabIds = (box: any, ids: Set<string>) => {
        if (box?.tabs) {
          box.tabs.forEach((tab: any) => ids.add(tab.id));
        }
        if (box?.children) {
          box.children.forEach((child: any) => collectAllTabIds(child, ids));
        }
      };

      // Collect all existing tab IDs
      const allTabIds = new Set<string>();
      if (layout?.dockbox) collectAllTabIds(layout.dockbox, allTabIds);
      if (layout?.floatbox) collectAllTabIds(layout.floatbox, allTabIds);
      if (layout?.maxbox) collectAllTabIds(layout.maxbox, allTabIds);

      // Update only LINKED windows (dataBrowser, wellLogPlot, crossPlot, logPlot)
      allTabIds.forEach((tabId) => {
        const basePanelType = tabId.toString().split("_")[0];
        if (
          basePanelType === "dataBrowser" ||
          basePanelType === "wellLogPlot" ||
          basePanelType === "crossPlot" ||
          basePanelType === "logPlot"
        ) {
          // Check if this window is LINKED (isLocked=true means linked)
          const isLinked = isWindowLocked(tabId);

          if (isLinked) {
            // Find the current title from the layout
            let title = null;
            if (layout?.dockbox) {
              title = findTabTitle(layout.dockbox, tabId);
            }
            if (!title && layout?.floatbox) {
              title = findTabTitle(layout.floatbox, tabId);
            }
            if (!title && layout?.maxbox) {
              title = findTabTitle(layout.maxbox, tabId);
            }

            // Preserve the title when updating
            const tabData = loadTab({
              id: tabId,
              title: title || PANEL_TITLES[tabId as PanelId] || tabId,
            });
            dockRef.current?.updateTab(tabId, tabData);
          }
        }
      });
    }
  }, [selectedWell, projectPath]);

  useEffect(() => {
    if (theme === "dark") {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
  }, [theme]);

  // Fetch workspace root and load current project on mount
  useEffect(() => {
    const initializeWorkspace = async () => {
      try {
        const response = await axios.get("/api/workspace/info");
        const workspaceData = response.data;

        console.log("[Workspace] Workspace info loaded:", workspaceData);

        if (
          workspaceData.hasOpenProject &&
          workspaceData.currentProjectPath &&
          workspaceData.currentProjectName
        ) {
          setProjectPath(workspaceData.currentProjectPath);
          setProjectName(workspaceData.currentProjectName);
          (window as any).addAppLog?.(
            `📂 Project "${workspaceData.currentProjectName}" opened successfully`,
            "success",
            "success",
          );
        } else {
          console.log("[Workspace] No current project found");
          (window as any).addAppLog?.(
            `📁 No project selected. Please create a new project to get started.`,
            "info",
          );
          toast({
            title: "No Project Selected",
            description:
              "Please create a new project or open an existing project to get started.",
            variant: "default",
          });
        }
      } catch (error) {
        console.error("[Workspace] Failed to fetch workspace info:", error);
        toast({
          title: "Error",
          description:
            "Failed to initialize workspace. Please check if the backend is running.",
          variant: "destructive",
        });
      }
    };

    // Listen for window focus messages from popup windows
    const handleWindowMessage = (event: MessageEvent) => {
      if (event.data.type === "WINDOW_FOCUS") {
        const message =
          event.data.message ||
          `${event.data.windowType} focused: ${event.data.wellName}`;
        if ((window as any).addAppLog) {
          (window as any).addAppLog(message, "info");
        }
        console.log("[Workspace] Received focus notification:", event.data);
      }
    };

    window.addEventListener("message", handleWindowMessage);

    initializeWorkspace();

    return () => {
      window.removeEventListener("message", handleWindowMessage);
    };
  }, []);

  // Save project to storage whenever it changes
  useEffect(() => {
    const saveProjectToStorage = async () => {
      if (projectPath && projectPath !== "No path selected" && projectName) {
        try {
          console.log(
            "[Workspace] Saving current project to storage:",
            projectPath,
            projectName,
          );
          await axios.post("/api/projects/set-current", {
            projectPath: projectPath,
            projectName: projectName,
          });
        } catch (error) {
          console.error("Error saving project to storage:", error);
        }
      }
    };

    saveProjectToStorage();
  }, [projectPath, projectName]);

  // Load wells when project path changes
  useEffect(() => {
    let isCurrent = true; // Track if this effect is still current

    const loadWells = async () => {
      if (!projectPath || projectPath === "No path selected") {
        setWells([]);
        setSelectedWell(null);
        return;
      }

      // ALWAYS clear selectedWell and wells immediately when project changes
      // This prevents stale data from showing during the transition
      console.log(
        "[Workspace] Project changed to:",
        projectPath,
        "- clearing all data immediately",
      );
      setSelectedWell(null);
      setWells([]);

      try {
        // Load all wells into session cache (eager loading)
        console.log("[Workspace] Loading all wells into session cache...");
        try {
          const loadAllResponse = await axios.post(
            "/api/projects/load-all-wells",
            {
              projectPath: projectPath,
            },
          );

          if (isCurrent && loadAllResponse.data.success) {
            console.log(
              `[Workspace] Loaded ${loadAllResponse.data.loadedWells} of ${loadAllResponse.data.totalWells} wells into cache`,
            );
            (window as any).addAppLog?.(
              `💾 Cached ${loadAllResponse.data.loadedWells} well(s) in session (ID: ${loadAllResponse.data.sessionId.substring(0, 16)}...)`,
              "success",
              "💾",
            );

            if (
              loadAllResponse.data.failedWells &&
              loadAllResponse.data.failedWells.length > 0
            ) {
              console.warn(
                "[Workspace] Failed to load some wells:",
                loadAllResponse.data.failedWells,
              );
            }
          }
        } catch (cacheError) {
          console.warn(
            "[Workspace] Failed to load wells into cache (continuing anyway):",
            cacheError,
          );
        }

        // Get wells list for UI
        const response = await axios.get(
          `/api/wells/list?projectPath=${encodeURIComponent(projectPath)}`,
        );

        // Only apply results if this effect is still current (projectPath hasn't changed)
        if (!isCurrent) {
          console.log("[Workspace] Ignoring stale response for old project");
          return;
        }

        if (response.data.wells && Array.isArray(response.data.wells)) {
          let wellsToDisplay = response.data.wells;

          // Check if there are selected wells saved in storage for this project
          try {
            const projectName =
              projectPath.split("/").pop() ||
              projectPath.split("\\").pop() ||
              "project";
            (window as any).addAppLog?.(
              `🔍 Checking storage for saved well selection...`,
              "info",
            );

            const selectedWellsResponse = await axios.get(
              `/api/cli/selected-wells/${encodeURIComponent(projectName)}`,
            );

            if (
              selectedWellsResponse.data.success &&
              selectedWellsResponse.data.selected_wells &&
              selectedWellsResponse.data.selected_wells.length > 0
            ) {
              const selectedWellNames =
                selectedWellsResponse.data.selected_wells;
              wellsToDisplay = response.data.wells.filter((well: any) =>
                selectedWellNames.includes(well.name),
              );
              console.log(
                `[Workspace] Applied well filter from storage: ${selectedWellNames.length} wells selected, ${wellsToDisplay.length} found`,
              );
              (window as any).addAppLog?.(
                `✓ Retrieved ${selectedWellNames.length} selected wells from storage`,
                "success",
              );
              (window as any).addAppLog?.(
                `📊 Applying filter: showing ${wellsToDisplay.length} of ${response.data.wells.length} well(s)`,
                "info",
              );
            } else {
              (window as any).addAppLog?.(
                `ℹ️ No saved well selection found - showing all wells`,
                "info",
              );
            }
          } catch (filterError) {
            console.warn(
              "[Workspace] Could not load well filter from storage:",
              filterError,
            );
            (window as any).addAppLog?.(
              `⚠️ Could not retrieve well selection from storage`,
              "warning",
            );
          }

          // Deduplicate wells by path to prevent React key warnings
          const uniqueWells = Array.from(
            new Map(wellsToDisplay.map((w: any) => [w.path, w])).values()
          );
          setWells(uniqueWells);
          (window as any).addAppLog?.(
            `📊 Found ${uniqueWells.length} well(s) in project: ${uniqueWells.map((w: any) => w.name).join(", ")}`,
            "success",
            "database",
          );

          // Check for active well in storage, or set first well as active by default
          let activeWellToSelect: WellData | null = null;
          try {
            const projectName =
              projectPath.split("/").pop() ||
              projectPath.split("\\").pop() ||
              "project";
            const activeWellResponse = await axios.get(
              `/api/cli/active-well/${encodeURIComponent(projectName)}`,
            );

            if (
              isCurrent &&
              activeWellResponse.data.success &&
              activeWellResponse.data.active_well
            ) {
              const activeWellNameFromStorage =
                activeWellResponse.data.active_well;
              setActiveWellName(activeWellNameFromStorage);
              console.log(
                `[Workspace] Active well from storage: ${activeWellNameFromStorage}`,
              );

              // Find the active well in the displayed wells list
              activeWellToSelect =
                wellsToDisplay.find(
                  (w: any) => w.name === activeWellNameFromStorage,
                ) || null;
            } else if (isCurrent && wellsToDisplay.length > 0) {
              // No active well set - automatically set first well as active
              const firstWell = wellsToDisplay[0];
              const firstWellName = firstWell.name;
              setActiveWellName(firstWellName);
              activeWellToSelect = firstWell;
              console.log(
                `[Workspace] No active well found - setting first well as active: ${firstWellName}`,
              );

              // Save first well as active in storage
              try {
                await axios.post("/api/cli/execute", {
                  command: `ACTIVE_WELL ${firstWellName}`,
                  projectPath: projectPath,
                  deletePermissionEnabled: false,
                });
                console.log(
                  `[Workspace] Saved first well as active in storage: ${firstWellName}`,
                );
              } catch (saveError) {
                console.warn(
                  "[Workspace] Could not save active well to storage:",
                  saveError,
                );
              }
            } else if (isCurrent) {
              setActiveWellName(null);
            }
          } catch (activeWellError) {
            console.warn(
              "[Workspace] Could not load active well from storage:",
              activeWellError,
            );
            if (isCurrent && wellsToDisplay.length > 0) {
              // Error loading from storage - set first well as active anyway
              const firstWell = wellsToDisplay[0];
              const firstWellName = firstWell.name;
              setActiveWellName(firstWellName);
              activeWellToSelect = firstWell;
              console.log(
                `[Workspace] Error loading active well - setting first well as active: ${firstWellName}`,
              );
            } else if (isCurrent) {
              setActiveWellName(null);
            }
          }

          // Auto-select the active well in the UI
          if (activeWellToSelect && isCurrent) {
            setTimeout(() => {
              if (isCurrent) {
                console.log(
                  "[Workspace] Auto-selecting active well:",
                  activeWellToSelect.name,
                );
                handleWellSelect(activeWellToSelect);
              }
            }, 100);
          }
        }
      } catch (error) {
        if (isCurrent) {
          console.error("Error loading wells:", error);
          (window as any).addAppLog?.(
            `⚠️ Error loading wells: ${error}`,
            "error",
            "⚠️",
          );
        }
      }
    };

    loadWells();

    // Cleanup: mark this effect as no longer current when projectPath changes
    return () => {
      isCurrent = false;
    };
  }, [projectPath]);

  // Apply font sizes to the document
  const applyFontSizes = (sizes: any) => {
    const root = document.documentElement;
    if (sizes.dataBrowser) root.style.setProperty("--font-size-data-browser", `${sizes.dataBrowser}px`);
    if (sizes.wellList) root.style.setProperty("--font-size-well-list", `${sizes.wellList}px`);
    if (sizes.feedbackLog) root.style.setProperty("--font-size-feedback-log", `${sizes.feedbackLog}px`);
    if (sizes.zonationList) root.style.setProperty("--font-size-zonation-list", `${sizes.zonationList}px`);
    if (sizes.cliTerminal) root.style.setProperty("--font-size-cli-terminal", `${sizes.cliTerminal}px`);
  };

  // Helper function to ensure emptyDock tab always uses emptyDock group (headerless)
  const ensureEmptyDockGroup = (layout: any): any => {
    if (!layout) return layout;

    const normalizeBox = (box: any): any => {
      if (!box) return box;

      // If this box has tabs, check for emptyDock and force its group
      if (box.tabs && Array.isArray(box.tabs)) {
        box.tabs = box.tabs.map((tab: any) => {
          if (tab.id === "emptyDock") {
            return { ...tab, group: "emptyDock" };
          }
          return tab;
        });
      }

      // Recursively normalize children
      if (box.children && Array.isArray(box.children)) {
        box.children = box.children.map(normalizeBox);
      }

      return box;
    };

    return {
      ...layout,
      dockbox: layout.dockbox ? normalizeBox(layout.dockbox) : undefined,
      floatbox: layout.floatbox ? normalizeBox(layout.floatbox) : undefined,
      maxbox: layout.maxbox ? normalizeBox(layout.maxbox) : undefined,
    };
  };

  // Auto-load saved layout when project changes
  useEffect(() => {
    const autoLoadLayout = async () => {
      if (!projectPath || !dockRef.current) return;

      try {
        // Try to load the last active layout name from localStorage
        const savedLayoutName =
          localStorage.getItem(`activeLayoutName_${projectPath}`) || "default";

        const response = await axios.get(
          `/api/workspace/layout?projectPath=${encodeURIComponent(projectPath)}&layoutName=${encodeURIComponent(savedLayoutName)}`,
        );

        if (response.data.success && response.data.layout) {
          // Normalize layout to ensure emptyDock uses headerless group
          const normalizedLayout = ensureEmptyDockGroup(response.data.layout);
          dockRef.current.loadLayout(normalizedLayout);

          // Set layout name from the saved value
          setCurrentLayoutName(savedLayoutName);

          if (response.data.visiblePanels) {
            setVisiblePanels(new Set(response.data.visiblePanels));
          }

          // Load and apply font sizes from layout
          if (response.data.fontSizes && Object.keys(response.data.fontSizes).length > 0) {
            applyFontSizes(response.data.fontSizes);
            console.log("[Workspace] Applied font sizes from layout:", response.data.fontSizes);
          }

          console.log(
            `[Workspace] Auto-loaded saved layout '${savedLayoutName}' from storage`,
          );
        }
      } catch (error) {
        console.log("[Workspace] No saved layout found, using default");
      }
    };

    autoLoadLayout();
  }, [projectPath]);

  // Save current layout name to localStorage whenever it changes
  useEffect(() => {
    if (projectPath && currentLayoutName) {
      localStorage.setItem(
        `activeLayoutName_${projectPath}`,
        currentLayoutName,
      );
    }
  }, [currentLayoutName, projectPath]);

  const togglePanel = (panelId: string) => {
    if (!dockRef.current) return;

    const layout = dockRef.current.getLayout();

    // Helper to find tab in layout
    const findTab = (box: any, id: string): any => {
      if (box.tabs) {
        const tab = box.tabs.find((t: any) => t.id === id);
        if (tab) return { box, tab };
      }
      if (box.children) {
        for (const child of box.children) {
          const result = findTab(child, id);
          if (result) return result;
        }
      }
      return null;
    };

    // Check if panel exists in layout
    let panelExists = false;
    if (layout.dockbox && findTab(layout.dockbox, panelId)) {
      panelExists = true;
    }
    if (!panelExists && layout.floatbox && findTab(layout.floatbox, panelId)) {
      panelExists = true;
    }

    if (panelExists) {
      // Remove the panel
      const removeTab = (box: any): boolean => {
        if (box.tabs) {
          const index = box.tabs.findIndex((t: any) => t.id === panelId);
          if (index !== -1) {
            box.tabs.splice(index, 1);
            return true;
          }
        }
        if (box.children) {
          for (const child of box.children) {
            if (removeTab(child)) return true;
          }
        }
        return false;
      };

      if (layout.dockbox) removeTab(layout.dockbox);
      if (layout.floatbox) removeTab(layout.floatbox);

      dockRef.current.loadLayout(layout);
      setVisiblePanels((prev) => {
        const newSet = new Set(prev);
        newSet.delete(panelId);
        return newSet;
      });
    } else {
      // Add the panel - create proper TabData object with content
      const tabData = {
        id: panelId,
        title: PANEL_TITLES[panelId as PanelId],
        closable: true,
        group: "default",
      };

      // Load the tab content using our loadTab function
      const tabWithContent = loadTab(tabData);

      // Add it to the layout as a floating window
      dockRef.current.dockMove(tabWithContent, null, "float");
      setVisiblePanels((prev) => {
        const newSet = new Set(prev);
        newSet.add(panelId);
        return newSet;
      });
    }
  };

  const saveLayout = async (layoutName: string = "default") => {
    if (!dockRef.current || !projectPath) return;

    try {
      const layout = dockRef.current.saveLayout();
      const visiblePanelIds = Array.from(visiblePanels);

      // Update current layout name
      setCurrentLayoutName(layoutName);

      // Prepare window links data from windowWellLocks
      const windowLinks: Record<string, any> = {};
      windowWellLocks.forEach((value, key) => {
        windowLinks[key] = {
          isLocked: value.isLocked,
          lockedWellId: value.lockedWell?.id || value.lockedWell?.name || null,
          lockedWellPath: value.lockedWell?.path || null,
        };
      });

      await axios.post("/api/workspace/layout", {
        projectPath,
        layout,
        visiblePanels: visiblePanelIds,
        layoutName,
        windowLinks,
      });

      console.log(
        `[Workspace] Layout '${layoutName}' saved with ${Object.keys(windowLinks).length} window link states`,
      );

      toast({
        title: "Layout Saved",
        description: `Layout '${layoutName}' has been saved to storage.`,
      });
    } catch (error) {
      console.error("Error saving layout:", error);
      toast({
        title: "Save Failed",
        description: "Failed to save layout. Please try again.",
        variant: "destructive",
      });
    }
  };

  const loadLayout = async (layoutName: string = "default") => {
    if (!dockRef.current || !projectPath) return;

    try {
      const response = await axios.get(
        `/api/workspace/layout?projectPath=${encodeURIComponent(projectPath)}&layoutName=${encodeURIComponent(layoutName)}`,
      );

      if (response.data.success && response.data.layout) {
        dockRef.current.loadLayout(response.data.layout);

        // Update current layout name
        setCurrentLayoutName(layoutName);

        if (response.data.visiblePanels) {
          setVisiblePanels(new Set(response.data.visiblePanels));
        }

        // Restore window link states from JSON
        if (response.data.windowLinks) {
          const newWindowLocks = new Map();
          Object.entries(response.data.windowLinks).forEach(
            ([windowId, linkData]: [string, any]) => {
              // Find the well object if available
              const lockedWell = linkData.lockedWellId
                ? wells.find((w) => (w.id || w.name) === linkData.lockedWellId)
                : null;

              newWindowLocks.set(windowId, {
                isLocked: linkData.isLocked,
                lockedWell: lockedWell || null,
              });
            },
          );
          setWindowWellLocks(newWindowLocks);
          console.log(
            `[Workspace] Restored ${newWindowLocks.size} window link states from JSON`,
          );
        }

        toast({
          title: "Layout Loaded",
          description: `Layout '${layoutName}' has been restored from storage.`,
        });
      } else {
        toast({
          title: "No Saved Layout",
          description: `No layout '${layoutName}' found for this project.`,
        });
      }
    } catch (error) {
      console.error("Error loading layout:", error);
      toast({
        title: "Load Failed",
        description: "Failed to load layout.",
        variant: "destructive",
      });
    }
  };

  const resetToDefaultLayout = async () => {
    if (!dockRef.current || !projectPath) return;

    try {
      // Delete saved layout from storage
      await axios.delete(
        `/api/workspace/layout?projectPath=${encodeURIComponent(projectPath)}`,
      );

      // Load the default layout
      dockRef.current.loadLayout(defaultLayout);

      // Reset visible panels to default
      setVisiblePanels(
        new Set(["wells", "zonation", "dataBrowser", "feedback", "cli"]),
      );

      // Log to feedback panel
      if ((window as any).addAppLog) {
        (window as any).addAppLog(
          "Workspace layout reset to default",
          "success",
        );
      }

      toast({
        title: "Default Layout Restored",
        description: "Workspace has been reset to the default layout.",
      });
    } catch (error) {
      console.error("Error resetting layout:", error);
      toast({
        title: "Reset Failed",
        description: "Failed to reset layout to default.",
        variant: "destructive",
      });
    }
  };

  const saveProjectData = async () => {
    console.log("Project save disabled");
  };

  // Centralized helper to persist project and reload page for complete state reset
  const switchToProject = async (
    path: string,
    name: string,
    createdAt: string,
  ) => {
    try {
      // Save to storage
      console.log(
        "[Workspace] Saving project to storage before switch:",
        path,
        name,
      );
      await axios.post("/api/projects/set-current", {
        projectPath: path,
        projectName: name,
      });

      // Reload page to completely reset all state
      console.log("[Workspace] Switching to project:", path);
      window.location.reload();
    } catch (error) {
      console.error("[Workspace] Error saving project to storage:", error);
      toast({
        title: "Error",
        description: "Failed to switch project. Please try again.",
        variant: "destructive",
      });
    }
  };

  const loadProjectData = (projectData: ProjectData) => {
    switchToProject(projectData.path, projectData.name, projectData.createdAt);
  };

  const handleProjectFolderSelect = (folderPath: string) => {
    const folderName = folderPath.split("/").pop() || folderPath;
    const createdAt = new Date().toISOString();
    switchToProject(folderPath, folderName, createdAt);
  };

  const handleOpenImportPicker = () => {
    setDirectoryPickerMode("import");
    setDirectoryPickerOpen(true);
  };

  const handleOpenProjectPicker = () => {
    setDirectoryPickerMode("open");
    setDirectoryPickerOpen(true);
  };

  const handleDirectorySelect = (path: string) => {
    if (directoryPickerMode === "import") {
      (window as any).addAppLog?.(
        `📂 Import from directory: ${path}`,
        "info",
        "📂",
      );
      toast({
        title: "Import from Directory",
        description: `Selected directory: ${path}`,
      });
    } else {
      handleProjectFolderSelect(path);
      toast({
        title: "Project Opened",
        description: `Selected project directory: ${path}`,
      });
    }
  };

  const handleLoadProject = async (fileName: string) => {
    console.log("Project load disabled");
  };

  const toggleTheme = () => {
    setTheme((prev) => (prev === "light" ? "dark" : "light"));
  };

  const parseCSVFile = async (file: File): Promise<any> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();

      reader.onload = (e) => {
        try {
          const text = e.target?.result as string;
          const lines = text.split("\n").filter((line) => line.trim());

          if (lines.length === 0) {
            resolve({ headers: [], rows: [] });
            return;
          }

          const headers = lines[0].split(",").map((h) => h.trim());
          const rows = lines.slice(1).map((line) => {
            const values = line.split(",").map((v) => v.trim());
            return headers.reduce(
              (obj, header, index) => {
                obj[header] = values[index] || "";
                return obj;
              },
              {} as Record<string, string>,
            );
          });

          resolve({ headers, rows, rowCount: rows.length });
        } catch (error) {
          reject(error);
        }
      };

      reader.onerror = () => reject(reader.error);
      reader.readAsText(file);
    });
  };

  const parseLASFile = async (file: File): Promise<any> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();

      reader.onload = (e) => {
        try {
          const text = e.target?.result as string;
          const lines = text.split("\n");

          const wellInfo: Record<string, string> = {};
          let inWellSection = false;

          for (const line of lines) {
            const trimmedLine = line.trim();

            if (trimmedLine.startsWith("~W")) {
              inWellSection = true;
              continue;
            }

            if (trimmedLine.startsWith("~")) {
              inWellSection = false;
            }

            if (inWellSection && trimmedLine && !trimmedLine.startsWith("#")) {
              const colonIndex = trimmedLine.indexOf(":");
              if (colonIndex > 0) {
                const beforeColon = trimmedLine.substring(0, colonIndex).trim();
                const parts = beforeColon
                  .split(/\s+/)
                  .filter((p) => p.length > 0);

                if (parts.length >= 2) {
                  const mnemonicWithUnit = parts[0];
                  const mnemonic = mnemonicWithUnit.split(".")[0];
                  const value = parts[1];
                  wellInfo[mnemonic] = value;
                }
              }
            }
          }

          resolve({
            type: "LAS",
            wellInfo,
            lineCount: lines.length,
          });
        } catch (error) {
          reject(error);
        }
      };

      reader.onerror = () => reject(reader.error);
      reader.readAsText(file);
    });
  };

  const handleLoadWells = async (
    files: File[],
    onError?: (message: string) => void,
  ) => {
    try {
      const newWells: WellData[] = [];

      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        const lowerName = file.name.toLowerCase();
        let parsedData;

        try {
          if (lowerName.endsWith(".csv")) {
            parsedData = await parseCSVFile(file);
          } else if (lowerName.endsWith(".las")) {
            parsedData = await parseLASFile(file);
          }

          newWells.push({
            id: `well-${Date.now()}-${i}`,
            name: file.name.replace(/\.(csv|las)$/i, ""),
            path: file.name,
            data: parsedData,
          });
        } catch (fileError) {
          console.error(`Error parsing file ${file.name}:`, fileError);
          if (onError) {
            onError(
              `Failed to parse ${file.name}: ${fileError instanceof Error ? fileError.message : "Unknown error"}`,
            );
          }
        }
      }

      if (newWells.length > 0) {
        // Deduplicate by path before merging
        setWells((prev) => {
          const existingPaths = new Set(prev.map(w => w.path));
          const uniqueNewWells = newWells.filter(w => !existingPaths.has(w.path));
          return [...prev, ...uniqueNewWells];
        });

        if (!projectName) {
          const firstFileName = newWells[0].name;
          setProjectName(firstFileName);
        }
      }
    } catch (error) {
      console.error("Error loading wells:", error);
      if (onError) {
        onError(
          `Failed to load wells: ${error instanceof Error ? error.message : "Unknown error"}`,
        );
      }
    }
  };

  const handleOpenNewWellDialog = () => {
    setNewWellDialogOpen(true);
  };

  const handleWellCreated = async () => {
    await refreshWellsList();
  };

  const handleWellSelect = async (well: WellData) => {
    // Log user action
    (window as any).addAppLog?.(
      `👆 User selected well: ${well.name}`,
      "info",
      "success",
    );

    setSelectedWell(well);

    const channel = new BroadcastChannel("well-selection-channel");
    channel.postMessage({
      type: "WELL_SELECTED",
      well: {
        id: well.id,
        name: well.name,
        path: well.path,
        projectPath: well.projectPath || projectPath,
      },
    });
    channel.close();

    if (!well.datasets && well.path) {
      try {
        // Use /api/wells/data as the single canonical endpoint
        const response = await axios.get(
          `/api/wells/data?wellPath=${encodeURIComponent(well.path)}`,
        );
        const wellData = response.data;
        const updatedWell = {
          ...well,
          datasets: wellData.datasets || [],
          wellName: wellData.wellName || well.name,
          _dataLoadTimestamp: Date.now(), // Track when data was loaded
        };
        setSelectedWell(updatedWell);
        setWells((prev) =>
          prev.map((w) => (w.id === well.id ? updatedWell : w)),
        );
      } catch (error) {
        console.error("Error loading well data:", error);
      }
    }
  };

  const handleGeneratePlotFromDataBrowser = (logNames: string[]) => {
    setSelectedLogsForPlot(logNames);
    togglePanel("wellLogPlot");
  };

  const handleDatasetSelect = (wellId: string, dataset: any) => {
    setSelectedDatasetByWell((prev) => {
      const newMap = new Map(prev);
      newMap.set(wellId, dataset);
      return newMap;
    });
  };

  const getSelectedDataset = (wellId: string) => {
    return selectedDatasetByWell.get(wellId) || null;
  };

  // Function to refresh the wells list
  const refreshWellsList = async () => {
    if (!projectPath || projectPath === "No path selected") {
      return;
    }

    try {
      console.log("[Workspace] Refreshing wells list...");

      // Get wells list for UI
      const response = await axios.get(
        `/api/wells/list?projectPath=${encodeURIComponent(projectPath)}`,
      );

      if (response.data.wells && Array.isArray(response.data.wells)) {
        let wellsToDisplay = response.data.wells;

        // Check if there are selected wells saved in storage for this project
        try {
          const projectName =
            projectPath.split("/").pop() ||
            projectPath.split("\\").pop() ||
            "project";
          const selectedWellsResponse = await axios.get(
            `/api/cli/selected-wells/${encodeURIComponent(projectName)}`,
          );

          if (
            selectedWellsResponse.data.success &&
            selectedWellsResponse.data.selected_wells &&
            selectedWellsResponse.data.selected_wells.length > 0
          ) {
            const selectedWellNames = selectedWellsResponse.data.selected_wells;
            wellsToDisplay = response.data.wells.filter((well: any) =>
              selectedWellNames.includes(well.name),
            );
            console.log(
              `[Workspace] Applied well filter: showing ${wellsToDisplay.length} of ${response.data.wells.length} wells`,
            );
          }
        } catch (filterError) {
          console.warn(
            "[Workspace] Could not load well filter from storage:",
            filterError,
          );
        }

        // Deduplicate wells by path to prevent React key warnings
        const uniqueWells = Array.from(
          new Map(wellsToDisplay.map((w: any) => [w.path, w])).values()
        );
        setWells(uniqueWells);
        console.log(
          `[Workspace] Refreshed well list: ${uniqueWells.length} wells (${wellsToDisplay.length} before dedup)`,
        );

        // Check if there's an active well to auto-select and update active well indicator
        try {
          const projectName =
            projectPath.split("/").pop() ||
            projectPath.split("\\").pop() ||
            "project";
          const activeWellResponse = await axios.get(
            `/api/cli/active-well/${encodeURIComponent(projectName)}`,
          );

          if (
            activeWellResponse.data.success &&
            activeWellResponse.data.active_well
          ) {
            const activeWellNameFromStorage =
              activeWellResponse.data.active_well;
            setActiveWellName(activeWellNameFromStorage);

            // Find and select the active well
            const wellToSelect = wellsToDisplay.find(
              (well: any) => well.name === activeWellNameFromStorage,
            );
            if (wellToSelect) {
              setSelectedWell(wellToSelect);
              console.log(
                `[Workspace] Auto-selected active well from storage: ${activeWellNameFromStorage}`,
              );
              (window as any).addAppLog?.(
                `✓ Active well selected: ${activeWellNameFromStorage}`,
                "success",
              );
            }
          } else {
            setActiveWellName(null);
          }
        } catch (activeWellError) {
          console.warn(
            "[Workspace] Could not load active well from storage:",
            activeWellError,
          );
          setActiveWellName(null);
        }
      }
    } catch (error) {
      console.error("[Workspace] Error refreshing wells list:", error);
    }
  };

  // Function to refresh the selected well's data (for Data Browser)
  const refreshWellData = async () => {
    if (!selectedWell?.path) {
      return;
    }

    try {
      console.log("[Workspace] Refreshing selected well data...");

      // Reload the well data to get updated datasets using canonical endpoint
      const response = await axios.get(
        `/api/wells/data?wellPath=${encodeURIComponent(selectedWell.path)}`,
      );

      if (response.data && response.data.datasets) {
        // Create a completely new well object with a timestamp to force Data Browser refresh
        const updatedWell = {
          ...selectedWell,
          datasets: response.data.datasets || [],
          wellName: response.data.wellName || selectedWell.name,
          _refreshTimestamp: Date.now(), // Force refresh by creating new object reference
        };

        setWells((prev) =>
          prev.map((w) => (w.id === selectedWell.id ? updatedWell : w)),
        );
        setSelectedWell(updatedWell);

        console.log(
          `[Workspace] Refreshed well data for: ${selectedWell.name}`,
        );
      }
    } catch (error) {
      console.error("[Workspace] Error refreshing well data:", error);
    }
  };

  // Toggle well lock for a specific window
  const toggleWindowWellLock = (
    windowId: string,
    currentWell: WellData | null,
  ) => {
    setWindowWellLocks((prev) => {
      const currentLock = prev.get(windowId);
      // Default to linked (true) if no state exists
      const currentIsLocked = currentLock?.isLocked !== false;
      const newIsLocked = !currentIsLocked;

      const newLocks = new Map(prev);
      if (newIsLocked) {
        // LINK the window - it will follow global well selection
        newLocks.set(windowId, { isLocked: true, lockedWell: null });
        console.log(
          `[Workspace] Linked window ${windowId} to follow global well selection`,
        );
        // Defer log to avoid state update during render
        setTimeout(() => {
          (window as any).addAppLog?.(
            `🔗 Window ${windowId} linked - will follow well selection`,
            "info",
            "🔗",
          );
        }, 0);
      } else {
        // UNLINK the window - capture current well so it stays locked to this well
        newLocks.set(windowId, { isLocked: false, lockedWell: currentWell });
        console.log(
          `[Workspace] Unlinked window ${windowId}, locked to well: ${currentWell?.name || "none"}`,
        );
        // Defer log to avoid state update during render
        setTimeout(() => {
          (window as any).addAppLog?.(
            `🔓 Window ${windowId} unlinked - locked to ${currentWell?.name || "current well"}`,
            "info",
            "🔓",
          );
        }, 0);
      }

      return newLocks;
    });
  };

  // Get the well to use for a specific window
  const getWellForWindow = (windowId: string): WellData | null => {
    const lockState = windowWellLocks.get(windowId);
    // If LINKED (isLocked=true), follow global selection
    // If UNLINKED (isLocked=false), stay on locked well
    if (lockState && !lockState.isLocked && lockState.lockedWell) {
      return lockState.lockedWell;
    }
    return selectedWell;
  };

  // Check if a window is locked (linked)
  // Returns true (linked) by default for new windows
  const isWindowLocked = (windowId: string): boolean => {
    const lockState = windowWellLocks.get(windowId);
    // Default to true (linked) if no lock state exists
    return lockState?.isLocked !== false;
  };

  // Empty Dock Panel Component
  const EmptyDockPanel = () => (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        height: "100%",
        backgroundColor: "transparent",
      }}
    >
      <div
        style={{
          fontSize: "48px",
          fontWeight: "300",
          color: "rgba(150, 150, 150, 0.3)",
          letterSpacing: "4px",
          textTransform: "uppercase",
        }}
      >
        Petrophysics
      </div>
    </div>
  );

  // RC Dock loadTab callback - dynamically creates panel content
  const loadTab = (data: any) => {
    const panelId = data.id as PanelId;
    // Extract the base panel type from unique IDs (e.g., "wellLogPlot_1" -> "wellLogPlot")
    const parts = panelId.toString().split("_");
    const basePanelType = parts[0] as PanelId;

    // Parse window index from panel ID if windowIndex is not provided (for restored layouts)
    let windowIndex = data.windowIndex;
    if (!windowIndex && parts.length > 1) {
      const parsedIndex = parseInt(parts[1], 10);
      windowIndex = isNaN(parsedIndex) ? 1 : parsedIndex;
    } else if (!windowIndex) {
      windowIndex = 1;
    }

    // Use lock state to determine which well to show in this window
    // For plot panels, use the well from lock state, otherwise use global selectedWell
    const wellForPanel =
      basePanelType === "wellLogPlot" ||
      basePanelType === "crossPlot" ||
      basePanelType === "logPlot" ||
      basePanelType === "dataBrowser"
        ? getWellForWindow(panelId.toString())
        : selectedWell;

    const panelSpecificProps =
      basePanelType === "wells"
        ? {
            wells,
            selectedWell,
            onWellSelect: handleWellSelect,
            activeWellName,
          }
        : basePanelType === "feedback"
          ? {
              onLoadWells: handleLoadWells,
              projectPath,
              selectedWell,
              autoScroll: feedbackAutoScroll,
              activeWindowId,
              activeWindowTitle: data.title,
            }
          : basePanelType === "zonation"
            ? { projectPath: projectPath || undefined, selectedWell }
            : basePanelType === "dataBrowser"
              ? {
                  selectedWell: wellForPanel,
                  projectPath,
                  onGeneratePlot: handleGeneratePlotFromDataBrowser,
                  selectedDataset: wellForPanel
                    ? getSelectedDataset(wellForPanel.id)
                    : null,
                  onDatasetSelect: wellForPanel
                    ? (dataset: any) =>
                        handleDatasetSelect(wellForPanel.id, dataset)
                    : undefined,
                  isLocked: isWindowLocked(panelId.toString()),
                  onToggleLock: () =>
                    toggleWindowWellLock(panelId.toString(), wellForPanel),
                  windowId: panelId,
                }
              : basePanelType === "wellLogPlot" || basePanelType === "logPlot"
                ? {
                    selectedWell: wellForPanel,
                    projectPath,
                    selectedLogsForPlot,
                    windowId: panelId,
                    windowIndex,
                    selectedDataset: wellForPanel
                      ? getSelectedDataset(wellForPanel.id)
                      : null,
                    onDatasetSelect: wellForPanel
                      ? (dataset: any) =>
                          handleDatasetSelect(wellForPanel.id, dataset)
                      : undefined,
                    isLocked: isWindowLocked(panelId.toString()),
                    onToggleLock: () =>
                      toggleWindowWellLock(panelId.toString(), wellForPanel),
                  }
                : basePanelType === "crossPlot"
                  ? {
                      selectedWell: wellForPanel,
                      projectPath,
                      selectedLogsForPlot,
                      windowId: panelId,
                      windowIndex,
                      selectedDataset: wellForPanel
                        ? getSelectedDataset(wellForPanel.id)
                        : null,
                      onDatasetSelect: wellForPanel
                        ? (dataset: any) =>
                            handleDatasetSelect(wellForPanel.id, dataset)
                        : undefined,
                      isLocked: isWindowLocked(panelId.toString()),
                      onToggleLock: () =>
                        toggleWindowWellLock(panelId.toString(), wellForPanel),
                      onOpenControlWindow: () => {
                        setCrossPlotControlTargetId(panelId.toString());
                        togglePanel("crossPlotControl");
                      },
                      externalXLog:
                        crossPlotSelections[panelId.toString()]?.xLog,
                      externalYLog:
                        crossPlotSelections[panelId.toString()]?.yLog,
                    }
                  : basePanelType === "crossPlotControl"
                    ? {
                        selectedWell: selectedWell,
                        projectPath,
                        panelId: panelId.toString(),
                        targetWindowId: crossPlotControlTargetId,
                        initialXLog: crossPlotControlTargetId
                          ? crossPlotSelections[crossPlotControlTargetId]?.xLog
                          : undefined,
                        initialYLog: crossPlotControlTargetId
                          ? crossPlotSelections[crossPlotControlTargetId]?.yLog
                          : undefined,
                        onPlotConfigChange: (
                          windowId: string,
                          xLog: string,
                          yLog: string,
                        ) => {
                          setCrossPlotSelections((prev) => ({
                            ...prev,
                            [windowId]: { xLog, yLog },
                          }));
                        },
                      }
                    : basePanelType === "cli"
                      ? {
                          projectPath: projectPath || undefined,
                          onRefreshWells: refreshWellsList,
                          onRefreshWellData: refreshWellData,
                        }
                      : {};

    const PanelMap: Record<string, any> = {
      wells: WellsPanelNew,
      zonation: ZonationPanelNew,
      dataBrowser: DataBrowserPanelNew,
      feedback: FeedbackPanelNew,
      wellLogPlot: WellLogPlotPanel,
      crossPlot: CrossPlotPanel,
      crossPlotControl: CrossPlotControlPanel,
      logPlot: LogPlotPanel,
      cli: CLIPanel,
      settings: (props: any) => <SettingsPanel {...props} projectPath={projectPath} />,
      emptyDock: EmptyDockPanel,
    };

    const PanelComponent = PanelMap[basePanelType] || PanelMap[panelId];
    // Use projectPath, wellId, windowId, and lock state as key to force complete remount when these change
    // This ensures child components fully reset and don't show stale data
    // IMPORTANT: Use wellForPanel (not selectedWell) for plot/browser panels so linked windows update correctly
    const wellId = wellForPanel
      ? wellForPanel.id || wellForPanel.name
      : "no-well";
    const lockState = isWindowLocked(panelId.toString())
      ? "linked"
      : "unlinked";
    const componentKey =
      basePanelType === "dataBrowser" ||
      basePanelType === "wellLogPlot" ||
      basePanelType === "crossPlot" ||
      basePanelType === "logPlot"
        ? `${panelId}-${projectPath}-${wellId}-${lockState}`
        : basePanelType === "cli"
          ? `${panelId}-${projectPath}`
          : panelId;

    return {
      id: data.id,
      title: data.title,
      content: <PanelComponent key={componentKey} {...panelSpecificProps} />,
      group: data.group || "default",
    };
  };

  // Default RC Dock layout structure matching user's image:
  // 3-column grid layout:
  // Column 1 (left): Wells + Zonation stacked
  // Column 2 (center): Empty dock + Feedback Logs stacked
  // Column 3 (right): Data Browser + CLI Terminal stacked
  const defaultLayout = useMemo(
    () => ({
      dockbox: {
        mode: "horizontal" as const,
        children: [
          {
            size: 220,
            mode: "vertical" as const,
            children: [
              {
                tabs: [
                  {
                    id: "wells",
                    title: "Wells",
                    closable: true,
                    group: "default",
                    content: <div />,
                  },
                ],
              },
              {
                tabs: [
                  {
                    id: "zonation",
                    title: "Zonation",
                    closable: true,
                    group: "default",
                    content: <div />,
                  },
                ],
              },
            ],
          },
          {
            size: 700,
            mode: "vertical" as const,
            children: [
              {
                tabs: [
                  {
                    id: "emptyDock",
                    title: "Empty dock",
                    closable: false,
                    group: "default",
                    content: <div style={{ 
                      display: 'flex', 
                      alignItems: 'center', 
                      justifyContent: 'center',
                      height: '100%',
                      color: '#666',
                      fontSize: '14px'
                    }}>
                      Drag panels here
                    </div>,
                  },
                ],
              },
              {
                tabs: [
                  {
                    id: "feedback",
                    title: "Feedback Logs",
                    closable: true,
                    group: "default",
                    content: <div />,
                  },
                ],
              },
            ],
          },
          {
            size: 300,
            mode: "vertical" as const,
            children: [
              {
                tabs: [
                  {
                    id: "dataBrowser",
                    title: "Data Browser",
                    closable: true,
                    group: "default",
                    content: <div />,
                  },
                ],
              },
              {
                tabs: [
                  {
                    id: "cli",
                    title: "CLI Terminal",
                    closable: true,
                    group: "default",
                    content: <div />,
                  },
                ],
              },
            ],
          },
        ],
      },
    }),
    [],
  );

  // Open a new floating window for a panel
  const openFloatingWindow = (panelId: PanelId) => {
    if (dockRef.current) {
      // Generate unique ID and title for logplot and crossplot windows
      let uniqueId = panelId;
      let windowTitle = PANEL_TITLES[panelId];
      let windowIndex = 1;

      if (panelId === "wellLogPlot") {
        windowIndex = plotWindowCounter;
        uniqueId = `wellLogPlot_${plotWindowCounter}` as PanelId;
        windowTitle = `Well Log Plot #${plotWindowCounter}`;
        setPlotWindowCounter((prev) => prev + 1);
      } else if (panelId === "crossPlot") {
        windowIndex = crossPlotWindowCounter;
        uniqueId = `crossPlot_${crossPlotWindowCounter}` as PanelId;
        windowTitle = `Cross Plot #${crossPlotWindowCounter}`;
        setCrossPlotWindowCounter((prev) => prev + 1);
      } else if (panelId === "logPlot") {
        windowIndex = plotWindowCounter; // Use same counter as wellLogPlot
        uniqueId = `logPlot_${plotWindowCounter}` as PanelId;
        windowTitle = `Log Plot #${plotWindowCounter}`;
        setPlotWindowCounter((prev) => prev + 1);
      }

      const newTab = loadTab({
        id: uniqueId,
        title: windowTitle,
        group: "default",
        windowIndex: windowIndex,
        windowType: panelId,
      });

      // Stagger window positions based on counter to avoid overlapping
      const offset = (windowIndex - 1) * 30;

      // Create floating window with specific position and size
      const floatingPanel = {
        ...newTab,
        x: 100 + offset,
        y: 100 + offset,
        w: 800,
        h: 600,
        z: windowIndex,
      };

      // Add to layout as floating window
      dockRef.current.dockMove(floatingPanel, null, "float");

      // Set this as active window and log to feedback
      setActiveWindowId(uniqueId);
      (window as any).addAppLog?.(`📊 Opened ${windowTitle}`, "success", "📊");
    }
  };

  // Handle layout changes to detect when well log plot is closed and track active window
  const handleLayoutChange = (
    newLayout: any,
    currentTabId?: string,
    direction?: string,
  ) => {
    // Track active window when a tab is activated
    if (currentTabId && direction === "active") {
      setActiveWindowId(currentTabId);

      // Find the tab title from the layout
      const findTabTitle = (box: any, tabId: string): string | null => {
        if (box.tabs) {
          const tab = box.tabs.find((t: any) => t.id === tabId);
          if (tab) return tab.title;
        }
        if (box.children) {
          for (const child of box.children) {
            const title = findTabTitle(child, tabId);
            if (title) return title;
          }
        }
        return null;
      };

      let title = null;
      if (newLayout?.dockbox) {
        title = findTabTitle(newLayout.dockbox, currentTabId);
      }
      if (!title && newLayout?.floatbox) {
        title = findTabTitle(newLayout.floatbox, currentTabId);
      }

      if (
        title &&
        (currentTabId.startsWith("wellLogPlot_") ||
          currentTabId.startsWith("crossPlot_"))
      ) {
        (window as any).addAppLog?.(`🎯 Focused: ${title}`, "info", "🎯");
      }
    }

    // Check if wellLogPlot tab still exists in the layout
    const checkTabExists = (box: any): boolean => {
      if (box.tabs) {
        if (box.tabs.some((tab: any) => tab.id === "wellLogPlot")) {
          return true;
        }
      }
      if (box.children) {
        for (const child of box.children) {
          if (checkTabExists(child)) return true;
        }
      }
      return false;
    };

    // Check both dockbox and floatbox for the wellLogPlot tab
    let tabExists = false;
    if (newLayout?.dockbox) {
      tabExists = checkTabExists(newLayout.dockbox);
    }
    if (!tabExists && newLayout?.floatbox) {
      tabExists = checkTabExists(newLayout.floatbox);
    }
    if (!tabExists && newLayout?.maxbox) {
      tabExists = checkTabExists(newLayout.maxbox);
    }

    // Update state if well log plot was closed
    if (!tabExists && wellLogPlotFloatingOpen) {
      setWellLogPlotFloatingOpen(false);
    }
  };

  // Toggle well log plot floating window
  const toggleWellLogPlotFloating = () => {
    if (!dockRef.current) return;

    if (wellLogPlotFloatingOpen) {
      // Close the floating window by finding and removing the wellLogPlot tab
      const layout = dockRef.current.getLayout();
      const findAndRemoveTab = (box: any): boolean => {
        if (box.tabs) {
          const wellLogIndex = box.tabs.findIndex(
            (tab: any) => tab.id === "wellLogPlot",
          );
          if (wellLogIndex !== -1) {
            box.tabs.splice(wellLogIndex, 1);
            return true;
          }
        }
        if (box.children) {
          for (const child of box.children) {
            if (findAndRemoveTab(child)) return true;
          }
        }
        return false;
      };

      // Check dockbox, floatbox, and maxbox
      let found = false;
      if (layout.dockbox && findAndRemoveTab(layout.dockbox)) {
        found = true;
      }
      if (!found && layout.floatbox && findAndRemoveTab(layout.floatbox)) {
        found = true;
      }
      if (!found && layout.maxbox && findAndRemoveTab(layout.maxbox)) {
        found = true;
      }

      if (found) {
        dockRef.current.loadLayout(layout);
        setWellLogPlotFloatingOpen(false);
      } else {
        // Tab was already closed manually, reset state and reopen
        setWellLogPlotFloatingOpen(false);
        const newTab = loadTab({
          id: "wellLogPlot",
          title: PANEL_TITLES.wellLogPlot,
          group: "default",
        });
        dockRef.current.dockMove(newTab, null, "float");
        setWellLogPlotFloatingOpen(true);
      }
    } else {
      // Open as floating window
      const newTab = loadTab({
        id: "wellLogPlot",
        title: PANEL_TITLES.wellLogPlot,
        group: "default",
      });
      dockRef.current.dockMove(newTab, null, "float");
      setWellLogPlotFloatingOpen(true);
    }
  };

  const groups = {
    default: {
      floatable: true,
      maximizable: true,
      newWindow: true,
      closable: true,
      panelLock: {
        panelStyle: "default",
      },
      tabLocked: false,
      disableDock: false,
      animated: true,
      panelExtra: (panelData: any, context: any) => {
        const activeTab = panelData.activeId;
        const isMaximized = panelData.parent.mode === "maximize";
        const isWindow = panelData.parent.mode === "window";

        // Info content based on active tab
        let infoContent = null;
        const wellBelongsToProject =
          selectedWell &&
          selectedWell.path &&
          projectPath &&
          (selectedWell.path === projectPath ||
            selectedWell.path.startsWith(projectPath + "/") ||
            selectedWell.path.startsWith(projectPath + "\\"));

        if (activeTab === "wells" && wells.length > 0) {
          infoContent = (
            <div
              style={{
                fontSize: "12px",
                opacity: 0.7,
                marginRight: "8px",
                fontWeight: "500",
              }}
            >
              {wells.length} {wells.length === 1 ? "well" : "wells"}
            </div>
          );
        } else if (activeTab === "dataBrowser" && wellBelongsToProject) {
          infoContent = (
            <div
              style={{
                fontSize: "12px",
                opacity: 0.7,
                marginRight: "8px",
                fontWeight: "500",
              }}
            >
              {selectedWell.name}
            </div>
          );
        } else if (activeTab === "wellLogPlot" && wellBelongsToProject) {
          infoContent = (
            <div
              style={{
                fontSize: "12px",
                opacity: 0.7,
                marginRight: "8px",
                fontWeight: "500",
              }}
            >
              Plot: {selectedWell.name}
            </div>
          );
        } else if (activeTab === "crossPlot" || activeTab === "logPlot") {
          infoContent = (
            <div
              style={{
                fontSize: "12px",
                opacity: 0.7,
                marginRight: "8px",
                fontWeight: "500",
              }}
            >
              {wellBelongsToProject ? selectedWell.name : "No well selected"}
            </div>
          );
        } else if (activeTab === "feedback") {
          infoContent = (
            <div
              style={{
                fontSize: "12px",
                opacity: 0.7,
                marginRight: "8px",
                fontWeight: "500",
              }}
            >
              Console
            </div>
          );
        }

        // Control buttons array
        const buttons = [];

        // Minimize/Maximize button (don't show in window mode)
        if (!isWindow) {
          buttons.push(
            <span
              key="minimize-maximize"
              className="panel-control-btn"
              title={isMaximized ? "Restore" : "Maximize"}
              onClick={(e: React.MouseEvent) => {
                context.dockMove(panelData, null, "maximize");
                e.stopPropagation();
              }}
              style={{
                cursor: "pointer",
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                width: "20px",
                height: "20px",
                opacity: 0.6,
                transition: "opacity 0.2s",
                fontSize: "14px",
                fontWeight: "bold",
              }}
              onMouseEnter={(e) => (e.currentTarget.style.opacity = "1")}
              onMouseLeave={(e) => (e.currentTarget.style.opacity = "0.6")}
            >
              {isMaximized ? "▬" : "▣"}
            </span>,
          );
        }

        // New Window button (don't show if already in window mode)
        if (!isWindow) {
          buttons.push(
            <span
              key="new-window"
              className="panel-control-btn"
              title="Open in new window"
              onClick={(e: React.MouseEvent) => {
                context.dockMove(panelData, null, "new-window");
                e.stopPropagation();
              }}
              style={{
                cursor: "pointer",
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                width: "20px",
                height: "20px",
                opacity: 0.6,
                transition: "opacity 0.2s",
                fontSize: "14px",
                fontWeight: "bold",
              }}
              onMouseEnter={(e) => (e.currentTarget.style.opacity = "1")}
              onMouseLeave={(e) => (e.currentTarget.style.opacity = "0.6")}
            >
              ⇪
            </span>,
          );
        }

        // Dock Back button (only show in window mode)
        if (isWindow) {
          buttons.push(
            <span
              key="dock-back"
              className="panel-control-btn"
              title="Bring back to main window"
              onClick={(e: React.MouseEvent) => {
                // Move panel back to dockbox in the middle
                context.dockMove(panelData, "dockbox", "middle");
                e.stopPropagation();
              }}
              style={{
                cursor: "pointer",
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                width: "20px",
                height: "20px",
                opacity: 0.6,
                transition: "opacity 0.2s",
                fontSize: "14px",
                fontWeight: "bold",
              }}
              onMouseEnter={(e) => (e.currentTarget.style.opacity = "1")}
              onMouseLeave={(e) => (e.currentTarget.style.opacity = "0.6")}
            >
              ⇩
            </span>,
          );
        }

        // Close button (always show)
        buttons.push(
          <span
            key="close"
            className="panel-control-btn"
            title="Close"
            onClick={(e: React.MouseEvent) => {
              context.dockMove(panelData, null, "remove");
              e.stopPropagation();
            }}
            style={{
              cursor: "pointer",
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              width: "20px",
              height: "20px",
              opacity: 0.6,
              transition: "opacity 0.2s",
              fontSize: "14px",
              fontWeight: "bold",
            }}
            onMouseEnter={(e) => (e.currentTarget.style.opacity = "1")}
            onMouseLeave={(e) => (e.currentTarget.style.opacity = "0.6")}
          >
            ✕
          </span>,
        );

        return (
          <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
            {infoContent}
            {buttons}
          </div>
        );
      },
    },
  };

  // Use effect to update dock when wells or selectedWell changes
  useEffect(() => {
    if (dockRef.current) {
      // Force update of the dock layout to re-render panels with new data
      dockRef.current.updateTab(
        "wells",
        loadTab({ id: "wells", title: "Wells" }),
      );
      if (selectedWell) {
        dockRef.current.updateTab(
          "dataBrowser",
          loadTab({ id: "dataBrowser", title: "Data Browser" }),
        );
        dockRef.current.updateTab(
          "wellLogPlot",
          loadTab({ id: "wellLogPlot", title: "Well Log Plot" }),
        );
      }
    }
  }, [wells, selectedWell]);

  // Update CLI panel when projectPath changes
  useEffect(() => {
    if (dockRef.current && projectPath) {
      dockRef.current.updateTab(
        "cli",
        loadTab({ id: "cli", title: "CLI Terminal" }),
      );
    }
  }, [projectPath]);

  return (
    <div className="h-screen w-full flex flex-col bg-[#F0F4F5] dark:bg-background">
      {/* Sticky Menu Bar */}
      <div className="sticky top-0 z-50 bg-white dark:bg-card">
        <MenuBar
          onTogglePanel={togglePanel}
          onOpenFloatingWindow={openFloatingWindow}
          onToggleWellLogPlotFloating={toggleWellLogPlotFloating}
          wellLogPlotFloatingOpen={wellLogPlotFloatingOpen}
          visiblePanels={visiblePanels}
          onSaveLayout={saveLayout}
          onLoadLayout={loadLayout}
          onResetLayout={resetToDefaultLayout}
          theme={theme}
          onToggleTheme={toggleTheme}
          feedbackAutoScroll={feedbackAutoScroll}
          onToggleFeedbackAutoScroll={() =>
            setFeedbackAutoScroll((prev) => !prev)
          }
          projectPath={projectPath}
          wellCount={wells.length}
          onProjectPathChange={handleProjectFolderSelect}
          onSaveProject={saveProjectData}
          onOpenProjectList={() => setProjectListOpen(true)}
          onOpenImportPicker={handleOpenImportPicker}
          onOpenProjectPicker={handleOpenProjectPicker}
          onNewWell={handleOpenNewWellDialog}
          currentLayoutName={currentLayoutName}
          onToggleMobileSidebar={() => {}}
          isMobileSidebarOpen={false}
        />

        <ProjectInfoBar
          projectPath={projectPath}
          projectName={projectName}
          wellCount={wells.length}
          selectedLayout={{ name: currentLayoutName }}
          selectedDataset={
            selectedWell?.id ? getSelectedDataset(selectedWell.id) : null
          }
        />
      </div>

      {/* RC Dock Layout */}
      <div className="flex-1 relative" data-theme={theme}>
        <DockLayout
          ref={dockRef}
          defaultLayout={defaultLayout}
          loadTab={loadTab}
          groups={groups}
          onLayoutChange={handleLayoutChange}
          style={{
            position: "absolute",
            left: 0,
            top: 0,
            right: 0,
            bottom: 0,
          }}
        />
      </div>

      {/* Mobile Panel Selector Button */}
      <Button
        className="fixed bottom-20 right-4 md:hidden z-40 h-14 w-14 rounded-full shadow-lg"
        onClick={() => setMobilePanelSelectorOpen(true)}
      >
        <Layers className="h-6 w-6" />
      </Button>

      {/* Mobile Panel Selector Sheet */}
      <Sheet
        open={mobilePanelSelectorOpen}
        onOpenChange={setMobilePanelSelectorOpen}
      >
        <SheetContent side="bottom" className="h-[60vh]">
          <SheetHeader>
            <SheetTitle>All Panels</SheetTitle>
            <SheetDescription>Select a panel to view</SheetDescription>
          </SheetHeader>
          <div className="grid grid-cols-2 gap-3 mt-6">
            {Object.entries(PANEL_TITLES).map(([id, title]) => (
              <Button
                key={id}
                variant={visiblePanels.has(id) ? "default" : "outline"}
                className="h-20 flex flex-col items-center justify-center gap-2"
                onClick={() => {
                  togglePanel(id as PanelId);
                  setMobilePanelSelectorOpen(false);
                }}
              >
                <span className="font-semibold">{title}</span>
                {visiblePanels.has(id) && (
                  <span className="text-xs opacity-75">Active</span>
                )}
              </Button>
            ))}
          </div>
        </SheetContent>
      </Sheet>

      <ProjectListDialog
        open={projectListOpen}
        onOpenChange={setProjectListOpen}
        onSelectProject={async (fileName) => {
          try {
            await handleLoadProject(fileName);
            toast({
              title: "Project Loaded",
              description: "Project data loaded successfully.",
            });
          } catch (error) {
            toast({
              title: "Load Failed",
              description:
                error instanceof Error
                  ? error.message
                  : "Failed to load project",
              variant: "destructive",
            });
            throw error;
          }
        }}
      />

      <DirectoryPicker
        open={directoryPickerOpen}
        onOpenChange={setDirectoryPickerOpen}
        onSelectPath={handleDirectorySelect}
        initialPath={projectPath}
        currentProjectPath={projectPath}
        onProjectDeleted={() => {
          setProjectPath("");
          setProjectName("");
          setWells([]);
          localStorage.removeItem("lastProjectPath");
          localStorage.removeItem("lastProjectName");
          localStorage.removeItem("lastProjectCreatedAt");
          toast({
            title: "Project Deleted",
            description:
              "The current project has been deleted. Please select a new project.",
          });
        }}
      />

      <NewWellDialog
        open={newWellDialogOpen}
        onOpenChange={setNewWellDialogOpen}
        projectPath={projectPath}
        onWellCreated={handleWellCreated}
      />
    </div>
  );
}
