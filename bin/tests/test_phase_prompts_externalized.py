"""Phase prompt externalization tests (v1.5.4 F-1).

The phase prompt bodies live as markdown files under ``phase_prompts/``
at the QPB repo root, loaded by
``bin.run_playbook._load_phase_prompt``. Externalization is the single-
source-of-truth lever that lets UI-context skill-direct mode and
CLI-automation runner-driven mode read the same content.

These tests pin three contracts:

1. **Loader contract** — verbatim return for pure-literal prompts,
   ``str.format()`` substitution for parameterized prompts, missing
   files raise FileNotFoundError loudly.

2. **File presence contract** — every phase prompt + the single_pass
   and iteration prompts have a corresponding markdown file. If a
   future edit deletes one, this test fires before downstream gates
   silently regress.

3. **Byte-equality contract** — Council 2026-04-30 P0-2: pin SHA256
   hashes for every rendered prompt artifact so cosmetic drift in
   ``phase_prompts/*.md`` (whitespace tweak, typo fix, prose
   rewrite) trips a test. Substring assertions in sibling test files
   covered the load-bearing phrasing but missed any change outside
   those substrings; the Council mutation test confirmed altering
   ``phase1.md``'s opening sentence left all 304 substring
   assertions green. Hashes are the only catch-everything net.

   When you intentionally edit a phase_prompts/*.md file, capture the
   new hashes by running:

       python3 -c "from bin import run_playbook; import hashlib; \\
         print({k: hashlib.sha256(v.encode()).hexdigest() for k, v in [ \\
           ('phase2', run_playbook.phase2_prompt()), ...]})"

   and update ``EXPECTED_HASHES`` below. The hash baseline IS the
   change-acknowledgement signal.
"""

from __future__ import annotations

import hashlib
import unittest
from pathlib import Path

from bin import run_playbook


PHASE_PROMPTS_DIR = Path(__file__).resolve().parents[2] / "phase_prompts"


class PhasePromptsDirectoryTests(unittest.TestCase):
    """File presence contract: every prompt the orchestrator loads
    must have a corresponding markdown file."""

    def test_phase_prompts_dir_exists_at_repo_root(self) -> None:
        self.assertTrue(
            PHASE_PROMPTS_DIR.is_dir(),
            f"phase_prompts/ not found at {PHASE_PROMPTS_DIR}",
        )

    def test_all_six_phase_files_present(self) -> None:
        for n in range(1, 7):
            path = PHASE_PROMPTS_DIR / f"phase{n}.md"
            self.assertTrue(path.is_file(), f"missing {path}")

    def test_single_pass_and_iteration_files_present(self) -> None:
        for name in ("single_pass.md", "iteration.md"):
            self.assertTrue(
                (PHASE_PROMPTS_DIR / name).is_file(),
                f"missing phase_prompts/{name}",
            )

    def test_readme_present(self) -> None:
        self.assertTrue(
            (PHASE_PROMPTS_DIR / "README.md").is_file(),
            "phase_prompts/ should carry a README explaining the layout",
        )


class LoaderContractTests(unittest.TestCase):
    """Loader contract: `_load_phase_prompt(name)` returns file contents
    verbatim; `_load_phase_prompt(name, **subs)` applies str.format()."""

    def test_loader_returns_file_verbatim_when_no_substitutions(self) -> None:
        # phase2 is a pure-literal file; the loader must return its
        # bytes unchanged.
        text = run_playbook._load_phase_prompt("phase2")
        on_disk = (PHASE_PROMPTS_DIR / "phase2.md").read_text(encoding="utf-8")
        self.assertEqual(text, on_disk)

    def test_loader_applies_substitutions_when_provided(self) -> None:
        # iteration.md uses {strategy} substitution.
        text = run_playbook._load_phase_prompt(
            "iteration",
            skill_fallback_guide="GUIDE",
            strategy="parity",
        )
        # The "{strategy}" placeholder should be substituted.
        self.assertIn("using the parity strategy", text)
        self.assertNotIn("{strategy}", text)

    def test_loader_missing_file_raises(self) -> None:
        with self.assertRaises(FileNotFoundError):
            run_playbook._load_phase_prompt("does_not_exist")

    def test_loader_pure_literal_phase_files_have_no_unescaped_braces(self) -> None:
        """Pure-literal phase files (phase2..phase6) skip .format() so
        their JSON code blocks can use single { without escaping. This
        test pins that they are NOT mistakenly run through .format()
        — if a future loader change introduces unconditional
        formatting, the JSON braces would explode."""
        for n in range(2, 7):
            text = run_playbook._load_phase_prompt(f"phase{n}")
            # The loader returns the file unchanged. We re-check by
            # reading the file directly and confirming equality.
            on_disk = (PHASE_PROMPTS_DIR / f"phase{n}.md").read_text(
                encoding="utf-8"
            )
            self.assertEqual(text, on_disk, f"phase{n} loader drift")


class FormatStringEscapingTests(unittest.TestCase):
    """Files that go through .format() must double-escape literal
    braces. Pure-literal files must NOT — otherwise their JSON code
    blocks would render with double braces in the output."""

    def test_phase1_uses_double_braces_for_json(self) -> None:
        """phase1.md goes through .format(); JSON code blocks must use
        {{ / }} so they render as { / } after substitution."""
        raw = (PHASE_PROMPTS_DIR / "phase1.md").read_text(encoding="utf-8")
        # The role-map schema JSON in phase1.md is the load-bearing
        # case. It must contain `{{` (which becomes `{` after format).
        self.assertIn('{{\n  "schema_version"', raw)

    def test_phase3_uses_single_braces_for_json(self) -> None:
        """phase3.md is pure-literal (no substitutions); JSON code
        blocks use single { directly."""
        raw = (PHASE_PROMPTS_DIR / "phase3.md").read_text(encoding="utf-8")
        # The compensation-grid schema JSON in phase3.md uses single
        # braces because we never call .format() on it.
        self.assertIn('{\n  "schema_version": "1.5.2"', raw)


class PhasePromptByteEqualityTests(unittest.TestCase):
    """Council 2026-04-30 P0-2: SHA256 hash regression baseline for
    every rendered phase prompt artifact.

    The hashes below are captured against ``b279d2f`` + the P0
    fix-up commit's apparatus state. Any change to
    ``phase_prompts/*.md`` (or to the loader, or to substitution
    inputs) shifts the hash and trips the matching assertion. To
    update the baseline after an intentional edit, re-capture via
    the snippet in this file's module docstring.

    Coverage: all 13 rendered artifacts — phase1 in both seed modes,
    phase2..6, single_pass in both seed modes, and iteration for
    every strategy in ``next_strategy``'s rotation (gap, unfiltered,
    parity, adversarial)."""

    EXPECTED_HASHES = {
        "phase1_no_seeds_True":  (17081, "5b79a14bae8b11e03e80edf32ea34e457db029e8d41692647247e5725c39cf4e"),
        "phase1_no_seeds_False": (16884, "78f026bcc0c9f39a6225534f191fa1cbc837a9b5a0720ef717ae8160f99ddeb8"),
        "phase2":                ( 2593, "38b3001831f960079a357b3852cc235b5fc6c930c19b2f2ff165d078eb4341b7"),
        "phase3":                ( 8464, "59749f49d2379ce8fd2efdf7a23015a71216cd6041be0360fddbcc167ab1e128"),
        "phase4":                ( 3031, "93f2cb5d8eebfc2b52371866c10c7e0b176dc5203c8b75c6552a4a71e168c978"),
        "phase5":                (10185, "ff1d676111b1c026e80450a6c8bf11ce3236e3335ce8abef52ded023f81b9248"),
        "phase6":                ( 1217, "33f65c1831c49b6c3dabc5ec61d792056bd505dd4bcd22e2d8012aa7fa3862a7"),
        # v1.5.6 BUG-008: SKILL_FALLBACK_GUIDE grew from 4 to 6
        # documented install paths (added .cursor + .continue), so
        # every prompt that interpolates the guide grows by ~86 bytes.
        # Hashes recomputed against the v1.5.6 guide.
        "single_pass_True":      (  457, "77830f3ad7cb4d0bac165afc555c54c48866af1756b01a24f4bfd2e80a940b7a"),
        "single_pass_False":     (  402, "89b9ad80cb42e8b4562926e0d54c86fc272a94e53e061856994646174041116d"),
        "iteration_gap":         (  704, "3c64de3996bfa8e6eadc2dd5772a20420021f5d435a6717b3f95e01fbd536322"),
        "iteration_unfiltered":  (  711, "295a26150c49ab3f3a8095966121f2023a9234d4bf98a07fb2bcc26f6ced8ade"),
        "iteration_parity":      (  707, "75a915adb8a5f2b5cbbad623ddf3c5b62738fd1c443444a48b5be59d461b0491"),
        "iteration_adversarial": (  712, "fd98cc78b4e1864f5932d824318d43fecfa53fe624cb30a3bab6094d6d739220"),
    }

    def _render(self, label: str) -> str:
        if label == "phase1_no_seeds_True":
            return run_playbook.phase1_prompt(no_seeds=True)
        if label == "phase1_no_seeds_False":
            return run_playbook.phase1_prompt(no_seeds=False)
        if label == "single_pass_True":
            return run_playbook.single_pass_prompt(no_seeds=True)
        if label == "single_pass_False":
            return run_playbook.single_pass_prompt(no_seeds=False)
        if label.startswith("iteration_"):
            strategy = label.split("_", 1)[1]
            return run_playbook.iteration_prompt(strategy)
        if label.startswith("phase"):
            phase_num = label[len("phase"):]
            return getattr(run_playbook, f"phase{phase_num}_prompt")()
        raise ValueError(f"unknown artifact label: {label}")

    def test_every_rendered_artifact_matches_expected_hash(self) -> None:
        for label, (expected_len, expected_hash) in self.EXPECTED_HASHES.items():
            with self.subTest(artifact=label):
                body = self._render(label)
                actual_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
                self.assertEqual(
                    len(body), expected_len,
                    f"{label}: byte length drift "
                    f"(expected {expected_len}, got {len(body)}). If the "
                    f"phase prompt was intentionally edited, update "
                    f"EXPECTED_HASHES."
                )
                self.assertEqual(
                    actual_hash, expected_hash,
                    f"{label}: SHA256 drift. If the phase prompt was "
                    f"intentionally edited, update EXPECTED_HASHES with "
                    f"the new hash. New hash: {actual_hash}"
                )

    def test_iteration_strategies_cover_every_rotation_step(self) -> None:
        """Pin that EXPECTED_HASHES covers every strategy in
        ``next_strategy``'s rotation. Adding a new iteration strategy
        without adding its hash would silently leave that prompt
        unprotected."""
        rotation = set()
        s = "gap"
        while s:
            rotation.add(s)
            s = run_playbook.next_strategy(s)
        covered = {
            label[len("iteration_"):]
            for label in self.EXPECTED_HASHES
            if label.startswith("iteration_")
        }
        self.assertEqual(
            rotation, covered,
            f"iteration strategy rotation {rotation} differs from "
            f"hash-pinned set {covered}"
        )


class CursorRunnerStdinPipingTests(unittest.TestCase):
    """v1.5.4 F-1 also ensured the cursor runner pipes the prompt on
    stdin (verified against cursor-cli 3.1.10). Pin the runner-side
    branch so a future refactor can't quietly switch cursor to argv
    passing and hit argv-length limits on long phase prompts."""

    def test_run_prompt_pipes_stdin_for_cursor(self) -> None:
        # The branch under test lives at the run_prompt subprocess
        # call site: runner in ("codex", "cursor") sets
        # run_kwargs["input"] = prompt. We grep for the literal tuple
        # to pin it without booting subprocess.run.
        src = Path(run_playbook.__file__).read_text(encoding="utf-8")
        self.assertIn('runner in ("codex", "cursor")', src)


if __name__ == "__main__":
    unittest.main()
