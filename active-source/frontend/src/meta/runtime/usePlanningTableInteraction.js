import {nextTick,onMounted,onBeforeUnmount,watch} from 'vue'
import {createColumnWidthPreferenceRuntime,columnPreferenceKey} from './columnWidthPreferences.js'
import {readTabIdentity} from './tabAuthenticationContext.js'

// Local adapter for the two existing native PlanningCenter tables. Presentation only.
export function usePlanningTableInteraction(tables,compact,onLayout) {
 const states=new Map();let observer=null,queued=false,disposed=false,drag=null,frame=0
 const columns=t=>Array.isArray(t?.columns)?t.columns:t?.store?.states?.columns?.value||[]
 const userKey=()=>{const x=readTabIdentity();return x?.username?`${x.companyId??'unknown'}:${x.username}`:''}
 const owner=t=>t?.$el?.querySelector('.el-table__body-wrapper .el-scrollbar__wrap')
 const cap=t=>Math.max(80,(owner(t)?.clientWidth||248)-72)
 function layout(t){t?.doLayout?.();cancelAnimationFrame(frame);frame=requestAnimationFrame(()=>{onLayout?.();decorate()})}
 function ensure(key,t) {
  let s=states.get(key)
  if(!s){s={t,original:new Map(),mode:null,runtime:null};states.set(key,s)}
  const mode=compact.value?'compact':'desktop'
  const changed=s.mode!==mode;let added=false
  for(const c of columns(t)) {
   const id=columnPreferenceKey(c)
   if(!s.original.has(id)){added=true;s.original.set(id,{width:c.width,minWidth:c.minWidth,realWidth:c.realWidth,maxWidth:c.maxWidth})}
  }
  if(changed) {
   s.mode=mode
   for(const [index,c] of columns(t).entries()) {
    const original=s.original.get(columnPreferenceKey(c))
    if(compact.value){c.minWidth=index===0?80:72;c.maxWidth=index===0?cap(t):960;c.width=c.label==='业务动作'?96:Math.min(Number(original.width||original.minWidth||original.realWidth)||120,index===0?cap(t):960);c.realWidth=c.width}
    else Object.assign(c,original)
   }
   if(compact.value){s.runtime=createColumnWidthPreferenceRuntime({storage:window.localStorage,userKey:userKey(),pageId:'planning-requirements',tableId:`${key}-compact`});s.runtime.capture(t);s.runtime.apply(t)}
   else s.runtime=null
   layout(t)
  } else if(compact.value) {
   for(const [index,c] of columns(t).entries()) {
    c.minWidth=index===0?80:72;c.maxWidth=index===0?cap(t):960
    if(c.label==='业务动作'&&!Number(c.width)){c.width=96;c.realWidth=96}
   }
   s.runtime?.capture(t)
   if(added){s.runtime?.apply(t);layout(t)}
  }
  return s
 }
 function sync(){
  for(const [key,ref] of Object.entries(tables)){
   const t=ref.value;if(!t?.$el)continue
   const s=ensure(key,t),first=columns(t)[0]
   if(compact.value&&first&&drag?.state!==s){
    const key=columnPreferenceKey(first),saved=s.runtime?.read().columns||{}
    const original=s.original.get(key),defaultWidth=Math.min(Number(original?.width||original?.minWidth||original?.realWidth)||120,cap(t))
    const desired=!s.manualFirst&&!Object.prototype.hasOwnProperty.call(saved,key)?defaultWidth:Math.min(Number(first.width),cap(t))
    if(Number(first.width)!==desired){first.width=desired;first.realWidth=desired;layout(t)}
   }
  }
  decorate()
 }
 function move(event){
  if(!drag||event.pointerId!==drag.pointerId)return
  event.preventDefault();event.stopPropagation()
  const desired=drag.width+event.clientX-drag.x
  drag.column.width=Math.min(Number(drag.column.maxWidth)||960,Math.max(Number(drag.column.minWidth)||72,desired));drag.column.realWidth=drag.column.width
  layout(drag.state.t)
 }
 function finish(event){
  if(!drag||event.pointerId!==drag.pointerId)return
  const active=drag;drag=null
  window.removeEventListener('pointermove',move);window.removeEventListener('pointerup',finish);window.removeEventListener('pointercancel',cancel)
  active.state.runtime?.persist(active.column.width,active.column)
  if(active.column===columns(active.state.t)[0])active.state.manualFirst=true
  active.state.t.$el.dataset.planningLastResizePointerType=active.pointerType
  active.state.t.$el.dataset.planningLastResizeWidth=String(active.column.width)
  layout(active.state.t)
 }
 function cancel(){
  if(drag){const active=drag;drag=null;active.column.width=active.width;active.column.realWidth=active.width;layout(active.state.t)}
  window.removeEventListener('pointermove',move);window.removeEventListener('pointerup',finish);window.removeEventListener('pointercancel',cancel)
 }
 function begin(event,state,column){
  if(!compact.value||drag||event.isPrimary===false||(event.pointerType==='mouse'&&event.button!==0))return
  event.preventDefault();event.stopImmediatePropagation()
  drag={state,column,pointerId:event.pointerId,pointerType:event.pointerType,x:event.clientX,width:Number(column.realWidth||column.width||column.minWidth)}
  event.currentTarget.setPointerCapture?.(event.pointerId)
  window.addEventListener('pointermove',move,{passive:false});window.addEventListener('pointerup',finish);window.addEventListener('pointercancel',cancel)
 }
 function decorate(){
  if(disposed)return
  for(const state of states.values()) {
   const root=state.t.$el
   if(!compact.value){root.querySelectorAll('[data-plan-resize-handle]').forEach(x=>x.remove());continue}
   for(const th of root.querySelectorAll('thead th')) {
    const column=columns(state.t).find(c=>th.classList.contains(c.id))
    if(!column||th.querySelector('[data-plan-resize-handle]'))continue
    const handle=document.createElement('button');handle.type='button';handle.className='planning-column-resize-handle';handle.dataset.planResizeHandle=columnPreferenceKey(column);handle.setAttribute('role','separator');handle.setAttribute('aria-orientation','vertical');handle.setAttribute('aria-label',`拖动调整${column.label}列宽`);handle.title='按住边界左右拖动调整列宽';handle.textContent='↔'
    handle.addEventListener('pointerdown',e=>begin(e,state,column))
    handle.addEventListener('click',e=>{e.preventDefault();e.stopImmediatePropagation()})
    handle.addEventListener('keydown',e=>{if(!['ArrowLeft','ArrowRight'].includes(e.key))return;e.preventDefault();e.stopPropagation();state.runtime?.persist(Number(column.realWidth)+(e.key==='ArrowRight'?8:-8),column);layout(state.t)})
    th.appendChild(handle)
   }
  }
 }
 function schedule(){if(queued||disposed)return;queued=true;nextTick(()=>{queued=false;if(!disposed)sync()})}
 function reset(key){cancel();const s=states.get(key);if(s)s.manualFirst=false;s?.runtime?.reset(s.t);layout(s?.t)}
 function dragend(key,width,oldWidth,column){const s=states.get(key);if(compact.value)s?.runtime?.persist(width,column);else if(s&&column)s.original.set(columnPreferenceKey(column),{width:column.width,minWidth:column.minWidth,realWidth:column.realWidth,maxWidth:column.maxWidth});layout(s?.t)}
 function identityChanged(){cancel();for(const s of states.values())s.mode=null;schedule()}
 watch(()=>[compact.value,...Object.values(tables).map(r=>columns(r.value).length)],schedule)
 onMounted(()=>{schedule();observer=new MutationObserver(schedule);for(const ref of Object.values(tables))if(ref.value?.$el)observer.observe(ref.value.$el.querySelector('thead'),{childList:true,subtree:true});window.addEventListener('pce:authentication-changed',identityChanged)})
 onBeforeUnmount(()=>{disposed=true;cancel();observer?.disconnect();cancelAnimationFrame(frame);window.removeEventListener('pce:authentication-changed',identityChanged);for(const s of states.values())s.t.$el?.querySelectorAll('[data-plan-resize-handle]').forEach(x=>x.remove())})
 return {sync,reset,dragend}
}
