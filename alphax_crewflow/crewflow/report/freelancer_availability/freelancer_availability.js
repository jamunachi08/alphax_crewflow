frappe.query_reports["Freelancer Availability"] = {
	filters: [
		{ fieldname: "month", label: __("Month"), fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1 },
		{ fieldname: "specialty", label: __("Specialty"), fieldtype: "Link", options: "Freelancer Specialty" },
		{ fieldname: "freelancer", label: __("Freelancer"), fieldtype: "Link", options: "Freelancer Profile" },
		{ fieldname: "include_inactive", label: __("Include Blocked / Inactive"), fieldtype: "Check" },
	],
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname && column.fieldname.startsWith("d") && data && data[column.fieldname]) {
			const off = data[column.fieldname] === __("Off");
			const bg = off ? "var(--gray-300)" : "var(--blue-100)";
			value = `<div style="background:${bg};border-radius:4px;padding:0 4px;font-size:11px">${value}</div>`;
		}
		return value;
	},
};
