---
name: scout
description: "Scout phase of the Swarm Cycle. Reconnaissance before action: read context, define goal, decompose tasks, assign roles, set constraints and success criteria."
---

# Scout — Reconnaissance

Like scout bees mapping the environment before the swarm acts, this phase maps the goal, constraints, and execution path before any code is written.

## When to use
- Starting any new task, feature, bugfix, or research
- Before writing the first line of code

## Procedure

### 1. Read the terrain
- `docs_canonical/REPO_MAP.md` — repo structure
- `docs_canonical/ARCHITECTURE.md` — module boundaries
- `docs_canonical/TASKS.md` — current priorities
- The relevant policy for your domain (see `AGENTS.md` routing table)

### 2. Define the mission

```
## Scout Report

**Mission:** [One sentence — what we're trying to achieve]

**Terrain:**
- Current state: [what exists now]
- Target state: [what should exist after]
- Constraints: [what we must NOT break]

**Task Decomposition:**
| # | Task | Role | Depends On | Est. |
|---|------|------|------------|------|
| 1 | [description] | Researcher | — | 5m |
| 2 | [description] | Analyst | 1 | 10m |
| 3 | [description] | Writer | 2 | 10m |

**Playbook:** [research / code_review / discover / strategy / swarm_feature / swarm_bugfix / swarm_research / none]

**Pack:** [research-pack / review-pack / pm-pack / none]

**Success Criteria:**
- [ ] [Measurable outcome]
- [ ] All tests pass (229)
- [ ] Harness check passes (22/22)
- [ ] No policy violations

**Risks:**
| Risk | Impact | Mitigation |
|------|--------|------------|
| [what could fail] | HIGH/MED/LOW | [prevention] |
```

### 3. Validate before proceeding
- Module boundaries respected? (ARCHITECTURE.md)
- Correct policy applied? (policy docs)
- Role assignments consistent? (role_policy.yaml)
- Playbook appropriate? (playbook_policy.yaml)

Output: Scout Report. Then proceed to → **Build**.

## Scout Templates

### Feature Scout
```
Mission: Implement [feature name]
Constraints: Zero deps, tests required, API stable
Tasks: 1.Research → 2.Implement → 3.Test → 4.Review
Playbook: swarm_feature
```

### Bugfix Scout
```
Mission: Fix [bug description]
Constraints: Minimal change, don't break existing tests
Tasks: 1.Reproduce → 2.Fix → 3.Regression test → 4.Verify
Playbook: swarm_bugfix
```

### Research Scout
```
Mission: Research [topic]
Constraints: Time-boxed, source-verified
Tasks: 1.Gather → 2.Analyze → 3.Synthesize → 4.Review
Pack: research-pack
Playbook: swarm_research
```
