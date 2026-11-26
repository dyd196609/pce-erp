# Import User Idempotency Acceptance

User-visible replay means **upload the same Excel file again**. The user does not edit a table cell or modify the sample.

For a fresh sample, preview must show CREATE=1 and MATCH=0. After explicit confirmation and page readback, re-uploading the exact file must show CREATE=0 and MATCH=1. A second confirmation must not increase the entity count.

Automated acceptance covers all nine entities and passed template, zero-write preview, formal write, readback and replay matching. Representative user acceptance remains pending for Customer, Material and Workshop until the user performs the supplied isolated-DB walkthrough.
