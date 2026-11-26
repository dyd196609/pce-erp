# PCE Organization Operating Model V2 OOM-3.3.3 治理权限与角色边界设计报告

日期：2026-08-18  
阶段：OOM-3.3.3 Governance Permission & Role Boundary Design（治理权限与角色边界设计）  
类型：DESIGN ONLY（仅设计）  
实施授权：NOT AUTHORIZED（未授权实施）
## 1. 设计结论

本报告只设计组织主数据治理中的 Governance Role（治理角色）、Role（系统角色）、Permission（权限）、Responsibility（职责/责任定义）、AuthorizationService（统一授权服务）和 Workflow Runtime（流程运行引擎）边界。

- Data Owner（数据所有者）、Data Steward（数据管理员）、Reviewer（审核人）和 Approver（批准人）是治理职责，不等于业务 Responsibility，也不自动等于 `system.Role`。
- Role 回答“用户拥有哪些系统操作能力集合”；Responsibility 回答“企业中谁应该承担什么业务责任”。
- Permission 只表达能否执行系统动作；拥有 Permission 的用户不会因此自动成为责任人、Reviewer 或 Approver。
- 治理动作必须同时满足 Governance Assignment（治理指派）和 Authorization Decision（授权裁决）。
- 同一 Change Request（变更申请）的申请、审核、批准必须按自然人隔离；角色代码不同但自然人相同仍应拒绝。
- AuthorizationService 只输出 ALLOW/DENY 和证据，不承担业务批准、责任解析或组织治理。
- Workflow Runtime 可以承载审核与批准过程，但不能创建责任、修改岗位、决定责任人或替代组织事实。
- 本报告不新增或修改 Permission Model，不创建角色、权限、API、页面或数据。
## 2. 已读取文件、关键原文与判断

### 2.1 BAC-0 架构签发报告

路径：`D:\Dev-PCE\Source\docs\governance\PCE Business Action Contract V1 BAC-0架构签发报告.md`  
用途：确认 BAC 权威及 Responsibility/Permission 分离。
关键原文：
> “`backend/system/authorization.py`：AuthorizationService 统一授权裁决，只负责‘是否允许执行’。”
> “`backend/system/models.py`：Responsibility、PositionResponsibility、Role、Permission，责任与授权模型保持分离。”
判断：治理权限必须由 BAC 动作引用 Permission；Business Responsibility 仍由责任目录和岗位关系表达。
### 2.2 BAC-1 架构与契约定义设计报告

路径：`D:\Dev-PCE\Source\docs\governance\PCE Business Action Contract V1 BAC-1架构与契约定义设计报告.md`  
用途：确认 `requiredResponsibility` 与 `requiredPermission` 字段边界。
关键原文：
> “把当前分布在 Frontend Registry（前端注册表）与 ActionPermissionPolicy（动作权限策略）中的动作事实，收敛为一个服务端权威契约。”
判断：治理动作未来也必须由 Server Business Action Contract（服务端业务动作契约）定义；前端、Role 和 Workflow 不得自行定义动作事实。
### 2.3 OOM V2 与 BAC 对接设计报告

路径：`D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 与 Business Action Contract 对接设计报告.md`  
用途：确认 Position、Responsibility、Role、Permission 和 Employee 的事实边界。
关键原文：
> “`Position.default_role` 只是岗位上的默认角色提示字段，不是正式授权事实；正式授权必须读取 `UserRoleScopeAssignment → Role → RolePermission → Permission`。”
判断：Position 不自动产生 Role，Responsibility 不自动产生 Permission；治理授权必须消费正式用户角色权限关系。
### 2.4 OOM-1、OOM-2 与 OOM-3

路径：

- `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-1实施方案设计报告.md`
- `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-2实施设计与Schema决策报告.md`
- `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-3数据治理与初始化方案设计报告.md`
用途：确认模型复用、任职时态、Data Owner、Data Steward、Approver 和数据治理门禁。
判断：Employee Assignment（员工任职关系）与授权关系独立；初始化和正式维护都不能以技术管理员权限替代业务治理职责。
### 2.5 OOM-3.1 治理矩阵

路径：`D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-3.1主数据责任与治理矩阵设计报告.md`  
用途：确认四类核心治理角色与职责分离。
关键原文：
> “企业事实由业务 Data Owner 定义，由 Data Steward 维护，由独立 Reviewer 审核，由独立 Approver 批准生效。”
> “Data Steward 不得审核或批准自己录入的变更。”
判断：系统必须核验自然人身份和本次变更中的参与历史，而不能只检查用户是否拥有某个 Role。
### 2.6 OOM-3.2 与 OOM-3.3.2

路径：

- `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-3.2组织主数据变更流程与治理闭环设计报告.md`
- `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-3.3.2组织主数据变更管理能力边界设计报告.md`
用途：确认 Change Request 生命周期、申请/审核/批准隔离及唯一事实执行链。
关键原文：
> “同一自然人不得同时完成 Submitted、Reviewed、Approved。”
> “OrganizationOperatingService 应作为唯一组织事实执行入口。”
判断：治理权限控制发生在每个状态转换点；批准后仍须经过 AuthorizationService 和 OrganizationOperatingService 才能生效。
### 2.7 OOM-3.3.1 归档限制

路径：`D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-3.3.1主数据对象与系统能力映射设计报告.md`  
用途：应提供对象能力映射。
实际读取结果：当前文件只有 5 行状态摘要，无设计正文。本轮不越权修复；对象边界使用其他完整 OOM 基线。
### 2.8 权限与运行时基线

路径：`D:\Dev-PCE\Source\docs\standards\PCE-BUSINESS-ACTION-PERMISSION-V1.0.md`  
用途：确认动作、权限、角色、范围和统一授权入口。
关键原文：
> “`system.AuthorizationService` 是身份、动作权限与数据范围结论的唯一公共入口。”
> “`Position` 表达人员在组织中的岗位，`Role` 表达系统授权集合；二者不得合并。”
路径：`D:\Dev-PCE\Source\docs\governance\PCE公共组织身份权限核心V1-最终人工验收与封板报告.md`  
用途：确认服务端真实授权与岗位角色分离。
关键原文：
> “岗位与系统角色是不同字段、不同对象，没有 Position=Role 绑定。”
> “最终决定来自 `AuthorizationService`。”
路径：`D:\Dev-PCE\Source\docs\governance\Runtime职责规范.md` 与 `D:\Dev-PCE\Source\docs\governance\PCE-ERP运行层文件职责规范.md`  
用途：确认唯一 Runtime 和只读投影边界。
关键原文：
> “Runtime Adapter……只读运行模型；禁止创建业务对象、推进状态。”
判断：Workflow/Runtime 可以读取治理状态和承载过程，但正式事实写入必须收敛到组织服务。
## 3. 当前实现能力与缺口

### 3.1 AuthorizationService 当前能力

路径：`D:\Dev-PCE\Source\backend\system\authorization.py`  
用途：统一授权裁决。
关键原文：
```python
class AuthorizationService:
    def decide(...):
```
当前已能基于 User、action code、organization、Role/Permission/Scope 事实返回 `ALLOWED` 或 `PERMISSION_DENIED` 及证据。
缺口：当前裁决不等于本次 Change Request 的治理参与资格，也没有证明自然人未同时参与提交、审核和批准。
### 3.2 当前组织维护权限

路径：`D:\Dev-PCE\Source\backend\system\organization_operating.py`  
用途：组织维护动作到 Permission 的映射。
关键原文：
```python
SAVE_ORGANIZATION_UNIT → system.organization.structure.manage
SAVE_POSITION → system.organization.position.manage
SAVE_RESPONSIBILITY → system.organization.responsibility.manage
SAVE_POSITION_RESPONSIBILITY → system.organization.responsibility.manage
```
判断：现有 `*.manage` 是可复用的当前维护能力基线，但粒度不足以表达 Submit、Review、Approve、Retire 的职责分离。目标动作和权限需要 BAC-1 实施阶段另行定义，本轮不创建。
### 3.3 Workflow Runtime 当前能力

路径：`D:\Dev-PCE\Source\backend\workflow_runtime\action_permissions.py`  
用途：动作权限策略和服务端校验器。
关键原文：
```python
class ActionPermissionPolicy:
    requiredPermission: str
```
```python
class ActionPermissionValidator:
```
判断：现有运行时可校验动作权限，但没有治理角色指派或 Change Request 职责分离事实；不得把 `requiredPermission` 解释为审批人来源。
## 4. 四类 Governance Role（治理角色）

| 治理角色 | 回答的问题 | 核心职责 | 系统能力边界 |
|---|---|---|---|
| Data Owner | 谁对业务事实负责？ | 定义语义、规则、质量目标 | 确认业务所有权；不自动拥有全部权限 |
| Data Steward | 谁维护和保证质量？ | 草稿、校验、影响分析、提交 | 可维护申请；不得审核/批准自己维护的申请 |
| Reviewer | 谁检查变更正确性？ | 合理性、影响、引用、时态审核 | 必须被明确指派且有审核 Permission |
| Approver | 谁承担生效批准责任？ | 接受风险、批准生效条件 | 必须独立指派且有批准 Permission |
### 4.1 治理角色不是静态系统角色的简单替代

系统 Role 可以聚合治理动作 Permission，例如“组织变更审核角色”；但用户拥有该 Role 只表示具备审核能力，不表示他自动成为每条申请的 Reviewer。
每次动作必须同时满足：
```text
Governance Assignment（本申请明确指派）
+ Permission（动作执行能力）
+ Organization Scope（组织范围）
+ Separation of Duties（职责分离）
= Action Allowed（允许执行）
```
### 4.2 治理角色不产生业务 Responsibility

- Data Owner 不等于某项 Business Responsibility 的责任人。
- Reviewer/Approver 不等于流程业务审批责任。
- 治理角色指派不得写入 PositionResponsibility。
- 业务 Responsibility 不自动授予治理 Permission。
## 5. Role 与 Responsibility 边界

| 对象 | 回答 | 事实来源 | 不表示 |
|---|---|---|---|
| Role（角色） | 用户拥有哪些系统能力集合？ | UserRoleScopeAssignment、Role | 岗位、业务责任、审批人 |
| Permission（权限） | 用户能否执行系统动作？ | RolePermission、Permission | 谁应该负责 |
| Responsibility（责任） | 企业中谁应该承担什么业务责任？ | Responsibility 目录 | 系统授权集合 |
| PositionResponsibility | 哪个岗位承担责任？ | 岗位责任关系 | 用户是否有执行权限 |
| Governance Assignment | 谁审核/批准本次变更？ | 获批治理指派 | 通用业务责任 |
禁止模型：

- `Role = Responsibility`；
- `Permission → 寻找责任人`；
- “拥有 Permission 的用户 = 责任人”；
- “岗位默认 Role = 正式授权”；
- “Approver Role 中任意用户 = 本申请批准人”。
## 6. Permission（权限）设计边界

### 6.1 AuthorizationService 负责

- 是否允许查看组织治理对象；
- 是否允许创建或提交 Change Request；
- 是否允许执行审核、批准、退役或生效动作；
- 用户的组织和部门 Scope 是否覆盖目标对象；
- 返回 ALLOW/DENY、决策代码和服务端证据。
### 6.2 AuthorizationService 不负责

- 判断业务上谁应该批准；
- 创建或修改 Responsibility；
- 选择承担责任的 Position；
- 为 Change Request 自动指定 Reviewer/Approver；
- 替代影响分析或业务审批；
- 因用户为 superuser 而豁免自然人职责分离。
### 6.3 目标授权输入与输出

输入：User（用户）、Action（动作）、Organization Scope（组织范围）、requiredPermission、Business Object（业务对象）和治理上下文。  
输出：ALLOW/DENY、Decision Code（决策代码）、Decision Evidence（决策证据）、有效 Scope。
治理上下文校验应位于治理服务中；AuthorizationService 保持统一授权职责，不扩展为审批引擎。
## 7. 治理动作权限设计

以下为未来 BAC/Permission 候选语义，不代表本轮创建权限。每个动作必须独立拥有 `requiredPermission`，不得复用一个 `manage` 权限完成提交、审核和批准全部步骤。
| 对象 | 查看 | 提交 | 审核 | 批准 | 特殊动作 |
|---|---|---|---|---|---|
| Company | company.view | company.change.submit | company.change.review | company.change.approve | deactivate/merge |
| Organization Unit | unit.view | unit.change.submit | unit.change.review | unit.change.approve | deactivate/merge |
| Position | position.view | position.change.submit | position.change.review | position.change.approve | deactivate/retire |
| Responsibility | responsibility.view | responsibility.change.submit | responsibility.change.review | responsibility.change.approve | suspend/retire |
| PositionResponsibility | relation.view | relation.change.submit | relation.change.review | relation.change.approve | end/period-adjust |
| Employee Assignment | assignment.view | assignment.change.submit | assignment.change.review | assignment.change.approve | transfer/concurrent/acting/end |
### 7.1 Company

公司查看、提交、审核、批准必须分权；合并和停用属于高风险动作，批准权限不能由普通维护角色继承。
### 7.2 Organization Unit

创建申请、关系调整、合并和停用都先形成 Change Request；有结构维护权限不表示可以审核或批准自己的调整。
### 7.3 Position

新建、修改、停用/退役采用不同动作语义。任何岗位权限均不得自动创建 Responsibility、Role 或 Permission。
### 7.4 Responsibility

责任是最高治理等级。查看、提交定义、业务/架构审核、批准、暂停和退役应分离；退役必须检查 BAC 和岗位责任引用。
### 7.5 PositionResponsibility

建立、修改、解除、PRIMARY/SUPPORTING 和有效期调整都通过关系变更申请；拥有关系维护权限不等于可以决定业务责任归属。
### 7.6 Employee Assignment

调岗、兼岗、代理和离岗是任职变更动作；执行权限不自动授予新岗位相关业务 Permission，也不修改 Responsibility。
## 8. Governance Role 与系统 Role 的目标映射

以下是能力包设计示例，不是本轮实际 Role 创建方案：
| 能力包 | 可包含 Permission | 不得隐含 |
|---|---|---|
| Governance Viewer | view | 提交、审核、批准 |
| Change Submitter | view、draft、submit | review、approve |
| Change Reviewer | view、review | 自动成为指定 Reviewer |
| Change Approver | view、approve | 自动成为指定 Approver |
| Effective Executor | execute-effective | 业务批准权 |
| Audit Viewer | view-audit | 修改或删除审计 |
允许同一用户因工作需要持有多个系统 Role，但对单个 Change Request 仍执行自然人级冲突门禁。Role 分配不能规避交易级职责分离。
## 9. AuthorizationService 能力边界

目标授权链：
```text
User + Action + Object + Organization Scope
→ Server BAC.requiredPermission
→ AuthorizationService
→ ALLOW / DENY + Decision Evidence
```
治理动作最终允许条件：
```text
AuthorizationService = ALLOW
+ 指派资格有效
+ 状态转换合法
+ 自然人职责分离通过
= 治理动作允许
```
AuthorizationService 返回 ALLOW 只是必要条件，不是业务批准结果；治理服务仍需校验申请状态、指派与参与历史。
## 10. Workflow Runtime 边界

### 10.1 未来允许

- 承载 Change Request 的审核和批准过程；
- 创建审核/批准待办；
- 记录节点开始、完成、拒绝和退回；
- 调用 AuthorizationService 校验节点动作；
- 将获批结果交给 OrganizationOperatingService 执行。
### 10.2 明确禁止

- Workflow 创建或修改 Responsibility；
- Workflow 修改 Position 或 Employee Assignment；
- Workflow 根据 Role/Permission 决定业务责任人；
- Workflow 把 `required_role_code` 写成 Responsibility Code；
- Workflow 绕过 Change Request 直接写组织事实；
- Workflow 用任务状态替代正式组织事实状态。
Workflow 只是治理过程承载者，不是组织事实所有者。当前 `Workflow Integration = NOT AUTHORIZED`。
## 11. 权限冲突检测

### 11.1 检测输入

- 当前 User 与 Employee/自然人身份；
- Change Request 的 requester、steward、reviewer、approver、operator；
- 已完成状态转换及操作者；
- 当前 action、requiredPermission 和 Organization Scope；
- 是否存在代理、共享账户或身份绑定异常。
### 11.2 阻断规则

| 冲突 | 结果 |
|---|---|
| 申请人尝试审核 | DENY |
| 申请人尝试批准 | DENY |
| Data Steward 尝试批准自己维护的申请 | DENY |
| Reviewer 尝试批准同一申请 | DENY |
| Approver 未被指派 | DENY，即使拥有 Permission |
| 指派人无对应 Permission | DENY |
| Scope 不覆盖目标组织 | DENY |
| superuser 触发职责冲突 | DENY，不豁免 |
| 共享账号无法证明自然人隔离 | DENY |
### 11.3 提示与记录

系统应返回稳定治理拒绝代码，例如 `GOVERNANCE_SOD_CONFLICT`、可理解中文原因、冲突阶段和处理建议；不得泄露无关用户权限信息。
每次拒绝记录：申请编号、动作、当前操作者、冲突类型、Permission/Scope 决策摘要、时间和零业务写入结果。拒绝记录不能推进 Change Request 状态。
## 12. 验收设计

| 编号 | 场景 | 预期结果 |
|---|---|---|
| GPR-01 | Role 与 Responsibility 查询 | 来源、字段和语义分离 |
| GPR-02 | 有批准 Permission 但未被指派 | DENY |
| GPR-03 | 被指派但无批准 Permission | DENY/HTTP 403 |
| GPR-04 | 申请人切换不同 Role 审核自己申请 | 按自然人识别并拒绝 |
| GPR-05 | Reviewer 尝试批准 | DENY，状态不变 |
| GPR-06 | superuser 自提自批 | DENY，职责分离不豁免 |
| GPR-07 | Scope 不覆盖目标组织 | DENY，数据写入 0 |
| GPR-08 | 正确 Reviewer 审核 | ALLOW，记录证据，不改正式事实 |
| GPR-09 | 正确 Approver 批准 | ALLOW，只改变申请状态 |
| GPR-10 | 未经批准调用组织写服务 | 拒绝，正式事实不变 |
| GPR-11 | Workflow 尝试创建 Responsibility | 拒绝 |
| GPR-12 | 拥有业务 Permission 的用户被当作责任人 | 不得发生 |
## 13. OOM-4 前置条件

进入 Organization Model Implementation（组织模型实施）前必须确认：

1. 四类治理角色的职责与对象范围冻结；
2. Governance Assignment 与系统 Role 的双条件模型获批；
3. Submit/Review/Approve/Execute 动作语义和 BAC 字段获批；
4. 每个对象的目标 Permission 粒度获批；
5. 自然人身份绑定、代理和共享账号策略明确；
6. 职责分离冲突代码、提示、审计和零写入规则冻结；
7. superuser 不豁免治理职责分离的规则获批；
8. AuthorizationService 保持授权职责、不演变为审批引擎；
9. Workflow 只承载过程、不写组织事实的边界冻结；
10. Permission/Role 迁移、API、页面和测试分别获得新授权。
## 14. 保护确认

本轮只新增本设计报告，没有生成 OOM-3.3.4，也没有修复 OOM-3.3.1 归档内容。
`Documentation Changed = YES`。  
`Code Changed = NO`；`Database Changed = NO`；`Migration Created = NO`；`API Created = NO`。  
`Organization Data Changed = NO`；`Responsibility Data Changed = NO`；`Employee Data Changed = NO`。  
`Permission Model Changed = NO`；`AuthorizationService Changed = NO`；`Workflow Runtime Changed = NO`。  
`ApprovalTask Changed = NO`；`RRE Started = NO`；`Unauthorized Business Writes = 0`。
## 15. 最终状态

`OOM-3.3.3 Governance Permission & Role Boundary Design = COMPLETE`。  
`OOM-3.3.4 = NOT STARTED`。  
`Organization Model Implementation = NOT AUTHORIZED`。  
`RRE-1 = NOT AUTHORIZED`；`Workflow Integration = NOT AUTHORIZED`。
本报告完成后停止，等待下一步指令。
