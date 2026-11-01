#!/usr/bin/env bash
# Submit the two private vulnerability reports via the GitHub API, as the authenticated gh user.
# Usage: ./submit.sh            (dry run: prints each payload, submits nothing)
#        ./submit.sh --send     (submits, asks y/N before each one, saves responses next to this script)
#
# Endpoint: POST /repos/{owner}/{repo}/security-advisories/reports
# The API does not take attachments, so the patch and the spec are embedded in the description.
set -euo pipefail
cd "$(dirname "$0")"
SEND=${1:-}
command -v gh >/dev/null || { echo "gh is not installed"; exit 1; }
command -v python3 >/dev/null || { echo "python3 is not installed"; exit 1; }
gh auth status >/dev/null 2>&1 || { echo "run: gh auth login"; exit 1; }
echo "Submitting as: $(gh api user -q .login)"

build() { # build <report.md> <attachment> <attachment-lang> <ecosystem> <package> <range> <severity> <cwe,cwe>
python3 - "$@" <<'PY'
import json, re, sys
md, att, lang, eco, pkg, rng, sev, cwes = sys.argv[1:9]
text = open(md, encoding="utf-8").read()
title = re.search(r"^Title: (.*)$", text, re.M).group(1)
# the form fields at the top of the .md go into the structured API fields; the description starts after the "Description" heading
body = text.split("\nDescription\n", 1)[1].strip()
if att:
    body += "\n\n```" + lang + "\n" + open(att, encoding="utf-8").read().rstrip("\n") + "\n```\n"
payload = {
    "summary": title[:1024],
    "description": body,
    "severity": sev,
    "cwe_ids": cwes.split(","),
    "vulnerabilities": [{"package": {"ecosystem": eco, "name": pkg}, "vulnerable_version_range": rng}],
    "start_private_fork": False,
}
print(json.dumps(payload))
PY
}

submit() { # submit <owner/repo> <payload-json> <out-name>
  local repo=$1 payload=$2 out=$3
  echo; echo "=== $repo"
  echo "$payload" | python3 -c 'import json,sys; d=json.load(sys.stdin); print("summary:", d["summary"]); print("severity:", d["severity"], "cwe:", d["cwe_ids"]); print("package:", d["vulnerabilities"]); print("description length:", len(d["description"]), "chars"); print(); print(d["description"][:1200]); print("...")'
  if [ "$SEND" != "--send" ]; then echo "(dry run, not sent)"; return; fi
  read -r -p "Send this report to $repo? [y/N] " yn
  [ "$yn" = "y" ] || { echo "skipped"; return; }
  echo "$payload" | gh api -X POST "repos/$repo/security-advisories/reports" --input - > "$out"
  echo "sent. advisory: $(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d.get("html_url") or d.get("url"))' "$out")"
}

P1=$(build adonis-BUG-011.md 0001-fix-request-do-not-consult-X-Forwarded-Host-in-autho.patch diff npm @adonisjs/http-server ">= 9.0.0, <= 9.3.1" medium CWE-601,CWE-348)
submit adonisjs/http-server "$P1" response-adonis.json

P2=$(build addressable-BUG-044.md display_uri_bidi_spec.rb ruby rubygems addressable "<= 2.9.0" low CWE-451,CWE-176)
submit sporkmonger/addressable "$P2" response-addressable.json
