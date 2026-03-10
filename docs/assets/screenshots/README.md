# Documentation Screenshots

Store project screenshots used for docs, plans, and verification here instead of the repository root.

Current folders:
- `debug/`: debug captures and investigation screenshots
- `deploy/`: deployment and Swagger screenshots
- `desktop/`: full desktop UI screenshots
- `embed/`: embed mode screenshots
- `lms/`: LMS integration screenshots
- `magic-link/`: email login and verification screenshots
- `sidebar/`: sidebar/chat UI screenshots
- `tmp/`: temporary captures that should not be committed long-term

Rules:
- Do not place screenshots in the repository root.
- Put stable documentation screenshots in the closest matching folder above.
- Use `tmp/` for short-lived captures while debugging or validating UI work.
- If a new feature needs many screenshots, create a new subfolder here rather than adding files at the top level.
- Desktop capture scripts should write temporary output into `tmp/`, then promote files into a stable folder only if they are worth keeping.