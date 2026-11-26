# Cross-Database Identity Drift Analysis

`CROSS-DATABASE NUMERIC IDENTITY DRIFT = CONFIRMED DESIGN DEFECT; HISTORICAL LOGIN PATH NOT RECOVERABLE`

Before this corrective, JWT authentication trusted only numeric `user_id` when resolving the current database. A token issued against database A could therefore select the same PK with different semantics in database B. The A3 contradiction (validated user 14 → Employee 109, but real Commit → Employee missing) is consistent only with a different runtime identity/database or a different authenticated user; the old implementation could not distinguish them.

New login tokens bind numeric ID, username, `system.User:<username>` stable identity, database alias/path and a database instance UUID created by the shared rehearsal bootstrap. Authentication re-resolves the user and rejects username or database-context mismatch with `数据库运行上下文已变化，请重新登录。` A real HTTP test proved an old token receives HTTP 401 after a DB switch. Rebuilding at the same path creates a new instance UUID, so path reuse cannot preserve a token.

Preview fingerprints now bind the stable user identity, organization and database context. Commit re-resolves authorization from current `request.user`; it never trusts cached Employee/Position/Responsibility IDs. A Preview/Commit actor mismatch returns HTTP 403 and `当前登录身份已变化，请重新预览后再确认导入。`
