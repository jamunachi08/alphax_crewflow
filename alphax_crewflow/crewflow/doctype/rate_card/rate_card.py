# Copyright (c) 2026, AlphaX
# License: see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate

from alphax_crewflow.crewflow.engine import rules


class RateCard(Document):
	def validate(self):
		if self.valid_from and self.valid_to and getdate(self.valid_from) > getdate(self.valid_to):
			frappe.throw(_("Valid From cannot be after Valid To."))
		seen = []
		for row in self.items:
			if flt(row.level_from) > flt(row.level_to):
				frappe.throw(_("Row {0}: Level From cannot exceed Level To.").format(row.idx))
			if flt(row.rate) <= 0:
				frappe.throw(_("Row {0}: rate must be positive.").format(row.idx))
			key = (row.work_type, row.season, row.equipment_type or "")
			for other_key, lf, lt, idx in seen:
				if other_key == key and rules.ranges_overlap(flt(row.level_from), flt(row.level_to), lf, lt):
					frappe.throw(_("Rows {0} and {1} overlap for the same work type, season and equipment.").format(idx, row.idx))
			seen.append((key, flt(row.level_from), flt(row.level_to), row.idx))
