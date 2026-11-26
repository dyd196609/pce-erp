# FINAL / CONSOLIDATED

# 《Phase B New Controlled Protection Baseline Governance Responsibility Authorization Layer Design评估FINAL / CONSOLIDATED报告》

日期：2026-09-29  
阶段：Governance Responsibility Authorization Layer Design Assessment  
类型：逻辑模型与方案比较；非开发、非批准、非授权记录生成  
Source Proposal：`NCPSB-SP-A-20260929-001`  
Logical Source：`PCE-NCPB-A-REBUILD-SOURCE-P01`  
Review Level：B（身份、权限、审批和证据链跨域设计）；Full Content Review Required：NO  
最终 Gate：`GOVERNANCE RESPONSIBILITY AUTHORIZATION DESIGN ASSESSMENT COMPLETE`

## 一、范围、前态与证据控制

本轮承接 `D:\Dev-PCE\Source\docs\governance\Phase B New Controlled Protection Baseline Governance Responsibility Authorization Integration评估FINAL CONSOLIDATED报告 20260929.md`。该报告的结论是：现有组织、员工、账户、角色、权限和通用审批结构可作为基础，但没有本 Proposal 的专属四角色任命证据；`HC-01`～`04` 与 `GAP-01`～`04` 仍为 `MISSING/OPEN`。本轮只比较授权层逻辑设计，不确定物理表、不选择人员、不签发授权。

| 直接输入 | 作用 | 只可支持的判断 |
|---|---|---|
| 上述 Integration 评估报告 | 前态与已识别模型差距 | 四角色任命未证实；系统权限不等于治理授权 |
| `docs/governance/Phase B New Controlled Protection Baseline Governance Input Human Coordination Readiness FINAL CONSOLIDATED报告 20260929.md` | HC-01～04 人工签署要求 | 原件、任命权、双身份绑定和职责冲突仍待人工 |
| `backend/system/models.py`、`backend/pfm/models.py`、`backend/workflow_runtime/models.py`、`backend/system/authorization.py` | 当前工作树源码模型与服务 | 字段/关系可观察；不等于运行库已应用或存在人员行值 |
| 当前 Protection/Acceptance/开发数据库 | 本轮未打开 | 不作 Schema、Migration、人员、授权或审批运行事实判断 |

`backend/system/models.py` 与 `backend/system/authorization.py` 在前态评估时已有未提交变更。设计仅引用当前源码结构，不将工作树视为冻结 Commit 或新 Baseline 来源。734F 与 ABA 保持历史证据身份，独立治理输入仍为 0，Phase B 技术准入继续阻断。

```text
EFFECTIVE INSTRUCTION SET
ACTIVE = 本轮 Layer Design Assessment：A/B/C 比较、最小逻辑模型、Verification 绑定
FROZEN = 历史 734F/ABA 边界；HC-01~04 未获真实任命；Gap 不自动关闭
NOT AUTHORIZED = models/Migration/数据库/权限/组织/员工变更；任命、审批、授权号或 Source/Baseline 创建

INSTRUCTION CONTROL SHEET
Original Goal = 评估治理责任授权层及既有模型复用
Current Goal = 形成方案比较、字段契约、冲突和 Verification 链设计
IN SCOPE = 现有源码/报告只读复核；新增本评估报告
OUT OF SCOPE = 物理模型、Migration、实现、任命、签署、审批、权限/数据写入
Database Boundary = 不连接或修改数据库
Non-Regression Baseline = 组织权限基础与历史报告不变；Phase B 阻断
User Acceptance Path = N/A（非 UI 任务）
Stop Condition = 归档回读后停止；详细开发设计须另获授权
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

本轮只新增文档；Registry 无当前 `FROZEN_VERIFIED` 项并不解除对既有组织/权限功能的 Preserve-and-Extend 保护。用户真实运行结果仍高于源码和历史报告。

## 二、现有模型复用评估

| 基础 | 当前源码可观察能力 | 历史、版本与快照限制 | 治理授权中的职责 |
|---|---|---|---|
| Organization Foundation：Company / Department / OrganizationUnit | Company 有身份编码和状态；Department/OrganizationUnit 有公司、层级、有效期（`backend/system/models.py:59-159`） | Company 本身无有效期、版本或 Owner 授权；Department/OrganizationUnit 有日期但无统一版本与不可变范围快照 | 提供企业/组织引用；授权证据须固定签发时范围快照及读取时点 |
| Identity Foundation：Employee / User | Employee 有主键/工号、状态、正式部门/岗位及可空一对一 User；User 有主键、账号、公司 ID、启用状态（`backend/pfm/models.py:6-43`；`backend/system/models.py:33-56`） | 员工—账户及任职关系允许缺失或变化；没有 Proposal 任命历史 | 提供自然人和账户双身份，核验有效状态，不生成任命 |
| Position Responsibility：Position / Responsibility / PositionWorkflowResponsibility | 岗位、职责、流程节点与 OWNER/REVIEWER/APPROVER/EXECUTOR 类型可表达候选能力（`backend/system/models.py:508-710`） | 岗位责任没有本 Proposal、具体 User、授权号与签发链；有效期主要是日期 | 仅支持候选资格/职责语义核验；岗位职责 ≠ Proposal 治理任命 |
| Security Foundation：Role / Permission / UserRoleScopeAssignment | RolePermission、用户角色组织/数据范围及服务端 AuthorizationService 可检查业务动作（`backend/system/models.py:579-620,742-798`；`backend/system/authorization.py:39-151`） | 系统授权无本 Proposal 的 Authorization ID/任命范围/审批历史；兼容回退和超级用户分支不能作为治理签署证明 | 系统操作能力门禁；系统权限 ≠ 治理授权 |
| Approval Foundation：WorkflowInstance / ApprovalTask / ApprovalDecision | 有流程实例、任务、决策 actor、action/hash、时间等通用审批事实（`backend/workflow_runtime/models.py:109-185`） | 未见为本 Proposal 配置的正式 document type、流程定义、任命审批或撤销链；WorkflowInstance 的 document_id 为整数，外部工件关联需设计 | 未来可复用审批过程；通用审批记录 ≠ 本 Proposal 治理批准 |

`SegregationOfDutiesAuthority` 已有同用户和角色分离配置（`backend/workflow_runtime/models.py:56-64`），`OrganizationOperatingAuditRecord` 可记录特定组织运作修改（`backend/system/models.py:715-739`）。二者都不能自动证明四角色六组冲突已完成或授权已签发。上述结论为源码结构观察；本轮不验证运行数据库的 Schema、Migration 应用、对象行值或审批实例。

## 三、治理授权层必要性判断

结论：**需要一个 Proposal-bound Governance Responsibility Authorization 逻辑层；无需重复建设 Company、Employee、User、Role 或 Permission 主数据。** 现有各层分别回答“组织是谁”“人员/账户是谁”“可执行何种系统动作”“通用审批发生了什么”，尚无单一正式事实回答“有权主体在何时、对哪一 Proposal/Logical Source、以何种范围任命哪位自然人与账户承担哪项治理责任，并可撤销和追溯”。

“需要逻辑层”不等于“现在需要新表”。详细设计须决定由受控持久化对象、签发工件登记、Workflow 扩展或组合实现，并证明同一事实不形成平行权威。任何方案都须保留独立原件、双身份绑定、四角色分离、撤销历史与只读核验入口。

## 四、方案 A/B/C 比较

| 方案 | 可复用优势 | 不足与风险 | 适用性评价 |
|---|---|---|---|
| A：完全复用现有 Workflow/ApprovalTask/ApprovalDecision | 现有流程、任务、决策 actor/hash/时间及通用审计模式可复用 | 决策记录是一次审批事件，难独立表达长期任命身份、Authorization ID、精确 Proposal 范围、有效期和撤销历史；本 Proposal 流程未配置 | **单独使用不足**；适合作为治理授权的审批过程引擎，另需持续授权事实和原件链 |
| B：独立治理授权证据层 | 能明确四角色、Proposal/Logical 双绑定、人员/账户、范围、时效、版本、状态和授权号；便于查当前资格及历史 | 若复制组织/权限或自行审批，易产生第二套权威；未来持久化、审批和撤销实施需单独授权 | **推荐为核心逻辑事实层**，但必须引用现有基础与审批原件，不得独立取代它们 |
| C：原始授权文档 + Evidence Registry + Verification | 保留签发原件、Hash、渠道与可审计受理过程；本轮无需数据库新对象 | 单独作为运行查询与撤销/有效时点决策源较弱；文件名或登记行不能证明签署权 | **作为不可省略的原件证据层**；不能单独替代授权状态与系统权限 |

推荐组合为 **B（授权语义）+ C（原件与验证）+ A（经另行批准后复用审批过程）**。此为架构方向，不是现行实现决定；如果有权主体选用纯文档承载 B 的事实，也必须满足相同字段、版本、时效、撤销和查询可验证性。不得把已有 ApprovalDecision、Role 或 PositionWorkflowResponsibility 直接升格为 HC 任命。

## 五、推荐最小逻辑模型与字段需求

逻辑对象名：`Proposal-bound Governance Responsibility Authorization`。以下仅是设计字段，不是数据库列、已签发记录或新编号。

| 字段 | 设计含义与核验约束 | 当前基础关联 |
|---|---|---|
| Authorization ID | 由真实签发主体提供的唯一治理授权编号；不得由本轮生成 | 无等价正式字段 |
| Proposal ID | 严格绑定 `NCPSB-SP-A-20260929-001` | Proposal 登记原件 |
| Logical Source ID | 严格绑定 `PCE-NCPB-A-REBUILD-SOURCE-P01` | 逻辑来源提案 |
| Governance Role | 仅 Source Owner / Source Preparer / Technical Reviewer / Approver 之一 | 不等同系统 Role 或岗位 |
| Employee ID | 唯一自然人引用及当时状态快照 | `pfm.Employee.pk`，辅以工号 |
| User ID | 被授权操作的账户引用，与 Employee 关系一致 | `system.User.pk`；核对 Employee.user |
| Organization | 公司、组织/部门范围及签发时层级快照 | Company/OrganizationUnit/Department ID 与编码 |
| Authorization Scope | Source、企业、组织、数据、输入/审核/批准动作及排除边界；可引用批准的 Data Boundary | 不等同 UserRoleScopeAssignment.scope_code |
| Issuer | 签发主体身份、签发权依据与原件关联 | 需独立治理输入 |
| Approver | 批准主体 User/Employee 身份、权限来源、决策引用 | 可关联经批准的 Workflow 决策，但不得推断 |
| Effective Time / Expiry Time | 带时区生效与失效时点；区间必须有效，重叠需审查 | 现有组织/岗位日期仅供核对 |
| Status | 授权生命周期，如待核、有效、撤销、过期；与证据受理状态分离 | 不复用业务 Role.active 代替 |
| Version | 不可覆盖的版本；变更应新版本并关联前版 | 不直接借用 RoleScope 的 version |
| Original Evidence Hash | 原始签发工件 SHA256；保留原件身份和验证方法 | C 层原件登记 |

最低补充字段：签发时间及签发时区、接收时间、原件位置与版本、审批决策/签署引用、授权依据、撤销/更正引用、读取环境与组织权限事实快照版本、上一版本引用。所有值都要来自真实原件或权威只读查询，不由 Codex 预填。授权生命周期（如有效/撤销）与输入受理状态（`RECEIVED/PENDING/ACCEPTED/REJECTED`）必须分开；“原件获接受”也不自动使授权有效，仍要满足生效时间、撤销状态和职责分离。

```text
Organization / Identity / Position Responsibility / Security Foundation
                 ↓ reference + as-of snapshot
Proposal-bound Governance Responsibility Authorization (logical B)
                 ↔ Original Authorization Document (C)
                 ↔ approved Workflow Decision, if independently configured (A)
                 ↓ read-only verification
Governance Input Acceptance Verification → Conflict Check → Gap Review
```

## 六、六组职责冲突设计

比较集合固定为 Owner↔Preparer、Owner↔Reviewer、Owner↔Approver、Preparer↔Reviewer、Preparer↔Approver、Reviewer↔Approver。每组读取同一 Proposal/Logical Source 和相交的有效时间范围；分别输出 User ID、Employee ID/工号、系统 Role/治理 Role、Organization/委托关系、Effective Time 比较及证据版本。

同一自然人或共享账户执行需分离的角色必须阻断；不同 User ID 不能单独证明不同自然人。Role 的职责冲突语义、跨组织是否构成不独立、临时代理与相邻而不重叠的有效期，由有权治理主体在详细设计中制定正式规则；仅“同组织”不自动判冲突，也不能自动判无冲突。缺任何四角色身份、组织引用、时间或原件真实性时，六组结论为 `PENDING/NOT TESTABLE`，绝不输出无冲突。冲突计算结果须保留输入版本、时间、规则版本及 Reviewer/Approver 确认，身份或授权变化后重算。

## 七、Permission Organization Fact Package 与 Verification 绑定

Permission Organization Fact Package 回答“公司、组织、员工、账户、岗位、角色、权限及范围事实是什么”；治理责任授权回答“谁被有权主体为本 Proposal 授予哪项治理职责”。二者需要同一环境、身份、组织、时点和版本核对，**互不替代**。权限包可支持身份、组织和系统操作能力核验；治理任命原件及审批记录才支持签发权限与责任范围核验。

| Verification 步骤 | 输入与只读检查 | 状态边界 |
|---|---|---|
| 1. 原件受理 | 实际到达后记录 Input ID、来源渠道、签发主体、原件 Hash/版本、签发和接收时间；绑定双 ID | 文件到达仅 `RECEIVED`；模板、设计报告、循环引用不得提升 |
| 2. 身份与授权 | 将 Employee/User、Organization、Role/Permission、Scope 与原件逐项核对；检查 Issuer/Approver 权限和签发时点 | 信息不全为 `PENDING`，禁用来源/篡改/无效授权为 `REJECTED`，满足条件才 `ACCEPTED` |
| 3. 生命周期 | 核验生效/失效、撤销、更正及版本链，保持原件不可覆盖 | 接受原件 ≠ 当前有效授权 |
| 4. 六组冲突 | 四份任命均接受后比较身份、自然人、Role、Organization 和重叠时段 | 任一不可测或禁止冲突时阻断 |
| 5. Gap 状态复核 | 独立检查 HC-01～04 各自最低受理条件，关联 Verification ID、失败原因和原始证据 | 收到授权记录 ≠ 自动关闭 Gap；各 Gap 单独裁决 |

未来系统权限校验也不能跳过独立治理授权核验。`AuthorizationService` 的超级用户分支及兼容性 `UserOrganizationRoleAuthority` 回退均不构成任命原件或治理签发权证据。任何撤销、员工离职/调岗、账户停用、权限变更、原件 Hash 不一致，都应使受影响资格重新验证，而非保留过期 `ACCEPTED` 结论。

## 八、实施前置条件与开发设计阶段判断

1. 治理主体必须确认 B 的单一事实权威、A 的审批复用范围、C 的原件保管与法律/组织签发链；选择物理形态及存储位置须另行授权。
2. 固定 Governance Role 语义、授权范围语法、组织/身份快照时点、状态与版本/撤销规则、六组冲突政策、审批人权限来源及异常处理。
3. 若复用 Workflow，先审批专用 document type、definition、任务与 Decision 关联方式；`WorkflowInstance.document_id` 为整数，外部原件需有受控稳定关联，不能以文件名或任意 ID 拼接。
4. 决定权限动作与治理授权的双门禁、最小可见性、审计保留、隐私保护和失败关闭规则；不得改变现有组织权限权威或静默替换现有页面/API。
5. 确认目标环境、已批准 Commit、Schema/Migration 差异、测试/恢复设计与既有源码未提交变化的处置；本轮不执行任何 Migration 或环境创建。
6. 真实 HC-01～04 任命仍须由独立治理主体签发，再经过 Governance Input Acceptance Verification；设计完成不能补足真实批准证据。

**判断：可申请下一阶段“详细开发设计”授权，但未自动进入该阶段，更未获得代码、数据库、Migration 或生产实施授权。** 正式申请至少应明确上述决策主体、设计范围、输出契约和停止点。HC-01～04 本轮仍 `MISSING`；Source Qualification Review Pre-check 仍 `NOT READY`。

## 九、保护、合规与最终状态

本轮只新增一份设计评估报告。未修改 models、Migration、数据库、权限、组织或员工数据；未指定人员、生成 Authorization ID、形成批准记录、执行审批，未创建 Source、Baseline 或 Generation/Validation/Recovery 环境。非 UI 任务，用户可见路径与 UI 数据可见性为 `N/A`；无实现修改，运行回归为 `N/A`。734F 与 ABA 历史证据、全部先前报告和 Phase B 阻断状态保持。

| Compliance Item | 结果 | 证据/限制 |
|---|---|---|
| 单一目标与范围 | `COMPLETE` | A/B/C、最小模型、冲突及 Verification 关系已评估 |
| 源码事实与运行事实分离 | `PASS` | 只读取源码和前态报告；未连接数据库 |
| 非回归与生产边界 | `PASS` | 无实现或业务写入；现有功能未改动 |
| 人工任命/用户验收 | `MISSING / N/A` | 未收到任命原件；本轮不涉及 UI 人工验收 |
| Gap-01～04 与 Pre-check | `OPEN / NOT READY` | 设计不能关闭证据缺口 |

```text
Documentation Changed = YES (this report only)
Code Changed = NO
Database Changed = NO
Migration Created/Executed = NO
Permission/Organization/Employee Data Changed = NO
Responsibility Subject Appointed = NO
Authorization ID Issued = NO
Approval Executed = NO
Source/Baseline Created = NO
Generation/Validation/Recovery Environment Created = NO
Unauthorized Business Writes = 0
GAP-01~GAP-04 CLOSED = NO
SOURCE QUALIFICATION REVIEW PRE-CHECK = NOT READY
PHASE B TECHNICAL RE-ADMISSION = BLOCKED
GOVERNANCE RESPONSIBILITY AUTHORIZATION DESIGN ASSESSMENT COMPLETE
```
