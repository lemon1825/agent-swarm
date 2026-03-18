# ARCHITECTURE

## System Overview
Agent Swarm Core is a lightweight multi-agent orchestration engine that coordinates:
- task decomposition
- role assignment
- workflow/playbook selection
- execution with retries/timeouts/checkpoints
- approval-aware flow control
- ontology-guided capability validation
- skill retrieval and evolution
- metrics collection

It is designed to be embedded inside a product or internal system rather than act as a full hosted platform.

## Core Execution Flow
Typical flow:

1. Receive goal and task specification
2. Infer or validate task decomposition
3. Select workflow/playbook if applicable
4. Assign role(s) to task(s)
5. Apply ontology and policy validation
6. Execute tasks with retry/timeout/checkpoint logic
7. Route handoffs where needed
8. Require approval where policy demands
9. Collect outputs, metrics, lineage, and artifacts
10. Optionally evolve skill population via replay/genetics logic

## Major Architectural Layers

### 1. Orchestration Layer
Responsible for: execution loop, dependency ordering, concurrency, retries, checkpointing, approvals.
Primary module: `core.py`

### 2. Knowledge and Semantics Layer
Responsible for: ontology terms and relations, alias resolution, ancestor closure, capability inference, task-role/skill compatibility guidance.
Primary module: `ontology.py`

### 3. Validation Layer
Responsible for: input/output schema checks, structured validation errors, preset validation patterns, contract enforcement.
Primary module: `validation.py`

### 4. Skill Layer
Responsible for: skill storage, skill matching, skill metadata, replay-aware improvement paths.
Primary modules: `skills.py`, `genetics.py`

### 5. Workflow Layer
Responsible for: playbooks, recommended next steps, workflow-guided routing.
Primary module: `playbooks.py`

### 6. Operational Layer
Responsible for: metrics, session memory, error classification, execution observability.
Primary modules: `metrics.py`, `session.py`

## Module Boundaries

### `core.py`
May orchestrate execution and call into: validation, ontology, skills, playbooks, metrics, sessions.
It should not become a UI or billing layer.

### `ontology.py`
Defines semantic structure and lightweight reasoning.
It should remain deterministic and low-dependency.

### `genetics.py`
Defines skill evolution mechanics.
It should not introduce uncontrolled runtime mutation without validation and benchmark policy.

### `playbooks.py`
Defines workflow patterns and next-step guidance.
It should not become a general UI workflow editor.

## Architectural Constraints
- Core engine should remain lightweight
- Core engine should remain safe for embedding
- Ontology reasoning in core should be deterministic and low-cost
- Expensive or exploratory reasoning belongs to the product layer, not core
- Product-layer concerns must remain outside the engine boundary
- New policy logic must be backed by tests

## Policy ↔ Runtime Enforcement Mapping

Each canonical policy document maps to specific code locations where enforcement occurs.

| Policy Document | Primary Code | Enforcement Points |
|---|---|---|
| ROLE_POLICY.md | `core.py`, `ontology.py` | `_exec_slot()` org chart validation, handoff check, `detect_role_mismatch()` |
| ONTOLOGY_POLICY.md | `ontology.py`, `core.py` | `_exec_slot()` capability gate, `_validate_plan_ontology()`, `validate_plan_report()` |
| EXECUTION_POLICY.md | `core.py` | `_exec_slot()` timeout/retry, `_classify_error()` backoff, checkpoint phases, budget check, approval callback |
| SKILL_EVOLUTION_POLICY.md | `genetics.py`, `skills.py` | `evolve_generation()` crossover/adversarial/tournament, `evaluate_shadow_promotion()` 6-gate, `compute_fitness()` |
| PLAYBOOK_POLICY.md | `playbooks.py`, `ontology.py` | `recommend_playbook()`, `_auto_decompose()` playbook injection, `SOPPlaybook.next_steps` |
| PRODUCT_BOUNDARY.md | — | Not enforced in code. Governs repository scope decisions. |

### Enforcement Detail

**ROLE_POLICY enforcement in core.py `_exec_slot()`:**
1. Org chart handoff validation (step 1 of 10)
2. Typed handoff payload schema check (step 2)
3. Role mismatch detection via ontology (step 4)

**ONTOLOGY_POLICY enforcement in core.py `_exec_slot()`:**
1. Capability gate — SOFT/WARN/STRICT (step 3 of 10)
2. Plan-level validation before execution (`_validate_plan_ontology()`)
3. Structured violation output via `OntologyViolation` / `ValidationReport`

**EXECUTION_POLICY enforcement in core.py:**
1. `_classify_error()` → 7 error types with distinct retry/fail behavior
2. `_calc_backoff()` → exponential with jitter, class-specific ceilings
3. Budget check → `BudgetPolicy.block_on_exceed`
4. Checkpoint → 7-phase save/resume
5. Approval → `approval_callback` with async wait

**SKILL_EVOLUTION_POLICY enforcement in genetics.py:**
1. `crossover()` → distance guard (>0.3), domain compatibility
2. `adversarial_test()` → 5-7 scenarios, coverage threshold
3. `tournament_select()` → bottom 25% demoted
4. `compute_fitness()` → 6-component weighted score
5. `evaluate_shadow_promotion()` → 6-gate threshold in skills.py

### Machine-Readable Policy Files

Each YAML file in `policies/` corresponds to the canonical doc:

| Policy YAML | Canonical Doc |
|---|---|
| `policies/role_policy.yaml` | `ROLE_POLICY.md` |
| `policies/ontology_policy.yaml` | `ONTOLOGY_POLICY.md` |
| `policies/execution_policy.yaml` | `EXECUTION_POLICY.md` |
| `policies/skill_evolution_policy.yaml` | `SKILL_EVOLUTION_POLICY.md` |
| `policies/playbook_policy.yaml` | `PLAYBOOK_POLICY.md` |

## Codebase Truth Policy
If architecture documents conflict with code, code is the source of truth.
Canonical docs should reflect observable implementation and flag conflicts explicitly.

## Operational Layer (Symphony-inspired)

```
Event Source (GitHub/Linear/Webhook)
         ↓
TrackerAdapter → parses events, applies filters
         ↓
RunMachine → submit(RunConfig) → Run(state=QUEUED)
         ↓
Supervisor → concurrency control, failure isolation
         ↓
Run lifecycle: QUEUED → PLANNING → IMPLEMENTING → TESTING → APPROVAL → COMPLETED
         ↓
Swarm.run() executes inside isolated Workspace
         ↓
ProofBundle generated → tasks, tests, approval, tokens, cost, artifacts
```

### New Components

| Component | File | Role |
|---|---|---|
| RunMachine | run_machine.py | 10-state run lifecycle, proof bundles |
| WorkspaceManager | workspace.py | Per-run isolated execution sandbox |
| TrackerAdapter | tracker.py | Event-driven trigger (GitHub/Linear/webhook) |
| Supervisor | supervisor.py | Concurrency cap, failure isolation, auto-pause |
| MemoryStore | memory.py | Persistent 4-type memory across runs |
| StreamingAdapter | streaming.py | Token-by-token LLM output streaming |
| DurableCheckpoint | durable.py | File-based checkpoints surviving restarts |
| DetailedTracer | tracing.py | Per-node timing, tokens, cost + HTML export |
| LLMCache | cache.py | Response cache with TTL |
| SmartRouter | router.py | Auto model selection by task complexity |
| ToolRegistry | tools.py | 6 built-in tools (web_search, http_fetch, etc.) |
