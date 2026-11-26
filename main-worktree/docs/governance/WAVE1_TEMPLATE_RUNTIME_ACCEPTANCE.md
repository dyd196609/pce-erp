# Wave 1 Template Runtime Acceptance

| Check | Result |
|---|---|
| sole template ID | PASS — `PCE-LATEST-BASE-DATA-TEMPLATE-V1.0` |
| corrective scope | PASS — Customer, Supplier, Material, Product Definition, Product Engineering children, Manufacturing Resource |
| provider continuity static gate | PASS — 27 mappings |
| authenticated controlled runtime | PASS — 23 list pages |
| DB/API/UI count and identity | PASS for automated evidence |
| loaded-empty/read-failed separation | PASS |
| capability non-regression | PASS |
| direct Vite production compilation | PASS |
| full build | PASS — `npm run build`, exit 0 |
| user manual validation | FAIL — user evidence controls until explicit revalidation PASS |

The in-app-browser controlled-origin readback was blocked by the user's saved Browser Use permission; it was not bypassed. Headless Chrome evidence and an explicit manual route/count handoff are available in `WAVE1_DATA_PROVIDER_RUNTIME_ACCEPTANCE.md`.
