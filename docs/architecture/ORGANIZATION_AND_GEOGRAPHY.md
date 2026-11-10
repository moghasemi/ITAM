# ITAM — Organizational and Geographic Model

Status: approved target architecture; partial schema and authorization implementation in PR #7  
Date: 2026-11-10

## Decision

ITAM must model organizational responsibility independently from geographic location. A treatment center has exactly one organizational owner (the provincial Treatment Management unit) and a separate geographic location.

### Organizational hierarchy

`National HQ → Province → Provincial Treatment Management → Treatment Centers` (the Treatment Management ownership is stored as an explicit relational association, not as a geographic parent link).

There must be exactly one `Provincial Treatment Management` unit for each of the 31 provinces. Its stable code should be derived from the province code (for example, `IR-TM-<province-id>`). The unit belongs to exactly one province.

### Geographic hierarchy

`Geographic Province → Geographic County → Geographic City/Locality → Center`

Geographic entities must not be represented as organizational units. A center's geographic province must match the province of its organizational Treatment Management unit. County and city are separate geographic references, not parents in the organizational tree.

## Center invariants

- Every operational center has exactly one Treatment Management unit.
- Every center has a geographic province and county; city/locality is required when supported by the authoritative source.
- The organizational province and geographic province must match.
- The center's organizational owner must be the single Treatment Management unit of that province.
- Historical records with ambiguous province/county/city mapping remain unassigned or quarantined; never guess.
- Demo/test centers must be explicitly marked and use visibly synthetic codes (for example, `DEMO-*`). Demo operational records are restricted to Sistan and Baluchestan.

## Contracts and authorization

- Each contract belongs to exactly one province.
- A provincial contract covers all centers whose Treatment Management unit belongs to that province.
- Contractor access is granted only by a currently active contract whose date range includes today and whose province is active.
- All center-scoped authorization, forms, services, reports, dashboards and exports must derive province through the Treatment Management relation. No legacy geographic parent traversal may remain as an authorization boundary.
- Inactive, expired, future, suspended, or terminated contracts fail closed.

## Data baseline

The requested initial target is 413 real treatment centers. This is a project baseline requested by the product owner, not a claim about the current live count. Public reports have conflicting counts (413 and 408); the dataset must therefore record source, publication/effective date, retrieval date, and verification status.

Do not manufacture a 413-row list. Import only named centers supported by a traceable authoritative source. If the complete list cannot be verified, stop the import and report the gap rather than filling missing rows with fabricated data.

The repository loader supplies 31 province records and 484 county records. PR #7 adds one `TreatmentManagement` row per province and a separate `Center.treatment_management` ownership relation; existing county → province remains the geographic location relation for compatibility. `Center.city` is still a legacy free-text value: normalized city/locality entities are not implemented. The loader does not supply a verified city/locality dataset or the 413 treatment-center directory. These sources must be independently verified before production seeding.

## Migration and rollout sequence

1. **Implemented in PR #7:** add the one-to-one Treatment Management unit per province.
2. **Implemented in PR #7:** add the explicit `Center.treatment_management` ownership relation and backfill deterministic existing county → province mappings.
3. **Implemented in PR #7:** update province-bound contract coverage and contractor, asset, ticket and maintenance scope paths to use Treatment Management ownership.
4. **Implemented in PR #7:** create/update the 31 Treatment Management units through the Iran geography loader and add regression tests for ownership, province matching and loader idempotence.
5. Still required: add normalized geographic city/locality entities and source metadata; retain legacy free-text city until verified mappings are available.
6. Still required: audit every remaining report, dashboard, template and reconciliation path for legacy geographic traversals.
7. Still required: import the verified center dataset with provenance; assert exactly 413 verified real records only after the source list is complete.
8. Keep synthetic operational demo data restricted to Sistan and Baluchestan and mark every demo record explicitly.
9. Only after CI and local tests pass, prepare a separately approved local SQLite rebuild. Never reset production data.

## Compatibility and safety

- Do not reinterpret the current `OrganizationalUnit` county records as permanent geographic records without an explicit migration strategy.
- Do not drop legacy fields/relations in the same migration that introduces the new schema. Use an expand → backfill → switch consumers → validate → contract sequence.
- Do not use reconciliation auto-apply to assign ambiguous centers.
- Keep all existing reconciliation CSV files untouched.
- This document distinguishes completed schema work from outstanding geographic normalization and center-directory sourcing. PR #7 is not ready to merge until CI and local validation pass.


## Public count evidence and provenance (reviewed 2026-11-10)

The count of treatment centers is not yet a reliable import key or proof of a complete directory:

- The Social Security Organization newsroom reported **413 treatment centers** in its 1404 performance summary: https://newsroom.tamin24.ir/news/tshrh-trh-aamlt-gdd-dr-hozh-tmn-gtmaa/
- A separate 1404 report quoting the organization's latest statistics reported **408 owned treatment centers**, broken down as 75 hospitals, 329 outpatient centers and 4 limited-surgery centers: https://tamin24.ir/news/31298

These public figures conflict. They may reflect different reporting dates, definitions, or revisions; the repository must not silently choose one or synthesize missing entries. The product owner's requested 413-row baseline remains a target pending an authoritative, name-level directory from the organization.

The current `data/iran_admin/provinces.json` and `counties.json` files contain province/county labels and IDs, but do not carry a source URL, source publication date, retrieval timestamp, or verification metadata. Treat them as operational seed data, not as a fully provenance-verified official geographic registry. No city/locality file or named 413-center directory is present in this branch.

## Read-only data audit

PR #7 adds:

```powershell
python manage.py audit_organization_data
python manage.py audit_organization_data --format json
```

The command checks center county/province/management relationships, missing management assignments, inactive management warnings, demo-code consistency, missing legacy city labels, and contract province validity. It is read-only: it does not infer mappings, update records, or repair errors. A non-zero command exit means one or more critical inconsistencies were found and must be reviewed before any rebuild or import.
