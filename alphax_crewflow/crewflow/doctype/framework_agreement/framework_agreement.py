# Copyright (c) 2026, AlphaX
# License: see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today


class FrameworkAgreement(Document):
	def validate(self):
		if getdate(self.start_date) > getdate(self.end_date):
			frappe.throw(_("Start Date cannot be after End Date."))
		if self.client_contract:
			so = frappe.db.get_value("Sales Order", self.client_contract, ["customer", "project"], as_dict=True)
			if so and not self.customer:
				self.customer = so.customer
		seen = set()
		for m in self.members:
			if m.freelancer in seen:
				frappe.throw(_("Freelancer {0} is listed twice.").format(m.freelancer_name or m.freelancer))
			seen.add(m.freelancer)
			if not m.joined_on:
				m.joined_on = today()
		self.status = compute_status(self)
		before = self.get_doc_before_save()
		if before and getdate(before.end_date) != getdate(self.end_date):
			self.expiry_alert_sent = 0

	@frappe.whitelist()
	def close_agreement(self):
		self.db_set("status", "Closed")
		return self.status


def compute_status(doc):
	if doc.status == "Closed":
		return "Closed"
	t = getdate(today())
	if t > getdate(doc.end_date):
		return "Expired"
	if t >= getdate(doc.start_date):
		return "Active"
	return "Draft"
