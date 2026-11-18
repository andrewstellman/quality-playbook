#include "shim.h"
#include "real_lookups.c"
#define ISCSI_OP_NOOP_OUT 0x00
static struct iscsit_conn conn;
static void reset(void){ conn.conn_cmd_list.next = conn.conn_cmd_list.prev = &conn.conn_cmd_list; }
static void add(struct iscsit_cmd *c){ list_add_tail(&c->i_conn_node, &conn.conn_cmd_list); }
static int fails;
static void check(const char *what, struct iscsit_cmd *got, struct iscsit_cmd *want){
  int ok = got == want; fails += !ok;
  printf("%s %-66s -> %s\n", ok ? "PASS" : "FAIL", what, got ? got->name : "NULL"); }
int main(void){
  static struct iscsit_cmd rd[1000];
  struct iscsit_cmd rej0 = { ISCSI_OP_REJECT, 0, {0}, "Reject0" };
  struct iscsit_cmd rd0  = { ISCSI_OP_SCSI_CMD, 0, {0}, "READ0" };
  struct iscsit_cmd txt0 = { ISCSI_OP_TEXT, 0, {0}, "Text0" };
  struct iscsit_cmd nop0 = { ISCSI_OP_NOOP_IN, 0, {0}, "NOP-In0" };
  struct iscsit_cmd nop3 = { ISCSI_OP_NOOP_IN, 3, {0}, "NOP-In3" };
  struct iscsit_cmd nop4 = { ISCSI_OP_NOOP_IN, 4, {0}, "NOP-In4" };
  struct iscsit_cmd rejr5 = { ISCSI_OP_REJECT, 5, {0}, "Reject(from READ ttt5)" };
  struct iscsit_cmd nopout = { ISCSI_OP_NOOP_OUT, 0xFFFFFFFF, {0}, "NOP-Out cmd" };
  struct iscsit_cmd nopnr = { ISCSI_OP_NOOP_IN, 0xFFFFFFFF, {0}, "NOP-In(no response)" };
  struct iscsit_cmd nopend = { ISCSI_OP_NOOP_IN, 1000, {0}, "NOP-In1000" };
  reset();
  check("empty list, ttt 0", iscsit_find_nopin_from_ttt(&conn,0), NULL);
  reset(); add(&rd0); add(&rej0); add(&txt0); add(&nop0);
  check("[READ0, Reject0, Text0, NOP-In0] ttt 0", iscsit_find_nopin_from_ttt(&conn,0), &nop0);
  check("  same list, unchanged first-match lookup ttt 0 (for reference)", iscsit_find_cmd_from_ttt(&conn,0), &rd0);
  reset(); add(&nop3); add(&nop4);
  check("[NOP-In3, NOP-In4] ttt 4", iscsit_find_nopin_from_ttt(&conn,4), &nop4);
  check("[NOP-In3, NOP-In4] ttt 3", iscsit_find_nopin_from_ttt(&conn,3), &nop3);
  reset(); add(&rejr5);
  check("[Reject keeping a READ's ttt 5] ttt 5", iscsit_find_nopin_from_ttt(&conn,5), NULL);
  reset(); for (int i = 0; i < 1000; i++) { rd[i] = (struct iscsit_cmd){ ISCSI_OP_SCSI_CMD, (u32)i, {0}, "READ" }; add(&rd[i]); } add(&nopend);
  check("[1000 READs ttt 0..999, NOP-In1000] ttt 1000", iscsit_find_nopin_from_ttt(&conn,1000), &nopend);
  check("  same list ttt 999 (a READ)", iscsit_find_nopin_from_ttt(&conn,999), NULL);
  /* precondition: caller filters ttt 0xffffffff before calling */
  reset(); add(&nopout); add(&nopnr);
  check("[NOP-Out cmd, NOP-In no-resp] ttt 0xffffffff (unreachable: caller filters)", iscsit_find_nopin_from_ttt(&conn,0xFFFFFFFF), &nopnr);
  /* known limitation in the notes: a second reply still matches */
  reset(); add(&nop4);
  struct iscsit_cmd *a = iscsit_find_nopin_from_ttt(&conn,4), *b = iscsit_find_nopin_from_ttt(&conn,4);
  check("[NOP-In4] first reply ttt 4", a, &nop4);
  check("[NOP-In4] second reply ttt 4 still matches (double reply, out of scope)", b, &nop4);
  printf("failures: %d\n", fails); return fails != 0; }
