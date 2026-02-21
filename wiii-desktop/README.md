# Wiii Desktop

![Tauri v2](https://img.shields.io/badge/Tauri-v2-24C8D8?logo=tauri&logoColor=white)
![React 18](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-5.x-3178C6?logo=typescript&logoColor=white)
![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-3.4-06B6D4?logo=tailwindcss&logoColor=white)
![Vitest](https://img.shields.io/badge/Vitest-1468_tests-6E9F18?logo=vitest&logoColor=white)

**Cross-platform desktop client for the Wiii AI platform.**

*by The Wiii Lab*

---

## Features

- **Real-time AI Chat** -- SSE V3 streaming with token-by-token response delivery
- **Rich Thinking Display** -- Thinking blocks, tool call cards, reasoning timeline, and multi-phase thinking chain
- **Kawaii/Manga Avatar** -- Living avatar with emotion engine, Rive integration, soul emotion, and micro-reactions
- **Google OAuth Authentication** -- Desktop deep link flow with JWT refresh tokens
- **Multi-Organization Workspace** -- Workspace switcher with org-level branding, permissions, and feature gating
- **Org-Level Customization** -- Per-org CSS custom properties, PermissionGate RBAC, admin settings tab
- **Conversation Persistence** -- Auto-save via Tauri plugin-store with debounced writes
- **Frameless Window** -- Custom title bar with drag regions, minimize/maximize/close controls, and splash screen
- **Dark / Light / System Theme** -- Three theme modes with Tailwind CSS class strategy
- **Keyboard Shortcuts** -- Ctrl+Enter to send, command palette, and configurable bindings
- **Context Panel** -- Token budget visualization, conversation compaction controls
- **Character Panel** -- AI character traits and personality inspection
- **Living Agent Dashboard** -- Soul status, 4D mood indicator, heartbeat monitor, skill tree, daily journal viewer
- **Screenshot Blocks** -- Inline browser screenshot rendering from product search

---

## Tech Stack

| Technology | Version | Purpose |
|---|---|---|
| Tauri | v2 | Cross-platform desktop shell (Rust backend) |
| React | 18 | UI framework |
| TypeScript | 5.x | Type safety |
| Vite | 5.x | Build tool and dev server |
| Tailwind CSS | 3.4 | Utility-first styling |
| Zustand | 4.5 | State management (11 stores) |
| Immer | 11.x | Immutable state updates |
| Vitest | 1.6 | Testing framework (1468 tests) |
| Lucide React | 0.400 | Icon library |
| Motion | 12.x | Animation library |
| React Markdown | 9.x | Markdown rendering with GFM and syntax highlighting |
| Rive (WebGL2) | 4.27 | Avatar animation runtime |

### Tauri Plugins (Rust)

| Plugin | Purpose |
|---|---|
| `tauri-plugin-store` | Persistent key-value storage |
| `tauri-plugin-http` | CORS-free HTTP requests |
| `tauri-plugin-dialog` | Native file/message dialogs |
| `tauri-plugin-shell` | System shell and URL opening |
| `tauri-plugin-notification` | Desktop notifications |

---

## Project Structure

```
wiii-desktop/
├── src/
│   ├── api/                     # 16 API modules
│   │   ├── client.ts            # HTTP client (Tauri plugin-http / fetch fallback)
│   │   ├── sse.ts               # SSE parser for /chat/stream/v3
│   │   ├── chat.ts              # Chat endpoints
│   │   ├── organizations.ts     # Organization CRUD
│   │   ├── users.ts             # User profile and identities
│   │   ├── admin.ts             # Admin endpoints
│   │   ├── character.ts         # Character trait API
│   │   ├── context.ts           # Context management API
│   │   ├── domains.ts           # Domain listing
│   │   ├── feedback.ts          # User feedback
│   │   ├── health.ts            # Health check
│   │   ├── living-agent.ts      # Living Agent status, skills, journal
│   │   ├── memories.ts          # Semantic memory
│   │   ├── preferences.ts       # User preferences
│   │   ├── sources.ts           # Source citations
│   │   └── types.ts             # Shared API types
│   │
│   ├── components/
│   │   ├── auth/                # Authentication UI
│   │   │   └── LoginScreen.tsx  # Google OAuth login screen
│   │   ├── chat/                # Chat experience (15 components)
│   │   │   ├── ChatView.tsx     # Main chat container
│   │   │   ├── ChatInput.tsx    # Message input with send controls
│   │   │   ├── MessageList.tsx  # Scrollable message list
│   │   │   ├── MessageBubble.tsx # Individual message rendering
│   │   │   ├── ThinkingBlock.tsx # AI thinking with markdown + tool cards
│   │   │   ├── ThinkingFlow.tsx # Multi-phase thinking chain
│   │   │   ├── ThinkingTimeline.tsx # Timeline visualization
│   │   │   ├── ActionText.tsx   # Action text between thinking phases
│   │   │   ├── StreamingIndicator.tsx # Pipeline progress + elapsed timer
│   │   │   ├── ReasoningTrace.tsx # Reasoning step display
│   │   │   ├── ScreenshotBlock.tsx # Inline browser screenshots
│   │   │   ├── SourceCitation.tsx # Source reference cards
│   │   │   ├── SuggestedQuestions.tsx # Pill-style suggestions
│   │   │   ├── DomainSelector.tsx # Domain picker
│   │   │   └── WelcomeScreen.tsx # Org-branded welcome
│   │   ├── layout/              # Application shell (8 components)
│   │   │   ├── AppShell.tsx     # Root layout container
│   │   │   ├── TitleBar.tsx     # Custom frameless title bar
│   │   │   ├── Sidebar.tsx      # Conversation list + navigation
│   │   │   ├── StatusBar.tsx    # Connection status + info
│   │   │   ├── WorkspaceSelector.tsx # Organization switcher
│   │   │   ├── ContextPanel.tsx # Token budget and compaction
│   │   │   ├── CharacterPanel.tsx # AI character inspection
│   │   │   └── SourcesPanel.tsx # Source documents panel
│   │   ├── living-agent/         # Living Agent dashboard (5 components)
│   │   │   ├── LivingAgentPanel.tsx # Main 3-tab panel (overview/skills/journal)
│   │   │   ├── MoodIndicator.tsx # 4D emotional state with energy bars
│   │   │   ├── SkillTree.tsx    # Skill lifecycle cards (active + mastered)
│   │   │   ├── JournalView.tsx  # Collapsible daily journal entries
│   │   │   └── HeartbeatStatus.tsx # Heartbeat monitor with manual trigger
│   │   ├── settings/            # Settings modal
│   │   │   ├── SettingsPage.tsx # Tabbed settings (Connection/User/Preferences/Linh hồn)
│   │   │   └── OrgSettingsTab.tsx # Organization admin config
│   │   └── common/              # Shared components (10 components)
│   │       ├── MarkdownRenderer.tsx # Rich markdown with code highlighting
│   │       ├── CodeBlock.tsx    # Syntax-highlighted code blocks
│   │       ├── ErrorBoundary.tsx # React error boundary
│   │       ├── ConnectionBadge.tsx # Connection status indicator
│   │       ├── PermissionGate.tsx # RBAC permission wrapper
│   │       ├── CommandPalette.tsx # Keyboard-driven command palette
│   │       ├── ConfirmDialog.tsx # Confirmation modal
│   │       ├── Toast.tsx        # Toast notifications
│   │       ├── AvatarPreview.tsx # Avatar preview component
│   │       └── WiiiAvatar.tsx   # Avatar display wrapper
│   │
│   ├── stores/                  # 12 Zustand stores
│   │   ├── settings-store.ts    # Server URL, API key, theme, user preferences
│   │   ├── chat-store.ts        # Conversations, messages, streaming state (largest)
│   │   ├── auth-store.ts        # JWT tokens, OAuth flow, login state
│   │   ├── org-store.ts         # Organizations, permissions, workspace, branding
│   │   ├── connection-store.ts  # Backend connectivity and health
│   │   ├── domain-store.ts      # Available domain plugins
│   │   ├── ui-store.ts          # Sidebar visibility, modals, layout state
│   │   ├── avatar-store.ts      # Avatar animations, emotion state
│   │   ├── character-store.ts   # AI character traits and config
│   │   ├── context-store.ts     # Token budget, context info
│   │   ├── living-agent-store.ts # Living Agent soul, mood, skills, journal
│   │   ├── memory-store.ts      # Semantic memory viewer
│   │   └── toast-store.ts       # Toast notification queue
│   │
│   ├── hooks/                   # Custom React hooks
│   │   ├── useSSEStream.ts      # SSE V3 stream consumption
│   │   ├── useAutoScroll.ts     # Smart auto-scroll for chat
│   │   ├── useKeyboardShortcuts.ts # Global keyboard bindings
│   │   └── useAvatarState.ts    # Avatar emotion state bridge
│   │
│   ├── lib/                     # Utility modules
│   │   ├── avatar/              # Avatar engine (18 modules)
│   │   │   ├── WiiiAvatar.tsx   # Main avatar component
│   │   │   ├── use-avatar-animation.ts # Animation orchestrator
│   │   │   ├── face-geometry.ts # Face shape generation
│   │   │   ├── blob-geometry.ts # Organic blob shapes
│   │   │   ├── eye-moisture.ts  # Eye shine effects
│   │   │   ├── blink-controller.ts # Natural blink timing
│   │   │   ├── gaze-controller.ts # Eye tracking
│   │   │   ├── noise-engine.ts  # Simplex noise for organic motion
│   │   │   ├── particle-system.ts # Particle effects
│   │   │   ├── mood-theme.ts    # Mood-based color themes
│   │   │   ├── manga-indicators.ts # Manga expression markers
│   │   │   ├── micro-reaction-registry.ts # Micro-reaction animations
│   │   │   ├── reaction-chains.ts # Chained reaction sequences
│   │   │   ├── state-config.ts  # Avatar state definitions
│   │   │   ├── face-config.ts   # Face configuration
│   │   │   ├── types.ts         # Avatar type definitions
│   │   │   └── rive/            # Rive animation integration
│   │   ├── org-branding.ts      # CSS custom property injection for orgs
│   │   ├── org-config.ts        # Organization configuration
│   │   ├── domain-config.ts     # Domain plugin configuration
│   │   ├── storage.ts           # Tauri store / localStorage adapter
│   │   ├── stream-buffer.ts     # SSE stream buffering
│   │   ├── theme.ts             # Theme management
│   │   ├── constants.ts         # App-wide constants
│   │   ├── format.ts            # Text formatting utilities
│   │   ├── greeting.ts          # Time-based greeting messages
│   │   ├── date-utils.ts        # Date formatting
│   │   ├── animations.ts        # Animation utilities
│   │   └── conversation-groups.ts # Conversation grouping logic
│   │
│   └── __tests__/               # 55 test files, 1468 Vitest tests
│
├── src-tauri/                   # Rust backend
│   ├── src/
│   │   ├── lib.rs               # Tauri app setup and plugin registration
│   │   └── commands/            # Tauri IPC commands
│   │       ├── mod.rs           # Command module declarations
│   │       └── splash.rs        # Splash screen lifecycle
│   ├── capabilities/            # Tauri v2 capability permissions
│   ├── icons/                   # App icons (ICO, ICNS, PNG, BMP)
│   ├── windows/                 # NSIS installer language files
│   ├── Cargo.toml               # Rust dependencies
│   └── tauri.conf.json          # Tauri configuration
│
├── public/
│   └── splashscreen.html        # Splash screen HTML
├── package.json                 # Node dependencies
├── vite.config.ts               # Vite configuration
├── tailwind.config.js           # Tailwind CSS configuration
├── tsconfig.json                # TypeScript configuration
└── postcss.config.js            # PostCSS configuration
```

---

## Quick Start

### Prerequisites

- [Node.js](https://nodejs.org/) >= 18
- [Rust](https://rustup.rs/) (for Tauri builds)
- [Tauri CLI prerequisites](https://v2.tauri.app/start/prerequisites/)

### Install Dependencies

```bash
cd wiii-desktop
npm install
```

### Development (Web Only)

Starts the Vite dev server at `http://localhost:1420` -- useful for rapid UI iteration without the Rust backend:

```bash
npm run dev
```

### Development (Full Tauri App)

Launches the complete desktop application with Rust backend, splash screen, and native features:

```bash
npx tauri dev
```

### Build for Production

Produces an NSIS installer for Windows:

```bash
npx tauri build
```

The installer is output to `src-tauri/target/release/bundle/nsis/`.

### Run Tests

```bash
npx vitest run          # All 1468 tests
npx vitest run --ui     # Interactive test UI
npx vitest run --coverage  # With coverage report
```

### Lint

```bash
npm run lint
```

---

## Architecture

### State Management

12 Zustand stores manage application state, with Tauri plugin-store providing persistent storage across sessions:

| Store | Key Responsibilities |
|---|---|
| `settings-store` | Server URL, API key, theme, streaming version, user display preferences |
| `chat-store` | Conversations, messages, streaming state, content blocks (largest store) |
| `auth-store` | JWT access/refresh tokens, OAuth flow state, login/logout |
| `org-store` | Organizations list, active workspace, permissions, org branding config |
| `connection-store` | Backend connectivity status, health check results |
| `domain-store` | Available domain plugins, active domain selection |
| `ui-store` | Sidebar visibility, modal states, layout preferences |
| `avatar-store` | Avatar emotion state, animation triggers, expression config |
| `character-store` | AI character traits, personality blocks |
| `context-store` | Token budget info, utilization percentage, compaction state |
| `living-agent-store` | Living Agent soul status, 4D emotional state, skills, journal, heartbeat |
| `memory-store` | Semantic memory entries, memory filter state |
| `toast-store` | Toast notification queue |

Persistence strategy:
- **Immediate persist**: Conversation create/delete/rename, stream finalize, stream error
- **Debounced persist** (2s): Message additions during active streaming
- **Storage adapter**: `lib/storage.ts` uses `@tauri-apps/plugin-store` in Tauri, falls back to `localStorage` in browser

### Streaming (SSE V3)

The app consumes Server-Sent Events from the `/chat/stream/v3` endpoint. Event types:

| Event | Purpose |
|---|---|
| `status` | Pipeline progress -- node transitions (e.g., "Routing", "Searching knowledge base") |
| `thinking` | AI reasoning content -- rendered in ThinkingBlock with markdown |
| `thinking_start` | Opens a new thinking block in the UI |
| `thinking_end` | Closes the current thinking block |
| `tool_call` | Tool invocation event -- displayed as inline tool cards |
| `tool_result` | Tool execution result with data |
| `answer` | Token-by-token response text -- streamed into AnswerBlock |
| `done` | Stream completion with metadata (sources, timing) |
| `error` | Stream error with message |

The `useSSEStream` hook manages the SSE connection lifecycle, while `StreamBuffer` handles buffering and ordered delivery.

### Message Rendering

Messages use a ContentBlock system for interleaved display of different content types:

- **ThinkingBlock** -- AI reasoning with markdown rendering, inline tool call cards, and auto-collapse on completion
- **AnswerBlock** -- Rich markdown with GFM tables, syntax-highlighted code blocks, and LaTeX
- **ActionText** -- Transitional text between thinking phases ("Searching products...", "Comparing prices...")
- **ThinkingTimeline** -- Visual timeline of thinking phases with timestamps
- **ScreenshotBlock** -- Inline browser screenshot rendering with thumbnails

### Authentication

Three authentication modes, resolved in order:

1. **Google OAuth** -- Desktop deep link flow (`com.wiii-lab.wiii-desktop://oauth/callback`). JWT access + refresh token pair stored in `auth-store`.
2. **LMS Token Exchange** -- HMAC-signed backend-to-backend flow for LMS integration.
3. **API Key** -- Header-based authentication (`X-API-Key`) for development and testing.

### Organization Customization

- **WorkspaceSelector** in the sidebar allows switching between organizations
- **Per-org branding** via CSS custom properties injected by `org-branding.ts` (accent color, logo, name)
- **PermissionGate** component wraps UI sections that require specific roles or permissions
- **OrgSettingsTab** provides admin configuration for organization settings
- **Domain filtering** restricts available domain plugins based on org `allowed_domains`

### Avatar System

The Wiii avatar is a living, expressive character powered by a multi-layer animation engine:

- **Face geometry** -- Procedural SVG face with blob shapes and simplex noise
- **Emotion engine** -- Maps AI states (thinking, answering, idle) to emotional expressions
- **Manga indicators** -- Sweat drops, sparkles, emphasis marks for expressive reactions
- **Micro-reactions** -- Subtle animations (blinks, eye moisture, gaze tracking)
- **Rive integration** -- Hardware-accelerated WebGL2 animation via `@rive-app/react-webgl2`
- **Mood themes** -- Dynamic color palette changes based on emotional state

---

## Testing

```bash
npx vitest run                              # All tests
npx vitest run src/__tests__/chat-store*    # Specific test file
npx vitest run src/__tests__/sprint161*     # Sprint-specific tests
npx vitest run --coverage                   # With coverage report
npx vitest run --ui                         # Interactive browser UI
```

**1468 tests** across **55 test files** -- all passing.

Test coverage areas:
- Store logic (chat, auth, org, settings, context, memory, avatar, living-agent)
- SSE streaming and stream buffer
- Thinking block lifecycle and multi-phase thinking flow
- Avatar emotion engine and animation system
- Living Agent types, store, and API module structure
- Organization UI consistency and integration
- Screenshot rendering and thumbnails
- Conversation persistence and grouping
- Theme switching and greeting logic

---

## Configuration

### Tauri Configuration (`src-tauri/tauri.conf.json`)

| Setting | Value |
|---|---|
| Product name | `Wiii` |
| Identifier | `com.wiii-lab.wiii-desktop` |
| Window size | 1200 x 800 (min 800 x 600) |
| Decorations | `false` (frameless, custom title bar) |
| Bundle target | NSIS (Windows installer) |
| Installer languages | Vietnamese, English |
| Copyright | Copyright 2026 The Wiii Lab |

### Vite Configuration (`vite.config.ts`)

| Setting | Value |
|---|---|
| Dev server port | `1420` |
| Path alias | `@` maps to `./src` |
| Build target | `chrome105` (Windows) / `safari13` (macOS/Linux) |
| Env prefix | `VITE_`, `TAURI_` |

### Environment Variables

The desktop app connects to a Wiii backend instance. Configure via the Settings page (Connection tab) or environment:

| Variable | Purpose |
|---|---|
| `VITE_API_URL` | Backend server URL (default: `http://localhost:8000`) |
| `VITE_API_KEY` | API key for authentication |

---

## Scripts

| Script | Command | Description |
|---|---|---|
| `npm run dev` | `vite` | Start Vite dev server at localhost:1420 |
| `npm run build` | `tsc && vite build` | TypeScript check + production build |
| `npm run preview` | `vite preview` | Preview production build locally |
| `npm run test` | `vitest` | Run tests in watch mode |
| `npm run test:ui` | `vitest --ui` | Interactive test UI in browser |
| `npm run lint` | `eslint src/ --ext .ts,.tsx` | Lint TypeScript source |
| `npx tauri dev` | -- | Full Tauri app development |
| `npx tauri build` | -- | Build production installer |

---

## License

Proprietary -- All rights reserved.

*Wiii by The Wiii Lab*
