# Phase B Git源基线治理清单

- 日期：2026-09-28
- 任务：A4 Git源基线治理
- 分类方法：Git索引事实 + 文件路径/类型 + 集成提交交叉比对
- 清理动作：无
- Git破坏性动作：无

## 1. 基线身份

|对象|路径|分支|HEAD|角色|状态|
|-|-|-|-|-|-|
|主工作区|`D:\Dev-PCE\Source`|`master`|`6058ee03022ac1f4ef7a40905aef32f0dd2e294e`|当前权威成果来源与大量未提交历史现场|待治理，不得直接作为Phase B开发基线|
|集成工作树|`C:\Users\DAODA\.codex\worktrees\manufacturing-baseline-convergence\Source`|`codex/manufacturing-baseline-convergence-20260927`|`969a86fe4a1b8557e8c837d19c58e9a9cc5d8fba`|Phase A + 当前权威成果的已提交集成候选|保留；需完成污染资产与C5源资产治理|
|当前权威提交|Git对象|`codex/current-authority-baseline-20260927`|`dfc390104e857d095d402a0d021510f61caf9ee1`|主工作区白名单成果证据|保留|
|Phase A证据提交|Git对象|`codex/manufacturing-phase-a-evidence-20260927`|`ee4838ff0dc89082071ed106da5c4e6318a32cb0`|Phase A历史证据|保留|

## 2. 快照摘要

|工作树|tracked index files|tracked changed|deleted|untracked|路径清单摘要|
|-|-:|-:|-:|-:|-|
|主工作区|16,760|124|4|31,696|tracked digest `53F03D836C34CDDC83C3F614C2966D3ACC31A42E1517C21E5B95F7045851225A`; untracked digest `3C35D998730039615C418AF863AECF2190143A9BB5D2FDEEAA44E26F270F08A5`|
|集成工作树|20,375|63|0|1,213|tracked digest `C7AA1515A71F60FE7EA55842AA52B43D9B27384EA3FFBFE425DCAB5BEFADE106`; untracked digest `3274AA9C5BCE4B6B01C4E529CCEC380A3D27FBBD4E3DF3B06C64BDD734717011`|

注：Windows权限/长路径导致若干真实会话临时目录无法枚举；因此上述 untracked 是Git可枚举下限，不是对磁盘临时文件的绝对总数。

## 3. 主工作区全部变更分类

### 3.1 tracked变化

|文件/目录|类别|数量/状态|来源与权威判断|处理建议|
|-|-|-|-|-|
|`backend/**/*.py`（不含缓存）|A 正式源码候选|32项左右，含models/services/views/urls/settings|相对master的当前成果；绝大多数内容已进入集成HEAD|保留；以集成提交为权威，不从脏工作树重新复制|
|`frontend/src/**`（通用页面、API、Router、Registry相关）|A 正式源码候选|约58项|当前权威前端成果；对应内容已由authority提交收敛|保留；禁止整体覆盖或重新挑拣|
|`frontend/package.json`、`package-lock.json`、`index.html`、`vite.config.js`|A/配置候选|4项|构建配置/依赖事实|保留并以集成提交版本为准|
|`backend/pde/migrations/0020_workcenter_engineering_closure.py`|A Migration历史|deleted|删除已在集成HEAD体现；涉及Migration源图|保留Git历史；交由下一任务做源图裁决|
|`backend/pde/tests_workcenter_engineering_closure_wave21.py`|B 测试源码|deleted|删除已在集成HEAD体现|保留Git历史；不在本任务恢复|
|`frontend/src/domain/permission/permissionEngine.js`|A 正式源码|deleted|删除已在集成HEAD体现|保留当前收敛事实；权限边界不在本任务修改|
|`frontend/frontend_backup.zip`|D 临时/备份|deleted in main；集成提交仍有历史版本|非生产源码|待人工确认后归档；本任务不删|
|`backend/**/__pycache__/**`、`*.pyc`|C 运行产物|22项以上|Python运行缓存|可清理候选；禁止进入未来源码提交|
|`frontend/node_modules/.package-lock.json`、`.vite/**`|C 运行产物|3项以上|npm/Vite缓存|可清理候选；不作为源码事实|
|`backend/db.sqlite3`|C 运行/验证数据库|modified|当前为C5隔离基线副本，不是业务库|保留当前C5事实；不得作为正式源码或业务数据|
|`frontend/src/meta/manufacturing/manufacturingFoundation*`等|E 历史实验/非权威实现|已跟踪/未跟踪混合|G4已确认C类来源边界，仍有运行依赖|继续隔离治理；本任务不改|
|`frontend/src/meta/scm/scmMockDataGenerator.js`|E 样例/历史实现|modified|样例生成器，不是核心权威|保留追溯，禁止进入核心制造服务|
|`frontend/src/views/PurchaseOrderList copy.vue`|E 重复/历史入口候选|modified|文件名与现有正式列表并存|待入口治理确认；不得作为Phase B权威入口|

tracked交叉比对：124项中95项字节内容与集成HEAD一致，3项删除已由集成HEAD体现，26项不同；26项中主要为数据库/缓存，正式源码差异集中在 `backend/pce_backend/settings.py`、`backend/pde/models.py`、`backend/planning/models.py`，它们由Phase A集成提交增量扩展，不能用主工作区旧版本覆盖。

### 3.2 untracked变化

|文件/目录|类别|数量|是否已进入集成HEAD|状态|处理建议|
|-|-|-:|-|-|-|
|正式源码候选总计|A|2,273|2,267已存在；6未存在|大部分已收敛|集成HEAD内容作为候选权威；6项单列确认|
|`frontend/test-results/**`、`docs/evidence/**`、`docs/governance/**`、`frontend/tests/**`|B|6,971|739已存在；6,232未存在|测试证据混杂|保留；后续按Manifest归档，不直接并入生产源码|
|`.runtime/**`、`work/**`、build/cache/pyc/sqlite/log|C|19,033|0|运行产物|建议加入受控ignore/外部证据目录；未经确认不删|
|验收构建副本、Excel runner输出、未归属文档|D|3,252|532已存在；2,720未存在|来源未完全确认|待确认；不得自动提交或清理|
|legacy/sample/mock/backup/重复入口|E|167|58已存在；109未存在|历史/实验|保留追溯并禁止成为Phase B权威|

## 4. 未进入集成HEAD的A类候选

|文件|类别|来源事实|权威状态|建议|
|-|-|-|-|-|
|`backend/canary-data/.gitkeep`|A/目录占位|2026-07-23遗留|非关键，未确认|待确认|
|`backend/scripts/build_c5_validation_baseline.py`|A/C5验证工具|2026-09-28生成；SHA256 `28065D526A9AE1538B3EDD6170025DDA56C81280A1D596887AB8DF66B4868F9A`|当前C5 PASS所需、但未提交|必须单独评审后纳入受控源基线|
|`backend/system/tests_account_credential_governance_v1.py`|B/测试源码|2026-09-18；SHA256 `6F047FD615ACDA54171CA7874666E04AF136553C89142E81774A8E068B435DD5`|未确认是否属于Phase B|待测试责任人确认|
|`backend/validation/c5/README.md`|B/C5合同|SHA256 `EDD0872B5D4FED819D920C51AD4994990579C86767A9241765164486E23A34E2`|当前C5说明，但未提交|与生成器/Manifest作为同一原子包评审|
|`backend/validation/c5/manifest.json`|B/C5证据|SHA256 `826C6266631A2A4A5E16C45EF547F08900AD92D01EE3013E6C84E4E4E8035BA4`|当前C5 Manifest，但未提交|与生成器/README作为同一原子包评审|
|`backups/.../backend/pde/models.py`|E 备份|历史Schema迁移备份|非权威|归档保留，禁止编译/引用|

## 5. C5验证资产

|资产|Hash/状态|类别|治理结论|
|-|-|-|-|
|`backend/validation/c5/c5-validation-baseline.sqlite3`|`0840A70E7D2F3965FCFC038977841D9BABC0354101B5C7CCE14F89552FC39F67`，888,832 bytes|B/C5验证资产；被`*.sqlite3`忽略|保持原样；不可作为业务库；需决定可复现交付方式|
|主工作区 `backend/db.sqlite3`|同上|C/C5 Gate输入副本|C5专用；不进入业务运行|
|集成工作树 `backend/db.sqlite3`|`22AA5F7B0766E74EB6FEC14087360AFC8F48C6E79A34C25F5A41ABAD65611907`，827,392 bytes|C/旧验证输入|与当前C5 PASS资产不一致；禁止称为同一可复现基线|

## 6. 集成提交污染项

`969a86fe…`的20,375个已跟踪文件中：

|路径/类型|已跟踪数量|类别|建议|
|-|-:|-|-|
|`frontend/node_modules/**`|14,130|C 运行/依赖缓存|后续受控提交停止跟踪；当前不得删除|
|`__pycache__/**`及`*.pyc`|110|C Python缓存|后续停止跟踪；当前不得删除|
|`backend/db.sqlite3`|1|C 数据库运行资产|从软件源权威中分离；保持C5隔离边界|
|`frontend/test-results/**`|9|B 测试证据|仅保留有Manifest/Hash的权威检查点；与生产源码分层|
|`docs/governance/**`|380|B 治理证据|保留，但不等于业务源码|

## 7. Ignore治理建议（本任务未修改）

当前 `.gitignore` 已声明 `node_modules`、`__pycache__`、`*.sqlite3`、`dist/build`，但对已被Git追踪的文件不生效；同时 `.runtime/**`、`work/**`、`frontend/test-results/**` 尚未形成统一忽略/证据归档合同。

建议后续单独授权：

1. 先生成待停止追踪清单与证据Manifest；
2. 经人工确认后仅从Git索引停止追踪，不删除工作区证据；
3. 对`.runtime`、`work`、普通测试输出采用ignore；
4. 对权威检查点采用小范围白名单或独立证据仓库；
5. 禁止`git clean/reset/checkout`。

## 8. 当前治理状态

|事项|状态|
|-|-|
|每类文件来源/责任已建立|PASS（目录级全量覆盖 + 关键文件逐项）|
|正式源码候选与运行产物已分离|PASS（逻辑分类）|
|集成提交已无运行产物|FAIL|
|C5源资产已纳入集成提交|FAIL|
|当前工作树可直接用于Phase B开发|NO|
|Git源基线治理|PARTIAL|

