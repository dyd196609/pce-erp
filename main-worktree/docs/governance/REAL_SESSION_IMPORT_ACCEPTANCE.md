# Real Session Import Acceptance

Automated gate `verify:pce-formal-import-real-session-actor`: PASS.

Actual HTTP chain: isolated DB → shared bootstrap → backend → login HTTP → current context → XLSX template → Preview HTTP → Commit HTTP → formal readback HTTP → Replay Preview/Commit.

- Automated maintenance Customer Commit/readback/replay: PASS
- User Customer A4 Commit/readback/replay: PASS
- User-visible Customer idempotency: PASS
- Read-only Preview: ALLOW
- Read-only Commit: HTTP 403
- Database switch with old JWT: HTTP 401
- Sanitized Customer Commit traces: 4 total across preflight/final DB contexts
- Production database hash: unchanged
- Production writes: 0

Material B4 and Workshop C4 read-only Preview readiness under the same final A4 actor is PASS. Their user-visible Commit/readback/replay remains PENDING.
