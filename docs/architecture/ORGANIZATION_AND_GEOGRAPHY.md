# ITAM — Organizational and Geographic Model

Status: approved target architecture; implementation plan  
Date: 2026-11-10

## Decision

ITAM must model organizational responsibility independently from geographic location. A treatment center has exactly one organizational owner (the provincial Treatment Management unit) and a separate geographic location.

### Organizational hierarchy

`National HQ → Province → Provincial Treatment Management → Treatment Centers`

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

The current repository geography loader supplies 31 provinces and 484 counties. It does not yet supply a verified city/locality dataset or the 413 treatment-center directory. These sources must be independently verified before production seeding.

## Migration and rollout sequence

1. Add separate geographic province, county and city/locality entities, with stable source codes and source metadata.
2. Add the one-to-one Treatment Management unit per province.
3. Add explicit center relations to Treatment Management and geographic entities.
4. Backfill only deterministic mappings from existing county → province relationships; preserve unresolved records for review.
5. Update all access scopes and query paths (accounts, contracts, tickets, assets, maintenance, reports, dashboards, forms, admin and templates).
6. Add database constraints and model/service validation for province consistency and unique Treatment Management per province.
7. Add regression tests for cross-province isolation, inactive/expired/future contracts, null/ambiguous legacy mappings, and every affected workflow.
8. Import the verified center dataset with provenance; assert exactly 413 verified real records only after the source list is complete.
9. Keep synthetic operational demo data restricted to Sistan and Baluchestan and mark every demo record explicitly.
10. Only after CI and local tests pass, prepare a separately approved local SQLite rebuild. Never reset production data.

## Compatibility and safety

- Do not reinterpret the current `OrganizationalUnit` county records as permanent geographic records without an explicit migration strategy.
- Do not drop legacy fields/relations in the same migration that introduces the new schema. Use an expand → backfill → switch consumers → validate → contract sequence.
- Do not use reconciliation auto-apply to assign ambiguous centers.
- Keep all existing reconciliation CSV files untouched.
- This document records the target architecture; it does not claim that the schema, center directory, or migration has already been implemented.
