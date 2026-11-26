# FINAL CONSOLIDATED — Wave 1 Minimal Closure, 2026-09-11

最新指令：`WAVE1-IMPORT-MINIMAL-EVIDENCE-BUILD-CLEANUP-CLOSURE-20260911-001`。本节替代下方旧报告的当前结论，旧事实不删除。原报告另完整保存在 `evidence/wave1-final-closure-20260911/history/FINAL_BEFORE_MINIMAL_CLOSURE.md`。

## 最新结论

**三代表人工 PASS 保留；原文件零新增重放补证 PASS；运行归属和安全处置 PASS；本轮完整 npm run build Exit 1，不能 CLOSED。**

未修改产品业务、认证、Actor、导入核心、模板、解析器、模型、Migration、测试断言或构建输入；未重新首次导入、删除样例或更换样例。没有自动展开下一主线。

## 1. Reading Receipt 与版本锁

完整读取项目两级 AGENTS、有效 CODEX 规范 V1.2、固化与保护规范、当前模块台账、Preflight、相关模板/Actor 契约、原文件与首次审计、A4/B4/C4 交接、前轮报告及实际启动/正式清理入口。详见同一 evidence 目录 `CLOSURE_READING_RECEIPT.md`。

前轮交付清单 42 项全部核验一致，原 ZIP SHA-256：`4745EEFE2FD5DB9A085E42261650B75CBEB676F5EAECF0FC44D575E421E9327F`。

当前实际 dirty/untracked 工作树 66 项相关源码、依赖、配置、测试及原样例逐项 SHA-256：`CLOSURE_FINAL_SOURCE_LOCK.json`。清单指纹 `7f95d26842538d6b2e69c0fbaaf7f4be6c72539005a6e37b272fd6c3fdb3c8e5`；补证前后与验证后全部一致，不以 Git HEAD 代替。当前台账无 FROZEN_VERIFIED，未变更模块治理状态；Operation 独立保护标记和 Routing 家族语义保留。

## 2. 人工、首次导入、当前读回与自动重放

| 对象 | 用户人工裁决 | 唯一原业务身份 / PK | 首次审计 | 本轮补证前→后总数 | 自动补证 |
|---|---|---|---|---:|---|
| Customer A4 | PASS，含用户明确 Commit/读回/Replay PASS | W1-A4-CUST-20260911 / 91 | 2447，20:20:29 | 91→91 | Preview CREATE=0/MATCH=1；Commit 201，created=0/matched=1 |
| Material B4 | 人工导入 PASS | W1-B4-MAT-20260911 / 273 | 2448，20:34:03 | 271→271 | Preview CREATE=0/MATCH=1；Commit 201，created=0/matched=1 |
| Workshop C4 | 人工导入 PASS | W1-C4-WS-20260911 / 4 | 2449，20:35:31 | 4→4 | Preview CREATE=0/MATCH=1；Commit 201，created=0/matched=1 |

时间均为 2026-09-11 +08:00。首次提交、原文件指纹及写入后的字段来自原审计和只读回读；人工结果来自用户。B4/C4 未被扩写为用户亲自执行过具体次数的历史 Replay。

Customer 当前 91 = 原 89 + A3（PK90，audit2446，20:12:19）+ A4（PK91）。A3 来源为 A3 文件，其具体操作者属于人工还是自动没有充分记录，不再称为“自动 preflight”。用户原 89→90→90 观察作为历史人工原文保留，不作为当前服务器总数。A3/A4 均保留，各一条。

历史请求只有 actor/outcome，不能把 20:13 Customer 请求归入尚未首次创建的 A4；B4/C4 第二次成功请求也缺文件和返回数量关联。这一历史限制保留。本轮按新授权对三个原文件**各一次**正式 HTTP 登录后的 Preview→Commit→API 读回，明确标注 `AUTOMATED CLOSURE SUPPLEMENT`。

实际补证时间及请求关联：A4 22:10:18，`W1-CLOSURE-20260911-A4-1789135818`；B4 22:10:19，`W1-CLOSURE-20260911-B4-1789135819`；C4 22:10:19，`W1-CLOSURE-20260911-C4-1789135819`。完整脱敏请求字段、HTTP 返回、Actor/DB、原审计关联和 API 返回正文见 `CLOSURE_REPLAY_RESULTS.json`，服务端新轨迹见 `CLOSURE_ACTUAL_HTTP_TRACE.jsonl`，未改写旧请求日志。

三项 Preview fingerprint 均再次匹配原首次审计；API 中可读回同一身份。每个对象全表排序快照 SHA 前后相同，逐业务身份及字段相同。原 A4 验收库业务新增/更新/删除各 0；该库新增业务审计 0，成功 Commit 请求轨迹 3 条。正式登录产生的隔离会话及账号失效写入另计，不冒充业务零写入。

## 3. 原文件完整 SHA-256

| 原文件 | SHA-256 |
|---|---|
| A4-客户人工导入样例.xlsx | `134A674C0E4F04AE801F92D9900570EE87DD3400081452724DF7EDE67B4BB603` |
| B4-物料人工导入样例.xlsx | `68E5B866EA6ABE4759C06C790B896885D359B63B85E80C2C1341648EE19A82E8` |
| C4-车间人工导入样例.xlsx | `A90316CFC655E6405D58AEE8221C54BDF717599CAFE091735CF6C80D9F1E17F1` |

Actor-bound Preview fingerprints依次为 `6cb6be194573ab9259e0ab415bb11dca8dce65ddcfa8bcac49e027ecf10664d6`、`eca0dcdad71d061795bb71667391471bbf25c03c3ec663fdbc027f74f5d1536b`、`6e1bf7f2ec09fd5d839db5bcd41287a451d13068e89e35df1ae8d8d0a9bb488c`。

## 4. 当前运行归属及最终安全处置

`CLOSURE_RUNTIME_OWNERSHIP.json` 标记 `RECONSTRUCTED FROM CURRENT OBSERVATIONS`，不是原始 Run Manifest。依据实际 PID/创建时间/命令行/父子关系、前端启动日志和 runtime identity、原 exec session33613 的实际请求、直接与代理 HTTP 的同一 DB/Actor 响应共同确认，不靠端口或新清单自证。

真实隔离库仍为 `D:\Dev-PCE\work\wave1_actor_binding_manual_a4_20260911_001.sqlite3`，alias default；binding ID `64da9580-46d1-4241-9c33-a3a5ac351f0e`；DB context `6a95418e89efd1a05526252787ea36cb8990f69280ec1b9325245108a881bce0`。

原后端 PID66500/父59020 在19:40启动，但锁定 Actor 源文件最后修改19:48。保存证据后，原会话正常中断；22:10:15 仅重启已确认服务（启动 PID62676），同一数据库、同一代码锁，完成正式登录与补证后停止。原前端 PID64020 及已逐个核验的启动父链11880/64448/58924已停止。最终5173/5174/8000无 LISTENING；上述进程及构建 runner 已不存在。

Maintenance14/Read-only15均停用且密码不可用；本次 Employee109 inactive、Position36 disabled、Responsibility57 suspended，相关 scope/position mappings停用；2条会话都先证明属于User14后删除。真实旧 JWT、旧 Session Cookie、原维护密码再次请求分别返回401。只读账号同样不可认证；正式登录没有独立 refresh token，JWT认证每次检查 active user。原有员工/岗位/职责未修改；测试部门等仍被 C4 引用的记录保留，不删除业务引用。详见 `CLOSURE_IDENTITY_CLEANUP.json`。

用户 Chrome/Codex 主进程在05时已启动，不属于本次 owned runner，未关闭或删 Profile。本轮构建创建的独立浏览器 runner70280与Vite65384已退出；其隔离Profile按现有清理合同**实际删除**，现场确认不存在。更早一轮“Profile删除受策略阻止”仅保留为历史，不冒充本轮结果。外部构建缓存/安全测试临时目录保留为诊断材料；定向真实Session测试留下的两个测试数据库亦已按其Bootstrap run ID停用测试身份并清除会话，原地保留，不涉及A4业务库。详见 `CLOSURE_TEST_RESIDUAL_DISPOSITION.json`。本轮未绕过任何删除策略。

原A4库停机原地封存，最终SHA-256 `140CA6567904322027855452A2CBFFF85CC526D87AEFB1D391DFAA36D1D78300`；变化来自授权的隔离登录与身份/Session清理。业务全表指纹不变。数据库未覆盖、恢复、删除或改换，A3/A4/B4/C4均保留。

## 5. 最终版本验证与真实 Build 失败

| 命令 | 本地开始→结束 | PID | 真实 Exit |
|---|---|---:|---:|
| npm run verify:pce-formal-import-actor-context | 22:11:07→22:11:47 | 64128 | 0 |
| npm run verify:pce-formal-import-backend-continuity | 22:11:47→22:11:51 | 73632 | 0 |
| npm run build（包含npm自动prebuild） | 22:11:51→22:15:00 | 4212 | **1** |

Actor定向门禁包含14项Actor断言及真实HTTP登录/Session、Commit、Replay、只读403、跨库JWT失效测试。测试使用内存测试库和独立临时副本，不是Production或A4业务库；测试fixture自身的创建不能算作原A4库业务写入0，也没有作为新的人工样例交付。

完整Build在既有 `prebuild → verify:pce-operation-column-layout` 停止：`incoming-inspections-main` 于 `pceOperationColumnLayout.spec.js:163` 的 `page.goto(.../#/qms/incoming-inspections)` 等待domcontentloaded超45,000ms；同组 `payment-execution-prepare-list` PASS，合计1失败/1通过。尚未运行到主build链后续门禁或vite产物编译，不能声称全部门禁已通过。日志另见已停止8000的ECONNREFUSED，不能仅据此断定导航超时的唯一原因，也不把未完成页面加载误判为已证明布局回归。

没有改断言、放宽超时、跳过失败或再次构建。`CLOSURE_BUILD_EXECUTION.json`含完整命令、时间、PID、退出码、完整日志哈希和已有产物指纹（明确是旧产物，不是本轮成功Build）。`CLOSURE_full-build.log`完整SHA-256：`ED1DB0FA26C0F807AB7DFD76AE31066C6A1E21327E062D20D6D0E880A43BFA98`。失败Trace及Error Context保存在 `current-build-failure/`。

最后已记录的完整Exit0仍是历史19:06构建，日志SHA `F1432BBB1F7F0B44CE57821181AA1DF6353806B42F226224CAB30160811D602F`；它早于身份绑定修改，不能覆盖当前版本。本轮未获得完整Exit0。

## 6. 九对象采用状态与能力基线

| 对象 | 当前未筛选DB总数 | 人工覆盖 | 本轮采用状态 |
|---|---:|---|---|
| Customer | 91 | 原数据/模板PASS；A4人工PASS；本轮原文件重放PASS | 不升级：当前完整Build未通过 |
| Supplier | 121 | 原数据/模板PASS；约定代表覆盖 | 不升级：当前完整Build未通过 |
| Material | 271 | 原数据/模板PASS；B4人工PASS；本轮原文件重放PASS | 不升级：当前完整Build未通过 |
| Product Definition | 0 | LOADED_EMPTY人工PASS；约定代表覆盖 | 不升级：当前完整Build未通过 |
| Workshop | 4 | 原数据/模板PASS；C4人工PASS；本轮原文件重放PASS | 不升级：当前完整Build未通过 |
| Operation | 33 | 原数据/模板PASS；约定代表覆盖 | 不升级；独立Protected Baseline保留 |
| WorkCenter | 0 | LOADED_EMPTY人工PASS；约定代表覆盖 | 不升级：当前完整Build未通过 |
| Equipment | 0 | LOADED_EMPTY人工PASS；约定代表覆盖 | 不升级：当前完整Build未通过 |
| Standard Capacity | 0 | LOADED_EMPTY人工PASS；约定代表覆盖 | 不升级：当前完整Build未通过 |

九对象历史自动证据仍为 `actor-nine-xlsx-runtime.log` 的9对象Schema/XLSX/Preview/写入/审计/读回/Replay匹配检查，以及历史19项backend regression；并非本轮重新执行九对象首次导入。保留真实版本边界：Schema V1.0、Actor V1.0、Auth DB Context V1、Latest Template V1.0；本轮最终66项源码清单与定向验证建立当前关联，不能把历史九对象记录改名为本轮完整E2E通过。

现有唯一机器采用矩阵未改，其历史 `ADOPTING_IMPORT_ACTOR_CONTEXT_BLOCKED` 标签**不代表最新Actor仍失败或用户未验收**；现有文档矩阵写入最新真实缺口。另有明确静态障碍：`verifyPceLatestBaseDataTemplateAdoption.mjs`无条件要求九对象等于该旧状态。转ADOPTED需要处理此门禁，但本轮禁止修改测试断言，因此未改、未绕过。ADOPTED新增0；Completed Module Registry及整个供应商/采购/订单/生产模块治理状态不变。

成果原位保存：`LATEST_BASE_DATA_TEMPLATE_CONTRACT.md`、`ORDER_PRODUCTION_BASE_DATA_TEMPLATE_ADOPTION_MATRIX.md`、`LATEST_TEMPLATE_FULL_CAPABILITY_MATRIX.md`、`WAVE1_IMPORT_CAPABILITY_STATUS.md`与既有`WAVE1_CAPABILITY_PRESERVATION_MATRIX.md`。中文工作表/表头/业务值、XLSX/CSV分流、用户可见校验/Preview/确认、正式Actor、写入/审计/读回、幂等、单行与表头全选分离、搜索/高级筛选/排序/导出/分页/流程导航/横向滚动均保留既有能力及人工结果；不新建第二套模板或台账。对应实现/共享依赖/测试真实SHA引用见源码锁及历史清单。以后基础数据应继承现有完整契约，不降级成精简页面。

## 7. Production、Git、剩余项与下一主线

Production前后SHA-256均为 `CF6054C87C84FD07273FD6F042A195E85D2F659451208711A9407214CF9365C7`。Business / Import / Audit / Auth / Session / Employee / Position / Responsibility / Permission / Migration / Recovery写入**逐项0**；没有生产导入或发布授权。

Git HEAD `6058ee03022ac1f4ef7a40905aef32f0dd2e294e`；最终观察111项tracked dirty、1201项untracked，不能全部归因本轮。保留用户原工作树。Git Commit/Push/Reset/Clean均未执行。当前锁定66项产品、配置、测试、样例无变化；本轮只增加外部包装、验证产物和报告证据。

剩余工作明确收敛为**最终验证/采用门禁**，有两个具体条件，不能合并掩盖：

1. 当前完整Build在既有来料检验导航加载超时退出1，必须有合格的最终版本完整Exit0证据。
2. 现有采用门禁硬编码旧Actor阻断状态，与允许ADOPTED的结案条件冲突；如需修改该断言，须另行明确授权，本轮不扩权。

原三个缺口中的原文件重放关联、运行归属/身份清理均已解决；不再要求重做人工验收、首次导入或更换样例。当前异常停止，不能关闭Wave1。

下一业务主线仅提出：选定一张**已有真实全屋定制/整木订单**，只读核实接单前置、订单版本/客户/明细及必要产品、BOM/物料引用，再在明确授权后进入该订单物料核算闭环；不以完善全部27模块为前提。本轮未实际开展新开发或生产写入。

## 8. 可审查交付

本正文、当前证据、历史报告、脱敏实际HTTP结果、完整构建日志/失败Trace与逐文件SHA清单打包为 `WAVE1_IMPORT_MINIMAL_CLOSURE_20260911.zip`，并提供独立可阅读 `FINAL_CONSOLIDATED.md` 和 `DELIVERY_SHA256.txt`。所有文件的完整SHA-256在包内SHA256清单，交付文件完整SHA在外置DELIVERY_SHA256，避免自身哈希循环引用。没有将密码、Token、Cookie或数据库密码哈希放入本次报告/证据包。

```text
USER MANUAL REPRESENTATIVE IMPORT VALIDATION = PASS
REPLAY EVIDENCE CLOSURE = PASS
FINAL SOURCE BUILD = FAIL (npm run build Exit 1)
ISOLATED BUSINESS CREATES DURING CLOSURE = 0 (ORIGINAL A4 ACCEPTANCE DB)
RUNTIME OWNERSHIP AND SAFE DISPOSITION = PASS
ADOPTED MODULES = NONE (NO NEW UPGRADES)
OPERATION PROTECTED BASELINE = PRESERVED
PRODUCTION WRITES = 0
PRODUCTION IMPORT EXECUTED = NO
REMAINING GAPS = FINAL_BUILD_NAVIGATION_TIMEOUT; HARDCODED_ADOPTION_GATE
WAVE1 IMPORT CLOSURE = BLOCKED — NOT CLOSED
```

---

# 历史报告（下文不是本轮当前状态）：Wave 1 Import Final Closure

指令：`WAVE1-LATEST-TEMPLATE-IMPORT-FINAL-CLOSURE-20260911-001`。日期：2026-09-11。性质：FINAL CLOSURE ONLY。Review Level C。

## 本轮裁决

Customer A4、Material B4、Workshop C4 的用户人工导入结果均正式登记为 PASS。历史 B4/C4 READY 与 IMPORT BACKEND PENDING 是操作前状态，不能覆盖此裁决。

本轮到达异常停止点，未宣布 CLOSED。三项原文件与首次写入审计的指纹逐一一致，原业务身份各一条；但现有记录不足以完整关联同文件重放，当前 Run Manifest 未找到，且可定位完整 Build 日志早于身份绑定代码变更。以下仅列结案证据与运行处置缺口，已 PASS 的模板、中文化、Preview、Provider、Export、Filter 不重新开发或重验。

## 1. Reading Receipt / 控制单

`GOVERNANCE READING RECEIPT` 与 `COMPLETED MODULE GOVERNANCE READING RECEIPT`：

- 完整读取 `D:\Dev-PCE\AGENTS.md`、`D:\Dev-PCE\Source\AGENTS.md`。
- 完整读取 `docs/governance/PCE CODEX开发指令规范管理V1.2.md`，重点执行事实来源、用户裁决、版本一致性与最终可审查正文要求。
- 完整读取 `docs/governance/PCE 已开发模块固化与变更保护规范 V1.0.md`、`completed_module_registry.v1.json`、`COMPLETED_MODULE_PROTECTION_PREFLIGHT_V1.md`。
- 完整读取模板正式契约 `LATEST_BASE_DATA_TEMPLATE_CONTRACT.md` 及机器权威 `frontend/src/meta/contracts/latestBaseDataTemplateContract.js`。
- 完整读取现有采用矩阵 `ORDER_PRODUCTION_BASE_DATA_TEMPLATE_ADOPTION_MATRIX.md` 及机器权威 `frontend/src/meta/master-data/orderProductionBaseDataTemplateAdoption.js`。
- 完整读取 `MANUAL_CUSTOMER_ACTOR_HANDOFF.md`、`MANUAL_B4_C4_ACTOR_HANDOFF.md`、`FINAL_DB_ACTOR_BOOTSTRAP.md`、`REAL_HTTP_IMPORT_ACTOR_TRACE.md`、上一份 `FINAL_CONSOLIDATED.md` 及其 SHA 清单。
- 读取现有九对象 runtime、XLSX、中文化、幂等、能力保留、Data Continuity 人工记录和完整 Build 记录；大体积 Build 日志仅定向核查，不声称逐行全文审计。
- 当前 A4 Run Manifest：在项目 work、Source/work、当前任务目录及 pce-runtime 范围搜索（含 ignored/hidden 名称）未找到。Bootstrap 审计与交接文件存在，但不冒充进程运行清单。
- Preservation Standard Read = YES；Completed Module Registry Read = YES；Affected Frozen Modules = NONE；Freeze Contracts Read = N/A（当前台账无 FROZEN_VERIFIED）；Unfreeze Authorization = NOT REQUIRED FOR REPORTS。
- Preflight = SAFE TO MODIFY（仅报告、证据文件）；产品源码/机器采用状态未修改。
- 有效指令集：本次结案指令 ACTIVE；A4/B4/C4 用户 PASS 生效；此前标准能力 PASS 持续保护；旧交接状态历史保留；生产零写入和 Git 禁止动作持续生效。
- 单一目标为结案；多于十份输入是用户指定的既有证据合并，不扩展全工程历史审计。没有创建第二套台账或模板。
- 异常停止依据：本指令第十一节“业务身份不一致”“无法证明重放结果”“代码与测试版本不一致”“清理对象身份不明”。当前只归档结果，不执行重新导入或不明对象清理。

## 2. 当前可回读的隔离证据

证据库：`D:\Dev-PCE\work\wave1_actor_binding_manual_a4_20260911_001.sqlite3`，以 SQLite `mode=ro` 打开。该路径由本轮实际请求轨迹与库内 Bootstrap 审计共同印证；尚缺 Run Manifest 对当前服务进程的绑定，因此不把它描述成已完成运行身份核验。

- Bootstrap audit 2445：Run `W1FI-A4-MANUAL-20260911-001`；databaseBindingId `64da9580-46d1-4241-9c33-a3a5ac351f0e`。
- 当前请求 DB context：`6a95418e89efd1a05526252787ea36cb8990f69280ec1b9325245108a881bce0`。
- Maintenance User 14、Read-only User 15；Employee 109、Position 36、Responsibility 57、Role 18、organization 1。
- 读前与读后隔离库 SHA：`000FF79573F3972C0BB6AF818D19D6AED779A738D29C7BA28912844A715A5CE0`，一致。
- 原始捕获：`evidence/wave1-final-closure-20260911/wave1-final-closure-readback.json`；文件/审计关联：同目录 `wave1-final-closure-correlations.json`。

## 3. 三代表人工结果、首次提交与实际数量

| 对象 | 用户最新裁决 | 原文件业务身份 | 首次写入证据 | 本轮未筛选 DB 总数 | 此身份条数 |
|---|---|---|---|---:|---:|
| Customer A4 | PASS（含用户明确的 Commit/读回/Replay PASS） | W1-A4-CUST-20260911 | audit 2447 / PK 91 / 20:20:29 | 91 | 1 |
| Material B4 | 人工导入 PASS | W1-B4-MAT-20260911 | audit 2448 / PK 273 / 20:34:03 | 271 | 1 |
| Workshop C4 | 人工导入 PASS | W1-C4-WS-20260911 | audit 2449 / PK 4 / 20:35:31 | 4 | 1 |

时间为本地 +08:00。首次审计保存文件名、XLSX 类型、Schema V1.0、Preview fingerprint、完整 actor、授权 ALLOWED、空 before state 与已创建 after state。以冻结原文件字节和同一 actor binding 重新计算 fingerprint，三者均与首次审计完全一致。

Material 的交接基线 270 → 当前 271，Workshop 3 → 当前 4。当前数据与首次审计及原样例字段一致。此处是数据库与已保存审计回读，不冒充本轮重新访问页面/API。三项用户可见结论来自用户裁决；本轮未取得新的 API 响应正文。

Customer 数量差异：库中另有 `W1-A3-CUST-20260911`（PK 90），audit 2446 在 20:12:19 创建，来源明确为 A3 文件；A4 是之后 20:20:29 创建。故当前完整总数是 89 基线 + A3 一条 + A4 一条 = 91。先前报告把 A3 称作已验证的“自动 preflight”及把全部 Customer 成功请求归为 A4 的表述无充分依据，应撤销该归属推断。用户记录的 89 → 90、Replay 90 原文保留，但不能作为当前服务端总数。未删除 A3/A4 或改写数量。

## 4. 重放证据与自动补证

| 对象 | 已保存成功请求 | 能证明的事实 | 未能证明的具体内容 |
|---|---|---|---|
| A4 | 最终 context 的 Customer 请求为 20:12:19、20:13:18、20:20:29 | A3 首次审计在 20:12；A4 首次审计在 20:20；A4 当前唯一 | 没有 A4 首次创建之后的 Customer Commit 轨迹；不能把 20:13 请求归属 A4 Replay |
| B4 | materials 20:34:03、20:34:39 均 PASS | 第一次与 audit 2448 一致；第二次成功；当前 B4 一条 | 第二次 trace 未保存文件指纹/业务身份/created/matched/总数；没有可定位完整响应正文 |
| C4 | workshops 20:35:31、20:35:42 均 PASS | 第一次与 audit 2449 一致；第二次成功；当前 C4 一条 | 第二次 trace 同样未保存文件指纹/业务身份/created/matched/总数 |

追踪实现 `formal_import_views.py` 只将 actorContext 与 outcome 写入 JSONL，未保存 Commit 结果的上述字段；MATCH 分支不新增写入审计。因此不能把两次成功请求擅自扩写为“已证明同文件 CREATE=0/MATCH=1”。这属于结案证据关联缺口，不等于发现重复创建或撤销用户人工 PASS。

`AUTOMATED CLOSURE SUPPLEMENT = NOT EXECUTED`。本指令只允许在原运行环境已确认后对 B4/C4 缺失重放各补一次；Run Manifest/进程 ownership 未确认，所以未进入补证写入。A4 自动补重放不在此授权范围。新增业务记录 0，原业务身份与数据均未改动。

## 5. 九对象自动验证版本与逐页采用判断

现存 `actor-nine-xlsx-runtime.log` 记录九对象 Template/XLSX/Preview/Commit/readback/replayMatch PASS，隔离写入 9、审计 9、只读拒绝与批次原子回滚 PASS；`actor-backend-regression.log` 记录 19 tests OK。运行库是 `wave1_actor_runtime_20260911_001.sqlite3`，不是此次人工库。

合同版本：`WAVE1-FORMAL-IMPORT-SCHEMA-V1.0`、`WAVE1-FORMAL-IMPORT-ACTOR-CONTEXT-V1.0`、`PCE-AUTH-DB-CONTEXT-V1`、`PCE-LATEST-BASE-DATA-TEMPLATE-V1.0`。历史九对象 PASS 不自动证明后续修改版本已完整验证；当前 28 项交接哈希全部匹配，但缺少最后身份绑定修改后与完整 Build 绑定的源码清单/日志。

| 页面 | 当前 DB 总数 | 已有覆盖 | 本轮采用判定及剩余缺口 |
|---|---:|---|---|
| Customer | 91 | 自动 + A4 人工 PASS | 未升级 ADOPTED；A4 重放归属/计数证据差异、最终版本证据 |
| Supplier | 121 | 九对象自动 + 既有数据/模板人工 + 代表覆盖 | 未升级；代表重放证据及最终版本证据未完整 |
| Material | 271 | 自动 + B4 人工 PASS | 未升级；第二次请求的同文件结果关联、最终版本证据 |
| Product Definition | 0 | 自动 + 正式空集合/模板人工 + 代表覆盖 | 未升级；代表重放证据及最终版本证据未完整 |
| Workshop | 4 | 自动 + C4 人工 PASS | 未升级；第二次请求的同文件结果关联、最终版本证据 |
| Operation | 33 | 自动 + 既有数据/模板人工 + 代表覆盖 | 未升级；代表重放证据及最终版本证据；Protected Baseline 保留 |
| WorkCenter | 0 | 自动 + 正式空集合/模板人工 + 代表覆盖 | 未升级；代表重放证据及最终版本证据未完整 |
| Equipment | 0 | 自动 + 正式空集合/模板人工 + 代表覆盖 | 未升级；代表重放证据及最终版本证据未完整 |
| Standard Capacity | 0 | 自动 + 正式空集合/模板人工 + 代表覆盖 | 未升级；代表重放证据及最终版本证据未完整 |

现有机器采用矩阵仍含历史 `ADOPTING_IMPORT_ACTOR_CONTEXT_BLOCKED`；本轮异常停止未改运行输入或相关门禁，不把它解释成最新人工失败。现有文档矩阵追加本轮裁决和具体缺口，未建立第二份机器台账。待结案证据完整后，仍需原位更新机器状态与受影响门禁；这项工作明确未完成。

## 6. 标准能力保存、Operation 与范围

现有契约、`LATEST_TEMPLATE_FULL_CAPABILITY_MATRIX.md`、`WAVE1_CAPABILITY_PRESERVATION_MATRIX.md`、`WAVE1_USER_MANUAL_ACCEPTANCE.md` 保存中文工作表/表头/业务值、XLSX/CSV 分流、可见校验与 Preview、显式确认、正式 actor、写入/审计/读回、幂等、单行选择/表头全选分离、搜索/高级筛选/排序/导出/分页/流程导航/固定列/横向滚动证据。本轮补入新的人工裁决和结案证据边界，不改变能力实现。

Operation `protectedBaseline=true` 原样保留；Routing / Routing Version / Routing Step 不变。页面 ADOPTED 与整个业务模块 FROZEN 分离，Completed Module Registry 未改；供应商/采购流程、订单/生产整体完成、生产导入与生产发布均未作新增声明或授权。

## 7. 最后完整 Build 与版本一致性

可定位的最后完整日志：当前任务 `work/full-build-actor-context-retry.log`（输出副本 `outputs/full-build-actor-context.log`），185749118 bytes，最后写入 2026-09-11 19:06:11 +08:00，末尾 `built in 8.93s`。前轮正式报告记录 `npm run build Exit 0`。日志 SHA-256：`F1432BBB1F7F0B44CE57821181AA1DF6353806B42F226224CAB30160811D602F`。

后续文件修改时间：JWT auth 19:23:16；import service 19:24:28；前端 API/Toolbar 19:25；package.json 19:30；import views/tests 19:34；identity_context.py 19:39:59。该完整日志包含 actor-context gate，但不含后来新增的 `verify:pce-formal-import-real-session-actor`。未找到可以替代它的更晚完整日志或绑定源码树证明，故“旧 Build 覆盖当前版本”不能确认。

本轮没有改产品源码、认证、导入核心、共享模板或机器状态，没有重新 Build 或重跑整套前端测试。历史 Exit 0 保留为历史结果，未冒充本轮执行。当前与上次交接 manifest 的 28 个文件哈希一致，也不能倒推出它们曾经过 19:06 那次 Build。

## 8. 隔离账号、Session/JWT、进程、端口、Profile

本轮实际读取的 Maintenance 14 与 Read-only 15 均仍 active，Django Session 数为 1。凭证逻辑失效：NOT EXECUTED；密码未修改；Session 未删除；JWT 未做失效验证，不能声称不可再认证。

当前 native 只读结果：5174 LISTENING 的 PID 为 64020，StartTime 14:26:40，路径 `D:\nodejs\node.exe`；8000 LISTENING 的 PID 为 66500，StartTime 19:40:20，路径 `D:\Dev-PCE\work\wave27_exact_runtime_20260903\python314\python.exe`。这些来自本轮 `netstat`/`Get-Process`，不是沿用历史 PID。`Get-CimInstance` 与 `Get-NetTCPConnection` 返回拒绝访问，缺少当前命令行与 Run ownership 链，不据端口直接杀进程。

现有 cleanup 函数会删除库内全部 Sessions，执行前还需核对本次 ownership；因运行清单缺失及异常停止，本轮未执行。既有员工、岗位、职责、角色、权限与组织均未修改。前后端/浏览器运行器未停止；Profile 未尝试删除，其实际路径与归属未证实。没有把历史 Profile 删除受阻当成本轮结果，也没有绕过 Sandbox。

隔离数据库保留原地，未删除、覆盖、迁移或重新导入；当前为证据保留，不宣称已完成停机封存。已复制只读证据与历史报告；服务仍可能继续运行，故封存状态为 PENDING_RUN_OWNERSHIP。

## 9. 生产保护与 Git

生产数据库 `D:\Dev-PCE\Source\backend\db.sqlite3` 本轮开始与结束 SHA-256 均为：

`CF6054C87C84FD07273FD6F042A195E85D2F659451208711A9407214CF9365C7`

Production Business / Import / Audit / Auth / Session / Employee / Position / Responsibility / Permission / Migration / Recovery Writes：各 0。本轮隔离业务写入、自动重放、身份清理写入也均为 0。

Git HEAD：`6058ee03022ac1f4ef7a40905aef32f0dd2e294e`。工作树原本 dirty：检查时 111 个 tracked 状态条目；另有现存 untracked 文件。未将这些变更归因于本轮。Commit / Push / Reset / Clean 均未执行。本轮只改报告、只读证据工具及交付包。

## 10. 交付、缺口与停止状态

历史 FINAL、A4、B4/C4 交接、采用矩阵和 SHA 清单原文保存在 `evidence/wave1-final-closure-20260911/history/`。新证据包含实际 DB 计数、原文件字节哈希、首次审计、文件/actor fingerprint 关联和原始脱敏请求 JSONL。最终正文与证据包交付至当前任务 outputs；完整文件哈希见随附 SHA256.txt。没有凭空创建 Run Manifest。

剩余工作仅三类：

1. 原文件重放证据关联：A4 首次之后的实际 Replay 记录；B4/C4 第二次请求的原文件 fingerprint 与 Commit 结果。现有成功轨迹与唯一业务记录不足以补造缺失字段。
2. 最后身份绑定修改后的验证/Build 版本证明及随后采用状态原位更新。保留旧完整 Build Exit 0，不替代当前版本验证。
3. 当前 Run Manifest 与运行资源 ownership；据此完成临时账号、Session/JWT、进程和 Profile 处置及隔离库封存。

恢复只需补足这些证据与处置条件；不要求重做首次导入、不要求新样例、不重开已通过能力。按第十一节异常停止点结束本轮。

```text
USER MANUAL REPRESENTATIVE IMPORT VALIDATION = PASS
FORMAL IMPORT BACKEND CLOSURE = BLOCKED_EVIDENCE
LATEST BASE DATA TEMPLATE FULL CAPABILITY = NOT FULLY CERTIFIED FOR CURRENT VERSION
ADOPTED MODULES = NONE (NO NEW UPGRADES)
REMAINING GAPS = REPLAY_CORRELATION; BUILD_VERSION_EVIDENCE; RUN_OWNERSHIP_AND_CLEANUP
OPERATION PROTECTED BASELINE = PRESERVED
PRODUCTION IMPORT EXECUTED = NO
WAVE1 IMPORT CLOSURE = BLOCKED (NOT CLOSED)
```

## 历史原文：A4 PASS / B4 C4 READY 交接（不代表当前裁决）

### FINAL CONSOLIDATED — Wave 1 Manual Actor Identity Binding Corrective

Instruction: `WAVE1-MANUAL-ACTOR-IDENTITY-BINDING-CORRECTIVE-20260911-001`  
Run: `W1FI-A4-MANUAL-20260911-001`

## Current decision

- Customer A4 manual validation: **PASS**.
- Material B4 and Workshop C4: **READY FOR MANUAL VALIDATION** under the same A4 actor/bootstrap.
- Actor cleanup: **DEFERRED** until both B4 and C4 manual validation and replay are complete.
- Formal Import Backend overall: **PENDING**; `ADOPTED = 0` and status remains `ADOPTING_IMPORT_BACKEND_PENDING`.
- Production business/auth/organization/import/migration writes: **0**.

## Governance receipt

Read: repository AGENTS instructions; Codex Governance V1.2; Completed Module Preservation Standard V1.0; completed-module registry; preflight; current corrective. Frozen affected modules: none. Unfreeze: not required. This continuation only recorded the user decision, generated B4/C4 samples from existing governed template bytes, performed read-only Preview readiness, and updated evidence. No passing XLSX schema/localization, Preview, Data Provider, Export, Filter, route, component, or runtime implementation was changed.

## Required 24 answers

1. Historical failed Commit `request.user`: exact username is **UNKNOWN** because the request predated tracing. The A4 real requests are durably traced.
2. Historical Login DB vs Commit DB: not directly recoverable. A4 Login/Preview/Commit is bound to one database instance and cannot cross DB.
3. Numeric drift: `CROSS-DATABASE NUMERIC IDENTITY DRIFT` was confirmed as the old design defect; numeric PK alone is no longer accepted across database contexts.
4. A4 username/stable identity: `wave1_import_maintenance_a4` / `system.User:wave1_import_maintenance_a4`.
5. Employee: 109 / `W1AC-A4-E1` / active.
6. Position: 36 / `W1AC-A4-20260911` / enabled and effective.
7. Responsibility: 57 / `W1AC-A4-20260911-RESP` / active and effective.
8. Customer permission: `masterdata.customer.maintain` = ALLOWED.
9. Organization: company/organization 1; scope `ORGANIZATION`.
10. Preview actor: stable username + organization + DB alias/instance context are included in the fingerprint and returned binding.
11. Commit actor: re-resolved from authenticated `request.user`; cached Employee/Position/Responsibility is never trusted. Mismatch returns precise HTTP 403 Chinese error.
12. Automated/manual bootstrap: YES, both use `bootstrap_rehearsal_actors`; B4/C4 do not create or modify another actor.
13. Customer A4 first Commit: **USER PASS**; user-visible count 89 → 90; identity `W1-A4-CUST-20260911` searchable.
14. Customer A4 Replay: **USER PASS**; Preview CREATE=0/MATCH=1; replay Commit PASS; user-visible count remains 90.
15. Material B4: READY; read-only Preview CREATE=1/MATCH=0 under A4 actor; expected 270 → 271.
16. Material Replay: USER PENDING; expected CREATE=0/MATCH=1 and count remains 271.
17. Workshop C4: READY; read-only Preview CREATE=1/MATCH=0 under A4 actor; expected 3 → 4.
18. Workshop Replay: USER PENDING; expected CREATE=0/MATCH=1 and count remains 4.
19. Read-only protection: Preview ALLOW; Commit HTTP 403 PASS.
20. Production writes: business/auth/User/Employee/Position/Responsibility/Permission/Session/import/migration = 0. Production SHA-256 `CF6054C87C84FD07273FD6F042A195E85D2F659451208711A9407214CF9365C7` unchanged.
21. Build: prior `npm run build` Exit 0 remains valid; this continuation changed only helper scripts, samples, and evidence documents.
22. User Manual Final: Customer A4 PASS; B4/C4 PENDING; ADOPTED=0 and status remains `ADOPTING_IMPORT_BACKEND_PENDING`.
23. Evidence SHA: `WAVE1_MANUAL_ACTOR_IDENTITY_BINDING_SHA256.txt`.
24. ChatGPT Reviewable: YES.

## Current environment and controlled caveat

Frontend `http://127.0.0.1:5174`; Backend `http://127.0.0.1:8000`; DB `D:\Dev-PCE\work\wave1_actor_binding_manual_a4_20260911_001.sqlite3`.

The user's visible Customer acceptance count is authoritative: 89 → 90 and replay remains 90. A later direct diagnostic of the isolated SQLite file reports 91 physical Customer rows because it also retains one earlier non-production A3 preflight row (`W1-A3-CUST-20260911`). It is explicitly separated from the A4 user-visible result and was not deleted in this continuation because the requested write budget is zero. Production is unaffected.

`FORMAL IMPORT ACTOR CONTEXT = CUSTOMER MANUAL PASS / B4 C4 READY`  
`USER-VISIBLE CUSTOMER IMPORT COMMIT + IDEMPOTENCY = PASS`  
`MATERIAL B4 + WORKSHOP C4 MANUAL VALIDATION = PENDING`  
`ADOPTED = 0`  
`PRODUCTION WRITES = 0`
