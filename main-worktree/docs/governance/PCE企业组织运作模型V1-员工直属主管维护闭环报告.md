# PCE 企业组织运作模型 V1——员工直属主管维护闭环报告

报告日期：2026-08-17  
专项类型：Employee Reporting Relation Maintenance Closure  
当前状态：IMPLEMENTED / AUTOMATIC PASS / HUMAN ACCEPTANCE WAITING

---

## 1. 最终结论

本轮严格限定在 Employee（员工）直属主管维护闭环，没有修改 AuthorizationService、Permission Core、Department、Position、Workflow、采购业务、PurchaseOrder、SupplierMaterialPrice 或 SCM Static Gate，也没有新增第三套员工关系模型。

正式管理员入口保持唯一：

```text
#/organization
→ 员工档案
→ 编辑员工
→ 直属主管（Direct Manager）
→ SAVE_EMPLOYEE
→ AuthorizationService
→ system.organization.reporting.manage
→ OrganizationOperatingService
→ EmployeeReportingRelation
→ OrganizationOperatingAuditRecord
→ 服务端刷新回读
```

员工编辑主表单已直接提供直属主管与有效期字段；直属主管候选只来自正式 Employee 档案，并显示“姓名（岗位）· 员工编号”。保存员工时，直属主管的创建、更新或解除与员工档案处于同一个服务端事务中。

```text
Employee Reporting Closure = PASS
Specialized Automatic Tests = 8/8 PASS
Organization / Permission Joint Regression = 35/35 PASS
Procurement R5.1 Protection = 4/4 PASS
Vite Production Build = PASS（2542 modules）
Human Acceptance H10 = WAITING FOR USER
Human Acceptance of Organization Model V1 = WAITING FOR H01-H09 + H10
Ready Gate = FAIL（用户尚未签发人工验收，且既有 SCM 静态门禁仍有 7 项）
```

`Employee Reporting Closure = PASS` 表示本轮实现、服务端规则、API 回读、审计和自动验收已经闭合；它不替代用户在真实浏览器中的 H10 签发。

---

## 2. 治理加载与复用结论

开发前已读取：

- `docs/standards/PCE-DEVELOPMENT-STANDARD-V1.0.md`
- `docs/standards/PCE-BUSINESS-ACTION-PERMISSION-V1.0.md`
- `docs/governance/01-开发治理总纲/PCE-ERP开发治理总纲.md`
- `docs/governance/02-架构与运行边界/PCE-ERP架构与运行边界规范.md`
- `docs/governance/Runtime职责规范.md`
- `docs/governance/Schema规范.md`
- `docs/governance/真实运行验收规范.md`
- `docs/governance/PCE企业组织运作模型V1-实施与人工验收交接报告.md`
- `docs/governance/PCE企业组织运作模型V1-正式管理员入口统一与维护闭环整改报告.md`
- `docs/governance/PCE-ERP智能化开发总纲.md`
- `docs/governance/04-页面与交互治理/PCE-ERP页面与交互开发规范.md`
- `docs/governance/05-自动验收治理/PCE-ERP自动验收与证据治理规范.md`

智能化影响评估：本轮是显式人工主数据关系维护，不允许系统推断主管，不新增推荐或自动组织能力。  
已有能力扫描：既有 EmployeeReportingRelation、OrganizationOperatingService、AuthorizationService、OrganizationOperatingAuditRecord、EnterpriseOrganizationModelService 和 PceEnterpriseListTable 均可复用。  
复用方案：扩展既有 `SAVE_EMPLOYEE` 载荷与同一服务事务；继续复用既有汇报维护权限、正式事实投影和列表基座。  
实施边界：只补员工编辑入口、直属主管事务保存、服务端防环/同公司规则、审计快照、回读显示和专项测试。

没有新增 Metadata、Schema、Runtime、Registry、Config、页面路由、权限核心或员工关系模型。

---

## 3. 修改文件清单

| 文件 | 本轮变化 |
|---|---|
| `backend/system/organization_operating.py` | `SAVE_EMPLOYEE` 同事务保存/更新/解除直属主管；新增汇报链防环、V1 同公司校验和直属主管审计快照；既有 `SAVE_REPORTING_RELATION` 同步复用防环与公司校验。 |
| `backend/system/enterprise_organization.py` | 服务端员工投影增加直属主管姓名、岗位、显示值和有效期；只读取 active + primary 正式关系；保留职能主管显示。 |
| `backend/system/tests_employee_reporting_relation_closure_v1.py` | 新增 T01–T08 专项自动测试。 |
| `frontend/src/meta/components/OrganizationOperatingAdminDialog.vue` | 员工主编辑表单增加“直属主管（Direct Manager）”和有效期；候选来自正式 Employee；保存按钮明确员工与主管同存并回读。 |
| `frontend/src/meta/pages/AccessControlFoundationPage.vue` | 员工列表直接显示直属主管与职能主管；直属主管进入正式筛选与快速搜索字段。 |
| `frontend/src/meta/components/EnterpriseOrganizationModelView.vue` | 综合组织模型继续复用同一服务端员工投影，明确显示“直属主管”。 |
| `docs/governance/PCE企业组织运作模型V1-员工直属主管维护闭环报告.md` | 本报告。 |

未修改：`backend/system/authorization.py`、Permission Core、Department/Position 模型及迁移、Workflow、采购域代码、PurchaseOrder、SupplierMaterialPrice、SCM Static Gate。

---

## 4. 数据模型变化

数据库 Schema 变化：无。  
迁移文件：无。  
第三套员工关系模型：无。

继续复用既有正式模型：

```text
pfm.Employee
  ↓ employee / manager（均为 Employee 外键）
pfm.EmployeeReportingRelation
  - relation_type = DIRECT
  - is_primary = true
  - active
  - effective_from
  - effective_to
```

岗位上下级仍属于 `system.Position.parent_position`；员工实际汇报关系仍只属于 `pfm.EmployeeReportingRelation`。Position、Role、Department、User 均不能作为直属主管对象。

解除直属主管时不删除历史行，而是将当前 active 主直属关系置为 inactive；重新读取只投影 active + primary 关系。

---

## 5. API 变化

现有写端点保持不变：

```text
POST /api/access-control/enterprise-organization-model/
POST /api/access-control/foundation/（既有兼容委托入口）
```

`SAVE_EMPLOYEE` 新增可选载荷：

```json
{
  "directManagerId": 123,
  "directManagerEffectiveFrom": "2026-08-17",
  "directManagerEffectiveTo": null
}
```

- 提供 `directManagerId`：创建或更新当前 `DIRECT + primary + active` 关系；
- 提供 `directManagerId: null`：解除当前直属主管并保留历史行；
- 旧调用不提供该字段：不改变既有直属主管关系，保持向后兼容；
- 员工档案、直属主管关系与审计在同一个 `transaction.atomic()` 内完成，任一校验失败整体回滚。

现有读端点保持不变：

```text
GET /api/access-control/foundation/
GET /api/access-control/enterprise-organization-model/
```

员工服务端投影新增：

```text
directManagerId
directManagerName
directManagerPositionName
directManagerDisplay
directManagerEffectiveFrom
directManagerEffectiveTo
functionalManagerDisplay
```

页面、综合组织模型和自动验收均复用这些服务端字段，不在前端重算主管关系。

---

## 6. 服务端防错误规则

| 规则 | 服务端结果 |
|---|---|
| 员工主管自己 | HTTP 400 / `SELF_MANAGER_FORBIDDEN` |
| 直接或多级汇报链形成循环 | HTTP 400 / `REPORTING_CYCLE_FORBIDDEN` |
| 主管 Employee 不存在 | HTTP 400 / `INVALID_MANAGER` |
| 员工与主管跨 Company | HTTP 400 / `CROSS_COMPANY_MANAGER_FORBIDDEN` |
| 有效期结束早于开始 | HTTP 400 / `INVALID_EFFECTIVE_PERIOD` |
| 无维护权限 | HTTP 403；服务端拒绝，零关系写入、零审计写入 |

防环检查沿当前相同关系类型的 active + primary 汇报链逐级读取并锁定；不把岗位上下级当作员工汇报链。

---

## 7. 权限变化

新增 Permission：无。  
修改 AuthorizationService：无。  
绕过 AuthorizationService：无。

继续复用：

```text
system.organization.reporting.manage
```

服务端执行顺序：

```text
页面显式保存意图
→ OrganizationOperatingService.execute
→ AuthorizationService.decide
→ system.organization.reporting.manage
→ 组织/部门数据范围
→ 事务校验与持久化
→ OrganizationOperatingAuditRecord
```

页面隐藏、候选过滤和按钮状态只用于体验；API 权限结论仍由服务端产生。

---

## 8. 审计变化

每次通过员工保存成功修改直属主管，继续生成既有 `OrganizationOperatingAuditRecord`：

```text
actionCode = SAVE_EMPLOYEE
actor / createdAt / reason
targetType = Employee
targetId / targetLabel
beforeSnapshot.directManager
afterSnapshot.directManager
```

直属主管快照包含：关系 ID、员工 ID、主管 Employee ID、关系类型、主关系标志、状态、生效日期和失效日期。正常新增、更新和解除均可从 Before/After 追踪；失败事务不产生审计记录。

---

## 9. 自动测试结果

### 9.1 本轮专项测试

| 编号 | 场景 | 结果 |
|---|---|---|
| T01 | 正常设置直属主管、有效期与审计 | PASS |
| T02 | 自己主管自己 | PASS：拒绝 |
| T03 | 循环主管关系 | PASS：拒绝 |
| T04 | 无权限用户调用 API | PASS：HTTP 403 |
| T05 | 保存后通过正式 Foundation API 重新读取 | PASS：一致 |
| T06 | 跨公司直属主管 | PASS：V1 拒绝 |
| T07 | 更新既有直属主管 | PASS：关系不重复，Before/After 正确 |
| T08 | 解除直属主管并重新读取 | PASS：历史行 inactive，页面投影为待维护 |

执行结果：

```text
Ran 8 tests in 0.136s
OK
```

### 9.2 联合回归

```text
system.tests_employee_reporting_relation_closure_v1
system.tests_enterprise_organization_operating_model_v1
system.tests_enterprise_organization_model_v1
system.tests_organization_access_core_v1
system.tests_erp_access_foundation
```

结果：

```text
Ran 35 tests in 2.658s
OK
```

### 9.3 工程与保护检查

| 检查 | 结果 |
|---|---|
| Django system check | PASS，0 issues |
| migrations check | PASS，No changes detected |
| Procurement R5.1 | PASS，4/4 |
| Vite production build | PASS，2542 modules |
| PCE-WEB-ACCEPTANCE-V1.1 | `1154/1161`，既有 SCM 7 项 blocker |

全项目静态门禁的 7 项仍属于采购询价、询价下一流程验收、供应商绩效、采购员绩效和采购异常责任分析。本轮没有修复、改写、绕过或降低这些门禁，因此 Full Project Build / Ready Gate 仍不能标记为 PASS。

---

## 10. 采购保护与真实库数量

真实开发库本轮前后：

| 对象 | Before | After | 新增/变化 |
|---|---:|---:|---:|
| Employee | 104 | 104 | 0 |
| EmployeeReportingRelation | 0 | 0 | 0 |
| OrganizationOperatingAuditRecord | 5 | 5 | 0 |
| PurchaseOrder | 218 | 218 | 0 |
| SupplierMaterialPrice | 28 | 28 | 0 |

```text
Authorized Business Write Count（真实开发库）= 0
Unauthorized Business Write Count = 0
PurchaseOrder Added = 0
SupplierMaterialPrice Added = 0
```

专项测试仅在 Django 隔离测试数据库创建关系与审计，测试结束销毁；未向真实开发库补造任何主管关系。

---

## 11. 浏览器人工验收 H10-Employee Reporting

当前状态：`WAITING FOR USER`。本报告不把自动测试、源码检查或 Vite 构建冒充用户人工验收。

请用户本人执行：

1. 使用 `superadmin` 登录；
2. 进入 `#/organization`；
3. 选择“员工档案”；
4. 选择一名可确认的真实员工并点击“编辑”；
5. 在“员工档案”主表单找到“直属主管（Direct Manager）”；
6. 从正式 Employee 候选中选择主管，例如“李四（采购经理）”；
7. 按需要填写直属主管有效期；
8. 填写明确修改原因；
9. 点击“保存员工及直属主管并回读”；
10. 点击页内“刷新”，确认员工列表“直属主管”仍显示同一人员；
11. 浏览器整页刷新后再次确认；
12. 打开 `#/organization-model`，确认同一员工的“直属主管”显示一致；
13. 在最近组织维护审计中核对操作者、时间、原因、员工和 Before/After；
14. 最后确认 PurchaseOrder 仍为 218、SupplierMaterialPrice 仍为 28。

H10 单页验收记录模板：

```text
Page URL / 页面URL：http://localhost:5173/#/organization?tab=employees
Page Title / 页面标题：组织、人员、岗位、账户、角色与权限 / 员工档案
Route Component：AccessControlFoundationPage.vue
Acceptance Regions / 验收区域：
  Top Region / 顶部区域：ERP 组织与权限基础、服务端正式数据、员工档案页签
  Middle Region / 中部区域：员工企业列表、编辑窗口、直属主管（Direct Manager）、有效期、修改原因
  Bottom Region / 底部区域：正式维护闭环说明、最近组织维护审计
Checked Fields / 检查字段：员工编号、姓名、公司、部门、岗位、直属主管、有效期、修改原因
Checked Buttons / 检查按钮：编辑、保存员工及直属主管并回读、刷新
Expected Result / 期望结果：Employee → Direct Manager 关系保存；刷新、整页重载和综合模型回读一致；审计完整
Actual Result / 实际结果：等待用户填写
Screenshot / 截图：等待用户本次会话截图
Business Write Count：等待用户填写（只允许已授权 EmployeeReportingRelation + Audit）
Page Acceptance：WAITING
```

PASS 条件：同一 Employee 与所选直属主管关系真实存在，页面刷新、整页刷新、综合模型和审计使用同一服务端事实，且没有采购写入。

---

## 12. 治理检查

```text
Governance Files Loaded: PASS
Frozen Asset Check: PASS（仅修改授权范围内员工编辑字段与显示；未改公共 Page Shell、列表基座或流程图）
Identity Check: PASS（Employee ID 与 EmployeeReportingRelation ID 独立；主管引用正式 Employee ID）
Data Extract Check: PASS（单员工/单主直属关系为模型唯一性契约；未对集合做未授权降维）
Array Completeness: N/A（本动作是单 Employee 的单 primary DIRECT 关系；无多来源数组）
Regression Check: PASS（35/35 组织权限联合回归、4/4 R5.1、Vite build）
Automatic Acceptance: PASS
Browser Automatic Acceptance: NOT EXECUTED（本轮按指令等待用户 H10）
Real Browser Evidence: WAITING
Human Acceptance: WAITING
Build: PASS（Vite）；Full Project Static Gate 仍被既有 7 项 SCM blocker 阻断
Ready Gate: FAIL
PAGE_FREEZE_CHECK: PASS
FLOW_VISUAL_FREEZE_CHECK: N/A（未修改流程可视化）
COMPONENT_IMPACT_CHECK: N/A（未修改公共组件）
DATA_IDENTITY_CHECK: PASS
DATA_EXTRACT_CHECK: PASS
ARRAY_COMPLETENESS_CHECK: N/A
BUSINESS_CAPABILITY_CHECK: PASS（复用既有企业列表、筛选、刷新、权限与审计；本轮不新增导入/批量能力）
```

---

## 13. 最终状态

```text
PCE Enterprise Organization Operating Model V1 = IMPLEMENTED
Employee Reporting Closure = PASS
Direct Manager Entry in Employee Edit = PASS
Server Validation = PASS
AuthorizationService Chain = PASS
Save / Update / Clear / Readback = PASS
OrganizationOperatingAuditRecord = PASS
Procurement Protection = PASS
PurchaseOrder = 218
SupplierMaterialPrice = 28
Human Acceptance H10 = WAITING FOR USER
Human Acceptance H01-H09 = WAITING FOR USER
Human Acceptance of Organization Model V1 = WAITING
Full Project Static Gate = FAIL（既有 SCM 7 项，非本轮范围）
Ready = FAIL
```

本轮开发到此停止。下一步只等待用户完成 H10，并继续完成组织模型 V1 的 H01–H09；不进入 AuthorizationService、Permission Core、Department/Position 模型、Workflow 执行、采购业务或 SCM 静态门禁整改。
