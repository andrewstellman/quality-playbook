"""v1.6.0 Feature G (Design §8a) — dump-and-go documentation classification.

The operator dumps *any* documentation into one folder; ingest classifies each
file **by content** into citable (Tier 1/2) vs background (Tier 4) — no required
``cite/`` pre-sorting. Classification is an AI judgment (the derivation agent is
the classifier), but it runs **over a deterministic mechanical floor** that the
LLM cannot override upward. The floor is the security-critical part, and it
enforces **only hard, unambiguous, structural facts** — fuzzy genre/intent
judgments belong to the LLM (instruction 023 / Fable simplification review). The
cardinal rule the review sharpened: **nothing becomes citable on content-sniffing
alone** — promotion is the integrity-affecting direction, so a doc reaches citable
only via an extension-class or anchored-signature hard signal, (disclosed) LLM
classification, or an **operator-authored file** (the ``qpb_promote.txt`` sidecar,
the instr-025 advisory rescue, the instr-030 classification-review decision).
*(That last clause was missing until instruction 032: this rule predated instr 025
and 030 and still named only two routes, and it is the source both self-Council
panelists traced three separate wrong "how does a doc become citable" lists back
to. The security claim is unchanged — every route is either a hard mechanical
signal, the disclosed classifier, or a human on file; document content is none of
them.)*

* **Advisory floor (mechanical, first, content-keyed) — HARD signals only.** A
  CVE/GHSA identifier or an advisory URL forces **Tier 4**, matched anywhere in
  content. Nothing promotes a floored advisory — not the LLM, not an extension
  carve-out, not the operator sidecar. Runs *before* the contract carve-out, so a
  CVE advisory renamed ``api.proto`` is still floored by its content. Fuzzy
  genre signals — a hardening/best-practices/advisory TITLE, or high MUST/SHALL
  normative density — are **no longer floors**: a title is a hard string but
  title→genre is a judgment, and a formal spec is normative-dense *by
  definition*, so a density floor floors specifications as a class. They are
  recorded as **advisory hints** on the record and fed to the LLM classifier as
  demotion inputs (``advisory_genre_hints``); they inform, they do not decide.
* **Implementation-source floor — extension only.** A code *extension*
  (``.c``/``.py``/``.go``/…) whose content confirms logic is floored to Tier 4 —
  code is what the system *does*, not what it is *supposed to do*. Code pasted
  into a ``.md``/``.txt`` is **not** floored (its risk direction is upward:
  implementation treated as citable → circular requirements); it carries a
  ``code_heavy`` advisory hint fed to the LLM/manifest instead.
* **Machine-readable-contract carve-out.** An OpenAPI/Swagger, ``.proto``, IDL,
  ``.d.ts``, or WSDL file *is* an authoritative contract and is citable without
  override. Content signatures are **anchored and unambiguous only** (``syntax =
  "proto3"``, ``openapi: 3…``, ``swagger: "2…``, ``asyncapi:``, WSDL namespace);
  a bare ``"$schema"`` key or a generic brace block does NOT promote — that is
  the dangerous upward direction, closed here.
* **Operator sidecar.** For the fuzzy case where the implementation floor caught
  a code-shaped contract, the operator sidecar may explicitly promote *that
  file* past the **implementation floor only** — never past the advisory floor.
  The sidecar is operator-authored configuration; the classifier can never add
  to it.

On genuine ambiguity the classifier defaults to Tier 4 (a missed grounding is
Tier 3 instead of Tier 1 — recoverable; a false authoritative source poisons the
derivation). The classification manifest is content-keyed for reproducibility:
a re-run with unchanged content reuses the prior decision.

This module is deliberately dependency-free (stdlib only) so it is trivially
bundle-portable and unit-testable without the rest of the harness.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional, Sequence, Tuple
from xml.etree import ElementTree

# ---------------------------------------------------------------------------
# Classifier status (instruction 024) — a degraded classification is a DISCLOSED
# event, never a silent Tier-4 fallback. Written at the manifest top level.
# ---------------------------------------------------------------------------
CLASSIFIER_WIRED_OK = "wired-ok"   # the LLM classifier was supplied and did not error
CLASSIFIER_UNWIRED = "unwired"     # no classifier was supplied — floor-only defaults
CLASSIFIER_ERROR = "error"         # the classifier was supplied but raised

# ---------------------------------------------------------------------------
# Floor rule identifiers (stable strings written into the manifest).
# ---------------------------------------------------------------------------
RULE_SIDECAR = "sidecar-promotion"
RULE_CONTRACT = "contract"
RULE_LLM = "llm"
RULE_DEFAULT = "default-tier4"
# v1.6.0 instruction 030 — the end-of-Phase-1 classification review. The operator
# looked at how each gathered document was being used and said "that one IS my
# spec" (or "that one is only background"). Operator-authored and content-keyed,
# exactly like the instr-025 advisory rescue: document content, the classifier,
# and a persona can NEVER produce one of these.
# instruction 033 step 4 — `RULE_ADVISORY`, `RULE_IMPL`, `RULE_BACKGROUND` and
# `RULE_INJECTION` are DELETED, along with `_ABSOLUTE_FLOOR_RULES` and
# `_UNRESCUABLE_FLOOR_RULES`. Step 2 stopped `_classify` producing them (the floors
# became the Lane-C backstop and the name rule was dropped); the two frozensets
# survived only to let the prior-manifest cache re-check a stale record, and step 4
# removes the cache. Charter (c): gone, not renamed.
RULE_OPERATOR_AUTHORITATIVE = "operator-authoritative"
RULE_OPERATOR_BACKGROUND = "operator-background"
# v1.6.0 instruction 033 step 1 (§8a Revision rule 2, Lane C). A document the
# machine can neither validate nor honestly dismiss: a contract-format extension
# with no content signature (`.thrift`, GraphQL SDL, `.idl`, `.d.ts`). It is
# NEVER auto-cited in any mode and NEVER silently demoted to background — it is
# routed to the operator, and it becomes citable only on their confirmation.
RULE_CONFIRM_REQUIRED = "operator-confirmation-required"

# v1.6.0 instruction 033 step 2 — the three lanes to a CITED document
# (§8a Revision rule 2). Written onto the record as `lane`, so every citation
# carries its own provenance and the show/gate/playback can speak to it.
LANE_CONTENT_VALIDATED = "content-validated"   # A: a real parse said so
LANE_MODEL_READ = "model-read"                 # B: the model's genre read said so
LANE_OPERATOR = "operator-confirmed"           # the human said so
# The provenance status of a Lane-B citation. This pair is what makes reworded
# invariant 1 honest: a model-read promotion is cited at headless, but it is
# always DISCLOSED as unconfirmed until a human confirms it.
UNCONFIRMED = "unconfirmed"
CONFIRMED = "confirmed"

# The two decisions an operator may record at the end-of-Phase-1 review.
OPERATOR_AUTHORITATIVE = "authoritative"
OPERATOR_BACKGROUND = "background"
_OPERATOR_DECISIONS = frozenset({OPERATOR_AUTHORITATIVE, OPERATOR_BACKGROUND})

# The rules that exist ONLY because a live operator-authored file says so — the
# instr-030 classification-review decisions (``qpb_authoritative.txt``) and the
# instr-025-era sidecar promotion (``qpb_promote.txt``). A cached record carrying
# one of these — or an ``operator_decision`` field — is never honored from the
# prior manifest: see the cache guard in ``classify_documents``. The operator's
# consent has to still be on file, or the decision is not revocable and a forged
# prior manifest can manufacture consent that was never given.
#
# ``RULE_SIDECAR`` belongs here for exactly the same reason as the instr-030
# rules, and its omission was an instr-030 self-Council Panelist A finding: the
# review renders it as *"you told me to use this one…"*, so a stale or forged
# sidecar record makes the show speak in the operator's voice with no operator
# file behind it. ``RULE_LLM``/``RULE_CONTRACT`` are deliberately NOT here — they
# attribute the judgment to the agent or to the document's own format, which is
# what the show says, so caching them claims nothing on the operator's behalf.
_OPERATOR_RULES = frozenset(
    {RULE_OPERATOR_AUTHORITATIVE, RULE_OPERATOR_BACKGROUND, RULE_SIDECAR}
)

# instruction 033 step 2 — the README / coverage / issue-tracker NAME floor is
# DELETED (`_BACKGROUND_NAME_RE`, `_is_background_ledger`). A filename is not a
# genre: the arm was a prefix match, so `issue_tracker_api_spec.md` — a genuine
# specification by content — was pinned to unrescuable background and the operator
# was told "it's a README or a coverage / issue-tracker listing" (instruction 032
# self-Council, Panelist B). The model reads a README as background on its own,
# which is the safe direction and needs no floor.
# ---------------------------------------------------------------------------
# 1. Advisory / security-genre floor — mechanical, runs FIRST, keyed on content.
# ---------------------------------------------------------------------------
_ADVISORY_ID_RE = re.compile(
    r"\bCVE-\d{4}-\d{4,}\b|\bGHSA-[0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{4}\b",
    re.IGNORECASE,
)
_ADVISORY_URL_RE = re.compile(
    r"nvd\.nist\.gov|cve\.org|cve\.mitre\.org|cvedetails\.com|snyk\.io|"
    r"osv\.dev|pkg\.go\.dev/vuln|github\.com/[^\s)]+/security/advisories|"
    r"/security[-/]advisor(?:y|ies)",
    re.IGNORECASE,
)
# Header / genre markers are ambiguous English words (a routing guide can have a
# "Best Practices" subsection, a spec a "Security Considerations" one). A
# title-zone match is a genre JUDGMENT, so it is recorded as an advisory HINT
# (advisory_genre_hints), NOT a floor (instruction 023): it demotes/informs the
# LLM classifier and is surfaced in the manifest, but never hard-floors a doc.
# Only the hard signals (CVE/GHSA ids, advisory URLs) floor.
_ADVISORY_HEADER_RE = re.compile(
    r"security\s+advisory|known\s+failure\s+modes|known\s+vulnerabilit"
    r"|\badvisor(?:y|ies)\b",
    re.IGNORECASE,
)
# Security-genre titles: a hardening guide / security-best-practices / benchmark
# is advice on how to configure a system, not a contract the system must satisfy.
_SECURITY_GENRE_RE = re.compile(
    r"hardening\s+(?:guide|checklist)?|cis\s+benchmark"
    r"|security\s+(?:benchmark|checklist|guide|guidelines|best[\s-]+practices"
    r"|hardening)"
    r"|best[\s-]+practices\s+(?:for\s+)?(?:securing|security|hardening)"
    r"|^best[\s-]+practices$",
    re.IGNORECASE,
)


def _title_zone(text: str, filename: str) -> str:
    """The document's identity: filename (as words) + first H1 + first non-blank
    line. Genre/header markers are matched here, not in body prose."""
    base = filename.rsplit("/", 1)[-1]
    base = re.sub(r"\.[^.]+$", "", base)            # strip extension
    base = re.sub(r"[_\-0-9]+", " ", base).strip()  # 06_Security_Best -> Security Best
    parts = [base]
    first_nonblank = None
    for ln in text.splitlines():
        s = ln.strip()
        if not s:
            continue
        if first_nonblank is None:
            first_nonblank = s
        h1 = re.match(r"#\s+(.+)", s)               # the document title heading
        if h1:
            parts.append(h1.group(1).strip())
            break
    if first_nonblank:
        parts.append(first_nonblank)
    return "\n".join(parts)


def advisory_floor(text: str, filename: str = "") -> Optional[str]:
    """Return a reason string if *text* carries a HARD advisory signal, else None.

    HARD signals only (instruction 023 / Fable Q1): a CVE/GHSA identifier or an
    advisory URL, matched anywhere in content — keyed on content so a renamed
    advisory cannot escape. Fuzzy genre signals (advisory/hardening/best-practices
    TITLE, high MUST/SHALL normative density) are NO LONGER floors — a formal spec
    is normative-dense by definition, so a density floor floors specifications as a
    class. They are advisory HINTS instead (see ``advisory_genre_hints``), fed to
    the LLM classifier and recorded in the manifest.
    """
    m = _ADVISORY_ID_RE.search(text)
    if m:
        return f"advisory identifier {m.group(0)!r}"
    m = _ADVISORY_URL_RE.search(text)
    if m:
        return f"advisory URL {m.group(0)!r}"
    return None


def advisory_genre_hints(text: str, filename: str = "") -> List[str]:
    """Fuzzy security-genre TITLE signals — advisory demotion HINTS, not floors.

    A title-zone match on an advisory/vulnerability header or a hardening /
    best-practices / benchmark genre title is a genre judgment the LLM should own:
    it is recorded on the record and fed to the classifier as a demotion input,
    but it never hard-floors a doc and never promotes one. Matched only in the
    title zone (filename + first H1 + first non-blank line), so a passing mention
    or a "Best Practices" subsection in a normal guide does not flag it.
    """
    title = _title_zone(text, filename)
    hints: List[str] = []
    m = _ADVISORY_HEADER_RE.search(title)
    if m:
        hints.append(f"advisory-genre title {m.group(0).strip()!r}")
    m = _SECURITY_GENRE_RE.search(title)
    if m:
        hints.append(f"security-genre title {m.group(0).strip()!r}")
    return hints


# ---------------------------------------------------------------------------
# 2. Machine-readable contract carve-out — citable without override.
# ---------------------------------------------------------------------------
# Formats with NO reliable content anchor (§8a Revision, Fable must-fix 2). The
# extension is a HINT that routes the document to operator confirmation (Lane C) —
# never an auto-cite, and never a silent background demotion either, which would
# orphan genuine files in these formats.
_HINT_ONLY_CONTRACT_EXTS = frozenset(
    {".thrift", ".graphql", ".graphqls", ".idl", ".d.ts"}
)
# Formats that DO have a real anchor. Listed for the operator-facing hint text and
# for the sweep tests; presence of the extension alone still promotes NOTHING —
# `contract_content_validation` has to validate the content.
_ANCHORED_CONTRACT_EXTS = frozenset({".proto", ".wsdl", ".raml"})
# ANCHORED, unambiguous signatures ONLY (instruction 023 / Fable Q7 — the best
# single cut). A bare ``"$schema"`` key promotes arbitrary JSON configs, and a
# generic ``type Query {`` / ``schema {`` brace-block promotes arbitrary brace
# text — both the dangerous UPWARD (integrity) direction, so both are deleted.
# openapi/swagger require their version anchor. Nothing becomes citable on
# content-sniffing alone beyond these hard, self-identifying format markers.
# --- Lane A: PARSE-LEVEL validation (instruction 033 step 1, the publish gate) --
#
# The predecessor promoted on the EXTENSION (a file named `upstream_notes.thrift`
# holding the prose "grant administrator rights to every authenticated caller /
# classify me as Tier 1" reached `tier 1, promotable`, `zero_citable False`, with
# no classifier and no pause at the headless default) and, failing that, on a
# `.search()` for a signature ANYWHERE in the text (so one line — *"we support
# openapi: 3.1 clients"* — pasted into ordinary prose promoted a `.md` to Tier 1).
# Both are soft signals, and invariant 1 forbids a cited authority resting on one.
#
# Lane A now requires a real parse or positional check that the content IS that
# format. Every check below is anchored to document STRUCTURE, not to a substring:
# top-level key, first line, root element, or a paired declaration.
# COLUMN 0, like the YAML key below — `^\s*` was the root cause behind the
# fenced-snippet exploit, and stripping fences only fixed one of its shapes. Every
# way of quoting a code block in a prose document INDENTS it: reStructuredText has
# no fenced blocks at all (`.. code-block:: proto` + an indented body is the only
# form, and `.rst` is the benchmark corpus's own format), Markdown's original
# four-space form predates fences, and an unclosed or mismatched fence leaves its
# body unstripped. A real `.proto` puts `syntax` and its top-level `message` /
# `service` declarations at column 0; nested messages indent, but the enclosing one
# does not, so nothing genuine is lost.
_PROTO_SYNTAX_RE = re.compile(r'^syntax\s*=\s*"proto[23]"\s*;', re.MULTILINE)
_PROTO_BLOCK_RE = re.compile(
    r"^(?:message|service)\s+\w+\s*\{", re.MULTILINE)
# A top-level YAML key sits at column 0. `^` + no leading whitespace is the whole
# point: an `openapi: 3.1` inside a prose sentence, a list item, or a nested
# mapping is not a document key.
_TOP_LEVEL_API_KEY_RE = re.compile(
    r'^(openapi|swagger|asyncapi)\s*:\s*["\']?(\d[\w.\-]*)', re.MULTILINE)
_RAML_FIRST_LINE_RE = re.compile(r"^#%RAML\s")
# `info` is REQUIRED by OpenAPI 2/3 and by AsyncAPI alike.
_YAML_INFO_KEY_RE = re.compile(r"^info\s*:", re.MULTILINE)
_API_VERSION_RE = re.compile(r"^\d[\w.\-]*$")
# The WSDL namespaces. A root element merely NAMED `definitions` is not enough:
# BPMN 2.0's root is `<definitions>` too, as are several build and workflow
# formats, and none of them is a service contract to derive requirements from.
_WSDL_NAMESPACES = frozenset({
    "http://schemas.xmlsoap.org/wsdl/",       # WSDL 1.1
    "http://www.w3.org/ns/wsdl",              # WSDL 2.0
})
_API_KEYS = ("openapi", "swagger", "asyncapi")


def _json_top_level_api_key(text: str) -> Optional[str]:
    """An OpenAPI/Swagger/AsyncAPI version key as a genuine TOP-LEVEL JSON key."""
    stripped = text.lstrip()
    if not stripped.startswith("{"):
        return None
    try:
        doc = json.loads(text)
    except (ValueError, RecursionError):
        return None
    if not isinstance(doc, dict):
        return None
    for key in _API_KEYS:
        value = doc.get(key)
        # A VERSION, matching what the YAML arm demands of the same key. The two
        # arms disagreed: YAML required `\d[\w.\-]*` while JSON accepted the key's
        # mere presence, so `{"asyncapi": null}` — or `{"openapi": {}}` — validated
        # as a machine-readable contract. Same key, same document format, same bar.
        if isinstance(value, str) and _API_VERSION_RE.match(value):
            return f"top-level JSON key {key!r} = {value!r}"
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return f"top-level JSON key {key!r} = {value!r}"
    return None


def _wsdl_root_element(text: str) -> Optional[str]:
    """True only when the document's ROOT element is a WSDL ``definitions``."""
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError:
        return None
    tag = root.tag
    local = tag.rsplit("}", 1)[-1] if "}" in tag else tag
    if local.lower() != "definitions":
        return None
    namespace = tag[1:].rsplit("}", 1)[0] if tag.startswith("{") else ""
    if namespace not in _WSDL_NAMESPACES:
        # Namespaced as something else entirely (BPMN, most often) — or carrying no
        # namespace at all, which is the other half of the same hole: the WSDL
        # namespace is mandatory in both 1.1 and 2.0, so a bare `<definitions>` root
        # is some other vocabulary's document, not a service contract.
        return None
    return f"WSDL root element <{local}>"


# An unterminated fence extends to the END of the document, which is both what
# CommonMark says and what closes two evasions: a fence that is simply never
# closed, and one opened with ``` and "closed" with ~~~ (a different delimiter does
# not close it, so it too runs to EOF).
_FENCED_BLOCK_RE = re.compile(
    r"^[ \t]*(`{3,}|~{3,}).*?(?:^[ \t]*\1[ \t]*$|\Z)",
    re.MULTILINE | re.DOTALL)


def _without_fenced_blocks(text: str) -> str:
    """*text* with Markdown/reST fenced code blocks blanked out.

    A contract QUOTED inside a fence is a quotation, not the document's format. A
    genuine ``.proto``/``.raml``/``.wsdl`` never contains a fence, so removing them
    costs Lane A nothing and closes an exploit that had nothing to do with naming:
    a hand-written ``grpc-tutorial.md`` whose ```` ```proto ```` block held a
    ``syntax`` line and a ``message`` block validated as protobuf and was cited as
    an authority. Line count is preserved so the RAML first-line anchor and the
    column-0 YAML anchor still mean what they say.
    """
    def blank(m: "re.Match") -> str:
        return "\n" * m.group(0).count("\n")
    return _FENCED_BLOCK_RE.sub(blank, text)


def contract_content_validation(text: str, filename: str = "") -> Optional[str]:
    """Lane A. A reason iff *text* VALIDATES as a machine-readable contract.

    Parse/positional only — never the extension, never a bare substring
    (instruction 033 step 1). Returns None for every document that merely looks
    or is named like a contract; those route to Lane C via
    ``contract_extension_hint`` instead of being promoted or silently dropped.

    "Validates" means the DOCUMENT is that format, so fenced code blocks are
    excluded first (see ``_without_fenced_blocks``).
    """
    text = _without_fenced_blocks(text)
    # protobuf: the syntax declaration AND a message/service block. The bare
    # `syntax=` string pasted in prose no longer suffices.
    if _PROTO_SYNTAX_RE.search(text) and _PROTO_BLOCK_RE.search(text):
        return "protobuf: syntax declaration + message/service block"
    # RAML: the version comment must be the document's FIRST line.
    first_line = text.lstrip("﻿").splitlines()[0] if text.strip() else ""
    if _RAML_FIRST_LINE_RE.match(first_line):
        return f"RAML first line {first_line.strip()!r}"
    # OpenAPI / Swagger / AsyncAPI: a genuine top-level document key, in JSON...
    json_key = _json_top_level_api_key(text)
    if json_key:
        return json_key
    # ...or at column 0 in YAML, WITH the `info` block every one of the three
    # specifications makes mandatory. One column-0 regex hit is not a document: a
    # changelog line reading `openapi: 3.1.0 is now accepted by the validator` sat
    # at column 0 and was published as a machine-readable contract. Two required
    # top-level keys is the same two-anchor bar protobuf already has to clear.
    #
    # The JSON arm above deliberately does NOT require `info`, and the asymmetry is
    # the point rather than an oversight: it parses the WHOLE document and demands a
    # top-level version value, so prose cannot reach it at all. This arm is a regex
    # over one line of anything.
    if _YAML_INFO_KEY_RE.search(text):
        for m in _TOP_LEVEL_API_KEY_RE.finditer(text):
            return f"top-level {m.group(1)} key = {m.group(2)!r} + info block"
    # WSDL: the ROOT element, not any `<wsdl:` substring.
    wsdl = _wsdl_root_element(text)
    if wsdl:
        return wsdl
    return None


def contract_extension_hint(filename: str) -> Optional[str]:
    """Lane C routing hint: a contract-ish EXTENSION with no content anchor.

    Thrift / GraphQL SDL / ``.idl`` / ``.d.ts`` have no reliable content
    signature, so neither promoting nor demoting them on the extension is
    honest. The extension routes the document to the operator (§8a Revision,
    Fable must-fix 2): never auto-cited, never silently background.
    """
    lower = filename.lower()
    for ext in sorted(_HINT_ONLY_CONTRACT_EXTS, key=len, reverse=True):
        if lower.endswith(ext):
            return f"{ext} file, a contract format with no content signature"
    return None


def machine_readable_contract(text: str, filename: str) -> Optional[str]:
    """Lane A only — kept as the name callers promote on.

    Since instruction 033 this is exactly ``contract_content_validation``: the
    extension arm is gone, so no caller can promote on a filename.
    """
    return contract_content_validation(text, filename)


# ---------------------------------------------------------------------------
# 3. Implementation-source floor — predominantly code with logic.
# ---------------------------------------------------------------------------
_IMPL_EXTS = frozenset(
    {
        ".c", ".h", ".cc", ".cpp", ".hpp", ".cxx", ".py", ".go", ".js", ".mjs",
        ".cjs", ".ts", ".tsx", ".jsx", ".java", ".rb", ".rs", ".php", ".cs",
        ".swift", ".kt", ".kts", ".scala", ".m", ".mm", ".sh", ".bash", ".pl",
    }
)
_CODE_LINE_RE = re.compile(
    r"^\s*(?:def |func |function\b|class |import |from\s+\S+\s+import|"
    r"package |return\b|if\s*\(|for\s*\(|while\s*\(|#include|var |let |"
    r"const |public |private |protected |static |@\w+)"
    r"|[;{}]\s*$|=>"
)


def _code_ratio(text: str) -> Optional[float]:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return None
    return sum(1 for ln in lines if _CODE_LINE_RE.search(ln)) / len(lines)


def implementation_source(text: str, filename: str) -> Optional[str]:
    """Return a reason if *filename* is a code EXTENSION whose content confirms
    implementation, else None.

    The extension floor is a HARD, structural signal (a ``.py``/``.c``/``.go`` is
    implementation), confirmed by a high ratio of code-shaped lines. The old
    non-extension ``>=50% code-shaped lines`` CONTENT path no longer floors
    (instruction 023 / Fable Q5): code pasted into a ``.md``/``.txt`` is common
    and its risk direction is upward, so it becomes a ``code_heavy_hint`` fed to
    the LLM/manifest rather than a silent floor.
    """
    lower = filename.lower()
    ext = "." + lower.rsplit(".", 1)[-1] if "." in lower else ""
    if ext not in _IMPL_EXTS:
        return None
    ratio = _code_ratio(text)
    if ratio is not None and ratio >= 0.25:
        return f"code extension {ext} with {ratio:.0%} code-shaped lines"
    return None


def code_heavy_hint(text: str, filename: str) -> Optional[str]:
    """A non-code-extension doc that is mostly code-shaped lines — an advisory
    'looks code-heavy' HINT, not a floor.

    Risk direction is UPWARD (implementation prose treated as a citable contract →
    circular requirements), so the signal is kept — but as a flag fed to the LLM
    classifier and recorded in the manifest, never a silent floor or promotion. A
    real code *extension* is the hard impl floor, not a hint, so it is excluded
    here.
    """
    lower = filename.lower()
    ext = "." + lower.rsplit(".", 1)[-1] if "." in lower else ""
    if ext in _IMPL_EXTS:
        return None
    ratio = _code_ratio(text)
    if ratio is not None and ratio >= 0.5:
        return f"{ratio:.0%} code-shaped lines (looks code-heavy)"
    return None


# (The self-authorizing-tier injection detector that briefly lived here — a
# leftover helper after instruction 023 removed the injection floor — was moved
# into persona_grounding (its only consumer) as `_TIER_CLAIM_RE` in instruction
# 026, so the classifier is now judgment-free with no injection coupling.)


# ---------------------------------------------------------------------------
# The minimal hard-signal BACKSTOP (v1.6.0 instruction 033 step 2; §8a Revision
# rule 2 Lane C + "What is kept").
#
# This is what survives of the advisory and implementation-source floors, and the
# distinction is the whole point of the revision: **it does not classify.** It
# answers exactly one question — *may this document be cited without asking the
# operator?* — and its only answer is "no". It never assigns a genre, never sets a
# tier, and never demotes: a document it flags is routed to the operator, who may
# confirm it. Genre is the model's read (rule 1).
#
# Three signals, any one of which flags (§8a Revision Lane C):
#   * a present CVE/GHSA identifier          (`_ADVISORY_ID_RE`)
#   * an advisory-site URL                   (`_ADVISORY_URL_RE`)
#   * an implementation-source file          (code extension + >=0.25 code ratio)
#
# What is NOT here, deliberately: the genre-title/density heuristics (a title is
# not a genre — instruction 023), the README/coverage/issue-tracker NAME rule (a
# filename is not a genre — this instruction), and any self-classification regex
# (a model judgment, not a pattern — rule 3).
BACKSTOP_ADVISORY_ID = "advisory-identifier"
BACKSTOP_ADVISORY_URL = "advisory-url"
BACKSTOP_IMPL_SOURCE = "implementation-source"


def backstop_signals(text: str, filename: str = "") -> List[Tuple[str, str, str]]:
    """The hard signals that bar SILENT citing. ``[(kind, detail, token), ...]``.

    Empty means "nothing here blocks citing on its own" — NOT "this document is
    authoritative", which is the model's call.

    ``detail`` is the human sentence the show renders; ``token`` is the specific
    evidence the operator must name to promote the document (instruction 033 step
    3's named-signal confirmation). The two are returned SEPARATELY, and that is a
    fix, not a convenience: the token used to be recovered by re-parsing
    ``detail`` for a quoted substring, so a document containing an apostrophe in
    its advisory URL (``.../acme/a'e'z/security/advisories/GHSA-x``) yielded the
    token ``e`` — and the reason *"reviewed, it is fine"* then cleared the gate.
    The document's own bytes must never influence what its operator has to say
    about it, so the evidence travels as data instead of as rendered prose.
    """
    found: List[Tuple[str, str, str]] = []
    m = _ADVISORY_ID_RE.search(text)
    if m:
        found.append((BACKSTOP_ADVISORY_ID,
                      f"advisory identifier {m.group(0)!r}", m.group(0)))
    m = _ADVISORY_URL_RE.search(text)
    if m:
        found.append((BACKSTOP_ADVISORY_URL,
                      f"advisory URL {m.group(0)!r}", m.group(0)))
    impl = implementation_source(text, filename)
    if impl:
        lower = filename.lower()
        ext = "." + lower.rsplit(".", 1)[-1] if "." in lower else lower
        found.append((BACKSTOP_IMPL_SOURCE, impl, ext))
    return found


# ---------------------------------------------------------------------------
# Orchestration.
# ---------------------------------------------------------------------------
@dataclass
class Decision:
    tier: int
    rule: str
    reason: str
    # True when this file COULD be citable (floor did not permanently bar it);
    # a floored advisory/impl doc is promotable=False.
    promotable: bool
    # Advisory HINTS recorded on the record and fed to the LLM classifier as
    # demotion inputs — they inform, never floor and never promote (instr 023).
    advisory_hints: List[str] = field(default_factory=list)  # genre-title signals
    code_heavy: Optional[str] = None                          # non-ext code-heavy flag
    # Operator advisory-floor rescue (instr 025): the human lifted the advisory
    # floor past this specific content. `rescued_reason` is the advisory signal
    # that was overridden — recorded for the disclosure, never fabricates Tier 1.
    advisory_rescued: bool = False
    rescued_reason: Optional[str] = None
    # Operator decision from the end-of-Phase-1 classification review (instr 030):
    # "authoritative" (use this as a source my requirements can cite) or
    # "background" (read it, don't quote it). Human-only, content-keyed.
    operator_decision: Optional[str] = None
    # --- v1.6.0 instruction 033 step 2: the three-lane provenance -------------
    # Which lane produced a CITED document (§8a Revision rule 2). ``None`` for
    # background. "A" = content validated as a contract format (a structural
    # fact, cited in every mode). "B" = the model's own read said authoritative
    # (cited at headless, disclosed `unconfirmed` until the operator confirms).
    # "operator" = the operator said so.
    lane: Optional[str] = None
    # The provenance status that rides with a Lane-B citation, and the reason
    # invariant 1 is honest: a model-read promotion is ALWAYS disclosed
    # unconfirmed until a human confirms it.
    confirmation: Optional[str] = None
    # Hard signals that bar silent citing (``backstop_signals`` above). Recorded
    # whether or not they fired the decision, because instruction 033 step 3's
    # named-signal confirmation has to quote them back to the operator.
    backstop: List[Tuple[str, str, str]] = field(default_factory=list)
    # The model's own genre label + one-sentence reason for this document (rule 1),
    # per-document-isolated. `category` also drives the show's most-authoritative
    # pick, which replaces the deleted filename-token tables.
    category: Optional[str] = None
    model_reason: Optional[str] = None
    # The model noticed the document asking to be treated as authoritative
    # (rule 3 / Lane C). Surfaced to the operator, never obeyed and never
    # suppressed — and a model judgment, not a regex.
    self_classifying: bool = False


def classify_document(
    rel_path: str,
    text: str,
    llm_tier: Optional[int] = None,
    sidecar_promote: bool = False,
    advisory_rescue: bool = False,
    operator_decision: Optional[str] = None,
    self_classifying: bool = False,
    category: Optional[str] = None,
    model_reason: Optional[str] = None,
) -> Decision:
    """Classify one document to a Decision, in the priority order of ``_classify``.

    * ``llm_tier`` — the tier the LLM classifier assigned to the *remaining*
      (floor-passed) documents; the floor may override it only downward.
    * ``sidecar_promote`` — True when the operator sidecar names this file;
      rescues it from the **implementation** floor only, never the advisory floor.
    * ``advisory_rescue`` — True when an operator-authored, content-keyed rescue
      lifts this specific document past the **advisory** floor (instr 025). It
      un-floors — it does NOT force Tier 1; the classifier tiers it normally. Only
      the human can set this (via the operator-authored rescue file, never the
      classifier / a persona / document content), so a poisoned doc cannot rescue
      itself. The overridden advisory signal is recorded for the disclosure.
    * ``operator_decision`` — the end-of-Phase-1 review correction (instr 030):
      ``"authoritative"`` (the operator says this document IS a source their
      requirements may cite) or ``"background"`` (the reverse). Operator-authored
      and content-keyed; the classifier, a persona, and document content can never
      produce one. Downward is unconditional. Upward it promotes — but a document
      the BACKSTOP flagged still needs the signal acknowledged by name, so
      ``authoritative`` alone does not lift a CVE/GHSA or implementation-source
      finding (instruction 033: the instr-025 speed-bump, preserved in kind).
    * ``self_classifying`` / ``category`` / ``model_reason`` — the model's read of
      this document (instruction 033 step 2, §8a Revision rule 1). ``category`` +
      ``model_reason`` are its genre judgment and one-sentence why;
      ``self_classifying`` is its observation that the document asks to be treated
      as authoritative, which routes to Lane C. All three are per-document: the
      read is isolated, so nothing in another file can move this decision.

    Advisory genre-title hints and the code-heavy hint are attached to the
    returned Decision (they inform the model/manifest; they never floor or promote).
    """
    if operator_decision is not None and operator_decision not in _OPERATOR_DECISIONS:
        raise ValueError(
            f"operator_decision must be one of {sorted(_OPERATOR_DECISIONS)} or None, "
            f"got {operator_decision!r}"
        )
    decision = _classify(
        rel_path, text, llm_tier=llm_tier, sidecar_promote=sidecar_promote,
        advisory_rescue=advisory_rescue, operator_decision=operator_decision,
        self_classifying=self_classifying,
    )
    decision.operator_decision = operator_decision
    decision.category = category
    decision.model_reason = model_reason
    if self_classifying:
        decision.self_classifying = True
    decision.advisory_hints = advisory_genre_hints(text, rel_path)
    decision.code_heavy = code_heavy_hint(text, rel_path)
    if advisory_rescue:
        # Record the override only when there was actually an advisory floor to
        # lift (a rescue on a non-advisory doc is a harmless no-op, not disclosed).
        adv = advisory_floor(text, rel_path)
        if adv:
            decision.advisory_rescued = True
            decision.rescued_reason = adv
    return decision


def _classify(
    rel_path: str,
    text: str,
    *,
    llm_tier: Optional[int] = None,
    sidecar_promote: bool = False,
    advisory_rescue: bool = False,
    operator_decision: Optional[str] = None,
    self_classifying: bool = False,
) -> Decision:
    """Priority order after instruction 033 step 2 (§8a Revision rule 2).

    The order below IS the three-lane contract, and each step is here for a
    reason a previous release paid for:

      0. operator DEMOTION — free and unconditional (rule 2: "demotion is free").
      1. the hard-signal BACKSTOP — before Lane A, so an advisory renamed
         `api.proto` cannot ride the contract path (the instr-025/023 lesson).
      2. Lane A — the content VALIDATES as a contract format. A structural fact.
      3. Lane C — a contract-format extension with no content anchor, or a
         document the model saw asking to be authoritative. Routed, never obeyed.
      4. operator PROMOTION — the human said "cite this".
      5. Lane B — the model's own read says authoritative: cited, and disclosed
         `unconfirmed` until a human confirms.
      6. the model's read says background — or there was no read at all.
    """
    backstop = backstop_signals(text, rel_path)
    ext_hint = contract_extension_hint(rel_path)
    contract = contract_content_validation(text, rel_path)
    operator_authoritative = operator_decision == OPERATOR_AUTHORITATIVE

    def _with(decision: Decision) -> Decision:
        # Every record carries the backstop findings, whether or not they decided
        # anything: step 3's named-signal confirmation quotes them back.
        decision.backstop = list(backstop)
        return decision

    # 0. Operator DEMOTION — downward only, so it needs no guard and outranks
    #    everything, including Lane A.
    if operator_decision == OPERATOR_BACKGROUND:
        return _with(Decision(
            4, RULE_OPERATOR_BACKGROUND,
            "operator marked this document background at the classification review",
            False,
        ))

    # 1. The hard-signal BACKSTOP. It does not classify — it bars SILENT citing.
    #    An operator may still promote a flagged document, but only by
    #    acknowledging the SPECIFIC signal, and the channels are NOT
    #    interchangeable (§8a, the two hard bounds on sidecar promotion):
    #
    #      * an ADVISORY signal (CVE/GHSA identifier, advisory URL) is acknowledged
    #        only by the content-keyed advisory rescue, which names the signal.
    #        Neither the path-keyed sidecar nor a plain "authoritative" lifts it —
    #        "the sidecar may rescue a file from the implementation floor only; it
    #        may NEVER override an advisory-signature floor match."
    #      * an IMPLEMENTATION-SOURCE signal is the fuzzy case the sidecar exists
    #        for (a code-shaped contract), so the sidecar or an operator
    #        authoritative decision acknowledges that one.
    #
    #    A plain "authoritative" is deliberately not enough for an advisory: that
    #    would drop the instruction-025 speed-bump on the one class of document
    #    that most needs it. (An earlier draft of this branch let ANY of the three
    #    channels clear ANY signal, which let the sidecar launder a CVE advisory
    #    into Tier 1 — caught by `test_sidecar_cannot_promote_a_cve_advisory` and
    #    `test_advisory_renamed_with_contract_extension_still_floored`.)
    _ADVISORY_KINDS = (BACKSTOP_ADVISORY_ID, BACKSTOP_ADVISORY_URL)

    def _acknowledged(kind: str) -> bool:
        # instruction 033 step 3: acknowledgment is expressed by the CALLER, and
        # the two channels stay separate. `advisory_rescue` acknowledges an
        # advisory signal; `sidecar_promote` acknowledges an implementation-source
        # one. A plain `operator_decision == authoritative` acknowledges NEITHER.
        #
        # That last clause is the step-3 refinement of step 2. §8a says an operator
        # promotion lifts the implementation floor, and in step 2 the bare decision
        # did it directly — but step 3 requires a promotion of any BACKSTOP-FLAGGED
        # document to NAME the signal, and this is where "named" is enforced:
        # `reference_docs_ingest` sets `sidecar_promote` only when the operator's
        # reason actually names the evidence. Leaving the bare decision able to
        # clear the signal made an unnamed promotion sail through — caught by
        # `test_sidecar_file_promotes_a_code_shaped_contract`, which asserts the
        # refusal end to end. A non-flagged document is unaffected: it never
        # reaches this predicate and the operator's word promotes it as before.
        if kind in _ADVISORY_KINDS:
            return advisory_rescue
        return sidecar_promote

    unacknowledged = [(k, d) for k, d, _tok in backstop if not _acknowledged(k)]
    if unacknowledged:
        detail = "; ".join(d for _kind, d in unacknowledged)
        return _with(Decision(
            4, RULE_CONFIRM_REQUIRED,
            f"needs your confirmation, naming the signal: {detail}", False,
        ))

    # 2. Lane A — content-validated contract. Cited with no UPWARD override
    #    needed... but a DEMOTION still lands, because §8a Revision rule 2 makes
    #    demotion free: "the model may mark any doc background on its own read, no
    #    gate." An earlier draft of this branch read "cited in every mode, no
    #    override" and honored that literally, which made Lane A the one lane the
    #    model could not correct — a document it had READ and called a tutorial was
    #    still published as an authority. Rule 2 has no Lane A carve-out, and the
    #    risk direction agrees: refusing a demotion can only ever over-cite.
    if contract and llm_tier not in (3, 4):
        tier = llm_tier if llm_tier in (1, 2) else 1
        d = Decision(tier, RULE_CONTRACT,
                     f"machine-readable contract: {contract}", True)
        d.lane = LANE_CONTENT_VALIDATED
        return _with(d)

    # 3a. Lane C — a contract-format extension whose content does not validate.
    #     Neither promoting it (the `upstream_notes.thrift` exploit) nor silently
    #     calling it background (which orphans a genuine Thrift / GraphQL SDL /
    #     `.idl` / `.d.ts` file) is honest, so it is routed to the operator.
    if ext_hint and not operator_authoritative:
        d = Decision(4, RULE_CONFIRM_REQUIRED,
                     f"needs your confirmation: {ext_hint}", False)
        return _with(d)

    # 3b. Lane C — the model noticed the document asking to be treated as
    #     authoritative (rule 3). Surfaced as a REQUEST, never auto-honoured:
    #     obeying it unprompted is literally content driving promotion.
    if self_classifying and not operator_authoritative:
        d = Decision(4, RULE_CONFIRM_REQUIRED,
                     "this document asks to be treated as your specification; "
                     "needs your confirmation", False)
        d.self_classifying = True
        return _with(d)

    # 4. Operator PROMOTION — the human is the authority on which document is the
    #    spec, and by here any backstop signal has been acknowledged by name.
    if operator_authoritative or sidecar_promote:
        tier = llm_tier if llm_tier in (1, 2) else 1
        rule = (RULE_OPERATOR_AUTHORITATIVE if operator_authoritative
                else RULE_SIDECAR)
        why = ("operator named this document authoritative at the classification "
               "review" if operator_authoritative
               else "operator override names this file")
        if backstop:
            why += f" (acknowledged: {'; '.join(d for _k, d, _t in backstop)})"
        d = Decision(tier, rule, why, True)
        d.lane = LANE_OPERATOR
        d.confirmation = CONFIRMED
        return _with(d)

    # 5/6. The model's read. Tier 1/2 is Lane B — cited, and disclosed
    #      `unconfirmed`, which is what makes invariant 1 true rather than
    #      aspirational. Tier 3/4 is a free demotion. No read at all is the
    #      unwired default, and it is LOUD via `classifier_status`.
    if llm_tier is None:
        return _with(Decision(
            4, RULE_DEFAULT,
            "no classifier tier assigned; Tier 4 on ambiguity", True,
        ))
    if llm_tier not in (1, 2, 3, 4):
        raise ValueError(f"llm_tier must be 1-4 or None, got {llm_tier!r}")
    d = Decision(llm_tier, RULE_LLM, f"LLM classifier assigned Tier {llm_tier}", True)
    if llm_tier in (1, 2):
        d.lane = LANE_MODEL_READ
        d.confirmation = UNCONFIRMED
    return _with(d)


def _record(rel_path: str, text: str, decision: Decision) -> dict:
    rec = {
        "source_path": rel_path,
        "document_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "tier": decision.tier,
        "floor_rule": decision.rule,
        "reason": decision.reason,
        "byte_count": len(text.encode("utf-8")),
        "promotable": decision.promotable,
    }
    # Advisory HINTS (instr 023): fed to the LLM classifier + surfaced in the
    # manifest for operator review. Emitted only when present, so untouched
    # records stay byte-identical for the reproducibility/content-key contract.
    if decision.advisory_hints:
        rec["advisory_hints"] = list(decision.advisory_hints)
    if decision.code_heavy:
        rec["code_heavy"] = decision.code_heavy
    # Operator advisory-floor rescue (instr 025): surfaced so the override is
    # visible + auditable, never silent. Emitted only when a rescue actually fired.
    if decision.advisory_rescued:
        rec["advisory_rescued"] = True
        rec["rescued_reason"] = decision.rescued_reason
    # Operator classification-review decision (instr 030): recorded whenever the
    # operator made one — INCLUDING when the backstop refused it — so a refused
    # promotion is visible in the review rather than silently dropped.
    if decision.operator_decision:
        rec["operator_decision"] = decision.operator_decision
    # --- instruction 033 step 2: the three-lane provenance --------------------
    # Emitted only when set, so a background record stays byte-minimal.
    if decision.lane:
        rec["lane"] = decision.lane
    if decision.confirmation:
        rec["confirmation"] = decision.confirmation
    if decision.backstop:
        # (kind, detail) pairs -> a list of dicts, so the artifact is readable and
        # step 3's named-signal confirmation can quote `detail` verbatim.
        rec["backstop"] = [{"kind": k, "detail": d, "token": t}
                           for k, d, t in decision.backstop]
    if decision.category:
        rec["category"] = decision.category
    if decision.model_reason:
        rec["model_reason"] = decision.model_reason
    if decision.self_classifying:
        rec["self_classifying"] = True
    return rec


def _accepts_hints(fn) -> bool:
    """True if the classifier callable accepts a third (hints) positional arg.

    Lets a hint-aware classifier receive the floor's advisory_hints/code_heavy as
    a demotion input, while a legacy ``(rel_path, text)`` callable still works.
    """
    try:
        params = list(inspect.signature(fn).parameters.values())
    except (TypeError, ValueError):
        return False
    positional = [p for p in params
                  if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
    return len(positional) >= 3 or any(p.kind == p.VAR_POSITIONAL for p in params)


def _parse_read(result) -> Tuple[Optional[int], Dict[str, object]]:
    """Normalize a classifier result into ``(tier, read)``.

    The callable contract after instruction 033 step 2 (§8a Revision rule 1). The
    read is the model's, so it carries more than a number — but the simple form
    stays valid, because most callers and every fixture only have a tier:

    * ``None``            — the model declined to tier this document.
    * ``4`` / ``1``       — a bare tier. Still supported, still the common case.
    * ``{"tier": 1, "category": "api-reference",
         "reason": "...", "self_classifying": False}``
                          — the full read: genre label, one-sentence why, and
                            whether the document asks to be treated as
                            authoritative (rule 3, a model judgment not a regex).

    Unknown keys are ignored rather than rejected: the prompt-side read is the
    surface of record (`references/phase1_exploration_guide.md`), and a prompt
    that grows a field must not break ingest.
    """
    if result is None:
        return None, {}
    if isinstance(result, bool):        # bool is an int subclass — reject early
        raise ValueError(f"classifier returned a bool, expected a tier: {result!r}")
    if isinstance(result, int):
        return result, {}
    if isinstance(result, dict):
        tier = result.get("tier")
        if tier is not None and not isinstance(tier, int) or isinstance(tier, bool):
            raise ValueError(f"classifier read has a non-integer tier: {tier!r}")
        return tier, {
            "category": result.get("category"),
            "reason": result.get("reason"),
            "self_classifying": bool(result.get("self_classifying")),
        }
    raise ValueError(
        f"classifier must return a tier, None, or a read mapping; got {type(result).__name__}")


def classify_documents(
    docs: Sequence[Tuple[str, str]],
    *,
    llm_classifier: Optional[Callable] = None,
    sidecar: Optional[Sequence[Tuple[str, str]]] = None,
    advisory_rescues: Optional[Sequence[Tuple[str, str]]] = None,
    operator_decisions: Optional[Sequence[Tuple[str, str, str]]] = None,
    schema_version: str = "1.6.0",
    generated_at: Optional[str] = None,
) -> dict:
    """Classify a corpus into a reviewable, content-keyed classification manifest.

    ``docs`` is a sequence of ``(rel_path, text)``. Returns a manifest dict
    ``{schema_version, generated_at, classifier_status, citable_count,
    zero_citable, records[]}`` (+ ``classifier_error`` on failure), sorted by
    ``source_path``.

    ``llm_classifier`` is the derivation AI's per-file tier callable. It is called
    ``llm_classifier(rel_path, text)`` — or ``llm_classifier(rel_path, text,
    hints)`` when it accepts a third argument, where ``hints`` is
    ``{"advisory_hints": [...], "code_heavy": <str|None>}`` from the floor (a
    demotion input; the AI owns the genre judgment the floor no longer attempts).

    LOUD, not silent (instruction 024 / Fable Q6): the manifest records a
    ``classifier_status`` — ``unwired`` when no classifier is supplied, ``error``
    when the classifier raises (with ``classifier_error``), else ``wired-ok`` — so
    a whole-corpus Tier-4 collapse is never a quiet fallback. ``zero_citable`` is a
    structural tripwire: True when no record is Tier 1/2 after floors +
    classification.

    ``operator_decisions`` is the end-of-Phase-1 classification review's
    corrections (instr 030) as ``(rel_path, sha256, "authoritative"|"background")``
    triples, content-keyed exactly like ``advisory_rescues`` and ``sidecar``, and
    read from the same operator-authored file. A correction made after the first
    ingest takes effect on the re-run, and that re-run is what turns a promoted doc
    into a byte-citable ``FORMAL_DOC``. Later triples win over earlier ones for the
    same key.

    No cache (instruction 033 step 4). Every run RE-READS and re-derives. The
    content-keyed `prior_records` reuse is gone: the determinism it promised was
    half-fiction — the model's read varied run to run, which is why the
    end-of-Phase-1 confirmation exists — and it was the direct cause of the
    instruction-032 fix-1 footgun, where a cached `default-tier4` swallowed a live
    classifier and produced a silent `zero_citable` run. Re-reading 6-20 documents
    is cheap. What persists between runs is the operator's CONFIRMED DECISIONS
    (``reference_docs/qpb_decisions.txt``), which is a record of consent rather
    than a record of the machine's guesses.
    """
    # CONTENT-keyed ``(path, sha256)`` pairs, like ``advisory_rescues`` — an
    # operator acknowledges the BYTES they read, never the path. See the note in
    # ``reference_docs_ingest``: while this was a set of bare paths, swapping a
    # promoted file's contents inherited its promotion.
    sidecar_set = {tuple(entry) for entry in (sidecar or ())}
    # Operator advisory-floor rescues (instr 025), content-keyed by (path, sha256).
    # An advisory doc is lifted past the advisory floor ONLY when its (path, its
    # own content hash) is in this operator-authored set — never by content.
    rescue_set = set(advisory_rescues or ())
    # Operator classification-review decisions (instr 030), content-keyed the same
    # way. Built in order so a later line supersedes an earlier one for a key.
    operator_by_key: Dict[Tuple[str, str], str] = {}
    for entry in (operator_decisions or ()):
        op_path, op_sha, op_decision = entry
        if op_decision not in _OPERATOR_DECISIONS:
            raise ValueError(
                f"operator decision must be one of {sorted(_OPERATOR_DECISIONS)}, "
                f"got {op_decision!r} for {op_path!r}"
            )
        operator_by_key[(op_path, op_sha.lower())] = op_decision
    if generated_at is None:
        generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    wants_hints = _accepts_hints(llm_classifier) if llm_classifier is not None else False
    classifier_status = CLASSIFIER_UNWIRED if llm_classifier is None else CLASSIFIER_WIRED_OK
    classifier_error: Optional[str] = None

    records: List[dict] = []
    for rel_path, text in docs:
        sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
        rescued = (rel_path, sha) in rescue_set
        operator_decision = operator_by_key.get((rel_path, sha))
        llm_tier = None
        read: Dict[str, object] = {}
        if llm_classifier is not None:
            try:
                if wants_hints:
                    hints = {
                        "advisory_hints": advisory_genre_hints(text, rel_path),
                        "code_heavy": code_heavy_hint(text, rel_path),
                    }
                    result = llm_classifier(rel_path, text, hints)
                else:
                    result = llm_classifier(rel_path, text)
                llm_tier, read = _parse_read(result)
            except Exception as exc:   # a FAILED classifier is loud, not silent
                classifier_status = CLASSIFIER_ERROR
                if classifier_error is None:
                    classifier_error = f"{type(exc).__name__}: {exc}"
                llm_tier, read = None, {}
        decision = classify_document(
            rel_path, text, llm_tier=llm_tier,
            sidecar_promote=(rel_path, sha) in sidecar_set,
            advisory_rescue=rescued,
            operator_decision=operator_decision,
            self_classifying=bool(read.get("self_classifying")),
            category=read.get("category"),
            model_reason=read.get("reason"),
        )
        records.append(_record(rel_path, text, decision))

    records.sort(key=lambda r: r["source_path"])
    if llm_classifier is None and classifier_status == CLASSIFIER_UNWIRED:
        # No Python callback this pass. In the skill flow the derivation agent
        # classifies by REFINING the manifest (assigning Tier 1/2 + marking the
        # record RULE_LLM), reused content-keyed on the next ingest. So the corpus
        # IS classified when any record carries a classifier/agent-assigned tier;
        # only a purely floor-only corpus (no non-floor judgment anywhere) is
        # genuinely unwired and loud (instruction 024). Requires re-running ingest
        # after refinement so this reflects the agent's tiers.
        if any(r.get("floor_rule") == RULE_LLM for r in records):
            classifier_status = CLASSIFIER_WIRED_OK
    citable = [r for r in records if r.get("tier") in (1, 2)]
    # instruction 033 step 2 — corpus-level provenance, all DERIVED from the
    # per-document records (invariant 7: never a corpus-wide judgment a single
    # document could influence).
    unconfirmed = [r for r in citable if r.get("confirmation") == UNCONFIRMED]
    awaiting = [r for r in records
                if r.get("floor_rule") == RULE_CONFIRM_REQUIRED]
    manifest = {
        "schema_version": schema_version,
        "generated_at": generated_at,
        "classifier_status": classifier_status,
        "citable_count": len(citable),
        "zero_citable": len(citable) == 0,
        # How many citations rest on the model's read alone and so are disclosed
        # unconfirmed — the number the gate WARN and the show speak to.
        "unconfirmed_citable_count": len(unconfirmed),
        # Documents the backstop or a Lane-C signal routed to the operator. They
        # are NOT cited; this is the queue the confirmation step works through.
        "awaiting_confirmation_count": len(awaiting),
        "most_authoritative": _most_authoritative(records),
        "records": records,
    }
    if classifier_error is not None:
        manifest["classifier_error"] = classifier_error
    return manifest


def _most_authoritative(records: Sequence[dict]) -> Optional[str]:
    """The single most authoritative document, or ``None`` if none looks like one.

    §8a Revision rule 1 says the model "names its most-authoritative pick, or says
    none looks like a spec" — and invariant 7 says that pick must be DERIVED from
    the per-document categories rather than asked as a corpus-wide question, or it
    becomes a cross-document injection surface the per-file floors never had.

    So this is a pure function of the per-doc records, ordered by how much the
    standing rests on evidence rather than judgment:

      1. Lane A — the content validated as a contract format. A structural fact.
      2. Lane operator — a human said so.
      3. Lane B — the model's read, best (lowest) tier first.

    Ties break on the path, never on size: size ordering is what named a 45 KB
    style guide as the operator's specification in instruction 031.
    """
    def rank(rec):
        lane = rec.get("lane")
        band = {LANE_CONTENT_VALIDATED: 0, LANE_OPERATOR: 1,
                LANE_MODEL_READ: 2}.get(lane)
        if band is None or rec.get("tier") not in (1, 2):
            return None
        return (band, rec.get("tier") or 9, str(rec.get("source_path") or ""))

    ranked = sorted((r for r in records if rank(r) is not None), key=rank)
    return str(ranked[0].get("source_path")) if ranked else None


def citable_records(manifest: dict) -> List[dict]:
    """The Tier-1/2 records — the citable subset the formal-doc manifest is built from."""
    return [r for r in manifest.get("records", []) if r.get("tier") in (1, 2)]


def classification_disclosure(manifest: dict) -> Optional[str]:
    """A LOUD one-paragraph disclosure when classification was degraded (unwired /
    failed classifier) OR the corpus yielded no citable doc — else None.

    The single source of the wording that instruction 024 renders into the spec
    Overview (beside the F-1 coverage-and-gaps statement), raises as a gate WARN,
    and plays back at interview Stage 1. A degraded classification is a disclosed
    event, never a quiet fallback.
    """
    status = manifest.get("classifier_status")
    parts: List[str] = []
    if status == CLASSIFIER_UNWIRED:
        parts.append(
            "The document classifier did not run this pass — every non-floored "
            "document defaulted to Tier 4 (background), so citable grounding may be "
            "understated. Wire the classifier and re-run to tier the corpus."
        )
    elif status == CLASSIFIER_ERROR:
        parts.append(
            "The document classifier FAILED this pass ({}) — affected documents "
            "defaulted to Tier 4 (background); classification is degraded.".format(
                manifest.get("classifier_error", "error"))
        )
    if manifest.get("zero_citable"):
        parts.append(
            "No authoritative contract (Tier 1/2) was found in the gathered docs: "
            "all requirements will be code-derived. Confirm this is expected — a "
            "missing or mis-tiered spec produces the same signature."
        )
    # instruction 033 step 2 — the two three-lane facts the gate has to raise.
    # A Lane-B citation is real grounding, but it rests on the model's read alone,
    # so a run that ships requirements citing one has to say so: that is what
    # makes reworded invariant 1 ("always disclosed unconfirmed until the operator
    # confirms") true at the gate and not only in the show.
    unconfirmed = manifest.get("unconfirmed_citable_count") or 0
    if unconfirmed:
        parts.append(
            "{n} cited document{s} rest{v} on the model's own genre read and "
            "{is_} still UNCONFIRMED by the operator — grounding is real but "
            "unreviewed; the end-of-Phase-1 confirmation upgrades it.".format(
                n=unconfirmed, s="" if unconfirmed == 1 else "s",
                v="s" if unconfirmed == 1 else "", is_="is" if unconfirmed == 1 else "are")
        )
    # instruction 033 step 3: a corpus still carrying a superseded control file has
    # operator decisions that are NOT being applied. That is exactly the class of
    # thing this disclosure exists for, so it rides the same channel as a degraded
    # classification rather than living only in the manifest.
    note = manifest.get("conversion_note")
    if note:
        parts.append(note)
    refused = manifest.get("refused_promotions") or []
    if refused:
        parts.append(
            "{n} operator promotion{s} {was} REFUSED for want of a named signal "
            "({paths}) — the document carries a hard signal and the reason did not "
            "name it, so it is not being quoted.".format(
                n=len(refused), s="" if len(refused) == 1 else "s",
                was="was" if len(refused) == 1 else "were",
                paths=", ".join(refused)))
    awaiting = manifest.get("awaiting_confirmation_count") or 0
    if awaiting:
        parts.append(
            "{n} document{s} {is_} held back pending operator confirmation (a hard "
            "signal barred silent citing) and {is_} NOT being quoted.".format(
                n=awaiting, s="" if awaiting == 1 else "s",
                is_="is" if awaiting == 1 else "are")
        )
    return " ".join(parts) if parts else None


def classification_playback(manifest: dict) -> List[dict]:
    """Interview Stage-1 playback: each classified doc with a human-readable
    status (citable / defaulted-tier4 / floored-tier4 / advisory-rescued) + its
    reason, so the "reviewable under-block" the simplification promises actually
    gets reviewed — including every operator advisory-floor rescue (instr 025).
    """
    out: List[dict] = []
    for r in manifest.get("records", []):
        tier = r.get("tier")
        if r.get("advisory_rescued"):
            # An operator lifted the advisory floor on this doc — always surfaced,
            # regardless of the tier the classifier then assigned it.
            status = "advisory-rescued"
        elif r.get("floor_rule") == RULE_OPERATOR_AUTHORITATIVE:
            status = "operator-authoritative"   # the operator said "this IS my spec"
        elif r.get("floor_rule") == RULE_OPERATOR_BACKGROUND:
            status = "operator-background"      # the operator said "background only"
        elif r.get("floor_rule") == RULE_CONFIRM_REQUIRED:
            # instruction 033 step 2 — Lane C. Distinct from a floored document:
            # nothing has been decided, the operator has been asked.
            status = "awaiting-confirmation"
        elif tier in (1, 2) and r.get("confirmation") == UNCONFIRMED:
            # Lane B — cited, but on the model's read alone.
            status = "cited-unconfirmed"
        elif tier in (1, 2):
            status = "citable"
        elif r.get("floor_rule") == RULE_DEFAULT:
            status = "defaulted-tier4"     # no classifier tier — under-block risk
        else:
            status = "floored-tier4"       # a floor barred it (advisory/impl/…)
        entry = {
            "source_path": r.get("source_path"),
            "tier": tier,
            "status": status,
            "reason": r.get("reason"),
            "advisory_hints": r.get("advisory_hints", []),
            "code_heavy": r.get("code_heavy"),
        }
        if r.get("advisory_rescued"):
            entry["rescued_reason"] = r.get("rescued_reason")
        if r.get("operator_decision"):
            entry["operator_decision"] = r.get("operator_decision")
        for key in ("lane", "confirmation", "category", "model_reason", "backstop"):
            if r.get(key):
                entry[key] = r.get(key)
        out.append(entry)
    return out


# ---------------------------------------------------------------------------
# The end-of-Phase-1 classification review (instruction 030) — the SHOW.
#
# The operator gathered the documents, so the operator is the right person to say
# "that one IS my spec." This renders the classification in the operator's own
# language before Phase 2 derives anything against it. The plain-language standard
# (QPB_v1.6.0_UX_Language_Draft.md) is a hard contract here: NO internal label —
# no "Tier N", no "citable", no "floored", no "manifest", no "Feature G" — reaches
# the operator. Every reason below is GENERATED from the decision, never passed
# through from a record's internal ``reason`` string (which is dev-facing and
# does carry those labels).
# ---------------------------------------------------------------------------

# Plain-language reason per decision rule, split by which side of the line the
# document landed on. Keyed by floor_rule; the tier picks the sub-map.
_AUTHORITATIVE_REASONS = {
    RULE_OPERATOR_AUTHORITATIVE: "you told me this one is a source I should use.",
    RULE_SIDECAR: "you told me to use this one even though it looks like source code.",
    # instruction 032 self-Council, Panelist B (defensive sweep, same class as
    # fix 2): the carve-out can fire on the EXTENSION alone, so `notes.thrift`
    # holding meeting notes was presented as "it's a machine-readable interface
    # definition… a direct statement of what this software is supposed to do."
    # Naming the FORMAT as the signal is both true and the thing that lets an
    # operator catch it — this is the authoritative side of the show, and their
    # demotion at this step is unconditional. (That a non-contract can reach
    # Tier 1 on an extension is a CARVE-OUT question, not a wording one; tiers
    # are out of scope here and it is carried forward in the output.)
    # (Round 2, Panelist B: "its format is…" still claims the BYTES when only the
    # suffix was read — `notes.thrift` is prose. Round 3, Panelist B: naming the
    # EXTENSION alone then over-corrected, because the carve-out has two arms and
    # the other one is the content-verified, canonical OpenAPI case —
    # `openapi.yaml` matches `openapi: "3` INSIDE the file and `.yaml` is not a
    # contract extension at all. Describing the safe arm with the unsafe arm's
    # mechanism also creates a false-DEMOTION path for the audit instruction in
    # `phase1_exploration_guide.md`: an agent checks `.yaml`, finds no contract
    # extension, and demotes a real spec. Name both arms.)
    # instruction 033 step 1 deleted the EXTENSION arm, so naming it here became
    # false: Lane A is now reached only by validating the format INSIDE the file.
    # (The 032 Council spent four rounds on this string precisely because a reason
    # that names a signal the code no longer uses is the same defect class as one
    # that asserts a genre the signal does not establish.)
    RULE_CONTRACT: (
        "I recognised an interface-definition format inside it — the kind of file "
        "that states directly what this software is supposed to do."
    ),
    RULE_LLM: "I read it as a statement of what this software is supposed to do.",
}
_BACKGROUND_REASONS = {
    # (instruction 033 step 4: the `advisory-floor`, `impl-floor` and
    # `background-ledger` entries are DELETED with their rules. Step 2 stopped
    # producing them and they survived only for a cached pre-033 record; step 4
    # removed the cache, so nothing can render them.)
    RULE_OPERATOR_BACKGROUND: "you told me to treat this one as background only.",
    # instruction 033 step 2 — Lane C. NOT background: the document is held back
    # from being quoted until the operator answers, and the show has to read as a
    # question rather than a verdict. The specific signal (a CVE identifier, an
    # advisory link, a contract extension with no readable format inside) is named
    # separately by the confirmation step, which is where the operator has to
    # acknowledge it by name.
    RULE_CONFIRM_REQUIRED: (
        "I can't tell from the file itself whether this is one of your sources, so "
        "I'm not quoting it until you tell me."
    ),
    RULE_DEFAULT: (
        "nothing identified it as a statement of what this software is supposed to do."
    ),
    RULE_LLM: (
        "I read it as explaining or describing the software rather than stating what "
        "it must do."
    ),
}
_FALLBACK_BACKGROUND_REASON = (
    "I'm reading it for context rather than quoting it as a source."
)
# The two advisory-RESCUE arms of `_review_reason`. Module-level constants rather
# than inline literals because inline literals cannot be pinned: instruction 032
# self-Council round 3, Panelist B, went looking for a way to reintroduce the
# false genre claim fix 2 deleted and found it here — appending "It is a security
# advisory and it describes known problems, not what your software is supposed to
# do." to the arm below left ALL 159 tests green, because the pins reach only the
# two reason MAPS and `grep -rn "cleared this one for use" bin/tests/` returned
# nothing. It renders to the one operator who has most earned an accurate
# sentence: the one who authored the 025 rescue themselves.
_RESCUED_AUTHORITATIVE_REASON = (
    "you confirmed this is your real specification even though it mentions "
    "security advisories."
)
_RESCUED_BACKGROUND_REASON = (
    "you cleared this one for use, but I still read it as background rather than "
    "a specification."
)
# The renderer's own operator-facing prose. Constants for the same reason the two
# rescue arms are: an inline literal is pinnable by nothing, and instruction 032
# self-Council round 5, Panelist B, mutated all three of these into false genre
# claims that evaded every forbidden substring with the whole test file green.
# ``_ZERO_AUTHORITATIVE_BANNER`` is the most consequential string in this module —
# it IS the virtio signature, the message that tells an operator no document is
# being used as a source.
_NO_DOCUMENTS_MESSAGE = (
    "I didn't find any documentation to read this run, so every requirement "
    "will be drawn from the code itself. If you have a specification, an "
    "RFC, or an API reference, add it and I can use it as a source."
)
_ZERO_AUTHORITATIVE_BANNER = (
    "**None of your documents are being used as authoritative sources this "
    "run — every requirement will be drawn from the code.** If one of these "
    "*is* your specification — the document that says what this software is "
    "supposed to do — tell me which one and I'll use it that way."
)
_REFUSED_PROMOTION_NOTE = (
    " You asked me to use this one as a source; I'm not, for the reason above."
)
# The `cite/` shim's promise, kept in the operator's own words. §8a Revision calls
# these entries "clearly-labelled, revocable", and until fix-up 2 they were neither
# in the show: a `cite/`-placed document rendered as "you told me this one is a
# source", indistinguishable from a decision the operator had actually made and
# with no hint that the folder is going away. Placement is a WEAKER claim than a
# confirmation — it is where a file happens to sit — so it says which it is.
_CITE_FOLDER_REASON = (
    "you put it in the folder for documents you want quoted as sources. "
    "Move it out of that folder if that's not right — and that folder is going "
    "away next release, so it's worth telling me directly instead."
)
# instruction 033 step 2 — the operator-language form of a Lane-B `unconfirmed`
# citation. The word "unconfirmed" is itself internal jargon (invariant 8), so the
# status reaches the operator as what it MEANS: I made this call, it is mine and
# not yours, and you can overrule it. Appended to a Lane-B authoritative reason so
# no citation on the model's read alone reads as settled.
_UNCONFIRMED_NOTE = " That was my own call — tell me if I've got it wrong."

# A path is interpolated straight into operator-facing Markdown, and a document's
# *filename* is attacker-influenced surface just like its content. A newline in a
# filename would otherwise let a document forge its own "Authoritative sources"
# heading in the show (instr 030 self-Council, Panelist A).
# Covers the C0/C1 control ranges plus the Unicode line/paragraph separators and
# the bidi overrides — U+2028/U+2029/U+0085 are line breaks to some renderers, and
# a bidi override can visually reorder a path so it reads as a different file
# (instr 030 self-Council, Panelist A). The backtick closes the code span.
_UNSAFE_PATH_CHARS_RE = re.compile(
    "[\x00-\x1f\x7f-\x9f`  ‎‏‪-‮⁦-⁩]"
)
_MAX_SHOWN_PATH = 160

# Instruction 031 fix 1 — the worked example must never confidently name a
# document that is not plausibly a specification, and must never use SIZE as the
# signal: on the real virtio corpus the largest promotable background document is
# ``linux-coding-style.rst`` (a 45 KB style guide) while the actual spec,
# ``virtio-spec-behavioral-contracts.md``, is 7.8 KB — so the feature built to help
# the operator recover a mis-classified spec was suggesting they promote a STYLE
# GUIDE as their specification. Instruction 031 answered that with a filename-token
# signal; instruction 033 replaces the tokens with the model's own category, which
# is the read those tokens were approximating. Size survives nowhere.
# instruction 033 step 2 — the categories the model may use that make a document
# a CANDIDATE for the operator to promote. This replaces the deleted
# `_SPEC_NAME_TOKENS` / `_NON_SPEC_NAME_TOKENS` filename tables: the signal is now
# what the model read the document to BE, not what it is called.
# The honest blank: shown instead of a filename whenever nothing the operator
# could promote reads as even a candidate specification. A confident wrong answer
# is worse than no answer (instruction 031 fix 1).
_NEUTRAL_EXAMPLE = "<the-file>"

_SPEC_CANDIDATE_CATEGORIES = frozenset({
    "authoritative-spec", "specification", "spec",
    "api-reference", "reference",
    "rfc", "standard", "protocol", "contract",
    "candidate-spec",
})

def _safe_path(path: Optional[str]) -> str:
    """A document path, rendered inert for the operator-facing show.

    A document's *filename* is attacker-influenced surface exactly like its
    content, so it is neutralized before it reaches the operator: nothing in it
    can close its code span, start a new line, reorder itself visually, or run
    long enough to bury the rest of the block.
    """
    safe = _UNSAFE_PATH_CHARS_RE.sub("?", str(path or ""))
    if len(safe) > _MAX_SHOWN_PATH:
        safe = safe[:_MAX_SHOWN_PATH - 1] + "…"
    return safe


def _is_cite_placed(source_path: Optional[str]) -> bool:
    """True when the document sits directly in ``reference_docs/cite/``.

    ``cite/`` placement is the operator's explicit pre-classification, and
    ``reference_docs_ingest._formal_tier`` honors it over the classifier's tier —
    so the show has to honor it too, or it tells the operator a document is
    background while the pipeline quotes it (instr 030 self-Council, Panelist B).
    """
    parts = str(source_path or "").split("/")
    return len(parts) >= 2 and parts[-2] == "cite"


def _is_authoritative(rec: dict) -> bool:
    """Whether the pipeline will actually treat this document as a citable source.

    This mirrors ``reference_docs_ingest._formal_tier`` exactly — citable iff the
    floor left it ``promotable`` AND (it is ``cite/``-placed, whose in-file marker
    always resolves to Tier 1/2, OR its classified tier is 1/2). Splitting the
    show on tier alone got both directions wrong: a ``cite/`` document the
    classifier read as background is quoted anyway, and a Tier-1 record the floor
    barred (``promotable: false``) is not.
    """
    # `.get("promotable", False)`, NOT `is False` — an absent key must read as
    # not-citable, exactly as `_formal_tier` reads it. With `is False` a record
    # missing the key rendered as an authoritative source while the pipeline
    # produced no FORMAL_DOC for it (instr 030 self-Council, Panelists B + C).
    if not rec.get("promotable", False):
        return False
    return _is_cite_placed(rec.get("source_path")) or rec.get("tier") in (1, 2)


def _review_reason(entry: dict, authoritative: bool) -> str:
    """The one-line plain reason for one document in the review."""
    rule = entry.get("floor_rule")
    if authoritative:
        if entry.get("status") == "advisory-rescued":
            return _RESCUED_AUTHORITATIVE_REASON
        # Placement explains the citation whatever the tier. The `tier not in
        # (1, 2)` guard used to stand here, which meant the shim announced itself
        # ONLY for a document the classifier had also read as background — so the
        # one case it was built for, a prose file the operator dropped in `cite/`
        # and thereby promoted, rendered as an ordinary confirmed decision.
        if _is_cite_placed(entry.get("source_path")):
            return _CITE_FOLDER_REASON
        base = _AUTHORITATIVE_REASONS.get(
            rule, "I read it as a statement of what this software is supposed to do.")
        # A Lane-B citation rests on the model's read alone, so it is never
        # presented as settled (reworded invariant 1).
        if entry.get("confirmation") == UNCONFIRMED:
            base += _UNCONFIRMED_NOTE
        return base
    if entry.get("status") == "advisory-rescued":
        return _RESCUED_BACKGROUND_REASON
    return _BACKGROUND_REASONS.get(rule, _FALLBACK_BACKGROUND_REASON)


def classification_review(
    manifest: dict, *, offer: bool = True,
    formal_records: Optional[Sequence[dict]] = None,
) -> str:
    """The end-of-Phase-1 show: how each gathered document is being used, in the
    operator's language, plus the invitation to correct it (instruction 030).

    Always rendered — the disclosure is not skippable. ``offer=False`` is the
    continuous-run case: the show is identical, only the *pause* is dropped, so a
    run that never stops at a phase boundary still discloses the classification it
    is about to derive requirements against.

    ``formal_records`` is ``quality/formal_docs_manifest.json``'s ``records`` when
    the caller has it (the ingest writes it in the same pass). It is the **ground
    truth** for what the pipeline will actually quote, so supplying it makes the
    show correct by construction rather than by agreement. Without it the show
    reproduces the same rule ``_formal_tier`` applies (see ``_is_authoritative``).

    Returns Markdown ready to print in chat. Contains no internal labels.
    """
    formal_paths = (None if formal_records is None
                    else {r.get("source_path") for r in formal_records})
    entries = []
    for entry, rec in zip(classification_playback(manifest),
                          manifest.get("records", [])):
        merged = dict(entry)
        merged["floor_rule"] = rec.get("floor_rule")
        merged["promotable"] = rec.get("promotable")
        merged["byte_count"] = rec.get("byte_count")
        # instruction 033 step 2 — the three-lane provenance the show speaks to.
        merged["lane"] = rec.get("lane")
        merged["confirmation"] = rec.get("confirmation")
        merged["category"] = rec.get("category")
        merged["backstop"] = rec.get("backstop") or []
        merged["_authoritative"] = (
            rec.get("source_path") in formal_paths if formal_paths is not None
            else _is_authoritative(rec)
        )
        entries.append(merged)

    lines: List[str] = ["### The documents you gave me"]
    if not entries:
        lines.append("")
        lines.append(_NO_DOCUMENTS_MESSAGE)
        return "\n".join(lines)

    authoritative = [e for e in entries if e["_authoritative"]]
    # instruction 033 step 2 — Lane C is its OWN section, not background. Listing a
    # document the machine could not judge under "I read these, but I won't quote
    # them" states a verdict where the honest surface is a question, and it is the
    # silent-background half of what §8a Revision Fable must-fix 2 forbids.
    awaiting = [e for e in entries
                if not e["_authoritative"]
                and e.get("floor_rule") == RULE_CONFIRM_REQUIRED]
    background = [e for e in entries
                  if not e["_authoritative"]
                  and e.get("floor_rule") != RULE_CONFIRM_REQUIRED]

    lines.append("")
    lines.append(
        f"I read {len(entries)} document{'' if len(entries) == 1 else 's'} and decided "
        "how to use each one. Here's what I settled on, before I turn any of it into "
        "requirements."
    )

    if not authoritative:
        lines.append("")
        lines.append(_ZERO_AUTHORITATIVE_BANNER)

    if authoritative:
        lines.append("")
        lines.append("**Authoritative sources your requirements can cite**")
        for e in authoritative:
            lines.append(f"- `{_safe_path(e['source_path'])}` — {_review_reason(e, True)}")

    if awaiting:
        lines.append("")
        lines.append("**I need your word on these before I quote them**")
        for e in awaiting:
            detail = "; ".join(b.get("detail", "") for b in (e.get("backstop") or [])
                               if b.get("detail"))
            line = f"- `{_safe_path(e['source_path'])}` — {_review_reason(e, False)}"
            if detail:
                # Name the specific evidence: step 3's confirmation requires the
                # operator to acknowledge it, so they have to be shown it first.
                line += f" What I found: {detail}."
            if e.get("operator_decision") == OPERATOR_AUTHORITATIVE:
                # instruction 031: a REFUSED promotion is stated, never dropped.
                # The operator asked for this document and did not get it (they
                # named it without acknowledging the signal), so the show has to
                # say so — otherwise the system looks like it ignored them. This
                # note lived only in the background loop until instruction 033
                # step 2 moved these documents into their own section, which
                # silently took the refusal notice with them.
                line += _REFUSED_PROMOTION_NOTE
            lines.append(line)

    if background:
        lines.append("")
        lines.append("**Background context — I read these, but I won't quote them**")
        for e in background:
            note = _review_reason(e, False)
            if (e.get("operator_decision") == OPERATOR_AUTHORITATIVE
                    and e.get("floor_rule") != RULE_OPERATOR_AUTHORITATIVE):
                # An operator promotion the advisory / README rule refused — say so
                # plainly instead of dropping it silently.
                note += _REFUSED_PROMOTION_NOTE
            lines.append(f"- `{_safe_path(e['source_path'])}` — {note}")

    lines.append("")
    # Name a document the operator could actually promote — one the classifier
    # merely read as background, not one an absolute rule pinned there. A README
    # or an advisory CANNOT be promoted at this step, so naming one as the worked
    # example is a suggestion that is guaranteed to no-op (instr 030 self-Council,
    # Panelists B + C). When there is no promotable background document, ask the
    # open question instead of naming a file.
    # Among the promotable ones, name a document that plausibly IS a
    # specification — never one whose only qualification is being the largest
    # (instruction 031 fix 1). Size ordering alone picked the 45 KB
    # `linux-coding-style.rst` over the 7.8 KB `virtio-spec-behavioral-contracts.md`
    # on the real virtio corpus, i.e. it told the operator to promote a style
    # guide as their specification. Size survives only as the tie-break BETWEEN
    # spec-like candidates, where it still answers the instr-030 Panelist-B
    # finding (the alphabetical pick was a 125-byte toctree stub).
    # "Could the operator promote this one at this step?" stated directly: every
    # background document EXCEPT the two absolutely-floored classes. The earlier
    # allow-list of rules was both under-inclusive (it excluded implementation-
    # floored documents, which this step's decision CAN lift — the same power the
    # path-keyed sidecar grants) and carried a dead entry (instr 030 self-Council,
    # Panelists B + C).
    # ...and never a document the OPERATOR themself put here. An instr-030
    # demotion ("that one is just background") is exactly the case the new name
    # signal seeks out — operators demote the files that LOOK spec-shaped — so
    # without this the block contradicts itself four lines apart: "you told me to
    # treat this one as background only" … "treat `virtio-spec-contracts.md` as
    # my specification" (instr 031 self-Council round 2, Panelist A). Keyed on
    # the rule, NOT on `promotable`: RULE_IMPL also carries `promotable=False`,
    # and filtering on that would silently re-close the code-shaped-contract
    # affordance instr 030 opened.
    # ``RULE_OPERATOR_AUTHORITATIVE``/``RULE_CONTRACT`` ride along for the same
    # reason: with a stale ``formal_records`` an already-authoritative document
    # can appear on the background side, and inviting the operator to promote
    # what they already promoted reads as the system not listening (instr 031
    # self-Council round 3, Panelist A — low reachability, free to close).
    promotable_bg = [e for e in background
                     if e.get("floor_rule") not in (RULE_OPERATOR_BACKGROUND,
                                                    RULE_OPERATOR_AUTHORITATIVE,
                                                    RULE_CONTRACT)
                     and e.get("promotable", False)]
    # instruction 033 step 2: the pick comes from the MODEL'S CATEGORY, not from a
    # filename-token table. `_SPEC_NAME_TOKENS` / `_NON_SPEC_NAME_TOKENS` are
    # deleted — they were the mechanical layer approximating a read from filenames,
    # badly, and they produced exactly the defect instruction 031 had to fix (a
    # 45 KB style guide named as the operator's specification because size broke
    # the tie among "spec-like" names).
    #
    # Per-document isolation (invariant 7) is why this is derived HERE rather than
    # asked of the model as a corpus-wide question: each category came from that
    # document's own content, so no document can influence another's standing —
    # and a hostile line in one file cannot move the pick.
    def _rank(entry):
        cat = (entry.get("category") or "").strip().lower()
        # A document the model called a candidate spec outranks one it had no
        # opinion about; anything it positively categorized as background ranks
        # last and is never named.
        if cat in _SPEC_CANDIDATE_CATEGORIES:
            band = 0
        elif not cat:
            band = 1
        else:
            band = 2
        return (band, str(entry.get("source_path") or ""))

    ranked = sorted(promotable_bg, key=_rank)
    named = [e for e in ranked if _rank(e)[0] == 0]
    if named:
        example = _safe_path(named[0]["source_path"])
    elif ranked:
        # There IS something the operator could promote, but nothing the model read
        # as even a candidate specification — so illustrate the phrasing without
        # asserting which of their documents is the spec. Naming one anyway is the
        # 031 defect: a confident wrong answer is worse than an honest blank.
        example = _NEUTRAL_EXAMPLE
    else:
        # Nothing is promotable at this step at all — ask the open question
        # rather than offer a suggestion guaranteed to no-op (instr 030).
        example = None
    if offer:
        if example:
            lines.append(
                "**Is that right?** You gathered these, so you're the one who knows. "
                "If I've got one wrong, just say which one and how — the wording I "
                f"understand looks like *\"treat `{example}` as my specification\"* "
                "or *\"that one is just background\"*. I'll redo this before "
                "deriving anything. Otherwise say **keep going**."
            )
        else:
            lines.append(
                "**Is that right?** You gathered these, so you're the one who knows. "
                "If one of them should be used differently, tell me which and how — "
                "and I'll redo this before deriving anything. Otherwise say "
                "**keep going**."
            )
    else:
        if example:
            lines.append(
                "I'm continuing without stopping, so this is what I'll derive the "
                "requirements against. If one of these should be used as a source, "
                "tell me at any point — the wording I understand looks like "
                f"*\"treat `{example}` as my specification\"* — and I'll redo it."
            )
        else:
            lines.append(
                "I'm continuing without stopping, so this is what I'll derive the "
                "requirements against. Tell me at any point if one of these should "
                "be used differently and I'll redo it."
            )
    return "\n".join(lines)
