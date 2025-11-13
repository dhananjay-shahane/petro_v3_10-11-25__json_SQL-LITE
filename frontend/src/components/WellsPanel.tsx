import DockPanel from "./DockPanel";

export default function WellsPanel({ onClose }: { onClose?: () => void }) {
  return (
    <DockPanel title="Wells" onClose={onClose}>
      <div className="p-4 text-center text-muted-foreground">
        <p>No wells available</p>
      </div>
    </DockPanel>
  );
}
