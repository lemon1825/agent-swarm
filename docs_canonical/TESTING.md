# TESTING

## Testing Philosophy
This repository is test-first and regression-sensitive.
New logic should not be accepted unless: behavior is clearly defined, tests exist for that behavior, existing tests continue to pass.

## Testing Strategy
Testing is expected across: unit behavior, integration behavior, policy behavior, regression behavior, production-like error handling.

## Primary Test Areas
At minimum, the repository should verify:
- orchestration flow
- retry/timeout behavior
- approval handling
- checkpoint behavior
- ontology gate behavior
- role and handoff enforcement
- validation rules
- playbook recommendations
- skill genetics logic
- production error classification

## Required Verification Workflow
Before considering a change complete:
1. run targeted tests for touched modules
2. run broader test suite
3. verify no critical examples break
4. confirm public API remains coherent

## Coverage Expectations
High-risk areas must be strongly tested: execution engine, ontology gate behavior, validation logic, role/handoff policy, skill promotion/evolution.

## Special Rules

### Ontology Changes
Any ontology-related behavior change must include tests for: term resolution, aliases, ancestors, capability rules, gate mode behavior.

### Skill Genetics Changes
Any genetics-related change must include tests for: mutation, crossover, selection, lineage, replay/adversarial evaluation logic if affected.

### Recommendation Logic Changes
Any recommendation/routing change must include deterministic tests. No recommendation logic should rely on vague or untestable behavior.

## Unknown or Missing Expectations
If coverage targets are not explicitly enforced in the repository, do not invent numerical coverage thresholds. State only what is evidenced by the repo.
