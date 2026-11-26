# Phase B Target Schema Manifest Draft

> 本文件是待架构签署草案，不是Migration、Schema或Replay授权。所有`ProposedStatus`只有在Decision、Signer和SignatureDate完整后才生效。

## 1. 基础身份

|字段|值|
|-|-|
|Manifest ID|`PCE-PHASE-B-TARGET-SCHEMA-DRAFT-20260928-01`|
|创建时间|`2026-09-28T12:06:41+08:00`|
|Manifest状态|`DRAFT_PENDING_ARCHITECTURE_DECISION`|
|基础源码commit|`969a86fe4a1b8557e8c837d19c58e9a9cc5d8fba`|
|Git分支|`codex/manufacturing-baseline-convergence-20260927`|
|Schema目标版本|`PHASE-B-MANUFACTURING-FOUNDATION-TARGET-V0.1-DRAFT`|
|证据附件|`Phase B Migration历史来源 Evidence Record 20260928.md`|
|DecisionResponsibility|`admin / architecture governance`（沿用G1治理主体，不代表已签署本Manifest）|
|Decision|`EMPTY`|
|Signer|`EMPTY`|
|SignatureDate|`EMPTY`|
|EvidenceReference|`EMPTY`|

## 2. Migration集合草案

状态值：`INCLUDE_ACTIVE`、`ARCHIVE_HISTORY`、`REDESIGN_REQUIRED`、`EXCLUDE`。表中为建议状态，不构成最终选择。

|App|Migration|ProposedStatus|DecisionStatus|说明|
|-|-|-|-|-|
|Django built-ins|admin/auth/contenttypes/sessions当前安装集合|INCLUDE_ACTIVE|PENDING_SIGNATURE|框架依赖；版本须固定|
|system|0001–0017|INCLUDE_ACTIVE|PENDING_SIGNATURE|组织、权限、工序、车间和班组依赖|
|masterdata|0001–0012|INCLUDE_ACTIVE|PENDING_SIGNATURE|物料、UOM及共享主数据依赖|
|masterdata|0013_manufacturing_plant_phase_a|INCLUDE_ACTIVE|PENDING_SIGNATURE|Phase A ManufacturingPlant目标|
|pde|0001–0019|INCLUDE_ACTIVE|PENDING_SIGNATURE|当前活动前置链|
|pde|0020_group3_transition_mode_override|REDESIGN_REQUIRED|PENDING_ARCHITECTURE_DECISION|与历史0020同号异义|
|pde|0020_workcenter_engineering_closure|ARCHIVE_HISTORY候选|PENDING_ARCHITECTURE_DECISION|正式应用名称证据；部署字节未证实|
|pde|0021_group3a_operation_executor_authority|REDESIGN_REQUIRED|PENDING_ARCHITECTURE_DECISION|权限seed；与历史0021同号异义|
|pde|0021_order_engineered_product_structure|ARCHIVE_HISTORY候选|PENDING_ARCHITECTURE_DECISION|历史Schema链候选|
|pde|0022_manufacturing_definition_applicability|REDESIGN_REQUIRED|PENDING_ARCHITECTURE_DECISION|与历史0022同号异义|
|pde|0022_structure_template_rule_binding_wave27|ARCHIVE_HISTORY候选|PENDING_ARCHITECTURE_DECISION|历史Schema链候选|
|pde|0023–0030当前活动链|REDESIGN_REQUIRED|BLOCKED_BY_0020_0022|依赖当前0022，不能先于上游裁决|
|pde|0031_operation_time_standard_phase_a_rebased|INCLUDE_ACTIVE候选|BLOCKED_BY_PDE_CONVERGENCE|Phase A标准工时目标，依赖0030|
|pfm|0001_initial|INCLUDE_ACTIVE|PENDING_SIGNATURE|Employee基础|
|pfm|0002_employee_formal_organization_relations|REDESIGN_REQUIRED|PENDING_ARCHITECTURE_DECISION|当前活动；有数据匹配|
|pfm|0002_initial|ARCHIVE_HISTORY候选|PENDING_ARCHITECTURE_DECISION|历史已应用名称；候选字节身份未证实|
|pfm|0003_enterprise_organization_model_v1|REDESIGN_REQUIRED|BLOCKED_BY_PFM_0002|依赖当前0002|
|mes|0001_manufacturing_domain_foundation_phase_a|INCLUDE_ACTIVE候选|BLOCKED_BY_PDE_PFM|Phase A Calendar/Capability/Skill目标|
|planning|0001–0004|INCLUDE_ACTIVE|PENDING_SIGNATURE|现有计划基础链|
|planning|0005_order_planning_chain_v1|REDESIGN_REQUIRED|PENDING_ARCHITECTURE_DECISION|方案A纳入；方案B排除，不能自动选择|
|planning|0006_material_plant_profile_phase_a|REDESIGN_REQUIRED|PENDING_ARCHITECTURE_DECISION|当前收敛文件依赖0005；方案B需重设计|
|procurement|0001–0028|INCLUDE_ACTIVE候选|PENDING_SEED_REVIEW|跨域依赖；RunPython需白名单|
|sales|0001–0005|INCLUDE_ACTIVE候选|PENDING_SEED_REVIEW|PDE/Planning依赖|
|workflow_runtime|0001–0006|INCLUDE_ACTIVE候选|PENDING_SEED_REVIEW|状态转换和显式merge依赖|
|其他当前项目应用|当前集成提交中其余活动Migration|INCLUDE_ACTIVE候选|PENDING_SEED_REVIEW|完整节点见Migration源图证据；逐项seed仍需白名单|
|production应用0001–0004|不存在于当前仓库/INSTALLED_APPS|EXCLUDE|EVIDENCE_ABSENT|不是当前DAG节点；外部证据出现时重新评审|

## 3. Schema范围草案

### 3.1 Phase B目标基础表

在上游裁决通过后，Manifest目标至少包含：

|领域|目标Migration|目标表|
|-|-|-|
|EMD|masterdata.0013|`masterdata_manufacturing_plant`、`masterdata_manufacturing_plant_version`、`masterdata_plant_warehouse_assignment`、`masterdata_plant_workshop_assignment`|
|MES|mes.0001|`mes_manufacturing_calendar`、`mes_resource_capability`、`mes_employee_skill_certification`|
|PDE|pde.0031|`pde_operation_time_standard`|
|PLAN|planning.0006|`planning_material_plant_profile`|

### 3.2 依赖Schema

包含由签署后的`INCLUDE_ACTIVE`集合建立的Company、Workshop、Process、Team、Employee、Material、UOM、WorkCenter、Equipment、Routing、Planning基础对象。具体表、字段、索引与约束必须由签署Migration集合生成的fingerprint锁定，不允许以当前数据库反向补写Migration。

### 3.3 字段、索引与约束

- 字段：以签署Migration operations为唯一Replay输入；Manifest另存规范化字段fingerprint。
- 索引：记录名称、表、列顺序、唯一性、条件表达式。
- 约束：记录PK、FK、UNIQUE、CHECK及其名称、列和目标。
- 版本/生效期：六项Phase A模型中的version、status、effective_from/effective_to必须纳入指纹。
- 跨域FK：必须符合EMD → PDE/MES/PLAN、PDE → MES/PLAN、MES → PLAN方向；禁止循环修改权威。

### 3.4 权限与seed范围

|Seed/权限|草案状态|原因|
|-|-|-|
|既有系统/业务Migration的RunPython|PENDING_WHITELIST|尚未完成全部153节点数据操作审查|
|PDE 0021活动链权限投影|PENDING_ARCHITECTURE_DECISION|属于争议同号链|
|Planning 0005 `order_planning_operator`|EXCLUDE_BY_DEFAULT / OPTION_A_ONLY|MPS/MRP仍关闭；只有方案A单独授权后纳入|
|Planning 0005 `planning.mps.generate`|EXCLUDE_BY_DEFAULT / OPTION_A_ONLY|同上|
|Planning 0005 `planning.mrp.generate`|EXCLUDE_BY_DEFAULT / OPTION_A_ONLY|同上|
|业务样例、C类数据、测试JSON|EXCLUDE|不得进入核心制造或Replay seed|

## 4. 明确排除范围

本Manifest即使未来签署，也不授权：

- 正式BOM或BOM Version生成；
- EngineeringMaterialRequirement生成；
- EngineeringOperationRequirement生成；
- ProductionPlan生成；
- MPS/MRP/APS业务运行；
- 正式业务数据转换、初始化或状态推进；
- 正式数据库Migration；
- C类来源转正式；
- Router、Registry、权限运行配置或页面修改。

## 5. PDE Migration Convergence Matrix

|编号|候选|Git来源 / blob / SHA256|Schema影响|数据/RunPython影响|正式事实关联|候选方向|ArchitectureDecision|
|-|-|-|-|-|-|-|-|
|0020|活动`group3_transition_mode_override`|`dfc3901` / `c1790533...` / `4B1D6A97...9C43`|RoutingStep增加转换模式|无|当前活动源图|INCLUDE_ACTIVE或REDESIGN_REQUIRED|EMPTY|
|0020|历史`workcenter_engineering_closure`|`6058ee0` / `9e10a8c...` / `241FDC94...AA09`|4张资源关系表及WorkCenter关系|无|既有报告记录历史名称已应用|ARCHIVE_HISTORY或REDESIGN_REQUIRED|EMPTY|
|0021|活动`group3a_operation_executor_authority`|`dfc3901` / `bd2e38dd...` / `2280B16E...3D1`|无Schema|可逆RunPython，角色/权限绑定|当前活动源图|INCLUDE_ACTIVE或REDESIGN_REQUIRED|EMPTY|
|0021|历史`order_engineered_product_structure`|`fa7dfb0` / `50e60020...` / `4D2171E5...799`|订单工程结构6张核心表及约束|无|既有报告记录历史名称已应用|ARCHIVE_HISTORY或REDESIGN_REQUIRED|EMPTY|
|0022|活动`manufacturing_definition_applicability`|`dfc3901` / `69dbfb84...` / `DFF556E9...2688`|工艺类型、BOM/Routing适用范围及约束|无|当前活动源图|INCLUDE_ACTIVE或REDESIGN_REQUIRED|EMPTY|
|0022|历史`structure_template_rule_binding_wave27`|`44dfc6b` / `d55eaa27...` / `0228DE88...DF4`|结构规则、材料核算、边面定义6张表|无|既有报告记录历史名称已应用|ARCHIVE_HISTORY或REDESIGN_REQUIRED|EMPTY|

建议但不代替裁决：历史文件保留为不可执行证据；活动语义与经确认仍需要的历史语义通过未来独立设计表达。是否采用该方向必须由架构责任人签署，不能在当前任务自动生效。

## 6. PFM 0002 Convergence Matrix

|候选|Git来源 / blob / SHA256|Schema差异|数据迁移|正式证据|候选方向|ArchitectureDecision|
|-|-|-|-|-|-|-|
|活动`0002_employee_formal_organization_relations`|`eeaa985` / `6af9c11d...` / `7B7DC571...81B1`|Employee.user调整；增加department_ref、position_ref|按文本/旧ID匹配组织岗位；反向noop|当前活动源图|ACTIVE KEEP或REDESIGN REQUIRED|EMPTY|
|历史`0002_initial`|`02a832b` / `2b6edc8d...` / `8EB41E01...D3AA`；删除`6480e62`|增加Employee.user、EmployeeCertificate.employee|无|既有报告记录历史名称已应用；日期早于候选提交|HISTORY ARCHIVE或REDESIGN REQUIRED|EMPTY|

强制规则：两个0002不得同时进入活动目录。建议状态为`REDESIGN_REQUIRED`，因为必须确认EmployeeCertificate.employee最终权威并解释历史删除；最终选择仍为空。

## 7. Planning Dependency Decision Matrix

### 方案A：接受0005进入目标Schema

|项目|影响|
|-|-|
|Schema|增加MPS run/line/allocation和MRP run/proposal共5张表|
|权限|创建/更新`order_planning_operator`、`planning.mps.generate`、`planning.mrp.generate`，可选绑定`planning.view`|
|seed|`RunPython`正向写入；反向为noop，回滚后可能残留|
|0006|维持当前对0005的依赖，可纳入同一Replay|
|治理要求|必须独立授权“结构与权限存在但业务执行继续关闭”，并补全回滚合同|
|Decision|`EMPTY / PENDING ARCHITECTURE DECISION`|

### 方案B：继续关闭MPS/MRP，不让0005进入目标Schema

|项目|影响|
|-|-|
|Schema|不创建5张MPS/MRP表|
|权限|不创建MPS/MRP生成角色与权限|
|0006|当前依赖无法执行，必须授权重新设计到`planning.0004`或另一获准父节点|
|源历史|当前0005作为历史/设计证据保留，不进入Replay集合|
|治理要求|产生新的受评审Migration设计；不得直接编辑已捕获历史文件|
|Decision|`EMPTY / PENDING ARCHITECTURE DECISION`|

Planning最终状态：`PENDING ARCHITECTURE DECISION`。

## 8. Target Schema Decision Matrix

|来源|事实类型|证据|可信度|问题|建议|
|-|-|-|-|-|-|
|当前活动Migration|Migration事实|固定commit、文件、blob、SHA256、dependencies和operations|源码身份高|不等于正式部署事实；含争议链和未授权Planning|作为Replay候选输入，逐项签署|
|历史Migration|历史Migration事实|可达commit/blob/SHA256、删除记录、分支链|历史存在性高；部署身份低|没有部署制品Hash；同号异义|不可执行归档；需要的语义重新设计|
|正式数据库事实|部署/运行Schema事实|既有已签报告中的Migration名称、时间与运行事实|运行事实高|不能证明Migration字节；本任务禁止重开或反推|用于兼容验收，不作源码生成器|
|C5模型直建库|当前模型直建Schema事实|manifest、固定Hash、`migrationUsed=false`|模型装载事实高；Migration证明力为零|绕过Migration和seed|仅保留C5 Gate用途|

## 9. Migration Replay Authorization Gate

|Gate|条件|状态|解除条件|
|-|-|-|-|
|R0|Target Schema Manifest签署|BLOCKED|Decision、Signer、SignatureDate、EvidenceReference完整|
|R1|PDE/PFM历史来源裁决|BLOCKED|六个PDE候选和两个PFM候选逐项决定，且无同号双活动|
|R2|Planning 0005/0006方向确认|BLOCKED|签署方案A或B；若B，先授权依赖重设计|
|R3|固定源码commit|READY|Replay必须从`969a86fe...`或后续签署commit的干净隔离checkout运行|
|R4|Replay专用隔离环境|PENDING|创建带路径断言的专用settings和全新临时数据库；不得指向正式/C5|
|R5|RunPython/seed白名单|BLOCKED|逐项批准正向、反向、幂等与残留合同|
|R6|Schema fingerprint标准|PENDING|规范已定义；仍需实现只读采集器和签署预期manifest|
|R7|正式数据库保护Hash|READY|正式库`734F5B...FEE7D`、C5`0840A7...39F67`；Replay前后必须一致|

## 10. Manifest签署区

|字段|值|
|-|-|
|PDE Decision|`EMPTY`|
|PFM Decision|`EMPTY`|
|Planning Decision A/B|`EMPTY`|
|RunPython Allowlist Reference|`EMPTY`|
|Target Fingerprint Reference|`EMPTY`|
|Signer|`EMPTY`|
|SignatureDate|`EMPTY`|
|SignatureComment|`EMPTY`|
|EvidenceReference|`EMPTY`|

当前Manifest不可用于Replay授权。
