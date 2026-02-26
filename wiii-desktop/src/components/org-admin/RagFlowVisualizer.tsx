/**
 * RagFlowVisualizer — Sprint 191: "Mắt Tri Thức"
 *
 * RAG retrieval simulation: query input → pipeline steps → graded chunks.
 * Shows embed → retrieve → grade pipeline with timing.
 */
import { useState } from "react";
import { Search, Loader2, AlertCircle, Clock, CheckCircle2, MinusCircle, XCircle } from "lucide-react";
import { simulateRagFlow } from "@/api/admin";
import type { RagFlowResponse, RagFlowChunk } from "@/api/types";

const GRADE_CONFIG: Record<string, { label: string; color: string; bg: string; icon: React.ReactNode }> = {
  relevant: {
    label: "Liên quan",
    color: "text-green-700 dark:text-green-400",
    bg: "bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800",
    icon: <CheckCircle2 size={14} className="text-green-500" />,
  },
  partial: {
    label: "Một phần",
    color: "text-amber-700 dark:text-amber-400",
    bg: "bg-amber-50 dark:bg-amber-900/20 border-amber-200 dark:border-amber-800",
    icon: <MinusCircle size={14} className="text-amber-500" />,
  },
  irrelevant: {
    label: "Không liên quan",
    color: "text-red-700 dark:text-red-400",
    bg: "bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800",
    icon: <XCircle size={14} className="text-red-500" />,
  },
};

interface Props {
  orgId: string;
}

export function RagFlowVisualizer({ orgId }: Props) {
  const [query, setQuery] = useState("");
  const [topK, setTopK] = useState(10);
  const [data, setData] = useState<RagFlowResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    setError(null);
    try {
      const res = await simulateRagFlow(orgId, query.trim(), topK);
      setData(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Lỗi mô phỏng");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Query input */}
      <form onSubmit={handleSubmit} className="flex items-end gap-3">
        <div className="flex-1">
          <label className="text-xs text-text-secondary mb-1 block">Câu hỏi thử nghiệm</label>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Nhập câu hỏi để mô phỏng RAG..."
            className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text placeholder:text-text-tertiary focus:border-[var(--accent)] focus:outline-none"
            maxLength={1000}
          />
        </div>
        <div className="flex items-center gap-2">
          <label className="text-xs text-text-secondary">Top K:</label>
          <select
            value={topK}
            onChange={(e) => setTopK(Number(e.target.value))}
            className="rounded-lg border border-border bg-surface px-2 py-2 text-xs text-text"
          >
            {[5, 10, 15, 20].map((k) => (
              <option key={k} value={k}>{k}</option>
            ))}
          </select>
        </div>
        <button
          type="submit"
          disabled={loading || !query.trim()}
          className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-4 py-2 text-xs font-medium text-white hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? <Loader2 size={14} className="animate-spin" /> : <Search size={14} />}
          Thử nghiệm
        </button>
      </form>

      {error && (
        <div className="flex items-center gap-2 text-red-500 text-sm">
          <AlertCircle size={16} />
          {error}
        </div>
      )}

      {data && (
        <>
          {/* Pipeline steps */}
          <div className="rounded-xl border border-border bg-surface p-4">
            <h4 className="text-xs font-medium text-text-secondary mb-3">Pipeline ({data.computation_ms}ms)</h4>
            <div className="flex items-center gap-2">
              {data.steps.map((step, i) => (
                <div key={step.name} className="flex items-center gap-2">
                  {i > 0 && <span className="text-text-tertiary">→</span>}
                  <div className="rounded-lg border border-border bg-surface-secondary px-3 py-1.5">
                    <p className="text-xs font-medium text-text">{step.name}</p>
                    <div className="flex items-center gap-1 mt-0.5">
                      <Clock size={10} className="text-text-tertiary" />
                      <span className="text-xs text-text-tertiary">{step.duration_ms}ms</span>
                    </div>
                    {step.detail && (
                      <p className="text-xs text-text-tertiary mt-0.5">{step.detail}</p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Chunk cards */}
          <div className="space-y-2">
            <h4 className="text-xs font-medium text-text-secondary">
              Kết quả ({data.chunks.length} chunk)
            </h4>
            {data.chunks.length === 0 ? (
              <p className="text-xs text-text-tertiary text-center py-4">
                Không tìm thấy kết quả.
              </p>
            ) : (
              data.chunks.map((chunk) => (
                <ChunkCard key={chunk.chunk_id} chunk={chunk} />
              ))
            )}
          </div>
        </>
      )}
    </div>
  );
}

function ChunkCard({ chunk }: { chunk: RagFlowChunk }) {
  const cfg = GRADE_CONFIG[chunk.grade] || GRADE_CONFIG.irrelevant;
  const simPercent = Math.round(chunk.similarity * 100);

  return (
    <div className={`rounded-xl border p-3 ${cfg.bg}`}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-medium text-text truncate">{chunk.document_name}</span>
            {chunk.page_number != null && (
              <span className="text-xs text-text-tertiary">tr.{chunk.page_number}</span>
            )}
          </div>
          <p className="text-xs text-text-secondary line-clamp-3">{chunk.content_preview}</p>
        </div>
        <div className="flex flex-col items-end gap-1 flex-shrink-0">
          <div className="flex items-center gap-1">
            {cfg.icon}
            <span className={`text-xs font-medium ${cfg.color}`}>{cfg.label}</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-16 h-1.5 rounded-full bg-gray-200 dark:bg-gray-700 overflow-hidden">
              <div
                className={`h-full rounded-full ${
                  chunk.grade === "relevant" ? "bg-green-500" :
                  chunk.grade === "partial" ? "bg-amber-500" : "bg-red-500"
                }`}
                style={{ width: `${simPercent}%` }}
              />
            </div>
            <span className="text-xs text-text-tertiary w-8 text-right">{simPercent}%</span>
          </div>
        </div>
      </div>
    </div>
  );
}
