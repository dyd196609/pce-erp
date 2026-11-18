import {getTabAuthEpoch,readTabIdentity} from './tabAuthenticationContext.js'

// M02 explicitly opts in independently reproduced original organization catalogs, supplier and customer lists. Other routes retain
// their existing in-memory behavior; no business facts are saved.
export function isPersistentPresentationKey(key) {
 try {
  if(!/^(table|filters):/.test(key))return false
  const path=key.slice(key.indexOf(':')+1).split(':')[0]
  const route=new URL(path,'http://presentation.invalid')
  if(['/master-data/suppliers','/master-data/customers'].includes(route.pathname))return !route.searchParams.has('view')
  return route.pathname==='/organization'&&['responsibilities','companies','departments','positions','employees','users','roles','permissions','review-grants','job-families','job-levels'].includes(route.searchParams.get('tab'))
 }catch{return false}
}
export function presentationRoutePath(path) {
 try{const route=new URL(path,'http://presentation.invalid');if(['/master-data/suppliers','/master-data/customers'].includes(route.pathname)){route.searchParams.delete(route.pathname==='/master-data/suppliers'?'supplierId':'customerId');return route.pathname+route.search}if(route.pathname==='/organization'&&['responsibilities','companies'].includes(route.searchParams.get('tab'))){
  route.searchParams.delete(route.searchParams.get('tab')==='companies'?'companyId':'responsibilityId');return route.pathname+(route.search?route.search:'')
 }}catch{/* Existing route remains unchanged. */}
 return path
}
const forbidden=new Set(['__proto__','constructor','prototype'])
const text=value=>typeof value==='string'&&value.length<=1000?value:undefined
function cleanPresentation(key,value) {
 if(!value||typeof value!=='object'||Array.isArray(value))return null
 const result={}
 if(key.startsWith('table:')) {
  for(const name of ['page','size','left','top','pageY']){const n=value[name];if(typeof n==='number'&&Number.isFinite(n)&&n>=0&&n<=10000000)result[name]=n}
  if(!Number.isSafeInteger(result.page)||result.page<1)delete result.page
  if(![10,20,50,100].includes(result.size))delete result.size
 }else{
  for(const name of ['quickSearch','appliedSearch'])if(text(value[name])!==undefined)result[name]=value[name]
  if(typeof value.advancedVisible==='boolean')result.advancedVisible=value.advancedVisible
  if(value.sortState&&text(value.sortState.prop)!==undefined&&['','ascending','descending'].includes(value.sortState.order))result.sortState={prop:value.sortState.prop,order:value.sortState.order}
  if(value.filters&&typeof value.filters==='object'&&!Array.isArray(value.filters)){
   const filters={};const scalar=v=>v===null||typeof v==='boolean'||(typeof v==='number'&&Number.isFinite(v))||text(v)!==undefined
   for(const [name,item] of Object.entries(value.filters).slice(0,100)){
    if(forbidden.has(name)||name.length>100)continue
    if(scalar(item))filters[name]=item
    else if(Array.isArray(item)&&item.length<=20&&item.every(scalar))filters[name]=item
   }result.filters=filters
  }
 }
 if(!Object.keys(result).length)return null
 if(!key.startsWith('table:'))return {quickSearch:'',appliedSearch:'',advancedVisible:false,sortState:{prop:'',order:''},filters:{},...result}
 return result
}
export function createPresentationContext(epochProvider,options={}) {
 let epoch=epochProvider(),scope=null,initialized=false;const states=new Map(),parents=new Map()
 const storageKey=()=>scope?`pce.presentation.m02.v1:${scope}`:null
 const storage=()=>{try{return options.storageProvider?.()}catch{return null}}
 const persist=()=>{const key=storageKey();if(!key)return
  const values=Array.from(states).filter(([name])=>isPersistentPresentationKey(name)).map(([name,value])=>[name,cleanPresentation(name,value)]).filter(([,value])=>value)
  try{storage()?.setItem(key,JSON.stringify(values.slice(-100)))}catch{/* Keep the existing memory-only behavior when preference storage is unavailable. */}}
 const sync=()=>{
  const current=epochProvider(),identity=options.identityProvider?.(),nextScope=identity?.username?`${String(identity.userId??identity.id??'')}:${identity.username}`:null
  if(!initialized||current!==epoch||nextScope!==scope){states.clear();parents.clear();epoch=current;scope=nextScope;initialized=true
   try{const key=storageKey(),saved=key?JSON.parse(storage()?.getItem(key)||'[]'):[]
    if(Array.isArray(saved))for(const entry of saved.slice(-100))if(Array.isArray(entry)&&isPersistentPresentationKey(entry[0])){const value=cleanPresentation(entry[0],entry[1]);if(value)states.set(entry[0],value)}
   }catch{/* Corrupt preferences never become facts or block service reading. */}}
  return options.identityProvider?`${epoch}:${scope||'unidentified'}`:epoch
 }
 return {epoch:sync,persistent:isPersistentPresentationKey,read:key=>{sync();return states.has(key)?JSON.parse(JSON.stringify(states.get(key))):null},
  save:(key,value,owner)=>{if(owner!==sync())return;const stored=isPersistentPresentationKey(key)?cleanPresentation(key,value):value;if(!stored)return;states.set(key,JSON.parse(JSON.stringify(stored)));if(states.size>100)states.delete(states.keys().next().value);if(isPersistentPresentationKey(key))persist()},
  parent:key=>{sync();return parents.get(key)||'/home'},
  remember:(to,from)=>{sync();if(from.path==='/system-login'||!from.matched?.length)return;
   if(parents.get(from.fullPath)===to.fullPath)return;
   if(to.path===from.path){if(parents.has(from.fullPath))parents.set(to.fullPath,parents.get(from.fullPath));return}
   if(to.path.startsWith('/planning/')&&(from.path==='/home'||from.path.startsWith('/planning/')))parents.set(to.fullPath,from.fullPath)},
  clear:()=>{sync();states.clear();parents.clear();persist()}}
}
export const workPresentation=createPresentationContext(()=>typeof window==='undefined'?0:getTabAuthEpoch(),{
 identityProvider:()=>typeof window==='undefined'?null:readTabIdentity(),storageProvider:()=>typeof window==='undefined'?null:window.sessionStorage,
})
if(typeof window!=='undefined')window.addEventListener('pce:authentication-changed',()=>workPresentation.epoch())
