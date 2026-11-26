# PCE 公共组织、部门、岗位、身份与权限核心 V1 架构调整记录

日期：2026-08-16  
状态：已实施

## 1. 调整原因

下一代设计报告给出了面向未来的 Role、Permission、Scope 与 Assignment 分层方向；更高层开发治理要求不得另建平行权限框架，并要求 API、页面、Runtime、strictFacts 和验收报告复用同一服务端事实。实施时以更高层治理为准，对设计方案作了低风险收敛。

## 2. 原方案、冲突与最终方案

| 主题 | 设计报告原方向 | 更高层约束/现实 | 最终实施 |
|---|---|---|---|
| Role/Permission | 可演进为下一代模型 | 禁止平行框架；既有模型已被真实业务使用 | 复用 `system.Role / Permission / RolePermission` |
| Assignment/Scope | 拆出正式授权与 Scope | 旧 `UserOrganizationRoleAuthority.department_id` 多义 | 新增 `UserRoleScopeAssignment`；真实部门 FK 与 Scope 枚举分离 |
| 授权入口 | 新公共 AuthorizationService | 页面和模块不得各自重算 | `system.AuthorizationService` 成为唯一公共结论入口 |
| 旧服务 | 替换 BusinessPermissionAuthorization | R5.1/R10 仍有真实消费者 | 保留薄兼容门面，内部完全委托新服务 |
| Workflow | 保留状态/流程验证 | 权限与组织事实不得由 Workflow 自建 | Validator 保留业务校验；Provider 改读中央权限事实 |
| 动作 Registry | 后端唯一 Canonical Registry | 既有 `Permission` 已是服务端动作权限事实 | V1 动作目录直接投影 `system.Permission`，不新建第二张表 |
| 前端 | PermissionProfileClient/Resolver | 现存 Meta 引擎仍有 15+ 真实消费者，涉及采购 Gate | 新增公共 Runtime 给新试点；旧引擎列入后续 REPLACE，不强删 |

## 3. 正式模型边界

```text
Company
  └─ Department
       └─ Position
            └─ Employee ↔ User

User ── UserRoleScopeAssignment ── Role ── RolePermission ── Permission(action_code)
                    ├─ organization: Company
                    ├─ department: Department（仅 DEPARTMENT 时必须存在）
                    └─ scope_code: SELF / DEPARTMENT / ORGANIZATION / ALL
```

`CUSTOM` 是数据库保留值，`AuthorizationService` V1 明确不匹配它，因此不会被误当成放权范围。

## 4. 决策与事实契约

`AuthorizationService.decide` 统一返回：

```text
contractVersion
allowed
actionCode
organizationId
decisionCode
reason
facts.visible
facts.executable
facts.disabledReason
roleCodes
permissionCodes
scope.codes
scope.departmentIds
authoritySource
```

正式 Assignment 优先；只有用户尚无正式 Assignment 时，才读取旧 Authority 兼容源。管理 API 只写正式 Assignment，不再写旧表。

## 5. 低风险试点选择

动作：`system.organization_directory.view`。

选择理由：

- 只读 Company、Department、Position 持久化事实；
- 不维护主数据、不推进 Workflow、不触发 Gate；
- 不创建 PurchaseOrder，不修改 SupplierMaterialPrice；
- 不涉及付款、银行发送或生产接口；
- 可以真实证明组织 Scope 对列表可见范围的约束。

## 6. 治理标准调整

`PCE-BUSINESS-ACTION-PERMISSION-V1.0.md` 已补充公共组织权限核心契约：

- 正式主源升级为 `UserRoleScopeAssignment`；
- 旧 `UserOrganizationRoleAuthority` 只读兼容，禁止新写；
- `AuthorizationService` 为唯一公共权限入口；
- Position 与 Role 不得混合；
- 前端 Permission Profile 不得重算角色权限；
- DEPARTMENT 必须引用真实 Department。

## 7. 审核状态

实现与更高层开发治理一致。2026-08-16，用户完成最终报告原文与真实浏览器截图审核并明确签发人工验收通过；本记录的最终状态由最终封板报告统一收口为：

```text
PCE ORGANIZATION & ACCESS CORE V1 = BASELINE
Human Acceptance = PASS
权限专项 = CLOSED
Full Project Build = BLOCKED BY EXISTING SCM STATIC GATES
```

专项基线不覆盖完整构建阻断，也不把全项目 Ready Gate 标记为 PASS。
