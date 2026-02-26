/**
 * KnowledgeScatter3D — Sprint 191: "Mắt Tri Thức"
 *
 * Plotly 3D scatter showing embedding clusters with interactive rotation.
 * Lazy-loaded to avoid bundle bloat.
 */
import { lazy, Suspense, useCallback, useEffect, useState } from "react";
import { Loader2, AlertCircle } from "lucide-react";
import { getKnowledgeScatter } from "@/api/admin";
import type { ScatterResponse, ScatterDocument, ScatterPoint } from "@/api/types";

// Lazy-load Plotly (1.5MB gl3d-dist-min)
const Plot = lazy(async () => {
  const [plotlyMod, factoryMod] = await Promise.all([
    import("plotly.js-gl3d-dist-min" as string),
    import("react-plotly.js/factory" as string),
  ]);
  const Plotly = plotlyMod.default || plotlyMod;
  const createPlotlyComponent = factoryMod.default || factoryMod;
  const PlotComponent = createPlotlyComponent(Plotly);
  return { default: PlotComponent };
});

interface Props {
  orgId: string;
}

export function KnowledgeScatter3D({ orgId }: Props) {
  const [data, setData] = useState<ScatterResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [method, setMethod] = useState<"pca" | "tsne">("pca");
  const [limit, setLimit] = useState(500);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getKnowledgeScatter(orgId, { method, dimensions: 3, limit });
      setData(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Lỗi tải dữ liệu");
    } finally {
      setLoading(false);
    }
  }, [orgId, method, limit]);

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

  if (!data || data.points.length === 0) {
    return (
      <div className="text-center py-8 text-text-tertiary text-sm">
        Chưa có dữ liệu embedding. Tải lên tài liệu PDF trước.
      </div>
    );
  }

  // Group by document for traces
  const grouped = new Map<string, { doc: ScatterDocument; points: ScatterPoint[] }>();
  for (const doc of data.documents) {
    grouped.set(doc.id, { doc, points: [] });
  }
  for (const pt of data.points) {
    const entry = grouped.get(pt.document_id);
    if (entry) entry.points.push(pt);
  }

  const traces = Array.from(grouped.values()).map(({ doc, points }) => ({
    type: "scatter3d" as const,
    mode: "markers" as const,
    name: doc.name,
    x: points.map((p) => p.x),
    y: points.map((p) => p.y),
    z: points.map((p) => p.z ?? 0),
    text: points.map(
      (p) => `${p.document_name}${p.page_number != null ? ` (tr.${p.page_number})` : ""}\n${p.content_preview}`
    ),
    hoverinfo: "text" as const,
    marker: {
      size: 4,
      color: doc.color,
      opacity: 0.7,
    },
  }));

  const isDark = typeof document !== "undefined" && document.documentElement.classList.contains("dark");

  const layout = {
    autosize: true,
    height: 450,
    margin: { l: 0, r: 0, t: 30, b: 0 },
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    font: { color: isDark ? "#94a3b8" : "#475569", size: 10 },
    scene: {
      xaxis: { showgrid: true, gridcolor: isDark ? "#334155" : "#e2e8f0" },
      yaxis: { showgrid: true, gridcolor: isDark ? "#334155" : "#e2e8f0" },
      zaxis: { showgrid: true, gridcolor: isDark ? "#334155" : "#e2e8f0" },
    },
    legend: { font: { size: 10 } },
  };

  return (
    <div className="space-y-3">
      {/* Controls */}
      <div className="flex items-center gap-4 text-xs">
        <div className="flex items-center gap-2">
          <span className="text-text-secondary">Phương pháp:</span>
          <select
            value={method}
            onChange={(e) => setMethod(e.target.value as "pca" | "tsne")}
            className="rounded-lg border border-border bg-surface px-2 py-1 text-xs text-text"
          >
            <option value="pca">PCA</option>
            <option value="tsne">t-SNE</option>
          </select>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-text-secondary">Giới hạn:</span>
          <input
            type="range"
            min={100}
            max={1000}
            step={100}
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
            className="w-24"
          />
          <span className="text-text-tertiary w-8">{limit}</span>
        </div>
        <span className="text-text-tertiary ml-auto">
          {data.points.length} điểm | {data.computation_ms}ms | {data.method}
        </span>
      </div>

      {/* 3D Chart */}
      <div className="rounded-xl border border-border bg-surface p-4">
        <Suspense
          fallback={
            <div className="flex items-center justify-center py-12 text-text-secondary">
              <Loader2 size={20} className="animate-spin mr-2" />
              Đang tải thư viện 3D...
            </div>
          }
        >
          <Plot
            data={traces}
            layout={layout}
            config={{ responsive: true, displayModeBar: true, displaylogo: false }}
            style={{ width: "100%", height: 450 }}
          />
        </Suspense>
      </div>
    </div>
  );
}
