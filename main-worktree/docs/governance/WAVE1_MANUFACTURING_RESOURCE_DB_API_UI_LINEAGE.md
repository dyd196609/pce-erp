# Wave 1 Manufacturing Resource DB → API → UI Lineage

| Object | Model / table | DB | API | UI | Provider |
|---|---|---:|---:|---:|---|
| Workshop | `system.Workshop` / `system_workshop` | 3 | 3 | 3 | `LOADED_WITH_DATA` |
| Work Center | `pde.WorkCenter` / `pde_work_center` | 0 | 0 | 0 | `LOADED_EMPTY` |
| Operation | `system.Process` / `system_process` | 33 | 33 | 33 | `LOADED_WITH_DATA` |
| Equipment | `pde.Equipment` / `pde_equipment` | 0 | 0 | 0 | `LOADED_EMPTY` |
| Standard Capacity | `pde.StandardCapacity` / `pde_standard_capacity` | 0 | 0 | 0 | `LOADED_EMPTY` |

All use `/api/pde/a1-foundation/{entity}/`, `pdeApi`, `ProductionFoundationMaintenance`, the sole latest-template runtime, and `PceEnterpriseListTable`. Sample Workshop `WS202608000001` and Operation `PROC202608000001` matched visible UI identities. The prior all-zero appearance was a shared provider/auth failure; only Work Center, Equipment and Standard Capacity are genuine zero collections.

## Product Engineering decision and counts

Product Engineering is a domain/group container, not a standalone list. Its formal child counts are: Product Category 3; Manufacturing Process Type 14; Product Definition 0; Product Version 0; Product BOM 0; BOM Version 0; BOM Item 0; BOM Substitute 0; Routing 42; Routing Version 42; Routing Step 1137; Engineering Document 0; Engineering Document Version 0; Product Manufacturing Output 0; Engineering Source Record 1; Engineering Rule Definition 4. The automated UI run covered the registered list children used by the current shell; engineering calculation remains a specialized readiness page, not a fabricated master object.
