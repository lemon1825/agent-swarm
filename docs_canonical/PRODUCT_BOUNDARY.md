# PRODUCT_BOUNDARY

## Purpose
This document defines the line between:
- open-source engine scope
- hosted/commercial product scope

The goal is to protect repository clarity and avoid mixing core engine concerns with product-layer concerns.

## Core Engine Scope
The open-source engine may include:
- orchestration core
- ontology core
- validation core
- skill evolution core
- playbooks
- CLI
- examples
- tests
- documentation

## Product Layer Scope
The following belong outside the engine layer:
- hosted execution platform
- dashboard UI
- approval inbox UI
- team/workspace features
- billing
- tenant management
- enterprise governance UI
- persistent cloud backend
- premium domain packs and commercial admin tooling

## Boundary Rule
If a feature primarily exists to improve:
- hosted operations
- billing
- tenant administration
- UI management
- enterprise governance

it belongs in product scope, not engine scope.

## Engine Rule
If a feature primarily improves:
- execution safety
- semantic routing
- validation correctness
- skill evolution reliability
- testability

it may belong in engine scope.

## Stability Principle
Engine simplicity is more valuable than packing product features into the core repository.

## Commercialization Note
Open-source trust can be built through the engine.
Revenue should primarily come from:
- hosted execution
- team workflows
- governance tooling
- premium packs
- enterprise services
