# PCE Responsibility Resolution Engine（责任解析引擎）V1——只读解析验证设计报告

报告日期：2026-08-17  
任务类型：Architecture Design & Read-only Validation Design（架构设计与只读验证设计）  
当前状态：DESIGN COMPLETE / IMPLEMENTATION NOT AUTHORIZED（设计完成/未授权实施）

---

## 1. 设计目标

Responsibility Resolution Engine（责任解析引擎）回答：

> 对于一个业务动作，在指定业务对象、组织范围和解析时点下，当前企业中谁应该负责？

V1 第一阶段只做只读解析与 AuthorizationService（统一授权服务）预检，不执行任何业务动作。

```text
Business Action（业务动作）
  ↓ Required Responsibility（所需责任）
Responsibility（职责/责任定义）
  ↓ PositionResponsibility（岗位职责关系）
Position（岗位）
  ↓ 当前有效任职
Employee（员工）
  ↓ User（用户账户）
AuthorizationService（统一授权服务）预检
  ↓
只读解析结果与证据
```

本设计禁止：

- 修改业务代码或前端代码；
- 修改数据库或业务数据；
- 创建 Migration（数据库迁移）；
- 创建或修改 Responsibility；
- 创建解析结果表或 Evidence（解析证据）表；
- 创建或修改 ApprovalTask（审批任务）；
- 修改 Workflow Runtime（流程运行引擎）；
- 修改采购申请状态、节点或审批人；
- 通知候选员工；
- 启动 Shadow Mode（影子模式）；
- 自动选择管理员、主管或任意有权限人员；
- 自动授予 Role（角色）或 Permission（权限）。

---

## 2. 已完整读取的依据

### 2.1 Responsibility（责任）

- `docs/governance/PCE Responsibility Master Data V1设计报告.md`
- `docs/governance/PCE Responsibility Master Data V1-R1实施报告.md`
- `docs/governance/PCE Responsibility Master Data V1-R1.2整改报告.md`
- `docs/governance/PCE Responsibility Master Data V1岗位责任角色权限语义边界确认报告.md`

### 2.2 Organization（组织）

- `docs/governance/PCE企业组织运作模型V1-实施与人工验收交接报告.md`
- `docs/governance/PCE企业组织运作模型V1-正式管理员入口统一与维护闭环整改报告.md`

### 2.3 Permission（权限）

- `docs/standards/PCE-BUSINESS-ACTION-PERMISSION-V1.0.md`
- `docs/governance/PCE公共组织身份权限核心V1-最终人工验收与封板报告.md`

依据文件确认：Responsibility 的唯一事实来源是 `system.Responsibility`；岗位承担关系来自 `system.PositionResponsibility`；员工任职来自正式 Employee 与 Position 关系；Role 与 Position 分离；最终授权只能由服务端 AuthorizationService 裁决。

---

## 3. 四层语义边界

| 对象 | 回答的问题 | 在解析引擎中的职责 | 明确禁止 |
|---|---|---|---|
| Position（岗位） | 组织中有什么职位？ | 承载责任并连接当前任职员工 | 直接作为审批人或权限 |
| Responsibility（职责/责任定义） | 企业中谁应该承担什么稳定责任？ | 定义所需责任并找到承担岗位 | 自动授予角色或权限 |
| Role（角色） | 系统账户具有什么授权集合？ | 仅作为授权预检事实 | 作为责任候选或岗位替代物 |
| Permission（权限） | 账户是否具备执行能力？ | 由 AuthorizationService 在预检阶段验证 | 用来反向选择责任人 |

责任解析与权限预检必须分离：

```text
责任解析结果：谁应该负责？
授权预检结果：这个人当前是否允许执行？
```

禁止通过 Permission 筛掉无权限候选后，从剩余人员中选出“唯一责任人”。如果责任路径有多人，解析状态必须保持 `MULTIPLE_CANDIDATES（多个候选人）`，即使其中只有一人拥有权限。

---

## 4. 设计原则

### 4.1 Enterprise Operation Data Driven Principle（企业运作数据驱动原则）

代码只提供解析算法、过滤规则、错误状态和读取能力；实际责任、岗位、员工和授权关系全部来自管理员维护的正式服务端事实。

禁止写死：

- 采购经理等岗位名称；
- 张三等员工姓名；
- 采购部或公司固定 ID；
- 某角色即责任人；
- 某权限持有人即审批人；
- 找不到责任时由管理员或直属主管兜底。

### 4.2 Read-only by Construction（结构性只读）

只读解析入口只能调用查询服务和 AuthorizationService 的只读决策能力，不导入或调用：

- OrganizationOperatingService（组织运作服务）的保存动作；
- Workflow 状态转换服务；
- ApprovalTask 创建服务；
- 通知服务；
- 采购申请审批服务；
- 责任或权限维护接口。

### 4.3 Deterministic Resolution（确定性解析）

同一服务端事实、同一输入和同一解析时点必须得到相同结果。排序只用于稳定展示证据，不得作为选择候选人的规则。

### 4.4 Fail Closed（失败关闭）

缺少映射、责任无效、多人候选、无人任职、无执行账户或授权拒绝均返回明确状态，不得静默替换为旧逻辑、管理员、主管或任意有权限用户。

---

## 5. Business Action（业务动作）到责任的映射

### 5.1 映射位置

复用既有 Business Action Registry（业务动作注册中心），为动作契约增加只读元数据引用：

```json
{
  "actionCode": "procurement.purchase_request.approve",
  "requiredResponsibility": "PURCHASE_REQUEST_APPROVAL",
  "requiredPermission": "procurement.purchase_request.approve",
  "scopeDimensions": ["COMPANY", "DEPARTMENT"],
  "workflowCode": "PROCUREMENT_PURCHASE_REQUEST",
  "nodeCode": "PURCHASE_APPROVAL"
}
```

`requiredResponsibility` 与 `requiredPermission` 是两个独立字段。即使示例字符串相近，也不能合并语义。

### 5.2 映射规则

1. Business Action 必须已在正式注册中心登记；
2. 动作必须显式引用一个已存在的 Responsibility Code（责任编码）；
3. 注册动作不得自动创建、激活或修改 Responsibility；
4. 映射不得包含 Position ID、Employee ID、用户名或岗位名称；
5. 页面不得自行维护或覆盖映射；
6. 动作没有 `requiredResponsibility` 时返回 `ACTION_RESPONSIBILITY_NOT_CONFIGURED（动作未配置所需责任）`；
7. 引用的责任不存在时返回 `RESPONSIBILITY_REFERENCE_INVALID（责任引用无效）`；
8. 多席位会签必须由 Workflow 定义显式表达，不能用偶然多人候选代替。

### 5.3 不自动生成原则

正确：

```text
采购申请审批动作
需要
既有 PURCHASE_REQUEST_APPROVAL（采购申请审批责任）
```

错误：

```text
注册采购申请审批动作
自动生成 PURCHASE_REQUEST_APPROVAL
```

责任必须先作为独立企业事实存在并由管理员维护；动作契约只能引用。

---

## 6. 只读解析输入

### 6.1 最小输入

| 字段 | 必填 | 说明 |
|---|---:|---|
| `business_action_code` | 是 | 已登记的 Business Action Code（业务动作编码） |
| `object_type` | 是 | 业务对象类型，例如 `purchase_request` |
| `object_id` | 是 | 服务端业务对象稳定 ID |

### 6.2 服务端派生输入

以下字段不得信任客户端结论，必须通过 `object_type + object_id` 重新读取：

- Company（公司）；
- Department（部门）；
- 当前业务状态；
- Workflow Code（流程编码）；
- Node Code（节点编码）；
- 业务对象版本；
- 组织范围和数据范围。

### 6.3 可选控制输入

| 字段 | 规则 |
|---|---|
| `as_of` | 默认取一次服务端当前时间；仅受控测试身份可指定 |
| `include_inactive_evidence` | 默认 false；仅诊断展示，不改变候选结果 |
| `explain` | 默认 true；控制是否返回完整只读 Evidence |

客户端不得提交 `employee_id`、`position_id`、`role_code`、`permission_code` 或“预期审批人”影响解析结果。

---

## 7. 完整解析链与规则

### 7.1 Step 1：读取业务对象

服务端按 `object_type + object_id` 读取真实对象。

- 不存在：`BUSINESS_OBJECT_NOT_FOUND（业务对象不存在）`；
- 对调用者不可见：HTTP 403，不泄露对象是否存在；
- 对象类型与动作不匹配：`ACTION_OBJECT_TYPE_MISMATCH（动作与对象类型不匹配）`。

读取结果形成公司、部门、状态、流程和节点上下文。

### 7.2 Step 2：解析 Required Responsibility（所需责任）

从 Business Action Registry 获取 `requiredResponsibility`，不从按钮、页面文本、角色或 Permission 推导。

### 7.3 Step 3：读取 Responsibility（职责/责任定义）

唯一来源：

`system.Responsibility`

责任必须同时满足：

```text
status = ACTIVE
AND effective_from <= as_of
AND (effective_to IS NULL OR effective_to >= as_of)
```

不满足时返回 `RESPONSIBILITY_UNAVAILABLE（责任当前不可用）`，并在 Evidence 中说明草稿、暂停、失效、尚未生效或已过期。

### 7.4 Step 4：读取 PositionResponsibility（岗位职责关系）

只读取：

- `responsibility_id` 精确匹配；
- `active=true`；
- V1 默认 `is_primary=true`，即 `PRIMARY`（主责）；
- Position 所属公司与业务对象公司一致；
- 若动作契约声明 Department 维度，则岗位部门必须符合服务端对象部门范围；
- Position 当前有效。

`SUPPORTING`（协助）关系可以作为诊断证据返回，但不得自动升级为主责任候选。

结果：

- 零个有效岗位：`RESPONSIBILITY_UNRESOLVED（责任未解析）`；
- 多个有效岗位：`MULTIPLE_CANDIDATES（多个候选人）`；
- 唯一岗位：继续解析 Employee。

Priority（优先级）、ID、创建时间、编码或名称排序都不能用于自动选岗。

### 7.5 Step 5：从 Position 找 Employee（员工）

员工必须满足：

- 正式 `position_ref` 指向候选 Position；
- 正式部门与岗位组织关系一致；
- 员工状态为有效在职状态；
- 员工所属公司与业务对象公司一致；
- 解析时点处于适用任职事实范围。

结果：

- 无有效员工：`NO_ACTIVE_EMPLOYEE（无有效员工）`；
- 多个有效员工：`MULTIPLE_CANDIDATES`；
- 唯一员工：继续读取 User。

禁止按员工 ID、姓名、入职日期、创建时间、是否有权限或是否为主管自动选人。

### 7.6 Step 6：读取 User（用户账户）

唯一 Employee 必须关联一个有效 User。

- 未关联账户：`NO_EXECUTION_IDENTITY（无执行身份）`；
- 账户停用：`EXECUTION_IDENTITY_INACTIVE（执行身份已停用）`；
- 唯一有效账户：责任解析状态可记为 `RESOLVED（解析成功）`。

User 只提供数字执行身份，不改变“谁应该负责”的解析结论。

### 7.7 Step 7：AuthorizationService 只读预检

仅在解析得到唯一 Employee/User 时执行：

```text
AuthorizationService.decide(
  user = resolved_user,
  action_code = requiredPermission,
  organization_id = object.company,
  business_object = server_loaded_object_context
)
```

预检结果：

- `ALLOW`：`authorization_precheck_status=ALLOW`；
- `DENY`：`authorization_precheck_status=DENY`，业务语义为 `RESPONSIBILITY_FOUND_PERMISSION_DENIED（责任存在但权限不足）`。

预检不执行业务动作，不写授权，不创建任务，不修改对象状态。

---

## 8. 多人冲突与禁止选择规则

### 8.1 冲突矩阵

| 场景 | 解析状态 | 是否预检权限 |
|---|---|---:|
| 唯一有效主责岗位、唯一有效员工 | `RESOLVED` | 是 |
| 多个有效主责岗位 | `MULTIPLE_CANDIDATES` | 否；可诊断展示，但不得用于筛选 |
| 唯一岗位、多名有效员工 | `MULTIPLE_CANDIDATES` | 否；可诊断展示，但不得用于筛选 |
| 无有效主责岗位 | `RESPONSIBILITY_UNRESOLVED` | 否 |
| 有岗位但无有效员工 | `NO_ACTIVE_EMPLOYEE` | 否 |
| 唯一员工但无有效账户 | `NO_EXECUTION_IDENTITY` | 否 |
| 唯一员工且授权拒绝 | `RESOLVED` + `DENY` | 已完成只读预检 |

### 8.2 绝对禁止的消歧规则

禁止：

- 随机选择；
- 按 Position、Employee 或 User ID；
- 按创建时间或最后修改时间；
- 按姓名、编码或岗位名称排序后取第一名；
- 按 Priority 自动选择；
- 选择唯一拥有 Permission 的候选人；
- 找管理员；
- 找直属主管或职能主管；
- 找任意拥有相关 Role 的用户；
- 用旧审批人填补新责任缺口。

多人问题必须通过正式组织范围、岗位责任配置、任职关系或显式会签流程解决。

---

## 9. 输出设计

### 9.1 顶层结果

建议对象：`ResponsibilityResolutionPreviewResult（责任解析预览结果）`

| 字段 | 说明 |
|---|---|
| `contract_version` | `PCE-RESPONSIBILITY-RESOLUTION-PREVIEW-V1` |
| `read_only` | 固定 `true` |
| `business_action` | 动作编码与中文名称 |
| `business_object` | 类型、ID、版本、公司、部门、状态快照 |
| `required_responsibility` | 所需责任编码和名称 |
| `required_permission` | 所需权限编码；只用于预检 |
| `position_candidates` | 按正式路径得到的岗位候选及排除原因 |
| `employee_candidates` | 员工候选及有效性证据 |
| `resolved_employee` | 仅唯一解析成功时存在 |
| `resolution_status` | 责任解析状态 |
| `authorization_precheck` | 独立的 ALLOW/DENY/NOT_RUN |
| `evidence` | 完整只读解析证据 |
| `resolved_at` | 单次服务端解析时点 |
| `business_write_count` | 固定并验证为 0 |

### 9.2 状态分离

不得只返回一个含糊的 `success`。至少分开：

```text
resolution_status
authorization_precheck.status
```

示例：责任找到但权限不足：

```json
{
  "resolution_status": "RESOLVED",
  "authorization_precheck": {
    "status": "DENY",
    "decision_code": "PERMISSION_DENIED"
  },
  "business_outcome": "RESPONSIBILITY_FOUND_PERMISSION_DENIED"
}
```

责任解析不能直接返回 Permission 对象或把 Permission 当作候选来源。权限编码只作为独立预检输入和证据。

---

## 10. Evidence（解析证据）设计

### 10.1 本阶段存储原则

Evidence 只在当前请求内生成并随响应返回：

```text
Evidence Persistence = NONE
Evidence Table = NONE
Business Audit Write = NONE
```

本阶段不新增解析记录表、快照表或专用审计表。普通技术访问日志不得被解释为正式业务解析证据。

### 10.2 Evidence 内容

| 分组 | 字段 |
|---|---|
| 动作 | action code、required responsibility、required permission、workflow、node |
| 对象 | object type、ID、version、company、department、business status |
| 责任 | Responsibility ID/code/name/status/effective period、事实来源 |
| 岗位关系 | PositionResponsibility ID、PRIMARY/SUPPORTING、active、来源 |
| 岗位 | Position ID/code/name、company、department、状态和有效期 |
| 员工 | Employee ID/no/name、position、department、status |
| 账户 | User ID/username、active；仅必要内部证据，页面避免过度暴露 |
| 授权 | action code、decision code、ALLOW/DENY、scope、authority source |
| 结果 | resolution status、candidate counts、排除原因、解析时点 |

### 10.3 示例

```json
{
  "businessAction": {
    "code": "procurement.purchase_request.approve",
    "name": "采购申请审批"
  },
  "responsibility": {
    "code": "PURCHASE_REQUEST_APPROVAL",
    "name": "采购申请审批责任",
    "source": "system.Responsibility"
  },
  "position": {
    "code": "PURCHASE_MANAGER",
    "name": "采购经理",
    "source": "system.PositionResponsibility"
  },
  "employee": {
    "employeeNo": "EMP006",
    "name": "张三"
  },
  "resolutionStatus": "RESOLVED",
  "authorizationPrecheck": "ALLOW",
  "resolvedAt": "server-time",
  "readOnly": true
}
```

示例中的岗位和员工只用于解释输出，不构成代码默认值或正式数据创建指令。

---

## 11. 只读 API 设计

### 11.1 Endpoint（接口）

```text
GET /api/responsibility-resolution/preview
```

Query Parameters（查询参数）：

```text
business_action_code=procurement.purchase_request.approve
object_type=purchase_request
object_id={server_object_id}
```

### 11.2 调用者权限

V1 预览仅面向受控管理员和架构验收身份。建议复用现有 `system.organization.responsibility.manage` 作为预览入口权限，不新增 `responsibility.preview.v2` 等重复权限。

这项权限只控制谁能查看解析预览；候选 Employee 是否能执行目标动作，仍由 AuthorizationService 按 `requiredPermission` 独立预检。

### 11.3 服务端处理顺序

```text
验证调用者身份与预览权限
→ 校验 Action Registry
→ 服务端读取业务对象
→ 固定本次 as_of
→ 只读解析 Responsibility / Position / Employee / User
→ 唯一成功时调用 AuthorizationService 预检候选 User
→ 组装 Evidence
→ 返回响应
```

### 11.4 HTTP 语义

| 情况 | HTTP | 业务状态 |
|---|---:|---|
| 解析完成，包括未解析/多人/无员工/候选权限拒绝 | 200 | 由 `resolution_status` 表达 |
| 调用者无预览权限 | 403 | `PREVIEW_PERMISSION_DENIED` |
| 参数格式错误或动作与对象类型不匹配 | 400 | 明确错误码 |
| 对象不存在 | 404；跨租户时可统一 403 | 不泄露其他组织对象 |
| 系统读取失败 | 500 | `RESOLUTION_READ_FAILED`，零业务写入 |

多人、无人和权限不足是可解释的业务解析结果，不是服务器异常。

### 11.5 只读安全契约

- 仅允许 GET；
- 响应设置 `Cache-Control: no-store`；
- 不接受客户端提交的岗位、员工、角色、权限或状态结论；
- 对象和组织事实必须重新读取；
- 限制候选列表数量并返回 `candidate_count`，超限返回配置冲突；
- 不调用任何 POST/transition/create/notify 方法；
- 响应固定包含 `read_only=true` 和 `business_write_count=0`；
- 超时、异常或授权拒绝均不得产生业务写入。

### 11.6 响应示例

```json
{
  "success": true,
  "data": {
    "contract_version": "PCE-RESPONSIBILITY-RESOLUTION-PREVIEW-V1",
    "read_only": true,
    "business_action": {
      "code": "procurement.purchase_request.approve",
      "name": "采购申请审批"
    },
    "business_object": {
      "type": "purchase_request",
      "id": "123",
      "company_id": "server-derived",
      "department_id": "server-derived"
    },
    "required_responsibility": {
      "code": "PURCHASE_REQUEST_APPROVAL",
      "name": "采购申请审批责任"
    },
    "position_candidates": [],
    "employee_candidates": [],
    "resolved_employee": null,
    "resolution_status": "RESPONSIBILITY_UNRESOLVED",
    "authorization_precheck": {
      "status": "NOT_RUN"
    },
    "evidence": {
      "responsibility_source": "system.Responsibility",
      "position_relationship_source": "system.PositionResponsibility",
      "employee_source": "pfm.Employee",
      "exclusions": ["NO_ACTIVE_PRIMARY_POSITION"]
    },
    "resolved_at": "server-time",
    "business_write_count": 0
  }
}
```

---

## 12. Purchase Request（采购申请）只读验证方案

### 12.1 验证目标

输入：

```text
business_action_code = procurement.purchase_request.approve
object_type = purchase_request
object_id = 人工选择的真实采购申请 ID
```

输出只展示：

- 所需责任；
- 岗位候选；
- 员工候选；
- 解析状态；
- 唯一员工时的授权预检；
- Evidence。

### 12.2 前置事实

只读验证前由管理员人工确认：

1. `PURCHASE_REQUEST_APPROVAL` 已存在并处于有效期内的 ACTIVE 状态；
2. 目标公司有明确的有效 PRIMARY PositionResponsibility；
3. Position 有零个、一个或多个正式 Employee，用于不同测试场景；
4. 唯一 Employee 场景已关联有效 User；
5. User 的 Role/Permission/Scope 分别覆盖 ALLOW 与 DENY 场景；
6. 采购申请对象、公司、部门、状态和动作契约均由服务端读取。

验证接口不得为了满足前置条件创建或修改这些事实。

### 12.3 运行保护断言

每次预览前后必须比较：

```text
Responsibility count           unchanged
PositionResponsibility count   unchanged
PositionWorkflowResponsibility unchanged
ApprovalTask count             unchanged
Purchase Request status/version unchanged
PurchaseOrder count            unchanged
SupplierMaterialPrice count    unchanged
Notification count             unchanged
Unauthorized Business Writes   = 0
```

### 12.4 页面建议

未来可在受控诊断页提供“只读解析预览”，固定显示：

> 本功能只计算谁应该负责并进行权限预检，不创建审批任务、不改变采购状态、不通知候选人。

页面不得提供“采用此人”“创建任务”“替换审批人”或“自动修复配置”按钮。

---

## 13. 测试方案

### 13.1 必测六项

| 编号 | 配置 | 预期 |
|---|---|---|
| RRE-T01 | 唯一有效责任、岗位、员工和账户 | `resolution_status=RESOLVED`；返回唯一 Evidence |
| RRE-T02 | 同一范围多个有效主责岗位，或唯一岗位多人任职 | `MULTIPLE_CANDIDATES`；不按权限或 ID 选择 |
| RRE-T03 | 动作无责任映射或无有效岗位责任路径 | `RESPONSIBILITY_UNRESOLVED` 或更精确的映射错误；不找主管 |
| RRE-T04 | 唯一岗位无有效员工任职 | `NO_ACTIVE_EMPLOYEE`；授权预检 `NOT_RUN` |
| RRE-T05 | 唯一员工但 AuthorizationService 拒绝 | `RESOLVED` + `DENY`；业务结果为 `RESPONSIBILITY_FOUND_PERMISSION_DENIED` |
| RRE-T06 | 唯一员工且 AuthorizationService 允许 | `RESOLVED` + `ALLOW`；仍不执行动作 |

### 13.2 扩展安全测试

| 编号 | 验证 | 预期 |
|---|---|---|
| RRE-T07 | DRAFT/SUSPENDED/EXPIRED/过期责任 | 不进入候选 |
| RRE-T08 | SUPPORTING 关系存在但无 PRIMARY | 不自动升级，返回未解析 |
| RRE-T09 | 多候选中只有一人有权限 | 仍为 `MULTIPLE_CANDIDATES` |
| RRE-T10 | 跨公司岗位或员工 | 排除并记录 Scope Evidence |
| RRE-T11 | 员工无账户或账户停用 | 对应明确身份状态，不找替代人 |
| RRE-T12 | 调用者无预览权限 | HTTP 403，零写入 |
| RRE-T13 | 伪造客户端 company/department/status | 服务端忽略并重新读取 |
| RRE-T14 | 重复请求 | 相同事实与 as_of 得到相同结果，零写入 |
| RRE-T15 | 技术异常/超时 | `RESOLUTION_READ_FAILED`，所有保护数量不变 |
| RRE-T16 | 只读采购保护 | ApprovalTask、采购状态、订单和价格均不变 |

### 13.3 测试分层

1. 纯解析规则单元测试；
2. 正式模型只读集成测试；
3. AuthorizationService ALLOW/DENY 预检测试；
4. API 参数、403、404 与 no-store 测试；
5. 零业务写入与模型数量保护测试；
6. 浏览器人工只读预览验收。

自动测试样例只能存在于隔离测试数据库，不得创建正式责任或采购事实。

---

## 14. 风险与控制

| 优先级 | 风险 | 影响 | 控制 |
|---|---|---|---|
| P0 | 用权限过滤多人候选 | 把“可以做”误当“应该做” | 多人先终止解析，权限不参与消歧 |
| P0 | 无责任时找主管/管理员 | 隐性硬编码审批人 | 明确 `RESPONSIBILITY_UNRESOLVED`，禁止兜底 |
| P0 | 预览误调用流程写服务 | 创建任务或推进采购 | 结构性只读依赖、零写入断言 |
| P0 | 客户端伪造组织范围 | 跨公司数据泄露或误解析 | 按 object ID 重新读取全部上下文 |
| P0 | Action 自动生成责任 | 企业责任未经治理 | Registry 只能引用既有责任 |
| P1 | SUPPORTING 被当主责 | 产生错误负责人 | V1 默认只消费有效 PRIMARY |
| P1 | 一个岗位多人任职 | 无唯一自然人 | `MULTIPLE_CANDIDATES`，不自动选人 |
| P1 | 责任找到但账户无权限 | 任务无法合法执行 | 独立返回 DENY，不换责任人 |
| P1 | Evidence 被误认为正式审计 | 历史证明不足 | 响应内临时证据，明确不落库 |
| P1 | 全局责任跨公司关系混淆 | 候选范围错误 | 按业务对象 Company/Department 精确过滤 |
| P1 | 使用列表缓存解析 | 事实过期 | 每次预览从服务端正式模型重新读取 |
| P2 | 候选数量过大 | 性能与信息泄露 | 限制候选数量、索引评审、超限报冲突 |
| P2 | AI 建议被自动采用 | 未授权企业事实 | `ADVISORY_ONLY` + 人工维护与审计 |

---

## 15. AI（人工智能）边界

AI 可以：

- 推荐责任配置草案；
- 发现动作缺少责任映射；
- 分析无人、多人、无账户或权限不足；
- 解释 Evidence 与冲突原因；
- 推荐管理员检查哪些正式事实。

AI 不可以：

- 自动创建或修改 Responsibility；
- 自动分配 PositionResponsibility；
- 自动选择候选人或审批人；
- 自动授予 Role、Permission 或 Scope；
- 自动修改岗位、员工或汇报关系；
- 自动创建 ApprovalTask；
- 自动启动 Shadow Mode 或正式执行。

AI 结论固定为 `ADVISORY_ONLY（仅建议）`。

---

## 16. 后续 Shadow Mode（影子模式）路线

### Phase RRE-0：架构签发

人工确认本报告的输入、状态、冲突、Evidence、授权预检和零写入边界。

### Phase RRE-1：纯函数与隔离测试

后续独立授权后，只实现解析规则和隔离测试，不开放真实 API，不读取或写入采购运行状态。

### Phase RRE-2：管理员只读 Preview API（预览接口）

开放受控 GET 接口，完成 RRE-T01～RRE-T16、浏览器人工预览和零写入验收。

### Phase RRE-3：Purchase Request 只读人工验证

管理员选择真实采购申请，仅查看解析结果。ApprovalTask、采购状态、通知和旧审批逻辑均不变化。

### Phase RRE-4：Shadow Mode 设计复核

比较：

```text
旧审批结果
VS
新只读责任解析结果
```

只设计触发点、差异状态、日志边界、性能和关闭开关。本阶段仍不启动 Shadow。

### Phase RRE-5：Shadow Mode 独立实施授权

只有 RRE-0～RRE-4 人工签发后才能另行授权。Shadow 必须保持旧流程唯一生效，不创建新任务，不替换审批人，不推进采购状态。

### Phase RRE-6：正式切换评审

不属于本报告授权范围。必须重新评审 Workflow Runtime、任务证据、并发、回退、采购业务和人工验收。

---

## 17. 实施前决策清单

| 决策 | V1 结论 |
|---|---|
| 责任事实来源 | `system.Responsibility` |
| 岗位关系来源 | `system.PositionResponsibility` |
| 员工来源 | 正式 Employee 任职关系 |
| 动作映射 | 既有 Business Action Registry 的 `requiredResponsibility` 引用 |
| 权限 | 独立 `requiredPermission`，AuthorizationService 预检 |
| 多岗位/多员工 | `MULTIPLE_CANDIDATES`，不自动选择 |
| 无岗位责任 | `RESPONSIBILITY_UNRESOLVED` |
| 无有效员工 | `NO_ACTIVE_EMPLOYEE` |
| 责任存在但无权限 | `RESPONSIBILITY_FOUND_PERMISSION_DENIED` |
| Evidence | 请求内生成并返回，不落库 |
| API | 受控 GET、no-store、零业务写入 |
| Preview 调用权限 | 建议复用 `system.organization.responsibility.manage` |
| ApprovalTask | 不创建、不修改 |
| Workflow Runtime | 不修改、不调用执行链 |
| Purchase Request | 只读加载，不改状态、不通知 |
| AI | 仅建议 |
| Shadow Mode | 本轮不启动，等待独立授权 |

---

## 18. 本轮变更与保护声明

本轮只完整读取指定依据并新增本设计报告。

```text
Code Changed = NO
Database Changed = NO
Migration Created = NO
Resolution Table Created = NO
Responsibility Data Changed = NO
Permission / Role Changed = NO
Workflow Runtime Changed = NO
ApprovalTask Changed = NO
Purchase Approval Changed = NO
Shadow Mode Started = NO
Business Data Changed = NO
```

本轮没有调用责任、岗位、权限、采购、流程或任务写接口，也没有运行责任解析。

---

## 19. 最终结论

Responsibility Resolution Engine V1 必须先完成两件彼此独立的事：

```text
第一：解析谁应该负责
第二：预检这个人当前是否允许执行
```

责任解析不能用 Permission 选择责任人，AuthorizationService 不能替代责任解析。只有唯一责任人且预检 ALLOW，未来才可能在另行授权后进入任务或执行阶段。

最终状态：

```text
Responsibility Resolution Architecture = PASS
Read-only Validation Design = PASS
Implementation Authorized = NO
Preview API Implemented = NO
Shadow Mode = NOT STARTED
Human Architecture Review = WAITING
```

本轮到此停止，等待人工架构审核。
