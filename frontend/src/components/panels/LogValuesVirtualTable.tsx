import { memo, useMemo, useState, useCallback, useRef, useEffect } from "react";
import { ChevronUp, ChevronDown, ChevronsUpDown } from "lucide-react";

interface WellLog {
  name: string;
  log: any[];
}

interface LogValuesVirtualTableProps {
  logs: WellLog[];
  rowCount: number;
  height: number;
}

type SortOrder = 'asc' | 'desc' | null;

const ROW_HEIGHT = 36;
const HEADER_HEIGHT = 40;
const OVERSCAN_COUNT = 5;

const LogValuesVirtualTable = memo(function LogValuesVirtualTable({
  logs,
  rowCount,
  height,
}: LogValuesVirtualTableProps) {
  const [scrollTop, setScrollTop] = useState(0);
  const [sortColumn, setSortColumn] = useState<number | null>(null);
  const [sortOrder, setSortOrder] = useState<SortOrder>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setScrollTop(0);
    if (scrollRef.current) {
      scrollRef.current.scrollTop = 0;
    }
    setSortColumn(null);
    setSortOrder(null);
  }, [logs, rowCount]);

  const handleSort = useCallback((columnIndex: number) => {
    if (sortColumn === columnIndex) {
      if (sortOrder === 'asc') {
        setSortOrder('desc');
      } else if (sortOrder === 'desc') {
        setSortColumn(null);
        setSortOrder(null);
      }
    } else {
      setSortColumn(columnIndex);
      setSortOrder('asc');
    }
  }, [sortColumn, sortOrder]);

  const sortedIndices = useMemo(() => {
    if (sortColumn === null || sortOrder === null || logs.length === 0) {
      return Array.from({ length: rowCount }, (_, i) => i);
    }

    const log = logs[sortColumn];
    if (!log || !log.log) {
      return Array.from({ length: rowCount }, (_, i) => i);
    }

    const columnLength = log.log.length;
    const indices = Array.from({ length: rowCount }, (_, i) => i);
    
    indices.sort((a, b) => {
      const valueA = a < columnLength ? log.log[a] : undefined;
      const valueB = b < columnLength ? log.log[b] : undefined;
      
      const isNullA = valueA === null || valueA === undefined || valueA === '';
      const isNullB = valueB === null || valueB === undefined || valueB === '';
      
      if (isNullA && isNullB) return 0;
      if (isNullA) return sortOrder === 'asc' ? 1 : -1;
      if (isNullB) return sortOrder === 'asc' ? -1 : 1;
      
      const numA = typeof valueA === 'number' ? valueA : Number(valueA);
      const numB = typeof valueB === 'number' ? valueB : Number(valueB);
      
      const isNumA = !isNaN(numA) && isFinite(numA);
      const isNumB = !isNaN(numB) && isFinite(numB);
      
      if (isNumA && isNumB) {
        return sortOrder === 'asc' ? numA - numB : numB - numA;
      }
      
      if (isNumA && !isNumB) return sortOrder === 'asc' ? -1 : 1;
      if (!isNumA && isNumB) return sortOrder === 'asc' ? 1 : -1;
      
      const strA = String(valueA);
      const strB = String(valueB);
      
      return sortOrder === 'asc' 
        ? strA.localeCompare(strB, undefined, { numeric: true })
        : strB.localeCompare(strA, undefined, { numeric: true });
    });
    
    return indices;
  }, [sortColumn, sortOrder, logs, rowCount]);

  const scrollHeight = height - HEADER_HEIGHT;
  const visibleRowCount = Math.ceil(scrollHeight / ROW_HEIGHT);

  const { startRow, endRow, offsetY } = useMemo(() => {
    if (rowCount === 0) {
      return { startRow: 0, endRow: 0, offsetY: 0 };
    }

    const rawStart = Math.floor(scrollTop / ROW_HEIGHT);
    const maxStart = Math.max(0, rowCount - visibleRowCount);
    const start = Math.min(rawStart, maxStart);
    const startWithOverscan = Math.max(0, start - OVERSCAN_COUNT);
    const end = Math.min(rowCount, start + visibleRowCount + OVERSCAN_COUNT);

    return {
      startRow: startWithOverscan,
      endRow: end,
      offsetY: startWithOverscan * ROW_HEIGHT,
    };
  }, [scrollTop, visibleRowCount, rowCount]);

  const handleScroll = useCallback((e: React.UIEvent<HTMLDivElement>) => {
    setScrollTop(e.currentTarget.scrollTop);
  }, []);

  const totalHeight = rowCount * ROW_HEIGHT;
  const visibleRows = Math.max(0, endRow - startRow);

  return (
    <div
      className="flex flex-col border border-border"
      style={{ height: `${height}px` }}
    >
      {/* Sticky header */}
      <div
        className="sticky top-0 z-10 flex bg-muted dark:bg-card border-b border-border"
        style={{ height: `${HEADER_HEIGHT}px` }}
        role="row"
      >
        {logs.map((log, index) => (
          <div
            key={index}
            role="columnheader"
            aria-sort={
              sortColumn === index
                ? sortOrder === 'asc'
                  ? 'ascending'
                  : sortOrder === 'desc'
                  ? 'descending'
                  : 'none'
                : 'none'
            }
            className="flex-1 border-r border-border last:border-r-0"
          >
            <button
              onClick={() => handleSort(index)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  handleSort(index);
                }
              }}
              className="w-full h-full px-4 py-2 text-left font-semibold text-foreground hover:bg-accent/50 cursor-pointer focus:outline-none focus:ring-2 focus:ring-primary transition-colors flex items-center justify-between gap-2"
              title={`Sort by ${log.name}`}
              aria-label={`Sort by ${log.name}${
                sortColumn === index
                  ? `, currently sorted ${sortOrder === 'asc' ? 'ascending' : 'descending'}`
                  : ''
              }`}
            >
              <span className="truncate">{log.name}</span>
              <span className="flex-shrink-0 text-muted-foreground" aria-hidden="true">
                {sortColumn === index ? (
                  sortOrder === 'asc' ? (
                    <ChevronUp className="h-4 w-4" />
                  ) : (
                    <ChevronDown className="h-4 w-4" />
                  )
                ) : (
                  <ChevronsUpDown className="h-3.5 w-3.5 opacity-40" />
                )}
              </span>
            </button>
          </div>
        ))}
      </div>

      {/* Scrollable content */}
      <div
        ref={scrollRef}
        className="overflow-auto relative h-80 direction-ltl"
        style={{
          height: `${scrollHeight}px`,
        }}
        onScroll={handleScroll}
      >
        <div style={{ height: `${totalHeight}px`, position: "relative" }}>
          <div
            style={{
              transform: `translateY(${offsetY}px)`,
              willChange: "transform",
            }}
          >
            {Array.from({ length: visibleRows }, (_, index) => {
              const virtualIndex = startRow + index;
              if (virtualIndex >= rowCount) return null;

              const actualRowIndex = sortedIndices[virtualIndex];

              return (
                <div
                  key={virtualIndex}
                  className="flex border-b border-border hover:bg-accent/50"
                  style={{ height: `${ROW_HEIGHT}px` }}
                >
                  {logs.map((log, colIndex) => {
                    const value = log.log[actualRowIndex];
                    return (
                      <div
                        key={colIndex}
                        className="flex-1 px-4 py-2 text-foreground border-r border-border last:border-r-0 overflow-hidden text-ellipsis whitespace-nowrap flex items-center"
                      >
                        {value !== null && value !== undefined ? value : "-"}
                      </div>
                    );
                  })}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
});

export default LogValuesVirtualTable;
