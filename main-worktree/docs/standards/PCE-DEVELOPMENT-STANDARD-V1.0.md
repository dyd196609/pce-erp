# PCE-DEVELOPMENT-STANDARD-V1.0

## 页面诊断生命周期

1. 路由切换时，页面向共享壳注册的 `refresh/buildDiagnostics` 必须绑定页面实例所有权。
2. 页面卸载只能注销自己注册的提供者；不得无条件清空后来页面已经注册的提供者。
3. 真实浏览器验收必须至少执行一次跨页或刷新后的“复制诊断数据”，核对版本、模块、API、页面与 `strictFacts`。
4. 诊断生命周期修复不得改变业务状态、业务动作资格或写入口径。

## 企业级列表页面运行基座

1. 新建或迁移的企业级列表页面必须声明 `PCE-ENTERPRISE-LIST-CONTRACT-V1.0`。
2. 通用列表结构必须使用 `PceEnterpriseListTable`，高级筛选使用 `PceEnterpriseAdvancedFilter`，业务状态使用 `PceBusinessStatus`。
3. 列表页面只声明筛选字段、业务列、导出字段和只读操作，不得重复实现通用工具栏、固定列和滚动布局。
4. 选择框、序号、主业务编号必须左冻结，操作列必须右冻结；横向滚动只能影响中间业务字段。
5. 列表运行基座不得计算服务端业务事实、判定业务权限、推进状态或发起业务写入。
6. API、页面、诊断和 `strictFacts` 必须继续复用同一服务端事实。
7. 状态组件只能显示 `statusLabel`，不得向用户渲染 `statusCode`。
