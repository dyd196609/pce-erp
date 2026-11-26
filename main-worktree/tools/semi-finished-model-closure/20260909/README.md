# 半成品配置最小模型候选包 — 仅隔离验证

本包对应当前唯一正式`pde`模型与原有`db_table`，不是第二套生产模型。生产未应用。

- `canonical-models.patch`：以本轮冻结的实际`backend/pde/models.py`为基线，包含历史契约恢复与最小BOM/数量扩展。仅执行了`git apply --check`，未应用生产。
- `candidate/backend/`：与已完成迁移、44项约束测试、106真实对象round-trip及回滚的隔离候选逐字节一致。
- `MANIFEST.json`：源代码、生产模型/数据库基线SHA与候选文件SHA。
- `0024`：先验证既有孤表DDL一致，再仅补迁移State；Database Operations=0。不是绕过缺失表的通用fake迁移。
- `0025`：四张类型化关系表及既有ProductBOM、BOMItem、TemplateMaterialRequirementSlot最小扩展；不修改Routing。
- 固定数量必须有真实正值；CALCULATED/MANUAL可保留NULL；不得用0或1占位。公式只引用既有EngineeringRuleDefinition。
- 新增关系、族、草稿BOM版本和71来源继承仅存在于`.runtime/semi-finished-model-closure-20260909/isolated.sqlite3`。
- 部署前必须另获生产授权，并重做真实数据库DDL、迁移历史分叉、权限/写入链及生产回滚Gate。本包没有一键生产执行器，也不声称生产可写API已交付。
- 隔离脚本位于`D:\Dev-PCE\Source\scripts\semi_finished_model_closure_*.py`。数据库路径在Django初始化前锁定为隔离目录。
- 真正采购身份、族允许成员、厚度语义、数量规则及损耗未齐备；本包通过不等于耗用业务READY。

当前技术证据：`D:\Dev-PCE\Source\docs\evidence\semi_finished_model_closure_20260909`。
