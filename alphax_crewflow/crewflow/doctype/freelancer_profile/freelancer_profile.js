frappe.ui.form.on("Freelancer Profile", {
	refresh(frm) {
		const colors = { Active: "green", Blocked: "red", Suspended: "orange", Inactive: "gray" };
		if (frm.doc.status) frm.page.set_indicator(__(frm.doc.status), colors[frm.doc.status]);
		if (frm.is_new()) return;
		frm.add_custom_button(__("Work Orders"), () =>
			frappe.set_route("List", "Daily Work Order", { freelancer: frm.doc.name })
		, __("View"));
		frm.add_custom_button(__("Rating History"), () =>
			frappe.set_route("List", "Freelancer Rating Log", { freelancer: frm.doc.name })
		, __("View"));
		frm.add_custom_button(__("Availability"), () =>
			frappe.set_route("query-report", "Freelancer Availability", { freelancer: frm.doc.name })
		, __("View"));
		if (["Blocked", "Suspended"].includes(frm.doc.status)) {
			frm.add_custom_button(__("Request Reinstatement"), () =>
				frappe.new_doc("CrewFlow Exception", {
					exception_type: "Reinstatement",
					reference_doctype: "Freelancer Profile",
					reference_name: frm.doc.name,
					freelancer: frm.doc.name,
				})
			);
		}
	},
});
