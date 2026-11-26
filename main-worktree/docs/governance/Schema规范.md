# Schema规范（兼容入口）

- 当前生效规范：`docs/governance/02-架构与运行边界/PCE-ERP架构与运行边界规范.md`
- 现有实现契约：`frontend/src/meta/core/schemaContract.js`、`schemaNormalizer.js`、`schemaRegistry.js`
- 兼容入口版本：`V1.14.2.8.4.27.2.32`

本文件不建立第二套 Schema 体系。字段、类型、必填、枚举与关系统一属于 Schema；页面必须消费现有 Registry/Schema，不得在页面重新声明一套列表字段事实。

