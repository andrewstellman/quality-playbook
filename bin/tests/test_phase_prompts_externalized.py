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
        """Phase files phase2..phase6 must remain readable as-is when
        the loader is called with NO substitutions. v1.5.6 BUG-011/012
        added a `{skill_fallback_guide}` placeholder substituted via
        ``str.replace()`` (NOT ``str.format()``) precisely so that
        phase3 / phase5 JSON code blocks can keep using single ``{``
        / ``}`` braces. This test pins the no-substitution contract:
        the loader without any kwargs returns the file verbatim."""
        for n in range(1, 7):
            text = run_playbook._load_phase_prompt(f"phase{n}")
            on_disk = (PHASE_PROMPTS_DIR / f"phase{n}.md").read_text(
                encoding="utf-8"
            )
            self.assertEqual(text, on_disk, f"phase{n} loader drift")

    def test_loader_fallback_guide_uses_replace_not_format(self) -> None:
        """v1.5.6 BUG-011/012: the {skill_fallback_guide} placeholder
        is substituted via ``str.replace()``, BEFORE ``.format()`` is
        invoked, so files that carry it (phase{2..6}) are NOT exposed
        to .format()'s brace-escaping rules. Pin the path: load
        phase3 (which has single-brace JSON code blocks) with ONLY
        the fallback-guide substitution and confirm the JSON braces
        survive unescaped."""
        text = run_playbook._load_phase_prompt(
            "phase3",
            skill_fallback_guide="GUIDE",
        )
        # The replacement happened.
        self.assertIn("GUIDE", text)
        self.assertNotIn("{skill_fallback_guide}", text)
        # And the single-brace JSON survived.
        self.assertIn('{\n  "schema_version": "1.5.2"', text)


class FormatStringEscapingTests(unittest.TestCase):
    """Files that go through .format() must double-escape literal
    braces. Files that go through ONLY str.replace() must NOT —
    otherwise their JSON code blocks would render with double braces
    in the output."""

    def test_phase1_uses_double_braces_for_json(self) -> None:
        """phase1.md goes through .format(); JSON code blocks must use
        {{ / }} so they render as { / } after substitution."""
        raw = (PHASE_PROMPTS_DIR / "phase1.md").read_text(encoding="utf-8")
        # The role-map schema JSON in phase1.md is the load-bearing
        # case. It must contain `{{` (which becomes `{` after format).
        self.assertIn('{{\n  "schema_version"', raw)

    def test_phase3_uses_single_braces_for_json(self) -> None:
        """phase3.md goes through str.replace() only (no .format()),
        so JSON code blocks use single { directly. v1.5.6 BUG-011/012:
        adding the {skill_fallback_guide} placeholder did NOT switch
        phase3 onto the .format() path — the loader's replace-then-
        format ordering keeps phase{2..6} JSON readable."""
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
        # v1.5.6 cluster B: phase1.md replaced its hardcoded 4-path
        # fallback list with the {skill_fallback_guide} placeholder
        # for parity with cluster 5's phase{2..6} work. The substituted
        # guide is the same six-path SKILL_FALLBACK_GUIDE constant used
        # by single_pass / iteration / phase{2..6}; phase1's body grew
        # by ~86 bytes (six-path guide minus the old four-path literal).
        # v1.5.6 cluster 047: phase1.md role_map prompt section
        # rewritten — LLM no longer instructed to compute breakdown +
        # summary; runner does it via normalize_role_map_for_gate
        # before the Phase 2 entry-gate. Schema example collapsed
        # from full role_map to files+provenance. Hashes recomputed.
        # v1.5.6 fix-up 070 NF-3: Gate Self-Check enumeration extended
        # to include check 1 (≥120 lines) — the Council post-fixup
        # review noticed the enumeration started at check 2.
        # (Previous edit was 067 C-3: phase1.md content-guidance block
        # rewritten to teach the SIX exact gate-required section titles
        # + per-section minima from SKILL.md:1257-1273.) Hashes recomputed.
        "phase1_no_seeds_True":  (20262, "bfc066dd37491626fdf9a6ca110a005d72d639e66b00145972981ac7375e929a"),
        "phase1_no_seeds_False": (20065, "d52fb1bc7554fd0c96654f8900ba1c8e239c80f820f6bc33edc5b0960cf0682e"),
        # v1.5.6 BUG-011/012: phase{2..6}.md previously hardcoded
        # `.github/skills/` paths; the fix prepends {skill_fallback_guide}
        # (the same SKILL_FALLBACK_GUIDE constant the iteration/single_pass
        # prompts already substitute) and replaces every hardcoded reference
        # with a layout-agnostic instruction. Hashes recomputed to reflect
        # both the fallback-guide preamble and the rewritten body.
        # v1.5.7 Deliverable 2: cookbook-reference paragraph added to
        # phase2.md after the "Read these files" block, pointing at
        # references/role_map_queries.md. Hashes recomputed (+436 bytes).
        # v1.5.7 fix F-4c (instruction 030): 8 explicit artifact-location
        # REQ directives added to phase2.md so REQUIREMENTS.md carries
        # canonical-path REQs the gate can enforce against
        # (quality/writeups/BUG-<id>.md, quality/patches/, etc.).
        # Hash recomputed (3931 → 5345 bytes).
        # v1.5.7 instruction 032 NCF-3/NCF-14 (the workspace REQ
        # wording was updated from "populated quality/workspace/" to
        # "quality/workspace/ tree present (populated OR empty)" so
        # the REQ matches the F-4 amendment's empty-dir rejection).
        # Hash recomputed (5345 → 5454 bytes). When updating phase
        # prompts: recompute via `python3 -c "import hashlib;
        # from bin import run_playbook; b=run_playbook.phaseN_prompt();
        # print(len(b), hashlib.sha256(b.encode()).hexdigest())"`.
        # v1.5.7 instruction 037 (UX defect closure): mandatory
        # "## What just happened" + "### What to do next" tail
        # appended to every phase prompt (phase1-6 + single_pass +
        # iteration). Pointer to references/what_just_happened.md
        # added; per-phase template hint (State P<N>, State C, State
        # G, State S, State B, State I, State F) included so the
        # agent picks the right decision-tree branch without inlining
        # the tree. All hashes recomputed. Note: the `expected_len`
        # column is the Unicode codepoint count (matches the test's
        # `len(body)`), NOT the UTF-8 byte length — multi-byte
        # characters like the em-dash `—` count as 1 codepoint but
        # take 3 bytes in UTF-8.
        # v1.5.7 instruction 046 (A-3): SKILL_FALLBACK_GUIDE expanded
        # 6 → 10 install layouts (codex/windsurf/cline/aider). Every
        # prompt that interpolates the guide grew by 167 codepoints;
        # phase5/phase6 grew more (+370) because they ALSO carry the
        # gate-location enumeration which gained the 4 new
        # quality_gate.py paths. All hashes recomputed — this baseline
        # update IS the sanctioned change-acknowledgement signal.
        # v1.5.7 instruction 047 Item 3 (A-5): phase1.md gained the
        # Asymmetry-Promotion Rule + confirmation-checklist item 7;
        # phase2.md gained the asymmetry-promotion backstop paragraph.
        # phase1/phase2 hashes recomputed; phase3-6 + single_pass +
        # iteration unchanged (each prompt is its own file).
        # v1.5.7 instruction 057 (A-13): phase6.md Step 6.2 gained the
        # MANDATORY gate-verdict-witness + "No PASS without N=0 FAILs"
        # contract (the credibility-defect closure — agent must quote
        # the gate's Total:/RESULT: lines verbatim). phase6 hash
        # recomputed (3035 → 4495 codepoints); phase1-5 + single_pass
        # + iteration unchanged. This baseline update IS the sanctioned
        # change-acknowledgement signal.
        # v1.5.7 instruction 065 (A-14 + A-15 + A-16): the
        # phase-boundary artifact-contract validator
        # (bin/validate_phase_artifacts.py) MANDATE was wired into
        # the phase prompts. phase1.md gained the Mode-A
        # normalize_role_map_for_gate + --phase 1 validator-witness
        # block (A-16 — Mode A has no runner to normalize breakdown);
        # phase2.md gained the --phase 2 MANDATORY validation block
        # (A-14 manifest §1.6 wrappers); phase5.md gained the
        # explicit "Write quality/INDEX.md" §11 emission STEP +
        # --phase 5 validator (A-15 — Mode A has no runner to emit
        # INDEX.md); phase6.md gained the --phase 6 re-validation +
        # gate_verdict-value witness. phase3/phase4/single_pass/
        # iteration were NOT edited (their hashes are unchanged).
        # Hashes recomputed — this baseline update IS the sanctioned
        # change-acknowledgement signal.
        # v1.5.7 instruction 067 F2 (closing the 065 codex HALT):
        # the validator-witness mandate wording in phase{1,2,5,6}.md
        # changed from the unsatisfiable "quote its final exit-code
        # line verbatim" to "quote its final `RESULT:` line verbatim
        # (it matches `RESULT: VALIDATION PASSED (phase N)` or
        # `RESULT: VALIDATION FAILED (phase N — X FAIL, Y PASS)` …)"
        # now that bin/validate_phase_artifacts.py emits a literal
        # self-authenticating RESULT line. phase3/phase4/single_pass/
        # iteration were NOT edited (their hashes are unchanged).
        # Hashes recomputed — this baseline update IS the sanctioned
        # change-acknowledgement signal.
        # v1.5.7 instruction 089b F13a: phase1.md gained the
        # NON-OPTIONAL Phase-1 validator-invocation mandate (run
        # validate_phase_artifacts --phase 1 + quote the verbatim
        # RESULT line; Stage: annotation requirement w/ syntax
        # example matching the run_state_lib parser; HALT clause for
        # can't-invoke runtimes) — closes the 2026-05-18 codex
        # desktop "reported Phase 1 PASS against a non-compliant
        # EXPLORATION.md" gap (F13). phase1 codepoint length
        # 24719→27026 (no_seeds_True) / 24522→26829 (no_seeds_False).
        # phase2-6/single_pass/iteration UNCHANGED (089b touched only
        # phase1.md among the run_playbook-rendered prompts; the F11
        # references/phase{1,2}_guide.md edits are NOT
        # run_playbook-rendered and carry no EXPECTED_HASHES entry).
        # Hashes recomputed — this baseline update IS the sanctioned
        # change-acknowledgement signal.
        # v1.5.7 090k: phase1.md gained the run-start attribution
        # banner directive so channel-installed Mode A agents see
        # it (the openfga-run3 dogfood found no banner emitted).
        # 090l rewrote that directive (condensed→full, skill-load
        # anchor). v1.5.7 090m REMOVED the directive entirely:
        # root-cause analysis showed SKILL.md (the file actually
        # read at skill-load) is the correct surface; phase1.md +
        # AGENTS.md were the wrong place all along. With the
        # directive removed, the hashes return to their pre-090k
        # baseline (27026 no_seeds_True, 26829 no_seeds_False).
        "phase1_no_seeds_True":  (27026, "42010af537fa2d1bde614f791e2bd5a2b82b506a4d43cfa1b69f04268533d605"),
        "phase1_no_seeds_False": (26829, "daf228a20f85f5a65ef6efaaa3b8acc7457d27313bff5c555d3a85cbc70de1eb"),
        # v1.5.7 instruction 073 Item-4 (A-19): phase2.md gained the
        # httpx-2026-05-17 missing-manifests warning (validator now
        # FAILs on ABSENT manifests, not just wrong-shape; agent must
        # WRITE missing manifests per schemas.md §6/§7/§8). Hash
        # recomputed. phase1/phase5/phase3/phase4/single_pass/
        # iteration UNCHANGED.
        # v1.5.7 instruction 080 (W4): verify.sh → verify.py across
        # references/ + phase_prompts/; the non-substitution invariant
        # prose rewritten (verify.py must subprocess the ORIGINAL
        # shell pipeline — Python reimplementation FORBIDDEN, v1.3.23
        # invariant preserved). phase2.md gained the verify.py
        # orchestrator/invariant wording in the Phase-2a mechanical
        # block + the canonical-artifact REQ (verify.sh → verify.py);
        # phase5.md step 6 verify.sh → `python … verify.py`. phase2
        # hash recomputed (9910 → 10096 codepoints); phase5 (16080 →
        # 16089). phase6_auditor.md was ALSO edited (verify.py +
        # non-substitution prose at its mechanical-verify step) but
        # carries NO EXPECTED_HASHES entry (it is not a
        # run_playbook-rendered prompt — see the 071 note above).
        # phase6.md was NOT modified (it has no verify.sh reference —
        # the instruction-080 :7/:18 citation was stale; verify-
        # before-claim). phase1/phase3/phase4/single_pass/iteration
        # UNCHANGED. Hashes recomputed — this baseline update IS the
        # sanctioned change-acknowledgement signal.
        # v1.5.7 instruction 085 (A-22 TTY hardening side-deliverable):
        # phase3.md + phase5.md gained a RECOMMENDED (not required)
        # disposable-`git worktree` RED→GREEN guidance paragraph (the
        # 2026-05-18 Claude Code cobra run demonstrated it). phase3
        # codepoint length 9778 → 10969; phase5 16089 → 16790.
        # phase1/phase2/phase4/phase6/single_pass/iteration UNCHANGED
        # (each prompt is its own file; 085 touched only phase3/phase5).
        # Hashes recomputed — this baseline update IS the sanctioned
        # change-acknowledgement signal.
        # v1.5.7 instruction 089o (#329): phase5.md step 4 (the TDD
        # red-green cycle) gained the probe-first contract — probe
        # the test runner FIRST and capture quality/results/
        # phase5_env.log; a RED/GREEN tag asserts real execution
        # (a by-inspection prediction under it is an overclaim that
        # FAILs the gate); NOT_RUN only with a non-zero probe whose
        # output is quoted. phase5 codepoint length 16790 → 17635.
        # v1.5.7 instruction 089p (#329 follow-up): phase5.md step 4
        # gained the online-resolution steer — run the test runner
        # in default ONLINE mode (no pre-emptive -o/--offline),
        # retry online before concluding, record NOT_RUN only on a
        # captured ONLINE failure. phase5 codepoint length
        # 17635 → 18254. phase1/2/3/4/6/single_pass/iteration
        # UNCHANGED (089o + 089p touched only phase5 among the
        # run_playbook-rendered prompts; references/iteration.md +
        # references/phase2_generation_guide.md were also edited
        # but those are NOT run_playbook-rendered prompts and carry
        # no EXPECTED_HASHES entry). Hash recomputed — this
        # baseline update IS the sanctioned change-acknowledgement
        # signal.
        # v1.5.7 191 FINDING-50: schemas.md prose citations stripped (kind-B)
        # and rewritten (kind-C). Hash recomputed.
        "phase2":                (10114, "4ad72d9beb4b0cb229b92324554de0e5eafc602c5733dd337b3590484a98a022"),
        # v1.5.7 090j: phase3.md + phase4.md gained the triage
        # precision-guardrail pointers (D1 reachability_analysis on
        # HIGH/MED bugs + D2 KNOWN-ISSUE classification for advisory-
        # only findings + D3 security-HIGH bar via cve_version_applies).
        # phase3: 10969 → 12167 codepoints; phase4: 3911 → 4398.
        # Hashes recomputed.
        # v1.5.7 191 FINDING-50: schemas.md prose citations stripped/rewritten.
        "phase3":                (12047, "5d06b2ff3f5d5b602b79f4cec7afb0853723e641a03efb7d8583edc68cb718ce"),
        "phase4":                ( 4475, "b4c4dd6a103cbfe71d5f136b1a2bc5ebdf136125ec276e8a9c84129620b9c289"),
        # v1.5.7 090g: phase5.md gained the explicit apply→run→
        # revert green-cycle block. v1.5.7 090o: phase5.md gained
        # the build-prep paragraph (Keto cold-cache fix:
        # go mod download / npm ci / pip install / cargo fetch /
        # Maven offline) + the environment-failure remediation
        # paragraph (don't degrade silently — emit specific fix
        # commands and re-run-Phases-5-6 guidance) + THE LOAD-
        # BEARING GUARD (an assertion failure is a RED, not an
        # environment failure — never launder a real RED via the
        # remediation/skip path). Codepoints 21004 → 25914;
        # hash recomputed.
        # v1.5.7 191 FINDING-50: schemas.md prose citations stripped/rewritten.
        "phase5":                (25874, "73ec995d76e142939f03ee70fe226cf5ff7629ac468e27ba3490928409ca2056"),
        # v1.5.7 instruction 071 (A-13 hybrid): phase6.md rewritten
        # for fresh-context sub-agent delegation of Phase 6
        # verification (principled A-17 exception). The old inline
        # Step-6.x gate-invocation body was replaced with Part A
        # (MANDATORY sub-agent spawn + virtio/express/httpx citation
        # + fresh-chat fallback) + Part B (paste the auditor's
        # verbatim GATE/VALIDATOR WITNESS + AUDITOR VERDICT). The
        # gate-invocation/witness/validator logic now canonically
        # lives in the NEW phase_prompts/phase6_auditor.md (which is
        # NOT a run_playbook-rendered prompt, so it carries no
        # EXPECTED_HASHES entry). phase1/2/5/phase3/phase4/
        # single_pass/iteration are UNCHANGED. Hash recomputed —
        # this baseline update IS the sanctioned
        # change-acknowledgement signal.
        # v1.5.7 instruction 073 Item-2 (071 codex F2 fix): phase6.md
        # gained an explicit environment-based Mode A vs Mode B
        # branch BEFORE the STRUCTURAL sub-agent mandate — a Mode B
        # per-phase CLI subprocess is already an isolated fresh
        # context and executes verification directly (no nested
        # sub-agent), so the 071 mandate no longer leaks into Mode B.
        # Hash recomputed (071 value 5411 → 6795).
        # v1.5.7 instruction 087 (A-27): phase6.md gained the
        # NON-OPTIONAL sub-agent-delegation framing (in-session
        # verification is the FAILURE mode this contract closes, not a
        # fallback; codex-class runtimes must STOP-and-ASK if dispatch
        # needs operator approval) — closes the 2026-05-18 codex
        # desktop "delegation wasn't explicitly authorized so I
        # verified in-session" misread. phase6 codepoint length
        # 6795 → 7868. phase1/2/3/4/5/single_pass/iteration UNCHANGED
        # (each prompt is its own file; 087 touched only phase6).
        # Hash recomputed — this baseline update IS the sanctioned
        # change-acknowledgement signal.
        # v1.5.7 instruction 089c (F15): phase6.md gained the
        # three-state verdict contract — the GATE WITNESS block now
        # shows all three RESULT: lines (PASSED / PASSED WITH CLEANUP
        # NEEDED / FAILED), a "Three-state verdict" mapping para, the
        # AUDITOR VERDICT three-state mapping (PASS / PASS WITH
        # CLEANUP NEEDED / FAIL), and the retired "No PASS without
        # N=0 FAILs" rule restated as "No PASS/PASS-WITH-CLEANUP if
        # any substantive FAILs" (Mode-B + Part-A rule-name pointers
        # updated to match). phase6 codepoint length 7868 → 9017.
        # phase1/2/3/4/5/single_pass/iteration UNCHANGED (each prompt
        # is its own file; 089c touched only phase6 among the
        # run_playbook-rendered prompts — phase6_auditor.md /
        # what_just_happened.md / phase6_verify_guide.md are NOT
        # run_playbook-rendered and carry no EXPECTED_HASHES entry).
        # Hash recomputed — this baseline update IS the sanctioned
        # change-acknowledgement signal.
        # v1.5.7 instruction 089d (F17): phase6.md gained one
        # sentence-internal extension at :54 — the gate_verdict enum
        # citation in the "auditor reward shape" parenthetical grew
        # from `pass`/`partial`/`fail` to `pass`/`pass-with-cleanup`/
        # `partial`/`fail` (adding the new schemas.md §11 enum value
        # for the 089c three-state cleanup-needed outcome that 089d
        # F17 now wires through to the INDEX gate_verdict). phase6
        # codepoint length 9017 → 9152. phase1-5/single_pass/iteration
        # UNCHANGED (089d-F17 touched only phase6 among the
        # run_playbook-rendered prompts). Hash recomputed — this
        # baseline update IS the sanctioned change-acknowledgement
        # signal.
        # v1.5.7 191 FINDING-50: schemas.md prose citations stripped/rewritten.
        "phase6":                ( 9151, "b64921d1ea22c3c777e7cc244fe9795917c33b43a44ebea58f2ea166c24e2017"),
        # v1.5.6 BUG-008: SKILL_FALLBACK_GUIDE grew from 4 to 6
        # documented install paths (added .cursor + .continue), so
        # every prompt that interpolates the guide grows by ~86 bytes.
        # Hashes recomputed against the v1.5.6 guide.
        # v1.5.7 instruction 038 codex review fix-up: single_pass.md
        # State-C wording narrowed to "Phase 1 boundary only" so the
        # single-pass run doesn't tell the agent to use State C at
        # later boundaries in a code-only run. P2-P5 template names
        # now explicit instead of "State P<N>" string. Hashes
        # recomputed (codepoint length).
        "single_pass_True":      ( 1415, "8bb2dc58c3469238b46fe83586906ad7c1440e276c8d81740d94d33c673c0c7b"),
        "single_pass_False":     ( 1360, "61d57056eb437c429efa7f397078bc3089165fb4f9db3a9fa51476367945e282"),
        # v1.5.7 instruction 038 codex round-2 fix-up: iteration.md
        # tail rewritten to point at PROGRESS.md `## Iteration:
        # <strategy> complete` headings (and at Rules 4-5 of the
        # decision-tree classifier) instead of the round-1 wording
        # that still referenced non-existent `iteration_end` events
        # in `quality/run_state.jsonl`. Hashes recomputed.
        "iteration_gap":         ( 1933, "47c649e392816795627242895350d49d652d3eca573a60b6b8f145b664a29582"),
        "iteration_unfiltered":  ( 1961, "a027c3038927b2a202b97c82e168f660c0897ee3e3e945340d1bf3342f86bdc5"),
        "iteration_parity":      ( 1945, "1062def6c280ebedfa9ff52df3b3ff6faa35b3526858aabe516852e0d25533b3"),
        "iteration_adversarial": ( 1965, "f72e5363772322466111aeebc34354e4e37097ba69d373d622390f80a4159358"),
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

    def test_iteration_prompts_direct_agent_to_load_iteration_reference(self) -> None:
        """v1.5.7 BUG-006 bite: every iteration prompt must direct the
        agent to read `references/iteration.md` before running the
        strategy. Pre-fix the iteration prompt only mentioned the
        strategy name; an agent that hadn't already loaded the
        iteration reference missed strategy-specific protocol
        (which artifacts to consult, what to surface, what NOT to
        touch). Each of the four strategy rotations must carry the
        directive."""
        from bin import run_playbook
        for strategy in ("gap", "unfiltered", "parity", "adversarial"):
            with self.subTest(strategy=strategy):
                body = run_playbook.iteration_prompt(strategy)
                self.assertIn(
                    "references/iteration.md", body,
                    f"iteration_{strategy} prompt must direct agent to "
                    f"read references/iteration.md; got: {body!r}",
                )


class PhasePromptHardcodedPathRegressionTests(unittest.TestCase):
    """v1.5.6 BUG-011/012: phase{2..6}.md previously hardcoded
    ``.github/skills/SKILL.md``, ``.github/skills/references/...``,
    ``.github/skills/quality_gate.py``, and
    ``.github/skills/quality_gate/`` paths. Adopters who installed to
    ``.claude/skills/quality-playbook/``, ``.cursor/skills/quality-playbook/``,
    or ``.continue/skills/quality-playbook/`` got prompts whose Read /
    invoke commands pointed nowhere, breaking phases 2-6 silently.

    The fix substitutes ``{skill_fallback_guide}`` (the same ten-layout
    fallback prose used by single_pass / iteration prompts) and rewrites
    every hardcoded reference to either layout-agnostic prose or an
    enumeration of all ten canonical layouts (v1.5.7 instruction 046
    A-3 expanded 6 → 10: codex / windsurf / cline / aider).

    These tests guard against regression in two directions: any future
    edit reintroducing a single-layout hardcode (e.g.
    ``.github/skills/SKILL.md``) trips ``test_no_phase_prompt_hardcodes_single_layout``,
    and any future edit that drops the substitution wiring trips
    ``test_phase_prompts_substitute_full_fallback_guide``.
    """

    # v1.5.7 instruction 046 (A-3): 6 → 10 canonical layouts.
    SIX_CANONICAL_LAYOUTS = (
        "SKILL.md",
        ".claude/skills/quality-playbook/SKILL.md",
        ".github/skills/SKILL.md",
        ".cursor/skills/quality-playbook/SKILL.md",
        ".continue/skills/quality-playbook/SKILL.md",
        ".github/skills/quality-playbook/SKILL.md",
        ".codex/skills/quality-playbook/SKILL.md",
        ".windsurf/skills/quality-playbook/SKILL.md",
        ".cline/skills/quality-playbook/SKILL.md",
        ".aider/skills/quality-playbook/SKILL.md",
    )

    SIX_GATE_LAYOUTS = (
        "quality_gate.py",
        ".claude/skills/quality-playbook/quality_gate.py",
        ".github/skills/quality_gate.py",
        ".cursor/skills/quality-playbook/quality_gate.py",
        ".continue/skills/quality-playbook/quality_gate.py",
        ".github/skills/quality-playbook/quality_gate.py",
        ".codex/skills/quality-playbook/quality_gate.py",
        ".windsurf/skills/quality-playbook/quality_gate.py",
        ".cline/skills/quality-playbook/quality_gate.py",
        ".aider/skills/quality-playbook/quality_gate.py",
    )

    @staticmethod
    def _render_phase_prompt(n: int) -> str:
        """phase1_prompt requires a no_seeds kwarg; phase{2..6} take
        no args. v1.5.6 cluster B: phase1 was widened to use the
        {skill_fallback_guide} placeholder so this test surface now
        covers all six phase prompts. Centralize the phase-1 special
        case here."""
        from bin import run_playbook
        if n == 1:
            return run_playbook.phase1_prompt(no_seeds=True)
        return getattr(run_playbook, f"phase{n}_prompt")()

    def test_phase_prompts_substitute_full_fallback_guide(self) -> None:
        """Every phase{1..6}_prompt() output must contain the verbatim
        SKILL_FALLBACK_GUIDE string — i.e., the prompt drops the
        runtime-canonical fallback list into the LLM's context as a
        single block. Without this substitution, the prompt's bare
        references to ``SKILL.md`` and ``references/`` would be
        ambiguous to the LLM. Cluster 5 widened phase{2..6}; cluster
        B widened phase1 for parity."""
        from bin import run_playbook

        for n in range(1, 7):
            with self.subTest(phase=n):
                body = self._render_phase_prompt(n)
                self.assertIn(
                    run_playbook.SKILL_FALLBACK_GUIDE, body,
                    f"phase{n}_prompt() did not substitute "
                    f"SKILL_FALLBACK_GUIDE. The {{skill_fallback_guide}} "
                    f"placeholder must appear at the top of phase{n}.md "
                    f"and phase{n}_prompt() must pass "
                    f"skill_fallback_guide=SKILL_FALLBACK_GUIDE to the "
                    f"loader. (BUG-011/012 regression.)"
                )
                # Placeholder must NOT survive into the rendered prompt.
                self.assertNotIn(
                    "{skill_fallback_guide}", body,
                    f"phase{n}_prompt() left the literal "
                    f"{{skill_fallback_guide}} placeholder unsubstituted "
                    f"— the loader/wiring is broken."
                )

    def test_no_phase_prompt_hardcodes_single_layout(self) -> None:
        """No phase{2..6}_prompt() body may contain a single-layout
        ``.github/skills/`` path that does NOT also enumerate the
        five other canonical layouts in the same prose neighborhood.

        We enforce this with a per-line check: every line containing
        ``.github/skills/`` must ALSO contain at least three of the
        other five canonical layout markers. The fallback-guide
        sentence and the gate-resolution prose both list all ten —
        any future single-layout hardcode (one ``.github/skills/SKILL.md``
        on a line with no other layout) trips this test."""
        from bin import run_playbook

        # All non-`.github/skills/` layout markers — at least 3 of these
        # must co-occur with `.github/skills/` for the line to be a
        # legitimate fallback-list enumeration rather than a hardcode.
        peer_layouts = (
            ".claude/skills/quality-playbook/",
            ".cursor/skills/quality-playbook/",
            ".continue/skills/quality-playbook/",
            ".github/skills/quality-playbook/",
        )
        for n in range(1, 7):
            with self.subTest(phase=n):
                body = self._render_phase_prompt(n)
                # Strip the SKILL_FALLBACK_GUIDE block from analysis —
                # it's the canonical ten-layout enumeration and is
                # supposed to mention `.github/skills/`. Any remaining
                # `.github/skills/` reference must itself be an
                # enumeration of all ten layouts.
                stripped = body.replace(run_playbook.SKILL_FALLBACK_GUIDE, "")
                for line_no, line in enumerate(stripped.splitlines(), start=1):
                    if ".github/skills/" not in line:
                        continue
                    peer_hits = sum(1 for marker in peer_layouts if marker in line)
                    self.assertGreaterEqual(
                        peer_hits, 3,
                        f"phase{n}_prompt() line {line_no} contains a "
                        f"`.github/skills/` reference without enumerating "
                        f"≥3 other canonical layouts. This looks like a "
                        f"single-layout hardcode (BUG-011/012 regression). "
                        f"Line: {line!r}"
                    )

    def test_phase_prompts_enumerate_all_ten_skill_layouts(self) -> None:
        """The substituted fallback guide must enumerate all ten
        canonical SKILL.md install layouts. Pin them by string match
        against phase{2..6}_prompt() outputs. A future edit that
        accidentally narrows SKILL_FALLBACK_GUIDE (e.g., dropping
        `.cursor/`) is caught here."""
        from bin import run_playbook

        for n in range(1, 7):
            with self.subTest(phase=n):
                body = self._render_phase_prompt(n)
                for layout in self.SIX_CANONICAL_LAYOUTS:
                    self.assertIn(
                        layout, body,
                        f"phase{n}_prompt() does not mention the "
                        f"{layout!r} install layout. The fallback "
                        f"guide must enumerate all ten adopter layouts."
                    )

    def test_phase5_and_phase6_enumerate_all_ten_gate_layouts(self) -> None:
        """Phase 5 (cardinality gate) invokes quality_gate.py inline
        and must enumerate all ten canonical gate-script locations.

        v1.5.7 instruction 071 (A-13 hybrid): Phase 6's gate
        invocation moved OUT of phase6.md into the fresh-context
        auditor sub-agent prompt (`phase_prompts/phase6_auditor.md`)
        — phase6.md now spawns the sub-agent rather than invoking
        the gate itself, so the ten-layout gate enumeration
        canonically lives in the auditor prompt. Both surfaces must
        still let the LLM resolve the gate from any install layout,
        not just `.github/skills/`. (Pin updated in-commit per the
        instruction-067 precedent for instruction-directed
        relocations; the requirement is unchanged — only its
        location moved.)"""
        from bin import run_playbook

        phase5_body = run_playbook.phase5_prompt()
        for layout in self.SIX_GATE_LAYOUTS:
            self.assertIn(
                layout, phase5_body,
                f"phase5_prompt() does not mention the {layout!r} "
                f"gate-script location. Phase 5 must enumerate all "
                f"ten canonical quality_gate.py locations."
            )
        auditor = (PHASE_PROMPTS_DIR / "phase6_auditor.md").read_text(
            encoding="utf-8"
        )
        for layout in self.SIX_GATE_LAYOUTS:
            self.assertIn(
                layout, auditor,
                f"phase6_auditor.md does not mention the {layout!r} "
                f"gate-script location. Post-071 the Phase 6 gate "
                f"invocation lives in the auditor sub-agent prompt; "
                f"it must enumerate all ten canonical "
                f"quality_gate.py locations."
            )

    def test_phase_prompts_drop_old_invocation_pattern(self) -> None:
        """The pre-fix Phase 5 prompt invoked the cardinality gate via
        ``sys.path.insert(0, '.github/skills/quality_gate')``. The
        post-fix prompt invokes ``python3 <resolved_quality_gate_path> .``
        instead — running the gate as a script naturally executes
        the cardinality check (it's part of the standard pass).
        Pin that the brittle ``sys.path.insert`` pattern is gone."""
        from bin import run_playbook

        for n in range(1, 7):
            with self.subTest(phase=n):
                body = self._render_phase_prompt(n)
                self.assertNotIn(
                    "sys.path.insert(0, '.github/skills/quality_gate')",
                    body,
                    f"phase{n}_prompt() still uses the brittle "
                    f"`sys.path.insert(0, '.github/skills/quality_gate')` "
                    f"pattern. It must be replaced with the layout-"
                    f"agnostic `python3 <resolved_quality_gate_path> .` "
                    f"invocation."
                )


class AsymmetryPromotionRuleTests(unittest.TestCase):
    """v1.5.7 instruction 047 Item 3 (A-5): the Phase-1→Phase-2
    promotion gap fix. A noticed architectural asymmetry in
    EXPLORATION.md prose must become a multi-site `Pattern:`-tagged
    REQ; otherwise the v1.5.2 compensation-grid BUG-default has no
    cells and the asymmetry never produces BUGs in Phase 3 (the
    v1.5.1 RING_RESET / v1.5.7 virtio gap)."""

    def test_phase1_prompt_directs_asymmetry_to_REQ(self) -> None:
        """Phase 1 prompt must carry the Asymmetry-Promotion Rule +
        confirmation-checklist item bridging noticed-asymmetry prose
        to a multi-site Pattern:-tagged REQ.

        Mutation-test evidence (in-tree per
        ai_context/DEVELOPMENT_PROCESS.md:152-160): deleting the
        'MANDATORY ASYMMETRY-PROMOTION RULE' heading block from
        phase_prompts/phase1.md makes both assertions fire; restoring
        it passes. Bite verified during instruction 047 development.
        """
        from bin import run_playbook
        body = run_playbook.phase1_prompt(no_seeds=True)
        self.assertIn(
            "MANDATORY ASYMMETRY-PROMOTION RULE", body,
            "phase1 prompt must carry the Asymmetry-Promotion Rule "
            "heading (A-5)",
        )
        self.assertIn(
            "escalate, do not demote to prose", body,
            "phase1 prompt must direct noticed asymmetries to a "
            "multi-site Pattern:-tagged REQ (escalate-not-demote rule)",
        )
        # Confirmation-checklist item 7 pins it for self-attestation.
        self.assertIn(
            "no noticed asymmetry was demoted to prose without a REQ",
            body,
            "phase1 confirmation checklist must include the "
            "asymmetry-promotion attestation (item 7)",
        )

    def test_phase2_prompt_directs_pattern_tag_for_compensation(self) -> None:
        """Phase 2 prompt must carry the asymmetry-promotion backstop
        instructing a scan of EXPLORATION.md prose for un-promoted
        compensation/parity asymmetries.

        Mutation-test evidence: deleting the 'Asymmetry-promotion
        backstop' paragraph from phase_prompts/phase2.md makes this
        assertion fire; restoring it passes. Bite verified.
        """
        from bin import run_playbook
        body = run_playbook.phase2_prompt()
        self.assertIn(
            "Asymmetry-promotion backstop", body,
            "phase2 prompt must carry the asymmetry-promotion backstop "
            "(A-5)",
        )
        self.assertIn(
            "scan EXPLORATION.md prose for compensation/parity framing",
            body,
            "phase2 backstop must direct a prose scan for "
            "un-promoted asymmetries",
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
