# PCE 代理开发约束

- PCE 软件开发以业务流程中心为最高业务建设主线：先明确企业业务流程、起止节点、业务对象、责任与操作/审核关系，再设计权限、数据模型和软件实现。模块及组织、权限、GRA、Workflow 等支撑能力必须服务正式业务流程；不得先建技术能力再寻找业务用途。既有安全、授权、冻结和数据保护门禁不因流程优先而降低；详细规则见 `docs/governance/PCE CODEX开发指令规范管理V1.2.md` 第 34 节。
- 每个 PCE 正式任务在首次修改前必须全文读取 `docs/governance/PCE CODEX开发指令规范管理V1.2.md`；所有 UI 人工验收交付必须执行其中 `DELIVERED USER STATE CONTRACT`，在全部测试后对同一可见浏览器 Tab 做最后路径与 Readback，无法保证同一用户状态时只能报告 `DELIVERED USER STATE = NOT GUARANTEED`。
- 共享页面壳的可观测性注册必须使用实例所有权；旧页面卸载不得清除新页面的诊断提供者。
- API、页面、复制诊断、`strictFacts` 与验收报告必须复用同一服务端事实，不得用上一页缓存或前端重算补齐。
- 银行发送任务只允许 `prepared -> queued -> ready_to_send`；禁止进入 `sent`，禁止任何银行发送或付款执行写入。
- 银行发送生产隔离门禁只允许 `created -> checked -> isolated`；生产接口、生产密钥、真实发送权限和付款执行权限必须保持关闭，模拟审计不得推进业务状态。
- 企业级列表静态治理必须识别 `PceEnterpriseListTable` 的组件契约；工具栏、筛选、选择、冻结列、操作列与单一横向滚动拥有者不得因封装而被误判为缺失。
- 企业级列表页面必须接入 `PCE-ENTERPRISE-LIST-CONTRACT-V1.1`、`PceEnterpriseListTable`、`PceEnterpriseAdvancedFilter` 与 `PceBusinessStatus`，不得在页面重复建设通用列表基座。
- 高级筛选字段必须声明 `filterType`；枚举使用带 `options` 或受治理选项提供者的 `select`，日期使用 `date`/`daterange`，页面不得自行创建筛选控件。
- 企业级列表横向滚动所有权属于表格内部；选择框、序号、主业务编号固定在左侧，操作列固定在右侧。
- 用户页面只显示服务端 `statusLabel`；`statusCode` 仅用于内部治理，禁止直接向业务用户展示。
- 银行发送最终审批只允许 `pending -> first_approved -> second_approved -> final_locked`；两次审批必须由不同用户和不同角色完成，`final_locked` 不等于已发送，禁止进入 `approved_to_send` 或 `sent`。
- 生产放行评审只允许 `draft -> reviewing -> review_passed -> locked`；至少双人且用户、角色必须分离，`locked` 不等于允许发送。生产接口、生产密钥、真实发送权限和付款执行权限必须保持关闭。
- 银行发送执行框架只允许 `draft -> designed -> security_reviewed`；框架对象不是执行或发送记录，禁止进入 `enabled`、`sent`，禁止使用 `production` 环境。
- `BankConnectorAdapter` 的准备、签名、发送与查询接口在真实发送版本开放前只能返回本地模拟结果；不得发起网络调用、加载生产证书、自动重试或形成真实银行回执。
- 供应商对账只允许 `draft -> internal_review -> supplier_confirming -> completed`，必须通过 `BusinessStateTransition`；对账完成不得自动创建付款、银行发送、资金或总账对象。
- 采购员与供应商绩效页面必须展示服务端持久化指标及其来源关系，评分与五端事实不得由页面重新计算。
- 供应商对账、供应商绩效与采购员绩效页面必须由 `PceListPageShell` 提供页面身份、动作说明、流程、导航、可观测性和标题治理；禁止在业务页面内重复建设独立顶部结构。

## Completed Module Preservation Mandatory Reading

- 每个正式任务首次修改前，必须完整读取 `D:\Dev-PCE\AGENTS.md`、本文件、`docs/governance/PCE CODEX开发指令规范管理V1.2.md`（或未来有效上位版本）、`docs/governance/PCE 已开发模块固化与变更保护规范 V1.0.md`、`docs/governance/completed_module_registry.v1.json`，以及所有受影响 Module Freeze Contracts。
- 必须输出 `COMPLETED MODULE GOVERNANCE READING RECEIPT`，明确 Preservation Standard、Registry、Affected Frozen Modules、Freeze Contracts 与 Unfreeze Authorization。Receipt 缺失时不得修改源码。
- 必须先执行 `docs/governance/COMPLETED_MODULE_PROTECTION_PREFLIGHT_V1.md`；命中 Frozen Core 或 Frozen Shared Dependency 且没有用户明确 Unfreeze 授权时，结论必须为 `UNFREEZE AUTHORIZATION REQUIRED` 并停止。
- 用户真实运行结果高于自动化、Registry、Meta、Route 和报告；冲突时总体 Gate 为 FAIL/BLOCKED。任何新增必须 Preserve-and-Extend，禁止静默替换菜单、路由、组件、API、数据权威、权限、Workflow 或 DB/API/UI identity。

## 两主题共同协作唯一入口

开始PCE-ERP任务前必须读取 [共同开发与统一交付规则](D:/Dev-PCE/Source/docs/governance/PCE_TWO_THEME_COLLABORATION.md)，并按其中唯一共同基线指针与共享台账接续。该规则持续适用于“软用＋日期”和“纯日期”及以后各日期主题；本指引仅引用，不另存规则副本。
