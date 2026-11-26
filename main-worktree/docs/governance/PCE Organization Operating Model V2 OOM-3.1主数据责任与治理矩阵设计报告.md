# PCE Organization Operating Model V2 OOM-3.1 主数据责任与治理矩阵设计报告

日期：2026-08-18  
阶段：OOM-3.1 Data Governance Design（OOM-3.1 数据治理设计）  
任务类型：DESIGN ONLY（仅设计）  
实施授权：NOT AUTHORIZED（未授权实施）

## 1. 报告结论

本报告为 Company（公司）、Organization Unit（组织单元）、Job Family（岗位族）、Job Level（岗位等级）、Position（岗位）、Responsibility（职责/责任定义）、PositionResponsibility（岗位责任关系）与 Employee Assignment（员工任职关系）建立统一治理责任矩阵。

正式结论如下：

- 企业事实由业务 Data Owner（数据所有者）定义，由 Data Steward（数据管理员）维护，由独立 Reviewer（审核人）审核，由独立 Approver（批准人）批准生效。
- “提出/录入、审核、批准/生效”不得由同一治理角色包办；同一自然人不得审批自己发起或维护的变更。
- AuthorizationService（统一授权服务）只判断操作者能否执行维护动作，不替代业务审核或批准。
- Workflow Runtime（流程运行引擎）、Responsibility Resolution Engine（责任解析引擎，RRE）、页面与 AI（人工智能）只能消费、校验或建议，不得创造企业主数据事实。
- Responsibility 是责任唯一事实；Position 只能承担已有责任；Employee 通过有效任职关系承接岗位责任。
- Job Level 只服务职业发展、薪酬与分析，不决定 Responsibility、Role（角色）、Permission（权限）或审批人。

状态：

```text
OOM-3.1 Governance Matrix Design = COMPLETE
Organization Model Implementation = NOT AUTHORIZED
OOM-4 = NOT STARTED
RRE-1 = NOT AUTHORIZED
Workflow Integration = NOT AUTHORIZED
```

## 2. 审计依据、关键原文与判断

以下内容均从 `D:\Dev-PCE\Source` 的正式文件读取。本节保留关键原文片段，使架构判断可直接复核。

### 2.1 Business Action Contract（业务动作契约）依据

#### 2.1.1 BAC-0 架构签发基线

文件：`D:\Dev-PCE\Source\docs\governance\PCE Business Action Contract V1 BAC-0架构签发报告.md`  
用途：确认 Business Action（业务动作）的权威来源以及责任、权限、工作流边界。

关键原文：

> “本次批准代表架构规则批准，不代表代码实施批准。”

> “当前仓库尚未实施完整 Server Business Action Contract（服务端业务动作契约），尤其尚未建立 `requiredResponsibility` 字段。”

> “`backend/system/authorization.py`：AuthorizationService 统一授权裁决，只负责‘是否允许执行’。”

判断：Server Business Action Contract Registry（服务端业务动作契约注册中心）是未来动作唯一事实源；`requiredResponsibility` 与 `requiredPermission` 必须分离。BAC-0 不构成代码或 RRE 实施授权。

#### 2.1.2 BAC-1 契约定义设计

文件：`D:\Dev-PCE\Source\docs\governance\PCE Business Action Contract V1 BAC-1架构与契约定义设计报告.md`  
用途：确认动作契约目标字段、前后端关系及运行时兼容策略。

关键原文：

> “把当前分布在 Frontend Registry（前端注册表）与 ActionPermissionPolicy（动作权限策略）中的动作事实，收敛为一个服务端权威契约。”

> “`requiredResponsibility` 尚不存在。”

> “Meta Runtime 存在由 Schema/Runtime 生成 Workflow Action 的第二前端路径……未来也只能引用 Server Contract 中已有 `actionCode`，不能独立创建动作语义。”

判断：业务动作可引用已有责任，但不能生成责任；前端与流程设计器只能投影或引用服务端契约。

### 2.2 Organization Operating Model（企业组织运行模型）依据

#### 2.2.1 OOM V2 与 BAC 对接设计

文件：`D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 与 Business Action Contract 对接设计报告.md`  
用途：确认组织事实链、现有模型能力及 RRE 边界。

关键原文：

> “当前 `system.Responsibility` 已经是独立责任目录事实源；BAC 只能引用其编码，不能生成责任。”

> “当前 `system.PositionResponsibility` 可以表达‘岗位承担责任’。”

> “Job Family（岗位族）和 Job Level（岗位等级）……不得自动产生责任或权限。”

> “EmployeeReportingRelation（员工汇报关系）只表达直属/职能汇报，不得作为 RRE 找不到责任人时的主管兜底。”

判断：责任、岗位责任和员工任职必须由组织治理产生；RRE 不得以主管、角色、权限或默认值补齐缺失事实。

#### 2.2.2 OOM-1 实施方案设计

文件：`D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-1实施方案设计报告.md`  
用途：确认模型复用、管理责任与实施阶段边界。

关键原文：

> “复用现有 `Company`、`OrganizationUnit`、`Department`、`JobFamily`、`JobLevel`、`Position`、`Responsibility`、`PositionResponsibility`、`Employee`、`User`、`Role` 和 `Permission`，不建设 V2 平行表族。”

> “员工变动只改变任职关系，不修改 Business Action、Workflow、Responsibility 或 Permission。”

判断：OOM-3.1 应治理现有事实与已批准的最小扩展方向，而不是新建平行主数据体系。

#### 2.2.3 OOM-2 Schema（数据结构）决策

文件：`D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-2实施设计与Schema决策报告.md`  
用途：确认时态 EmployeePositionAssignment（员工岗位任职关系）与岗位责任有效期的目标语义。

关键判断摘要：

- EmployeePositionAssignment 用于表达主岗、兼岗、代理、调岗和历史时点；
- PositionResponsibility 需要受控有效期间，支持当前与历史责任证据；
- 上述内容仍属于设计决策，不代表 Migration（数据库迁移）或实施获准。

判断：治理流程必须先定义生效、失效、重叠与历史追溯规则，再允许未来 OOM-4 讨论实施。

#### 2.2.4 OOM-3 数据治理与初始化设计

文件：`D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-3数据治理与初始化方案设计报告.md`  
用途：确认治理角色、四眼原则、初始化及质量门禁。

关键原文与既有设计要点：

> Data Owner（数据所有者）、Data Steward（数据管理员）、Data Custodian（数据保管人）、Approver（批准人）与 Consumer（数据消费者）应分离。

> 数据治理流程应经过管理员校验、所有者审核、独立批准、授权校验、服务保存、审计与回读。

判断：OOM-3.1 将该原则细化为对象级 RACI（负责、批准、协作、知会）与变更控制矩阵，不修改任何数据。

### 2.3 Permission（权限）与 AuthorizationService（统一授权服务）依据

文件：`D:\Dev-PCE\Source\docs\governance\PCE公共组织身份权限核心V1-最终人工验收与封板报告.md`  
用途：确认正式身份、角色、权限、范围与服务端裁决边界。

关键原文：

> “两名业务人员的 Position 均来自 `system.Position`，Role 均来自 `system.Role`；岗位与系统角色是不同字段、不同对象，没有 Position=Role 绑定。”

> “最终决定来自 `AuthorizationService`。”

> “普通用户……后端返回 HTTP 403、`PERMISSION_DENIED`。”

文件：`D:\Dev-PCE\Source\backend\system\authorization.py`  
用途：核对当前统一授权服务的真实运行职责。

关键原文：

```python
permission_codes = sorted(cls._permission_codes(role_codes))
```

```python
class BusinessPermissionAuthorization:
    """Compatibility facade; all decisions now delegate to AuthorizationService."""
```

判断：Role → RolePermission → Permission 是执行能力链；它既不是 Responsibility 来源，也不构成业务主数据批准。治理批准与系统权限校验缺一不可。

### 2.4 Workflow Runtime（流程运行引擎）依据

文件：`D:\Dev-PCE\Source\docs\governance\Runtime职责规范.md`  
用途：确认 Runtime 只按受治理定义运行，不拥有企业事实定义权。

文件：`D:\Dev-PCE\Source\backend\workflow_runtime\action_permissions.py`  
用途：核对当前动作权限校验能力和字段缺口。

关键原文：

```python
class ActionPermissionPolicy:
    actionCode: str
    moduleCode: str
    requiredPermission: str
    role: tuple
    organizationScope: str
    serverValidator: str
```

```python
class ActionPermissionValidator:
```

判断：当前服务端具备动作与权限校验基础，但没有 `requiredResponsibility`。Workflow Runtime 只能引用已发布动作及组织事实；不得维护公司、岗位、责任、员工任职，也不得把 `required_role_code` 写入 Responsibility Code（责任编码）。

## 3. 统一语义边界

| 对象 | 回答的问题 | 唯一事实来源 | 明确禁止 |
|---|---|---|---|
| Position（岗位） | 企业组织中设置了什么职位？ | 组织主数据 | 岗位等同员工、角色、权限或审批人 |
| Responsibility（职责/责任定义） | 企业业务中谁应该承担什么责任？ | Responsibility 目录 | 页面、Workflow、RRE、AI 自动创建 |
| PositionResponsibility（岗位责任关系） | 哪个岗位在何范围、何期间承担责任？ | 岗位责任关系 | 从岗位名称推断或自动分配 |
| Employee Assignment（员工任职关系） | 哪位员工在何期间担任何岗位？ | 正式任职关系 | 用用户角色、主管关系或页面缓存代替 |
| Role（角色） | 用户账户拥有哪组授权能力？ | 统一身份权限模型 | Role 等同 Responsibility |
| Permission（权限） | 账户是否具备动作执行能力？ | Permission 与 RolePermission | 用权限寻找责任人 |
| Business Action Contract（业务动作契约） | 一个动作需要什么责任和权限？ | 服务端契约注册中心 | 创建责任或指定审批人 |
| AuthorizationService（统一授权服务） | 当前执行是否允许？ | 服务端角色、权限和范围事实 | 定义业务责任或批准主数据 |
| RRE | 当前事实下谁应该负责？ | 只读消费 BAC 与 OOM | 创建/修复企业事实、自动兜底 |
| Workflow Runtime | 如何执行已定义流程？ | 已发布流程与契约引用 | 自行创建动作、责任、岗位或人员 |

## 4. 治理角色与职责分离

### 4.1 标准治理角色

| 治理角色 | 核心职责 | 不得承担 |
|---|---|---|
| Data Owner（数据所有者） | 对业务语义、质量、范围和结果负责；批准重大业务定义 | 直接技术落库；批准自己录入的变更 |
| Data Steward（数据管理员） | 受理、录入、校验、去重、准备影响分析、维护草稿 | 审批自己提交的变更；绕过授权 |
| Reviewer（审核人） | 审核业务合理性、上下游影响、时态与冲突 | 作为同一变更的录入人或最终激活人 |
| Approver（批准人） | 独立批准激活、失效、退役等正式状态变化 | 批准本人发起、维护或审核的变更 |
| Data Custodian（数据保管人） | 保障平台、备份、审计、完整性与访问控制 | 决定企业业务语义 |
| Authorized Operator（受权执行人） | 在正式页面/API 中执行已批准变更 | 修改批准内容、替代审核或授权服务 |
| Consumer（数据消费者） | BAC、RRE、Workflow、Digital Twin 等只读消费 | 反向修改主数据 |

### 4.2 强制职责分离规则

1. Initiator（发起人）不得成为同一变更的 Approver。
2. Data Steward 不得审核或批准自己录入的变更。
3. Reviewer 不得执行同一变更的激活、失效或退役。
4. Data Owner 可以批准业务语义，但不得绕过独立 Reviewer；若 Data Owner 是发起人，必须由上一级或跨域批准人批准。
5. Authorized Operator 只能执行已批准的内容；变更批准后如字段发生变化，批准自动失效并重新走流程。
6. 系统管理员、超级管理员或数据库管理员的技术权限不构成 Data Owner 身份。
7. 紧急变更不得降低双人控制；可缩短时限，但仍需不同自然人完成审核与批准，并保留事后复核证据。

最小有效链：

```text
业务提出
  ↓
Data Steward 录入与校验
  ↓
Reviewer 独立审核
  ↓
Approver 独立批准
  ↓
AuthorizationService 校验执行权限
  ↓
受控服务保存
  ↓
Audit（审计）+ Refresh Readback（刷新回读）
```

## 5. 主数据责任与治理矩阵

### 5.1 总矩阵

| 数据对象 | Data Owner（数据所有者） | Data Steward（数据管理员） | Reviewer（审核人） | Approver（批准人） | 允许的维护动作 | 主要影响系统 |
|---|---|---|---|---|---|---|
| Company（公司） | 企业治理负责人/法定组织负责人 | 企业组织主数据管理员 | 财务、法务与架构代表 | 企业架构委员会或授权高管 | 创建、名称/编码受控调整、暂停、失效；不得物理删除 | 全部组织范围、权限 Scope、BAC 范围、RRE、报表 |
| Organization Unit（组织单元） | 公司组织负责人 | 组织主数据管理员 | 上级组织负责人 + 架构审核人 | 公司组织治理批准人 | 创建、层级调整、类型变更、合并、失效 | Department、Position、责任范围、RRE 路径、经营分析 |
| Department/Center/Business Unit（部门/中心/事业部） | 对应业务单元负责人 | 组织主数据管理员 | 上级组织负责人 | 公司组织治理批准人 | 创建、调整、合并、失效 | 岗位归属、员工归属、Scope、RRE 范围 |
| Job Family（岗位族） | 人力资源/组织发展负责人 | 岗位体系管理员 | 业务领域代表 | 人力资源治理批准人 | 创建、改名、合并、暂停、退役 | 岗位分类、职业发展、统计分析 |
| Job Level（岗位等级） | 人力资源薪酬与职级负责人 | 职级管理员 | 薪酬/组织发展审核人 | 人力资源治理批准人 | 创建、调整说明、暂停、退役 | 职业发展、薪酬、分析；不影响责任和权限 |
| Position（岗位） | 用岗部门负责人 | 组织/岗位管理员 | 上级组织负责人 + 人力资源审核人 | 公司组织治理批准人 | 创建、归属调整、岗位族/等级调整、暂停、退役 | PositionResponsibility、任职、RRE、组织报表 |
| Responsibility（职责/责任定义） | 业务领域负责人 | 责任目录管理员 | 业务专家 + 企业架构审核人 | 跨域责任治理批准人 | 新增、修改说明/领域、暂停、退役；编码生效后不可复用 | BAC 引用、PositionResponsibility、流程责任、RRE |
| PositionResponsibility（岗位责任关系） | 责任所属业务负责人 | 组织/责任关系管理员 | 岗位 Owner + 责任 Owner 双方审核 | 独立组织治理批准人 | 建立、PRIMARY/SUPPORTING、范围、有效期、终止 | RRE 候选、职责清单、流程责任证据 |
| Employee（员工档案） | 人力资源负责人 | 人事主数据管理员 | 用人部门审核人 | 人力资源授权批准人 | 建档、基本资料调整、状态变更、离职失效 | 任职、账户身份、报表；不直接产生责任 |
| Employee Assignment（员工任职关系） | 用人部门负责人 | 人事/组织任职管理员 | 岗位 Owner 或上级部门负责人 | 人力资源授权批准人 | 入岗、调岗、离岗、兼岗、代理、结束任职 | 当前责任人、RRE、组织名册、历史证据 |

### 5.2 权限只控制“能否操作”，不替代治理角色

未来实施应复用现有组织维护权限语义，例如结构、部门、岗位、责任和员工关系维护权限；本报告不新增 Permission。系统写入必须经过 AuthorizationService，但拥有维护权限的用户仍须提供已完成审核批准的治理证据。

```text
治理批准 = 业务事实可以生效
Permission = 操作者可以执行系统动作
AuthorizationService = 当前操作最终是否允许
```

三者不得合并。

## 6. 分对象治理规则

### 6.1 Company（公司）

- 创建：由企业治理负责人提出，法务/财务核验主体信息，架构审核组织范围，独立高管批准。
- 修改：公司编码一经被引用原则上不可变；名称变化保留别名和生效时间。
- 失效：必须先完成下属组织、岗位、任职和有效责任关系影响清单；禁止级联物理删除。
- 权限：技术管理员只执行批准结果，不能自行建立 company ID 或默认 `company_id=1` 事实。

### 6.2 Organization Unit（组织单元）及部门、中心、事业部

- 统一组织树是层级事实；Department 等业务主档需明确映射，不得建立第二棵竞争组织树。
- 新建必须声明公司、父级、组织类型、生效日期和负责人。
- 调整父级属于高影响变更，必须做循环校验、跨公司校验和下游岗位/范围影响评估。
- 失效前必须处理有效子单元、岗位和任职，历史路径保留。

### 6.3 Job Family（岗位族）

- 回答“企业有哪些岗位类别”，由人力资源/组织发展维护，业务领域共同审核。
- 不从岗位名称自动推断，不因新增岗位自动创建岗位族。
- 合并或退役时保留历史编码与岗位引用迁移清单。
- 不直接赋予 Responsibility、Role 或 Permission。

### 6.4 Job Level（岗位等级）

- 回答同类岗位的等级分析问题，可服务职业发展、薪酬与经营分析。
- 不建立“等级越高自动审批”或“P4 自动拥有某责任/权限”的规则。
- 等级调整不得自动修改 PositionResponsibility、RolePermission 或审批人。
- 是否需要桥梁关系须在未来独立 Schema 决策中说明；OOM-3.1 不授权新增表。

### 6.5 Position（岗位）

- 岗位是组织职位，不是员工、角色或审批人。
- 创建必须声明组织归属、岗位族、岗位等级、状态与生效时间；不自动生成责任。
- 组织归属调整前必须评估岗位责任范围和所有有效任职。
- 退役顺序：停止新增任职 → 结束/迁移任职 → 终止未来责任关系 → 退役岗位；历史关系保留。

### 6.6 Responsibility（职责/责任定义）

责任治理采用最高强度控制：

- Data Owner：业务领域负责人，定义业务语义及使用边界。
- Data Steward：责任目录管理员，检查编码、重名、生命周期和引用影响。
- Reviewer：业务专家与企业架构审核人共同审核，避免岗位化、人名化和权限化命名。
- Approver：未参与录入/审核的跨域责任治理批准人。
- 编码采用“业务对象 + 责任目的”，生效后不可复用；语义实质变化应退役旧责任并建立新责任。
- 页面只能创建“草稿申请”，不能绕过治理直接形成 Active（有效）责任。
- Workflow、RRE、BAC、AI、岗位页、员工页均不得创建 Responsibility。
- AI 只可推荐、查缺、识别冲突；建议必须由人类治理链确认。

### 6.7 PositionResponsibility（岗位责任关系）

- 关系必须引用已有且在目标时点有效的 Position 与 Responsibility。
- PRIMARY（主责）与 SUPPORTING（协助）是承担类型，不是候选人自动优先级；RRE 遇到多候选仍按正式解析规则返回冲突。
- 责任 Owner 与岗位 Owner 必须双向审核；独立批准人决定生效。
- 必须治理公司/组织范围、生效与失效时间、重叠、空档和历史证据。
- 禁止由岗位名称、员工姓名、Role、Permission 或 Workflow 自动生成关系。

### 6.8 Employee Assignment（员工任职关系）

- 入岗：人事管理员录入，岗位 Owner 核验岗位与容量，人力资源批准生效。
- 调岗：旧任职设置明确结束时点，新任职设置开始时点；不得覆盖历史记录。
- 离岗：结束全部需终止的有效任职，并进行未解析责任风险检查；不修改责任定义。
- 兼岗：必须声明任职类型、范围、有效期和批准依据；不得因同一员工权限较多而自动兼岗。
- 代理：必须有明确开始、结束和业务批准；到期自动成为无效事实，但是否自动关闭需后续实施设计。
- User（用户账户）绑定只提供执行身份；员工任职与用户授权仍是两套事实。

## 7. 变更影响分析矩阵

| 变更对象 | 必查直接影响 | 必查间接影响 | 禁止的自动副作用 | 风险级别 |
|---|---|---|---|---|
| Company | 下属组织、公司范围、有效岗位/任职 | BAC scopeDimensions、Authorization Scope、RRE | 自动迁移公司、重写历史 | 极高 |
| Organization Unit/Department | 子节点、岗位、员工、负责人 | 权限范围、RRE 组织过滤、报表 | 自动重挂全部对象 | 高 |
| Job Family | 所属岗位与分类报表 | 职业发展、统计口径 | 生成责任或权限 | 中 |
| Job Level | 岗位等级引用、薪酬分析 | 人才发展与经营分析 | 决定责任、权限、审批人 | 中 |
| Position | 任职、岗位责任、上下级岗位 | RRE 候选与组织模型展示 | 自动迁移责任、赋予 Role | 极高 |
| Responsibility | BAC 引用、岗位责任、流程责任配置 | RRE 可解析性、审计解释 | 自动改 Permission 或审批任务 | 极高 |
| PositionResponsibility | 当前/未来责任候选、重叠/空档 | RRE 结果、流程责任证据 | 按 ID/权限/姓名选人 | 极高 |
| Employee Assignment | 当前任职、兼岗、代理、离岗 | RRE 当前责任人、历史 Evidence | 修改 BAC、Workflow、责任或权限 | 极高 |

### 7.1 三类关键变更的门禁

#### 修改 Position（岗位）

必须输出：受影响 Organization Unit、所有有效 PositionResponsibility、所有当前/未来 Employee Assignment、RRE 候选变化和回退方案。不得因岗位变更自动更改 Role 或 Permission。

#### 修改 Responsibility（职责/责任定义）

必须输出：所有 BAC `requiredResponsibility` 引用、PositionResponsibility、PositionWorkflowResponsibility 以及未完成流程的语义影响。已发布编码不可原地改成另一业务含义。

#### 修改 Employee Assignment（员工任职关系）

必须输出：变更前后岗位、时点、任职类型、受影响责任集合和历史解析证据。员工变化只改变任职事实，不改变 BAC、Responsibility、Workflow 或 Permission。

## 8. 生命周期与变更控制

### 8.1 通用生命周期

```text
DRAFT（草稿）
  ↓ 审核通过
REVIEWED（已审核，治理过程状态）
  ↓ 独立批准
APPROVED（已批准，治理过程状态）
  ↓ 受权执行并回读
ACTIVE（有效）
  ↓
SUSPENDED（暂停）或 RETIRED/EXPIRED（退役/失效）
```

`REVIEWED` 与 `APPROVED` 是治理过程状态，不要求本轮新增数据库枚举；未来可由变更申请/审计证据表达。各实体应继续使用其已批准生命周期，禁止为统一界面强改模型。

### 8.2 修改与历史追溯

- 技术字段、业务字段和关系字段均须记录 Before（修改前）、After（修改后）、Operator（操作者）、Reason（原因）、Time（时间）与批准证据。
- 对生效日期、组织层级、岗位归属、责任语义、岗位责任和员工任职的变更，不得覆盖历史。
- 物理删除只允许针对从未生效、未被引用且经独立批准的错误草稿；正式事实一律停用、失效或退役。
- 未来实施必须提供保存后服务端回读，不得以页面缓存作为验收证据。

## 9. 数据维护流程设计

| 阶段 | 输入 | 责任角色 | 必须证据 | 失败处理 |
|---|---|---|---|---|
| 申请 | 变更原因、对象、目标值、生效时间 | 业务申请人 | 业务依据 | 退回补充 |
| 录入与预检 | 草稿、重复/引用/时间检查 | Data Steward | 校验结果、影响清单 | 不进入审核 |
| 业务审核 | 语义、范围、合理性 | Reviewer | 审核意见 | 驳回或重提 |
| 独立批准 | 风险、职责分离、实施窗口 | Approver | 批准人、时间、条件 | 保持草稿 |
| 权限校验 | 操作者、业务动作、范围 | AuthorizationService | ALLOW/DENY | HTTP 403，不写入 |
| 保存 | 已批准变更 | 受权服务/Operator | 事务结果 | 整体回滚 |
| 审计与回读 | Before/After、原因、批准证据 | 审计服务/Data Steward | 服务端回读 | 标记异常、禁止宣告完成 |
| 影响复核 | 下游只读验证 | Data Owner/Reviewer | 影响对象清单 | 启动受控回退 |

本报告不要求 Workflow Runtime 执行上述治理流程；在其获得专门实施授权前，可由正式变更单与审计记录承载，但不得省略职责分离。

## 10. 初始化治理原则

1. 不按岗位名称、部门名称、员工姓名或 Role 自动生成 Responsibility。
2. 不批量推断 PositionResponsibility；每条关系必须由责任 Owner 和岗位 Owner 确认。
3. 不把 `Employee.position_ref` 未经治理地扩展成兼岗或代理事实。
4. 初始化顺序为 Company → Organization Unit/Department → Job Family/Job Level → Position → Responsibility → PositionResponsibility → Employee Assignment。
5. 每批初始化必须先 Dry Run（试运行）与差异清单，再由不同人员审核、批准；本阶段不执行导入。
6. 冲突、重复、跨公司、时间重叠、孤儿引用和历史缺口必须阻断发布，不得由管理员兜底。

## 11. 面向 BAC、RRE、Workflow 与 AI 的消费边界

### 11.1 BAC

Server Business Action Contract 只能通过 `requiredResponsibility` 引用已治理责任，通过 `requiredPermission` 引用权限；两者相互独立。BAC 不拥有责任的创建、修改或退役权。

### 11.2 RRE

RRE 未来只读消费：

```text
Business Action Contract
  + Responsibility
  + PositionResponsibility
  + Position
  + Employee Assignment
  → Resolution Result（解析结果）
```

无事实返回 unresolved，多候选返回 multiple candidates；不得自动找主管、管理员或有权限的人。

### 11.3 Workflow Runtime

Workflow Node（流程节点）只能引用已有动作契约；Workflow Runtime 不维护组织、岗位、责任或员工任职。`ApprovalTask.required_role_code` 保持 Role 语义，不得写入 Responsibility Code。

### 11.4 AI 与 Digital Twin（数字孪生）

- AI 可以建议、检测缺失、识别冲突和解释影响；不得创建、批准或激活事实。
- Digital Twin 可以读取受治理事实及其版本进行观察；不得成为回写主数据的旁路。

## 12. 验收设计

### 12.1 治理设计验收

| 编号 | 场景 | 预期结果 |
|---|---|---|
| GOV-01 | 同一用户创建并尝试批准 Responsibility | 拒绝，职责分离不满足 |
| GOV-02 | 岗位管理员从岗位页创建 Responsibility | 拒绝，只能引用已有责任 |
| GOV-03 | Job Level 升级触发责任或权限变化 | 不发生任何自动变化 |
| GOV-04 | PositionResponsibility 跨公司绑定 | 拒绝并记录原因 |
| GOV-05 | 同一责任产生多个有效候选 | 保留真实多候选事实；不得自动选人 |
| GOV-06 | Employee 调岗 | 旧任职保留历史，新任职按时点生效 |
| GOV-07 | 无维护 Permission 的用户执行写入 | AuthorizationService 返回 DENY/HTTP 403，写入为 0 |
| GOV-08 | 审批后内容被修改 | 原批准失效，重新审核批准 |
| GOV-09 | 责任退役仍被 ACTIVE BAC 引用 | 阻断退役或先完成受控引用迁移 |
| GOV-10 | 页面刷新回读 | 与同一服务端事实一致，不使用前端缓存补齐 |

### 12.2 OOM-4 前置门禁

进入任何实施讨论前，必须由人工确认：

- 每类主数据的 Data Owner、Data Steward、Reviewer、Approver 已实名授权；
- 职责分离冲突规则已确定；
- 变更申请、批准证据、审计与回退载体已确定；
- OOM-2 Schema 决策获得独立实施授权；
- BAC-1 Implementation 与 RRE-1 仍按各自授权门禁推进；
- 未授权状态下不得以页面功能、脚本或 SQL 导入数据。

## 13. 风险清单

| 风险 | 影响 | 控制措施 | 优先级 |
|---|---|---|---|
| 超级管理员兼任所有治理角色 | 自建、自批、自执行 | 自然人级职责分离、批准证据绑定 | P0 |
| Responsibility 被页面/流程自动创建 | 责任目录失真、RRE 不可解释 | 唯一目录、写入口收敛、禁止消费者回写 | P0 |
| Position/Role/Responsibility 混用 | 错误授权或错误责任人 | 语义校验、字段隔离、评审清单 | P0 |
| 任职无有效期或覆盖历史 | 无法按时点解析 | 时态模型、禁止覆盖、重叠校验 | P0 |
| 岗位责任多人候选被静默选一人 | 绕过企业治理 | 明确冲突结果、人工配置范围 | P0 |
| 组织层级调整未做影响分析 | 权限范围及 RRE 候选漂移 | 变更前依赖清单和双人批准 | P1 |
| Job Level 被用于自动审批 | 职级与责任混淆 | 明确禁止并建立测试门禁 | P1 |
| Workflow/RRE 反向修复主数据 | 第二事实源 | 只读接口与零写入约束 | P0 |
| AI 建议被自动采纳 | 无人类责任主体 | 人工批准、AI 无写权限 | P1 |

## 14. 本阶段保护结果

本任务只新增本治理设计文档。仓库原有工作树包含其他未提交内容，本任务未修改、清理或归属判断这些既有内容；以下状态均指本任务自身行为。

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

## 15. 最终状态与停止条件

```text
OOM-3.1 Governance Matrix Design = COMPLETE
Organization Model Implementation = NOT AUTHORIZED
OOM-4 = NOT STARTED
RRE-1 = NOT AUTHORIZED
Workflow Integration = NOT AUTHORIZED
```

本报告完成后停止。下一步只能进行人工架构与数据治理评审；未经新的明确授权，不得进入代码、Schema、Migration、API、组织数据初始化、RRE 或 Workflow 集成实施。
