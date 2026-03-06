# Architecture Documentation

This folder contains the primary architecture references for the backend service.

## Reading Order

| Document | Role | Notes |
|----------|------|-------|
| [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) | **Start here** | Most complete and current architecture overview, subsystem map, and deployment context |
| [SYSTEM_FLOW.md](SYSTEM_FLOW.md) | Request and streaming flow | Detailed lifecycle diagrams for chat, middleware, orchestration, and SSE |
| [FOLDER_MAP.md](FOLDER_MAP.md) | Codebase map | Useful when locating implementation areas in the backend |
| [contextual-rag.md](contextual-rag.md) | Strategy note | Retrieval and context-enrichment design detail |
| [tool-registry.md](tool-registry.md) | Pattern note | Tool registration and dispatch conventions |

## Recommended Usage

- Start with [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) for the current system shape.
- Use [SYSTEM_FLOW.md](SYSTEM_FLOW.md) when you need sequence-level request or streaming behavior.
- Use [FOLDER_MAP.md](FOLDER_MAP.md) when translating the docs into implementation files.

## Related Docs

- [../../README.md](../../README.md): repository overview
- [../integration/WIII_LMS_INTEGRATION.md](../integration/WIII_LMS_INTEGRATION.md): LMS architecture and contract
- [../../scripts/deploy/README.md](../../scripts/deploy/README.md): deployment runbook
