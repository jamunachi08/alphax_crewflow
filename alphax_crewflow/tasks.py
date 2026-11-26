# Copyright (c) 2026, AlphaX
# License: see license.txt

import frappe
from frappe import _
from frappe.utils import cint, date_diff, getdate, today

from alphax_crewflow.crewflow.doctype.framework_agreement.framework_agreement import compute_status
from alphax_crewflow.crewflow.engine import services


def daily():
	refresh_framework_agreements()
	run_monthly_invoicing()


def refresh_framework_agreements():
	for name in frappe.get_all("Framework Agreement", filters={"status": ("!=", "Closed")}, pluck="name"):
		fa = frappe.get_doc("Framework Agreement", name)
		status = compute_status(fa)
		if status != fa.status:
			fa.db_set("status", status, update_modified=False)
		days_left = date_diff(fa.end_date, today())
		if status == "Active" and not fa.expiry_alert_sent and 0 <= days_left <= cint(fa.expiry_alert_days):
			users = {fa.owner}
			for role in services.approver_roles("Contract Approval"):
				users.update(services.users_with_role(role))
			services.notify(
				users,
				_("Framework Agreement {0} expires in {1} days ({2}).").format(fa.title, days_left, fa.end_date),
				"Framework Agreement",
				fa.name,
			)
			fa.db_set("expiry_alert_sent", 1, update_modified=False)


def run_monthly_invoicing():
	s = services.settings()
	if not cint(s.auto_generate_invoices) or getdate(today()).day != cint(s.payment_day or 10):
		return
	if not s.freelancer_service_item:
		frappe.log_error("CrewFlow: Freelancer Service Item not set; monthly invoicing skipped.", "CrewFlow Invoicing")
		return
	from alphax_crewflow.crewflow.integrations.invoicing import generate_freelancer_invoices

	try:
		created = generate_freelancer_invoices()
	except Exception:
		frappe.log_error(frappe.get_traceback(), "CrewFlow Invoicing")
		return
	if created:
		users = set()
		for role in ("CrewFlow Finance",):
			users.update(services.users_with_role(role))
		services.notify(
			users,
			_("{0} freelancer invoices generated for last month.").format(len(created)),
			"Purchase Invoice",
			created[0],
		)
