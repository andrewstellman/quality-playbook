# Synthesis: nvmet CRTO-from-CAP patch review

Three reviewers, fresh context each, working from the raw captures, the kernel source at
the snapshot commit, the full-history clone, and the spec text. Charters in `PANEL.md`;
full reviews in `A-falsify-redgreen.md` (Opus), `B-patch-minimality.md` (Sonnet),
`C-message-and-email.md` (Sonnet).

## Verdicts

| question | A (falsify) | B (minimality) | C (message/email) |
|---|---|---|---|
| GREEN kernel differs only by the patch | SHIP | | |
| ANAGRPID cross-check identical to base | SHIP | | |
| Reproducer cannot fake a verdict | SHIP (tested, not reasoned) | | |
| Value at 0x68 is the target's CRTO, not cached or substituted | SHIP | | |
| "CSTS bits 6:0; nvmet writes RDY, CFS, SHST" | SHIP | | |
| `NVME_CAP_TIMEOUT(ctrl->cap)` is the right expression (CRWMT, CRIMT = 0) | | SHIP | |
| Smaller or better fix | | SHIP | |
| Every buggy site, no other | | SHIP | |
| Style | | SHIP | |
| Old code correct where new is not | | SHIP | |
| Every name in the message exists in the source | | | **FIX-REQUIRED** |
| `Fixes:` names the introducing commit | | | SHIP |
| `Assisted-by:` matches merged practice | | | SHIP |
| Tested-on matches captures | | | SHIP |
| Spec quote and figure | | | SHIP |
| Host paragraph supported | | | SHIP |
| Standalone, base-commit, no SoB in draft, author | | | SHIP |
| Subject prefix and length | | | SHIP |
| Over-claims | | | CONCERN, non-blocking |

Overall: one FIX-REQUIRED, raised independently by A (outside its charter, flagged so it
would not be lost) and by C. Nobody falsified the red/green, found a smaller correct
patch, or found an unsupported claim beyond the name.

## The defect

The draft's first sentence names `nvmet_get_property()`. No such function exists in the
snapshot or in the full clone; the function is `nvmet_execute_prop_get()`
(`fabrics-cmd.c:38`). The wrong name predates this run: it is in the QPB `BUGS.md` entry,
the evidence `README.md`, and the runbook's message skeleton, and the runbook's claim
checks did not cover it because the planner did not know it was wrong. The panel caught
it. **Action: rename in the message (`../MESSAGE-v2.txt`), the README, and the runbook.**

## The concern

C (over-claim check) read the host's CRTO read site (`host/core.c:2815-2832` at the
snapshot): when CRWMS is set the host takes the larger of CRTO.CRWMT and CAP.TO, with a
comment that "some devices are known to get this wrong". C suggested one clause saying
what the host would do once CRWMS is advertised. **Action: none.** The sentence as sent is
true and bounded; the host's `max()` means that even with CRWMS set a Linux initiator
would mask this bug, which is a reason the patch is a conformance fix rather than a
behavior fix, and the message already says so in plain terms. Adding the clause would
invite the "so why bother" reading without adding a fact the maintainer cannot see in
the host code.

## Two things the panel confirmed that we had only asserted

- A rebuilt the reproducer's parse and arithmetic against constructed inputs and found no
  input that prints GREEN with CRTO still 0; the only failure mode is `UNEXPECTED`, which
  the runbook treats as a stop.
- A found four unpatched kernels across four suffixes in the guest all reading CRTO `0`
  and both patched ones reading `f`, and the ANAGRPID cross-check diff between base and
  patched captures is exactly the four CRTO lines.

## Required before sending

1. Amend the commit message with `../MESSAGE-v2.txt` (one word changed:
   `nvmet_get_property()` to `nvmet_execute_prop_get()`), adding the operator's
   `Signed-off-by`, and regenerate the patch with `git format-patch`.
2. Nothing else. The diff, the `Fixes:` line, the trailer, and the tested-on paragraph
   are unchanged.
