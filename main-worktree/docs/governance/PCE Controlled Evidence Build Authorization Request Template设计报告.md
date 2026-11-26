# PCE Controlled Evidence Build Authorization Request Template（受控证据构建授权申请模板）设计报告

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 系统 | PCE（ProfitOS / Dev-PCE） |
| 主题 | Controlled Evidence Build Authorization Request Template（受控证据构建授权申请模板） |
| 阶段 | Controlled Evidence Build Authorization Governance Design（受控证据构建授权治理设计） |
| 类型 | Design Only（仅设计） |
| 日期 | 2026-08-19 |
| 输出性质 | 可复用空白模板及字段治理规则 |
| 申请实例 | NOT CREATED |
| 授权清单实例 | NOT CREATED |
| 当前授权 | NOT GRANTED |
| 当前执行 | NOT STARTED |
## 2. 设计目标与边界

本报告定义未来申请 Controlled Evidence Build（受控证据构建）时使用的统一 Authorization Request Template（授权申请模板）。 模板解决：

- 申请人必须填写什么； 审核人必须检查什么； 六维授权范围如何固定；
- 证据目标如何与 Gate（门禁）关联； 风险、停止、回退和清理如何预先声明； 申请状态与授权状态如何保持分离。
本报告不创建具体申请、授权清单或授权决定。 本报告不授权 Schema、Migration、API、页面、数据、RRE 或 Workflow 活动。
## 3. Preflight（执行前检查）

```text
Context Scope = CONTROLLED
Input Files = 6
Task Scope = SINGLE
Target Size = 300-500 LINES
Implementation Authorization = NO
Template Instance Creation = NO
```
基线按 Level 0/1/2 读取，没有读取无关历史文件。
## 4. 已读取治理基线与判断依据

### 4.1 Level 0：CODEX 核心规范

路径：`D:\Dev-PCE\Source\docs\governance\PCE CODEX开发指令规范管理V1.1.md` 用途：控制上下文、任务规模、阶段边界和归档回读。 关键原文：
> 没有明确授权即视为不允许。Design Complete（设计完成）、Preparation Complete（准备完成）、Gate PASS（门禁通过）均不自动等于 Implementation Authorized（实施已授权）。
判断依据：模板设计完成不构成申请批准或证据构建授权。
### 4.2 Level 1：Controlled Evidence Build 阶段基线

路径：`D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 Controlled Evidence Build Authorization设计报告.md` 用途：确认独立授权、默认禁止和当前状态。 关键原文：
> 授权批准人与执行人必须分离。 环境隔离确认人与环境搭建人必须分离。
> 任何未列入清单的活动默认禁止。 授权过期后不得继续构建或写入。
> Controlled Evidence Build Authorization = NOT GRANTED
路径：`D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 Controlled Evidence Build Authorization评审与授权申请设计报告.md` 用途：确认申请、评审、裁决、暂停、撤销和关闭状态。 关键原文：
> APPROVED 只表示申请通过评审，可生成批准版授权清单。 APPROVED 不表示证据构建已经 ACTIVE（执行中）。
> Controlled Evidence Build Authorization Request Instance = NOT CREATED
判断依据：本模板必须同时防止“未列明即允许”和“申请批准即执行”两类越权。
### 4.3 Level 2：Gate 专项基线

路径：`D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-4 Gate综合状态评估与解除路线图报告.md` 关键原文：

```text
Gate-1 Architecture = PASS
Gate-2 Data = BLOCKED
Gate-3 Governance = BLOCKED
Gate-4 Technical = BLOCKED
Gate-5 Business = BLOCKED
```
路径：`D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 Gate-2 Data解除准备设计报告.md` 关键原文：
> 准备设计完成、Migration 草案存在或测试环境结构可用，都不能单独使 Gate-2 转为 PASS。
路径：`D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 Gate-4 Technical解除准备设计报告.md` 关键原文：
> 生产初始化必须等待独立数据导入授权；隔离预演成功不能自动授权生产执行。
判断依据：模板可申请 Gate-2、Gate-4 技术证据，但不得替代 Gate-3、Gate-5 或生产授权。
## 5. 模板治理原则

### 5.1 空白模板原则

所有待填写值统一使用 `{{FIELD_NAME}}`，不得预填真实人员、环境、密钥、端点、数据或批准结论。
### 5.2 单次申请原则

一份申请只对应一个明确证据目标、一个固定源提交和一组可独立关闭的活动。
### 5.3 六维白名单原则

Time、Environment、Files、Data、People、Activities 六个维度都必须明确；未列入范围默认禁止。
### 5.4 可失败原则

Evidence Question（证据问题）必须允许得出失败或阻塞结果，禁止写成“确保上线”“保证通过”。
### 5.5 状态分离原则

Request APPROVED 不等于 Authorization ACTIVE；Evidence COMPLETE 不等于 Gate PASS。
## 6. Authorization Request Template（授权申请模板）

以下内容为未来申请时复制使用的标准空白模板。
### 6.1 Template Control（模板控制）

| 字段 | 待填写值 | 规则 |
|---|---|---|
| template_version | `{{TEMPLATE_VERSION}}` | 必须引用当前活动模板版本 |
| request_id | `{{REQUEST_ID}}` | 全局唯一，不得复用 |
| request_version | `{{REQUEST_VERSION}}` | 实质变更必须递增 |
| request_status | `DRAFT` | 新申请只能从 DRAFT 开始 |
| created_at | `{{CREATED_AT}}` | ISO 8601 时间 |
| last_updated_at | `{{LAST_UPDATED_AT}}` | 每次修订更新 |
### 6.2 Request Information（申请信息）

| 字段 | 待填写值 | 填写要求 |
|---|---|---|
| title | `{{TITLE}}` | 描述证据主题，不写“上线申请” |
| request_owner | `{{REQUEST_OWNER}}` | 具名自然人 |
| department_or_organization | `{{REQUEST_ORGANIZATION}}` | 申请人所属组织 |
| request_date | `{{REQUEST_DATE}}` | 正式提交日期 |
| objective | `{{OBJECTIVE}}` | 说明需要形成什么证据 |
| business_reason | `{{BUSINESS_REASON}}` | 说明 Gate 缺口及必要性 |
| target_gate_summary | `{{TARGET_GATE_SUMMARY}}` | 仅声明证据目标，不承诺 PASS |
| contact | `{{CONTACT}}` | 可用联系方式 |
申请声明：

```text
本申请只请求在授权隔离环境中构建指定证据，不请求生产实施、正式数据切换或业务上线。
```
### 6.3 Evidence Objective（证据目标）

| 编号 | Target Gate | Evidence Question | Expected Output | Success Criteria | Failure Result |
|---|---|---|---|---|---|
| `{{EO_ID}}` | `{{GATE_2_OR_GATE_4}}` | `{{QUESTION}}` | `{{OUTPUT}}` | `{{CRITERIA}}` | `FAILED/BLOCKED` |
填写规则：

- Target Gate 只能填写 Gate-2、Gate-4 或其明确子项； Evidence Question 必须可验证、可失败； Expected Output 必须指定文件、日志或结构化结果；
- Success Criteria 必须客观可复核； 禁止填写“最终 Gate PASS”“正式上线成功”等结论。
### 6.4 Scope Definition（六维范围）

#### A. Time（时间）

| 字段 | 待填写值 | 规则 |
|---|---|---|
| requested_start | `{{START_TIME}}` | 不早于授权签发时间 |
| requested_end | `{{END_TIME}}` | 到期自动失效 |
| maximum_duration | `{{MAX_DURATION}}` | 不得开放式延期 |
| allowed_windows | `{{TIME_WINDOWS}}` | 明确日期和时段 |
| expiry_action | `STOP_AND_REVOKE_CREDENTIALS` | 固定停止行为 |
#### B. Environment（环境）

| 字段 | 待填写值 | 规则 |
|---|---|---|
| environment_id | `{{ENVIRONMENT_ID}}` | 唯一编号，禁止只写“测试环境” |
| environment_type | `NON_PRODUCTION_EVIDENCE` | 不得使用 production |
| database_id | `{{DATABASE_ID}}` | 隔离数据库唯一标识 |
| service_endpoints | `{{ENDPOINT_ALLOWLIST}}` | 仅白名单端点 |
| network_policy | `{{NETWORK_POLICY_ID}}` | 默认拒绝 |
| production_reachability | `DENIED` | 必须有验证证据 |
| environment_owner | `{{ENVIRONMENT_OWNER}}` | 具名负责人 |
| disposal_method | `{{DESTROY_FREEZE_OR_REBUILD}}` | 结束时明确处理 |
#### C. Files（文件）

| 字段 | 待填写值 | 规则 |
|---|---|---|
| repository | `{{REPOSITORY}}` | 唯一仓库 |
| branch | `{{BRANCH}}` | 候选分支，不得自动发布 |
| source_commit | `{{COMMIT_SHA}}` | 固定不可歧义提交 |
| allowed_paths | `{{EXPLICIT_ALLOWED_PATHS}}` | 文件或目录白名单 |
| prohibited_paths | `{{EXPLICIT_PROHIBITED_PATHS}}` | 至少包含生产和相邻模块 |
| candidate_artifacts | `{{CANDIDATE_ARTIFACTS}}` | 逐项列出 |
| merge_policy | `NO_AUTO_MERGE` | 需后续独立授权 |
#### D. Data（数据）

| 字段 | 待填写值 | 规则 |
|---|---|---|
| data_source_type | `SYNTHETIC/MASKED/AUTHORIZED_READONLY_COPY` | 三选一 |
| data_source | `{{DATA_SOURCE}}` | 必须可追溯 |
| data_custodian | `{{DATA_CUSTODIAN}}` | 具名自然人 |
| classification | `{{DATA_CLASSIFICATION}}` | 明确敏感等级 |
| masking_rule | `{{MASKING_RULE}}` | 非合成数据必填 |
| permitted_objects | `{{DATA_OBJECTS}}` | 对象白名单 |
| record_limit | `{{MAX_RECORD_COUNT}}` | 写入与处理上限 |
| test_namespace | `{{TEST_NAMESPACE}}` | 与正式事实隔离 |
| retention_period | `{{RETENTION_PERIOD}}` | 到期清理或批准保留 |
| destruction_evidence | `{{DESTRUCTION_OUTPUT}}` | 清理证据位置 |
#### E. People（人员）

| 角色 | 待填写自然人 | 职责 | 冲突限制 |
|---|---|---|---|
| Request Owner | `{{REQUEST_OWNER}}` | 对申请真实性负责 | 不得最终自批 |
| Authorization Owner | `{{AUTHORIZATION_OWNER}}` | 未来作出授权裁决 | 不得是唯一执行人 |
| Execution Lead | `{{EXECUTION_LEAD}}` | 未来按清单执行 | 不得修改范围 |
| Architecture Reviewer | `{{ARCHITECTURE_REVIEWER}}` | 检查 BAC/OOM 边界 | 不得批准越界 |
| Security Reviewer | `{{SECURITY_REVIEWER}}` | 检查环境、凭据、网络 | 不得是唯一环境搭建人 |
| Data Custodian | `{{DATA_CUSTODIAN}}` | 批准测试数据来源 | 不得批准来源不明数据 |
| Technical Reviewer | `{{TECHNICAL_REVIEWER}}` | 检查测试与回退 | 不得自证全部结果 |
| Evidence Reviewer | `{{EVIDENCE_REVIEWER}}` | 独立复核证据 | 不得删除失败记录 |
| Stop Authority | `{{STOP_AUTHORITY}}` | 暂停和紧急停止 | 必须可即时联系 |
自然人职责分离检查：`{{PASS/BLOCKED}}`
### F. Activities（活动）

允许活动表：

| activity_id | activity | object | environment | maximum_write | expected_evidence |
|---|---|---|---|---:|---|
| `{{ACTIVITY_ID}}` | `{{ALLOWED_ACTIVITY}}` | `{{OBJECT}}` | `{{ENVIRONMENT_ID}}` | `{{WRITE_LIMIT}}` | `{{EVIDENCE}}` |
永久禁止活动：

- 生产代码部署和生产数据库修改； 正式组织、责任、员工或权限事实写入； 正式 Migration、企业数据导入或业务状态切换；
- 生产密钥、证书、端点或外部副作用； Workflow Runtime 修改、ApprovalTask 创建或 RRE 启动； 未列入允许活动表的文件、数据、人员或动作。
Write Budget（写入预算）：

| 字段 | 待填写值 |
|---|---|
| allowed_object_types | `{{OBJECT_TYPES}}` |
| maximum_total_writes | `{{MAX_WRITES}}` |
| namespace | `{{TEST_NAMESPACE}}` |
| cleanup_required | `YES` |
| unauthorized_business_writes | `0` |
### 6.5 Environment Isolation（环境隔离证明）

| 检查 | 申请人证据 | 审核结果 |
|---|---|---|
| 独立数据库或可证明隔离 | `{{EVIDENCE_REF}}` | `{{PASS/BLOCKED}}` |
| 生产写端点不可达 | `{{EVIDENCE_REF}}` | `{{PASS/BLOCKED}}` |
| 非生产短期凭据 | `{{EVIDENCE_REF}}` | `{{PASS/BLOCKED}}` |
| 网络默认拒绝 | `{{EVIDENCE_REF}}` | `{{PASS/BLOCKED}}` |
| 数据来源获批 | `{{EVIDENCE_REF}}` | `{{PASS/BLOCKED}}` |
| 测试命名空间存在 | `{{EVIDENCE_REF}}` | `{{PASS/BLOCKED}}` |
| 日志与审计可用 | `{{EVIDENCE_REF}}` | `{{PASS/BLOCKED}}` |
| 环境可恢复或销毁 | `{{EVIDENCE_REF}}` | `{{PASS/BLOCKED}}` |
任一检查为 BLOCKED，不得进入 Authorization Decision（授权裁决）。
### 6.6 Data Provenance（数据来源声明）

| 字段 | 待填写值 |
|---|---|
| provenance_id | `{{PROVENANCE_ID}}` |
| source_system | `{{SOURCE_SYSTEM}}` |
| extraction_method | `{{EXTRACTION_METHOD}}` |
| source_owner | `{{SOURCE_OWNER}}` |
| authorization_reference | `{{DATA_AUTH_REFERENCE}}` |
| masking_or_generation_method | `{{METHOD}}` |
| sensitive_fields | `{{SENSITIVE_FIELDS}}` |
| lifecycle | `{{CREATE_USE_RETAIN_DESTROY}}` |
| prohibited_reuse | `{{PROHIBITED_REUSE}}` |
申请人声明：来源不明数据不得进入环境，隔离结果不得回写正式数据源。
### 6.7 Evidence Output（证据输出）

| evidence_id | 输出 | 格式 | 生成者 | 保存位置 | SHA256 | 保留期 |
|---|---|---|---|---|---|---|
| `{{EVIDENCE_ID}}` | `{{OUTPUT_NAME}}` | `{{FORMAT}}` | `{{PRODUCER}}` | `{{LOCATION}}` | `{{SHA256}}` | `{{RETENTION}}` |
最低证据范围：

- 授权申请与批准版清单； 环境、端点、数据库、凭据和数据清单； 源提交、候选 Migration 和变更摘要；
- 测试结果、原始日志、失败记录和数据摘要； 回退、恢复、清理和凭据撤销结果； Evidence Owner（证据负责人）与独立复核结论。
Evidence Owner：`{{EVIDENCE_OWNER}}` 证据包目标位置：`{{EVIDENCE_PACKAGE_LOCATION}}`
### 6.8 Risk Register（风险登记）

| risk_id | 风险描述 | 影响 | 概率 | 控制措施 | 责任人 | 状态 | 停止触发 |
|---|---|---|---|---|---|---|---|
| `{{RISK_ID}}` | `{{DESCRIPTION}}` | `{{IMPACT}}` | `{{PROBABILITY}}` | `{{CONTROL}}` | `{{OWNER}}` | `OPEN` | `{{TRIGGER}}` |
P0/P1 风险未关闭时，申请不得 APPROVED。
### 6.9 Rollback Plan（回退方案）

| 字段 | 待填写值 |
|---|---|
| rollback_id | `{{ROLLBACK_ID}}` |
| baseline_snapshot | `{{BASELINE_REFERENCE}}` |
| recovery_point | `{{RECOVERY_POINT}}` |
| rollback_steps | `{{ORDERED_STEPS}}` |
| rollback_owner | `{{ROLLBACK_OWNER}}` |
| maximum_recovery_time | `{{RTO}}` |
| verification_method | `{{DIGEST_AND_COUNT_CHECK}}` |
| failure_escalation | `{{ESCALATION_PATH}}` |
回退失败必须触发 Stop Authority，不得继续扩大执行。
### 6.10 Cleanup Plan（清理方案）

| 清理对象 | 处理动作 | 负责人 | 完成证据 |
|---|---|---|---|
| 测试数据 | `{{DELETE_OR_APPROVED_RETAIN}}` | `{{OWNER}}` | `{{EVIDENCE}}` |
| 临时凭据 | `REVOKE` | `{{OWNER}}` | `{{EVIDENCE}}` |
| 网络白名单 | `REMOVE` | `{{OWNER}}` | `{{EVIDENCE}}` |
| 候选环境 | `{{DESTROY_OR_FREEZE}}` | `{{OWNER}}` | `{{EVIDENCE}}` |
| 临时制品 | `{{ARCHIVE_OR_DELETE}}` | `{{OWNER}}` | `{{EVIDENCE}}` |
| 日志与证据 | `ARCHIVE_READONLY` | `{{OWNER}}` | `{{EVIDENCE}}` |
### 6.11 Stop Conditions（停止条件）

以下条件必须预设为立即停止：

- 发现生产写端点或生产凭据； 数据、代码、环境、人员或活动超出白名单； Manifest 摘要与批准版不一致；
- 日志或审计不可用； 发生未授权业务写入； 回退无法执行；
- 授权到期或 Stop Authority 指令停止。
停止通知路径：`{{STOP_NOTIFICATION_PATH}}`
## 7. Review Checklist（评审检查清单）

### 7.1 Completeness Review（完整性检查）

| 检查 | 结果 | 证据/意见 |
|---|---|---|
| 所有必填字段已填写 | `{{PASS/BLOCKED}}` | `{{REF}}` |
| 六维范围完整 | `{{PASS/BLOCKED}}` | `{{REF}}` |
| 附件可访问 | `{{PASS/BLOCKED}}` | `{{REF}}` |
| 无生产或正式实施请求 | `{{PASS/REJECTED}}` | `{{REF}}` |
### 7.2 Architecture Review（架构审核）

| 检查 | 结果 | 证据/意见 |
|---|---|---|
| 符合 BAC 唯一事实源边界 | `{{PASS/REJECTED}}` | `{{REF}}` |
| 符合 OOM 组织事实边界 | `{{PASS/REJECTED}}` | `{{REF}}` |
| 不创建平行事实模型 | `{{PASS/REJECTED}}` | `{{REF}}` |
| 不混用 Responsibility 与 Permission | `{{PASS/REJECTED}}` | `{{REF}}` |
| 不修改 Workflow 或启动 RRE | `{{PASS/REJECTED}}` | `{{REF}}` |
Architecture Reviewer：`{{NAME}}`；日期：`{{DATE}}`；结论：`{{PASS/BLOCKED/REJECTED}}`
### 7.3 Security Review（安全审核）

| 检查 | 结果 | 证据/意见 |
|---|---|---|
| 环境和数据库唯一隔离 | `{{PASS/BLOCKED}}` | `{{REF}}` |
| 生产端点不可达 | `{{PASS/REJECTED}}` | `{{REF}}` |
| 仅使用非生产短期凭据 | `{{PASS/REJECTED}}` | `{{REF}}` |
| 网络默认拒绝 | `{{PASS/BLOCKED}}` | `{{REF}}` |
| 监控和紧急停止有效 | `{{PASS/BLOCKED}}` | `{{REF}}` |
Security Reviewer：`{{NAME}}`；日期：`{{DATE}}`；结论：`{{PASS/BLOCKED/REJECTED}}`
### 7.4 Data Review（数据审核）

| 检查 | 结果 | 证据/意见 |
|---|---|---|
| 数据来源可追溯且获批 | `{{PASS/BLOCKED}}` | `{{REF}}` |
| 分类和脱敏适当 | `{{PASS/BLOCKED}}` | `{{REF}}` |
| 对象、数量和命名空间受限 | `{{PASS/BLOCKED}}` | `{{REF}}` |
| 保留与销毁规则明确 | `{{PASS/BLOCKED}}` | `{{REF}}` |
| 不会回写正式数据源 | `{{PASS/REJECTED}}` | `{{REF}}` |
Data Custodian：`{{NAME}}`；日期：`{{DATE}}`；结论：`{{PASS/BLOCKED/REJECTED}}`
### 7.5 Technical Review（技术审核）

| 检查 | 结果 | 证据/意见 |
|---|---|---|
| 候选方案可执行且可失败 | `{{PASS/BLOCKED}}` | `{{REF}}` |
| 测试范围和阈值明确 | `{{PASS/BLOCKED}}` | `{{REF}}` |
| 写入预算可监控 | `{{PASS/BLOCKED}}` | `{{REF}}` |
| 回退步骤可执行 | `{{PASS/REJECTED}}` | `{{REF}}` |
| 清理和恢复可验证 | `{{PASS/BLOCKED}}` | `{{REF}}` |
Technical Reviewer：`{{NAME}}`；日期：`{{DATE}}`；结论：`{{PASS/BLOCKED/REJECTED}}`
### 7.6 Evidence Review（证据审核）

| 检查 | 结果 | 证据/意见 |
|---|---|---|
| 输出与 Evidence Question 对应 | `{{PASS/BLOCKED}}` | `{{REF}}` |
| 原始日志与失败记录保留 | `{{PASS/REJECTED}}` | `{{REF}}` |
| 文件生成者、时间和版本可追溯 | `{{PASS/BLOCKED}}` | `{{REF}}` |
| SHA256 和归档位置明确 | `{{PASS/BLOCKED}}` | `{{REF}}` |
| 独立复核人与执行人分离 | `{{PASS/BLOCKED}}` | `{{REF}}` |
Evidence Reviewer：`{{NAME}}`；日期：`{{DATE}}`；结论：`{{PASS/BLOCKED/REJECTED}}`
## 8. Status Model（状态模型）

### 8.1 Request（申请）状态

```text
DRAFT
↓
SUBMITTED
↓
REVIEWING
↓
APPROVED / REJECTED / BLOCKED
↓
CLOSED
```
### 8.2 Authorization（授权）状态

```text
NOT_CREATED
↓
AUTHORIZED
↓
ACTIVE
↓
SUSPENDED / COMPLETE / FAILED / REVOKED
↓
CLOSED
```
### 8.3 状态规则

- 本报告只设计状态，不创建状态实例； Request APPROVED 只允许形成待签发清单，不自动进入 ACTIVE； BLOCKED 不得签发授权；
- REJECTED 必须记录原因和是否允许重新申请； SUSPENDED 恢复必须重新确认受影响评审； REVOKED 不得恢复原授权；
- COMPLETE 不自动改变 Gate 或实施授权状态。
## 9. Authorization Decision Placeholder（授权裁决占位区）

此区域仅供未来独立授权流程使用，本设计报告不得填写。

| 字段 | 待填写值 |
|---|---|
| decision | `{{APPROVED/REJECTED/BLOCKED}}` |
| authorization_id | `{{AUTHORIZATION_ID_OR_NOT_CREATED}}` |
| manifest_version | `{{MANIFEST_VERSION}}` |
| authorized_from | `{{START}}` |
| expires_at | `{{EXPIRY}}` |
| decision_reason | `{{REASON}}` |
| authorization_owner | `{{NAME}}` |
| signature_reference | `{{SIGNATURE_REF}}` |
| manifest_sha256 | `{{SHA256}}` |
模板警告：未完成全部审核和正式签发时，本区必须保持空白，Authorization = NOT GRANTED。
## 10. Gate Evidence Mapping（门禁证据映射）

| Gate | 模板可申请的证据 | 模板不能替代 |
|---|---|---|
| Gate-2 Data | Schema 验证、数据质量、候选转换、Migration 演练、回退 | 正式 Schema/Migration 授权、Data Owner 签发、正式数据迁移 |
| Gate-4 Technical | 服务、API、页面、测试、性能、安全、恢复与回退验证 | 生产发布、正式执行、上线运行证据 |
| Gate-3 Governance | 仅可验证职责分离控制 | 实名治理、职责任命和治理签发 |
| Gate-5 Business | 仅可支持非生产演示或模拟脚本 | 业务确认、首批数据确认、人工验收和上线窗口 |
任何申请、授权或证据结果都不能自动改变 Gate 状态。
## 11. Template Validation Rules（模板校验规则）

| 编号 | 校验 | 失败结果 |
|---|---|---|
| TV-01 | request_id 唯一 | BLOCKED |
| TV-02 | objective 描述证据而非上线 | REJECTED |
| TV-03 | Target Gate 仅为 Gate-2/Gate-4 | BLOCKED 或 REJECTED |
| TV-04 | 六维范围全部填写 | BLOCKED |
| TV-05 | environment_id 和 database_id 唯一 | BLOCKED |
| TV-06 | source_commit 固定 | BLOCKED |
| TV-07 | allowed/prohibited paths 无开放表述 | BLOCKED |
| TV-08 | 数据来源可追溯 | BLOCKED 或 REJECTED |
| TV-09 | 生产端点不可达 | REJECTED |
| TV-10 | 自然人职责分离通过 | BLOCKED |
| TV-11 | 写入预算明确且可监控 | BLOCKED |
| TV-12 | 回退和清理方案完整 | BLOCKED |
| TV-13 | 证据位置和 SHA256 规则明确 | BLOCKED |
| TV-14 | P0/P1 风险关闭 | BLOCKED |
| TV-15 | 未承诺 Gate PASS | REJECTED |
## 12. 模板使用与版本规则

- 申请人复制本模板后生成独立文件，不得修改归档母版； 申请文件名必须包含 request_id 和版本； 所有 `{{...}}` 占位符必须填写或明确标记 NOT APPLICABLE；
- 未填写占位符不得进入 SUBMITTED； 实质变更必须递增 request_version 并重新审核； 批准版 Manifest 必须与申请版本、源提交和环境一一对应；
- 模板升级后，新申请使用最新活动版本；历史申请保持原模板版本供审计。
## 13. 风险与控制

| 风险 | 影响 | 控制 |
|---|---|---|
| 空白模板被误认为授权 | 越权执行 | 首页与最终状态明确 NOT GRANTED |
| 使用“测试环境”等模糊描述 | 环境串用 | 强制 environment_id/database_id |
| 允许活动开放式填写 | 范围扩张 | 活动、对象、写入预算白名单 |
| 申请人自审自批 | 证据失真 | People 表和自然人冲突检查 |
| 数据来源不明 | 泄露或事实污染 | Data Provenance 和 Data Custodian 签发 |
| APPROVED 自动进入 ACTIVE | 跳过执行前检查 | Request/Authorization 双状态模型 |
| 技术证据代替 Gate-3/5 | 治理绕过 | Gate 映射明确不可替代项 |
| 失败日志未保留 | 无法复核 | Evidence Output 强制原始日志和 SHA256 |
## 14. 本轮保护状态

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
## 15. 最终状态

```text
Controlled Evidence Build Authorization Request Template Design = COMPLETE
Authorization Request Instance = NOT CREATED
Authorization Manifest Instance = NOT CREATED
Controlled Evidence Build Authorization = NOT GRANTED
Controlled Evidence Build Execution = NOT STARTED
OOM-4.2 Implementation Authorization Review = NOT STARTED
Organization Model Implementation = NOT AUTHORIZED
RRE-1 = NOT AUTHORIZED
Workflow Integration = NOT AUTHORIZED
Context Scope = CONTROLLED
Input Files = 6
Task Scope = SINGLE
```
本报告只完成标准申请模板设计，不创建申请、授权或执行实例。 归档完成后立即停止，等待人工审查。
