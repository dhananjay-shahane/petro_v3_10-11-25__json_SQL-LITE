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
import { Label } from "@/components/ui/label";
import { Download, FileImage, FileCode } from "lucide-react";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { useToast } from "@/hooks/use-toast";

interface CrossPlotDownloadDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  plotImage: string | null;
}

export default function CrossPlotDownloadDialog({
  open,
  onOpenChange,
  plotImage,
}: CrossPlotDownloadDialogProps) {
  const { toast } = useToast();
  const [selectedFormat, setSelectedFormat] = useState("png");

  const downloadFormats = [
    { value: "png", label: "PNG Image", icon: FileImage, description: "Portable Network Graphics" },
    { value: "jpg", label: "JPG Image", icon: FileImage, description: "JPEG format" },
    { value: "svg", label: "SVG Vector", icon: FileCode, description: "Scalable Vector Graphics" },
  ];

  const handleDownload = () => {
    if (!plotImage) {
      toast({
        title: "Error",
        description: "No plot image available to download",
        variant: "destructive",
      });
      return;
    }

    try {
      const link = document.createElement("a");
      const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
      
      if (selectedFormat === "svg") {
        toast({
          title: "Format Not Supported",
          description: "SVG export is not yet implemented. Please use PNG or JPG.",
          variant: "destructive",
        });
        return;
      }

      link.href = `data:image/${selectedFormat};base64,${plotImage}`;
      link.download = `crossplot_${timestamp}.${selectedFormat}`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      toast({
        title: "Download Started",
        description: `Cross plot saved as ${selectedFormat.toUpperCase()}`,
      });

      onOpenChange(false);
    } catch (error) {
      toast({
        title: "Download Failed",
        description: "An error occurred while downloading the plot",
        variant: "destructive",
      });
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[480px]">
        <DialogHeader>
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-primary/10 rounded-lg">
              <Download className="h-5 w-5 text-primary" />
            </div>
            <div>
              <DialogTitle className="text-xl">Download Cross Plot</DialogTitle>
              <DialogDescription className="mt-1">
                Choose a format to download the plot
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        <div className="space-y-4 py-4">
          <RadioGroup value={selectedFormat} onValueChange={setSelectedFormat}>
            <div className="space-y-2">
              {downloadFormats.map((format) => (
                <div
                  key={format.value}
                  className="flex items-center space-x-3 border rounded-lg p-3 hover:bg-accent/50 transition-colors"
                >
                  <RadioGroupItem value={format.value} id={format.value} />
                  <Label
                    htmlFor={format.value}
                    className="flex-1 cursor-pointer flex items-center gap-3"
                  >
                    <format.icon className="h-5 w-5 text-muted-foreground" />
                    <div>
                      <div className="font-medium">{format.label}</div>
                      <div className="text-xs text-muted-foreground">
                        {format.description}
                      </div>
                    </div>
                  </Label>
                </div>
              ))}
            </div>
          </RadioGroup>
        </div>

        <DialogFooter className="gap-2">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleDownload} className="gap-2">
            <Download className="h-4 w-4" />
            Download
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
