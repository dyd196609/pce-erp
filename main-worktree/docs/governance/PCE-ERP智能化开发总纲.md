# PCE-ERP智能化开发总纲

# 文档信息

- 版本：`V1.14.2.8.4.27.2.32`
- 用途：建立PCE-ERP智能化开发优先原则，并接管后续版本的既有能力复用治理
- 适用范围：PCE-ERP全部模块、页面、服务、Runtime、Schema、Registry、Metadata、Config与验收任务
- 治理层级：现行《PCE-ERP开发治理总纲》之下的强制专项总纲，不是第二个最高治理入口
- 关联规范：`01-开发治理总纲/PCE-ERP开发治理总纲.md`、五大核心规范、对应模块专项规范
- 维护方式：持续更新

## 1. INTELLIGENCE-FIRST-001 智能化能力优先原则

所有未来版本在设计和编码前，必须先判断目标是否可由已有智能能力、Metadata、Registry、Schema、Runtime、Provider、组件、CRUD Engine或配置能力实现。可以复用时，必须复用；无法证明已有能力不适用时，不得创建新框架。

“智能化”不是自动替代业务人员，而是让系统基于统一事实自动生成界面、解析配置、汇集证据、发现异常、提出建议并执行可重复校验。智能结果不得脱离服务端事实、权限、版本和审计契约。

## 2. CAPABILITY-REUSE-001 已有能力复用原则

每个版本启动必须先完成以下四项，并在实施报告中逐项输出：

```text
一、智能化影响评估
二、已有能力扫描
三、复用方案
四、实施边界
```

扫描至少覆盖任务相关的既有Registry、Schema、Runtime、Provider、公共组件、Domain规则、权限与验收资产。复用方案必须记录能力名称、正式所有者文件、当前用途、复用范围、差距和选择结论。

决策顺序固定为：

| 情况 | 处理 |
|---|---|
| 已有能力可直接接入 | 在原能力所有权内直接复用，执行回归验收 |
| 只需小幅通用扩展 | 扩展原框架；证明兼容性、权限、审计与受影响消费者 |
| 需要重大业务重构 | 暂缓，形成独立版本方案，不在当前任务暗改业务闭环 |
| 没有明确业务收益 | 保持现状 |
| 能力归属或事实来源不明 | 输出`UNKNOWN`并阻断新增框架 |

## 3. DUPLICATE-FRAMEWORK-001 禁止重复框架建设

禁止新建第二套Metadata、Registry、Schema、Runtime、Config、列表、筛选、下拉、权限或页面生成体系；禁止绕过已有Schema，以页面硬编码替代智能配置；禁止只因用户给出的目录当前不存在，就创建同名顶层目录复制已有能力。

当前目录所有权如下：

- 前端Metadata、Schema、Runtime、Registry与智能组件统一归属`frontend/src/meta`；其中具体能力位于`meta/schema`、`meta/runtime`、`meta/registry`、`meta/core`、`meta/components`及相关领域目录。
- 后端通用流程Runtime归属`backend/workflow_runtime`；业务服务与Runtime按模块归属`backend/<module>`，不得为形式统一复制到新的`backend/runtime`或`backend/services`。
- 发现历史并行实现时，先完成引用、事实所有者和兼容性审计，再提出收敛方案；不得直接删除、替换或再建第三套。

## 4. 业务模块智能化升级原则

业务模块升级优先复用已有Registry、Schema和Runtime，实现列表、字段、筛选、下拉、权限、证据汇集、异常识别与建议能力。所有显示、诊断、`strictFacts`和验收必须复用同一服务端事实；页面不得自行计算业务结论。

基础资料智能化方向按以下规则执行：

| 方向 | 复用入口 | 边界 |
|---|---|---|
| 列表自动生成 | 既有Registry、Schema、Page/CRUD Renderer、企业列表契约 | 不在页面重复声明通用列基座 |
| 字段自动生成 | Schema Contract、Normalizer、Resolver | 字段业务语义仍由领域契约负责 |
| 筛选自动生成 | Filter Schema、列表筛选Runtime、高级筛选组件 | 字段必须声明`filterType` |
| 下拉自动生成 | `optionsSource/optionsProvider`与受治理Runtime | 禁止页面静态拼接正式选项 |
| 用户配置 | 在现有Registry上增加服务端配置投影 | 未具备租户、角色、版本、审计、回滚前不得声称已支持 |
| 权限控制 | 既有Permission Runtime、Action Contract和服务端权限 | 隐藏按钮不等于服务端授权 |

## 5. 人工维护与自动化边界

系统可以自动执行只读扫描、配置解析、页面生成、事实聚合、完整性检查、异常提示、风险计算和候选建议；可以在受治理规则下生成不落库的草稿投影。

以下事项必须由有权限的人员通过显式Action确认并保留人员、时间、原因、版本和Before/After证据：主数据新增或合并、同名供应商处置、供应商分类确认、关系主次确认、价格确认、供应商选择、询价发送、报价确认、核价、推荐确认、审批以及采购订单创建或状态推进。

禁止自动审批、自动选最低价、自动推荐并落地供应商、自动生成交易对象、自动覆盖人工数据或绕过Guard。统一优先级为：

```text
人工确认结果 > 系统计算结果 > 默认规则结果
```

## 6. 供应商采购链智能化边界

供应商档案、关系、价格以及`PurchaseRequest -> PurchaseInquiry -> SupplierQuotation -> QuoteComparisonFact -> PriceApprovalPreparation -> SupplierRecommendationDecision -> PurchaseOrderGate -> PurchaseOrder`必须保持现有业务身份、来源关系、人工决策、Guard和生命周期。

可安全升级的范围是复用现有能力增强只读证据、智能提示、完整性校验和界面生成。涉及事实迁移、状态机替换、自动业务决定、交易写入或推翻既有闭环的升级必须暂缓并另立版本。本总纲不授权任何业务写入。

## 7. 验收门禁

- `PCE-INTELLIGENCE-GOVERNANCE-001`：本总纲存在、在唯一总纲和依赖注册表中登记，四项启动流程可检索。
- `PCE-CAPABILITY-REUSE-001`：任务具有能力清单、正式所有者和复用决策；直接复用项没有创建平行能力。
- `DUPLICATE-FRAMEWORK-001`：不存在未经授权的第二套Metadata/Runtime/Registry/Schema/Config体系，缺失目录没有被机械补建。

任一门禁为`FAIL`或`UNKNOWN`时，禁止进入实施或签发READY。治理-only版本以治理文件可检索、引用有效、验收脚本可执行以及业务代码树和数据库Hash不变作为Build证据。

## 8. 真实运行对象一致性与验收权限（V1.14.2.8.4.27.2.45.6）

- `SAME-OBJECT-ACCEPTANCE-001`：自动验收、Runtime、API、页面显示、用户点击及最终归档必须追踪到同一 `SupplierQuotation` 对象与同一明细来源。`Automatic Test SupplierQuotation ID = Runtime SupplierQuotation ID = API SupplierQuotation ID = Page SupplierQuotation ID = Clicked SupplierQuotation ID = SupplierMaterialPrice.sourceObjectId`；任一层不能证明或不相等即为 `FAIL`，禁止 READY。
- `HUMAN-ACCEPTANCE-AUTHORITY-001`：Codex 和自动浏览器只能签发 `Browser Automatic Acceptance` 与 `Real Browser Evidence`。未收到用户明确“人工验收通过”时必须输出 `Human Acceptance: WAITING`；Playwright 或任何自动点击不得写成 `Browser Human Acceptance: PASS`。
- `AUTHORIZED-BUSINESS-WRITE-001`：报告必须分别输出 `Authorized Business Write Count` 与 `Unauthorized Business Write Count`。只读治理版本两者均为 0；明确授权的数据建设版本允许前者大于 0，但后者必须为 0，并逐项记录对象类型、对象 ID、写入次数、原因、来源版本、测试/正式事实属性及回滚能力。禁止以笼统的 `Business Write Count: 0` 掩盖实际写入。
- `RUNTIME-BEFORE-TEST-001`：用户反馈真实页面失败后，必须按 `Browser Page -> API -> Runtime -> Service -> Database` 顺序先追踪现有对象；不得先增加 Fixture、Mock、测试数据、旁路 Service 调用或内部 Service 直调来制造 PASS。自动测试只证明能力存在，不能替代真实运行链成立。

上述规则属于最高级 READY 门禁。统计数量相同不能替代对象 ID 一致性；会话投影、持久对象、测试数据库与开发运行数据库必须明确区分。
# 统一列表刷新与逐对象动作（V1.14.2.8.4.27.2.45.10）

- 标准列表刷新必须复用 `LIST-REFRESH-CONTRACT-001`，通过当前 Registry 的正式 Provider 重新读取服务端并保留用户列表条件；没有服务端 Provider 时不得伪报真实刷新。
- 列表业务动作必须由 Action Runtime（操作运行层）逐对象计算。已归档、映射阻断、未完成和未通过不得因全局对象数量而互相影响。
- 历史供应商/物料引用只能通过既有映射能力建立显式、持久、可追踪关系；没有唯一权威目标时固定为 `WAITING_MANUAL_MAPPING（等待人工映射）`，禁止编码外形推断。
