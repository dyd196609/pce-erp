# Wave 1 Import DB / API / UI Readback

The isolated database started as a copy of the sealed Production baseline. The formal import adapter wrote only through the canonical service. Existing providers were then used for API/page refresh; no provider, count rule or fallback changed.

| Object | Production baseline | Isolated after import | Replay | Imported identity |
|---|---:|---:|---:|---|
| Customer | 89 | 90 | 90 | W1-CUST |
| Supplier | 121 | 122 | 122 | W1-SUP |
| Material | 270 | 271 | 271 | W1-MAT |
| Product Definition | 0 | 1 | 1 | W1-PROD |
| Workshop | 3 | 4 | 4 | W1-WS |
| Operation | 33 | 34 | 34 | W1-OP |
| WorkCenter | 0 | 1 | 1 | W1-WC |
| Equipment | 0 | 1 | 1 | W1-EQ |
| Standard Capacity | 0 | 1 | 1 | W1-CAP |

Existing sets were preserved; no truncate, replace-all or overwrite path exists. Operation retained its 33 baseline rows, business identity, route/API authority and routing semantics. Zero-data pages demonstrate 0→1 and replay remains 1.

Automated DB/formal API readback: PASS. Shared UI refresh binding: PASS by build/static gate. Automated browser smoke-check: Customer count 90 and imported identity `W1-CUST` visibly PASS; import/template controls enabled. User end-to-end manual import confirmation remains PENDING. Production SHA remained `CF6054C87C84FD07273FD6F042A195E85D2F659451208711A9407214CF9365C7`.
