---
name: brainstorm
description: "Multi-perspective idea exploration and design document generation. Diverge, converge, and synthesize into actionable specifications."
---

# Brainstorm — Multi-Perspective Ideation

Like a hive mind generating and filtering ideas through multiple lenses, this skill explores solution spaces from diverse perspectives before converging on a design.

## When to use
- Starting a new feature with unclear requirements
- Exploring multiple approaches to a complex problem
- Generating design documents from scratch

## Roles
- **Devil's Advocate** — challenges assumptions, finds flaws
- **Optimist** — explores possibilities, finds opportunities
- **Pragmatist** — grounds ideas in reality, estimates effort
- **User Advocate** — represents end-user needs and friction

## Procedure

### 1. Diverge — Generate ideas
Each role generates ideas independently:
```
## Diverge Report

| # | Idea | Perspective | Rationale |
|---|------|-------------|-----------|
| 1 | [idea] | Devil's Advocate | [why] |
| 2 | [idea] | Optimist | [why] |
| 3 | [idea] | Pragmatist | [why] |
| 4 | [idea] | User Advocate | [why] |
```

### 2. Converge — Evaluate ideas
Score each idea against feasibility, impact, and risk:
```
## Evaluation Matrix

| Idea | Feasibility | Impact | Risk | Score |
|------|-------------|--------|------|-------|
| [idea] | HIGH/MED/LOW | HIGH/MED/LOW | HIGH/MED/LOW | [1-10] |
```

### 3. Synthesize — Design document
Combine top-scoring ideas into a specification:
```
## Design Document

**Goal:** [one sentence]
**Chosen approach:** [top idea]
**Pros:** [list]
**Cons:** [list]
**Risks:** [list with mitigations]
**Alternatives considered:** [rejected ideas with reasons]
**Next steps:** [action items]
```

Output: Design document with pros/cons/risks. Then proceed to → **Build** or **Review**.
