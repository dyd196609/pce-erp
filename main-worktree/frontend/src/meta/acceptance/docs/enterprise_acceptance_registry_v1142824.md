# V1.14.2.8.4.24 Enterprise Acceptance Framework Registry

## 定位

本版本只在既有 Template、Evidence Engine、Runner、SCM Acceptance Model 之上增加 Registry、Activation 与 Service 层。既有接口保持兼容，不修改任何业务页面、业务状态或业务 API。

## 注册结构

SCM Module Profile 注册：

- 3 个对象：PurchaseRequest、PurchaseInquiry、PurchaseOrder。
- 1 个模块模板：SCM Business Page Acceptance Template V2。
- 3 层模板栈：Master、Common、SCM V2。
- 10 个既有只读 Evidence Collector。
- 8 个规则集，自动形成 20 个激活规则绑定。
- 既有 Enterprise Page Acceptance Runner。
- 不可变验收归档定义。

`SCM_TRACE_COLLECTOR` 与 `SCM_ACTION_COLLECTOR` 是面向注册语义的别名，分别复用现有 `SERVER_FACTS_COLLECTOR` 与 `ACTION_EVIDENCE_COLLECTOR`，不重复建设 Collector。

## 自动激活流程

```text
moduleCode
  -> Enterprise Acceptance Registry
  -> Template Stack Resolver
  -> Evidence Collector Resolver
  -> Business Rule Resolver
  -> Acceptance Runner Profile
  -> Archive Profile
```

主要接口：

- `activateModule({ moduleCode })`：激活模块验收框架。
- `getModuleAcceptanceProfile({ moduleCode })`：返回模块治理能力。
- `validateModuleRegistration(...)`：阻断缺少模板、规则、Collector、Runner 或 Archive 的注册。
- `executeModuleAcceptance(...)`：先激活 Profile，再调用兼容的既有 Runner。

未知模块或不完整注册返回 `BLOCKED`，不会回退到无治理运行。

## 只读与数据保护

激活过程只加载验收配置并注册内存 Collector，不调用业务写 API，不创建业务对象，不修改业务状态，不触发审批：

```text
Business Logic Changed=NO
SCM Logic Changed=NO
Business Write Count=0
Production Data Written=NO
productionUserDataWritten=false
```

## 验证

在 `frontend` 目录运行：

```text
node scripts/verifyEnterpriseAcceptanceRegistryV1142824.mjs
node --test tests/acceptance/enterpriseAcceptanceRegistryV1142824.test.mjs
```

自动验证必须达到 `PASS=10`、`FAIL=0`、`UNKNOWN=0`。归档输出位于：

`test-results/page-acceptance/V1.14.2.8.4.24/registry/`
