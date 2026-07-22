"""v1.6.0 Feature G (Design §8a) — dump-and-go documentation classification.

The operator dumps *any* documentation into one folder; ingest classifies each
file **by content** into citable (Tier 1/2) vs background (Tier 4) — no required
``cite/`` pre-sorting. Classification is an AI judgment (the derivation agent is
the classifier), but it runs **over a deterministic mechanical floor** that the
LLM cannot override upward. The floor is the security-critical part:

* **Advisory floor (mechanical, first, content-keyed).** A CVE/GHSA identifier,
  an advisory URL/header, or a security-genre marker (hardening-guide /
  best-practices / benchmark title, high MUST/SHALL-density "how to harden"
  prose) forces **Tier 4**. Nothing promotes a floored advisory — not the LLM,
  not an extension carve-out, not the operator sidecar. Runs *before* the
  contract carve-out, so a CVE advisory renamed ``api.proto`` is still floored
  by its content.
* **Implementation-source floor.** A document that is predominantly
  *implementation* code (function bodies) is floored to Tier 4 — code is what
  the system *does*, not what it is *supposed to do*.
* **Machine-readable-contract carve-out.** An OpenAPI/Swagger, ``.proto``, JSON
  Schema, IDL, ``.d.ts``, or WSDL file *is* an authoritative contract and is
  citable without override; the implementation floor targets logic, not
  interface definitions.
* **Operator sidecar.** For the fuzzy case where the implementation floor caught
  a code-shaped contract, the operator sidecar may explicitly promote *that
  file* past the **implementation floor only** — never past the advisory floor.
  The sidecar is operator-authored configuration; the classifier can never add
  to it.
* **Injection resistance.** The classifier treats content as data: a document
  arguing for its own authority (self-classifying tier language, imperatives to
  the classifier) is a signal *toward* Tier 4, not away.

On genuine ambiguity the classifier defaults to Tier 4 (a missed grounding is
Tier 3 instead of Tier 1 — recoverable; a false authoritative source poisons the
derivation). The classification manifest is content-keyed for reproducibility:
a re-run with unchanged content reuses the prior decision.

This module is deliberately dependency-free (stdlib only) so it is trivially
bundle-portable and unit-testable without the rest of the harness.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional, Sequence, Tuple

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

# The ABSOLUTE floor rules — a decision under any of these permanently bars
# citability and can never be reversed by the LLM, a rename, the sidecar, or a
# reused prior-manifest record. (default-tier4 is NOT absolute: it just means
# "no classifier tier was assigned", which a later run's LLM may raise.)
_ABSOLUTE_FLOOR_RULES = frozenset(
    {RULE_ADVISORY, RULE_IMPL, RULE_INJECTION, RULE_BACKGROUND}
)

# §8a item 7: README and the coverage / issue-tracker ledgers are background
# and stay Tier 4 — the classifier cannot promote them. (An advisory-signature
# README is still caught by the advisory floor first.)
_BACKGROUND_NAME_RE = re.compile(
    r"^(?:readme|[^/]*coverage[^/]*|issue[_-]?tracker[^/]*)\.(?:md|txt|rst)$",
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
# "Best Practices" subsection, a spec a "Security Considerations" one). They floor
# only when they describe the WHOLE DOCUMENT'S GENRE — i.e. they appear in the
# TITLE ZONE (filename + first H1 + first non-blank line), not in body prose or a
# subsection heading. Unambiguous signals (CVE/GHSA ids, advisory URLs) match
# anywhere; these do not.
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
# RFC-2119 normative keywords — high density is a *contract* signal on its own,
# so it floors only in combination with hardening/config subject matter.
_NORMATIVE_RE = re.compile(
    r"\b(?:MUST(?:\s+NOT)?|SHALL(?:\s+NOT)?|SHOULD(?:\s+NOT)?|REQUIRED)\b"
)
_HARDENING_SUBJECT_RE = re.compile(
    r"\b(?:harden|hardening|configure|configuration|disable|enable|"
    r"restrict|permission|least\s+privilege|secure\s+default)\b",
    re.IGNORECASE,
)


def advisory_floor(text: str, filename: str = "") -> Optional[str]:
    """Return a reason string if *text* is advisory/security-genre, else None.

    Unambiguous signals (CVE/GHSA ids, advisory URLs) are matched anywhere in
    content — keyed on content so a renamed advisory cannot escape. Ambiguous
    English markers (advisory/vulnerability headers, hardening/best-practices
    genre) are matched only in the title zone, so a passing mention or a
    "Best Practices" subsection in a normal guide does not floor it.
    """
    m = _ADVISORY_ID_RE.search(text)
    if m:
        return f"advisory identifier {m.group(0)!r}"
    m = _ADVISORY_URL_RE.search(text)
    if m:
        return f"advisory URL {m.group(0)!r}"
    title = _title_zone(text, filename)
    m = _ADVISORY_HEADER_RE.search(title)
    if m:
        return f"advisory-genre title {m.group(0)!r}"
    m = _SECURITY_GENRE_RE.search(title)
    if m:
        return f"security-genre title {m.group(0)!r}"
    # High normative density + hardening subject = a how-to-harden guide.
    words = max(1, len(text.split()))
    normative = len(_NORMATIVE_RE.findall(text))
    density = normative / words
    if normative >= 5 and density >= 0.004 and _HARDENING_SUBJECT_RE.search(text):
        return (
            f"high normative density ({normative} MUST/SHALL over ~{words} "
            "words) with hardening/configuration subject"
        )
    return None


# ---------------------------------------------------------------------------
# 2. Machine-readable contract carve-out — citable without override.
# ---------------------------------------------------------------------------
_CONTRACT_EXTS = frozenset(
    {".proto", ".wsdl", ".graphql", ".graphqls", ".raml", ".thrift", ".idl"}
)
_CONTRACT_CONTENT_RE = re.compile(
    r'syntax\s*=\s*"proto[23]?"'          # protobuf
    r'|"openapi"\s*:|openapi\s*:\s*["\']?3'  # OpenAPI 3
    r'|"swagger"\s*:|swagger\s*:\s*["\']?2'  # Swagger 2
    r'|"asyncapi"\s*:|asyncapi\s*:'          # AsyncAPI
    r'|"\$schema"\s*:'                        # JSON Schema
    r"|<wsdl:|<definitions[^>]*wsdl"          # WSDL
    r"|^\s*type\s+Query\s*\{|^\s*schema\s*\{",  # GraphQL SDL
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


def implementation_source(text: str, filename: str) -> Optional[str]:
    """Return a reason if *text* is predominantly implementation code.

    A code extension is a strong signal; content is confirmed by a high ratio
    of code-shaped lines so a ``.md`` walkthrough that merely *quotes* code is
    not floored while an actual ``.py`` module is.
    """
    lower = filename.lower()
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return None
    code_lines = sum(1 for ln in lines if _CODE_LINE_RE.search(ln))
    ratio = code_lines / len(lines)
    ext = "." + lower.rsplit(".", 1)[-1] if "." in lower else ""
    if ext in _IMPL_EXTS and ratio >= 0.25:
        return f"code extension {ext} with {ratio:.0%} code-shaped lines"
    if ratio >= 0.5:
        return f"{ratio:.0%} code-shaped lines (predominantly implementation)"
    return None


# ---------------------------------------------------------------------------
# 4. Injection resistance — content arguing for its own authority.
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
    # a floored advisory/impl/injection doc is promotable=False.
    promotable: bool


def classify_document(
    rel_path: str,
    text: str,
    llm_tier: Optional[int] = None,
    sidecar_promote: bool = False,
) -> Decision:
    """Classify one document to a Decision, enforcing the floor in priority order.

    * ``llm_tier`` — the tier the LLM classifier assigned to the *remaining*
      (floor-passed) documents; the floor may override it only downward.
    * ``sidecar_promote`` — True when the operator sidecar names this file;
      rescues it from the **implementation** floor only, never the advisory floor.
    """
    # 1. Advisory floor FIRST — content-keyed, before any extension carve-out
    #    or sidecar. An advisory can never reach citable by any path.
    adv = advisory_floor(text, rel_path)
    if adv:
        return Decision(4, RULE_ADVISORY, f"advisory/security-genre: {adv}", False)

    # README / coverage / issue-tracker ledgers are background — pinned Tier 4
    # (§8a item 7); the classifier cannot promote them.
    if _is_background_ledger(rel_path):
        return Decision(4, RULE_BACKGROUND, "README/coverage/ledger stays Tier 4 background", False)

    contract = machine_readable_contract(text, rel_path)
    impl = implementation_source(text, rel_path)

    # 2. Implementation floor (a machine-readable contract is exempt).
    if impl and not contract:
        if sidecar_promote:
            tier = llm_tier if llm_tier in (1, 2) else 1
            return Decision(
                tier, RULE_SIDECAR,
                f"operator-sidecar promotion past implementation floor ({impl})",
                True,
            )
        return Decision(4, RULE_IMPL, f"implementation-source floor: {impl}", False)

    # 3. Injection resistance — a floor-passed doc arguing for its own tier
    #    is a signal toward Tier 4, not away.
    inj = injection_signature(text)
    if inj:
        return Decision(
            4, RULE_INJECTION,
            f"not promoted on self-assertion: {inj}", False,
        )

    # 4. Machine-readable contract — citable without override.
    if contract:
        tier = llm_tier if llm_tier in (1, 2) else 1
        return Decision(tier, RULE_CONTRACT, f"machine-readable contract: {contract}", True)

    # 5. Floor-passed background/authoritative — the LLM classifier decides.
    if llm_tier is None:
        return Decision(
            4, RULE_DEFAULT,
            "no classifier tier assigned; Tier 4 on ambiguity", True,
        )
    if llm_tier not in (1, 2, 3, 4):
        raise ValueError(f"llm_tier must be 1-4 or None, got {llm_tier!r}")
    return Decision(llm_tier, RULE_LLM, f"LLM classifier assigned Tier {llm_tier}", True)


def _record(rel_path: str, text: str, decision: Decision) -> dict:
    return {
        "source_path": rel_path,
        "document_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "tier": decision.tier,
        "floor_rule": decision.rule,
        "reason": decision.reason,
        "byte_count": len(text.encode("utf-8")),
        "promotable": decision.promotable,
    }


def classify_documents(
    docs: Sequence[Tuple[str, str]],
    *,
    llm_classifier: Optional[Callable[[str, str], Optional[int]]] = None,
    sidecar: Optional[Sequence[str]] = None,
    prior_records: Optional[Sequence[dict]] = None,
    schema_version: str = "1.6.0",
    generated_at: Optional[str] = None,
) -> dict:
    """Classify a corpus into a reviewable, content-keyed classification manifest.

    ``docs`` is a sequence of ``(rel_path, text)``. Returns a manifest dict
    ``{schema_version, generated_at, records[]}`` sorted by ``source_path``.

    Reproducibility: when ``prior_records`` is supplied, a document whose
    content sha256 matches a prior record for the same path reuses that prior
    decision instead of re-invoking the classifier — so a re-run with unchanged
    content reproduces the same tiering (§8a). The floor itself is deterministic
    on content, so classification is stable regardless.
    """
    sidecar_set = set(sidecar or ())
    prior_by_key: Dict[Tuple[str, str], dict] = {
        (r["source_path"], r["document_sha256"]): r for r in (prior_records or [])
    }
    if generated_at is None:
        generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    records: List[dict] = []
    for rel_path, text in docs:
        sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
        cached = prior_by_key.get((rel_path, sha))
        if cached is not None:
            # Defense-in-depth: never trust a prior record to keep a document
            # citable when the deterministic floor bars it. The floor is
            # content-only, so re-running it on the (unchanged) content cannot
            # change a legitimate decision — but it DOES catch a poisoned /
            # hand-edited prior manifest that tried to launder a floored doc to
            # Tier 1/2. If the absolute floor fires, the fresh floored decision
            # wins over the cache.
            guard = classify_document(rel_path, text)  # no LLM, no sidecar
            if guard.rule in _ABSOLUTE_FLOOR_RULES and cached.get("tier") != guard.tier:
                records.append(_record(rel_path, text, guard))
                continue
            rec = dict(cached)
            rec["reused_from_prior"] = True
            records.append(rec)
            continue
        llm_tier = llm_classifier(rel_path, text) if llm_classifier else None
        decision = classify_document(
            rel_path, text, llm_tier=llm_tier, sidecar_promote=rel_path in sidecar_set
        )
        records.append(_record(rel_path, text, decision))

    records.sort(key=lambda r: r["source_path"])
    return {
        "schema_version": schema_version,
        "generated_at": generated_at,
        "records": records,
    }


def citable_records(manifest: dict) -> List[dict]:
    """The Tier-1/2 records — the citable subset the formal-doc manifest is built from."""
    return [r for r in manifest.get("records", []) if r.get("tier") in (1, 2)]
