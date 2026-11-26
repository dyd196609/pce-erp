# PCE订单评审正式关系补齐实施 FINAL / CONSOLIDATED报告

报告日期：2026-09-30  
实施基线：`ca4264dadf754f3efd511a2ee962e371fca0ad64`  
上游P0-02基础：`c78bca8eab5e4ea74572eb092f5cb8c8ca036c21`  
最终Gate：**PCE ORDER REVIEW FORMAL RELATION IMPLEMENTATION COMPLETE**

## 1. 结论

P1-REL订单评审正式关系补齐已经完成代码实施与隔离验证。

本轮新增：

```text
OrderCrossFunctionalReview
        |
        | OneToOne / PROTECT
        v
OrderReviewSalesOrderRelation ---- PROTECT ----> SalesOrder
        |
        | 1:N
        v
OrderReviewScopeItem ------------- PROTECT ----> SalesOrderItem
```

P0 Gate返回的`review_id`和`review_version`不再被订单创建入口丢弃。CRM来源订单在同一个事务中完成Gate、订单、订单行、正式订单关系和订单行范围；任一步失败会整笔回滚。

没有实施历史回填，没有修改历史评审、审批决定、订单、订单行或真实验收库。

## 2. 治理读取与保护

- 已确认实施HEAD精确为`ca4264dadf754f3efd511a2ee962e371fca0ad64`，开始时worktree clean。
- 已重新读取/复核已开发模块固化与变更保护规范、Completed Module Registry、保护Preflight、P1-REL诊断设计报告及P0-01 Gate依赖基线报告。
- 上位AGENTS与PCE CODEX开发指令规范V1.2的SHA与最近一次全文读取一致。
- Registry `currentFrozenVerifiedModuleIds`为空。
- Affected Frozen Modules：无。
- Freeze Contracts：无适用合同。
- Unfreeze Authorization：不需要。
- Preflight：`SAFE TO MODIFY`，仅限两个关系模型、一个新Schema Migration、订单创建事务和专项测试。
- Review Level：Level C。

## 3. 新增模型

### 3.1 OrderReviewSalesOrderRelation

位置：`backend/pde/models.py`。

字段：

- `company` → `system.Company`，`PROTECT`；
- `review` → `OrderCrossFunctionalReview`，`OneToOneField + PROTECT`；
- `sales_order` → `SalesOrder`，`ForeignKey + PROTECT`；
- `scope_mode`：`WHOLE_ORDER` / `SELECTED_ITEMS` / `UNRESOLVED`；
- `order_version_snapshot`；
- `source_content_hash_snapshot`；
- `resolution_basis`：`RUNTIME_GATE` / `APPROVED_HISTORICAL_MANIFEST`；
- `scope_reason`；
- `created_by` → `system.User`，`PROTECT`；
- `audit_hash`，唯一；
- `created_at`。

实现规则：

- 一个Review版本最多一个正式订单关系；
- 一个SalesOrder允许多个Review版本关系；
- `company_id == review.company_id == sales_order.company_id`；
- 只允许`CRM_ORDER_REVIEW`和`SUBMITTED`评审；
- 来源内容哈希及订单版本快照必须与正式对象一致；
- `RUNTIME_GATE`禁止`UNRESOLVED`；
- `UNRESOLVED`只允许`APPROVED_HISTORICAL_MANIFEST`；
- `SELECTED_ITEMS`必须有范围原因；
- 模型保存后禁止修改，实例删除被阻断。

### 3.2 OrderReviewScopeItem

字段：

- `relation` → `OrderReviewSalesOrderRelation`，`PROTECT`；
- `sales_order_item` → `SalesOrderItem`，`PROTECT`；
- `line_no_snapshot`；
- `external_line_no_snapshot`；
- `item_identity_hash`，64位SHA256；
- `created_at`。

实现规则：

- `(relation, sales_order_item)`唯一；
- 订单行必须属于relation对应SalesOrder；
- 行号和外部行号快照必须与正式订单行一致；
- 保存后禁止修改，实例删除被阻断；
- 没有把`OrderCrossFunctionalReviewItem`转换或重解释为订单行范围。

## 4. Migration清单

新增唯一Migration：

`backend/pde/migrations/0032_order_review_sales_order_relation.py`

依赖：

- `pde.0031_merge_pde_legacy_and_order_chain`；
- `sales.0005_sales_order_item_tax_snapshot`；
- `system.0018_normalize_process_display_order_schema`；
- 当前User模型。

Migration只包含：

- 两张新关系表；
- 6个目标外键；
- review唯一约束；
- relation + sales_order_item唯一约束；
- company + sales_order索引；
- scope、resolution basis、订单版本及行号检查约束。

Migration不包含：

- `RunPython`；
- 历史数据回填；
- 旧Migration修改；
- Migration删除或重编号；
- fake Migration；
- PDE Review、OEI、EngineeringCalculation、BOM、Routing或ProductVersion变更。

## 5. 服务调整

### 5.1 Gate结果持久化

`sales.services.create_order()`现在保存：

```text
admission = _require_crm_admission(...)
```

并直接使用本次Gate返回的：

- `admission.review_id`；
- `admission.review_version`。

关系创建不使用`source_order_no`、JSON或`EngineeringSourceRecord`重新猜配Review。

### 5.2 原子事务顺序

`create_order()`继续由既有`@transaction.atomic`统一保护：

1. P0 CRM Order Admission Gate；
2. SalesOrder；
3. SalesOrderItem；
4. OrderReviewSalesOrderRelation；
5. OrderReviewScopeItem；
6. 订单审计记录；
7. 同事务提交。

范围或关系校验失败时，已创建的订单和订单行一并回滚。

### 5.3 范围输入

对Gate识别出的CRM来源订单：

- `reviewScopeMode=WHOLE_ORDER`：为本次创建的全部订单行建立范围快照；
- `reviewScopeMode=SELECTED_ITEMS`：要求明确的`reviewScopeItemLineNos`列表及`reviewScopeReason`；
- `reviewScopeMode=UNRESOLVED`：在线流程硬阻断；
- 缺少或非法范围模式：硬阻断。

非CRM、无来源上下文订单保持既有创建流程，不伪造评审关系。

既有开发合同样本调用方已明确传入`WHOLE_ORDER`，未改变其其它业务规则。

### 5.4 审计快照

订单创建审计新增：

- `orderReviewRelationId`；
- `orderReviewId`；
- `orderReviewVersion`；
- `orderReviewScopeMode`。

relation和scope item分别保存稳定SHA256审计/身份哈希。

## 6. 测试结果

### 6.1 P1-REL专项矩阵

文件：`backend/pde/tests_order_review_sales_order_relation.py`

最终结果：**12 tests，全部通过**。

覆盖：

1. Gate返回review_id后成功建立正式关系；
2. REJECT不能创建订单或关系；
3. APPROVED创建`RUNTIME_GATE`关系；
4. 一个Review不能关联两个SalesOrder；
5. 一个SalesOrder允许多个Review版本；
6. WHOLE_ORDER覆盖全部当前订单行；
7. SELECTED_ITEMS只覆盖明确订单行；
8. 其它订单的SalesOrderItem被阻断；
9. company/review/order企业范围不一致被阻断；
10. 重复scope relation被阻断；
11. 新流程失败不修改既有历史订单；
12. 在线UNRESOLVED原子阻断。

### 6.2 联合回归

执行P0原矩阵、P1-REL专项矩阵及两条既有订单创建路径。

结果：**20 tests，全部通过**。

联合回归后只新增企业范围专项测试，未修改业务代码；最终P1专项12项再次全部通过。

### 6.3 非阻断环境警告

Django持续报告独立worktree中`backend/static`目录不存在的`staticfiles.W004`。页面/静态目录不属于本轮范围；没有通过页面或设置修改掩盖该警告。测试与Migration验证均成功。

## 7. Migration验证

### 7.1 模型一致性

`manage.py makemigrations --check --dry-run`：

- 退出码：0；
- 结果：`No changes detected`；
- 未使用`--skip-checks`。

### 7.2 Migration图

- 冲突：`{}`；
- PDE唯一叶节点：`0032_order_review_sales_order_relation`；
- Sales唯一叶节点：`0005_sales_order_item_tax_snapshot`；
- System唯一叶节点：`0018_normalize_process_display_order_schema`。

### 7.3 空库全量重建

在工作区内创建明确临时SQLite空库，执行全量`manage.py migrate --noinput`：

- 全量Migration成功；
- `pde.0032`成功应用；
- Schema读取确认两张表、列、FK、唯一索引、普通索引和检查约束存在；
- `django_migrations`中`pde.0032`记录数为1；
- 临时库验证后已删除。

首次Schema读取脚本因Shell引号转义失败，但Migration已成功；随后直接读取同一个已重建临时库完成全部Schema验证，没有重跑或伪造Migration结果。

## 8. Git状态

- 当前分支：`codex/p0-01-gate-baseline`；
- 当前HEAD：`ca4264dadf754f3efd511a2ee962e371fca0ad64`；
- 本轮尚未创建新commit；
- 未push；
- 变更文件正好5个：
  - `backend/pde/models.py`；
  - `backend/sales/services.py`；
  - `backend/sales/development_contract_sample.py`；
  - `backend/pde/migrations/0032_order_review_sales_order_relation.py`；
  - `backend/pde/tests_order_review_sales_order_relation.py`。
- `git diff --check`通过；
- 除新`0032`外无Migration文件变化；
- 未出现范围外实现符号。

## 9. 数据库与历史数据保护

### 真实验收库

- 未执行Migration；
- 未连接进行业务写入；
- 执行前后只读SHA保持：

`2E827C8B1BA6BFE384C6946A8A478363D6490AFA58CE453070F29A0FB7AA82F2`

### 历史数据

- 无数据Migration；
- 无自动历史回填；
- 无`source_order_no`批量匹配；
- 无JSON自动写关系；
- 无Review、ApprovalDecision、SalesOrder或SalesOrderItem历史修改；
- 现有历史REJECT记录保持原状；
- 历史关系登记仍需独立授权。

## 10. 变更状态

| 项目 | 状态 |
|---|---|
| Code Change | YES |
| Migration Change | YES：仅新增Schema Migration 0032 |
| Database Change | 仅隔离内存库与临时空库；均已销毁/删除 |
| Real Acceptance Database Change | NO |
| Business Data Write | NO |
| Historical Backfill | NO |
| Permission Change | NO |
| Workflow Change | NO |
| Page Change | NO |
| Other P1 Work | NOT STARTED |

## 11. 是否达到真实验收库执行条件

**技术验证结论：YES。**

依据：专项测试、P0联合回归、`makemigrations --check`、唯一Migration叶节点、空库全量重建及Schema对象检查全部通过。

但当前实现尚未提交，且本轮明确禁止真实验收库执行Migration。因此：

- 本报告不构成真实验收库执行授权；
- 不得自动对真实验收库执行`pde.0032`；
- 真实验收库执行必须在代码评审、Git基线固定后取得新的明确授权。

## 12. 未完成事项与停止点

- 尚未创建实施commit；
- 尚未push；
- 尚未执行真实验收库Migration；
- 尚未进行任何历史关系登记；
- PDE正式关系、OEI、EngineeringCalculation FK、BOM、Routing、ProductVersion及其它P1问题均未启动。

后续唯一动作：

**对当前5文件diff进行代码评审，并在独立授权下形成唯一实施commit。**

本轮在此停止。

## 13. 最终Gate

**PCE ORDER REVIEW FORMAL RELATION IMPLEMENTATION COMPLETE**
