# Phase B Target Schema Manifest与Migration收敛决策 FINAL / CONSOLIDATED报告

日期：2026-09-28  
任务性质：只读分析、决策矩阵和Manifest草案  
基础集成提交：`969a86fe4a1b8557e8c837d19c58e9a9cc5d8fba`

## 一、任务范围

本任务编制了Target Schema Manifest草案，建立PDE、PFM和Planning收敛矩阵，并冻结Replay授权Gate。没有进行Migration、Schema、数据库、业务模型、权限、Router或Registry修改。

## 二、治理读取结果

### COMPLETED MODULE GOVERNANCE READING RECEIPT

已全文读取根/仓库AGENTS、开发规范V1.2、固化保护规范V1.0、completed module Registry和Preflight。

- Registry：解析PASS，当前登记34个模块。
- 当前文件Hash：根AGENTS `0CD48571...5954`；仓库AGENTS `BC701CB8...EC44`；开发规范 `7171774A...5C3`；固化规范 `695F812E...C39C`；Registry `DF754062...521F`；Preflight `D2B2487B...D4BD`。
- 开发规范、固化规范和Registry的Hash较上一任务发生变化；本任务采用本轮读取的当前版本，不回退、不覆盖。
- Frozen Core：未修改。
- Frozen Shared Dependency：未修改。
- Unfreeze：不需要；后续修改Migration必须重新Preflight并取得授权。
- 保护等级：Level C。
- Preflight：`SAFE TO MODIFY DOCUMENTATION ONLY`。
- UI/DELIVERED USER STATE：N/A。

## 三、Target Schema Manifest Draft

已创建：[Phase B Target Schema Manifest Draft 20260928.md](./Phase%20B%20Target%20Schema%20Manifest%20Draft%2020260928.md)。

身份：

- Manifest ID：`PCE-PHASE-B-TARGET-SCHEMA-DRAFT-20260928-01`；
- 目标版本：`PHASE-B-MANUFACTURING-FOUNDATION-TARGET-V0.1-DRAFT`；
- 基础分支：`codex/manufacturing-baseline-convergence-20260927`；
- 基础commit：`969a86fe...`；
- 状态：`DRAFT_PENDING_ARCHITECTURE_DECISION`；
- Decision、Signer、SignatureDate和EvidenceReference全部为空。

Manifest按应用和Migration范围标记`INCLUDE_ACTIVE`候选、`ARCHIVE_HISTORY`候选、`REDESIGN_REQUIRED`或`EXCLUDE`，并区分DecisionStatus。草案状态不是Replay授权。

Phase B目标基础表覆盖ManufacturingPlant及版本/分配、MES Calendar/Capability/Skill、PDE TimeStandard和Planning MaterialPlantProfile。现有依赖表只能在对应Migration获签后纳入。

明确排除正式BOM、BOM Version、工程材料/工序需求、ProductionPlan、MPS/MRP/APS运行、正式数据转换、C类数据和正式数据库Migration。

## 四、PDE 0020–0022决策矩阵

|编号|活动候选|历史候选|当前判断|决策状态|
|-|-|-|-|-|
|0020|转换模式字段|WorkCenter/产线/工位/能力关系|两个语义均存在；历史名称与正式应用事实关联，但无部署字节证明|EMPTY|
|0021|角色权限RunPython|订单工程结构Schema|权限数据与结构模型完全不同|EMPTY|
|0022|制造定义适用范围|结构规则与工程核算基础|表、依赖、业务域不同|EMPTY|

当前活动链存在于集成提交；历史链存在于独立Git提交。任何历史候选都没有正式部署制品Hash，不能自动选择。

Manifest建议方向是“历史文件不可执行归档 + 对仍需语义另行设计”，但该建议未签署、未生效。PDE状态保持`PENDING ARCHITECTURE DECISION`。

## 五、PFM 0002决策矩阵

活动`0002_employee_formal_organization_relations`增加正式组织/岗位关系并执行文本匹配；历史`0002_initial`增加Employee.user和EmployeeCertificate.employee，不含RunPython。

历史应用日期早于当前Git候选提交日期，无法用候选blob证明部署字节。两个0002禁止同时进入活动目录。

可选方向：

- `ACTIVE KEEP`：需解释EmployeeCertificate关系的最终来源；
- `HISTORY ARCHIVE`：需确认历史删除意图；
- `REDESIGN REQUIRED`：建议方向，但仍需签署。

PFM ArchitectureDecision保持`EMPTY`。

## 六、Planning 0005/0006决策矩阵

Planning 0005创建5张MPS/MRP表、角色`order_planning_operator`以及`planning.mps.generate`、`planning.mrp.generate`权限；反向函数为noop。

Planning 0006当前收敛文件直接依赖0005。来源复核发现：

- Phase A原始提交`ee4838f`：blob `dc210f09...`，SHA-256 `F1C8281E...5813`，依赖Planning 0004和原PDE 0024；
- 收敛merge `c4a3c81`及当前基线：blob `cb417f31...`，SHA-256 `1640F824...9AB5`，依赖Planning 0005和PDE 0031。

方案A：接受0005结构与权限进入目标Schema，但MPS/MRP业务执行继续关闭；需独立授权并补全回滚合同。

方案B：继续排除0005；必须另行授权设计0006依赖，不能直接编辑当前Migration。

当前：`PENDING ARCHITECTURE DECISION`，没有自动选择。

## 七、Target Schema Decision Matrix

|来源|事实类型|可信度|主要问题|建议|
|-|-|-|-|-|
|当前活动Migration|Migration事实|源码身份高|不等于部署事实；含争议链和未授权Planning|逐项签署后作为Replay输入|
|历史Migration|历史Migration事实|存在性高，部署身份低|无正式制品Hash；同号异义|不可执行归档；所需语义重新设计|
|正式数据库事实|部署/运行Schema事实|运行事实高|不能证明Migration字节；禁止反推|仅作为兼容验收事实|
|C5模型直建库|模型直建Schema事实|模型装载事实高，Migration证明力为零|`migrationUsed=false`|只用于C5，不作Replay基线|

唯一目标Schema必须由签署Manifest定义，而不是由任何单一来源自动决定。

## 八、Replay Authorization Gate

|Gate|状态|
|-|-|
|R0 Target Schema Manifest签署|BLOCKED|
|R1 PDE/PFM历史来源裁决|BLOCKED|
|R2 Planning 0005/0006方向确认|BLOCKED|
|R3 固定源码commit|READY|
|R4 Replay专用隔离环境|PENDING|
|R5 RunPython/seed白名单|BLOCKED|
|R6 Schema fingerprint标准与预期manifest|PENDING|
|R7 正式数据库/C5保护Hash|READY|

R3和R7通过不足以授权Replay；R0、R1、R2、R5为当前硬阻断。

## 九、未决策事项

1. PDE每个活动/历史同号候选的纳入、归档或重新设计决定；
2. PFM活动0002是否保留、历史0002是否归档、EmployeeCertificate关系如何承接；
3. Planning选择方案A或B；
4. 所有RunPython和seed的白名单、反向、幂等、残留合同；
5. 签署后的表/字段/索引/约束/权限预期fingerprint；
6. Manifest实际Signer、日期、意见和证据引用。

## 十、下一步授权需求

在考虑《Phase B隔离数据库Migration Replay验证执行指令》前，需要用户或架构治理责任人：

1. 填写并签署Manifest决策区；
2. 明确PDE/PFM收敛方向；
3. 明确Planning方案A或B；
4. 批准RunPython/seed白名单；
5. 批准专用隔离settings、临时数据库路径和fingerprint采集器；
6. 明确Replay仅限临时数据库，不授权正式Migration或业务启用。

## 保护结果

- 本任务没有运行`migrate`、`sqlmigrate`、`makemigrations`、DDL或DML。
- 没有修改Migration、依赖、模型、权限、Router、Registry、正式数据库或C5数据库。
- 没有生成BOM、BOM Version、工程材料/工序需求、ProductionPlan、MPS、MRP或APS对象。
- 正式数据库和C5 Hash在最终Readback中复核。

## FINAL / CONSOLIDATED

```text
TARGET SCHEMA MANIFEST = DRAFT CREATED
TARGET SCHEMA DECISION = UNRESOLVED
MIGRATION CONVERGENCE DECISION = PARTIAL
REPLAY AUTHORIZATION = NOT READY

PHASE B READY = NOT DECLARED
```

本轮完成的是可签署决策材料，不是决策替代、Schema修改或Replay授权。
