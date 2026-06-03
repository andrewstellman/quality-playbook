"""v1.5.7 instruction 086 (A-26) regression defense.

Sibling file, consistent with the existing test_install_* split
(test_install_manifest_no_drift / test_install_skill_script_form /
test_install_skill).
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from bin import install_skill


class BundleCompletenessTests(unittest.TestCase):
    """v1.5.7 instruction 086 (A-26) regression defense: every
    bin.<module> reference in SKILL.md or phase_prompts/*.md must be
    either bundled by install_skill.py OR explicitly listed in the
    operator-side allowlist (modules adopters run from the QPB clone,
    NOT from install_root).

    Mutation-test evidence (in-tree per
    ai_context/DEVELOPMENT_PROCESS.md:152-160) — BITE EXECUTED during
    086 development:
      Mutation: remove run_state_lib.py from the 086 bundle additions
        in install_skill.py._bundle_files().
      Observed failure (purged __pycache__ first):
        FAIL: test_every_bin_module_referenced_in_skill_or_phase_prompts_is_bundled_or_allowlisted
        AssertionError: bin.run_state_lib referenced in
        SKILL.md/phase_prompts/*.md but neither bundled nor allowlisted.
      Mutation reverted; tests pass.
    """

    # Adopters do NOT run these from install_root — they're QPB-side
    # operator-driven entry points. SKILL.md / phase_prompts may
    # reference them as `<clone>/bin/<name>.py` style invocations.
    _OPERATOR_SIDE_BIN_MODULES = frozenset({
        "bin.run_playbook",   # Mode B runner — operator-side
        "bin.qpb_validate",   # Phase 0 entry — operator runs from QPB clone
    })

    # v1.5.7 instruction 088: documented illustrative placeholders —
    # NOT real module references. The 088 slash-form regex extension
    # (intentionally) also matches generic file:line citation
    # examples; phase_prompts/phase1.md:93 uses `bin/foo.py:120-135`
    # purely to show the citation FORMAT. Excluding it keeps the
    # broadened regex from false-positiving on teaching examples
    # while still catching real slash-form module references.
    _PLACEHOLDER_BIN_MODULES = frozenset({
        "bin.foo",            # phase1.md:93 citation-format example
    })

    def test_every_bin_module_referenced_in_skill_or_phase_prompts_is_bundled_or_allowlisted(self) -> None:
        """For each `bin.<module>` reference in SKILL.md or
        phase_prompts/*.md, verify the corresponding file is either
        bundled by install_skill.py::_bundle_files() OR in the
        operator-side allowlist."""
        qpb_root = Path(__file__).resolve().parent.parent.parent
        text_sources = [qpb_root / "SKILL.md"]
        phase_prompts = qpb_root / "phase_prompts"
        if phase_prompts.is_dir():
            text_sources.extend(sorted(phase_prompts.glob("*.md")))

        # v1.5.7 instruction 088 (Council follow-up): match BOTH the
        # dotted form (`bin.<module>`) and the slash form
        # (`bin/<module>.py`). SKILL.md:266,801 + phase_prompts/
        # phase1.md:31 + phase_prompts/phase4.md:29 use slash form;
        # the dotted-only regex had a real coverage hole that would
        # silently rot if a future doc addition used only slash form.
        DOTTED_PATTERN = re.compile(r"\bbin\.([a-z_][a-z0-9_]+)\b")
        SLASH_PATTERN = re.compile(r"\bbin/([a-z_][a-z0-9_]+)\.py\b")
        referenced: set[str] = set()
        for src in text_sources:
            if src.is_file():
                text = src.read_text(encoding="utf-8")
                for match in DOTTED_PATTERN.finditer(text):
                    referenced.add(f"bin.{match.group(1)}")
                for match in SLASH_PATTERN.finditer(text):
                    referenced.add(f"bin.{match.group(1)}")  # normalize

        bundled = {
            f"bin.{src.name[:-3]}"  # strip .py
            for src, _dst in install_skill._bundle_files(qpb_root)
            if src.suffix == ".py" and src.parent.name == "bin"
        }

        for ref in sorted(referenced):
            if ref in self._OPERATOR_SIDE_BIN_MODULES:
                continue
            if ref in self._PLACEHOLDER_BIN_MODULES:
                continue
            self.assertIn(
                ref, bundled,
                f"{ref} referenced in SKILL.md/phase_prompts/*.md "
                f"but neither bundled by install_skill.py nor in the "
                f"operator-side allowlist "
                f"({sorted(self._OPERATOR_SIDE_BIN_MODULES)}). Either "
                f"add it to _bundle_files() or, if it's an "
                f"operator-side entry point adopters don't invoke from "
                f"install_root, add it to the _OPERATOR_SIDE_BIN_MODULES "
                f"allowlist.")


class AgentsMdCpBlocksMatchBundleTests(unittest.TestCase):
    """v1.5.7 instruction 088 (A-29 regression defense): AGENTS.md
    Step 3 manual install recipes must enumerate exactly the same
    bin/*.py files that install_skill.py::_bundle_files() copies.
    Drift between these two paths re-creates the A-26 ship-blocker
    via a doc-sanctioned alternate adopter path (the 2026-05-18
    post-087 Council A-29 finding: the cp recipes lagged 10 modules
    behind _bundle_files()).

    Mutation-test evidence (in-tree per
    ai_context/DEVELOPMENT_PROCESS.md:152-160) — BITE EXECUTED during
    instruction-088 development:
      Mutation: delete the `cp "$QPB"/bin/run_state_lib.py ...`
        line from BOTH AGENTS.md recipes (Copilot AND Claude Code).
        NOTE: this is a SET comparison over the whole file, so the
        module must be absent from EVERY recipe to register as
        missing — removing it from only one recipe does NOT fire
        (the verify-before-claim correction to the instruction's
        prescribed single-recipe bite).
      Observed failure (purged __pycache__ first):
        FAIL: test_agents_md_cp_blocks_match_bundle
        AssertionError: Items in the first set but not the second:
          'run_state_lib.py'  [the `missing = bundle_files -
          agents_cp_files` assertEqual; first set = _bundle_files()'s
          bin/*.py, second = AGENTS.md cp basenames]
      Mutation reverted (authoritative shutil.copy2 from a pre-bite
      snapshot); test passes.
    """

    def test_agents_md_cp_blocks_match_bundle(self) -> None:
        qpb_root = Path(__file__).resolve().parent.parent.parent
        agents_md = (qpb_root / "AGENTS.md").read_text(encoding="utf-8")
        cp_pattern = re.compile(
            r'cp\s+"\$QPB"/bin/([a-z_][a-z0-9_]+\.py)\s')
        agents_cp_files = set(cp_pattern.findall(agents_md))
        bundle_files = {
            src.name
            for src, _dst in install_skill._bundle_files(qpb_root)
            if src.suffix == ".py" and src.parent.name == "bin"
        }
        missing = bundle_files - agents_cp_files
        extra = agents_cp_files - bundle_files
        self.assertEqual(
            missing, set(),
            f"AGENTS.md missing bin/*.py: {sorted(missing)}. The "
            "AGENTS.md manual install recipe MUST mirror "
            "install_skill.py::_bundle_files() (A-29 ship-blocker: "
            "drift re-creates A-26 via the doc-sanctioned path).")
        self.assertEqual(
            extra, set(),
            f"AGENTS.md has bin/*.py NOT in bundle: {sorted(extra)}. "
            "Did install_skill.py drop a module without updating "
            "AGENTS.md in lockstep?")


class AllMdCpBlocksMatchBundleTests(unittest.TestCase):
    """v1.5.7 instruction 089 (F2 Council finding): the A-29 drift
    class — a doc-side bin/ cp recipe lagging _bundle_files() —
    recurs unless EVERY adopter-facing doc with a cp recipe is pinned,
    not just AGENTS.md. 088's AgentsMdCpBlocksMatchBundleTests covered
    AGENTS.md (prefixed `cp "$QPB"/bin/x.py`) only; README Step 3 uses
    the bare `cp bin/x.py` form and was the stale third enumeration
    (F1). This class scans EVERY root/docs *.md that carries a bin/ cp
    recipe (auto-discovered, so a future recipe-bearing doc is covered
    the moment it lands) and asserts per-file symmetric equality with
    _bundle_files(), matching BOTH the prefixed and bare cp forms.

    Mutation-test evidence (in-tree per
    ai_context/DEVELOPMENT_PROCESS.md:152-160) — BITE EXECUTED during
    instruction-089 development:
      Mutation: delete the `cp bin/run_state_lib.py ...` line from
        ALL THREE README Step 3 recipes (Claude / Copilot-flat /
        Copilot-nested). NOTE: this is a per-file WHOLE-FILE set
        comparison, so the module must be absent from EVERY recipe
        in the file to register as drift — deleting it from only one
        recipe does NOT fire (the verify-before-claim correction to
        the instruction's prescribed single-line bite, same
        set-semantics class as the 088 AGENTS.md bite).
      Observed failure (purged __pycache__ first):
        FAIL: test_all_md_cp_recipes_match_bundle
        AssertionError: Items in the first set but not the second:
          'run_state_lib.py'  [README.md cp recipe drifted from
          _bundle_files(): missing={'run_state_lib.py'}]
      Mutation reverted (authoritative shutil.copy2 from a pre-bite
      snapshot); test passes.
    """

    # Prefixed (AGENTS.md): cp "$QPB"/bin/<name>.py <dest>
    PREFIXED_PATTERN = re.compile(
        r'cp\s+"\$QPB"/bin/([a-z_][a-z0-9_]+\.py)\s')
    # Bare (README Step 3): cp bin/<name>.py <dest>
    BARE_PATTERN = re.compile(
        r'(?:^|\s)cp\s+bin/([a-z_][a-z0-9_]+\.py)\s')
    # Any bin/ cp recipe line (prefixed OR bare) — scan-set selector.
    _RECIPE_LINE = re.compile(
        r'cp\s+(?:"\$QPB"/)?bin/[a-z_][a-z0-9_]+\.py\s')
    # Reuse 088's placeholder exclusion (citation-format teaching
    # examples), mapped basename -> dotted to match the existing set.
    _PLACEHOLDER_BASENAMES = frozenset(
        ref.split(".", 1)[1] + ".py"
        for ref in BundleCompletenessTests._PLACEHOLDER_BIN_MODULES
    )

    def _scan_set(self, qpb_root: Path) -> list[Path]:
        candidates: list[Path] = []
        candidates.extend(sorted(qpb_root.glob("*.md")))
        docs = qpb_root / "docs"
        if docs.is_dir():
            candidates.extend(sorted(docs.rglob("*.md")))
        out = []
        for p in candidates:
            try:
                txt = p.read_text(encoding="utf-8")
            except OSError:
                continue
            if self._RECIPE_LINE.search(txt):
                out.append(p)
        return out

    def test_all_md_cp_recipes_match_bundle(self) -> None:
        qpb_root = Path(__file__).resolve().parents[2]
        bundle_files = {
            src.name
            for src, _dst in install_skill._bundle_files(qpb_root)
            if src.suffix == ".py" and src.parent.name == "bin"
        }
        scanned = self._scan_set(qpb_root)
        self.assertTrue(
            scanned,
            "no *.md with a bin/ cp recipe found — scan-set selector "
            "is stale (AGENTS.md + README.md should match).")
        for p in scanned:
            txt = p.read_text(encoding="utf-8")
            declared = (
                set(self.PREFIXED_PATTERN.findall(txt))
                | set(self.BARE_PATTERN.findall(txt))
            ) - self._PLACEHOLDER_BASENAMES
            missing = bundle_files - declared
            extra = declared - bundle_files
            rel = p.relative_to(qpb_root)
            self.assertEqual(
                missing, set(),
                f"{rel} cp recipe drifted from _bundle_files(): "
                f"missing={sorted(missing)}. Every adopter-facing "
                f"manual install recipe MUST mirror "
                f"install_skill.py::_bundle_files() (A-29 class).")
            self.assertEqual(
                extra, set(),
                f"{rel} cp recipe has bin/*.py NOT in _bundle_files(): "
                f"extra={sorted(extra)}. Did _bundle_files() drop a "
                f"module without updating {rel} in lockstep?")


if __name__ == "__main__":
    unittest.main()
