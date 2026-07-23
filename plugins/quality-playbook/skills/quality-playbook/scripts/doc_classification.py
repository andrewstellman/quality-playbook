"""v1.6.0 Feature G (Design §8a) — dump-and-go documentation classification.

The operator dumps *any* documentation into one folder; ingest classifies each
file **by content** into citable (Tier 1/2) vs background (Tier 4) — no required
``cite/`` pre-sorting. Classification is an AI judgment (the derivation agent is
the classifier), but it runs **over a deterministic mechanical floor** that the
LLM cannot override upward. The floor is the security-critical part, and it
enforces **only hard, unambiguous, structural facts** — fuzzy genre/intent
judgments belong to the LLM (instruction 023 / Fable simplification review). The
cardinal rule the review sharpened: **nothing becomes citable on content-sniffing
alone** — promotion is the integrity-affecting direction, so a doc reaches
citable only via an extension-class hard signal or (disclosed) LLM classification.

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


# ---------------------------------------------------------------------------
# Self-authorizing-tier detection — NO LONGER a classifier floor (instruction
# 023 removed the injection floor: the LLM owns the self-authorizing-tier
# judgment). This detector is RETAINED because it is composed by
# ``persona_grounding.grounding_injection_signature`` (Guard 1) — a DIFFERENT,
# load-bearing control on the auto-apply path that the instruction explicitly
# keeps and does not touch. It is a pure detection helper here, invoked by no
# floor in this module; deleting it would break that Guard-1 reuse and redden the
# suite. (The eventual removal of this reuse belongs to the later Feature-H
# directive-narrowing instruction, not here.)
# ---------------------------------------------------------------------------
_INJECTION_RE = re.compile(
    r"classify\s+(?:me|this|the\s+following)\s+(?:as\s+)?tier"
    r"|cite\s+(?:me|this)\s+as\s+(?:an\s+)?authoritative"
    r"|treat\s+(?:me|this)\s+as\s+(?:an\s+)?(?:authoritative|tier)"
    r"|(?:mark|assign|set)\s+(?:me|this|it)?\s*(?:as\s+)?tier\s*[12]"
    r"|this\s+(?:document|doc|file)\s+is\s+(?:an\s+)?authoritative"
    r"|this\s+is\s+(?:an\s+)?authoritative\s+spec"
    r"|you\s+must\s+(?:cite|classify|treat)"
    r"|ignore\s+(?:the\s+)?(?:previous|rubric|above|instructions)"
    r"|as\s+an\s+ai\s+(?:classifier|model)",
    re.IGNORECASE,
)


def injection_signature(text: str) -> Optional[str]:
    """Return a reason if *text* argues for its own tier / addresses the classifier."""
    m = _INJECTION_RE.search(text)
    if m:
        return f"self-authorizing/injection content {m.group(0).strip()!r}"
    return None


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


def classify_document(
    rel_path: str,
    text: str,
    llm_tier: Optional[int] = None,
    sidecar_promote: bool = False,
    advisory_rescue: bool = False,
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

    Advisory genre-title hints and the code-heavy hint are attached to the
    returned Decision (they inform the LLM/manifest; they never floor or promote).
    """
    decision = _classify(
        rel_path, text, llm_tier=llm_tier, sidecar_promote=sidecar_promote,
        advisory_rescue=advisory_rescue,
    )
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

    contract = machine_readable_contract(text, rel_path)
    impl = implementation_source(text, rel_path)

    # 2. Implementation floor — the code-EXTENSION floor only (a machine-readable
    #    contract is exempt). The old non-extension content sniff is now a hint.
    if impl and not contract:
        if sidecar_promote:
            tier = llm_tier if llm_tier in (1, 2) else 1
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


def classify_documents(
    docs: Sequence[Tuple[str, str]],
    *,
    llm_classifier: Optional[Callable] = None,
    sidecar: Optional[Sequence[str]] = None,
    advisory_rescues: Optional[Sequence[Tuple[str, str]]] = None,
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

    Reproducibility: when ``prior_records`` is supplied, a document whose
    content sha256 matches a prior record for the same path reuses that prior
    decision instead of re-invoking the classifier — so a re-run with unchanged
    content reproduces the same tiering (§8a). The floor itself is deterministic
    on content, so classification is stable regardless.
    """
    sidecar_set = set(sidecar or ())
    # Operator advisory-floor rescues (instr 025), content-keyed by (path, sha256).
    # An advisory doc is lifted past the advisory floor ONLY when its (path, its
    # own content hash) is in this operator-authored set — never by content.
    rescue_set = set(advisory_rescues or ())
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
        cached = prior_by_key.get((rel_path, sha))
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
        out.append(entry)
    return out
