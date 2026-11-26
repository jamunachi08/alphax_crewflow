# Copyright (c) 2026, AlphaX
# License: see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate

from alphax_crewflow.crewflow.engine import rules


class RateBand(Document):
	def validate(self):
		if self.valid_from and self.valid_to and getdate(self.valid_from) > getdate(self.valid_to):
			frappe.throw(_("Valid From cannot be after Valid To."))
		seen = []
		for row in self.items:
			if flt(row.level_from) > flt(row.level_to):
				frappe.throw(_("Row {0}: Level From cannot exceed Level To.").format(row.idx))
			if flt(row.min_rate) > flt(row.max_rate):
				frappe.throw(_("Row {0}: Minimum Rate cannot exceed Maximum Rate.").format(row.idx))
			key = (row.specialty, row.work_type)
			for other_key, lf, lt, idx in seen:
				if other_key == key and rules.ranges_overlap(flt(row.level_from), flt(row.level_to), lf, lt):
					frappe.throw(_("Rows {0} and {1} overlap for the same specialty and task type.").format(idx, row.idx))
			seen.append((key, flt(row.level_from), flt(row.level_to), row.idx))


def find_band(specialty, work_type, level, on_date=None, rate_band=None):
	"""Return (band_name, row) for the first active band matching specialty/work type/level."""
	filters = {"is_active": 1}
	if rate_band:
		filters = {"name": rate_band}
	for name in frappe.get_all("Rate Band", filters=filters, order_by="creation desc", pluck="name"):
		band = frappe.get_doc("Rate Band", name)
		if on_date and (
			(band.valid_from and getdate(on_date) < getdate(band.valid_from))
			or (band.valid_to and getdate(on_date) > getdate(band.valid_to))
		):
			continue
		for row in band.items:
			if row.specialty == specialty and row.work_type == work_type and rules.level_in_range(
				flt(level), flt(row.level_from), flt(row.level_to)
			):
				return band, row
	return None, None
