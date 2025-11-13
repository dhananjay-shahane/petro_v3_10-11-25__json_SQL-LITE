import React from 'react';
import { useDropzone } from 'react-dropzone';
import { CloudUpload, FileText, CheckCircle2, XCircle, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Progress } from '@/components/ui/progress';

export interface FileUploadItem {
  id: string;
  name: string;
  size: number;
  status: 'pending' | 'uploading' | 'success' | 'error';
  progress?: number;
  errorMessage?: string;
}

interface FileUploadZoneProps {
  mode: 'single-las' | 'multi-las' | 'csv';
  accept?: Record<string, string[]>;
  multiple?: boolean;
  maxSizeMB?: number;
  files?: FileUploadItem[];
  onFilesAccepted: (files: File[]) => void;
  onFilesRejected?: (files: File[]) => void;
  disabled?: boolean;
  className?: string;
  allowFolders?: boolean;
}

export function FileUploadZone({
  mode,
  accept = {
    'application/las': ['.las'],
    'text/plain': ['.las', '.LAS']
  },
  multiple = false,
  maxSizeMB = 500,
  files = [],
  onFilesAccepted,
  onFilesRejected,
  disabled = false,
  className,
  allowFolders = false
}: FileUploadZoneProps) {
  const maxSize = maxSizeMB * 1024 * 1024;

  const { getRootProps, getInputProps, isDragActive, isDragReject } = useDropzone({
    accept,
    multiple,
    maxSize,
    disabled,
    useFsAccessApi: false,
    onDrop: (acceptedFiles, rejectedFiles) => {
      if (acceptedFiles.length > 0) {
        onFilesAccepted(acceptedFiles);
      }
      if (rejectedFiles.length > 0 && onFilesRejected) {
        onFilesRejected(rejectedFiles.map(f => f.file));
      }
    }
  });

  const getFileIcon = (status: string) => {
    switch (status) {
      case 'uploading':
        return <Loader2 className="h-5 w-5 animate-spin text-blue-500" />;
      case 'success':
        return <CheckCircle2 className="h-5 w-5 text-green-500" />;
      case 'error':
        return <XCircle className="h-5 w-5 text-red-500" />;
      default:
        return <FileText className="h-5 w-5 text-muted-foreground" />;
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  };

  return (
    <div className={cn("space-y-4", className)}>
      <div
        {...getRootProps()}
        className={cn(
          "border-2 border-dashed rounded-lg p-8 transition-colors cursor-pointer",
          "hover:border-primary/50 hover:bg-accent/5",
          isDragActive && !isDragReject && "border-primary bg-primary/5",
          isDragReject && "border-destructive bg-destructive/5",
          disabled && "opacity-50 cursor-not-allowed"
        )}
      >
        <input {...getInputProps(allowFolders ? {
          webkitdirectory: "true",
          directory: ""
        } as any : {})} />
        
        <div className="flex flex-col items-center justify-center text-center space-y-4">
          <div className="relative">
            <CloudUpload 
              className={cn(
                "h-16 w-16 text-muted-foreground/50",
                isDragActive && !isDragReject && "text-primary",
                isDragReject && "text-destructive"
              )} 
            />
            <FileText 
              className={cn(
                "h-8 w-8 absolute bottom-0 right-0 text-muted-foreground/30",
                isDragActive && !isDragReject && "text-primary/70"
              )}
            />
          </div>
          
          <div>
            <p className="text-base font-medium">
              {isDragActive ? (
                isDragReject ? (
                  <span className="text-destructive">File type not accepted</span>
                ) : (
                  <span className="text-primary">Drop your files here</span>
                )
              ) : (
                <>
                  Drop your files here or{' '}
                  <span className="text-primary underline">Browse</span>
                </>
              )}
            </p>
            <p className="text-sm text-muted-foreground mt-1">
              {mode === 'csv' && 'CSV file only'}
              {mode === 'single-las' && 'Single LAS file'}
              {mode === 'multi-las' && 'Multiple LAS files'}
              {' • '}Maximum {maxSizeMB} MB per file
            </p>
          </div>
        </div>
      </div>

      {files.length > 0 && (
        <div className="space-y-2">
          <p className="text-sm font-medium">
            {files.length} {files.length === 1 ? 'file' : 'files'} selected
          </p>
          
          <div className="space-y-2 max-h-60 overflow-y-auto">
            {files.map((file) => (
              <div
                key={file.id}
                className="flex items-center gap-3 p-3 border rounded-lg bg-card"
              >
                <div className="flex-shrink-0">
                  {getFileIcon(file.status)}
                </div>
                
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{file.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {formatFileSize(file.size)}
                  </p>
                  
                  {file.status === 'uploading' && file.progress !== undefined && (
                    <Progress value={file.progress} className="h-1 mt-2" />
                  )}
                  
                  {file.status === 'error' && file.errorMessage && (
                    <p className="text-xs text-destructive mt-1">{file.errorMessage}</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
