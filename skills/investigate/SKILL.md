---
name: investigate
description: "Root cause analysis with evidence chain. Reproduce, hypothesize, test, build evidence chain, and report findings."
---

# Investigate — Root Cause Analysis

Like scout bees tracing a scent trail back to its source, this skill systematically tracks down root causes through hypothesis testing and evidence chains.

## When to use
- Debugging a complex or intermittent bug
- Understanding unexpected system behavior
- Post-incident root cause analysis

## Procedure

### 1. Reproduce
Establish a reliable reproduction:
```
## Reproduction

Steps:
1. [step]
2. [step]
3. [step]

Expected: [what should happen]
Actual: [what happens]
Reproducibility: Always / Intermittent ([X]% of attempts)
Environment: [relevant details]
```

### 2. Hypothesize
Generate candidate root causes:
```
## Hypotheses

| # | Hypothesis | Likelihood | Test method |
|---|-----------|------------|-------------|
| 1 | [cause] | HIGH/MED/LOW | [how to verify] |
| 2 | [cause] | HIGH/MED/LOW | [how to verify] |
| 3 | [cause] | HIGH/MED/LOW | [how to verify] |
```

### 3. Test hypotheses
Test each hypothesis systematically:
```
## Hypothesis Testing

| # | Hypothesis | Test | Result | Verdict |
|---|-----------|------|--------|---------|
| 1 | [cause] | [what was done] | [observation] | CONFIRMED/REJECTED |
| 2 | [cause] | [what was done] | [observation] | CONFIRMED/REJECTED |
```

### 4. Build evidence chain
```
## Evidence Chain

Root cause: [confirmed hypothesis]

Evidence:
1. [observation] → supports [conclusion]
2. [observation] → supports [conclusion]
3. [observation] → confirms root cause

Timeline:
[when introduced] → [when manifested] → [when detected]
```

### 5. Investigation Report
```
## Investigation Report

Bug: [description]
Root cause: [one sentence]
Evidence confidence: HIGH/MEDIUM/LOW
Impact: [scope of affected functionality]
Fix: [recommended approach]
Prevention: [how to prevent recurrence]
Related: [similar past issues if any]
```

Output: Investigation report with root cause and evidence chain.
