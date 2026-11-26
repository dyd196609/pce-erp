# Phase B Target Schema Manifest决策签署准备 FINAL / CONSOLIDATED报告

## 一、任务范围

本任务仅整理 Migration 历史证据、决策选项、签署位置与 Replay 前置 Gate，形成架构治理责任人可审阅的 Target Schema Manifest 草案。未修改 Migration、模型、Schema、权限、Router、Registry、数据库或 C5 验证资产；未执行 `migrate`、`sqlmigrate`、`makemigrations`、DDL 或 DML。

## 二、治理读取结果

### COMPLETED MODULE GOVERNANCE READING RECEIPT

| 项目 | 结果 |
|---|---|
| Preservation Standard | 已全文读取 `PCE 已开发模块固化与变更保护规范 V1.0` |
| Registry | `completed_module_registry.v1.json` 解析通过，共 34 项 |
| Preflight | 已全文执行 `COMPLETED_MODULE_PROTECTION_PREFLIGHT_V1` 的只读判定 |
| Frozen Core | 本任务未修改任何 Frozen Core |
| Frozen Shared Dependency | 本任务未修改任何 Frozen Shared Dependency |
| Affected Frozen Modules | 无源码、API、页面、路由、权限、Workflow、DB/API/UI identity 变更 |
| Freeze Contracts | 本任务无需要进入修改流程的 Module Freeze Contract |
| Unfreeze Authorization | 不需要；范围仅为新增治理文档 |
| 保护等级 | Level C：Migration/架构治理证据；`SAFE TO MODIFY DOCUMENTATION ONLY` |

治理文件读取范围：

1. `D:\Dev-PCE\AGENTS.md`
2. `D:\Dev-PCE\Source\AGENTS.md`
3. `docs/governance/PCE CODEX开发指令规范管理V1.2.md`
4. `docs/governance/PCE 已开发模块固化与变更保护规范 V1.0.md`
5. `docs/governance/completed_module_registry.v1.json`
6. `docs/governance/COMPLETED_MODULE_PROTECTION_PREFLIGHT_V1.md`

## 三、Manifest Draft

已生成《Phase B Target Schema Manifest V1.0 Draft》，包含：

- Manifest ID、目标版本、source branch/commit、状态、Decision Owner 与空白签署栏；
- 应用、Migration、Schema、Permission 与 Seed 范围；
- BOM、工序需求、ProductionPlan、MPS/MRP/APS 执行和正式数据转换的明确排除项；
- PDE、PFM、Planning 决策区；
- R0–R7 Replay Authorization Gate；
- 总体签署栏。

Manifest 状态固定为 `DRAFT_PENDING_ARCHITECTURE_DECISION`，未填写 Signer、Signature Date 或最终 Decision。

## 四、PDE决策材料

PDE 0020、0021、0022 均记录了活动与历史候选的 commit、blob、SHA256、dependencies、Schema 影响、数据影响、RunPython 影响和与正式事实的关系。

每项均提供但未选择：

- OPTION A：`INCLUDE ACTIVE`
- OPTION B：`ARCHIVE HISTORY`
- OPTION C：`REDESIGN REQUIRED`

每项 Decision、Signer、Date 均保持空白。现有证据能证明 Git 候选身份，但不能证明任一候选就是唯一部署字节来源，因此不得自动裁决。

## 五、PFM决策材料

已对 `0002_employee_formal_organization_relations` 与历史 `0002_initial` 的 Schema、数据迁移、RunPython、Git 来源和正式应用证据进行并列整理。

提供但未选择：

- OPTION A：`ACTIVE KEEP`
- OPTION B：`HISTORY ARCHIVE`
- OPTION C：`REDESIGN REQUIRED`

Decision、Signer、Date 保持空白。正式应用时间与候选 Git 时间之间存在不能由当前证据消除的差异。

## 六、Planning决策材料

已确认：

- Planning 0005 创建 MPS/MRP 五类表结构并执行角色/权限 seed；其 reverse 为 noop。
- 当前收敛后的 Planning 0006 依赖 Planning 0005，并同时依赖 PDE、Masterdata、MES 叶节点。
- 当前 0006 的收敛文件与原 Phase A 证据文件不是同一 blob，二者来源均已列明。

已提供两个架构选项：

- OPTION A：接受 0005 进入目标 Schema，但业务执行继续关闭，并显式治理权限 seed 与回滚残留。
- OPTION B：排除 0005，继续关闭 MPS/MRP，并在独立授权任务中重新设计 0006 依赖。

当前 Decision 为 `PENDING ARCHITECTURE DECISION`，Signer 与 Date 为空。

## 七、Replay Gate

| Gate | 结果 | 说明 |
|---|---|---|
| R0 Target Schema Manifest Signed | `BLOCKED` | Manifest 尚未签署 |
| R1 PDE/PFM历史来源裁决 | `BLOCKED` | 决策栏为空 |
| R2 Planning方向确认 | `BLOCKED` | 0005/0006 方向未签署 |
| R3 Source Commit固定 | `READY` | 集成分支已识别；执行前仍须固定并校验完整 SHA |
| R4 Replay隔离环境 | `PENDING` | 未建立本次专用空数据库 |
| R5 RunPython/Seed白名单 | `BLOCKED` | 白名单依赖 R1/R2 决策 |
| R6 Schema Fingerprint标准 | `PENDING` | 范围已列出，规则待签署 |
| R7数据保护Hash | `READY` | 正式数据库保护 SHA 已记录 |

## 八、Architecture Decision Summary

当前不能 Replay 的根本原因不是静态图无法读取，而是唯一目标 Schema 未被签署。活动源码、历史 Migration、正式数据库事实和 C5 模型直建库分别属于源码事实、历史事实、部署事实和运行验证事实，不能混为同一证据。

推荐讨论顺序：先确定业务边界，再决定 Planning 0005/0006，随后逐项裁决 PDE 与 PFM，形成 RunPython/seed 白名单，固定完整源码 commit 和 fingerprint 标准，最后签署 Manifest 并另行授权隔离 Replay。

## 九、待签署事项

1. PDE 0020 的活动/历史/重设计方向。
2. PDE 0021 的活动/历史/重设计方向。
3. PDE 0022 的活动/历史/重设计方向。
4. PFM 0002 的活动保留/历史归档/重设计方向。
5. Planning 0005 纳入或排除及 0006 的依赖处理方向。
6. RunPython/seed 白名单。
7. Schema fingerprint 标准。
8. Target Schema Manifest 总体签署。

## 十、下一步授权需求

下一步必须由架构治理责任人完成上述决策与 Manifest 签署。全部 R0–R7 条件达到可执行状态后，方可另行申请《Phase B隔离数据库Migration Replay验证执行指令》。本报告不包含 Replay、Schema、Migration 或 Phase B 业务实施授权。

## 十一、保护与禁止事项确认

- Migration 文件：未修改、未创建、未合并、未删除。
- Migration 命令：未执行。
- 正式数据库与 C5 数据库：未打开写入、未执行 DDL/DML。
- 模型、Schema、权限、Router、Registry：未修改。
- BOM、BOM Version、EngineeringMaterialRequirement、EngineeringOperationRequirement、ProductionPlan、MPS、MRP、APS：未生成或执行。
- 签署字段：未代填。

## 十二、最终状态

```text
TARGET SCHEMA MANIFEST PREPARATION = PASS
TARGET SCHEMA DECISION = UNRESOLVED
REPLAY AUTHORIZATION = NOT READY
```

`PHASE B READY` 未被声明。

