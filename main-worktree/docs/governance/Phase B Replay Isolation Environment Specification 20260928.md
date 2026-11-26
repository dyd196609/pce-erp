# Replay Isolation Environment Specification

## 1. 目的与状态

本规格定义 Phase B Migration Replay 专用隔离环境的准备要求，不创建数据库、不执行 Migration，也不授权 Replay。

```text
R4 = READY FOR AUTHORIZATION
REPLAY EXECUTION = NOT AUTHORIZED
```

## 2. 数据库要求

### 2.1 允许的数据库

- 每次 Replay 必须创建全新的空数据库；
- 数据库必须位于独立临时根目录，例如 `%TEMP%\pce-phase-b-replay\<run-id>\replay.sqlite3`；
- `<run-id>` 必须唯一并记录创建时间、操作者、Source Commit 和授权编号；
- 第一次 Replay 与第二次 Replay 使用独立空数据库，禁止复用业务库或C5库；
- 文件创建、Migration执行和销毁只能在获得后续Replay授权后进行。

### 2.2 禁止的数据库与路径

严禁使用或连接：

- `D:\Dev-PCE\Acceptance\` 下任何数据库；
- `D:\Dev-PCE\Source\backend\db.sqlite3`；
- `D:\Dev-PCE\Source\backend\validation\c5\` 下任何C5资产；
- 任何由 `schema_editor` 直建的C5数据库；
- 当前工作区、工作树或正式业务目录内的数据库；
- 未被本次Replay授权清单明确登记的网络数据库、DSN或连接字符串。

## 3. 生命周期

| 阶段 | 要求 |
|---|---|
| PREPARED | 生成唯一run-id、解析临时绝对路径、记录保护Hash；不创建库 |
| AUTHORIZED | 获得独立Replay执行授权，冻结Source Commit、目标集合和白名单 |
| CREATED_EMPTY | 创建零字节/全新空库并证明此前不存在 |
| REPLAYING | 仅使用专用settings和单一连接；网络与生产连接关闭 |
| FINGERPRINTED | 输出规范化Manifest JSON及SHA256 |
| CLOSED | 关闭连接，记录文件Hash、日志Hash和退出码 |
| DISPOSED/ARCHIVED | 按授权决定安全删除临时库或连同证据归档；不得复制为业务库 |

## 4. 配置隔离

### 4.1 专用settings设计

未来Replay执行应使用专用设置入口（设计名称）：

```text
pce_backend.settings_replay
```

该设置只能继承必要的应用注册和Migration模块映射，不得继承业务数据库连接、缓存写入、任务队列、外部网络、邮件、银行接口或生产密钥。

### 4.2 强制环境变量

| 变量 | 约束 |
|---|---|
| `PCE_REPLAY_MODE` | 必须严格等于 `1` |
| `PCE_REPLAY_RUN_ID` | 非空、唯一、只允许安全字符 |
| `PCE_REPLAY_DB_PATH` | 必须为解析后的临时绝对路径 |
| `PCE_REPLAY_SOURCE_COMMIT` | 必须等于 `969a86fe4a1b8557e8c837d19c58e9a9cc5d8fba` |
| `PCE_REPLAY_ALLOW_NETWORK` | 必须等于 `0` |
| `PCE_REPLAY_ALLOW_PRODUCTION` | 必须等于 `0` |
| `PCE_REPLAY_ALLOW_SEEDLIST` | 必须引用已签署的R5白名单Hash；签署前为空并阻断 |

未设置、重复、相对路径、符号链接逃逸、UNC路径或非SQLite连接配置均应 fail closed。

## 5. 执行前安全断言设计

未来验证脚本必须在加载Django前完成以下检查：

1. 将候选路径解析为规范绝对路径，并解析符号链接/重解析点；
2. 断言目标文件不存在，父目录为本次新建临时目录；
3. 断言路径不等于且不位于以下根路径内：
   - `D:\Dev-PCE\Acceptance`；
   - `D:\Dev-PCE\Source`；
   - C5验证资产目录；
   - 用户配置的任何正式业务数据根目录；
4. 断言数据库引擎为本地SQLite且只有一个数据库alias；
5. 断言Source Commit、Manifest Hash、R5白名单Hash和R6规范Hash全部与授权记录一致；
6. 断言网络、生产密钥、异步任务和外部服务适配器全部关闭；
7. 任一断言失败时必须在创建数据库之前终止，退出码非零。

禁止以警告代替阻断，禁止自动修正到其他路径后继续。

## 6. 数据保护快照

准备时记录：

| 保护对象 | 路径 | SHA256 |
|---|---|---|
| 正式Acceptance数据库 | `D:\Dev-PCE\Acceptance\PDE-Operable-20260912\pde-operable-acceptance.sqlite3` | `734F5B7D4D2A345F925DC5E06B61FA46CF4F068E91362389A59E33C8732FEE7D` |
| C5 schema_editor数据库 | `D:\Dev-PCE\Source\backend\db.sqlite3` | `0840A70E7D2F3965FCFC038977841D9BABC0354101B5C7CCE14F89552FC39F67` |

Replay授权执行时必须在执行前后重新计算并比较两者Hash。Replay期间禁止打开、连接、复制、替换或写入这些文件。

## 7. 证据输出设计

每次获授权Replay必须输出：

- run-id与时间；
- Source Commit、Manifest Hash、白名单Hash、Fingerprint规范Hash；
- 解析后的临时数据库路径；
- 所有安全断言结果；
- 命令、退出码和日志Hash；
- F1/F2规范化Manifest及Hash；
- 正式库与C5库前后Hash；
- 临时库最终处置记录。

## 8. 授权栏

| 字段 | 内容 |
|---|---|
| R4 Status | `READY FOR AUTHORIZATION` |
| Environment Owner |  |
| Authorized Run Root |  |
| Authorization Reference |  |
| Signer |  |
| Date |  |

