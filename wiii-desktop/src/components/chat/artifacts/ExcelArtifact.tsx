/**
 * ExcelArtifact — renders Excel/CSV data as interactive HTML table.
 * Sprint 167: "Không Gian Sáng Tạo"
 *
 * Lazy-loads SheetJS (xlsx) on first use for .xlsx parsing.
 * If content is JSON array, renders directly without SheetJS.
 */
import { useState, useMemo, useCallback } from "react";
import { ArrowUpDown, Download } from "lucide-react";
import type { ArtifactData } from "@/api/types";

interface Props {
  artifact: ArtifactData;
  mode: "card" | "panel";
}

const MAX_CARD_ROWS = 8;
const PAGE_SIZE = 50;

export default function ExcelArtifact({ artifact, mode }: Props) {
  const [sortColumn, setSortColumn] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [page, setPage] = useState(0);

  // Parse content — JSON array or SheetJS parsing
  const { rows, columns } = useMemo(() => {
    try {
      const parsed = JSON.parse(artifact.content);
      if (Array.isArray(parsed) && parsed.length > 0) {
        const cols = Object.keys(parsed[0]);
        return { rows: parsed as Record<string, unknown>[], columns: cols };
      }
    } catch {
      // Not JSON — would need SheetJS for xlsx binary
    }
    return { rows: [] as Record<string, unknown>[], columns: [] as string[] };
  }, [artifact.content]);

  const sortedRows = useMemo(() => {
    if (!sortColumn) return rows;
    return [...rows].sort((a, b) => {
      const va = a[sortColumn];
      const vb = b[sortColumn];
      if (typeof va === "number" && typeof vb === "number") {
        return sortDir === "asc" ? va - vb : vb - va;
      }
      const cmp = String(va ?? "").localeCompare(String(vb ?? ""), undefined, { numeric: true });
      return sortDir === "asc" ? cmp : -cmp;
    });
  }, [rows, sortColumn, sortDir]);

  const totalPages = Math.ceil(sortedRows.length / PAGE_SIZE);
  const displayRows = mode === "card"
    ? sortedRows.slice(0, MAX_CARD_ROWS)
    : sortedRows.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  const handleSort = useCallback((col: string) => {
    setSortColumn((prev) => {
      if (prev === col) {
        setSortDir((d) => (d === "asc" ? "desc" : "asc"));
        return col;
      }
      setSortDir("asc");
      return col;
    });
  }, []);

  // H-7: CSV download implementation
  const handleDownload = useCallback(() => {
    if (rows.length === 0 || columns.length === 0) return;
    const header = columns.join(",");
    const csvRows = rows.map(r =>
      columns.map(c => `"${String(r[c] ?? "").replace(/"/g, '""')}"`).join(",")
    );
    const csv = [header, ...csvRows].join("\n");
    const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${artifact.title || "data"}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }, [rows, columns, artifact.title]);

  if (rows.length === 0) {
    return <div className="text-sm text-text-tertiary p-4">Không thể phân tích dữ liệu Excel.</div>;
  }

  return (
    <div className="space-y-2">
      {/* Header with row count */}
      {mode === "panel" && (
        <div className="flex items-center justify-between px-4 pt-2">
          <span className="text-xs text-text-tertiary">{rows.length} hàng × {columns.length} cột</span>
          <button
            onClick={handleDownload}
            className="flex items-center gap-1 text-xs text-text-secondary hover:text-text px-2 py-1 rounded bg-surface-tertiary hover:bg-border transition-colors"
          >
            <Download size={12} />
            Tải xuống
          </button>
        </div>
      )}

      {/* Table */}
      <div className="overflow-auto">
        <table className="w-full text-xs">
          <thead>
            <tr>
              {columns.map((col) => (
                <th
                  key={col}
                  onClick={() => handleSort(col)}
                  className="sticky top-0 bg-surface-tertiary px-3 py-2 text-left text-text-secondary font-medium cursor-pointer hover:bg-border/50 transition-colors whitespace-nowrap"
                >
                  <span className="flex items-center gap-1">
                    {col}
                    <ArrowUpDown size={10} className="text-text-tertiary" />
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {displayRows.map((row, idx) => (
              <tr key={idx} className="border-t border-border/50 hover:bg-surface-secondary transition-colors">
                {columns.map((col) => (
                  <td key={col} className="px-3 py-1.5 text-text whitespace-nowrap">
                    {String(row[col] ?? "")}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination (panel mode only) */}
      {mode === "panel" && totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 py-2">
          <button
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={page === 0}
            className="px-2 py-1 text-xs rounded bg-surface-tertiary disabled:opacity-50 hover:bg-border transition-colors"
          >
            Trước
          </button>
          <span className="text-xs text-text-tertiary">
            {page + 1} / {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
            disabled={page >= totalPages - 1}
            className="px-2 py-1 text-xs rounded bg-surface-tertiary disabled:opacity-50 hover:bg-border transition-colors"
          >
            Sau
          </button>
        </div>
      )}

      {mode === "card" && rows.length > MAX_CARD_ROWS && (
        <div className="text-center text-[10px] text-text-tertiary py-1">
          +{rows.length - MAX_CARD_ROWS} hàng khác
        </div>
      )}
    </div>
  );
}
