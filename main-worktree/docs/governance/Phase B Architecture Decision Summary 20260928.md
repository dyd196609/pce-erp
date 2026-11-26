# Phase B Architecture Decision Summary

## 1. 当前为什么不能 Replay

当前静态 Migration 图可读取，不等于目标 Schema 已经确定。Replay 仍被以下事实阻断：

1. PDE 0020–0022 存在两条同号但语义完全不同的历史链，不能同时作为同一活动图的唯一来源。
2. PFM 0002 的活动文件与历史候选在 Schema、数据迁移和时间证据上不一致，部署字节身份未被证明。
3. Planning 0006 当前依赖 Planning 0005，而 0005 会引入 MPS/MRP 结构及权限 seed；是否纳入目标 Schema 尚未获得架构决策。
4. RunPython/seed 白名单尚未签署，部分反向函数为 noop，无法提前宣称可逆。
5. Schema fingerprint 的确定性序列化与比对标准尚未签署，Replay 结果没有唯一验收基准。

因此，当前执行 Replay 会把“选择目标 Schema”的架构决策隐式交给 Migration 执行顺序，违反治理边界。

## 2. 当前为什么不能自动选择 Migration

- Migration 名称或编号相同不代表文件语义、依赖或部署字节相同。
- 当前活动源码是“源码事实”，历史文件是“Git 历史事实”，正式数据库记录是“部署事实”；三者不能互相替代。
- 数据库可运行只证明当前实例可用，不能证明从空库重放时应选择哪条历史链。
- C5 模型直建库是运行验证事实，不是 Migration replay 证据。
- 选择任何候选都会改变未来唯一迁移链、回滚责任和审计解释，必须由架构治理责任人签署。

## 3. 各方案影响

### 3.1 PDE 0020–0022

- `INCLUDE ACTIVE`：目标 Schema 采用当前活动链，但仍需证明与领域边界和正式事实的兼容性。
- `ARCHIVE HISTORY`：历史链保留证据、不进入活动目录；不会自动补回历史结构。
- `REDESIGN REQUIRED`：以新的受控 Migration 承接目标语义；需要独立设计、编号、评审和授权。

### 3.2 PFM 0002

- `ACTIVE KEEP`：保留当前组织关系语义，但 RunPython 及 noop 反向行为必须纳入风险与白名单。
- `HISTORY ARCHIVE`：历史 `0002_initial` 只保留证据，不能以同号文件共同进入活动目录。
- `REDESIGN REQUIRED`：另行设计收敛路径；在完成前 PFM Replay 目标不完整。

### 3.3 Planning 0005/0006

- 接受 0005：结构上纳入 MPS/MRP 与权限 seed，但业务执行仍必须关闭；回滚与权限残留风险需要显式接受。
- 排除 0005：保持 MPS/MRP 不进入本轮目标 Schema，但必须独立重设计 0006 依赖，未完成前 0006 暂缓 Replay。

## 4. 推荐讨论顺序

1. 先确定 Target Schema 的业务边界与明确排除项。
2. 决定 Planning 0005/0006 方向，因为它直接改变目标集合与权限 seed 范围。
3. 对 PDE 0020–0022 按编号逐项裁决活动链、历史归档或重新设计。
4. 裁决 PFM 0002，并明确数据迁移与反向 noop 的接受条件。
5. 基于上述结果形成 RunPython/seed 白名单。
6. 固定完整 source commit 与 Migration 文件 Hash 清单。
7. 签署 Schema fingerprint 标准与隔离环境要求。
8. 最后签署 Target Schema Manifest，并另行授权隔离 Replay。

## 5. 待签署事项

| 事项 | 当前状态 |
|---|---|
| PDE 0020 决策 | 空白，待架构签署 |
| PDE 0021 决策 | 空白，待架构签署 |
| PDE 0022 决策 | 空白，待架构签署 |
| PFM 0002 决策 | 空白，待架构签署 |
| Planning 0005/0006 方向 | `PENDING ARCHITECTURE DECISION` |
| RunPython/seed 白名单 | `BLOCKED` |
| Schema fingerprint 标准 | `PENDING` |
| Manifest 总体签署 | 空白，待架构签署 |

本摘要不推荐或代替任何最终选项，不构成 Replay 授权。

