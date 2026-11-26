# Copyright (c) 2026, AlphaX
# License: see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate


class FreelancerUnavailability(Document):
	def validate(self):
		if getdate(self.from_date) > getdate(self.to_date):
			frappe.throw(_("From Date cannot be after To Date."))
		booked = frappe.get_all(
			"Daily Work Order",
			filters={
				"freelancer": self.freelancer,
				"docstatus": 1,
				"work_date": ("between", [self.from_date, self.to_date]),
			},
			pluck="name",
		)
		if booked:
			frappe.msgprint(
				_("Freelancer already has issued work orders in this period: {0}").format(", ".join(booked)),
				indicator="orange",
			)
