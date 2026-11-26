# Wave 1 Provider Failure State Contract

| State | Meaning | UI rule |
|---|---|---|
| `LOADING` | Request in progress | Keep structure visible; show loading. |
| `LOADED_EMPTY` | Authenticated 2xx with zero formal rows | Show a formal empty collection. |
| `LOADED_WITH_DATA` | Authenticated 2xx with rows | Show rows and total. |
| `AUTH_FAILED` | HTTP 401/403 or auth error | Show auth failure, never zero facts. |
| `SERVER_CONTEXT_UNAVAILABLE` | No tenant/batch server context | Show context failure, never zero facts. |
| `API_FAILED` | Network/non-schema API failure | Show API failure, never zero facts. |
| `SCHEMA_FAILED` | Invalid fact-load/provider schema | Show schema failure, never zero facts. |

The table shell, toolbar, columns, search, advanced filter, export, pagination, navigation and applicable import extension remain rendered when a provider fails. Formal pages do not call localStorage as a business-data source; storage of the existing authentication token is identity infrastructure, not business fact authority.
