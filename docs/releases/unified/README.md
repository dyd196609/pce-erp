# PCE-ERP unified loaded source

This fixed branch stores verified, loaded product source snapshots.
Product paths are `backend/` and `frontend/`; no duplicate deployment tree is included.

- Source manifest SHA256: `a2675d3c5e94bdf7f4e2d395615815284b56114a8fa92dd84b1d649b50d2e439`
- Product files: 4223; backend: 1394; frontend: 2829; migration files: 253.
- Manifest: `PRODUCT_SOURCE_MANIFEST.json` (exact bytes of the loaded source manifest).
- Existing repository history and project documentation are retained.
- Databases, private credentials, sessions, backups, dependencies and build outputs are excluded.
- Historical deployment documentation is retained for reference. The source snapshot does not deploy a service or grant enterprise pilot approval.

Subsequent verified snapshots append commits on `release/unified`.


Current loaded product manifest SHA256: 47defeb5ab440f6d674d65fa9920bdc432b835360bbbe8808be6b990806cad95
