"""v1.6.0 Feature H slice 2 (instruction 014) — persona orchestration + isolation.

THE SECURITY oracle (§8b Verification 3). Isolation is PREVENTION by
construction: the impl tree / secrets / operator_confirmations.jsonl are never
staged, and the spawn tool config has no shell and no network, so a persona
cannot reach them — proven here, not merely detected after the fact. The
fabrication-tell is exercised as an independent backstop.
"""

import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = (
    REPO_ROOT / "plugins" / "quality-playbook" / "skills" / "quality-playbook" / "scripts"
)
sys.path.insert(0, str(SCRIPT_DIR))

import persona_orchestration as po  # noqa: E402


DOCS = po.StagedInput("13_api_reference.md", "# API Reference\n\nrouter.Get(pattern, handler)\n")
SPEC = po.StagedInput("REQUIREMENTS.md", "# Requirements\n\n### REQ-001: Routes match longest prefix\n")
RUBRIC = po.StagedInput("rubric.md", "# Rubric\n\nComplete · Honest · Consistent · Correct\n")


def _h_provision(persona):
    # Feature H context provisioning: docs + rendered spec + rubric.
    return [DOCS, SPEC, RUBRIC]


def _stub_executor(persona, staging_dir, tool_config):
    # A deterministic persona: emits one grounded-looking add citing staged text.
    return {"persona_id": persona["id"], "moves": [
        {"move": "add", "req_id": None, "section": "Routing",
         "reason": "the reference documents regexp params",
         "citation": "router.Get(pattern, handler)"},
    ]}


class StagingCorrectnessTests(unittest.TestCase):
    def _run_root_with_secrets(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        # Simulate a real run tree the persona must NOT reach.
        (root / "src").mkdir()
        (root / "src" / "router.go").write_text("func Get(){ /* impl */ }", encoding="utf-8")
        (root / ".env").write_text("SECRET=abc", encoding="utf-8")
        (root / "quality").mkdir()
        (root / "quality" / "operator_confirmations.jsonl").write_text(
            '{"ts":"t"}\n', encoding="utf-8")
        return root

    def test_staging_dir_contains_exactly_the_declared_inputs(self):
        root = self._run_root_with_secrets()
        staging = po.stage_persona_inputs("domain-expert", [DOCS, SPEC, RUBRIC], root / "_staging")
        names = sorted(p.name for p in staging.iterdir())
        self.assertEqual(names, ["13_api_reference.md", "REQUIREMENTS.md", "rubric.md"])

    def test_impl_secrets_and_confirmations_are_absent(self):
        root = self._run_root_with_secrets()
        staging = po.stage_persona_inputs("security-reviewer", [DOCS, SPEC, RUBRIC], root / "_staging")
        staged = {p.name for p in staging.rglob("*")}
        self.assertNotIn("router.go", staged)
        self.assertNotIn(".env", staged)
        self.assertNotIn("operator_confirmations.jsonl", staged)
        # No subdirectory (which could re-introduce the impl tree).
        self.assertFalse(any(p.is_dir() for p in staging.rglob("*")))
        po.assert_isolation(staging)  # contract holds


class LeastPrivilegePreventionTests(unittest.TestCase):
    """Oracle 2 — prevention, not detection."""

    def _staging(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return po.stage_persona_inputs("p", [DOCS, SPEC, RUBRIC], Path(tmp.name))

    def test_tool_config_denies_shell_and_network(self):
        cfg = po.persona_tool_config(self._staging())
        for shell in ("Bash", "shell", "sh", "exec"):
            self.assertTrue(cfg.denies(shell), shell)
        for net in ("fetch", "WebFetch", "network", "curl", "http"):
            self.assertTrue(cfg.denies(net), net)
        self.assertFalse(cfg.denies("Read"))
        self.assertFalse(cfg.allow_bash)
        self.assertFalse(cfg.allow_network)

    def test_read_root_is_the_staging_dir(self):
        staging = self._staging()
        cfg = po.persona_tool_config(staging)
        self.assertEqual(Path(cfg.read_root), staging.resolve())

    def test_staging_refuses_a_forbidden_input(self):
        # A caller that tries to stage the human ledger is refused (defensive).
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        with self.assertRaises(po.IsolationError):
            po.stage_persona_inputs(
                "p",
                [po.StagedInput("operator_confirmations.jsonl", '{"ts":"t"}')],
                Path(tmp.name),
            )

    def test_assert_isolation_rejects_a_symlink_escape(self):
        # A symlink into the impl tree would defeat prevention-by-absence.
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        outside = root / "secret.txt"
        outside.write_text("SECRET", encoding="utf-8")
        staging = po.stage_persona_inputs("p", [DOCS], root / "_staging")
        (staging / "link").symlink_to(outside)
        with self.assertRaises(po.IsolationError):
            po.assert_isolation(staging)

    def test_the_prevention_argument_holds_end_to_end(self):
        # The complete claim: a persona cannot read the impl tree/secrets because
        # (a) they are not in the staging dir and (b) it has no shell/network to
        # reach them. Both facts asserted together.
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        (root / "src").mkdir(); (root / "src" / "impl.go").write_text("x", encoding="utf-8")
        staging = po.stage_persona_inputs("p", [DOCS, SPEC, RUBRIC], root / "_staging")
        staged = {p.name for p in staging.rglob("*")}
        cfg = po.persona_tool_config(staging)
        self.assertNotIn("impl.go", staged)          # (a) absent
        self.assertTrue(cfg.denies("Bash"))          # (b) no shell
        self.assertTrue(cfg.denies("fetch"))         # (b) no network


class FabricationTellTests(unittest.TestCase):
    def test_move_citing_unstaged_content_is_flagged(self):
        # A persona output referencing impl detail NOT in its staged inputs.
        diff = {"moves": [
            {"move": "add", "reason": "read the source",
             "citation": "func Get(){ /* impl */ }"},  # not in staged docs
        ]}
        flags = po.detect_fabrication(diff, [DOCS.text, SPEC.text, RUBRIC.text])
        self.assertEqual(len(flags), 1)
        self.assertIn("fabrication", flags[0].lower())

    def test_grounded_move_citing_staged_content_is_clean(self):
        diff = {"moves": [
            {"move": "add", "citation": "router.Get(pattern, handler)"},  # in DOCS
        ]}
        self.assertEqual(po.detect_fabrication(diff, [DOCS.text, SPEC.text, RUBRIC.text]), [])


class IndependenceAndRunTests(unittest.TestCase):
    def _selected(self):
        return [
            {"id": "domain-expert", "anchored": True, "specialization": "Go routing"},
            {"id": "security-reviewer", "anchored": True},
        ]

    def test_personas_get_separate_staging_dirs_and_are_blind(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        seen_dirs = []

        def executor(persona, staging_dir, cfg):
            seen_dirs.append(str(staging_dir))
            # The executor CANNOT see any other persona's diff-set — its only
            # inputs are its own persona, staging dir, and config (structural
            # independence). Confirm the staging dir holds only this run's files.
            names = {p.name for p in Path(staging_dir).iterdir()}
            assert names == {"13_api_reference.md", "REQUIREMENTS.md", "rubric.md"}
            return {"persona_id": persona["id"], "moves": []}

        runs = po.run_personas(self._selected(), _h_provision, executor, Path(tmp.name))
        self.assertEqual(len(runs), 2)
        # Distinct staging dirs per persona (blind, no shared context).
        self.assertEqual(len(set(seen_dirs)), 2)
        self.assertEqual(len(set(r.staging_dir for r in runs)), 2)

    def test_run_rejects_a_defer_move(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)

        def bad_executor(persona, staging_dir, cfg):
            return {"moves": [{"move": "defer", "reason": "punt"}]}

        with self.assertRaises(ValueError):
            po.run_personas([{"id": "domain-expert"}], _h_provision, bad_executor, Path(tmp.name))

    def test_run_carries_diff_set_and_fabrication_flags(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        runs = po.run_personas([{"id": "domain-expert"}], _h_provision, _stub_executor, Path(tmp.name))
        self.assertEqual(runs[0].diff_set["moves"][0]["move"], "add")
        self.assertEqual(runs[0].fabrication_flags, [])  # cites staged content

    def test_raw_diff_set_shape_no_grounding_or_apply(self):
        # This slice emits RAW candidates only — no grounded/candidate bucket,
        # no merge, no apply. The move carries the context slices 3-5 need.
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        runs = po.run_personas([{"id": "domain-expert"}], _h_provision, _stub_executor, Path(tmp.name))
        move = runs[0].diff_set["moves"][0]
        self.assertEqual(set(move) >= {"move", "reason"}, True)
        self.assertIn("citation", move)  # context for slice 3 grounding


class TargetAgnosticSeamTests(unittest.TestCase):
    def test_a_different_provision_shape_works(self):
        # Feature B's provisioning is the OPPOSITE isolation: finding + source +
        # REQ + rubric. The orchestration must not care what the inputs are.
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)

        def b_provision(persona):
            return [
                po.StagedInput("finding.md", "# Finding\n\nBUG-001 claim"),
                po.StagedInput("source_excerpt.go", "func F(){}"),
                po.StagedInput("REQ-001.md", "### REQ-001"),
                po.StagedInput("rubric.md", "# FP rubric"),
            ]

        def executor(persona, staging_dir, cfg):
            names = {p.name for p in Path(staging_dir).iterdir()}
            assert names == {"finding.md", "source_excerpt.go", "REQ-001.md", "rubric.md"}
            return {"moves": []}

        runs = po.run_personas([{"id": "security-reviewer"}], b_provision, executor, Path(tmp.name))
        self.assertEqual(len(runs), 1)
        # Same orchestration, different (target-supplied) input set.
        self.assertEqual(sorted(runs[0].staged_names),
                         ["REQ-001.md", "finding.md", "rubric.md", "source_excerpt.go"])

    def test_staging_fingerprint_is_reproducible(self):
        a = po.staging_fingerprint([DOCS, SPEC, RUBRIC])
        b = po.staging_fingerprint([RUBRIC, DOCS, SPEC])  # order-independent
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
