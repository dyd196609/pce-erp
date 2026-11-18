# PCE-ERP unified loaded source

This fixed branch stores verified, loaded product source snapshots.
Product paths are `backend/` and `frontend/`; no duplicate deployment tree is included.

- Source manifest SHA256: `89ab8b463f1663e9b53ac32be1539f1dc2f97f1fa3d957603a1a81eac4f401a3`
- Product files: 4215; backend: 1389; frontend: 2826; migration files: 251.
- Manifest: `PRODUCT_SOURCE_MANIFEST.json` (exact bytes of the loaded source manifest).
- Existing repository history and project documentation are retained.
- Databases, private credentials, sessions, backups, dependencies and build outputs are excluded.
- Historical deployment documentation is retained for reference. The source snapshot does not deploy a service or grant enterprise pilot approval.

Subsequent verified snapshots append commits on `release/unified`.
