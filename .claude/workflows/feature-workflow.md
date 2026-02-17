# Feature Implementation Workflow

**Coordinator:** LEADER
**Participants:** ARCHITECT, DEVELOPER, REVIEWER, TESTER

---

## Phase 1: Planning (LEADER + ARCHITECT)

### 1.1 Requirements Analysis
- [ ] Understand feature requirements
- [ ] Identify affected components
- [ ] Estimate complexity

### 1.2 Design (ARCHITECT)
- [ ] Create design document
- [ ] Define API contracts
- [ ] Plan database changes
- [ ] Identify risks

### 1.3 Task Breakdown (LEADER)
- [ ] Break into atomic tasks
- [ ] Define dependencies
- [ ] Assign to agents
- [ ] Set priorities

---

## Phase 2: Implementation (DEVELOPER)

### 2.1 Setup
- [ ] Read assigned task
- [ ] Understand context
- [ ] Review related code

### 2.2 Development
- [ ] Implement feature
- [ ] Add error handling
- [ ] Write unit tests
- [ ] Update documentation

### 2.3 Self-Check
- [ ] Code compiles/runs
- [ ] Tests pass
- [ ] No linting errors
- [ ] Follows patterns

---

## Phase 3: Testing (TESTER)

### 3.1 Test Development
- [ ] Write integration tests
- [ ] Add edge case tests
- [ ] Property-based tests (if applicable)

### 3.2 Test Execution
- [ ] All tests pass
- [ ] Coverage adequate
- [ ] No regressions

---

## Phase 4: Review (REVIEWER)

### 4.1 Code Review
- [ ] Correctness check
- [ ] Security review
- [ ] Performance review
- [ ] Style compliance

### 4.2 Feedback
- [ ] Document issues
- [ ] Suggest improvements
- [ ] Approve or request changes

---

## Phase 5: Approval (LEADER)

### 5.1 Final Review
- [ ] All tasks completed
- [ ] All tests pass
- [ ] Review approved
- [ ] Documentation updated

### 5.2 Completion
- [ ] Mark feature complete
- [ ] Update project status
- [ ] Archive tasks

---

## Communication Flow

```
LEADER
   │
   ├── Design Request ──────► ARCHITECT
   │   ◄── Design Document ──┘
   │
   ├── Task Assignment ─────► DEVELOPER
   │   ◄── Completion Report ─┘
   │
   ├── Test Request ────────► TESTER
   │   ◄── Test Report ───────┘
   │
   └── Review Request ──────► REVIEWER
       ◄── Review Report ─────┘
```
