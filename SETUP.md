# Quick Setup

Plamen supports two AI backends: **Claude Code** and **Codex CLI**. Both use the same audit pipeline and produce the same output. Pick the backend you already have, or install both — they can coexist.

## Automated Setup

```bash
# 1. Clone
git clone https://github.com/PlamenTSV/plamen.git ~/.plamen
cd ~/.plamen && git submodule update --init --recursive

# 2. Install for your backend
python plamen.py install            # Claude Code (symlinks into ~/.claude/)
python plamen.py install --codex    # Codex CLI (symlinks into ~/.codex/plamen/)
# If you use both backends, run both commands

# 3. (Optional) Build RAG vulnerability database (~6GB RAM)
plamen rag
```

> **Windows**: Developer Mode must be enabled before running `plamen.py install` — the installer creates symlinks that require it. See [docs/dependencies.md](docs/dependencies.md) for instructions.

## Interactive Setup

```bash
plamen setup
```

Launches an interactive wizard that checks your toolchain (Foundry, Solana CLI, etc.) and can install missing components automatically.

## Next Steps

- Full manual installation instructions: [docs/setup.md](docs/setup.md)
- Dependency troubleshooting (Python version, OpenSSL, ChromaDB, platform quirks): [docs/dependencies.md](docs/dependencies.md)
