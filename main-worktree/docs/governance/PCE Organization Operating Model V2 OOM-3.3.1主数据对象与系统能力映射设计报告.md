# PCE Organization Operating Model V2 OOM-3.3.1 主数据对象与系统能力映射设计报告

日期：2026-08-18  
阶段：OOM-3.3.1 Master Data Object to System Capability Mapping Design（主数据对象与系统能力映射设计）  
文档类型：DESIGN ONLY / DOCUMENTATION INTEGRITY RESTORED（仅设计／文档完整性已恢复）  
实施授权：NOT AUTHORIZED（未授权实施）

## 1. 文档状态

本文件是 OOM-3.3.1 正式设计正文的恢复归档，用于说明 Organization Operating Model V2（企业组织运行模型 V2）中各类组织主数据事实需要哪些软件能力支撑，以及这些能力不得跨越的边界。

本次修复依据已归档的 OOM-3.3.2、OOM-3.3.3、OOM-3.3.4、OOM-4、OOM-4.1.1 至 OOM-4.1.4 和 BAC-0/BAC-1 基线恢复原设计语义。它不是重新评估架构门禁，不新增实施授权，也不进入代码、数据库、页面、API（接口）、RRE（责任解析引擎）或 Workflow Runtime（流程运行引擎）实施。

```text
Document Body = RESTORED
Design Scope = MASTER DATA OBJECT CAPABILITY MAPPING ONLY
Implementation Authorization = NO
```

## 2. 设计目标

本报告解决：

> Company（公司）、Organization Unit（组织单元）、Position（岗位）、Responsibility（责任）、PositionResponsibility（岗位责任关系）和 Employee Assignment（员工任职关系）如何映射为未来软件能力，同时保持企业事实、治理、权限、流程和智能能力之间的边界。

设计目标：

1. 明确每个对象的唯一事实来源；
2. 识别当前已有能力和缺口；
3. 定义未来需要的软件能力；
4. 明确可以自动化的校验和必须由人完成的业务决定；
5. 保证 BAC、AuthorizationService、Workflow、AI、Digital Twin 和 RRE 只能按其边界消费或治理事实；
6. 禁止建立平行事实模型或通过名称、角色、权限推断企业事实。

## 3. 已读取治理基线与判断依据

### 3.1 OOM-3.3 系列基线

| 实际路径 | 文件用途 | 关键原文 | 对本报告的约束 |
|---|---|---|---|
| `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-3.3.2组织主数据变更管理能力边界设计报告.md` | 变更申请、影响分析和正式事实执行边界 | “Change Request 需要成为独立治理对象” | 对象维护能力必须与正式事实分离 |
| `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-3.3.3治理权限与角色边界设计报告.md` | Data Owner、治理角色、Role、Permission 边界 | “Role 回答能力集合；Responsibility 回答业务责任” | 对象能力不能把责任等同于授权 |
| `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-3.3.4人工智能数字孪生与控制能力边界设计报告.md` | AI、Digital Twin、Control 边界 | “只能观察、建议、模拟、阻断” | 智能能力不能修改企业事实 |

### 3.2 OOM 实施证据基线

已读取：

- `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-4实施准入与验收门禁设计报告.md`
- `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-4.1.1组织模型Schema实施包设计报告.md`
- `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-4.1.2组织服务能力实施包设计报告.md`
- `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-4.1.3组织管理页面实施包设计报告.md`
- `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-4.1.4组织数据初始化与验收实施包设计报告.md`

关键判断：

```text
Employee.position_ref = Current Primary Position Projection
PositionResponsibility = 原地演进，不创建 PositionResponsibilityV2
OrganizationOperatingService = 唯一正式事实执行入口
Page = 展示事实并提交 Change Request
Initialization = 人工确认的受控批次，不是 Migration 默认数据
```

### 3.3 BAC（业务动作契约）基线

| 实际路径 | 文件用途 | 关键原文 | 对本报告的约束 |
|---|---|---|---|
| `D:\Dev-PCE\Source\docs\governance\PCE Business Action Contract V1 BAC-0架构签发报告.md` | 动作语义架构基线 | Server Business Action Contract 是唯一动作事实源 | 组织对象不能创建业务动作 |
| `D:\Dev-PCE\Source\docs\governance\PCE Business Action Contract V1 BAC-1架构与契约定义设计报告.md` | 动作契约模型设计 | `requiredResponsibility` 与 `requiredPermission` 分离 | 责任发现与授权裁决不得混合 |

## 4. 当前模型能力分析

### 4.1 Company（公司）

实际模型：`D:\Dev-PCE\Source\backend\system\models.py:59`

当前能力：

- 具有稳定 ID、公司编码、公司名称和启停状态；
- 是 OrganizationUnit、Department、Position、User 和授权范围的公司边界；
- 可作为组织查询和跨公司校验的根事实。

当前缺口：

- 缺少统一的变更申请、影响分析、独立审核批准和历史治理闭环；
- Company 自身的时态和合并语义尚未形成完整服务能力。

复用判断：`REUSE`。不得新建 CompanyV2；未来通过治理能力增强，不由页面直接修改。

### 4.2 OrganizationUnit（组织单元）

实际模型：`D:\Dev-PCE\Source\backend\system\models.py:75`

当前能力：

- 表达公司、事业部、中心、部门、团队等组织类型；
- 具有 Company、parent、自关联层级、有效期和启停状态；
- 现有 OrganizationOperatingService 已提供父子循环、跨公司和期间校验；
- EnterpriseOrganizationModelService 可形成服务端关系树投影。

当前缺口：

- 合并、拆分、迁移、停用影响分析和历史查询能力不完整；
- 当前直接保存尚未经过 Change Request、Review 和 Approval；
- 组织负责人、岗位、任职和流程范围影响需要统一分析。

复用判断：`REUSE AND EXTEND CAPABILITY`。不新建第二组织单元模型。

### 4.3 Position（岗位）

实际模型：`D:\Dev-PCE\Source\backend\system\models.py:280`

当前能力：

- 关联 Company、Department、JobFamily、JobLevel 和 parent_position；
- 具有描述、职责摘要、有效期和启停状态；
- 可承载 PositionResponsibility；
- 可在综合组织模型中展示层级和当前任职人数。

当前缺口：

- 生命周期变更尚未统一经过影响分析和治理审批；
- 停用岗位时对任职、岗位责任、子岗位和流程引用的阻断不完整；
- `default_role` 仍需持续声明为兼容参考，不得被当作实际授权事实。

复用判断：`REUSE`。岗位是责任承载载体，不是 Employee、Role、Permission 或审批人。

### 4.4 Responsibility（责任）

实际模型：`D:\Dev-PCE\Source\backend\system\models.py:394`

当前能力：

- `system.Responsibility` 已作为唯一责任目录事实源；
- 具有 code、name、description、category、status 和有效期；
- 支持 DRAFT、ACTIVE、SUSPENDED、EXPIRED 生命周期；
- ResponsibilityCatalogService 提供列表、详情、关联岗位和审计投影；
- OrganizationOperatingService 提供编码、生命周期和有效期校验。

当前缺口：

- Change Request、独立审核批准和 BAC 引用影响分析尚未实施；
- 责任停用/失效前对 PositionResponsibility、流程责任和未来 RRE 的影响需要显式展示；
- 当前服务仍能在授权后直接保存正式事实。

复用判断：`REUSE AS SOLE FACT SOURCE`。禁止 ResponsibilityV2，禁止页面、Workflow、RRE 或 AI 自动创建责任。

### 4.5 PositionResponsibility（岗位责任关系）

实际模型：`D:\Dev-PCE\Source\backend\system\models.py:420`

当前能力：

- 明确连接 Position 与已有 Responsibility；
- 当前用 `is_primary` 和 `active` 表达 PRIMARY/SUPPORTING 及启停；
- 责任目录详情可显示关联岗位；
- 当前服务支持人工选择责任并建立关系。

当前缺口：

- 尚无完整有效期间、治理状态、来源和历史期间；
- 当前唯一关系行不适合表达同一岗位责任的多时段历史；
- 尚无 PRIMARY 重叠、责任空档、多人候选和 BAC 影响分析闭环。

复用判断：`REUSE AND TEMPORALLY EXTEND IN PLACE`。禁止 PositionResponsibilityV2 或其他平行关系表。

### 4.6 Employee Assignment（员工任职关系）

当前事实基础：`D:\Dev-PCE\Source\backend\pfm\models.py:6` 的 Employee，以及 `position_ref`、`department_ref` 字段。

当前能力：

- Employee 可关联当前正式部门和一个当前岗位；
- 员工、账户、部门、岗位和汇报关系能够服务端读取；
- EmployeeReportingRelation 可表达直属/职能主管，但它不是任职事实。

当前缺口：

- `Employee.position_ref` 不能表达多岗位、兼岗、代理、借调、未来生效或完整历史；
- 不能严格回答指定时点谁在某岗位任职；
- 不能作为未来 RRE 的长期时态事实源。

复用判断：Employee 继续作为员工档案；未来增加最小 EmployeePositionAssignment，并把 `position_ref` 降为 Current Primary Position Projection（当前主岗位投影）。禁止 EmployeeAssignmentV2 或从主管关系推断任职。

## 5. 主数据对象到系统能力映射

| 对象 | 唯一事实来源 | 当前可复用能力 | 未来需要能力 | 强制边界 |
|---|---|---|---|---|
| Company | `system.Company` | 查询、公司范围、启停 | 变更申请、合并影响、历史审计 | 页面不能直接修改 |
| OrganizationUnit | `system.OrganizationUnit` | 层级、类型、有效期、循环校验 | 调整、合并、停用、时点查询 | Workflow 不创建组织 |
| Position | `system.Position` | 部门/族/等级/父岗/有效期 | 生命周期、停用影响、历史查询 | 不自动产生责任、角色、权限 |
| Responsibility | `system.Responsibility` | 独立目录、生命周期、详情审计 | 变更治理、BAC 引用影响、退役控制 | 页面/AI/RRE 不自动创建 |
| PositionResponsibility | `system.PositionResponsibility` | 岗位选择已有责任、主责/协助 | 时态、历史、范围、重叠校验 | 不建 V2，不按名称推断 |
| Employee Assignment | 未来 `pfm.EmployeePositionAssignment` | `Employee.position_ref` 兼容当前投影 | 主岗、多岗、代理、调岗、时态历史 | 不推断责任，不自动授权 |

## 6. 对象能力边界

### 6.1 允许自动化的能力

- 编码、必填、枚举和引用校验；
- 跨公司引用阻断；
- 组织和岗位层级循环检测；
- `[effective_from,effective_to)` 有效期和重叠检测；
- 影响对象清单生成；
- 数据缺失、责任空档、多候选和无任职告警；
- Before/After、操作者、原因和时间审计；
- 服务端刷新回读与数量/摘要校验。

### 6.2 必须人工完成的能力

- 判断公司、组织单元和岗位是否应该存在；
- 定义岗位族、岗位等级和岗位业务含义；
- 创建、修改、暂停或退役 Responsibility；
- 决定哪个 Position 承担哪个 Responsibility；
- 确认员工主岗、兼岗、代理和任职有效期；
- 审核影响、批准变更和签发初始化数据。

### 6.3 禁止自动化的能力

- 根据名称、关键词或组织层级创建责任；
- 根据 Position 创建 Role 或 Permission；
- 根据 Permission 寻找责任人；
- 根据经理、主管或管理员身份兜底任职；
- 根据 RRE 结果修改组织事实；
- 由 Workflow 完成状态直接写正式事实；
- 由 AI、Digital Twin 或 Control 自动修复主数据。

## 7. 核心语义边界

```text
Position（岗位）≠ Employee（员工）
Position（岗位）≠ Responsibility（责任）
Responsibility（责任）≠ Role（角色）
Responsibility（责任）≠ Permission（权限）
Employee（员工）≠ Responsibility（责任）
Role（角色）≠ Organization Governance Role（组织治理角色）
```

正式解释：

- Position 回答“企业组织中有什么职位”；
- Responsibility 回答“企业业务中应该承担什么责任”；
- PositionResponsibility 回答“哪个岗位在什么期间承担责任”；
- Employee Assignment 回答“当前哪个员工在什么期间任职”；
- Role 回答“账户拥有哪些系统能力集合”；
- Permission 回答“账户是否具备某个系统动作能力”；
- AuthorizationService 回答“当前执行是否被允许”。

## 8. 与 BAC 和 RRE 的对接关系

目标链路：

```text
Business Action Contract（业务动作契约）
↓ requiredResponsibility（所需责任编码）
Responsibility（责任）
↓
PositionResponsibility（岗位责任关系）
↓
Position（岗位）
↓
Employee Assignment（员工任职关系）
↓
Employee（员工）
```

并行授权链：

```text
Business Action Contract
↓ requiredPermission（所需权限编码）
AuthorizationService
↓
ALLOW / DENY
```

RRE 只读消费 BAC 和 OOM 的有效时点事实。RRE 不能：

- 创建或修改 Responsibility；
- 建立 PositionResponsibility；
- 建立、修改或结束 Employee Assignment；
- 通过 Permission 消除多人候选；
- 用主管、管理员或旧审批人兜底；
- 自动授权或创建 ApprovalTask。

BAC 只能引用已有责任，不能根据 actionCode 自动生成责任。当前 BAC-1 和 RRE-1 仍未获得实施授权。

## 9. 与 OOM-3.2 和 OOM-3.3 的对接

正式治理链：

```text
Change Request（变更申请）
↓
Impact Analysis（影响分析）
↓
Review（审核）
↓
Approval（批准）
↓
AuthorizationService（执行权限复核）
↓
OrganizationOperatingService（唯一事实执行）
↓
Audit + Server Readback（审计与服务端回读）
```

边界：

| 能力 | 可以做什么 | 不能做什么 |
|---|---|---|
| Change Request | 保存拟议变更和影响证据 | 冒充正式组织事实 |
| AuthorizationService | 判断是否允许执行维护动作 | 决定谁应该批准、谁承担责任 |
| Workflow Runtime | 承载审核和批准过程 | 创建责任、修改岗位或任职 |
| AI | 提醒缺失、推荐配置、解释影响 | 自动创建或批准事实 |
| Digital Twin | 读取快照、模拟拟议变更 | 成为事实源或回写事实 |
| Control | 确定性校验、阻断、告警和留证 | 自动修复企业事实 |
| OrganizationOperatingService | 执行已批准且到期的正式变更 | 自行决定业务批准 |

## 10. 当前能力与未来能力差距

| 能力领域 | 当前已有 | 未来需要 | 本阶段范围 |
|---|---|---|---|
| 事实模型 | Company、OrganizationUnit、Position、Responsibility、PositionResponsibility、Employee | EmployeePositionAssignment、岗位责任时态扩展 | 仅设计说明 |
| 事实读取 | 服务端综合投影、责任目录、组织范围 | 统一 As Of 当前/历史/未来查询 | 不实施 |
| 事实写入 | Authorization+事务+校验+审计 | 只执行已批准 Change Request | 不实施 |
| 变更治理 | 修改原因和事实审计 | 申请、影响、审核、批准、生效、幂等 | 不实施 |
| 页面 | `#/organization` 正式入口 | 提交申请、查看影响和审批；综合页完全只读 | 不修改页面 |
| 初始化 | 当前事实和兼容字段可盘点 | 候选、人工确认、隔离预演、受控批次 | 不导入数据 |
| 权限 | AuthorizationService、Role/Permission/Scope | 治理动作与职责分离证据 | 不改权限模型 |
| RRE | 设计存在 | 只读解析和 Evidence | 不启动 |
| Workflow | 可承载任务 | 仅承载治理流程，不写事实 | 不集成 |

## 11. Gate-1 证据完整性要求

本报告作为 Gate-1 Architecture（架构门禁）证据，应证明：

1. 六类主数据对象具有明确事实来源；
2. 当前模型的复用与扩展边界清楚；
3. 不建设平行 Company、Position、Responsibility 或 PositionResponsibility 模型；
4. Responsibility、Role、Permission 和 Position 严格分离；
5. Employee Assignment 缺口被明确识别；
6. Change Request、AuthorizationService、Workflow、AI、Digital Twin、Control 和 RRE 均不成为组织事实来源；
7. 当前文档修复不自动触发 Gate 重评估或实施授权。

是否通过 OOM-4 Gate 必须由后续独立评审决定。本报告仅恢复缺失的架构证据正文。

## 12. 本阶段不包含

- 不修改 `backend/system/models.py` 或 `backend/pfm/models.py`；
- 不创建 EmployeePositionAssignment；
- 不扩展 PositionResponsibility；
- 不创建 Change Request Schema；
- 不修改 OrganizationOperatingService；
- 不创建 API、页面或 Migration；
- 不导入或修复企业数据；
- 不修改 Role、Permission 或 AuthorizationService；
- 不修改 Workflow Runtime 或 ApprovalTask；
- 不启动 RRE、Shadow Mode 或 Workflow Integration；
- 不重新评估 OOM-4 Gate 或 OOM-4.2 实施授权。

## 13. 保护声明

本轮只修复本 Markdown 文件正文。未修改代码、数据库、模型、页面、API、权限、Workflow、RRE 或业务数据。

```text
Documentation Changed = YES
Code Changed = NO
Database Changed = NO
Migration Created = NO
API Created = NO
Organization Data Changed = NO
Responsibility Data Changed = NO
Employee Data Changed = NO
Permission Model Changed = NO
Workflow Runtime Changed = NO
ApprovalTask Changed = NO
RRE Started = NO
Unauthorized Business Writes = 0
```

## 14. 最终状态

```text
OOM-3.3.1 Documentation Integrity Repair = COMPLETE
OOM-3.3.1 Master Data Capability Mapping Design = COMPLETE
OOM-4 Gate Review = NOT STARTED
OOM-4.2 Implementation Authorization Review = NOT STARTED
Organization Model Implementation = NOT AUTHORIZED
RRE-1 = NOT AUTHORIZED
Workflow Integration = NOT AUTHORIZED
```

本报告正文恢复完成并以原文件名重新归档。执行到此停止，等待后续独立架构决策。
