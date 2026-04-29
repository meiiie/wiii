# Wiii Pointy — local demo

A self-contained HTML page that simulates an LMS host calling the Wiii Pointy
bridge. Useful for visual QA without spinning up the iframe + backend.

## Build the bundle

```bash
cd wiii-desktop
npm run build:pointy
```

This produces `dist-pointy/wiii-pointy.umd.js` (and `.es.js`).

## Run the demo

```bash
cd wiii-desktop
npx vite preview --outDir dev-demo/pointy --port 4173
# or simply open the file in any browser:
#   start dev-demo/pointy/index.html      (Windows)
#   xdg-open dev-demo/pointy/index.html   (Linux)
```

Click the buttons in the bottom bar to simulate `ui.highlight`, `ui.scroll_to`,
`ui.navigate`, and `ui.show_tour` calls. The orange "W" cursor should fly to
the targeted element with the spotlight + tooltip overlay.

The demo posts messages to itself (origin == window.origin) so the bridge
accepts them. In production, replace `FAKE_IFRAME_ORIGIN` with the real
Wiii iframe origin (e.g., `https://wiii.holilihu.online`).
