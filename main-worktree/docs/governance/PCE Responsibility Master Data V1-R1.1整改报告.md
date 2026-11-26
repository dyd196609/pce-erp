# PCE Responsibility Master Data（责任主数据）V1-R1.1整改报告

## 1. 整改结论

R1.1 Rectification（R1.1 整改）已完成。

Responsibility Catalog（责任目录）现在作为 `#/organization` 的顶层独立“责任管理”入口维护。Position（岗位）维护窗口已移除创建或编辑 Responsibility（职责/责任定义）的能力，只保留从既有责任目录选择并建立 PositionResponsibility（岗位职责关系）。

最终页面语义为：

```text
责任管理
  ↓ 独立定义 Responsibility
岗位管理
  ↓ 选择已有 Responsibility
PositionResponsibility
  ↓
Position 承担责任
```

当前状态：

`R1.1 Automated Rectification = PASS`

`Human Acceptance（人工验收） = PENDING`

## 2. 问题原因

R1 已经在数据模型和服务端保持 Responsibility（职责/责任定义）独立，但前端把责任目录表单放在“岗位管理”的内部维护窗口中，形成了以下错误操作语义：

```text
岗位编辑 → 责任管理 → 创建责任
```

这容易让管理员理解为岗位创建责任，与正式架构“责任先独立定义、岗位再承担责任”不一致。

根因是页面信息架构错误，不是数据模型错误。既有 Responsibility、PositionResponsibility、授权、审计和生命周期服务均可复用，无需新增模型或 Migration（数据库迁移）。

## 3. 修改文件

| 文件 | 修改内容 |
|---|---|
| `frontend/src/meta/pages/AccessControlFoundationPage.vue` | 增加顶层“责任管理”Tab、责任目录列表、筛选、计数及新增/编辑入口 |
| `frontend/src/meta/components/OrganizationOperatingAdminDialog.vue` | 增加独立责任目录维护区；从岗位窗口移除责任创建表单；岗位只保留已有责任分配 |
| `frontend/src/meta/components/OrganizationOperatingCatalogForm.vue` | 支持顶层入口传入现有责任并独立新建、编辑和生命周期维护 |
| `backend/system/tests_responsibility_master_data_r11.py` | 新增 RM-R1.1-01 至 RM-R1.1-06 专项测试 |
| `backend/system/tests_responsibility_master_data_r1.py` | 将旧审计测试的“最新记录”判定改为稳定的审计主键倒序 |
| `docs/governance/PCE Responsibility Master Data V1-R1.1整改报告.md` | 本整改报告 |

本轮未修改：

- `backend/system/models.py`；
- 任何 Migration（数据库迁移）；
- PositionResponsibility（岗位职责关系）结构；
- PositionWorkflowResponsibility（岗位流程责任关系）结构；
- Workflow Runtime（流程运行引擎）；
- ApprovalTask（审批任务）；
- AuthorizationService（统一授权服务）；
- Permission Core（权限核心）。

## 4. 页面变化

### 4.1 顶层责任目录入口

正式入口：

```text
#/organization
  ↓
责任管理
```

“责任管理”与“部门管理”“岗位管理”“员工档案”等处于同一导航层级，不再依附于某个岗位。

责任目录列表显示：

- Responsibility Code（责任编码）；
- Responsibility Name（责任名称）；
- Description（说明）；
- Business Domain（业务领域）；
- Status（状态）；
- Effective From（生效日期）；
- Effective To（失效日期）。

支持按编码、名称、业务领域和状态筛选，支持独立新增、编辑、刷新回读。

责任维护表单继续要求 Reason（修改原因），并支持：

- `DRAFT`（草稿）；
- `ACTIVE`（生效）；
- `SUSPENDED`（暂停）；
- `EXPIRED`（失效）。

### 4.2 岗位责任分配

岗位维护窗口删除了原“责任管理”Tab，不再包含 Responsibility 创建或编辑表单。

岗位窗口保留“职责分配”，管理员只能：

1. 选择岗位；
2. 从服务端责任目录选择已有责任；
3. 选择 `PRIMARY`（主责）或 `SUPPORTING`（协助）；
4. 填写修改原因；
5. 保存并回读岗位责任关系。

页面明确提示：新责任必须在顶层“责任管理”中独立创建。

### 4.3 唯一事实来源

顶层责任目录、岗位责任选择框及综合组织模型继续读取同一服务端 `responsibilities` 投影。页面不缓存生成责任，不根据岗位、部门或员工名称推导责任。

## 5. 服务变化

本轮无需修改 OrganizationOperatingService（组织运作服务）核心实现。既有接口已经支持不依赖岗位的独立责任创建和查询：

- `SAVE_RESPONSIBILITY`：独立创建或维护责任；不接受岗位作为创建前提；
- `SAVE_POSITION_RESPONSIBILITY`：仅接收已存在的责任标识；责任不存在时返回校验错误，不会隐式创建；
- `GET /api/access-control/enterprise-organization-model/`：返回责任目录正式服务端事实。

生命周期校验保持 R1 规则，失效责任不能恢复生效，有效期必须满足 `effective_to >= effective_from`，历史责任不提供物理删除。

## 6. 权限与审计

继续复用：

`system.organization.responsibility.manage`（组织责任维护权限）

责任创建与修改调用链保持：

```text
页面
  ↓
AuthorizationService
  ↓
Permission
  ↓
OrganizationOperatingService
  ↓
OrganizationOperatingAuditRecord
```

未新增权限点或责任专用审计表。

每次成功创建或修改继续记录：

- Before（修改前）；
- After（修改后）；
- Operator（操作者）；
- Reason（修改原因）；
- Time（时间）。

RM-R1.1-05 已验证创建审计的 Before 为空对象，After 包含 `DRAFT` 状态，并包含操作者、修改原因和创建时间。

## 7. 自动测试结果

执行范围：

```text
system.tests_responsibility_master_data_r11
system.tests_responsibility_master_data_r1
system.tests_enterprise_organization_operating_model_v1
```

结果：18 项全部通过。

| 测试 | 验证内容 | 结果 |
|---|---|---|
| RM-R1.1-01 | 顶层责任目录可独立创建；不会同时创建岗位责任 | PASS |
| RM-R1.1-02 | 岗位只能绑定已有责任；不存在的责任不会被隐式创建；岗位区域不存在责任创建表单 | PASS |
| RM-R1.1-03 | 草稿、生效、暂停、失效生命周期及失效终态保持有效 | PASS |
| RM-R1.1-04 | 无权限创建责任返回 HTTP 403 | PASS |
| RM-R1.1-05 | 审计 Before、After、Operator、Reason、Time 完整 | PASS |
| RM-R1.1-06 | 刷新后从同一服务端投影回读责任事实 | PASS |
| R1 专项回归 | 7 项 | PASS |
| 企业组织模型回归 | 5 项 | PASS |

Django System Check（Django 系统检查）：0 个问题。

前端生产编译：

```text
npx vite build .
```

结果：PASS，2542 个模块完成转换和构建。第三方依赖纯注释及大分块提示为既有非阻塞警告。

## 8. 数据保护结果

整改前后未执行正式责任创建，自动测试只使用事务隔离测试数据库。

实库最终检查：

| 检查项 | 数量 |
|---|---:|
| Responsibility（职责/责任定义） | 0 |
| PositionResponsibility（岗位职责关系） | 0 |
| PositionWorkflowResponsibility（岗位流程责任关系） | 0 |
| ApprovalTask（审批任务） | 0 |
| PurchaseOrder（采购订单） | 218 |
| SupplierMaterialPrice（供应商物料价格） | 28 |
| Unauthorized Business Writes（未授权业务写入） | 0 |

未创建采购订单、供应商价格、责任数据、岗位责任数据或流程任务。

`makemigrations --check --dry-run system` 结果为 `No changes detected`，确认本轮没有 Schema（数据结构）变化或遗漏迁移。

## 9. Human Acceptance（人工验收）清单

### H-R1.1-01 独立入口

1. 使用 `superadmin` 登录。
2. 进入 `#/organization`。
3. 确认顶层导航存在“责任管理”，且与“岗位管理”处于同一层级。
4. 点击“责任管理”，确认显示责任目录列表及新增/维护责任按钮。

通过条件：无需进入岗位即可进入 Responsibility Catalog（责任目录）。

### H-R1.1-02 独立创建责任

1. 在“责任管理”点击新增责任。
2. 输入：
   - 责任编码：`PURCHASE_REQUEST_APPROVAL`；
   - 责任名称：采购申请审批责任；
   - 说明：采购申请的正式审批责任；
   - 业务领域：采购；
   - 状态：草稿；
   - 修改原因：R1.1 人工验收创建。
3. 保存。

通过条件：责任独立创建成功，没有要求选择岗位，也没有自动创建岗位责任关系。

### H-R1.1-03 刷新回读

1. 刷新浏览器页面。
2. 重新进入“责任管理”。
3. 搜索 `PURCHASE_REQUEST_APPROVAL`。
4. 打开编辑窗口。

通过条件：编码、名称、说明、业务领域和草稿状态均与保存内容一致。

### H-R1.1-04 岗位选择已有责任

1. 进入“岗位管理”。
2. 编辑真实岗位，例如采购经理岗位。
3. 进入“职责分配”。
4. 从责任选择框选择已创建的 `PURCHASE_REQUEST_APPROVAL`。
5. 选择“主责”，填写修改原因并保存。
6. 刷新后重新检查。

通过条件：岗位责任关系真实存在并可回读，责任来源是已有责任目录。

### H-R1.1-05 岗位不能创建责任

1. 检查岗位维护窗口的全部 Tab。
2. 确认不存在“责任管理”创建表单。
3. 确认“职责分配”只有已有责任选择框，没有新增责任按钮或自动生成选项。

通过条件：岗位只能承担责任，不能定义或创建责任。

### H-R1.1-06 审计

1. 查看最近组织维护审计。
2. 找到责任创建和岗位责任分配记录。
3. 核对操作者、时间、修改原因、Before 和 After。

通过条件：两类操作均有完整 OrganizationOperatingAuditRecord（组织运作审计记录）。

## 10. 停止边界

R1.1 完成后停止。本轮未进入且不得自动继续：

- R2；
- R5；
- R6；
- Responsibility Resolution Engine（责任解析引擎）；
- Shadow Mode（影子模式）；
- Workflow Runtime（流程运行引擎）切换。

最终原则：责任先独立定义，再由岗位承担。岗位不是责任的创建者，而是责任的承载者。
