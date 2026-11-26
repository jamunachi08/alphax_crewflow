# Copyright (c) 2026, AlphaX
# License: see license.txt

import frappe
from frappe import _
from frappe.utils import cint, flt, now_datetime

from alphax_crewflow.crewflow.engine import rules, services
from alphax_crewflow.crewflow.integrations.budget import budget_alerts

FINANCE_ROLES = ["CrewFlow Finance", "CrewFlow Admin", "Accounts Manager"]


def validate(doc, method=None):
	before = doc.get_doc_before_save()
	if before and flt(before.base_grand_total) != flt(doc.base_grand_total) and doc.get("crewflow_budget_checked"):
		# amounts changed after Finance checked: require a fresh check
		doc.crewflow_budget_checked = 0
		doc.crewflow_budget_checked_by = None
		doc.crewflow_budget_checked_on = None
	budget_alerts(doc)


def before_submit(doc, method=None):
	s = services.settings()
	if not cint(s.enable_po_approval):
		return
	if cint(s.require_budget_check) and not doc.get("crewflow_budget_checked"):
		frappe.throw(_("Finance must confirm budget availability before this order is approved."))
	role = rules.po_required_role(
		flt(doc.base_grand_total),
		flt(s.po_tier1_limit), s.po_tier1_role,
		flt(s.po_tier2_limit), s.po_tier2_role,
		s.po_tier3_role,
	)
	if role and not services.user_has_any_role([role]):
		frappe.throw(
			_("Orders of {0} require approval by {1}.").format(frappe.format(doc.base_grand_total, {"fieldtype": "Currency"}), role),
			frappe.PermissionError,
		)


@frappe.whitelist()
def mark_budget_checked(purchase_order):
	frappe.only_for(FINANCE_ROLES)
	doc = frappe.get_doc("Purchase Order", purchase_order)
	if doc.docstatus != 0:
		frappe.throw(_("Only draft orders can be budget-checked."))
	doc.db_set(
		{
			"crewflow_budget_checked": 1,
			"crewflow_budget_checked_by": frappe.session.user,
			"crewflow_budget_checked_on": now_datetime(),
		}
	)
	return True
