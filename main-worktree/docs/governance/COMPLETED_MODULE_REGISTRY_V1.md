# COMPLETED MODULE REGISTRY V1

机器权威台账：`completed_module_registry.v1.json`  
生效日期：2026-09-11  
当前 `FROZEN_VERIFIED` 模块：**0**  
当前 Unfreeze 授权：**NO**

## 分类规则

- `FROZEN_VERIFIED`：明确用户验收 + 当前非回归 + Freeze Contract + Source Baseline 同时成立。
- `DEVELOPED_BUT_DRIFTED`：实现/历史证据存在，但当前用户运行与设计或自动报告冲突。
- `DEVELOPED_NOT_CURRENTLY_VERIFIED`：实现/历史证据存在，但本轮没有当前用户复验闭环。
- `PLANNED_NOT_PROVEN`：本次能建立的证据主要停留在计划、Registry、Meta、Route 或 migration 名称。
- `UNKNOWN_REQUIRES_REVIEW`：对象边界或证据冲突需专项核验。

## 人工可读台账

| 模块 | 状态 | AS-BUILT 证据摘要 | AS-RUNNING | AS-FROZEN |
|---|---|---|---|---|
| 企业基础资料 | DEVELOPED_NOT_CURRENTLY_VERIFIED | 源码与历史报告 | 未复验 | NO |
| 组织结构 | DEVELOPED_NOT_CURRENTLY_VERIFIED | 历史人工验收/封板报告 | 当前非回归未证明 | NO |
| 供应商 | DEVELOPED_NOT_CURRENTLY_VERIFIED | Migration、验收报告、历史 121 条事实 | 当前采购域有冲突 | NO |
| 采购物料 | DEVELOPED_NOT_CURRENTLY_VERIFIED | MaterialMaster 权威报告、历史 270 条事实 | 未复验 | NO |
| 采购申请 | DEVELOPED_NOT_CURRENTLY_VERIFIED | 专页、Route、Migration、历史验收 | 当前页面 58 条可见，但菜单层级冲突 | NO |
| 采购审批 | DEVELOPED_NOT_CURRENTLY_VERIFIED | 专页、Route、历史验收 | 未复验 | NO |
| 询价准备 | DEVELOPED_NOT_CURRENTLY_VERIFIED | 专页、Route、历史验收 | 未复验 | NO |
| 采购询价 | DEVELOPED_NOT_CURRENTLY_VERIFIED | 专页、Route、历史验收 | 未复验 | NO |
| 供应商报价 | DEVELOPED_NOT_CURRENTLY_VERIFIED | Migration、专页、Route、历史验收 | 未复验 | NO |
| 报价比较 | DEVELOPED_NOT_CURRENTLY_VERIFIED | Migration、专页、Route、历史验收 | 未复验 | NO |
| 采购核价 | DEVELOPED_NOT_CURRENTLY_VERIFIED | Migration、专页、Route、历史验收 | 未复验 | NO |
| 供应商推荐 | DEVELOPED_NOT_CURRENTLY_VERIFIED | 专页、Route、历史证据存在但阶段记录不一致 | 未复验 | NO |
| 采购订单准入 | DEVELOPED_NOT_CURRENTLY_VERIFIED | 专页、Route、历史证据含早期阻断与后续通过 | 未复验 | NO |
| 采购订单 | DEVELOPED_NOT_CURRENTLY_VERIFIED | 模型、Route、历史 325/724 事实 | 未复验 | NO |
| 收货/采购收货预备 | DEVELOPED_BUT_DRIFTED | Route、组件、1 条正式收货 | 正式路径与用户 UI 不一致 | NO |
| 来料检验 | DEVELOPED_BUT_DRIFTED | Route、组件、1 条正式检验 | 用户无法正常打开 | NO |
| 入库 | DEVELOPED_NOT_CURRENTLY_VERIFIED | 数据/Migration 证据，自动报告 1 条 | 未由用户复验 | NO |
| 库存余额 | DEVELOPED_NOT_CURRENTLY_VERIFIED | Route、自动 DB/API/UI 1 条/数量 2 | 用户未验收 | NO |
| 库存流水 | DEVELOPED_NOT_CURRENTLY_VERIFIED | Route、自动报告 1 条 | 用户未验收 | NO |
| 供应商对账 | DEVELOPED_NOT_CURRENTLY_VERIFIED | Route、Migration、Workflow 规则 | 未复验 | NO |
| 供应商绩效 | DEVELOPED_NOT_CURRENTLY_VERIFIED | Route、Migration | 未复验 | NO |
| 采购员绩效 | PLANNED_NOT_PROVEN | 本审计仅确认 Registry/Route | 未证明 | NO |
| 差异分析 | DEVELOPED_NOT_CURRENTLY_VERIFIED | Route、协同 Migration | 未复验 | NO |
| 供应商确认 | DEVELOPED_NOT_CURRENTLY_VERIFIED | Route、Workflow Migration | 未复验 | NO |
| 付款申请 | DEVELOPED_NOT_CURRENTLY_VERIFIED | Route、Migration | 未复验 | NO |
| 付款状态记录 | PLANNED_NOT_PROVEN | Registry/Route/Migration 名称，完成证据不足 | 未证明 | NO |
| 采购应付预备 | DEVELOPED_BUT_DRIFTED | Route、组件存在 | 用户菜单缺失 | NO |
| 采购应付核对 | DEVELOPED_BUT_DRIFTED | Route、组件、Migration 存在 | 用户菜单缺失 | NO |
| 供应商结算 | DEVELOPED_BUT_DRIFTED | Route、组件存在 | 用户找不到预期入口 | NO |
| 供应商结算完成 | DEVELOPED_NOT_CURRENTLY_VERIFIED | Route、Migration；用户看到 1 条 | 页面存在但未完整验收 | NO |
| 采购对账 | DEVELOPED_BUT_DRIFTED | Route、组件存在 | 用户菜单缺失 | NO |

## 当前裁决

供应商/采购整体不得冻结。`Supplier/Procurement = DEVELOPED_BUT_DRIFTED / DEVELOPED_NOT_CURRENTLY_VERIFIED`。自动 Gate 通过不改变该裁决。所有 `freezeContractPath` 与 `sourceBaselineReference` 目前为空，意味着没有模块因本轮治理建档而被追认冻结；后续必须逐模块补证，而不是批量升级。
