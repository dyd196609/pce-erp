// Navigation locators only. Formal facts, permissions, reasons and draft inputs
// are always read from the server or entered anew; none are persisted here.
const positive = value => typeof value === 'string' && /^[1-9][0-9]{0,14}$/.test(value) ? value : ''
export const WORKSHOP_RECEPTION_LOCATION_STORAGE_KEY = 'pce_workshop_reception_view_location_v1'
export const WORKSHOP_RECEPTION_LOCATION_KEYS = Object.freeze(['receiptContextCompanyId', 'receiptContextUserId',
  'receiptContextPlanId', 'receiptWorkOrderId', 'receiptWorkshopId', 'resourceOperationId', 'handoffOperationId'])
export function readWorkshopReceptionLocation(query, { companyId, userId, planId }) {
  const plan = positive(String(planId || '')), company = positive(String(companyId || '')), user = positive(String(userId || ''))
  const hasContext = WORKSHOP_RECEPTION_LOCATION_KEYS.some(key => query[key] !== undefined)
  const ownerMatches = !!plan && !!company && !!user && query.receiptContextCompanyId === company
    && query.receiptContextUserId === user && query.receiptContextPlanId === plan
  return { ownerMatches, hasContext, planId: plan,
    workOrderId: ownerMatches ? positive(query.receiptWorkOrderId) : '',
    workshopId: ownerMatches ? positive(query.receiptWorkshopId) : '',
    resourceOperationId: ownerMatches ? positive(query.resourceOperationId) : '',
    handoffOperationId: ownerMatches ? positive(query.handoffOperationId) : '' }
}
export function workshopReceptionLocationQuery(query, context, patch = {}) {
  const current = readWorkshopReceptionLocation(query, context), next = { ...query }
  for (const key of WORKSHOP_RECEPTION_LOCATION_KEYS) delete next[key]
  const plan = positive(String(context.planId || ''))
  if (!plan || !positive(String(context.companyId || '')) || !positive(String(context.userId || ''))) return next
  Object.assign(next, { receiptContextCompanyId: String(context.companyId), receiptContextUserId: String(context.userId), receiptContextPlanId: plan })
  for (const [field, key] of [['workOrderId', 'receiptWorkOrderId'], ['workshopId', 'receiptWorkshopId'],
    ['resourceOperationId', 'resourceOperationId'], ['handoffOperationId', 'handoffOperationId']]) {
    const value = positive(String(patch[field] ?? current[field] ?? ''))
    if (value) next[key] = value
  }
  return next
}
export function createWorkshopReceptionLocationStore(storage) {
  let storageError=null
  if(storage===undefined){try{storage=globalThis.window?.sessionStorage}catch(error){storageError=error}}
  const memory=[]
  const fields=['companyId','userId','planId','workOrderId','workshopId','resourceOperationId','handoffOperationId']
  function rows(){if(storageError)throw new Error('当前标签页无法读取查看定位；未恢复旧定位。')
    const value=storage?JSON.parse(storage.getItem(WORKSHOP_RECEPTION_LOCATION_STORAGE_KEY)||'[]'):memory
    if(!Array.isArray(value)||!value.every(row=>row&&Object.keys(row).every(key=>fields.includes(key))
      &&['companyId','userId','planId'].every(key=>positive(row[key]))&&fields.every(key=>row[key]===''||positive(row[key]))))
      throw new Error('已保存的查看定位不完整；未替换为其他业务对象。')
    return value}
  return {
    read({companyId,userId,planId}){const company=String(companyId||''),user=String(userId||''),plan=String(planId||'')
      return [...rows()].reverse().find(row=>row.companyId===company&&row.userId===user&&(!plan||row.planId===plan))||null},
    save(value,{replaceInvalid=false}={}){const row=Object.fromEntries(fields.map(key=>[key,positive(String(value[key]||''))]))
      if(!row.companyId||!row.userId||!row.planId)return
      let previous
      try{previous=rows()}catch(error){if(!replaceInvalid||storageError)throw error;previous=[]}
      const next=[...previous.filter(item=>item.companyId!==row.companyId||item.userId!==row.userId||item.planId!==row.planId),row]
      if(storage)storage.setItem(WORKSHOP_RECEPTION_LOCATION_STORAGE_KEY,JSON.stringify(next))
      else{memory.splice(0,memory.length,...next)}},
  }
}
