# Copyright (c) 2026, AlphaX
# License: see license.txt

from datetime import date

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, getdate


class SeasonCalendar(Document):
	def validate(self):
		y = cint(self.calendar_year)
		if not 2000 <= y <= 2100:
			frappe.throw(_("Enter a valid Gregorian year."))
		rows = sorted(self.periods, key=lambda r: getdate(r.from_date))
		for r in rows:
			if getdate(r.from_date) > getdate(r.to_date):
				frappe.throw(_("Row {0}: From Date is after To Date.").format(r.idx))
			if getdate(r.from_date).year != y or getdate(r.to_date).year != y:
				frappe.throw(_("Row {0}: dates must fall within {1}. Split periods that cross the year end.").format(r.idx, y))
		for a, b in zip(rows, rows[1:]):
			if getdate(b.from_date) <= getdate(a.to_date):
				frappe.throw(_("Season periods overlap: rows {0} and {1}.").format(a.idx, b.idx))

	@frappe.whitelist()
	def suggest_hijri_periods(self):
		"""Replace Hijri-sourced rows with periods computed from Hijri-based Rate Seasons."""
		try:
			from hijridate import Gregorian, Hijri
		except ImportError:
			frappe.throw(_("The hijridate package is not installed on this site."))

		y = cint(self.calendar_year)
		year_start, year_end = date(y, 1, 1), date(y, 12, 31)
		h_first = Gregorian(y, 1, 1).to_hijri().year
		h_last = Gregorian(y, 12, 31).to_hijri().year

		self.periods = [r for r in self.periods if r.source != "Hijri"]
		for season in frappe.get_all(
			"Rate Season",
			filters={"hijri_based": 1},
			fields=["name", "hijri_start_month", "hijri_start_day", "hijri_end_month", "hijri_end_day"],
		):
			for hy in range(h_first, h_last + 1):
				start = _hijri_to_date(Hijri, hy, season.hijri_start_month, season.hijri_start_day)
				end_year = hy if cint(season.hijri_end_month) >= cint(season.hijri_start_month) else hy + 1
				end = _hijri_to_date(Hijri, end_year, season.hijri_end_month, season.hijri_end_day)
				start, end = max(start, year_start), min(end, year_end)
				if start <= end:
					self.append("periods", {"season": season.name, "from_date": start, "to_date": end, "source": "Hijri"})
		self.periods.sort(key=lambda r: getdate(r.from_date))
		for i, r in enumerate(self.periods, 1):
			r.idx = i
		self.save()
		return len(self.periods)


def _hijri_to_date(Hijri, year, month, day):
	month = cint(month)
	length = Hijri(year, month, 1).month_length()
	g = Hijri(year, month, min(cint(day), length)).to_gregorian()
	return date(g.year, g.month, g.day)
