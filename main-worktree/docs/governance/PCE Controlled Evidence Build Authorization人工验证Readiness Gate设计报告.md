# PCE Controlled Evidence Build Authorization（受控证据构建授权）人工验证 Readiness Gate（就绪门禁）设计报告

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 系统 | PCE（ProfitOS / Dev-PCE） |
| 文档日期 | 2026-08-19 |
| 阶段 | Controlled Evidence Build Authorization Human Validation Preparation（受控证据构建授权人工验证准备） |
| 类型 | DESIGN ONLY（仅设计） |
| Review Level（审查等级） | B（重点审查） |
| Context Scope（上下文范围） | CONTROLLED（受控） |
| Task Scope（任务范围） | SINGLE（单一） |
| 输入文件数量 | 4 |
| Readiness Gate 执行 | NOT STARTED（未执行） |
| Human Validation Result | BLOCKED（阻断） |
| 实施授权 | NOT AUTHORIZED（未授权） |
## 2. 唯一目标

本报告设计 Human Validation（人工验证）正式重新启动前的 Readiness Gate（就绪门禁），明确人员、材料、范围、独立性、环境、预期结果和审计证据的启动条件。
核心问题：
> 在进入正式人工验证执行前，需要满足哪些前置条件，如何判断验证是否可以开始？
本轮只设计门禁，不执行检查，不作真实 PASS 裁决，不创建 Gate、Validation、Authorization、Manifest 或 Evidence Package 实例。
## 3. Preflight（执行前检查）

| 检查项 | 结果 | 判断 |
|---|---|---|
| 任务是否单一 | YES | 仅设计人工验证启动门禁 |
| 输入文件是否最小必要 | YES | 仅 4 份指定基线 |
| 输入文件是否超过 5 份 | NO | 未触发拆分 |
| 是否执行 Readiness Gate | NO | 不产生真实检查记录 |
| 是否确认真实人员 | NO | 不填写 person_id 或姓名 |
| 是否执行签署 | NO | 不创建签署记录 |
| 是否执行 Human Validation | NO | 不重跑 S01～S06 |
| 是否关闭 HVX Issue | NO | 门禁只核验证据 |
| 是否发起治理冻结 | NO | 保持 NOT STARTED |
| 是否授予执行权限 | NO | 保持 NOT GRANTED |
| 输出规模 | 300–500 行 | Medium Governance |
| 全文回传要求 | NO | Level B 提供关键章节与依据 |
## 4. 已读取治理基线与判断依据

### 4.1 CODEX 核心规范

实际路径：`D:\Dev-PCE\Source\docs\governance\PCE CODEX开发指令规范管理V1.2.md`
文件用途：确认风险分级、最小上下文、证据优先、阶段分离和归档回读要求。
关键原文：
> 没有明确授权即视为不允许。Design Complete（设计完成）、Preparation Complete（准备完成）、Gate PASS（门禁通过）均不自动等于 Implementation Authorized（实施已授权）。
判断：Readiness Gate 正向裁决只允许启动人工验证，不授予实施或证据构建权限。
### 4.2 人工验证执行报告

实际路径：`D:\Dev-PCE\Source\docs\governance\PCE Controlled Evidence Build Authorization治理体系人工验证执行报告.md`
文件用途：确认当前阻断结果、正式场景签署和 HVX Issue。
关键原文：
> 因此：`Human Validation Result = BLOCKED`。
> `Formal Human Scenarios Signed = 0 / 6`
> 本轮没有修复或关闭 Issue；不得将 OPEN 预填为 RESOLVED/VERIFIED。
判断：当前没有满足启动条件；本设计不能改变正式结果或 Issue 状态。
### 4.3 人工验证执行规范

实际路径：`D:\Dev-PCE\Source\docs\governance\PCE Controlled Evidence Build Authorization人工验证执行规范设计报告.md`
文件用途：确认既有 Readiness Gate、角色独立性、材料冻结和最低签署规则。
关键原文：
> Readiness Gate 未通过不得开始任何场景。
> 未来工作区仅允许只读基线和离线记录模板，不得连接生产或非生产执行端点，不得持有数据库、API 或业务写凭据。
> 输入材料在开始前计算摘要并冻结。会议期间不得静默替换文件；变化必须记录并触发影响评估。
判断：门禁必须先于任何场景执行，并对工作区、输入 Hash 和人员独立性实行硬阻断。
### 4.4 角色任命与签署准备设计

实际路径：`D:\Dev-PCE\Source\docs\governance\PCE Controlled Evidence Build Authorization人工验证角色任命与签署准备设计报告.md`
文件用途：确认角色要求、资格、独立性、职责分离、签署包和 HVX 关闭条件。
关键原文：
> Appointment Preparation Complete 仅在以下设计材料齐全时成立：
> `BLOCKED` 用于条件尚不完整但可以通过补充人员、材料、范围或有效期合法解决的情况；它不表示允许继续。
> Issue 只能按 `OPEN → FIXING → RESOLVED → VERIFIED` 流转；本轮没有真实 Issue 状态写入，也不得把“关闭条件已设计”写成“问题已关闭”。
判断：门禁消费真实角色与签署证据，但不创建这些证据，也不代替独立复验关闭 Issue。
## 5. Readiness Gate 定义

Readiness Gate 是正式 Human Validation 开始前的准入检查和启动裁决机制。
它检查：

- 验证范围是否冻结；
- 必需角色是否具名、合格并签署；
- 自然人独立性与职责分离是否成立；
- 输入材料及预期结果是否冻结；
- 只读验证工作区是否安全；
- 记录、Hash 和审查责任是否准备完成。
Readiness Gate 不是：

- Human Validation PASS；
- Governance Freeze 或 Freeze Recommendation；
- OOM Gate PASS；
- Controlled Evidence Build Authorization；
- Implementation Authorization；
- 业务验收或系统测试。
## 6. 门禁治理角色

| 角色 | 门禁职责 | 不得替代 |
|---|---|---|
| Gate Owner | 发起检查、确认范围、汇总门禁结果 | 专业 Reviewer |
| Validation Owner | 确认验证计划和角色集合 | Gate 最终独立复核 |
| Architecture Reviewer | 检查对象、边界和输入一致性 | Security/Data Reviewer |
| Security Reviewer | 检查工作区、凭据和访问边界 | Authorization Owner |
| Data Reviewer | 检查数据边界、来源和零业务写入 | Business Owner |
| Process Reviewer | 检查场景、状态和判定闭环 | Workflow Runtime |
| Evidence Reviewer | 检查记录模板、Hash 和归档位置 | Recorder |
| Independent Observer | 复核角色冲突、程序和签署完整性 | 任一专业 Reviewer |
| Gate Recorder | 追加记录实际条件、证据和结论 | 决定专业结论 |
所有执行角色未来必须映射具名自然人；本轮不任命、不实名、不签署。
## 7. Readiness Gate 条件总览

| 编号 | 条件 | 核心证据 | 正向结果 |
|---|---|---|---|
| RG-01 | 验证范围冻结 | Scope Manifest、场景目录 | PASS CANDIDATE |
| RG-02 | 验证角色准备完成 | Role Matrix、签署包 | PASS CANDIDATE |
| RG-03 | 自然人独立性完成 | 声明、SoD 矩阵 | PASS CANDIDATE |
| RG-04 | 验证材料冻结 | 文件清单、版本、SHA256 | PASS CANDIDATE |
| RG-05 | 验证环境准备 | Workspace Checklist | PASS CANDIDATE |
| RG-06 | 预期结果冻结 | Expected Result Catalog | PASS CANDIDATE |
| RG-07 | 审计与证据准备 | Record Template、Archive Plan | PASS CANDIDATE |
单项 `PASS CANDIDATE` 仅表示该项具备正向证据；不等于总体 READY 或 APPROVED_FOR_VALIDATION。
## 8. RG-01 验证范围冻结

### 8.1 检查内容

- validation_objective：本轮验证要证明的设计事项；
- included_objects：Request、Validation、Review、Decision、Manifest、Authorization、Audit、Evidence Package；
- scenario_catalog：正常、缺陷、边界违规、职责冲突、异常和证据链场景；
- exclusions：系统调用、API、数据库、真实实例、业务验收和实施；
- validation_window：计划开始、结束和有效期；
- change_control：范围变化的版本和重检规则。
### 8.2 通过条件

范围、目标、场景、排除项和停止条件均唯一、无歧义，并绑定同一计划版本。
### 8.3 阻断条件

目标含糊、场景缺失、排除项不完整或范围在检查期间变化，结果为 BLOCKED；必须生成新版本后重检。
## 9. RG-02 验证角色准备完成

### 9.1 必需角色

必须具备 Validation Owner、Architecture Reviewer、Security Reviewer、Data Reviewer、Process Reviewer、Evidence Reviewer 和 Independent Observer。
必要时增加 Validation Lead、Recorder、Issue Owner 和 Re-validator；支撑角色不得替代必需角色。
### 9.2 检查内容

- 每个角色绑定唯一 person_id 和自然人；
- 身份、组织归属、资格与验证范围一致；
- 任命和签署处于有效期；
- 关键场景满足专业 Reviewer + Independent Observer 双重确认；
- 没有 Role Code、共享账号或管理员兜底；
- 角色在整个验证和复验窗口可履职。
### 9.3 通过条件

角色名册、资格确认、真实任命与签署包完整，所有 Hash 与计划版本一致。
### 9.4 阻断条件

缺少角色、签署、资格、有效期或自然人映射时必须 BLOCKED；不得以一人兼任全部专业角色解决。
## 10. RG-03 自然人独立性完成

### 10.1 检查内容

- 每个 person_id 已提交独立性声明；
- 设计、维护、修复、批准、执行和证据审核关系已披露；
- 职责分离矩阵以 person_id 全量交叉检查；
- 可补正冲突已换人或缩小范围并重新检查；
- 不可豁免冲突已 REJECTED；
- Independent Observer 独立且完成复核。
### 10.2 强制禁止组合

| 组合 | 门禁结果 |
|---|---|
| Designer + Final Validator | BLOCKED，候选配置必须更换 |
| Request Owner + Approver | BLOCKED，候选配置必须更换 |
| Executor + Evidence Reviewer | BLOCKED，候选配置必须更换 |
| Fix Owner + Verifier | BLOCKED，候选配置必须更换 |
| Approver + Independent Observer | BLOCKED，候选配置必须更换 |
| 共享账号承担任一签署角色 | FAILED，身份底线不成立 |
### 10.3 通过条件

全部必需角色的声明为 CLEAR，冲突矩阵无未处置项，复核签署绑定同一版本。
## 11. RG-04 验证材料冻结

### 11.1 材料清单

- Human Validation Plan；
- Human Validation Execution Standard；
- 适用对象设计报告；
- Scenario Catalog 和 Checklist；
- Role & Independence Package；
- Issue Register 和 Revalidation Plan；
- Record、Deviation、Stop 和 Signature 模板。
### 11.2 版本与 Hash

每份材料必须记录绝对路径、文件名、版本、行数、SHA256、冻结时间和材料 Owner。
任何文件缺失、版本不一致或 Hash 变化均使 RG-04 BLOCKED；变化不能静默接受，必须影响分析、重新冻结并重跑受影响门禁项。
### 11.3 通过条件

清单完整、文件可读、版本唯一、Hash 一致且所有 Reviewer 确认使用同一冻结输入。
## 12. RG-05 验证环境准备

### 12.1 环境定义

本门禁对应 Design Tabletop Walkthrough 的只读文档工作区，不是 Controlled Evidence Build 技术环境。
允许：只读基线、离线记录模板、Hash 校验工具和经批准的归档位置。
禁止：

- 生产环境或生产端点；
- 非生产执行端点；
- 数据库、API 或业务写凭据；
- 真实业务数据导入；
- 创建 Request、Manifest、Authorization 或 Evidence Package；
- 修改组织、责任、员工、权限或 Workflow 事实。
### 12.2 检查内容

| 检查 | 通过标准 |
|---|---|
| Workspace | 与生产和执行端点隔离 |
| Access | 只读、最小必要、具名访问 |
| Credentials | 无数据库、API、生产或业务写凭据 |
| Data | 仅文档和虚构场景，不含正式业务数据 |
| Tools | 只用于阅读、Hash 和离线记录 |
| Logging | 会话、访问和记录变化可追溯 |
| Stop Capability | 任一 Reviewer 可触发停止 |
发现生产环境、生产凭据或真实业务写能力时，RG-05 为 FAILED 并立即停止门禁检查。
## 13. RG-06 验证预期结果冻结

### 13.1 检查内容

- 每个 Scenario ID 有唯一 Expected Result；
- PASS、FAIL、BLOCKED 定义一致；
- 边界违规、职责冲突和异常状态有确定预期；
- 预期结果引用适用设计章节和版本；
- actual_result、validator、时间和结果字段保持空白；
- 争议项已形成 Issue，不以多数投票掩盖。
### 13.2 通过条件

所有强制场景预期已在执行前签署冻结，且未预填实际结果或 PASS。
### 13.3 变更控制

执行开始后不得修改 Expected Result 适配实际输出；确需修改时，停止场景、记录偏差、生成新版本并重新执行门禁。
## 14. RG-07 审计与证据准备

### 14.1 必备能力

- Validation Record、Issue、Deviation、Stop、Correction 和 Revalidation 模板；
- evidence_reference、validator_person_id、时间和签署字段；
- input_sha256、record_sha256 和归档索引；
- 只追加不覆盖的记录规则；
- Evidence Reviewer 和归档保管责任；
- 失败、阻断和中止证据保留规则。
### 14.2 通过条件

每个场景可以从结果反查输入、步骤、验证人、证据、Issue 和复验；模板可用但尚未创建真实记录。
### 14.3 阻断条件

记录模板缺字段、归档位置不可用、Hash 规则缺失或 Evidence Reviewer 未具名时必须 BLOCKED。
## 15. Readiness Check Record（就绪检查记录）设计

| 字段 | 设计要求 |
|---|---|
| gate_id | 未来唯一门禁编号；本轮不创建 |
| gate_version | 门禁检查版本 |
| check_item | RG-01～RG-07 |
| expected_condition | 冻结的通过条件 |
| actual_condition | 未来现场记录；本轮为空 |
| evidence_reference | 文件、签署、Hash 或检查表引用 |
| reviewer_person_id | 未来具名自然人；本轮为空 |
| co_reviewer | 关键项的独立复核人 |
| result | PASS/BLOCKED/FAILED；本轮 NOT_EXECUTED |
| checked_at | 可信时间；本轮为空 |
| issue_ids | 关联问题 |
| reservations | 保留意见 |
| record_sha256 | 未来最终记录摘要 |
禁止预填 actual_condition、reviewer、checked_at、PASS 或签署。
## 16. Readiness Gate 状态设计

### 16.1 主状态机

```text
NOT_STARTED
↓
CHECKING
↓
READY
↓
APPROVED_FOR_VALIDATION
```
异常出口：
```text
CHECKING / READY
├─ BLOCKED
└─ FAILED
```
### 16.2 状态语义

| 状态 | 含义 | 是否可开始验证 |
|---|---|---|
| NOT_STARTED | 尚无真实门禁记录 | NO |
| CHECKING | 正在收集实际条件和证据 | NO |
| READY | RG-01～RG-07 均有正向候选结果，待最终签署 | NO |
| BLOCKED | 存在可补正人员、材料、范围或证据缺口 | NO |
| FAILED | 存在设计缺陷、规则冲突、无法闭环或安全底线失败 | NO |
| APPROVED_FOR_VALIDATION | 门禁最终签署完成，仅允许开始人工验证 | YES |
`APPROVED_FOR_VALIDATION` 是用户语境中“Readiness Gate PASS”的正式状态表达，不等于 Human Validation PASS。
### 16.3 转换规则

| 转换 | 必备条件 | 触发主体 |
|---|---|---|
| NOT_STARTED → CHECKING | gate_id、版本、范围和 Reviewer 已具名 | Gate Owner |
| CHECKING → BLOCKED | 任一可补正条件未满足 | 对应 Reviewer |
| CHECKING → FAILED | 设计、规则、状态或安全底线失败 | 专业 Reviewer + Observer |
| CHECKING → READY | RG-01～RG-07 单项均满足 | Gate Owner 汇总 |
| READY → APPROVED_FOR_VALIDATION | 全部单项签署、版本和 Hash 复检通过 | Validation Owner + Independent Observer |
| READY → BLOCKED | 签署前发现漂移或失效 | 任一 Reviewer |
所有转换必须追加记录；不得修改旧结论或从 BLOCKED/FAILED 自动跳至 APPROVED_FOR_VALIDATION。
## 17. 阻断规则

以下情况必须 BLOCKED：

- 验证范围、场景或排除项不明确；
- 缺少 Validation Owner、专业 Reviewer 或 Independent Observer；
- 缺少真实任命、资格或签署；
- person_id、独立性声明或职责分离未确认；
- 输入文件、文档或清单版本不一致；
- SHA256 变化且未重新冻结；
- Expected Result 或判定规则未冻结；
- 记录模板、证据位置或审查人员未准备；
- 有效期不覆盖计划验证窗口；
- HVX 修复证据尚不足以支持正式复验。
BLOCKED 只能在补正、形成新版本并重新检查后解除；不得通过豁免强行继续。
## 18. 失败规则

以下情况必须 FAILED：

- 发现影响验证合法性的设计缺陷；
- 多份规范的规则相互冲突且无法确定权威解释；
- 状态模型无法形成合法闭环；
- 职责冲突无法被规则阻断；
- 审计或证据链设计不可追溯；
- 发现生产环境、生产凭据或正式业务写能力；
- 有人试图在门禁期间创建实例、调用 API 或修改数据库；
- 出现不可恢复的版本或 Hash 证据失真。
FAILED 必须创建未来 Issue 候选、保留证据并停止；不得降级为 BLOCKED 以绕过设计修复。
## 19. 总体判定算法

1. 按 RG-01 至 RG-07 逐项检查，不允许跳项；
2. 任一 FAILED 时总体立即 FAILED；
3. 无 FAILED 但任一 BLOCKED 时总体 BLOCKED；
4. 所有单项满足时进入 READY，不直接允许验证；
5. 在 READY 状态重新核对人员、签署、版本、Hash 和有效期；
6. Validation Owner 与 Independent Observer 完成最终签署后，进入 APPROVED_FOR_VALIDATION；
7. 任何签署后漂移使正向裁决失效并回到 BLOCKED；
8. 门禁结果只适用于绑定的验证计划版本和时间窗口。
禁止多数表决覆盖单项 FAILED/BLOCKED，禁止管理员或权限拥有者兜底。
## 20. HVX Issue 映射

| Issue | 门禁关联 | 必查证据 | 门禁作用 |
|---|---|---|---|
| HVX-I01 | RG-02 | 具名角色、任命、资格和签署包 | 缺失则 BLOCKED |
| HVX-I02 | RG-03 | 独立性声明、person_id 矩阵、Observer 签署 | 缺失则 BLOCKED |
| HVX-I03 | RG-03/RG-06 | 冲突判别矩阵、BLOCKED/REJECTED 语义和人员确认 | 缺失则 BLOCKED |
Readiness Gate 是检查工具，不是 Issue Owner 或 Re-validator；它不能自动把 Issue 从 OPEN 改为 RESOLVED/VERIFIED。
门禁可以接受 `RESOLVED_PENDING_REVALIDATION` 性质的修复证据作为重新执行输入，但只有正式人工验证和独立复验才能形成 VERIFIED。
本轮 HVX-I01、HVX-I02 和 HVX-I03 均保持 OPEN。
## 21. 与 Human Validation 的关系

```text
Role Preparation
↓
Readiness Gate CHECKING
↓
APPROVED_FOR_VALIDATION
↓
Human Validation Execution（新记录）
↓
Validation Result
```
规则：

- 门禁通过只允许创建新的人工验证执行记录；
- 不得修改原执行报告中的 BLOCKED 结论；
- Human Validation 必须现场记录 Actual Result、证据、时间和签署；
- `APPROVED_FOR_VALIDATION ≠ Human Validation PASS`；
- 门禁有效期、人员或输入变化时必须停止验证并重新检查。
## 22. 与 Governance Freeze 的关系

只有以下链路完成，才可以进入独立冻结评审：
```text
Readiness Gate APPROVED_FOR_VALIDATION
↓
Human Validation PASS
↓
Applicable Issues VERIFIED
↓
Governance Freeze Review
```
Human Validation PASS 只允许发起 Freeze Review；Freeze Review 不等于 Freeze Decision。
Governance Freeze 仍不等于 Controlled Evidence Build Authorization、OOM-4.2 或任何实施授权。
## 23. 门禁设计验收场景

| 场景 | 输入 | 预期门禁结果 |
|---|---|---|
| RG-T01 | 七项完整且最终签署有效 | APPROVED_FOR_VALIDATION |
| RG-T02 | 缺少 Evidence Reviewer | BLOCKED |
| RG-T03 | 独立性声明未完成 | BLOCKED |
| RG-T04 | 输入 SHA256 漂移 | BLOCKED，重新冻结 |
| RG-T05 | Expected Result 可在执行后修改 | FAILED |
| RG-T06 | 发现生产凭据 | FAILED，立即停止 |
| RG-T07 | 状态模型存在自动 PASS 路径 | FAILED |
| RG-T08 | 全部单项满足但最终签署缺失 | READY，不得开始验证 |
| RG-T09 | APPROVED 后人员有效期届满 | BLOCKED，裁决失效 |
| RG-T10 | Gate 试图自动关闭 HVX Issue | FAILED |
本轮只设计场景，不执行测试或生成实际结果。
## 24. 风险与控制

| 风险 | 影响 | 控制 |
|---|---|---|
| READY 被误作批准 | 未签署即启动 | READY 与 APPROVED 分离 |
| Gate PASS 被误作验证 PASS | 结论越权 | 正式状态使用 APPROVED_FOR_VALIDATION |
| 缺角色仍继续 | 独立性失效 | RG-02 硬阻断 |
| Role Code 替代自然人 | 无法追责 | RG-02/03 强制 person_id |
| 输入 Hash 漂移 | 预期与结果不一致 | RG-04 重新冻结 |
| 执行后修改预期 | 结果偏置 | RG-06 内容冻结 |
| 使用技术测试环境 | 阶段越界 | RG-05 仅只读文档工作区 |
| 日志模板不完整 | 结果不可追溯 | RG-07 硬阻断 |
| BLOCKED 被豁免 | 未满足条件启动 | 禁止多数表决或管理员兜底 |
| FAILED 被降级 | 设计缺陷被隐藏 | 独立失败语义与 Issue |
| 门禁自动关 Issue | 绕过复验 | Issue 生命周期分离 |
| 门禁通过自动冻结 | 越过人工验证 | Human Validation 与 Freeze 双门禁 |
## 25. 本轮保护状态

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
补充保护：
```text
Readiness Gate Executed = NO
Readiness Gate Decision Created = NO
Natural Person Confirmed = NO
Signature Record Created = NO
Validation Record Created = NO
Human Validation Re-executed = NO
HVX Issue Status Changed = NO
```
## 26. 最终状态

```text
Controlled Evidence Build Authorization Human Validation Readiness Gate Design = COMPLETE
Human Validation Execution = COMPLETE
Human Validation Result = BLOCKED
Governance Freeze Review = NOT STARTED
Governance Freeze Decision = NOT MADE
Controlled Evidence Build Authorization = NOT GRANTED
Controlled Evidence Build Execution = NOT STARTED
OOM-4.2 Implementation Authorization Review = NOT STARTED
Organization Model Implementation = NOT AUTHORIZED
RRE-1 = NOT AUTHORIZED
Workflow Integration = NOT AUTHORIZED
Context Scope = CONTROLLED
Input Files = 4
Task Scope = SINGLE
Review Level = B
Full Content Review Required = NO
Documentation Archived = YES
Archive Content Readback = YES
ChatGPT Reviewable = YES
Source Excerpts Verified = YES
```
本报告完成后立即停止。不得执行 Readiness Gate、不得形成 APPROVED_FOR_VALIDATION、不得重新执行 Human Validation、不得进入 Governance Freeze、Controlled Evidence Build、OOM-4.2 或任何实施活动。
