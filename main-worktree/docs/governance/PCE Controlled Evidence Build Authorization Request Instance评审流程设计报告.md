# PCE Controlled Evidence Build Authorization Request Instance（受控证据构建授权申请实例）评审流程设计报告

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 系统 | PCE（ProfitOS / Dev-PCE） |
| 阶段 | Controlled Evidence Build Authorization Preparation（受控证据构建授权准备阶段） |
| 类型 | Design Only（仅设计） |
| 日期 | 2026-08-19 |
| Review Level（审查等级） | B（重点审查） |
| Full Content Review Required（是否强制全文审查） | NO |
| 设计对象 | 未来 Request Instance 的评审、意见、裁决和状态流转 |
| 当前申请实例 | NOT CREATED |
| 当前审核记录 | NOT CREATED |
| 当前授权 | NOT GRANTED |
| 当前执行 | NOT STARTED |
## 2. 设计目标与边界

本报告设计一个已通过 Request Validation（申请验证）的 Request Instance，未来如何被独立提交、完成专业评审、处理意见并形成申请裁决。

本报告不创建真实申请、审核记录、裁决记录、Authorization Manifest（授权清单）或 Authorization（授权），不执行 Controlled Evidence Build（受控证据构建）。

评审流程只回答申请是否可批准形成 Manifest；它不回答执行是否已激活，也不改变任何 Gate（门禁）状态。
## 3. Preflight（执行前检查）

```text
Context Scope = CONTROLLED
Input Files = 5
Task Scope = SINGLE
Review Level = B
Full Content Review Required = NO
Review Record Creation = NO
Authorization = NOT GRANTED
Execution = NOT STARTED
```

输入文件均存在且不超过 6 个；没有读取无关历史文件；报告目标为 200–400 行。
## 4. 已读取基线与判断依据
### 4.1 CODEX 核心规范

路径：`D:\Dev-PCE\Source\docs\governance\PCE CODEX开发指令规范管理V1.2.md`

用途：确认风险分级、上下文控制、单任务、完整归档回读和阶段分离。

关键原文：

> 核心治理规范升级至少为 Level B，不得因“只修改文档”降为 Level A。

判断：本任务涉及授权治理流程，采用 Level B，但不要求在回复中重复全文。
### 4.2 Controlled Evidence Build 授权评审基线

路径：`D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 Controlled Evidence Build Authorization评审与授权申请设计报告.md`

用途：确认评审角色、状态、裁决、暂停、关闭及 Request/Authorization 分离。

关键原文：

> APPROVED 只表示申请通过评审，可生成批准版授权清单。 APPROVED 不表示证据构建已经 ACTIVE（执行中）。

判断：申请裁决为 APPROVED 时仍不得进入执行。
### 4.3 Request Template（授权申请模板）

路径：`D:\Dev-PCE\Source\docs\governance\PCE Controlled Evidence Build Authorization Request Template设计报告.md`

用途：确认申请字段、审核检查清单和裁决占位边界。

关键原文：

> 模板警告：未完成全部审核和正式签发时，本区必须保持空白，Authorization = NOT GRANTED。

判断：评审未完成时不得预填批准结论或 Manifest 标识。
### 4.4 Request Instance 创建准备设计

路径：`D:\Dev-PCE\Source\docs\governance\PCE Controlled Evidence Build Authorization Request Instance创建准备设计报告.md`

用途：确认生命周期、版本、归档以及 Request 与 Manifest 边界。

关键原文：

> 禁止 `Request APPROVED = Authorization ACTIVE`，禁止由 Request 字段直接驱动执行器。

判断：评审流程不能直接调用执行器或生成 ACTIVE 状态。
### 4.5 Request Instance 验证规则

路径：`D:\Dev-PCE\Source\docs\governance\PCE Controlled Evidence Build Authorization Request Instance验证规则设计报告.md`

用途：确认 READY_FOR_REVIEW、BLOCKED、REJECTED 和重验规则。

关键原文：

> `READY_FOR_REVIEW` 只是一项只读资格结论，不自动把 Request 状态改为 SUBMITTED 或 REVIEWING。状态迁移必须由未来独立提交动作完成。

判断：本流程从未来独立提交动作开始，不由验证结果自动触发。
## 5. Review Entry Gate（评审入口门禁）
### 5.1 进入条件

未来 Request 只有同时满足以下条件才可从 DRAFT 进入 SUBMITTED：

- 最新验证结果为 READY_FOR_REVIEW，且 rule_set_version 仍有效；
- request_id、request_version 与 input_sha256 精确匹配；
- Request Owner 明确执行提交动作；所有必需附件仍可访问且摘要一致；
- 专业审核角色已实名并通过职责冲突检查；
- 未创建 Manifest、授权记录、审批任务或执行状态。
### 5.2 禁止自动进入

验证器、页面加载、定时任务、管理员身份或历史申请均不得自动触发 SUBMITTED。提交必须形成独立、可审计的未来动作。
### 5.3 入口失败

| 条件 | 结果 |
|---|---|
| 验证过期或摘要漂移 | BLOCKED，重新验证 |
| 申请版本发生实质变化 | BLOCKED，创建新版本 |
| 出现永久禁止范围 | REJECTED |
| 审核角色冲突 | BLOCKED |
## 6. Review Lifecycle（评审生命周期）

```text
SUBMITTED
↓
COMPLETENESS_REVIEW
↓
ARCHITECTURE_REVIEW
↓
SECURITY_REVIEW
↓
DATA_REVIEW
↓
TECHNICAL_REVIEW
↓
EVIDENCE_REVIEW
↓
DECISION_PENDING
↓
APPROVED / BLOCKED / REJECTED
↓
CLOSED
```
### 6.1 状态所有权

状态由未来评审服务依据签发结果推进；页面只能提交动作和显示服务端状态，不能自行改状态。
### 6.2 串行与并行

Completeness Review 必须最先完成；Architecture Review 必须在最终安全、数据和技术签发前通过。Security、Data、Technical 可在架构初审通过后并行，但生命周期仍统一显示 REVIEWING。Evidence Review 必须使用冻结后的最终范围和其他专业结论。
### 6.3 终态边界

APPROVED、BLOCKED、REJECTED 是 Request 裁决结果；SUSPENDED、REVOKED、ACTIVE 属于后续 Authorization 生命周期，不能写入 Request 状态。
## 7. Reviewer（审核角色）职责

| 角色 | 职责 | 必须输出 | 禁止 |
|---|---|---|---|
| Request Owner | 提交真实完整的申请并响应 findings | 补正说明、版本变更原因 | 审批自己的申请 |
| Completeness Reviewer | 检查字段、附件、六维范围 | 完整性结论 | 代替专业审核 |
| Architecture Reviewer | 检查 BAC/OOM、事实源、权限和运行边界 | 架构意见 | 批准平行事实源 |
| Security Reviewer | 检查环境、网络、凭据、日志和停止能力 | 安全意见 | 接受生产写端点 |
| Data Reviewer | 检查来源、分类、脱敏、保留和销毁 | 数据意见 | 放行来源不明数据 |
| Technical Reviewer | 检查可行性、测试、写入预算和回退 | 技术意见 | 自证自己的全部实现 |
| Evidence Reviewer | 检查输出、原始日志、摘要和归档 | 证据意见 | 删除失败或反对证据 |
| Authorization Owner | 汇总有效审核并作 Request 裁决 | Decision Record | 跳过必需审核 |
### 7.1 职责分离

Request Owner 不得担任 Authorization Owner；Executor 不得担任唯一 Technical Reviewer 或 Evidence Reviewer；环境搭建人不得担任唯一 Security Reviewer；数据准备人不得担任唯一 Data Reviewer。

共享账号、超级管理员和无有效期限的代理人不能满足自然人职责分离。
## 8. Review Record（评审记录）设计

每个专业评审未来应形成独立记录，不得直接覆盖 Request 正文。

| 字段 | 说明 |
|---|---|
| review_id | 唯一评审记录标识 |
| review_type | COMPLETENESS / ARCHITECTURE / SECURITY / DATA / TECHNICAL / EVIDENCE |
| request_id / version | 精确申请版本 |
| input_sha256 | 被审核快照摘要 |
| reviewer | 实名自然人及账户 |
| started_at / completed_at | 服务端时间 |
| conclusion | PASS / BLOCKED / REJECTED |
| findings | Finding 引用列表 |
| evidence_refs | 依据文件和摘要 |
| signature_ref | 审核签发引用 |

本轮不创建任何 review_id 或 Review Record。
## 9. Review Findings（评审发现）设计
### 9.1 Finding 字段

| 字段 | 说明 |
|---|---|
| finding_id | 唯一标识；本轮不创建实例 |
| review_type | 来源审核类型 |
| severity | P0 / P1 / P2 / P3 |
| description | 可验证的问题描述 |
| evidence | 文件、日志、规则或摘要引用 |
| owner | 具名处理责任人 |
| due_date | 截止时间 |
| status | OPEN / FIXING / RESOLVED / REJECTED |
| resolution_evidence | 解决证据及摘要 |
### 9.2 严重度

| 严重度 | 含义 | 裁决影响 |
|---|---|---|
| P0 | 生产、正式数据、授权或安全越界 | REJECTED；不得补丁式放行 |
| P1 | 关键隔离、回退、来源或职责冲突 | BLOCKED，关闭前不得批准 |
| P2 | 重要完整性或技术缺口 | BLOCKED 或带条件退回 |
| P3 | 不影响合法性的改进项 | 可记录后进入裁决 |
### 9.3 Finding 状态流转

```text
OPEN
↓
FIXING
↓
RESOLVED / REJECTED
```

RESOLVED 必须附解决证据并由原审核人或授权替补复核；Request Owner 不能自行关闭自己的 finding。
### 9.4 申请变化

处理 finding 导致环境、数据、repository、commit、人员、活动、时间或风险实质变化时，必须生成新 Request 版本、重新验证并使受影响审核失效。
## 10. 分阶段审核门槛
### 10.1 Completeness Review

检查必填字段、六维范围、控制计划、附件、版本和摘要。缺失可补正信息为 BLOCKED；目标含禁止事项为 REJECTED。
### 10.2 Architecture Review

检查 BAC/OOM 唯一事实源、Responsibility/Permission 边界、Workflow/RRE 边界及无平行模型。任何架构越界为 REJECTED。
### 10.3 Security Review

检查非生产环境、生产不可达、短期最小权限凭据、网络白名单、日志、审计和紧急停止。生产密钥或写端点为 REJECTED。
### 10.4 Data Review

检查数据来源、Data Custodian、分类、脱敏、数量、命名空间、保留和销毁。来源不明且无法合法化为 REJECTED。
### 10.5 Technical Review

检查候选方案、测试范围、写入预算、幂等性、恢复和回退。无法回退或存在正式业务副作用为 REJECTED。
### 10.6 Evidence Review

检查 Evidence Question 与输出映射、原始日志、失败证据、保存位置、SHA256 和独立复核。只保留结论而无原始证据为 REJECTED。
## 11. Decision Readiness（裁决就绪）

只有以下条件全部满足，Request 才能进入 DECISION_PENDING：

- 所有必需专业审核已完成并绑定同一 request_version 与 input_sha256；
- 没有 OPEN/FIXING 的 P0、P1 或 P2 finding；没有任何专业审核为 REJECTED；
- P3 finding 已记录责任人、期限和不阻断依据；职责分离仍有效；
- 最新 Request 快照、审核记录和证据摘要一致；
- Authorization Owner 已实名但尚未预填裁决结果。

任一条件不满足时保持 REVIEWING 或转为 BLOCKED，不得进入裁决。
## 12. Decision（裁决）设计
### 12.1 APPROVED

条件：所有必需审核 PASS，关键 findings 已关闭，申请范围冻结且无禁止事项。

效果：只允许进入独立 Authorization Manifest 准备与签发流程。不得创建 ACTIVE、不得启动执行、不得改变 Gate。
### 12.2 BLOCKED

适用：目标可能合规，但缺少可补正材料、签发、隔离证明、数据批准、回退或人员条件。

效果：记录阻断项和补正期限；补正后按版本和重审规则返回相应审核节点。
### 12.3 REJECTED

适用：包含生产写入、正式数据切换、正式 Migration、生产凭据、来源不明数据、不可回退、Workflow/RRE 启用或其他永久边界违规。

效果：记录拒绝原因、依据和是否允许重新申请；不得生成 Manifest。
### 12.4 Decision Record（裁决记录）

未来裁决记录至少包含 decision_id、request_id/version、input_sha256、decision、reason、审核结论索引、未关闭 P3、Authorization Owner、时间、签名引用和 SHA256。

本轮不创建 Decision Record，不填写 APPROVED、BLOCKED 或 REJECTED 实例结论。
## 13. 状态流转规则

| 当前状态 | 允许目标 | 前置条件 |
|---|---|---|
| DRAFT | SUBMITTED | READY_FOR_REVIEW + 独立提交动作 |
| SUBMITTED | COMPLETENESS_REVIEW | 快照冻结、摘要一致 |
| 任一 REVIEW | 下一审核 / BLOCKED / REJECTED | 当前审核已签发 |
| EVIDENCE_REVIEW | DECISION_PENDING | 全部审核和 findings 门禁通过 |
| DECISION_PENDING | APPROVED / BLOCKED / REJECTED | Authorization Owner 裁决 |
| APPROVED / BLOCKED / REJECTED | CLOSED | 归档和关闭条件满足 |

禁止跳过节点；禁止页面直接写状态；禁止 APPROVED 自动进入 AUTHORIZED 或 ACTIVE。
## 14. 版本变化与重审

实质变化必须递增 request_version 并重新执行 Request Validation。旧 Review Record 保留但对新版本失效。

仅影响某一专业域的变化至少重做该域审核和 Evidence Review；影响目标、范围、事实边界或职责分离时，从 Architecture Review 重新开始。

input_sha256 变化但 request_version 未变化时立即 BLOCKED，并记录不可变快照违规。
## 15. 与 Gate（门禁）的关系

| Gate | 评审可支持 | 不能替代 |
|---|---|---|
| Gate-2 Data | 判断数据结构、质量和候选 Migration 证据计划是否可评审 | 正式 Migration、数据签发和生产迁移 |
| Gate-4 Technical | 判断服务、页面、测试、恢复和回退证据计划是否可评审 | 生产发布和上线运行证据 |
| Gate-3 Governance | 检查本申请职责分离 | 实名治理任命和治理签发 |
| Gate-5 Business | 检查非生产验证计划 | 业务确认、人工验收和上线窗口 |

Request APPROVED 不自动改变 Gate 状态；Gate 只能通过独立 Gate Reassessment（门禁重新评估）变更。
## 16. Human Validation（人工验证）时间点
### 16.1 当前准备阶段

只进行设计审查：确认评审流程、角色、findings、裁决和状态边界是否完整。不运行系统或创建记录。
### 16.2 Controlled Evidence Build 阶段

只有未来获得独立授权后，才可在隔离环境由实名人员验证审核控制、页面流程、权限拒绝、证据生成和停止能力。
### 16.3 正式实施后

业务人工验收只能在正式实施另行授权并完成后执行，验证真实业务范围、正式数据、用户操作和运行结果。

三个时间点的证据、结论和签发人不得互相替代。
## 17. Audit & Archive（审计与归档）

未来归档必须包含 Request 各版本、验证结果、所有 Review Record、findings 全生命周期、Decision Record、签名引用、状态迁移日志和各文件 SHA256。

所有记录只能追加；拒绝意见、失败证据和旧版本不得删除。审核更正必须创建新记录并引用原记录。

归档索引必须能从 request_id/version 追溯输入摘要、审核人、findings、裁决和关闭结果。

本轮不创建任何审计或归档实例。
## 18. 设计验证场景

| 编号 | 场景 | 预期结果 |
|---|---|---|
| RRP-T01 | READY_FOR_REVIEW 后无提交动作 | 保持 DRAFT |
| RRP-T02 | Request Owner 自批 | BLOCKED |
| RRP-T03 | Completeness 未通过进入架构审核 | 拒绝跳转 |
| RRP-T04 | Security 发现生产写端点 | REJECTED |
| RRP-T05 | P1 finding 仍 OPEN | 不得 DECISION_PENDING |
| RRP-T06 | 解决 finding 后修改 commit | 新版本、重验、重审 |
| RRP-T07 | 全部审核 PASS | 可进入 DECISION_PENDING |
| RRP-T08 | APPROVED 后自动 ACTIVE | 拒绝自动迁移 |
| RRP-T09 | 技术审核替代 Gate-3 | 拒绝 |
| RRP-T10 | 删除拒绝意见 | 审计失败并 BLOCKED |
| RRP-T11 | 隔离验证代替业务验收 | 拒绝 |
| RRP-T12 | input_sha256 漂移 | BLOCKED |

这些场景仅为未来验证设计，本轮不执行。
## 19. 风险与控制

| 风险 | 影响 | 控制 |
|---|---|---|
| 验证通过自动提交 | 绕过申请人意愿 | 独立提交动作 |
| 申请人自审自批 | 治理失效 | 自然人职责分离 |
| finding 被口头关闭 | 证据不可追溯 | 解决证据和复核签发 |
| 变更范围但复用审核 | 错误裁决 | 版本失效和重审 |
| APPROVED 被误作 ACTIVE | 未授权执行 | Request/Manifest/Authorization 状态分离 |
| 技术评审替代业务验收 | Gate 绕过 | 三类人工验证时间点分离 |
| 拒绝证据被删除 | 审计失真 | 追加式只读归档 |
## 20. 本轮保护状态

```text
Documentation Changed = YES
Code Changed = NO
Database Changed = NO
Migration Created = NO
API Created = NO
Page Created = NO
Organization Data Changed = NO
Responsibility Data Changed = NO
Employee Data Changed = NO
Permission Model Changed = NO
Workflow Runtime Changed = NO
ApprovalTask Changed = NO
RRE Started = NO
Unauthorized Business Writes = 0
```

本轮未创建申请、审核、finding、裁决、Manifest、授权或执行记录。
## 21. 最终状态

```text
Controlled Evidence Build Authorization Request Instance Review Process Design = COMPLETE
Authorization Request Instance = NOT CREATED
Review Record Instance = NOT CREATED
Finding Instance = NOT CREATED
Decision Record Instance = NOT CREATED
Authorization Manifest Instance = NOT CREATED
Controlled Evidence Build Authorization = NOT GRANTED
Controlled Evidence Build Execution = NOT STARTED
OOM-4.2 Implementation Authorization Review = NOT STARTED
Organization Model Implementation = NOT AUTHORIZED
RRE-1 = NOT AUTHORIZED
Workflow Integration = NOT AUTHORIZED
Context Scope = CONTROLLED
Input Files = 5
Task Scope = SINGLE
Review Level = B
Full Content Review Required = NO
Documentation Archived = YES
Archive Content Readback = YES
ChatGPT Reviewable = YES
Source Excerpts Verified = YES
```

本报告完成后立即停止，等待人工审查；不得提交真实申请、创建审核或裁决记录、生成 Manifest、批准授权或启动受控证据构建。
