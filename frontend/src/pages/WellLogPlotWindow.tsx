import { useState, useEffect } from "react";
import { useLocation } from "wouter";
import WellLogPlot from "@/components/WellLogPlot";

interface WellData {
  id?: string;
  name: string;
  path?: string;
  projectPath?: string;
}

export default function WellLogPlotWindow() {
  const [location] = useLocation();
  
  const params = new URLSearchParams(window.location.search);
  const initialWellId = params.get('wellId');
  const initialWellName = params.get('wellName');
  const initialProjectPath = params.get('projectPath');

  const initialWell = initialWellId && initialWellName ? {
    id: initialWellId,
    name: initialWellName,
    projectPath: initialProjectPath || undefined
  } : null;

  // Generate unique window ID
  const [windowId] = useState<string>(() => {
    return `LogPlot-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
  });

  const [selectedWell, setSelectedWell] = useState<WellData | null>(initialWell);
  const [isLinked, setIsLinked] = useState<boolean>(() => {
    const saved = localStorage.getItem('popupWindowLinked');
    return saved !== 'false';
  });

  useEffect(() => {
    localStorage.setItem('popupWindowLinked', String(isLinked));
  }, [isLinked]);

  // Focus notification
  useEffect(() => {
    const handleFocus = () => {
      const wellName = selectedWell?.name || 'No well';
      const message = `LogPlot Window [${windowId}] focused: ${wellName}`;
      
      // Send to parent window's feedback panel if available
      if (window.opener && !window.opener.closed) {
        try {
          window.opener.postMessage({
            type: 'WINDOW_FOCUS',
            windowType: 'LogPlot',
            windowId: windowId,
            wellName: wellName,
            message: message
          }, '*');
        } catch (e) {
          console.log('[WellLogPlotWindow] Could not notify parent window:', e);
        }
      }
      
      console.log(`[WellLogPlotWindow] ${message}`);
    };

    window.addEventListener('focus', handleFocus);
    
    // Send initial focus notification
    handleFocus();

    return () => {
      window.removeEventListener('focus', handleFocus);
    };
  }, [selectedWell?.name, windowId]);

  useEffect(() => {
    if (!isLinked) return;

    const channel = new BroadcastChannel('well-selection-channel');
    
    const handleMessage = (event: MessageEvent) => {
      if (event.data.type === 'WELL_SELECTED' && isLinked) {
        const newWell = event.data.well;
        console.log('[WellLogPlotWindow] Received well selection update:', newWell);
        setSelectedWell(newWell);
      }
    };

    channel.addEventListener('message', handleMessage);

    return () => {
      channel.removeEventListener('message', handleMessage);
      channel.close();
    };
  }, [isLinked]);

  const toggleLink = () => {
    setIsLinked(prev => !prev);
  };

  const currentProjectPath = selectedWell?.projectPath || initialProjectPath || undefined;

  return (
    <div className="h-screen w-full bg-background overflow-hidden">
      <div className="h-full flex flex-col">
        <div className="flex items-center justify-between px-2 sm:px-4 py-2 border-b border-border bg-card shrink-0">
          <div className="flex-1 min-w-0">
            <h1 className="text-sm sm:text-lg font-semibold text-foreground truncate">
              Well Log Plot{selectedWell?.name ? `: ${selectedWell.name}` : ''}
            </h1>
            <p className="text-xs text-muted-foreground truncate">ID: {windowId}</p>
          </div>
          <button
            onClick={() => window.close()}
            className="px-2 sm:px-3 py-1 text-xs sm:text-sm rounded hover:bg-accent text-muted-foreground hover:text-foreground shrink-0"
          >
            Close Window
          </button>
        </div>
        <div className="flex-1 overflow-auto p-2 sm:p-4">
          <WellLogPlot 
            selectedWell={selectedWell}
            projectPath={currentProjectPath}
            isLocked={isLinked}
            onToggleLock={toggleLink}
          />
        </div>
      </div>
    </div>
  );
}
