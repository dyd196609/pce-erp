# PCE-ERP运行层文件职责规范

- 规则编号：`RUNTIME-FILE-RESPONSIBILITY-001`
- 生效版本：`V1.14.2.8.4.27.2.15`
- 适用范围：PCE-ERP全部业务对象、Provider、Runtime、ViewModel与页面
- 状态：长期有效、持续更新

## 1. 业务对象唯一运行层

每个业务对象只能拥有一个正式Runtime入口，固定依赖方向为：

```text
Domain -> Runtime Adapter -> ViewModel -> Page
                     ^
                     |
                  Provider
```

页面读取链必须可追踪为：

```text
Router -> Page -> Runtime Adapter -> Provider -> Domain
```

Provider负责读取权威事实，Runtime Adapter负责把同一业务对象转换成唯一Runtime Model。页面不得直接把Gate、Source、临时对象、Demo对象或Provider原始结构作为当前业务对象。

采购订单正式入口固定为`PurchaseOrderRuntimeAdapter -> PurchaseOrderRuntimeModel`。列表、详情、打印与导出只能消费该模型及其ViewModel投影。

## 2. 文件职责隔离

| 层级 | 职责 | 禁止事项 |
|---|---|---|
| Schema | 定义业务字段、顺序、数据类型与必填规则 | 页面格式、业务编号拼接、Provider读取 |
| Domain | 定义业务对象、Canonical编号、状态与业务规则 | 页面DOM与展示格式 |
| Provider | 获取同一服务端或持久化事实 | 为同一对象返回多种结构、页面临时数据回退 |
| Runtime Adapter | 唯一对象转换、关系归一化与只读运行模型 | 创建业务对象、推进状态、来源编号替代正式编号 |
| ViewModel | 面向页面的只读业务投影 | 修改Domain、重新读取第二事实源 |
| Page | 展示、导航、收集用户动作 | 拼接编号、重算业务对象、直接消费Gate/Source/Demo对象 |

## 3. 禁止重复实现

同一业务能力只能存在一个正式实现。升级时，旧文件必须删除、归档或改为无业务逻辑的兼容转发；禁止两个Formatter、两个Runtime或两个Adapter同时维护规则。

验收必须输出正式实现路径、活动import数量、兼容转发数量和重复业务逻辑扫描结果。正式Runtime入口数量不等于1时必须FAIL。

## 4. 运行模型要求

Runtime Model必须声明`runtimeModelType`、`runtimeAdapterCode`、对象`id`、Canonical业务编号、关联子项及事实来源；缺少Canonical编号或父子关系冲突时显式FAIL。转换只读且`Business Write Count = 0`。

## 5. 变更记录

- `V1.14.2.8.4.27.2.15`：建立业务对象唯一运行层、六层职责隔离和重复实现门禁。
