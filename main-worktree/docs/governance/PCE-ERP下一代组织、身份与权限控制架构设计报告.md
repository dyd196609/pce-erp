# PCE-ERP 下一代组织、身份与权限控制架构设计报告

报告日期：2026-08-16（Asia/Shanghai）  
任务类型：`NEXT-GENERATION ARCHITECTURE DESIGN`  
报告状态：`RECOMMENDATION ONLY（仅设计建议，未实施）`

> 本报告只形成目标架构、边界、历史处置和实施路线。本轮没有修改采购业务、权限 Runtime、Workflow、Gate、Role、Permission 或数据库；没有执行 Migration、没有删除文件、没有修复 SCM Static Gate、没有创建采购订单。

## 1. Executive Summary（总体结论）

PCE-ERP 应选择“保留正式组织与人员主数据，重新设计统一授权运行核心，逐动作替换旧 Runtime”的路线，而不是把现有多套权限引擎永久拼接在一起。

未来由一个后端 `Authorization Service` 对“谁、在什么组织和数据范围内、能否对哪个业务对象执行哪个动作”作最终判断。Role 是跨 ERP 模块复用的授权集合，Position 仍是组织岗位，两者不等同。业务动作由公共 `Business Action Registry` 登记；Scope 使用独立、类型化的正式结构，不再借用 `department_id`。Workflow 只负责流程、任务、顺序和职责分离；Gate 只负责业务数据资格；前端和 Meta Runtime 只消费服务端权限事实。

当前采购系统是受保护业务。新核心必须先在独立管理面和低风险动作上验证，通过影子判定、双读比较、逐动作开关和可回退 Adapter 后，才进入 SCM。`SupplierMaterialPrice`、直接采购、`PurchaseOrderGate` 和采购审批在切换前保持现状，禁止以架构统一为由抢先重构。

明确推荐：

- 主数据：保留 `system.User / Company / Department / Position` 与 `pfm.Employee`。
- 运行核心：新建公共 `Authorization Service`，不把现有任一类直接扩张为永久核心。
- 现有 `BusinessPermissionAuthorization`：`REPLACE`，其有效查询逻辑可迁入新核心。
- `ActionPermissionValidator`：`REFACTOR` 为 Workflow/业务 Guard 编排器，授权部分委托统一服务。
- 前端 `permissionEngine`、`rbacEngine`：`REPLACE` 为 Permission Profile 消费层。
- 无消费者的 Domain 权限引擎和确认无正式用途的 Demo 权限事实：满足前置条件后 `DELETE`。

## 2. 设计原则

1. **未来效率优先**：新模块只声明业务动作、角色授权与适用 Scope，不再创建模块专属 Permission Engine。
2. **不为整合而整合**：历史能力按 `KEEP / REFACTOR / REPLACE / DELETE` 处置；永久 Adapter 不是目标。
3. **允许重设计**：现有职责交叉、字段复用和前端权限真相可以废弃，但必须影子验证、可回退。
4. **保护采购**：R5.1 与 R10 的已验收边界是迁移不变量。
5. **服务端唯一裁判**：按钮可见性不是授权；所有写动作必须由后端再次授权。
6. **事实唯一**：API、Profile、页面、诊断、`strictFacts` 与验收报告复用同一授权决定。
7. **默认拒绝、最小权限**：身份、动作、对象、Scope 或证据缺失时返回拒绝/`UNKNOWN`，不得默认放行。
8. **流程、权限、Gate 分离**：Authorization 判断“人能否做”；Gate 判断“数据是否能做”；Workflow 判断“现在是否轮到做”。
9. **AI 仅建议**：AI 不成为最终授权者，不得自动授予高风险权限。

## 3. 审计基础与当前可复用资产（KEEP）

### 3.1 已读取并采用的治理事实

本报告完整读取并采用以下现行文件：

- `docs/governance/组织、岗位、账户、角色、权限体系专项报告.md`（上一轮完整组织权限专项审计及 R10/SCM 静态门禁事实）
- `docs/standards/PCE-DEVELOPMENT-STANDARD-V1.0.md`
- `docs/standards/PCE-BUSINESS-ACTION-PERMISSION-V1.0.md`
- `docs/governance/01-开发治理总纲/PCE-ERP开发治理总纲.md`
- `docs/governance/02-架构与运行边界/PCE-ERP架构与运行边界规范.md`
- `docs/governance/03-业务流程运行治理/PCE-ERP业务流程运行治理规范.md`
- `docs/governance/PCE-ERP智能化开发总纲.md`
- `docs/governance/06-模块专项治理/SCM/PCE-ERP-SCM专项治理规范.md`
- `docs/governance/真实运行验收规范.md`
- `docs/governance/Schema规范.md`、`Runtime职责规范.md`
- `docs/Architecture.md`、`docs/Enterprise Process Operating System.md`、`docs/Enterprise OS UI Model.md`

上一轮已确认且本轮不得推翻的基线包括：R5.1 采购回归通过、R10 前后端隔离通过、采购订单计数 218→218；正式组织/人员模型已建立；普通采购员对人工价格维护前端禁用且后端返回 403。

### 3.2 KEEP 清单

| 资产 | 结论 | 保留边界 |
|---|---|---|
| `system.User` | KEEP | 唯一登录账户来源；继续使用 Django 密码、会话与账号状态能力 |
| `system.Company` | KEEP | 法人/企业主档；后续统一命名为 Organization 的法人层 |
| `system.Department` | KEEP | 部门树正式来源；需补强有效期/层级治理但不另建第二主档 |
| `system.Position` | KEEP | 岗位主档；不得再把 Position 或其 Django Group 直接当企业 Role |
| `pfm.Employee` | KEEP | 唯一真实员工档案；`User ↔ Employee` 一对一关系继续保留 |
| `system.Role / Permission / RolePermission` 中的正式数据概念 | KEEP（数据语义） | 记录可迁入目标结构；当前运行方式另行 REFACTOR |
| `PCE-BUSINESS-ACTION-PERMISSION-V1.0` 的服务端最终校验原则 | KEEP | 契约升级但不降低安全边界 |
| 已验收采购 Guard、状态机、Provider、R10 用例 | KEEP | 作为迁移不变量和回归基线，不在权限项目中重写 |

## 4. 当前需要改造资产（REFACTOR）

| 资产 | 改造方向 |
|---|---|
| `system.Role / Permission / RolePermission` Runtime | Role/Permission 成为公共授权配置；增加版本、风险、有效期、审计和 Scope 绑定，取消模块本地角色真相 |
| `UserOrganizationRoleAuthority` | 从 Workflow 所有权移出；拆分用户角色授权与数据 Scope，消除 `department_id` 多义编码 |
| `workflow_runtime.ActionPermissionValidator` | 保留选择数、对象存在性、状态和流程检查；角色、Permission、Scope 判断改调统一授权服务 |
| `pceBusinessActionRegistry` | 保留公共 Registry 思想；以后端登记为唯一事实，前端只接收投影，消除前后端重复动作清单 |
| Workflow string role | 流程定义只引用稳定的 `requiredActionCode` 或能力要求；字符串 Role 不再成为企业授权真相 |
| Django Group/Permission 使用方式 | 保留 Django 框架能力用于管理后台/框架兼容；解除 Position=Group 与企业 Role 的隐式关系 |

## 5. 当前需要替换资产（REPLACE）

| 资产 | 替换结论 |
|---|---|
| `BusinessPermissionAuthorization` | 由新的公共 `AuthorizationService` 替换；现有 RolePermission 查询和 R10 行为作为迁移输入与回归基线 |
| Meta `permissionEngine` | 替换为 `PermissionProfileClient + PermissionFactResolver`，不得内置 admin/manager/viewer 权限真相 |
| Meta `rbacEngine` | 替换为同一 Profile 消费层，不保留第二套角色映射 |
| Enterprise OS localStorage 角色/权限模型 | 替换为服务端 Identity/Authorization API；localStorage 只可保存无安全意义的 UI 偏好 |
| 前端/后端重复动作注册 | 替换为后端 Canonical Registry + 版本化只读投影/构建生成物 |

## 6. 当前建议删除资产（DELETE 候选）

引用计数口径：2026-08-16 对 `backend` 与 `frontend/src` 源码扫描，排除 `node_modules`、测试产物、Checkpoint、文档、图片和 JSON 证据；“消费者”不计文件自身。

| 候选 | 当前消费者 | 是否真实运行 | 删除影响 | 删除前置条件 |
|---|---:|---|---|---|
| `frontend/src/domain/permission/permissionEngine.js` | 0 | 未发现调用 | 低 | 构建与全局 import 扫描为 0 后直接删除 |
| `frontend/src/meta/domain/employeeModel.js` | 1（`reviewEngine`） | 仅审查/Demo 投影 | 中 | `reviewEngine` 改读服务端只读身份快照 |
| `frontend/src/meta/domain/organizationModel.js` | 1（`reviewEngine`） | 仅审查/Demo 投影 | 中 | 同上，并确认 Review 页面不再依赖 Demo |
| `enterpriseOperationModel/Store` 内本地 role/permission | 1 个主要页面消费者；Model 另有采购询价用户 Provider 引用 | 部分路由仍运行 | 高 | 先切换 `/organization/*` 子路由和采购询价 Provider；迁移仅 UI 偏好，禁止迁移本地权限事实 |
| `enterpriseOSModel.organizationNodes` | 2 个对 Model 的上层消费者，节点本身无独立服务端来源 | Dashboard/Runtime 展示 | 中 | 改读组织摘要 API，冻结页面字段与回归证据 |
| 重复 Demo organization/employee 集合 | 多处分散，尤其 manufacturing sample/store | Demo/制造基础页可能运行 | 高 | 逐集合确认 Production/Canary/Demo 模式；只删除正式运行链上的伪事实，保留显式隔离测试 Fixture |

删除必须独立立项。当前引用不等于业务价值；引用为 0 仍需 Build 和页面回归，引用大于 0 必须先替换消费者。本轮未删除任何文件。

## 7. 下一代组织身份架构

```text
Company（法人/公司）
  └─ Department（部门，可形成树）
       └─ Position（组织岗位）
            └─ Employee（真实员工）
                 ↔ User（登录账户，原则上一对一）
```

职责定义：

- Company：法人、租户内公司和授权组织边界。
- Department：组织层级与数据归属，不承载 Scope 特殊值。
- Position：员工承担的组织职位，不直接等于 Role。
- Employee：人员主档、在离职状态、组织与岗位关系的权威来源。
- User：认证身份、启停和登录安全；不得以 username 硬编码授权。

未来如出现兼职、多岗位或跨公司任职，应新增版本化 `EmployeeAssignment`，而不是让 Employee 字段保存多个混合值。该建议属于未来模型设计，本轮不建表。

## 8. 下一代 Role / Permission 架构

### 8.1 概念

- Position 回答“员工在组织中担任什么职位”。
- Role 回答“登录身份获得哪组系统能力”。
- Permission 以业务动作授权为主，代码与 Business Action 一一关联或稳定映射。
- 用户可以有多个 Role；Role 可以有多个 Permission；Permission 可属于多个 Role。

### 8.2 建议未来数据结构

| 对象 | 关键字段（设计） | 说明 |
|---|---|---|
| `Role` | code, name, risk_level, active, version | 跨模块公共角色，不绑定 Position |
| `Permission` | code, action_code, name, module_code, risk_level, active | 业务动作权限；展示/字段权限可作为独立类别但仍集中登记 |
| `RolePermission` | role, permission, constraints, valid_from/to | 唯一 role+permission，支持期限和约束 |
| `UserRoleGrant` | user, role, organization, active, source, valid_from/to, version | 用户角色授权事实及审计来源 |
| `ScopeDefinition` | scope_code, name, resolver_code, active, version | SELF/DEPARTMENT/ORGANIZATION/ALL/CUSTOM 正式字典 |
| `GrantScopeBinding` | user_role_grant, scope_code | 授权与 Scope 绑定 |
| `ScopeTarget` | binding, target_type, target_id | CUSTOM 多目标，禁止 JSON 字符串拼接承担关系真相 |

## 9. Authorization Service（统一授权服务）

### 9.1 唯一入口

未来所有模块调用同一个后端服务：

```text
decide(subject, action_code, organization, department, business_object, context)
```

建议 API：

- `POST /api/authorization/decisions`：单动作最终判定。
- `POST /api/authorization/decisions/batch`：页面/列表批量判定，避免 N+1。
- `GET /api/authorization/profile`：当前用户 Permission Profile。
- `GET /api/business-actions`：版本化动作注册投影。

### 9.2 判定顺序

1. 验证 User 有效、Employee 状态和组织关系。
2. 从 Canonical Registry 读取 action，不信任客户端提交的角色、Permission 或状态。
3. 从业务对象 Provider 读取 organization、department、owner 与敏感上下文。
4. 读取有效 `UserRoleGrant → RolePermission`。
5. 由 Scope Engine 判断授权是否覆盖对象。
6. 应用授权约束、风险策略和适用的 SoD 静态冲突规则。
7. 返回决定与可审计证据；缺失事实默认拒绝。

### 9.3 统一输出契约

```json
{
  "allowed": false,
  "decisionCode": "SCOPE_DENIED",
  "reason": "当前授权范围不覆盖该业务对象。",
  "scope": {"code": "DEPARTMENT", "matched": false},
  "constraints": [],
  "facts": {
    "actionCode": "supplier_material_price.manual_maintain",
    "visible": true,
    "executable": false,
    "disabledReason": "当前授权范围不覆盖该业务对象。"
  },
  "evidenceVersion": "...",
  "policyVersion": "..."
}
```

`reason` 用于用户提示，`decisionCode` 用于协议和审计；不得向业务用户直接展示内部角色代码、Scope 技术编码或敏感策略细节。

### 9.4 为什么不直接扩张现有类

`BusinessPermissionAuthorization` 当前仅返回 Permission、roleCodes、scopeCodes，未统一对象事实、约束、版本、批量判定和完整原因；`ActionPermissionValidator` 又混合动作注册、对象状态、选择数量和授权。因此推荐重写清晰的公共核心，并迁入可复用查询逻辑，而不是继续让任一现有类膨胀。

## 10. Scope Engine（数据权限范围引擎）

正式 Scope：

| scope_code | 语义 | 匹配依据 |
|---|---|---|
| `SELF` | 本人拥有/负责的数据 | 对象 owner/employee/user 与当前身份 |
| `DEPARTMENT` | 指定部门及可配置的下级部门 | 正式 Department 关系与层级策略 |
| `ORGANIZATION` | 指定公司/法人 | 对象 organization/company |
| `ALL` | 租户内全部授权组织 | 只授予受控高权限角色，不等于跨租户 |
| `CUSTOM` | 多组织、多部门或指定对象集合 | `ScopeTarget` 结构化多目标 |

必须取消：`department_id='SELF'/'ALL'/''`。迁移期只允许一个临时 Adapter 将旧值映射为正式 Scope；Adapter 有明确退出 Phase，不允许新写入继续产生旧编码。

Scope 判定输出应包含匹配规则、目标、策略版本和解释，但 Profile 对前端只暴露必要事实。列表查询必须在服务端应用 Scope，不能先返回全量再由前端过滤。

## 11. Business Action Registry（业务动作注册中心）

Registry 是动作目录，不是用户授权表。每个动作至少登记：

- `action_code`、业务名称、module、业务对象类型；
- 风险等级、读/写/外部副作用分类；
- 所需 Permission、可用状态契约引用；
- 对象授权上下文 Provider；
- 是否需要二次确认、SoD、审计和幂等；
- 状态、版本、owner 与废弃替代关系。

推荐命名统一为小写点分格式，例如 `purchase.request.submit`。现有大写/连字符动作在迁移期通过 alias 映射，Canonical code 不随页面或路由命名变化。

后端 Registry 是唯一事实。前端 `pceBusinessActionRegistry` 暂时作为生成投影/兼容消费者，禁止继续独立新增企业角色或 Permission 真相。

## 12. Permission Profile（统一权限资料）

Profile 是当前登录身份的服务端投影，包含：

- identity 摘要：user、employee、active organization；
- roles（仅管理/诊断必要时返回）；
- action facts：visible、executable、disabledReason、constraints；
- scope 摘要与可选择组织；
- policy/profile 版本、生成时间、过期时间。

Profile 只优化展示，不替代写 API 的最终 `decide`。高风险动作执行时必须重新判定；Role/Scope 变更后使 Profile 失效。不得把完整敏感策略或其他用户权限下发前端。

## 13. Meta Runtime 接入方式

目标链：

```text
Page Schema declares action_code
  → Meta Runtime requests Permission Profile/action facts
  → Runtime renders visible/enabled/reason
  → user submits intent
  → backend Authorization Service re-decides
```

Schema 只声明动作，不声明 `admin/manager/viewer`。Meta Runtime 不保存 Role 表，不按 localStorage 推导权限，不用默认角色放行。Profile 读取失败时高风险动作必须禁用并显示“权限事实读取失败”，不得回退到旧页面缓存。

## 14. Workflow 接入方式

Workflow 保留：流程定义、步骤、顺序、任务、状态、候选职责、SoD 执行和审批历史。Workflow 不再维护企业 Role/Permission 主档。

未来 `ActionPermissionValidator` 分成两类职责：

- Workflow/Business Guard：对象存在、选择数量、状态、流程阶段、任务归属、审批顺序。
- Authorization Service：身份、Role、Permission、organization、Scope、授权约束。

流程节点引用 `requiredActionCode`。候选人解析可以向 Authorization Service 查询“谁具备动作能力”，真正执行时仍按当前对象重新判定。Workflow 中的 string role 仅作迁移 alias，不能成为授权来源。

## 15. Gate 与 Permission 分工

| 问题 | 所有者 | 示例 |
|---|---|---|
| 这个人有没有权人工维护价格？ | Authorization Service | `supplier_material_price.manual_maintain` |
| 供应商、物料、价格、日期是否有效？ | Domain Gate | SupplierMaterialPrice Gate |
| 当前是否轮到该审批任务？ | Workflow Guard | task/step/status |
| 写入是否幂等、并发版本是否匹配？ | Domain/Persistence Guard | version/idempotency |

最终执行必须同时满足 Authorization + Gate + Workflow（适用时），任何一个拒绝都不得写入。不得把数据不合格伪装成“无权限”，也不得以有权限绕过 Gate。

## 16. AI Intelligence Layer（智能权限分析层）

AI 可执行：岗位/操作分析、Role 推荐、Permission 建议、长期不用权限回收建议、异常访问预警、SoD 冲突分析和影响模拟。

AI 的正式边界：

- `ADVISORY ONLY`；输出建议、证据、置信度和风险，不直接修改 Grant。
- 任何授权变更由有权限人员显式审批，记录 before/after、理由、操作者和版本。
- 管理员、付款审批、跨组织、外部发送等高风险授权必须双人/分角色审批（按专项规则）。
- AI 无权给自身或调用身份加权，无权关闭审计、Scope 或后端校验。
- AI 输入遵守最小数据原则；训练/分析结果不能泄露其他组织或用户权限。

## 17. ERP 模块接入规范

| 模块 | 未来只需新增/配置 | 禁止 |
|---|---|---|
| SCM | 业务动作、对象授权上下文、Role-Permission、Scope、Guard 调用 | 新 SCM Permission Engine；在 R5.1/R10 保护期大面积切换 |
| Inventory | 库存动作与对象 organization/warehouse 上下文、角色授权 | 库存专属角色真相或前端行过滤作为安全边界 |
| Production | 工单/报工/投料动作、工厂/车间 Scope、SoD | 生产本地 Role 表或 Position=Role |
| Finance | 财务动作、金额/组织约束、SoD、强审计；逐步替换 `has_perm`/本地 Authority | 直接开放付款、银行发送或用 `locked` 代表可发送 |
| CRM | 从第一天接公共 Registry、Authorization、Profile | 创建 CRM 专属 Permission Runtime |

新增模块的最小权限开发包：动作登记、对象授权上下文 Provider、Role-Permission 配置、Scope 规则、服务端调用、Profile 投影、拒绝测试和人工隔离验收。无需开发新权限引擎。

## 18. 采购系统影响分析

下表区分“本轮设计影响”（均为无写入）与未来切换影响：

| 采购能力 | 未来影响 | 原因与策略 |
|---|---|---|
| 采购申请 | MEDIUM | 动作、提交/审批与 Scope 需统一；先影子判定，不改生命周期与 Provider |
| 既定价格确认 | MEDIUM | 需要动作码和对象 Scope；保持现有 Gate，逐动作切换 |
| 直接采购 | HIGH | 当前 `BusinessPermissionAuthorization` 已承载 R10 关键权限；在新服务等价测试前 `DEFER` |
| `SupplierMaterialPrice` 人工维护 | HIGH | 前端事实与后端 403 是 R10 冻结资产；最后一批 SCM 写动作切换，必须三类账户复验 |
| `PurchaseOrderGate` | HIGH | 既有页面仍调用旧前端 permissionEngine，且 Gate/Permission 易混；先分离职责，不改 Gate 结果 |
| 采购员/Employee 选择与可见范围 | LOW | 主数据保留；仅未来用正式 Scope 替换旧编码，先双读比对数量 |
| 采购审批 | HIGH | Workflow string roles、任务、状态与统一授权交叉；必须在 Workflow Adapter 成熟后迁移 |

采购稳定策略：Phase 1–3 不改采购执行路径；SCM 进入 Phase 4 前必须具备旧/新决定对比、按 action_code 开关、拒绝一致性报告和一键回退。涉及采购申请、采购订单、Gate、SupplierMaterialPrice 的大面积改造全部 `DEFER`，直到采购里程碑与专项授权成立。

## 19. Legacy Disposition Matrix（历史代码处置表）

源码引用数沿用第 6 节口径，包含定义/测试时另作说明。

| 历史实现 | 处置 | 原因 | 影响/工作量 | 采购影响 | 时机 |
|---|---|---|---|---|---|
| Django Group / Permission | REFACTOR | Django 认证能力有价值，但 Position.group 与企业 Role 容易混淆；源码涉及约 3 文件 | 小-中；解除企业授权语义，保留框架兼容 | LOW | Phase 2/8 |
| `system.Role / Permission / RolePermission` | REFACTOR | 正式数据有价值，字段和授权模型不足；约 12 源文件涉及 | 中-高；数据迁移、API、管理页 | HIGH（若直接切） | Phase 1–4 |
| `workflow_runtime.ActionPermissionValidator` | REFACTOR | 有 11 个源码引用，状态/对象校验有价值，但不能继续拥有授权真相 | 高；Workflow、银行隔离、供应商绩效等消费者 | HIGH | Phase 3–6 |
| `BusinessPermissionAuthorization` | REPLACE | 仅 3 个源码引用且能力窄，无法承载目标输出/Scope/批量/版本 | 中；复用查询逻辑、替换调用 | HIGH（直接采购/R10） | Phase 4，最后切关键写动作 |
| Meta `permissionEngine` | REPLACE | 内置 plan 与 admin/manager/viewer；15 个源码消费者 | 高；逐消费者改读 Profile | HIGH | Phase 3–7 |
| Meta `rbacEngine` | REPLACE | 第二套静态 roles；3 个源码消费者 | 小-中 | LOW | Phase 3/7 |
| Domain `permissionEngine` | DELETE | 模拟 currentUser，0 消费者 | 小 | NO IMPACT | Phase 8，Build 前置 |
| Enterprise OS local role/permission | REPLACE | localStorage 可写且有正式路由消费者，不能作为企业事实 | 高；服务端 API 与页面替换 | MEDIUM | Phase 2–3 |
| Workflow string role | REFACTOR | 角色字符串散布在动作策略中；迁移期仍需 alias | 高 | HIGH | Phase 4–6 |
| `pceBusinessActionRegistry` | REFACTOR | 14 个前端源码消费者；公共动作思想正确，但前后端重复 | 高；后端 Canonical + 前端投影 | MEDIUM | Phase 1–7 |

## 20. 两种方案成本比较

| 维度 | 方案 A：保守整合旧体系 | 方案 B：重设计运行核心（推荐） |
|---|---|---|
| 初期工作量 | 低-中，约 12–20 人周 | 中-高，约 35–52 人周 |
| 运行风险 | 初期较低，长期因多裁判/多 Adapter 上升 | 通过分阶段控制，初期可控；长期最低 |
| 未来维护成本 | 高：每个新模块继续理解多套 Engine | 低：一个决定入口、一份 Profile |
| 模块扩展效率 | 低-中 | 高：只登记动作、授权和 Scope |
| 历史包袱 | 持续累积，Adapter 永久化 | 分 Phase 清退 |
| 采购影响 | 短期低，长期每次改动都可能触碰采购 | 前三阶段无影响，SCM 延后并逐动作切换 |
| 可审计性 | 决定证据分散 | 统一 decision/evidence/policy version |
| 结论 | 不推荐作为目标架构 | **推荐** |

方案 A 仅可作为迁移期临时状态，不能成为终局。

## 21. 实施工作量与 Phase

估算为设计级范围，单位为人周，不含等待业务人员签字时间。

| Phase | 目标 | 涉及模块/文件范围 | DB | API | 前端 Runtime | 采购影响 | 人工回归 | 估算 |
|---|---|---|---|---|---|---|---|---:|
| 0 | 设计冻结、动作命名、ADR、基线 | docs/治理/验收资产 | 否 | 否 | 否 | NO IMPACT | 设计评审 | 1–2 |
| 1 | 新公共核心、Registry、Scope 模型与决定契约 | system/新公共 authorization 包、workflow 接口 | 是（新表/迁移） | 是 | 否 | NO IMPACT（不接生产链） | 单元/安全评审 | 5–8 |
| 2 | 独立权限管理页、审计、Profile | system API、组织权限管理页 | 是 | 是 | 是（仅管理面） | LOW | 管理页/账号隔离 | 4–6 |
| 3 | 低风险只读动作、影子判定、对比观测 | 一个非采购或只读动作 | 可能 | 是 | 是 | NO/LOW | 新旧决定对比 | 3–5 |
| 4 | SCM 逐动作接入 | procurement/masterdata/workflow/相关页面 | 可能 | 是 | 是 | HIGH，需专项授权 | R5.1、R10、真实账户 | 7–10 |
| 5 | Finance 接入 | finance、付款准备链；真实发送仍关闭 | 可能 | 是 | 是 | LOW（对采购） | SoD/金额/组织/零发送 | 5–8 |
| 6 | Inventory/Production/CRM | 各模块 Provider 与动作 | 可能 | 是 | 是 | LOW | 模块 Golden Path | 5–8 |
| 7 | 前端旧 Engine 退出 | 15+3 个消费者、Meta Runtime | 否/可能否 | 已有 | 高 | MEDIUM | 全导航/按钮/403 | 3–4 |
| 8 | 历史清理 | Domain Demo、localStorage 权限、alias/Adapter | 视审计 | 可能删旧 API | 中 | MEDIUM | 全量 Build/回归 | 2–3 |

总计约 35–52 人周。涉及数据库的 Phase 必须另行授权、备份、迁移演练和回滚；本报告不授权执行。

## 22. 风险清单

| 风险 | 等级 | 控制 |
|---|---|---|
| 新旧服务给出不同允许结果 | 高 | 影子判定、拒绝优先、差异报告；未归零不切写动作 |
| Scope 旧编码迁移错误 | 高 | 双读、逐授权记录对账、列表数量与对象逐项比对 |
| Position/Role 混淆造成扩大授权 | 高 | 明确模型与管理 UI，禁止自动 Position→Role |
| Profile 缓存过期导致按钮与后端不一致 | 中 | 版本/TTL/失效事件；后端执行时重判 |
| Workflow 与 Authorization 相互递归 | 高 | 单向依赖：Workflow 调 Authorization，Authorization 不调用 Workflow 状态机 |
| Registry 前后端漂移 | 高 | 后端唯一事实、版本化投影、契约校验 |
| 超级管理员绕过 Scope | 高 | superuser 仅应急治理，强审计；生产业务角色不依赖 superuser |
| Demo/localStorage 被误当正式事实 | 高 | 模式隔离、Provider 来源标记、Production 禁止回退 |
| 迁移阻塞采购开发 | 高 | Phase 1–3 与采购隔离；SCM 切换 `DEFER` 到独立里程碑 |
| AI 建议被自动执行 | 高 | 人工审批、建议与执行 API 物理分离 |

## 23. 回退策略

每个迁移动作都有独立 feature flag：`legacy / shadow / enforce_new`。

1. `legacy`：旧服务执行，新服务不参与。
2. `shadow`：旧服务执行，新服务只读判定并记录差异，不影响结果。
3. `enforce_new`：新服务执行；旧服务可只读比对。

回退单位必须是单个 `action_code + module + organization`，不得全系统 Big Bang。回退只切判定路由，不回滚业务对象、不改状态、不覆盖人工数据。数据库采用新增结构和向前兼容迁移；在清理 Phase 前保留旧读路径。任何扩大授权差异、403 异常下降、R10 失败或采购对象数量/业务键变化都立即回到 `legacy`。

## 24. SCM 7 项 Static Gate 关系

上一轮七项 blocker 为列表 quick search/高级筛选静态治理问题：前四项涉及采购询价及下一流程页面，后三项涉及供应商绩效、采购员绩效和采购异常责任分析。

| Gate | 既有分类 | 与本架构的依赖 | 结论 |
|---|---|---|---|
| SG01–SG04 | ARCHITECTURE/LEGACY | 不依赖 Role/Permission/Scope/Authorization 重设计；属于列表契约与历史页面结构 | `NO DEPENDENCY` |
| SG05–SG07 | SCM LOCAL | 不依赖统一权限核心；属于 SCM 页面筛选字段治理 | `NO DEPENDENCY` |

新权限架构不会自动修复或要求先修 SG01–SG07；七项门禁可在独立任务中处理。本轮未修复。

## 25. 推荐目标架构、唯一真相与下一步建议

```mermaid
flowchart TB
  subgraph Identity["Identity & Organization Master"]
    Company["Company / Organization"] --> Department["Department"]
    Department --> Position["Position"]
    Position --> Employee["Employee"]
    Employee <--> User["User"]
  end

  subgraph Core["Authorization Core"]
    Role["Role"] --> RP["Role Permission"]
    Permission["Permission"] --> RP
    Registry["Business Action Registry"] --> Permission
    Grant["User Role Grant"] --> Role
    Scope["Scope Engine"] --> Grant
    Auth["Authorization Service"]
    RP --> Auth
    Grant --> Auth
    Scope --> Auth
    Registry --> Auth
  end

  User --> Grant
  Company --> Scope
  Department --> Scope
  Object["Business Object Authorization Context"] --> Auth
  Workflow["Workflow Adapter"] --> Auth
  Profile["Permission Profile"] <-- Auth
  Meta["Meta Runtime Consumer"] --> Profile
  UI["Pages / UI Generator"] --> Meta
  Gate["Business Gate"] --> Execute["Controlled Action Execution"]
  Auth --> Execute
  Workflow --> Execute
  AI["AI Intelligence Layer - Advisory"] --> Review["Human Authorization Review"]
  Review --> Grant
```

唯一真相来源：

| 真相 | 唯一来源 |
|---|---|
| User | `system.User` |
| Employee | `pfm.Employee` |
| Organization/Company | `system.Company`（Department 为其组织层级） |
| Position | `system.Position` |
| Role | 目标公共 Role 主档（迁移自 `system.Role`） |
| Permission | 目标公共 Permission，与 Canonical Action 映射 |
| Scope 定义 | `ScopeDefinition + GrantScopeBinding + ScopeTarget` |
| Authorization 判定 | 新公共 `Authorization Service` |
| Business Action | 后端 Canonical Business Action Registry |
| 前端权限显示 | 服务端 Permission Profile/action facts |

下一步只能作为建议：

1. 由架构、SCM、Finance、安全和业务负责人审核本报告并冻结 ADR。
2. 先批准或否决 Phase 0；不要直接授权 Phase 1 数据库实施。
3. 为 R5.1、R10、三类真实账户、218 采购订单基线建立迁移不可变量清单。
4. 单独选择一个非采购、只读、无外部副作用动作作为未来 Phase 3 候选。
5. 在任何 SCM 实施前另发专项指令，明确动作、组织、账号、回退开关和人工验收矩阵。

---

## 附录 A：必须明确回答的 12 个问题

### Q01 未来是否值得保留现有组织、人事主数据？

**是。** `system.User / Company / Department / Position` 与 `pfm.Employee` 已形成真实运行基础，应 KEEP；只补强关系、有效期和治理，不另建第二套主档。

### Q02 Role / Permission 是否应该重新设计运行机制？

**是。** 保留正式数据语义，重新设计授权、Scope、版本、审计和唯一判定入口。

### Q03 是否应该保留 Django Group / Permission？

**保留框架能力，但不作为企业权限真相。** 处置为 REFACTOR：用于 Django 管理/兼容，解除 Position=Group 和企业 Role 的隐式绑定；确认无消费者后再考虑更深清理。

### Q04 BusinessPermissionAuthorization 应成为唯一服务还是重写公共服务？

**重写新的公共 Authorization Service。** 现有类 REPLACE，其有效 RolePermission 查询和 R10 行为迁入并作为回归基线。

### Q05 Workflow ActionPermissionValidator 如何处置？

**REFACTOR。** 保留对象、选择、状态、流程阶段校验；授权判断委托唯一 Authorization Service。

### Q06 Meta permissionEngine 如何处置？

**REPLACE。** 用 Permission Profile 消费层替换；15 个现有消费者逐一迁移，禁止一次删除。

### Q07 rbacEngine 如何处置？

**REPLACE。** 其静态角色映射没有继续成为企业真相的价值，3 个消费者迁移后删除。

### Q08 Scope 应如何重新设计？

**使用独立、类型化、版本化结构。** 正式支持 SELF、DEPARTMENT、ORGANIZATION、ALL、CUSTOM；CUSTOM 使用结构化多目标，彻底停止 `department_id` 特殊值编码。

### Q09 AI 在权限体系中的正式边界是什么？

**建议型、不可自动授权。** AI 可推荐、发现异常和 SoD 风险；任何授权变更必须由有权限人员显式审批并审计，高风险授权不得自动执行。

### Q10 如何保证采购开发不被权限重构阻塞？

**隔离 Phase 1–3，SCM 延后，逐动作影子切换。** 保持现有采购服务和 R10 路径，差异未归零不切写动作；按 action_code 回退，不做 Big Bang。

### Q11 新增 ERP 模块需要开发哪些权限内容？

**只开发动作登记、对象授权上下文、Role-Permission 配置、Scope 规则、服务端调用、Profile 展示和拒绝/隔离测试。** 不开发模块专属 Permission Engine。

### Q12 推荐整合旧体系还是重设计运行核心？

**明确推荐重设计运行核心。** 保留主数据和有效业务事实，以渐进迁移替换旧 Runtime。该方案初期工作量更高，但运行边界更清晰、未来模块效率更高、长期风险和维护成本更低。

## 附录 B：本轮治理检查

```text
Governance Files Loaded: PASS
Frozen Asset Check: PASS（仅新增设计报告）
Identity Check: PASS（完成身份与唯一真相设计）
Data Extract Check: N/A（纯设计，无 Provider/Runtime 修改）
Array Completeness: N/A（纯设计，无业务集合转换）
Regression Check: N/A（未实施；R5.1/R10 作为未来强制基线）
Automatic Acceptance: N/A（纯文档设计）
Browser Human Acceptance: N/A（无页面变更）
Build: N/A（无代码变更）
Ready Gate: N/A（报告状态为 RECOMMENDATION ONLY）
```

本轮到此停止，等待用户与 ChatGPT 审核后再决定保留、暂缓、替换或删除项。
