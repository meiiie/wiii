# Claude Code Multi-Agent System

This folder contains the configuration for a multi-agent Claude Code setup for the Maritime AI Service project.

---

## Folder Structure

```
.claude/
├── agents/                 # Agent persona definitions
│   ├── leader.md          # LEADER - Project management, audit (DEFAULT)
│   ├── developer.md       # DEVELOPER - Feature implementation
│   ├── reviewer.md        # REVIEWER - Code review, QA
│   ├── tester.md          # TESTER - Testing, bug hunting
│   ├── architect.md       # ARCHITECT - System design
│   └── researcher.md      # RESEARCHER - Codebase exploration
│
├── workflows/             # Standard workflows
│   ├── audit-workflow.md  # Code audit process
│   ├── feature-workflow.md # Feature implementation process
│   └── bugfix-workflow.md # Bug fix process
│
├── knowledge/             # Project knowledge base
│   ├── system-patterns.md # Common patterns in this codebase
│   └── gotchas.md         # Known issues and workarounds
│
├── reports/               # Audit reports and findings
│   └── (generated reports)
│
├── tasks/                 # Task assignments for agents
│   └── (task files)
│
└── README.md              # This file
```

---

## Agent Roles

| Role | Responsibility | Authority |
|------|----------------|-----------|
| **LEADER** | Project management, audit, task delegation | Full |
| **DEVELOPER** | Implement features, fix bugs | Assigned scope |
| **REVIEWER** | Code review, quality assurance | Review scope |
| **TESTER** | Testing, bug discovery | Test scope |
| **ARCHITECT** | System design, architecture decisions | Design scope |
| **RESEARCHER** | Codebase exploration, documentation | Read-only |

---

## How to Use

### Starting a Session

When starting Claude Code, the default role is **LEADER**. To switch roles:

```
"I'm working as DEVELOPER on task TASK-2025-02-05-001"
"Switch to REVIEWER role for code review"
"Acting as TESTER to write tests for the chat module"
```

### LEADER Workflow

1. **Audit** - Run audit workflow, generate reports
2. **Plan** - Break down work into tasks
3. **Delegate** - Assign tasks to agents via `.claude/tasks/`
4. **Review** - Check completed work
5. **Approve** - Sign off on changes

### Agent Communication

Agents communicate through:
- **Task files** in `.claude/tasks/`
- **Reports** in `.claude/reports/`
- **Knowledge** in `.claude/knowledge/`
- **Wave mailbox** in `.claude/coord/` for architect ↔ Claude Code team handoff

### Task File Format

```markdown
## Task Assignment

**Task ID:** TASK-YYYY-MM-DD-NNN
**Assigned to:** [DEVELOPER|REVIEWER|TESTER|ARCHITECT|RESEARCHER]
**Priority:** [CRITICAL|HIGH|MEDIUM|LOW]
**Status:** [OPEN|IN_PROGRESS|REVIEW|COMPLETED]

### Objective
[Clear goal]

### Context
[Background information]

### Acceptance Criteria
- [ ] Criterion 1
- [ ] Criterion 2

### Files
- `path/to/file.py`

### Notes
[Additional information]
```

---

## Best Practices

1. **Always read before write** - Understand code before modifying
2. **Minimal changes** - Make only necessary modifications
3. **Follow patterns** - Use existing code patterns
4. **Test changes** - Run relevant tests after modifications
5. **Document findings** - Update knowledge base with discoveries
6. **Report blockers** - Communicate issues immediately

---

## Quick Reference

### File Naming Conventions

- Tasks: `TASK-YYYY-MM-DD-NNN.md`
- Reports: `audit-YYYY-MM-DD.md`, `review-TASK-XXX.md`
- Bugs: `BUG-YYYY-MM-DD-NNN.md`

### Priority Levels

| Priority | Response |
|----------|----------|
| CRITICAL | Immediate |
| HIGH | Same day |
| MEDIUM | This week |
| LOW | Backlog |

### Severity Levels (Issues)

| Severity | Action |
|----------|--------|
| BLOCKER | Must fix before merge |
| CRITICAL | Must fix before merge |
| MAJOR | Should fix |
| MINOR | Nice to fix |
| INFO | Optional |
