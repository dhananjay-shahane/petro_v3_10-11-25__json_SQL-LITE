import DockPanel from "./DockPanel";
import TabbedPanel from "./TabbedPanel";
import DataGrid from "./DataGrid";

export default function DataBrowserPanel({
  onClose,
  onMinimize,
  onMaximize,
}: {
  onClose?: () => void;
  onMinimize?: () => void;
  onMaximize?: () => void;
}) {
  const columns = [
    { id: "index", label: "#", width: "60px" },
    { id: "name", label: "Name", width: "200px" },
    { id: "value", label: "Value" },
  ];

  const logsData = Array.from({ length: 20 }, (_, i) => ({
    index: `${i + 1}`,
    name: `Log Entry ${i + 1}`,
    value: `${(Math.random() * 1000).toFixed(2)}`,
  }));

  const tabs = [
    {
      id: "logs",
      label: "Logs",
      content: (
        <div className="h-full">
          <DataGrid
            columns={columns}
            data={logsData}
            onRowClick={(row) => console.log("Row clicked:", row)}
          />
        </div>
      ),
    },
    {
      id: "log-values",
      label: "Log Values",
      content: (
        <div className="p-3 text-sm text-muted-foreground">
          Log values content
        </div>
      ),
    },
    {
      id: "constants",
      label: "Constants",
      content: (
        <div className="p-3 text-sm text-muted-foreground">
          Constants content
        </div>
      ),
    },
  ];

  return (
    <DockPanel
      title="Data Browser"
      onClose={onClose}
      onMinimize={onMinimize}
      onMaximize={onMaximize}
    >
      <div style={{ fontSize: 'var(--font-size-data-browser, 14px)' }} className="h-full">
        <TabbedPanel tabs={tabs} defaultTab="logs" />
      </div>
    </DockPanel>
  );
}
