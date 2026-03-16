---
id: wiii-visual-code-gen
name: Visual Code Generation
skill_type: subagent
node: code_studio_agent
description: Design system reference and patterns for generating inline visual HTML/CSS/SVG code via code_html param.
version: "1.0.0"
---

# Visual Code Generation Skill

Khi tao visual inline bang code_html, Wiii viet HTML/CSS/SVG tay — moi visual unique, custom.

## Design System CSS Variables

code_html duoc wrap trong design system shell co san cac CSS vars:

```
Light mode:
  --bg: #ffffff    --bg2: #f8fafc   --bg3: #f1f5f9
  --text: #1e293b  --text2: #475569  --text3: #94a3b8
  --accent: #2563eb --green: #10b981 --purple: #8b5cf6
  --amber: #f59e0b  --teal: #14b8a6  --pink: #ec4899
  --border: #e2e8f0  --shadow: rgba(0,0,0,0.06)
  --radius: 12px     --radius-sm: 8px

Dark mode (tu dong): Cac vars tu chuyen — chi can dung var(--xxx).
```

## Quy tac viet code_html

1. CHI viet body content (CSS + HTML). KHONG viet <!DOCTYPE>, <html>, <head>, <body> — system tu wrap.
2. Dung <style> block cho CSS, sau do HTML content.
3. LUON dung CSS variables thay vi hardcode color: `color: var(--accent)` KHONG `color: #2563eb`.
4. Dark mode tu dong — KHONG can @media prefers-color-scheme.
5. Uu tien CSS animation/transition > JavaScript. Chi dung JS khi that su can interaction.
6. Font-family da co san (system font stack) — khong can khai bao lai.
7. Responsive: dung flex/grid + media query max-width:500px cho mobile.

## Patterns

### SVG Diagram Custom
```html
<style>
.diagram { display: flex; flex-direction: column; align-items: center; gap: 8px; }
.node { padding: 10px 16px; border-radius: var(--radius); border: 1.5px solid var(--border);
  background: var(--bg2); font-size: 13px; font-weight: 500; color: var(--text);
  transition: transform 0.15s; }
.node:hover { transform: translateY(-2px); }
.node.primary { border-color: var(--accent); color: var(--accent); }
.connector { width: 2px; height: 20px; background: var(--border); }
</style>
<div class="diagram">
  <div class="node primary">API Gateway</div>
  <div class="connector"></div>
  <div class="node">Service Layer</div>
</div>
```

### Network/Grid Layout
```html
<style>
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 8px; }
.cell { padding: 12px; border-radius: var(--radius-sm); border: 1px solid var(--border);
  background: var(--bg2); text-align: center; }
.cell-title { font-size: 12px; font-weight: 600; color: var(--text); }
.cell-value { font-size: 20px; font-weight: 800; margin-top: 4px; }
</style>
<div class="grid">
  <div class="cell"><div class="cell-title">Metric</div><div class="cell-value" style="color:var(--accent)">95%</div></div>
</div>
```

### SVG Inline Chart/Diagram
```html
<svg viewBox="0 0 400 200" style="width:100%;height:auto">
  <rect x="10" y="20" width="80" height="160" rx="8" fill="var(--accent)" opacity="0.2" stroke="var(--accent)"/>
  <text x="50" y="110" text-anchor="middle" fill="var(--text)" font-size="12" font-weight="600">Node A</text>
  <line x1="90" y1="100" x2="150" y2="100" stroke="var(--border)" stroke-width="2" marker-end="url(#arrow)"/>
  <defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto">
    <path d="M0,0 L10,5 L0,10 Z" fill="var(--text3)"/></marker></defs>
</svg>
```

### Animated Flow
```html
<style>
@keyframes flow { from { stroke-dashoffset: 20; } to { stroke-dashoffset: 0; } }
.flow-line { stroke-dasharray: 5 5; animation: flow 1s linear infinite; }
</style>
```

## Anti-patterns — KHONG lam

- KHONG hardcode mau: `color: #2563eb` → dung `color: var(--accent)`
- KHONG dung font-family custom (da co san)
- KHONG viet <!DOCTYPE html> (system tu wrap)
- KHONG dung JavaScript cho hover/animation don gian (dung CSS :hover, transition)
- KHONG tao visual qua lon (>5000 chars HTML) — giu gon, tinh te
