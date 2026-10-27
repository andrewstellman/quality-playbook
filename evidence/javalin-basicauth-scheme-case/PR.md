`basicAuthCredentials()` only recognises the scheme spelled exactly `Basic `, but RFC 9110 section 11.1 makes scheme names case-insensitive, so a client sending `Authorization: basic <token>` gets a 401 from `enableBasicAuth`. The scheme is now matched case-insensitively. The test in `TestRequest` sends `basic <token>` and expects a 200.

Found with the Quality Playbook, an AI code-review tool I maintain; I reproduced it and reviewed the fix myself.
