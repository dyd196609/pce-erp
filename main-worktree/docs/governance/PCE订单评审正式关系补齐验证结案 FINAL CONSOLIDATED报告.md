# 《PCE订单评审正式关系补齐验证结案 FINAL CONSOLIDATED报告》

**文档状态：FINAL / CONSOLIDATED**  
**结案日期：2026-09-30（Asia/Shanghai）**  
**实施前置基线：`ca4264dadf754f3efd511a2ee962e371fca0ad64`**  
**唯一实施提交：`295d8682ed0299756444deb0a354418bd9c8180a`**  
**最终 Gate：`PCE ORDER REVIEW FORMAL RELATION = CLOSED / PASS`**

## 1. 结案结论

“PCE订单评审正式关系补齐”问题已完成从事实诊断、最小关系设计、代码实施、隔离验证、唯一提交、真实验收库 Migration 到数据库后置验证的完整闭环。

最终形成以下正式追溯关系：

```text
OrderCrossFunctionalReview
        ^
        | OneToOne / PROTECT
        |
OrderReviewSalesOrderRelation ---- FK / PROTECT ----> SalesOrder
        |
        | 1:N / PROTECT
        v
OrderReviewScopeItem ------------ FK / PROTECT ----> SalesOrderItem
```

结案状态：

- 订单评审正式订单关系：完成；
- 订单评审订单行范围模型：完成；
- 新订单正式关系持久化：完成；
- 真实验收库 `pde.0032_order_review_sales_order_relation`：完成；
- 历史关系回填：未执行，另行任务；
- PDE Review / OrderEngineeringInstance 正式关系：未进入；
- BOM / Routing / ProductVersion：未进入；
- Unauthorized Business Writes：0；
- Git push：未执行。

## 2. 原问题与原开发事实

### 2.1 原问题

原模型中，`OrderCrossFunctionalReview` 与正式 `SalesOrder`、`SalesOrderItem` 之间没有数据库外键或等价的正式业务关系。系统虽然可以通过来源记录、来源订单号、JSON、通用来源身份和 P0 Gate 返回值进行运行时判断，但无法从数据库关系证明：

1. 某个订单评审版本最终对应哪个正式销售订单；
2. 该评审覆盖全订单、部分订单行，还是哪些具体订单行；
3. 历史订单读取时使用的是当时评审范围，而不是字符串或最新数据推断。

### 2.2 原有间接事实的定位

| 原有对象/字段 | 正式定位 | 是否可替代正式关系 |
| --- | --- | --- |
| `EngineeringSourceRecord` | 历史来源、原始快照、辅助证据 | 否 |
| `OrderCrossFunctionalReview.source_record` | 评审依据来源 | 否 |
| `source_order_no` / `external_source_no` | 外部标识快照 | 否 |
| 来源 JSON | 证据与展示事实 | 否 |
| `ExternalIdentity` | 通用解析证据 | 否 |
| P0 Gate `review_id` / `review_version` | 在线准入结果 | 可作为正式关系创建输入，但自身不是已持久化关系 |

`OrderCrossFunctionalReviewItem` 仍是评审检查项，不是销售订单行范围；本次未把两者混同或转换。

## 3. 治理与保护回执

本轮在修改、提交和真实库执行前重新核验：

- `D:\Dev-PCE\AGENTS.md`；
- `D:\Dev-PCE\Source\AGENTS.md`；
- `PCE CODEX开发指令规范管理V1.2.md`；
- `PCE 已开发模块固化与变更保护规范 V1.0.md`；
- `completed_module_registry.v1.json`；
- `COMPLETED_MODULE_PROTECTION_PREFLIGHT_V1.md`；
- 本问题诊断设计报告、实施报告；
- P0-01 Gate 基线收敛报告；
- P0-02 真实验收库 Migration 报告。

`COMPLETED MODULE GOVERNANCE READING RECEIPT`：

- Preservation Standard：已读取并执行；
- Registry：当前 `currentFrozenVerifiedModuleIds = []`；
- Affected Frozen Modules：无；
- Freeze Contracts：无适用合同；
- Unfreeze Authorization：不需要；
- Review Level：C；
- 实施方式：Preserve-and-Extend；
- 原脏工作树：未用于实施、提交或真实库执行；
- 独立 worktree：`C:\Users\DAODA\.codex\worktrees\p0-chain-fix\Source`。

## 4. 诊断结论与最终模型设计

### 4.1 `OrderReviewSalesOrderRelation`

最终模型实现：

- `review`：`OneToOneField` → `OrderCrossFunctionalReview`，`PROTECT`；
- `sales_order`：FK → `SalesOrder`，`PROTECT`；
- `company`：FK → Company，`PROTECT`；
- 一个评审版本最多一个正式订单关系；
- 一个销售订单允许关联多个历史评审版本；
- `scope_mode` 支持 `WHOLE_ORDER`、`SELECTED_ITEMS`、`UNRESOLVED`；
- `RUNTIME_GATE` 禁止 `UNRESOLVED`；
- `UNRESOLVED` 仅保留给未来经批准的历史登记；
- 保存订单版本、来源内容哈希、解析依据、范围原因、创建人、审计哈希和创建时间；
- 关系为只追加记录，不允许更新改指订单或删除。

企业一致性由模型/服务校验：

```text
relation.company_id
  == review.company_id
  == sales_order.company_id
```

### 4.2 `OrderReviewScopeItem`

最终模型实现：

- `relation`：FK → `OrderReviewSalesOrderRelation`，`PROTECT`；
- `sales_order_item`：FK → `SalesOrderItem`，`PROTECT`；
- `(relation, sales_order_item)` 唯一；
- 订单行必须属于 relation 对应的 `SalesOrder`；
- 保存 `line_no_snapshot`；
- 保存 `external_line_no_snapshot`；
- 保存 64 位 `item_identity_hash`；
- 范围记录只追加，不允许修改或删除。

### 4.3 范围语义

| 范围模式 | 实施语义 |
| --- | --- |
| `WHOLE_ORDER` | 对创建时全部 `SalesOrderItem` 生成范围记录 |
| `SELECTED_ITEMS` | 只对显式行号生成范围记录，并要求范围原因 |
| `UNRESOLVED` | 新在线流程硬阻断；本轮也未登记任何历史数据 |

## 5. 实施代码与范围审查

本次唯一实施范围严格为 5 个文件：

1. `backend/pde/models.py`；
2. `backend/sales/services.py`；
3. `backend/sales/development_contract_sample.py`；
4. `backend/pde/migrations/0032_order_review_sales_order_relation.py`；
5. `backend/pde/tests_order_review_sales_order_relation.py`。

最终差异统计：

| 文件 | 新增 | 删除 |
| --- | ---: | ---: |
| `backend/pde/migrations/0032_order_review_sales_order_relation.py` | 79 | 0 |
| `backend/pde/models.py` | 152 | 0 |
| `backend/pde/tests_order_review_sales_order_relation.py` | 328 | 0 |
| `backend/sales/development_contract_sample.py` | 1 | 0 |
| `backend/sales/services.py` | 116 | 2 |
| **合计** | **676** | **2** |

范围审查确认没有夹带：

- PDE Review 正式关系；
- `OrderEngineeringInstance` 关系；
- `EngineeringCalculation` FK；
- BOM；
- Routing；
- ProductVersion；
- ProductManufacturingOutput；
- 页面；
- 权限业务模型或角色授权；
- Workflow 扩展；
- 历史业务数据回填。

新增测试文件引用既有 Workflow 类型仅用于建立销售订单创建测试夹具，不构成生产 Workflow 扩展。

## 6. P0 Gate 承接与订单创建事务

订单创建继续复用既有 P0 CRM Order Admission Gate，没有重新设计或绕过 Gate。

正式顺序为：

```text
CRM Gate
→ SalesOrder
→ SalesOrderItem
→ OrderReviewSalesOrderRelation
→ OrderReviewScopeItem
→ Audit
→ Commit
```

实现直接使用本次 Gate 返回的：

- `review_id`；
- `review_version`。

关系创建仅按 `review_id` 加公司、评审类型和已提交状态锁定评审，并验证 `review_version`。没有通过 `source_order_no`、JSON、`EngineeringSourceRecord` 或 `ExternalIdentity` 二次猜配 Review。

整个 `create_order()` 仍由 `transaction.atomic` 包裹。关系或范围任一步失败时，订单、订单行、关系、范围和审计一起回滚。在线 `UNRESOLVED` 的原子阻断已有专项测试。

## 7. Schema Migration

Migration：`pde.0032_order_review_sales_order_relation`

依赖：

- `pde.0031_merge_pde_legacy_and_order_chain`；
- `sales.0005_sales_order_item_tax_snapshot`；
- `system.0018_normalize_process_display_order_schema`；
- 当前用户模型。

操作内容：

- 创建 `OrderReviewSalesOrderRelation`；
- 创建 `OrderReviewScopeItem`；
- 创建公司 + 订单组合索引；
- 创建范围模式、解析依据、正版本、relation + item 唯一、正行号约束。

Migration 不包含：

- `RunPython`；
- `RunSQL`；
- 数据回填；
- 历史 Migration 修改；
- fake；
- 删除或重编号。

## 8. 唯一实施 Commit

| 项目 | 值 |
| --- | --- |
| Commit | `295d8682ed0299756444deb0a354418bd9c8180a` |
| Parent | `ca4264dadf754f3efd511a2ee962e371fca0ad64` |
| Tree | `2975cc3af52cf296cdecb660142fb8167710faf1` |
| Subject | `P1-REL order review formal sales order relation` |
| 文件数 | 5 |
| 统计 | 676 insertions, 2 deletions |
| Push | 未执行 |

Commit 正文明确记录：

- formal review/order relation；
- review scope relation；
- no historical backfill；
- no P1 scope expansion。

未 squash、未改写 P0-01 / P0-02 历史。

## 9. 新 Commit 自动验证

所有下列验证均在 commit `295d8682...` 形成后重新执行，没有引用实施阶段旧结果。

### 9.1 测试结果

联合矩阵共 21 项：

- P1-REL 专项：12 项；
- P0-01 Gate：5 项；
- 订单需求准备既有回归：2 项；
- 已涉及销售订单创建路径：2 项。

结果：**21 / 21 PASS**。

覆盖内容包括：

- Gate 返回 Review ID 正式持久化；
- REJECT 不建订单关系；
- APPROVED 正常建关系；
- 一个 Review 不得关联两个订单；
- 一个订单可关联多个 Review 版本；
- WHOLE_ORDER；
- SELECTED_ITEMS；
- 跨订单行阻断；
- 企业一致性；
- 重复范围阻断；
- 失败不改变历史订单；
- 在线 UNRESOLVED 原子阻断；
- P0 显式 REJECT 优先级、Pending、来源不唯一及新流程空 conclusion + approved；
- 订单需求准备和已有销售创建路径。

首次联合命令中 4 个旧测试选择器名称不存在，产生 `AttributeError`；这是选择器错误，不是实现断言失败。读取当前 commit 的测试原文后使用真实方法名完整重跑，最终 21 项全部通过。该失败没有触碰真实验收库。

### 9.2 其它 Gate

| 检查 | 结果 |
| --- | --- |
| `makemigrations --check --dry-run` | `No changes detected` |
| Django system/import check | 通过；仅既有 worktree static 目录警告 |
| Migration conflicts | `{}` |
| PDE leaf | `0032_order_review_sales_order_relation` |
| Sales leaf | `0005_sales_order_item_tax_snapshot` |
| System leaf | `0018_normalize_process_display_order_schema` |
| `git show --check HEAD` | 通过 |
| 实施 worktree | clean |
| 未授权文件 | 0 |

测试期间 Python 刷新了 54 个历史受跟踪的 `__pycache__/*.pyc`。经确认全部且仅为生成文件后精确恢复到 commit；没有把这些文件纳入提交。

非阻断既有警告：

- 独立 worktree 的 `backend/static` 目录不存在（`staticfiles.W004`）；
- `settings.py` 中既有路径字符串触发 Python invalid escape `SyntaxWarning`。

本轮没有通过范围外修改隐藏警告。

## 10. 真实验收库执行前状态

目标库：`D:\Dev-PCE\Acceptance\PDE-Operable-20260912\pde-operable-acceptance.sqlite3`

| 项目 | 执行前值 |
| --- | --- |
| SHA256 | `2E827C8B1BA6BFE384C6946A8A478363D6490AFA58CE453070F29A0FB7AA82F2` |
| 文件大小 | 31,481,856 bytes |
| WAL / SHM / journal | 均不存在 |
| journal mode | `delete` |
| `django_migrations` | 172 |
| Migration 记录指纹 | `fe1159addc7f8bbc7d246684131ea760cf35c1d460c81e9dd1f594095b99f666` |
| Schema 对象数 | 883 |
| Schema 指纹 | `553e01e2d8e074b6c270c6a1f0e573731ae7b726b28b643509c32986e3f0551f` |
| 业务表数（不含 `django_migrations`） | 299 |
| 广义业务/应用表总行数 | 15,602 |
| 广义数据指纹 | `366c13d29af508a81414e5d8b6e0dee17f8f19fa4ef4a93c221f6c60f918fdd3` |
| `integrity_check` | `ok` |
| `foreign_key_check` | 0 |

关键计数：

| 表 | 执行前 |
| --- | ---: |
| `pde_order_cross_functional_review` | 3 |
| `pde_order_cross_functional_review_item` | 29 |
| `sales_order` | 3 |
| `sales_order_item` | 6 |
| `workflow_approval_decisions` | 2 |
| `pde_engineering_source_record` | 12 |
| `pde_order_engineering_instance` | 5 |
| `pde_order_engineering_baseline` | 2 |
| `pde_bom_version` | 0 |
| `pde_routing` | 42 |
| `pde_routing_version` | 42 |
| `pde_order_review_sales_order_relation` | 不存在 |
| `pde_order_review_scope_item` | 不存在 |

### 10.1 回滚准备

回滚目录：

`D:\Dev-PCE\Acceptance\PDE-Operable-20260912\rollback\P1-REL-0032-20260930T125358-CST`

逐字节副本：

`pde-operable-acceptance.pre-0032.sqlite3`

副本 SHA256：`2E827C8B1BA6BFE384C6946A8A478363D6490AFA58CE453070F29A0FB7AA82F2`  
副本大小：31,481,856 bytes

源库与副本 SHA、大小完全一致。副本未删除，保留供受控回滚使用。

证据文件：

- `pre_state.json`；
- `post_state.json`；
- `metadata_and_constraints_validation.json`。

### 10.2 执行计划

执行前 `migrate --plan` 的唯一计划项：

```text
pde.0032_order_review_sales_order_relation
```

无其它待执行 Migration，因此满足授权前提。

## 11. 真实验收库执行

执行代码精确为：`295d8682ed0299756444deb0a354418bd9c8180a`

执行命令：

```text
python manage.py migrate pde 0032_order_review_sales_order_relation --noinput
```

结果：

```text
Applying pde.0032_order_review_sales_order_relation... OK
```

没有使用 fake，没有手工写 `django_migrations`，没有修改、删除或重编号历史 Migration。

## 12. 数据库后置验证

### 12.1 Migration 与文件状态

| 项目 | 执行后值 |
| --- | --- |
| 数据库 SHA256 | `7E68600E46B3569CE0F57D0C8EE15FA4BA19EED5573C4D793747298FDD6DFF8F` |
| 文件大小 | 31,481,856 bytes |
| `django_migrations` | 173（+1） |
| 唯一新增记录 | `pde.0032_order_review_sales_order_relation` |
| Migration 记录指纹 | `c5c1f8ea899b266be54dfc9416f9abc0d1b384adff485e93b0be8994d9791560` |
| 待执行 Migration | 0 |
| Migration conflicts | 0 |
| PDE leaf | `0032_order_review_sales_order_relation` |
| 0032 应用记录数 | 1 |
| WAL / SHM / journal | 均不存在 |

数据库 SHA 变化由新 Schema、授权 Migration 记录以及 Django 为两个新模型生成的标准 ContentType/默认权限元数据共同导致。

### 12.2 Schema、FK、索引与约束

两张新表均存在：

- `pde_order_review_sales_order_relation`；
- `pde_order_review_scope_item`。

FK 实际落地：

- relation → `sales_order`；
- relation → `pde_order_cross_functional_review`；
- relation → `system_company`；
- relation → `user_system`；
- scope item → relation；
- scope item → `sales_order_item`。

SQLite 以 `NO ACTION` 表达 Django `PROTECT` 的数据库参照行为；应用层 `PROTECT` 与不可变模型校验继续生效。

索引/唯一性实际落地：

- `pde_orr_company_order_idx(company_id, sales_order_id)`；
- relation 的公司、订单、创建人 FK 索引；
- `review_id` 唯一；
- `audit_hash` 唯一；
- scope item 的 relation、sales order item FK 索引；
- `(relation_id, sales_order_item_id)` 唯一。

CHECK 实际落地：

- `pde_orr_scope_valid`；
- `pde_orr_basis_valid`；
- `pde_orr_order_version_positive`；
- `pde_orsi_line_positive`。

### 12.3 完整性

| 检查 | 结果 |
| --- | --- |
| `PRAGMA integrity_check` | `ok` |
| `PRAGMA foreign_key_check` | 0 |
| Schema 对象数 | 891 |
| Schema 指纹 | `a76d82cd332ddab85e2baeb0c45bcea25d3bbf6e86ff0be62f7ff97c74498f00` |

### 12.4 历史业务数据保护

关键业务计数执行前后完全一致：

| 表 | 前 | 后 | 变化 |
| --- | ---: | ---: | ---: |
| Review | 3 | 3 | 0 |
| ReviewItem | 29 | 29 | 0 |
| SalesOrder | 3 | 3 | 0 |
| SalesOrderItem | 6 | 6 | 0 |
| ApprovalDecision | 2 | 2 | 0 |
| EngineeringSourceRecord | 12 | 12 | 0 |
| OrderEngineeringInstance | 5 | 5 | 0 |
| OrderEngineeringBaseline | 2 | 2 | 0 |
| BOMVersion | 0 | 0 | 0 |
| Routing | 42 | 42 | 0 |
| RoutingVersion | 42 | 42 | 0 |

两张新关系表：

| 表 | 执行后记录数 |
| --- | ---: |
| `pde_order_review_sales_order_relation` | 0 |
| `pde_order_review_scope_item` | 0 |

因此没有生成 `Review 1 → SalesOrder 3` 历史关系，也没有任何其它历史回填。

对全部执行前既有表进行行数与逐行内容哈希对比后，仅以下 Django 框架元数据发生预期变化：

- `django_content_type`：+2，分别对应两个新模型；
- `auth_permission`：+8，分别是每个新模型的 add/change/delete/view 默认权限元数据；
- `django_migrations`：+1，为本次授权 Migration。

这 8 条默认权限记录没有分配给任何用户或角色，不构成权限授权或权限业务模型调整。排除上述框架元数据后，受保护的既有业务表变化清单为空。

结论：

- Business Domain Data Write：0；
- Unauthorized Business Writes：0；
- 历史回填：0；
- 用户、角色、权限分配变化：0；
- Workflow 数据/定义变化：0。

## 13. 正式关系运行能力

本轮未通过制造历史数据来证明运行能力。运行能力由以下事实共同证明：

1. P1/P0/订单创建联合自动化 21 / 21 PASS；
2. 原子事务失败回滚测试 PASS；
3. 模型级企业、范围、快照和不可变校验；
4. 空库/测试库完整 Migration 路径成功；
5. 真实验收库两张表及 FK、唯一索引、普通索引、CHECK 已落地；
6. 真实验收库新关系表保持 0 行，符合“禁止历史回填”。

## 14. 变更状态总表

| 项目 | 状态 |
| --- | --- |
| Code Change | YES，唯一 5 文件 commit |
| Migration Change | YES，新增 `pde.0032` |
| Real Acceptance Database Change | YES，仅授权 0032 及 Django 标准模型元数据 |
| Business Domain Data Write | NO |
| Historical Business Data Backfill | NO |
| Unauthorized Business Writes | 0 |
| Permission Model / Role Assignment Change | NO |
| Django default permission metadata | YES，两个模型共 8 条，未授权给用户/角色 |
| Workflow Change | NO |
| Page Change | NO |
| Git Push | NO |

## 15. Remaining Issues 与停止点

本问题之外的下一个尚未解决问题名称：

**订单评审 → PDE工程准备（CRM Review → PDE Review → OrderEngineeringInstance）正式前置关系补齐。**

本报告只记录该名称，没有开始诊断、设计或开发。

本轮在此停止；不自动进入其它 P1、BOM、Routing 或 ProductVersion 工作。

## 16. 最终 Gate

全部结案条件已满足：

1. 唯一实施 commit 已形成；
2. commit 仅包含批准 5 文件；
3. P1 专项 PASS；
4. P0 与既有路径联合回归 PASS；
5. `makemigrations` PASS；
6. Migration graph PASS；
7. 真实验收库 0032 PASS；
8. Schema / FK / 索引 / 约束 PASS；
9. 历史业务数据变化 0；
10. Unauthorized Business Writes = 0；
11. 历史回填 = 0；
12. 其它 P1 未进入。

**PCE ORDER REVIEW FORMAL RELATION = CLOSED / PASS**
