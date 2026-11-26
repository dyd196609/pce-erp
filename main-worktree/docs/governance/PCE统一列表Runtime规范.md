# PCE统一列表Runtime规范

- 版本：`V1.14.2.8.4.27.2.45.10`
- 规则编号：`LIST-REFRESH-CONTRACT-001`
- 适用范围：使用 `PceEnterpriseListTable（PCE企业统一列表）` 与 `FoundationMetadataList（基础资料元数据列表）` 的标准列表页

## 1. 唯一刷新入口

列表刷新能力归属既有 `pceEnterpriseListContract.js`。页面不得新建第二套刷新框架；公共组件通过 Registry（注册中心）定位当前实体的 Provider（数据提供器），再调用 `createPceListRefreshRuntime`。

标准链固定为：

```text
用户点击刷新
→ 当前页面Registry定义的Provider({ force: true })
→ 服务端API / Runtime
→ 替换rows
→ 重算currentResultCount与totalCount
→ 保留快速搜索、高级筛选、排序和pageSize
→ 当前页超界时调整到合法页
→ 中文成功/失败反馈
```

## 2. 强制要求

只要标准列表显示“刷新”，必须同时满足：调用正式Provider并产生新的服务端请求；使用新响应替换列表行；更新结果数；保留筛选、排序和每页数量；显示“刷新中…”及中文结果反馈。

禁止 `window.location.reload()`、`router.go(0)`、重新打开页面、重赋旧数组或只有loading动画。没有服务端Provider的历史本地维护页不得声称“Network真实刷新PASS”；必须登记为迁移缺口。

## 3. 验收

人工验收必须保留 `Before Data ≠ Server New State`，点击刷新后证明 `After Data = Server New State`。自动验收只证明契约与调用链存在，不能替代真实差异数据和人工点击。

## 4. PCE-EDIT-PERSISTENCE-001 编辑持久化门禁

只要列表页面提供“编辑”和“保存”，必须证明同一对象完成 Browser（浏览器）→ API（服务接口）→ Service / Runtime（服务/运行层）→ Database（数据库）→ Re-read（重新读取）→ Browser 的完整闭环。保存成功后 Provider 必须重新请求正式事实并替换列表数据；仅修改前端行对象、localStorage（浏览器本地存储）或 Server Memory（服务端内存）均为 FAIL。

保存动作必须展示“保存中…”、明确中文成功反馈与具体中文失败原因。页内刷新、浏览器重新加载及后端重启后同一对象字段仍一致，才可判定持久化 PASS。
