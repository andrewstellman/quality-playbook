Confirmer: CONFIRMED, no upstream duplicate. Repro /tmp/cobrav/BUG-030/ (`app ubr` doesn't suggest `über`; after fix it does).
Doc: site/content/user_guide.md:791 — suggestions "use an implementation of Levenshtein distance. Every registered command that matches a minimum distance of 2 (ignoring case) will be displayed as a suggestion."
Fixer notes: same as QPB's patch; params renamed sStr/tStr and converted to []rune after lowercasing.
