# PCE Organization Operating Model V2 OOM-4.1.3 组织管理页面实施包设计报告
日期：2026-08-18  
阶段：OOM-4.1.3 Organization Management UI Implementation Package Design（组织管理页面实施包设计）  
任务性质：DESIGN ONLY（仅设计）  
页面实施授权：NOT AUTHORIZED（未授权实施）
## 1. 设计目标与结论
本报告设计未来获得独立实施授权后，Organization Operating Model V2（企业组织运行模型 V2）的管理页面结构、事实来源、操作闭环、权限展示、审计展示和 Workflow Runtime（流程运行引擎）页面边界。
结论：
1. `#/organization` 继续作为唯一正式组织治理入口，不新建第二套组织管理系统。
2. `#/organization-model` 及其部门、岗位子页继续作为综合只读查看与诊断入口，不承担维护。
3. 当前页面“直接保存正式事实”的按钮必须在未来实施时改为“提交 Change Request（变更申请）”；页面不得直接调用正式事实保存动作。
4. 页面只展示服务端事实、服务端 `statusLabel`、AuthorizationService（统一授权服务）结论和治理流程证据，不自行计算组织事实、权限或审批人。
5. OOM-4.1.2 的 Change Request、影响分析和已批准变更执行能力尚未实施，因此页面实施当前不可启动。
```text
Organization Management UI Design = PASS
Current Single Entry = PRESENT
Current Governed Change UI = NOT PRESENT
Page Implementation = NOT AUTHORIZED
```
## 2. 已读取文件、用途、关键原文与判断
### 2.1 治理与实施包基线
| 实际路径 | 文件用途 | 关键原文 | 判断依据 |
|---|---|---|---|
| `D:\Dev-PCE\Source\docs\governance\PCE Business Action Contract V1 BAC-0架构签发报告.md` | 冻结 Business Action Contract（业务动作契约）唯一事实源 | “Frontend Projection 只能展示和适配” | 页面不能定义动作、责任、权限或审批人 |
| `D:\Dev-PCE\Source\docs\governance\PCE Business Action Contract V1 BAC-1架构与契约定义设计报告.md` | 设计服务端契约字段和前端投影 | `requiredResponsibility` 与 `requiredPermission` 分离 | 页面不得用权限推断责任人 |
| `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-4实施准入与验收门禁设计报告.md` | 冻结实施准入与验收门禁 | 架构、数据、治理、技术、业务门禁均须通过 | 页面设计完成不代表允许开发 |
| `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-4.1.1组织模型Schema实施包设计报告.md` | 设计 Employee Assignment（员工任职关系）及岗位责任时态结构 | `Employee.position_ref` 仅为当前主岗位投影 | 页面不能把旧单岗位字段当长期事实 |
| `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-4.1.2组织服务能力实施包设计报告.md` | 设计唯一事实执行入口和治理服务链 | `Change Request → Impact Analysis → Review → Approval → OrganizationOperatingService` | 页面只能提交申请并读取执行结果 |
### 2.2 当前页面与组件
| 实际路径 | 文件用途 | 关键原文 | 当前判断 |
|---|---|---|---|
| `D:\Dev-PCE\Source\frontend\src\meta\pages\AccessControlFoundationPage.vue` | `#/organization` 组织、人员、岗位、账户、角色与权限统一页面 | “全部记录来自服务端正式模型；岗位不等于角色” | 唯一正式入口基础可复用 |
| `D:\Dev-PCE\Source\frontend\src\meta\components\OrganizationOperatingAdminDialog.vue` | 部门、岗位、责任、员工等维护弹窗 | `saveEnterpriseOrganizationModel(action, payload)` | 当前直接保存正式事实，未来必须改为提交变更申请 |
| `D:\Dev-PCE\Source\frontend\src\meta\components\OrganizationOperatingCatalogForm.vue` | 岗位族、等级、责任目录表单 | “责任必须先以草稿创建” | 目录语义可复用，提交语义需治理化 |
| `D:\Dev-PCE\Source\frontend\src\meta\components\EnterpriseOrganizationModelView.vue` | 综合组织模型查看、关系树和诊断 | “本页只展示服务端组织事实、关系树与诊断” | 正确目标是完全只读 |
| `D:\Dev-PCE\Source\frontend\src\api\accessControl.js` | 组织和权限页面请求适配 | `saveEnterpriseOrganizationModel()` POST 正式动作 | 当前页面写入口；未来页面不得绕过 Change Request |
| `D:\Dev-PCE\Source\frontend\src\router\index.js` | 组织页面 Route（路由） | `/organization` 与 `/organization-model` 分离 | 路由结构可复用，不新增第二入口 |
### 2.3 当前关键原文证据
正式入口：
```vue
<main class="access-page" data-page-code="erp-access-control-foundation">
  <h1>组织、人员、岗位、账户、角色与权限</h1>
</main>
```
当前直接保存：
```javascript
const response = await accessControlApi.saveEnterpriseOrganizationModel(
  action, requestPayload
)
```
综合页只读声明：
```vue
<PceBusinessStatus
  status-code="READ_ONLY"
  status-label="综合查看与诊断"
  source="server"
/>
```
综合页隐藏的历史维护代码：
```vue
<el-dialog v-if="false"
  title="已停用：请使用 /organization 正式管理员入口">
```
判断：综合页当前运行可达性已只读，但文件仍保留整套不可达保存表单和 `saveAction()`。未来页面实施包应删除或拆除该死代码，避免形成第二维护入口；本轮不修改。
## 3. 页面目标架构
```text
Server Organization Facts
↓
Frontend Projection（前端投影）
↓
#/organization
↓
Change Request Draft（变更申请草稿）
↓
Impact Analysis Preview（影响分析预览）
↓
Submit / Review / Approval（提交/审核/批准）
↓
OrganizationOperatingService（服务端执行）
↓
Server Readback + Audit（服务端回读与审计）
```
页面职责：
- 展示服务端正式事实；
- 收集变更意图、原因和期望生效时间；
- 展示影响分析、审核、批准和执行结果；
- 提交用户动作；
- 刷新并读取服务端最终事实。
页面禁止：
- 直接写 Organization、Position、Responsibility 或 Employee Assignment；
- 根据名称、缓存或页面临时状态创建企业事实；
- 计算 Authorization ALLOW/DENY；
- 选择业务批准人或责任人；
- 把按钮隐藏当成安全边界；
- 用上一页缓存补齐事实。
## 4. 页面信息架构
正式入口保持：
```text
#/organization
```
目标一级导航：
| Tab | 主要对象 | 页面定位 |
|---|---|---|
| 组织结构 | Company、OrganizationUnit、Department | 查看事实、提出结构变更 |
| 岗位体系 | JobFamily、JobLevel、Position | 查看岗位分类和生命周期、提出变更 |
| 责任目录 | Responsibility | 独立责任目录与生命周期治理 |
| 岗位责任 | PositionResponsibility | 选择已有责任，维护承担关系 |
| 员工任职 | Employee Assignment | 主岗、兼岗、代理和历史 |
| 员工档案 | Employee、汇报关系、账户关联 | 人员档案及关系维护申请 |
| 变更申请 | Change Request | 我的申请、待审核、待批准、待生效、已执行 |
| 审计记录 | Audit | 申请、审批、执行和事实 Before/After |
| 用户与权限 | User、Role、Permission、Scope | 授权管理，与责任治理严格分离 |
`#/organization-model` 保持：
- 企业组织关系树；
- 部门、岗位、员工和责任关系只读展示；
- `strictFacts` 诊断；
- 最近审计证据；
- 跳转到唯一正式入口；
- 不包含保存按钮、写表单或写请求函数。
## 5. 公共页面与企业列表契约
实施时必须继续复用：
- `PceListPageShell`：页面身份、动作说明、导航、可观测性和标题治理；
- `PCE-ENTERPRISE-LIST-CONTRACT-V1.1`：企业列表正式契约；
- `PceEnterpriseListTable`：工具栏、选择、冻结列、操作列和唯一横向滚动拥有者；
- `PceEnterpriseAdvancedFilter`：受治理高级筛选；
- `PceBusinessStatus`：服务端业务状态展示。
约束：
- 快捷搜索、高级筛选、导出、刷新和选择不得在页面重复建设；
- 高级筛选字段必须声明 `filterType`；枚举使用服务端治理选项；
- 选择框、序号、主业务编号固定左侧，操作列固定右侧；
- 横向滚动由表格内部唯一拥有；
- 用户页面只显示服务端 `statusLabel`，不直接显示内部 `statusCode`；
- API、页面、复制诊断、`strictFacts` 和验收报告复用同一服务端事实。
## 6. 组织结构页面设计
列表显示：
```text
编码、名称、类型、所属公司、上级组织、负责人、
生效时间、失效时间、状态、子组织数、岗位数、员工数
```
允许动作：
- 查看详情；
- 新增变更申请；
- 调整变更申请；
- 合并/停用变更申请；
- 查看影响分析；
- 查看历史和审计。
提交表单只生成 Change Request，不修改正式事实。公司字段由服务端组织范围确定；父级候选、负责人候选和状态选项均来自服务端。
合并或停用前必须展示对子组织、Position、PositionResponsibility、Employee Assignment、BAC 引用和 Workflow 范围的影响。
## 7. 岗位体系页面设计
### 7.1 JobFamily（岗位族）与 JobLevel（岗位等级）
显示：编码、名称、说明、等级顺序、状态、关联岗位数量。
固定说明：
```text
岗位族用于岗位分类；岗位等级用于职业发展、薪酬和管理分析。
岗位族和岗位等级不决定责任、权限或审批人。
```
### 7.2 Position（岗位）
显示：编码、名称、公司、组织单元、部门、岗位族、岗位等级、上级岗位、生效区间、任职人数、责任数量和状态。
页面禁止：
- 岗位自动生成 Responsibility；
- 岗位自动创建 Role 或 Permission；
- 用岗位名称推断审批人；
- 用 `defaultRole` 作为实际授权结论。
岗位停用申请必须先展示有效任职、岗位责任、子岗位和流程引用阻断项。
## 8. Responsibility（责任）页面设计
责任目录继续独立于岗位管理。
列表显示：
```text
责任编码、责任名称、业务领域、状态、有效期、
关联岗位数量、BAC 引用数量、最后更新时间
```
详情显示：
- 基础定义；
- 生命周期；
- 关联岗位；
- Business Action Contract 引用；
- 变更申请历史；
- 审核和批准证据；
- 正式事实审计。
固定说明：
```text
Responsibility 表示企业业务责任，不等同于岗位、角色或权限。
责任必须独立定义；岗位只能承担已有责任。
```
页面、AI、RRE、Workflow 和岗位编辑页均不得自动创建责任。
## 9. PositionResponsibility（岗位责任关系）页面设计
页面只能从 Responsibility API（责任数据接口）的 `system.Responsibility` 事实选择责任。
字段：
```text
Position、Responsibility、relationType（PRIMARY/SUPPORTING）、
effectiveFrom、effectiveTo、status、reason
```
保存语义：
```text
提交岗位责任变更申请
```
禁止显示“立即保存正式职责分配”。影响预览必须展示：
- 同责任的其他 PRIMARY；
- 时间重叠；
- 当前员工候选变化；
- BAC 引用；
- RRE 未来解析结果可能变化。
页面不得自动消除多人候选，也不得用 Permission 选择责任岗位或员工。
## 10. Employee Assignment（员工任职关系）页面设计
员工档案与任职事实分开呈现：
```text
Employee = 员工身份档案
Employee Assignment = 员工在哪个岗位任职的时态事实
```
任职列表显示：员工、岗位、组织单元、类型、主岗标志、生效区间、状态和来源。
支持提出：
- 入职任职；
- 调岗；
- 晋升；
- 兼岗；
- 代理；
- 离岗。
调岗采用旧区间结束、新区间开始的交接预览。页面必须提示：员工变化只改变任职事实，不修改 BAC、Responsibility、Workflow、Role 或 Permission。
`Employee.position_ref` 仅作为兼容当前主岗位投影；页面不得把它作为历史、多岗或代理事实。
## 11. Change Request 与审计页面设计
### 11.1 变更申请列表
视图：我的草稿、待审核、待批准、待生效、已执行、已拒绝、执行失败。
字段：申请编号、对象类型、对象、动作、申请人、审核人、批准人、期望生效时间、服务端状态标签和最后更新时间。
### 11.2 变更申请详情
分区：
1. 申请摘要；
2. Before/Proposed After；
3. 影响分析 BLOCKER/WARNING/INFORMATION/UNKNOWN；
4. 审核记录；
5. 批准记录；
6. 生效与执行结果；
7. 正式事实 Before/After；
8. 服务端回读和审计引用。
职责分离：同一自然人不得同时完成提交、审核和批准。页面可以提示冲突，但最终阻断必须由服务端完成。
### 11.3 页面动作
```text
保存草稿 / 提交 / 撤回 / 审核通过 / 退回 /
批准 / 拒绝 / 取消未来生效 / 查看执行结果
```
页面不得提供“绕过审批立即应用”。
## 12. Workflow Runtime 页面边界设计
页面可以展示：
- Approval Status（审批状态）；
- Workflow Node（流程节点）；
- Approval Record（审批记录）；
- 当前待办、处理人显示和时间；
- 流程实例编号及其 Change Request 引用。
页面可以提交受控流程动作：审核意见、批准意见、退回和拒绝，但必须由服务端 Workflow Runtime 与 AuthorizationService 重新验证。
页面不能直接：
- 修改 Organization（组织）事实；
- 修改 Responsibility（责任）；
- 修改 Position（岗位）；
- 修改 PositionResponsibility；
- 修改 Employee Assignment；
- 把 Workflow 完成解释为正式事实已经生效；
- 把 Responsibility Code 写入 `ApprovalTask.required_role_code`。
正确边界：
```text
Workflow 页面
↓ 提交审核/批准意图
Workflow Runtime
↓ 形成批准证据
Organization Change Governance Service
↓ 到期请求执行
OrganizationOperatingService
↓
正式事实与审计
```
Workflow 页面不得创建责任、决定责任人或替代 OrganizationOperatingService。
## 13. Authorization 与页面状态设计
页面启动时读取 Permission Profile（权限档案）和服务端动作能力投影。
状态：
- `ALLOW`：显示动作入口；
- `DENY`：隐藏或禁用，并显示服务端原因；
- `READ_ONLY`：只显示事实和流程证据；
- `UNKNOWN/read_failed`：阻断提交，不展示空结果冒充无数据。
按钮显示只改善体验。即使按钮隐藏，服务端仍必须返回 HTTP 403。
Role（角色）只表达权限集合；Responsibility 回答谁应该负责。页面必须持续展示二者语义说明，不允许把角色选项放入责任字段。
## 14. 页面错误、刷新与并发设计
页面必须处理：
- 事实读取失败；
- 权限拒绝；
- 影响分析存在阻断；
- Change Request 版本冲突；
- 正式事实已漂移；
- 有效期重叠；
- 跨公司引用；
- 重复提交；
- 服务端回读不一致。
保存草稿或提交成功后必须清除临时页面缓存并重新读取服务端申请事实。正式执行完成后，组织页面与综合模型页都重新读取相同服务端组织事实。
不得通过前端合并旧数据和新响应来掩盖冲突。
## 15. 页面实施包拆分
以下仅为未来实施包，不构成开发授权：
### UI-0：Prerequisite Gate（前置门禁）
- OOM-4.1.1 Schema 和 OOM-4.1.2 服务已实施并验收；
- Change Request 读取/动作能力可用；
- BAC 与权限动作来源明确；
- 页面字段、状态和验收标准冻结。
### UI-1：Read Projection（只读投影）
- 整理 `#/organization` 的统一服务端事实；
- 完成 As Of 查询、来源、数量和加载状态展示；
- 保持企业列表契约。
### UI-2：Change Request UI（变更申请界面）
- 将现有“保存”表单转为申请草稿；
- 增加影响分析、提交和版本冲突处理；
- 不调用正式事实保存动作。
### UI-3：Review & Approval UI（审核批准界面）
- 展示流程状态、节点和记录；
- 支持受控审核/批准意图；
- 服务端执行职责分离和 403。
### UI-4：Audit & History UI（审计历史界面）
- 串联申请、审批、执行、Before/After 和回读；
- 历史不可编辑。
### UI-5：Read-only Consolidation（只读入口收敛）
- 删除综合模型页中 `v-if="false"` 的历史写表单和保存逻辑；
- 保留只读关系树、诊断和正式入口跳转；
- 静态扫描证明不存在第二写入口。
### UI-6：Acceptance（验收）
- 自动测试；
- 权限身份测试；
- 浏览器人工验收；
- 零组织外业务副作用验证。
## 16. 自动测试与人工验收设计
| 编号 | 场景 | 预期 |
|---|---|---|
| OOM413-T01 | `/organization` 唯一正式入口 | PASS |
| OOM413-T02 | 综合模型页写入口扫描 | 0 |
| OOM413-T03 | 页面提交组织变更 | 只创建 Change Request |
| OOM413-T04 | 页面直接调用事实写接口 | 服务端拒绝 |
| OOM413-T05 | 无权限提交/审核/批准 | HTTP 403 |
| OOM413-T06 | 同人提交、审核、批准 | 服务端阻断 |
| OOM413-T07 | 责任下拉事实源 | system.Responsibility |
| OOM413-T08 | 岗位页创建责任 | 不存在该能力 |
| OOM413-T09 | Employee Assignment 历史/未来查询 | 服务端事实一致 |
| OOM413-T10 | Workflow 页面 | 只展示/提交流程意图，不写组织事实 |
| OOM413-T11 | 保存后刷新回读 | 申请与正式事实分别一致 |
| OOM413-T12 | `statusLabel` 展示 | 不向业务用户直显内部状态码 |
| OOM413-T13 | 列表契约与横向滚动 | 符合企业列表基线 |
| OOM413-T14 | read_failed | 明确阻断，不伪装零数据 |
| OOM413-T15 | RRE、采购、ApprovalTask 写入 | 全部为 0 |
人工验收重点：
- [ ] 页面文案明确岗位、责任、角色、权限边界；
- [ ] 所有维护按钮显示“提交变更申请”，不显示“立即保存正式事实”；
- [ ] 影响分析可见且不能自动批准；
- [ ] 审核与批准身份、意见和时间可见；
- [ ] Workflow 完成后，正式事实只有 OrganizationOperatingService 到期执行才改变；
- [ ] `#/organization-model` 完全只读；
- [ ] 刷新后仍读取相同服务端事实；
- [ ] 无组织数据、责任数据、员工数据或采购业务的未授权写入。
## 17. 风险与实施阻断
| 风险 | 影响 | 处理 | 优先级 |
|---|---|---|---|
| 当前表单直接保存正式事实 | 绕过治理闭环 | UI-2 改为申请语义 | P0 |
| Change Request 服务未实施 | 页面无正式申请来源 | 等待 OOM-4.1.2 实施授权 | P0 |
| 综合页保留不可达写代码 | 第二入口回归风险 | UI-5 删除死代码 | P0 |
| Employee Assignment 未实施 | 任职页面无时态事实 | 等待 OOM-4.1.1 | P0 |
| BAC 服务端契约未实施 | 动作投影可能漂移 | 等待 BAC 独立授权 | P0 |
| 前端以权限选择责任人 | 破坏责任/权限边界 | 服务端事实与静态门禁 | P0 |
| Workflow 完成即显示已生效 | 混淆审批和事实状态 | 分开展示流程状态与事实状态 | P0 |
| 页面复用旧缓存补齐 | 多事实源 | 强制服务端刷新回读 | P1 |
当前准入结论：
```text
OOM-4.1.3 Page Implementation Gate = FAIL
Reason = SCHEMA AND SERVICE IMPLEMENTATION NOT AUTHORIZED
```
## 18. 本轮保护确认
本轮仅只读检查治理报告、前端页面、组件、路由和请求适配，并新增本 Markdown 报告。未创建页面、API、Migration 或业务数据，未运行 Workflow 或 RRE。
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
Workflow Runtime Changed = NO
ApprovalTask Changed = NO
RRE Started = NO
Unauthorized Business Writes = 0
```
## 19. 最终状态
```text
OOM-4.1.3 Organization Management UI Implementation Package Design = COMPLETE
OOM-4.1.4 = NOT STARTED
Organization Model Implementation = NOT AUTHORIZED
RRE-1 = NOT AUTHORIZED
Workflow Integration = NOT AUTHORIZED
```
本报告完整结束。停止等待下一步指令，不进入 OOM-4.1.4、页面开发、API 创建或数据库修改。
