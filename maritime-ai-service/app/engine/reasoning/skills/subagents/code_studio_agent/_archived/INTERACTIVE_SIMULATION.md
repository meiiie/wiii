---
id: wiii-interactive-simulation
name: Interactive Simulation
skill_type: subagent
node: code_studio_agent
description: Patterns cho mô phỏng vật lý tương tác — pendulum, spring, wave, collision, orbit. Canvas/SVG + requestAnimationFrame + sliders + stats.
version: "1.0.0"
---

# Interactive Simulation Skill

Mô phỏng tương tác là visual cao cấp nhất — kết hợp vật lý, animation, và UI controls.

## Cấu trúc bắt buộc

Mỗi mô phỏng PHẢI có đủ 5 phần:

1. **Canvas/SVG viewport** — vùng render chính (viewBox responsive)
2. **Stats panel** — hiển thị số liệu realtime (vận tốc, năng lượng, góc...)
3. **Energy bars** — thanh năng lượng Eₚ và Eₖ (hoặc tương đương)
4. **Control sliders** — tham số có thể thay đổi (chiều dài, góc, trọng lực...)
5. **Action buttons** — Đặt lại, Tạm dừng/Tiếp tục

## CSS Framework

```css
/* Control slider */
.ctrl{display:flex;align-items:center;gap:10px;margin:6px 0;font-size:13px;color:var(--text2)}
.ctrl input[type=range]{flex:1;accent-color:var(--accent)}
.val{min-width:52px;text-align:right;font-weight:500;font-size:13px;color:var(--text)}

/* Energy bars */
.bar-wrap{display:flex;gap:8px;margin:4px 0}
.bar-label{font-size:12px;min-width:28px;color:var(--text2)}
.bar-bg{flex:1;height:14px;border-radius:7px;background:var(--bg3);overflow:hidden}
.bar-fill{height:100%;border-radius:7px;transition:width .05s}

/* Stats panel */
.stats{display:flex;gap:16px;flex-wrap:wrap;margin:8px 0}
.stat{background:var(--bg2);border-radius:var(--radius-sm);padding:8px 12px;flex:1;min-width:90px}
.stat-label{font-size:11px;color:var(--text3)}
.stat-val{font-size:18px;font-weight:500;color:var(--text);margin-top:2px}

/* Buttons */
.btn-row{display:flex;gap:8px;margin:8px 0}
.btn-row button{padding:6px 14px;font-size:13px;background:transparent;color:var(--text);
  border:1px solid var(--border);border-radius:6px;cursor:pointer;transition:background .15s}
.btn-row button:hover{background:var(--bg3)}
```

## JavaScript Pattern

```javascript
// Biến trạng thái
let paused = false, raf;

// Animation loop
function step() {
  if (!paused) {
    // Physics update (dt = 0.016 ~ 60fps)
    const dt = 0.016;
    // ... update positions, velocities ...
  }
  draw();
  raf = requestAnimationFrame(step);
}

// Reset
function resetSim() {
  // Reset all state variables
  paused = false;
  document.getElementById('btn-pause').textContent = 'Tạm dừng';
}

// Pause/Resume
function togglePause() {
  paused = !paused;
  document.getElementById('btn-pause').textContent = paused ? 'Tiếp tục' : 'Tạm dừng';
}
```

## SVG Polish

- Dùng `radialGradient` cho vật thể (bob, ball, planet)
- Dùng `trail path` (opacity thấp) cho quỹ đạo
- Dùng `stroke-dasharray` cho góc đo
- Dùng `text-anchor="middle"` cho label
- ViewBox 680x340 cho landscape, 400x500 cho portrait

## Patterns có sẵn

| Mô phỏng | Biến | SVG/Canvas |
|-----------|------|------------|
| Con lắc đơn | L, θ₀, g | SVG (dây + bob + trail) |
| Lò xo | k, m, x₀ | SVG (spring zigzag + mass) |
| Sóng | λ, f, A | Canvas (sine wave animation) |
| Va chạm | m₁, m₂, v₁, v₂ | SVG (2 circles + velocity arrows) |
| Quỹ đạo | G, M, v₀ | Canvas (planet orbit trail) |
| Con lắc đôi | L₁, L₂, θ₁, θ₂ | SVG (chaotic trail) |

## Hàng hải — Mô phỏng đặc thù

| Mô phỏng | Mô tả |
|-----------|-------|
| COLREGs Rule 15 | 2 tàu giao nhau, tàu bên phải nhường đường |
| Đèn hàng hải | Tàu quay 360°, hiện đèn mạn xanh/đỏ/trắng |
| Tín hiệu cờ | Hệ thống cờ tín hiệu quốc tế, hover hiện nghĩa |
| Buoyage System | Phao luồng IALA A/B, màu sắc + hình dạng |
| Compass Rose | La bàn 360° + bearing + deviation |
