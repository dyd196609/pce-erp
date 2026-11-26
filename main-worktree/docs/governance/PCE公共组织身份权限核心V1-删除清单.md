# PCE 公共组织、部门、岗位、身份与权限核心 V1 删除清单

日期：2026-08-16  
原则：搜索消费者 → 搜索路由/Runtime/测试/API → 删除 → Build → 自动测试 → 浏览器回归

## 1. 已删除

### `frontend/src/domain/permission/permissionEngine.js`

结论：`DELETE`。

删除前证据：

- 对 `frontend/src`、测试和脚本搜索 `domain/permission/permissionEngine`，真实消费者为 0；
- 未发现路由、Runtime、API 或测试引用；
- 设计审计报告同样记录消费者为 0；
- 文件自身不是公共 Meta Runtime 引擎。

删除后证据：

- 文件不存在；
- 全仓搜索只剩治理报告中的历史路径文本，不存在源码 import；
- Vite 生产构建完成，2,533 个模块转换成功；
- 组织权限核心 19 项测试与 R5.1 4 项测试通过；
- 真实组织目录页面可访问、筛选可用、控制台无错误。

恢复方式：可从 Git 历史或本轮前工作区备份恢复；本轮没有删除数据库数据。

## 2. 已调查但保留

| 候选 | 证据 | 本轮结论 |
|---|---|---|
| `frontend/src/meta/domain/employeeModel.js` | `meta/review/reviewEngine.js` 有真实 import | KEEP，先替换 Review 消费者再删 |
| `frontend/src/meta/domain/organizationModel.js` | `meta/review/reviewEngine.js` 有真实 import | KEEP，先改读服务端身份快照 |
| `frontend/src/meta/domain/roleModel.js` | `meta/review/reviewEngine.js` 有真实 import | KEEP，不能按 Demo 名称强删 |
| `frontend/src/meta/runtime/permissionEngine.js` | SCM 动作、CRUD、AI、数据网关、驾驶舱、PurchaseOrderGate 等多处真实消费者 | REPLACE，保护期内不大面积切换 |
| `frontend/src/meta/auth/rbacEngine.js` | `profitOSApi`、`runtimeTracer`、商业授权 Runtime 有消费者 | REPLACE，消费者归零后才可 DELETE |
| Enterprise OS 本地角色/权限 | 仍有页面与 Provider 依赖 | REFACTOR/REPLACE，禁止直接清空 |

## 3. 本轮未删除

- 未删除 Company、Department、Position、Employee、User、Role、Permission 或 RolePermission 数据。
- 未删除两条旧 Authority；它们保留为只读兼容和迁移核验事实。
- 未删除任何采购、价格、Gate、审批、付款或银行发送实现。
- 未修改或清理工作区中与本任务无关的大量既有未提交变更。

## 4. 最终状态

确认无消费者的孤立旧引擎已实际删除；其余候选均按证据保留。2026-08-16 用户完成最终人工签发后，本清单随权限专项正式封板：

```text
PCE ORGANIZATION & ACCESS CORE V1 = BASELINE
Human Acceptance = PASS
权限专项 = CLOSED
Full Project Build = BLOCKED BY EXISTING SCM STATIC GATES
```

不再扩展 V1.1、V2、复杂 AI 权限、CUSTOM Scope 或历史权限大迁移。
