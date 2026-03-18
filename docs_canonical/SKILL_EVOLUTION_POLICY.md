# SKILL_EVOLUTION_POLICY

## Purpose
This document defines the policy layer for skill evolution, including genetics-inspired behavior.

Skill evolution is intended to improve repository behavior over time without sacrificing reliability.

## Core Concepts
- mutation
- crossover
- selection
- tournament / competition
- lineage
- replay evaluation
- adversarial evaluation
- promotion / rollback

## Policy Principle
Skill evolution is not freeform creativity.
It is controlled adaptation.

Any evolved skill must be:
- explainable
- testable
- benchmarkable
- reversible

## Mutation Policy
Mutation may be triggered by:
- repeated failure patterns
- validation breakdowns
- task-class weaknesses
- replay-identified gaps

Mutation should not bypass validation.

## Crossover Policy
Crossover may combine successful skills only when they are semantically compatible.

Compatibility should consider:
- task class
- domain
- expected inputs/outputs
- role compatibility
- ontology semantics where available

Crossover must not be assumed beneficial without evaluation.

## Selection Policy
Selection determines which skills remain:
- active
- shadow
- inactive
- archived

Selection should be based on measurable evidence rather than intuition alone.

## Fitness Policy
Fitness may consider:
- success rate
- retry count
- latency penalty
- validation quality
- adversarial robustness
- task-class usefulness

Fitness calculation must remain inspectable.

## Replay Policy
Replay-style evaluation is preferred before promotion where supported.
Newly evolved skills should not become active without meaningful evidence.

## Adversarial Policy
Adversarial tests may stress a skill before promotion.
These tests should be bounded and budget-aware.

## Lineage Policy
Lineage must track:
- parent skills
- generation
- mutation or crossover source
- promotion status
- rollback history if applicable

## Promotion Policy
Promotion must be explicit and threshold-based.
Promotion rules should be test-backed and deterministic where possible.

## Rollback Policy
If an evolved skill degrades quality or stability, rollback must be possible.

## Required Testing
Evolution policy changes require tests for:
- mutation behavior
- crossover compatibility
- selection outcomes
- lineage tracking
- promotion logic
- rollback logic where applicable
