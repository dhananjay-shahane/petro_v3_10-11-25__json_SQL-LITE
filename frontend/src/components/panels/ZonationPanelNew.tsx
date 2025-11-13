import { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Upload, Trash2, FileText, Check, Filter } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import LogSelectDialog from "../dialogs/LogSelectDialog";
import axios from "axios";

interface WellData {
  id: string;
  name: string;
  path: string;
  projectPath?: string;
  data?: any;
  logs?: any[];
  metadata?: any;
}

interface TopsFile {
  filename: string;
  path: string;
  size: number;
}

interface ZoneData {
  zone: string;
  depth: number;
}

interface FileSummary {
  filename: string;
  well_count: number;
  zone_count: number;
  wells: string[];
  unique_zones: string[];
  file_type: string;
}

export default function ZonationPanelNew({ 
  onClose,
  projectPath,
  selectedWell
}: { 
  onClose?: () => void;
  projectPath?: string;
  selectedWell?: WellData | null;
}) {
  const { toast } = useToast();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [topsFiles, setTopsFiles] = useState<TopsFile[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedFile, setSelectedFile] = useState<string>("");
  const [zones, setZones] = useState<ZoneData[]>([]);
  const [fileSummary, setFileSummary] = useState<FileSummary | null>(null);
  const [isLoadingZones, setIsLoadingZones] = useState(false);
  const [selectedZones, setSelectedZones] = useState<Set<string>>(new Set());
  const [logSelectDialogOpen, setLogSelectDialogOpen] = useState(false);
  const [selectedTopsLog, setSelectedTopsLog] = useState<string>("");

  // Load tops files when component mounts or projectPath changes
  useEffect(() => {
    if (projectPath) {
      loadTopsFiles();
    }
  }, [projectPath]);

  // Load zones when a file is selected or well changes
  useEffect(() => {
    if (selectedFile && projectPath) {
      loadFileSummaryAndZones(selectedFile);
    } else {
      setZones([]);
      setFileSummary(null);
    }
    setSelectedZones(new Set());
  }, [selectedFile, projectPath, selectedWell]);

  const handleZoneClick = (zoneName: string) => {
    setSelectedZones((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(zoneName)) {
        newSet.delete(zoneName);
      } else {
        newSet.add(zoneName);
      }
      return newSet;
    });
  };

  const handleSelectAllZones = () => {
    if (selectedZones.size === zones.length) {
      setSelectedZones(new Set());
    } else {
      setSelectedZones(new Set(zones.map(z => z.zone)));
    }
  };

  const loadTopsFiles = async () => {
    if (!projectPath) return;
    
    setIsLoading(true);
    try {
      const response = await axios.get(`/api/tops/list?project_path=${encodeURIComponent(projectPath)}`);
      
      if (response.data.success) {
        setTopsFiles(response.data.files);
        console.log(`[Zonation] Loaded ${response.data.files.length} tops files`);
        
        if (response.data.files.length > 0 && !selectedFile) {
          setSelectedFile(response.data.files[0].filename);
        }
      }
    } catch (error) {
      console.error('[Zonation] Error loading tops files:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const loadFileSummaryAndZones = async (filename: string) => {
    if (!projectPath) return;
    
    setIsLoadingZones(true);
    setZones([]);
    
    try {
      const summaryResponse = await axios.get(`/api/tops/summary?project_path=${encodeURIComponent(projectPath)}&filename=${encodeURIComponent(filename)}`);
      
      if (summaryResponse.data.success) {
        setFileSummary(summaryResponse.data.summary);
        console.log(`[Zonation] Loaded summary for ${filename}:`, summaryResponse.data.summary);
      }
      
      let zonesLoaded = false;
      
      if (selectedWell) {
        try {
          const zonesResponse = await axios.get(`/api/tops/zones/well?project_path=${encodeURIComponent(projectPath)}&filename=${encodeURIComponent(filename)}&well_name=${encodeURIComponent(selectedWell.name)}`);
          
          if (zonesResponse.data.success && zonesResponse.data.zones.length > 0) {
            setZones(zonesResponse.data.zones);
            console.log(`[Zonation] Loaded ${zonesResponse.data.zones.length} zones with depths for well ${selectedWell.name} from ${filename}`);
            zonesLoaded = true;
          }
        } catch (wellError: any) {
          console.log(`[Zonation] Well ${selectedWell.name} not found in ${filename}, loading all zones instead`);
        }
      }
      
      if (!zonesLoaded) {
        const zonesResponse = await axios.get(`/api/tops/zones?project_path=${encodeURIComponent(projectPath)}&filename=${encodeURIComponent(filename)}`);
        
        if (zonesResponse.data.success) {
          const zonesWithoutDepths = zonesResponse.data.zones.map((zoneName: string) => ({
            zone: zoneName,
            depth: 0
          }));
          setZones(zonesWithoutDepths);
          console.log(`[Zonation] Loaded ${zonesResponse.data.zones.length} zones (no depths) from ${filename}`);
        }
      }
    } catch (error) {
      console.error('[Zonation] Error loading zones:', error);
      toast({
        title: "Load Failed",
        description: "Failed to load zone data from file",
        variant: "destructive",
      });
    } finally {
      setIsLoadingZones(false);
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
      
      if (selectedFile === filename) {
        setSelectedFile("");
      }
      
      await loadTopsFiles();
      
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
    <div className="flex flex-col h-full bg-white dark:bg-card">
      <div className="flex items-center gap-2 p-2 border-b border-card-border">
        <span className="text-sm text-foreground font-medium">Select Tops:</span>
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
      
      <div className="flex-1 flex flex-col overflow-hidden" style={{ fontSize: 'var(--font-size-zonation-list, 14px)' }}>
        {isLoading ? (
          <div className="flex items-center justify-center h-full">
            <p className="text-muted-foreground">Loading tops files...</p>
          </div>
        ) : topsFiles.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center p-4">
            <FileText className="w-12 h-12 text-muted-foreground mb-2" />
            <p className="text-muted-foreground">No tops files uploaded</p>
            <p className="text-muted-foreground mt-1 text-[0.85em]">Upload a tops file to get started</p>
          </div>
        ) : (
          <>
            <div className="p-3 space-y-2 border-b border-card-border">
              <Select value={selectedFile} onValueChange={setSelectedFile}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Select a tops file" />
                </SelectTrigger>
                <SelectContent>
                  {topsFiles.map((file) => (
                    <SelectItem key={file.filename} value={file.filename}>
                      {file.filename}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              
              {selectedFile && (
                <div className="flex items-center justify-between">
                  <div className="text-xs text-muted-foreground">
                    {fileSummary && (
                      <span>
                        {fileSummary.zone_count} zones
                      </span>
                    )}
                  </div>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => handleDeleteTopsFile(selectedFile)}
                  >
                    <Trash2 className="w-3 h-3 mr-1" />
                    Delete
                  </Button>
                </div>
              )}
            </div>
            
            <div className="flex-1 overflow-auto p-3">
              {isLoadingZones ? (
                <div className="flex items-center justify-center h-full">
                  <p className="text-sm text-muted-foreground">Loading zones...</p>
                </div>
              ) : zones.length === 0 && selectedFile ? (
                <div className="flex items-center justify-center h-full text-center">
                  <p className="text-sm text-muted-foreground">No zones found in file</p>
                </div>
              ) : (
                <div className="space-y-1">
                  <div className="text-xs font-medium text-muted-foreground mb-2 uppercase flex justify-between items-center">
                    <span>Zones ({zones.length})</span>
                    <div className="flex items-center gap-2">
                      {selectedWell && <span className="text-xs normal-case">Well: {selectedWell.name}</span>}
                      {zones.length > 0 && (
                        <>
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-6 px-2 text-xs"
                            onClick={() => setLogSelectDialogOpen(true)}
                          >
                            <Filter className="w-3 h-3 mr-1" />
                            Filter Logs
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-6 px-2 text-xs"
                            onClick={handleSelectAllZones}
                          >
                            {selectedZones.size === zones.length ? "Deselect All" : "Select All"}
                          </Button>
                        </>
                      )}
                    </div>
                  </div>
                  {selectedZones.size > 0 && (
                    <div className="text-xs text-muted-foreground mb-2 px-2">
                      {selectedZones.size} zone{selectedZones.size !== 1 ? 's' : ''} selected
                    </div>
                  )}
                  {zones.map((zoneData, index) => {
                    const isSelected = selectedZones.has(zoneData.zone);
                    return (
                      <div
                        key={index}
                        onClick={() => handleZoneClick(zoneData.zone)}
                        className={`p-2 border rounded transition-all cursor-pointer ${
                          isSelected 
                            ? 'bg-primary/10 border-primary hover:bg-primary/20' 
                            : 'bg-muted/50 border-border hover:bg-muted'
                        }`}
                      >
                        <div className="flex justify-between items-center">
                          <div className="flex items-center gap-2">
                            <div className={`w-4 h-4 rounded border flex items-center justify-center ${
                              isSelected ? 'bg-primary border-primary' : 'border-muted-foreground/30'
                            }`}>
                              {isSelected && <Check className="w-3 h-3 text-primary-foreground" />}
                            </div>
                            <p className="text-sm font-medium">{zoneData.zone}</p>
                          </div>
                          {selectedWell && zoneData.depth > 0 && (
                            <p className="text-xs text-muted-foreground">{zoneData.depth.toFixed(2)} m</p>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </>
        )}
      </div>
      
      <LogSelectDialog
        open={logSelectDialogOpen}
        onOpenChange={setLogSelectDialogOpen}
        availableLogs={selectedWell?.logs || []}
        selectedLog={selectedTopsLog}
        onSelectLog={setSelectedTopsLog}
        wellName={selectedWell?.name}
      />
    </div>
  );
}
