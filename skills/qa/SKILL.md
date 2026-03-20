---
name: qa
description: "Issue taxonomy and health score QA. Scan, classify by severity, compute health score, and generate actionable QA report."
---

# QA — Quality Assurance

Like worker bees inspecting every cell in the comb, this skill systematically scans for issues, classifies them, and produces a quantified health score.

## When to use
- Periodic codebase health checks
- Pre-release quality assessment
- After large refactoring or migration

## Procedure

### 1. Scan
Scan codebase for issues across all categories:
- Tests: coverage, flaky tests, missing assertions
- Code: complexity, duplication, dead code
- Security: hardcoded secrets, injection vectors
- Dependencies: outdated, vulnerable, unnecessary
- Documentation: stale, missing, inconsistent

### 2. Classify
Assign severity to each issue:
```
## Issue Taxonomy

| # | Issue | Category | Severity | File | Impact |
|---|-------|----------|----------|------|--------|
| 1 | [issue] | [category] | CRITICAL | [file:line] | [impact] |
| 2 | [issue] | [category] | HIGH | [file:line] | [impact] |
| 3 | [issue] | [category] | MEDIUM | [file:line] | [impact] |
| 4 | [issue] | [category] | LOW | [file:line] | [impact] |
| 5 | [issue] | [category] | INFO | [file:line] | [impact] |
```

Severity weights: CRITICAL=20, HIGH=10, MEDIUM=5, LOW=2, INFO=0

### 3. Score
```
## Health Score

Base: 100
Deductions:
- CRITICAL × [count] × 20 = -[total]
- HIGH × [count] × 10 = -[total]
- MEDIUM × [count] × 5 = -[total]
- LOW × [count] × 2 = -[total]

**Health Score: [max(0, 100 - deductions)]**
```

### 4. Report
```
## QA Report

Health Score: [score]/100
Rating: EXCELLENT (90+) / GOOD (70-89) / FAIR (50-69) / POOR (<50)
Issues: [total] ([critical] critical, [high] high, [medium] medium, [low] low, [info] info)
Top 3 priorities:
1. [most impactful issue + recommended fix]
2. [second issue + recommended fix]
3. [third issue + recommended fix]
```

Output: QA report with health score and prioritized issue list.
