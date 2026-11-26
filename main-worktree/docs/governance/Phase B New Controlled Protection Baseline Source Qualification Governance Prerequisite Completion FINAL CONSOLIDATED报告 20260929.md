# FINAL / CONSOLIDATED

# 《Phase B New Controlled Protection Baseline Source Qualification Governance Prerequisite Completion FINAL / CONSOLIDATED报告》

日期：2026-09-29  
Governance Prerequisite ID：`NCPSB-SQGP-A-20260929-001`  
绑定Source Proposal：`NCPSB-SP-A-20260929-001`  
绑定Logical Source：`PCE-NCPB-A-REBUILD-SOURCE-P01`  
绑定Evidence Completion：`NCPSB-SQEC-A-20260929-001`  
任务性质：治理前置结构建立 / 不产生Source或环境  
审查等级：Level C  
最终Gate：`NOT READY FOR SOURCE QUALIFICATION REVIEW PRE-CHECK`

## 一、原始授权范围

本轮只允许：

1. 治理责任定义与证据整理；
2. 输入边界定义；
3. Schema/Migration现状分析；
4. 数据范围定义；
5. 事实包结构准备；
6. 审批链缺口登记；
7. Source Qualification前置条件状态更新。

明确未授权数据库、Schema、Migration、Seed、Replay、VACUUM、Candidate、Baseline、Hash签署或Generation/Validation/Recovery环境的创建与变更。

### 1.1 本轮证据来源

本轮不重新打开数据库，只使用已经归档的八份治理报告及上一轮只读核验结果。关键冻结事实包括：

- ABA6765继续是Drifted Historical Evidence，不是未来Source；
- 734F继续是Historical Evidence，实体和恢复源不可获得；
- 当前工作树存在1490项状态，不得直接作为冻结输入；
- 当前仓库与Protection Migration登记在`pde`、`pfm`、`planning`、`procurement`存在差异；
- Generation、Validation和Recovery环境均为`NOT CREATED`。

### 1.2 未执行事项

- 未任命任何真实人员或代替治理主体签署；
- 未修改数据库、Schema、Migration文件、代码、配置或数据；
- 未执行Migration、Seed、Replay、VACUUM、DDL或DML；
- 未创建数据库、Source、Candidate、Baseline或任何运行环境；
- 未计算新的Baseline Hash或签署Hash；
- 未初始化Acceptance Runtime；
- 未隐藏、重命名或解决既有Migration差异。

## 二、本轮治理补充项

本轮新增以下治理结构：

| Governance Record | ID | 当前状态 |
|---|---|---|
| Responsibility Appointment Register | `NCPSB-RAR-A-001` | `PENDING` |
| Data Boundary Definition Evidence | `NCPSB-DBDE-A-001` | `PENDING` |
| Schema/Migration Governance Comparison | `NCPSB-SMGC-A-001` | `CONFIRMED`（现状比较） |
| Consistent Input Combination Decision Record | `NCPSB-CICD-A-001` | `PENDING` |
| Baseline Data Package Plan | `NCPSB-BDPP-A-001` | `PENDING` |
| Business Fact Package Plan | `NCPSB-BFPP-A-001` | `PENDING` |
| Data Scope Manifest Plan | `NCPSB-DSMP-A-001` | `PENDING` |
| Exclusion List Plan | `NCPSB-ELP-A-001` | `PENDING` |
| Permission Organization Fact Package Plan | `NCPSB-POFP-A-001` | `MISSING` |
| Runtime Chain Binding Register | `NCPSB-RCBR-A-001` | `PENDING` |

这些记录是治理结构，不是事实批准、输入冻结、环境建立或资格结论。

## 三、四类责任主体状态

### 3.1 Responsibility Appointment Register

| Role Record | 治理角色 | User ID | Role | Organization | Authorization | 当前状态 |
|---|---|---|---|---|---|---|
| `RAR-SO-001` | Source Owner | `PENDING` | `PENDING` | `PENDING` | 来源范围、身份、边界和输入最终责任待授权 | `PENDING GOVERNANCE APPOINTMENT` |
| `RAR-SP-001` | Source Preparer | `PENDING` | `PENDING` | `PENDING` | 输入准备、数据范围和证据生成职责待授权 | `PENDING GOVERNANCE APPOINTMENT` |
| `RAR-TR-001` | Technical Reviewer | `PENDING` | `PENDING` | `PENDING` | Schema、Migration、工具链审核及冲突检查职责待授权 | `PENDING GOVERNANCE APPOINTMENT` |
| `RAR-AP-001` | Approver | `PENDING` | `PENDING` | `PENDING` | 最终批准权限、范围和批准时间待授权 | `PENDING GOVERNANCE APPOINTMENT` |

### 3.2 职责与冲突规则

| 角色 | 必须承担 | 禁止事项 |
|---|---|---|
| Source Owner | 批准来源身份、企业/组织边界、数据范围和截止点 | 不得单人同时准备、技术复核和最终批准 |
| Source Preparer | 形成四类输入包、证据索引和排除清单 | 不得兼任Technical Reviewer或Approver |
| Technical Reviewer | 独立检查Schema、Migration、Runner、工具链、依赖和证据一致性 | 不得审核自己准备的输入 |
| Approver | 审核责任分离、输入冻结和Review申请范围 | 不得批准自己准备或唯一复核的结果 |

实际人员任命后必须记录User ID、正式Role、Organization、Authorization ID、有效期和签署时间，并执行两两冲突检查。当前没有任命证据，职责分离状态仍为`PENDING`。

## 四、企业、组织和数据边界状态

### 4.1 Data Boundary Definition Evidence

| Boundary Field | 定义要求 | 当前值 | 状态 |
|---|---|---|---|
| 企业主体 | 唯一法人/企业身份、Owner和批准记录 | `PENDING GOVERNANCE APPOINTMENT` | `PENDING` |
| 组织范围 | 公司、部门、岗位及层级边界 | `PENDING GOVERNANCE APPOINTMENT` | `PENDING` |
| 数据所属范围 | 基础资料、业务域、事实类型和所属主体 | `NOT ESTABLISHED` | `MISSING` |
| 排除范围 | 临时、测试、模拟、缓存、个人测试及运行期数据 | `NOT ESTABLISHED` | `MISSING` |
| 截止时间点 | 唯一、批准、可重现的数据冻结时间 | `PENDING GOVERNANCE APPOINTMENT` | `PENDING` |
| 时区 | 截止点及审计事件的统一时区 | 建议`Asia/Shanghai / UTC+08:00`，尚未批准 | `PENDING` |
| 历史参考与未来Source区分 | 734F/ABA只作历史证据；未来Source使用新身份和新输入链 | 规则已建立 | `CONFIRMED` |

### 4.2 边界原则

- ABA及其副本不得成为未来Source、输入数据库或事实权威；
- 当前Protection表、行数或Schema只能作为历史参考，不能自动定义未来边界；
- 企业主体、组织关系和业务事实必须由责任主体从权威来源批准；
- 截止点变更会使已准备的数据包和Hash失效，必须新建版本；
- 未列入包含范围的对象默认排除，不能通过页面存在或历史行数推定纳入。

## 五、Schema/Migration治理状态

### 5.1 已确认现状比较

| 比较项 | 当前状态 |
|---|---|
| Protection Schema参考 | 300张表、583个索引、Schema参考SHA256为`C237E1705331CC3D0374F44EF45BE8121EC98E9F956F79CFF28B60DD94B3E7A1` |
| Protection Migration登记 | 170条、31个app |
| 当前仓库Migration文件 | 149个、27个本地app |
| 当前Migration聚合清单Hash | `2D8850BAEB4C778A074EF183A286A249A8387533A108EAFFCFB762BB1B9F7164` |
| 集合一致app | 23个 |
| 集合不一致app | 4个：`pde`、`pfm`、`planning`、`procurement` |
| 当前Git引用 | `6058ee03022ac1f4ef7a40905aef32f0dd2e294e` / `master` |
| 当前工作树 | 1490项状态；其中backend 325项、Migration相关20项 |

### 5.2 差异记录

| app | 必须保留的差异事实 |
|---|---|
| `pde` | Protection登记存在4个当前仓库无对应文件的Migration名称 |
| `pfm` | Protection登记额外存在`0002_initial` |
| `planning` | 当前仓库存在`0005_order_planning_chain_v1`，Protection未登记 |
| `procurement` | 当前仓库存在`0028_completed_module_read_permissions`，Protection未登记 |

差异不得通过本轮修改文件、执行Migration或重写`django_migrations`处理。

### 5.3 Consistent Input Combination Decision Record

| 决策字段 | 当前值 | 状态 |
|---|---|---|
| Approved Schema Source | `NOT ESTABLISHED` | `MISSING` |
| Approved Migration Set | `NOT ESTABLISHED` | `MISSING` |
| Approved Commit | `NOT ESTABLISHED` | `MISSING` |
| Schema Signature Rule | 需定义规范化对象、排序、编码和算法版本 | `PENDING` |
| Migration Signature Rule | 需定义文件、拓扑、Hash、fake审计和集合相等规则 | `PENDING` |
| Selection Rationale | 必须解释选择依据、排除依据及与数据包的兼容关系 | `PENDING` |
| Decision Owner / Reviewer / Approver | 尚未任命 | `PENDING GOVERNANCE APPOINTMENT` |

治理主体未来必须选择一个干净、不可变且内部一致的Schema/Migration/Commit组合。本报告不替其选择，也不把当前脏工作树或ABA组合升级为获批输入。

## 六、Data Scope Manifest状态

### 6.1 Baseline Data Package Plan

| 规划字段 | 必须内容 | 当前状态 |
|---|---|---|
| Package ID / Version | 唯一ID、版本和Proposal绑定 | `PENDING` |
| 数据范围 | 获批企业、组织和基础资料对象 | `MISSING` |
| 来源 | 权威系统/文件、Owner、路径和创建链 | `MISSING` |
| 内容证据 | 对象清单、记录数、内容Hash和引用关系 | `MISSING` |
| 批准 | Preparer、Reviewer、Approver及时间 | `PENDING` |

### 6.2 Business Fact Package Plan

| 规划字段 | 必须内容 | 当前状态 |
|---|---|---|
| 保留事实范围 | 经批准的订单、采购、库存、PDE、BOM、生产、计划、PFM等事实 | `MISSING` |
| 对象边界 | 实体、关系、有效期和企业/组织归属 | `MISSING` |
| 来源分类 | SOURCE / FORMAL / PREVIEW / SIMULATED_FOR_TEST / SYSTEM_DERIVED | `PENDING` |
| 可追溯路径 | 上游对象、转换规则、输入证据和责任人 | `MISSING` |
| 截止时间 | 与Data Boundary唯一截止点一致 | `PENDING` |

Excel/XLSX未来只允许作为业务素材、来源证据和人工事实输入。工作簿列、Sheet或公式不得直接定义数据库模型、编码标准或软件结构。

### 6.3 Data Scope Manifest与排除清单规划

Data Scope Manifest必须绑定企业、组织、截止点、Baseline Data Package和Business Fact Package，并逐项列明包含与排除范围。

排除清单至少覆盖：

- 临时表和临时记录；
- 测试、模拟和Preview数据；
- Django Session、缓存、队列和其它运行数据；
- 个人测试用户及其产生的数据；
- 未经批准的开发数据、修复数据和派生文件；
- ABA、开发库、运行库和未知来源SQLite。

当前Data Scope Manifest及排除清单均为`MISSING`。

## 七、权限组织事实包状态

### 7.1 Permission Organization Fact Package

整体状态：`MISSING`

| 事实类别 | 必须记录 | 当前状态 |
|---|---|---|
| 权限来源 | 权威来源、Permission ID、动作、对象、范围和审批 | `MISSING` |
| 组织来源 | 公司、部门、岗位树、有效期和Owner | `MISSING` |
| 员工引用 | Employee/User ID、组织和岗位引用、状态 | `MISSING` |
| 角色关系 | Role ID、职责、用户分配和作用范围 | `MISSING` |
| 审批关系 | 批准人、授权单、时间、有效期和撤销规则 | `MISSING` |
| 数据范围关系 | 角色/权限与企业、组织、对象范围的映射 | `MISSING` |
| 引用完整性 | 公司—组织—岗位—员工—用户—角色—权限一致性规则 | `PENDING` |

不得从ABA、开发库、页面展示或临时运行状态反推目标权限组织事实。必须由治理责任主体批准权威来源。

## 八、Runner/Commit/工具链绑定状态

### 8.1 Runtime Chain Binding Register

| Binding Item | 必须证据 | 当前值 | 状态 |
|---|---|---|---|
| Approved Commit | 完整SHA、干净工作树、签署/批准记录 | `NOT ESTABLISHED` | `MISSING` |
| Runner Version | 唯一版本、内容Hash、入口和禁止副作用 | `NOT ESTABLISHED` | `MISSING` |
| Parameter File | 版本、Hash、完整参数和环境变量白名单 | `NOT ESTABLISHED` | `MISSING` |
| Tool Versions | Python、Django、SQLite及辅助工具版本/Hash | `NOT ESTABLISHED` | `MISSING` |
| Python/Dependencies | 解释器身份、锁文件、依赖Hash和离线重建规则 | 当前requirements Hash仅为参考 | `PENDING` |
| Execution Environment Identity | environmentId、Host、路径、Operator和隔离策略 | `NOT CREATED` | `NOT AUTHORIZED` |
| Recovery Path | 保存位置、空目录恢复、比对和失败隔离路径 | 只有通用设计 | `PENDING` |

当前Git HEAD和1490项工作树状态只能作为现状证据，不能直接填入Approved Commit。任何绑定项变更都必须使关联Evidence Package产生新版本。

## 九、状态分类清单

### 9.1 CONFIRMED

- Source Proposal ID、Logical Source Identity及历史证据隔离规则；
- 四类责任角色的职责、记录字段和冲突约束；
- Data Boundary Definition所需字段与历史/未来数据区分规则；
- Protection Schema/Migration参考状态及四个差异app；
- 当前工作树1490项状态不能作为冻结输入；
- 四类数据/事实/范围/排除规划结构；
- Permission Organization Fact Package必备结构；
- Runtime Chain七项绑定字段和失效规则。

### 9.2 PENDING

- 四类责任主体正式任命；
- 企业主体、组织范围、截止点和时区批准；
- Schema/Migration签名规则和一致输入选择决定；
- 事实来源分类、引用完整性规则和恢复路径；
- Python/依赖版本及锁定方式；
- 各规划记录的Owner、Reviewer、Approver和批准时间。

### 9.3 MISSING

- 获批Schema Source、Migration Set和Commit；
- Baseline Data Package与Business Fact Package内容；
- Data Scope Manifest与排除清单；
- Permission Organization Fact Package；
- Runner、参数文件、工具版本和可重复生成证据；
- 实际职责分离与冲突检查证据。

### 9.4 NOT AUTHORIZED

- 数据库、Schema或Migration变更；
- Migration、Seed、Replay、VACUUM、DDL或DML；
- Source、Candidate或Baseline文件生成；
- 新Baseline Hash计算或Hash签署；
- Generation、Validation或Recovery环境创建；
- Acceptance Runtime初始化；
- Source Qualification Review执行。

## 十、Source Qualification Review进入条件更新

| 进入条件 | 本轮前 | 本轮治理补充 | 当前状态 |
|---|---|---|---|
| 来源身份明确 | `PENDING` | 定义未来databaseIdentity与历史隔离规则 | `PENDING`：Owner和范围未批准 |
| 输入已冻结 | `MISSING` | 建立一致输入决策记录和绑定清单 | `MISSING`：实际输入不存在 |
| 数据边界明确 | `MISSING` | 建立Data Boundary Definition结构 | `PENDING`：字段未获批准 |
| Schema/Migration可验证 | `FAIL` | 保留四app差异并建立决策字段 | `FAIL`：尚无一致获批组合 |
| 权限组织可验证 | `MISSING` | 建立事实包结构 | `MISSING`：内容和批准均不存在 |
| 恢复路径存在 | `PENDING` | 建立绑定字段和设计要求 | `PENDING`：无具体路径、责任或环境 |
| 职责分离明确 | `PENDING` | 建立四角色记录和冲突规则 | `PENDING`：未任命、未检查 |

本轮补充了治理结构，但没有把待任命、待批准或缺失事实转换为已完成证据。由于仍存在`FAIL`、`MISSING`和`PENDING`，不得进入Review Pre-check。

## 十一、下一步治理授权需求

要改变当前Gate，责任主体必须依次提供：

1. 四类角色的真实任命和冲突检查结果；
2. 企业、组织、数据边界、截止点与时区的签署批准；
3. 一致Schema/Migration/Commit组合的治理选择和理由；
4. Baseline Data Package、Business Fact Package、Data Scope Manifest及排除清单；
5. Permission Organization Fact Package与引用完整性规则；
6. Approved Commit、Runner、参数、工具、依赖和恢复路径的绑定证据；
7. 上述工件形成后，另行授权只读Review Pre-check。

任何授权都不得隐含数据库修改、Migration执行或环境创建。若输入或责任边界变化，相关记录必须新建版本并重新审查。

## 十二、保护状态与最终Gate

八份既有治理报告、734F历史记录和ABA文件均保持不变。本报告仅追加治理结构。

```text
GOVERNANCE PREREQUISITE COMPLETION = COMPLETE

SOURCE PROPOSAL ID = NCPSB-SP-A-20260929-001

RESPONSIBILITY APPOINTMENT = PENDING

DATA BOUNDARY APPROVAL = PENDING

CONSISTENT SCHEMA / MIGRATION INPUT = MISSING

DATA SCOPE MANIFEST = MISSING

PERMISSION ORGANIZATION FACT PACKAGE = MISSING

RUNTIME CHAIN BINDING = MISSING

DATABASE CHANGED = NO

MIGRATION EXECUTED = NO

ENVIRONMENTS CREATED = NO

NOT READY FOR SOURCE QUALIFICATION REVIEW PRE-CHECK
```
