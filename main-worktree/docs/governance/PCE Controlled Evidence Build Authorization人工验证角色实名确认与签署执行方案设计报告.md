# PCE Controlled Evidence Build Authorization（受控证据构建授权）人工验证角色实名确认与签署执行方案设计报告

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
| Human Validation Result | BLOCKED（阻断） |
| 真实自然人确认 | NOT EXECUTED（未执行） |
| 真实签署 | NOT EXECUTED（未执行） |
| 实施授权 | NOT AUTHORIZED（未授权） |
## 2. 唯一目标

本报告设计未来 Human Validation（人工验证）正式启动前，验证角色从已定义角色要求进入实名确认、独立性声明、职责分离确认、签署和验证激活准备的治理闭环。
核心问题：
> 在不创建真实授权、不执行 Controlled Evidence Build（受控证据构建）的前提下，未来如何完成验证角色实名确认、独立性声明、职责分离确认和签署执行？
本报告只定义流程、字段、校验、状态和证据要求；不填写自然人姓名，不创建确认、签署、任命或验证记录。
## 3. Preflight（执行前检查）

| 检查项 | 结果 | 判断 |
|---|---|---|
| 任务是否单一 | YES | 只设计实名确认与签署执行方案 |
| 输入是否最小必要 | YES | 仅 4 份直接基线 |
| 输入文件是否超过 5 份 | NO | 未触发拆分 |
| 是否任命真实自然人 | NO | 所有人员字段保持空白 |
| 是否执行真实签署 | NO | 不创建签署事件或签章 |
| 是否创建治理角色记录 | NO | 仅设计字段结构 |
| 是否执行 Human Validation | NO | 不重跑正式场景 |
| 是否改变 Issue 状态 | NO | 只设计关闭映射 |
| 是否发起 Governance Freeze | NO | 保持 NOT STARTED |
| 是否授予任何执行权限 | NO | 保持 NOT GRANTED |
| 输出规模 | 300–500 行 | Medium Governance |
| 全文回传 | NO | Level B 交付关键章节和依据 |
## 4. 已读取基线、关键原文与判断

### 4.1 CODEX 核心规范

实际路径：`D:\Dev-PCE\Source\docs\governance\PCE CODEX开发指令规范管理V1.2.md`
文件用途：确认风险分级、上下文控制、证据优先、阶段分离和回读要求。
关键原文：
> 没有明确授权即视为不允许。Design Complete（设计完成）、Preparation Complete（准备完成）、Gate PASS（门禁通过）均不自动等于 Implementation Authorized（实施已授权）。
判断：本方案完成不能产生真实确认、签署、验证 PASS、治理冻结或实施授权。
### 4.2 人工验证执行报告

实际路径：`D:\Dev-PCE\Source\docs\governance\PCE Controlled Evidence Build Authorization治理体系人工验证执行报告.md`
文件用途：确认当前人工验证状态及 HVX-I01～I03。
关键原文：
> 因此：`Human Validation Result = BLOCKED`。
> `Formal Human Scenarios Signed = 0 / 6`
> 本轮没有修复或关闭 Issue；不得将 OPEN 预填为 RESOLVED/VERIFIED。
判断：本轮不得用流程设计替代自然人签署，正式结果和三个 Issue 状态均保持不变。
### 4.3 人工验证执行规范

实际路径：`D:\Dev-PCE\Source\docs\governance\PCE Controlled Evidence Build Authorization人工验证执行规范设计报告.md`
文件用途：确认自然人身份、冲突申报、最低签署和 Readiness Gate（就绪门禁）。
关键原文：
> 所有角色未来必须映射具名自然人；仅有 Role Code（角色编码）或共享账号不满足要求。
> 单个检查项由执行 Reviewer 签署；关键边界场景至少由对应专业 Reviewer 和 Independent Observer 双重确认；总体结果由 Validation Owner 汇总但不得改写单项结论。
> Readiness Gate 未通过不得开始任何场景。
判断：实名确认必须绑定自然人、角色、范围与版本；签署完成后仍需独立就绪复检。
### 4.4 角色任命与签署准备设计

实际路径：`D:\Dev-PCE\Source\docs\governance\PCE Controlled Evidence Build Authorization人工验证角色任命与签署准备设计报告.md`
文件用途：确认角色资格、独立性、职责分离矩阵、签署包和 Issue 关闭条件。
关键原文：
> Appointment Preparation Complete 仅在以下设计材料齐全时成立：
> `BLOCKED` 用于条件尚不完整但可以通过补充人员、材料、范围或有效期合法解决的情况；它不表示允许继续。
> `REJECTED` 用于当前候选配置包含不可豁免冲突、共享身份、故意绕过或违反独立性底线的情况；必须更换配置并形成新版本。
判断：本报告消费已设计结构，进一步定义未来实名确认与签署的执行顺序，不改变既有边界。
## 5. 当前状态与目标状态

| 治理对象 | 当前状态 | 本方案设计目标 | 本轮实际状态 |
|---|---|---|---|
| Role Requirement | 已定义 | 转为可确认角色包 | DESIGN COMPLETE |
| Named Person | 未提供 | 定义实名核验步骤 | NOT IDENTIFIED |
| Qualification | 标准已定义 | 定义资格确认动作 | NOT ASSESSED |
| Independence | 声明结构已定义 | 定义声明与复核动作 | NOT DECLARED |
| SoD | 矩阵已设计 | 定义交叉确认动作 | NOT CHECKED |
| Signature Package | 结构已设计 | 定义冻结、签署与失效规则 | NOT CREATED |
| Human Validation | 正式结果 BLOCKED | 定义启动前条件 | NOT RE-EXECUTED |
| Governance Freeze | 未开始 | 保持独立后续阶段 | NOT STARTED |
## 6. 总体执行设计

未来执行链设计为：
```text
Role Confirmation Package Preparation
↓
Natural Person Identity Verification
↓
Qualification Confirmation
↓
Independence Declaration
↓
Segregation of Duties Cross-check
↓
Package Content Freeze
↓
Signature Execution
↓
Activation Readiness Check
↓
ACTIVE_FOR_VALIDATION / BLOCKED / REJECTED
```
该链路只面向人工验证角色就绪，不授予 Authorization、系统权限、业务批准权或 Controlled Evidence Build 执行权。
## 7. Role Confirmation Package（角色确认包）设计

### 7.1 每角色必备字段

| 字段 | 要求 |
|---|---|
| role_confirmation_id | 未来唯一编号；本轮不创建 |
| package_version | 确认包精确版本 |
| role_name | Validation Owner 或指定专业角色 |
| required_responsibility | 验证职责说明，不是 OOM Responsibility 主数据 |
| qualification_requirement | 专业能力、经验和适用基线要求 |
| validation_objects | 被验证对象 |
| scenario_scope | 可签署的 Scenario ID 范围 |
| decision_scope | 可以作出的 PASS/FAIL/BLOCKED 结论范围 |
| prohibited_substitution | 不得替代的其他角色 |
| effective_from | 生效起点 |
| effective_to | 失效终点 |
| confirmation_status | 当前确认状态 |
| source_document_hashes | 适用设计和执行规范 SHA256 |
### 7.2 必需角色覆盖

确认包必须覆盖：Validation Owner、Architecture Reviewer、Security Reviewer、Data Reviewer、Process Reviewer、Evidence Reviewer 和 Independent Observer。
Recorder、Issue Owner、Re-validator、Signature Custodian、Validation Lead 等支撑角色按验证计划增加，但不能替代七类必需角色。
### 7.3 包状态

本轮所有实例字段保持空白，包状态为 `NOT_CREATED`；报告中出现的字段名和流程不构成真实 Role Confirmation Package。
## 8. Natural Person Confirmation（自然人确认）设计

### 8.1 确认字段

| 字段 | 验证要求 | 保存原则 |
|---|---|---|
| natural_person_identifier | 组织内可唯一追踪的 person_id | 必须具名、不可共享 |
| verified_name | 与权威身份来源一致 | 不在本报告填写 |
| organization_affiliation | 当前组织归属 | 记录来源和核验时间 |
| current_assignment | 当前正式任职或工作分配 | 只读核验，不修改组织事实 |
| proposed_validation_role | 拟承担验证角色 | 不等于 Role/Permission |
| contact_channel | 未来签署通知渠道 | 最小必要记录 |
| conflict_declaration | 独立性声明引用 | 必须绑定相同 person_id |
| availability_confirmation | 验证期和复验期可履职 | 明确有效窗口 |
| identity_verifier | 独立核验人 | 不得为候选本人 |
| verified_at | 可信时间 | 追加记录 |
### 8.2 身份核验来源

未来核验应读取已有权威员工/人员身份来源及正式任职事实，但不因核验创建或修改 Employee、User、Role、Permission 或 Employee Assignment。
只保存核验引用、结果和必要摘要；不在签署包复制不必要的身份证件、敏感号码或完整人事档案。
### 8.3 禁止替代

以下信息不能单独证明自然人身份：

- Role Code（角色编码）；
- Permission（权限）；
- Account Name（账号名称）；
- 邮箱别名、共享账号或群组；
- 超级管理员身份；
- 历史验证记录中的旧姓名。
### 8.4 核验结果

| 结果 | 含义 | 后续 |
|---|---|---|
| IDENTITY_CONFIRMED | 身份、归属和 person_id 一致 | 进入资格与独立性确认 |
| REVIEW_REQUIRED | 来源不一致或资料需补充 | BLOCKED |
| IDENTITY_REJECTED | 共享身份、伪冒或无法追责 | REJECTED |
| EXPIRED | 核验超出有效期 | 重新核验 |
## 9. Qualification Confirmation（资格确认）设计

### 9.1 检查内容

- 身份与拟承担角色一致；
- 专业能力证据覆盖对应验证对象；
- 已阅读并理解适用的冻结基线；
- 可在有效期内参加验证、问题处理和必要复验；
- 未被授予超出验证所需的系统或业务权限；
- 对应角色不存在禁止替代关系。
### 9.2 资格结论

| 状态 | 语义 | 是否继续 |
|---|---|---|
| QUALIFIED_FOR_SCOPE | 仅对冻结范围合格 | YES |
| QUALIFICATION_INCOMPLETE | 证据不足 | NO，BLOCKED |
| NOT_QUALIFIED | 专业能力或身份不适用 | NO，REJECTED |
| QUALIFICATION_EXPIRED | 有效期结束 | NO，重新确认 |
资格确认不能授予任命、权限或最终裁决权；它只是后续签署的前置证据。
## 10. Independence Declaration（独立性声明）执行设计

### 10.1 声明内容

每名拟参与者必须以同一 person_id 声明：

- 是否参与被验证治理设计；
- 是否负责被验证对象；
- 是否参与相关 Issue 修复；
- 是否是 Request Owner、Approver、Executor 或 Evidence Owner；
- 是否参与 Governance Freeze 或其他最终裁决；
- 是否与其他参与者存在汇报、利益或控制关系；
- 是否使用代理、共享账号或超级管理员身份；
- 是否存在其他影响独立判断的事项。
### 10.2 执行步骤

1. Signature Custodian 提供冻结版本声明表；
2. 候选自然人逐项作出声明，不允许默认勾选 CLEAR；
3. Conflict Reviewer 对照人员矩阵和工作关系复核；
4. Independent Observer 检查申报是否完整、是否存在未披露关系；
5. 形成结果和处置，不覆盖原始申报；
6. 声明或关系变化时创建新版本并重新检查。
### 10.3 声明结果

| 结果 | 适用条件 | 处置 |
|---|---|---|
| CLEAR | 无已知实质冲突 | 进入职责分离确认 |
| REVIEW_REQUIRED | 信息不足或潜在冲突待裁决 | BLOCKED |
| CONFLICT | 已确认存在冲突 | 按可补正/不可豁免规则处置 |
`CONFLICT` 若可通过更换人员或缩小范围合法消除，则保持 BLOCKED 并重检；若命中不可豁免组合，则 REJECTED。
## 11. Segregation of Duties（职责分离）确认设计

### 11.1 强制禁止组合

| 组合 | 结果 | 处置 |
|---|---|---|
| Designer + Final Validator | REJECTED | 指定独立最终验证人 |
| Request Owner + Approver | REJECTED | 更换其中一方 |
| Executor + Evidence Reviewer | REJECTED | 指定独立证据审核人 |
| Fix Owner + Verifier | REJECTED | 指定独立 Re-validator |
| Approver + Independent Observer | REJECTED | 独立观察人不得参与批准 |
### 11.2 补充检查

| 组合或条件 | 结果 |
|---|---|
| Validation Owner 覆盖全部专业 Reviewer | REJECTED |
| Scenario Owner 是唯一 Scenario Reviewer | REJECTED |
| Evidence Owner 是唯一 Evidence Reviewer | REJECTED |
| Independent Observer 兼任任一必需 Reviewer | REJECTED |
| 共享账号承担任一签署角色 | REJECTED |
| 必需角色尚无人选 | BLOCKED |
| 身份或关系信息待补充 | BLOCKED |
### 11.3 确认算法

职责分离以 person_id 进行全矩阵交叉比较，而不是比较角色名称、账号或 Permission。
每次提交、人员替换、角色范围变化、签署前和激活前均重新运行同一检查；结果和矩阵版本进入签署包。
## 12. Signature Package（签署包）执行设计

### 12.1 包内容

- Validation Role Matrix；
- Named Person Confirmation Sheet（人员确认表）；
- Qualification Confirmation；
- Independence Declaration；
- Segregation of Duties Check Result；
- Scope & Effective Period；
- Source Document Version and SHA256；
- Reservations and Outstanding Issues；
- Signature Order and Required Signers；
- signature_date、signature_method 和 signature_reference 字段。
### 12.2 内容冻结

签署前由 Signature Custodian 核对角色、自然人、范围、有效期、声明、冲突矩阵和源文件 Hash，生成待签版本。
冻结后人员、范围、有效期或输入 Hash 变化必须使当前包失效，形成新版本并重新执行受影响检查；禁止手工覆盖旧包。
### 12.3 签署顺序

1. 候选自然人签署身份、职责接受和独立性声明；
2. Qualification Reviewer 签署资格核验结论；
3. Conflict Reviewer 签署职责分离矩阵；
4. Independent Observer 签署程序与冲突复核；
5. Appointment Authority 未来签署真实任命决定；
6. Validation Owner 确认角色集合和会话准备；
7. Signature Custodian 完整性核验并封存签署包。
本轮不指定上述自然人，不执行任何一步签署。
### 12.4 签名绑定要求

每个签名必须绑定：person_id、角色、范围、package_version、package_sha256、签署时间、签署方法和签署意图。
仅有图片签名、账号登录、Role Code、邮件转发或口头同意均不能单独构成合格签署。
### 12.5 拒签、撤回和替换

拒签必须记录原因并使流程 BLOCKED；撤回或人员替换必须追加事件、废止旧签署并创建新版本。
任何过期、Hash 不匹配或范围不一致的签署不得用于 `ACTIVE_FOR_VALIDATION`。
### 12.6 签署结果边界

`Signature Package = COMPLETE` 只证明指定自然人接受角色、资格和独立性检查完成；它不等于 Human Validation PASS、Governance Freeze、Authorization Granted 或 Implementation Authorized。
## 13. Role Confirmation 状态设计

### 13.1 主状态机

```text
NOT_STARTED
↓
PREPARED
↓
IDENTITY_CONFIRMED
↓
INDEPENDENCE_CONFIRMED
↓
SIGNED
↓
ACTIVE_FOR_VALIDATION
```
### 13.2 转换门禁

| 转换 | 必备条件 | 触发主体 | 禁止条件 |
|---|---|---|---|
| NOT_STARTED → PREPARED | 角色包内容齐全 | Signature Custodian | 范围或版本不明 |
| PREPARED → IDENTITY_CONFIRMED | person_id、归属和身份核验通过 | Identity Verifier | 共享账号或身份不一致 |
| IDENTITY_CONFIRMED → INDEPENDENCE_CONFIRMED | 资格合格、声明 CLEAR、SoD 通过 | Conflict Reviewer | 声明缺失或冲突未处置 |
| INDEPENDENCE_CONFIRMED → SIGNED | 全部必需签署绑定同一版本 | Signature Custodian | 缺签、过期或 Hash 漂移 |
| SIGNED → ACTIVE_FOR_VALIDATION | Readiness Gate 全部通过 | Validation Owner + Independent Observer | 任一角色或输入失效 |
### 13.3 异常状态

| 状态 | 触发 | 后续 |
|---|---|---|
| BLOCKED | 材料、人员、声明或签署可补正缺失 | 补正后新版本重检 |
| REJECTED | 不可豁免冲突、共享身份或故意绕过 | 更换候选配置 |
| EXPIRED | 有效期结束 | 重新实名确认和签署 |
| REVOKED | 签署后发现身份、独立性或完整性失效 | 停止验证并保留证据 |
| SUPERSEDED | 新版本替代 | 旧版本只读归档 |
`SIGNED ≠ ACTIVE_FOR_VALIDATION`；只有独立 Readiness Gate 复检通过才能激活验证角色。
本轮不创建任何状态实例，所有真实状态仍为 NOT STARTED/NOT EXECUTED。
## 14. HVX Issue Closure Mapping（问题关闭映射）

### 14.1 HVX-I01：缺少具名验证角色

进入 `RESOLVED` 的未来证据：角色名单确认、自然人身份确认、资格确认、真实任命和签署包完成。
进入 `VERIFIED` 的额外条件：独立 Re-validator 检查签署包，并按执行规范重新执行全部正式场景。
本轮状态：`OPEN`；未创建任何实名或签署证据。
### 14.2 HVX-I02：缺少自然人独立性证明

进入 `RESOLVED` 的未来证据：全部独立性声明完成、person_id 交叉冲突检查通过、Independent Observer 签署。
进入 `VERIFIED` 的额外条件：独立 Re-validator 复验声明、关系和职责分离矩阵。
本轮状态：`OPEN`；无真实声明或冲突检查。
### 14.3 HVX-I03：缺少冲突判别矩阵

进入 `RESOLVED` 的未来证据：判别矩阵冻结、BLOCKED/REJECTED 语义确认、所有验证人员确认理解。
进入 `VERIFIED` 的额外条件：场景 S04 和相关负向路径完成一致性复验。
本轮状态：`OPEN`；已有候选矩阵但尚未人工冻结或复验。
### 14.4 状态保护

签署包完成只能为 Issue Owner 提交 `RESOLVED` 提供证据；Issue Owner 不得自标 `VERIFIED`，原始 BLOCKED 结果不得覆盖。
## 15. 与 Human Validation（人工验证）的关系

```text
Role Preparation Complete
↓
Real Person Confirmation
↓
Independence & SoD Confirmation
↓
Signature Complete
↓
Activation Readiness Check
↓
Human Validation Execution
↓
Validation Result
```
规则：

- 实名确认不等于任命；
- 任命不等于签署完成；
- 签署完成不等于角色已激活；
- 角色激活只允许开始验证，不预设 PASS；
- 正式验证必须创建新的记录，不修改原执行报告；
- 当前 `Human Validation Result = BLOCKED` 在正式复验完成前不变。
## 16. 与 Governance Freeze（治理冻结）的关系

即使未来角色签署完成，仍需：Human Validation 全场景执行、P0/P1/P2 Issue 独立复验、Human Validation PASS 和独立 Governance Freeze Review。
Validation PASS 只允许提出冻结评审；Freeze Recommendation 不等于 Freeze Decision。
Governance Freeze 仍不等于 Controlled Evidence Build Authorization、OOM-4.2 或任何实施授权。
## 17. 未来执行检查清单

| ID | 检查 | 通过标准 | 本轮状态 |
|---|---|---|---|
| RCS-01 | 角色包 | 七类必需角色均有冻结要求 | DESIGNED |
| RCS-02 | 自然人身份 | person_id 与权威来源一致 | NOT EXECUTED |
| RCS-03 | 组织归属 | 当前归属和任职只读核验 | NOT EXECUTED |
| RCS-04 | 资格 | 专业能力和范围匹配 | NOT ASSESSED |
| RCS-05 | 独立性 | 每人声明且结果 CLEAR | NOT DECLARED |
| RCS-06 | 职责分离 | 全 person_id 矩阵通过 | NOT CHECKED |
| RCS-07 | 内容冻结 | package_version 和 Hash 固定 | NOT CREATED |
| RCS-08 | 必需签署 | 顺序、范围和意图完整 | NOT SIGNED |
| RCS-09 | 有效期 | 所有签署覆盖验证窗口 | NOT CHECKED |
| RCS-10 | Readiness Gate | 所有输入、角色和安全项通过 | NOT STARTED |
| RCS-11 | Issue | HVX-I01～I03 独立复验 | NOT STARTED |
| RCS-12 | 人工验证 | 新记录执行 S01～S06 | NOT STARTED |
## 18. 风险与控制

| 风险 | 影响 | 控制 |
|---|---|---|
| 账号名替代自然人 | 无法追责 | 权威来源 + person_id 双核验 |
| 复制敏感身份材料 | 隐私扩大 | 仅保存核验引用和最小摘要 |
| 资格确认被误作任命 | 越过有权主体 | 独立 Appointment Decision |
| 默认勾选 CLEAR | 隐藏冲突 | 逐项声明和独立复核 |
| 角色名称掩盖同人 | SoD 失效 | 全矩阵按 person_id 比较 |
| Approver 兼 Observer | 观察不独立 | 强制 REJECTED |
| 签名图片与版本脱离 | 无法证明意图 | 绑定版本、Hash、范围和时间 |
| 签署后静默换人 | 证据失真 | 旧包失效，新版本重签 |
| SIGNED 自动激活 | 跳过门禁 | 独立 Activation Readiness Check |
| 角色激活预填 PASS | 结论失真 | 场景现场记录、禁止预填 |
| Issue 过早关闭 | BLOCKED 被掩盖 | RESOLVED/VERIFIED 分离 |
| 签署完成自动冻结 | 越过治理裁决 | 独立 Freeze Review/Decision |
## 19. 设计验收标准

本方案完成必须满足：

- Role Confirmation Package 字段、范围和状态明确；
- 自然人确认不能由 Role、Permission 或 Account Name 替代；
- 独立性声明有明确步骤和 CLEAR/CONFLICT/REVIEW_REQUIRED 结果；
- 用户指定的五类禁止组合全部进入 SoD 矩阵；
- 签署内容、顺序、身份绑定、失效和替换规则完整；
- `SIGNED ≠ ACTIVE_FOR_VALIDATION` 明确；
- HVX-I01～I03 关闭映射不预填 RESOLVED/VERIFIED；
- Human Validation 和 Governance Freeze 边界保持不变；
- 不出现真实人员、真实签名、状态实例或权限变更。
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
补充保护：
```text
Natural Person Confirmed = NO
Real Person Appointed = NO
Governance Role Record Created = NO
Signature Record Created = NO
Human Validation Re-executed = NO
HVX Issue Status Changed = NO
```
## 21. 最终状态

```text
Controlled Evidence Build Authorization Human Validation Role Identity Confirmation & Signature Preparation Design = COMPLETE
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
本报告完成后立即停止。下一步只能由人工决定是否启动真实人员确认、独立性申报和签署；不得直接执行 Human Validation，不得发起 Governance Freeze，不得签发 Controlled Evidence Build Authorization 或进入任何实施活动。
