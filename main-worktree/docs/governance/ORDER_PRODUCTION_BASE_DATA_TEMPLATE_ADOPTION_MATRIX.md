# Order / Production Base Data Template Adoption Matrix

## Latest minimal closure — 2026-09-11 22:16 +08:00

This section supersedes the earlier current assessment below. A4/B4/C4 human PASS preserved; each original-file formal HTTP replay now PASS with CREATE=0/MATCH=1 and unchanged full-table data/counts 91/271/4. Actual Actor/DB/runtime ownership confirmed; temporary identities and sessions invalidated; owned services stopped. Replay and actor ownership are no longer open gaps.

| Page | Current total | Current adoption decision / remaining condition |
|---|---:|---|
| Customer | 91 | NOT UPGRADED: current full npm build Exit 1; adoption assertion hardcodes old status |
| Supplier | 121 | NOT UPGRADED: same final build/adoption-gate conditions |
| Material | 271 | NOT UPGRADED: same final build/adoption-gate conditions |
| Product Definition | 0 | NOT UPGRADED: same final build/adoption-gate conditions |
| Workshop | 4 | NOT UPGRADED: same final build/adoption-gate conditions |
| Operation | 33 | NOT UPGRADED: same conditions; independent protectedBaseline PRESERVED |
| WorkCenter | 0 | NOT UPGRADED: same final build/adoption-gate conditions |
| Equipment | 0 | NOT UPGRADED: same final build/adoption-gate conditions |
| Standard Capacity | 0 | NOT UPGRADED: same final build/adoption-gate conditions |

Full build failed in prebuild incoming-inspections navigation (page.goto 45s timeout), not at an import assertion. The separate existing adoption gate unconditionally requires `ADOPTING_IMPORT_ACTOR_CONTEXT_BLOCKED`; the current instruction prohibits editing test assertions. Machine metadata remains unchanged, and those historical labels must not be read as current Actor failure or missing human acceptance. No new authority/registry was created. See FINAL_CONSOLIDATED and the existing evidence directory's CLOSURE_* records. Whole-module governance/FROZEN status is unchanged.

## Previous 2026-09-11 final-closure assessment (historical)

Instruction `WAVE1-LATEST-TEMPLATE-IMPORT-FINAL-CLOSURE-20260911-001`: Customer A4, Material B4 and Workshop C4 user manual import = PASS. Their original-file fingerprints match creation audits 2447/2448/2449 and each business identity exists once. Current unfiltered DB totals are 91/271/4; Customer also contains the separately audited A3 identity. Older READY/PENDING statements below are historical, not a rejection of the latest user decision.

| Page | Current adoption assessment | Specific remaining closure evidence |
|---|---|---|
| Customer | NOT UPGRADED | A4 replay attribution/count discrepancy; final code/build version |
| Supplier | NOT UPGRADED | Representative replay coverage and final code/build version |
| Material | NOT UPGRADED | Second successful request lacks same-file/result linkage; final code/build version |
| Product Definition | NOT UPGRADED | Representative replay coverage and final code/build version |
| Workshop | NOT UPGRADED | Second successful request lacks same-file/result linkage; final code/build version |
| Operation | NOT UPGRADED; protectedBaseline preserved | Representative replay coverage and final code/build version |
| WorkCenter | NOT UPGRADED | Representative replay coverage and final code/build version |
| Equipment | NOT UPGRADED | Representative replay coverage and final code/build version |
| Standard Capacity | NOT UPGRADED | Representative replay coverage and final code/build version |

No second machine registry was created. The existing machine authority was not modified after the explicit exception stop; its actor-blocked labels are stale historical state, not the current human result. Normalizing those labels and running the affected gate remains an explicit unfinished task after the evidence gaps are resolved. See `FINAL_CONSOLIDATED.md` and `evidence/wave1-final-closure-20260911/`.

## Historical pre-acceptance projection

Scope authority: 27 canonical modules from `foundationEntryUnificationRegistry.js`. Machine authority: `orderProductionBaseDataTemplateAdoption.js`. Template authority remains `PCE-LATEST-BASE-DATA-TEMPLATE-V1.0`.

| Domain | Modules | Status |
|---|---|---|
| Wave 1 order/supply | customer, supplier, material | data/template/preview user PASS; `ADOPTING_IMPORT_ACTOR_CONTEXT_BLOCKED` |
| Wave 1 product | product-definition | data/template user PASS at connected 0/0/0; `ADOPTING_IMPORT_ACTOR_CONTEXT_BLOCKED` |
| Product engineering | product-category, manufacturing-process-type, product-version, BOM family, documents, manufacturing-output, engineering-source-record | only product-definition received current user PASS; remaining module-specific validation not inferred |
| Protected engineering | routing, routing-version, routing-step | `ADOPTING_PROTECTED_BASELINE`; provider continuity preserved |
| Engineering calculation | engineering-calculation | specialized read-only readiness page; import not applicable |
| Manufacturing resource | workshop, work-center, equipment, capacity | data/template/preview user PASS at 3/0/0/0; `ADOPTING_IMPORT_ACTOR_CONTEXT_BLOCKED` |
| Protected manufacturing | operation | data/template user PASS at 33; `ADOPTING_IMPORT_ACTOR_CONTEXT_BLOCKED`; protected-baseline marker preserved |
| Other backlog | uom, warehouse, warehouse-location | `ADOPTING`; outside corrective Wave 1 manual decision |

Customer, Supplier, Material, Product Definition, Workshop, Work Center, Operation, Equipment and Standard Capacity are `ADOPTING_IMPORT_ACTOR_CONTEXT_BLOCKED`. The backend core is automated-PASS; user-visible Commit/Replay through the formal actor chain remains pending. No status becomes `ADOPTED` before that user gate passes.
