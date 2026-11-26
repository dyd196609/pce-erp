# FINAL / CONSOLIDATED

# 《Phase B Protection Baseline治理决策准备 FINAL报告》

日期：2026-09-29（Asia/Shanghai）  
阶段：Phase B Protection Baseline治理决策准备  
任务类型：PREPARATION / GOVERNANCE DECISION MATERIAL  
审查等级：Level C（Protection Hash漂移异常仍未消除）  
任务结论：决策材料已完成；责任主体选择尚未作出

## 一、任务目标与非目标

本任务只为责任主体准备两条治理路径的事实、差异、风险、授权条件和停止边界，不替责任主体选择，不启动任一路径。

治理路径：

- 路径A：保留当前Protection文件及全部调查证据，作为不可重新签署历史证据；
- 路径B：明确废弃734F旧Protection Baseline，并另行启动新的受控Protection Baseline建立流程。

本报告中的“治理路径A/B”仅用于本轮决策比较，不复用前轮“恢复源Option A”或“当前文件重新签署Option B”的旧语义。前轮恢复源结论仍为`NOT AVAILABLE / NOT FOUND`，当前文件重新签署结论仍为`NOT READY`。

本任务没有：

- 选择、批准或执行路径A或路径B；
- 废弃、替换、覆盖或重新签署任何Baseline；
- 将当前ABA6765文件指定为新Baseline来源；
- 修改数据库、代码、配置、权限、组织或业务数据；
- 初始化Acceptance Runtime Database；
- 执行Migration、Replay、Seed、DDL、DML或VACUUM；
- 开放Phase B技术准入或开发。

## 二、治理读取与指令控制

### 2.1 COMPLETED MODULE GOVERNANCE READING RECEIPT

```text
Preservation Standard Read = YES
Completed Module Registry Read = YES
Affected Frozen Modules = []
Freeze Contracts Read = []
Unfreeze Authorization = NO
Preserve-and-Extend Analysis = REPORT-ONLY; EXISTING EVIDENCE AND SYSTEM STATE PRESERVED
Non-Regression Plan = NO DATABASE / HASH / CODE / BASELINE RECORD CHANGE
User Reality Conflict Rule = USER REALITY OVERRIDES AUTOMATION
Preflight Result = SAFE TO MODIFY
```

已全文读取：

1. `D:\Dev-PCE\AGENTS.md`；
2. `D:\Dev-PCE\Source\AGENTS.md`；
3. `docs/governance/PCE CODEX开发指令规范管理V1.2.md`；
4. `docs/governance/PCE 已开发模块固化与变更保护规范 V1.0.md`；
5. `docs/governance/completed_module_registry.v1.json`；
6. `docs/governance/COMPLETED_MODULE_PROTECTION_PREFLIGHT_V1.md`；
7. `docs/governance/Phase B Protection Database Option B补充证据调查 FINAL报告 20260929.md`；
8. `docs/governance/Phase B Protection CASE C残余不确定性收敛调查 FINAL报告 20260929.md`；
9. Protection文件的只读文件身份与Hash事实。

Registry登记34个模块，`currentFrozenVerifiedModuleIds=[]`，没有适用Freeze Contract。

### 2.2 EFFECTIVE INSTRUCTION SET / INSTRUCTION REGISTER

| ID | 状态 | 目的 | 仍有效约束 |
|---|---|---|---|
| PB-OPTION-B-SUPPLEMENT-20260929 | COMPLETED / FROZEN | Option B补充证据 | UNKNOWN；不得重签、恢复或初始化 |
| PB-CASE-C-RESIDUAL-20260929 | COMPLETED / FROZEN | 最后一次证据收敛 | REDUCED UNKNOWN；Option B NOT READY；技术准入阻断 |
| PB-BASELINE-GOV-PREP-20260929 | ACTIVE | 生成治理决策准备材料 | 不代选、不执行两路径、报告后停止 |

### 2.3 INSTRUCTION CONTROL SHEET

```text
Original Goal = 准备Protection Baseline治理选择材料
Current Goal = 汇总事实、比较路径A/B、分类风险并明确所需授权
IN SCOPE = 读取既有报告/Hash/治理文档；整理决策材料；风险分析
OUT OF SCOPE = 路径选择或执行；数据库/代码/配置/权限/组织/业务数据变更；Hash重新签署；Acceptance初始化
User Decisions = 当前仅准备材料；责任主体后续明确选择
Frozen Facts / Functions = CASE C COMPLETE；REDUCED UNKNOWN；Option B NOT READY；当前技术准入BLOCKED
Non-Regression Baseline = Protection文件、734F记录、ABA当前文件及全部历史调查证据原样保留
Database Boundary = NO DATABASE OPEN OR WRITE REQUIRED; FILE HASH/METADATA READ ONLY
User Acceptance Path = N/A
Required Evidence = 两轮报告、当前Hash/File ID/sidecar状态、治理规范
Stop Condition = 本报告归档并完整回读后停止
```

## 三、当前事实状态

### 3.1 当前Protection身份

| 项目 | 当前事实 | 证据等级 |
|---|---|---|
| 路径 | `D:\Dev-PCE\Acceptance\PDE-Operable-20260912\pde-operable-acceptance.sqlite3` | CONFIRMED |
| 当前SHA256 | `ABA6765C72540A52C3275D97A86CB302543BDA877DB95A3F745384757CDF93B1` | CONFIRMED |
| 历史固定基线SHA256 | `734F5B7D4D2A345F925DC5E06B61FA46CF4F068E91362389A59E33C8732FEE7D` | CONFIRMED历史记录 |
| 文件长度 | 31,481,856 bytes | CONFIRMED |
| CreationTime | `2026-09-12T13:48:22.2660122+08:00` | CONFIRMED |
| LastWriteTime | `2026-09-28T19:06:11.1963262+08:00` | CONFIRMED |
| NTFS File ID | `0x0000000000000000001b000000095003` | CONFIRMED当前值 |
| WAL/SHM/journal | 当前均不存在 | CONFIRMED当前观察 |

当前Hash、长度、LastWriteTime与File ID自首次漂移调查至本轮保持稳定；调查期间未观察到再次变化。这证明漂移后的当前文件身份稳定，不证明它等同734F基线。

### 3.2 已确认的认证写入链

```text
HTTP POST /api/auth/login/ 200
↓
Django login(request, user)
↓
django_session认证Session事实
↓
user_system.last_login = 2026-09-28 19:06:11.140081
↓
SQLite LastWriteTime = 2026-09-28 19:06:11.1963262
```

支持事实：

- `19:05:58`未认证读取返回401；
- `19:06:11`登录返回200；
- 同秒Session、`last_login`、文件LastWriteTime及登录后读取返回200互相对应；
- 登录代码明确调用Django `login()`，Session中间件已启用。

```text
AUTHENTICATION WRITE ASSOCIATION = CONFIRMED
```

### 3.3 未发现的积极证据

以下结论均表示“在已调查范围内未观察到”，不表示法证级排除：

| 调查事项 | 结果 | 证据等级 |
|---|---|---|
| 业务写入积极证据 | NOT OBSERVED | OBSERVED ONLY |
| 权限变化积极证据 | NOT OBSERVED | OBSERVED ONLY |
| 组织变化积极证据 | NOT OBSERVED | OBSERVED ONLY |
| 事件窗口Migration记录 | NOT OBSERVED | OBSERVED ONLY |
| 事件窗口DDL证据 | NOT OBSERVED | OBSERVED ONLY |
| Protection复制/覆盖命令积极证据 | NOT EVIDENCED | OBSERVED ONLY |
| 事件窗口业务/管理审计记录 | NOT OBSERVED | OBSERVED ONLY |
| 漂移后schema再次变化 | NOT OBSERVED | 当前签名稳定 |

300张非系统表的全字段窗口扫描只命中`user_system.last_login`。指定PDE、销售、采购、计划、权限组织域84张表、183个时间字段窗口命中0。当前`sqlite_master`对象签名在两次漂移后调查间保持`5ED7885ACFCB7FC191A65EBE9283FA46F8B87CC05D193789281BF011B81696D3`。

### 3.4 不能证明事项

1. 没有734F前态数据库实体；
2. 没有734F与当前文件的逐页、逐表、逐行、逐字段比较；
3. 没有完整进程、命令行、文件I/O和数据库写入审计链；
4. 没有漂移前File ID或可回放的历史USN；
5. 原始事件窗口HTTP日志载体已被后续运行截断，仅保留同期证据记录；
6. 无法排除无时间字段变化、等量替换或保留旧时间值的覆盖；
7. 无法证明权限、组织及业务关系表没有无时间字段变化；
8. 无法证明所有Hash差异仅由Session和`last_login`产生。

```text
AUTHENTICATION WRITE ONLY = NOT PROVEN
SCHEMA EQUALITY WITH 734F = NOT PROVEN
FILE OPERATION INCIDENT EXCLUSION = NOT PROVEN
```

## 四、CASE C演进过程

### 4.1 初始CASE C

前轮Option B差异和补充证据调查确认认证写入，却缺少734F比较实体。因此不能进入“全部差异均为认证运行数据”的排他性结论：

```text
UNKNOWN
```

### 4.2 最后一次证据收敛

新增外部证据包括：

- Codex精确窗口只见隔离Replay报告生成与Hash只读检查；
- Windows事件日志未出现Protection、SQLite、复制、Migration或业务管理命令；
- PowerShell历史未命中Protection精确路径或复制/移动命令；
- 当前schema签名在两个调查时点保持一致；
- 170条Migration记录最新应用时间早于事件窗口，窗口命中0；
- 指定业务和权限组织域窗口命中0；
- 当前文件身份与Hash在调查期间保持稳定。

这些证据降低了Schema、Migration、Codex文件操作及带时间业务写入风险，但不能补回734F前态或完整文件审计链，因此演进为：

```text
UNKNOWN
↓
REDUCED UNKNOWN
```

`REDUCED UNKNOWN`表示不确定范围已缩小，不表示证据门槛已经满足，也不构成当前文件重新签署依据。

## 五、治理路径A：保留历史证据

### 5.1 路径定义

保留当前Protection文件、734F历史固定记录、ABA当前Hash、全部调查报告和关联证据，明确将其管理为不可重新签署的历史证据集合。

该路径不把当前文件重新确认为活动Protection Baseline，也不删除或覆盖734F历史记录。

### 5.2 优点

- 保留事实完整性：历史固定Hash、当前文件、漂移事实和调查限制同时存在；
- 不把未被排他性证明的当前状态制造成新基线；
- 避免以治理标签掩盖`AUTHENTICATION WRITE ONLY = NOT PROVEN`；
- 最小化进一步技术写入、误签和审计争议；
- 为未来独立调查或责任复核保留原始对象和决策上下文。

### 5.3 限制和后果

- 当前734F活动基线无法恢复或验证；
- 当前ABA文件只能作为漂移后历史证据，不能承担活动基线资格；
- Acceptance Runtime初始化继续不得执行；
- Phase B技术重新准入和开发继续阻断；
- 若未来仍需恢复Phase B，仍需另行提出新受控Baseline治理议题。

### 5.4 路径A所需书面授权

- 责任主体确认“保留为不可重新签署历史证据”；
- 确认734F记录与ABA文件均不得被覆盖、删除或改写；
- 指定证据保管位置、访问责任人和保留期限；
- 确认技术阻断持续有效；
- 明确未来重新开启Baseline议题需要新的独立指令。

## 六、治理路径B：废弃旧Baseline并建立新受控Baseline

### 6.1 路径定义

由明确责任主体形成不可歧义的书面记录，宣布734F旧Protection Baseline不再作为活动准入基线；在保留旧记录和调查证据的前提下，另行授权并启动新的受控Protection Baseline建立流程。

该路径不是对当前ABA6765文件重新签署。当前文件不得因路径B获选而自动成为新Baseline来源、候选或结果。

### 6.2 必须满足的前置条件

1. **明确责任主体授权**：记录授权人、职责、授权范围、日期和签署依据；
2. **明确旧Baseline废弃记录**：将734F状态标记为已废弃/不再活动，但永久保留Hash、原因、证据和生效时间；
3. **明确新Baseline来源**：来源必须有可证明的生成链、业务边界、数据身份和责任归属，不能默认采用当前ABA文件；
4. **明确隔离环境**：定义物理路径、数据库身份、运行Profile、网络/应用隔离和禁止写入边界；
5. **明确全量Hash流程**：规定生成前后Hash、文件身份、schema/row/关键事实清单、签署角色和双人复核；
6. **明确恢复路径**：形成可验证的受控副本、恢复演练、Hash复核、保存位置和失败回退；
7. **明确后续准入标准**：定义何时可申请Acceptance初始化、技术重准入及谁有权裁决；
8. **保留历史证据**：路径B不得删除、覆盖或重写734F、ABA及CASE C调查链；
9. **职责分离**：Baseline生成、复核、签署和准入裁决不得由单一责任人自批；
10. **独立执行指令**：准备、建立、验证、签署与准入必须分阶段授权，不因本报告自动开始。

### 6.3 优点

- 可在明确放弃不可恢复旧基线后，建立具有完整来源与恢复能力的新活动基线；
- 可以重新形成前态、全量Hash、责任签署和可复核恢复链；
- 若所有独立Gate未来通过，可为后续Phase B重准入提供新的技术依据。

### 6.4 限制和后果

- 废弃旧Baseline是治理责任决定，不能由技术证据自动推出；
- 新Baseline建立将产生新的受控工件和独立风险，需要单独计划、执行和验证；
- 在新Baseline全部Gate和责任复核完成前，Phase B仍持续阻断；
- 新Baseline不能消除或改写旧漂移事实，只能建立新的治理起点；
- 当前ABA文件是否可作为任何来源必须由未来独立来源审查决定，本报告不作预判。

## 七、两条路径差异

| 比较项 | 路径A：保留历史证据 | 路径B：建立新受控Baseline |
|---|---|---|
| 本轮是否自动执行 | 否 | 否 |
| 734F历史记录 | 永久保留；不再尝试重签 | 永久保留并另行记录废弃状态 |
| 当前ABA文件 | 历史证据，不是活动基线 | 历史证据；不得自动成为新Baseline |
| 是否需要新技术流程 | 当前不启动 | 需要另行授权的来源、隔离、建立、验证、签署流程 |
| 审计姿态 | 保留现状与不确定性 | 保留旧事实并建立新的治理起点 |
| 恢复能力 | 734F恢复源仍不存在 | 必须为新Baseline新建并验证恢复路径 |
| 当前技术准入 | 持续阻断 | 新Baseline全部Gate完成前持续阻断 |
| 主要优点 | 不制造未经证明基线 | 可建立完整、可恢复的新治理链 |
| 主要代价 | 无活动基线，Phase B无法推进 | 责任与执行成本高，且必须严格分阶段 |

## 八、风险分类

风险标记说明：`已确认`表示事实或风险触发条件已有证据；`未确认`表示尚未发现积极证据但不能排除；`缺失证据`表示结论所需证据源不存在或不完整。

| 风险类别 | 风险事项 | 标记 | 对治理选择的影响 |
|---|---|---|---|
| 技术风险 | 当前Hash与734F不一致 | 已确认 | 当前文件不能沿用旧基线资格 |
| 技术风险 | 认证写入与Hash漂移同秒关联 | 已确认 | 解释了观察到的认证事实，但不是排他性解释 |
| 技术风险 | 是否还存在无时间字段或未记录写入 | 未确认 | 禁止将当前状态直接认定为纯认证漂移 |
| 技术风险 | 734F与当前schema完全一致 | 缺失证据 | 缺少734F实体Comparator |
| 数据可信风险 | 业务、权限、组织变化积极证据 | 未确认（未观察到） | 可降低风险，不能证明零变化 |
| 数据可信风险 | 当前数据可作为新Baseline来源 | 未确认 | 必须由未来独立来源审查决定 |
| 数据可信风险 | 全部Hash变化仅来自认证写入 | 缺失证据 | `AUTHENTICATION WRITE ONLY`不能成立 |
| 审计风险 | 734F前态数据库实体缺失 | 已确认 | 无法完成逐页、逐行、逐字段差分 |
| 审计风险 | 完整文件操作和进程审计链 | 缺失证据 | 无法法证级排除替换/覆盖或外部动作 |
| 审计风险 | 漂移前File ID/历史USN | 缺失证据 | 当前File ID稳定不能反证事件前连续性 |
| 后续开发风险 | 在Baseline决策前启动Acceptance或Phase B | 已确认高风险 | 必须继续阻断 |
| 后续开发风险 | 将路径B误解为签署当前ABA文件 | 已确认治理风险 | 必须使用“建立新的受控Protection Baseline”语义 |
| 后续开发风险 | 新Baseline未分阶段即直接准入 | 未确认 | 需要独立Gate和职责分离防止发生 |
| 恢复风险 | 734F恢复源不存在 | 已确认 | 旧基线不可恢复 |
| 恢复风险 | 当前历史证据被删除或覆盖 | 未确认 | 两条路径均必须禁止删除和覆盖 |
| 恢复风险 | 新Baseline恢复路径未建立 | 缺失证据 | 路径B执行前必须设计、演练并验证 |

## 九、责任主体决策所需授权材料

### 9.1 路径选择授权的必填字段

责任主体后续应形成独立书面决策，至少包含：

```text
Decision ID = [待填写]
Decision Authority = [姓名/角色/职责]
Decision Date = [待填写]
Selected Governance Path = [A / B]
Decision Rationale = [待填写]
Evidence Reviewed = [CASE C报告、Option B报告、Hash与文件身份]
734F Record Preservation = REQUIRED
ABA File Preservation = REQUIRED
Historical Reports Preservation = REQUIRED
Effective Scope = [待填写]
Explicit Prohibitions = [待填写]
Next Authorized Stage = [NONE / 独立新Baseline准备指令]
Independent Reviewer = [待填写]
```

本报告不预填`Selected Governance Path`，也不把任何路径标记为已批准。

### 9.2 若选择路径B，还需单独授权

- 旧734F Baseline废弃记录的起草、复核与签署；
- 新Baseline来源识别与可信性审查；
- 隔离环境和数据库身份设计；
- 受控Baseline建立方案；
- 全量事实、schema、文件Hash和恢复证据方案；
- 双人职责分离复核；
- 建立完成后的独立技术准入评审。

这些授权必须逐阶段下达。本报告不构成其中任何一项执行授权。

## 十、未完成事项与禁止事项

### 10.1 未完成事项

- 责任主体尚未选择路径A或路径B；
- 734F旧Baseline尚未被正式保留为最终历史状态或正式废弃；
- 新受控Baseline来源、隔离、Hash、恢复和准入标准尚未授权或建立；
- Protection Baseline Decision仍为PENDING；
- Acceptance Runtime初始化与Phase B技术重准入仍被阻断。

### 10.2 持续禁止事项

- 修改Protection数据库、代码、配置、权限、组织或业务数据；
- Hash重新签署；
- Acceptance Runtime初始化；
- Migration、Replay、Seed、DDL、DML或VACUUM；
- 删除历史文件、覆盖旧Baseline记录或改写调查报告；
- 将当前ABA文件自动指定为新Baseline；
- 在责任主体书面选择和独立授权前进入任一路径执行；
- 在新受控Baseline全部Gate完成前解除技术阻断。

## 十一、保护状态与合规矩阵

### 11.1 保护状态

```text
Documentation Changed = YES (THIS REPORT ONLY)
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
Hash Re-signed = NO
Acceptance Runtime Database Initialized = NO
Baseline Path Selected = NO
New Controlled Baseline Started = NO
Protection SHA256 Before = ABA6765C72540A52C3275D97A86CB302543BDA877DB95A3F745384757CDF93B1
Protection SHA256 After = ABA6765C72540A52C3275D97A86CB302543BDA877DB95A3F745384757CDF93B1
```

### 11.2 最终合规矩阵

| Compliance Item | Result | Evidence / Note |
|---|---|---|
| Original Goal | PASS | 仅生成两路径治理决策准备材料 |
| Governance Reading Receipt | PASS | 6项治理基线已全文读取 |
| Effective Instruction Set | PASS | 3项任务指令已登记 |
| Scope / Stop Condition | PASS | 报告归档回读后停止 |
| Existing Results Preserved | PASS | CASE C、Hash和全部历史记录未修改 |
| Automated Tests | N/A | 无代码或实现变更 |
| User-Visible Real Path | N/A | 非UI任务 |
| UI Data Visibility | N/A | 非UI任务 |
| Non-Regression | PASS | 仅新增报告；技术与数据状态未改变 |
| User Manual Validation | N/A | 本任务需要后续治理选择，不是UI验收 |
| Production Boundary | PASS | 数据库写入0；外部执行0 |
| Report vs User Reality Conflict | NONE | 未发现冲突 |
| Final Stop Condition | PASS | 不进入任一路径执行 |

## 十二、最终状态

### 12.1 CODEX执行质量指标

```text
Context Scope = CONTROLLED
Input Files = 9 DIRECT EVIDENCE OBJECTS
Task Scope = SINGLE
Output Size = 430 LINES / BELOW 500-LINE LIMIT
Review Level = C
Full Content Review Required = YES
Documentation Archived = YES
Archive Content Readback = YES
ChatGPT Reviewable = YES VIA ARCHIVED FULL REPORT
```

### 12.2 固定状态

```text
PROTECTION BASELINE GOVERNANCE PREPARATION = COMPLETE

CURRENT BASELINE DECISION = PENDING

OPTION A = RETAIN HISTORICAL EVIDENCE

OPTION B = REQUIRE EXPLICIT AUTHORIZATION FOR NEW CONTROLLED BASELINE

HASH RESIGN = NOT EXECUTED

PHASE B TECHNICAL RE-ADMISSION = BLOCKED
```
