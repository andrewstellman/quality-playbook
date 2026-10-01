"""Verbatim-extraction harness for two bionemo-recipes fixes (CPU only).

The real modules cannot be imported without CUDA: amplify.state_dict_convert imports
transformer_engine via amplify.amplify_te, and models/esm2/collator.py imports
transformer_engine and nvtx at module level. This harness therefore pulls the named
functions out of a checkout with `ast` (exact source text, decorators included, nothing
retyped), writes them into stand-in modules with the same import names the tests use,
and runs the named test functions, also extracted verbatim from the checkout, under pytest.

Stubs (the only code not taken from the checkout):
  amplify: `io` namespace with `TransformCTX = object`, so the `ctx: io.TransformCTX`
           annotation on _pad_weights evaluates. The function body never touches `io`.
  thd:     `nvtx` module whose `annotate(...)` returns the function unchanged, so the
           `@nvtx.annotate(...)` decorator on _split_batch_by_cp_rank is kept verbatim.

Usage: run_extracted.py {amplify|thd} --src-tree DIR --test-tree DIR
"""

import argparse
import ast
import hashlib
import os
import subprocess
import sys
import tempfile
import textwrap


SPECS = {
    "amplify": {
        "src_file": "models/amplify/src/amplify/state_dict_convert.py",
        "src_funcs": ["_pad_weights"],
        "module_path": "amplify/state_dict_convert.py",
        "module_prelude": "import types\n\nimport torch\n\nio = types.SimpleNamespace(TransformCTX=object)  # STUB\n",
        "test_file": "models/amplify/tests/test_amplify_model.py",
        "test_funcs": ["test_pad_weights_dtype_device"],
        "test_prelude": "from unittest.mock import MagicMock\n\nimport pytest\nimport torch\n",
    },
    "thd": {
        "src_file": "models/esm2/collator.py",
        "src_funcs": ["_find_seq_dim", "_process_tensor_thd", "_process_tensor_bshd", "_split_batch_by_cp_rank"],
        "module_path": "collator.py",
        "module_prelude": "import torch\n\nimport nvtx  # STUB module, see nvtx.py\n",
        "extra_modules": {"nvtx.py": "def annotate(*args, **kwargs):  # STUB\n    return lambda fn: fn\n"},
        "test_file": "models/esm2/tests/test_collator_context_parallel.py",
        "test_funcs": [
            "get_dummy_data_bshd_single_sequence",
            "get_dummy_data_bshd_multiple_sequences",
            "test_split_batch_by_cp_rank_bshd_single_sequence",
            "test_split_batch_by_cp_rank_bshd_multiple_sequences",
            "test_split_batch_by_cp_rank_bshd_cp4",
            "test_split_batch_by_cp_rank_bshd_3d_tensor",
            "test_split_batch_by_cp_rank_thd_non_divisible",
            "test_split_batch_by_cp_rank_thd_covers_all_tokens",
        ],
        "test_prelude": "import pytest\nimport torch\n\nfrom collator import _split_batch_by_cp_rank\n",
    },
}


def extract(path, names):
    text = open(path).read()
    lines = text.splitlines(keepends=True)
    tree = ast.parse(text)
    found = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in names:
            start = min([node.lineno] + [d.lineno for d in node.decorator_list])
            found[node.name] = (start, node.end_lineno, "".join(lines[start - 1 : node.end_lineno]))
    out = []
    for name in names:
        if name not in found:
            out.append((name, None, None, None))  # not present in this tree
        else:
            out.append((name, *found[name]))
    return out


def git_state(tree):
    def g(*a):
        return subprocess.run(["git", "-C", tree, *a], capture_output=True, text=True).stdout.rstrip()

    return g("rev-parse", "HEAD"), g("status", "--short")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("fix", choices=SPECS)
    ap.add_argument("--src-tree", required=True)
    ap.add_argument("--test-tree", required=True)
    args = ap.parse_args()
    spec = SPECS[args.fix]

    for label, tree in (("source tree", args.src_tree), ("test tree", args.test_tree)):
        head, status = git_state(tree)
        print(f"{label}: {tree}\n  HEAD {head}\n  git status --short: {status.splitlines() or 'clean'}")

    work = tempfile.mkdtemp(prefix=f"harness-{args.fix}-", dir="/tmp/fix")
    src_path = os.path.join(args.src_tree, spec["src_file"])
    body = [spec["module_prelude"]]
    print(f"\n== extracted from {spec['src_file']} (source tree)")
    for name, start, end, seg in extract(src_path, spec["src_funcs"]):
        if seg is None:
            sys.exit(f"missing source function {name}")
        print(f"  {name}: lines {start}-{end} sha256={hashlib.sha256(seg.encode()).hexdigest()[:16]}")
        body.append("\n\n" + seg)
    mod = os.path.join(work, spec["module_path"])
    os.makedirs(os.path.dirname(mod), exist_ok=True)
    if os.path.dirname(spec["module_path"]):
        open(os.path.join(os.path.dirname(mod), "__init__.py"), "w").close()
    open(mod, "w").write("".join(body))
    for fname, content in spec.get("extra_modules", {}).items():
        open(os.path.join(work, fname), "w").write(content)

    test_path = os.path.join(args.test_tree, spec["test_file"])
    tbody = [spec["test_prelude"]]
    print(f"\n== extracted from {spec['test_file']} (test tree)")
    for name, start, end, seg in extract(test_path, spec["test_funcs"]):
        if seg is None:
            sys.exit(f"missing test function {name}")
        print(f"  {name}: lines {start}-{end} sha256={hashlib.sha256(seg.encode()).hexdigest()[:16]}")
        tbody.append("\n\n" + seg)
    tfile = os.path.join(work, f"test_extracted_{args.fix}.py")
    open(tfile, "w").write("".join(tbody))

    print("\n== extracted source function(s), exactly as written into the stand-in module")
    print(textwrap.indent(open(mod).read(), "  | ", lambda line: True))
    import torch

    print(f"== torch {torch.__version__}, cuda available: {torch.cuda.is_available()}\n")
    sys.stdout.flush()
    env = dict(os.environ, PYTHONPATH=work)
    rc = subprocess.run(
        [sys.executable, "-m", "pytest", "-v", "-rs", "-p", "no:cacheprovider", "--rootdir", work, tfile],
        cwd=work,
        env=env,
    ).returncode
    print(f"\npytest exit code: {rc}")
    if args.fix == "thd":
        demo_thd(work)
    sys.exit(rc)


def demo_thd(work):
    """Harness-only demonstration (not an upstream test): what the extracted function does
    with a non-divisible padded length, and the error text when many lengths are bad."""
    sys.path.insert(0, work)
    import torch
    from collator import _split_batch_by_cp_rank

    def shard_all(cu, cp):
        ids = torch.arange(int(cu[-1]), dtype=torch.int64).unsqueeze(0)
        seen = []
        for r in range(cp):
            out, _ = _split_batch_by_cp_rank(
                cu_seqlens_padded=cu, input_ids_padded=ids, labels_padded=ids.clone(),
                qvk_format="thd", cp_rank=r, cp_world_size=cp,
            )
            seen += out.flatten().tolist()
        return sorted(set(range(int(cu[-1]))) - set(seen))

    print("\n== harness demo: cu_seqlens_padded=[0, 8, 18] (lengths 8, 10), cp_world_size=2")
    try:
        missing = shard_all(torch.tensor([0, 8, 18], dtype=torch.int32), 2)
        print(f"  no exception; token positions assigned to no CP rank: {missing}")
    except ValueError as e:
        print(f"  ValueError: {e}")
    print("== harness demo: 7 packed sequences of length 6, cp_world_size=2")
    try:
        missing = shard_all(torch.arange(0, 43, 6, dtype=torch.int32), 2)
        print(f"  no exception; token positions assigned to no CP rank: {missing}")
    except ValueError as e:
        print(f"  ValueError: {e}")


if __name__ == "__main__":
    main()
