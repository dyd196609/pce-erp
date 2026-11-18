import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import {
  foundationCanonicalRouteDefinitions,
  getFoundationCanonicalModule,
  getFoundationCanonicalModuleByEntity,
} from '../src/meta/master-data/foundationEntryUnificationRegistry.js'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const read = relative => readFileSync(path.join(root, relative), 'utf8')
const page = read('src/meta/pages/PdeOrderEngineeringCalculationPage.vue')
const maintenance = read('src/meta/components/ProductionFoundationMaintenance.vue')
const backend = read('../backend/pde/views.py')

const ruleIdentity = getFoundationCanonicalModule('engineering-rule-definition')
assert(ruleIdentity, 'engineering rule identity missing')
assert.equal(ruleIdentity.entityKey, 'engineering-rule-definitions')
assert.equal(ruleIdentity.component, 'ProductionFoundationMaintenance')
assert.equal(ruleIdentity.routeName, 'FoundationEngineeringRuleDefinitions')
assert.equal(ruleIdentity.routePath, '/foundation/master-data/engineering-rule-definitions')
assert.equal(getFoundationCanonicalModuleByEntity('engineering-rule-definitions'), ruleIdentity)
assert(foundationCanonicalRouteDefinitions.some(row => row.name === ruleIdentity.routeName))

assert.equal((page.match(/打开工程规则定义/g) || []).length, 3, 'rule-only, source, and order-line modes must expose one governed entry each')
assert(page.includes("name: 'FoundationEngineeringRuleDefinitions'"))
assert(page.includes("const returnLocation = businessPageLocation('input')"))
assert(page.includes('returnTo: returnLocation.path'))
assert(page.includes('activeDraft.value?.sourceVersion'))
assert.equal((page.match(/<el-button type="primary" class="formal-card-action"/g) || []).length, 3, 'all three mutually exclusive entry modes must use the normal primary business button')
assert(page.includes("navigationScope: sourceScope ? 'source' : 'order-line'"))
assert(page.includes("navigationScope: 'rules-entry'"))
assert(page.includes("loadPermissionProfile({ force: true })"))
assert(page.includes("accessMode.value = canViewRules ? 'rules-only' : 'denied'"))
assert(page.includes("if (!canViewCalculation)"))
assert(page.includes('restrictedCalculationFactsRequested: ruleOnlyEntryMode.value ? false : null'))
assert(page.includes('不会读取或展示订单、来源、设计对象、基线、实例或核算结果'))
assert(page.includes("Number(selection.salesOrderItemId) > 0"))
assert(page.includes("...(!sourceScope && selectedOrder.value?.lineNo ? { salesOrderLineNo:"))

assert(maintenance.includes('返回工程数据录入'))
assert(maintenance.includes('返回工程规则入口'))
assert(maintenance.includes('返回业务上下文'))
assert(maintenance.includes('查看范围：{{ ruleReturnScopeLabel }}'))
assert(maintenance.includes("if (navigationScope === 'source') return `整单来源${countLabel}`"))
assert(maintenance.includes("if (navigationScope === 'rules-entry') return '当前公司共用工程规则（无订单上下文）'"))
assert(maintenance.includes("if (!stableSalesOrderItemId) return '销售订单行范围未核实'"))
assert(maintenance.includes('企业共用规则仍按当前公司、适用范围及服务端权限读取，不按订单过滤。'))
assert(maintenance.includes("target.startsWith('/pde/engineering-calculations')"))
assert(maintenance.includes("pdeApi.productionFoundationA1(isRuleDefinitions ? selectedEntity.value : '')"))
assert(maintenance.includes('当前账号没有“查看工程规则定义”权限。'))
assert(maintenance.includes('currentUserAuthorization'))

assert(backend.includes('current_user_authorization'))
assert(backend.includes('当前账号没有“查看工程规则定义”权限。'))

console.log(JSON.stringify({
  result: 'passed',
  entryCount: 3,
  routeName: ruleIdentity.routeName,
  routePath: ruleIdentity.routePath,
  targetComponent: ruleIdentity.component,
  permissionDeniedCopy: '当前账号没有“查看工程规则定义”权限。',
  returnLabels: ['返回工程规则入口', '返回工程数据录入'],
}, null, 2))
