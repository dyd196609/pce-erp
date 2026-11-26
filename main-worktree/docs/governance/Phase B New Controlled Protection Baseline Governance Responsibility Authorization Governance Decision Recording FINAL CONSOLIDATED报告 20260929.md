# FINAL / CONSOLIDATED

# 《Phase B New Controlled Protection Baseline Governance Responsibility Authorization Governance Decision Recording FINAL / CONSOLIDATED报告》

日期：2026-09-29  
阶段：Governance Decision Recording 结构与验证规则设计  
对象：Proposal-bound Governance Responsibility Authorization Layer（GRA）  
Proposal：`NCPSB-SP-A-20260929-001`  
Logical Source：`PCE-NCPB-A-REBUILD-SOURCE-P01`  
Review Level：B；Full Content Review Required：NO  
最终 Gate：`GOVERNANCE DECISION RECORDING READY`

## 一、范围与证据前态

本轮承接《Governance Responsibility Authorization Governance Decision Preparation FINAL / CONSOLIDATED报告》中的 D-01～D-07 待决事项，以及 Layer Design、Detailed Design、Governance & Architecture Review。只定义未来正式裁决原件的记录结构、真实性验证和状态转换；**不代替治理主体填写任何选项，也不建立一条已裁决记录**。当前独立治理裁决原件为 0；`HC-01`～`HC-04` 缺真实任命，`GAP-01`～`GAP-04` 未关闭；Source Qualification Review Pre-check 仍为 `NOT READY`。734F 和 ABA 仍分别是历史固定证据与漂移后历史证据，不是本 Proposal 的未来 Source。

```text
EFFECTIVE INSTRUCTION SET
ACTIVE = 决策登记逻辑结构、D-01~D-07 待决目录、验证/状态规则；仅新增本报告
FROZEN = 734F/ABA 历史边界；既有组织、身份、系统权限和 Workflow 权威；开放的 HC/GAP
NOT AUTHORIZED = 填写裁决、指定决策人、签发 Authorization ID、GRA/Registry 数据、审批、代码/数据库/权限修改、Migration、Source/Baseline 创建

INSTRUCTION CONTROL SHEET
Original Goal = 建立可验证的 Governance Decision Record 结构
Current Goal = 记录字段、待决目录、真实性 Gate、追加式生命周期及下游边界
IN SCOPE = 已有报告只读汇总；本报告
OUT OF SCOPE = 正式裁决、原件受理、实施、数据库或运行环境创建
Database Boundary = 不连接数据库
Non-Regression Baseline = 组织权限、登录、Workflow、现有菜单/Route/API 及已开发模块不变
User Acceptance Path = N/A（无 UI 交付）
Stop Condition = 报告回读后停止；等待独立原件
```

```text
COMPLETED MODULE GOVERNANCE READING RECEIPT
Project Instructions = D:\Dev-PCE\AGENTS.md; D:\Dev-PCE\Source\AGENTS.md
Formal Governance Standard = D:\Dev-PCE\Source\docs\governance\PCE CODEX开发指令规范管理V1.2.md
Preservation Standard Read = YES
Completed Module Registry Read = YES
Registry Module Count = 34
Affected Frozen Modules = []
Freeze Contracts Read = []
Unfreeze Authorization = NO / NOT REQUIRED FOR THIS DOCUMENT-ONLY TASK
Preflight = SAFE TO MODIFY (new report only)
```

本轮仅新增文档，不命中 Frozen Core 或共享依赖的实现修改。未来任何代码/Schema/UI 任务须按拟改文件重新预检，不能沿用本轮结论。

## 二、Governance Decision Record 逻辑结构

以下是**字段契约**，不是数据库表、正式 Decision 实例或待填模板的签署页。实际值只能从独立治理原件及权威只读核验中取得；本报告不生成 Decision ID、Authorization ID、人员、时间或 Hash。

| 字段组 | 必填字段 | 验证目的与约束 |
|---|---|---|
| 基础身份 | Decision ID、Decision Version、Proposal ID、Logical Source ID、Related Design Version | Decision ID/Version 由有权治理记录机制提供，不能用 D-01 项号代替；双 ID 必须精确匹配，设计版本须可定位不可歧义 |
| 决策主体 | Decision Maker 的 User ID/自然人关联、Organization、Role、Authorization Basis、Decision Authority Evidence | 验证真实身份、组织、角色、该事项的签署权限及签署时有效性；系统管理员或报告作者不能替代 |
| 决策内容 | Decision Item ID、Question、Selected Option、Decision Reason、Scope、Effective Date/Time、Expiry Date/Time | 选项限 `ACCEPT / MODIFY / REJECT`；理由及范围须覆盖具体事项；时间带时区，期限/生效逻辑一致 |
| 原件与审查 | Supporting Documents、Original Evidence Location、Evidence Version、Evidence SHA256、Signed Time/Timezone、Received Time、Review History | 保存不可覆盖原件的可读位置、字节身份、独立来源、签署/接收链、复核方法/结果/人/时间；文件名不等于真实性 |
| 生命周期 | DRAFT、PENDING DECISION、DECIDED、SUPERSEDED、REVOKED；previousVersion/targetDecision 引用、状态事件时间、原因 | 状态事件追加保存；历史原件、选择与签署不可覆盖；撤销/替代不能使旧版本消失 |

设计上将三个标识分离：`D-01`～`D-07` 是**议题 ID**；未来 `Decision ID` 是**原件/裁决实例 ID**；`Authorization ID` 是未来 GRA 授权编号。三者不得互换或从其他字段推测。`Related Design Version` 至少能绑定被裁决文档的正式版本/内容身份；仅写报告日期不足以证明具体版本。原件 SHA256 仅证明字节一致，不证明签发权。Decision Record 的受理/核验状态与未来 GRA 授权生命周期分开，正式裁决也不自动生成 GRA。

## 三、D-01～D-07 待决目录

下表仅登记问题与允许选项。各项 `Decision ID = NOT PROVIDED`、`Decision Version = NOT PROVIDED`、`Selected Option = NOT SELECTED`、`Decision Maker = NOT PROVIDED`、`Original Evidence = NOT RECEIVED`；当前统一为 `PENDING DECISION`。这七行不是七份正式 Decision Record。

| Item ID | 待裁决问题 | 允许选项 | 当前状态 |
|---|---|---|---|
| D-01 | 是否采用 GRA 作为 Proposal/Logical Source 绑定的治理责任授权事实层，且不建立第二套组织权限 | `ACCEPT / MODIFY / REJECT` | `PENDING DECISION` |
| D-02 | 是否采用 B（治理授权语义）+ C（原件证据）+ A（受控 Workflow）的分工及版本关联 | `ACCEPT / MODIFY / REJECT` | `PENDING DECISION` |
| D-03 | 是否保持 Company/Department/OrganizationUnit、Employee/User、Role/Permission/UserRoleScopeAssignment 分别为组织、身份、系统权限权威，GRA+Evidence Registry 为本 Proposal 治理授权权威 | `ACCEPT / MODIFY / REJECT` | `PENDING DECISION` |
| D-04 | 是否建立 GRA 专属 Document Type、ProcessDefinition、审批链及职责分离规则并复用现有 Workflow 框架 | `ACCEPT / MODIFY / REJECT` | `PENDING DECISION` |
| D-05 | 是否以系统权限、有效治理授权、范围匹配、生命周期有效共同构成强制服务端门禁且禁止特权/页面/普通审批绕过 | `ACCEPT / MODIFY / REJECT` | `PENDING DECISION` |
| D-06 | 未来实施申请是否覆盖 GRA、原件登记、API、页面、Workflow、审计等候选范围，以及明确排除范围和保护条件 | `ACCEPT / MODIFY / REJECT` | `PENDING DECISION` |
| D-07 | 是否允许进入 **Implementation Authorization Assessment**，而非开发或实施批准 | `ACCEPT / MODIFY / REJECT` | `PENDING DECISION` |

`MODIFY` 必须附明确改动、受影响设计版本和重审要求；`REJECT` 必须附理由及替代或终止路径；`ACCEPT` 仍须精确记录批准范围、限制、有效期。任何项目不能因为同一原件写了总括意见就自动推定其它项目已决。

## 四、真实性、权限与范围验证规则

正式 Decision 只有在以下检查均可证实时才能进入 `DECIDED`：

1. **独立来源**：确有原始裁决工件，区别于本报告链、模板、空表、设计意见和 Codex 生成记录；登记提供渠道和原件保管位置，原件不可覆盖。
2. **决策身份**：原件中的 Decision Maker 有真实 User ID、自然人对应关系、Role、Organization；签署与接收时间可解释。仅文件创建人、系统管理员或报告作者不足以证明身份。
3. **事项权限**：Authorization Basis 与 Decision Authority Evidence 能证明签署时对该 `D-xx` 事项及范围有权；有效期覆盖签署/生效时点。身份真实但无事项权限仍不得受理为正式裁决。
4. **双 ID 与版本**：Proposal 为 `NCPSB-SP-A-20260929-001`，Logical Source 为 `PCE-NCPB-A-REBUILD-SOURCE-P01`；决策问题、动作、设计版本和适用范围一致，未混入其它 Source/企业对象。
5. **原件完整性**：实际原件字节 SHA256 与登记值一致，Version、签署时间/时区、接收时间、签名/授权依据、Supporting Documents 和审查链可核验。Hash 不符或来源禁用为拒绝；材料不足为待补。
6. **状态与冲突**：核对是否有未撤销的前版、范围重叠或相互矛盾的裁决；新版本必须清晰引用旧版，决策人/复核人职责分离按获批规则检查。

验证结果应保留原始输入、方法、执行人、时间、逐项结果及失败原因；`PENDING` 表示信息不足，`REJECTED` 表示明确不合规。二者都不能升为 `DECIDED`。Decision 真实性核验不等于 HC 四角色六组冲突已通过；那是后续责任任命核验。

## 五、状态转换与不可覆盖历史

| 当前状态 | 触发与门禁 | 后态 | 禁止的捷径 |
|---|---|---|---|
| `DRAFT` | 仅形成未签署的记录草案，字段可待填 | `PENDING DECISION` | 草案不是裁决原件 |
| `PENDING DECISION` | 收到真实独立原件，进入只读真实性/权限/范围/时间/Hash 核验 | 仍待核；全部通过才 `DECIDED` | 收到文件即宣称正式裁决 |
| `PENDING DECISION` | 信息不足或无法独立证实 | `PENDING DECISION`（记录原因） | 用推测值补齐字段 |
| `PENDING DECISION` | 禁止来源、篡改、无效授权或范围不符 | 保持未决并记录 `REJECTED` 验证结果 | 删除/覆盖失败原件或伪造新结果 |
| `DECIDED` | 有权主体出具有效撤销原件，独立验证并追加撤销事件 | `REVOKED` | 直接修改原决策选择/Hash |
| `DECIDED` | 有权主体签发明确引用旧版的新裁决，新版独立验证 | 旧版 `SUPERSEDED`；新版独立 `DECIDED` | 原位覆盖旧版本 |

`Verification` 是核验活动，不是“收到文件后自动通过”的状态；每一步必须保留版本、决策人、原件与审核链。当前目录仍在 `PENDING DECISION`，不因本报告创建而转为 `DRAFT` 实例。撤销或替代均不追溯擦除原件与历史影响；有效时点和再评估范围须由有权主体明示。

## 六、Decision 与 HC/GAP 的独立关系

```text
实际裁决原件 → Decision Verification → 经核验的治理规则
                         ↓
             仍须真实 HC-01~HC-04 任命原件
                         ↓
         Governance Input Acceptance Verification
                         ↓
              四角色六组 Conflict Check
                         ↓
               GAP-01~GAP-04 独立复核
```

即使某项 Decision 后来进入 `DECIDED`，它只确定该议题的治理规则，不自动提供四位责任主体、Authorization ID、Data Boundary 批准或冲突结果。Gap 关闭必须逐项依据真实任命原件、独立核验和专属 Gap 最低受理条件；不能以“Decision Record 结构已完成”或“七项都接受”代替。

## 七、Decision 与实施/Source Qualification 的独立关系

即使未来 D-01～D-07 都取得经核验的 `ACCEPT`，仍需 HC-01～04、编号规则、Data Boundary、架构实施批准、Approved Commit/Schema/Migration 组合、目标环境、测试/回退方案、开发实施与 Migration 各自的独立授权。D-07 的 `ACCEPT` 最多允许进入 Implementation Authorization Assessment，不构成开发许可。物理模型、API、页面或 Migration 不得因为本记录契约存在而创建。Source Qualification Review Pre-check 仍要独立验证全部条件，Phase B 技术准入继续阻断。

## 八、当前待决状态与未执行事项

本轮仅新增本报告中的逻辑目录与规则；没有独立裁决原件输入，也没有正式 Decision 实例、Decision ID、决策人、Selected Option、签署时间或 Evidence Registry 条目。未创建 Authorization ID/GRA 记录，未执行 Workflow 审批，未修改组织权限模型、数据库、models、Migration、API、页面、权限或配置，未创建 Source、Baseline 或运行环境。非 UI 交付，`DELIVERED USER STATE CONTRACT = N/A`；无实施测试。报告回读仅验证结构完整，不证明外部治理事实。

```text
DECISION ITEM CATALOG = D-01~D-07 COMPLETE
FORMAL DECISION RECORDS RECEIVED = 0
SELECTED OPTIONS RECORDED = 0
DECISION MAKERS RECORDED = 0
HC-01~HC-04 = MISSING
GAP-01~GAP-04 = OPEN
SOURCE QUALIFICATION REVIEW PRE-CHECK = NOT READY
DEVELOPMENT / MIGRATION AUTHORIZATION = NOT GRANTED
CODE / DATABASE / WORKFLOW / PERMISSION CHANGED = NO
SOURCE / BASELINE / RUNTIME ENVIRONMENT CREATED = NO
PHASE B TECHNICAL RE-ADMISSION = BLOCKED
GOVERNANCE DECISION RECORDING READY
```
