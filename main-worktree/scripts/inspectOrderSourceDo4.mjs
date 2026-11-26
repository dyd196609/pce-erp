import { DatabaseSync } from 'node:sqlite'
import { readFileSync } from 'node:fs'
import { createHash } from 'node:crypto'

const paths = ['D:/Dev-PCE/Source/backend/db.sqlite3', 'D:/Dev-PCE/Acceptance/PDE-Operable-20260912/pde-operable-acceptance.sqlite3']
for (const path of paths) {
  const db = new DatabaseSync(path, { readOnly: true })
  const tables = db.prepare("SELECT name FROM sqlite_master WHERE type='table'").all().map(x => x.name)
  const names = ['sales_customer', 'system_departments', 'system_companies', 'pfm_employee', 'material', 'unit_of_measure', 'pde_product_definition', 'pde_product_category', 'pde_manufacturing_process_type', 'pde_engineering_source_record', 'masterdata_external_identity', 'sales_order', 'sales_order_item', 'planning_demand', 'planning_requirement', 'purchase_plan', 'production_plan']
  const schema = Object.fromEntries(names.filter(x => tables.includes(x)).map(x => [x, db.prepare(`PRAGMA table_info(${x})`).all().map(x => x.name)]))
  const counts = Object.fromEntries(names.filter(x => tables.includes(x)).map(x => [x, db.prepare(`SELECT COUNT(*) n FROM ${x}`).get().n]))
  const out = { path, sha256: createHash('sha256').update(readFileSync(path)).digest('hex'), schema, counts,
    relatedTableNames: tables.filter(x => /customer|employee|department|compan|material|unit_of_measure/.test(x)),
    migrations: db.prepare("SELECT app,name FROM django_migrations WHERE app IN ('sales','planning','pde','masterdata','system') ORDER BY app,id").all() }
  console.log(JSON.stringify(out, null, 2))
  db.close()
}
