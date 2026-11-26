# Copyright (c) 2026, AlphaX
# License: see license.txt

"""Monthly freelancer invoicing: one Purchase Invoice per freelancer and currency covering
all work orders accepted in the period that are not yet invoiced."""

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import add_days, cint, getdate, today

from alphax_crewflow.crewflow.engine import rules, services


def generate_freelancer_invoices(period_start=None):
	s = services.settings()
	if not s.freelancer_service_item:
		frappe.throw(_("Set the Freelancer Service Item in CrewFlow Settings."))
	period_start = period_start or rules.previous_month_start(getdate(today()))
	period_end = add_days(rules.next_month_start(period_start), -1)

	orders = frappe.get_all(
		"Daily Work Order",
		filters={
			"docstatus": 1,
			"qc_result": "Accepted",
			"purchase_invoice": ("is", "not set"),
			"work_date": ("between", [period_start, period_end]),
		},
		fields=["name", "freelancer", "project", "business_line", "work_date", "work_type", "rate", "currency", "boq_code"],
		order_by="freelancer, work_date",
	)
	groups = defaultdict(list)
	for o in orders:
		groups[(o.freelancer, o.currency)].append(o)

	created = []
	for (freelancer, currency), rows in groups.items():
		created.append(_make_invoice(s, freelancer, currency, rows, period_start, period_end))
	return created


def _make_invoice(s, freelancer, currency, rows, period_start, period_end):
	company = s.company or frappe.db.get_value("Project", rows[0].project, "company")
	pi = frappe.new_doc("Purchase Invoice")
	pi.update(
		{
			"supplier": freelancer,  # Freelancer Profile is named after its Supplier
			"company": company,
			"posting_date": today(),
			"set_posting_time": 1,
			"currency": currency,
			"bill_no": f"CF-{freelancer}-{period_start:%Y%m}"[:140],
			"bill_date": period_end,
			"remarks": _("Freelancer work orders accepted {0} to {1}").format(period_start, period_end),
		}
	)
	for o in rows:
		pi.append(
			"items",
			{
				"item_code": s.freelancer_service_item,
				"qty": 1,
				"rate": o.rate,
				"project": o.project,
				"cost_center": o.business_line or frappe.db.get_value("Project", o.project, "cost_center"),
				"description": f"{o.work_type} - {o.work_date} - {o.project}" + (f" - BOQ {o.boq_code}" if o.boq_code else ""),
				"crewflow_work_order": o.name,
			},
		)
	pi.set_missing_values()
	pi.insert(ignore_permissions=True)
	for o in rows:
		frappe.db.set_value("Daily Work Order", o.name, "purchase_invoice", pi.name, update_modified=False)
	if cint(s.auto_submit_invoices):
		pi.submit()
	return pi.name
