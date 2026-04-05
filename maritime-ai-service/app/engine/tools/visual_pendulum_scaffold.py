"""Pendulum simulation scaffold helpers for Code Studio visual upgrades."""

from __future__ import annotations

import html as html_mod

from app.engine.tools.visual_html_builders import _wrap_html

def _looks_like_pendulum_simulation(raw_html: str, title: str, query: str) -> bool:
    haystack = " ".join(part for part in (raw_html, title, query) if part).lower()
    return any(
        token in haystack
        for token in (
            "pendulum",
            "con lac",
            "con lắc",
            "theta",
            "omega",
            "gravity",
            "damping",
            "dao dong",
            "dao động",
        )
    )


def _build_pendulum_simulation_scaffold(title: str, subtitle: str = "", query: str = "") -> str:
    return _build_pendulum_simulation_scaffold_v2(title, subtitle, query)

def _build_pendulum_simulation_scaffold_v2(title: str, subtitle: str = "", query: str = "") -> str:
    safe_title = html_mod.escape(title.strip() or "Mini Pendulum Physics App")
    safe_subtitle = html_mod.escape(
        subtitle.strip() or "Keo qua nang de doi goc lech, roi quan sat chuyen dong cua con lac."
    )
    normalized_query = " ".join(part for part in (title, subtitle, query) if part).lower()
    wants_gravity = any(token in normalized_query for token in ("gravity", "trong luc", "trong-luc"))
    wants_damping = any(token in normalized_query for token in ("damping", "ma sat", "ma-sat", "friction"))

    control_blocks: list[str] = []
    if wants_gravity:
        control_blocks.append(
            """
      <div class="pendulum-control">
        <header><strong>Gravity</strong><span id="gravity-value">9.81 m/s^2</span></header>
        <input id="gravity-slider" type="range" min="1" max="20" step="0.1" value="9.81" aria-label="Gravity" />
      </div>
""".strip("\n")
        )
    if wants_damping:
        control_blocks.append(
            """
      <div class="pendulum-control">
        <header><strong>Damping</strong><span id="damping-value">0.020</span></header>
        <input id="damping-slider" type="range" min="0" max="0.12" step="0.002" value="0.02" aria-label="Damping" />
      </div>
""".strip("\n")
        )
    control_blocks.append(
        """
      <div class="pendulum-control">
        <header><strong>Length</strong><span id="length-value">1.20 m</span></header>
        <input id="length-slider" type="range" min="0.6" max="2.2" step="0.05" value="1.2" aria-label="Length" />
      </div>
""".strip("\n")
    )
    controls_markup = "\n".join(control_blocks)

    live_running = "Mo phong dang chay voi cac tham so hien tai."
    if wants_gravity and wants_damping:
        live_running = "Mo phong dang chay voi gravity, damping va chieu dai hien tai."
    elif wants_gravity:
        live_running = "Mo phong dang chay voi gravity va chieu dai hien tai."
    elif wants_damping:
        live_running = "Mo phong dang chay voi damping va chieu dai hien tai."

    return f"""
<style>
  .pendulum-lab {{
    display: grid;
    gap: 14px;
    grid-template-columns: minmax(0, 1.55fr) minmax(240px, 0.95fr);
    align-items: stretch;
  }}
  .pendulum-stage {{
    position: relative;
    min-height: 360px;
    border-radius: 18px;
    border: 1px solid color-mix(in srgb, var(--border) 78%, transparent);
    background:
      radial-gradient(circle at top, rgba(37,99,235,0.10), transparent 42%),
      linear-gradient(180deg, color-mix(in srgb, var(--bg2) 92%, white) 0%, color-mix(in srgb, var(--bg) 90%, white) 100%);
    overflow: hidden;
  }}
  .pendulum-canvas {{
    width: 100%;
    height: 100%;
    display: block;
    touch-action: none;
    cursor: grab;
  }}
  .pendulum-canvas.is-dragging {{
    cursor: grabbing;
  }}
  .pendulum-overlay {{
    position: absolute;
    inset: 12px 12px auto;
    display: flex;
    justify-content: space-between;
    gap: 12px;
    pointer-events: none;
    font-size: 12px;
    color: var(--text2);
  }}
  .pendulum-chip {{
    background: color-mix(in srgb, var(--bg) 82%, white);
    border: 1px solid color-mix(in srgb, var(--border) 72%, transparent);
    border-radius: 999px;
    padding: 6px 10px;
    box-shadow: 0 10px 24px rgba(15, 23, 42, 0.08);
  }}
  .pendulum-panel {{
    display: grid;
    gap: 12px;
    align-content: start;
  }}
  .pendulum-card {{
    border-radius: 16px;
    border: 1px solid color-mix(in srgb, var(--border) 74%, transparent);
    background: color-mix(in srgb, var(--bg) 95%, white);
    padding: 14px;
  }}
  .pendulum-card h3 {{
    margin: 0 0 6px;
    font-family: var(--wiii-serif, "Georgia", serif);
    font-size: 17px;
    color: var(--text);
  }}
  .pendulum-card p {{
    margin: 0;
    color: var(--text2);
    font-size: 13px;
    line-height: 1.55;
  }}
  .pendulum-controls {{
    display: grid;
    gap: 12px;
  }}
  .pendulum-control {{
    display: grid;
    gap: 6px;
  }}
  .pendulum-control header {{
    display: flex;
    justify-content: space-between;
    gap: 8px;
    align-items: baseline;
    font-size: 12px;
    color: var(--text2);
  }}
  .pendulum-control strong {{
    color: var(--text);
    font-size: 13px;
  }}
  .pendulum-readouts {{
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 10px;
  }}
  .pendulum-readout {{
    border-radius: 14px;
    background: color-mix(in srgb, var(--bg2) 80%, white);
    border: 1px solid color-mix(in srgb, var(--border) 66%, transparent);
    padding: 10px 12px;
  }}
  .pendulum-readout label {{
    display: block;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--text3);
    margin-bottom: 6px;
  }}
  .pendulum-readout strong {{
    font-size: 18px;
    color: var(--text);
  }}
  .pendulum-actions {{
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
  }}
  .pendulum-actions button {{
    min-width: 108px;
  }}
  .pendulum-note {{
    font-size: 12px;
    color: var(--text2);
  }}
  .pendulum-live {{
    min-height: 18px;
  }}
  @media (max-width: 720px) {{
    .pendulum-lab {{
      grid-template-columns: 1fr;
    }}
    .pendulum-stage {{
      min-height: 320px;
    }}
  }}
</style>

<div class="pendulum-lab" data-sim-kind="pendulum">
  <section class="pendulum-stage" aria-label="{safe_title}">
    <canvas id="pendulum-sim" class="pendulum-canvas"></canvas>
    <div class="pendulum-overlay">
      <div class="pendulum-chip">Keo qua nang de doi goc lech</div>
      <div class="pendulum-chip">Canvas runtime + live telemetry</div>
    </div>
  </section>

  <aside class="pendulum-panel">
    <section class="pendulum-card">
      <h3>{safe_title}</h3>
      <p>{safe_subtitle}</p>
    </section>

    <section class="pendulum-card pendulum-controls" aria-label="Dieu chinh tham so">
{controls_markup}
    </section>

    <section class="pendulum-card pendulum-readouts" aria-live="polite">
      <div class="pendulum-readout">
        <label>Goc lech</label>
        <strong id="angle-readout">18.0 deg</strong>
      </div>
      <div class="pendulum-readout">
        <label>Van toc goc</label>
        <strong id="velocity-readout">0.00 rad/s</strong>
      </div>
      <div class="pendulum-readout">
        <label>Chu ky xap xi</label>
        <strong id="period-readout">2.20 s</strong>
      </div>
      <div class="pendulum-readout">
        <label>Trang thai</label>
        <strong id="status-readout">Dang chay</strong>
      </div>
    </section>

    <section class="pendulum-card">
      <div class="pendulum-actions">
        <button type="button" id="play-toggle">Tam dung</button>
        <button type="button" id="reset-btn">Dat lai</button>
      </div>
      <p class="pendulum-note pendulum-live" id="pendulum-live">Ban co the keo truc tiep qua nang de dat goc ban dau moi.</p>
    </section>
  </aside>
</div>

<script>
  (function () {{
    const canvas = document.getElementById('pendulum-sim');
    const ctx = canvas.getContext('2d');
    const gravitySlider = document.getElementById('gravity-slider');
    const dampingSlider = document.getElementById('damping-slider');
    const lengthSlider = document.getElementById('length-slider');
    const playToggle = document.getElementById('play-toggle');
    const resetBtn = document.getElementById('reset-btn');
    const gravityValue = document.getElementById('gravity-value');
    const dampingValue = document.getElementById('damping-value');
    const lengthValue = document.getElementById('length-value');
    const angleReadout = document.getElementById('angle-readout');
    const velocityReadout = document.getElementById('velocity-readout');
    const periodReadout = document.getElementById('period-readout');
    const statusReadout = document.getElementById('status-readout');
    const live = document.getElementById('pendulum-live');

    const baseState = {{
      gravity: 9.81,
      damping: 0.02,
      length: 1.2,
      theta: Math.PI / 10,
      omega: 0,
      running: true,
      dragging: false,
    }};
    const state = Object.assign({{}}, baseState);

    let rafId = 0;
    let lastTime = performance.now();
    let pivot = {{ x: 0, y: 40 }};
    let bobRadius = 18;
    let pixelsPerMeter = 180;

    function report(kind, payload, summary, status) {{
      if (window.WiiiVisualBridge && typeof window.WiiiVisualBridge.reportResult === 'function') {{
        window.WiiiVisualBridge.reportResult(kind, payload, summary, status);
      }}
    }}

    function setText(node, value) {{
      if (node) {{
        node.textContent = value;
      }}
    }}

    function resizeCanvas() {{
      const rect = canvas.getBoundingClientRect();
      const ratio = Math.max(1, window.devicePixelRatio || 1);
      canvas.width = Math.max(320, Math.floor(rect.width * ratio));
      canvas.height = Math.max(280, Math.floor(rect.height * ratio));
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.scale(ratio, ratio);
      pivot = {{ x: rect.width / 2, y: 44 }};
      pixelsPerMeter = Math.max(110, rect.height * 0.52);
      draw();
      if (window.WiiiVisualBridge && typeof window.WiiiVisualBridge.resize === 'function') {{
        window.WiiiVisualBridge.resize();
      }}
    }}

    function pendulumMetrics() {{
      const angleDeg = state.theta * 180 / Math.PI;
      const approxPeriod = 2 * Math.PI * Math.sqrt(state.length / Math.max(state.gravity, 0.1));
      return {{ angleDeg, approxPeriod }};
    }}

    function syncReadouts() {{
      const metrics = pendulumMetrics();
      setText(gravityValue, state.gravity.toFixed(2) + ' m/s^2');
      setText(dampingValue, state.damping.toFixed(3));
      setText(lengthValue, state.length.toFixed(2) + ' m');
      setText(angleReadout, metrics.angleDeg.toFixed(1) + ' deg');
      setText(velocityReadout, state.omega.toFixed(2) + ' rad/s');
      setText(periodReadout, metrics.approxPeriod.toFixed(2) + ' s');
      setText(statusReadout, state.dragging ? 'Dang keo' : (state.running ? 'Dang chay' : 'Tam dung'));
      if (live) {{
        live.textContent = state.dragging
          ? 'Tha chuot de xem con lac tiep tuc dao dong tu goc moi.'
          : (state.running
            ? '{live_running}'
            : 'Mo phong dang tam dung. Ban co the keo qua nang hoac tiep tuc chay.');
      }}
    }}

    function bobPosition() {{
      const rect = canvas.getBoundingClientRect();
      const rodLength = state.length * pixelsPerMeter;
      return {{
        x: pivot.x + rodLength * Math.sin(state.theta),
        y: pivot.y + rodLength * Math.cos(state.theta),
        width: rect.width,
        height: rect.height,
        rodLength: rodLength,
      }};
    }}

    function drawGrid(width, height) {{
      ctx.save();
      ctx.strokeStyle = 'rgba(148, 163, 184, 0.14)';
      ctx.lineWidth = 1;
      for (let x = 24; x < width; x += 32) {{
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, height);
        ctx.stroke();
      }}
      for (let y = 24; y < height; y += 32) {{
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(width, y);
        ctx.stroke();
      }}
      ctx.restore();
    }}

    function draw() {{
      const rect = canvas.getBoundingClientRect();
      const width = rect.width;
      const height = rect.height;
      ctx.clearRect(0, 0, width, height);
      drawGrid(width, height);

      ctx.save();
      ctx.fillStyle = 'rgba(15, 23, 42, 0.06)';
      ctx.fillRect(0, height - 38, width, 38);
      ctx.restore();

      const bob = bobPosition();

      ctx.save();
      ctx.strokeStyle = 'rgba(37, 99, 235, 0.85)';
      ctx.lineWidth = 4;
      ctx.lineCap = 'round';
      ctx.beginPath();
      ctx.moveTo(pivot.x, pivot.y);
      ctx.lineTo(bob.x, bob.y);
      ctx.stroke();

      ctx.fillStyle = 'rgba(148, 163, 184, 0.42)';
      ctx.beginPath();
      ctx.arc(pivot.x, pivot.y, 8, 0, Math.PI * 2);
      ctx.fill();

      const bobGradient = ctx.createRadialGradient(bob.x - 8, bob.y - 10, 4, bob.x, bob.y, 22);
      bobGradient.addColorStop(0, '#93c5fd');
      bobGradient.addColorStop(0.45, '#2563eb');
      bobGradient.addColorStop(1, '#1e3a8a');
      ctx.fillStyle = bobGradient;
      ctx.beginPath();
      ctx.arc(bob.x, bob.y, bobRadius, 0, Math.PI * 2);
      ctx.fill();

      ctx.strokeStyle = 'rgba(255,255,255,0.7)';
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(bob.x - 5, bob.y - 6, 6, Math.PI * 1.2, Math.PI * 1.9);
      ctx.stroke();
      ctx.restore();

      syncReadouts();
    }}

    function advance(dt) {{
      const acceleration = -(state.gravity / Math.max(state.length, 0.25)) * Math.sin(state.theta) - state.damping * state.omega;
      state.omega += acceleration * dt;
      state.theta += state.omega * dt;
    }}

    function loop(now) {{
      const dt = Math.min(0.032, Math.max(0.001, (now - lastTime) / 1000));
      lastTime = now;
      if (state.running && !state.dragging) {{
        advance(dt);
      }}
      draw();
      rafId = window.requestAnimationFrame(loop);
    }}

    function pointerToTheta(clientX, clientY) {{
      const rect = canvas.getBoundingClientRect();
      const dx = clientX - rect.left - pivot.x;
      const dy = clientY - rect.top - pivot.y;
      return Math.atan2(dx, Math.max(24, dy));
    }}

    function onPointerDown(event) {{
      const bob = bobPosition();
      const rect = canvas.getBoundingClientRect();
      const x = event.clientX - rect.left;
      const y = event.clientY - rect.top;
      const distance = Math.hypot(x - bob.x, y - bob.y);
      if (distance > bobRadius + 16) return;
      state.dragging = true;
      state.running = false;
      state.omega = 0;
      canvas.classList.add('is-dragging');
      canvas.setPointerCapture(event.pointerId);
      state.theta = pointerToTheta(event.clientX, event.clientY);
      draw();
    }}

    function onPointerMove(event) {{
      if (!state.dragging) return;
      state.theta = pointerToTheta(event.clientX, event.clientY);
      draw();
    }}

    function onPointerUp(event) {{
      if (!state.dragging) return;
      state.dragging = false;
      state.running = true;
      canvas.classList.remove('is-dragging');
      try {{
        canvas.releasePointerCapture(event.pointerId);
      }} catch (_error) {{}}
      const metrics = pendulumMetrics();
      report(
        'simulation_result',
        {{
          simulation: 'pendulum',
          angle_deg: Number(metrics.angleDeg.toFixed(1)),
          gravity: Number(state.gravity.toFixed(2)),
          damping: Number(state.damping.toFixed(3)),
          length_m: Number(state.length.toFixed(2)),
        }},
        'Nguoi dung vua tha con lac o goc ' + metrics.angleDeg.toFixed(1) + ' deg.',
        'completed'
      );
    }}

    if (gravitySlider) {{
      gravitySlider.addEventListener('input', function () {{
        state.gravity = Number(gravitySlider.value);
        draw();
      }});
    }}
    if (dampingSlider) {{
      dampingSlider.addEventListener('input', function () {{
        state.damping = Number(dampingSlider.value);
        draw();
      }});
    }}
    if (lengthSlider) {{
      lengthSlider.addEventListener('input', function () {{
        state.length = Number(lengthSlider.value);
        draw();
      }});
    }}

    playToggle.addEventListener('click', function () {{
      state.running = !state.running;
      playToggle.textContent = state.running ? 'Tam dung' : 'Tiep tuc';
      draw();
      report(
        'simulation_result',
        {{
          simulation: 'pendulum',
          action: state.running ? 'resume' : 'pause',
          gravity: Number(state.gravity.toFixed(2)),
          damping: Number(state.damping.toFixed(3)),
          length_m: Number(state.length.toFixed(2)),
        }},
        state.running ? 'Nguoi dung tiep tuc mo phong con lac.' : 'Nguoi dung tam dung mo phong con lac.',
        state.running ? 'running' : 'paused'
      );
    }});

    resetBtn.addEventListener('click', function () {{
      Object.assign(state, baseState);
      if (gravitySlider) gravitySlider.value = String(baseState.gravity);
      if (dampingSlider) dampingSlider.value = String(baseState.damping);
      if (lengthSlider) lengthSlider.value = String(baseState.length);
      playToggle.textContent = 'Tam dung';
      draw();
      report(
        'simulation_result',
        {{
          simulation: 'pendulum',
          action: 'reset',
          angle_deg: 18,
        }},
        'Nguoi dung da dat lai mo phong con lac ve trang thai mac dinh.',
        'reset'
      );
    }});

    canvas.addEventListener('pointerdown', onPointerDown);
    canvas.addEventListener('pointermove', onPointerMove);
    canvas.addEventListener('pointerup', onPointerUp);
    canvas.addEventListener('pointercancel', onPointerUp);
    window.addEventListener('resize', resizeCanvas);

    resizeCanvas();
    draw();
    rafId = window.requestAnimationFrame(loop);

    window.addEventListener('beforeunload', function () {{
      if (rafId) window.cancelAnimationFrame(rafId);
    }});
  }})();
</script>
""".strip()
