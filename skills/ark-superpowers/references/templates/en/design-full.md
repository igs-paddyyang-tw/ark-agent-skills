---
title: "{Project Name} Design Document"
type: design
version: "1.0"
status: proposed
language: en
author: "{Author}"
created: YYYY-MM-DD
updated: YYYY-MM-DD
deciders: []
related_spec: ""
---

# {Project Name} — Design Document

## 1. Overview

This document describes the technical design for {system/feature}.

## 2. Context

- Related Spec: `docs/specs/{spec-file}.md`
- Current system state
- Technical debt and limitations

## 3. Architecture Decisions

### ADR-001: {Decision Title}

**Status**: proposed

**Context**: Why is this decision needed?

**Options**:

| Option | Pros | Cons | Notes |
|--------|------|------|-------|
| A: ... | ... | ... | ... |
| B: ... | ... | ... | ... |
| C: ... | ... | ... | ... |

**Decision**: Choose option X because...

**Consequences**:
- Positive: ...
- Negative: ...
- Risks: ...

## 4. System Architecture

### 4.1 High-Level Architecture

```text
[Component A] → [Component B] → [Component C]
                      ↓
               [Data Store]
```

### 4.2 Data Flow

Describe the complete data path from input to output.

### 4.3 API Design

| Endpoint | Method | Purpose | Request/Response |
|----------|--------|---------|------------------|
| ... | ... | ... | ... |

## 5. Failure Isolation & Degradation

| Failure Scenario | Blast Radius | Degraded Behavior | Recovery |
|------------------|--------------|-------------------|----------|
| ... | ... | ... | ... |

## 6. Security Considerations

- Authentication/Authorization
- Data encryption
- Input validation

## 7. Observability

- Metrics
- Logging
- Tracing
- Alerting

## 8. Technology Stack

| Purpose | Technology | Rationale |
|---------|-----------|-----------|
| ... | ... | ... |
