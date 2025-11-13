import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { useToast } from "@/hooks/use-toast";
import { Settings2, TextCursor, ChevronRight } from "lucide-react";
import axios from "axios";

interface FontSizeSettings {
  dataBrowser: number;
  wellList: number;
  feedbackLog: number;
  zonationList: number;
  cliTerminal: number;
}

const DEFAULT_FONT_SIZES: FontSizeSettings = {
  dataBrowser: 14,
  wellList: 14,
  feedbackLog: 13,
  zonationList: 14,
  cliTerminal: 13,
};

const FONT_SIZE_OPTIONS = [
  { label: "Data Browser", key: "dataBrowser" as keyof FontSizeSettings, min: 10, max: 20 },
  { label: "Well List", key: "wellList" as keyof FontSizeSettings, min: 10, max: 20 },
  { label: "Feedback Log", key: "feedbackLog" as keyof FontSizeSettings, min: 10, max: 20 },
  { label: "Zonation List", key: "zonationList" as keyof FontSizeSettings, min: 10, max: 20 },
  { label: "CLI Terminal", key: "cliTerminal" as keyof FontSizeSettings, min: 10, max: 20 },
];

const MENU_ITEMS = [
  { id: "font-size", label: "Font Size", icon: TextCursor },
];

export default function SettingsPanel({
  onClose,
  onMinimize,
  onMaximize,
  projectPath,
}: {
  onClose?: () => void;
  onMinimize?: () => void;
  onMaximize?: () => void;
  projectPath?: string;
}) {
  const { toast } = useToast();
  const [activeSection, setActiveSection] = useState("font-size");
  const [fontSizes, setFontSizes] = useState<FontSizeSettings>(DEFAULT_FONT_SIZES);
  const [originalFontSizes, setOriginalFontSizes] = useState<FontSizeSettings>(DEFAULT_FONT_SIZES);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    loadSettings();
  }, [projectPath]);

  const loadSettings = async () => {
    try {
      const url = projectPath 
        ? `/api/settings/font-sizes?projectPath=${encodeURIComponent(projectPath)}`
        : "/api/settings/font-sizes";
      const response = await axios.get(url);
      if (response.data.fontSizes) {
        console.log("[Settings] Loaded font sizes from server:", response.data.fontSizes);
        setFontSizes(response.data.fontSizes);
        setOriginalFontSizes(response.data.fontSizes);
        applyFontSizes(response.data.fontSizes);
      }
    } catch (error) {
      console.error("Error loading font size settings:", error);
      setFontSizes(DEFAULT_FONT_SIZES);
      setOriginalFontSizes(DEFAULT_FONT_SIZES);
      applyFontSizes(DEFAULT_FONT_SIZES);
    }
  };

  const handleFontSizeChange = (key: keyof FontSizeSettings, value: number) => {
    const newSizes = { ...fontSizes, [key]: value };
    setFontSizes(newSizes);
    applyFontSizes(newSizes);
  };

  const handleApply = async () => {
    setIsLoading(true);
    try {
      await axios.post("/api/settings/font-sizes", {
        fontSizes,
        projectPath,
      });

      setOriginalFontSizes(fontSizes);

      toast({
        title: "Settings Saved",
        description: "Font size settings have been applied successfully.",
      });
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to save font size settings.",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleReset = () => {
    setFontSizes(DEFAULT_FONT_SIZES);
    applyFontSizes(DEFAULT_FONT_SIZES);
  };

  const applyFontSizes = (sizes: FontSizeSettings) => {
    const root = document.documentElement;
    root.style.setProperty("--font-size-data-browser", `${sizes.dataBrowser}px`);
    root.style.setProperty("--font-size-well-list", `${sizes.wellList}px`);
    root.style.setProperty("--font-size-feedback-log", `${sizes.feedbackLog}px`);
    root.style.setProperty("--font-size-zonation-list", `${sizes.zonationList}px`);
    root.style.setProperty("--font-size-cli-terminal", `${sizes.cliTerminal}px`);
  };

  const renderContent = () => {
    switch (activeSection) {
      case "font-size":
        return (
          <div className="flex flex-col h-full">
            <div className="flex-1 overflow-auto p-6">
              <div className="max-w-3xl">
                <div className="mb-6">
                  <h2 className="text-2xl font-semibold mb-2">Font Size</h2>
                  <p className="text-sm text-muted-foreground">
                    Customize font sizes for different panels in the application
                  </p>
                </div>

                <div className="space-y-8">
                  {FONT_SIZE_OPTIONS.map((option) => (
                    <div key={option.key} className="space-y-3">
                      <div className="flex items-center justify-between">
                        <Label htmlFor={option.key} className="text-sm font-medium">
                          {option.label}
                        </Label>
                        <span className="text-sm font-mono text-muted-foreground bg-muted px-3 py-1 rounded-md">
                          {fontSizes[option.key]}px
                        </span>
                      </div>
                      
                      <Slider
                        id={option.key}
                        min={option.min}
                        max={option.max}
                        step={1}
                        value={[fontSizes[option.key]]}
                        onValueChange={(value) => handleFontSizeChange(option.key, value[0])}
                        className="w-full"
                      />

                      <div
                        className="p-4 border rounded-lg bg-muted/30"
                        style={{ fontSize: `${fontSizes[option.key]}px` }}
                      >
                        <p className="text-foreground">
                          Preview: The quick brown fox jumps over the lazy dog
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="border-t bg-card p-4">
              <div className="flex items-center justify-between max-w-3xl">
                <Button variant="outline" onClick={handleReset}>
                  Reset to Defaults
                </Button>
                <Button onClick={handleApply} disabled={isLoading}>
                  {isLoading ? "Saving..." : "Save Changes"}
                </Button>
              </div>
            </div>
          </div>
        );
      default:
        return null;
    }
  };

  return (
    <div className="flex h-full bg-background">
      {/* Sidebar */}
      <div className="w-64 border-r bg-card flex flex-col">
        <div className="p-4 border-b">
          <div className="flex items-center gap-2">
            <Settings2 className="h-5 w-5" />
            <h1 className="text-lg font-semibold">Settings</h1>
          </div>
        </div>

        <div className="flex-1 overflow-auto py-2">
          {MENU_ITEMS.map((item) => {
            const Icon = item.icon;
            const isActive = activeSection === item.id;
            
            return (
              <button
                key={item.id}
                onClick={() => setActiveSection(item.id)}
                className={`w-full flex items-center justify-between px-4 py-3 text-sm transition-colors ${
                  isActive
                    ? "bg-muted text-foreground font-medium border-l-2 border-l-primary"
                    : "text-muted-foreground hover:bg-muted/50 hover:text-foreground"
                }`}
              >
                <div className="flex items-center gap-3">
                  <Icon className="h-4 w-4" />
                  <span>{item.label}</span>
                </div>
                {isActive && <ChevronRight className="h-4 w-4" />}
              </button>
            );
          })}
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col bg-background">
        {renderContent()}
      </div>
    </div>
  );
}
