# CSV Import Encoding Contract

CSV is a supported compatibility format. Only a file formally dispatched as CSV is decoded as UTF-8 and may receive `CSV必须使用UTF-8编码。`.

XLSX is binary ZIP/OpenXML and is sent directly to the XLSX parser; it is never decoded as UTF-8. A file whose extension and signature conflict is rejected as a file-signature error before either parser is trusted.

Automated dispatch cases:

- valid XLSX → XLSX parser: PASS
- valid UTF-8 CSV → CSV parser: PASS
- non-UTF-8 CSV → CSV encoding error: PASS
- XLSX → never CSV encoding error: PASS
- fake `.xlsx` → rejected: PASS
- XLSX renamed `.csv` → rejected: PASS
- unsupported extension → rejected: PASS

`CSV UTF-8 VALIDATION SCOPED TO CSV ONLY = YES`
