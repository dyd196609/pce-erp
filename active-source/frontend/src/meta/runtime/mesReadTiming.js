import {ref,watch,nextTick,onBeforeUnmount} from 'vue'
// Observability only. Intent carries no account, permission or business fact.
let sequence=0, intent=null, installed=false
let documentResourceObserver = null
const documentResourceEntries = []
const now=()=>globalThis.performance?.now?.() ?? Date.now()
export function beginMesReadIntent(kind='interaction',stamp=now()) {
 intent={id:++sequence,kind,started:stamp,routeStarted:null,routeFinished:null,http:[]}
 return intent
}
export function installMesReadIntentCapture() {
 if(installed || !globalThis.document)return
 installed=true
 // Capture precedes component handlers, router guards and lazy loading.
 document.addEventListener('click',event=>{
  if(event.target?.closest?.('a,button,[role="button"]'))beginMesReadIntent('user-click',now())
 },true)
 document.addEventListener('change',event=>{
  if(event.target?.closest?.('select'))beginMesReadIntent('user-selection',now())
 },true)
 // Initial document refresh includes script/bootstrap/auth preparation.
 if(!intent)beginMesReadIntent('document-navigation',0)
 if (globalThis.location?.hash.startsWith('#/planning/operation-handovers')) observeHandoverNavigation()
}
export function markMesRouteStart(){if(!intent)beginMesReadIntent('programmatic-route');intent.routeStarted=now()}
export function markMesRouteEnd(){if(intent)intent.routeFinished=now()}
const handoverResources = new Set([
 '/api/enterprise/masterdata/materials/facts/', '/api/masterdata/enterprise/materials/facts/',
 '/api/access-control/profile/', '/api/planning/operation-handovers/',
])
function collectHandoverResources(entries) {
 for (const entry of entries) {
  const url = new URL(entry.name)
  if (url.origin === globalThis.location?.origin && handoverResources.has(url.pathname)) {
   documentResourceEntries.push(entry)
  }
 }
}
function observeHandoverNavigation() {
 if (!globalThis.PerformanceObserver?.supportedEntryTypes?.includes('resource')) return
 // Native resource buffers can fill while Vite loads modules. Start observing
 // before mounting, then disconnect at the first complete document detail.
 documentResourceObserver = new PerformanceObserver(list => collectHandoverResources(list.getEntries()))
 documentResourceObserver.observe({type:'resource', buffered:true})
}
function handoverDocumentRequests() {
 if (documentResourceObserver) {
  collectHandoverResources(documentResourceObserver.takeRecords())
  documentResourceObserver.disconnect()
  documentResourceObserver = null
 } else {
  collectHandoverResources(globalThis.performance?.getEntriesByType?.('resource') || [])
 }
 return documentResourceEntries.splice(0).map(entry => {
  const url = new URL(entry.name)
  return {path:url.pathname, startMs:entry.startTime, requestStartMs:entry.requestStart,
   responseStartMs:entry.responseStart, endMs:entry.responseEnd,
   serverMs:entry.serverTiming?.find(mark => mark.name === 'routing-read')?.duration ?? null}
 })
}
export function useMesReadTiming(readState){
 const visibleReadMs=ref(null),readCycle=ref(0);let active=null,disposed=false
 watch(readState,async value=>{
  if(value==='loading'){
   // A passive refresh without a DOM event must not reuse an old ready cycle.
   if(!intent || intent.completed)beginMesReadIntent('programmatic-read')
   active={intent,componentStarted:now(),cycle:++readCycle.value};visibleReadMs.value=null
  }else if(value==='loaded' && active){
   const current=active;await nextTick()
   if(disposed || active!==current || current.cycle!==readCycle.value || readState()!=='loaded')return
   const completed=now();visibleReadMs.value=completed-current.intent.started
   current.intent.completed=true
   const sample={intentId:current.intent.id,startKind:current.intent.kind,totalReadyMs:visibleReadMs.value,
    componentReadMs:completed-current.componentStarted,routeAuthPreparationMs:current.intent.routeFinished!==null && current.intent.routeStarted!==null
      ? current.intent.routeFinished-current.intent.routeStarted:null,http:current.intent.http,
    ready:true,url:globalThis.location?.href,contains:'total includes route/auth + HTTP/server + validation/DOM; spans overlap'}
   if (sample.startKind === 'document-navigation' && globalThis.location?.hash.startsWith('#/planning/operation-handovers')) {
    sample.documentRequests = handoverDocumentRequests()
    sample.startupMilestones = {
     navigationStartMs: 0,
     routerStartedMs: current.intent.routeStarted,
     sessionCheckedMs: globalThis.performance?.getEntriesByName?.('pce:handover-session-checked').at(-1)?.startTime ?? null,
     routeReadyMs: current.intent.routeFinished,
     detailRequestIssuedMs: sample.documentRequests.find(entry => entry.path === '/api/planning/operation-handovers/')?.requestStartMs ?? null,
     detailOperableMs: completed,
    }
   }
   console.info('PCE_MES_BUSINESS_READY',JSON.stringify(sample))
   if(globalThis.window)window.dispatchEvent(new CustomEvent('pce-mes-business-ready',{detail:sample}))
  }else if(value==='read_failed'){visibleReadMs.value=null;active=null}
 },{immediate:true})
 onBeforeUnmount(()=>{disposed=true;active=null})
 return {visibleReadMs,readCycle}
}
export async function timedMesRead(load,path){
 const current=intent,started=now()
 try{const result=await load();const sample={path,durationMs:now()-started,httpStatus:result?.data?.factLoadFacts?.httpStatus??result?.factLoadFacts?.httpStatus??null,success:result?.success===true};current?.http.push(sample);console.info('PCE_MES_READ_TIMING',JSON.stringify(sample));return result}
 catch(error){const sample={path,durationMs:now()-started,success:false};current?.http.push(sample);console.info('PCE_MES_READ_TIMING',JSON.stringify(sample));throw error}
}
