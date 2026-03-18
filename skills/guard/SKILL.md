---
name: guard
description: "Guard phase of the Swarm Cycle. Protect quality: run tests, verify policy compliance, check success criteria, identify gaps. Produces Guard Report."
---

# Guard — Quality Protection

Guard bees protect the hive. This phase protects the codebase from regressions, policy violations, and unmet criteria.

## Procedure

### 1. Run all tests
```bash
pytest tests/ -q                    # 106 must pass
python test_agent_swarm.py           # 123 must pass
python scripts/check_harness.py      # 22/22 must pass
```

### 2. Policy compliance
For each changed file, verify against relevant policy document.
```
| File | Policy | Status | Issue |
|------|--------|--------|-------|
| [file] | [policy.md] | ✓/✗ | [detail] |
```

Key checks:
- [ ] Zero dependencies maintained
- [ ] Public API unchanged
- [ ] Module boundaries respected
- [ ] Gate modes correct (SOFT/WARN/STRICT)

### 3. Success criteria (from Scout Report)
```
| Criteria | Met | Evidence |
|----------|-----|----------|
| [from scout] | ✓/✗ | [proof] |
```

### 4. Gap analysis
```
| # | Gap | Severity | Fix needed |
|---|-----|----------|------------|
```

### 5. Guard Report
```
## Guard Report
Tests: [X] passed / [Y] failed
Policy: [X] compliant / [Y] violations
Criteria: [X]/[Y] met
Harness: PASS/FAIL
Gaps: [count]
Decision: PASS → Evolve / FAIL → back to Build
```
