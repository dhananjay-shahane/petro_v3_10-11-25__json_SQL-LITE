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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Layout, Save, Sparkles, Info, Plus, RefreshCw } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface SaveLayoutDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSave: (layoutName: string) => void;
  existingLayouts?: string[];
  currentLayoutName?: string;
}

export default function SaveLayoutDialog({
  open,
  onOpenChange,
  onSave,
  existingLayouts = [],
  currentLayoutName = "default",
}: SaveLayoutDialogProps) {
  const [saveMode, setSaveMode] = useState<"new" | "existing">("new");
  const [layoutName, setLayoutName] = useState("");
  const [selectedExisting, setSelectedExisting] = useState("");

  useEffect(() => {
    if (open) {
      setSaveMode(existingLayouts.length > 0 ? "existing" : "new");
      setLayoutName("");
      // Pre-select current layout if it exists in the list
      if (existingLayouts.includes(currentLayoutName)) {
        setSelectedExisting(currentLayoutName);
      } else {
        setSelectedExisting("");
      }
    }
  }, [open, existingLayouts, currentLayoutName]);

  const handleSave = () => {
    const nameToSave = saveMode === "existing" ? selectedExisting : layoutName.trim();
    if (nameToSave) {
      onSave(nameToSave);
      setLayoutName("");
      setSelectedExisting("");
      onOpenChange(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && saveMode === "new" && layoutName.trim()) {
      handleSave();
    }
  };

  const suggestedNames = [
    "Analysis View",
    "Plotting Workspace",
    "Data Review",
    "Multi-Well View",
  ];

  const canSave = saveMode === "new" ? layoutName.trim() !== "" : selectedExisting !== "";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[540px]">
        <DialogHeader>
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-primary/10 rounded-lg">
              <Save className="h-5 w-5 text-primary" />
            </div>
            <div>
              <DialogTitle className="text-xl">Save Workspace Layout</DialogTitle>
              <DialogDescription className="mt-1">
                Preserve your current window arrangement and panel configuration
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {/* What gets saved info */}
          <Alert className="border-blue-200 bg-blue-50/50 dark:bg-blue-950/20 dark:border-blue-900">
            <Info className="h-4 w-4 text-blue-600 dark:text-blue-400" />
            <AlertDescription className="text-sm text-blue-900 dark:text-blue-100">
              <strong>What's saved:</strong> Window positions, panel visibility, and window link states
            </AlertDescription>
          </Alert>

          {/* Save mode selection */}
          {existingLayouts.length > 0 && (
            <div className="space-y-2">
              <Label className="text-sm font-medium">Choose an option:</Label>
              <div className="grid grid-cols-2 gap-2">
                <Button
                  variant={saveMode === "existing" ? "default" : "outline"}
                  size="sm"
                  onClick={() => setSaveMode("existing")}
                  className="justify-start gap-2"
                >
                  <RefreshCw className="h-4 w-4" />
                  Update Existing
                </Button>
                <Button
                  variant={saveMode === "new" ? "default" : "outline"}
                  size="sm"
                  onClick={() => setSaveMode("new")}
                  className="justify-start gap-2"
                >
                  <Plus className="h-4 w-4" />
                  Create New
                </Button>
              </div>
            </div>
          )}

          {/* Existing layout selection */}
          {saveMode === "existing" && existingLayouts.length > 0 && (
            <div className="space-y-2">
              <Label htmlFor="existing-layout" className="text-sm font-medium flex items-center gap-2">
                <Layout className="h-4 w-4" />
                Select Layout to Update
              </Label>
              <Select value={selectedExisting} onValueChange={setSelectedExisting}>
                <SelectTrigger className="h-11">
                  <SelectValue placeholder="Choose a layout..." />
                </SelectTrigger>
                <SelectContent>
                  {existingLayouts.map((layout) => (
                    <SelectItem key={layout} value={layout}>
                      {layout}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {selectedExisting && (
                <p className="text-sm text-amber-600 dark:text-amber-400 flex items-center gap-1.5">
                  <Info className="h-3.5 w-3.5" />
                  This will overwrite the "{selectedExisting}" layout
                </p>
              )}
            </div>
          )}

          {/* New layout name input */}
          {saveMode === "new" && (
            <>
              <div className="space-y-2">
                <Label htmlFor="layoutName" className="text-sm font-medium flex items-center gap-2">
                  <Layout className="h-4 w-4" />
                  New Layout Name
                </Label>
                <Input
                  id="layoutName"
                  value={layoutName}
                  onChange={(e) => setLayoutName(e.target.value)}
                  onKeyPress={handleKeyPress}
                  placeholder="Enter a descriptive name..."
                  className="h-11 text-base"
                  autoFocus
                />
              </div>

              {/* Suggested names */}
              <div className="space-y-2">
                <Label className="text-xs text-muted-foreground flex items-center gap-1.5">
                  <Sparkles className="h-3 w-3" />
                  Quick suggestions:
                </Label>
                <div className="flex flex-wrap gap-2">
                  {suggestedNames.map((name) => (
                    <Button
                      key={name}
                      variant="outline"
                      size="sm"
                      className="h-7 text-xs"
                      onClick={() => setLayoutName(name)}
                      disabled={existingLayouts.includes(name)}
                    >
                      {name}
                      {existingLayouts.includes(name) && " (exists)"}
                    </Button>
                  ))}
                </div>
              </div>
            </>
          )}

          {/* Existing layouts count */}
          {existingLayouts.length > 0 && (
            <p className="text-xs text-muted-foreground">
              You have {existingLayouts.length} saved layout{existingLayouts.length !== 1 ? 's' : ''}
            </p>
          )}
        </div>

        <DialogFooter className="gap-2">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button 
            onClick={handleSave} 
            disabled={!canSave}
            className="gap-2"
          >
            <Save className="h-4 w-4" />
            {saveMode === "existing" ? "Update Layout" : "Save New Layout"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
