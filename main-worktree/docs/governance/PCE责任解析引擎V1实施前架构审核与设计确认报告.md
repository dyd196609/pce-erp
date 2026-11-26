# PCE Responsibility Resolution Engine（责任解析引擎）V1——实施前架构审核与设计确认报告

报告日期：2026-08-17  
任务类型：Architecture Review & Design Confirmation（架构审核与设计确认）  
实施属性：Design Only（仅设计）/ Not Implemented（未实施）  
当前状态：DESIGN CONFIRMED / HUMAN ARCHITECTURE SIGN-OFF WAITING（设计已确认/等待人工架构签发）

---

## 1. 当前设计审核结论

本轮确认 Responsibility Resolution Engine（责任解析引擎）V1 的基本方向正确，但只允许进入实施准备，不授权实现、数据库迁移或采购流程切换。

核心边界正式确认如下：

```text
Responsibility（职责/责任定义）
→ 回答“谁应该负责？”

Permission（权限）
→ 回答“谁可以执行？”

AuthorizationService（统一授权服务）
→ 回答“当前这次执行是否被允许？”
```

三者必须严格分离：

```text
Responsibility（职责/责任定义）
→ 解析 Position（岗位）与 Employee（员工）

Permission（权限）
→ 通过 Role（角色）表达系统能力集合

AuthorizationService（统一授权服务）
→ 结合 Employee 关联账户、Role、Permission、Scope（数据范围）和业务对象作最终裁决
```

责任解析不得直接授权；拥有权限的任意用户不得被当作责任人；责任人缺少权限时不得改找管理员、有权限用户、直属主管或按 ID 排序的第一人。

### 1.1 审核结论

| 审核项 | 结论 |
|---|---|
| 数据驱动方向 | PASS（通过） |
| 复用现有组织模型 | PASS（通过） |
| 复用现有权限核心 | PASS（通过） |
| 新增第二套权限体系 | NO（否） |
| 新增 V2 责任模型 | NO（否） |
| 只读责任解析设计 | READY FOR IMPLEMENTATION PLANNING（可进入实施计划） |
| Shadow Mode（影子模式）设计 | CONFIRMED（已确认） |
| 采购审批切换 | NOT AUTHORIZED（未授权） |
| 数据库或模型变更 | NOT AUTHORIZED（未授权） |
| 人工架构签发 | WAITING（等待） |

### 1.2 实施前硬门禁

以下任一条件未满足时，不得从影子模式进入正式责任驱动任务分派：

1. 四项 Architecture Decision Record（架构决策记录）经人工签发；
2. 正式 Responsibility、PositionResponsibility（岗位职责关系）与 PositionWorkflowResponsibility（岗位流程责任关系）已由管理员维护，并完成有效性与唯一性验收；
3. Business Action Registry（业务动作注册中心）能够声明所需职责，但不改变 Permission Registry（权限注册中心）的权威性；
4. 多人候选、无候选、无执行账户和权限拒绝均有明确阻断结果；
5. Shadow Mode 差异样本达到人工批准的观察期与通过标准；
6. 任何 ApprovalTask（审批任务）及 Evidence（解析证据）字段扩展另行完成 Schema（数据结构）审核与 Migration（数据库迁移）授权；
7. 采购申请现有审批行为、状态和数据数量在影子阶段保持不变。

---

## 2. 已完整读取的依据

### 2.1 责任解析与组织模型材料

- `docs/governance/PCE责任解析引擎V1设计报告.md`
- `docs/governance/PCE企业组织运作模型V1-数据驱动架构审计报告.md`
- `docs/governance/PCE企业组织运作模型V1-实施与人工验收交接报告.md`
- `docs/governance/PCE企业组织运作模型V1-正式管理员入口统一与维护闭环整改报告.md`
- `docs/governance/PCE企业组织运作模型V1-员工汇报关系语义优化报告.md`

### 2.2 权限体系材料

- `docs/standards/PCE-BUSINESS-ACTION-PERMISSION-V1.0.md`
- `docs/governance/组织、岗位、账户、角色、权限体系专项报告.md`
- `docs/governance/PCE公共组织身份权限核心V1-最终人工验收与封板报告.md`

权限材料共同确认：页面、路由、按钮、localStorage（浏览器本地存储）、岗位名称和用户名均不是授权事实；服务端 AuthorizationService 是身份、动作权限和数据范围结论的唯一公共入口。Position 不等于 Role，Role 也不等于 Responsibility。

---

## 3. Enterprise Operation Data Driven Principle（企业运作数据驱动原则）

> 企业组织、部门、岗位、员工、职责、责任和流程归属属于动态企业主数据。代码只提供模型、规则、校验和运行能力；企业实际关系必须由管理员维护的数据产生。

允许代码固定的是稳定语义：Business Action Code（业务动作编码）、Permission Code（权限编码）、Workflow Code（流程编码）、Node Code（节点编码）、Responsibility Code（职责编码）、状态机与校验算法。

禁止代码固定的是企业事实：公司 ID、部门 ID 或名称、岗位 ID 或名称、员工 ID、用户名、审批人、供应商负责人和实际汇报关系。

正确链路：

```text
Business Rule（业务规则）
→ 读取正式企业主数据
→ 解析当前有效责任
→ 取得唯一 Employee
→ AuthorizationService 最终裁决
→ Task / Execution（任务/执行）
```

禁止链路：

```text
采购申请
→ 代码写死“采购经理”
→ 取任意管理员或拥有审批权限的人
→ 创建任务
```

---

## 4. 当前实现事实与差距

### 4.1 当前正式事实

| 对象 | 当前能力 | 当前数据/运行状态 |
|---|---|---|
| Department（部门） | 公司、层级和正式组织范围 | 可复用 |
| Position（岗位） | 公司、部门、层级、有效期和启停 | 可复用 |
| Employee（员工） | 正式部门、正式岗位、状态及可选 User（用户账户） | 可复用 |
| EmployeeReportingRelation（员工汇报关系） | 直属/职能主管及有效期 | 仅显式主管策略使用 |
| Responsibility（职责/责任定义） | 唯一 code、name、description、category、is_active | 当前 0 条 |
| PositionResponsibility（岗位职责关系） | 岗位、职责、主责和启停 | 当前 0 条 |
| PositionWorkflowResponsibility（岗位流程责任关系） | 流程、节点、责任类型、有效期和岗位 | 当前 0 条 |
| Business Action（业务动作） | 已声明 requiredPermission、Role 和 Scope 等 | 尚未声明 requiredResponsibility |
| Permission（权限） | RolePermission（角色权限关系）和组织范围事实 | 已封板，必须复用 |
| ApprovalTask（审批任务） | `required_role_code`、步骤和审批数量 | 未保存责任、岗位、员工或证据 |

### 4.2 已确认运行断点

1. 采购申请提交路径仍写入“采购经理审批”和“采购经理”文本；
2. Workflow Runtime（流程运行引擎）没有消费 PositionWorkflowResponsibility；
3. Business Action 契约只有 Required Permission（所需权限），没有 Required Responsibility（所需职责）；
4. ApprovalTask 不能持久化解析责任人及解析证据；
5. 当前三类责任数据均为 0，不能声称任何真实业务责任已完成解析；
6. 前端流程 owner 或角色文案不能作为正式比较基准，只能作为 Legacy Result（旧逻辑结果）的原始文本证据。

---

## 5. Decision 1：Responsibility Code（职责编码）规范

决策编号：`ADR-RRE-001`  
决策状态：CONFIRMED FOR HUMAN SIGN-OFF（已形成确认方案，等待人工签发）

### 5.1 编码定位

Responsibility Code 是跨组织变化保持稳定的业务责任语义标识，不是岗位编码、员工编码、权限编码或流程节点编码。

编码回答“需要哪一种责任”，不回答“当前哪个岗位或员工承担责任”。例如：

```text
PURCHASE_REQUEST_APPROVAL（采购申请审批责任）
PURCHASE_ORDER_APPROVAL（采购订单审批责任）
SUPPLIER_REVIEW（供应商审核责任）
SUPPLIER_APPROVAL（供应商批准责任）
PAYMENT_APPROVAL（付款审批责任）
```

### 5.2 统一语法

```text
<BUSINESS_OBJECT>_<RESPONSIBILITY_PURPOSE>
```

正式约束：

| 项目 | 规则 |
|---|---|
| 字符集 | 大写英文字母、数字和下划线 |
| 正则建议 | `^[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)*$` |
| 长度 | 3～80 字符，适配现有 Responsibility.code |
| 唯一性 | PCE 全局唯一，沿用现有数据库唯一约束 |
| 语序 | 先业务对象，后责任目的 |
| 末尾词 | 优先使用 `APPROVAL / REVIEW / EXECUTION / OWNERSHIP / EVALUATION` 等受治理词汇 |
| 禁止内容 | 人名、用户名、公司 ID、部门 ID、岗位 ID、日期、环境名和自由文本 |
| 禁止版本后缀 | 不使用 `_V1`、`_V2` 表达流程或实现版本 |

推荐示例：

| Module Code（模块编码） | Responsibility Code | 中文名称 |
|---|---|---|
| `PROCUREMENT` | `PURCHASE_REQUEST_APPROVAL` | 采购申请审批责任 |
| `PROCUREMENT` | `PURCHASE_ORDER_APPROVAL` | 采购订单审批责任 |
| `SUPPLIER` | `SUPPLIER_REVIEW` | 供应商审核责任 |
| `SUPPLIER` | `SUPPLIER_APPROVAL` | 供应商批准责任 |
| `FINANCE` | `PAYMENT_APPROVAL` | 付款审批责任 |
| `WAREHOUSE` | `GOODS_RECEIPT_APPROVAL` | 收货审批责任 |
| `QUALITY` | `QUALITY_DISPOSITION_APPROVAL` | 质量处置审批责任 |
| `PERFORMANCE` | `PERFORMANCE_EVALUATION` | 绩效评价责任 |

不推荐示例：

```text
PROCUREMENT_MANAGER        # 写入了岗位语义
APPROVER_LISI              # 写入了人员语义
PURCHASE_APPROVAL_V2       # 把版本写进稳定责任编码
DEPT_8_APPROVAL            # 写入了企业数据 ID
```

### 5.3 模块归属

Responsibility 使用全局稳定目录；企业实际承担关系仍由 Company（公司）下的 PositionResponsibility 和 PositionWorkflowResponsibility 决定。

V1 不新增模块字段。现有 `Responsibility.category` 在实施时应受控承载 canonical module code（正式模块编码），并与 Business Action Registry 的 `moduleCode` 一致。当前 Responsibility 为 0 条，不存在历史分类迁移问题；若实施核查发现 `category` 已承担不同正式语义，则必须停止并重新进行 Schema 评审，禁止一字段双义。

模块归属规则：

1. 一个 Responsibility 只有一个 owner module（归属模块）；
2. 其他模块可以引用，但不能复制出同义职责；
3. 跨模块责任由语义主责模块拥有；
4. moduleCode 不是公司、部门或岗位；
5. 模块变更是治理变更，必须有原因和审计。

### 5.4 版本化决策

Responsibility Code 本身不版本化且一经正式使用不可改义。Workflow Version（流程版本）、Action Contract Version（动作契约版本）和 Evidence Schema Version（证据结构版本）分别记录自己的版本。

处理规则：

- 名称或说明的非破坏性澄清：保留 code；
- 责任语义发生实质变化：创建新的语义化 code，不复用旧 code；
- 不允许通过 `_V2` 掩盖语义不清，应使用能说明新责任边界的新名称；
- 历史任务和证据继续引用原 code 与当时名称快照。

### 5.5 停用决策

允许停用，复用现有 `is_active`。停用含义：

1. 不再允许新 PositionResponsibility、PositionWorkflowResponsibility 或新流程版本引用；
2. 解析时不进入新候选；
3. 不删除历史关系和 Evidence（解析证据）；
4. 已创建任务按其冻结证据处理，但执行时仍重新校验权限；
5. 重新启用只允许恢复完全相同语义，禁止停用后换义复用。

---

## 6. Decision 2：Multiple Candidates（多人责任候选）规则

决策编号：`ADR-RRE-002`  
决策状态：CONFIRMED FOR HUMAN SIGN-OFF（已形成确认方案，等待人工签发）

### 6.1 候选路径定义

一个 Candidate Path（候选责任路径）必须完整包含：

```text
Responsibility
→ PositionResponsibility
→ PositionWorkflowResponsibility（流程场景）
→ Position
→ Employee
→ User
```

先按服务端业务对象的 Company、Department、Workflow Code、Node Code、责任类型、有效期和启停状态过滤，再计算候选数量。Permission 不参与候选缩减，只在责任唯一后校验。

### 6.2 判定矩阵

| 情况 | 结果码 | 处理 |
|---|---|---|
| 唯一有效路径、唯一 Employee | `RESOLVED`（责任已解析） | 继续 AuthorizationService 权限预检 |
| 无有效路径或岗位无有效 Employee | `RESPONSIBILITY_UNRESOLVED`（责任未解析） | 阻断新任务；管理员补配置 |
| 一个 Responsibility 对应多个有效 Position | `MULTIPLE_CANDIDATES`（多个责任候选人） | 阻断；不得选第一项 |
| 一个 Position 对应多个有效 Employee | `MULTIPLE_CANDIDATES` | 阻断；不得按资历、姓名或 ID 选人 |
| 多条路径最终指向同一 Employee | `RESPONSIBILITY_CONFIGURATION_CONFLICT`（责任配置冲突） | 阻断并清理重叠路径，不静默去重 |
| 唯一 Employee 无 User | `RESPONSIBILITY_FOUND_NO_EXECUTION_IDENTITY`（责任存在但无执行身份） | 阻断数字任务 |
| 唯一 Employee 权限不足 | `RESPONSIBILITY_FOUND_PERMISSION_DENIED`（责任存在但权限不足） | 阻断；修复权限，不换人 |

### 6.3 允许的确定性缩小方式

以下方式属于正式业务规则，可以缩小候选：

1. 业务对象的正式 Company；
2. 业务对象或流程契约声明的正式 Department Scope（部门范围）；
3. 精确匹配 workflowCode、nodeCode 与 ownershipType；
4. Position、Employee 和关系的 active/effective period（启用与有效期）；
5. 管理员维护的、可审计的业务 Scope，例如品类、区域或金额层级——但只有在正式模型已明确表达后才能使用。

以下方式一律禁止：

- 随机选择；
- 按 ID、姓名、创建时间或查询返回顺序选择；
- 找管理员代替；
- 找任意拥有权限的人；
- 按“采购经理”“采购部”等名称包含关系筛选；
- 因 `is_primary=true` 就在重叠配置中静默胜出；
- 用直属主管作为默认回退。

### 6.4 多候选后的治理路径

推荐优先级：

```text
P1 修复责任配置范围
→ P2 修复组织或有效期重叠
→ P3 明确并行会签流程语义
→ P4 必要时执行一次性人工异常选择
```

#### A. 配置责任范围

由管理员把同一职责的岗位分配限定到明确 Company、Department、workflow/node 或未来受治理业务 Scope。范围是数据，不是代码中的部门或岗位名称。

#### B. 人工选择

V1 默认不允许普通审批发起人从候选中任意选人。若未来必须支持一次性异常选择，应作为独立 Business Action，例如 `workflow.responsibility_exception.select`，并满足：

- 只能从服务端返回的当前候选中选择；
- 需要独立 Permission；
- 必须填写原因；
- 只对一个业务对象、一个节点和一次任务有效；
- 保存操作者、候选全集、选择结果、时间和 Evidence；
- 不修改 PositionResponsibility 等企业主数据；
- 当前模型不能完整持久化该异常动作，必须另行评审既有 ApprovalTask 的最小扩展，不能新建 V2 责任表。

#### C. 并行或会签

并行审批必须由 Workflow Route（流程路线）显式声明 `allow_parallel`、席位责任和 `minimum_approvals`。偶然出现多个候选不等于并行会签，不得自动转换。

---

## 7. Decision 3：Evidence（解析证据）策略

决策编号：`ADR-RRE-003`  
决策状态：RECOMMEND OPTION B（推荐方案 B，等待人工签发）

### 7.1 三种保存时点比较

| 方案 | 保存时点 | 优点 | 缺点 | 结论 |
|---|---|---|---|---|
| A | 只在运行时生成 | 简单、零持久化 | 组织变化后无法证明当时为什么选人；无法重放任务分派 | 仅用于预览和 Shadow，不作为正式闭环 |
| B | 审批任务生成时保存 | 与任务责任同一时点、可证明、可审计、可重放 | 需要既有 ApprovalTask 具备证据字段 | **推荐为正式方案** |
| C | 业务执行完成后保存 | 可附带最终执行结果 | 保存过晚；无法证明任务创建时依据，且失败/未完成任务没有证据 | 只能作为补充执行证据 |

### 7.2 推荐策略

采用“B 为主、A 和 C 各司其职”：

```text
A：解析时生成临时 Evidence
→ B：创建 ApprovalTask 时在同一事务冻结 Assignment Evidence（分派证据）
→ C：实际执行时追加 Execution Authorization Evidence（执行授权证据）
```

关键规则：

1. B 是正式责任分派证据，不得等到业务完成后补造；
2. Task 创建与 B 的保存必须原子化，要么同时成功，要么都不发生；
3. C 追加实际执行时 AuthorizationService 结论，不覆盖 B；
4. 组织关系变化不修改历史 B；如需改派，必须由显式改派动作产生新的证据链；
5. Shadow Mode 没有正式任务，因此只产生 A，并写入受控的 shadow observability event（影子可观测事件），不得写业务任务表。

### 7.3 Evidence 最小字段

| 证据组 | 必须字段 |
|---|---|
| Identity（身份） | `resolution_id`、`correlation_id`、`evidence_schema_version` |
| Business Action（业务动作） | action code、module code、required permission、action contract version |
| Workflow（工作流） | workflow code、workflow version、node code、责任类型 |
| Responsibility（职责/责任定义） | ID、code、名称快照、module code、active |
| Position（岗位） | ID、code、名称快照、Company ID、Department ID、有效期 |
| Employee（员工） | ID、employee no、姓名快照、状态、User ID |
| Mapping Source（映射来源） | PositionResponsibility ID、PositionWorkflowResponsibility ID、启停和有效期 |
| Organization Scope（组织范围） | Company ID、Department ID、Scope code、业务对象来源 |
| Resolution（解析结论） | status、candidate count、candidate path IDs、resolved at |
| Authorization（授权） | required permission、decision code、authority source、role codes、scope snapshot |
| Integrity（完整性） | `resolution_hash`、业务对象类型/ID/版本 |

示例：

```text
Business Action（业务动作）：procurement.purchase_request.approve（采购申请审批）
Workflow Code（流程编码）：PROCUREMENT_PURCHASE_REQUEST
Node Code（节点编码）：PURCHASE_APPROVAL
Responsibility（职责/责任定义）：PURCHASE_REQUEST_APPROVAL（采购申请审批责任）
Position（岗位）：采购经理 / POS-PROCUREMENT-MANAGER
Employee（员工）：李四 / EMP006
Organization Scope（组织范围）：Company 2 / Department 8
Source（来源）：PositionResponsibility #21 + PositionWorkflowResponsibility #34
Resolved At（解析时间）：服务端 UTC 时间
```

示例名称和 ID 只说明证据格式，不得写入代码或自动初始化为正式事实。

### 7.4 Evidence 完整性与隐私

- Hash（摘要指纹）由规范化 ID、code、版本、有效期、业务对象版本和解析时间生成；Hash 不替代原文；
- 标签使用当时快照，解析键必须使用稳定 ID/code；
- 不保存身份证、电话等无关个人敏感信息；
- 普通页面只显示必要解释，完整权限结构只向受权诊断入口开放；
- Evidence 不得由前端重算，也不得从上一页缓存补齐。

---

## 8. Decision 4：Purchase Request Shadow Mode（采购申请影子模式）

决策编号：`ADR-RRE-004`  
决策状态：CONFIRMED FOR IMPLEMENTATION PLANNING（已确认，可进入实施计划但尚未授权实施）

### 8.1 目标与不可变边界

Shadow Mode 的唯一目标是比较现有采购申请审批路由与新责任解析结果，不改变现有采购审批。

```text
Legacy Path（旧路径）
采购申请 → 原审批逻辑 → 原节点/角色/审批人结果

Shadow Path（影子路径）
采购申请 → Responsibility Resolution Engine → 新解析结果与 Evidence

Compare（比较）
旧结果 VS 新结果 → 差异事件与统计
```

影子路径必须保证：

- 不创建、修改或关闭 ApprovalTask；
- 不修改 Purchase Request（采购申请）状态、节点或审批人字段；
- 不调用审批动作；
- 不修改 Role、Permission、责任关系或组织数据；
- 解析失败、超时或日志失败不回滚旧审批；
- 新结果永远不成为影子阶段的业务执行输入。

### 8.2 触发位置

推荐触发位置：采购申请由旧逻辑成功提交并完成事务提交之后，通过 after-commit observer（事务提交后观察器）发起只读影子解析。

选择理由：

1. 旧事务结果已经确定，影子异常不会影响提交；
2. 可以读取服务端提交后的真实状态和旧审批结果；
3. 避免在旧业务事务内增加锁、延迟或失败传播；
4. 影子读取使用业务对象 ID 重新加载，不信任页面载荷。

必须区分：

- Trigger Action（触发动作）：`purchase_request.submit`；
- Target Assignment Action（目标分派动作）：`procurement.purchase_request.approve` 或经 Registry 确认的正式审批动作；
- Shadow 解析的是目标审批责任，不是把提交人当审批人。

### 8.3 输入数据

所有输入由服务端重新读取：

| 输入 | 来源 |
|---|---|
| business object type / ID / version | 提交后的 Purchase Request |
| Company | 正式业务对象及授权上下文 |
| Department | 正式申请部门/采购组织规则 |
| business action | 服务端 Business Action Registry |
| required permission | 同一 Action 契约 |
| required responsibility | 同一 Action 契约 |
| workflow code / version | 正式流程定义或旧路由映射 |
| node code / responsibility type | 当前目标审批节点 |
| as-of time | 服务端解析时间 |
| legacy result | 旧逻辑生成的节点、required role、Employee/User ID 或原始审批人文本 |

若 Company、Department、workflow/node 或对象版本无法从正式服务端事实确定，新路径返回 `RESPONSIBILITY_CONTEXT_MISMATCH`，不得用 `company_id=1`、采购部名称或页面字段兜底。

### 8.4 输出结果

每次影子运行输出：

```text
shadow_run_id
correlation_id
trigger_action
target_assignment_action
business_object_type / id / version
legacy_result
resolution_result
permission_precheck
evidence
comparison_status
duration_ms
error_code
observed_at
business_write_count = 0
```

### 8.5 日志方案

影子结果写入结构化可观测日志或受治理的非业务观察存储，不写 PurchaseRequest（采购申请）、ApprovalTask、OrganizationOperatingAuditRecord（组织运作审计记录）或其他业务表。

日志要求：

- 一次运行一个 `shadow_run_id`；
- 通过 `correlation_id` 关联旧提交日志，但不改变旧日志；
- 保存稳定 ID/code 和必要标签快照；
- 多候选保存全部候选路径 ID，不只保存第一人；
- 脱敏，不记录密码、身份证和不必要联系方式；
- 日志写入失败只产生技术告警，不影响旧业务；
- 观察数据保留周期、访问权限和导出规则在实施前单独确认。

### 8.6 差异分类

| Comparison Status（比较状态） | 定义 | 处理 |
|---|---|---|
| `MATCH_EMPLOYEE` | 旧、新均有稳定 Employee ID 且一致 | 统计匹配 |
| `MATCH_EXECUTION_USER` | Employee 映射不同表达，但最终 User ID 一致 | 人工复核组织数据 |
| `LEGACY_TEXT_ONLY` | 旧逻辑只有“采购经理”等文本，无法与 Employee 比较 | 不得记为 MATCH；列入旧事实不足 |
| `NEW_UNRESOLVED` | 新链无责任候选 | 配置缺失清单 |
| `NEW_MULTIPLE_CANDIDATES` | 新链有多个候选 | 配置冲突清单 |
| `NEW_PERMISSION_DENIED` | 新链唯一责任人权限不足 | 权限差距清单 |
| `ASSIGNEE_MISMATCH` | 旧、新稳定 Employee/User 不一致 | P0 人工复核 |
| `SCOPE_MISMATCH` | 公司或部门范围不一致 | P0，禁止进入正式切换 |
| `COMPARISON_NOT_POSSIBLE` | 任一路径缺少足够稳定身份或上下文 | 补齐事实，不猜测 |
| `SHADOW_TECHNICAL_ERROR` | 超时、依赖或日志技术失败 | 技术修复，旧逻辑继续 |

旧值只有“采购经理”文本时，不能因为新岗位也显示“采购经理”就判定匹配；岗位名称一致不证明 Employee 一致。

### 8.7 差异分析指标

至少按 workflow version、node、Company、Department 和日期统计：

- 影子触发总数；
- 解析成功率；
- 唯一责任率；
- 多候选率；
- 无候选率；
- 权限通过率；
- 稳定身份可比较率；
- Employee/User 精确匹配率；
- P0 Scope/assignee mismatch 数；
- P95 解析耗时；
- Shadow technical error 数；
- Business write count，必须恒为 0。

不得以“岗位文案匹配率”代替 Employee/User 精确匹配率。

### 8.8 开关、隔离与回退

服务端 Feature Mode（功能模式）按流程版本受控：

```text
OFF     = 不调用责任解析
SHADOW  = 只读解析、记录差异、旧逻辑唯一生效
ENFORCE = 责任解析成为任务分派门禁；本轮不授权
```

开关规则：

1. 默认 `OFF`；
2. 开关由服务端受治理配置拥有，前端参数不能启用；
3. 可按 workflow/version 逐步开放；如需 Company allowlist（公司允许清单），必须使用正式 Company ID 的受治理配置，不得写死在代码；
4. 设独立 kill switch（紧急关闭开关）和超时；
5. Shadow 异常只关闭影子观察，不改变旧路径；
6. 回退只需 `SHADOW → OFF`，无需回滚业务数据，因为 Shadow 不产生业务写入；
7. 未来 `ENFORCE → SHADOW/LEGACY` 回退只影响尚未创建的新任务，不修改已创建任务及其冻结 Evidence。

### 8.9 影子阶段退出标准

Shadow 不以固定天数自动结束。进入下一阶段必须同时满足：

1. 有人工批准的最小业务样本量和覆盖期；
2. `SCOPE_MISMATCH = 0`；
3. `ASSIGNEE_MISMATCH` 全部完成人工归因；
4. `NEW_MULTIPLE_CANDIDATES` 和 `NEW_UNRESOLVED` 已清零或有明确不切换决定；
5. 唯一责任人的权限预检通过；
6. Shadow technical error 在批准阈值内；
7. PurchaseOrder（采购订单）和 SupplierMaterialPrice（供应商物料价格）保护计数不变；
8. 由人工架构与业务负责人共同签发，禁止程序自动切换到 ENFORCE。

---

## 9. 当前模型充分性审核

### 9.1 复用结论

| 现有对象 | Shadow 只读解析 | 正式任务分派 | 结论 |
|---|---|---|---|
| Department | 足够 | 足够 | 提供 Company/Department Scope |
| Position | 足够 | 足够 | 提供岗位、组织、有效期和启停 |
| Employee | 条件足够 | 条件足够 | 必须 active 且数字任务需关联 active User |
| EmployeeReportingRelation | 专用策略足够 | 专用策略足够 | 仅动作明确 DIRECT/FUNCTIONAL 时使用 |
| Responsibility | 足够 | 条件足够 | 采用全局稳定目录；category 受控作为 module code |
| PositionResponsibility | 当前解析足够 | 历史重放依赖 Evidence | 本身无有效期，不能单独证明历史状态 |
| PositionWorkflowResponsibility | 足够 | 足够 | 流程场景必须非空关联 Responsibility 并精确匹配节点 |
| Business Action Registry | 契约需扩展 | 契约需扩展 | 在原 Registry 增 requiredResponsibility 等元数据，不新建 Registry |
| Permission / AuthorizationService | 足够 | 足够 | 不修改、不复制，继续最终裁决 |
| ApprovalTask | Shadow 不需要扩展 | 不足 | 缺责任、岗位、Employee/User 和 Evidence 字段 |

### 9.2 不新增模型决策

```text
Read-only Resolution（只读解析）= 现有数据模型足够
Shadow Comparison（影子比较）= 现有业务模型足够
Permission Pre-check（权限预检）= 现有权限模型足够
Persistent Assignment Evidence（持久分派证据）= 现有 ApprovalTask 字段不足
New V2 Responsibility Model（新增V2责任模型）= 禁止
```

### 9.3 未来最小扩展候选

只有在 Shadow 通过并获得独立 Schema/Migration（数据结构/迁移）授权后，才可评审对既有 ApprovalTask 的最小扩展：

- `required_responsibility_id`；
- `resolved_position_id`；
- `assigned_employee_id`；
- `assigned_user_id`；
- `resolution_evidence`；
- `resolution_hash`；
- `resolved_at`。

这是候选设计，不是本报告授权。禁止：

- 新增 ResponsibilityPermissionV2；
- 新增 ApprovalPermissionV2；
- 新增 DirectManagerTable 或 ManagerAuthorityTable；
- 把 Responsibility Code 塞入 `required_role_code`；
- 把 Employee ID 塞入角色字段；
- 使用 OrganizationOperatingAuditRecord 保存审批任务证据。

---

## 10. Workflow Runtime（流程运行引擎）迁移路线

### 10.1 当前与目标

```text
当前：Workflow Node → required_role_code → Role → ApprovalTask

目标：Workflow Node
     → Required Responsibility
     → Responsibility Resolution Engine
     → Position
     → Employee / User
     → AuthorizationService
     → ApprovalTask + Frozen Evidence（冻结证据）
```

### 10.2 兼容模式

| 模式 | `required_role_code` | Required Responsibility | 谁决定新任务 | 用途 |
|---|---|---|---|---|
| `LEGACY` | 生效 | 可为空 | 旧逻辑 | 存量兼容 |
| `SHADOW` | 唯一生效 | 必填用于观察 | 旧逻辑 | 差异验证 |
| `ENFORCE` | 仅历史快照/兼容显示 | 必填并生效 | 责任解析结果 | 未来正式模式 |

禁止同一新任务同时由 required role 和 required responsibility 共同决定责任人。Mode 是流程版本契约的一部分，不能由页面临时切换。

### 10.3 阶段路线

1. **W0 冻结设计**：签发本报告、编码规范和异常码；不改 Runtime。
2. **W1 契约准备**：在现有 Business Action Registry/route 契约设计中加入 required responsibility；不新建第二 Registry。
3. **W2 Read-only Provider（只读提供者）**：实现无写解析与 Evidence；隔离测试覆盖唯一、无候选、多人、无权限和跨公司。
4. **W3 Shadow**：采购申请旧逻辑唯一生效；新逻辑提交后只读比较。
5. **W4 Review Gate（审核门禁）**：人工审核差异、责任数据和权限；不自动升级。
6. **W5 Task Evidence**：另行批准最小扩展既有 ApprovalTask，任务创建时冻结 Evidence。
7. **W6 Enforce Pilot（正式门禁试点）**：仅指定新 workflow version 使用责任分派；失败即不创建任务。
8. **W7 Legacy Retirement（旧模式退役）**：停止新流程写 required role；历史任务只读保留。

### 10.4 回退方案

- W3 可即时从 SHADOW 回到 OFF，业务行为完全不变；
- W6 若回退，只允许新业务对象回到经批准的旧 workflow version；
- 已创建任务不静默改派、不重写 Evidence、不改 required role 历史；
- 回退原因、时间、操作者、影响对象和版本必须审计；
- 不允许以回退为名绕过 AuthorizationService；
- 不允许 unresolved 时在同一请求内偷偷调用 Legacy fallback（旧逻辑回退）。若 ENFORCE 失败，应明确阻断；切换模式必须是治理动作。

---

## 11. Permission（权限）融合方案

### 11.1 唯一执行链

```text
Business Action
→ Business Action Registry 取得 requiredPermission
→ Responsibility Resolution Engine 找到唯一 Employee
→ Employee.user
→ UserRoleScopeAssignment（用户角色范围分配）
→ Role
→ RolePermission
→ Permission
→ AuthorizationService
→ ALLOW / DENY（允许/拒绝）
```

当前 AuthorizationService 的调用参数在实现语义上接收 Permission Code。引擎必须从原 Business Action Registry 读取 `requiredPermission` 后传入，不能假设 Business Action Code 与 Permission Code 永远相同。

### 11.2 两次授权校验

1. **任务生成前预检**：只对唯一责任 Employee 的关联 User 执行，判断该任务是否有可执行身份；
2. **实际执行时复检**：当前登录 User 必须与任务指派一致，并重新执行 ActionPermissionValidator（动作权限校验器）及 AuthorizationService，检查当前 Role、Permission、Scope、对象状态、流程阶段和职责分离。

预检通过不是永久授权。任务创建后权限变化时，实际执行按当前权限事实拒绝，但不篡改创建时责任 Evidence。

### 11.3 结果矩阵

| 责任解析 | 权限结论 | 最终处理 |
|---|---|---|
| 无候选 | 任意 | `RESPONSIBILITY_UNRESOLVED` |
| 多候选 | 任意 | `MULTIPLE_CANDIDATES` |
| 唯一责任人 | DENY | `RESPONSIBILITY_FOUND_PERMISSION_DENIED` |
| 唯一责任人 | ALLOW | `RESOLVED_AUTHORIZED`（责任已解析且获准） |

权限不能用于从多人候选中挑人；责任关系也不能自动生成 Role、Permission 或 Scope。

---

## 12. Purchase Request（采购申请）首阶段验证方案

### 12.1 目标责任链

```text
Purchase Request
→ procurement.purchase_request.approve
→ PURCHASE_REQUEST_APPROVAL
→ PositionResponsibility
→ PositionWorkflowResponsibility
→ 当前有效 Position
→ 唯一 active Employee
→ Employee.user
→ AuthorizationService
→ Shadow Result（影子结果）
```

岗位是否叫“采购经理”不影响解析；承担岗位与实际 Employee 必须来自管理员维护数据。

### 12.2 隔离验证矩阵

| 编号 | 场景 | 影子预期 |
|---|---|---|
| S01 | 唯一责任岗位、唯一 Employee、权限允许 | `RESOLVED_AUTHORIZED` |
| S02 | Responsibility 缺失或停用 | `RESPONSIBILITY_UNRESOLVED` |
| S03 | 无 PositionResponsibility | `RESPONSIBILITY_UNRESOLVED` |
| S04 | 无匹配 workflow/node 关系 | `RESPONSIBILITY_UNRESOLVED` |
| S05 | 一个职责对应多个有效岗位 | `MULTIPLE_CANDIDATES` |
| S06 | 一个岗位对应多个 active Employee | `MULTIPLE_CANDIDATES` |
| S07 | Employee 没有 active User | `RESPONSIBILITY_FOUND_NO_EXECUTION_IDENTITY` |
| S08 | 唯一责任人权限不足 | `RESPONSIBILITY_FOUND_PERMISSION_DENIED` |
| S09 | 跨 Company 或 Department Scope | `RESPONSIBILITY_CONTEXT_MISMATCH` |
| S10 | 旧逻辑只有“采购经理”文本 | `LEGACY_TEXT_ONLY`，不得假报 MATCH |
| S11 | 影子解析超时或异常 | 旧逻辑继续，记录 `SHADOW_TECHNICAL_ERROR` |
| S12 | 影子执行全过程 | PurchaseRequest/ApprovalTask 写入 0 |

---

## 13. 实施阶段建议

| 阶段 | 目标 | 允许内容 | 明确禁止 | 完成门禁 |
|---|---|---|---|---|
| D0 | 人工签发本设计 | 文档评审 | 代码、Schema、数据 | 四项 ADR 签发 |
| D1 | 数据与契约准备方案 | 责任编码清单、动作映射清单 | 自动创建正式责任数据 | 管理员数据方案通过 |
| D2 | 只读引擎专项 | Provider/Service 与隔离测试 | 业务状态、任务写入 | S01～S12 通过 |
| D3 | Shadow 上线 | 提交后只读观察与日志 | 影响旧审批 | 观察期数据完整 |
| D4 | 差异治理 | 人工修复责任/权限配置 | 自动选人、AI 写关系 | P0 差异清零 |
| D5 | 任务证据专项 | 最小 ApprovalTask 扩展评审 | 新 V2 表 | Schema 与迁移专项签发 |
| D6 | Enforce 试点 | 新流程版本责任门禁 | 静默 Legacy fallback | 人工业务验收通过 |
| D7 | 分模块迁移 | 供应商、订单、收货、质量、财务、绩效 | 跨模块一次性切换 | 每模块独立验收 |

每个阶段需要新的实施授权。本报告不授权 D2 及以后任何代码、模型、迁移或业务数据变更。

---

## 14. 后续应用架构约束

| 场景 | Required Responsibility 示例 | 责任来源要求 |
|---|---|---|
| Supplier Review（供应商审核） | `SUPPLIER_REVIEW` | 职责、岗位、Employee；禁止 buyer_name 文本 |
| Supplier Approval（供应商批准） | `SUPPLIER_APPROVAL` | 精确组织范围与唯一岗位 |
| Purchase Order Approval（采购订单审批） | `PURCHASE_ORDER_APPROVAL` | 订单 Company/Department + 流程节点 |
| Goods Receipt Approval（收货审批） | `GOODS_RECEIPT_APPROVAL` | 仓储组织正式岗位关系 |
| Quality Approval（质量审批） | `QUALITY_DISPOSITION_APPROVAL` | 质量组织与检验对象范围 |
| Payment Approval（付款审批） | `PAYMENT_APPROVAL` | 财务责任与现有付款安全边界；不得触发真实付款 |
| Performance Evaluation（绩效评价） | `PERFORMANCE_EVALUATION` | 显式选择岗位职责策略或 EmployeeReportingRelation 策略 |

所有场景继续先解析责任，再由 AuthorizationService 裁决。供应商负责人、评价人和审批人不得使用姓名或岗位文案作为身份键。

---

## 15. AI Boundary（人工智能边界）

AI 可以：

- 提醒 Responsibility 缺失；
- 推荐可能的岗位职责配置；
- 发现多人候选、范围重叠和权限缺口；
- 汇总 Shadow 差异并解释风险；
- 生成等待管理员确认的配置建议。

AI 不可以：

- 自动指定审批人；
- 自动从多人候选中选一人；
- 自动授予 Role、Permission 或 Scope；
- 自动创建、修改或停用 Responsibility、PositionResponsibility、PositionWorkflowResponsibility 或 EmployeeReportingRelation；
- 自动把 Shadow 切到 ENFORCE；
- 用概率判断替代正式企业主数据。

AI 输出只能是 `ADVISORY_ONLY（仅建议）`。任何主数据变化必须由有权限管理员执行显式 Business Action、填写原因并形成审计。

---

## 16. 风险清单

| 优先级 | 风险 | 影响 | 实施前控制 |
|---|---|---|---|
| P0 | 三类责任事实当前均为 0 | Shadow 全部 unresolved，无法验证真实责任 | 由管理员维护；禁止自动 seed 正式数据 |
| P0 | 采购申请旧逻辑只有“采购经理”文本 | 无法稳定比较 Employee | 分类为 LEGACY_TEXT_ONLY，不伪造 MATCH |
| P0 | Workflow Runtime 不消费岗位流程责任 | 维护数据不影响任务 | 先 Shadow，后独立 Enforce 授权 |
| P0 | ApprovalTask 无 Evidence 字段 | 无法形成持久任务证明 | Shadow 后另行评审最小扩展 |
| P0 | 多岗位或多员工候选 | 责任不唯一 | 阻断并修配置，不自动选人 |
| P0 | Company/Department 上下文不可靠 | 跨公司错派 | 只读服务端对象；不接受客户端结论 |
| P1 | Responsibility 无 Company 字段 | 多公司语义可能混淆 | 确认全局语义目录 + 公司岗位分配 |
| P1 | `category` 字段语义未治理 | module ownership 不一致 | 实施前确认只承载 module code；冲突则停下评审 |
| P1 | PositionResponsibility 无有效期 | 历史责任无法重放 | 正式任务冻结 Evidence；V1 只解析当前事实 |
| P1 | Employee 单正式岗位 | 兼岗无法表达 | V1 不推断；必要时另行模型评审 |
| P1 | Employee 无 User | 无数字执行身份 | 专用错误并阻断 |
| P1 | 用 Permission 过滤多人候选 | 混淆责任与授权 | 先唯一责任、后单人权限校验 |
| P1 | Shadow 增加请求延迟 | 影响旧提交体验 | after-commit、超时、熔断、非阻塞 |
| P1 | Shadow 日志泄露人员或权限信息 | 安全与隐私风险 | 最小字段、权限隔离、脱敏和保留期 |
| P1 | ENFORCE 自动回退 Legacy | 掩盖配置失败、形成双事实 | 明确模式切换；请求内禁止静默 fallback |
| P2 | AI 建议被当作正式事实 | 未授权责任或权限变化 | ADVISORY_ONLY + 人工动作与审计 |

---

## 17. 实施前决策记录摘要

| 决策编号 | 决策 | 确认内容 | 人工状态 |
|---|---|---|---|
| ADR-RRE-001 | 职责编码 | 全局唯一、大写下划线、对象+责任目的、不含版本；允许停用但不删历史 | WAITING SIGN-OFF |
| ADR-RRE-002 | 多人候选 | 唯一 Employee 才能继续；多人阻断；配置修复优先；人工例外必须独立动作 | WAITING SIGN-OFF |
| ADR-RRE-003 | Evidence | 任务创建时保存为正式方案；执行时追加授权证据；Shadow 只记观察事件 | WAITING SIGN-OFF |
| ADR-RRE-004 | 采购 Shadow | 旧逻辑唯一生效；提交后只读解析；结构化差异；`SHADOW → OFF` 可即时回退 | WAITING SIGN-OFF |

人工签发以上四项只表示允许形成下一阶段实施计划，不自动授权代码、Migration、业务数据或采购审批改造。

---

## 18. 保护基线与本轮边界

设计前后只读复核：

```text
Database SHA256 Before = 9FC2A4B19716E84EB10F397BF94736CC69FFC6D1472C6FFB1849DD3A20036619
Database SHA256 After  = 9FC2A4B19716E84EB10F397BF94736CC69FFC6D1472C6FFB1849DD3A20036619
PurchaseOrder Before / After = 218 / 218
SupplierMaterialPrice Before / After = 28 / 28
Responsibility Before / After = 0 / 0
PositionResponsibility Before / After = 0 / 0
PositionWorkflowResponsibility Before / After = 0 / 0
```

本轮只读取文档、源码、数据库计数和哈希，并新增本设计报告。未运行 Migration、测试数据生成、采购动作、审批动作、浏览器保存或任何业务写入。数据库哈希与保护计数前后完全一致。

最终签发：

```text
PurchaseOrder（采购订单）= 218
SupplierMaterialPrice（供应商物料价格）= 28
Unauthorized Business Writes（未授权业务写入）= 0
```

---

## 19. 最终确认

PCE Responsibility Resolution Engine V1 的实施前架构结论如下：

```text
先由 Responsibility 决定谁应该负责
→ 再由 Permission 表达执行能力
→ 最后由 AuthorizationService 对当前执行作最终裁决
```

V1 应先建立只读、确定性、证据化的解析能力，再运行 Purchase Request Shadow Mode。Shadow 期间旧审批是唯一业务事实，新解析只能观察和比较。多人、无人、无账户或无权限均不得自动兜底。

现有组织与权限模型足以支持只读解析、权限预检和 Shadow；完整持久任务分派仍需对既有 ApprovalTask 的最小扩展进行独立审核。禁止新增平行责任模型或第二套权限体系。

最终状态：

```text
Architecture Supplement Design = PASS
Four Decisions = DOCUMENTED / HUMAN SIGN-OFF WAITING
Shadow Mode Plan = PASS
Implementation = NOT STARTED
Code Changed = NO
Database Changed = NO
Workflow Runtime Changed = NO
Permission Changed = NO
Purchase Approval Changed = NO
Business Data Changed = NO
Human Architecture Review = WAITING
```

本轮到此停止，等待人工架构审核。
