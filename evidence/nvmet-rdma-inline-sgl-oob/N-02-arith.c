/*
 * N-02 arithmetic confirmation harness — nvmet-rdma in-capsule SGL offset wrap.
 *
 * This does NOT reproduce a live crash and sends nothing over any wire. It
 * compiles the EXACT arithmetic from the pinned source and shows that a
 * host-chosen 64-bit SGL `addr` makes the bounds check at rdma.c:867 pass by
 * wrapping, after which the offset becomes a wild index into the 4-entry
 * inline_sg[] array. Method mirrors the Quality Playbook's "userspace
 * arithmetic extracted verbatim, compiled with gcc" approach.
 *
 * Source (drivers/nvme/target/rdma.c @ 4d7d9486, verbatim):
 *   855 static u16 nvmet_rdma_map_sgl_inline(struct nvmet_rdma_rsp *rsp) {
 *   858   u64 off = le64_to_cpu(sgl->addr);
 *   859   u32 len = le32_to_cpu(sgl->length);
 *   867   if (off + len > rsp->queue->dev->inline_data_size) { ...reject... }
 *   876   nvmet_rdma_use_inline_sg(rsp, len, off);
 *   830 static void nvmet_rdma_use_inline_sg(struct nvmet_rdma_rsp *rsp, u32 len, u64 off) {
 *   833   u64 page_off = off % PAGE_SIZE;
 *   834   u64 page_idx = off / PAGE_SIZE;
 *   835   int sg_count = num_pages(page_off + len);
 *   839   sg = &rsp->cmd->inline_sg[page_idx];   // <-- wild index
 *   193 static int num_pages(int len) { return 1 + (((len - 1) & PAGE_MASK) >> PAGE_SHIFT); }
 *   #define NVMET_RDMA_MAX_INLINE_SGE 4          // inline_sg[] has 4 entries
 *   int inline_data_size;                        // signed int (rdma.c:141)
 */
#include <stdint.h>
#include <stdio.h>
#include <inttypes.h>

/* x86-64 page constants, as the kernel uses them. */
#define PAGE_SHIFT 12
#define PAGE_SIZE  ((uint64_t)1 << PAGE_SHIFT)        /* 4096 */
#define PAGE_MASK  (~(PAGE_SIZE - 1))                 /* 0xFFFFFFFFFFFFF000 */

#define NVMET_RDMA_MAX_INLINE_SGE 4
/* sizeof(struct scatterlist) on x86-64 (CONFIG_NEED_SG_DMA_LENGTH): 32 bytes. */
#define SIZEOF_SCATTERLIST 32

/* rdma.c:193 verbatim; note the parameter is a *signed int*. */
static int num_pages(int len)
{
	return 1 + (((len - 1) & PAGE_MASK) >> PAGE_SHIFT);
}

/* The shipped check at rdma.c:867, as written (off+len in u64, wraps). */
static int shipped_check_passes(uint64_t off, uint32_t len, int inline_data_size)
{
	/* `inline_data_size` is promoted to u64 for the comparison. */
	return !(off + len > (uint64_t)inline_data_size);   /* 1 == accepted */
}

/* A non-wrapping fix: reject before adding (reorder so no term can wrap). */
static int fixed_check_passes(uint64_t off, uint32_t len, int inline_data_size)
{
	uint64_t ids = (uint64_t)inline_data_size;
	if (off > ids)
		return 0;
	return !(len > ids - off);
}

static void show(const char *label, uint64_t off, uint32_t len, int ids)
{
	int accepted = shipped_check_passes(off, len, ids);
	uint64_t page_off = off % PAGE_SIZE;
	uint64_t page_idx = off / PAGE_SIZE;
	int sg_count = num_pages((int)(page_off + len));       /* u64 truncated to int */
	/* &inline_sg[page_idx] displacement from the 4-entry array base: */
	uint64_t disp = page_idx * (uint64_t)SIZEOF_SCATTERLIST;

	printf("%-22s off=0x%016" PRIx64 " len=0x%" PRIx32 " inline_data_size=%d\n",
	       label, off, len, ids);
	printf("    off+len (u64)        = 0x%016" PRIx64 "  %s\n",
	       off + (uint64_t)len,
	       (off + (uint64_t)len) < off ? "<-- WRAPPED past 2^64" : "");
	printf("    shipped check :867   = %s\n",
	       accepted ? "ACCEPTED (passes bounds check)" : "rejected");
	if (!accepted) { printf("\n"); return; }
	printf("    page_idx = off/4096  = %" PRIu64 "  (inline_sg[] has %d entries; index is %s)\n",
	       page_idx, NVMET_RDMA_MAX_INLINE_SGE,
	       page_idx >= NVMET_RDMA_MAX_INLINE_SGE ? "OUT OF BOUNDS" : "in bounds");
	printf("    sg_count (num_pages) = %d\n", sg_count);
	if (page_idx >= NVMET_RDMA_MAX_INLINE_SGE) {
		printf("    &inline_sg[page_idx] = base + %" PRIu64 " bytes (= base + ~2^%d)\n",
		       disp, (int)(64 - __builtin_clzll(disp | 1)));
		printf("    => loop writes sg->offset/sg->length/sg_mark_end() at that wild address\n");
	}
	printf("    fixed check verdict  = %s\n\n",
	       fixed_check_passes(off, len, ids) ? "ACCEPTED" : "REJECTED (fix stops it)");
}

int main(void)
{
	/* inline_data_size default = NVMET_RDMA_DEFAULT_INLINE_DATA_SIZE = PAGE_SIZE. */
	int ids_default = (int)PAGE_SIZE;       /* 4096 */
	int ids_max = 16 * 1024;                /* NVMET_RDMA_MAX_INLINE_DATA_SIZE */

	puts("== N-02: nvmet-rdma in-capsule SGL bounds check wraps (rdma.c:867) ==\n");
	puts("Legitimate inline write (for contrast):");
	show("benign", 0x0, 0x1000, ids_default);

	puts("Malicious addr chosen so off+len wraps to 0 (reviewers' example):");
	show("wrap -> idx 2^52-1", 0xFFFFFFFFFFFFF000ULL, 0x1000, ids_default);

	puts("Same attack with the larger 16K inline_data_size:");
	show("wrap, ids=16K", 0xFFFFFFFFFFFFF000ULL, 0x1000, ids_max);

	puts("A different wrap point (off just below 2^64, len large):");
	show("wrap, big len", 0xFFFFFFFF00000000ULL, 0xFF000000, ids_default);

	puts("Conclusion: the shipped check accepts host addresses it must reject,");
	puts("and page_idx = off/PAGE_SIZE then indexes a 4-entry array at ~2^52;");
	puts("the non-wrapping fix rejects every crafted case above.");
	return 0;
}
