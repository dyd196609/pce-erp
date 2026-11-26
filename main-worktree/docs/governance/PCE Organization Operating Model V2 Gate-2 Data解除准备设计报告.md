# PCE Organization Operating Model V2 Gate-2 Data 解除准备设计报告

日期：2026-08-18  
阶段：OOM-4 Gate-2 Data Preparation Design（OOM-4 Gate-2 数据门禁解除准备设计）  
类型：DESIGN ONLY（仅设计）  
当前门禁：Gate-2 Data（数据门禁）= BLOCKED（阻断）  
实施授权：NOT AUTHORIZED（未授权实施）

## 1. 设计目标与最终结论

本报告只设计 Gate-2 Data（数据门禁）从 BLOCKED 转为 PASS 所需的 Schema 批准、数据质量、候选转换、初始化签发、迁移与回退证据。

本报告不修改 Schema、不创建或执行 Migration（数据库迁移）、不导入数据、不创建 EmployeePositionAssignment（员工任职关系）实例，也不启动 RRE（责任解析引擎）。

当前结论：

```text
Gate-2 Data Preparation Design = COMPLETE
Gate-2 Data = BLOCKED
Gate-2 PASS Evidence Package = NOT ESTABLISHED
Gate-2 Data Reassessment = NOT STARTED
Implementation Authorized = NO
```

原因：目标 Schema 只有设计，Migration 未授权；现有数据缺少时态任职和岗位责任事实，数据质量、首批数据及回退证据尚未获得人工签发。

## 2. 已读取基线与判断依据

### 2.1 OOM-4 门禁基线

| 实际读取路径 | 文件用途 | 关键原文 | 判断依据 |
|---|---|---|---|
| `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-4实施准入与验收门禁设计报告.md` | 定义 Gate-2 PASS 标准 | “Schema 决策、时态模型、数据画像、转换映射、初始化” | Gate-2 必须以正式证据证明结构、转换和数据质量 |
| `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-4 Gate重新评估报告.md` | 提供当前 Gate 状态和只读盘点 | “目标数据结构未实施，Migration 未授权，当前企业数据未达到受控初始化条件” | Gate-2 必须保持 BLOCKED |

当前五门状态：

```text
Gate-1 Architecture = PASS
Gate-2 Data = BLOCKED
Gate-3 Governance = BLOCKED
Gate-4 Technical = BLOCKED
Gate-5 Business = BLOCKED
```

本报告不处理 Gate-3、Gate-4 或 Gate-5，也不重复评估 Gate-1。

### 2.2 Schema 与实施包基线

| 实际读取路径 | 文件用途 | 关键原文 | 判断依据 |
|---|---|---|---|
| `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-2实施设计与Schema决策报告.md` | 冻结目标模型与时态规则 | “Employee.position_ref 只能作为迁移期当前主岗投影”；“原地演进 system.PositionResponsibility” | 不建立平行任职或岗位责任事实源 |
| `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-4.1.1组织模型Schema实施包设计报告.md` | 定义未来 Schema 实施包 | “不在 Schema Migration 中自动创建或推断任何企业正式数据” | 迁移结构与初始化业务数据必须分离 |
| `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-4.1.4组织数据初始化与验收实施包设计报告.md` | 提供当前只读盘点、初始化和验收设计 | “候选数据必须携带来源、原值、建议值、人工确认值和差异原因” | 现有字段只能产生候选，不能自动成为正式事实 |

统一时态规则：

```text
[effective_from, effective_to)
```

即有效起点包含、有效终点不包含；相邻交接可以共用边界时点，但不得重叠。

### 2.3 数据治理基线

| 实际读取路径 | 文件用途 | 关键原文 | 判断依据 |
|---|---|---|---|
| `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-3数据治理与初始化方案设计报告.md` | 定义质量维度、初始化治理和签发 | “初始化不是 Migration 默认数据，而是经过 Data Owner 与 Data Steward 确认的受控批次” | 初始化必须人工治理和分批签发 |
| `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-3.1主数据责任与治理矩阵设计报告.md` | 定义数据对象 Owner/Steward/Reviewer/Approver | “企业事实由业务 Data Owner 定义，由 Data Steward 维护，由独立 Reviewer 审核，由独立 Approver 批准生效” | 候选确认和正式激活必须职责分离 |
| `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-3.2组织主数据变更流程与治理闭环设计报告.md` | 定义 Change Request 与受控生效 | “正式组织事实不得因页面编辑或操作者拥有维护权限而直接改变” | 初始化和转换不能绕过治理闭环 |

### 2.4 BAC 与 RRE 边界基线

| 实际读取路径 | 文件用途 | 关键原文 | 判断依据 |
|---|---|---|---|
| `D:\Dev-PCE\Source\docs\governance\PCE Business Action Contract V1 BAC-0架构签发报告.md` | 冻结业务动作权威与责任/权限边界 | “Permission 不能寻找责任人” | 不能从权限持有人生成岗位责任或任职 |
| `D:\Dev-PCE\Source\docs\governance\PCE Business Action Contract V1 BAC-1架构与契约定义设计报告.md` | 定义 `requiredResponsibility` 引用关系 | “Contract 只能引用已有 Responsibility，不能自动创建” | 责任必须先由企业治理确认 |
| `D:\Dev-PCE\Source\docs\governance\PCE责任解析引擎V1设计报告.md` | 定义责任解析消费链和异常 | RRE 读取 Responsibility、PositionResponsibility、Position、Employee | RRE 是消费者，不是数据修复或初始化工具 |

## 3. Gate-2 当前阻断原因

| 编号 | 当前缺口 | 风险 | 解除所需证据 |
|---|---|---|---|
| G2-B01 | Schema 实施未批准 | 目标关系不可落地 | 经签发的最终 Schema 决策 |
| G2-B02 | Migration 未批准 | 无受控结构变更路径 | 独立 Migration 授权与批准记录 |
| G2-B03 | EmployeePositionAssignment 未实施 | 无多岗位、代理和历史任职事实 | 模型、约束、查询和验收证据 |
| G2-B04 | PositionResponsibility 无时态字段 | 无法证明某时点岗位承担责任 | 原地时态演进与历史验收证据 |
| G2-B05 | 数据质量报告未签发 | 缺失、重复、孤儿或重叠风险未知 | 正式画像、异常清单和处置结论 |
| G2-B06 | 首批数据未确认 | 技术候选可能被误当企业事实 | Owner/Steward/Reviewer/Approver 签发批次 |
| G2-B07 | 转换映射未批准 | `position_ref` 可能伪造历史 | 逐条候选、来源和人工确认记录 |
| G2-B08 | 数据回退未演练 | 失败后无法可靠恢复 | 备份、恢复和数据核对演练记录 |
| G2-B09 | As Of 查询未验收 | RRE 可能读取错误时点事实 | 当前/历史/未来查询测试证据 |

以上任一项缺失，Gate-2 必须保持 BLOCKED。

## 4. Schema 实施准入证据设计

### 4.1 EmployeePositionAssignment（员工任职关系）

Gate-2 PASS 前必须形成以下批准证据：

| 类别 | 必须冻结内容 |
|---|---|
| 模型权威 | `pfm.EmployeePositionAssignment` 是长期任职事实；禁止 EmployeeAssignmentV2 |
| 主体关系 | Employee 和 Position 均为正式外键；跨公司 V2 默认拒绝 |
| 任职性质 | REGULAR（正式）、ACTING（代理）、SECONDMENT（借调）等受控值 |
| 主岗规则 | `is_primary` 与任职性质分离；同一员工同一时点主岗唯一 |
| 时态字段 | `effective_from` 必填；`effective_to` 可空且严格晚于起点 |
| 生命周期 | DRAFT 可确认/取消；CONFIRMED 通过结束期间终止，不覆盖历史 |
| 多岗位 | 主岗、兼岗、代理可表达；不得静默选出唯一岗位 |
| 来源证据 | 来源字段、候选批次、确认人、批准人、原因和时间 |
| 查询契约 | 支持 Current、As Of、History、Future Effective |
| 审计 | 新增、确认、结束、纠错均保留 Before/After 和治理证据 |

必须批准的核心约束：

```text
effective_to IS NULL OR effective_to > effective_from
assignment_type != ACTING OR effective_to IS NOT NULL
同一员工同一时点 CONFIRMED 主岗最多一个
同一任职事实不得存在非法重叠期间
```

### 4.2 PositionResponsibility（岗位责任关系）

必须原地演进 `system.PositionResponsibility`，禁止创建 `PositionResponsibilityV2`。

Gate-2 所需确认：

- Position 与 Responsibility 引用正式且状态可用；
- PRIMARY（主责）与 SUPPORTING（协助）为受控关系语义；
- 增加并使用 `[effective_from, effective_to)`；
- 历史行不得物理删除或被当前值覆盖；
- 同一 Scope、责任和期间的 PRIMARY 冲突必须阻断；
- Supporting 不可被当成唯一责任人选择规则；
- 关系来源、公司/组织范围、状态与治理批次可追溯；
- 当前、历史和未来时点查询返回同一服务端事实。

### 4.3 Temporal Model（时态模型）

所有时态关系统一使用：

```text
effective_from <= as_of
AND (effective_to IS NULL OR as_of < effective_to)
```

必须验证：

- 当前查询只返回当前有效记录；
- 历史查询不会被新数据覆盖；
- 未来生效不提前影响当前事实；
- 交接边界不重叠；
- 时区、日期精度和边界解释一致；
- 修正历史必须形成新治理证据，不能静默更新。

## 5. 数据质量门禁设计

### 5.1 质量维度与阻断规则

| 维度 | 必查规则 | P0 阻断示例 |
|---|---|---|
| Completeness（完整性） | 必填字段和必需关系齐全 | Position 无组织归属、正式员工无确认任职 |
| Uniqueness（唯一性） | 编码、主岗、PRIMARY 和期间无冲突 | 同公司编码重复、同一时点多个主岗 |
| Referential Integrity（引用完整性） | 所有外键存在且状态允许引用 | 关系指向不存在/退役岗位或责任 |
| Validity（有效性） | 状态、类型、范围、日期合法 | `effective_to <= effective_from` |
| Temporal Consistency（时态一致性） | 无非法重叠、空档有解释、历史可追溯 | 两条正式主岗重叠 |
| Semantic Integrity（语义完整性） | 岗位、责任、角色、权限、任职不混用 | 从 Role 生成 Responsibility |
| Governance Evidence（治理证据） | 候选、审核、批准和来源完整 | 无批准人却激活正式事实 |

### 5.2 数据质量输出

正式质量报告至少包含：

1. 检查时间、数据库摘要、应用版本和规则版本；
2. 每类对象总数、有效数、历史数和未来生效数；
3. 缺失、重复、孤儿、重叠、跨公司和状态冲突数量；
4. 每条异常的对象标识、规则、级别、Owner 和处置状态；
5. 修复前后差异及重新检查结果；
6. Data Steward 校验、Data Owner 确认、Reviewer 审核和 Approver 签发；
7. P0/P1 未决项为 0；
8. 报告文件版本和 SHA256。

## 6. 当前企业数据准备评估

OOM-4.1.4 的只读盘点结果：

| 数据对象 | 当前数量 | 当前性质 | 是否可直接成为新增 OOM V2 正式事实 |
|---|---:|---|---|
| Company | 2 | 已有事实，需对账 | 不重建；对账通过后复用 |
| OrganizationUnit | 18 | 已有 2 公司单元、16 部门单元 | 需确认生效时点和层级 |
| Department | 16 | 已有部门事实 | 需与组织单元一致性核对 |
| JobFamily | 0 | 无数据 | 不得按岗位名称自动生成 |
| JobLevel | 0 | 无数据 | 不得按职级文本自动生成 |
| Position | 35 | 有部门归属，分类/时间缺失 | 只能对账后纳入批准批次 |
| Responsibility | 1 | DRAFT | 不得自动激活 |
| PositionResponsibility | 0 | 无岗位责任事实 | 必须由业务治理人工建立 |
| Employee | 104 | 员工档案 | 不等于正式任职事实 |

主要质量风险：

```text
Position 缺 JobFamily = 35
Position 缺 JobLevel = 35
Position 缺 effective_from = 33
OrganizationUnit 缺 effective_from = 18
Employee 缺 department_ref = 52
Employee 缺 position_ref = 85
Active Responsibility = 0
PositionResponsibility = 0
```

判定：当前存在部分可复用档案，但整体不满足 Gate-2 PASS；所有缺失只是待确认事项，不能由系统自动判错、填充或推断。

## 7. Employee.position_ref 数据治理

`Employee.position_ref` 只能产生 Current Primary Position Candidate（当前主岗位候选），不能成为长期时态权威或自动转换为 EmployeePositionAssignment。

候选治理链：

```text
读取旧 position_ref
→ 生成候选记录（不写正式事实）
→ Data Steward 核对来源、员工、岗位和建议期间
→ Data Owner 确认业务事实
→ Reviewer 检查重叠、公司、状态和历史
→ Approver 批准批次
→ 获授权后形成正式 EmployeePositionAssignment
→ 服务端回读、审计和数量核对
```

每条候选至少记录：Employee、旧值、候选 Position、候选类型、候选主岗标志、建议起止时间、来源、置信说明、人工确认值、差异原因和治理人员。

禁止：默认起始日期、从部门/主管/Role 推断岗位、把空 `position_ref` 自动补成部门岗位、把当前值伪造成历史。

## 8. PositionResponsibility 数据治理

当前 `PositionResponsibility = 0` 是真实基线，不是系统应自动补齐的错误。

未来每条关系必须经过：

1. Responsibility 已由业务 Owner 定义并处于允许引用状态；
2. Position 已确认且组织/公司范围明确；
3. PRIMARY 或 SUPPORTING 由业务负责人明确选择；
4. 生效和失效时间由治理主体确认；
5. Reviewer 检查重复、重叠、多 PRIMARY、跨范围和引用影响；
6. Approver 完成独立批准；
7. 经授权的服务形成正式事实、审计并回读。

禁止从岗位名称、Role、Permission、员工姓名、汇报关系或 Workflow 节点自动生成 Responsibility 或 PositionResponsibility。

## 9. Migration 与回退证据设计

本报告不创建或执行 Migration。Gate-2 PASS 评审前至少需要：

| 证据 | 数据门禁关注点 |
|---|---|
| Migration 草案 | 只处理获批 Schema，不含自动企业事实种子 |
| 依赖与顺序 | 模型、字段、约束、索引、兼容步骤明确 |
| 迁移前备份 | 文件、时间、位置、SHA256、恢复责任人明确 |
| 数据基线 | 各对象数量、摘要、异常和审计数量可复核 |
| 候选生成方案 | 只读、可重复、输出稳定，不写正式事实 |
| 数据转换方案 | 仅消费已签发批次，逐条可追溯 |
| 校验方案 | 前后数量、引用、时态、历史和抽样回读 |
| 恢复方案 | Schema、数据和应用版本恢复步骤明确 |
| 回退演练 | 隔离副本恢复成功，RTO/RPO 和差异为可接受 |
| 失败封存 | 保留失败日志、批次、原因和审计，不静默 SQL 修复 |

Migration 的技术执行批准属于独立授权，并与 Gate-4 技术证据协同；Gate-2 只确认其数据结构、转换、校验和恢复证据是否足以保护数据。

## 10. Gate-2 Data Evidence Package（数据验收证据包）

| 编号 | 必需证据 | 最低内容 | 签发主体 |
|---|---|---|---|
| G2-E01 | 最终 Schema 决策 | 模型、字段、约束、索引、时态、无平行表 | 数据架构负责人 |
| G2-E02 | Schema/Migration 批准记录 | 范围、版本、依赖、授权边界 | 架构负责人 + DBA |
| G2-E03 | 当前数据画像 | 数量、质量维度、异常、摘要 | Data Steward |
| G2-E04 | 转换映射清单 | 旧事实、候选、确认值、来源、差异原因 | Data Owner + Reviewer |
| G2-E05 | 首批数据清单 | Company 到 Employee Assignment 的明确范围 | Data Owner |
| G2-E06 | 候选确认记录 | 逐条或受控批次确认及排除原因 | Steward/Reviewer/Approver |
| G2-E07 | 数据质量报告 | P0/P1 为 0，规则和复测证据完整 | 数据质量负责人 |
| G2-E08 | 时态查询验收 | Current/As Of/History/Future 测试 | 测试负责人 + Data Owner |
| G2-E09 | 备份恢复方案 | 恢复点、摘要、责任人、RTO/RPO | DBA/数据保管人 |
| G2-E10 | 回退演练记录 | 隔离演练、恢复核对、异常处置 | 技术负责人 + Reviewer |
| G2-E11 | 初始化治理签发 | Owner/Steward/Reviewer/Approver 与批次摘要 | 治理负责人 |
| G2-E12 | Gate-2 验收记录 | 结论、例外、未决项、签名日期 | Gate-2 签发组 |

所有证据必须有文件名、版本、Owner、签发日期和 SHA256。口头确认、页面截图或未签字清单不能单独支持 PASS。

## 11. Gate-2 PASS 判定规则

Gate-2 转为 PASS 必须全部满足：

1. G2-E01～G2-E12 全部形成并获授权主体签发；
2. EmployeePositionAssignment 目标模型及约束已实施并验收；
3. PositionResponsibility 时态能力已原地实施并验收；
4. `[effective_from, effective_to)` 在保存和查询中一致；
5. 数据画像完整，P0/P1 质量缺陷为 0；
6. `position_ref` 只生成候选，正式任职均有人工确认和批准证据；
7. Responsibility 与 PositionResponsibility 未由 Role、Permission 或名称自动生成；
8. 首批正式数据范围已由 Data Owner/Steward/Reviewer/Approver 签发；
9. 当前、历史、未来和交接查询验收通过；
10. 备份恢复和回退演练通过；
11. 未授权业务写入为 0；
12. 独立 Gate-2 Data Reassessment 最终裁决 PASS。

准备设计完成、Migration 草案存在或测试环境结构可用，都不能单独使 Gate-2 转为 PASS。

## 12. 与 RRE 的数据准入关系

RRE-1 启动前至少需要：

```text
Business Action Contract.requiredResponsibility 有效
+ Responsibility ACTIVE 且可按时点读取
+ PositionResponsibility 有效且无未决冲突
+ EmployeePositionAssignment 有效且 As Of 查询可靠
= 可进入只读解析验证的必要数据条件
```

RRE 不负责：

- 创建或激活 Responsibility；
- 生成 PositionResponsibility；
- 把 `position_ref` 转成正式任职；
- 补齐岗位族、岗位等级或有效期；
- 修复无候选、多候选、空档或重叠；
- 用 Permission、Role、管理员、主管或最小 ID 推断责任人。

数据不完整时必须返回明确未解析或候选冲突状态，并由组织数据治理流程处理。

本轮 `RRE-1 = NOT AUTHORIZED`。

## 13. 后续顺序与停止点

本设计获确认后，后续仍需独立进行：

1. 最终 Schema 与数据规则签发；
2. Migration 和回退包独立评审授权；
3. 隔离环境结构实施及备份恢复演练；
4. 只读数据画像和候选批次生成；
5. Data Owner/Steward/Reviewer/Approver 人工确认；
6. 获授权后受控转换和初始化；
7. 数据质量、时态查询、审计和回退验收；
8. 另行发起 Gate-2 Data Reassessment。

上述步骤不在本轮执行。本报告不授权 Schema、Migration、数据导入、组织模型实施或 RRE。

## 14. 保护确认

```text
Documentation Changed = YES
Code Changed = NO
Database Changed = NO
Migration Created = NO
API Created = NO
Page Created = NO
Organization Data Changed = NO
Responsibility Data Changed = NO
Employee Data Changed = NO
EmployeePositionAssignment Instance Created = NO
PositionResponsibility Schema Changed = NO
Permission Model Changed = NO
Workflow Runtime Changed = NO
ApprovalTask Changed = NO
RRE Started = NO
Unauthorized Business Writes = 0
```

## 15. 最终状态

```text
Gate-2 Data Preparation Design = COMPLETE
Gate-2 Data = BLOCKED
Gate-3 Governance = BLOCKED
Gate-4 Technical = BLOCKED
Gate-5 Business = BLOCKED
Gate-2 Data Reassessment = NOT STARTED
OOM-4.2 Implementation Authorization Review = NOT STARTED
Organization Model Implementation = NOT AUTHORIZED
RRE-1 = NOT AUTHORIZED
Workflow Integration = NOT AUTHORIZED
```

本报告完整结束。停止等待下一步决策，不进入 Migration、数据导入、Schema 修改、Gate-2 重评、组织模型实施、RRE-1 或 Workflow Integration。
