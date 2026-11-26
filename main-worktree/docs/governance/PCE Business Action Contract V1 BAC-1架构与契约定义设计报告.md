# PCE Business Action Contract V1 BAC-1架构与契约定义设计报告

报告日期：2026-08-17  
阶段：BAC-1 Architecture & Contract Definition Design（BAC-1 架构与契约定义设计）  
任务性质：DESIGN ONLY（仅设计）  
实施授权：NOT AUTHORIZED（未授权实施）  
RRE-1 状态：NOT AUTHORIZED（未授权实施）

---

## 1. 设计目标

本报告设计 Server Business Action Contract（服务端业务动作契约）的完整模型、唯一 Contract Registry（契约注册中心）、编码规则、生命周期、校验规则、兼容策略和未来消费关系。

目标是把当前分布在 Frontend Registry（前端注册表）与 ActionPermissionPolicy（动作权限策略）中的动作事实，收敛为一个服务端权威契约：

```text
Server Business Action Contract
        ↓
Frontend Projection
        ↓
User Action
        ↓
Server Validation
        ↓
Responsibility Resolution / Authorization
        ↓
Workflow / Execution
```

本报告不修改代码、数据库、Migration（数据库迁移）、API（接口）、ActionPermissionPolicy、AuthorizationService（统一授权服务）、Workflow Runtime（流程运行引擎）、ApprovalTask（审批任务）或采购流程。

---

## 2. 设计依据与基线

### 2.1 已批准架构基线

已完整读取：

`D:\Dev-PCE\Source\docs\governance\PCE Business Action Contract V1 BAC-0架构签发报告.md`

基线文件：509 行。读取时 SHA256：

```text
AF7F93522C686ADB67A1AC303ED2DDAEFFE8DBE406B7B939736C777757C9E99D
```

BAC-0 已冻结：

```text
BAC-0 = BASELINED
Human Architecture Approval = APPROVED
Architecture Baseline Status = ESTABLISHED
BAC-1 = DESIGN ONLY
BAC-1 IMPLEMENTATION = NOT AUTHORIZED
RRE-1 = NOT AUTHORIZED
```

### 2.2 既有分析结论

《PCE Business Action Contract V1设计与治理分析报告》已确认：

- 当前完整 Business Action Contract 不存在；
- Frontend Registry 拥有 UI 动作定义；
- 后端 ActionPermissionPolicy 拥有服务端权限策略；
- 两者存在重复实现面；
- `requiredResponsibility` 尚不存在；
- Server Business Action Contract Registry 必须成为唯一运行事实源。

### 2.3 本轮真实仓库读取范围

| 实际路径 | 用途 | 读取行数 |
|---|---|---:|
| `frontend/src/meta/runtime/pceBusinessActionRegistry.js` | 前端动作注册、展示、状态和权限投影 | 1,138 |
| `frontend/src/meta/components/PceBusinessActionBar.vue` | 前端按钮与服务端权限校验 | 240 |
| `frontend/src/meta/core/pageRenderer.js` | Meta Runtime 动作渲染和执行入口 | 2,831 |
| `frontend/src/meta/bpm/bpmDesignerEngine.js` | BPM 状态和迁移图设计 | 121 |
| `backend/workflow_runtime/action_permissions.py` | 服务端动作权限 Policy 与 Validator | 970 |
| `backend/workflow_runtime/views.py` | 服务端权限矩阵和校验接口 | 227 |
| `backend/workflow_runtime/models.py` | Workflow 与 ApprovalTask 模型 | 227 |
| `backend/system/authorization.py` | AuthorizationService 授权裁决 | 320 |
| `backend/system/models.py` | Responsibility、Role、Permission 等模型 | 642 |
| `backend/pfm/models.py` | Employee、Position 和 User 关系 | 166 |

扫描结果：

```text
Search Scope = frontend/src/meta + backend
Search Field = requiredResponsibility
Result = NO MATCH
```

---

## 3. 当前状态分析

### 3.1 Frontend Registry（前端注册表）

实际路径：

`D:\Dev-PCE\Source\frontend\src\meta\runtime\pceBusinessActionRegistry.js`

关键原文，第 790—819 行：

```javascript
].map(contract => Object.freeze({
  ...contract,
  actions: Object.freeze(contract.actions.map(item => {
    const requiredPermission =
      `pce.action.${contract.currentModule}.${item.actionId}`
    return Object.freeze({
      ...item,
      actionCode: item.actionId,
      moduleCode: contract.currentModule,
      requiredPermission,
      permission: requiredPermission,
      displayName: item.actionName,
      allowedStatus: [...item.allowedStatuses],
      singleOrBatch: item.scope,
      serverEligibilityCheck: true,
      organizationScope: 'legal_entity',
      serverValidator: 'workflow_runtime.ActionPermissionValidator',
    })
  })),
```

现状判断：

- 已有 `actionCode`、`moduleCode`、`requiredPermission`；
- 已有显示名称、状态、动作范围和校验器信息；
- 未提供 `requiredResponsibility`、`objectType`、`workflowCode`、`nodeCode`、`scopeDimensions`；
- `requiredPermission` 由前端再次拼接，存在与服务端漂移风险；
- Frontend Registry 当前是展示事实源之一，不符合 BAC-0 最终边界。

### 3.2 PceBusinessActionBar（业务动作栏）

实际路径：

`D:\Dev-PCE\Source\frontend\src\meta\components\PceBusinessActionBar.vue`

关键原文，第 21—41 行：

```vue
<el-button
  v-for="action in displayedActions"
  :key="action.actionId"
  :data-pce-action-id="action.actionId"
  :data-pce-action-source="'BusinessActionRegistry'"
  :data-required-permission="action.requiredPermission"
  :data-server-validator="action.serverValidator"
  :disabled="permissionState.loading || !action.enabled"
  @click="execute(action)"
>
  {{ action.actionName }}
</el-button>
```

关键原文，第 170—180 行：

```javascript
const permissionPayload = await validateBusinessActionPermission({
  actionCode: action.actionCode,
  moduleCode: action.moduleCode,
  objectIds: selectedObjectIds.value,
  selectionCount: props.selectedRows.length,
  legalEntityId: selectedLegalEntityId.value,
})
```

判断：页面已经使用 Action Code 提交意图并调用服务端校验；未来应保留这一交互模式，但动作内容必须由 Server Contract Projection 提供。客户端的状态、组织、责任、权限和候选人员均不可信。

### 3.3 Meta Runtime（元运行时）

实际路径：

`D:\Dev-PCE\Source\frontend\src\meta\core\pageRenderer.js`

关键原文，第 1069—1081 行：

```javascript
...workflow.availableActions.map((action) =>
  h(ElButton, {
    disabled: runtime.controlMode === PAGE_STATE.BLOCKED,
    onClick: () => handlers.handleWorkflowAction({
      key: action,
      label: translate(action),
      type: 'workflow',
      workflowAction: action,
    }, record),
  }, () => translate(action))
),
```

关键原文，第 1973—2000 行：

```javascript
const rowRuntime = buildRuntime(runtimeSchema.value, row, pageMode.value)
const workflowAction = action.workflowAction || action.key

if (!(rowRuntime.workflow?.availableActions || []).includes(workflowAction)) return

const workflowResult = await dataGateway.executeState(workflowAction, {
  module: runtimeSchema.value?.api?.module || runtimeSchema.value?.name,
  id: row.id,
  data: row,
})
```

判断：Meta Runtime 存在由 Schema/Runtime 生成 Workflow Action 的第二前端路径。BAC-1 目标要求该路径未来也只能引用 Server Contract 中已有 `actionCode`，不能独立创建动作语义。

### 3.4 BPM Designer（流程设计器）

实际路径：

`D:\Dev-PCE\Source\frontend\src\meta\bpm\bpmDesignerEngine.js`

关键原文，第 38—45 行：

```javascript
export function applyGraphToSchema(graph = {}) {
  return {
    states: (graph.nodes || []).map((node) => node.id),
    transitions: (graph.edges || []).map((edge) => ({
      from: edge.from,
      to: edge.to,
    })),
  }
}
```

判断：当前设计器只管理状态和迁移，没有完整动作契约。未来只允许节点引用已有 Action Contract，不允许设计器创建 Action、Responsibility 或审批人。

### 3.5 ActionPermissionPolicy（动作权限策略）

实际路径：

`D:\Dev-PCE\Source\backend\workflow_runtime\action_permissions.py`

关键原文，第 421—436 行：

```python
@dataclass(frozen=True)
class ActionPermissionPolicy:
    actionCode: str
    moduleCode: str
    requiredPermission: str
    role: tuple
    organizationScope: str
    serverValidator: str
    allowedStatuses: tuple
    scope: str
```

关键原文，第 534—546 行：

```python
policy = ActionPermissionPolicy(
    actionCode=action_code,
    moduleCode=module_code,
    requiredPermission=required_permission_code(module_code, action_code),
    role=action_roles,
    organizationScope=ORGANIZATION_SCOPE,
    serverValidator=SERVER_VALIDATOR,
    allowedStatuses=allowed_statuses,
    scope="batch" if is_batch else "single",
)
policies[(module_code, action_code)] = policy
```

判断：现有 Policy 已有服务端动作注册、权限、角色、状态、范围和校验器，是方案 A 的主要复用基础；但它把“完整动作契约”缩减成权限策略，也包含固定 Role 兼容逻辑，不能直接宣布为完整 Contract。

### 3.6 服务端动作注册与拒绝

同文件第 742—746 行：

```python
policy = POLICIES.get((module_code, action_code))
if not policy:
    return self._decision(
        None, False, "action_not_registered", "业务动作未注册。"
    )
```

判断：未注册动作拒绝机制可直接成为未来 Contract Registry 的基础 Guard；不能再建立第三套 RRE Action Map。

### 3.7 AuthorizationService（统一授权服务）

实际路径：

`D:\Dev-PCE\Source\backend\system\authorization.py`

关键原文，第 43—51 行和第 108—111 行：

```python
def decide(
    cls,
    *,
    user,
    action_code,
    organization_id=None,
    business_object=None,
    context=None,
):
```

```python
if action_code not in permission_codes:
    return cls._deny(decision, "PERMISSION_DENIED", "当前角色未获得该业务动作权限。")
if not scoped_evidence:
    return cls._deny(decision, "SCOPE_DENIED", "当前授权范围不覆盖该组织或业务对象。")
```

判断：当前参数名虽为 `action_code`，实际与 Permission Code 集合比较。未来必须由 Contract 取出 `requiredPermission` 后调用，不得直接混用 Action Code 与 Permission Code。

### 3.8 ApprovalTask（审批任务）

实际路径：

`D:\Dev-PCE\Source\backend\workflow_runtime\models.py`

关键原文，第 122—130 行：

```python
task_no = models.CharField(max_length=80, unique=True)
workflow_instance = models.ForeignKey(
    WorkflowInstance, on_delete=models.PROTECT, related_name="tasks"
)
step_no = models.PositiveIntegerField()
required_role_code = models.CharField(max_length=80)
minimum_approvals = models.PositiveIntegerField(default=1)
allow_parallel = models.BooleanField(default=False)
```

判断：`required_role_code` 继续表示 Role Code，不得写入 Responsibility Code。本阶段不设计或实施 ApprovalTask Schema 变化。

---

## 4. BAC-1 目标架构

### 4.1 完整运行链

```text
Server Business Action Contract Registry
        ↓ authoritative contract
Frontend Projection
        ↓ display only
User Action
        ↓ actionCode + object identity + intent
Server Contract Lookup
        ↓
Business Object Fact Reload
        ↓
ActionPermissionValidator
        ├─ requiredPermission → AuthorizationService
        └─ requiredResponsibility → Responsibility Resolution Engine（未来）
        ↓
Workflow / Domain Guard / Execution（未来独立授权）
```

### 4.2 逻辑所有权

Business Action Contract 属于 Platform Business Action Governance（平台业务动作治理），不是 UI、Workflow、Permission 或 RRE 的私有模型。

逻辑职责：

- Contract Registry 拥有动作定义；
- ActionPermissionValidator 消费动作校验字段；
- RRE 消费责任字段；
- AuthorizationService 消费 Contract 解析出的 Permission Code；
- Workflow Runtime 只引用 Action Code；
- Frontend 只消费展示投影；
- Digital Twin 只消费观察投影。

---

## 5. BusinessActionContract（业务动作契约）模型

### 5.1 规范结构

```text
BusinessActionContract
├─ contractVersion
├─ actionCode
├─ moduleCode
├─ displayName
├─ objectType
├─ requiredResponsibility
├─ requiredPermission
├─ workflowCode
├─ nodeCode
├─ scopeDimensions
├─ allowedStatuses
├─ actionScope
├─ serverValidator
└─ status
```

### 5.2 字段定义

| 字段 | 类型设计 | 必需性 | 规则 |
|---|---|---:|---|
| `contractVersion` | String | 是 | 契约结构版本，不是业务对象版本 |
| `actionCode` | String | 是 | 全局唯一、稳定、不可复用 |
| `moduleCode` | String | 是 | 已注册模块编码 |
| `displayName` | String | 是 | 面向业务用户的中文名称 |
| `objectType` | String | 是 | 服务端 Fact Provider 可识别的对象类型 |
| `requiredResponsibility` | String/Null | 条件必需 | 责任型动作必须引用已有责任编码 |
| `requiredPermission` | String | 是 | 必须引用 Permission Registry |
| `workflowCode` | String/Null | 条件必需 | Workflow 动作必须提供 |
| `nodeCode` | String/Null | 条件必需 | 节点型动作必须提供 |
| `scopeDimensions` | Tuple/List | 是 | 描述需要读取的业务范围维度 |
| `allowedStatuses` | Tuple/List | 是 | 来自 Domain State Contract |
| `actionScope` | Enum | 是 | VIEW/SINGLE/BATCH/SYSTEM |
| `serverValidator` | String | 是 | 受控 Validator Registry Key |
| `status` | Enum | 是 | DRAFT/ACTIVE/SUSPENDED/RETIRED |

### 5.3 不适用字段规则

字段必须存在，不能通过缺字段表达不适用：

- 只读、导航或系统动作不需要责任时：`requiredResponsibility=null`；
- 非 Workflow 动作：`workflowCode=null`、`nodeCode=null`；
- `null` 合法性由 `actionScope`、动作分类和发布校验共同判断。

### 5.4 建议不可变性

ACTIVE 后以下字段视为身份或核心语义，不允许原地改变：

- `actionCode`；
- `objectType`；
- `requiredResponsibility` 的业务语义；
- `requiredPermission` 的业务语义；
- `workflowCode/nodeCode` 的流程语义。

语义变化应创建新 Action Code 或新 Contract Release（契约发布版本），旧动作进入 RETIRED 并保留历史引用。

---

## 6. Contract Registry（契约注册中心）设计

### 6.1 所有者

逻辑所有者：

```text
PCE Platform Business Action Contract Registry
（PCE 平台业务动作契约注册中心）
```

Workflow Runtime、AuthorizationService、RRE 和 Frontend 均为消费者，不拥有 Contract。

### 6.2 存储位置建议

V1 推荐使用 Server-owned Versioned Declarative Registry（服务端版本化声明式注册中心），随服务端发布并受代码评审、静态校验和发布门禁治理。

推荐逻辑位置：

```text
backend/workflow_runtime/business_action_contracts
```

或后续经平台目录评审迁移到中立位置：

```text
backend/business_action_contract
```

BAC-1 Design 不决定最终物理目录，也不创建文件。逻辑所有权必须独立于 Workflow Runtime，即使 V1 为兼容而暂时靠近现有 `action_permissions.py`。

### 6.3 为什么 V1 不优先设计数据库表

Business Action 是软件能力契约，与管理员维护的 Responsibility 主数据不同。动作出现、参数、Validator 和副作用边界通常随软件版本发布。

V1 推荐代码/声明式注册中心，而非动态数据库表，原因：

- 避免数据库配置声明一个代码并不支持的动作；
- Validator 和 Domain Handler 必须与部署版本一致；
- 容易执行静态扫描、契约 Hash 和发布门禁；
- 不需要本阶段 Migration；
- 避免管理员通过数据配置绕过代码审查。

如果未来需要运行时启停，状态可以由受治理的 Release/Control 配置投影控制；是否持久化必须另行设计和授权。

### 6.4 读取方式

服务端内部读取接口概念设计：

```text
getByActionCode(actionCode)
listByModule(moduleCode)
listActiveByObjectType(objectType)
resolveLegacyKey(moduleCode, legacyActionId)
validateContract(actionCode)
```

所有调用返回不可变 Contract Snapshot（契约快照）并带：

```text
contractVersion
registryVersion
contractHash
source = server
```

本报告不创建 API。Frontend Projection 的网络读取方式留待 BAC-1 Implementation 或独立 API 设计授权。

### 6.5 发布方式

建议发布链：

```text
DRAFT Contract
↓ Schema Validation
Reference Validation
↓
Cross-registry Consistency Validation
↓
Compatibility Review
↓
Human Architecture / Module Owner Approval
↓
ACTIVE Release + Registry Version + Hash
```

发布不得自动创建 Permission、Responsibility、Workflow 或业务数据。

---

## 7. 方案 A 与方案 B 比较

### 7.1 方案 A：演进现有 ActionPermissionPolicy

定义：以现有服务端 `POLICIES` 和 `ActionPermissionPolicy` 为迁移基础，将其事实源地位演进为完整 `BusinessActionContract`；原 Policy 变成由 Contract 派生的权限兼容投影。

优点：

- 复用已运行的服务端动作注册；
- 复用未注册动作拒绝机制；
- 复用 ActionPermissionValidator 和 Fact Provider；
- 复用现有服务端契约 View；
- 易于保持当前动作权限行为；
- 避免同时存在 Policy Registry 和 Contract Registry 两个权威源；
- 影响面可分阶段控制。

缺点和风险：

- 当前 Policy 含固定 Role 兼容分支，容易继续混淆责任与授权；
- 当前键是 `(moduleCode, actionCode)`，目标要求全局 Action Code；
- 当前字段名和消费者均围绕 Permission，需要兼容适配；
- 若简单“加字段”而不改变所有权，仍可能把 Contract 错当权限对象；
- 现有大量调用和测试需要未来全量回归。

控制方案：

```text
BusinessActionContract = Canonical Source
ActionPermissionPolicy = Derived Compatibility Projection
```

禁止 Contract 与 Policy 各自人工维护。

### 7.2 方案 B：新建独立模型

定义：保留现有 ActionPermissionPolicy，另建独立 BusinessActionContract 模型或表。

优点：

- 新模型语义干净；
- 不受旧 Policy 字段和角色分支限制；
- 可以独立设计生命周期和版本；
- 初期对现有校验代码影响较小。

缺点和风险：

- 立即形成两套服务端事实源；
- Action、Permission、状态可能漂移；
- RRE 与 Validator 可能读取不同 Registry；
- 需要双写、同步或运行时一致性校验；
- 若采用数据库模型，需要 Migration 和管理权限治理；
- 违反 BAC-0 的单一事实源方向，除非同时退役 Policy 的定义权。

### 7.3 推荐结论

推荐：

```text
方案 A：受治理演进
```

但不是在现有 dataclass 上无边界堆字段，而是：

1. 以当前服务端 Policy Registry 为迁移入口；
2. 设计完整 BusinessActionContract 作为新的 Canonical Type（权威类型）；
3. 现有 ActionPermissionPolicy 由 Contract 派生，只保留兼容输出；
4. ActionPermissionValidator 改为未来消费 Contract 的权限投影；
5. 前端 Registry 改为未来消费 Contract 的展示投影；
6. Policy 与 Frontend 不再独立定义同一事实；
7. 完成消费者迁移后再评审旧 Policy 类型的退役。

推荐原因：最大限度复用当前服务端运行链，同时避免第三套 Registry。

后续实施影响：跨服务端 Policy、View、测试和前端 Projection，属于平台治理变更，必须单独授权并执行全量契约回归。

---

## 8. ActionCode（动作编码）治理

### 8.1 目标格式

```text
business_domain.business_object.action
```

示例：

```text
procurement.purchase_request.approve
procurement.purchase_order.issue
supplier.supplier.review
finance.payment_request.approve
quality.incoming_inspection.confirm
```

### 8.2 命名规则

- 全小写；
- 使用点号分隔业务领域、对象和动作；
- 分段仅允许小写字母、数字和下划线；
- 不包含页面、Route、按钮编号、员工、岗位或 Role 名称；
- 动词使用稳定业务语义，如 `create/submit/approve/reject/confirm/issue/close/view`；
- 一个 Action Code 只表达一个稳定业务意图；
- 禁止同一编码在不同模块复用不同语义。

建议正则：

```text
^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*){2,}$
```

### 8.3 唯一性

目标 `actionCode` 在整个 Server Contract Registry 全局唯一。`moduleCode` 只用于模块归属、查询和展示，不再参与构造唯一主键。

### 8.4 生命周期

- DRAFT 期间可调整编码；
- 首次 ACTIVE 后编码冻结；
- 语义变化创建新编码；
- 旧编码进入 RETIRED；
- 历史 Workflow、Audit、Task 和 Evidence 保留原编码与 Contract Version；
- 已 RETIRED 编码不得重新分配给新语义。

### 8.5 当前兼容方案

当前存在：

```text
actionId
(moduleCode, actionCode)
```

建议建立只读 Legacy Alias（历史别名）概念：

```text
Legacy Key:
  moduleCode + legacyActionId

Canonical Value:
  global actionCode
```

兼容原则：

- 页面和旧 API 可以在迁移期继续提交旧组合键；
- 服务端 Alias Resolver 将其映射到唯一 Canonical Action Code；
- 多个旧键可以映射到一个新编码，但必须证明语义完全相同；
- 一个旧键不得映射到多个新编码；
- 未映射旧动作 Fail Closed；
- 新功能只能使用 Canonical Action Code；
- Alias 只兼容读取和请求解析，不成为第二事实源。

本报告不创建 Alias 表或映射文件。

---

## 9. Responsibility 与 Permission 映射

Contract 同时保存两个独立引用：

```text
BusinessActionContract
├─ requiredResponsibility
└─ requiredPermission
```

责任路径：

```text
requiredResponsibility
↓
Responsibility
↓
PositionResponsibility
↓
Position
↓
Employee
```

授权路径：

```text
requiredPermission
↓
User
↓
Role / RolePermission
↓
Permission
↓
AuthorizationService
```

强制规则：

- Contract 只能引用已有 Responsibility，不能自动创建；
- Permission 不参与责任候选消歧；
- Role 不得作为 Responsibility 引用；
- Position 名称和 Employee 姓名不得写入 Contract；
- 多责任候选保持 `MULTIPLE_CANDIDATES`；
- 责任解析成功但权限拒绝返回独立结果，不更换责任人。

---

## 10. 与 AuthorizationService 的关系

未来调用：

```text
actionCode
↓
BusinessActionContract.requiredPermission
↓
AuthorizationService
↓
ALLOW / DENY
```

### 10.1 ActionCode 与 PermissionCode 是否可相同

允许字符串相同，例如：

```text
actionCode = procurement.purchase_request.approve
requiredPermission = procurement.purchase_request.approve
```

但必须保留两个字段，原因：

- Action 描述业务意图；
- Permission 描述执行能力；
- 一个 Permission 未来可能保护多个细分 Action；
- Action 退役不一定等于 Permission 立即删除；
- 审计必须区分申请了什么动作与依据什么权限放行；
- AuthorizationService 当前实际比较 Permission Code；
- RRE 需要 Action 的 Responsibility，不需要 Permission 作为责任来源。

### 10.2 防止语义混淆

- Contract Builder 禁止用隐式规则替代显式 `requiredPermission`；
- Validator 必须检查 Permission Registry 引用存在；
- Authorization Adapter 只接收 `requiredPermission`；
- 日志同时记录 `actionCode` 和 `permissionCode`；
- 字段即使同值也不能互相覆盖；
- 不建议继续在消费者中用字符串拼接 Permission Code。

本阶段不修改 AuthorizationService 参数或核心逻辑。

---

## 11. 与 Workflow Runtime 的关系

### 11.1 Workflow Node 引用

未来 Workflow Node 只保存或引用：

```text
actionCode
```

运行时：

```text
Workflow Node.actionCode
↓
Server Contract Registry.getByActionCode
↓
objectType / requiredResponsibility / requiredPermission / scopeDimensions
↓
RRE + Authorization（未来）
```

Workflow Node 不复制 Contract 全部字段，避免流程定义持有过期契约副本。历史实例应保存所使用的 `contractVersion` 和必要 Evidence，但该持久化方案不属于 BAC-1 Design 的实施授权。

### 11.2 required_role_code 边界

```text
ApprovalTask.required_role_code = Role Code
```

禁止：

```text
ApprovalTask.required_role_code = Responsibility Code
```

BAC-1 不修改 ApprovalTask，也不设计通过该字段承载责任解析结果。

---

## 12. Frontend Projection（前端展示投影）

### 12.1 目标链

```text
Server Contract
↓
Frontend Projection
↓
Frontend Registry Adapter
↓
PceBusinessActionBar / Meta Runtime / BPM Designer
```

### 12.2 允许的前端字段

前端可以维护纯展示属性：

- 图标；
- 颜色和按钮样式；
- 页面分组；
- 排序；
- 本地化文案覆盖；
- 页面区域；
- 帮助说明。

这些属性不得改变服务端 Action Code 和执行语义。

### 12.3 禁止的前端权力

Frontend Registry 禁止：

- 创建正式 Action；
- 创建 Responsibility；
- 修改 Required Permission；
- 覆盖 Allowed Statuses 的服务端结论；
- 决定 Company/Department Scope；
- 计算或选择审批人；
- 把按钮可见解释为 Authorization；
- 用缓存补齐服务端缺失 Contract。

### 12.4 一致性设计

Frontend Projection 必须携带：

```text
contractVersion
registryVersion
contractHash
source = server
```

版本或 Hash 不一致时：

- 写动作禁用；
- 返回 Contract Version Mismatch；
- 重新加载服务端投影；
- 禁止使用旧页面定义继续执行。

---

## 13. Contract 生命周期

### 13.1 DRAFT（草稿）

- 可以创建和编辑；
- 不进入生产 Registry；
- 不被 UI、Workflow、RRE 或 Execution 消费；
- 可运行静态和引用校验。

### 13.2 ACTIVE（有效）

- 已通过完整校验和人工发布批准；
- 可由正式消费者读取；
- 核心语义冻结；
- 发布时生成 Registry Version 和 Contract Hash。

### 13.3 SUSPENDED（暂停）

- 临时禁止新动作执行；
- 保留历史读取和审计；
- 页面投影显示不可用原因；
- 不删除 Permission、Responsibility 或历史 Workflow；
- 恢复 ACTIVE 需要重新校验和明确批准。

### 13.4 RETIRED（退役）

- 永久停止新业务使用；
- 保留历史引用；
- 不允许恢复 ACTIVE；
- 新语义必须使用新 Action Code；
- 历史任务、审计和 Evidence 仍可解释原 Contract。

### 13.5 生命周期迁移

```text
DRAFT → ACTIVE
DRAFT → RETIRED
ACTIVE → SUSPENDED
SUSPENDED → ACTIVE
ACTIVE → RETIRED
SUSPENDED → RETIRED
```

禁止：

```text
RETIRED → ACTIVE
ACTIVE → DRAFT
```

---

## 14. Contract Validation（契约校验）

Contract 成为 ACTIVE 前必须通过以下校验。

### 14.1 Schema 校验

- 14 个标准字段全部存在；
- 字段类型正确；
- 条件不适用字段显式为 `null`；
- Enum 值来自受控集合；
- `scopeDimensions`、`allowedStatuses` 不包含重复值。

### 14.2 Action Code 校验

- 满足命名正则；
- 全局唯一；
- 未被历史 RETIRED 动作占用；
- 不包含员工、岗位、Role、页面或按钮名称；
- Legacy Alias 无一对多冲突。

### 14.3 对象和状态校验

- `objectType` 已在服务端 Fact Provider/对象注册中心登记；
- `allowedStatuses` 全部存在于对象 Domain State Contract；
- `*` 只允许明确受控的 VIEW 类动作；
- 写动作不得在未知状态开放。

### 14.4 Permission 校验

- `requiredPermission` 非空；
- Permission Registry 中存在；
- Permission 状态可用；
- 不自动创建 Permission；
- 不能只凭 Role 存在判定合法。

### 14.5 Responsibility 校验

- 责任型动作的 `requiredResponsibility` 非空；
- 引用的 Responsibility 存在；
- 发布时处于可配置状态；
- 不根据 Action Code 自动生成 Responsibility；
- 不以 Role、Position 或 Employee 替代；
- 无需责任的动作必须满足受控豁免规则。

### 14.6 Workflow 校验

- Workflow 动作的 `workflowCode` 存在；
- `nodeCode` 属于该 Workflow；
- Node 引用同一 `actionCode`；
- Contract 不把 Responsibility 写入 `required_role_code`；
- 非 Workflow 动作的两个字段显式为 null。

### 14.7 Scope 校验

V1 业务上下文维度建议：

```text
COMPANY
DEPARTMENT
BUSINESS_OBJECT
OWNER
```

这些是解析所需维度，不等于 Authorization 的授予范围。AuthorizationService 正式授权范围继续使用：

```text
SELF
DEPARTMENT
ORGANIZATION
ALL
```

禁止把 `ALL` 当业务对象维度，禁止由前端 Legal Entity 参数决定最终 Scope。

### 14.8 Validator 校验

- `serverValidator` 必须存在于服务端受控 Validator Registry；
- 禁止客户端提供任意 import path；
- Validator 必须支持对应 Object Type；
- Validator 必须重新读取业务对象和当前状态；
- 写动作必须 Fail Closed。

### 14.9 发布一致性校验

- Server Registry Version 已生成；
- Contract Hash 稳定；
- Frontend Projection 可由同一 Contract 生成；
- ActionPermission Projection 与 Contract 一致；
- 无未映射正式页面动作；
- 无重复 Registry；
- 无业务数据写入副作用。

---

## 15. 兼容与迁移策略设计

这里的 Migration Strategy（迁移策略）是契约和消费者迁移设计，不是数据库 Migration。本阶段禁止创建数据库迁移。

### Phase C0：盘点冻结

- 冻结前端 Registry 和后端 Policy 清单；
- 比对动作数量、组合键、权限、状态和角色；
- 记录版本与 Hash；
- 不改变运行行为。

### Phase C1：Canonical Contract Schema

- 经新授权后定义 BusinessActionContract 类型；
- 建立校验器和隔离测试；
- 不切换消费者。

### Phase C2：生成兼容投影

- 由 Canonical Contract 生成 ActionPermissionPolicy Projection；
- 证明现有 Validator 决策无变化；
- 旧 `POLICIES` 不再独立维护。

### Phase C3：Legacy Action Alias

- 建立旧 `(moduleCode, actionId)` 到 Canonical Action Code 的映射；
- 未映射动作阻断；
- 新动作只使用全局编码。

### Phase C4：Frontend Projection

- Frontend Registry 改为展示适配器；
- Meta Runtime 和 BPM 只引用已有 Action Code；
- 前后端版本和 Hash 一致。

### Phase C5：RRE Readiness Gate

- Contract 正式提供 `requiredResponsibility`；
- RRE 所需字段校验通过；
- 零业务写入验收通过；
- 人工决定是否授权 RRE-1。

### Phase C6：Workflow/Execution 专项

- 不属于 BAC-1；
- 必须独立审核 Workflow、ApprovalTask、Evidence、回退和业务保护。

---

## 16. RRE Dependency（责任解析依赖）检查

未来 RRE-1 的最小 Contract 输入：

| 字段 | 用途 | BAC-1 设计状态 | 当前实现状态 |
|---|---|---|---|
| `actionCode` | 唯一动作身份 | 已定义 | 存在旧形式，未全局治理 |
| `objectType` | 服务端读取业务对象 | 已定义 | Contract 中不存在 |
| `requiredResponsibility` | 定位责任主数据 | 已定义 | 不存在 |
| `requiredPermission` | 候选权限预检 | 已定义 | Policy 中已存在 |
| `scopeDimensions` | 公司/部门/对象范围 | 已定义 | 结构化字段不存在 |

附加 Workflow 输入：

```text
workflowCode
nodeCode
```

当前结论：

```text
RRE Contract Dependency Design = COMPLETE
RRE Contract Dependency Implementation = NOT PRESENT
RRE-1 Ready = NO
RRE-1 Authorized = NO
```

---

## 17. 主要风险

| 优先级 | 风险 | 影响 | 设计控制 |
|---|---|---|---|
| P0 | Contract 与 Policy 双重维护 | 服务端事实漂移 | Policy 必须由 Contract 派生 |
| P0 | Frontend 继续定义责任 | 客户端成为责任事实源 | Frontend 只接收 Projection |
| P0 | RRE 自建 Action Map | 第三套 Registry | 只允许读取 Server Contract |
| P0 | Permission 用于选择责任人 | 授权替代责任 | 多候选不按权限消歧 |
| P0 | Responsibility 写入 role 字段 | 语义和历史损坏 | `required_role_code` 冻结 |
| P1 | 全局编码与旧键冲突 | 兼容请求失败 | Legacy Alias + Fail Closed |
| P1 | Contract 状态与部署代码不一致 | 不支持动作被开放 | 声明式随版本发布、Validator 校验 |
| P1 | 前后端 Hash 不一致 | 页面显示错误动作 | 写动作阻断并重新加载 |
| P1 | `scopeDimensions` 与授权 Scope 混淆 | 越权或误拒绝 | 业务维度与授权范围分开 |
| P1 | RETIRED 动作被重新使用 | 历史审计歧义 | 编码永久保留 |
| P2 | 兼容投影长期不退役 | 维护复杂度增加 | 设置迁移完成门和消费者清单 |

---

## 18. 后续实施影响

若未来 BAC-1 Implementation 获得授权，预计影响：

- 服务端 Contract 类型与 Registry；
- ActionPermissionPolicy 兼容投影；
- ActionPermissionValidator 的契约读取；
- 服务端 Contract 输出；
- 前端 Registry 的 Projection 适配；
- Meta Runtime/BPM 的 Action Code 引用；
- 静态门禁和契约一致性测试。

明确不应在 BAC-1 Implementation 自动包含：

- 数据库表；
- Migration；
- ApprovalTask 修改；
- Workflow Runtime 任务分派；
- RRE 实施；
- 采购审批切换；
- Shadow Mode。

---

## 19. 实施前架构决策清单

在讨论 BAC-1 Implementation 前，人工必须确认：

- [ ] 采用方案 A 受治理演进；
- [ ] BusinessActionContract 是唯一 Canonical Source；
- [ ] ActionPermissionPolicy 只作为派生兼容投影；
- [ ] V1 使用服务端版本化声明式 Registry，不建数据库表；
- [ ] `actionCode` 使用全局名称空间；
- [ ] 旧 `(moduleCode, actionId)` 使用只读 Alias 兼容；
- [ ] `requiredResponsibility` 与 `requiredPermission` 分字段；
- [ ] Frontend 只能消费 Projection；
- [ ] Workflow Node 只引用 Action Code；
- [ ] `required_role_code` 不承载 Responsibility；
- [ ] RRE-1 继续未授权；
- [ ] BAC-1 Implementation 需要新授权。

---

## 20. 本轮保护状态

本轮只新增本治理设计报告。

```text
Documentation Changed = YES
Code Changed = NO
Database Changed = NO
Migration Created = NO
API Created = NO
ActionPermissionPolicy Changed = NO
AuthorizationService Changed = NO
Workflow Runtime Changed = NO
ApprovalTask Changed = NO
Purchase Business Changed = NO
Permission Model Changed = NO
Responsibility Data Changed = NO
RRE Started = NO
Shadow Mode Started = NO
Unauthorized Business Writes = 0
```

---

## 21. 最终结论

推荐采用方案 A 的受治理演进：以现有服务端 Action Permission Registry 为迁移基础，建立完整 BusinessActionContract 作为唯一权威类型；原 ActionPermissionPolicy 和 Frontend Registry 分别降级为权限兼容投影和展示投影。

设计完成不代表实施授权。当前仓库仍未提供 `requiredResponsibility`、`objectType` 和结构化 `scopeDimensions`，因此 RRE-1 继续保持阻断。

```text
BAC-1 Architecture Design = COMPLETE
BusinessActionContract Model Design = PASS
Contract Registry Design = PASS
Recommended Option = A (GOVERNED EVOLUTION)
ActionCode Governance Design = PASS
Responsibility / Permission Mapping Design = PASS
AuthorizationService Integration Design = PASS
Workflow Compatibility Design = PASS
Frontend Projection Design = PASS
Lifecycle Design = PASS
Contract Validation Design = PASS
Compatibility / Migration Strategy Design = PASS
BAC-1 Implementation = NOT AUTHORIZED
RRE-1 Ready = NO
RRE-1 = NOT AUTHORIZED
Human Architecture Decision = WAITING
```

本轮到此停止，不进入代码、数据库、API、Workflow 或 RRE 实施。
