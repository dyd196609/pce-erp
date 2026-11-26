# FINAL / CONSOLIDATED

# 《Phase B New Controlled Protection Baseline Governance Responsibility Authorization Governance Decision Preparation FINAL / CONSOLIDATED报告》

日期：2026-09-29  
阶段：Governance Decision Preparation（仅决策材料）  
对象：Proposal-bound Governance Responsibility Authorization Layer（GRA）  
Source Proposal：`NCPSB-SP-A-20260929-001`  
Logical Source：`PCE-NCPB-A-REBUILD-SOURCE-P01`  
Review Level：B；Full Content Review Required：NO  
最终 Gate：`GOVERNANCE RESPONSIBILITY AUTHORIZATION GOVERNANCE DECISION PACKAGE READY`

## 一、决策背景、依据与本轮边界

路径 B 正在准备未来新的受控 Protection Baseline；这不是将旧 734F 或漂移后的 ABA 文件重新解释、复制或签署为新来源。GRA 的目的仅是为本 Proposal 提供可核验的治理责任授权事实。现有设计评估提出 B（授权语义）+ C（原件证据）+ A（复用经批准的 Workflow 过程）；详细设计给出逻辑字段、验证、冲突、审批及非回归契约；Governance & Architecture Review 对 GRA 的定位和分层职责作出**技术层面的方向性接受**，但把唯一权威、专属 Workflow 绑定、安全规则及物理形态保留为待裁决事项。实施准备评估仍为阻断状态。这些报告均不是独立治理主体的签发/批准原件。

| 输入 | 可用于决策的内容 | 不可替代的证据 |
|---|---|---|
| `Governance Responsibility Authorization Layer Design评估FINAL CONSOLIDATED报告 20260929.md` | A/B/C 比较与事实分层 | 正式治理批准 |
| `Governance Responsibility Authorization Layer Detailed Design FINAL CONSOLIDATED报告 20260929.md` | 候选模型、原件、页面/API、审批与安全契约 | 实施授权与人员任命 |
| `Governance Responsibility Authorization Layer Governance & Architecture Review FINAL CONSOLIDATED报告 20260929.md` | 技术可接受范围、REVISE 项及阻断项 | 有权主体的书面决策 |
| `Governance Responsibility Authorization Layer Implementation Readiness评估FINAL CONSOLIDATED报告 20260929.md` | HC/GAP、架构、测试及授权缺口 | 缺失的独立输入本身 |

当前独立治理输入接受数为 0；`HC-01`～`HC-04` 缺真实任命原件，`GAP-01`～`GAP-04` 未关闭；Source Qualification Review Pre-check 为 `NOT READY`。本轮不指定人员、不签发编号、不执行审批，也不打开或修改数据库。下文所有选项均是**待有权治理主体裁决**，没有预选。

```text
EFFECTIVE INSTRUCTION SET
ACTIVE = 整理 GRA 治理决策包；仅新增本报告
FROZEN = 734F/ABA 历史证据；既有组织/身份/权限/Workflow 权威；HC/GAP 未关闭
NOT AUTHORIZED = 治理签署或任命、GRA/Registry 记录、Authorization ID、源码/数据库/权限修改、Migration、Source/Baseline 创建

INSTRUCTION CONTROL SHEET
Original Goal = 供有权治理主体判断 GRA、B+C+A、事实权威与是否进入实施授权评估
Current Goal = 明确各决策问题、选项、范围、所需原件及后续影响
IN SCOPE = 已有设计/评审/阻断报告只读汇总；本报告
OUT OF SCOPE = 代决、实施批准、开发、Migration、正式 Source Qualification
Database Boundary = 不连接数据库
Non-Regression Baseline = 组织权限、登录、Workflow、现有菜单/Route/API 和已开发模块身份不变
User Acceptance Path = N/A（无 UI 交付）
Stop Condition = 文档核对完成即停止，等待独立治理输入
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

本轮不修改实现或共享依赖。未来实施须按具体拟改文件重新完成保护预检；本报告不能代替 Unfreeze 授权。用户真实运行结果高于报告与源码推断。

## 二、GRA 定位决策

**待裁决问题 D-01：是否采用 GRA 作为本 Proposal/Logical Source 绑定的治理责任授权事实层？** 可选记录值仅 `ACCEPT / MODIFY / REJECT`；当前为 `PENDING DECISION`。技术建议是保持独立的授权语义，但建议不构成批准。

| 可选裁决 | 应明确的范围 | 后续影响 |
|---|---|---|
| `ACCEPT` | 仅承载四类治理角色的任命、范围、时效、版本和撤销事实；引用既有基础事实，不复制组织/员工/角色/权限 | 可继续审定物理承载与授权评估，不自动任命或实施 |
| `MODIFY` | 逐项列出需修订的授权语义、边界及重新评审责任 | 修改设计后重评；未完成前不得实施 |
| `REJECT` | 记录拒绝理由及是否有替代的可追溯治理授权方案 | 停止按本 GRA 方案推进；不能把岗位或系统权限直接顶替治理任命 |

任何裁决均应明确禁止 GRA 成为第二套组织权限系统；若拟改变该边界，必须单独提出架构变更并重做事实权威评审。

## 三、B+C+A 组合决策

**待裁决问题 D-02：是否采用 B+C+A 的分工与受控关联？** 当前为 `PENDING DECISION`，可选 `ACCEPT / MODIFY / REJECT`。

| 层 | 拟承担的唯一职责 | 不得冒充的事实 |
|---|---|---|
| B：GRA | 谁被授予本 Proposal/Logical Source 的何种 Governance Role、范围、起止时间及生命周期 | 不自创签发权，不复制组织/身份/系统权限 |
| C：Evidence Registry | 原件、SHA256、来源、签署/接收时间、Verification、更正/撤销历史 | Hash 或文件名不能单独证明签署权/批准有效 |
| A：Workflow | 正式审批的节点、Task、Decision、actor、时间与决策 Hash | 普通 Workflow 决策不能自动成为持续治理授权 |

裁决书须明确 B↔C 原件/版本关系、A↔B 精确 Proposal/版本/范围绑定、失败与撤销的单向因果、初始任命的独立签发权，避免循环授权。若 `MODIFY`，须列出替代结构及单一权威如何保持；若 `REJECT`，当前组合停止，不能自动退化为只用 Workflow 或只用文档。治理选择不等于数据库表或 Migration 选择。

## 四、事实权威边界决策

**待裁决问题 D-03：是否保留如下单一事实来源并批准 GRA 只读引用边界？** 当前为 `PENDING DECISION`。

| 事实 | 现有基础权威 | 拟定 GRA 关联 | 必须在决策中明确 |
|---|---|---|---|
| Organization | Company、Department、OrganizationUnit | ID 引用与签发时经核验的最小范围快照 | 公司、层级、有效期、历史解释及数据范围口径 |
| Identity | Employee、User | 自然人/账户双身份引用及状态核验 | 关联缺失、离职/调岗、账户停用时 Fail-Closed |
| Security | Role、Permission、UserRoleScopeAssignment | 系统动作权限与组织范围的服务端核验 | 系统 Role/岗位不转换为治理角色 |
| Governance | 经独立核验的 GRA + Evidence Registry | 本 Proposal 任命语义和原始证据链 | 哪个对象是持续授权权威、原件权威及版本/撤销效力 |
| Approval Process | 专属配置的 WorkflowInstance、ApprovalTask、ApprovalDecision | 决策事件引用 | 普通审批与本 Proposal 批准的分界 |

对任何一项选择 `MODIFY/REJECT` 时，应明确替代权威、迁移风险和重新评审范围；不得在本决策包中改写当前权威数据。

## 五、Workflow 决策事项

**待裁决问题 D-04：是否在现有 Workflow 框架内设 GRA 专用审批配置？** 可选 `ACCEPT / MODIFY / REJECT`，当前未裁决。需分别决定：专用 Document Type、ProcessDefinition、审批节点/链、提交/审核/批准/撤销动作、双人及六组职责分离、代理/回避、Decision 与 GRA 版本/原件 Hash/范围的稳定绑定。既有 `WorkflowInstance.document_id` 为整数，外部工件如不具兼容稳定标识，须先审批映射方案，不能以文件名或临时 ID 拼接。收到普通 Workflow 批准、页面显示或证据受理通过均不等于 GRA 授权生效。

## 六、安全治理决策事项

**待裁决问题 D-05：是否批准服务端双门禁与例外禁止原则？** 当前未裁决。候选判定为：有效系统动作 Permission **且** 对象/组织范围匹配 **且** 本 Proposal 有效治理授权或独立核验的签发权 **且** 生命周期、证据、审批及职责分离条件成立，才允许动作；其余 Fail-Closed。Superuser、Admin、前端隐藏/禁用按钮、旧缓存及普通 Workflow 不能绕过治理授权。

裁决需补充 Action Code、对象级 Validator、直接 API 拒绝、审计与异常处理、初始任命签发权的非循环引导。`ACCEPT` 仅批准政策方向，不自动登记 Permission 或部署 Validator；`MODIFY/REJECT` 须明确可审计的替代安全边界。

## 七、人工责任与证据保管决策事项

| 待裁决权责 | 必须由有权主体提供的定义 | 当前状态 |
|---|---|---|
| 签发/变更/撤销权 | 权威主体、适用范围、代理/回避、有效时间及可核验授权依据 | `MISSING` |
| 批准权 | 谁可批准 GRA、授权范围、生命周期及冲突例外（若允许） | `MISSING` |
| 原件保管权 | 原件位置/不可覆盖、Hash 复算、访问权限、留存/恢复及更正/撤销链 | `PENDING` |
| 独立审查权 | Verification、六组冲突、Gap 状态复核及审核自己输入的禁止规则 | `PENDING` |
| 四角色任命 | HC-01～04 的 User/Employee、Role、Organization、授权依据、范围和有效期 | `MISSING` |
| 编号与边界 | Authorization ID 规则、企业/组织/数据及排除范围、截止时间/时区 | `MISSING / PENDING` |

本轮没有指定任何自然人、账号、签发者或批准者，也没有生成 Authorization ID。治理主体须提交独立原件；模板、设计报告和 Codex 记录不可作为批准输入。收到材料后仍须由 Governance Input Acceptance Verification 逐件核验，不直接关闭 Gap。

## 八、未来实施边界的待裁决范围

**待裁决问题 D-06：未来可申请的实施范围及明确排除范围是什么？** 这是范围划定，不是本轮开发许可。

| 候选纳入范围 | 应另行批准的约束 | 当前状态 |
|---|---|---|
| GRA 数据模型、Evidence Registry、Conflict Check/版本撤销审计 | 单一事实权威、原件不可覆盖、隐私、恢复及 Migration/回退 | `PENDING` |
| API、服务端 Permission/Validator、Workflow 专属配置 | 幂等、版本、状态机、双门禁、独立审批与直接调用拒绝 | `PENDING` |
| 组织与权限基础中的受控页面入口 | 既有 Tab/Route/Menu 与企业列表基座 Preserve-and-Extend、服务端事实、人工 UI 验收 | `PENDING` |
| 测试与审计 | 六组冲突、过期/撤销、原件 Hash、错误/并发、非回归、恢复与用户可见路径 | `PENDING` |

明确排除：替换 Company/Employee/User/Role/Permission 主数据或现有 Workflow 历史；复写旧 734F/ABA；创建 Source、Candidate、Baseline；Acceptance Runtime 初始化；Phase B 开发/准入的自动放行。实施时不得顺带处理当前其他模块 Schema 漂移或未冻结工作树。命中 Frozen Core/Shared Dependency 时仍需独立 Unfreeze 审批。

## 九、待治理主体裁决清单及决策记录最低要求

| 决策 ID | 问题 | 可用结果 | 当前记录 |
|---|---|---|---|
| D-01 | GRA Proposal 绑定定位与非平行组织权限体系 | `ACCEPT / MODIFY / REJECT` | `PENDING DECISION` |
| D-02 | B+C+A 分工、原件/版本/审批关联 | `ACCEPT / MODIFY / REJECT` | `PENDING DECISION` |
| D-03 | Organization/Identity/Security/Governance 单一事实权威 | `ACCEPT / MODIFY / REJECT` | `PENDING DECISION` |
| D-04 | 专属 Workflow 类型、定义、审批链及职责分离 | `ACCEPT / MODIFY / REJECT` | `PENDING DECISION` |
| D-05 | 双门禁与 Superuser/Admin/前端/普通审批不绕过政策 | `ACCEPT / MODIFY / REJECT` | `PENDING DECISION` |
| D-06 | 未来实施候选范围、明确排除与保护边界 | `ACCEPT / MODIFY / REJECT` | `PENDING DECISION` |
| D-07 | 是否允许进入**实施授权评估**，而非实施本身 | `ACCEPT / MODIFY / REJECT` | `PENDING DECISION` |

每项真实决策须另有独立记录：决策主体与权限依据、决策时间/时区、所绑定的双 ID、文档/设计版本、选择及理由、适用范围/有效期、例外、原件位置与 Hash、签署和审查链。缺任一关键字段时保持待验证；本报告不预填签名、User ID、Authorization ID 或批准时间。`D-07 ACCEPT` 仅允许开展后续评估，不等于授权开发、Migration、Source Qualification 或关闭任何 Gap。

## 十、决策后续影响与进入条件

若有权主体 `ACCEPT` 某项，应将真实决定交 Governance Input Acceptance Verification，核对独立性、签署权、双 ID、版本、Hash、范围、有效期和职责冲突，再更新对应状态。`MODIFY` 应形成修订设计及复审；`REJECT` 应停止依赖该方案并记录替代路径。任何单项选择不自动推出其它项通过。

即使 D-01～D-07 经独立核验，未来仍须：HC-01～04 真实任命、Authorization ID 与 Data Boundary 批准、四角色六组冲突检查、`GAP-01`～`GAP-04` 独立关闭；架构/安全批准物理承载与专属流程；冻结 Approved Commit/Schema/Migration、目标环境、测试与回退方案；分别取得 Migration 与开发实施授权。决策包完成 **不等于** 具备立即实施条件，也不自动通过 Source Qualification Review Pre-check 或开放 Phase B。

## 十一、未执行事项与最终状态

本轮仅新增本报告。未产生任何治理批准事实、责任任命、Authorization ID、GRA/Evidence Registry 记录或审批；未修改组织权限模型、Workflow、数据库、models、Migration、API、页面或配置；未创建 Source、Baseline 或运行环境。非 UI 交付，`DELIVERED USER STATE CONTRACT = N/A`；未执行实施测试。文档回读仅验证材料完整，不验证未来真实签署。

```text
DECISION QUESTIONS PREPARED = D-01~D-07
INDEPENDENT GOVERNANCE DECISIONS RECORDED = 0
HC-01~HC-04 = MISSING
GAP-01~GAP-04 = OPEN
SOURCE QUALIFICATION REVIEW PRE-CHECK = NOT READY
IMPLEMENTATION / MIGRATION AUTHORIZATION = NOT GRANTED
CODE / DATABASE / PERMISSION / WORKFLOW CHANGED = NO
SOURCE / BASELINE / RUNTIME ENVIRONMENT CREATED = NO
PHASE B TECHNICAL RE-ADMISSION = BLOCKED
GOVERNANCE RESPONSIBILITY AUTHORIZATION GOVERNANCE DECISION PACKAGE READY
```
