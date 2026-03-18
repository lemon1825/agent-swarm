# WORKFLOWS

## Development Workflow
All repository work should follow this sequence:
1. Read `REPO_MAP.md`
2. Read relevant policy documents
3. Inspect target code path
4. Make a plan
5. Implement narrowly
6. Run relevant tests
7. Update documentation if required

Do not skip validation.

## Agent Task Lifecycle
Standard agent lifecycle:
1. Plan
2. Implement
3. Verify
4. Document

This loop is mandatory for repository-safe changes.

## Policy-Aware Work Sequence

### If changing ontology behavior
Read first: `ONTOLOGY_POLICY.md`, `ARCHITECTURE.md`, `TESTING.md`

### If changing role routing or handoffs
Read first: `ROLE_POLICY.md`, `EXECUTION_POLICY.md`, `TESTING.md`

### If changing execution logic
Read first: `EXECUTION_POLICY.md`, `ARCHITECTURE.md`, `TESTING.md`

### If changing skill evolution
Read first: `SKILL_EVOLUTION_POLICY.md`, `TESTING.md`

### If changing playbooks
Read first: `PLAYBOOK_POLICY.md`, `ONTOLOGY_POLICY.md`, `TESTING.md`

## Local Development Workflow
Expected flow:
1. install dependencies
2. run examples if needed
3. run targeted tests
4. run broader test suite before finalizing

## Release and Packaging Workflow
For release-ready changes:
1. verify package imports correctly
2. verify CLI entry point works
3. verify examples still run
4. verify automated tests pass
5. ensure README usage remains accurate

## Documentation Workflow
Canonical docs are additive.
Do not rewrite or delete legacy docs unless explicitly instructed.
If documentation conflicts are found, flag them rather than silently resolving them.

## Workflow Stability Rule
Repository stability takes priority over documentation neatness.
If a proposed documentation change risks breaking references, preserve stability.
