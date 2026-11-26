# PCE Responsibility Master Data（责任主数据）V1——R1 Schema 扩展授权前设计说明

报告日期：2026-08-17  
任务类型：R1 Pre-implementation Stop Report（R1实施前停止说明）  
当前状态：SCHEMA AUTHORIZATION REQUIRED / IMPLEMENTATION NOT STARTED（需要数据结构授权/实施未开始）

---

## 1. 停止结论

R1 实施前检查触发了用户指令中的强制停止条件：当前既有 Responsibility（职责/责任定义）无法持久化 R1 要求的四状态和有效期。若不进行 Schema（数据结构）扩展，页面只能产生前端伪字段、临时推导或语义复用，违反单一服务端事实原则。

因此本轮已停止：

```text
Code Implementation（代码实施）= NOT STARTED
Database Change（数据库变更）= NO
Migration（数据库迁移）= NOT CREATED
Responsibility Data（正式责任数据）= NOT CREATED
Workflow Runtime（流程运行引擎）= NOT CHANGED
ApprovalTask（审批任务）= NOT CHANGED
Permission（权限）= NOT CHANGED
Purchase Approval（采购审批）= NOT CHANGED
```

不得生成 `PCE Responsibility Master Data V1-R1实施报告.md`，因为 R1 尚未完成。获得新的 Migration 授权后，才能恢复 R1 实施。

---

## 2. 已完整复核的依据

- `docs/governance/PCE Responsibility Master Data V1设计报告.md`
- `docs/governance/PCE Responsibility Master Data V1实施计划设计报告.md`
- `docs/governance/PCE责任解析引擎V1设计报告.md`
- `docs/governance/PCE责任解析引擎V1实施前架构审核与设计确认报告.md`
- `docs/governance/PCE企业组织运作模型V1-数据驱动架构审计报告.md`
- `docs/governance/PCE企业组织运作模型V1-正式管理员入口统一与维护闭环整改报告.md`
- `docs/governance/PCE企业组织运作模型V1-员工直属主管维护闭环报告.md`
- `docs/standards/PCE-BUSINESS-ACTION-PERMISSION-V1.0.md`
- `docs/governance/PCE公共组织身份权限核心V1-最终人工验收与封板报告.md`

权限封板文件在仓库中的正式文件名包含连接符，已按实际文件读取。

---

## 3. 当前模型事实

### 3.1 Responsibility

当前字段：

```text
code
name
description
category
is_active
```

缺少：

```text
status
effective_from
effective_to
```

`is_active` 是布尔字段，只能表达两个值，不能无歧义区分：

```text
DRAFT（草稿）
ACTIVE（生效）
SUSPENDED（暂停）
EXPIRED（失效）
```

同时，现有模型没有存储 Effective From（生效日期）和 Effective To（失效日期）的位置。

### 3.2 PositionResponsibility（岗位职责关系）

当前字段：

```text
position
responsibility
is_primary
active
```

R1 要求的责任类型可以无损复用：

```text
is_primary = true  → PRIMARY（主责）
is_primary = false → SUPPORTING（协助）
```

因此本轮不需要为了 PRIMARY/SUPPORTING 新增类型字段或新关系表。

### 3.3 Business Domain（业务领域）

现有 `Responsibility.category` 可以在 R1 受控承载 Business Domain，不新增 `business_domain` 同义字段。实施前必须确认 category 仍无其它正式语义；当前 Responsibility 数量为 0。

---

## 4. 为什么不能在零 Schema 变更下实施

| 替代方式 | 问题 | 结论 |
|---|---|---|
| 用 `is_active=true/false` 表达四状态 | DRAFT、SUSPENDED、EXPIRED 会合并为同一值 | 禁止 |
| 用 `category` 拼接状态或日期 | 一个字段承载业务领域和生命周期两种语义 | 禁止 |
| 只在前端保存状态 | 刷新丢失，API、审计和页面事实不一致 | 禁止 |
| 根据日期动态推导全部状态 | 当前无日期字段，且无法区分草稿与暂停 | 禁止 |
| 把状态写入 description | 非结构化、不可校验、不可筛选 | 禁止 |
| 新建 ResponsibilityV2 | 形成第二责任模型 | 禁止 |

结论：完成 R1 责任维护闭环必须获得最小 Schema/Migration 授权。

---

## 5. 最小必需 Schema 扩展方案

仅扩展既有 `system.Responsibility`：

| 字段 | 建议定义 | 默认/空值 | 用途 |
|---|---|---|---|
| `status` | `CharField(max_length=20, choices=...)` | 默认 `DRAFT` | 唯一生命周期状态事实 |
| `effective_from` | `DateField(null=True, blank=True)` | DRAFT 可空 | 生效日期；激活时服务校验必填 |
| `effective_to` | `DateField(null=True, blank=True)` | 可空 | 失效日期 |

状态枚举：

```text
DRAFT
ACTIVE
SUSPENDED
EXPIRED
```

数据库约束建议：

```text
effective_to IS NULL
OR effective_from IS NULL
OR effective_to >= effective_from
```

服务端约束：

1. ACTIVE 必须具有 effective_from；
2. code 符合 `^[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)*$`；
3. code 进入 ACTIVE 后不可修改；
4. 生命周期只允许：
   - DRAFT → ACTIVE；
   - DRAFT → EXPIRED；
   - ACTIVE → SUSPENDED；
   - ACTIVE → EXPIRED；
   - SUSPENDED → ACTIVE；
   - SUSPENDED → EXPIRED；
5. EXPIRED 不可恢复；
6. 责任不可物理删除；
7. `is_active` 暂时保留为兼容投影，由服务端按 `status == ACTIVE` 单向同步，不允许页面独立维护。

---

## 6. Migration 设计边界

建议未来创建一个受控增量迁移，名称由 Django（服务端框架）实际迁移序号决定，例如：

```text
system.00xx_responsibility_lifecycle_v1
```

迁移必须：

- 只增加上述三个字段和有效期检查约束；
- 不新建 ResponsibilityV2、PositionResponsibilityV2 或映射表；
- 不创建任何 Responsibility 正式数据；
- 不根据岗位、部门、员工或旧审批文本生成责任；
- 不修改 Permission Registry（权限注册中心）；
- 不修改 Workflow Runtime、ApprovalTask 或采购审批；
- 在应用前创建数据库备份并记录 SHA256（摘要哈希）；
- 应用前确认 Responsibility 数量仍为 0；若已非 0，停止并重新设计数据迁移策略；
- 应用后确认 PurchaseOrder 和 SupplierMaterialPrice 数量不变；
- 支持反向移除新增字段，但正式数据产生后不得直接执行破坏性反向迁移。

### 6.1 本次不建议纳入的扩展

以下是已批准总体架构中的后续关系增强，但不是当前 R1 生命周期闭环的最小阻断项：

```text
PositionResponsibility.priority
PositionResponsibility.effective_from
PositionResponsibility.effective_to
PositionWorkflowResponsibility.responsibility NOT NULL
```

为避免借 Migration 授权扩大本轮范围，建议另行决定是否与生命周期迁移合并。本 R1 可先继续使用既有 `is_primary/active` 完成 PRIMARY/SUPPORTING 关系维护；关系有效期间与流程责任强化可进入后续明确授权。

---

## 7. Migration 获批后的 R1 恢复范围

获得新授权后，只允许恢复以下工作：

1. 扩展既有 Responsibility 模型和受控 Migration；
2. 扩展 OrganizationOperatingService 的责任编码、生命周期、有效期和不可删除校验；
3. 继续复用 `system.organization.responsibility.manage`；
4. 在 `#/organization` 增强责任管理与岗位责任维护；
5. PositionResponsibility 继续复用 `is_primary` 表达 PRIMARY/SUPPORTING；
6. 所有成功修改写 OrganizationOperatingAuditRecord（组织运作审计记录）；
7. 增加 RM-R1-01～RM-R1-07 测试；
8. 保存后刷新并回读同一服务端事实；
9. 生成正式 R1 实施报告和人工验收清单。

继续禁止：责任解析引擎、Shadow Mode（影子模式）、流程接入、ApprovalTask、采购审批和自动责任数据。

---

## 8. 请求的下一步授权

建议下一条指令明确授权：

```text
允许对既有 system.Responsibility 增加：
- status
- effective_from
- effective_to
- 有效期数据库检查约束

允许创建并应用一条受控 system Migration；
禁止任何责任数据初始化；
授权恢复 R1 页面、服务、审计、回读和 RM-R1-01～RM-R1-07 测试；
其余 Workflow、ApprovalTask、责任解析、Shadow、Permission 和采购范围继续冻结。
```

是否同时授权 PositionResponsibility 的 priority/effective period，应由用户在新指令中明确；未明确则不实施。

---

## 9. 保护基线

停止点只读复核：

```text
Database SHA256 = 9FC2A4B19716E84EB10F397BF94736CC69FFC6D1472C6FFB1849DD3A20036619
PurchaseOrder（采购订单）= 218
SupplierMaterialPrice（供应商物料价格）= 28
Responsibility = 0
PositionResponsibility = 0
PositionWorkflowResponsibility = 0
Unauthorized Business Writes（未授权业务写入）= 0
```

本轮只执行文档、源码、哈希和数据库计数读取，并新增本说明文件。未运行 Migration、测试数据生成、浏览器保存、采购动作或任何业务写操作。

---

## 10. 最终状态

```text
R1 Preflight（R1实施前检查）= BLOCKED BY REQUIRED SCHEMA EXTENSION
Schema Extension Design = COMPLETE
Migration Authorization = WAITING
R1 Implementation = NOT STARTED
R1 Implementation Report = NOT GENERATED
Code Changed = NO
Database Changed = NO
Responsibility Data Created = NO
Workflow Runtime Changed = NO
ApprovalTask Changed = NO
Permission Changed = NO
Purchase Approval Changed = NO
Unauthorized Business Writes = 0
```

本轮在规定停止点结束，等待新的 Migration 授权。
