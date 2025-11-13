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
  const [lasFiles, setLasFiles] = useState<File[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [lasPreview, setLasPreview] = useState<any>(null);
  const [batchPreview, setBatchPreview] = useState<any>(null);
  const [setName, setSetName] = useState<string>("");
  const [datasetType, setDatasetType] = useState<string>("CONTINUOUS");
  const { toast} = useToast();

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

  const handleBatchLasPreview = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    
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
      formData.append("projectPath", projectPath);
      
      for (let i = 0; i < files.length; i++) {
        formData.append("files", files[i]);
      }
      
      const response = await fetch("/api/wells/preview-las-batch", {
        method: "POST",
        body: formData,
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "Failed to preview LAS files");
      }
      
      const result = await response.json();
      setBatchPreview(result);
      setLasFiles(Array.from(files));
      
      toast({
        title: "Preview Ready",
        description: `${result.validFiles} of ${result.totalFiles} files ready to import`,
      });
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.message || "Failed to preview LAS files",
        variant: "destructive",
      });
    } finally {
      setIsUploading(false);
    }
  };

  const handleBatchLasImport = async () => {
    if (!batchPreview || !batchPreview.files || batchPreview.files.length === 0) {
      toast({
        title: "Error",
        description: "No files to import. Please select files first.",
        variant: "destructive",
      });
      return;
    }

    setIsUploading(true);

    try {
      const validFiles = batchPreview.files.filter((f: any) => f.tempFileId && f.validationErrors.length === 0);
      
      if (validFiles.length === 0) {
        throw new Error("No valid files to import");
      }

      const importRequest = {
        projectPath: projectPath,
        files: validFiles.map((f: any) => ({
          tempFileId: f.tempFileId,
          datasetType: datasetType,
        })),
        defaultDatasetType: datasetType,
        defaultDatasetSuffix: "",
      };

      const response = await fetch("/api/wells/import-las-batch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(importRequest),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "Failed to import LAS files");
      }

      const result = await response.json();

      toast({
        title: "Success",
        description: result.message,
      });

      if (result.results && result.results.length > 0 && onWellCreated) {
        result.results.forEach((res: any) => {
          if (res.status !== "failed" && res.wellName) {
            onWellCreated({
              id: res.wellName,
              name: res.wellName,
              path: `${projectPath}/10-WELLS/${res.wellName}.ptrc`,
            });
          }
        });
      }

      setLasFiles([]);
      setBatchPreview(null);
      setDatasetType("CONTINUOUS");
      onOpenChange(false);
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.message || "Failed to import LAS files",
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
      setLasFiles([]);
      setLasPreview(null);
      setBatchPreview(null);
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
          <DialogTitle>Load Well</DialogTitle>
          <DialogDescription>
            Upload a LAS file or CSV file with well data to create wells in your project.
          </DialogDescription>
        </DialogHeader>
        
        <Tabs defaultValue="help" className="w-full">
          <TabsList className="grid w-full grid-cols-4">
            <TabsTrigger value="help">Help</TabsTrigger>
            <TabsTrigger value="las">Load LAS</TabsTrigger>
            <TabsTrigger value="las-folder">Load LAS Folder</TabsTrigger>
            <TabsTrigger value="csv">Upload CSV</TabsTrigger>
          </TabsList>
          
          <TabsContent value="help" className="space-y-4 pt-4">
            <div className="bg-muted p-6 rounded-lg space-y-4">
              <h3 className="font-bold text-lg">Load Well - Help & Information</h3>
              
              <div className="space-y-3">
                <div>
                  <p className="font-semibold text-sm mb-2">📁 Load LAS (Single File)</p>
                  <p className="text-sm text-muted-foreground">
                    Upload a single LAS file to create a new well or add a dataset to an existing well. 
                    The well name is automatically extracted from the LAS file header.
                  </p>
                </div>

                <div>
                  <p className="font-semibold text-sm mb-2">📂 Load LAS Folder (Multiple Files)</p>
                  <p className="text-sm text-muted-foreground">
                    Select multiple LAS files at once. Each file will be processed individually:
                  </p>
                  <ul className="list-disc list-inside text-sm text-muted-foreground ml-4 mt-1 space-y-1">
                    <li>If well exists: Dataset is added to existing well</li>
                    <li>If well doesn't exist: New well is created</li>
                    <li>Preview shows which wells will be created/updated</li>
                  </ul>
                </div>

                <div>
                  <p className="font-semibold text-sm mb-2">📄 Upload CSV (Batch Well Creation)</p>
                  <p className="text-sm text-muted-foreground">
                    Upload a CSV file with well information to create multiple wells at once.
                  </p>
                </div>

                <div className="pt-3 border-t border-border">
                  <p className="font-semibold text-sm mb-2">📊 LAS File Requirements</p>
                  <ul className="list-disc list-inside text-sm text-muted-foreground space-y-1">
                    <li>File must have .las or .LAS extension</li>
                    <li>Must contain WELL name in header section</li>
                    <li>Maximum file size: 500 MB (recommended: up to 50 MB)</li>
                    <li>Well data saved as JSON in 10-WELLS folder with .ptrc extension</li>
                    <li>Original LAS files copied to 02-INPUT_LAS_FOLDER</li>
                  </ul>
                </div>

                <div className="pt-3 border-t border-border">
                  <p className="font-semibold text-sm mb-2">💾 Storage Information</p>
                  <p className="text-sm text-muted-foreground">
                    Wells are stored as individual JSON files with .ptrc extension in the project's 10-WELLS folder. 
                    This allows for efficient loading and in-memory caching using LRU (Least Recently Used) algorithm.
                  </p>
                </div>
              </div>
            </div>

            <div className="text-sm text-muted-foreground">
              <p className="font-medium">Current Project:</p>
              <p className="font-mono text-xs mt-1">{projectPath || "No project selected"}</p>
            </div>
          </TabsContent>
          
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

            {lasPreview && (
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
          
          <TabsContent value="las-folder" className="space-y-4 pt-4">
            <div className="grid gap-2">
              <Label htmlFor="las-files">Select Multiple LAS Files</Label>
              <div className="flex items-center gap-2">
                <Input
                  id="las-files"
                  type="file"
                  accept=".las,.LAS"
                  multiple
                  onChange={(e) => handleBatchLasPreview(e.target.files)}
                  disabled={isUploading}
                  className="cursor-pointer"
                />
              </div>
              {lasFiles.length > 0 && (
                <p className="text-sm text-muted-foreground">
                  Selected: {lasFiles.length} file(s)
                </p>
              )}
            </div>

            {batchPreview && batchPreview.files && batchPreview.files.length > 0 && (
              <div className="bg-muted p-4 rounded-lg text-sm space-y-3 max-h-96 overflow-y-auto">
                <div className="font-medium text-green-600">
                  ✓ Preview Ready: {batchPreview.validFiles} valid, {batchPreview.duplicates} existing, {batchPreview.errors} errors
                </div>
                
                <div className="space-y-2">
                  {batchPreview.files.map((file: any, idx: number) => (
                    <div
                      key={idx}
                      className={`p-3 rounded border ${
                        file.validationErrors && file.validationErrors.length > 0
                          ? 'border-red-300 bg-red-50'
                          : file.isDuplicate
                          ? 'border-yellow-300 bg-yellow-50'
                          : 'border-green-300 bg-green-50'
                      }`}
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <p className="font-medium text-xs">
                            {file.filename}
                            {file.isDuplicate && <span className="ml-2 text-yellow-700">(Will Update Existing)</span>}
                            {file.validationErrors && file.validationErrors.length > 0 && (
                              <span className="ml-2 text-red-700">(Error)</span>
                            )}
                          </p>
                          {file.wellName && (
                            <p className="text-xs text-muted-foreground mt-1">
                              Well: {file.wellName} | Curves: {file.curveNames?.length || 0} | 
                              Depth: {file.startDepth?.toFixed(1)} - {file.stopDepth?.toFixed(1)} | 
                              Points: {file.dataPoints}
                            </p>
                          )}
                          {file.validationErrors && file.validationErrors.length > 0 && (
                            <div className="mt-1 text-xs text-red-600">
                              {file.validationErrors.map((err: string, i: number) => (
                                <div key={i}>• {err}</div>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

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
              <Button
                onClick={handleBatchLasImport}
                disabled={isUploading || !batchPreview || batchPreview.validFiles === 0}
              >
                <Upload className="w-4 h-4 mr-2" />
                {isUploading ? "Importing..." : `Import ${batchPreview?.validFiles || 0} Files`}
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
