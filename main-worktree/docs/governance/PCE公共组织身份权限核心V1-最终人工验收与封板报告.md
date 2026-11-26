# PCE 公共组织身份权限核心 V1——最终人工验收与封板报告

日期：2026-08-16  
任务类型：FINAL HUMAN ACCEPTANCE（最终人工验收）与封板检查  
验收页面：`http://localhost:5173/#/organization-directory`  
业务动作：`system.organization_directory.view`  
最终状态：`BASELINE（正式基线）`；权限专项 `CLOSED（正式结束）`

## 1. 执行边界

本轮只进行最终验收与证据固化，没有修改 AuthorizationService、Scope、Role/Permission 模型、Workflow、Gate、采购代码、SupplierMaterialPrice、PurchaseOrder、Meta permissionEngine、rbacEngine 或 SG01–SG07。

没有创建采购订单、维护供应商物料价格、推进采购审批、执行付款或银行发送。为补齐 DENY 和 DEPARTMENT 两类真实身份，仅通过正式 `/api/access-control/foundation/` 管理 API 建立专用测试 User、Employee、Role、RolePermission 和 UserRoleScopeAssignment；没有使用 SQL 或直接 SQLite 修改。

## 2. 治理与原始报告加载

以下规范已在测试前重新完整读取：

- `docs/standards/PCE-DEVELOPMENT-STANDARD-V1.0.md`
- `docs/standards/PCE-BUSINESS-ACTION-PERMISSION-V1.0.md`
- `docs/governance/PCE-ERP开发治理总规范.md`
- `docs/governance/01-开发治理总纲/PCE-ERP开发治理总纲.md`
- `docs/governance/02-架构与运行边界/PCE-ERP架构与运行边界规范.md`
- `docs/governance/03-业务流程运行治理/PCE-ERP业务流程运行治理规范.md`
- `docs/governance/Runtime职责规范.md`
- `docs/governance/Schema规范.md`
- `docs/governance/真实运行验收规范.md`

以下 V1 五份报告已重新完整读取：

- `PCE公共组织身份权限核心V1-实施报告.md`
- `PCE公共组织身份权限核心V1-架构调整记录.md`
- `PCE公共组织身份权限核心V1-删除清单.md`
- `PCE公共组织身份权限核心V1-测试报告.md`
- `PCE公共组织身份权限核心V1-人工验收报告.md`

治理加载结果：PASS。

## 3. 测试账户

测试账户密码没有写入源码、报告、截图、Console 或最终输出；工作区搜索确认不存在测试密码文本。

| 账户类型 | User | Employee | Department | Position | Role | Scope | 目录 Permission |
|---|---|---|---|---|---|---|---|
| ADMIN | `admin` / ID 1 | N/A，既有系统管理员没有 Employee 绑定 | Company ID 1 | N/A | `superadmin` | `ALL` | `*` |
| 普通业务人员 | `pce_org_deny_v1` / ID 6 | `EMP-V1-FINAL-DENY` / ID 103 | 采购部 `CGB` / ID 8 | 采购员 `CGB-CLERK` / ID 11 | `organization_denied_viewer_v1` | `SELF` | 未授予 |
| 部门业务人员 | `pce_org_department_v1` / ID 7 | `EMP-V1-FINAL-DEPT` / ID 104 | 采购部 `CGB` / ID 8 | 采购员 `CGB-CLERK` / ID 11 | `organization_department_viewer_v1` | `DEPARTMENT`，department ID 8 | 已授予 |

两名业务人员的 Position 均来自 `system.Position`，Role 均来自 `system.Role`；岗位与系统角色是不同字段、不同对象，没有 Position=Role 绑定。

## 4. H01–H17 结果

| 编号 | 状态 | 真实结果 |
|---|---|---|
| H01 管理员 ALL | PASS | admin 页面显示 `superadmin / ALL / ALLOW`，组织目录 16 条。 |
| H02 管理员权限来源 | PASS | API 决策契约为 `PCE-ORGANIZATION-ACCESS-CORE-V1`，`authoritySource=system.User`，服务端返回 `ALLOWED_SUPERUSER`；页面消费 Permission Profile 和组织目录 API，未发现 username/role 前端硬编码放行。 |
| H03 普通用户 DENY | PASS | 真实登录后手工进入 `/organization-directory`，页面显示 `organization_denied_viewer_v1 / SELF / DENY`，明确提示 Permission Profile 未授予业务动作，结果 0 条，无白屏。 |
| H04 普通用户后端绕过 | PASS | 使用同一真实 User 直接调用组织目录 API，后端返回 HTTP 403、`PERMISSION_DENIED`、rows=[]；已登录身份仍被服务端拒绝。 |
| H05 DEPARTMENT Scope | PASS | 部门用户真实登录后页面显示 `organization_department_viewer_v1 / DEPARTMENT / ALLOW`，结果仅 1 条。 |
| H06 部门身份真实性 | PASS | 唯一可见行是正式 `system.Department`：采购部 `CGB`、ID 8；未使用前端模拟字符串。 |
| H07 Scope 与 Department 分离 | PASS | 正式 Assignment 为 `department_id=8`、`scope_code=DEPARTMENT`；两字段独立，未出现 department_id=`DEPARTMENT/SELF`。 |
| H08 Permission Profile | PASS | admin=`superadmin/*/ALL`；普通用户=`organization_denied_viewer_v1/无动作权限/SELF`；部门用户=`organization_department_viewer_v1/system.organization_directory.view/DEPARTMENT`。 |
| H09 前端无硬编码越权 | PASS | 普通用户手工输入 URL 仍为 DENY、0 条；后端 API 同时 403。前端路由存在不构成授权。 |
| H10 Position 与 Role 分离 | PASS | 两名测试员工 Position=采购员 ID 11；Role 分别为无权限角色和部门查看角色，字段与对象独立。 |
| H11 采购系统保护 | PASS | `/scm/purchase-order/create` 正常加载，无白屏、无权限 Runtime error；未点击创建采购订单。 |
| H12 SupplierMaterialPrice 保护 | PASS | `/foundation/erp/supplier-material-prices` 正常显示供应商、物料、价格及既有人工维护控件；只查看，未新增价格。 |
| H13 PurchaseOrderGate 保护 | PASS | `/scm/purchase-order-gate` 正常显示采购订单准入页面，无白屏或 Console error；未修改 Gate 或推进状态。 |
| H14 PurchaseOrder 数量 | PASS | 测试开始 218，测试结束 218，本轮新增 0。 |
| H15 浏览器 Console | PASS | admin、DENY 用户、DEPARTMENT 用户的组织目录验收均无页面 error；H11–H13 页面也无页面 error。一次浏览器控制器自身 Statsig 外网超时不属于 PCE 页面 Console，未计为应用错误。 |
| H16 测试数据恢复 | PASS | 两套身份通过正式管理 API 建立，计划保留为受治理的 V1 回归身份；没有改动或替换既有 R10 两账户。最终状态见第 8 节。 |
| H17 最终权限矩阵 | PASS | 三类真实身份的页面和 API 结果与正式 Role/Permission/Scope 一致，见第 6 节。 |

## 5. 组织目录逐账户页面验收记录

### 5.1 ADMIN

```text
Page URL / 页面URL：http://localhost:5173/#/organization-directory
Page Title / 页面标题：组织目录 / 组织目录
Route Component：OrganizationDirectoryPage（由 PceListPageShell 包装）
Acceptance Regions / 验收区域：
  Top Region / 顶部区域：SYSTEM、organization-directory-v1、组织目录、只读试点说明
  Middle Region / 中部区域：权限运行链 superadmin / ALL / ALLOW
  Bottom Region / 底部区域：企业列表工具栏与 16 条正式部门数据
Checked Fields / 检查字段：actionCode、Runtime、Role、Scope、最终决定、部门编码/名称/公司/岗位数量/statusLabel
Checked Buttons / 检查按钮：搜索、刷新、高级筛选、清空筛选、清除排序、导出、选择；未执行业务写动作
Expected Result / 期望结果：管理员允许查看全部组织目录
Actual Result / 实际结果：ALLOW，16 条，无 Console error
Screenshot / 截图：frontend/test-results/pce-organization-access-core-v1-final/H01-H02-admin-all-allow.png
Business Write Count：0
Page Acceptance：PASS
```

### 5.2 普通业务人员

```text
Page URL / 页面URL：http://localhost:5173/#/organization-directory
Page Title / 页面标题：组织目录 / 组织目录
Route Component：OrganizationDirectoryPage（由 PceListPageShell 包装）
Acceptance Regions / 验收区域：
  Top Region / 顶部区域：页面身份正常，非白屏
  Middle Region / 中部区域：明确无权限警告；organization_denied_viewer_v1 / SELF / DENY
  Bottom Region / 底部区域：目录结果 0 条，不泄露全公司数据
Checked Fields / 检查字段：Role、Scope、DENY、disabledReason、结果数
Checked Buttons / 检查按钮：手工直接输入 URL；未执行写操作
Expected Result / 期望结果：无目录权限时页面与 API 均拒绝
Actual Result / 实际结果：页面 DENY/0 条，后端 HTTP 403 PERMISSION_DENIED，无 Console error
Screenshot / 截图：frontend/test-results/pce-organization-access-core-v1-final/H03-H04-H09-deny-user-browser.png
Business Write Count：0
Page Acceptance：PASS
```

### 5.3 部门业务人员

```text
Page URL / 页面URL：http://localhost:5173/#/organization-directory
Page Title / 页面标题：组织目录 / 组织目录
Route Component：OrganizationDirectoryPage（由 PceListPageShell 包装）
Acceptance Regions / 验收区域：
  Top Region / 顶部区域：页面身份与只读边界正常
  Middle Region / 中部区域：organization_department_viewer_v1 / DEPARTMENT / ALLOW
  Bottom Region / 底部区域：仅采购部 CGB 一行，不含财务部、生产部等其他部门
Checked Fields / 检查字段：Role、Scope、ALLOW、department ID 8、部门编码 CGB、结果数 1
Checked Buttons / 检查按钮：手工直接输入 URL；未执行写操作
Expected Result / 期望结果：只可查看正式授权部门
Actual Result / 实际结果：ALLOW，仅采购部 1 条，API departmentIds=[8]，无 Console error
Screenshot / 截图：frontend/test-results/pce-organization-access-core-v1-final/H05-H10-department-user-browser.png
Business Write Count：0
Page Acceptance：PASS
```

## 6. 最终权限矩阵

| 账户类型 | 真实账户 | Role | Scope | Permission Profile | 页面 | 后端 API | 最终结果 |
|---|---|---|---|---|---|---|---|
| ADMIN | admin | superadmin | ALL | permissionCodes=`*` | ALLOW，16 条 | HTTP 200，16 条 | PASS |
| 普通业务人员 | pce_org_deny_v1 | organization_denied_viewer_v1 | SELF | 无 `system.organization_directory.view` | DENY，0 条 | HTTP 403，PERMISSION_DENIED | PASS |
| 部门业务人员 | pce_org_department_v1 | organization_department_viewer_v1 | DEPARTMENT / department ID 8 | 含 `system.organization_directory.view` | ALLOW，仅采购部 1 条 | HTTP 200，departmentIds=[8]、1 条 | PASS |

## 7. API 与安全边界

三账户的 Permission Profile 均由 `/api/access-control/profile/` 返回，组织目录由 `/api/access-control/organization-directory/` 读取；最终决定来自 `AuthorizationService`。

普通用户虽然已经登录并能手工进入真实路由，后端仍返回 HTTP 403。这证明按钮、路由、页面显示和本地状态都不是最终安全边界。部门用户的 API 决策同时返回：

```text
authoritySource = system.UserRoleScopeAssignment
scope.codes = [DEPARTMENT]
scope.departmentIds = [8]
resultCount = 1
businessWriteCount = 0
```

## 8. 数据库变化与测试数据状态

测试前基线：

```text
PurchaseOrder = 218
User = 3
Employee = 102
Role = 6
Permission = 39
RolePermission = 57
UserRoleScopeAssignment = 2
```

测试后：

```text
PurchaseOrder = 218
SupplierMaterialPrice = 28（只记录结束值；本轮未调用价格写接口）
User = 5
Employee = 104
Role = 8
Permission = 39
RolePermission = 58
UserRoleScopeAssignment = 4
```

本轮新增且保留的专用回归事实：

- User：2；
- Employee：2；
- Role：2；
- RolePermission：1（只给部门查看角色授予目录查看动作）；
- UserRoleScopeAssignment：2；
- PurchaseOrder：0；
- Permission：0；
- SupplierMaterialPrice：0 次写动作；
- Workflow/Gate 状态推进：0。

两套测试关系保留为后续 V1 回归身份，均为 active。没有清理它们，因为正式管理 API 当前没有删除 User/Employee/Role 的安全操作，并且直接数据库清理被本轮明确禁止。既有 `pce_buyer_r10`、`pce_direct_r10` 未修改。

## 9. 采购保护

| 保护对象 | 结果 | 证据 |
|---|---|---|
| 直接采购/采购订单创建入口 | PASS | 页面正常加载，未点击创建；`H11-purchase-order-create-readonly-check.png` |
| SupplierMaterialPrice | PASS | 页面与既有人工维护权限控件正常，仅查看；`H12-supplier-material-price-readonly-check.png` |
| PurchaseOrderGate | PASS | 准入页面正常显示，未修改/推进；`H13-purchase-order-gate-readonly-check.png` |
| PurchaseOrder 数量 | PASS | 218 → 218，本轮新增 0 |

## 10. 自动回归

| 项目 | 结果 | 真实输出 |
|---|---|---|
| Django check | PASS | `System check identified no issues (0 silenced)` |
| 组织权限核心 + R10 | PASS | 19/19，`Ran 19 tests in 1.377s / OK` |
| R5.1 | PASS | 4/4，`Ran 4 tests in 1.726s / OK` |
| Vite 生产编译 | PASS | 2,533 modules transformed，built in 2.93s |
| Full npm build | BLOCKED | 既有 PCE-WEB-ACCEPTANCE-V1.1 的 7 个 SCM blocker；未进入 Vite build 阶段 |

直接 Vite 编译只有既有依赖注释、动态 import 和大 chunk 警告，没有编译错误。

## 11. Full Build 与 SG01–SG07

准确状态：

```text
Full Build
=
BLOCKED BY EXISTING SCM STATIC GATES
（被既有 SCM 静态门禁阻断）
```

7 个 blocker 仍为：

1. 采购询价快捷搜索字段；
2. 采购询价高级筛选；
3. 询价下一流程验收快捷搜索字段；
4. 询价下一流程验收高级筛选；
5. 供应商绩效高级筛选字段数；
6. 采购员绩效高级筛选字段数；
7. 采购异常责任分析高级筛选字段数。

这些 blocker 与组织权限核心 V1 无关，本轮没有修复、弱化或隐藏它们；因此不能宣称 Full Build PASS，也不把它们误判为权限核心功能 FAIL。

## 12. 截图证据

本次浏览器会话证据目录：`frontend/test-results/pce-organization-access-core-v1-final/`

- `H01-H02-admin-all-allow.png`
- `H03-H04-H09-deny-user-browser.png`
- `H05-H10-department-user-browser.png`
- `H11-purchase-order-create-readonly-check.png`
- `H12-supplier-material-price-readonly-check.png`
- `H13-purchase-order-gate-readonly-check.png`

六张截图均来自本轮真实浏览器会话，不复用历史截图。

## 13. 治理检查与封板门禁

```text
Governance Files Loaded: PASS
Frozen Asset Check: PASS（未修改已冻结权限核心或采购资产）
Identity Check: PASS（User/Employee/Department/Position/Role/Scope 分离）
Data Extract Check: PASS（Profile/API/Page 使用同一服务端授权事实）
Array Completeness: PASS（admin 16、DENY 0、DEPARTMENT 1；与 API 一致）
Regression Check: PASS（R10 19/19、R5.1 4/4、采购三页面可用）
Automatic Acceptance: PASS（本任务规定专项）
Browser Automatic Acceptance: PASS
Real Browser Evidence: PASS
Human Acceptance: PASS（用户已于 2026-08-16 明确签发“人工验收通过”）
Build: BLOCKED BY EXISTING SCM STATIC GATES
Ready Gate: FAIL
Scoped V1 Baseline: PASS
Permission Workstream: CLOSED
```

按照 `docs/governance/真实运行验收规范.md` 第 9 节，`Human Acceptance: PASS` 必须来自用户明确反馈。用户已在审核本报告原文及本轮真实浏览器截图后完成明确签发，因此专项可记录为：

```text
PCE ORGANIZATION & ACCESS CORE V1 = BASELINE
Human Acceptance = PASS
权限专项 = CLOSED
```

Full Build 仍被既有 SCM 静态门禁阻断，所以 `Ready Gate` 保持 `FAIL`。此处 `BASELINE` 是用户签发的权限专项正式基线，不代表 Full Project Build PASS，也不代表全项目 READY。

## 14. 最终结论

H01–H17 的适用技术验证全部通过：管理员 ALL、普通用户 DENY、后端 403、部门用户单部门范围、正式 Department、Scope 分离、Profile 差异、URL 不可绕过、Position/Role 分离、采购保护和零订单写入均有真实证据。

用户已在查看本报告与本次截图后明确签发“人工验收通过”。本轮最终状态分别记录为：

```text
PCE 公共组织身份权限核心 V1 = BASELINE（正式基线）
Human Acceptance = PASS（通过）
权限专项 = CLOSED（正式结束）
Full Project Build = BLOCKED BY EXISTING SCM STATIC GATES
Ready Gate = FAIL
```

权限专项至此封板并停止开发；两套专用权限回归账户继续保留为后续 V1 自动/人工回归身份。不进入 V1.1、V2、复杂 AI 权限、CUSTOM Scope 或大规模历史权限迁移。SCM 7 项历史静态门禁等待新的独立指令处理。

## 15. 用户最终签发记录

签发日期：2026-08-16  
签发主体：用户人工审核  
审核材料：本报告完整原文及本轮真实浏览器截图  
签发结论：`Human Acceptance = PASS`；`PCE ORGANIZATION & ACCESS CORE V1 = BASELINE`。

用户同时确认：

- ADMIN 为 `ALL / ALLOW`；普通业务人员为 `DENY`，直接调用后端 API 返回 HTTP 403；部门业务人员为 `DEPARTMENT / ALLOW`，仅可访问授权部门数据；
- Department 与 Scope 分离，Position 与 Role 分离，Permission Profile 与 AuthorizationService 一致，手工输入 URL 不能绕过后端权限；
- 直接采购、SupplierMaterialPrice、PurchaseOrderGate 保护回归通过；PurchaseOrder 保持 `218 → 218`，本轮新增 0；
- 两套专用权限回归账户允许保留；
- Full Project Build 不得标记为 PASS，其准确状态为 `BLOCKED BY EXISTING SCM STATIC GATES`。
