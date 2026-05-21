# Phase 4c: Chain Analysis - Split Agent Architecture

> **Usage**: Orchestrator reads this file and spawns 2 sequential chain agents.
> Replace placeholders `{SCRATCHPAD}`, `{list...}`, etc. with actual values.
> Split into Agent 1 (enabler + grouping) and Agent 2 (chain matching + composition coverage).
> Each agent stays under security-analyzer context limits.

---

## Pre-Step: Chain Summary Extraction (Orchestrator Inline)

Before spawning agents, the orchestrator extracts Chain Summary sections into a compact file.
This prevents agents from reading 5000+ lines of full depth/scanner output.

```
For each file in [depth_*_findings.md, blind_spot_*_findings.md, validation_sweep_findings.md,
                   niche_*_findings.md, design_stress_findings.md, sibling_propagation_findings.md]:
  Extract ONLY the '## Chain Summary' table section
  Append to {SCRATCHPAD}/chain_summaries_compact.md with a header per source file
```

This produces ~200-400 lines instead of 5000+.

`chain_summaries_compact.md` is orchestrator-owned. Chain agents must read it,
not generate it. If it is missing, that is a pre-step failure by the
orchestrator, not a task for Chain Agent 1 or 2.

**Artifact discipline**: `chain_summaries_compact.md`, `enabler_results.md`,
and `composition_coverage.md` are REQUIRED standalone artifacts. If you
also include their contents inline elsewhere, still write the dedicated files.

---

## Agent 1: Enabler Enumeration + Grouping (security-analyzer)

```
Task(subagent_type="security-analyzer", prompt="
You are Chain Agent 1: Enabler Enumeration and Grouping.

## Your Inputs
Read:
- {SCRATCHPAD}/findings_inventory.md (breadth summary + Chain Summary table)
- {SCRATCHPAD}/chain_summaries_compact.md (extracted chain summaries from depth/scanner agents)
- {SCRATCHPAD}/confidence_scores.md (for prioritization)
- {SCRATCHPAD}/attack_surface.md (for enabler enumeration)
- {SCRATCHPAD}/depth_*_findings.md (for STEP 0-pre: scan for [CROSS-DOMAIN-DEP] tags)

For specific findings referenced in enabler enumeration, read the relevant source files directly.

## Mandatory First Action

Before semantic grouping, physically create all three handoff files on disk:

- `{SCRATCHPAD}/hypotheses.md`
- `{SCRATCHPAD}/finding_mapping.md`
- `{SCRATCHPAD}/enabler_results.md`

If the files already contain a driver-written `MECHANICAL_BASELINE`, you may
overwrite them as you improve the analysis. Do not merely return a summary
saying the files were written. Only return `DONE` after all three files exist
on disk and contain the final content for this phase.

## PHASE 0: ENABLER ENUMERATION (Rule 12)

Before grouping, exhaustively enumerate all paths to each dangerous precondition state.

### STEP 0-pre: Cross-Domain Dependency Scan

Search ALL depth agent output files (`depth_*_findings.md`) for `[CROSS-DOMAIN-DEP: {domain}]` tags. These are assumptions a depth agent identified as outside its own domain — potential compound exploit paths invisible to single-domain analysis. For each tag found:
1. Check if ANY finding in the referenced domain addresses that assumption
2. If NO finding covers it → add to the enabler enumeration as a candidate dangerous state
3. If a finding DOES cover it → check whether the finding's postcondition could break the tagged assumption

### STEP 0a: Extract Dangerous States

From all CONFIRMED, PARTIAL, and CONTESTED findings, extract each dangerous precondition state:

| Finding ID | Dangerous State S | Current Known Path(s) to S | Actor Category of Known Path |

### STEP 0b: Enumerate Missing Paths (Rule 12)

For EACH dangerous state S, fill the 5-actor-category table:

| # | Actor Category | Path to State S? | Reachable? | Existing Finding? | If Missing: New Finding |
|---|----------------|-------------------|------------|-------------------|------------------------|
| 1 | External attacker (permissionless) | {path or 'No path'} | YES/NO | {ID or NONE} | {[EN-N] or N/A} |
| 2 | Semi-trusted role (within permissions) | {path or 'No path'} | YES/NO | {ID or NONE} | {[EN-N] or N/A} |
| 3 | Natural operation (normal protocol flow) | {path or 'No path'} | YES/NO | {ID or NONE} | {[EN-N] or N/A} |
| 4 | External event (slash, pause, governance) | {path or 'No path'} | YES/NO | {ID or NONE} | {[EN-N] or N/A} |
| 5 | User action sequence (normal usage) | {path or 'No path'} | YES/NO | {ID or NONE} | {[EN-N] or N/A} |

**Rules**:
- 'No path' requires a brief explanation of WHY this actor category cannot reach state S
- If reachable but no existing finding → create [EN-N] finding
- New findings inherit the IMPACT severity of the original finding
- New findings may have DIFFERENT likelihood

### STEP 0c: Cross-State Interactions

Check if reaching state S1 (from Finding A) also reaches state S2 (from Finding B):
- If YES → document the combined attack path

## Hypothesis ID Taxonomy (SC)

When you group findings into hypotheses, use **one** of the canonical SC
hypothesis ID prefixes below. The driver's parity gate, the verification
queue, and the report-index parser all recognize exactly this set — emitting
a prefix outside this list silently drops every constituent INV-* from the
audit-completeness accounting.

| Prefix | Meaning | When to use |
|---|---|---|
| `HC-NN` | Hypothesis, Critical severity | Grouped hypothesis whose worst constituent is Critical |
| `HH-NN` | Hypothesis, High severity | Grouped hypothesis whose worst constituent is High |
| `HM-NN` | Hypothesis, Medium severity | Grouped hypothesis whose worst constituent is Medium |
| `HL-NN` | Hypothesis, Low severity | Grouped hypothesis whose worst constituent is Low |
| `HI-NN` | Hypothesis, Informational | Grouped hypothesis whose worst constituent is Informational |
| `GRP-NN` | Severity-agnostic group | Multi-finding group that genuinely spans tiers and uses an explicit anti-absorption override |
| `CH-NN` | Chain hypothesis | Agent 2's chain hypotheses (combined attack from blocked + enabler findings) |
| `H-NN` | Generic hypothesis (legacy) | Backward-compatible fallback — prefer the severity-bucketed forms above when possible |

Numbering is per-prefix and sequential from `01` (zero-padded to 2 digits is
fine, single-digit is fine). All constituents of a hypothesis (e.g. `HC-02`
absorbs `INV-001, INV-002`) must be recorded in `finding_mapping.md` and
shown under the hypothesis section in `hypotheses.md`, so the parity gate
can expand the grouped row back to its INV-* constituents.

## PHASE 1: GROUPING AND DEDUP

### Grouping Steps

1. MERGE depth findings, enabler findings ([EN-N]), and breadth findings
2. CROSS-CORRELATE findings across agents - deduplicate same root cause
3. GROUP by root cause into hypotheses
4. RECOVER dismissed findings if contradicted by depth agents
5. ANALYZE compound exploits
6. VERIFY coverage - every finding has a status

### GROUPING RULES (MANDATORY)
1. **Max 5 findings per hypothesis**. If grouping would exceed 5, split by exploit path.
2. **No catch-all hypotheses**. Every finding must map to a hypothesis with a specific root cause. 'Miscellaneous' groupings are PROHIBITED.
3. **Group by exploit path, not component**. Two findings affecting the same component but using different exploit mechanisms → separate hypotheses.
4. **Orphan findings** each become their own single-finding hypothesis.
5. **LOW_CONFIDENCE orphans**: each becomes a standalone hypothesis at its original severity.
6. **Anti-absorption (MECHANICALLY ENFORCED)**: Before grouping two findings, apply this check:
   (a) Same fix required for both (if fixes differ → separate hypotheses)
   (b) Grouping does not obscure a severity difference > 1 tier
   (c) Reader can understand BOTH attack paths from a single description
   (d) **Fix comparison test**: Write a 1-line fix for each. If fixes modify DIFFERENT functions → separate hypotheses.

   This rule is NOT advisory — the driver runs a mechanical validator on
   your output (`_validate_chain_anti_absorption`) that checks:
   - Constituents span distinct `(file, function)` pairs → SPLIT
   - Constituent severity tier span > 1 (e.g., a Medium and a High
     cannot share a Medium hypothesis) → SPLIT
   - Pairwise root-cause text Jaccard similarity < 0.30 → SPLIT

   **Jaccard worked example (so you can self-check before emitting):**
   The metric is `|A ∩ B| / |A ∪ B|` on lowercased word tokens of the two
   root-cause descriptions. A pair below 0.30 → SPLIT into separate
   hypotheses; ≥ 0.30 → grouping is allowed.

   - **OK to group (Jaccard ≈ 0.50)**:
     A = "missing zero address check in setFeeRecipient admin setter"
     B = "missing zero address check in setVault admin setter"
     A tokens = `{missing, zero, address, check, in, setfeerecipient, admin, setter}` (8)
     B tokens = `{missing, zero, address, check, in, setvault, admin, setter}` (8)
     Intersection = `{missing, zero, address, check, in, admin, setter}` (7)
     Union = 9. Jaccard = 7/9 ≈ 0.78 → same root cause + same fix → group.

   - **MUST SPLIT (Jaccard ≈ 0.14)**:
     A = "reentrancy via external call before state write in withdraw"
     B = "integer overflow on fee calculation in setFee"
     Intersection ≈ `{in}` (1)
     Union ≈ 14. Jaccard ≈ 1/14 ≈ 0.07 → distinct mechanisms / distinct
     fixes → separate hypotheses, even if they share severity.

   Violations trigger a retry with a hint listing the offending groups.
   If you believe a violation is intentional (two findings are TRULY
   redundant detections of the same single bug), add inside the
   hypothesis section body:

       Anti-absorption override: <one-sentence reason>

   Without an explicit override, mechanical splits are mandatory.

7. **Severity inheritance**: When grouping findings of different severities, the hypothesis inherits the HIGHEST severity from its constituent findings.

### MANDATORY FULL-EVIDENCE RE-READ (multi-constituent groups)

Before grouping **≥3 candidate findings into one hypothesis**, you MUST:

1. Locate each candidate's full finding text in its source file
   (`depth_*_findings.md`, `niche_*_findings.md`, `blind_spot_*_findings.md`,
   `analysis_*.md`, or `validation_sweep_findings.md`). The
   `chain_summaries_compact.md` row tells you the source filename — open it
   and find the finding by its ID.
2. Read each candidate's full **Description**, **Impact**, **Evidence**,
   **Root Cause** sections — not just the compact-summary one-liner. The
   compact summary preserves *what* but loses *how*, and you need the *how*
   to apply the anti-absorption fix-comparison test.
3. Apply rule 6(a)–(d) using the full text. If any two constituents have:
   distinct fix locations (different file:function), severity tier
   difference > 1, OR root causes describing different mechanisms — SPLIT.

ANTI-PATTERN EXAMPLE — do NOT merge findings that share a file but have
distinct fixes:

> Finding A: attacker-controlled `len` parameter → out-of-bounds read.
>   Fix: add `require(2 + len*33 <= input.length)` validation.
> Finding B: assembly `mload(ptr)` reads 32 bytes for a 1-byte boolean
>   field, corrupting it with adjacent data.
>   Fix: replace `mload(ptr)` with `byte(0, mload(ptr))`.
> Finding C: pointer-table memory layout where Solidity ABI expects
>   inline struct layout.
>   Fix: rewrite the assembly block to write structs inline.
>
> **Correct grouping: 3 separate hypotheses** (each requires editing a
> different code location with a different fix). Same source file is
> NOT a valid merge criterion. Rule 6(d): fix-comparison test fails.

The skipping cost of full re-read for ≥3-constituent candidates is small
(typically <50 KB extra context per group). The cost of an over-merge is
losing all constituents when the verifier picks the weakest one's PoC.

**Confidence-aware grouping**: Group LOW_CONFIDENCE findings with CONFIDENT findings of the same root cause where possible. Flag CONTESTED findings for verification priority.

## Output

Write:
- {SCRATCHPAD}/hypotheses.md - hypothesis table (grouped findings)
- {SCRATCHPAD}/finding_mapping.md - finding → hypothesis mapping
- {SCRATCHPAD}/enabler_results.md - enabler enumeration results (dangerous states, 5-actor tables, cross-state interactions)

Do NOT fold `enabler_results.md` into `hypotheses.md` as the only copy. Both
files must exist separately.

Return: 'DONE: {N} hypotheses, {E} enabler paths enumerated'

Only return `DONE` after `hypotheses.md`, `finding_mapping.md`, and
`enabler_results.md` exist on disk.
")
```

---

## Agent 2: Chain Matching + Composition Coverage (security-analyzer)

> **Spawned AFTER Agent 1 completes.** Reads Agent 1's output.

```
Task(subagent_type="security-analyzer", prompt="
You are Chain Agent 2: Chain Matching and Composition Coverage.

## Your Inputs
Read:
- {SCRATCHPAD}/hypotheses.md (grouped hypotheses from Agent 1)
- {SCRATCHPAD}/finding_mapping.md (finding → hypothesis mapping from Agent 1)
- {SCRATCHPAD}/enabler_results.md (enabler enumeration + cross-state interactions from Agent 1)
- {SCRATCHPAD}/variable_finding_map.md (variable→finding cross-reference for variable-level matching - if missing, fall back to grep-based variable name matching in findings_inventory.md)
- {SCRATCHPAD}/chain_candidate_pairs.md (pre-filtered pairs with shared state/type — if present, evaluate ONLY these pairs)
- {SCRATCHPAD}/findings_inventory.md (for full finding details when needed)

For specific chain candidates, read the relevant source files directly.

## PHASE 2: CHAIN ANALYSIS - Match Postconditions to Preconditions

### Step 2.0: Load Pre-Filtered Pairs (if available)

Read {SCRATCHPAD}/chain_candidate_pairs.md. If present:
- Evaluate ONLY the pairs listed in the STATE Pairs and TYPE Pairs tables
- For each pair: read both findings' full details, verify the mechanical match is semantically valid
- Create CHAIN HYPOTHESIS for valid matches
- Mark each evaluated pair as EXPLORED in composition_coverage.md
- All pairs NOT in chain_candidate_pairs.md are EXCLUDED (no shared state or type) — mark them as a single summary row "EXCLUDED: {N} pairs with no shared state/type" in composition_coverage.md. Do NOT spend time evaluating them.

If chain_candidate_pairs.md is MISSING, fall back to the original algorithm below.

### Step 2.1: Original Algorithm (fallback if no pre-filter)

For each PARTIAL or REFUTED finding:
1. Extract its missing precondition and type (STATE/ACCESS/TIMING/EXTERNAL/BALANCE)
2. **For STATE-type preconditions**: extract the specific state variable name(s). Use variable_finding_map.md to find ALL findings that write to the SAME variable - match on variable names, not just descriptions.
3. Search ALL CONFIRMED/PARTIAL findings for matching postconditions - across ALL severity tiers and vulnerability classes
4. If found: Create CHAIN HYPOTHESIS with combined attack sequence

### Chain Hypothesis Format

## Chain Hypothesis CH-{N}
### Blocked Finding (A)
- **ID**: [XX-N], **Title**: [Attack that was blocked]
- **Original Verdict**: REFUTED/PARTIAL, **Missing Precondition**: [What was missing], **Type**: [TYPE]
### Enabler Finding (B)
- **ID**: [YY-M], **Title**: [Finding that creates the precondition]
- **Original Verdict**: CONFIRMED/PARTIAL, **Postcondition Created**: [What it creates], **Type**: [TYPE]
### Chain Match
- **Match Strength**: STRONG / MODERATE / WEAK
- **Match Reasoning**: B creates the exact precondition A needs
### Combined Attack Sequence
1. [Step from B]: Execute enabler action
2. [Step from A]: Execute previously-blocked attack
3. [Impact]: Combined effect
### Severity Reassessment
Chain Severity Matrix:
| Original A | Original B | Chain Severity |
|------------|------------|----------------|
| REFUTED | Any | Re-evaluate A with B's postcondition |
| LOW | LOW | MEDIUM |
| LOW | MEDIUM+ | HIGH |
| MEDIUM | MEDIUM | HIGH |
| MEDIUM | HIGH | HIGH |
| HIGH | Any | HIGH or CRITICAL |
| CRITICAL | Any | CRITICAL |
Chain severity is NEVER lower than the higher of Finding A or Finding B.
Upgrade if: combined impact > $100k AND profitability > 2x → CRITICAL
Upgrade if: combined impact > $10k AND profitability > 2x → minimum HIGH

### Composition Coverage Map

After chain matching, write a coverage map of finding pairs you considered:

| Finding A | Finding B | Explored? | Result | Notes |
|-----------|-----------|-----------|--------|-------|

Rules: List pairs where at least one has a postcondition or missing precondition. Cross-class pairs (state + token, access + external) are HIGH PRIORITY.

## PHASE 3: RAG VALIDATION FOR CHAINS

For each chain hypothesis:
1. assess_hypothesis_strength(hypothesis='Chain: {B title} enables {A title}')
2. get_similar_findings(pattern='{combined attack description}')
3. If local results < 5: search_solodit_live(keywords='{chain pattern}', impact=['HIGH','MEDIUM'], quality_score=3, max_results=20)
4. If historical precedent found → upgrade chain severity

**RAG fallback**: If unified-vuln-db tools fail or return errors (missing deps, timeout, empty DB), skip RAG validation for chains. Use WebSearch as fallback: search `site:solodit.xyz {chain pattern}` for each chain hypothesis. If WebSearch also fails, proceed without historical validation — chain severity is determined by the postcondition-precondition match logic above, not by RAG. Do NOT retry failed MCP calls.

## Output

Update {SCRATCHPAD}/hypotheses.md - add chain hypotheses to the hypothesis table
Write:
- {SCRATCHPAD}/synthesis_full.md - full analysis (enabler + grouping + chain results)
- {SCRATCHPAD}/chain_hypotheses.md - chain summary with:
  1. Chain summary table: Chain ID | Finding A | Missing Precondition | Finding B | Postcondition Match | Chain Severity
  2. Detailed chain hypotheses
  3. Findings status update (which findings upgraded)
  4. Verification priority order
- {SCRATCHPAD}/composition_coverage.md - composition coverage map

Do NOT rely on `chain_hypotheses.md` to implicitly serve as composition
coverage. `composition_coverage.md` must be written as its own file.

Return: 'DONE: {M} chains identified, {K} severity upgrades, {U} unexplored pairs remaining, verification priority: [list]'
")
```

---

## Iterative Chain Composition (Orchestrator Logic)

After Agent 2 completes, the orchestrator checks for unexplored cross-class pairs:

```
ITERATIVE_CHAIN_COMPOSITION(SCRATCHPAD):
  // Agent 1 + Agent 2 run sequentially (above)

  // ═══ EARLY EXIT CHECK ═══
  // If Agent 2 reported 0 new chains AND 0 unexplored cross-class Medium+ pairs → skip iteration 2
  // Read Agent 2's return message for chain count and unexplored pair count
  // This prevents spawning a redundant iteration 2 agent when composition is already complete

  // Read composition coverage map
  coverage = read(SCRATCHPAD + "/composition_coverage.md")
  unexplored = [pair for pair in coverage if pair.explored == NO]

  cross_class_unexplored = [p for p in unexplored
                            if p.finding_a.class != p.finding_b.class
                            and max(p.finding_a.severity, p.finding_b.severity) >= MEDIUM]
  if len(cross_class_unexplored) == 0:
    goto DONE

  // Spawn targeted iteration 2 agent for unexplored pairs only
  spawn chain_iteration2_agent(SCRATCHPAD, cross_class_unexplored)
  await chain_iteration2_agent

  DONE:
    // Proceed to Phase 5 verification
```

### Iteration 2 Chain Agent Template

```
Task(subagent_type="security-analyzer", prompt="
You are the Chain Composition Agent - ITERATION 2 (targeted cross-class pass).

The first chain analysis identified {M} chains. {U} cross-class finding pairs were NOT explored.
Analyze ONLY these unexplored pairs for compound attack paths.

## Your Inputs
- {SCRATCHPAD}/composition_coverage.md (focus on NOT EXPLORED rows)
- {SCRATCHPAD}/chain_hypotheses.md (do NOT duplicate existing chains)
- {SCRATCHPAD}/findings_inventory.md (full finding details)

## Unexplored Pairs
{PASTE UNEXPLORED CROSS-CLASS PAIRS - max 15}

## Your Task
For EACH pair:
1. Read both findings' full details
2. Check: does A's postcondition enable B's precondition? And vice versa?
3. If YES: create CHAIN HYPOTHESIS (use Chain Hypothesis Format from chain_hypotheses.md)
4. Validate via RAG

## Output
Write to {SCRATCHPAD}/chain_iteration2.md
Append new chains to {SCRATCHPAD}/chain_hypotheses.md
Update {SCRATCHPAD}/composition_coverage.md

Return: 'DONE: {N} new chains from {U} unexplored pairs'
")
```

| Condition | Effect |
|-----------|--------|
| 0 unexplored cross-class Medium+ pairs | Skip iteration 2 |
| Hard cap | 2 iterations maximum |

---

### Chain-Specific PoC Requirements

Chain hypotheses receive PRIORITY in verification:

```solidity
function test_CH1_full_chain() public {
    // === STEP 1: Enabler (Finding B) - create the postcondition ===
    // === VERIFY POSTCONDITION - assert precondition for Finding A is now met ===
    // === STEP 2: Blocked Finding (Finding A) - execute previously-blocked attack ===
    // === VERIFY CHAIN IMPACT - assert combined impact > either alone ===
}
```

---

## Iterative Depth Pass

> The separate Phase 4d iterative depth pass is handled by the Adaptive Depth Loop in Phase 4b (iterations 2-3).
> However, if chain analysis discovers NEW chains that upgrade severity AND the upgraded findings were not covered by the adaptive loop, the orchestrator MAY spawn one additional targeted depth pass:

**Trigger**: Chain analyzer returned K > 0 severity upgrades where the upgraded finding was previously CONFIDENT (≥ 0.7) and thus was NOT re-analyzed in iterations 2-3.

```
Task(subagent_type="depth-{relevant-type}", prompt="
## Iterative Depth Pass (Post-Chain)

Chain analysis upgraded these findings:
{list of upgraded findings from chain_hypotheses.md}

For EACH upgraded finding:
1. Re-analyze with the CHAIN CONTEXT (the enabler finding is now known)
2. Trace the COMPLETE attack sequence (enabler → blocked finding → impact)
3. Validate the chain with RAG: search_solodit_live(keywords='<chain pattern>')
4. Compute impact with REAL constants for the COMBINED attack
5. Apply Rule 10: Use worst realistic operational parameters for severity

Write to {SCRATCHPAD}/depth_iterative_{type}_findings.md

Return: 'DONE: {N} chain-enabled findings analyzed'
")
```

If iterative depth reveals NEW chains, feed back to chain analysis agent for a final update to `chain_hypotheses.md`.
