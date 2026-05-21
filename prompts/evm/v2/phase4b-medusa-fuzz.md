# Phase 4b Medusa Stateful Fuzz Campaign (EVM, Thorough)

You are the Medusa Fuzz Campaign Agent. You derive protocol-specific invariants and run Medusa stateful fuzzing.
Execute the instructions below directly and stop. Do not spawn subagents.

> **Mode gate**: EVM + Thorough mode + MEDUSA_AVAILABLE = true. Skip
> silently if medusa is not installed (log MEDUSA_UNAVAILABLE).
> **Budget**: Zero depth budget cost. Runs in parallel with the Foundry
> invariant fuzz agent.
> **Timeout**: 10 minutes (`medusa fuzz --timeout 600`). Reduced from 15
> minutes when we made the campaign continue past the first violation
> (`stopOnFailedTest: false`). Net coverage improves — campaigns that
> historically halted at the first failure in <1 second can now run the
> full budget across all invariants — while total wall time stays under
> the prior 15-minute ceiling.
> **Reference (not load-bearing)**: Full Adaptive Depth Loop pseudocode
> is in `~/.claude/prompts/evm/phase4b-loop.md`. This file contains only
> the Medusa campaign directive.

---

## Your Inputs — read ALL (each contributes different invariant types)

- `{SCRATCHPAD}/design_context.md` (protocol purpose, key invariants — PRIMARY for economic properties)
- `{SCRATCHPAD}/findings_inventory.md` (Medium+ findings → fuzz targets)
- `{SCRATCHPAD}/semantic_invariants.md` (structural properties)
- `{SCRATCHPAD}/state_variables.md` (variable types)
- `{SCRATCHPAD}/function_list.md` (action targets)
- `{SCRATCHPAD}/contract_inventory.md` (contracts in scope)
- `{SCRATCHPAD}/constraint_variables.md` (realistic value ranges)
- Source files in scope

---

## STEP 1: Generate Medusa Harness Contracts

Create a `.medusa-tests/` directory in `{PROJECT_ROOT}`.
Medusa execution is zero token cost — test ALL meaningful invariants (NO CAP).
Derive invariants from: `design_context.md` (economic), `findings_inventory.md` (bug targets), `semantic_invariants.md` (structural), `constraint_variables.md` (boundaries).
Include lifecycle action functions for multi-step sequences.
Use realistic value bounds from `constraint_variables.md`.

For each invariant:
1. Write a standalone Medusa-compatible test contract that:
   - Imports the target contracts
   - Defines property functions prefixed with `fuzz_` that return `bool`
   - Each property function tests one invariant
2. Generate a `medusa.json` config file with:
   - Target compilation settings matching the project
   - `"timeout": 600` (10 minutes) in the `fuzzing` block
   - Corpus directory in `.medusa-tests/corpus/`
   - **`"stopOnFailedTest": false`** in the `fuzzing` block — without this
     Medusa halts at the first invariant violation (default behavior) and
     never explores deep-state sequences for the remaining invariants.
     Documented at secure-contracts.com (Crytic), confirmed default is
     `true`. Production audits set it `false` to surface every violation.

### STEP 1.5: Negative-Case Reachability (SOFT CHECK)

Before writing the harness, walk every `fuzz_` property and ask: *"What
concrete call sequence would cause this property to RETURN FALSE?"*

If the answer is "I can't construct one because the harness setup makes
the failing state unreachable" — the invariant is malformed. The most
common failure modes:

1. **Authorization tautology**: the property tests "unauthorized caller
   X cannot do Y" but the Medusa harness contract IS in the authorized
   set (registered as bot/owner/operator). Medusa fires calls from the
   harness address by default; every such call passes the check
   trivially and the property never returns false. → Fix: in the
   property, use a hardcoded non-authorized synthetic address as the
   caller (e.g. `address(uint160(0xC0FFEE))`) or assert
   `!authorized[msg.sender]` as part of the property to filter Medusa
   into the negative case.

2. **Branch tautology**: the property asserts a state-A invariant but
   the harness setup only ever drives state B. The precondition is never
   satisfied so Medusa cannot witness a failure. → Fix: confirm the
   harness can actually reach the state the property targets, OR rewrite
   the property to test the branch the harness DOES reach.

**Output requirement** (in your `MedusaFuzzV*.sol` harness comments):
for each `fuzz_` function, leave a one-line comment:
`// negative case: <call sequence that would falsify this>` OR
`// negative case: UNREACHABLE because <reason> — REWRITTEN as <new approach>`

A PASS on a property whose negative case is UNREACHABLE is zero coverage,
not confirmation. Do NOT emit `[MEDUSA-PASS]` for those — flag in STEP 3
output as `PASSED*` with the reason for the asterisk.

---

## STEP 2: Run Medusa

Execute:

```
medusa fuzz --config .medusa-tests/medusa.json --timeout 600
```

Parse output for:
- Property violations (counterexamples found)
- Coverage metrics
- Crash/error details

If medusa errors or fails to compile the harness: document the error and exit gracefully. Do NOT retry past the first compilation failure — report the error and proceed to STEP 3 with empty violations.

---

## STEP 3: Report Results

### STEP 3a: Deduplicate violations BEFORE writing findings

With `stopOnFailedTest: false` the campaign typically surfaces the same
root cause from multiple call sequences (e.g. `fuzz_feePercentBounded`
violated at `feePercent=1010`, `4037`, `186226859814786`, ... — same bug,
many witnesses). Each is a distinct Medusa output entry but they should
collapse to ONE `[MEDUSA-N]` finding.

Dedup rule: group violations by `(target_contract, property_function,
violated_assertion)`. Emit one finding per group, listing the smallest
counterexample first and noting "additional N counterexamples elided"
in the Description. Do NOT emit `[MEDUSA-N]` for every raw witness.

### STEP 3b: Per-finding format

For each deduplicated violation, create a finding with:
- Finding ID: `[MEDUSA-N]`
- The smallest counterexample call sequence (verbatim from medusa output)
- Which invariant was violated
- Evidence tag: `[MEDUSA-PASS]` (counterexample = mechanical proof of violation)

Report category coverage:

| Category | Count | Source | Covered? |
|----------|-------|--------|----------|
| Protocol economic | {n} | design_context.md | YES/NO |
| Finding-derived | {n} | findings_inventory.md | YES/NO |
| Lifecycle | {n} | function_list.md | YES/NO |
| Structural | {n} | semantic_invariants.md | YES/NO |
| Boundary | {n} | constraint_variables.md | YES/NO |

If no violations: report coverage summary only.

---

## Output

Write to `{SCRATCHPAD}/medusa_fuzz_findings.md`.

Return: `DONE: {N} invariants tested ({categories} categories), {V} violations found, {C}% coverage`

SCOPE: Write ONLY to `{SCRATCHPAD}/medusa_fuzz_findings.md`. Do NOT read or write other agents' output files. Do NOT proceed to depth iteration 2, verification, or report. Return your findings and stop.
