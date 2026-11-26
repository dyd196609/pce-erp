# PCE订单→PDE→BOM→工艺路线P0-02一次性收口 FINAL / CONSOLIDATED报告

## 1. 最终结论

**最终 Gate：PCE P0-02 MIGRATION CONVERGENCE COMPLETE**

本轮已在独立干净 worktree 中形成并验证唯一基线：

> 当前代码模型 + 完整 Migration 历史 + 可从空库重建的 Schema = 一致

PDE、Sales、System 范围内的模型状态与 Migration 状态一致；PDE 平行历史分支保留，并以空操作 merge Migration 合流；`system_process.display_order` 的历史物理结构差异通过新增后继规范化 Migration 收敛。最终空库重建、唯一叶节点、`makemigrations --check`、表、索引、约束、外键及 Schema diff 全部通过。

本轮未连接真实验收库执行 Migration，未修改真实验收库，未写入业务数据。

## 2. 执行边界与治理回执

### 2.1 COMPLETED MODULE GOVERNANCE READING RECEIPT

- Preservation Standard：已全文读取 `PCE 已开发模块固化与变更保护规范 V1.0.md`。
- Registry：已完整读取 `completed_module_registry.v1.json`。
- Governance：已全文读取根目录与 Source 的 `AGENTS.md`、`PCE CODEX开发指令规范管理V1.2.md`、`COMPLETED_MODULE_PROTECTION_PREFLIGHT_V1.md`。
- Prior report：已读取《PCE订单→PDE→BOM→工艺路线P0实施 FINAL CONSOLIDATED报告》。
- Affected Frozen Modules：未命中 `FROZEN_VERIFIED` 模块；相关登记项 `sales-order-source-intake`、`engineering-calculation-six-continuations` 为 `DEVELOPED_NOT_CURRENTLY_VERIFIED`。
- Freeze Contracts：无适用于本次 Migration 历史收口的 Frozen Core / Frozen Shared Dependency 合同。
- Unfreeze Authorization：不需要。
- Preflight：`SAFE TO MODIFY`，仅限本指令授权的 Migration/模型基线收口。

### 2.2 Effective Instruction Set

- 当前有效任务：`P0-02-CLOSEOUT-20260930`。
- Review Level：C。
- Preserve-and-Extend：执行。
- 明确排除的 P1 关系、BOM、Routing、产品版本组合、页面、权限及 Workflow 扩展：均未处理。

## 3. 独立执行环境与固定基线

- 独立 worktree：`C:\Users\DAODA\.codex\worktrees\p0-chain-fix\Source`
- Git HEAD：`6058ee03022ac1f4ef7a40905aef32f0dd2e294e`
- Git 状态：detached HEAD；本轮成果均已暂存，未 commit、未 push。
- 原工作树：`D:\Dev-PCE\Source`，执行前后保持原有脏工作树；未在该工作树整理 Migration。
- 原工作树取证时共有 1,532 个状态项，本轮未清理、覆盖或回退这些既有成果。
- 纳管后的 PDE/Sales/System Migration 文件数：61。
- Migration 清单指纹：`4B0CF02369E51E20070D95E4E39F062B925E3C84531F66F0295E5A9753182D40`。

### 3.1 数据库固定

- 真实验收库：`D:\Dev-PCE\Acceptance\PDE-Operable-20260912\pde-operable-acceptance.sqlite3`
- 只读基线副本：`D:\Dev-PCE\work\p0-migration-convergence-20260930\acceptance-baseline.sqlite3`
- 两者 SHA256 均为：`E05E453D32910FA635C1A2463921F797C7084B71C8A3103CDF8D2DB696E828CC`
- 最终复核时真实验收库 SHA256 未变化。

## 4. P0-02 原阻断原因

原阻断由三部分组成：

1. Git HEAD 未纳管验收库已经应用的 PDE、Sales、System Migration 文件，仓库无法独立表达真实历史。
2. PDE 存在两条真实、均已应用的平行历史分支，但缺少统一叶节点。
3. 当前实际开发模型高于干净 Git HEAD；直接对旧 HEAD 执行 `makemigrations --check` 会产生大量新增/删除误判，不能作为真实代码基线。

此外，`system_process.display_order` 在验收库与按当前运行时重建库之间存在物理 DDL 差异，导致 Schema 指纹不一致。

## 5. Migration 最终状态

### 5.1 恢复并纳管的真实历史

- PDE 当前订单工程分支：`0020_group3_transition_mode_override` 至 `0030_order_engineering_baseline`。
- PDE 历史工程建模分支：`0020_workcenter_engineering_closure` 至 `0023_detailed_material_requirement_selection_wave27a`。
- Sales：`0004_order_operating_system_v1`、`0005_sales_order_item_tax_snapshot`。
- System：`0015_process_default_transition_mode`、`0016_process_display_order`、`0017_team_operation_capability`。

已应用历史 Migration 的内容未修改、未删除、未重编号，未使用 fake。

### 5.2 新增收敛 Migration

1. `pde.0031_merge_pde_legacy_and_order_chain`
   - 空操作 merge Migration；
   - 保留两条真实历史分支；
   - 不修改业务 Schema。

2. `system.0018_normalize_process_display_order_schema`
   - 仅在 SQLite 执行物理结构规范化；
   - Django state 不变化；
   - 目标 DDL 已存在时立即 no-op；
   - 非 SQLite 后端 no-op；
   - 复制全部既有行并执行 FK 检查；
   - 不修改旧 `0016`。

`0016_process_display_order.py` SHA256：`2416CCF5ACC5EE17FA79C8D77810AEC99CD586D1AB9E99A7D2B91C6159DEA893`。

`0018_normalize_process_display_order_schema.py` SHA256：`C4FA6CC08DA113A1E840B90FE62AD31B63D664EFE64A105A6DB469B782DCA846`。

### 5.3 唯一叶节点

- PDE：`0031_merge_pde_legacy_and_order_chain`
- Sales：`0005_sales_order_item_tax_snapshot`
- System：`0018_normalize_process_display_order_schema`
- Migration graph conflicts：`{}`
- Unapplied migrations（最终空库）：`[]`

## 6. 代码模型基线状态

独立 worktree 中已将当前实际开发的以下模型文件纳入基线：

- `backend/pde/models.py`
- `backend/sales/models.py`
- `backend/system/models.py`

同时从真实已应用的 PDE 历史分支恢复模型 state 所要求的既有模型、字段、Meta 与约束，包括 `ProductionLine`、`Station`、WorkCenter 能力关系、模板结构与材料选择相关模型，以及 `WorkCenter.production_line`、`ProductConfiguration.company/definition_mode` 等既有状态。

这些恢复用于表达已应用 Migration 的真实最终 state；没有新增本指令禁止的 Review→SalesOrder FK、ReviewScopeItem、CRM/PDE predecessor、EngineeringCalculation FK、BOM 生成、Routing 冻结或版本组合关系。

完整执行：

```text
python manage.py makemigrations --check --dry-run
No changes detected
Exit code: 0
```

非阻断警告仅为 clean worktree 未包含 `backend/static` 目录，以及既有 settings 注释中的 Python escape SyntaxWarning；均不影响 Migration/Schema 结论。

## 7. system_process.display_order 差异最终结论

### 7.1 验收库结构

```sql
display_order integer unsigned NOT NULL DEFAULT 2147483647 CHECK(display_order > 0)
```

### 7.2 原空库重建结构

```sql
"display_order" integer unsigned NOT NULL CHECK ("display_order" >= 0)
CONSTRAINT "system_process_display_order_positive" CHECK ("display_order" > 0)
```

### 7.3 原因分类

- 缺失 Migration：否；`0016` 的历史文件已找到且已应用。
- 旧 Migration 内容被修改：否；当前 `0016` 与 2026-09-09 留档 SHA256 一致。
- 已确认人工改库：无证据，不作此结论。
- 最终分类：历史 SQLite Migration 执行/运行时路径差异。验收库保留列级 default 与 inline check；当前 Django/SQLite 重建路径将 state 物化为另一种等价业务约束形式。

### 7.4 收敛方式

新增 `system.0018` 将空库物理结构规范化到验收库既有结构。这样既不修改旧 Migration，也不要求先改验收库；对当前验收库执行时命中目标结构并 no-op，仅记录 Migration 已应用。

## 8. 空库重建结果

最终证据库：

`D:\Dev-PCE\work\p0-migration-convergence-20260930\empty-rebuild-v4.sqlite3`

SHA256：`A1BCA29D2522EF1A44D852073AB7CCD79662A4A3358C7EC48213B54EBCA65190`

执行结果：

- 单进程、全新不存在文件启动；
- 全量 `migrate --noinput`：PASS，明确退出码 0；
- 所有 Migration 均应用；
- `pde.0031`：OK；
- `system.0018`：OK；
- `makemigrations --check --dry-run`：PASS；
- 唯一叶节点：PASS；
- 冲突检查：PASS；
- 未应用节点检查：PASS。

过程说明：v2 验证时曾因验证器过早启动第二个确认进程，与仍运行的首进程并发触碰同一隔离库，第二进程出现瞬时 `table already exists`；取证确认首进程已完整成功，这不是 Migration 分支冲突。v2、v3 均未作为最终证据。随后改用全新 v4、严格单进程并等待明确退出码，完成最终验证。

## 9. Schema、表、索引、约束与 FK 验证

比较范围：全部 `pde_*`、`sales_*`、`system_*` 表及其索引、触发器、列、默认值、约束和外键。

- 验收库对象数：399
- 空库重建对象数：399
- Schema object diff：0
- Table fact diff：0
- 验收库对象指纹：`8BA37B47F3EDA4AB81F70C1ABEE7F8A3F8A629531243CD9452E8871BA508FC7C`
- 重建库对象指纹：`8BA37B47F3EDA4AB81F70C1ABEE7F8A3F8A629531243CD9452E8871BA508FC7C`
- 验收库列/FK/索引事实指纹：`3229C9DECA41EFD813924A004B071EF7185B8F96C8DECAA7ECAB4402AF164717`
- 重建库列/FK/索引事实指纹：`3229C9DECA41EFD813924A004B071EF7185B8F96C8DECAA7ECAB4402AF164717`
- 验收库副本 `integrity_check`：`ok`
- 空库重建 `integrity_check`：`ok`
- 两库 `foreign_key_check`：均为 0 条违规

结论：表结构、索引、约束与 FK 检查全部通过。

## 10. 验收库副本演练

演练文件：

`D:\Dev-PCE\work\p0-migration-convergence-20260930\acceptance-rehearsal-v1.sqlite3`

仅应用：

- `pde.0031_merge_pde_legacy_and_order_chain`
- `system.0018_normalize_process_display_order_schema`

结果：二者均 OK；`system.0018` 命中既有目标 DDL，不重建 `system_process`。

业务数据指纹（排除 `django_migrations`）：

- 表数：299
- 行数：15,602
- 演练前 SHA256：`3160DACF755F779F47A0B08FAF3958A5D26E97D0973562B8CAAC22775B6740AC`
- 演练后 SHA256：`3160DACF755F779F47A0B08FAF3958A5D26E97D0973562B8CAAC22775B6740AC`

Schema 演练前后对象指纹和事实指纹完全一致，diff 为 0。

## 11. 变更状态

| 项目 | 状态 | 说明 |
|---|---|---|
| Code Change | YES | 独立 worktree 中同步 PDE/Sales/System 当前模型及历史 state |
| Database Change | NO | 真实验收库未连接执行、未修改 |
| Migration Change | YES | 恢复 19 个真实历史文件，纳管空 merge，新增 `system.0018` |
| Isolated Validation DB Change | YES | 仅 v2/v3/v4 与 rehearsal 隔离文件 |
| Business Data Write | NO | 真实业务库无写入；rehearsal 业务数据指纹不变 |
| Permission Change | NO | 未修改 |
| Workflow Change | NO | 未修改 |
| Page Change | NO | 未修改 |

## 12. 是否达到验收库执行条件

**YES，已达到“提交代码评审后再申请验收库执行”的技术前置条件。**

注意：本结论不是对真实验收库执行的授权。本轮严格停在隔离验证完成点。独立 worktree 当前为 detached HEAD，成果已暂存但未 commit、未 push；在进入真实验收库前仍必须完成正常代码评审/合入，并使用合入后的唯一 Git commit 重新固定执行基线。

## 13. 风险与保护

1. `system.0018` 是 SQLite 物理 DDL 收敛；非 SQLite 后端明确 no-op。若未来切换数据库后端，应另立任务形成相应基线，不能复用 SQLite 结论。
2. 真实验收库仍缺 `pde.0031` 与 `system.0018` 的应用记录；这是预期停止状态，不得手工插入或 fake。
3. 原工作树高度脏且包含大量用户既有成果；后续不得把独立 worktree 结果以覆盖方式回写原工作树。
4. v2 并发验证事故已隔离并弃用；最终证据仅使用全新 v4 和 rehearsal-v1。

## 14. 下一步唯一动作

**对独立 worktree 中已暂存的 P0-02 收口变更发起代码评审并形成唯一合入 commit；在该 commit 获得明确验收库执行授权前，不对真实验收库运行任何 Migration。**

## 15. 明确停止点

本轮在以下位置停止：

- 独立 worktree 收口成果：已完成、已暂存；
- 空库重建与 Schema 验证：已完成；
- 验收库副本演练：已完成；
- 真实验收库：未执行、无变化；
- commit：未创建；
- push：未执行；
- P1 与其他禁止范围：未进入。

**PCE P0-02 MIGRATION CONVERGENCE COMPLETE**
