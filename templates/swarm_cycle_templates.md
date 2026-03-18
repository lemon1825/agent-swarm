# Swarm Cycle Templates

## Scout Report Template
```markdown
## Scout Report: [title]
**Date:** [YYYY-MM-DD] | **Type:** feature / bugfix / research / review

### Mission
[One clear sentence]

### Terrain
- Current: [what exists]  |  Target: [what should exist]

### Constraints
- Zero dependencies | Tests must pass | API stable | [domain-specific]

### Task Decomposition
| # | Task | Role | Depends On | Est. |
|---|------|------|------------|------|

### Success Criteria
- [ ] [outcome] | - [ ] 229 tests pass | - [ ] Harness 22/22

### Risks
| Risk | Impact | Mitigation |
|------|--------|------------|
```

## Build Log Template
```markdown
## Build Log: [title]
| # | Task | Role | Status | Output | Files | Time |
|---|------|------|--------|--------|-------|------|

**Completed:** X/Y | **Files changed:** [list] | **Ready for:** Guard
```

## Guard Report Template
```markdown
## Guard Report: [title]
| Check | Result |
|-------|--------|
| pytest (106) | ✓/✗ |
| integration (123) | ✓/✗ |
| harness (22) | ✓/✗ |
| policy compliance | ✓/✗ |
| success criteria | X/Y met |
| gaps found | [count] |

**Decision:** PASS → Evolve / FAIL → Build
```

## Cycle Report Template
```markdown
## Swarm Cycle: [type] — [title]
**Duration:** [time]

| Phase | Status | Detail |
|-------|--------|--------|
| Scout | ✓ | [goal], [N] tasks, [N] roles |
| Build | ✓ | [X/Y] completed, [N] files |
| Guard | ✓ | 229 tests, 0 violations |
| Evolve | ✓ | [N] fixes, [N] docs, [N] lessons |

**Result:** [achieved]
**Next:** [next cycle]
```
