# Disclosure / duplicate search (2026-09-27, via web_fetch)

calibre README.md: "Bug reports and feature requests should be made in the calibre bug tracker at Launchpad. GitHub is only used for code hosting and pull requests." So GitHub search covers PRs; Launchpad covers bugs.

## GitHub (api.github.com/search/issues, lexical)
| Query | Hits | Relevant |
|---|---|---|
| `repo:kovidgoyal/calibre navcatalog` | 0 | - |
| `repo:kovidgoyal/calibre opds hex` | 0 | - |
| `repo:kovidgoyal/calibre opds crash` | 0 | - |
| `repo:kovidgoyal/calibre opds 500` | 2 (#500 recipe update, #741 vl search) | No |
| `repo:kovidgoyal/calibre from_hex_unicode` | 1 (#2903 "Polyglot cleanup", merged 2025-11-19) | No (refactor, lists from_hex_unicode as retained) |
| `repo:kovidgoyal/calibre opds is:pr created:>2026-01-01` | 1 (#3213 content server plugins, merged 2026-07-09) | No |
| `repo:kovidgoyal/calibre 3101 normpath` | 1 (#3101) | Context: sibling BUG-001/002 fix, merged 2026-04-21 |

## Launchpad (api.launchpad.net/1.0/calibre?ws.op=searchTasks)
| Query | Hits | Relevant |
|---|---|---|
| `navcatalog` (default = open statuses) | 0 | - |
| `navcatalog`, status=Fix Released | 1: #1947879 "IOS client access, the library does not display content." (2021) | No: traceback is lxml SerialisationError in html_to_lxml on a *valid* navcatalog id |
| `opds 500` (open) | 0 | - |
| `opds hex` (open) | 0 | - |
| `opds error`, status=Fix Released | 3: #1621642 "OPDS 500 internal server error" (2016), #1932992 "OPDS 'up' navigation issue" (2021), #2126611 (FTS threading) | No: #1621642 is a 500 on a valid /opds/category id in calibre 2.67 (CherryPy era); others unrelated |

Limitation: web_fetch collapses repeated `status=` params, so each Launchpad query covered either the default open statuses or one closed status; Invalid / Won't Fix / Expired were not searched. Lexical search can miss paraphrased reports.

No report or PR for malformed-hex / empty ids in OPDS handlers was found.
