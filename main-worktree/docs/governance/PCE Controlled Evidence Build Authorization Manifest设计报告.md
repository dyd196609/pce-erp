# PCE Controlled Evidence Build Authorization Manifest（受控证据构建授权清单）设计报告

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 系统 | PCE（ProfitOS / Dev-PCE） |
| 阶段 | Controlled Evidence Build Authorization Preparation（受控证据构建授权准备阶段） |
| 类型 | Design Only（仅设计） |
| 日期 | 2026-08-19 |
| Review Level（审查等级） | B（重点审查） |
| Full Content Review Required（是否强制全文审查） | NO |
| 设计对象 | 未来 Authorization Manifest 的结构、边界、生成、签发和生命周期 |
| 当前 Manifest 实例 | NOT CREATED |
| 当前授权 | NOT GRANTED |
| 当前执行 | NOT STARTED |
## 2. 设计目标与非目标

本报告设计未来一个 Request（授权申请）通过专业评审并获得 APPROVED 后，如何形成明确、最小范围、可审计且不可误解的 Authorization Manifest（授权清单）。

Manifest 固化被批准的时间、环境、文件、数据、人员和活动。它不能自行批准执行，也不能把签名、审核通过或 Gate 证据转化为 ACTIVE。

本报告不创建 manifest_id、Manifest Instance、签名、Authorization、执行记录、Migration、API、页面或业务数据。
## 3. Preflight（执行前检查）

```text
Context Scope = CONTROLLED
Input Files = 6
Task Scope = SINGLE
Review Level = B
Full Content Review Required = NO
Manifest Instance Creation = NO
Authorization = NOT GRANTED
Execution = NOT STARTED
```

输入文件不超过 6 个；没有读取无关历史文件；目标报告控制在 300–500 行。
## 4. 已读取基线与判断依据
### 4.1 CODEX 核心规范

路径：`D:\Dev-PCE\Source\docs\governance\PCE CODEX开发指令规范管理V1.2.md`

用途：确认风险分级、最小上下文、阶段分离、归档回读和保护要求。

关键原文：

> 核心治理规范升级至少为 Level B，不得因“只修改文档”降为 Level A。

判断：本任务涉及授权边界设计，采用 Level B，但不要求在回复中重复全文。
### 4.2 Controlled Evidence Build 授权设计

路径：`D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 Controlled Evidence Build Authorization设计报告.md`

用途：确认 Manifest 最小字段、六维范围、默认禁止、隔离和生命周期。

关键原文：

> 任何未列入清单的活动默认禁止。 授权过期后不得继续构建或写入。

判断：Manifest 必须是显式白名单，缺失不能解释为允许。
### 4.3 授权评审与申请设计

路径：`D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 Controlled Evidence Build Authorization评审与授权申请设计报告.md`

用途：确认 Request、Decision、Manifest、Authorization 和执行状态边界。

关键原文：

> APPROVED 只表示申请通过评审，可生成批准版授权清单。 APPROVED 不表示证据构建已经 ACTIVE（执行中）。

判断：Request APPROVED 只提供生成前置条件，不自动创建或激活 Manifest。
### 4.4 Request Template（申请模板）

路径：`D:\Dev-PCE\Source\docs\governance\PCE Controlled Evidence Build Authorization Request Template设计报告.md`

用途：确认六维范围、写入预算、停止、回退、清理和证据输出字段。

关键原文：

> Time、Environment、Files、Data、People、Activities 六个维度都必须明确；未列入范围默认禁止。

判断：Manifest 必须将申请字段转换为可执行、不可歧义的批准范围。
### 4.5 Request Instance 创建准备设计

路径：`D:\Dev-PCE\Source\docs\governance\PCE Controlled Evidence Build Authorization Request Instance创建准备设计报告.md`

关键原文：

> Request 回答“为什么需要构建证据、希望证明什么”；Manifest 回答“批准哪些具体范围可以执行”。Request APPROVED 不自动创建 Manifest，更不自动启动执行。

判断：Manifest 不重复定义申请理由，而是固化裁决后的允许范围。
### 4.6 Request Instance 评审流程设计

路径：`D:\Dev-PCE\Source\docs\governance\PCE Controlled Evidence Build Authorization Request Instance评审流程设计报告.md`

关键原文：

> 效果：只允许进入独立 Authorization Manifest 准备与签发流程。不得创建 ACTIVE、不得启动执行、不得改变 Gate。

判断：本设计位于 Request APPROVED 之后、Manifest 实例创建和授权签发之前。
## 5. Manifest 定义与语义边界
### 5.1 Request（申请）

回答“为什么需要构建证据、希望证明什么”，承载目标、理由和候选范围。
### 5.2 Decision（裁决）

回答“申请是否被 APPROVED、BLOCKED 或 REJECTED”，并记录裁决依据。
### 5.3 Manifest（授权清单）

回答“在批准后，具体允许谁、何时、何地、对哪些文件和数据执行哪些活动，以及如何停止、回退和留证”。
### 5.4 Authorization（授权）

回答“该 Manifest 是否已经被正式批准用于未来执行”。Manifest 存在或 SIGNED 不自动等于授权已生效。
### 5.5 Active（当前可执行）

回答“当前时间点是否同时满足授权有效、执行前检查通过、未暂停或撤销”。只有后续 Authorization 状态为 ACTIVE 才可能执行。

禁止关系：

```text
Request APPROVED ≠ Manifest SIGNED
Manifest SIGNED ≠ Authorization AUTHORIZED
Authorization AUTHORIZED ≠ ACTIVE
ACTIVE ≠ Gate PASS
```
## 6. 双状态生命周期设计

为避免 Manifest 文档状态与执行授权状态混淆，采用两个独立状态轴。
### 6.1 Manifest Document Lifecycle（清单文档生命周期）

```text
NOT_CREATED
↓
DRAFT
↓
REVIEWED
↓
SIGNED
↓
SUPERSEDED / CLOSED
```
### 6.2 Authorization Lifecycle（授权生命周期）

```text
NOT_GRANTED
↓
AUTHORIZED
↓
READY_CHECK
↓
ACTIVE
↓
SUSPENDED / COMPLETE / FAILED / REVOKED
↓
CLOSED
```
### 6.3 聚合展示

用户要求的 `NOT_CREATED → DRAFT → REVIEWED → SIGNED → ACTIVE → ... → CLOSED` 可以作为聚合视图，但服务端事实必须保留双状态，不允许 `SIGNED → ACTIVE` 自动迁移。
### 6.4 本轮状态

本报告不创建任何状态实例；当前保持 Manifest `NOT_CREATED`、Authorization `NOT_GRANTED`、Execution `NOT_STARTED`。
## 7. Manifest Identity（清单身份）字段

| 字段 | 说明 | 规则 |
|---|---|---|
| manifest_id | 清单唯一标识 | 未来由权威编号器产生；本轮不创建 |
| manifest_version | 清单版本 | 正整数递增，不得覆盖 |
| linked_request_id | 来源 Request | 必须存在且为 APPROVED |
| request_version | 来源申请版本 | 与裁决精确一致 |
| request_sha256 | 来源申请摘要 | 摘要漂移即阻断 |
| decision_id | 来源裁决 | 必须为 APPROVED |
| decision_sha256 | 裁决摘要 | 不得缺失 |
| template_version | Manifest 模板版本 | 创建时冻结 |
| created_by / time | 创建主体与服务端时间 | 必须审计 |
| reviewed_by / time | 清单审核主体与时间 | 职责分离 |
| signed_by / time | 签发主体与时间 | 不得由执行人代签 |
| signature_reference | 签名引用 | 可验证且不可复用 |
| manifest_sha256 | 规范化正文摘要 | 签发后不可变 |
## 8. Objective（目标）与证据映射字段

| 字段 | 规则 |
|---|---|
| objective | 继承已批准目标，不得扩大 |
| target_gates | 仅 Gate-2、Gate-4 或批准子项 |
| evidence_questions | 每项可验证、可失败 |
| expected_outputs | 文件、日志、摘要或结构化结果 |
| success_criteria | 客观阈值，不承诺 Gate PASS |
| failure_result | FAILED / BLOCKED |
| evidence_location | 只读归档位置 |
| evidence_owner | 具名保管人 |

Manifest 可以比 Request 更窄，不得比已批准 Request 和 Decision 更宽。
## 9. Six-Dimension Authorization Scope（六维授权范围）
### 9.1 Time（时间）

| 字段 | 规则 |
|---|---|
| authorized_from | 不早于签发和 READY_CHECK 完成时间 |
| expires_at | 必填；到期自动失效 |
| maximum_duration | 不得开放式延期 |
| allowed_windows | 明确日期和时段 |
| expiry_action | STOP、撤销凭据并阻止新写入 |

延期必须生成新版本并重新评审、签发和授权。
### 9.2 Environment（环境）

| 字段 | 规则 |
|---|---|
| environment_id | 唯一、非生产、显著标识 |
| database_id | 独立或可证明隔离 |
| endpoint_allowlist | 只允许显式非生产端点 |
| network_policy | 默认拒绝 |
| production_reachability | 固定为 DENIED |
| credential_profile | 非生产、短期、最小权限 |
| environment_owner | 具名自然人 |
| disposal_method | 销毁、冻结或重建 |

生产环境、生产数据库、生产密钥、证书、令牌和写端点永久禁止。
### 9.3 Files（文件）

| 字段 | 规则 |
|---|---|
| repository | 唯一仓库 |
| branch | 候选分支，不自动合并 |
| commit | 固定不可歧义提交 |
| allowed_paths | 文件或目录白名单 |
| prohibited_paths | 生产和范围外路径 |
| candidate_artifacts | 逐项列出 |
| merge_policy | 固定 `NO_AUTO_MERGE` |

未列入路径默认禁止；commit 漂移必须立即停止。
### 9.4 Data（数据）

| 字段 | 规则 |
|---|---|
| source_type | SYNTHETIC / MASKED / AUTHORIZED_READONLY_COPY |
| source | 可追溯且获批 |
| data_custodian | 具名自然人 |
| classification | 明确敏感等级 |
| masking_rule | 非合成数据必填 |
| permitted_objects | 对象白名单 |
| record_limit | 最大处理和写入数量 |
| test_namespace | 与正式事实隔离 |
| retention | 明确保留期限 |
| destruction | 清理方法和证据 |

来源不明数据、生产回写及把测试数据提升为正式事实永久禁止。
### 9.5 People（人员）

| 角色 | 职责 | 冲突限制 |
|---|---|---|
| Request Owner | 来源申请负责人 | 不得批准自己的申请 |
| Authorization Owner | 授权裁决和范围负责人 | 不得是唯一执行人 |
| Execution Lead | 未来按清单组织执行 | 不得修改范围 |
| Architecture Reviewer | 检查架构边界 | 不得批准越界 |
| Security Reviewer | 检查环境和凭据 | 不得是唯一环境搭建人 |
| Data Custodian | 检查数据来源 | 不得批准来源不明数据 |
| Technical Reviewer | 检查测试和回退 | 不得自证全部执行结果 |
| Evidence Reviewer | 独立复核证据 | 不得删除失败记录 |
| Stop Authority | 暂停和紧急停止 | 必须即时可联系 |

所有角色必须是具名自然人；共享账号和超级管理员不能替代职责分离。
### 9.6 Activities（活动）

允许活动必须逐项包含 activity_id、动作、对象、环境、写入预算、预期证据和负责人。

可申请范围包括隔离环境中的 Schema Validation、Candidate Migration Rehearsal、Service/API/UI Validation、Automated Test、Rollback Rehearsal、Performance Test 和 Security Test。

永久禁止：生产部署、生产数据库写入、正式 Migration、正式数据导入、业务状态切换、外部生产副作用、Workflow 启用、ApprovalTask 创建和 RRE 启动。
## 10. Write Budget（写入预算）

| 字段 | 规则 |
|---|---|
| writes_allowed | YES/NO；仅隔离测试可为 YES |
| allowed_object_types | 对象白名单 |
| maximum_total_writes | 非负整数上限 |
| per_activity_limit | 每项活动上限 |
| test_namespace | 所有测试写入必须命中 |
| monitoring_source | 服务端计数或审计来源 |
| cleanup_required | 固定 YES |
| cleanup_owner | 具名负责人 |
| unauthorized_business_writes | 固定 0 |

达到预算上限必须停止新写入并进入 SUSPENDED；任何命名空间外写入必须 REVOKED 并保全证据。
## 11. Stop Conditions（停止条件）

Manifest 必须把以下条件定义为立即停止：

- 文件、数据、环境、人员或活动超出白名单；发现生产端点、凭据、证书或写权限；
- commit、Manifest SHA256、环境或数据摘要漂移；日志、审计、监控或证据采集不可用；
- 写入预算超限或测试命名空间外产生对象；数据来源或分类变化；
- 回退无法执行、安全风险达到阈值、授权到期或 Stop Authority 指令停止。

可调查且未形成永久违规时进入 SUSPENDED；生产连接、未授权业务写入、证据篡改或重大安全越界进入 REVOKED。
## 12. Rollback & Cleanup（回退与清理）
### 12.1 Rollback 字段

| 字段 | 说明 |
|---|---|
| rollback_plan | 有序步骤和触发条件 |
| recovery_point | 基线快照或可重建点 |
| rollback_owner | 具名负责人 |
| maximum_recovery_time | RTO |
| validation_after_rollback | 数量、Schema 和摘要比对 |
| failure_escalation | 失败后的停止与升级路径 |
### 12.2 Cleanup 字段

必须覆盖测试数据、临时凭据、网络白名单、候选环境、候选制品、日志和证据。清理失败不得 CLOSED。

回退只能恢复隔离环境，不得回写、修复或改变生产事实。
## 13. Evidence Output（证据输出）

最低输出：

- 授权清单、环境清单、源提交、候选变更和候选 Migration 摘要；
- 测试结果、原始日志、错误与失败记录、权限拒绝和安全隔离结果；
- Schema、数据对象数量、数据来源和环境摘要；
- 回退、恢复、清理、凭据撤销和残留检查记录；
- 每个文件的生成者、时间、来源版本、保存位置和 SHA256；
- Evidence Reviewer 的独立复核和整体证据包 SHA256。

摘要不能替代原始日志，失败结果不得删除。
## 14. Manifest Generation（生成规则）
### 14.1 生成前置条件

- linked Request 精确版本为 APPROVED；Decision Record、Request 和审核摘要一致；
- 所有 P0/P1/P2 findings 已关闭；P3 有责任人和不阻断依据；
- 六维范围已冻结并通过职责分离；没有现存同版本 Manifest；
- Manifest 生成动作获得未来独立权限和审计支持。
### 14.2 生成方式

未来应由服务端从批准版 Request、Decision 和有效 Review Record 确定性生成 DRAFT。页面不得手工拼接授权范围或自行生成 manifest_id。

生成器只能收窄范围。任何扩大时间、环境、路径、数据、人员、活动或写入预算的变化必须退回 Request 新版本和重新评审。
### 14.3 规范化与摘要

字段采用稳定排序和规范化序列化；生成 DRAFT 后计算内容摘要；REVIEWED 和 SIGNED 必须绑定同一摘要。摘要漂移即 BLOCKED。
### 14.4 生成结果

生成只产生 DRAFT，不产生 SIGNED、AUTHORIZED 或 ACTIVE。本轮不执行生成。
## 15. Review & Signature（清单审核与签发）

Manifest Review 检查其未超出 Request、Decision 和专业审核结论，六维范围无歧义，停止、回退、清理和证据输出可执行。

签发必须由具名批准人完成，记录 signature_reference、signed_at 和 manifest_sha256。签发人与 Execution Lead 必须分离。

SIGNED 只表示清单正文冻结并签名；仍需独立 Authorization Decision 和 READY_CHECK 才可能进入 ACTIVE。
## 16. Manifest Immutability（不可变规则）

签发后以下字段不可原地修改：

- manifest_id、manifest_version、linked_request_id、request_version 和所有摘要；
- environment、database、endpoints、network policy 和 credential profile；
- repository、branch、commit、allowed/prohibited paths；
- data source、classification、masking、objects、limit、retention 和 destruction；
- people、roles、activities、write budget、时间窗口和 expiration；
- stop conditions、rollback、cleanup、evidence outputs、签发人和签名。

任何实质变化必须 SUSPENDED 当前授权、创建新 Manifest 版本、重做受影响审核并重新签发；原版本永久保留。
## 17. Authorization & Activation（授权与激活）边界
### 17.1 Manifest

定义允许范围；不作是否执行的最终裁决。
### 17.2 Authorization

独立确认该 SIGNED Manifest 是否可以进入执行准备。只有 AUTHORIZED 才可启动 READY_CHECK。
### 17.3 READY_CHECK

核对当前环境、数据库、端点、凭据、commit、数据、人员、时间和 manifest_sha256 与签发版一致。
### 17.4 ACTIVE

表示当前可在授权范围内执行。ACTIVE 必须有开始时间、执行主体和审计记录；到期、停止或漂移立即退出 ACTIVE。

本报告不设计授权批准实例，也不执行 READY_CHECK 或 ACTIVE 转换。
## 18. Gate（门禁）映射

| Gate | Manifest 可限定的活动 | 不能替代 |
|---|---|---|
| Gate-2 Data | Schema、时态、数据质量、候选 Migration 和回退演练 | 正式 Migration、数据签发和生产迁移 |
| Gate-4 Technical | 服务、API、页面、权限、测试、恢复和回退验证 | 生产发布和上线证据 |
| Gate-3 Governance | 本授权链的职责分离测试 | 实名治理、任命和职责签发 |
| Gate-5 Business | 非生产演示或模拟验证 | 业务确认、人工验收和上线窗口 |

Manifest SIGNED、Authorization ACTIVE 或证据 COMPLETE 均不自动改变 Gate 状态。
## 19. Audit & Archive（审计与归档）

未来归档必须保存 Request/Decision/Review 引用、Manifest 所有版本、生成差异、签发记录、状态迁移、暂停/撤销原因、执行引用、回退、清理、关闭记录和 SHA256。

Manifest 各版本只能追加，不得覆盖。SUPERSEDED、FAILED、REVOKED 和 CLOSED 记录不得删除。

归档索引必须支持从 manifest_id/version 追溯 request_id/version、decision_id、manifest_sha256、批准人、执行状态和证据包。

本轮不创建任何归档实例。
## 20. Manifest Validation Rules（清单校验规则）

| 编号 | 校验 | 失败结果 |
|---|---|---|
| MFV-01 | 来源 Request 和 Decision 均存在且摘要一致 | BLOCKED |
| MFV-02 | Manifest 范围不超过批准 Request | REJECTED |
| MFV-03 | 六维范围全部明确 | BLOCKED |
| MFV-04 | 环境非生产且生产不可达 | REJECTED |
| MFV-05 | repository、commit 和路径固定 | BLOCKED |
| MFV-06 | 数据来源获批且不可回写 | REJECTED/BLOCKED |
| MFV-07 | 自然人职责分离通过 | BLOCKED |
| MFV-08 | 写入预算和测试命名空间明确 | BLOCKED |
| MFV-09 | 停止、回退、清理可执行 | BLOCKED |
| MFV-10 | 证据输出和 SHA256 规则完整 | BLOCKED |
| MFV-11 | 签发正文与 manifest_sha256 一致 | REJECTED |
| MFV-12 | SIGNED 未自动转为 ACTIVE | PASS 门禁 |
## 21. 设计验证场景

| 编号 | 场景 | 预期结果 |
|---|---|---|
| MFD-T01 | APPROVED Request 生成 DRAFT | 仅 DRAFT，不授权 |
| MFD-T02 | Manifest 比 Request 多一个路径 | REJECTED |
| MFD-T03 | 使用生产写端点 | REJECTED |
| MFD-T04 | 缺少 write budget | BLOCKED |
| MFD-T05 | 签发后修改 commit | 摘要漂移，BLOCKED |
| MFD-T06 | SIGNED 自动进入 ACTIVE | 拒绝自动迁移 |
| MFD-T07 | 达到写入预算 | SUSPENDED |
| MFD-T08 | 命名空间外写入 | REVOKED |
| MFD-T09 | 到期继续活动 | 强制停止 |
| MFD-T10 | 回退后摘要不一致 | FAILED/BLOCKED |
| MFD-T11 | Manifest 替代 Gate-3 实名治理 | 拒绝 |
| MFD-T12 | 测试结果替代业务验收 | 拒绝 |

这些场景仅为未来验证设计，本轮不执行。
## 22. 风险与控制

| 风险 | 影响 | 控制 |
|---|---|---|
| Request APPROVED 自动生成 ACTIVE | 越权执行 | 生成、签发、授权、激活四步分离 |
| Manifest 范围大于 Request | 范围扩张 | 服务端集合包含校验 |
| 签发后字段可修改 | 审计失真 | 规范化摘要和不可变版本 |
| 聚合状态掩盖双状态 | 误判可执行 | 文档状态与授权状态分别存储 |
| 未列活动被默认允许 | 白名单失效 | 未列入即禁止 |
| 超预算或到期仍写入 | 业务副作用 | 计数门禁、自动停止和撤销 |
| 失败证据被删除 | 无法复核 | 原始日志和追加式归档 |
| Manifest 被当作 Gate PASS | 治理绕过 | Gate 独立重新评估 |
## 23. 本轮保护状态

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

本轮未创建 manifest_id、Manifest Instance、签名、授权、执行、审核或业务记录。
## 24. 最终状态

```text
Controlled Evidence Build Authorization Manifest Design = COMPLETE
Authorization Manifest ID = NOT CREATED
Authorization Manifest Instance = NOT CREATED
Manifest Signature Instance = NOT CREATED
Controlled Evidence Build Authorization = NOT GRANTED
Controlled Evidence Build Execution = NOT STARTED
OOM-4.2 Implementation Authorization Review = NOT STARTED
Organization Model Implementation = NOT AUTHORIZED
RRE-1 = NOT AUTHORIZED
Workflow Integration = NOT AUTHORIZED
Context Scope = CONTROLLED
Input Files = 6
Task Scope = SINGLE
Review Level = B
Full Content Review Required = NO
Documentation Archived = YES
Archive Content Readback = YES
ChatGPT Reviewable = YES
Source Excerpts Verified = YES
```

本报告完成后立即停止，等待人工审查；不得创建或签发 Manifest、批准授权、进入 ACTIVE 或启动受控证据构建。
