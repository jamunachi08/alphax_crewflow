# Copyright (c) 2026, AlphaX
# License: see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, getdate

from alphax_crewflow.crewflow.engine import rules


class ProjectBOQ(Document):
	def validate(self):
		codes = set()
		total = 0
		for item in self.items:
			if item.boq_code in codes:
				frappe.throw(_("BOQ Code {0} is duplicated.").format(item.boq_code))
			codes.add(item.boq_code)
			item.amount = flt(item.qty) * flt(item.client_rate)
			total += item.amount
		self.total_amount = total

		keys = set()
		for q in self.quotas:
			q.month_start = rules.month_start(getdate(q.month_start))
			if q.boq_code and q.boq_code not in codes:
				frappe.throw(_("Quota row {0}: BOQ Code {1} is not in the BOQ items.").format(q.idx, q.boq_code))
			if cint(q.quota_days) < 0:
				frappe.throw(_("Quota row {0}: days cannot be negative.").format(q.idx))
			key = (str(q.month_start), q.work_type, q.boq_code or "")
			if key in keys:
				frappe.throw(_("Quota row {0} duplicates another row for the same month, work type and BOQ code.").format(q.idx))
			keys.add(key)
