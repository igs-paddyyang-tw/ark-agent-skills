---
title: "{Project Name} Execution Plan"
type: plan
version: "1.0"
status: draft
language: en
author: "{Author}"
created: YYYY-MM-DD
updated: YYYY-MM-DD
related_design: ""
---

# {Project Name} — Execution Plan

## 1. Summary

One paragraph describing the delivery goal and timeline.

## 2. Milestones

### Phase 1: {Phase Name} (Week 1-2)

| # | Task | Role | Output File | Estimate | AC-ID | AC |
|---|------|------|-------------|----------|-------|-----|
| 1.1 | ... | coder | `src/...` | 2h | AC-001 | ... |
| 1.2 | ... | ai-dev | `src/...` | 1h | AC-002 | ... |

> 📌 **Column Contract**:
> - **#**: `{milestone}.{seq}` (e.g. 1.1, 1.2). Cross-milestone deps noted as `[← 2.3]` after task name
> - **Role**: `coder` / `ai-dev` / `qa` / `human` (executor dispatches by this enum)
> - **Output File**: Full relative path; executor verifies file existence
> - **AC-ID**: Unique `AC-XXX` (three digits). Test docstrings must include `AC: AC-XXX` for traceability
> - See `ark-code-spec-validator/references/ac-id-convention.md`

**Phase 1 Deliverables**:
- [ ] Deliverable 1
- [ ] Deliverable 2

### Phase 2: {Phase Name} (Week 3-4)

| # | Task | Role | Output File | Estimate | AC-ID | AC |
|---|------|------|-------------|----------|-------|-----|
| 2.1 | ... | coder | `src/...` | 3h | AC-003 | ... |
| 2.2 | (needs 1.2 output) ... [← 1.2] | qa | `tests/...` | 1h | AC-004 | ... |

**Phase 2 Deliverables**:
- [ ] Deliverable 1
- [ ] Deliverable 2

## 3. Risk Management

| Risk | Probability | Impact | Mitigation | Trigger |
|------|-------------|--------|------------|---------|
| ... | H/M/L | H/M/L | ... | ... |

## 4. Verification Criteria

| Category | Metric | Target | Method |
|----------|--------|--------|--------|
| Unit Tests | Coverage | > 80% | pytest --cov |
| Integration | E2E | All pass | CI pipeline |
| Performance | P99 latency | < 3s | Load test 48hr |
| Security | Vulnerability scan | 0 critical | SAST/DAST |

## 5. Rollback Plan

| Trigger | Steps | Estimated Time | Owner |
|---------|-------|----------------|-------|
| ... | ... | ... | ... |

## 6. Dependencies & Prerequisites

- External dependencies
- Environment requirements
- Staffing requirements

## 7. Communication Plan

| Event | Audience | Channel | Frequency |
|-------|----------|---------|-----------|
| Progress update | Team | Slack | Weekly |
| Risk escalation | Management | Meeting | Immediate |
| Launch notification | All | Email | Once |
