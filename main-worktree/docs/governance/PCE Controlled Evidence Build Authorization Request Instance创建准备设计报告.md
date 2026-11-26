# PCE Controlled Evidence Build Authorization Request Instance（受控证据构建授权申请实例）创建准备设计报告

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 系统 | PCE（ProfitOS / Dev-PCE） |
| 阶段 | Controlled Evidence Build Authorization Preparation（受控证据构建授权准备阶段） |
| 类型 | Design Only（仅设计） |
| 日期 | 2026-08-19 |
| Review Level（审查等级） | B（重点审查） |
| Full Content Review Required（是否强制全文审查） | NO |
| 当前申请实例 | NOT CREATED |
| 当前授权清单实例 | NOT CREATED |
| 当前授权 | NOT GRANTED |
| 当前执行 | NOT STARTED |
## 2. 设计目标与非目标

本报告设计未来创建一次 Authorization Request Instance（授权申请实例）之前必须具备的字段、流程、校验、版本管理、审核关联和归档机制。

本报告只形成 Preparation Design（准备设计），不分配真实 Request ID（申请编号），不创建 DRAFT 实例，不提交审核，不作批准裁决，也不生成 Authorization Manifest（授权清单）。

本报告不授权代码、数据库、Migration、API、页面、组织数据、责任数据、员工数据、Permission、Workflow Runtime 或 RRE 活动。
## 3. Preflight（执行前检查）

```text
Context Scope = CONTROLLED
Input Files = 4
Task Scope = SINGLE
Review Level = B
Full Content Review Required = NO
Authorization Request Instance Creation = NO
Authorization Manifest Instance Creation = NO
Implementation Authorization = NO
```

输入文件未超过 5 个，没有读取无关历史文件；目标报告控制在 200–400 行。
## 4. 已读取治理基线与判断依据
### 4.1 Level 0：CODEX 核心规范

路径：`D:\Dev-PCE\Source\docs\governance\PCE CODEX开发指令规范管理V1.2.md`

用途：确认上下文控制、单任务、风险分级、完整归档回读和阶段授权分离。

关键原文：

> 核心治理规范升级至少为 Level B，不得因“只修改文档”降为 Level A。

判断：本任务涉及授权治理边界，采用 Level B；完整文件必须回读，但回复无需重复全文。
### 4.2 Level 1：受控证据构建授权设计

路径：`D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 Controlled Evidence Build Authorization设计报告.md`

用途：确认受控证据构建定义、隔离边界、授权清单和状态模型。

关键原文：

> 任何未列入清单的活动默认禁止。 授权过期后不得继续构建或写入。

判断：Request 只能提出需求；具体可执行白名单必须由未来批准版 Manifest 固化。
### 4.3 Level 1：授权评审设计

路径：`D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 Controlled Evidence Build Authorization评审与授权申请设计报告.md`

用途：确认申请、评审、批准、拒绝、阻断、暂停、撤销和关闭边界。

关键原文：

> APPROVED 只表示申请通过评审，可生成批准版授权清单。 APPROVED 不表示证据构建已经 ACTIVE（执行中）。

判断：申请状态、授权状态和执行状态必须使用独立状态机。
### 4.4 Level 1：授权申请模板

路径：`D:\Dev-PCE\Source\docs\governance\PCE Controlled Evidence Build Authorization Request Template设计报告.md`

用途：确认申请字段、六维范围、审核清单、风险、回退、清理和停止条件。

关键原文：

> 所有待填写值统一使用 `{{FIELD_NAME}}`，不得预填真实人员、环境、密钥、端点、数据或批准结论。

判断：本准备报告继续使用占位符描述未来字段，不得生成真实申请内容。
## 5. 核心设计原则
### 5.1 未创建原则

本报告状态始终为 `Request Instance = NOT CREATED`。概念模型、字段样例或编号格式均不得被解释为真实实例。
### 5.2 请求与授权分离

Request 回答“为什么需要构建证据、希望证明什么”；Manifest 回答“批准哪些具体范围可以执行”。Request APPROVED 不自动创建 Manifest，更不自动启动执行。
### 5.3 六维范围原则

Time、Environment、Files、Data、People、Activities 六个维度必须全部显式声明；任何开放式描述无效。
### 5.4 不可变快照原则

每个已提交版本必须形成不可变快照、SHA256 和版本索引。实质范围变化必须创建新版本，不能覆盖原文。
### 5.5 默认禁止原则

生产环境、正式数据、生产凭据、生产端点、正式 Migration、Workflow 启用、RRE 启动以及未列明活动默认禁止。
## 6. Request Instance（申请实例）生命周期
### 6.1 创建前状态

```text
NOT_CREATED
↓
CREATION_READY / CREATION_BLOCKED
```

`CREATION_READY` 只表示创建前材料和校验设计满足要求，不表示实例已创建。
### 6.2 未来实例状态

```text
DRAFT（草稿）
↓
SUBMITTED（已提交）
↓
REVIEWING（评审中）
↓
APPROVED / REJECTED / BLOCKED
↓
CLOSED（关闭）
```
### 6.3 状态规则

| 状态 | 允许动作 | 禁止动作 |
|---|---|---|
| DRAFT | 编辑、补充、撤回草稿 | 形成授权、开始执行 |
| SUBMITTED | 完整性检查、退回补充 | 原地改变实质范围 |
| REVIEWING | 记录专业审核和问题 | 跳过必需审核 |
| APPROVED | 进入独立 Manifest 准备 | 直接进入 ACTIVE |
| REJECTED | 记录原因、关闭或重新起草 | 改写拒绝记录 |
| BLOCKED | 补齐依赖后创建新版本 | 继续裁决或执行 |
| CLOSED | 只读归档 | 恢复写入或复用编号 |

Request 的 APPROVED、REJECTED、BLOCKED 是申请裁决；SUSPENDED、REVOKED 属于未来 Authorization 生命周期，不得混入 Request 状态。
## 7. Instance 数据结构设计
### 7.1 标识与基础信息

| 字段 | 类型/格式 | 规则 |
|---|---|---|
| request_id | `{{REQUEST_ID}}` | 未来由权威编号器生成；本轮不分配 |
| request_version | 正整数 | 初始提交版本为 1，后续递增 |
| template_version | 版本引用 | 指向创建时活动模板 |
| title | 文本 | 明确证据主题，不写“上线申请” |
| request_owner | 自然人引用 | 必须实名，不得使用共享账号 |
| request_date | 日期时间 | ISO 8601 |
| created_by | 用户引用 | 与审计身份一致 |
| created_at | 日期时间 | 服务端生成 |
| updated_by / updated_at | 用户与时间 | 每次修改留痕 |
### 7.2 目标信息

| 字段 | 规则 |
|---|---|
| objective | 描述需要形成的证据，不承诺 Gate PASS |
| business_reason | 说明当前缺口及必要性 |
| target_gates | 只允许 Gate-2、Gate-4 或明确子项 |
| evidence_questions | 每项可验证、可失败 |
| expected_outputs | 指定文件、日志或结构化结果 |
| success_criteria | 客观、可复核、有阈值 |
| failure_result | 明确 FAILED 或 BLOCKED |
### 7.3 六维范围信息

| 维度 | 必填字段 | 核心约束 |
|---|---|---|
| Time | start、end、maximum_duration、windows | 到期自动失效 |
| Environment | environment_id、database_id、endpoints、network_policy | 仅非生产且生产不可达 |
| Files | repository、branch、commit、allowed_paths、prohibited_paths | 固定提交、路径白名单 |
| Data | source、classification、masking、objects、record_limit、namespace | 可追溯、最小化、不可回写 |
| People | owner、reviewers、executor、evidence reviewer、stop authority | 自然人职责分离 |
| Activities | activity、object、write budget、expected evidence | 未列入即禁止 |
### 7.4 控制信息

| 字段 | 最低内容 |
|---|---|
| risk_register | 风险、影响、概率、控制、责任人、停止触发 |
| rollback_plan | 恢复点、有序步骤、负责人、RTO、验证方法 |
| cleanup_plan | 数据、凭据、网络、环境和制品处理 |
| stop_conditions | 生产可达、越界、审计失效、回退失败、到期等 |
| dependencies | 前置报告、环境、数据授权和人员依赖 |
| evidence_location | 未来证据包的只读归档位置 |
### 7.5 审核和归档关联

实例应通过引用关联审核记录、附件索引、版本索引、修改记录、裁决记录和关闭记录。审核意见不得直接嵌入并覆盖申请正文。
## 8. 创建前校验设计
### 8.1 完整性校验

- 模板版本有效；所有必填字段存在；Request Owner 已实名；目标和证据问题可验证；
- 六维范围均存在；风险、回退、清理和停止方案完整；附件可访问；
- 没有未解释占位符、半句或开放式“相关内容”。
### 8.2 边界校验

- environment_type 必须为非生产；production_reachability 必须为 DENIED；
- 数据只能是合成、脱敏或获批只读副本；不得请求正式事实写入；
- 禁止正式 Migration、生产部署、企业数据导入、Workflow 启用或 RRE 启动；
- 允许路径、活动和写入预算必须形成白名单。
### 8.3 可追踪性校验

- 来源模板、创建人、创建时间和版本可追踪；repository 与 commit 固定；
- 数据来源和授权引用可追踪；附件具备版本与 SHA256；
- request_id 未来必须由权威编号器生成，禁止手工复用或前端推断。
### 8.4 职责分离校验

Request Owner 不得是最终 Authorization Owner；执行人不得是唯一技术或证据审核人；环境搭建人不得是唯一安全审核人；共享账号不能满足分离要求。
### 8.5 校验结果

| 结果 | 含义 | 后续 |
|---|---|---|
| CREATION_READY | 创建前规则满足 | 仅可等待独立实例创建授权 |
| CREATION_BLOCKED | 存在可补材料或依赖 | 修正准备材料后重检 |
| CREATION_REJECTED | 目标包含禁止事项 | 停止，不得创建实例 |

任何校验结果均不自动创建 Request Instance。
## 9. Request 与 Authorization Manifest 边界

| 对象 | 回答问题 | 形成时点 | 是否允许执行 |
|---|---|---|---|
| Request | 为什么需要、需要证明什么 | 申请提出时 | 否 |
| Review Record | 各专业审核是否接受 | 评审过程中 | 否 |
| Decision Record | 申请批准、拒绝或阻断 | 评审完成后 | 否 |
| Authorization Manifest | 具体允许的时间、环境、文件、数据、人员和活动 | Request APPROVED 后另行签发 | 仅在后续 READY_CHECK 通过后 |

禁止 `Request APPROVED = Authorization ACTIVE`，禁止由 Request 字段直接驱动执行器。
## 10. 版本管理设计
### 10.1 版本规则

- request_id 在同一申请链内稳定；request_version 从 1 递增；
- DRAFT 可以保存修订历史，但 SUBMITTED 后的版本正文不可覆盖；
- 新版本必须引用 previous_version、change_reason、changed_fields 和创建者；
- 每个版本独立计算 SHA256，并写入版本索引。
### 10.2 必须创建新版本的变化

- Environment、database、endpoint 或网络边界；Data 来源、分类、脱敏、数量或保留期；
- Repository、branch、commit、allowed/prohibited paths；People 或职责分离关系；
- Activities、写入预算、测试范围或目标 Gate；Time 窗口、期限、回退、清理或停止条件；
- 任何影响审核结论的风险或依赖变化。
### 10.3 非实质更正

拼写或排版更正也必须追加修改记录；只有不改变语义、范围和证据的问题才可作为同版本勘误。审核人有异议时一律升级版本。
### 10.4 审核失效

新版本发布后，受影响专业审核自动失效；环境、数据或安全边界变化至少重新执行 Security Review 和 Data Review；范围、责任或架构变化必须重新执行 Architecture Review。
## 11. 审核关联设计

| 审核 | 最低检查 | 输出状态 |
|---|---|---|
| Completeness Review | 字段、附件、六维范围 | PASS/BLOCKED/REJECTED |
| Architecture Review | BAC/OOM、事实源、责任权限边界 | PASS/BLOCKED/REJECTED |
| Security Review | 环境、网络、凭据、停止能力 | PASS/BLOCKED/REJECTED |
| Data Review | 来源、分类、脱敏、保留与销毁 | PASS/BLOCKED/REJECTED |
| Technical Review | 可行性、测试、写入预算、回退 | PASS/BLOCKED/REJECTED |
| Evidence Review | 输出、原始日志、SHA256、独立复核 | PASS/BLOCKED/REJECTED |

本报告不执行上述审核，不创建 Review Record，不填写审核人或审核结论。
## 12. Gate 映射设计

| Gate | Request 可提出的证据问题 | 不能替代 |
|---|---|---|
| Gate-2 Data | Schema、数据质量、时态、候选转换、Migration 演练和回退 | 正式 Migration、数据签发和生产迁移 |
| Gate-4 Technical | 服务、API、页面、权限、审计、测试、恢复和回退 | 生产发布和上线运行证据 |
| Gate-3 Governance | 仅可测试职责分离控制 | 实名任命、职责签发和人工治理 |
| Gate-5 Business | 仅可支持非生产演示或模拟脚本 | 业务确认、人工验收和上线窗口 |

Request 创建、提交或批准均不改变 Gate 状态。
## 13. 归档机制设计
### 13.1 归档组成

- Request 文件及所有版本；创建、修改、提交和撤回记录；
- 模板版本、附件清单、来源引用和各文件 SHA256；
- 完整性、架构、安全、数据、技术和证据审核记录；
- Decision Record、未来 Manifest 引用和关闭记录；
- 被拒绝、阻断和失败的原始材料。
### 13.2 归档索引

索引至少包含 request_id、request_version、状态、文件路径、SHA256、创建时间、提交时间、关闭时间和上一版本引用。索引只能追加，不得覆盖历史。
### 13.3 完整性规则

每个已提交版本必须先冻结正文，再计算 SHA256；审核记录必须引用精确版本与摘要；摘要漂移时立即 BLOCKED；关闭后仅允许追加审计更正，不得改写原记录。
### 13.4 保留与访问

归档按最小权限只读开放。REJECTED、BLOCKED 和已关闭申请不得删除；数据附件按分类与保留策略清理，但清理证据必须永久关联。
## 14. 未来创建流程设计

```text
选择活动模板
↓
准备目标与六维范围
↓
执行创建前校验
↓
CREATION_READY / BLOCKED / REJECTED
↓
独立实例创建授权
↓
权威编号器分配 request_id
↓
创建 DRAFT 并记录初始摘要
```

本报告只覆盖“准备与校验”设计，不执行“独立实例创建授权”及其后步骤。
## 15. 设计验证场景

| 编号 | 场景 | 预期结果 |
|---|---|---|
| CEB-RIP-T01 | 必填字段缺失 | CREATION_BLOCKED |
| CEB-RIP-T02 | 包含生产写端点 | CREATION_REJECTED |
| CEB-RIP-T03 | 数据来源不明 | CREATION_BLOCKED 或 REJECTED |
| CEB-RIP-T04 | 六维范围缺失一项 | CREATION_BLOCKED |
| CEB-RIP-T05 | 手工复用 request_id | 拒绝创建 |
| CEB-RIP-T06 | SUBMITTED 后修改 commit | 新版本并重新审核 |
| CEB-RIP-T07 | Request APPROVED 后直接执行 | 拒绝；Manifest 未签发 |
| CEB-RIP-T08 | 技术证据替代 Gate-3 | 拒绝 |
| CEB-RIP-T09 | 关闭后覆盖历史正文 | 拒绝并保留审计 |
| CEB-RIP-T10 | SHA256 与归档正文不一致 | BLOCKED |

这些场景仅为未来测试设计，本轮不执行。
## 16. 风险与控制

| 风险 | 影响 | 控制 |
|---|---|---|
| 准备报告被误作真实申请 | 越权进入评审 | 首页和最终状态明确 NOT CREATED |
| Request 被误作 Manifest | 未授权执行 | 对象、状态机和签发时点分离 |
| 手工编号或重复编号 | 审计链冲突 | 权威编号器和唯一性校验 |
| 提交后覆盖正文 | 历史不可追溯 | 不可变版本、追加修改记录和 SHA256 |
| 开放式范围 | 执行边界失控 | 六维白名单和默认禁止 |
| 审核结论跨版本复用 | 错误批准 | 版本变化使受影响审核失效 |
| Gate-2/4 证据替代 Gate-3/5 | 治理绕过 | Gate 映射明确不可替代项 |
## 17. 本轮保护状态

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

本轮没有生成 Request ID、Request Instance、Manifest、Review Record、Decision Record 或任何执行授权。
## 18. 最终状态

```text
Controlled Evidence Build Authorization Request Instance Preparation Design = COMPLETE
Authorization Request ID = NOT CREATED
Authorization Request Instance = NOT CREATED
Authorization Manifest Instance = NOT CREATED
Controlled Evidence Build Authorization = NOT GRANTED
Controlled Evidence Build Execution = NOT STARTED
OOM-4.2 Implementation Authorization Review = NOT STARTED
Organization Model Implementation = NOT AUTHORIZED
RRE-1 = NOT AUTHORIZED
Workflow Integration = NOT AUTHORIZED
Context Scope = CONTROLLED
Input Files = 4
Task Scope = SINGLE
Review Level = B
Full Content Review Required = NO
Documentation Archived = YES
Archive Content Readback = YES
ChatGPT Reviewable = YES
Source Excerpts Verified = YES
```

本报告完成后立即停止，等待人工审查；不得自动创建申请实例、提交审核、生成授权清单或启动受控证据构建。
