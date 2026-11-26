# FINAL / CONSOLIDATED

# 《Phase B GRA第一应用业务对象裁决结果 FINAL / CONSOLIDATED报告》

日期：2026-09-29  
Proposal：`NCPSB-SP-A-20260929-001`  
Logical Source：`PCE-NCPB-A-REBUILD-SOURCE-P01`  
性质：五项候选对象比较与人工裁决空缺记录；非正式 Decision、非实施  
Review Level：B；Full Content Review Required：NO  
最终 Gate：`GRA FIRST APPLICATION OBJECT BLOCKED`

## 一、裁决输入与保护预检

承接《Phase B GRA第一应用场景边界确认 FINAL / CONSOLIDATED报告》：工程版本发布责任仍是候选首场景。当前指令列出五类对象及 `ACCEPT/MODIFY/REJECT` 空白复选框，但没有勾选任何候选、填写最终对象、唯一标识、责任类型、企业/数据/时间范围或跨模块判断。本轮只能比较候选并记录**尚无人工对象裁决**，不得由技术判断代选。现有源码只读事实不等于运行数据库存在对象或治理主体已批准。

```text
EFFECTIVE INSTRUCTION SET
ACTIVE = 五类业务对象只读比较、责任和数据/模块边界缺口登记；本报告
FROZEN = 734F/ABA 历史证据；PDE/BOM/生产/组织权限/Workflow 既有事实权威；未关闭 DGI/HC/GAP
NOT AUTHORIZED = 指定责任人、创建 GRA/Authorization ID/Decision、修改产品/工程/BOM/生产/权限/Workflow/数据库、Migration、API/页面开发

INSTRUCTION CONTROL SHEET
Original Goal = 由有权主体裁决 GRA 第一绑定对象
Current Goal = 给出候选可核验差异并保持未填最终选择的事实
IN SCOPE = 当前源码与前轮场景报告只读核查；本报告
OUT OF SCOPE = 代选、签署、业务发布、跨模块实施和技术准入
Database Boundary = 不连接数据库
Non-Regression Baseline = 既有 PDE/BOM/生产/权限/Workflow 不变
User Acceptance Path = N/A（无 UI 交付）
Stop Condition = 最终对象、责任链及范围未由主体明确时保持阻断
```

```text
COMPLETED MODULE GOVERNANCE READING RECEIPT
Project Instructions = D:\Dev-PCE\AGENTS.md; D:\Dev-PCE\Source\AGENTS.md
Formal Governance Standard = D:\Dev-PCE\Source\docs\governance\PCE CODEX开发指令规范管理V1.2.md
Preservation Standard Read = YES
Completed Module Registry Read = YES
Registry Module Count = 34
Affected Frozen Modules = []
Freeze Contracts Read = []
Unfreeze Authorization = NO / NOT REQUIRED FOR THIS DOCUMENT-ONLY TASK
Preflight = SAFE TO MODIFY (new report only)
```

本轮仅新增报告，未触及 Frozen Core/Shared Dependency 实现；未来如拟变更任何模块须重新预检。734F 与 ABA 均仅为历史证据。

## 二、候选对象 A～E 比较

| 候选 | 当前源码中的可能身份规则 | 当前可见状态/关联 | 作为首个 GRA 责任对象的代价 | 人工选择 |
|---|---|---|---|---|
| A `ProductVersion` | 数据行主键；业务上 `product + version_no` 唯一（`backend/pde/models.py:854-879`） | draft/reviewed/released/obsolete，生效/失效日期 | 较接近单一产品版本责任；仍须证明发布动作、正式审核链与组织边界 | `NOT SELECTED` |
| B `EngineeringDocumentVersion` | 行主键；`document + document_version` 唯一（`backend/pde/models.py:2637-2669`） | 引用 ProductVersion、BOMVersion、RoutingVersion，状态和有效期 | 资料版本清晰，但不得把引用的 BOM/工艺自动并入其发布责任 | `NOT SELECTED` |
| C `BOMVersion` | 行主键；`product + bom_version` 及非空 `bom + bom_version` 有唯一约束，另有修订和标准/按单作用域（`backend/pde/models.py:2046-2124`） | 产品/订单工程/工程核算关联、状态、审批投影 | 可能牵连制造结构、生产与采购；需独立 BOM 发布治理范围 | `NOT SELECTED` |
| D `EngineeringChangeNotice` | 行主键；`change_no` 唯一（`backend/pde/models.py:2724-2750`） | before/after 产品版本，draft/reviewing/approved/effective | 是变更通知/生效责任，不等同单一版本发布；需定义变更链 | `NOT SELECTED` |
| E `ProductManufacturingOutput` | 行主键；产品/产品版本/BOM 版本/工艺版本/可空资料版本组成受控版本集合（`backend/pde/models.py:2753-2835`） | draft/engineering_review/released_to_manufacturing/inactive | “发布至制造”直接触及生产，跨版本集合影响最大；不能作为纯 PDE 内部责任 | `NOT SELECTED` |

这些是**源码中的候选键/约束**，不是当前业务记录的唯一 ID，也不证明运行库的 Schema 与数据符合源码。A～E 不能互换；若治理主体选择一个，正式 D-06 须明确对象类型、行身份/业务键、具体适用版本及是否只验证责任而不执行发布。本轮最终第一应用对象、对象类型、业务唯一标识及选择理由均为 `NOT PROVIDED`。没有技术默认胜出项。

## 三、责任链裁决状态

| 责任 | 业务含义 | 是否纳入 | 未来需说明 |
|---|---|---|---|
| 创建责任 | 负责选定对象形成 | `NOT SELECTED` | 对象形成边界、组织范围、原件和有效期 |
| 审核责任 | 独立核对对象满足发布前条件 | `NOT SELECTED` | 与创建/发布分离、审核依据、现有 Workflow 事实 |
| 发布责任 | 对选定对象的正式发布资格负责 | `NOT SELECTED` | 责任授权与实际发布动作的分界、服务端权限/状态机 |
| 其它 | 由主体提出 | `NOT PROVIDED` | 不得从岗位名、页面或系统 Role 推导 |

若有权主体选择三段责任，可在未来设计中比较“创建 → 独立审核 → 发布”的逻辑链；当前不把它写成已确认流程，不任命 Owner/Reviewer/Approver。GRA 只表达经签发的责任事实，不能替代系统 Permission、正式审批或自动推进版本状态。

## 四、数据范围与第一阶段排除

企业主体、组织/部门、对象范围、截止时间/时区、责任有效期、数据来源和排除清单全部未填写，故 `DATA BOUNDARY = MISSING`。候选对象的模型字段不能代替企业批准。第一阶段的**保护性非授权边界**是：不修改产品、工程资料、BOM、生产数据；不重建全 ERP 权限，不改全部 Workflow，不涉及财务/采购审批或质量放行责任。用户表单中的排除项未勾选，不能声称这些已获正式治理签署；但在未另获授权前一律不实施。

要用于 D-06，需将固定 Proposal/Logical Source 双 ID 与**单一选定业务对象**、企业/组织/数据及时间边界直接绑定；若对象为 C/E 或包含按单版本，还须清楚划定订单工程实例、产品/BOM/工艺版本集合与下游范围。

## 五、跨模块影响

| 模块 | 当前可见依赖或风险 | 本轮人工“是/否” |
|---|---|---|
| PDE | A、B、D 属 PDE 工程对象；E 含工程输出；存在维护/发布 action code | `NOT SELECTED` |
| BOM | B 引用 BOM；C 直接为 BOM 版本；E 引用 BOM | `NOT SELECTED` |
| 生产/工艺 | B/E 引用 RoutingVersion；E 有发布至制造状态 | `NOT SELECTED` |
| 采购 | C/E 的版本选择可能产生下游依赖，未证明具体链 | `NOT ASSESSED` |
| 财务 | 未见本首场景的正式授权链 | `NOT ASSESSED` |
| 质量 | 未见本首场景的正式放行链 | `NOT ASSESSED` |

表中“可见依赖”仅为源码结构，**不是**对真实运行范围的“涉及/不涉及”裁决。所有人工复选仍空。未来选 C/D/E 或将 A/B 的责任扩展至 BOM、生产、采购、财务或质量时，须单独做数据权威、已开发模块、Frozen Core/Shared Dependency、审批和非回归影响评估；本轮不自动扩大。

## 六、D-06 正式 Decision 条件与后续流程

当前**不具备形成正式 D-06 Decision 的完整范围材料**：五候选未裁定唯一对象，无实际业务标识、三类责任纳入选择、企业/组织/数据/时间界限、跨模块“是/否”和理由，也无有权主体签署原件。后续须由治理主体明确选择及排除，再把对象/责任/边界写入有版本的签署原件，绑定双 ID，由 Governance Decision Verification 独立核验主体权限、原件 Hash、时间和范围。仅在相应 Decision 按正式规则验证后，才可按其明示授权进入 Implementation Authorization Assessment；仍不能自动进入开发。

本轮只新增本报告。未指定人员，未创建 GRA、Decision 或 Authorization ID；未修改任何产品/工程/BOM/生产/权限/Workflow/数据库/代码，未执行 Migration、开发 API/页面或创建 Source/Baseline。非 UI 交付，`DELIVERED USER STATE CONTRACT = N/A`。

```text
FIRST APPLICATION OBJECT = NOT SELECTED
OBJECT UNIQUE IDENTITY = NOT PROVIDED
CREATOR / REVIEWER / RELEASE RESPONSIBILITIES = NOT SELECTED
ENTERPRISE / ORGANIZATION / DATA / TIME BOUNDARY = MISSING
CROSS-MODULE HUMAN IMPACT DECISIONS = NOT PROVIDED
FORMAL D-06 DECISION = PENDING
DGI-01~DGI-07 = OPEN
HC-01~HC-04 = MISSING
GAP-01~GAP-04 = OPEN
IMPLEMENTATION AUTHORIZATION ASSESSMENT = NOT ENTERED
SOURCE QUALIFICATION REVIEW PRE-CHECK = NOT READY
CODE / DATABASE / WORKFLOW / PERMISSION CHANGED = NO
SOURCE / BASELINE / RUNTIME ENVIRONMENT CREATED = NO
PHASE B TECHNICAL RE-ADMISSION = BLOCKED
GRA FIRST APPLICATION OBJECT BLOCKED
```
