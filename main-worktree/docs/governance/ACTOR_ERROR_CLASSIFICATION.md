# Actor Error Classification

| Code | HTTP | User-visible meaning |
|---|---:|---|
| `FORMAL_IMPORT_ACTOR_USER_INVALID` | 403 | 正式导入账户不存在或未启用。 |
| `FORMAL_IMPORT_ACTOR_EMPLOYEE_REQUIRED` | 403 | 正式导入账户必须关联员工。 |
| `FORMAL_IMPORT_ACTOR_EMPLOYEE_INACTIVE` | 403 | 正式导入员工必须处于在职状态。 |
| `FORMAL_IMPORT_ACTOR_POSITION_REQUIRED` | 403 | 正式导入员工必须关联岗位。 |
| `FORMAL_IMPORT_ACTOR_POSITION_DISABLED` | 403 | 正式导入岗位必须启用。 |
| `FORMAL_IMPORT_ACTOR_POSITION_OUT_OF_TERM` | 403 | 正式导入岗位不在有效期内。 |
| `FORMAL_IMPORT_ACTOR_RESPONSIBILITY_REQUIRED` | 403 | 正式导入岗位必须关联当前有效的职责。 |
| `FORMAL_IMPORT_ACTOR_RESPONSIBILITY_EXPIRED` | 403 | 正式导入岗位必须关联当前有效的职责。 |
| `FORMAL_IMPORT_ACTOR_PERMISSION_DENIED` | 403 | 正式导入账户缺少有效角色权限范围。 |
| `FORMAL_IMPORT_ACTOR_ORGANIZATION_MISMATCH` | 403 | 账户/员工/岗位/部门与目标企业范围不一致。 |
| `FORMAL_IMPORT_ACTOR_ROLE_POSITION_MISMATCH` | 403 | 正式导入岗位角色与账户授权角色不一致。 |
| `PREVIEW_ACTOR_CONTEXT_CHANGED` | 403 | 当前登录身份已变化，请重新预览后再确认导入。 |
| JWT database mismatch | 401 | 数据库运行上下文已变化，请重新登录。 |

The UI continues to display the backend's precise message. No combined catch-all actor error remains in the formal Commit chain.
