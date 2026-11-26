# Migration Data Operation B-Class Evidence Record V1.0

## 1. 证据边界

- Source Commit：`969a86fe4a1b8557e8c837d19c58e9a9cc5d8fba`
- 证据来源：Git blob静态读取；未执行Migration、函数、SQL或数据库连接。
- Blob SHA256：对Git blob原始字节计算SHA256。
- 决策含义：仅确认隔离Replay的数据操作边界，不构成执行授权。

## 2. Evidence Record基础信息索引

所有记录的Git Commit均为`969a86fe4a1b8557e8c837d19c58e9a9cc5d8fba`。

|ID|App|Migration|Operation Type|Function / Line Range|File Path|Blob SHA256|Decision|
|---|---|---|---|---|---|---|---|
|B01|masterdata|0004_enterprise_procurement_dimensions_r4|RunPython / Seed|seed_enterprise_dimensions 5–25|backend/masterdata/migrations/0004_enterprise_procurement_dimensions_r4.py|51A6D56820B146E73AB4805CB43B8F04F7C943487BEAA5883268C20F8DD26DE1|C REDESIGN REQUIRED|
|B02|masterdata|0009_unit_and_code_governance_a1|RunPython + RunSQL|link_existing_units 5–27；RunSQL入口64|backend/masterdata/migrations/0009_unit_and_code_governance_a1.py|68A5CCDFDF53BBFEA340BD421AB6415ED5B8D5AA5262E6723256B7F97C77D014|A APPROVE FOR REPLAY|
|B03|masterdata|0011_foundation_identity_uom_and_encoders|RunPython / Seed|establish_uom_governance_and_code_rules 8–36；reverse_governance_seed 37–49|backend/masterdata/migrations/0011_foundation_identity_uom_and_encoders.py|BC97BEB0280462F3F71755FED85AF81C340E8693A2D2AB5AE6A10242C98E156D|C REDESIGN REQUIRED|
|B04|masterdata|0012_standard_uom_initialization_v12|RunPython / Seed|seed_standard_units 16–45；remove_standard_units 46–56|backend/masterdata/migrations/0012_standard_uom_initialization_v12.py|FA0BFAC859741410A66D6784B7E1878F0995ED80C7A327661743BDC1ADCF3888|C REDESIGN REQUIRED|
|B05|pde|0007_production_master_permissions_and_codes_a1|RunPython / Permission + CodeRule Seed|configure_a1_governance 27–54|backend/pde/migrations/0007_production_master_permissions_and_codes_a1.py|1DCF865C5EE1BD4445767D85E8BF5F91EF8E188E61E3D3B1467F595DEE31DF15|C REDESIGN REQUIRED|
|B06|pde|0010_engineering_permissions_a15|RunPython / Permission Seed|configure_engineering_permissions 14–33|backend/pde/migrations/0010_engineering_permissions_a15.py|2E3C5D2D909D7462644785E91A0F1B95CB272D7E22D9AAFA0DB68DF4F421CD7D|A APPROVE FOR REPLAY|
|B07|pde|0011_plan_operator_engineering_authority_a15|RunPython / RolePermission Seed|grant_existing_plan_operator_authority 21–36|backend/pde/migrations/0011_plan_operator_engineering_authority_a15.py|7C945D1BDB7C16A8100D9AD82A982CC400E298D62F6108E23B5CE944E68533E7|C REDESIGN REQUIRED|
|B08|pde|0013_production_unified_model_permissions_a17|RunPython / Permission + CodeRule Seed|configure_a17_authority 20–51|backend/pde/migrations/0013_production_unified_model_permissions_a17.py|DE2567F83C89E4614B531AFEEB1AE010372F182F29316A268F7B9F695E478546|C REDESIGN REQUIRED|
|B09|pde|0017_engineering_rule_foundation_do2|RunPython / Permission Seed|configure_do2_rule_authority 12–31|backend/pde/migrations/0017_engineering_rule_foundation_do2.py|392102B1EFDA42D4D12E2D26B82B22DF21E986C37283676CA61351ED0FFD174E|C REDESIGN REQUIRED|
|B10|pde|0018_engineering_calculation_closure_do3|RunPython / Backfill + Permission Seed|preserve_existing_calculation_evidence 11–27；configure_do3_authority_and_codes 28–56|backend/pde/migrations/0018_engineering_calculation_closure_do3.py|18E5D0B85490CC48BC2FFEC5C9EE1F28F6506EBC84D84F4044A6D623CF1A3A65|C REDESIGN REQUIRED|
|B11|pde|0021_group3a_operation_executor_authority|RunPython / RolePermission Seed|grant_operation_authority 4–23；revoke_operation_authority 24–31|backend/pde/migrations/0021_group3a_operation_executor_authority.py|2280B16E33B0339975559FF8C14CAACB2706803A78B243904EFEAAB6581A93D1|A APPROVE FOR REPLAY|
|B12|pde|0030_order_engineering_baseline|RunPython / Permission Seed|create_baseline_permissions 5–16|backend/pde/migrations/0030_order_engineering_baseline.py|3B7F450DB1C69388718D8B10C51A6D7E70867726073B402B064D528BB4BCD846|A APPROVE FOR REPLAY|
|B13|planning|0002_planning_access_workflow_v1|RunPython / Permission + Workflow Seed|seed_planning_access 22–59|backend/planning/migrations/0002_planning_access_workflow_v1.py|477335B340AAB999D6B497F27F32A3EE7B6B1B6A40136571F1840A010C3D6BDF|C REDESIGN REQUIRED|
|B14|procurement|0024_purchase_fulfillment_inventory_v1|RunPython / Role + Permission + Workflow + Warehouse Seed|seed_fulfillment_foundation 33–122|backend/procurement/migrations/0024_purchase_fulfillment_inventory_v1.py|620CCF75CE28612CBD02F3F2EF7DB623A9A00B48CE9471F57F5E1C312E2C982A|C REDESIGN REQUIRED|
|B15|procurement|0028_completed_module_read_permissions|RunPython / Permission Seed|register_read_permissions 14–22；unregister_read_permissions 23–27|backend/procurement/migrations/0028_completed_module_read_permissions.py|59EE75C5A8D8E7FBBD6767DF4B3601CE008B4DA0B3D0D3E0DCB188534D88EAC9|A APPROVE FOR REPLAY|
|B16|sales|0003_industrial_order_engineering_input_do1|RunPython / Permission + Workflow Seed|seed_engineering_input_authority 10–59|backend/sales/migrations/0003_industrial_order_engineering_input_do1.py|AC3CF9171D47567939929831ABAC632C5C8BF5AC57A06291FB1EE73BF744B989|C REDESIGN REQUIRED|
|B17|sales|0004_order_operating_system_v1|RunPython / Role + Permission + Workflow Seed|seed_order_operating_authority 22–60|backend/sales/migrations/0004_order_operating_system_v1.py|FF3781CACB657FFD8A95D8090EC147CCBF07670B57EAB75560DB69CF00BB62F8|C REDESIGN REQUIRED|
|B18|supplier_performance|0006_formal_supplier_settlement_14_22_v1|RunPython / Role + Permission + Workflow Seed|seed_formal_foundation 39–117|backend/supplier_performance/migrations/0006_formal_supplier_settlement_14_22_v1.py|C32A465034B070FA1D135B2AF37D243F9E681796874A62672F5E2B71962F3A0A|C REDESIGN REQUIRED|
|B19|system|0004_erp_access_foundation|RunPython / RBAC Seed|seed_access_foundation 39–81|backend/system/migrations/0004_erp_access_foundation.py|3ECA8C834C1D875D10677664A97DDB9D3EB0861838D7A95F65E4BAE7DFA8779C|A APPROVE FOR REPLAY|
|B20|system|0005_organization_access_core_v1|RunPython / Permission + Legacy Authority Projection|_business_hash 11–20；seed_access_core_v1 21–87|backend/system/migrations/0005_organization_access_core_v1.py|B2228D240EF3027B3C1665078ACA5E3639E122AF5118A4AC1C72B14A7C22CD6A|A APPROVE FOR REPLAY|
|B21|system|0006_enterprise_organization_model_v1|RunPython / Organization Projection|seed_existing_organization_hierarchy 7–53|backend/system/migrations/0006_enterprise_organization_model_v1.py|AD76F5504530A4B0FE5DACCB8EDD6A5267A2DEADEF561B4424B945341ACE1D8A|A APPROVE FOR REPLAY|
|B22|system|0007_remove_department_cost_center_and_more|RunPython / Enum Migration + Permission Seed|migrate_ownership_types 18–24；seed_organization_operating_permissions 25–40|backend/system/migrations/0007_remove_department_cost_center_and_more.py|7DEC89ECC6EEDC79BFF291C462B6328BC0839DE6F37F615520E6AD493D2B5130|A APPROVE FOR REPLAY|

## 3. Evidence Records

### B01 — masterdata.0004_enterprise_procurement_dimensions_r4

|字段|内容|
|---|---|
|App / Migration|`masterdata` / `0004_enterprise_procurement_dimensions_r4`|
|Operation Type|RunPython / 基础及业务数据Seed|
|Function / Lines|`seed_enterprise_dimensions`，5–25；入口53|
|File Path|`backend/masterdata/migrations/0004_enterprise_procurement_dimensions_r4.py`|
|Git Commit|`969a86fe4a1b8557e8c837d19c58e9a9cc5d8fba`|
|Blob SHA256|`51A6D56820B146E73AB4805CB43B8F04F7C943487BEAA5883268C20F8DD26DE1`|
|调用链|RunPython → 查询Department(code=`CGB`) → `get_or_create` ProjectMaster/CostCenter/ExpenseCategory/BudgetCategory → 保留6组固定编码事实|
|数据影响|创建项目、成本中心、费用分类、预算分类；不删除；不改权限。|
|输入依赖|system.Department；依赖固定部门码及固定PCE项目/采购语义，不依赖正式订单。|
|幂等|业务键存在时不重复，但不会校正既有值；重复执行结果受前置数据影响。|
|Reverse|`RunPython.noop`；所有Seed残留。|
|风险|高：创建特定项目和组织业务事实，不是通用Schema必需数据。|
|Replay建议|**C — REDESIGN REQUIRED**：拆分Schema与可配置基础资料初始化，禁止固定项目/部门Seed。|

### B02 — masterdata.0009_unit_and_code_governance_a1

|字段|内容|
|---|---|
|App / Migration|`masterdata` / `0009_unit_and_code_governance_a1`|
|Operation Type|RunPython + RunSQL|
|Function / Lines|`link_existing_units`，5–27；RunPython入口62；RunSQL入口64|
|File Path|`backend/masterdata/migrations/0009_unit_and_code_governance_a1.py`|
|Git Commit|同上|
|Blob SHA256|`68A5CCDFDF53BBFEA340BD421AB6415ED5B8D5AA5262E6723256B7F97C77D014`|
|调用链|RunPython → 遍历Material → 按company_id+文本单位`get_or_create` UOM → 更新Material外键；RunSQL → `CREATE TABLE IF NOT EXISTS code_rule`|
|数据影响|可能创建UOM并更新Material；SQL创建`code_rule`表和唯一约束；不改权限。|
|输入依赖|Material.unit、purchase_unit、company_id；空库无Material时仅Schema操作。|
|幂等|UOM有唯一约束，Material覆盖为相同外键；SQL使用IF NOT EXISTS，可重复。|
|Reverse|RunPython为noop；RunSQL以`DROP TABLE IF EXISTS code_rule`反向。隔离空库无业务残留。|
|风险|中：非空业务库会改写Material；本批准严格限于全新隔离空库。|
|Replay建议|**A — APPROVE FOR REPLAY**：仅R4隔离空库，F1/F2必须一致。|

### B03 — masterdata.0011_foundation_identity_uom_and_encoders

|字段|内容|
|---|---|
|App / Migration|`masterdata` / `0011_foundation_identity_uom_and_encoders`|
|Operation Type|RunPython / UOM规范化及CodeRule Seed|
|Function / Lines|`establish_uom_governance_and_code_rules` 8–36；`reverse_governance_seed` 37–49；入口169|
|File Path|`backend/masterdata/migrations/0011_foundation_identity_uom_and_encoders.py`|
|Git Commit|同上|
|Blob SHA256|`BC97BEB0280462F3F71755FED85AF81C340E8693A2D2AB5AE6A10242C98E156D`|
|调用链|RunPython → 按固定中文/毫米代码重分类全部UOM → 固定company_id=1创建物料/车间编码规则|
|数据影响|批量修改UOM；创建2条CodeRule；修改基础资料与配置。|
|输入依赖|既有UOM；硬编码COUNT_CODES、`mm`及company_id=1。|
|幂等|重复执行稳定，但把未知单位强制设为other，且固定公司前提不可移植。|
|Reverse|重置全部UOM维度/符号并仅删除current_seq=0规则；不能恢复原值，反向不完整。|
|风险|高：写死公司、语言/代码规则并破坏原值可追溯性。|
|Replay建议|**C — REDESIGN REQUIRED**：配置驱动单位分类和按Plant/Company授权的编码规则。|

### B04 — masterdata.0012_standard_uom_initialization_v12

|字段|内容|
|---|---|
|App / Migration|`masterdata` / `0012_standard_uom_initialization_v12`|
|Operation Type|RunPython / 标准UOM Seed|
|Function / Lines|`seed_standard_units` 16–45；`remove_standard_units` 46–56；入口64|
|File Path|`backend/masterdata/migrations/0012_standard_uom_initialization_v12.py`|
|Git Commit|同上|
|Blob SHA256|`FA0BFAC859741410A66D6784B7E1878F0995ED80C7A327661743BDC1ADCF3888`|
|调用链|RunPython → 固定6种单位 → company_id=1 `get_or_create`/覆盖 → reverse按代码删除|
|数据影响|创建或强制修改6项UOM基础资料。|
|输入依赖|固定company_id=1；不读取正式业务事实。|
|幂等|重复后数据稳定，但会覆盖同码既有定义。|
|Reverse|删除固定公司/代码；若被PROTECT引用会失败，且不能恢复被覆盖的旧值。|
|风险|高：固定公司及覆盖行为不符合通用主数据治理。|
|Replay建议|**C — REDESIGN REQUIRED**：采用全局标准单位模板＋公司启用关系，不直接覆盖公司事实。|

### B05 — pde.0007_production_master_permissions_and_codes_a1

|字段|内容|
|---|---|
|Operation Type|RunPython / Permission、RolePermission、CodeRule Seed|
|Function / Lines|`configure_a1_governance` 27–54；入口61|
|File / SHA256|`backend/pde/migrations/0007_production_master_permissions_and_codes_a1.py` / `1DCF865C5EE1BD4445767D85E8BF5F91EF8E188E61E3D3B1467F595DEE31DF15`|
|调用链|RunPython → upsert 7项production权限 → 可选绑定`PLAN_OPERATOR_V1` → company_id=1创建9项CodeRule|
|数据影响|修改权限、角色授权及编码配置；含BOM/Routing维护权限。|
|输入依赖|Role、Permission、CodeRule；固定角色码、公司1和production前缀。|
|幂等|业务键层面幂等；固定公司与角色前提导致环境相关结果。|
|Reverse|noop；权限、授权和CodeRule全部残留。|
|风险|高：PLAN角色跨域、正式BOM关闭、固定公司。|
|Replay建议|**C — REDESIGN REQUIRED**：按EMD/PDE/MES领域拆分权限和公司配置。|

### B06 — pde.0010_engineering_permissions_a15

|字段|内容|
|---|---|
|Operation Type|RunPython / Permission Seed与派生角色授权|
|Function / Lines|`configure_engineering_permissions` 14–33；入口36|
|File / SHA256|`backend/pde/migrations/0010_engineering_permissions_a15.py` / `2E3C5D2D909D7462644785E91A0F1B95CB272D7E22D9AAFA0DB68DF4F421CD7D`|
|调用链|RunPython → upsert 6项工程权限 → 查询已有产品/BOM/Routing维护角色 → 给同一角色补工程权限|
|数据影响|创建/更新Permission和RolePermission；无业务数据。|
|输入依赖|前置Permission及RolePermission；空库结果由固定迁移链确定。|
|幂等|update_or_create/get_or_create，重复安全且唯一键稳定。|
|Reverse|noop；隔离库保留权限记录，靠库销毁清理。|
|风险|中：权限扩展明确，但属于PDE工程能力且不开放执行状态。|
|Replay建议|**A — APPROVE FOR REPLAY**：仅隔离Replay并纳入权限Fingerprint。|

### B07 — pde.0011_plan_operator_engineering_authority_a15

|字段|内容|
|---|---|
|Operation Type|RunPython / 跨域RolePermission Seed|
|Function / Lines|`grant_existing_plan_operator_authority` 21–36；入口40–42|
|File / SHA256|`backend/pde/migrations/0011_plan_operator_engineering_authority_a15.py` / `7C945D1BDB7C16A8100D9AD82A982CC400E298D62F6108E23B5CE944E68533E7`|
|调用链|RunPython → 查询`PLAN_OPERATOR_V1` → 查询13项主数据/工程权限 → 全量绑定|
|数据影响|扩展PLAN角色到BOM、Routing、工程发布和主数据维护。|
|输入依赖|既有PLAN角色与权限；不存在角色时静默跳过。|
|幂等|get_or_create防重复，但结果依赖角色是否预先存在。|
|Reverse|noop；授权残留。|
|风险|高：违反领域职责分离，且涉及关闭的BOM能力。|
|Replay建议|**C — REDESIGN REQUIRED**：使用领域角色和显式授权配置，不由Migration跨域赋权。|

### B08 — pde.0013_production_unified_model_permissions_a17

|字段|内容|
|---|---|
|Operation Type|RunPython / Permission、RolePermission、CodeRule Seed|
|Function / Lines|`configure_a17_authority` 20–51；入口58|
|File / SHA256|`backend/pde/migrations/0013_production_unified_model_permissions_a17.py` / `DE2567F83C89E4614B531AFEEB1AE010372F182F29316A268F7B9F695E478546`|
|调用链|RunPython → upsert 6项权限 → 绑定PLAN角色 → 遍历Company为3类对象创建CodeRule|
|数据影响|权限扩展和每公司编码配置。|
|输入依赖|Company、PLAN角色；公司集合决定输出数量。|
|幂等|业务键幂等，但不同前置Company集合产生不同Fingerprint。|
|Reverse|noop；全部残留。|
|风险|高：跨域PLAN赋权及环境依赖Seed。|
|Replay建议|**C — REDESIGN REQUIRED**：权限配置与公司CodeRule初始化分离并纳入显式输入Manifest。|

### B09 — pde.0017_engineering_rule_foundation_do2

|字段|内容|
|---|---|
|Operation Type|RunPython / 工程规则Permission与PLAN角色授权|
|Function / Lines|`configure_do2_rule_authority` 12–31；入口35|
|File / SHA256|`backend/pde/migrations/0017_engineering_rule_foundation_do2.py` / `392102B1EFDA42D4D12E2D26B82B22DF21E986C37283676CA61351ED0FFD174E`|
|调用链|RunPython → upsert 4项工程规则权限 → 可选绑定`PLAN_OPERATOR_V1`|
|数据影响|权限及跨域角色授权。|
|输入依赖|PLAN角色是否存在。|
|幂等|不重复，但输出随前置角色存在性变化。|
|Reverse|noop；残留。|
|风险|高：PLAN角色获得PDE规则创建、修改、发布权。|
|Replay建议|**C — REDESIGN REQUIRED**。|

### B10 — pde.0018_engineering_calculation_closure_do3

|字段|内容|
|---|---|
|Operation Type|两段RunPython：工程事实回填＋权限/CodeRule Seed|
|Function / Lines|`preserve_existing_calculation_evidence` 11–27；`configure_do3_authority_and_codes` 28–56；入口117、125|
|File / SHA256|`backend/pde/migrations/0018_engineering_calculation_closure_do3.py` / `18E5D0B85490CC48BC2FFEC5C9EE1F28F6506EBC84D84F4044A6D623CF1A3A65`|
|调用链|RunPython1 → 回填Calculation company/scope/source/item及DerivedFact canonical_field；RunPython2 → upsert权限 → 绑定PLAN角色 → 每Company创建CodeRule|
|数据影响|修改工程事实；创建权限、授权及编码配置。|
|输入依赖|既有工程实例、来源、订单行、Company和PLAN角色。|
|幂等|回填值稳定；Seed业务键幂等，但结果依赖业务事实和公司集合。|
|Reverse|两段均noop；工程回填及权限/规则残留。|
|风险|高：混合数据回填与跨域权限，不能独立白名单。|
|Replay建议|**C — REDESIGN REQUIRED**：拆分纯回填与治理Seed。|

### B11 — pde.0021_group3a_operation_executor_authority

|字段|内容|
|---|---|
|Operation Type|RunPython / 最小角色权限投影|
|Function / Lines|`grant_operation_authority` 4–23；`revoke_operation_authority` 24–31；入口39|
|File / SHA256|`backend/pde/migrations/0021_group3a_operation_executor_authority.py` / `2280B16E33B0339975559FF8C14CAACB2706803A78B243904EFEAAB6581A93D1`|
|调用链|RunPython → get_or_create企业主数据维护角色 → get既有资源维护Permission → get_or_create单一RolePermission；reverse删除该绑定|
|数据影响|创建角色（如缺失）并绑定单一权限。|
|输入依赖|`production.master_data.resource.maintain`必须由前置迁移存在。|
|幂等|角色和绑定均以稳定编码幂等。|
|Reverse|删除绑定但保留新建角色；残留角色必须进入Fingerprint。|
|风险|中：反向不完全，但投影最小且与EMD/MES资源治理一致。|
|Replay建议|**A — APPROVE FOR REPLAY**：记录残留角色合同。|

### B12 — pde.0030_order_engineering_baseline

|字段|内容|
|---|---|
|Operation Type|RunPython / Permission Seed|
|Function / Lines|`create_baseline_permissions` 5–16；入口83|
|File / SHA256|`backend/pde/migrations/0030_order_engineering_baseline.py` / `3B7F450DB1C69388718D8B10C51A6D7E70867726073B402B064D528BB4BCD846`|
|调用链|RunPython → upsert baseline.save与baseline.confirm两个PDE权限 → 结束|
|数据影响|仅Permission，无角色绑定和业务数据。|
|输入依赖|system.Permission表。|
|幂等|稳定权限编码，重复安全。|
|Reverse|noop；隔离库销毁。|
|风险|中低：不推进基线状态，不创建基线事实。|
|Replay建议|**A — APPROVE FOR REPLAY**。|

### B13 — planning.0002_planning_access_workflow_v1

|字段|内容|
|---|---|
|Operation Type|RunPython / Permission及计划Workflow Seed|
|Function / Lines|`seed_planning_access` 22–59；入口67|
|File / SHA256|`backend/planning/migrations/0002_planning_access_workflow_v1.py` / `477335B340AAB999D6B497F27F32A3EE7B6B1B6A40136571F1840A010C3D6BDF`|
|调用链|RunPython → upsert5项计划权限 → 创建Demand→Requirement→PurchasePlan/ProductionPlan流程及4节点|
|数据影响|创建权限、流程定义和节点；包含ProductionPlan确认能力。|
|输入依赖|workflow_runtime结构；无正式订单依赖。|
|幂等|稳定编码幂等；定义Hash确定。|
|Reverse|noop；流程和权限残留。|
|风险|高：固化旧Demand平行路径并引入当前关闭的ProductionPlan确认。|
|Replay建议|**C — REDESIGN REQUIRED**：与已发布制造输出→MPS/MRP正式路径统一。|

### B14 — procurement.0024_purchase_fulfillment_inventory_v1

|字段|内容|
|---|---|
|Operation Type|RunPython / Role、Permission、Workflow、Warehouse Seed|
|Function / Lines|`seed_fulfillment_foundation` 33–122；入口193|
|File / SHA256|`backend/procurement/migrations/0024_purchase_fulfillment_inventory_v1.py` / `620CCF75CE28612CBD02F3F2EF7DB623A9A00B48CE9471F57F5E1C312E2C982A`|
|调用链|RunPython → 建quality_inspector角色 → upsert8权限/绑定角色 → 按固定岗位职责补流程节点/Mapping → 取首个active Company → 建`WH-RM-001`仓库|
|数据影响|权限、角色、工作流、岗位关系及默认仓库基础资料。|
|输入依赖|固定岗位/职责编码、首个active Company、既有采购流程。|
|幂等|大部分业务键幂等，但“首个公司”导致环境相关归属。|
|Reverse|noop；全部残留。|
|风险|高：默认仓库、固定岗位与跨模块权限属于业务配置，不应由核心Migration猜测。|
|Replay建议|**C — REDESIGN REQUIRED**。|

### B15 — procurement.0028_completed_module_read_permissions

|字段|内容|
|---|---|
|Operation Type|RunPython / 只读Permission Seed|
|Function / Lines|`register_read_permissions` 14–22；`unregister_read_permissions` 23–27；入口31|
|File / SHA256|`backend/procurement/migrations/0028_completed_module_read_permissions.py` / `59EE75C5A8D8E7FBBD6767DF4B3601CE008B4DA0B3D0D3E0DCB188534D88EAC9`|
|调用链|RunPython → upsert6项SCM/WMS/QMS/FIN只读Permission；reverse按固定编码删除|
|数据影响|仅权限定义，无角色绑定。|
|输入依赖|system.Permission。|
|幂等|稳定编码，重复安全。|
|Reverse|显式删除6项权限；若未来已有外键绑定，回滚风险由数据库约束暴露。|
|风险|中低：跨域但均为只读合同。|
|Replay建议|**A — APPROVE FOR REPLAY**。|

### B16 — sales.0003_industrial_order_engineering_input_do1

|字段|内容|
|---|---|
|Operation Type|RunPython / Permission、Workflow Node、岗位映射Seed|
|Function / Lines|`seed_engineering_input_authority` 10–59；入口183|
|File / SHA256|`backend/sales/migrations/0003_industrial_order_engineering_input_do1.py` / `AC3CF9171D47567939929831ABAC632C5C8BF5AC57A06291FB1EE73BF744B989`|
|调用链|RunPython → upsert工程输入权限 → 可选绑定sales角色 → 查固定流程 → 建节点 → 查固定岗位/职责并建Mapping|
|数据影响|权限、角色授权、Workflow与组织责任映射。|
|输入依赖|`SALES_ORDER_TO_SUPPLY_PLAN`、`YXB-SALES`、`RESP_SALES_ORDER_002`。|
|幂等|稳定业务键，但输出取决于固定组织资料是否存在。|
|Reverse|noop；残留。|
|风险|高：把特定组织编码写入通用迁移，并依赖行业语义迁移。|
|Replay建议|**C — REDESIGN REQUIRED**。|

### B17 — sales.0004_order_operating_system_v1

|字段|内容|
|---|---|
|Operation Type|RunPython / Role、Permission、Workflow、岗位映射Seed|
|Function / Lines|`seed_order_operating_authority` 22–60；入口121|
|File / SHA256|`backend/sales/migrations/0004_order_operating_system_v1.py` / `FF3781CACB657FFD8A95D8090EC147CCBF07670B57EAB75560DB69CF00BB62F8`|
|调用链|RunPython → 对10项动作upsert权限和角色 → 绑定RolePermission → 可选创建流程节点 → 固定岗位/职责Mapping|
|数据影响|大量角色、权限、流程和组织映射。|
|输入依赖|固定销售流程、岗位及职责编码。|
|幂等|稳定编码幂等，但依赖组织样本且会覆盖角色描述/流程节点。|
|Reverse|noop；全部残留。|
|风险|高：组织和生命周期配置写入Migration，不符合配置/规则驱动。|
|Replay建议|**C — REDESIGN REQUIRED**。|

### B18 — supplier_performance.0006_formal_supplier_settlement_14_22_v1

|字段|内容|
|---|---|
|Operation Type|RunPython / 角色权限、结算流程和岗位责任Seed|
|Function / Lines|`seed_formal_foundation` 39–117；入口172|
|File / SHA256|`backend/supplier_performance/migrations/0006_formal_supplier_settlement_14_22_v1.py` / `C32A465034B070FA1D135B2AF37D243F9E681796874A62672F5E2B71962F3A0A`|
|调用链|RunPython → upsert采购/财务角色及12项权限 → 创建结算流程与节点 → 按固定岗位/职责建立责任映射|
|数据影响|角色、权限、流程和组织关系；含付款申请release等敏感动作。|
|输入依赖|固定岗位代码/名称、职责编码；依赖采购仓储前置迁移。|
|幂等|业务键幂等，但组织匹配和流程结果依赖前置数据。|
|Reverse|noop；全部残留。|
|风险|高：固定“验收14—22”语义、跨SCM/FIN授权及付款相关权限。|
|Replay建议|**C — REDESIGN REQUIRED**：保持银行发送和付款执行关闭。|

### B19 — system.0004_erp_access_foundation

|字段|内容|
|---|---|
|Operation Type|RunPython / ERP基础Permission、Role、RolePermission Seed及去重|
|Function / Lines|`seed_access_foundation` 39–81；入口86|
|File / SHA256|`backend/system/migrations/0004_erp_access_foundation.py` / `3ECA8C834C1D875D10677664A97DDB9D3EB0861838D7A95F65E4BAE7DFA8779C`|
|调用链|RunPython → upsert14权限和3角色 → 按固定集合绑定 → 删除重复RolePermission → 后续加唯一约束|
|数据影响|基础RBAC定义及重复关系清理；不创建业务单据。|
|输入依赖|前置system角色权限表；空库输出确定。|
|幂等|upsert/get_or_create并主动去重，重复结果稳定。|
|Reverse|noop；隔离库销毁。|
|风险|中：权限范围较大，但属于后续唯一约束所需基础数据准备。|
|Replay建议|**A — APPROVE FOR REPLAY**：权限对象纳入Fingerprint。|

### B20 — system.0005_organization_access_core_v1

|字段|内容|
|---|---|
|Operation Type|RunPython / 组织查看权限及旧授权投影|
|Function / Lines|`_business_hash` 11–20；`seed_access_core_v1` 21–87；入口189|
|File / SHA256|`backend/system/migrations/0005_organization_access_core_v1.py` / `B2228D240EF3027B3C1665078ACA5E3639E122AF5118A4AC1C72B14A7C22CD6A`|
|调用链|RunPython → upsert组织查看权限 → 绑定3个既有角色 → 遍历active LegacyAuthority → 解析组织/部门范围 → update_or_create Assignment及业务Hash|
|数据影响|权限与用户角色组织范围投影；不删除。|
|输入依赖|Company、Department、旧授权；空库迁移链决定输出。|
|幂等|唯一键(user,role,organization)和确定性Hash，重复安全。|
|Reverse|noop；隔离库销毁。|
|风险|中：读取旧授权，但转换规则明确、稳定且不猜测缺失角色。|
|Replay建议|**A — APPROVE FOR REPLAY**。|

### B21 — system.0006_enterprise_organization_model_v1

|字段|内容|
|---|---|
|Operation Type|RunPython / Company与Department事实投影|
|Function / Lines|`seed_existing_organization_hierarchy` 7–53；入口264|
|File / SHA256|`backend/system/migrations/0006_enterprise_organization_model_v1.py` / `AD76F5504530A4B0FE5DACCB8EDD6A5267A2DEADEF561B4424B945341ACE1D8A`|
|调用链|RunPython → 每Company upsert COMPANY组织单元 → 每Department upsert DEPARTMENT单元 → 修正父层级 → 回填Department.organization_unit|
|数据影响|基于既有事实创建组织投影并更新Department外键；不发明公司/部门。|
|输入依赖|Company与Department完整性；孤立department会触发失败而非静默造数。|
|幂等|稳定派生编码和update_or_create，重复安全。|
|Reverse|noop；隔离库销毁。|
|风险|中：非空库会创建投影，但逻辑明确且属于Schema演进。|
|Replay建议|**A — APPROVE FOR REPLAY**。|

### B22 — system.0007_remove_department_cost_center_and_more

|字段|内容|
|---|---|
|Operation Type|两段RunPython：ownership值迁移＋组织权限Seed|
|Function / Lines|`migrate_ownership_types` 18–24；`seed_organization_operating_permissions` 25–40；入口65、99|
|File / SHA256|`backend/system/migrations/0007_remove_department_cost_center_and_more.py` / `7DEC89ECC6EEDC79BFF291C462B6328BC0839DE6F37F615520E6AD493D2B5130`|
|调用链|RunPython1 → RESPONSIBLE/CONSULTED/INFORMED映射为OWNER/REVIEWER/EXECUTOR；RunPython2 → upsert6权限 → 绑定superadmin/pce_business_admin|
|数据影响|规范化组织责任类型并建立组织管理权限。|
|输入依赖|PositionWorkflowResponsibility、既有管理角色。|
|幂等|update过滤旧值，第二次无变化；权限/绑定以业务键幂等。|
|Reverse|两段noop；旧枚举值不恢复，隔离库销毁。|
|风险|中：不可逆枚举归一，但属于后续字段choices的必要转换。|
|Replay建议|**A — APPROVE FOR REPLAY**。|

## 4. B类22项汇总

|Decision|数量|Migration|
|---|---:|---|
|A — APPROVE FOR REPLAY|9|masterdata.0009；pde.0010、0021、0030；procurement.0028；system.0004、0005、0006、0007|
|B — EXCLUDE FROM REPLAY|0|无|
|C — REDESIGN REQUIRED|13|masterdata.0004、0011、0012；pde.0007、0011、0013、0017、0018；planning.0002；procurement.0024；sales.0003、0004；supplier_performance.0006|

全部22项均具有Evidence Record、明确Decision和风险等级，无留空项。

