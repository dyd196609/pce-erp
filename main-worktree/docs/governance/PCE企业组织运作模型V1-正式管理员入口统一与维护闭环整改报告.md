# PCE 企业组织运作模型 V1——正式管理员入口统一与维护闭环整改报告

报告日期：2026-08-16  
整改类型：ADMIN ENTRY UNIFICATION & MAINTENANCE CLOSURE  
当前状态：IMPLEMENTED / HUMAN ACCEPTANCE WAITING

---

## 1. 最终结论

本轮已将企业组织运作模型 V1 的组织、部门、岗位、员工、职责、汇报关系和流程责任维护能力统一接入正式管理员入口：

```text
#/organization
├── ?tab=departments
├── ?tab=positions
├── ?tab=employees
├── ?tab=users
├── ?tab=roles
└── ?tab=permissions
```

`#/organization-model*` 现定位为综合查看、关系树、事实诊断和审计展示，不再向用户提供第二套正式维护入口。

```text
Implementation = PASS
Specialized Automatic Tests = 27/27 PASS
Procurement Protection Tests = 4/4 PASS
Vite Production Build = PASS
Read-only Real Browser Evidence = PASS
Human Acceptance H01-H09 = WAITING
Full Project Build = BLOCKED BY EXISTING SCM STATIC GATES
Ready Gate = FAIL
```

---

## 2. 两套页面数据源审计

审计发现，两套页面原本已经使用相同正式 Django 模型，不存在两套 Department、Position 或 Employee 数据库模型：

| 事实 | 正式模型 |
|---|---|
| OrganizationUnit | `system.OrganizationUnit` |
| Department | `system.Department` |
| Position | `system.Position` |
| Employee | `pfm.Employee` |
| JobFamily | `system.JobFamily` |
| JobLevel | `system.JobLevel` |
| Responsibility | `system.Responsibility` |
| PositionResponsibility | `system.PositionResponsibility` |
| EmployeeReportingRelation | `pfm.EmployeeReportingRelation` |
| PositionWorkflowResponsibility | `system.PositionWorkflowResponsibility` |

真实问题不是“两套数据库模型”，而是“两条写链”：

```text
原 #/organization
→ AccessControlFoundationView 简化写方法
→ 只校验 superuser
→ 没有 reason / 六项权限 / OrganizationOperatingAuditRecord

原 #/organization-model*
→ OrganizationOperatingService
→ 六项权限 / AuthorizationService / 事务 / reason / 审计
```

整改后，正式组织动作统一进入：

```text
OrganizationOperatingService
→ AuthorizationService
→ 正式模型持久化
→ OrganizationOperatingAuditRecord
→ EnterpriseOrganizationModelService 回读
```

旧 Foundation POST 即使继续接收组织动作，也只能委托同一 OrganizationOperatingService，无法再绕过修改原因、维护权限或审计。

---

## 3. 正式管理员入口能力

### 3.1 部门管理

列表显示：部门编码、名称、公司、组织单元、上级部门、责任岗位、实际负责人和状态。

维护支持：部门编码、名称、类型、组织单元、上级部门、责任岗位、生效/失效日期、状态和修改原因。实际负责人通过独立 Employee 关系维护，不再使用含义模糊的“负责人”输入框。

组织单元维护作为部门体系内的二级页签提供，不增加新的左侧一级菜单。

### 3.2 岗位管理

列表显示：岗位编码、名称、部门、岗位族、岗位等级、上级岗位、默认角色、任职人数和状态。

岗位管理内部提供：

- 岗位基本信息、上下级、默认角色和有效期；
- JobFamily 新增、编辑、启用和停用；
- JobLevel 新增、编辑、启用和停用；
- Responsibility 新增、编辑、启用和停用；
- PositionResponsibility 分配及主责标识；
- PositionWorkflowResponsibility 的 OWNER、APPROVER、REVIEWER、EXECUTOR 配置。

岗位树继续直接读取 `parent_position`，不存在第二套岗位层级。

### 3.3 员工档案

列表显示：员工编号、姓名、公司、正式部门、正式岗位、直属/职能主管、关联登录账户和状态。

员工维护支持：

- 正式部门和正式岗位；
- 查看、建立或解除与既有 User 的一对一关系；
- 直属主管和职能主管；
- 员工不能成为自己的主管；
- 账户密码、安全状态和账号启停仍只在“用户账户”维护。

### 3.4 Role 与 Permission

Role 管理保持原实现，只做岗位默认角色选择所需的接入，没有重构。

Permission 没有新增/编辑按钮是正确治理设计。当前权限目录来自业务动作代码、治理迁移和受控初始化；管理员可以查看权限编码、模块和已授权角色，并在角色管理中分配既有权限，但不能任意创造新的 Permission。

---

## 4. 权限与审计边界

继续复用且仅复用以下六项维护权限：

```text
system.organization.structure.manage
system.organization.department.manage
system.organization.position.manage
system.organization.responsibility.manage
system.organization.reporting.manage
system.organization.workflow_responsibility.manage
```

所有成功组织写操作必须包含 `reason`，并记录操作者、目标、Before、After 和时间。无权限身份直接调用组织写 API 返回 HTTP 403；页面按钮不是最终权限边界。

正式动作现包括：

```text
SAVE_ORGANIZATION_UNIT
SAVE_DEPARTMENT
SAVE_DEPARTMENT_LEADER
SAVE_JOB_FAMILY
SAVE_JOB_LEVEL
SAVE_POSITION
SAVE_RESPONSIBILITY
SAVE_POSITION_RESPONSIBILITY
SAVE_EMPLOYEE
SAVE_EMPLOYEE_ACCOUNT
SAVE_REPORTING_RELATION
SAVE_WORKFLOW_RESPONSIBILITY
```

---

## 5. 数据库变更

没有新增第三套组织模型。唯一模型增量是为既有 `system.Position` 增加：

```text
effective_from
effective_to
```

两个字段均可空，由迁移 `system.0008_position_effective_period` 建立；现有 35 个岗位没有被自动填值。

迁移前备份：

```text
D:\Dev-PCE\Source\backend\db.pre-admin-entry-unification-v1-20260816.sqlite3
SHA256 4D34EA970B14274A699B565305AA3459AD3E521095CA4B571C23B5F86C541791
```

---

## 6. 正式数据保护结果

```text
Position = 35
Employee = 104
EmployeeReportingRelation = 0
OrganizationLeadershipAssignment = 0
OrganizationOperatingAuditRecord = 0
PurchaseOrder = 218
SupplierMaterialPrice = 28
masterdata.CostCenter = 1（TEMPORARY LEGACY）
```

审计数仍为 0，证明本轮没有根据岗位名称、部门名称或审批历史自动建立任何正式组织关系。

继续执行：

> **本阶段取消成本中心、利润中心及其它经营中心设计。经营核算、绩效、成本、收入、费用、利润、投资回报等内容，待 PCE-ERP 管理运作体系及主要业务系统完成、产生真实业务数据后，再单独设计。**

没有恢复 `system.CostCenter` 或 `system.ProfitCenter`；采购域的 `masterdata.CostCenter` 保持 TEMPORARY LEGACY，未扩大使用。

---

## 7. 自动与构建验证

| 验证 | 结果 |
|---|---|
| 组织运作、管理员入口、组织模型与权限核心联合测试 | `27/27 PASS`，2.697s |
| 管理员入口与综合投影同源 | PASS |
| Foundation POST 缺少 reason | PASS，HTTP 400 / REASON_REQUIRED |
| 普通身份直接写组织 API | PASS，HTTP 403 |
| 部门/岗位层级防环 | PASS |
| 员工自主管禁止 | PASS |
| 员工账户一对一关联 | PASS |
| 组织成功写入生成审计 | PASS（隔离测试库） |
| migrations check | PASS，No changes detected |
| Django check | PASS |
| Procurement R5.1 保护回归 | `4/4 PASS` |
| Vite production build | PASS，2542 modules |
| PurchaseOrder | `218 -> 218`，新增 0 |
| SupplierMaterialPrice | `28 -> 28`，新增 0 |

全项目构建仍为：

```text
PCE-WEB-ACCEPTANCE-V1.1 = 1154/1161
Full Project Build = BLOCKED BY EXISTING SCM STATIC GATES
Blocker Count = 7
```

七项仍是采购询价、询价下一流程验收、供应商绩效、采购员绩效和采购异常责任分析的既有列表静态门禁。本轮没有修复或改写其结论。

---

## 8. 真实浏览器证据

当前浏览器身份是 `organization_department_viewer_v1 / DEPARTMENT`，不是管理员，因此本轮没有绕过登录或使用管理员凭据。

真实浏览器确认：

- `#/organization?tab=departments` 对当前身份返回“仅系统管理员可以维护组织与权限基础”，没有维护按钮；
- 部门表头已经是组织单元、上级部门、责任岗位、实际负责人和状态；
- 岗位表头已经是岗位族、岗位等级、上级岗位、默认角色、任职人数和状态；
- 员工表头已经是公司、正式部门、正式岗位、直属/职能主管、关联登录账户和状态；
- 权限目录已经显示“已授权角色”，并声明权限只允许受控登记；
- `#/organization-model/departments` 显示“综合查看与诊断”“唯一正式管理员入口”，当前只读身份按钮禁用，业务写入为 0。

证据：

```text
frontend/test-results/pce-admin-entry-unification-v1/ADMIN-ENTRY-V1-01-readonly-guard.png
frontend/test-results/pce-admin-entry-unification-v1/ADMIN-ENTRY-V1-02-model-readonly.png
```

---

## 9. H01–H09 人工验收恢复条件

原 `H01–H09 = SUSPENDED` 的入口阻断原因已经消除，现调整为：

```text
H01-H09 = READY FOR HUMAN EXECUTION / WAITING
Human Acceptance = NOT PASS YET
```

用户本人需要使用 superadmin 登录 `localhost`，在唯一入口完成：

- [ ] H01：部门管理 → 组织单元维护，保存并刷新一个可确认的上下级关系；
- [ ] H02：部门管理，维护上级部门并确认防环；
- [ ] H03：部门管理，维护责任岗位；
- [ ] H04：部门管理，维护实际负责人 Employee；
- [ ] H05：岗位管理 → 岗位族，创建/编辑并关联岗位；
- [ ] H06：岗位管理 → 岗位等级，创建/编辑并关联岗位；
- [ ] H07：岗位管理，维护上级岗位并在综合岗位树回读；
- [ ] H08：岗位管理 → 岗位职责，维护 Responsibility 和岗位分配；
- [ ] H09：岗位管理，维护默认 Role 并确认 Position 与 Role 独立；
- [ ] 配套：员工档案中核验关联登录账户和直属主管；
- [ ] 配套：岗位管理中核验流程责任仅保存配置、不执行 Workflow；
- [ ] 配套：在综合页面刷新并确认同一事实无需第二次维护；
- [ ] 最终：再次确认 PurchaseOrder 218、SupplierMaterialPrice 28。

人工验收完成前，不得签发 `Human Acceptance = PASS`。

---

## 10. 当前状态

```text
PCE Enterprise Organization Operating Model V1 = IMPLEMENTED
Admin Entry Unification = PASS
Maintenance Service Unification = PASS
Automatic Acceptance = PASS
Read-only Real Browser Evidence = PASS
Human Acceptance = WAITING FOR USER
Full Project Build = BLOCKED BY EXISTING SCM STATIC GATES
Ready = FAIL
Unauthorized Business Writes = 0
PurchaseOrder Added = 0
SupplierMaterialPrice Added = 0
```

本轮到此停止开发，不进入 SCM 七项历史门禁、Workflow 执行、采购业务、经营中心、复杂 AI 权限或自动组织数据填充。
