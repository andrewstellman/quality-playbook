"""v1.5.7 089d (F20) — cross-module pin: the plaintext-extension set
must be a single authoritative constant across all three surfaces
that ingest / mirror / classify `reference_docs/` content.

Pre-089d three modules each defined their own:
  - bin/reference_docs_ingest.SUPPORTED_EXTENSIONS         (authoritative — includes .rst)
  - bin/run_playbook._REFERENCE_DOCS_PLAINTEXT_EXTS         (omitted .rst)
  - bin/bootstrap_self_audit_docs.PLAINTEXT_EXTENSIONS      (omitted .rst)

The drift caused .rst documents under `reference_docs/` to be
classified inconsistently depending on which surface processed them
(opus bootstrap BUG-016 / BUG-017 / BUG-018). F20 makes
`reference_docs_ingest.SUPPORTED_EXTENSIONS` the single source of
truth; the other two re-export it.

This test asserts the three references point at the SAME object
(identity check, not just equality), which catches the case where
a future maintainer reintroduces a local literal.
"""

from __future__ import annotations

import unittest


class ReferenceDocsPlaintextExtensionsPinTests(unittest.TestCase):

    def test_three_surfaces_share_one_authoritative_constant(self) -> None:
        """All three reference_docs/ plaintext-extension consumers
        resolve to the same frozenset object (identity, not just
        equality).

        Mutation-test evidence (ai_context/DEVELOPMENT_PROCESS.md:
        152-160), instruction-089d F20:
          Mutation: in bin/run_playbook.py, revert
          `_REFERENCE_DOCS_PLAINTEXT_EXTS =
          reference_docs_ingest.SUPPORTED_EXTENSIONS` back to the
          local literal `frozenset({".txt", ".md"})` (the pre-089d
          buggy form, omitting .rst).
          Expected failure: THIS test fails — the local literal is
          a different object than reference_docs_ingest's frozenset
          AND drops `.rst`, so both `assertIs` and the
          `.rst`-membership assertion fail.
          Restoration: re-import; test passes. Bite executed during
          089d development; PASS→FAIL→PASS confirmed
          (__pycache__ purged between mutate and restore).
        """
        from bin import bootstrap_self_audit_docs as bsad
        from bin import reference_docs_ingest
        from bin import run_playbook

        canonical = reference_docs_ingest.SUPPORTED_EXTENSIONS

        # `.rst` MUST be in the canonical set (the entire reason F20
        # exists — the local literals were dropping it).
        self.assertIn(
            ".rst", canonical,
            "reference_docs_ingest.SUPPORTED_EXTENSIONS must include "
            "'.rst' — the canonical reference_docs/ plaintext-extension "
            "set per F20.",
        )

        # run_playbook + bootstrap must point at the canonical
        # frozenset (identity check — a local literal would be a
        # different object even with matching contents).
        self.assertIs(
            run_playbook._REFERENCE_DOCS_PLAINTEXT_EXTS, canonical,
            "bin/run_playbook._REFERENCE_DOCS_PLAINTEXT_EXTS must be "
            "the same object as reference_docs_ingest.SUPPORTED_EXTENSIONS "
            "(F20 cross-surface pin). If you see this fail, a local "
            "literal was reintroduced — replace it with the import.",
        )
        self.assertIs(
            bsad.PLAINTEXT_EXTENSIONS, canonical,
            "bin/bootstrap_self_audit_docs.PLAINTEXT_EXTENSIONS must "
            "be the same object as reference_docs_ingest."
            "SUPPORTED_EXTENSIONS (F20 cross-surface pin).",
        )


if __name__ == "__main__":
    unittest.main()
