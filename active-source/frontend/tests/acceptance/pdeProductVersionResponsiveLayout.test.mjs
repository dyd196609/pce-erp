import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const pagePath = path.resolve(here, '../../src/meta/pages/PdeProductVersionManagementPage.vue')
const pageSource = fs.readFileSync(pagePath, 'utf8')

assert.match(
  pageSource,
  /\.version-page,\.version-page>\*,\.card,\.primary-flow,\.selected-panel,\.selected-panel>\*,\.snapshot-items,\.current-facts,\.comparison\{min-width:0;max-width:100%;box-sizing:border-box\}/,
  'every grid boundary around the two governed lists must be allowed to shrink to the visible page width',
)
assert.equal(
  (pageSource.match(/<PceEnterpriseListTable/g) || []).length,
  2,
  'the responsive fix must preserve both governed enterprise-list instances',
)
assert.match(pageSource, /table-id="pde-product-version-history-table"[\s\S]*?min-width="1460px"/)
assert.match(pageSource, /table-id="pde-product-version-current-table"[\s\S]*?min-width="1960px"/)
assert.doesNotMatch(
  pageSource,
  /\.pce-enterprise-pagination\s*\{[^}]*position\s*:\s*fixed/,
  'pagination must remain owned by its list instead of being fixed to the browser corner',
)

console.log('PDE product-version responsive list boundaries: PASS')
