import DockPanel from "./DockPanel";
import { Button } from "@/components/ui/button";
import { useState, useEffect, useRef } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";

interface LogEntry {
  timestamp: string;
  type: 'api' | 'backend' | 'test';
  level: 'info' | 'success' | 'error' | 'warning';
  message: string;
  data?: any;
  endpoint?: string;
  method?: string;
  status?: number;
}

export default function FeedbackPanel({
  onClose,
  onMinimize,
  onMaximize,
}: {
  onClose?: () => void;
  onMinimize?: () => void;
  onMaximize?: () => void;
}) {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [selectedLog, setSelectedLog] = useState<LogEntry | null>(null);
  const [autoScroll, setAutoScroll] = useState(true);
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  // Intercept console logs and API calls
  useEffect(() => {
    // Store original console methods
    const originalLog = console.log;
    const originalError = console.error;
    const originalWarn = console.warn;

    // Listen for custom activity events
    const handleActivityEvent = (event: CustomEvent) => {
      const { type, message, level, data } = event.detail;
      addLog({
        timestamp: new Date().toLocaleTimeString(),
        type: type || 'test',
        level: level || 'info',
        message: message,
        data: data,
      });
    };

    window.addEventListener('app-activity' as any, handleActivityEvent);

    // Override console.log to capture logs
    console.log = (...args) => {
      originalLog(...args);
      
      // Check if this is a backend log (from our API responses)
      const message = args.map(a => typeof a === 'object' ? JSON.stringify(a, null, 2) : String(a)).join(' ');
      
      if (message.includes('[LOG PLOT]') || message.includes('[CROSS PLOT]') || 
          message.includes('[LogPlot]') || message.includes('[CrossPlot]')) {
        addLog({
          timestamp: new Date().toLocaleTimeString(),
          type: 'backend',
          level: 'info',
          message: message,
        });
      }
    };

    console.error = (...args) => {
      originalError(...args);
      const message = args.map(a => typeof a === 'object' ? JSON.stringify(a, null, 2) : String(a)).join(' ');
      addLog({
        timestamp: new Date().toLocaleTimeString(),
        type: 'backend',
        level: 'error',
        message: message,
      });
    };

    console.warn = (...args) => {
      originalWarn(...args);
      const message = args.map(a => typeof a === 'object' ? JSON.stringify(a, null, 2) : String(a)).join(' ');
      addLog({
        timestamp: new Date().toLocaleTimeString(),
        type: 'backend',
        level: 'warning',
        message: message,
      });
    };

    // Intercept fetch to log API calls
    const originalFetch = window.fetch;
    window.fetch = async (...args) => {
      const [url, options] = args;
      const method = options?.method || 'GET';
      const startTime = Date.now();
      
      try {
        const response = await originalFetch(...args);
        const duration = Date.now() - startTime;
        
        // Clone response to read body without consuming it
        const clonedResponse = response.clone();
        let responseData = null;
        
        try {
          responseData = await clonedResponse.json();
        } catch {
          try {
            responseData = await clonedResponse.text();
          } catch {
            responseData = '[Unable to read response]';
          }
        }
        
        // Safely parse request body
        let requestData = null;
        if (options?.body) {
          if (typeof options.body === 'string') {
            try {
              requestData = JSON.parse(options.body);
            } catch {
              requestData = options.body; // Keep as string if not JSON
            }
          } else {
            requestData = '[Non-text body]';
          }
        }
        
        addLog({
          timestamp: new Date().toLocaleTimeString(),
          type: 'api',
          level: response.ok ? 'success' : 'error',
          message: `${method} ${url} - ${response.status} (${duration}ms)`,
          endpoint: url.toString(),
          method: method,
          status: response.status,
          data: {
            request: requestData,
            response: responseData,
            duration: `${duration}ms`,
            headers: Object.fromEntries(response.headers.entries()),
          },
        });
        
        return response;
      } catch (error) {
        const duration = Date.now() - startTime;
        addLog({
          timestamp: new Date().toLocaleTimeString(),
          type: 'api',
          level: 'error',
          message: `${method} ${url} - FAILED (${duration}ms)`,
          endpoint: url.toString(),
          method: method,
          data: { error: error instanceof Error ? error.message : String(error) },
        });
        throw error;
      }
    };

    return () => {
      console.log = originalLog;
      console.error = originalError;
      console.warn = originalWarn;
      window.fetch = originalFetch;
      window.removeEventListener('app-activity' as any, handleActivityEvent);
    };
  }, []);

  const addLog = (log: LogEntry) => {
    setLogs(prev => [log, ...prev].slice(0, 500)); // Keep last 500 logs
  };

  // Auto-scroll to top when new logs arrive (logs are prepended)
  useEffect(() => {
    if (autoScroll && scrollContainerRef.current) {
      scrollContainerRef.current.scrollTop = 0;
    }
  }, [logs, autoScroll]);

  const clearLogs = () => {
    setLogs([]);
    setSelectedLog(null);
  };

  const getLevelColor = (level: string) => {
    switch (level) {
      case 'success': return 'bg-green-500/10 text-green-400 border-green-500/20';
      case 'error': return 'bg-red-500/10 text-red-400 border-red-500/20';
      case 'warning': return 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20';
      default: return 'bg-blue-500/10 text-blue-400 border-blue-500/20';
    }
  };

  const getTypeColor = (type: string) => {
    switch (type) {
      case 'api': return 'bg-purple-500/10 text-purple-400 border-purple-500/20';
      case 'backend': return 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20';
      case 'test': return 'bg-orange-500/10 text-orange-400 border-orange-500/20';
      default: return 'bg-gray-500/10 text-gray-400 border-gray-500/20';
    }
  };

  const apiLogs = logs.filter(log => log.type === 'api');
  const backendLogs = logs.filter(log => log.type === 'backend');

  return (
    <DockPanel
      title="Testing & Logs"
      onClose={onClose}
      onMinimize={onMinimize}
      onMaximize={onMaximize}
    >
      <div className="flex flex-col h-full">
        <div className="p-2 border-b border-border flex items-center gap-2">
          <Badge variant="outline" className="text-xs">
            {logs.length} Total Logs
          </Badge>
          <Badge variant="outline" className={getTypeColor('api')}>
            {apiLogs.length} API
          </Badge>
          <Badge variant="outline" className={getTypeColor('backend')}>
            {backendLogs.length} Backend
          </Badge>
          <Button 
            size="sm" 
            variant={autoScroll ? "default" : "outline"}
            onClick={() => setAutoScroll(!autoScroll)}
            className="ml-auto h-7 text-xs"
          >
            {autoScroll ? "Auto-Scroll: ON" : "Auto-Scroll: OFF"}
          </Button>
          <Button 
            size="sm" 
            variant="outline" 
            onClick={clearLogs}
            className="h-7 text-xs"
          >
            Clear All
          </Button>
        </div>

        <Tabs defaultValue="all" className="flex-1 flex flex-col">
          <TabsList className="w-full justify-start rounded-none border-b border-border bg-transparent p-0">
            <TabsTrigger value="all" className="rounded-none data-[state=active]:border-b-2 data-[state=active]:border-primary">
              All Logs
            </TabsTrigger>
            <TabsTrigger value="api" className="rounded-none data-[state=active]:border-b-2 data-[state=active]:border-primary">
              API Calls
            </TabsTrigger>
            <TabsTrigger value="backend" className="rounded-none data-[state=active]:border-b-2 data-[state=active]:border-primary">
              Backend Logs
            </TabsTrigger>
            <TabsTrigger value="details" className="rounded-none data-[state=active]:border-b-2 data-[state=active]:border-primary">
              Details
            </TabsTrigger>
          </TabsList>

          <TabsContent value="all" className="flex-1 m-0">
            <div className="h-full overflow-auto" ref={scrollContainerRef}>
              <div className="p-2 space-y-1">
                {logs.map((log, index) => (
                  <div
                    key={index}
                    onClick={() => setSelectedLog(log)}
                    className={`p-2 rounded text-xs font-mono cursor-pointer transition-colors ${
                      selectedLog === log ? 'bg-accent' : 'hover:bg-accent/50'
                    }`}
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-muted-foreground">{log.timestamp}</span>
                      <Badge className={`${getTypeColor(log.type)} text-xs px-1.5 py-0`}>
                        {log.type.toUpperCase()}
                      </Badge>
                      <Badge className={`${getLevelColor(log.level)} text-xs px-1.5 py-0`}>
                        {log.level.toUpperCase()}
                      </Badge>
                      {log.method && (
                        <Badge variant="outline" className="text-xs px-1.5 py-0">
                          {log.method}
                        </Badge>
                      )}
                      {log.status && (
                        <Badge variant="outline" className="text-xs px-1.5 py-0">
                          {log.status}
                        </Badge>
                      )}
                    </div>
                    <div className="text-foreground/80 line-clamp-2">{log.message}</div>
                  </div>
                ))}
                {logs.length === 0 && (
                  <div className="text-center text-muted-foreground py-8">
                    No logs yet. Interact with the application to see logs here.
                  </div>
                )}
              </div>
            </div>
          </TabsContent>

          <TabsContent value="api" className="flex-1 m-0">
            <ScrollArea className="h-full">
              <div className="p-2 space-y-1">
                {apiLogs.map((log, index) => (
                  <div
                    key={index}
                    onClick={() => setSelectedLog(log)}
                    className={`p-2 rounded text-xs font-mono cursor-pointer transition-colors ${
                      selectedLog === log ? 'bg-accent' : 'hover:bg-accent/50'
                    }`}
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-muted-foreground">{log.timestamp}</span>
                      <Badge className={`${getLevelColor(log.level)} text-xs px-1.5 py-0`}>
                        {log.level.toUpperCase()}
                      </Badge>
                      <Badge variant="outline" className="text-xs px-1.5 py-0">
                        {log.method}
                      </Badge>
                      <Badge variant="outline" className="text-xs px-1.5 py-0">
                        {log.status}
                      </Badge>
                    </div>
                    <div className="text-foreground/80">{log.endpoint}</div>
                  </div>
                ))}
                {apiLogs.length === 0 && (
                  <div className="text-center text-muted-foreground py-8">
                    No API calls logged yet.
                  </div>
                )}
              </div>
            </ScrollArea>
          </TabsContent>

          <TabsContent value="backend" className="flex-1 m-0">
            <ScrollArea className="h-full">
              <div className="p-2 space-y-1">
                {backendLogs.map((log, index) => (
                  <div
                    key={index}
                    onClick={() => setSelectedLog(log)}
                    className={`p-2 rounded text-xs font-mono cursor-pointer transition-colors ${
                      selectedLog === log ? 'bg-accent' : 'hover:bg-accent/50'
                    }`}
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-muted-foreground">{log.timestamp}</span>
                      <Badge className={`${getLevelColor(log.level)} text-xs px-1.5 py-0`}>
                        {log.level.toUpperCase()}
                      </Badge>
                    </div>
                    <div className="text-foreground/80 whitespace-pre-wrap">{log.message}</div>
                  </div>
                ))}
                {backendLogs.length === 0 && (
                  <div className="text-center text-muted-foreground py-8">
                    No backend logs yet.
                  </div>
                )}
              </div>
            </ScrollArea>
          </TabsContent>

          <TabsContent value="details" className="flex-1 m-0">
            <ScrollArea className="h-full">
              <div className="p-3">
                {selectedLog ? (
                  <div className="space-y-3">
                    <div>
                      <h3 className="text-sm font-semibold mb-2">Log Details</h3>
                      <div className="space-y-1 text-xs">
                        <div className="flex gap-2">
                          <span className="text-muted-foreground w-20">Time:</span>
                          <span>{selectedLog.timestamp}</span>
                        </div>
                        <div className="flex gap-2">
                          <span className="text-muted-foreground w-20">Type:</span>
                          <Badge className={getTypeColor(selectedLog.type)}>
                            {selectedLog.type.toUpperCase()}
                          </Badge>
                        </div>
                        <div className="flex gap-2">
                          <span className="text-muted-foreground w-20">Level:</span>
                          <Badge className={getLevelColor(selectedLog.level)}>
                            {selectedLog.level.toUpperCase()}
                          </Badge>
                        </div>
                        {selectedLog.endpoint && (
                          <div className="flex gap-2">
                            <span className="text-muted-foreground w-20">Endpoint:</span>
                            <span className="font-mono">{selectedLog.endpoint}</span>
                          </div>
                        )}
                        {selectedLog.method && (
                          <div className="flex gap-2">
                            <span className="text-muted-foreground w-20">Method:</span>
                            <span>{selectedLog.method}</span>
                          </div>
                        )}
                        {selectedLog.status && (
                          <div className="flex gap-2">
                            <span className="text-muted-foreground w-20">Status:</span>
                            <span>{selectedLog.status}</span>
                          </div>
                        )}
                      </div>
                    </div>

                    <div>
                      <h3 className="text-sm font-semibold mb-2">Message</h3>
                      <div className="p-2 bg-muted rounded text-xs font-mono whitespace-pre-wrap">
                        {selectedLog.message}
                      </div>
                    </div>

                    {selectedLog.data && (
                      <div>
                        <h3 className="text-sm font-semibold mb-2">Data</h3>
                        <ScrollArea className="h-64">
                          <pre className="p-2 bg-muted rounded text-xs font-mono overflow-x-auto">
                            {JSON.stringify(selectedLog.data, null, 2)}
                          </pre>
                        </ScrollArea>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="text-center text-muted-foreground py-8">
                    Select a log entry to view details
                  </div>
                )}
              </div>
            </ScrollArea>
          </TabsContent>
        </Tabs>
      </div>
    </DockPanel>
  );
}
