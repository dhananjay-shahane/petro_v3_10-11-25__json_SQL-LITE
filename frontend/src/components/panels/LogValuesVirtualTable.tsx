import { memo, useMemo, useState, useCallback, useRef, useEffect } from "react";

interface WellLog {
  name: string;
  log: any[];
}

interface LogValuesVirtualTableProps {
  logs: WellLog[];
  rowCount: number;
  height: number;
}

const ROW_HEIGHT = 36;
const HEADER_HEIGHT = 40;
const OVERSCAN_COUNT = 5;

const LogValuesVirtualTable = memo(function LogValuesVirtualTable({
  logs,
  rowCount,
  height,
}: LogValuesVirtualTableProps) {
  const [scrollTop, setScrollTop] = useState(0);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setScrollTop(0);
    if (scrollRef.current) {
      scrollRef.current.scrollTop = 0;
    }
  }, [logs, rowCount]);

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
      >
        {logs.map((log, index) => (
          <div
            key={index}
            className="flex-1 px-4 py-2 text-left font-semibold text-foreground border-r border-border last:border-r-0 overflow-hidden text-ellipsis whitespace-nowrap relative"
          >
            {log.name}
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
              const rowIndex = startRow + index;
              if (rowIndex >= rowCount) return null;

              return (
                <div
                  key={rowIndex}
                  className="flex border-b border-border hover:bg-accent/50"
                  style={{ height: `${ROW_HEIGHT}px` }}
                >
                  {logs.map((log, colIndex) => {
                    const value = log.log[rowIndex];
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
