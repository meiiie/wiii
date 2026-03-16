---
id: wiii-svg-diagram
name: SVG Diagram
skill_type: subagent
node: code_studio_agent
description: Patterns cho sơ đồ SVG tĩnh và tương tác — architecture, flowchart, mind map, comparison, timeline. Hover effects, gradients, arrows.
version: "1.0.0"
---

# SVG Diagram Skill

Sơ đồ SVG là visual giải thích chính — kiến trúc hệ thống, quy trình, so sánh, timeline.

## Nguyên tắc SVG

1. **Responsive**: `viewBox` + `width="100%"` + `height="auto"`
2. **Màu**: LUÔN dùng CSS vars — `fill="var(--accent)"`, `stroke="var(--border)"`
3. **Text**: `font-family: inherit`, `text-anchor="middle"` cho center
4. **Hover**: CSS `.layer:hover { opacity: 0.85 }` hoặc `transform: translateY(-2px)`
5. **Arrow markers**: Dùng `<defs><marker>` cho mũi tên

## Arrow Marker Template

```html
<defs>
  <marker id="arr" viewBox="0 0 10 10" refX="9" refY="5"
    markerWidth="6" markerHeight="6" orient="auto">
    <path d="M0,0L10,5L0,10Z" fill="var(--text3)"/>
  </marker>
</defs>
```

## Pattern: Layered Architecture

```html
<style>
.layer{transition:opacity .15s;cursor:default}
.layer:hover{opacity:0.85}
.layer-title{font-size:13px;font-weight:700}
.layer-desc{font-size:11px}
.pill{font-size:10px}
</style>
<svg viewBox="0 0 600 DYNAMIC_HEIGHT" style="width:100%;height:auto">
  <defs><!-- arrow marker --></defs>
  <!-- Mỗi layer: rect + title + description + component pills -->
  <g class="layer">
    <rect x="40" y="Y" width="520" height="90" rx="12"
      fill="var(--COLOR)" opacity="0.08" stroke="var(--COLOR)" stroke-width="1.5"/>
    <text x="300" y="Y+28" text-anchor="middle" class="layer-title"
      fill="var(--COLOR)">LAYER NAME</text>
    <text x="300" y="Y+48" text-anchor="middle" class="layer-desc"
      fill="var(--text2)">Mô tả chi tiết layer</text>
    <!-- Component pills -->
    <rect x="X" y="Y+60" width="W" height="20" rx="4"
      fill="var(--COLOR)" opacity="0.12"/>
    <text x="X+W/2" y="Y+74" text-anchor="middle" class="pill"
      fill="var(--COLOR)">Component</text>
  </g>
  <!-- Arrow between layers -->
  <line x1="300" y1="Y1" x2="300" y2="Y2"
    stroke="var(--text3)" stroke-width="1.5" marker-end="url(#arr)"/>
</svg>
```

**Tính DYNAMIC_HEIGHT**: Mỗi layer cao 90px + arrow gap 30px.
3 layers = 90*3 + 30*2 = 330px.

## Pattern: Horizontal Flow

```html
<style>
.flow-node{transition:transform .15s}
.flow-node:hover{transform:translateY(-3px)}
</style>
<svg viewBox="0 0 DYNAMIC_WIDTH 120" style="width:100%;height:auto">
  <!-- Mỗi node: rounded rect + text -->
  <g class="flow-node">
    <rect x="X" y="20" width="120" height="70" rx="12"
      fill="var(--COLOR)" opacity="0.08" stroke="var(--COLOR)" stroke-width="1.5"/>
    <text x="X+60" y="50" text-anchor="middle" font-size="13" font-weight="700"
      fill="var(--COLOR)">Node Name</text>
    <text x="X+60" y="68" text-anchor="middle" font-size="10"
      fill="var(--text2)">Description</text>
  </g>
  <!-- Arrow -->
  <line x1="X1+120" y1="55" x2="X2" y2="55"
    stroke="var(--text3)" stroke-width="1.5" marker-end="url(#arr)"/>
</svg>
```

## Pattern: Mind Map / Concept

```html
<svg viewBox="0 0 600 400" style="width:100%;height:auto">
  <!-- Center node -->
  <circle cx="300" cy="200" r="50" fill="var(--accent)" opacity="0.1"
    stroke="var(--accent)" stroke-width="2"/>
  <text x="300" y="205" text-anchor="middle" font-size="14" font-weight="700"
    fill="var(--accent)">Khái niệm chính</text>

  <!-- Branch lines (curved) -->
  <path d="M350,200 Q400,150 450,130" fill="none"
    stroke="var(--green)" stroke-width="1.5"/>

  <!-- Branch nodes -->
  <rect x="420" y="110" width="140" height="40" rx="8"
    fill="var(--green)" opacity="0.08" stroke="var(--green)" stroke-width="1"/>
  <text x="490" y="135" text-anchor="middle" font-size="12"
    fill="var(--green)">Nhánh 1</text>
</svg>
```

## Bảng màu theo loại

| Visual | Màu chính | Màu phụ |
|--------|-----------|---------|
| Architecture | accent (xanh dương) → green → purple (theo layer) | text3 cho arrows |
| Process/Flow | accent cho active, text3 cho inactive | green cho completed |
| Comparison | red (trái) + teal (phải) | amber cho highlight |
| Concept | accent cho center, phân đều green/purple/amber/teal cho branches | |
| Timeline | accent cho mốc chính, text3 cho đường kẻ | green cho hoàn thành |

## Kỹ thuật nâng cao

- **Gradient fill**: `<linearGradient>` cho background sections
- **Animated dash**: `stroke-dasharray` + CSS animation cho data flow
- **Tooltip**: `<title>` element trong SVG cho native browser tooltip
- **Responsive text**: `font-size` theo viewBox ratio, không dùng px
