"""v1.6.0 — differential test: our Markdown model vs a reference parser.

**This test exists to end a loop, and the loop is worth naming.**

The v1.6.0 render contract has to know which lines of a REQUIREMENTS.md are
real Markdown structure and which are quoted material, because a `##` line
inside a code fence is text, not a heading — and a document that gets every
heading quoted can present a flat, incoherent requirement list while the
gate certifies it clean.

`quality_gate._render_blank_fences` is that model. Across five rounds of the
instruction-001 self-Council, it was wrong five times, and each fix was
correct about exactly the shape it had been shown:

    round 3   ``` pairs only              -> fixed ``` pairs
    round 4   ~~~, unclosed, 6-backtick    -> enumerated the fence grammar
    round 5   info-string polarity;        -> ...and HTML block type 1 only,
              HTML blocks                     leaving types 2 and 6 open

Round 5 named the exit condition, and it is not "enumerate harder":

    The exit condition isn't "cover the grammar", it's "check the model
    against an authority." Every bypass in rounds 3-5 was a gap between the
    gate's model of Markdown and Markdown itself.

So this module stops hand-modelling CommonMark and differentially tests the
model against a reference parser. For each case, both must agree on one
question: **does this document contain a real level-2 heading called
"Actors and roles"?** If the reference parser says no and our scanner says
yes, that is a bypass; if the reference says yes and ours says no, that is a
false positive that would fail a correct document.

The dependency is optional: the module skips when no reference parser is
installed, so the suite still runs in a bare environment. It is a
verification aid, not a runtime dependency of the skill — `quality_gate.py`
ships with no third-party imports and must keep it that way.
"""

import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = (
    REPO_ROOT / "plugins" / "quality-playbook" / "skills" / "quality-playbook" / "scripts"
)
sys.path.insert(0, str(SCRIPT_DIR))

import quality_gate  # noqa: E402

try:
    from markdown_it import MarkdownIt
    _MD = MarkdownIt("commonmark")
except ImportError:  # pragma: no cover - environment-dependent
    _MD = None


PROBE_HEADING = "Actors and roles"


def _reference_has_heading(text):
    """Does a reference CommonMark parser see `## Actors and roles`?"""
    tokens = _MD.parse(text)
    for i, tok in enumerate(tokens):
        if tok.type == "heading_open" and tok.tag == "h2":
            inline = tokens[i + 1] if i + 1 < len(tokens) else None
            if inline is not None and inline.content.strip() == PROBE_HEADING:
                return True
    return False


def _our_model_has_heading(text):
    """Does quality_gate's model see `## Actors and roles` as structure?"""
    blanked = quality_gate._render_blank_fences(text)
    for m in re.finditer(r"^##\s+(.+)$", blanked, re.MULTILINE):
        if m.group(1).strip() == PROBE_HEADING:
            return True
    return False


# Each case is a document fragment placed around the probe heading. The
# names describe the construct, not the expected answer — the reference
# parser supplies the expected answer, which is the whole point.
CASES = {
    # --- plain ---------------------------------------------------------
    "bare_heading": f"## {PROBE_HEADING}\n",
    "heading_after_prose": f"Some prose.\n\n## {PROBE_HEADING}\n",
    "heading_first_line": f"## {PROBE_HEADING}\n\ntrailing prose\n",

    # --- backtick fences ------------------------------------------------
    "fence_backtick_3": f"```\n## {PROBE_HEADING}\n```\n",
    "fence_backtick_4": f"````\n## {PROBE_HEADING}\n````\n",
    "fence_backtick_6": f"``````\n## {PROBE_HEADING}\n``````\n",
    "fence_backtick_info": f"```markdown\n## {PROBE_HEADING}\n```\n",
    # B-6: a backtick fence's info string MAY contain tildes.
    "fence_backtick_info_tilde": f"```text~ex\n## {PROBE_HEADING}\n```\n",
    "fence_backtick_closed_longer": f"```\n## {PROBE_HEADING}\n`````\n",
    "fence_backtick_closer_short": f"`````\n## {PROBE_HEADING}\n```\n",
    "fence_backtick_unclosed": f"```\n## {PROBE_HEADING}\n",
    "fence_backtick_indented": f"  ```\n  ## {PROBE_HEADING}\n  ```\n",

    # --- tilde fences ---------------------------------------------------
    "fence_tilde_3": f"~~~\n## {PROBE_HEADING}\n~~~\n",
    "fence_tilde_5": f"~~~~~\n## {PROBE_HEADING}\n~~~~~\n",
    "fence_tilde_info": f"~~~markdown\n## {PROBE_HEADING}\n~~~\n",
    # A tilde fence's info string may contain backticks.
    "fence_tilde_info_backtick": f"~~~`x`\n## {PROBE_HEADING}\n~~~\n",
    "fence_tilde_unclosed": f"~~~\n## {PROBE_HEADING}\n",
    "fence_tilde_closed_by_backtick": f"~~~\n## {PROBE_HEADING}\n```\n",
    "fence_backtick_closed_by_tilde": f"```\n## {PROBE_HEADING}\n~~~\n",

    # --- fences that do NOT contain the heading -------------------------
    "fence_before_heading": f"```\nquoted\n```\n\n## {PROBE_HEADING}\n",
    "fence_after_heading": f"## {PROBE_HEADING}\n\n```\nquoted\n```\n",
    "two_fences_heading_between": (
        f"```\na\n```\n\n## {PROBE_HEADING}\n\n```\nb\n```\n"
    ),
    "fence_containing_fence_lookalike": (
        f"````\n```\n````\n\n## {PROBE_HEADING}\n"
    ),

    # --- HTML blocks ----------------------------------------------------
    "html_pre": f"<pre>\n## {PROBE_HEADING}\n</pre>\n",
    "html_script": f"<script>\n## {PROBE_HEADING}\n</script>\n",
    "html_textarea": f"<textarea>\n## {PROBE_HEADING}\n</textarea>\n",
    "html_div": f"<div>\n## {PROBE_HEADING}\n</div>\n",
    "html_table": f"<table>\n## {PROBE_HEADING}\n</table>\n",
    "html_comment": f"<!--\n## {PROBE_HEADING}\n-->\n",
    "html_div_then_blank_then_heading": (
        f"<div>\nquoted\n</div>\n\n## {PROBE_HEADING}\n"
    ),
    "html_pre_closed_then_heading": (
        f"<pre>\nquoted\n</pre>\n\n## {PROBE_HEADING}\n"
    ),
    "html_pre_single_line_then_heading": (
        f"<pre>x</pre>\n\n## {PROBE_HEADING}\n"
    ),

    # --- indentation / other block contexts ------------------------------
    "indented_code_block": f"    ## {PROBE_HEADING}\n",
    "blockquoted": f"> ## {PROBE_HEADING}\n",
    "list_item": f"- ## {PROBE_HEADING}\n",
}


# Intentional divergences from CommonMark, with justification.
#
# The render contract is deliberately stricter than CommonMark in one
# respect: a §5.2 document part must be a top-level heading, not a heading
# nested inside another block. CommonMark happily parses `> ## Actors` and
# `- ## Actors` as h2; the contract does not accept them as document parts,
# because a spec whose "Actors and roles" section lives inside a blockquote
# or a list item is not the canonical eight-part shape the interview walks.
#
# Both divergences are in the CONSERVATIVE direction — we decline to see a
# heading, so the mandatory-part checks FAIL rather than pass. A stricter
# model cannot produce a bypass here; it can only over-fire, and over-firing
# on this shape is the intended behavior.
#
# Anything NOT listed here must agree with the reference parser. Adding a
# row is a deliberate act that needs a reason, which is the point: it keeps
# "our model is wrong" from being quietly reclassified as "intended".
INTENTIONAL_DIVERGENCES = {
    "blockquoted": "a document part must not be nested in a blockquote",
    "list_item": "a document part must not be nested in a list item",
}


@unittest.skipIf(_MD is None, "no reference CommonMark parser installed")
class FenceModelDifferentialTests(unittest.TestCase):
    """Our structure model must agree with a reference parser."""

    def test_model_agrees_with_reference_parser(self):
        disagreements = []
        for name, body in CASES.items():
            if name in INTENTIONAL_DIVERGENCES:
                continue
            text = f"# Doc\n\n{body}"
            expected = _reference_has_heading(text)
            actual = _our_model_has_heading(text)
            if expected != actual:
                direction = (
                    "BYPASS (we see structure the parser does not)"
                    if actual
                    else "FALSE POSITIVE (we hide structure the parser sees)"
                )
                disagreements.append(f"{name}: {direction}")
        self.assertEqual(
            disagreements, [],
            "quality_gate._render_blank_fences disagrees with a reference "
            "CommonMark parser about which lines are real structure. Each "
            "disagreement is either a bypass (a flat document can pass by "
            "quoting its headings) or a false positive (a correct document "
            "gets failed):\n  " + "\n  ".join(disagreements),
        )

    def test_every_intentional_divergence_still_diverges(self):
        """A divergence that stopped diverging is a stale allowlist row.

        Without this, an allowlist entry silently becomes permission for a
        future model change nobody reviewed.
        """
        for name, reason in INTENTIONAL_DIVERGENCES.items():
            with self.subTest(case=name, reason=reason):
                self.assertIn(name, CASES)
                text = f"# Doc\n\n{CASES[name]}"
                self.assertTrue(
                    _reference_has_heading(text),
                    f"{name}: the reference parser no longer sees a heading "
                    "here, so this row no longer describes a divergence.",
                )
                self.assertFalse(
                    _our_model_has_heading(text),
                    f"{name}: our model now agrees with the reference "
                    "parser, so this allowlist row is stale — delete it.",
                )

    def test_divergences_are_conservative_not_permissive(self):
        """An intentional divergence may never be a bypass.

        Diverging by seeing LESS structure fails a document we do not
        understand. Diverging by seeing MORE would let a flat document pass.
        """
        for name in INTENTIONAL_DIVERGENCES:
            with self.subTest(case=name):
                text = f"# Doc\n\n{CASES[name]}"
                self.assertFalse(
                    _our_model_has_heading(text)
                    and not _reference_has_heading(text),
                    f"{name}: this divergence sees structure the reference "
                    "parser does not — that is a bypass, not a strictness "
                    "choice.",
                )

    def test_the_probe_actually_discriminates(self):
        """Control: the harness must be able to see a real heading.

        Without this, a bug that made `_our_model_has_heading` always return
        False would show up as agreement on most cases.
        """
        self.assertTrue(_reference_has_heading(f"# D\n\n## {PROBE_HEADING}\n"))
        self.assertTrue(_our_model_has_heading(f"# D\n\n## {PROBE_HEADING}\n"))
        self.assertFalse(
            _reference_has_heading(f"# D\n\n```\n## {PROBE_HEADING}\n```\n")
        )
        self.assertFalse(
            _our_model_has_heading(f"# D\n\n```\n## {PROBE_HEADING}\n```\n")
        )

    def test_case_list_covers_the_constructs_that_broke(self):
        """Every construct a self-Council round found must stay covered."""
        for required in (
            "fence_backtick_info_tilde",   # round 5, B-6
            "fence_tilde_3",               # round 4, B-5
            "fence_backtick_unclosed",     # round 4, B-5
            "fence_backtick_closer_short",  # round 4, B-5
            "html_pre",                    # round 5, B-7 (type 1)
            "html_div",                    # round 5, B-7 (type 6)
            "html_comment",                # round 5, B-7 (type 2)
        ):
            with self.subTest(case=required):
                self.assertIn(required, CASES)


class NoThirdPartyImportInTheGateTests(unittest.TestCase):
    """The gate ships to adopters; the reference parser is test-only.

    Runs unconditionally — this invariant matters most in the environment
    where markdown_it is NOT installed.
    """

    def test_quality_gate_does_not_import_a_markdown_library(self):
        source = (SCRIPT_DIR / "quality_gate.py").read_text(
            encoding="utf-8", errors="replace"
        )
        for banned in ("markdown_it", "import commonmark", "import markdown"):
            with self.subTest(module=banned):
                self.assertNotIn(
                    banned, source,
                    f"quality_gate.py must not depend on {banned!r} — it "
                    "ships to adopters with no third-party dependencies. The "
                    "reference parser is a test-time verification aid only.",
                )


if __name__ == "__main__":
    unittest.main()
