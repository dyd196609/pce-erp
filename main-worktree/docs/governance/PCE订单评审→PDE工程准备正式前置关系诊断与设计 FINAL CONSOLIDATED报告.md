# 《PCE订单评审→PDE工程准备正式前置关系诊断与设计 FINAL / CONSOLIDATED报告》

报告日期：2026-09-30（Asia/Shanghai）  
任务阶段：第1条／事实诊断与最小设计  
任务类型：READ ONLY + DESIGN  
实施基线：`295d8682ed0299756444deb0a354418bd9c8180a`  
Parent：`ca4264dadf754f3efd511a2ee962e371fca0ad64`  
总体结论：**诊断与最小设计完成；正式前置关系缺口确认存在；本轮未实施。**

## 1. 执行结论

当前系统已经具备 CRM 准入 Gate、CRM 评审到销售订单/订单行范围的 0032 正式关系、PDE 评审版本、最终审批、产品设计项、订单行工程实例等独立能力，但它们尚未形成一条不可变的正式前置链。

当前真实关系是：

```text
CRM Review --P0运行时判定--> 下游服务
CRM Review --0032正式关系--> SalesOrder + SalesOrderItem范围（仅新在线数据；当前真实库0行）

PDE Review --共同source_record/source_order_no--> CRM Review候选
PDE Review --通用document_type/document_id--> WorkflowInstance --> ApprovalDecision

ProductDesignItem --> SalesOrderItem + EngineeringSourceRecord
OrderEngineeringInstance --> SalesOrderItem + EngineeringSourceRecord + 工程身份
```

缺少的是：

1. PDE Review 对一个精确 CRM Review/0032关系的不可变前置引用；
2. 已批准 PDE Review、精确 ApprovalDecision 与工程准备资格之间的不可变授权对象；
3. OrderEngineeringInstance 对该工程准备授权的正式 FK；
4. 所有工程准备写入口对同一正式授权的统一复用。

因此：

```text
Schema Change = YES
Migration = YES
0032 Alone Is Sufficient = NO
Historical Auto Backfill = NO
```

## 2. 范围与停止边界

IN SCOPE：

- CRM Order Review；
- PDE Production Feasibility Review；
- PDE Engineering Preparation；
- OrderEngineeringInstance；
- SalesOrder / SalesOrderItem；
- 0032正式关系；
- Review Workflow / ApprovalDecision；
- 相关准备、设计与正式工程接续服务；
- 当前验收库只读事实。

OUT OF SCOPE：EngineeringCalculation→Baseline、MaterialRequirement、BOM、Routing、ProductVersion、ProductManufacturingOutput、工程资料发布、页面、权限重设计、Workflow重设计、历史数据写入。

本轮唯一允许的文件变化是新增本报告。

## 3. 治理与保护回执

### COMPLETED MODULE GOVERNANCE READING RECEIPT

- 已全文读取 `D:\Dev-PCE\AGENTS.md`、当前 `AGENTS.md`、`PCE CODEX开发指令规范管理V1.2.md`、`PCE 已开发模块固化与变更保护规范 V1.0.md`、Completed Module Registry、Protection Preflight。
- Preservation Standard：Preserve-and-Extend。
- Registry：`currentFrozenVerifiedModuleIds=[]`。
- Affected Frozen Modules：NONE；既有 CRM/PDE 成果仍受保护。
- Freeze Contracts：无适用专项合同。
- Unfreeze Authorization：NOT REQUIRED。
- Preflight：`SAFE TO MODIFY`，仅限新增本报告。
- 未推翻或重建 Review、SalesOrder、OrderEngineeringInstance、Workflow、权限、页面或来源体系。

## 4. 原开发成果读取清单

### 4.1 当前基线源码、模型、Migration与测试

已读取并交叉核对：

- `backend/pde/models.py`；
- `backend/pde/migrations/0025_order_cross_functional_review.py`；
- `0026_order_review_itemized.py`；
- `0027_order_review_participant_grant.py`；
- `0031_merge_pde_legacy_and_order_chain.py`；
- `0032_order_review_sales_order_relation.py`；
- `backend/pde/crm_order_admission.py`；
- `order_demand_preparation_service.py`；
- `product_design_service.py`；
- `formal_engineering_continuation_service.py`；
- `engineering_calculation_service.py`；
- `production_foundation_service.py`；
- `backend/sales/services.py`；
- P0 Gate、订单需求准备、0032正式关系相关测试；
- WorkflowInstance、ApprovalTask、ApprovalDecision模型。

### 4.2 原开发工作树事实

原开发工作树中的以下已有成果也已读取：

- `backend/pde/order_review_service.py`；
- `backend/pde/order_review_approval.py`；
- `backend/pde/order_review_views.py`；
- `backend/pde/review_permission_catalog.py`；
- `backend/pde/order_review_signoff_readiness.py`；
- CRM/PDE Review路由及既有评审测试。

这些文件是既有开发与验收依据，但当前仍是原脏工作树中的未跟踪/未收口成果，**不在 commit `295d8682...` 的Git树内**。本报告不把“原开发成果存在”误写为“已进入当前唯一可重建基线”。第2条实施必须先按依赖闭包原样承接，不得重写成第二套评审服务。

### 4.3 历史FINAL / CONSOLIDATED证据

已读取当前链路完整核查、P0问题收敛、P0 Gate依赖基线收敛、订单评审正式关系验证结案、CRM/PDE最小数据关系设计、最小实现开发、CRM/PDE业务关系收敛，以及订单评审分离、逐项签认、最终审批、真实运行链、三页面读取恢复、订单工程基线和正式工程接续等归档报告。

历史报告仅用于解释原设计裁决；当前源码、当前Migration、当前真实库事实优先。

## 5. 当前真实开发位置

| 项目 | 当前事实 |
|---|---|
| 唯一实施commit | `295d8682ed0299756444deb0a354418bd9c8180a` |
| 独立干净worktree | `C:\Users\DAODA\.codex\worktrees\p0-chain-fix\Source` |
| worktree状态 | clean |
| PDE Migration叶节点 | `0032_order_review_sales_order_relation` |
| 真实验收库0032 | 已应用 |
| 验收库执行前后只读SHA | `7E68600E46B3569CE0F57D0C8EE15FA4BA19EED5573C4D793747298FDD6DFF8F` |
| 原开发工作树 | 大量既有未提交/未跟踪成果，仅作证据，不作实施基线 |

P0-01、P0-02和订单评审→订单正式关系均已关闭。本任务不退回旧Migration历史，不修改0032。

## 6. 当前对象事实

### 6.1 OrderCrossFunctionalReview

- 单表承载 `CRM_ORDER_REVIEW` 与 `PDE_PRODUCTION_FEASIBILITY`；
- FK：company、EngineeringSourceRecord、reviewer；
- 关键字段：review_type、source_order_no、source_version、source_content_hash、review_version、conclusion、record_status、item_summary；
- 唯一约束：company + review_type + source_order_no + review_version；company + review_type + idempotency_key；
- `SUBMITTED` 后禁止覆盖修改；
- CRM与PDE两个Review之间没有FK、关联表或精确前置版本字段。

### 6.2 OrderReviewSalesOrderRelation / OrderReviewScopeItem

- 0032已建立 CRM Review OneToOne → SalesOrder；
- company、review、sales_order均为受保护关系；
- 只允许 `CRM_ORDER_REVIEW`；
- 范围支持 WHOLE_ORDER、SELECTED_ITEMS、UNRESOLVED；
- ScopeItem正式指向SalesOrderItem并保存行号、外部行号和身份哈希；
- 关系只追加，不允许改指或删除；
- 当前真实库两表均为0行，未执行历史回填。

### 6.3 SalesOrder / SalesOrderItem

- SalesOrder拥有正式PK、公司、业务编号、外部来源号和version；
- SalesOrderItem正式FK到SalesOrder，订单内line_no唯一；
- 是OEI的正式订单行身份；
- `external_source_no`、source_order_no仅能作为来源线索，不能替代FK。

### 6.4 EngineeringSourceRecord

- 保存来源编号、来源类型、来源版本、payload、content_hash和状态；
- `(company, source_no, source_version)`唯一；
- 当前定位不变：`历史来源 = YES；辅助证据 = YES；正式业务前置关系 = NO`。

### 6.5 ProductDesignItem

- 正式FK到SalesOrderItem、EngineeringSourceRecord及工程主数据；
- 保存source_version/content_hash快照；
- 可以证明设计项属于哪个订单行及来源；
- 不保存CRM Review、PDE Review、Workflow或ApprovalDecision；
- 不得因设计项与Review同source_record而推定正式前置关系。

### 6.6 ProductEngineeringReadiness

- 可选FK到SalesOrder，SalesOrderItem为可选OneToOne；
- 保存工程、BOM、Routing、资料、制造输出和MRP准备状态；
- 不关联CRM/PDE Review或OEI；
- 当前真实库0行；本轮不把它提升为新的授权权威。

### 6.7 OrderEngineeringInstance

- OneToOne正式关联SalesOrderItem；
- FK关联company、EngineeringSourceRecord；
- 工程身份为长期产品+基线产品版本，或产品分类+选定工艺类型；
- `(company, instance_no)`唯一；
- 不保存CRM Review；
- 不保存PDE Review；
- 不保存Workflow、ApprovalDecision或工程准备授权；
- 创建后只能从共同source_record和订单行外围推断评审，无法固定还原当时采用的PDE评审版本。

### 6.8 WorkflowInstance / ApprovalDecision

- WorkflowInstance通过通用 `(document_type, document_id)`关联业务文档，数据库没有到Review的FK；
- `(document_type, document_id)`唯一；
- ApprovalDecision通过ApprovalTask关联WorkflowInstance；
- 它能证明某个具体Review文档的最终审批，但不能证明该Review是哪一个CRM前置关系，也不能证明某个OEI采用了该决定。

## 7. 当前真实关系图

```text
EngineeringSourceRecord
  ├─ CRM Review (review_type=CRM_ORDER_REVIEW)
  ├─ PDE Review (review_type=PDE_PRODUCTION_FEASIBILITY)
  ├─ ProductDesignItem ──> SalesOrderItem ──> SalesOrder
  └─ OrderEngineeringInstance ──> SalesOrderItem

CRM Review
  └─ OrderReviewSalesOrderRelation ──> SalesOrder
       └─ OrderReviewScopeItem ──> SalesOrderItem

PDE Review
  └─ (document_type + document_id) ──> WorkflowInstance
       └─ ApprovalTask ──> ApprovalDecision

缺失：
CRM正式关系 ─X─> PDE Review ─X─> 工程准备授权 ─X─> OEI
```

CRM与PDE Review当前唯一共同业务线索是company、source_record、source_order_no、source_version和source_content_hash。它们不是数据库级前置关系。

## 8. CRM Review → PDE Review专项结论

### 8.1 PDE评审创建的当前依据

原开发 `order_review_service.py` 按review_type和来源上下文创建版本；PDE评审创建时未保存：

- 精确CRM review PK；
- CRM review_version；
- OrderReviewSalesOrderRelation PK；
- 被覆盖的OrderReviewScopeItem集合或范围哈希。

P0 Gate能对给定来源上下文判定CRM准入，但它是运行时判定，不是不可变前置关系。多个CRM复评版本存在时，如果调用方不持久化Gate返回的review_id/review_version，后续仍可能重新选择不同版本。

### 8.2 0032能否复用

必须复用，而且只能把0032作为唯一订单关系权威。PDE Review不应再建立第二个独立SalesOrder FK或另一套订单行范围表。

但是0032只允许CRM Review，不能单独表达“哪个PDE Review基于哪个CRM评审版本及其订单范围”。因此0032不足以关闭当前缺口。

### 8.3 CRM结论与准入语义

- 显式历史 `REJECT`：P0 Gate硬阻断，不能被后续approved覆盖；
- `RETURN_FOR_COMPLETION`：阻断；
- Workflow/ApprovalDecision rejected：阻断；
- Pending或决定缺失：阻断；
- 新逐项流程 `conclusion=""`：以最终Workflow/ApprovalDecision为准；
- `CONDITIONAL`：原开发裁决没有把它定义为自动放行；在不存在服务端条件关闭事实时必须阻断。条件关闭对象属于未来独立业务设计，不得由本任务伪造。

结论：准入规则已有主体，但PDE Review没有持久化具体准入结果，正式前置关系仍缺失。

## 9. PDE Review → OEI专项结论

`FormalEngineeringContinuationService.create_instance`当前执行：

1. 读取SalesOrderItem；
2. 通过ProductDesignItem解析唯一source_record、产品分类和工艺类型；
3. 调用CRM P0 Gate；
4. 调用ProductionFoundationService创建OEI；
5. 审计仅保存orderNo、lineNo和designItemIds。

它没有：

- 查询PDE Review；
- 校验PDE Review的record_status/conclusion；
- 校验PDE Workflow/ApprovalDecision；
- 读取0032关系及订单行范围；
- 保存任何PDE review_id/review_version/approvalDecisionId。

因此当前OEI创建可在CRM Gate通过后直接发生；数据库不能证明其依据了哪个已批准PDE评审。共同source_record不是正式前置关系。

## 10. 工程准备实际调用链

### 10.1 order_demand_preparation

样本专用 `_target_facts`：

- 精确查找指定开发订单、source版本/hash和PDE Review v2；
- 调用CRM P0 Gate；
- 要求PDE Review为SUBMITTED；
- 要求PDE Workflow approved、ApprovalDecision approved及10/10签认；
- 不读取0032关系或OrderReviewScopeItem；
- 不检查PDE Review的conclusion字段；
- 返回review/workflow/decision，但只在ExternalIdentity审计JSON中保存其ID，不形成正式FK。

### 10.2 engineering_readiness_facts

普通只读路径从ProductDesignItem取得source_record集合，再查询PDE Review并按 `-review_version, -pk` 取第一条。它没有同时限定SUBMITTED、业务结论、Workflow和最终决定。

此前发现的“通过ProductDesignItem/source_record反查并选择最高PDE评审版本”风险在当前295基线中仍存在。

### 10.3 product_design_context

普通读取上下文从设计项解析唯一source_record，然后在所有已提交Review中按 `-review_version, -pk` 选择第一条；该查询甚至没有先限定 `review_type=PDE_PRODUCTION_FEASIBILITY`，随后才按PDE document_type查Workflow。

通用设计写入口主要复用CRM P0 Gate，没有持久化PDE评审前置关系。样本专用写入口虽验证指定PDE v2，但仍未形成正式FK。

### 10.4 formal engineering continuation

OEI创建只复用CRM P0 Gate，PDE Review并非准入条件。其审计没有PDE review/decision身份。正式核算入口的P0保护不能补齐OEI历史前置关系。

## 11. 已存在且无需重建的能力

以下能力保留并直接复用：

1. P0 CRM Order Admission Gate及其显式REJECT优先规则；
2. 0032 `OrderReviewSalesOrderRelation`；
3. `OrderReviewScopeItem`及WHOLE_ORDER/SELECTED_ITEMS/UNRESOLVED语义；
4. Review类型、版本、提交后不可变和逐项签认；
5. 既有WorkflowInstance、ApprovalTask、ApprovalDecision；
6. SalesOrder→SalesOrderItem正式关系；
7. ProductDesignItem→SalesOrderItem/source_record关系；
8. OEI→SalesOrderItem/source_record及工程身份；
9. EngineeringSourceRecord的来源追溯能力；
10. 现有页面、权限和Workflow配置。

## 12. 已确认缺口与真实原因

| ID | 等级 | 缺口 | 真实原因与影响 |
|---|---|---|---|
| REL-PDE-01 | P1 | CRM Review与PDE Review无正式前置关系 | 原模型以共同来源区分评审类型，未保存P0 Gate返回的精确Review和0032关系；复评后可能漂移 |
| REL-PDE-02 | P1 | PDE Review未复用0032订单/行范围 | 0032后开发尚未扩展到PDE评审；不能证明PDE评审适用于哪个订单行 |
| REL-PDE-03 | P1 | PDE准备准入逻辑不统一 | 样本路径固定v2，普通读取取最高版本，通用写路径只用CRM Gate；不同服务解释不同事实 |
| REL-PDE-04 | P1 | OEI无已接受PDE评审/批准关系 | OEI创建只记录订单行、来源和设计项，历史版本无法由数据库固定还原 |
| REL-PDE-05 | P1 | SUBMITTED、conclusion、Workflow、Decision未形成一个权威资格 | SUBMITTED只是记录状态；动态查询可遗漏结论或审批条件 |
| REL-PDE-06 | P1 | 当前Git基线缺少原Review运行服务闭包 | 原服务虽已开发验证，但不在295 commit；若忽略会形成不可运行的局部修补 |

## 13. 最小正式数据模型

### 13.1 目标关系图

```text
CRM Review
  └─ OrderReviewSalesOrderRelation (0032，唯一订单关系权威)
       ├─ SalesOrder
       └─ OrderReviewScopeItem ──> SalesOrderItem
       |
       └─ PDEReviewPredecessorRelation
            └─ PDE Review
                 └─ WorkflowInstance ──> ApprovalDecision
                      |
                      └─ PDEEngineeringPreparationAuthorization
                           └─ OrderEngineeringInstance
                                └─ SalesOrderItem
```

### 13.2 新对象一：PDEReviewPredecessorRelation

职责：只表达“这个PDE评审版本基于哪个精确CRM正式订单评审关系”，不表达最终批准。

最小字段：

- `company` FK PROTECT；
- `pde_review` OneToOne FK → OrderCrossFunctionalReview，PROTECT；
- `crm_order_relation` FK → OrderReviewSalesOrderRelation，PROTECT；
- `crm_review_version_snapshot`；
- `pde_review_version_snapshot`；
- `order_version_snapshot`；
- `source_content_hash_snapshot`；
- `scope_identity_hash_snapshot`；
- `resolution_basis`；
- `created_by` FK PROTECT；
- `audit_hash` unique；
- `created_at`。

规则：

- pde_review必须为PDE_PRODUCTION_FEASIBILITY；
- crm_order_relation.review必须为CRM_ORDER_REVIEW；
- company、source_record、source_version、source_content_hash必须一致；
- CRM Gate返回的review_id/review_version必须与0032 relation一致；
- 一个PDE评审版本最多一个前置关系；
- 一个CRM关系允许多个PDE复评版本；
- 范围完全继承0032 relation及其ScopeItem，不复制第二套SalesOrder/SalesOrderItem关系；
- 在线PDE Review创建时同事务建立；
- 只追加、不可改指、不可删除。

### 13.3 新对象二：PDEEngineeringPreparationAuthorization

职责：把“前置关系”和“最终批准资格”固化为可被所有工程准备写入口复用的不可变业务事实。

最小字段：

- `company` FK PROTECT；
- `predecessor_relation` OneToOne FK → PDEReviewPredecessorRelation，PROTECT；
- `workflow_instance` FK/OneToOne → WorkflowInstance，PROTECT；
- `approval_decision` FK/OneToOne → ApprovalDecision，PROTECT；
- `pde_review_version_snapshot`；
- `pde_review_content_hash_snapshot`；
- `order_version_snapshot`；
- `scope_identity_hash_snapshot`；
- `authorization_basis`；
- `created_by` FK PROTECT；
- `audit_hash` unique；
- `created_at`。

创建条件：

- PDE Review精确为SUBMITTED；
- Workflow document_type/document_id精确指向该Review；
- Workflow状态approved；
- ApprovalDecision为approved；
- 显式REJECT、RETURN_FOR_COMPLETION、最终rejected或pending硬阻断；
- 新逐项流程conclusion为空时，以最终审批决定为准；
- 旧ACCEPT仍需最终approved；
- CONDITIONAL在没有正式条件关闭证据时阻断；
- 前置0032范围必须存在且非UNRESOLVED；
- 授权只追加，不通过改写Review或Workflow形成。

前置关系与授权必须分为两个对象：待审、驳回的PDE评审也需要保留其CRM前置历史，但不得形成工程准备授权。合并为一个对象会迫使系统后续修改不可变关系，或把“有前置”误写成“已批准”。

### 13.4 OrderEngineeringInstance最小扩展

新增：

```text
engineering_preparation_authorization
  FK PDEEngineeringPreparationAuthorization
  on_delete=PROTECT
  nullable for legacy rows at schema transition
```

新在线流程必须非空。OEI通过该FK可精确还原PDE Review、ApprovalDecision、CRM Review、SalesOrder及评审订单行范围，因此不再增加重复的 `accepted_crm_review` 和 `accepted_pde_review` 两个平行FK。

OEI.sales_order_item必须属于授权继承的0032范围；否则fail-closed。

### 13.5 统一服务Gate

新增单一服务 `require_pde_engineering_preparation_admission`：

- 输入company、SalesOrderItem、精确authorization或可唯一解析的正式前置身份；
- 只读取上述正式关系及当前不可变审批事实；
- 返回PDE review_id/review_version、CRM review_id/review_version、0032 relation、scope item、workflow和decision；
- 任一关系缺失、版本/hash不一致、范围不包含订单行、存在歧义时fail-closed；
- order_demand_preparation、产品设计写入口、OEI创建、正式工程核算入口复用同一结果；
- 禁止各服务再按source_record取最高Review。

只读页面事实可从正式关系投影；本轮及第2条均不要求页面改版。

## 14. Schema与Migration判断

| 问题 | 结论 |
|---|---|
| 是否需要Schema Change | YES |
| 是否需要Migration | YES，新建0033，不修改0032或历史Migration |
| 0032能否单独完成 | NO；它缺少PDE Review前置和批准授权 |
| 是否新增PDE predecessor | YES |
| OEI是否持久化accepted review | YES，通过authorization FK间接且唯一地持久化，不增加重复直接FK |
| 是否需要独立Gate/Authorization | YES；Gate为统一服务，Authorization为不可变正式对象 |
| 必须FK的关系 | PDE Review→predecessor、predecessor→0032 relation、authorization→predecessor/workflow/decision、OEI→authorization |
| 证据快照 | review versions、source hash、order version、scope hash、audit hash；不能代替FK |

Migration必须：

- 依赖 `pde.0032_order_review_sales_order_relation`；
- 创建两个新关系表；
- 给OEI增加nullable FK；
- 增加唯一约束、必要索引和基本CheckConstraint；
- 不含RunPython历史猜配、不改旧Migration、不fake、不回填真实验收库。

## 15. 真实验收库只读事实与历史分类

### 15.1 只读事实

- Review：3条；CRM #1，PDE #2/#3；
- SalesOrder：3条；SalesOrderItem：6条；
- ProductDesignItem：71条；
- OrderEngineeringInstance：5条；
- 0032 Relation：0条；ScopeItem：0条；
- WorkflowInstance：2条；ApprovalDecision：2条；
- CRM Review #1：SUBMITTED、review_version=1、conclusion=REJECT；其Workflow/Decision为approved；
- PDE Review #2：SUBMITTED、v1、ACCEPT，但没有Workflow/Decision；
- PDE Review #3：SUBMITTED、v2、ACCEPT；Workflow #2 approved、Decision #2 approved；
- ExternalIdentity #1941-#1945精确记录Review #3、Decision #2、SalesOrder #3及SalesOrderItem #3-#6；
- OEI #2-#5正式关联SalesOrderItem #3-#6和source #11，但其创建审计只含orderNo/lineNo/designItemIds，没有reviewId或decisionId。

查询使用SQLite只读URI和`PRAGMA query_only=ON`。数据库SHA保持：

`7E68600E46B3569CE0F57D0C8EE15FA4BA19EED5573C4D793747298FDD6DFF8F`

### 15.2 分类结果

| 对象/候选关系 | 分类 | 依据与未来处理 |
|---|---|---|
| CRM Review #1 → SalesOrder #3（订单头） | DETERMINISTICALLY_RESOLVABLE | company/source/version/hash及ExternalIdentity #1940唯一一致；未来仅可经批准历史manifest登记；该关系不代表评审通过 |
| CRM Review #1 → SalesOrderItem #3-#6评审范围 | UNRESOLVED | 0032范围表0行；不得因订单现有4行自动解释为历史评审范围 |
| CRM Review #1作为合格PDE前置 | UNRESOLVED / NOT ELIGIBLE | 显式REJECT为硬阻断；approved决定不能覆盖；不得建立“已接受前置” |
| PDE Review #2 → CRM前置 | UNRESOLVED | 只有共同source；无精确CRM PK、0032关系、Workflow或Decision |
| PDE Review #2 → 工程准备授权 | UNRESOLVED / NOT ELIGIBLE | 无最终审批事实 |
| PDE Review #3 → SalesOrder #3及Item #3-#6准备范围 | DETERMINISTICALLY_RESOLVABLE | ExternalIdentity #1941-#1945保存精确reviewId=3、decisionId=2及每个订单行 |
| PDE Review #3 → CRM正式前置 | UNRESOLVED | 没有前置FK；唯一CRM候选#1为显式REJECT，不能仅凭同源登记为合格前置 |
| ProductDesignItem #1-#71 → SalesOrderItem #3-#6/source #11 | DETERMINISTICALLY_RESOLVABLE | 现有FK直接证明 |
| ProductDesignItem #1-#71 → accepted PDE Review #3 | UNRESOLVED | 设计项本身无review/decision FK；外围准备审计不能替代每项正式前置 |
| OEI #1 → 本链Review | UNRESOLVED | company/source/order均属于另一上下文，无相关Review |
| OEI #2-#5 → SalesOrderItem #3-#6/source #11 | DETERMINISTICALLY_RESOLVABLE | 现有FK直接证明 |
| OEI #2-#5 → accepted PDE Review #3/Decision #2 | UNRESOLVED | OEI创建服务未读取PDE资格，审计也未保存review/decision；同源、时序和外围需求准备不足以证明实际授权 |

本轮及第2条实施都不得自动回填上述历史。未来若授权历史登记，只有表中明确标为DETERMINISTICALLY_RESOLVABLE的具体关系可进入人工批准manifest；其余保持UNRESOLVED。

## 16. 第2条最小实施文件范围

### 16.1 当前295基线直接修改/新增

- `backend/pde/models.py`；
- `backend/pde/migrations/0033_*.py`；
- 新统一 `pde_engineering_preparation_admission.py`；
- `order_demand_preparation_service.py`；
- `product_design_service.py`；
- `formal_engineering_continuation_service.py`；
- `production_foundation_service.py`（封闭通用OEI旁路）；
- 必要的专项测试及P0/0032非回归测试。

### 16.2 必须先纳管的原开发依赖闭包

由于295基线不含原Review运行服务，第2条必须明确授权以原开发原文为准纳管并最小扩展：

- `order_review_service.py`；
- `order_review_approval.py`；
- `order_review_views.py`；
- `review_permission_catalog.py`；
- `order_review_signoff_readiness.py`；
- 对应CRM/PDE后端路由、管理命令和既有Review测试中实际必需的闭包。

这属于把已经开发验证的Review运行链纳入可重建基线并接入新关系，不是页面改版、权限重设计或Workflow重设计。实施前必须做import依赖扫描，禁止复制、删减或伪造模块。

### 16.3 明确排除

- 前端页面及路由改版；
- 新权限、角色或Workflow定义；
- EngineeringCalculation、Baseline、BOM、Routing、ProductVersion等范围外文件；
- 历史数据脚本；
- 真实验收库Migration；
- 业务数据回填。

## 17. 第2条实施授权边界

下一条《PCE订单评审→PDE工程准备正式前置关系实施指令》应明确授权：

1. 基于commit `295d8682...`的独立干净worktree实施；
2. 纳管第16.2节已开发Review依赖闭包，不重新设计其页面、权限、Workflow；
3. 新增PDEReviewPredecessorRelation；
4. 新增PDEEngineeringPreparationAuthorization；
5. OEI增加nullable授权FK，新在线创建强制非空；
6. 新增统一PDE工程准备Admission Gate；
7. PDE Review创建同事务固化predecessor；最终批准同事务固化authorization；
8. 所有相关写入口复用同一Gate并阻断动态latest选择；
9. 仅在隔离库创建/执行0033并完成空库重建、migration graph、makemigrations check和专项/回归测试；
10. 不执行真实验收库、不回填历史、不进入范围外P1。

## 18. 必须覆盖的实施测试

1. PDE Review保存精确CRM review/0032 relation；
2. CRM显式REJECT、final rejected、pending分别阻断；
3. 多个CRM复评版本只使用Gate返回的精确版本；
4. WHOLE_ORDER和SELECTED_ITEMS范围正确继承；
5. 不在CRM范围内的订单行阻断；
6. PDE Review pending/rejected没有Authorization；
7. 新流程空conclusion + approved允许形成Authorization；
8. ACCEPT + approved允许；
9. CONDITIONAL无条件关闭事实时阻断；
10. OEI必须保存Authorization并能还原精确PDE/CRM review和decision；
11. 直接调用ProductionFoundation创建无授权OEI被阻断；
12. 动态最高Review不再决定写入资格；
13. 旧OEI保持不变、nullable、不自动回填；
14. P0 Gate与0032既有测试全部通过；
15. 任一步失败整笔事务回滚。

## 19. 风险与保护要求

| 风险 | 等级 | 保护措施 |
|---|---|---|
| 将同source_record解释成正式前置 | P0 | 只接受FK关系；来源仅作一致性证据 |
| 用最新/最高Review替代历史版本 | P0 | 创建时保存精确predecessor和authorization FK |
| 重复建设订单关系 | P0 | PDE关系只引用0032，不再保存第二个SalesOrder/Scope体系 |
| 将SUBMITTED解释成批准 | P0 | Authorization必须同时验证结论规则、Workflow和Decision |
| 将CONDITIONAL自动放行 | P1 | 无正式条件关闭事实时阻断 |
| 历史OEI自动猜配PDE Review | P0 | 保持nullable/UNRESOLVED，禁止RunPython回填 |
| 忽略未纳管原Review服务 | P0 | 第2条先完成精确依赖闭包；不在脏工作树直接开发 |
| 通用ProductionFoundation旁路 | P1 | 服务层统一Gate并增加模型/写服务一致性校验 |

## 20. 保护状态

```text
Documentation Change = YES（仅本报告）
Code Change = NO
Database Change = NO
Migration Change = NO
Business Data Write = NO
Permission Change = NO
Workflow Change = NO
Page Change = NO
Historical Backfill = NO
Unauthorized Business Writes = 0
```

## 21. 明确停止点与最终Gate

本报告已经一次完成事实诊断、真实调用链还原、历史数据分类、Schema/Migration判断、最小模型和第2条授权边界。无需再次执行“审计/调查/模型设计”前置轮次。

报告归档后立即停止：

- 不修改源码；
- 不创建Migration；
- 不修改数据库；
- 不回填历史；
- 不进入BOM、Routing、ProductVersion或其它P1问题。

下一步只允许进入：

`《PCE订单评审→PDE工程准备正式前置关系实施指令》`

**PCE ORDER REVIEW TO PDE ENGINEERING PREPARATION PREDECESSOR RELATION DIAGNOSIS AND DESIGN COMPLETE**
