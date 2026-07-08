# API Reference

## Standard Response Envelope

All API responses must use the same structure:

```json
{
  "success": true,
  "data": {},
  "error": null,
  "meta": {
    "module": "purchase",
    "timestamp": "2026-06-30T00:00:00.000Z"
  }
}
```

## Success Response

```json
{
  "success": true,
  "data": {
    "id": 1
  },
  "error": null,
  "meta": {
    "module": "system",
    "timestamp": "2026-06-30T00:00:00.000Z"
  }
}
```

## Error Response

```json
{
  "success": false,
  "data": null,
  "error": "VALIDATION_ERROR",
  "meta": {
    "module": "purchase",
    "timestamp": "2026-06-30T00:00:00.000Z"
  }
}
```

## Frontend Contract

The frontend request layer normalizes upstream responses. If an upstream service already returns the standard envelope, the envelope is preserved and missing metadata is completed. If an upstream service returns raw data, the request layer wraps it as a standard success response.

## Approved API Namespaces

- `/api/core/*`
- `/api/profit/*`
- `/api/execution/*`
- `/api/purchase/*`
- `/api/system/*`

## Contract Rules

- `success` must be a boolean.
- `data` contains the payload on success and is `null` on failure.
- `error` is `null` on success and a string on failure.
- `meta.module` identifies the product module.
- `meta.timestamp` is an ISO-8601 timestamp generated at the response boundary.
