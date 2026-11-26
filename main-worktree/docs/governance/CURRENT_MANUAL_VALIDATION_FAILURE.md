# CURRENT MANUAL VALIDATION FAILURE

## Formal Verdict

- Run: `manual-validation-recovery-20260911-054417-fe795775`
- USER MANUAL VALIDATION: FAIL
- REPORT VS USER REALITY CONFLICT: YES
- SUPPLIER_PROCUREMENT_FREEZE: NOT AUTHORIZED
- Rollback: NOT STARTED
- Forward-after-Rollback: NOT STARTED
- Business code changes: 0
- Production writes / migrations / recovery writes: 0 / 0 / 0

## Failure facts

正式菜单路径与实际 UI 不一致；来料检验节点无法正常打开；采购应付预备、采购应付核对、预期供应商结算、采购对账在实际菜单缺失；另一独立对象“供应商结算完成”存在且用户看到一条记录。自动 Seven Real Menu 7/7 与 Run Manifest eight-menu PASS 均被用户现实否决。

## Safe closure

Run Manifest、Bootstrap、当前 UI 文本回读与冲突矩阵已保存。前端 PID 46960、后端 PID 48704 已精确停止，端口 5174/8016 无监听，指定运行目录已清理。没有进入 Rollback、Forward、Recovery 或 Module Freeze。
