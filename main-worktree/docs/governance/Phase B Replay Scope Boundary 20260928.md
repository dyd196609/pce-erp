# Phase B Replay Scope Boundary

状态：`DRAFT — EXECUTION MANIFEST PREPARED — NOT AUTHORIZED FOR EXECUTION`

## 1. 允许范围（仅在后续重新授权后）

1. 已签署Target Schema Manifest最终执行集合内的Migration；
2. R5 Allowlist中A类136项数据操作；
3. R6 `PCE-SCHEMA-FINGERPRINT-V1`的F1/F2生成与比较；
4. 位于独立临时根目录的两个全新空SQLite数据库；
5. 固定Source Commit、Manifest Hash、Allowlist Hash及Fingerprint规范Hash。

## 2. 明确禁止范围

1. 正式数据库、Acceptance数据库、C5数据库及工作区业务数据库；
2. R5 B类3项和C类14项数据操作；
3. PFM 0002现有未批准实现及依赖它的未收敛链；
4. Planning 0005、当前依赖Planning 0005的Planning 0006；
5. MPS/MRP结构、权限、Seed与生成能力；
6. BOM、BOM Version、EngineeringMaterialRequirement、EngineeringOperationRequirement；
7. ProductionPlan、APS及正式制造数据；
8. 白名单外RunPython、RunSQL、Seed、Permission Seed、Role Seed或组织Seed。

## 3. Execution Manifest治理结果

已生成`PCE-PHASE-B-REPLAY-EXECUTION-MANIFEST-V1.0-20260928`，Source Commit为`969a86fe4a1b8557e8c837d19c58e9a9cc5d8fba`。当前状态仍为`DRAFT`：

|项目|数量|
|---|---:|
|Migration总节点|153|
|INCLUDE FOR REPLAY|74|
|EXCLUDE FROM REPLAY|3|
|REDESIGN REQUIRED|76|
|原A因B/C依赖传播被阻断|62|
|当前DRAFT可达叶节点|9|

Manifest已经逐节点列明Migration身份、依赖、Operation Class、Decision与原因，但依赖闭包结论为`BLOCKED`。不得用无目标标准`migrate`执行全部叶节点，也不得把DRAFT叶节点解释为授权目标。

在以下条件完成前禁止Replay：

- 62个传播阻断项完成架构裁决；
- Dependency Closure转为PASS；
- Guard完成实现、测试并进入新的固定commit；
- Manifest与Scope Boundary共同签署；
- R4执行参数与责任人完成授权。

## 4. 未来失败标准

任一条件发生即`FAIL/BLOCKED`：

1. 数据库路径不属于已授权临时根目录；
2. 访问正式数据库、Acceptance数据库、C5数据库或工作区业务数据库；
3. 执行未列入最终执行Manifest的Migration；
4. 执行R5 B/C项或任何白名单外数据操作；
5. 执行Planning 0005/0006当前链或PFM 0002/0003当前未收敛链；
6. F1与F2规范化JSON或SHA256不一致；
7. 正式库或C5库保护Hash变化；
8. 安全断言、Migration、Comparator或Hash检查非自然退出0；
9. 发生网络访问、生产密钥加载、业务数据初始化或制造业务输出。

## 5. 当前状态

```text
REPLAY SCOPE BOUNDARY = DEFINED BUT NOT EXECUTABLE
REPLAY AUTHORIZATION = NOT READY
```
