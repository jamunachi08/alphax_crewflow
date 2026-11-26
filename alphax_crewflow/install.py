# Copyright (c) 2026, AlphaX
# License: see license.txt

"""Idempotent seeders: safe to run on every install and migrate."""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

ROLES = [
	"CrewFlow Executive",
	"CrewFlow Projects Director",
	"CrewFlow Production Manager",
	"CrewFlow Project Manager",
	"CrewFlow Coordinator",
	"CrewFlow Review Officer",
	"CrewFlow Finance",
	"CrewFlow Admin",
]

DEFAULT_APPROVERS = [
	("Quota Overrun", "CrewFlow Executive"),
	("Workload Overrun", "CrewFlow Projects Director"),
	("Workload Overrun", "CrewFlow Executive"),
	("Post-facto Issue", "CrewFlow Executive"),
	("Rate Change", "CrewFlow Projects Director"),
	("Rate Change", "CrewFlow Executive"),
	("Partial Acceptance", "CrewFlow Projects Director"),
	("Partial Acceptance", "CrewFlow Executive"),
	("Reinstatement", "CrewFlow Projects Director"),
	("Contract Approval", "CrewFlow Projects Director"),
	("Contract Approval", "CrewFlow Executive"),
	("Budget Overrun", "CrewFlow Executive"),
	("Post-closure Adjustment", "CrewFlow Executive"),
	("Other", "CrewFlow Executive"),
]

DEFAULT_BANDS = [(90, 5), (80, 4), (70, 3), (60, 2), (0, 1)]

REJECTION_REASONS = [
	("Camera shake", "اهتزاز الكاميرا"),
	("Dirty lens", "عدسة متسخة"),
	("Shadow / exposure", "ظل / تعريض"),
	("Non-compliant duration", "مدة غير مطابقة"),
	("Wrong format or resolution", "صيغة أو دقة غير صحيحة"),
	("Other", "أخرى"),
]

SAMPLE_TEMPLATE = {
	"template_name": "Standard Photo & Video Day",
	"template_name_ar": "يوم تصوير فوتوغرافي وفيديو قياسي",
	"delivery_method": "Electronic",
	"delivery_hours": 24,
	"outputs": [
		{"output_type": "Video clips", "unit": "Clips", "min_qty": 30, "file_format": "MP4", "resolution": "4K",
		 "min_duration_sec": 15, "max_duration_sec": 20},
		{"output_type": "Photos", "unit": "Photos", "min_qty": 100, "file_format": "JPEG + RAW"},
	],
	"checks": [
		{"check_item": "Camera date and time set accurately before shooting", "check_item_ar": "ضبط التاريخ والوقت بدقة قبل التصوير"},
		{"check_item": "Photos delivered in JPEG and RAW", "check_item_ar": "الصور بصيغة JPEG و RAW"},
		{"check_item": "Videos delivered in MP4", "check_item_ar": "الفيديو بصيغة MP4"},
		{"check_item": "Original in-camera file names unchanged", "check_item_ar": "عدم تغيير أسماء الملفات الأصلية داخل الكاميرا"},
		{"check_item": "Clip duration within the required range", "check_item_ar": "مدة المقاطع ضمن المدى المطلوب"},
		{"check_item": "Resolution and quality as required (e.g. 4K)", "check_item_ar": "الدقة والجودة حسب المطلوب (مثل 4K)"},
	],
	"instructions": "<p>Professional quality with attention to lighting and composition. Static or moving shots as directed.</p>"
	"<p dir=\"rtl\">جودة احترافية مع مراعاة الإضاءة والتكوين الفني. لقطات ثابتة أو متحركة حسب التوجيه.</p>",
}

CUSTOM_FIELDS = {
	"Purchase Invoice Item": [
		{
			"fieldname": "crewflow_work_order",
			"label": "CrewFlow Work Order",
			"fieldtype": "Link",
			"options": "Daily Work Order",
			"insert_after": "project",
			"read_only": 1,
			"no_copy": 1,
		}
	],
	"Purchase Order": [
		{
			"fieldname": "crewflow_approval_section",
			"label": "CrewFlow Approval",
			"fieldtype": "Section Break",
			"insert_after": "terms",
			"collapsible": 1,
		},
		{
			"fieldname": "crewflow_budget_checked",
			"label": "Budget Confirmed by Finance",
			"fieldtype": "Check",
			"insert_after": "crewflow_approval_section",
			"read_only": 1,
			"no_copy": 1,
		},
		{
			"fieldname": "crewflow_budget_checked_by",
			"label": "Confirmed By",
			"fieldtype": "Link",
			"options": "User",
			"insert_after": "crewflow_budget_checked",
			"read_only": 1,
			"no_copy": 1,
		},
		{
			"fieldname": "crewflow_budget_checked_on",
			"label": "Confirmed On",
			"fieldtype": "Datetime",
			"insert_after": "crewflow_budget_checked_by",
			"read_only": 1,
			"no_copy": 1,
		},
	],
}


def after_install():
	seed(first_install=True)


def after_migrate():
	seed(first_install=False)


def seed(first_install=False):
	create_roles()
	create_custom_fields(CUSTOM_FIELDS, ignore_validate=True, update=True)
	create_masters(first_install)
	seed_settings(first_install)
	frappe.db.commit()


def create_roles():
	for role in ROLES:
		if not frappe.db.exists("Role", role):
			frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert(ignore_permissions=True)


def create_masters(first_install=False):
	if not frappe.db.exists("Supplier Group", "Freelancers"):
		parent = frappe.db.get_value("Supplier Group", {"is_group": 1}, "name", order_by="lft asc")
		frappe.get_doc(
			{"doctype": "Supplier Group", "supplier_group_name": "Freelancers", "parent_supplier_group": parent, "is_group": 0}
		).insert(ignore_permissions=True)
	if not frappe.db.exists("Rate Season", "Regular"):
		frappe.get_doc(
			{"doctype": "Rate Season", "season_name": "Regular", "season_name_ar": "عادي", "is_default": 1}
		).insert(ignore_permissions=True)
	if first_install and not frappe.db.exists("Work Order Template", SAMPLE_TEMPLATE["template_name"]):
		frappe.get_doc({"doctype": "Work Order Template", **SAMPLE_TEMPLATE}).insert(ignore_permissions=True)
	for en, ar in REJECTION_REASONS:
		if not frappe.db.exists("Rejection Reason", en):
			frappe.get_doc({"doctype": "Rejection Reason", "reason": en, "reason_ar": ar}).insert(ignore_permissions=True)


def seed_settings(first_install=False):
	s = frappe.get_single("CrewFlow Settings")
	changed = False
	if not s.quality_bands:
		for min_pct, score in DEFAULT_BANDS:
			s.append("quality_bands", {"min_pct": min_pct, "score": score})
		changed = True
	if not s.exception_approvers:
		for exc, role in DEFAULT_APPROVERS:
			s.append("exception_approvers", {"exception_type": exc, "role": role})
		changed = True
	defaults = {
		"freelancer_supplier_group": "Freelancers",
		"default_season": "Regular",
		"po_tier1_role": "CrewFlow Project Manager",
		"po_tier2_role": "CrewFlow Projects Director",
		"po_tier3_role": "CrewFlow Executive",
	}
	for field, value in defaults.items():
		if not s.get(field) and frappe.db.exists(s.meta.get_field(field).options, value):
			s.set(field, value)
			changed = True
	numeric_defaults = {
		"min_level": 3.5, "rating_window": 10, "suspension_rejections": 3, "acceptance_threshold": 60,
		"weight_quality": 60, "weight_compliance": 15, "weight_punctuality": 15, "weight_manager": 10,
		"checkin_grace_minutes": 15, "checkin_penalty_step_minutes": 30, "max_checkin_penalty": 2,
		"late_delivery_penalty": 2, "workload_pct": 30, "workload_min_average": 10, "workload_fixed_tolerance": 3,
		"quota_alert_pct": 80, "payment_day": 10, "po_tier1_limit": 25000, "po_tier2_limit": 100000,
		"budget_alert_pct": 80,
	}
	# numeric defaults only on first install (or if never configured) so zeros chosen by users survive migrate
	never_configured = not any(s.get(f) for f in ("weight_quality", "weight_compliance", "weight_punctuality", "weight_manager"))
	for field, value in numeric_defaults.items():
		if (first_install or never_configured) and not s.get(field):
			s.set(field, value)
			changed = True
	if not s.initial_level_method:
		s.initial_level_method = "Pad with initial level"
		changed = True
	if not s.workload_basis:
		s.workload_basis = "Agreement lifetime"
		changed = True
	if changed:
		s.flags.ignore_mandatory = True
		s.save(ignore_permissions=True)
