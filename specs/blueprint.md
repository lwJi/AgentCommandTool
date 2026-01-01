# blueprint.md — Iterative Refinement Architecture

## 0) Objective
Produce **high-quality, criteria-verified outputs** from ambiguous goals via a **closed-loop control architecture** that:
- separates *intent* (Manager) from *production* (Specialists) from *judgment* (Verifier),
- prevents drift and repetition,
- converges reliably within explicit budgets.

---

## 1) Roles

| Role | Responsibility | May Write | May Read |
|------|----------------|-----------|----------|
| **Manager** | Owns task definition, decomposes work, selects strategy, decides stop/escalate/accept | Task Spec, Plan, Decisions Log, Delta Summary | All state |
| **Specialist** | Generates candidate artifacts for assigned packets | Candidates only | Task Spec, assigned Packets, own Verification Reports |
| **Verifier** | Evaluates candidates against criteria; issues diagnostic reports | Verification Reports only | Task Spec, Candidate under review, attached evidence, prior reports (for consistency checks only) |

**Communication constraint:** Manager-to-Verifier communication must go through Task Spec or candidate evidence — never via Decisions Log.

---

## 2) State

The system maintains a **Working Set** (active state) and an **Archive** (reference-only history).

### Working Set (bounded, used for decisions)

| Section | Contents |
|---------|----------|
| **Task Spec** | Objective (one sentence), Constraints (must/must-not), Acceptance Criteria (versioned, with criterion IDs C1, C2, …), Risk notes |
| **Plan** | Packet ID, local objective, inputs/outputs, dependencies, **owned criterion IDs** |
| **Criteria Map** | For each criterion ID: `owned-by: [packets]` OR `integration-level` OR `waived: reason` |
| **Active Candidates** | Candidate ID → Packet ID, assumptions, provenance |
| **Latest Reports** | Verification reports for active candidates |
| **Delta Summary** | What changed this iteration, remaining unmet criteria |
| **Decisions Log** | Iteration decisions with rationale (Manager-only) |

### Archive
Older candidates, reports, and decision details retained by ID. Not used for reasoning unless Manager promotes them back to Working Set.

**Invariant:** Working Set must fit context budget. Archive is invisible to roles unless promoted.

---

## 3) Criteria Rules

1. Acceptance criteria have stable **criterion IDs** (C1, C2, …).
2. Packets must not define local criteria independent of these IDs.
3. Every criterion ID must appear in the Criteria Map as: owned by ≥1 packet, OR integration-level, OR waived.
4. Criteria changes require version increment and logged rationale.

---

## 4) Lifecycle

```
┌─────────────────────────────────────────────────────────┐
│  1. FRAME     Manager sets Task Spec + budgets          │
│  2. DECOMPOSE Manager creates packets, assigns criteria │
│  3. PRODUCE   Specialists generate candidates           │
│  4. VERIFY    Verifier evaluates per-packet criteria    │
│  5. DECIDE    Manager chooses: repair/re-plan/accept    │
│  6. COMPACT   Manager updates Working Set, archives old │
│  7. ITERATE   Loop until pass or stop condition         │
│  8. FINALIZE  Verify integration criteria, output result│
└─────────────────────────────────────────────────────────┘
```

### Stop Conditions (define before iteration)
- Max iterations / time / cost budget
- Maximum tolerated uncertainty
- Escalation threshold (e.g., same failure N times)
- Accept-with-waiver rules

### Exit Statuses
`PASS` | `BUDGET_EXHAUSTED` | `ESCALATED` | `UNCERTAINTY_LIMIT` | `ITERATION_LIMIT`

On non-pass exit: output best candidate + unmet criteria + verification report.

---

## 5) Verification Contract

### Report Structure
| Field | Description |
|-------|-------------|
| Outcome | `PASS` / `FAIL` / `PARTIAL` / `UNKNOWN` |
| Criteria coverage | Pass/fail/unknown per criterion ID |
| Failure labels | From taxonomy below |
| Repair targets | What must change (diagnostic, not solution) |
| Confidence | How certain, how costly if wrong |

### Failure Taxonomy
1. **Coverage** — missed criterion
2. **Violation** — did something disallowed
3. **Inconsistency** — self-contradiction
4. **Unsupported** — assertion without evidence
5. **Ambiguity** — cannot verify (return UNKNOWN)
6. **Scope** — answered wrong question
7. **Overconfidence** — uncertainty not acknowledged

### Verifier Boundaries
The Verifier must NOT:
- Introduce or modify criteria
- Reframe objective or constraints
- Propose solutions (repair targets are diagnostic only)
- Negotiate waivers

Every judgment must cite criterion IDs and evidence. If unverifiable → return `UNKNOWN`.

---

## 6) Iteration Strategies

| Strategy | When to Use |
|----------|-------------|
| **Targeted Repair** | Failures are local and actionable |
| **Re-plan** | Wrong assumptions or broken packet boundaries |
| **Parallel Regeneration** | Break correlated errors across candidates |
| **Escalation** | Verifier is inconsistent or blind |

### Anti-Loop Requirements
- Repairs must state what changed and why it resolves the failure.
- Track repeated failures; trigger re-plan or parallel regeneration automatically.
- No vague "try again" — require failure taxonomy + repair targets.

---

## 7) Failure Modes

| Mode | Cause | Guardrail |
|------|-------|-----------|
| **Hallucination loop** | Vague feedback + correlated blind spots | Require failure taxonomy, track repeats, mandate deltas |
| **Goalpost drift** | Silent criteria changes | Version criteria, log changes |
| **Reward hacking** | Verifier becomes predictable | Enforce criteria coverage, prefer hard-to-game checks |
| **Verifier inconsistency** | Shifting thresholds | Anchor to stable criteria, record justifications |

---

## 8) Definition of Done

A result is done when:
- Final candidate **passes** all criteria (or waivers recorded), OR
- System exits with explicit status + best candidate + unmet criteria documented

In both cases:
- Verification reports attached
- Decision log explains why this output was selected
