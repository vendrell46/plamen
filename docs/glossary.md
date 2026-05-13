# Glossary

Quick reference for the Plamen-specific terms that show up in the README,
slash commands, and orchestrator rules. Read once; everything else is
explained inline where it's used.

## Pipeline structure

- **Pipeline** — the full audit. Two flavors: `sc` (smart contract) and `l1`
  (node-client infrastructure). Picked at wizard step 0.
- **Phase** — one stage of the pipeline. SC has 39, L1 has more. Examples:
  `recon`, `breadth`, `inventory`, `depth_iter1`, `verify_critical`,
  `report_assemble`. Sequence is hard-coded in
  [`docs/architecture.md`](architecture.md).
- **V1 / V2** — V1 was the legacy single-conversation LLM orchestrator. V2 is
  the current deterministic Python driver (`scripts/plamen_driver.py`) that
  spawns the same agents per phase in subprocesses. V2 is resumable on crash.

## Agent vocabulary

- **Breadth agent** — surveys the whole codebase quickly, flags candidate
  issues. Multiple run in parallel, each covering a subset.
- **Depth agent** — verifies a single candidate by tracing code paths.
  Types: `depth-token-flow`, `depth-state-trace`, `depth-edge-case`,
  `depth-external`, plus `depth-consensus-invariant` and
  `depth-network-surface` for L1.
- **Scanner** — focused single-purpose static check (e.g. `scanner-A`,
  `scanner-B`, `scanner-C` for blind-spots).
- **Niche agent** — flag-triggered specialist (e.g.
  `callback-receiver-safety`, `signature-verification-audit`). Loads only
  when its trigger pattern is detected.
- **Skill** — reusable methodology shipped as a markdown file
  (`SKILL.md`) under `agents/skills/`. Injected into an agent prompt
  when the relevant flag fires.
- **Skeptic-judge** — Thorough-mode quality gate. Skeptic argues against a
  HIGH/CRITICAL finding, judge breaks the tie.

## Evidence

- **PoC** — proof of concept. Executable test that demonstrates the bug.
  Evidence tag `[POC-PASS]` means the test ran and the assertion held.
- **CODE-TRACE** — manual trace through code, no executable test. Lower
  confidence than POC-PASS.
- **CONTESTED** — verdict where verifier and skeptic disagree; held back
  from final report or human-review-only.
- **`.scratchpad/`** — per-audit workspace inside the target project. Holds
  all intermediate artifacts (findings, traces, manifests). Created by
  recon, deleted on `--fresh` restart, otherwise preserved for resume.

## Models & accounts

- **MCP** — Model Context Protocol. Anthropic's protocol for plugging tools
  (Slither, Solodit, ChromaDB, etc.) into Claude Code. Codex CLI supports a
  subset; see [`docs/mcp-servers.md`](mcp-servers.md).
- **RAG** — retrieval-augmented generation. Plamen's vulnerability
  knowledge base built from Solodit + DefiHackLabs + Immunefi writeups.
  Built via `plamen rag` (~6GB RAM, 3–5 min). Optional but improves recall.
- **Pro / Max** — Anthropic Claude subscription tiers in the audit-mode
  table. Pro = ~5x weekly cap; Max = ~20x. Light mode is Pro-friendly;
  Core/Thorough generally need Max.
- **Sonnet / Opus / Haiku** — Anthropic Claude model tiers. Cheaper /
  faster / less capable in that order. Plamen picks per agent role per
  audit mode automatically.

## Operations

- **Bake (Phase 0.5)** — L1-only. Runs `scip-go` / `rust-analyzer scip` /
  Opengrep once before recon to build a code-index baseline. SC mode does
  not have this phase.
- **Recon** — first phase of every audit. Builds the design context,
  attack surface, semantic invariants. Output drives every later phase.
- **Inventory** — phase that lists every entry point, state variable, and
  external interaction for downstream agents to consume.
- **Validation Sweep** — late-pipeline pass that re-verifies the
  highest-priority candidates with a fresh model context.
