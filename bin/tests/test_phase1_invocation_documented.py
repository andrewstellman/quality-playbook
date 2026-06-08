"""v1.5.7 instruction 058 (A-11) — the canonical Phase 1
reference_docs_ingest invocation must be layout-aware.

`bin/reference_docs_ingest.py` does `from bin import benchmark_lib`
at import, so `python3 -m bin.reference_docs_ingest <target>`
resolves ONLY when `bin/` is reachable as a top-level package. For
an `install_skill.py`-layout adopter the bundled `bin/` lives at
`<install_root>/bin/` (inside the marker dir), NOT at the target
repo root — so the bare invocation taught pre-058 silently failed
with `ModuleNotFoundError: No module named 'bin'` (the virtio
opus-4.6 Mode-A repro, 2026-05-16). SKILL.md + the Phase 1 reference
guide now teach the `PYTHONPATH=<install_root>` form, and
`install_skill.py --verbose` emits the exact command.

These tests pin that the documentation + the installer hint teach
the cwd-independent invocation so a future edit cannot silently
regress to the bare `-m` form.
"""

from __future__ import annotations

import io
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

_QPB_ROOT = Path(__file__).resolve().parents[2]
# v1.5.8 instruction 208: SKILL.md + references/ moved into the
# plugin skill folder.
_SKILL_DIR = _QPB_ROOT / "plugins" / "quality-playbook" / "skills" / "quality-playbook"
_SKILL_MD = _SKILL_DIR / "SKILL.md"
_PHASE1_GUIDE = _SKILL_DIR / "references" / "phase1_exploration_guide.md"

from bin import install_skill  # noqa: E402


def _phase1_section(text: str) -> str:
    """SKILL.md slice from the Phase 1 heading to the Phase 2
    heading — scopes the assertion to the Phase 1 description."""
    start = text.index("**Phase 1 (Explore):**")
    rest = text[start:]
    nxt = rest.find("**Phase 2 (Generate):**")
    return rest if nxt == -1 else rest[:nxt]


class Phase1InvocationDocumentedTests(unittest.TestCase):

    def test_skill_md_phase1_invocation_teaches_pythonpath(self) -> None:
        """SKILL.md's Phase 1 description teaches the layout-aware
        invocation (PYTHONPATH=<install_root>), not the bare
        cwd-dependent `-m bin.reference_docs_ingest` form.

        Mutation-test evidence (in-tree per
        ai_context/DEVELOPMENT_PROCESS.md:152-160), instruction-058
        A-11:
          Mutation: revert SKILL.md's Phase 1 paragraph to the
          pre-058 text `(`python -m bin.reference_docs_ingest
          <target>` to walk `reference_docs/` …)` — i.e. drop the
          `PYTHONPATH=<install_root>` invocation form.
          Expected failure: THIS test fails with
            AssertionError: SKILL.md Phase 1 description must teach a
            cwd-independent reference_docs_ingest invocation
            (PYTHONPATH=<install_root> …) — the bare `-m` form
            silently fails for install_skill.py-layout adopters
            (A-11)
          because the Phase 1 section no longer contains `PYTHONPATH=`.
          Restoration: re-apply the 058 paragraph; passes.
          Bite executed during instruction-058 development;
          PASS→FAIL→PASS confirmed (__pycache__ purged between
          mutate and restore).
        """
        section = _phase1_section(_SKILL_MD.read_text(encoding="utf-8"))
        self.assertIn("bin.reference_docs_ingest", section)
        self.assertIn(
            "PYTHONPATH=", section,
            "SKILL.md Phase 1 description must teach a cwd-independent "
            "reference_docs_ingest invocation (PYTHONPATH=<install_root> "
            "…) — the bare `-m` form silently fails for "
            "install_skill.py-layout adopters (A-11)",
        )
        # The install-root concept must be named so the adopter knows
        # what to set PYTHONPATH to.
        self.assertIn("install root", section.lower())

    def test_phase1_reference_guide_teaches_pythonpath(self) -> None:
        """references/phase1_exploration_guide.md's ingest step
        teaches the same PYTHONPATH=<install_root> form (coherent
        with SKILL.md — no doc drift)."""
        guide = _PHASE1_GUIDE.read_text(encoding="utf-8")
        self.assertIn("bin.reference_docs_ingest", guide)
        self.assertIn(
            "PYTHONPATH=", guide,
            "phase1_exploration_guide.md must teach the layout-aware "
            "PYTHONPATH=<install_root> ingest invocation (A-11)",
        )

    def test_install_skill_verbose_prints_invocation_hint(self) -> None:
        """install_skill.py --verbose emits a
        phase1_ingest_invocation_hint event with a copy-pasteable
        layout-specific command on the install-success path."""
        with TemporaryDirectory() as tmp:
            target = (
                Path(tmp) / ".claude" / "skills" / "quality-playbook"
            )
            buf = io.StringIO()
            rc = install_skill.install(
                target=target,
                source_root=_QPB_ROOT,
                no_smoke=True,
                verbose=True,
                stream=buf,
            )
            out = buf.getvalue()
            self.assertEqual(rc, 0, f"install failed:\n{out[:1500]}")
            self.assertIn("event=phase1_ingest_invocation_hint", out)
            # The hint must carry a cwd-independent command.
            self.assertIn("PYTHONPATH=", out)
            self.assertIn("-m bin.reference_docs_ingest", out)


if __name__ == "__main__":
    unittest.main()
