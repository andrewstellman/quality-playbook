`UploadedFile.filename()` returned the client's file name as sent, including directory components, so the documented `"upload/" + filename()` example could write outside the upload directory with a name like `../../evil.txt`. `filename()` now returns only the last path segment, and `extension()` is derived from it. The test is in `TestMultipartForms`. The docs example is fixed separately in javalin/javalin.github.io.

Reported to @tipsy by email on 21 Oct. Found with the Quality Playbook, an AI code-review tool I maintain; Claude reproduced it and wrote the fix and test, and I reviewed them.
