# ONTOLOGY_POLICY

## Purpose
Ontology in this repository provides a lightweight semantic layer for:
- task typing
- role compatibility
- capability requirements
- artifact relationships
- approval-related semantics
- playbook guidance

The core ontology must remain lightweight, deterministic, and low-dependency.

## Core Principles
- codebase truth first
- deterministic semantic checks in core
- expensive semantic reasoning belongs in product layer
- ontology should aid routing and validation, not make core unpredictable

## Supported Semantic Functions
At minimum, ontology may support: term resolution, alias resolution, ancestor closure, capability inheritance, required capability checks, produced artifact mapping, approval-required semantics, routing recommendations.

## Gate Modes

### SOFT
Record violations, do not block execution. Suitable for first-use experience and exploratory adoption.

### WARN
Record violations, surface stronger warnings. May require operator attention depending on runtime policy.

### STRICT
Violations may block: plan validation, task execution, handoff execution — depending on rule class and implementation. Strict behavior must remain deterministic and test-backed.

## Recommended Rule Classes
- unknown ontology term
- missing required capability
- invalid task-role pairing
- invalid task-playbook pairing
- invalid semantic handoff
- missing approval-required semantics

## Design Boundary
Core ontology must not require heavyweight graph infrastructure.
External RDF/OWL/SHACL/graph systems may be layered later outside core.

## Change Policy
Any ontology change must be accompanied by tests for: term lookup, aliases, ancestor behavior, capability requirements, gate mode behavior.

## Conflict Policy
If legacy docs describe ontology differently from code behavior, canonical interpretation must follow code behavior and note the conflict.
