"""Tests for bin/skill_derivation/curate_requirements.py — Phase 5
Stage 5A REQUIREMENTS.md curation."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from bin.skill_derivation.curate_requirements import (
    CurateConfig,
    curate,
    _cluster_via_union_find,
    _jaccard,
    _tokenize,
)


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r) + "\n")


class JaccardClusteringTests(unittest.TestCase):
    def test_tokenize_drops_stop_words(self) -> None:
        self.assertEqual(
            _tokenize("the orchestrator MUST exit non-zero on missing"),
            {"orchestrator", "exit", "non", "zero", "missing"},
        )

    def test_jaccard_identical_is_one(self) -> None:
        a = _tokenize("phase one produces eight findings")
        b = _tokenize("phase one produces eight findings")
        self.assertAlmostEqual(_jaccard(a, b), 1.0)

    def test_jaccard_disjoint_is_zero(self) -> None:
        a = _tokenize("orchestrator runs phase one")
        b = _tokenize("template formats artifact rendering")
        self.assertAlmostEqual(_jaccard(a, b), 0.0)

    def test_clusters_high_jaccard_pairs(self) -> None:
        reqs = [
            {"id": "A", "acceptance_criteria":
                "Phase 1 produces EXPLORATION.md with 8 findings"},
            {"id": "B", "acceptance_criteria":
                "Phase 1 produces EXPLORATION.md containing 8 findings"},
            {"id": "C", "acceptance_criteria":
                "Phase 5 reconciles bug fixes against the spec"},
        ]
        clusters = _cluster_via_union_find(reqs, threshold=0.6)
        # A + B cluster together (Jaccard ~1.0); C alone.
        self.assertEqual(len(clusters), 2)
        sizes = sorted(len(c) for c in clusters)
        self.assertEqual(sizes, [1, 2])


class CurationFlowTests(unittest.TestCase):
    def test_small_corpus_lands_in_target_band(self) -> None:
        """A 100-REQ corpus across 50 partitions, K=2 default → ~100
        REQs, in [80, 110]. Acceptance criteria use truly distinct
        word stems so the Jaccard dedup doesn't collapse them."""
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            formal = tmp / "pass_c_formal.jsonl"
            # 50 unique vocabulary roots so each (section_idx, j) has
            # a distinct token set after stop-word removal.
            roots = [
                "alpha", "bravo", "charlie", "delta", "echo", "foxtrot",
                "golf", "hotel", "india", "juliet", "kilo", "lima",
                "mike", "november", "oscar", "papa", "quebec", "romeo",
                "sierra", "tango", "uniform", "victor", "whiskey",
                "xray", "yankee", "zulu", "anvil", "boulder", "compass",
                "decoy", "ember", "fjord", "glade", "hatch", "ingot",
                "jolt", "knell", "lattice", "morass", "notch", "obelisk",
                "patina", "quench", "rhombus", "saber", "tempest",
                "umbra", "vellum", "weald", "xenon",
            ]
            recs = []
            for s in range(50):
                root = roots[s]
                # j=0 and j=1 use disjoint vocabulary so the Jaccard
                # dedup doesn't cluster them.
                first_words = (
                    f"{root}-sundial sundial-{root} {root}-glyph "
                    f"glyph-{root} {root}-omen omen-{root}"
                )
                second_words = (
                    f"{root}-geyser geyser-{root} {root}-runic "
                    f"runic-{root} {root}-talon talon-{root}"
                )
                for j, criteria in enumerate([first_words, second_words]):
                    recs.append({
                        "id": f"REQ-PHASE3-{s * 2 + j + 1:03d}",
                        "section_idx": s, "source_document": "SKILL.md",
                        "disposition": "accepted",
                        "title": f"REQ {s}.{j}",
                        "acceptance_criteria": criteria,
                        "tier": 1,
                    })
            _write_jsonl(formal, recs)
            cfg = CurateConfig(formal_path=formal)
            result = curate(cfg)
            self.assertEqual(result["input_accepted"], 100)
            self.assertGreaterEqual(result["total_requirements"], 80)
            self.assertLessEqual(result["total_requirements"], 110)

    def test_jaccard_dedup_collapses_near_duplicates(self) -> None:
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            formal = tmp / "pass_c_formal.jsonl"
            # 10 REQs in section 0 — three near-duplicate pairs +
            # four unique. Jaccard at 0.6 should cluster 3 pairs into
            # 3 representatives + 4 unique = 7 distinct REQs.
            _write_jsonl(formal, [
                {"id": "R1", "section_idx": 0, "source_document": "SKILL.md",
                 "disposition": "accepted",
                 "acceptance_criteria":
                     "phase one produces EXPLORATION.md with eight findings"},
                {"id": "R2", "section_idx": 0, "source_document": "SKILL.md",
                 "disposition": "accepted",
                 "acceptance_criteria":
                     "phase one EXPLORATION.md produces eight findings"},
                {"id": "R3", "section_idx": 0, "source_document": "SKILL.md",
                 "disposition": "accepted",
                 "acceptance_criteria":
                     "exploration must include eight findings minimum count",
                 "tier": 1},
                {"id": "R4", "section_idx": 0, "source_document": "SKILL.md",
                 "disposition": "accepted",
                 "acceptance_criteria":
                     "exploration includes eight findings minimum count"},
                {"id": "U1", "section_idx": 0, "source_document": "SKILL.md",
                 "disposition": "accepted",
                 "acceptance_criteria": "completely orthogonal alpha topic"},
                {"id": "U2", "section_idx": 0, "source_document": "SKILL.md",
                 "disposition": "accepted",
                 "acceptance_criteria": "different beta concept entirely"},
            ])
            cfg = CurateConfig(
                formal_path=formal,
                target_min=1, target_max=20,  # don't iterate
                initial_k=20,  # keep all post-dedup
            )
            result = curate(cfg)
            # R1+R2 cluster, R3+R4 cluster, U1, U2 alone → 4 distinct.
            self.assertEqual(result["total_requirements"], 4)


if __name__ == "__main__":
    unittest.main()
