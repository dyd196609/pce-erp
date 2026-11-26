# PCE Enterprise Organization Model V1 实施报告

## 0. 文档信息与结论

- 建设对象：PCE Enterprise Organization Model V1（PCE 企业组织经营模型第一版）
- 实施日期：2026-08-16
- 实施范围：组织层级、部门体系、岗位体系、员工组织关系、岗位职责、流程责任接口、成本中心关系、利润中心关系预留
- 实施状态：`IMPLEMENTED / REVIEW PENDING（已实施，等待审核）`
- 专项自动测试：`PASS（通过）`
- Browser Automatic Acceptance（浏览器自动验收）：`PASS（通过）`
- Real Browser Evidence（真实浏览器证据）：`PASS（通过）`
- Human Acceptance（人工验收）：`WAITING FOR HUMAN REVIEW（等待人工审核）`
- Full Project Build（全项目构建）：`BLOCKED BY EXISTING SCM STATIC GATES（被既有 SCM 静态门禁阻断）`
- Ready Gate（就绪门禁）：`FAIL（尚未满足）`

本轮没有把新的组织经营模型直接封为正式基线。原因不是专项实现失败，而是人工审核尚未签发，且全项目构建仍被任务开始前已存在的 7 项 SCM 静态门禁阻断。本报告严格区分专项测试、真实浏览器证据、人工签发和全项目构建状态。

---

## 1. 当前架构

### 1.1 治理读取与冲突检查

实施前已读取并按以下优先级执行：

1. PCE-ERP 开发治理体系；
2. 架构与运行边界；
3. Schema、Runtime、Workflow、Permission 规范；
4. PCE 公共组织身份权限核心 V1 的实施、架构调整和最终封板材料；
5. SCM 专项治理、采购业务主数据引用治理、Enterprise Process Operating System 和 Enterprise OS UI Model；
6. 本轮 Enterprise Organization Model V1 指令。

本轮设计未发现必须中止的公共架构冲突。组织经营模型继续复用既有统一身份与权限事实，不建立第二套用户、角色、权限、部门或岗位运行时。

### 1.2 既有正式主链

本轮开始前的正式主链保持为：

```text
system.User
  -> pfm.Employee
  -> system.Company / system.Department / system.Position

system.User
  -> system.Role
  -> system.Permission
  -> AuthorizationService
  -> Permission Profile
```

本轮在其上增加经营组织关系，不替换既有实体：

```text
Company
  -> OrganizationUnit
      -> Department
          -> Employee / Position

Position
  -> JobFamily / JobLevel / Parent Position
  -> DefaultRole -> Permission
  -> PositionResponsibility -> Responsibility
  -> PositionWorkflowResponsibility

Employee
  -> EmployeeReportingRelation
  -> OrganizationLeadershipAssignment
```

### 1.3 权限运行边界

三个新页面和一个新 API 复用已封板权限动作：

```text
system.organization_directory.view
```

服务端仍由 `AuthorizationService` 作出 `ALLOW / DENY` 和数据范围决策。前端只展示服务端 Permission Profile 与服务端组织事实，不缓存上一页事实、不重新计算权限、不创建平行 Permission Engine。

`DEPARTMENT` Scope 下，OrganizationUnit、Department、Position、Employee、负责人、汇报关系和流程职责投影都按服务端已授权部门收敛；手工输入页面 URL 不能扩大服务端数据范围。

---

## 2. 新增内容

### 2.1 新增正式模型

`system` 域新增：

- `OrganizationUnit`：支持 `COMPANY / BUSINESS_UNIT / CENTER / DEPARTMENT / TEAM`，包含父组织、所属公司、状态、生效和失效日期；
- `CostCenter`：成本中心主数据基础；
- `ProfitCenter`：利润中心关系预留，不包含利润计算；
- `JobFamily`：岗位族；
- `JobLevel`：岗位等级；
- `Responsibility`：可复用岗位职责；
- `PositionResponsibility`：岗位与职责的多对多映射及主责标记；
- `PositionWorkflowResponsibility`：岗位与流程/节点责任的接口模型，不执行流程、不绑定具体人员。

`pfm` 域新增：

- `EmployeeReportingRelation`：员工与直属/职能主管关系，禁止员工自指，限制每类有效主汇报关系唯一；
- `OrganizationLeadershipAssignment`：员工担任 OrganizationUnit 或 Department 负责人的正式关系，一条记录只能指向一种组织对象。

### 2.2 既有模型增强

`Department` 保留原身份和层级关系，并增加：

- `department_type`；
- `organization_unit`；
- `cost_center`；
- `effective_from / effective_to`。

负责人没有以临时字段写入 Department，而是通过 `OrganizationLeadershipAssignment` 表达，从而避免污染部门主表并支持未来的有效期治理。

`Position` 保留正式岗位身份，并增加：

- `job_family`；
- `job_level`；
- `parent_position`；
- `default_role`；
- `description`；
- `responsibility_summary`。

`default_role` 只是岗位默认角色入口，Role 与 Permission 仍是独立正式实体。

### 2.3 服务端投影

新增 `EnterpriseOrganizationModelService`，输出统一契约：

```text
PCE-ENTERPRISE-ORGANIZATION-MODEL-V1
```

投影内容包括：

- 组织单元及父子关系；
- 部门及经营属性；
- 岗位族、岗位等级、岗位上级、默认角色；
- 岗位职责和流程责任接口；
- 员工归属、汇报关系、组织负责人；
- 成本中心与利润中心关系；
- Permission Profile 范围事实；
- `strictFacts` 写入与流程执行计数。

### 2.4 数据迁移

迁移 `system.0006_enterprise_organization_model_v1` 将正式库中既有 2 个 Company 和 16 个 Department 投影为 18 个 OrganizationUnit，并把 16 个 Department 连接到对应 OrganizationUnit。

该迁移只从既有正式 Company/Department 事实派生组织层级，没有猜测或生成部门负责人、成本中心、岗位族、岗位等级、岗位职责、汇报关系或流程责任数据。

---

## 3. 保留内容

以下既有资产未重构、未替换：

- `system.User`；
- `system.Company`；
- `system.Department`；
- `system.Position`；
- `pfm.Employee`；
- `system.Role`；
- `system.Permission`；
- `AuthorizationService`；
- Permission Profile；
- `PurchaseOrder`；
- `SupplierMaterialPrice`；
- `PurchaseOrderGate`。

明确保持的边界：

- Position 不等于 Role；
- Role 不等于 Permission；
- Department 不等于 Scope；
- OrganizationUnit 不取代 Company 或 Department；
- Responsibility 不直接绑定具体员工；
- 流程责任接口不执行审批、不推进业务状态；
- ProfitCenter 只预留关系，不计算利润；
- CostCenter 只建立归属基础，不执行财务核算；
- AI 仅可在未来读取并分析，不得自动修改组织；
- Delegate 只保留未来扩展边界，本轮没有建立代理审批执行链。

本轮没有扩展薪资、招聘、培训、人事档案、考勤、完整绩效、完整成本核算、利润分析或复杂代理审批。

---

## 4. 数据模型

### 4.1 组织层级

```text
Company
  1 -> N OrganizationUnit

OrganizationUnit
  0..1 -> Parent OrganizationUnit
  0..N -> Child OrganizationUnit
  0..1 -> ProfitCenter

Department
  0..1 -> Parent Department
  0..1 -> OrganizationUnit
  0..1 -> CostCenter
```

OrganizationUnit 类型已经具备公司、事业部、中心、部门和团队的 V1 扩展能力。当前正式数据仅投影已有 Company 与 Department，未凭空创建事业部、中心或团队。

### 4.2 岗位体系

```text
Position
  0..1 -> JobFamily
  0..1 -> JobLevel
  0..1 -> Parent Position
  0..1 -> Default Role

Position
  N <-> N Responsibility
      via PositionResponsibility
```

岗位层级使用自关联 `parent_position`。岗位职责使用独立 Responsibility 主数据和映射表，不把职责文本固化为人员属性。

### 4.3 岗位、角色与权限

正式关系为：

```text
Position -> DefaultRole -> RolePermission -> Permission
```

该链只表示默认职责角色建议入口，不意味着岗位自动覆盖用户角色，也不允许绕过已有 RoleAssignment 与 AuthorizationService。

### 4.4 员工汇报与负责人

```text
Employee -> EmployeeReportingRelation -> Manager Employee

Employee -> OrganizationLeadershipAssignment
         -> OrganizationUnit xor Department
```

直属主管、职能主管、部门负责人和组织负责人可以独立表达。正式数据没有可靠来源时保持空值，不以员工名称、岗位名称或页面推断负责人。

### 4.5 流程责任

```text
workflow_code + node_code
  -> PositionWorkflowResponsibility
  -> Position
```

映射支持责任类型 `OWNER / APPROVER / REVIEWER / EXECUTOR`，但该模型只是未来 Workflow Resolver 的查询接口。本轮不会据此自动寻找人员、执行审批或改变任何采购/付款状态。

---

## 5. 页面

新增三个真实路由页面：

| 页面 | 路由 | 页面编码 |
| --- | --- | --- |
| 企业组织经营模型 | `/organization-model` | `enterprise-organization-model-v1` |
| 部门体系 | `/organization-model/departments` | `enterprise-department-model-v1` |
| 岗位与职责体系 | `/organization-model/positions` | `enterprise-position-model-v1` |

三个页面共同遵循：

- 复用 `PceListPageShell` 页面壳；
- 复用 `PCE-ENTERPRISE-LIST-CONTRACT-V1.1`；
- 复用 `PceEnterpriseListTable`；
- 复用 `PceEnterpriseAdvancedFilter`；
- 复用 `PceBusinessStatus`；
- 由服务端 Permission Profile 与组织模型 API 提供事实；
- 页面只显示服务端 `statusLabel`；
- 列表横向滚动所有权属于表格内部；
- 页面为低风险只读入口，没有新增、修改、删除、审批或采购业务动作。

页面展示内容：

- 组织页面：组织树、组织单元列表、员工组织归属、汇报关系证据；
- 部门页面：部门树、部门类型、组织单元、负责人、成本中心、员工/岗位数量；
- 岗位页面：岗位树、岗位族、等级、上级岗位、默认角色、职责和流程责任接口。

对于正式库尚无数据的经营属性，页面明确显示“待维护”或 0，不使用前端猜测补齐。

---

## 6. API

新增只读 API：

```text
GET /api/access-control/enterprise-organization-model/
```

请求链：

```text
Authenticated User
  -> AuthorizationService
  -> system.organization_directory.view
  -> Permission Profile / Scope
  -> EnterpriseOrganizationModelService
  -> scope-aware server facts
```

行为：

- 无业务动作权限：服务端返回 403；
- `DEPARTMENT` Scope：只返回授权部门及相关组织、岗位、员工和责任事实；
- `ALL` Scope：返回所有可见正式组织事实；
- 前端手工输入 URL 不改变 API 授权结果；
- API 不提供写入方法，不执行组织变更、权限变更、流程推进或采购写入。

---

## 7. 测试结果

### 7.1 Django 系统检查与迁移检查

- `manage.py check`：`PASS`，0 issues；
- `makemigrations --check --dry-run`：`PASS`，No changes detected；
- `system.0006` 与 `pfm.0003`：已成功应用。

### 7.2 组织模型与权限专项自动测试

命令范围：

```text
system.tests_enterprise_organization_model_v1
system.tests_organization_access_core_v1
```

最终结果：

```text
Ran 12 tests in 0.585s
OK
System check identified no issues (0 silenced).
```

覆盖：

- 四级组织层级；
- Department 与 OrganizationUnit、CostCenter 关系；
- JobFamily、JobLevel、Position 上级关系；
- Position、DefaultRole、Permission 分离；
- Responsibility 与 PositionResponsibility；
- PositionWorkflowResponsibility；
- EmployeeReportingRelation；
- OrganizationLeadershipAssignment；
- `DEPARTMENT` Scope 收敛；
- Permission Profile/AuthorizationService 回归；
- PurchaseOrder 与 SupplierMaterialPrice 零写入。

### 7.3 采购保护回归

采购 R5.1 保护回归：

```text
Ran 4 tests
OK
```

未修复、未调整、未绕开任何 SCM 历史静态门禁。

### 7.4 前端专项构建

直接 Vite 生产构建：

```text
2538 modules transformed
built in 2.56s
exit code 0
```

构建仍有既有依赖纯注释、动态导入和大分块警告；这些是 warning，不影响本次 Vite 构建退出码。

### 7.5 全项目构建

`Full npm run build` 不能标记为 PASS。真实结果为：

```text
PCE-WEB-ACCEPTANCE-V1.1
1154 / 1161 assertions passed
allowBuild = false
```

阻断来自任务开始前已存在的 7 项 SCM 静态门禁：

1. `purchase-inquiry` quick search fields；
2. `purchase-inquiry` advanced filter not placeholder；
3. `purchase-inquiry-acceptance` quick search fields；
4. `purchase-inquiry-acceptance` advanced filter not placeholder；
5. `supplier-performance` advanced filter count；
6. `buyer-performance` advanced filter count；
7. `buyer-exception-analysis` advanced filter count。

本轮遵照指令停止在此，没有修复这 7 项历史门禁。

---

## 8. 采购影响

最终正式库计数：

| 对象 | 本轮前 | 本轮后 | 本轮新增 |
| --- | ---: | ---: | ---: |
| PurchaseOrder | 218 | 218 | 0 |
| SupplierMaterialPrice | 28 | 28 | 0 |

采购保护结论：

- 未创建采购订单；
- 未新增或修改 SupplierMaterialPrice；
- 未推进采购审批；
- 未修改 PurchaseOrderGate；
- 未执行采购、付款、银行发送或财务状态迁移；
- 未进入供应商管理或采购后续开发；
- 组织模型 API 与页面均为只读。

`strictFacts` 与最终数据库查询共同确认：

```text
purchaseOrderWriteCount = 0
supplierMaterialPriceWriteCount = 0
purchaseOrderGateWriteCount = 0
workflowExecutionCount = 0
unauthorizedBusinessWriteCount = 0
```

---

## 9. 数据库变化

### 9.1 迁移文件

- `backend/system/migrations/0006_enterprise_organization_model_v1.py`；
- `backend/pfm/migrations/0003_enterprise_organization_model_v1.py`。

### 9.2 正式数据变化

迁移前已创建数据库备份：

```text
D:\Dev-PCE\Source\backend\db.pre-enterprise-organization-model-v1-20260816.sqlite3
Length: 2506752 bytes
SHA256: 3AC50ADDA8F36D0D4096CD65C697C2E18309433F2E8CF48A85DE29D150048053
```

本轮授权的数据迁移：

- 从既有 Company 创建 OrganizationUnit：2 条；
- 从既有 Department 创建 OrganizationUnit：16 条；
- 把既有 Department 关联到对应 OrganizationUnit：16 条更新；
- 授权组织主数据行操作合计：34；
- 未授权业务写入：0。

最终正式库事实：

| 对象 | 数量 |
| --- | ---: |
| Company | 2 |
| OrganizationUnit | 18 |
| Department | 16 |
| 已关联 OrganizationUnit 的 Department | 16 |
| Position | 35 |
| Employee | 104 |
| CostCenter | 0 |
| ProfitCenter | 0 |
| JobFamily | 0 |
| JobLevel | 0 |
| Responsibility | 0 |
| PositionResponsibility | 0 |
| PositionWorkflowResponsibility | 0 |
| EmployeeReportingRelation | 0 |
| OrganizationLeadershipAssignment | 0 |

后九项为 0 是正确正式事实：现有库没有经确认的来源，本轮拒绝为负责人、职责、岗位族级、成本中心、利润中心和汇报关系制造数据。隔离自动测试已验证这些正向关系在模型与 API 中可工作。

---

## 10. 人工验收结果

### 10.1 真实浏览器执行记录

真实浏览器使用当前已登录的 `DEPARTMENT` Scope 专用权限账户，逐页打开并刷新：

1. `/organization-model`；
2. `/organization-model/departments`；
3. `/organization-model/positions`。

真实可见结果：

- 页面明确显示当前角色、`DEPARTMENT` Scope、`ALLOW`、`AuthorizationService / Server`；
- 组织页面只显示 2 个可见组织单元、1 个授权部门、2 个相关岗位和 20 名相关员工；
- 部门树只显示授权的采购部；
- 岗位树只显示授权部门内的采购员和采购经理；
- 员工组织归属来自服务端正式 Employee/Department/Position 关系；
- 未维护的直属主管、部门负责人、成本中心、岗位族级和职责均显示“待维护”；
- 流程责任区显示接口已建立、正式映射为 0，没有把接口存在误写为已存在审批责任数据；
- 三页刷新后业务写入计数保持 0；
- 页面根容器没有额外横向溢出，横向滚动仍由表格内部拥有；
- 浏览器 Console error 数量为 0。

证据文件：

- `frontend/test-results/pce-enterprise-organization-model-v1/EOM-V1-01-organization-hierarchy.png`；
- `frontend/test-results/pce-enterprise-organization-model-v1/EOM-V1-02-department-hierarchy.png`；
- `frontend/test-results/pce-enterprise-organization-model-v1/EOM-V1-03-position-responsibility.png`。

### 10.2 验收状态分层

依据真实运行验收治理，Codex 控制真实浏览器得到的是 Browser Automatic Acceptance 和 Real Browser Evidence，不替代最终人工签字。因此状态为：

| 验收层 | 状态 |
| --- | --- |
| Automatic Acceptance（专项自动验收） | PASS |
| Browser Automatic Acceptance | PASS |
| Real Browser Evidence | PASS |
| Human Acceptance | WAITING FOR HUMAN REVIEW |
| Full Project Build | BLOCKED BY EXISTING SCM STATIC GATES |
| Ready Gate | FAIL |

等待审核人核对本报告和三张证据截图后，才能决定是否签发 Human Acceptance；在此之前不得把 Enterprise Organization Model V1 标记为 BASELINE 或 READY。

---

## 11. 后续扩展建议

以下仅为后续独立指令候选，不在本轮继续开发：

1. 经业务负责人确认后，导入正式 JobFamily、JobLevel、Responsibility、CostCenter 和负责人数据；
2. 为组织主数据维护建立独立写权限、审批、审计和有效期流程，禁止复用只读目录权限；
3. 由 Workflow 域建立 Resolver，按 `workflow_code + node_code + Position` 查找候选人员；在正式治理完成前不得自动推进流程；
4. 在独立版本中设计 Delegate 的有效期、委托范围、冲突检测和审计，不把代理等同于权限复制；
5. ProfitCenter 在财务治理完成后再接经营分析，本轮模型不承担利润计算；
6. AI 只接只读分析接口，输出建议和异常提示；任何组织、岗位、权限或负责人变更必须由人工确认并走正式写入流程；
7. SCM 7 项历史静态门禁等待新的独立指令处理，本轮不进入该专项。

---

## 12. 最终停止声明

PCE Enterprise Organization Model V1 的本轮实现、迁移、专项测试、采购保护检查、真实浏览器证据和报告已经完成。

最终记录：

```text
PCE Enterprise Organization Model V1 = IMPLEMENTED / REVIEW PENDING
Specialized Automatic Tests = PASS
Browser Automatic Acceptance = PASS
Real Browser Evidence = PASS
Human Acceptance = WAITING FOR HUMAN REVIEW
Full Project Build = BLOCKED BY EXISTING SCM STATIC GATES
Ready Gate = FAIL
PurchaseOrder = 218 -> 218, Added = 0
SupplierMaterialPrice = 28 -> 28, Added = 0
Unauthorized Business Writes = 0
```

现按指令停止，不进入 SCM 静态门禁、供应商管理、采购后续开发、复杂代理审批、完整 HR、利润分析或 AI 自动组织优化，等待人工审核。

---

## 13. 后续治理变更记录：经营中心设计取消

2026-08-16，后续正式版本 `PCE Enterprise Organization Operating Model V1` 调整本报告第 2、3、4、7、9、11 节中关于 `system.CostCenter`、`system.ProfitCenter` 及其关系预留的结论。

正式原则变更为：

> **本阶段取消成本中心、利润中心及其它经营中心设计。经营核算、绩效、成本、收入、费用、利润、投资回报等内容，待 PCE-ERP 管理运作体系及主要业务系统完成、产生真实业务数据后，再单独设计。**

引用审计确认：上一轮新增的 `system.CostCenter`、`system.ProfitCenter` 数据量均为 0，关系引用均为 0，没有 API、Service、Runtime、页面或 Workflow 的外部正式消费者，仅被上一轮预留实现及测试引用。因此后续迁移 `system.0007_remove_department_cost_center_and_more` 按 Django 正式迁移历史删除这两个预留模型及投影；历史迁移 `system.0006_enterprise_organization_model_v1` 保留不动。

采购域现有 `masterdata.CostCenter` 是不同的历史正式对象，具有 PurchaseRequest、Project、Provider、API、页面、测试和静态门禁消费者；后续版本将其分类为 `TEMPORARY LEGACY（暂时历史兼容）`，不删除、不迁移、不扩大使用。本治理变更不回写采购事实，也不代表已经完成未来经营核算设计。
