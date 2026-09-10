# Reviewer C: commit message and email against the evidence

Charter: every sentence in the draft patch's commit message must be traceable to a file in
the evidence folder or to the source, and the email must be free of the mistakes made on
the previous patches from this project.

Files read: `README.md`, `RUNBOOK.md`, `RUN-REPORT.md`, `cc-red-base.txt`,
`cc-green-crto.txt`, `nvmet-crto-from-cap.patch`,
`DRAFT-0001-nvmet-derive-the-CRTO-property-from-CAP-not-CSTS.patch`,
`repro-bug001-crto.sh`, `build-kernel.sh`; the snapshot source at
`/Users/andrewstellman/Documents/QPB/repos/linux/nvme-target/` (`drivers/nvme/target/fabrics-cmd.c`,
`core.c`, `include/linux/nvme.h`); the spec text `nvme-base-2.4.txt`; and the sibling
`../nvmet-anagrpid/` evidence (`README.md`, `0001-nvmet-accept-ANA-group-ID-NVMET_MAX_ANAGRPS-in-confi.patch`,
`MESSAGE-v2.txt`, `review/PANEL.md`, `review/SYNTHESIS.md`, `review/C-message-and-email.md`).

I was given read access to a full-history clone at `~/src/linux` (mounted for me at
`/sessions/kind-zealous-edison/mnt/linux` for shell commands; same content, same path
semantics as `~/src/linux` for git purposes) and ran every git command in the charter
myself against it, live, rather than trusting the RUN-REPORT transcript. Exact commands
and output are quoted below. I did not check out, commit, modify, push, or otherwise
change anything in that clone; every command was a read (`git blame`, `git show`,
`git log`, `git config`, and one `checkpatch.pl` invocation against the already-committed
`HEAD`, which does not write to the tree).

## Checklist

### 1. Every function/macro/field/register name exists in the snapshot source with that exact name

**FIX-REQUIRED.** The draft's opening sentence
(`DRAFT-...patch:6`, and `README.md:14`, `RUNBOOK.md:14`):

> `nvmet_get_property()` answers a Property Get of CRTO with `NVME_CAP_TIMEOUT(ctrl->csts)`.

I grepped the actual function name in `fabrics-cmd.c`:

```
$ grep -n "nvmet_get_property\|nvmet_execute_prop_get" drivers/nvme/target/fabrics-cmd.c
38:static void nvmet_execute_prop_get(struct nvmet_req *req)
113:		req->execute = nvmet_execute_prop_get;
```

There is no function named `nvmet_get_property` anywhere in the file. I widened the
search to the whole target tree and to the full-history clone's committed tree at the
snapshot commit, and to be sure it isn't a macro or wrapper I don't know about:

```
$ grep -rn "nvmet_get_property" ~/Documents/QPB/repos/linux/nvme-target/
(no files found)
$ git show 4d7d9486c04d917265f64c55bd23b2cc4fe7749c -- drivers/nvme/target/fabrics-cmd.c | grep -c nvmet_get_property
0
```

The function the message describes is `nvmet_execute_prop_get()`
(`fabrics-cmd.c:38`), which contains the `switch (offset)` with the `case
NVME_REG_CRTO:` block the message is about (verified: line 67 is the `case`, matching
the blame output below). `nvmet_get_property` does not exist under any name at this
commit. Per the checklist rule ("A name that does not exist is FIX-REQUIRED"), this is
FIX-REQUIRED: change `nvmet_get_property()` to `nvmet_execute_prop_get()` in the first
sentence of the commit message before sending.

This is not something introduced during the autopilot run — `README.md:14` and
`RUNBOOK.md:14` both already say `nvmet_get_property()`, so the wrong name was baked
into the diagnosis before the runbook was written, and the autopilot run correctly kept
the message's shape rather than inventing wording, per its instructions. It still has to
be fixed before this reaches the list; nobody upstream will have a `nvmet_get_property`
to look up.

Every other name in the message checks out exactly:

- `NVME_CAP_TIMEOUT(cap)` — `include/linux/nvme.h:166`, verified in the git-tracked
  clone: `#define NVME_CAP_TIMEOUT(cap) (((cap) >> 24) & 0xff)` (matches the RUN-REPORT
  grep, which I re-ran).
- `ctrl->csts`, `ctrl->cap` — both real fields of `struct nvmet_ctrl`, both written in
  `core.c` (`NVME_CSTS_RDY`/`CFS`/`SHST_CMPLT` writes and `ctrl->cap |= (15ULL << 24)`
  at line 1460).
- `nvmet_init_cap()` — real function, `core.c:1453`, called from `nvmet_alloc_ctrl()`
  at line 1650. (RUN-REPORT step 3 already caught and fixed the earlier
  `nvmet_init_ctrl()` typo from the original runbook template — that fix is correctly
  reflected in the sent draft, which says `nvmet_init_cap()`. Good catch by the prior
  run; I re-verified it holds.)
- `CRTO.CRWMT`, `CAP.TO`, `CC.CRIME`, `CAP.CRMS.CRWMS` — spec notation, not C
  identifiers; checked against the spec text below (§5) rather than the source.

### 2. `Fixes:` tag — introducing commit, not one that moved the line; tag format

**SHIP.** I re-ran every command in RUNBOOK.md step 3 myself against the live clone
(not reusing RUN-REPORT's transcript):

```
$ git blame -L 67,69 4d7d9486c04d917265f64c55bd23b2cc4fe7749c -- drivers/nvme/target/fabrics-cmd.c
1e058089d28f5 (Keith Busch 2024-11-04 14:17:59 -0800 67) 		case NVME_REG_CRTO:
1e058089d28f5 (Keith Busch 2024-11-04 14:17:59 -0800 68) 			val = NVME_CAP_TIMEOUT(ctrl->csts);
1e058089d28f5 (Keith Busch 2024-11-04 14:17:59 -0800 69) 			break;

$ git show 1e058089d28f5 -- drivers/nvme/target/fabrics-cmd.c
commit 1e058089d28f58bd194d3c0f06512f42079f5a1d
Author: Keith Busch <kbusch@kernel.org>
...
    nvmet: implement crto property

    This property is required for nvme 2.1. The target only supports ready
    with media, so this is just the same value as CAP.TO.
...
@@ -64,6 +64,9 @@ static void nvmet_execute_prop_get(struct nvmet_req *req)
 		case NVME_REG_CSTS:
 			val = ctrl->csts;
 			break;
+		case NVME_REG_CRTO:
+			val = NVME_CAP_TIMEOUT(ctrl->csts);
+			break;
 		default:
 			status = NVME_SC_INVALID_FIELD | NVME_STATUS_DNR;
 			break;

$ git log --oneline -S'NVME_CAP_TIMEOUT(ctrl->csts)' 4d7d9486c04d917265f64c55bd23b2cc4fe7749c -- drivers/nvme/target/fabrics-cmd.c
1e058089d28f nvmet: implement crto property

$ git log --oneline -S'NVME_REG_CRTO' 4d7d9486c04d917265f64c55bd23b2cc4fe7749c -- drivers/nvme/target/
1e058089d28f nvmet: implement crto property

$ git log -1 --abbrev=12 --format='Fixes: %h ("%s")' 1e058089d28f5
Fixes: 1e058089d28f ("nvmet: implement crto property")
```

All three lines of the `case NVME_REG_CRTO:` block are pure additions with no `-` line
in the hunk (context before the addition goes `NVME_REG_CSTS` case straight to
`default:`, so there was no prior CRTO handler for the expression to have moved from).
Both pickaxe searches — the exact expression and the broader `NVME_REG_CRTO` token
anywhere in the target — return exactly this one commit up to the snapshot, so nothing
later touched it either. The commit's own message ("this is just the same value as
CAP.TO") states the intent the code fails to deliver, confirming the defect is in the
introducing commit, not a regression. This matches RUN-REPORT.md's reasoning
line-for-line, and I reproduced every command myself rather than trusting the
transcript. Tag format: 12-character hash (`1e058089d28f`), subject in parentheses and
double quotes — correct, and matches `DRAFT-...patch:35` verbatim.

### 3. `Assisted-by:` form vs. merged practice and the ANAGRPID patch as sent

**SHIP.** Draft trailer (`DRAFT-...patch:36`): `Assisted-by: Claude:claude-opus-5
[Quality Playbook]`. I surveyed merged practice myself rather than trusting PANEL.md's
example:

```
$ git log origin/master --grep='^Assisted-by:' -40 --format='%h %s%n  %(trailers:key=Assisted-by,valueonly)'
```

gives 40 recent merged commits with forms including bare `LLM`, `<Agent>:<model>`
(`Claude:claude-opus-5`, `Codex:gpt-5`, `Gemini:gemini-3.1-pro`, `OpenAI-Codex:GPT-5`),
`<Agent>:<model> [tool/step]` (`Kiro:claude-opus-5 checkpatch sparse`), and one
`nvmet-tcp` commit, `14cc5a7e7773`, with `Claude:claude-opus-4-8` — restricting to
`drivers/nvme` confirms the same bracket-free form there
(`22eb631bf86e nvme-fc: ... — Claude:claude-opus-4-6`,
`659ae9d02cb5 nvmet: pci-epf: ... — Claude:claude-opus-4-8`).

None of the `drivers/nvme`-restricted or top-40 samples happen to carry a `[...]`
qualifier, so I widened the search across all history for the bracket form specifically,
since that's the part of the draft's trailer PANEL.md's instructions asserted as
precedented:

```
$ git log origin/master --grep='^Assisted-by:.*\[' -E -100 --format='%h %s%n  %(trailers:key=Assisted-by,valueonly)'
139f57343b3d scsi: mpi3mr: ... — Claude:Sonnet5 [Claude Code]
3cf908dd1396 clk: zynq: ... — Claude:claude-opus-5 [kernel-doc]
0991f3b4624e regulator: ab8500: ... — Claude:claude-opus-5 [kernel-doc]
828cd614e2af hwmon: ... — Claude:claude-opus-4-7 [Claude Code]
...
```

So `<Agent>:<model> [qualifier]` is real merged practice, and `Claude:claude-opus-5`
specifically (same agent, same model string, lowercase, hyphenated) is merged more than
once. The `[Quality Playbook]` qualifier names the review tool the same way merged
commits use `[Claude Code]`, `[kernel-doc]`, `[Amazon Kiro IDE]` to name the harness or
step that produced the finding — a reasonable fit to the pattern, not an invented one.

Comparing directly with the sibling patch: `../nvmet-anagrpid/0001-nvmet-accept-ANA-group-ID-NVMET_MAX_ANAGRPS-in-confi.patch:45`
has `Assisted-by: Claude:claude-opus-5 [Quality Playbook]` — identical string, and its
body carries the identical sentence: "The issue was found by Claude Opus 5 running
Quality Playbook, an LLM-driven code review tool:
https://github.com/andrewstellman/quality-playbook" (`0001-...patch:40-42`). The CRTO
draft (`DRAFT-...patch:31-33,36`) matches both word for word. One caveat worth naming
for the record: the ANAGRPID patch is "sent" (per its `README.md:10-13`, "Status:
awaiting review", with a Message-ID and lore.kernel.org link) but not yet merged, so it
is a precedent for what this project has sent, not additional evidence of *merged*
upstream practice beyond the `git log` survey above. That survey stands on its own,
independent of the sibling patch.

### 4. "Tested on" paragraph vs. raw captures

**SHIP.** Draft (`DRAFT-...patch:25-29`):

> Tested on 7.3.0-rc1-qpb-cc-crto-base+ (unpatched) and 7.3.0-rc1-qpb-cc-crto+
> (patched) in an arm64 QEMU guest with nvmet over NVMe/TCP to 127.0.0.1, reading the
> properties with nvme get-property. Before: CAP reads 0x8200f0003ff (TO = 15) and CRTO
> reads 0. After: CAP is unchanged and CRTO reads 0xf, so CRWMT = 15 = CAP.TO.

- Release strings: `cc-red-base.txt:1` `kernel: 7.3.0-rc1-qpb-cc-crto-base+`;
  `cc-green-crto.txt:1` `kernel: 7.3.0-rc1-qpb-cc-crto+`. Exact match.
- Before values: `cc-red-base.txt:26-32` — raw CAP `8200f0003ff`, raw CRTO `0`,
  `CAP.TO = 15   CRTO.CRWMT = 0`. Matches "CAP reads 0x8200f0003ff (TO = 15) and CRTO
  reads 0" exactly.
- After values: `cc-green-crto.txt:25-32` — raw CAP `8200f0003ff` (unchanged), raw CRTO
  `f`, `CAP.TO = 15   CRTO.CRWMT = 15`. Matches "CAP is unchanged and CRTO reads 0xf, so
  CRWMT = 15 = CAP.TO" exactly.
- Transport/tool: `repro-bug001-crto.sh:48-51` reads CAP at offset 0x00 and CRTO at
  offset 0x68 via `nvme get-property`, over the TCP fabric set up earlier in the script
  (`addr_trtype tcp`, `addr_traddr 127.0.0.1`, `addr_trsvcid 4420`). Matches "NVMe/TCP to
  127.0.0.1 ... nvme get-property."
- Architecture: `RUN-REPORT.md` environment table, `host | macOS 26.3 (25D125), arm64`;
  the guest is the same arm64 QEMU guest as the ANAGRPID evidence (`README.md:41-44`
  points at `../nvmet-anagrpid/README.md`, which records "Ubuntu 24.04.4 LTS arm64
  cloud image"). Matches "arm64 QEMU guest."

### 5. Spec quotation and figure reference

**SHIP.** I grepped the spec text directly rather than trusting RUN-REPORT's line
numbers:

```
$ grep -n "Figure 36: Offset 0h: CAP" nvme-base-2.4.txt
552:Figure 36: Offset 0h: CAP – Controller Capabilities ...
4332:                        Figure 36: Offset 0h: CAP – Controller Capabilities
4397:                  Figure 36: Offset 0h: CAP – Controller Capabilities
4464:                        Figure 36: Offset 0h: CAP – Controller Capabilities
4518:                        Figure 36: Offset 0h: CAP – Controller Capabilities
$ grep -n "Figure 57: Offset 68h: CRTO" nvme-base-2.4.txt
573:Figure 57: Offset 68h: CRTO – Controller Ready Timeouts ...
```

and read lines 4483–4489 directly:

```
4483    If the Controller Ready Independent of Media Enable (CC.CRIME) bit is cleared to
4484    '0' and the worst-case time for the CSTS.RDY bit to change state is due to enabling
4485    the controller after the CC.EN bit transitions from '0' to '1', then this field shall be
4486    set to:
4487        a)   the value in the Controller Ready With Media Timeout (CRTO.CRWMT)
4488             field; or
4489    Impl b)   FFh if the value in the CRTO.CRWMT field is greater than FFh.
```

This sits between the 4464 and 4518 occurrences of the Figure 36 header, i.e. inside
Figure 36's CAP.TO field description, not Figure 57. The draft (`DRAFT-...patch:12-16`)
attributes the quote to "Figure 36 (CAP)" — correct — and the quoted portion, "shall be
set to: a) the value in the Controller Ready With Media Timeout (CRTO.CRWMT) field; or
b) FFh if the value in the CRTO.CRWMT field is greater than FFh," matches the spec text
verbatim, word for word and punctuation for punctuation (the paraphrase outside the
quotation marks — "when CC.CRIME is '0'" for "is cleared to '0'" — is outside the quoted
span and is an accurate gloss). I also confirmed the spec's own naming convention for
compound field references: line 4320, "referred to by the name CAP.CRMS.CRWMS," is the
spec itself using exactly the "CAP.CRMS.CRWMS" notation the commit message uses in its
host paragraph — that's not an invented shorthand.

### 6. Host paragraph — Linux host reads CRTO only under CAP.CRMS.CRWMS

**SHIP**, re-derived independently:

```
$ git show 4d7d9486c04d917265f64c55bd23b2cc4fe7749c:drivers/nvme/host/core.c | grep -n -B4 -A10 'NVME_REG_CRTO'
2814-	timeout = NVME_CAP_TIMEOUT(ctrl->cap);
2815-	if (ctrl->cap & NVME_CAP_CRMS_CRWMS) {
2816-		u32 crto, ready_timeout;
2817-
2818:		ret = ctrl->ops->reg_read32(ctrl, NVME_REG_CRTO, &crto);
...
```

The only `NVME_REG_CRTO` read in the host core is gated by
`ctrl->cap & NVME_CAP_CRMS_CRWMS`. Supported as written.

On the over-claim question the charter asks explicitly ("is 'Linux initiators have not
seen the wrong value' an over-claim? Consider out-of-tree or non-Linux initiators"): no.
The sentence is scoped to "Linux initiators," not "no initiator," and the very next
sentence immediately names a concrete counter-example that *does* see the bug ("A host
that reads the property directly does, for example nvme-cli's get-property"). That
already covers the class of reader this caveat exists for — anything that queries the
property directly rather than going through the in-kernel host driver's CRWMS-gated
path, Linux or not. I don't think the message needs to enumerate out-of-tree or
non-Linux host drivers by name; the "reads the property directly" framing already
generalizes to them without asserting anything about them specifically.

### 7. Standalone patch, `base-commit`, no `Signed-off-by`, author consistency

**SHIP.**

- `DRAFT-...patch:4`: `Subject: [PATCH] ...` — no series marker. `git format-patch -1`
  (RUN-REPORT.md:775) is a single-patch invocation.
- `base-commit: 4d7d9486c04d917265f64c55bd23b2cc4fe7749c` at `DRAFT-...patch:55`,
  matching the snapshot commit named throughout.
- `Signed-off-by:` count in the draft: `grep -c "Signed-off-by:"
  DRAFT-0001-nvmet-derive-the-CRTO-property-from-CAP-not-CSTS.patch` → 0. Correct per
  the runbook: the operator adds it when amending, consistent with
  `Documentation/process/coding-assistants.rst`'s rule against AI agents adding
  Signed-off-by. `checkpatch --strict` on `HEAD` in the live clone reproduces the same
  single expected error and nothing else:

  ```
  $ ./scripts/checkpatch.pl --strict --no-signoff -g HEAD
  total: 0 errors, 0 warnings, 0 checks, 8 lines checked
  Commit 114455e4fd47 ("nvmet: derive the CRTO property from CAP, not CSTS") has no
  obvious style problems and is ready for submission.
  ```

- Author: `git log -1 --format='%an <%ae>' 114455e4fd47` → `Andrew Stellman
  <astellman@stellman-greene.com>`, matching `DRAFT-...patch:2`. `git config user.name`
  in the clone returns `Andrew Stellman` (no override needed).

### 8. Subject line: prefix, length, mood

**SHIP** — and I can do better than the sibling review here, which had to flag this as
a CONCERN for lack of a full clone. I have the full clone:

```
$ git log --oneline -30 4d7d9486 -- drivers/nvme/target/fabrics-cmd.c
f1a8846e0638 nvmet: fix max_qid race between configfs and controller allocation
bb78836b3a7c nvmet: fabrics: add CQ init and destroy
c91a20129185 nvmet-auth: authenticate on admin queue only
...
cc3d4671a0db nvmet: add a missing endianess conversion in nvmet_execute_admin_connect
43043c9b9725 nvmet: Introduce nvmet_req_transfer_len()
6202783184bf nvmet: Improve nvmet_alloc_ctrl() interface and implementation
1e058089d28f nvmet: implement crto property
5a47c2080a73 nvmet: support reservation feature
...
```

`nvmet:` is the overwhelming, near-universal prefix for this file's history, including
the `Fixes:` commit itself (`1e058089d28f nvmet: implement crto property`). The draft's
subject, `nvmet: derive the CRTO property from CAP, not CSTS`, matches.

- Length: `echo -n "nvmet: derive the CRTO property from CAP, not CSTS" | wc -c` → 50,
  well under 75.
- Mood: "derive" is imperative. SHIP.

### 9. Every body line 75 columns or fewer

**SHIP.** `git show 114455e4fd47 --format=%B -s | awk '{ print length }'` on every
non-blank line: longest is 71 (two lines: "Before: CAP reads 0x8200f0003ff (TO = 15)
and CRTO reads 0. After: CAP" and "7.3.0-rc1-qpb-cc-crto+ (patched) in an arm64 QEMU
guest with nvmet over"). The URL line
(`https://github.com/andrewstellman/quality-playbook`) is 50 characters and sits on its
own line, under the limit with room to spare. All lines pass.

## Over-claim / under-claim check

- **"Advertising CRWMS is a separate change."** (`DRAFT-...patch:23`) The charter asks
  whether this needs more: "should the message say what a host would do differently
  once CRWMS is advertised?" I read the host's own comment at the CRTO read site
  (`drivers/nvme/host/core.c:2825-2828`): "CRTO should always be greater or equal to
  CAP.TO, but some devices are known to get this wrong. Use the larger of the two
  values." That's a genuinely useful one-sentence addition a maintainer might want —
  once nvmet sets CRWMS, the in-tree host driver will read CRTO and take
  `max(CRTO.CRWMT, CAP.TO)`, so a correct CRTO stops being cosmetic and starts
  affecting the enable-timeout the host actually waits for. This is a **CONCERN, not
  blocking**: the sentence as written is not wrong or unsupported, it is just terser
  than it could be. I would not hold the patch for it, but if the message is touched
  again before sending, adding one clause here would preempt the obvious "why does this
  matter if nobody reads it" maintainer question more directly than the current
  "Advertising CRWMS is a separate change" does on its own.
- No other superlative or unbounded claim appears. "nvmet reports 15 in CAP.TO and 0 in
  CRTO.CRWMT" is bounded and directly evidenced (§4 above). "Take the value from
  ctrl->cap, where the timeout is actually stored" is a plain factual description of
  the one-line diff, verified against the diff itself.
- **Under-claim check (not in the charter's list, but worth flagging alongside the
  wrong-function-name defect):** the message never names the file
  (`drivers/nvme/target/fabrics-cmd.c`) or the switch statement
  (`nvmet_execute_prop_get()`'s `switch (offset)`) by a name that actually exists once
  §1's fix lands — after the fix, be sure the corrected sentence still reads
  grammatically ("nvmet_execute_prop_get() answers a Property Get of CRTO with
  NVME_CAP_TIMEOUT(ctrl->csts)" scans fine as a drop-in replacement, so no follow-on
  rewording should be needed beyond the function name itself).

## Precedent-checklist recap (mistakes made on previous patches from this project)

| Item | Verdict |
|---|---|
| Every name in the message exists in the source with that exact spelling | **FIX-REQUIRED** — `nvmet_get_property()` does not exist; the function is `nvmet_execute_prop_get()`. Confirmed by direct grep of the snapshot source and the full-history clone at the snapshot commit. |
| `Fixes:` names the introducing commit, correct tag format | SHIP — independently re-ran the full blame/pickaxe chain myself against a live full-history clone (not the shallow snapshot the ANAGRPID reviewer was stuck with) |
| `Assisted-by:` form matches merged practice and the sibling patch | SHIP — surveyed merged history myself (`<Agent>:<model> [qualifier]` is real, repeated, merged practice); matches `../nvmet-anagrpid/0001-*.patch` word for word |
| "Tested on" paragraph matches raw captures | SHIP |
| Spec quotation verbatim, correct figure | SHIP — grepped and read the spec text directly, confirmed CAP.TO sits in Figure 36 as claimed |
| Host paragraph supported; not an over-claim about non-Linux hosts | SHIP — re-derived the host core.c gate myself; the "reads it directly" clause already generalizes without needing to name non-Linux hosts |
| Standalone, `base-commit`, no Signed-off-by (operator adds it), author consistent | SHIP |
| Subject prefix, length, mood | SHIP — full clone available to me; `nvmet:` is the dominant, exclusive-in-practice prefix for this file, unlike the ANAGRPID review which had to flag this as unverifiable |
| Every body line ≤ 75 columns | SHIP — longest line is 71 |
| Over-claims | None found. One non-blocking CONCERN: the CRWMS-is-separate sentence could be one clause richer for a maintainer, not required |

## Overall verdict

**FIX-REQUIRED.** One defect must be fixed before this is sent: the commit message's
opening sentence names a function, `nvmet_get_property()`, that does not exist anywhere
in the snapshot source or the full-history clone at the snapshot commit — the real
function containing the `case NVME_REG_CRTO:` block is `nvmet_execute_prop_get()`
(`drivers/nvme/target/fabrics-cmd.c:38`). This error predates the autopilot run (it is
already in `README.md:14` and `RUNBOOK.md:14`), so it is not something Claude Code
introduced while packaging the patch — but it is now baked into the draft that is about
to go to linux-nvme, and a maintainer will notice a function name they cannot find. Fix:
replace `nvmet_get_property()` with `nvmet_execute_prop_get()` in the first sentence,
regenerate the commit and the draft patch, and re-run `checkpatch.pl --strict
--no-signoff` once more (it will not catch this, since it's not a style problem, but the
diff/patch content should be re-diffed against the tested `nvmet-crto-from-cap.patch`
again after the message-only edit to confirm nothing else changed).

Everything else in the commit message and email — the `Fixes:` tag and its underlying
reasoning (independently re-derived against a full-history clone, not the transcript),
the `Assisted-by` trailer and provenance sentence (checked against a fresh merged-history
survey and against the sibling patch as sent), the "Tested on" paragraph, the spec
quotation and figure reference, the host paragraph, and the
series/base-commit/Signed-off-by/author/subject/line-length mechanics — is traceable
line-for-line to the evidence folder, the source, and the spec text, and I found no
over-claim in the text that would actually be sent. Once the one function-name fix
lands, I have no remaining objection.
