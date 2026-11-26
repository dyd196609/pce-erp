# PCE 企业组织运作模型 V1——实施与人工验收交接报告

报告日期：2026-08-16  
状态：IMPLEMENTED / HUMAN ACCEPTANCE WAITING

---

## 1. 结论

PCE 企业组织运作模型 V1 的维护闭环、独立写权限、服务端授权、保存后回读、变更原因和审计事实已经实现。专项自动回归为 `16/16 PASS`；Vite 生产构建通过；真实浏览器已完成部门范围只读身份的页面与维护拒绝核验。

本报告不是人工验收通过证明。H01–H09 必须由用户本人使用管理员身份、在真实浏览器中选择可确认的业务事实并保存，因此当前状态为：

```text
Implementation = PASS
Specialized Automatic Tests = PASS
Read-only Browser Evidence = PASS
Human Acceptance H01-H09 = WAITING
Full Project Build = BLOCKED BY EXISTING SCM STATIC GATES
Ready Gate = FAIL
```

不得把 `WAITING` 改写成 `PASS`，也不得用自动测试替代用户人工保存、刷新和回读。

---

## 2. 本轮治理原则

> **本阶段取消成本中心、利润中心及其它经营中心设计。经营核算、绩效、成本、收入、费用、利润、投资回报等内容，待 PCE-ERP 管理运作体系及主要业务系统完成、产生真实业务数据后，再单独设计。**

本轮不扩展 V1.1、V2、复杂 AI 权限、CUSTOM Scope、完整 HR、自动流程执行或历史权限大迁移。AI 不得写入正式组织、岗位、人员或流程责任关系。

---

## 3. 引用审计与经营中心处置

| 对象 | 数据/引用结论 | 正式处置 |
|---|---|---|
| `system.CostCenter` | 0 条；关系引用 0；无正式外部消费者 | 由 `system.0007` 删除当前模型和关系投影 |
| `system.ProfitCenter` | 0 条；关系引用 0；无正式外部消费者 | 由 `system.0007` 删除当前模型和关系投影 |
| `system.0006_enterprise_organization_model_v1` | 已应用迁移历史 | 保留，不篡改迁移历史 |
| `masterdata.CostCenter` | 1 条；存在 PurchaseRequest、Project、Provider、API、页面、测试等真实消费者 | `TEMPORARY LEGACY`；保留、不迁移、不扩大使用 |

删除前数据库备份：

```text
D:\Dev-PCE\Source\backend\db.pre-enterprise-organization-operating-model-v1-20260816.sqlite3
SHA256 F60939F7FF1794821B99EF24FC9922BC1E9E17ACF2E1F2AB076BC8F19AD74604
```

---

## 4. 已实现的数据与关系维护

维护中心复用现有组织目录页面壳和企业级列表基座，按组织、部门、岗位/责任三组维护，不创建单一巨表。正式能力包括：

- OrganizationUnit：编码、名称、类型、上级组织单元、有效期、启停；
- Department：层级、所属组织单元、责任岗位、有效期、启停；
- Department 实际负责人：独立关联 Employee，不与责任岗位混同；
- JobFamily、JobLevel：创建、编辑、启停与岗位关联；
- Position：层级、岗位族、岗位等级、默认 Role、职责摘要、有效期、启停；
- Responsibility、PositionResponsibility：职责目录及岗位职责分配；
- EmployeeReportingRelation：员工与主管的正式汇报关系；
- PositionWorkflowResponsibility：按 `OWNER / APPROVER / REVIEWER / EXECUTOR` 维护岗位流程责任；
- OrganizationOperatingAuditRecord：每次成功写入记录操作者、原因、目标、Before、After 和时间。

部门“责任岗位”和“实际负责人”是两个独立字段；Position 与 Role 仍然独立。流程责任只是责任事实，不自动推进流程。

---

## 5. 权限与后端边界

新增并使用六项独立写权限：

```text
system.organization.structure.manage
system.organization.department.manage
system.organization.position.manage
system.organization.responsibility.manage
system.organization.reporting.manage
system.organization.workflow_responsibility.manage
```

真实库结果：六项权限均存在，只向 `superadmin` 形成 6 条 RolePermission 授予。页面只用于呈现当前 Permission Profile，最终边界由 AuthorizationService 在 POST 接口重新判定；无权限调用返回真实 HTTP 403。

写操作必须提交明确的 `reason`。服务端使用事务、对象公司归属检查、部门范围检查、有效期校验、组织/部门/岗位层级防环、员工自主管禁止和枚举白名单。前端隐藏或禁用按钮不是授权依据。

---

## 6. 正式动作清单

```text
SAVE_ORGANIZATION_UNIT
SAVE_DEPARTMENT
SAVE_DEPARTMENT_LEADER
SAVE_JOB_FAMILY
SAVE_JOB_LEVEL
SAVE_POSITION
SAVE_RESPONSIBILITY
SAVE_POSITION_RESPONSIBILITY
SAVE_REPORTING_RELATION
SAVE_WORKFLOW_RESPONSIBILITY
```

所有动作保存后刷新同一服务端事实并回读，审计和页面事实不使用上一页缓存，也不由前端重算补齐。

---

## 7. 真实库最终事实

```text
Permission = 45
新增维护 Permission = 6
新增维护 RolePermission = 6（superadmin）
OrganizationUnit = 18
Department = 16
Position = 35
JobFamily = 0
JobLevel = 0
Responsibility = 0
PositionResponsibility = 0
PositionWorkflowResponsibility = 0
EmployeeReportingRelation = 0
OrganizationLeadershipAssignment = 0
OrganizationOperatingAuditRecord = 0
masterdata.CostCenter = 1（TEMPORARY LEGACY）
PurchaseOrder = 218
SupplierMaterialPrice = 28
```

本轮没有自动补齐任何 JobFamily、JobLevel、负责人、汇报、职责或流程责任，没有根据名称推断正式事实。组织业务事实写入为 0；新增权限及其受控角色授予属于本轮治理迁移。

---

## 8. 自动验证结果

| 验证项 | 结果 |
|---|---|
| 组织运作模型、上一版组织模型、权限核心联合测试 | `16/16 PASS`，1.201s |
| 10 类保存、刷新、服务端回读和审计 | PASS（隔离测试库） |
| 无写权限直接调用后端 | PASS，HTTP 403 |
| 组织/部门/岗位层级防环及员工自主管 | PASS |
| 当前系统经营中心模型已取消 | PASS |
| Django system check | PASS |
| migrations check | PASS，No changes detected |
| Procurement R5.1 保护回归 | `4/4 PASS` |
| Vite production build | PASS，2538 modules |
| PurchaseOrder 保护 | `218 -> 218`，新增 0 |
| SupplierMaterialPrice 保护 | `28 -> 28`，新增 0 |

全项目 `npm run build` 不得标记为 PASS。其结果仍为 `1154/1161`，被既有 7 项 SCM 静态门禁阻断；本轮未修复、未绕过、未修改其结论。

---

## 9. 真实浏览器只读证据

已使用当前真实 `DEPARTMENT / ALLOW` 目录查看身份核验：

- `/organization-model`：仅见授权范围事实，结构维护权限为 DENY，维护入口禁用；
- `/organization-model/departments`：责任岗位与实际负责人分栏显示，维护权限为 DENY；
- `/organization-model/positions`：岗位、职责、汇报及流程责任维护权限均为 DENY，维护入口禁用；
- 页面不再显示或消费 system CostCenter / ProfitCenter。

证据文件：

```text
frontend/test-results/pce-enterprise-organization-operating-model-v1/EOM-OPS-V1-01-organization-readonly.jpg
frontend/test-results/pce-enterprise-organization-operating-model-v1/EOM-OPS-V1-02-department-responsibility.jpg
frontend/test-results/pce-enterprise-organization-operating-model-v1/EOM-OPS-V1-03-position-maintenance-deny.jpg
```

这组证据只证明只读身份和维护拒绝，不能代替管理员人工保存验收。

---

## 10. 用户本人 H01–H09 人工验收清单

请使用管理员身份登录 `localhost`，选择你能够确认的正式事实；若只是测试关系，必须使用清晰的 TEST / ACCEPTANCE 标识和原因，且不得把推断当作正式事实。每项均需执行“保存 → 页面刷新 → 浏览器整页刷新 → 服务端回读/审计确认”。

- [ ] H01：修改或确认一个 OrganizationUnit 上下级关系；刷新后仍存在。
- [ ] H02：为一个 Department 设置上级部门；刷新后仍存在且无层级环。
- [ ] H03：为一个 Department 设置责任 Position。
- [ ] H04：为一个 Department 设置实际负责人 Employee；页面显示真实姓名，并与责任岗位独立。
- [ ] H05：创建/选择 JobFamily 并关联一个 Position。
- [ ] H06：创建/选择 JobLevel 并关联一个 Position。
- [ ] H07：设置 Position A 的上级 Position B；岗位树真实变化且无环。
- [ ] H08：创建/选择 Responsibility，并分配给一个 Position。
- [ ] H09：查看或维护一个 Position 的默认 Role；确认 Position 与 Role 仍是两个独立对象。

配套闭环建议一并人工验证：

- [ ] 设置一条 EmployeeReportingRelation，确认员工不能成为自己的主管；
- [ ] 设置一条 PositionWorkflowResponsibility，确认责任类型为 OWNER/APPROVER/REVIEWER/EXECUTOR，且不会自动推进任何流程；
- [ ] 使用无维护权限身份手工输入维护页面 URL，并直接 POST 同一 API，确认后端仍返回 403；
- [ ] 在审计列表核对每次成功保存的操作者、原因、Before、After；
- [ ] 最后重新核对 PurchaseOrder 为 218、SupplierMaterialPrice 为 28。

人工验收完成前不得签发 `Human Acceptance = PASS`。

---

## 11. 当前封板状态

```text
PCE Enterprise Organization Operating Model V1 = IMPLEMENTED
Specialized Automatic Acceptance = PASS
Read-only Real Browser Evidence = PASS
Human Acceptance = WAITING FOR USER H01-H09
Full Project Build = BLOCKED BY EXISTING SCM STATIC GATES
Ready = FAIL
Unauthorized Business Writes = 0
PurchaseOrder Added = 0
SupplierMaterialPrice Added = 0
```

权限核心代码、PurchaseOrderGate、采购审批、采购订单和供应商物料价格均未为制造 PASS 而修改。下一步仅等待用户本人完成 H01–H09 并提供验收结论；本轮不进入 SCM 7 项历史门禁治理或任何后续扩展开发。
