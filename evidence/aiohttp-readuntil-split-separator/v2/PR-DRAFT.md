## What do these changes do?

`StreamReader.readuntil()` searched each buffered chunk on its own, so a multi-byte separator whose bytes arrived in different chunks was missed. Feeding `b"line1\r"` then `b"\nline2"` made `readuntil(b"\r\n")` return `b"line1\r\nline2"`. This also checks the last `len(separator) - 1` bytes already read against the start of the next chunk.

## Are there changes in behavior for the user?

`readuntil()` now stops at the first separator however the data was chunked. One visible change: a line that exactly fits `max_size` but whose separator is split across chunks is now returned instead of raising `LineTooLong`, because the bytes read past the missed separator are no longer counted. `readline()` and other one-byte separators take the old path.

## Is it a substantial burden for the maintainers to support this?

No. The change is local to the `readuntil()` loop, with tests in `tests/test_streams.py`.

## Related issue number

None found. #6701/#6810 fixed a different multi-byte separator bug.

## Checklist

- [x] I think the code is well written
- [x] Unit tests for the changes exist
- [ ] Documentation reflects the changes: N/A, no API change
- [x] If you provide code modification, please add yourself to `CONTRIBUTORS.txt`
- [x] Add a new news fragment into the `CHANGES/` folder

<details>
<summary>Test output</summary>

Pure-Python mode (`AIOHTTP_NO_EXTENSIONS=1`), Python 3.10.12, on e11d2836.

```
new tests without the fix:  14 failed, 10 passed (the 10 are controls that pass either way)
new tests with the fix:     24 passed
tests/test_streams.py:      160 passed
```

</details>

Drafted with Claude Opus 5.5; reviewed by andrewstellman.
