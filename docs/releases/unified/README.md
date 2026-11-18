# PCE-ERP unified loaded source

This fixed branch stores verified, loaded product source snapshots.
Product paths are `backend/` and `frontend/`; no duplicate deployment tree is included.

- Source manifest SHA256: `72479b9113a4a5fb5db29fe73d6a74e4c95c3af3c8819d28d582f67ad9aff317`
- Product files: 4211; backend: 1385; frontend: 2826; migration files: 250.
- Manifest: `PRODUCT_SOURCE_MANIFEST.json` (exact bytes of the loaded source manifest).
- Existing repository history and project documentation are retained.
- Databases, private credentials, sessions, backups, dependencies and build outputs are excluded.
- Historical deployment documentation is retained for reference. The source snapshot does not deploy a service or grant enterprise pilot approval.

Subsequent verified snapshots append commits on `release/unified`.
