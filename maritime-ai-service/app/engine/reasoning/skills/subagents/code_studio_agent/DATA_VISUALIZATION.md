---
id: wiii-data-visualization
name: Data Visualization
skill_type: subagent
node: code_studio_agent
description: Patterns cho data viz bằng SVG thuần — bar chart, pie chart, line chart, radar, heatmap. Không cần thư viện ngoài.
version: "1.0.0"
---

# Data Visualization Skill

Data viz bằng SVG thuần — nhẹ, responsive, dark mode tự động.

## Bar Chart (SVG)

```html
<style>
.bar-chart text{font-size:11px;fill:var(--text2)}
.bar-rect{transition:opacity .15s}
.bar-rect:hover{opacity:0.75}
</style>
<svg class="bar-chart" viewBox="0 0 500 280" style="width:100%;height:auto">
  <!-- Y-axis labels -->
  <text x="35" y="30" text-anchor="end">100</text>
  <text x="35" y="130" text-anchor="end">50</text>
  <text x="35" y="230" text-anchor="end">0</text>
  <!-- Grid lines -->
  <line x1="45" y1="25" x2="480" y2="25" stroke="var(--bg3)" stroke-width="1"/>
  <line x1="45" y1="125" x2="480" y2="125" stroke="var(--bg3)" stroke-width="1"/>
  <line x1="45" y1="225" x2="480" y2="225" stroke="var(--border)" stroke-width="1"/>

  <!-- Bars — height = value * 2, y = 225 - height -->
  <rect class="bar-rect" x="70" y="65" width="50" height="160" rx="4"
    fill="var(--accent)" opacity="0.8"/>
  <text x="95" y="245" text-anchor="middle" font-size="11">Label 1</text>
  <text x="95" y="58" text-anchor="middle" font-size="11" fill="var(--accent)" font-weight="600">80</text>

  <!-- Thêm bars tương tự, x += 85 mỗi bar -->
</svg>
```

**Tính toán**: barWidth=50, gap=35, startX=70.
`x = startX + index * (barWidth + gap)`
`barHeight = (value / maxValue) * 200`
`y = 225 - barHeight`

## Pie Chart (SVG)

```html
<style>
.pie-slice{transition:transform .15s;transform-origin:200px 150px}
.pie-slice:hover{transform:scale(1.05)}
.pie-label{font-size:11px;fill:var(--text2)}
.pie-value{font-size:13px;font-weight:700}
</style>
<svg viewBox="0 0 400 300" style="width:100%;height:auto">
  <!-- Pie slices — dùng arc path -->
  <!-- Slice: M cx,cy L startX,startY A r,r 0 largeArc,1 endX,endY Z -->

  <!-- Legend bên phải -->
  <rect x="250" y="60" width="12" height="12" rx="2" fill="var(--accent)"/>
  <text x="268" y="71" class="pie-label">Category A (45%)</text>
</svg>
```

**Công thức arc**:
```
startAngle = cumulative / total * 2π
endAngle = (cumulative + value) / total * 2π
startX = cx + r * cos(startAngle - π/2)
startY = cy + r * sin(startAngle - π/2)
endX = cx + r * cos(endAngle - π/2)
endY = cy + r * sin(endAngle - π/2)
largeArc = (endAngle - startAngle > π) ? 1 : 0
```

## Line Chart (SVG + CSS animation)

```html
<style>
.line-path{fill:none;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
.line-dot{transition:r .15s}
.line-dot:hover{r:6}
.area-fill{opacity:0.08}
</style>
<svg viewBox="0 0 500 250" style="width:100%;height:auto">
  <!-- Grid -->
  <line x1="50" y1="200" x2="470" y2="200" stroke="var(--border)" stroke-width="1"/>

  <!-- Area fill -->
  <path class="area-fill" d="M70,60 L150,100 L230,80 L310,140 L390,90 L470,120 L470,200 L70,200Z"
    fill="var(--accent)"/>

  <!-- Line -->
  <path class="line-path" d="M70,60 L150,100 L230,80 L310,140 L390,90 L470,120"
    stroke="var(--accent)"/>

  <!-- Data points -->
  <circle class="line-dot" cx="70" cy="60" r="4" fill="var(--accent)"/>
  <!-- Thêm dots tương tự -->

  <!-- X labels -->
  <text x="70" y="218" text-anchor="middle" font-size="10" fill="var(--text3)">T1</text>
</svg>
```

## Radar Chart (SVG)

```html
<svg viewBox="0 0 300 300" style="width:100%;height:auto">
  <!-- Background rings -->
  <polygon points="..." fill="none" stroke="var(--bg3)" stroke-width="1"/>
  <!-- Axis lines -->
  <line x1="150" y1="150" x2="150" y2="30" stroke="var(--bg3)" stroke-width="1"/>
  <!-- Data polygon -->
  <polygon points="..." fill="var(--accent)" opacity="0.15"
    stroke="var(--accent)" stroke-width="2"/>
  <!-- Data points -->
  <circle cx="X" cy="Y" r="4" fill="var(--accent)"/>
  <!-- Labels -->
  <text x="150" y="20" text-anchor="middle" font-size="11" fill="var(--text2)">Axis 1</text>
</svg>
```

**Công thức tọa độ radar**:
```
angle = index * (2π / numAxes) - π/2
x = cx + radius * value/maxValue * cos(angle)
y = cy + radius * value/maxValue * sin(angle)
```

## Heatmap (HTML Grid)

```html
<style>
.hm{display:grid;gap:2px}
.hm-cell{aspect-ratio:1;border-radius:4px;display:flex;align-items:center;
  justify-content:center;font-size:11px;font-weight:500;transition:transform .1s}
.hm-cell:hover{transform:scale(1.1);z-index:1}
.hm-label{font-size:11px;color:var(--text3);text-align:center;padding:4px}
</style>
```

**Màu heatmap**: dùng `opacity` trên một màu base:
- Low: `background: color-mix(in srgb, var(--accent) 10%, var(--bg2))`
- Mid: `background: color-mix(in srgb, var(--accent) 50%, var(--bg2))`
- High: `background: var(--accent); color: white`

## Nguyên tắc

1. LUÔN có grid lines nhẹ (`var(--bg3)`)
2. LUÔN có labels cho axes
3. Hover effect cho mọi data point
4. Responsive viewBox — không hardcode pixel
5. Số liệu hiện trên chart (value labels) — không chỉ tooltip
6. Dùng `color-mix()` cho opacity variation trên CSS vars
