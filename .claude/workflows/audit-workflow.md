# Audit Workflow

**Executor:** LEADER
**Frequency:** On-demand or weekly

---

## Phase 1: Preparation

1. **Define scope**
   - Full system audit OR
   - Specific module/feature audit

2. **Gather context**
   - Recent changes (git log)
   - Open issues
   - Previous audit findings

---

## Phase 2: Static Analysis

### Security Scan
```bash
# Check for security issues
bandit -r app/ -ll -f json > .claude/reports/security-scan.json

# Check for secrets
grep -rn "password\|secret\|api_key\|token" app/ --include="*.py" | grep -v "\.pyc"
```

### Code Quality
```bash
# Unused imports
ruff check app/ --select=F401

# Type checking
mypy app/ --ignore-missing-imports

# Complexity
radon cc app/ -a -s
```

### Dead Code
```bash
# Find unused functions (requires vulture)
vulture app/ --min-confidence 80
```

---

## Phase 3: Manual Review

### Architecture Check
- [ ] Layer boundaries respected
- [ ] No circular dependencies
- [ ] Proper dependency injection
- [ ] Consistent error handling

### Code Patterns
- [ ] Follows project conventions
- [ ] No copy-paste code
- [ ] Proper async usage
- [ ] Resource cleanup (context managers)

### Security Review
- [ ] Input validation
- [ ] SQL parameterization
- [ ] Authentication checks
- [ ] Rate limiting

---

## Phase 4: Testing Review

```bash
# Run tests with coverage
pytest tests/ --cov=app --cov-report=term-missing

# Check test quality
pytest tests/ -v --tb=short
```

- [ ] Coverage > 70%
- [ ] Critical paths tested
- [ ] Edge cases covered
- [ ] No skipped tests without reason

---

## Phase 5: Documentation

### Generate Report
Save to `.claude/reports/audit-YYYY-MM-DD.md`:

```markdown
# Audit Report: [Scope]
Date: YYYY-MM-DD

## Executive Summary
[Overall health assessment]

## Metrics
| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| Test Coverage | X% | >70% | PASS/FAIL |
| Security Issues | N | 0 | PASS/FAIL |
| Code Complexity | X | <10 avg | PASS/FAIL |

## Findings
[Detailed findings table]

## Action Items
[Prioritized list with assignments]

## Recommendations
[Improvement suggestions]
```

---

## Phase 6: Task Creation

For each finding requiring action:
1. Create task in `.claude/tasks/`
2. Assign to appropriate agent
3. Set priority and deadline
4. Link to audit report
