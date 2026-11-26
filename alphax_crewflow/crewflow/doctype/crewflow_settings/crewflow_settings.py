# Copyright (c) 2026, AlphaX
# License: see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, getdate

from alphax_crewflow.crewflow.engine import rules


class CrewFlowSettings(Document):
	def validate(self):
		total = flt(self.weight_quality) + flt(self.weight_compliance) + flt(self.weight_punctuality) + flt(self.weight_manager)
		if abs(total - 100) > 0.01:
			frappe.throw(_("Rating weights must total 100%. Current total: {0}%").format(total))
		if not 1 <= flt(self.min_level) <= 5:
			frappe.throw(_("Minimum Contracting Level must be between 1 and 5."))
		if not 1 <= cint(self.payment_day) <= 28:
			frappe.throw(_("Payment Day must be between 1 and 28."))
		if flt(self.po_tier1_limit) > flt(self.po_tier2_limit):
			frappe.throw(_("Tier 1 limit cannot exceed Tier 2 limit."))
		for b in self.quality_bands:
			if not 1 <= flt(b.score) <= 5:
				frappe.throw(_("Quality band row {0}: score must be 1-5.").format(b.idx))

	def on_update(self):
		frappe.clear_document_cache(self.doctype, self.name)


@frappe.whitelist()
def run_freelancer_invoicing(month=None):
	from alphax_crewflow.crewflow.integrations.invoicing import generate_freelancer_invoices

	frappe.only_for(["CrewFlow Finance", "CrewFlow Admin", "System Manager"])
	period = rules.month_start(getdate(month)) if month else None
	return generate_freelancer_invoices(period)
