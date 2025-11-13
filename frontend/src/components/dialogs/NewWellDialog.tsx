import { useState } from "react";
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
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useToast } from "@/hooks/use-toast";
import { Upload } from "lucide-react";

interface NewWellDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projectPath: string;
  onWellCreated?: (well: { id: string; name: string; path: string }) => void;
}

export default function NewWellDialog({ 
  open, 
  onOpenChange, 
  projectPath,
  onWellCreated 
}: NewWellDialogProps) {
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [lasFile, setLasFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [lasPreview, setLasPreview] = useState<any>(null);
  const [setName, setSetName] = useState<string>("");
  const [datasetType, setDatasetType] = useState<string>("CONTINUOUS");
  const { toast } = useToast();

  const handleCsvUpload = async () => {
    if (!csvFile) {
      toast({
        title: "Error",
        description: "Please select a CSV file",
        variant: "destructive",
      });
      return;
    }

    if (!projectPath || projectPath === "No path selected") {
      toast({
        title: "Error",
        description: "No project is currently open. Please open or create a project first.",
        variant: "destructive",
      });
      return;
    }

    setIsUploading(true);

    try {
      const formData = new FormData();
      formData.append("csvFile", csvFile);
      formData.append("projectPath", projectPath);

      const response = await fetch("/api/wells/create-from-csv", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || "Failed to create wells from CSV");
      }

      const result = await response.json();

      toast({
        title: "Success",
        description: `Successfully created ${result.wellsCreated} well(s) from CSV`,
      });

      // Notify parent about the first well created (for backward compatibility)
      if (result.wells && result.wells.length > 0 && onWellCreated) {
        result.wells.forEach((well: any) => {
          onWellCreated({
            id: well.id,
            name: well.name,
            path: well.path,
          });
        });
      }

      setCsvFile(null);
      onOpenChange(false);
    } catch (error: any) {
      const errorMessage = error.message || "Failed to create wells from CSV. Please try again.";
      toast({
        title: "Error",
        description: errorMessage,
        variant: "destructive",
      });
    } finally {
      setIsUploading(false);
    }
  };

  const handleLasUpload = async () => {
    if (!lasFile) {
      toast({
        title: "Error",
        description: "Please select a LAS file",
        variant: "destructive",
      });
      return;
    }

    if (!projectPath || projectPath === "No path selected") {
      toast({
        title: "Error",
        description: "No project is currently open. Please open or create a project first.",
        variant: "destructive",
      });
      return;
    }

    setIsUploading(true);

    try {
      const formData = new FormData();
      formData.append("lasFile", lasFile);
      formData.append("projectPath", projectPath);
      if (setName.trim()) {
        formData.append("setName", setName.trim());
      }
      formData.append("datasetType", datasetType);

      const response = await fetch("/api/wells/create-from-las", {
        method: "POST",
        body: formData,
        // 5 minute timeout for large files (if AbortSignal.timeout is supported)
        signal: AbortSignal.timeout?.(300000)
      });

      const result = await response.json();

      // Display logs in Python Logs panel
      if (result.logs && Array.isArray(result.logs)) {
        result.logs.forEach((log: any) => {
          if ((window as any).addPythonLog) {
            (window as any).addPythonLog(log.message, log.type);
          }
        });
      }

      if (!response.ok) {
        throw new Error(result.error || "Failed to create well from LAS file");
      }

      toast({
        title: "Success",
        description: `Well "${result.well.name}" created successfully from LAS file`,
      });

      if (onWellCreated) {
        onWellCreated({
          id: result.well.id,
          name: result.well.name,
          path: result.filePath,
        });
      }

      setLasFile(null);
      setLasPreview(null);
      setSetName("");
      setDatasetType("CONTINUOUS");
      onOpenChange(false);
    } catch (error: any) {
      const errorMessage = error.message || "Failed to create well from LAS file. Please try again.";
      
      // Log error to Python Logs panel
      if ((window as any).addPythonLog) {
        (window as any).addPythonLog(`❌ Upload failed: ${errorMessage}`, 'error');
      }
      
      toast({
        title: "Error",
        description: errorMessage,
        variant: "destructive",
      });
    } finally {
      setIsUploading(false);
    }
  };

  const handleDialogClose = (open: boolean) => {
    if (!open && !isUploading) {
      setCsvFile(null);
      setLasFile(null);
      setLasPreview(null);
      setSetName("");
      setDatasetType("CONTINUOUS");
    }
    onOpenChange(open);
  };

  const handleCsvFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      if (!file.name.endsWith('.csv')) {
        toast({
          title: "Error",
          description: "Please select a CSV file",
          variant: "destructive",
        });
        return;
      }
      setCsvFile(file);
    }
  };

  const handleLasFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      if (!file.name.endsWith('.las') && !file.name.endsWith('.LAS')) {
        toast({
          title: "Error",
          description: "Please select a LAS file",
          variant: "destructive",
        });
        return;
      }
      
      // Check file size (500 MB limit)
      const MAX_FILE_SIZE = 500 * 1024 * 1024;
      const RECOMMENDED_SIZE = 50 * 1024 * 1024;
      
      if (file.size > MAX_FILE_SIZE) {
        toast({
          title: "File Too Large",
          description: `File size is ${(file.size / (1024 * 1024)).toFixed(2)} MB. Maximum allowed is 500 MB.`,
          variant: "destructive",
        });
        e.target.value = ''; // Clear the file input
        return;
      }
      
      // Warn if file is large but within limits
      if (file.size > RECOMMENDED_SIZE) {
        toast({
          title: "Large File Warning",
          description: `File size is ${(file.size / (1024 * 1024)).toFixed(2)} MB. Processing may take longer. Recommended size is up to 50 MB for optimal performance.`,
          variant: "default",
        });
      }
      
      setLasFile(file);
      
      // Preview LAS file content
      try {
        const content = await file.text();
        const preview = await fetch('/api/wells/preview-las', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ lasContent: content, filename: file.name })
        });
        
        if (preview.ok) {
          const data = await preview.json();
          setLasPreview(data);
        }
      } catch (error) {
        console.error('Error previewing LAS file:', error);
      }
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleDialogClose}>
      <DialogContent className="sm:max-w-[600px]">
        <DialogHeader>
          <DialogTitle>Create New Well</DialogTitle>
          <DialogDescription>
            Upload a LAS file or CSV file with well data to create wells in your project.
          </DialogDescription>
        </DialogHeader>
        
        <Tabs defaultValue="las" className="w-full">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="las">Upload LAS</TabsTrigger>
            <TabsTrigger value="csv">Upload CSV</TabsTrigger>
          </TabsList>
          
          <TabsContent value="las" className="space-y-4 pt-4">
            <div className="grid gap-2">
              <Label htmlFor="las-file">LAS File</Label>
              <div className="flex items-center gap-2">
                <Input
                  id="las-file"
                  type="file"
                  accept=".las,.LAS"
                  onChange={handleLasFileChange}
                  disabled={isUploading}
                  className="cursor-pointer"
                />
              </div>
              {lasFile && (
                <p className="text-sm text-muted-foreground">
                  Selected: {lasFile.name} ({(lasFile.size / 1024).toFixed(2)} KB)
                </p>
              )}
            </div>

            <div className="grid gap-4">
              <div className="grid gap-2">
                <Label htmlFor="set-name">Dataset Name (Optional)</Label>
                <Input
                  id="set-name"
                  type="text"
                  placeholder="e.g., MAIN, SPLICE, etc. (leave blank to use SET from LAS file)"
                  value={setName}
                  onChange={(e) => setSetName(e.target.value)}
                  disabled={isUploading}
                />
                <p className="text-xs text-muted-foreground">
                  Custom dataset name. If blank, will use SET parameter from LAS file or default to "MAIN"
                </p>
              </div>

              <div className="grid gap-2">
                <Label htmlFor="dataset-type">Dataset Type</Label>
                <select
                  id="dataset-type"
                  value={datasetType}
                  onChange={(e) => setDatasetType(e.target.value)}
                  disabled={isUploading}
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <option value="CONTINUOUS">Continuous (evenly spaced depth intervals)</option>
                  <option value="POINT">Point (variable interval sampling)</option>
                </select>
                <p className="text-xs text-muted-foreground">
                  Select "Point" for datasets where the index log is sampled at variable intervals
                </p>
              </div>
            </div>

            {lasPreview ? (
              <div className="bg-muted p-4 rounded-lg text-sm space-y-2">
                <p className="font-medium text-green-600">✓ LAS File Parsed Successfully</p>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div>
                    <span className="font-medium">Well Name:</span> {lasPreview.wellName || 'N/A'}
                  </div>
                  <div>
                    <span className="font-medium">Company:</span> {lasPreview.company || 'N/A'}
                  </div>
                  <div>
                    <span className="font-medium">Location:</span> {lasPreview.location || 'N/A'}
                  </div>
                  <div>
                    <span className="font-medium">Depth Range:</span> {lasPreview.startDepth || 'N/A'} - {lasPreview.stopDepth || 'N/A'}
                  </div>
                  <div className="col-span-2">
                    <span className="font-medium">Curves ({lasPreview.curveNames?.length || 0}):</span> {lasPreview.curveNames?.join(', ') || 'None'}
                  </div>
                  <div className="col-span-2">
                    <span className="font-medium">Data Points:</span> {lasPreview.dataPoints || 0} rows
                  </div>
                </div>
              </div>
            ) : (
              <div className="bg-muted p-4 rounded-lg text-sm">
                <p className="font-medium mb-2">LAS File Upload:</p>
                <p className="text-muted-foreground mb-2">Upload a LAS (Log ASCII Standard) file to create a well:</p>
                <ul className="list-disc list-inside text-muted-foreground space-y-1">
                  <li>The well name will be extracted from the LAS file header</li>
                  <li>Well log data and curves will be parsed automatically</li>
                  <li>Data will be saved in JSON format in the 10-WELLS folder</li>
                  <li>LAS file will be copied to 02-INPUT_LAS_FOLDER</li>
                </ul>
                <div className="mt-3 pt-3 border-t border-border">
                  <p className="font-semibold text-foreground">📊 File Size Limits:</p>
                  <p className="text-muted-foreground mt-1">• Recommended: Up to 50 MB for optimal performance</p>
                  <p className="text-muted-foreground">• Maximum: 500 MB (larger files may take longer to process)</p>
                </div>
              </div>
            )}

            <div className="text-sm text-muted-foreground">
              <p className="font-medium">Current Project:</p>
              <p className="font-mono text-xs mt-1">{projectPath || "No project selected"}</p>
              {projectPath && projectPath !== "No path selected" && (
                <p className="font-mono text-xs mt-1">
                  Well will be saved to: {projectPath}/10-WELLS/[well-name].ptrc
                </p>
              )}
            </div>

            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => onOpenChange(false)}
                disabled={isUploading}
              >
                Cancel
              </Button>
              <Button onClick={handleLasUpload} disabled={isUploading || !lasFile}>
                <Upload className="w-4 h-4 mr-2" />
                {isUploading ? "Uploading..." : "Upload LAS File"}
              </Button>
            </DialogFooter>
          </TabsContent>
          
          <TabsContent value="csv" className="space-y-4 pt-4">
            <div className="grid gap-2">
              <Label htmlFor="csv-file">CSV File</Label>
              <div className="flex items-center gap-2">
                <Input
                  id="csv-file"
                  type="file"
                  accept=".csv"
                  onChange={handleCsvFileChange}
                  disabled={isUploading}
                  className="cursor-pointer"
                />
              </div>
              {csvFile && (
                <p className="text-sm text-muted-foreground">
                  Selected: {csvFile.name} ({(csvFile.size / 1024).toFixed(2)} KB)
                </p>
              )}
            </div>

            <div className="bg-muted p-4 rounded-lg text-sm">
              <p className="font-medium mb-2">CSV Format:</p>
              <p className="text-muted-foreground mb-2">The CSV file should contain the following columns:</p>
              <ul className="list-disc list-inside text-muted-foreground space-y-1">
                <li><code>well_name</code> - Name of the well (required)</li>
                <li><code>description</code> - Well description (optional)</li>
                <li><code>las_file</code> - LAS filename in 02-INPUT_LAS_FOLDER (optional)</li>
                <li><code>depth_min</code> - Minimum depth (optional)</li>
                <li><code>depth_max</code> - Maximum depth (optional)</li>
                <li><code>location</code> - Well location (optional)</li>
              </ul>
            </div>

            <div className="text-sm text-muted-foreground">
              <p className="font-medium">Current Project:</p>
              <p className="font-mono text-xs mt-1">{projectPath || "No project selected"}</p>
              {projectPath && projectPath !== "No path selected" && (
                <p className="font-mono text-xs mt-1">
                  Wells will be saved to: {projectPath}/10-WELLS/[well-name].ptrc
                </p>
              )}
            </div>

            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => onOpenChange(false)}
                disabled={isUploading}
              >
                Cancel
              </Button>
              <Button onClick={handleCsvUpload} disabled={isUploading || !csvFile}>
                <Upload className="w-4 h-4 mr-2" />
                {isUploading ? "Uploading..." : "Upload & Create Wells"}
              </Button>
            </DialogFooter>
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}
