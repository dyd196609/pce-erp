# PCE业务流程中心现有模块开发进度盘点与订单生产流程准备 FINAL / CONSOLIDATED报告

日期：2026-09-29（Asia/Shanghai）  
阶段：Development Progress Assessment  
类型：READ ONLY / PREPARATION  
审查等级：B（跨模块流程与数据权威边界）；对话不要求全文传输。  
裁决口径：源码/Registry 能证明 AS-BUILT 或 AS-DESIGNED；未执行当前真实菜单点击、DB/API/UI 连续性与用户人工验收，不能证明 AS-RUNNING / AS-FROZEN。

## 一、任务范围、有效指令与保护回执

唯一目标：建立流程中心现有能力地图，定位订单 → 工程 → 计划 → 生产 → 交付的连接与缺口；本轮不开发、不写数据库、不修改权限、Workflow 或 GRA。

EFFECTIVE INSTRUCTION SET：当前盘点指令 ACTIVE；《PCE CODEX开发指令规范管理V1.2》第 34 节 ACTIVE；Completed Module Preserve-and-Extend、安全、Source/Baseline 隔离、用户真实运行高于自动化等历史保护继续有效。下一阶段《订单与生产运作流程收敛开发指令》尚未发出，不属于本轮授权。

INSTRUCTION REGISTER：`BPC-ASSESS-20260929-001`，目的为流程中心进度盘点，状态 COMPLETE；本轮停止于只读报告，不产生实施授权。

INSTRUCTION CONTROL SHEET：IN SCOPE = 源码、流程 Registry、历史台账只读核验与报告；OUT OF SCOPE = 代码、数据库、Migration、API、页面、权限、Workflow、GRA及业务数据变更；Database Boundary = 未访问数据库；User Acceptance Path = 未执行（非 UI 验收）；Stop Condition = 本报告归档并停止。

COMPLETED MODULE GOVERNANCE READING RECEIPT：

- Preservation Standard Read = YES；Completed Module Registry Read = YES（34 项，`currentFrozenVerifiedModuleIds=[]`）。
- Affected Frozen Modules = NONE BY FILE CHANGE；这不表示既有成果没有保护。
- Freeze Contracts Read = NOT APPLICABLE（本轮仅新增报告，不触及 Frozen Core / Shared Dependency）。
- Unfreeze Authorization = NO；Preserve-and-Extend Analysis = 原有菜单、路由、组件、API、数据权威与用户记录均不变。
- Preflight Result = SAFE TO MODIFY（仅本报告）；User Reality Conflict Rule = USER REALITY OVERRIDES AUTOMATION。

直接证据：`D:\Dev-PCE\AGENTS.md`；`D:\Dev-PCE\Source\AGENTS.md`；`docs/governance/PCE CODEX开发指令规范管理V1.2.md`（第 27–34 节）；`docs/governance/PCE 已开发模块固化与变更保护规范 V1.0.md`（第 4、13 节）；`docs/governance/completed_module_registry.v1.json`；`docs/governance/COMPLETED_MODULE_PROTECTION_PREFLIGHT_V1.md`；`docs/governance/流程中心入口统一规范.md`。

## 二、业务流程中心现状

源码登记 `/process-center` 为单一规范路径；Router 指向 `ProcessCenterRoutePage`，该组件承载 `EnterpriseOSPage`；`processCenterRuntime.js` 将 CRM 流程与 `businessProcessRegistry.js` 流程合并，并检查单模块活动流程数量不超过 1。`EnterpriseOSPage` 的模块导航按当前模块选取一个正式流程；无流程时显示空态。

静态目录登记 14 个模块：CRM、PDE、EMD、SCM、PLAN、MRP、MPS、APS、WMS、MES、QMS、BI/FDM、KPI、ProfitOS；FIN 由活动流程补入运行模型。源码内活动流程定义为 CRM、PDE、EMD、SCM、WMS、QMS、FIN、ProfitOS 共 8 个；MES 流程定义为 `planned`，其余计划类模块没有在本次核查中发现活动正式流程。这里的“活动”是源码属性，不是当前用户可操作证明。

风险：`businessProcessRegistry.js` 初始化时可从浏览器 `localStorage` 读取流程集合。故静态定义的唯一流程断言虽存在，仍需将当前运行态、用户菜单路径和持久化覆盖来源单独验证。节点上的 `acceptanceStatus: 'PASS'` 与页面上的 `data-acceptance-status='PASS'` 也是声明字段，不等于本轮真实验收。直接业务路由、兼容工作台与流程中心节点并存；是否造成重复入口必须由实际菜单导航核查，不能仅凭路由推断。

证据：`frontend/src/router/index.js:466`；`frontend/src/meta/pages/ProcessCenterRoutePage.vue:1`；`frontend/src/meta/pages/EnterpriseOSPage.vue:225,265,676`；`frontend/src/meta/runtime/processCenterRuntime.js:1-70`；`frontend/src/meta/process/businessProcessRegistry.js:13-28,323-350`。

## 三、各模块业务能力地图

统一口径：入口“已登记”只表示源码中有流程中心模块/节点，不保证真实用户可见。开发状态仅为 AS-BUILT 粗分；“已完成业务能力”限于可证实的对象/动作/节点，不宣称端到端完成。未做数据库只读数量核验，历史 Registry 的数字只可作历史参考。

| 模块与流程职责 | 流程中心入口／唯一流程（静态） | 当前开发状态与已观察业务能力 | 未完成或待证事项；订单生产主线判断 |
|---|---|---|---|
| CRM／接单与需求形成 | 已登记 `/process-center?module=CRM`，源码 1 条订单流程；接单、订单评审、产品设计节点有目标路由，后续 BOM/工艺/工程核算/制造输出节点仍为 planned/frozen | 部分完成：`SalesOrder`、`SalesOrderItem` 保留客户、交期、销售负责人及工程引用；订单评审有关联模型 | 当前用户入口、评审真实通过、订单需求形成及下游交接未验证；**需要收尾** |
| PDE／订单工程准备到制造定义 | 已登记单条 PDE 正式流程，含需求、准备、评审、设计、版本、核算、BOM、工艺、资料、制造输出等节点 | 部分完成：产品/版本、BOM/工艺版本、工程资料与 `ProductManufacturingOutput` 模型及状态动作存在 | Registry 节点 `PASS` 不能证明真实工程发布；与订单及计划的同一对象身份、制造可用事实需验证；**需要收尾** |
| EMD／企业主数据支撑 | 已登记单条主数据维护流程（组织、客户、供应商、物料、BOM、工艺、仓库） | 部分完成：物料与单位等主数据模型存在 | 主数据权威、正式用户可见与来源关系尚未本轮验证；作为支撑接入，**需要收尾** |
| SCM／需求到采购与供应保障 | 已登记单条采购与供应商结算流程，含申请、审批、询价、报价、比较、核价、订单、收货、检验等 | 部分完成：采购申请、采购订单、收货、检验等模型和流程节点存在 | 流程跨 WMS/QMS/FIN，真实入口及对象连续性未验证；台账有采购家族部分用户可见冲突；**需要收尾** |
| PLAN／需求与生产/采购计划 | 目录标为 planned；本次未见活动 PLAN 正式流程，另有 `/planning/requirements` 等直接路由 | 部分完成（技术）：`Demand`、`PlanningRequirement`、`PurchasePlan`、`ProductionPlan` 模型与服务存在 | 流程中心正式入口、需求到计划再到工单的执行交接未证；**需要重新设计流程接入**，保护现有对象 |
| MRP／物料净需求与供给建议 | 目录 planned，无本次可见活动正式流程 | 部分完成（技术）：`MaterialRequirementsPlanningRun`、`MaterialRequirementProposal` 模型与计算服务存在 | 建议不是正式采购/生产执行；入口、人工复核及下游转换待证；**需要重新设计流程接入** |
| MPS／主生产计划 | 目录 planned，无本次可见活动正式流程 | 部分完成（技术）：`MasterProductionScheduleRun/Line`、需求分配模型与提案服务存在 | `proposed/reviewed` 不等于生产任务；入口、产能与批准交接待证；**需要重新设计流程接入** |
| APS／高级排程 | 目录 planned，无本次可见活动正式流程 | 未发现本轮范围内可证明的独立排程闭环 | 有限产能、资源排程和制造执行链接待建立；**暂不适合直接连接** |
| WMS／收货与库存、交付 | 已登记单条仓储流程，仅收货与库存余额 2 节点 | 部分完成：`WarehouseInbound`、`InventoryBalance`、`InventoryTransaction` 等模型存在 | 流程缺正式出库/发运/客户交付节点；台账记载收货入口漂移；**需要重新设计交付段并收尾既有入口** |
| MES／生产执行 | 目录 planned；生产流程本身也为 planned，生产工单节点无目标页面 | 未开发正式流程（本轮未见 MES 业务应用模型与可操作节点） | 工单、工序执行、反馈、完工及与 PLAN/WMS 的对象交接缺口最大；**暂不适合直接连接** |
| QMS／质量检验 | 已登记单条质量流程，当前 1 个来料检验节点 | 部分完成：采购来料检验模型及路由存在 | 过程/成品检验、质量放行与 MES/交付衔接未证；台账记载用户无法从正常路径打开来料检验；**需要收尾** |
| FIN／结算 | 不在静态目录初始 14 项中，但由活动 FIN 流程补入运行模块；应付、付款、状态、结算完成节点 | 部分完成：若干采购付款准备与结算对象、页面路由存在 | 与订单生产交付主线是下游财务旁链，生产付款执行边界不得扩张；用户可见路径存在历史冲突；**需要收尾但非本主线首要瓶颈** |
| BI/FDM／分析 | 目录 planned，无活动正式流程 | 未证明业务闭环 | 只可作为将来分析消费者，**暂不适合直接连接** |
| KPI／绩效 | 目录 planned，无活动正式流程 | 未证明业务闭环 | 只可作为将来指标消费者，**暂不适合直接连接** |
| ProfitOS／经营效益 | 目录 planned，但源码另有活动绩效流程，可能被运行模型补充 | 部分完成／状态冲突：绩效节点从 SCM 节点投影，供应商与采购员绩效有不同实现成熟度 | 目录计划态与流程活动态需统一核验；不应反向阻塞订单生产主线；**需要收尾** |

所有模块的真实点击路径、页面标题、可见记录数、实际业务写入和用户人工验收在本轮均为 NOT VERIFIED，不能以本表将任何模块升级为 FROZEN。源码证据集中在 `frontend/src/meta/process/businessProcessRegistry.js:13-302`、`frontend/src/meta/runtime/crmOrderProcessRegistry.js:1-30`、`backend/sales/models.py:22-132`、`backend/pde/models.py`、`backend/planning/models.py:5-373`、`backend/procurement/models.py`、`completed_module_registry.v1.json`。

## 四、订单 → 工程 → 计划 → 生产 → 交付主线

| 交接点 | 已有事实 | 当前缺口与判定 |
|---|---|---|
| CRM 订单入口 | 销售订单、行、客户、交期、工程引用在模型中；CRM 接单/评审节点已登记 | 真实菜单路径、订单评审通过、需求形成同源证据未核实；**仅具备技术入口基础** |
| 订单 → PDE | 订单行可引用产品版本和制造输出；PDE 有订单工程评审与工程准备对象 | 同一订单行到工程版本/BOM/工艺/制造输出的授权、状态与业务事实闭环未验证；**部分可连接** |
| PDE → PLAN/MPS/MRP | `Demand` 可绑定订单行、产品版本及已发布制造输出；MPS/MRP 模型和服务有引用链；未发布工程组合不得进入新制造需求 | 流程中心没有活动 PLAN/MPS/MRP 正式流程；提案与正式计划/执行边界需核对；**技术链可设计，运行链未证** |
| PLAN → MES | `ProductionPlan` 存在 | MES 生产工单/工序反馈/完工正式流程未证；**当前主线断点** |
| MES → WMS → 交付 | WMS 有入库与库存对象、部分页面 | 无本轮可证的完工入库 → 库存 → 出库/发运 → 客户交付连续链；**当前主线断点** |

`backend/planning/services.py:361,451` 支持 MPS/MRP 提案生成的源码证据；`backend/planning/models.py:47-80` 对制造需求要求正式发布的工程组合。以上不能代替数据库实有对象、当前权限或人工验收。

## 五、需优先澄清的结构性问题

1. **流程中心登记 ≠ 当前运行**：静态模块状态、节点路由和 `PASS` 属性只证明声明；需以同一当前用户从正常菜单核实可见入口、唯一流程、节点落点和返回路径。
2. **无活动流程却有直接页面**：PLAN/MRP/MPS 的后端对象及计划路由已存在，而流程中心入口为 planned；不应把这类能力标为“未开发”，也不能称为已接入流程。
3. **对象连续性不等于业务闭环**：订单行、工程输出、需求、计划的 FK/服务链存在；MES 执行和交付对象链没有被本轮证明。
4. **跨模块节点与平行入口风险**：SCM 正式流程含 WMS/QMS/FIN 页面；它们各自也有流程定义；需判断是跨模块引用、兼容入口还是重复正式节点，不得先删已有入口。
5. **用户现实冲突**：Registry 记录采购收货、来料检验、部分应付/结算入口存在历史可见性冲突；在用户路径复验前不得沿用自动 `PASS`。
6. **责任链**：销售负责人、创建/审核账户等字段和组织权限事实存在，但不能据此认定跨模块最终责任链已签署；GRA仅列为未来责任增强，不作为本轮主线前置开发任务。
7. **运行态覆盖来源**：流程 Registry 可消费 localStorage；正式流程权威与当前浏览器状态的一致性需专门核查，不得凭静态文件假定一致。

## 六、优先开发建议（仅准备，不授权实施）

P0：先做正常菜单路径的只读运行盘点，记录各模块真实入口、单一正式流程、节点可达、同一对象身份和现有用户可见差异；对用户已指出的漂移按当前缺陷最小整改另行授权。此项是事实核验，不重建模块。

P1：以一个真实订单行建立 CRM → PDE → PLAN 的对象与状态交接规范：订单评审、工程准备完成、正式制造输出、需求形成、MPS/MRP 提案与计划确认分别保留其独立权威和责任。未获受控数据源与准入前只定义验收场景，不创建或重放业务对象。

P2：把 PLAN → MES 生产工单/工序反馈/完工，以及 MES → WMS 入库/出库/交付列为两个独立缺口包；先明确业务起终点和权威对象，再谈模型、权限、页面与流程实现。APS、BI/KPI/ProfitOS 不应提前成为订单生产闭环的必经建设前置。

P3：在不替代既有 SCM/QMS/FIN 成果的前提下核清跨模块导航与真实业务对象关系；GRA按具体责任节点独立设计，不以其未完成阻断流程能力盘点，但不得绕过受其约束的正式授权 Gate。

## 七、保护边界、合规与最终判断

历史 Registry 的 34 个模块记录和用户报告的真实运行冲突原样保留；未访问 Protection/Acceptance 数据库，未计算或重新签署 Hash。Phase B Protection Baseline 与 Source Qualification 相关阻断仍保持，不因本盘点解除。

| Compliance Item | Result | Evidence / Note |
|---|---|---|
| Original Goal | PASS | 完成流程中心能力地图与订单生产交接缺口分类 |
| Governance Reading / Effective Instruction Set | PASS | 活动 V1.2 第 34 节、保护规范、Registry 与本报告控制单 |
| Scope / Stop Condition | PASS | 只读分析和新增报告；后续开发未启动 |
| Existing Results Preserved | PASS BY SCOPE | 未修改菜单、路由、业务实现或数据；不等于运行态非回归测试 |
| Automated Tests / User-Visible Real Path / UI Data Visibility | N/A / NOT VERIFIED / NOT VERIFIED | 本轮非开发、非 UI 验收，未启动应用或读取数据库 |
| User Manual Validation | PENDING | 不以 Registry PASS 代替人工验收 |
| Production Boundary | PASS BY SCOPE | 无生产业务写入；无数据库访问 |
| Report vs User Reality Conflict | HISTORICAL CONFLICT PRESERVED | 不撤销、不覆盖用户既有负面观察 |

保护状态：Documentation Changed = YES（仅新增本报告）；Code/Database/Migration/API/Page/Organization/Employee/Permission/Workflow/GRA Changed = NO；Unauthorized Business Writes = 0。  
Context Scope = CONTROLLED；Task Scope = SINGLE；Review Level = B；Full Content Review Required = NO。  
归档回读、实际行数与 SHA256 以保存后校验结果为准，不在正文预填。

**PCE BUSINESS PROCESS CENTER DEVELOPMENT NEEDS PREPARATION**

结论：订单—工程—计划的模型/服务连接已有技术基础，但生产执行与交付闭环及当前用户流程入口均未获本轮证实。盘点到此停止；等待单独的《PCE业务流程中心订单与生产运作流程收敛开发指令》及所需门禁授权。
