# Manufacturing Definition Applicability Contract V1.0

状态：`CURRENT / ACTIVE`  
指令：`G3-MANUFACTURING-APPLICABILITY-20260908-001`  
生产迁移授权：`NO`

## 审计结论

- `pde.Routing.product`、`pde.ProductBOM.product`为非空外键，Header只能服务长期`ProductDefinition`。
- `RoutingVersion`与`BOMVersion`再次强制绑定`ProductDefinition/ProductVersion`，即使存在Header也可形成重复身份及漂移。
- `OrderEngineeringInstance`与`SalesOrderItem.clean()`同样把ORDER_ENGINEERED强制绑定长期产品，无法表达已人工确认的37个一单一设计对象。
- 当前没有正式对象表达“ProductCategory + manufacturing/finishing process type → reusable Routing”。
- `RoutingVersion.applicability`是版本级资源/配置条件JSON，不是适用主体身份，不能替代受约束的Header范围。
- `ProductBOM/BOMVersion`存在同根缺口，登记为`SHARED MANUFACTURING APPLICABILITY GAP = YES`。

## 唯一上位契约

现有`Routing`和`ProductBOM`原位增强，不建立第二套模型。每个Header使用`scope_type`，并且必须且只能存在一个目标：

| scope_type | 唯一目标 | 用途 |
|---|---|---|
| `PRODUCT_DEFINITION` | `product_id` | 长期标准或具体产品制造定义 |
| `PRODUCT_CATEGORY` | `product_category_id` | 分类/模板级复用制造定义 |
| `ORDER_ENGINEERING` | `order_engineering_instance_id` | 单一订单工程实例专用制造定义 |

`ManufacturingProcessType`是公司内可维护主数据。真实来源的14种工艺类型由受控来源写入数据，不进入Python/前端硬编码枚举。Routing可引用该维度；当前42条的正式业务身份是3个ProductCategory × 14个ManufacturingProcessType。

## 版本与解析

- Header是适用主体唯一权威；Version只表达Header版本及版本级条件。
- 兼容字段`RoutingVersion.product/product_version`与`BOMVersion.product/product_version`允许为空；填写时必须与PRODUCT_DEFINITION Header一致，非产品Header禁止填写。
- ORDER_ENGINEERED有效路线按：订单实例专用Route → ProductDefinition专用Route → ProductCategory + selected process type Route逐级解析。
- 同一优先级0条时继续降级；多条同时有效返回`AMBIGUOUS_EFFECTIVE_ROUTING`；全部为0返回`NO_EFFECTIVE_ROUTING`。禁止随机取第一条。
- 版本解析继续使用生命周期、生效区间与版本级`applicability`条件；0或多版本均阻断。

## 边界

- `STANDARD`、`TEMPLATE_ASSISTED`与`ORDER_ENGINEERED`共用现有BOM/Route体系。
- 当前整改只提供模型能力和隔离回放，不创建生产Routing、BOM、ProductDefinition或ProductVersion。
- Operation的GENERAL/KITTING默认转序语义不变；RoutingStep仍可显式覆盖。
- “开料→拼皮”的主数据展示顺序不等于任意Routing必须包含拼皮；当前来源路线拼皮出现次数保持0。

## 2026-09-09 半成品材料主体隔离扩展

本节是当前用户指令的候选设计授权，不是生产迁移授权。保留既有三类主体，只有ProductBOM增加MATERIAL（唯一Material）和MATERIAL_CONFIGURATION（唯一受控Material配置）主体；Routing不增加此范围、不改变执行语义。

配置复用Material和ExternalIdentity；工艺类型复用ManufacturingProcessType；坯板材料族复用MaterialCategory并用显式允许成员/规格关系约束解析。色板、木皮的来源业务身份、canonical值、正式身份、解析状态和人工确认分别保存。拼皮/肤感使用KNOWN_TRUE、KNOWN_FALSE、UNKNOWN、NOT_APPLICABLE，不能以布尔默认值消灭未知。

现有ProductBOM/BOMVersion/BOMItem继续是唯一BOM。数量模式FIXED/CALCULATED/MANUAL分别表达固定用量、引用EngineeringRuleDefinition的运行时用量、工程人工指定。未知数量允许NULL并阻断生成，不使用0或1占位。配置属性并非自动耗用物料，尤其色板与油漆工艺。

现有四张材料需求/候选/结果/模板槽表优先历史恢复，不另建相同职责表。模型候选只在隔离backend和SQLite副本迁移/回放；正式运行模型、生产DB和已发布四条规则保持不变。

## 2026-09-09 角色层级纠正（隔离候选，取代旧五角色/厚度未知Gate）

依据65975ebd用户指令：BTKF2601001、QSFB4601001来源配置身份已确认并冻结；新层级UI仍待人工验收。

- 配置默认角色只有SUBSTRATE、VENEER、SURFACE/PROCESS_CONSUMABLE，数量方式均CALCULATED；规则未发布用PENDING，数量NULL。颜色/油漆工艺是属性，不自动变成耗材。
- EDGE不属于配置；复用原ComponentMaterialRequirement。EngineeringBreakdownItem以受约束来源行FK引用MaterialConfigurationSourceBinding，再引用配置，不伪造订单或已成功计算记录。组件提供几何、数量、封边方式、结构位置。
- 既有订单组件owner保留；需求必须且仅有一个组件owner。材料规格身份与用量状态独立；封边材料、逐边余量未知仍NULL，基础单位m，不发布毛耗用或采购需求。
- OTHER_FIXED保留在原工程结构/BOM，不复制成配置角色。粗略BOM仅结构参考，非数量/公式权威。
- 三合一L列厚度正式登记BOARD_MATCH_INPUT；63行不再以THICKNESS_UNKNOWN阻断。解析顺序是配置→坯板族→L厚度→显式允许采购成员→正式长宽厚→几何适配→最小合法规格。精确厚度，不以名称或几何猜材料族，不近似替换，不隐含批准旋转。
- 木皮按见光面积形成净量预览；自身厚度仅物料属性，不参与用量。采购身份未解析只阻断正式采购需求，不阻断可判定净面积。
- 表面耗材ROLE=VALIDATED、QUANTITY_MODE=CALCULATED、RULE=PENDING、具体物料待解析；不猜耗用系数、损耗、涂布率或道数。
- 0024/0025保留原候选；0026仅在新隔离backend与SQLite副本中纠正四个既有模型。全部生产Migration/DB/业务写入0，规则发布不在本轮范围。
