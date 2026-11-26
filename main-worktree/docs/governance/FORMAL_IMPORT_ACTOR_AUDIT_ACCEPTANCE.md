# Formal Import Actor Audit Acceptance

Successful formal writes pass source and actor metadata into `ProductionFoundationService.write` and persist it in the existing organization operating audit record. No new audit authority or database migration was introduced.

| Required field | Recorded key | Acceptance |
|---|---|---|
| User ID | `actorContext.userId` / audit actor | PASS |
| Employee ID | `actorContext.employeeId` | PASS |
| Position ID | `actorContext.positionId` | PASS |
| Responsibility ID | `actorContext.responsibilityId` | PASS |
| Organization | `actorContext.organizationId` / audit organization | PASS |
| Import Run ID | `importRunId` | PASS |
| Source File | `sourceFile` | PASS |
| Object Type | `objectType` | PASS |
| Preview Fingerprint | `previewFingerprint` | PASS |
| Commit Time | audit `createdAt` | PASS |

Runtime readback sampled audit ID 2445 for Customer and found actor ID 14, organization 1, execution chain identifiers, contract version, run ID, source file/type, object type, preview fingerprint, row/schema and complete actor context. Automated audit writes: 9. Production audit writes: 0.
