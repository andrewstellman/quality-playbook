#include "shim.h"
#include "real_lookups.c"
/* the opcode-check-only alternative, as in the council replacement minus the state test */
static struct iscsit_cmd *opcode_check_only(struct iscsit_conn *c, u32 ttt)
{ struct iscsit_cmd *p = iscsit_find_cmd_from_ttt(c, ttt); return (!p || p->iscsi_opcode != ISCSI_OP_NOOP_IN) ? NULL : p; }
static struct iscsit_conn conn;
static void reset(void){ conn.conn_cmd_list.next = conn.conn_cmd_list.prev = &conn.conn_cmd_list; }
static void add(struct iscsit_cmd *c){ list_add_tail(&c->i_conn_node, &conn.conn_cmd_list); }
static int fails;
static void check(const char *what, struct iscsit_cmd *got, struct iscsit_cmd *want){
  int ok = got == want; fails += !ok;
  printf("%s %-62s -> %s\n", ok ? "PASS" : "FAIL", what, got ? got->name : "NULL (connection closed)"); }
int main(void){
  struct iscsit_cmd rej  = { ISCSI_OP_REJECT,   0, {0}, "Reject" };
  struct iscsit_cmd nop0 = { ISCSI_OP_NOOP_IN,  0, {0}, "NOP-In" };
  struct iscsit_cmd rd0  = { ISCSI_OP_SCSI_CMD, 0, {0}, "READ" };
  struct iscsit_cmd rd5  = { ISCSI_OP_SCSI_CMD, 5, {0}, "READ" };
  struct iscsit_cmd txt7 = { ISCSI_OP_TEXT,     7, {0}, "Text" };
  struct iscsit_cmd nop6 = { ISCSI_OP_NOOP_IN,  6, {0}, "NOP-In" };
  puts("== patched lookup (iscsit_find_nopin_from_ttt)");
  reset(); add(&rej); add(&nop0);
  check("[Reject ttt0, NOP-In ttt0], reply names ttt0", iscsit_find_nopin_from_ttt(&conn,0), &nop0);
  reset(); add(&rd0);
  check("[READ ttt0], NOP-Out names ttt0", iscsit_find_nopin_from_ttt(&conn,0), NULL);
  reset(); add(&rej);
  check("[Reject ttt0], NOP-Out names ttt0", iscsit_find_nopin_from_ttt(&conn,0), NULL);
  reset(); add(&rd5); add(&txt7); add(&nop6);
  check("[READ 5, Text 7, NOP-In 6], NOP-Out names 5", iscsit_find_nopin_from_ttt(&conn,5), NULL);
  check("[READ 5, Text 7, NOP-In 6], NOP-Out names 7", iscsit_find_nopin_from_ttt(&conn,7), NULL);
  check("[READ 5, Text 7, NOP-In 6], reply names 6", iscsit_find_nopin_from_ttt(&conn,6), &nop6);
  check("[READ 5, Text 7, NOP-In 6], unknown ttt 9", iscsit_find_nopin_from_ttt(&conn,9), NULL);
  printf("patched failures: %d\n", fails); int pf = fails; fails = 0;
  puts("== for comparison: existing lookup + opcode check");
  reset(); add(&rej); add(&nop0);
  check("[Reject ttt0, NOP-In ttt0], reply names ttt0", opcode_check_only(&conn,0), &nop0);
  reset(); add(&rd5); add(&nop6);
  check("[READ 5, NOP-In 6], NOP-Out names 5", opcode_check_only(&conn,5), NULL);
  printf("opcode-check-only failures: %d\n", fails);
  return pf != 0; }
