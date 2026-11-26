# Phase B Migration Data Operation Allowlist B类22项证据补充 FINAL / CONSOLIDATED报告

## 一、任务范围

本任务仅对Allowlist原B类22项进行固定commit源码读取、函数级证据整理、三选一裁决和文档更新。未执行Migration、RunPython、RunSQL、DDL/DML或数据库连接，未创建Replay数据库。

## 二、治理读取结果

### COMPLETED MODULE GOVERNANCE READING RECEIPT

|项目|结果|
|---|---|
|六份指定治理文件|已全文读取|
|Registry|JSON解析通过，共34项|
|Frozen Core|未修改|
|Frozen Shared Dependency|未修改|
|Freeze Contract|未触发修改流程|
|Unfreeze|不需要|
|保护等级|Level C；`SAFE TO MODIFY DOCUMENTATION ONLY`|

## 三、B类22项Evidence Record摘要

已生成《Migration Data Operation B-Class Evidence Record V1.0》。每项包含：

- App、Migration、Operation Type；
- 函数名及精确源码行区间；
- 文件路径、固定Git Commit及Git blob原始字节SHA256；
- 入口、函数、影响对象及结束状态调用链；
- 创建、修改、删除、权限、配置、组织和基础资料影响；
- 输入表、前置数据、环境与业务事实依赖；
- 幂等、唯一约束和重复执行分析；
- reverse函数、noop、完整性和残留；
- 风险等级与固定三选一Decision。

22/22记录完整，无无法判断项。

## 四、函数级证据结果

|Decision|数量|主要结论|
|---|---:|---|
|A — APPROVE FOR REPLAY|9|确定性、稳定业务键，且可在全新隔离空库＋Fingerprint合同下重放|
|B — EXCLUDE FROM REPLAY|0|原B类中无单纯排除项|
|C — REDESIGN REQUIRED|13|固定公司/岗位、跨域权限、旧计划路径或业务配置Seed必须拆分治理|

批准的9项为：

- `masterdata.0009`；
- `pde.0010`、`pde.0021`、`pde.0030`；
- `procurement.0028`；
- `system.0004`、`system.0005`、`system.0006`、`system.0007`。

## 五、Permission Seed结果

批准范围仅包括：

- PDE工程权限定义及最小、稳定角色投影；
- 基线保存/确认权限定义；
- SCM/WMS/QMS/FIN只读权限定义；
- System基础RBAC、组织查看与组织治理权限。

以下转为REDESIGN REQUIRED：

- PLAN角色跨域获得BOM、Routing、工程规则/计算权限；
- 固定岗位/职责与Workflow映射；
- 包含关闭能力或付款相关的跨域权限Seed；
- 依赖公司/组织样本的权限和配置混合操作。

## 六、RunSQL结果

唯一RunSQL为`masterdata.0009_unit_and_code_governance_a1`：

- SQL：`CREATE TABLE IF NOT EXISTS code_rule`；
- 影响：创建`code_rule`表及唯一约束；
- 重复性：IF NOT EXISTS；
- reverse：`DROP TABLE IF EXISTS code_rule`；
- Decision：A，但仅限全新隔离空库。

## 七、基础数据Seed结果

以下因产生固定业务事实或不可移植配置而要求重新设计：

- 固定PCE项目、采购成本中心及分类；
- company_id=1单位/编码规则；
- 默认`WH-RM-001`仓库和首个active Company；
- 固定销售岗位、职责和流程节点；
- 采购结算“14—22”验收语义。

强制C类结论保持不变：Planning 0005排除、PFM 0002重新设计、PDE行业语义排除、Sales验收样例排除。

## 八、Reverse分析

- 9项A中显式reverse者按Evidence执行；noop者只接受隔离临时库销毁合同；
- 13项C不得执行，其noop或不完整reverse风险不再由当前Replay承担；
- 本结论不证明正式数据库可回滚，也不允许在非空业务库复用。

## 九、Allowlist更新结果

全量153项更新为：

|最终Decision|数量|
|---|---:|
|A — APPROVE FOR REPLAY|136|
|B — EXCLUDE FROM REPLAY|3|
|C — REDESIGN REQUIRED|14|

Allowlist状态更新为`READY FOR SIGNATURE`，指定签署人`admin`，签署日期和Decision仍为空。

## 十、R5状态

22项已全部具有Evidence Record、明确Decision与风险等级，满足Gate从`BLOCKED`转为：

```text
R5 = READY FOR AUTHORIZATION
```

但Allowlist尚未完成真实签署：

```text
R5 DATA OPERATION ALLOWLIST = READY FOR SIGNATURE
```

## 十一、Replay Gate状态

|Gate|状态|
|---|---|
|R0|`READY`|
|R1|`READY WITH REDESIGN REQUIRED`|
|R2|`READY WITH EXCLUSION`|
|R3|`READY`|
|R4|`READY FOR AUTHORIZATION`|
|R5|`READY FOR AUTHORIZATION`|
|R6|`READY`|
|R7|`READY`|

Replay Authorization保持`NOT READY`，等待R5真实签署及后续独立执行授权。

## 十二、保护结果

- 未执行`migrate`、`sqlmigrate`、`makemigrations`、RunPython或RunSQL；
- 未执行DDL/DML，未创建Replay数据库；
- 未修改Migration源码、依赖、模型、Schema、权限、Router或Registry；
- 未生成BOM、BOM Version、EngineeringMaterialRequirement、EngineeringOperationRequirement、ProductionPlan、MPS、MRP或APS；
- 正式数据库与C5数据库未被连接或写入。

## 十三、最终状态

```text
B-CLASS DATA OPERATION EVIDENCE = COMPLETE
R5 DATA OPERATION ALLOWLIST = READY FOR SIGNATURE
REPLAY AUTHORIZATION = NOT READY
```

未声明`PHASE B READY`。

