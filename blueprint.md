# blueprint.md — North Star Workflow: Solo Coding Agent + Read-only Scouts
(Consolidate-First • Verification-Gated • Versioned Context • Scope-Capped • Anti-Stuck)

## 0) Objective
Ship maintainable code changes with high confidence by enforcing:
- **Single editor** (one agent owns all code edits),
- **Evidence-backed context** (scouts gather facts; main agent consolidates),
- **Verification-gated progress** (every slice ends in PASS/FAIL),
- **Anti-stuck recovery** (structured escalation via verifier audit after repeated failures),
- **Versioned context snapshots** (immutable per iteration; reload latest only),
- **Scope-capped scouting** (context gathering cannot sprawl past declared scope).

---

## 1) Roles (hard boundaries)

### Main Agent (Coder / Controller)
The only role allowed to **plan, edit code, and assemble deliverables**; owns scope, iteration strategy, and stop/ship decisions.

### Scout Subagents (Read-only)
Gather **repo facts only** (paths, symbols, conventions, commands, entry points, tests) and return **evidence-backed findings**; no code edits, no implementation proposals.

### Verifier Subagent (Read-only, on-demand)
Performs **independent evaluation** against acceptance + verification signals; returns a PASS/FAIL report with concrete findings; never edits code.

---

## 2) Core invariants (non-negotiable)
1) **One writer:** only the Main Agent edits code/artifacts.
2) **Consolidate before planning:** no plan is made from raw scout output.
3) **Versioned truth:** never edit an old snapshot; write a new one.
4) **Reload-latest-only:** planning/editing uses only the latest snapshot.
5) **Evidence-only scouting:** scouts provide facts, not solutions.
6) **Scope cap:** scouting must stay within the declared scope unless scope is explicitly revised.
7) **Explicit PASS/FAIL gates:** each work slice ends with a gate decision.
8) **Anti-stuck state is latest-only:** the latest snapshot MUST carry (a) the current `Slice ID` and (b) the anti-stuck counters:
   - `Consecutive Iteration FAILs (this Slice ID)`
   - `Consecutive Exit FAILs (this Slice ID)`
   Anti-stuck triggers read only these latest-header fields (no text-diffing).
9) **Slice identity before work:** if starting a genuinely new slice (or if no snapshot exists yet), a new snapshot with the intended `Slice ID` MUST exist **before any scouting or implementation begins**.

---

## 3) Primary artifact: Versioned Context Snapshots (single source of truth)

### 3.1 Storage
- Snapshots: `agent/context/iter-####.md` (monotonic increasing)
- Convenience alias (optional but recommended): `agent/context.md` always reflects the latest snapshot.
- **Rule (Authoritative):** the latest snapshot is the only active context for planning/editing.

**“Latest” definition:** the snapshot with the highest iteration number `####`.

**State-transition rule:** PASS/FAIL outcomes, issue open/resolve, and scope changes are recorded **only by writing a new snapshot**. Prior snapshots are immutable forever.

### 3.2 Snapshot Header (MANDATORY)
Each `iter-####.md` begins with a tiny header:

- `Iteration: ####`
- `Parent snapshot: iter-####` (or `none`)
- `Slice ID: S-####` *(stable identifier for the slice; see rule below)*
- `Slice: <one sentence: smallest coherent change attempted this iteration>`
- `Scope cap: <one sentence: what is explicitly in-scope / out-of-scope for scouting>`
- `Gate (iteration): <fast/standard checks for this slice>`
- `Gate (exit): <full checks required before shipping>`
- `Last gate run: <iteration|exit|none>`
- `Last gate outcome: <PASS|FAIL|none>`
- `Consecutive Iteration FAILs (this Slice ID): <integer >= 0>`
- `Consecutive Exit FAILs (this Slice ID): <integer >= 0>`

**Lineage rule (acyclic):** `Parent snapshot`, if present, must refer to an **earlier** iteration number (`parent < current`). Never self-parent; never point forward.

**Slice ID rule (MANDATORY):**
- `Slice ID` is the **authoritative identity** of the current slice.
- `Slice ID` MUST remain **unchanged across iterations** while pursuing the same slice, even if the `Slice:` sentence is reworded for clarity.
- Starting a genuinely new slice MUST assign a **new `Slice ID`** in a **new snapshot** **before any scouting/implementation for that new slice proceeds**.
- Operationalization: this is satisfied by **Step 0.5 — Initialize Snapshot** in the workflow lifecycle.

**Anti-stuck counters rule (MANDATORY):**
- The anti-stuck counters are **authoritative** for escalation and are read from the **latest snapshot only**.
- They are updated **only** by writing a **new snapshot** after running a gate (iteration or exit).
- Update rules (for the gate that was just run):
  - Always set:
    - `Last gate run` to `iteration` or `exit`
    - `Last gate outcome` to `PASS` or `FAIL`
  - If gate outcome is **PASS**:
    - Set the corresponding counter to `0`:
      - iteration PASS → `Consecutive Iteration FAILs (this Slice ID): 0`
      - exit PASS → `Consecutive Exit FAILs (this Slice ID): 0`
  - If gate outcome is **FAIL**:
    - If `Slice ID` is **unchanged** from the parent snapshot → increment the corresponding counter by `+1`.
    - If `Slice ID` is **different** from the parent snapshot → set the corresponding counter to `1` (first failure on this new Slice ID).
- The counter for the *other* gate type is unchanged by this gate run (except at slice initialization; see Step 0.5).
- Anti-stuck does **not** use `Slice:` text comparisons; rewording `Slice:` never resets counters.

Purpose:
- prevents silent scope drift,
- makes lineage obvious,
- makes “what are we doing” and “how do we know” explicit.

### 3.3 Snapshot Structure (after header)

#### Authority boundary (MANDATORY)
The snapshot contains both **provenance** and **decision context**, but only one tier is authoritative:
- **Authoritative for planning/editing:** **Consolidated Context**
- **Non-authoritative (provenance only):** **Evidence (Scout Findings)**

Plans and code edits must be grounded only in **Consolidated Context** (not Evidence).

#### Promotion rule (MANDATORY)
If a fact is needed for planning/editing but appears only in **Evidence**, treat it as **unknown** until it is **promoted** into **Consolidated Context** in a **new snapshot**, with its supporting evidence/check recorded.

Structure:
1) **Evidence (Scout Findings) — NON-AUTHORITATIVE**
   - raw-ish scout notes (paths/symbols/commands/snippets)
   - explicit uncertainties / open questions
   - provenance for audits and verifier review

2) **Consolidated Context (Source of Truth) — AUTHORITATIVE**
   - distilled conventions, key files/symbols, entry points, test/build commands
   - constraints + acceptance criteria relevant to this work
   - no speculation

3) **Issues (State)**
   - **Open Issues:** unresolved failures/risks/unknowns (each with a single “next action”: fix / re-scout / re-plan)
   - **Resolved This Iteration:** items from prior Open Issues resolved by this iteration (with the evidence/check that closed it)

(Everything needed to proceed lives in this one snapshot, with the authority boundary above.)

---

## 4) Workflow lifecycle (default)

### Step 0 — Intake (Main Agent)
- Restate goal + constraints.
- Define acceptance criteria (“done”).
- Declare initial **scope cap** (what areas are allowed for scouting; what is excluded).
- Choose gates:
  - **Iteration gate** (fast/standard for the slice),
  - **Exit gate** (full confidence gate before shipping).
- Determine slice identity:
  - If continuing the current slice → keep the existing `Slice ID`.
  - If starting a new slice → mint a new `Slice ID` (to be recorded via Step 0.5).

### Step 0.5 — Initialize Snapshot (MANDATORY when starting a slice)
Write a NEW `agent/context/iter-####.md` **before any scouting or implementation begins** when either:
- there is no existing snapshot yet, OR
- a genuinely new slice is being started (new `Slice ID`).

Minimum requirements:
- header fully populated (`Slice ID`, `Slice`, `Scope cap`, gates),
- `Parent snapshot: none` if this is the first snapshot; otherwise point to the latest prior snapshot (parent < current),
- `Last gate run: none`,
- `Last gate outcome: none`,
- `Consecutive Iteration FAILs (this Slice ID): 0`,
- `Consecutive Exit FAILs (this Slice ID): 0`,
- `Consolidated Context` includes intake-level constraints + acceptance criteria + chosen gates (no repo facts yet unless already known and verified),
- `Evidence` may be empty.

### Step 1 — Scout Phase (read-only, scope-capped)
- Spawn scouts only to answer explicit unknowns within scope.
- Scouts return evidence bundles (paths + minimal snippets + factual notes).

**Stop-scouting rule:** stop when the scope cap’s “sufficient context” condition is met
(e.g., entry points identified + relevant tests located + build/test commands confirmed).

### Step 2 — Consolidation (MANDATORY)
- Write a NEW `agent/context/iter-####.md`:
  - header filled (Slice ID / Slice / Scope cap / Gates),
  - Evidence section includes scout findings,
  - Consolidated Context distills only verified facts + constraints,
  - Issues (State) captures current Open Issues (and any prior resolved items if applicable).

**Note:** Any on-demand Verifier audit output follows the same pipeline as scout output:
capture as **Evidence** first, then promote into **Consolidated Context** via a **new snapshot** before acting on it.

### Step 3 — Reload Latest (MANDATORY)
- Discard earlier snapshots from active reasoning.
- Proceed using only the latest snapshot.

### Step 4 — Plan (slice-level)
- Plan the **smallest coherent change** that satisfies the slice and is grounded in **Consolidated Context**.
- Explicitly tie the slice to the iteration gate.
- **If a required fact is not in Consolidated Context, do not plan on it:**
  - open an Issue, then **re-scout/verify** and **promote** the fact into Consolidated Context via a **new snapshot**.

### Step 5 — Edit
- Implement as small, reviewable diffs.
- Keep changes diagnosable (avoid mixing unrelated refactors).

### Step 6 — Verify (MANDATORY)
- Run the appropriate gate for where you are in the lifecycle:
  - **Iteration gate** during normal loop cycles.
  - **Exit gate** when preparing to ship (Step 7).
- After **any gate run (iteration or exit)**, write a **NEW snapshot** that records:
  - `Last gate run` and `Last gate outcome`,
  - the updated anti-stuck counter(s) per the header rule,
  - updated **Issues (State)**:
    - carry forward remaining Open Issues,
    - move any newly-resolved items into **Resolved This Iteration** (with the check/evidence that resolved it).
- **Never edit prior snapshots** to “close” issues.

### Step 7 — Deliver (Exit)
Exit only when:
- acceptance criteria are met, AND
- **exit gate** passes, AND
- the latest snapshot is written and reflects final reality.

If the **exit gate FAILs**:
- write a new snapshot capturing the exit-gate FAIL (per Step 6),
- follow the failure ladder (fix-forward / re-scout / re-plan),
- re-run exit gate when ready (each run recorded via a new snapshot).

Deliverables:
- patch/diff,
- latest context snapshot (and optional `agent/context.md` alias),
- short “change record” (what changed / why / how verified / known risks).

---

## 5) Failure handling (anti-stuck control logic)

### 5.1 Failure ladder (per failed gate)
1) **Fix-forward** (if failure is local and understood).
2) **Re-scout** (if failure suggests missing/incorrect repo facts), still scope-capped.
3) **Re-plan** (if approach is wrong or slice is poorly chosen).

### 5.2 Mandatory verifier-audit trigger (Required)
Track consecutive FAILs on the **same Slice ID** using the latest snapshot’s anti-stuck counters:
- After **3 consecutive iteration-gate FAILs** (**i.e., `Consecutive Iteration FAILs (this Slice ID) >= 3`**) → trigger an **on-demand Verifier audit (required)**.
- After **3 consecutive exit-gate FAILs** (**i.e., `Consecutive Exit FAILs (this Slice ID) >= 3`**) → trigger an **on-demand Verifier audit (required)**.
  - Then the Main Agent must write a **NEW snapshot** that:
    - records the Verifier report in **Evidence**, and
    - promotes any decision-critical conclusions into **Consolidated Context** (or records them as unknowns + evidence gaps in Issues).
  - **Reload latest** and choose the next step (**fix-forward / re-scout / re-plan**) grounded in the latest snapshot’s **Consolidated Context**.

(Verifier audits may be triggered earlier at the Main Agent’s discretion, especially when symptoms indicate drift or uncertainty.)

### 5.3 Scope revision rule
If progress requires expanding beyond scope cap:
- Scope must be explicitly revised in the next snapshot header before new scouting begins.
- Otherwise, treat out-of-scope exploration as a failure mode (stop and re-plan).

---

## 6) On-demand independent audit (Verifier Subagent)
Trigger an audit when:
- **Pre-exit** (recommended for high-impact changes), or
- after **3 consecutive FAILs** on the same **Slice ID** for either gate type (**required**), or
- when symptoms indicate drift (conflicting assumptions, broad refactors, unclear acceptance mapping).

Audit output:
- PASS/FAIL against acceptance criteria + exit gate intent,
- mismatch list (what’s unmet, tied to criteria/gates),
- **diagnosis** (likely cause categories + confidence + supporting evidence),
- **evidence gaps** (what facts/logs/tests are missing to resolve uncertainty),
- **risk flags** (where drift/scope/assumptions are breaking),
- **verification suggestions only** (how to validate/falsify hypotheses; *no code-change prescriptions*).

**Verifier constraint:** may not propose implementation steps or “what to change”; it may only report unmet conditions, diagnoses, evidence gaps, risks, and verification suggestions.

**Audit Consolidation Rule (MANDATORY):**
- Verifier output is **NON-AUTHORITATIVE** until captured in **Evidence** and (if needed for decisions)
  **promoted** into **Consolidated Context** via writing a **new snapshot**.
- The Main Agent may not choose the next step (fix-forward / re-scout / re-plan) based on a raw Verifier report.
  Next-step decisions must be justified from **Consolidated Context** in the **latest snapshot**.

---

## 7) Maintainability guardrails
- **Single-writer rule** is absolute.
- **Plans must cite Consolidated Context**, not raw evidence.
- **Small diffs** over “hero refactors.”
- **Snapshot discipline**: immutable history; all updates (PASS/FAIL, issue open/resolve, scope revision) happen only via a new snapshot.
- **Header honesty**: Slice ID / Slice / Scope / Gates must match the actual diff and checks run.
- **Authority boundary honesty**: Evidence is provenance only; any planning-critical fact must be promoted into Consolidated Context in a new snapshot.
- **Anti-stuck honesty**: `Slice:` text rewording never resets fail streaks; only an explicit new `Slice ID` represents a new slice.

