# Copyright (c) 2026, AlphaX
# License: see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint


class WorkOrderTemplate(Document):
	def validate(self):
		for row in self.outputs:
			if cint(row.min_duration_sec) and cint(row.max_duration_sec) and cint(row.min_duration_sec) > cint(row.max_duration_sec):
				frappe.throw(_("Output row {0}: minimum duration exceeds maximum.").format(row.idx))
			for f in ("delivered_qty", "accepted_qty", "delivered_size_gb", "delivered_formats"):
				row.set(f, None)
