frappe.views.calendar["Daily Work Order"] = {
	field_map: {
		start: "work_date",
		end: "work_date",
		id: "name",
		title: "freelancer_name",
		status: "status",
	},
	style_map: {
		Issued: "info",
		Executed: "info",
		Delivered: "warning",
		"Pending Approval": "warning",
		Accepted: "success",
		Rejected: "danger",
	},
	filters: [
		{ fieldtype: "Link", fieldname: "project", options: "Project", label: __("Project") },
		{ fieldtype: "Link", fieldname: "freelancer", options: "Freelancer Profile", label: __("Freelancer") },
		{ fieldtype: "Link", fieldname: "work_type", options: "Work Type", label: __("Work Type") },
	],
	get_events_method: "frappe.desk.calendar.get_events",
};
