# REPO_MAP

## Repository Purpose
This repository contains Agent Swarm Core, a lightweight, test-first multi-agent orchestration engine designed for:
- parallel research workflows
- review-heavy workflows
- approval-aware automation
- ontology-guided routing
- skill evolution and replay-based improvement

The repository is intended to serve as an embeddable engine rather than a full hosted platform.

## Major Directories
- `agent_swarm/`
  - core engine and runtime logic
- `tests/`
  - automated verification for engine behavior
- `examples/`
  - runnable usage examples
- `docs_canonical/`
  - canonical documentation layer for AI agents and maintainers
- `policies/`
  - machine-readable policy definitions (YAML)

## Core Modules
- `core.py`
  - orchestration runtime, execution flow, planner hooks, checkpoints, approvals
- `models.py`
  - core dataclasses and runtime models
- `validation.py`
  - schema validation, structured validation rules, presets
- `ontology.py`
  - ontology term/relation registry, capability inference, gate modes
- `skills.py`
  - skill storage, matching, retrieval logic
- `genetics.py`
  - skill genetics operators such as mutation, crossover, selection, lineage
- `playbooks.py`
  - built-in workflow definitions and next-step recommendations
- `metrics.py`
  - operational metrics collection
- `session.py`
  - session and memory handling
- `__main__.py`
  - CLI entry point

## Key Entry Points
- CLI execution via package entry point
- library import via `agent_swarm`
- examples in `examples/`
- automated tests in `tests/`

## High-Level Dependency Structure
The repository is intentionally lightweight.
The core engine should remain low-dependency and deterministic where possible.

Preferred dependency order:
1. codebase truth
2. canonical docs
3. legacy docs
4. optional external integrations

## Repository Boundary
This repository represents the engine layer.
The following are considered product-layer concerns and should remain outside core scope:
- hosted execution control plane
- dashboard UI
- approval inbox UI
- billing
- workspace/team features
- enterprise governance UI

## Added Modules (v1.0.0+)

| File | Lines | Purpose |
|---|---|---|
| `agent_swarm/tools.py` | 303 | Built-in tools: web_search, http_fetch, file_read, file_write, shell_exec, json_parse |
| `agent_swarm/memory.py` | 230 | Persistent 4-type memory: short, long, entity, context |
| `agent_swarm/streaming.py` | 170 | AsyncGenerator LLM streaming adapter |
| `agent_swarm/durable.py` | 137 | File-based persistent checkpoints for durable execution |
| `agent_swarm/tracing.py` | 294 | LangSmith-grade detailed tracing with HTML export |
| `agent_swarm/cache.py` | 108 | LLM response cache with TTL and hit-rate stats |
| `agent_swarm/router.py` | 106 | Smart model router: auto-selects fast/balanced/strong tier |
| `agent_swarm/run_machine.py` | 454 | Implementation run state machine + proof bundles |
| `agent_swarm/workspace.py` | 182 | Isolated per-run workspace with artifact collection |
| `agent_swarm/tracker.py` | 277 | GitHub/Linear/webhook trigger adapter |
| `agent_swarm/supervisor.py` | 218 | OTP-inspired supervisor: concurrency, failure isolation |
