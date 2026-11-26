frappe.views.calendar["Freelancer Unavailability"] = {
	field_map: {
		start: "from_date",
		end: "to_date",
		id: "name",
		title: "freelancer_name",
	},
	filters: [{ fieldtype: "Link", fieldname: "freelancer", options: "Freelancer Profile", label: __("Freelancer") }],
	get_events_method: "frappe.desk.calendar.get_events",
};
