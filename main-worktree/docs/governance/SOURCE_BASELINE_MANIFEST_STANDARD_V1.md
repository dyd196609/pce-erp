# SOURCE BASELINE MANIFEST STANDARD V1

## 目的

冻结不仅保存文字契约，还保存可恢复的代码、构建、Schema 与数据验证身份。Manifest 必须 UTF-8、稳定排序、逐文件 SHA-256，并与 Module Freeze Contract 互相引用。

## 必填内容

1. `moduleId`、`freezeVersion`、生成时间、生成工具版本。
2. 所有直接实现文件及 SHA-256。
3. Router、Navigation、Registry、Meta、共享表格、API Adapter、权限、Runtime、Generator 等关键共享依赖及 SHA-256。
4. 工作树状态、Git commit 与 tree identity（若存在）；dirty tree 必须明确，不得把 HEAD 冒充当前工作树。
5. Build Tree SHA、产物文件数、构建命令和结果。
6. 相关 Migration 名称/状态、Schema contract、数据库类型与只读 fingerprint；不得嵌入凭据或敏感数据。
7. Golden Business Identity 的 DB 查询口径、API identity、UI identity、租户/范围和验证时间。
8. Freeze Contract、用户验收、菜单截图与回归 Evidence 路径。

## 不可变性与恢复

清单生成后计算自身 SHA-256，并只以新版本替换。优先形成正式 Git Commit + `freeze/<module>/<version>` Tag；没有用户授权时禁止自动 Commit/Tag，仍须生成清单并写明 `GIT FREEZE TAG = PENDING USER AUTHORIZATION`。恢复必须使用清单逐文件验证，不允许全局回滚覆盖其他模块成果。

## 当前状态

本规范已建立；本轮没有任何模块获得新的 Freeze Contract 或 Source Baseline Manifest，也未执行 Git Commit/Tag。
