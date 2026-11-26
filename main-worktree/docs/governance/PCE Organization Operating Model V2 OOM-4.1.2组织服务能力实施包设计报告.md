# PCE Organization Operating Model V2 OOM-4.1.2 组织服务能力实施包设计报告

日期：2026-08-18  
阶段：OOM-4.1.2 Organization Service Capability Implementation Package Design（组织服务能力实施包设计）  
任务性质：DESIGN ONLY（仅设计）  
实施授权：NOT AUTHORIZED（未授权实施）

## 1. 设计目标与结论

本报告设计未来获得明确实施授权后，OrganizationOperatingService（组织运作服务）及相关只读、治理、影响分析和审计能力的实施边界。

总体结论：

1. 复用现有 `OrganizationOperatingService` 作为组织正式事实的唯一执行入口，不建立第二套组织事实写服务。
2. 复用 `EnterpriseOrganizationModelService` 作为综合组织模型的服务端只读投影，复用 `ResponsibilityCatalogService` 作为以 `system.Responsibility` 为根事实的责任目录投影。
3. 当前服务已经具备动作注册、AuthorizationService（统一授权服务）校验、组织范围校验、事务、领域校验、Before/After 审计和刷新回读基础。
4. 当前写链在授权通过后直接修改正式事实，尚未具备 Change Request（变更申请）、独立审核、独立批准、未来生效执行、执行幂等和完整审批证据。
5. 目标写链必须改为“已批准变更申请 → 到期复核 → 唯一事实执行器 → 正式事实 → 审计”，页面、Workflow Runtime（流程运行引擎）、Runtime Adapter（运行时适配器）、RRE（责任解析引擎）均不得直接写组织事实。
6. OOM-4.1.1 已明确 Change Request 持久结构不在最小事实 Schema 包内。因此在其 Schema 决策和 Migration（数据库迁移）另行批准前，服务层只能完成设计，不能实施治理闭环。

```text
Organization Service Capability Design = PASS
Current Direct Maintenance Capability = REUSABLE WITH RECTIFICATION
Approved Change Execution Capability = NOT PRESENT
Organization Model Implementation = NOT AUTHORIZED
```

## 2. 已读取文件、用途、关键原文与判断

### 2.1 BAC（业务动作契约）基线

| 实际路径 | 文件用途 | 关键原文 | 判断依据 |
|---|---|---|---|
| `D:\Dev-PCE\Source\docs\governance\PCE Business Action Contract V1 BAC-0架构签发报告.md` | 冻结业务动作唯一事实源和责任/权限边界 | “Server Business Action Contract Registry = Business Action 的唯一运行事实来源” | 组织服务只能消费动作契约，不能注册业务动作 |
| `D:\Dev-PCE\Source\docs\governance\PCE Business Action Contract V1 BAC-1架构与契约定义设计报告.md` | 设计服务端契约模型、生命周期与消费者关系 | `requiredResponsibility` 与 `requiredPermission` 为独立字段 | 组织服务不得用 Permission（权限）替代 Responsibility（责任），也不得自行创建二者 |

BAC 冻结链路：

```text
Server Business Action Contract
↓ requiredResponsibility          ↓ requiredPermission
Responsibility                    AuthorizationService
```

结论：组织治理动作未来应引用已发布的服务端动作契约；BAC-1 尚未获得实施授权时，现有 `ACTION_PERMISSIONS` 只能作为受控兼容层，不能被宣布为完整 Business Action Contract（业务动作契约）。

### 2.2 OOM（企业组织运行模型）基线

已完整读取：

- `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 与 Business Action Contract 对接设计报告.md`
- `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-1实施方案设计报告.md`
- `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-2实施设计与Schema决策报告.md`
- `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-3数据治理与初始化方案设计报告.md`
- `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-3.1主数据责任与治理矩阵设计报告.md`
- `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-3.2组织主数据变更流程与治理闭环设计报告.md`
- `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-3.3.2组织主数据变更管理能力边界设计报告.md`
- `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-3.3.3治理权限与角色边界设计报告.md`
- `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-3.3.4人工智能数字孪生与控制能力边界设计报告.md`
- `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-4实施准入与验收门禁设计报告.md`
- `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-4.1.1组织模型Schema实施包设计报告.md`

共同关键原文和冻结判断：

```text
Change Request → Impact Analysis → Review → Approval
→ Effective Date → OrganizationOperatingService → Audit
```

```text
[effective_from, effective_to)
```

```text
Employee.position_ref = Current Primary Position Projection
EmployeePositionAssignment = 未来任职事实
PositionResponsibilityV2 = FORBIDDEN
```

判断：服务实施必须服从统一时态语义、历史不可删除、职责分离和唯一事实写入口；不能用服务代码补造尚未批准的 Schema。

### 2.3 权限与运行边界基线

| 实际路径 | 文件用途 | 关键原文 | 判断 |
|---|---|---|---|
| `D:\Dev-PCE\Source\docs\standards\PCE-BUSINESS-ACTION-PERMISSION-V1.0.md` | 动作权限和服务端复核标准 | “前端展示不是权限，服务端验证才是权限” | 所有维护动作必须重新调用 AuthorizationService |
| `D:\Dev-PCE\Source\docs\governance\PCE公共组织身份权限核心V1-最终人工验收与封板报告.md` | AuthorizationService 正式基线证据 | 页面 DENY 与后端 HTTP 403 一致 | 页面、路由、按钮均不能构成授权 |
| `D:\Dev-PCE\Source\docs\governance\Runtime职责规范.md` | Runtime 规范兼容入口 | “本文件不建立第二套 Runtime” | 必须继续读取其当前生效规范 |
| `D:\Dev-PCE\Source\docs\governance\PCE-ERP运行层文件职责规范.md` | Runtime/Provider/Page 职责 | “Runtime Adapter 只读，Business Write Count = 0” | Runtime Adapter 不得执行组织写入 |
| `D:\Dev-PCE\Source\docs\governance\02-架构与运行边界\PCE-ERP架构与运行边界规范.md` | Action、Guard、Persistence 总边界 | “Page → Action → Guard → Domain Transition → Persistence → Audit” | 组织写入必须经过服务端 Guard 和事务 |
| `D:\Dev-PCE\Source\docs\governance\03-业务流程运行治理\PCE-ERP业务流程运行治理规范.md` | Workflow 生命周期和人工决策边界 | Workflow 只承载受控节点，人工决定必须留证 | Workflow 可承载审核批准，不拥有组织事实 |

## 3. 当前服务能力审查

### 3.1 OrganizationOperatingService（组织运作服务）

实际路径：`D:\Dev-PCE\Source\backend\system\organization_operating.py`

文件作用：组织维护动作的 Action → Guard → Persistence → Audit（动作—校验—持久化—审计）执行服务。

关键原文：

```python
class OrganizationOperatingService:
    """Explicit Action -> Guard -> Persistence -> Audit service for organization maintenance."""
```

```python
decision = AuthorizationService.decide(
    user=user,
    action_code=permission_code,
    organization_id=str(user.company_id),
    business_object={"departmentId": department_id} if department_id else {},
)
```

```python
with transaction.atomic():
    result = handler(user=user, payload=payload, reason=reason)
```

```python
OrganizationOperatingAuditRecord.objects.create(
    action_code=action_code,
    actor=user,
    reason=reason,
    before_snapshot=before,
    after_snapshot=after,
)
```

当前可复用能力：

- 维护动作白名单与权限映射；
- 修改原因必填；
- 统一授权与组织/部门范围检查；
- 事务和行锁；
- 父子循环、跨公司、有效期、员工主管循环等领域校验；
- Company、OrganizationUnit、Department、JobFamily、JobLevel、Position、Responsibility、PositionResponsibility、Employee 和汇报关系写入；
- 每次成功写入形成 Before/After 审计；
- 返回服务端目标事实、授权证据、审计 ID 和写入数。

当前必须整改的能力：

- `execute()` 接到允许动作后直接调用保存处理器，未验证 Approved Change Request（已批准变更申请）；
- 没有申请编号、申请版本、审核人、批准人、批准版本和生效执行凭证；
- 没有幂等键和“一个申请只应用一次”的执行记录；
- 有效期字段存在，但更新会立即改变当前记录，尚未形成通用未来生效调度和 As Of（截至时点）读取；
- `SAVE_EMPLOYEE` 直接写 `Employee.position_ref`，尚未消费未来 EmployeePositionAssignment（员工岗位任职关系）；
- `SAVE_POSITION_RESPONSIBILITY` 仍以 `active/is_primary` 表达当前态，尚未消费 OOM-4.1.1 设计的时态字段；
- `ACTION_PERMISSIONS` 是本地兼容映射，不是已实施的服务端 Business Action Contract Registry（业务动作契约注册中心）。

### 3.2 EnterpriseOrganizationModelService（企业组织模型服务）

实际路径：`D:\Dev-PCE\Source\backend\system\enterprise_organization.py`

关键原文：

```python
class EnterpriseOrganizationModelService:
    """Read-only projection of canonical organization operating facts."""
```

```python
"strictFacts": {
    "factSource": "server",
    "authorizedBusinessWriteCount": 0,
    "unauthorizedBusinessWriteCount": 0,
    "workflowExecutionCount": 0,
}
```

判断：该服务已经是正确的服务端只读投影基础，可复用公司范围、部门范围、员工可见性、责任关系和严格事实诊断；未来必须增加 `asOf` 语义和任职事实投影，但不得在投影层重算或写入正式事实。

### 3.3 ResponsibilityCatalogService（责任目录服务）

实际路径：`D:\Dev-PCE\Source\backend\system\responsibility_catalog.py`

关键原文：

```python
RESPONSIBILITY_FACT_SOURCE = "system.Responsibility"

class ResponsibilityCatalogService:
    """Read-only projection whose root fact is always system.Responsibility."""
```

判断：责任目录唯一事实源正确；岗位关系只能作为关联信息，不能反向生成责任。未来继续复用，不得建立第二责任目录服务。

### 3.4 当前审计与治理模型缺口

实际路径：`D:\Dev-PCE\Source\backend\system\models.py`

现有 `OrganizationOperatingAuditRecord` 包含：

```text
action_code, actor, organization, target_type, target_id,
target_label, reason, before_snapshot, after_snapshot, created_at
```

仓库扫描未发现正式 Organization Change Request（组织变更申请）模型，也未发现审核人、批准人和申请应用状态字段。

结论：当前审计能够证明“谁直接改了什么”，不能完整证明“谁申请、谁审核、谁批准、何时应生效、由哪个批准版本执行”。这是实施阻断，不允许用日志字符串或 Workflow Task 临时代替。

## 4. 目标服务职责与唯一边界

### 4.1 目标服务链

```text
Change Request
↓
Impact Analysis
↓
Review
↓
Approval
↓
Effective-Time Guard
↓
OrganizationOperatingService
↓
Organization Facts + Audit Evidence
↓
Server Readback
```

### 4.2 服务能力分层

| 能力 | 目标所有者 | 能否写正式事实 | 边界 |
|---|---|---:|---|
| 组织事实查询 | EnterpriseOrganizationModelService | 否 | 读取服务端 Canonical Facts（规范事实） |
| 责任目录查询 | ResponsibilityCatalogService | 否 | 根事实固定为 system.Responsibility |
| 变更申请生命周期 | Organization Change Governance Capability（组织变更治理能力，目标） | 否 | 只维护申请及审批证据 |
| 影响分析 | Organization Impact Analysis Capability（组织影响分析能力，目标） | 否 | 只发现影响和阻断项 |
| 正式事实执行 | OrganizationOperatingService | 是 | 只执行已批准且到期的请求 |
| 权限裁决 | AuthorizationService | 否 | 只判断用户是否允许执行动作 |
| 审核/批准过程 | Workflow Runtime 或受控治理流程 | 否 | 不创建或修改组织事实 |
| 责任解析 | RRE | 否 | 只读有效事实并输出解析证据 |
| Runtime Adapter | 唯一组织 Runtime Adapter | 否 | 只读投影，Business Write Count = 0 |

### 4.3 OrganizationOperatingService 目标职责

服务未来必须负责：

- 读取并锁定已批准变更申请；
- 复核申请对象、版本、审批证据、职责分离和有效时间；
- 复核服务端动作契约及 requiredPermission（所需权限编码）；
- 调用 AuthorizationService 检查当前执行身份与组织范围；
- 重新读取正式当前事实，检测申请后是否发生并发漂移；
- 执行领域校验和唯一事务；
- 写入正式事实和完整审计；
- 标记请求已应用并返回真实写入数；
- 从服务端重新读取目标事实并验证一致性。

服务未来不得负责：

- 创建 Business Action（业务动作）、Responsibility、Role 或 Permission；
- 决定谁是业务批准人；
- 用拥有权限的人反推 Data Owner（数据所有者）或责任人；
- 自动修复责任、岗位或员工任职；
- 在多人冲突时随机选择；
- 创建 Workflow Task（流程任务）、ApprovalTask（审批任务）或推进采购状态；
- 让页面提交的状态、批准结论、责任编码成为可信事实。

## 5. 事实读取能力设计

统一查询必须支持：

| 对象 | 当前查询 | 历史/未来查询 | 权威来源 |
|---|---|---|---|
| Company（公司） | 当前有效公司 | 截至时点状态 | system.Company |
| Organization Unit（组织单元） | 当前层级 | 历史和未来层级 | system.OrganizationUnit |
| Position（岗位） | 当前有效岗位 | 历史/未来有效期 | system.Position |
| Responsibility（责任） | 当前有效目录 | 生命周期与有效期 | system.Responsibility |
| PositionResponsibility（岗位责任关系） | 当前有效关系 | 时态关系和类型 | system.PositionResponsibility |
| Employee Assignment（员工任职关系） | 当前主岗/兼岗/代理 | 完整任职历史 | 未来 EmployeePositionAssignment |

统一时点谓词：

```text
effective_from <= asOf
AND (effective_to IS NULL OR asOf < effective_to)
```

查询返回至少包含：

```text
factSource, asOf, resultCount, factLoadStatus,
authorization, businessWriteCount = 0
```

禁止使用上一页缓存、前端重算、旧 `Employee.position_ref` 或责任关系反推来补齐缺失事实。缺失或读取失败必须显式返回 `UNKNOWN/read_failed`。

## 6. Change Request（变更申请）服务能力设计

### 6.1 目标内容

未来变更申请至少表达：

```text
requestId, requestVersion, objectType, objectId,
actionCode, proposedBeforeVersion, proposedAfter,
reason, requestedEffectiveAt, requester,
impactAnalysisVersion, reviewer, approver,
status, createdAt, updatedAt, appliedAt
```

这只是服务契约设计，不代表本轮创建 Schema 或 API。

### 6.2 生命周期

```text
DRAFT
→ SUBMITTED
→ IMPACT_ANALYZED
→ UNDER_REVIEW
→ REVIEWED
→ APPROVED
→ SCHEDULED
→ APPLIED
```

分支终态：

```text
REJECTED / CANCELLED / EXECUTION_FAILED
```

规则：

- Change Request 不是正式组织事实；
- 申请保存不得改变 Company、OrganizationUnit、Position、Responsibility、PositionResponsibility 或 Employee Assignment；
- 申请人、审核人、批准人不得由同一自然人同时承担；
- 修改已审核内容必须生成新版本并使原审核、批准失效；
- 只有 `APPROVED/SCHEDULED` 且达到有效时间的冻结版本可进入执行；
- `APPLIED` 不可重复应用；失败不得留下部分正式事实。

### 6.3 当前 Schema 阻断

OOM-4.1.1 已将 Change Request Schema 明确排除在最小事实 Schema 包之外。因此未来实施前必须二选一并单独签发：

1. 批准最小 Change Request、Review/Approval Evidence（审核/批准证据）和 Application Record（应用记录）持久模型；或
2. 批准一个已经存在且满足同等不可变、版本化、审计和幂等要求的治理对象作为正式来源。

禁止用 ApprovalTask、日志文本、页面缓存或 `OrganizationOperatingAuditRecord.before_snapshot` 冒充变更申请。

## 7. Impact Analysis（影响分析）能力设计

影响分析输入：申请冻结版本、对象类型、对象 ID、目标值、有效时间和组织范围。

至少分析：

| 变更对象 | 必查影响 |
|---|---|
| Company | 组织单元、岗位、任职、跨公司引用 |
| OrganizationUnit/Department | 子层级、岗位、员工、岗位责任、流程范围 |
| Position | 子岗位、任职、岗位责任、部门负责岗位 |
| Responsibility | BAC 引用、岗位责任、流程责任、RRE 可解析性 |
| PositionResponsibility | PRIMARY/SUPPORTING 冲突、责任覆盖和候选变化 |
| Employee Assignment | 当前责任人、主岗冲突、兼岗/代理、历史连续性 |

输出必须区分：

```text
BLOCKER（阻断）
WARNING（警告）
INFORMATION（提示）
UNKNOWN（事实不足）
```

影响分析只发现风险，不得自动批准、自动修复、自动生成责任或自动选择员工。正式执行前必须基于同一申请版本重新计算关键阻断项，防止分析后数据漂移。

## 8. Effective Date（生效时间）执行能力

统一采用 `[effective_from, effective_to)` 左闭右开区间。

目标能力：

- 当前、历史和未来 As Of 查询；
- 未来生效请求排程；
- 调岗、责任交接和岗位调整的无重叠衔接；
- 执行时以服务端时钟和批准时区为准；
- 生效前不改变当前事实；
- 生效时重新复核权限、版本、有效期、冲突和引用；
- 一个事务内关闭旧区间并创建/激活新区间；
- 回读证明交界点只有一个有效事实。

未来生效执行器只能触发 `OrganizationOperatingService.applyApprovedChange()` 等受控领域命令。它不是 Runtime Adapter，也不是 Workflow Runtime；不得绕过 Guard 直接使用 ORM。

## 9. Audit（审计）能力设计

完整证据链必须同时覆盖申请、审批和事实应用：

```text
Request Before/After
Requester / Requested At / Reason
Impact Analysis / Version
Reviewer / Reviewed At / Review Decision
Approver / Approved At / Approval Decision
Effective Time
Executor / Executed At
Fact Before/After
Action Code / Permission Decision / Organization Scope
Request Version / Idempotency Key / Write Count
```

现有 `OrganizationOperatingAuditRecord` 可继续作为正式事实变更审计，不新增“责任专用审计表”。但其当前字段不足以独立承载完整治理证据；未来应通过正式请求/审批证据引用或最小字段扩展建立可追踪链，具体 Schema 必须另行批准。

审计要求：

- 成功和失败执行均要有可检索证据；
- 正式事实 Before/After 不可被后续编辑覆盖；
- 审计与事实写入必须事务一致；
- 回退不得删除原批准与失败证据；
- Digital Twin（数字孪生）和 Control（控制体系）只读审计，不得修改证据。

## 10. AuthorizationService 对接边界

目标输入：

```text
User + requiredPermission/actionCode + Organization Scope
+ Business Object + Context
```

目标输出：

```text
ALLOW / DENY + decisionCode + reason
+ roleCodes + permissionCodes + scope + authoritySource
```

OrganizationOperatingService 必须在以下时点校验：

1. 创建或提交变更申请时，检查是否允许提出该类维护；
2. 审核/批准动作时，检查对应治理动作权限；
3. 生效执行时，检查服务执行身份和范围；
4. 正式读取时，按组织范围裁剪事实。

AuthorizationService 不负责：业务批准、责任解析、选择岗位、选择审核人、创建责任或判断变更合理性。拥有 Permission 只表示“可执行该系统动作”，不表示“业务上应该批准”。

## 11. Workflow Runtime 对接边界

未来 Workflow Runtime 可以：

- 承载提交、审核、退回、批准和拒绝节点；
- 保存过程任务及节点决策；
- 向治理服务返回经验证的流程实例和批准证据引用；
- 在批准后请求组织服务进行受控应用。

Workflow Runtime 不可以：

- 创建 Company、OrganizationUnit、Position 或 Responsibility；
- 直接更新 PositionResponsibility 或 Employee Assignment；
- 决定业务责任人或用 `required_role_code` 承载 Responsibility Code；
- 以流程完成替代组织事实生效；
- 在页面加载、节点创建或任务完成时自动写正式组织事实。

当前 `ApprovalTask.required_role_code` 继续保持 Role（角色）语义。本报告不修改 Workflow Runtime 或 ApprovalTask。

## 12. RRE 读取边界

未来 RRE 只读以下有效事实：

```text
Business Action Contract
↓ requiredResponsibility
Responsibility
↓
PositionResponsibility
↓
Position
↓
Employee Assignment
↓
Employee
```

组织服务应向 RRE 提供同一 `asOf` 和组织范围下的权威读取能力与 Evidence（解析证据）来源标识。

RRE 不得：

- 调用组织写命令；
- 创建或修复岗位、责任、任职；
- 用主管、管理员、权限或旧审批人兜底；
- 在发现多人、无人或无权限时修改主数据。

只有 OOM Schema、组织服务、BAC 契约和数据治理分别实施并验收后，才可讨论 RRE-1；当前仍未授权。

## 13. 并发、幂等与一致性设计

正式事实执行必须满足：

- 使用 `requestId + requestVersion` 形成唯一应用键；
- `APPLIED` 请求重复提交返回原结果，不产生第二次写入；
- 锁定请求记录和目标事实；
- 比较申请所基于的事实版本或摘要；
- 事实已变化时返回 `STALE_CHANGE_REQUEST`，禁止静默覆盖；
- 跨多个事实的变更必须单事务提交；
- 审计写入失败则正式事实一并回滚；
- 返回真实 `writeCount`、目标版本和 readback hash；
- 批量变更必须先完整校验，再整体写入，禁止部分成功。

## 14. 错误契约设计

建议统一错误码：

| 错误码 | 含义 | 是否写正式事实 |
|---|---|---:|
| `CHANGE_REQUEST_REQUIRED` | 未提供正式变更申请 | 否 |
| `CHANGE_REQUEST_NOT_APPROVED` | 申请未批准 | 否 |
| `SEGREGATION_OF_DUTIES_VIOLATION` | 申请/审核/批准职责冲突 | 否 |
| `CHANGE_REQUEST_VERSION_MISMATCH` | 申请版本不一致 | 否 |
| `STALE_CHANGE_REQUEST` | 正式事实已漂移 | 否 |
| `EFFECTIVE_TIME_NOT_REACHED` | 未到生效时间 | 否 |
| `IMPACT_BLOCKER_PRESENT` | 存在影响阻断项 | 否 |
| `TEMPORAL_OVERLAP` | 有效期重叠 | 否 |
| `CROSS_COMPANY_REFERENCE_FORBIDDEN` | 跨公司引用 | 否 |
| `PERMISSION_DENIED/SCOPE_DENIED` | 授权或范围拒绝 | 否 |
| `ALREADY_APPLIED` | 请求已应用，返回幂等结果 | 否 |
| `READBACK_MISMATCH` | 保存后回读不一致 | 事务回滚或标记失败 |

错误必须包含 `requestId`、`actionCode`、`decisionCode`、原因和安全的 Evidence；不得泄漏超出用户组织范围的数据。

## 15. 实施包拆分设计

以下为未来实施包，不构成本轮授权：

### Package S0：Prerequisite Gate（前置门禁）

- OOM-4.1.1 Schema 方案获得独立实施授权；
- Change Request/审批证据 Schema 完成决策并授权；
- BAC-1 服务端契约实施状态明确；
- 权限动作和治理角色映射完成审批；
- 数据备份、摘要、回退和零业务写基线冻结。

### Package S1：Read Capability（读取能力）

- 为组织、岗位、责任、岗位责任和任职提供统一 As Of 查询；
- 扩展服务端投影而不建立第二事实源；
- 增加事实来源、加载状态、数量和零写诊断。

### Package S2：Change Governance Capability（变更治理能力）

- 实施变更申请生命周期、版本、职责分离和审批证据；
- 申请保存只写治理对象，不写正式组织事实；
- 所有状态迁移通过领域 Guard。

### Package S3：Impact Analysis Capability（影响分析能力）

- 建立对象级影响分析器；
- 只读 BAC、Workflow 引用和组织事实；
- 输出 BLOCKER/WARNING/INFORMATION/UNKNOWN。

### Package S4：Approved Change Executor（已批准变更执行器）

- 收敛所有正式事实写入到 OrganizationOperatingService；
- 实施版本复核、锁、幂等、时态、事务和服务端回读；
- 禁止旧页面/API 绕过 Change Request 直接保存。

### Package S5：Audit & Observability（审计与可观测性）

- 串联 Request、Review、Approval、Application 和 Fact Audit；
- 提供严格事实、写入数、失败原因和链路证据；
- Digital Twin/Control 只读消费。

### Package S6：Verification（验证）

- 单元、服务、授权、并发、时态、审计、回读和保护测试；
- 真实浏览器验收留给 OOM-4.1.3/4.1.4 后续独立阶段；
- 不启动 RRE 或 Workflow Integration。

## 16. 自动测试与验收设计

| 编号 | 场景 | 预期 |
|---|---|---|
| OOM412-T01 | 未携带变更申请写事实 | 拒绝，零正式写入 |
| OOM412-T02 | 未批准申请执行 | `CHANGE_REQUEST_NOT_APPROVED` |
| OOM412-T03 | 同一人提交、审核、批准 | 阻断 |
| OOM412-T04 | 无权限提交/审核/批准/执行 | HTTP 403 |
| OOM412-T05 | 影响分析存在 BLOCKER | 拒绝执行 |
| OOM412-T06 | 未来生效请求提前执行 | 拒绝 |
| OOM412-T07 | 到期请求执行 | 单事务成功 |
| OOM412-T08 | 重复执行同一版本 | 幂等，无第二次写入 |
| OOM412-T09 | 申请后事实发生变化 | `STALE_CHANGE_REQUEST` |
| OOM412-T10 | `[from,to)` 交界查询 | 唯一有效事实 |
| OOM412-T11 | 跨公司岗位/员工/责任关系 | 拒绝 |
| OOM412-T12 | Employee Assignment 主岗重叠 | 拒绝 |
| OOM412-T13 | PositionResponsibility 有效期重叠 | 拒绝 |
| OOM412-T14 | 审计证据 | 申请/审核/批准/执行/Before/After 完整 |
| OOM412-T15 | 保存后服务端回读 | 与正式事实一致 |
| OOM412-T16 | RRE、Workflow、ApprovalTask、采购写入 | 全部为 0 |

实施验收必须证明：

- 一个且只有一个正式事实写入口；
- 页面、Runtime、Workflow 和 RRE 无直接 ORM 写路径；
- 当前、历史、未来查询使用同一服务端时态事实；
- AuthorizationService ALLOW/DENY 与接口结果一致；
- 审核、批准和执行身份可追溯且职责分离；
- 失败不留下部分事实；
- 审计和回读完整。

## 17. 风险与阻断项

| 编号 | 风险/缺口 | 影响 | 处理 | 优先级 |
|---|---|---|---|---|
| SVC-R01 | 当前直接保存正式事实 | 绕过治理闭环 | 实施时强制 Approved Change Guard | P0 |
| SVC-R02 | Change Request Schema 未批准 | 无法形成不可变申请证据 | 单独 Schema 决策与授权 | P0 |
| SVC-R03 | 审计缺 Reviewer/Approver 链 | 无法证明批准来源 | 建立正式引用链 | P0 |
| SVC-R04 | BAC 服务端完整契约未实施 | 动作仍为局部映射 | 保持兼容，等待 BAC 独立授权 | P0 |
| SVC-R05 | EmployeePositionAssignment 未实施 | 无法提供时态任职 | 等待 OOM-4.1.1 Schema 授权 | P0 |
| SVC-R06 | PositionResponsibility 非时态 | 历史解析不足 | 原表最小扩展，不建 V2 | P0 |
| SVC-R07 | 未来生效执行与 Workflow 混淆 | 流程可能越权写事实 | 独立受控领域执行器 | P0 |
| SVC-R08 | 多入口继续直接写 | 出现第二事实写入口 | 静态扫描、服务门禁、删除绕过路径 | P0 |
| SVC-R09 | 影响分析被误作批准 | 系统自动决定企业事实 | 分离分析结果与批准决定 | P1 |
| SVC-R10 | 旧字段和新任职事实双写漂移 | 页面/RRE 读取不一致 | OOM-4.1.1 兼容阶段与权威切换门禁 | P0 |

## 18. 实施前准入清单

- [ ] OOM-4.1.1 Schema 实施获得新授权；
- [ ] Change Request 与审批证据的持久模型完成架构批准；
- [ ] OrganizationOperatingService 唯一写入口规则签发；
- [ ] 现有直接保存入口完成清单和封锁方案；
- [ ] Data Owner、Data Steward、Reviewer、Approver 映射确认；
- [ ] 职责分离规则确认；
- [ ] 治理动作权限与 BAC 兼容方案确认；
- [ ] Impact Analysis 规则和 UNKNOWN 阻断策略确认；
- [ ] As Of、时区、未来生效和交接规则确认；
- [ ] 幂等、并发、版本和事务策略确认；
- [ ] 审计引用链与保留期确认；
- [ ] 回退、备份和数量/摘要基线确认；
- [ ] 零 RRE、Workflow、ApprovalTask 和采购副作用测试批准。

任一 P0 条件未满足时：

```text
Organization Service Implementation Gate = FAIL
```

## 19. 本轮保护确认

本轮仅进行只读仓库审查并新增本设计报告。未运行 ORM 写入、Migration、业务 API、Workflow、RRE 或数据初始化。仓库原有其他改动不属于本任务，本轮未修改、清理或归因。

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
AuthorizationService Changed = NO
Workflow Runtime Changed = NO
ApprovalTask Changed = NO
RRE Started = NO
Unauthorized Business Writes = 0
```

## 20. 最终状态

```text
OOM-4.1.2 Organization Service Capability Implementation Package Design = COMPLETE
OOM-4.1.3 = NOT STARTED
OOM-4.1.4 = NOT STARTED
Organization Model Implementation = NOT AUTHORIZED
Schema Migration = NOT AUTHORIZED
RRE-1 = NOT AUTHORIZED
Workflow Integration = NOT AUTHORIZED
```

本报告完整结束。停止等待下一步架构决策，不进入 OOM-4.1.3、OOM-4.1.4 或任何代码实施。
