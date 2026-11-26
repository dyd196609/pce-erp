# 《Phase B New Controlled Protection Baseline建立准备 详细检查表附录》

日期：2026-09-29  
性质：主报告的受控设计附录；不是执行指令  
主报告：`Phase B New Controlled Protection Baseline建立准备 FINAL报告 20260929.md`

## 一、Baseline Readiness逐项清单

### 1.1 文件与SQLite身份

- [ ] 候选文件位于批准Generation输出路径；
- [ ] 文件长度、CreationTime、冻结时间、File ID和SHA256已记录；
- [ ] Validation副本SHA256与Generation输出一致；
- [ ] 无`-wal`、`-shm`、`-journal`和活动写句柄；
- [ ] `integrity_check`和`quick_check`均为`ok`；
- [ ] page/freelist/schema/user/application版本及journal mode已记录；
- [ ] Hash计算与批准/签署明确分离。

### 1.2 Schema对象和表结构

- [ ] `sqlite_master`全部table/index/view/trigger清单已规范化签名；
- [ ] 各对象类型分别有数量和SHA256；
- [ ] 每表列名、类型、NULL、默认值、主键、外键签名已生成；
- [ ] 索引列、唯一性、部分索引条件和触发器SQL已纳入签名；
- [ ] 不存在未批准、缺失或重名对象；
- [ ] Schema合同版本与候选身份绑定。

### 1.3 Migration状态

- [ ] `django_migrations`完整清单、数量、最大时间和规范化Hash已记录；
- [ ] 实际Migration集合与批准Manifest逐项相等；
- [ ] 无fake、未授权节点、缺失依赖或分叉叶节点；
- [ ] Migration源码版本、Commit和文件Hash已绑定；
- [ ] 数据Migration输入、输出、幂等性和审计结果可证明；
- [ ] 候选建立完成后未再运行Migration。

### 1.4 表内容和关键业务事实

- [ ] 全部非系统表行数和每表规范内容Hash已生成；
- [ ] 固定列/主键顺序及类型化编码覆盖NULL/TEXT/INTEGER/REAL/BLOB；
- [ ] 无主键表使用明确可重复的全行排序规则；
- [ ] 关键事实覆盖Sales、CRM、Procurement、Inventory、PDE、BOM、Production、Planning、PFM；
- [ ] 数量、状态、来源关系、审批/转换历史和禁止对象均有期望与实际；
- [ ] 来源标记为SOURCE/FORMAL/SYSTEM_DERIVED，不以Preview或模拟数据冒充；
- [ ] Session、登录、Token、缓存等运行期数据策略由合同预先明确。

### 1.5 权限与组织模型

- [ ] 用户、角色、权限、菜单、角色权限/菜单和用户范围均有清单与内容Hash；
- [ ] 公司、组织单元、部门、岗位、职责、团队及组织审计均有清单与内容Hash；
- [ ] 权限和组织事实来自批准权威源；
- [ ] 不存在孤立引用、越权角色、未知范围或临时管理员；
- [ ] 职责分离检查通过并形成独立报告；
- [ ] 权限/组织变化会使候选签名失效并要求重新验证。

## 二、Evidence Package逐项要求

| 工件 | 最低内容 |
|---|---|
| Historical Evidence Manifest | 734F、ABA、三份报告路径/Hash/保留状态 |
| Source Qualification Record | 来源身份、链路、责任人、资格Gate |
| Environment Isolation Record | 五类环境身份、deny-list、运行策略 |
| Candidate Build Manifest | 输入、Runner、Commit、时间、输出身份 |
| SQLite Identity Report | 文件元数据、PRAGMA、integrity结果 |
| Schema Signature Report | 对象、表结构、索引、视图、触发器签名 |
| Migration Manifest | 允许清单、实际清单、源码Hash和差异 |
| Data Fact Manifest | 全表行数、内容Hash、关键业务事实 |
| Permission/Organization Manifest | 权限、角色、范围、组织和职责分离 |
| Recovery Verification Report | 恢复副本身份、比对和失败结果 |
| Responsibility Sign-off | 四角色身份、时间和冲突检查 |
| Sealed Baseline Manifest | Baseline ID、版本、最终Hash、位置和状态 |

每项必须包含自身SHA256、格式版本、生成工具Hash、生成时间、操作者和上游工件Hash。

## 三、Recovery Verification逐项清单

### 3.1 保存副本

- [ ] Primary及至少两个一致副本已登记；
- [ ] 至少一个副本处于独立离线或不同故障域；
- [ ] 每份记录ID、版本、SHA256、长度、位置、保管人和介质状态；
- [ ] 保存目录禁止应用运行、登录、Migration和自动清理；
- [ ] 历史版本只追加、不覆盖，并记录`supersedes`。

### 3.2 恢复通过条件

- [ ] 恢复文件SHA256和长度等于Signed Baseline Manifest；
- [ ] integrity和quick_check通过；
- [ ] Schema、Migration、每表内容Hash、权限组织和关键事实全部一致；
- [ ] 恢复过程未修改Primary或保存副本；
- [ ] 已从非Primary故障域完成至少一次恢复；
- [ ] Technical Reviewer已独立签署。

### 3.3 失败回退

- [ ] 标记Recovery Gate FAIL并保持技术阻断；
- [ ] 隔离失败恢复副本，不修补或回写封存件；
- [ ] 保存日志、介质身份、命令、操作者和时间；
- [ ] 禁止改用ABA、开发库或未经批准副本；
- [ ] 根因分类为介质、传输、Manifest或候选可信问题；
- [ ] 修正需创建新候选并从Source Qualification重新开始；
- [ ] 未经授权不删除失败证据。

## 四、附录保护状态

```text
CHECKLIST DESIGN ONLY = YES
BASELINE FILE CREATED = NO
DATABASE CHANGED = NO
HASH SIGNED = NO
ACCEPTANCE INITIALIZED = NO
```
