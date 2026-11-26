# PCE订单→PDE→BOM→工艺路线P0实施 FINAL / CONSOLIDATED报告

报告日期：2026-09-30（Asia/Shanghai）  
任务边界：仅P0-01 CRM订单评审REJECT下游准入阻断、P0-02 Migration历史分支收口准备。  
总体Gate：**PCE CRM TO PDE P0 IMPLEMENTATION BLOCKED**。

> 结论先行：P0-01统一服务层Gate已经实施，要求的核心状态矩阵及历史对象零变更测试通过。P0-02已经在独立干净worktree恢复并纳管两条真实历史分支、Sales 0004/0005、依赖Migration并建立空操作merge；空库全量migrate成功且PDE仅一个叶节点。但是强制验证发现`makemigrations --check`未通过，并且隔离重建库与验收库副本存在一项`system_process` Schema差异。按照“失败立即停止、不得进入验收库”，未对验收库执行Migration，整体Gate必须BLOCKED。

## 1. 治理读取与保护回执

COMPLETED MODULE GOVERNANCE READING RECEIPT

- Preservation Standard：已全文读取`D:\Dev-PCE\AGENTS.md`、`D:\Dev-PCE\Source\AGENTS.md`、`PCE CODEX开发指令规范管理V1.2.md`、`PCE 已开发模块固化与变更保护规范 V1.0.md`。
- Registry：已读取`completed_module_registry.v1.json`。相关登记项为`sales-order-source-intake`与`engineering-calculation-six-continuations`，状态均为`DEVELOPED_NOT_CURRENTLY_VERIFIED`。
- Preflight：已执行`COMPLETED_MODULE_PROTECTION_PREFLIGHT_V1.md`要求的范围判定。
- Affected Frozen Modules：无命中Frozen Core/Frozen Shared Dependency。
- Freeze Contracts：本任务范围无适用的独立Freeze Contract。
- Unfreeze Authorization：不需要；结论为`SAFE TO MODIFY`，仅限本报告列明的P0 Gate、测试和Migration收口准备。
- Preserve-and-Extend：没有重建CRM、PDE、BOM、Routing、版本体系、权限或Workflow；没有处理任何P1关联补齐。

## 2. 固定执行基线与实际开发位置

- 固定Git HEAD：`6058ee03022ac1f4ef7a40905aef32f0dd2e294e`。
- 当前实际开发树：`D:\Dev-PCE\Source`。该树在任务开始前已存在大量用户修改/未跟踪成果；P0-01仅在实际开发树做最小服务扩展。
- P0-02独立worktree：`C:\Users\DAODA\.codex\worktrees\p0-chain-fix\Source`，从上述HEAD创建；Migration整理不在原脏工作树执行。
- 验收库：`D:\Dev-PCE\Acceptance\PDE-Operable-20260912\pde-operable-acceptance.sqlite3`，全程只读。
- 验收库副本：`D:\Dev-PCE\work\p0-migration-convergence-20260930\acceptance-baseline.sqlite3`。
- 原库及副本SHA-256均为`E05E453D32910FA635C1A2463921F797C7084B71C8A3103CDF8D2DB696E828CC`；任务结束复核未变化。

## 3. P0-01代码修改清单

### 3.1 统一CRM订单准入Gate

新增`backend/pde/crm_order_admission.py`，形成唯一服务端判定：

1. 企业、来源记录、来源订单号、来源版本必须分别唯一；缺失或多值时返回`CRM_ORDER_SOURCE_CONTEXT_AMBIGUOUS`，FAIL CLOSED。
2. 只接受与唯一来源上下文精确一致的已提交`CRM_ORDER_REVIEW`。
3. 最新相关评审的`conclusion=REJECT`先于Workflow/ApprovalDecision判断，返回`CRM_ORDER_REVIEW_EXPLICITLY_REJECTED`；`approved`不能覆盖它。
4. `RETURN_FOR_COMPLETION`同样阻断。
5. 新逐项流程`conclusion=""`时，以`CRMOrderReview` Workflow及最新ApprovalDecision为准；仅`workflow=approved`且`decision=approved`允许下游。
6. 不修改评审、审批、订单或PDE历史数据。

### 3.2 全部要求入口复用同一结果

- SalesOrder来源型创建：`backend/sales/services.py`的`create_order`。
- SalesOrder确认/推进：`confirm_order`及`perform_order_action`；`cancel`、`close`保留为纠偏/收尾动作，不被准入Gate阻止；幂等回放不重复写。
- PDE需求准备：`backend/pde/order_demand_preparation_service.py::_target_facts`。
- 产品设计写入口：通过`_target_facts`覆盖初始化、计划、增加设计项等；通过`_selected_items`覆盖设计内容、完成和删除类写入口。
- OrderEngineeringInstance创建：`backend/pde/formal_engineering_continuation_service.py::create_instance`；已有实例的纯幂等回读不改历史。
- 正式工程核算：`backend/pde/engineering_calculation_service.py`的`order_engineering`执行分支；`validation`计算不绑定正式订单，不扩展处理。

各服务只转换统一Gate的领域异常，不再自行解释CRM评审状态。

## 4. P0-01测试结果

### 4.1 最终定向验证

命令：

`manage.py test pde.tests_crm_order_admission_p0 pde.tests_order_demand_preparation.OrderDemandPreparationTests.test_explicit_crm_reject_blocks_without_changing_historical_objects pde.tests_order_demand_preparation.OrderDemandPreparationTests.test_prepare_persists_four_requirements_and_stops_before_design`

结果：**7 tests，全部通过**。

覆盖：

| 场景 | 结果 |
|---|---|
| REJECT + APPROVED | 硬阻断，通过 |
| REJECT + REJECTED | 硬阻断，通过 |
| conclusion空 + APPROVED | 允许，通过 |
| Pending审批 | 阻断，通过 |
| 来源不唯一 | 阻断，通过 |
| 已有SalesOrder/PDE对象 | 阻断前后计数一致，无删除、无修改，通过 |
| 正常PDE需求准备回归 | 允许并保持幂等，通过 |

Python语法编译检查通过；Django system check在测试运行中报告`0 silenced`且无错误。

### 4.2 必须保留的中间失败

首次扩大运行`pde.tests_crm_order_admission_p0`和整个`OrderDemandPreparationTests`共30项时出现7个错误：

- 5项为新测试用户fixture错误地使用`company`而非`company_id`；已修正，相关5项复跑通过。
- 1项为新增历史对象保护断言插入位置不正确；已修正，复跑通过。
- 1项为既有普通页面测试期望`readiness.data.strictFacts.approvalStatus`，当前实际API结果没有该键。该项不属于本次P0准入逻辑，依照禁止页面调整和禁止扩展范围未修改，仍列为未完成回归项。

## 5. P0-02 Migration收口结果

### 5.1 已恢复并纳管

独立worktree Git暂存区现仅纳管20个Migration文件：

- PDE当前分支：`0020_group3_transition_mode_override`至`0030_order_engineering_baseline`（11个）。
- PDE真实历史分支：`0021_order_engineered_product_structure`、`0022_structure_template_rule_binding_wave27`、`0023_detailed_material_requirement_selection_wave27a`（3个）；来源为已归档历史证据，原样复制。
- Sales：`0004_order_operating_system_v1`、`0005_sales_order_item_tax_snapshot`（2个）。
- System依赖：`0015_process_default_transition_mode`、`0016_process_display_order`、`0017_team_operation_capability`（3个）。
- 新增空操作merge：`pde/0031_merge_pde_legacy_and_order_chain.py`（1个），仅依赖两个真实叶节点，`operations=[]`。

未修改任何已经应用Migration的内容；未删除Migration记录；未使用fake；未重编号；未覆盖任一历史分支。

### 5.2 验收库Migration事实

只读副本中的`django_migrations`确认同时存在：

- `pde.0020_workcenter_engineering_closure -> 0021_order_engineered_product_structure -> 0022_structure_template_rule_binding_wave27 -> 0023_detailed_material_requirement_selection_wave27a`；
- `pde.0020_group3_transition_mode_override -> ... -> 0030_order_engineering_baseline`；
- `sales.0004`、`sales.0005`；
- `system.0015`、`0016`、`0017`。

这证明平行历史是真实已应用历史，不能删除、改号或伪造。

## 6. P0-02隔离验证

### 6.1 通过项

- 空库全量`migrate --noinput`：**PASS**；所有Migration成功应用，包含两条PDE分支和`0031` merge。
- 唯一PDE叶节点：**PASS**；仅`('pde', '0031_merge_pde_legacy_and_order_chain')`。
- SQLite完整性：重建库与验收副本均`PRAGMA integrity_check = ok`。
- FK检查：重建库与验收副本均`PRAGMA foreign_key_check = []`。
- 受检PDE/Sales/System Schema对象名称集合：双方均399个，名称集合完全一致。

### 6.2 阻断项

1. `makemigrations --check --dry-run`：**FAIL**。干净worktree的HEAD代码模型早于后续未纳管开发模型，而已恢复Migration已包含这些模型；Django因此建议生成大量删除Migration。没有生成或保存该错误Migration。本结果说明当前仓库尚未形成“代码模型 + Migration”同一可重建基线。
2. Schema diff：**FAIL**。399个PDE/Sales/System对象中仅`system_process`定义不同：
   - 验收副本：`display_order`有数据库默认`2147483647`及内联`CHECK(display_order > 0)`；
   - 空库重建：无该数据库默认，存在字段`CHECK(display_order >= 0)`及命名约束`system_process_display_order_positive CHECK(display_order > 0)`。
   - 对象名称、索引名称、FK检查均无其他差异。

根据授权指令，出现失败后已停止；没有把任何Migration应用到验收库，也没有通过fake或改写历史掩盖差异。

## 7. Git、数据库与Migration状态

### 7.1 Git状态

- 原实际开发树：保持原有脏状态；本任务涉及的P0-01文件中，2个原跟踪文件修改、6个当前开发成果/测试文件为未跟踪。没有提交、没有推送、没有改动其他用户成果。
- 独立Migration worktree：HEAD固定为`6058ee0...`；20个Migration文件均为Git暂存新增；无其他工作树改动。Python验证产生的已跟踪`__pycache__`噪声已恢复，仅剩授权Migration文件。

### 7.2 数据库状态

- 验收库：**未修改**，前后SHA-256一致。
- 业务数据库：**未执行Migration、未写业务数据**。
- 隔离验证库：新建`D:\Dev-PCE\work\p0-migration-convergence-20260930\empty-rebuild.sqlite3`，仅用于空库重建验证。
- 验收库副本：仅用于只读Migration记录及Schema指纹比较。

### 7.3 Migration状态

- 历史文件恢复/纳管：完成。
- 平行分支空操作merge：完成。
- 空库重建与唯一叶节点：通过。
- `makemigrations --check`：未通过。
- Schema diff：未通过（1项明确差异）。
- 进入验收库：禁止，未执行。

## 8. 状态矩阵

| 保护项 | 状态 |
|---|---|
| Code Change | **YES**：仅P0-01服务逻辑、接入点和测试 |
| Database Change | **NO（验收/业务库）**；仅创建隔离验证库及只读副本 |
| Migration Change | **YES（独立worktree，暂存未提交）**：恢复19个、增加1个空操作merge |
| Business Data Write | **NO** |
| Permission Change | **NO** |
| Workflow Change | **NO**；只读取既有Workflow/ApprovalDecision |
| Page Change | **NO** |

## 9. 未完成事项、风险与后续顺序

未完成事项：

1. 需要另行授权，把当前实际已开发模型代码与已收口Migration带到同一干净Git基线，再重新执行`makemigrations --check`。
2. 需要对`system_process.display_order`的验收Schema与迁移重建Schema差异作来源确认；不得在本任务中擅自修改已应用Migration或验收库。
3. 重新执行全部隔离Gate后，只有全部通过才能制定验收库迁移/对齐方案。
4. 普通页面既有测试的`strictFacts.approvalStatus`缺失需在独立任务确认；本任务禁止页面/API扩展，因此未处理。

风险：

- 当前虽然已有唯一Migration图叶节点，但代码模型基线尚未与迁移状态同库收敛，不能宣称唯一可重建发布基线完成。
- `system_process`单项Schema漂移若被忽略，会导致空库重建与验收环境约束/默认值语义不同。
- 原实际开发树大量成果未纳入Git；P0-01代码目前不能单独由固定HEAD重建，提交前必须由后续授权任务进行受控收口。

建议后续实施顺序：

1. 独立授权“当前实际模型代码Git收口”，不得混入P1关系或页面变化。
2. 在新的干净基线重跑：空库migrate → 唯一叶节点 → `makemigrations --check` → Schema/表/索引/约束/FK diff。
3. 对`system_process`差异形成单独决策：确认验收库是历史人工漂移还是缺失的正式Migration；禁止修改旧Migration。
4. 全部隔离验证通过后，另行申请验收库操作授权；本报告不授权该动作。

## 10. 明确停止点与最终Gate

停止点：P0-02隔离验证的`makemigrations --check`及Schema diff失败处。已停止在验收库之前。

**PCE CRM TO PDE P0 IMPLEMENTATION BLOCKED**

其中：**P0-01 IMPLEMENTATION COMPLETE；P0-02 CONVERGENCE PREPARED BUT VALIDATION BLOCKED。**
