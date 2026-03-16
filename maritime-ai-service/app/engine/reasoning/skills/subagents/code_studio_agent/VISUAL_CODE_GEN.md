---
id: wiii-visual-code-gen
name: visual-code-gen
skill_type: subagent
node: code_studio_agent
description: Design philosophy, examples, and quality guidelines for LLM-first HTML/SVG/JS visual generation. Use when creating any visual via tool_create_visual_code.
version: "4.0.0"
---

# Visual Code Generation — LLM-First

Bạn tạo visual bằng cách viết HTML/CSS/SVG/JS trực tiếp — mỗi visual unique, tailored chính xác theo context của user. Không dùng template. Model tự quyết complexity phù hợp với nội dung.

## Design Philosophy

Tự hỏi: **"Visual này có khiến người ta dừng cuộn và nói 'whoa' không?"**

- Animation là mặc định, tĩnh là ngoại lệ
- Bold và unexpected hơn là safe và conventional
- Mỗi visual KHÁC NHAU — tailored cho context cụ thể
- Đơn giản khi cần đơn giản, phức tạp khi cần phức tạp

### Chất lượng tối thiểu

- Phải có đồ họa thật — SVG shapes, styled elements, visual content
- Phải hoàn chỉnh — chạy được ngay, không placeholder
- Phải có hover/transition cho elements tương tác
- Responsive: dùng viewBox, %, @media khi cần

### Tránh AI-Slop

- KHÔNG centered layouts đồng loạt + purple gradients
- KHÔNG cookie-cutter patterns lặp đi lặp lại
- KHÔNG text-only cards giả vờ là visual
- Mỗi visual phải có character riêng phù hợp với nội dung

## Environment

```
CSS Variables có sẵn (dark mode tự động):
  --bg, --bg2, --bg3, --text, --text2, --text3
  --accent, --accent-bg, --green, --green-bg, --purple, --purple-bg
  --amber, --amber-bg, --teal, --teal-bg, --pink, --pink-bg
  --red, --red-bg, --border, --shadow, --radius, --radius-sm

CDN whitelist (import từ cdnjs.cloudflare.com nếu cần):
  D3.js v7, Chart.js v4, Three.js r160, KaTeX, Tailwind CSS v3.4

Built-in (không cần CDN):
  SVG, Canvas 2D, CSS Animations, requestAnimationFrame
```

Chỉ viết body content: `<style>` + HTML + `<script>`. Shell tự wrap `<!DOCTYPE>`.

## Thinking — Trước khi viết code

1. Thông điệp cốt lõi cần truyền đạt là gì?
2. Visual metaphor nào truyền tải tốt nhất?
3. Mức độ tương tác phù hợp? (static diagram? animated? interactive controls?)
4. Color palette nào phù hợp với nội dung?

## Example A: Mô phỏng vật lý (con lắc đơn)

Khi nào dùng: user hỏi về vật lý, muốn thấy hiện tượng hoạt động.
Complexity cao: SVG animated + sliders + stats + energy bars.

```html
<style>
.ctrl{display:flex;align-items:center;gap:10px;margin:6px 0;font-size:13px;color:var(--text2)}
.ctrl input[type=range]{flex:1;accent-color:var(--accent)}
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
  border:1px solid var(--border);border-radius:6px;cursor:pointer;transition:all .15s}
.btn-row button:hover{background:var(--bg3);border-color:var(--accent)}
</style>
<svg id="sim" width="100%" viewBox="0 0 680 340">
  <defs><radialGradient id="bg" cx="40%" cy="35%"><stop offset="0%" stop-color="var(--purple)"/><stop offset="100%" stop-color="var(--accent)"/></radialGradient></defs>
  <line x1="100" y1="30" x2="580" y2="30" stroke="var(--border)" stroke-width="3" stroke-linecap="round"/>
  <path id="trail" d="" fill="none" stroke="var(--accent)" stroke-width="1.5" opacity="0.3"/>
  <line id="str" x1="340" y1="30" x2="340" y2="230" stroke="var(--text2)" stroke-width="1.5"/>
  <circle id="bob" cx="340" cy="230" r="20" fill="url(#bg)"/>
  <path id="arc" d="" fill="none" stroke="var(--amber)" stroke-width="1" stroke-dasharray="3 2"/>
  <text id="albl" x="0" y="0" fill="var(--amber)" font-size="11"></text>
</svg>
<div class="stats">
  <div class="stat"><div class="stat-label">Chu kỳ T</div><div class="stat-val" id="sT">—</div></div>
  <div class="stat"><div class="stat-label">Vận tốc</div><div class="stat-val" id="sV">—</div></div>
  <div class="stat"><div class="stat-label">Góc</div><div class="stat-val" id="sA">—</div></div>
</div>
<div style="font-size:12px;color:var(--text3);margin:4px 0 2px">Năng lượng</div>
<div class="bar-wrap"><span class="bar-label" style="color:var(--purple)">Eₚ</span><div class="bar-bg"><div class="bar-fill" id="pe" style="background:var(--purple);width:50%"></div></div></div>
<div class="bar-wrap"><span class="bar-label" style="color:var(--green)">Eₖ</span><div class="bar-bg"><div class="bar-fill" id="ke" style="background:var(--green);width:50%"></div></div></div>
<div class="ctrl"><span>Chiều dài</span><input type="range" id="sL" min="60" max="250" value="200" oninput="up()"><span class="val" id="vL">2.0 m</span></div>
<div class="ctrl"><span>Góc</span><input type="range" id="sAng" min="5" max="80" value="30" oninput="up()"><span class="val" id="vA">30°</span></div>
<div class="ctrl"><span>g</span><input type="range" id="sG" min="1" max="25" value="10" step="0.5" oninput="up()"><span class="val" id="vG">10.0</span></div>
<div class="btn-row"><button onclick="reset()">Đặt lại</button><button id="bp" onclick="tog()">Tạm dừng</button></div>
<script>
const PX=340,PY=30;let L=200,t0=Math.PI/6,g=10,w=0,th=Math.PI/6,p=false,pts=[];
function up(){L=+document.getElementById('sL').value;t0=+document.getElementById('sAng').value*Math.PI/180;g=+document.getElementById('sG').value;document.getElementById('vL').textContent=(L/100).toFixed(1)+' m';document.getElementById('vA').textContent=Math.round(t0*180/Math.PI)+'°';document.getElementById('vG').textContent=g.toFixed(1);th=t0;w=0;pts=[];document.getElementById('sT').textContent=(2*Math.PI*Math.sqrt(L/100/g)).toFixed(2)+'s';}
function pos(a){return{x:PX+L*Math.sin(a),y:PY+L*Math.cos(a)};}
function draw(){const q=pos(th);document.getElementById('str').setAttribute('x2',q.x);document.getElementById('str').setAttribute('y2',q.y);document.getElementById('bob').setAttribute('cx',q.x);document.getElementById('bob').setAttribute('cy',q.y);document.getElementById('sV').textContent=Math.abs(w*L/100).toFixed(2)+' m/s';document.getElementById('sA').textContent=(th*180/Math.PI).toFixed(1)+'°';const mPE=1-Math.cos(t0),cPE=1-Math.cos(th),pp=mPE>0?(cPE/mPE)*100:0;document.getElementById('pe').style.width=Math.round(pp)+'%';document.getElementById('ke').style.width=Math.round(100-pp)+'%';pts.push(q);if(pts.length>120)pts.shift();if(pts.length>1){let d='M'+pts[0].x.toFixed(1)+' '+pts[0].y.toFixed(1);for(let i=1;i<pts.length;i++)d+='L'+pts[i].x.toFixed(1)+' '+pts[i].y.toFixed(1);document.getElementById('trail').setAttribute('d',d);}const R=40,a1y=PY+R,a2x=PX+R*Math.sin(th),a2y=PY+R*Math.cos(th);document.getElementById('arc').setAttribute('d','M'+PX+' '+a1y+'A'+R+' '+R+' 0 0 '+(th>=0?1:0)+' '+a2x.toFixed(1)+' '+a2y.toFixed(1));document.getElementById('albl').setAttribute('x',(PX+52*Math.sin(th/2)).toFixed(1));document.getElementById('albl').setAttribute('y',(PY+52*Math.cos(th/2)).toFixed(1));document.getElementById('albl').textContent=Math.abs(th*180/Math.PI).toFixed(0)+'°';}
function step(){if(!p){const dt=0.016;w+=(-g*100/L*Math.sin(th))*dt;w*=0.9995;th+=w*dt;}draw();requestAnimationFrame(step);}
function reset(){up();p=false;document.getElementById('bp').textContent='Tạm dừng';}
function tog(){p=!p;document.getElementById('bp').textContent=p?'Tiếp tục':'Tạm dừng';}
up();step();
</script>
```

## Example B: Sơ đồ kiến trúc (SVG layers)

Khi nào dùng: user hỏi về hệ thống, kiến trúc, flow.
Complexity trung bình: SVG tĩnh + hover effects + arrow markers.

```html
<style>
.layer{transition:all .2s;cursor:default}
.layer:hover{opacity:0.85}
.layer:hover rect{stroke-width:2.5}
</style>
<svg viewBox="0 0 600 360" style="width:100%;height:auto">
  <defs><marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0,0L10,5L0,10Z" fill="var(--text3)"/></marker></defs>
  <g class="layer"><rect x="50" y="20" width="500" height="80" rx="12" fill="var(--accent)" opacity="0.08" stroke="var(--accent)" stroke-width="1.5"/><text x="300" y="48" text-anchor="middle" fill="var(--accent)" font-size="13" font-weight="700">API GATEWAY</text><text x="300" y="68" text-anchor="middle" fill="var(--text2)" font-size="11">Xác thực • Rate Limiting • Load Balancing</text></g>
  <line x1="300" y1="100" x2="300" y2="130" stroke="var(--text3)" stroke-width="1.5" marker-end="url(#arr)"/>
  <g class="layer"><rect x="50" y="130" width="500" height="80" rx="12" fill="var(--green)" opacity="0.08" stroke="var(--green)" stroke-width="1.5"/><text x="300" y="158" text-anchor="middle" fill="var(--green)" font-size="13" font-weight="700">SERVICE LAYER</text><text x="300" y="178" text-anchor="middle" fill="var(--text2)" font-size="11">Business Logic • Microservices • Event-Driven</text></g>
  <line x1="300" y1="210" x2="300" y2="240" stroke="var(--text3)" stroke-width="1.5" marker-end="url(#arr)"/>
  <g class="layer"><rect x="50" y="240" width="500" height="80" rx="12" fill="var(--purple)" opacity="0.08" stroke="var(--purple)" stroke-width="1.5"/><text x="300" y="268" text-anchor="middle" fill="var(--purple)" font-size="13" font-weight="700">DATA LAYER</text><text x="300" y="288" text-anchor="middle" fill="var(--text2)" font-size="11">PostgreSQL • Redis Cache • Object Storage</text></g>
</svg>
```

## Example C: So sánh (CSS Grid + hover)

Khi nào dùng: user hỏi so sánh 2+ phương án.
Complexity thấp-trung: styled divs + hover lift + responsive.

```html
<style>
.comp{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.side{padding:16px;border-radius:var(--radius);border:1.5px solid var(--border);transition:all .2s}
.side:hover{transform:translateY(-3px);box-shadow:0 8px 24px var(--shadow)}
.side h3{font-size:15px;font-weight:700;margin-bottom:4px}
.side .sub{font-size:11px;color:var(--text3);margin-bottom:12px}
.side ul{list-style:none;padding:0}
.side li{padding:6px 0;font-size:13px;color:var(--text2);border-bottom:1px solid var(--bg3)}
.side li::before{content:"→ ";color:var(--text3)}
.hl{margin-top:12px;padding:8px 12px;border-radius:var(--radius-sm);font-size:12px;font-weight:600}
@media(max-width:500px){.comp{grid-template-columns:1fr}}
</style>
<div class="comp">
  <div class="side" style="border-color:var(--accent)">
    <h3 style="color:var(--accent)">Phương án A</h3>
    <div class="sub">Mô tả ngắn</div>
    <ul><li>Điểm 1</li><li>Điểm 2</li><li>Điểm 3</li></ul>
    <div class="hl" style="background:color-mix(in srgb,var(--accent) 10%,transparent);color:var(--accent)">Kết luận A</div>
  </div>
  <div class="side" style="border-color:var(--green)">
    <h3 style="color:var(--green)">Phương án B</h3>
    <div class="sub">Mô tả ngắn</div>
    <ul><li>Điểm 1</li><li>Điểm 2</li><li>Điểm 3</li></ul>
    <div class="hl" style="background:color-mix(in srgb,var(--green) 10%,transparent);color:var(--green)">Kết luận B</div>
  </div>
</div>
```
