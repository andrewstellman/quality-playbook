#include <stdio.h>
#include <stddef.h>
typedef unsigned int u32; typedef unsigned short u16; typedef unsigned char u8;
struct list_head { struct list_head *next, *prev; };
#define container_of(p,t,m) ((t *)((char *)(p) - offsetof(t,m)))
#define list_for_each_entry(pos, head, member) \
  for (pos = container_of((head)->next, typeof(*pos), member); &pos->member != (head); \
       pos = container_of(pos->member.next, typeof(*pos), member))
static void list_add_tail(struct list_head *n, struct list_head *h){ n->prev=h->prev; n->next=h; h->prev->next=n; h->prev=n; }
#define spin_lock_bh(l) ((void)(l))
#define spin_unlock_bh(l) ((void)(l))
#define pr_err(...) ((void)0)
#define ISCSI_OP_NOOP_IN 0x20
#define ISCSI_OP_SCSI_CMD 0x01
#define ISCSI_OP_TEXT 0x04
#define ISCSI_OP_REJECT 0x3f
struct iscsit_cmd { u8 iscsi_opcode; u32 targ_xfer_tag; struct list_head i_conn_node; const char *name; };
struct iscsit_conn { int cmd_lock; struct list_head conn_cmd_list; u16 cid; };
