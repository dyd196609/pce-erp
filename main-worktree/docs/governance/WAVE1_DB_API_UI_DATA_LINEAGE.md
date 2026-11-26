# Wave 1 DB / API / UI Data Lineage

| Area | DB → API → UI result | Local business storage |
|---|---|---:|
| Customer | `sales_customer` → enterprise facts API → Customer page = 89/89/89 | 0 |
| Supplier | `supplier` → enterprise facts API → Supplier page = 121/121/121 | 0 |
| Material | `material` → PDE A1 materials → latest-template list = 270/270/270 | 0 |
| Product Definition | `pde_product_definition` → PDE A1 products → latest-template list = 0/0/0 `LOADED_EMPTY` | 0 |
| Product Engineering | formal child tables → PDE A1 entity APIs → 14 validated child lists | 0 |
| Manufacturing Resource | formal tables → PDE A1 endpoints → 3/0/33/0/0 UI totals | 0 |

Detailed object tables, endpoints, states and sample identities are in the per-area lineage documents. The router and adoption matrix both consume the canonical foundation registry. This corrective makes no recovery or business-data write.
