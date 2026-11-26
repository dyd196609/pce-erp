import assert from 'node:assert/strict'
import test from 'node:test'
import fs from 'node:fs'
import vm from 'node:vm'
import { parse, compileTemplate } from '@vue/compiler-sfc'
import { submitManufacturingOutputRelease } from '../../src/meta/pages/manufacturingOutputGenerationSubmission.js'
const proof={ completed:true,writeRequestId:101,auditId:102,businessStateTransitionId:103 }
const result={ row:{id:1,statusCode:'released_to_manufacturing'},...proof,releaseReadback:proof }
const candidate={ output:{id:1,statusCode:'released_to_manufacturing'},manufacturingRelease:{releaseReadback:proof} }
const options=extra=>({confirm:async()=>{},request:async()=>({success:true,data:{result}}),refresh:async()=>{},
  readback:()=>candidate,isSubmitting:()=>false,setSubmitting:()=>{},...extra})
test('发布事务响应与正式回读一致才允许成功',async()=>{
  assert.equal((await submitManufacturingOutputRelease(options())).result.row.id,1)
})
for(const status of [200,400,401,403,409,500]) {
  test(`HTTP ${status}业务失败保留准确错误`,async()=>{
    await assert.rejects(submitManufacturingOutputRelease(options({request:async()=>({success:false,
      meta:{status},error:{code:'PUBLISHER_DENIED',message:'正式发布人拒绝'}})})),/PUBLISHER_DENIED.*正式发布人拒绝/)
  })
}
test('确认取消不发送发布请求',async()=>{
  let sent=0
  await assert.rejects(submitManufacturingOutputRelease(options({confirm:async()=>{throw 'cancel'},request:async()=>{sent++}})),x=>x==='cancel')
  assert.equal(sent,0)
})
test('在途重复提交只发送一次',async()=>{
  let busy=false,sent=0,finish
  const barrier=new Promise(resolve=>{finish=resolve})
  const shared=options({isSubmitting:()=>busy,setSubmitting:x=>{busy=x},request:async()=>{sent++;await barrier;return {success:true,data:{result}}}})
  const first=submitManufacturingOutputRelease(shared)
  assert.equal((await submitManufacturingOutputRelease(shared)).duplicateSuppressed,true)
  finish();await first;assert.equal(sent,1);assert.equal(busy,false)
})
test('缺正式发布事实或回读不一致不宣称成功',async()=>{
  await assert.rejects(submitManufacturingOutputRelease(options({request:async()=>({success:true,data:{result:{...result,auditId:null}}})})),/SUCCESS_CONTRACT_INVALID/)
  await assert.rejects(submitManufacturingOutputRelease(options({readback:()=>({...candidate,output:{id:1,statusCode:'draft'}})})),/READBACK_MISMATCH/)
})
test('网络错误释放在途锁',async()=>{
  let busy=false
  await assert.rejects(submitManufacturingOutputRelease(options({setSubmitting:x=>{busy=x},request:async()=>{throw Error('网络失败')}})),/网络失败/)
  assert.equal(busy,false)
})
const page=fs.readFileSync(new URL('../../src/meta/pages/PdeFoundationPage.vue',import.meta.url),'utf8')
const start=page.indexOf('async function handleReleaseManufacturingOutput(payload)')
const handler=page.slice(start,page.indexOf('\nfunction failureMessage',start))
test('真实页面发布函数处理成功、失败、确认取消',async()=>{
  for(const phase of ['success','fail','cancel']) {
    const successes=[],errors=[],requests=[]
    const state={value:false}
    const run=vm.runInNewContext(`${handler};handleReleaseManufacturingOutput`,{
      submitManufacturingOutputRelease,manufacturingOutputSubmitting:state,
      strictFacts:{value:{manufacturingOutputCandidate:candidate}},refresh:async()=>{},newIdempotencyKey:()=> 'key',
      ElMessageBox:{confirm:async()=>{if(phase==='cancel')throw 'cancel'}},
      ElMessage:{success:x=>successes.push(x),error:x=>errors.push(x)},
      pdeApi:{releaseManufacturingOutput:async(id,body)=>{requests.push({id,body});return phase==='fail'
        ? {success:false,meta:{status:403},error:{code:'RELEASE_DENIED',message:'发布拒绝'}} : {success:true,data:{result}}}},
    })
    await run({outputId:1,action:'pde.manufacturing_output.release',reason:'人工发布理由'})
    assert.equal(requests.length,phase==='cancel'?0:1)
    assert.equal(successes.length,phase==='success'?1:0)
    assert.equal(errors.length,phase==='fail'?1:0)
    if(phase==='fail')assert.match(errors[0],/RELEASE_DENIED/)
    if(requests.length)assert.equal(requests[0].body.outputId,undefined)
    assert.equal(state.value,false)
  }
})
test('原组件可编译且消费单一服务端发布准入',()=>{
  const source=fs.readFileSync(new URL('../../src/meta/pages/components/ManufacturingOutputHandoff.vue',import.meta.url),'utf8')
  for(const [filename,content] of [['Handoff.vue',source],['PdeFoundationPage.vue',page]]) {
    const parsed=parse(content,{filename});assert.equal(parsed.errors.length,0)
    assert.equal(compileTemplate({source:parsed.descriptor.template.content,filename,id:'release-test'}).errors.length,0)
  }
  assert.match(source,/readiness\?\.releaseAllowed/)
  assert.match(page,/@release="handleReleaseManufacturingOutput"/)
})
