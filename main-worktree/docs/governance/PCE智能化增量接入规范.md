# PCE智能化增量接入规范

- 规则编号：`PCE-INTELLIGENCE-INTEGRATION-001`
- 生效版本：`V1.14.2.8.4.27.2.40`
- 上位规范：`PCE-ERP智能化开发总纲.md`
- 适用范围：PCE-ERP后续新增或增量升级的业务页面

## 1. 渐进式接入原则

业务闭环优先，智能能力只做增强；已有架构保持稳定。每个增量版本必须先输出：智能化影响评估、已有能力扫描、复用方案、实施边界。已有能力可满足时必须直接接入，不能以“更方便”为由新建第二套框架。

## 2. 六项强制判断

| 检查面 | 必答问题 | 正式接入口 | 禁止方式 |
|---|---|---|---|
| 字段 | 字段是否来自Schema/Metadata？ | 现有 Schema Registry、领域Schema、Metadata Registry | 页面重复声明正式字段语义或列名 |
| 列表 | 是否来自List Runtime？ | `PCE-ENTERPRISE-LIST-CONTRACT-V1.1`、`PceEnterpriseListTable` | 复制表格基座或页面自建滚动/固定列 |
| 筛选 | 是否来自Filter Runtime？ | `listFilterRuntime`、`filterType`、受治理选项Provider | 页面自行创建通用筛选控件或静态正式选项 |
| 按钮 | 是否来自Action Runtime？ | Schema Action Contract、`listActionColumnRuntime`、权限Runtime | template硬编码通用按钮、仅靠隐藏按钮授权 |
| 数据 | 是否来自Provider？ | 服务端事实、领域Provider、统一Runtime Adapter | 页面缓存、Fixture或前端重算补齐正式事实 |
| 验收 | 是否可自动化且完成真实浏览器验收？ | Acceptance Runtime、专项门禁、真实URL与截图 | 仅以源码扫描或历史截图签发READY |

任一项回答为`NO`或`UNKNOWN`时，必须先记录差距和边界；不得通过页面硬编码绕过。

## 3. 标准接入链

```text
Metadata Registry
  -> Schema Contract
  -> Provider / Server Facts
  -> Page/List/Filter/Action Runtime
  -> Governed Component
  -> Acceptance Runtime
  -> Real Browser Evidence
```

API、Provider、Runtime、页面、诊断、`strictFacts`与验收必须复用同一服务端事实。

## 4. 扩展决策

1. 可直接复用：接入现有所有者并做回归。
2. 需要小幅通用增强：只扩展原所有者，记录消费者、兼容性和验收。
3. 涉及数据库、状态机或业务闭环重构：暂缓并另立授权版本。
4. 无明确收益：保持现状。
5. 所有权不明：标记`UNKNOWN`并阻断开发。

## 5. 基础资料方向冻结

员工、物料、供应商、价格、关系、工艺、设备逐步接入现有 Metadata/Schema/Runtime。当前不建设企业配置中心；租户/角色配置必须等待权限、版本、审计、回滚和服务端持久化方案齐备。

## 6. 禁止事项

禁止新增第二套 Metadata、Schema、Registry、List Runtime、Page Runtime、Filter Runtime、Action Runtime或Provider体系；禁止大范围重构稳定业务页面；禁止智能建议自动替代人工核价、供应商选择、审批、采购订单创建或状态推进。

## 7. 版本门禁

- `PCE-INTELLIGENCE-INTEGRATION-001`：六项判断与接入链可检索。
- `NO-DUPLICATE-FRAMEWORK-001`：未创建平行框架或禁止目录。
- `RUNTIME-REUSE-001`：新增页面/能力引用现有正式所有者。
- `BUSINESS-REGRESSION-001`：受保护业务实现与数据库哈希不变，适用回归通过。
- `REAL-BROWSER-EVIDENCE-001`：所有指定页面有当前版本真实URL、区域、字段、按钮和截图。

三重门禁 `Automatic Acceptance + Browser Human Acceptance + Build` 全部PASS后才可签发READY。

## 8. 价格持久化四层同对象门禁（V1.14.2.8.4.27.2.45.9）

任何 `SupplierMaterialPrice（供应商物料有效价格）` 持久化 PASS 必须同时证明 `Database Object（数据库对象） = Runtime Object（运行层对象） = API Object（接口对象） = Browser Object（浏览器对象）`。任一层字段契约不一致、数量不一致或对象编号不一致均为 FAIL，不得用数据库存在或单元测试通过替代页面事实。
