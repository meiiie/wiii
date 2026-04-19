"""Core HTML helpers shared by structured visual builders."""

from __future__ import annotations

import html as html_mod


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


def _esc(s: str) -> str:
    """HTML-escape user content."""
    return html_mod.escape(str(s))


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
        f"<body>{title_html}{subtitle_html}{body_html}</body></html>"
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
        f"</body></html>"
    )
