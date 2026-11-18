import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { buildProcessNodeTabUrl } from '../src/meta/process/processNodeNavigation.js'
import { listPceBusinessModules } from '../src/meta/runtime/pceBusinessModuleRegistry.js'
import { resolveScmPageIdentity } from '../src/meta/schema/scm/scmPageIdentityRegistry.js'
import { resolveScmStandardPageContract } from '../src/meta/schema/scm/scmStandardPageContract.js'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const read = relative => fs.readFileSync(path.join(root, relative), 'utf8')
const assert = (condition, message) => { if (!condition) throw new Error(message) }
const canonicalRoute = '/scm/purchase-request'
const canonicalComponent = 'src/meta/pages/ScmPurchaseRequestPage.vue'
const router = read('src/router/index.js')
const menu = read('src/meta/enterprise-os/enterpriseOSModel.js')
const page = read('src/meta/pages/ScmPurchaseRequestPage.vue')
const legacyPage = read('src/meta/pages/ScmPage.vue')

const modules = listPceBusinessModules().filter(item => item.moduleId === 'purchase-request')
assert(modules.length === 1, `Purchase Request canonical module count must be 1, received ${modules.length}`)
assert(modules[0].route === canonicalRoute, 'Purchase Request canonical module route mismatch')
assert(modules[0].pageComponent === canonicalComponent, 'Purchase Request canonical component mismatch')
const identity = resolveScmPageIdentity(canonicalRoute)
assert(identity?.businessObject === 'PurchaseRequest' && identity?.route === canonicalRoute, 'Purchase Request identity mismatch')
const contract = resolveScmStandardPageContract(canonicalRoute)
assert(contract?.apiEndpoint === '/api/procurement/scm-page-facts/purchase-request/', 'Purchase Request formal API mismatch')
assert(contract?.traceAuthority === 'SCM Standard Page Facts API', 'Purchase Request trace authority mismatch')
assert(router.includes("path: 'scm/purchase-requests'") && router.includes("redirect: '/scm/purchase-request'"), 'Legacy plural route must redirect')
assert(router.includes("wrapPceListPage('purchase-request', () => import('@/meta/pages/ScmPurchaseRequestPage.vue'))"), 'Canonical route component binding missing')
assert((router.match(/wrapPceListPage\('purchase-request', \(\) => import\('@\/meta\/pages\/ScmPurchaseRequestPage\.vue'\)\)/g) || []).length === 3, 'Purchase Request list/create/detail routes do not share the formal component')
assert(menu.includes("label: '采购申请', path: '/scm/purchase-request'"), 'Governed real menu entry missing')
assert(page.includes('PceEnterpriseListTable') && page.includes('data-acceptance-id="purchase-request-business-page"'), 'Formal visible table missing')
assert(page.includes(':has(> .pce-list-page-content > .purchase-request-page)'), 'Formal business content is not prioritized above diagnostics')
assert(!legacyPage.includes('/scm/purchase-requests'), 'Legacy SCM navigation still exposes plural Purchase Request route')

const node = { pageCode: 'purchase-request', pageUrl: canonicalRoute, allowNewTab: true }
const generatedUrl = buildProcessNodeTabUrl(node, { origin: 'http://127.0.0.1:5174', pathname: '/' })
assert(generatedUrl === 'http://127.0.0.1:5174/#/scm/purchase-request', 'New-tab resolver did not preserve current runtime origin')

console.log(JSON.stringify({
  result: 'PASS',
  canonicalBusinessObject: identity.businessObject,
  canonicalRoute,
  canonicalComponent,
  formalApi: contract.apiEndpoint,
  canonicalModuleCount: modules.length,
  legacyPluralRoute: 'REDIRECT',
  generatedUrl,
  runtimeOriginSource: 'location.origin',
  productionUserDataWritten: false,
}, null, 2))
