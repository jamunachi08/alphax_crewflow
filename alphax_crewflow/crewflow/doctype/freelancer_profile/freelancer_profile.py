# Copyright (c) 2026, AlphaX
# License: see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from alphax_crewflow.crewflow.engine import services

MANUAL_STATUSES = {"Active", "Inactive"}


class FreelancerProfile(Document):
	def validate(self):
		if not 1 <= flt(self.initial_level) <= 5:
			frappe.throw(_("Initial Level must be between 1 and 5."))
		self._validate_supplier()
		if self.is_new():
			self.current_level = flt(self.initial_level)
			if flt(self.current_level) < flt(services.settings().min_level):
				self.status = "Blocked"
				self.status_reason = _("Onboarded below the minimum contracting level.")
		else:
			self._guard_status_change()
		if not self.rated_orders:
			# before any rating the level follows the onboarding level
			self.current_level = flt(self.initial_level)

	def _validate_supplier(self):
		group = services.settings().freelancer_supplier_group
		if group:
			sg = frappe.db.get_value("Supplier", self.supplier, "supplier_group")
			if sg != group:
				frappe.msgprint(
					_("Supplier {0} is in group {1}, not the freelancer group {2}.").format(self.supplier, sg, group),
					indicator="orange",
					alert=True,
				)

	def _guard_status_change(self):
		before = self.get_doc_before_save()
		if not before or before.status == self.status:
			return
		if self.flags.crewflow_reinstate:
			return
		if before.status in ("Blocked", "Suspended") or self.status not in MANUAL_STATUSES:
			frappe.throw(
				_("Status {0} to {1} can only change through an approved Reinstatement exception or the rating engine.").format(
					_(before.status), _(self.status)
				)
			)


@frappe.whitelist()
def create_from_supplier(supplier, specialty, initial_level):
	doc = frappe.get_doc(
		{"doctype": "Freelancer Profile", "supplier": supplier, "specialty": specialty, "initial_level": flt(initial_level)}
	)
	doc.insert()
	return doc.name
