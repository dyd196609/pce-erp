# PCE CRM订单评审与PDE工程准备最小数据关系设计 FINAL / CONSOLIDATED报告

日期：2026-09-30  
任务 ID：`CRM-PDE-RELATION-DESIGN-20260930-001`  
阶段：DESIGN  
审查等级：Level B  
实施授权：NOT AUTHORIZED  
数据库写入：PROHIBITED  

## 1. 最终结论

本轮设计检查完成。现有仓库已经具备两段重要正式关系：

1. `SalesOrder → SalesOrderItem` 是正式外键关系；`SalesOrderItem` 已可引用 `ProductDefinition`、`ProductVersion`、`ProductManufacturingOutput` 和 `EngineeringDocumentVersion`。
2. PDE 内部已经具备 `ProductVersion`、`BOMVersion`、`RoutingVersion`、`EngineeringDocumentVersion` 与 `ProductManufacturingOutput` 的一致性关系和校验；按单工程还具备 `SalesOrderItem → OrderEngineeringInstance → baseline_product_version` 的正式关系。

但目标追溯链尚不完整。核心缺口是：

- `OrderCrossFunctionalReview` 没有指向正式 `SalesOrder` 的外键，也没有订单行评审范围关系；
- 评审与 PDE 工程对象之间没有正式交接关系，当前主要通过共同的 `EngineeringSourceRecord`、来源订单号文本或来源 JSON 推断；
- 仓库没有名为 `EngineeringVersion` 的正式模型；现有“工程版本”文字在不同场景分别指 `EngineeringSourceRecord.source_version`、`ProductDesignRevision`、`OrderEngineeringBaseline`、`EngineeringCalculationRecord.revision` 或制造发布组合，不能继续用同一个模糊名称串链；
- `ProductVersion → BOMVersion / RoutingVersion → EngineeringDocumentVersion` 的内部版本一致性已经存在，但订单评审并不能以正式外键到达该版本集合。

因此：

```text
设计任务 = COMPLETE
现有端到端正式数据关系 = INCOMPLETE
最小实施 = REQUIRES SCHEMA CHANGE + MIGRATION
无数据库修改完成正式追溯 = NO
本轮数据库、Migration、业务数据修改 = 0
```

最终 Gate：

```text
PCE CRM TO PDE DATA RELATION DESIGN COMPLETE
```

该 COMPLETE 只表示设计核查和最小关系方案完成，不表示关系已经实施、数据已经迁移或运行链已经通过。

## 2. 边界、治理与证据

目标是检查 `SalesOrder → SalesOrderItem → OrderReview → PDE工程对象 → ProductVersion/BOMVersion/RoutingVersion/EngineeringDocumentVersion` 的正式追溯。非目标是开发或重建 CRM、PDE、BOM、Routing、工程资料、版本管理，或实施 Schema、Migration、业务数据、权限、Workflow 与页面变化。

治理回执：`D:\Dev-PCE\AGENTS.md`、`D:\Dev-PCE\Source\AGENTS.md`、V1.2 主治理规范、模块保护规范、Completed Module Registry 与 Protection Preflight 均已全文读取；`Effective Instruction Set = YES`；`Instruction Register = CRM-PDE-RELATION-DESIGN-20260930-001 / ACTIVE`；冲突为 NONE。

```text
Preservation Standard Read = YES
Completed Module Registry Read = YES
Affected Protected Modules = [sales-order-source-intake, engineering-calculation-six-continuations, PDE version chain]
Affected Frozen Modules = []
Freeze Contracts Read = []
Unfreeze Authorization = NO
Preflight Result = SAFE TO MODIFY（仅本报告）
```

Registry 无 `FROZEN_VERIFIED` 项且相关 `freezeContractPath=null`，不等于无保护；既有页面、API、数据权威、权限、Workflow 和身份仍须保留。

关键代码证据：`backend/sales/models.py:22-315`；`backend/pde/models.py:854-923,1145-1438,1542-1646,2046-2275,2637-2891`；`backend/pde/order_review_service.py:508-607,881-885,988-1032`；`backend/sales/engineering_source_formalization.py:142-254`；`backend/pde/order_demand_preparation_service.py:82-116,405-426`；`backend/pde/order_bom_handoff_service.py:55-73,174-251`；CRM/PDE 流程 Registry。

只读数据证据：当前 `backend/db.sqlite3` 未完整部署目标 CRM/评审/版本表，不能证明运行链 PASS。历史只读副本包含 SalesOrder 3、SalesOrderItem 6、Review 3、Source 12、ProductVersion 1、OrderEngineeringInstance 1、BOMVersion 0、RoutingVersion 42、EngineeringDocumentVersion 0、ProductManufacturingOutput 0；它仅证明历史结构和数据状态，不是当前运行权威。同键来源和同键评审未发现重复；同一来源号的多个不同版本属于版本历史。

## 3. 已有关系

| 关系 | 状态 | 证据与判断 |
|---|---|---|
| SalesOrder → SalesOrderItem | FORMAL / COMPLETE | `ForeignKey(PROTECT)`；订单内行号唯一；正式行身份不得由来源行号替代 |
| SalesOrderItem → ProductDefinition/ProductVersion/ProductManufacturingOutput/EngineeringDocumentVersion | FORMAL / PARTIAL | 已有外键和一致性校验，但绕过订单评审 |
| SalesOrderItem → OrderEngineeringInstance → baseline_product_version | FORMAL | 一对一订单工程实例，含公司、产品、物料、版本与来源校验；应复用为 PDE 工程锚点 |
| ProductVersion → BOMVersion、RoutingVersion | FORMAL | 两类版本独立指向同一产品版本 |
| EngineeringDocumentVersion → ProductVersion+BOMVersion+RoutingVersion | FORMAL / STRONG | 校验同产品、同产品版本和主表一致性 |
| ProductManufacturingOutput → 完整版本集合 | FORMAL / STRONG | 组合产品/BOM/工艺/资料版本；发布要求齐套且全部 released |
| CRM/PDE 流程节点 | PROCESS PROJECTION EXISTS | 节点顺序已存在；页面跳转不能替代底层正式关系 |

不需要重建 PDE、BOM、Routing、工程资料或版本集合。缺口集中在订单评审与正式订单/订单行/PDE 工程对象之间。

## 4. 缺失关系

### GAP-01：OrderReview 缺少正式 SalesOrder 关系

严重度：P0

`OrderCrossFunctionalReview` 只有：

- `source_record`；
- `source_order_no` 文本；
- `source_version` 和 `source_content_hash` 快照。

没有 `sales_order_id`。服务端的 `formalSalesOrderEstablished` 主要读取来源 JSON 中的 `matchedSalesOrderId` 或 `formalSalesOrderCreated`，并没有重新读取正式 SalesOrder 外键事实。来源正式化预览虽然会按 `SalesOrder.external_source_no` 查找匹配订单，但结果只是运行时匹配。

影响：订单号重复、来源文本变化、JSON 陈旧、订单重新编号或跨公司错误时，评审不能由数据库关系保证归属。

### GAP-02：OrderReview 缺少 SalesOrderItem 范围关系

严重度：P0

评审是订单级对象，但工程准备和版本选择是订单行级对象。当前没有不可变的“本评审覆盖哪些正式订单行”关系。

影响：无法证明某个订单行是否包含在该评审版本中；新增、取消或拆分订单行后，也无法判断旧评审是否仍覆盖当前范围。

### GAP-03：OrderReview → PDE工程对象缺少正式交接

严重度：P0

`OrderEngineeringInstance` 有订单行和来源记录，但没有指向 `OrderCrossFunctionalReview` 或已确认 `OrderEngineeringBaseline` 的关系。`order_demand_preparation_service` 通过设计项共同 `source_record` 查找 PDE 评审；这是来源相关性，不是正式业务交接。

影响：不能数据库级证明工程实例来自哪个通过的 CRM 订单评审/PDE 可行性评审，也不能证明使用的是哪个不可变评审版本。

### GAP-04：EngineeringVersion 业务含义未统一

严重度：P0（命名与权威风险）

仓库中不存在 `EngineeringVersion` 模型。现有对象分工是：

- `EngineeringSourceRecord.source_version`：外部或历史来源版本；
- `ProductDesignRevision`：单个设计项修订；
- `OrderEngineeringBaseline`：整单工程事实的不可变受控快照；
- `EngineeringCalculationRecord.revision`：核算修订；
- `ProductManufacturingOutput`：产品/BOM/工艺/资料的制造发布组合。

这些对象不能互相替代。特别是 `EngineeringSourceRecord.source_version` 不能升级为正式订单工程版本。

### GAP-05：ProductVersion 到订单工程基线的选择关系不完整

严重度：P1

`OrderEngineeringInstance.baseline_product_version` 可以保存订单行使用的基线产品版本，但 `OrderEngineeringBaseline` 本身没有直接保存每个范围项所选 `ProductVersion`。产品版本管理服务有时按产品取当前候选版本用于展示，这不是不可变选择事实。

影响：工程基线回读可证明来源与设计内容，但不总能证明当时采用的产品版本。

### GAP-06：版本链是组合关系，不是严格串行父子关系

严重度：P1

目标表达中的 `ProductVersion → EngineeringVersion → BOMVersion → RoutingVersion → EngineeringDocumentVersion` 容易被误解为每一层只有一个下游版本。现有正确模型是：

```text
ProductVersion
├─ BOMVersion
├─ RoutingVersion
└─ EngineeringDocumentVersion（同时锁定 ProductVersion + BOMVersion + RoutingVersion）

ProductManufacturingOutput
└─ 锁定上述完整版本集合，并可绑定 OrderEngineeringInstance
```

不得把 RoutingVersion 设计成 BOMVersion 的子版本，也不得为满足线性图而新增错误外键。

## 5. EngineeringSourceRecord 定位裁决

本轮确认如下：

```text
历史来源 = YES
辅助证据 = YES
正式业务关系 = NO
```

理由：

1. 它保存 `source_type`、`source_version`、原始 payload 和 content hash，适合来源追溯与防篡改；
2. 它已被产品设计项、订单工程实例、核算和基线明细引用，适合作为证据链；
3. 它不具备 SalesOrder/SalesOrderItem 的商业身份、订单行范围或正式评审状态；
4. 当前评审直接依赖它，是现状兼容关系，不应被解释为“来源记录就是订单评审事实”。

保留规则：

- 保留所有现有 `source_record` 外键和版本/hash 快照；
- 不删除、不改名、不把来源记录并入 SalesOrder；
- 新正式关系建立后，来源记录继续作为 provenance；
- 正式资格判断必须使用 SalesOrder、SalesOrderItem、Review、PDE 工程对象和 Workflow 当前事实，不得只凭来源状态。

## 6. 最小数据关系设计

### 6.1 推荐的正式追溯图

```text
SalesOrder
└─ SalesOrderItem
   ├─ OrderReviewScopeItem ──> OrderCrossFunctionalReview
   │                            ├─ sales_order
   │                            └─ source_record（辅助证据）
   └─ OrderEngineeringInstance
      ├─ accepted_crm_order_review
      ├─ accepted_pde_feasibility_review
      ├─ confirmed_engineering_baseline（可选；按现有基线流程）
      ├─ baseline_product_version
      ├─ source_record（辅助证据）
      └─ ProductManufacturingOutput
         ├─ ProductVersion
         ├─ BOMVersion
         ├─ RoutingVersion
         └─ EngineeringDocumentVersion
```

### 6.2 最小新增关系 A：OrderCrossFunctionalReview.sales_order

建议字段：

```text
OrderCrossFunctionalReview.sales_order
  FK sales.SalesOrder
  on_delete = PROTECT
  related_name = cross_functional_reviews
  nullable only during controlled legacy backfill window
```

规则：

- 新建正式评审必须非空；
- `review.company_id == sales_order.company_id`；
- `source_order_no` 保留为不可变来源快照，不再作为 join key；
- `source_record` 保留为辅助证据；
- 查询、权限、Workflow 和幂等键使用 `sales_order_id + review_type + review_version` 作为正式业务范围。

### 6.3 最小新增关系 B：OrderReviewScopeItem

建议新增纯关联模型，不承载第二套评审事实：

```text
OrderReviewScopeItem
  review FK OrderCrossFunctionalReview PROTECT
  sales_order_item FK SalesOrderItem PROTECT
  item_version_snapshot
  scope_hash_snapshot
  included_at
  unique(review, sales_order_item)
```

规则：

- 订单行必须属于 `review.sales_order`；
- 评审提交后范围不可变；
- 全单评审在提交时固化当时全部有效订单行；
- 订单行后来新增、取消或变更时，旧评审保持历史，新版本评审重新固化范围；
- 不把 `EngineeringSourceRecord` 的行数或来源行号当 SalesOrderItem 范围。

### 6.4 最小新增关系 C：OrderEngineeringInstance 的评审交接

建议在现有 `OrderEngineeringInstance` 上增加受保护引用：

```text
accepted_crm_order_review FK OrderCrossFunctionalReview PROTECT
accepted_pde_feasibility_review FK OrderCrossFunctionalReview PROTECT, nullable by process applicability
confirmed_engineering_baseline FK OrderEngineeringBaseline PROTECT, nullable until baseline confirmed
```

校验：

- CRM 引用必须是 `CRM_ORDER_REVIEW`；
- PDE 引用必须是 `PDE_PRODUCTION_FEASIBILITY`；
- 引用必须属于同公司、同 `SalesOrder`，且 scope 包含当前 `sales_order_item`；
- 引用必须是已提交并由 Workflow 当前事实最终通过的版本；
- 工程实例创建时保存精确 review PK，不按“最新版本”动态漂移；
- 评审撤回或订单行变化不得原地改旧实例，应按现有版本/失效规则形成新实例或阻断。

### 6.5 EngineeringVersion 的最小裁决

不新增泛化 `EngineeringVersion` 表。

正式口径建议固定为：

- “订单工程版本”展示名对应现有 `OrderEngineeringBaseline`，业务唯一身份使用 baseline PK/`baseline_no`/sequence/snapshot hash；
- “产品工程版本”对应现有 `ProductVersion`；
- “制造工程发布组合”对应现有 `ProductManufacturingOutput`；
- “来源版本”只对应 `EngineeringSourceRecord.source_version`；
- “设计修订”只对应 `ProductDesignRevision`；
- “核算修订”只对应 `EngineeringCalculationRecord.revision`。

若有权业务主体未来坚持建立独立 `EngineeringVersion`，必须先单独裁决对象粒度、生命周期、唯一身份及与上述五类对象的替代关系；本任务不授权该新模型。

### 6.6 ProductVersion 与完整版本集合

复用现有关系，不新增串行外键：

- `OrderEngineeringInstance.baseline_product_version` 保存订单行采用的产品版本；
- `BOMVersion.product_version` 和 `RoutingVersion.product_version` 继续独立指向同一 ProductVersion；
- `EngineeringDocumentVersion` 继续同时锁定 ProductVersion、BOMVersion 和 RoutingVersion；
- `ProductManufacturingOutput` 继续作为完整发布集合，并绑定 OrderEngineeringInstance；
- 正式追溯以 `ProductManufacturingOutput` 为版本集合终点，而不是由页面逐层猜选“最新版本”。

## 7. 服务与流程最小调整设计

仅描述未来实施，不在本轮执行。

### 7.1 评审服务

- `build_review_facts` 必须从 `sales_order` 外键读取正式订单事实；
- `matchedSalesOrderId`、`formalSalesOrderCreated` 和 `source_order_no` 只保留诊断/兼容用途；
- 保存草稿时固化 `OrderReviewScopeItem`；
- 提交前校验订单行范围 hash 未变化；
- API、页面、诊断和验收报告复用同一正式关系查询。

### 7.2 PDE 准备服务

- 不再以 `source_record_id__in` 单独选择评审；
- 先按 SalesOrder/SalesOrderItem 找精确已通过评审，再交给现有 OrderEngineeringInstance；
- 来源记录只用于验证 review/instance 的 provenance 一致性；
- 不自动创建 ProductVersion、BOMVersion、RoutingVersion 或工程资料版本。

### 7.3 版本追溯服务

提供只读统一追溯 DTO：

```text
salesOrderId
salesOrderItemId
crmOrderReviewId/reviewVersion
pdeFeasibilityReviewId/reviewVersion
orderEngineeringInstanceId
engineeringBaselineId/baselineNo/snapshotHash
productVersionId/versionNo
manufacturingOutputId
bomVersionId/versionNo
routingVersionId/versionNo
engineeringDocumentVersionId/versionNo
sourceRecordId/sourceVersion/contentHash (provenance only)
```

任何必需正式对象缺失时返回明确 gap，不从上一页缓存、来源 JSON 或最大版本号补齐。

### 7.4 流程节点

保留 CRM 和 PDE 现有节点，不新增流程。只在节点进入条件中增加：

- CRM 订单评审必须有正式 SalesOrder 和固化行范围；
- PDE 工程准备必须读取已通过的精确评审版本；
- 产品版本、BOM、Routing、工程资料沿用现有 PDE 生命周期；
- 评审通过不自动发布任何版本，也不自动创建制造输出。

## 8. Schema、Migration 与无数据库修改判断

### 8.1 是否需要 Schema 变化

`YES`。

最低需要：

1. `OrderCrossFunctionalReview.sales_order`；
2. `OrderReviewScopeItem` 关联表；
3. `OrderEngineeringInstance.accepted_crm_order_review`；
4. 按适用流程增加 `accepted_pde_feasibility_review`；
5. 如订单工程基线被正式作为订单工程版本，增加 `confirmed_engineering_baseline` 精确引用。

### 8.2 是否需要 Migration

`YES`。

任何上述外键、约束、索引或关联表都必须通过后续独立授权的 Migration 实施。本轮未创建 Migration。

建议未来分两阶段：

1. 先加 nullable 关系、只读审计命令和一致性报告；
2. 仅对唯一可证明的历史记录受控回填，再增加新数据非空/一致性约束。

无法唯一证明的历史记录保持 `UNRESOLVED`，禁止按订单号或来源号强行匹配。

### 8.3 是否可以无数据库修改完成

分开回答：

- 本次“最小数据关系设计报告”：`YES`，已在零数据库修改下完成；
- 正式端到端可追溯关系：`NO`；
- 只用服务层拼接：`NO`，因为这会继续让来源记录/字符串代替正式业务关系；
- 仅增加只读诊断：可以改善可见性，但不能关闭 GAP-01 至 GAP-05。

## 9. 重复来源与来源替代检查

### 9.1 重复来源

- Schema 对 `(company, source_no, source_version)` 已有唯一约束；
- 只读历史副本未发现同键重复；
- 同一 `source_no` 的多个 `source_version` 是合法版本历史，不应视为重复；
- 仍需在未来 Migration 前审计“不同 source_no/hash 指向同一真实来源”的语义重复，数据库唯一键无法自动发现该问题。

### 9.2 来源记录替代正式对象

当前存在替代风险：

- 评审直接绑定来源记录，而非正式订单；
- PDE 准备通过共同来源记录推断评审；
- `formalSalesOrderEstablished` 可由来源 payload 标志得出；
- 页面 URL 的 `engineeringVersion` 曾使用 `source.source_version`，容易被业务用户理解为正式工程版本。

结论：来源记录当前是兼容连接和证据，但不得继续作为正式关系权威。

## 10. 验收与非回归设计

未来实施至少验证：

1. 现有 CRM/PDE 页面、Route、API、权限和 Workflow 不减少；
2. 旧 `source_record`、source version/hash 与历史评审可完整回读；
3. 新评审必须精确关联一个 SalesOrder，并固化正确订单行范围；
4. 同订单号跨公司不能串联；
5. 订单行新增或变更后，旧评审范围保持不变并阻断静默沿用；
6. OrderEngineeringInstance 只能引用覆盖当前订单行的已通过评审；
7. ProductVersion、BOMVersion、RoutingVersion、EngineeringDocumentVersion 必须属于同一产品/版本集合；
8. ProductManufacturingOutput 继续执行现有发布与齐套校验；
9. 来源记录不再决定正式订单/评审/版本资格；
10. 不创建平行 CRM、PDE、BOM 或版本模型。

## 11. 风险与停止点

| 风险 | 等级 | 处理 |
|---|---|---|
| 直接按 `source_order_no` 回填错误订单 | P0 | 必须使用公司、正式订单、来源 hash、订单行范围和人工异常队列联合证明 |
| 把 EngineeringSourceRecord 当 OrderReview/EngineeringVersion | P0 | 明确 provenance-only，正式资格读取外键与 Workflow |
| 新建泛化 EngineeringVersion 与现有基线/修订/发布组合重复 | P0 | 当前禁止新增；先统一业务口径 |
| 为线性流程图错误增加 BOM→Routing 父子关系 | P0 | 保持共同 ProductVersion + 发布组合模型 |
| 历史数据无法唯一匹配 | P1 | 保持 nullable/UNRESOLVED，不猜配 |
| 当前开发数据库未完整部署目标 Schema | P1 | 后续实施先确认目标环境和 migration graph；本轮不执行 |

停止点：本报告归档、完整回读和校验后立即停止，不进入 Schema、Migration、服务、API、页面、权限、Workflow 或数据实施。

## 12. 合规矩阵

| Compliance Item | Result | Evidence / Note |
|---|---|---|
| Original Goal | PASS | 已确认已有关系、缺口和最小设计 |
| Governance Reading Receipt | PASS | 五份强制治理/保护文件已全文读取 |
| Effective Instruction Set | PASS | `CRM-PDE-RELATION-DESIGN-20260930-001` |
| Scope / Stop Condition | PASS | 仅设计；报告后停止 |
| Existing Results Preserved | PASS | 仅新增报告；未修改既有实现 |
| Automated Tests | N/A | 无源码变化；使用静态证据与 SQLite 只读核查 |
| User-Visible Real Path | N/A | 非 UI 实施/验收任务 |
| UI Data Visibility | N/A | 非 UI 数据可见性任务 |
| Non-Regression | PASS | Code/DB/Migration/API/Page/Workflow 均未修改 |
| User Manual Validation | N/A | 本轮不声明用户人工业务验收 |
| Production Boundary | PASS | Unauthorized Business Writes = 0 |
| Report vs User Reality Conflict | NONE | 未收到冲突性用户运行证据 |
| Final Stop Condition | PASS | 不进入实施 |

## 13. 保护状态

```text
Documentation Changed = YES
Code Changed = NO
Database Changed = NO
Migration Created = NO
API Created = NO
Page Created = NO
Organization Data Changed = NO
Responsibility Data Changed = NO
Employee Data Changed = NO
Permission Model Changed = NO
Workflow Runtime Changed = NO
ApprovalTask Changed = NO
RRE Started = NO
CRM Business Data Changed = NO
PDE Business Data Changed = NO
BOM Data Changed = NO
Routing Data Changed = NO
Engineering Document Data Changed = NO
Unauthorized Business Writes = 0
```

## 14. 归档状态

```text
Context Scope = CONTROLLED
Task Scope = SINGLE
Review Level = B
Full Content Review Required = NO
Documentation Archived = YES
Archive Content Readback = YES
ChatGPT Reviewable = YES
Output Size = WITHIN 500 LINES
```

