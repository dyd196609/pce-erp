import assert from 'node:assert/strict'
import test from 'node:test'
import {BusinessActionRegistry} from '../../src/meta/runtime/pceBusinessActionRegistry.js'
import {hasCompleteActionContract} from '../../scripts/pceBusinessActionContractShape.mjs'
test('existing internal editors keep their original commands; incomplete navigation is rejected',()=>{
 const rows=BusinessActionRegistry.list();assert(rows.every(hasCompleteActionContract))
 const editor=structuredClone(rows.find(c=>c.currentModule==='routing-management'))
 assert(hasCompleteActionContract(editor));editor.actions[0].actionType='navigation';assert.equal(hasCompleteActionContract(editor),false)
 editor.actions[0].actionType='command';editor.actions[0].serverEligibilityCheck=false;assert.equal(hasCompleteActionContract(editor),false)
 assert.equal(hasCompleteActionContract({...editor,currentModule:'unknown'}),false)
 assert.equal(hasCompleteActionContract({...editor,actions:[]}),false)
})
