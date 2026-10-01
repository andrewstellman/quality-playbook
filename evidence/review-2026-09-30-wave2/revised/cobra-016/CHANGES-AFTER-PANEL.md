# cobra-016: changes after panel
1. Extra slice-flag duplicate: done. Stop detection now reads the `--` probe's last arg (kept as "--" only when parsing had stopped) and restores the args before the existing real ParseFlags; no third parse. `--tags a -- --out ''`: base tags=[a a], previous fix [a a a], now [a a].
2. toComplete change for `--out=x` after `--`: done (disclosed in PR text). Not tested (not asked).
3. Fold new block into the one above / duplicated error return: done; one ParseFlags error return, as on base.
4. Mention open PR #2259: done.
5. Doc quote joining two sentences: done; quotes the first sentence of the note only.
Also: the copy comment now says why the copy is needed (checkIfFlagCompletion's shortened slice + the probe's append), since the line was touched anyway (S1/S3).
