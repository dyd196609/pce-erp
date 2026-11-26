# Phase B Replay Authorization Final Checklist

检查日期：2026-09-28

## 1. 基础身份

|项目|结果|
|---|---|
|Source Branch|`codex/manufacturing-baseline-convergence-20260927`|
|Source Commit|`969a86fe4a1b8557e8c837d19c58e9a9cc5d8fba`|
|Commit存在性|PASS；Git对象类型为`commit`|
|Branch包含性|PASS；`codex/manufacturing-baseline-convergence-20260927`、`codex/phase-b-source-governance`均包含该commit|
|Manifest ID|`PCE-PHASE-B-TARGET-SCHEMA-MANIFEST-V1.0-20260928`|
|检查性质|只读授权检查；未创建Replay数据库，未执行Migration|

## 2. R0-R7最终检查

|Gate|文档状态|最终检查|证据与结论|
|---|---|---|---|
|R0 Target Schema Manifest|`READY`|PASS WITH QUALIFICATION|状态为`TECHNICAL BASELINE SIGNED`，Signer为`admin`，Source Commit固定；但Target Schema Decision仍为`PARTIALLY RESOLVED`，只能结合R1/R2排除边界使用。|
|R1 PDE/PFM裁决|`READY WITH REDESIGN REQUIRED`|CONDITIONAL|PDE 0020–0022活动链已确认并保留历史追溯；PFM 0002为`REDESIGN REQUIRED`。当前Replay不得包含PFM 0002未批准重设计内容。PFM 0003直接依赖PFM 0002，依赖闭包尚未形成可执行集合。|
|R2 Planning方向|`READY WITH EXCLUSION`|CONDITIONAL|Planning 0005明确排除；Planning 0006直接依赖0005且须重新设计。当前Replay不得包含0005、0006、MPS/MRP结构、权限或生成能力。|
|R3 Source Commit|`READY`|PASS|commit存在，固定身份与Manifest一致；当前主工作区位于`master`，未来Replay必须从固定commit的独立受控环境执行。|
|R4 Replay隔离环境|`READY FOR AUTHORIZATION`|BLOCKED|规格已完成，但Environment Owner、Authorized Run Root、Authorization Reference、Signer、Date为空；固定commit内不存在`pce_backend.settings_replay`、路径安全断言或Allowlist执行门禁实现。|
|R5 Data Operation Allowlist|`READY`|DOCUMENT PASS / EXECUTION BLOCKED|Allowlist签署与Hash通过，A=136、B=3、C=14；但没有可执行机制保证标准Migration运行时跳过B/C操作。多个B/C操作位于后续Migration的必经依赖链。|
|R6 Schema Fingerprint|`READY`|PASS|格式为`PCE-SCHEMA-FINGERPRINT-V1`，范围、Normalization及F1/F2 Comparator已签署。规范SHA256：`5C3E3C60CE7D0C1413CD2BD758139C6F2957381F155339F318E86D2C0B2F0BA1`。|
|R7 数据保护|`READY`|PASS|正式库及C5库SHA256与保护值一致。|

## 3. 签署与Hash校验

|对象|校验结果|
|---|---|
|Target Schema签署表|SHA256 `02B0913BC2AE917AB7E47412EE7A6F4AF2F984EF5EBD9ABACAB49C066DB6580A`；admin签署存在|
|Replay隔离规格|SHA256 `D2C67803CA41966003BDA9834FBB293E53A7BCAEA663F8F928B10A35B14EDAEF`；授权栏未签署|
|R5 Allowlist|SHA256 `8FE570A22A78741E393F37E0EB0CE95E90D1D466177F2536698B56533D33B0D2`；签署状态`TECHNICAL BASELINE SIGNED`|
|R6 Fingerprint规范|SHA256 `5C3E3C60CE7D0C1413CD2BD758139C6F2957381F155339F318E86D2C0B2F0BA1`；状态`READY`|

## 4. Allowlist执行闭包检查

结论：`NO`，当前尚不能证明“执行时不存在超出Allowlist的操作”。

静态事实：

1. `planning.0002`包含C类RunPython，`planning.0003`直接依赖`planning.0002`；
2. `planning.0005`为B类且被Target Schema排除，`planning.0006`直接依赖`planning.0005`；
3. `pfm.0002`包含C类RunPython且标记`REDESIGN REQUIRED`，`pfm.0003`直接依赖`pfm.0002`；
4. `sales.0001`为B类数据操作，但`planning.0003`和`sales.0002`等后续节点依赖该Migration；
5. PDE链存在多个C类RunPython节点，后续Schema节点沿该链继续依赖；
6. 固定commit内未发现专用Replay settings、安全断言或基于签署Hash的操作级执行门禁。

标准Django Migration会执行Migration文件中的全部operations；当前证据不能同时保证后续Schema节点可达和B/C数据操作不执行。

## 5. 最终检查结论

```text
REPLAY AUTHORIZATION CHECK = BLOCKED
REPLAY AUTHORIZATION = NOT READY
```

本结论不影响R5文档签署和R6标准就绪状态，但禁止进入隔离数据库Migration Replay执行。
