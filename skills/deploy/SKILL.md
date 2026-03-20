---
name: deploy
description: "Deployment verification and rollback plan. Pre-deploy checks, deploy, verify, monitor, and generate rollback instructions."
---

# Deploy — Deployment Verification

Like a swarm carefully selecting and verifying a new hive location before committing, this skill ensures deployments are verified and reversible.

## When to use
- Deploying to staging or production
- Verifying a deployment succeeded
- Creating rollback plans

## Procedure

### 1. Pre-deploy checks
```
## Pre-Deploy Checklist

| Check | Status | Details |
|-------|--------|---------|
| All tests pass | PASS/FAIL | [test results] |
| Code review approved | YES/NO | [reviewer] |
| Version bumped | YES/NO | [version] |
| Changelog updated | YES/NO | [changes] |
| Config validated | YES/NO | [env vars, secrets] |
| Rollback plan ready | YES/NO | [see section 5] |
| Dependencies locked | YES/NO | [lock file hash] |
```

### 2. Deploy
```
## Deployment

Target: [staging/production]
Method: [deploy method]
Version: [version being deployed]
Timestamp: [ISO datetime]
Status: SUCCESS/FAILED
```

### 3. Verify
Post-deployment verification:
```
## Post-Deploy Verification

| Check | Status | Details |
|-------|--------|---------|
| Service healthy | PASS/FAIL | [health endpoint] |
| Smoke tests pass | PASS/FAIL | [test results] |
| Metrics normal | PASS/FAIL | [dashboard link] |
| No error spikes | PASS/FAIL | [log check] |
| Feature flags correct | PASS/FAIL | [flag states] |
```

### 4. Monitor
```
## Monitoring Window

Duration: [monitoring period]
Key metrics:
| Metric | Baseline | Current | Status |
|--------|----------|---------|--------|
| Error rate | [baseline] | [current] | OK/ALERT |
| Latency p99 | [baseline] | [current] | OK/ALERT |
| CPU/Memory | [baseline] | [current] | OK/ALERT |
```

### 5. Rollback plan
```
## Rollback Plan

Trigger conditions:
- Error rate > [threshold]
- Latency p99 > [threshold]
- Critical functionality broken

Rollback steps:
1. [step with exact command]
2. [step with exact command]
3. [step with exact command]

Previous version: [version to rollback to]
Rollback estimated time: [duration]
Data migration rollback: [YES/NO — details if YES]
```

### 6. Deploy Report
```
## Deploy Report

Version: [old] → [new]
Target: [environment]
Status: DEPLOYED / ROLLED BACK / FAILED
Verification: PASS/FAIL
Rollback plan: READY
Next: [monitoring window or action]
```

Output: Deployment report with rollback instructions.
