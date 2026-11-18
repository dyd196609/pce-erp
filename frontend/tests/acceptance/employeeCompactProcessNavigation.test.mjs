import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import * as Vue from 'vue'
import {parse} from '@vue/compiler-sfc'
import {compile} from '@vue/compiler-dom'
import {renderToString} from '@vue/server-renderer'
const s=fs.readFileSync(new URL('../../src/meta/components/PceListPageShell.vue',import.meta.url),'utf8')
const template=parse(s).descriptor.template.content
const start=template.indexOf('<nav v-if="props.compactEmployeeView && props.showCompactProcessNavigation')
const end=template.indexOf('</details>',start)+'</details>'.length
const render=Function('Vue',compile(template.slice(start,end),{mode:'function'}).code)(Vue)
async function html(enabled,{previous='/planning/operation-handovers?subview=output&taskId=14&workOrderId=2',next='/planning/operation-completions?taskId=14&workOrderId=2',compact=true}={}){
 const ctx={props:{compactEmployeeView:compact,showCompactProcessNavigation:enabled},financePage:null,governedPage:{purpose:'正式交接'},pageTitle:'工序交接单',operationConfig:null,previousNavigation:{label:'部分产出确认',pageUrl:previous},currentNavigation:{label:'工序批次交接与实际接收'},nextNavigation:{label:'独立审核完工',pageUrl:next}}
 const app=Vue.createSSRApp({render,setup:()=>ctx});app.component('router-link',{props:['to'],render(){return Vue.h('a',{href:this.to},this.$slots.default?.())}});return renderToString(app)
}
test('opt-in process navigation remains outside closed guide and preserves original scoped destinations',async()=>{const x=await html(true);assert(x.indexOf('aria-label="业务流程导航"')<x.indexOf('<details'));assert.equal((x.match(/aria-label="业务流程导航"/g)||[]).length,1);assert(x.includes('subview=output&amp;taskId=14&amp;workOrderId=2'));assert(x.includes('/planning/operation-completions?taskId=14&amp;workOrderId=2'));assert(!x.match(/<details[^>]*\bopen\b/))})
test('default leaves existing compact pages navigation inside their guide',async()=>{const x=await html(undefined);assert(x.indexOf('aria-label="业务流程导航"')>x.indexOf('<details'));assert.equal((x.match(/aria-label="业务流程导航"/g)||[]).length,1);assert(x.includes('页面说明与业务流程'))})
test('absent original destinations remain labels without new links',async()=>{const x=await html(true,{previous:null,next:null});assert(!x.includes('<a '));assert(x.includes('<strong>部分产出确认</strong>'));assert(x.includes('<strong>独立审核完工</strong>'))})
test('option does not add compact navigation on noncompact pages',async()=>{assert(!(await html(true,{compact:false})).includes('aria-label="业务流程导航"'))})
