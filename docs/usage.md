# Usage

> **Just installed?** See [getting-started.md](getting-started.md) first — what's required, what's optional, and how to run your first audit.

All invocations -- terminal CLI, Claude Code slash commands, and Codex CLI -- launch the same V2 deterministic driver (`plamen_driver.py`). The driver runs each audit phase as an isolated subprocess with automatic checkpointing, gating, retry, and rate-limit pause/resume.

---

## Quick Start

### Terminal (recommended)

```bash
plamen                                  # Interactive wizard
plamen core /path/to/project            # SC audit, Core mode
plamen l1 thorough /path/to/node-client # L1 audit, Thorough mode
```

### Claude Code

```
/plamen-wizard          # SC audit — interactive config then driver launch
/plamen-l1-wizard       # L1 infrastructure audit
```

### Codex CLI

```
$plamen core /path/to/project           # Codex has no slash commands
$plamen l1 core /path/to/node-client
```

Codex requires prior setup: `plamen install --codex`.

---

## CLI Reference (`plamen` / `plamen.py`)

All commands below launch the V2 deterministic driver. The `plamen` command is a symlink to `plamen.py` in your PATH.

### Audit Commands

| Command | Description |
|---------|-------------|
| `plamen` | Interactive wizard: mode selection, target, docs, scope, cost estimate, launch |
| `plamen light /path` | Smart contract audit in Light mode (Pro plan, ~18-22 agents) |
| `plamen core /path` | Smart contract audit in Core mode (Max plan, ~30-50 agents) |
| `plamen thorough /path` | Smart contract audit in Thorough mode (Max plan, ~40-100 agents) |
| `plamen l1 light /path` | L1 infrastructure audit in Light mode |
| `plamen l1 core /path` | L1 infrastructure audit in Core mode |
| `plamen l1 thorough /path` | L1 infrastructure audit in Thorough mode |
| `plamen compare` | Diff two audit reports (post-mortem analysis) |
| `plamen resume` | Resume an interrupted audit from last checkpoint |
| `plamen resume /path/config.json` | Resume a specific audit config |

### Setup Commands

| Command | Description |
|---------|-------------|
| `plamen setup` | Toolchain installer: installs chain tools, checks dependencies, shows status |
| `plamen install` | Symlink installer for Claude Code (`~/.claude/`) |
| `plamen install --codex` | Symlink installer for Codex CLI (`~/.codex/plamen/`) |
| `plamen rag` | Build or rebuild the RAG vulnerability knowledge base |
| `plamen uninstall` | Remove Plamen from `~/.claude/` (and `~/.codex/plamen/` if installed) |

### Options

| Option | Applies to | Description |
|--------|-----------|-------------|
| `--docs PATH` | SC audits | Path to whitepaper or spec file |
| `--scope PATH` | SC audits | Path to scope file listing contracts |
| `--notes TEXT` | SC audits | Free-text scope notes |
| `--network NAME` | SC audits | Target network (ethereum, arbitrum, optimism, base, polygon, bsc, avalanche) |
| `--proven-only` | SC audits | Cap findings with only `[CODE-TRACE]` evidence at Low severity |
| `--tier T0\|T1\|T2\|T3` | L1 audits | L1 tier override (auto-detected from LOC by default) |
| `--modules a,b,c` | L1 T1 audits | Module selection for T1 subsystem scope |
| `--codex` | All audits | Force Codex CLI backend |
| `--claude` | All audits | Force Claude Code backend (default) |

### Examples

```bash
# SC audit with docs and scope
plamen core /path/to/project --docs whitepaper.pdf --scope scope.txt

# SC Thorough with proven-only and network
plamen thorough /path/to/project --network ethereum --proven-only

# L1 audit targeting specific modules
plamen l1 core /path/to/geth --tier t1 --modules consensus,p2p

# Build RAG database (requires ~6GB RAM)
export SOLODIT_API_KEY=your_key_here
plamen rag
```

---

## PATH Setup

To use `plamen` as a command (instead of `python plamen.py`):

```bash
# Linux (bash)
echo 'export PATH="$HOME/.plamen:$PATH"' >> ~/.bashrc && source ~/.bashrc

# macOS (zsh)
echo 'export PATH="$HOME/.plamen:$PATH"' >> ~/.zshrc && source ~/.zshrc
```

```powershell
# Windows (PowerShell, one-time)
[System.Environment]::SetEnvironmentVariable("Path", "$env:USERPROFILE\.plamen;" + $env:Path, "User")
```

Or run directly: `python3 ~/.plamen/plamen.py` (macOS/Linux) or `python ~/.plamen/plamen.py` (Windows).

---

## Resuming an Interrupted Audit

The driver checkpoints after each phase. If the process crashes, hits rate limits, or is interrupted:

```bash
# Auto-detect and resume
plamen resume

# Resume a specific config
plamen resume /path/to/project/.scratchpad/config.json

# Direct driver launch (advanced)
python ~/.plamen/scripts/plamen_driver.py /path/to/project/.scratchpad/config.json

# Fresh restart (discard previous progress)
python ~/.plamen/scripts/plamen_driver.py --fresh /path/to/project/.scratchpad/config.json
```

From Claude Code, running `/plamen-wizard` auto-detects an existing scratchpad and offers to resume.

---

## When to Use Which

| | Terminal (`plamen`) | Claude Code | Codex CLI |
|---|---|---|---|
| **First time** | Use this | `/plamen-wizard` | Need Codex + tools |
| **Cost estimate** | Shows estimate | No estimate | No estimate |
| **Resume on crash** | `plamen resume` | `/plamen-wizard` (auto-detects) | `$plamen resume` |
| **Daily use** | `plamen core .` | `/plamen-wizard` | `$plamen core .` |

---

## Cost Estimation

The terminal wrapper estimates token usage before launch:
- Input/Output tokens (millions)
- API cost (USD)
- Weekly plan usage (% of Pro, Max x5, Max x20)

Estimates are rough -- actual usage varies with protocol complexity. Run `/cost` after an audit for actuals.
