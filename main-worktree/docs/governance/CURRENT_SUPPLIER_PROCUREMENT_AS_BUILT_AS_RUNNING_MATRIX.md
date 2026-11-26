# CURRENT SUPPLIER PROCUREMENT AS-BUILT / AS-RUNNING MATRIX

| 模块 | AS-DESIGNED | AS-BUILT | AS-RUNNING | AS-FROZEN |
|---|---|---|---|---|
| 供应商 | 正式主数据 | Migration/报告/历史 121 条 | 当前采购域未完整复验 | NO |
| 采购物料 | MaterialMaster 唯一权威 | 报告/历史 270 条 | 未复验 | NO |
| 采购申请 | 正式菜单路径、专页 | Route/专页；58/104 | 页面 58 条可见，菜单层级冲突 | NO |
| 采购审批至订单准入 | 连续采购前段流程 | 九个专页/Route/历史验收 | 本轮未逐页复验 | NO |
| 采购订单 | 正式订单对象 | 模型/Route；历史 325/724 | 未复验 | NO |
| 收货预备 | 正常菜单可达 | Route/组件；1 条 | 路径不一致 | NO |
| 来料检验 | 正常菜单可达 | Route/组件；1 条 | 用户不能正常打开 | NO |
| 入库/库存 | 连续业务链 | 数据、Route；1/1/数量2 | 仅自动证据 | NO |
| 应付预备 | 正常菜单可发现 | Route/组件 | 菜单缺失 | NO |
| 应付核对 | 正常菜单可发现 | Route/组件/Migration | 菜单缺失 | NO |
| 供应商结算 | 正常菜单可发现 | Route/组件 | 用户找不到 | NO |
| 供应商结算完成 | 独立完成记录页 | Route/Migration | 用户看到 1 条 | NO；尚未完整验收 |
| 采购对账 | 正常菜单可发现 | Route/组件 | 菜单缺失 | NO |

整体裁决：`SUPPLIER_PROCUREMENT_CURRENT_FREEZE = NOT AUTHORIZED`。
