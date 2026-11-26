# PCE-ERP自动验收与证据治理规范

# 文档信息

- 版本：V1.14.2.8.4.27.2.4.3
- 用途：统一自动验收、人工反向验收、扫描、证据、金丝雀和归档
- 适用范围：PCE-ERP全部版本、页面、流程和治理任务
- 优先级：高
- 关联规范：06模块专项、07案例库
- 维护方式：持续更新

## 1. 验收原则

Acceptance负责证明，不执行Domain规则、不推进状态、不补数据。自动验收负责可重复契约、事实、Guard、边界、回归和Build；人工验收负责真实可见性、操作性、语义、异常反馈和业务路径。两者任一失败均不得READY。

## 2. 统一验收输出

```text
Version PASS
Governance PASS
Boundary PASS
Schema PASS
Runtime PASS
Rule PASS
Guard PASS
Acceptance PASS
Build PASS
```

不适用项必须输出`N/A`及原因，不得省略。最终结果同时输出`PASS/FAIL/N/A/UNKNOWN`汇总和任务指定状态。

## 3. 失败输出契约

每个失败必须输出：

```text
文件
  -> 位置
  -> 问题
  -> 原因
  -> 建议
```

脚本必须返回非零退出码。读取失败使用`read_failed`，证据缺失使用`UNKNOWN`；禁止把异常吞掉后输出PASS。

## 4. 验收层次

1. Governance：规范加载、规则映射、案例和边界；
2. Boundary：禁止文件、模块、写入和外部副作用；
3. Schema：字段、类型、状态、关系和版本；
4. Runtime：真实Provider、模式、上下文、刷新和恢复；
5. Rule：Domain正向与反向规则；
6. Guard：状态、数据、权限、幂等、完整性阻断；
7. Acceptance：页面/流程/批量/金丝雀/人工证据；
8. Regression：Golden Path和公共能力不可破坏；
9. Build：目标代码可构建；治理-only任务以业务Hash不变和验证脚本可执行作为Build证据。

静态文件存在不能替代Runtime，Build不能替代业务验收，自动PASS不能覆盖人工FAIL。

## 5. 自动扫描与数据绑定

扫描必须使用稳定路径和机器契约，覆盖：唯一对象/页面/Route、Schema字段、Provider事实来源、Runtime模式、Action Contract、Guard、Handoff、状态迁移、列表契约、数据数量、业务键、刷新一致性和禁止副作用。

API、页面、诊断、strictFacts和验收使用同一服务端事实。验证数据绑定时记录来源接口、requestId、tenant、batch、resultCount、业务键集合和factLoadStatus。

## 6. Batch Completeness

所有批量提交、确认、审批、派工、放行或处理动作输出：

- `Total Item Count`；
- `Completed Item Count`；
- `Pending Item Count`；
- `Action Disabled`；
- `Confirm Action Enabled`。

必须满足`Total=Completed+Pending`。`Total=0`或`Pending>0`时按钮与服务端入口同时阻断，状态保持；全部完成后验证动作恢复。

## 7. 金丝雀治理

- Canary A：正常最小样本；
- Canary B：批量/边界/多对象样本；
- Canary C：缺数据、无权限、非法状态或异常阻断。

每个样本记录来源、编号、输入/输出数量、预期、实际、模式、执行人、时间、证据、业务写入和生产写入。Canary不得冒充Production，不得调用未授权生产写接口。

## 8. 人工反向验收

人工验收记录验收人、时间、环境、真实对象、入口、操作步骤、可见字段、按钮、异常、刷新和结果。自动PASS/人工FAIL时状态必须降级为`AUTO_PASS_HUMAN_FAIL`，进入案例库，补充规范和自动反向用例后重新验收。

## 9. 数据保护证据

涉及已有业务对象时输出Before/After/Refresh Count、业务键集合、来源匹配、下游引用、生产API、Canary隔离、各类写入数和`productionUserDataWritten`。任何非授权变化阻断验收。

治理-only任务必须冻结并复核业务代码树Hash、后端代码Hash和数据库Hash。

## 10. 归档

| 资产 | 位置 |
|---|---|
| 核心和模块规范 | `docs/governance`新体系目录 |
| 历史规范 | `docs/governance/archive` |
| 单页/版本验收 | `frontend/test-results`或指定验收目录 |
| 版本冻结 | `CheckpointArchive` |

验收报告不得改写治理规则；冻结归档不得覆盖历史版本。

## 11. 治理体系自检

治理重构必须检查：唯一最高入口、五个核心规范、模块和案例体系、归档标记、孤立活跃规范、失效引用、依赖循环、重复最高规则、业务代码零修改。任何失败阻断`PCE_GOVERNANCE_SYSTEM_REFACTOR_READY`。

## 12. DATA-PROTECTION-RUNTIME-001 人工数据保持验收规则

凡页面、Provider、Runtime、流程或自动计算涉及人工录入、人工确认、人工选择、人工审核或人工调整数据，必须建立不可变保持验收。验收必须使用同一业务对象、人工数据版本和字段集合，逐项验证：

1. 页面刷新后，人工数据与刷新前完全一致；
2. 重新加载Provider后，人工数据完全一致，系统事实合并不得覆盖人工确认；
3. 流程跳转到下一节点并返回后，人工数据及版本保持一致；
4. 退出并重新进入页面后，人工数据从权威事实恢复且保持一致；
5. 自动计算、重新计算、后台同步或默认初始化运行后，人工结果保持不变。

每个场景必须记录：业务对象编号、人工字段、Before值、After值、人工数据版本、Action记录、Provider来源、Runtime上下文、预期、实际和结果。通过条件为人工字段值与版本均一致；任何字段被系统值、默认值、空值、旧值或建议值替代均为`FAIL`。

验收必须同时包含以下反向用例：

- Provider返回新的系统计算值时，已有人工值仍优先；
- Runtime恢复旧上下文时，不得回退人工版本；
- 默认初始化再次执行时，不得覆盖人工数据；
- 没有明确Action时，任何人工字段变化必须被Guard阻断；
- 经确认、撤回、修改或重新提交Action变更时，Before/After、操作者、原因和历史版本可追溯。

统一优先级断言为：

```text
人工确认结果 > 系统计算结果 > 默认规则结果
```

存在`FAIL`或`UNKNOWN`时，人工数据相关业务节点、页面或版本不得输出READY。

## 13. SCM正式采购订单创建证据

`SCM-PO-CREATE-RUNTIME-001`：正式采购订单创建验收必须覆盖无 Gate、Gate 未就绪、准入失败、人工草稿未保存或字段不完整时零写入；显式人工动作成功时，每个已确认供应商分组仅创建一个 `draft` 订单聚合；同一`Gate + Supplier`重放时零新增。证据必须同时证明来源 Gate、推荐、询价、核价、确认人、确认时间、报价、核价及资质证据完整，人工供应商、数量、价格、交期、备注和审批意见经 Provider 重载与页面重入保持不变。

验收必须输出 `Automatic Creation=NO`、`Legacy Orders Changed=NO`，并分别记录首创与幂等重放的 `Business Write Count`。任何自动提交、自动审批、自动下达、自动发布、自动发送供应商，或历史订单变化，均直接判定为 FAIL。

## 14. SCM-PO-ITEM-SOURCE-RUNTIME-001 采购订单明细来源证据

每条采购订单明细必须验证采购申请、询价、报价比较、核价和 Gate 编号完整，物料编码和名称一致，`requestedQuantity -> orderedQuantity -> remainingQuantity -> confirmedQuantity` 可解释，供应商分配来源、报价、核准价、人工确认价、需求日期、供应商交期和人工确认交期可追溯。缺少来源或人工确认值时创建 Action 必须零写入。

验收必须包含多供应商样本：一个采购草稿形成多个可见且已确认的供应商草稿，显式创建后每张采购订单只能含一个供应商；同一物料分配给多个供应商时输出`PURCHASE_ORDER_ITEM_MULTI_SUPPLIER_ALLOCATION`并整体零写入。不得自动选取供应商、自动分量或在页面加载/草稿保存时创建订单。还必须证明保存后的供应商、确认数量、确认价格、供应商级交期和备注在 Provider 重载、刷新与页面重入后不被建议值覆盖；Legacy 订单与已存在正式订单保持不变。

## 15. SCM-PO-QUANTITY-RUNTIME-001 采购数量核算证据

验收必须证明`建议采购数量 = 需求数量 - 可用库存 - 已采购未入库数量`（结果不小于零），并分别记录各输入的Provider来源和完整性状态。未接入真实库存时必须显示`NOT_CONNECTED/PARTIAL`，不得伪装为完整库存事实。

人工确认量低于或等于原建议量时允许无原因保存；高于建议量时必须保存原值、新值、原因、修改人和修改时间，无原因增加必须输出明确阻断且业务写入为零。刷新、Provider重载和页面重入后保持一致；任何自动改量、自动创建采购订单或历史订单变化均为FAIL。

## 16. SCM-PO-DRAFT-RUNTIME-001 采购订单人工草稿证据

验收必须证明只有一个`PurchaseOrderDraft`业务身份和一个草稿Store；草稿状态覆盖`editing/confirmed/ready_for_creation`。未保存草稿、人工确认不完整、数量无效、增加数量无原因、版本冲突或Gate失效时，创建Action必须阻断且正式采购订单写入为零。

必须验证确认供应商、确认数量、确认价格、确认交期、备注和调整原因在保存、刷新、Provider重载和页面重入后保持一致，并保留原建议数量、调整后数量、修改人、修改时间及历史。草稿保存不等于采购订单创建，不得自动提交、审批、下达或改变Legacy订单。

## 17. SCM-PO-DRAFT-ITEM-INCLUSION-001 草稿物料纳入验收

确认采购数量为0的明细必须以`excluded`保留在草稿并允许保存，正式采购订单明细数不得包含该行；确认数量大于0的明细标记为`included`。创建前必须至少存在一个完整的`included`明细，供应商拆分、来源完整性和人工字段Guard只对纳入行执行，同时不得删除排除行的草稿证据。

验收至少包含：需求量0且确认量0保存成功；建议量365、确认量370并填写原因保存成功；增量无原因阻断；确认量超过建议量10倍阻断；刷新后状态、数量、原因、供应商、价格、交期和备注保持。人工页面验收不得实际创建PurchaseOrder。

## 18. SCM-PO-SUPPLIER-SPLIT-RUNTIME-001 供应商草稿拆分证据

验收必须证明唯一`PurchaseOrderDraft`内可以形成多个`SupplierPurchaseDraft`，每个分组只含一个供应商并独立保存`deliveryDate/supplierRemark/approvalRemark/items`。明细必须具有`materialCode/supplierId/confirmedQuantity/confirmedPrice`，同一物料跨供应商重复分配时整体零写入阻断。

显式创建样本必须证明N个有效供应商分组形成N张单供应商`draft`订单，且`Gate + Supplier`幂等重放不新增；任一分组不完整时不得产生部分订单。刷新、Provider重载和页面重入后，各分组交期、备注、审批意见以及明细供应商、数量和价格保持一致。自动审批、自动发布、自动发送、Legacy订单变化均为FAIL。

## 19. SCM-PO-SUPPLIER-ASSIGNMENT-UI-RUNTIME-001 供应商分配页面证据

供应商采购草稿信息列表只展示序号、供应商编码、供应商名称、交货日期、审批意见和备注，不得在该列表展示物料数量、采购金额或总金额。物料明细必须接入企业列表契约，提供供应商、物料编码、物料名称筛选，固定身份列与操作列，并在表格内部拥有横向滚动。

物料供应商只能从当前`SupplierPurchaseDraft`集合选择，禁止自由输入不存在的供应商。验收必须证明每条明细仅归属一个供应商、显示分配来源、人工分配及数量/价格/交期/备注在刷新后保持，且正式拆分仍为每张PurchaseOrder单一供应商；页面验收不得自动创建PurchaseOrder。

## 20. SCM-PO-DRAFT-UI-REFINEMENT-RUNTIME-001 草稿页面过滤与入口证据

供应商采购草稿信息必须接入企业列表契约并证明一个供应商一行，只包含供应商编码、名称、交货日期、审批意见和备注等供应商级业务字段，不得显示物料数量、采购金额或总金额。物料明细可见投影必须严格等于`included && confirmedQuantity > 0`，同时证明被过滤的`excluded`/零数量行仍保留在草稿证据中且正式订单明细不包含它们。

数量异常验收必须证明列表保留“正常/需填写原因/严重异常”状态，并将原因聚合到采购数量核算说明区域，页面不得逐行重复大面积红色提示。`/scm/purchase-order`的“新增采购订单”只能导航到`/scm/purchase-order/create`，目标页必须执行`PurchaseOrderCreationGuard`；导航过程业务写入为0，禁止列表页直接调用`CREATE_PURCHASE_ORDER`。

## 21. SCM-PO-SUPPLIER-REAL-SPLIT-RUNTIME-001 真实供应商拆分证据

验收必须使用至少三个供应商和多条物料证明：`SupplierPurchaseDraft.length`等于物料行中的不同明确供应商数，每个供应商草稿只包含一个供应商，名称不存在拼接，且每个物料的供应商身份与所属分组一致。草稿头汇总供应商不得作为物料供应商兜底；旧聚合名称只有存在同物料推荐证据时才允许只读恢复，人工明确分配必须保持。

数量一致性必须覆盖：需求0且确认数量大于0时保存和创建均阻断、业务写入0；需求大于0且确认数量0时允许保留草稿但不进入有效投影；确认数量大于0但供应商缺失时阻断。页面有效物料数必须等于`requestedQuantity > 0 && confirmedQuantity > 0`的行数，供应商数量必须直接读取`SupplierPurchaseDraft.length`。

## 22. SCM-PO-DRAFT-SOURCE-RUNTIME-001 草稿真实数据源证据

验收必须输出页面字段、Provider、Runtime和Domain Model的逐层来源，证明供应商列表只来自`SupplierPurchaseDraft[]`、供应商数量只来自数组长度、物料供应商只来自`PurchaseOrderItem`行级字段。必须反向注入聚合供应商名称，证明其不能形成供应商草稿数据源。

必须验证显式`requestedQuantity=0 && confirmedQuantity>0`在页面草稿加载前FAIL，且Provider不得将显式0回填为上游建议数量。刷新、Provider重载与页面重入后，人工供应商分配、确认数量、价格、交期和备注必须保持；验收期间业务写入和PurchaseOrder新增均为0。

## 23. SCM-PO-MATERIAL-ELIGIBILITY-RUNTIME-001 采购物料准入证据

验收必须混合构造有效、无需求、无供应商和未选择推荐项，证明Guard逐行给出PASS/FAIL/NOT_SELECTED。采购物料数必须只统计PASS行，供应商草稿和供应商数量必须只由PASS行生成；FAIL及NOT_SELECTED项保留在只读推荐证据区域，不得进入采购订单物料列表。

创建Action必须复用Guard，并证明传入正式订单构建器的明细全部满足正需求、正确认量和明确供应商。过滤前后人工字段与源推荐证据必须保持，人工页面验收不得创建PurchaseOrder，业务写入计数必须为0。

## 24. SCM-PO-CREATION-CONTEXT-RUNTIME-001 多采购申请创建上下文证据

验收必须使用至少六个来源采购申请，证明Gate数组、`PurchaseOrderCreationContext.purchaseRequestIds[]`、Provider、草稿和页面来源列表数量一致，且不存在只取第一项。必须覆盖同物料跨申请合并，验证合并数量正确、`sourcePurchaseRequestIds[]`完整、人工供应商与确认数量不被覆盖。

正式订单只读构建投影必须保留订单头完整来源数组及明细逐来源数组；测试不得调用持久化仓库创建订单。刷新、Provider重载和页面重入后来源及人工字段保持，PurchaseOrder新增=0、业务写入计数=0、`productionDataWritten=false`。

## 25. DATA-EXTRACT-001 业务数据提取完整性规则

Provider、Runtime、Action、Adapter以及验收数据适配器提取集合型业务事实时，必须保持集合语义并完整传递。禁止通过`array[0]`、`sourceIds[0]`、`firstItem`、单值回退或隐式类型转换把多条数据降为一条；禁止只校验第一条后宣称整个集合通过。

确有单对象业务语义时，必须由上游契约明确声明唯一性，并在降维前验证输入数量严格等于1；零条或多条均显式失败。不得以页面只显示一条、当前选中一条或兼容旧字段为理由丢弃其余来源。

自动验收必须扫描高风险单条读取模式，并结合运行夹具验证完整数组从Source到Provider、Runtime、Action/Handoff及输出逐层保持。静态命中只能作为风险线索，最终结果必须结合字段语义判定；未经证明的降维输出`FAIL/UNKNOWN`。

## 26. ARRAY-COMPLETENESS-001 数组完整性验收规则

多来源业务场景，包括多个采购申请、多个供应商、多个物料和多个来源单据，必须逐层记录并比较：

```text
Input Item Count
Output Item Count
Source Relation Count
Input Business Keys
Output Business Keys
Missing Keys
Unexpected Keys
Duplicate Keys
```

通过条件为输入、输出与来源关系符合声明的映射规则，业务键逐项可追溯，且不存在非授权缺失、增加或重复。若业务规则执行合并或拆分，数量可以不同，但必须提供确定的映射关系和守恒证据；不得用“首条正确”替代集合完整性。

验收至少覆盖单条、多条、空数组、重复项、乱序和中间层截断反向用例。任一层只读取第一条、数组静默变单值、来源数量不一致或无法解释映射时，必须阻断后续动作并输出FAIL。

## 27. 运行治理增强验收项

所有适用版本必须在统一验收输出中增加：

```text
PAGE_FREEZE_CHECK PASS/FAIL/N/A
FLOW_VISUAL_FREEZE_CHECK PASS/FAIL/N/A
COMPONENT_IMPACT_CHECK PASS/FAIL/N/A
DATA_IDENTITY_CHECK PASS/FAIL/N/A
DATA_EXTRACT_CHECK PASS/FAIL/N/A
ARRAY_COMPLETENESS_CHECK PASS/FAIL/N/A
```

- `PAGE_FREEZE_CHECK`比较页面区域、交互、布局、容器和滚动基线；
- `FLOW_VISUAL_FREEZE_CHECK`比较流程名称、节点、关系、箭头、容器和滚动基线；
- `COMPONENT_IMPACT_CHECK`核对公共组件的`Affected Pages List`及逐页回归结果；
- `DATA_IDENTITY_CHECK`核对`ObjectId/BusinessNo/SourceRelations`职责和稳定性；
- `DATA_EXTRACT_CHECK`核对集合提取链无未授权降维；
- `ARRAY_COMPLETENESS_CHECK`核对输入、输出、来源数量和业务键映射。

治理-only任务的Build证据继续执行第4节和第9节：业务代码树、后端代码和数据库Hash保持不变，治理规则可检索、结构完整且验收检查可执行。

## 28. PCE-LIST-DISPLAY-GOVERNANCE-001 列表展示治理验收

列表展示治理版本必须验证`LIST-DISPLAY-001`、`TECH-FIELD-SEPARATION-001`和`TABLE-ROW-HEIGHT-001`均由既有页面与列表运行契约承接，不得新建平行治理体系。自动证据至少包含：

- 默认业务列不存在ObjectId、SourceRelations、完整GateId、API、Runtime诊断、JSON和内部状态码；
- 来源字段只显示业务摘要，详情页仍保留完整来源链；
- 业务列表为紧凑单行，长文本具备截断与Tooltip/详情入口，操作列固定右侧；
- 服务端持久事实仍加载且默认折叠，“查看诊断信息”可以展开；
- `PAGE_FREEZE_CHECK`、`COMPONENT_IMPACT_CHECK`和受影响页面回归通过；
- Provider、Action、Store、业务模型、数据库及业务数据Hash保持，业务写入计数为0。

验收标志为`PCE_LIST_DISPLAY_GOVERNANCE_READY`。任一完整技术字段仍在默认列表展示、诊断事实被删除、详情来源丢失、紧凑模式破坏输入或动作、公共组件消费者未完成回归时必须输出FAIL。

## 29. BUSINESS-CAPABILITY-CHECK 历史业务能力回收验收清单

所有ERP业务列表的自动与人工验收必须输出`BUSINESS_CAPABILITY_CHECK PASS/FAIL/N/A`，并逐项记录：

```text
Import Template        Required/Supported/N/A + Evidence/Reason
Data Import            Required/Supported/N/A + Evidence/Reason
Data Export            Required/Supported/N/A + Evidence/Reason
Advanced Filter        Required/Supported/N/A + Evidence/Reason
Sort                   Required/Supported/N/A + Evidence/Reason
Pagination             Required/Supported/N/A + Evidence/Reason
Batch Action           Required/Supported/N/A + Evidence/Reason
Permission Control     Required/Supported/N/A + Evidence/Reason
Operation Log          Required/Supported/N/A + Evidence/Reason
Rule-calculated Risk   Required/Supported/N/A + Source/Rule
Risk Color Mapping     Required/Supported/N/A + Label/Color Evidence
```

### 29.1 导入能力检查

适用导入的列表必须验证模板字段说明、格式、必填项、枚举/主数据要求和模板版本；运行证据必须覆盖合法文件、格式错误、必填缺失、主数据不存在、重复业务键、无权限和重复提交。必须证明执行顺序为校验、错误反馈、预览、人工确认、受控写入，确认前及任一阻断场景业务写入为0；审计包含人员、时间、文件摘要、范围和逐项结果。

### 29.2 导出能力检查

适用导出的列表必须验证当前结果与筛选/排序/权限范围一致，隐藏技术字段和敏感字段未泄露，并存在导出人员、时间、范围、数量、业务键摘要和结果日志。至少覆盖无权限、空结果、超范围请求和导出失败；空文件或前端拼接结果不得替代真实成功证据。

### 29.3 批量操作检查

适用批量动作必须验证已选、可执行、不可执行和影响范围可见，并输出`Total/Completed/Pending/Success/Failed`及逐项原因。按钮和服务端Guard必须共同覆盖零选择、混合状态、数据缺失、无权限、重复提交和全部成功；部分成功只有模块专项明确授权时才可PASS。操作日志必须能按Action和业务键追溯。

### 29.4 风险计算与颜色检查

风险字段必须记录权威输入、规则版本、计算时间、计算结果和中文标签；人工直接编辑控件必须不存在，人工风险反馈不得改变等级。颜色断言必须读取业务等级映射而非扫描任意CSS，并验证中文标签、正常/提示/警示/严重警示语义、未知状态和无障碍替代文本一致。

### 29.5 判定与治理-only边界

能力适用性必须由业务语义决定。`N/A`无业务原因、仅检查按钮存在、用前端模拟代替Action/Guard/审计、风险等级可人工改写、颜色无规则来源或任一必需能力缺失时，`BUSINESS_CAPABILITY_CHECK`为FAIL。治理-only版本以规则可检索、结构完整、相互引用有效、禁止范围Hash不变和规范检查可执行作为Build证据；不得为使清单通过而修改页面或业务代码。

## 30. TEST-DATA-001 开发测试数据治理规则

开发测试数据必须具有明确的数据分类、生成脚本、适用环境和可重建证据。标记为`DEVELOPMENT_TEST_DATA`的数据允许在开发环境删除或重建；验收数据必须保留版本、场景、业务键、输入、结果和证据，未完成归档前不得清理；企业生产数据未经业务所有者授权禁止删除、重建、改号或覆盖。

测试数据只能验证业务模型，不得成为业务模型、编号规则、状态规则或来源关系的定义依据。发现测试数据与模型冲突时，必须先验证模型契约，再通过独立测试数据脚本修复明确标记的数据；禁止在页面、Provider或Runtime中按备注、编号片段、数组位置或其他猜测静默修补，禁止通过删改样本掩盖Provider提取、数量守恒或身份模型错误。

测试数据清理或重建必须输出数据分类、环境、Before/After数量、业务键映射、删除/新增/修改数量、操作者、时间和恢复方式。自动验收不得调用企业生产写接口；未能证明数据分类或环境隔离时，测试数据写入为0并输出`UNKNOWN/FAIL`。

## 31. PRINT-FORM-ACCEPTANCE-001 企业打印表单验收

适用打印单据必须验证`PRINT-FORM-001`及独立`BusinessPrintViewModel`结构，至少输出Header、Basic Information Layout、Six/Eight Column Layout、Detail Section、Approval Section、Role Visibility和Human Data Protection结果。静态检查必须证明打印入口未克隆页面DOM，运行检查必须证明预览由打印模型生成且企业名称与单据名称分行展示。

业务编号必须逐项比较详情、列表、导出和打印使用的权威编号字段；不得接受Gate编号、来源数组拼接或编号解析结果。明细验收必须记录交易明细输入数量、打印输出数量、业务键、来源声明、缺失/额外项，并反向证明Gate、SupplierRecommendation、QuoteComparison等禁止来源没有进入打印明细。

角色检查至少覆盖采购人员、仓库、供应商和管理版：仓库版不得输出价格，供应商版不得输出内部审批、成本、历史价格和推荐依据，管理版可以输出完整业务字段但不得输出未授权技术字段。审批、审核、复核和制表栏的可编辑性必须服从角色权限；验收必须证明空白栏不自动生成审批结果、预览编辑不产生业务写入、刷新前后订单编号、物料、供应商和金额保持一致。任何数据库、交易对象、Gate、生命周期或正式审批变化均为FAIL。
