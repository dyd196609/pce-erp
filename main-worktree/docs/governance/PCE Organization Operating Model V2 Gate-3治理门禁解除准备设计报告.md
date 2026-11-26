# PCE Organization Operating Model V2 Gate-3 治理门禁解除准备设计报告

日期：2026-08-18  
阶段：OOM-4 Gate-3 Governance Preparation Design（OOM-4 Gate-3 治理门禁解除准备设计）  
类型：DESIGN ONLY（仅设计）  
当前门禁：Gate-3 Governance（治理门禁）= BLOCKED（阻断）  
实施授权：NOT AUTHORIZED（未授权实施）

## 1. 设计目标与结论

本报告只设计 Gate-3 Governance（治理门禁）从 BLOCKED 转为 PASS 所需的治理对象、实名任命、授权范围、职责分离、替补机制和证据包。

本报告不录入自然人、不创建系统 Role（角色）或 Permission（权限）、不建立 Change Request（变更申请）数据，不修改组织事实，也不代替人工签发。

当前结论：

```text
Gate-3 Governance Preparation Design = COMPLETE
Gate-3 Governance = BLOCKED
Gate-3 Ready for PASS Review = NO
Implementation Authorized = NO
```

Gate-3 只有在本报告定义的实名治理证据全部形成、完成冲突检查并由指定治理责任人正式签发后，才可以提交新的 Gate-3 评审；准备设计完成不等于门禁解除。

## 2. 已读取治理基线与判断依据

### 2.1 OOM-4 Gate 基线

| 实际读取路径 | 文件用途 | 关键原文 | 判断依据 |
|---|---|---|---|
| `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-4实施准入与验收门禁设计报告.md` | 定义五大 Gate 及 Gate-3 PASS 标准 | “Owner/Steward/Reviewer/Approver 名单签发”；“自提自审自批被系统阻断” | Gate-3 必须同时具备实名、职责分离、治理动作、审计责任证据 |
| `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-4 Gate重新评估报告.md` | 提供修复 OOM-3.3.1 后的当前门禁状态 | “抽象 RACI 和职责分离设计完整，但自然人尚未实名、授权和签发” | 当前 Gate-3 必须保持 BLOCKED |

重新评估基线：

```text
Gate-1 Architecture = PASS
Gate-2 Data = BLOCKED
Gate-3 Governance = BLOCKED
Gate-4 Technical = BLOCKED
Gate-5 Business = BLOCKED
```

本报告不处理 Gate-2、Gate-4 或 Gate-5。

### 2.2 OOM 治理基线

| 实际读取路径 | 文件用途 | 关键原文 | 判断依据 |
|---|---|---|---|
| `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-3数据治理与初始化方案设计报告.md` | 定义初始化治理和角色责任 | “初始化不是 Migration 默认数据，而是经过 Data Owner 与 Data Steward 确认的受控批次” | 技术脚本和管理员不能替代业务治理签发 |
| `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-3.1主数据责任与治理矩阵设计报告.md` | 定义 Owner、Steward、Reviewer、Approver 与职责分离 | “同一自然人不得审批自己发起或维护的变更” | 冲突检查必须落到 Natural Person（自然人），不能只看 Role Code |
| `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-3.2组织主数据变更流程与治理闭环设计报告.md` | 定义变更申请、影响分析、审核、批准、生效、审计闭环 | “OrganizationOperatingService 作为未来执行已批准变更的唯一组织写服务” | 治理指派和批准先于正式事实执行 |
| `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-3.3.3治理权限与角色边界设计报告.md` | 定义 Governance Assignment、Role、Permission 边界 | “治理动作必须同时满足 Governance Assignment 和 Authorization Decision” | 被指派与有权限是两个独立必要条件 |

### 2.3 BAC 与权限基线

| 实际读取路径 | 文件用途 | 关键原文 | 判断依据 |
|---|---|---|---|
| `D:\Dev-PCE\Source\docs\governance\PCE Business Action Contract V1 BAC-0架构签发报告.md` | 冻结动作、责任和权限语义 | “Permission 不能寻找责任人” | 治理批准人不能从 Permission 持有人集合推断 |
| `D:\Dev-PCE\Source\docs\governance\PCE Business Action Contract V1 BAC-1架构与契约定义设计报告.md` | 设计 `requiredResponsibility` 与 `requiredPermission` 独立字段 | “Workflow Runtime、AuthorizationService、RRE 和 Frontend 均为消费者” | 治理事实不由权限或运行时创建 |
| `D:\Dev-PCE\Source\docs\standards\PCE-BUSINESS-ACTION-PERMISSION-V1.0.md` | 定义统一授权入口 | “system.AuthorizationService 是身份、动作权限与数据范围结论的唯一公共入口” | AuthorizationService 只裁决能否执行，不决定业务批准责任 |

## 3. Gate-3 当前阻断原因

| 编号 | 缺失证据 | 当前风险 | 解除条件 |
|---|---|---|---|
| G3-B01 | 实名 Data Owner（数据所有者） | 无人对业务语义和正确性最终负责 | 按数据对象和范围签发自然人名单 |
| G3-B02 | 实名 Data Steward（数据管理员） | 日常维护、质量检查和执行责任不明确 | 签发主岗及替补 Steward |
| G3-B03 | 实名 Reviewer（审核人） | 影响分析和合理性检查没有独立承担人 | 签发与提交/维护人隔离的 Reviewer |
| G3-B04 | 实名 Approver（批准人） | 正式生效没有业务批准责任人 | 签发独立 Approver 及权限范围 |
| G3-B05 | 职责冲突矩阵 | 换 Role、换 Permission 或 superuser 可形成自提自批 | 按自然人完成冲突扫描和人工复核 |
| G3-B06 | 替补机制 | 离职、请假、调岗时可能找管理员兜底 | 预先签发有限范围替补及启动条件 |
| G3-B07 | 治理授权范围 | 可能出现无限范围管理员 | 明确公司、组织、对象和有效期间 |
| G3-B08 | 正式签发记录 | 概念角色无法作为门禁证据 | 形成版本化任命文件和签发记录 |
| G3-B09 | 培训与验收记录 | 治理责任人可能不会执行闭环 | 完成角色培训、冲突演练和验收签字 |
| G3-B10 | 审计责任书 | 证据保存、查阅、复核责任不明确 | 签发保留期限、查阅范围和复核周期 |

只要任一项未完成，Gate-3 保持 BLOCKED；不得以“管理员已存在”“权限足够”或“设计已完成”替代证据。

## 4. Governance Role（治理角色）实名化设计

### 4.1 实名治理对象最小字段

每一项治理任命至少包含：

| 字段 | 说明 | 强制规则 |
|---|---|---|
| `natural_person_id` | 自然人唯一身份 | 禁止只保存账号名或 Role Code |
| `employee_id` | 正式 Employee（员工）引用 | 必须可回读当前任职状态 |
| `user_id` | 执行系统动作的 User（用户） | 必须与自然人身份受控绑定 |
| `governance_role` | OWNER/STEWARD/REVIEWER/APPROVER | 只表达治理职责，不表达业务 Responsibility |
| `object_type` | 治理数据对象 | 不得使用无限对象通配符作为默认值 |
| `company_scope` | 公司范围 | 必须明确具体公司或获批集合 |
| `organization_scope` | 组织范围 | 必须明确组织节点及是否包含下级 |
| `effective_from` | 生效时间 | 必须早于失效时间 |
| `effective_to` | 失效时间 | 空值仅允许有明确长期任命理由 |
| `appointment_document` | 任命文件编号与版本 | 必须可追溯且不可被静默覆盖 |
| `appointed_by` | 任命签发自然人 | 不能由被任命人自签 |
| `reason` | 任命原因 | 必填 |
| `status` | DRAFT/APPROVED/ACTIVE/EXPIRED/REVOKED | 未 ACTIVE 不具备治理资格 |

注：以上是证据字段设计，不代表本轮创建 Schema、API 或数据。

### 4.2 Data Owner（数据所有者）

Data Owner 回答“谁对该类企业事实的业务语义、质量目标和最终正确性负责”。

必须承担：定义语义与质量标准、确认治理范围、批准重大定义变化、对缺陷处置作业务决策。

不得承担：直接技术落库、批准本人发起或维护的变更、因 Owner 身份自动获得系统权限。

### 4.3 Data Steward（数据管理员）

Data Steward 承担受理、草稿维护、唯一性/完整性/引用检查、影响分析准备和执行已批准维护任务。

Data Steward 不得审核或批准本人录入、修订或提交的申请；维护权限不等于批准权。

### 4.4 Reviewer（审核人）

Reviewer 检查变更合理性、影响分析、引用完整性、时态冲突、治理范围和数据质量。

Reviewer 必须独立于该申请的 Requester 和 Steward，且不得再成为同一申请的 Approver 或 Effective Executor（生效执行人）。

### 4.5 Approver（批准人）

Approver 对正式生效承担最终业务批准责任，确认风险、范围、生效时间、回退条件和审计要求。

Approver 必须被具体指派并具有相应系统执行能力；仅拥有批准 Permission 不构成指派。

## 5. 治理责任矩阵

以下矩阵定义应当实名化的责任席位，不在本报告中填写自然人姓名：

| 数据对象 | Data Owner | Data Steward | Reviewer | Approver | 治理等级 |
|---|---|---|---|---|---|
| Company（公司） | 企业法人/公司治理业务负责人 | 企业组织主数据管理员 | 法务/财务/组织治理审核人 | 企业治理授权批准人 | 极高 |
| Organization Unit（组织单元） | 组织管理业务负责人 | 组织结构数据管理员 | 组织设计与影响审核人 | 获授权组织调整批准人 | 高 |
| Position（岗位） | 人力/组织岗位体系负责人 | 岗位主数据管理员 | 用工与组织影响审核人 | 岗位治理批准人 | 高 |
| Responsibility（责任） | 对应业务领域 Data Owner | 责任目录管理员 | 业务专家与企业架构审核人 | 跨域责任治理批准人 | 最高 |
| PositionResponsibility（岗位责任关系） | 业务领域 Owner + 组织 Owner | 岗位责任关系管理员 | 业务/组织联合审核人 | 独立关系批准人 | 最高 |
| Employee Assignment（员工任职关系） | 人力资源/用工 Owner | 员工任职管理员 | 用工合规与组织审核人 | 任职变更批准人 | 高 |

每个席位必须进一步填写：自然人、员工、账号、范围、任期、替补、任命文件、签发人和签发日期。

## 6. 职责分离控制

### 6.1 自然人级控制原则

检查对象必须是 Natural Person（自然人），而不是账号、Role 或 Permission。

即使同一自然人使用不同账号、切换不同 Role、拥有多个 Permission 或具有 superuser 身份，也不得完成同一 Change Request 的冲突步骤。

### 6.2 最小冲突矩阵

| 已参与动作 | 后续尝试动作 | 结果 |
|---|---|---|
| Draft/Maintain（草稿/维护） | Review（审核） | DENY |
| Draft/Maintain | Approve（批准） | DENY |
| Submit（提交） | Review | DENY |
| Submit | Approve | DENY |
| Review | Approve | DENY |
| Review | Execute Effective（执行生效） | DENY |
| Approve | 修改批准载荷 | DENY；批准失效并重新提交 |
| 任命自己为治理角色 | 签发本次任命 | DENY |

正常链路至少包含不同自然人完成维护/提交、审核和批准；重大 Company、Responsibility、PositionResponsibility 变更还应由独立执行人实施生效。

### 6.3 冲突检测输出

冲突必须返回稳定结果，例如：

```text
decision = DENY
reason_code = GOVERNANCE_SOD_CONFLICT
natural_person = 当前自然人
conflicting_stage = SUBMIT/REVIEW/APPROVE/EXECUTE
write_count = 0
```

拒绝记录应进入治理审计，但不得改变申请状态或正式组织事实。

## 7. 治理授权范围

每项治理指派必须同时限定：

1. Governance Role（治理角色）；
2. Company Scope（公司范围）；
3. Organization Scope（组织范围）；
4. Object Type（数据对象范围）；
5. Change Type（允许处理的变更类型）；
6. Risk Level（允许处理的风险等级）；
7. Effective Period（有效期间）；
8. 是否允许代理及代理条件；
9. 是否需要联合审核或联合批准；
10. 任命文件和撤销依据。

禁止默认授予 `ALL_COMPANIES + ALL_ORGANIZATIONS + ALL_OBJECTS + NO_EXPIRY`。确需跨域授权时，必须有单独风险说明、最短有效期和更高层签发。

系统 Role 可以聚合动作 Permission，但不能替代上述 Governance Assignment（治理指派）。

## 8. 替补与异常机制

| 异常 | 处理原则 | 禁止行为 | 必备证据 |
|---|---|---|---|
| Owner 缺失 | 暂停需要 Owner 决策的高风险变更，发起补位任命 | 自动找最高管理员 | 缺位记录、补位申请、签发 |
| Steward 缺失 | 由预先任命且范围匹配的替补受理 | 临时共享账号维护 | 替补生效记录、操作审计 |
| Reviewer 缺失 | 保持申请待审核，启动受控替补 | 由 Requester 自审 | 替补独立性检查 |
| Approver 缺失 | 保持待批准，不得生效 | Reviewer 或管理员代批 | 替补任命和权限/范围证据 |
| 人员离职 | 到期或撤销原指派，封存未完成事项并重新指派 | 延用离职账号 | 撤销时间、转交清单 |
| 人员调岗 | 重新校验范围和利益冲突 | 默认继承原范围 | 新任职、重新授权、签发 |
| 组织调整 | 重新计算组织 Scope 并人工复核 | 自动扩大至新组织树 | 影响分析和范围重签 |
| 紧急变更 | 可缩短时限，但不同自然人审核/批准不变 | 单人紧急放行 | 紧急理由、双人证据、事后复核 |

替补不是常设无限管理员。替补只有在预定义触发条件成立、范围匹配且未发生职责冲突时才可生效。

## 9. Gate-3 Governance Evidence Package（治理证据包）

### 9.1 必需清单

| 证据编号 | 证据 | 最低内容 | 验收主体 |
|---|---|---|---|
| G3-E01 | 治理角色实名名单 | 六类对象的 Owner/Steward/Reviewer/Approver 自然人 | 数据治理负责人 |
| G3-E02 | 任命文件 | 编号、版本、签发人、签发日期、任期 | 企业治理负责人 |
| G3-E03 | 授权范围表 | 公司、组织、对象、动作、风险等级、有效期 | 业务 Owner + 权限治理人 |
| G3-E04 | 身份绑定证明 | Natural Person、Employee、User 一致性 | 身份治理负责人 |
| G3-E05 | 职责冲突矩阵 | 任命级和单次申请级冲突 | 内控/审计负责人 |
| G3-E06 | 冲突检查记录 | 检查时间、输入、发现项、处置、复核人 | Reviewer + 审计负责人 |
| G3-E07 | 替补与撤销清单 | 替补人、触发条件、范围、有效期、撤销规则 | Data Owner |
| G3-E08 | 治理动作目录 | Submit/Review/Approve/Execute 的边界 | 架构与权限治理负责人 |
| G3-E09 | 审计责任书 | 保存期限、证据字段、查阅人、复核周期 | 审计负责人 |
| G3-E10 | 培训记录 | 角色职责、边界、冲突和异常处理 | 培训负责人 |
| G3-E11 | 验收记录 | 正常、拒绝、替补、离职/调岗场景 | 业务验收负责人 |
| G3-E12 | 正式签发页 | Gate-3 结论、例外、未决项、签名日期 | Gate-3 指定签发组 |

### 9.2 证据质量要求

- 每份证据必须有文件名、版本、Owner、签发日期和 SHA256；
- 任命名单中的自然人必须可关联正式 Employee 和 User；
- 所有范围必须具体、可验证并具有有效期间；
- 不允许空白签发栏、口头确认、聊天记录或单独截图替代正式证据；
- 冲突检查必须覆盖同账号、不同账号同自然人、多 Role、superuser、代理和共享账号；
- 验收必须证明拒绝时正式事实写入为 0；
- 任何例外必须有到期日期、风险 Owner 和补救计划，P0 例外不得签发 PASS。

## 10. Gate-3 PASS 判定规则

Gate-3 转为 PASS 必须全部满足：

1. G3-E01～G3-E12 全部存在并完成签发；
2. 六类主数据对象均有实名、有效且范围明确的四类治理角色；
3. 任命级冲突扫描结果为 PASS，无未解决 P0/P1 冲突；
4. 提交、维护、审核、批准和生效执行的自然人分离规则已被正式确认；
5. superuser、切换 Role、代理和共享账号不能绕过职责分离；
6. 替补、撤销、离职、调岗和组织调整规则已签发；
7. Governance Assignment 与 Permission 的双条件模型获得确认；
8. AuthorizationService、Workflow Runtime、RRE 的边界无歧义；
9. 培训和人工验收完成；
10. Gate-3 指定签发组形成正式 PASS 记录。

判定表达式：

```text
Named Governance Roles
+ Scoped Appointments
+ Natural-Person Separation of Duties
+ Substitute/Revocation Controls
+ Signed Evidence Package
+ Training and Acceptance
= Eligible for Gate-3 PASS Review
```

“Eligible for Review”仍不等于 PASS；最终状态必须由新的独立 Gate-3 评审裁决。

## 11. 系统能力边界

### 11.1 AuthorizationService（统一授权服务）

负责：判断当前 User 是否拥有动作 Permission，组织 Scope 是否覆盖目标对象，并返回 ALLOW/DENY 与 Decision Evidence。

不负责：指定 Owner、Reviewer 或 Approver；作出业务批准；创建 Responsibility；因为用户为管理员而豁免治理冲突。

治理动作允许条件为：

```text
Governance Assignment 有效
+ AuthorizationService = ALLOW
+ Change Request 状态合法
+ Natural Person 职责分离通过
= 治理动作允许
```

### 11.2 Workflow Runtime（流程运行引擎）

未来可承载审核和批准过程、待办、节点记录与结果传递。

不得定义治理责任、自动选择管理员代替、创建组织/岗位/责任/任职事实，或绕过 OrganizationOperatingService 写入正式事实。

本轮 `Workflow Integration = NOT AUTHORIZED`。

### 11.3 RRE（责任解析引擎）

RRE 未来只读取已生效的 Business Action Contract、Responsibility、PositionResponsibility 和 Employee Assignment 事实。

RRE 不创建治理关系、不任命治理角色、不修复缺位、不选择管理员兜底。

本轮 `RRE-1 = NOT AUTHORIZED`。

### 11.4 Role、Permission 与 Responsibility

| 概念 | 回答 | 不能替代 |
|---|---|---|
| Governance Assignment | 谁被正式指派处理特定范围治理事项？ | Permission、业务 Responsibility |
| Role | 用户拥有哪些系统能力集合？ | 治理指派、业务责任 |
| Permission | 当前用户是否可执行某动作？ | 责任人或批准人发现 |
| Responsibility | 企业中谁应该承担某项业务责任？ | 系统授权、治理指派 |

## 12. 后续执行顺序与停止点

本设计获人工确认后，后续仍应分开处理：

1. 由业务治理负责人提供候选实名名单；
2. 独立完成身份绑定、范围和利益冲突检查；
3. 形成任命、替补、撤销、审计和培训证据；
4. 由有权主体签发证据包；
5. 另行发起 Gate-3 Governance Reassessment（治理门禁重新评估）；
6. 只有新评审裁决 PASS，Gate-3 状态才可改变。

以上步骤不在本轮执行。本报告不授权实名录入、权限配置、Schema、API、页面或 Workflow 开发。

## 13. 保护确认

```text
Documentation Changed = YES
Code Changed = NO
Database Changed = NO
Migration Created = NO
API Created = NO
Page Created = NO
Organization Data Changed = NO
Responsibility Data Changed = NO
Employee Data Changed = NO
Permission Model Changed = NO
AuthorizationService Changed = NO
Workflow Runtime Changed = NO
ApprovalTask Changed = NO
RRE Started = NO
Unauthorized Business Writes = 0
```

## 14. 最终状态

```text
Gate-3 Governance Preparation Design = COMPLETE
Gate-3 Governance = BLOCKED
Gate-3 PASS Evidence Package = NOT ESTABLISHED
OOM-4.2 Implementation Authorization Review = NOT STARTED
Organization Model Implementation = NOT AUTHORIZED
RRE-1 = NOT AUTHORIZED
Workflow Integration = NOT AUTHORIZED
```

本报告完整结束。停止等待下一步决策，不进入 Gate-2、Gate-4、Gate-5、OOM-4.2、组织模型实施、RRE-1 或 Workflow Integration。
