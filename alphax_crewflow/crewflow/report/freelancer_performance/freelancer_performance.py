# Copyright (c) 2026, AlphaX
# License: see license.txt

import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = [
		{"fieldname": "freelancer", "label": _("Freelancer"), "fieldtype": "Link", "options": "Freelancer Profile", "width": 160},
		{"fieldname": "freelancer_name", "label": _("Name"), "fieldtype": "Data", "width": 180},
		{"fieldname": "specialty", "label": _("Specialty"), "fieldtype": "Link", "options": "Freelancer Specialty", "width": 130},
		{"fieldname": "status", "label": _("Status"), "fieldtype": "Data", "width": 90},
		{"fieldname": "current_level", "label": _("Level"), "fieldtype": "Float", "precision": 2, "width": 80},
		{"fieldname": "orders", "label": _("Rated Orders"), "fieldtype": "Int", "width": 100},
		{"fieldname": "accepted", "label": _("Accepted"), "fieldtype": "Int", "width": 90},
		{"fieldname": "rejected", "label": _("Rejected"), "fieldtype": "Int", "width": 90},
		{"fieldname": "rejected_pct", "label": _("Rejected %"), "fieldtype": "Percent", "width": 100},
		{"fieldname": "quality", "label": _("Quality"), "fieldtype": "Float", "precision": 2, "width": 85},
		{"fieldname": "compliance", "label": _("Compliance"), "fieldtype": "Float", "precision": 2, "width": 95},
		{"fieldname": "punctuality", "label": _("Punctuality"), "fieldtype": "Float", "precision": 2, "width": 95},
		{"fieldname": "manager", "label": _("Manager"), "fieldtype": "Float", "precision": 2, "width": 85},
		{"fieldname": "weighted", "label": _("Avg Score"), "fieldtype": "Float", "precision": 2, "width": 90},
	]
	cond, join, values = ["1=1"], ["l.freelancer = fp.name"], {}
	if filters.from_date:
		join.append("l.work_date >= %(from)s")
		values["from"] = filters.from_date
	if filters.to_date:
		join.append("l.work_date <= %(to)s")
		values["to"] = filters.to_date
	if filters.project:
		join.append("l.project = %(project)s")
		values["project"] = filters.project
	if filters.specialty:
		cond.append("fp.specialty = %(specialty)s")
		values["specialty"] = filters.specialty
	if filters.status:
		cond.append("fp.status = %(status)s")
		values["status"] = filters.status
	data = frappe.db.sql(
		f"""
		select
			fp.name freelancer, fp.freelancer_name, fp.specialty, fp.status, fp.current_level,
			count(l.name) orders,
			sum(l.qc_result = 'Accepted') accepted,
			sum(l.qc_result = 'Rejected') rejected,
			avg(l.quality_score) quality, avg(l.compliance_score) compliance,
			avg(l.punctuality_score) punctuality, avg(l.manager_score) manager,
			avg(l.weighted_score) weighted
		from `tabFreelancer Profile` fp
		left join `tabFreelancer Rating Log` l on {' and '.join(join)}
		where {' and '.join(cond)}
		group by fp.name
		order by fp.current_level desc
		""",
		values,
		as_dict=True,
	)
	for d in data:
		d.rejected_pct = round(100.0 * flt(d.rejected) / d.orders, 1) if d.orders else 0
	return columns, data
