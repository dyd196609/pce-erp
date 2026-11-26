# PCE-BUSINESS-ACTION-PERMISSION-V1.0

## 目标

业务动作统一形成以下服务端权威链：

`BusinessStateTransition → BusinessActionRegistry → Permission Provider → Action Permission Validator`

前端展示不是权限，服务端验证才是权限。

## 动作权限声明

黄金流程内每个动作必须声明：

- `actionCode`
- `moduleCode`
- `requiredPermission`
- `role`
- `organizationScope`
- `serverValidator`

`organizationScope` 对旧业务动作继续兼容 `legal_entity`；PCE 公共组织权限核心
V1 使用 `SELF / DEPARTMENT / ORGANIZATION / ALL` 四种正式范围，`CUSTOM`
仅作保留值，不得在 V1 中启用。权限来源必须是服务端
`UserRoleScopeAssignment`、`Role`、`Permission` 和 `RolePermission`，不得由
路由参数、页面内存、localStorage 或按钮可见性推导。

`UserOrganizationRoleAuthority` 自 PCE 公共组织权限核心 V1 起降级为旧数据只读
兼容源：允许 `AuthorizationService` 在用户尚无正式关系时读取，禁止新增、修改或
把它继续作为新功能写入目标。完成存量核验和迁移后再按证据清理。

## 角色与范围

- `pce_business_viewer`：仅查看。
- `pce_business_operator`：查看和单条动作。
- `pce_business_batch_operator`：查看、单条和批量动作。
- `pce_business_admin`：完整业务动作权限，但仍需通过组织、状态和流程校验。

拥有角色不等于拥有动作权限；角色必须同时获得动作对应的
`requiredPermission`，并覆盖业务对象的法人组织范围。

## 服务端校验

任何单条、批量或跨模块导航动作在执行前都必须调用
`workflow_runtime.ActionPermissionValidator`。校验顺序为：

1. 用户身份；
2. 动作注册；
3. 选择数量；
4. 服务端业务对象存在性；
5. 服务端当前状态和流程阶段；
6. 对象法人组织范围；
7. 用户组织角色；
8. 角色动作权限。

客户端提交的状态、角色、权限编码和组织结论均不可信。服务端必须根据对象
ID重新读取状态和法人范围，并从权威权限对象重新计算结论。

## PCE 公共组织权限核心 V1 补充契约

- `system.AuthorizationService` 是身份、动作权限与数据范围结论的唯一公共入口。
- `ActionPermissionValidator` 继续拥有动作注册、选择数量、业务对象、状态和流程
  阶段校验；其角色、权限与组织范围事实必须由 `AuthorizationService` 提供。
- `Position` 表达人员在组织中的岗位，`Role` 表达系统授权集合；二者不得合并或
  互相替代。
- `Permission Profile` 与具体授权决策必须来自同一组服务端关系和权限事实；前端
  Runtime 只能消费服务端结论，不得按角色名重算权限。
- `DEPARTMENT` 范围必须引用真实 `Department`；禁止再用部门字段承载
  `ALL`、法人或其他特殊范围标记。

## 展示与拒绝

前端可以根据服务端权限矩阵隐藏或禁用按钮，但隐藏和禁用只是用户体验。
服务端校验端点对禁止动作必须返回 HTTP 403；绕过前端直接调用时仍必须拒绝。

## 保护边界

本契约不开放银行发送、付款执行、付款凭证、核销、总账或过账动作，也不得
写入生产用户业务数据。
