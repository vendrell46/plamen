"""Tests for v2.0.6 P2 — canonical ID ledger + collision gate.

Covers:
  P2.1  _id_ledger.json schema + helpers (load/save/register/next/lookup)
  P2.2  Inventory + niche promotion register at mint time
  P2.3  Chain prompt receives driver-injected ID ledger directive
  P2.4  Post-phase collision gate (BLOCKING for chain / chain_agent2)
  P2.5  Consumer backstop gate (WARNING-only at first ship)

The DODO 2026-05-21 root cause was chain attempt 1 minting GRP-01 for
title-A (Critical public-withdraw), then chain attempt 2 re-minting
GRP-01 for title-B (Medium reinitializer). All P2 fixtures here are
synthetic — never DODO-scratchpad copies — to prevent overfitting.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

from plamen_parsers import (  # noqa: E402
    _ID_LEDGER_NAME,
    _ID_LEDGER_SCHEMA_VERSION,
    _id_ledger_load,
    _id_prefix_of,
    _title_hash,
    id_ledger_all_for_prefix,
    id_ledger_all_records,
    id_ledger_lookup,
    id_ledger_next_available,
    id_ledger_register,
)
from plamen_validators import (  # noqa: E402
    _generate_id_ledger_collision_retry_hint,
    _parse_hypothesis_id_title_pairs,
    _validate_consumer_ids_in_ledger,
    _validate_id_ledger_collisions,
)
from plamen_prompt import _render_id_ledger_directive  # noqa: E402


# ---------------------------------------------------------------------------
# P2.1 — schema + helpers
# ---------------------------------------------------------------------------


def test_p21_round_trip(tmp_path):
    """Allocate, persist, reload — basic ledger round-trip."""
    r1 = id_ledger_register(
        tmp_path, finding_id="GRP-01", owner_phase="chain_agent1",
        owner_attempt=1, owning_artifact="hypotheses.md",
        title="Some root cause",
    )
    assert r1["status"] == "REGISTERED"
    assert (tmp_path / _ID_LEDGER_NAME).exists()
    payload = json.loads((tmp_path / _ID_LEDGER_NAME).read_text(encoding="utf-8"))
    assert payload["schema_version"] == _ID_LEDGER_SCHEMA_VERSION
    assert len(payload["allocations"]) == 1
    rec = payload["allocations"][0]
    assert rec["id"] == "GRP-01"
    assert rec["owner_phase"] == "chain_agent1"
    assert rec["prefix"] == "GRP-"
    assert "title_hash" in rec and rec["title_hash"].startswith("sha256:")


def test_p21_title_hash_stable_across_minor_variations():
    """Same logical title hashes identically across case/whitespace/ID-prefix."""
    base = "GatewayTransferNative.withdraw() Is Public — Permissionless Drain"
    h_base = _title_hash(base)
    assert _title_hash(base.lower()) == h_base
    assert _title_hash(f"  {base}  ") == h_base
    assert _title_hash(f"[GRP-01]: {base}") == h_base
    assert _title_hash(f"Finding [GRP-01]: {base}") == h_base


def test_p21_id_prefix_of():
    """Prefix extractor handles common forms; returns '' for non-IDs."""
    assert _id_prefix_of("GRP-01") == "GRP-"
    assert _id_prefix_of("HM-99") == "HM-"
    assert _id_prefix_of("INV-001") == "INV-"
    assert _id_prefix_of("CH-12") == "CH-"
    assert _id_prefix_of("not-an-id") == ""
    assert _id_prefix_of("") == ""


def test_p21_register_reuse_when_title_unchanged(tmp_path):
    """Re-registering the same ID with the SAME title is REUSED, not a write."""
    r1 = id_ledger_register(
        tmp_path, finding_id="GRP-01", owner_phase="chain_agent1",
        owner_attempt=1, owning_artifact="hypotheses.md",
        title="Same root cause",
    )
    assert r1["status"] == "REGISTERED"
    r2 = id_ledger_register(
        tmp_path, finding_id="GRP-01", owner_phase="chain_agent1",
        owner_attempt=2, owning_artifact="hypotheses.md",
        title="Same root cause",
    )
    assert r2["status"] == "REUSED"
    # Ledger should still have exactly ONE allocation.
    assert len(id_ledger_all_records(tmp_path)) == 1


def test_p21_register_collision_when_title_differs(tmp_path):
    """The DODO root cause: same ID, different title → COLLISION."""
    id_ledger_register(
        tmp_path, finding_id="GRP-01", owner_phase="chain_agent1",
        owner_attempt=1, owning_artifact="hypotheses.md",
        title="GatewayTransferNative.withdraw() Is Public",
    )
    r = id_ledger_register(
        tmp_path, finding_id="GRP-01", owner_phase="chain_agent1",
        owner_attempt=2, owning_artifact="hypotheses.md",
        title="No reinitializer() Function",
    )
    assert r["status"] == "COLLISION"
    assert r["existing"]["title_preview"].startswith("GatewayTransfer")
    assert r["current"]["title_preview"].startswith("No reinitializer")


def test_p21_next_available_advances_per_prefix(tmp_path):
    """next_available picks max+1 per prefix; prefixes are independent."""
    for i in range(1, 4):
        id_ledger_register(
            tmp_path, finding_id=f"GRP-{i:02d}", owner_phase="chain_agent1",
            owner_attempt=1, owning_artifact="hypotheses.md",
            title=f"title {i}",
        )
    id_ledger_register(
        tmp_path, finding_id="HH-01", owner_phase="chain_agent1",
        owner_attempt=1, owning_artifact="hypotheses.md", title="hh title",
    )
    assert id_ledger_next_available(tmp_path, "GRP-") == "GRP-04"
    assert id_ledger_next_available(tmp_path, "HH-") == "HH-02"
    assert id_ledger_next_available(tmp_path, "HM-") == "HM-01"


def test_p21_lookup_and_filter(tmp_path):
    """lookup + all_for_prefix return expected records."""
    id_ledger_register(
        tmp_path, finding_id="GRP-01", owner_phase="chain_agent1",
        owner_attempt=1, owning_artifact="hypotheses.md", title="t1",
    )
    id_ledger_register(
        tmp_path, finding_id="HH-01", owner_phase="chain_agent1",
        owner_attempt=1, owning_artifact="hypotheses.md", title="t2",
    )
    assert id_ledger_lookup(tmp_path, "GRP-01")["title_preview"] == "t1"
    assert id_ledger_lookup(tmp_path, "missing") is None
    grp_recs = id_ledger_all_for_prefix(tmp_path, "GRP-")
    assert len(grp_recs) == 1


# ---------------------------------------------------------------------------
# P2.3 — prompt directive
# ---------------------------------------------------------------------------


def test_p23_chain_directive_lists_allocations_and_nextavail(tmp_path):
    """build_phase_prompt for chain emits the directive with the live ledger state."""
    id_ledger_register(
        tmp_path, finding_id="GRP-01", owner_phase="chain_agent1",
        owner_attempt=1, owning_artifact="hypotheses.md",
        title="A real title",
    )
    id_ledger_register(
        tmp_path, finding_id="INV-001", owner_phase="inventory",
        owner_attempt=1, owning_artifact="findings_inventory.md",
        title="An inventory finding",
    )
    d = _render_id_ledger_directive("chain", tmp_path)
    assert "## ID LEDGER" in d
    assert "GRP-01" in d
    # INV-* is NOT in chain's namespace — must not appear.
    assert "INV-001" not in d
    # Next-available numbers present.
    assert "GRP-02" in d
    assert "HM-01" in d


def test_p23_chain_directive_handles_empty_ledger(tmp_path):
    """Empty ledger → directive still emits with 'no prior allocations' note."""
    d = _render_id_ledger_directive("chain", tmp_path)
    assert "No prior allocations" in d
    assert "GRP-01" in d  # next-available


def test_p23_directive_empty_for_non_chain_phases(tmp_path):
    """Phases other than chain/chain_agent2 get no directive (empty string)."""
    assert _render_id_ledger_directive("inventory_chunk_a", tmp_path) == ""
    assert _render_id_ledger_directive("breadth", tmp_path) == ""
    assert _render_id_ledger_directive("depth", tmp_path) == ""


def test_p23_chain_agent2_directive_scoped_to_CH(tmp_path):
    """chain_agent2 sees CH-* only — not GRP/HM/etc."""
    id_ledger_register(
        tmp_path, finding_id="GRP-01", owner_phase="chain_agent1",
        owner_attempt=1, owning_artifact="hypotheses.md", title="t1",
    )
    d = _render_id_ledger_directive("chain_agent2", tmp_path)
    assert "CH-01" in d  # next-available CH
    assert "GRP-01" not in d  # different namespace from chain_agent2


# ---------------------------------------------------------------------------
# P2.4 — collision gate
# ---------------------------------------------------------------------------


def test_p24_parse_hypothesis_id_title_pairs():
    """Heading parser extracts (ID, title) pairs from hypotheses-like MD."""
    text = (
        "# Hypotheses\n\n"
        "### GRP-01 — GatewayTransferNative.withdraw() Is Public\n\n"
        "Some body text.\n\n"
        "### HH-02 — Initial fee setter has no upper bound\n\n"
        "Body.\n\n"
        "## Chain Hypothesis CH-01: chain title\n\n"
    )
    pairs = _parse_hypothesis_id_title_pairs(text)
    pair_dict = dict(pairs)
    assert "GRP-01" in pair_dict
    assert "GatewayTransferNative" in pair_dict["GRP-01"]
    assert pair_dict.get("HH-02", "").startswith("Initial fee")
    assert pair_dict.get("CH-01", "").startswith("chain title")


def test_p24_collision_gate_passes_on_first_attempt(tmp_path):
    """Attempt 1: no prior allocations → no collisions."""
    (tmp_path / "hypotheses.md").write_text(
        "### GRP-01 — public withdraw drain\n"
        "**Severity**: Critical\n", encoding="utf-8",
    )
    issues = _validate_id_ledger_collisions(tmp_path, "chain", attempt=1)
    assert issues == []
    # AND the ID is now registered.
    assert id_ledger_lookup(tmp_path, "GRP-01") is not None


def test_p24_collision_gate_detects_remint_with_different_content(tmp_path):
    """Attempt 2 re-mints GRP-01 with DIFFERENT title → collision."""
    # Attempt 1
    (tmp_path / "hypotheses.md").write_text(
        "### GRP-01 — public withdraw drain\n", encoding="utf-8",
    )
    _validate_id_ledger_collisions(tmp_path, "chain", attempt=1)
    # Attempt 2 overwrites with different content
    (tmp_path / "hypotheses.md").write_text(
        "### GRP-01 — no reinitializer in any contract\n", encoding="utf-8",
    )
    issues = _validate_id_ledger_collisions(tmp_path, "chain", attempt=2)
    assert len(issues) == 1
    assert "GRP-01" in issues[0]
    assert "public withdraw" in issues[0]
    assert "no reinitializer" in issues[0]


def test_p24_collision_gate_no_false_positive_on_same_content(tmp_path):
    """Attempt 2 reuses GRP-01 with SAME title → no collision."""
    (tmp_path / "hypotheses.md").write_text(
        "### GRP-01 — public withdraw drain\n", encoding="utf-8",
    )
    _validate_id_ledger_collisions(tmp_path, "chain", attempt=1)
    # Same content (LLM retry that preserved its grouping)
    _validate_id_ledger_collisions(tmp_path, "chain", attempt=2)
    issues = _validate_id_ledger_collisions(tmp_path, "chain", attempt=2)
    assert issues == []


def test_p24_retry_hint_format(tmp_path):
    """Retry hint mentions the conflict and gives actionable repair steps."""
    fake_collisions = [
        "ID `GRP-01` was previously allocated by chain/attempt 1 "
        "to title 'public withdraw'; this attempt tried "
        "to re-allocate it to 'reinitializer missing'"
    ]
    hint = _generate_id_ledger_collision_retry_hint(fake_collisions, "chain")
    assert "ID ledger collision" in hint
    assert "GRP-01" in hint
    assert "REUSE" in hint
    assert "next-available" in hint


def test_p24_gate_silent_on_non_chain_phases(tmp_path):
    """Gate only triggers on chain / chain_agent2; other phases get [] silently."""
    (tmp_path / "hypotheses.md").write_text(
        "### GRP-01 — t\n", encoding="utf-8",
    )
    assert _validate_id_ledger_collisions(tmp_path, "breadth") == []
    assert _validate_id_ledger_collisions(tmp_path, "inventory_chunk_a") == []
    assert _validate_id_ledger_collisions(tmp_path, "depth") == []


# ---------------------------------------------------------------------------
# P2.5 — consumer backstop
# ---------------------------------------------------------------------------


def test_p25_backstop_empty_when_all_refs_in_ledger(tmp_path):
    """Consumer references only ledger-registered IDs → no warnings."""
    id_ledger_register(
        tmp_path, finding_id="GRP-01", owner_phase="chain_agent1",
        owner_attempt=1, owning_artifact="hypotheses.md", title="t",
    )
    id_ledger_register(
        tmp_path, finding_id="HH-02", owner_phase="chain_agent1",
        owner_attempt=1, owning_artifact="hypotheses.md", title="t2",
    )
    (tmp_path / "report_index.md").write_text(
        "| C-01 | Title | Critical | ... | GRP-01 |\n"
        "| H-01 | Title | High | ... | HH-02 |\n", encoding="utf-8",
    )
    issues = _validate_consumer_ids_in_ledger(tmp_path, "report_index")
    assert issues == []


def test_p25_backstop_flags_unregistered_refs(tmp_path):
    """Consumer references an ID not in the ledger → warning issue."""
    id_ledger_register(
        tmp_path, finding_id="GRP-01", owner_phase="chain_agent1",
        owner_attempt=1, owning_artifact="hypotheses.md", title="t",
    )
    (tmp_path / "report_index.md").write_text(
        "| C-01 | Title | Critical | ... | GRP-99 |\n", encoding="utf-8",
    )
    issues = _validate_consumer_ids_in_ledger(tmp_path, "report_index")
    assert len(issues) == 1
    assert "GRP-99" in issues[0]
    assert "consumer-backstop" in issues[0]


def test_p25_backstop_silent_when_ledger_empty(tmp_path):
    """No ledger (legacy audit) → backstop skips silently (no false halt)."""
    (tmp_path / "report_index.md").write_text(
        "| C-01 | Title | Critical | ... | GRP-01 |\n", encoding="utf-8",
    )
    issues = _validate_consumer_ids_in_ledger(tmp_path, "report_index")
    assert issues == []


def test_p25_backstop_ignores_report_tier_ids(tmp_path):
    """M-NN/L-NN/etc. report-tier IDs are not part of the ledger namespace."""
    id_ledger_register(
        tmp_path, finding_id="GRP-01", owner_phase="chain_agent1",
        owner_attempt=1, owning_artifact="hypotheses.md", title="t",
    )
    (tmp_path / "report_index.md").write_text(
        "| M-01 | Title | Medium | ... | GRP-01 |\n"
        "| L-05 | Title | Low | ... | GRP-01 |\n", encoding="utf-8",
    )
    # M-01 and L-05 are report-tier IDs; they're not validated here.
    # GRP-01 is in ledger → no issues.
    issues = _validate_consumer_ids_in_ledger(tmp_path, "report_index")
    assert issues == []


def test_p25_backstop_ignores_inv_for_now(tmp_path):
    """INV-* allowed without ledger entry (legacy compatibility)."""
    # No ledger entries; but consumer references INV-099.
    id_ledger_register(
        tmp_path, finding_id="GRP-01", owner_phase="chain_agent1",
        owner_attempt=1, owning_artifact="hypotheses.md", title="t",
    )
    (tmp_path / "verification_queue.md").write_text(
        "| 1 | INV-099 | verify_INV-099.md | High | Title |\n",
        encoding="utf-8",
    )
    # INV-099 is NOT in ledger but is allowed (P2.2 exception).
    issues = _validate_consumer_ids_in_ledger(tmp_path, "sc_verify_queue")
    assert issues == []
