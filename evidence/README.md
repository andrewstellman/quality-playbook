# Evidence: how these kernel patches are found, confirmed, reviewed, and sent

This folder is the public record behind every Linux kernel patch submitted from the
Quality Playbook project. One subfolder per bug. Each holds the raw reproduction
captures, the scripts that produced them, the patch as tested and as sent, the review
that preceded sending, and the upstream status. Nothing in a capture is edited; when a
capture is not clean, the README of that bug says so and says why.

This file documents the method. It exists so that a maintainer, or anyone else, can
see exactly what was done by a person, what was done by an AI model, which model, and
what checks stood between a model's claim and a patch on a mailing list.

## Bugs

| folder | bug | status |
|---|---|---|
| [virtio-pci-intx](./virtio-pci-intx/) | `vp_interrupt()` returns `IRQ_NONE` for a config-change-only interrupt | merged, `93fa09455fb1`, 7.3-rc3 |
| [nvmet-anagrpid](./nvmet-anagrpid/) | ANA group ID 128 clamped to 0 by `array_index_nospec()` | sent to linux-nvme 2026-09-10, awaiting review |
| [nvmet-crto](./nvmet-crto/) | Property Get of CRTO computed from CSTS instead of CAP | sent to linux-nvme 2026-09-10, awaiting review |

## Who does what

Four kinds of participant, named by role so the attribution is unambiguous:

| role | who | does | never does |
|---|---|---|---|
| finder | Quality Playbook running on Claude (Opus 5 for the nvme-target run; earlier runs used the model recorded in each run's `REPORT.md`) | reads a subsystem against its spec and reports candidate bugs with code and spec citations | reproduce, patch, or send anything |
| planner | Claude Fable 5.1 in the Cowork chat with the operator | picks which candidate to pursue, writes the reproducer scripts and the runbook, writes the review charters, synthesizes the reviews | run `git send-email`, `git push`, or post anywhere |
| autopilot | Claude Code, launched with `--model opus` (Claude Opus 5 at the time of these runs; the ANAGRPID and CRTO run reports do not record the model themselves; runbooks written after 2026-09-10 must require it in the environment table) | follows a bug's `RUNBOOK.md`: builds kernels, runs the reproducers, traces the origin for `Fixes:`, packages a draft patch, writes `RUN-REPORT.md` | edit the patch or the scripts, add `Signed-off-by`, send |
| reviewers | three sub-agents (one Opus, two Sonnet) with fresh context | each reads the evidence folder against one charter and writes a verdict file | modify anything but their own file |
| operator | Andrew Stellman | reads the evidence and the reviews, amends the commit with his `Signed-off-by`, sends, pushes the evidence, answers the list | delegate the send or the sign-off |

The operator is the author of record and the only participant who signs. The kernel's
`Documentation/process/coding-assistants.rst` says an AI agent must not add a
`Signed-off-by`; the runbooks enforce that with `git commit -F <message>` and an
explicit instruction, and the operator adds the sign-off with `git commit --amend -s`
before sending.

## The pipeline, one bug at a time

### 1. Finding

Quality Playbook runs its six phases and iteration strategies over a subsystem snapshot
at a fixed commit (for nvmet: torvalds/linux `4d7d9486c04d`, v7.3-rc1) with a gathered
documentation corpus. The public run records are in the
[quality-playbook-linux](https://github.com/andrewstellman/quality-playbook-linux)
repository. A finding at this stage is a claim with citations, nothing more. Most
candidates are killed by the run's own validation; the ones that survive still have to be
reproduced before anyone believes them.

### 2. Choosing

The planner picks the candidate that is most likely to be real, has a host-visible
symptom, and has a minimal fix. Visible symptom and minimal patch are both required.
A bug that can only be shown by reading code is not pursued.

### 3. Reproducing, by hand first

The planner writes a reproducer script that prints exactly one of `RED:` (bug present)
or `GREEN:` (bug absent) as its last line and exits 1 or 0 accordingly. Any other output
is a broken script, not a result. The operator runs it in a QEMU guest on his own
machine:

- Apple Silicon Mac, `qemu-system-aarch64 -M virt -accel hvf`, Ubuntu 24.04 arm64 cloud
  image, ssh forwarded to `localhost:2222`, a key used only for this guest.
- For nvmet: target and host in the same guest over NVMe/TCP to `127.0.0.1:4420`,
  because Ubuntu does not ship `nvme-loop`.
- Kernels are built inside the guest from the snapshot commit with Ubuntu's config,
  debug info off, one `LOCALVERSION` suffix per build, so base and patched kernels
  coexist in GRUB and `uname -r` proves which one produced a capture.

Three kernels, three captures: unpatched snapshot (must be RED), snapshot plus this
patch only (must be GREEN), and where a second patch exists, snapshot plus the other
patch only (this bug must still be RED). The last one shows the patches are independent.
The scripts also run the other bug's reproducers on every boot as a cross-check that a
patch changes nothing it should not.

The stock Ubuntu kernel is run first as a cheap red, but the red of record is always the
snapshot commit, because that is what the patch is against.

### 4. Reproducing again, by autopilot

The planner writes `RUNBOOK.md`: a self-contained procedure for a fresh Claude Code
session with no memory of the manual work. It names the paths, the hard rules, the known
traps, the exact commands, the expected verdicts at each step, and the commit message
skeleton. The operator launches Claude Code with the model recorded in the run report and
pastes one line: read the runbook and follow it exactly.

The autopilot builds its own kernels with its own suffixes (reusing the manual run's
kernels is forbidden in the runbook), runs the reproducers, saves every command's output
to `cc-transcript.txt`, and stops at the first result that is not what the runbook says
to expect. It then traces the `Fixes:` commit by blaming the defective line and following
the history back until it finds the commit that introduced the expression, not the one
that last touched the function. It applies the patch on a fresh branch, runs
`checkpatch.pl --strict` and `get_maintainer.pl`, and writes `RUN-REPORT.md` with the
verdicts, the blame chain with diff excerpts, and a final `RESULT:` line.

Two independent reproductions with independently built kernels is the bar for
"confirmed".

### 5. Review

Three reviewer sub-agents run in parallel, each with fresh context, each reading the
evidence folder and the kernel source rather than the chat that produced them. Their
charters are in `review/PANEL.md` for each bug, and their full output is committed
alongside:

- **A, falsify the red/green (Opus).** Try to show the GREEN does not prove the fix: is
  the green kernel different from the red one in any way other than the patch; can the
  scripts produce a false verdict; is the symptom really caused by the mechanism
  claimed; are there other consumers of the changed value.
- **B, minimality and style (Sonnet).** Is this the smallest correct change written the
  way the subsystem writes code; is there a case where the old code was right and the
  new code is wrong; does the diff touch every buggy site and no other.
- **C, message and email (Sonnet).** Every sentence of the commit message must trace to
  a file in the evidence folder or a line of source. Checklist: `Fixes:` names the
  introducing commit (verify the blame chain independently); `Assisted-by:` matches
  what has actually been merged (survey `git log --grep='^Assisted-by:'` in a full
  clone, do not inherit the previous patch's form); the tested-on paragraph matches the
  raw captures; the spec quotation is verbatim from the spec text; standalone patch,
  `base-commit` present, one `Signed-off-by`, subject prefix and length right; no
  over-claims.

The planner reads the three files and writes `review/SYNTHESIS.md`: verdicts per
question, disagreements, and the exact list of changes required before sending. Nothing
goes out with an open FIX-REQUIRED.

### 6. Sending

The operator reads the final patch file himself, amends with `--amend -s`, and sends
with `git send-email` to the addresses `get_maintainer.pl` returned, Cc himself. Gmail
app passwords are created by the operator immediately before sending and revoked after;
they are never pasted into chat or stored in a config file.

### 7. Recording

The Message-ID, lore URL, recipients, and status go into the bug's README, committed
and pushed so the evidence URL in the patch resolves. Replies from the list and the
merge status are added as they happen.

## Rules every participant works under

- No fabrication. Every log in the evidence is pasted from what a command printed. A
  failed command is pasted as a failure.
- A reproducer result that is not a clean RED or GREEN halts the run; nobody retries
  with modifications.
- The autopilot may fix its environment (disk space, a missing package) and must record
  each fix; it may not change the experiment.
- Nothing is claimed as pushed, sent, or merged until the end state has been observed
  (`git ls-remote`, the send-email result line, the commit in `torvalds/master`).
- A `Fixes:` tag comes from blaming the defective line and reading the blamed commit's
  diff, never from finding a commit that touched the function.
- The AI never adds `Signed-off-by`, never sends, never pushes, never posts.
- Bot protection on lore.kernel.org is not bypassed; thread status is read by the
  operator in a browser.
- Commit messages are plain kernel prose: no flourish, no summary sentences tacked onto
  paragraphs, no claims that are not in the logs.

## Where spec claims come from

A bug that is a spec violation quotes the spec verbatim, with figure or section number,
from the text corpus the run itself used: for nvmet,
`repos/linux/nvme-target/reference_docs/cite/nvme-base-2.4.txt`, a `pdftotext`
conversion of NVM Express Base Specification 2.4 downloaded from nvmexpress.org. Quotes
are never taken from `REQUIREMENTS.md` or any other artifact the run derived, because
checking a run's conclusion against the run's own reading would be circular. The live
kernel tree (`torvalds/master`) is consulted only to confirm the defective lines still
exist upstream.

One caveat is stated where it applies: the corpus is revision 2.4 while nvmet advertises
2.1. Where a requirement might differ between revisions, the commit message cites 2.4
explicitly.

A conversion trap worth recording: `pdftotext` output contains form-feed characters that
Python's `splitlines()` counts as line breaks and `grep -n` does not, so line numbers
from the two tools diverge by hundreds of lines near the end of a long spec. Citations
are checked with the tool that will be used to verify them.

## Disclosure and trailers

Every patch discloses AI involvement in two places: a body sentence naming the tool and
its URL ("The issue was found by Claude Opus 5 running Quality Playbook, an LLM-driven
code review tool: https://github.com/andrewstellman/quality-playbook"), and an
`Assisted-by:` trailer.

`Documentation/process/coding-assistants.rst` gives the trailer form as
`Assisted-by: LLM [TOOL]`. Merged practice as of 2026-09-10, surveyed with
`git log origin/master --grep='^Assisted-by:'`, is `<Agent>:<model>` with an optional
harness in brackets; an nvmet-tcp commit (`14cc5a7e7773`) carries
`Assisted-by: Claude:claude-opus-4-8`. The nvmet patches therefore use
`Assisted-by: Claude:claude-opus-5 [Quality Playbook]`, naming the model that found the
bug and the harness it ran in. The bare `LLM` form on the virtio patch was what the
document specified at the time and was accepted, but the maintainer asked which LLM and
which agent afterward, so the trailer now answers that up front.

## What the virtio patch taught, and how the pipeline now prevents it

The first patch, [virtio-pci-intx](./virtio-pci-intx/), was merged, but its path there
exposed four mistakes. Each maps to a check in the pipeline above.

1. **Wrong `Fixes:` tag, twice.** v2 and v3 blamed `77cf524654a8` ("virtio_pci: split up
   vp_interrupt"), which only moved the line; the return value dates to `3343660d8c62`
   ("virtio: PCI device", 2007). The maintainer replied "this is still the wrong commit
   to blame" and merged the patch with the tag as sent. The tag had been chosen from the
   commit that touched the function. Now the autopilot blames the line, reads the blamed
   diff, follows the history back, and writes the chain into the report; reviewer C
   re-derives it independently.
2. **Sent as part of a series.** v2 went out as `[PATCH v2 3/4]` alongside three
   unrelated changes and the maintainer asked for a standalone repost. Now every bug is
   its own standalone patch with its own `base-commit`.
3. **Trailer form.** `Assisted-by: LLM` matched the document, but the maintainer
   replied "This is not the correct format. See Documentation" and later asked which
   LLM and which agent. The commit was merged with the bare form. Now the trailer names
   the model and the harness, and reviewer C's charter requires a survey of merged
   trailers rather than inheriting the previous patch's form.
4. **Testing described after the fact.** The maintainer's first question was "how was
   this tested?" and the red/green test was built in response. Now the red/green exists,
   twice, before the message is written, and the tested-on paragraph is checked against
   the raw captures.

Two smaller ones: the `Tested-by:` trailer is not used when the tester and the author
are the same person, and a claim about the documentation ("the docs require
`AGENT:MODEL`") that came from another assistant was checked against the file at the
base commit and found to be untrue before it could reach the list.

## Layout of a bug folder

```
<bug>/
  README.md                 defect, environment, red and green captures, summary, upstream status
  <name>.patch              the patch as tested (applies to the snapshot commit on its own)
  repro-*.sh                reproducer scripts, byte-identical to the copies that ran in the guest
  build-kernel.sh           the build script, likewise
  red-*.txt, green-*.txt    raw manual captures
  RUNBOOK.md                the autopilot's instructions
  RUN-REPORT.md             the autopilot's report
  cc-transcript.txt         every command and its output from the autopilot run
  cc-red-*.txt, cc-green-*.txt   the autopilot's captures
  DRAFT-0001-*.patch        the autopilot's draft (no Signed-off-by)
  MESSAGE-v2.txt            the message after review changes
  0001-*.patch              the patch as sent
  review/PANEL.md           the three charters and the common instructions
  review/A-*.md, B-*.md, C-*.md   the three reviews
  review/SYNTHESIS.md       verdicts, disagreements, required changes
```

## Limitations, stated plainly

- The reviewers are language models. They read the source and the captures and they
  cite what they read, but a SHIP from them is not a maintainer's review. It is a filter
  that runs before a maintainer's time is spent.
- The stock Ubuntu red for the CRTO bug was not captured with a clean verdict line
  because the script was being fixed between runs; the snapshot-commit red is the red
  of record and the README says so.
- The QPB run that found a bug is not the evidence for it. The run's `BUGS.md` entry is
  where the candidate came from; the evidence folder is where it was tested.
- The captures show what happened on one arm64 guest with one config. Nothing here
  claims coverage of other architectures or transports.
