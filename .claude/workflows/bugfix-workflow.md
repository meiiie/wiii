# Bug Fix Workflow

**Coordinator:** LEADER
**Participants:** RESEARCHER, DEVELOPER, TESTER, REVIEWER

---

## Phase 1: Triage (LEADER)

### 1.1 Bug Assessment
- [ ] Reproduce the bug
- [ ] Determine severity
- [ ] Identify affected users/features
- [ ] Set priority

### Severity Matrix
| Severity | Description | Response Time |
|----------|-------------|---------------|
| CRITICAL | System down, data loss | Immediate |
| HIGH | Major feature broken | Same day |
| MEDIUM | Feature degraded | This week |
| LOW | Minor inconvenience | Backlog |

---

## Phase 2: Investigation (RESEARCHER)

### 2.1 Root Cause Analysis
- [ ] Trace the error
- [ ] Find the root cause
- [ ] Identify affected code
- [ ] Document findings

### 2.2 Research Report
```markdown
## Bug Investigation: [Bug ID]

### Reproduction
[Steps to reproduce]

### Root Cause
[What's causing the bug]

### Affected Code
- `file.py:line` - [description]

### Suggested Fix
[Approach to fix]

### Risk Assessment
[What could go wrong with the fix]
```

---

## Phase 3: Fix (DEVELOPER)

### 3.1 Implementation
- [ ] Implement fix
- [ ] Add regression test
- [ ] Verify fix works
- [ ] Check for side effects

### 3.2 Completion Report
- [ ] Document changes
- [ ] Explain fix approach
- [ ] Note any concerns

---

## Phase 4: Verification (TESTER)

### 4.1 Testing
- [ ] Verify bug is fixed
- [ ] Run regression tests
- [ ] Test edge cases
- [ ] Confirm no new issues

---

## Phase 5: Review & Close (REVIEWER + LEADER)

### 5.1 Code Review
- [ ] Review fix quality
- [ ] Check for proper testing
- [ ] Approve changes

### 5.2 Closure (LEADER)
- [ ] Verify all criteria met
- [ ] Close bug
- [ ] Update documentation if needed
- [ ] Consider preventive measures
