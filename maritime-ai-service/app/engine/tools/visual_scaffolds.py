"""Visual scaffold library — reusable HTML/CSS/JS templates for Code Studio.

Inspired by Claude Design's starter components (deck_stage, design_canvas,
ios_frame, etc.). Each scaffold provides a complete interactive shell that
the LLM can fill with domain-specific content.

Available scaffolds:
- simulation: Generic Canvas-based physics/math simulation
- quiz: Interactive quiz widget with React state management
- dashboard: Data dashboard with metric card slots
- pendulum: (wrapped from visual_pendulum_scaffold.py)

Design principles (from Claude Design):
- Avoid AI slop: no gradient spam, no emoji, no "AI card" tropes
- Use CSS variables for theming
- Responsive grid layouts
- WiiiVisualBridge telemetry integration
- Canvas-first for simulations, React for interactive UIs
"""

from __future__ import annotations

import html as html_mod
from typing import Optional

from app.engine.tools.visual_html_core import (
    _DESIGN_CSS,
    _svg_icon,
    _tweaks_inject,
    _wrap_html,
    _wrap_html_react,
)


# ---------------------------------------------------------------------------
# Scaffold registry
# ---------------------------------------------------------------------------

_SCAFFOLD_KINDS = ("simulation", "quiz", "dashboard", "pendulum")


def detect_scaffold(query: str, visual_type: str, raw_html: str = "") -> Optional[str]:
    """Detect which scaffold matches the query/context.

    Returns scaffold kind string or None if no scaffold fits.
    """
    haystack = " ".join(part for part in (query, visual_type, raw_html) if part).lower()

    # Pendulum (most specific — check first)
    pendulum_tokens = (
        "pendulum", "con lac", "con lắc", "dao dong con lac", "dao động con lắc",
    )
    if any(t in haystack for t in pendulum_tokens):
        return "pendulum"

    # Generic simulation
    sim_tokens = (
        "simulation", "mô phỏng", "mo phong", "physics", "vat ly", "vật lý",
        "particle", "hat", "hạt", "wave", "song", "sóng",
        "collision", "va cham", "va chạm", "trajectory", "quy đạo",
        "force", "luc", "lực", "motion", "chuyen dong", "chuyển động",
        "gravity sim", "friction sim", "momentum", "dao dong", "dao động",
    )
    if visual_type == "simulation" or any(t in haystack for t in sim_tokens):
        return "simulation"

    # Quiz
    quiz_tokens = (
        "quiz", "trac nghiem", "trắc nghiệm", "cau hoi", "câu hỏi",
        "flashcard", "kiem tra", "kiểm tra", "kahoot", "test me",
    )
    if visual_type == "quiz" or any(t in haystack for t in quiz_tokens):
        return "quiz"

    # Dashboard
    dash_tokens = (
        "dashboard", "bang dieu khien", "bảng điều khiển", "analytics",
        "metrics", "kpi", "monitoring", "theo doi", "theo dõi",
    )
    if visual_type == "dashboard" or any(t in haystack for t in dash_tokens):
        return "dashboard"

    return None


def build_scaffold(kind: str, title: str, subtitle: str = "", query: str = "") -> str:
    """Build scaffold HTML by kind.

    Returns self-contained HTML ready for quality scoring and rendering.
    """
    if kind == "pendulum":
        from app.engine.tools.visual_pendulum_scaffold import _build_pendulum_simulation_scaffold
        return _build_pendulum_simulation_scaffold(title, subtitle, query)
    if kind == "simulation":
        return _build_simulation_scaffold(title, subtitle, query)
    if kind == "quiz":
        return _build_quiz_scaffold(title, subtitle, query)
    if kind == "dashboard":
        return _build_dashboard_scaffold(title, subtitle, query)
    raise ValueError(f"Unknown scaffold kind: {kind!r}")


# ---------------------------------------------------------------------------
# Detection helpers (for maybe_upgrade_code_studio_output)
# ---------------------------------------------------------------------------

def _looks_like_simulation(raw_html: str, title: str, query: str) -> bool:
    """Check if raw HTML looks like a simulation that could be scaffolded."""
    haystack = " ".join(part for part in (raw_html, title, query) if part).lower()
    sim_tokens = (
        "canvas", "getcontext", "requestanimationframe",
        "physics", "simulation", "mo phong", "mô phỏng",
    )
    has_sim_tokens = any(t in haystack for t in sim_tokens)
    is_pendulum = any(t in haystack for t in ("pendulum", "con lac", "con lắc"))
    return has_sim_tokens and not is_pendulum


def _looks_like_quiz(raw_html: str, title: str, query: str) -> bool:
    """Check if context suggests a quiz scaffold."""
    haystack = " ".join(part for part in (raw_html, title, query) if part).lower()
    return any(t in haystack for t in (
        "quiz", "trac nghiem", "trắc nghiệm", "cau hoi", "câu hỏi", "flashcard",
    ))


def _looks_like_dashboard(raw_html: str, title: str, query: str) -> bool:
    """Check if context suggests a dashboard scaffold."""
    haystack = " ".join(part for part in (raw_html, title, query) if part).lower()
    return any(t in haystack for t in (
        "dashboard", "bang dieu khien", "analytics", "metrics", "kpi",
    ))


# ---------------------------------------------------------------------------
# Scaffold 1: Generic Simulation (Canvas)
# ---------------------------------------------------------------------------

def _build_simulation_scaffold(title: str, subtitle: str = "", query: str = "") -> str:
    """Generic Canvas simulation shell for physics/math/engineering.

    Provides: Canvas stage, parameter controls, live readouts,
    play/pause/reset, WiiiVisualBridge telemetry.
    """
    safe_title = html_mod.escape(title.strip() or "Simulation")
    safe_subtitle = html_mod.escape(
        subtitle.strip() or "Interactive simulation — adjust parameters and observe."
    )
    sim_tweaks = _tweaks_inject(
        '{"--sim-speed":"1","--sim-intensity":"0.7",'
        '"--sim-bg":"#f8fafc","--sim-accent":"#2563eb"}'
    )

    return f"""<!DOCTYPE html>
<html lang="vi"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>{_DESIGN_CSS}
.sim-lab {{
  display: grid;
  gap: 14px;
  grid-template-columns: minmax(0, 1.55fr) minmax(240px, 0.95fr);
  align-items: stretch;
}}
.sim-stage {{
  position: relative;
  min-height: 360px;
  border-radius: 14px;
  border: 1px solid var(--border);
  background: var(--bg2);
  overflow: hidden;
}}
.sim-canvas {{
  width: 100%; height: 100%; display: block;
  touch-action: none; cursor: crosshair;
}}
.sim-overlay {{
  position: absolute; inset: 12px 12px auto;
  display: flex; justify-content: space-between; gap: 12px;
  pointer-events: none; font-size: 12px; color: var(--text2);
}}
.sim-chip {{
  background: color-mix(in srgb, var(--bg) 85%, white);
  border: 1px solid var(--border); border-radius: 999px;
  padding: 5px 10px; font-size: 11px;
}}
.sim-panel {{
  display: grid; gap: 12px; align-content: start;
}}
.sim-card {{
  border-radius: 14px; border: 1px solid var(--border);
  background: var(--bg); padding: 14px;
}}
.sim-card h3 {{
  margin: 0 0 6px; font-size: 16px; color: var(--text);
}}
.sim-card p {{
  margin: 0; color: var(--text2); font-size: 13px; line-height: 1.5;
}}
.sim-controls {{
  display: grid; gap: 10px;
}}
.sim-control {{
  display: grid; gap: 4px;
}}
.sim-control header {{
  display: flex; justify-content: space-between; align-items: baseline;
  font-size: 12px; color: var(--text2);
}}
.sim-control strong {{
  color: var(--text); font-size: 13px;
}}
.sim-readouts {{
  display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px;
}}
.sim-readout {{
  border-radius: 12px; background: var(--bg2);
  border: 1px solid var(--border); padding: 10px 12px;
}}
.sim-readout label {{
  display: block; font-size: 10px; text-transform: uppercase;
  letter-spacing: 0.04em; color: var(--text3); margin-bottom: 4px;
}}
.sim-readout strong {{
  font-size: 17px; color: var(--text);
}}
.sim-actions {{
  display: flex; gap: 10px;
}}
.sim-actions button {{
  min-width: 100px; padding: 8px 16px;
  border-radius: 8px; border: 1px solid var(--border);
  background: var(--bg2); color: var(--text); cursor: pointer;
  font-size: 13px; font-weight: 500;
  transition: background 0.15s;
}}
.sim-actions button:hover {{
  background: var(--accent-bg);
}}
@media (max-width: 720px) {{
  .sim-lab {{ grid-template-columns: 1fr; }}
  .sim-stage {{ min-height: 280px; }}
}}
</style></head>
<body>
<div class="sim-lab" data-sim-kind="generic">
  <section class="sim-stage" aria-label="{safe_title}">
    <canvas id="sim-canvas" class="sim-canvas"></canvas>
    <div class="sim-overlay">
      <div class="sim-chip">Canvas runtime</div>
      <div class="sim-chip">Adjust parameters below</div>
    </div>
  </section>
  <aside class="sim-panel">
    <section class="sim-card">
      <h3>{safe_title}</h3>
      <p>{safe_subtitle}</p>
    </section>
    <section class="sim-card sim-controls" aria-label="Parameters">
      <div class="sim-control">
        <header><strong>Speed</strong><span id="speed-val">1.00x</span></header>
        <input id="speed-slider" type="range" min="0.1" max="3" step="0.1" value="1" aria-label="Speed" />
      </div>
      <div class="sim-control">
        <header><strong>Intensity</strong><span id="intensity-val">0.70</span></header>
        <input id="intensity-slider" type="range" min="0" max="1" step="0.05" value="0.7" aria-label="Intensity" />
      </div>
    </section>
    <section class="sim-card sim-readouts" aria-live="polite">
      <div class="sim-readout"><label>Frame</label><strong id="frame-readout">0</strong></div>
      <div class="sim-readout"><label>FPS</label><strong id="fps-readout">60</strong></div>
      <div class="sim-readout"><label>Elapsed</label><strong id="elapsed-readout">0.0s</strong></div>
      <div class="sim-readout"><label>Status</label><strong id="status-readout">Running</strong></div>
    </section>
    <section class="sim-card">
      <div class="sim-actions">
        <button type="button" id="play-toggle">{_svg_icon("pause", 14)} Pause</button>
        <button type="button" id="reset-btn">{_svg_icon("reset", 14)} Reset</button>
      </div>
    </section>
  </aside>
</div>
<script>
(function() {{
  const canvas = document.getElementById('sim-canvas');
  const ctx = canvas.getContext('2d');
  const speedSlider = document.getElementById('speed-slider');
  const intensitySlider = document.getElementById('intensity-slider');
  const playToggle = document.getElementById('play-toggle');
  const resetBtn = document.getElementById('reset-btn');
  const speedVal = document.getElementById('speed-val');
  const intensityVal = document.getElementById('intensity-val');
  const frameReadout = document.getElementById('frame-readout');
  const fpsReadout = document.getElementById('fps-readout');
  const elapsedReadout = document.getElementById('elapsed-readout');
  const statusReadout = document.getElementById('status-readout');

  const pauseSvg = '{_svg_icon("pause", 14)}';
  const playSvg = '{_svg_icon("play", 14)}';

  const state = {{
    speed: 1.0, intensity: 0.7, running: true,
    frame: 0, elapsed: 0, lastTime: performance.now()
  }};

  function report(k,p,s,st) {{ window.WiiiVisualBridge?.reportResult?.(k,p,s,st); }}

  function resize() {{
    const r = canvas.getBoundingClientRect();
    const dpr = Math.max(1, window.devicePixelRatio || 1);
    canvas.width = Math.max(320, Math.floor(r.width * dpr));
    canvas.height = Math.max(280, Math.floor(r.height * dpr));
    ctx.setTransform(1,0,0,1,0,0); ctx.scale(dpr,dpr);
  }}

  function draw() {{
    const r = canvas.getBoundingClientRect();
    const w = r.width, h = r.height;
    ctx.clearRect(0,0,w,h);
    // Grid
    ctx.save(); ctx.strokeStyle = 'rgba(148,163,184,0.12)'; ctx.lineWidth = 1;
    for(let x=24;x<w;x+=32){{ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,h);ctx.stroke();}}
    for(let y=24;y<h;y+=32){{ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(w,y);ctx.stroke();}}
    ctx.restore();
    // Animated particles
    const count = Math.floor(20 * state.intensity);
    for(let i=0;i<count;i++){{
      const t = state.elapsed * state.speed + i * 1.37;
      const x = w/2 + Math.sin(t * 0.7 + i) * w * 0.3;
      const y = h/2 + Math.cos(t * 0.5 + i * 0.8) * h * 0.3;
      const r2 = 3 + Math.sin(t + i) * 2;
      ctx.fillStyle = 'rgba(37,99,235,' + (0.3 + state.intensity * 0.5) + ')';
      ctx.beginPath(); ctx.arc(x,y,r2,0,Math.PI*2); ctx.fill();
    }}
    // Readouts
    frameReadout.textContent = state.frame;
    fpsReadout.textContent = Math.round(1000 / Math.max(1, performance.now() - state.lastTime + 0.001));
    elapsedReadout.textContent = state.elapsed.toFixed(1) + 's';
    statusReadout.textContent = state.running ? 'Running' : 'Paused';
    speedVal.textContent = state.speed.toFixed(2) + 'x';
    intensityVal.textContent = state.intensity.toFixed(2);
  }}

  function loop(now) {{
    const dt = Math.min(0.032, Math.max(0.001, (now - state.lastTime) / 1000));
    state.lastTime = now;
    if(state.running) {{
      state.elapsed += dt * state.speed;
      state.frame++;
    }}
    draw();
    requestAnimationFrame(loop);
  }}

  speedSlider.addEventListener('input', () => {{ state.speed = Number(speedSlider.value); }});
  intensitySlider.addEventListener('input', () => {{ state.intensity = Number(intensitySlider.value); }});
  playToggle.addEventListener('click', () => {{
    state.running = !state.running;
    playToggle.innerHTML = state.running ? pauseSvg + ' Pause' : playSvg + ' Resume';
    report('simulation_result', {{action: state.running?'resume':'pause'}},
      state.running ? 'Resumed simulation.' : 'Paused simulation.', state.running?'running':'paused');
  }});
  resetBtn.addEventListener('click', () => {{
    state.frame = 0; state.elapsed = 0; state.running = true;
    playToggle.innerHTML = pauseSvg + ' Pause';
    report('simulation_result', {{action:'reset'}}, 'Simulation reset.', 'reset');
  }});

  window.addEventListener('resize', resize);
  resize(); draw();
  requestAnimationFrame(loop);
}})();
</script>
{sim_tweaks}
</body></html>"""


# ---------------------------------------------------------------------------
# Scaffold 2: Quiz Widget (React)
# ---------------------------------------------------------------------------

def _build_quiz_scaffold(title: str, subtitle: str = "", query: str = "") -> str:
    """Interactive quiz widget using React for state management.

    Features: question flow, answer selection, scoring,
    progress bar, immediate feedback, WiiiVisualBridge reporting.
    """
    from app.engine.tools.visual_html_core import _REACT_CDN_SCRIPTS

    safe_title = html_mod.escape(title.strip() or "Knowledge Check")
    safe_subtitle = html_mod.escape(
        subtitle.strip() or "Answer the questions below to test your understanding."
    )

    jsx = """const { useState, useCallback } = React;

// Sample questions — LLM replaces with domain-specific content
const QUESTIONS = [
  {
    id: 1,
    text: "Câu hỏi mẫu 1 — thay bằng nội dung thực tế?",
    options: ["Đáp án A", "Đáp án B", "Đáp án C", "Đáp án D"],
    correct: 0,
    explanation: "Giải thích tại sao đáp án A đúng."
  },
  {
    id: 2,
    text: "Câu hỏi mẫu 2 — thay bằng nội dung thực tế?",
    options: ["Đáp án A", "Đáp án B", "Đáp án C", "Đáp án D"],
    correct: 2,
    explanation: "Giải thích tại sao đáp án C đúng."
  },
  {
    id: 3,
    text: "Câu hỏi mẫu 3 — thay bằng nội dung thực tế?",
    options: ["Đáp án A", "Đáp án B", "Đáp án C", "Đáp án D"],
    correct: 1,
    explanation: "Giải thích tại sao đáp án B đúng."
  }
];

function report(k, p, s, st) {
  window.WiiiVisualBridge?.reportResult?.(k, p, s, st);
}

const quizStyles = {
  container: {
    maxWidth: 640,
    margin: '0 auto',
    fontFamily: 'var(--font, system-ui, sans-serif)',
  },
  header: {
    marginBottom: 16,
  },
  title: {
    fontSize: 18,
    fontWeight: 700,
    color: 'var(--text)',
    margin: '0 0 4px',
  },
  subtitle: {
    fontSize: 13,
    color: 'var(--text2)',
    margin: 0,
  },
  progressBar: {
    height: 6,
    borderRadius: 3,
    background: 'var(--bg3)',
    margin: '16px 0',
    overflow: 'hidden',
  },
  progressFill: {
    height: '100%',
    borderRadius: 3,
    background: '#D97757',
    transition: 'width 0.3s ease',
  },
  questionCard: {
    background: 'var(--bg)',
    border: '1px solid var(--border)',
    borderRadius: 14,
    padding: 20,
  },
  questionText: {
    fontSize: 16,
    fontWeight: 600,
    color: 'var(--text)',
    margin: '0 0 16px',
    lineHeight: 1.5,
  },
  option: {
    display: 'block',
    width: '100%',
    textAlign: 'left',
    padding: '12px 16px',
    margin: '8px 0',
    borderRadius: 10,
    border: '1px solid var(--border)',
    background: 'var(--bg2)',
    color: 'var(--text)',
    fontSize: 14,
    cursor: 'pointer',
    transition: 'all 0.15s ease',
  },
  optionSelected: {
    border: '2px solid #D97757',
    background: '#fef7f4',
  },
  optionCorrect: {
    border: '2px solid #10b981',
    background: '#ecfdf5',
  },
  optionWrong: {
    border: '2px solid #ef4444',
    background: '#fef2f2',
  },
  explanation: {
    marginTop: 12,
    padding: 12,
    borderRadius: 10,
    background: 'var(--bg2)',
    fontSize: 13,
    color: 'var(--text2)',
    lineHeight: 1.5,
  },
  btnRow: {
    display: 'flex',
    gap: 10,
    marginTop: 16,
  },
  btn: {
    padding: '10px 24px',
    borderRadius: 10,
    border: '1px solid var(--border)',
    background: 'var(--bg2)',
    color: 'var(--text)',
    fontSize: 14,
    fontWeight: 500,
    cursor: 'pointer',
    transition: 'background 0.15s',
  },
  btnPrimary: {
    background: '#D97757',
    color: '#fff',
    border: 'none',
  },
  scoreCard: {
    textAlign: 'center',
    padding: 32,
  },
  scoreNumber: {
    fontSize: 48,
    fontWeight: 800,
    color: '#D97757',
    margin: '16px 0 8px',
  },
  scoreLabel: {
    fontSize: 14,
    color: 'var(--text2)',
  },
};

function Quiz() {
  const [current, setCurrent] = useState(0);
  const [selected, setSelected] = useState(null);
  const [answered, setAnswered] = useState(false);
  const [score, setScore] = useState(0);
  const [finished, setFinished] = useState(false);

  const q = QUESTIONS[current];
  const progress = ((current + (answered ? 1 : 0)) / QUESTIONS.length) * 100;

  const handleSelect = useCallback((idx) => {
    if (answered) return;
    setSelected(idx);
  }, [answered]);

  const handleConfirm = useCallback(() => {
    if (selected === null) return;
    const isCorrect = selected === q.correct;
    setAnswered(true);
    if (isCorrect) setScore(s => s + 1);
    report('quiz_answer', {
      question: current + 1,
      selected: selected,
      correct: q.correct,
      isCorrect: isCorrect,
    }, isCorrect ? 'Correct answer!' : 'Wrong answer.', isCorrect ? 'correct' : 'wrong');
  }, [selected, current, q]);

  const handleNext = useCallback(() => {
    if (current + 1 >= QUESTIONS.length) {
      setFinished(true);
      report('quiz_complete', {
        total: QUESTIONS.length,
        score: score + (selected === q.correct ? 1 : 0),
      }, 'Quiz completed!', 'completed');
      return;
    }
    setCurrent(c => c + 1);
    setSelected(null);
    setAnswered(false);
  }, [current, score, selected, q]);

  if (finished) {
    const finalScore = score;
    return (
      <div style={quizStyles.container}>
        <div style={{...quizStyles.questionCard, ...quizStyles.scoreCard}}>
          <div style={quizStyles.title}>Quiz Complete!</div>
          <div style={quizStyles.scoreNumber}>{finalScore}/{QUESTIONS.length}</div>
          <div style={quizStyles.scoreLabel}>
            {finalScore >= QUESTIONS.length * 0.8 ? 'Excellent work!' :
             finalScore >= QUESTIONS.length * 0.5 ? 'Good effort!' : 'Keep practicing!'}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={quizStyles.container}>
      <div style={quizStyles.header}>
        <div style={quizStyles.title}>__TITLE__</div>
        <div style={quizStyles.subtitle}>__SUBTITLE__</div>
      </div>
      <div style={quizStyles.progressBar}>
        <div style={{...quizStyles.progressFill, width: progress + '%'}}></div>
      </div>
      <div style={{fontSize: 12, color: 'var(--text3)', marginBottom: 12}}>
        Question {current + 1} of {QUESTIONS.length}
      </div>
      <div style={quizStyles.questionCard}>
        <div style={quizStyles.questionText}>{q.text}</div>
        {q.options.map((opt, idx) => {
          let style = {...quizStyles.option};
          if (answered && idx === q.correct) style = {...style, ...quizStyles.optionCorrect};
          else if (answered && idx === selected) style = {...style, ...quizStyles.optionWrong};
          else if (idx === selected) style = {...style, ...quizStyles.optionSelected};
          return (
            <button key={idx} style={style} onClick={() => handleSelect(idx)}>
              {opt}
            </button>
          );
        })}
        {answered && q.explanation && (
          <div style={quizStyles.explanation}>{q.explanation}</div>
        )}
        <div style={quizStyles.btnRow}>
          {!answered ? (
            <button style={{...quizStyles.btn, ...quizStyles.btnPrimary}}
              onClick={handleConfirm} disabled={selected === null}>
              Confirm
            </button>
          ) : (
            <button style={{...quizStyles.btn, ...quizStyles.btnPrimary}}
              onClick={handleNext}>
              {current + 1 >= QUESTIONS.length ? 'Finish' : 'Next'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<Quiz />);"""

    # Inject title/subtitle into JSX
    jsx = jsx.replace("__TITLE__", safe_title).replace("__SUBTITLE__", safe_subtitle)

    quiz_tweaks = _tweaks_inject('{"--quiz-accent":"#D97757","--quiz-radius":"10"}')

    return (
        "<!DOCTYPE html>\n"
        '<html lang="vi"><head><meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        f"<style>{_DESIGN_CSS}</style>\n"
        f"{_REACT_CDN_SCRIPTS}\n"
        f"</head>\n<body>"
        f'<div id="root"></div>\n'
        f'<script type="text/babel">\n{jsx}\n</script>'
        f"{quiz_tweaks}"
        f"</body></html>"
    )


# ---------------------------------------------------------------------------
# Scaffold 3: Dashboard
# ---------------------------------------------------------------------------

def _build_dashboard_scaffold(title: str, subtitle: str = "", query: str = "") -> str:
    """Data dashboard with metric card slots and responsive grid.

    Features: KPI cards, chart placeholder slots, responsive CSS Grid,
    WiiiVisualBridge reporting on card clicks.
    """
    safe_title = html_mod.escape(title.strip() or "Dashboard")
    safe_subtitle = html_mod.escape(
        subtitle.strip() or "Key metrics and data at a glance."
    )
    dash_tweaks = _tweaks_inject('{"--dash-accent":"#2563eb","--dash-gap":"12"}')

    return f"""<!DOCTYPE html>
<html lang="vi"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>{_DESIGN_CSS}
.dash-container {{
  max-width: 960px; margin: 0 auto;
  font-family: var(--font, system-ui, sans-serif);
}}
.dash-header {{
  margin-bottom: 20px;
}}
.dash-title {{
  font-size: 20px; font-weight: 700; color: var(--text); margin: 0 0 4px;
}}
.dash-subtitle {{
  font-size: 13px; color: var(--text2); margin: 0;
}}
.dash-kpis {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px; margin-bottom: 20px;
}}
.dash-kpi {{
  border-radius: 14px; border: 1px solid var(--border);
  background: var(--bg); padding: 16px;
  cursor: pointer; transition: box-shadow 0.15s;
}}
.dash-kpi:hover {{
  box-shadow: 0 4px 16px var(--shadow);
}}
.dash-kpi-label {{
  font-size: 11px; text-transform: uppercase;
  letter-spacing: 0.04em; color: var(--text3);
  margin-bottom: 6px;
}}
.dash-kpi-value {{
  font-size: 28px; font-weight: 800; color: var(--text);
}}
.dash-kpi-change {{
  font-size: 12px; margin-top: 4px;
}}
.dash-kpi-change.positive {{ color: #10b981; }}
.dash-kpi-change.negative {{ color: #ef4444; }}
.dash-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 12px;
}}
.dash-card {{
  border-radius: 14px; border: 1px solid var(--border);
  background: var(--bg); padding: 16px;
  min-height: 200px;
}}
.dash-card-title {{
  font-size: 14px; font-weight: 600; color: var(--text);
  margin: 0 0 12px;
}}
.dash-slot {{
  border-radius: 10px; border: 2px dashed var(--border);
  background: var(--bg2); min-height: 150px;
  display: flex; align-items: center; justify-content: center;
  color: var(--text3); font-size: 13px;
}}
@media (max-width: 640px) {{
  .dash-kpis {{ grid-template-columns: 1fr 1fr; }}
  .dash-grid {{ grid-template-columns: 1fr; }}
}}
</style></head>
<body>
<div class="dash-container" data-sim-kind="dashboard">
  <div class="dash-header">
    <div class="dash-title">{safe_title}</div>
    <div class="dash-subtitle">{safe_subtitle}</div>
  </div>

  <div class="dash-kpis">
    <div class="dash-kpi" data-kpi="metric-1" onclick="reportKpi('metric-1')">
      <div class="dash-kpi-label">Metric A</div>
      <div class="dash-kpi-value" id="kpi-1">1,234</div>
      <div class="dash-kpi-change positive">+12.5%</div>
    </div>
    <div class="dash-kpi" data-kpi="metric-2" onclick="reportKpi('metric-2')">
      <div class="dash-kpi-label">Metric B</div>
      <div class="dash-kpi-value" id="kpi-2">567</div>
      <div class="dash-kpi-change negative">-3.2%</div>
    </div>
    <div class="dash-kpi" data-kpi="metric-3" onclick="reportKpi('metric-3')">
      <div class="dash-kpi-label">Metric C</div>
      <div class="dash-kpi-value" id="kpi-3">89.1%</div>
      <div class="dash-kpi-change positive">+1.8%</div>
    </div>
  </div>

  <div class="dash-grid">
    <div class="dash-card">
      <div class="dash-card-title">Chart Slot 1</div>
      <div class="dash-slot" id="chart-slot-1">Chart placeholder — fill with SVG/Canvas</div>
    </div>
    <div class="dash-card">
      <div class="dash-card-title">Chart Slot 2</div>
      <div class="dash-slot" id="chart-slot-2">Chart placeholder — fill with SVG/Canvas</div>
    </div>
    <div class="dash-card" style="grid-column: 1 / -1;">
      <div class="dash-card-title">Data Table</div>
      <div class="dash-slot" id="table-slot" style="min-height:120px;">Table placeholder — fill with data</div>
    </div>
  </div>
</div>
<script>
(function() {{
  function report(k,p,s,st) {{ window.WiiiVisualBridge?.reportResult?.(k,p,s,st); }}
  window.reportKpi = function(name) {{
    report('dashboard_interaction',
      {{card: name, action: 'click'}},
      'User clicked on ' + name + ' card.',
      'active');
  }};
}})();
</script>
{dash_tweaks}
</body></html>"""
