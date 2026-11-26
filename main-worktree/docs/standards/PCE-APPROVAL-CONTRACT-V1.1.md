# PCE-APPROVAL-CONTRACT-V1.1

## 1. 单一审批引擎

所有正式审批流程统一复用 `backend/workflow_runtime`：

- `ProcessDefinition`：版本化流程定义；
- `WorkflowInstance`：一份业务对象对应一份当前流程实例；
- `ApprovalTask`：服务端审批节点和角色要求；
- `ApprovalDecision`：不可替代的审批历史与幂等证据。

禁止在页面、localStorage、JSON 字段或模块私有数组中建立第二套审批状态。

## 2. 服务端动作契约

客户端只能提交动作意图、稳定动作编码、幂等键、当前对象版本、流程版本和任务版本。服务端在事务内重新读取对象、任务、角色、组织范围和职责分离权威对象，再决定状态转换。

审批引起的所有业务状态必须通过状态转换服务产生，并在同一事务写入 `BusinessStateTransition` 和业务审计。审批状态、业务状态、审批决策和转换记录不得分步提交或由页面、脚本直接补写最终状态。

SQLite 环境依赖事务、唯一约束、乐观版本和持久业务锁进行并发控制；不得描述为完整行锁数据库。

## 3. 职责分离

审批流程至少验证：

- maker 与 checker 不同；
- maker 与 final authorizer 不同；
- checker 与 final authorizer 不同；
- 审批人具备当前节点要求角色；
- 审批人组织范围覆盖业务对象法人或组织范围。

## 4. 页面、诊断与验收

审批页面使用中文状态，显示流程实例、任务、审批历史、职责分离和下一步资格。API、页面、复制诊断、`strictFacts` 和验收报告必须共享服务端事实对象。
