# CRUD Engine规范（兼容入口）

- 当前生效规范：`docs/governance/02-架构与运行边界/PCE-ERP架构与运行边界规范.md`
- 现有实现契约：`frontend/src/meta/crud/crudEngine.js`、`CRUDRenderer.vue`
- 兼容入口版本：`V1.14.2.8.4.27.2.32`

本文件不建立第二套 CRUD Engine。CRUD 表格和表单定义必须来自既有 Meta 字段，业务动作继续遵守 Action、Guard、Domain 与 Persistence 边界；不得因元数据接入产生业务写入或绕过既有业务规则。

