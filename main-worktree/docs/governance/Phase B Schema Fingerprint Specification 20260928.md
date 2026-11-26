# Schema Fingerprint Specification

## 1. 目的与状态

本规格定义隔离Replay结果的确定性比较合同。它是待评审标准，不代表已执行或通过Replay。

```text
R6 = READY
FINGERPRINT ACCEPTANCE = SIGNED
```

## 2. Fingerprint范围

### 2.1 Migration集合

每个节点记录：

- `app`；
- `migration_name`；
- 直接`dependencies`，按`app/name`排序；
- 源文件SHA256或Git blob；
- 是否包含RunPython、RunSQL及其获批白名单ID；
- 是否为目标叶节点。

### 2.2 Schema

每张表记录：

- table name；
- column name、逻辑type、长度/精度；
- nullable；
- 规范化default；
- primary key；
- foreign key目标、列及删除规则；
- index名称、唯一性、列顺序与条件；
- unique/check等constraint名称与规范化表达式。

### 2.3 权限

仅记录目标Manifest和R5白名单允许的对象：

- permission稳定业务编码、名称、模块；
- role稳定业务编码；
- role-permission assignment的业务键；
- 其他获批scope assignment业务键。

不得以数据库自增ID作为主要比较键。

### 2.4 Seed

每项获批seed记录：

- allowlist ID；
- 对象类型；
- 稳定业务键；
- 记录数量；
- 关键业务字段的规范化摘要；
- 反向/残留合同状态。

未在R5签署白名单中的seed不得执行，也不得出现在可接受Fingerprint中。

## 3. 标准化规则

1. 输出编码为UTF-8，无BOM，换行统一LF。
2. JSON对象键按Unicode代码点升序排列。
3. app、migration、table、column、index、constraint、permission、role集合按稳定业务键升序排列。
4. 依赖、索引列和复合约束字段保留语义顺序；其他无序集合排序。
5. 布尔值使用JSON `true/false`，空值使用`null`，数字禁止字符串化。
6. 默认值必须表示为规范化逻辑值或稳定表达式；禁止记录数据库内存地址、Python对象repr或运行时间。
7. SQL表达式先统一空白、引号策略和大小写策略，但不得丢失语义。
8. 路径、用户名、机器名、连接字符串、生成时间和数据库文件物理属性不得进入逻辑Fingerprint。
9. 忽略SQLite内部对象，如`sqlite_sequence`和页面布局；不得忽略业务表、逻辑默认值、约束或索引。
10. `django_migrations`逐行记录不作为Schema表内容比较，但其目标Migration集合必须在`migrations`区完整记录。
11. 最终摘要为规范化JSON字节的SHA256大写十六进制值。

## 4. Manifest JSON结构

```json
{
  "format": "PCE-SCHEMA-FINGERPRINT-V1",
  "sourceCommit": "969a86fe4a1b8557e8c837d19c58e9a9cc5d8fba",
  "targetManifestId": "PCE-PHASE-B-TARGET-SCHEMA-MANIFEST-V1.0-20260928",
  "migrations": [],
  "schema": {
    "tables": []
  },
  "permissions": [],
  "roles": [],
  "assignments": [],
  "seeds": [],
  "summarySha256": ""
}
```

`summarySha256`计算时该字段必须暂置为空字符串，避免自引用。

## 5. Acceptance Comparator

### 5.1 F1与F2

- F1：在第一个全新隔离空数据库上按签署目标集合完成第一次Replay后生成的规范化Manifest。
- F2：在第二个独立、全新隔离空数据库上使用相同Source Commit、Manifest、R5白名单和配置完成第二次Replay后生成的规范化Manifest。
- 两次执行不得共享数据库文件、seed缓存或业务数据。

### 5.2 通过条件

必须同时满足：

1. 两次Replay均自然退出0；
2. F1与F2的规范化JSON逐字节相同；
3. `SHA256(F1) = SHA256(F2)`；
4. Migration集合、表、字段、索引、约束、权限、角色、assignment与seed均无未解释差异；
5. 正式数据库和C5数据库前后Hash不变；
6. 无白名单外RunPython、RunSQL或seed执行。

任一不满足均为`FAIL/BLOCKED`，不得用差异忽略规则临时放行。

## 6. 差异输出

Comparator必须输出机器可读差异，至少包括：

- JSON Pointer路径；
- F1值与F2值；
- 差异类型（missing/extra/changed/order）；
- 所属Migration或表；
- 是否命中允许忽略项；
- 最终判定。

允许忽略项只能来自已签署规范，运行时不得新增。

## 7. 评审签署区

| 字段 | 内容 |
|---|---|
| R6 Status | `READY` |
| Format | `PCE-SCHEMA-FINGERPRINT-V1` |
| Comparator Rule | `F1 canonical JSON bytes = F2 canonical JSON bytes` |
| Reviewer | `admin` |
| Decision | `APPROVED FOR REPLAY AUTHORIZATION PREPARATION` |
| Signature Date | `2026-09-28` |
| Evidence Reference | `Phase B Schema Fingerprint Specification 20260928` |

该签署确认Fingerprint范围、标准化规则、F1/F2 Comparator和输出格式，不授权创建数据库或执行Replay。

