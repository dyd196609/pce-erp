# PCE Responsibility Resolution Engine（责任解析引擎）V1架构接入影响分析报告

报告日期：2026-08-17  
任务类型：Architecture Integration Impact Analysis（架构接入影响分析）  
评审阶段：RRE-0 Architecture Approval（架构签发阶段）  
实施状态：NOT AUTHORIZED（未授权实施）

---

## 1. 分析目的

本报告分析 Responsibility Resolution Engine（责任解析引擎）V1 接入现有 Dev-PCE 企业操作系统后，对 Business Process Management（业务流程管理）、User Interface（用户界面）、Control（控制体系）、Organization Model（组织模型）、AuthorizationService（统一授权服务）、Workflow Runtime（流程运行引擎）、Execution Engine（执行引擎）和 Digital Twin（数字孪生）的架构影响。

本轮输入为《PCE Responsibility Resolution Engine V1 架构接入评审与人工签发报告》，并结合当前仓库的正式规范、既有责任解析设计和现有实现进行事实核对。

本报告只给出影响结论和进入下一阶段的约束，不授予 RRE-1 开发权限。本轮不修改业务代码、数据库、Migration（数据库迁移）、API、Workflow、ApprovalTask（审批任务）或采购业务。

---

## 2. 总体结论

总体结论：`CONDITIONAL PASS（有条件通过）`。

责任解析引擎位于 Business Action（业务动作）与任务指派之间的方向正确，与现有组织模型和权限核心兼容；现有 Responsibility、PositionResponsibility、Position、Employee、User 和 AuthorizationService 足以支持后续“纯解析 + 隔离测试”。

但签发报告中的线性接入图需要补充两个强制条件：

1. Business Action Registry（业务动作注册中心）必须存在服务端权威契约。当前公共机器实现位于前端，不能单独作为服务端责任解析事实源；
2. AuthorizationService 不是链路中只调用一次的步骤。它至少承担“预览调用者访问控制”“候选执行人权限预检”和未来“实际执行者最终复核”三种不同职责。

在这两个条件未被签发前，只能确认架构方向，不得进入真实 API、Workflow 接入、任务创建、Shadow Mode（影子模式）或执行链。

```text
Architecture Position                         = PASS
Organization Compatibility                   = PASS
Responsibility / Permission Separation       = PASS
RRE-1 Pure Function Feasibility               = PASS WITH CONDITIONS
Server-side Action Contract Readiness         = GAP
Workflow Runtime Integration Readiness        = NOT READY
Execution Engine Integration Readiness        = NOT READY
Digital Twin Observation Readiness            = DESIGN ONLY
Implementation Authorization                  = NO
```

---

## 3. 已核对的现有事实

### 3.1 责任与组织事实

- `system.Responsibility` 已具备编码、名称、状态和有效期；
- `system.PositionResponsibility` 已表达岗位承担责任，包含 `is_primary` 和 `active`；
- `pfm.Employee.position_ref` 指向正式 Position（岗位）；
- Employee 可通过正式一对一关系关联 User（用户账户）；
- Position 和 Role（角色）是独立模型。

因此，纯解析链不需要新增 Responsibility V2、PositionResponsibility V2 或平行员工关系表。

### 3.2 权限事实

`backend/system/authorization.py` 中的 AuthorizationService 已统一接收：

- User；
- `action_code`；
- `organization_id`；
- `business_object`；
- `context`。

其输出包含 ALLOW/DENY、Decision Code（决策编码）、Scope（数据范围）、Role、Permission 和来源证据。该能力适合在唯一候选形成后进行只读权限预检，不适合用于寻找或筛选责任人。

### 3.3 Business Action 事实

当前标准把公共 Business Action Registry 的机器实现指向：

`frontend/src/meta/runtime/pceBusinessActionRegistry.js`

该注册表已经声明 `actionCode`、`moduleCode`、`requiredPermission`、状态、角色展示信息和服务端校验器，但当前没有正式 `requiredResponsibility` 字段，而且属于前端契约实现。

与此同时，服务端 `backend/workflow_runtime/action_permissions.py` 维护独立 Policy（策略）集合并由 ActionPermissionValidator（动作权限校验器）读取服务端对象、状态、组织和授权事实。

影响：当前存在“前端动作展示契约 + 服务端动作权限策略”两个实现面。RRE 不得从前端模块导入或信任责任映射，也不得再建立第三套独立动作注册表。

### 3.4 Workflow Runtime 事实

现有 ApprovalTask 使用 `required_role_code` 表达节点资格，未记录 Responsibility、Position、Employee 或解析 Evidence（解析证据）。

影响：

- RRE-1 纯解析不受阻；
- Workflow Runtime 不能在 RRE-1 直接消费解析结果；
- 不得把 Responsibility Code 填入 `required_role_code`；
- 未来任务持久化需要独立 Schema 和 Migration 评审。

### 3.5 Digital Twin 事实

当前 Digital Twin 能力主要位于前端 Meta/Platform Runtime：

- `enterpriseDigitalTwinEngine.js` 根据传入页面上下文进行只读模拟；
- `digitalTwinV20.js` 使用内存 Map 保存 Twin State（孪生状态）。

它们不是服务端组织或责任事实源，不能参与责任解析、候选筛选或权限裁决。

---

## 4. 修订后的接入位置

签发报告给出的主方向成立，但正式接入必须区分“动作发起人”“责任候选人”和“最终执行人”。

### 4.1 只读预览链

```text
Preview Caller（预览调用者）
  ↓ AuthorizationService：验证是否允许查看预览
Server Business Action Contract（服务端业务动作契约）
  ↓ requiredResponsibility + requiredPermission
Server-loaded Business Object Context（服务端读取业务对象上下文）
  ↓
Responsibility Resolution Engine
  ↓ Responsibility → PositionResponsibility → Position → Employee → User
Unique Candidate（唯一候选人）
  ↓ AuthorizationService：候选人权限预检
Read-only Result + Evidence（只读结果与解析证据）
```

### 4.2 未来执行链

```text
User Intent（用户意图）
  ↓
ActionPermissionValidator：发起人、动作、对象、状态、范围校验
  ↓
Responsibility Resolution Engine：解析谁应该负责
  ↓
AuthorizationService：候选执行人权限预检
  ↓ 唯一候选 + ALLOW + 独立实施授权
Workflow Runtime：创建或分派任务
  ↓
Actual Actor（实际执行者）
  ↓ AuthorizationService：执行时重新校验
Domain Guard（领域守卫）
  ↓
Execution Engine / Persistence（执行引擎/持久化）
```

这意味着责任解析引擎不是 ActionPermissionValidator、AuthorizationService、Workflow Runtime 或 Execution Engine 的替代品，而是任务指派之前新增的一层确定性领域解析能力。

---

## 5. 分模块接入影响

| 模块 | RRE-0/RRE-1 影响 | 未来接入影响 | 当前结论 |
|---|---|---|---|
| BPM（业务流程管理） | 无运行变化 | 节点由固定角色逐步迁移为 Required Responsibility（所需责任） | 兼容，暂不接入 |
| UI（用户界面） | 无页面变化 | 只允许展示服务端预览结果、状态和 Evidence | 不得前端解析 |
| Control（控制体系） | 增加零写入与边界验收要求 | 可观察未解析、多人、无人和权限拒绝 | 只观察，不自动修复 |
| Organization Model（组织模型） | 只读复用现有正式关系 | 组织数据质量直接决定解析结果 | 无 Schema 需求 |
| AuthorizationService（统一授权服务） | 作为候选权限预检依赖 | 执行时仍是最终裁决者 | 不修改核心逻辑 |
| ActionPermissionValidator（动作权限校验器） | RRE-1 不修改 | 保留发起动作的状态、对象、范围与权限 Guard | 不可被 RRE 替代 |
| Workflow Runtime（流程运行引擎） | 无影响 | 未来消费唯一且允许的解析结果 | 当前未准备好 |
| ApprovalTask（审批任务） | 不创建、不修改 | 未来需最小证据字段或受治理关联 | 需独立授权 |
| Execution Engine（执行引擎） | 无影响 | 只消费已授权任务，不直接调用 RRE 决定执行 | 禁止提前接入 |
| Digital Twin（数字孪生） | 无影响 | 可消费只读摘要观察组织责任风险 | 不得成为事实源 |
| AI Evolution（AI 自进化） | 仅分析 | 可推荐配置、解释冲突 | 不得自动采用 |

---

## 6. BPM 与 Workflow 影响

### 6.1 BPM 定义层

未来审批节点应声明：

```text
businessActionCode
requiredResponsibility
requiredPermission
workflowCode
nodeCode
responsibilityType
scopeDimensions
```

其中 `requiredResponsibility` 和 `requiredPermission` 必须保持独立。

BPM Designer（流程设计器）未来只能选择已有 ACTIVE Responsibility，不能：

- 输入员工姓名作为审批人；
- 通过岗位名称生成责任；
- 通过 Role 反推责任；
- 保存前端临时人员列表；
- 直接创建 ApprovalTask。

RRE-1 不修改 BPM Designer，也不新增字段到现有生产流程定义。

### 6.2 Workflow Runtime

Workflow Runtime 未来的职责是消费已完成的解析结果，而不是自己读取岗位名称或选择员工。

必须保持：

```text
RRE 解决：谁应该负责
AuthorizationService 解决：候选人是否允许
Workflow Runtime 解决：何时创建和推进任务
Execution Engine 解决：已授权动作如何执行
```

现有 `required_role_code` 必须保留为 Legacy Compatibility（历史兼容），不能被重命名或语义复用为责任编码。

---

## 7. Business Action Registry 接入影响

### 7.1 必需扩展

未来服务端动作契约至少需要：

```json
{
  "actionCode": "procurement.purchase_request.approve",
  "requiredPermission": "procurement.purchase_request.approve",
  "requiredResponsibility": "PURCHASE_REQUEST_APPROVAL",
  "objectType": "purchase_request",
  "scopeDimensions": ["COMPANY", "DEPARTMENT"],
  "workflowCode": "PROCUREMENT_PURCHASE_REQUEST",
  "nodeCode": "PURCHASE_APPROVAL"
}
```

### 7.2 唯一事实要求

需要在 RRE-1 开始前签发以下选择之一：

1. 把服务端 Action Policy 提升为动作执行契约的权威来源，并让前端注册表从服务端契约生成或校验；或
2. 建立单一共享、可由前后端生成的静态契约源。

禁止：

- RRE 直接导入前端 JavaScript 注册表；
- 页面传入 `requiredResponsibility` 并被服务端信任；
- RRE 内维护独立 Python 字典形成第三套 Registry；
- Business Action 自动创建 Responsibility。

### 7.3 RRE-1 的临时边界

若 RRE-1 仅开发纯函数，可通过显式 Injected Contract（注入契约）作为测试输入，不接生产 Registry、不开放 API、不形成正式动作映射。该做法只用于隔离测试，不能进入 RRE-2。

---

## 8. Organization Model 接入影响

纯解析依赖以下正式事实：

```text
system.Responsibility
system.PositionResponsibility
system.Position
pfm.Employee.position_ref
pfm.Employee.user
system.User
```

过滤规则必须统一：

- Responsibility 为 ACTIVE 且处于有效期；
- PositionResponsibility 为 active；
- V1 默认只把 `is_primary=true` 作为主责任候选；
- Position 为有效状态并属于业务对象 Company；
- Employee 为 active，正式 position_ref 与候选岗位一致；
- User 存在且有效；
- Department Scope 只能来自服务端业务对象和正式组织关系。

数据缺口必须产生明确结果：

| 缺口 | 结果 |
|---|---|
| 动作未配置责任 | `ACTION_RESPONSIBILITY_NOT_CONFIGURED` |
| 责任无有效岗位 | `RESPONSIBILITY_UNRESOLVED` |
| 多岗位或多员工 | `MULTIPLE_CANDIDATES` |
| 岗位无有效员工 | `NO_ACTIVE_EMPLOYEE` |
| 员工无有效账户 | `NO_EXECUTION_IDENTITY` |

不得使用 EmployeeReportingRelation（员工汇报关系）作为缺口兜底。直属主管和职能主管不是默认责任人。

---

## 9. AuthorizationService 接入影响

### 9.1 三次不同授权语义

| 时点 | 被校验身份 | 目的 |
|---|---|---|
| 预览入口 | 当前调用者 | 是否允许查看责任解析信息 |
| 责任解析后 | 唯一候选 User | 是否具备目标 Business Action 的 Permission 与 Scope |
| 未来实际执行 | 实际登录执行者 | 对当前对象、状态、版本和范围进行最终复核 |

候选预检 ALLOW 不是执行授权凭证，不能被 Workflow 或 Execution 缓存后长期复用。

### 9.2 多候选规则

存在多个候选时，不调用权限结果进行消歧。即使只有一个候选获得 ALLOW，解析结果仍然是 `MULTIPLE_CANDIDATES`。

### 9.3 核心逻辑影响

RRE-1 应以依赖接口调用现有 AuthorizationService，不修改其 Role、Permission、Scope 或 superuser 规则。若需要批量预检或专用 Evidence 格式，应先设计 Adapter（适配器），不得复制授权算法。

---

## 10. UI 与 Control 影响

### 10.1 UI

RRE-1 没有页面影响。未来只读预览页面必须：

- 读取同一服务端解析结果；
- 展示 Responsibility、Position、Employee、解析状态和 Evidence；
- 显示“只读预览，不创建任务，不改变状态”；
- 刷新后重新读取服务端事实；
- 不提供“自动采用”“创建审批任务”“替换审批人”按钮；
- 不在浏览器重算候选人或权限。

### 10.2 Control

Control Plane（控制平面）未来可以统计：

- 未配置责任动作数；
- 无责任岗位数；
- 多候选冲突数；
- 无有效员工数；
- 有责任但权限拒绝数；
- 解析延迟和服务端读取失败数。

这些指标只用于观察和治理提示，不得触发自动组织调整、责任分配、授权或流程执行。

---

## 11. Execution Engine 影响

RRE-0 和 RRE-1 对 Execution Engine 为零影响。

未来正式执行必须满足：

```text
Resolution Status = RESOLVED
Candidate Count = 1
Authorization Precheck = ALLOW
Workflow Task = formally created under separate authorization
Actual Actor Authorization = ALLOW at execution time
Domain Guard = PASS
```

Execution Engine 不得：

- 直接从 Responsibility 生成执行；
- 把预检 ALLOW 当成永久授权；
- 在多人时选择一人；
- 在无人时找管理员或主管；
- 因 Digital Twin 或 AI 建议自动执行。

---

## 12. Digital Twin 影响

责任解析结果未来可以成为 Digital Twin 的 Observation（观察数据），推荐只提供去敏摘要：

```text
actionCode
objectType
companyId / departmentId
requiredResponsibilityCode
resolutionStatus
positionCandidateCount
employeeCandidateCount
authorizationPrecheckStatus
resolvedAt
evidenceHash（若未来持久化策略获批）
```

Digital Twin 可以模拟“组织调整后冲突是否减少”，但输出只能是 Simulation（模拟）或 Advisory（建议），不能回写：

- Responsibility；
- PositionResponsibility；
- Employee；
- Role/Permission；
- Workflow；
- ApprovalTask。

当前前端内存 Twin 不是权威事实层。RRE 不得读取 Twin State 作为候选输入，Twin 也不得把页面 Rows 或缓存结果冒充服务端 Evidence。

---

## 13. 非功能影响

### 13.1 一致性

单次解析必须固定一个服务端 `as_of`，并在同一数据库读一致性窗口内完成。责任、岗位和员工事实发生并发变化时，返回冲突或重新解析，不能组合不同时点事实。

### 13.2 性能

RRE-1 应避免逐候选 N+1 Query（逐项查询）。推荐以受控 QuerySet 一次读取责任、岗位关系、岗位、员工和账户。性能优化不得改变多人结果。

### 13.3 安全与隐私

- 先验证预览调用者，后返回员工候选；
- 跨公司对象统一拒绝，避免通过 404/详情差异探测人员；
- 普通业务用户不返回无关候选员工或完整账户信息；
- Evidence 中 User 信息按最小必要原则输出。

### 13.4 可观测性

RRE-1 单元测试可以记录技术诊断，但不得形成业务审计。未来 API 日志必须区分 Technical Trace（技术轨迹）与 Business Evidence（业务证据）。RRE-0/RRE-1 均不新增证据表。

### 13.5 失败策略

所有读取失败、配置缺失和冲突均 Fail Closed（失败关闭）。不得回退旧审批人、固定角色、管理员或前端缓存。

---

## 14. 主要风险清单

| 优先级 | 风险 | 影响 | 处置 |
|---|---|---|---|
| P0 | 仅用前端 Registry 提供责任映射 | 服务端事实可被客户端替代 | 先签发服务端动作契约所有权 |
| P0 | RRE 复制一套 Action Registry | 出现第三事实源 | 使用共享生成源或既有服务端 Policy |
| P0 | 用 Permission 消歧候选 | “可以做”替代“应该做” | 多候选立即返回冲突 |
| P0 | 预检 ALLOW 直接触发 Workflow | 越过任务与执行授权 | RRE-1 禁止 Workflow 依赖 |
| P0 | 把责任编码写入 required_role_code | 破坏 Role/Responsibility 语义 | 历史字段只做兼容 |
| P0 | Digital Twin/AI 回写责任 | 自动改变企业事实 | 强制 Advisory Only |
| P1 | Employee 正式岗位缺失 | 无法解析实际人员 | 返回 NO_ACTIVE_EMPLOYEE/UNRESOLVED |
| P1 | 多岗位或一岗多人 | 无唯一负责人 | 返回 MULTIPLE_CANDIDATES |
| P1 | 候选无 User 或账号停用 | 无数字执行身份 | 返回明确身份错误 |
| P1 | 组织事实并发变化 | Evidence 与任务不一致 | 固定 as_of；未来任务创建时重算 |
| P1 | RRE 查询泄露其他公司员工 | 人员隐私与越权 | 调用者授权、服务端 Scope、最小输出 |
| P2 | N+1 查询 | 预览和流程延迟 | 预取正式关系，不改变解析规则 |

---

## 15. RRE-1 进入条件

只有人工签发以下条件后，才建议授权 RRE-1 Pure Resolution Engine Implementation（纯解析引擎实施）：

1. 确认 RRE 为服务端 Domain Query/Resolution Service（领域查询/解析服务），不是前端 Runtime；
2. 确认 RRE-1 只实现纯解析函数、状态模型和隔离测试；
3. 确认 Business Action 到 Responsibility 的映射在 RRE-1 仅通过测试注入，或已有单一服务端权威契约；
4. 确认不新增数据库表、不创建 Migration、不创建 API；
5. 确认不修改 Workflow Runtime、ApprovalTask、Execution Engine 和采购流程；
6. 确认不启动 Shadow Mode；
7. 确认不修改 AuthorizationService 核心逻辑；
8. 确认多人、无人、无权限均失败关闭；
9. 确认测试数据只在隔离测试数据库产生；
10. 确认 RRE-1 完成后仍需独立 RRE-2 API 授权。

### RRE-1 建议交付物

- 输入与输出 Data Transfer Object（数据传输对象）；
- 解析状态枚举；
- 纯解析服务；
- 可替换的 Repository（仓储）读取接口；
- 可替换的 Authorization Precheck Port（授权预检端口）；
- Evidence Builder（证据构建器），仅内存返回；
- RRE-T01～RRE-T16 隔离测试；
- 零业务写入证明。

---

## 16. 人工签发建议

建议对原签发栏采用以下意见：

```text
签发意见：

Responsibility Resolution Engine V1 架构方向有条件通过。

允许后续单独授权 RRE-1 纯解析函数与隔离测试；
在服务端 Business Action 责任映射契约完成签发前，
不得开放真实 API、接入 Workflow Runtime、创建 ApprovalTask、
启动 Shadow Mode 或进入 Execution Engine。

AuthorizationService 必须分别承担预览访问控制、
候选权限预检和实际执行时最终复核；
Permission 不得参与责任候选消歧。
```

本影响分析不能代替架构负责人签名，也不自动把 `Human Architecture Approval` 从 PENDING 改为 PASS。

---

## 17. 本轮保护声明

```text
Code Changed                         = NO
Database Changed                     = NO
Migration Created                    = NO
API Created                          = NO
Responsibility Data Changed          = NO
PositionResponsibility Changed       = NO
AuthorizationService Changed         = NO
Workflow Runtime Changed             = NO
ApprovalTask Changed                 = NO
Execution Engine Changed             = NO
Purchase Business Changed            = NO
Shadow Mode Started                  = NO
Unauthorized Business Writes         = 0
```

本轮唯一新增内容为本架构接入影响分析报告。

---

## 18. 最终状态

```text
Architecture Integration Impact Analysis = COMPLETE
Architecture Direction                   = PASS
Integration Readiness                    = CONDITIONAL PASS
Human Architecture Approval              = PENDING
RRE-1 Development Authorization          = NO
RRE-1 Development                        = NOT STARTED
Workflow / Execution Integration         = NOT AUTHORIZED
```

本轮到此停止，等待人工架构签发。
