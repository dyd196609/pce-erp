# PCE Organization Operating Model V2 Gate-4 Technical 解除准备设计报告

日期：2026-08-18  
阶段：OOM-4 Gate-4 Technical Preparation Design（OOM-4 Gate-4 技术门禁解除准备设计）  
类型：DESIGN ONLY（仅设计）  
当前门禁：Gate-4 Technical（技术门禁）= BLOCKED（阻断）  
实施授权：NOT AUTHORIZED（未授权实施）

## 1. 设计目标与最终结论

本报告只设计 Gate-4 Technical（技术门禁）从 BLOCKED 转为 PASS 所需的 Schema、Migration（数据库迁移）、服务、页面、初始化、测试、备份恢复、回退和隔离预演证据。

本报告不修改代码或数据库，不创建或执行 Migration，不创建 API 或页面，不执行测试环境迁移，不导入组织数据，也不启动 RRE（责任解析引擎）。

当前结论：

```text
Gate-4 Technical Preparation Design = COMPLETE
Gate-4 Technical = BLOCKED
Gate-4 PASS Evidence Package = NOT ESTABLISHED
Gate-4 Technical Reassessment = NOT STARTED
Implementation Authorized = NO
```

四个 OOM-4.1 实施包的设计已经完成，但设计文件不能替代已评审的可执行包、真实测试、恢复演练、隔离预演和责任人签发。

## 2. 已读取基线与判断依据

### 2.1 OOM-4 门禁基线

| 实际读取路径 | 文件用途 | 关键原文 | 判断依据 |
|---|---|---|---|
| `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-4实施准入与验收门禁设计报告.md` | 定义 Gate-4 PASS 标准 | “Migration 草案、备份恢复演练、测试清单、性能预算、部署/回退 Runbook” | 技术门禁必须由可执行且已演练证据支持 |
| `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-4 Gate重新评估报告.md` | 提供当前门禁状态 | “四个设计包补齐了技术实施准备的设计证据……当前仍处于 DESIGN ONLY” | Gate-4 必须保持 BLOCKED |

当前状态：

```text
Gate-1 Architecture = PASS
Gate-2 Data = BLOCKED
Gate-3 Governance = BLOCKED
Gate-4 Technical = BLOCKED
Gate-5 Business = BLOCKED
```

本报告只处理 Gate-4，不解除其他门禁。

### 2.2 OOM-4.1 实施包基线

| 实际读取路径 | 文件用途 | 关键原文 | 判断依据 |
|---|---|---|---|
| `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-4.1.1组织模型Schema实施包设计报告.md` | 定义目标 Schema、分阶段 Migration 和回退准备 | “Schema Package Design = COMPLETE；Schema Migration = NOT AUTHORIZED” | Schema 设计完成不表示结构已实施 |
| `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-4.1.2组织服务能力实施包设计报告.md` | 定义唯一写服务、Change Request 和审计链 | “当前写链……尚未具备 Change Request、独立审核、独立批准、未来生效执行、执行幂等” | 服务实施验证尚不存在 |
| `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-4.1.3组织管理页面实施包设计报告.md` | 定义唯一管理入口和页面写入边界 | “#/organization 继续作为唯一正式组织治理入口”；“页面不得直接调用正式事实保存动作” | 页面仍需实际实现和浏览器验证 |
| `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-4.1.4组织数据初始化与验收实施包设计报告.md` | 定义候选、批准批次、预演和回读 | “初始化不是 Schema Migration 的默认数据”；“必须先在隔离副本预演” | 初始化执行能力和预演证据尚未形成 |

### 2.3 技术治理基线

| 实际读取路径 | 文件用途 | 关键原文 | 判断依据 |
|---|---|---|---|
| `D:\Dev-PCE\Source\docs\governance\02-架构与运行边界\PCE-ERP架构与运行边界规范.md` | 定义 Page、Schema、Provider、Runtime、Domain、Persistence 边界 | “Domain 负责状态变化，Action 负责业务动作申请，Guard 负责阻断，Acceptance 负责证明” | 页面和 Runtime 不能成为组织事实写入口 |
| `D:\Dev-PCE\Source\docs\governance\03-业务流程运行治理\PCE-ERP业务流程运行治理规范.md` | 定义节点、动作、Guard、验收和回归 | “静态‘文件存在’不能代替真实 Handoff 和人工动作” | 技术验收必须执行正常、边界和失败路径 |
| `D:\Dev-PCE\Source\docs\governance\Runtime职责规范.md` | 指向唯一运行层规范 | “本文件不建立第二套 Runtime” | OOM 不得建立第二运行事实源 |
| `D:\Dev-PCE\Source\docs\governance\PCE-ERP运行层文件职责规范.md` | 定义 Runtime Adapter 只读边界 | “转换只读且 Business Write Count = 0” | Runtime Adapter 不得创建或修改组织事实 |
| `D:\Dev-PCE\Source\docs\standards\PCE-BUSINESS-ACTION-PERMISSION-V1.0.md` | 定义服务端动作权限链 | “system.AuthorizationService 是身份、动作权限与数据范围结论的唯一公共入口” | 所有组织写动作必须服务端复核并对越权返回 403 |

## 3. Gate-4 当前阻断原因

| 编号 | 当前缺口 | 技术风险 | 解除所需证据 |
|---|---|---|---|
| G4-B01 | Schema 未实施 | 目标结构不可验证 | Schema 评审和隔离实施报告 |
| G4-B02 | 无可执行 Migration 草案 | 顺序、依赖和锁表风险未知 | 经评审的 Migration 文件及依赖图 |
| G4-B03 | 无锁定/耗时实测 | 可能超出维护窗口 | 隔离副本性能与锁分析 |
| G4-B04 | 无备份恢复演练 | 无可靠恢复点 | 备份摘要和恢复演练报告 |
| G4-B05 | 无批准回退 Runbook | 失败处置不可执行 | 版本化操作手册和责任人签发 |
| G4-B06 | 服务未实施 | 唯一写入口和治理链无法验证 | 服务实现与集成测试报告 |
| G4-B07 | Change Request 持久方案未决 | 审批证据、幂等和执行状态无权威源 | 独立 Schema 决策与实现证据 |
| G4-B08 | 页面未实施 | 仍可能直接保存正式事实 | 浏览器和 API 越权验证报告 |
| G4-B09 | 初始化未预演 | 批次、回滚和回读风险未知 | 隔离初始化预演报告 |
| G4-B10 | 自动测试未执行 | 校验、权限、时态和回归未证明 | 完整测试报告与失败证据 |
| G4-B11 | 无可观测性证据 | 漂移和未授权写入无法及时发现 | 指标、日志、审计和告警报告 |
| G4-B12 | 无隔离环境端到端预演 | 生产风险未量化 | 环境清单、预演记录和签发 |

任一 P0 阻断项未关闭，Gate-4 必须保持 BLOCKED。

## 4. Schema 技术证据设计

### 4.1 Schema Review Package（数据结构评审包）

Gate-4 PASS 前必须形成：

| 证据 | 最低要求 |
|---|---|
| 模型关系图 | Company、OrganizationUnit、Position、Responsibility、PositionResponsibility、EmployeePositionAssignment 关系完整 |
| 字段字典 | 类型、空值、枚举、默认值、时区、来源和所有者明确 |
| 关系约束 | 外键、删除策略、跨公司、主岗、代理、PRIMARY/SUPPORTING 规则冻结 |
| 时态约束 | 统一 `[effective_from, effective_to)`，重叠和非法区间受服务/数据库双重阻断 |
| 唯一性 | 编码、关系期间、主岗和主责唯一规则明确 |
| 索引 | Current/As Of/History、责任到岗位、岗位到员工查询计划可验证 |
| 兼容策略 | `Employee.position_ref` 仅作当前主岗投影，停止旧权威条件明确 |
| 无平行模型 | 禁止 PositionResponsibilityV2、EmployeeAssignmentV2 和第二组织树 |
| 数据边界 | Migration 不自动创建或推断企业正式数据 |

### 4.2 Schema 评审证据

证据必须包含评审版本、提交哈希、目标数据库类型，以及 ORM 模型、DDL、约束和索引的一致性检查；还必须包含静态冲突扫描、命名检查、真实查询计划、索引选择、写入代价和容量预算。

数据架构、应用、DBA、安全和测试负责人必须完成签发，未决 P0/P1 问题必须为 0。

设计文档通过不能替代上述实施与验证证据。

## 5. Migration（数据库迁移）技术门禁

### 5.1 Migration 包必须包含

| 项目 | 技术要求 |
|---|---|
| Migration 文件 | 单一目的、可审查、无隐藏业务数据种子 |
| 依赖图 | 明确应用版本、前置 Migration、表和约束依赖 |
| 执行顺序 | M0 预检、M1 新表、M2 扩字段、M3 候选对账、M4 收紧约束、M5 权威切换分离 |
| 预检 | 数据库版本、磁盘、连接、锁、表计数、异常、备份摘要 |
| 失败处理 | 每阶段停止条件、事务边界、失败证据封存 |
| 验证脚本 | Schema、约束、索引、数量、引用、时态和审计检查 |
| 性能预算 | 执行时间、锁等待、磁盘增长、回读延迟和允许阈值 |
| 回退点 | 每阶段恢复点和不可逆变更说明 |
| 人工批准 | 执行人、观察人、回退批准人、维护窗口 |

### 5.2 强制禁止

禁止在 Schema Migration 中自动生成 EmployeePositionAssignment、Responsibility 或 PositionResponsibility；禁止根据岗位名、Role、Permission 或主管推断事实。

禁止未审人工 SQL、生产数据未授权试验、删除失败日志/历史/审计证据，以及未取得新授权即执行 Migration。

本报告 `Migration Created = NO`。

## 6. OrganizationOperatingService 技术门禁

### 6.1 目标执行链

```text
Approved Change Request
→ Effective-Date Guard
→ AuthorizationService Revalidation
→ Version/Before-Snapshot Guard
→ OrganizationOperatingService
→ Transactional Fact Write
→ Audit
→ Server Readback
```

### 6.2 必须验证的能力

| 能力 | PASS 证据 |
|---|---|
| 唯一事实写入口 | ORM/API/页面/Workflow/RRE 绕过扫描为 0 |
| Change Request | 只接受已批准、未漂移、已到期且范围匹配的请求 |
| AuthorizationService | 每次执行重新判断 User、Action、Permission 和 Scope |
| Domain Guard | 组织循环、跨公司、状态、引用和时态规则服务端阻断 |
| 审计 | Before、After、Operator、Reviewer、Approver、Reason、Effective Time 完整 |
| 幂等 | 同一申请重复执行不产生第二次业务写入 |
| 并发 | 版本锁/行锁阻断 Lost Update（丢失更新） |
| 错误恢复 | 任一写入或审计失败，事务整体回滚 |
| 回读 | API、页面、诊断和验收读取同一服务端事实 |
| 拒绝证据 | HTTP 403/409/422 等稳定代码且写入计数为 0 |

### 6.3 Change Request 前置决策

现有服务包明确指出正式 Change Request Schema 尚未批准。实施前必须独立决定：

1. 建立最小 Change Request、Review/Approval Evidence 和 Application Record；或
2. 批准一个现有对象作为等价的不可变、版本化、可审计且可幂等治理事实源。

禁止用 ApprovalTask、日志文本、页面缓存或审计 Before Snapshot 冒充 Change Request。

## 7. 页面技术门禁

### 7.1 唯一入口与事实来源

- `#/organization` 是唯一正式组织治理入口；
- `#/organization-model` 保持综合只读查看和诊断；
- API、页面、复制诊断、`strictFacts` 和验收复用同一服务端事实；
- 页面只能提交 User Intent（用户意图）和 Change Request；
- 页面不得直接写 Company、Position、Responsibility、PositionResponsibility 或 Employee Assignment；
- 页面不得自行计算权限、审批人、责任或状态。

### 7.2 页面 PASS 验证

| 场景 | 预期结果 |
|---|---|
| 新建/修改组织对象 | 只生成 Change Request，不改变正式事实 |
| 审核和批准 | 展示服务端指派、状态和证据，不由前端决定人选 |
| 未授权按钮直调 API | 服务端 403，业务写入 0 |
| 版本冲突 | 显示明确冲突，不覆盖人工数据 |
| 刷新/重入 | 恢复同一申请和服务端正式事实 |
| 审计查看 | 能追踪申请、审核、批准、执行和 Before/After |
| 综合模型 | 只读，无法通过路由或组件绕过写入链 |

静态页面文件存在、按钮可见或截图正常不能单独证明 PASS；必须执行浏览器和 API 复核。

## 8. 数据初始化技术门禁

### 8.1 隔离数据区

```text
Source Snapshot（只读源快照）
→ Candidate Workspace（候选工作区）
→ Human Review/Approval（人工审核批准）
→ Approved Initialization Batch（已批准批次）
→ Controlled Executor（受控执行器）
→ Server Readback + Audit（服务端回读与审计）
```

### 8.2 必须验证

- 只读盘点前后数据库摘要和对象数量不变；
- 候选生成可重复且不会写正式事实；
- 候选保留来源、原值、建议值、人工值和差异原因；
- 修改已审核候选产生新版本并使旧批准失效；
- 未批准候选不能进入正式批次；
- 批次行哈希、批次版本和批准证据不可变；
- 重复执行保持幂等；
- 任一行失败整体回滚；
- 执行后从服务端重新读取，而非信任内存结果；
- 初始化不创建 Business Action、Role、Permission、Workflow 或采购对象。

生产初始化必须等待独立数据导入授权；隔离预演成功不能自动授权生产执行。

## 9. 测试与验收技术门禁

### 9.1 测试层次

| 测试层 | 必测内容 |
|---|---|
| Unit（单元） | 字段、状态、时态、重叠、主岗、主责、Scope、幂等和异常规则 |
| Service（服务） | Action、Guard、Authorization、事务、审计、回读和错误恢复 |
| Integration（集成） | Change Request→批准→生效→审计完整链；Workflow 仅承载过程 |
| Migration | 正向、失败、重试、回退、旧读兼容、权威切换和数据摘要 |
| UI/Browser | 唯一入口、申请、审核状态、审计、刷新、直调 API 拒绝 |
| Security（安全） | 越权、Scope、共享账号、绕过写服务、参数篡改和 superuser 边界 |
| Concurrency（并发） | 重复提交、双批准、并发生效、版本漂移和锁超时 |
| Regression（回归） | 原组织、权限、Workflow、ApprovalTask、采购及公共运行层不变 |
| Recovery（恢复） | 备份恢复、应用回退、Schema 回退和失败证据保留 |

### 9.2 最低失败用例

- 未批准申请执行必须拒绝；
- 批准后 Payload 改变必须使批准失效；
- 无 Permission 或 Scope 必须返回 HTTP 403；
- 非唯一写入口调用必须拒绝；
- 时态重叠、跨公司、孤儿引用必须拒绝；
- 同一批次重复执行不得重复写入；
- 审计失败必须回滚事实写入；
- 页面/RRE/Workflow 尝试写事实必须拒绝；
- 回退失败必须触发强制停止而非继续实施；
- 所有拒绝场景 `Unauthorized Business Writes = 0`。

### 9.3 测试报告质量

测试报告必须记录代码版本、Migration 版本、数据库摘要、环境、时间、执行者、用例总数、PASS/FAIL、日志/审计链接、缺陷和复测结果。P0/P1 失败项必须为 0。

## 10. 备份与回退技术门禁

### 10.1 备份证据

- 数据库备份绝对路径、生成时间、大小和 SHA256；
- 应用构建版本、依赖锁文件和配置摘要；
- Migration 状态、表数量、业务对象数量和关键关系数量；
- 备份加密、访问控制、保留期限和恢复责任人；
- 恢复副本的完整性验证记录。

### 10.2 回退 Runbook（回退操作手册）

Runbook 至少包含：

1. 启动和强制停止条件；
2. 决策人、执行人、观察人、业务通知人；
3. 应用回退、Schema 回退和数据恢复顺序；
4. 可逆/不可逆步骤及对应恢复点；
5. 最大 RTO、RPO 和维护窗口；
6. 失败日志、审计和证据封存方法；
7. 恢复后数量、摘要、权限、时态和服务回读检查；
8. BAC、Permission、Workflow、ApprovalTask、采购业务和 RRE 保护检查；
9. 异常升级路径；
10. 回退完成签发页。

### 10.3 保护边界

回退不得修改 BAC、Permission、Workflow Runtime、ApprovalTask、采购数据或 RRE；不得物理删除已经确认的时态历史或失败证据；不得以人工 SQL 静默制造“恢复成功”。

## 11. 隔离环境预演与可观测性

### 11.1 环境要求

- 使用授权的隔离数据库副本，不连接生产写端点；
- 配置、密钥、外部网络和业务副作用保持关闭；
- 固化应用、数据库、Migration、测试和数据批次版本；
- 预演前后保存 SHA256、对象计数和环境清单；
- 预演覆盖正常、边界、失败和回退四类路径；
- 生产采购订单、供应商价格和流程任务写入为 0。

### 11.2 可观测性证据

必须观察并归档：Migration 阶段和耗时、锁等待、事务回滚、服务动作、Authorization 决策、Change Request 状态、审计写入、幂等命中、数据漂移、未授权写入、页面回读和回退进度。

数据存在但读取失败必须报告 `read_failed`，不得伪装为零条结果；页面缓存或 Runtime Snapshot 不得补齐事实。

## 12. Gate-4 Technical Evidence Package（技术证据包）

| 编号 | 必需证据 | 最低内容 | 签发主体 |
|---|---|---|---|
| G4-E01 | Schema 评审记录 | 模型、字段、约束、索引、查询计划 | 数据架构 + DBA |
| G4-E02 | Migration 草案 | 文件、依赖、顺序、停止点、验证 | 技术负责人 + DBA |
| G4-E03 | Change Request 技术决策 | 权威模型、版本、审计、幂等 | 架构负责人 |
| G4-E04 | 性能与锁分析 | 耗时、锁、容量、阈值和结论 | DBA + 性能负责人 |
| G4-E05 | 备份恢复报告 | SHA256、恢复副本、RTO/RPO | DBA/数据保管人 |
| G4-E06 | 回退 Runbook | 步骤、责任人、窗口、签发 | 技术与业务负责人 |
| G4-E07 | 服务验证报告 | 唯一写入、Guard、Authorization、审计、幂等、并发 | 服务负责人 |
| G4-E08 | 页面验证报告 | 唯一入口、申请流、审计、刷新、API 拒绝 | 前端/测试负责人 |
| G4-E09 | 初始化预演报告 | 候选、批次、回滚、回读和零自动生成 | 数据/测试负责人 |
| G4-E10 | 自动测试报告 | 单元、服务、集成、Migration、安全、并发、回归 | 测试负责人 |
| G4-E11 | 安全验证报告 | 越权、绕过、Scope、参数篡改和零写入 | 安全负责人 |
| G4-E12 | 可观测性报告 | 指标、日志、审计、告警和漂移 | 运维负责人 |
| G4-E13 | 隔离端到端预演 | 部署、迁移、初始化、测试、回退完整执行 | 发布负责人 |
| G4-E14 | 保护模块回归 | BAC、权限、Workflow、ApprovalTask、采购、RRE 未变 | 模块 Owner |
| G4-E15 | Gate-4 签发页 | 结论、例外、未决项、签名日期 | Gate-4 签发组 |

每份证据必须包含文件名、版本、代码提交、Migration 标识、环境、执行时间、Owner、签发日期和 SHA256。

## 13. Gate-4 PASS 判定规则

Gate-4 转为 PASS 必须全部满足：

1. G4-E01～G4-E15 全部形成并获授权主体签发；
2. Schema、服务、页面和初始化目标能力均已在隔离环境实施和验证；
3. Migration 可执行、可观察、满足性能预算且拥有明确停止点；
4. Change Request 正式技术来源已经决策、实施并验证；
5. OrganizationOperatingService 是唯一事实写入口，绕过扫描为 0；
6. AuthorizationService、审计、幂等、并发和错误恢复测试全部通过；
7. 页面只提交 Change Request，刷新读取同一服务端事实；
8. 初始化只消费已批准批次，不自动推断或创建企业事实；
9. 单元、集成、Migration、安全、并发和回归测试无 P0/P1 失败；
10. 备份可验证恢复，回退 Runbook 在隔离副本完整演练通过；
11. BAC、Permission、Workflow、ApprovalTask、采购业务和 RRE 保护检查通过；
12. Unauthorized Business Writes（未授权业务写入）= 0；
13. 独立 Gate-4 Technical Reassessment 最终裁决 PASS。

设计完成、代码合并、测试用例存在或单次成功迁移都不能单独使 Gate-4 转为 PASS。

## 14. 后续顺序与停止点

本设计获确认后，后续仍需独立授权并依次形成：

1. Schema 与 Change Request 技术决策签发；
2. 可审查 Migration、验证脚本和回退 Runbook；
3. 隔离环境备份恢复基线；
4. Schema、服务、API 和页面受控实施；
5. 初始化候选和批准批次预演；
6. 全层测试、安全验证、性能分析和保护回归；
7. 完整回退演练；
8. 技术证据包签发；
9. 另行发起 Gate-4 Technical Reassessment。

以上步骤不在本轮执行。本报告不授权 Migration、代码、API、页面、数据导入、组织模型实施或 RRE。
## 15. 保护确认

```text
Documentation Changed = YES
Code Changed = NO
Database Changed = NO
Migration Created = NO
API Created = NO
Page Created = NO
Test Environment Migration Executed = NO
Organization Data Changed = NO
Responsibility Data Changed = NO
Employee Data Changed = NO
Permission Model Changed = NO
AuthorizationService Changed = NO
Workflow Runtime Changed = NO
ApprovalTask Changed = NO
RRE Started = NO
Unauthorized Business Writes = 0
```

## 16. 最终状态

```text
Gate-4 Technical Preparation Design = COMPLETE
Gate-2 Data = BLOCKED
Gate-3 Governance = BLOCKED
Gate-4 Technical = BLOCKED
Gate-5 Business = BLOCKED
Gate-4 Technical Reassessment = NOT STARTED
OOM-4.2 Implementation Authorization Review = NOT STARTED
Organization Model Implementation = NOT AUTHORIZED
RRE-1 = NOT AUTHORIZED
Workflow Integration = NOT AUTHORIZED
```

本报告完整结束。停止等待下一步决策，不进入 Migration、代码/API/页面开发、数据导入、Gate-4 重评、组织模型实施、RRE-1 或 Workflow Integration。
