import { useState, useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Search } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

interface LogSelectDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  availableLogs: string[];
  selectedLog?: string;
  onSelectLog: (log: string) => void;
  wellName?: string;
}

export default function LogSelectDialog({
  open,
  onOpenChange,
  availableLogs,
  selectedLog,
  onSelectLog,
  wellName,
}: LogSelectDialogProps) {
  const [filterText, setFilterText] = useState("");
  const [wildcardFilter, setWildcardFilter] = useState("");
  const [selectedLogs, setSelectedLogs] = useState<Set<string>>(new Set());

  // Filter logs based on wildcard and search text
  const filteredLogs = availableLogs.filter((log) => {
    const matchesWildcard = wildcardFilter
      ? log.toUpperCase().includes(wildcardFilter.toUpperCase())
      : true;
    const matchesFilter = filterText
      ? log.toUpperCase().includes(filterText.toUpperCase())
      : true;
    return matchesWildcard && matchesFilter;
  });

  const handleSelect = () => {
    if (selectedLogs.size > 0) {
      // Select the first checked log
      const firstSelected = Array.from(selectedLogs)[0];
      onSelectLog(firstSelected);
      onOpenChange(false);
    }
  };

  const handleCancel = () => {
    setSelectedLogs(new Set());
    onOpenChange(false);
  };

  const handleToggleLog = (log: string) => {
    setSelectedLogs((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(log)) {
        newSet.delete(log);
      } else {
        newSet.add(log);
      }
      return newSet;
    });
  };

  const handleSelectAll = () => {
    if (selectedLogs.size === filteredLogs.length) {
      setSelectedLogs(new Set());
    } else {
      setSelectedLogs(new Set(filteredLogs));
    }
  };

  useEffect(() => {
    if (open) {
      setSelectedLogs(selectedLog ? new Set([selectedLog]) : new Set());
    }
  }, [open, selectedLog]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl max-h-[90vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>Log Select - {wellName || "Select logs"}</DialogTitle>
        </DialogHeader>

        <div className="flex-1 overflow-hidden flex flex-col gap-3 py-2">
          {/* Filter Section */}
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Label className="text-sm font-medium w-20">Filter:</Label>
              <div className="relative flex-1">
                <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search logs..."
                  value={filterText}
                  onChange={(e) => setFilterText(e.target.value)}
                  className="pl-8 h-9"
                />
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setFilterText("")}
                className="h-9"
              >
                Clear
              </Button>
            </div>

            <div className="flex items-center gap-2">
              <Label className="text-sm font-medium w-20">Wildcard:</Label>
              <Input
                value={wildcardFilter}
                onChange={(e) => setWildcardFilter(e.target.value)}
                placeholder="e.g., TOPS, GR, DEPTH (leave empty for all)"
                className="flex-1 h-9"
              />
              <Button
                variant="outline"
                size="sm"
                onClick={handleSelectAll}
                className="h-9"
              >
                {selectedLogs.size === filteredLogs.length ? "Deselect All" : "Select All"}
              </Button>
            </div>
          </div>

          {/* Logs Table */}
          <div className="flex-1 border rounded-md overflow-hidden flex flex-col bg-background">
            <ScrollArea className="flex-1">
              <Table>
                <TableHeader className="sticky top-0 bg-muted">
                  <TableRow>
                    <TableHead className="w-12">
                      <Checkbox
                        checked={selectedLogs.size === filteredLogs.length && filteredLogs.length > 0}
                        onCheckedChange={handleSelectAll}
                      />
                    </TableHead>
                    <TableHead>Name</TableHead>
                    <TableHead className="w-32">Type</TableHead>
                    <TableHead className="w-32">Dataset</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredLogs.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={4} className="text-center py-8 text-muted-foreground">
                        No logs found matching the filter
                      </TableCell>
                    </TableRow>
                  ) : (
                    filteredLogs.map((log) => {
                      const isSelected = selectedLogs.has(log);
                      const logType = log.toUpperCase().includes("TOPS") ? "Tops" : "Log";
                      
                      return (
                        <TableRow
                          key={log}
                          className={`cursor-pointer ${isSelected ? "bg-primary/10" : "hover:bg-muted/50"}`}
                          onClick={() => handleToggleLog(log)}
                        >
                          <TableCell>
                            <Checkbox
                              checked={isSelected}
                              onCheckedChange={() => handleToggleLog(log)}
                              onClick={(e) => e.stopPropagation()}
                            />
                          </TableCell>
                          <TableCell className="font-mono text-sm">{log}</TableCell>
                          <TableCell className="text-sm text-muted-foreground">{logType}</TableCell>
                          <TableCell className="text-sm text-muted-foreground">Default</TableCell>
                        </TableRow>
                      );
                    })
                  )}
                </TableBody>
              </Table>
            </ScrollArea>
          </div>

          {/* Summary */}
          <div className="text-sm text-muted-foreground">
            {selectedLogs.size > 0 && (
              <span>
                {selectedLogs.size} log{selectedLogs.size !== 1 ? "s" : ""} selected: {Array.from(selectedLogs).join(", ")}
              </span>
            )}
            {selectedLogs.size === 0 && <span>No logs selected</span>}
          </div>
        </div>

        <DialogFooter className="gap-2">
          <Button variant="outline" onClick={handleCancel}>
            Cancel
          </Button>
          <Button onClick={handleSelect} disabled={selectedLogs.size === 0}>
            OK
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
