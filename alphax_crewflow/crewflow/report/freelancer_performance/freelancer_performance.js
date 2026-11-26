frappe.query_reports["Freelancer Performance"] = {
	filters: [
		{ fieldname: "from_date", label: __("From"), fieldtype: "Date", default: frappe.datetime.add_months(frappe.datetime.get_today(), -12) },
		{ fieldname: "to_date", label: __("To"), fieldtype: "Date", default: frappe.datetime.get_today() },
		{ fieldname: "project", label: __("Project"), fieldtype: "Link", options: "Project" },
		{ fieldname: "specialty", label: __("Specialty"), fieldtype: "Link", options: "Freelancer Specialty" },
		{ fieldname: "status", label: __("Status"), fieldtype: "Select", options: "\nActive\nBlocked\nSuspended\nInactive" },
	],
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "current_level" && data && data.current_level < 3.5) {
			value = `<span style="color:var(--red-600);font-weight:600">${value}</span>`;
		}
		return value;
	},
};
