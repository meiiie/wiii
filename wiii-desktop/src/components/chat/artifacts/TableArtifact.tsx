/**
 * TableArtifact — renders JSON data as a sortable HTML table.
 * Sprint 167: "Không Gian Sáng Tạo"
 */
import { useState, useMemo } from "react";
import { ArrowUpDown } from "lucide-react";
import type { ArtifactData } from "@/api/types";

interface Props {
  artifact: ArtifactData;
  mode: "card" | "panel";
}

const MAX_CARD_ROWS = 5;

export default function TableArtifact({ artifact, mode }: Props) {
  const [sortColumn, setSortColumn] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");

  // Parse JSON content into rows
  const rows = useMemo<Record<string, unknown>[]>(() => {
    try {
      const parsed = JSON.parse(artifact.content);
      if (Array.isArray(parsed)) return parsed;
      if (artifact.metadata?.table_data && Array.isArray(artifact.metadata.table_data)) {
        return artifact.metadata.table_data as Record<string, unknown>[];
      }
      return [];
    } catch {
      return [];
    }
  }, [artifact.content, artifact.metadata?.table_data]);

  const columns = useMemo(() => {
    if (rows.length === 0) return [];
    return Object.keys(rows[0]);
  }, [rows]);

  // Sort rows
  const sortedRows = useMemo(() => {
    if (!sortColumn) return rows;
    return [...rows].sort((a, b) => {
      const va = a[sortColumn];
      const vb = b[sortColumn];
      const cmp = String(va ?? "").localeCompare(String(vb ?? ""), undefined, { numeric: true });
      return sortDir === "asc" ? cmp : -cmp;
    });
  }, [rows, sortColumn, sortDir]);

  const displayRows = mode === "card" ? sortedRows.slice(0, MAX_CARD_ROWS) : sortedRows;

  const handleSort = (col: string) => {
    if (sortColumn === col) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortColumn(col);
      setSortDir("asc");
    }
  };

  if (rows.length === 0) {
    return <div className="text-sm text-text-tertiary p-4">Không có dữ liệu bảng.</div>;
  }

  return (
    <div className={mode === "card" ? "overflow-auto max-h-[200px]" : "overflow-auto"}>
      <table className="w-full text-xs">
        <thead>
          <tr>
            {columns.map((col) => (
              <th
                key={col}
                onClick={() => handleSort(col)}
                className="sticky top-0 bg-surface-tertiary px-3 py-2 text-left text-text-secondary font-medium cursor-pointer hover:bg-border/50 transition-colors"
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
                <td key={col} className="px-3 py-1.5 text-text">
                  {String(row[col] ?? "")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {mode === "card" && rows.length > MAX_CARD_ROWS && (
        <div className="text-center text-[10px] text-text-tertiary py-1">
          +{rows.length - MAX_CARD_ROWS} hàng khác
        </div>
      )}
    </div>
  );
}
