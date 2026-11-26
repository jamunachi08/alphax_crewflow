# Copyright (c) 2026, AlphaX
# License: see license.txt

import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_to_date, cint, flt, get_datetime, getdate, now_datetime

from alphax_crewflow.crewflow.engine import rules, services

ROLE_ADMIN = "CrewFlow Admin"
ROLE_COORD = "CrewFlow Coordinator"
ROLE_REVIEW = "CrewFlow Review Officer"
ROLE_PM = "CrewFlow Project Manager"
ROLE_PD = "CrewFlow Projects Director"
ROLE_EXEC = "CrewFlow Executive"

FIELD_ROLES = [ROLE_COORD, ROLE_REVIEW, ROLE_PM, ROLE_PD, ROLE_EXEC, ROLE_ADMIN]
QC_RECORD_ROLES = [ROLE_REVIEW, ROLE_ADMIN]
QC_APPROVE_ROLES = [ROLE_PM, ROLE_PD, ROLE_EXEC, ROLE_ADMIN]
KEY_FIELDS = ("project", "freelancer", "work_date", "work_type", "framework_agreement", "project_contract", "equipment_type")


class DailyWorkOrder(Document):
	# ------------------------------------------------------------------ lifecycle
	def validate(self):
		if self.docstatus == 0:
			self.status = "Draft"
		self._validate_basics()
		self._set_context()
		self._set_rate()
		self._apply_template()
		self._init_signoffs()
		self._reset_issue_signoffs_on_change()
		if getattr(self, "_action", None) != "submit":
			self._show_issues(services.work_order_issues(self), enforce=False)

	def before_submit(self):
		# serialize issuance per freelancer to stop concurrent double booking
		frappe.db.sql("select name from `tabFreelancer Profile` where name = %s for update", self.freelancer)
		self._set_context()
		self._set_rate()
		self._require_signoffs("Issue")
		used = self._show_issues(services.work_order_issues(self), enforce=True)
		self.exceptions_used = "\n".join(used) if used else None
		self.status = "Issued"
		self.issued_by = frappe.session.user
		self.issued_on = now_datetime()

	def before_cancel(self):
		if self.status not in ("Issued",):
			frappe.throw(
				_("Only Issued work orders can be cancelled (before execution). This one is {0}.").format(_(self.status))
			)
		if not self.cancellation_reason:
			frappe.throw(_("Enter a Cancellation Reason before cancelling."))

	def on_cancel(self):
		self.db_set("status", "Cancelled")

	# ------------------------------------------------------------------ internals
	def _validate_basics(self):
		if self.engagement_type == "Framework":
			self.project_contract = None
		else:
			self.framework_agreement = None
		if self.delivery_due and getdate(self.delivery_due) < getdate(self.work_date):
			frappe.throw(_("Delivery Due cannot be before the Work Date."))
		if self.work_zone:
			zone_project = frappe.db.get_value("Work Zone", self.work_zone, "project")
			if zone_project and zone_project != self.project:
				frappe.throw(_("Work Zone {0} belongs to project {1}.").format(self.work_zone, zone_project))
		if self.boq_code:
			boq = self.project_boq or frappe.db.get_value("Project BOQ", {"project": self.project}, "name")
			if not boq or not frappe.db.exists(
				"Project BOQ Item", {"parent": boq, "parenttype": "Project BOQ", "boq_code": self.boq_code}
			):
				frappe.throw(_("BOQ Code {0} is not in the project's BOQ.").format(self.boq_code))
			self.project_boq = boq
		elif not self.project_boq:
			self.project_boq = frappe.db.get_value("Project BOQ", {"project": self.project}, "name")

	def _set_context(self):
		self.freelancer_level = flt(frappe.db.get_value("Freelancer Profile", self.freelancer, "current_level"))
		self.season = services.resolve_season(self.work_date)

	def _set_rate(self):
		rate, currency, source = services.resolve_rate(self)
		self.rate = rate
		self.currency = currency
		self.rate_source = source

	def _apply_template(self):
		if not self.work_order_template:
			self.work_order_template = frappe.db.get_value("Work Type", self.work_type, "default_template")
		if self.work_order_template and not self.outputs:
			tpl = frappe.get_doc("Work Order Template", self.work_order_template)
			for o in tpl.outputs:
				self.append(
					"outputs",
					{
						f: o.get(f)
						for f in ("output_type", "unit", "min_qty", "file_format", "resolution", "min_duration_sec", "max_duration_sec")
					},
				)
			if not self.checks:
				for c in tpl.checks:
					self.append("checks", {"check_item": c.check_item, "check_item_ar": c.check_item_ar})
			if not self.instructions:
				self.instructions = tpl.instructions
			if tpl.delivery_method:
				self.delivery_method = tpl.delivery_method
			if not self.delivery_due and cint(tpl.delivery_hours):
				self.delivery_due = add_to_date(get_datetime(str(getdate(self.work_date))), hours=cint(tpl.delivery_hours))
		if not self.outputs:
			wt = frappe.db.get_value("Work Type", self.work_type, ["output_unit", "default_min_output"], as_dict=True)
			if wt and (wt.output_unit or wt.default_min_output):
				self.append(
					"outputs",
					{"output_type": wt.output_unit or self.work_type, "unit": wt.output_unit, "min_qty": wt.default_min_output},
				)

	def _init_signoffs(self):
		if self.is_new():
			for row in self.sign_offs:
				row.signed_by = row.signed_on = None
		if self.docstatus != 0 or self.sign_offs:
			return
		for step in services.settings().get("signoff_steps") or []:
			self.append(
				"sign_offs",
				{"step_name": step.step_name, "stage": step.stage, "role": step.role, "is_required": step.is_required},
			)

	def _reset_issue_signoffs_on_change(self):
		before = self.get_doc_before_save()
		if not before or self.docstatus != 0:
			return
		# signatures come only from sign_off(); never trust values posted by the client
		stored = {r.name: r for r in before.get("sign_offs") or []}
		for row in self.sign_offs:
			prev = stored.get(row.name)
			row.signed_by = prev.signed_by if prev else None
			row.signed_on = prev.signed_on if prev else None
		if any(str(before.get(f) or "") != str(self.get(f) or "") for f in KEY_FIELDS):
			for row in self.sign_offs:
				if row.stage == "Issue" and row.signed_by:
					row.signed_by = None
					row.signed_on = None
					frappe.msgprint(
						_("Issue sign-off '{0}' was cleared because key details changed.").format(row.step_name),
						indicator="orange",
						alert=True,
					)

	def _require_signoffs(self, stage):
		missing = rules.unsigned_required([r.as_dict() for r in self.sign_offs], stage)
		if missing:
			frappe.throw(_("Required sign-off missing: {0}").format(", ".join(missing)), title=_("Sign-off required"))

	def _show_issues(self, issues, enforce):
		used, blockers = [], []
		for it in issues:
			if it["severity"] == services.ALERT:
				frappe.msgprint(it["message"], indicator="orange", alert=not enforce)
				continue
			if it["exception"]:
				exc = services.approved_exception(it["exception"], self.doctype, self.name)
				if exc:
					used.append(f"{it['exception']}: {exc.name}")
					continue
				msg = it["message"] + " " + _("Requires an approved '{0}' exception.").format(_(it["exception"]))
			else:
				msg = it["message"]
			blockers.append(msg)
		if blockers:
			if enforce:
				frappe.throw("<br>".join(blockers), title=_("Cannot issue Work Order"))
			frappe.msgprint(
				"<br>".join(blockers), title=_("Will block on issue"), indicator="red"
			)
		return used

	def _require_status(self, *allowed):
		if self.docstatus != 1 or self.status not in allowed:
			frappe.throw(_("Action not allowed when status is {0}.").format(_(self.status)))

	def _require_roles(self, roles):
		if not services.user_has_any_role(roles):
			frappe.throw(_("You are not permitted to perform this action."), frappe.PermissionError)

	def _segregation(self, *other_users):
		if not cint(services.settings().enforce_segregation):
			return
		me = frappe.session.user
		if me == "Administrator":
			return
		if me in [u for u in other_users if u]:
			frappe.throw(_("Segregation of duties: you issued or recorded this work order, so you cannot perform this step."))

	# ------------------------------------------------------------------ actions
	@frappe.whitelist()
	def record_checkin(self, actual_checkin=None):
		self._require_roles(FIELD_ROLES)
		self._require_status("Issued")
		self.db_set({"actual_checkin": get_datetime(actual_checkin or now_datetime()), "status": "Executed"})
		return self.status

	@frappe.whitelist()
	def record_delivery(self, delivered_on=None):
		self._require_roles(FIELD_ROLES)
		self._require_status("Executed", "Issued")
		self.db_set(
			{
				"delivered_on": get_datetime(delivered_on or now_datetime()),
				"delivery_received_by": frappe.session.user,
				"status": "Delivered",
			}
		)
		return self.status

	@frappe.whitelist()
	def record_qc(self, outputs, compliance_score=None, rejections=None, remarks=None, checks=None):
		"""outputs: [{row_name, delivered_qty, accepted_qty, delivered_size_gb, delivered_formats}]
		rejections: [{reason, qty, remarks}]; checks: [{row_name, compliant, remarks}]"""
		self._require_roles(QC_RECORD_ROLES)
		self._require_status("Delivered", "Pending Approval")
		self._segregation(self.owner, self.issued_by)
		self._require_signoffs("Receipt")

		outputs = json.loads(outputs) if isinstance(outputs, str) else (outputs or [])
		rejections = json.loads(rejections) if isinstance(rejections, str) else (rejections or [])
		by_name = {o.get("row_name") or o.get("name"): o for o in outputs}

		delivered = accepted = 0
		min_met = True
		for row in self.outputs:
			o = by_name.get(row.name, {})
			row.delivered_qty = cint(o.get("delivered_qty"))
			row.accepted_qty = cint(o.get("accepted_qty"))
			row.delivered_size_gb = flt(o.get("delivered_size_gb"), 3)
			row.delivered_formats = (o.get("delivered_formats") or "").strip() or None
			if row.accepted_qty > row.delivered_qty:
				frappe.throw(_("Row {0}: accepted cannot exceed delivered.").format(row.idx))
			delivered += row.delivered_qty
			accepted += row.accepted_qty
			if cint(row.min_qty) and row.delivered_qty < cint(row.min_qty):
				min_met = False
			row.db_update()

		if not self.outputs:
			frappe.throw(_("Add at least one required output before recording QC."))

		checks = json.loads(checks) if isinstance(checks, str) else (checks or [])
		check_map = {c.get("row_name"): c for c in checks}
		compliant = 0
		for row in self.checks:
			c = check_map.get(row.name, {})
			row.compliant = 1 if cint(c.get("compliant")) else 0
			row.remarks = c.get("remarks")
			compliant += row.compliant
			row.db_update()
		auto = rules.checklist_score(compliant, len(self.checks))
		if auto is None and compliance_score in (None, ""):
			frappe.throw(_("Enter the Output Compliance Score (no technical checklist on this order)."))
		final_compliance = auto if auto is not None else rules.clamp_score(flt(compliance_score))

		frappe.db.delete("Daily Work Order Rejection", {"parent": self.name, "parenttype": self.doctype})
		idx = 0
		for r in rejections:
			if not r.get("reason"):
				continue
			idx += 1
			child = frappe.new_doc("Daily Work Order Rejection")
			child.update(
				{
					"reason": r["reason"],
					"qty": cint(r.get("qty")),
					"remarks": r.get("remarks"),
					"parent": self.name,
					"parenttype": self.doctype,
					"parentfield": "rejections",
					"idx": idx,
				}
			)
			child.db_insert()

		self.db_set(
			{
				"delivered_units": delivered,
				"accepted_units": accepted,
				"acceptance_pct": rules.acceptance_pct(delivered, accepted),
				"min_output_met": 1 if min_met else 0,
				"compliance_score": final_compliance,
				"qc_remarks": remarks,
				"qc_recorded_by": frappe.session.user,
				"qc_recorded_on": now_datetime(),
				"status": "Pending Approval",
			}
		)
		return self.status

	@frappe.whitelist()
	def approve_qc(self, manager_score):
		self._require_roles(QC_APPROVE_ROLES)
		self._require_status("Pending Approval")
		self._segregation(self.owner, self.issued_by, self.qc_recorded_by)
		self._require_signoffs("QC")

		s = services.settings()
		partial = services.approved_exception("Partial Acceptance", self.doctype, self.name)
		result = rules.qc_decision(
			flt(self.acceptance_pct), bool(self.min_output_met), flt(s.acceptance_threshold), bool(partial)
		)
		quality = rules.quality_band_score(flt(self.acceptance_pct), services.quality_bands())
		punctuality = rules.punctuality_score(
			services.combine(self.work_date, self.scheduled_checkin),
			get_datetime(self.actual_checkin) if self.actual_checkin else None,
			get_datetime(self.delivery_due) if self.delivery_due else None,
			get_datetime(self.delivered_on) if self.delivered_on else None,
			cint(s.checkin_grace_minutes),
			cint(s.checkin_penalty_step_minutes),
			flt(s.max_checkin_penalty),
			flt(s.late_delivery_penalty),
		)
		manager = rules.clamp_score(flt(manager_score))
		weighted = rules.weighted_score(quality, flt(self.compliance_score), punctuality, manager, services.weights())

		used = self.exceptions_used or ""
		if partial and (flt(self.acceptance_pct) < flt(s.acceptance_threshold) or not self.min_output_met):
			used = (used + "\n" if used else "") + f"Partial Acceptance: {partial.name}"

		self.db_set(
			{
				"qc_result": result,
				"status": result,
				"quality_score": quality,
				"punctuality_score": punctuality,
				"manager_score": manager,
				"weighted_score": weighted,
				"qc_approved_by": frappe.session.user,
				"qc_approved_on": now_datetime(),
				"exceptions_used": used or None,
			}
		)
		self.reload()
		level = services.apply_rating(self)
		return {"status": self.status, "weighted_score": weighted, "level": level}

	@frappe.whitelist()
	def return_to_review(self, reason):
		"""Project Manager sends recorded QC back to the review officer."""
		self._require_roles(QC_APPROVE_ROLES)
		self._require_status("Pending Approval")
		self.add_comment("Comment", _("QC returned for review: {0}").format(reason))
		self.db_set("status", "Delivered")
		return self.status

	@frappe.whitelist()
	def sign_off(self, row_name):
		row = next((r for r in self.sign_offs if r.name == row_name), None)
		if not row:
			frappe.throw(_("Sign-off step not found."))
		if row.signed_by:
			frappe.throw(_("'{0}' is already signed by {1}.").format(row.step_name, row.signed_by))
		if row.role and not services.user_has_any_role([row.role]):
			frappe.throw(_("Only {0} can sign '{1}'.").format(row.role, row.step_name), frappe.PermissionError)
		allowed = {
			"Issue": self.docstatus == 0,
			"Receipt": self.docstatus == 1 and self.status in ("Executed", "Delivered"),
			"QC": self.docstatus == 1 and self.status == "Pending Approval",
		}
		if not allowed.get(row.stage):
			frappe.throw(_("'{0}' cannot be signed while the order is {1}.").format(row.step_name, _(self.status)))
		now = now_datetime()
		frappe.db.set_value(
			"Daily Work Order Sign-off", row.name, {"signed_by": frappe.session.user, "signed_on": now}, update_modified=False
		)
		frappe.db.set_value(self.doctype, self.name, "modified", now, update_modified=False)
		self.add_comment("Info", _("Signed '{0}'").format(row.step_name))
		return {"step": row.step_name, "signed_on": now}

