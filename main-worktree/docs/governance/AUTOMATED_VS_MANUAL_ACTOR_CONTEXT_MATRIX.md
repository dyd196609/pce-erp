# Automated vs Manual Actor Context Matrix

| Dimension | Earlier automated nine-object run | User-observed manual run | Corrective run |
|---|---|---|---|
| User | constructed non-staff/non-superuser test user | `wave1_formal_import_gate`; delivered session/database state uncertain | `wave1_import_maintenance_a3`, user ID 14 |
| Employee | linked, active | retained DB now shows ID 109; state at failure indeterminate | ID 109, `W1AC-A3-E1`, active |
| Employment | active | retained DB now active | active |
| Position | linked | retained DB now ID 36 | ID 36, `W1AC-A3-20260911` |
| Position status | enabled/effective | retained DB now active | enabled and effective |
| Responsibility | formal model + position mapping | retained DB now responsibility ID 57 | ID 57, `W1AC-A3-20260911-RESP` |
| Responsibility validity | active/effective | retained DB now valid | active from 2026-09-11 |
| Permission | seven Wave 1 permissions | retained DB now seven permissions | least-privilege seven permissions |
| Organization scope | organization assignment | retained DB now organization 1 | organization 1 |
| Company scope | company-aligned actor/position | retained DB now company 1 | company 1 |
| Actor ID | test actor resolved by service | numeric JWT `user_id` could resolve against another isolated DB copy | fresh user ID 14 in one pinned isolated DB |
| Write context | `APIClient.force_authenticate`; bypassed login only, not AuthorizationService or actor-chain guard | real browser/JWT; stale session/database delivery possible | Django test + nine XLSX runtime + live HTTP login/Preview |
| Result | Commit/readback/replay PASS 9/9 | Preview PASS; Commit FAIL | automated Commit/replay PASS 9/9; manual Commit/replay pending |

The automated actor was not a privileged service actor and did not bypass Employee, Position or Responsibility. `force_authenticate` bypassed only token/login transport. The corrective adds live HTTP evidence so token transport and the formal actor chain are both covered, while preserving user manual validation as a separate final gate.
