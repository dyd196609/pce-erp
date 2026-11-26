# PCE Responsibility Master Data（责任主数据）V1-R1实施报告

## 1. 实施结论

本轮已在授权边界内完成 R1 Implementation（R1 阶段实施）：

- 对既有 `system.Responsibility` 完成唯一、最小的 Schema（数据结构）增量扩展；
- 在 `#/organization` 唯一正式入口完成 Responsibility（职责/责任定义）生命周期维护与 PositionResponsibility（岗位职责关系）分配；
- 所有写操作继续经过 AuthorizationService（统一授权服务）、OrganizationOperatingService（组织运作服务）与 OrganizationOperatingAuditRecord（组织运作审计记录）；
- 自动测试、保存回读、审计快照、权限隔离及采购保护验证通过；
- 未创建任何正式责任数据，未实施 Responsibility Resolution Engine（责任解析引擎），未运行 Shadow Mode（影子模式），未修改 Workflow Runtime（流程运行引擎）或 ApprovalTask（审批任务）。

当前状态：

`Responsibility Master Data V1 R1 Automated Closure = PASS`

`Human Acceptance（人工验收） = PENDING`

## 2. 修改文件清单

| 文件 | 修改内容 |
|---|---|
| `backend/system/models.py` | 在既有 `Responsibility` 增加状态与有效期字段；未新增平行模型 |
| `backend/system/migrations/0009_responsibility_lifecycle_v1.py` | 唯一受控增量 Migration（数据库迁移） |
| `backend/system/organization_operating.py` | 增加编码、生命周期、有效期和生效必填项校验；保持授权、事务和审计链 |
| `backend/system/enterprise_organization.py` | 服务端投影增加责任状态、中文状态、生效日期、失效日期和业务领域 |
| `backend/system/tests_responsibility_master_data_r1.py` | 新增 RM-R1-01 至 RM-R1-07 自动测试 |
| `backend/system/tests_enterprise_organization_operating_model_v1.py` | 适配“先草稿、后生效”的责任生命周期并更新合法审计数量 |
| `frontend/src/meta/components/OrganizationOperatingCatalogForm.vue` | 增加责任管理字段、生命周期选择、有效期和不可删除说明 |
| `frontend/src/meta/components/OrganizationOperatingAdminDialog.vue` | 在正式组织入口提供责任管理及主责/协助分配 |
| `frontend/src/meta/components/EnterpriseOrganizationModelView.vue` | 综合组织模型改为只读展示责任事实，避免形成第二个责任维护入口 |
| `backend/db.sqlite3` | 已应用唯一受控迁移；未写入责任或采购业务数据 |
| `backend/db.pre-responsibility-r1-schema-20260817.sqlite3` | 迁移前可恢复数据库备份 |

## 3. Migration（数据库迁移）

迁移名称：

`system.0009_responsibility_lifecycle_v1`

迁移依赖：

`system.0008_position_effective_period`

迁移只包含以下三个字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `status` | 受控字符枚举 | `DRAFT`、`ACTIVE`、`SUSPENDED`、`EXPIRED` |
| `effective_from` | 可空日期 | 责任开始有效日期 |
| `effective_to` | 可空日期 | 责任结束日期 |

明确未增加：

- `company_id`；
- `ResponsibilityV2` 或其他平行责任表；
- `PositionResponsibility` 的优先级或有效期字段；
- `PositionWorkflowResponsibility` 的任何字段。

迁移前检查：

| 检查项 | 结果 |
|---|---:|
| Responsibility（职责/责任定义） | 0 |
| PositionResponsibility（岗位职责关系） | 0 |
| PositionWorkflowResponsibility（岗位流程责任关系） | 0 |
| PurchaseOrder（采购订单） | 218 |
| SupplierMaterialPrice（供应商物料价格） | 28 |

迁移前数据库 SHA256（数据库摘要哈希）：

`9FC2A4B19716E84EB10F397BF94736CC69FFC6D1472C6FFB1849DD3A20036619`

备份文件 SHA256：

`9FC2A4B19716E84EB10F397BF94736CC69FFC6D1472C6FFB1849DD3A20036619`

迁移后数据库 SHA256：

`D43720A6259E213F63C8D3A6874919F2D11A391F7D5F8BAD59809A086A245516`

迁移状态：`[X] 0009_responsibility_lifecycle_v1`。

## 4. Schema（数据结构）变化

Responsibility（职责/责任定义）继续是 Global Responsibility Catalog（全局责任目录），不归属单一公司。原有字段 `code`、`name`、`description`、`category`、`is_active` 保留；本轮只增加已授权的三个生命周期字段。

状态语义：

| 状态 | 中文说明 | 运行含义 |
|---|---|---|
| `DRAFT` | 草稿 | 可维护，尚未生效 |
| `ACTIVE` | 生效 | 当前有效，`is_active=true` |
| `SUSPENDED` | 暂停 | 暂停承担，`is_active=false` |
| `EXPIRED` | 失效 | 历史终态，`is_active=false` |

`is_active` 保留用于兼容既有读取关系，但由服务根据 `status` 同步，不作为页面独立生命周期输入。

PositionResponsibility（岗位职责关系）结构保持不变：

- `is_primary=true` 表示 `PRIMARY`（主责）；
- `is_primary=false` 表示 `SUPPORTING`（协助）；
- `active` 表示关系是否有效。

## 5. 服务变化

### 5.1 编码校验

责任编码必须使用大写业务对象与责任目的，至少三个下划线分隔部分，例如：

`PURCHASE_REQUEST_APPROVAL`

不会根据岗位名称、部门名称或员工姓名自动生成责任编码或责任数据。

### 5.2 生命周期校验

允许的状态转换：

- `DRAFT -> ACTIVE`；
- `DRAFT -> EXPIRED`；
- `ACTIVE -> SUSPENDED`；
- `ACTIVE -> EXPIRED`；
- `SUSPENDED -> ACTIVE`；
- `SUSPENDED -> EXPIRED`。

禁止：

- 新责任跳过草稿直接生效；
- `EXPIRED -> ACTIVE`；
- 其他未声明状态转换；
- 非草稿责任修改责任编码；
- 物理删除历史责任。

责任进入 `ACTIVE` 时必须填写：责任说明、业务领域、生效日期。

### 5.3 有效期校验

当两个日期同时存在时，必须满足：

`effective_to >= effective_from`

无效日期格式或失效日期早于生效日期均由服务端拒绝。

### 5.4 保存与回读

沿用现有接口：

- `POST /api/access-control/enterprise-organization-model/`
- `GET /api/access-control/enterprise-organization-model/`

写动作继续使用：

- `SAVE_RESPONSIBILITY`；
- `SAVE_POSITION_RESPONSIBILITY`。

读取投影返回 `businessDomain`、`status`、`statusLabel`、`effectiveFrom`、`effectiveTo` 与 `isActive`，页面刷新后从同一服务端事实回读，不使用前端缓存重建事实。

## 6. 页面变化

唯一正式维护入口保持：

`#/organization -> 岗位 -> 责任管理 / 职责分配`

责任管理支持：

- 责任编码；
- 责任名称；
- 责任说明；
- 业务领域；
- 状态；
- 生效日期；
- 失效日期；
- 修改原因；
- 保存并回读。

职责分配支持管理员明确选择岗位、责任和承担类型：

- `PRIMARY`（主责）；
- `SUPPORTING`（协助）。

页面不提供删除责任按钮，也不会根据岗位名称自动选择或生成责任。

`#/organization-model` 继续读取相同服务端事实，但责任及岗位责任区域改为只读综合展示，并提示管理员回到正式组织入口维护。

## 7. Permission（权限）验证

本轮未新增、未修改权限体系，继续复用：

`system.organization.responsibility.manage`（组织责任维护权限）

保存调用链：

`页面 -> AuthorizationService -> Permission -> OrganizationOperatingService -> OrganizationOperatingAuditRecord`

无权限用户调用写接口返回 HTTP 403，且没有产生责任数据或审计数据。AuthorizationService（统一授权服务）与 Permission Core（权限核心）均未修改。

## 8. Audit（审计）结果

每次成功创建、修改状态或分配岗位责任，继续写入 OrganizationOperatingAuditRecord（组织运作审计记录），包含：

- Before（修改前）；
- After（修改后）；
- Operator（操作者）；
- Reason（修改原因）；
- Time（时间）。

RM-R1-06 已验证草稿变为生效时：

- `before.status = DRAFT`；
- `after.status = ACTIVE`；
- 操作者、原因和时间均存在。

未新增责任专用审计表。

## 9. 自动测试结果

执行命令：

```text
python manage.py test system.tests_responsibility_master_data_r1 system.tests_enterprise_organization_operating_model_v1
```

结果：12 项测试全部通过，其中 R1 专项 7 项。

| 编号 | 验证内容 | 结果 |
|---|---|---|
| RM-R1-01 | 创建草稿责任 | PASS |
| RM-R1-02 | 责任编码唯一 | PASS |
| RM-R1-03 | 生命周期转换及失效后禁止恢复 | PASS |
| RM-R1-04 | 有效期校验 | PASS |
| RM-R1-05 | 无权限用户 HTTP 403 | PASS |
| RM-R1-06 | 审计 Before/After、操作者、原因 | PASS |
| RM-R1-07 | 岗位责任绑定、刷新回读、采购保护 | PASS |
| 既有组织模型回归 | 5 项 | PASS |

Django System Check（Django 系统检查）：0 个问题。

前端验证：

- `npx vite build .`：PASS，2542 个模块完成生产编译；
- `npm run build`：在进入 Vite 编译前被仓库既有 7 项 SCM Static Gate（供应链静态门禁）缺口拦截，涉及采购询价及绩效页面高级筛选，与本轮责任主数据修改无关；本轮未越权修改这些采购/SCM 页面。

## 10. 数据库与采购保护结果

迁移后实库检查：

| 检查项 | 结果 |
|---|---:|
| Responsibility（职责/责任定义） | 0 |
| PositionResponsibility（岗位职责关系） | 0 |
| PositionWorkflowResponsibility（岗位流程责任关系） | 0 |
| PurchaseOrder（采购订单） | 218 |
| SupplierMaterialPrice（供应商物料价格） | 28 |
| Unauthorized Business Writes（未授权业务写入） | 0 |

结论：没有自动创建责任、岗位责任或流程责任；没有创建采购订单，没有修改供应商物料价格事实，没有发生未授权业务写入。

## 11. 明确未实施范围

本轮没有：

- 实施 Responsibility Resolution Engine（责任解析引擎）；
- 运行 Shadow Mode（影子模式）；
- 修改 Workflow Runtime（流程运行引擎）；
- 修改 ApprovalTask（审批任务）；
- 切换 Purchase Request（采购申请）审批；
- 修改 Permission（权限）体系；
- 自动创建 `PURCHASE_REQUEST_APPROVAL` 或任何正式责任；
- 进入 R2、R5 或 R6。

## 12. Human Acceptance（人工验收）清单

请使用 `superadmin` 执行：

1. 进入 `#/organization`。
2. 进入“岗位”，打开正式维护窗口并选择“责任管理”。
3. 确认可以看到责任编码、责任名称、责任说明、业务领域、状态、生效日期、失效日期、修改原因。
4. 人工创建第一条草稿责任，例如 `PURCHASE_REQUEST_APPROVAL`，填写修改原因并保存。
5. 刷新页面，确认草稿责任仍存在且字段一致。
6. 编辑该责任，填写责任说明、业务领域和生效日期，将状态改为“生效”并保存。
7. 刷新页面，确认状态仍为“生效”。
8. 进入“职责分配”，选择真实岗位、该责任及“主责”或“协助”，填写原因并保存。
9. 刷新后确认岗位责任关系仍存在；进入 `#/organization-model` 确认只读综合展示来自同一服务端事实。
10. 查看组织运作审计，确认创建、生效和岗位分配记录均包含操作者、时间、原因、Before 与 After。
11. 验证无权限账户写入返回 HTTP 403。
12. 验证页面没有删除历史责任入口，失效责任不能恢复生效。

人工验收通过前，不启动责任解析、影子模式、流程切换或后续阶段。

## 13. 最终状态

`Responsibility Master Data V1 R1 = IMPLEMENTED`

`Automated Test = PASS`

`Schema Migration = PASS`

`Audit and Refresh Readback = PASS`

`Purchase Protection = PASS`

`Human Acceptance = PENDING`

R1 在此停止，等待人工验收，不进入 R2/R5/R6。
