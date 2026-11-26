// Copyright (c) 2026, AlphaX

const CF_STATUS_COLORS = {
	Draft: "gray",
	Issued: "blue",
	Executed: "cyan",
	Delivered: "purple",
	"Pending Approval": "orange",
	Accepted: "green",
	Rejected: "red",
	Cancelled: "darkgrey",
};

frappe.ui.form.on("Daily Work Order", {
	setup(frm) {
		frm.set_query("freelancer", () => ({ filters: { status: "Active" } }));
		frm.set_query("framework_agreement", () => ({
			filters: { project: frm.doc.project, status: ["!=", "Closed"] },
		}));
		frm.set_query("project_contract", () => ({
			filters: { project: frm.doc.project, docstatus: 1, freelancer: frm.doc.freelancer || undefined },
		}));
		frm.set_query("work_zone", () => ({ filters: { project: frm.doc.project } }));
		frm.set_query("project_boq", () => ({ filters: { project: frm.doc.project } }));
	},

	refresh(frm) {
		if (frm.doc.status) {
			frm.page.set_indicator(__(frm.doc.status), CF_STATUS_COLORS[frm.doc.status] || "gray");
		}
		add_signoff_button(frm);
		if (frm.doc.docstatus !== 1) {
			if (!frm.is_new()) add_exception_button(frm);
			return;
		}
		const s = frm.doc.status;
		if (s === "Issued") {
			frm.add_custom_button(__("Record Check-in"), () => prompt_datetime(frm, "record_checkin", "actual_checkin", __("Actual Check-in")), __("Actions"));
		}
		if (s === "Issued" || s === "Executed") {
			frm.add_custom_button(__("Record Delivery"), () => prompt_datetime(frm, "record_delivery", "delivered_on", __("Delivered On")), __("Actions"));
		}
		if (s === "Delivered" || s === "Pending Approval") {
			frm.add_custom_button(__("Record QC"), () => qc_dialog(frm), __("Actions"));
		}
		if (s === "Pending Approval") {
			frm.add_custom_button(__("Approve QC"), () => approve_dialog(frm), __("Actions"));
			frm.add_custom_button(__("Return to Review"), () => {
				frappe.prompt({ fieldname: "reason", fieldtype: "Small Text", label: __("Reason"), reqd: 1 }, (v) =>
					frm.call("return_to_review", { reason: v.reason }).then(() => frm.reload_doc())
				);
			}, __("Actions"));
		}
		if (!["Accepted", "Cancelled"].includes(s)) add_exception_button(frm);
	},

	work_order_template(frm) {
		if (frm.doc.work_order_template && (frm.doc.outputs || []).length) {
			frappe.confirm(__("Replace the current outputs and checklist with the template?"), () => {
				frm.clear_table("outputs");
				frm.clear_table("checks");
				frm.set_value("instructions", "");
				frm.save();
			});
		}
	},

	project(frm) {
		["framework_agreement", "project_contract", "work_zone", "project_boq", "boq_code"].forEach((f) => frm.set_value(f, null));
	},
});

function add_signoff_button(frm) {
	const stage_ok = {
		Issue: frm.doc.docstatus === 0 && !frm.is_new(),
		Receipt: frm.doc.docstatus === 1 && ["Executed", "Delivered"].includes(frm.doc.status),
		QC: frm.doc.docstatus === 1 && frm.doc.status === "Pending Approval",
	};
	const open = (frm.doc.sign_offs || []).filter(
		(r) => !r.signed_by && stage_ok[r.stage] && (!r.role || frappe.user.has_role(r.role))
	);
	if (!open.length) return;
	frm.add_custom_button(__("Sign Off"), () => {
		if (frm.is_dirty()) {
			frappe.msgprint(__("Save the work order before signing."));
			return;
		}
		frappe.prompt(
			{
				fieldname: "row_name",
				fieldtype: "Select",
				label: __("Step"),
				reqd: 1,
				options: open.map((r) => ({ label: __(r.step_name), value: r.name })),
				default: open[0].name,
			},
			(v) => frm.call("sign_off", { row_name: v.row_name }).then(() => frm.reload_doc()),
			__("Sign Off")
		);
	}, __("Actions"));
}

function add_exception_button(frm) {
	frm.add_custom_button(__("Request Exception"), () => {
		frappe.new_doc("CrewFlow Exception", {
			reference_doctype: "Daily Work Order",
			reference_name: frm.doc.name,
			project: frm.doc.project,
			freelancer: frm.doc.freelancer,
			work_date: frm.doc.work_date,
		});
	}, __("Actions"));
}

function prompt_datetime(frm, method, fieldname, label) {
	frappe.prompt(
		{ fieldname, fieldtype: "Datetime", label, default: frappe.datetime.now_datetime(), reqd: 1 },
		(v) => frm.call(method, { [fieldname]: v[fieldname] }).then(() => frm.reload_doc()),
		label
	);
}

function qc_dialog(frm) {
	const outputs = (frm.doc.outputs || []).map((r) => ({
		row_name: r.name,
		output_type: r.output_type,
		min_qty: r.min_qty,
		delivered_qty: r.delivered_qty || 0,
		accepted_qty: r.accepted_qty || 0,
		delivered_size_gb: r.delivered_size_gb || 0,
		delivered_formats: r.delivered_formats || r.file_format || "",
	}));
	const checks = (frm.doc.checks || []).map((r) => ({
		row_name: r.name,
		check_item: frappe.boot.lang === "ar" && r.check_item_ar ? r.check_item_ar : r.check_item,
		compliant: r.compliant || 0,
		remarks: r.remarks || "",
	}));
	const has_checks = checks.length > 0;
	const d = new frappe.ui.Dialog({
		title: __("Record Quality Acceptance"),
		size: "large",
		fields: [
			{
				fieldname: "outputs",
				fieldtype: "Table",
				label: __("Outputs"),
				cannot_add_rows: true,
				in_place_edit: true,
				data: outputs,
				fields: [
					{ fieldname: "row_name", fieldtype: "Data", hidden: 1 },
					{ fieldname: "output_type", fieldtype: "Data", label: __("Output"), read_only: 1, in_list_view: 1 },
					{ fieldname: "min_qty", fieldtype: "Int", label: __("Min"), read_only: 1, in_list_view: 1 },
					{ fieldname: "delivered_qty", fieldtype: "Int", label: __("Delivered"), in_list_view: 1, reqd: 1 },
					{ fieldname: "accepted_qty", fieldtype: "Int", label: __("Accepted"), in_list_view: 1, reqd: 1 },
					{ fieldname: "delivered_size_gb", fieldtype: "Float", label: __("Size (GB)"), in_list_view: 1 },
					{ fieldname: "delivered_formats", fieldtype: "Data", label: __("Formats"), in_list_view: 1 },
				],
			},
			{
				fieldname: "checks",
				fieldtype: "Table",
				label: __("Technical Checklist"),
				cannot_add_rows: true,
				in_place_edit: true,
				hidden: !has_checks,
				data: checks,
				fields: [
					{ fieldname: "row_name", fieldtype: "Data", hidden: 1 },
					{ fieldname: "check_item", fieldtype: "Data", label: __("Check Item"), read_only: 1, in_list_view: 1 },
					{ fieldname: "compliant", fieldtype: "Check", label: __("Compliant"), in_list_view: 1 },
					{ fieldname: "remarks", fieldtype: "Data", label: __("Remarks"), in_list_view: 1 },
				],
			},
			{
				fieldname: "rejections",
				fieldtype: "Table",
				label: __("Rejection Reasons"),
				data: [],
				fields: [
					{ fieldname: "reason", fieldtype: "Link", options: "Rejection Reason", label: __("Reason"), in_list_view: 1, reqd: 1 },
					{ fieldname: "qty", fieldtype: "Int", label: __("Qty"), in_list_view: 1 },
					{ fieldname: "remarks", fieldtype: "Data", label: __("Remarks"), in_list_view: 1 },
				],
			},
			{
				fieldname: "compliance_score",
				fieldtype: "Float",
				label: __("Output Compliance Score (1-5)"),
				description: __("Count, duration, resolution, formats, camera settings, file naming"),
				hidden: has_checks,
				reqd: !has_checks,
			},
			{ fieldname: "remarks", fieldtype: "Small Text", label: __("Remarks") },
		],
		primary_action_label: __("Save QC"),
		primary_action(v) {
			frm.call("record_qc", {
				outputs: v.outputs,
				rejections: v.rejections || [],
				compliance_score: has_checks ? null : v.compliance_score,
				checks: v.checks || [],
				remarks: v.remarks,
			}).then(() => {
				d.hide();
				frm.reload_doc();
			});
		},
	});
	d.show();
}

function approve_dialog(frm) {
	const d = new frappe.ui.Dialog({
		title: __("Approve Quality Acceptance"),
		fields: [
			{
				fieldtype: "HTML",
				options: `<p>${__("Acceptance")}: <b>${flt(frm.doc.acceptance_pct, 1)}%</b> &middot; ${__("Minimum output met")}: <b>${frm.doc.min_output_met ? __("Yes") : __("No")}</b></p>`,
			},
			{ fieldname: "manager_score", fieldtype: "Float", label: __("Manager Assessment (1-5)"), description: __("Conduct and cooperation"), reqd: 1 },
		],
		primary_action_label: __("Approve"),
		primary_action(v) {
			frm.call("approve_qc", { manager_score: v.manager_score }).then((r) => {
				d.hide();
				if (r.message) {
					frappe.show_alert({
						message: __("Result: {0} · Score {1} · Freelancer level {2}", [__(r.message.status), r.message.weighted_score, r.message.level]),
						indicator: r.message.status === "Accepted" ? "green" : "red",
					});
				}
				frm.reload_doc();
			});
		},
	});
	d.show();
}
