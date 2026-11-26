# PCE 公共组织、部门、岗位、身份与权限核心 V1 测试报告

日期：2026-08-16

## 1. 自动测试汇总

| 检查 | 结果 | 证据 |
|---|---|---|
| Django `check` | PASS | 0 issues |
| `makemigrations --check --dry-run` | PASS | No changes detected |
| 组织权限核心 + 既有 R10 基础 | PASS | 19/19 |
| R5.1 采购专项 | PASS | 4/4 |
| workflow 权限兼容套件 | PARTIAL | 7/9；本轮修复后旧 viewer 行为已通过，剩 2 个既有静态期望差异 |
| 直接 Vite 生产构建 | PASS | 2,533 modules transformed；生成 OrganizationDirectory chunk |
| 正式 `npm run build` | BLOCKED | prebuild 在既有 7 个 SCM 静态 blocker 处停止 |
| `git diff --check`（本轮文件） | PASS | 仅 CRLF 提示，无空白错误 |
| 数据迁移 | PASS | 仅 system 0005；workflow 0002–0004 未应用 |
| 采购订单不变量 | PASS | 218 → 218 |

## 2. 核心 19 项覆盖

新增测试覆盖：

- Position 与 Role 独立；
- DEPARTMENT Scope 必须有真实 Department；
- AuthorizationService ALLOW/DENY；
- Permission Profile 使用正式服务端事实；
- 授权决策 API；
- 部门范围组织目录；
- 无权限用户 HTTP 403；
- 管理 API 只写正式 Assignment；
- 动作目录复用 system.Permission；
- 既有 ERP/R10 的 Employee、Department、Position、RolePermission、人工价格 403、有权限隔离写、ALL/SELF/ORGANIZATION 范围继续通过。

执行结果：

```text
Ran 19 tests in 0.963s
OK
System check identified no issues
```

## 3. R5.1 保护回归

```text
Ran 4 tests in 1.292s
OK
System check identified no issues
```

本轮没有把直接采购、SupplierMaterialPrice 人工维护、PurchaseOrderGate 或采购审批改为首批试点。正式库 PurchaseOrder 迁移前后均为 218。

## 4. workflow 兼容测试说明

`workflow_runtime.tests.test_business_action_permissions_v552` 共 9 项，7 项通过。剩余 2 项失败内容为：

1. 测试仍固定期待 `moduleCount == 14`，当前真实 Registry 返回 27；仓库正式前端治理脚本实际已验证 32 个模块和 89 个动作并通过。
2. 测试要求 `MODULE_ACTIONS == OBJECT_FACT_SOURCES`，当前已有 `bank-send-isolation-gate`、`bank-send-simulation-audit` 两个新增模块尚未加入旧测试事实映射。

这两个差异在本轮前已存在，属于测试静态期望落后于当前 Registry，不是中央授权服务造成的 ALLOW/DENY 回归。本轮首次接入时暴露的 viewer 组织过滤问题已修复，相关 viewer 测试现已通过。本轮没有擅自修改这些旧测试或银行发送模块来制造绿色结果。

## 5. Build 说明

直接执行 Vite 编译：PASS。只有依赖包纯注释、动态 import 和大 chunk 警告，无编译错误。

正式 `npm run build` 的权限、银行发送、采购上游和支付链前置门禁先后通过；随后 `verify:web-acceptance-contract` 报告 7 个既有 SCM blocker：

- 采购询价：快捷搜索字段、高级筛选；
- 询价下一流程验收：快捷搜索字段、高级筛选；
- 供应商绩效：高级筛选字段数；
- 采购员绩效：高级筛选字段数；
- 采购异常责任分析：高级筛选字段数。

这些与本轮新增 SYSTEM 组织目录无关，但它们使全项目 `allowBuild=false`，所以本报告不宣称完整 npm build PASS。

## 6. 结论

组织权限核心专项可运行且保护回归通过；全项目仍有已披露外部 blocker。2026-08-16，用户完成最终报告与真实浏览器截图审核并签发人工验收通过。最终状态分别记录为：

```text
PCE ORGANIZATION & ACCESS CORE V1 = BASELINE
Human Acceptance = PASS
权限专项 = CLOSED
Full Project Build = BLOCKED BY EXISTING SCM STATIC GATES
```

完整 `npm run build` 未通过，因此本报告不把 Full Project Build 或全项目 Ready Gate 标记为 PASS。
