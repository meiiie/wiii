---
id: wiii-modern-charts
name: Modern Charts (Recharts)
skill_type: subagent
node: code_studio_agent
description: Recharts 3.x chart patterns for Wiii — chart selection guide, copy-pasteable JSX, Wiii design tokens, data format spec, and antipatterns.
version: "1.0.0"
---

# Modern Charts — Recharts 3.x for Wiii

Wiii desktop ships `recharts ^3.7.0` as a first-class dependency. When the runtime is React (desktop app, embedded widget, Sandpack preview), prefer Recharts over raw SVG or Chart.js CDN iframes.

This skill covers:
1. Which chart type fits which question
2. Complete JSX examples (copy-paste ready)
3. Wiii visual design tokens
4. Standard data format the LLM should produce
5. Antipatterns to avoid

---

## 1. Chart type selection guide

Pick the chart type based on what the user is trying to understand, not what looks fancy.

| Chart type | Best for | Example question |
|---|---|---|
| **RadarChart** | Multi-dimensional comparison of 2-3 entities across 5-8 axes | "So sanh kha nang cua hai loai tau" |
| **BarChart** (vertical) | Comparing discrete values across groups | "Doanh thu theo thang" |
| **BarChart** (horizontal) | Ranking, leaderboard, long category labels | "Xep hang 10 cang lon nhat" |
| **LineChart** | Trends over time, continuous change | "Gia dau thay doi the nao tu 2020?" |
| **PieChart / Donut** | Percentage breakdown of a whole (max 6-7 slices) | "Ty le loai hang hoa xuat khau" |
| **AreaChart** | Cumulative volume over time, stacked composition | "Luong hang qua cang theo nam" |

### Decision rules

- Fewer than 4 categories and showing parts of a whole -> Pie/Donut.
- More than 6 categories -> never Pie. Use Bar instead.
- Time on X axis -> Line or Area.
- Ranking or long labels -> Horizontal Bar.
- Multi-axis profile comparison -> Radar.
- When in doubt, use a simple BarChart. It is the most universally readable.

---

## 2. Recharts JSX examples

Every example below is a complete, self-contained React component. Import paths use the `recharts` package at `^3.7.0` already installed in `wiii-desktop`.

### 2a. RadarChart — multi-dimensional comparison

```tsx
import {
  RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  Radar, Legend, ResponsiveContainer, Tooltip,
} from "recharts";

const data = [
  { axis: "Toc do",      A: 85, B: 65 },
  { axis: "Tai trong",   A: 70, B: 90 },
  { axis: "An toan",     A: 92, B: 78 },
  { axis: "Nhien lieu",  A: 60, B: 82 },
  { axis: "Chi phi",     A: 75, B: 68 },
  { axis: "Do ben",      A: 88, B: 74 },
];

export function ShipComparisonRadar() {
  return (
    <ResponsiveContainer width="100%" aspect={1.2}>
      <RadarChart data={data} cx="50%" cy="50%" outerRadius="70%">
        <PolarGrid stroke="var(--border, #e5e7eb)" />
        <PolarAngleAxis dataKey="axis" tick={{ fontSize: 12, fill: "var(--text-secondary, #6b7280)" }} />
        <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fontSize: 10 }} />
        <Radar name="Tau A" dataKey="A" stroke="#D97757" fill="#D97757" fillOpacity={0.25} strokeWidth={2} />
        <Radar name="Tau B" dataKey="B" stroke="#38bdf8" fill="#38bdf8" fillOpacity={0.2} strokeWidth={2} />
        <Tooltip
          contentStyle={{ borderRadius: 10, background: "var(--bg-secondary, #fff8f0)", border: "1px solid var(--border, #e5e7eb)" }}
        />
        <Legend verticalAlign="bottom" iconType="circle" />
      </RadarChart>
    </ResponsiveContainer>
  );
}
```

### 2b. BarChart — grouped vertical bars

```tsx
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
} from "recharts";

const data = [
  { month: "T1", hanhtrinh: 120, hanhkhach: 85 },
  { month: "T2", hanhtrinh: 145, hanhkhach: 92 },
  { month: "T3", hanhtrinh: 130, hanhkhach: 110 },
  { month: "T4", hanhtrinh: 160, hanhkhach: 125 },
  { month: "T5", hanhtrinh: 175, hanhkhach: 140 },
];

export function MonthlyTrafficBar() {
  return (
    <ResponsiveContainer width="100%" aspect={1.8}>
      <BarChart data={data} barGap={4} barCategoryGap="20%">
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border, #e5e7eb)" vertical={false} />
        <XAxis dataKey="month" tick={{ fontSize: 12, fill: "var(--text-secondary, #6b7280)" }} />
        <YAxis tick={{ fontSize: 11 }} />
        <Tooltip
          contentStyle={{ borderRadius: 10, background: "var(--bg-secondary, #fff8f0)", border: "1px solid var(--border, #e5e7eb)" }}
        />
        <Legend verticalAlign="bottom" iconType="square" />
        <Bar dataKey="hanhtrinh" name="Hanh trinh" fill="#D97757" radius={[4, 4, 0, 0]} />
        <Bar dataKey="hanhkhach" name="Hanh khach" fill="#38bdf8" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
```

### 2c. Horizontal BarChart — ranking / leaderboard

```tsx
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer,
} from "recharts";

const data = [
  { name: "Cang Hai Phong",    value: 156 },
  { name: "Cang Sai Gon",     value: 142 },
  { name: "Cang Da Nang",     value: 98 },
  { name: "Cang Quy Nhon",    value: 76 },
  { name: "Cang Vung Tau",    value: 65 },
].sort((a, b) => a.value - b.value);

export function PortRanking() {
  return (
    <ResponsiveContainer width="100%" height={data.length * 48 + 40}>
      <BarChart data={data} layout="vertical" margin={{ left: 20 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border, #e5e7eb)" horizontal={false} />
        <XAxis type="number" tick={{ fontSize: 11 }} />
        <YAxis dataKey="name" type="category" width={120} tick={{ fontSize: 12, fill: "var(--text-secondary, #6b7280)" }} />
        <Tooltip
          contentStyle={{ borderRadius: 10, background: "var(--bg-secondary, #fff8f0)", border: "1px solid var(--border, #e5e7eb)" }}
        />
        <Bar dataKey="value" name="Luot tau" fill="#D97757" radius={[0, 6, 6, 0]} barSize={24} />
      </BarChart>
    </ResponsiveContainer>
  );
}
```

### 2d. LineChart — trends over time with multiple series

```tsx
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
} from "recharts";

const data = [
  { year: "2020", ron95: 18500, ron92: 17200 },
  { year: "2021", ron95: 21300, ron92: 19800 },
  { year: "2022", ron95: 28700, ron92: 26100 },
  { year: "2023", ron95: 24500, ron92: 22900 },
  { year: "2024", ron95: 23100, ron92: 21400 },
];

export function FuelPriceTrend() {
  return (
    <ResponsiveContainer width="100%" aspect={1.8}>
      <LineChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border, #e5e7eb)" />
        <XAxis dataKey="year" tick={{ fontSize: 12, fill: "var(--text-secondary, #6b7280)" }} />
        <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} />
        <Tooltip
          contentStyle={{ borderRadius: 10, background: "var(--bg-secondary, #fff8f0)", border: "1px solid var(--border, #e5e7eb)" }}
          formatter={(value: number) => [`${value.toLocaleString()} d/L`, undefined]}
        />
        <Legend verticalAlign="bottom" iconType="plainline" />
        <Line type="monotone" dataKey="ron95" name="RON 95" stroke="#D97757" strokeWidth={2.5} dot={{ r: 4 }} activeDot={{ r: 6 }} />
        <Line type="monotone" dataKey="ron92" name="RON 92" stroke="#38bdf8" strokeWidth={2} dot={{ r: 3.5 }} activeDot={{ r: 5.5 }} />
      </LineChart>
    </ResponsiveContainer>
  );
}
```

### 2e. PieChart — donut variant with percentage breakdown

```tsx
import {
  PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer,
} from "recharts";

const COLORS = ["#D97757", "#38bdf8", "#4ade80", "#fbbf24", "#a78bfa"];

const data = [
  { name: "Dau tho",       value: 38 },
  { name: "Container",     value: 27 },
  { name: "Hang roi",      value: 18 },
  { name: "Hang dong lanh", value: 11 },
  { name: "Khac",          value: 6 },
];

export function CargoBreakdownDonut() {
  return (
    <ResponsiveContainer width="100%" aspect={1.3}>
      <PieChart>
        <Pie
          data={data}
          cx="50%"
          cy="45%"
          innerRadius="45%"
          outerRadius="70%"
          paddingAngle={3}
          dataKey="value"
          nameKey="name"
          label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
          labelLine={{ stroke: "var(--text-secondary, #6b7280)", strokeWidth: 1 }}
        >
          {data.map((_, i) => (
            <Cell key={i} fill={COLORS[i % COLORS.length]} />
          ))}
        </Pie>
        <Tooltip
          contentStyle={{ borderRadius: 10, background: "var(--bg-secondary, #fff8f0)", border: "1px solid var(--border, #e5e7eb)" }}
          formatter={(value: number) => [`${value}%`, undefined]}
        />
        <Legend verticalAlign="bottom" iconType="circle" />
      </PieChart>
    </ResponsiveContainer>
  );
}
```

### 2f. AreaChart — cumulative volume over time

```tsx
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
} from "recharts";

const data = [
  { month: "T1", nhapkhau: 320, xuatkhau: 280 },
  { month: "T2", nhapkhau: 350, xuatkhau: 310 },
  { month: "T3", nhapkhau: 410, xuatkhau: 340 },
  { month: "T4", nhapkhau: 380, xuatkhau: 370 },
  { month: "T5", nhapkhau: 450, xuatkhau: 400 },
  { month: "T6", nhapkhau: 470, xuatkhau: 430 },
];

export function TradeVolumeArea() {
  return (
    <ResponsiveContainer width="100%" aspect={1.8}>
      <AreaChart data={data}>
        <defs>
          <linearGradient id="gradImport" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#D97757" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#D97757" stopOpacity={0.02} />
          </linearGradient>
          <linearGradient id="gradExport" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#4ade80" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#4ade80" stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border, #e5e7eb)" />
        <XAxis dataKey="month" tick={{ fontSize: 12, fill: "var(--text-secondary, #6b7280)" }} />
        <YAxis tick={{ fontSize: 11 }} />
        <Tooltip
          contentStyle={{ borderRadius: 10, background: "var(--bg-secondary, #fff8f0)", border: "1px solid var(--border, #e5e7eb)" }}
        />
        <Legend verticalAlign="bottom" iconType="plainline" />
        <Area type="monotone" dataKey="nhapkhau" name="Nhap khau" stroke="#D97757" fill="url(#gradImport)" strokeWidth={2} />
        <Area type="monotone" dataKey="xuatkhau" name="Xuat khau" stroke="#4ade80" fill="url(#gradExport)" strokeWidth={2} />
      </AreaChart>
    </ResponsiveContainer>
  );
}
```

---

## 3. Wiii design guidelines

### Color palette

Use warm, approachable tones. The Wiii brand is friendly and educational, not corporate.

| Role | Value | Usage |
|---|---|---|
| Primary | `#D97757` | First series, Wiii orange — the lead voice |
| Secondary | `#38bdf8` | Second series, sky blue contrast |
| Accent green | `#4ade80` | Third series, positive/growth |
| Accent amber | `#fbbf24` | Fourth series, warning/attention |
| Accent violet | `#a78bfa` | Fifth series, supplementary |

For 6+ series, loop back with lighter variants (`#f4a68a`, `#7dd3fc`, ...).

Never use random corporate blues, grays, or purple gradients as the dominant color.

### Typography and text

- Font: inherit from the host app via `var(--font-body)` or system default. Do not import Google Fonts.
- Axis labels: `fontSize: 11-12`, `fill: "var(--text-secondary, #6b7280)"`
- Tick labels: `fontSize: 10-11`
- Chart titles: rendered OUTSIDE the chart component as a normal heading element (`<h3>` or `<p>`), not via Recharts `plugins.title`. This keeps title styling consistent with the rest of the conversation.
- Titles should be conversational Vietnamese in Wiii voice. Example: "Luong hang qua cang nua dau 2025" instead of "BAO CAO THONG KE HANG HOA Q1-Q2/2025".

### Container styling

```css
.chart-container {
  width: 100%;
  border-radius: 12px;
  padding: 16px;
  background: var(--bg-secondary, #faf5ee);
}
```

- Border radius: 12-16px on the outer container.
- Never hardcode pixel width on `ResponsiveContainer`. Always use `width="100%"` and control height via `aspect` ratio or the parent container.
- Aspect ratios: 1.6-2.0 for wide charts (Line, Bar, Area), 1.0-1.3 for square charts (Radar, Pie).

### Tooltip

```tsx
<Tooltip
  contentStyle={{
    borderRadius: 10,
    background: "var(--bg-secondary, #fff8f0)",
    border: "1px solid var(--border, #e5e7eb)",
    fontSize: 12,
  }}
/>
```

Always provide a warm-toned tooltip background. Never leave the tooltip unstyled (Recharts default is stark white with a black border).

### Legend

- Position: `verticalAlign="bottom"` (consistent placement).
- Icon: `iconType="circle"` for Radar/Pie, `"square"` for Bar, `"plainline"` for Line/Area.
- Do not place legends on the right side — it wastes horizontal space on mobile.

### Grid

```tsx
<CartesianGrid strokeDasharray="3 3" stroke="var(--border, #e5e7eb)" vertical={false} />
```

- Dashed grid lines, light color.
- Prefer `vertical={false}` for Bar and Line charts (less clutter).
- For Radar charts, `PolarGrid` with light `stroke` is sufficient.

### Responsive behavior

- Always wrap in `<ResponsiveContainer width="100%" ...>`.
- Use `aspect` prop for predictable height (e.g., `aspect={1.8}`).
- For horizontal bar charts where height depends on item count, compute height: `height={data.length * 48 + 40}`.
- The chart must look correct at 320px through 1200px width.

---

## 4. Standard data format

When the LLM generates chart data (e.g., from `tool_generate_visual` or inline in a response), use this JSON structure:

```json
{
  "chart_type": "radar",
  "title": "Hai tau nay khac nhau o diem nao?",
  "data": [
    { "axis": "Toc do", "A": 85, "B": 65 },
    { "axis": "Tai trong", "A": 70, "B": 90 },
    { "axis": "An toan", "A": 92, "B": 78 }
  ],
  "series": [
    { "dataKey": "A", "name": "Tau Hoa Binh", "color": "#D97757" },
    { "dataKey": "B", "name": "Tau Thang Loi", "color": "#38bdf8" }
  ],
  "config": {
    "colors": ["#D97757", "#38bdf8", "#4ade80", "#fbbf24", "#a78bfa"],
    "showLegend": true,
    "showTooltip": true,
    "showGrid": true,
    "aspectRatio": 1.2
  }
}
```

### Field spec

| Field | Type | Required | Notes |
|---|---|---|---|
| `chart_type` | `"radar" \| "bar" \| "line" \| "pie" \| "area" \| "horizontal_bar"` | yes | Determines which Recharts component to use |
| `title` | `string` | yes | Conversational Vietnamese. No uppercase. No "bao cao" framing |
| `data` | `array<object>` | yes | Array of data points. Each object has a category key + one or more numeric value keys |
| `series` | `array<{ dataKey, name, color }>` | yes for multi-series | Maps value keys to display names and colors |
| `config.colors` | `string[]` | no | Override default palette. Falls back to Wiii palette |
| `config.showLegend` | `boolean` | no | Default `true` |
| `config.showTooltip` | `boolean` | no | Default `true` |
| `config.showGrid` | `boolean` | no | Default `true` |
| `config.aspectRatio` | `number` | no | Default varies by chart type |

### Per-type data shape

**Bar / Line / Area** — category key is the X axis:
```json
{ "data": [{ "month": "T1", "revenue": 120, "cost": 80 }] }
```

**Horizontal Bar** — same as Bar, renderer rotates via `layout="vertical"`:
```json
{ "data": [{ "name": "Cang Hai Phong", "value": 156 }] }
```

**Radar** — category key becomes `PolarAngleAxis`:
```json
{ "data": [{ "axis": "Speed", "A": 85, "B": 65 }] }
```

**Pie / Donut** — each item is a slice:
```json
{ "data": [{ "name": "Dau tho", "value": 38 }] }
```
Donut is the same as Pie with `innerRadius` set in config.

---

## 5. Antipatterns

### Deprecated structured primitives

Do NOT use these components for chart rendering:
- `DiagramNodeCard` — designed for flow diagrams, not data charts
- `DiagramFlowBridge` — connector arrows, not chart elements
- `DiagramLegend` — custom legend for structured visuals, conflicts with Recharts Legend

These exist in `visual-primitives` for the structured template fallback path. Charts should use native Recharts components.

### "Bao cao" corporate style

Do NOT produce output that looks like a government report:
- No uppercase section headers ("BAO CAO THONG KE", "SO SANH TRUC DIEN")
- No gray box backgrounds with dark borders
- No corporate blue/gray gradients
- No stiff formal Vietnamese in titles
- No stamp-like decorative borders

Charts should feel like a friend drawing a diagram to explain something, not a quarterly report.

### Chart.js CDN in iframe

Do NOT generate `<script src="https://cdn.jsdelivr.net/npm/chart.js">` inside an HTML string and render it in an iframe. Wiii desktop already has Recharts installed natively. Using Chart.js CDN:
- Adds network latency
- Breaks offline mode
- Creates a sandboxed iframe that cannot read host CSS variables
- Duplicates functionality

The only valid Chart.js path is the backend `chart_tools.py` fallback for non-React contexts (e.g., raw HTML widget lane). In the React desktop app, always use Recharts.

### Hardcoded pixel dimensions

Do NOT write:
```tsx
// BAD
<BarChart width={600} height={400}>
```

Always use:
```tsx
// GOOD
<ResponsiveContainer width="100%" aspect={1.8}>
  <BarChart>
```

Fixed pixel dimensions break on mobile, in the embed view, and when the sidebar is toggled.

### Pie chart overuse

Do NOT use PieChart for:
- More than 6-7 categories (becomes unreadable)
- Comparing values between groups (use Bar)
- Showing trends over time (use Line)
- Any case where "other" would be the largest slice

### Missing units and context

Do NOT produce charts without:
- Axis labels with units (VND, tan, chuyen, %)
- A title explaining what the chart shows
- A legend when there are multiple series

A chart without labels is just decoration.

### Over-animation

Do NOT add complex entry animations, spinning pie slices, or bouncing bars. Recharts has sensible built-in transitions. The `isAnimationActive` prop can be set to `false` if motion is distracting. Respect `prefers-reduced-motion`.

---

## 6. Integration notes

### Where charts render in Wiii

- **article_figure / chart_runtime path**: `tool_generate_visual` produces a `VisualPayload` with `presentation_intent: "chart_runtime"`. The frontend `VisualBlock.tsx` receives the payload and can render Recharts components natively using the structured `spec` data.
- **Code Studio path**: `tool_create_visual_code` produces full React/HTML artifacts. For chart widgets that need more interactivity (filters, toggles, drill-down), Code Studio is appropriate. Simple data charts should use the chart runtime path.
- **Admin panels**: `AnalyticsTab.tsx` and `KnowledgeScatter2D.tsx` already use Recharts directly in app code.

### Theme integration

Recharts does not natively read CSS variables. Pass them explicitly:

```tsx
const style = getComputedStyle(document.documentElement);
const borderColor = style.getPropertyValue("--border").trim() || "#e5e7eb";
```

Or use the hardcoded fallback values shown in the examples above. The `var(--token, fallback)` syntax works in inline style strings but not in Recharts props that expect plain strings. Use the fallback pattern: `"var(--border, #e5e7eb)"` where Recharts accepts style objects, and plain hex where it expects a raw color string.

### Accessibility

- Always include a visible title (as heading text, not just in the SVG).
- Include a `<p>` summary below the chart for screen readers.
- Use distinguishable colors (the Wiii palette passes WCAG contrast for chart fills on light backgrounds).
- Tooltips provide detail on hover/focus — ensure `Tooltip` is always present.
