"""Core HTML helpers shared by structured visual builders.

Provides:
- _DESIGN_CSS: Wiii design system with CSS variables
- _SVG_ICONS: Inline SVG icon library (no emoji dependency)
- _svg_icon(): Helper to render SVG icons by name
- _wrap_html(): Standard HTML wrapper
- _wrap_html_react(): React + Babel HTML wrapper
"""

from __future__ import annotations

import html as html_mod


# ---------------------------------------------------------------------------
# Inline SVG icon library — no emoji, no external dependencies.
# All icons use currentColor for automatic theme adaptation.
# Source: Claude Design "avoid AI slop" + professional icon standards.
# ---------------------------------------------------------------------------

_SVG_ICONS: dict[str, str] = {
    "play": (
        '<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 16 16"'
        ' fill="currentColor"><polygon points="4,2 14,8 4,14"/></svg>'
    ),
    "pause": (
        '<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 16 16"'
        ' fill="currentColor"><rect x="3" y="2" width="3.5" height="12" rx="1"/>'
        '<rect x="9.5" y="2" width="3.5" height="12" rx="1"/></svg>'
    ),
    "reset": (
        '<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 16 16"'
        ' fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"'
        ' stroke-linejoin="round"><path d="M2 8a6 6 0 0 1 11.3-2.8"/><polyline points="13.5,1.8 13.5,5.2 10.1,5.2"/>'
        '<path d="M14 8a6 6 0 0 1-11.3 2.8"/><polyline points="2.5,14.2 2.5,10.8 5.9,10.8"/></svg>'
    ),
    "check": (
        '<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 16 16"'
        ' fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"'
        ' stroke-linejoin="round"><polyline points="3,8 6.5,11.5 13,4.5"/></svg>'
    ),
    "close": (
        '<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 16 16"'
        ' fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">'
        '<line x1="3" y1="3" x2="13" y2="13"/><line x1="13" y1="3" x2="3" y2="13"/></svg>'
    ),
    "arrow_right": (
        '<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 16 16"'
        ' fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"'
        ' stroke-linejoin="round"><line x1="2" y1="8" x2="12" y2="8"/>'
        '<polyline points="9,4 13,8 9,12"/></svg>'
    ),
    "arrow_left": (
        '<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 16 16"'
        ' fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"'
        ' stroke-linejoin="round"><line x1="14" y1="8" x2="4" y2="8"/>'
        '<polyline points="7,4 3,8 7,12"/></svg>'
    ),
    "settings": (
        '<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 16 16"'
        ' fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round">'
        '<circle cx="8" cy="8" r="2.5"/><path d="M8 1.5v2M8 12.5v2M1.5 8h2M12.5 8h2'
        'M3.1 3.1l1.4 1.4M11.5 11.5l1.4 1.4M3.1 12.9l1.4-1.4M11.5 4.5l1.4-1.4"/></svg>'
    ),
    "chevron_down": (
        '<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 16 16"'
        ' fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"'
        ' stroke-linejoin="round"><polyline points="3,6 8,11 13,6"/></svg>'
    ),
}


def _svg_icon(name: str, size: int = 16, aria_label: str = "") -> str:
    """Render an inline SVG icon by name.

    Returns a self-contained <svg> tag using currentColor for theme adaptation.
    If name is not found, returns a small placeholder square.
    """
    template = _SVG_ICONS.get(name)
    if template is None:
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}"'
            f' viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">'
            f'<rect x="3" y="3" width="10" height="10" rx="2" opacity="0.3"/></svg>'
        )
    svg = template.replace("{w}", str(size)).replace("{h}", str(size))
    if aria_label:
        svg = svg.replace(">", f' aria-label="{html_mod.escape(aria_label)}">', 1)
    else:
        svg = svg.replace(">", ' aria-hidden="true">', 1)
    return svg


_DESIGN_CSS = """
:root {
  --bg: #ffffff; --bg2: #f8fafc; --bg3: #f1f5f9;
  --text: #1e293b; --text2: #475569; --text3: #94a3b8;
  --accent: #2563eb; --accent-bg: #eff6ff;
  --red: #ef4444; --red-bg: #fef2f2;
  --green: #10b981; --green-bg: #ecfdf5;
  --amber: #f59e0b; --amber-bg: #fffbeb;
  --purple: #8b5cf6; --purple-bg: #f5f3ff;
  --teal: #14b8a6; --teal-bg: #f0fdfa;
  --pink: #ec4899; --pink-bg: #fdf2f8;
  --border: #e2e8f0; --shadow: rgba(0,0,0,0.06);
  --radius: 12px; --radius-sm: 8px;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #0f172a; --bg2: #1e293b; --bg3: #334155;
    --text: #f1f5f9; --text2: #94a3b8; --text3: #64748b;
    --accent: #60a5fa; --accent-bg: #1e3a5f;
    --red: #f87171; --red-bg: #3b1111;
    --green: #34d399; --green-bg: #0d3320;
    --amber: #fbbf24; --amber-bg: #3b2e0a;
    --purple: #a78bfa; --purple-bg: #2d1b69;
    --teal: #2dd4bf; --teal-bg: #0d3331;
    --pink: #f472b6; --pink-bg: #3b1132;
    --border: #334155; --shadow: rgba(0,0,0,0.3);
  }
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  color: var(--text); background: transparent; line-height: 1.5;
  padding: 4px 0; font-size: 14px;
}
.widget-title {
  font-size: 13px; font-weight: 700; text-align: left;
  margin-bottom: 14px; color: var(--text2); letter-spacing: 0.02em;
}
.widget-subtitle {
  font-size: 11px; color: var(--text3); text-align: left;
  margin-top: -10px; margin-bottom: 12px;
}
.code-badge {
  display: inline-block; font-family: 'SF Mono', 'Fira Code', monospace;
  font-size: 13px; background: var(--bg3); color: var(--red);
  padding: 2px 8px; border-radius: 6px; font-weight: 500;
}
.label { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; color: var(--text3); }
"""


# ---------------------------------------------------------------------------
# Tweaks Protocol (from Claude Design)
# PostMessage-based live editing: host toggles panel, user adjusts params,
# changes persist via /*EDITMODE-BEGIN*/.../*EDITMODE-END*/ JSON markers.
# ---------------------------------------------------------------------------

_TWEAKS_CSS = """
.wiii-tweaks-panel{display:none;position:fixed;bottom:16px;right:16px;z-index:9999;
  width:280px;max-height:70vh;overflow-y:auto;background:var(--bg);
  border:1px solid var(--border);border-radius:12px;
  box-shadow:0 8px 32px rgba(0,0,0,0.15);padding:16px;
  font-family:system-ui,sans-serif;font-size:13px;color:var(--text);
  backdrop-filter:blur(8px);}
.wiii-tweaks-panel.active{display:block;}
.wiii-tweaks-header{display:flex;justify-content:space-between;align-items:center;
  margin-bottom:12px;padding-bottom:8px;border-bottom:1px solid var(--border);}
.wiii-tweaks-title{font-size:13px;font-weight:700;color:var(--text2);
  text-transform:uppercase;letter-spacing:0.05em;}
.wiii-tweaks-close{background:none;border:none;cursor:pointer;padding:4px;
  color:var(--text3);display:flex;align-items:center;}
.wiii-tweaks-close:hover{color:var(--text);}
.wiii-tweaks-group{margin-bottom:12px;}
.wiii-tweaks-group-label{font-size:11px;font-weight:600;color:var(--text3);
  text-transform:uppercase;letter-spacing:0.04em;margin-bottom:6px;}
.wiii-tweaks-row{display:flex;align-items:center;gap:8px;margin-bottom:6px;}
.wiii-tweaks-row label{flex:1;font-size:12px;color:var(--text2);min-width:80px;}
.wiii-tweaks-row input[type="range"]{flex:1;height:4px;-webkit-appearance:none;
  background:var(--bg3);border-radius:2px;outline:none;}
.wiii-tweaks-row input[type="color"]{width:28px;height:28px;border:1px solid var(--border);
  border-radius:6px;cursor:pointer;padding:0;}
.wiii-tweaks-row span{font-size:12px;color:var(--text3);min-width:36px;text-align:right;}
"""

_TWEAKS_JS = """(function(){
var _ts=document.getElementById('wiii-tweak-state');
if(!_ts)return;
var _rm=/\\/\\*EDITMODE-BEGIN\\*\\/([\\s\\S]*?)\\/\\*EDITMODE-END\\*\\//;
var _m=_rm.exec(_ts.textContent);
var _d=_m?JSON.parse(_m[1]):{};
function _apply(k,v){document.documentElement.style.setProperty(k,v);}
function _persist(){var j=JSON.stringify(_d);
_ts.textContent='/*EDITMODE-BEGIN*/'+j+'/*EDITMODE-END*/';
if(window.parent!==window)window.parent.postMessage({type:'__edit_mode_set_keys',edits:_d},'*');}
function _render(){var p=document.getElementById('wiii-tweaks-panel');if(!p)return;
p.innerHTML='';var h='<div class="wiii-tweaks-header"><span class="wiii-tweaks-title">Tweaks</span>'
+'<button class="wiii-tweaks-close" id="wiii-tweaks-close-btn">'+_closeSvg+'</button></div>';
var keys=Object.keys(_d);if(!keys.length){h+='<p style="font-size:12px;color:var(--text3)">No tweaks.</p>';}
for(var i=0;i<keys.length;i++){var k=keys[i],v=_d[k];var isColor=typeof v==='string'&&v[0]==='#';
if(isColor){h+='<div class="wiii-tweaks-row"><label>'+k+'</label>'
+'<input type="color" value="'+v+'" data-key="'+k+'"><span>'+v+'</span></div>';}
else{h+='<div class="wiii-tweaks-row"><label>'+k+'</label>'
+'<input type="range" min="0" max="100" value="'+v+'" data-key="'+k+'"><span>'+v+'</span></div>';}}
p.innerHTML=h;document.getElementById('wiii-tweaks-close-btn').onclick=function(){p.classList.remove('active');};
var inputs=p.querySelectorAll('input');for(var j=0;j<inputs.length;j++){inputs[j].oninput=function(e){
var key=e.target.getAttribute('data-key'),val=e.target.value;
_d[key]=val;_apply(key,val);var sp=e.target.nextElementSibling;if(sp)sp.textContent=val;_persist();};}}
var _closeSvg='<svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="3" y1="3" x2="13" y2="13"/><line x1="13" y1="3" x2="3" y2="13"/></svg>';
var _panel=document.createElement('div');_panel.id='wiii-tweaks-panel';_panel.className='wiii-tweaks-panel';
document.body.appendChild(_panel);
for(var k in _d)_apply(k,_d[k]);
window.addEventListener('message',function(e){
if(!e||!e.data||!e.data.type)return;
if(e.data.type==='__activate_edit_mode'){_render();_panel.classList.add('active');}
if(e.data.type==='__deactivate_edit_mode'){_panel.classList.remove('active');}});
if(window.parent!==window)window.parent.postMessage({type:'__edit_mode_available'},'*');
})();
"""

_TWEAKS_STATE_MARKER = (
    '<script id="wiii-tweak-state">'
    '/*EDITMODE-BEGIN*/{}/*EDITMODE-END*/'
    '</script>'
)


def _esc(s: str) -> str:
    """HTML-escape user content."""
    return html_mod.escape(str(s))


def _tweaks_inject(state_json: str = "{}") -> str:
    """Build the Tweaks protocol injection block for HTML output."""
    marker = (
        f'<script id="wiii-tweak-state">'
        f'/*EDITMODE-BEGIN*/{state_json}/*EDITMODE-END*/'
        f'</script>'
    )
    return f"<style>{_TWEAKS_CSS}</style>{marker}<script>{_TWEAKS_JS}</script>"


def _wrap_html(
    body_css: str,
    body_html: str,
    title: str = "",
    subtitle: str = "",
) -> str:
    """Wrap visual content in full HTML document with design system."""
    title_html = (
        f'<div class="wiii-frame-title widget-title">{_esc(title)}</div>'
        if title
        else ""
    )
    subtitle_html = (
        f'<div class="wiii-frame-subtitle widget-subtitle">{_esc(subtitle)}</div>'
        if subtitle
        else ""
    )
    return (
        "<!DOCTYPE html>\n"
        '<html lang="vi"><head><meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        '<meta name="color-scheme" content="light">\n'
        f"<style>{_DESIGN_CSS}\n{body_css}</style></head>\n"
        f"<body>{title_html}{subtitle_html}{body_html}"
        f"{_tweaks_inject()}</body></html>"
    )


# ---------------------------------------------------------------------------
# React + Babel CDN (pinned versions with integrity hashes)
# Source: Claude Design system prompt (April 2026)
# ---------------------------------------------------------------------------

_REACT_CDN_SCRIPTS = (
    '<script src="https://unpkg.com/react@18.3.1/umd/react.development.js"'
    ' integrity="sha384-hD6/rw4ppMLGNu3tX5cjIb+uRZ7UkRJ6BPkLpg4hAu/6onKUg4lLsHAs9EBPT82L"'
    ' crossorigin="anonymous"></script>\n'
    '<script src="https://unpkg.com/react-dom@18.3.1/umd/react-dom.development.js"'
    ' integrity="sha384-u6aeetuaXnQ38mYT8rp6sbXaQe3NL9t+IBXmnYxwkUI2Hw4bsp2Wvmx4yRQF1uAm"'
    ' crossorigin="anonymous"></script>\n'
    '<script src="https://unpkg.com/@babel/standalone@7.29.0/babel.min.js"'
    ' integrity="sha384-m08KidiNqLdpJqLq95G/LEi8Qvjl/xUYll3QILypMoQ65QorJ9Lvtp2RXYGBFj1y"'
    ' crossorigin="anonymous"></script>'
)


def _wrap_html_react(
    body_css: str,
    body_jsx: str,
    title: str = "",
    subtitle: str = "",
) -> str:
    """Wrap React JSX content in full HTML with Babel transpilation.

    Use for interactive widgets (quiz, dashboard) that benefit from React
    state management. For simulations, prefer Canvas + vanilla JS.

    Rules (from Claude Design):
    - Give global-scoped style objects SPECIFIC names (never ``const styles = {}``)
    - Share components via ``Object.assign(window, { Component })``
    - Keep files under 1000 lines
    """
    title_html = (
        f'<div class="wiii-frame-title widget-title">{_esc(title)}</div>'
        if title
        else ""
    )
    subtitle_html = (
        f'<div class="wiii-frame-subtitle widget-subtitle">{_esc(subtitle)}</div>'
        if subtitle
        else ""
    )
    return (
        "<!DOCTYPE html>\n"
        '<html lang="vi"><head><meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        '<meta name="color-scheme" content="light">\n'
        f"<style>{_DESIGN_CSS}\n{body_css}</style>\n"
        f"{_REACT_CDN_SCRIPTS}\n"
        f"</head>\n<body>"
        f"{title_html}{subtitle_html}"
        f'<div id="root"></div>\n'
        f'<script type="text/babel">\n{body_jsx}\n</script>'
        f"{_tweaks_inject()}</body></html>"
    )
