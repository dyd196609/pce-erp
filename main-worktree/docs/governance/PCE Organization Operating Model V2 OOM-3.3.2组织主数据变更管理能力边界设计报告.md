# PCE Organization Operating Model V2 OOM-3.3.2 组织主数据变更管理能力边界设计报告

日期：2026-08-18  
阶段：OOM-3.3.2 Governance Capability Boundary Design（治理能力边界设计）  
类型：DESIGN ONLY（仅设计）  
实施授权：NOT AUTHORIZED（未授权实施）
## 1. 设计结论

本报告只设计 Change Management（变更管理）如何映射为软件能力，不展开 OOM-3.3.3 治理权限角色设计或 OOM-3.3.4 AI、Digital Twin、Control 能力设计。
核心结论：

- Change Request（变更申请）需要成为独立治理对象，与 Company、Organization Unit、Position、Responsibility、PositionResponsibility、Employee Assignment 等正式事实分离。
- 正式组织事实不能由页面直接修改；页面先提交变更申请，获批后才可由唯一组织事实执行入口生效。
- Impact Analysis（影响分析）可以自动发现引用、冲突与候选变化，但不能自动审核或批准。
- Reviewer（审核人）检查正确性，Approver（批准人）承担业务批准责任；申请、审核、批准不得由同一自然人完成。
- Effective Period（有效期间）统一采用 `[effective_from, effective_to)` 左闭右开模型。
- OrganizationOperatingService（组织运作服务）继续作为唯一事实执行入口，不新建平行写服务。
- Workflow（工作流）可在未来独立授权后承载过程编排，但不能直接创建或修改组织事实。
- RRE（责任解析引擎）只读消费事实，不得发起自动修复或写组织数据。
## 2. 已读取治理文件、关键原文与判断

### 2.1 BAC-0 架构签发报告

路径：`D:\Dev-PCE\Source\docs\governance\PCE Business Action Contract V1 BAC-0架构签发报告.md`  
用途：确认 Business Action Contract（业务动作契约，BAC）的权威地位及责任、权限边界。
关键原文：
> “本次批准代表架构规则批准，不代表代码实施批准。”
> “当前仓库尚未实施完整 Server Business Action Contract（服务端业务动作契约），尤其尚未建立 `requiredResponsibility` 字段。”
判断：BAC 架构基线不等于实施；组织变更管理不得借 BAC 自动创建 Responsibility。
### 2.2 BAC-1 架构与契约定义设计报告

路径：`D:\Dev-PCE\Source\docs\governance\PCE Business Action Contract V1 BAC-1架构与契约定义设计报告.md`  
用途：确认 `requiredResponsibility`、`requiredPermission` 与服务端契约边界。
关键原文：
> “把当前分布在 Frontend Registry（前端注册表）与 ActionPermissionPolicy（动作权限策略）中的动作事实，收敛为一个服务端权威契约。”
判断：`requiredResponsibility` 只能引用已有责任；`requiredPermission` 只用于 AuthorizationService（统一授权服务）。Permission 不能寻找责任人。
### 2.3 OOM V2 与 BAC 对接设计报告

路径：`D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 与 Business Action Contract 对接设计报告.md`  
用途：确认组织、岗位、责任、岗位责任、员工与 BAC/RRE 的事实链。
关键原文：
> “当前 `system.Responsibility` 已经是独立责任目录事实源；BAC 只能引用其编码，不能生成责任。”
> “当前 `system.PositionResponsibility` 可以表达‘岗位承担责任’。”
判断：变更申请只能提出对正式事实的修改，不得成为第二责任目录或第二岗位责任事实源。
### 2.4 OOM-1 实施方案设计报告

路径：`D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-1实施方案设计报告.md`  
用途：确认现有模型复用与员工变更边界。
关键原文：
> “员工变动只改变任职关系，不修改 Business Action、Workflow、Responsibility 或 Permission。”
判断：调岗、晋升、离岗、兼岗与代理均通过 Employee Assignment 变更表达，不联动改责任或授权。
### 2.5 OOM-2 实施设计与 Schema 决策报告

路径：`D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-2实施设计与Schema决策报告.md`  
用途：确认时态关系与统一有效期间。
关键原文：
> “Half-open Interval（左闭右开区间）：统一使用 `[effective_from, effective_to)`，交接时点不重叠。”
判断：变更申请必须显式携带生效时间；未来任职与岗位责任按左闭右开区间校验重叠和交接。
### 2.6 OOM-3 数据治理与初始化方案

路径：`D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-3数据治理与初始化方案设计报告.md`  
用途：确认数据所有权、管护、独立批准、初始化和质量门禁。
判断：批量初始化也属于变更管理，不得绕过申请、影响分析、审核、批准和审计。
### 2.7 OOM-3.1 主数据责任与治理矩阵

路径：`D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-3.1主数据责任与治理矩阵设计报告.md`  
用途：确认 Data Owner、Data Steward、Reviewer、Approver 及职责分离。
关键原文：
> “企业事实由业务 Data Owner（数据所有者）定义，由 Data Steward（数据管理员）维护，由独立 Reviewer（审核人）审核，由独立 Approver（批准人）批准生效。”
> “同一自然人不得审批自己发起或维护的变更。”
判断：变更管理能力必须按自然人校验职责冲突，不能只比较角色代码。
### 2.8 OOM-3.2 变更流程与治理闭环

路径：`D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-3.2组织主数据变更流程与治理闭环设计报告.md`  
用途：本报告的直接流程基线。
关键原文：
> “正式组织事实不得因页面编辑或操作者拥有维护权限而直接改变。”
> “保留现有 OrganizationOperatingService 作为未来‘执行已批准变更’的唯一组织写服务。”
判断：OOM-3.3.2 把上述治理规则映射为申请、影响分析、审核、批准、生效执行与审计能力。
### 2.9 OOM-3.3.1 归档状态说明

路径：`D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-3.3.1主数据对象与系统能力映射设计报告.md`  
用途：应提供主数据对象与系统能力映射。
实际读取结果：当前文件只有 OOM-3.3.1 完成和后续阶段未开始的状态摘要，没有可复核的设计正文。
判断：本报告不擅自修复或扩写上一阶段文件；对象边界继续以 OOM 对接、OOM-1、OOM-2、OOM-3.1 与 OOM-3.2 的完整内容为依据。此归档缺口需要另行治理。
## 3. 当前软件能力与缺口

### 3.1 当前组织事实执行链

代码路径：`D:\Dev-PCE\Source\backend\system\organization_operating.py`  
用途：当前组织维护动作的授权、事务保存和审计。
关键原文：
```python
class OrganizationOperatingService:
```
```python
decision = AuthorizationService.decide(...)
with transaction.atomic():
    result = handler(...)
```
判断：已有“动作注册—授权—事务—审计”的正确基础，可演进为获批变更的唯一执行器。
### 3.2 当前审计能力

代码路径：`D:\Dev-PCE\Source\backend\system\models.py`  
用途：OrganizationOperatingAuditRecord（组织运作审计记录）。
关键原文：
```python
class OrganizationOperatingAuditRecord(models.Model):
    before_snapshot = models.JSONField("修改前", default=dict)
    after_snapshot = models.JSONField("修改后", default=dict)
```
判断：当前可记录 Before/After、操作者、原因和时间，但不足以完整证明申请人、审核人、批准人、批准内容摘要和计划生效时间。
### 3.3 当前页面能力

代码路径：`D:\Dev-PCE\Source\frontend\src\meta\components\OrganizationOperatingAdminDialog.vue`  
用途：当前组织、岗位、责任、岗位责任和员工维护交互。
关键原文：
> “保存岗位并回读”
> “正式组织事实已保存并生成审计”
判断：当前页面仍以即时保存正式事实为中心，尚无独立 Change Request、Impact Analysis、Review、Approval 和计划生效交互。未来应把保存动作收敛为提交申请或执行获批申请。
### 3.4 能力缺口

| 缺口 | 当前影响 | 目标能力 |
|---|---|---|
| 无独立 Change Request | 页面可直接进入正式保存 | 申请与正式事实隔离 |
| 无结构化影响分析 | 审核人无法验证完整依赖 | 服务端只读影响快照 |
| 无 Reviewer/Approver 证据 | 审计只证明操作者 | 独立审核与批准记录 |
| 无批准内容摘要 | 批准后内容可发生漂移 | Payload Hash（内容摘要） |
| 无计划生效门禁 | 保存即生效 | 生效日期与执行前复核 |
| 无状态历史 | 无法解释申请生命周期 | 状态转换证据链 |
| 无批准过期/替代控制 | 旧批准可能误执行 | Expired/Superseded 控制 |
## 4. Change Request（变更申请）能力

设计决策：未来需要 Change Request 作为独立治理对象，但本轮不决定数据库表、API 或页面实现。
### 4.1 对象边界

Change Request 是“拟议变更与治理证据”，不是正式 Organization、Position、Responsibility、PositionResponsibility 或 Employee Assignment 事实。
它可以引用正式对象并保存冻结快照，但在 Effective（已生效）前不得改变正式事实。
### 4.2 最小逻辑字段

| 字段 | 说明 |
|---|---|
| requestCode | 唯一申请编号 |
| requester | 申请人 |
| objectType/objectId | 申请对象类型与标识 |
| changeType | CREATE、UPDATE、SUSPEND、MERGE、RETIRE、ASSIGN 等 |
| reason | 变更原因 |
| beforeSnapshot | 申请时正式事实 |
| proposedChange/afterSnapshot | 拟议变更内容 |
| payloadHash | 获批内容摘要 |
| effectiveFrom/effectiveTo | 生效时间与有效区间 |
| impactScope | 影响对象与范围 |
| reviewer/approver | 审核人与批准人 |
| status | 当前治理状态 |
| executionEvidence | 执行、审计和回读关联 |
### 4.3 系统可自动完成

- 生成申请编号；
- 保存草稿；
- 校验必填字段和对象存在性；
- 读取 Before Snapshot；
- 生成差异与 Payload Hash；
- 防止同对象冲突申请并发执行；
- 记录状态转换。
### 4.4 必须人工完成

- 提出业务原因和目标结果；
- 确认影响处置方案；
- 审核正确性；
- 批准风险和生效时点；
- 对异常生效与回退作业务决定。
## 5. Impact Analysis（影响分析）能力

影响分析是只读分析证据，不是自动批准器或事实修复器。
| 影响对象 | 必查内容 | 可自动发现 | 禁止自动决定 |
|---|---|---|---|
| Company | 下属组织、岗位、员工、范围 | 引用与数量 | 合并迁移目标 |
| Organization Unit | 子节点、岗位、任职 | 循环、跨公司、依赖 | 新组织归属 |
| Position | 岗位责任、任职、上级岗位 | 当前/未来关系 | 责任或人员迁移 |
| Responsibility | BAC、岗位责任、流程责任 | 有效引用与状态 | 新责任语义 |
| PositionResponsibility | 空档、重叠、多候选 | 区间和候选冲突 | 选择责任人 |
| Employee Assignment | 原岗、新岗、兼岗、代理 | 时间重叠与责任缺口 | 替代员工 |
| BAC | `requiredResponsibility`、范围维度 | 引用清单 | 改动作契约 |
| Workflow | 节点/流程责任引用 | 引用清单 | 修改流程或任务 |
| RRE | 唯一、无候选、多候选风险 | 预测状态 | 自动修复或选人 |
影响快照必须绑定申请版本。拟议内容变化后，应重新分析并使旧审核/批准失效。
## 6. Review / Approval（审核 / 批准）能力

### 6.1 标准生命周期

`Draft（草稿）→ Submitted（已提交）→ Reviewed（已审核）→ Approved（已批准）→ Effective（已生效）→ Archived（已归档）`
辅助终态：Rejected（已拒绝）、Cancelled（已取消）、Expired（批准过期）、ExecutionFailed（执行失败）、Superseded（被替代）。
### 6.2 状态控制

| 转换 | 执行人 | 必要条件 |
|---|---|---|
| Draft → Submitted | 申请人/Data Steward | 内容、原因、日期完整 |
| Submitted → Reviewed | Reviewer | 影响分析完整，审核人独立 |
| Reviewed → Approved | Approver | 批准人独立，Payload 未变化 |
| Approved → Effective | 受权执行器 | 到达时间、授权通过、事实未漂移 |
| Effective → Archived | 系统/治理管理员 | 审计、回读和影响复核完成 |
### 6.3 职责分离

- Reviewer 检查事实、语义、时间、引用和影响分析是否正确。
- Approver 接受业务风险并批准变更和生效时间。
- 同一自然人不得同时完成 Submitted、Reviewed、Approved。
- Data Steward 维护过的申请不得由本人批准。
- 超级管理员、技术管理员身份不构成业务批准。
- 批准后任何拟议字段变化都必须回到 Submitted 并重新审核。
## 7. Effective Date（生效时间）能力

### 7.1 时间模型

所有时态关系采用：
时间区间：`[effective_from, effective_to)`。
`effective_from` 包含，`effective_to` 不包含。旧关系在 T 结束、新关系在 T 开始时不重叠。
### 7.2 未来生效

- Approved 仅表示允许在指定时点执行，不等于已经改变正式事实。
- 到时执行前必须重新核对 Payload Hash、Before Snapshot、引用有效性、授权和冲突申请。
- 任一条件漂移时不得执行，申请转为失败、过期或重新审核。
### 7.3 历史查询

- 可按业务时点查询当时有效的组织、岗位责任和任职关系。
- 记录 Business Effective Time（业务生效时间）和 System Recorded Time（系统记录时间）。
- 正式历史不得通过 UPDATE 覆盖；纠错使用新申请和更正证据。
## 8. 不同主数据的变更能力

### 8.1 Company（公司）

| 变更 | 能力 | 影响门禁 |
|---|---|---|
| 新增 | 主体创建申请 | 不自动建组织、岗位、责任、角色 |
| 修改 | 字段差异申请 | 编码/法定主体实质变化需高等级审核 |
| 停用 | 终止申请 | 阻断仍有有效下属事实的停用 |
| 合并 | 变更组合 | 人工确认存续主体与迁移清单 |
公司合并不得作为单一字段修改；每个迁移子步骤都要有审计和回退点。
### 8.2 Organization Unit（组织单元）

| 变更 | 能力 | 影响门禁 |
|---|---|---|
| 新建部门 | 组织创建申请 | 父级、公司、编码、循环校验 |
| 关系调整 | 父级/类型变更申请 | 分析岗位、员工、范围 |
| 合并 | 存续单元与迁移计划 | 保留原组织历史 |
| 停用 | 终止申请 | 处置子组织、岗位和任职 |
组织调整只提出依赖迁移建议，不自动修改岗位责任、Permission 或 Workflow。
### 8.3 Position（岗位）

| 变更 | 能力 | 影响门禁 |
|---|---|---|
| 创建 | 岗位创建申请 | 组织、岗位族、等级有效 |
| 修改 | 分类/归属差异申请 | 分析任职和岗位责任 |
| 停用/退役 | 终止申请 | 先处置未来任职和责任关系 |
岗位变化禁止自动创建 Responsibility、Role、Permission、审批人或 Workflow 执行人。
### 8.4 Responsibility（职责/责任定义）

责任采用最高治理等级。
| 变更 | 能力 | 影响门禁 |
|---|---|---|
| 创建 | 独立责任申请 | 编码、语义、重复和领域审核 |
| 修改 | 语义澄清申请 | 核心语义改变应新建并退役旧责任 |
| 暂停 | 暂停申请 | 检查 BAC 与岗位责任引用 |
| 退役 | 永久退役申请 | 先迁移或终止全部有效引用 |
页面、AI、RRE、Workflow、BAC 和岗位编辑均不得创建正式责任。
### 8.5 PositionResponsibility（岗位责任关系）

| 变更 | 能力 | 影响门禁 |
|---|---|---|
| 新增关系 | 关系申请 | 岗位、责任、公司范围有效 |
| 取消关系 | 有效期终止 | 不物理删除历史 |
| PRIMARY 调整 | 承担类型申请 | 检测重复主责和多候选 |
| SUPPORTING 调整 | 协助关系申请 | 不生成 Permission |
| 日期调整 | 时态区间申请 | 重叠、空档、回溯校验 |
PRIMARY 不是自动选人优先级；发现多候选只能报告冲突。
### 8.6 Employee Assignment（员工任职关系）

| 变更 | 能力 | 影响门禁 |
|---|---|---|
| 入职/入岗 | 新任职申请 | 员工、岗位、日期有效 |
| 调岗 | 旧任职结束 + 新任职建立 | 原子时点交接 |
| 晋升/降级 | 岗位/等级变更申请 | 不自动改责任和权限 |
| 离岗 | 任职结束申请 | 输出责任缺口，不自动找人 |
| 兼岗 | 第二任职申请 | 明确范围与有效期 |
| 代理 | 临时任职申请 | 明确被代理岗位和结束时间 |
员工变化只改变任职事实，不修改 BAC、Responsibility、PositionResponsibility、Role、Permission 或 Workflow。
## 9. OrganizationOperatingService 能力边界

设计结论：OrganizationOperatingService 应作为唯一组织事实执行入口。
未来允许：

- 接收已批准且到达生效时点的申请；
- 验证申请状态和 Payload Hash；
- 调用 AuthorizationService 再校验执行人；
- 校验当前事实未偏离 Before Snapshot；
- 在事务中写正式事实和 OrganizationOperatingAuditRecord；
- 返回服务端回读结果。
未来禁止：

- 代替 Data Owner 定义变更；
- 自动审核或批准申请；
- 接受页面绕过申请直接写正式事实；
- 允许 Workflow、RRE 或 AI 直接写组织事实；
- 根据岗位名、员工名、Role 或 Permission 自动生成 Responsibility；
- 在申请失败时留下部分写入。
目标执行链：
目标执行链：`Approved Change Request → Effective-Time Revalidation → AuthorizationService → OrganizationOperatingService → Formal Fact + Audit → Server Readback`。
## 10. Audit（审计）能力

每次状态转换和正式生效必须记录：
| 证据 | 内容 |
|---|---|
| Before | 变更前正式事实 |
| After | 获批且实际保存的事实 |
| Requester | 申请人和时间 |
| Operator | 实际执行人和时间 |
| Reviewer | 审核人、意见、时间 |
| Approver | 批准人、条件、时间 |
| Effective Time | 计划和实际生效时间 |
| Reason | 业务原因 |
| Impact Snapshot | 影响对象、风险和处置 |
| Payload Hash | 获批内容摘要 |
| Authorization | 动作、Permission、Scope、裁决 |
| Readback | 保存后正式事实摘要 |
现有 OrganizationOperatingAuditRecord 可继续作为正式事实写入审计源；Change Request 状态与审核批准证据如何持久化，需 OOM-4 独立决定，禁止本轮直接新增 V2 审计表。
审计成功条件：事务提交、审计记录、服务端回读和影响复核全部通过。任一失败都不能显示 Effective。
## 11. 自动化边界矩阵

| 能力 | 允许自动化 | 禁止自动化 |
|---|---|---|
| 申请 | 编号、草稿、字段检查 | 自动提出业务理由 |
| 影响分析 | 引用、时态、冲突扫描 | 自动接受风险 |
| 审核 | 身份冲突与完整性门禁 | 自动审核通过 |
| 批准 | 状态和签名验证 | 自动批准业务变更 |
| 生效 | 到时复核与事务执行 | 执行漂移或未批准内容 |
| 责任治理 | 重码与引用检查 | 创建/修改责任语义 |
| 岗位责任 | 多候选/空档检测 | 自动选择责任人 |
| 任职 | 区间校验、原子调岗 | 自动指定岗位或替代人 |
| 回退 | 生成反向申请草稿 | 删除历史或静默恢复 |
## 12. OOM-4 前置条件

进入 Organization Model Implementation（组织模型实施）前必须完成：

1. Change Request 独立对象的人工架构批准；
2. 状态机、异常状态和状态转换权限冻结；
3. `[effective_from, effective_to)` 时态规则冻结；
4. 影响分析输入、输出、版本绑定和失败门禁冻结；
5. 自然人级申请/审核/批准隔离规则冻结；
6. Payload Hash、Before Snapshot 和并发漂移策略冻结；
7. OrganizationOperatingService 唯一事实执行入口确认；
8. Change Request、审批证据与现有审计的最小 Schema 决策；
9. 页面从即时保存到申请式维护的兼容设计；
10. 失败、过期、替代、回退和归档验收设计；
11. BAC、Workflow、RRE 只读引用边界继续保持；
12. Migration、API、页面和数据初始化分别取得新授权。
## 13. 保护确认

本任务只新增本设计报告。没有修复 OOM-3.3.1 归档内容，也没有生成 OOM-3.3.3 或 OOM-3.3.4。
`Documentation Changed = YES`。  
`Code Changed = NO`；`Database Changed = NO`；`Migration Created = NO`；`API Created = NO`。  
`Organization Data Changed = NO`；`Responsibility Data Changed = NO`；`Employee Data Changed = NO`。  
`Permission Model Changed = NO`；`Workflow Runtime Changed = NO`；`ApprovalTask Changed = NO`。  
`RRE Started = NO`；`Unauthorized Business Writes = 0`。
## 14. 最终状态

`OOM-3.3.2 Governance Capability Boundary Design = COMPLETE`。  
`OOM-3.3.3 = NOT STARTED`；`OOM-3.3.4 = NOT STARTED`。  
`Organization Model Implementation = NOT AUTHORIZED`；`RRE-1 = NOT AUTHORIZED`；`Workflow Integration = NOT AUTHORIZED`。
本报告完成后停止，等待下一步指令。
