# Jewellery Billing App — Current Project State

## Project Type

Production-oriented Jewellery Billing Application.

Stack:

* FastAPI
* SQLModel
* Jinja2 templates
* SQLite (local development)
* Supabase PostgreSQL (production)
* Alembic migrations
* Gemini OCR invoice scanning

The application is already functional and has undergone recent stabilization work.

The goal now is:

* production hardening
* PostgreSQL safety
* accounting correctness
* deployment readiness
* missing accounting workflow implementation

DO NOT rewrite architecture unnecessarily.

---

# CURRENTLY IMPLEMENTED FEATURES

The application already contains:

* invoice system
* stock management
* financial year model
* invoice numbering by FY
* month locking system
* dashboard
* reporting system
* settings management
* Gemini invoice scan support
* migration system
* Supabase compatibility structure

Recent stabilization changes were already applied using Cursor AI.

---

# RECENTLY FIXED / IMPROVED

The following improvements were already implemented recently and MUST be verified before any further changes:

## 1. Google API key optional handling

Scan routes should no longer crash if GOOGLE_API_KEY is missing.

## 2. Decimal financial calculations

Financial calculations were migrated toward Decimal usage.

Need verification that all critical money/weight calculations are safe.

## 3. Transaction safety

Invoice creation flow now uses transaction handling.

Need verification that stock/balance updates are fully atomic.

## 4. Financial year uniqueness

Unique constraints were added for financial year labels.

## 5. Alembic migration structure

New migrations were added.

Need migration-order verification.

## 6. Soft delete direction

Initial soft-delete related structure was added.

Need verification of consistency.

---

# VERY IMPORTANT REQUIREMENTS

This is accounting software.

Protect:

* balances
* stock
* invoice numbering
* financial years
* GST calculations
* historical records

Do not introduce risky architectural rewrites.

Do not rewrite unrelated files.

Do not generate giant full-file rewrites.

Prefer:

* minimal safe patches
* small targeted changes
* migration-safe updates

---

# CURRENT REMAINING TASKS

The following items are STILL missing or need verification.

These are now the primary focus.

---

# TASK 1 — Verify Existing Fixes

Before implementing anything new:

Verify whether recent Cursor fixes are ACTUALLY correct and production-safe.

Specifically verify:

* Decimal usage consistency
* transaction safety completeness
* migration consistency
* PostgreSQL compatibility
* nullable handling
* default values
* rollback safety
* soft delete consistency

Identify:

* hidden regressions
* partially fixed logic
* broken edge cases
* unsafe migrations

---

# TASK 2 — Migration Apply Order

Need exact safe migration apply order for production rollout.

Need:

* migration dependency verification
* migration ordering review
* SQLite → PostgreSQL migration safety
* production migration checklist

Need exact commands and safest rollout process.

---

# TASK 3 — SQLite Test Checklist Before Supabase Push

Need detailed test checklist for verifying app locally before PostgreSQL deployment.

Include:

* invoice creation
* invoice edit
* stock updates
* FY switching
* reports
* Decimal calculations
* transaction rollback tests
* locked month restrictions
* OCR scan flow

Goal:
catch SQLite-hidden issues before Supabase deployment.

---

# TASK 4 — Supabase Rollout / Rollback Plan

Need professional deployment strategy.

Need:

* rollout sequence
* backup strategy
* rollback steps
* migration rollback safety
* recovery process if deployment fails
* safe production update strategy

---

# TASK 5 — Previous Financial Year Readonly Protection

Currently old financial years may still be editable.

Need:

* backend enforcement
* route-level protection
* safe readonly architecture

Only active FY should allow modifications.

Historical FY should remain view-only.

---

# TASK 6 — Backend Month Lock Enforcement

Need verification whether month lock is only frontend-based.

If backend enforcement is missing:
implement route-level protection.

Locked periods must reject modifications server-side.

---

# TASK 7 — Financial Year Filtering System

Need proper FY selection/filtering for:

* reports
* invoices
* dashboard
* stock views

Need architecture-safe implementation plan.

---

# TASK 8 — Year-End Carry Forward Workflow

Critical accounting workflow still missing.

Need safe architecture for:

* stock carry forward
* balance carry forward
* advance carry forward
* opening balances
* FY closing process
* invoice numbering reset

Need implementation strategy BEFORE coding.

---

# TASK 9 — Invoice Number Concurrency Safety

Need verification that invoice numbering is safe under concurrent usage.

Need:

* duplicate prevention
* transaction-safe generation
* DB constraint review

---

# IMPORTANT WORKFLOW REQUIREMENTS

Before changing code:

1. verify actual implementation from files
2. identify affected routes/models/services
3. explain accounting risks
4. explain migration impact
5. explain rollback impact

Then generate:

* small safe patches
* targeted snippets
* minimal modifications

Avoid:

* giant rewrites
* architecture rewrites
* unnecessary refactors

---

# RESPONSE STYLE

Keep responses:

* compact
* technical
* structured
* production-oriented

Avoid long summaries and token waste.

Focus on:

* verified findings
* implementation safety
* production stability
* accounting correctness
