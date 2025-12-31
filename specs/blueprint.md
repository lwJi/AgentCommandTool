# blueprint.md — North Star Architecture: Iterative Refinement (Manager → Specialists → Verifier → Iterate)

## 0) Objective
Produce **high-quality, criteria-verified outputs** from ambiguous goals via a **closed-loop control architecture** that:
- separates *intent* (what “good” means) from *production* (candidate generation) from *judgment* (verification),
- prevents drift and repetition,
- converges reliably within explicit budgets.

---

## 1) Roles (single-sentence responsibilities)

### Manager (Controller)
Owns the **task definition** (objective/constraints/acceptance criteria), decomposes work, selects iteration strategy, and decides **stop / escalate / accept**.

### Specialist(s) (Producers)
Generate **candidate artifacts** for assigned work packets under constraints; optimize for *constructive synthesis*, not for final correctness.

### Verifier (Auditor)
Evaluates candidates against **explicit acceptance criteria**, issuing an actionable **verification report** (pass/fail + failure reasons + repair targets).

---

## 2) Canonical Shared State (the “single source of truth”)
A stable, versioned record that prevents forgetting and goalpost drift:

- **Task Spec**
  - Objective (one sentence)
  - Constraints (must/must-not)
  - Acceptance Criteria (testable checklist with **criterion IDs**, includes **version number** for change tracking)
  - Risk/priority notes (what errors are costly)

- **Plan / Work Packets**
  - Packet ID, local objective, required inputs/outputs
  - **Criteria coverage**: list of **criterion IDs** this packet is responsible for (and any declared sub-criteria as decompositions of those IDs)
  - Dependencies (if any)

- **Criteria Coverage Map (non-negotiable)**
  - For each **criterion ID**, record one of:
    - **Owned-by packets**: [packet IDs...], or
    - **Integration-level**: verified only in Finalize, or
    - **Waived**: allowed-by policy + recorded decision
  - Coverage status must be explicit; uncovered criteria are invalid state.

- **Candidates**
  - Candidate ID → packet ID
  - Assumptions / uncertainty notes
  - Provenance (which Specialist, which iteration)

- **Verification Reports**
  - Report ID → candidate ID
  - Outcome: PASS / FAIL / PARTIAL / UNKNOWN
  - Failure taxonomy labels
  - Minimal counterexample / contradiction (when applicable)
  - Repair targets (what must change to pass)

- **Decisions Log**
  - Iteration decisions with rationale (why repair vs re-plan vs escalate)
  - Criteria change rationales (what changed, why—canonical version lives in Task Spec)

- **Delta Summary**
  - What changed this iteration
  - Remaining unmet/UNKNOWN criteria by ID
  - Active candidate IDs (candidates selected by Manager for current iteration)

- **Archive**
  - Older candidates, reports, evidence artifacts, and decision details retained by ID
  - Reference-only; not part of Working Set unless explicitly promoted

---

## 2.1) Role-Based State Views and Write Authority (non-negotiable)
The system maintains a **single canonical shared state**, but each role operates on a **constrained view** of that state to preserve **Verifier independence** and prevent **judge-shopping**.

### Write authority (who may mutate what)
- **Manager** may write: **Task Spec** (including criteria version updates), **Plan / Work Packets**, **Criteria Coverage Map**, **Decisions Log** (including waivers and criteria change rationales), **Delta Summary**, **Archive**.
- **Specialists** may write: **Candidates** (including assumptions/uncertainty notes and attached evidence artifacts).
- **Verifier** may write: **Verification Reports** only.

### Read views (who may see what)
- **Manager view**: may read all sections of shared state.
- **Specialist view**: may read **Task Spec**, assigned **Work Packets**, relevant **Criteria Coverage Map entries** (for owned criteria), and **Verification Reports** relevant to their candidates/packets (but may not read or modify criteria change rationales as “instructions”).
- **Verifier (Auditor) view**: may read **only** the inputs listed in §4.1. Any information outside §4.1 is **out-of-scope** and must not influence outcomes.

### Communication constraint (prevents boundary leakage)
If the Manager wants the Verifier to consider something, it must appear **either** in the **Task Spec / criteria version** **or** as an **explicit evidence artifact attached to the candidate**—never via the Decisions Log or side-channel rationale.

---

## 2.2) Criteria Identity and Decomposition Binding (non-negotiable)
To prevent “convergent wrongness” and packet-level spec drift:

- Acceptance Criteria are first-class items with stable **criterion IDs** (e.g., C1, C2, …).
- Work packets **must not** define independent “local criteria” that are not traceable to criterion IDs.
- Every criterion ID must be explicitly accounted for in the **Criteria Coverage Map** as:
  - owned by ≥1 packet, **or**
  - integration-level (verified in Finalize), **or**
  - waived per policy (Manager-only, recorded).

---

## 2.3) State Compaction and Context Budget (non-negotiable)
To prevent iteration from degrading due to unbounded state growth, the canonical state is partitioned into:

### Working Set (the only state roles operate on by default)
A bounded, iteration-stable slice containing only what is required to make the *next* decision well:
- Current **Task Spec** (current criteria version)
- Current **Plan / Work Packets** and **Criteria Coverage Map**
- The active candidates listed in **Delta Summary** (see §2)
- The **latest relevant verification report(s)** for those active candidates
- The current **Delta Summary** (see §2)

### Archive (reference-only history)
See **Archive** definition in §2. Non-working-set state is retained by ID but treated as non-existent for routine reasoning unless promoted back into the Working Set by the Manager.

**Invariant:** Each iteration ends with a Working Set that fits within the agreed context budget; anything outside the Working Set is treated as non-existent for routine reasoning unless promoted.

---

## 3) Lifecycle (numbered control loop)

1. **Frame**
   - Manager sets Task Spec + budgets + stop conditions.

2. **Decompose**
   - Manager defines work packets with interfaces and **assigns criterion IDs to packet ownership**.
   - Manager declares any **integration-level** criterion IDs in the Criteria Coverage Map.

3. **Produce**
   - Specialists generate candidates per packet (optionally in parallel).

4. **Verify**
   - Verifier evaluates each candidate against criteria and issues a report.

5. **Decide**
   - Manager chooses next action based on report(s):
     - targeted repair, re-plan, parallel regeneration, escalation, or accept-with-waiver.

6. **Compact**
   - Manager updates the **Delta Summary** and selects the **Working Set** for the next loop.
   - Any non-working-set history is retained only in the **Archive** by reference.

7. **Iterate**
   - Apply the decision and repeat until pass or stop conditions trigger.
   - On stop condition (budget exhausted, escalation threshold, etc.) → proceed to **Finalize**.

8. **Finalize**
   - Verifier evaluates any **integration-level** criterion IDs and issues the final verification report(s) with explicit PASS/FAIL/UNKNOWN coverage.
   - Manager outputs the best candidate(s) + the latest verifier report(s) + decision rationale.
   - If no candidate passes: output the best non-passing candidate with **exit status: BUDGET_EXHAUSTED**, attach the latest verification report, and document unmet criteria.

---

## 4) Verification Contract (what the Verifier must output)
A verification report must be **diagnostic**, not stylistic.

### Required elements
- **Outcome**: PASS / FAIL / PARTIAL / UNKNOWN  
  - **UNKNOWN** is mandatory when criteria cannot be verified from the provided spec/evidence (no guessing).
- **Criteria coverage**: which criteria passed/failed/unknown (**by criterion ID**)
- **Failure taxonomy**: label each failure (see below)
- **Repair targets**: concrete, criterion-linked change requirements (what must be true/added/removed), not solution steps
- **Confidence + severity**: how sure, how costly if wrong
- **Verifier scope declaration**: confirm compliance with §4.1 inputs/prohibitions (auditor boundaries)

### Failure taxonomy (recommended)
1. Requirement coverage failure (missed criterion)
2. Constraint violation (did something disallowed)
3. Internal inconsistency (self-contradiction)
4. Unsupported claim (assertion without backing)
5. Ambiguity (cannot verify due to unclear spec)
6. Scope error (answered a different question)
7. Overconfidence (uncertainty not acknowledged)

---

## 4.1) Verifier Independence Boundaries (non-negotiable)
The Verifier must be provided an explicit **Auditor View** as defined in §2.1; any non-view state is treated as **non-existent** for judgment purposes.

The Verifier is an **auditor**, not a co-author. To preserve stable judgment across iterations:

### Inputs the Verifier may use
- The **Task Spec** (objective, constraints, acceptance criteria including their version number).
- The **candidate under review** (and its declared assumptions/uncertainty notes).
- Any **explicit evidence artifacts** attached to the candidate (e.g., citations, calculations, logs), treated as claims to evaluate.
- Prior **Verification Reports** for the same candidate or criterion, solely to detect inconsistency (not to justify outcomes).

### Inputs the Verifier must NOT use (to avoid drift and judge-shopping)
- The Manager’s **Decisions Log** (rationales, preferences, iteration strategy).
- Other candidates in the same iteration (unless the criteria explicitly require comparative evaluation).
- The Verifier’s own prior reports *as justification* for a new outcome (prior reports may be referenced only to detect inconsistency).

### Prohibitions (keep roles clean)
- The Verifier **must not**:
  - introduce or modify acceptance criteria,
  - reframe the objective or constraints,
  - propose concrete solution steps or authored content (no “rewrite it like this”); repair targets must remain diagnostic,
  - negotiate waivers (waivers are Manager-only decisions).

### Required anchoring behavior
- Every pass/fail decision must cite **criterion IDs** (or exact criterion text) and indicate the **evidence** used.
- If verification is impossible due to ambiguity or missing evidence, the Verifier must return **UNKNOWN** for the affected criteria and label the failure as **Ambiguity** or **Unsupported claim**, not guess.

---

## 5) Verify → Iterate Strategies (control policies)
The Manager selects a policy based on failure type and convergence behavior:

- **Targeted Repair (Specialist self-correct)**
  - Use when failures are local and report is actionable.
- **Re-plan (Manager changes decomposition/spec)**
  - Use when failures indicate wrong assumptions, missing criteria, or broken packet boundaries.
- **Verifier-guided repair** (enhanced diagnostics, not solution proposals)
  - Use when Specialists need more granular failure analysis; Verifier provides detailed criterion-level breakdowns, evidence gaps, and failure taxonomy labels (per §4) while remaining prohibited from proposing concrete fixes (per §4.1).
- **Parallel Regeneration**
  - Use to break correlated errors; the same verifier evaluates each candidate independently against the same criteria, and the Manager compares the reports.
- **Escalation / Modality shift**
  - Use when verifier is inconsistent or blind; seek independent judgment.

---

## 6) Stop Conditions and Budgets (non-negotiable)
Define before iteration starts:
- max iterations / time / cost budget,
- maximum tolerated uncertainty,
- “accept with waiver” rules (which criteria may be waived, who decides, and how it’s recorded),
- escalation thresholds (e.g., repeated same failure N times).

---

## 7) Failure Modes (and architectural guardrails)

### Hallucination loops (repeating the same wrong core)
**Cause:** non-actionable verification + correlated blind spots + retry bias.  
**Guardrails:**
- Require failure taxonomy + repair targets (no vague “try again”).
- Track repeated failures; trigger re-plan or parallel regeneration automatically (policy-level).
- Require explicit “delta” on repair: what changed and why it resolves the failure.

### Goalpost drift / spec rot
**Cause:** silent changes to acceptance criteria.  
**Guardrails:**
- Version criteria; log changes with rationale.
- Treat criteria changes as first-class state transitions.

### Reward hacking (passing the verifier, not the task)
**Cause:** verifier becomes style-based or predictable.  
**Guardrails:**
- Enforce criteria coverage reporting.
- Prefer checks that are hard to “format-match” (consistency, coverage, contradiction checks).

### Verifier inconsistency
**Cause:** shifting thresholds across iterations.  
**Guardrails:**
- Anchor verifier to a stable criteria set and thresholds.
- Record pass/fail justifications for auditability.

---

## 8) Definition of "Done" (architectural)
A result is "done" only when:
- the final candidate **passes** acceptance criteria (or waivers are explicitly recorded), **OR**
- the system exits with **BUDGET_EXHAUSTED** status (best non-passing candidate + unmet criteria documented),
- verification reports are attached and internally consistent,
- the decision log explains *why this is the selected output*.
