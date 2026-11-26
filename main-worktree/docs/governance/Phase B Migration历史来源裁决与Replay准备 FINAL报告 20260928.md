# Phase B Migration历史来源裁决与Replay准备 FINAL / CONSOLIDATED报告

日期：2026-09-28  
任务性质：Migration历史来源裁决准备；只读分析与证据整理  
活动基线：`codex/manufacturing-baseline-convergence-20260927@969a86fe4a1b8557e8c837d19c58e9a9cc5d8fba`

## 一、任务范围

本任务建立了争议Migration的字节级Evidence Record、Target Schema Decision Matrix和后续隔离Replay Test Plan。

执行内容仅包括：治理文件全文读取、Git对象和历史只读检查、Migration源码静态解析、既有治理报告引用、治理文档编制、文件级保护Hash核验。

未运行：`migrate`、`sqlmigrate`、`makemigrations`、DDL、DML、Migration恢复/合并/删除/依赖修改、正式库内容查询或任何制造业务生成。

## 二、治理读取结果

### COMPLETED MODULE GOVERNANCE READING RECEIPT

已全文读取：

1. `D:\Dev-PCE\AGENTS.md`；
2. `D:\Dev-PCE\Source\AGENTS.md`；
3. `docs/governance/PCE CODEX开发指令规范管理V1.2.md`；
4. `docs/governance/PCE 已开发模块固化与变更保护规范 V1.0.md`；
5. `docs/governance/completed_module_registry.v1.json`；
6. `docs/governance/COMPLETED_MODULE_PROTECTION_PREFLIGHT_V1.md`。

读取Hash与上一治理任务一致：根AGENTS `0CD48571...5954`、仓库AGENTS `BC701CB8...EC44`、开发规范 `50791C92...E888`、固化规范 `B6FAAAB1...35D8`、Registry `10F23EA6...3B32`、Preflight `D2B2487B...D4BD`。

- Registry：可解析；已固化模块和共享依赖保护规则有效。
- Frozen Core：只读涉及，未修改。
- Frozen Shared Dependency：只读涉及，未修改。
- Unfreeze：当前不需要；未来修改PDE/PFM/Planning Migration时必须重新Preflight并取得明确授权。
- 保护等级：Level C。
- Preflight结论：`SAFE TO MODIFY DOCUMENTATION ONLY`。
- UI/DELIVERED USER STATE：N/A。

G1已有admin签署只确认“数据库运行事实优先、未来建立唯一可信可复现基线、不强制恢复全部历史文件”。它不等于对任何具体blob、Schema或Migration执行授权。

## 三、Migration历史证据档案

完整Evidence Record见：[Phase B Migration历史来源 Evidence Record 20260928.md](./Phase%20B%20Migration历史来源%20Evidence%20Record%2020260928.md)。

### 3.1 总览

|对象|活动文件来源|历史候选来源|主要差异|正式证据边界|状态|
|-|-|-|-|-|-|
|PDE 0020|`dfc3901` / `c1790533...`|`6058ee0` / `9e10a8c...`|1字段 vs 4张资源关系表及WorkCenter关系|既有报告证明历史名称已登记，不证明blob|待确认|
|PDE 0021|`dfc3901` / `bd2e38dd...`|`fa7dfb0` / `50e60020...`|权限RunPython vs 订单工程结构Schema|同上|待确认|
|PDE 0022|`dfc3901` / `69dbfb84...`|`44dfc6b` / `d55eaa27...`|制造适用范围 vs 结构规则/核算表|同上|待确认|
|PFM 0002|`eeaa985` / `6af9c11d...`|`02a832b` / `2b6edc8d...`|组织关系+数据绑定 vs 用户/证书关系|历史应用日期早于当前Git候选提交日期|无法确认部署字节|
|Planning 0005|`dfc3901` / `ef5e79ae...`|此前无Git历史|5张MPS/MRP表+权限seed|既有报告明确未应用|需独立授权|
|Planning 0006|当前收敛`c4a3c81` / `cb417f31...`；原始证据`ee4838f` / `dc210f09...`|Phase A证据经收敛merge重排依赖|1张Plant计划属性表；当前依赖0005|无正式部署授权|父依赖阻断|

### 3.2 证据可信边界

Git commit/blob/SHA-256能够证明“仓库历史中存在这些字节”，不能证明“正式数据库当时执行的就是这些字节”。正式应用记录只存app、name、applied，不存Git或文件Hash。本任务严格引用已有治理证据，没有打开正式数据库，也没有根据现有Schema反向生成Migration。

## 四、PDE 0020–0022裁决状态

### 4.1 两条链来源

活动链进入当前集成提交：

```text
pde.0019
→ 0020_group3_transition_mode_override        (source commit dfc3901)
→ 0021_group3a_operation_executor_authority   (source commit dfc3901)
→ 0022_manufacturing_definition_applicability (source commit dfc3901)
```

历史候选链：

```text
pde.0019
→ 0020_workcenter_engineering_closure          (commit 6058ee0)
→ 0021_order_engineered_product_structure      (commit fa7dfb0)
→ 0022_structure_template_rule_binding_wave27  (commit 44dfc6b)
```

### 4.2 与正式事实的关联

既有治理报告记录正式数据库应用名称为历史候选链中的0020、0021、0022，而不是当前活动链同号名称。这是名称级关联证据，不是部署字节证据。

### 4.3 部署字节身份

没有。没有正式部署归档、Migration文件Hash审计记录、制品manifest或能把数据库应用记录绑定到Git blob的证据。禁止据此直接选中某条链。

### 4.4 唯一目标Schema判断

当前不能形成唯一目标Schema：

- 选择活动链会丢失正式库登记过的历史资源/结构/规则语义；
- 选择历史链会丢失当前活动链的转换模式、权限投影和适用范围语义；
- 同时恢复会形成同号多叶，必须另行设计显式收敛，不能在本任务自动merge；
- 仅以当前模型或正式数据库结构为准都违反“不得反向伪造Migration”。

PDE裁决状态：`HISTORICAL SOURCE PENDING / UNIQUE TARGET SCHEMA UNRESOLVED`。

## 五、PFM 0002裁决状态

当前活动`0002_employee_formal_organization_relations`来源于`eeaa985`，提供Employee正式Department/Position关系并执行数据匹配。历史`0002_initial`来自`02a832b`，后在`6480e62`删除，提供Employee.user和EmployeeCertificate.employee关系，不执行数据迁移。

既有报告记录正式库在2026-05-20已应用`pfm.0002_initial`，而当前可达Git候选提交时间为2026-05-31。这一时间倒置说明候选blob不能直接充当正式部署字节证明，可能存在更早外部来源或提交时间/归档链缺口。

PFM裁决状态：`DATABASE FACT EXISTS / DEPLOYED BYTES UNVERIFIED / CONVERGENCE REQUIRED`。

后续必须确认：历史删除意图、EmployeeCertificate.employee最终权威、当前组织关系Migration是否应在独立新编号承接，以及历史名称如何保留审计。不得直接把两个0002放入同一活动目录。

## 六、Planning 0005/0006授权分析

### 6.1 Planning 0005事实

`planning.0005_order_planning_chain_v1`创建：

1. `planning_mps_run`；
2. `planning_mps_line`；
3. `planning_mps_demand_allocation`；
4. `planning_mrp_run`；
5. `planning_mrp_proposal`。

它还通过不可逆`RunPython(..., noop)`创建/更新：

- 角色`order_planning_operator`；
- 权限`planning.mps.generate`；
- 权限`planning.mrp.generate`；
- 可选绑定已有`planning.view`。

### 6.2 Planning 0006事实

`planning.0006_material_plant_profile_phase_a`创建Plant级物料计划属性，但声明直接依赖`planning.0005_order_planning_chain_v1`，同时依赖EMD Plant、MES基础模型和PDE TimeStandard。

### 6.3 与关闭边界的冲突

当前治理边界要求MPS/MRP执行和正式生产计划保持关闭。仅创建表并不等于执行业务，但0005同时创建生成权限，并且既有治理决定明确它未获正式部署授权。因此它不能默认进入Replay目标链。

### 6.4 分类

|分类|结论|
|-|-|
|A 已授权，可进入Replay|否|
|B 需要独立授权|是，0005本身需要|
|C 需要重新设计依赖|是，若继续关闭0005，则0006必须摆脱对0005的隐式依赖|

Planning裁决：`B + C`。本任务不选择“授权0005”或“重设计0006”，等待用户/架构责任人决策。

## 七、Target Schema Decision Matrix

|来源|证据|可信度|问题|下一步|
|-|-|-|-|-|
|当前Migration活动链|固定提交、153项目节点、Git blob/SHA256、静态Loader可加载|源代码身份高；正式目标适配度中|PDE/PFM历史语义缺口；Planning 0005未授权|逐项签署纳入/排除清单，解决0005/0006|
|历史Migration|PDE/PFM候选commit、blob、SHA256、依赖和操作均可追溯|历史存在性高；部署身份低至中|候选不一定是正式执行字节；同号异义|获取制品/归档Hash或签署“仅作历史证据、不作活动源”|
|正式数据库事实|既有已签治理报告中的应用名称、时间和运行事实|运行状态事实高；Migration字节身份低|本任务不得重开；数据库结构不能反向伪造Migration|只用于兼容验收目标，由独立只读Schema fingerprint授权任务提供摘要|
|C5模型直建库|manifest、固定Hash、`migrationUsed=false`|模型装载验证高；Migration证明力为零|由schema_editor直建，绕过Migration和seed|仅保留C5用途，禁止作为Replay基线|

### 7.1 推荐的目标Schema裁决模型

未来Replay不能直接选择上述任一来源作为绝对权威。应先签署`Target Schema Manifest`，至少包含：

1. 固定源码commit；
2. 每个争议Migration的`INCLUDE_ACTIVE / ARCHIVE_HISTORY / REDESIGN`决定；
3. 允许出现的业务表、字段、索引、约束白名单；
4. 允许执行的数据Migration和seed白名单；
5. 明确MPS/MRP结构和权限是否纳入；
6. 正式数据库兼容要求，但不以其结构反向生成Migration；
7. 预期叶节点集合和Migration集合Hash。

### 7.2 当前可选方向（不代替用户裁决）

- T1：当前活动全链。可直接描述，但会包含未授权Planning 0005，当前不可批准Replay。
- T2：当前活动链排除Planning 0005。因0006直接依赖0005，当前图不可执行，需先授权重新设计依赖。
- T3：恢复历史PDE/PFM链并收敛。缺部署字节身份且需要新设计，当前不可执行。
- T4：签署一个面向未来的受控新基线，将历史链归档为证据，并以独立、非伪造的新Migration表达经批准差异。该方向符合G1原则，但必须另行设计和授权。

当前没有一项达到“唯一目标Schema已签署”。

## 八、Migration Replay Test Plan

本节仅定义未来验证方法，不执行任何命令。

### 8.1 Replay前置条件

|Gate|条件|当前状态|
|-|-|-|
|R0|Target Schema Manifest签署|BLOCKED|
|R1|PDE 0020–0022与PFM 0002纳入/归档/重设计决定|BLOCKED|
|R2|Planning 0005独立授权，或0006依赖重设计获授权|BLOCKED|
|R3|所有待执行Migration位于干净、固定commit|PARTIAL；提交固定但集成工作树脏|
|R4|隔离settings强制数据库路径在新临时目录，拒绝正式库/C5路径|待建立|
|R5|RunPython/seed白名单、反向策略与幂等预期签署|BLOCKED|
|R6|正式数据库和C5保护Hash记录|READY|

### 8.2 临时数据库来源与隔离

未来执行时：

1. 使用新建临时目录和全新空SQLite文件；路径必须通过显式前缀断言，不得位于Acceptance、主工作区`backend/db.sqlite3`或C5目录。
2. 使用专用Replay settings，仅引用获授权源码commit和空数据库。
3. 执行前后只计算正式数据库与C5基线文件Hash，不连接它们。
4. 禁止复制正式数据、C5直建库、测试JSON或行业样例作为seed来源。

### 8.3 建议分阶段范围

1. `Replay-Graph-A`：只对获签Target Schema Manifest中的活动链执行完整forward。
2. `Replay-History-PDE`：如需比较历史语义，在另一独立空库/独立证据分支重放历史候选链；禁止把同号文件混放。
3. `Replay-History-PFM`：同理独立比较两个PFM 0002方案。
4. `Replay-Planning`：只有B/C决策完成后才纳入0005/0006；在此之前暂缓整个Planning Phase A叶节点。
5. 不执行BOM、ProductionPlan、MPS、MRP或APS业务服务；Migration seed也必须局限于白名单。

### 8.4 Schema fingerprint规范

每次forward完成后生成规范化、排序后的指纹：

- `django_migrations`应用集合；
- 表名与建表SQL规范化摘要；
- 每表字段名、类型、null/default、主键；
- 外键目标、删除策略可见Schema；
- 索引、唯一约束、Check约束；
- 触发器和视图；
- 已授权seed的业务键、角色/权限关系数量和值；
- 整体manifest SHA-256。

不得把数据库文件Hash作为唯一Schema fingerprint，因为SQLite文件页布局和时间因素可能变化。

### 8.5 Forward / Reverse / Forward

1. 从空库执行获授权forward至目标叶节点。
2. 保存`F1` Schema与seed fingerprint。
3. 在同一隔离副本按批准边界执行reverse到明确父节点。
4. 保存`R1` fingerprint并确认目标表/字段/seed已按合同撤销。
5. 再次forward到相同叶节点，保存`F2`。
6. 要求`F1 == F2`，且两者等于Target Schema Manifest预期。

已知风险：Planning 0005的反向函数为noop，角色和权限seed不会自动删除。因此其回滚合同当前不完整；若纳入Replay，必须先由授权设计说明预期残留或提供受控反向方案。本任务不得修改它。

### 8.6 通过标准

必须同时满足：

```text
clean database
→ authorized migration replay succeeds
→ F1 schema fingerprint matches signed target
→ reverse matches rollback contract
→ second forward produces F2
→ F1 = F2 = signed baseline
→ protected database/C5 hashes unchanged
```

任何超时、不可逆数据操作、未授权seed、缺失依赖、指纹差异或保护Hash变化均为FAIL，不得降级为PASS。

## 九、禁止事项确认

本任务没有：

- 修改、创建、合并、删除Migration；
- 修改依赖或业务模型；
- 执行`migrate`、`sqlmigrate`、`makemigrations`；
- 执行DDL/DML；
- 打开正式数据库内容或用其反推Migration；
- 使用C5数据库作为Replay证据；
- 生成BOM、BOM Version、工程材料/工序需求、ProductionPlan、MPS、MRP或APS对象；
- 修改C5 Gate、Router、Registry或权限。

## 十、下一步授权需求

在发布《Phase B隔离数据库Migration Replay验证执行指令》前，仍需明确授权/决策：

1. 签署Target Schema Manifest和目标方向T1/T2/T3/T4之一；
2. 对PDE 0020–0022、PFM 0002逐项决定活动、归档或重设计；
3. 对Planning作出二选一决策：独立授权0005，或授权重设计0006依赖；
4. 批准专用隔离settings、临时数据库目录及可执行Migration白名单；
5. 批准RunPython/seed白名单和反向合同；
6. 明确Replay仅为测试验证，不构成生产Migration授权。

## FINAL / CONSOLIDATED

```text
MIGRATION HISTORY SOURCE GOVERNANCE = PARTIAL
TARGET SCHEMA = UNRESOLVED
REPLAY TEST PLAN = PREPARED
REPLAY PREPARATION = NOT READY

PHASE B READY = NOT DECLARED
PHASE B IMPLEMENTATION = BLOCKED
```

结论：历史候选、活动文件及差异均已形成可审阅证据链，但部署字节身份、唯一目标Schema和Planning授权仍未闭合。当前只能准备Replay方案，不能授权或执行Replay。
