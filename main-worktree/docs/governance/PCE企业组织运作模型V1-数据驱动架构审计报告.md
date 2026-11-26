# PCE 企业组织运作模型 V1——数据驱动架构审计报告

报告日期：2026-08-17  
审计类型：Enterprise Organization Operating Model Data Driven Architecture Audit  
任务性质：只读架构审计；禁止业务代码、数据库和既有模型修改  
审计状态：AUDIT COMPLETE / REFACTOR DECISION REQUIRED

---

## 1. 审计目标

本轮检查 PCE 企业组织运作模型及其后续业务消费者是否遵守以下正式原则：

> **Enterprise Operation Data Driven Principle（企业运作数据驱动原则）**：企业组织、部门、岗位、员工、职责、责任和流程归属属于动态企业主数据。系统代码只提供模型、规则、校验和运行能力；企业实际组织关系必须由管理员维护的数据产生。

正确运行链应为：

```text
业务规则
→ 读取 Company / Department / Position / Employee 动态主数据
→ 读取 Responsibility / PositionResponsibility
→ 读取 EmployeeReportingRelation / PositionWorkflowResponsibility
→ 解析当前有效责任人
→ 生成运行结果和审计事实
```

本轮不新增功能，不修改 Department、Position、Employee、EmployeeReportingRelation、Workflow、Permission、PurchaseOrder 或 SupplierMaterialPrice，不修改任何业务代码或数据库。唯一新增文件为本审计报告。

---

## 2. 已读取规范与既有报告

### 2.1 开发治理规范

- `docs/standards/PCE-DEVELOPMENT-STANDARD-V1.0.md`
- `docs/standards/PCE-BUSINESS-ACTION-PERMISSION-V1.0.md`
- `docs/governance/01-开发治理总纲/PCE-ERP开发治理总纲.md`
- `docs/governance/02-架构与运行边界/PCE-ERP架构与运行边界规范.md`
- `docs/governance/Runtime职责规范.md`
- `docs/governance/Schema规范.md`
- `docs/governance/真实运行验收规范.md`

### 2.2 组织模型既有报告

- `docs/governance/PCE企业组织运作模型V1-实施与人工验收交接报告.md`
- `docs/governance/PCE企业组织运作模型V1-正式管理员入口统一与维护闭环整改报告.md`
- `docs/governance/PCE企业组织运作模型V1-员工直属主管维护闭环报告.md`
- `docs/governance/PCE企业组织运作模型V1-员工汇报关系语义优化报告.md`

规范共同边界：页面、API、Provider、Runtime、诊断与验收报告必须复用同一服务端事实；AuthorizationService 是统一授权入口；Position 不等于 Role；Runtime 不得成为数据库；历史缓存、演示数组和前端重算不能补造正式事实。

---

## 3. 审计方法与边界

### 3.1 检查范围

后端重点检查：

```text
backend/system/
backend/pfm/
backend/workflow_runtime/
backend/procurement/
backend/masterdata/
backend/supplier_performance/
```

前端重点检查：

```text
frontend/src/meta/components/
frontend/src/meta/pages/
frontend/src/meta/process/
frontend/src/meta/workflow/
frontend/src/meta/runtime/
frontend/src/meta/manufacturing/
frontend/src/platform/auth/
frontend/src/views/
frontend/src/router/
```

### 3.2 检查方法

- 按 Company、Department、Position、Employee、EmployeeReportingRelation、Responsibility、PositionResponsibility、PositionWorkflowResponsibility 追踪模型、写服务、读投影和消费者；
- 搜索固定公司 ID、固定部门/岗位名称、固定用户名/员工、固定审批人、前端角色判断和本地组织数组；
- 反查路由、导入和调用位置，区分生产可达代码、测试/验收夹具、管理命令和无引用历史文件；
- 对测试数据、状态枚举、权限编码和企业事实分别判定，避免把合法系统规则误报为企业事实硬编码；
- 仅执行源码读取、Git 状态读取、数据库只读计数和文件哈希，不执行测试、迁移、构建、服务写动作或浏览器保存动作。

### 3.3 分类规则

| 分类 | 含义 | 处置 |
|---|---|---|
| A | 已由正式模型、服务端查询和有效关系产生 | KEEP |
| B | 可接受的系统规则、状态枚举、权限编码或隔离测试夹具 | KEEP |
| C | 生产或未来正式运行可能消费的企业事实硬编码/重复事实/解析断点 | REFACTOR |
| D | 无引用、损坏、一次性初始化或演示历史代码 | DELETE CANDIDATE |

优先级：`P0` 为继续采购审批/流程责任开发前必须决策；`P1` 为进入供应商、绩效或经营分析正式化前必须治理；`P2` 为清理与隔离项。

---

## 4. 当前组织模型事实

### 4.1 真实开发库只读计数

```text
Company = 2
OrganizationUnit = 18
Department = 16
Position = 35
Employee = 104
EmployeeReportingRelation = 2
JobFamily = 0
JobLevel = 0
Responsibility = 0
PositionResponsibility = 0
PositionWorkflowResponsibility = 0
OrganizationLeadershipAssignment = 0
OrganizationOperatingAuditRecord = 12
PurchaseOrder = 218
SupplierMaterialPrice = 28
```

当前 `Responsibility`、`PositionResponsibility` 和 `PositionWorkflowResponsibility` 均为 0，因此现阶段不能用真实数据证明“流程节点已按职责解析到岗位再解析到员工”；只能证明维护模型和投影代码存在。

### 4.2 唯一正式组织事实链

| 业务事实 | 正式来源 | 当前结论 |
|---|---|---|
| 公司 | `system.Company` | 已数据驱动 |
| 组织单元 | `system.OrganizationUnit` | 已数据驱动 |
| 部门及上级部门 | `system.Department.parent` | 已数据驱动 |
| 部门责任岗位 | `system.Department.responsible_position` | 已数据驱动 |
| 部门实际负责人 | `pfm.OrganizationLeadershipAssignment` | 模型已存在，当前无数据 |
| 岗位及上级岗位 | `system.Position.parent_position` | 已数据驱动 |
| 员工正式部门/岗位 | `pfm.Employee.department_ref / position_ref` | 已数据驱动 |
| 员工直属/职能主管 | `pfm.EmployeeReportingRelation` | 已数据驱动，当前 2 条 |
| 职责目录 | `system.Responsibility` | 模型已存在，当前无数据 |
| 岗位职责 | `system.PositionResponsibility` | 模型已存在，当前无数据 |
| 岗位流程责任 | `system.PositionWorkflowResponsibility` | 模型已存在，当前无数据且尚未接入流程执行解析 |
| 组织变更审计 | `system.OrganizationOperatingAuditRecord` | 已数据驱动，当前 12 条 |

---

## 5. 数据驱动情况

### 5.1 A 类：已数据驱动，KEEP

1. `backend/system/enterprise_organization.py:40-141` 从当前用户 `company_id`、AuthorizationService 范围和正式 QuerySet 读取 Company、OrganizationUnit、Department、Position、Employee 与 EmployeeReportingRelation，没有按“采购部”“采购经理”推断组织关系。
2. `backend/system/models.py:75-148` 的 OrganizationUnit、Department 层级、组织单元和责任岗位均为外键事实；`backend/system/models.py:280-336` 的 Position 上级岗位、岗位族、岗位等级和默认 Role 均为模型关系。
3. `backend/pfm/models.py:94-129` 的 EmployeeReportingRelation 同时引用 Employee，区分 DIRECT/FUNCTIONAL，并以数据库约束限制单员工单类型 active primary 关系。
4. `backend/system/organization_operating.py:282-690` 的组织维护动作按当前用户公司查询，进行层级防环、员工自主管/汇报环、跨公司、有效期和权限校验，并写入 OrganizationOperatingAuditRecord。
5. `frontend/src/meta/pages/AccessControlFoundationPage.vue:208-217` 的正式 `#/organization` 页面通过服务端 API 刷新并回读；员工、部门、岗位和主管显示使用服务端投影。
6. `frontend/src/meta/components/EnterpriseOrganizationModelView.vue:94-116` 的综合模型展示使用相同服务端投影，没有在页面重新推导主管关系。

### 5.2 B 类：可接受系统规则，KEEP

1. `DIRECT / FUNCTIONAL`、`OWNER / APPROVER / REVIEWER / EXECUTOR`、启用/停用、有效期和状态转换属于模型枚举或运行规则，不是企业实际人员/岗位事实。
2. `backend/system/authorization.py:75-83` 的 Django superuser 特权位于统一 AuthorizationService 内，是系统管理规则；不得把该规则复制为页面 `if(role === "admin")`。
3. Permission code、Action code、Workflow code 和 Node code 可以是稳定系统标识；实际承担者必须由职责、岗位和员工关系解析。
4. `tests/`、验收 profile、迁移 seed 和明确的 canary 管理命令中的虚构公司/员工/部门可保留为隔离测试数据，前提是不能进入正式 Runtime、正式 API 返回或真实业务库自动初始化。
5. “采购部门”“直属主管”等字段标题只是业务语义标签，不等同于固定某个部门或人员。

### 5.3 总体判定

```text
Organization Master Maintenance = DATA DRIVEN
Employee Reporting Relation = DATA DRIVEN
Responsibility Storage = DATA DRIVEN BUT EMPTY
Workflow Responsibility Storage = DATA DRIVEN BUT NOT CONSUMED BY WORKFLOW RUNTIME
Procurement / Supplier / Legacy Foundation Consumers = MIXED, HARD-CODING RISKS PRESENT
Enterprise-wide Data Driven Closure = NOT PASS
```

---

## 6. 硬编码与架构风险发现

| 分类 | 优先级 | 位置 | 问题 | 影响 | 建议 |
|---|---|---|---|---|---|
| C / REFACTOR | P0 | `backend/procurement/purchase_request_api.py:70-81` | 提交采购申请时直接写入“采购经理审批”“采购经理”；批准动作以当前用户名或“采购经理”作为审批人，没有查询 Workflow Node、Responsibility、Position、Employee。 | 审批路由与企业岗位调整无关；名称相同不等于真实审批人；无法证明职责、权限和审计同一身份。 | 在后续专项中建立 `Workflow Node → Required Responsibility → PositionWorkflowResponsibility → Position → active Employee` 解析器；解析失败必须阻断，禁止名称兜底。 |
| C / REFACTOR | P0 | `backend/workflow_runtime/action_permissions.py:25-28,457-480` | 供应商应付和付款申请动作直接映射固定 role code；未消费 PositionWorkflowResponsibility。 | 组织管理员维护的岗位流程责任不会改变运行结果，形成“可维护但不生效”的假闭环。 | 将固定 role code 降为系统能力/权限要求；实际责任人从岗位流程责任解析，并继续由 AuthorizationService 校验动作权限。 |
| C / REFACTOR | P0 | `backend/workflow_runtime/models.py:115-130`、`backend/system/models.py:432-463` | ApprovalTask 使用 `required_role_code`，而岗位流程责任另存于 system 模型；全仓生产消费者只发现维护、展示和审计，未发现二者连接。 | Workflow 运行与企业组织事实分裂；未来流程责任开发可能继续建立第二条责任链。 | 先形成统一责任解析契约和同一业务 ID 证据，再开发审批执行；禁止新增第三套责任模型。 |
| C / REFACTOR | P0 | `frontend/src/meta/process/businessProcessRegistry.js:186-301` | 正式流程 owner 写死为“企业主数据管理员、产品工程负责人、采购经理、仓库主管、生产主管、质量经理、财务主管、运营经理”，并可持久化到 localStorage（322-339）。 | 流程设计中心展示的负责人不是组织主数据事实；浏览器本地状态可覆盖服务端组织责任。 | Registry 只保留流程/节点定义；owner 由服务端 PositionWorkflowResponsibility 投影，页面只读服务端事实。 |
| C / REFACTOR | P0 | `frontend/src/meta/workflow/approvalFlowConfigStore.js:5-17,40-82` | 采购申请、询价、核价、采购订单的审批步数和“审核员/复核员/审批员”在前端构造并保存 localStorage。 | 前端成为审批责任事实来源；刷新浏览器或换终端可能得到不同流程，无法形成审计闭环。 | 仅保留 UI 编辑器；配置、版本、有效期和责任引用必须由正式服务端 Workflow/Responsibility 数据提供。 |
| C / REFACTOR | P0 | `backend/procurement/views.py:130,190,752`、`backend/masterdata/views.py:772,826` | 供应商导入、采购订单创建/导入、物料分类/物料导入直接写 `company_id=1`。 | 多公司数据会被写入错误公司；违反 Company 主数据和数据范围隔离，且是真实写入口。 | 后续专项统一从已认证用户和服务端授权上下文解析 Company；拒绝客户端任意公司与常量兜底。 |
| C / REFACTOR | P0 | `frontend/src/views/SupplierList.vue:697`、`MaterialList.vue:687`、`MaterialCategoryList.vue:119`、`ShiftList.vue:74`、`PurchaseOrderList.vue:1340` | 旧页面提交载荷固定 `company_id: 1`。 | 即使后端修复，旧页面仍会提交错误公司事实；若路由或组件再次启用会污染跨公司数据。 | 确认路由可达性后迁移到服务端公司上下文；不可达页面进入删除候选，不得继续复用。 |
| C / REFACTOR | P0 | `backend/masterdata/enterprise_master_data.py:11-51`、`backend/masterdata/views.py:90-97`、`frontend/src/router/index.js:85-87` | `/master-data/organizations` 的正式服务端 API 返回代码中的“华东制造有限公司/苏州工厂/采购部/总装工作中心”静态数组；只有 material/supplier 被标记 canonical runtime。 | 系统同时存在 system.Company/OrganizationUnit/Department 和静态 EMD 组织事实，违反唯一事实来源。 | 组织主数据页面改为读取 EnterpriseOrganizationModelService；静态 organizations fixture 只允许移入测试目录。 |
| C / REFACTOR | P0 | `frontend/src/meta/manufacturing/manufacturingFoundationStore.js:78-109,124-127,173-180` | localStorage 默认状态内置部门、角色、员工、排班、角色权限和用户角色；正式路由仍有页面消费该 Store。 | 形成第二套 Employee/Department/Role 事实，且含虚构个人信息；与 `#/organization` 不一致。 | 员工/组织相关页面全部改读正式服务端事实；样例工厂移入隔离 fixture。现有 `/foundation/pfm/employees` 重定向正确，但 create/detail/skills/certificates/shifts 路由仍需审计清理。 |
| C / REFACTOR | P1 | `backend/procurement/scm_runtime_services.py:177-181,399-403` | 采购员资格通过 legacy `Employee.position__contains="采购"` 判断。 | 岗位改名、非中文岗位、临时代理或职责配置均会误判；没有读取 PositionResponsibility。 | 采购资格改为 required Responsibility 或受治理权限 + 正式 Position/Employee 关系，不以岗位名称包含词判断。 |
| C / REFACTOR | P1 | `frontend/src/meta/pages/ScmPurchaseOrderCreateEntryPage.vue:179`、`ScmAgreedPricePurchaseConfirmationPage.vue:99` | 前端再次用 `position.includes('采购')` 过滤采购员候选。 | 页面与服务端重复计算企业资格；可能隐藏服务端允许的员工或展示不应选择的员工。 | 候选由服务端责任解析接口返回；前端不按岗位文案过滤。 |
| C / REFACTOR | P1 | `backend/procurement/serializers.py:353-377` | 申请人与部门校验兼容 legacy department ID/name，并以部门名称是否包含“采购”判断“标准采购组织”。 | 部门改名或多语言后规则失效；字符串回退可能掩盖正式 Department 关系缺失。 | 以正式 Department ID 和配置化组织职责判断；legacy 字符串只作历史显示，不得参与新决策。 |
| C / REFACTOR | P1 | `backend/procurement/scm_runtime_services.py:282-287` | 直接采购创建申请时写死“直接采购授权”“采购部”“直接采购需求”“高管直接采购授权”。 | 新生成采购申请的组织归属和审批事实不是管理员维护数据。 | 从发起 Employee、Department、授权责任和 Workflow Node 获取；不存在正式映射时阻断创建。 |
| C / REFACTOR | P1 | `backend/procurement/models.py:56-59,106-108,604-608`、`backend/procurement/scm_runtime_services.py:828-830,1100-1102` | PurchaseRequest 保留申请人/部门/采购部门/审批人为字符串；PurchaseOrder 虽有 buyer_employee，但部分路径仍只写 buyer/confirmedBy 字符串。 | 人员改名、离职、跨公司或同名时无法稳定追踪 Employee；绩效与责任分析可能按文本聚合错误。 | 新写链强制正式 Employee/Department FK；字符串仅保存不可变显示快照，不能作为责任解析键。 |
| C / REFACTOR | P1 | `backend/supplier_performance/models.py:36-40,118-123` | 采购员绩效和对账差异以 CharField buyer_id/buyer_name 保存，没有 Employee FK。 | 绩效对象无法与 Employee、Position、ReportingRelation 稳定关联；同名、改名和跨公司存在混算风险。 | 正式绩效设计前建立 Employee 外键和来源业务对象链；历史文本保留为快照而非身份。 |
| C / REFACTOR | P1 | `backend/supplier_performance/services.py:389-564,651-762` | 生产 service 模块包含固定租户、月份、供应商、BUYER-001/BUYER-002、张敏/李强和固定 canary 用户的数据生成函数。 | 管理命令误运行可能把演示企业事实写入当前库；绩效/供应商责任容易被样例数据冒充正式事实。 | 将 demo generator 移至 tests/fixtures 或专用 canary app，并在设置层硬隔离生产数据库。 |
| C / REFACTOR | P1 | `frontend/src/platform/auth/permissionV12.js:8-38` | 固定 `user={id:1, role:'admin', dept:'purchase'}`，并以 `if (user.role === 'admin')` 放行；该模块通过 metaKernelV12 → metaKernelV13 → metaOSKernel/AI 路径仍有消费者。 | 绕开 AuthorizationService 和服务端 Scope；任何复用都可能得到伪造 ALL 权限。 | 立即列入权限架构专项；生产路径只消费服务端 Permission Profile，前端判断只控制展示。 |
| C / REFACTOR | P1 | `backend/system/models.py:394-403`、`backend/system/enterprise_organization.py:366` | Responsibility 没有 Company 归属，综合模型向公司用户返回全局职责目录。 | 若职责是企业自定义主数据，多公司之间会共享/泄漏职责；当前 0 条数据尚未暴露问题。 | 在录入职责前明确“全局模板”或“公司主数据”语义；若属公司事实，后续专项增加公司范围及授权过滤。 |
| D / DELETE CANDIDATE | P2 | `backend/system/init_permissions.py:3-95` | 无正式导入消费者的一次性脚本固定业务角色、admin 用户、`company_id=1` 和默认密码；init_menus 仅打印提示引用。 | 人工误执行会创建固定企业事实和弱口令管理员。 | 归档或删除；如确需初始化，改为受治理管理命令并禁止默认密码/固定公司。 |
| D / DELETE CANDIDATE | P2 | `frontend/src/platform/auth/permissionV18.js:8-42` | 未发现生产 import，内容为固定 admin/purchase 的旧权限引擎。 | 容易被未来开发误引用，重新引入前端授权旁路。 | 删除或移入明确的历史归档，不得作为模板复用。 |
| D / DELETE CANDIDATE | P2 | `backend/procurement/views.py.broken` | 损坏的历史视图副本仍位于源码目录，并含固定人员/旧逻辑。 | 静态扫描噪声和误复制风险。 | 删除或移出源代码树。 |
| D / DELETE CANDIDATE | P2 | `backend/generate_orders_standalone.py`、`backend/import_materials_from_excel.py` | 独立脚本固定张三/李四/王五或 `company_id=1`，未发现正式调用链。 | 人工执行可能污染真实业务数据。 | 删除、归档或加独立测试库硬门禁；不得连接正式数据库。 |

### 6.1 未判为硬编码的问题

- `Department.DepartmentType.PRODUCTION` 是类型枚举，不是把“生产部”固定为某个 Department；
- `superadmin` 位于 AuthorizationService 内的系统管理员语义属于系统规则；前端自行判断 `admin` 则不属于可接受规则；
- 测试文件中的采购部、采购经理、固定 ID 和虚构人员属于隔离测试夹具；只有当它们被正式 Runtime/API 导入或写入真实库时才升级为 C；
- 页面字段名“采购部门”“负责人”“直属主管”是显示语义，本身不构成企业事实。

---

## 7. 重点未来风险

### 7.1 供应商管理风险

- 尚未发现统一的“供应商负责人 → Employee”正式关系；现有绩效/差异对象主要以 buyer_id/buyer_name 字符串连接；
- 制造基础 Store 和 supplier performance demo 中存在固定负责人/采购员；
- 正式供应商负责人设计必须引用 Employee，并通过 PositionResponsibility 或专门、唯一且受审计的供应商责任分配关系产生，不能引用 User、岗位名称或自由文本。

### 7.2 采购审批风险

- 当前采购申请提交直接进入“采购经理审批”，不是动态职责解析；
- Workflow Runtime 的固定 role code 与 PositionWorkflowResponsibility 未连接；
- 在该断点解决前继续扩展采购审批，会把当前硬编码固化为新的流程基础设施。

### 7.3 绩效风险

- BuyerPerformanceMetric 使用字符串身份，示例数据固定 BUYER-001/BUYER-002；
- 评价人、被评价人、直属/职能主管和责任岗位尚未形成同一 Employee 身份链；
- 后续绩效评价关系必须按有效期读取 EmployeeReportingRelation、PositionResponsibility 和业务对象归属，不得按姓名或岗位名称推断。

### 7.4 成本与经营分析风险

- 固定 `company_id=1` 会直接造成跨公司成本、订单和供应商数据归属错误；
- PurchaseRequest 和部分历史对象仍保存部门字符串，无法稳定连接 Department 层级；
- 经营分析必须使用业务发生时的 Company/Department/Position/Employee ID 与快照，禁止通过“采购部”“生产部”等名称归类。

---

## 8. 后续开发强制约束

### 8.1 动态主数据边界

以下对象全部作为动态企业主数据：

```text
Organization
Department
Position
Employee
Responsibility
PositionResponsibility
EmployeeReportingRelation
PositionWorkflowResponsibility
```

代码允许固定：模型类型、状态机、权限编码、动作编码、流程/节点稳定编码和校验算法。代码禁止固定：企业实际公司、部门、岗位、员工、负责人、审批人、评价关系及供应商责任人。

### 8.2 责任解析契约

后续流程责任统一按以下顺序：

```text
Workflow Code + Node Code + Ownership Type
→ active/effective PositionWorkflowResponsibility
→ optional required Responsibility
→ active Position / PositionResponsibility
→ active Employee.position_ref
→ Company / Department Scope
→ AuthorizationService action permission
→ resolved Employee candidate(s) + evidence IDs
```

解析结果必须返回关系 ID、岗位 ID、Employee ID、有效期和来源版本；零人、多人的处理规则必须显式配置。禁止用户名、岗位名称、部门名称和前端 role code 兜底。

### 8.3 单一事实与失败策略

- `#/organization` 与 `#/organization-model` 继续读取 EnterpriseOrganizationModelService；
- `/master-data/organizations` 不得继续返回静态组织数组；
- localStorage 只能保存 UI 偏好，不得保存组织、权限、流程责任或审批配置；
- 正式关系缺失时必须返回 `read_failed / responsibility_unresolved` 并阻断业务动作，不能回退到“采购经理”或 `company_id=1`；
- 页面候选列表由服务端返回，不得通过 `position.includes('采购')` 等字符串规则筛选；
- 审计必须保存解析前提、关系来源和最终 Employee 身份。

---

## 9. 后续开发建议

### 9.1 岗位职责体系

先明确 Responsibility 是全局模板还是 Company 级主数据；建立有效期、公司范围和唯一性规则。业务能力只引用责任编码/ID，不引用岗位名称。

### 9.2 流程责任体系

优先建设只读责任解析服务和证据契约，再接入 Workflow Runtime。现有 PositionWorkflowResponsibility 必须成为唯一岗位流程责任来源，不新增平行映射表。

### 9.3 供应商管理

供应商负责人必须引用 Employee；如需主责/协同、品类或区域范围，应在单一责任分配模型中显式表达有效期和范围，并产生审计。

### 9.4 采购审批

采购申请不得固定“采购经理”。节点只声明 Required Responsibility；服务端按 Company、Department、Position 和 Employee 解析审批人，再由 AuthorizationService 校验实际动作权限。

### 9.5 绩效体系

评价人与被评价人统一使用 Employee ID；主管评价读取 EmployeeReportingRelation，职责评价读取 PositionResponsibility，流程表现读取真实业务任务和 PositionWorkflowResponsibility。姓名只作快照显示。

### 9.6 经营分析

所有事实表保留 Company、Department、Position、Employee 的稳定 ID 和发生时快照；分析维度从主数据层级读取，禁止按中文名称、字符串包含或固定公司 ID 归类。

### 9.7 建议实施顺序

```text
P0-1 统一 Company 上下文并封堵 company_id=1 正式写入口
P0-2 统一 Organization/Employee 页面事实，隔离静态 EMD 与 localStorage 副本
P0-3 建立 PositionWorkflowResponsibility 只读解析契约
P0-4 让采购申请/Workflow Runtime 消费责任解析结果
P1-1 将采购员资格从岗位名称改为 Responsibility
P1-2 将供应商负责人、绩效采购员和采购对象连接正式 Employee
P1-3 清理前端本地权限/审批配置
P2   删除或隔离历史脚本、broken 文件和 canary/demo generator
```

---

## 10. 保护基线与零写入证明

审计前后真实数据库复核：

```text
Database SHA256 Before = 9FC2A4B19716E84EB10F397BF94736CC69FFC6D1472C6FFB1849DD3A20036619
Database SHA256 After  = 9FC2A4B19716E84EB10F397BF94736CC69FFC6D1472C6FFB1849DD3A20036619
PurchaseOrder Before / After = 218 / 218
SupplierMaterialPrice Before / After = 28 / 28
```

本轮只执行读取、搜索、哈希和 ORM `.count()`；未执行 POST、管理命令、迁移、测试数据生成、采购动作或浏览器保存。数据库前后哈希完全一致，两项保护计数完全一致。

```text
PurchaseOrder Added = 0
SupplierMaterialPrice Added = 0
Unauthorized Business Writes = 0
```

---

## 11. 最终结论

PCE 企业组织运作模型 V1 的正式维护核心已经建立数据驱动基础：组织、部门、岗位、员工、员工汇报关系、岗位职责和岗位流程责任都有正式模型、受控维护入口、服务端查询与审计边界。

但企业级闭环尚未完成。当前主要问题不是缺少模型，而是外围业务仍存在第二事实源和运行消费断点：固定公司 ID、静态组织/员工数组、按岗位/部门名称判断、固定采购经理审批、固定前端流程 owner、localStorage 审批配置，以及 Workflow Runtime 未消费 PositionWorkflowResponsibility。

最终状态：

```text
Audit = PASS
Risk Inventory = COMPLETE
Core Organization Maintenance Data Driven = PASS
Employee Reporting Data Driven = PASS
Responsibility Data Prepared = PASS / NO REAL DATA
Workflow Responsibility Runtime Consumption = FAIL
Enterprise-wide Data Driven Closure = FAIL / REFACTOR DECISION REQUIRED
Business Code Changed = NO
Database Changed = NO
PurchaseOrder = 218
SupplierMaterialPrice = 28
Unauthorized Business Writes = 0
Human Architecture Review = WAITING
```

本轮到此停止，不实施任何整改。下一步等待人工架构审核和统一重构优先级决策。
