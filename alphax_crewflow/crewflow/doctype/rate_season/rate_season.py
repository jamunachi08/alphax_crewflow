# Copyright (c) 2026, AlphaX
# License: see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint


class RateSeason(Document):
	def validate(self):
		if self.hijri_based:
			for f, hi in (("hijri_start_month", 12), ("hijri_end_month", 12), ("hijri_start_day", 30), ("hijri_end_day", 30)):
				if not 1 <= cint(self.get(f)) <= hi:
					frappe.throw(_("{0} must be between 1 and {1}.").format(self.meta.get_label(f), hi))
		if self.is_default:
			frappe.db.set_value("Rate Season", {"is_default": 1, "name": ("!=", self.name)}, "is_default", 0)
