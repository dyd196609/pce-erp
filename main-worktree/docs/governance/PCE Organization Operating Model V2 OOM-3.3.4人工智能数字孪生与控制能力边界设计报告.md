# PCE Organization Operating Model V2 OOM-3.3.4 人工智能、数字孪生与控制能力边界设计报告

日期：2026-08-18  
阶段：OOM-3.3.4 AI / Digital Twin / Control Capability Boundary Design（人工智能、数字孪生与控制能力边界设计）  
类型：DESIGN ONLY（仅设计）  
实施授权：NOT AUTHORIZED（未授权实施）

## 1. 设计结论

本报告冻结 AI（人工智能）、Digital Twin（数字孪生）与 Control（控制体系）在 Organization Operating Model（企业组织运行模型，OOM）中的能力边界。

- AI 可以发现异常、解释证据、推荐配置、生成非正式建议和辅助影响分析；不能创建、修改、批准或生效组织事实。
- Digital Twin 可以读取正式事实、形成时点快照、模拟拟议变更和预测解析影响；不能成为 Company、Organization Unit、Position、Responsibility、PositionResponsibility 或 Employee Assignment 的事实来源。
- Control 可以执行确定性校验、阻断不合规动作、告警和留证；不能自动修复企业事实。
- Autonomous Execution（自治执行）不得用于组织主数据变更。即使风险被标记为 LOW，也不能无人值守创建岗位、责任、岗位责任或员工任职。
- AI、Digital Twin 和 Control 的输出只能进入“观察、建议、模拟、阻断”通道；需要改变事实时必须由人提出 Change Request（变更申请）。
- Business Action Contract（业务动作契约，BAC）、AuthorizationService（统一授权服务）、OrganizationOperatingService（组织运作服务）和人工审核批准闭环保持权威。
- 本报告不修改现有自治代码，只记录其与 OOM 治理边界的兼容风险。

## 2. 已读取正式基线与判断依据

### 2.1 BAC 基线

路径：

- `D:\Dev-PCE\Source\docs\governance\PCE Business Action Contract V1 BAC-0架构签发报告.md`
- `D:\Dev-PCE\Source\docs\governance\PCE Business Action Contract V1 BAC-1架构与契约定义设计报告.md`

用途：确认服务端 BAC 是 Business Action（业务动作）唯一事实来源，以及 `requiredResponsibility`、`requiredPermission` 分离。

关键原文：

> “当前仓库尚未实施完整 Server Business Action Contract，尤其尚未建立 `requiredResponsibility` 字段。”

> “未来也只能引用 Server Contract 中已有 `actionCode`，不能独立创建动作语义。”

判断：AI、Digital Twin 和 Control 不得创建 actionCode、Responsibility 或 Permission，也不得修改 BAC 引用。

### 2.2 OOM 对接、治理矩阵与变更闭环

路径：

- `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 与 Business Action Contract 对接设计报告.md`
- `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-3.1主数据责任与治理矩阵设计报告.md`
- `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-3.2组织主数据变更流程与治理闭环设计报告.md`

用途：确认组织事实源、Data Owner（数据所有者）、Data Steward（数据管理员）、Reviewer（审核人）、Approver（批准人）和变更闭环。

关键原文：

> “当前 `system.Responsibility` 已经是独立责任目录事实源；BAC 只能引用其编码，不能生成责任。”

> “企业事实由业务 Data Owner 定义，由 Data Steward 维护，由独立 Reviewer 审核，由独立 Approver 批准生效。”

> “正式组织事实不得因页面编辑或操作者拥有维护权限而直接改变。”

判断：算法建议没有 Data Owner、Reviewer 或 Approver 法定地位；任何写入意图必须回到人工治理链。

### 2.3 OOM-3.3.2 与 OOM-3.3.3

路径：

- `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-3.3.2组织主数据变更管理能力边界设计报告.md`
- `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-3.3.3治理权限与角色边界设计报告.md`

用途：确认 Change Request 独立对象、唯一事实执行入口、治理指派与 Permission 双条件。

关键原文：

> “OrganizationOperatingService 应作为唯一组织事实执行入口。”

> “拥有 Permission 的用户不会因此自动成为责任人、Reviewer 或 Approver。”

判断：AI 不能模拟用户、获取治理角色、接受指派或调用组织事实执行入口。

### 2.4 Responsibility Resolution Engine（责任解析引擎，RRE）设计

路径：`D:\Dev-PCE\Source\docs\governance\PCE责任解析引擎V1设计报告.md`  
用途：确认 RRE 只读解析、Evidence（证据）和异常策略。

关键原文：

> “V1 Read-only Resolution（V1只读解析）= 现有模型足够。”

> “解析引擎本身不创建任务、不推进状态。”

> “差异只报告，不自动修复。”

判断：AI 或 Control 不能借 RRE 输出自动调整岗位、责任或员工任职；多候选和无候选必须显式保留。

### 2.5 Autonomous ERP（自治 ERP）说明

路径：`D:\Dev-PCE\Source\docs\Full Autonomous ERP OS.md`  
用途：核对当前自治架构愿景。

关键原文：

> “It can decide, execute, repair, and continue enterprise workflows without manual approval.”

> “Low-risk processes can execute without manual approval.”

判断：该通用愿景与 OOM 正式主数据的人工治理要求存在直接冲突。OOM 领域必须设置更严格的 Domain Boundary（领域边界）：组织事实永远不适用“低风险免人工批准”。

## 3. 当前代码能力与风险

### 3.1 Enterprise Digital Twin

路径：`D:\Dev-PCE\Source\frontend\src\meta\digitalTwin\enterpriseDigitalTwinEngine.js`  
用途：构建企业状态、模拟流程、预测 KPI 和风险。

关键原文：

```javascript
export function buildEnterpriseState(context = {})
export function simulateWorkflow(state = {})
export function forecastKPIs(state = {})
export function predictDecision(state = {})
```

判断：模拟与预测能力可以用于只读影响分析，但输入必须来自服务端正式事实并带来源、时点和版本；预测结果不能作为组织写入 Payload。

路径：`D:\Dev-PCE\Source\frontend\src\platform\twin\digitalTwinV20.js`  
关键原文：

```javascript
export const updateTwin = (id, state) => { ... }
export const simulate = (id, action) => { ... simulated: true }
```

判断：`updateTwin` 只能更新内存孪生观察状态，名称不得被解释为更新正式组织事实；Twin State 不是服务端权威事实。

### 3.2 AI 与自治决策

路径：`D:\Dev-PCE\Source\frontend\src\meta\governance\autonomousGovernanceEngine.js`  
关键原文：

```javascript
autoExecutable: decision.recommendation === 'AUTO_APPROVE'
```

路径：`D:\Dev-PCE\Source\frontend\src\meta\autonomy\autonomousExecutionEngine.js`  
关键原文：

```javascript
executed: executionAllowed
unattendedMode: ... ? 'ACTIVE' : 'CONTROLLED'
```

路径：`D:\Dev-PCE\Source\frontend\src\platform\ai\autonomousLoopV21.js`  
关键原文：

```javascript
executeAutonomy(decision, instance.meta)
```

判断：这些代码含自动批准、自动执行或无人值守语义。在没有代码修改授权的本轮，只能登记为 OOM 接入阻断风险；它们不得接收组织治理动作、组织 Change Request 或 OrganizationOperatingService 写权限。

### 3.3 Control Tower

路径：

- `D:\Dev-PCE\Source\frontend\src\meta\core\metaControlTower.js`
- `D:\Dev-PCE\Source\frontend\src\meta\pages\ControlTower.vue`

用途：事件追踪、日志和优化动作展示。

关键原文：

```javascript
console.log(`[CONTROL TOWER] ${event}`, payload)
```

判断：当前能力以观察和前端展示为主。Console 或页面 action 不是审计事实，不能替代 OrganizationOperatingAuditRecord 或 Change Request Evidence。

## 4. 总体系统能力边界

| 能力层 | 允许 | 禁止 |
|---|---|---|
| AI | 推荐、解释、分类、预测、生成非正式草案 | 创建事实、提交/审核/批准、生效 |
| Digital Twin | 服务端事实快照、时点重放、模拟、差异预测 | 作为事实源、回写、改状态 |
| Control | 确定性校验、阻断、告警、证据、指标 | 自动修复、自动选人、自动授权 |
| RRE | 只读解析与 Evidence | 创建责任、任务或组织事实 |
| Workflow | 经授权承载过程 | 决定企业事实或责任人 |
| AuthorizationService | ALLOW/DENY 与证据 | 业务批准、责任发现 |
| OrganizationOperatingService | 执行获批变更 | 接受 AI/Twin 直接写入 |

## 5. AI（人工智能）能力边界

### 5.1 允许能力

- 分析无责任岗位、无员工岗位、责任空档和多人候选；
- 推荐可能需要新增或调整的责任配置；
- 对 Change Request 生成影响分析草稿和风险说明；
- 解释 BAC、Responsibility、PositionResponsibility、Employee Assignment 与 RRE Evidence；
- 比较变更前后组织结构和候选变化；
- 发现数据异常、重复编码、语义冲突和历史断层；
- 为 Data Steward 提供非正式建议，明确模型版本、置信度和输入来源。

### 5.2 禁止能力

- 自动创建 Company、Organization Unit、Position、Responsibility、PositionResponsibility 或 Employee Assignment；
- 自动提交 Change Request；
- 作为 Reviewer、Approver、Data Owner 或 Data Steward；
- 自动决定责任人、审批人、岗位或员工迁移目标；
- 自动授予 Role/Permission 或调用 AuthorizationService 冒充用户；
- 自动修改 BAC、Workflow、ApprovalTask 或 RRE 配置；
- 因风险评分为低而自动批准、生效或修复事实；
- 把模型输出当作 Before/After 正式证据。

### 5.3 AI 输出契约

AI 建议至少包含：建议编号、生成时间、模型/规则版本、输入事实来源、事实时点、建议内容、置信度、已知限制、影响对象和“非正式、未批准、零写入”标记。

AI 建议只能被人引用到新的 Change Request 草稿；引用不等于采纳，且申请人必须重新确认内容和原因。

## 6. Digital Twin（数字孪生）能力边界

### 6.1 允许读取

- Organization 当前与历史状态；
- Position 生命周期、组织归属和分类；
- Responsibility 状态及 BAC 引用；
- PositionResponsibility 有效区间；
- Employee Assignment 主岗、兼岗、代理与历史；
- Change Request 状态、Impact Analysis 和批准结果；
- RRE 只读解析结果与 Evidence；
- Authorization 决策摘要，但不得复制敏感权限明细给无权用户。

### 6.2 允许模拟

- 组织单元调整、合并与停用后的结构差异；
- 岗位创建、迁移或退役后的责任缺口；
- 岗位责任变更后的无候选、多候选和有效期冲突；
- 员工调岗、离岗、兼岗或代理后的责任候选变化；
- Responsibility 暂停/退役对 BAC 和 RRE 的影响；
- 拟议 Change Request 在不同生效时点的结果。

### 6.3 禁止能力

- Digital Twin 状态成为正式事实源；
- Twin `update` 调用正式组织写接口；
- 模拟结果自动转为 Approved Change Request；
- 预测结果自动改变 Responsibility、Position 或 Employee Assignment；
- 以 Twin Snapshot 替代服务端回读或审计；
- 删除、覆盖或“修复”历史事实。

### 6.4 Snapshot（快照）证据

每个孪生快照必须声明：sourceContract、sourceObjectIds、asOfTime、sourceVersions、snapshotHash、readOnly、generatedAt 和 accessScope。来源不完整时结果必须标记 `INCOMPLETE_FACTS`，不得补前端缓存。

## 7. Control（控制体系）能力边界

### 7.1 Preventive Control（预防性控制）

- 阻断未注册 Business Action；
- 阻断无 Permission、Scope 不符或职责分离冲突；
- 阻断页面、AI、RRE、Workflow 直接写组织事实；
- 阻断责任编码重复、岗位/责任跨公司、组织循环；
- 阻断有效期重叠、非法回溯和批准后 Payload 漂移；
- 阻断未批准或未到生效时间的 OrganizationOperatingService 执行。

### 7.2 Detective Control（侦测性控制）

- 无 Responsibility 的 Position；
- 有 Responsibility 但无有效 PositionResponsibility；
- 有岗位责任但无有效 Employee Assignment；
- 多岗位或多人造成的 MULTIPLE_CANDIDATES；
- Responsibility 已暂停/退役但 BAC 仍引用；
- Position 已停用但仍存在未来任职或岗位责任；
- Employee Assignment 时间重叠、空档或代理过期；
- Digital Twin 与正式服务端事实版本漂移；
- AI 输出缺来源、时点、版本或置信度。

### 7.3 Corrective Control（纠正性控制）

允许：创建告警、形成缺陷单、生成非正式修正建议、准备 Change Request 草稿、要求人工复核。  
禁止：自动修复 Company、Organization Unit、Position、Responsibility、PositionResponsibility、Employee Assignment、Role、Permission 或 Workflow。

### 7.4 Control Evidence（控制证据）

控制结果应记录 controlCode、controlVersion、severity、objectType/objectId、sourceFacts、detectedAt、result、reason、recommendedAction、writeCount。阻断类控制必须固定 `writeCount = 0`。

## 8. AI、Twin、Control 与治理闭环关系

```text
Formal Server Facts（正式服务端事实）
→ Digital Twin Snapshot（只读孪生快照）
→ AI / Control Analysis（建议与检测）
→ Human Decision（人工决定）
→ Change Request Draft（人工确认后形成草稿）
→ Review / Approval（人工审核批准）
→ AuthorizationService
→ OrganizationOperatingService
→ Audit + Server Readback
```

禁止链：`AI/Twin/Control → Direct Organization Write`。

## 9. 风险等级与自动化规则

| 场景 | 自动分析 | 自动阻断 | 自动写入 |
|---|---|---|---|
| 只读异常扫描 | 允许 | 不适用 | 禁止 |
| 无责任/无员工岗位 | 允许 | 可阻断后续执行 | 禁止 |
| 多候选 | 允许 | 必须阻断自动选择 | 禁止 |
| 责任退役仍被引用 | 允许 | 必须阻断退役 | 禁止 |
| 组织循环/跨公司 | 允许 | 必须阻断 | 禁止 |
| AI 推荐低风险调整 | 允许 | 不自动阻断人工查看 | 禁止 |
| 已批准且到时的变更 | 可再校验 | 条件失败即阻断 | 仅组织服务可执行 |

组织主数据不存在“低风险 AI 自动生效”类别。

## 10. 接入隔离要求

在后续任何实施授权前必须保证：

1. 自治引擎不能导入组织写 API 或 OrganizationOperatingService 写适配器；
2. AI/Twin/Control 使用只读 Provider，技术凭据没有组织写 Permission；
3. 输出对象与正式 Domain Model 类型分离，并带 `advisory`、`simulation` 或 `controlEvidence` 标识；
4. Control Tower 页面按钮不能直接执行组织变更；
5. `AUTO_APPROVE`、`autoExecutable`、`unattendedMode` 对 OOM 对象强制无效；
6. 任何建议转申请都必须由已登录自然人确认，并重新经过 AuthorizationService；
7. 模拟数据、Fixture、前端缓存不得成为 Impact Analysis 正式证据；
8. 未经 BAC-1、OOM-4、RRE-1 和 Workflow Integration 独立授权，不建立连接。

## 11. 验收设计

| 编号 | 场景 | 预期结果 |
|---|---|---|
| AITC-01 | AI 推荐新 Responsibility | 只显示建议，正式责任数量不变 |
| AITC-02 | AI 尝试提交/批准 Change Request | 拒绝，写入 0 |
| AITC-03 | Twin 模拟部门合并 | 返回模拟差异，不改组织树 |
| AITC-04 | Twin Snapshot 缺事实版本 | `INCOMPLETE_FACTS`，禁止作为证据 |
| AITC-05 | Control 发现组织循环 | 阻断拟议变更，正式事实不变 |
| AITC-06 | Control 发现多候选 | 报告冲突，不自动选人 |
| AITC-07 | `AUTO_APPROVE` 作用于组织责任 | 强制拒绝 |
| AITC-08 | Autonomous Engine 调组织写入口 | 权限/边界拒绝，写入 0 |
| AITC-09 | Control Tower 执行优化动作 | 仅建议/导航，不直接写组织事实 |
| AITC-10 | 人工引用 AI 建议创建草稿 | 允许草稿，必须重新审核批准 |
| AITC-11 | RRE 返回无候选 | 保留未解析，不自动修复 |
| AITC-12 | Digital Twin 与服务端漂移 | 标记失效并重新构建快照 |

## 12. OOM-4 前置条件

进入 Organization Model Implementation（组织模型实施）前必须完成：

1. AI、Digital Twin、Control 的只读/建议/阻断边界人工批准；
2. OOM 对象永不适用 AI 自动批准和无人值守执行的规则冻结；
3. AI 建议、Twin Snapshot、Control Evidence 输出契约冻结；
4. 只读 Provider、凭据和 Permission 隔离方案完成；
5. Autonomous Engine 与组织写服务的静态/运行时隔离门禁设计完成；
6. Control 检测目录、严重度、阻断条件和证据要求冻结；
7. 模拟结果转 Change Request 草稿的人工确认规则冻结；
8. 数据漂移、事实不完整和模型不确定性的失败策略冻结；
9. AITC-01～AITC-12 验收方案获批；
10. 每项代码、API、页面、Permission 和集成另行授权。

## 13. 保护确认

本轮只新增本设计报告，未修改或接入现有 AI、Digital Twin、Control、Workflow、RRE 或组织服务。

`Documentation Changed = YES`。  
`Code Changed = NO`；`Database Changed = NO`；`Migration Created = NO`；`API Created = NO`；`Page Created = NO`。  
`Organization Data Changed = NO`；`Responsibility Data Changed = NO`；`Employee Data Changed = NO`。  
`Permission Model Changed = NO`；`AuthorizationService Changed = NO`；`Workflow Runtime Changed = NO`。  
`ApprovalTask Changed = NO`；`RRE Started = NO`；`Autonomous Organization Execution = NO`。  
`Unauthorized Business Writes = 0`。

## 14. 最终状态

`OOM-3.3.4 AI / Digital Twin / Control Capability Boundary Design = COMPLETE`。  
`OOM-3.3 Split Design = COMPLETE`。  
`Organization Model Implementation = NOT AUTHORIZED`；`OOM-4 = NOT STARTED`。  
`RRE-1 = NOT AUTHORIZED`；`Workflow Integration = NOT AUTHORIZED`。  
`AI Organization Write = PROHIBITED`；`Digital Twin Organization Write = PROHIBITED`。

本报告完成后停止，等待下一阶段架构决策。
