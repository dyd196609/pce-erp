# PCE P0-01 CRM订单准入Gate基线收敛 FINAL / CONSOLIDATED报告

报告日期：2026-09-30  
执行结论：**BLOCKED — 未创建commit**  
停止点：提交前强制验证未通过；未进入P1-REL。

## 1. 任务与边界

本轮目标是在P0-02收口commit：

`c78bca8eab5e4ea74572eb092f5cb8c8ca036c21`

之上，原样纳管已经验证的P0-01 CRM订单准入Gate及其测试，形成可审查、可重建的新代码基线。

本轮严格排除：P1订单评审正式关系、`OrderReviewSalesOrderRelation`、`OrderReviewScopeItem`、BOM、Routing、ProductVersion、页面、权限及Workflow扩展。

## 2. COMPLETED MODULE GOVERNANCE READING RECEIPT

- `D:\Dev-PCE\AGENTS.md`：已全文读取；SHA256 `0CD48571FDCBF666074E297747530BD5FB2E5BAA2E5B2B3FF4293B013CFA5954`。
- `D:\Dev-PCE\Source\AGENTS.md`：已全文读取；SHA256 `271116362F53C15A0E63AF3214FD1CEEB2F229586CD2E57B37BB0BA05DD45A01`。
- `PCE CODEX开发指令规范管理V1.2.md`：已全文读取；SHA256 `FB21BCB17375AE529A599FC92488548BD21E8027509DD846FC2B32F6C9760D8C`。
- `PCE 已开发模块固化与变更保护规范 V1.0.md`：已全文读取；SHA256 `695F812E33DF0C3DF0C7EFD7524D55A4CCE6F7CA489DA4C0D15462C714ABC39C`。
- `completed_module_registry.v1.json`：已全文读取；SHA256 `DF7540621B621C13BE5E2B7A901B39B907B1FDAC3EB1DE402532FAA64221521F`。
- `COMPLETED_MODULE_PROTECTION_PREFLIGHT_V1.md`：已全文读取；SHA256 `D2B2487B8126EB435599CF35DDB3A0AB98E96D2A0F6241A4AE1950859EE6D4BD`。
- P0实施报告：已读取；SHA256 `85805229F9CD351C779CD04B2A3AEE15649A8E25272732C3A452ECDFBA0C3AAD`。
- P0-02合入准备报告：已读取；SHA256 `92D9BE0E88D3FFA8A95B37D7830E96B57EFB4499E4E26633B0044259E0229A4A`。
- Preservation Standard：适用并已执行。
- Registry状态：相关模块不在`currentFrozenVerifiedModuleIds`。
- Affected Frozen Modules：无。
- Freeze Contracts：无适用合同。
- Unfreeze Authorization：不需要。
- Preflight结论：`SAFE TO MODIFY`，仅限本报告所列P0-01文件。
- Review Level：Level C。

## 3. 独立worktree与基础commit

- 独立worktree：`C:\Users\DAODA\.codex\worktrees\p0-chain-fix\Source`。
- 初始状态：干净、detached HEAD。
- 基础commit：`c78bca8eab5e4ea74572eb092f5cb8c8ca036c21`。
- 本轮分支：`codex/p0-01-gate-baseline`。
- 分支创建后仅迁入冻结的P0-01文件；未合并原脏工作树的其他文件。

## 4. 原样迁入文件与SHA256

共8个文件；源文件与worktree副本逐一验证为相同SHA256：

1. `backend/pde/crm_order_admission.py`  
   `164D21C07D315E90B6BD6280BCFB5DF5946FA846F81B13EE8014CBEDFCA354E8`
2. `backend/pde/tests_crm_order_admission_p0.py`  
   `35F430507492556734B04254D4A880D2D356384B34E2F303B2E675C3D8E52AE9`
3. `backend/pde/order_demand_preparation_service.py`  
   `52304AE71B1D505C685CCB68C1791B1338F9534588E64CA8B393FDE0AAD0A040`
4. `backend/pde/product_design_service.py`  
   `258FE852821375A0D14E4E2FC30B35D0FF48E58C98586FC7E457F9700B6C70A3`
5. `backend/pde/formal_engineering_continuation_service.py`  
   `B40594EB0014639B1BF283A259B599ACF95E31FC66563313190A87B28369F3DE`
6. `backend/pde/tests_order_demand_preparation.py`  
   `142D0FDF90DC240920BDD9677A0E5A43575A2EACFE195C262CCD0B9B55E9DBD4`
7. `backend/pde/engineering_calculation_service.py`  
   `A9DEF9BFC9B6EF94764888E3484B31B9FC63E30E9AF542F32395FA9EE7D29A28`
8. `backend/sales/services.py`  
   `7C5432A15A26DB34822E0DBF5C80B5082AA66E30C5A276001781387FF536BDF3`

P1排除检查：上述文件未出现`OrderReviewSalesOrderRelation`或`OrderReviewScopeItem`。

## 5. 强制验证结果

### 5.1 P0-01测试矩阵

执行命令：

```text
manage.py test pde.tests_crm_order_admission_p0 pde.tests_order_demand_preparation.OrderDemandPreparationTests.test_explicit_crm_reject_blocks_without_changing_historical_objects pde.tests_order_demand_preparation.OrderDemandPreparationTests.test_prepare_persists_four_requirements_and_stops_before_design --verbosity 2
```

结果：**FAIL，退出码1**。

事实：

- Django发现6项测试。
- 隔离测试数据库为`file:memorydb_default?mode=memory&cache=shared`。
- 全部Migration在该内存库应用完成，包括PDE 0031与System 0018。
- 系统检查加载PDE URL及服务时失败，测试方法尚未开始执行。
- 直接阻断：`ModuleNotFoundError: No module named 'pde.engineering_work_context'`。
- 内存测试数据库随后已销毁。

因此不能把本轮结果表述为“P0测试通过”。

### 5.2 makemigrations检查

执行命令：

```text
manage.py makemigrations --check --dry-run
```

结果：**FAIL，退出码1**。

失败原因同上：Django系统检查加载`engineering_calculation_service.py`时，c78基线缺少`pde.engineering_work_context`。

未使用`--skip-checks`伪造通过；未生成Migration。

### 5.3 Migration图

结果：**PASS**。

- 冲突：`{}`。
- PDE唯一叶节点：`0031_merge_pde_legacy_and_order_chain`。
- Sales唯一叶节点：`0005_sales_order_item_tax_snapshot`。
- System唯一叶节点：`0018_normalize_process_display_order_schema`。

### 5.4 Git diff检查

- worktree仅包含冻结的8个P0-01文件。
- 暂存区为空。
- 未创建commit。
- 未push。
- 未发现P1正式关系模型符号。

## 6. 最终原因

已验证的P0-01成果来自原实际开发脏工作树。该成果的入口文件同时依赖尚未纳入c78基线的既有PDE服务文件，包括但不限于：

- `backend/pde/engineering_work_context.py`
- `backend/pde/engineering_condition_options.py`
- `backend/pde/calculation_batch_reuse.py`
- `backend/pde/formal_calculation_readback.py`
- `backend/pde/product_design_import_service.py`
- `backend/pde/product_design_export_service.py`

这些依赖不是本轮冻结的P0-01文件，并包含产品设计、工程核算、导入导出等更广的已开发成果。直接一并纳管会扩大授权范围；删除依赖、加入假模块、跳过检查或从大文件中重新提炼Gate则不再是“原样迁入”，并可能重新设计P0-01。

因此，在当前授权边界内，无法同时满足：

1. 原样迁入；
2. 仅纳管P0-01；
3. 可审查、可重建；
4. P0测试矩阵通过；
5. `makemigrations --check`通过。

## 7. Git与数据库状态

### Git

- 基础commit：`c78bca8eab5e4ea74572eb092f5cb8c8ca036c21`。
- 新commit ID：**NOT CREATED**。
- 当前分支：`codex/p0-01-gate-baseline`。
- 当前状态：8个冻结文件未暂存；其余无本轮改动。
- P0-02 commit未被改写、squash或覆盖。

### 数据库

- 真实验收库Migration：未执行。
- 真实业务数据写入：无。
- Django测试仅使用内存测试库，并已销毁。
- 观察到的`D:\Dev-PCE\Source\backend\db.sqlite3` SHA256：`0840A70E7D2F3965FCFC038977841D9BABC0354101B5C7CCE14F89552FC39F67`。
- 本轮未对该文件执行写命令。

## 8. 保护状态

| 项目 | 状态 |
|---|---|
| Code Change | 独立worktree中仅原样复制8个文件，未提交 |
| Database Change | NO |
| Migration Change | NO |
| Business Data Write | NO |
| Permission Change | NO |
| Workflow Change | NO |
| Page Change | NO |
| P1-REL | NOT STARTED |

## 9. 未完成事项与风险

- 新commit未创建。
- P0测试矩阵未进入测试方法执行阶段。
- `makemigrations --check`未通过。
- 若在未收敛依赖的情况下强行提交，基线不能通过Django系统检查，不属于可重建基线。
- 若未经授权纳管全部传递依赖，将混入P0之外的PDE成果并破坏本轮范围边界。

## 10. 后续唯一动作

**另行明确授权“P0-01入口所依赖的既有PDE服务基线收敛”，给出允许纳管的依赖文件边界；随后在当前独立worktree重新执行测试矩阵、`makemigrations --check`、Migration图与diff审查，全部通过后再创建唯一commit。**

在获得该授权前，不创建commit，不进入P1-REL。

## 11. 最终Gate

**PCE P0-01 CRM ORDER ADMISSION GATE BASELINE CONVERGENCE BLOCKED**

停止原因：提交前测试与`makemigrations --check`均被c78基线缺失的范围外PDE服务依赖阻断。
