"""Before/after probe: build wheel metadata for small projects and report the result.
Run with PYTHONPATH pointing at a setuptools source tree."""
import os, sys, tempfile, textwrap, warnings, io, contextlib, pathlib, shutil
import setuptools
from setuptools import build_meta

CASES = [
 # (id, pyproject [project] extra lines, setup() kwargs source, setup.cfg text)
 ("A no dynamic; setup.py long_description", "", "long_description='hello'", None),
 ("B no dynamic; setup.py python_requires", "", "python_requires='>=3.8'", None),
 ("C no dynamic; setup.py both + content type", "", "long_description='hello', long_description_content_type='text/markdown', python_requires='>=3.8'", None),
 ("D dynamic=[readme]; setup.py long_description", "dynamic = ['readme']", "long_description='hello'", None),
 ("E dynamic=[requires-python]; setup.py python_requires", "dynamic = ['requires-python']", "python_requires='>=3.8'", None),
 ("F pyproject readme + requires-python; plain setup()", "readme = 'README.md'\nrequires-python = '>=3.9'", "", None),
 ("G pyproject and setup.py both set them", "readme = 'README.md'\nrequires-python = '>=3.9'", "long_description='hello', python_requires='>=3.8'", None),
 ("H no [project] table; setup.py sets both", None, "name='p', version='1', long_description='hello', python_requires='>=3.8'", None),
 ("I no dynamic; setup.py description", "", "description='short'", None),
 ("J no dynamic; plain setup()", "", "", None),
 ("K pyproject readme table", "readme = {text = 'inline', content-type = 'text/x-rst'}", "", None),
 ("L no dynamic; setup.py empty strings", "", "long_description='', python_requires=''", None),
 ("M no dynamic; setup.cfg long_description + python_requires", "", "", "[metadata]\nlong_description = from cfg\n[options]\npython_requires = >=3.7\n"),
 ("N no dynamic; setup.py python_requires + description", "", "python_requires='>=3.8', description='short'", None),
]

def run(case):
    cid, proj, kwargs, cfg = case
    d = pathlib.Path(tempfile.mkdtemp())
    try:
        py = "[build-system]\nrequires = ['setuptools']\nbuild-backend = 'setuptools.build_meta'\n"
        if proj is not None:
            py += "[project]\nname = 'p'\nversion = '1'\n" + proj + "\n"
        (d/"pyproject.toml").write_text(py)
        (d/"setup.py").write_text(f"from setuptools import setup\nsetup({kwargs})\n")
        (d/"README.md").write_text("readme file text\n")
        (d/"p.py").write_text("")
        if cfg: (d/"setup.cfg").write_text(cfg)
        out = d/"out"; out.mkdir()
        cwd = os.getcwd(); os.chdir(d)
        buf = io.StringIO()
        try:
            with warnings.catch_warnings(record=True) as w, contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                warnings.simplefilter("always")
                try:
                    name = build_meta.prepare_metadata_for_build_wheel(str(out))
                    meta = (out/name/"METADATA").read_text()
                    head, _, body = meta.partition("\n\n")
                    rp = [l for l in head.splitlines() if l.startswith("Requires-Python")]
                    ct = [l for l in head.splitlines() if l.startswith("Description-Content-Type")]
                    sm = [l for l in head.splitlines() if l.startswith("Summary")]
                    res = "OK | " + "; ".join([*(rp or ["Requires-Python: (absent)"]), *(ct or ["Content-Type: (absent)"]), *(sm or []), "body=" + repr(body.strip())])
                except BaseException as e:
                    res = f"CRASH {type(e).__name__}: {e}"
            md = sorted({str(x.message).splitlines()[0].strip() for x in w if "defined outside of" in str(x.message)})
            res += " | warnings: " + (", ".join(md) if md else "none")
        finally:
            os.chdir(cwd)
        return res
    finally:
        shutil.rmtree(d, ignore_errors=True)

print("# setuptools from", os.path.dirname(setuptools.__file__), setuptools.__version__, file=sys.stderr)
for c in CASES:
    print(c[0] + "\t" + run(c))
