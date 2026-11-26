# Phase B Migration Data Operation Allowlist与Schema Fingerprint评审 FINAL / CONSOLIDATED报告

## 一、任务范围

本任务仅对固定Source Commit中的Migration数据操作进行静态分类，形成Allowlist V1.0评审结果，并完成Schema Fingerprint Specification的admin技术评审。未执行Migration、Replay、DDL/DML或数据库写入，未创建Replay数据库。

## 二、治理读取结果

### COMPLETED MODULE GOVERNANCE READING RECEIPT

| 项目 | 结果 |
|---|---|
| 六份指定治理文件 | 已全文读取 |
| Registry | JSON解析通过，共34项 |
| Frozen Core | 未修改 |
| Frozen Shared Dependency | 未修改 |
| Freeze Contract | 未触发修改流程 |
| Unfreeze | 不需要 |
| 保护等级 | Level C；`SAFE TO MODIFY DOCUMENTATION ONLY` |

## 三、Migration Data Operation Allowlist

已生成《Phase B Migration Data Operation Allowlist V1.0》，覆盖固定commit `969a86fe4a1b8557e8c837d19c58e9a9cc5d8fba`中的全部153个Migration候选。

| 分类 | 数量 | 含义 |
|---|---:|---|
| A — APPROVED FOR REPLAY | 127 | 107个纯Schema迁移及20个确定性回填；仅适用于获授权隔离空库 |
| B — REVIEW REQUIRED | 22 | 权限扩展、基础数据Seed、RunSQL或反向合同仍需函数级签署 |
| C — EXCLUDED FROM REPLAY | 4 | Planning 0005、PFM 0002、行业语义操作及验收样例Seed |

由于22项B类仍未完成函数级证据与签署，Allowlist状态保持`DRAFT`，R5不得提升。

## 四、RunPython分类

共46个RunPython候选：

- A类20项：确定性回填/规范化，仅在全新隔离空库、固定commit和F1/F2比较合同下允许；
- B类22项：涉及权限/角色、基础数据Seed、对象范围或反向合同不足；
- C类4项：明确排除当前Replay。

A类中使用`RunPython.noop`的项目只接受“隔离临时库销毁”残留合同，不代表具备正式数据库回滚能力。

## 五、RunSQL分类

唯一RunSQL候选为`masterdata.0009_unit_and_code_governance_a1`。其SQL摘要、表/字段影响、重复性和reverse SQL尚未完成独立签署，分类为：

```text
B — REVIEW REQUIRED
```

不得在当前Replay中执行。

## 六、Seed分类

- 通用基础数据Seed：B，需稳定业务键、幂等和反向合同；
- 行业语义/验收样例Seed：C；
- Planning 0005的MPS/MRP Seed：C；
- PFM 0002的数据绑定：C，等待重新设计。

## 七、Permission Seed分类

Role、Permission与RolePermission等权限扩展均未自动批准。相关Migration保持B类，必须逐项证明：

- 权限稳定编码与业务模块归属；
- 是否属于当前Target Schema；
- 重复执行结果；
- reverse或残留处理；
- 不会开放MPS/MRP、BOM、生产计划或付款执行能力。

Planning 0005权限Seed继续保持C类排除。

## 八、Reverse/noop分类

扫描识别42个`RunPython.noop`候选：

- A类noop采用一次性隔离库销毁合同，不作生产回滚声明；
- B类noop必须补充残留对象、检测方法和补偿合同；
- C类noop禁止进入当前Replay。

R4要求每次使用新空库，因此不得依赖noop实现环境清理。

## 九、R5签署状态

| 字段 | 结果 |
|---|---|
| ALLOWLIST STATUS | `DRAFT` |
| Reviewer/Signer | `admin` |
| Signature Type | `Technical Allowlist Review Result` |
| Review Decision | `NOT READY — B类数据操作尚未完成函数级签署` |
| R5 Gate | `BLOCKED` |
| Execution Authorization | `NOT GRANTED` |

admin签名仅确认当前分类与阻断边界，不代表Migration执行授权。

## 十、Schema Fingerprint评审结果

admin已确认以下内容：

- Migration：app、name、dependencies、文件身份及数据操作白名单引用；
- Schema：table、column、type、nullable、default、主外键、index、constraint；
- 权限：permission、role、assignment稳定业务键；
- Seed：仅获批对象、数量、关键业务键及摘要；
- Normalization：UTF-8/LF、稳定排序、默认值规范化、时间/路径/SQLite物理差异处理；
- Comparator：两个独立空库F1/F2规范化JSON逐字节相同且SHA256一致；
- 输出格式：`PCE-SCHEMA-FINGERPRINT-V1`。

评审人：`admin`；日期：`2026-09-28`；决定：`APPROVED FOR REPLAY AUTHORIZATION PREPARATION`。

## 十一、R6状态

```text
R6 SCHEMA FINGERPRINT = READY
```

该状态仅表示Fingerprint标准完成技术评审，不代表Replay获准执行。

## 十二、Replay Gate状态

| Gate | 当前状态 |
|---|---|
| R0 | `READY` |
| R1 | `READY WITH REDESIGN REQUIRED` |
| R2 | `READY WITH EXCLUSION` |
| R3 | `READY` |
| R4 | `READY FOR AUTHORIZATION` |
| R5 | `BLOCKED` |
| R6 | `READY` |
| R7 | `READY` |

R4保持不变，Replay Authorization保持`NOT READY`。

## 十三、保护结果

- 未执行`migrate`、`sqlmigrate`、`makemigrations`或任何Migration；
- 未执行DDL/DML，未创建Replay数据库；
- 未修改Migration源码、依赖、模型、Schema、权限、Router或Registry；
- 未生成BOM、BOM Version、EngineeringMaterialRequirement、EngineeringOperationRequirement、ProductionPlan、MPS、MRP或APS；
- 正式数据库与C5数据库未被连接或写入。

## 十四、下一步需求

在进入隔离Replay执行前，必须继续完成22项B类操作的函数级评审与签署，使R5达到可授权状态；随后还需对R4执行环境进行独立授权并固定Allowlist与Fingerprint文件Hash。

## 十五、最终状态

```text
R5 DATA OPERATION ALLOWLIST = NOT READY
R6 SCHEMA FINGERPRINT = READY
REPLAY AUTHORIZATION = NOT READY
```

未声明`PHASE B READY`。

