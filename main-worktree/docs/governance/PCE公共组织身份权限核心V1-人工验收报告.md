# PCE 公共组织、部门、岗位、身份与权限核心 V1 人工验收报告

日期：2026-08-16  
环境：`http://localhost:5173/#/organization-directory`，后端 `127.0.0.1:8000`  
账户：已有 admin 登录会话  
动作边界：只读浏览与前端筛选；未执行采购、付款、银行发送或主数据维护

## 1. 验收结果

| 编号 | 验收点 | 结果 | 实际证据 |
|---|---|---|---|
| P01 | 路由可达与页面命名 | PASS | URL 可达，文档标题与双层页面标题均为“组织目录” |
| P02 | 公共页面壳 | PASS | `PceListPageShell` 显示 SYSTEM、pageCode、业务对象、页面位置 |
| P03 | 业务动作声明 | PASS | 页面展示 `system.organization_directory.view` |
| P04 | Permission Profile | PASS | 页面显示角色 `superadmin`、Scope `ALL` |
| P05 | AuthorizationService 结果 | PASS | 最终决定 `ALLOW`，原因来自服务端统一授权 |
| P06 | 服务端正式事实 | PASS | 显示 Company/Department/Position 聚合出的 16 条部门 |
| P07 | 用户状态标签 | PASS | 页面只显示服务端 `statusLabel=启用`，未展示 statusCode |
| P08 | 企业列表契约 | PASS | 搜索、刷新、高级筛选、清空、排序、导出、选择和操作列均存在 |
| P09 | 固定/滚动治理 | PASS | 浏览器测得横向滚动拥有者为 1，操作列表头为 1 |
| P10 | 快捷搜索 | PASS | 输入“采购部”后当前结果由 16 条收敛为 1 条，出现采购部 |
| P11 | 页面控制台 | PASS | error/warn 日志为 0 |
| P12 | 只读边界 | PASS | 页面无新增、编辑、删除或业务推进动作；服务端 strictFacts 的 businessWriteCount 为 0 |
| P13 | 采购不变量 | PASS | 浏览器验收后 PurchaseOrder 仍为 218 |

## 2. 可见运行链

页面实际显示：

```text
业务动作：system.organization_directory.view
公共 Runtime：PCE-ORGANIZATION-ACCESS-CORE-V1
角色：superadmin
Scope：ALL
最终决定：ALLOW
系统管理员通过统一授权服务校验。
```

这证明浏览器运行链为：

```text
OrganizationDirectoryPage
  → action_code
  → PermissionProfileRuntime
  → /api/access-control/profile/
  → /api/access-control/organization-directory/
  → AuthorizationService
  → Role / Permission / Scope
  → ALLOW
```

DENY、DEPARTMENT 和普通用户管理页拒绝由后端自动测试覆盖：无动作权限返回 HTTP 403，部门 Scope 只返回指定部门，普通用户不能通过管理 API 写入旧 Authority。

## 3. 未执行项

- 未点击导出下载；其控件和 Runtime 已通过构建与 DOM 验证。
- 未在浏览器中切换真实普通账户，因为本轮不重置或暴露账户口令；DENY 与部门范围使用隔离后端测试完成。
- 未执行任何采购创建、价格维护、审批、付款或银行发送动作。

## 4. 结论

低风险真实试点的页面结构、交互、服务端事实、权限链和零写边界均通过。后续最终验收已补齐 ADMIN、DENY、DEPARTMENT 三类真实浏览器身份及 H01–H17 证据；以《PCE 公共组织身份权限核心 V1——最终人工验收与封板报告》为最终事实。2026-08-16，用户明确签发：

```text
Human Acceptance = PASS
PCE ORGANIZATION & ACCESS CORE V1 = BASELINE
权限专项 = CLOSED
Full Project Build = BLOCKED BY EXISTING SCM STATIC GATES
```

该人工签发不改变完整构建被 7 个既有 SCM 静态门禁阻断的事实，也不构成全项目 Ready Gate PASS。
