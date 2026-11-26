#!/usr/bin/env python3
"""Structural guard for alphax_crewflow. Run from the repo root: python3 verify_tree.py
Exits non-zero on any failure. No Frappe site needed."""

import ast
import glob
import json
import os
import py_compile
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(ROOT, "alphax_crewflow")
DT_DIR = os.path.join(APP, "crewflow", "doctype")

CORE_DOCTYPES = {
	"Company", "Supplier", "Supplier Group", "Customer", "Project", "Sales Order", "Purchase Invoice",
	"Purchase Order", "Item", "Cost Center", "Currency", "Country", "User", "Role", "DocType", "UOM",
}
FORBIDDEN_TERMS = [r"\bDKH\b", r"Dunia", r"Alkhaleej"]

errors = []


def err(msg):
	errors.append(msg)


def snake(name):
	return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


# ------------------------------------------------------------------ doctypes
app_doctypes, tables = {}, set()
for path in glob.glob(os.path.join(DT_DIR, "*", "*.json")):
	folder = os.path.basename(os.path.dirname(path))
	d = json.load(open(path))
	if d.get("doctype") != "DocType":
		continue
	if snake(d["name"]) != folder or os.path.basename(path) != folder + ".json":
		err(f"{path}: name/folder mismatch")
	app_doctypes[d["name"]] = d
	if d.get("istable"):
		tables.add(d["name"])
	for f in ("__init__.py", folder + ".py"):
		if not os.path.exists(os.path.join(os.path.dirname(path), f)):
			err(f"{folder}: missing {f}")
	cls = re.sub(r"[^A-Za-z0-9]", "", d["name"])
	src = open(os.path.join(os.path.dirname(path), folder + ".py")).read()
	if f"class {cls}(" not in src:
		err(f"{folder}: controller class {cls} not found")

for name, d in app_doctypes.items():
	names = [f["fieldname"] for f in d["fields"]]
	if len(names) != len(set(names)):
		err(f"{name}: duplicate fieldnames")
	if d.get("field_order") != names:
		err(f"{name}: field_order mismatch")
	if d.get("is_submittable") and "amended_from" not in names:
		err(f"{name}: submittable without amended_from")
	for f in d["fields"]:
		ft, opt = f["fieldtype"], f.get("options")
		if ft == "Link" and opt not in app_doctypes and opt not in CORE_DOCTYPES:
			err(f"{name}.{f['fieldname']}: unknown Link target {opt}")
		if ft == "Table" and opt not in tables:
			err(f"{name}.{f['fieldname']}: Table target {opt} is not a child table")
		if ft == "Dynamic Link" and opt not in names:
			err(f"{name}.{f['fieldname']}: Dynamic Link options field {opt} missing")
		if f.get("fetch_from"):
			src_field = f["fetch_from"].split(".")[0]
			if src_field not in names:
				err(f"{name}.{f['fieldname']}: fetch_from source {src_field} missing")
		if ft == "Currency" and opt and opt not in names and opt not in ("currency",):
			err(f"{name}.{f['fieldname']}: Currency options {opt} not a field")
		if ft == "Currency" and opt == "currency" and "currency" not in names:
			err(f"{name}.{f['fieldname']}: currency field missing")
	if not d.get("istable") and not d.get("permissions"):
		err(f"{name}: no permissions")

# ------------------------------------------------------------------ python
for path in glob.glob(os.path.join(ROOT, "**", "*.py"), recursive=True):
	try:
		py_compile.compile(path, doraise=True)
	except py_compile.PyCompileError as e:
		err(f"compile: {e}")


def resolve(dotted):
	parts = dotted.split(".")
	mod, fn = parts[:-1], parts[-1]
	file = os.path.join(ROOT, *mod) + ".py"
	if not os.path.exists(file):
		return False
	tree = ast.parse(open(file).read())
	return any(isinstance(n, ast.FunctionDef) and n.name == fn for n in tree.body)


hooks_src = open(os.path.join(APP, "hooks.py")).read()
for dotted in re.findall(r'"(alphax_crewflow\.[a-z_.]+)"', hooks_src):
	if not resolve(dotted):
		err(f"hooks: cannot resolve {dotted}")
for js in re.findall(r'"(public/js/[a-z_]+\.js)"', hooks_src):
	if not os.path.exists(os.path.join(APP, js)):
		err(f"hooks: missing {js}")

for path in glob.glob(os.path.join(APP, "**", "*.js"), recursive=True):
	for m in re.findall(r'method:\s*"(alphax_crewflow\.[a-z_.]+)"', open(path).read()):
		if not resolve(m):
			err(f"{path}: cannot resolve {m}")

# ------------------------------------------------------------------ reports & workspace
for path in glob.glob(os.path.join(APP, "crewflow", "report", "*", "*.json")):
	folder = os.path.dirname(path)
	name = os.path.basename(folder)
	for ext in (".py", ".js"):
		if not os.path.exists(os.path.join(folder, name + ext)):
			err(f"report {name}: missing {ext}")
	if "def execute(" not in open(os.path.join(folder, name + ".py")).read():
		err(f"report {name}: no execute()")
ws = json.load(open(os.path.join(APP, "crewflow", "workspace", "crewflow", "crewflow.json")))
reports = {json.load(open(p))["name"] for p in glob.glob(os.path.join(APP, "crewflow", "report", "*", "*.json"))}
for link in ws["links"]:
	if link["type"] == "Link":
		target = link["link_to"]
		if link["link_type"] == "DocType" and target not in app_doctypes and target not in CORE_DOCTYPES:
			err(f"workspace: unknown doctype {target}")
		if link["link_type"] == "Report" and target not in reports and target != "Accounts Payable":
			err(f"workspace: unknown report {target}")
json.loads(ws["content"])

# ------------------------------------------------------------------ print formats
for path in glob.glob(os.path.join(APP, "crewflow", "print_format", "*", "*.json")):
	pf = json.load(open(path))
	if pf.get("doc_type") not in app_doctypes:
		err(f"print format {pf.get('name')}: unknown doc_type")
	try:
		import jinja2

		jinja2.Environment().parse(pf.get("html") or "")
	except ImportError:
		pass
	except Exception as e:  # noqa: BLE001
		err(f"print format {pf.get('name')}: jinja error {e}")
	for field in re.findall(r"doc\.([a-z_]+)", pf.get("html") or ""):
		if field in ("get_formatted", "name", "status", "outputs", "checks", "rejections", "sign_offs"):
			continue
		if field not in [f["fieldname"] for f in app_doctypes[pf["doc_type"]]["fields"]]:
			err(f"print format {pf.get('name')}: unknown field doc.{field}")
for name, d in app_doctypes.items():
	dpf = d.get("default_print_format")
	if dpf and not os.path.exists(os.path.join(APP, "crewflow", "print_format", snake(dpf), snake(dpf) + ".json")):
		err(f"{name}: default print format {dpf} missing")

# ------------------------------------------------------------------ JS syntax
node = subprocess.run(["which", "node"], capture_output=True, text=True).stdout.strip()
if node:
	for path in glob.glob(os.path.join(APP, "**", "*.js"), recursive=True):
		r = subprocess.run([node, "--check", path], capture_output=True, text=True)
		if r.returncode:
			err(f"js syntax {path}: {r.stderr.strip().splitlines()[-1] if r.stderr else ''}")

# ------------------------------------------------------------------ branding guard
for path in glob.glob(os.path.join(ROOT, "**", "*"), recursive=True):
	if os.path.isdir(path) or path.endswith((".pyc", ".svg")) or path.endswith("verify_tree.py"):
		continue
	try:
		text = open(path, encoding="utf-8").read()
	except UnicodeDecodeError:
		continue
	for term in FORBIDDEN_TERMS:
		if re.search(term, text):
			err(f"{path}: contains client-specific term {term}")

# ------------------------------------------------------------------ result
if errors:
	print("verify_tree: FAILED")
	for e in errors:
		print("  -", e)
	sys.exit(1)
print(f"verify_tree: OK ({len(app_doctypes)} doctypes, {len(reports)} reports)")
