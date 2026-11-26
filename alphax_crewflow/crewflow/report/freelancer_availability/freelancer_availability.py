# Copyright (c) 2026, AlphaX
# License: see license.txt

import calendar

import frappe
from frappe import _
from frappe.utils import getdate, today

from alphax_crewflow.crewflow.engine import rules


def execute(filters=None):
	filters = frappe._dict(filters or {})
	start = rules.month_start(getdate(filters.month or today()))
	days = calendar.monthrange(start.year, start.month)[1]
	end = start.replace(day=days)

	columns = [
		{"fieldname": "freelancer", "label": _("Freelancer"), "fieldtype": "Link", "options": "Freelancer Profile", "width": 150},
		{"fieldname": "freelancer_name", "label": _("Name"), "fieldtype": "Data", "width": 160},
		{"fieldname": "level", "label": _("Level"), "fieldtype": "Float", "precision": 2, "width": 70},
		{"fieldname": "booked", "label": _("Booked"), "fieldtype": "Int", "width": 70},
	]
	for d in range(1, days + 1):
		dt = start.replace(day=d)
		columns.append({"fieldname": f"d{d}", "label": f"{d} {dt:%a}", "fieldtype": "Data", "width": 70})

	fp_filters = {"status": "Active"} if not filters.include_inactive else {}
	if filters.specialty:
		fp_filters["specialty"] = filters.specialty
	if filters.freelancer:
		fp_filters["name"] = filters.freelancer
	people = frappe.get_all(
		"Freelancer Profile", filters=fp_filters, fields=["name", "freelancer_name", "current_level"], order_by="freelancer_name"
	)
	if not people:
		return columns, []
	names = [p.name for p in people]

	orders = frappe.get_all(
		"Daily Work Order",
		filters={"freelancer": ("in", names), "docstatus": 1, "work_date": ("between", [start, end])},
		fields=["freelancer", "work_date", "project"],
	)
	off = frappe.get_all(
		"Freelancer Unavailability",
		filters={"freelancer": ("in", names), "from_date": ("<=", end), "to_date": (">=", start)},
		fields=["freelancer", "from_date", "to_date"],
	)
	grid = {n: {} for n in names}
	for o in orders:
		grid[o.freelancer][getdate(o.work_date).day] = o.project
	for u in off:
		for d in range(1, days + 1):
			dt = start.replace(day=d)
			if getdate(u.from_date) <= dt <= getdate(u.to_date):
				grid[u.freelancer].setdefault(d, _("Off"))

	data = []
	for p in people:
		row = {"freelancer": p.name, "freelancer_name": p.freelancer_name, "level": p.current_level}
		row["booked"] = sum(1 for v in grid[p.name].values() if v != _("Off"))
		for d in range(1, days + 1):
			row[f"d{d}"] = grid[p.name].get(d, "")
		data.append(row)
	return columns, data
