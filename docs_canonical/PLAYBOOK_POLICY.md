# PLAYBOOK_POLICY

## Purpose
Playbooks provide reusable workflow structure for recurring task patterns.

They are intended to:
- reduce ad hoc planning
- increase consistency
- improve routing and next-step guidance
- align goals with known workflow patterns

## Playbook Types
Two broad categories should remain distinct:

### Workflow Playbooks
Multi-step structured execution paths.

### Reference Skills / Reference Assets
Supporting knowledge or reusable guidance, not full execution workflows.

These should not be conflated.

## Playbook Selection Principles
Playbook selection should consider:
- goal type
- task type
- ontology term alignment
- role compatibility
- expected outputs

## Recommendation Rules
When playbook recommendation exists, it should be:
- deterministic when possible
- explainable
- test-backed

## Next-Step Guidance
Playbooks may recommend next steps after completion.
Next-step guidance should be grounded in:
- workflow sequence
- ontology alignment
- goal ancestry
- repository-supported routing logic

## Playbook Boundaries
Playbooks should not become an uncontrolled scripting layer.
They should remain inspectable and bounded.

## Required Testing
Playbook changes should include tests for:
- recommendation correctness
- workflow compatibility
- next-step guidance
- ontology-aware matching where applicable
