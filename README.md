# AlphaX CrewFlow

Freelancer and crew work-order management for project-based service businesses that engage
day-rate freelancers, suppliers and subcontractors — media and film production, events,
documentation, surveying, inspection and similar field-crew operations.

Built on Frappe / ERPNext (v15 and v16). All thresholds, weights, seasons and approvers are configuration.

## What it does

| Area | Capability |
|---|---|
| Freelancers | Freelancer Profile on top of ERPNext Supplier: specialty, level (1-5), equipment, ID, IBAN, portfolio, status (Active / Blocked / Suspended / Inactive) |
| Rates | Rate Cards (work type x season x level band x optional equipment) and Rate Bands (min/max per specialty, task and level) with 12-month average reference |
| Seasons | Season Calendar per Gregorian year with one-click Hijri period suggestion (Ramadan, Hajj or any Hijri range) |
| Contracts | Framework Agreements (long-term, member pool, expiry alerts) and Project Contracts (short projects, negotiated rate, band check, approval) |
| Quota | Project BOQ with monthly work-day quota per work type / BOQ item; alert at 80%, block at 100% |
| Work Orders | Daily Work Order per freelancer per day: template-driven outputs and checklist, locked rate, sign-offs, check-in, delivery, QC, rating, bilingual print |
| Rules on issue | Eligibility, unavailability, double booking (row-locked), post-facto, agreement validity, workload balance, quota |
| Quality | Acceptance % vs threshold + minimum output; rejection reasons; accept/reject only, partial acceptance by exception |
| Rating | Weighted score (quality, compliance, punctuality, manager), rolling level over last N orders, auto-block and auto-suspend |
| Exceptions | One approval document for every override, role-based approvers, segregation of duties, full audit trail |
| Purchasing | Amount-tiered PO approval with Finance budget confirmation; 80% early budget alert on PO and Purchase Invoice |
| Payment | Monthly job creates one Purchase Invoice per freelancer and currency for accepted orders of the prior month |
| Reports | Quota Consumption, Freelancer Performance, Freelancer Availability (+ ERPNext Accounts Payable aging) |
| Language | English / Arabic |

## Install

```bash
bench get-app https://github.com/<org>/alphax_crewflow
bench --site <site> install-app alphax_crewflow
```
On Frappe Cloud: add the repo to the bench group, deploy, then install on the site.
Python dependency: `hijridate` (installed automatically from pyproject).

## First-time setup
1. **CrewFlow Settings** — company, Freelancer Service Item (non-stock service item), review thresholds and approver roles.
2. **Roles** — assign the eight `CrewFlow *` roles to users; add a *User Permission* on Project for project managers who should see only their own projects.
3. **Masters** — Work Order Templates (outputs + checklist), Freelancer Specialty, Work Type (tick *Rate Depends on Equipment* for e.g. drone work), Equipment Type, Rate Season.
4. **Season Calendar** for the year → *Suggest Hijri Periods* → review.
5. **Rate Card** / **Rate Band**.
6. Suppliers in group *Freelancers* → **Freelancer Profile** for each.
7. Per project: **Project BOQ** (items + monthly quota), **Work Zones**, and a **Framework Agreement** or **Project Contracts**.

## Roles

| Role | Typical holder |
|---|---|
| CrewFlow Executive | CEO / General Manager |
| CrewFlow Projects Director | Head of projects |
| CrewFlow Production Manager | Contracting lead for short projects |
| CrewFlow Project Manager | Project managers |
| CrewFlow Coordinator | Scheduling / coordination |
| CrewFlow Review Officer | Receipt & quality review |
| CrewFlow Finance | Finance team |
| CrewFlow Admin | System administrator |

Rates on Daily Work Orders are field-level restricted (permlevel 1): visible to Finance, Projects Director, Executive and Admin only.

## Developer checks
```bash
python3 verify_tree.py                          # structural guard
python3 -m unittest alphax_crewflow.tests.test_rules   # pure rule tests, no site needed
```

Licence: commercial — AlphaX.
