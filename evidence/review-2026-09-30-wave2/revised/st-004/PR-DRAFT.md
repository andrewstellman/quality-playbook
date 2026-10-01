**Title:** Ignore readme and requires-python not listed in dynamic

## Summary of changes

`pyproject.toml` with `[project]` `name = 'p'`, `version = '1'` and no `dynamic`, plus `setup(long_description='hello')` in `setup.py`: the build fails with `AttributeError: 'NoneType' object has no attribute 'get'`. With `setup(python_requires='>=3.8')` it fails with `TypeError: 'NoneType' object is not iterable`. Expected: the `_MissingDynamic` warning and the value ignored, as already happens for `description`, `classifiers`, `dependencies`, etc. (the warn-and-ignore behaviour abravalheri explains in [a comment on #4183](https://github.com/pypa/setuptools/issues/4183#issuecomment-1887294648)).

`_handle_missing_dynamic` (`setuptools/config/_apply_pyprojecttoml.py`) resets `readme` and `requires-python` to `None`, which `_long_description` and `_python_requires` did not handle. Both now treat `None` as a reset. For `python_requires`, the value is also cleared from `dist`, so `_finalize_requires` cannot copy it back. The new cases extend `TestPresetField.test_not_listed_in_dynamic`.

PEP 621 (`dynamic`): "If the metadata does not list a field in ``dynamic``, then a build back-end CANNOT fill in the requisite metadata on behalf of the user".

### Pull Request Checklist
- [x] Changes have tests
- [x] News fragment added in [`newsfragments/`].

Found by Quality Playbook, an AI code-review tool, with Claude; I reviewed the change.
