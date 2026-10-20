import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent
SOURCE = REPO_ROOT / "drivers/block/zram/zram_drv.c"


def read_source() -> str:
    return SOURCE.read_text(encoding="utf-8")


def extract_function(source: str, name: str) -> str:
    match = re.search(rf"\b{name}\s*\([^)]*\)\s*\{{", source, re.MULTILINE)
    assert match is not None, f"Could not find function {name}"
    start = match.start()
    brace_start = source.find("{", match.start())
    depth = 0
    for idx in range(brace_start, len(source)):
        char = source[idx]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[start : idx + 1]
    raise AssertionError(f"Could not extract function {name}")


class TestZramKernelBugs(unittest.TestCase):
    def test_bug_1_async_backing_read_allocation_failures_complete_parent_bio(self):
        """BUG-1: allocation failure paths should mark parent bio failed and end it."""
        func = extract_function(read_source(), "read_from_bdev_async")

        kmalloc_block = re.search(r"if\s*\(!req\)\s*(\{.*?\}|return;)", func, re.DOTALL)
        self.assertIsNotNone(kmalloc_block, "Missing kmalloc failure block")
        kmalloc_text = kmalloc_block.group(1)
        self.assertIn("parent->bi_status", kmalloc_text)
        self.assertIn("bio_endio(parent)", kmalloc_text)

        bio_alloc_block = re.search(r"if\s*\(!bio\)\s*\{(.*?)\n\t\}", func, re.DOTALL)
        self.assertIsNotNone(bio_alloc_block, "Missing bio_alloc failure block")
        bio_alloc_text = bio_alloc_block.group(1)
        self.assertIn("parent->bi_status", bio_alloc_text)
        self.assertIn("bio_endio(parent)", bio_alloc_text)

    def test_bug_2_unaligned_single_fragment_discard_ends_bio_before_return(self):
        """BUG-2: early return in unaligned discard path should bio_endio the bio."""
        func = extract_function(read_source(), "zram_bio_discard")
        guard = re.search(
            r"if\s*\(offset\)\s*\{\s*if\s*\(n <= \(PAGE_SIZE - offset\)\)\s*(.*?)\s*n -= \(PAGE_SIZE - offset\);",
            func,
            re.DOTALL,
        )
        self.assertIsNotNone(guard, "Could not find unaligned single-fragment discard guard")
        early_return_block = guard.group(1)
        self.assertIn("bio_endio(bio)", early_return_block)

    def test_bug_3_algorithm_params_store_blocks_post_init_mutation(self):
        """BUG-3: algorithm_params_store should reject writes after init_done(zram)."""
        func = extract_function(read_source(), "algorithm_params_store")
        self.assertIn("init_done(zram)", func)
        self.assertIn("-EBUSY", func)

    def test_bug_4_recompress_store_rejects_unknown_type_values(self):
        """BUG-4: type= parser should reject unknown values instead of leaving mode == 0."""
        func = extract_function(read_source(), "recompress_store")
        type_block = re.search(r'if\s*\(!strcmp\(param,\s*"type"\)\)\s*\{(.*?)continue;', func, re.DOTALL)
        self.assertIsNotNone(type_block, "Could not find type= parsing block")
        self.assertIn("-EINVAL", type_block.group(1))


if __name__ == "__main__":
    unittest.main()
