import math, tomllib
import tomlkit
from tomlkit.items import Float

inf, nan = float("inf"), float("nan")
CASES = [
    ("+0.0", "-x", lambda v: -v),
    ("+5.0", "x * -0.0", lambda v: v * -0.0),
    ("+5.0", "x / -inf", lambda v: v / -inf),
    ("-0.0", "x * 1", lambda v: v * 1),
    ("-0.0", "+x", lambda v: +v),
    ("-1e-200", "x * 1e-200", lambda v: v * 1e-200),
    ("+0", "x / -1 (Integer)", lambda v: v / -1),
    ("0.0", "-x (unsigned)", lambda v: -v),
    ("+0.0", "x + 0.0", lambda v: v + 0.0),
    ("-1.5", "x * -1", lambda v: v * -1),
    ("+1.5", "x * -1", lambda v: v * -1),
    ("+1.0", "x * nan", lambda v: v * nan),
    ("+1.0", "x * -nan", lambda v: v * -nan),
    ("+inf", "x - inf", lambda v: v - inf),
    ("-1.0", "x * nan", lambda v: v * nan),
    ("1.0", "x * nan (unsigned)", lambda v: v * nan),
    ("+1.0", "x * inf", lambda v: v * inf),
    ("+1.0", "x * -inf", lambda v: v * -inf),
    ("-1.0", "x * -inf", lambda v: v * -inf),
    ("-inf", "x * -1", lambda v: v * -1),
    ("+1e308", "x * 10", lambda v: v * 10),
]

def orig(self, result):
    raw = str(result)
    if self._sign and result >= 0:
        raw = f"+{raw}"
    return Float(result, self._trivia, raw)

def shape_a(self, result):  # run's patch
    raw = str(result)
    if self._sign and result >= 0 and not raw.startswith("-"):
        raw = f"+{raw}"
    return Float(result, self._trivia, raw)

def shape_b(self, result):  # startswith only
    raw = str(result)
    if self._sign and not raw.startswith("-"):
        raw = f"+{raw}"
    return Float(result, self._trivia, raw)

def shape_c(self, result):  # copysign only
    raw = str(result)
    if self._sign and math.copysign(1.0, result) > 0:
        raw = f"+{raw}"
    return Float(result, self._trivia, raw)

def run(fn):
    Float._new = fn
    out = []
    for src, _, op in CASES:
        doc = tomlkit.parse(f"x = {src}")
        doc["x"] = op(doc["x"])
        s = doc.as_string()
        try:
            tomlkit.parse(s); tomllib.loads(s); ok = "ok "
        except Exception as e:
            ok = "BAD"
        out.append(f"{ok} {s[4:]}")
    return out

cols = [run(f) for f in (orig, shape_a, shape_b, shape_c)]
print(f"{'source':10} {'op':20} {'0518af2':12} {'A: >=0 and not startswith':27} {'B: not startswith':20} {'C: copysign > 0'}")
for (src, name, _), *row in zip(CASES, *cols):
    print(f"{src:10} {name:20} {row[0]:12} {row[1]:27} {row[2]:20} {row[3]}")
