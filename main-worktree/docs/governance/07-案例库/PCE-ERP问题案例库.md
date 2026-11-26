# PCE-ERP 问题案例库

# 文档信息

- 版本：V1.14.2.8.18.20
- 用途：集中保存治理与各业务模块的问题案例、根因、解决方案和回归证据
- 适用范围：PCE-ERP全部模块与治理资产
- 优先级：高
- 关联规范：PCE-ERP开发治理总纲、PCE-ERP自动验收与证据治理规范
- 维护方式：持续更新；只追加，不覆盖历史

文档编号：`PCE-ERP-GOV-CASE-LIBRARY-001`  
当前版本：`2.7`  
维护状态：长期有效、只追加不覆盖历史  
最近更新：`V1.14.2.8.18.20.4`

## 1. 登记规则

每个新增问题必须登记案例编号、发现版本、问题描述、根因、解决方案和纳入规则，并关联复现证据与回归测试。已有案例的结论变化使用追加记录，不静默改写历史。

## 2. 案例模板

```md
### CASE-<MODULE>-NNN：<标题>
- 案例编号：CASE-<MODULE>-NNN
- 发现版本：<version>
- 问题描述：<用户可观察的问题>
- 根因：<事实链上的根因>
- 解决方案：<修复与边界>
- 纳入规则：<规范/PROCESS 编号>
- 回归测试：<test/report>
```

## 3. SCM 采购案例

### CASE-SCM-001：采购申请状态与业务状态混淆

- 案例编号：`CASE-SCM-001`
- 发现版本：`V1.14.2.8.18.2`
- 问题描述：审批已通过后生成询价准备被旧值 `approvalCompleted` 阻断，一个字段同时承担审批与业务生命周期含义。
- 根因：页面、Guard 与 Runtime 各自定义状态，缺少统一 State Contract。
- 解决方案：分离 `approvalStatus` 与业务生命周期状态，Guard 只读取冻结的 PurchaseRequest State Contract。
- 纳入规则：State 状态规范、`PROCESS-008`。
- 回归测试：审批通过后可生成询价准备，且两类状态分别显示。

### CASE-SCM-002：询价准备无法进入页面

- 案例编号：`CASE-SCM-002`
- 发现版本：`V1.14.2.8.18.3`
- 问题描述：采购申请显示已生成询价准备，但询价页待处理记录为 0。
- 根因：交接只验证字段映射，没有创建可被 Provider 读取的 InquiryPreparation 业务上下文。
- 解决方案：建立真实 InquiryPreparationContext、Provider 与 Source → Context → Target 交接。
- 纳入规则：Handoff 交接规范、`PROCESS-006-B`。
- 回归测试：单条与批量创建后首次加载、刷新记录数一致。

### CASE-SCM-003：页面名称未登记

- 案例编号：`CASE-SCM-003`
- 发现版本：`V1.14.2.8.18.4`
- 问题描述：询价详情或编辑页显示“页面名称未登记”。
- 根因：只登记工作台，页面族身份未完整进入统一 Registry。
- 解决方案：为工作台、详情、编辑、验收页分别登记完整 Page Contract。
- 纳入规则：页面开发模板、`PROCESS-009`。
- 回归测试：直接打开页面族任一路由均显示正确页面名称。

### CASE-SCM-004：按钮存在但无法执行

- 案例编号：`CASE-SCM-004`
- 发现版本：`V1.14.2.8.18.5`
- 问题描述：编辑按钮可见但无法进入编辑页，批量选择没有真实动作入口。
- 根因：按钮未贯通 Action Contract、Router、Target Page 与 Runtime Context。
- 解决方案：按执行链登记动作、路由、目标页、输入和可观测结果。
- 纳入规则：Action 动作规范、`PROCESS-006-A`、`PROCESS-009`。
- 回归测试：查看、编辑、批量动作从点击到目标上下文逐段断言。

### CASE-SCM-005：状态未回写

- 案例编号：`CASE-SCM-005`
- 发现版本：`V1.14.2.8.18.6`
- 问题描述：执行准备供应商报价后 Runtime 已变化，询价列表仍显示草稿。
- 根因：运行状态、业务状态和列表展示使用不同映射与事实源。
- 解决方案：分离业务状态与流程状态，由统一 State Mapping、Store 和 Provider 回写及展示。
- 纳入规则：State 状态规范、Provider 数据规范、`PROCESS-008`。
- 回归测试：动作执行后详情、列表、刷新和重开状态一致。

### CASE-SCM-006：Provider 存在但页面无数据

- 案例编号：`CASE-SCM-006`
- 发现版本：`V1.14.2.8.18.3.1`
- 问题描述：InquiryPreparation Provider 已存在，询价页面仍显示 0 条。
- 根因：Provider 读取位置与 Context 存储位置不一致，页面另有临时数据来源。
- 解决方案：Provider 读取真实 Context 集合，页面以其为唯一来源，并增加三段计数诊断。
- 纳入规则：Provider 数据规范、`PROCESS-006-B`、`PROCESS-009`。
- 回归测试：Context、Provider、Page 三个数量在首次加载与刷新后一致。

### CASE-SCM-007：关闭页面数据丢失

- 案例编号：`CASE-SCM-007`
- 发现版本：`V1.14.2.8.18.7`
- 问题描述：关闭询价页再进入时已创建询价消失，但询价准备仍存在。
- 根因：PurchaseInquiry 只保存在页面临时 state，未进入受治理 Runtime Store。
- 解决方案：建立 create/save/reload 生命周期的 Runtime Store，并统一由 Provider 恢复列表。
- 纳入规则：Provider 数据规范、一页一验收规范、`PROCESS-008`。
- 回归测试：保存后关闭重开，数据、状态与下一动作保持一致。

### CASE-SCM-008：供应商选择设计错误

- 案例编号：`CASE-SCM-008`
- 发现版本：`V1.14.2.8.18.7A`
- 问题描述：供应商候选按询价单级维护，无法表达每个物料由哪些供应商报价。
- 根因：领域模型粒度与采购决策粒度不一致。
- 解决方案：建立物料明细级 MaterialSupplierCandidateContext，供应商只能从 Supplier Master Provider 搜索、增加、删除或替换。
- 纳入规则：节点开发模板、页面开发模板、Handoff 交接规范、`PROCESS-008`。
- 回归测试：逐物料供应商决策保存、交接与重开保持一致。

### CASE-SCM-009：核价读取旧数据

- 案例编号：`CASE-SCM-009`
- 发现版本：`V1.14.2.8.18.8`
- 问题描述：询价已形成 QuotePreparationContext，核价页仍显示旧测试数据或空数据。
- 根因：核价页读取遗留 mock，未承接当前有效的报价准备事实。
- 解决方案：通过 PriceApprovalPreparationContext 承接当前 QuotePreparationContext，页面只读统一 Provider；无数据明确展示空态。
- 纳入规则：Provider 数据规范、Handoff 交接规范、`PROCESS-008`、`PROCESS-009`。
- 回归测试：核价页展示当前询价数据且不出现历史测试数据，不创建报价、比价或订单对象。

### CASE-SCM-010：审批配置页面身份未登记

- 案例编号：`CASE-SCM-010`
- 发现版本：`V1.14.2.8.18.8`
- 问题描述：打开 `/admin/approval-flow-config` 时浏览器标题显示“页面名称未登记”，不满足独立 Page Contract 要求。
- 影响页面：`PAGE-002` 审批配置页面。
- 根因：路由只登记组件，未在统一页面身份 Registry 中登记完整的 pageCode、pageName、route、moduleCode 与 businessObject。
- 解决方案：后续修复版本为审批配置页面建立并注册完整 Page Contract；本验收版本不修改业务代码。
- 对应规范：页面开发模板、`PROCESS-009`、`PROCESS-010`。
- 纳入规则：页面名称未登记必须阻断单页验收和 Golden Path 总验收。
- 回归测试：`verifyScmPurchaseGoldenPathV114288.mjs` 的 PAGE-002 页面身份断言。

### CASE-SCM-011：审批配置未形成 Approval Contract 闭环

- 案例编号：`CASE-SCM-011`
- 发现版本：`V1.14.2.8.18.8`
- 问题描述：页面可选择 1/2/3 关，但无法证明审批配置经 Approval Contract 形成审批实例、审批结果并幂等回写业务状态。
- 影响页面：`PAGE-002` 审批配置页面及采购申请审批链。
- 根因：旧 `approvalFlowConfigStore` 使用本地配置和 `getNextApprovalStatus` 直接推导状态，未声明 approvalContractCode、实例标识、审批历史与 resultWriteback。
- 解决方案：后续版本建立采购申请 Approval Contract，将配置、实例、动作、结果回写和 State Contract 分层；补充越权、驳回、重复提交与回写失败测试。
- 对应规范：Approval审批治理规范、节点开发模板、`PROCESS-008`、`PROCESS-010`。
- 纳入规则：只有关卡选择器不等于 Approval Contract 通过。
- 回归测试：`verifyScmPurchaseGoldenPathV114288.mjs` 的 Approval Contract 链断言。

### CASE-SCM-012：询价工作台流程状态显示不一致

- 案例编号：`CASE-SCM-012`
- 发现版本：`V1.14.2.8.18.8`
- 问题描述：同一询价列表行显示“已进入供应商报价准备”，页面下一动作区域仍显示“询价编辑中”，同页出现互相冲突的当前流程状态。
- 影响页面：`PAGE-004` 询价工作台。
- 根因：列表行读取持久化询价事实，下一动作区域在当前对象未选中时使用静态回退文本，未复用同一 Provider 状态事实。
- 解决方案：后续版本让当前状态区域绑定明确选中对象或显示“未选择对象”，禁止用业务状态回退值冒充当前对象事实。
- 对应规范：页面开发模板、Provider数据规范、`PROCESS-008`、`PROCESS-009`。
- 纳入规则：同页列表、详情和下一动作区域必须显示同一对象的同一状态事实。
- 回归测试：`verifyScmPurchaseGoldenPathV114288.mjs` 的 PAGE-004 状态一致性断言。

### CASE-SCM-013：询价编辑页直接展示技术状态值

- 案例编号：`CASE-SCM-013`
- 发现版本：`V1.14.2.8.18.8`
- 问题描述：询价编辑页向业务用户显示 `active`、`unclassified`、`purchase_request_suggestion` 和 `quote_preparation_ready` 等技术值。
- 影响页面：`PAGE-005` 询价编辑页面。
- 根因：供应商候选卡与流程导航直接渲染内部 code/source，没有统一使用用户可见的中文 statusLabel 和业务来源标签。
- 解决方案：后续版本在 Provider/State Mapping 输出中文标签，技术 code 仅保留于诊断区域；本验收版本不修改页面业务代码。
- 对应规范：页面开发模板、PCE-ERP开发治理总规范、`PROCESS-009`、`PROCESS-010`。
- 纳入规则：用户业务区域不得直接显示内部状态码和来源枚举。
- 回归测试：`verifyScmPurchaseGoldenPathV114288.mjs` 的 PAGE-005 用户可见文本断言。

### CASE-SCM-014：采购申请保存回归被测试库迁移阻断

- 案例编号：`CASE-SCM-014`
- 发现版本：`V1.14.2.8.18.8`
- 问题描述：采购申请创建的 Django 回归用例在创建隔离测试库时失败，错误为 `no such table: material_category`，无法签发保存能力回归通过。
- 影响页面：`PAGE-001` 采购申请页面；同时阻断 `PROCESS-008` 与 Regression。
- 根因：现有数据库迁移链在测试库中引用尚未创建的 `material_category` 表，失败发生在采购申请测试执行之前。
- 解决方案：由后续数据库治理版本修正迁移依赖顺序或测试设置；完成后重跑采购申请创建用例和完整黄金路径。本版本禁止修改数据库结构。
- 对应规范：回归测试规范、`PROCESS-008`、`PROCESS-010`。
- 纳入规则：测试未实际执行完成时不得以测试源码存在或页面已有历史数据替代 Regression PASS。
- 回归测试：`procurement.tests_v417.PurchaseRequestOrganizationRelationshipV417Tests.test_v11428818_authenticated_create_returns_complete_purchase_request_and_is_listed`。

## 3.1 V1.14.2.8.18.8.1 问题收敛修复记录

### CASE-SCM-010 修复记录：审批配置页面身份登记

- 修复版本：`V1.14.2.8.18.8.1`
- 问题描述：审批关卡配置页面缺少统一页面身份，页面顶部可能显示“页面名称未登记”。
- 根因：路由、页面组件与 `scmPageIdentityRegistry` 没有复用同一组 `pageCode/pageName/route/moduleCode/businessObject`。
- 修复方案：将 `/admin/approval-flow-config` 注册为 `approval-flow-config / 审批关卡配置 / SCM / ApprovalContract`，并让路由元数据和页面根节点声明同一身份。
- 对应治理规则：页面开发模板、`PROCESS-009`、`PROCESS-010`。
- 回归结果：`enterpriseScmPurchaseGoldenPathStabilizationV1142881.test.mjs` 页面身份断言通过；黄金路径 `PAGE-002 PASS`。

### CASE-SCM-011 修复记录：Approval Runtime 生命周期闭环

- 修复版本：`V1.14.2.8.18.8.1`
- 问题描述：原审批配置只表达关卡数量，不能证明 Contract、Instance、Action、Result 和业务状态回写闭环。
- 根因：审批状态由配置 Store 局部推导，缺少可执行的 Approval Runtime 和结果写回幂等键。
- 修复方案：建立统一 Approval Contract/Instance/Action/Result/Writeback Runtime；支持 1、2、3 关审批，并通过 `businessObjectId:approvalInstanceId:result` 语义防止重复结果写回。
- 对应治理规则：Approval审批治理规范、节点开发模板、`PROCESS-008`、`PROCESS-010`。
- 回归结果：1/2/3 关审批、重复审批与重复回写共四组自动断言通过；`Approval Lifecycle PASS`。

### CASE-SCM-012 修复记录：询价状态与下一动作统一映射

- 修复版本：`V1.14.2.8.18.8.1`
- 问题描述：询价已显示“已进入供应商报价准备”，下一动作仍显示“询价编辑中”。
- 根因：列表与下一动作区域没有消费同一 PurchaseInquiry 状态映射，未选择对象时还使用静态业务回退文本。
- 修复方案：统一 `Runtime State -> Display State -> Next Action`；`quote_preparation_ready` 固定显示“已进入供应商报价准备”，下一动作为“进入供应商报价准备”，页面只绑定当前询价的统一映射结果。
- 对应治理规则：State状态规范、Provider数据规范、页面开发模板、`PROCESS-008`、`PROCESS-009`。
- 回归结果：状态、展示和下一动作精确映射断言通过；`State And Action Mapping PASS`、`PAGE-004 PASS`。

### CASE-SCM-013 修复记录：询价业务语言展示

- 修复版本：`V1.14.2.8.18.8.1`
- 问题描述：询价编辑页直接显示 `active`、`unclassified` 和 `quote_preparation_ready` 等技术状态。
- 根因：供应商候选区和流程导航直接渲染内部代码，没有用户可见的业务标签映射。
- 修复方案：建立 Business Status Display Mapping；业务区显示“有效”“未分类”“供应商主数据”“已进入供应商报价准备”，内部代码仅保留在模型和诊断层。
- 对应治理规则：PCE-ERP开发治理总规范、页面开发模板、Provider数据规范、`PROCESS-009`、`PROCESS-010`。
- 回归结果：业务中文标签及技术值不直出断言通过；`Business Language Display PASS`、`PAGE-005 PASS`。

### CASE-SCM-014 修复记录：黄金路径测试库迁移完整性

- 修复版本：`V1.14.2.8.18.8.1`
- 问题描述：采购申请保存回归在干净测试库中先后因 `material_category`、`employee` 基础表缺失而无法执行。
- 根因：`MaterialCategory` 初始迁移声明为不受管，且 `pfm` 存在空迁移包但没有 Employee/Shift/EmployeeCertificate 初始迁移，Django 不会为该已迁移应用自动同步表。
- 修复方案：让 `material_category` 由迁移创建，并补齐 `pfm/0001_initial.py` 基础表迁移；不绕过迁移、不使用既有开发库数据。
- 对应治理规则：回归测试规范、`PROCESS-008`、`PROCESS-010`。
- 回归结果：隔离测试数据库真实执行采购申请创建、保存和列表回读用例通过；`Database Migration Integrity PASS`。

## 3.2 V1.14.2.8.18.10.3 节点页面治理案例

### CASE-SCM-016：采购流程中心节点导航映射不完整

- 案例编号：`CASE-SCM-016`
- 发现版本：`V1.14.2.8.18.10.1`
- 问题描述：流程中心仅展示粗粒度采购节点，供应商报价、报价比较和供应商推荐等已完成节点未拥有同步导航。
- 根因：流程展示模型未随节点运行框架持续同步，页面路由与节点注册分散维护。
- 解决方案：建立统一 SCM 采购流程中心注册表，节点携带前后关系、页面路由和验收档案。
- 纳入规则：页面开发模板、`PROCESS-009`、`PROCESS-011`。
- 回归测试：`verifyScmProcessCenterNavigationV11428101.mjs`。

### CASE-SCM-017：多个独立业务节点共用采购询价页面

- 案例编号：`CASE-SCM-017`
- 发现版本：`V1.14.2.8.18.10.3`
- 问题描述：询价准备、采购询价、供应商推荐和采购订单准入均映射到 `/scm/purchase-inquiry`，页面同时承担四个独立业务职责。
- 根因：节点扩展时只新增 Runtime 区域，没有同步建立独立 Page Contract、Page Identity、Route 和单页验收。
- 解决方案：拆分询价准备、采购询价、供应商推荐、采购订单准入四个主页面，建立唯一节点页面注册和 PROCESS-011 强制校验。
- 纳入规则：`NODE-PAGE-001`、`PROCESS-009`、`PROCESS-011`。
- 回归测试：`verifyScmNodePageGovernanceV11428103.mjs`。

### CASE-SCM-027：CODEX 执行命令缺少统一规范管理

- 案例编号：`CASE-SCM-027`
- 发现版本：`V1.14.2.8.18.10.3.1`
- 修复版本：`V1.14.2.8.18.10.3.1A`
- 问题描述：CODEX 任务输入格式、范围、验收标准和报告结构不统一，治理文件即使被读取也不能稳定形成检查与验收结果。
- 影响：不同版本执行口径漂移，历史问题可能重复出现，关键治理失败可能被错误签发 READY。
- 根因：缺少统一 CODEX 执行命令规范以及“规范 → 检查项 → 验收结果”的强制链路。
- 解决方案：建立《CODEX执行命令规范.md》，接入治理总规范与符合性检查矩阵，并以自动验收和非零退出码实施失败阻断。
- 纳入规则：`PROCESS-010`、`CODEX-COMMAND-001`。
- 回归测试：`verifyCodexCommandGovernanceV114281031A.mjs`。

### CASE-SCM-024：审批配置页面错误作为业务节点页面

- 案例编号：`CASE-SCM-024`
- 发现版本：`V1.14.2.8.18.10.3.1`
- 修复版本：`V1.14.2.8.18.10.3.2`
- 问题描述：流程中心“审批”节点跳转审批规则配置页，系统配置与业务执行语义混淆。
- 根因：节点页面映射把 `purchase-approval` 绑定到 `approval-flow-config`。
- 解决方案：新增 `/scm/purchase-approvals` 审批实例执行页，配置页仅维护规则。
- 纳入规则：`NODE-PAGE-001`、`PAGE-IDENTITY`、`PROCESS-009`。
- 回归测试：`enterpriseBusinessNameApprovalBindingV114281032.test.mjs`。

### CASE-SCM-025：审批配置与实际审批运行不一致

- 案例编号：`CASE-SCM-025`
- 发现版本：`V1.14.2.8.18.10.3.1`
- 修复版本：`V1.14.2.8.18.10.3.2`
- 问题描述：配置可选择 1/2/3 关，但实际运行缺少 Policy 和 Task 绑定证据。
- 根因：Approval Contract、Instance 和配置之间没有显式绑定对象。
- 解决方案：建立 `APPROVAL-RUNTIME-001`，配置生成 Policy，Policy 生成同数量 Task，最终 Result 幂等回写。
- 纳入规则：`APPROVAL-RUNTIME-001`、`PROCESS-010`。
- 回归测试：1/2/3 关 Configuration→Writeback 自动测试。

### CASE-SCM-026：流程中心、页面和标题名称不一致

- 案例编号：`CASE-SCM-026`
- 发现版本：`V1.14.2.8.18.10.3.1`
- 修复版本：`V1.14.2.8.18.10.3.2`
- 问题描述：询价/采购询价、质量检验/来料检验、库存余额/入库等名称由多处独立定义。
- 根因：流程、页面身份、页面契约和标题服务没有共同事实源。
- 解决方案：建立 `BusinessNameRegistry`，统一流程名称、页面标题、业务对象名称及路由标题。
- 纳入规则：`NAME-GOV-001`、`PAGE-IDENTITY`、`PROCESS-010`。
- 回归测试：`verifyBusinessNameApprovalBindingV114281032.mjs`。

### CASE-SCM-028：业务名称治理覆盖不足

- 案例编号：`CASE-SCM-028`
- 发现版本：`V1.14.2.8.18.10.3.3`
- 修复版本：`V1.14.2.8.18.10.3.3`
- 问题描述：原 BusinessNameRegistry 仅登记 14 个采购相关页面，PDE、Finance、询价页面族及部分 SCM/WMS/QMS 页面仍依赖流程常量或旧页面目录名称。
- 影响：同一业务路由可能在流程中心、页面身份、页面顶部和浏览器标题出现不同名称，未登记页面继续落入旧标题回退。
- 根因：`NAME-GOV-001` 只验证已登记记录的一致性，没有验证所有已发现业务页面是否被 Registry 覆盖。
- 解决方案：新增 `NAME-GOV-002` 和全局覆盖扫描器，将 Process Registry、Page Identity Registry、页面目录与标题生成器联合扫描；Registry 扩展到 84 个唯一业务路由并补齐 `pageName/browserTitle`。
- 纳入规则：`NAME-GOV-001`、`NAME-GOV-002`、`PAGE-IDENTITY`、`PROCESS-009`、`PROCESS-010`。
- 回归测试：`verifyBusinessNameConsistencyGovernanceV114281033.mjs`；完整来源报告 `frontend/business_name_source_report_v114281033.json`。

### CASE-SCM-029：名称已注册但页面组件未消费统一名称源

- 案例编号：`CASE-SCM-029`
- 发现版本：`V1.14.2.8.18.10.3.4`
- 修复版本：`V1.14.2.8.18.10.3.4`
- 问题描述：BusinessNameRegistry、流程中心和浏览器标题已统一，但部分页面 Header 或内部主题仍显示组件固定名称，例如入库页面内部仍出现“库存余额”。
- 根因：NAME-GOV-001/002 只约束名称登记和路由覆盖，公共页面壳仍允许局部 pageName 优先，业务组件也可以固定 `<h1>`、内部主题或直接写 `document.title`。
- 解决方案：建立 `resolvePageNameConsumption` 与 `PceBusinessNameConsumer`，公共页面壳以 Registry 为首选并使用原始 browserTitle；扫描全部已登记业务组件的固定 H1、固定内部主题和直接标题写入。
- 对应规范：`NAME-GOV-001`、`NAME-GOV-002`、`NAME-GOV-003`、`PAGE-IDENTITY`、`PROCESS-009`、`PROCESS-010`。
- 回归测试：`verifyPageNameConsumptionGovernanceV114281034.mjs`；报告 `frontend/page_name_consumer_report_v114281034.json`。

### CASE-SCM-030：页面壳标题未消费统一名称源

- 案例编号：`CASE-SCM-030`
- 发现版本：`V1.14.2.8.18.10.3.5`
- 修复版本：`V1.14.2.8.18.10.3.5`
- 问题描述：内容区 Header 与 Browser Title 已显示 Registry 名称，但 PCE Enterprise Page V2 共享壳仍可通过 `governedPage.pageName`、旧 canonical service 或 `fallbackTitle` 显示另一名称；例如壳层可能显示“库存余额”，内容区显示“入库”。
- 影响：共享页面壳身份区、壳层 Header、内容 Header 与浏览器标题不能形成最终一致性，未登记名称也可能被旧值掩盖。
- 根因：NAME-GOV-003 约束了页面组件消费，但公共壳仍保留多级名称回退，Router 包装层也继续注入局部标题。
- 解决方案：建立 `NAME-GOV-004`；PceListPageShell 的页面名、模块名、业务对象名与浏览器标题仅消费 `resolvePageNameConsumption`，移除 `fallbackTitle`、旧 canonical service 和 Page Contract 名称回退；未登记时明确失败。
- 纳入规则：`NAME-GOV-001`、`NAME-GOV-002`、`NAME-GOV-003`、`NAME-GOV-004`、`PAGE-TEMPLATE`、`PROCESS-009`、`PROCESS-010`。
- 回归结果：九个抽查页面的流程中心、Registry、壳层 Header、内容 Header 与 Browser Title 一致；壳层固定名称与回退字段扫描为零，`verifyPageShellNameGovernanceV114281035.mjs` 通过。

### CASE-WMS-001：应用壳绕过统一名称源显示旧页面名称

- 案例编号：`CASE-WMS-001`
- 发现版本：`V1.14.2.8.18.10.3.5.1`
- 问题描述：访问 `/wms/inventory-balances` 时，Browser Title、PceListPageShell 与 WmsPage 内容 Header 均显示“入库”，但最外层 ProfitCockpit 顶部显示“库存余额”。
- 影响：同一页面出现应用壳与页面壳名称不一致，用户无法确认统一页面身份。
- 根因：目标路由硬编码 `meta.title: '库存余额'`，ProfitCockpit 在导航未命中时直接消费 `route.meta.title`，该应用壳未纳入 NAME-GOV-004 的自动扫描。
- 解决方案：后续修复版本让 ProfitCockpit 消费 BusinessNameRegistry，移除 route meta 与 WmsPage 的页面名称回退，并建立应用壳/页面壳/内容/浏览器四端集成门禁。
- 纳入规则：`NAME-GOV-001`、`NAME-GOV-002`、`NAME-GOV-003`、`NAME-GOV-004`、建议新增 `PAGE-SHELL-001`、`PROCESS-010`。
- 回归测试：待修复版本增加运行态断言；本版本诊断入口为 `verifyWmsInventoryBalanceNameTraceV1142810351.mjs`，当前预期输出 Name Source Trace FAIL 与 Hardcoded Source Scan FAIL。

## 3.3 V1.14.2.8.18.10.3.3 名称治理闭环记录

- `CASE-SCM-023`：治理规则已映射为 NAME-GOV-002 可执行全局门禁，缺少路由覆盖或名称证据时以非零退出码阻断，回归 PASS。
- `CASE-SCM-026`：流程、页面身份、顶部名称和浏览器标题统一消费 BusinessNameRegistry，回归 PASS。
- `CASE-SCM-028`：84 个唯一业务路由、127 条来源记录完成覆盖扫描；CRM/MES 当前无可访问登记页，保留零页面扫描证据，回归 PASS。
- `CASE-SCM-029`：45 个已登记业务页面组件固定 H1、固定内部主题及页面直接标题写入均为 0；九个抽查页面四端一致，回归 PASS。
- `CASE-SCM-030`：共享页面壳名称回退已清零；九个抽查页面五端一致，未登记名称显式失败，回归 PASS。

## 4. 变更记录

| 版本 | 变更 | 规则来源 |
| --- | --- | --- |
| 1.4 | 补录 CASE-SCM-016，并新增 CASE-SCM-017 节点共用页面治理案例 | V1.14.2.8.18.10.3 |
| 1.5 | 新增 CASE-SCM-027，建立 CODEX 执行命令统一治理与失败阻断 | V1.14.2.8.18.10.3.1A |
| 1.6 | 新增 CASE-SCM-024～026，治理审批页面语义、运行绑定和业务名称唯一来源 | V1.14.2.8.18.10.3.2 |
| 1.7 | 新增 CASE-SCM-028，并闭环 CASE-SCM-023/026 的全局名称覆盖门禁 | V1.14.2.8.18.10.3.3 |
| 1.8 | 新增 CASE-SCM-029，建立统一页面名称消费与硬编码扫描门禁 | V1.14.2.8.18.10.3.4 |
| 1.9 | 新增 CASE-SCM-030，建立共享页面壳名称唯一消费与最终一致性门禁 | V1.14.2.8.18.10.3.5 |
| 2.0 | 新增 CASE-WMS-001，记录最外层应用壳仍消费 route.meta.title 的名称旁路 | V1.14.2.8.18.10.3.5.1 |

## V1.14.2.8.18.10.3.6 名称问题收敛

### CASE-SCM-028 / CASE-SCM-029 / CASE-SCM-030 关闭记录

- 修复版本：`V1.14.2.8.18.10.3.6`
- 根因收敛：Registry 覆盖、页面组件消费与共享壳消费此前分阶段治理，Router 和局部回退仍可形成第二名称源。
- 修复方案：Router 删除业务标题；流程中心、页面壳、内容 Header 与 Browser Title 统一消费 `BusinessNameRegistry`；新增静态扫描和运行名称断言。
- 对应治理规则：`NAME-GOV-001` 至 `NAME-GOV-006`、`PROCESS-009`、`PROCESS-010`。
- 回归结果：由 `verifyBusinessNameSingleSourceV114281036.mjs` 强制判定。

### CASE-WMS-001：入库页面多名称来源（关闭）

- 修复版本：`V1.14.2.8.18.10.3.6`
- 问题描述：`/wms/inventory-balances` 同时出现“库存余额”和“入库”。
- 根因：Router `meta.title`、应用壳回退、模块 Registry 原始 `canonicalName` 与 WMS 页面 `currentList.title`/canonical service 回退绕过统一 Registry。
- 修复方案：删除 Router 标题与模块原始别名；ProfitCockpit、WMS 内容 Header 和 Browser Title 均直接消费 `BusinessNameRegistry`。
- 对应治理规则：`NAME-GOV-004`、`NAME-GOV-005`、`NAME-GOV-006`、`PAGE-SHELL-001`、`PROCESS-009`。
- 回归结果：静态第二来源扫描、九页运行名称断言、回归与 Build 全部通过后关闭。

| 2.1 | 关闭 CASE-SCM-028/029/030 与 CASE-WMS-001，建立 NAME-GOV-005/006 强制门禁 | V1.14.2.8.18.10.3.6 |
| 1.3 | 收敛修复 CASE-SCM-010 至 CASE-SCM-014，并补齐页面身份、Approval Runtime、状态映射、业务语言及测试库迁移回归证据 | V1.14.2.8.18.8.1 |
| 1.2 | 收录采购申请保存回归的测试库迁移阻断 | V1.14.2.8.18.8 |
| 1.1 | 收录 PAGE-002/004/005 黄金路径治理问题 | V1.14.2.8.18.8 |
| 1.0 | 收录 9 个 SCM 采购真实问题案例 | V1.14.2.8.18.7 |
## CASE-SCM-023 治理文件已加载但没有强制门禁

- 发现版本：V1.14.2.8.18.10.3
- 修复版本：V1.14.2.8.18.10.3.1
- 问题描述：验收只确认治理文件存在，页面名称、Page V2 结构和企业列表能力缺失时仍可能输出 PASS。
- 影响页面：SCM 采购黄金路径 PAGE-001～PAGE-009。
- 根因：治理规则没有映射为可执行检查项，也没有绑定页面级 DOM、组件契约、路由与验收记录证据。
- 修复方案：新增治理符合性检查矩阵和失败阻断执行器；九页逐项执行规则、检查、证据、结果四联门禁，并加入反向失败测试。
- 纳入规则：PROCESS-010、PAGE Governance、NODE-PAGE-001、PROCESS-011、PROCESS-009。
- 回归结果：Governance Compliance Matrix、九页门禁、Regression、Build 全部通过。

### CASE-SCM-031：自动验收通过但人工验收发现问题未回流机制

- 案例编号：`CASE-SCM-031`
- 发现版本：`V1.14.2.8.18.10.3.x`
- 修复版本：`V1.14.2.8.18.10.3.6A`
- 问题描述：自动验收报告为 PASS，但人工页面验证发现真实问题后，任务仍可能沿用自动结果进入 READY。
- 影响：问题未进入诊断、案例、规范和回归闭环，错误 READY 可能进入发布或后续开发基线。
- 根因：自动验收与人工验收是两套记录，缺少人工结果反向降级最终状态并触发问题回流的统一机制。
- 解决方案：建立 `CODEX-COMMAND-002`；定义 `AUTO_PASS_HUMAN_FAIL`，强制执行诊断版本、根因定位、规范判断、案例更新、自动验收补强、重新验收与人工复验。
- 对应规范：`CODEX-COMMAND-002`、`PROCESS-009`、`PROCESS-010`。
- 回归测试：`verifyCodexHumanFeedbackGovernanceV114281036A.mjs` 必须证明自动 PASS + 人工 FAIL 无 READY 资格，并证明人工反馈关闭后才能恢复 READY 资格。

| 2.2 | 新增 CASE-SCM-031，建立人工验收反向校验与 AUTO_PASS_HUMAN_FAIL 阻断机制 | V1.14.2.8.18.10.3.6A |

### CASE-SCM-032：开发动作先于规范归档导致治理遗漏

- 案例编号：`CASE-SCM-032`
- 发现版本：`V1.14.2.8.18.10.3.6B`
- 修复版本：`V1.14.2.8.18.10.3.6B`
- 问题描述：发现经验或业务问题后直接进入开发，未优先完成规范归档、治理评估及验收规则更新。
- 影响：开发实现可能遗漏跨模块治理约束，规范、验收矩阵和问题案例无法及时保护后续版本。
- 根因：缺少规范先行门禁，CODEX 任务生成和开发实施没有以前置治理证据为准入条件。
- 解决方案：建立 `GOV-001` 规范先行开发原则，并由 `CODEX-COMMAND-003` 在开发前检查规范覆盖、规范补充、案例库更新和验收矩阵更新；任一必需项未完成即阻断开发。
- 对应规范：`GOV-001`、`CODEX-COMMAND-003`、`PROCESS-010`。
- 回归结果：由 `verifyGovernanceFirstDevelopmentV114281036B.mjs` 执行正向与反向门禁、文档归档、旧治理规则回归及 Build 检查。

| 2.3 | 新增 CASE-SCM-032，建立 GOV-001 与 CODEX-COMMAND-003 规范先行开发门禁 | V1.14.2.8.18.10.3.6B |
| 2.4 | 新增 CASE-GOV-002，建立 PROCESS-011 流程节点真实运行四层门禁 | V1.14.2.8.18.16.2 |
### CASE-SCM-033：业务列表重复建设导致筛选、操作列和宽表行为不一致

- 案例编号：`CASE-SCM-033`
- 发现版本：`V1.14.2.8.18.12.1`
- 修复版本：`V1.14.2.8.18.13`
- 问题描述：供应商报价、报价比较和采购核价页面暴露出筛选下拉缺失、操作列来源不统一、宽表滚动不稳定及页面横向溢出。
- 影响：相同列表能力在不同页面表现不一致，页面局部修复无法保护后续模块。
- 根因：公共列表契约只有能力声明，缺少筛选选项来源归一化、Action Contract 操作列解析和可执行页面宽度规则。
- 解决方案：建立 `LIST-RUNTIME-001`，新增 List Filter Runtime、Action Column Runtime 和统一表格/页面容器规则，并以 SCM 三页作为回归样本。
- 对应规范：`GOV-001`、`LIST-RUNTIME-001`、`PROCESS-009`、`PROCESS-010`。
- 回归脚本：`verifyUnifiedListRuntimeV1142813.mjs`。

#### 第二阶段关闭记录

- 修复版本：`V1.14.2.8.18.13.1`
- 补充根因：第一阶段完成公共解析器后，采购询价仍保留硬编码操作插槽，四个 SCM 列表也未统一声明 `filterFields/optionsProvider`。
- 收敛方案：新增 `LIST-RUNTIME-002`、`ListContainer Runtime` 与 `UnifiedFilterSchema`，四页统一通过 Action Contract 和声明式筛选接入。
- 回归脚本：`verifyListRuntimeGovernanceV11428131.mjs`。

#### 宽表几何验收补强记录

- 补强版本：`V1.14.2.8.18.13.2`
- 人工反馈：采购询价、供应商报价、报价比较和采购核价仍可能出现浏览器被撑宽、底部滚动条不可见及固定操作列异常。
- 复用根因：仍属于公共列表滚动契约与自动验收不足，不新增重复案例。
- 收敛方案：建立 `TABLE-SCROLL-RUNTIME-001`、`LIST-WIDTH-POLICY-001` 和 `HORIZONTAL-SCROLL-VISIBLE-CHECK`；用真实 `scrollWidth/clientWidth` 几何事实替代仅扫描 CSS 字符串。
- 回归脚本：`verifyTableScrollRuntimeV11428132.mjs`。

#### 真实 DOM 渲染修复记录

- 修复版本：`V1.14.2.8.18.13.3`
- 人工失败事实：自动几何测试通过，但真实页面仍被撑宽、滚动条不可见且操作列被截断。
- 根因：`PceEnterpriseListTable` 将 Element Plus 实际横向视口强制设为 `overflow-x:hidden`，同时外层内容以 1600px 最小宽度参与页面布局，形成错误的双层滚动模型。
- 修复：倒置公共组件根结构为 `BusinessTableScrollContainer → PceEnterpriseListTable → el-table`；外层内容恢复 `min-width:0`，最小宽度只作用于真实 table，Element Plus 实际视口恢复横向滚动。
- 验收入口：`verifyTableScrollVisualV11428133.mjs`；没有四页浏览器真实几何证据时必须 FAIL。

#### 报价比较动态列链路收敛记录

- 修复版本：`V1.14.2.8.18.13.4`
- 人工失败事实：报价比较页面仍可被动态供应商列撑宽，内部横向滚动条不可见，而其他统一列表正常。
- 根因：公共页面壳的普通插槽缺少可收缩 `ListContainer`；报价比较又将供应商固定投影为 A/B/C，未通过统一列运行层计算真实动态宽度。
- 收敛方案：公共 `PceListPageShell` 接入 `LIST-RUNTIME-002` 内容容器；建立通用 `pceTableColumnRuntime`；报价比较按真实供应商数量声明动态列组，继续由 `BusinessTableScrollContainer` 唯一拥有滚动。
- 治理判断：复用 `CASE-SCM-033`、`LIST-RUNTIME-002`、`TABLE-SCROLL-RUNTIME-001`，不新增页面私有滚动规则或重复案例。
- 验收入口：`verifyQuoteComparisonScrollVisualV11428134.mjs`；真实浏览器几何证据未通过时禁止 READY。
## CASE-SCM-034 列表筛选与核价参考能力不足

- 发现版本：V1.14.2.8.18.12.1 人工验收
- 问题描述：宽表滚动体验不稳定，编号字段仍为纯文本，高级筛选缺少远程选择和批量筛选，核价缺少老物料历史价格参考。
- 根因：统一列表第二阶段只固化了基础筛选与容器，没有覆盖编号选项 Provider、选择集筛选和只读历史价格投影。
- 解决方案：建立 LIST-RUNTIME-002、LIST-FILTER-002、Batch Filter Runtime 与 Price Reference Context。
- 纳入规则：LIST-RUNTIME-002、LIST-FILTER-002、PRICE-REFERENCE-001、PROCESS-010。
- 回归要求：采购询价、供应商报价、报价比较、核价准备与 Build 必须同时通过。

## CASE-SCM-035 新旧物料核价使用同一历史价格摘要

- 案例编号：`CASE-SCM-035`
- 发现版本：`V1.14.2.8.18.15`
- 问题描述：核价参考仅投影最近采购价，无法区分无采购历史的新物料与有采购历史的老物料，也未提供历史最低价、采购次数和逐笔价格证据。
- 根因：`PriceReferenceContext` 以当前报价供应商过滤历史并输出单条摘要，缺少物料级历史识别、分型上下文和证据模型。
- 解决方案：建立 `MaterialPriceContextType`、`MaterialPriceContext`、`NewMaterialPriceAssessmentContext` 与 `PriceChangeEvidence`；历史识别改为物料维度，页面增加只读价格参考区域。
- 对应规范：`MATERIAL-PRICE-CONTEXT-001`、`PRICE-REFERENCE-001`、`PROCESS-008`、`PROCESS-009`、`PROCESS-010`。
- 回归测试：`verifyMaterialPriceContextV1142815.mjs` 必须覆盖新旧物料、价格证据、人工决策边界、SupplierQuote/QuoteComparison/PriceApproval 兼容与 Build。

## CASE-SCM-036 核价增强后公共页面视觉与空列表回归

- 案例编号：`CASE-SCM-036`
- 发现版本：`V1.14.2.8.18.15.1`
- 问题描述：人工验收发现业务流程中心标题被页签挤压，供应商报价与报价比较在零数据时完全卸载企业列表；采购询价虽仍挂载列表，但服务端事实为零，容易被误判为列表消失。
- 根因：上一版本验收只覆盖核价模型夹具和静态兼容性，没有覆盖五个真实路由的零数据渲染；两个工作台使用页面级 `v-if/v-else` 以记录数决定是否挂载列表；流程中心标题区缺少抗压缩约束。旧流程验收脚本还使用已被 `BusinessNameRegistry` 替换的历史节点名称，形成验收漂移。
- 解决方案：建立 `SCM-REGRESSION-ISOLATION-001`；流程中心仅增加页面局部标题布局约束；供应商报价和报价比较始终挂载统一企业列表并由列表显示空状态；不生成模拟业务数据；核价模型继续仅在采购核价只读区域消费；同步纠正验收脚本的名称与组件拆分识别。
- 对应规范：`PROCESS-008`、`PROCESS-009`、`PROCESS-010`、`LIST-RUNTIME-001`、`LIST-RUNTIME-002`、`MATERIAL-PRICE-CONTEXT-001`、`SCM-REGRESSION-ISOLATION-001`。
- 回归测试：`verifyV11428151RegressionRecovery.mjs` 必须覆盖治理文件、流程中心视觉契约、三张上游列表、采购核价、模型隔离、零业务写入与 Build。

## CASE-GOV-001 业务增强误修改公共层导致系统回归

- 案例编号：`CASE-GOV-001`
- 案例名称：业务增强误修改公共层导致系统回归
- 发现版本：`V1.14.2.8.18.15`
- 问题描述：SCM 新旧物料核价与价格参考增强过程中，业务增强边界未充分隔离公共展示层，人工验收发现流程中心展示及既有 SCM 页面发生回归。
- 影响范围：业务流程中心、采购询价、供应商报价、报价比较。
- 问题归类：开发边界治理问题；不是业务模型问题，也不是页面功能不足问题。
- 根因：业务增强任务没有在实施前强制区分业务专属层与公共能力，也没有对 List Runtime、Page Shell、Process Center 和公共组件执行前置治理评估及公共消费者回归。
- 解决方案：建立《业务增强版本修改边界规范.md》和 `BUSINESS-ENHANCEMENT-BOUNDARY-001`；业务增强仅直接修改业务模型、兼容 Provider 与目标页面业务区域；公共能力变更必须先完成治理评估、影响分析、自动回归和真实页面验收。
- 对应规范：`GOV-001`、`PROCESS-008`、`PROCESS-010`、`CODEX-COMMAND-004`、`BUSINESS-ENHANCEMENT-BOUNDARY-001`。
- 回归测试：`verifyBusinessEnhancementBoundaryGovernanceV11428152.mjs` 必须检查新规范、总规范引用、CODEX 命令门禁、案例、治理矩阵、既有回归与 Build。

## CASE-SCM-037 核价进入供应商推荐仅跳路由且生产读取测试事实

- 案例编号：`CASE-SCM-037`
- 发现版本：`V1.14.2.8.18.16` 人工验收
- 修复版本：`V1.14.2.8.18.16.1`
- 问题描述：采购核价点击“进入供应商推荐”只执行页面跳转，没有传递 priceApprovalId、quoteComparisonId、物料、候选供应商及价格证据；供应商推荐页面在 Demo 模式直接读取验收事实，生产链没有 PriceApproval 真实上下文优先源；人工候选确认与当前核价事实未形成同一 Decision 链。
- 影响范围：采购核价、供应商推荐决策、PurchaseOrderGate 前置交接。
- 根因：页面动作把路由导航误当作业务 Handoff；SupplierRecommendationDecisionProvider 包装旧 QuoteComparison Provider，但没有核价 Handoff Store 和真实事实优先级；验收只验证推荐页面内部演示流程，没有从采购核价入口执行双页真实链路。
- 解决方案：建立 `BUSINESS-HANDOFF-REAL-001`；核价动作先持久生成 `PriceApprovalSupplierRecommendationHandoff` 再导航；推荐 Provider 按 PriceApproval Handoff → QuoteComparison Runtime → Demo/Acceptance（仅显式模式）的顺序取数；人工确认生成与 Handoff 来源绑定的 `SupplierRecommendationDecision`，确认后只进入 PurchaseOrderGate。
- 对应规范：`GOV-001`、`PROCESS-008`、`PROCESS-009`、`PROCESS-010`、`CODEX-COMMAND-002`、`BUSINESS-ENHANCEMENT-BOUNDARY-001`、`BUSINESS-HANDOFF-REAL-001`。
- 回归测试：`verifySupplierRecommendationRealHandoffV11428161.mjs` 必须覆盖 PriceApproval 输入、QuoteComparison 上下文、真实 Provider、生产 Demo 隔离、候选绑定、人工 Decision、PurchaseOrder 隔离、既有回归与 Build，并执行采购核价到推荐页面的人工复验。

## CASE-SCM-038 资格证据待核验导致真实候选被自动禁选

- 案例编号：`CASE-SCM-038`
- 发现版本：`V1.14.2.8.18.16.1` 浏览器反向验收
- 问题描述：采购核价真实交接成功后，报价比较候选供应商因供应商主数据缺少资格档案而显示“资格待核验”，页面与领域校验同时禁止采购人员选择，人工确认链被阻断。
- 根因：资格证据被错误提升为自动决策门禁；页面禁用选项和 Domain 的 `qualificationStatus === qualified` 校验共同构成系统自动拒绝，与“系统提供证据、采购人员最终决策”边界冲突。
- 解决方案：保留资格状态只读展示和 Decision 审计快照；候选有效性仅校验其确实来自当前 QuoteComparison，允许采购人员选择待核验或受限候选，但必须填写推荐理由和确认人。
- 对应规范：`PROCESS-008`、`BUSINESS-HANDOFF-REAL-001`、`BUSINESS-EVIDENCE-MANUAL-001`。
- 回归测试：`verifySupplierRecommendationRealHandoffV11428161.mjs` 必须包含未验证资格候选仍可通过显式人工理由生成 Decision 的正向场景，并继续证明不存在自动推荐或采购订单写入。

## CASE-SCM-039 推荐已形成 Gate Handoff 但采购订单准入页面列表为空

- 案例编号：`CASE-SCM-039`
- 发现版本：`V1.14.2.8.18.16.1` 浏览器反向验收
- 问题描述：供应商推荐完成显式人工确认并形成 `handoff_ready` 后可以进入采购订单准入路由，但准入页面仅读取旧 Gate Runtime，上游 `SupplierRecommendationPurchaseOrderGateHandoff` 未被页面 Provider 消费，列表显示 0 条。
- 根因：推荐侧输出契约和 Gate 页面输入 Provider 未形成同一事实链；自动验收只检查 Handoff 对象存在和未创建采购订单，没有断言目标页面可见消费。
- 解决方案：新增采购订单准入业务 Provider，合并旧 Gate Runtime 事实与推荐 Handoff 只读投影；页面展示“推荐交接已就绪”，不自动执行准入检查、不创建 Gate Decision 或 PurchaseOrder。
- 对应规范：`BUSINESS-HANDOFF-REAL-001`、`PROCESS-008`、`PROCESS-009`、`PROCESS-010`。
- 回归测试：`verifySupplierRecommendationRealHandoffV11428161.mjs` 必须断言 Gate Provider 可见 Handoff，并通过浏览器确认进入准入页后存在当前推荐交接记录且采购订单仍未创建。

## CASE-GOV-002 流程节点存在但业务链未闭环

- 案例编号：`CASE-GOV-002`
- 案例名称：流程节点存在但业务链未闭环
- 发现版本：`V1.14.2.8.18.16`
- 问题描述：供应商推荐节点已有对象、页面和 Provider，但未正确承接采购核价真实数据，导致自动验收通过而真实人工业务失败。
- 根因：缺少流程节点真实运行验收标准；节点页面映射和 Provider 文件存在被误当作业务运行闭环。
- 解决方案：在 `V1.14.2.8.18.16.2` 建立《流程节点真实运行验收规范.md》，将 PROCESS-011 定义为对象存在、页面存在、数据真实承接、人工动作闭环四层门禁，并同步总规范、CODEX 规则、一页一验收和治理矩阵。
- 对应规范：`PROCESS-009`、`PROCESS-010`、`PROCESS-011`、`CODEX-COMMAND-002`、`CODEX-COMMAND-003`。
- 回归测试：后续流程节点验收脚本必须逐项输出四层结果；缺少真实数据或人工动作证据时 PROCESS-011 必须失败。

## CASE-SCM-040 推荐交接存在但完整审计字段未贯通到 PurchaseOrderGate

- 案例编号：`CASE-SCM-040`
- 发现版本：`V1.14.2.8.18.16.2`
- 问题描述：核价到供应商推荐的 Handoff 已存在，但未独立承接 `priceApprovalNo`；`PurchaseOrderGate` 页面也未显式展示推荐供应商、推荐依据、确认人和确认时间，对象存在但真实运行闭环证据不完整。
- 根因：上一版验收聚焦 Handoff 建立与 Gate 可见，没有按 PROCESS-011 将业务编号和人工确认审计字段作为跨节点硬契约。
- 解决方案：在 `SupplierRecommendationDecisionPreparationContext`、`SupplierRecommendationDecision` 与 Gate Handoff 中贯通 `priceApprovalNo`；Gate Provider 只读投影推荐依据和人工确认审计字段，页面明确展示且仍不创建 PurchaseOrder。
- 对应规范：`PROCESS-008`、`PROCESS-009`、`PROCESS-010`、`PROCESS-011`、`BUSINESS-HANDOFF-REAL-001`。
- 回归测试：`verifySupplierRecommendationRuntimePathV11428162.mjs` 必须同时验证真实核价入口、完整 Handoff、生产 Demo 隔离、人工 Decision、Gate 审计字段、PROCESS-011、公共层回归与 Build。

## CASE-SCM-041 同一核价单多物料时供应商推荐入口命中错误实例

- 案例编号：`CASE-SCM-041`
- 发现版本：`V1.14.2.8.18.16.3`
- 问题描述：采购核价进入供应商推荐时路由只携带 `priceApprovalId`，推荐页也只按该字段查找。同一核价单存在多物料时，点击物料 A 可能显示物料 B 的推荐上下文。
- 根因：入口身份仅使用父单级编号，没有以 `priceApprovalId + quoteComparisonId + materialCode` 形成唯一业务实例键；页面还允许手动切换到非入口记录。
- 解决方案：建立 `SupplierRecommendationRuntimeContext` 和复合 `entryKey`；核价路由携带三项唯一键，推荐页必须精确命中唯一记录并锁定实例，零命中或多命中均显式失败。
- 对应规范：`PROCESS-008`、`PROCESS-009`、`PROCESS-010`、`PROCESS-011`、`BUSINESS-HANDOFF-REAL-001`、`BUSINESS-ENHANCEMENT-BOUNDARY-001`。
- 回归测试：`verifySupplierRecommendationEntryConsistencyV11428163.mjs` 必须覆盖同核价单多物料的正确命中、缺失键、重复键、路由上下文、页面数据、Demo 隔离、人工 Decision、Gate 交接、公共层回归与 Build。

## CASE-SCM-042 批量核价与流程中心入口无法恢复独立推荐任务

- 案例编号：`CASE-SCM-042`
- 发现版本：`V1.14.2.8.18.16.4`
- 问题描述：采购核价列表仅支持单条进入供应商推荐；多选核价记录不能形成批次任务。同一询价的多物料缺少独立推荐上下文，不同询价也没有拆分规则。从流程中心直接进入推荐页时，路由没有 `RuntimeContextId`，页面无法恢复已经持久化的真实任务，人工选择、填写、确认与 Gate 交接不能稳定闭环。
- 根因：核价交接只建立单实例复合键，没有批次编排模型；推荐页面初始化只接受完整复合业务键，没有以持久化运行上下文编号作为任务恢复入口；核价业务行还缺少唯一 `id`，公共表格默认行键使第二次选择覆盖第一次选择。
- 解决方案：建立 `SupplierRecommendationBatchContext`，同一询价组成一个批次但每个物料分别执行真实 Handoff、分别保存 `SupplierRecommendationRuntimeContext`；不同询价拆分为多个批次。核价页按核价、报价比较、物料、供应商生成业务唯一行键。推荐页优先按 `RuntimeContextId` 精确加载，从无参数流程入口进入时只允许恢复最近的真实核价上下文并将 URL 规范化为带 `RuntimeContextId` 的入口；无真实上下文时显示明确失败，不加载 Demo 事实。人工确认继续逐物料生成独立 `SupplierRecommendationDecision`，只向 `PurchaseOrderGate` 交接，不创建采购订单。
- 对应规范：`PROCESS-008`、`PROCESS-009`、`PROCESS-010`、`PROCESS-011`、`BUSINESS-HANDOFF-REAL-001`、`BUSINESS-ENHANCEMENT-BOUNDARY-001`。
- 回归测试：`verifySupplierRecommendationBatchAndActionV11428164.mjs` 必须覆盖单条入口、批量拆分、流程中心上下文、任务恢复、候选动作、证据展示、人工确认、Decision、Gate、PROCESS-011、公共层回归与 Build。

## CASE-SCM-043 批量任务对象承载推荐业务事实导致实例混合

- 案例编号：`CASE-SCM-043`
- 发现版本：`V1.14.2.8.18.16.5`
- 问题描述：批量核价已能生成多个运行上下文，但 `SupplierRecommendationBatchContext` 同时保存物料、报价比较、供应商候选和 RuntimeContext 列表，页面直接消费该聚合对象时存在把多个核价记录展示成一个推荐实例的风险，批量任务与单任务业务上下文职责未隔离。
- 根因：批次管理对象和推荐决策业务对象缺少硬边界；批次对象承担了业务事实聚合，页面没有以单一 `RuntimeContextId` 作为唯一业务上下文，并缺少“一个页面实例只能有一个物料”的运行门禁。
- 解决方案：将 `SupplierRecommendationBatchContext` 收敛为只包含 `batchId`、`sourcePriceApprovalIds`、`taskCount` 的任务管理对象；另建批次任务索引，每个任务仅引用一个由 `priceApprovalId + quoteComparisonId + materialCode` 唯一确定的 `SupplierRecommendationRuntimeContext`。页面批次区域只展示任务列表，业务区始终按当前任务的 `RuntimeContextId` 加载单物料、单报价比较、候选、报价和历史价格；发现多物料时阻断人工动作。候选选择、理由、确认人、确认时间、confirmed Decision 与 Gate Handoff 继续逐任务闭环，禁止创建采购订单。
- 对应规范：`PROCESS-008`、`PROCESS-009`、`PROCESS-010`、`PROCESS-011`、`BUSINESS-HANDOFF-REAL-001`、`BUSINESS-ENHANCEMENT-BOUNDARY-001`。
- 回归测试：`verifySupplierRecommendationBatchSplitV11428165.mjs` 必须覆盖批次对象职责、任务逐条拆分、单实例、物料与报价比较隔离、候选人工动作、Decision、Gate、PROCESS-011、既有回归与 Build。

## CASE-SCM-044 候选动作未形成当前推荐对象且流程节点入口缺失运行上下文

- 案例编号：`CASE-SCM-044`
- 发现版本：`V1.14.2.8.18.16.6`
- 问题描述：供应商推荐页面虽有候选列表和人工确认区域，但列表操作列没有“选择供应商”动作，选中状态也未形成绑定当前 RuntimeContext 的推荐选择对象；报价比较表重复展示物料列，容易把同一物料的多家供应商报价误读为多个商品。流程中心供应商推荐节点仍使用无参数静态路由，进入后只能依赖页面兜底恢复，节点导航本身没有携带 `runtimeContextId`。
- 根因：候选行操作、人工确认草稿与 Decision 之间缺少显式对象链；物料身份与供应商报价没有分区展示；SCM 流程节点注册未消费最近激活的真实推荐运行上下文。
- 解决方案：候选列表操作列增加显式人工选择，生成绑定 `runtimeContextId + materialCode + supplierCode` 的 `SupplierRecommendationCurrentSelection`，人工确认区显示该推荐供应商并继续要求理由、确认人和确认按钮；物料在独立摘要区只显示一次，报价比较表按供应商逐行展示报价。新增 SCM 专属流程入口上下文提供者，流程注册在生成供应商推荐节点链接时附加已验证的 `runtimeContextId`；没有真实上下文时不提供可导航空链接。页面继续按该编号精确恢复，禁止 Demo 和跨实例数据。
- 对应规范：`PROCESS-008`、`PROCESS-009`、`PROCESS-010`、`PROCESS-011`、`BUSINESS-HANDOFF-REAL-001`、`BUSINESS-ENHANCEMENT-BOUNDARY-001`。
- 回归测试：`verifySupplierRecommendationActionClosureV11428166.mjs` 必须覆盖候选动作、当前推荐对象、报价比较分区、流程中心带参入口、运行上下文恢复、人工 confirmed Decision、Gate Handoff、PROCESS-011、回归与 Build。

## CASE-SCM-045 多入口直接传递运行上下文导致推荐实例身份不统一

- 案例编号：`CASE-SCM-045`
- 发现版本：`V1.14.2.8.18.16.7`
- 问题描述：采购核价单条入口、批量入口和流程中心入口均直接携带 `runtimeContextId`，页面同时保留复合键、RuntimeContext 和无参数兜底等多种恢复方式。相同业务实例从不同入口进入时缺少统一任务身份，无法稳定证明用户处理的是同一项供应商推荐工作。
- 根因：`SupplierRecommendationRuntimeContext` 同时承担数据承接身份与用户任务入口身份，没有独立的任务对象连接入口、当前办理人、任务状态和运行上下文。
- 解决方案：建立 `SupplierRecommendationTask`，字段固定为 `taskId`、`sourcePriceApprovalIds`、`runtimeContextId`、`status`、`currentAssignee`。采购核价单条、批量及流程中心统一创建或恢复 Task，路由只携带 `taskId`；页面严格执行 `TaskId → RuntimeContextId → SupplierRecommendationDecisionContext → 页面数据`，拒绝仅传 RuntimeContext、复合键或无参数直接打开。批量每个物料建立独立 Task；人工选择、confirmed Decision 和 Gate Handoff 同步推进 Task 状态与办理人。
- 对应规范：`PROCESS-008`、`PROCESS-009`、`PROCESS-010`、`PROCESS-011`、`BUSINESS-HANDOFF-REAL-001`、`BUSINESS-ENHANCEMENT-BOUNDARY-001`。
- 回归测试：`verifySupplierRecommendationTaskRuntimeV11428167.mjs` 必须覆盖任务模型、三入口统一、批量逐任务拆分、同一 Task/RuntimeContext 恢复、候选动作、Decision、Gate、PROCESS-011、回归与 Build。

## CASE-SCM-047 候选控件可见但未形成可确认的当前选择

- 案例编号：`CASE-SCM-047`
- 发现版本：`V1.14.2.8.18.16.8`
- 问题描述：供应商推荐页候选按钮可以生成 `CurrentSelection`，但同一区域的候选下拉框只修改供应商编码，没有生成绑定当前 RuntimeContext 的选择对象，导致用户完成可见选择后“确认推荐”仍不可执行；页面动作也缺少统一的用户执行权限门禁。
- 根因：页面控件的可见性与动作运行契约分离，仅以局部 `disabled` 和状态判断约束按钮，没有统一验证状态、必要数据、权限和执行结果，也没有让所有候选入口复用同一选择 Action。
- 解决方案：建立供应商推荐 Action Executability 评估器，统一验证按钮可见、允许状态、Task/RuntimeContext 与业务数据完整、用户 `EXECUTE` 权限和预期结果状态；按钮和事件处理函数共同消费该门禁。候选下拉框改为调用与候选按钮相同的选择动作并生成 `CurrentSelection`。
- 对应规范：`PROCESS-008`、`PROCESS-009`、`PROCESS-010`、`PROCESS-011`、`CODEX-COMMAND-002`、`BUSINESS-ENHANCEMENT-BOUNDARY-001`。
- 回归测试：`verifySupplierRecommendationActionExecutabilityV11428168.mjs` 必须覆盖 Task 入口回归、动作存在、合法执行、越级阻断、缺数据阻断、权限阻断、人工确认、Decision 状态、Gate Handoff、PROCESS-011 六层、既有回归与 Build。

## CASE-SCM-048 单物料任务被错误用作采购推荐决策业务入口

- 案例编号：`CASE-SCM-048`
- 发现版本：`V1.14.2.8.18.16.9`
- 问题描述：供应商推荐已具备 Task Runtime 与动作闭环，但页面和流程中心以单物料 Task 作为用户入口，采购人员无法在同一个采购决策工作台中查看并逐项完成一个核价批次的多物料推荐，也不能形成一次完整的批次确认结果。
- 根因：技术执行粒度与采购决策业务粒度混用；`SupplierRecommendationTask` 适合绑定一个 RuntimeContext，却不适合作为跨物料采购推荐的聚合根和页面身份。
- 解决方案：新增 `SupplierRecommendationDecisionBatch` 聚合根与 `SupplierRecommendationDecisionItem`，由批次承接核价批次、报价比较批次和多个物料项；Task 仅作为 Item 的底层执行索引。采购核价与流程中心统一以 `decisionBatchId` 进入“供应商推荐决策工作台”，逐物料保存供应商及理由，全部完成后生成 `SupplierRecommendationDecisionBatchResult` 和只读 Gate Handoff，禁止创建 PurchaseOrder。
- 对应规范：`PROCESS-008`、`PROCESS-009`、`PROCESS-010`、`PROCESS-011`、`BUSINESS-HANDOFF-REAL-001`、`BUSINESS-ENHANCEMENT-BOUNDARY-001`。
- 回归测试：`verifySupplierRecommendationDecisionWorkbenchV11428169.mjs` 必须覆盖批次模型、多物料隔离、供应商报价比较、逐项人工决策、批量确认、流程中心同批次恢复、Gate Handoff、PROCESS-011 六层、既有回归与 Build。

## CASE-SCM-049 技术对象名称替代供应商推荐业务名称

- 案例编号：`CASE-SCM-049`
- 发现版本：`V1.14.2.8.18.17`
- 问题描述：供应商推荐页面、页面身份和流程中心显示“供应商推荐决策工作台”，且采购核价与流程中心入口使用带 `decisionBatchId` 查询参数的技术 URL，导致用户看到技术对象和内部批次实现而非稳定的采购业务入口。
- 影响：采购人员对节点职责产生误解；相同业务从不同入口呈现不同的 URL 身份，页面名称与企业业务名称不一致。
- 根因：将内部 `SupplierRecommendationDecisionBatch` 对象名称直接投影为用户业务名称，并把批次解析参数作为查询字符串暴露给业务页面。
- 解决方案：用户业务名称统一恢复为“供应商推荐”，内部对象继续保持 `SupplierRecommendationDecisionBatch`；采购核价、批量入口和流程中心统一使用 `/scm/supplier-recommendation-task/{taskId}`，页面从路径任务标识恢复既有决策批次，不暴露 batchId、runtimeContextId、priceApprovalId 或 quoteComparisonId 查询参数。
- 对应规范：`NAME-GOV-001`、`NODE-PAGE-001`、`PROCESS-009`、`PROCESS-011`、`BUSINESS-ENHANCEMENT-BOUNDARY-001`。
- 回归测试：`verifySupplierRecommendationEntryGovernanceV1142817.mjs` 必须覆盖业务名称、Route Identity、采购核价入口、流程中心入口、相同页面身份、无技术查询泄漏、既有业务回归与 Build。

## CASE-SCM-050 决策批次页面直接读存储导致核价来源字段不可证明

- 案例编号：`CASE-SCM-050`
- 发现版本：`V1.14.2.8.18.18`
- 问题描述：供应商推荐页面直接读取 `SupplierRecommendationDecisionBatch` 存储，只能展示批次中的物料和候选，采购申请编号与逐 Item 核价编号未投影，`quoteComparisonId` 仅存在于内部绑定索引，页面无法证明当前物料、候选和历史价格来自同一真实核价实例。
- 根因：DecisionBatch 聚合建立后缺少跨 `SupplierRecommendationTask → RuntimeContext → PriceApproval Handoff` 的只读数据承接 Provider；页面把批次存储误作完整业务事实源。
- 解决方案：新增 `SupplierRecommendationDataHandoffProviderV1142818`，按 Task、DecisionBatch、PriceApproval Runtime Context 关联并逐 Item 校验 priceApprovalId、quoteComparisonId、materialCode、materialName、供应商候选和 PriceReferenceContext；任一映射缺失或含 Demo/Acceptance 标识立即阻断。页面业务数据区只消费 Provider 投影，不修改路由、身份、动作或 Gate。
- 对应规范：`PROCESS-008`、`PROCESS-009`、`PROCESS-010`、`PROCESS-011`、`BUSINESS-HANDOFF-REAL-001`、`BUSINESS-ENHANCEMENT-BOUNDARY-001`。
- 回归测试：`verifySupplierRecommendationDataHandoffV1142818.mjs` 必须覆盖单物料金丝雀、多物料金丝雀、异常阻断、核价/Task/批次/Item 字段一致性、候选与报价匹配、Demo 隔离、PROCESS-011 Data Handoff、既有回归与 Build。

## CASE-SCM-051 报价行粒度替代物料决策粒度导致推荐物料丢失

- 案例编号：`CASE-SCM-051`
- 发现版本：`V1.14.2.8.18.18.1`
- 问题描述：采购核价输入 19 条记录且实际包含 13 个不同物料时，供应商推荐 DecisionBatch 的输出数量不等于 13；同一物料的多供应商报价在报价行、核价记录和物料三个粒度之间混用，导致物料重复或丢失。
- 根因：DecisionItem 由来源行直接映射，且真实数据 Provider 假设每个物料只能存在一个 Task 绑定；没有先按业务入口保全同一核价与报价比较下的供应商事实，再按 `materialCode` 形成唯一物料决策项。
- 解决方案：建立两阶段聚合。入口阶段按 `priceApprovalId + quoteComparisonId + materialCode` 合并同一业务来源并保全全部候选；DecisionBatch 阶段严格 `groupBy(materialCode)`，每个物料生成一个 DecisionItem，并聚合 `quoteComparisonIds`、`supplierCandidates`、`priceEvidence`；Provider 支持同一物料的多个真实 Task/RuntimeContext 绑定并逐一校验，禁止截断或回退 Demo 数据。
- 对应规范：`PROCESS-008`、`PROCESS-009`、`PROCESS-010`、`PROCESS-011`、`BUSINESS-HANDOFF-REAL-001`、`BUSINESS-ENHANCEMENT-BOUNDARY-001`。
- 回归测试：`verifySupplierRecommendationDecisionItemGrainV11428181.mjs` 必须覆盖来源行数、不同物料数、DecisionItem 粒度、多供应商候选聚合、无数据丢失、PROCESS-011 Data Handoff、既有回归与 Build。

## CASE-SCM-052 页面Route承载业务组合标识导致页面身份不稳定

- 案例编号：`CASE-SCM-052`
- 发现版本：`V1.14.2.8.18.17.1`
- 问题描述：供应商推荐使用 `/scm/supplier-recommendation-task/{taskId}` 作为页面入口，路径参数实际承载 DecisionBatch、PriceApproval、QuoteComparison 与 Material 的组合业务标识；同一页面因业务实例不同形成不同 URL，与供应商报价等稳定页面身份不一致。
- 根因：页面身份和业务运行上下文未分层；Task/DecisionBatch 的内部恢复键被直接提升为公开 Route 参数，核价入口和流程中心均依赖该技术参数导航。
- 解决方案：供应商推荐页面身份统一为 `/scm/supplier-recommendation`；新增内部 `SupplierRecommendationRouteContextResolverV11428171`，由核价入口激活内部批次上下文，页面加载后按 Task、DecisionBatch、DecisionItem 顺序恢复；流程中心只返回稳定页面Route，不在URL中暴露业务组合数据。
- 对应规范：`PROCESS-009`、`PROCESS-011`、`NAME-GOV-001`、`NODE-PAGE-001`、`BUSINESS-ENHANCEMENT-BOUNDARY-001`。
- 回归测试：`verifySupplierRecommendationRouteIdentityV11428171.mjs` 必须覆盖页面Route、业务数据不泄露、流程中心入口、Context恢复、同一页面身份、既有回归与Build。

## CASE-GOV-003 业务运行数据泄露到页面Route

- 案例编号：`CASE-GOV-003`
- 案例名称：业务运行数据泄露到页面Route
- 发现版本：`V1.14.2.8.18.17.1`
- 治理版本：`V1.14.2.8.18.17.2`
- 问题描述：页面URL承担Task、业务批次、订单、物料或RuntimeContext等业务上下文，导致同一业务页面因运行实例不同形成多个技术Route。
- 影响：Page Identity不稳定；流程中心与业务入口可能指向不同URL；内部对象键对用户暴露；刷新、收藏、复制URL和权限校验与业务上下文耦合。
- 根因：缺少Page Route与Business Context的强制职责分离，使用Router参数替代Context Resolver、Task和Provider的业务恢复链。
- 解决方案：建立`ROUTE-CONTEXT-001`。Route只表达稳定页面身份；业务实例统一按`Page Route → Context Resolver → Task → Business Object → Provider → Page Data`恢复；PROCESS-011增加Route Identity与Context Separation。
- 对应规范：`ROUTE-CONTEXT-001`、`PROCESS-009`、`PROCESS-010`、`PROCESS-011`、`NODE-PAGE-001`、`CODEX-COMMAND-002`。
- 回归要求：`verifyRouteContextGovernanceV11428172.mjs`必须检查治理文档、页面模板、PROCESS-011扩展、案例、既有供应商推荐Route回归与Build。

## CASE-SCM-053 跨询价批量核价只激活首个推荐决策批次

- 案例编号：`CASE-SCM-053`
- 发现版本：`V1.14.2.8.18.18.2`
- 问题描述：采购核价批量选择19条、覆盖13个物料且来源属于多个询价时，Task层按询价拆分为多个底层批次，DecisionBatch层逐批创建推荐批次，而页面只激活第一个DecisionBatch，最终仅显示首批2个物料。
- 根因：底层Task管理批次与用户一次批量推荐决策的聚合根职责混用；DecisionBatch直接复用按`sourceInquiryNo`拆分的Task批次边界，并通过`decisionBatches[0]`丢弃其他批次的页面入口。
- 解决方案：保留Task层按询价形成的运行事实，但将本次选择产生的全部Task扁平映射到一个DecisionBatch；DecisionItem继续严格按`materialCode`聚合，并保存`sourcePriceApprovalIds`、`quoteComparisonIds`和全部`SupplierCandidate`；Provider逐项校验完整来源集合，输出数量诊断。
- 对应规范：`PROCESS-008`、`PROCESS-009`、`PROCESS-011`、`ROUTE-CONTEXT-001`、`BUSINESS-HANDOFF-REAL-001`、`BUSINESS-ENHANCEMENT-BOUNDARY-001`。
- 回归测试：`verifySupplierRecommendationBatchIntegrityV11428182.mjs`必须覆盖选择行数、Task数量、Batch源映射、13物料聚合、候选完整性、刷新恢复、Route隔离、既有回归与Build。

## CASE-SCM-054 同物料多供应商真实验收场景缺失

- 案例编号：`CASE-SCM-054`
- 发现版本：`V1.14.2.8.18.18.3`
- 问题描述：供应商推荐批量完整性自动验收已覆盖同物料多供应商聚合，但真实采购运行数据中每个物料仅有一家供应商报价，导致 Canary C 无法通过真实页面验证一个 DecisionItem 保留多个 SupplierCandidate。
- 根因：既有采购询价只向单一供应商形成报价准备，真实业务链没有产生同一 `inquiryNo + materialCode` 下的多个 SupplierQuote；自动测试事实不能替代 PROCESS-011 Data Handoff 的真实运行证据。
- 解决方案：从已审批采购申请生成新的询价准备，通过采购询价页面为同一物料选择多个 Supplier Master 候选，人工录入各供应商报价，完成报价收集和报价比较，再由采购核价页面选择同物料报价行进入供应商推荐；以页面结果验证一个 DecisionItem 和多个 SupplierCandidate，禁止直接修改推荐对象或注入候选。
- 对应规范：`PROCESS-009`、`PROCESS-010`、`PROCESS-011`、`ROUTE-CONTEXT-001`、`CODEX-COMMAND-002`、`BUSINESS-ENHANCEMENT-BOUNDARY-001`。
- 回归测试：`verifySupplierRecommendationMultiSupplierCanaryV11428184.mjs`必须验证真实多供应商来源、SupplierQuote数量、QuoteComparison供应商数量、单物料DecisionItem、候选聚合、Demo隔离、Canary C、PROCESS-011、既有回归与Build。

## CASE-SCM-055 人工决策闭环仅有兼容字段且候选证据展示不完整

- 案例编号：`CASE-SCM-055`
- 发现版本：`V1.14.2.8.18.19`
- 问题描述：供应商推荐页面已经能够保存供应商与理由并批量确认，但DecisionItem仅保存`decisionSupplier/decisionReason/status`兼容字段，无法直接表达人工复核人、复核时间及`manual_review → confirmed`状态；人工决策区的候选下拉框也未逐候选显示报价比较、历史价格和资格状态。
- 根因：早期实现优先打通页面动作与Gate交接，没有把人工选择事实提升为完整领域字段，也没有把Provider已有的报价、历史和资格证据投影到每个候选的决策视图。
- 解决方案：向后兼容扩展SupplierRecommendationDecisionItem，增加`decisionItemId、selectedSupplierCode、selectedSupplierName、selectionReason、reviewStatus、reviewer、reviewedAt`；选择动作保持`manual_review`，批量确认后形成`SupplierRecommendationDecision`并进入`confirmed`；页面逐候选只读显示价格、比较、历史与资格证据，仍由采购人员选择并填写理由。
- 对应规范：`PROCESS-009`、`PROCESS-010`、`PROCESS-011`、`CODEX-COMMAND-002`、`BUSINESS-ENHANCEMENT-BOUNDARY-001`、`ROUTE-CONTEXT-001`。
- 回归测试：`verifySupplierRecommendationHumanDecisionV1142819.mjs`必须覆盖候选证据、人工选择、理由输入、非最低价确认、13项批量确认、Decision状态、Gate交接、无自动推荐、无采购订单、PROCESS-011、既有回归与Build。

## CASE-SCM-056 批量推荐确认前未完成全部物料决策导致按钮不可执行

- 案例编号：`CASE-SCM-056`
- 案例名称：批量推荐确认前未完成全部物料决策导致按钮不可执行
- 发现版本：`V1.14.2.8.18.19`
- 治理版本：`V1.14.2.8.18.19.1`
- 问题描述：供应商推荐批次包含多个 `DecisionItem`，用户仅完成部分物料的供应商选择后点击“批量确认推荐”，确认按钮不可执行；页面若不说明未完成项及门禁原因，用户会将正确的完整性阻断误判为按钮故障。
- 根因：`DecisionBatch` 的确认规则要求全部 `DecisionItem` 同时完成 `selectedSupplier`（或受治理的供应商编码/名称字段）、`selectionReason` 和 `reviewStatus`，才允许执行 Batch Confirm；验收此前只观察按钮结果，没有显式核对批次完成度。
- 正确行为：存在未完成项时阻止批量确认、保持原业务状态，并提示“当前批次仍有未完成物料决策。”；全部物料完成后允许确认。系统不得自动补齐选择、理由或复核状态。
- 验收规则：执行 `Batch Decision Completeness Check`，必须输出 `Completed Item Count`、`Pending Item Count`、`Confirm Action Enabled`；仅当待完成数为 0 时确认动作可用。
- 对应规范：`PROCESS-009`、`PROCESS-011`、`Action Executability`、`Batch Decision Completeness Check`、`CODEX-COMMAND-002`。
- 回归测试：`verifySupplierRecommendationDecisionCompletenessV11428191.mjs` 必须验证本案例、完整性门禁治理文本、既有供应商推荐人工决策回归与 Build。

### V1.14.2.8.18.19.2 治理补充记录

- 模板定位：`CASE-SCM-056` 同时作为所有批量业务完整性检查模板，适用于 SCM 采购推荐、付款审批、生产派工、质量放行、库存处理及其他批量节点。
- 统一规则：接入 `BATCH-COMPLETENESS-001` 与 PROCESS-011 `Batch Completeness`；所有批量动作必须输出 `Total Item Count`、`Completed Item Count`、`Pending Item Count` 和 `Action Disabled`。
- 阻断规则：待完成数大于 0 或总项数为 0 时禁止批量动作并保持原状态；全部子项完成后必须恢复可执行。业务不得自动补齐、跳过或隐藏未完成项。
- 回归入口：`verifyBatchDecisionCompletenessGovernanceV11428192.mjs`。

| 2.5 | 将 CASE-SCM-056 提升为全模块批量业务完整性治理模板，建立 BATCH-COMPLETENESS-001 | V1.14.2.8.18.19.2 |

## CASE-SCM-057 采购订单准入条件不完整导致错误进入订单阶段

- 案例编号：`CASE-SCM-057`
- 案例名称：采购订单准入条件不完整导致错误进入订单阶段
- 发现版本：`V1.14.2.8.18.20`
- 问题描述：采购订单准入页面只读展示供应商推荐批次交接，旧 Gate Runtime 仍按单供应商推荐事实输出 `eligible`，没有对 DecisionBatch 的全部物料确认、供应商字段、人工审计和业务证据执行统一准入检查。
- 根因：旧 `PurchaseOrderCreationGateDecision` 早于 `SupplierRecommendationDecisionBatchResult` 建立，输入粒度仍是单推荐决定；批次交接只进入页面展示，没有形成可持久恢复的 Gate Decision 和 `BATCH-COMPLETENESS-001` 门禁。
- 解决方案：新增 V20 `PurchaseOrderCreationGateDecision` 与真实 Gate Provider，以 `SupplierRecommendationDecisionBatchResult` 为输入，逐项检查批量完整性、Decision状态、供应商、人工确认和报价/历史/理由证据；输出 `ready_for_purchase_order` 或 `blocked`，仅保存 Gate Decision，禁止创建、提交或审批 PurchaseOrder。
- 对应规范：`PROCESS-008`、`PROCESS-009`、`PROCESS-010`、`PROCESS-011`、`BATCH-COMPLETENESS-001`、`ROUTE-CONTEXT-001`、`BUSINESS-ENHANCEMENT-BOUNDARY-001`。
- 回归测试：`verifyPurchaseOrderGateRuntimeV1142820.mjs` 必须覆盖单物料、13物料、一个未确认物料阻断、真实 Provider、九项 PROCESS-011、PurchaseOrder 隔离、既有回归与 Build。

| 2.6 | 新增 CASE-SCM-057，建立 DecisionBatch 到采购订单准入 Gate 的完整性与禁止创建订单门禁 | V1.14.2.8.18.20 |

### CASE-SCM-057 V1.14.2.8.18.20.1 动作闭环补充记录

- 人工反馈：Gate已有检查按钮但已保存决定不能重新检查；物料行缺少异常原因和返回处理入口；历史PurchaseOrder事实存在影响当前Gate判断的风险。
- 补充根因：Provider以已保存决定直接幂等返回，页面把动作限制在`pending_review`；Gate证据规则把历史价格事实误作当前批次准入必要条件。
- 收敛方案：每次动作重新读取当前`SupplierRecommendationDecisionBatchResult`并覆盖最新Gate Decision，记录`checkedBy/lastCheckedAt`；逐物料展示阻断原因并提供查看依据、查看供应商和返回推荐修改；新增`HistoricalPurchaseOrderIsolationCheck`，历史PurchaseOrder列表不参与准入判断。
- 回归入口：`verifyPurchaseOrderGateActionClosureV11428201.mjs`。

## CASE-SCM-058 Gate通过但缺少人工回退闭环

- 案例编号：`CASE-SCM-058`
- 案例名称：Gate通过但缺少人工回退闭环
- 类型：流程节点状态不可逆治理案例
- 发现版本：`V1.14.2.8.18.20.1`
- 修复版本：`V1.14.2.8.18.20.2`
- 问题描述：采购订单准入 Gate 的“返回供应商推荐修改”仅执行页面跳转，已确认 DecisionItem 仍保持锁定，采购人员无法重新选择供应商或修改理由；Gate 每次检查只覆盖最新 Gate Decision，没有长期保留检查人、检查时间、检查项目、结果和阻断原因。
- 根因：退回入口没有绑定供应商推荐领域状态转换；Gate Decision 同时承担当前结论与审计日志职责，缺少追加式检查记录模型。
- 解决方案：新增受权限保护的退回动作，严格执行 `confirmed → reopen_review → manual_review`，使当前 Result/Handoff 暂时失效并允许重新选择、重新确认；新增 `PurchaseOrderGateInspectionRecord`，每次 Gate 检查追加保存检查项和结果，页面独立展示检查记录及人工审计动作。
- 边界：退回不删除物料，不修改 Route、Page Shell、List Runtime 或 Process Center；检查、退回和重新确认均保持 `purchaseOrderCreated=false`。
- 对应规范：`PROCESS-009`、`PROCESS-010`、`PROCESS-011`、`ROUTE-CONTEXT-001`、`BATCH-COMPLETENESS-001`、`CODEX-COMMAND-002`。
- 回归测试：`verifyPurchaseOrderGateAuditLoopV11428202.mjs` 必须覆盖退回修改、Decision重开、重新确认、Gate检查记录、审计追踪、PurchaseOrder隔离、PROCESS-011、既有回归与Build。

## CASE-SCM-059 Gate退回修改后业务数据未重新承接导致准入结果未更新

- 案例编号：`CASE-SCM-059`
- 案例名称：Gate退回修改后业务数据未重新承接导致准入结果未更新
- 类型：流程节点数据回写一致性治理案例
- 发现版本：`V1.14.2.8.18.20.2`
- 修复版本：`V1.14.2.8.18.20.3`
- 问题描述：Gate退回供应商推荐后，采购人员能够修改供应商并重新确认，但再次打开Gate仍先显示修改前供应商；只有手工再次点击检查，页面才读取新结果。
- 根因分析：`SupplierRecommendationDecisionBatchStore`按BatchId覆盖旧Result，未提供Decision Revision；Gate Provider优先恢复已保存Gate Decision，无法判断该决定对应的上游Result是否已经变化。
- 错误链路：`Decision修改 → 覆盖同一Result → Gate读取旧Decision缓存 → 页面展示旧供应商 → 手工复检后才刷新`。
- 正确链路：`reopen_review → 人工修改 → 追加DecisionBatchResult Revision → Gate读取最新Revision → 比对sourceDecisionSignature → 自动重新Evaluation → 追加Inspection Record`。
- 修复方案：确认结果按Revision追加保存并保留历史版本；Gate Decision记录`sourceDecisionRevision/sourceDecisionSignature`，打开页面发现版本变化时立即以最新Result重建Decision并追加供应商快照检查记录；未重新确认或Revision缺失时强制Blocked。
- 边界：不修改Route、Page Shell、List Runtime、Process Center公共组件；不创建、提交或审批PurchaseOrder。
- 对应规范：`PROCESS-009`、`PROCESS-010`、`PROCESS-011`、`ROUTE-CONTEXT-001`、`BATCH-COMPLETENESS-001`、`BUSINESS-ENHANCEMENT-BOUNDARY-001`、`CODEX-COMMAND-002`。
- 回归测试：`verifyPurchaseOrderGateReopenDataSyncV11428203.mjs`必须覆盖Decision Revision、更新传播、最新结果读取、旧缓存隔离、Inspection历史、未确认/缺版本阻断、Ready恢复、PurchaseOrder隔离、PROCESS-011、回归与Build。

### V1.14.2.8.18.20.4 Gate治理冻结确认

- `CASE-SCM-057` 冻结名称：采购订单准入条件不完整导致错误进入订单阶段。
- `CASE-SCM-058` 冻结名称：Gate通过但缺少人工回退闭环；冻结类型：流程节点状态不可逆治理案例。
- `CASE-SCM-059` 冻结名称：Gate退回修改后业务数据未重新承接导致准入结果未更新；冻结类型：流程节点数据回写一致性治理案例。
- 三个案例统一绑定 `SCM-PO-GATE-001`、`PROCESS-011`、`BATCH-COMPLETENESS-001` 和冻结回归入口 `verifyPurchaseOrderGateGovernanceFreezeV11428204.mjs`。
- 冻结后如需改变Gate职责、状态、输入、检查项、Revision或Inspection规则，必须建立新的治理版本，禁止在业务增强版本中静默改写。

## CASE-SCM-060 公共金丝雀视图替换页面业务区域导致专项能力缺失

- 案例编号：`CASE-SCM-060`
- 发现与修复版本：`V1.14.2.8.4.21`
- 问题描述：采购询价 URL 正确进入 `canary_acceptance` 后，公共页面壳用通用金丝雀列表替换了采购询价页面插槽，导致来源证据、物料明细、供应商候选、发送/报价状态和页面操作指引没有挂载。
- 根因：公共金丝雀注入假设所有 SCM 页面均由通用只读列表承接，没有为已经具备统一双模式 Provider 的业务页面声明数据事实所有权。
- 解决方案：在公共壳增加默认关闭的 `pageOwnsCanary` 显式契约，仅由采购询价路由启用；启用后保留同一个业务页面并由页面专用 Provider 互斥读取 Canary API，同时关闭壳层重复的通用 Canary Context，避免同页出现两套事实。
- 对应规范：`PCE-ERP统一页面验收标准V1.1`、`一页一验收规范`、`金丝雀测试管理规范`、`PROCESS-011`。
- 回归测试：`verifyScmPurchaseInquiryRuntimeV11428421.mjs` 必须覆盖单页面 Canary 所有权、页面唯一、正式/Canary API 互斥、8 场景映射、刷新保持和生产写入隔离。

## CASE-SCM-061 采购询价页面存在但正式业务对象链未落库

- 案例编号：`CASE-SCM-061`
- 发现版本：`V1.14.2.8.4.21`
- 修复版本：`V1.14.2.8.4.21-R1`
- 问题描述：采购询价唯一页面、正式/Canary 双运行模式和页面验收均已存在，但正式模式 `resultCount=0`；已审批采购申请没有形成服务端 `PurchaseInquiry`。
- 根因：历史“询价准备”和“激活询价”能力只写入浏览器 `localStorage/sessionStorage`，正式事实 API 只读数据库，缺少经过审批门禁的服务端创建动作。
- 解决方案：复用真实 `PurchaseRequest`、持久化明细与建议供应商，建立 `PurchaseRequest → InquiryPreparationObject → PurchaseInquiry` 服务端链；仅允许 `status=approved` 且 `approval_status=completed` 的采购申请由用户显式、幂等生成询价。
- 边界：不得把 Demo/Acceptance/浏览器缓存作为正式对象；不得自动生成 SupplierQuotation、PriceApproval 或 PurchaseOrder；不得修改采购申请模型或复制页面。
- 对应规范：`PROCESS-011`、`PAGE-COMMON`、`SCM-INQUIRY`、`CHAIN`、`一页一验收规范`。
- 回归测试：`verifyScmPurchaseInquiryBusinessChainR1V11428421.mjs` 必须验证来源关系、8 个 Canary 映射、刷新保持、正式事实隔离和 PurchaseOrder 零创建。
## CASE-SCM-062 供应商报价页面存在但正式业务对象链未落地

- 案例编号：`CASE-SCM-062`
- 发现与修复版本：`V1.14.2.8.4.22`
- 问题描述：供应商报价页面、前端领域模型和浏览器运行时已经存在，但正式模式仍依赖前端本地事实，服务端没有 `SupplierQuotation` 持久对象、来源询价关系或人工保存/提交动作，页面无法证明报价来自同一真实 `PurchaseInquiry`。
- 根因：页面运行能力与服务端业务对象链分离；旧 Provider 使用浏览器存储补齐报价事实，自动验收只检查了对象和页面存在，未验证服务端 Data Handoff 与刷新保持。
- 解决方案：建立 `PurchaseInquiry -> SupplierQuotation` 服务端模型、映射服务和受认证人工动作；正式页面只读写服务端事实，金丝雀页面只读独立投影，二者互斥；报价接收不创建 PriceApproval、SupplierRecommendation 或 PurchaseOrder。
- 对应规范：`PROCESS-011`、`PAGE-COMMON`、`SCM-QUOTATION`、`CHAIN`、`CANARY`、`一页一验收规范`。
- 回归测试：`verifyScmSupplierQuotationBusinessChainV11428422.mjs` 必须覆盖真实来源关系、字段完整性、8 场景映射、刷新保持、正式/Canary 隔离及下游零创建。

## CASE-SCM-063 浏览器会话事实缺少服务端连续性基线

- 案例编号：`CASE-SCM-063`
- 发现版本：`V1.14.2.8.4.23`
- 问题描述：报价比较正式页面使用浏览器运行时事实；不同浏览器会话可分别显示 13 条与 5 条，而服务端页面事实接口返回 0 条，无法由服务端独立证明升级前后仍为同一组 13 条业务对象。
- 根因：`SupplierQuotation -> QuoteComparison` 的正式比较结果尚未持久化为服务端 QuoteComparison 对象，连续性证据依赖浏览器会话；页面可见不等于跨会话可审计。
- 解决方案：本版本冻结既有正式 Provider、存储键和聚合键，不迁移、不清除、不重算正式事实；新增 `DATA-CONTINUITY-002`，将升级前基线、同会话升级后数量和刷新后数量作为三段证据。Canary 仅走独立服务端只读 API，禁止替换 Production。后续若建设服务端 QuoteComparison，必须另立迁移版本并核对迁移前后逐对象身份。
- 对应规范：`DATA-CONTINUITY-001`、`DATA-CONTINUITY-002`、`PROCESS-011`、`CANARY`。
- 回归测试：`verifyScmQuoteComparisonContinuityV11428423.mjs` 必须验证正式 Provider 路径未替换、存储/聚合契约未改变、8 个 Canary 映射、下游零创建和构建结果。

## CASE-SCM-064 历史报价比较仅存浏览器会话导致生产事实无法恢复

- 案例编号：`CASE-SCM-064`
- 发现版本：`V1.14.2.8.4.23-R1`
- 问题描述：用户历史会话曾显示 13 条 QuoteComparison，当前隔离会话显示 5 条，公共服务端事实接口返回 0；正式数据库及全部数据库备份均不存在 QuoteComparison 表或 13 条对象快照。
- 根因：历史报价比较由前端浏览器 Runtime Store 基于 SupplierQuote 聚合，未形成服务端 QuoteComparison 持久对象；新建的 SupplierQuotation 服务端链当前也只有 1 条对象，无法无损重建历史 13 条比较事实。
- 解决原则：禁止使用 Canary、Demo、验收事实、当前 1 条 SupplierQuotation 或隔离会话 5 条记录补齐 13 条。恢复必须取得原 13 条会话的可审计导出，逐项保留询价、报价、供应商、物料、数量与报价金额，再通过独立受控迁移版本写入服务端；缺少该来源时必须输出 ISSUES_FOUND。
- 对应规范：`DATA-CONTINUITY-001`、`DATA-CONTINUITY-002`、`PROCESS-011`。
- 回归测试：`verifyScmQuoteComparisonProductionContinuityR1.mjs` 必须以服务端 Production QuoteComparison 数量、刷新一致性、SupplierQuotation 来源、Canary 隔离和下游零新增作为门禁，不得用前端缓存使验收通过。

### V1.14.2.8.4.23-R2 纠偏记录

- 纠偏：R1 所称“不存在”仅指服务端模型、表和标准事实注册不存在，不代表人工浏览器中的 QuoteComparison 运行时业务对象不存在；人工正式浏览器已确认 13 条 Production QuoteComparison。
- 新根因定位：人工页面 Provider、自动验收环境和公共诊断 API 分别读取不同事实所有者，导致 `13 / 5 / 0`。问题类型由“对象缺失”修正为“Production 数据源不一致”。
- 统一契约：Production Provider 固定返回 `resultCount`、`rows`、`source: production`、`dataMode: production` 和 `factLoadStatus: loaded`；验收适配器只能消费该同一对象，不得自行聚合或补齐。
- 未解除门禁：在公共诊断 API 也能读取同一 13 条权威事实前，`PRODUCTION-DATA-CONSISTENCY` 仍为 FAIL，禁止输出 READY。

## CASE-SCM-065 前置业务页面切换服务端事实后历史浏览器链不可见

- 案例编号：`CASE-SCM-065`
- 发现版本：`V1.14.2.8.4.21-R2`
- 问题描述：人工历史链已产生 13 条报价比较及后续业务影响，但当前正式服务端只有 1 条 PurchaseInquiry 和 1 条 SupplierQuotation；询价、报价页面切换到服务端事实后，原浏览器 Runtime 中的历史前置对象不再可见。
- 根因：历史询价、报价和报价比较事实由浏览器 Runtime/存储拥有，未以统一业务键持久化到服务端；当前页面、隔离浏览器、自动验收和人工原浏览器读取不同事实所有者。
- 正确处理：冻结已有数据与下游对象；取得原浏览器事实的可审计导出后，另立受控迁移版本，按 `PR -> PI -> SQ -> QC` 逐对象核对来源编号，再迁移到统一服务端事实。未取得原始事实时保持 `ISSUES_FOUND`。
- 禁止方案：不得重新创建 PI/SQ、重新生成 QC、用当前 1 条服务端链或隔离浏览器 5 条运行事实补足 13 条，也不得使用 Demo/Canary 冒充 Production。
- 对应规范：`CHAIN-CONTINUITY-001`、`DATA-CONTINUITY-001`、`DATA-CONTINUITY-002`、`PROCESS-011`。
- 回归测试：`verifyScmInquiryQuotationChainContinuityR2.mjs` 必须报告服务端数量、两次读取一致性、来源关系、QC 13 条基线、Canary 隔离和下游零新增；任何事实所有者不一致均不得输出 READY。

## CASE-SCM-066 核价流程状态与业务结论混用导致推荐准入错误

- 案例编号：`CASE-SCM-066`
- 发现与修复版本：`V1.14.2.8.4.24-R2.3`
- 问题描述：历史核价以 `approved/rejected` 同时表达流程完成状态和业务结论，出现 `approvalOpinion=不同意` 但 `status=approved` 时，系统仍可能仅凭状态生成供应商推荐上下文。
- 根因：PriceApprovalPreparation 缺少独立、受控的 `reviewResult`，供应商推荐准入条件只检查流程状态，没有联合检查人工业务结论。
- 解决方案：流程状态收敛为 `draft -> reviewing -> completed`，新增 `reviewResult=pass/reject/adjust`；历史记录不回写，通过审批意见只读映射结论；推荐准入必须同时满足 `status=completed AND reviewResult=pass`。
- 边界：不修改 QuoteComparisonFact、Legacy Adapter、历史核价编号/状态/意见，不创建 PurchaseOrder；本版本只保护推荐入口，不开发推荐页面。
- 对应规范：`PROCESS-009`、`PROCESS-010`、`PROCESS-011`、`DATA-CONTINUITY-001`、`LIST-RUNTIME-001`。
- 回归测试：`verifyScmPriceApprovalDecisionGuardR23.mjs` 必须覆盖结论字段、历史映射、不同意阻断、通过准入、中文状态、历史哈希不变及 PurchaseOrder 零新增。

## CASE-SCM-067 企业物料页面与采购申请选择器读取不同事实集合

- 案例编号：`CASE-SCM-067`
- 发现版本：`V1.14.2.8.4.27.2.22`
- 问题描述：企业物料页面显示4条物料，采购申请物料选择器显示80条，维护人员无法从企业物料页面定位业务选择器中的物料。
- 根因：企业物料页面读取 `enterprise_master_data.py` 的4条静态验收 rows；采购申请引用接口读取 SQLite `material` 表中80条启用且可采购的 `masterdata.Material`，两个入口未复用同一服务端事实。
- 解决方案：本版本只读追踪并冻结来源，新增企业基础数据治理与物料唯一来源规范；后续独立迁移版本应以数据库 MaterialMaster 为唯一来源，先去重再切换企业物料页面 Provider。
- 纳入规则：`MASTER-DATA-SOURCE-001`、`MATERIAL-SELECTOR-SOURCE-TRACE-001`、`MATERIAL-SOURCE-UNIQUE-001`、`MATERIAL-MASTER-FIELD-COMPLETE-001`。
- 回归测试：`verifyMaterialSelectorSourceTraceV11428427222.mjs`；在事实统一前，唯一来源门禁必须保持 FAIL，不得用静态数据或前端合并伪造通过。

## CASE-SCM-068 静态物料验收Fixture进入正式企业物料页面

- 案例编号：`CASE-SCM-068`
- 发现版本：`V1.14.2.8.4.27.2.22`
- 修复版本：`V1.14.2.8.4.27.2.23`
- 问题描述：企业物料页面把4条静态验收 rows 标记为服务端物料事实，导致其与采购业务实际使用的80条 MaterialMaster 不一致。
- 根因：通用企业主数据事实文件同时承担页面注册和验收数据，物料实体没有接入正式 ORM 与唯一 Runtime Adapter。
- 解决方案：引用扫描确认4条编码无业务用途后删除静态 rows；建立 `MaterialMasterRuntimeAdapter → MaterialRuntimeModel`，企业物料页面和采购申请引用接口共同读取 `masterdata.Material/material`。
- 纳入规则：`MATERIAL-MASTER-SINGLE-RUNTIME-001`、`MATERIAL-DATA-SOURCE-001`、`MATERIAL-FIXTURE-CLEANUP-001`、`MATERIAL-BUSINESS-CHAIN-001`。
- 回归测试：`verifyMaterialMasterSingleSourceV11428427223.mjs`、企业物料/采购申请/采购订单详情浏览器验收及 Build。
## CASE-SCM-069 采购订单信任Gate价格导致供应商事实、金额与交期失真

- 发现版本：V1.14.2.8.4.27.2.24
- 问题描述：采购订单创建链直接读取页面/Gate载荷中的 `unitPrice` 与交期，导致供应商字段不完整、采购执行单价和金额为0、交期为空；前端又通过数量乘单价重算金额，形成第二事实源。
- 根因：缺少 SupplierMaster、供应商报价事实与 PurchaseOrderItem 之间的服务端来源解析；CreationRequest 未在写入前校验价格与交期事实。
- 修复方案：建立 `PurchaseOrderSupplierFactRuntime`，以 SupplierMaster 和已持久化 SupplierQuotation 为价格事实来源，以报价交期、供应商物料交期事实、采购申请需求日期为交期优先链；金额仅由服务端计算，缺少有效价格时阻断整单并保持零写入；页面仅消费服务端金额及来源诊断。
- 对应治理规则：SUPPLIER-MASTER-SOURCE-001、SCM-PURCHASE-LIFECYCLE-001、SUPPLIER-SOURCE-TRACE-001、PURCHASE-PRICE-SOURCE-001、PURCHASE-AMOUNT-CALC-001、PURCHASE-DELIVERY-SOURCE-001。
- 回归结果：后端来源、金额、交期与零写入阻断测试通过；物料主数据链保持不变；Gate模型与数据库结构未修改。
## CASE-SCM-070 页面私有供应商物料编码与服务端主数据无法匹配

- 发现版本：V1.14.2.8.4.27.2.25
- 问题描述：基础资料页面显示供应商物料价格和关系已维护，但采购订单服务端无法继承；页面集合使用 `SUP-000001`、`MAT-000001` 及本地ID，服务端使用 `SUP001`、`MT001` 等正式编码。
- 根因：页面私有 Store 与服务端 SupplierMaster/MaterialMaster 没有统一身份契约，且缺少供应商、物料、关系、价格四对象的服务端联合解析门禁。
- 修复方案：隔离页面私有事实，建立 `SupplierMaterialFactResolver`；只允许服务端主键或完整编码严格匹配，持久化 SupplierQuotation 行投影关系及价格事实，冲突时阻断订单创建。
- 对应治理规则：SUPPLIER-CODE-MATCH-001、MATERIAL-CODE-MATCH-001、PURCHASE-ORDER-FACT-INHERIT-001。
- 回归结果：严格编码匹配、订单事实继承、错误编码零写入和V24事实链回归通过；数据库、Gate及正式编码未修改。
## CASE-SCM-071 SupplierMaster页面第二事实源与基础字段不完整

- 发现版本：V1.14.2.8.4.27.2.26
- 问题描述：供应商主数据页面读取 `enterprise_master_data.py` 两条静态测试供应商，而采购业务使用 `supplier` 表100条SupplierMaster；正式数据全部缺地址和分类，并存在一组同名供应商。
- 根因：供应商页面未像物料页面一样接入正式Runtime Adapter，业务使用关系没有统一反向映射和缺失字段诊断。
- 修复方案：建立 `SupplierMasterRuntimeAdapter` 与 `SupplierBusinessMapping`，页面切换到正式SupplierMaster，静态供应商清空；缺失地址/分类和同名歧义显式进入人工确认，不伪造或自动合并。
- 对应治理规则：SUPPLIER-MASTER-SOURCE-001、SUPPLIER-BUSINESS-MAPPING-001、SUPPLIER-FIELD-COMPLETE-001、SUPPLIER-DUPLICATE-001。
- 回归结果：唯一来源和业务映射能力通过；字段完整性及同名确认未关闭，版本不得READY。
- 关闭版本：`V1.14.2.8.4.27.2.27`
- 关闭方案：SupplierMaster新增持久化分类字段；受控数据迁移只补齐空地址、空分类及缺失联系资料；同名记录不合并、不删除、不改编码，分别建立`SupplierDuplicateReview`并保持`待人工确认`。
- 新增规则：`SUPPLIER-FIELD-COMPLETE-002`、`SUPPLIER-DUPLICATE-REVIEW-001`。
- 回归要求：自动验收必须同时核对100条SupplierMaster字段完整性、同名审核覆盖、页面服务端事实、Supplier编码集合不变，以及PurchaseOrder/Gate/Material零修改边界。

## CASE-SCM-072 供应商物流送货地址缺失且采购订单展示链不完整

- 发现与修复版本：`V1.14.2.8.4.27.2.28`
- 问题描述：SupplierMaster只有注册地址，无法独立表达物流送货地址；采购订单详情虽已有部分供应商字段，但没有独立供应商信息区域，打印预览只显示供应商名称。
- 根因：SupplierMaster交付字段及“SupplierMaster → 订单服务端投影 → Runtime/Schema → 详情/打印DOM”的字段来源契约未建立。
- 解决方案：SupplierMaster新增`delivery_address`并补全测试数据；订单服务端只读投影新增`supplierDeliveryAddress`；详情和打印通过受治理Schema/ViewModel展示五项供应商信息；列表只保留供应商名称。
- 对应规则：`SUPPLIER-DELIVERY-ADDRESS-001`、`PURCHASE-ORDER-SUPPLIER-VIEW-001`、`PURCHASE-ORDER-PRINT-SUPPLIER-001`、`PAGE-FIELD-SOURCE-UNIQUE-001`。
- 禁止边界：不修改采购订单创建、价格、交期、MaterialMaster或Gate逻辑，除SupplierMaster基础资料外Business Write Count为0。

## CASE-EMD-001 企业基础资料首页使用旧样例集合统计

- 发现与修复版本：`V1.14.2.8.4.27.2.29`
- 问题描述：企业基础资料首页“物料档案”读取 `manufacturingFoundationStore.materials.length`，显示5个；正式 MaterialMaster Runtime 为80个，供应商、关系和价格卡片也存在相同的第二来源风险。
- 根因：首页汇总卡片没有服务端统计 Runtime，直接对页面私有 Store 集合计数。
- 解决方案：建立 `MaterialSupplierRelationRuntime`、`SupplierMaterialPriceRuntime` 和唯一聚合入口 `MasterDataStatisticsRuntime`；页面通过只读 API/Provider 消费四个同名统计字段，读取失败不回退旧 Store。
- 对应规则：`MASTER-DATA-STATISTICS-SOURCE-001`、`MASTER-DATA-COUNT-CONSISTENCY-001`、`PAGE-FIELD-SOURCE-UNIQUE-001`。
- 禁止边界：不修改 MaterialMaster、SupplierMaster、数据库结构、采购业务或 Gate；Business Write Count 为0。

## CASE-EMD-002 物料供应商关系仅来自页面样例导致业务事实覆盖不足

- 发现与治理版本：`V1.14.2.8.4.27.2.30`
- 问题描述：企业基础资料仅显示1条页面样例关系，无法反映采购申请、询价、报价、核价、推荐、Gate及采购订单历史中真实使用过的物料/供应商组合。
- 根因：缺少统一的服务端 `MaterialSupplierUsageMatrix` 和 `MaterialSupplierRelation Runtime`；页面私有 Store 被误作正式关系来源，首页统计也只能对旧集合计数。
- 解决方案：只读扫描既有业务事实，以严格的 MaterialMaster/SupplierMaster 编码匹配建立使用矩阵；仅当推荐、核价、报价/比较或采购历史提供有效依据时投影正式关系。采购申请或询价单独出现的组合保留“待人工确认”，不得自动建关系。
- 字段规则：主供应商只接受明确推荐、核价或比较结论；交货周期必须保留报价、价格事实或人工基础资料来源；无来源时保持空值，禁止猜测。
- 对应规则：`MATERIAL-SUPPLIER-SOURCE-001`、`MATERIAL-SUPPLIER-UNIQUE-001`、`MATERIAL-SUPPLIER-MAPPING-001`、`MASTER-DATA-STATISTICS-RELATION-001`。
- 回归入口：`verify_material_supplier_relation_v11428427230`、`verify:material-supplier-relation-runtime:v11428427230`、基础资料首页/关系列表/采购申请真实浏览器验收。
- 禁止边界：不修改 MaterialMaster、SupplierMaster、SupplierMaterialPrice、PurchaseRequest、PurchaseOrder、Gate 或数据库结构；业务交易写入为0。

## CASE-EMD-003 基础资料高级筛选控件尺寸与布局不一致

- 发现与治理版本：`V1.14.2.8.4.27.2.31`
- 问题描述：基础资料高级筛选区域同时出现34px、67px和100px控件高度，查询、范围和操作条件混排，页面间宽度、间距和响应式行为不一致。
- 根因：统一筛选组件只约束字段渲染，未建立语义分行与尺寸Runtime；部分基础资料页面又维护私有四列栅格，导致公共组件和页面样式并行生效。
- 解决方案：建立`PCE-ADVANCED-FILTER-LAYOUT-V1.0`，统一输出查询条件、范围条件、操作按钮三行；控件高度固定36px，字段最小宽度180px，按1440/1024/768以下断点形成4/3/2/1列，并由真实浏览器计算样式验收。
- 回归保护：`FILTER-LAYOUT-HEIGHT-001`、`FILTER-LAYOUT-WIDTH-001`、`FILTER-LAYOUT-RESPONSIVE-001`及`verify:pce-filter-layout:v11428427231`。
- 禁止边界：布局治理不得修改主数据、Provider、业务Runtime、采购流程、订单或Gate；Business Write Count为0。

## CASE-EMD-004 基础资料列表重复声明字段并绕开既有元数据能力

- 发现与治理版本：`V1.14.2.8.4.27.2.32`
- 问题描述：部分基础资料列表在页面内声明列名、列数量和筛选控件；系统已有 Schema、Registry、列表 Runtime、筛选 Runtime 与下拉 Provider，却没有形成统一消费链。
- 根因：历史基础资料页面早于 `PCE-ENTERPRISE-LIST-CONTRACT-V1.1`，字段数组兼任表格、表单、筛选与导入职责，后续能力升级没有先执行现有 Meta 扫描。
- 解决方案：先扫描 `meta/schema|runtime|registry|core|components`，扩充既有 `masterDataRegistry`，以薄适配组件复用 `PceEnterpriseListTable`、`PceEnterpriseAdvancedFilter`、`PceBusinessStatus` 和 `listFilterRuntime`；关系页继续使用原 `MaterialSupplierRelationRuntime` 字段定义。
- 企业配置结论：当前未发现用户级持久化列名、隐藏、排序、筛选与下拉配置闭环；仅提出在现有 Registry 上增加受权限、版本、审计和回滚保护的配置投影，禁止新建平行 Config/Registry。
- 回归保护：`EXISTING-METADATA-SCAN-001`、`DUPLICATE-RUNTIME-CHECK-001`、`HARDCODE-FIELD-SCAN-001`及`verify:pce-existing-intelligence:v11428427232`。
- 禁止边界：不修改基础资料或采购交易事实，不新增第二 Runtime/Registry，不修改数据库；Business Write Count为0。

## CASE-GOV-001 已有智能能力未进入版本启动门禁导致重复建设风险

- 发现与治理版本：`V1.14.2.8.4.27.2.32`
- 问题描述：系统已经具有Schema、Registry、Runtime、CRUD、列表、筛选、下拉、权限和智能分析能力，但开发治理没有要求每个版本在设计前完成能力扫描，目录命名差异容易被误判为能力缺失。
- 根因：既有智能资产散布在`frontend/src/meta`、`backend/workflow_runtime`和模块目录；现行强制执行链缺少“智能化影响评估、已有能力扫描、复用方案、实施边界”。
- 解决方案：在唯一最高总纲下新增《PCE-ERP智能化开发总纲》，建立`INTELLIGENCE-FIRST-001`、`PCE-CAPABILITY-REUSE-001`和`DUPLICATE-FRAMEWORK-001`；登记实际目录所有权，顶层目录不存在时不得机械补建。
- 人工边界：智能能力仅提供事实聚合、生成、建议、解释和校验；供应商合并、关系、价格、选择、核价、审批和PurchaseOrder交易动作继续由人工显式Action与既有Guard控制。
- 回归保护：`verifyPceIntelligenceGovernanceV11428427232.mjs`必须验证唯一最高入口、四项启动流程、能力清单、九项供应商评估、禁止目录、业务代码Hash和数据库Hash不变。

## CASE-SCM-073 价格能力分散且历史样本不足导致智能结论不可成立

- 发现与治理版本：`V1.14.2.8.4.27.2.33`
- 问题描述：系统已有报价、比价、核价、推荐和订单价格能力，但SupplierMaterialPrice仅是报价明细Runtime投影；当前只有1条报价明细、0条正式QuoteComparisonFact、13条空历史价格核价准备，无法可靠计算趋势或异常。
- 根因：价格事实没有统一的物料、供应商、时间、有效期、币种、税口径和来源契约；历史订单来源字段也未覆盖Legacy数据。
- 解决方案：新增`PRICE-FACT-MODEL-001`和`PRICE-SOURCE-TRACE-001`，规划扩展既有SupplierMaterialPriceRuntime承载报价、比较、核价和执行四类只读事实；禁止新建价格模块或让Gate/页面成为价格源。
- 人工边界：最低价、最近价、趋势和异常只作为带样本量与规则版本的参考；核价、异常豁免、供应商选择、推荐确认和采购订单执行价格必须人工确认。
- 回归保护：`scanSupplierPriceFactsV11428427233.py`只读输出质量基线；`verifySupplierChainIntelligenceV11428427233.mjs`验证治理契约、数据质量证据、禁止平行框架、业务源文件和数据库Hash不变。

## CASE-SCM-074 供应商价格缺少统一只读事实模型与期间唯一投影

- 发现与治理版本：`V1.14.2.8.4.27.2.34`
- 问题描述：报价明细、供应商物料基础价格与采购订单历史价格没有统一模型；页面若直接拼接这些来源，将出现同一供应商、物料和生效日期多价、来源丢失或历史覆盖风险。
- 根因：V2.33仅完成价格事实规划，尚未形成统一字段契约、来源优先级、期间唯一投影、历史候选保留和只读查看入口。
- 解决方案：在既有 `master_data_statistics_runtime.py` 所有权内新增不可变 `SupplierPriceFactModel` 与只读 `SupplierPriceFactRuntime`；按 `SupplierQuotation > SupplierMaterialPrice > PurchaseOrderHistory` 选择当前期间事实，并通过 `historyModels` 保留全部来源候选。
- 页面方案：`#/foundation/erp/supplier-price-facts` 复用既有 Metadata Registry、页面壳、企业列表、高级筛选和状态组件，仅查看服务端事实，不提供价格维护或自动决策。
- 回归保护：`PRICE-FACT-SOURCE-001`、`PRICE-FACT-TRACE-001`、`PRICE-FACT-UNIQUE-001`、`PRICE-HISTORY-PROTECT-001`、`PRICE-NO-AUTO-DECISION-001`及`verify:supplier-price-fact:v11428427234`。
- 禁止边界：不修改 MaterialMaster、SupplierMaster、MaterialSupplierRelation、PurchaseOrder、Gate、采购流程或数据库结构；Business Write Count为0。

## CASE-GOV-002 自动验收PASS但缺少真实浏览器证据仍可能错误签发READY

- 发现与治理版本：`V1.14.2.8.4.27.2.36`
- 问题描述：部分版本能够通过源码扫描、自动测试和Build，但未逐页打开真实URL、核对用户可见区域和字段、点击声明按钮或保存本次截图，最终报告仍可能输出READY。
- 根因：既有规范分散规定了运行证据与人工反向校验，但没有统一的逐页证据必填模板，也没有把自动验收、浏览器人工验收和Build组合成不可绕过的READY判定公式。
- 解决方案：新增《真实运行验收规范》与`CODEX-COMMAND-004`，Codex任务固定使用九段式执行模板；逐页记录URL、标题、顶部/中部/底部、字段、按钮、期望、实际和截图；三项门禁必须全部PASS。
- 失败处理：人工FAIL或证据不足分别输出FAIL/UNKNOWN；自动PASS、人工FAIL固定为`AUTO_PASS_HUMAN_FAIL`，执行案例登记、根因定位、规范/自动验收补强、重新Build和人工复验，禁止READY。
- 回归保护：`HUMAN-ACCEPTANCE-REQUIRED-001`、`PAGE-EVIDENCE-001`、`READY-GATE-001`。
- 禁止边界：治理检查只验证证据结构和READY逻辑，不能替代真实浏览器本身；历史截图、Provider直调、模拟DOM和源码字符串不得冒充当前页面验收。

## CASE-EMD-005 基础资料筛选选项、结果计数与页面动作边界不一致

- 发现与治理版本：`V1.14.2.8.4.27.2.35`
- 问题描述：基础资料页面虽已复用企业列表与高级筛选组件，但编码、供应商和物料筛选仍可能只从当前页面结果生成选项；筛选后的分页使用当前结果而统计卡仍显示服务端原始总数；事实、主数据与配置页面的操作按钮缺少统一分类。
- 根因：既有 `masterDataRegistry`、Filter Runtime 与 Dropdown Provider 尚未形成“字段类型—正式主数据选项—查询投影—结果计数—动作策略”的完整消费链，页面继续承担部分推断职责。
- 解决方案：兼容扩展既有 Remote Select Provider，以 SupplierMaster/MaterialMaster 正式事实接口提供下拉；由同一 `filteredRows` 投影驱动当前结果数与分页；在既有 Registry 声明 `fact/master/config` 及其 `view`、`view/edit`、`view/edit/toggle-status` 策略，公共列表只按策略渲染。
- 事实边界：SupplierPriceFact 固定为只读事实并增加单日历史执行价格、日期区间有效价格说明；服务端总数只作独立基线，不冒充筛选结果。
- 回归保护：`FILTER-DROPDOWN-COMPLETE-001`、`FILTER-COUNT-SYNC-001`、`MASTER-DATA-ACTION-001`、`FACT-VS-MASTER-PAGE-001` 及 `verify:master-data-runtime-standard:v11428427235`。
- 禁止边界：不新建 Metadata、Registry 或 Runtime，不修改 MaterialMaster、SupplierMaster、SupplierPriceFact、PurchaseOrder、Gate、数据库或任何业务事实；Business Write Count为0。

## CASE-PCE-REAL-RUNTIME-001 自动验收5成功/0失败，但真实页面1成功/11失败

- 发现版本：`V1.14.2.8.4.27.2.45.6`；关联问题版本：`V1.14.2.8.4.27.2.45.5`。
- 问题现象：旧报告记录批量确认成功 5、失败 0，并将自动浏览器结果写为 `Browser Human Acceptance: PASS`；用户在真实页面选取另一组已完成任务后得到成功 1、失败 11，页面仍大量出现 `legacy_verified_fact`。
- 自动测试结果：自动浏览器从列表首部选择 5 条 `SESSION-PAP-*`，其来源为 5 张真实 `SupplierQuotation` 的 JSON 明细投影，归档结果为 Server Memory 中的 `PAR-*` 与 `SMP-CONF-*`，成功 5、失败 0。
- 人工运行结果：人工选择集合混入 11 条持久化 `legacy_verified_fact`；这些对象没有可精确重读的 `SupplierQuotation` 明细，归档服务返回来源不存在，只有真实报价投影成功。
- 对象差异：页面当前合并 9 条非持久 `session_acceptance` 投影与 13 条持久化旧事实。自动选择集合、人工选择集合不是同一批对象；页面虽显示报价业务编号，但未展示底层 `SupplierQuotation.pk`，Server Memory 结果也不具备跨进程持久身份，因此同对象证据不完整。
- 根因：把验收专用的会话投影与正式持久核价对象合并在同一列表，自动化按位置选择真实投影，而人工操作覆盖旧事实；报告只比较统计结果，没有锁定点击对象 ID，并错误地把自动浏览器签成了人工验收。
- 错误开发模式：以 Fixture/会话投影/内部调用证明页面链路；只报告数量；把自动浏览器等同人工验收；以 `Business Write Count: 0` 遮蔽数据建设版本的授权写入。
- 正确治理方式：先按 Browser、API、Runtime、Service、Database 逐层还原对象，分类 `REAL_SUPPLIER_QUOTATION`、`LEGACY_VERIFIED_FACT`、`OTHER`，逐条核对来源 ID；人工验收由用户独立签发。
- 以后禁止：为 PASS 新增对象、把 legacy 事实转换报价、用 Server Memory 冒充持久业务对象、按行号而非对象 ID 选取、自动签发人工 PASS。
- 自动门禁：`SAME-OBJECT-ACCEPTANCE-001`、`HUMAN-ACCEPTANCE-AUTHORITY-001`、`AUTHORIZED-BUSINESS-WRITE-001`、`RUNTIME-BEFORE-TEST-001`、`V2455-SUCCESS-OBJECT-TRACE-001`、`REAL-RUNTIME-OBJECT-TRACE-001`。
# CASE-SCM-PRICE-004 核价完成约20条但有效价格仅8条

- 现象：采购核价页面已完成对象超过20条，而供应商物料有效价格曾显示8条。
- 根因：核价集合混合历史验收事实、开发测试报价事实和正式供应商报价；“已完成”仅说明流程结束。有效价格还要求正式报价明细、人工通过、显式确认、字段完整且未重复归档。
- 正确处理：逐对象对账并显示价格归档状态；历史验收事实明确 `Can Archive=false / No SupplierQuotation Object`；程序来源编码只以统一中文标签展示。
- 禁止处理：新增测试对象凑数、把历史事实转换正式报价、直接插入有效价格或让最低价自动归档。
- 税率规则：正式报价税率优先，否则取企业采购默认税率；授权维护仅限税率和有效期，并保留审计。

# CASE-SCM-PRICE-005 历史核价事实无法生成有效价格导致价格归档长期失败

- 涉及版本：V45.1 至 V45.7。
- 根因：错误地把 `SupplierQuotation` 当作 `SupplierMaterialPrice` 唯一合法来源，同时用 Server Memory 保存所谓正式价格，导致人工核价完成后历史来源永远不能通过新决策归档，已确认价格又会在进程重启后消失。
- 修正：原始价格事实保持真实类型；新的人工核价、供应商选择和确认动作形成持久 `PriceApprovalResult`，再一对一生成持久 `SupplierMaterialPrice`。
- 防复发门禁：确认动作幂等、原始来源不可篡改、生效日期来自服务端人工事件、失效日期不自动生成、历史 `SupplierPriceFact` 不写入。
- V45.8 真实运行补充：数据库 `supplier_material_price` 与 `SupplierMaterialPriceRuntime` 均有16条，但 API 运行进程缺少 `originalSourceTypeLabel（原始来源类型中文）` 字段，前端严格契约在第一行抛出 `SupplierMaterialPrice Runtime field unavailable: originalSourceTypeLabel`，于是页面将 Runtime 置空并显示0条。真实根因是后端运行进程与前端契约版本不一致，不是缓存、测试事务回滚或数据丢失。
- V45.9 修正：四层同对象门禁固定为 `Database = Runtime = API = Browser`；页内刷新强制重新请求正式 API。4条原显示“待确认报价”的历史对象实际均引用不存在的 `SUP-000001/SUP-000002`，正式 SupplierMaster 无编码或唯一名称映射，故统一改为 `SUPPLIER_MAPPING_FAILED（供应商映射失败）/不允许归档`，禁止猜测映射或补造供应商。
