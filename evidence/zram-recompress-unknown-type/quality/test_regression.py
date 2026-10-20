import unittest
from pathlib import Path

from quality.test_functional import function_block


ROOT = Path(__file__).resolve().parents[1]
ZRAM_DRV = ROOT / "drivers/block/zram/zram_drv.c"


class TestConfirmedBugs(unittest.TestCase):
    @unittest.expectedFailure
    def test_algorithm_params_are_frozen_after_init(self):
        """[BUG from code review]
        algorithm_params_store() should reject post-init parameter writes with -EBUSY,
        matching the documented pre-init-only setup flow."""
        block = function_block(ZRAM_DRV, "algorithm_params_store")
        self.assertIn("if (init_done(zram))", block)
        self.assertIn("return -EBUSY;", block)

    @unittest.expectedFailure
    def test_async_backing_read_setup_failure_is_reported(self):
        """[BUG from code review]
        read_from_bdev_async() should mark the parent bio failed when request or bio
        allocation fails instead of returning silently."""
        block = function_block(ZRAM_DRV, "read_from_bdev_async")
        self.assertIn("parent->bi_status = BLK_STS_IOERR;", block)
        self.assertIn("bio_endio(parent);", block)

    @unittest.expectedFailure
    def test_unaligned_single_fragment_discard_completes_bio(self):
        """[BUG from code review]
        zram_bio_discard() should complete the bio even when an unaligned request frees
        no whole physical page."""
        block = function_block(ZRAM_DRV, "zram_bio_discard")
        fragment_guard = "if (n <= (PAGE_SIZE - offset))"
        self.assertIn(fragment_guard, block)
        guard_index = block.index(fragment_guard)
        return_index = block.index("return;", guard_index)
        bio_endio_index = block.rfind("bio_endio(bio);", guard_index, return_index)
        self.assertNotEqual(bio_endio_index, -1, "no bio_endio() before early return")

    @unittest.expectedFailure
    def test_recompress_store_rejects_unknown_type_values(self):
        """[BUG from spec_audits/2026-04-06-triage.md]
        recompress_store() should reject an unknown type= selector instead of leaving
        mode at 0 and scanning every eligible slot."""
        block = function_block(ZRAM_DRV, "recompress_store")
        self.assertIn('if (!strcmp(param, "type"))', block)
        self.assertIn("ret = -EINVAL;", block)
        self.assertRegex(
            block,
            r'if\s*\(!strcmp\(param,\s*"type"\)\).*?return\s+-EINVAL;',
            "unknown recompress types are not explicitly rejected",
        )


if __name__ == "__main__":
    unittest.main()
