# PCE 公共组织、部门、岗位、身份与权限核心 V1 实施报告

日期：2026-08-16  
实施范围：Day 1–Day 5（用户提供的正式指令原文止于 `## Day 6` 标题，未包含 Day 6 内容）  
实施状态：核心能力已落地；经用户最终人工签发，专项状态为 `BASELINE（正式基线）`

## 1. 结果

本轮已建立可运行的公共组织权限核心，而非仅补充设计文档：

1. 保留 `system.User / Company / Department / Position`、`pfm.Employee` 和既有 `system.Role / Permission / RolePermission`，没有建立平行 Role/Permission 框架。
2. 新增正式 `system.UserRoleScopeAssignment`，把用户、角色、组织、真实部门和 `SELF / DEPARTMENT / ORGANIZATION / ALL` Scope 建成持久化关系；`CUSTOM` 仅保留，V1 不启用。
3. 建立唯一公共服务端入口 `system.AuthorizationService`，统一输出身份、动作权限、Scope、ALLOW/DENY、原因和服务端事实。
4. `BusinessPermissionAuthorization` 降级为兼容门面；`workflow_runtime.ActionPermissionProvider` 的角色、权限和组织范围事实改读公共服务。
5. 建立 Permission Profile API、动作目录 API、授权决策 API，以及前端 `PermissionProfileRuntime`；前端不再按角色名推导权限。
6. 选择 `system.organization_directory.view` 作为低风险真实试点，形成“页面 action_code → 公共 Runtime → Permission Profile → AuthorizationService → Role/Permission/Scope → ALLOW/DENY”完整链路。
7. 删除零消费者旧文件 `frontend/src/domain/permission/permissionEngine.js`；有消费者的 Meta Runtime、RBAC 和 Demo 模型未强删。
8. 数据库迁移前完成等哈希备份，仅应用 `system.0005_organization_access_core_v1`；采购订单保持 218 条，未发生采购、付款或银行发送业务写入。

## 2. 实施文件

后端核心：

- `backend/system/models.py`
- `backend/system/migrations/0005_organization_access_core_v1.py`
- `backend/system/authorization.py`
- `backend/system/authorization_views.py`
- `backend/system/access_control_views.py`
- `backend/system/urls.py`
- `backend/workflow_runtime/action_permissions.py`
- `backend/system/tests_organization_access_core_v1.py`

前端核心：

- `frontend/src/api/accessControl.js`
- `frontend/src/meta/runtime/permissionProfileRuntime.js`
- `frontend/src/meta/pages/OrganizationDirectoryPage.vue`
- `frontend/src/router/index.js`
- `frontend/src/meta/governance/businessNameRegistry.js`

治理与证据：

- `docs/standards/PCE-BUSINESS-ACTION-PERMISSION-V1.0.md`
- 本报告及同批架构调整、删除、测试和人工验收报告
- 数据库备份 `backend/db.pre-organization-access-core-v1-20260816.sqlite3`

## 3. 数据迁移结果

迁移前源库 SHA-256：`A5F72AC753D74858732C2CD58D9F65431267C2EE3F9FD984F6E3F282DA1017A8`。  
备份 SHA-256：`A5F72AC753D74858732C2CD58D9F65431267C2EE3F9FD984F6E3F282DA1017A8`。  
两者字节长度均为 2,486,272，备份证据一致。

迁移只执行：

```text
system.0005_organization_access_core_v1
```

迁移后 `workflow_runtime.0002–0004` 仍未应用，证明没有误带入其他迁移。

迁移前后关键数量：

| 对象 | 迁移前 | 迁移后 | 说明 |
|---|---:|---:|---|
| PurchaseOrder | 218 | 218 | 无采购订单写入 |
| User | 3 | 3 | 无账户增删 |
| Role | 6 | 6 | 复用既有角色 |
| Permission | 38 | 39 | 新增组织目录查看动作 |
| RolePermission | 54 | 57 | 为既有三类角色授予只读试点动作 |
| 旧 Authority | 2 | 2 | 原记录保留为只读兼容证据 |
| 正式 Assignment | 0 | 2 | 从两条有效旧关系安全回填 |

## 4. 安全边界

- 未把 Position 当 Role；岗位回答“人在组织中做什么”，Role 回答“系统允许做什么”。
- Department 只引用真实部门；特殊 Scope 不再写入部门字段。
- Permission、Gate、Workflow 保持分离；本轮没有把业务状态或流程条件塞入 Permission Profile。
- 没有切换直接采购、人工维护 SupplierMaterialPrice、PurchaseOrderGate 或采购审批作为首批试点。
- 银行发送、付款执行、凭证、总账、生产密钥和真实网络发送均未开放或写入。
- AI 边界固定为 `ADVISORY_ONLY`，不允许 AI 自动授予权限或扩大范围。

## 5. 已知阻断与最终状态

核心实现、专项测试、Django 检查、模型迁移一致性、直接 Vite 生产编译、R5.1 和浏览器试点均通过。完整 `npm run build` 仍在既有 `PCE-WEB-ACCEPTANCE-V1.1` 的 7 个 SCM 静态 blocker 处停止；这些 blocker 与本轮组织权限核心无关，本轮没有扩大修改范围去掩盖它们。

正式指令要求全文读取名为“ProfitOS 组织权限全局架构审计与 SCM 静态门禁关联诊断报告”的报告 A。仓库未发现该精确文件，只发现并全文读取最接近的 `组织、岗位、账户、角色、权限体系专项报告.md`。因此不能宣称报告 A 精确原文已经审核完毕。

2026-08-16，用户完成最终报告原文与真实浏览器截图审核并明确签发 `Human Acceptance = PASS`。本报告的最终批准状态由最终封板报告统一收口为：

```text
PCE ORGANIZATION & ACCESS CORE V1 = BASELINE
权限专项 = CLOSED
Full Project Build = BLOCKED BY EXISTING SCM STATIC GATES
```

该专项基线不等于 Full Project Build PASS，也不等于全项目 Ready Gate PASS。后续停止权限专项开发，SCM 7 项历史静态门禁等待独立指令处理。
