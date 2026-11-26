# Runtime职责规范（兼容入口）

- 当前生效规范：`docs/governance/PCE-ERP运行层文件职责规范.md`
- 上位规范：`docs/governance/02-架构与运行边界/PCE-ERP架构与运行边界规范.md`
- 兼容入口版本：`V1.14.2.8.4.27.2.32`

本文件不建立第二套 Runtime。每个业务对象保持唯一正式 Runtime；页面筛选、列投影和下拉选项只能消费既有 Runtime/Provider，不得把页面缓存或静态 Fixture 建成第二事实源。

