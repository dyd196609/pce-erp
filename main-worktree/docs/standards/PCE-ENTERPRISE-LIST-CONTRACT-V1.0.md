# PCE-ENTERPRISE-LIST-CONTRACT-V1.0

## 目标

为 PCE 企业级列表页面提供唯一、可复用、可自动检查的运行基座，同时保持业务状态机、权限、事实契约和数据模型不变。

## 页面声明

每个列表页面必须声明：

- `pageCode`
- `pageType=list`
- `title`
- `moduleCode`

## 标准能力

- 搜索
- Schema 驱动的高级筛选
- 排序与清除排序
- 导出当前结果
- 行选择与清空选择
- 表格内部横向滚动
- 选择框、序号、主业务编号左冻结
- 操作列右冻结

## 状态呈现

业务页面使用 `PceBusinessStatus`。

- 输入：`statusCode`、`statusLabel`
- 显示：仅 `statusLabel`
- 禁止：直接显示技术状态编码

## 事实边界

运行基座只操作已加载的行数据，不生成业务计数，不构造或覆盖：

- API Facts
- Page Facts
- Diagnostic Facts
- StrictFacts

四端一致性继续由页面既有服务端事实契约保证。

## 动作与安全

操作列只承载页面已注册的安全动作。业务权限继续由 PCE Business Action Registry 和服务端权限验证决定。

运行基座禁止：

- 银行发送
- 付款执行
- 资金扣减
- 状态推进
- 业务对象创建
- 生产数据写入

## 自动检查

执行：

```bash
npm run verify:pce-enterprise-list-runtime:v612
```

检查器输出 `PASS`、`FAIL` 或 `UNKNOWN`，不得用人工判断替代结构性门禁。
