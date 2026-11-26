frappe.ui.form.on("Purchase Order", {
	refresh(frm) {
		if (frm.doc.docstatus !== 0 || frm.is_new() || frm.doc.crewflow_budget_checked) return;
		const finance = ["CrewFlow Finance", "CrewFlow Admin", "Accounts Manager"].some((r) => frappe.user.has_role(r));
		if (!finance) return;
		frm.add_custom_button(__("Confirm Budget Available"), () =>
			frappe.call({
				method: "alphax_crewflow.crewflow.integrations.purchase_order.mark_budget_checked",
				args: { purchase_order: frm.doc.name },
			}).then(() => frm.reload_doc())
		);
	},
});
