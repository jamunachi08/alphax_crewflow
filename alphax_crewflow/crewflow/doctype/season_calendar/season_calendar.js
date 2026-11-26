frappe.ui.form.on("Season Calendar", {
	refresh(frm) {
		if (frm.is_new()) return;
		frm.add_custom_button(__("Suggest Hijri Periods"), () =>
			frm.call("suggest_hijri_periods").then(() => {
				frm.reload_doc();
				frappe.show_alert({ message: __("Hijri periods refreshed. Review against the official calendar."), indicator: "green" });
			})
		);
	},
});
