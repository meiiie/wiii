/**
 * KnowledgeGraph — Sprint 191: "Mắt Tri Thức"
 *
 * Knowledge graph visualization using Mermaid diagrams.
 * Shows document→chunk relationships and cross-doc similarity.
 */
import { useCallback, useEffect, useState } from "react";
import { Loader2, AlertCircle, FileText, Link2 } from "lucide-react";
import MermaidDiagram from "@/components/common/MermaidDiagram";
import { getKnowledgeGraph } from "@/api/admin";
import type { KnowledgeGraphResponse } from "@/api/types";

interface Props {
  orgId: string;
}

export function KnowledgeGraph({ orgId }: Props) {
  const [data, setData] = useState<KnowledgeGraphResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [maxNodes, setMaxNodes] = useState(50);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getKnowledgeGraph(orgId, { max_nodes: maxNodes });
      setData(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Lỗi tải dữ liệu");
    } finally {
      setLoading(false);
    }
  }, [orgId, maxNodes]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12 text-text-secondary">
        <Loader2 size={20} className="animate-spin mr-2" />
        Đang tính toán...
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center gap-2 py-8 justify-center text-red-500 text-sm">
        <AlertCircle size={16} />
        {error}
      </div>
    );
  }

  if (!data || data.nodes.length === 0) {
    return (
      <div className="text-center py-8 text-text-tertiary text-sm">
        Chưa có dữ liệu để xây dựng đồ thị. Tải lên tài liệu PDF trước.
      </div>
    );
  }

  const docCount = data.nodes.filter((n) => n.node_type === "document").length;
  const chunkCount = data.nodes.filter((n) => n.node_type === "chunk").length;
  const containsEdges = data.edges.filter((e) => e.edge_type === "contains").length;
  const similarEdges = data.edges.filter((e) => e.edge_type === "similar_to").length;

  return (
    <div className="space-y-3">
      {/* Controls */}
      <div className="flex items-center gap-4 text-xs">
        <div className="flex items-center gap-2">
          <span className="text-text-secondary">Max nodes:</span>
          <input
            type="range"
            min={10}
            max={100}
            step={10}
            value={maxNodes}
            onChange={(e) => setMaxNodes(Number(e.target.value))}
            className="w-24"
          />
          <span className="text-text-tertiary w-8">{maxNodes}</span>
        </div>
        <span className="text-text-tertiary ml-auto">{data.computation_ms}ms</span>
      </div>

      {/* Stats bar */}
      <div className="flex items-center gap-4 text-xs">
        <span className="inline-flex items-center gap-1 text-blue-600 dark:text-blue-400">
          <FileText size={12} />
          {docCount} tài liệu
        </span>
        <span className="inline-flex items-center gap-1 text-amber-600 dark:text-amber-400">
          <FileText size={12} />
          {chunkCount} chunk
        </span>
        <span className="inline-flex items-center gap-1 text-text-secondary">
          <Link2 size={12} />
          {containsEdges} chứa
        </span>
        {similarEdges > 0 && (
          <span className="inline-flex items-center gap-1 text-violet-600 dark:text-violet-400">
            <Link2 size={12} />
            {similarEdges} tương tự
          </span>
        )}
      </div>

      {/* Mermaid diagram */}
      <div className="rounded-xl border border-border bg-surface p-4 overflow-x-auto">
        <MermaidDiagram code={data.mermaid_code} />
      </div>
    </div>
  );
}
