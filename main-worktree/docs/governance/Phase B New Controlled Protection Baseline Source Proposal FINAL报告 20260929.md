# FINAL / CONSOLIDATED

# 《Phase B New Controlled Protection Baseline Source Proposal FINAL报告》

日期：2026-09-29  
阶段：S1后续 — Source Proposal（来源提案）  
任务性质：治理提案登记 / 不产生数据库实体  
审查等级：Level C  
本轮结论：提出一个A类逻辑来源提案；B类与C类均不提出

## 一、当前治理背景

治理路径B要求：保留734F历史固定证据、保留ABA6765漂移后历史证据及完整CASE C调查链，通过全新、分阶段、可审计的流程建立未来受控Protection Baseline。

本轮前置状态为：

| 项目 | 固定状态 |
|---|---|
| Governance Path | `B` |
| 734F | `Historical Evidence` |
| ABA6765 | `Drifted Historical Evidence` |
| Drift Type | `REDUCED UNKNOWN` |
| Authentication Write Only | `NOT PROVEN` |
| Source Qualification Review | `COMPLETE` |
| Source Qualified | `NO` |
| Phase B Technical Re-admission | `BLOCKED` |

本轮只提出未来来源的逻辑对象，不改变上述任何事实，也不执行来源资格审查。

## 二、S1 Source Qualification结论承接

上一阶段已作出以下fail-closed结论：

- 734F不得作为活动来源；
- ABA6765不得作为来源；
- 开发数据库、`backend/db.sqlite3`、活动运行数据库和未知来源SQLite副本不得作为来源；
- A、B、C只是允许提出的来源类型，不代表具体来源已经通过资格Gate；
- 只有来源身份、来源链、数据范围、Schema/Migration、权限组织、恢复路径和职责分离七项全部满足，具体来源才可能通过后续审查。

因此，本报告不得继承或制造任何资格结论。提案状态只表示“是否提出”，不表示可信性、完整性、可执行性或准入状态。

## 三、任务范围与严格边界

### 3.1 本轮唯一目标

1. 在A/B/C中选择值得进入未来证据编制申请的来源类型；
2. 给出具体Source Proposal ID与逻辑身份；
3. 说明其预期输入、构建模型、数据边界和价值；
4. 完整登记当前证据缺口和禁止条件；
5. 判断是否允许申请Source Qualification Evidence Package编制授权。

### 3.2 本轮未执行事项

- 未创建Baseline文件或Candidate Database；
- 未创建、复制、导出或重命名任何数据库文件；
- 未打开Protection数据库或其它数据库进行业务读取；
- 未修改任何数据库、代码、配置、权限、组织或业务数据；
- 未计算任何新Baseline Hash，未签署Hash；
- 未建立正式Baseline Manifest或正式资格证据包；
- 未初始化Acceptance Runtime；
- 未执行Migration、Replay、Seed、DDL、DML或VACUUM；
- 未建立生成、验证或恢复环境；
- 未执行Source Qualification；
- 未进入Phase B开发或技术准入。

### 3.3 Database Boundary

```text
Database Opened = NO
Database Business Read = NO
Database Copy Created = NO
Database Write Attempted = NO
Candidate File Path Allocated = NO
Candidate File Created = NO
```

## 四、治理阅读与指令控制

### 4.1 COMPLETED MODULE GOVERNANCE READING RECEIPT

```text
Preservation Standard Read = YES
Completed Module Registry Read = YES
Registry Module Count = 34
Affected Frozen Modules = []
Freeze Contracts Read = []
Unfreeze Authorization = NO / NOT REQUIRED
Preserve-and-Extend Analysis = REPORT-ONLY; FIVE HISTORICAL REPORTS AND TWO HISTORICAL IDENTITIES PRESERVED
Preflight Result = SAFE TO MODIFY
```

已完整读取六份强制治理文件及以下五份专项报告：

1. Option B补充证据调查报告；
2. CASE C残余不确定性收敛报告；
3. Protection Baseline治理决策准备报告；
4. New Controlled Protection Baseline建立准备报告；
5. Source Qualification报告。

Registry的`currentFrozenVerifiedModuleIds=[]`，本任务不影响冻结模块、共享依赖、路由、API、数据权威、权限、Workflow或数据库身份。

### 4.2 INSTRUCTION CONTROL SHEET

```text
Original Goal = 提出未来可能成为新受控Protection Baseline来源的具体候选对象
Current Goal = 登记一个A类逻辑提案并停止在Evidence Package授权申请之前
IN SCOPE = 提案身份、预期输入/边界、构建设想、优势、缺口、禁止条件、下一授权需求
OUT OF SCOPE = 数据库实体、正式Manifest、资格执行、构建、Hash、签署、Acceptance初始化、技术准入
User Decisions = A/B/C三类中只提出具备治理合理性的具体逻辑对象
Frozen Facts / Functions = 734F历史身份；ABA漂移身份；Source Qualified为NO
Non-Regression Baseline = 五份历史报告、两个历史身份、技术阻断保持
Database Boundary = 不打开、不复制、不修改任何数据库
User Acceptance Path = N/A（非UI任务）
Required Evidence = 治理文件、五份历史报告、提案登记与缺口清单
Stop Condition = 本报告完成并回读；不开始Evidence Package编制
```

## 五、来源提案原则

1. 提案可以描述未来对象，但不得创建对象本身；
2. 提案ID与未来数据库身份分离，避免把治理记录误认为数据库实体；
3. 未确定的版本、人员、环境、Commit或输入Hash必须明确标为待指定，不得推测；
4. A类优先用于建立完整、可重复、可恢复的来源链；
5. 没有权威快照事实时不得虚构B类对象；
6. A类仍可行且没有专项例外依据时不得提出C类；
7. 734F、ABA、开发库、运行库及未知副本持续位于deny-list；
8. `PROPOSED`仅允许申请编制证据，不授权构建、审查或签署。

## 六、来源提案总表

| Source Proposal ID | Source Type | Proposed Logical Source | Source Proposal Status | 说明 |
|---|---|---|---|---|
| `NCPSB-SP-A-20260929-001` | A — 受控重新构建 | `PCE-NCPB-A-REBUILD-SOURCE-P01` | `PROPOSED` | 唯一提出对象；尚无数据库文件 |
| `NCPSB-SP-B-20260929-001` | B — 权威冻结快照 | N/A | `NOT PROPOSED` | 当前没有可指认的权威冻结快照 |
| `NCPSB-SP-C-20260929-001` | C — 特殊授权来源 | N/A | `NOT PROPOSED` | A类仍可行，且无专项授权或例外必要性 |

## 七、A类具体来源提案

### 7.1 来源提案登记

| 登记字段 | 内容 |
|---|---|
| Source Proposal ID | `NCPSB-SP-A-20260929-001` |
| Source Proposal Status | `PROPOSED` |
| Source Type | A — 受控重新构建来源 |
| Proposed Logical Source Identity | `PCE-NCPB-A-REBUILD-SOURCE-P01` |
| Source Owner | `PENDING GOVERNANCE APPOINTMENT` |
| Database Identity | `NOT EXISTS`; 未来身份必须由独立授权分配，不得复用734F或ABA身份 |
| Physical Database File | `NOT CREATED` |
| Expected Enterprise Scope | PCE明确获批的单一企业主体与组织边界；具体主体待证据包授权指定 |
| Expected Data Cut-off | 待治理批准并冻结，必须包含时区 |
| Expected Evidence Required | Database/File Identity、Source Chain、Data Scope、Schema/Migration、Permission/Organization、Recovery、Responsibility证据 |
| Known Gaps | Owner、输入版本、数据包、Runner、Commit、环境、截止点、恢复设计均未指定或未冻结 |
| Prohibited Conditions | 禁止使用734F、ABA、开发库、运行库、未知副本或任何现存SQLite作为捷径 |

该逻辑身份只用于把提案及其未来证据绑定到同一个治理对象。它不是数据库名称、文件路径、Baseline ID或签署对象。

### 7.2 预期来源输入

| 输入类别 | 提案要求 | 当前状态 |
|---|---|---|
| Schema版本 | 选取经治理批准、完整签名且与目标业务范围一致的冻结Schema版本 | 尚未选择、冻结或批准 |
| Migration集合 | 完整、有序、可与源码Commit及文件Hash对应；禁止fake与未授权分叉 | 尚未建立批准集合 |
| 基础数据包 | 仅包含获批的正式基础数据，具备来源、范围、版本和内容Hash | 尚未定义或批准 |
| 业务事实包 | 明确需要保留的业务事实、关系、截止点与来源分类 | 尚未定义或批准 |

输入必须以独立治理对象提交。不得从ABA逆向抽取并称为“已批准事实包”，不得直接复制开发库或运行库，也不得以现有测试结果替代输入来源证明。

### 7.3 预期构建方式

| 构建要素 | 提案要求 | 当前状态 |
|---|---|---|
| Generation Environment | 与Development、Validation、Recovery及Acceptance物理/逻辑隔离 | 尚未授权或建立 |
| Runner | 单一版本、可审计、参数固定、内容Hash可验证 | 尚未设计或批准 |
| Toolchain | Python/Django/SQLite及依赖版本锁定，工具自身可验证 | 尚未冻结 |
| Commit | 绑定获批Schema与Migration源码的唯一Commit | 尚未选择 |
| Network/Secrets | 默认断网；不加载生产接口、生产密钥或外部副作用能力 | 尚未形成环境证据 |
| Output Handling | 未来只写获批候选路径，构建完成后冻结；本轮不分配路径 | 未执行 |

### 7.4 为什么值得进入未来资格证据编制

- 可以从批准输入开始建立完整Source Chain，而不是解释漂移后的ABA；
- Schema、Migration、基础数据和业务事实可分别版本化与Hash绑定；
- Runner、Commit、工具链和环境可以被重复验证；
- 可以在不触碰历史Protection证据的前提下建立全新身份；
- 可设计为可重复生成，并为后续独立恢复验证提供确定输入；
- 更适合落实准备、技术复核、批准和技术准入的职责分离。

以上是提案价值，不是资格结论。任何一项只有在未来证据包中得到实证，才能供Source Qualification Gate评估。

### 7.5 当前已知缺口

1. Source Owner和三类核心责任人尚未由治理主体任命；
2. 企业主体、组织范围、数据边界和截止时间尚未批准；
3. Schema版本与Migration集合尚未冻结；
4. 基础数据包与业务事实包尚未定义、审批或计算输入Hash；
5. 测试、模拟、Preview、运行期和个人数据排除规则尚未形成证据；
6. Runner、工具链、参数、Commit及依赖版本尚未确定；
7. Generation Environment尚未授权，隔离证据不存在；
8. 权限、组织、用户和角色的目标事实尚未定义；
9. 可重复生成方案尚未实证；
10. 保存副本、恢复路径和失败回退尚未形成可验证方案；
11. Source Qualification Evidence Package尚未建立；
12. 任何候选数据库、文件身份或内容Hash均不存在。

### 7.6 禁止条件

以下任一情形都会使本提案停止，不得进入构建授权：

- 将ABA或其副本作为输入数据库、候选或事实权威；
- 将734F历史Hash重新解释为可恢复实体；
- 使用开发库、`backend/db.sqlite3`、活动运行库或未知SQLite；
- 在输入未冻结前创建候选文件；
- 缺少明确Owner、独立Reviewer或Approver；
- 使用fake migration、未授权Schema分叉或来源不明数据包；
- 让Generation路径被应用、登录流程或测试Runner持续打开；
- 以提案通过替代Source Qualification、Recovery或技术准入。

## 八、B类来源判断

### 8.1 提案登记

| 登记字段 | 内容 |
|---|---|
| Source Proposal ID | `NCPSB-SP-B-20260929-001` |
| Source Proposal Status | `NOT PROPOSED` |
| Source Type | B — 权威冻结快照来源 |
| Source Owner | N/A |
| Database Identity | N/A |
| Expected Data Boundary | N/A |
| Known Gaps | 无权威系统身份、所有者、冻结时间、数据范围、创建链、完整Hash和恢复链 |
| Prohibited Conditions | 不得把ABA、开发库、运行库或未知副本命名为权威快照 |

### 8.2 判断理由

当前证据中没有一个可指认的权威冻结快照。没有所有者、冻结事件、数据截止点、创建/导出链、文件身份和独立恢复能力时，不能构造B类提案。未来如出现真实权威快照，必须使用新的Proposal ID重新提出，不能继承本次A类提案。

## 九、C类来源判断

### 9.1 提案登记

| 登记字段 | 内容 |
|---|---|
| Source Proposal ID | `NCPSB-SP-C-20260929-001` |
| Source Proposal Status | `NOT PROPOSED` |
| Source Type | C — 特殊授权来源 |
| Source Owner | N/A |
| Database Identity | N/A |
| Expected Data Boundary | N/A |
| Known Gaps | 无法证明A/B均不可用；无特殊授权依据、等价控制或风险补偿方案 |
| Prohibited Conditions | C类不得成为绕过A类输入冻结、职责分离或恢复要求的例外通道 |

### 9.2 判断理由

A类受控重新构建仍具备治理可行性，当前不存在必须绕开A/B的技术或治理事实，也没有责任主体签发专项例外。因此不提出C类来源。

## 十、当前对象处理规则

| 当前对象 | Source Proposal Status | 固定处理 |
|---|---|---|
| 734F | `NOT PROPOSED AS ACTIVE SOURCE` | 只保留为Historical Evidence |
| ABA6765 | `NOT PROPOSED` | 只保留为Drifted Historical Evidence；不得复制为候选 |
| Development Database | `NOT PROPOSED` | 开发环境不得成为Baseline来源 |
| Runtime Database | `NOT PROPOSED` | 活动写入与运行身份不满足来源控制 |
| Unknown SQLite | `NOT PROPOSED` | 来源链未知即fail-closed |

这些状态不改变Source Qualification报告已经作出的`NOT QUALIFIED`结论。

## 十一、Evidence Package进入判断

对`NCPSB-SP-A-20260929-001`的判断为：

```text
EVIDENCE PACKAGE AUTHORIZATION REQUEST = ALLOWED
EVIDENCE PACKAGE COMPILATION = NOT EXECUTED
SOURCE QUALIFICATION EXECUTION = NOT AUTHORIZED
```

“允许申请”仅表示该A类逻辑提案具有收集资格证据的合理性。它不授权读取未明确列入范围的系统、生成数据库、建立正式Baseline Manifest、运行Migration、计算候选Hash或对来源作资格裁决。

## 十二、下一阶段授权需求

下一授权阶段只能是：**为`NCPSB-SP-A-20260929-001`编制Source Qualification Evidence Package**。

授权书必须至少明确：

1. 任命Source Owner、Source Preparer、Technical Reviewer和Approver，并完成职责冲突检查；
2. 批准企业主体、组织范围、数据边界和带时区截止点；
3. 精确列明允许只读收集的Schema、Migration、基础数据和业务事实来源；
4. 明确允许访问的路径、仓库Commit、工具及日志，未列明对象不得读取；
5. 定义输入分类、输入Hash和Evidence Package格式，但不得创建数据库；
6. 定义权限/组织目标事实和测试、模拟、运行期数据排除规则；
7. 提交可重复生成与恢复路径设计，实际演练留待后续独立授权；
8. 延续734F、ABA、开发库、运行库、未知SQLite的deny-list；
9. 任何证据缺失、身份冲突或责任冲突即停止；
10. Evidence Package完成后仍须另行授权Source Qualification审查，不能自动进入环境建立或Candidate构建。

## 十三、历史证据保护核对

五份历史报告在本轮开始时的SHA256如下，本轮不修改这些文件：

| 历史报告 | SHA256 | 状态 |
|---|---|---|
| Option B补充证据调查 | `EE9033A686B58811483C1B6502B9444CF57818E1A1839E55D5E96A15F0ACEBF1` | PRESERVED |
| CASE C残余不确定性收敛 | `5D7683399A26A78ED2DCC4553FEE85A7DD0A7A4B8767510A19960CBC086A7961` | PRESERVED |
| Baseline治理决策准备 | `2D9E026A8C38C8945FD6F7A883A479C700B4576C013D50540173B272429359BD` | PRESERVED |
| New Controlled Baseline建立准备 | `B5C707A1F2919AE58681FBA55C2156CF41BD123DD8EA329580E5168927F99028` | PRESERVED |
| Source Qualification | `FCE83708F20C09780E3C2F648E5D7980DF6A5AB07755353D500F1A1042818CD0` | PRESERVED |

734F继续作为Historical Evidence；ABA6765继续作为Drifted Historical Evidence。提案`PCE-NCPB-A-REBUILD-SOURCE-P01`不得复用、覆盖或暗示继承这两个历史身份。

## 十四、保护状态与合规矩阵

### 14.1 保护状态

```text
Documentation Changed = YES (THIS REPORT ONLY)
Code Changed = NO
Configuration Changed = NO
Database Opened = NO
Database Changed = NO
Database Copy Created = NO
Candidate Database Created = NO
Formal Baseline Manifest Created = NO
Migration / Replay / Seed Executed = NO
DDL / DML / VACUUM Executed = NO
Old 734F Record Changed = NO
Current ABA File Changed = NO
Historical Reports Changed = NO
New Baseline Hash Calculated = NO
Hash Signed = NO
Acceptance Initialized = NO
Phase B Development Started = NO
Unauthorized Business Writes = 0
```

### 14.2 最终合规矩阵

| Compliance Item | Result | Evidence / Note |
|---|---|---|
| Original Goal | PASS | 一个A类逻辑来源提案已登记；B/C未提出 |
| Governance Reading Receipt | PASS | 六份治理文件与五份历史报告已读 |
| Effective Instruction Set | PASS | 提案范围、deny-list、下一授权与停止点已登记 |
| Scope / Stop Condition | PASS | 仅新增报告，不创建数据库或证据包 |
| Existing Results Preserved | PASS | 734F、ABA及五份报告保持原身份 |
| Proposal Identity | PASS | Proposal ID与逻辑来源身份已明确分离 |
| Proposal Status Vocabulary | PASS | 每个来源只使用`PROPOSED`或`NOT PROPOSED` |
| A Source Proposal | PASS | 输入、构建设想、优势、缺口与禁止条件已登记 |
| B Source Decision | PASS | 无权威快照，未提出 |
| C Source Decision | PASS | 无必要性和专项授权，未提出 |
| Database Boundary | PASS | 未打开、复制或修改数据库 |
| Automated Tests | N/A | 无代码或实现变更 |
| User-Visible Real Path | N/A | 非UI任务 |
| Non-Regression | PASS | 历史身份、报告与技术阻断不变 |
| Report vs User Reality Conflict | NONE | 未发现冲突 |
| Final Stop Condition | PASS | 停止在Evidence Package编制授权之前 |

## 十五、最终裁决

本轮创建的是来源提案记录，而不是数据库候选：

- `NCPSB-SP-A-20260929-001`：`PROPOSED`；
- B类：`NOT PROPOSED`；
- C类：`NOT PROPOSED`；
- 734F、ABA、开发库、运行库及未知SQLite：全部不作为提案来源。

该A类提案可以申请Source Qualification Evidence Package编制授权，但当前没有建立证据包、没有执行资格审查，也没有产生任何数据库身份或文件。

## 十六、最终状态

```text
SOURCE PROPOSAL REVIEW = COMPLETE

SOURCE PROPOSAL CREATED = YES

SOURCE QUALIFICATION = NOT EXECUTED

SOURCE QUALIFIED = NO

CANDIDATE DATABASE CREATED = NO

NEW BASELINE CREATED = NO

HASH SIGNED = NO

DATABASE CHANGED = NO

ACCEPTANCE INITIALIZED = NO

PHASE B TECHNICAL RE-ADMISSION = BLOCKED
```
