frappe.ui.form.on("Framework Agreement", {
	setup(frm) {
		frm.set_query("client_contract", () => ({ filters: { docstatus: 1, customer: frm.doc.customer || undefined } }));
		frm.set_query("freelancer", "members", () => ({ filters: { status: "Active" } }));
	},
	refresh(frm) {
		const colors = { Draft: "gray", Active: "green", Expired: "red", Closed: "darkgrey" };
		if (frm.doc.status) frm.page.set_indicator(__(frm.doc.status), colors[frm.doc.status]);
		if (!frm.is_new() && frm.doc.status !== "Closed") {
			frm.add_custom_button(__("Close Agreement"), () =>
				frappe.confirm(__("Close this agreement? No further work orders can be issued against it."), () =>
					frm.call("close_agreement").then(() => frm.reload_doc())
				)
			);
		}
		if (!frm.is_new()) {
			frm.add_custom_button(__("Work Orders"), () =>
				frappe.set_route("List", "Daily Work Order", { framework_agreement: frm.doc.name })
			, __("View"));
		}
	},
});
