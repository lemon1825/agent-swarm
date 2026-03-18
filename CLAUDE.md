# CLAUDE.md

This file is the entry point for Claude Code when working on this repository.

## First Steps
1. Read `AGENTS.md` for operating rules
2. Read `docs_canonical/REPO_MAP.md` for repository structure
3. Read the relevant policy document before touching any subsystem

## Swarm Cycle Workflow

This repository includes Swarm Cycle skills in `skills/`. Use them for any task:

```
skills/scout/   → Plan: define goal, tasks, roles, constraints
skills/build/     → Do: execute with checkpoints and role rules
skills/guard/  → Check: tests, policy compliance, gap analysis
skills/evolve/    → Act: fixes, docs, lessons, next steps
skills/swarm-cycle/   → All 4 phases in one flow
```

**Quick Swarm Cycle for any task:**
1. Read `skills/swarm-cycle/SKILL.md`
2. Follow the cycle: Scout → Build → Guard → Evolve
3. Use `templates/swarm_cycle_templates.md` for structured output

**Cycle types:**
- Feature delivery: Plan scope → Implement → Test → Document
- Bugfix: Reproduce → Fix → Regression test → Lessons
- Research: Define question → Gather → Synthesize → Extract skills
- Code review: Scope → Scan → Prioritize → Fix suggestions

## Quick Reference

### Run tests
```bash
pytest tests/ -q                    # 106 pytest tests
python test_agent_swarm.py           # 123 integration tests
python scripts/check_harness.py      # 22 harness checks
```

### Verify import
```bash
python -c "from agent_swarm import Swarm; print('OK')"
```

### CLI
```bash
python -m agent_swarm --version
python -m agent_swarm --playbooks
python -m agent_swarm --ontology
python -m agent_swarm --packs
```

### MCP
```bash
python -m agent_swarm.mcp_server          # Start MCP server
python -m agent_swarm.mcp_server --setup  # Show setup guide
```

## Non-Negotiable Rules
- Zero external dependencies in `agent_swarm/`
- Every feature must have a test
- `pytest tests/ -q` must pass before any commit
- Public API (`from agent_swarm import Swarm`) must never break
- Codebase is ground truth over documentation

## Documentation Hierarchy
1. `docs_canonical/` — authoritative policy and architecture
2. `policies/` — machine-readable YAML policy definitions
3. `skills/` — Claude Code Swarm Cycle workflow skills
4. `AGENTS.md` — agent operating instructions
5. `README.md` — public-facing documentation

If conflicts exist between layers, lower-numbered sources take precedence.

## Policy-Aware Work Routing

| Changing... | Read first |
|---|---|
| Ontology behavior | ONTOLOGY_POLICY.md, ARCHITECTURE.md |
| Role routing | ROLE_POLICY.md, EXECUTION_POLICY.md |
| Execution logic | EXECUTION_POLICY.md, ARCHITECTURE.md |
| Skill evolution | SKILL_EVOLUTION_POLICY.md |
| Playbooks | PLAYBOOK_POLICY.md, ONTOLOGY_POLICY.md |
| Product boundary | PRODUCT_BOUNDARY.md |
