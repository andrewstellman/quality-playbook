`sendComment()` splits a comment on `\n` only, so a `\r` inside it ends the comment line for an SSE client and the rest is read as a new field: `sendComment("hello\rdata: forged")` makes the browser dispatch a `data: forged` message. The SSE spec treats CR, LF and CRLF as line terminators, and event names and ids already have them stripped (#2579).

Comments are now split on `\r\n`, `\r` or `\n`, so every line gets the `:` prefix. Comments without `\r` are unchanged. The test in `TestSse` sends a comment containing `\r` and expects no `data:` line.

Found with the Quality Playbook, an AI code-review tool I maintain; I reproduced it and reviewed the fix myself.
