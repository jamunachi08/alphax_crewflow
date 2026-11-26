frappe.ui.form.on("CrewFlow Settings", {
	refresh(frm) {
		frm.add_custom_button(__("Generate Freelancer Invoices"), () => {
			frappe.prompt(
				{
					fieldname: "month",
					fieldtype: "Date",
					label: __("Any date in the month to invoice"),
					default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
					reqd: 1,
				},
				(v) =>
					frappe.call({
						method: "alphax_crewflow.crewflow.doctype.crewflow_settings.crewflow_settings.run_freelancer_invoicing",
						args: { month: v.month },
						freeze: true,
					}).then((r) => {
						const list = r.message || [];
						frappe.msgprint(list.length ? __("Created: {0}", [list.join(", ")]) : __("Nothing to invoice for that month."));
					}),
				__("Freelancer Invoicing")
			);
		});
	},
});
