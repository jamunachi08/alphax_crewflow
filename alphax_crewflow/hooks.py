app_name = "alphax_crewflow"
app_title = "AlphaX CrewFlow"
app_publisher = "AlphaX"
app_description = "Freelancer and crew work-order management for project-based service businesses"
app_email = "info@alphax.sa"
app_license = "Commercial"
app_logo_url = "/assets/alphax_crewflow/images/crewflow.svg"

required_apps = ["frappe/erpnext"]

add_to_apps_screen = [
	{
		"name": "alphax_crewflow",
		"logo": "/assets/alphax_crewflow/images/crewflow.svg",
		"title": "CrewFlow",
		"route": "/app/crewflow",
	}
]

# ------------------------------------------------------------------ install / migrate
after_install = "alphax_crewflow.install.after_install"
after_migrate = "alphax_crewflow.install.after_migrate"

# ------------------------------------------------------------------ client scripts on core doctypes
doctype_js = {
	"Purchase Order": "public/js/purchase_order.js",
}

calendars = ["Daily Work Order", "Freelancer Unavailability"]

# ------------------------------------------------------------------ document events
doc_events = {
	"Purchase Order": {
		"validate": "alphax_crewflow.crewflow.integrations.purchase_order.validate",
		"before_submit": "alphax_crewflow.crewflow.integrations.purchase_order.before_submit",
	},
	"Purchase Invoice": {
		"validate": "alphax_crewflow.crewflow.integrations.purchase_invoice.validate",
		"on_cancel": "alphax_crewflow.crewflow.integrations.purchase_invoice.unlink_work_orders",
		"on_trash": "alphax_crewflow.crewflow.integrations.purchase_invoice.unlink_work_orders",
	},
}

# ------------------------------------------------------------------ scheduler
scheduler_events = {
	"daily": [
		"alphax_crewflow.tasks.daily",
	],
}
