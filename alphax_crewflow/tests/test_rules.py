# Copyright (c) 2026, AlphaX
"""Pure-rule tests. Run with: python -m unittest alphax_crewflow.tests.test_rules (no site needed)."""

import unittest
from datetime import date, datetime

from alphax_crewflow.crewflow.engine import rules


class TestScoring(unittest.TestCase):
	def test_quality_bands(self):
		self.assertEqual(rules.quality_band_score(95), 5)
		self.assertEqual(rules.quality_band_score(90), 5)
		self.assertEqual(rules.quality_band_score(89.9), 4)
		self.assertEqual(rules.quality_band_score(70), 3)
		self.assertEqual(rules.quality_band_score(60), 2)
		self.assertEqual(rules.quality_band_score(59.9), 1)

	def test_acceptance(self):
		self.assertEqual(rules.acceptance_pct(40, 30), 75.0)
		self.assertEqual(rules.acceptance_pct(0, 0), 0.0)

	def test_weighted(self):
		self.assertEqual(rules.weighted_score(5, 5, 5, 5), 5.0)
		self.assertEqual(rules.weighted_score(4, 3, 5, 2), round((4 * 60 + 3 * 15 + 5 * 15 + 2 * 10) / 100, 2))

	def test_punctuality(self):
		sched = datetime(2026, 12, 1, 7, 0)
		due = datetime(2026, 12, 1, 22, 0)
		self.assertEqual(rules.punctuality_score(sched, datetime(2026, 12, 1, 7, 10), due, due), 5)
		self.assertEqual(rules.punctuality_score(sched, datetime(2026, 12, 1, 7, 40), due, due), 4)
		self.assertEqual(rules.punctuality_score(sched, datetime(2026, 12, 1, 9, 0), due, due), 3)
		self.assertEqual(rules.punctuality_score(sched, datetime(2026, 12, 1, 9, 0), due, datetime(2026, 12, 2, 1, 0)), 1)
		self.assertEqual(rules.punctuality_score(sched, None, due, due), 3)

	def test_qc_decision(self):
		self.assertEqual(rules.qc_decision(60, True), "Accepted")
		self.assertEqual(rules.qc_decision(59, True), "Rejected")
		self.assertEqual(rules.qc_decision(80, False), "Rejected")
		self.assertEqual(rules.qc_decision(40, False, partial_exception=True), "Accepted")


class TestLevel(unittest.TestCase):
	def test_pad(self):
		# 3 scores of 5 + 7 slots of initial 4 -> 4.3
		self.assertEqual(rules.rolling_level(4, [5, 5, 5], 10), 4.3)

	def test_hold(self):
		self.assertEqual(rules.rolling_level(4, [5, 5, 5], 10, "Hold initial level until window is full"), 4.0)

	def test_full_window(self):
		self.assertEqual(rules.rolling_level(4, [3] * 12, 10), 3.0)


class TestWorkload(unittest.TestCase):
	def test_below_min_average_uses_tolerance(self):
		# peers average 5 -> limit 8
		self.assertEqual(rules.workload_check(8, [4, 6])["status"], rules.OK)
		self.assertEqual(rules.workload_check(9, [4, 6])["status"], rules.BLOCK)

	def test_percentage_rule(self):
		# peers average 20 -> limit 26
		self.assertEqual(rules.workload_check(26, [20, 20])["status"], rules.OK)
		self.assertEqual(rules.workload_check(27, [20, 20])["status"], rules.BLOCK)

	def test_no_peers(self):
		self.assertEqual(rules.workload_check(50, [])["status"], rules.OK)


class TestQuotaAndBands(unittest.TestCase):
	def test_quota(self):
		self.assertEqual(rules.quota_check(7, 10)["status"], rules.OK)
		self.assertEqual(rules.quota_check(8, 10)["status"], rules.ALERT)
		self.assertEqual(rules.quota_check(10, 10)["status"], rules.ALERT)
		self.assertEqual(rules.quota_check(11, 10)["status"], rules.BLOCK)
		self.assertEqual(rules.quota_check(1, 0)["status"], rules.BLOCK)

	def test_band_position(self):
		self.assertEqual(rules.band_position(50, 100, 200), "Below Minimum")
		self.assertEqual(rules.band_position(150, 100, 200), "Within Band")
		self.assertEqual(rules.band_position(250, 100, 200), "Above Maximum")

	def test_po_role(self):
		args = (25000, "PM", 100000, "PD", "CEO")
		self.assertEqual(rules.po_required_role(25000, *args), "PM")
		self.assertEqual(rules.po_required_role(25001, *args), "PD")
		self.assertEqual(rules.po_required_role(100001, *args), "CEO")

	def test_months(self):
		self.assertEqual(rules.month_start(date(2026, 3, 17)), date(2026, 3, 1))
		self.assertEqual(rules.previous_month_start(date(2026, 1, 10)), date(2025, 12, 1))
		self.assertEqual(rules.next_month_start(date(2026, 12, 5)), date(2027, 1, 1))


class TestChecklistAndSignoff(unittest.TestCase):
	def test_checklist(self):
		self.assertIsNone(rules.checklist_score(0, 0))
		self.assertEqual(rules.checklist_score(4, 4), 5.0)
		self.assertEqual(rules.checklist_score(0, 4), 1.0)
		self.assertEqual(rules.checklist_score(3, 4), 4.0)

	def test_unsigned(self):
		steps = [
			{"step_name": "Coordination", "stage": "Receipt", "is_required": 1, "signed_by": None},
			{"step_name": "Production", "stage": "Issue", "is_required": 1, "signed_by": "a@x"},
			{"step_name": "Optional", "stage": "Receipt", "is_required": 0, "signed_by": None},
		]
		self.assertEqual(rules.unsigned_required(steps, "Receipt"), ["Coordination"])
		self.assertEqual(rules.unsigned_required(steps, "Issue"), [])


if __name__ == "__main__":
	unittest.main()
