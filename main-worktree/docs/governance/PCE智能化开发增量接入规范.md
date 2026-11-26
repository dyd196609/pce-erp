# PCE智能化开发增量接入规范（兼容入口）

- 生效版本：`V1.14.2.8.4.27.2.41`
- 唯一正文：[`PCE智能化增量接入规范.md`](PCE智能化增量接入规范.md)
- 状态：兼容文件名入口，不复制规则正文

本文件用于兼容任务文档中的历史命名。PCE智能化增量接入规则的唯一维护正文仍为`PCE智能化增量接入规范.md`；修改、验收和引用均必须指向唯一正文，禁止由本入口形成第二套治理规范。
# V1.14.2.8.4.27.2.45.8 价格决策增量接入

价格归档继续复用既有 `SupplierMaterialPriceRuntime`、Provider、Metadata、Registry 和权限入口。允许在 `masterdata` 价格域补齐持久 `PriceApprovalResult` 与 `SupplierMaterialPrice` 事实模型，并让原 Runtime 接回；禁止创建平行 Runtime、审批中心或页面加载自动写入。归档写入只由“确认报价”显式动作触发，幂等键为核价准备对象身份。
