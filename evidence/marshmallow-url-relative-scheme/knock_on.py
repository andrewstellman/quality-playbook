"""Run the same inputs through validate.URL and fields.Url. Usage: PYTHONPATH=<clone>/src python knock_on.py"""
import marshmallow
from marshmallow import ValidationError, fields, validate

print("marshmallow from", marshmallow.__file__)

CONFIGS = [
    ("relative=False", dict()),
    ("relative=True", dict(relative=True)),
    ("relative=True,absolute=False", dict(relative=True, absolute=False)),
    ("relative=True,schemes=['ws']", dict(relative=True, schemes=["ws"])),
]
INPUTS = [
    "http://example.com",
    "http://example.com/a?u=http://b.c",
    "ftp://example.com",
    "ws://test.test",
    "foo://example.org",
    "/foo/bar",
    "/foo?bar#baz",
    "//host/x",
    "/redirect?to=http://example.com",
    "/a#http://x.y",
    "/p?u=ws://q",
    "/a/b://c",
    "?next=https://example.com/",
    "#http://x.y",
    "a://b",
    "file:///tmp/x",
    "",
    "://x",
]

def run(v, s):
    try:
        v(s)
        return "ok"
    except ValidationError as e:
        return "ERR"

for name, kw in CONFIGS:
    v = validate.URL(**kw)
    print(f"== validate.URL({name})")
    for s in INPUTS:
        print(f"{s!r:40} {run(v, s)}")

print("== fields.Url(relative=True).deserialize")
f = fields.Url(relative=True)
for s in INPUTS:
    try:
        f.deserialize(s)
        r = "ok"
    except ValidationError:
        r = "ERR"
    print(f"{s!r:40} {r}")
