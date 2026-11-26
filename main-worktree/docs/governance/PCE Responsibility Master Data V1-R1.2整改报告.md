# PCE Responsibility Master Data（责任主数据）V1-R1.2整改报告

## 1. 整改结论

R1.2 Data Source & Detail View Rectification（R1.2 责任事实来源与详情展示整改）已完成。

本轮建立了显式的 Responsibility API（责任数据接口）：

`GET /api/access-control/responsibilities/`

该接口以 `system.Responsibility` 为根查询对象，并在响应中明确返回：

`factSource = system.Responsibility`

责任列表和岗位责任选择框均直接读取该接口。PositionResponsibility（岗位职责关系）只用于保存岗位承担关系和计算详情中的关联岗位，不参与生成责任目录。

当前状态：

`R1.2 Automated Rectification = PASS`

`Human Acceptance（人工验收） = PENDING`

## 2. 人工验收问题

R1.1 已将 Responsibility Catalog（责任目录）从岗位页面拆为独立入口，但岗位责任下拉仍通过页面综合 `facts.responsibilities` 数组获得选项。

该数组虽然由服务端投影返回，但页面接口契约无法直接证明：

- 它以 Responsibility（职责/责任定义）为根事实；
- 它不是从岗位责任关系反向生成；
- 它不是上一轮页面缓存或临时状态；
- 它不依赖岗位、部门或员工信息推断。

同时，责任列表缺少关联岗位摘要和责任详情，管理员无法在一个正式查看闭环中确认基础信息、生命周期、岗位关系和审计证据。

## 3. 原因分析

问题属于读取契约和详情展示不足，不是数据模型问题。

原页面同时复用综合组织投影承载多个对象。对责任选择而言，服务端来源虽然正确，但没有独立 `factSource` 证据，也没有专用详情投影，因此人工验收无法快速判断责任选择的唯一事实来源。

现有模型已经足够：

- Responsibility（职责/责任定义）：责任目录根事实；
- PositionResponsibility（岗位职责关系）：岗位承担责任的关系事实；
- Position（岗位）：关系目标；
- OrganizationOperatingAuditRecord（组织运作审计记录）：创建和修改证据。

因此本轮不需要 Migration（数据库迁移）或平行模型。

## 4. 修改文件

| 文件 | 修改内容 |
|---|---|
| `backend/system/responsibility_catalog.py` | 新增只读责任目录投影服务，以 `system.Responsibility` 为根事实，附加岗位关系与审计摘要 |
| `backend/system/access_control_views.py` | 新增受统一授权服务保护的责任目录读取视图 |
| `backend/system/urls.py` | 注册责任目录读取接口 |
| `frontend/src/api/accessControl.js` | 增加责任目录及详情 API 调用 |
| `frontend/src/meta/pages/AccessControlFoundationPage.vue` | 责任列表改读专用 API，增加关联岗位数量、最后更新时间及责任详情窗口 |
| `frontend/src/meta/components/OrganizationOperatingAdminDialog.vue` | 岗位责任下拉改用独立 `responsibilityOptions`，显示事实来源说明 |
| `backend/system/tests_responsibility_master_data_r12.py` | 新增 RM-R1.2-01 至 RM-R1.2-06 自动测试 |
| `docs/governance/PCE Responsibility Master Data V1-R1.2整改报告.md` | 本整改报告 |

本轮未修改：

- AuthorizationService（统一授权服务）核心逻辑；
- OrganizationOperatingService（组织运作服务）核心逻辑；
- Permission Core（权限核心）；
- Responsibility、PositionResponsibility 或 PositionWorkflowResponsibility 的数据结构；
- Workflow Runtime（流程运行引擎）；
- ApprovalTask（审批任务）；
- 采购审批。

## 5. 数据来源调整

### 5.1 Responsibility API（责任数据接口）

列表读取：

```text
GET /api/access-control/responsibilities/
```

详情读取：

```text
GET /api/access-control/responsibilities/?id={responsibility_id}
```

接口契约：

`PCE-RESPONSIBILITY-CATALOG-V1`

来源证据：

| 响应字段 | 值 | 含义 |
|---|---|---|
| `factSource` | `system.Responsibility` | 责任目录唯一根事实 |
| `relationshipSource` | `system.PositionResponsibility` | 关联岗位只来自岗位职责关系 |
| `auditSource` | `system.OrganizationOperatingAuditRecord` | 详情审计信息来源 |

目录查询从 `Responsibility.objects` 开始。PositionResponsibility 只通过关联统计和详情查询附加到已经存在的责任，不可能反向生成责任选项。

### 5.2 页面加载链

`#/organization` 刷新时分别读取：

1. 组织与权限基础事实；
2. Responsibility API（责任数据接口）。

责任列表使用接口返回的 `items`。岗位责任分配窗口通过独立的 `responsibilityOptions` 属性接收同一接口结果，并在选择框下显示：

`数据来源：Responsibility API · system.Responsibility`

禁止来源保持：

- 不从 PositionResponsibility 反向生成；
- 不从岗位已存在关系提取目录；
- 不从岗位名称、部门名称或员工信息推断；
- 不从前端临时状态生成；
- 不自动创建 `PURCHASE_REQUEST_APPROVAL`。

### 5.3 保存链保持

岗位选择已有责任后，保存仍只执行：

```text
AuthorizationService
  ↓
OrganizationOperatingService
  ↓
PositionResponsibility
  ↓
OrganizationOperatingAuditRecord
```

不存在的责任标识会被服务端拒绝，不会隐式创建 Responsibility。

## 6. Responsibility List（责任列表）

列表保持简洁，显示：

- Responsibility Code（责任编码）；
- Responsibility Name（责任名称）；
- Business Domain（业务领域）；
- Status（状态）；
- Effective From（生效日期）；
- Effective To（失效日期）；
- 关联岗位数量；
- 最后更新时间。

列表不显示：

- Before（修改前）；
- After（修改后）；
- 完整审计记录。

这些信息保留在详情和正式审计事实中。

## 7. Responsibility Detail View（责任详情查看）

入口：

```text
#/organization
  ↓
责任管理
  ↓
查看详情
```

### 7.1 基础信息

- Responsibility Code（责任编码）；
- Responsibility Name（责任名称）；
- Business Domain（业务领域）；
- Description（说明）。

### 7.2 生命周期信息

- Status（状态）；
- Effective From（生效日期）；
- Effective To（失效日期）。

### 7.3 关系信息

- 关联岗位数量；
- 岗位编码；
- 岗位名称；
- 部门；
- 公司；
- `PRIMARY`（主责）或 `SUPPORTING`（协助）。

关联岗位只读取有效 PositionResponsibility 关系。

### 7.4 审计信息

- Created By（创建人）；
- Created Time（创建时间）；
- Last Modified By（最后修改人）；
- Last Modified Time（最后修改时间）；
- Reason（修改原因）。

创建信息取最早一条 `SAVE_RESPONSIBILITY` 审计，最后修改信息取最新一条责任审计。详情只读，不创建审计或业务数据。

## 8. 权限与服务边界

责任目录读取继续使用：

`system.organization.responsibility.manage`（组织责任维护权限）

读取接口调用既有 AuthorizationService（统一授权服务）完成服务端权限裁决。没有新增 `responsibility.detail.manage`、`responsibility.admin.v2` 或其他重复权限。

所有写操作仍通过既有 OrganizationOperatingService（组织运作服务）。本轮没有改变责任生命周期、有效期、编码、事务或审计写入规则。

## 9. 自动测试结果

执行范围：

```text
system.tests_responsibility_master_data_r12
system.tests_responsibility_master_data_r11
system.tests_responsibility_master_data_r1
system.tests_enterprise_organization_operating_model_v1
```

结果：24 项全部通过。

| 测试 | 验证内容 | 结果 |
|---|---|---|
| RM-R1.2-01 | 岗位责任选择来自 Responsibility API；有无岗位关系的责任均来自 `system.Responsibility` | PASS |
| RM-R1.2-02 | 岗位不能创建责任；无效责任标识被拒绝且不会隐式创建 | PASS |
| RM-R1.2-03 | 详情读取基础信息、生命周期、关联岗位及审计信息 | PASS |
| RM-R1.2-04 | 列表字段完整且不包含 Before、After 或完整审计 | PASS |
| RM-R1.2-05 | 连续刷新回读同一服务端责任事实 | PASS |
| RM-R1.2-06 | 无权限写接口返回 HTTP 403 | PASS |
| R1.1 专项回归 | 6 项 | PASS |
| R1 专项回归 | 7 项 | PASS |
| 企业组织模型回归 | 5 项 | PASS |

Django System Check（Django 系统检查）：0 个问题。

前端生产编译：

```text
npx vite build .
```

结果：PASS，2542 个模块完成转换和构建。第三方依赖注释和大分块提示为既有非阻塞警告。

`makemigrations --check --dry-run system` 返回 `No changes detected`，确认没有 Schema（数据结构）变化或遗漏迁移。

## 10. 数据保护结果

自动测试使用隔离测试数据库，没有修改正式开发库中的人工责任事实。

实库最终检查：

| 检查项 | 数量 |
|---|---:|
| Responsibility（职责/责任定义） | 1 |
| PositionResponsibility（岗位职责关系） | 0 |
| PositionWorkflowResponsibility（岗位流程责任关系） | 0 |
| ApprovalTask（审批任务） | 0 |
| PurchaseOrder（采购订单） | 218 |
| SupplierMaterialPrice（供应商物料价格） | 28 |
| Unauthorized Business Writes（未授权业务写入） | 0 |

当前 1 条 Responsibility 为人工维护事实，本轮保持不变。没有自动创建责任、岗位责任、流程责任、审批任务、采购订单或供应商物料价格。

## 11. Human Acceptance（人工验收）清单

### H-R1.2-01 责任列表

1. 使用 `superadmin` 登录。
2. 进入 `#/organization`。
3. 点击顶层“责任管理”。
4. 确认列表显示责任编码、名称、业务领域、状态、生效日期、失效日期、关联岗位数量和最后更新时间。
5. 刷新页面，确认责任数量仍为当前人工维护数量。

### H-R1.2-02 责任详情

1. 在责任列表点击“查看详情”。
2. 确认显示责任编码、名称、业务领域和说明。
3. 确认显示状态、生效日期和失效日期。
4. 确认显示关联岗位数量和岗位列表；没有关系时明确显示“暂无关联岗位”。
5. 确认显示创建人、创建时间、最后修改人、最后修改时间和修改原因。
6. 确认页面提示事实来源为 `Responsibility API · system.Responsibility`。

### H-R1.2-03 岗位选择已有责任

1. 进入“岗位管理”。
2. 编辑真实岗位并进入“职责分配”。
3. 确认责任选择框下显示数据来源说明。
4. 确认选择框内容与顶层责任目录一致。
5. 选择人工维护责任并保存岗位责任关系。
6. 刷新后确认关系仍存在，责任详情的关联岗位数量和列表同步更新。

### H-R1.2-04 禁止岗位创建责任

1. 检查岗位维护窗口全部 Tab。
2. 确认不存在责任创建表单、新增责任按钮或按岗位名称生成责任的功能。

### H-R1.2-05 数量保护

1. 操作前记录责任数量。
2. 仅浏览列表、详情和打开岗位选择框。
3. 刷新后再次确认责任数量。

通过条件：只读操作不增加 Responsibility；岗位分配只增加人工确认的 PositionResponsibility。

## 12. 停止边界

R1.2 完成后停止并等待人工验收。本轮未进入：

- R2；
- R5；
- R6；
- Responsibility Resolution Engine（责任解析引擎）；
- Shadow Mode（影子模式）；
- Workflow Runtime（流程运行引擎）切换。

最终原则：Responsibility（职责/责任定义）必须先作为独立企业事实存在，Position（岗位）只能承担责任，不能创造责任。
