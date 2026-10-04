# GPT standard-review control scoring (2026-10-04)

This scores the nine specified behaviors against the **existing** 140 Sol/Terra standard-review reports at `docs/research/control-2026-09-27/results/`. Each target has ten reports per model at the pinned commits and scopes in [SCOPES](../control-2026-09-27/SCOPES.md). The report text, not a grep hit, determines the result: a **hit** explicitly reports the same failure as a finding. Mentioning a file, suggesting a related fix, or finding a different bug in the same function is a miss. I read the matching passages and all reported-finding headings, including no-match reports, for paraphrases. This scoring was **not blind**: the nine targets were known to the scorer. The run-level decisions, citations, and source SHA-256 values are in [controls.json](controls.json).

| Target | Sol hits | Terra hits |
|---|---:|---:|
| aiohttp readuntil split multi-byte separator | 0/10 | 2/10 |
| chi GetHead under mounted subrouter ignores explicit HEAD | 0/10 | 0/10 |
| Express subsecond cookie maxAge | 0/10 | 0/10 |
| OpenTelemetry UrlParser bracketed IPv6 | 10/10 | 9/10 |
| OpenTelemetry ForwardedHost bracketed IPv6 | 10/10 | 9/10 |
| AssertJ Percentage.toString overflow | 10/10 | 8/10 |
| calibre OPDS navcatalog malformed hex yields 500 | 0/10 | 0/10 |
| BioNeMo AMPLIFY _pad_weights dtype/device | 6/10 | 9/10 |
| BioNeMo THD CP remainder tokens | 0/10 | 2/10 |

Each linked run below is a reported hit; the link points to the relevant finding line in the original review. All unlisted runs for that target/model are misses. There are no uncertain cells.

### aiohttp readuntil split multi-byte separator

- **sol:** none.
- **terra:** [run 06](../control-2026-09-27/results/terra-aiohttp-run06.md#L13), [run 08](../control-2026-09-27/results/terra-aiohttp-run08.md#L13).

### chi GetHead under mounted subrouter ignores explicit HEAD

- **sol:** none.
- **terra:** none.

### Express subsecond cookie maxAge

- **sol:** none.
- **terra:** none.

### OpenTelemetry UrlParser bracketed IPv6

- **sol:** [run 01](../control-2026-09-27/results/sol-otel-run01.md#L17), [run 02](../control-2026-09-27/results/sol-otel-run02.md#L19), [run 03](../control-2026-09-27/results/sol-otel-run03.md#L15), [run 04](../control-2026-09-27/results/sol-otel-run04.md#L17), [run 05](../control-2026-09-27/results/sol-otel-run05.md#L19), [run 06](../control-2026-09-27/results/sol-otel-run06.md#L13), [run 07](../control-2026-09-27/results/sol-otel-run07.md#L17), [run 08](../control-2026-09-27/results/sol-otel-run08.md#L15), [run 09](../control-2026-09-27/results/sol-otel-run09.md#L17), [run 10](../control-2026-09-27/results/sol-otel-run10.md#L17).
- **terra:** [run 01](../control-2026-09-27/results/terra-otel-run01.md#L29), [run 02](../control-2026-09-27/results/terra-otel-run02.md#L15), [run 04](../control-2026-09-27/results/terra-otel-run04.md#L31), [run 05](../control-2026-09-27/results/terra-otel-run05.md#L37), [run 06](../control-2026-09-27/results/terra-otel-run06.md#L38), [run 07](../control-2026-09-27/results/terra-otel-run07.md#L13), [run 08](../control-2026-09-27/results/terra-otel-run08.md#L23), [run 09](../control-2026-09-27/results/terra-otel-run09.md#L31), [run 10](../control-2026-09-27/results/terra-otel-run10.md#L37).

### OpenTelemetry ForwardedHost bracketed IPv6

- **sol:** [run 01](../control-2026-09-27/results/sol-otel-run01.md#L13), [run 02](../control-2026-09-27/results/sol-otel-run02.md#L15), [run 03](../control-2026-09-27/results/sol-otel-run03.md#L13), [run 04](../control-2026-09-27/results/sol-otel-run04.md#L13), [run 05](../control-2026-09-27/results/sol-otel-run05.md#L13), [run 06](../control-2026-09-27/results/sol-otel-run06.md#L17), [run 07](../control-2026-09-27/results/sol-otel-run07.md#L19), [run 08](../control-2026-09-27/results/sol-otel-run08.md#L19), [run 09](../control-2026-09-27/results/sol-otel-run09.md#L19), [run 10](../control-2026-09-27/results/sol-otel-run10.md#L15).
- **terra:** [run 01](../control-2026-09-27/results/terra-otel-run01.md#L21), [run 02](../control-2026-09-27/results/terra-otel-run02.md#L33), [run 03](../control-2026-09-27/results/terra-otel-run03.md#L41), [run 04](../control-2026-09-27/results/terra-otel-run04.md#L15), [run 05](../control-2026-09-27/results/terra-otel-run05.md#L29), [run 06](../control-2026-09-27/results/terra-otel-run06.md#L53), [run 07](../control-2026-09-27/results/terra-otel-run07.md#L31), [run 09](../control-2026-09-27/results/terra-otel-run09.md#L23), [run 10](../control-2026-09-27/results/terra-otel-run10.md#L29).

### AssertJ Percentage.toString overflow

- **sol:** [run 01](../control-2026-09-27/results/sol-assertj-run01.md#L23), [run 02](../control-2026-09-27/results/sol-assertj-run02.md#L21), [run 03](../control-2026-09-27/results/sol-assertj-run03.md#L23), [run 04](../control-2026-09-27/results/sol-assertj-run04.md#L24), [run 05](../control-2026-09-27/results/sol-assertj-run05.md#L23), [run 06](../control-2026-09-27/results/sol-assertj-run06.md#L22), [run 07](../control-2026-09-27/results/sol-assertj-run07.md#L21), [run 08](../control-2026-09-27/results/sol-assertj-run08.md#L24), [run 09](../control-2026-09-27/results/sol-assertj-run09.md#L19), [run 10](../control-2026-09-27/results/sol-assertj-run10.md#L21).
- **terra:** [run 01](../control-2026-09-27/results/terra-assertj-run01.md#L31), [run 02](../control-2026-09-27/results/terra-assertj-run02.md#L31), [run 03](../control-2026-09-27/results/terra-assertj-run03.md#L37), [run 04](../control-2026-09-27/results/terra-assertj-run04.md#L32), [run 06](../control-2026-09-27/results/terra-assertj-run06.md#L37), [run 07](../control-2026-09-27/results/terra-assertj-run07.md#L27), [run 08](../control-2026-09-27/results/terra-assertj-run08.md#L37), [run 09](../control-2026-09-27/results/terra-assertj-run09.md#L29).

### calibre OPDS navcatalog malformed hex yields 500

- **sol:** none.
- **terra:** none.

### BioNeMo AMPLIFY _pad_weights dtype/device

- **sol:** [run 01](../control-2026-09-27/results/sol-bionemo-run01.md#L21), [run 02](../control-2026-09-27/results/sol-bionemo-run02.md#L17), [run 04](../control-2026-09-27/results/sol-bionemo-run04.md#L17), [run 06](../control-2026-09-27/results/sol-bionemo-run06.md#L15), [run 07](../control-2026-09-27/results/sol-bionemo-run07.md#L19), [run 09](../control-2026-09-27/results/sol-bionemo-run09.md#L19).
- **terra:** [run 02](../control-2026-09-27/results/terra-bionemo-run02.md#L31), [run 03](../control-2026-09-27/results/terra-bionemo-run03.md#L33), [run 04](../control-2026-09-27/results/terra-bionemo-run04.md#L29), [run 05](../control-2026-09-27/results/terra-bionemo-run05.md#L13), [run 06](../control-2026-09-27/results/terra-bionemo-run06.md#L39), [run 07](../control-2026-09-27/results/terra-bionemo-run07.md#L23), [run 08](../control-2026-09-27/results/terra-bionemo-run08.md#L23), [run 09](../control-2026-09-27/results/terra-bionemo-run09.md#L76), [run 10](../control-2026-09-27/results/terra-bionemo-run10.md#L31).

### BioNeMo THD CP remainder tokens

- **sol:** none.
- **terra:** [run 05](../control-2026-09-27/results/terra-bionemo-run05.md#L37), [run 06](../control-2026-09-27/results/terra-bionemo-run06.md#L15).

The [Terra OpenTelemetry run 08](../control-2026-09-27/results/terra-otel-run08.md#L21) comma-list finding suggests bracketed IPv6 handling as an ancillary fix. It does not report the ForwardedHost IPv6 failure, so that target/run is a miss and is separately recorded as considered but not reported. The [Terra aiohttp run 03](../control-2026-09-27/results/terra-aiohttp-run03.md#L13) finding concerns `EmptyStreamReader.readuntil()` crashing; it is distinct from a separator split across chunks. BioNeMo reports about token-dropout offset or padding errors are distinct from the THD context-parallel remainder-token loss and were scored as misses for that target.

These counts measure only reported matches to the nine selected targets; they do not independently verify control findings, estimate overall bug recall, or establish a matched-model comparison with historical QPB runs. The [Claude scoring note](../control-2026-09-27/results/CLAUDE-SCORING.md) uses the same reported-finding rule for a separate arm and itself says that historical QPB models are unmatched. The Express subsecond-cookie candidate was dropped in the broader evidence assessment, and the chi GetHead patch regressed; finding or missing those descriptions in a control report would not restore their technical validity. No source, tests, network, or historical evidence records were changed for this tally.
