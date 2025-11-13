import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useState, useEffect, useRef } from "react";
import { Terminal, Play, Trash2, HelpCircle, Folder, Upload } from "lucide-react";
import axios from "axios";
import { Input } from "@/components/ui/input";

interface CLICommandInfo {
  name: string;
  description: string;
}

export default function CLIPanel({
  projectPath,
  onRefreshWells,
  onRefreshWellData,
}: {
  projectPath?: string;
  onRefreshWells?: () => Promise<void>;
  onRefreshWellData?: () => Promise<void>;
}) {
  const [commandInput, setCommandInput] = useState("");
  const [availableCommands, setAvailableCommands] = useState<CLICommandInfo[]>([]);
  const [showHelp, setShowHelp] = useState(false);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [filteredCommands, setFilteredCommands] = useState<CLICommandInfo[]>([]);
  const [selectedSuggestionIndex, setSelectedSuggestionIndex] = useState(0);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const saveTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const suggestionsRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    loadAvailableCommands();
  }, []);

  useEffect(() => {
    if (projectPath) {
      loadCommandHistory();
    }
  }, [projectPath]);

  const loadAvailableCommands = async () => {
    try {
      const response = await axios.get('/api/cli/commands');
      if (response.data.success && response.data.commands) {
        setAvailableCommands(response.data.commands);
      }
    } catch (error) {
      console.error('[CLI] Failed to load commands:', error);
    }
  };

  const loadCommandHistory = async () => {
    if (!projectPath) return;
    
    try {
      const response = await axios.get('/api/cli/history/load', {
        params: { projectPath }
      });
      if (response.data.success && response.data.commandHistory) {
        setCommandInput(response.data.commandHistory);
        console.log('[CLI] Command history loaded from storage');
        const commandLines = response.data.commandHistory.split('\n').filter((l: string) => l.trim()).length;
        (window as any).addAppLog?.(
          `📋 Loaded ${commandLines} command(s) from CLI history`,
          'info',
          'database'
        );
      }
    } catch (error) {
      console.error('[CLI] Failed to load command history:', error);
    }
  };

  const saveCommandHistory = async () => {
    if (!projectPath || !commandInput.trim()) return;
    
    try {
      await axios.post('/api/cli/history/save', {
        projectPath,
        commandHistory: commandInput
      });
      console.log('[CLI] Command history saved to storage');
      (window as any).addAppLog?.(
        `💾 CLI history saved for project: ${projectPath.split('/').pop()}`,
        'success',
        'database'
      );
    } catch (error) {
      console.error('[CLI] Failed to save command history:', error);
    }
  };

  const smartSplitCommand = (command: string): string[] => {
    // Split command respecting quoted strings and preserving paths with spaces
    const parts: string[] = [];
    let current = '';
    let inQuotes = false;
    
    for (let i = 0; i < command.length; i++) {
      const char = command[i];
      
      if (char === '"' || char === "'") {
        inQuotes = !inQuotes;
      } else if (char === ' ' && !inQuotes) {
        if (current) {
          parts.push(current);
          current = '';
        }
      } else {
        current += char;
      }
    }
    
    if (current) {
      parts.push(current);
    }
    
    return parts;
  };

  const isLocalFilePath = (path: string): boolean => {
    // Check for Windows paths (C:\, D:\, etc.) or Unix paths (/home/, /Users/, etc.)
    const windowsPathPattern = /^[A-Za-z]:\\/;
    const unixPathPattern = /^(\/home\/|\/Users\/|~\/)/;
    return windowsPathPattern.test(path) || unixPathPattern.test(path);
  };

  const uploadFileAndReplaceCommand = async (command: string): Promise<string | null> => {
    const parts = smartSplitCommand(command.trim());
    const commandName = parts[0].toUpperCase();
    
    if (commandName === 'IMPORT_LAS_FILE') {
      // Find the file path argument (could be second or third arg depending on format)
      let filePathIndex = -1;
      for (let i = 1; i < parts.length; i++) {
        if (isLocalFilePath(parts[i])) {
          filePathIndex = i;
          break;
        }
      }
      
      if (filePathIndex === -1) {
        return command; // No local path found, proceed normally
      }
      
      window.addAppLog?.('📤 Local file path detected. Please select the LAS file to upload...', 'info');
      
      // Create hidden file input
      const input = document.createElement('input');
      input.type = 'file';
      input.accept = '.las';
      
      return new Promise((resolve) => {
        input.onchange = async (e) => {
          const file = (e.target as HTMLInputElement).files?.[0];
          if (!file) {
            window.addAppLog?.('✗ No file selected', 'error');
            resolve(null);
            return;
          }
          
          try {
            window.addAppLog?.(`📤 Uploading ${file.name}...`, 'info');
            
            const formData = new FormData();
            formData.append('file', file);
            formData.append('project_path', projectPath || '');
            
            const response = await axios.post('/api/upload/las-file', formData, {
              headers: { 'Content-Type': 'multipart/form-data' },
              timeout: 300000  // 5 minutes timeout for large files
            });
            
            if (response.data.success) {
              window.addAppLog?.(`✓ ${response.data.message}`, 'success');
              
              // Replace the local path with server path in command
              // Quote the path if it contains spaces to preserve the filename
              const serverPath = response.data.server_path;
              parts[filePathIndex] = serverPath.includes(' ') ? `"${serverPath}"` : serverPath;
              const newCommand = parts.join(' ');
              
              window.addAppLog?.(`📝 Modified command: ${newCommand}`, 'info');
              resolve(newCommand);
            } else {
              window.addAppLog?.('✗ Upload failed', 'error');
              resolve(null);
            }
          } catch (error: any) {
            window.addAppLog?.(`✗ Upload error: ${error.message}`, 'error');
            resolve(null);
          }
        };
        
        input.click();
      });
    } else if (commandName === 'IMPORT_LAS_FILES_FROM_FOLDER') {
      // Find folder path argument
      let folderPathIndex = -1;
      for (let i = 1; i < parts.length; i++) {
        if (isLocalFilePath(parts[i])) {
          folderPathIndex = i;
          break;
        }
      }
      
      if (folderPathIndex === -1) {
        return command; // No local path found, proceed normally
      }
      
      window.addAppLog?.('📤 Local folder path detected. Please select LAS files to upload...', 'info');
      
      // Create hidden file input for multiple files
      const input = document.createElement('input');
      input.type = 'file';
      input.accept = '.las';
      input.multiple = true;
      
      return new Promise((resolve) => {
        input.onchange = async (e) => {
          const files = (e.target as HTMLInputElement).files;
          if (!files || files.length === 0) {
            window.addAppLog?.('✗ No files selected', 'error');
            resolve(null);
            return;
          }
          
          try {
            window.addAppLog?.(`📤 Uploading ${files.length} file(s)...`, 'info');
            
            const formData = new FormData();
            for (let i = 0; i < files.length; i++) {
              formData.append('files', files[i]);
            }
            formData.append('project_path', projectPath || '');
            
            const response = await axios.post('/api/upload/las-files', formData, {
              headers: { 'Content-Type': 'multipart/form-data' },
              timeout: 300000  // 5 minutes timeout for large files
            });
            
            if (response.data.success) {
              window.addAppLog?.(`✓ ${response.data.message}`, 'success');
              
              // Replace the local folder path with server folder path in command
              // Quote the path if it contains spaces to preserve directory names with spaces
              const folderPath = response.data.folder_path;
              parts[folderPathIndex] = folderPath.includes(' ') ? `"${folderPath}"` : folderPath;
              const newCommand = parts.join(' ');
              
              window.addAppLog?.(`📝 Modified command: ${newCommand}`, 'info');
              resolve(newCommand);
            } else {
              window.addAppLog?.('✗ Upload failed', 'error');
              resolve(null);
            }
          } catch (error: any) {
            window.addAppLog?.(`✗ Upload error: ${error.message}`, 'error');
            resolve(null);
          }
        };
        
        input.click();
      });
    }
    
    return command; // No file path detected, return original command
  };

  const executeCommand = async (command: string) => {
    if (!command.trim()) return;
    if (!projectPath) {
      if (window.addAppLog) {
        window.addAppLog('CLI: No project selected. Please select a project first.', 'error');
      }
      return;
    }

    if (window.addAppLog) {
      window.addAppLog(`${command}`, 'info');
    }

    try {
      // Check if command contains local file paths and handle upload
      const modifiedCommand = await uploadFileAndReplaceCommand(command);
      if (modifiedCommand === null) {
        // Upload was cancelled or failed
        return;
      }
      
      const finalCommand = modifiedCommand;
      
      const deletePermissionEnabled = (window as any).deletePermissionEnabled || false;
      const response = await axios.post('/api/cli/execute', {
        command: finalCommand,
        projectPath: projectPath,
        deletePermissionEnabled: deletePermissionEnabled,
      });

      if (window.addAppLog) {
        window.addAppLog(`✓ ${response.data.message}`, 'success');
        
        // Show result information if available
        if (response.data.result) {
          if (response.data.result.selected_wells) {
            window.addAppLog(
              `💾 Saved ${response.data.result.total_selected} well(s) to storage: ${response.data.result.selected_wells.join(', ')}`,
              'success'
            );
          }
          
          // Show detailed result for other commands
          const resultStr = JSON.stringify(response.data.result, null, 2);
          if (resultStr !== '{}') {
            window.addAppLog(`📋 Result: ${resultStr}`, 'info');
          }
        }
      }

      // Refresh wells list and data browser after certain commands IMMEDIATELY (real-time update)
      const commandName = command.trim().split(' ')[0].toUpperCase();
      
      // Commands that create, modify, or select wells (triggers well list refresh)
      const wellListCommands = ['SELECT_WELLS', 'MAKE_SELECTED_WELL', 'CREATE_EMPTY_WELL', 'DELETE_WELL', 'LIST_ALL_WELLS', 'IMPORT_LAS_FILE', 'IMPORT_LAS_FILES_FROM_FOLDER', 'ACTIVE_WELL'];
      
      // Commands that modify well data (for Data Browser refresh - shows changes immediately)
      const wellDataCommands = ['INSERT_CONSTANT', 'INSERT_LOG', 'DELETE_DATASET', 'IMPORT_LAS_FILE', 'IMPORT_LAS_FILES_FROM_FOLDER', 'LOAD_TOPS', 'LOAD_TOPS_BULK', 'EXPORT_TOPS', 'LIST_OF_DATASET', 'FIND_WITH_DATASET'];
      
      // Refresh wells list immediately after command execution
      if (wellListCommands.includes(commandName)) {
        if (onRefreshWells) {
          window.addAppLog?.('🔄 Refreshing well list...', 'info');
          await onRefreshWells();
          window.addAppLog?.('✓ Well list updated - changes are now visible', 'success');
        }
      }
      
      // Refresh well data browser immediately after command execution
      if (wellDataCommands.includes(commandName)) {
        if (onRefreshWellData) {
          window.addAppLog?.('🔄 Refreshing well data...', 'info');
          await onRefreshWellData();
          window.addAppLog?.('✓ Data browser updated - changes are now visible', 'success');
        }
      }

      // Save command history after successful execution
      await saveCommandHistory();
    } catch (error: any) {
      const errorMessage = error.response?.data?.detail || error.message || 'Command execution failed';
      if (window.addAppLog) {
        window.addAppLog(`✗ ${errorMessage}`, 'error');
      }
    }
  };

  const executeSelectedLine = () => {
    if (!textareaRef.current) return;
    
    const textarea = textareaRef.current;
    const cursorPosition = textarea.selectionStart;
    const textBeforeCursor = textarea.value.substring(0, cursorPosition);
    const lineNumber = textBeforeCursor.split('\n').length - 1;
    const lines = textarea.value.split('\n');
    
    if (lineNumber >= 0 && lineNumber < lines.length) {
      const lineToExecute = lines[lineNumber].trim();
      if (lineToExecute && !lineToExecute.startsWith('#')) {
        executeCommand(lineToExecute);
      }
    }
  };

  const executeAllCommands = () => {
    const lines = commandInput.split('\n');
    const commands = lines.filter(line => line.trim() && !line.trim().startsWith('#'));
    
    commands.forEach((command, index) => {
      setTimeout(() => {
        executeCommand(command);
      }, index * 500);
    });
  };

  const handleTextareaKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      executeSelectedLine();
    }
    
    if (e.shiftKey && e.key === 'Enter') {
      e.preventDefault();
      executeAllCommands();
    }
  };
  
  const updateSuggestions = () => {
    if (!textareaRef.current) return;
    
    const cursorPosition = textareaRef.current.selectionStart;
    const textBeforeCursor = commandInput.substring(0, cursorPosition);
    const lines = textBeforeCursor.split('\n');
    const currentLine = lines[lines.length - 1].trim();
    
    // Only show suggestions at the start of a line (for command name)
    if (!currentLine || currentLine.includes(' ')) {
      setShowSuggestions(false);
      return;
    }
    
    // Filter commands that start with the typed text (case-insensitive)
    const matches = availableCommands.filter(cmd =>
      cmd.name.toUpperCase().startsWith(currentLine.toUpperCase())
    );
    
    if (matches.length > 0 && currentLine.length > 0) {
      setFilteredCommands(matches);
      setSelectedSuggestionIndex(0);
      setShowSuggestions(true);
    } else {
      setShowSuggestions(false);
    }
  };
  
  const completeSuggestion = (commandName: string) => {
    if (!textareaRef.current) return;
    
    const cursorPosition = textareaRef.current.selectionStart;
    const textBeforeCursor = commandInput.substring(0, cursorPosition);
    const textAfterCursor = commandInput.substring(cursorPosition);
    const lines = textBeforeCursor.split('\n');
    const currentLineStart = textBeforeCursor.lastIndexOf('\n') + 1;
    const currentLine = lines[lines.length - 1];
    const leadingWhitespace = currentLine.match(/^\s*/)?.[0] || '';
    
    // Replace the current line with the selected command
    const newText = 
      commandInput.substring(0, currentLineStart) +
      leadingWhitespace + commandName + ' ' +
      textAfterCursor;
    
    setCommandInput(newText);
    setShowSuggestions(false);
    
    // Move cursor to after the command name and space
    setTimeout(() => {
      if (textareaRef.current) {
        const newCursorPos = currentLineStart + leadingWhitespace.length + commandName.length + 1;
        textareaRef.current.selectionStart = newCursorPos;
        textareaRef.current.selectionEnd = newCursorPos;
        textareaRef.current.focus();
      }
    }, 0);
  };

  const clearInput = () => {
    setCommandInput("");
    saveCommandHistory();
  };

  const handleCommandInputChange = (value: string) => {
    setCommandInput(value);
    
    // Debounced auto-save: save 2 seconds after user stops typing
    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current);
    }
    
    saveTimeoutRef.current = setTimeout(() => {
      saveCommandHistory();
    }, 2000);
  };

  const getProjectName = () => {
    if (!projectPath) return "No project";
    return projectPath.split('/').pop() || projectPath.split('\\').pop() || "Unknown";
  };

  const insertExample = (example: string) => {
    setCommandInput(prev => prev ? `${prev}\n${example}` : example);
  };

  return (
    <div className="h-full flex flex-col bg-background" style={{ fontSize: 'var(--font-size-cli-terminal, 13px)' }}>
      {/* Header */}
      <div className="border-b bg-muted/30">
        <div className="flex items-center justify-between px-4 py-2">
          <div className="flex items-center gap-2">
            <Terminal className="w-4 h-4 text-primary" />
            <span className="font-semibold">CLI Terminal</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1.5 px-2 py-1 bg-background rounded text-[0.85em] cursor-help" title={projectPath || "No project selected"}>
              <Folder className="w-3 h-3 text-muted-foreground" />
              <span className="font-mono">{getProjectName()}</span>
            </div>
            <Button
              variant={showHelp ? "default" : "ghost"}
              size="sm"
              onClick={() => setShowHelp(!showHelp)}
              className="h-7"
            >
              <HelpCircle className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
      </div>

      {/* Help Panel */}
      {showHelp && (
        <div className="border-b bg-muted/20 max-h-48 overflow-auto">
          <div className="p-3 space-y-2">
            <div className="text-xs font-semibold mb-2">Available Commands:</div>
            <div className="grid grid-cols-1 gap-1.5">
              {availableCommands.map((cmd) => (
                <div 
                  key={cmd.name} 
                  className="flex items-start gap-2 p-2 hover:bg-muted rounded cursor-pointer transition-colors"
                  onClick={() => insertExample(cmd.name)}
                >
                  <code className="text-xs font-mono font-semibold text-primary flex-shrink-0">{cmd.name}</code>
                  <span className="text-xs text-muted-foreground">{cmd.description}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Command Input Area */}
      <div className="flex-1 flex flex-col p-3">
        <div className="flex-1 flex flex-col border rounded-lg bg-card overflow-hidden relative">
          <div className="flex items-center justify-between px-3 py-2 border-b bg-muted/30">
            <span className="text-xs font-medium text-muted-foreground">Command Editor</span>
            <div className="flex items-center gap-1">
              <Button
                variant="ghost"
                size="sm"
                onClick={executeSelectedLine}
                disabled={!commandInput.trim() || !projectPath}
                className="h-6 text-xs"
              >
                <Play className="h-3 w-3 mr-1" />
                Run Line
              </Button>
              <Button
                size="sm"
                onClick={executeAllCommands}
                disabled={!commandInput.trim() || !projectPath}
                className="h-6 text-xs"
              >
                <Play className="h-3 w-3 mr-1" />
                Run All
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={clearInput}
                disabled={!commandInput}
                className="h-6 text-xs"
              >
                <Trash2 className="h-3 w-3" />
              </Button>
            </div>
          </div>

          <Textarea
            ref={textareaRef}
            value={commandInput}
            onChange={(e) => handleCommandInputChange(e.target.value)}
            onKeyDown={handleTextareaKeyDown}
            placeholder="# Enter CLI commands here (one per line)&#10;# Lines starting with # are comments&#10;&#10;CREATE_EMPTY_WELL MyWell Dev&#10;INSERT_CONSTANT MyWell API_GRAVITY 45.2 API&#10;SELECT_WELLS well1 well2 well3&#10;&#10;# Ctrl/Cmd+Enter: Run current line&#10;# Shift+Enter: Run all commands"
            className="flex-1 resize-none font-mono border-0 focus-visible:ring-0 focus-visible:ring-offset-0 rounded-none"
            style={{ fontSize: 'inherit' }}
            disabled={!projectPath}
          />
        </div>

        {!projectPath && (
          <div className="mt-2 p-2 bg-orange-50 dark:bg-orange-950/20 border border-orange-200 dark:border-orange-800 rounded text-xs text-orange-700 dark:text-orange-400">
            ⚠️ No project selected. Please select a project to execute CLI commands.
          </div>
        )}

        <div className="mt-2 flex items-center justify-between text-xs text-muted-foreground">
          <div className="flex items-center gap-3">
            <span>💡 All output appears in Feedback Logs panel</span>
          </div>
          <div className="flex items-center gap-2">
            <kbd className="px-1.5 py-0.5 bg-muted rounded border text-[10px]">Ctrl+Enter</kbd>
            <span>Run Line</span>
            <kbd className="px-1.5 py-0.5 bg-muted rounded border text-[10px] ml-2">Shift+Enter</kbd>
            <span>Run All</span>
          </div>
        </div>
      </div>
    </div>
  );
}

declare global {
  interface Window {
    addAppLog?: (message: string, type: 'info' | 'error' | 'success' | 'warning', iconType?: string) => void;
  }
}
