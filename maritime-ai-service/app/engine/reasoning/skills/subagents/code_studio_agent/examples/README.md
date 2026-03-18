# Code Studio Reference Examples

Few-shot examples for LLM visual code generation. Loaded on-demand based on `visual_type`.

| File | Category | Lines | Use when |
|------|----------|-------|----------|
| `canvas_wave_interference.html` | Canvas simulation | ~800 | simulation, physics, animation |
| `svg_ship_encounter.html` | SVG interactive diagram | ~830 | diagram, architecture |
| `svg_comparison_chart.html` | SVG comparison chart | ~470 | comparison, chart, benchmark, statistics |
| `svg_flow_diagram.html` | SVG flow diagram | ~600 | process, workflow, timeline |
| `dashboard_metrics.html` | Interactive dashboard | ~624 | dashboard, metrics, overview |
| `widget_maritime_calculator.html` | HTML/CSS/JS widget | ~370 | tool, quiz, calculator |

## Design System

All examples share the same CSS variable theme (dark-first, light via `prefers-color-scheme`).
All use `<style>` first, HTML second, `<script>` last — fragment only (no DOCTYPE/html/head/body).
All integrate `WiiiVisualBridge.reportResult()` for host communication.
