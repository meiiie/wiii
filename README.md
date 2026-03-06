# Wiii

Wiii is a monorepo for an AI platform that combines a FastAPI backend, a Tauri desktop client, retrieval and memory pipelines, multi-tenant organization support, LMS integrations, and an embed application served at `/embed/`.

This repository is structured for active product engineering rather than as a minimal example. This README focuses on the things engineers usually need first: repository shape, local startup, current deployment model, and where to find subsystem documentation.

## Repository Overview

- `maritime-ai-service/`: backend services, APIs, orchestration, integrations, data access, deployment
- `wiii-desktop/`: Tauri desktop app, frontend code, embed app, frontend scripts
- `docs/`: committed plans, design notes, and documentation assets
- `Documents/`: supporting reference material and vendor research
- `tools/`: one-off utilities, fixtures, and local helpers kept out of the root
- `.claude/`: agent workflows, reports, and internal project knowledge

## Core Areas

- FastAPI service layer with organization-aware middleware and integrations
- Multi-agent orchestration, retrieval, memory, and tool execution flows
- Tauri desktop client built with React, TypeScript, Zustand, and Vite
- LMS and webhook integration paths
- Embed application for iframe-based host integrations
- Production deployment via Docker Compose, Nginx, and host-level TLS termination

## Project Layout

```text
.
├── maritime-ai-service/
│   ├── app/
│   ├── docs/
│   ├── scripts/
│   └── tests/
├── wiii-desktop/
│   ├── src/
│   ├── src-tauri/
│   ├── docs/
│   ├── scripts/
│   └── dist-embed/
├── docs/
│   ├── plans/
│   └── assets/
├── Documents/
└── tools/
```

## Quick Start

### Backend

```bash
cd maritime-ai-service
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
docker compose up -d postgres neo4j minio
alembic upgrade head
uvicorn app.main:app --reload
```

### Desktop

```bash
cd wiii-desktop
npm install
npm run dev
```

### Full Desktop App

```bash
cd wiii-desktop
npx tauri dev
```

## Build and Test

### Backend tests

```bash
cd maritime-ai-service
set PYTHONIOENCODING=utf-8 && pytest tests/unit/ -p no:capture --tb=short -q
```

### Desktop tests

```bash
cd wiii-desktop
npx vitest run
npx tsc --noEmit
```

### Embed bundle

```bash
cd wiii-desktop
npm run build:embed
```

## Deployment Status

Production deployment no longer needs `wiii-desktop/dist-embed/` to exist in the checked-out server repository.

The current production path uses CI-built immutable images that already contain embed assets.

The remaining operational step is to validate the image-based path on a staging or production-like host and then commit the already-prepared `dist-embed` untracking change as the new baseline.

Design document:

- `docs/plans/2026-03-06-dist-embed-deploy-redesign.md`

## Documentation Map

- Backend setup and service details: `maritime-ai-service/README.md`
- Desktop architecture and local conventions: `wiii-desktop/README.md`
- Repository docs conventions: `docs/README.md`
- Production deployment runbook: `maritime-ai-service/scripts/deploy/README.md`
- Plans and implementation notes: `docs/plans/`

## Repository Conventions

- Keep durable documentation in `docs/`, not at the repository root.
- Keep screenshots and other documentation assets in `docs/assets/`.
- Keep temporary screenshots in `docs/assets/screenshots/tmp/`.
- Keep supporting reference material in `Documents/`.
- Keep one-off utilities in `tools/` or project-local `scripts/` folders.
- Do not hand-edit hashed files inside build output directories.

## Current Cleanup Assessment

The repository root is substantially cleaner than before, but the working tree is not globally clean.

There are still many active changes across backend, desktop, deployment, and generated assets. In practice that means the structure is cleaner, but this repository is not yet at a clean `git status` baseline. Further cleanup should stay separate from unrelated feature work.

## License

See `LICENSE` for repository licensing terms.