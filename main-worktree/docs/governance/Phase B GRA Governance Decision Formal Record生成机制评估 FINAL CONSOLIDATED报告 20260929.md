# FINAL / CONSOLIDATED

# 《Phase B GRA Governance Decision Formal Record生成机制评估 FINAL / CONSOLIDATED报告》

日期：2026-09-29  
Proposal：`NCPSB-SP-A-20260929-001`  
Logical Source：`PCE-NCPB-A-REBUILD-SOURCE-P01`  
性质：只读机制评估；不产生决策、授权或软件实现  
Review Level：B；Full Content Review Required：NO  
最终 Gate：`GRA FORMAL DECISION GENERATION DESIGN ASSESSMENT COMPLETE`

## 一、范围、证据与保护边界

本轮承接 GRA 逻辑设计、D-01～D-07 候选方向和[未签署 Formal Decision 模板](<D:/Dev-PCE/Source/docs/governance/Phase B GRA Governance Decision Formal Record 未签署模板 20260929.md>)，评估正式 Decision 应如何由有权治理主体产生。现状仍为：候选方向有文字，正式 Decision 原件、Decision Maker 身份/事项权限及签署链缺失；Verification Register 正式条目为 0。模板、报告及聊天文字不能成为签署原件。本轮仅检查当前源码结构和历史报告，不连接数据库，不判断运行库中是否有相应记录。

```text
EFFECTIVE INSTRUCTION SET
ACTIVE = A/B/C 产生机制比较、字段分类、现有基础复用、首场景适配及设计入口评估
FROZEN = 734F/ABA 历史证据；既有组织/身份/权限/Workflow 单一事实权威；未关闭 DGI/HC/GAP
NOT AUTHORIZED = 正式 Decision、人员指定、最终选项、Authorization ID、GRA/Registry、组织/权限/Workflow/数据库/代码/Migration/API/页面变更

INSTRUCTION CONTROL SHEET
Original Goal = 评估 GRA Governance Decision Formal Record 的产生机制
Current Goal = 区分系统只读事实辅助与人工决策/签署权，判断工程版本发布首场景和开发设计入口
IN SCOPE = 当前模型源码及既有报告只读检查；本报告
OUT OF SCOPE = 原件签署、治理批准、物理模型/API/UI/Migration 选型或开发
Database Boundary = 不连接数据库
Non-Regression Baseline = Company/Employee/User/Role/Permission/Workflow 与已开发模块不被替换
User Acceptance Path = N/A（无 UI 交付）
Stop Condition = 评估完成即停止；无正式治理原件不启动实施
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

本轮仅新增文档，不命中 Frozen Core/Shared Dependency 实现变更；未来开发须重新按拟改文件预检。用户真实运行结果高于源码和报告。

## 二、Formal Decision 三种产生方式比较

| 方案 | 过程与优点 | 不足/风险 | 本阶段适用性 |
|---|---|---|---|
| A：完全人工产生 | 有权治理主体独立填写、签署原件，交独立接收方 Verification；不依赖新软件，签署意图和责任直接可追溯 | 重复录入、字段遗漏、身份/双 ID/版本错填；需严格受理清单和原件保管 | **当前唯一可实际申请提交的路径**，但须由真实主体提供签署原件；模板本身不产生 Decision |
| B：系统辅助草稿 | 从现有基础模型只读检索身份、组织、岗位、系统角色/权限等候选事实，附事实来源/读取时点；减少录入差错 | 可能把过期/空关联、超级用户或岗位误写成治理权限；系统无法选择裁决、签发权或签署；当前无获批的专属草稿功能 | **仅作为未来可评审设计方向**；需治理规则、架构、权限、代码和测试的独立授权后才可实施 |
| C：复用现有责任/授权/审批能力 | Position/Responsibility/PositionWorkflowResponsibility、UserRoleScopeAssignment 和 Workflow 结构可提供职责候选、系统权限及正式审批过程 | 都未直接绑定本 Proposal 的正式 Decision Maker/事项授权；通用 ApprovalDecision 不是 GRA 治理裁决；直接复用为权威会形成第二套或错误授权 | **部分复用作事实与过程**，不可单独代替独立签署原件与 Proposal-bound 决策事实 |

建议的顺序为：现在使用 A 提交真实原件并独立核验；是否引入 B 的只读草稿辅助或 C 的专属流程复用，由治理与架构主体在正式 Decision 后另行批准。此为机制评估建议，不是对 D-01～D-07 的最终选择，也不自动开启开发。

## 三、系统辅助与人工责任的精确边界

系统在获批实现后**可以**只读显示和校验：员工工号/状态、User ID/启用状态及 Employee 关联、公司/部门/组织编码与有效期、岗位和职责映射、系统 Role/Permission/数据范围、相关 Workflow 定义/已存在 Decision 的来源；必须同时记录事实源、版本、读取时间、适用组织和失败状态。Employee.user、department_ref、position_ref 均可为空，缺失时不可假装有事实。`system.User.company_id` 是数值关联字段；不能仅凭数值或姓名自动断言企业治理权限。事实读取失败或时点不一致应 Fail-Closed，不从页面缓存、旧快照或默认值补齐。

系统**不得**自动：选择 `ACCEPT/MODIFY/REJECT`、填写 D-04/D-06 的范围和理由、指定 Decision Maker、推定 Authorization Basis、签署、生成正式 Decision 或 Governance Authorization、宣布批准。人工治理主体作决策、承担责任并签署；独立接收/Reviewer 再验证原件、身份、事项权限、双 ID、Hash、时间及范围。正式 Decision ID 只能按经治理批准的编号/记录机制获得，不能把 D-01 项号或系统草稿 ID 当作正式编号。

现有 `backend/system/authorization.py` 中的超级用户与兼容授权路径用于系统操作能力，不能越过治理签发门禁。系统辅助生成草稿时也不能把 `is_superuser`、Role、Position 或 Workflow actor 自动转换为“有权裁决本 Proposal”。

## 四、Formal Decision 字段分类

| 类别 | 典型字段 | 可用来源与处理规则 |
|---|---|---|
| A：系统事实（可提示、不可自证治理权） | Employee ID/工号与状态、User ID、Company/Department/OrganizationUnit、Position、Responsibility、Role、Permission、UserRoleScopeAssignment.scope_code | 源码显示有对应模型/关联；未来仅从获准环境只读带入并保留来源和 as-of 时点。显示值须由人工核对，缺关联/历史冲突为未知；不自动写入正式原件 |
| B：业务/治理判断（必须人工） | D-01～D-07 最终选项、理由、限制、第一应用对象、责任链、企业/数据与排除范围、生效政策、D-04 轻量 Workflow 边界 | 只有有权治理主体可填写、选择、确认；候选文字不是最终选择 |
| C：治理证据（正式来源与独立核验） | Decision Maker 事项权限依据、Authorization Basis、签署原件、Signed Time/Timezone、Decision Version、原件位置/长度/SHA256、审查链 | 来自独立签发/审批原件；Hash 在原件最终签署后按字节只读计算并在独立受理记录中登记。系统可核验，不可替代签署权或自造签署时间 |

双 ID 可预印在未签署模板中以降低误填，但**必须由签署原件本身明确绑定**；不能仅因系统页面或本报告包含双 ID 就视为原件绑定。系统生成的接收时间/Hash 是核验元数据，不是 Decision Maker 的签署时间/授权依据。

## 五、现有组织权限与审批能力的事实支持范围

| 基础 | 当前源码可观察字段/对象 | 能回答 | 不能证明 |
|---|---|---|---|
| 公司与组织 | `system.Company`、`Department`、`OrganizationUnit` 有公司/层级、部分有效期（`backend/system/models.py:59-159`） | 企业/部门/组织候选身份 | 谁对 D-01～D-07 有签发权；当前层级不自动代表签署时层级 |
| 员工与用户 | `pfm.Employee` 有工号、状态、可空 User/部门/岗位关联；`system.User` 有账户、公司 ID、启用状态（`backend/pfm/models.py:6-44`；`backend/system/models.py:33-53`） | 自然人和账号候选绑定 | 账户存在或员工在职即有本 Proposal 决策权 |
| 岗位与职责 | `Position`、`Responsibility`、`PositionResponsibility`、`PositionWorkflowResponsibility`（`backend/system/models.py:508-710`） | 岗位职责和流程责任候选 | 岗位名或职责类型自动构成治理任命/签署授权 |
| 系统权限 | `Role`、`Permission`、`RolePermission`、`UserRoleScopeAssignment`（`backend/system/models.py:579-620,742-798`） | 可执行的系统动作及组织/数据范围候选 | GRA 的 Issuer/Approver、事项授权或原件真实性 |
| 通用审批 | `ProcessDefinition`、`WorkflowInstance`、`ApprovalTask`、`ApprovalDecision` 和 SoD（`backend/workflow_runtime/models.py:56-185`） | 经专属配置后的审批过程和 actor/时间候选证据 | 未配置本 Proposal 的普通 Decision 自动成为 GRA 正式治理裁决 |

以上只证明**当前工作树源码结构可见**，不证明目标数据库已应用相同 Schema、存在对应行值或任何主体已获授权。复用原则是组织/身份/权限继续为原权威；未来 GRA/Decision 只引用并保存经批准的必要时点证据，不复制一套员工、角色或权限体系。

## 六、后续 GRA 能力影响（不决定物理实现）

若未来正式授权实施，可能需要 Decision Record（按双 ID/版本/事项记裁决）、Evidence Registry（不可覆盖原件与接收/Hash 链）、Governance Authorization（经签发的具体责任授予）、Verification（独立核验与失败原因）、Responsibility Binding（自然人/User/组织/责任范围/时间的受控关联）。这些是**不同事实与生命周期**：Decision 选择治理规则，不直接创建具体任命；Evidence Hash 不单独证明签发权；普通 Workflow 不等于授权。是否新模型、扩展既有模型或外部原件登记，以及 API、页面、Migration、权限、环境和恢复方式，均需独立架构/开发授权，本轮不选、不建。

## 七、首个应用场景：`需调整`（对象/范围仍未锁定）

“工程版本发布责任”有利于单场景验证：当前源码可见 `EngineeringDocumentVersion` 与 ProductVersion、BOMVersion、RoutingVersion 的关联和状态/有效期（`backend/pde/models.py:2637-2669`），也可见工程版本维护/发布等 action code（`backend/pde/views.py:844-848`）。但这只是结构/动作名证据，**不证明**哪个工程版本对象是正式责任对象、现有发布审批节点与责任链是否成立、实际运行记录是什么，或候选 Decision 已签署。

正式采用前必须由有权主体明确：产品工程版本、工程资料版本、BOM 版本、工程变更版本或发布版本中的**唯一首场景对象**；版本标识、创建/审核/发布各责任及批准节点、企业/组织/数据/时间边界；本场景与 `NCPSB-SP-A-20260929-001`/`PCE-NCPB-A-REBUILD-SOURCE-P01` 的关系；是否触及 BOM、生产、采购、财务及对应非回归和 Unfreeze 要求。第一阶段应仅验证责任授权和责任核验，不改变正式工程发布流程；若跨模块，另行范围评估。当前不推荐直接扩大或进入实现，评价为**需调整/补充范围后重评**。

## 八、是否进入 GRA 开发设计及最终状态

**当前不具备进入正式 GRA 开发设计的治理前置条件。** 尚无已核验的 D-01～D-07 签署原件，D-04 轻量模式与 D-06 首场景对象未定，Decision Maker 权限和 D-07 的正式评估入口未成立。可继续进行不改变事实的设计问题整理；正式开发设计须先由有权主体明确并验证治理方向、对象边界和设计授权范围。开发设计即使获准，也仍不等于代码/Migration/权限/Workflow 实施许可；Phase B 技术准入继续阻断。

本轮仅新增此报告。未生成正式 Decision、签署、任命、Authorization ID、GRA 或 Evidence Registry 数据，未修改组织/权限/Workflow/数据库/代码，未创建 Migration、API、页面、Source、Baseline 或运行环境。非 UI 交付，`DELIVERED USER STATE CONTRACT = N/A`；无数据库运行事实或人工签署可验收。

```text
FORMAL DECISION GENERATION MECHANISM = ASSESSED
CURRENT EXECUTABLE PATH = HUMAN-SIGNED ORIGINAL + INDEPENDENT VERIFICATION
SYSTEM-ASSISTED DRAFT = FUTURE DESIGN ONLY / NOT AUTHORIZED
SIGNED FORMAL DECISIONS RECEIVED = 0
FIRST APPLICATION SCENARIO = ENGINEERING VERSION RELEASE RESPONSIBILITY / SCOPE ADJUSTMENT REQUIRED
GRA DEVELOPMENT DESIGN ENTRY = NOT READY
DGI-01~DGI-07 = OPEN
HC-01~HC-04 = MISSING
GAP-01~GAP-04 = OPEN
SOURCE QUALIFICATION REVIEW PRE-CHECK = NOT READY
CODE / DATABASE / WORKFLOW / PERMISSION CHANGED = NO
SOURCE / BASELINE / RUNTIME ENVIRONMENT CREATED = NO
PHASE B TECHNICAL RE-ADMISSION = BLOCKED
GRA FORMAL DECISION GENERATION DESIGN ASSESSMENT COMPLETE
```
