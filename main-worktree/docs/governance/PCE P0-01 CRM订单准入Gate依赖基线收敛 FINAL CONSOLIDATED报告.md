# PCE P0-01 CRM订单准入Gate依赖基线收敛 FINAL / CONSOLIDATED报告

报告日期：2026-09-30  
最终Gate：**PASS / COMPLETE**  
基础commit：`c78bca8eab5e4ea74572eb092f5cb8c8ca036c21`  
新commit：`ca4264dadf754f3efd511a2ee962e371fca0ad64`

## 1. 任务结论

P0-02 Migration收口、P0-01 CRM订单准入Gate及其运行/测试所需最小既有依赖，已经在独立worktree形成唯一可审查Git基线。

新commit直接建立在P0-02 commit之上；未squash、改写或覆盖P0-02历史。P0测试矩阵、`makemigrations --check`、P0入口导入、Migration图与Git diff审查全部通过。

本轮未进入P1订单评审正式关系，未新增或修改Migration、模型、业务数据、页面、权限或Workflow。

## 2. 治理读取与保护结论

- 已复核项目上位AGENTS、当前AGENTS、PCE CODEX开发指令规范V1.2、已开发模块固化与变更保护规范、Completed Module Registry、保护Preflight及上一轮阻断报告。
- 上述文件SHA与本线程最近一次全文读取一致。
- Registry当前冻结验证模块为空。
- Affected Frozen Modules：无。
- Freeze Contracts：无适用合同。
- Unfreeze Authorization：不需要。
- Preflight：`SAFE TO MODIFY`，仅限P0-01运行与测试依赖闭包。
- Review Level：Level C。

## 3. Git基线

- 独立worktree：`C:\Users\DAODA\.codex\worktrees\p0-chain-fix\Source`。
- 分支：`codex/p0-01-gate-baseline`。
- 父commit：`c78bca8eab5e4ea74572eb092f5cb8c8ca036c21`。
- 新commit：`ca4264dadf754f3efd511a2ee962e371fca0ad64`。
- commit tree：`ec96e93f8814be87f117d84dc3bd2dfc709062fa`。
- commit文件数：18。
- commit后worktree：clean。
- Push：未执行。

## 4. 依赖闭包

### 4.1 P0入口与核心文件

1. `backend/pde/crm_order_admission.py`
2. `backend/pde/order_demand_preparation_service.py`
3. `backend/pde/product_design_service.py`
4. `backend/pde/formal_engineering_continuation_service.py`
5. `backend/pde/engineering_calculation_service.py`
6. `backend/sales/services.py`
7. `backend/pde/tests_crm_order_admission_p0.py`
8. `backend/pde/tests_order_demand_preparation.py`

### 4.2 直接依赖

- `engineering_calculation_service.py` → `engineering_work_context.py`。
- `product_design_service.py` → `engineering_condition_options.py`。
- `formal_engineering_continuation_service.py` → `calculation_batch_reuse.py`、`formal_calculation_readback.py`。
- `tests_order_demand_preparation.py` → `product_design_import_service.py`、`product_design_export_service.py`、`sales/development_contract_sample.py`。

### 4.3 间接导入依赖

- `engineering_work_context.py` → `engineering_condition_options.py`。
- `calculation_batch_reuse.py` → `engineering_work_context.py`、`engineering_condition_options.py`、`semi_finished_configuration_preview.py`、`semi_finished_configuration_validation.py`、`room_door_edge_preview.py`。
- 产品设计导入服务复用`engineering_condition_options.py`、`order_demand_preparation_service.py`和`product_design_service.py`。

### 4.4 依赖判定方式

依赖通过以下证据交叉确认：

1. P0入口文件的本地Python import扫描；
2. c78基线与当前已验证成果的文件存在性比对；
3. Django真实系统检查加载；
4. 六个P0入口模块显式import冒烟；
5. P0测试矩阵的真实运行。

未创建假模块，未删除导入，未使用`--skip-checks`。

## 5. commit纳管文件

### P0 Gate、入口及测试

- `backend/pde/crm_order_admission.py`
- `backend/pde/engineering_calculation_service.py`
- `backend/pde/formal_engineering_continuation_service.py`
- `backend/pde/order_demand_preparation_service.py`
- `backend/pde/product_design_service.py`
- `backend/pde/tests_crm_order_admission_p0.py`
- `backend/pde/tests_order_demand_preparation.py`
- `backend/sales/services.py`

### 必要既有依赖

- `backend/pde/calculation_batch_reuse.py`
- `backend/pde/engineering_condition_options.py`
- `backend/pde/engineering_work_context.py`
- `backend/pde/formal_calculation_readback.py`
- `backend/pde/product_design_export_service.py`
- `backend/pde/product_design_import_service.py`
- `backend/pde/room_door_edge_preview.py`
- `backend/pde/semi_finished_configuration_preview.py`
- `backend/pde/semi_finished_configuration_validation.py`
- `backend/sales/development_contract_sample.py`

其中`formal_engineering_continuation_service.py`仅移除一个文件末尾多余空行，以使`git diff --check`通过；无业务逻辑变化。

## 6. 明确排除文件与能力

以下文件或能力未纳管：

- `backend/pde/product_version_management_service.py`：仅为非P0延迟函数路径，且ProductVersion在本轮禁止范围内。
- `backend/pde/acceptance_isolation.py`：仅为批量核算非P0延迟执行路径。
- `backend/pde/semi_finished_configuration_source.json`：P0 Gate及测试矩阵不读取。
- `docs/evidence/room_door_edge_20260909/`及`docs/evidence/semi_finished_role_layer_20260909/`：P0 Gate及测试矩阵不读取。
- 所有P1关系模型与实现。
- 所有新增Migration、model、view、URL、页面及权限文件。
- BOM、Routing、ProductVersion的新开发或变更。
- 数据库文件、业务数据、验收库副本及运行生成物。

纳管的既有服务文件中可能保留原有非P0函数或文字引用；本轮没有设计、扩展或验证这些范围外能力，也没有将其作为本轮交付成果。

## 7. 验证结果

### 7.1 P0-01测试矩阵

执行：

```text
manage.py test pde.tests_crm_order_admission_p0 pde.tests_order_demand_preparation.OrderDemandPreparationTests.test_explicit_crm_reject_blocks_without_changing_historical_objects pde.tests_order_demand_preparation.OrderDemandPreparationTests.test_prepare_persists_four_requirements_and_stops_before_design
```

结果：**7 tests，全部通过；退出码0**。

覆盖：

- REJECT + APPROVED硬阻断；
- REJECT + REJECTED硬阻断；
- conclusion为空 + APPROVED允许；
- Pending审批阻断；
- 来源不唯一阻断；
- 历史订单/PDE对象不删除、不修改；
- 正常需求准备既有路径保持。

测试数据库为Django隔离内存库，完成后已销毁。

### 7.2 makemigrations

命令：`manage.py makemigrations --check --dry-run`。  
结果：**PASS，No changes detected，退出码0**。  
未使用`--skip-checks`。

### 7.3 P0入口import

显式导入以下模块：

- `pde.crm_order_admission`
- `pde.order_demand_preparation_service`
- `pde.product_design_service`
- `pde.formal_engineering_continuation_service`
- `pde.engineering_calculation_service`
- `sales.services`

结果：**PASS**。

### 7.4 Migration图

- 冲突：`{}`。
- PDE唯一叶节点：`0031_merge_pde_legacy_and_order_chain`。
- Sales唯一叶节点：`0005_sales_order_item_tax_snapshot`。
- System唯一叶节点：`0018_normalize_process_display_order_schema`。

### 7.5 Git diff

- `git diff --cached --check`：PASS。
- commit文件数：18。
- P1符号扫描：无`OrderReviewSalesOrderRelation`、无`OrderReviewScopeItem`。
- 禁止路径扫描：无Migration、model、view、URL、前端或权限文件。
- commit统计：10306 insertions、61 deletions。

### 7.6 非阻断警告

Django报告worktree内`backend/static`目录不存在的`staticfiles.W004`警告。该目录/页面不属于本轮范围；警告未影响测试、系统检查结论或Migration检查，未通过页面或设置修改消除。

## 8. 数据保护状态

| 项目 | 状态 |
|---|---|
| Code Change | YES，仅P0 Gate、入口、测试及必要既有依赖 |
| Migration Change | NO |
| Database Change | NO |
| Business Data Write | NO |
| Permission Change | NO |
| Workflow Change | NO |
| Page Change | NO |
| P1-REL | NOT STARTED |
| Push | NO |

观察到的`D:\Dev-PCE\Source\backend\db.sqlite3` SHA256为：

`0840A70E7D2F3965FCFC038977841D9BABC0354101B5C7CCE14F89552FC39F67`

本轮未对该数据库执行写命令或Migration。

## 9. Git状态

- Branch：`codex/p0-01-gate-baseline`。
- HEAD：`ca4264dadf754f3efd511a2ee962e371fca0ad64`。
- Parent：`c78bca8eab5e4ea74572eb092f5cb8c8ca036c21`。
- Worktree：clean。
- Staged changes：无。
- Untracked changes：无。
- Push：未执行。

## 10. 后续唯一动作

**对commit `ca4264dadf754f3efd511a2ee962e371fca0ad64`进行代码评审与合入授权；不得自动进入P1-REL。**

## 11. 最终Gate

**PCE P0-01 CRM ORDER ADMISSION GATE DEPENDENCY BASELINE CONVERGENCE COMPLETE**
