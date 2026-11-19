# PCE-ERP unified loaded source

This fixed branch stores verified, loaded product source snapshots.
Product paths are `backend/` and `frontend/`; no duplicate deployment tree is included.

- Source manifest SHA256: `fba249415da1bbaf19e95420bbbc7f05b67dbcb34323d242dc22a1e7c9ba4ec5`
- Product files: 4217; backend: 1390; frontend: 2827; migration files: 252.
- Manifest: `PRODUCT_SOURCE_MANIFEST.json` (exact bytes of the loaded source manifest).
- Existing repository history and project documentation are retained.
- Databases, private credentials, sessions, backups, dependencies and build outputs are excluded.
- Historical deployment documentation is retained for reference. The source snapshot does not deploy a service or grant enterprise pilot approval.

Subsequent verified snapshots append commits on `release/unified`.
