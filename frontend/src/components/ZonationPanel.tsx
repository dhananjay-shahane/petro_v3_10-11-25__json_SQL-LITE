import { useState, useRef, useEffect } from "react";
import DockPanel from "./DockPanel";
import { Button } from "@/components/ui/button";
import { Plus, Upload, Trash2, FileText } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import axios from "axios";

interface TopsFile {
  filename: string;
  path: string;
  size: number;
}

export default function ZonationPanel({ 
  onClose,
  projectPath 
}: { 
  onClose?: () => void;
  projectPath?: string;
}) {
  const { toast } = useToast();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [topsFiles, setTopsFiles] = useState<TopsFile[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  // Load tops files when component mounts or projectPath changes
  useEffect(() => {
    if (projectPath) {
      loadTopsFiles();
    }
  }, [projectPath]);

  const loadTopsFiles = async () => {
    if (!projectPath) return;
    
    setIsLoading(true);
    try {
      const response = await axios.get(`/api/tops/list?project_path=${encodeURIComponent(projectPath)}`);
      
      if (response.data.success) {
        setTopsFiles(response.data.files);
        console.log(`[Zonation] Loaded ${response.data.files.length} tops files`);
      }
    } catch (error) {
      console.error('[Zonation] Error loading tops files:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file || !projectPath) return;

    setIsUploading(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("project_path", projectPath);

      const response = await axios.post("/api/tops/upload", formData, {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      });

      if (response.data.success) {
        toast({
          title: "Tops File Uploaded",
          description: `${file.name} uploaded successfully`,
        });
        
        // Reload tops files to show the newly uploaded file
        await loadTopsFiles();
        
        // Log to feedback panel
        if ((window as any).addAppLog) {
          (window as any).addAppLog(`Tops file uploaded: ${file.name}`, 'success');
        }
      }
    } catch (error: any) {
      console.error('[Zonation] Error uploading tops file:', error);
      toast({
        title: "Upload Failed",
        description: error.response?.data?.detail || "Failed to upload tops file",
        variant: "destructive",
      });
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  const handleDeleteTopsFile = async (filename: string) => {
    if (!projectPath) return;
    
    try {
      await axios.delete(`/api/tops/delete?project_path=${encodeURIComponent(projectPath)}&filename=${encodeURIComponent(filename)}`);
      
      toast({
        title: "File Deleted",
        description: `${filename} has been deleted`,
      });
      
      // Reload tops files
      await loadTopsFiles();
      
      // Log to feedback panel
      if ((window as any).addAppLog) {
        (window as any).addAppLog(`Tops file deleted: ${filename}`, 'info');
      }
    } catch (error: any) {
      console.error('[Zonation] Error deleting tops file:', error);
      toast({
        title: "Delete Failed",
        description: error.response?.data?.detail || "Failed to delete tops file",
        variant: "destructive",
      });
    }
  };

  return (
    <DockPanel title="Zonation" onClose={onClose}>
      <div className="flex flex-col h-full">
        <div className="flex items-center gap-2 p-2 border-b border-card-border">
          <span className="text-sm text-foreground font-medium">Tops Files:</span>
          <Button
            size="sm"
            variant="outline"
            className="ml-auto"
            onClick={() => fileInputRef.current?.click()}
            disabled={isUploading || !projectPath}
          >
            <Upload className="w-3 h-3 mr-1" />
            {isUploading ? "Uploading..." : "Upload"}
          </Button>
          <input
            ref={fileInputRef}
            type="file"
            className="hidden"
            onChange={handleFileUpload}
            accept=".txt,.csv,.dat,.tops"
          />
        </div>
        
        <div className="flex-1 overflow-auto p-3">
          {isLoading ? (
            <div className="flex items-center justify-center h-full">
              <p className="text-sm text-muted-foreground">Loading tops files...</p>
            </div>
          ) : topsFiles.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center p-4">
              <FileText className="w-12 h-12 text-muted-foreground mb-2" />
              <p className="text-sm text-muted-foreground">No tops files uploaded</p>
              <p className="text-xs text-muted-foreground mt-1">Upload a tops file to get started</p>
            </div>
          ) : (
            <div className="space-y-2">
              {topsFiles.map((file) => (
                <div
                  key={file.filename}
                  className="flex items-center justify-between p-2 bg-primary/10 border border-primary/20 rounded hover:bg-primary/20 transition-colors"
                >
                  <div className="flex items-center gap-2 flex-1 min-w-0">
                    <FileText className="w-4 h-4 text-primary flex-shrink-0" />
                    <div className="min-w-0">
                      <p className="text-sm font-medium truncate">{file.filename}</p>
                      <p className="text-xs text-muted-foreground">
                        {(file.size / 1024).toFixed(2)} KB
                      </p>
                    </div>
                  </div>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="flex-shrink-0"
                    onClick={() => handleDeleteTopsFile(file.filename)}
                  >
                    <Trash2 className="w-3 h-3" />
                  </Button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </DockPanel>
  );
}
