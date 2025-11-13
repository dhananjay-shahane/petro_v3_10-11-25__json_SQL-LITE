import { useState, useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Settings2 } from "lucide-react";
import { Slider } from "@/components/ui/slider";
import { useToast } from "@/hooks/use-toast";
import axios from "axios";

interface FontSizeSettings {
  dataBrowser: number;
  wellList: number;
  feedbackLog: number;
  zonationList: number;
  cliTerminal: number;
}

interface SettingsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
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

export default function SettingsDialog({
  open,
  onOpenChange,
}: SettingsDialogProps) {
  const { toast } = useToast();
  const [fontSizes, setFontSizes] = useState<FontSizeSettings>(DEFAULT_FONT_SIZES);
  const [originalFontSizes, setOriginalFontSizes] = useState<FontSizeSettings>(DEFAULT_FONT_SIZES);
  const [isLoading, setIsLoading] = useState(false);

  // Load settings on mount and apply them
  useEffect(() => {
    loadSettings();
  }, []);

  // Load settings when dialog opens
  useEffect(() => {
    if (open) {
      loadSettings();
    }
  }, [open]);

  const loadSettings = async () => {
    try {
      const response = await axios.get("/api/settings/font-sizes");
      if (response.data.fontSizes) {
        setFontSizes(response.data.fontSizes);
        setOriginalFontSizes(response.data.fontSizes);
        // Apply the loaded settings immediately
        applyFontSizes(response.data.fontSizes);
      }
    } catch (error) {
      console.error("Error loading font size settings:", error);
      // Use defaults if loading fails
      setFontSizes(DEFAULT_FONT_SIZES);
      setOriginalFontSizes(DEFAULT_FONT_SIZES);
      applyFontSizes(DEFAULT_FONT_SIZES);
    }
  };

  const handleFontSizeChange = (key: keyof FontSizeSettings, value: number) => {
    setFontSizes((prev) => ({
      ...prev,
      [key]: value,
    }));
  };

  const handleApply = async () => {
    setIsLoading(true);
    try {
      await axios.post("/api/settings/font-sizes", {
        fontSizes,
      });

      // Apply font sizes to the document
      applyFontSizes(fontSizes);

      setOriginalFontSizes(fontSizes);

      toast({
        title: "Settings Saved",
        description: "Font size settings have been applied successfully.",
      });

      onOpenChange(false);
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

  const handleCancel = () => {
    setFontSizes(originalFontSizes);
    onOpenChange(false);
  };

  const handleReset = () => {
    setFontSizes(DEFAULT_FONT_SIZES);
  };

  // Helper function to apply font sizes dynamically
  const applyFontSizes = (sizes: FontSizeSettings) => {
    const root = document.documentElement;
    root.style.setProperty("--font-size-data-browser", `${sizes.dataBrowser}px`);
    root.style.setProperty("--font-size-well-list", `${sizes.wellList}px`);
    root.style.setProperty("--font-size-feedback-log", `${sizes.feedbackLog}px`);
    root.style.setProperty("--font-size-zonation-list", `${sizes.zonationList}px`);
    root.style.setProperty("--font-size-cli-terminal", `${sizes.cliTerminal}px`);
  };

  // Apply preview font sizes
  useEffect(() => {
    if (open) {
      applyFontSizes(fontSizes);
    }
  }, [fontSizes, open]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[600px] sm:min-w-[500px] min-h-[400px] max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-primary/10 rounded-lg">
              <Settings2 className="h-5 w-5 text-primary" />
            </div>
            <div>
              <DialogTitle className="text-xl">Settings</DialogTitle>
              <DialogDescription className="mt-1">
                Adjust font sizes for different panels
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {/* Font Size Section */}
          <div className="space-y-4">
            <div className="pb-2 border-b">
              <h3 className="text-base font-semibold">Adjust Font Size</h3>
              <p className="text-sm text-muted-foreground mt-1">
                Customize font sizes for different panels
              </p>
            </div>

            <div className="space-y-6">
              {FONT_SIZE_OPTIONS.map((option) => (
                <div key={option.key} className="space-y-3">
                  <div className="flex items-center justify-between">
                    <Label htmlFor={option.key} className="text-sm font-medium">
                      {option.label}
                    </Label>
                    <span className="text-sm font-mono text-muted-foreground">
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

                  {/* Preview */}
                  <div
                    className="p-3 border rounded-md bg-muted/50"
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

        <DialogFooter className="gap-2 sm:gap-0">
          <Button variant="outline" onClick={handleReset} className="sm:mr-auto">
            Reset to Defaults
          </Button>
          <Button variant="outline" onClick={handleCancel}>
            Cancel
          </Button>
          <Button onClick={handleApply} disabled={isLoading} className="gap-2">
            {isLoading ? "Saving..." : "Apply"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
