# Changelog

## 1.1.0 — 2026-11-26
Aligned with field paper work-order practice.
- Work Order Template: required outputs (min qty, format, resolution, duration range), technical checklist, instructions, delivery defaults; default template per Work Type; sample "Standard Photo & Video Day" template on first install
- Daily Work Order: freelancer mobile, technical checklist, delivered size (GB) and formats per output, delivery received by, "Electronic and Physical" delivery
- Output compliance score calculated from the checklist when present
- Configurable sign-off steps (Issue / Receipt / QC stages, role, required) with tamper-proof signing and reset on key changes
- Bilingual printed work order (CrewFlow Work Order) set as the default print format
- Clear wording: "Rejected at acceptance" (after delivery) vs "Cancelled before execution"
- verify_tree.py checks print formats; 17 rule tests

## 1.0.0 — 2026-11-26
Initial release (Phase 1).
- Freelancer Profile, specialties, equipment, unavailability
- Rate Seasons, Season Calendar with Hijri suggestion, Rate Cards, Rate Bands
- Framework Agreements with member pool and expiry alerts; Project Contracts with band check and approval
- Project BOQ with monthly quota; Work Zones
- Daily Work Order with issuance rule engine, check-in, delivery, QC, rating
- CrewFlow Exception approvals with role matrix and segregation of duties
- Rolling level, auto-block and auto-suspension
- Amount-tiered PO approval, Finance budget confirmation, 80% budget alerts
- Monthly freelancer Purchase Invoice generation
- Reports: Quota Consumption, Freelancer Performance, Freelancer Availability
- Workspace, calendar views, English/Arabic translations
