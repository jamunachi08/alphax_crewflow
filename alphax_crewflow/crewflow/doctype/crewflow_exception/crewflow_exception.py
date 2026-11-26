# Copyright (c) 2026, AlphaX
# License: see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime

from alphax_crewflow.crewflow.engine import services

NEEDS_REFERENCE = {
	"Quota Overrun", "Workload Overrun", "Post-facto Issue", "Rate Change", "Partial Acceptance", "Reinstatement",
}


class CrewFlowException(Document):
	def validate(self):
		if self.is_new() or not self.requested_by:
			self.requested_by = frappe.session.user
		self.status = "Pending" if self.docstatus == 0 else self.status
		if self.exception_type in NEEDS_REFERENCE and not (self.reference_doctype and self.reference_name):
			frappe.throw(_("{0} needs a reference document.").format(_(self.exception_type)))
		if self.exception_type == "Reinstatement" and self.reference_doctype != "Freelancer Profile":
			frappe.throw(_("A Reinstatement must reference a Freelancer Profile."))
		if self.exception_type == "Rate Change" and flt(self.new_rate) <= 0:
			frappe.throw(_("Enter the new rate."))
		if self.reference_doctype == "Daily Work Order" and self.reference_name:
			ref = frappe.db.get_value(
				"Daily Work Order", self.reference_name, ["project", "freelancer", "work_date"], as_dict=True
			)
			if ref:
				self.project, self.freelancer, self.work_date = ref.project, ref.freelancer, ref.work_date
		if self.reference_doctype == "Freelancer Profile" and self.reference_name:
			self.freelancer = self.reference_name

	def before_submit(self):
		if not services.user_can_approve(self.exception_type):
			roles = ", ".join(sorted(services.approver_roles(self.exception_type))) or _("none configured")
			frappe.throw(
				_("You cannot approve '{0}' exceptions. Approver roles: {1}").format(_(self.exception_type), roles),
				frappe.PermissionError,
			)
		if (
			services.settings().enforce_segregation
			and frappe.session.user == self.requested_by
			and frappe.session.user != "Administrator"
		):
			frappe.throw(_("Segregation of duties: you cannot approve your own exception request."))
		self.approved_by = frappe.session.user
		self.approved_on = now_datetime()
		self.status = "Approved"

	def on_submit(self):
		if self.exception_type == "Reinstatement":
			fp = frappe.get_doc("Freelancer Profile", self.reference_name)
			fp.flags.crewflow_reinstate = True
			fp.status = "Active"
			fp.status_reason = _("Reinstated by {0} on {1} ({2}): {3}").format(
				self.approved_by, self.approved_on, self.name, self.justification
			)
			fp.save(ignore_permissions=True)
		elif self.exception_type == "Rate Change" and self.reference_doctype == "Daily Work Order":
			dwo = frappe.get_doc("Daily Work Order", self.reference_name)
			if dwo.docstatus == 1:
				if dwo.purchase_invoice:
					frappe.throw(_("Work Order {0} is already invoiced on {1}.").format(dwo.name, dwo.purchase_invoice))
				old = dwo.rate
				dwo.db_set({"rate": flt(self.new_rate), "rate_source": _("Rate Change exception {0}").format(self.name)})
				dwo.add_comment("Info", _("Rate changed from {0} to {1} by {2} ({3}).").format(old, self.new_rate, self.approved_by, self.name))

	def on_cancel(self):
		self.db_set("status", "Cancelled")
