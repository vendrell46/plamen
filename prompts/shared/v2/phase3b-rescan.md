# Phase 3b: Additional Breadth Pass (Thorough Mode Only)

This phase runs after first-pass breadth and before inventory. It owns only
additional analysis artifacts produced before inventory synthesis.

> **Loaded by**: The V2 driver's `rescan` subprocess.
> **Mode gate**: Thorough mode ONLY. Skip in Light and Core mode.
> **Purpose**: Counter attention saturation after first-pass breadth by running
> a smaller, independent breadth pass over under-explored surfaces.

---

## V2 Phase Position

This phase runs after first-pass breadth analysis. Its job is to add
under-explored breadth coverage by writing additional `analysis_*.md`
files. This subprocess does NOT merge findings or perform finding-level
synthesis.

---

## Inputs

Read first-pass breadth outputs matching `{SCRATCHPAD}/analysis_*.md` and
the recon artifacts needed to assign under-explored surfaces. Treat existing
first-pass findings as an exclusion set:

- Do not report the same root cause.
- Do not report the same location with only a renamed title.
- Prefer vulnerability classes and files that are weakly represented in the
  first-pass breadth outputs.

On retry, ignore this phase's own prior outputs when building the first-pass
exclusion set; use them only to determine which additional outputs are already
substantial and can be skipped.

---

## Work Plan

Spawn 2-3 additional breadth agents in bounded parallel calls. Each agent gets
one broad non-overlapping or intentionally cross-checking scope, depending on
the gaps visible from first-pass breadth and recon artifacts.

Focus areas that usually reveal attention-saturation misses:

1. Cross-function state inconsistencies.
2. Asymmetric operations.
3. Parameter encoding mismatches between paired functions.
4. Economic assumptions violated under edge conditions.
5. Time-dependent state that goes stale under specific operation sequences.

In Thorough mode, a focused per-contract/cluster pass is mandatory. Keep it in
this same subprocess unless the phase graph launches a separate per-contract
producer. Write it under this phase's owned additional-analysis output family.

---

## Subagent Output Contract (MANDATORY -- include in every Task prompt)

Each Task subagent you spawn for this phase must obey the following contract.
The coordinator MUST include these rules verbatim in the spawned subagent's
prompt.

1. **Reservation write is OK as crash insurance.** Writing a short header
   (e.g. `# Per-Contract Agent N: <cluster>`) at the start of your work to
   reserve the output file is allowed and encouraged -- it lets the driver
   recover partial work if your subprocess is interrupted.

2. **The reservation is NOT your output.** Your final output is the same file
   overwritten with your full findings. A subagent that returns analytical
   content as text while leaving the file at its reservation header has
   produced an empty output as far as the rest of the pipeline is concerned.

3. **End-of-task write assertion (HARD GATE).** Immediately before returning,
   you MUST:
   - Read your assigned output file from disk.
   - If its size is below 1 KB OR it contains only the reservation header,
     overwrite it now with your full findings (or with a substantive
     explanation of why no findings apply, per the scope-review fallback in
     the Output Contract above).
   - Only after the file contains your real content may you return.

4. **Return message is status only.** Your return value to the coordinator is
   a one-line status (e.g. `DONE: 3 findings in <cluster>` or
   `DONE: scope-review only -- no clustered findings`). Do NOT put findings,
   analysis, or any other substantive content in the return value -- that is
   the file's job. Substantive content in the return message is a contract
   violation: the coordinator discards it and the pipeline cannot consume it.

5. **A stub return is a violation.** If you find yourself wanting to return
   findings as text because "the file is just a reservation," stop -- that is
   the failure mode this contract exists to prevent. Overwrite the file
   first, then return the one-line status.

---

## Output Contract

Write only this phase's additional analysis files:

- `analysis_rescan_*.md`
- at least one `analysis_percontract_*.md`

Each additional agent writes exactly one output file. If no meaningful
per-contract cluster exists, still write
`analysis_percontract_scope_review.md` with a substantive explanation of why
clustered per-contract analysis is not applicable and what files were checked.

---

## Orchestrator Termination Contract (HARD STOP)

<!-- BUILD-STRIP: raw contract tokens for standalone contract tests only: findings_inventory.md depth_*.md -->

As soon as the required `analysis_rescan_*.md` files (one per spawned
rescan agent) AND at least one `analysis_percontract_*.md` are on disk
with size >= 200 bytes, return immediately:

```
DONE: rescan {N} files, per-contract {M} files written
```

Any output written by the orchestrator beyond this contract is
discarded by the driver and wastes session tokens. Do not produce
files outside the two artifact families above. Do not write inventory,
verification, report, depth, or `semantic_invariants.md` artifacts from
this phase; later subprocesses own those outputs.
