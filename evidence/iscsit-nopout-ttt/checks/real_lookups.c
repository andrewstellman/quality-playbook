/* extracted verbatim from patched drivers/target/iscsi/iscsi_target_util.c */
struct iscsit_cmd *iscsit_find_cmd_from_ttt(
	struct iscsit_conn *conn,
	u32 targ_xfer_tag)
{
	struct iscsit_cmd *cmd = NULL;

	spin_lock_bh(&conn->cmd_lock);
	list_for_each_entry(cmd, &conn->conn_cmd_list, i_conn_node) {
		if (cmd->targ_xfer_tag == targ_xfer_tag) {
			spin_unlock_bh(&conn->cmd_lock);
			return cmd;
		}
	}
	spin_unlock_bh(&conn->cmd_lock);

	pr_err("Unable to locate TTT: 0x%08x on CID: %hu\n",
			targ_xfer_tag, conn->cid);
	return NULL;
}

struct iscsit_cmd *iscsit_find_nopin_from_ttt(struct iscsit_conn *conn,
					      u32 targ_xfer_tag)
{
	struct iscsit_cmd *cmd;

	spin_lock_bh(&conn->cmd_lock);
	list_for_each_entry(cmd, &conn->conn_cmd_list, i_conn_node) {
		if (cmd->iscsi_opcode == ISCSI_OP_NOOP_IN &&
		    cmd->targ_xfer_tag == targ_xfer_tag) {
			spin_unlock_bh(&conn->cmd_lock);
			return cmd;
		}
	}
	spin_unlock_bh(&conn->cmd_lock);

	pr_err("Unable to locate NOPIN TTT: 0x%08x on CID: %u\n",
	       targ_xfer_tag, conn->cid);
	return NULL;
}
