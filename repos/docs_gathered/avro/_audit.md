# Audit — avro at pinned SHA

## Sources consulted (whitelist verification)

In-repo sources at the pinned commit:

- `/tmp/gather_avro/README.md`
- `/tmp/gather_avro/BUILD.md`
- `/tmp/gather_avro/doc/content/en/docs/++version++/_index.md`
- `/tmp/gather_avro/doc/content/en/docs/++version++/Specification/_index.md`
- `/tmp/gather_avro/doc/content/en/docs/++version++/IDL Language/_index.md`
- `/tmp/gather_avro/doc/content/en/docs/++version++/SASL profile/_index.md`
- `/tmp/gather_avro/doc/content/en/docs/++version++/Getting started (Java)/_index.md`
- `/tmp/gather_avro/lang/java/avro/src/main/java/org/apache/avro/Schema.java` (header doc + class-level comments)
- `/tmp/gather_avro/lang/java/avro/src/main/java/org/apache/avro/Protocol.java` (header doc + class-level comments)
- `/tmp/gather_avro/lang/java/avro/src/main/java/org/apache/avro/SchemaCompatibility.java` (header doc + entry-point doc)
- `/tmp/gather_avro/lang/java/avro/src/main/java/org/apache/avro/io/Decoder.java` (class-level doc)
- `/tmp/gather_avro/lang/java/avro/src/main/java/org/apache/avro/io/EncoderFactory.java` (class-level doc)
- `/tmp/gather_avro/lang/java/avro/src/main/java/org/apache/avro/io/DecoderFactory.java` (class-level doc)
- `/tmp/gather_avro/lang/java/avro/src/main/java/org/apache/avro/file/DataFileWriter.java` (header + class doc)
- `/tmp/gather_avro/lang/java/avro/src/main/java/org/apache/avro/file/CodecFactory.java` (class-level doc)
- `/tmp/gather_avro/lang/java/avro/src/main/java/org/apache/avro/specific/SpecificData.java` (header)
- `/tmp/gather_avro/lang/java/ipc/src/main/java/org/apache/avro/ipc/Transceiver.java` (class-level doc)
- Package listings under
  `/tmp/gather_avro/lang/java/avro/src/main/java/org/apache/avro/{,data,file,generic,io,message,reflect,specific}/`
- Package listing under `/tmp/gather_avro/lang/java/ipc/src/main/java/org/apache/avro/ipc/`
- Listings under `/tmp/gather_avro/lang/java/{mapred,tools,maven-plugin}/`
- `/tmp/gather_avro/lang/py/README.md`
- Listing of `/tmp/gather_avro/lang/py/avro/` and headers of `schema.py`, `io.py`, `codecs.py`, `datafile.py`
- Listings of `/tmp/gather_avro/lang/c/src/`,
  `/tmp/gather_avro/lang/c++/include/avro/`, `/tmp/gather_avro/lang/c++/MainPage.dox`
- Listing of `/tmp/gather_avro/lang/csharp/` and `/tmp/gather_avro/lang/csharp/src/apache/main/`

No external URLs were fetched; the in-tree spec and source were
sufficient.

## Sources explicitly NOT consulted (blacklist verification)

- GitHub Security tab: NOT READ
- GitHub Issues: NOT READ
- GitHub PRs: NOT READ
- Commits later than the pinned SHA: NOT READ
- CHANGELOG security entries: not consulted at all (no `CHANGELOG.md`
  was opened during gathering; the per-language `ChangeLog` files in
  `lang/c/` and `lang/c++/` were not read)
- 3rd-party CVE databases: NOT READ
- `docs_gathered.contaminated/` tree: NOT ACCESSED (explicit
  per-task forbidden path)
- Stack Overflow / blog posts / external commentary: NOT READ
- Wayback Machine: not needed

## Self-check verdict

- Forbidden vocabulary scan: PASS — `grep -iE` for the full
  forbidden-vocabulary list (vulnerab|advisor|exploit|patched|patching|
  disclosed|disclosure|embargoed|security fix|security patch|security
  issue|known issue|known bug|known flaw|hardened|tightened|
  strengthened|fortified|footgun|gotcha|watch out|be careful|CVE-|
  GHSA-|CWE-|hotfix|backport|breaking change|rewritten|rebuilt|
  high-churn|audit|audited|coordinated disclosure|responsible
  disclosure) returned zero matches across all eight files.
- Equal subsystem depth check: PASS. Word counts per file are 479
  (overview), 566 (schema model), 575 (binary and JSON encoding), 475
  (object container files), 598 (schema resolution), 640 (RPC
  protocols), 527 (language implementations), 558 (logical types).
  Total ~4418 words, ~552 per file with a spread of 475 – 640. No
  file is structurally elevated above the others.
- Fix-narrative scan: PASS — `grep -niE` for "fixed in v|since v[0-9]|
  before v[0-9]|after v[0-9]|until v[0-9]|prior to v[0-9]|was added
  in|was added because" returned zero matches. Occurrences of the
  word "fixed" are all references to the Avro `fixed` type or the
  generic phrase "fixed in advance".
- Code-quote check: PASS. Quoted code is limited to (a) schema
  fragments from the public specification (`{"type": "record", ...}`
  examples) and (b) names of public types, factory methods, and
  packages. No function bodies were quoted.

## Gatherer

- subagent / cowork instance
- date: 2026-06-02

## Notes

- The pinned commit's documentation tree uses Hugo placeholders such
  as `++version++` in the doc paths. Those are paths-as-stored at the
  pinned SHA, not version strings I am asserting in the corpus.
- Word budget came in slightly above the 3500 target (≈4418). I
  preferred even depth across eight subsystems over compressing any
  one of them below the others; this seemed truer to the equal-depth
  constraint than dropping content from one file to hit the budget.
- Implementation coverage: Java, Python, C++, and C# were chosen for
  the language-implementation file. The C, JavaScript, Perl, PHP, and
  Ruby implementations are acknowledged in `overview.md` and at the
  end of `language_implementations.md` but not described
  field-by-field; the Rust implementation was noted as having moved
  to a companion repository, per the in-repo README at the pinned SHA.
