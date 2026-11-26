"""Frappe-aware services for CrewFlow: data gathering around the pure rules in rules.py."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, get_datetime, getdate, today

from alphax_crewflow.crewflow.engine import rules

BLOCK = "block"
ALERT = "alert"


# ------------------------------------------------------------------ settings & roles
def settings():
	return frappe.get_cached_doc("CrewFlow Settings")


def weights():
	s = settings()
	return (
		flt(s.weight_quality),
		flt(s.weight_compliance),
		flt(s.weight_punctuality),
		flt(s.weight_manager),
	)


def quality_bands():
	rows = [(flt(r.min_pct), flt(r.score)) for r in settings().quality_bands]
	return rows or rules.DEFAULT_QUALITY_BANDS


def approver_roles(exception_type: str) -> set[str]:
	return {r.role for r in settings().exception_approvers if r.exception_type == exception_type}


def user_has_any_role(roles, user=None) -> bool:
	user = user or frappe.session.user
	if user == "Administrator":
		return True
	return bool(set(roles or []) & set(frappe.get_roles(user)))


def user_can_approve(exception_type: str, user=None) -> bool:
	return user_has_any_role(approver_roles(exception_type), user)


def users_with_role(role: str) -> list[str]:
	users = frappe.get_all("Has Role", filters={"role": role, "parenttype": "User"}, pluck="parent")
	if not users:
		return []
	return frappe.get_all("User", filters={"name": ("in", users), "enabled": 1, "user_type": "System User"}, pluck="name")


def approved_exception(exception_type: str, reference_doctype: str, reference_name: str | None):
	if not reference_name or reference_name.startswith("new-"):
		return None
	return frappe.db.get_value(
		"CrewFlow Exception",
		{
			"exception_type": exception_type,
			"reference_doctype": reference_doctype,
			"reference_name": reference_name,
			"docstatus": 1,
		},
		["name", "new_rate"],
		as_dict=True,
		order_by="approved_on desc",
	)


def notify(users, subject: str, doctype: str, name: str, message: str = ""):
	for user in set(u for u in users if u and u not in ("Administrator", "Guest")):
		frappe.get_doc(
			{
				"doctype": "Notification Log",
				"for_user": user,
				"type": "Alert",
				"subject": subject,
				"email_content": message or subject,
				"document_type": doctype,
				"document_name": name,
			}
		).insert(ignore_permissions=True)


def issue(severity: str, message: str, exception: str | None = None) -> dict:
	return {"severity": severity, "message": message, "exception": exception}


# ------------------------------------------------------------------ seasons
def resolve_season(work_date) -> str:
	d = getdate(work_date)
	cal = frappe.db.get_value("Season Calendar", {"calendar_year": d.year}, "name")
	if cal:
		seasons = frappe.get_all(
			"Season Calendar Period",
			filters={"parent": cal, "parenttype": "Season Calendar", "from_date": ("<=", d), "to_date": (">=", d)},
			pluck="season",
		)
		if seasons:
			return seasons[0]
	season = settings().default_season or frappe.db.get_value("Rate Season", {"is_default": 1}, "name")
	if not season:
		frappe.throw(_("No rate season covers {0}. Set a default Rate Season in CrewFlow Settings.").format(d))
	return season


# ------------------------------------------------------------------ rates
def resolve_rate(doc) -> tuple[float, str, str]:
	"""Return (rate, currency, source) for a Daily Work Order."""
	override = approved_exception("Rate Change", doc.doctype, doc.name)

	if doc.engagement_type == "Project Contract":
		pc = frappe.db.get_value(
			"Project Contract", doc.project_contract, ["agreed_rate", "currency", "docstatus"], as_dict=True
		)
		if not pc or pc.docstatus != 1:
			frappe.throw(_("Project Contract {0} must be approved (submitted).").format(doc.project_contract))
		rate, currency, source = flt(pc.agreed_rate), pc.currency, _("Project Contract {0}").format(doc.project_contract)
	else:
		card_name = frappe.db.get_value("Framework Agreement", doc.framework_agreement, "rate_card")
		card = frappe.get_doc("Rate Card", card_name)
		if not card.is_active:
			frappe.throw(_("Rate Card {0} is inactive.").format(card_name))
		wd = getdate(doc.work_date)
		if (card.valid_from and wd < getdate(card.valid_from)) or (card.valid_to and wd > getdate(card.valid_to)):
			frappe.throw(_("Rate Card {0} is not valid on {1}.").format(card_name, wd))
		requires_eq = cint(frappe.db.get_value("Work Type", doc.work_type, "requires_equipment"))
		if requires_eq and not doc.equipment_type:
			frappe.throw(_("Work Type {0} is priced by equipment. Select the equipment.").format(doc.work_type))
		match = None
		for row in card.items:
			if row.work_type != doc.work_type or row.season != doc.season:
				continue
			if not rules.level_in_range(flt(doc.freelancer_level), flt(row.level_from), flt(row.level_to)):
				continue
			if requires_eq and (row.equipment_type or "") != (doc.equipment_type or ""):
				continue
			match = row
			break
		if not match:
			frappe.throw(
				_("No rate in Rate Card {0} for Work Type {1}, Season {2}, Level {3}{4}.").format(
					card_name,
					doc.work_type,
					doc.season,
					flt(doc.freelancer_level, 2),
					(", " + _("Equipment") + " " + doc.equipment_type) if requires_eq else "",
				)
			)
		rate, currency, source = flt(match.rate), card.currency, _("Rate Card {0}").format(card_name)

	if override and override.new_rate:
		return flt(override.new_rate), currency, _("Rate Change exception {0}").format(override.name)
	return rate, currency, source


# ------------------------------------------------------------------ work-order checks
def work_order_issues(doc) -> list[dict]:
	"""Evaluate every issuance rule. Returns a list of issues (severity, message, exception)."""
	s = settings()
	out: list[dict] = []
	wd = getdate(doc.work_date)

	# 1. eligibility
	status = frappe.db.get_value("Freelancer Profile", doc.freelancer, "status")
	if status != "Active":
		out.append(issue(BLOCK, _("Freelancer {0} is {1}. Only a reinstatement can re-activate them.").format(
			doc.freelancer_name or doc.freelancer, _(status))))

	# 2. unavailability
	unavailable = frappe.db.get_value(
		"Freelancer Unavailability",
		{"freelancer": doc.freelancer, "from_date": ("<=", wd), "to_date": (">=", wd)},
		"name",
	)
	if unavailable:
		out.append(issue(BLOCK, _("Freelancer is marked unavailable on {0} ({1}).").format(wd, unavailable)))

	# 3. double booking
	clash = frappe.db.get_value(
		"Daily Work Order",
		{"freelancer": doc.freelancer, "work_date": wd, "docstatus": 1, "name": ("!=", doc.name)},
		["name", "project"],
		as_dict=True,
	)
	if clash:
		out.append(issue(BLOCK, _("Double booking: freelancer already has {0} on project {1} for {2}.").format(
			clash.name, clash.project, wd)))

	# 4. post-facto issue
	if getdate(today()) > wd:
		out.append(issue(BLOCK, _("Work date {0} is in the past. Work Orders must be issued before the work.").format(wd),
			"Post-facto Issue"))

	# 5. engagement validity
	if doc.engagement_type == "Framework" and doc.framework_agreement:
		out.extend(_framework_issues(doc, s, wd))
	elif doc.engagement_type == "Project Contract" and doc.project_contract:
		out.extend(_contract_issues(doc, wd))

	# 6. quota
	out.extend(_quota_issues(doc, s, wd))

	return out


def _framework_issues(doc, s, wd) -> list[dict]:
	out = []
	fa = frappe.get_doc("Framework Agreement", doc.framework_agreement)
	if fa.project != doc.project:
		out.append(issue(BLOCK, _("Framework Agreement {0} belongs to project {1}.").format(fa.name, fa.project)))
	if fa.status == "Closed" or wd < getdate(fa.start_date) or wd > getdate(fa.end_date):
		out.append(issue(BLOCK, _("Framework Agreement {0} does not cover {1}.").format(fa.name, wd)))
	elif (getdate(fa.end_date) - wd).days <= cint(fa.expiry_alert_days):
		out.append(issue(ALERT, _("Framework Agreement {0} expires on {1}.").format(fa.name, fa.end_date)))

	members = [m for m in fa.members if m.is_active]
	if doc.freelancer not in [m.freelancer for m in members]:
		out.append(issue(BLOCK, _("Freelancer is not an active member of Framework Agreement {0}.").format(fa.name)))
		return out

	if not cint(s.enable_workload_rule):
		return out

	peers = [m.freelancer for m in members if m.freelancer != doc.freelancer]
	if peers:
		peers = frappe.get_all(
			"Freelancer Profile", filters={"name": ("in", peers), "status": "Active"}, pluck="name"
		)
	conditions = "framework_agreement = %(fa)s and docstatus = 1 and name != %(me)s"
	values = {"fa": fa.name, "me": doc.name or ""}
	if s.workload_basis == "Calendar month":
		ms = rules.month_start(wd)
		conditions += " and work_date between %(ms)s and %(me_end)s"
		values.update({"ms": ms, "me_end": add_days(rules.next_month_start(ms), -1)})
	counts = dict(
		frappe.db.sql(
			f"select freelancer, count(name) from `tabDaily Work Order` where {conditions} group by freelancer",
			values,
		)
	)
	own_after = cint(counts.get(doc.freelancer, 0)) + 1
	res = rules.workload_check(
		own_after,
		[cint(counts.get(p, 0)) for p in peers],
		flt(s.workload_pct),
		flt(s.workload_min_average),
		flt(s.workload_fixed_tolerance),
	)
	if res["status"] == rules.BLOCK:
		out.append(issue(BLOCK, _("Workload rule: this would be day {0} for the freelancer; limit is {1} (peer average {2}).").format(
			own_after, res["limit"], res["average"]), "Workload Overrun"))
	return out


def _contract_issues(doc, wd) -> list[dict]:
	out = []
	pc = frappe.db.get_value(
		"Project Contract", doc.project_contract,
		["project", "freelancer", "valid_from", "valid_to", "docstatus", "work_type"], as_dict=True,
	)
	if not pc or pc.docstatus != 1:
		out.append(issue(BLOCK, _("Project Contract {0} is not approved.").format(doc.project_contract)))
		return out
	if pc.project != doc.project or pc.freelancer != doc.freelancer:
		out.append(issue(BLOCK, _("Project Contract {0} is for a different project or freelancer.").format(doc.project_contract)))
	if pc.work_type and pc.work_type != doc.work_type:
		out.append(issue(BLOCK, _("Project Contract {0} covers Work Type {1}.").format(doc.project_contract, pc.work_type)))
	if wd < getdate(pc.valid_from) or wd > getdate(pc.valid_to):
		out.append(issue(BLOCK, _("Project Contract {0} is not valid on {1}.").format(doc.project_contract, wd)))
	return out


def find_quota_row(project: str, work_type: str, wd, boq_code: str | None = None, project_boq: str | None = None):
	boq = project_boq or frappe.db.get_value("Project BOQ", {"project": project}, "name")
	if not boq:
		return None, None
	ms = rules.month_start(getdate(wd))
	rows = frappe.get_all(
		"Project BOQ Quota",
		filters={"parent": boq, "parenttype": "Project BOQ", "month_start": ms, "work_type": work_type},
		fields=["name", "boq_code", "quota_days", "freelancers_per_day"],
	)
	specific = [r for r in rows if r.boq_code and r.boq_code == boq_code]
	generic = [r for r in rows if not r.boq_code]
	row = (specific or generic or [None])[0]
	return boq, row


def quota_consumed(project: str, work_type: str, wd, boq_code: str | None, exclude: str | None = None,
		include_rejected: bool = True) -> int:
	ms = rules.month_start(getdate(wd))
	filters = {
		"project": project,
		"work_type": work_type,
		"docstatus": 1,
		"work_date": ("between", [ms, add_days(rules.next_month_start(ms), -1)]),
	}
	if boq_code:
		filters["boq_code"] = boq_code
	if exclude:
		filters["name"] = ("!=", exclude)
	if not include_rejected:
		filters["qc_result"] = ("!=", "Rejected")
	return frappe.db.count("Daily Work Order", filters)


def _quota_issues(doc, s, wd) -> list[dict]:
	out = []
	boq, row = find_quota_row(doc.project, doc.work_type, wd, doc.boq_code, doc.project_boq)
	if not row:
		if cint(s.require_quota):
			out.append(issue(BLOCK, _("No shooting-day quota for {0} / {1} in {2}.").format(
				doc.project, doc.work_type, rules.month_start(wd).strftime("%b %Y")), "Quota Overrun"))
		return out

	consumed = quota_consumed(
		doc.project, doc.work_type, wd, row.boq_code, exclude=doc.name,
		include_rejected=bool(cint(s.rejected_days_consume_quota)),
	)
	res = rules.quota_check(consumed + 1, cint(row.quota_days), flt(s.quota_alert_pct))
	if res["status"] == rules.BLOCK:
		out.append(issue(BLOCK, _("Quota exhausted: {0} of {1} days used this month for {2}.").format(
			consumed, row.quota_days, doc.work_type), "Quota Overrun"))
	elif res["status"] == rules.ALERT:
		out.append(issue(ALERT, _("Quota at {0}% ({1} of {2} days) for {3} this month.").format(
			res["pct"], consumed + 1, row.quota_days, doc.work_type)))

	if cint(row.freelancers_per_day):
		same_day = frappe.db.count(
			"Daily Work Order",
			{"project": doc.project, "work_type": doc.work_type, "work_date": wd, "docstatus": 1, "name": ("!=", doc.name)},
		)
		if same_day + 1 > cint(row.freelancers_per_day):
			out.append(issue(ALERT, _("{0} freelancers already booked for {1} on {2}; BOQ plans {3} per day.").format(
				same_day, doc.work_type, wd, row.freelancers_per_day)))
	return out


# ------------------------------------------------------------------ rating
def apply_rating(doc):
	"""Create the rating log for a QC-approved work order and refresh the freelancer's level/status."""
	frappe.get_doc(
		{
			"doctype": "Freelancer Rating Log",
			"freelancer": doc.freelancer,
			"work_order": doc.name,
			"work_date": doc.work_date,
			"project": doc.project,
			"qc_result": doc.qc_result,
			"quality_score": doc.quality_score,
			"compliance_score": doc.compliance_score,
			"punctuality_score": doc.punctuality_score,
			"manager_score": doc.manager_score,
			"weighted_score": doc.weighted_score,
		}
	).insert(ignore_permissions=True)
	level = recompute_level(doc.freelancer)
	frappe.db.set_value(
		"Freelancer Rating Log", {"work_order": doc.name}, "level_after", level, update_modified=False
	)
	check_suspension(doc.freelancer, doc.work_date)
	return level


def recompute_level(freelancer: str) -> float:
	s = settings()
	fp = frappe.get_doc("Freelancer Profile", freelancer)
	window = cint(s.rating_window) or 10
	scores = frappe.get_all(
		"Freelancer Rating Log",
		filters={"freelancer": freelancer},
		order_by="work_date desc, creation desc",
		limit_page_length=window,
		pluck="weighted_score",
	)
	level = rules.rolling_level(flt(fp.initial_level), [flt(x) for x in scores], window, s.initial_level_method or "Pad")
	updates = {
		"current_level": level,
		"rated_orders": frappe.db.count("Freelancer Rating Log", {"freelancer": freelancer}),
		"last_rated_on": today(),
	}
	if fp.status == "Active" and level < flt(s.min_level):
		updates["status"] = "Blocked"
		updates["status_reason"] = _("Auto-blocked on {0}: level {1} below minimum {2}.").format(today(), level, s.min_level)
		_notify_status_change(fp, updates["status_reason"])
	fp.db_set(updates)
	return level


def check_suspension(freelancer: str, work_date):
	s = settings()
	limit = cint(s.suspension_rejections)
	if not limit:
		return
	ms = rules.month_start(getdate(work_date))
	rejected = frappe.db.count(
		"Daily Work Order",
		{
			"freelancer": freelancer,
			"docstatus": 1,
			"qc_result": "Rejected",
			"work_date": ("between", [ms, add_days(rules.next_month_start(ms), -1)]),
		},
	)
	status = frappe.db.get_value("Freelancer Profile", freelancer, "status")
	if rejected >= limit and status == "Active":
		reason = _("Auto-suspended on {0}: {1} rejected work orders in {2}.").format(today(), rejected, ms.strftime("%b %Y"))
		frappe.db.set_value("Freelancer Profile", freelancer, {"status": "Suspended", "status_reason": reason})
		_notify_status_change(frappe.get_doc("Freelancer Profile", freelancer), reason)


def _notify_status_change(fp, reason):
	users = set()
	for role in approver_roles("Reinstatement"):
		users.update(users_with_role(role))
	notify(users, _("Freelancer {0}: {1}").format(fp.freelancer_name or fp.name, reason), "Freelancer Profile", fp.name)


# ------------------------------------------------------------------ helpers
def combine(work_date, time_value):
	if not time_value:
		return None
	return get_datetime(f"{getdate(work_date)} {time_value}")
