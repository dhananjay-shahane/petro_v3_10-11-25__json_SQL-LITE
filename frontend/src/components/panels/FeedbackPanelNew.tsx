import { Button } from "@/components/ui/button";
import {
  Terminal,
  Trash2,
  AlertCircle,
  CheckCircle,
  Info,
  AlertTriangle,
  FileText,
  BarChart3,
  TrendingUp,
  Database,
  Wrench,
  Folder,
  Globe,
} from "lucide-react";
import { useState, useEffect, useRef } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useToast } from "@/hooks/use-toast";

interface LogEntry {
  timestamp: string;
  message: string;
  type: "info" | "error" | "success" | "warning";
  iconType?: string;
}

interface WellData {
  id: string;
  name: string;
  uwi?: string;
  field?: string;
  operator?: string;
  location?: string;
}

export default function FeedbackPanelNew({
  projectPath,
  selectedWell,
  autoScroll = true,
  activeWindowId,
  activeWindowTitle,
}: {
  projectPath?: string;
  selectedWell?: WellData | null;
  autoScroll?: boolean;
  activeWindowId?: string;
  activeWindowTitle?: string;
}) {
  const [logs, setLogs] = useState<LogEntry[]>(() => {
    const savedLogs = localStorage.getItem("feedbackLogs");
    if (savedLogs) {
      try {
        return JSON.parse(savedLogs);
      } catch {
        return [
          {
            timestamp: new Date().toLocaleTimeString(),
            message: "Feedback console initialized",
            type: "info",
            iconType: "wrench",
          },
        ];
      }
    }
    return [
      {
        timestamp: new Date().toLocaleTimeString(),
        message: "Feedback console initialized",
        type: "info",
        iconType: "wrench",
      },
    ];
  });
  const { toast } = useToast();
  const scrollRef = useRef<HTMLDivElement>(null);
  const scrollEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    localStorage.setItem("feedbackLogs", JSON.stringify(logs));
    if (autoScroll) {
      scrollEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [logs, autoScroll]);

  const addLog = (
    message: string,
    type: LogEntry["type"] = "info",
    iconType?: string,
  ) => {
    // Remove emojis from message (simple working pattern)
    const cleanMessage = message
      .replace(/[\u{1F300}-\u{1F9FF}]/gu, '')
      .replace(/[\u{2600}-\u{26FF}]/gu, '')
      .replace(/[\u{2700}-\u{27BF}]/gu, '')
      .trim();
    
    const newLog: LogEntry = {
      timestamp: new Date().toLocaleTimeString(),
      message: cleanMessage,
      type,
      iconType,
    };
    setLogs((prev) => [...prev, newLog]);
  };

  const clearLogs = () => {
    const newLogs: LogEntry[] = [
      {
        timestamp: new Date().toLocaleTimeString(),
        message: "Logs cleared",
        type: "info",
        iconType: "trash",
      },
    ];
    setLogs(newLogs);
    localStorage.setItem("feedbackLogs", JSON.stringify(newLogs));
  };

  const getLogColor = (type: LogEntry["type"]) => {
    switch (type) {
      case "error":
        return "text-red-400 font-semibold";
      case "success":
        return "text-emerald-400 font-medium";
      case "warning":
        return "text-yellow-400 font-medium";
      default:
        return "text-slate-200";
    }
  };

  const getIconForMessage = (
    message: string,
    type: LogEntry["type"],
  ): string => {
    if (message.includes("project") && message.toLowerCase().includes("open"))
      return "folder";
    if (message.includes("LAS") && message.includes("upload")) return "upload";
    if (message.includes("well") && message.includes("creat")) return "wrench";
    if (message.includes("[LOG PLOT]")) return "barchart";
    if (message.includes("[CROSS PLOT]")) return "trending";
    if (message.includes("data") && message.includes("load")) return "database";
    if (message.includes("GET") || message.includes("POST")) return "globe";
    if (type === "error") return "error";
    if (type === "success") return "success";
    if (type === "warning") return "warning";
    return "info";
  };

  const getIconComponent = (iconType?: string) => {
    const iconClass = "w-4 h-4 shrink-0";
    switch (iconType) {
      case "folder":
        return <Folder className={iconClass} />;
      case "upload":
        return <FileText className={iconClass} />;
      case "wrench":
        return <Wrench className={iconClass} />;
      case "barchart":
        return <BarChart3 className={iconClass} />;
      case "trending":
        return <TrendingUp className={iconClass} />;
      case "database":
        return <Database className={iconClass} />;
      case "globe":
        return <Globe className={iconClass} />;
      case "error":
        return <AlertCircle className={iconClass} />;
      case "success":
        return <CheckCircle className={iconClass} />;
      case "warning":
        return <AlertTriangle className={iconClass} />;
      case "trash":
        return <Trash2 className={iconClass} />;
      case "info":
      default:
        return <Info className={iconClass} />;
    }
  };

  useEffect(() => {
    const originalLog = console.log;
    const originalError = console.error;
    const originalWarn = console.warn;
    const originalFetch = window.fetch;

    console.log = (...args) => {
      originalLog(...args);
      const message = args
        .map((a) =>
          typeof a === "object" ? JSON.stringify(a, null, 2) : String(a),
        )
        .join(" ");

      // Filter to only show relevant messages, exclude internal debug logs
      const shouldLog = 
        message.includes("[LOG PLOT]") ||
        message.includes("[CROSS PLOT]") ||
        message.includes("[LogPlot]") ||
        message.includes("[CrossPlot]") ||
        (message.includes("project") && !message.includes("Saving current project to storage")) ||
        (message.includes("well") && !message.includes("Rehydrated") && !message.includes("Auto-selecting")) ||
        message.includes("upload") ||
        message.includes("Loading all wells") ||
        message.includes("Loaded") && message.includes("cache");
      
      // Exclude internal workspace logs
      const shouldExclude =
        message.includes("Workspace info loaded") ||
        message.includes("Project changed to:") ||
        message.includes("clearing all data") ||
        message.includes("Rehydrated window locks") ||
        message.includes("Saving current project to storage") ||
        message.includes("Auto-selecting active well");

      if (shouldLog && !shouldExclude) {
        const iconType = getIconForMessage(message, "info");
        addLog(message, "info", iconType);
      }
    };

    console.error = (...args) => {
      originalError(...args);
      const message = args
        .map((a) =>
          typeof a === "object" ? JSON.stringify(a, null, 2) : String(a),
        )
        .join(" ");
      
      // Filter out development/HMR errors that are not user-relevant
      const shouldExclude = 
        message.includes("Failed to reload /src/index.css") ||
        message.includes("[hmr]") ||
        message.includes("502") ||  // Backend restart during HMR
        message.includes("Failed to load wells into cache") ||
        message.includes("Failed to load command history") ||
        message.includes("Failed to load commands") ||
        message.includes("Error saving project to storage") ||
        message.includes("AbortError") ||  // Cancelled requests during development
        message.includes("signal is aborted");
      
      if (!shouldExclude) {
        addLog(message, "error", "error");
      }
    };

    console.warn = (...args) => {
      originalWarn(...args);
      const message = args
        .map((a) =>
          typeof a === "object" ? JSON.stringify(a, null, 2) : String(a),
        )
        .join(" ");
      
      // Filter out development warnings
      const shouldExclude = 
        message.includes("Failed to load wells into cache") ||
        message.includes("502");
      
      if (!shouldExclude) {
        addLog(message, "warning", "warning");
      }
    };

    window.fetch = async (...args) => {
      const startTime = Date.now();
      const url =
        typeof args[0] === "string"
          ? args[0]
          : args[0] instanceof Request
            ? args[0].url
            : args[0]?.toString() || "unknown";
      const method = (args[1]?.method || "GET").toUpperCase();

      try {
        const response = await originalFetch(...args);
        const duration = Date.now() - startTime;

        const urlPath = url.split("?")[0];
        const wellInfo = selectedWell ? ` [Well: ${selectedWell.name}]` : "";
        
        // Don't log internal API calls that happen frequently
        const shouldSkipLog = 
          urlPath.includes("/api/workspace/info") ||
          urlPath.includes("/api/cli/commands");
        
        if (shouldSkipLog) {
          return response;
        }
        
        let logMessage = `${method} ${urlPath} - ${response.status} (${duration}ms)${wellInfo}`;
        let logType: LogEntry["type"] = "info";
        let iconType = "globe";

        if (urlPath.includes("/api/wells/create-from-las")) {
          logMessage = `LAS Upload Request - ${response.status} (${duration}ms)`;
          logType = response.ok ? "success" : "error";
          iconType = "upload";
        } else if (urlPath.includes("/log-plot")) {
          logMessage = `Log Plot Generation${wellInfo} - ${response.status} (${duration}ms)`;
          logType = response.ok ? "success" : "error";
          iconType = "barchart";
        } else if (urlPath.includes("/cross-plot")) {
          logMessage = `Cross Plot Generation${wellInfo} - ${response.status} (${duration}ms)`;
          logType = response.ok ? "success" : "error";
          iconType = "trending";
        } else if (urlPath.includes("/datasets")) {
          logMessage = `Data Loading${wellInfo} - ${response.status} (${duration}ms)`;
          logType = response.ok ? "success" : "error";
          iconType = "database";
        } else if (urlPath.includes("/api/wells")) {
          logMessage = `Well Operation - ${response.status} (${duration}ms)`;
          logType = response.ok ? "success" : "error";
          iconType = "wrench";
        }

        if (!response.ok) {
          logType = "error";
        }

        addLog(logMessage, logType, iconType);

        return response;
      } catch (error) {
        const duration = Date.now() - startTime;
        const wellInfo = selectedWell ? ` [Well: ${selectedWell.name}]` : "";
        const errorMessage = error instanceof Error ? error.message : String(error);
        
        // Don't log AbortErrors (cancelled requests during development)
        if (errorMessage.includes("aborted") || errorMessage.includes("AbortError")) {
          throw error;
        }
        
        addLog(
          `${method} ${url}${wellInfo} - Failed (${duration}ms): ${error}`,
          "error",
          "error",
        );
        throw error;
      }
    };

    (window as any).addAppLog = (
      message: string,
      type: LogEntry["type"] = "info",
      iconType?: string,
    ) => {
      const logIconType = iconType || getIconForMessage(message, type);
      addLog(message, type, logIconType);
    };

    (window as any).addPythonLog = (
      message: string,
      type: LogEntry["type"] = "info",
    ) => {
      const iconType = getIconForMessage(message, type);
      addLog(message, type, iconType);
    };

    return () => {
      console.log = originalLog;
      console.error = originalError;
      console.warn = originalWarn;
      window.fetch = originalFetch;
      delete (window as any).addAppLog;
      delete (window as any).addPythonLog;
    };
  }, [selectedWell]);

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-3 py-2 border-b border-border bg-muted/30">
        <div className="flex items-center gap-2 text-sm text-muted-foreground flex-wrap">
          <div className="flex items-center gap-2">
            <Terminal className="w-4 h-4" />
            <span>Activity Log</span>
          </div>
        </div>
        <Button size="sm" variant="ghost" onClick={clearLogs} className="h-7">
          <Trash2 className="w-3.5 h-3.5 mr-1.5" />
          Clear
        </Button>
      </div>

      <div className="flex-1 overflow-scroll h-full max-h-[500px]">
        <div
          ref={scrollRef}
          className="h-full overflow-y-auto p-3 font-mono bg-slate-950 dark:bg-slate-950"
          style={{ fontSize: 'var(--font-size-feedback-log, 13px)' }}
        >
          {logs.map((log, index) => (
            <div key={index} className="mb-1.5 flex gap-2 items-start leading-relaxed">
              <span className="text-slate-400 flex-shrink-0 font-medium">
                [{log.timestamp}]
              </span>
              {log.iconType && (
                <span className="flex-shrink-0 mt-0.5">
                  {getIconComponent(log.iconType)}
                </span>
              )}
              <span className={getLogColor(log.type)}>{log.message}</span>
            </div>
          ))}
          <div ref={scrollEndRef} />
        </div>
      </div>
    </div>
  );
}
