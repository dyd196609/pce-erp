# COMPLETED MODULE PROTECTION PREFLIGHT V1

状态：ACTIVE。适用于每个正式开发、整改、Migration、Recovery、权限、页面、Meta/Registry、Runtime、Generator、测试和 Production 任务。

## 输入

- 拟修改文件与业务对象；
- 当前 `completed_module_registry.v1.json`；
- 命中模块的 Freeze Contracts 与 Source Baseline Manifests；
- 共享依赖反向索引；
- 用户 Unfreeze 授权原文。

## 强制步骤

1. 输出 Completed Module Governance Reading Receipt。
2. 将拟修改文件与直接实现文件、Frozen Shared Dependencies 做精确匹配。
3. 列出受影响模块、契约、风险与所需回归。
4. 检查业务对象、名称、路由、菜单、组件、API/Data Authority、权限、Workflow 和 Golden Identity 是否可能漂移。
5. 若命中 Frozen Core Contract 且无明确用户授权，停止修改。
6. 若未命中或仅命中声明的 Allowed Extension Point，制定非回归计划。

## 唯一输出

- `SAFE TO MODIFY`：没有未授权 Frozen Core 影响，且非回归计划完整；或
- `UNFREEZE AUTHORIZATION REQUIRED`：命中 Frozen Core/共享依赖但无有效授权。

任何不确定匹配按影响处理，不得静默放行。没有 Preflight 结果不得改源码。

## Build Gate Contract

正式 Build Chain 必须调用 `verify:pce-completed-module-protection`，对冻结契约、Route、API/Data Authority、Menu、Permission、Golden DB/API/UI continuity 和 Shared Dependency impact 做确定性检查；未授权 drift 非零退出。脚本缺失或未接入时，`Build Protection Gate Contract = PASS` 仅表示本契约成立，`Build Gate Runtime Integration = PENDING`，不得误报执行器已生效。
