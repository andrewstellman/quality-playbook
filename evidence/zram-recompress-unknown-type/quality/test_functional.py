import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ZRAM_DRV = ROOT / "drivers/block/zram/zram_drv.c"
ZCOMP = ROOT / "drivers/block/zram/zcomp.c"
BACKEND_ZSTD = ROOT / "drivers/block/zram/backend_zstd.c"
DOC = ROOT / "Documentation/admin-guide/blockdev/zram.rst"
DOC_GATHERED = ROOT / "docs_gathered/zram-community-development-history.md"
ZSMALLOC_DOC = ROOT / "docs_gathered/zsmalloc-design.md"


def read(path: Path) -> str:
    return path.read_text()


def function_block(path: Path, name: str) -> str:
    text = read(path)
    for match in re.finditer(rf"\b{re.escape(name)}\s*\(", text):
        start = match.start()
        paren = text.find("(", start)
        depth = 0
        idx = paren
        while idx < len(text):
            ch = text[idx]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    idx += 1
                    break
            idx += 1
        while idx < len(text) and text[idx].isspace():
            idx += 1
        if idx >= len(text) or text[idx] != "{":
            continue
        brace = idx
        depth = 0
        for end in range(brace, len(text)):
            ch = text[end]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    line_start = text.rfind("\n", 0, start) + 1
                    return text[line_start:end + 1]
    raise AssertionError(f"{name} body unterminated in {path}")


class ZramSourceAssertions(unittest.TestCase):
    def assertAllIn(self, block: str, snippets):
        for snippet in snippets:
            self.assertIn(snippet, block)

    def assertRegexAll(self, block: str, patterns):
        for pattern in patterns:
            self.assertRegex(block, pattern)


class TestSpecRequirements(ZramSourceAssertions):
    def test_post_init_configuration_guards(self):
        """[Req: formal — Documentation/admin-guide/blockdev/zram.rst §§2-4,10] layout-sensitive knobs freeze after init."""
        self.assertAllIn(function_block(ZRAM_DRV, "disksize_store"), ["if (init_done(zram))", "return -EBUSY;"])
        self.assertAllIn(function_block(ZRAM_DRV, "__comp_algorithm_store"), ["if (init_done(zram))", "return -EBUSY;"])
        self.assertAllIn(function_block(ZRAM_DRV, "compressed_writeback_store"), ["if (init_done(zram))", "return -EBUSY;"])
        self.assertAllIn(function_block(ZRAM_DRV, "backing_dev_store"), ["if (init_done(zram))", "err = -EBUSY;"])

    def test_disksize_initializes_metadata_and_backends(self):
        """[Req: formal — Documentation/admin-guide/blockdev/zram.rst §§76-145] disksize is the initialization gate."""
        block = function_block(ZRAM_DRV, "disksize_store")
        self.assertAllIn(block, [
            "disksize = PAGE_ALIGN(disksize);",
            "if (!zram_meta_alloc(zram, disksize))",
            "comp = zcomp_create(",
            "zram->disksize = disksize;",
            "set_capacity_and_notify(",
        ])

    def test_mem_limit_and_max_used_input_rules(self):
        """[Req: formal — Documentation/admin-guide/blockdev/zram.rst §§147-165] mem-limit parsing is explicit."""
        self.assertAllIn(function_block(ZRAM_DRV, "mem_limit_store"), ["limit = memparse(buf, &tmp);", "PAGE_ALIGN(limit) >> PAGE_SHIFT"])
        self.assertAllIn(function_block(ZRAM_DRV, "mem_used_max_store"), ["if (err || val != 0)", "return -EINVAL;"])

    def test_incompressible_pages_use_huge_path(self):
        """[Req: formal — docs_gathered/zsmalloc-design.md §§18-29] incompressible pages use raw PAGE_SIZE storage."""
        self.assertIn("Maximum allocation: PAGE_SIZE", read(ZSMALLOC_DOC))
        write_page = function_block(ZRAM_DRV, "zram_write_page")
        huge_path = function_block(ZRAM_DRV, "write_incompressible_page")
        self.assertIn("if (comp_len >= huge_class_size)", write_page)
        self.assertAllIn(huge_path, ["zs_malloc(zram->mem_pool, PAGE_SIZE", "set_slot_flag(zram, index, ZRAM_HUGE);", "set_slot_size(zram, index, PAGE_SIZE);"])

    def test_writeback_parsing_supports_types_and_ranges(self):
        """[Req: formal — Documentation/admin-guide/blockdev/zram.rst §§352-392] writeback parses modern and legacy selectors."""
        block = function_block(ZRAM_DRV, "writeback_store")
        self.assertAllIn(block, ["err = parse_mode(param, &mode);", 'if (!strcmp(param, "type"))', 'if (!strcmp(param, "page_index"))', 'if (!strcmp(param, "page_indexes"))'])
        self.assertAllIn(function_block(ZRAM_DRV, "parse_page_indexes"), ["delim = strchr(val, '-');", "if (*hi >= nr_pages || *lo > *hi)", "*hi += 1;"])

    def test_recompress_supports_threshold_algorithm_and_priority(self):
        """[Req: formal — Documentation/admin-guide/blockdev/zram.rst §§462-547] recompress supports threshold/algo/priority selectors."""
        block = function_block(ZRAM_DRV, "recompress_store")
        self.assertAllIn(block, ['if (!strcmp(param, "type"))', 'if (!strcmp(param, "threshold"))', 'if (!strcmp(param, "algo"))', 'if (!strcmp(param, "priority"))', "if (threshold >= huge_class_size)"])

    def test_reset_claims_and_drains_before_teardown(self):
        """[Req: formal — docs_gathered/zram-community-development-history.md §§151-159] reset blocks opens and drains I/O."""
        block = function_block(ZRAM_DRV, "reset_store")
        self.assertAllIn(block, ["mutex_lock(&disk->open_mutex);", "zram->claim = true;", "sync_blockdev(disk->part0);", "zram_reset_device(zram);"])

    def test_stats_exports_match_documented_columns(self):
        """[Req: formal — Documentation/admin-guide/blockdev/zram.rst §§197-283] stats exports preserve field order."""
        io_stat = function_block(ZRAM_DRV, "io_stat_show")
        mm_stat = function_block(ZRAM_DRV, "mm_stat_show")
        bd_stat = function_block(ZRAM_DRV, "bd_stat_show")
        self.assertIn('%8llu %8llu 0 %8llu\\n', io_stat)
        self.assertIn('%8llu %8llu %8llu %8lu %8ld %8llu %8lu %8llu %8llu\\n', mm_stat)
        self.assertIn('%8llu %8llu %8llu\\n', bd_stat)


class TestFitnessScenarios(ZramSourceAssertions):
    def test_same_filled_pages_use_marker_storage(self):
        """[Req: inferred — from page_same_filled()/write_same_filled_page()] same-filled pages stay metadata-only."""
        self.assertAllIn(function_block(ZRAM_DRV, "page_same_filled"), ["if (val != page[last_pos])", "*element = val;"])
        self.assertAllIn(function_block(ZRAM_DRV, "write_same_filled_page"), ["set_slot_flag(zram, index, ZRAM_SAME);", "set_slot_handle(zram, index, fill);", "atomic64_inc(&zram->stats.same_pages);"])

    def test_writeback_filters_and_rollbacks(self):
        """[Req: formal — Documentation/admin-guide/blockdev/zram.rst §§345-459] writeback only touches eligible slots."""
        scan = function_block(ZRAM_DRV, "scan_slots_for_writeback")
        complete = function_block(ZRAM_DRV, "zram_writeback_complete")
        self.assertAllIn(scan, ["test_slot_flag(zram, index, ZRAM_WB)", "test_slot_flag(zram, index, ZRAM_SAME)", "test_slot_flag(zram, index, ZRAM_IDLE)", "test_slot_flag(zram, index, ZRAM_HUGE)", "test_slot_flag(zram, index, ZRAM_INCOMPRESSIBLE)"])
        self.assertAllIn(complete, ["zram_account_writeback_rollback(zram);", "zram_release_bdev_block(zram, req->blk_idx);", "if (!test_slot_flag(zram, index, ZRAM_PP_SLOT))"])

    def test_recompression_clears_idle_and_marks_incompressible(self):
        """[Req: formal — Documentation/admin-guide/blockdev/zram.rst §§503-547] recompression updates slot flags truthfully."""
        block = function_block(ZRAM_DRV, "recompress_slot")
        self.assertAllIn(block, ["clear_slot_flag(zram, index, ZRAM_IDLE);", "set_slot_flag(zram, index, ZRAM_INCOMPRESSIBLE);", "set_slot_comp_priority(zram, index, prio);"])

    def test_reset_and_remove_claim_before_freeing_state(self):
        """[Req: formal — docs_gathered/zram-community-development-history.md §§151-159] lifecycle teardown blocks openers before freeing state."""
        remove_block = function_block(ZRAM_DRV, "zram_remove")
        self.assertAllIn(remove_block, ["mutex_lock(&zram->disk->open_mutex);", "if (disk_openers(zram->disk))", "sync_blockdev(zram->disk->part0);", "zram_reset_device(zram);", "del_gendisk(zram->disk);"])

    def test_per_cpu_stream_get_retries_after_migration_race(self):
        """[Req: inferred — from zcomp_stream_get()] per-CPU stream acquisition is migration-safe."""
        block = function_block(ZCOMP, "zcomp_stream_get")
        self.assertAllIn(block, ["for (;;) {", "struct zcomp_strm *zstrm = raw_cpu_ptr(comp->stream);", "mutex_lock(&zstrm->lock);", "if (likely(zstrm->buffer))", "mutex_unlock(&zstrm->lock);"])

    def test_partial_io_uses_temporary_page(self):
        """[Req: inferred — from zram_bvec_write_partial()] partial writes preserve untouched bytes."""
        block = function_block(ZRAM_DRV, "zram_bvec_write_partial")
        self.assertAllIn(block, ["struct page *page = alloc_page(GFP_NOIO);", "ret = zram_read_page(zram, page, index, bio);", "memcpy_from_bvec(page_address(page) + offset, bvec);", "ret = zram_write_page(zram, page, index);"])

    def test_deferred_decompression_rechecks_written_back_state(self):
        """[Req: inferred — from decompress_bdev_page()] deferred decompression revalidates WB state."""
        block = function_block(ZRAM_DRV, "decompress_bdev_page")
        self.assertAllIn(block, ["if (!test_slot_flag(zram, index, ZRAM_WB))", "memset_page(page, 0, 0, PAGE_SIZE);", "return -EIO;"])


class TestBoundariesAndEdgeCases(ZramSourceAssertions):
    def test_idle_store_accepts_all_or_age_only(self):
        """[Req: formal — Documentation/admin-guide/blockdev/zram.rst §§322-340] idle input accepts only documented forms."""
        block = function_block(ZRAM_DRV, "idle_store")
        self.assertAllIn(block, ['if (!sysfs_streq(buf, "all"))', "!kstrtouint(buf, 0, &age_sec)", "return -EINVAL;"])

    def test_backing_device_must_be_block_and_nonzero(self):
        """[Req: formal — Documentation/admin-guide/blockdev/zram.rst §§345-351] backing devices are block-only and non-zero sized."""
        block = function_block(ZRAM_DRV, "backing_dev_store")
        self.assertAllIn(block, ["if (!S_ISBLK(inode->i_mode))", "err = -ENOTBLK;", "if (!nr_pages)", "err = -EINVAL;"])

    def test_writeback_limit_rounds_down_to_safe_units(self):
        """[Req: formal — Documentation/admin-guide/blockdev/zram.rst §§398-437] writeback budget prevents page-size underflow."""
        block = function_block(ZRAM_DRV, "writeback_limit_store")
        self.assertAllIn(block, ["val = rounddown(val, PAGE_SIZE / 4096);", "zram->bd_wb_limit = val;"])

    def test_writeback_batch_size_rejects_zero(self):
        """[Req: formal — Documentation/admin-guide/blockdev/zram.rst §§451-458] writeback batch size must be non-zero."""
        block = function_block(ZRAM_DRV, "writeback_batch_size_store")
        self.assertRegexAll(block, [r"if\s*\(!val\)", r"return -EINVAL;"])

    def test_parse_page_indexes_rejects_bad_ranges(self):
        """[Req: formal — Documentation/admin-guide/blockdev/zram.rst §§377-392] page range parsing rejects malformed selectors."""
        block = function_block(ZRAM_DRV, "parse_page_indexes")
        self.assertAllIn(block, ["if (!delim)", "return -EINVAL;", "if (*hi >= nr_pages || *lo > *hi)", "return -ERANGE;"])

    def test_discard_only_frees_whole_pages(self):
        """[Req: inferred — from zram_bio_discard()] discard frees whole physical pages only."""
        block = function_block(ZRAM_DRV, "zram_bio_discard")
        self.assertAllIn(block, ["if (offset) {", "n -= (PAGE_SIZE - offset);", "while (n >= PAGE_SIZE) {", "slot_free(zram, index);", "bio_endio(bio);"])

    def test_zstd_backend_installs_default_level_and_dictionary_state(self):
        """[Req: formal — Documentation/admin-guide/blockdev/zram.rst §§96-126] zstd backend parameter setup is explicit."""
        block = function_block(BACKEND_ZSTD, "zstd_setup_params")
        self.assertAllIn(block, ["if (params->level == ZCOMP_PARAM_NOT_SET)", "params->level = zstd_default_clevel();", "zstd_create_cdict_byreference", "zstd_create_ddict_byreference"])

    def test_documented_reset_contract_is_present_in_specs(self):
        """[Req: formal — docs_gathered/zram-community-development-history.md §§151-160] reset requires re-sizing before reuse."""
        history = read(DOC_GATHERED)
        admin = read(DOC)
        self.assertIn("Device reset via sysfs clears all memory; disksize must be reset before reuse", history)
        self.assertIn("You must set the disksize again", admin)


if __name__ == "__main__":
    unittest.main()
