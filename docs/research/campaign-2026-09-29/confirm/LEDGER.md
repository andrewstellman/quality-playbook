# Confirmation ledger, campaign 2026-09-29 (running; one line per entry)

Verdicts: CONFIRMED / DUP (already reported) / NOT-A-BUG / UNCLEAR / DOCS (docs wrong, code intended) / PENDING (confirmer cut off, rerun).

## zod (full triage of 001-023 in zod/TRIAGE.md)
- 024 openapi-3.0 nullable enum/literal omits null from enum: CONFIRMED (OAS 3.0.3 nullable text; nullProcessor already emits enum:[null]; downstream nestjs-zod #416, mastra #24516)
- 025 openapi-3.0 nullable $ref: nullable beside allOf with no type: CONFIRMED (OAS 3.0.3; fix spelling is a design choice)
- 026 fromJSONSchema ignores required names without properties: DUP of #6634 case 2 (round-trip angle not in #6634)
- 027 basics.mdx says parse() deep-clones; any/unknown/date/custom returned by reference: DOCS (api.md z.instanceof section already says nothing is cloned; tests pin pass-through; #996 was an earlier wording fix)
- 028 codecs.mdx says encode throws if a transform exists anywhere; only throws when reached: DOCS (one-sentence doc fix)

## click
**Filing constraint:** Pallets' LLM/AI policy (palletsprojects.com/contributing/llm-ai) closes and may block any issue or PR that looks AI-generated, including descriptions; confirmers found #3636, #3824, #3825, #3846, #3849 closed with label "rejected AI". click findings are research targets only unless Andrew writes a report himself.
- 001 atomic write replaces destination even when the write raises: CONFIRMED (docs "upon completion"; `_AtomicFile.close(delete=...)` ignores delete; File-param path needs context plumbing)
- 002 hidden-input prompt shows its default: DUP / declined (#687, #1419: maintainer 'passwords don't have a programmatic default'; show_default=False exists)
- 003 default_map string not split for multiple=True: UNCLEAR (docs + CHANGES scope the split to nargs>1/Tuple; code comment at core.py:2621 claims broader intent)
- 004 BOOL AttributeError on int: DUP (#1553, #1567; re-filed #3846/#3849 closed "rejected AI")
- 005 prompt default for a bool flag treats "false"/"off" as True: UNCLEAR leaning CONFIRMED (bool() cast is deliberate per PR #3030 and pinned for "foo"; disagrees with required=True default="off" -> False)
- 006 accepting a non-empty default at confirmation prompt loops forever: DUP (#3702 + PR #3703, closed "rejected AI"; still present on main)
- 007 click.command(params=L) mutates the caller's list; reused decorator keeps first help: CONFIRMED (#2131 use case crashes; #2294 precedent; click-extra worked around it downstream, never filed)
- 008 FloatRange accepts NaN: NOT-A-BUG (#3347/#3348 rejected; davidism: accepting all floats is fine)
- 009 zsh completion breaks on newline in help: DUP (PR #3636 closed "rejected AI", locked; fish/powershell siblings fixed)
- 010 echo() appends newline into caller's bytearray: CONFIRMED (one-line fix; not reported)
- 011 unbounded IntRange help shows x<=None: CONFIRMED (core.py:3594 `if range_str:` guard anticipates empty; not reported)
- 012 prompt lists Enum choices as Color.RED but accepts RED: DUP (#3028 closed 'fixed in #3004', but #3004 only fixed --help; still present at HEAD, file as 'not actually fixed')
- 013 get_app_dir returns a relative path when XDG_CONFIG_HOME is empty: CONFIRMED (XDG spec: 'not set or empty' -> default; PR #3683 on get_app_dir was 'rejected AI')
- 014 chained Group accepts nested group via constructor: UNCLEAR (test_chained builds exactly this on purpose; nested group runs fine, so the doc rule may be stale)
- 015 'Did you mean' ignores list_commands (CommandCollection, lazy groups): UNCLEAR leaning CONFIRMED (help and completion use list_commands; third-party bigbio/hvantk#305 hit it)
- 016-071: NOT CONFIRMED — click stopped 2026-09-29 by Andrew (Pallets AI policy: nothing can be filed)

## adonisjs-http-server
Contribution guide (adonisjs/.github CONTRIBUTING): no AI policy; "perfect issue" = a failing test in the repo plus a GitHub issue; bug PRs "mostly accepted once the bug has been confirmed".
- 001 uuid() matcher regex `[0-9a-zA-F]` accepts g-z: CONFIRMED (typo from PR #53; one-char fix)
- 002 routes without a domain 404 on hosts matching a domain group: UNCLEAR (isolation looks intentional per core #1053; doc line 438 loose; fallback would be breaking)
- 003 signed URLs with params needing percent-encoding never verify: CONFIRMED (signs encoded path, verifies decoded request.url())
- 004 redirect withQs on a target that already has ?query gives a second ?: CONFIRMED (appendQueryString helper exists, unused)
- 005 redirect().back() throws URIError on malformed Referer -> 500: CONFIRMED, SECURITY-ANGLE (client-triggerable 500; sibling of fixed #118) -> set aside per rule
- 006 cookie maxAge: 0 dropped (truthiness check): CONFIRMED (clearCookie exists, so impact modest; one-line fix)
- 007 plainCookie({encode:true}) throws "enc is not a function": CONFIRMED (option name collides with cookie-es encode)
- 008 brisk redirect loses qs after the first request (options.qs = undefined mutates caller's object): CONFIRMED
- 009 request.fresh() ignores headers set via response wrapper: CONFIRMED (its own JSDoc shows the failing pattern)
- 010 method spoofing: non-string _method -> 500: CONFIRMED (crash half only), SECURITY-ANGLE (client-triggerable 500 when spoofing enabled) -> set aside per rule; body half declined in core #1116
- 011 authority() consults X-Forwarded-Host despite JSDoc: DOCS (code changed on purpose in 0a30965; JSDoc stale)
- 012 X-Forwarded-Proto not lower-cased: UNCLEAR (RFC-based; JSDoc return contract 'http'|'https' supports it)
- 013 HEAD on response.download() omits Content-Length: UNCLEAR leaning CONFIRMED (docs say download sets content-length; RFC 9110 SHOULD)
- 014 response.send(new Error()) serializes to {} JSON: CONFIRMED (docs: error objects converted via toString; RegExp branch exists, Error missing)
- 015 redirect().status(301) ignored if response.status() was set earlier: CONFIRMED (safeStatus; #48/#49 maintainer: redirects should be 3xx)
- 016 abort() with no body says "Internal server error" for any status: UNCLEAR (body is a required param; cosmetic)
- 017 sync-throwing route handler skips upstream middleware: CONFIRMED (docs: upstream "always executed"; async path works; test pins async only)
- 018 group helpers crash on router.on() without a handler: UNCLEAR (docs never show a handler-less brisk route; ignoring it could drop group middleware)
- 019 URL builders freeze their domain list at first call: UNCLEAR leaning CONFIRMED (internal inconsistency; misuse-adjacent)
- 020 cookie readers replace an empty unencoded cookie with the default (|| vs ??): CONFIRMED, narrower than reported (0/false lost upstream in @poppinss/utils)
- 021 Referer host comparison case-sensitive: CONFIRMED for case (fails closed), UNCLEAR for explicit port
- 022 trusted-proxy cache ignores which trust function asks: UNCLEAR, SECURITY-ANGLE (XFP/XFH trust bypass when >1 trust function) -> set aside
- 023 URL lookup failures throw plain Error, not E_CANNOT_LOOKUP_ROUTE: CONFIRMED (regression from v6, core #4456 trace shows typed error)
- 024 absolute-form request target 404s: CONFIRMED (RFC 9112 §3.2.2 MUST; docs: request.url() relative to hostname)
- 025 domain routes don't match mixed-case host: UNCLEAR (RFC 3986 case-insensitive; trailing-dot half weak; :tenant passes case through)
- 026 generateTypes ALL map: domain route overwrites root route of same name: CONFIRMED (code comment at main.ts:636 states the prefixing intent)
- 027 jsonp() ignores ?callback despite its JSDoc: UNCLEAR (JSDoc stale since v4; adding lookup would create XSS risk)
- 028 type() writes "Content-Type: false" for unknown types / extension-less downloads: CONFIRMED
- 029 download that fails after stat sends file's Content-Length with 19-byte error body: CONFIRMED, SECURITY-ANGLE (keep-alive response desync) -> set aside
- 030 exception's async report() not awaited -> unhandled rejection: CONFIRMED, SECURITY-ANGLE (process crash under Node default) -> set aside
- 031 plainCookie cache ignores encoded flag: CONFIRMED
- 032 HTML status pages keep an earlier 2xx status/body: CONFIRMED (docs: render status page for error.status; JSON path correct)
- 033 vary() lost when Vary set via header(): UNCLEAR leaning CONFIRMED (#139 fixed same store split for cookies)
- 034 status(205).send(body) writes the body: CONFIRMED (RFC 9110 MUST NOT; resetContent() already sends none; 204/304 handled)
- 035 URL builder accepts '' for a required param -> URL of a different route: UNCLEAR (null/undefined check looks deliberate)

adonisjs totals: 35 entries. CONFIRMED and filable: 001, 003, 004, 006, 007, 008, 009, 014, 015, 017, 020, 021(case), 023, 024, 026, 028, 031, 032, 034 (19). Security-angle set aside: 005, 010, 022, 029, 030. UNCLEAR: 002, 012, 013, 016, 018, 019, 025, 027, 033, 035. DOCS: 011.

## httpx
**Filing constraint:** encode/httpx closed issues and discussions (Discussion #3784, maintainer, 2026-02-27) and per a Sept 2026 comment PRs are limited to collaborators. Upstream filing is not possible. The active fork is pydantic/httpx2 (several findings already have httpx2 issues/PRs: #1234, #1236, #1165). Confirmation paused after 001-010 pending Andrew's call.
- 001 URL password in INFO log / HTTPStatusError / Request repr: DUP (discussion #2765; PR #3513 closed unmerged), SECURITY-ANGLE
- 002 multi-member gzip truncated to first member: NOT-A-BUG (declined: #3269, PR #3270 "follow Chrome/Safari")
- 003 zstd in a Content-Encoding chain always fails: DUP (#3538, open PR #3697); empty-body chain remainder unreported
- 004 truncated gzip/deflate/br bodies accepted silently: CONFIRMED upstream-unreported (same fix open in httpx2 PR #1234)
- 005: withdrawn by QPB itself (302 method rewrite; intentional, requests-compatible) -> NOT-A-BUG
- 006 POST->GET redirect keeps Content-Type/Encoding/Language: CONFIRMED (RFC 9110 §15.4 SHOULD; code comment says it strips body headers)
- 007 base_url with query string puts path into query: DUP (#3614, open PR #3766; httpx2 #1236)
- 008 content= file-like: Content-Length ignores offset; pipe gets 0: CONFIRMED (multipart sibling fixed in #2065)
- 009 mixed-case multipart Content-Type -> body boundary differs from header: CONFIRMED (RFC 9110 §8.3.1)
- 010 NO_PROXY CIDR matches only the network address: DUP (#2828, #3224, #2737)
- 011-042: NOT CONFIRMED (paused)

## cobra
Note: many cobra bugs already have open, unmerged PRs; the maintainers merge slowly.
- 001 shorthand cluster -vf x sub routes x as a command: DUP (#2188; PRs #2189, #2510)
- 002 TraverseChildren: token after -- eaten as a flag value, next token routed as command: CONFIRMED (narrower than reported)
- 003 prefix matching ignores EnableCaseInsensitive: UNCLEAR leaning CONFIRMED (PR #1802 intent)
- 004 mistyped nested subcommand prints help, exits 0: DUP (#706, #1156; open PR #2500)
- 005 SuggestionsFor lists a command twice: DUP (open PR #2462); default-distance half UNCLEAR
- 006 user guide says nil Args = ArbitraryArgs; root with subcommands rejects args: DOCS (legacyArgs intended and tested; #2247 user hit it)
- 007 OnlyValidArgs rejects ArgAliases: UNCLEAR (godoc says accepted; user guide says ValidArgs only)
- 008 OnlyValidArgs suggestion computed from args[0]: DUP (open PRs #2489, #2460)
- 009 flag groups + normalize func: DUP (open PR #2502)
- 010 Version + non-bool user --version flag errors every run: UNCLEAR (error message suggests deliberate)
- 011 failing subcommand's error/usage go to root's writers, not sub's SetErr/SetOut: CONFIRMED (lookup-error path already uses sub's writers)
- 012 UsageString os.Exit(1)s when usage func errors; Execute never returns RunE error: CONFIRMED (CheckErr inside library)
- 013 defaultVersionFunc prints leading space for empty name; template doesn't: CONFIRMED (code comment: "must change in sync")
- 014 defaultHelpFunc vs defaultHelpTemplate differ for whitespace-only Long: CONFIRMED (same "in sync" comment)
- 015 --version usage ignores display name for empty Use: DUP (PR #2455 self-closed)
- 016 completion drops flag-looking positional after -- / non-interspersed: CONFIRMED (doc: args "as it would have done when calling RunE")
- 017 default completion command writes to the writer captured at first creation: UNCLEAR leaning CONFIRMED (__complete resolves at run time)
- 018 PowerShell: -o=<TAB> shorthand gives nothing (`--*=*` pattern): CONFIRMED (tested in real pwsh 7.4.6; bash/zsh/fish match -*=)
- 019 legacy bash script broken for program names with ':': CONFIRMED (V1 legacy; maintainers may say use V2)
- 020 legacy bash completion dead with CommandDisplayNameAnnotation: CONFIRMED (user guide says annotation fixes completions)
- 021 legacy bash must_have_one_flag omits inherited required flags; '=' on NoOptDefVal flags: CONFIRMED (V1 legacy)
- 022 GenBashCompletion sorts Aliases/ValidArgs/ArgAliases in place: UNCLEAR leaning CONFIRMED (visible in help and __complete)
- 023 man header keeps auto-gen tag when root disables it: DUP (#1346, open PR #1347)
- 024 GenManTreeFromOpts writes root_sub.1 but SEE ALSO says root-sub(1): DUP (#342 half-fixed in 2016)
- 025 YAML docs list hidden/deprecated flags: DUP (#1663, open PR #2503)
- 026 GenYamlCustom never calls linkHandler: UNCLEAR (docs copied from markdown; needs format decision)
- 027 doc generators write parent's DisableAutoGenTag onto child: UNCLEAR (hygiene; no no-mutation contract)
- 028 __complete ignores CompletionOptions.DisableDescriptions: UNCLEAR (option scoped to the completion command)
- 029 second ExecuteContext leaves subcommand with first (cancelled) ctx: DUP (#1109, #1469, #2193)
- 030 Levenshtein suggestion counts bytes, not runes: CONFIRMED
- 031 empty required-flag annotation panics Execute: UNCLEAR (misuse of internal annotation; one-line guard)
- 032 ParseFlags re-prints accumulated flag warnings (1,2,3...): CONFIRMED (beforeErrorBufLen exists for exactly this)
- 033 deprecation warnings written into __complete stdout when SetOut is set: DUP-partial (#1708 root cause; completion angle new)
- 034 completion after -ofile treats 'e' as flag awaiting value: CONFIRMED (related to open #1629)
- 035 doc generators sort cmd.Commands() in place, breaking EnableCommandSorting=false: CONFIRMED
- 036 GenMan writes defaults into caller's GenManHeader: UNCLEAR leaning CONFIRMED (tree path copies; test enforces it)
- 037 completion treats required annotation "false" as required: CONFIRMED (internal convention per #1330)
- 038 help <TAB> omits additional help topics: UNCLEAR
- 039 md/rst dates ignore SOURCE_DATE_EPOCH (man honours it): UNCLEAR (DisableAutoGenTag is documented route)
- 040 help <unknown> exits 0; CheckErr os.Exits inside Execute: UNCLEAR (os.Exit half stronger)
- 041 __complete permanently marks flag-group flags required/hidden: NOT-A-BUG (#2315 maintainer: intended)
- 042 completion ignores EnableCaseInsensitive: UNCLEAR (prefix matching is case-sensitive too; shells filter anyway)

cobra totals (42): CONFIRMED 19 (002, 011, 012, 013, 014, 016, 018, 019, 020, 021, 030, 032, 034, 035, 037 + leaning 003, 017, 022, 036); DUP 11 (001, 004, 005, 008, 009, 015, 023, 024, 025, 029, 033-partial); UNCLEAR 10 (007, 010, 026, 027, 028, 031, 038, 039, 040, 042); NOT-A-BUG 1 (041); DOCS 1 (006).

## Wave 2 selection round (2026-09-30)

Selectors (brief: /tmp/sel/SELECTOR-BRIEF.md) shortlisted requirement-anchored bugs per repo; confirmers followed CONFIRMER-BRIEF-wave2.md. Repros in /tmp/<repo>v/<bug-id>/ (sandbox).

| Repo | Bug | Requirement anchor | Verdict | Picked |
|---|---|---|---|---|
| pydantic | BUG-033 TypedDict own ser_json_* config ignored | docs_concepts_config.md:98-99, 232-233 | CONFIRMED | yes |
| pydantic | BUG-006 float multiple_of accepts inf/NaN | JSON Schema validation :177; Python fallback rejects inf | CONFIRMED (inf/NaN part) | yes |
| pydantic | BUG-005 Decimal multiple_of rounds at 28 digits | JSON Schema validation :177 | CONFIRMED | spare |
| setuptools | BUG-024 MANIFEST.in include `**` not recursive | userguide_miscellaneous.rst:113-114 | CONFIRMED (expected set corrected: depth-2 file required) | yes |
| setuptools | BUG-004+020 readme/requires-python not in dynamic crash | pep-0621.rst:449-451; #4183 maintainer: warn and ignore | CONFIRMED | yes |
| setuptools | BUG-025 build_editable ignores .dist-info metadata_directory | pep-0660.rst:118-121 | CONFIRMED | spare |
| addressable | BUG-032 {+v}/{#v} double-encode %XX | RFC 6570 §3.2.1 :1080-1087 | CONFIRMED | yes |
| addressable | BUG-011 route_from '' when only base has query | RFC 3986 §5.2.2; maintainer round-trip rule in #126 | CONFIRMED | yes |
| addressable | BUG-035 host lowercased before pct-decode | RFC 3986 §6.2.2.1-2 | CONFIRMED (LOW; denylist angle) | spare |
| javalin | BUG-011 precompressMaxSize=0 disables | javalin.io docs :1566 (live page same) | CONFIRMED (chunked symptom not reproduced) | yes |
| javalin | BUG-025 lowercase redirect drops contextPath | docs :1762 + :1508 | CONFIRMED | yes |
| javalin | BUG-031 endpoint ws.onUpgrade never called | docs :555-563 | UNCLEAR (onUpgrade designed for request logger, #2220/#2450) | no |
| cobra | BUG-016 completion drops flag-like positional after `--` | completions__index.md:238 | CONFIRMED (earlier) | yes |
| cobra | BUG-030 suggestion distance counts bytes | user_guide.md:791 | CONFIRMED (earlier) | yes |
