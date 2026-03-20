---
name: ship
description: "Ship pipeline: test, review, version, commit, push. Sequential pipeline with checkpoints at each stage for resume capability."
---

# Ship — Release Pipeline

Like scout bees signaling that the swarm is ready to move, this skill orchestrates the full ship pipeline from tests to push with checkpoints for safe resumption.

## When to use
- Shipping a completed feature or fix
- Creating a release
- Automated CI/CD pipeline steps

## Procedure

### 1. Test — Run all tests
```bash
pytest tests/ -q
python test_agent_swarm.py
python scripts/check_harness.py
```
```
## Checkpoint: Test
Status: PASS/FAIL
Results: [X] passed, [Y] failed
Blockers: [list if any]
```
**Gate:** All tests must pass. Stop if FAIL.

### 2. Review — Code review gate
Run multi-role review (see `skills/review/`):
```
## Checkpoint: Review
Score: [score]/100
Decision: PASS/FAIL
Blocking issues: [count]
```
**Gate:** Score >= 70, zero CRITICAL issues. Stop if FAIL.

### 3. Version — Bump version
```
## Checkpoint: Version
Previous: [X.Y.Z]
New: [X.Y.Z+1]
Type: patch/minor/major
```

### 4. Commit — Create commit with changelog
```
## Checkpoint: Commit
Hash: [commit hash]
Message: [commit message]
Files: [count] changed
```

### 5. Push — Push to remote
```
## Checkpoint: Push
Remote: origin
Branch: [branch]
Status: PUSHED/FAILED
```
**Gate:** Requires explicit approval before push.

### 6. Ship Report
```
## Ship Report

Pipeline: Test → Review → Version → Commit → Push
Status: SHIPPED / BLOCKED at [stage]
Test: [results]
Review: [score]
Version: [old] → [new]
Commit: [hash]
Push: [status]
```

Output: Ship report with all stage results.
