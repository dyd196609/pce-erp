# FINAL / CONSOLIDATED

# 《Phase B New Controlled Protection Baseline Governance Responsibility Authorization Integration评估FINAL / CONSOLIDATED报告》

日期：2026-09-29  
阶段：Governance Responsibility Authorization Integration Assessment  
类型：只读模型整合与差距评估；非开发、非授权批准  
Source Proposal：`NCPSB-SP-A-20260929-001`  
Logical Source：`PCE-NCPB-A-REBUILD-SOURCE-P01`  
Review Level：B（组织、权限、责任与验证链的跨域设计判断）；Full Content Review Required：NO  
最终 Gate：`GOVERNANCE RESPONSIBILITY INTEGRATION ASSESSMENT COMPLETE`

## 一、范围、证据层级和治理控制

本轮承接 `D:\Dev-PCE\Source\docs\governance\Phase B New Controlled Protection Baseline Governance Input Human Coordination Readiness FINAL CONSOLIDATED报告 20260929.md` 的 HC-01～HC-04，以及 Gap Closure 报告中的 `NCPSB-GAP-01`～`04`。直接前态：人工任命原件 0、已接受输入 0、已关闭 Gap 0，四角色身份及六组冲突仍未核实。目标是评估现有组织与权限基础能否承载未来责任授权，不建立新责任主体或批准事实。

| 证据层 | 本轮核验范围 | 允许结论 |
|---|---|---|
| 源码模型与服务 | `backend/system/models.py`、`backend/pfm/models.py`、`backend/workflow_runtime/models.py`、`backend/system/authorization.py`、`backend/workflow_runtime/execution_resolution.py` | 结构和既有解析能力在当前工作树中可观察 |
| Migration 文件 | `backend/system/migrations`、`backend/pfm/migrations`、`backend/workflow_runtime/migrations` 的相关建模记录 | 文件存在；不代表任何指定数据库已经应用 |
| 历史治理材料 | `docs/governance/组织、岗位、账户、角色、权限体系专项报告.md`、`docs/governance/PCE Responsibility Master Data V1岗位责任角色权限语义边界确认报告.md` | 历史实现与语义边界参考；不替代当前运行事实或人工任命 |
| 当前业务数据库与运行数据 | 本轮未打开、未查询、未登录 | 行级人员、账户、授权、审批、Migration 应用状态均 `NOT VERIFIED` |

源码 `backend/system/models.py` 和 `backend/system/authorization.py` 在本轮开始时已有未提交修改；本报告只评价当前工作树可见模型，不把它等同于已冻结 Commit、当前 Protection Schema 或已部署运行态。历史专项报告曾给出基础能力 `READY`，其测试账户和计数是当时证据，不能自动升级为本轮治理任命事实。用户真实运行观察高于代码及历史报告。

```text
EFFECTIVE INSTRUCTION SET
ACTIVE = 本轮 Integration Assessment：只读组织/权限模型、HC-01～04 映射与差距报告
FROZEN = 734F 历史固定证据；ABA 漂移后历史证据；未接受独立治理输入；Phase B 技术准入阻断
COMPLETED, STILL BINDING = Human Coordination Readiness；Gap Closure；Governance Input Acceptance Verification
NOT AUTHORIZED = 任命、签署、权限/组织/数据库/Migration 修改、Source/Baseline/环境创建

INSTRUCTION CONTROL SHEET
Original Goal = 评估复用组织与权限基础支撑 HC-01～HC-04
Current Goal = 列出可复用模型、缺失治理授权事实、验证链绑定及 Gap 裁决
IN SCOPE = 源码、Migration 文件和既有治理报告只读检查；新增评估报告
OUT OF SCOPE = 数据库读写及 Migration 执行；指定自然人、创建授权、修改权限或业务对象
Database Boundary = 本轮不连接数据库
Non-Regression Baseline = 既有代码、数据、报告和 734F/ABA 身份不变
User Acceptance Path = N/A（非 UI 任务）
Stop Condition = 归档回读后停止，不进入开发或 Source Qualification Review
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
Unfreeze Authorization = NO / NOT REQUIRED
Preflight Result = SAFE TO MODIFY
```

仅新增本评估文档，不修改 `organization-structure` 或任何实现文件；Registry 当前 `currentFrozenVerifiedModuleIds=[]` 不等于既有功能可以被替换。Preserve-and-Extend 与用户现实优先继续有效。

## 二、现有组织与权限基础能力：七类对象逐项检查

下表“存在”均指当前工作树源码字段存在，不能推导该字段在 Protection、Acceptance 或其它运行库已应用，也不能推导具体行值已获批准。

| 对象 | 当前可观察字段与关系 | 可直接复用的基础事实 | 对治理任命的限制 |
|---|---|---|---|
| 公司资料 | `system.Company`：主键、`name`、`code`、`is_active`（`backend/system/models.py:59`） | 企业/公司身份、编号和启用状态的候选权威源 | 无 Company 层生效/失效期及正式 Owner 外键；`contact` 只是联系人，不是授权 Owner；Data Boundary 仍须人工批准 |
| 部门/组织 | `Department`：公司、父部门、编码、`is_active`、有效期；`OrganizationUnit`：公司、类型、父组织、有效期（同文件 :75、:112） | 公司—组织—部门层级、有效状态 | `Department.manager` 为文本，不是正式签署身份；指定数据边界、部门范围及历史时点仍需批准和当时快照 |
| 岗位 | `Position`：编码/名称、公司、部门、岗位族/等级、上级岗位、职责摘要、有效期、启用状态（:508）；`Responsibility`、`PositionResponsibility`、`PositionWorkflowResponsibility`（:622、:648、:671） | 岗位层级、稳定职责、岗位与流程责任类型（OWNER/REVIEWER/APPROVER/EXECUTOR） | 岗位/岗位职责是资格线索，不等于某自然人的 Phase B 治理任命；流程节点映射也不绑定此 Proposal 的授权号 |
| 员工档案 | `pfm.Employee`：主键、`employee_no`、姓名、状态、正式部门/岗位外键、可空的一对一 User 引用（`backend/pfm/models.py:6`） | Employee ID、自然人、任职和在职状态的核验基础 | 账户、部门、岗位外键允许为空；历史任职与指定治理授权未由此自动证明 |
| 用户账户 | `system.User`：主键、`username`、姓名、`company_id`、`is_active`、登录/创建/更新时间（`backend/system/models.py:33`） | User ID、登录账户与启用状态；可沿 Employee 的一对一关系关联 | `company_id` 为数值字段而非 Company 外键；账户身份不等于治理签署权限；`is_superuser` 也不自动成为 Source Approver |
| 角色 | `Role`：主键、`name`、`code`、描述（:579）；`UserRoleScopeAssignment`：User、Role、Company、Department、Scope、active/version/hash/时间（:742） | 系统角色、组织与数据范围分配 | 系统 Role 不等于 Source Owner/Preparer/Reviewer/Approver；分配缺专属 Authorization ID、签发/撤销和有效期字段 |
| 权限 | `Permission`：主键、`code`、`name`、`module`；`RolePermission` 唯一 Role–Permission 映射（:592、:605）；服务端 `AuthorizationService`（`backend/system/authorization.py:39`） | 动作权限代码、角色权限和服务端范围判断 | 对象/动作/数据范围主要由代码与另一个 Scope 对象组合表达，非单一 Permission 字段；业务动作可执行不证明治理任命或签署有效 |

`AuthorizationService` 的正式权限事实源为 `UserRoleScopeAssignment`，但仍有兼容性回退到 `workflow_runtime.UserOrganizationRoleAuthority`，且超级用户分支可通过业务动作检查（`backend/system/authorization.py:13-14,39-151`）。未来治理任命核验不得把兼容回退或超级用户通行当作独立签署授权。`workflow_runtime.WorkflowExecutionResolutionService` 已能沿岗位责任、员工、账户、角色/权限解析流程执行候选，并输出缺口代码（`backend/workflow_runtime/execution_resolution.py:30-69,78-210`）；这是可复用的只读解析模式，不是 HC-01～04 的既成分配。

## 三、HC-01～HC-04 Governance Responsibility Mapping Matrix

| 治理角色 | 需要事实 | 现有来源可复用部分 | 缺少的正式事实 | 状态 |
|---|---|---|---|---|
| Source Owner / `HC-01` | 员工、账户、组织、Source/企业/数据范围、任命权和有效期 | Employee↔User；Company/Department；岗位职责；UserRoleScopeAssignment | 此 Proposal 的 Owner 任命、Authorization ID、批准主体/记录、签发与撤销、精确治理范围 | `FOUNDATION OBSERVED / APPOINTMENT MISSING` |
| Source Preparer / `HC-02` | 员工、账户、输入准备职责、范围与任命 | Employee↔User；Position/Responsibility；系统 Role/Permission | 此 Proposal 的 Preparer 任命、授权号、输入/证据职责和禁止自审的证据 | `FOUNDATION OBSERVED / APPOINTMENT MISSING` |
| Technical Reviewer / `HC-03` | 员工、账户、独立审核授权、Schema/Migration/Commit/Runtime 范围 | Employee↔User；PositionWorkflowResponsibility 的 REVIEWER 类型；系统权限 | 此 Proposal 的 Reviewer 任命、审核对象与范围、独立性、授权号和有效期 | `FOUNDATION OBSERVED / APPOINTMENT MISSING` |
| Approver / `HC-04` | 员工、账户、最终批准权限、签发链与范围 | Employee↔User；PositionWorkflowResponsibility 的 APPROVER 类型；通用审批对象 | 此 Proposal 的最终批准权来源、Approver 任命、Authorization ID、有效期及与准备/复核分离证据 | `FOUNDATION OBSERVED / APPOINTMENT MISSING` |

当前任何岗位、角色、超级用户或历史审批记录都不能自动映射为这四个具名责任主体。四角色的真实人员和组织归属未做数据库行级核验；本轮不指定任何人。`HC-01`～`04`、`GAP-01`～`04` 均不得关闭。

## 四、现有字段与能力边界

### 4.1 已满足的结构基础（源码可观察）

1. 身份链可表达：Company/Department/Position → Employee → User，并有 Employee–User 可空一对一关系；Role/Permission 通过正式 Scope Assignment 和 RolePermission 链接。
2. 岗位职责层已区分 Position、Responsibility、Role、Permission；`PositionWorkflowResponsibility.ownership_type` 能表达流程岗位的负责、审核和批准类型，但不是治理授权记录。
3. 通用审批链有 `WorkflowInstance`、`ApprovalTask`、`ApprovalDecision`，Decision 保存 actor、action、hash、时间等（`backend/workflow_runtime/models.py:109-185`）。`SegregationOfDutiesAuthority` 有同用户、角色分离开关（:56-64）。
4. `OrganizationOperatingAuditRecord` 有 actor、对象、前后快照、原因及创建时间（`backend/system/models.py:715-739`）；只适用于其记录的组织运作写入，不能泛化为已发生的治理任命或撤销。
5. Migration 源文件可见相关对象的创建记录：`system/0001`、`0002`、`0005`、`0006`，`pfm/0001`、`0002`，`workflow_runtime/0001`。本轮未核对任何目标数据库的 Migration 应用状态或行级完整性。

### 4.2 尚缺的治理授权事实及控制

| 缺口 | 当前源码判断 | 所需治理决策/后续证据 |
|---|---|---|
| Proposal 专属责任任命 | 未发现可把四角色、User/Employee、双身份、授权范围和有效期绑定为一份正式任命的对象或原件 | 独立治理主体签发的任命原件；决定是否需受控治理授权层持久化 |
| Authorization ID 与版本 | UserRoleScopeAssignment 有自身主键、version/hash，但无外部治理授权号语义 | 签发方提供真实 Authorization ID、版本、原件 Hash，不由系统推测 |
| 签发、批准、撤销及生效历史 | 通用审批和组织审计可复用模式，但未见此 Proposal 的正式 Document Type、批准路线、撤销状态和历史链 | 明确签发主体、审批流程、撤销/更正规则及不可覆盖审计；另行授权实施 |
| 精确数据/Source/职责范围 | 系统 Scope 为 SELF/DEPARTMENT/ORGANIZATION/ALL/CUSTOM；无法直接承载提案、截止点、Schema 审核对象等治理范围 | 将 Proposal/Logical Source、企业组织、数据边界、审核对象和时间绑定到同一授权证据 |
| 六组独立性检查 | 通用 SoD 有同用户与角色分离配置，但未见四角色六组身份/角色/组织比较记录 | 四任命先获独立验证，再六组逐项检查；不得以相异 User ID 单独代替自然人核对 |
| 权限动作与治理责任的双门禁 | `AuthorizationService` 检查业务动作，但不证明人员被正式任命为该提案治理角色 | 未来动作须同时满足系统权限与有效治理授权；两者缺一即阻断 |
| 运行事实 | 本轮未连接任何数据库，且相关源码有未提交改动 | 后续只读核实目标环境 Schema、数据及授权原件；不能用源码存在宣称正式事实有效 |

## 五、是否需要新增治理授权层：评估结论与最小整合模型

**结论：需要一个与既有组织/员工/账户/角色/权限模型相连的治理授权事实层；不需要重复建设这些基础主数据。** 这是模型整合建议，不是新增表或开发授权。实现形态（既有受控 Workflow 的扩展、独立签发工件登记，或以后获批的持久化对象）尚须治理主体和架构复核选择，不能本轮预设为数据库表。

建议的最小语义关系如下，箭头仅表示未来核验依赖，不表示本轮建立数据：

```text
Company / OrganizationUnit / Department / Position
                 ↓
       Employee ↔ User
                 ↓
Role / Permission / UserRoleScopeAssignment
                 +
Proposal-bound Governance Authorization Evidence
  {Proposal ID, Logical Source ID, governance role, User ID, Employee ID,
   organization/data/action scope, Authorization ID, issuer, approver,
   issued/effective/expiry time, status, version, original-document Hash}
                 +
independent approval / revocation / change audit
                 ↓
Governance Input Acceptance Verification
```

治理授权层只绑定并验证既有身份事实，不复制员工、岗位、角色或 Permission 为第二套权威。岗位/职责可用于推荐具备资格的候选范围，但最终任命必须由有权人工主体签发。通用 Workflow 对象若未来复用，必须先有受控 Document Type、流程定义、独立审批和保留原件的授权；不能把现有 ApprovalDecision 记录自行解释为本提案批准。授权撤销、账户停用、员工离职/调岗、组织/角色变更或原件 Hash 变化时，后续核验须失效并重新评估。

## 六、与 Permission Organization Fact Package 的关系

`GAP-09` 的 Permission Organization Fact Package 应提供 Company/Organization/Department、Employee/User、Position/Responsibility、Role/Permission、Scope Assignment 及引用完整性和时点证据。它回答“组织与权限事实是什么”；HC-01～04 的任命原件回答“谁被有权主体为此 Proposal 授予哪项治理责任”。前者不能替代后者，后者也不能豁免前者的有效状态与范围校验。

未来证据包建议逐件保留源对象 ID、环境/Schema 身份、读取时点、字段快照、来源 Hash/版本与人工签发依据；若运行库未授权读取或对象/引用缺失，则记 `NOT VERIFIED / MISSING`。不得从页面显示、测试账户、ABA/734F 历史文件或兼容性权限回退推导正式权限组织事实。

## 七、与 Phase B Governance Input Acceptance Verification 的对接

| 顺序 | 只读验证入口 | 可提升到的状态 | 失败关闭条件 |
|---|---|---|---|
| 1 | 收到四份独立任命原件；登记真实 Input ID、原件位置、Hash、签发/接收时间 | 仅 `RECEIVED` | 模板、设计/缺口报告、无独立签发渠道不得作为输入 |
| 2 | 核验签发主体、User/Employee/组织/Role/Scope 事实、Authorization ID、双身份绑定、范围、有效期和撤销状态 | 单件按 `ACCEPTED / PENDING / REJECTED` | 任何身份或授权事实缺失不得接受；系统管理员身份不豁免 |
| 3 | 四件均接受后，六组 Identity、Role、Organization/委托关系及自然人冲突检查 | 冲突检查可出逐项结果 | 身份不全不得输出无冲突；冲突保持阻断 |
| 4 | 核验 Permission Organization Fact Package 与任命快照时点的一致性 | 可形成引用完整性证据 | 引用缺失、失效或权限范围不符不得关闭相关 Gap |
| 5 | 独立复核每个 Gap 的专属条件，保留状态转换、原件及失败原因 | 才可考虑逐项关闭 `GAP-01`～`04` | 原件收到、模型存在、用户有系统 Role 均不自动关闭 Gap |

此链仅设计与现有 Verification Register 的数据契约；本轮未收到新的独立任命输入，未产生 Verification ID、没有核验具体人员。未接入新 API、页面或运行服务。

## 八、Source Qualification Review Pre-check 与 GAP-01～04 裁决

| 检查项 | 当前状态 | 判定 |
|---|---|---|
| 公司/组织/员工/账户/岗位/角色/权限结构 | `OBSERVED IN CURRENT SOURCE` | 有复用基础，但目标数据库与运行数据未验证 |
| Proposal 专属四角色任命和授权号 | `MISSING` | 无独立签署原件；不得由组织或 Role 自动生成 |
| 审批链、撤销与有效期 | `NOT PROVEN FOR THIS PROPOSAL` | 通用模型存在不等于已配置此治理流程 |
| 四角色六组职责分离 | `PENDING / NOT TESTABLE` | 无真实四身份 |
| Permission Organization Fact Package | `MISSING` | 源码结构不能代替正式权威事实包 |
| `GAP-01`～`04` | `OPEN / MISSING` | **本轮均不可关闭** |
| Source Qualification Review Pre-check | `NOT READY` | 其它 Gap 与审计缺口亦未满足 |

若未来授权开发治理授权层，必须另行确定数据权威、持久化或工件形态、审批与撤销语义、权限动作、不可变原件链、冲突算法、非回归范围及恢复路径；该实施授权不由本评估报告授予。

## 九、保护、非回归与最终状态

本轮只新增一份报告；未修改组织/员工/用户/角色/权限、数据库、Schema、Migration、代码或历史治理报告；未创建责任主体、Source、Baseline 或 Generation/Validation/Recovery 环境。未运行应用登录、数据查询或 Migration。因没有实现变更，模块测试与 UI 真实路径不适用；当前运行数据和用户人工验收未被本报告验证。734F 与 ABA 继续作为历史证据，Phase B 技术准入继续阻断。

| Compliance Item | 本轮结论 | 依据 |
|---|---|---|
| 目标与范围 | `COMPLETE` | 七类模型、四角色、授权层和 Verification 绑定已评估 |
| 源码事实与运行事实分离 | `PASS` | 仅宣称当前工作树结构可观察；未声称 Migration 已应用或人员已任命 |
| 既有结果保护 | `PASS` | 无实现、历史报告或数据库变更 |
| 用户可见路径 / UI 数据可见性 | `N/A` | 非 UI 任务 |
| 自动测试 / 运行非回归 | `N/A` | 无代码或数据修改 |
| 人工验收、四角色任命 | `PENDING / MISSING` | 未收到独立签署原件 |
| Phase B 准入 | `BLOCKED` | HC-01～04 与其它前置均未获接受 |

```text
Documentation Changed = YES (this report only)
Code Changed = NO
Database Changed = NO
Migration Created/Executed = NO
Organization/Employee/User/Role/Permission Data Changed = NO
Responsibility Subject Created = NO
Source/Baseline Created = NO
Generation/Validation/Recovery Environment Created = NO
Unauthorized Business Writes = 0
GAP-01~GAP-04 CLOSED = NO
SOURCE QUALIFICATION REVIEW PRE-CHECK = NOT READY
PHASE B TECHNICAL RE-ADMISSION = BLOCKED
GOVERNANCE RESPONSIBILITY INTEGRATION ASSESSMENT COMPLETE
```
