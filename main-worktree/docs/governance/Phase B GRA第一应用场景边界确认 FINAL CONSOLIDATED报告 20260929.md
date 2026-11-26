# FINAL / CONSOLIDATED

# 《Phase B GRA第一应用场景边界确认 FINAL / CONSOLIDATED报告》

日期：2026-09-29  
Proposal：`NCPSB-SP-A-20260929-001`  
Logical Source：`PCE-NCPB-A-REBUILD-SOURCE-P01`  
性质：第一应用边界的只读分析与待人工确认清单；非正式 Decision  
Review Level：B；Full Content Review Required：NO  
最终 Gate：`GRA FIRST APPLICATION SCOPE BLOCKED`

## 一、第一应用场景选择状态与保护边界

前轮 D-06 的候选文字为“工程版本发布责任”。本轮指令要求对此选择 `ACCEPT / MODIFY / REJECT`，并在产品工程版本、工程资料版本、BOM 版本、工程变更版本、发布版本之间确认对象，但所有复选框、对象标识、责任链及理由均未填写。因此“工程版本发布责任”仍是**候选场景**，不是已确认的首个 GRA 适用范围。本轮可提供源码结构证据与收敛建议，不能替有权治理主体选定对象或任命人员。

仅只读检查当前工作树源码和前述报告；未连接 Protection、Acceptance 或开发数据库。源码中的模型/状态和动作名不能证明目标运行库 Schema 已应用、具体业务记录存在或真实发布流程已执行。734F、ABA 历史证据及已开发模块保持原状。

```text
EFFECTIVE INSTRUCTION SET
ACTIVE = 工程版本候选对象、责任类型、模块引用/影响和后续 Decision 输入边界的只读评估
FROZEN = 734F/ABA 历史证据；既有 PDE/BOM/生产/权限/Workflow 数据权威；未关闭 DGI/HC/GAP
NOT AUTHORIZED = 代选首场景、指定 Owner/Reviewer/Approver、修改产品/工程/BOM/权限/Workflow/数据库、Migration、API/页面/GRA/Source/Baseline 创建

INSTRUCTION CONTROL SHEET
Original Goal = 确认 GRA 第一应用业务场景边界
Current Goal = 提供对象候选比较并标出不可由 Codex 代决的唯一对象、责任链和数据范围
IN SCOPE = 当前源码及历史报告只读分析；本报告
OUT OF SCOPE = 正式裁决、人员任命、业务发布、实施和技术准入
Database Boundary = 不连接数据库
Non-Regression Baseline = 现有组织权限与 PDE/BOM/生产/Workflow 功能不变
User Acceptance Path = N/A（无 UI 交付）
Stop Condition = 关键复选和对象/范围未由主体确认时保持阻断
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

本轮仅新增报告，未影响冻结实现；未来如改动 PDE 或共享依赖须重做完成模块保护预检，并在命中 Frozen Core 时取得明确 Unfreeze 授权。

## 二、业务对象候选与唯一标识

| 待人工选择的对象 | 当前源码可见身份/生命周期 | 与“发布责任”的关系及范围风险 | 本轮结论 |
|---|---|---|---|
| 产品工程版本 `ProductVersion` | `product + version_no` 唯一，`draft → reviewed → released → obsolete` 状态、生效/失效日期（`backend/pde/models.py:854-879`） | 可作为单一产品版本的狭义发布责任对象；但发布动作的正式服务端状态机/审批事实未在本轮验证 | `CANDIDATE`，不得自动选定 |
| 工程资料版本 `EngineeringDocumentVersion` | `document + document_version` 唯一，引用产品版本、BOM 版本、工艺版本，具状态及有效期（`backend/pde/models.py:2637-2689`） | 对象较明确但天然关联三类版本，责任是否仅针对资料发布须人工界定 | `CANDIDATE`，不得自动扩为 BOM/工艺批准 |
| BOM 版本 `BOMVersion` | 版本号/修订、标准或按单作用域、状态、审批投影及产品版本/核算关联（`backend/pde/models.py:2046-2092`） | 一旦选为首场景，将触及 BOM 正式发布与可能的生产/采购下游，不是“只读引用” | `SEPARATE SCOPE REVIEW REQUIRED` |
| 工程变更版本/通知 `EngineeringChangeNotice` | `change_no` 唯一，before/after 产品版本与 `draft/reviewing/approved/effective` 状态（`backend/pde/models.py:2724-2750`） | 是变更事件而非通用“版本发布”对象，可能引发多版本同步；须单独定义对象与生效责任 | `SEPARATE SCOPE REVIEW REQUIRED` |
| 制造定义发布 `ProductManufacturingOutput` | 产品、产品/BOM/工艺/资料版本集合；`draft/engineering_review/released_to_manufacturing/inactive`（`backend/pde/models.py:2753-2835`） | “发布至制造”明确跨向生产，责任对象为版本集合而非单一产品版本 | `SEPARATE SCOPE REVIEW REQUIRED` |

源码还可见工程版本维护/发布、工程资料发布及工程发布的 action code（`backend/pde/views.py:844-848`）；动作编码存在不等于 GRA 责任授权已存在或发布权限可用。**最小化技术建议**：若目标只是验证 GRA 如何绑定一个版本责任，不触发实际发布，可优先由有权主体比较 `ProductVersion` 与 `EngineeringDocumentVersion` 中的**一种**作为单一对象；这不是本报告的选择。必须说明业务唯一标识规则（正式对象类型 + 主键 + 业务版本键）、企业/组织及时间范围，并通过真实运行事实核验后才能写入 Decision。

## 三、责任链：仅逻辑定义，未纳入/未任命

| 责任类型 | 候选含义 | 本轮是否由主体勾选 | 未来需核验 |
|---|---|---|---|
| 创建责任 | 对指定版本的形成/维护负责 | `NOT SELECTED` | 对象、动作范围、组织边界、责任原件与有效期 |
| 审核责任 | 对指定版本内容和前置条件复核 | `NOT SELECTED` | 与创建/发布人员和角色的分离规则、正式审核事实 |
| 发布责任 | 对允许版本进入正式发布状态承担授权责任 | `NOT SELECTED` | 发布权、对象状态机、必要审批、下游影响和原件 |
| 其它责任 | 须由主体描述 | `NOT PROVIDED` | 不得从岗位或页面状态自动推导 |

若未来选择三项，逻辑链可描述为“形成 → 独立审核 → 受控发布”，但本轮未确认各节点是否纳入、审批节点由谁掌握或谁是责任人。GRA 第一阶段仅验证**责任授权事实、有效期和依据**，不替换现有系统 Permission、PDE 发布服务或正式 Workflow；GRA `ACTIVE` 也不得自动把工程版本状态推进为 `released`。

## 四、组织权限和数据范围边界

组织事实继续由 Company/Department/OrganizationUnit 提供，人员由 Employee/User 提供，系统操作能力及数据范围由 Role/Permission/UserRoleScopeAssignment 提供；GRA 只在经签发后表达“某自然人/账户对指定版本对象承担何种治理责任、范围、时间及原件依据”。职位、默认角色、超级用户身份或普通 Workflow 决策均不自动等于治理任命。本轮表单“接受/修改”未勾选，所以该原则仍是**待正式确认的既有设计边界**，不是新批准事实。

尚缺 Data Scope：企业主体、公司/组织/部门、选定版本对象类型和唯一标识、标准/按单属性（若涉及 BOM）、数据截止点/时区、责任有效期、允许读取和排除的数据集合，以及与固定 Proposal/Logical Source 双 ID 的关联依据。没有具体对象/范围，不应创建空泛的“全工程版本”授权。

## 五、PCE 模块影响与第一阶段包含/排除

| 模块 | 当前可见关系 | 首阶段可考虑的只读引用 | 不得自动进入的变更 |
|---|---|---|---|
| PDE/产品工程 | ProductVersion、EngineeringDocumentVersion、EngineeringChangeNotice、发布 action code | 被选定版本的身份、状态与责任验证依据 | 新建/审核/发布动作、状态迁移、工程核算或资料变更 |
| BOM | EngineeringDocumentVersion 和制造输出引用 BOMVersion；BOM 自有版本/审批投影 | 若未选 BOM 为主对象，仅作为版本一致性引用 | BOM 发布、变更、作用域重选、审批事实改写 |
| 生产/工艺 | EngineeringDocumentVersion 引用 RoutingVersion；制造输出有发布至制造状态 | 若仅核对工程版本，可引用关联工艺身份 | Routing 发布、生产准备、制造输出状态推进 |
| 采购/财务/质量 | 本轮未建立与首场景的授权链 | 无自动纳入 | 采购/财务审批、质量放行及其权限/流程改造 |

在第一阶段，**暂不授权**任何跨模块写入、全 ERP 权限治理或全 Workflow 改造；这是一条保护边界，不等于治理主体已在空白复选框中正式勾选“排除”。若首场景对象本身涉及 BOM、生产、采购、财务或质量，应单独评估数据权威、影响模块、冻结契约、恢复和非回归。尤其“发布至制造”不能被描述成零下游影响的普通版本属性。

## 六、最小验证目标与正式 Decision 所需输入

最小验证仅应回答：选定**一个**对象后，能否从正式组织/人员事实核对责任主体，能否依据真实签发原件表达其责任授权，能否核对责任有效期与范围，能否追溯签发/审核依据；不执行真实版本发布，不做企业级推广。技术上可设计只读验证路径，但当前无人员任命、授权原件或运行库事实，故不能声称该路径已通过。

正式 D-06 Decision 前须由有权主体提交：①是否继续采用该候选及 `ACCEPT/MODIFY/REJECT`；②唯一主业务对象及对象类型/业务键；③创建/审核/发布责任各自是否纳入、是否双人/多角色分离；④企业/组织/数据/时间范围；⑤不包含项；⑥与 `NCPSB-SP-A-20260929-001`、`PCE-NCPB-A-REBUILD-SOURCE-P01` 的明确关系；⑦对 BOM/生产/采购/财务/质量的逐项影响结论；⑧决策主体、事项权限、签署原件及其版本/Hash。D-04 轻量验证与正式审批关联的边界亦须一并确认。

## 七、是否具备进入正式 Decision 条件与未执行事项

**不具备**。对象类型、唯一标识、三类责任是否纳入、组织与数据范围、跨模块影响、双 ID 适用关系及人工选择均未确认；签署主体与原件仍缺。故只能将分析交给治理主体收敛场景，不能把工程版本发布责任标为已正式确认，也不能关闭 DGI/HC/GAP 或进入实施授权评估。

本轮仅新增此报告；未指定人员、创建 GRA/Authorization ID/Decision、修改产品/工程/BOM/权限/Workflow/数据库/代码，未执行 Migration、开发页面/API 或创建 Source/Baseline。非 UI 交付，`DELIVERED USER STATE CONTRACT = N/A`。

```text
FIRST APPLICATION CANDIDATE = ENGINEERING VERSION RELEASE RESPONSIBILITY
FIRST APPLICATION HUMAN CHOICE = NOT PROVIDED
FIRST OBJECT TYPE / UNIQUE IDENTITY = NOT CONFIRMED
CREATOR / REVIEWER / RELEASE RESPONSIBILITIES = NOT SELECTED
ENTERPRISE / ORGANIZATION / DATA BOUNDARY = MISSING
CROSS-MODULE IMPACT = NOT ASSESSED AS FORMAL FACT
FORMAL D-06 DECISION = PENDING
DGI-01~DGI-07 = OPEN
HC-01~HC-04 = MISSING
GAP-01~GAP-04 = OPEN
IMPLEMENTATION AUTHORIZATION ASSESSMENT = NOT ENTERED
SOURCE QUALIFICATION REVIEW PRE-CHECK = NOT READY
CODE / DATABASE / WORKFLOW / PERMISSION CHANGED = NO
SOURCE / BASELINE / RUNTIME ENVIRONMENT CREATED = NO
PHASE B TECHNICAL RE-ADMISSION = BLOCKED
GRA FIRST APPLICATION SCOPE BLOCKED
```
