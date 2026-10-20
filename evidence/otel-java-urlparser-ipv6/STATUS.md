status: merged
title: otel-java: UrlParser records server.address "[" for bracketed IPv6
link: https://github.com/open-telemetry/opentelemetry-java-instrumentation/pull/20320
updated: 2026-10-16
note: Merged as 966f903a (2026-10-16 16:36 UTC, squash, by Trask Stalnaker; "Co-authored-by: Lauri Tulmin"). Before merging, laurit merged main into the branch (5a3ed77), dropping the edits to reactor-netty's duplicate UrlParser, which #20603 had deleted; reactor-netty now uses the shared UrlParser. The merged diff (3 files, +44 -1) is identical by patch-id to Andrew's commit 4e0cc52 on those files. Checked with git against the live repository on 2026-10-16.
