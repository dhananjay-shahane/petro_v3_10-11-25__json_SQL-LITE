interface Column {
  id: string;
  label: string;
  width?: string;
}

interface DataGridProps {
  columns: Column[];
  data: Record<string, any>[];
  onRowClick?: (row: Record<string, any>, index: number) => void;
}

export default function DataGrid({ columns, data, onRowClick }: DataGridProps) {
  return (
    <div className="w-full h-full overflow-auto">
      <table className="w-full">
        <thead className="sticky top-0 bg-card border-b border-card-border">
          <tr className="h-8">
            {columns.map((col) => (
              <th
                key={col.id}
                className="px-3 py-2 text-left font-semibold text-foreground"
                style={{ width: col.width }}
              >
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, idx) => (
            <tr
              key={idx}
              className="h-9 border-b border-card-border hover-elevate cursor-pointer even:bg-card/50"
              onClick={() => onRowClick?.(row, idx)}
              data-testid={`row-data-${idx}`}
            >
              {columns.map((col) => (
                <td key={col.id} className="px-3 py-2 text-foreground">
                  {row[col.id]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
