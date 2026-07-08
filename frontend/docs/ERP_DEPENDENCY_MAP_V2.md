# PCE-ERP 依赖地图 V2（V3.5 SCHEMA ROUTER）

## 唯一运行链路

- `frontend/src/router/index.js` → `createSchemaRoutes()` → `schemaRegistry`
- `schemaRegistry` → `resolveSchema(route.path)` → `getSchemaByRoute(route)` → `loadSchema()`
- `loadSchema()` → `normalizeSchema(rawSchema)` → `createListPage(schema)`
- `createListPage(schema)` → `request({ url: schema.api.list })` → `data`

## route → schema 映射表

- `/purchase/order` → `schemaKey: purchaseOrder` → `frontend/src/meta/schema/purchase/purchaseOrder.js`
- `/purchase/order/:id` → `schemaKey: purchaseOrder` → `frontend/src/meta/schema/purchase/purchaseOrder.js`

## 单入口约束

- route 映射只允许写在 `frontend/src/meta/core/schemaRegistry.js`
- router 只允许导入 `createSchemaRoutes`
- resolver 只允许从 registry 动态加载 schema
- renderer 只允许由 resolver 调用
