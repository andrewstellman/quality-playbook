# st-004: changes after panel

- Drop the untested long_description_content_type reset (S2, S4): done; removed the line, YAGNI.
- Update the `val` annotations that now receive None (S1, O5): done; `_ProjectReadmeValue | None` and `str | None`.
- Comment the `vars(dist.metadata).pop` line (O1, S1): done; "_core_metadata writes Requires-Python whenever the attribute exists" (`_core_metadata.py:203` uses `hasattr`).
- Point at abravalheri's comment in #4183, not #4183 itself (O4, O5): done; PR links https://github.com/pypa/setuptools/issues/4183#issuecomment-1887294648 (the "Hyrum's law" comment).
