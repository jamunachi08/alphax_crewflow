frappe.ui.form.on("Project Contract", {
	setup(frm) {
		frm.set_query("freelancer", () => ({ filters: { status: "Active" } }));
	},
	refresh(frm) {
		const colors = { "Within Band": "green", "Below Minimum": "orange", "Above Maximum": "red" };
		if (frm.doc.band_position && frm.doc.docstatus === 0) {
			frm.dashboard.set_headline_alert(
				`<span class="indicator ${colors[frm.doc.band_position]}">${__(frm.doc.band_position)}</span>`
			);
		}
	},
});
