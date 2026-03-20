---
name: review
description: "Multi-role code and specification review with scoring. Distribute to specialized reviewers, collect feedback, score, and make gate decisions."
---

# Review — Multi-Role Assessment

Like guard bees inspecting every arrival from multiple angles, this skill applies structured multi-perspective review with quantified scoring and gate decisions.

## When to use
- After implementing a feature or fix
- Reviewing specifications before implementation
- Pre-commit quality gate

## Roles
- **Spec Compliance** — verifies requirements are met
- **Code Quality** — checks readability, structure, patterns
- **Security** — identifies vulnerabilities and risks
- **Design** — evaluates architecture and maintainability

## Procedure

### 1. Distribute to reviewers
Each role reviews independently against their criteria:
```
## Review Assignments

| Reviewer | Focus | Artifact |
|----------|-------|----------|
| Spec Compliance | Requirements coverage | [file/spec] |
| Code Quality | Readability, patterns | [file/diff] |
| Security | Vulnerabilities | [file/diff] |
| Design | Architecture fit | [file/diff] |
```

### 2. Collect feedback
```
## Reviewer Feedback

| Reviewer | Finding | Severity | Line/Section |
|----------|---------|----------|--------------|
| [role] | [issue] | CRITICAL/HIGH/MEDIUM/LOW | [location] |
```

### 3. Score
```
## Review Score

| Category | Score (0-100) | Weight | Weighted |
|----------|---------------|--------|----------|
| Spec Compliance | [score] | 30% | [weighted] |
| Code Quality | [score] | 25% | [weighted] |
| Security | [score] | 25% | [weighted] |
| Design | [score] | 20% | [weighted] |
| **Total** | | | **[total]** |
```

### 4. Gate decision
```
## Gate Decision

Score: [total]/100
Threshold: 70 (configurable)
Decision: PASS / FAIL
Blocking issues: [count CRITICAL + HIGH]
Action: Proceed to next phase / Return to Build
```

Output: Review report with pass/fail and score.
