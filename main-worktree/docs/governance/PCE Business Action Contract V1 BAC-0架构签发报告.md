# PCE Business Action Contract V1 BAC-0架构签发报告

报告日期：2026-08-17  
文档类型：Architecture Approval & Baseline Record（架构签发与基线记录）  
评审阶段：BAC-0 Architecture Approval（BAC-0 架构签发）  
Human Architecture Approval（人工架构批准）：APPROVED（已批准）  
Architecture Baseline Status（架构基线状态）：ESTABLISHED（已建立）  
Implementation Authorization（实施授权）：NO（未授权）

---

## 1. 签发目的

本报告正式确认 Business Action Contract（业务动作契约）可以作为 Dev-PCE Enterprise OS（企业操作系统）的基础语义层，并冻结后续 Business Action（业务动作）相关设计和开发必须遵守的架构规则。

本次批准代表架构规则批准，不代表代码实施批准，不授权 BAC-1 Implementation（BAC-1 实施）、Responsibility Resolution Engine RRE-1（责任解析引擎第一实施阶段）、API（接口）、Migration（数据库迁移）、Workflow Runtime（流程运行引擎）改造或采购流程切换。

---

## 2. 评审依据

本报告基于：

1. 《PCE Responsibility Resolution Engine V1只读解析验证设计报告》；
2. 《PCE Responsibility Resolution Engine V1架构接入影响分析报告》；
3. 《PCE Business Action Contract V1设计与治理分析报告》；
4. `D:\Dev-PCE\Source` 真实仓库只读检查结果；
5. BAC-0 人工架构确认指令。

BAC-0 前置结论：

```text
Business Action Contract Design = PASS
Current Business Action Contract Completeness = FAIL
Server-side Single Source of Truth = NOT ESTABLISHED
RRE-1 Ready = NO
Implementation Authorized = NO
```

BAC-0 签发只冻结目标架构。当前实现缺口继续保留为 BAC-1 的设计对象，不能因本报告已批准而被解释为已经完成代码实施。

---

## 3. 已核对的仓库事实

| 实际文件路径 | 文件作用 | 当前判断 |
|---|---|---|
| `frontend/src/meta/runtime/pceBusinessActionRegistry.js` | 前端动作注册、显示、状态过滤、路由和权限编码投影 | 是展示基础，不是服务端唯一事实源 |
| `frontend/src/meta/components/PceBusinessActionBar.vue` | 根据前端 Registry 渲染按钮并发起服务端动作校验 | 页面只可提交动作意图 |
| `frontend/src/meta/core/pageRenderer.js` | Meta Runtime 的 Workflow Action 展示与执行路径 | 正式动作必须统一引用服务端 Contract |
| `frontend/src/meta/bpm/bpmDesignerEngine.js` | BPM 状态和迁移图设计 | 只能引用已有 Action Contract |
| `backend/workflow_runtime/action_permissions.py` | 服务端动作权限 Policy、对象事实和状态权限校验 | 是未来 Server Contract 的现有基础 |
| `backend/workflow_runtime/views.py` | 服务端动作权限矩阵和动作校验接口 | 当前输出权限契约，不是完整 Action Contract |
| `backend/workflow_runtime/models.py` | WorkflowInstance、ApprovalTask、ApprovalDecision | `required_role_code` 保持 Role 语义 |
| `backend/system/authorization.py` | AuthorizationService 统一授权裁决 | 只负责“是否允许执行” |
| `backend/system/models.py` | Responsibility、PositionResponsibility、Role、Permission | 责任与授权模型保持分离 |
| `backend/pfm/models.py` | Employee、正式 Position 和 User 关系 | 为未来责任解析提供正式人员关系 |

全仓重点扫描结果：

```text
Search Scope = frontend/src/meta + backend
Search Field = requiredResponsibility
Result = NO MATCH
```

结论：当前仓库尚未实施完整 Server Business Action Contract（服务端业务动作契约），尤其尚未建立 `requiredResponsibility` 字段。因此，本报告的 `APPROVED` 只表示架构语义批准。

---

## 4. 当前关键原文证据

### 4.1 Frontend Registry（前端注册表）

来源：`frontend/src/meta/runtime/pceBusinessActionRegistry.js:790`

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
      displayName: item.actionName,
      allowedStatus: [...item.allowedStatuses],
      singleOrBatch: item.scope,
      organizationScope: 'legal_entity',
      serverValidator: 'workflow_runtime.ActionPermissionValidator',
    })
  })),
```

判断：当前前端已经存在 `actionCode`、`moduleCode`、`requiredPermission` 和状态展示信息，但不存在 `requiredResponsibility`、`objectType`、`workflowCode`、`nodeCode` 和结构化 `scopeDimensions`。

### 4.2 ActionPermissionPolicy（动作权限策略）

来源：`backend/workflow_runtime/action_permissions.py:421`

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

判断：现有服务端 Policy 是 Server Business Action Contract 的实现基础，但仍是权限策略，不是完整动作契约。

### 4.3 服务端未注册动作拒绝

来源：`backend/workflow_runtime/action_permissions.py:742`

```python
policy = POLICIES.get((module_code, action_code))
if not policy:
    return self._decision(
        None, False, "action_not_registered", "业务动作未注册。"
    )
```

判断：服务端已具备“未注册动作必须拒绝”的正确基础。BAC-1 应优先演进这一现有服务端能力，禁止为 RRE 建立第三套动作字典。

### 4.4 AuthorizationService（统一授权服务）

来源：`backend/system/authorization.py:43`、`backend/system/authorization.py:108`

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
    return cls._deny(
        decision,
        "PERMISSION_DENIED",
        "当前角色未获得该业务动作权限。",
    )
```

判断：未来必须由 Business Action Contract 先解析 `requiredPermission`，再调用 AuthorizationService。AuthorizationService 不负责寻找责任人。

### 4.5 ApprovalTask（审批任务）

来源：`backend/workflow_runtime/models.py:122`

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

判断：`required_role_code` 继续表达 Role Code（角色编码），禁止写入 Responsibility Code（责任编码）。

---

## 5. Business Action Contract 架构定位

正式架构：

```text
Server Business Action Contract
（服务端业务动作契约）
        ↓
Frontend Projection
（前端展示投影）
        ↓
User Action
（用户操作）
        ↓
Server Revalidation
（服务端重新验证）
        ↓
Domain / Workflow / Execution
（领域/流程/执行）
```

各层唯一职责：

| 层 | 唯一职责 | 禁止事项 |
|---|---|---|
| Server Business Action Contract | 定义动作、对象、责任、权限、流程和范围 | 由页面覆盖 |
| Frontend Projection | 显示、分组、按钮、图标和禁用原因 | 定义责任或审批人 |
| User Action | 提交动作申请 | 声明自己已授权 |
| Server Revalidation | 重读动作、对象、状态、权限和范围 | 信任页面缓存 |
| Responsibility Resolution Engine | 解析谁应该负责 | 授权或随机选人 |
| AuthorizationService | 判断当前执行是否允许 | 寻找责任人 |
| Workflow Runtime | 消费已验证动作和解析结果 | 自行创建动作语义 |
| Execution Engine | 执行通过 Guard 的正式动作 | 根据责任直接执行 |

签发结论：

```text
Business Action Contract Architecture = PASS
```

---

## 6. 唯一事实来源

BAC-0 正式确认：

```text
Server Business Action Contract Registry
（服务端业务动作契约注册中心）
=
Business Action（业务动作）的唯一运行事实来源
```

以下消费者只能读取同一服务端契约：

- ActionPermissionValidator（动作权限校验器）；
- Responsibility Resolution Engine（责任解析引擎）；
- Workflow Runtime（流程运行引擎）；
- AuthorizationService Adapter（授权服务适配层）；
- Frontend Projection（前端投影）；
- Control/Observability（控制与可观测性）；
- Digital Twin Observation（数字孪生观察）；
- Acceptance Tests（验收测试）。

必须区分：

```text
Server Contract Authority Design = PASS
Server Contract Authority Implementation = NOT ESTABLISHED
```

---

## 7. 字段模型冻结

BAC-0 冻结以下标准字段：

| 字段 | 中文说明 | 冻结规则 |
|---|---|---|
| `contractVersion` | 契约版本 | 必须存在 |
| `actionCode` | 动作编码 | 全局唯一、稳定、不绑定页面 |
| `moduleCode` | 模块编码 | 指明所属业务模块 |
| `displayName` | 显示名称 | 服务端默认业务名称 |
| `objectType` | 业务对象类型 | 服务端正式对象类型 |
| `requiredResponsibility` | 所需责任编码 | 责任型动作引用已有 Responsibility |
| `requiredPermission` | 所需权限编码 | AuthorizationService 的权限输入 |
| `workflowCode` | 流程编码 | 流程型动作必须提供 |
| `nodeCode` | 节点编码 | 节点型动作必须提供 |
| `scopeDimensions` | 范围维度 | 服务端组织范围解析维度 |
| `allowedStatuses` | 允许状态 | 来自服务端 Domain State Contract |
| `actionScope` | 动作范围 | VIEW、SINGLE、BATCH、SYSTEM 等 |
| `serverValidator` | 服务端校验器 | 正式 Guard/Validator |
| `status` | 状态 | DRAFT、ACTIVE、SUSPENDED、RETIRED |

非责任型或非 Workflow 动作的条件字段必须显式为 `null`，不得通过字段缺失表达“不适用”。

---

## 8. Responsibility 与 Permission 边界

Responsibility（责任）回答：

> 谁应该承担这个业务动作责任？

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

Permission（权限）回答：

> 当前用户是否允许执行这个动作？

```text
User
↓
Role
↓
RolePermission
↓
Permission
↓
AuthorizationService
```

强制禁止：

```text
Permission → 寻找责任人
Role = Responsibility
拥有权限的人 = 责任人
Position = Approver
```

即使多个责任候选中只有一人拥有 Permission，解析结果仍必须保持 `MULTIPLE_CANDIDATES（多个候选人）`，不得通过权限消歧。

---

## 9. Workflow Runtime 边界

当前语义冻结：

```text
ApprovalTask.required_role_code = Role Code
```

禁止：

```text
ApprovalTask.required_role_code = Responsibility Code
```

未来关系：

```text
Workflow Node
↓ actionCode
Server Business Action Contract
↓ requiredResponsibility
Responsibility Resolution Engine
↓ Employee
AuthorizationService
↓ ALLOW / DENY
Workflow Runtime
```

本报告不授权修改 Workflow Runtime、ApprovalTask 或 `required_role_code`。

---

## 10. Architecture Baseline Rules（架构基线规则）

本章节自本报告归档之日起成为 Dev-PCE 后续 Business Action 相关设计、开发、评审和验收的强制架构基线。

1. Server Business Action Contract（服务端业务动作契约）是 Business Action（业务动作）的唯一事实来源。
2. Frontend Registry（前端注册表）只能展示和适配，不能定义企业动作事实。
3. Permission（权限）不能寻找责任人。
4. Responsibility（责任）不能由 Role（角色）替代。
5. Workflow Runtime（流程运行引擎）不能自行创建 Business Action。
6. BPM Designer（流程设计器）只能引用已有 Action Contract（动作契约）。
7. Digital Twin（数字孪生）只能读取观察数据，不能成为动作、责任或授权事实源。
8. AI（人工智能）不能自动修改企业责任事实、动作契约、岗位责任或权限。
9. 页面按钮只能提交 User Intent（用户意图），不能提交并决定责任人或授权结论。
10. ActionPermissionValidator 必须继续从服务端重新读取动作、对象、状态和组织事实。
11. AuthorizationService 只负责执行许可裁决，不负责责任发现。
12. Responsibility Code 禁止写入 `required_role_code`。
13. RRE 禁止建立独立 Action Dictionary（动作字典）或信任前端责任编码。
14. Contract 不得根据 Action Code、岗位名称、Role 或员工姓名自动创建 Responsibility。
15. 任何违反本基线的实现必须在代码评审、静态门禁或人工验收阶段阻断。

---

## 11. RRE 接入前置条件

RRE-1 前必须存在并通过独立验收的 Server Business Action Contract，至少能够提供：

```text
actionCode
objectType
requiredResponsibility
requiredPermission
scopeDimensions
```

Workflow Action 还必须提供：

```text
workflowCode
nodeCode
```

当前事实：

```text
requiredResponsibility = NOT PRESENT
Server-side Full Business Action Contract = NOT PRESENT
RRE Dependency Ready = NO
RRE-1 Authorization = NO
```

---

## 12. BAC-0 签发矩阵

| 评审项 | 结论 | 说明 |
|---|---|---|
| Business Action Contract 架构定位 | PASS | 企业 OS 基础语义层 |
| 服务端唯一事实源规则 | PASS | Server Contract Registry 为唯一权威 |
| 当前服务端完整契约 | FAIL | 尚未实施 `requiredResponsibility` 等字段 |
| Frontend Projection 边界 | PASS | 前端仅展示和适配 |
| 字段模型 | PASS | 14 项字段完成冻结 |
| Responsibility 边界 | PASS | 解决谁应该负责 |
| Permission 边界 | PASS | 解决谁被允许执行 |
| Workflow Compatibility | PASS | `required_role_code` 保持 Role 语义 |
| AuthorizationService Compatibility | PASS | 继续作为统一授权裁决者 |
| Digital Twin Compatibility | PASS | 仅允许只读观察 |
| RRE 依赖准备 | NO | 完整 Server Contract 尚未实施 |
| BAC-1 实施授权 | NO | 需要新的实施授权 |
| RRE-1 实施授权 | NO | 等待 Contract 实施和验收 |

---

## 13. 人工架构批准记录

```text
Human Architecture Approval = APPROVED
Approval Scope = ARCHITECTURE RULES ONLY
Code Implementation Approval = NO
Database Implementation Approval = NO
API Implementation Approval = NO
Workflow Integration Approval = NO
RRE-1 Approval = NO
```

批准解释：

- Business Action Contract 架构方向正式通过；
- Server Business Action Contract Registry 的唯一事实源地位正式冻结；
- Architecture Baseline Rules 正式生效；
- 不代表当前服务端完整契约已经存在；
- 不代表 BAC-1 或 RRE-1 获得实施授权。

---

## 14. 当前阶段状态

```text
BAC-0 = BASELINED
BAC-1 = DESIGN ONLY
BAC-1 IMPLEMENTATION = NOT AUTHORIZED
RRE-1 = NOT AUTHORIZED
```

下一允许阶段：

```text
BAC-1 Architecture / Contract Definition Design Only
（BAC-1 架构与契约定义设计，仅设计）
```

进入任何实施活动前，必须获得新的明确实施授权。

---

## 15. 本轮保护状态

本轮只新增和归档治理文档，不修改业务代码或运行系统。

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
Unauthorized Business Writes = 0
```

---

## 16. 最终状态

```text
BAC-0 Architecture Review = COMPLETE
Human Architecture Approval = APPROVED
Architecture Baseline Status = ESTABLISHED
Business Action Contract Architecture = PASS
Server Contract Authority = PASS
Server Contract Authority Implementation = NOT ESTABLISHED
Responsibility Boundary = PASS
Permission Boundary = PASS
Workflow Compatibility = PASS
RRE Dependency Ready = NO
Implementation Authorized = NO
```

本报告自归档之日起成为 Dev-PCE Business Action 相关后续工作的正式架构基线。

