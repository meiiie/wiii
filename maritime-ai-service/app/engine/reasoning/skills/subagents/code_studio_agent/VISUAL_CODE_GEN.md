---
id: wiii-visual-code-gen
name: Visual Code Generation
skill_type: subagent
node: code_studio_agent
description: Design system reference, simulation patterns, and interactive visual examples for code_html generation. Includes complete pendulum simulation pattern.
version: "2.0.0"
---

# Visual Code Generation Skill

Khi tạo visual inline bằng code_html, Wiii viết HTML/CSS/SVG/JS — mỗi visual unique, custom, chuyên nghiệp.

## Design System CSS Variables

code_html được wrap trong design system shell có sẵn các CSS vars:

```
--bg: #ffffff    --bg2: #f8fafc   --bg3: #f1f5f9
--text: #1e293b  --text2: #475569  --text3: #94a3b8
--accent: #2563eb --green: #10b981 --purple: #8b5cf6
--amber: #f59e0b  --teal: #14b8a6  --pink: #ec4899
--border: #e2e8f0  --shadow: rgba(0,0,0,0.06)
--radius: 12px     --radius-sm: 8px
Dark mode tự động qua CSS vars — KHÔNG cần media query.
```

## Quy tắc viết code_html

1. CHỈ viết body content (CSS + HTML + JS). KHÔNG viết <!DOCTYPE>, <html>, <head>, <body>.
2. Dùng `<style>` block cho CSS, sau đó HTML, cuối cùng `<script>`.
3. LUÔN dùng CSS variables: `color: var(--accent)` KHÔNG `color: #2563eb`.
4. Font-family đã có sẵn — không cần khai báo lại.
5. PHẢI có interactive elements: sliders, buttons, stats display.
6. Dùng SVG cho đồ họa tĩnh/animated. Dùng Canvas cho vật lý realtime.

## Pattern 1: Mô phỏng vật lý (SVG + JavaScript)

Mẫu hoàn chỉnh cho mô phỏng tương tác — con lắc, lò xo, va chạm, quỹ đạo.

```html
<style>
.ctrl{display:flex;align-items:center;gap:10px;margin:6px 0;font-size:13px;color:var(--text2)}
.ctrl input[type=range]{flex:1}
.val{min-width:52px;text-align:right;font-weight:500;font-size:13px;color:var(--text)}
.bar-wrap{display:flex;gap:8px;margin:4px 0}
.bar-label{font-size:12px;min-width:28px;color:var(--text2)}
.bar-bg{flex:1;height:14px;border-radius:7px;background:var(--bg3);overflow:hidden}
.bar-fill{height:100%;border-radius:7px;transition:width .05s}
.stats{display:flex;gap:16px;flex-wrap:wrap;margin:8px 0}
.stat{background:var(--bg2);border-radius:var(--radius-sm);padding:8px 12px;flex:1;min-width:90px}
.stat-label{font-size:11px;color:var(--text3)}
.stat-val{font-size:18px;font-weight:500;color:var(--text);margin-top:2px}
.btn-row{display:flex;gap:8px;margin:8px 0}
.btn-row button{padding:6px 14px;font-size:13px;background:transparent;color:var(--text);
  border:1px solid var(--border);border-radius:6px;cursor:pointer}
</style>
<svg id="sim-svg" width="100%" viewBox="0 0 680 340">
  <defs>
    <radialGradient id="bob-grad" cx="40%" cy="35%">
      <stop offset="0%" stop-color="var(--purple)"/>
      <stop offset="100%" stop-color="var(--accent)"/>
    </radialGradient>
  </defs>
  <line x1="100" y1="30" x2="580" y2="30" stroke="var(--border)" stroke-width="3" stroke-linecap="round"/>
  <rect x="332" y="18" width="16" height="16" rx="3" fill="var(--text3)" opacity="0.4"/>
  <path id="trail" d="" fill="none" stroke="var(--accent)" stroke-width="1.5" opacity="0.3"/>
  <line id="string" x1="340" y1="30" x2="340" y2="230" stroke="var(--text2)" stroke-width="1.5"/>
  <circle id="bob" cx="340" cy="230" r="20" fill="url(#bob-grad)"/>
  <text class="ts" x="340" y="16" text-anchor="middle" fill="var(--text3)" font-size="11px">Điểm treo</text>
  <path id="angle-arc" d="" fill="none" stroke="var(--amber)" stroke-width="1" stroke-dasharray="3 2"/>
  <text id="angle-label" x="0" y="0" fill="var(--amber)" font-size="11px"></text>
</svg>
<div class="stats">
  <div class="stat"><div class="stat-label">Chu kỳ T</div><div class="stat-val" id="s-period">—</div></div>
  <div class="stat"><div class="stat-label">Vận tốc</div><div class="stat-val" id="s-vel">—</div></div>
  <div class="stat"><div class="stat-label">Góc hiện tại</div><div class="stat-val" id="s-angle">—</div></div>
</div>
<div style="font-size:12px;color:var(--text3);margin:4px 0 2px">Năng lượng</div>
<div class="bar-wrap">
  <span class="bar-label" style="color:var(--purple)">Eₚ</span>
  <div class="bar-bg"><div class="bar-fill" id="pe-bar" style="background:var(--purple);width:50%"></div></div>
</div>
<div class="bar-wrap">
  <span class="bar-label" style="color:var(--green)">Eₖ</span>
  <div class="bar-bg"><div class="bar-fill" id="ke-bar" style="background:var(--green);width:50%"></div></div>
</div>
<div class="ctrl">
  <span>Chiều dài</span>
  <input type="range" id="sl-len" min="60" max="250" value="200" step="1" oninput="updateParam()">
  <span class="val" id="v-len">2.0 m</span>
</div>
<div class="ctrl">
  <span>Góc lệch</span>
  <input type="range" id="sl-ang" min="5" max="80" value="30" step="1" oninput="updateParam()">
  <span class="val" id="v-ang">30°</span>
</div>
<div class="ctrl">
  <span>Trọng lực</span>
  <input type="range" id="sl-g" min="1" max="25" value="10" step="0.5" oninput="updateParam()">
  <span class="val" id="v-g">10.0 m/s²</span>
</div>
<div class="btn-row">
  <button onclick="resetSim()">Đặt lại</button>
  <button id="btn-pause" onclick="togglePause()">Tạm dừng</button>
</div>
<script>
const PX=340,PY=30;
let L=200,theta0=Math.PI/6,g=10,omega=0,theta=Math.PI/6;
let paused=false,raf,trailPts=[];
const bob=document.getElementById('bob'),str=document.getElementById('string');
const trail=document.getElementById('trail'),arc=document.getElementById('angle-arc'),aLbl=document.getElementById('angle-label');
function updateParam(){
  L=+document.getElementById('sl-len').value;
  theta0=+document.getElementById('sl-ang').value*Math.PI/180;
  g=+document.getElementById('sl-g').value;
  document.getElementById('v-len').textContent=(L/100).toFixed(1)+' m';
  document.getElementById('v-ang').textContent=Math.round(theta0*180/Math.PI)+'°';
  document.getElementById('v-g').textContent=g.toFixed(1)+' m/s²';
  theta=theta0;omega=0;trailPts=[];
  document.getElementById('s-period').textContent=(2*Math.PI*Math.sqrt(L/100/g)).toFixed(2)+'s';
}
function pos(th){return{x:PX+L*Math.sin(th),y:PY+L*Math.cos(th)};}
function draw(){
  const p=pos(theta);
  str.setAttribute('x2',p.x);str.setAttribute('y2',p.y);
  bob.setAttribute('cx',p.x);bob.setAttribute('cy',p.y);
  const speed=Math.abs(omega*L/100);
  document.getElementById('s-vel').textContent=speed.toFixed(2)+' m/s';
  document.getElementById('s-angle').textContent=(theta*180/Math.PI).toFixed(1)+'°';
  const maxPE=1-Math.cos(theta0),curPE=1-Math.cos(theta);
  const pePct=maxPE>0?(curPE/maxPE)*100:0;
  document.getElementById('pe-bar').style.width=Math.round(pePct)+'%';
  document.getElementById('ke-bar').style.width=Math.round(100-pePct)+'%';
  trailPts.push({x:p.x,y:p.y});if(trailPts.length>120)trailPts.shift();
  if(trailPts.length>1){
    let d='M'+trailPts[0].x.toFixed(1)+' '+trailPts[0].y.toFixed(1);
    for(let i=1;i<trailPts.length;i++)d+='L'+trailPts[i].x.toFixed(1)+' '+trailPts[i].y.toFixed(1);
    trail.setAttribute('d',d);
  }
  const aR=40,ax1=PX,ay1=PY+aR;
  const ax2=PX+aR*Math.sin(theta),ay2=PY+aR*Math.cos(theta);
  const sw=theta>=0?1:0;
  arc.setAttribute('d','M'+ax1+' '+ay1+'A'+aR+' '+aR+' 0 0 '+sw+' '+ax2.toFixed(1)+' '+ay2.toFixed(1));
  aLbl.setAttribute('x',(PX+52*Math.sin(theta/2)).toFixed(1));
  aLbl.setAttribute('y',(PY+52*Math.cos(theta/2)).toFixed(1));
  aLbl.textContent=Math.abs(theta*180/Math.PI).toFixed(0)+'°';
}
function step(){
  if(!paused){const dt=0.016,gPx=g*100;omega+=(-gPx/L*Math.sin(theta))*dt;omega*=0.9995;theta+=omega*dt;}
  draw();raf=requestAnimationFrame(step);
}
function resetSim(){updateParam();paused=false;document.getElementById('btn-pause').textContent='Tạm dừng';}
function togglePause(){paused=!paused;document.getElementById('btn-pause').textContent=paused?'Tiếp tục':'Tạm dừng';}
updateParam();step();
</script>
```

## Pattern 2: Sơ đồ kiến trúc (SVG tĩnh + hover)

```html
<style>
.arch-svg text{font-family:inherit}
.layer-box{transition:opacity .15s}
.layer-box:hover{opacity:0.85}
</style>
<svg viewBox="0 0 600 360" style="width:100%;height:auto">
  <defs><marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto">
    <path d="M0,0L10,5L0,10Z" fill="var(--text3)"/></marker></defs>
  <!-- Layer 1 -->
  <g class="layer-box">
    <rect x="50" y="20" width="500" height="80" rx="12" fill="var(--accent)" opacity="0.1" stroke="var(--accent)" stroke-width="1.5"/>
    <text x="300" y="48" text-anchor="middle" fill="var(--accent)" font-size="13" font-weight="700">API GATEWAY</text>
    <text x="300" y="68" text-anchor="middle" fill="var(--text2)" font-size="11">Xác thực JWT • Rate Limiting • Load Balancing</text>
    <rect x="80" y="76" width="80" height="18" rx="4" fill="var(--accent)" opacity="0.15"/>
    <text x="120" y="89" text-anchor="middle" fill="var(--accent)" font-size="10">Auth</text>
    <rect x="180" y="76" width="80" height="18" rx="4" fill="var(--accent)" opacity="0.15"/>
    <text x="220" y="89" text-anchor="middle" fill="var(--accent)" font-size="10">Router</text>
  </g>
  <!-- Arrow -->
  <line x1="300" y1="100" x2="300" y2="130" stroke="var(--text3)" stroke-width="1.5" marker-end="url(#arr)"/>
  <!-- Layer 2 -->
  <g class="layer-box">
    <rect x="50" y="130" width="500" height="80" rx="12" fill="var(--green)" opacity="0.1" stroke="var(--green)" stroke-width="1.5"/>
    <text x="300" y="158" text-anchor="middle" fill="var(--green)" font-size="13" font-weight="700">SERVICE LAYER</text>
    <text x="300" y="178" text-anchor="middle" fill="var(--text2)" font-size="11">Business Logic • Event-Driven • Microservices</text>
  </g>
  <!-- Arrow -->
  <line x1="300" y1="210" x2="300" y2="240" stroke="var(--text3)" stroke-width="1.5" marker-end="url(#arr)"/>
  <!-- Layer 3 -->
  <g class="layer-box">
    <rect x="50" y="240" width="500" height="80" rx="12" fill="var(--purple)" opacity="0.1" stroke="var(--purple)" stroke-width="1.5"/>
    <text x="300" y="268" text-anchor="middle" fill="var(--purple)" font-size="13" font-weight="700">DATA LAYER</text>
    <text x="300" y="288" text-anchor="middle" fill="var(--text2)" font-size="11">PostgreSQL • Redis Cache • Object Storage</text>
  </g>
</svg>
```

## Pattern 3: So sánh tương tác (HTML + CSS)

```html
<style>
.comp{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.side{padding:16px;border-radius:var(--radius);border:1.5px solid var(--border);transition:transform .15s}
.side:hover{transform:translateY(-2px)}
.side h3{font-size:15px;font-weight:700;margin-bottom:4px}
.side .sub{font-size:11px;color:var(--text3);margin-bottom:12px}
.side ul{list-style:none;padding:0}
.side li{padding:6px 0;font-size:13px;color:var(--text2);border-bottom:1px solid var(--bg3)}
.side li::before{content:"→ ";color:var(--text3)}
.highlight{margin-top:12px;padding:8px 12px;border-radius:var(--radius-sm);font-size:12px;font-weight:600}
@media(max-width:500px){.comp{grid-template-columns:1fr}}
</style>
<div class="comp">
  <div class="side" style="border-color:var(--accent)">
    <h3 style="color:var(--accent)">Phương án A</h3>
    <div class="sub">Mô tả ngắn gọn</div>
    <ul><li>Ưu điểm 1</li><li>Ưu điểm 2</li><li>Ưu điểm 3</li></ul>
    <div class="highlight" style="background:color-mix(in srgb,var(--accent) 10%,transparent);color:var(--accent)">Kết luận cho phương án A</div>
  </div>
  <div class="side" style="border-color:var(--green)">
    <h3 style="color:var(--green)">Phương án B</h3>
    <div class="sub">Mô tả ngắn gọn</div>
    <ul><li>Ưu điểm 1</li><li>Ưu điểm 2</li><li>Ưu điểm 3</li></ul>
    <div class="highlight" style="background:color-mix(in srgb,var(--green) 10%,transparent);color:var(--green)">Kết luận cho phương án B</div>
  </div>
</div>
```

## Nguyên tắc chất lượng

1. MỌI mô phỏng PHẢI có: sliders, stats realtime, nút đặt lại/tạm dừng.
2. MỌI sơ đồ PHẢI có: màu phân biệt layers, mô tả từng layer, hover effect.
3. MỌI so sánh PHẢI có: 2 cột rõ ràng, highlight kết luận, responsive mobile.
4. Dùng SVG gradient cho visual polish (radialGradient, linearGradient).
5. Dùng CSS transition/animation cho tương tác mượt.
6. KHÔNG bao giờ trả visual chỉ có text — phải có đồ họa thật (shapes, lines, animations).
