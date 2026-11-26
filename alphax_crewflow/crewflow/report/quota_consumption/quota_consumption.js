frappe.query_reports["Quota Consumption"] = {
	filters: [
		{ fieldname: "project", label: __("Project"), fieldtype: "Link", options: "Project" },
		{ fieldname: "from_date", label: __("From Month"), fieldtype: "Date", default: frappe.datetime.month_start() },
		{ fieldname: "to_date", label: __("To Month"), fieldtype: "Date", default: frappe.datetime.month_end() },
	],
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "consumption_pct" && data) {
			const pct = data.consumption_pct;
			const color = pct > 100 ? "red" : pct >= 80 ? "orange" : "green";
			value = `<span style="color:var(--${color}-600);font-weight:600">${value}</span>`;
		}
		return value;
	},
};
