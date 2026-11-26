# PCE Production 领域开发治理规范 V1.5

## 1. 文档控制

- 层级：Production L7
- 状态：`APPROVED / FROZEN`
- 生效日期：2026-08-29
- 前版：V1.4（保留历史；本文件为现行L7）
- 适用范围：MPS、MRP、ProductionPlan、制造订单、工单、生产用料、工序执行、报工、生产质量、生产库存交接及其分析事实
- 上位规则：L0、Architecture Lock、L1—L6 现行治理、《PCM开发需求文档 V1.5》、《PCM正式裁决记录 V1.0》
- 详细业务需求：继续引用 PCM Requirement ID；本文件不复制需求正文

## 2. 不可违反的领域规则

1. 每个生产开发任务、设计、代码、测试和验收证据必须引用稳定的 PCM Requirement ID。
2. 产品、物料、单位、BOM、工序、路线、工作中心、设备、组织、人员和库存必须来自服务端唯一正式事实；浏览器缓存只可保存界面偏好或显式隔离的 demo/acceptance 数据。
3. `localStorage`、页面数组、静态 rows、样例工厂和前端重算不得成为生产正式事实源；页面、API、Provider、诊断和验收必须读取同一服务端事实。
4. BOM 必须具有唯一身份、版本、明细、正式物料引用、生效/失效、状态和历史；替代料、损耗率等 MRP 输入不得藏在不可治理的自由 JSON 中。
5. 工艺路线必须具有唯一身份、版本、步骤、正式工序、生效基线和历史；标准路线与实际执行路线必须分离。正式资源层级为Company→Department→Workshop→WorkCenter→Operation/Resource；真实资料只确认Workshop时允许Operation和RoutingStep的WorkCenter为NULL/NOT_MAINTAINED，禁止虚构资源通过Gate。
6. MPS 是受控主生产计划，MRP 是基于已发布 MPS、BOM 和供应约束的展开结果；二者不得合并为一个对象。`Demand` 与 `PlanningRequirement` 继续分别承担业务需求事实和计划需求归集/净需求基础。
7. `ProductionPlan` 是计划/交接对象，制造订单是正式制造执行订单，`WorkOrder` 是可执行工作包；三者不得混用或用状态字段伪装为同一对象。
8. 计划、建议、预留、分配和排程不得直接改变 Physical Inventory。实际库存只允许由正式库存事务在授权、幂等、审计和来源完整条件下改变。
9. 工单必须双向追溯到制造订单、生产计划、MRP/MPS 和订单/预测需求；工单计划用料必须锁定 BOM 版本，工序执行必须锁定路线版本。
10. 非标准路线必须通过显式 Business Action，保留原因、权限决定、操作者、时间、原路线、实际路线和 Before/After 证据；不得覆盖标准路线。
11. 报工必须独立保存实际数量、人员、时间、工时和班次；实际用料、设备时间、报废、返工不得覆盖计划值或原始执行事实。
12. 返工、报废、拆分、变更和撤销必须追加新事实或受控冲销；禁止删除或原地覆盖历史生产事实。
13. 生产质量结果必须独立持久化，并关联来源工单、工序、批次、物料/产品、检验规则、执行人和处置结果。
14. 生产批次/序列/条码必须具备稳定身份；从成品到原料批次、工序、人员、质量和库存事务的追溯链不得依赖文本拼接。
15. 生产实际用料、人工工时、制造费用、报废、返工、设备工时和质量损失必须作为正式事实保留，供 KPI、BI 和 ProfitOS 只读使用。
16. 生产业务继续复用现有 `Permission → Role → Responsibility → Position → Employee → Account → AuthorizationService`，不得新建平行权限体系。
17. 每个状态推进必须是现有 Workflow / Business Action 体系中的显式动作，并同时具备状态 Guard、数据 Guard、权限 Guard、幂等和审计。
18. 生产业务继续复用现有审计、业务链追踪、只读验证、风险闭环和自动/人工验收体系；页面按钮可见不等于服务端授权。
19. APS、AI、异常分析、效益计算和改进建议均为建议层；正式排程、业务事实和财务/激励结果必须由有权限人员确认。
20. 行业规则不得写死在页面或算法。`printing`、`wholeHouseWood`、`general` 只定义可配置行业语义，不创建模拟正式数据。
21. 需要验证 BOM、路线、设备或现场执行字段时，必须在对应 Gate 节点索取真实行业资料；不得凭名称、历史样例或推断补齐。
22. OPC UA、Modbus TCP、API 仅为候选接口；没有真实设备资料、安全边界和独立任务授权时，不连接设备、不写采集事实。
23. Foundation Gate 全部 A 类项目通过后，生产基础进入 `FROZEN`；此后任何基础模型、引用、状态或接口变更必须经过影响分析、正式变更控制和回归验收。
24. 产品、物料、BOM 明细、工序、工作中心和设备之间必须使用稳定业务键和正式关系，不得靠名称相等或页面 ID 推断关联。
25. 工单计划用料必须显式追溯 BOM 版本；实际用料必须通过正式库存事务和来源对象追溯，不得回写覆盖 BOM。
26. 每个工序执行事实必须显式追溯路线版本和路线步骤；临时路线、跳序、并行和返工路线都必须是受控偏差事实。
27. 报工对象必须保存计划数量、合格数量、不合格数量、执行员工、班次、开始/结束时间和实际工时，缺失事实不得默认成零。
28. 返工、报废、拆分、撤销和冲销必须保留原对象、来源、原因、责任人、时间和数量变化，原生产事实不可删除。
29. 制程质量结果必须独立于报工和工单状态持久化；质量判定只能由正式规则和显式 Action 推进处置。
30. MPS/MRP/APS 的计算输入、规则版本、运行批次和输出必须可重放；系统建议与人工确认值必须同时保留。
31. 生产主数据或核心引用需要 Schema/Migration 时，必须另立获授权任务，先做影响分析、迁移/回滚设计和旧事实兼容，不得在治理任务中偷改。
32. 样例、canary、acceptance 和真实生产数据必须隔离并可识别；任何数量目标、自动初始化或导入都不得跨边界写入正式租户。
33. 正式工程发布必须锁定ProductVersion、BOMVersion、RoutingVersion和EngineeringDocumentVersion，并形成唯一ProductManufacturingOutput；兼容标量版本仅可作为由正式版本同步的只读投影。
34. 需要工程/制造的SalesOrderItem必须稳定引用ProductDefinition、ProductVersion和有效工程发布组合；普通采购型Material行可为空兼容。多明细订单必须逐行、幂等形成Demand。
35. A2前已经形成的PlanningRequirement直接PurchasePlan/ProductionPlan属于受保护历史；A2新Plan必须保存计划引擎、运行批次、来源版本和MPS/MRP来源，且不得对同一需求形成重复执行。
36. 正式菜单、页面、API、诊断、Gate、追踪和分析必须读取正式Service/API；静态Python rows、fixture、Demo和localStorage不得标记为server formal facts，也不得进入正式Gate。
37. Location与Lot/Batch只能扩展现有InventoryBalance/InventoryTransaction体系；旧Warehouse+Material库存必须继续读取和追踪，禁止建立第二余额或迁移localStorage库存。
38. Production Foundation Gate必须分别报告STRUCTURE、DATA、AUTHORIZATION、INTEGRATION和INDUSTRY DATA READY；结构Migration通过不得等同A1 CLOSED。
39. 标准制造与按单工程制造只能拥有一个正式制造定义对象：`ProductManufacturingOutput`。两种模式只允许改变制造定义的形成路径，不得形成两套BOM、两套路由或两套计划输入。
40. ProductCategory层级承担产品族分类语义；ProductDefinition通过受治理模式区分标准产品和可配置/按单工程产品。未经需求与行业证据，不新增ProductFamily或ConfigurableProduct平行表。
41. `OrderEngineeringInstance`必须一对一追溯正式SalesOrderItem，保存工程来源版本、快照、哈希、状态和审计；按单工程输出未正式发布前不得进入Demand、MPS或MRP。
42. 工程转换血缘固定为Engineering Source Record → Engineering Rule → Calculation Record → Breakdown Item → Derived Manufacturing Fact；该骨架不等于自动拆单引擎，A1.7不得实现全量公式计算、排产或优化。
43. 全系统仅使用ProductBOM→BOMVersion→BOMItem。按单BOM通过BOMVersion作用域及OrderEngineeringInstance稳定外键扩展，永久保存、版本化、审计和失效，不允许临时表或订单JSON替代。
44. 标准产能与标准工时是不同事实。StandardCapacity至少保存数量、UOM、时间基准、资源范围、适用条件与有效期；标准工时未知时必须为NULL/NOT_MAINTAINED，不得强制大于0，也不得用0冒充未知。
45. `08订单排产信息（样版）`和工程核算输出属于Golden Sample；只能用于规则回归、血缘校验与结果比对，不得导入为正式主数据或经营事实。
46. Excel公式错误必须分成输入完整、规则可恢复、外部链接缺失和不可恢复四类；公式缓存错误本身不构成业务模型失败，也不得通过复制输出结果绕过规则治理。
47. 行业差异通过数据、配置、版本、规则和通用扩展载荷表达；核心Product/BOM/Routing/Operation/WorkCenter/Capacity/Engineering Schema不得新增木业、印刷或单一行业专属字段。
48. 既有`#/foundation`是生产基础资料的统一业务入口；不得新建第二基础资料中心。页面必须按产品工程、制造资源、物料供应等业务关系组织，并通过正式API执行维护和回读。
49. 工程到计划的唯一正式交接是已发布ProductManufacturingOutput。标准路径直接形成，按单路径经OrderEngineeringInstance形成；A2只能消费稳定引用，不得在计划层重建BOM或工程规则。
50. A1.7完成后只能报告`READY_FOR_INDUSTRY_MASTER_DATA`；这不等于A1 DATA PASS/CLOSED，也不授权导入批量行业资料或进入A2。
51. 标准产能必须区分三种业务事实：已测定产能使用正数量；路线适用但无法确定时保存not_determinable且数量为NULL；不经过该工序时不创建适用产能记录。Excel中的0不得落为真实零产能，空格不得自动转成未知产能。每日工作时长属于可配置适用条件，不得反推标准工时。
52. Material基础库存/采购单位与Engineering Derived Quantity单位必须分离。来源资料没有Material单位时保存UNIT_NOT_CONFIRMED且正式UOM为空；门面板张、面积、长度等工程派生单位不得反向猜成Material基础单位。
53. Workshop是生产区域/车间组织事实，WorkCenter是可计划资源事实，两者不得互相替代。Operation可归属Workshop并在资源配置前不绑定WorkCenter；RoutingStep可引用Operation且WorkCenter待维护，直到真实资源资料提供后再受控补齐。
54. BOMItem损耗率必须区分MAINTAINED与NOT_MAINTAINED。未知值必须为NULL，明确0只表示经业务确认的零损耗；MRP不得把NULL默认成0。
55. BOM替代料必须区分NOT_MAINTAINED、CONFIRMED_NONE和MAINTAINED。无BOMItemSubstitute记录本身不证明不存在替代料；未来MRP必须读取维护状态并对未维护状态采取正式阻断或待维护策略。
56. ProductDefinition的order_engineered模式只定义长期可配置产品粒度；安装区域、尺寸、颜色、木皮、坯板和油漆工艺属于SalesOrderItem后的OrderEngineeringInstance/EngineeringSourceRecord。按单BOM仍由唯一ProductBOM/BOMVersion/BOMItem体系承载，不建立临时或第二套BOM。
57. EngineeringRuleDefinition必须具有稳定身份、版本、状态、适用条件、生效/失效、发布/废止动作和历史快照；执行中的EngineeringCalculation必须锁定Released规则版本，不得读取可变草稿或按名称推断规则。
58. Excel工作簿只可作为来源证据、规则恢复证据和Golden回归证据，不得作为正式生产运行时、公式执行器、主数据源或结果事实源。
59. 工程规则表达式必须使用安全AST或受控表达式并进行白名单校验；禁止`eval`、任意Python/JavaScript、动态导入、文件/网络访问及任何未授权副作用。
60. 规则输入输出和规则间依赖必须显式、可追溯并组成无环DAG；执行前必须验证缺失输入、未知依赖和循环依赖，执行时按稳定拓扑顺序运行。
61. 每次EngineeringCalculation必须保存输入快照、规则快照、CalculationDetail、中间值、最终输出、Decimal精度、UOM、舍入方式、错误分类、幂等键、执行身份、AuthorizationService结果和审计证据。
62. 工程来源事实必须同时保存raw_source、raw_sheet、raw_field、raw_value与canonical_field、normalized_value、value_type、unit、source_type；标准化、纠错和派生不得覆盖原始事实，既定九类source_type不得擅自改名、合并或扩展。
63. 一个SalesOrderItem对应一个完整EngineeringCalculation；一次Calculation允许执行N条规则、保存N个中间值和N个最终结果，禁止用每条规则一个孤立计算记录破坏聚合追踪。
64. EngineeringDerivedFact、EngineeringMaterialRequirement和EngineeringOperationRequirement是三个不同领域输出；不得用宽表、自由JSON或单一结果类型承载全部正式事实。
65. EngineeringMaterialRequirement只表达不含损耗的标准结构/标准用量；损耗、采购批量、安全库存、库存净需求和补充建议属于后续Material Control、MRP或采购域，不得写入A1.8工程规则结果。
66. EngineeringOperationRequirement只表达Operation、Input Quantity和UOM；StandardCapacity、标准工时、WorkCenter/Resource、日历、负荷、排程和APS是后续能力，不得混入工程工作量事实。
67. Excel中的“我的订单”“投产量”“线条单双”“产品平方”等历史术语只可进入来源映射和canonical dictionary，不得反向决定通用核心Schema、对象名或跨域职责。
68. 房门、木饰面、柜体及其它行业差异必须通过ProductCategory、Rule Package、版本、配置和受治理扩展属性表达；禁止在通用核心模型、Service或执行器中硬编码door、wall-panel、cabinet分支。
69. Golden G1、G2、G3只用于规则恢复、数据血缘和回归验证，不得写入正式主数据或经营事实；A1.8 DO只允许执行G1，G2/G3保持只读PLAN证据。
70. A1.8 DO最多实现并验证G1的5条代表规则，只能形成工程核算基础结论；不得实现全量公式、MaterialRequirement全链、OperationRequirement全链、汇总发布、MRP、APS、MES或生产执行。
71. A1.8及后续生产任务必须执行PDCA、范围锁定、阶段总结和变更控制；超出获批Task Control的对象、规则、Golden、模块或副作用必须停止并取得明确新授权。A1.9、A1.10和A2均不得由A1.8自动进入。

## 3. 开发前强制检查

每个 Production 任务必须输出：Requirement IDs、已有能力复用扫描、唯一事实所有者、对象/状态/Action/权限/审计/追踪设计、行业资料依赖、Schema/Migration 影响、禁止副作用和 Gate 状态。任一 A 类基础仍为 `FAIL/BLOCKED` 时，不得进入依赖它的业务流开发。

## 4. 冻结边界

本规范V1.5已冻结；冻结的是现行规则和A1.8 PLAN治理基线，不是A1.8 DO授权。当前状态为：A0=`PASS/CLOSED`，A1=`TECHNICAL PASS/NOT CLOSED`，A1.5=`PASS/CLOSED`，A1.7=`PASS/CLOSED`，A1.8 PLAN V1.1=`APPROVED/FROZEN`，A1.8 DO=`NOT AUTHORIZED`，A1.9/A1.10=`NOT ENTERED`，A2=`LOCKED`。当前只允许保留已批准PLAN和治理证据，禁止进入DO、A1.9、A1.10或A2。

## 5. V1.1正式修订记录

- 发现节点：PCE生产体系统一性审计V1.0。
- 修订原因：PDE版本/工程发布缺少正式写链；EMD静态BOM/Route/Warehouse与正式对象重复；WMS/QMS localStorage仍进入正式路径；销售、计划和库存稳定引用不足。
- 来源：用户A1.5正式指令、当前代码事实、PCM开发需求文档V1.1、Production Foundation Gate。
- 是否改变V1.0业务含义：否。V1.1仅补足唯一事实源、工程发布、历史兼容和Gate验收语义。
- 影响Requirement ID：PCM-MD-007、PCM-PDE-001/002、PCM-SALES-009、PCM-WMS-010、PCM-XMOD-001/002/005/008/009。
- 重新验收：A1.5自动测试、页面/API回读、权限审计、历史数据零破坏及GATE-INDUSTRY-DATA-01。
- 边界：不授权开发MPS/MRP/APS/A3/MES，不授权录入真实行业数据。

## 6. V1.2正式修订记录

- 发现节点：真实行业资料01—13及《工程拆单及订单排产数据核算方式》只读审阅。
- 修订原因：标准产能与标准工时语义混用；标准制造与按单工程缺少统一形成路径；订单工程来源、规则、计算、拆分、派生事实和按单BOM缺少稳定边界；既有基础资料页与A1正式API尚未形成统一业务入口。
- 来源：用户A1.7正式指令、真实行业资料、当前代码事实、PCM开发需求文档V1.1、Production L7 V1.1、Production Foundation Gate。
- 是否改变V1.1业务含义：否；新增对象用于实现原有工程发布和行业中立原则，未降低任何冻结要求。
- 影响Requirement ID：PCM-MD-003/006/008、PCM-PDE-003~008。
- 重新验收：A1.7专项测试、A1/A1.5回归、Migration、正式权限审计、页面/API回读、行业硬编码扫描、localStorage正式事实计数和A2零对象保护。
- 边界：不授权批量行业数据导入、工程拆单计算引擎、MPS/MRP/APS/A3/MES或真实生产执行。



## V1.3 变更记录（2026-08-28）

- 发现节点：A1真实行业样本中03标准产能业务语义确认。
- 正式证据：用户确认0表示经过但产能无法确定，空格表示不经过，现行每日工作时长为10小时且须可配置。
- 影响Requirement ID：PCM-MD-003。
- 新增治理规则：第51条。
- 是否改变既有业务含义：否；补足V1.2未覆盖的适用性与可测量性区分。
- Gate影响：Production Foundation Gate项目17增加measurement_status、0/空格和每日工时条件校验。
- 重新验收：Migration、正式Service/API、AuthorizationService、页面回读、A1/A1.5/A1.7回归。
- 边界：本变更不授权创建销售订单、MPS、MRP、ProductionPlan、ManufacturingOrder、WorkOrder或库存事务。

## V1.4 变更记录（2026-08-28）

- 发现节点：A1真实行业小样本基础语义校准。
- 正式证据：05表Material单位为空；01表提供Workshop分类但不提供WorkCenter；用户确认损耗率未知、替代料未维护，且按单BOM必须来自订单工程实例。
- 影响Requirement ID：PCM-MD-006、PCM-PDE-006、PCM-MRP-001。
- 新增治理规则：第52—56条，并修订第5条。
- 是否改变既有业务含义：否；补足未知事实、生产资源层级和BOM维护状态。
- Gate影响：A1结构与行业数据Gate增加Material单位状态、Workshop/WorkCenter分层、Nullable WorkCenter、损耗率状态和替代料状态核验。
- 重新验收：Migration、正式Service/API、AuthorizationService、页面回读、A1/A1.5/A1.7回归、行业样本及A2零对象保护。
- 边界：不授权创建SalesOrder、MPS、MRP、ProductionPlan、ManufacturingOrder、WorkOrder、MES或库存事务。

## V1.5 变更记录（2026-08-29）

- 发现节点：A1.8 PLAN V1.1完整订单工程核算数据血缘、工业术语和Golden Case范围校准。
- 正式证据：用户提供的《工程拆单及订单排产数据核算方式.xlsx》；房门、木饰面、柜体三类Golden只读分析；A1.8 TASK CONTROL PLAN V1.1；A1.8 PLAN正式批准指令。
- 影响Requirement ID：PCM-PDE-005、PCM-PDE-007、PCM-PDE-009、PCM-PDE-010、PCM-PDE-011。
- 新增治理规则：第57—71条。
- 是否改变既有业务含义：否；把既有工程血缘和行业中立原则细化为安全、版本化、可重放、可验收的执行治理。
- Gate影响：A1.8只允许未来独立授权的DO验证G1一个Golden、最多5条代表规则；G2/G3、MaterialRequirement全链、OperationRequirement全链及汇总发布分别留待后续获批任务。
- Blocker：`BLOCKER-MODEL-SO-01`继续开放并冻结五组Sales最小边界；`BLOCKER-DATA-MAT-01`不阻塞A1.8但阻塞A1.9；`BLOCKER-SOURCE-01`按VERIFIED_SOURCE/VERIFIED_RESULT受控；`BLOCKER-SEM-OP-01`在无唯一证据时延后；`BLOCKER-DOC-01`不阻塞A1.8但阻塞A1.10。
- 重新验收：A1.8未来DO的安全表达式、版本/发布、依赖DAG、Decimal/UOM/舍入、CalculationDetail、幂等、错误、三类输出边界、权限审计和Golden G1回归。
- 边界：本次只完成需求治理与PLAN冻结；不修改业务代码、Model、Schema、Migration、数据库、行业数据、Sales/PDE运行链、Planning、MRP、APS、MES或库存。
- 状态：Governance=`PASS`；A1.8 PLAN V1.1=`APPROVED/FROZEN`；A1.8 DO=`NOT AUTHORIZED`；A1.9/A1.10=`NOT ENTERED`；A2=`LOCKED`。

