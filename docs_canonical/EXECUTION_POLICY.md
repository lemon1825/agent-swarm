# EXECUTION_POLICY

## Purpose
Execution policy defines how the runtime behaves during task execution.
This includes: timeouts, retries, failure behavior, checkpoints, approvals, budget handling, ontology violations during execution.

## Execution Principles
- runtime behavior should remain deterministic where possible
- unsafe execution paths should be blocked or surfaced clearly
- checkpointing should preserve recoverability
- policy should be explicit, not hidden in incidental branches

## Timeout Policy
Timeout ceilings must not be bypassed by role-level overrides. Plan-level limits take precedence when appropriate.

## Retry Policy
Retries should be bounded and policy-controlled. Retry behavior must be testable and visible.

## Failure Policy
Failures should be classified where possible. Execution should avoid silent failure. Structured error information is preferred.

## Approval Policy
Approval-required tasks must enter an approval-aware state. Rejected work must not silently continue. Approval paths must be observable and test-backed.

## Checkpoint Policy
Checkpoint behavior should be explicit. Important execution phases should be preserved. Checkpointing should support recoverability without producing hidden duplicated work.

## Budget Policy
Execution should track budget-aware behavior where supported. Budget handling should be: visible, deterministic, testable.

## Ontology Violation Policy
Ontology violations must be handled according to gate mode: soft, warn, strict. Strict-mode behavior must be explicitly documented and test-backed.

## Handoff Policy During Execution
Typed handoff payloads must be validated before use. Invalid handoffs should fail clearly rather than degrade silently.

## Required Testing
Execution policy changes require tests for: timeout behavior, retry behavior, approval behavior, checkpoint behavior, budget handling, ontology gate behavior, handoff validation.
