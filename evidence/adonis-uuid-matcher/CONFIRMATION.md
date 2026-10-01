BUG-001: router.matchers.uuid() accepts non-hex letters g-z. CONFIRMED.
Claim: src/router/matchers.ts uuid() regex uses character class [0-9a-zA-F] (typo for [0-9a-fA-F]); so 'zzzzzzzz-zzzz-zzzz-zzzz-zzzzzzzzzzzz' matches and /posts/gggggggg-gggg-gggg-gggg-gggggggggggg reaches a uuid-guarded route.
Evidence: v6-docs_basics_routing.md "Inbuilt matchers": "// Validate id to be a valid UUID". Introduced by PR adonisjs/http-server#53 "fix: support UUIDs as per RFC spec (#50)" (2022), which meant to add lowercase a-f. tests/router/matchers.spec.ts:26-35 only tests real UUIDs and 'hello-world'. No duplicate (closest: http-server #50, #53; core #3385, #3522 are about lowercase being rejected).
Pushback: severity LOW; fix must stay [0-9a-fA-F] only (no version-digit checks).
