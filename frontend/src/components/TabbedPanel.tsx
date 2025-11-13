import { useState, ReactNode } from "react";
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";

interface Tab {
  id: string;
  label: string;
  content: ReactNode;
  closeable?: boolean;
}

interface TabbedPanelProps {
  tabs: Tab[];
  defaultTab?: string;
  onTabClose?: (tabId: string) => void;
}

export default function TabbedPanel({
  tabs,
  defaultTab,
  onTabClose,
}: TabbedPanelProps) {
  const [activeTab, setActiveTab] = useState(defaultTab || tabs[0]?.id);

  const activeTabContent = tabs.find((tab) => tab.id === activeTab)?.content;

  return (
    <div className="flex flex-col h-full">
      <div className="flex h-9 bg-card border-b border-card-border">
        {tabs.map((tab) => (
          <div
            key={tab.id}
            className={`group flex items-center gap-2 px-3 py-1.5 text-sm font-medium cursor-pointer border-r border-card-border transition-colors ${
              activeTab === tab.id
                ? "bg-background border-t-2 border-t-primary text-foreground"
                : "text-muted-foreground hover-elevate"
            }`}
            onClick={() => setActiveTab(tab.id)}
            data-testid={`tab-${tab.id}`}
          >
            <span className="truncate">{tab.label}</span>
            {tab.closeable && activeTab === tab.id && (
              <Button
                size="icon"
                variant="ghost"
                className="h-4 w-4 opacity-0 group-hover:opacity-100 transition-opacity"
                onClick={(e) => {
                  e.stopPropagation();
                  onTabClose?.(tab.id);
                }}
                data-testid={`button-close-tab-${tab.id}`}
              >
                <X className="w-3 h-3" />
              </Button>
            )}
          </div>
        ))}
      </div>
      <div className="flex-1 overflow-auto">{activeTabContent}</div>
    </div>
  );
}
