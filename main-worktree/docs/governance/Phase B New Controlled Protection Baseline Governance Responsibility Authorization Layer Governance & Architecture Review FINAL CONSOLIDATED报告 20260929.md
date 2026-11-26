# FINAL / CONSOLIDATED

# 《Phase B New Controlled Protection Baseline Governance Responsibility Authorization Layer Governance & Architecture Review FINAL / CONSOLIDATED报告》

日期：2026-09-29  
评审对象：Proposal-bound Governance Responsibility Authorization Layer（GRA）  
Source Proposal：`NCPSB-SP-A-20260929-001`  
Logical Source：`PCE-NCPB-A-REBUILD-SOURCE-P01`  
评审性质：技术与治理架构评估，不是独立治理主体的批准或实施放行  
Review Level：B；Full Content Review Required：NO  
最终 Gate：`GOVERNANCE RESPONSIBILITY AUTHORIZATION GOVERNANCE & ARCHITECTURE REVIEW COMPLETE`

## 一、评审范围、依据与保护预检

本轮依据以下三份已形成的文档评审方向与阻断条件，未读取数据库或将报告当作原始批准输入：

1. `Phase B New Controlled Protection Baseline Governance Responsibility Authorization Layer Design评估FINAL CONSOLIDATED报告 20260929.md`：B+C+A 逻辑方向及现有基础复用。
2. `Phase B New Controlled Protection Baseline Governance Responsibility Authorization Layer Detailed Design FINAL CONSOLIDATED报告 20260929.md`：逻辑对象、原件、页面/API、权限、Workflow 与非回归契约。
3. `Phase B New Controlled Protection Baseline Governance Responsibility Authorization Layer Implementation Readiness评估FINAL CONSOLIDATED报告 20260929.md`：治理、架构、测试与实施授权缺口。

三份报告均是设计/评估证据，不是外部签发件。现有 `HC-01`～`HC-04` 和 `GAP-01`～`GAP-04` 仍未关闭，独立治理输入接受数为 0；Source Qualification Review Pre-check 为 `NOT READY`。旧 734F 和当前 ABA 文件只保留历史证据身份，不是本 Proposal 的输入数据库或新来源。当前工作树不得自动视为冻结 Commit。所有模型、API、页面、Migration、权限及运行环境保持原状。

```text
EFFECTIVE INSTRUCTION SET
ACTIVE = GRA 治理与架构只读评审；仅新增本报告
FROZEN = 734F/ABA 历史边界；既有组织、身份、权限与 Workflow 权威；未关闭 HC/GAP
NOT AUTHORIZED = 任命、签发、审批、GRA/Registry 数据、代码/数据库/权限修改、Migration、Source/Baseline 创建

INSTRUCTION CONTROL SHEET
Original Goal = 判断 GRA 方向、架构及实施授权申请条件
Current Goal = 输出定位、事实权威、B+C+A、模型/Workflow/安全和未决事项评审
IN SCOPE = 三份报告及既有治理规范只读评估；本报告
OUT OF SCOPE = 独立治理批准、物理方案选型、实施和技术准入
Database Boundary = 不连接数据库
Non-Regression Baseline = 现有组织权限、登录、Workflow、菜单/Route/API 身份不变
User Acceptance Path = N/A（没有 UI 交付）
Stop Condition = 报告回读后停止；缺正式授权不进入实施
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

本轮仅新增报告，不命中 Frozen Core 或 Frozen Shared Dependency 的实现修改；未来任何拟改文件须重新做完成模块保护预检。用户真实运行结果仍高于源码、Registry、Meta 与报告。

## 二、GRA 核心定位结论

**评审结论：`ACCEPT`（仅接受设计定位，不构成治理批准）。** GRA 应是绑定 `Proposal ID + Logical Source ID` 的治理责任授权事实层，回答谁、由何权威、在何时、针对何范围承担 Owner/Preparer/Reviewer/Approver 中哪种职责。它只引用既有组织、自然人、账户、岗位、角色及系统权限事实；允许保存签发时经过核验的最小范围快照以解释历史，但不得复制员工、重建角色、重建权限或让快照成为第二套当前主数据。

限制：逻辑层必要性已论证，具体权威主体、签发与撤销权、编号规则、存储形态及生效政策尚未由有权治理主体批准。设计结论不能自动生成人员任命或有效授权。

## 三、事实权威边界

| 事实类型 | 应保持的权威 | GRA 的读取/保存边界 | 评审 |
|---|---|---|---|
| Organization | Company、Department、OrganizationUnit | 引用 ID、公司/层级和经批准的 as-of 范围快照；不得自行维护平行公司/部门 | `ACCEPT` 原则；历史版本规则待定 |
| Identity | Employee、User | 核对自然人、账户、一对一关系、状态与时间；缺关联即阻断，不补造 | `ACCEPT` 原则 |
| Security | Role、Permission、UserRoleScopeAssignment 及服务端校验 | 仅判断系统动作权限与组织数据范围；系统 Role 不自动转换 Governance Role | `ACCEPT` 原则 |
| Governance Authorization | Proposal-bound GRA + 原件 Evidence Registry | GRA 表达经独立核验的任命语义和状态；Registry 保存原件身份、来源与核验链 | `REVISE`：唯一授权事实与原件主从关系须正式定稿 |
| Approval Process | 既有 Workflow 正式定义与决策 | 只引用专属流程、明确版本/范围/原件绑定的 Decision；通用审批不能代替授权 | `REVISE`：专属流程与关联键未批准 |

需要明确单一事实来源：组织/身份/系统权限仍来自原模型；GRA 仅新增 Proposal 专属授权事实；原件不可覆盖；Workflow 只提供审批事件，不单独成为持续任命权威。当前权限服务中的超级用户与兼容回退只说明系统权限路径，不能证明治理签发资格。

## 四、B+C+A 架构组合评审

| 层 | 唯一职责 | 不得承担的职责 | 结论 |
|---|---|---|---|
| B：GRA 授权层 | 谁被授权、哪项治理角色、双 ID、范围、时段、版本与撤销状态 | 复制 Company/Employee/Role/Permission；自行创造签发权 | `ACCEPT` 逻辑职责 |
| C：Evidence Registry | 原件字节身份、Hash、来源、签署/接收时间、修订/撤销原件与 Verification | 仅凭文件名或 Hash 宣告签发权/批准有效 | `ACCEPT` 证据职责 |
| A：Workflow | 审批过程、任务、决策、时间及决策 Hash | 将普通审批或任意历史 Decision 视为本 Proposal 的持续授权 | `REVISE`：复用方式待专属流程审批 |

组合方向为**有条件可接受**：B 与 C 一对多版本/原件关系、A 的 Decision 与 GRA 精确版本/范围/原件 Hash 的关联、审批失败及撤销事件的单向因果关系必须在架构批准时固定。不得构成“Workflow 先依赖有效 GRA、GRA 又必须由同一有效 GRA 审批”的循环；初始任命须来自独立治理签发权，系统只核验和承载。三层关系清晰到足以供正式架构决策，但尚不足以称为获批实现架构。

## 五、数据模型架构评审

未来可能需要 GRA、Evidence Registry、Conflict Check Record 与 Version/Revoke Event。逻辑必要性分别是持续授权语义、不可覆盖原件、可复算六组冲突、历史/撤销追溯。现有 Workflow 可以承担审批过程，现有组织/权限模型仍为原事实权威。是否通过独立持久化模型、扩展已有对象、外部证据登记或组合承载，均需另行架构批准；**本轮不确定表、字段实现或 Migration**。

物理方案评审必须证明：双 ID 与 `Authorization ID + Version` 唯一性；Employee/User 和组织引用的 as-of 一致性；原件版本不可覆盖；生效、过期、撤销、取代的不可逆历史；Conflict Check 输入快照/规则版本可复算；证据与授权生命周期分轴；失败关闭与恢复比对。当前 Protection/Acceptance 不得充当设计试验库。批准 Commit、Schema/Migration 组合、目标环境与回退证据未冻结，故数据模型实施仍阻断。

## 六、Workflow 架构评审

复用 `WorkflowInstance`、`ApprovalTask`、`ApprovalDecision` 的方向可接受，但必须另行确定专用 Document Type、ProcessDefinition、节点/审批链、代理与回避、双人及六组职责分离政策。审批 Decision 必须绑定本 Proposal、Logical Source、GRA 版本、原件 Hash、范围及有效时点。既有 `WorkflowInstance.document_id` 为整数；若 GRA 原件或逻辑对象使用外部标识，须先审批稳定映射，禁止文件名或任意数字拼接。

Workflow 审批状态、证据受理状态与 GRA 生命周期是三条独立状态轴。收到原件、核验通过、普通 Workflow 决策或页面展示均不能单独使授权有效。架构结论：`REVISE` 专属绑定与政策后再申请实施；未配置/未批准时 Fail-Closed。

## 七、安全双门禁与绕过控制

未来敏感动作的服务端判定须同时满足：系统动作 Permission 与对象/组织范围匹配、针对本 Proposal 的有效治理授权或经过独立核验的签发权、生命周期/原件/审批/职责分离条件。任何一项缺失即拒绝并留审计；客户端只能展示服务端裁决，不得自行重算资格。

| 绕过路径 | 架构要求 | 当前批准状态 |
|---|---|---|
| Superuser/Admin | 系统特权不等于治理签发权；治理 Validator 不应有隐式放行分支 | `PENDING` 正式安全策略 |
| 前端隐藏/禁用按钮 | 不替代服务端动作权限与治理事实重验；直接 API 调用须同样拒绝 | `PENDING` API/测试契约 |
| Workflow 决策 | 只接受专属、同范围同版本且签发权有效的决策 | `PENDING` 专属流程规则 |
| 旧缓存/兼容权限回退 | 当前事实、原件与时点读取失败即阻断，不降级为有权 | `PENDING` 技术设计审查 |

评审结论：双门禁方向 `ACCEPT`；Action Code、Validator、审计、异常引导与初始签发权的具体政策 `REVISE`，须安全/治理主体审批后才能实施。

## 八、实施边界与非回归保护

未来实施申请必须冻结 Approved Commit、完整 Schema/Migration 组合、隔离目标环境和回退/恢复方案；明确拟改模型、API、页面、权限、Workflow、审计与测试范围。当前有大量未提交工作树变化，不能直接用作冻结输入；已有 pde、pfm、planning、procurement 差异不能靠 GRA Migration 顺带修复。

必须 Preserve-and-Extend：现有组织/员工/账户/角色权限主数据和授权服务、登录/Session、Workflow 已有 Document Type 与历史 Decision、`/organization` 页面现有 Tab、菜单、Route、API 与数据权威、已开发模块的 Golden Identity 均不静默替换。若拟实施触及 Frozen Core 或 Shared Dependency，须在实施任务重新预检并取得明确 Unfreeze 授权。非回归方案须包括身份关联、权限负例、六组冲突、并发版本、撤销/过期、Workflow 错绑、原件 Hash 不符、读失败、现有页面/API 可见性及恢复验证；本轮不执行这些测试。

## 九、必须由人工治理主体决定的事项

| 决策项 | 尚需真实批准的内容 | 本轮状态 |
|---|---|---|
| GRA 方向与 B+C+A 组合 | 是否采用及三层单一事实权威、外部原件与 Workflow 的法定/组织效力 | `PENDING` |
| 签发和撤销权 | Issuer、Approver、Revoker 的任命权依据、代理与回避 | `MISSING` |
| 四角色任命 | HC-01～04 的真实身份、组织、授权范围及有效期 | `MISSING` |
| Authorization ID | 编号权威、唯一性、签发/作废/更正规则 | `PENDING` |
| 数据边界 | 企业、组织、数据和排除范围及截止时间/时区的批准方式 | `MISSING` |
| Workflow | 专属类型/流程、节点、双人分离、六组冲突与代理规则 | `PENDING` |
| 原件保管 | 独立来源、原件不可覆盖、Hash 复算、访问/留存/恢复与撤销件链 | `PENDING` |

本报告仅把上述问题交给有权主体，**不代替其投票、签署或选择人员**。架构主体还需审定物理模型、唯一权威、对象关联和安全失败策略；开发团队不能把技术评审结论当作人工批准。

## 十、实施授权申请条件与评审裁决

目前可提交的是治理与架构**决策请求**，不是已具备材料的实施放行申请。正式申请实施授权前至少应有：独立治理主体对方向/组合与签发链的批准、HC-01～04 真实任命及核验路径、架构/安全对单一权威和专属 Workflow/双门禁的批准、冻结的 Commit/Schema/Migration/目标环境/回退方案、精确拟改范围及完成模块预检、可执行测试与非回归计划。`GAP-01`～`GAP-04` 仍须按原始证据逐项接受和关闭；功能开发不能反向证明其已关闭。

**本轮评审已完成，但正式治理/架构批准仍待有权主体作出；现阶段不具备进入实施授权申请的完整条件，也不进入开发。** 即使未来实施授权获批，也不自动通过 Source Qualification Review 或 Phase B 技术准入。

## 十一、未执行事项及固定状态

本轮只新增本评审报告。未创建 GRA/Registry 数据、Authorization ID 或责任任命；未执行审批；未修改数据库、models、Migration、API、页面、权限、组织、员工、配置或历史证据；未创建 Source、Baseline 或运行环境。无 UI 交付，`DELIVERED USER STATE CONTRACT = N/A`；未执行实施测试。报告回读仅确认文档本身，不证明外部治理批准。

```text
DOCUMENTATION CHANGED = THIS REPORT ONLY
CODE / DATABASE / SCHEMA / MIGRATION / PERMISSION / ORGANIZATION CHANGED = NO
INDEPENDENT GOVERNANCE APPROVAL = PENDING
HC-01~HC-04 = MISSING
GAP-01~GAP-04 = OPEN
SOURCE QUALIFICATION REVIEW PRE-CHECK = NOT READY
IMPLEMENTATION AUTHORIZATION = NOT GRANTED
PHASE B TECHNICAL RE-ADMISSION = BLOCKED
GOVERNANCE RESPONSIBILITY AUTHORIZATION GOVERNANCE & ARCHITECTURE REVIEW COMPLETE
```
