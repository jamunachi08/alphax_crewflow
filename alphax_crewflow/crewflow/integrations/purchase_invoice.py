# Copyright (c) 2026, AlphaX
# License: see license.txt

import frappe
from frappe import _

from alphax_crewflow.crewflow.integrations.budget import budget_alerts


def validate(doc, method=None):
	for row in doc.items:
		wo = row.get("crewflow_work_order")
		if not wo:
			continue
		linked = frappe.db.get_value("Daily Work Order", wo, ["purchase_invoice", "qc_result"], as_dict=True)
		if not linked or linked.qc_result != "Accepted":
			frappe.throw(_("Row {0}: Work Order {1} is not accepted.").format(row.idx, wo))
		if linked.purchase_invoice and linked.purchase_invoice != doc.name:
			frappe.throw(_("Row {0}: Work Order {1} is already on {2}.").format(row.idx, wo, linked.purchase_invoice))
	budget_alerts(doc)


def unlink_work_orders(doc, method=None):
	for row in doc.items:
		wo = row.get("crewflow_work_order")
		if wo and frappe.db.get_value("Daily Work Order", wo, "purchase_invoice") == doc.name:
			frappe.db.set_value("Daily Work Order", wo, "purchase_invoice", None, update_modified=False)
