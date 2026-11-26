# FINAL / CONSOLIDATED

# 《Phase B Protection CASE C残余不确定性收敛调查 FINAL报告》

日期：2026-09-29（Asia/Shanghai）  
任务性质：最后一次只读证据收敛窗口  
调查对象：`D:\Dev-PCE\Acceptance\PDE-Operable-20260912\pde-operable-acceptance.sqlite3`  
最终裁决：`CASE C / REDUCED UNKNOWN / OPTION B NOT READY`

## 一、原始CASE C背景

已确认的前置状态：

- Replay Validation：PASS（本轮未重跑）；
- Migration Replay：PASS（本轮未重跑）；
- Acceptance Runtime Database隔离：COMPLETE（本轮未初始化）；
- Protection固定基线SHA256：`734F5B7D4D2A345F925DC5E06B61FA46CF4F068E91362389A59E33C8732FEE7D`；
- 当前Protection SHA256：`ABA6765C72540A52C3275D97A86CB302543BDA877DB95A3F745384757CDF93B1`；
- Option A：NOT AVAILABLE；Recovery Source：NOT FOUND；
- 上一轮Option B补充调查：只观察到认证运行事实，但无法证明全部Hash差异仅来自认证写入；
- 原裁决：`DRIFT TYPE = UNKNOWN / OPTION B = NOT READY`。

本轮唯一目标是使用仍可取得的外部证据和当前只读结构事实，缩小UNKNOWN范围；不是恢复、修复、重新签署或准入执行。

## 二、本轮范围、保护边界与治理回执

### 2.1 COMPLETED MODULE GOVERNANCE READING RECEIPT

```text
Preservation Standard Read = YES
Completed Module Registry Read = YES
Affected Frozen Modules = []
Freeze Contracts Read = []
Unfreeze Authorization = NO
Preserve-and-Extend Analysis = REPORT-ONLY; NO MODULE OR SHARED DEPENDENCY CHANGE
Completed Module Protection Preflight = SAFE TO MODIFY
```

已全文读取`D:\Dev-PCE\AGENTS.md`、本工作区`AGENTS.md`、开发指令规范V1.2、已开发模块保护规范、Registry及Protection Preflight。Registry登记34个模块，`currentFrozenVerifiedModuleIds=[]`，没有适用Freeze Contract。本任务唯一写入是本报告。

### 2.2 调查范围

- 应用/HTTP/Django日志的既有记录；
- Codex执行记录；
- PowerShell持久历史的可访问内容；
- Windows事件日志；
- Protection文件系统元数据；
- SQLite当前schema对象、索引、Migration、page元数据及指定业务域；
- 重点窗口：`2026-09-28 19:00:00–19:10:00`，必要时使用UTC对应窗口及相邻证据。

SQLite唯一连接URI：

```text
file:///D:/Dev-PCE/Acceptance/PDE-Operable-20260912/pde-operable-acceptance.sqlite3?mode=ro&immutable=1
```

### 2.3 明确未执行事项

- 未修改任何数据库、代码、配置、权限、组织或业务数据；
- 未执行Hash重新签署、Migration、Replay、Seed、DDL、DML、VACUUM或journal恢复；
- 未创建或覆盖数据库副本；
- 未初始化Acceptance Runtime Database；
- 未启动应用、未登录、未触发新认证记录；
- 未进入Phase B开发或业务流程。

## 三、证据分级规则

| 等级 | 本报告含义 |
|---|---|
| CONFIRMED | 有明确日志、数据库字段、代码机制或文件时间的正向关联 |
| OBSERVED ONLY | 已扫描且未发现命中，只描述当前可见范围 |
| NOT PROVEN | 缺少734F前态、完整审计源或无时间字段比较，不能作排他性结论 |

`NOT OBSERVED`不等于`NO CHANGE`；本报告不将OBSERVED ONLY提升为CONFIRMED。

## 四、上一轮Option B补充调查汇总

### 4.1 当前数据库与表级事实

- 非系统表：300张；非空表：110张；完整当前行数快照已记录于上一轮报告；
- `user_system`：30行，admin的`last_login=2026-09-28 19:06:11.140081`；
- `django_session`：190行，存在一条同秒认证Session事实，`expire_date=2026-10-12 19:06:11.189491`，数据长度228；
- `django_admin_log=0`；`system_organization_operating_audits=2677`且窗口命中0；`business_action_audit_records=0`；
- 全部300张非系统表全字段窗口扫描只有`user_system.last_login`命中；
- Sales、CRM、Procurement、Inventory、PDE、BOM、Production、Planning、PFM未观察到窗口时间字面值；
- 权限与组织当前计数已记录，但因无734F前态不能证明无变化。

### 4.2 认证时间链

| 时间 | 事实 | 等级 |
|---|---|---|
| 19:05:58 | 未认证业务读取HTTP 401 | CONFIRMED（同期证据记录） |
| 19:06:11 | `POST /api/auth/login/` HTTP 200 | CONFIRMED（同期证据记录） |
| 19:06:11.140081 | `user_system.last_login` | CONFIRMED（当前DB字段） |
| 19:06:11.189491 | 对应14天Session到期事实 | CONFIRMED（当前DB字段） |
| 19:06:11.1963262 | Protection LastWriteTime | CONFIRMED（文件元数据） |
| 同秒 | 后续profile/material facts读取HTTP 200 | CONFIRMED（同期证据记录） |

服务代码`backend/system/views.py`的登录路径调用Django `login(request, user)`；Session中间件已启用。代码机制、HTTP、数据库字段和文件时间构成同秒正向链。

```text
AUTHENTICATION WRITE ASSOCIATION = CONFIRMED
AUTHENTICATION WRITE ONLY = NOT PROVEN
```

前者确认发生过认证写入；后者仍要求排除所有业务、权限、组织、Schema和无时间字段变化，当前证据不能做到。

## 五、本轮新增外部运行证据

### 5.1 Codex执行记录

已对可见的2026-09-28 Codex会话记录进行只读复核。精确窗口`19:04:30–19:07:01`内，主会话只记录：

1. `19:05:45`生成隔离Migration Replay FINAL报告；
2. `19:06:01`读取该报告、计算Fingerprint与Protection/C5 Hash及元数据；
3. `19:06:25`交付Replay结论。

窗口内未发现对Protection路径执行`Copy-Item`、`Move-Item`、覆盖、Migration、Seed或Replay的Codex命令。Replay报告记录隔离Replay完成时固定Hash仍为734F；报告生成与Hash读取均为只读。

分级：`OBSERVED ONLY`。Codex可见记录未命中不等于操作系统不存在其他进程或人工动作。

### 5.2 HTTP/Django日志保全状态

同期证据报告保存了19:05:58、19:06:11请求链，并记录当时后端日志SHA256为`096C1D2D9CD166A18EC30B0571263F36D65F593B2A3059B772AB1FECB3854888`、LastWriteTime为`19:06:11.3761696`。

当前活动`backend.stderr.log`已在2026-09-29被后续运行截断/重建，仅含新的401记录，无法再次从原日志载体独立回放事件窗口。因此：

- 同期报告中的登录链：CONFIRMED历史证据；
- 原始日志当前可复核性：NOT PROVEN；
- 未发现窗口内业务写请求：OBSERVED ONLY；
- 仅凭现存日志排除业务请求：NOT PROVEN。

### 5.3 Windows事件记录

只读查询`Microsoft-Windows-PowerShell/Operational`、`Windows PowerShell`、`Application`和`System`：

- PowerShell Operational：3条，均为19:06:27控制台启动/IPC事件；
- Windows PowerShell：8条，均属同一控制台引擎生命周期；其EncodedCommand解码为Codex通知音播放，与数据库无关；
- Application：窗口内无匹配事件；
- System：5条为IsolatedUserMode/Secure Trustlet事件，与Protection路径无关联；
- 事件消息未命中Protection路径、SQLite、复制、覆盖、Migration、runserver或Python数据库命令。

分级：`OBSERVED ONLY`。这些日志未启用完整进程命令行、Script Block、文件I/O或EDR审计，不能用于排除未记录动作。

### 5.4 PowerShell历史

持久历史文件已只读访问。结果：

- 未命中Protection精确路径；
- 未命中`Copy-Item`或`Move-Item`；
- 存在大量历史`runserver`及若干泛化`manage.py migrate`命令；
- PSReadLine历史没有执行时间戳，无法把泛化命令关联到19:00–19:10窗口。

分级：精确路径/复制覆盖`NOT OBSERVED`；窗口排除能力`NOT PROVEN`。

### 5.5 文件元数据

| 项目 | 当前结果 |
|---|---|
| Length | 31,481,856 bytes |
| CreationTime | `2026-09-12T13:48:22.2660122+08:00` |
| LastWriteTime | `2026-09-28T19:06:11.1963262+08:00` |
| SHA256 | `ABA6765C72540A52C3275D97A86CB302543BDA877DB95A3F745384757CDF93B1` |
| NTFS File ID | `0x0000000000000000001b000000095003` |
| `-wal` / `-shm` / `-journal` | 当前均不存在 |

当前Hash、长度、LastWriteTime及File ID自2026-09-28漂移调查以来保持一致，说明调查后的当前实体稳定。由于没有漂移前File ID、历史USN明细、ProcMon或EDR文件事件，不能法证级排除19:06:11之前的替换/覆盖。

```text
FILE OPERATION INCIDENT = NOT EVIDENCED
FILE OPERATION INCIDENT EXCLUSION = NOT PROVEN
```

## 六、SQLite结构稳定性补充

### 6.1 当前结构签名

规范化规则：按`type,name`排序，将`type|name|tbl_name|sql`以UTF-8拼接后计算SHA256。

| 对象 | 数量 | 当前签名 |
|---|---:|---|
| 全部sqlite_master对象 | 1300 | `5ED7885ACFCB7FC191A65EBE9283FA46F8B87CC05D193789281BF011B81696D3` |
| 表（含sqlite系统表） | 301 | `CA80D444055F0B72EC0A09C284C5312D622065F1BE79BF6CEBC4700EAFD65220` |
| 索引 | 999 | `51D582EA7CBD3A9AE6709BE0F108DACFA9A3911917E8BAB654FCA3ECADF38476` |

全部对象签名与2026-09-28 Option B调查记录的当前签名`5ED788...96D3`一致，证明漂移后调查时点至本轮之间当前schema清单稳定；它不等同734F，也不证明734F时的schema相同。

### 6.2 Migration和page观察

| 项目 | 当前值 |
|---|---|
| `django_migrations` | 170行 |
| Migration清单签名 | `3C637D1617B12904800826FB4653073D4F25179028E0EE1626184EAD93B8043D` |
| 最新`applied` | `2026-09-22 21:04:47.123924` |
| 19:00–19:10 Migration命中 | 0 |
| `page_count` | 7686 |
| `freelist_count` | 36 |
| `schema_version` | 6054 |
| `user_version` / `application_id` | 0 / 0 |
| `journal_mode` | `delete` |

结论分级：

```text
SCHEMA DDL OR MIGRATION IN WINDOW = NOT OBSERVED
POST-DRIFT CURRENT SCHEMA STABILITY = CONFIRMED
SCHEMA EQUALITY WITH 734F = NOT PROVEN
```

page和schema PRAGMA只有当前值，不能推导734F前态或页级变化来源。

## 七、业务关键表风险扫描

本轮按用户指定前缀重新扫描当前可见时间/审计字段，并同时覆盖本地与UTC对应窗口。

| 领域 | 匹配表 | 时间字段 | 窗口命中 | 最新可解释操作时间 |
|---|---:|---:|---:|---|
| PDE：`pde_engineering*`/`pde_product*`/`pde_order*` | 40 | 103 | 0 | `updated_at`最晚为2026-09-26 18:32:59 |
| Sales：`sales_order*` | 4 | 7 | 0 | `updated_at`最晚为2026-09-18 22:35:11 |
| Purchase：`purchase*`/`scm_purchase*` | 29 | 56 | 0 | `purchase_order.updated_at`最晚为2026-08-27 14:18:06 |
| Planning：`planning*` | 4 | 12 | 0 | `updated_at`最晚为2026-08-27 15:59:52 |
| Role/Permission/Organization指定前缀 | 7 | 5 | 0 | 组织审计`created_at`最晚为2026-09-26 18:32:59 |

此外，上一轮全库全字段扫描未命中任何业务字段。综合判定：

```text
BUSINESS DATA CHANGE OBSERVED = NO
PERMISSION CHANGE OBSERVED = NO
ORGANIZATION CHANGE OBSERVED = NO
BUSINESS / PERMISSION / ORGANIZATION CHANGE EXCLUSION = NOT PROVEN
```

原因是当前数量、当前最大时间和零窗口命中都不是前后差分；无时间字段更新、保留旧时间值的覆盖、等量替换及无审计关系表仍无法排除。

## 八、新增证据与残余缺口

### 8.1 新增证据

1. Codex精确窗口只出现Replay报告生成及Hash/元数据只读检查，未发现Protection写命令；
2. Windows四类事件日志未出现数据库、复制、Migration或业务管理操作证据；
3. PowerShell历史中未发现Protection精确路径或复制/移动命令；
4. 当前schema全对象签名与前一调查时点一致；
5. 170条Migration记录的最新时间早于事件窗口，窗口命中0；
6. 指定PDE、销售、采购、计划、权限组织域共84张匹配表、183个时间字段，窗口命中0；
7. 当前文件身份、Hash及无sidecar状态在调查期内保持稳定。

这些证据使“Schema/Migration/Codex文件操作/带时间业务写入”成为低可见风险，UNKNOWN范围较上一轮缩小。

### 8.2 决定性缺口

1. 734F数据库实体和可信逐页/逐行前态不存在；
2. 原始事件窗口HTTP日志载体已被后续运行截断，只有同期证据记录；
3. PowerShell历史没有时间戳，Windows日志没有完整命令行、Script Block和文件I/O审计；
4. 没有漂移前File ID、历史USN、ProcMon或EDR证据；
5. 无法排除无时间字段变化、等量替换或保留旧时间字段的写入；
6. 无法完成权限、组织和业务关系表与734F的全字段Comparator；
7. 因此不能证明Hash变化的全部字节范围只来自`last_login`与Session。

## 九、Option B重新评估

| 判定条件 | 结果 |
|---|---|
| 认证写入存在且与文件写入同秒 | CONFIRMED |
| 窗口内业务/管理/Migration/DDL积极证据 | NOT OBSERVED |
| 文件复制/覆盖积极证据 | NOT EVIDENCED |
| 当前schema在两次漂移后调查间稳定 | CONFIRMED |
| 变化表仅认证相关 | NOT PROVEN |
| 无业务、权限、组织或Schema变化 | NOT PROVEN |
| 全部Hash变化可由认证运行数据解释 | NOT PROVEN |

本轮没有发现CASE B所需的业务变化积极证据；但CASE A要求的排他性证明仍未满足。证据已显著聚焦到认证写入，却不能把“最强解释”升级为“唯一被证明解释”。

```text
DRIFT TYPE = REDUCED UNKNOWN
AUTHENTICATION WRITE ONLY = NOT PROVEN
OPTION B = NOT READY
```

## 十、Protection Baseline Decision建议

本报告完成最后一次证据收敛。继续重复扫描当前单点数据库不会补回734F前态，也不能消除决定性缺口。后续不应继续以同类调查替代治理决定。

可进入的治理选择仅为：

1. 保留当前Protection文件及现有报告，作为不可重新签署的历史证据；或
2. 由责任主体明确废弃旧Protection基线，并另行授权建立新的受控基线流程。

本任务不替责任主体选择、不废弃基线、不创建新基线，也不授权Hash重新签署。当前Protection Baseline Decision继续PENDING。

## 十一、Phase B影响与全部未完成项

继续阻断：

- Option B责任审核和Hash重新签署；
- Protection Baseline更新、替换或废弃；
- Acceptance Runtime Database初始化；
- Phase B流程开发、业务初始化和技术重新准入。

仍需治理层完成：

- 在“保留不可重新签署历史证据”与“废弃旧基线并建立新受控基线”之间作明确书面决定；
- 如选择新基线，另行定义来源、隔离、责任复核、全量签名及可恢复证据链；
- 在该决定完成前维持当前保护边界和阻断状态。

## 十二、本轮保护结果

```text
Documentation Changed = YES (THIS REPORT ONLY)
Code Changed = NO
Database Changed = NO
Database Open Mode = mode=ro + immutable=1
Migration / Replay / Seed = NOT EXECUTED
DDL / DML / VACUUM = NOT EXECUTED
Application / Login = NOT STARTED
Acceptance Runtime Database Initialized = NO
Hash Re-signed = NO
Protection SHA256 Before = ABA6765C72540A52C3275D97A86CB302543BDA877DB95A3F745384757CDF93B1
Protection SHA256 After = ABA6765C72540A52C3275D97A86CB302543BDA877DB95A3F745384757CDF93B1
Unauthorized Business Writes = 0
```

## 十三、最终状态

```text
PROTECTION CASE C RESIDUAL REVIEW = COMPLETE

DRIFT TYPE = REDUCED UNKNOWN

OPTION B STATUS = NOT READY

PROTECTION BASELINE DECISION = PENDING

PHASE B TECHNICAL RE-ADMISSION = BLOCKED
```
