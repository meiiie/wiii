# Code Studio Reference Examples

Few-shot examples for LLM visual code generation. Loaded on-demand based on `visual_type`.

| File | Category | Lines | Use when |
|------|----------|-------|----------|
| `canvas_wave_interference.html` | Canvas simulation | ~800 | `visual_type == "simulation"` |
| `svg_ship_encounter.html` | SVG interactive diagram | ~830 | `visual_type in ("diagram", "comparison", "process")` |
| `widget_maritime_calculator.html` | HTML/CSS/JS widget | ~370 | `visual_type in ("tool", "quiz", "calculator")` |

## Design System

All examples share the same CSS variable theme (dark-first, light via `prefers-color-scheme`).
All use `<style>` first, HTML second, `<script>` last — fragment only (no DOCTYPE/html/head/body).
All integrate `WiiiVisualBridge.reportResult()` for host communication.
