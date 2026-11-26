frappe.listview_settings["Daily Work Order"] = {
	add_fields: ["status", "qc_result"],
	get_indicator(doc) {
		const map = {
			Draft: "gray",
			Issued: "blue",
			Executed: "cyan",
			Delivered: "purple",
			"Pending Approval": "orange",
			Accepted: "green",
			Rejected: "red",
			Cancelled: "darkgrey",
		};
		return [__(doc.status), map[doc.status] || "gray", "status,=," + doc.status];
	},
};
