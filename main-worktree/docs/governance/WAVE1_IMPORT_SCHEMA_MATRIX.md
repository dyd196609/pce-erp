# Wave 1 Import Schema Matrix

Authority: `backend/pde/formal_import_service.py::FORMAL_IMPORT_SCHEMAS` (`WAVE1-FORMAL-IMPORT-SCHEMA-V1.0`). The official XLSX Template Download, XLSX/CSV preview and commit validators read the same registry.

| Entity | Business identity | Required import fields | Governed enum/reference rules |
|---|---|---|---|
| customers | company + code | code, name | boolean active |
| suppliers | company + code (model also globally unique code) | code, name, delivery_address | credit A-D; integer lead time |
| materials | company + code | code, name | unit status, material type, mutually valid supply flags |
| products | company + product_code | product_code, product_name, emd_material_code | EMD material exact identity when present; manufacturing mode/status |
| workshops | company + code | code, name | optional same-company department code |
| operations | company + code | code, name | optional workshop/work center/UOM; protected operation/calculation/transition enums |
| work-centers | company + code | code, name, department_code | same-company department/workshop; nonnegative numeric capacities |
| equipment | work center + code | code, name, work_center_code | same-company work center; nonnegative hourly capacity |
| standard-capacities | company + code | code, name, resource_scope, uom_code | scope-specific resource, measurement/quantity and time-basis rules |

Errors include `rowNumber`, `field`, `errorType`, Chinese `message`, and `suggestedAction`. Boolean, integer and decimal normalization is shared by preview and commit. References resolve only to active objects in the authenticated company.

`TEMPLATE SCHEMA SINGLE SOURCE = PASS`
