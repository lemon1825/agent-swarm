---
name: swarm-cycle
description: "Complete Swarm Cycle: Scout → Build → Guard → Evolve. The signature workflow of Agent Swarm. Use for any task: feature, bugfix, research, review."
---

# Swarm Cycle

**Scout → Build → Guard → Evolve**

The Swarm Cycle is Agent Swarm's workflow methodology. Like a bee colony: scouts map the terrain, builders execute, guards protect quality, and the colony evolves.

## Quick Start

For any task in this repository, follow this cycle:

```
1. SCOUT  → Map goal, constraints, tasks, roles, criteria
2. BUILD  → Execute in parallel with checkpoints and role rules
3. GUARD  → Tests + policy + criteria + gap analysis
4. EVOLVE → Fixes + docs + lessons + skill extraction + next cycle
```

## Cycle Types

### Feature Delivery
```
Scout: Define scope, decompose, assign roles
Build: Implement + test, follow module boundaries
Guard: 229 tests + harness + policy compliance
Evolve: Update docs, extract patterns, define follow-up
Playbook: swarm_feature
```

### Bugfix
```
Scout: Reproduce, identify root cause, plan minimal fix
Build: Fix + regression test
Guard: All tests pass, no side effects
Evolve: Document cause, prevent recurrence
Playbook: swarm_bugfix
```

### Research
```
Scout: Define question, choose pack, set scope
Build: Gather → Analyze → Synthesize
Guard: Sources verified, findings structured
Evolve: Extract skills, define follow-up research
Pack: research-pack
Playbook: swarm_research
```

### Code Review
```
Scout: Define scope, select review-pack
Build: Scan → Prioritize → Fix suggestions
Guard: All findings addressed
Evolve: Update standards if patterns found
Pack: review-pack
```

## Rules
1. Always start with Scout — never skip reconnaissance
2. Always run Guard — never ship without verification
3. Always Evolve — the swarm must get smarter every cycle
4. Follow `policies/` YAML files for role and execution rules
5. Use `templates/swarm_cycle_templates.md` for structured output

## MCP Integration
```
Scout: swarm_ontology → recommend_role, recommend_playbook
Build: swarm_run → parallel execution with agents
Guard: swarm_skills → check effectiveness
Evolve: swarm_skills → effectiveness report
```

## Output Format
```
## Swarm Cycle: [type] — [description]

### Scout
Mission: [1 sentence]
Tasks: [count] | Roles: [count] | Playbook: [name]

### Build
Completed: [X]/[Y] | Files: [count] | Time: [duration]

### Guard
Tests: [X]/229 | Policy: [X] compliant | Harness: PASS
Criteria: [X]/[Y] met | Gaps: [count]

### Evolve
Fixes: [count] | Docs: [count] | Skills extracted: [count]
Next: [1 sentence]

### Result: PASS / FAIL / PARTIAL
```
