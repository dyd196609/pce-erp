# PCE 企业组织运作模型 V1——员工汇报关系语义优化报告

报告日期：2026-08-17  
专项类型：Employee Reporting Relation UX Semantic Optimization  
状态：IMPLEMENTED / AUTOMATIC PASS / HUMAN ACCEPTANCE WAITING

---

## 1. 修改原因

真实人工验收发现员工汇报关系界面存在三项语义问题：

1. 详细维护区域使用“主管”字段，管理员无法判断是直属主管还是职能主管；
2. 员工编辑页显示“直属主管（Direct Manager）”，中英文括号增加理解负担；
3. 直属主管与职能主管没有并列中文职责说明，管理员无法快速判断两个关系的业务区别。

本轮只优化页面字段名称、中文提示、候选显示、服务端事实展示和操作说明，不改变任何关系模型、权限、服务或审计规则。

---

## 2. 修改页面

### 2.1 正式维护入口

```text
#/organization
→ 员工档案
→ 编辑员工
```

员工主表单现在并列显示：

```text
直属主管
员工日常汇报对象，负责日常工作安排和管理。

职能主管
员工专业领域负责人，负责专业指导和业务规范管理。
```

“汇报关系详细维护”区域根据当前关系类型明确显示“直属主管”或“职能主管”，不再出现含义不明确的 `label="主管"` 或“直属/职能主管”合并字段。

### 2.2 综合查看

```text
#/organization-model
```

每个员工的组织关系卡片同时显示：

```text
直属主管：<服务端 directManagerDisplay>
职能主管：<服务端 functionalManagerDisplay>
```

综合页面说明同步解释两类关系的业务含义。两个页面继续消费同一服务端 EmployeeReportingRelation 投影，不使用页面缓存或前端关系重算。

---

## 3. 修改字段

| 原显示 | 新显示 | 结果 |
|---|---|---|
| `主管` | 根据关系类型显示“直属主管”或“职能主管” | 取消歧义 |
| `直属主管（Direct Manager）` | `直属主管` | 页面不显示英文括号 |
| `直属/职能主管` | 分离为 `直属主管`、`职能主管` | 管理员可分别理解和维护 |
| `员工编号 · 姓名` | `姓名（岗位）· 员工编号` | 突出 Employee 人员主体与岗位辅助信息 |

候选示例：

```text
李四（采购经理）· EMP006
王五（供应链总监）· EMP008
```

候选对象仍是正式 `Employee`。岗位只作为括号中的人员识别信息，不能单独作为主管选项。

---

## 4. 数据与服务边界

### 4.1 数据模型

```text
EmployeeReportingRelation 数据模型变化 = NO
数据库迁移 = NO
新增员工关系模型 = NO
```

唯一事实来源保持：

```text
EmployeeReportingRelation
├── relation_type = DIRECT       → 直属主管
└── relation_type = FUNCTIONAL   → 职能主管
```

没有新增 EmployeeManagerV2、DirectManagerTable、FunctionalManagerTable 或页面本地关系事实。

### 4.2 服务、权限与审计

以下内容均未修改：

- AuthorizationService；
- Permission Core；
- OrganizationOperatingService 核心逻辑；
- `system.organization.reporting.manage`；
- OrganizationOperatingAuditRecord；
- Department、Position、Workflow；
- 采购业务与 SCM Static Gate。

职能主管详细保存继续调用既有：

```text
SAVE_REPORTING_RELATION
relationType = FUNCTIONAL
```

直属主管继续使用既有 DIRECT 关系保存链。成功保存仍记录操作者、时间、修改原因、Before 和 After；本轮没有增加或改变审计写法。

---

## 5. 修改文件

| 文件 | 修改内容 |
|---|---|
| `frontend/src/meta/components/OrganizationOperatingAdminDialog.vue` | 员工编辑页并列显示直属主管/职能主管、中文说明、员工候选格式；详细维护字段取消“主管”歧义。 |
| `frontend/src/meta/components/EnterpriseOrganizationModelView.vue` | 综合模型同时显示直属主管和职能主管，并补充中文业务说明与一致候选格式。 |
| `backend/system/tests_employee_reporting_relation_semantic_optimization_v1.py` | 新增 T01–T05 语义、回读和采购隔离测试。 |
| `docs/governance/PCE企业组织运作模型V1-员工汇报关系语义优化报告.md` | 本报告。 |

`AccessControlFoundationPage.vue` 已在上一闭环中分别显示“直属主管”和“职能主管”，本轮复核后无需再改变其数据逻辑。

---

## 6. 自动测试结果

### 6.1 本轮专项 T01–T05

| 编号 | 验证内容 | 结果 |
|---|---|---|
| T01 | 两个目标页面不存在 `label="主管"`、合并字段或 Direct/Functional Manager 英文括号显示 | PASS |
| T02 | 存在直属主管、职能主管、两段中文说明及“姓名（岗位）·员工编号”格式 | PASS |
| T03 | 保存 `DIRECT` 后通过正式 Foundation API 回读 | PASS，`李四（采购经理）` |
| T04 | 保存 `FUNCTIONAL` 后通过正式 Foundation API 回读 | PASS，`王五（供应链总监）` |
| T05 | 保存两类关系不改变 PurchaseOrder 与 SupplierMaterialPrice 数量 | PASS |

```text
Ran 5 tests in 0.088s
OK
```

### 6.2 组织与权限联合回归

本轮专项、员工直属主管闭环、组织运作模型、综合组织模型、组织权限核心及管理员入口联合执行：

```text
Ran 40 tests in 2.094s
OK
```

### 6.3 采购与构建保护

| 检查 | 结果 |
|---|---|
| Procurement R5.1 | PASS，4/4 |
| Django system check | PASS，0 issues |
| migrations check | PASS，No changes detected |
| Vite production build | PASS，2542 modules |
| PCE-WEB-ACCEPTANCE-V1.1 | 1154/1161；既有 SCM 7 项 blocker，未修改或绕过 |

真实开发库最终事实：

```text
EmployeeReportingRelation = 2
OrganizationOperatingAuditRecord = 10
PurchaseOrder = 218
SupplierMaterialPrice = 28
```

本轮自动测试只写隔离测试数据库，真实开发库业务写入为 0。当前 2 条员工汇报关系和 10 条组织审计是进入本轮结束检查时已经存在的正式事实，本轮未自动创建、删除或改写。

---

## 7. H10 员工汇报关系人工验收

当前状态：`WAITING FOR USER`。

### H10-1 字段语义

使用 `superadmin` 进入：

```text
#/organization
→ 员工档案
→ 编辑真实员工
```

确认同时看到：

- 直属主管；
- 职能主管；
- 两段中文职责说明；
- 页面没有“直属主管（Direct Manager）”或“职能主管（Functional Manager）”英文括号；
- 不存在单独名为“主管”的字段。

### H10-2 人员选择

选择真实 Employee，例如：

```text
李四（采购经理）· EMP006
```

确认候选主体是人员姓名，不是单独的岗位“采购经理”。

### H10-3 保存与刷新

填写修改原因并保存；点击页内刷新，再执行浏览器整页刷新，确认直属主管或职能主管保持不变。

### H10-4 综合组织模型一致性

进入：

```text
#/organization-model
```

确认同一员工同时显示相同的直属主管和职能主管事实。

### H10-5 审计

确认 OrganizationOperatingAuditRecord 存在，并记录：

- 操作者；
- 时间；
- 修改原因；
- Before；
- After。

人工验收完成后，请用户明确签发 `H10 员工汇报关系 = PASS`。Codex 自动测试和构建不能替代该签发。

---

## 8. 最终状态

```text
Employee Reporting Relation UX Semantic Optimization = PASS
Page Field Semantics = PASS
Direct Manager Chinese Display = PASS
Functional Manager Chinese Display = PASS
Employee Option Format = PASS
Single Server Fact Source = PASS
Data Model Changed = NO
AuthorizationService Changed = NO
Permission Core Changed = NO
OrganizationOperatingService Core Changed = NO
Audit Logic Changed = NO
Procurement Protection = PASS
PurchaseOrder = 218
SupplierMaterialPrice = 28
Automatic Acceptance = PASS
Vite Build = PASS
Human Acceptance H10 = WAITING FOR USER
Human Acceptance of Organization Model V1 = WAITING
Ready Gate = FAIL（等待用户人工验收；既有 SCM 7 项静态 blocker 仍在）
```

本轮到此停止，不扩展绩效、成本、利润中心、AI 组织优化或 HR 系统。下一步只等待组织模型最终人工验收。
