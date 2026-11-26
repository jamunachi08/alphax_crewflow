# Copyright (c) 2026, AlphaX
# License: see license.txt

import frappe
from frappe import _
from frappe.utils import add_days, cint, getdate

from alphax_crewflow.crewflow.engine import rules


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = [
		{"fieldname": "project", "label": _("Project"), "fieldtype": "Link", "options": "Project", "width": 160},
		{"fieldname": "month", "label": _("Month"), "fieldtype": "Date", "width": 100},
		{"fieldname": "work_type", "label": _("Work Type"), "fieldtype": "Link", "options": "Work Type", "width": 120},
		{"fieldname": "boq_code", "label": _("BOQ Code"), "fieldtype": "Data", "width": 100},
		{"fieldname": "quota_days", "label": _("Quota"), "fieldtype": "Int", "width": 80},
		{"fieldname": "issued", "label": _("Consumed"), "fieldtype": "Int", "width": 90},
		{"fieldname": "accepted", "label": _("Accepted"), "fieldtype": "Int", "width": 90},
		{"fieldname": "rejected", "label": _("Rejected"), "fieldtype": "Int", "width": 90},
		{"fieldname": "in_progress", "label": _("In Progress"), "fieldtype": "Int", "width": 100},
		{"fieldname": "remaining", "label": _("Remaining"), "fieldtype": "Int", "width": 90},
		{"fieldname": "consumption_pct", "label": _("Consumption %"), "fieldtype": "Percent", "width": 120},
		{"fieldname": "rejected_pct", "label": _("Rejected %"), "fieldtype": "Percent", "width": 100},
	]
	cond, values = ["q.parenttype = 'Project BOQ'"], {}
	if filters.project:
		cond.append("b.project = %(project)s")
		values["project"] = filters.project
	if filters.from_date:
		cond.append("q.month_start >= %(from)s")
		values["from"] = rules.month_start(getdate(filters.from_date))
	if filters.to_date:
		cond.append("q.month_start <= %(to)s")
		values["to"] = getdate(filters.to_date)
	quotas = frappe.db.sql(
		f"""
		select b.project, q.month_start, q.work_type, q.boq_code, q.quota_days
		from `tabProject BOQ Quota` q join `tabProject BOQ` b on b.name = q.parent
		where {' and '.join(cond)}
		order by b.project, q.month_start, q.work_type
		""",
		values,
		as_dict=True,
	)
	data = []
	for q in quotas:
		end = add_days(rules.next_month_start(q.month_start), -1)
		extra = "and boq_code = %(boq)s" if q.boq_code else ""
		counts = frappe.db.sql(
			f"""
			select
				count(name) issued,
				sum(qc_result = 'Accepted') accepted,
				sum(qc_result = 'Rejected') rejected
			from `tabDaily Work Order`
			where docstatus = 1 and project = %(p)s and work_type = %(wt)s and work_date between %(s)s and %(e)s {extra}
			""",
			{"p": q.project, "wt": q.work_type, "s": q.month_start, "e": end, "boq": q.boq_code},
			as_dict=True,
		)[0]
		issued, acc, rej = cint(counts.issued), cint(counts.accepted), cint(counts.rejected)
		data.append(
			{
				"project": q.project,
				"month": q.month_start,
				"work_type": q.work_type,
				"boq_code": q.boq_code,
				"quota_days": q.quota_days,
				"issued": issued,
				"accepted": acc,
				"rejected": rej,
				"in_progress": issued - acc - rej,
				"remaining": max(cint(q.quota_days) - issued, 0),
				"consumption_pct": round(100.0 * issued / q.quota_days, 1) if q.quota_days else 0,
				"rejected_pct": round(100.0 * rej / issued, 1) if issued else 0,
			}
		)
	chart = None
	if data:
		chart = {
			"data": {
				"labels": [f"{d['work_type']} {d['month']:%b %y}" for d in data][:24],
				"datasets": [
					{"name": _("Quota"), "values": [d["quota_days"] for d in data][:24]},
					{"name": _("Consumed"), "values": [d["issued"] for d in data][:24]},
				],
			},
			"type": "bar",
		}
	return columns, data, None, chart
