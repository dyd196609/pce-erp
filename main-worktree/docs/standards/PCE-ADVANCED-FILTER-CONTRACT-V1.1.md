# PCE 高级筛选契约 V1.1

版本：V1.14.2.8.4.7.52.1

每个高级筛选字段必须由唯一 `filterSchema` 描述，并包含：

- `field`
- 中文 `label`
- `type`
- `displayMap`
- `optionsProvider`

状态、供应商、法人、账簿、币种、银行接口、支付路线、签署策略、授权路线和场景类型统一使用 `select`。金额区间使用 `numberRange`，日期区间使用 `dateRange`。

业务页面不得把 `draft`、`reviewed`、`passed`、`blocked` 作为显示标签；对应中文分别为“草稿”“已复核”“已通过”“已阻断”。技术值只用于服务端查询参数和客户端精确匹配。

`pceBusinessModuleRegistry` 是字段契约来源，`pcePageAcceptanceRegistry` 只能投影该契约，不得维护第二套字段类型或显示映射。标准列表查询可保留 `queryType` 表达上下界，但不得用它替代对外 `type`。

四项阻断守卫：

- `filter_schema_has_display_labels`
- `filter_enum_values_not_exposed`
- `business_dictionary_fields_use_select`
- `advanced_filter_contract_consistent`

验收必须覆盖 13 个 strict 页面、筛选清空恢复、真实 Chrome、完整生产构建，以及持久金丝雀数据库和开发数据库前后哈希一致。
