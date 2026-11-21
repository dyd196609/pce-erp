# PCE-ERP unified loaded source

This fixed branch stores verified, loaded product source snapshots.
Product paths are `backend/` and `frontend/`; no duplicate deployment tree is included.

- Source manifest SHA256: `a2675d3c5e94bdf7f4e2d395615815284b56114a8fa92dd84b1d649b50d2e439`
- Product files: 4229; backend: 1400; frontend: 2829; migration files: 255.
- Manifest: `PRODUCT_SOURCE_MANIFEST.json` (exact bytes of the loaded source manifest).
- Existing repository history and project documentation are retained.
- Databases, private credentials, sessions, backups, dependencies and build outputs are excluded.
- Historical deployment documentation is retained for reference. The source snapshot does not deploy a service or grant enterprise pilot approval.

Subsequent verified snapshots append commits on `release/unified`.


Current loaded product manifest SHA256: 662d3cd06677215e0687402343b88908deb107d0553e048697946ebbe4e0a4ef
