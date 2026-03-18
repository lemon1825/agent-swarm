# STYLEGUIDE

## General Style Principles
- Prefer clarity over cleverness
- Prefer explicit naming over compressed abstractions
- Keep core deterministic where possible
- Keep low-level runtime logic readable
- Avoid unnecessary dependency growth

## File and Module Organization
Modules should remain conceptually separated:
- execution logic in `core.py`
- ontology logic in `ontology.py`
- validation in `validation.py`
- genetics in `genetics.py`
- playbooks in `playbooks.py`

Do not collapse unrelated concepts into a single module unless there is a strong reason.

## Naming Conventions
- Use clear, descriptive names
- Prefer singular nouns for entities and models
- Prefer action-oriented names for execution functions
- Keep role, task, skill, ontology terms semantically explicit

Examples: `OntologyTerm`, `LineageRecord`, `recommend_playbook`, `score_task_role_fit`

## Public API Rules
Only stable, intentional concepts should be exported through package entry points.
Avoid exporting internal helpers unless they are intended for reuse.

## Code Organization Principles
- Core runtime logic should not contain UI concerns
- Policy logic should be isolated and explicit
- Validation logic should not be hidden in ad hoc branches
- Skill evolution logic should be testable independently
- Ontology logic should remain explainable and inspectable

## Documentation in Code
Use docstrings for: public classes, public functions, non-obvious policy behavior, gate mode semantics, genetics operators.

## Example and Test Naming
Examples should indicate their scenario clearly: basic, ontology/playbook, production-like.
Tests should indicate: the behavior being asserted, the policy or module being exercised.
