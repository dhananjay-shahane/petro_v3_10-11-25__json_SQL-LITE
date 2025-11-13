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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface Dataset {
  name: string;
  type: string;
}

interface CrossPlotControlDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  availableLogs: Dataset[];
  xLog: string;
  yLog: string;
  onApply: (xLog: string, yLog: string) => void;
}

export default function CrossPlotControlDialog({
  open,
  onOpenChange,
  availableLogs,
  xLog,
  yLog,
  onApply,
}: CrossPlotControlDialogProps) {
  const [selectedXLog, setSelectedXLog] = useState(xLog);
  const [selectedYLog, setSelectedYLog] = useState(yLog);

  useEffect(() => {
    if (open) {
      setSelectedXLog(xLog);
      setSelectedYLog(yLog);
    }
  }, [open, xLog, yLog]);

  const handleApply = () => {
    if (selectedXLog && selectedYLog) {
      onApply(selectedXLog, selectedYLog);
      onOpenChange(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-primary/10 rounded-lg">
              <Settings2 className="h-5 w-5 text-primary" />
            </div>
            <div>
              <DialogTitle className="text-xl">Control Data</DialogTitle>
              <DialogDescription className="mt-1">
                Select logs for X and Y axes
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label htmlFor="x-axis" className="text-sm font-medium">
              X-Axis Log
            </Label>
            <Select value={selectedXLog} onValueChange={setSelectedXLog}>
              <SelectTrigger className="h-11">
                <SelectValue placeholder="Select X-axis log..." />
              </SelectTrigger>
              <SelectContent>
                {availableLogs.map((log) => (
                  <SelectItem key={log.name} value={log.name}>
                    {log.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="y-axis" className="text-sm font-medium">
              Y-Axis Log
            </Label>
            <Select value={selectedYLog} onValueChange={setSelectedYLog}>
              <SelectTrigger className="h-11">
                <SelectValue placeholder="Select Y-axis log..." />
              </SelectTrigger>
              <SelectContent>
                {availableLogs.map((log) => (
                  <SelectItem key={log.name} value={log.name}>
                    {log.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        <DialogFooter className="gap-2">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            onClick={handleApply}
            disabled={!selectedXLog || !selectedYLog}
            className="gap-2"
          >
            Apply
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
