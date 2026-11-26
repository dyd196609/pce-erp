# Phase B Git源基线治理 FINAL / CONSOLIDATED 报告

- 日期：2026-09-28
- 任务性质：A4 Git源基线治理；只读审计与文档归档
- 最终状态：`Git源基线治理状态 = PARTIAL`
- 下一允许阶段：`Phase B Migration源图治理审计`，不得进入业务开发

## 一、执行范围

本任务只执行Git源状态冻结、变更归属分类、权威性判断和后续治理建议。没有修改业务逻辑、Router、Registry、权限、业务流程、Schema、Migration或数据库；没有删除、归档、提交、reset、checkout或clean任何用户文件。

主工作区和制造集成工作树均纳入只读审计。主工作区是当前权威成果来源；集成工作树是Phase A与当前权威成果的已提交候选，二者没有互相覆盖。

## 二、治理文件读取结果

已全文读取：

1. `D:\Dev-PCE\AGENTS.md`，SHA256 `0CD48571FDCBF666074E297747530BD5FB2E5BAA2E5B2B3FF4293B013CFA5954`；
2. `D:\Dev-PCE\Source\AGENTS.md`，SHA256 `BC701CB81E2D71159CC3590001AA2DD0F929ACF158D18243A9408CDC0075EC44`；
3. `PCE CODEX开发指令规范管理V1.2.md`，1151行，SHA256 `50791C92F16248C84073CFF2BF58582414F14A03492AA4FCA69AA9052D5EA888`；
4. `PCE 已开发模块固化与变更保护规范 V1.0.md`，SHA256 `B6FAAAB15AA43E7E14836CC95BFE80DB1782C9EBA5F405C579DEC4AFAAC435D8`；
5. `completed_module_registry.v1.json`，SHA256 `10F23EA6109FECD7C0D4E5FA848938F29961D1D938DC9F306D87F37B2EE13B32`；
6. `COMPLETED_MODULE_PROTECTION_PREFLIGHT_V1.md`，SHA256 `D2B2487B8126EB435599CF35DDB3A0AB98E96D2A0F6241A4AE1950859EE6D4BD`。

### COMPLETED MODULE GOVERNANCE READING RECEIPT

- Preservation Standard：Preserve-and-Extend。
- Registry：已读取。
- Frozen Core：未命中；Registry当前条目未声明有效Freeze Contract。
- Frozen Shared Dependency：未修改，未命中。
- Affected Frozen Modules：`[]`。
- Unfreeze Authorization：`NOT REQUIRED`。
- Preflight：`SAFE TO MODIFY DOCUMENTATION ONLY`。
- Review Level：C。

## 三、有效指令集与控制单

|ID|状态|目的|持续边界|
|-|-|-|-|
|PCE-PB-A4-GIT-20260928|ACTIVE|建立Phase B Git源治理基线|不清理、不改源码/DB/C5、不进入业务开发|
|PCE-PB-C5|FROZEN USER FACT|C5 runtime validation PASS|本任务只核验Hash，不重跑、不修改|
|PCE-PB-READMISSION|ACTIVE BLOCKER|Phase B re-admission NOT READY|完成A4后仅进入Migration源图治理|

```text
INSTRUCTION CONTROL SHEET
Original Goal = 执行A4 Git源基线治理
Current Goal = 分类主工作区与集成工作树全部可枚举变更并冻结后续处置门禁
IN SCOPE = Git/文件系统只读快照、A-E分类、治理清单、FINAL报告
OUT OF SCOPE = 业务逻辑、C类源整改、Migration恢复、数据库、Router/Registry/权限、清理或提交
Frozen Facts = C5 PASS；正式数据库Hash；集成提交历史
Database Boundary = 只读Hash，不连接写入
User Acceptance Path = N/A
Stop Condition = 输出PARTIAL/PASS/BLOCKED并停止
```

## 四、当前Git状态

### 4.1 主工作区

- 路径：`D:\Dev-PCE\Source`
- 分支：`master`
- HEAD：`6058ee03022ac1f4ef7a40905aef32f0dd2e294e`
- HEAD时间：2026-09-01T14:05:24+08:00
- Git索引文件：16,760
- tracked changed：124；其中deleted 4
- untracked：31,696个可枚举文件
- tracked路径摘要：`53F03D836C34CDDC83C3F614C2966D3ACC31A42E1517C21E5B95F7045851225A`
- untracked路径摘要：`3C35D998730039615C418AF863AECF2190143A9BB5D2FDEEAA44E26F270F08A5`

### 4.2 集成工作树

- 路径：`C:\Users\DAODA\.codex\worktrees\manufacturing-baseline-convergence\Source`
- 分支：`codex/manufacturing-baseline-convergence-20260927`
- HEAD：`969a86fe4a1b8557e8c837d19c58e9a9cc5d8fba`
- HEAD时间：2026-09-27T22:22:59+08:00
- Git索引文件：20,375
- tracked changed：63；全部为缓存/运行产物
- untracked：1,213；主要为测试结果及两份治理报告
- tracked路径摘要：`C7AA1515A71F60FE7EA55842AA52B43D9B27384EA3FFBFE425DCAB5BEFADE106`
- untracked路径摘要：`3274AA9C5BCE4B6B01C4E529CCEC380A3D27FBBD4E3DF3B06C64BDD734717011`

由于Windows权限和超长路径，部分真实会话临时目录不能被Git完整枚举；因此文件计数是可审计下限。该不确定性禁止总体PASS。

## 五、文件分类结果

主工作区untracked全量目录级分类：

|类别|数量|已在集成HEAD|未在集成HEAD|结论|
|-|-:|-:|-:|-|
|A 正式源码候选|2,273|2,267|6|大部分已收敛；6项需单独决策|
|B 测试证据|6,971|739|6,232|保留，需Manifest化归档|
|C 运行产物|19,033|0|19,033|不得作为正式源码|
|D 临时/未归属|3,252|532|2,720|待确认，不删除|
|E 历史实验/非权威|167|58|109|保留追溯，禁止进入权威路径|

主工作区124项tracked变化中，95项与集成HEAD字节一致，3项删除已在集成HEAD体现，26项不同。不同项主要是数据库、Python/Vite缓存；正式源码差异只有集成Phase A增量扩展的settings/PDE/PLAN模型，必须保留集成语义。

完整目录级明细与关键文件Hash见同目录《Phase B Git源基线治理清单 20260928.md》。

## 六、正式源码清单

可以作为未来权威候选的不是当前脏工作树，而是可追踪提交链：

```text
master 6058ee03
  ├─ current authority dfc39010
  ├─ Phase A evidence ee4838ff
  └─ convergence c4a3c81d → governance bd7af566 → checkpoint 969a86fe
```

正式源码候选包括后端领域源码、前端`src`、受控scripts、package契约及Migration源码。主工作区中已与集成HEAD相同的文件不得再次复制；Phase A增量不得被主工作区旧文件覆盖。

未进入集成HEAD的五个真实候选是C5生成器、C5 README/Manifest、credential governance测试和canary目录占位；另一个路径是历史备份，不属于权威源码。

## 七、测试证据清单

测试证据主要分布于：

- `frontend/test-results/**`；
- `docs/evidence/**`；
- `docs/governance/**`；
- `frontend/tests/**`；
- `test-results/**`。

它们必须保留，但应与生产源码分层。未带Manifest/Hash/责任人的普通运行输出不得自动进入正式提交；已用于Gate的权威检查点必须按小白名单管理。

C5当前权威资产：

- generator：`28065D526A9AE1538B3EDD6170025DDA56C81280A1D596887AB8DF66B4868F9A`；
- README：`EDD0872B5D4FED819D920C51AD4994990579C86767A9241765164486E23A34E2`；
- Manifest：`826C6266631A2A4A5E16C45EF547F08900AD92D01EE3013E6C84E4E4E8035BA4`；
- SQLite基线及主工作区Gate输入：`0840A70E7D2F3965FCFC038977841D9BABC0354101B5C7CCE14F89552FC39F67`，888,832 bytes。

这些资产当前未形成与集成HEAD一致的Git原子包，是本次PARTIAL的核心原因之一。

## 八、运行产物与历史实验清单

### 8.1 运行产物

- `.runtime/**`约19,000级文件；
- `work/**`真实会话和Vite构建目录；
- Python `__pycache__`/`*.pyc`；
- `frontend/node_modules/.vite/**`；
- 各类dist/build/cache/log/sqlite。

集成HEAD自身已经错误追踪14,130个`frontend/node_modules`文件、110个pycache/pyc、一个`backend/db.sqlite3`和9个测试结果文件。`.gitignore`对已跟踪文件无效，必须由后续受控索引治理解决；本任务没有删除或停止追踪。

### 8.2 历史实验/非权威实现

重点对象：`manufacturingFoundationStore`、`manufacturingSampleDataFactory`、`foundationImportExport`、`scmMockDataGenerator`、legacy adapters、`PurchaseOrderList copy.vue`、历史backup和多套验收构建副本。

它们可能仍被当前运行依赖，因此仅标记E类并保持原样；不得解释为A1/A2或C类源隔离整改已完成。

## 九、保留/归档/待确认建议

|对象|当前处置|后续建议|
|-|-|-|
|集成提交链|保留|作为唯一合并历史，不重写|
|95项已匹配源码与3项已捕获删除|保留|不再从主工作区复制|
|C5 generator/README/Manifest|待确认|以原子包评审后纳入受控提交|
|C5 SQLite|保留隔离|明确可复现生成/安装合同，不作为业务库|
|测试证据|保留|外部归档或Manifest白名单|
|已跟踪node_modules/pycache/db|待确认|另行授权后仅停止Git追踪，不删除用户文件|
|`.runtime`/`work`/普通test-results|待确认|补ignore与证据保留策略|
|legacy/sample/重复入口|保留冻结|后续C类源隔离任务处理|
|Migration文件分支/删除|冻结|进入下一阶段Migration源图治理|

## 十、数据库保护结果

- 正式保护数据库：`D:\Dev-PCE\Acceptance\PDE-Operable-20260912\pde-operable-acceptance.sqlite3`
- 长度：31,481,856 bytes
- SHA256前后：`734F5B7D4D2A345F925DC5E06B61FA46CF4F068E91362389A59E33C8732FEE7D`
- 数据库写入：0
- Migration执行：0
- Schema改变：0
- 正式业务数据改变：0

## 十一、C5保护结果

用户给定事实 `C5 RUNTIME VALIDATION = PASS` 保持，不在本任务重跑或撤销。C5 SQLite、generator、README、Manifest的Hash均保持不变；没有修改C5脚本、Gate、断言或数据库内容。

但Git可复现性仍未完成：集成HEAD中的旧`backend/db.sqlite3` Hash为`22AA5F7B...11907`，与当前C5 PASS基线`0840A70E...39F67`不同；C5生成器/Manifest/README也未进入集成HEAD。该差异属于Git源治理阻断，不等于C5运行结果失败。

`C5 RUNTIME FACT = PRESERVED`

## 十二、下一阶段建议

1. 按用户指令进入《Phase B Migration源图治理执行指令》，只审计Migration来源、编号、依赖和多叶冲突，不执行业务开发或Migration。
2. 另行建立Git索引治理授权：确认停止追踪node_modules/pycache/db的精确清单，保留磁盘文件，不使用clean/reset。
3. 对C5三份源文件与生成器做原子包评审，决定可复现基线的提交方式；SQLite保持非业务、非正式数据边界。
4. 在上述决策完成前，不从任何脏工作树直接开始Phase B API/页面/权限开发。

## 十三、最终合规矩阵

|Compliance Item|Result|Evidence / Note|
|-|-|-|
|Original Goal|PARTIAL|分类完成；干净可复现Git提交尚未形成|
|Governance Reading Receipt|PASS|六份必读文件与Preflight|
|Scope / Stop Condition|PASS|只读审计+两份治理文档|
|Existing Results Preserved|PASS|未覆盖、删除或回滚|
|Automated Tests|N/A|不改代码；C5不重跑|
|User-Visible Real Path|N/A|非UI任务|
|Non-Regression|PASS|HEAD、C5 Hash、正式库Hash保持|
|Production Boundary|PASS|写入0、Migration 0|
|Report vs User Reality Conflict|NONE|接受用户C5 PASS事实，单列Git可复现差异|
|Final Stop Condition|PASS|仅建议进入Migration源图治理|

## 十四、最终状态

```text
GIT SOURCE BASELINE GOVERNANCE = PARTIAL
CLASSIFICATION SNAPSHOT = COMPLETE
SINGLE CLEAN SOURCE BASELINE = NOT YET ESTABLISHED
C5 RUNTIME FACT = PRESERVED
PHASE B BUSINESS DEVELOPMENT = NOT AUTHORIZED
NEXT = PHASE B MIGRATION SOURCE GRAPH GOVERNANCE
```

`DELIVERED USER STATE = NOT APPLICABLE`
