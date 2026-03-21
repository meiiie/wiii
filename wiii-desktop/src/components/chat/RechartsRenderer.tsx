/**
 * RechartsRenderer — renders chart specs using Recharts.
 *
 * Receives a `spec` with `chart_type`, `title`, `data`, `series`, and optional `config`.
 * Supports: radar, bar, horizontal_bar, line, pie, donut, area.
 * Falls back to bar chart for unknown types and to text for malformed data.
 */

import { useMemo } from "react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  LineChart,
  Line,
  AreaChart,
  Area,
  PieChart,
  Pie,
  Cell,
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from "recharts";

// Wiii warm palette
const PALETTE = ["#D97757", "#38bdf8", "#4ade80", "#fbbf24", "#a78bfa", "#f87171"];
const colorAt = (i: number) => PALETTE[i % PALETTE.length];

// ---------- helpers ----------

interface SeriesEntry {
  dataKey: string;
  name?: string;
  color?: string;
}

interface ChartSpec {
  chart_type?: string;
  title?: string;
  data?: unknown[];
  series?: SeriesEntry[];
  config?: Record<string, unknown>;
}

function safeData(raw: unknown): Record<string, unknown>[] {
  if (!Array.isArray(raw)) return [];
  return raw
    .filter((item): item is Record<string, unknown> => item !== null && typeof item === "object" && !Array.isArray(item))
    .slice(0, 200); // cap for safety
}

function inferSeries(data: Record<string, unknown>[], explicit?: SeriesEntry[]): SeriesEntry[] {
  if (Array.isArray(explicit) && explicit.length > 0) {
    return explicit.map((s, i) => ({
      dataKey: String(s.dataKey || s.name || `series_${i}`),
      name: String(s.name || s.dataKey || `Series ${i + 1}`),
      color: typeof s.color === "string" ? s.color : colorAt(i),
    }));
  }
  // auto-detect numeric keys (skip "name", "label", "category")
  if (data.length === 0) return [];
  const skip = new Set(["name", "label", "category", "group", "id"]);
  const keys = Object.keys(data[0]).filter(
    (k) => !skip.has(k.toLowerCase()) && typeof data[0][k] === "number",
  );
  return keys.map((k, i) => ({ dataKey: k, name: k, color: colorAt(i) }));
}

function categoryKey(data: Record<string, unknown>[]): string {
  if (data.length === 0) return "name";
  for (const k of ["name", "label", "category", "group"]) {
    if (k in data[0]) return k;
  }
  return Object.keys(data[0])[0] || "name";
}

const tooltipStyle = {
  contentStyle: {
    borderRadius: 12,
    border: "1px solid rgba(0,0,0,0.08)",
    boxShadow: "0 2px 8px rgba(0,0,0,0.08)",
    fontSize: 13,
  },
};

// ---------- sub-views ----------

function RadarChartView({ data, series, catKey }: { data: Record<string, unknown>[]; series: SeriesEntry[]; catKey: string }) {
  return (
    <ResponsiveContainer width="100%" height={320}>
      <RadarChart data={data} outerRadius="75%">
        <PolarGrid stroke="rgba(0,0,0,0.08)" />
        <PolarAngleAxis dataKey={catKey} tick={{ fontSize: 12, fill: "#6b7280" }} />
        <PolarRadiusAxis tick={{ fontSize: 10, fill: "#9ca3af" }} />
        {series.map((s, i) => (
          <Radar
            key={s.dataKey}
            name={s.name || s.dataKey}
            dataKey={s.dataKey}
            stroke={s.color || colorAt(i)}
            fill={s.color || colorAt(i)}
            fillOpacity={0.25}
          />
        ))}
        <Tooltip {...tooltipStyle} />
        <Legend verticalAlign="bottom" iconType="circle" wrapperStyle={{ fontSize: 13, paddingTop: 8 }} />
      </RadarChart>
    </ResponsiveContainer>
  );
}

function BarChartView({ data, series, catKey, layout }: { data: Record<string, unknown>[]; series: SeriesEntry[]; catKey: string; layout?: "horizontal" | "vertical" }) {
  const isVertical = layout === "vertical";
  return (
    <ResponsiveContainer width="100%" height={Math.max(300, isVertical ? data.length * 40 + 60 : 300)}>
      <BarChart data={data} layout={isVertical ? "vertical" : "horizontal"} margin={{ left: isVertical ? 20 : 0, right: 12 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
        {isVertical ? (
          <>
            <XAxis type="number" tick={{ fontSize: 12, fill: "#6b7280" }} />
            <YAxis dataKey={catKey} type="category" width={100} tick={{ fontSize: 12, fill: "#6b7280" }} />
          </>
        ) : (
          <>
            <XAxis dataKey={catKey} tick={{ fontSize: 12, fill: "#6b7280" }} />
            <YAxis tick={{ fontSize: 12, fill: "#6b7280" }} />
          </>
        )}
        <Tooltip {...tooltipStyle} />
        <Legend verticalAlign="bottom" iconType="square" wrapperStyle={{ fontSize: 13, paddingTop: 8 }} />
        {series.map((s, i) => (
          <Bar
            key={s.dataKey}
            dataKey={s.dataKey}
            name={s.name || s.dataKey}
            fill={s.color || colorAt(i)}
            radius={[4, 4, 0, 0]}
            maxBarSize={48}
          />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}

function LineChartView({ data, series, catKey }: { data: Record<string, unknown>[]; series: SeriesEntry[]; catKey: string }) {
  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
        <XAxis dataKey={catKey} tick={{ fontSize: 12, fill: "#6b7280" }} />
        <YAxis tick={{ fontSize: 12, fill: "#6b7280" }} />
        <Tooltip {...tooltipStyle} />
        <Legend verticalAlign="bottom" iconType="line" wrapperStyle={{ fontSize: 13, paddingTop: 8 }} />
        {series.map((s, i) => (
          <Line
            key={s.dataKey}
            type="monotone"
            dataKey={s.dataKey}
            name={s.name || s.dataKey}
            stroke={s.color || colorAt(i)}
            strokeWidth={2}
            dot={{ r: 3, fill: s.color || colorAt(i) }}
            activeDot={{ r: 5 }}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

function AreaChartView({ data, series, catKey }: { data: Record<string, unknown>[]; series: SeriesEntry[]; catKey: string }) {
  return (
    <ResponsiveContainer width="100%" height={300}>
      <AreaChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
        <XAxis dataKey={catKey} tick={{ fontSize: 12, fill: "#6b7280" }} />
        <YAxis tick={{ fontSize: 12, fill: "#6b7280" }} />
        <Tooltip {...tooltipStyle} />
        <Legend verticalAlign="bottom" iconType="square" wrapperStyle={{ fontSize: 13, paddingTop: 8 }} />
        {series.map((s, i) => (
          <Area
            key={s.dataKey}
            type="monotone"
            dataKey={s.dataKey}
            name={s.name || s.dataKey}
            stroke={s.color || colorAt(i)}
            fill={s.color || colorAt(i)}
            fillOpacity={0.18}
            strokeWidth={2}
          />
        ))}
      </AreaChart>
    </ResponsiveContainer>
  );
}

function PieChartView({ data, series, catKey, donut }: { data: Record<string, unknown>[]; series: SeriesEntry[]; catKey: string; donut?: boolean }) {
  const valueKey = series[0]?.dataKey || "value";
  return (
    <ResponsiveContainer width="100%" height={320}>
      <PieChart>
        <Pie
          data={data}
          dataKey={valueKey}
          nameKey={catKey}
          cx="50%"
          cy="50%"
          outerRadius={110}
          innerRadius={donut ? 60 : 0}
          paddingAngle={2}
          label={({ name, percent }: { name?: string; percent?: number }) => `${name ?? ""}: ${((percent ?? 0) * 100).toFixed(0)}%`}
          labelLine={{ stroke: "#9ca3af", strokeWidth: 1 }}
        >
          {data.map((_entry, i) => (
            <Cell key={`cell-${i}`} fill={colorAt(i)} />
          ))}
        </Pie>
        <Tooltip {...tooltipStyle} />
        <Legend verticalAlign="bottom" iconType="circle" wrapperStyle={{ fontSize: 13, paddingTop: 8 }} />
      </PieChart>
    </ResponsiveContainer>
  );
}

// ---------- main component ----------

export function RechartsRenderer({ spec }: { spec: Record<string, unknown> }) {
  const chartSpec = spec as unknown as ChartSpec;
  const chartType = String(chartSpec.chart_type || "bar").toLowerCase();
  const title = typeof chartSpec.title === "string" ? chartSpec.title : "";

  const data = useMemo(() => safeData(chartSpec.data), [chartSpec.data]);
  const series = useMemo(
    () => inferSeries(data, chartSpec.series as SeriesEntry[] | undefined),
    [data, chartSpec.series],
  );
  const catKey = useMemo(() => categoryKey(data), [data]);

  // graceful fallback for empty / malformed data
  if (data.length === 0 || series.length === 0) {
    return (
      <div className="rounded-2xl border border-[var(--border)] bg-white/80 px-5 py-6 text-sm text-text-secondary">
        {title && <p className="mb-2 font-semibold text-text">{title}</p>}
        <p>Không đủ dữ liệu để vẽ biểu đồ.</p>
      </div>
    );
  }

  let chart: React.ReactNode;
  switch (chartType) {
    case "radar":
      chart = <RadarChartView data={data} series={series} catKey={catKey} />;
      break;
    case "horizontal_bar":
      chart = <BarChartView data={data} series={series} catKey={catKey} layout="vertical" />;
      break;
    case "line":
      chart = <LineChartView data={data} series={series} catKey={catKey} />;
      break;
    case "area":
      chart = <AreaChartView data={data} series={series} catKey={catKey} />;
      break;
    case "pie":
      chart = <PieChartView data={data} series={series} catKey={catKey} />;
      break;
    case "donut":
      chart = <PieChartView data={data} series={series} catKey={catKey} donut />;
      break;
    case "bar":
    default:
      chart = <BarChartView data={data} series={series} catKey={catKey} />;
      break;
  }

  return (
    <div className="recharts-renderer space-y-3">
      {title && (
        <p className="text-sm font-semibold text-text">{title}</p>
      )}
      {chart}
    </div>
  );
}
