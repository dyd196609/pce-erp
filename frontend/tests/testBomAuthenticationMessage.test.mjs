import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import {ref,computed} from 'vue'
import {testBomFailure} from '../src/meta/runtime/testBomFailure.js'
const page=readFileSync(new URL('../src/meta/pages/components/TestBusinessBomHandoff.vue',import.meta.url),'utf8')
function panel(response){
 const body=page.split('<script setup>')[1].split('</script>')[0].replace(/^import .*$/gm,'')
 const events=[];const api={testBusinessBomHandoff:async()=>response,generateOrderBom:async()=>response,deriveTestBom:async()=>response}
 const setup=new Function('ref','computed','onMounted','useRoute','useRouter','pdeApi','resolvePceBusinessActions','testBomFailure','defineEmits','defineExpose',body+'\nreturn {load,generate,derive,loaded,error,records,selectedId,authenticationRequired,receipt,loginLocation}')
 const state=setup(ref,computed,()=>{},()=>({query:{orderId:'1',sourceCalculationId:'1'}}),()=>({replace:()=>{}}),api,()=>({availableActions:[],unavailableActions:[]}),testBomFailure,()=>((...event)=>events.push(event)),()=>{})
 return {state,api,events}
}
const ok={success:true,data:{records:[{id:1,salesOrderId:1,preview:{previewHash:'proof'},components:[]}]}}
for(const [name,response] of [
 ['anonymous',{success:false,httpStatus:401,error:{code:'HTTP_401',message:'Authentication credentials were not provided.'}}],
 ['expired-session',{success:false,meta:{status:403},error:{code:'HTTP_403',message:'Token已过期，请重新登录'}}],
 ['invalid-token',{success:false,httpStatus:401,error:{code:'TOKEN_NOT_VALID',message:'Token is invalid'}}],
 ['identity-changed',{success:false,error:{code:'AUTHENTICATION_CONTEXT_CHANGED',message:'标签页登录身份已变化'}}],
])test(name+' clears stale facts and offers normal login',async()=>{const {state,api,events}=panel(response);state.records.value=[{id:99}];state.loaded.value=true;state.receipt.value='旧保存结果';await state.load();assert.equal(state.loaded.value,false);assert.deepEqual(state.records.value,[]);assert.equal(state.selectedId.value,null);assert.equal(state.receipt.value,'');assert.equal(state.authenticationRequired.value,true);assert.match(state.error.value,/重新登录/);assert.doesNotMatch(state.error.value,/object Object|材料缺项/);assert.equal(state.loginLocation,'/login');assert.deepEqual(events.at(-1),['facts',null]);api.testBusinessBomHandoff=async()=>ok;await state.load();assert.equal(state.loaded.value,true);assert.equal(state.authenticationRequired.value,false);assert.equal(state.selectedId.value,1)})
for(const operation of ['generate','derive'])test(operation+' session loss is not success',async()=>{const {state,api,events}=panel(ok);await state.load();events.length=0;api[operation==='generate'?'generateOrderBom':'deriveTestBom']=async()=>({success:false,httpStatus:401,error:{message:'会话已失效'}});await state[operation]({id:2});assert.equal(state.authenticationRequired.value,true);assert.equal(state.loaded.value,false);assert.ok(!events.some(e=>e[0]==='saved'));assert.doesNotMatch(state.error.value,/object Object/)})
test('permission denial remains distinct from authentication and materials',()=>{const r=testBomFailure({httpStatus:403,error:{code:'PERMISSION_DENIED',message:'维护权限不足'}});assert.equal(r.authenticationRequired,false);assert.match(r.message,/无权/);assert.doesNotMatch(r.message,/材料|登录/)})
test('structured material blocker is a business error, not authentication',()=>{const r=testBomFailure({httpStatus:400,error:{code:'TEST_MATERIAL_REQUIREMENT_REQUIRED',message:'缺少材料需求映射'}});assert.equal(r.message,'缺少材料需求映射');assert.equal(r.authenticationRequired,false)})
test('unstructured object gets Chinese fallback without object coercion',()=>{assert.equal(testBomFailure({error:{details:{}}}).message,'测试BOM操作未完成，请重试。')})
test('network read failure hides data without an empty-valid success',async()=>{const {state,events}=panel({success:false,error:{code:'NETWORK_READ_FAILED',message:'网络读取失败'}});await state.load();assert.equal(state.loaded.value,false);assert.equal(state.authenticationRequired.value,false);assert.deepEqual(events.at(-1),['facts',null]);assert.match(state.error.value,/网络读取失败/)})
