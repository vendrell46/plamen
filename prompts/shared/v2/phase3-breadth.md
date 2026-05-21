# Phase 3: Parallel Breadth Analysis

> **Loaded by**: The V2 driver's Phase 3 subprocess (breadth analysis).
> **Purpose**: Parallel spawn rule, post-spawn verification, overreach handling,
> output file conventions, and agent closeout. Self-contained methodology for the
> breadth analysis phase.

---

## Spawn Rule

Spawn breadth agents in bounded parallel batches.

- If 1-6 breadth agents are missing, spawn them in a SINGLE message as parallel Task calls.
- If 7+ breadth agents are missing, spawn a batch of at most 6 agents, wait for that batch, close completed agents, then spawn the next batch.
- On retry, count only missing or stub breadth outputs from `spawn_manifest.md`; do not include already substantial outputs in the batch size.
- Each agent operates on its own scope independently and writes to its exact
  `Expected Output` from `spawn_manifest.md`.

---

## Post-Spawn Verification

Completion is manifest-exact, not batch-exact. A returned batch does not mean
the phase is complete.

Before exit, run this loop:

1. Parse `spawn_manifest.md` and build `EXPECTED_OUTPUTS`:
   - Include only rows that represent spawned breadth agents.
   - Do not include skill, injectable, template, methodology, checklist,
     binding, `merged into ...`, `covered by ...`, or `no separate agent`
     rows. Those rows modify an agent prompt; they do not own standalone
     `analysis_*.md` files.
   - Use the explicit output filename if the manifest names one.
   - Otherwise derive `{SCRATCHPAD}/analysis_<focus_area>.md`.
2. Build `COMPLETE_OUTPUTS` from expected files that exist and are >=200 bytes.
3. Build `OPEN_OUTPUTS` from expected files that are missing or <200 bytes.
4. If `OPEN_OUTPUTS` is non-empty:
   - Spawn agents for only the first `OPEN_OUTPUTS` batch.
   - Every Task prompt MUST include: focus area, expected output filename,
     and `FIRST ACTION: write a one-line header to {SCRATCHPAD}/{expected_output}`.
   - Do not identify outputs by numeric agent id; `analysis_1.md` is invalid
     when the manifest expects `analysis_core_state.md`.
   - Use at most 6 parallel Task calls per batch.
   - Wait for that batch and close completed agents.
   - Return to step 2.
5. Exit only when `OPEN_OUTPUTS` is empty.

Do not stop because the current batch returned. Do not proceed with 7/12,
9/12, or any partial manifest completion. If any required file is missing,
re-spawn that exact agent before returning from Phase 3.

Update `spawn_manifest.md` with completion status for each agent only after
the corresponding output file exists and is >=200 bytes.

---

## Output File Conventions

Each breadth agent writes to a single file:
```
{SCRATCHPAD}/analysis_{focus_area}.md
```

Where `{focus_area}` is the lowercase, hyphenated or underscored version of the agent's focus area (e.g., `analysis_core_state.md`, `analysis_access_control.md`, `analysis_oracle.md`).
The manifest `Expected Output` column is authoritative. If it names a file,
the agent must write that exact filename.

Finding IDs use a per-agent prefix:
- Core state agent: `[CS-1]`, `[CS-2]`, ...
- Access control agent: `[AC-1]`, `[AC-2]`, ...
- Token flow agent: `[TF-1]`, `[TF-2]`, ...
- External dependency: `[EX-1]`, `[EX-2]`, ...
- (Other prefixes assigned per focus area)

---

## Output Discipline

Breadth agents write exactly one manifest-derived `analysis_<focus_area>.md`
file each. No other artifact family is a breadth output. The driver's
gate ONLY accepts manifest-derived `analysis_*.md` filenames; anything
else is invisible to the gate and discarded.

If a spawned agent emits a file outside the manifest, record the
violation in `{SCRATCHPAD}/violations.md`, close the offending agent,
and rely on the remaining valid `analysis_*` outputs.

---

## Agent Closeout

- Do NOT read analysis files after agents return — file content stays on disk for downstream consumers; reading it here only wastes your context budget.
- Close completed breadth agents before returning. Do not carry finished workers forward.

---

## Context Budget Protection

The orchestrator does NOT read agent output files. Agent outputs stay
on disk for downstream consumers. This protects the orchestrator's
context from saturation.

Per the WRITE-THEN-VERIFY protocol, each agent:
1. Writes output directly to `{SCRATCHPAD}/{expected_filename}` using the Write tool
2. Returns ONLY a one-line summary: `"DONE: {N} findings written to {filename}"`

The orchestrator verifies file existence and size (>=200 bytes) mechanically after each return.

---

## Mode-Specific Agent Counts

| Mode | Agent Count | Model |
|------|-------------|-------|
| Light | 3-4 | sonnet |
| Core | 5-9 | opus |
| Thorough | 5-9 | opus |

Light mode caps at 3-4 sonnet agents. Core/Thorough use 5-9 opus agents based on complexity determination from Phase 2 Step 2a.

---

## Scope Containment Directive

Every breadth agent prompt MUST end with:

```
SCOPE: Write ONLY to your assigned output file. Do NOT read or write other agents' output files. Return your findings and stop.
```

For the breadth orchestrator itself: always reuse existing substantial
manifest-derived breadth outputs and spawn only the missing or stub rows from
`spawn_manifest.md`. Re-run the completion loop until all expected outputs are
substantial. As soon as the completion loop has zero open outputs, return
immediately with a one-line summary. Producing additional files beyond
the manifest-derived breadth set is discarded by the driver and wastes
session tokens.

---

## One-Line Addition to Each Breadth Agent Prompt (compact)

When constructing each breadth subagent's Task() prompt, also include
this directive verbatim. It is MANDATORY, not optional — prior audits
showed ~10% compliance when it was phrased as a soft suggestion, so it is
now written as a hard obligation with a worked example:

> **MANDATORY — Obligation Receipts.** If `{SCRATCHPAD}/opengrep_findings.md`
> exists, your `analysis_<focus>.md` is INCOMPLETE until it ends with a
> `## Obligation Receipts — opengrep_findings.md` section. Open
> `opengrep_findings.md`, read every row, and for EVERY row whose `Location`
> falls in your assigned scope, emit one of the two equivalent forms:
>
> **(a) Strict line form (preferred, unambiguous):**
> `[OBLIG:opengrep_findings.md:<row#>] STATUS:R|D|C KEY:<rule>@<file:L> -> <finding_id|reason|next_phase>`
>
> **(b) Table form (also accepted by the gate):**
> ```
> | Row | Rule | Location | Addressed By | Notes |
> |-----|------|----------|--------------|-------|
> | 7 | reentrancy-eth | Vault.sol:212 | (none) | guarded by nonReentrant — false positive |
> | 12 | use-ownable2step | Owner.sol:14 | AC-4 | single-step ownership, raised in access_control |
> ```
> The table form requires a numeric first column (the opengrep row index).
> Status is inferred from the row contents: notes containing `style|gas|
> false positive|non-security|by design` → DISMISSED; notes containing
> `carry|defer|later phase|next phase` → CARRIED; any other non-empty
> Addressed-By cell (a finding ID like `AC-4`, `BLIND-A-1`, prose, etc.)
> → REPORTED. Rows where every non-first cell is empty / `N/A` / `-` are
> NOT counted as receipts.
>
> STATUS short codes in the line form: `R` (Reported — you raised a finding
> for it), `D` (Dismissed — give the concrete reason it is not a bug), or
> `C` (Carried — deferred to a named later phase). You MUST account for
> every in-scope row; a row you neither report, dismiss, nor carry is an
> unaccounted obligation. Skip rows outside your scope (another agent
> owns them).

The Python gate (`_check_opengrep_obligation_coverage`) parses receipts
in both forms — strict-line first (canonical), then section-bounded
table form under any `## ... Obligation Receipts ... opengrep ...`
heading. WARNING-only — the pipeline never halts on missing receipts —
but an analysis file with zero receipts when opengrep rows exist is a
documented quality failure.

---

## Orchestrator Termination Contract (HARD STOP)

<!-- BUILD-STRIP: raw contract tokens for standalone contract tests only: analysis_rescan_*.md analysis_percontract_*.md findings_inventory.md semantic_invariants.md _overflow/breadth/ -->

As soon as every expected `analysis_<focus>.md` from `spawn_manifest.md`
is present on disk with size >= 200 bytes, return immediately:

```
DONE: {N} breadth analyses complete: {comma-separated filenames}
```

Any output written by the orchestrator after that signal is discarded
by the driver and wastes session tokens. The orchestrator's job is
spawning subagents and verifying their outputs — not producing analyses
itself, not writing other artifact families, not exploring beyond the
manifest.

Do NOT write later-phase artifacts from this breadth subprocess:
rescan outputs, per-contract outputs, inventory outputs, or semantic
invariant outputs. If such output is needed, a later phase owns it.
Quarantined overflow from this phase is discarded for cost discipline.
