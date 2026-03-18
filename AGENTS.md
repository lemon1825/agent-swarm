# Agent Operating Instructions

## Repository Knowledge Harness

This repository uses a canonical documentation layer
for repository knowledge.

Repository architecture, workflows, coding conventions,
and testing policies are defined in:

    docs_canonical/

Agents must read these documents before performing
repository tasks.

Canonical documentation is the authoritative source
for repository behavior.

Legacy documentation may be used only for reference.

If canonical documentation conflicts with legacy documentation,
canonical documentation takes precedence.

## Related Entry Points

- `CLAUDE.md` — Claude Code specific entry point (references this file)
- `README.md` — Public-facing documentation
- `CONTRIBUTING.md` — Contributor guidelines

## Canonical Document Structure

```
docs_canonical/
├── REPO_MAP.md                ← Start here. Repository structure and entry points.
├── ARCHITECTURE.md            ← Module boundaries, data flow, execution path.
├── WORKFLOWS.md               ← Development process, agent task lifecycle.
├── STYLEGUIDE.md              ← Coding conventions, naming, formatting.
├── TESTING.md                 ← Test strategy, structure, coverage expectations.
├── TASKS.md                   ← Current backlog and priorities.
├── ROLE_POLICY.md             ← Role responsibilities, handoff rules, approval authority.
├── ONTOLOGY_POLICY.md         ← Semantic layer rules, gate modes, design boundary.
├── EXECUTION_POLICY.md        ← Timeout, retry, checkpoint, budget, approval policy.
├── SKILL_EVOLUTION_POLICY.md  ← Mutation, crossover, fitness, promotion, rollback policy.
├── PLAYBOOK_POLICY.md         ← Playbook selection, recommendation, next-step rules.
└── PRODUCT_BOUNDARY.md        ← Engine scope vs product scope boundary.
```

## Machine-Readable Policies

```
policies/
├── role_policy.yaml
├── ontology_policy.yaml
├── execution_policy.yaml
├── skill_evolution_policy.yaml
└── playbook_policy.yaml
```

These YAML files are the machine-readable counterparts to policy documents.
They may be loaded by the engine at runtime for policy enforcement.

## Agent Rules

1. **Read `docs_canonical/REPO_MAP.md` first** before any task.
2. **Read relevant policy documents** before touching that subsystem.
3. **Zero dependencies.** Never add external packages to `agent_swarm/`.
4. **Every feature needs a test.** Add to `tests/test_all.py`.
5. **Run tests before committing:** `pytest tests/ -q` must pass.
6. **Don't break public API.** `from agent_swarm import Swarm` must always work.
7. **Don't modify existing test assertions** unless the behavior intentionally changed.
8. **Codebase is ground truth.** If docs conflict with code, code wins.

## Task Execution Loop

```
1. PLAN      → Read docs_canonical/ → understand scope and constraints
2. IMPLEMENT → Write code → follow STYLEGUIDE.md → zero dependencies
3. VERIFY    → pytest tests/ -q → python test_agent_swarm.py → both must pass
4. DOCUMENT  → Update docs_canonical/ if architecture/behavior changed
```

## Policy-Aware Work Routing

| Changing... | Read first |
|---|---|
| Ontology behavior | ONTOLOGY_POLICY.md, ARCHITECTURE.md, TESTING.md |
| Role routing / handoffs | ROLE_POLICY.md, EXECUTION_POLICY.md, TESTING.md |
| Execution logic | EXECUTION_POLICY.md, ARCHITECTURE.md, TESTING.md |
| Skill evolution | SKILL_EVOLUTION_POLICY.md, TESTING.md |
| Playbooks | PLAYBOOK_POLICY.md, ONTOLOGY_POLICY.md, TESTING.md |
| Product boundary | PRODUCT_BOUNDARY.md |

## Module Authority

| Module | Responsibility | May import from |
|---|---|---|
| core.py | Swarm engine, execution | skills, ontology, validation, playbooks, models, metrics, session |
| genetics.py | Skill evolution | skills only |
| All others | Standalone | Nothing internal |

## Stability Invariants

The following must NEVER be violated:
- existing file paths
- existing documentation files
- cross-document references
- repository conventions
- codebase structure
- zero-dependency constraint

Repository stability takes priority over documentation clarity.
