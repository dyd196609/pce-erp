# PCE Organization Operating Model V2 OOM-3.2 组织主数据变更流程与治理闭环设计报告

日期：2026-08-18  
阶段：OOM-3.2 Governance Process Design（OOM-3.2 治理流程设计）  
任务类型：DESIGN ONLY（仅设计）  
实施授权：NOT AUTHORIZED（未授权实施）

## 1. 执行摘要

本报告设计 Organization Master Data Change Governance Loop（组织主数据变更治理闭环）。核心原则是：正式组织事实不得因页面编辑或操作者拥有维护权限而直接改变；任何正式变更都必须先形成 Change Request（变更申请），完成 Impact Analysis（影响分析）、Review（审核）、Approval（批准），再按 Effective Date（生效时间）受控执行，并形成 Audit（审计）、服务端回读和影响复核证据。

目标闭环：

```text
Change Request（变更申请）
  ↓
Impact Analysis（影响分析）
  ↓
Review（审核）
  ↓
Approval（批准）
  ↓
Effective Date（生效时间）
  ↓
Authorized Execution（受权执行）
  ↓
Audit + Readback + Impact Verification（审计、回读、影响复核）
```

设计结论：

1. 保留现有 OrganizationOperatingService（组织运作服务）作为未来“执行已批准变更”的唯一组织写服务，不新建平行事实写入链。
2. 当前 `#/organization` 是正式维护入口，但现状仍属于“有权限即可提交并直接保存”；OOM-4 实施后应演进为“提交申请/执行已批准申请”，不得由页面直接决定事实生效。
3. AuthorizationService（统一授权服务）继续裁决“操作者能否执行”，不负责业务审核、批准或责任发现。
4. Workflow Runtime（流程运行引擎）不拥有公司、组织、岗位、责任、岗位责任或员工任职事实；本报告也不授权修改 Workflow Runtime。
5. Responsibility（职责/责任定义）变更采用最高治理等级；页面、Business Action Contract（业务动作契约，BAC）、RRE、Workflow 与 AI（人工智能）均不得自动创建责任。
6. Employee Assignment（员工任职关系）变化只改变任职事实，不修改 Business Action、Responsibility、Permission（权限）或 Workflow。

## 2. 已读取正式基线、关键原文与判断

本报告完整读取了以下文件。关键原文用于说明判断依据；引用未改变原文件含义。

### 2.1 BAC 基线

#### 2.1.1 BAC-0 架构签发报告

实际路径：`D:\Dev-PCE\Source\docs\governance\PCE Business Action Contract V1 BAC-0架构签发报告.md`  
文件用途：冻结服务端业务动作契约权威、责任与权限边界，以及工作流兼容原则。

关键原文：

> “本次批准代表架构规则批准，不代表代码实施批准。”

> “当前仓库尚未实施完整 Server Business Action Contract（服务端业务动作契约），尤其尚未建立 `requiredResponsibility` 字段。”

> “AuthorizationService 统一授权裁决，只负责‘是否允许执行’。”

判断：BAC 是未来 Business Action（业务动作）的唯一事实来源；架构批准不能解释为 BAC-1、RRE-1 或组织流程实施授权。

#### 2.1.2 BAC-1 架构与契约定义设计

实际路径：`D:\Dev-PCE\Source\docs\governance\PCE Business Action Contract V1 BAC-1架构与契约定义设计报告.md`  
文件用途：定义服务端契约模型和前端、Workflow、AuthorizationService 的消费边界。

关键原文：

> “把当前分布在 Frontend Registry（前端注册表）与 ActionPermissionPolicy（动作权限策略）中的动作事实，收敛为一个服务端权威契约。”

> “`requiredResponsibility` 尚不存在。”

> “未来也只能引用 Server Contract 中已有 `actionCode`，不能独立创建动作语义。”

判断：`requiredResponsibility` 只能引用既有 Responsibility；`requiredPermission` 独立输入 AuthorizationService。Permission 不得寻找责任人，Business Action 不得生成 Responsibility。

### 2.2 OOM 基线

#### 2.2.1 OOM V2 与 BAC 对接设计

实际路径：`D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 与 Business Action Contract 对接设计报告.md`  
文件用途：确定组织事实与 BAC、RRE 的目标连接关系。

关键原文：

> “当前 `system.Responsibility` 已经是独立责任目录事实源；BAC 只能引用其编码，不能生成责任。”

> “当前 `system.PositionResponsibility` 可以表达‘岗位承担责任’。”

> “EmployeeReportingRelation（员工汇报关系）只表达直属/职能汇报，不得作为 RRE 找不到责任人时的主管兜底。”

判断：责任目录、岗位责任与员工任职是独立企业事实；主管关系、Role 或 Permission 不能补齐责任解析缺口。

#### 2.2.2 OOM-1 实施方案设计

实际路径：`D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-1实施方案设计报告.md`  
文件用途：确认模型复用、实施阶段与员工变更边界。

关键原文：

> “复用现有 `Company`、`OrganizationUnit`、`Department`、`JobFamily`、`JobLevel`、`Position`、`Responsibility`、`PositionResponsibility`、`Employee`、`User`、`Role` 和 `Permission`，不建设 V2 平行表族。”

> “员工变动只改变任职关系，不修改 Business Action、Workflow、Responsibility 或 Permission。”

判断：变更闭环必须包围现有主数据服务和未来受控时态扩展，不得建立第二套组织事实模型。

#### 2.2.3 OOM-2 实施设计与 Schema 决策

实际路径：`D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-2实施设计与Schema决策报告.md`  
文件用途：定义 EmployeePositionAssignment（员工岗位任职关系）和 PositionResponsibility 有效期等目标时态能力。

关键判断：

- 员工任职必须支持主岗、兼岗、代理、调岗、离岗和历史时点；
- 岗位责任必须支持有效期，避免覆盖历史关系；
- Schema 决策不等于 Migration 或实施授权。

判断：OOM-3.2 可以设计变更申请与时点生效语义，但不得创建表、Migration 或数据。

#### 2.2.4 OOM-3 数据治理与初始化设计

实际路径：`D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-3数据治理与初始化方案设计报告.md`  
文件用途：确认 Data Owner（数据所有者）、Data Steward（数据管理员）、Data Custodian（数据保管人）、Approver（批准人）、Consumer（消费者）以及四眼控制。

关键判断：数据应经过管护校验、所有者审核、独立批准、授权校验、受控保存、审计和回读；初始化不能绕过治理。

#### 2.2.5 OOM-3.1 主数据责任与治理矩阵

实际路径：`D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-3.1主数据责任与治理矩阵设计报告.md`  
文件用途：确定各主数据的 Data Owner、Data Steward、Reviewer（审核人）、Approver（批准人）与职责分离规则。

关键原文：

> “提出/录入、审核、批准/生效不得由同一治理角色包办；同一自然人不得审批自己发起或维护的变更。”

> “技术管理员、超级管理员或数据库管理员的技术权限不构成 Data Owner 身份。”

判断：OOM-3.2 必须把角色矩阵落实为每次变更的状态机、证据链和禁止转换规则。

### 2.3 权限与运行时边界

实际路径：`D:\Dev-PCE\Source\docs\governance\PCE公共组织身份权限核心V1-最终人工验收与封板报告.md`  
文件用途：确认 Position、Role、Permission 分离以及服务端授权裁决。

关键原文：

> “岗位与系统角色是不同字段、不同对象，没有 Position=Role 绑定。”

> “最终决定来自 `AuthorizationService`。”

实际路径：`D:\Dev-PCE\Source\backend\system\authorization.py`  
文件用途：核对统一授权服务的当前真实职责。

关键原文：

```python
permission_codes = sorted(cls._permission_codes(role_codes))
```

```python
class BusinessPermissionAuthorization:
    """Compatibility facade; all decisions now delegate to AuthorizationService."""
```

判断：Role → Permission 是执行能力链；AuthorizationService 不是业务审核渠道，也不拥有组织事实批准权。

实际路径：`D:\Dev-PCE\Source\docs\governance\Runtime职责规范.md`  
文件用途：确认唯一 Runtime 与服务端事实消费原则。

关键原文：

> “每个业务对象保持唯一正式 Runtime；页面筛选、列投影和下拉选项只能消费既有 Runtime/Provider，不得把页面缓存或静态 Fixture 建成第二事实源。”

实际路径：`D:\Dev-PCE\Source\backend\workflow_runtime\action_permissions.py`  
文件用途：核对当前动作权限策略和校验能力。

关键原文：

```python
class ActionPermissionPolicy:
    actionCode: str
    moduleCode: str
    requiredPermission: str
```

判断：当前 Workflow Runtime 有动作权限校验基础，但不拥有组织主数据变更审批和事实创建职责。

## 3. 当前治理能力分析

### 3.1 当前服务端能力

实际路径：`D:\Dev-PCE\Source\backend\system\organization_operating.py`  
用途：正式组织维护动作的授权、保存与审计服务。

关键原文：

```python
class OrganizationOperatingService:
    """Explicit Action -> Guard -> Persistence -> Audit service for organization maintenance."""
```

```python
reason = str(payload.get("reason") or "").strip()
if len(reason) < 2:
    raise OrganizationOperatingError("REASON_REQUIRED", "请填写本次修改原因。")
```

```python
decision = AuthorizationService.decide(...)
if not decision["allowed"]:
    raise OrganizationOperatingError(..., http_status=403)
```

```python
with transaction.atomic():
    result = handler(user=user, payload=payload, reason=reason)
```

当前已具备：动作注册、原因必填、AuthorizationService 校验、Scope 校验、事务保存、Before/After 审计。

当前限制：请求被授权后直接进入持久化 handler；服务中尚未出现独立 Change Request、Impact Analysis、Reviewer、Approver、批准版本、批准失效或计划生效门禁。

### 3.2 当前 API 边界

实际路径：`D:\Dev-PCE\Source\backend\system\access_control_views.py`  
用途：组织与权限基础页面的服务端读写入口。

关键原文：

```python
if action in ACTION_PERMISSIONS:
    result = OrganizationOperatingService.execute(
        user=request.user, action=action, payload=payload,
    )
```

判断：现有入口复用统一服务是正确基础，但当前 POST 没有要求 `changeRequestId`、批准证据或生效窗口。未来不得通过另建旁路 API 解决，应在独立授权后让现有执行链只接受获批变更。

### 3.3 当前页面能力

实际路径：`D:\Dev-PCE\Source\frontend\src\meta\pages\AccessControlFoundationPage.vue`  
用途：`#/organization` 正式组织、人员、岗位、责任、账户、角色与权限管理入口。

关键原文：

> “成功保存必须填写原因并生成 OrganizationOperatingAuditRecord；综合页只负责查看、树展示与诊断。”

```javascript
async function saveEditor() {
  const response = await accessControlApi.action(...)
  ...
  await refresh()
}
```

判断：页面已有原因、服务端事实、审计展示和刷新回读，这是可复用基础；但页面仍是即时保存交互，未展示申请、影响、审核、批准、生效状态。现阶段页面不能被认定为完整治理审批渠道。

### 3.4 当前审计能力

实际路径：`D:\Dev-PCE\Source\backend\system\models.py`  
用途：OrganizationOperatingAuditRecord（组织运作审计记录）模型。

关键原文：

```python
action_code = models.CharField("业务动作编码", max_length=120)
actor = models.ForeignKey(...)
reason = models.CharField("修改原因", max_length=300)
before_snapshot = models.JSONField("修改前", default=dict)
after_snapshot = models.JSONField("修改后", default=dict)
created_at = models.DateTimeField("修改时间", auto_now_add=True)
```

判断：已有写入审计能证明操作者、原因、Before/After 和时间，但不能单独证明申请人、审核人、批准人、批准版本、计划生效时间。是否扩展现有审计或新增变更申请载体，必须在 OOM-4 形成最小 Schema 决策后另行授权。

## 4. 目标变更闭环模型

### 4.1 核心原则

- 所有正式事实先申请、后批准、再生效。
- 页面编辑的是 Proposed Change（拟议变更），不是正式事实。
- 审核针对业务正确性和影响完整性；批准针对风险接受与生效授权，两者不是同一步。
- AuthorizationService 校验系统执行权，但不能替代 Reviewer 或 Approver。
- 生效执行必须使用批准时冻结的 Payload Hash（变更内容摘要）；内容改变则原批准失效。
- 生效后必须读取同一服务端事实并核对审计；页面本地状态不构成证据。

### 4.2 概念状态机

```text
DRAFT（草稿）
  ↓ submit
IMPACT_ANALYSIS（影响分析中）
  ↓ impact complete
IN_REVIEW（审核中）
  ↓ review pass
PENDING_APPROVAL（待批准）
  ↓ approve
APPROVED（已批准，等待生效）
  ↓ effective date reached + authorization allow
EFFECTING（生效执行中）
  ↓ transaction + audit + readback pass
EFFECTIVE（已生效）
```

异常终态/分支：

```text
REJECTED（已拒绝）
CANCELLED（已取消）
EXPIRED（批准过期）
EFFECT_FAILED（生效失败）
ROLLED_BACK（已受控回退）
SUPERSEDED（被新申请替代）
```

这些是 Change Request 治理概念状态，不要求本轮创建枚举、表或 Workflow。

### 4.3 状态转换控制

| 当前状态 | 动作 | 执行角色 | 必要条件 | 目标状态 |
|---|---|---|---|---|
| DRAFT | 提交 | Requester/Data Steward | 原因、Before/After、对象、日期完整 | IMPACT_ANALYSIS |
| IMPACT_ANALYSIS | 完成分析 | Data Steward + 领域分析人 | 依赖清单、RRE/流程/BAC影响齐全 | IN_REVIEW |
| IN_REVIEW | 审核通过 | 独立 Reviewer | 非申请人、非维护人；无阻断风险 | PENDING_APPROVAL |
| IN_REVIEW | 审核拒绝 | Reviewer | 记录意见 | REJECTED |
| PENDING_APPROVAL | 批准 | 独立 Approver | 非申请/维护/审核人；内容摘要未变 | APPROVED |
| APPROVED | 生效 | Authorized Operator/系统调度 | 到达生效时间、授权 ALLOW、前置条件未漂移 | EFFECTING |
| EFFECTING | 保存与回读成功 | OrganizationOperatingService | 同一事务审计、回读一致 | EFFECTIVE |
| EFFECTING | 保存/回读失败 | 服务 | 原子回滚、错误证据 | EFFECT_FAILED |
| EFFECTIVE | 回退申请 | 新的独立治理链 | 禁止直接撤销历史 | 新 Change Request |

### 4.4 变更申请最小逻辑字段

以下为设计字段，不代表 Schema 授权：

| 字段 | 说明 |
|---|---|
| changeRequestCode | 全局唯一变更申请编号 |
| objectType/objectId | 目标对象类型与标识；新对象可暂为空 |
| changeType | CREATE、UPDATE、SUSPEND、RETIRE、MERGE、ASSIGN、END_ASSIGNMENT 等 |
| beforeSnapshot/afterSnapshot | 冻结的变更前后事实 |
| payloadHash | 批准内容摘要，防止批准后偷换内容 |
| reason | 业务原因 |
| requestedBy/requestedAt | 申请人和申请时间 |
| steward/reviewer/approver | 管护、审核和批准身份 |
| reviewedAt/approvedAt | 审核与批准时间 |
| effectiveAt | 计划生效时点 |
| organizationScope | 公司/组织范围 |
| impactAnalysis | 结构化影响分析与依赖清单 |
| approvalConditions | 批准附加条件与有效期 |
| executionActor/executedAt | 生效执行人和时间 |
| auditRecordIds | 对应组织审计记录 |
| readbackEvidence | 服务端回读摘要 |
| status | 治理状态 |

## 5. 治理角色剧本与职责分离

### 5.1 角色

| 角色 | 剧本职责 | 禁止事项 |
|---|---|---|
| Requester（申请人） | 提出业务需求、原因和目标日期 | 审核或批准自己的申请 |
| Data Steward（数据管理员） | 录入、规范化、校验、影响分析、准备回退方案 | 批准自己维护的内容 |
| Data Owner（数据所有者） | 对对象语义、质量和业务结果负责 | 以所有权绕过独立审核 |
| Reviewer（审核人） | 核验业务正确性、引用、时态和影响 | 同时作为申请人/维护人/最终批准人 |
| Approver（批准人） | 接受风险、批准生效日期与条件 | 批准本人参与提出、维护或审核的申请 |
| Authorized Operator（受权执行人） | 在批准范围内调用正式服务生效 | 更改获批 Payload 或决定业务内容 |
| Data Custodian（数据保管人） | 提供平台、备份、审计和访问控制 | 决定组织业务事实 |

### 5.2 自然人级隔离

同一自然人不得同时承担“提出 + 审核 + 批准”。最低控制为 Requester ≠ Reviewer ≠ Approver；Data Steward 若参与内容维护，也不得成为该申请 Approver。超级管理员身份不豁免此规则。

对于小型组织无法配置三名业务人员的情况，不得静默降级；应由上级治理主体或跨域批准人补位，并记录例外依据。

## 6. Company（公司）变更流程

### 6.1 新增公司

申请材料：法定主体信息、公司编码、名称、启用日期、组织范围、数据 Owner。  
影响分析：组织树根、Position、Employee Assignment、权限 Scope、BAC `scopeDimensions`、RRE 公司上下文、财务/经营报表。  
审核：法务/财务主体审核 + 企业架构审核。  
批准：授权高管或企业治理委员会。  
生效：只建立获批公司事实；不得自动创建部门、岗位、责任、角色或员工。

### 6.2 修改公司信息

- 展示名称等非标识属性可以按生效日变更并保留历史名称。
- 公司编码、法定身份或公司边界属于极高风险；被引用后原则上不可原地改写。
- 实质主体变化应采用新主体/替代关系方案，不得伪装成普通字段编辑。

### 6.3 公司失效

前置条件：不存在未处置的有效子组织、岗位、任职、岗位责任范围或活跃引用。  
禁止：物理删除、级联删除、把人员和岗位自动迁移到默认公司。

### 6.4 公司合并

公司合并不是单一 UPDATE，而是 Program of Changes（变更组合）：目标公司确认、组织迁移、岗位迁移、任职迁移、范围与权限复核、历史主体保留。每个子变更分别审计；任一步失败不得留下半迁移状态。

## 7. Organization Unit（组织单元）变更流程

适用 Department（部门）、Center（中心）、Business Unit（事业部）等组织类型。

### 7.1 新建部门/组织单元

必须声明：公司、父级、类型、编码、名称、负责人、生效日期。  
校验：同公司、编码唯一、父级有效、无循环、组织类型合法。  
禁止：自动创建岗位、员工任职、责任或权限范围。

### 7.2 部门调整

包括改名、负责人变化、父级调整、类型调整。父级或公司范围变化必须分析：

- 下属组织单元；
- Position 归属；
- Employee Assignment；
- PositionResponsibility 作用范围；
- Authorization Scope；
- BAC 范围维度；
- Workflow 现有范围引用；
- RRE 候选集合。

仅改部门不得自动改岗位责任、员工权限或流程节点。

### 7.3 部门合并

必须明确存续部门、终止部门、组织/岗位/员工迁移清单、有效时点和历史查询规则。合并申请批准后仍应按依赖顺序受控执行，禁止覆盖原部门历史。

### 7.4 部门终止

终止前必须清空或结束未来有效的子部门、岗位及任职，处置岗位责任范围，并完成权限 Scope 和流程范围复核。终止不等于删除。

## 8. Position（岗位）变更流程

### 8.1 创建岗位

Data Owner 为用岗部门负责人；Data Steward 为岗位管理员。申请必须说明组织归属、岗位族、岗位等级、岗位目的和生效日期。

创建岗位只产生 Position 事实：

- 不自动创建 Responsibility；
- 不自动建立 PositionResponsibility；
- 不自动授予 Role 或 Permission；
- 不自动成为审批人；
- 不自动修改 Workflow。

### 8.2 修改或岗位调动

岗位名称、岗位族或等级变化需审查分类影响；岗位组织归属调整需审查所有有效任职和岗位责任范围。岗位跨公司调动原则上采用结束旧岗位/建立新岗位及受控迁移，不原地改写历史公司边界。

### 8.3 岗位暂停/冻结

暂停期间禁止新增任职和新增责任关系；已有关系如何结束必须由独立申请决定。暂停不能自动撤销员工权限或改变 Workflow。

### 8.4 岗位退役

顺序：停止新任职 → 结束/迁移 Employee Assignment → 终止未来 PositionResponsibility → 检查 RRE 缺口 → 退役 Position。保留历史证据，不物理删除。

## 9. Responsibility（职责/责任定义）变更流程

### 9.1 新增责任

申请由业务领域提出，责任目录管理员校验编码和重复项，业务专家与企业架构共同审核，独立责任治理批准人批准。

必须确认：

- 编码采用业务对象 + 责任目的；
- 不包含岗位名、员工名、角色名；
- 不等同 Permission；
- BAC 只能在责任有效后引用；
- 不自动生成 PositionResponsibility。

页面、AI、RRE、Workflow、BAC、岗位编辑页均不得自动创建正式责任。

### 9.2 修改责任定义

描述性澄清可以版本化修改；若“谁应该负责什么”的核心语义发生改变，应新建责任并退役旧责任，不能原地改变既有编码含义。

影响分析必须列出：

```text
Responsibility
  → BAC.requiredResponsibility
  → PositionResponsibility
  → PositionWorkflowResponsibility（如存在）
  → RRE 解析语义
  → Workflow/任务的解释证据
```

### 9.3 暂停责任

暂停前必须检查 ACTIVE BAC 引用和未来有效岗位关系。暂停后新解析不得把该责任视为有效，但不得改写历史解析证据。当前阶段不运行 RRE，因此这里只定义未来门禁。

### 9.4 责任退役/失效

退役是永久生命周期决定。必须先迁移或终止 BAC 引用、岗位责任和流程责任配置。禁止删除历史 Responsibility 或复用其编码。

## 10. PositionResponsibility（岗位责任关系）变更流程

### 10.1 增加岗位责任

前置：Position 和 Responsibility 均有效且组织范围相容。岗位 Owner 与责任 Owner 双方审核，独立组织治理批准人生效。

### 10.2 取消岗位责任

采用有效期终止，不删除历史。影响分析必须判断是否造成责任空档、是否仍有其他有效岗位，以及未来 RRE 是否变为 `RESPONSIBILITY_UNRESOLVED`。

### 10.3 PRIMARY（主责）/SUPPORTING（协助）调整

调整承担类型是正式关系变更，需要 Before/After 与生效日。PRIMARY 不等于自动胜出规则；多个有效候选仍需由 RRE 返回冲突，不得按类型、ID、权限或姓名静默选人，除非未来解析规范另有明确批准。

### 10.4 有效日期调整

- 禁止覆盖已发生历史区间；
- 未来区间可通过新申请修正；
- 必须检测同一岗位/责任重复、重叠、空档和跨公司关系；
- 回溯生效原则上禁止；法定纠错需特殊批准并标明更正时间与业务有效时间。

## 11. Employee Assignment（员工任职关系）变更流程

### 11.1 入职/入岗

人事 Data Steward 建立员工任职申请，用岗负责人审核岗位、日期和任职类型，人力资源批准。账户创建与 Role/Permission 分配是独立权限治理，不与任职自动捆绑。

### 11.2 调岗

调岗是一组原子语义：结束旧任职 + 建立新任职。应保留连续时点，避免无意空档或重叠，并重新验证受影响岗位责任的当前候选。

### 11.3 晋升/降级

若仅改变 Employee 的职业等级信息，不得自动修改岗位责任或权限；若实际岗位改变，必须按调岗流程处理。Job Level 不决定 Responsibility 或 Permission。

### 11.4 离岗/离职

结束所有需要终止的主岗、兼岗和代理关系，输出将失去有效承担人的责任清单。禁止自动找主管、管理员或有权限的人替代。

### 11.5 兼岗

必须声明第二岗位、任职类型、范围、开始/结束日期和批准依据。兼岗可能扩大责任候选，但不能自动授予相应 Permission。

### 11.6 代理

代理必须有明确被代理岗位、起止时间、原因和批准人。到期后不再是当前任职事实；是否由未来调度自动结束属于 OOM-4 实施设计，不在本轮实现。

员工变化只改变 Employee Assignment，不修改：

```text
Business Action Contract
Responsibility
PositionResponsibility（除非另有独立申请）
Permission / Role
Workflow Definition
```

## 12. 统一影响分析机制

### 12.1 必查维度

每个变更提交审核前必须形成结构化影响报告：

| 维度 | 分析问题 |
|---|---|
| Organization | 公司、父子层级、部门、范围是否变化？ |
| Position | 哪些岗位被创建、迁移、暂停或失去组织归属？ |
| Responsibility | 哪些责任定义或有效性受影响？ |
| PositionResponsibility | 是否出现空档、重叠、跨公司或多候选？ |
| Employee Assignment | 哪些员工当前/未来任职改变？ |
| BAC | 哪些 `requiredResponsibility` 或 `scopeDimensions` 引用需要复核？ |
| Permission | 权限事实是否保持独立？Scope 是否需另走权限变更？ |
| Workflow | 是否存在范围或责任配置引用？不得由组织变更自动改流程 |
| RRE | 唯一候选是否变为无候选/多候选？是否需要重新验证？ |
| History/Audit | 是否保留旧事实、时点和证据？ |

### 12.2 影响等级

| 等级 | 示例 | 审核要求 |
|---|---|---|
| LOW（低） | 不改变标识和引用的说明修正 | Data Steward + 独立 Reviewer |
| MEDIUM（中） | 岗位族/等级分类调整、未来日期修正 | Data Owner + Reviewer + Approver |
| HIGH（高） | 组织层级、岗位归属、岗位责任、任职变化 | 双领域审核 + 独立 Approver + 回退方案 |
| CRITICAL（极高） | 公司合并、责任核心语义、跨公司迁移 | 架构/业务联合评审 + 治理委员会批准 |

### 12.3 重新验证规则

- Position 或 PositionResponsibility 变化：必须重新验证相关责任的候选集合。
- Employee Assignment 变化：必须重新验证该员工原岗位与新岗位覆盖的责任集合。
- Responsibility 变化：必须重新验证全部 BAC 引用、岗位关系和流程责任配置。
- Organization Unit 变化：必须重新验证组织范围、权限 Scope 及 RRE 过滤上下文。
- Job Level 单独变化：不触发责任或权限变化；仅验证分类和分析引用。

本阶段 `RRE Started = NO`，所谓重新验证是 OOM-4/RRE-1 的未来验收要求，不是本轮执行动作。

## 13. 生效控制、失败与回退

### 13.1 生效前再校验

批准到生效之间可能发生事实漂移。执行前必须重新确认：

- 批准的 Payload Hash 未变化；
- Before Snapshot 与当前正式事实一致；
- 引用对象仍有效；
- Reviewer/Approver 身份仍合规；
- AuthorizationService 返回 ALLOW；
- 生效日期和组织范围仍合法；
- 没有更新的 Change Request 替代本申请。

任一失败均不得部分写入，应转为 EFFECT_FAILED 或重新申请。

### 13.2 事务与依赖顺序

单对象变更采用原子事务。公司合并、组织迁移等组合变更应通过可恢复的分阶段计划执行，每阶段都要有检查点；不得把失败状态伪装为成功。

### 13.3 回退原则

- 未生效：取消申请，不触碰正式事实。
- 生效失败：事务回滚并保留失败证据。
- 已生效且可逆：提出新的反向 Change Request，重新审核批准。
- 已生效且不可逆/被下游引用：禁止直接恢复旧快照，应设计补偿变更。
- 历史审计永不删除；回退本身也是新的审计事实。

## 14. 审计闭环设计

### 14.1 必须记录的证据

| 字段 | 内容 |
|---|---|
| Before（变更前） | 生效前服务端正式事实快照 |
| After（变更后） | 获批并实际保存的事实快照 |
| Operator（操作者） | 实际执行写入的用户账户 |
| Requester（申请人） | 提出业务变更的自然人 |
| Data Steward | 准备和维护申请的人 |
| Reviewer（审核人） | 独立审核人及时间、意见 |
| Approver（批准人） | 独立批准人及时间、条件 |
| Effective Date（生效时间） | 业务生效时间与实际执行时间 |
| Reason（原因） | 可审计的业务原因 |
| Impact Analysis | 依赖、风险、RRE/BAC/Workflow 复核结果 |
| Authorization Evidence | 动作、Permission、Scope、ALLOW/DENY |
| Payload Hash | 批准内容完整性摘要 |
| Readback Evidence | 保存后服务端回读结果 |

### 14.2 现有审计复用策略

OrganizationOperatingAuditRecord 继续记录正式写入的 action、actor、organization、target、reason、Before、After 和时间。变更申请、审核、批准与影响分析证据如何持久化，需要 OOM-4 做最小 Schema/服务决策。

禁止把全部审批证据塞入前端缓存、日志文本或 `reason` 单字段；也禁止未经设计直接新增“V2 审计表”。

### 14.3 回读闭环

正式成功必须同时满足：

```text
事务提交成功
+ 审计记录成功
+ 服务端正式事实回读一致
+ 影响复核通过
= EFFECTIVE
```

任一条件不满足，页面不得显示“治理闭环完成”。

## 15. 页面与服务目标职责

### 15.1 `#/organization` 页面

未来允许：

- 新建/编辑变更草稿；
- 查看 Before/After；
- 展示影响分析；
- 提交审核；
- 对具备独立身份的用户展示审核/批准动作；
- 查看计划生效时间、执行结果、审计与回读。

未来禁止：

- 用“保存”按钮直接改变正式事实；
- 由页面计算或补齐影响事实；
- 同一用户在同一申请上同时出现提交、审核和批准动作；
- 页面自动创建 Responsibility、PositionResponsibility 或 Employee Assignment；
- 以本地缓存作为批准或回读证据。

### 15.2 OrganizationOperatingService

未来推荐职责：

```text
验证获批 Change Request
→ AuthorizationService 再校验
→ 业务对象不变量校验
→ 原子持久化
→ OrganizationOperatingAuditRecord
→ 服务端回读
```

它不负责替代 Data Owner、Reviewer 或 Approver，也不自行生成申请。

### 15.3 Workflow Runtime

本治理流程不等于授权修改 Workflow Runtime。未来如选择用工作流编排申请流程，Workflow 也只能编排治理状态，不能自行创造或改写组织事实；最终写入仍必须由组织服务完成。

## 16. 对象级变更闭环矩阵

| 对象 | 申请人 | Data Steward | Reviewer | Approver | 主要影响 | RRE 复核 |
|---|---|---|---|---|---|---|
| Company | 企业治理负责人 | 组织主数据管理员 | 法务/财务/架构 | 授权高管/治理委员会 | 全局组织与范围 | 必须，极高 |
| Organization Unit/Department | 业务单元负责人 | 组织管理员 | 上级组织 + 架构 | 公司组织治理批准人 | 岗位、员工、范围 | 必须 |
| Position | 用岗部门负责人 | 岗位管理员 | 上级组织 + HR | 公司组织治理批准人 | 任职、岗位责任 | 必须 |
| Responsibility | 业务领域负责人 | 责任目录管理员 | 业务专家 + 架构 | 跨域责任治理批准人 | BAC、岗位责任、流程 | 必须 |
| PositionResponsibility | 岗位/责任 Owner | 关系管理员 | 双方 Owner | 独立组织治理批准人 | 责任候选 | 必须 |
| Employee Assignment | 用人部门/HR | 人事任职管理员 | 岗位 Owner/部门负责人 | HR 授权批准人 | 当前责任人、历史时点 | 必须 |

## 17. 验收方案

| 编号 | 验收场景 | 预期结果 |
|---|---|---|
| OOM32-T01 | 页面尝试直接修改正式组织事实 | 不允许；必须先形成 Change Request |
| OOM32-T02 | 申请人审核自己的申请 | 拒绝 |
| OOM32-T03 | 审核人同时批准同一申请 | 拒绝 |
| OOM32-T04 | 批准后修改 After 内容 | 原批准失效，重新审核 |
| OOM32-T05 | 未到生效时间执行 | 不写入 |
| OOM32-T06 | 生效前正式事实已漂移 | 阻断并重新分析 |
| OOM32-T07 | 无维护 Permission 的执行人 | AuthorizationService DENY / HTTP 403 / 写入 0 |
| OOM32-T08 | 岗位变更自动改 Responsibility/Permission/Workflow | 不得发生 |
| OOM32-T09 | Responsibility 退役仍被 BAC 引用 | 阻断，先完成引用治理 |
| OOM32-T10 | PositionResponsibility 取消导致无责任人 | 影响分析明确 RRE 未解析风险，不自动兜底 |
| OOM32-T11 | 员工调岗 | 只改任职，历史保留，不改 BAC/责任/权限/流程 |
| OOM32-T12 | 保存后审计与回读 | Before/After、全角色、时间、原因、回读一致 |
| OOM32-T13 | 生效事务失败 | 原子回滚，正式事实不部分改变 |
| OOM32-T14 | 已生效变更回退 | 新申请、新批准、新审计，不删除原历史 |

## 18. OOM-4 前置条件

只有同时满足以下条件，才可以提交 OOM-4 Organization Model Implementation（组织模型实施）授权评审：

1. OOM-3.1 治理角色已由企业实名确认，且能满足自然人级职责分离。
2. 本报告的 Change Request 状态机、影响等级、审核与批准规则获得人工架构批准。
3. 明确变更申请、审核、批准、Payload Hash、计划生效和回读证据的最小持久化方案。
4. 决定复用/扩展现有 OrganizationOperatingAuditRecord 的边界，禁止重复审计事实源。
5. OOM-2 Employee Assignment 与 PositionResponsibility 时态 Schema 获得独立 Migration 授权。
6. 定义 `#/organization` 从即时保存到申请式维护的兼容和切换策略。
7. 定义 OrganizationOperatingService 对获批申请的强制校验接口，但尚未实施。
8. 定义公司合并、组织迁移和员工调岗的原子性/补偿策略。
9. 建立 BAC 引用、Workflow 引用和未来 RRE 影响的只读分析契约。
10. 完成安全、审计、回退、并发、时间边界与历史查询验收设计。
11. BAC-1 Implementation、RRE-1 与 Workflow Integration 继续保持各自独立授权，不因 OOM-4 自动开放。

在上述条件未满足并获得新授权前：

```text
Organization Model Implementation = NOT AUTHORIZED
OOM-4 = NOT STARTED
```

## 19. 风险清单

| 风险 | 影响 | 控制 | 优先级 |
|---|---|---|---|
| 有维护权限即直接保存 | 绕过业务治理 | Change Request 强制门禁 | P0 |
| 申请/审核/批准为同一自然人 | 自建自批 | 身份级职责分离 | P0 |
| 批准后 Payload 被修改 | 批准证据失真 | Payload Hash，修改即重审 | P0 |
| 计划生效时事实已漂移 | 覆盖他人变更 | Before Snapshot 乐观校验 | P0 |
| Responsibility 变更未检查 BAC | 动作引用失效 | 强制引用影响分析 | P0 |
| 员工变化自动改权限/流程 | 语义层混合 | 严格对象边界与独立申请 | P0 |
| Workflow 被用作事实写入者 | 第二事实源 | 最终写入收敛至组织服务 | P0 |
| RRE 自动修复无候选 | 隐藏治理缺陷 | 明确 unresolved/multiple 状态 | P0 |
| 回溯修改覆盖历史 | Evidence 不可信 | 时态关系、禁止覆盖 | P0 |
| 公司/组织合并部分成功 | 企业事实不一致 | 分阶段检查点与补偿设计 | P1 |
| 页面缓存作为影响事实 | 前后端漂移 | 服务端分析与回读 | P1 |
| AI 建议自动生效 | 无人类责任主体 | AI 无写入/批准权 | P1 |

## 20. 本阶段保护确认

本任务只新增本设计文档。仓库在任务开始前已有其他未提交内容；本任务未修改、清理或归属判断这些既有内容。以下状态指本任务本身：

```text
Documentation Changed = YES
Code Changed = NO
Database Changed = NO
Migration Created = NO
API Created = NO
Organization Data Changed = NO
Responsibility Data Changed = NO
Employee Data Changed = NO
Permission Model Changed = NO
Workflow Runtime Changed = NO
ApprovalTask Changed = NO
RRE Started = NO
Unauthorized Business Writes = 0
```

## 21. 最终状态与停止条件

```text
OOM-3.2 Governance Process Design = COMPLETE
Organization Model Implementation = NOT AUTHORIZED
OOM-4 = NOT STARTED
RRE-1 = NOT AUTHORIZED
Workflow Integration = NOT AUTHORIZED
```

本报告完成后停止。下一步仅允许人工架构与治理评审；未经新的明确授权，不得修改代码、数据库、Migration、API、组织数据、责任数据、员工任职、Permission、Workflow Runtime、采购业务或启动 RRE。
