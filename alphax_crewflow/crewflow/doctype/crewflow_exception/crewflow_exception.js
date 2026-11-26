frappe.ui.form.on("CrewFlow Exception", {
	refresh(frm) {
		const colors = { Pending: "orange", Approved: "green", Cancelled: "darkgrey" };
		if (frm.doc.status) frm.page.set_indicator(__(frm.doc.status), colors[frm.doc.status]);
		if (frm.doc.docstatus === 0 && !frm.is_new()) {
			frm.page.set_primary_action(__("Approve"), () => frm.savesubmit());
		}
	},
});
