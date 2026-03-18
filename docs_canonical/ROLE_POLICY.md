# ROLE_POLICY

## Purpose
This document defines role responsibilities, allowed task patterns, and permitted handoff paths.
Role policy exists to prevent ad hoc role assignment and unsafe task routing.

## Core Role Types
Common roles include: researcher, analyst, reviewer, approver, strategist, writer.
The exact set should follow codebase truth if expanded.

## General Role Rules

### Researcher
Typical responsibility: gather information, explore sources, perform discovery-oriented tasks.
Typical allowed tasks: research, discovery, market scan, source gathering.

### Analyst
Typical responsibility: compare, interpret, synthesize, structure findings, derive conclusions.
Typical allowed tasks: analysis, comparison, synthesis, prioritization.

### Reviewer
Typical responsibility: validate outputs, inspect correctness, check compliance or quality.
Typical allowed tasks: review, validation, policy check, consistency check.

### Approver
Typical responsibility: human or policy gate, final approval decision, acceptance/rejection authority.
Typical allowed tasks: approve, reject, finalize gated outcomes.

### Strategist / Writer
Used where playbooks or content workflows require them.
Their use should remain consistent with ontology and playbook policy.

## Handoff Policy
Handoffs must respect organizational and role constraints.
Allowed examples: researcher → analyst, analyst → reviewer, reviewer → approver.
Disallowed handoffs should be blocked when policy says so.

## Approval Authority
Not every role may approve. Approval-capable roles must be explicitly designated by policy and/or codebase logic.

## Role Assignment Principle
Role assignment should prefer policy-grounded routing over freeform inference.
If ontology or playbook guidance is available, it should be used.

## Violations
Role policy violations should be: recorded, surfaced clearly, optionally blocked depending on execution mode and policy class.
