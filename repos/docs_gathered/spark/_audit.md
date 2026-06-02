# Audit — spark at 7f9ca1b37e140303af0d70e2895d19314f812661

## Sources consulted (whitelist verification)

In-repo files at the pinned commit:

- /tmp/gather_spark/README.md
- /tmp/gather_spark/docs/cluster-overview.md
- /tmp/gather_spark/docs/rdd-programming-guide.md
- /tmp/gather_spark/docs/spark-connect-overview.md
- /tmp/gather_spark/docs/monitoring.md
- /tmp/gather_spark/docs/configuration.md
- /tmp/gather_spark/docs/sql-programming-guide.md (header only — content was a redirect)
- /tmp/gather_spark/docs/structured-streaming-programming-guide.md (header only — content was a redirect)
- /tmp/gather_spark/docs/ml-guide.md (header only)
- /tmp/gather_spark/sql/README.md
- /tmp/gather_spark/sql/connect/README.md
- /tmp/gather_spark/core/src/main/scala/org/apache/spark/SparkContext.scala (header / imports)
- /tmp/gather_spark/core/src/main/scala/org/apache/spark/rdd/RDD.scala (class docstring + header)
- /tmp/gather_spark/core/src/main/scala/org/apache/spark/scheduler/DAGScheduler.scala (class docstring + header)
- /tmp/gather_spark/core/src/main/scala/org/apache/spark/storage/BlockManager.scala (header only)
- /tmp/gather_spark/core/src/main/scala/org/apache/spark/shuffle/ShuffleManager.scala (class docstring + header)
- /tmp/gather_spark/sql/catalyst/src/main/scala/org/apache/spark/sql/catalyst/trees/TreeNode.scala (header)
- /tmp/gather_spark/sql/catalyst/src/main/scala/org/apache/spark/sql/catalyst/analysis/Analyzer.scala (header)
- /tmp/gather_spark/sql/catalyst/src/main/scala/org/apache/spark/sql/catalyst/plans/logical/LogicalPlan.scala (class signature)
- /tmp/gather_spark/sql/core/src/main/scala/org/apache/spark/sql/execution/SparkPlan.scala (header)
- /tmp/gather_spark/sql/core/src/main/scala/org/apache/spark/sql/execution/streaming/StreamExecution.scala (header)
- /tmp/gather_spark/mllib/src/main/scala/org/apache/spark/ml/Pipeline.scala (class docstring + header)
- /tmp/gather_spark/graphx/src/main/scala/org/apache/spark/graphx/Graph.scala (class docstring + header)
- Directory listings under: core/src/main/scala/org/apache/spark/, core/src/main/scala/org/apache/spark/scheduler/, core/src/main/scala/org/apache/spark/rdd/, core/src/main/scala/org/apache/spark/deploy/, core/src/main/scala/org/apache/spark/storage/, sql/, sql/catalyst/src/main/scala/org/apache/spark/sql/catalyst/, sql/core/src/main/scala/org/apache/spark/sql/, sql/core/src/main/scala/org/apache/spark/sql/execution/streaming/, sql/connect/, streaming/src/main/scala/org/apache/spark/streaming/, mllib/src/main/scala/org/apache/spark/ml/, connector/, resource-managers/, python/pyspark/.
- /tmp/gather_spark/streaming/src/main/scala/org/apache/spark/streaming/StreamingContext.scala (header)
- /tmp/gather_spark/python/pyspark/sql/connect/__init__.py (module docstring)

External documentation: none consulted. The in-repo `docs/` tree was sufficient; no Wayback Machine fetches were needed.

## Sources explicitly NOT consulted (blacklist verification)

- GitHub Security tab: NOT READ
- GitHub Issues: NOT READ
- GitHub PRs: NOT READ
- Commits later than the pinned SHA: NOT READ
- CHANGELOG entries: not consulted at all (none read; nothing to filter)
- 3rd-party CVE databases (NVD, CVE.org, NIST, Snyk, Wiz, etc.): NOT READ
- Stack Overflow / Reddit / blog posts / conference talks: NOT READ
- The forbidden `/Users/andrewstellman/Documents/QPB/repos/docs_gathered.contaminated/` tree: NOT READ
- The training-data CVE knowledge for Spark was not surfaced or used.

## Self-check verdict

- **Forbidden vocabulary scan**: PASS. Grep over the output directory for the full forbidden-word list (vulnerab, advisor, exploit, patched, disclos, embargo, known-issue/-bug/-flaw, hardened, tightened, strengthened, fortified, footgun, gotcha, watch-out, hotfix, backport, audit, coordinated, responsible-disclosure, CVE-/GHSA-/CWE-/PYSEC-, security-fix/-patch/-issue/-release/-tab, attack-surface, high-churn, rewritten, rebuilt, subtle, tricky, easy-to-get-wrong, "fixed in v", "since v", "before v", "after v", "until v", "prior to v") returned no matches.
- **Equal subsystem depth check**: PASS. Eight files covering architecture-overview, core-RDD-model, scheduler, SQL-engine, structured-streaming, Spark-Connect, MLlib, and configuration-and-deployment. Word counts per file currently range ~610-732, all within ~20% of each other. No file is a deep-dive while others are paragraphs.
- **Fix-narrative scan**: PASS. No "fixed in v", "since v", "before v", "added because of", "rewritten to handle" framing appears.
- **Code-quote check**: PASS. Quoted material is limited to class names, method/trait signatures, package paths, configuration property names, protobuf RPC names, and one minimal `SparkConf`-builder example showing public API surface. No function bodies are quoted; no pre/post comparisons exist.

## Gatherer

- subagent (Claude Opus 4.7, 1M context) acting under Cowork session
- date: 2026-06-02

## Notes

- The repo is large enough that a handful of plausible subsystems were deliberately not given top-level files of their own: GraphX, the legacy DStream-based streaming module, the storage/shuffle subsystem (BlockManager, ShuffleManager), the connector ecosystem, and PySpark internals. These are mentioned briefly inside other files (e.g., GraphX and DStream-streaming in the module layout; BlockManager inside the RDD persistence section). The choice of eight subsystems was driven by the "roughly equal real-world importance" rule: SQL, RDD model, scheduler, structured streaming, MLlib, Spark Connect, configuration/deployment, and the high-level architecture chapter were judged comparable as onboarding topics for a new contributor.
- Word budget is modestly above the ~4000 target (~5350 across the 8 subsystem files plus a 196-word MANIFEST). The procedure note says "~", and the equal-depth constraint was prioritized over hitting the exact total.
- The repo was cloned at depth 5000, then `git fetch --depth 20000 origin <SHA>` was used to bring the pinned commit into reach before checkout.
