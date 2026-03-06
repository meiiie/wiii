# Dist-Embed Deploy Redesign

## Summary

This document describes how to remove `wiii-desktop/dist-embed/` from version control without breaking the current `/embed/` runtime.

The recommended direction is:

1. Build the embed bundle in CI.
2. Package the bundle into deployable artifacts or images.
3. Deploy those immutable artifacts to production.
4. Stop mounting `dist-embed/` from the checked-out repository.
5. Remove `wiii-desktop/dist-embed/` from git tracking after the new path is proven.

## Implementation Status

Implemented in this repository revision:

- desktop CI now builds and uploads a `dist-embed/` artifact
- production image workflow now builds `dist-embed/` in CI and publishes the app and nginx images from that prebuilt artifact
- production deploy no longer requires `wiii-desktop/dist-embed/` in the checked-out server repository
- production deploy now pulls images by tag instead of building them on the host

Still intentionally deferred:

- committing the prepared removal of `wiii-desktop/dist-embed/` from git tracking after environment validation
- switching every local workflow away from the checked-in artifact
- proving rollback and smoke-test behavior in a real staging or production-like environment

## Current State

Today the system depends on `wiii-desktop/dist-embed/` being present in the repository checkout.

Current consumers:

- `maritime-ai-service/app/main.py` mounts `/embed/` from `../wiii-desktop/dist-embed` locally or `/app-embed` in Docker.
- `maritime-ai-service/docker-compose.yml` still mounts `../wiii-desktop/dist-embed` for local development.
- production images copy a CI-built `dist-embed/` bundle into `/app-embed` and `/usr/share/nginx/embed`.
- `maritime-ai-service/nginx/nginx.conf` and template serve `/embed` from the image-contained directory in production.

This gives predictable local behavior, but it has four problems:

1. Deployments depend on a mutable working tree artifact.
2. Git history gets noisy because every rebuild rotates hashed asset names.
3. The backend deploy path depends on the frontend checkout layout.
4. Recovery and rollback are harder because embed assets are not versioned as first-class deploy artifacts.

## Goals

- Remove `wiii-desktop/dist-embed/` from git.
- Keep `/embed/` reproducible across local, CI, and production environments.
- Make deploys use immutable, versioned artifacts.
- Reduce asset churn in code review.
- Keep local developer workflow simple.

## Non-Goals

- Replacing the embed app architecture.
- Replacing Docker Compose immediately.
- Introducing a full Kubernetes stack.

## Options

### Option A: CI-built artifact, packaged into images

Build `dist-embed/` in GitHub Actions, then copy the output into production images during the image build.

Advantages:

- Best reproducibility.
- No server-side Node.js dependency for deploy.
- Rollback becomes image rollback.
- Cleaner review flow because hashed assets never land in git.

Disadvantages:

- Requires Docker build changes and CI wiring.
- Slightly larger image build context or multi-stage build complexity.

### Option B: CI-built artifact, uploaded separately and downloaded on deploy

Build `dist-embed/` in CI, publish it as a release artifact or object storage bundle, and fetch it during deploy.

Advantages:

- Keeps embed artifact separate from backend image.
- Lower coupling between backend image and frontend build.

Disadvantages:

- Deploy script must download and validate external artifacts.
- More moving parts and more rollback logic.

### Option C: Server-side build during deploy

Install Node.js on the server and run `npm ci && npm run build:embed` as part of deploy.

Advantages:

- Easy to bootstrap.
- No artifact publishing system required.

Disadvantages:

- Least reproducible option.
- Slower deploys.
- More server drift risk.
- Production success depends on npm registry availability and server toolchain state.

## Recommendation

Choose **Option A**.

It is the cleanest long-term model for this repository because it turns the embed app into a normal build artifact of CI rather than a checked-in byproduct of local development.

## Target Architecture

```text
Developer push
    │
    ▼
GitHub Actions
    ├── desktop test job
    ├── embed build job
    ├── backend test job
    └── docker image build job
             │
             ├── app image contains embed assets at /app-embed
             └── nginx image contains embed assets at /usr/share/nginx/embed
                      │
                      ▼
             image registry or deploy host
                      │
                      ▼
             production deploy pulls immutable images
```

## CI/CD Design

### 1. New embed build stage

Add a workflow job that:

- runs on changes under `wiii-desktop/**`
- uses Node 20
- runs `npm ci`
- runs `npm run build:embed`
- validates `dist-embed/embed.html`
- uploads `dist-embed/` as a named build artifact

### 2. Image build from CI-produced embed bundle

Create a production image flow where:

- CI produces `dist-embed/` before Docker image creation
- the app image copies the embed bundle to `/app-embed`
- the nginx image copies the same embed bundle to `/usr/share/nginx/embed`

This removes the need for compose bind mounts from `../wiii-desktop/dist-embed`.

### 3. Deploy step

Update deployment to:

- pull versioned images, not rely on repository-local build outputs
- remove the precondition that `wiii-desktop/dist-embed/embed.html` exists in the checkout
- validate embed availability with a post-deploy `/embed/` smoke check

### 4. Rollback model

Rollback should use image tags or digests, not git state.

That gives a clean answer to: “what exact embed build is production serving?”

## Required Repository Changes

### Docker

- Add a frontend build stage that can produce the embed bundle.
- Either:
  - extend the backend `Dockerfile` to copy embed output into the app image, or
  - add dedicated Dockerfiles for app and nginx production images.

### Compose

Remove these bind mounts once the new images exist:

- `../wiii-desktop/dist-embed:/app-embed:ro`
- `../wiii-desktop/dist-embed:/usr/share/nginx/embed:ro`

### Deploy script

Replace current checks for local embed files with:

- image pull/build validation
- container health validation
- `/embed/` smoke test

### Git ignore and tracking

After migration:

- add `wiii-desktop/dist-embed/` to `.gitignore`
- remove tracked files from git with `git rm -r --cached wiii-desktop/dist-embed`

## Migration Plan

### Phase 1: Add CI embed build

- keep current tracked `dist-embed/`
- introduce CI embed build and validation
- confirm CI bundle matches local runtime expectations

### Phase 2: Bake embed into images

- update Dockerfiles and compose
- make production use image-contained embed assets
- keep current tracked directory temporarily as fallback

### Phase 3: Switch deploy logic

- remove bind-mount dependency from deploy path
- add `/embed/` smoke test
- verify rollback with previous image tag

### Phase 4: Untrack dist-embed

- ignore `wiii-desktop/dist-embed/`
- remove tracked copies from git
- update README and deploy docs

## Validation Checklist

- CI can build the embed bundle from a clean checkout.
- Production containers can serve `/embed/` without repository bind mounts.
- Local development still works via `npm run build:embed` when needed.
- Deploy no longer requires a prebuilt embed bundle in the checkout.
- Rollback restores both API and embed assets together.

## Recommended Execution Order

1. Add CI embed build job.
2. Add image build path for embed assets.
3. Update compose and deploy logic.
4. Verify `/embed/` smoke tests in staging or a disposable VM.
5. Untrack `dist-embed/`.

## Short Decision

If the goal is a cleaner repository and a safer deployment model, prefer **CI-built immutable images** over **server-side npm builds**.

Server-side build is acceptable only as a temporary bridge, not as the final architecture.