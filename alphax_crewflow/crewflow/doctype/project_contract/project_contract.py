# Copyright (c) 2026, AlphaX
# License: see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_months, flt, getdate, now_datetime, today

from alphax_crewflow.crewflow.doctype.rate_band.rate_band import find_band
from alphax_crewflow.crewflow.engine import rules, services


class ProjectContract(Document):
	def validate(self):
		if getdate(self.valid_from) > getdate(self.valid_to):
			frappe.throw(_("Valid From cannot be after Valid To."))
		fp = frappe.db.get_value("Freelancer Profile", self.freelancer, ["status", "current_level"], as_dict=True)
		if fp.status != "Active":
			frappe.throw(_("Freelancer is {0} and cannot be contracted.").format(_(fp.status)))
		self.freelancer_level = flt(fp.current_level)
		self._apply_band()
		self.avg_paid_12m = average_paid(self.specialty, self.work_type)

	def _apply_band(self):
		band, row = find_band(self.specialty, self.work_type, self.freelancer_level, self.valid_from, self.rate_band)
		if not row:
			self.band_min = self.band_max = None
			self.band_position = ""
			frappe.msgprint(_("No rate band found for this specialty, task type and level."), indicator="orange", alert=True)
			return
		self.rate_band = band.name
		if band.currency and band.currency != self.currency:
			frappe.msgprint(
				_("Rate Band {0} is in {1}; contract is in {2}. Band comparison is nominal.").format(
					band.name, band.currency, self.currency
				),
				indicator="orange",
			)
		self.band_min, self.band_max = flt(row.min_rate), flt(row.max_rate)
		self.band_position = rules.band_position(flt(self.agreed_rate), self.band_min, self.band_max)
		if self.band_position == "Below Minimum":
			frappe.msgprint(_("Agreed rate is below the band minimum of {0}.").format(self.band_min), indicator="orange", alert=True)
		elif self.band_position == "Above Maximum" and not (self.justification or "").strip():
			frappe.throw(_("Agreed rate is above the band maximum of {0}. A justification is required.").format(self.band_max))

	def before_submit(self):
		if not services.user_can_approve("Contract Approval"):
			frappe.throw(_("You are not an approver for project contracts."), frappe.PermissionError)
		if frappe.session.user == self.owner and frappe.session.user != "Administrator" and services.settings().enforce_segregation:
			frappe.throw(_("Segregation of duties: the person who prepared the contract cannot approve it."))
		self.approved_by = frappe.session.user
		self.approved_on = now_datetime()

	def before_cancel(self):
		used = frappe.db.count("Daily Work Order", {"project_contract": self.name, "docstatus": 1})
		if used:
			frappe.throw(_("{0} issued work orders use this contract.").format(used))


def average_paid(specialty, work_type):
	"""Average rate on issued work orders for the specialty/work type over the last 12 months (reference only)."""
	if not specialty or not work_type:
		return 0
	res = frappe.db.sql(
		"""
		select avg(dwo.rate)
		from `tabDaily Work Order` dwo
		join `tabFreelancer Profile` fp on fp.name = dwo.freelancer
		where dwo.docstatus = 1 and dwo.work_type = %s and fp.specialty = %s and dwo.work_date >= %s
		""",
		(work_type, specialty, add_months(today(), -12)),
	)
	return flt(res[0][0]) if res and res[0][0] else 0
