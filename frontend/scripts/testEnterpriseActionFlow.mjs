import {test} from 'node:test'
import assert from 'node:assert/strict'
import {validateActionFlow} from '../src/meta/runtime/pceActionFlowContract.js'
import {BusinessActionRegistry} from '../src/meta/runtime/pceBusinessActionRegistry.js'
const terminal={currentModule:'routing-management',route:'/pde/routings',nextModule:'routing-management',nextRoute:'/pde/routings',terminal:true}
test('registered routing terminals use existing self identity expression',()=>{
 for(const id of ['routing-management','routing-version-management']) assert.equal(validateActionFlow(BusinessActionRegistry.getContract(id)),true)
})
test('non terminal missing downstream stays rejected',()=>assert.equal(validateActionFlow({...terminal,terminal:false,nextModule:'',nextRoute:''}),false))
test('terminal with other downstream or wrong route stays rejected',()=>{
 assert.equal(validateActionFlow({...terminal,nextModule:'other'}),false)
 assert.equal(validateActionFlow({...terminal,nextRoute:'/other'}),false)
})
test('known downstream route identity must match',()=>assert.equal(validateActionFlow({currentModule:'a',route:'/a',nextModule:'b',nextRoute:'/wrong'},[{currentModule:'b',route:'/b'}]),false))
