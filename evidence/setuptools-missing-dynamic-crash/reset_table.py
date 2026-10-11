# What if readme / requires-python were added to the reset table instead (unpatched source)?
import os, tempfile, pathlib, warnings, io, contextlib
from setuptools.config import _apply_pyprojecttoml as m
from setuptools import build_meta
def build(kwargs):
    d = pathlib.Path(tempfile.mkdtemp()); os.chdir(d)
    (d/"pyproject.toml").write_text("[build-system]\nrequires=['setuptools']\nbuild-backend='setuptools.build_meta'\n[project]\nname='p'\nversion='1'\n")
    (d/"setup.py").write_text(f"from setuptools import setup\nsetup({kwargs})\n"); (d/"p.py").write_text("")
    out = d/"out"; out.mkdir()
    with warnings.catch_warnings(), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        warnings.simplefilter("ignore")
        try:
            n = build_meta.prepare_metadata_for_build_wheel(str(out))
            head = (out/n/"METADATA").read_text().partition("\n\n")
            return "OK " + "; ".join(l for l in head[0].splitlines() if l.startswith(("Requires-Python","Description"))) + " body=" + repr(head[2].strip())
        except BaseException as e:
            return f"CRASH {type(e).__name__}: {e}"
for label, table in [("readme -> ''", {"readme": ""}), ("readme -> {}", {"readme": {}}), ("requires-python -> ''", {"requires-python": ""})]:
    saved = dict(m._RESET_PREVIOUSLY_DEFINED); m._RESET_PREVIOUSLY_DEFINED.update(table)
    kw = "long_description='hello'" if "readme" in table else "python_requires='>=3.8'"
    print(label, "|", build(kw)); m._RESET_PREVIOUSLY_DEFINED.clear(); m._RESET_PREVIOUSLY_DEFINED.update(saved)
