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
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional, Sequence, Tuple

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
RULE_ADVISORY = "advisory-floor"
RULE_IMPL = "impl-floor"
RULE_SIDECAR = "sidecar-promotion"
RULE_INJECTION = "injection-floor"
RULE_CONTRACT = "contract"
RULE_LLM = "llm"
RULE_DEFAULT = "default-tier4"
RULE_BACKGROUND = "background-ledger"
# v1.6.0 instruction 030 — the end-of-Phase-1 classification review. The operator
# looked at how each gathered document was being used and said "that one IS my
# spec" (or "that one is only background"). Operator-authored and content-keyed,
# exactly like the instr-025 advisory rescue: document content, the classifier,
# and a persona can NEVER produce one of these.
RULE_OPERATOR_AUTHORITATIVE = "operator-authoritative"
RULE_OPERATOR_BACKGROUND = "operator-background"

# The two decisions an operator may record at the end-of-Phase-1 review.
OPERATOR_AUTHORITATIVE = "authoritative"
OPERATOR_BACKGROUND = "background"
_OPERATOR_DECISIONS = frozenset({OPERATOR_AUTHORITATIVE, OPERATOR_BACKGROUND})

# The ABSOLUTE floor rules — a decision under any of these bars citability.
# (default-tier4 is NOT absolute: it just means "no classifier tier was
# assigned", which a later run's LLM may raise.)
_ABSOLUTE_FLOOR_RULES = frozenset(
    {RULE_ADVISORY, RULE_IMPL, RULE_BACKGROUND}
)
# The UNRESCUABLE floor rules — a subset that NOTHING reverses: not the LLM, a
# rename, the operator sidecar, or a reused prior-manifest record. The
# implementation floor is deliberately EXCLUDED because it is legitimately
# rescued by the operator sidecar / cite/ placement; advisory and background are
# absolute regardless of any override. On a cache hit these are re-decided from
# content and the fresh floored decision always wins, so a poisoned prior
# manifest cannot keep an unrescuable-floored doc citable OR promotable
# (instruction 011 self-Council Panelist A). (The injection floor was removed in
# instruction 023 — the LLM owns the self-authorizing-tier judgment, and the
# grounding-layer directive check + Tier-1/2 guard are the load-bearing backstop
# on the auto-apply path; RULE_INJECTION is no longer produced.)
_UNRESCUABLE_FLOOR_RULES = frozenset(
    {RULE_ADVISORY, RULE_BACKGROUND}
)
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

# §8a item 7: README and the coverage / issue-tracker ledgers are background
# and stay Tier 4 — the classifier cannot promote them. (An advisory-signature
# README is still caught by the advisory floor first.) The coverage arm is
# EXACT stems (``coverage`` / ``coverage_report``), not the old free-floating
# ``*coverage*`` substring, so a real spec whose name merely contains "coverage"
# (e.g. ``test-coverage-requirements.md``) is not floored as background
# (instruction 023).
_BACKGROUND_NAME_RE = re.compile(
    r"^(?:readme|coverage(?:[_-]report)?|issue[_-]?tracker[^/]*)\.(?:md|txt|rst)$",
    re.IGNORECASE,
)


def _is_background_ledger(rel_path: str) -> bool:
    return bool(_BACKGROUND_NAME_RE.match(rel_path.rsplit("/", 1)[-1]))

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
_CONTRACT_EXTS = frozenset(
    {".proto", ".wsdl", ".graphql", ".graphqls", ".raml", ".thrift", ".idl"}
)
# ANCHORED, unambiguous signatures ONLY (instruction 023 / Fable Q7 — the best
# single cut). A bare ``"$schema"`` key promotes arbitrary JSON configs, and a
# generic ``type Query {`` / ``schema {`` brace-block promotes arbitrary brace
# text — both the dangerous UPWARD (integrity) direction, so both are deleted.
# openapi/swagger require their version anchor. Nothing becomes citable on
# content-sniffing alone beyond these hard, self-identifying format markers.
_CONTRACT_CONTENT_RE = re.compile(
    r'syntax\s*=\s*"proto[23]?"'                        # protobuf
    r'|"openapi"\s*:\s*["\']?3|openapi\s*:\s*["\']?3'   # OpenAPI 3 (version-anchored)
    r'|"swagger"\s*:\s*["\']?2|swagger\s*:\s*["\']?2'   # Swagger 2 (version-anchored)
    r'|"asyncapi"\s*:|asyncapi\s*:'                      # AsyncAPI
    r"|<wsdl:|<definitions[^>]*wsdl",                    # WSDL
    re.IGNORECASE | re.MULTILINE,
)


def machine_readable_contract(text: str, filename: str) -> Optional[str]:
    """Return a reason if *filename*/*text* is an interface/contract definition."""
    lower = filename.lower()
    if lower.endswith(".d.ts"):
        return "TypeScript declaration file (.d.ts)"
    for ext in _CONTRACT_EXTS:
        if lower.endswith(ext):
            return f"contract-definition extension {ext}"
    m = _CONTRACT_CONTENT_RE.search(text)
    if m:
        return f"contract signature {m.group(0).strip()!r}"
    return None


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


def classify_document(
    rel_path: str,
    text: str,
    llm_tier: Optional[int] = None,
    sidecar_promote: bool = False,
    advisory_rescue: bool = False,
    operator_decision: Optional[str] = None,
) -> Decision:
    """Classify one document to a Decision, enforcing the floor in priority order.

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
      and content-keyed like the advisory rescue; the classifier, a persona, and
      document content can never produce one. Its **upward** power stops exactly
      where the sidecar's does: it may lift the *implementation* floor (the same
      operator power ``qpb_promote.txt`` already grants, keyed on content rather
      than path) but it may **never** lift the advisory floor (that needs the
      instr-025 rescue, which acknowledges the specific signal being overridden)
      or the background-ledger floor. The downward direction is unconditional.

    Advisory genre-title hints and the code-heavy hint are attached to the
    returned Decision (they inform the LLM/manifest; they never floor or promote).
    """
    if operator_decision is not None and operator_decision not in _OPERATOR_DECISIONS:
        raise ValueError(
            f"operator_decision must be one of {sorted(_OPERATOR_DECISIONS)} or None, "
            f"got {operator_decision!r}"
        )
    decision = _classify(
        rel_path, text, llm_tier=llm_tier, sidecar_promote=sidecar_promote,
        advisory_rescue=advisory_rescue, operator_decision=operator_decision,
    )
    decision.operator_decision = operator_decision
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
) -> Decision:
    # 1. Advisory floor FIRST — HARD signals only (CVE/GHSA id, advisory URL),
    #    content-keyed, before any extension carve-out or sidecar. An advisory
    #    reaches classification ONLY via an operator-authored, content-keyed rescue
    #    (advisory_rescue, instr 025) — never by the classifier or document content.
    adv = advisory_floor(text, rel_path)
    if adv and not advisory_rescue:
        return Decision(4, RULE_ADVISORY, f"advisory (hard signal): {adv}", False)

    # README / coverage / issue-tracker ledgers are background — pinned Tier 4
    # (§8a item 7); the classifier cannot promote them.
    if _is_background_ledger(rel_path):
        return Decision(4, RULE_BACKGROUND, "README/coverage/ledger stays Tier 4 background", False)

    # 1b. Operator DEMOTION (instr 030) — the human looked at the end-of-Phase-1
    #     review and said "that one is background, don't quote it." Downward only,
    #     so it needs no guard; it runs before the promoting branches so it wins
    #     over the contract carve-out and the classifier alike.
    if operator_decision == OPERATOR_BACKGROUND:
        return Decision(
            4, RULE_OPERATOR_BACKGROUND,
            "operator marked this document background at the classification review",
            False,
        )

    contract = machine_readable_contract(text, rel_path)
    impl = implementation_source(text, rel_path)
    operator_authoritative = operator_decision == OPERATOR_AUTHORITATIVE

    # 2. Implementation floor — the code-EXTENSION floor only (a machine-readable
    #    contract is exempt). The old non-extension content sniff is now a hint.
    #    The operator's classification-review promotion (instr 030) rescues this
    #    floor exactly as the path-keyed sidecar does — the same operator power,
    #    keyed on content instead of on path. It does NOT reach the advisory or
    #    background-ledger floors above, which already returned.
    if impl and not contract:
        if sidecar_promote or operator_authoritative:
            tier = llm_tier if llm_tier in (1, 2) else 1
            if operator_authoritative:
                return Decision(
                    tier, RULE_OPERATOR_AUTHORITATIVE,
                    "operator named this document authoritative at the "
                    f"classification review, past the implementation floor ({impl})",
                    True,
                )
            return Decision(
                tier, RULE_SIDECAR,
                f"operator-sidecar promotion past implementation floor ({impl})",
                True,
            )
        return Decision(4, RULE_IMPL, f"implementation-source floor: {impl}", False)

    # 3. Machine-readable contract — citable without override.
    if contract:
        tier = llm_tier if llm_tier in (1, 2) else 1
        return Decision(tier, RULE_CONTRACT, f"machine-readable contract: {contract}", True)

    # 3b. Operator PROMOTION on a floor-passed document (instr 030) — the virtio
    #     case: a genuine spec the classifier read as background. The operator is
    #     the one who gathered the docs and is the authority on which is the spec.
    if operator_authoritative:
        tier = llm_tier if llm_tier in (1, 2) else 1
        return Decision(
            tier, RULE_OPERATOR_AUTHORITATIVE,
            "operator named this document authoritative at the classification review",
            True,
        )

    # 4. Floor-passed background/authoritative — the LLM classifier decides.
    #    (The classifier owns the self-authorizing-tier judgment: the injection
    #    floor was removed in instruction 023. Its advisory genre-title hint, if
    #    any, is surfaced on the record as a demotion input to the LLM.)
    if llm_tier is None:
        return Decision(
            4, RULE_DEFAULT,
            "no classifier tier assigned; Tier 4 on ambiguity", True,
        )
    if llm_tier not in (1, 2, 3, 4):
        raise ValueError(f"llm_tier must be 1-4 or None, got {llm_tier!r}")
    return Decision(llm_tier, RULE_LLM, f"LLM classifier assigned Tier {llm_tier}", True)


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
    # operator made one — INCLUDING when an absolute floor refused it — so a
    # refused promotion is visible in the review rather than silently dropped.
    if decision.operator_decision:
        rec["operator_decision"] = decision.operator_decision
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


def _newly_overridden(
    cached: dict, operator_decision: Optional[str], rescued: bool,
    in_sidecar: bool,
) -> bool:
    """Whether a live operator-authored override is NOT yet reflected in *cached*.

    True means the prior record predates the operator's instruction and must be
    thrown away rather than reused; False means the record already embodies it
    (or there is no override) and the content-keyed cache stands.

    Each of the three operator files gets the clause its semantics need:

    * ``qpb_authoritative.txt`` — always new when a decision is live. The decision
      forces a specific outcome, so re-deriving reproduces it exactly; there is
      nothing a cached record could hold that the re-derive would lose.
    * ``qpb_promote.txt`` — new only while the cached record shows the floor the
      sidecar *lifts*. The sidecar's sole power is rescuing the implementation
      floor, so against any other cached rule it changes nothing and the cache
      must stand. Keying on ``!= RULE_SIDECAR`` instead was permanently true for
      every non-implementation file — ``_classify`` reaches its sidecar branch
      only inside ``if impl and not contract``, so an ordinary spec can never
      settle at ``RULE_SIDECAR`` — which discarded the cache on every ingest and
      silently reverted the agent's tier refinement to Tier 4. That is severe for
      ``cite/``, whose every file is synthesized into the sidecar set: a
      ``cite/``-only corpus began reporting ``zero_citable`` — the manufactured
      virtio signature this instruction exists to surface — while the pipeline
      quoted every one of those documents (instr 030 self-Council round 4, all
      three panelists).
    * ``qpb_advisory_rescue.txt`` — new **only** while the cached record does not
      already carry ``advisory_rescued``. A rescue merely un-floors; it does not
      force a tier. Once the agent has tiered a rescued document and that record
      is cached, re-deriving it with no classifier in play would drop it to
      Tier 4 and destroy its ``FORMAL_DOC`` — so a rescue the record already
      reflects must keep its cache.
    """
    if operator_decision is not None:
        return True
    if in_sidecar and cached.get("floor_rule") == RULE_IMPL:
        return True
    return bool(rescued and not cached.get("advisory_rescued"))


def _cache_hides_live_classifier(cached: dict, has_classifier: bool) -> bool:
    """Whether reusing *cached* would silently SWALLOW a live classifier.

    ``RULE_DEFAULT`` is the one rule that records no judgment at all — it records
    the ABSENCE of one (*"no classifier tier assigned; Tier 4 on ambiguity"*),
    which is what **every** record of a bare unwired ingest carries. So when a
    classifier IS available this pass, reusing such a record is not
    reproducibility: it is discarding the classifier's vote in favour of a
    placeholder that stands for "nobody has voted yet".

    That was a live footgun, reproduced independently on chi and on a fresh
    virtio baseline (instruction 032 fix 1). The documented dump-and-go flow is
    "run the bare ingest, then refine tiers"; an agent that instead re-runs
    ``classify_documents`` *passing a live classifier* had it silently ignored —
    the first unwired pass froze every doc at ``default-tier4``, the content-keyed
    cache matched each doc by sha on the second pass, and the corpus stayed
    all-Tier-4. The visible outcome is a silent ``zero_citable`` run: the exact
    virtio failure mode Feature G exists to prevent.

    Deliberately narrow — it re-opens ONLY the unclassified default:

    * A genuinely-classified cached record (``RULE_LLM``, ``RULE_CONTRACT``, an
      operator rule, any real floor) is reused unchanged, so reproducibility for
      already-tiered unchanged content is intact (Design §8a).
    * With ``llm_classifier is None`` this cannot fire, so the documented
      edit-the-manifest-then-re-ingest-unwired flow still stands: a hand-tiered
      ``default-tier4`` -> ``llm`` record is honored, and a record left at the
      default keeps its cache.
    * No floor is weakened. Discarding the cache re-derives the document from
      content through the full floor stack, so an advisory / background /
      implementation floor decides again exactly as it did. The re-derive is
      byte-identical to a cold first-ever classify of the same inputs — which is
      the actual guarantee, and it is stronger than "it can only reach the
      classifier branch": a live operator decision or sidecar entry reaches its
      own branch, exactly as it would on a first ingest (instr 032 self-Council,
      Panelist A).
    """
    return has_classifier and cached.get("floor_rule") == RULE_DEFAULT


def classify_documents(
    docs: Sequence[Tuple[str, str]],
    *,
    llm_classifier: Optional[Callable] = None,
    sidecar: Optional[Sequence[str]] = None,
    advisory_rescues: Optional[Sequence[Tuple[str, str]]] = None,
    operator_decisions: Optional[Sequence[Tuple[str, str, str]]] = None,
    prior_records: Optional[Sequence[dict]] = None,
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
    triples, content-keyed exactly like ``advisory_rescues`` and read from the
    same kind of operator-authored file. A document carrying a decision **bypasses
    the prior-record cache**, so a correction made after the first ingest actually
    takes effect on the re-run (that re-run is what turns a promoted doc into a
    byte-citable ``FORMAL_DOC``). Later triples win over earlier ones for the same
    key.

    Reproducibility: when ``prior_records`` is supplied, a document whose
    content sha256 matches a prior record for the same path reuses that prior
    decision instead of re-invoking the classifier — so a re-run with unchanged
    content reproduces the same tiering (§8a). The floor itself is deterministic
    on content, so classification is stable regardless.

    The cache reuses **decisions**, and a ``default-tier4`` record is not one: it
    means no classifier tier was ever assigned. So when a live ``llm_classifier``
    is supplied, a cached bare default is discarded and the document re-derived,
    letting the classifier actually run (instruction 032 fix 1 — otherwise an
    unwired first ingest froze the whole corpus at Tier 4 and every later wired
    re-run was a silent no-op, i.e. a silent ``zero_citable``). Genuinely-classified
    records are still reused unchanged, and with no classifier supplied nothing
    changes at all — see ``_cache_hides_live_classifier``.
    """
    sidecar_set = set(sidecar or ())
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
    prior_by_key: Dict[Tuple[str, str], dict] = {
        (r["source_path"], r["document_sha256"]): r for r in (prior_records or [])
    }
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
        cached = prior_by_key.get((rel_path, sha))
        if cached is not None and (
            _newly_overridden(
                cached, operator_decision, rescued, rel_path in sidecar_set)
            # instruction 032 fix 1 — a live classifier must not be swallowed by a
            # cached record that only ever meant "nobody classified this yet".
            or _cache_hides_live_classifier(cached, llm_classifier is not None)
        ):
            # APPLICATION side of the operator-override contract (instr 030
            # self-Council, Panelists A + C). A NEW operator-authored override
            # must take effect on the very next ingest, so it bypasses the
            # content-keyed cache — otherwise the prior record (the very tiering
            # the operator just corrected) is reused and the override is a
            # permanent silent no-op. This is not hypothetical for any of the
            # three files: every one of them is authored AFTER a first ingest,
            # and the instr-025 rescue's documented workflow literally requires
            # copying the sha and reason out of the manifest a prior ingest
            # wrote — so the cache always exists by the time the operator writes
            # the file. Panelist C reproduced both no-ops.
            #
            # "NEW" is load-bearing: a rescue that the cached record ALREADY
            # reflects must keep its cache, because a rescue only un-floors and
            # does not force a tier — re-deriving a settled, agent-tiered rescued
            # document with no classifier in play would drop it back to Tier 4 and
            # destroy its FORMAL_DOC (Panelist A caught this in the naive fix).
            cached = None
        if cached is not None:
            # Defense-in-depth: never trust a prior record to keep a document
            # citable OR promotable when an UNRESCUABLE floor bars it. The floor
            # is content-only, so re-running it on the (unchanged) content cannot
            # change a legitimate decision — but it DOES defeat a poisoned /
            # hand-edited prior manifest. A poison that keeps tier==4 while
            # flipping `promotable` to true would slip past a tier-only guard and
            # then be laundered by _formal_tier's cite/ branch, so the guard
            # discards the cache entirely (both tier AND promotable) whenever an
            # unrescuable floor fires — advisory/injection/background, never the
            # sidecar-rescuable implementation floor (instruction 011 Panelist A).
            # The operator advisory rescue (instr 025) is applied here too, so a
            # LEGITIMATELY-rescued advisory doc re-decides as un-floored (not
            # RULE_ADVISORY) and its cache is honored — while a NON-rescued advisory
            # doc still trips RULE_ADVISORY and its poisoned cache is discarded. A
            # poisoned prior manifest cannot forge a rescue: the rescue comes only
            # from the operator-authored file, never from the (untrusted) cache.
            guard = classify_document(rel_path, text, advisory_rescue=rescued)  # no LLM, no sidecar
            if guard.rule in _UNRESCUABLE_FLOOR_RULES:
                records.append(_record(rel_path, text, guard))
                continue
            if (cached.get("operator_decision")
                    or cached.get("floor_rule") in _OPERATOR_RULES
                    or (cached.get("advisory_rescued") and not rescued)):
                # WITHDRAWAL / FORGERY side of the same contract.
                # `advisory_rescued` is an operator-voice surface that is not a
                # floor rule and so was not covered by _OPERATOR_RULES: a prior
                # manifest forged with `advisory_rescued: true` on a document
                # carrying no advisory signal at all sailed through, became
                # byte-citable, and made the review say "you confirmed this is
                # your real specification even though it mentions security
                # advisories" about a document the operator never saw. The
                # writer of that field is the derivation agent refining the
                # manifest — precisely the party that must never manufacture the
                # operator's consent (instr 030 self-Council, Panelist A). Keyed
                # to `not rescued` so a LIVE rescue still keeps its cache.
                #
                # An operator classification-review decision in the PRIOR manifest
                # with no live operator-authored backing (instr 030 self-Council,
                # Panelist A). Two cases, same answer: the operator WITHDREW the
                # line from qpb_authoritative.txt — a decision they can no longer
                # revoke is not a decision — or the prior manifest was
                # hand-edited/poisoned to forge consent the operator never gave.
                # Either way the cache is discarded and the document re-decided
                # from scratch below; the operator's consent has to still be on
                # file, exactly as the instr-025 rescue requires. Without this the
                # show would also FABRICATE the operator's own words back at them
                # ("you told me this one is a source I should use").
                cached = None
            else:
                rec = dict(cached)
                rec["reused_from_prior"] = True
                records.append(rec)
                continue
        llm_tier = None
        if llm_classifier is not None:
            try:
                if wants_hints:
                    hints = {
                        "advisory_hints": advisory_genre_hints(text, rel_path),
                        "code_heavy": code_heavy_hint(text, rel_path),
                    }
                    llm_tier = llm_classifier(rel_path, text, hints)
                else:
                    llm_tier = llm_classifier(rel_path, text)
            except Exception as exc:   # a FAILED classifier is loud, not silent
                classifier_status = CLASSIFIER_ERROR
                if classifier_error is None:
                    classifier_error = f"{type(exc).__name__}: {exc}"
                llm_tier = None
        decision = classify_document(
            rel_path, text, llm_tier=llm_tier,
            sidecar_promote=rel_path in sidecar_set, advisory_rescue=rescued,
            operator_decision=operator_decision,
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
    manifest = {
        "schema_version": schema_version,
        "generated_at": generated_at,
        "classifier_status": classifier_status,
        "citable_count": len(citable),
        "zero_citable": len(citable) == 0,
        "records": records,
    }
    if classifier_error is not None:
        manifest["classifier_error"] = classifier_error
    return manifest


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
    RULE_CONTRACT: (
        "its file extension, or an interface-definition signature inside it, marks "
        "it as a contract definition — the kind of file that states directly what "
        "this software is supposed to do."
    ),
    RULE_LLM: "I read it as a statement of what this software is supposed to do.",
}
_BACKGROUND_REASONS = {
    # instruction 032 fix 2 — say what was DETECTED, never what the document IS.
    # The advisory floor fires on a CVE/GHSA identifier or an advisory-site URL
    # found ANYWHERE in the content, so it also (correctly) demotes a
    # bibliography / sources list / index that merely *cites* those sources. The
    # old wording — "it's a security advisory — it describes known problems" —
    # was a flat falsehood about `sources.md` / `INDEX.md` /
    # `COLLECTION_SUMMARY.txt`, which are meta-documents about the doc set. This
    # wording is true of a real advisory AND of a document that only points at
    # one; the demotion it explains is the same in both cases.
    RULE_ADVISORY: (
        "it carries security-advisory material — a CVE-style identifier, or a link "
        "to a vulnerability database — so I'm reading it as background rather than "
        "a statement of what your software is supposed to do."
    ),
    # instruction 032 self-Council, Panelist B (defensive sweep): the floor needs
    # a code EXTENSION plus code-shaped content, and it fires on
    # declaration-only files too (a `virtio_ring.h` of pure declarations, an
    # interface-only `.ts`) — of which "it shows what the software already does"
    # is not true. The extension is the signal; say that.
    RULE_IMPL: (
        "it's a code file — code is how the software works, not a statement of what "
        "it's supposed to do."
    ),
    # instruction 032 self-Council, Panelist B (defensive sweep, same class as
    # fix 2): this fires on the FILENAME alone, and the issue-tracker arm of
    # `_BACKGROUND_NAME_RE` is a PREFIX match — so `issue_tracker_api_spec.md`,
    # a genuine specification by content, was told "it's a README or a coverage /
    # issue-tracker listing". Say what was detected (the name) instead of
    # asserting the genre. NOTE the tier is deliberately NOT touched here: this
    # floor is absolute and unrescuable-by-the-operator, which is a floor
    # question and out of scope for a reason-accuracy fix (instruction 032
    # "tiers are unchanged"). It is carried forward in the output instead.
    RULE_BACKGROUND: (
        "its name marks it as a README, a coverage report or an issue-tracker "
        "listing — documents that describe a project rather than specify it."
    ),
    RULE_OPERATOR_BACKGROUND: "you told me to treat this one as background only.",
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
_CITE_FOLDER_REASON = (
    "you put it in the folder for documents you want quoted as sources."
)

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
# document that is not plausibly a specification. Size is not that signal: on the
# real virtio corpus the largest promotable background document is
# ``linux-coding-style.rst`` (a 45 KB style guide) while the actual spec,
# ``virtio-spec-behavioral-contracts.md``, is 7.8 KB — so the feature built to
# help the operator recover a mis-classified spec was suggesting they promote a
# STYLE GUIDE as their specification.
#
# The signal is the document's NAME. The show is rendered from the classification
# manifest, whose records carry the path, the tier, the floor decision and the
# byte count — a title/self-identification signal would have to be derived at
# classify time and persisted as a new record field, which changes the manifest
# schema the content-keyed reproducibility contract is written against. That is a
# schema decision, not a rendering one, so the renderer uses what is already
# there and falls back to a NEUTRAL PLACEHOLDER whenever the name says nothing —
# an honest blank instead of a confident wrong answer.
_SPEC_NAME_TOKENS = frozenset({
    "spec", "specs", "specification", "specifications",
    "contract", "contracts",
    "reference", "references",
    "protocol", "protocols",
    "api", "apis",
    "rfc", "rfcs",
    "standard", "standards",
})
# ...and the genres that carry one of those words while being the opposite of a
# specification. A veto, evaluated first, because the failure it prevents is the
# reported defect itself: ``linux-coding-standards.rst`` (one rename away from
# the real virtio file) matches ``standards``, and ``api-migration-guide.md`` /
# ``quick-reference-card.md`` match ``api`` / ``reference`` — each would be named
# over a genuine spec, since size still breaks ties among spec-like candidates
# (instr 031 self-Council, Panelist A). A vetoed name falls through to the
# placeholder, which is the honest direction for exactly this class.
# Two classes, both naming what a document IS rather than what it is about:
#
# 1. GENRE words — the document's kind is not "specification": a guide, a
#    tutorial, an FAQ, a changelog, a set of examples, a table of contents.
# 2. PRACTICE-DOMAIN words — the subject is how the TEAM works (their coding,
#    documentation, naming, review or commit practice), so "standards" /
#    "reference" / "contract" beside one of these describes house style, not the
#    software's contract. This is the class `linux-coding-style.rst` belongs to,
#    and it is why closing it one filename at a time does not work:
#    `documentation-standards.md`, `naming-standards.md` and
#    `engineering-standards.md` are the same document wearing different words
#    (instr 031 self-Council round 3, Panelist A — who caught that round 2 had
#    closed only the one filename, not the class).
_NON_SPEC_NAME_TOKENS = frozenset({
    # genre
    "style", "styles", "styleguide",
    "guide", "guides", "guideline", "guidelines",
    "tutorial", "tutorials", "howto", "walkthrough", "walkthroughs",
    "faq", "faqs", "cheatsheet", "quickstart", "checklist", "checklists",
    "changelog", "notes", "note",
    "migration", "migrations", "migrating", "upgrade", "upgrading", "roadmap",
    "example", "examples", "sample", "samples", "card", "cards",
    "practices", "glossary", "readme", "index", "toc", "contents",
    # practice domain — "how we work", not "what the software must do"
    "coding", "documentation", "naming", "formatting", "engineering",
    "commit", "commits", "branching", "review", "reviews", "contributing",
    "onboarding", "process", "workflow", "workflows",
})
# Deliberately NOT vetoed: version-adjacent words (`release`, `changes`,
# `history`). A veto is a demotion, and demoting `virtio-spec-release-1.2.md`
# hands the example to whatever else is spec-like — in the worst case a 7-byte
# `api-contract-stub.md`, which re-opens the instr-030 substantive-over-stub
# finding one door over (instr 031 self-Council round 2, Panelist A). A version
# word only dates a document; it does not say what kind of document it is.
# (`index`/`toc` went back onto the veto in round 3: they are the instr-030
# toctree-stub genre, not version words — the rule above is what decides, and it
# puts them on the genre side.)
# Tokens are ALPHABETIC runs, so digits split too (``rfc793`` -> ``rfc``), and
# matching is whole-token — a substring match would read "spec" out of
# "inspector" and "api" out of "capital".
_NAME_TOKEN_SPLIT_RE = re.compile(r"[^a-z]+")
# The example phrasing with no file named. Deliberately not a real path: the
# operator substitutes their own, which is exactly the instruction the sentence
# is illustrating.
_NEUTRAL_EXAMPLE = "<the-file>"


def _spec_like_name(source_path: Optional[str]) -> bool:
    """Whether this document's *filename* plausibly identifies a specification.

    Matched on the basename with its extension stripped, whole-token, so a
    directory called ``reference_docs/`` (which every gathered document sits
    under) is not itself the signal. A genre veto beats a spec word: a
    ``coding-standards`` guide is a guide.
    """
    # Split on both separators: the pipeline normalizes to ``/``, but a
    # backslash path would otherwise leave the whole thing as one "basename" and
    # make the ``reference_docs`` directory itself the signal — inverting the
    # rule above (instr 031 self-Council, Panelist A).
    base = re.split(r"[\\/]", str(source_path or ""))[-1]
    stem = re.sub(r"\.[^.]+$", "", base)
    if not stem:
        stem = base           # a dotfile (``.spec``) is all name, no extension
    tokens = [tok for tok in _NAME_TOKEN_SPLIT_RE.split(stem.lower()) if tok]
    if any(tok in _NON_SPEC_NAME_TOKENS for tok in tokens):
        return False
    return any(tok in _SPEC_NAME_TOKENS for tok in tokens)


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
        if entry.get("tier") not in (1, 2) and _is_cite_placed(entry.get("source_path")):
            return _CITE_FOLDER_REASON
        return _AUTHORITATIVE_REASONS.get(
            rule, "I read it as a statement of what this software is supposed to do.")
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
    background = [e for e in entries if not e["_authoritative"]]

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
                     if e.get("floor_rule") not in (RULE_ADVISORY, RULE_BACKGROUND,
                                                    RULE_OPERATOR_BACKGROUND,
                                                    RULE_OPERATOR_AUTHORITATIVE,
                                                    RULE_CONTRACT)]
    # Prefer a documentation-shaped candidate over an implementation-floored one:
    # source files are eligible (the operator CAN promote one) but are often the
    # largest thing in the corpus, so size alone would routinely illustrate
    # "treat X as my specification" with a .c file (instr 030 self-Council,
    # Panelist B round 3).
    promotable_bg.sort(key=lambda e: (e.get("floor_rule") == RULE_IMPL,
                                      -(e.get("byte_count") or 0),
                                      str(e.get("source_path") or "")))
    # Documentation and source code are separate strata, not one list ordered by
    # a tiebreak. Sweeping for the name signal across BOTH inverted the
    # instr-030 doc-over-source rule: a spec-NAMED `.c` file beat an ordinary
    # document, so the show told the operator to treat source code as their
    # specification one line after telling them that file "shows what the
    # software already does, not what it's supposed to do" (instr 031
    # self-Council, Panelist A). A source file is named only when there is no
    # promotable document at all — the operator CAN promote a code-shaped
    # contract, and that is the case instr 030 opened the eligibility for.
    docs = [e for e in promotable_bg if e.get("floor_rule") != RULE_IMPL]
    pool = docs or promotable_bg
    spec_like = [e for e in pool if _spec_like_name(e.get("source_path"))]
    if spec_like:
        example = _safe_path(spec_like[0]["source_path"])
    elif pool:
        # There IS something the operator could promote, but nothing here looks
        # like a specification — so illustrate the phrasing without asserting
        # which of their documents is the spec. Naming the biggest one is the
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
