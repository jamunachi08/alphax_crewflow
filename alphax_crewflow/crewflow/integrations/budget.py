# Copyright (c) 2026, AlphaX
# License: see license.txt

"""Early-warning budget alert (default 80%) on top of ERPNext's own Budget stop/warn at 100%."""

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt


def budget_alerts(doc):
	from alphax_crewflow.crewflow.engine import services

	s = services.settings()
	alert_pct = flt(s.budget_alert_pct)
	if not alert_pct:
		return
	try:
		from erpnext.accounts.utils import get_fiscal_year
	except ImportError:
		return
	date = doc.get("transaction_date") or doc.get("posting_date")
	try:
		fy = get_fiscal_year(date, company=doc.company, as_dict=True)
	except Exception:
		return

	totals = defaultdict(float)
	for row in doc.items:
		project = row.get("project") or doc.get("project")
		if project and row.get("expense_account"):
			totals[(project, row.expense_account)] += flt(row.base_net_amount)

	for (project, account), amount in totals.items():
		budget = frappe.db.sql(
			"""
			select ba.budget_amount
			from `tabBudget` b join `tabBudget Account` ba on ba.parent = b.name
			where b.docstatus = 1 and b.budget_against = 'Project' and b.project = %s
			  and b.fiscal_year = %s and ba.account = %s
			""",
			(project, fy.name, account),
		)
		if not budget or not flt(budget[0][0]):
			continue
		limit = flt(budget[0][0])
		actual = frappe.db.sql(
			"""
			select coalesce(sum(debit - credit), 0) from `tabGL Entry`
			where project = %s and account = %s and is_cancelled = 0 and posting_date between %s and %s
			""",
			(project, account, fy.year_start_date, fy.year_end_date),
		)[0][0]
		used = flt(actual) + amount
		pct = 100.0 * used / limit
		if pct >= alert_pct:
			frappe.msgprint(
				_("Budget alert: {0} / {1} at {2}% of budget after this document.").format(project, account, round(pct, 1)),
				indicator="red" if pct >= 100 else "orange",
				alert=True,
			)
