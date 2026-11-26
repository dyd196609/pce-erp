import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import {operationVisibilityContractPresentIn} from '../../scripts/verifySystemConfigNonRegression.mjs'
const source=fs.readFileSync(new URL('../../src/meta/components/ProductionFoundationMaintenance.vue',import.meta.url),'utf8')
test('current authoritative, failure-aware visibility contract passes',()=>assert.equal(operationVisibilityContractPresentIn(source,{dataSource:'system.Process'}),true))
for(const [name,mutate,contract] of [
 ['wrong model',s=>s,{dataSource:'pde.Routing'}],
 ['unknown count replaced with zero',s=>s.replace('currentRows.value.length : null','currentRows.value.length : 0')],
 ['failure guard removed',s=>s.replace(' && !providerFailed.value','')],
 ['old raw array count restored',s=>s.replace('? currentRecordCount : undefined','? currentRows.length : undefined')],
 ['source replaced',s=>s.replace('operationFacts.value = operation.facts.operations','operationFacts.value = []')],
 ['required mode removed',s=>s.replace('>人工验收</button>','>其它</button>')],
]) test(`visibility guard rejects ${name}`,()=>assert.equal(operationVisibilityContractPresentIn(mutate(source),contract||{dataSource:'system.Process'}),false))
