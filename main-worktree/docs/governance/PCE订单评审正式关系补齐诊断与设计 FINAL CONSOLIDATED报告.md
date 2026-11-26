# 《PCE订单评审正式关系补齐诊断与设计 FINAL CONSOLIDATED报告》

**文档状态：FINAL / CONSOLIDATED**  
**核查日期：2026-09-30（Asia/Shanghai）**  
**任务性质：只读诊断与最小关系设计**  
**实施状态：未实施**

## 1. 最终结论

当前 `OrderCrossFunctionalReview` 与正式 `SalesOrder`、`SalesOrderItem` 之间**没有数据库外键或等价的正式业务关系**。

现有实现只能通过以下间接事实进行推断：

- `OrderCrossFunctionalReview.source_record_id`；
- `source_order_no`、`source_version`、`source_content_hash`；
- `SalesOrder.external_source_no`；
- `SalesOrder.delivery_information` / 来源 JSON；
- 通用 `ExternalIdentity` 字符串目标映射；
- P0-01 CRM 订单准入 Gate 返回的 `review_id`。

这些事实可以作为来源证据和历史解析依据，但不能替代 `OrderReview ↔ SalesOrder` 与 `OrderReview ↔ SalesOrderItem` 的正式关系。

本次确认两个 P1 缺口：

1. **订单级正式关系缺失**：准入 Gate 已能唯一返回评审，但订单创建服务未持久化该 `review_id`。
2. **订单行评审范围缺失**：现有 `OrderCrossFunctionalReviewItem` 是评审检查项，不是 `SalesOrderItem` 范围项；系统无法证明一次评审覆盖全订单、部分订单行，或具体哪些产品行。

最小推荐设计不是把 `sales_order` 在订单创建后回写到已提交、不可变的评审主表，而是 Preserve-and-Extend 新增：

- `OrderReviewSalesOrderRelation`：正式关联一个评审版本与一个销售订单；
- `OrderReviewScopeItem`：正式关联该关系与被评审的销售订单行。

该设计需要 Schema 变化和 Migration。**不能在无数据库修改的情况下完成正式关系补齐**；只能完成本次诊断设计。

## 2. 范围与停止边界

### 2.1 本次已检查

- CRM 正式订单：`SalesOrder`；
- CRM 正式订单行：`SalesOrderItem`；
- 订单评审：`OrderCrossFunctionalReview`；
- 评审检查项：`OrderCrossFunctionalReviewItem`；
- 工程来源：`EngineeringSourceRecord`；
- 订单创建、订单推进与 CRM 准入 Gate；
- 对应 Migration；
- 真实验收库中的上述表、外键、索引及少量历史关系事实。

### 2.2 明确排除

本报告不设计或处理 PDE Review、`OrderEngineeringInstance`、`EngineeringCalculation`、BOM、Routing、`ProductVersion`、页面、权限和 Workflow 扩展。报告中出现 PDE 类型评审仅用于说明共享表边界，不作任何关系设计。

## 3. 治理阅读回执与执行基线

### 3.1 COMPLETED MODULE GOVERNANCE READING RECEIPT

- 已全文读取 `D:\Dev-PCE\AGENTS.md` 与 `D:\Dev-PCE\Source\AGENTS.md`。
- 已全文读取 `docs/governance/PCE CODEX开发指令规范管理V1.2.md`。
- 已全文读取 `docs/governance/PCE 已开发模块固化与变更保护规范 V1.0.md`。
- 已全文读取 `docs/governance/completed_module_registry.v1.json`。
- 已全文读取 `docs/governance/COMPLETED_MODULE_PROTECTION_PREFLIGHT_V1.md`。
- 已读取 P0 实施、P0-02 收口/合入/真实验收库执行报告，以及 CRM/PDE 关系相关历史报告。
- Registry 当前 `currentFrozenVerifiedModuleIds = []`。
- 相关登记模块 `sales-order-source-intake`、`engineering-calculation-six-continuations` 均为 `DEVELOPED_NOT_CURRENTLY_VERIFIED`。
- Affected Frozen Modules：无。
- Freeze Contracts：本范围未命中。
- Unfreeze Authorization：不需要。
- Preflight：报告文件可创建；业务源码、Schema、Migration、数据库及业务数据不得修改。

### 3.2 当前实际基线

- 当前共享工作树 HEAD：`6058ee03022ac1f4ef7a40905aef32f0dd2e294e`；工作树已有大量用户成果和未提交文件，本次未触碰。
- 已完成 P0-02 的独立干净 worktree HEAD：`c78bca8eab5e4ea74572eb092f5cb8c8ca036c21`，状态干净。
- 与本次直接相关的 `pde.0025`、`pde.0026` 和 `sales.models` 在当前工作树与 P0-02 基线内容一致；当前 `pde.models` 还包含后续实际开发成果，因此本报告以当前工作树模型为准，并用 Migration 与真实库复核。
- 真实验收库：`D:\Dev-PCE\Acceptance\PDE-Operable-20260912\pde-operable-acceptance.sqlite3`。
- 核查时数据库 SHA256：`2E827C8B1BA6BFE384C6946A8A478363D6490AFA58CE453070F29A0FB7AA82F2`。
- 数据库大小：31,481,856 bytes；核查全部通过 SQLite `mode=ro` 执行。

## 4. 当前真实模型事实

### 4.1 OrderCrossFunctionalReview

模型：`pde.OrderCrossFunctionalReview`  
表：`pde_order_cross_functional_review`  
主键：隐式 `BigAutoField id`

主要字段如下：

| 类别 | 实际字段 |
| --- | --- |
| 公司范围 | `company_id`，FK → `system.Company`，`PROTECT` |
| 来源记录 | `source_record_id`，FK → `EngineeringSourceRecord`，`PROTECT` |
| 类型 | `review_type`：`CRM_ORDER_REVIEW` / `PDE_PRODUCTION_FEASIBILITY` |
| 来源快照 | `source_order_no`、`source_version`、`source_content_hash` |
| 评审版本 | `review_version` |
| 结论与意见 | `conclusion`、`review_opinion` |
| JSON 证据 | `evidence`、`missing_conditions`、`responsibility_feedback`、`item_summary` |
| 审计 | `reviewer_id`、`idempotency_key`、`audit_hash`、时间字段 |
| 状态 | `record_status`：`DRAFT` / `SUBMITTED` |
| 模板 | `template_version` |

实际外键只有：

1. `company_id`；
2. `reviewer_id`；
3. `source_record_id`。

**不存在 `SalesOrder` 外键，也不存在 `SalesOrderItem` 外键。**

版本与唯一性机制：

- `(company, review_type, source_order_no, review_version)` 唯一；
- `(company, review_type, idempotency_key)` 唯一；
- `audit_hash` 唯一；
- 已提交记录通过模型 `save()` 防止覆盖修改，新复评通过增加 `review_version` 实现。

### 4.2 OrderCrossFunctionalReviewItem 不是订单行范围

`OrderCrossFunctionalReviewItem` 保存的是固定/其它评审事项、意见、责任人和签认快照。其外键包括：

- `review_id`；
- `template_item_id`；
- `responsible_employee_id`；
- `signed_by_user_id`。

它没有 `sales_order_item_id`。真实验收库当前有 29 条评审检查项，其中 CRM 评审有 9 条；这些条目编码是检查表项目编码，不是销售订单行号。

因此：

> `OrderCrossFunctionalReviewItem` 不得重解释为 `OrderReviewScopeItem`，也不得通过字段名称或条目数量推断订单行覆盖范围。

### 4.3 SalesOrder

模型：`sales.SalesOrder`  
表：`sales_order`  
主键：隐式 `BigAutoField id`

与本任务相关的实际字段：

- `company_id`；
- `order_no`，当前全局唯一；
- `external_source_no`，普通字符串，**无唯一约束**；
- `order_source`；
- `version`；
- `delivery_information` JSON；
- 订单状态、客户、部门、负责人等正式字段。

SalesOrder 当前没有指向 `OrderCrossFunctionalReview` 的外键。

### 4.4 SalesOrderItem

模型：`sales.SalesOrderItem`  
表：`sales_order_item`  
主键：隐式 `BigAutoField id`

正式父关系：

- `sales_order_id`，FK → `SalesOrder`，`PROTECT`；
- `(sales_order_id, line_no)` 唯一。

与外部来源有关的 `external_line_no` 只是字符串快照。当前没有评审范围关系，也没有评审范围中间表。

## 5. 当前关系图

### 5.1 当前实际关系

```text
EngineeringSourceRecord
        ^  FK / PROTECT
        |
OrderCrossFunctionalReview
        |
        +--> OrderCrossFunctionalReviewItem   （评审检查项，不是订单行）

OrderCrossFunctionalReview
        - - source_order_no / source_version / hash / JSON / ExternalIdentity - -
                                                                            |
                                                                            v
SalesOrder -------------------------------------------------------> SalesOrderItem
           external_source_no                     FK / PROTECT；订单内行号唯一
```

虚线部分是间接来源证据，不具有评审到订单的数据库参照完整性。

### 5.2 目标最小关系

```text
OrderCrossFunctionalReview
        ^
        | OneToOne / PROTECT（每个评审版本最多一个正式订单关系）
        |
OrderReviewSalesOrderRelation ---- FK / PROTECT ----> SalesOrder
        |
        | 1:N
        v
OrderReviewScopeItem -------- FK / PROTECT ---------> SalesOrderItem
```

同一个 SalesOrder 可以因后续复评关联多个 `OrderCrossFunctionalReview` 版本；每个评审版本只能关联一个正式订单。多产品订单由多个 `OrderReviewScopeItem` 表达，不需要复制评审或拆分订单。

## 6. 当前服务关系事实

### 6.1 评审创建与读取

评审服务以 `EngineeringSourceRecord` 为入口：

- 读取来源 JSON 中的 `sourceOrderNo`；
- 以 `company_id + source_order_no + review_type` 查找当前评审；
- 创建评审时保存 `source_record`、来源编号、版本和内容哈希；
- 不解析、不保存正式 `SalesOrder` 或 `SalesOrderItem`。

### 6.2 P0-01 准入 Gate

P0-01 Gate 当前以：

- `company_id`；
- `source_record_id`；
- `source_order_no`；
- `source_version`

唯一查找已提交 CRM 评审，并返回不可变的 `review_id`、`review_version`、Workflow 和最终审批决定。显式历史 `REJECT` 优先硬阻断，不能被 `approved` 覆盖。

该 Gate 已解决“是否准入”的 P0 问题，但没有解决本报告的 P1 追溯问题。

### 6.3 订单创建入口的失联点

`sales.services.create_order()` 调用 `_require_crm_admission()`，但当前调用结果未赋值、未写入任何正式关系。随后仅把：

- `externalSourceNo` 写入 `SalesOrder.external_source_no`；
- `sourceRecordId` / `sourceVersion` 写入来源 JSON；
- 通用来源身份写入 `ExternalIdentity`。

因此当前实际流程是：

```text
Gate 成功返回 review_id
          |
          v
调用方丢弃返回值
          |
          v
SalesOrder 仅保留来源字符串/JSON
```

这是已确认的服务关系缺口，不是 Schema 字段名称问题。

订单确认与订单推进也会重新调用 Gate，但同样不持久化 `review_id`。重复校验不能替代正式关系。

## 7. EngineeringSourceRecord 与间接来源的正式定位

### 7.1 定位结论

| 对象/字段 | 定位 | 可否替代正式评审关系 |
| --- | --- | --- |
| `EngineeringSourceRecord` | 历史来源 + 原始内容快照 + 辅助证据 | 否 |
| `OrderCrossFunctionalReview.source_record` | 评审依据来源 FK | 否 |
| `source_order_no` / `external_source_no` | 外部来源标识快照 | 否 |
| `source_version` / `source_content_hash` | 评审依据版本与一致性证据 | 否 |
| `source_payload` / `delivery_information` / `evidence` | JSON 证据与展示事实 | 否 |
| `ExternalIdentity` | 通用来源对象到目标对象的持久化解析证据 | 否，目标类型和目标 ID 为通用字符串，且不是评审业务关系 |

### 7.2 为什么不能作为正式关系

1. `source_order_no` 和 `external_source_no` 没有共同 FK，`external_source_no` 也无唯一约束；当前数据唯一不等于 Schema 保证唯一。
2. JSON 中的 ID 没有数据库参照完整性，目标删除/替换时数据库不能保护。
3. `ExternalIdentity.target_entity_id` 是通用字符串，不验证目标表存在，也没有 `OrderReview` 语义。
4. 一个 `EngineeringSourceRecord` 可以被多种业务对象使用；来源相同不等于评审范围相同。
5. 来源行、销售订单行、评审检查项是三种不同业务身份，不能通过数量或文本相似度合并。

结论：`EngineeringSourceRecord` 的定位保持不变，**不得升级为订单评审事实或正式订单关系**。

## 8. 真实验收库事实与历史数据判断

### 8.1 当前计数

| 对象 | 当前数量 |
| --- | ---: |
| `OrderCrossFunctionalReview` | 3 |
| 其中 CRM 订单评审 | 1 |
| 其中 PDE 生产可行性评审 | 2 |
| `OrderCrossFunctionalReviewItem` | 29 |
| `EngineeringSourceRecord` | 12 |
| `SalesOrder` | 3 |
| `SalesOrderItem` | 6 |

真实库的 `pde_order_cross_functional_review` 外键列表只包含 Company、User、EngineeringSourceRecord；`pde_order_cross_functional_review_item` 对 `sales_order_item` 的外键数为 0。

### 8.2 当前 CRM 历史样本

当前唯一 CRM 评审：

- Review ID：1；
- Company ID：1；
- Source Record ID：11；
- Review Version：1；
- 状态：`SUBMITTED`；
- 历史显式结论：`REJECT`；
- 评审创建/提交时间早于正式 SalesOrder 3 的创建时间。

当前 SalesOrder 3：

- 具有 4 条正式 SalesOrderItem；
- `external_source_no` 与评审的 `source_order_no` 一致；
- 通过 `ExternalIdentity#1940` 形成 `EngineeringSourceRecord:11 -> SalesOrder:3` 的 `MATCH`；
- `ExternalIdentity.source_fingerprint`、Source Record 11 的 `content_hash`、Review 1 的 `source_content_hash` 三者一致；
- `MasterDataWriteRequest#1995` 为已提交状态，目标 SalesOrder ID 为 3。

这构成了**订单级可确定解析证据链**，不仅是字符串相等。因此未来经单独数据写入授权，可以通过一份明确、审查过的映射清单把 Review 1 与 SalesOrder 3 建立历史关系。

但必须同时保留以下事实：

- Review 1 的 `REJECT` 不得修改；
- SalesOrder 3 不得删除或改写；
- 该关系说明“历史上实际建立了订单”，不表示该建立动作当时符合准入规则；
- P0-01 Gate 负责阻止未来再次发生，而不是重写历史。

### 8.3 订单行范围不能确定回填

Review 1 有 9 条评审检查项，SalesOrder 3 有 4 条销售订单行，Source Record 11 中另有来源工程行。当前没有任何正式字段说明：

- 本次评审是全订单评审还是部分订单行评审；
- 哪些来源工程行被纳入评审；
- 这些来源行如何对应 4 条 SalesOrderItem；
- 未列出的订单行是“未评审”还是“默认包含”。

因此即使订单级关系可确定，**4 条订单行仍必须保持 `UNRESOLVED`，禁止按“同一订单”自动全部回填**。

其他历史数据处理：

- 两条 PDE 类型评审不在本任务范围，不创建本关系；
- SalesOrder 1、2 没有足够 CRM 评审证据，保持未关联；
- 单独的 `source_order_no == external_source_no` 只能产生候选，不能触发回填。

## 9. 已确认缺口与风险

| 编号 | 等级 | 已确认问题 | 影响 |
| --- | --- | --- | --- |
| P1-REL-01 | P1 | 无评审版本到正式销售订单的 FK/正式关系 | 无法从订单可靠还原准入评审；字符串重复、变化或跨版本时可能误配 |
| P1-REL-02 | P1 | 无评审到销售订单行的范围关系 | 无法证明全订单/部分行范围；多产品订单无法按评审范围控制 |
| P1-REL-03 | P1 | 订单创建入口丢弃 Gate 返回的 `review_id` | 已有权威事实未持久化，后续只能重新推断 |
| P1-REL-04 | P1 | 当前关系依赖 source string / JSON / generic identity | 数据库无参照完整性；来源证据可能被误用为正式事实 |
| P2-REL-05 | P2 | `SalesOrder.external_source_no` 无唯一约束 | 当前库无重复组，但 Schema 允许同公司同来源编号对应多订单 |
| P2-REL-06 | P2 | 无订单版本/行身份快照 | 订单增删行后无法证明当时评审范围 |

P0-01 已关闭不代表上述 P1 已关闭：P0-01 解决准入判定；本报告解决正式可追溯关系设计。

## 10. 最小 Schema 设计

### 10.1 为什么不直接在评审主表增加 sales_order

不推荐把 `sales_order_id` 直接加到 `OrderCrossFunctionalReview` 后再回写，原因是：

1. 当前真实流程是先评审、后创建正式 SalesOrder；评审提交时订单尚不存在。
2. 已提交评审是不可变审计记录；订单创建后回写会引入对历史评审的可变更新通道。
3. 一个 SalesOrder 后续可能发生多个评审版本；单个订单字段或单个评审字段无法同时准确表达版本历史。
4. 当前评审表同时承载 CRM/PDE 两类评审；直接加入 CRM 专用字段会扩大对 PDE 共享模型的影响。

因此，最小且符合 Preserve-and-Extend 的方案是新增独立正式关系对象。

### 10.2 OrderReviewSalesOrderRelation

建议新模型：`OrderReviewSalesOrderRelation`

| 字段 | 建议类型 | 规则 |
| --- | --- | --- |
| `id` | BigAutoField | 主键 |
| `company` | FK → Company, PROTECT | 企业范围索引；必须与两端公司一致 |
| `review` | OneToOne → OrderCrossFunctionalReview, PROTECT | 每个评审版本最多关联一个正式订单 |
| `sales_order` | FK → SalesOrder, PROTECT | 一个订单允许关联多个复评版本 |
| `scope_mode` | CharField | `WHOLE_ORDER` / `SELECTED_ITEMS` / `UNRESOLVED` |
| `order_version_snapshot` | PositiveIntegerField | 建立关系时的 `SalesOrder.version` |
| `source_content_hash_snapshot` | CharField(64) | 建立关系时的来源一致性证据，不作为连接键 |
| `resolution_basis` | CharField | `RUNTIME_GATE` / `APPROVED_HISTORICAL_MANIFEST` |
| `scope_reason` | TextField | 部分范围或历史未解析原因；全订单可为空 |
| `created_by` | FK → User, PROTECT | 办理人/数据治理执行人 |
| `audit_hash` | CharField(64), unique | 关系审计身份 |
| `created_at` | DateTimeField | 创建时间 |

必要约束与校验：

- `review` 唯一；
- 索引 `(company, sales_order)`；
- 服务校验 `review.review_type == CRM_ORDER_REVIEW`；
- 服务校验 `review.company_id == sales_order.company_id == relation.company_id`；
- 新在线关系只允许已提交且通过 P0 Gate 的评审；
- 新在线关系禁止 `UNRESOLVED`；`UNRESOLVED` 仅用于经授权登记的历史订单级关系且行范围未知；
- `resolution_basis=RUNTIME_GATE` 时必须直接使用本次 Gate 返回的 `review_id`，禁止二次用字符串查询；
- 关系只追加，不允许把一个评审版本改指另一订单；纠错必须通过受治理的撤销/替代机制另行授权。

### 10.3 OrderReviewScopeItem

建议新模型：`OrderReviewScopeItem`

| 字段 | 建议类型 | 规则 |
| --- | --- | --- |
| `id` | BigAutoField | 主键 |
| `relation` | FK → OrderReviewSalesOrderRelation, PROTECT | 正式订单级关系 |
| `sales_order_item` | FK → SalesOrderItem, PROTECT | 被本评审覆盖的正式订单行 |
| `line_no_snapshot` | PositiveIntegerField | 建立范围时的正式行号快照 |
| `external_line_no_snapshot` | CharField | 外部行号辅助快照，不作为连接键 |
| `item_identity_hash` | CharField(64) | 行身份/关键内容快照哈希 |
| `created_at` | DateTimeField | 创建时间 |

必要约束与校验：

- `(relation, sales_order_item)` 唯一；
- 服务校验 `sales_order_item.sales_order_id == relation.sales_order_id`；
- `WHOLE_ORDER`：范围行必须等于 `order_version_snapshot` 对应的全部订单行；
- `SELECTED_ITEMS`：至少一行，且必须明确保存选择结果和原因；未列行视为未被该评审覆盖；
- `UNRESOLVED`：不得创建任何虚构的 scope item；
- 订单新增/删除/替换行时不得自动继承旧评审范围，需要新的评审版本或明确的受治理复核。

跨表“订单行必须属于关系订单”无法由普通 SQL CheckConstraint 直接表达，必须由统一服务在同一事务内校验，并以测试覆盖；数据库仍通过两端 FK、唯一约束和 `PROTECT` 提供基础参照完整性。

### 10.4 全订单、部分订单行与多产品订单

| 场景 | 表达方式 |
| --- | --- |
| 全订单评审 | `scope_mode=WHOLE_ORDER`，为当时所有 SalesOrderItem 建立范围行 |
| 部分订单行评审 | `scope_mode=SELECTED_ITEMS`，只建立明确选择的范围行，必须保存原因 |
| 多产品订单 | 同一 relation 下建立多条 scope item；产品不同不需要复制订单级关系 |
| 历史范围未知 | `scope_mode=UNRESOLVED`，不猜配任何订单行 |
| 订单后来新增行 | 新行不继承旧评审；必须复评或另行明确纳入 |
| 同一订单复评 | 新的 OrderCrossFunctionalReview 版本建立新的 relation 和独立范围快照 |

## 11. 服务层最小设计

未来实施时，关系必须在正式 SalesOrder 创建事务内建立：

1. 调用统一 P0 Gate；
2. 保留其返回的 `CRMOrderAdmissionResult`，不得丢弃；
3. 创建 SalesOrder 与 SalesOrderItem；
4. 用 Gate 返回的 `review_id` 创建 `OrderReviewSalesOrderRelation`；
5. 按明确的 `scope_mode` 创建 `OrderReviewScopeItem`；
6. 校验公司、订单、订单行、评审版本和来源哈希；
7. 任一关系校验失败时整笔事务回滚，不能只创建订单而缺少正式关系。

订单确认、推进和后续只读追溯应读取已持久化 relation，并用 P0 Gate 做状态/准入再校验；不得每次重新用来源字符串推断关系。

本设计不改变 P0-01 的业务优先级：显式 `REJECT` 仍是硬阻断。历史 REJECT 订单的关系登记只是审计追溯，不产生新的准入许可。

## 12. 历史数据处理原则

### 12.1 可确定订单级回填的必要条件

只有同时满足下列条件，历史订单级关系才可进入“可回填”清单：

1. Review 为同公司 `CRM_ORDER_REVIEW`；
2. Review 的 `source_record_id` 存在；
3. Review `source_content_hash` 与 Source Record `content_hash` 一致；
4. 存在唯一 `ExternalIdentity`：`EngineeringSourceRecord:<id>`、`target_entity_type=SalesOrder`、`mapping_status=MATCH`；
5. ExternalIdentity 目标是同公司现存 SalesOrder；
6. 存在同一 identity、同一目标的已提交订单创建写入请求；
7. 来源编号匹配仅作为一致性复核，不作为主判据；
8. 不存在竞争映射或冲突证据。

任一条件不满足即为 `UNRESOLVED`。

### 12.2 当前历史分类

| 历史对象 | 订单级结论 | 行级结论 |
| --- | --- | --- |
| CRM Review 1 ↔ SalesOrder 3 | `DETERMINISTICALLY_RESOLVABLE`，未来可经批准映射清单登记 | `UNRESOLVED`，禁止自动把 4 行全部纳入 |
| SalesOrder 1 | `UNRESOLVED` / 无 CRM 评审证据 | `UNRESOLVED` |
| SalesOrder 2 | `UNRESOLVED` / 无 CRM 评审证据 | `UNRESOLVED` |
| 两条 PDE Review | 本任务不适用 | 本任务不适用 |

### 12.3 明确禁止

- 不得只凭 `source_order_no == external_source_no` 自动匹配；
- 不得以同一个 `source_record` 推定所有订单行均已评审；
- 不得以 JSON 中的 `salesOrderId` / `salesOrderItemId` 直接写 FK；
- 不得把评审检查项映射成销售订单行；
- 不得修改历史 `REJECT`、审批决定、SalesOrder 或 SalesOrderItem；
- 不得为了满足非空约束伪造关系；
- 不得把 `UNRESOLVED` 当作通过、全单覆盖或默认继承。

## 13. Schema、Migration 与无数据库修改判断

| 问题 | 结论 |
| --- | --- |
| 是否需要 Schema 变化 | **YES**：新增两个正式关系模型及约束/索引 |
| 是否需要 Migration | **YES**：至少需要 Schema Migration；历史登记需另行授权的数据收敛步骤 |
| 是否可以无数据库修改完成正式关系补齐 | **NO** |
| 是否可以无数据库修改完成本次诊断设计 | **YES，已完成** |

建议将未来 Migration 分阶段执行：

1. **Schema 阶段**：只创建关系表、FK、唯一约束和索引，不回填数据。
2. **新流量阶段**：订单创建事务使用 Gate 返回的 review ID 写正式关系；新数据不允许 `UNRESOLVED`。
3. **只读历史审计阶段**：生成明确映射清单和冲突清单，不写数据库。
4. **单独授权历史登记阶段**：仅按已审查映射清单创建关系；不得用开放式字符串查询批量猜配。
5. **约束验证阶段**：验证新订单均具有完整订单级和行级范围，再决定是否增加更强门禁；不得因遗留 `UNRESOLVED` 强制伪造数据。

不建议把历史回填隐藏在不可审查的通用 `RunPython` 推断逻辑中。应保留可回读输入清单、证据 ID、执行前后计数、回滚清单和审计哈希。

## 14. 后续实施顺序建议

1. 单独审批本报告的模型方向与基数规则。
2. 在独立干净 worktree 中实现两个模型和 Schema Migration。
3. 增加服务层统一关系创建函数，并由 SalesOrder 创建入口复用。
4. 增加测试：REJECT 不建单/不建关系、APPROVED 原子建单建关系、全单范围、部分行范围、多产品订单、跨订单行拒绝、重复评审关系拒绝、订单增行不继承。
5. 在空库执行全量 Migration、`makemigrations --check`、唯一叶节点与 FK/约束检查。
6. 对真实验收库先生成只读历史映射清单。
7. 另行取得 Business Data Write 授权后，登记可确定的订单级历史关系；所有行级未知保持 `UNRESOLVED`。
8. 完成 Readback 后再决定是否进入下一项 P1；不得顺带处理 PDE/OEI/BOM/Routing。

## 15. 本轮变更状态

| 项目 | 状态 |
| --- | --- |
| Code Change | **NO** |
| Database Change | **NO** |
| Migration Change | **NO** |
| Business Data Write | **NO** |
| Permission Change | **NO** |
| Workflow Change | **NO** |
| Page Change | **NO** |
| Report Change | **YES：仅新增本报告** |

## 16. 明确停止点与最终 Gate

本轮已完成：当前模型、服务、Migration 和真实验收库的交叉诊断；已给出最小正式关系、历史数据原则和实施顺序。

本轮在此停止。未创建 Migration，未修改模型，未回填关系，未修改任何评审、订单或订单行。

**最终 Gate：PCE ORDER REVIEW FORMAL RELATION DIAGNOSIS AND DESIGN COMPLETE**

