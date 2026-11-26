# Phase B Architecture Decision Summary for Signature

## 1. 当前为什么不能 Replay

Migration 静态图可读取不代表目标 Schema 已裁决。目前存在三类未签署分歧：

1. PDE 0020–0022 各有同号、不同语义的活动链与历史链。
2. PFM 0002 活动候选与历史候选在 Schema、数据迁移和证据时间上不一致。
3. Planning 0006 当前依赖 Planning 0005，而 0005 会引入 MPS/MRP 表和权限 seed；是否纳入目标 Schema 未决。

此外，RunPython/seed 白名单、隔离环境和 Schema fingerprint 标准尚未全部签署。因此当前执行 Replay 会把架构决策隐式交给执行顺序，不能形成可信基线。

## 2. 当前为什么不能自动选择 Migration

- 同一编号不等于同一文件、同一依赖或同一业务语义。
- 当前活动文件只能证明“源码事实”；Git 历史候选只能证明“历史事实”；正式库记录只能证明“部署事实”。
- 没有部署字节身份时，不能依据 Migration 名称推定具体候选。
- 正式数据库可运行不等于 clean database 能按某条候选链重放。
- C5 模型直建库证明运行加载能力，不是 Migration replay 证据。
- 自动选择会同时决定未来审计解释、权限 seed、反向行为和历史保留方式，必须由架构治理责任人签署。

## 3. 决策选项影响

### PDE 0020–0022

- `INCLUDE ACTIVE`：当前活动语义进入目标集合；历史结构不会因此自动恢复。
- `ARCHIVE HISTORY`：历史候选仅保留为审计证据，不进入活动 Migration 目录。
- `REDESIGN REQUIRED`：以新 Migration 承接目标语义；需要独立编号、设计、评审和授权。

### PFM 0002

- `ACTIVE KEEP`：保留当前正式组织关系迁移候选，同时接受其 RunPython 与反向 noop 的治理责任。
- `HISTORY ARCHIVE`：历史 `0002_initial` 仅保存证据，避免两个 0002 同时成为活动来源。
- `REDESIGN REQUIRED`：重新设计收敛链；完成前 PFM Replay 范围保持阻断。

### Planning 0005/0006

- `ACCEPT PLANNING 0005`：MPS/MRP 表和权限模型进入 Target Schema，但执行能力必须继续关闭；需签署回滚与 seed 残留合同。
- `EXCLUDE PLANNING 0005`：MPS/MRP 不进入本轮 Target Schema；需要独立授权重新设计 0006 依赖，完成前 0006 暂缓 Replay。

### RunPython/Seed

批准执行不应是全局布尔值。每个数据操作都应有对象范围、幂等条件、反向合同、残留处理和证据 Hash；未列入白名单的操作不得运行。

### Schema Fingerprint

签署标准决定 Replay 的验收口径。若未固定规范化格式、默认值表达、索引顺序、约束、权限及 seed 结果，两个环境即使逻辑相近也无法证明“same schema / same baseline”。

## 4. 建议签署顺序

1. 确认 Manifest 基础信息、Source Commit 和明确排除范围。
2. 决定 Planning 0005/0006 方向，先固定目标集合的最大边界。
3. 逐项签署 PDE 0020、0021、0022。
4. 签署 PFM 0002 收敛方向。
5. 依据上述决策形成并签署 RunPython/seed 白名单。
6. 签署 Schema fingerprint 格式、规范化规则和比较器。
7. 验收 Replay 专用隔离环境与正式数据库保护 Hash。
8. 完成 Manifest 总体签署，再单独申请 Replay 执行授权。

## 5. 当前结论

本摘要仅提供事实和影响分析，不推荐或代替任何最终决策。

```text
TARGET SCHEMA DECISION = UNRESOLVED
REPLAY AUTHORIZATION = NOT READY
```

