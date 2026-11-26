# PCE-ERP统一软件开发验收标准

## 页面场景参数验收（V1.14.2.8.4.20.2）

- 带场景 Query 的企业列表必须验证参数已经进入页面运行时，不能只验证 URL 文本存在。
- 必须验证场景数据 Provider 已替换普通数据 Provider，测试数据确实进入列表。
- 刷新页面后 Query、数据模式、批次、场景和清理策略必须保持一致。
- 场景模式与普通模式必须隔离；场景模式不得读取或写入普通业务对象。

版本：V1.14.2.8.4.14.1

## 1. 适用范围

本标准适用于PCE-ERP全部业务页面。页面必须按“开发 → 自动验收 → 单页人工验收 → 验收归档 → 下一页面”的顺序交付。多个页面不得共享一份人工验收结论；自动验收通过不能替代人工验收。

## 2. 事实与数据安全

- 业务事实必须来自服务端，`factSource=server`。
- 演示数据、mock和localStorage数据不得作为企业运行通过证据。
- 自动验收不得创建业务对象、推进业务状态或补写历史数据。
- 验收必须记录数据库Hash、业务写入数量，并保持`productionUserDataWritten=false`。

## 3. 单页验收维度

每页必须独立检查A至M：页面身份、PCE Enterprise Page V2模板、路由、可点击流程导航、服务端事实、API权限、上下游对象关系、状态机、按钮登记、业务边界、异常处理、性能和数据保护。

页面身份至少包含`pageCode`、`pageName`、`moduleCode`、`businessObject`和`version`。每个业务按钮必须登记`buttonName`、`allowedStatus`、`actionType`与`writeScope`。

## 4. 性能标准

- 普通页面总加载时间小于1000ms。
- 复杂页面总加载时间小于3000ms。
- 必须记录`routeLoadTime`、`schemaLoadTime`、`apiTime`、`renderTime`和`totalTime`。

## 5. 发布门禁

只有自动验收为PASS、人工验收为PASS且人工验收记录已经归档时，`nextPageAllowed`才允许为true。人工验收为PENDING时，即使自动验收全部通过，也不得标记页面最终验收通过或进入下一页面。

矩阵扫描可以在一次命令中检查多页“是否已经登记”，但每页必须保存独立检查结果；矩阵扫描不得产生跨页面的统一最终通过结论。最终验收和归档必须逐页执行。

## 6. SCM首批试点

SCM采购与供应商结算16页全部登记在`SCMEnterpriseAcceptanceMatrixV11428141`。验收编码与既有运行编码不一致时使用`runtimePageCode`映射；不得因此修改流程节点名称、顺序或业务路由。
