# Agent Prompts - Execution Guide

**Created by:** LEADER
**Date:** 2025-02-05
**Last Updated:** 2025-02-05 (Phase 2 ready)

---

## Overview

Các prompt này được thiết kế để copy vào Claude Code session mới. Mỗi agent sẽ nhận prompt tương ứng và thực thi theo đúng hướng dẫn.

---

## READY-TO-EXECUTE PROMPTS (Phase 2)

**Copy trực tiếp vào Claude Code session mới:**

| File | Agent | Task | Status |
|------|-------|------|--------|
| `READY-DEVELOPER-TASK005.md` | DEVELOPER | Parallelize operations | 🔵 READY |
| `READY-ARCHITECT-TASK006.md` | ARCHITECT | Clean deprecated code | 🔵 READY |
| `READY-REVIEWER-TASK007.md` | REVIEWER | Security review | 🔵 READY |
| `READY-TESTER-TASK008.md` | TESTER | Create regression tests | 🔵 READY |

---

## Execution Order

```
┌─────────────────────────────────────────────────────────────┐
│                    PHASE 1: CRITICAL FIXES                   │
│                         (Parallel)                           │
├─────────────────────────────────────────────────────────────┤
│  DEVELOPER (CRITICAL)  │  REVIEWER (SECURITY)               │
│  TASK-001 → TASK-004   │  TASK-007                          │
│  ~2-3 hours            │  ~1 hour                           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    PHASE 2: OPTIMIZATION                     │
│                       (Sequential)                           │
├─────────────────────────────────────────────────────────────┤
│  DEVELOPER (HIGH)      │  ARCHITECT (CLEANUP)               │
│  TASK-005              │  TASK-006                          │
│  ~1 hour               │  ~2 hours                          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    PHASE 3: VERIFICATION                     │
├─────────────────────────────────────────────────────────────┤
│  TESTER                                                      │
│  TASK-008 (Create regression tests)                         │
│  ~2 hours                                                    │
└─────────────────────────────────────────────────────────────┘
```

---

## Prompt Files

| File | Agent | Priority | Tasks |
|------|-------|----------|-------|
| `PROMPT-DEVELOPER-CRITICAL.md` | DEVELOPER | CRITICAL | TASK-001, 002, 003, 004 |
| `PROMPT-DEVELOPER-HIGH.md` | DEVELOPER | HIGH | TASK-005 |
| `PROMPT-ARCHITECT.md` | ARCHITECT | HIGH | TASK-006 |
| `PROMPT-REVIEWER.md` | REVIEWER | HIGH | TASK-007 |
| `PROMPT-TESTER.md` | TESTER | HIGH | TASK-008 |

---

## How to Use

### Option 1: Copy-Paste Full Prompt

1. Open new Claude Code terminal/session
2. Copy entire content of prompt file
3. Paste as first message
4. Agent will execute instructions

### Option 2: Reference Prompt File

Start new session with:
```
Read file: /mnt/e/Sach/Sua/AI_v1/.claude/prompts/PROMPT-DEVELOPER-CRITICAL.md

Then follow the instructions in that file.
```

---

## Quick Start Commands

### DEVELOPER (Critical Fixes)
```bash
# Terminal 1
cd /mnt/e/Sach/Sua/AI_v1
# Start Claude Code, paste PROMPT-DEVELOPER-CRITICAL.md
```

### REVIEWER (Security Review)
```bash
# Terminal 2 (can run parallel with DEVELOPER)
cd /mnt/e/Sach/Sua/AI_v1
# Start Claude Code, paste PROMPT-REVIEWER.md
```

### ARCHITECT (After DEVELOPER completes)
```bash
# Terminal 3
cd /mnt/e/Sach/Sua/AI_v1
# Start Claude Code, paste PROMPT-ARCHITECT.md
```

### TESTER (After all fixes)
```bash
# Terminal 4
cd /mnt/e/Sach/Sua/AI_v1
# Start Claude Code, paste PROMPT-TESTER.md
```

---

## Completion Tracking

Update task status in `.claude/tasks/`:

| Task | Status | Assignee | Notes |
|------|--------|----------|-------|
| TASK-001 | OPEN | DEVELOPER | |
| TASK-002 | OPEN | DEVELOPER | |
| TASK-003 | OPEN | DEVELOPER | |
| TASK-004 | OPEN | DEVELOPER | |
| TASK-005 | OPEN | DEVELOPER | Depends on 001-004 |
| TASK-006 | OPEN | ARCHITECT | |
| TASK-007 | OPEN | REVIEWER | |
| TASK-008 | OPEN | TESTER | Depends on 001-005 |

---

## Communication Protocol

### When Agent Completes Task

1. Update task file status to COMPLETED
2. Create completion report in `.claude/reports/`
3. Notify LEADER (mention in chat or update tracking table)

### When Agent is Blocked

1. Document blocker in task file
2. Create new task for dependency
3. Move to next available task

### When Agent Finds New Issue

1. Document in `.claude/reports/`
2. Create new task in `.claude/tasks/`
3. Notify LEADER for prioritization

---

## Support

**Audit Report:** `.claude/reports/audit-2025-02-05.md`
**Knowledge Base:** `.claude/knowledge/`
**Agent Personas:** `.claude/agents/`
