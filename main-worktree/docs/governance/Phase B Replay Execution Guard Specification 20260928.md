# Phase B Replay Execution Guard Specification

## 1. 状态与目的

状态：`DESIGN ONLY — NOT IMPLEMENTED — NOT AUTHORIZED`

本规格定义未来Replay执行器的fail-closed合同，防止标准Migration流程误执行B/C节点或白名单外Data Operation。本任务不实现代码、不创建数据库、不执行Migration。

## 2. Authorized Migration Manifest

执行器启动前必须读取已签署的Execution Manifest，并校验：

1. Manifest ID、状态与签署；
2. Source Commit精确等于`969a86fe4a1b8557e8c837d19c58e9a9cc5d8fba`；
3. Target Schema Manifest ID；
4. R5 Allowlist SHA256精确等于`8FE570A22A78741E393F37E0EB0CE95E90D1D466177F2536698B56533D33B0D2`；
5. R6格式为`PCE-SCHEMA-FINGERPRINT-V1`；
6. 每个Migration文件Hash、直接依赖、Decision和目标叶节点；
7. Execution Manifest自身Hash与授权包一致。

任一字段缺失或Hash不一致，必须在加载Django和创建数据库之前失败。

## 3. Migration Allowlist Check

1. 只允许显式目标叶节点，禁止无目标全量`migrate`；
2. 在执行前使用Migration graph生成完整plan；
3. 生成plan必须与Manifest INCLUDE集合逐节点、逐顺序完全一致；
4. plan出现B、C、未知、缺失或未签署Migration时立即FAIL；
5. 依赖闭包不完整、出现替代历史链或运行时图与Manifest不同均立即FAIL；
6. 禁止通过`--fake`、`--fake-initial`或状态表预填绕过节点。

## 4. Data Operation Check

每个RunPython/RunSQL执行前必须验证：

- app、migration、operation index；
- operation类型；
- callable/SQL规范化Hash；
- R5 Decision必须为A；
- Evidence ID与签署Allowlist一致。

同一Migration只要含未授权Operation，整个Migration在preflight阶段FAIL；禁止跳过、降级或只执行部分operations。

## 5. R4隔离断言

执行器必须在创建数据库前验证临时绝对路径、唯一run-id、Source Commit、四份治理Hash、网络关闭、生产连接关闭、单一SQLite alias及受保护路径排除。R4授权栏未签署时必须FAIL。

## 6. 执行与Fingerprint

- F1和F2使用两个独立全新空库；
- 两次plan、Manifest、Allowlist和配置必须一致；
- 每次自然退出0后生成`PCE-SCHEMA-FINGERPRINT-V1`；
- F1规范化JSON必须逐字节等于F2，SHA256必须相同；
- 正式库与C5库前后Hash必须不变。

## 7. Fail Closed事件

未授权Migration、未授权Operation、依赖闭包不满足、Hash漂移、路径错误、连接受保护数据库、网络/生产能力开启、命令异常、Fingerprint差异或保护Hash变化，均必须立即FAIL，不得跳过、警告后继续或自动修正。

## 8. 实施前置条件

该Guard若进入实现，必须作为独立任务重新执行Frozen Shared Dependency预检、代码评审和自动化测试，并形成新的固定Source Commit。本规格本身不授权实现或Replay。

