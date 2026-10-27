`UploadedFile.filename()` returns the file name exactly as the client sent it in 7.2.3 and earlier, which can include directory components such as `../`. #2675 makes it return only the file name from the next release on. This adds a short note after the upload example saying so, and leaves the example itself unchanged.

As discussed with @tipsy by email. Found with the Quality Playbook, an AI code-review tool I maintain; Claude wrote the change, and I reviewed it.
