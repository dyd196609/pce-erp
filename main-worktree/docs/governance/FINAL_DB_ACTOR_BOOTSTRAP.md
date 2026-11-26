# Final DB Actor Bootstrap

- Run ID: `W1FI-A4-MANUAL-20260911-001`
- Final DB: `D:\Dev-PCE\work\wave1_actor_binding_manual_a4_20260911_001.sqlite3`
- Production DB used for writes: NO
- Customer baseline: 89
- Sessions after bootstrap: 0
- Maintenance user: 14 / `wave1_import_maintenance_a4`
- Employee: 109 / `W1AC-A4-E1` / active
- Position: 36 / `W1AC-A4-20260911` / enabled and effective
- Responsibility: 57 / `W1AC-A4-20260911-RESP` / active and effective
- Role: 18 / `W1AC-A4-20260911-ROLE`
- Organization: 1
- Customer permission: `masterdata.customer.maintain` = ALLOWED
- Staff/superuser: false / false

The automated HTTP actor and manual actor both call `bootstrap_rehearsal_actors` through `bootstrap_wave1_formal_import_actor.py`. No alternate fixture or second Employee/Position/Responsibility was created in the final DB.

Old A3 cleanup completed: two temporary users disabled, one Employee inactive, one Position disabled, one Responsibility suspended and two copied sessions deleted. The preflight instance is recoverably archived at `D:\Dev-PCE\work\wave1_actor_binding_manual_a4_20260911_001.preflight-archived.sqlite3`; it is not served.
