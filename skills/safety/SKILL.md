---
name: safety
description: "Destructive command warnings and directory locks. Scan for dangerous patterns, check frozen paths, warn or block, and log actions."
---

# Safety — Protective Guardrails

Like guard bees at the hive entrance blocking threats, this skill scans for destructive operations and enforces directory locks to prevent accidental damage.

## When to use
- Before executing shell commands
- Before modifying protected files or directories
- As a pre-commit safety check

## Procedure

### 1. Scan for destructive patterns
Check commands against known dangerous patterns:
```
## Destructive Pattern Scan

| Pattern | Found | Command | Risk |
|---------|-------|---------|------|
| rm -rf | YES/NO | [command] | CRITICAL |
| git reset --hard | YES/NO | [command] | HIGH |
| git push --force | YES/NO | [command] | HIGH |
| DROP TABLE | YES/NO | [command] | CRITICAL |
| chmod 777 | YES/NO | [command] | MEDIUM |
| > /dev/null | YES/NO | [command] | LOW |
```

### 2. Check frozen paths
Verify no changes target protected directories:
```
## Frozen Path Check

Protected paths:
- agent_swarm/__init__.py (public API)
- policies/ (machine-readable policies)
- docs_canonical/ (authoritative docs)

| Path | Status | Action |
|------|--------|--------|
| [path] | FROZEN/ALLOWED | BLOCK/ALLOW |
```

### 3. Warn or block
```
## Safety Decision

| # | Threat | Severity | Action | Reason |
|---|--------|----------|--------|--------|
| 1 | [threat] | CRITICAL/HIGH/MEDIUM/LOW | BLOCK/WARN/ALLOW | [why] |
```

- CRITICAL: Block and require explicit override
- HIGH: Warn and require confirmation
- MEDIUM: Warn and proceed
- LOW: Log only

### 4. Log
```
## Safety Log

Timestamp: [ISO datetime]
Command: [what was checked]
Result: SAFE / WARNING / BLOCKED
Details: [findings]
```

Output: Safety check result with block/warn/allow decision.
