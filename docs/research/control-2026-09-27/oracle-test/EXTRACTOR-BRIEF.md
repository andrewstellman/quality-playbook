# Extractor brief

You are extracting a deduplicated list of defect findings from a set of code-review reports. Another set of agents will later classify these findings without seeing the reports, so the list you produce must be neutral.

## Inputs

- The review reports: `/Users/andrewstellman/Documents/QPB/docs/research/control-2026-09-27/results/<model>-<repo>-runNN.md` for the repo named in your task (both models, all run numbers present). Use the Read tool. Ignore any file without `-runNN` in its name.
- The read-only checkout of the code at `/tmp/control/<repo>` (shell tool). Use it to confirm file:line references and to resolve two reports that describe the same code differently.

Do not read anything else under `docs/research/` or `evidence/`.

## Output 1: the blind list

Write `/Users/andrewstellman/Documents/QPB/docs/research/control-2026-09-27/oracle-test/findings-<repo>-blind.md`:

```
# Findings: <repo>

Checkout: /tmp/control/<repo> at <pinned commit>. Paths are relative to it.

| ID | Location | Observed behaviour |
|---|---|---|
| <repo>-01 | path/file.ext:LINE (function name) | one or two sentences, see rules |
```

Rules for **Observed behaviour**. This column is the whole point; get it right.

- State only what the code does on a specific input or in a specific situation. Example: "`res.cookie('a', 'b', {maxAge: 500})` sends a cookie with `Max-Age=0`."
- Do NOT say why it's wrong. No "unlike the sibling function", no "contrary to RFC ...", no "the docstring says", no "should", no severity words (high, medium, low, critical, silently, corrupt, leak, bypass, DoS, security). No suggested fixes. No mention of tests, reproductions, or how many reports found it.
- If the report only describes the code path rather than an observable behaviour, phrase it as a behaviour anyway: "When X, the function returns Y / raises Z / writes W."
- Shuffle the rows so the order carries no information (not by severity, not by how many reports mention it, not by file order). Use `shuf` or a random key.

Deduplication:

- Two reports that describe the same defect in different words are one finding.
- Two distinct behaviours in the same function are two findings if a fix for one would not fix the other (for example, `Range: bytes=5` → 500 and `Range: bytes=-0` → 206 are two findings).
- If a report bundles several behaviours under one heading, split them.
- If a finding is plainly a false positive caused by the sandbox (for example, Python 3.14 syntax reported as a syntax error under Python 3.10), still include it; do not mark it. Classifiers will judge.

## Output 2: the hit matrix

Write `/Users/andrewstellman/Documents/QPB/docs/research/control-2026-09-27/oracle-test/findings-<repo>-hits.md`:

```
# Hits: <repo>

| ID | Reports that include it as a finding | Reports that mention it but do not report it |
|---|---|---|
| <repo>-01 | opus-run02, opus-run04, sonnet-run07 | opus-run10 |
```

"Include it as a finding" means the report lists it as a defect. "Mention but not report" means the report discusses the behaviour in a "considered and rejected" or "not reported" section, or names it as a non-defect. Be strict: a report that merely lists the file as read does not count in either column.

Also add a short section at the end: any judgement calls you made in deduplication, with the IDs involved.

## Ground rules

- Read every report in full. Do not grep for headings and stop.
- Never fabricate a finding or a hit. If unsure whether two reports describe the same defect, open the code and check.
- Do not write anything else anywhere.
