"""Pure business rules for CrewFlow.

No Frappe imports here: every function is deterministic and unit-testable.
Controllers and services gather data and call these functions.
"""

from __future__ import annotations

import math
from datetime import date, datetime

OK = "ok"
ALERT = "alert"
BLOCK = "block"


# ------------------------------------------------------------------ dates
def month_start(d: date) -> date:
	return date(d.year, d.month, 1)


def previous_month_start(d: date) -> date:
	if d.month == 1:
		return date(d.year - 1, 12, 1)
	return date(d.year, d.month - 1, 1)


def next_month_start(d: date) -> date:
	if d.month == 12:
		return date(d.year + 1, 1, 1)
	return date(d.year, d.month + 1, 1)


# ------------------------------------------------------------------ ranges
def level_in_range(level: float, level_from: float, level_to: float) -> bool:
	"""Inclusive range test with a tiny tolerance for float precision."""
	eps = 1e-9
	return (level_from - eps) <= level <= (level_to + eps)


def ranges_overlap(a_from: float, a_to: float, b_from: float, b_to: float) -> bool:
	return a_from <= b_to and b_from <= a_to


# ------------------------------------------------------------------ scoring
DEFAULT_QUALITY_BANDS = [(90, 5), (80, 4), (70, 3), (60, 2), (0, 1)]


def acceptance_pct(delivered: int, accepted: int) -> float:
	if not delivered:
		return 0.0
	return round(100.0 * accepted / delivered, 2)


def quality_band_score(pct: float, bands: list[tuple[float, float]] | None = None) -> float:
	"""bands: list of (min_pct, score). Highest min_pct that pct reaches wins."""
	bands = sorted(bands or DEFAULT_QUALITY_BANDS, key=lambda b: b[0], reverse=True)
	for min_pct, score in bands:
		if pct >= min_pct:
			return float(score)
	return float(bands[-1][1]) if bands else 1.0


def punctuality_score(
	scheduled_checkin: datetime | None,
	actual_checkin: datetime | None,
	delivery_due: datetime | None,
	delivered_on: datetime | None,
	grace_minutes: int = 15,
	step_minutes: int = 30,
	max_checkin_penalty: float = 2,
	late_delivery_penalty: float = 2,
) -> float:
	"""Start at 5; deduct for late check-in (per step beyond grace, capped) and late delivery.
	Missing check-in counts as the maximum check-in penalty. Floor is 1."""
	score = 5.0
	if scheduled_checkin and actual_checkin:
		late = (actual_checkin - scheduled_checkin).total_seconds() / 60.0 - (grace_minutes or 0)
		if late > 0:
			steps = math.ceil(late / max(step_minutes or 1, 1))
			score -= min(steps, max_checkin_penalty or 0)
	elif scheduled_checkin and not actual_checkin:
		score -= max_checkin_penalty or 0
	if delivery_due and delivered_on and delivered_on > delivery_due:
		score -= late_delivery_penalty or 0
	return max(1.0, min(5.0, score))


def clamp_score(value: float | None) -> float:
	if value is None:
		return 1.0
	return max(1.0, min(5.0, float(value)))


def weighted_score(quality: float, compliance: float, punctuality: float, manager: float,
		weights: tuple[float, float, float, float] = (60, 15, 15, 10)) -> float:
	total = sum(weights)
	if not total:
		raise ValueError("Rating weights must not all be zero")
	value = (quality * weights[0] + compliance * weights[1] + punctuality * weights[2] + manager * weights[3]) / total
	return round(value, 2)


def rolling_level(initial_level: float, recent_scores: list[float], window: int = 10,
		method: str = "Pad with initial level") -> float:
	"""recent_scores: newest first. Returns the freelancer level.

	- Pad with initial level: missing slots in the window are filled with the initial level.
	- Hold initial level until window is full: initial level is used until `window` scores exist.
	"""
	window = max(int(window or 1), 1)
	scores = list(recent_scores[:window])
	if len(scores) >= window:
		return round(sum(scores) / window, 2)
	if method.startswith("Hold"):
		return round(float(initial_level), 2)
	padded = scores + [float(initial_level)] * (window - len(scores))
	return round(sum(padded) / window, 2)


# ------------------------------------------------------------------ workload balance
def workload_check(own_days_after: float, others_days: list[float], pct: float = 30,
		min_average: float = 10, fixed_tolerance: float = 3) -> dict:
	"""Return dict(status, average, limit). `others_days` excludes the freelancer and any
	blocked/inactive peers. No peers -> always ok."""
	if not others_days:
		return {"status": OK, "average": 0.0, "limit": None}
	avg = sum(others_days) / len(others_days)
	if avg >= (min_average or 0):
		limit = avg * (1 + (pct or 0) / 100.0)
	else:
		limit = avg + (fixed_tolerance or 0)
	status = BLOCK if own_days_after > limit + 1e-9 else OK
	return {"status": status, "average": round(avg, 2), "limit": round(limit, 2)}


# ------------------------------------------------------------------ quota
def quota_check(consumed_after: int, quota_days: int, alert_pct: float = 80) -> dict:
	if not quota_days:
		return {"status": BLOCK, "pct": None}
	pct = 100.0 * consumed_after / quota_days
	if consumed_after > quota_days:
		status = BLOCK
	elif pct >= (alert_pct or 100):
		status = ALERT
	else:
		status = OK
	return {"status": status, "pct": round(pct, 1)}


# ------------------------------------------------------------------ rate bands
def band_position(rate: float, min_rate: float | None, max_rate: float | None) -> str:
	if min_rate is None and max_rate is None:
		return ""
	if min_rate is not None and rate < min_rate:
		return "Below Minimum"
	if max_rate is not None and rate > max_rate:
		return "Above Maximum"
	return "Within Band"


# ------------------------------------------------------------------ purchase order approval
def po_required_role(amount: float, tier1_limit: float, tier1_role: str | None,
		tier2_limit: float, tier2_role: str | None, tier3_role: str | None) -> str | None:
	if amount <= (tier1_limit or 0):
		return tier1_role
	if amount <= (tier2_limit or 0):
		return tier2_role
	return tier3_role


# ------------------------------------------------------------------ QC decision
def qc_decision(acceptance: float, min_output_met: bool, threshold: float = 60,
		partial_exception: bool = False) -> str:
	if acceptance >= threshold and min_output_met:
		return "Accepted"
	if partial_exception:
		return "Accepted"
	return "Rejected"


# ------------------------------------------------------------------ checklist compliance
def checklist_score(compliant: int, total: int) -> float | None:
	"""Map share of compliant checklist items to a 1-5 score. None when there is no checklist."""
	if not total:
		return None
	return round(1 + 4.0 * max(0, min(compliant, total)) / total, 2)


def unsigned_required(steps: list[dict], stage: str) -> list[str]:
	"""Names of required sign-off steps of a stage that have no signature."""
	return [s["step_name"] for s in steps if s.get("stage") == stage and s.get("is_required") and not s.get("signed_by")]
