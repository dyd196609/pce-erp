# PCE Controlled Evidence Build Authorization Request Instance（受控证据构建授权申请实例）验证规则设计报告

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 系统 | PCE（ProfitOS / Dev-PCE） |
| 阶段 | Controlled Evidence Build Authorization Preparation（受控证据构建授权准备阶段） |
| 类型 | Design Only（仅设计） |
| 日期 | 2026-08-19 |
| Review Level（审查等级） | B（重点审查） |
| Full Content Review Required（是否强制全文审查） | NO |
| 验证对象 | 未来已创建但尚未提交评审的 Request Instance 版本快照 |
| 当前申请实例 | NOT CREATED |
| 当前授权 | NOT GRANTED |
| 当前执行 | NOT STARTED |
## 2. 目标与边界

本报告定义未来 Authorization Request Instance（授权申请实例）创建后的验证规则，用于判断其是否完整、合法、可追踪，并具备进入授权评审流程的条件。

验证只输出 `READY_FOR_REVIEW`、`BLOCKED` 或 `REJECTED`。它不提交申请、不执行专业审核、不批准授权、不创建 Manifest，也不启动 Controlled Evidence Build（受控证据构建）。

本报告不创建 Request ID、Request Instance、Validation Record、Review Record、Decision Record 或 Authorization Manifest。
## 3. Preflight（执行前检查）

```text
Context Scope = CONTROLLED
Input Files = 5
Task Scope = SINGLE
Review Level = B
Full Content Review Required = NO
Request Instance Creation = NO
Validation Execution = NO
Authorization = NOT GRANTED
```

输入文件未超过 6 个；没有读取无关历史文件；报告目标为 200–400 行。
## 4. 已读取基线与判断依据
### 4.1 CODEX 核心规范

路径：`D:\Dev-PCE\Source\docs\governance\PCE CODEX开发指令规范管理V1.2.md`

用途：确认风险分级、上下文控制、单任务、归档回读和阶段分离。

关键原文：

> 核心治理规范升级至少为 Level B，不得因“只修改文档”降为 Level A。

判断：本任务影响授权准备边界，采用 Level B，但不要求在回复中传输全文。
### 4.2 受控证据构建授权设计

实际路径：`D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 Controlled Evidence Build Authorization设计报告.md`

说明：指令中的简称文件实际以 `PCE Organization Operating Model V2` 为前缀，使用仓库正式归档文件。

关键原文：

> 任何未列入清单的活动默认禁止。 授权过期后不得继续构建或写入。

判断：边界验证必须采用白名单和默认禁止，不能将缺失范围推定为允许。
### 4.3 授权评审与申请设计

实际路径：`D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 Controlled Evidence Build Authorization评审与授权申请设计报告.md`

关键原文：

> APPROVED 只表示申请通过评审，可生成批准版授权清单。 APPROVED 不表示证据构建已经 ACTIVE（执行中）。

判断：即使验证结果为 READY_FOR_REVIEW，也不等于 Request APPROVED 或 Authorization ACTIVE。
### 4.4 Request Template（授权申请模板）

路径：`D:\Dev-PCE\Source\docs\governance\PCE Controlled Evidence Build Authorization Request Template设计报告.md`

关键原文：

> | TV-04 | 六维范围全部填写 | BLOCKED |

判断：完整性验证必须把六维范围作为硬门禁。
### 4.5 Request Instance 创建准备设计

路径：`D:\Dev-PCE\Source\docs\governance\PCE Controlled Evidence Build Authorization Request Instance创建准备设计报告.md`

关键原文：

> 任何校验结果均不自动创建 Request Instance。

判断：本报告只设计创建后的验证，不创建或改变任何实例状态。
## 5. Validation Framework（验证框架）
### 5.1 分层模型

```text
Creation Validation（创建验证）
↓
Completeness Validation（完整性验证）
↓
Boundary Validation（边界验证）
↓
Risk Validation（风险验证）
↓
Security Validation（安全验证）
↓
Data Validation（数据验证）
↓
Responsibility Separation Validation（职责分离验证）
↓
Review Readiness Validation（评审就绪验证）
```

前一层存在阻断或拒绝结论时，后一层可以继续进行只读问题收集，但不得把总结果改为 READY_FOR_REVIEW。
### 5.2 概念输入

验证器未来只读取指定 Request Instance 的不可变版本快照、活动模板版本、附件索引、身份引用、环境与数据声明、风险登记以及归档摘要。

禁止读取前端缓存代替归档快照；禁止验证期间修正申请正文；禁止从 Role、管理员身份或历史申请推断缺失字段。
### 5.3 概念输出

| 字段 | 说明 |
|---|---|
| request_id / version | 被验证申请及精确版本 |
| rule_set_version | 使用的验证规则版本 |
| input_sha256 | 输入快照摘要 |
| validation_status | READY_FOR_REVIEW / BLOCKED / REJECTED |
| findings | 规则编号、字段路径、严重度、依据、补正建议 |
| validated_at / by | 服务端时间和验证主体 |
| output_sha256 | 验证结果摘要 |

本轮只设计该结构，不创建 Validation Record（验证记录）。
### 5.4 规则结果与严重度

| 结果 | 含义 | 总状态影响 |
|---|---|---|
| PASS | 规则满足 | 不阻断 |
| WARNING | 不影响合法性的改进项 | 可进入评审但必须展示 |
| BLOCKED | 可补正字段、证据或依赖缺失 | 总状态 BLOCKED |
| REJECTED | 目标或范围违反永久边界 | 总状态 REJECTED |

任何 REJECTED 优先于 BLOCKED；任何 BLOCKED 优先于 READY_FOR_REVIEW。
## 6. Creation Validation（创建验证）

| 规则 | 检查 | 失败结果 |
|---|---|---|
| ARV-CR-01 | request_id 由权威编号器产生且唯一 | REJECTED |
| ARV-CR-02 | request_version 为有效正整数 | BLOCKED |
| ARV-CR-03 | template_version 存在且创建时有效 | BLOCKED |
| ARV-CR-04 | created_by、created_at 来自服务端审计 | BLOCKED |
| ARV-CR-05 | 版本正文与 input_sha256 一致 | REJECTED |
| ARV-CR-06 | 状态为 DRAFT，且未形成 Manifest | REJECTED |
| ARV-CR-07 | request_id、版本、模板引用可追踪 | BLOCKED |

创建验证只验证实例来源是否合法，不重新执行编号或创建动作。
## 7. Completeness Validation（完整性验证）
### 7.1 基础与目标字段

必须存在 title、request_owner、request_date、objective、business_reason、target_gates、evidence_questions、expected_outputs、success_criteria 和 failure_result。

目标必须描述证据问题并允许失败；使用“保证上线”“必须通过”或把 Gate PASS 当预定结论时，结果为 REJECTED。
### 7.2 六维范围

| 规则 | 检查 | 失败结果 |
|---|---|---|
| ARV-CP-01 | Time 完整且开始早于结束 | BLOCKED |
| ARV-CP-02 | Environment、database 和 endpoint 唯一明确 | BLOCKED |
| ARV-CP-03 | Files 包含 repository、commit 和路径白名单 | BLOCKED |
| ARV-CP-04 | Data 包含来源、分类、对象、数量和命名空间 | BLOCKED |
| ARV-CP-05 | People 全部实名并可联系 | BLOCKED |
| ARV-CP-06 | Activities 逐项声明动作、对象、写入预算和证据 | BLOCKED |
### 7.3 控制与附件

Risk Register、Rollback Plan、Cleanup Plan、Stop Conditions、Environment Isolation、Data Provenance 和 Evidence Output 缺失时均为 BLOCKED。

附件无法访问、没有版本或没有 SHA256 时为 BLOCKED。未解释的占位符、半句以及“相关目录”“必要操作”等开放描述均为 BLOCKED。
## 8. Boundary Validation（边界验证）

| 规则 | 检查 | 失败结果 |
|---|---|---|
| ARV-BD-01 | environment_type 必须为 NON_PRODUCTION_EVIDENCE | REJECTED |
| ARV-BD-02 | production_reachability 必须为 DENIED | REJECTED |
| ARV-BD-03 | 禁止生产部署、生产数据库写入和正式 Migration | REJECTED |
| ARV-BD-04 | 禁止正式组织、责任、员工、权限或业务事实写入 | REJECTED |
| ARV-BD-05 | 禁止 Workflow 启用、ApprovalTask 创建或 RRE 启动 | REJECTED |
| ARV-BD-06 | allowed_paths 与 prohibited_paths 不冲突 | BLOCKED |
| ARV-BD-07 | 未列活动默认禁止 | BLOCKED |
| ARV-BD-08 | target_gates 仅限 Gate-2、Gate-4 或明确子项 | REJECTED |

验证不能通过缩小文字解释来放行实际越界范围；边界含糊时按 BLOCKED 处理。
## 9. Risk Validation（风险验证）
### 9.1 风险登记完整性

每项风险必须包含 risk_id、描述、影响、概率、控制、责任人、状态和停止触发。没有责任人或停止触发时为 BLOCKED。
### 9.2 风险门禁

| 条件 | 结果 |
|---|---|
| P0/P1 风险仍为 OPEN | BLOCKED |
| 风险控制依赖生产访问 | REJECTED |
| 回退不可执行或无法验证 | REJECTED |
| 日志、审计或停止机制不可用 | BLOCKED |
| 风险清单与范围明显不一致 | BLOCKED |

验证结果不得隐藏风险；WARNING、BLOCKED 和 REJECTED findings 都必须进入未来评审材料。
## 10. Security Validation（安全验证）

| 规则 | 检查 | 失败结果 |
|---|---|---|
| ARV-SE-01 | 不存在生产密钥、证书、令牌或配置引用 | REJECTED |
| ARV-SE-02 | 不存在生产写权限或生产写端点 | REJECTED |
| ARV-SE-03 | endpoint 使用显式白名单且网络默认拒绝 | BLOCKED |
| ARV-SE-04 | 凭据非生产、短期、最小权限且可撤销 | BLOCKED |
| ARV-SE-05 | 权限范围与允许活动一致 | BLOCKED |
| ARV-SE-06 | 日志、审计、监控和紧急停止可用 | BLOCKED |
| ARV-SE-07 | 环境可销毁、冻结或恢复 | BLOCKED |

超级管理员或生产权限不能作为隔离能力的替代方案。
## 11. Data Validation（数据验证）

| 规则 | 检查 | 失败结果 |
|---|---|---|
| ARV-DA-01 | 数据来源为合成、脱敏或获批只读副本 | REJECTED/BLOCKED |
| ARV-DA-02 | Data Custodian（数据保管人）实名 | BLOCKED |
| ARV-DA-03 | 分类、敏感字段和脱敏规则明确 | BLOCKED |
| ARV-DA-04 | 对象白名单、记录上限和测试命名空间明确 | BLOCKED |
| ARV-DA-05 | 保留期、清理方式和销毁证据明确 | BLOCKED |
| ARV-DA-06 | 禁止回写来源系统或提升为正式数据 | REJECTED |
| ARV-DA-07 | 数据授权引用与来源摘要可追踪 | BLOCKED |

测试数据、验证结果和候选转换均不能自动升级为正式企业或业务数据。
## 12. Responsibility Separation Validation（职责分离验证）
### 12.1 关键角色

Request Owner、Authorization Owner/Approver、Executor、Evidence Reviewer 必须由可识别自然人承担，关键链路不得由同一自然人兼任。
### 12.2 冲突规则

| 规则 | 冲突 | 结果 |
|---|---|---|
| ARV-SD-01 | Request Owner = Approver | BLOCKED |
| ARV-SD-02 | Approver = Executor | BLOCKED |
| ARV-SD-03 | Executor = Evidence Reviewer | BLOCKED |
| ARV-SD-04 | Request Owner = Evidence Reviewer | BLOCKED |
| ARV-SD-05 | 环境搭建人 = 唯一 Security Reviewer | BLOCKED |
| ARV-SD-06 | 数据准备人 = 唯一 Data Custodian | BLOCKED |
| ARV-SD-07 | 共享账号或超级管理员代替自然人 | REJECTED |
| ARV-SD-08 | 临时替换人没有预先实名、范围和期限 | BLOCKED |

职责分离只验证角色冲突，不判断业务上谁应该批准，也不执行责任解析。
## 13. Review Readiness Validation（评审就绪验证）
### 13.1 READY_FOR_REVIEW 条件

只有同时满足以下条件才可输出 READY_FOR_REVIEW：

- 所有 Creation、Completeness、Boundary、Risk、Security、Data 和职责分离硬规则通过；
- 没有 BLOCKED 或 REJECTED finding；所有必需附件可访问且摘要一致；
- 当前 request_version 与验证输入版本一致；专业审核角色已实名但尚未填写审核结论；
- 申请仍为 DRAFT，且未创建 Manifest、审批记录或执行状态。
### 13.2 BLOCKED 条件

字段、附件、人员、隔离证明、数据批准或风险控制可补正但尚不完整时输出 BLOCKED。补正必须形成新快照；实质变化必须递增版本并重新验证。
### 13.3 REJECTED 条件

目标包含生产访问、正式数据写入、正式 Migration、Workflow/RRE 启动、未知数据来源或无法回退等永久禁止事项时输出 REJECTED。
### 13.4 状态边界

`READY_FOR_REVIEW` 只是一项只读资格结论，不自动把 Request 状态改为 SUBMITTED 或 REVIEWING。状态迁移必须由未来独立提交动作完成。
## 14. Request Validation 与 Authorization 边界

| 能力 | 回答问题 | 是否允许执行 |
|---|---|---|
| Request Validation | 申请是否完整、合法、可进入评审 | 否 |
| Professional Review | 各专业审核是否接受申请 | 否 |
| Authorization Decision | 是否批准形成具体授权清单 | 否，仍需签发 Manifest |
| Authorization Manifest | 具体批准哪些执行范围 | 仅后续 READY_CHECK 通过后 |

禁止把 READY_FOR_REVIEW、Review PASS 或 Request APPROVED 解释为 Controlled Evidence Build 已获授权。
## 15. 重验与版本规则

以下变化必须使既有验证结果失效并重新验证：Environment、Data、repository、commit、路径、People、Activities、时间窗口、目标 Gate、风险、回退、清理或停止条件。

每次重验必须固定 request_id、request_version、rule_set_version 和 input_sha256。输入摘要变化但版本未变化时直接 REJECTED，并记录不可变快照违规。

验证规则版本升级时，未提交申请按新规则重验；已进入评审的申请由治理负责人决定继续旧规则还是退回重验，并记录依据，禁止静默切换。
## 16. Gate 映射

| Gate | 可支持 | 不能替代 |
|---|---|---|
| Gate-2 Data | Schema、时态、数据质量和候选 Migration 证据准备 | 正式 Schema/Migration 授权、数据签发 |
| Gate-4 Technical | 服务、API、页面、测试、恢复和回退准备 | 生产发布和上线证据 |
| Gate-3 Governance | 技术性职责分离检查 | 实名治理、任命和职责签发 |
| Gate-5 Business | 非生产验证材料准备 | 业务确认、人工验收和上线窗口 |

验证完成、申请就绪或后续评审通过均不自动改变任何 Gate 状态。
## 17. Validation Audit（验证审计）与归档

未来每次验证必须保留：规则集版本、输入版本及 SHA256、执行主体、服务端时间、逐条结果、全部 findings、总状态和输出 SHA256。

验证记录只追加，不覆盖历史；BLOCKED 和 REJECTED 记录不得删除；补正后的新验证必须引用上一记录。

归档索引必须把 Request 版本、验证记录、附件摘要和后续审核记录分开关联，防止验证器改写 Request 事实。

本轮不创建验证记录或归档实例。
## 18. 设计验证场景

| 编号 | 场景 | 预期结果 |
|---|---|---|
| ARV-T01 | 所有字段与六维范围完整 | READY_FOR_REVIEW |
| ARV-T02 | 缺少 Data Custodian | BLOCKED |
| ARV-T03 | 包含生产写端点 | REJECTED |
| ARV-T04 | P1 风险未关闭 | BLOCKED |
| ARV-T05 | Executor 同时为 Evidence Reviewer | BLOCKED |
| ARV-T06 | 使用共享超级管理员 | REJECTED |
| ARV-T07 | 数据来源不明 | BLOCKED 或 REJECTED，不得就绪 |
| ARV-T08 | input_sha256 与版本正文不一致 | REJECTED |
| ARV-T09 | READY 后修改 commit | 验证失效并重验 |
| ARV-T10 | READY 自动进入 REVIEWING | 拒绝自动迁移 |
| ARV-T11 | 技术验证替代 Gate-3 | 拒绝 |
| ARV-T12 | 测试数据提升为正式数据 | REJECTED |

以上均为未来测试设计，本轮不执行。
## 19. 风险与控制

| 风险 | 影响 | 控制 |
|---|---|---|
| READY 被误作授权 | 越权执行 | 状态、评审和 Manifest 三层分离 |
| 验证器自动修复申请 | 原始事实被改写 | 验证只读，只输出 findings |
| 缺失范围被默认允许 | 白名单失效 | 未列入即禁止 |
| 生产凭据隐藏在附件 | 生产风险 | 安全验证覆盖附件与引用 |
| 审核人跨版本复用结论 | 错误评审 | 摘要绑定和重验规则 |
| 共享管理员绕过分离 | 治理失效 | 自然人身份和冲突规则 |
| BLOCKED 记录被删除 | 无法追溯 | 追加式归档和摘要链 |
## 20. 本轮保护状态

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
Permission Model Changed = NO
Workflow Runtime Changed = NO
ApprovalTask Changed = NO
RRE Started = NO
Unauthorized Business Writes = 0
```

本轮未创建 Request Instance、Request ID、Manifest、验证记录、审核记录或任何授权。
## 21. 最终状态

```text
Controlled Evidence Build Authorization Request Instance Validation Rules Design = COMPLETE
Authorization Request ID = NOT CREATED
Authorization Request Instance = NOT CREATED
Validation Record Instance = NOT CREATED
Authorization Manifest Instance = NOT CREATED
Controlled Evidence Build Authorization = NOT GRANTED
Controlled Evidence Build Execution = NOT STARTED
OOM-4.2 Implementation Authorization Review = NOT STARTED
Organization Model Implementation = NOT AUTHORIZED
RRE-1 = NOT AUTHORIZED
Workflow Integration = NOT AUTHORIZED
Context Scope = CONTROLLED
Input Files = 5
Task Scope = SINGLE
Review Level = B
Full Content Review Required = NO
Documentation Archived = YES
Archive Content Readback = YES
ChatGPT Reviewable = YES
Source Excerpts Verified = YES
```

本报告完成后立即停止，等待人工审查；不得提交申请、创建审核记录、生成 Manifest、批准授权或启动受控证据构建。
