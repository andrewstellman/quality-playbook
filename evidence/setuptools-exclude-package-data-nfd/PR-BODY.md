## Summary of changes

With `exclude_package_data={'pkg': ['café.key']}` written in NFC and the file's name stored on disk in NFD (as macOS does), the file is still included in both the wheel and the sdist. `build_py.exclude_data_files` compares names and patterns byte for byte with `fnmatch`, while `MANIFEST.in` matching has normalized both sides since GHSA-h35f-9h28-mq5c. The fix normalizes both with `unicode_utils.normalize` before matching, and the new test builds a package with an NFD file name and an NFC pattern.

Found with the Quality Playbook, an AI code-review tool I maintain. The fix and test were written with AI assistance and reviewed by me.

### Pull Request Checklist
- [x] Changes have tests
- [x] News fragment added in `newsfragments/`.
