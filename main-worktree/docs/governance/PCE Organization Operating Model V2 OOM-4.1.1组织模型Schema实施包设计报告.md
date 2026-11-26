# PCE Organization Operating Model V2 OOM-4.1.1 组织模型 Schema 实施包设计报告

日期：2026-08-18  
阶段：OOM-4.1.1 Organization Model Schema Implementation Package Design（组织模型数据结构实施包设计）  
类型：DESIGN ONLY（仅设计）  
实施授权：NOT AUTHORIZED（未授权实施）

## 1. 结论

本报告只定义未来获得明确授权后所需的 Schema（数据结构）实施包，不修改模型、数据库或 Migration（数据库迁移）。

最小实施范围：

1. 新增 `pfm.EmployeePositionAssignment`，作为员工任职的时态权威关系；
2. 原地演进 `system.PositionResponsibility`，增加关系类型、治理状态、有效期间、来源和时间戳；
3. 保留 `Employee.position_ref` 作为迁移期 Current Primary Position Projection（当前主岗位投影），禁止长期双权威；
4. 建立统一 Temporal Query（时态查询）语义、索引、约束和兼容切换准备；
5. 不新增 `PositionResponsibilityV2`、`EmployeeAssignmentV2` 或平行组织模型；
6. 不扩展 Company、OrganizationUnit、JobFamily、JobLevel、Position、Responsibility、User、Role、Permission、Workflow 或 BAC；
7. 不在 Schema Migration 中自动创建或推断任何企业正式数据。

当前状态：Schema Package Design = COMPLETE；Schema Migration = NOT AUTHORIZED。

## 2. 已读取治理基线与判断

### 2.1 BAC-0 与 BAC-1

路径：

- `D:\Dev-PCE\Source\docs\governance\PCE Business Action Contract V1 BAC-0架构签发报告.md`
- `D:\Dev-PCE\Source\docs\governance\PCE Business Action Contract V1 BAC-1架构与契约定义设计报告.md`

用途：确认 BAC 是动作唯一事实来源，`requiredResponsibility` 与 `requiredPermission` 分离。

关键原文：

> “本次批准代表架构规则批准，不代表代码实施批准。”

> “`requiredPermission → AuthorizationService`；`requiredResponsibility → Responsibility Resolution Engine（未来）`。”

判断：Schema 包不能生成 Responsibility、Permission 或 BAC 映射，也不能改变 AuthorizationService 输入语义。

### 2.2 OOM V2 对接、OOM-1 与 OOM-2

路径：

- `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 与 Business Action Contract 对接设计报告.md`
- `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-1实施方案设计报告.md`
- `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-2实施设计与Schema决策报告.md`

用途：确认现有模型复用、Employee Assignment 缺口、PositionResponsibility 原地演进和时态模型。

关键原文：

> “当前 `pfm.Employee.position_ref` 只能表达员工的一个当前正式岗位，尚不能严谨表达多岗位、代理任职及历史时点任职。”

> “推荐新增 `pfm.EmployeePositionAssignment` 关系模型，需另行授权。”

> “是否新增平行岗位责任表：NO；原地演进 `system.PositionResponsibility`。”

> “Half-open Interval：统一使用 `[effective_from, effective_to)`。”

判断：本包严格沿用 OOM-2 决策，不重新设计第三套关系模型。

### 2.3 OOM-3～OOM-3.3.4

路径：

- `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-3数据治理与初始化方案设计报告.md`
- `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-3.1主数据责任与治理矩阵设计报告.md`
- `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-3.2组织主数据变更流程与治理闭环设计报告.md`
- `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-3.3.1主数据对象与系统能力映射设计报告.md`
- `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-3.3.2组织主数据变更管理能力边界设计报告.md`
- `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-3.3.3治理权限与角色边界设计报告.md`
- `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-3.3.4人工智能数字孪生与控制能力边界设计报告.md`

用途：确认数据治理、变更治理、权限和 AI/Twin/Control 边界。

关键原文：

> “初始化不是 Migration 默认数据，而是经过 Data Owner 与 Data Steward 确认的受控批次。”

> “Change Request 需要成为独立治理对象。”

> “拥有 Permission 的用户不会因此自动成为责任人、Reviewer 或 Approver。”

> “Autonomous Execution 不得用于组织主数据变更。”

判断：Schema 包只提供事实结构，不自动审批、授权、初始化、修复或执行。OOM-3.3.1 当前只有状态摘要，无可复核正文，仍是 OOM-4 Gate-1 归档阻断项；本轮不修复。

### 2.4 OOM-4 门禁

路径：`D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-4实施准入与验收门禁设计报告.md`  
用途：确认 Schema、Migration、治理、回退和验收门禁。

关键原文：

> “Gate-2 Data = BLOCKED。”

> “当前准入评估为 NOT READY。”

判断：本报告完成只能补充 Gate-2/4 的设计证据，不能把 Gate 状态改为 PASS。

## 3. 当前 Schema 能力审查

### 3.1 实际模型文件

路径：

- `D:\Dev-PCE\Source\backend\system\models.py`
- `D:\Dev-PCE\Source\backend\pfm\models.py`

用途：核对当前 Company、组织、岗位、责任、岗位责任、员工、账户、角色和权限字段。

### 3.2 复用/扩展/禁止矩阵

| 对象 | 当前能力 | 决策 |
|---|---|---|
| Company | code/name 唯一、is_active | 复用，本包不扩展 |
| OrganizationUnit | 公司、类型、父级、有效日期、公司内编码唯一 | 复用；未来纳入统一 Temporal Reader |
| Department | 公司、组织单元、有效日期、负责人岗位 | 复用，本包不改 |
| JobFamily | 公司、编码、名称、启停 | 复用；保持分类维度 |
| JobLevel | 公司、rank、编码、启停 | 复用；不参与责任/审批选择 |
| Position | 公司/部门、岗位族/等级、父岗位、有效日期 | 复用，本包不改 |
| Responsibility | 唯一编码、状态、有效日期 | 复用，本包不改 |
| PositionResponsibility | 岗位、责任、is_primary、active | 原地扩展时态能力 |
| Employee | 档案、department_ref、position_ref | 复用档案；position_ref 降级为投影 |
| EmployeePositionAssignment | 当前不存在 | 最小新增目标模型 |
| EmployeeReportingRelation | 直属/职能汇报及有效日期 | 复用；不得充当任职关系 |
| User/Role/Permission | 账户和授权事实 | 完全不变 |
| PositionWorkflowResponsibility | 流程责任配置与有效日期 | 不变；不接 Workflow Runtime |

### 3.3 当前关键原文

`backend/system/models.py`：

```python
class PositionResponsibility(models.Model):
    position = models.ForeignKey(Position, ...)
    responsibility = models.ForeignKey(Responsibility, ...)
    is_primary = models.BooleanField(...)
    active = models.BooleanField(...)
```

当前唯一约束为 `(position, responsibility)`，无法保留同一关系的多个历史期间。

`backend/pfm/models.py`：

```python
position_ref = models.ForeignKey(
    'system.Position', ... verbose_name='正式岗位'
)
```

单一 FK 无法表达兼岗、代理、借调、交接和历史。

## 4. EmployeePositionAssignment 目标模型

建议 Python 模型：`pfm.EmployeePositionAssignment`。  
建议数据库表：`employee_position_assignment`。  
权威语义：员工在某有效期间、某组织范围内担任某岗位的治理确认事实。

### 4.1 冻结字段

| 字段 | 推荐类型 | 必填 | 规则 |
|---|---|---|---|
| id | BigAutoField | 是 | 稳定关系标识 |
| employee | FK → pfm.Employee, PROTECT | 是 | 任职员工 |
| position | FK → system.Position, PROTECT | 是 | 任职岗位 |
| organization_unit | FK → system.OrganizationUnit, PROTECT | 是 | 目标组织证据；与岗位组织路径一致 |
| assignment_type | Enum | 是 | REGULAR、ACTING、SECONDMENT |
| is_primary | Boolean | 是 | 是否主岗，与任职性质分离 |
| effective_from | DateTime UTC | 是 | 左闭起点 |
| effective_to | DateTime UTC/Null | 否 | 右开终点；Null 为开放结束 |
| status | Enum | 是 | DRAFT、CONFIRMED、CANCELLED |
| source | Enum | 是 | MANUAL、MIGRATED、HR_IMPORT；禁止 AI_AUTOMATIC |
| source_reference | String/Null | 否 | 人工单据或外部批次引用 |
| created_at | DateTime | 是 | 创建时间 |
| updated_at | DateTime | 是 | 更新时间 |

### 4.2 语义组合

- 正式主岗：`REGULAR + is_primary=true`；
- 正式兼岗：`REGULAR + is_primary=false`；
- 临时代理主岗：`ACTING + is_primary=true`；
- 代理兼岗：`ACTING + is_primary=false`；
- 借调兼岗：`SECONDMENT + is_primary=false`。

ACTING 必须有 `effective_to`；跨公司任职 V2 默认拒绝。

### 4.3 状态与期间

`DRAFT → CONFIRMED`；`DRAFT → CANCELLED`。CONFIRMED 不改为 CANCELLED，通过关闭 `effective_to` 结束；恢复时新建 CONFIRMED 期间。

指定时点 T 的有效谓词：

```text
status = CONFIRMED
AND effective_from <= T
AND (effective_to IS NULL OR T < effective_to)
```

### 4.4 数据库约束候选

- `effective_to IS NULL OR effective_to > effective_from`；
- `assignment_type != ACTING OR effective_to IS NOT NULL`；
- FK 全部 PROTECT；
- `status`、`assignment_type`、`source` 使用受控枚举；
- 可表达的唯一候选：`(employee_id, position_id, effective_from)`；
- 复杂时间重叠、单一主岗和跨表公司一致性由事务服务强校验，不只依赖 DB。

### 4.5 索引候选

- `(employee_id, status, effective_from, effective_to)`；
- `(position_id, status, effective_from, effective_to)`；
- `(organization_unit_id, status, effective_from, effective_to)`；
- `(employee_id, is_primary, status)`；
- `source_reference` 普通索引，仅在外部批次需要时启用。

索引必须在目标数据库副本上使用真实查询计划验证，不能只按设计直接创建。

## 5. PositionResponsibility 原地时态演进

目标仍为 `system.PositionResponsibility`，禁止创建 `PositionResponsibilityV2`、ResponsibilityMappingV2 或平行表。

### 5.1 目标字段

| 字段 | 推荐类型 | 必填 | 规则 |
|---|---|---|---|
| id | BigAutoField | 是 | 关系期间标识 |
| position | FK → Position, PROTECT | 是 | 承担岗位 |
| responsibility | FK → Responsibility, PROTECT | 是 | 被承担责任 |
| relation_type | Enum | 是 | PRIMARY、SUPPORTING |
| effective_from | DateTime UTC | 是 | 左闭起点 |
| effective_to | DateTime UTC/Null | 否 | 右开终点 |
| status | Enum | 是 | DRAFT、CONFIRMED、CANCELLED |
| source | Enum | 是 | MANUAL、MIGRATED；禁止名称推断 |
| created_at | DateTime | 是 | 创建时间 |
| updated_at | DateTime | 是 | 更新时间 |

### 5.2 兼容字段

迁移期间保留：

```text
is_primary = (relation_type == PRIMARY)
active = status=CONFIRMED 且当前时点命中有效区间
```

兼容字段不是第二权威；最终应变为服务端投影。移除它们必须后续独立授权。

### 5.3 约束与索引

- 移除当前 `(position, responsibility)` 单行唯一约束；
- 新唯一候选为 `(position_id, responsibility_id, effective_from)`；
- DB Check：`effective_to IS NULL OR effective_to > effective_from`；
- 服务强规则：同一岗位/责任的 CONFIRMED 区间不得重叠；
- 服务强规则：同一时点只有一种 relation_type；
- 索引：`(position_id, status, effective_from, effective_to)`；
- 索引：`(responsibility_id, status, effective_from, effective_to)`。

同一 Responsibility 可以由多个 Position 承担；这是有效事实，RRE 应报告多候选，不得由 DB 强制唯一岗位。

### 5.4 Scope 决策

不增加 `company_id` 和自由 JSON scope：

```text
Company Scope = Position.company
Organization Scope = Position.department → OrganizationUnit
Business Scope = BAC.scopeDimensions + Business Object Facts
```

避免重复公司事实和无治理范围语言。

## 6. 统一时态模型

### 6.1 有效时间

统一业务语义为 `[effective_from, effective_to)`：起点包含、终点不包含。旧关系在 T 结束、新关系在 T 开始时可无重叠交接。

EmployeePositionAssignment 和 PositionResponsibility 使用 DateTime UTC；现有 Position、Responsibility、OrganizationUnit 的 DateField 本包不改变，其业务日区间由 Temporal Reader 按公司时区规范化。

### 6.2 查询能力

- Current Query：以服务端当前 UTC 时点执行有效谓词；
- As-of Query：以明确 T 查询历史事实；
- Future Query：查询未来已确认且将生效的期间；
- Handover Query：同时解释 T 前旧关系和 T 后新关系；
- History Query：包含结束和取消记录，不物理删除。

### 6.3 双时间证据

Valid Time 来自 effective_from/effective_to；System Time 来自 created_at/updated_at 和 OrganizationOperatingAuditRecord。第一包不新增完整双时态版本表，但必须保留审计以解释“何时记录”。

## 7. Schema Migration 准备包

以下是未来拆分建议，不执行：

| 阶段 | 目标 | 允许内容 | 禁止内容 |
|---|---|---|---|
| M0 Preflight | 固化恢复点与数据画像 | 备份、SHA256、计数、引用扫描 | 写业务数据 |
| M1 Add Assignment | 增量结构 | 新增空 EmployeePositionAssignment 表/索引 | 生成任职数据 |
| M2 Extend PR | 增量字段 | PR nullable 时态字段、枚举、索引 | 改旧权威读 |
| M3 Candidate Reconciliation | 人工对账 | 独立管理命令生成候选与差异 | Schema Migration 自动推断 |
| M4 Constraint Tightening | 收紧质量 | 确认后非空、Check、唯一候选 | 未清洗直接收紧 |
| M5 Authority Cutover | 切换读取 | 新时态关系成为权威，旧字段投影 | 双向独立写 |
| M6 Legacy Cleanup | 后续清理 | 关闭旧写路径 | 本包直接删字段 |

每个阶段必须有独立 Migration 文件、依赖、前后计数、执行时间预算、回退点和人工批准；M3 不应伪装成不可见的 Schema 数据迁移。

## 8. 数据转换准备

### 8.1 禁止自动断言

- 不按 `Employee.position_ref` 无条件生成 CONFIRMED Assignment；
- 不为缺少日期的数据编造 1970-01-01 或系统上线日；
- 不把 `PositionResponsibility.active=true` 断言为历史一直有效；
- 不从岗位名、部门名、员工名或 Role 生成 Responsibility；
- 不自动创建岗位族、岗位等级、岗位、责任或员工；
- 不运行 RRE、Workflow 或采购动作。

### 8.2 候选生成

候选行可从当前 `Employee.position_ref`、Employee.hire_date、Position.company/department/organization unit 和当前岗位责任读取，但必须标记 `UNCONFIRMED_CANDIDATE`。Data Owner/Steward 人工确认开始时间、任职类型、主岗、组织单元和来源后，才允许转为受控 MIGRATED 数据。

### 8.3 对账证据

每批记录：源数量、候选数量、确认数量、拒绝数量、歧义数量、目标数量、对象 ID 映射、数据摘要、操作者、审核人、批准人和审计记录。

## 9. Employee.position_ref 兼容策略

### 9.1 迁移前

`Employee.position_ref` 继续是当前主岗权威；新表不存在或为空。不得让 RRE 读取未确认的新关系。

### 9.2 增量结构后

旧字段继续权威，新表仅保存 DRAFT/候选或经受控批次确认的数据；执行 Dual Read Comparison（双读比对），禁止两个入口独立写。

### 9.3 权威切换后

EmployeePositionAssignment 成为任职权威；`position_ref` 由服务端投影指定时点唯一 CONFIRMED 主岗。页面不得直接编辑 `position_ref`。

### 9.4 停止旧字段写入条件

- 所有 active Employee 已完成候选对账；
- 每个主岗有确认的有效起点；
- 无跨公司、重叠、孤儿或歧义关系；
- 双读差异连续两个完整验收周期为 0；
- 所有消费者改为 Temporal Reader；
- 回退演练完成；
- Data Owner、Data Steward、技术负责人和验收负责人联合签发。

旧字段移除不在本包；先降级为只读投影，后续另行授权。

## 10. 当前与目标读写权威矩阵

| 阶段 | Assignment 读取 | position_ref | PR 读取 | is_primary/active |
|---|---|---|---|---|
| Current | position_ref | 权威 | 旧 PR 行 | 权威兼容字段 |
| Additive | 旧权威 + 新表影子比对 | 仍权威 | 旧权威 + 新字段影子 | 仍权威 |
| Reconciled | 新表优先验证、旧值对比 | 兼容 | 时态字段优先验证 | 兼容投影 |
| Cutover | EmployeePositionAssignment | 只读投影 | 时态 PositionResponsibility | 只读投影 |

任何阶段都禁止双向独立写和“读不到就回退页面缓存”。

## 11. RRE 数据准备

未来 RRE 只读链：

```text
Server Business Action Contract
→ requiredResponsibility
→ Responsibility at T
→ PositionResponsibility at T
→ Position at T
→ EmployeePositionAssignment at T
→ Employee
→ AuthorizationService Precheck
```

RRE 准入前必须确认：

- BAC 服务端契约已实现 `requiredResponsibility` 和 `requiredPermission`；
- Responsibility 状态和有效期可按 T 查询；
- PositionResponsibility 新时态字段已切换权威；
- EmployeePositionAssignment 已切换权威且 `position_ref` 只是投影；
- 多候选、无候选、无有效员工返回稳定状态，不自动修复；
- Evidence 包含关系 ID、有效区间、source、status、组织路径和查询时点；
- RRE 只读验证 `writeCount = 0`。

本包不实现或运行 RRE。

## 12. Change Request 与审计 Schema 边界

OOM-3.3.2 已决定 Change Request 是独立治理对象，但其持久化结构不在本“组织事实 Schema 最小包”中。它必须在服务能力实施包前形成独立 Schema 决策，禁止临时把 reviewer/approver/payloadHash 塞入 EmployeePositionAssignment 或 PositionResponsibility。

OrganizationOperatingAuditRecord 继续记录事实写入 Before/After、Operator、Reason 和时间；未来审核批准证据通过正式 Change Request 关联，不在关系表重复存储。

## 13. 回退准备

- M1/M2 为 Additive Schema，可关闭新能力并恢复旧读路径；
- 已确认的时态数据不物理删除，回退只撤销权威切换；
- 每阶段记录数据库备份 SHA256、表计数和迁移状态；
- 任一数量异常、约束失败、双读漂移或未授权写入立即停止；
- 回退不修改 BAC、Permission、Workflow、ApprovalTask、采购数据或 RRE；
- 正式执行前必须在隔离副本完成建表、加字段、收紧约束、切换与恢复演练。

## 14. 实施包文件清单设计

未来获批实施包至少包含：

- 模型变更说明与字段字典；
- M0 数据画像与备份摘要报告；
- 分阶段 Migration 草案及依赖图；
- 候选生成/人工确认管理命令设计；
- 约束与索引说明、查询计划验证；
- Temporal Reader 契约；
- 双读差异报告格式；
- 权威切换和旧写关闭清单；
- 回退 Runbook；
- 自动测试与人工验收清单；
- 非目标模块零变化证明。

本轮未创建上述代码或 Migration 文件。

## 15. Schema 验收设计

| 编号 | 场景 | PASS 条件 |
|---|---|---|
| SCH-01 | 新增 Assignment 空结构 | 结构存在，业务数据 0 |
| SCH-02 | Assignment FK | Employee/Position/OrgUnit 均 PROTECT |
| SCH-03 | 左闭右开 | T 交接无重叠、无空档 |
| SCH-04 | 单一主岗 | 同一时点最多一条 CONFIRMED primary |
| SCH-05 | 兼岗 | 多条非主岗有效关系可表达 |
| SCH-06 | 代理 | ACTING 必须有结束时间 |
| SCH-07 | 跨公司 | 服务端拒绝，写入 0 |
| SCH-08 | PR 历史 | 同岗位责任可保存多个非重叠期间 |
| SCH-09 | PR 类型 | PRIMARY/SUPPORTING 独立且不自动授权 |
| SCH-10 | 双读 | 新旧当前主岗差异为 0 |
| SCH-11 | position_ref 投影 | 与指定时点唯一主岗一致 |
| SCH-12 | 数据迁移 | 无自动推断、每行有人工作证据 |
| SCH-13 | RRE 隔离 | 未启动且写入 0 |
| SCH-14 | 权限/Workflow/采购保护 | 模型和业务数据无变化 |
| SCH-15 | 回退 | 撤销权威切换后旧读可用、审计保留 |

## 16. 当前门禁状态

| 门禁 | 本报告贡献 | 当前状态 |
|---|---|---|
| Gate-1 Architecture | 明确最小模型边界 | 仍 BLOCKED：OOM-3.3.1 正文缺失 |
| Gate-2 Data | 冻结目标字段、时态、兼容策略 | DESIGN COMPLETE；未获 Schema/Migration 批准 |
| Gate-3 Governance | 保留人工确认与审计边界 | BLOCKED：实名治理链未签发 |
| Gate-4 Technical | 给出分阶段 Migration/回退准备 | BLOCKED：未形成可执行包和演练 |
| Gate-5 Business | 给出数据确认点 | BLOCKED：业务数据和验收未签字 |

结论：`Organization Model Implementation = NOT AUTHORIZED`。

## 17. 保护确认

本轮只新增本设计报告，不生成 OOM-4.1.2、OOM-4.1.3 或 OOM-4.1.4。

`Documentation Changed = YES`。  
`Code Changed = NO`；`Database Changed = NO`；`Migration Created = NO`；`API Created = NO`；`Page Created = NO`。  
`Organization Data Changed = NO`；`Responsibility Data Changed = NO`；`Employee Data Changed = NO`。  
`Permission Model Changed = NO`；`AuthorizationService Changed = NO`；`Workflow Runtime Changed = NO`。  
`ApprovalTask Changed = NO`；`RRE Started = NO`；`Unauthorized Business Writes = 0`。

## 18. 最终状态

`OOM-4.1.1 Schema Implementation Package Design = COMPLETE`。  
`OOM-4.1.2 = NOT STARTED`；`OOM-4.1.3 = NOT STARTED`；`OOM-4.1.4 = NOT STARTED`。  
`Organization Model Implementation = NOT AUTHORIZED`。  
`Schema Migration = NOT AUTHORIZED`；`RRE-1 = NOT AUTHORIZED`；`Workflow Integration = NOT AUTHORIZED`。

本报告完整结束，停止等待下一步指令。
