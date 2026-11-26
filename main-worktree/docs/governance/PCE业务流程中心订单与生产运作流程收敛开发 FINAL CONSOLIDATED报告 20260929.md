# PCE业务流程中心订单与生产运作流程收敛开发 FINAL / CONSOLIDATED报告

日期：2026-09-29（Asia/Shanghai）  
阶段：Development Preflight / Stop Point  
任务类型：跨模块实施指令的只读准入核查；未进入实施  
Review Level：C（实施任务遇到有效准入阻断与未验证运行事实）

## 一、目标与实际结果

目标是以业务流程中心为入口，复用现有 CRM、PDE、PLAN 成果，证明销售订单→订单评审→工程准备→制造需求→计划生成的可运行业务链；本轮只定义 PLAN→MES 生产准备及 WMS 交付交接，不实施完整 MES 或交付。

实际结果：在首次源码修改前触发停止门禁。未修改应用代码、数据库、Schema、Migration、API、页面、权限、Workflow 或业务数据；未启动可写应用、Migration、Replay、Seed、Acceptance Runtime 或用户登录。不能据已有模型、服务和静态节点宣称流程已可运行。

## 二、有效指令与治理读取回执

EFFECTIVE INSTRUCTION SET：本轮开发指令 ACTIVE；V1.2 第 27–34 节、Preserve-and-Extend、用户现实优先、当前 Phase B Source/Baseline 技术准入阻断继续有效。此前只读盘点报告为输入事实，不是开发验收或新基线授权。

INSTRUCTION REGISTER：`BPC-CONVERGE-20260929-001`，目标订单→工程→计划收敛，状态 BLOCKED；`BPC-ASSESS-20260929-001` 为已完成的只读盘点；`BPC-20260929-001` 的流程中心优先原则继续有效。

GOVERNANCE READING RECEIPT：已全文回读 `D:\Dev-PCE\AGENTS.md`、`D:\Dev-PCE\Source\AGENTS.md`、`docs/governance/PCE CODEX开发指令规范管理V1.2.md`、`docs/governance/PCE 已开发模块固化与变更保护规范 V1.0.md`、`docs/governance/completed_module_registry.v1.json`、`docs/governance/COMPLETED_MODULE_PROTECTION_PREFLIGHT_V1.md`；专项读取上一轮流程盘点与 Phase B Source Qualification 报告。关键规则是 V1.2 第 4、6.7、15、27–30、34 节：关键准入缺失即停止、跨三模块应拆分、业务流程优先不豁免保护门禁、真实用户路径和 DB/API/UI 连续性不能由静态代码代替。

COMPLETED MODULE GOVERNANCE READING RECEIPT：Preservation Standard Read = YES；Completed Module Registry Read = YES（34 项，`currentFrozenVerifiedModuleIds=[]`）；Affected Frozen Modules = 无已登记 `FROZEN_VERIFIED` 对象，但销售订单来源、PDE 工程核算及 PLAN 计划数量语义等已开发对象仍须 Preserve-and-Extend；Freeze Contracts Read = N/A（本轮不改源码，登记对象的 `freezeContractPath` 为 null）；Unfreeze Authorization = NO。已执行保护 Preflight；结论 `SAFE TO MODIFY` 仅限新增本报告，不是对 CRM/PDE/PLAN 共享文件或运行链的放行。

INSTRUCTION CONTROL SHEET：Original/Current Goal = 订单→工程→计划流程收敛并验证可运行；IN SCOPE = 本轮只读核查、阻断报告；OUT OF SCOPE = 在阻断状态下修改源码或正式业务事实；Non-Regression Baseline = 既有订单、工程、计划对象和全部现有入口原样保留；Database Boundary = 未打开数据库，Protection/Acceptance 不写；User Acceptance Path = 应从业务流程中心真实菜单逐节点验证，本轮未执行；Stop Condition = 关键准入和范围拆分条件不满足时停止。

## 三、完成流程与入口路径

本轮完成的业务流程：**无**。源码存在候选路径 `/process-center?module=CRM`，CRM 静态流程登记接单、订单评审、产品设计三个有路由节点；BOM、工艺、制造输出仍标 `planned`，计划输入标 `frozen`（`frontend/src/meta/runtime/crmOrderProcessRegistry.js:5-13`）。`frontend/src/meta/process/businessProcessRegistry.js:18-23` 将 PLAN、MRP、MPS、MES 目录标为 `planned`。因此“单一正式流程中心路径跨 CRM→PDE→PLAN 可操作”尚无本轮证据。

正常菜单实际点击路径、最终页面标题、可见记录数、返回与刷新结果、同一浏览器 Tab 交付状态均未验证。静态节点的 `PASS` 字段不等于真实用户验收。`DELIVERED USER STATE = NOT GUARANTEED`。

## 四、业务对象、状态和上下游连接

| 交接 | 只读观察到的现有能力 | 未获证明的业务事实 |
|---|---|---|
| CRM 接单→评审 | `backend/sales/models.py` 有 `SalesOrder`/`SalesOrderItem`；流程 Registry 有订单评审节点 | 当前真实订单、商业/技术/交付评审已通过及责任链均未验证 |
| 订单→PDE | 订单行可关联产品版本与制造输出；PDE 有工程对象与版本模型 | 同一订单行的工程版本、BOM/工艺、制造准备发布状态未做 DB/API/UI 同源核验 |
| PDE→制造需求 | `backend/sales/services.py:435-542` 的 `generate_demand` 校验订单状态、制造准备，并在事务中为订单行创建 `Demand`，有重复/部分重复阻断 | 正式订单行是否满足条件、真实动作权限、审计与用户可见执行未验证 |
| 需求→计划 | `backend/planning/services.py:584-710` 有 `calculate_requirement` 与 `confirm_supply_plan`，区分采购和生产计划，零净需求/供给类型不明会阻断 | 真实计划数量语义、当前用户入口、`ProductionPlan` 对应订单行和状态结果未验证 |
| PLAN→MES→WMS | `ProductionPlan` 模型存在；WMS 有既有收货/库存能力 | MES 任务、工序与完工以及出库交付的正式对象和运行交接未证明；仅应作为后续独立阶段 |

状态变化本轮为零。上述源码能力不是当前环境的实际状态变化或业务闭环通过证据。

## 五、保护检查与阻断

1. 当前历史 Source Qualification 报告明确 `SOURCE QUALIFIED = NO`、`NEW BASELINE CREATED = NO`、`ACCEPTANCE INITIALIZED = NO`、`PHASE B TECHNICAL RE-ADMISSION = BLOCKED`。新指令没有明确解除 Source/Baseline 与 Acceptance 门禁。流程优先原则第 34.1 节也明确不得豁免这些门禁。故不能使用受保护运行链建立本任务所要求的正式可运行验收。
2. 本指令同时跨 CRM、PDE、PLAN，并包含 MES/WMS 交接定义，且涉及服务、页面、流程 Registry、状态、权限和验收。V1.2 第 6.7、15 节要求超过三模块/多实施层复评并拆分。本轮未获得分阶段受控实施范围、可写隔离环境身份、数据来源和回退条件；不可将大范围实施一次性视为安全原子任务。
3. `git status --short` 显示订单/工程/计划关键服务与模型、Router、流程中心页面及运行 Registry 已有大量未提交改动。它们按用户资产保留，不能清理或覆盖；在确认差异来源及目标工作基线前修改这些共享依赖会使非回归无法归因。
4. 上轮盘点与本轮静态检查只证明部分 AS-BUILT。没有真实菜单点击、正式数据 DB→API→UI 计数、相同订单行的下游身份、异常处理与用户人工验收。本任务要求“业务流程可运行”作为完成标准，因此不能输出 COMPLETE。

## 六、测试结果、遗留事项与下一阶段计划

测试结果：只读源码、治理报告和 Git 状态核验；未运行会写入数据库或认证日志的应用流程。单元/API/Build/真实用户路径、UI 数据可见性、非回归、用户人工验收均为 NOT RUN / NOT VERIFIED，不得计为 PASS。Unauthorized Business Writes = 0（本轮未执行任何业务写入）。

解除阻断后应先独立批准受控实施边界和环境，保留现有成果，再按小范围顺序实施并验收：① CRM 订单评审→PDE 工程准备的同一订单行身份/状态/责任；② PDE 已发布制造输出→Demand→PlanningRequirement→ProductionPlan 的服务端交接与 PLAN 唯一流程入口；③ 另行设计 PLAN→MES 任务交接；④ 更后续才处理 MES 完工→WMS→交付。每段均需正常菜单真实路径、正反例、权限、服务端事实、DB/API/UI 连续性和非回归。GRA 不作为此主线的前置开发任务。

所需独立授权/证据：明确本轮是否属于既有 Phase B 技术再准入范围；若属于，先完成 Source/Baseline、Recovery、Runtime Isolation 与 Re-admission Gates；无论是否属于 Phase B，均需给出可写隔离环境和数据来源、分段实施边界、保护回归基线以及真实用户验收路径。未获之前不启动下一阶段。

## 七、合规矩阵与最终 Gate

| Compliance Item | Result | Evidence / Note |
|---|---|---|
| Original Goal | BLOCKED | 未证明订单→工程→计划可运行闭环 |
| Governance Reading / Effective Instruction Set | PASS | 本报告第二节 |
| Scope / Stop Condition | PASS | 停于首次源码修改前 |
| Existing Results Preserved | PASS BY SCOPE | 未修改既有业务实现；运行非回归未验证 |
| Automated Tests | NOT RUN | 未进入实施，不以源码存在充当测试 |
| User-Visible Real Path / UI Data Visibility | NOT VERIFIED | 无正常菜单点击或 DB/API/UI 对照 |
| Non-Regression | NOT VERIFIED | 未实施，且现有工作树有大量未提交内容 |
| User Manual Validation | PENDING | 只能由用户明确授予 |
| Production Boundary | PASS BY SCOPE | 本轮无数据库或生产写入 |
| Report vs User Reality Conflict | HISTORICAL CONFLICT PRESERVED | 旧采购相关可见性冲突不被静态检查覆盖 |
| Final Stop Condition | PASS | 触发准入与范围门禁，停止 |

保护状态：Documentation Changed = YES（仅本报告）；Code/Database/Migration/API/Page/Organization/Employee/Permission/Workflow/GRA Changed = NO；Acceptance Initialized = NO；Hash Signed = NO；Unauthorized Business Writes = 0。归档行数和 SHA256 由保存后只读核验给出。

**PCE ORDER TO PRODUCTION PROCESS CONVERGENCE BLOCKED**
