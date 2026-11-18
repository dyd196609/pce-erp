// UI preferences and navigation only: never stores business facts or eligibility.
export function learningPreference(page, principal, storage) {
  const key = () => { const p = principal(); return p?.userId && p?.companyId ? `pce:learning:v1:${p.companyId}:${p.userId}:${page}` : null }
  return {
    read() { try { const k=key(); const store=storage===undefined?globalThis.localStorage:storage; return !!k && store?.getItem(k)==='open' } catch { return false } },
    write(open) { try { const k=key(); const store=storage===undefined?globalThis.localStorage:storage; if(k)store?.setItem(k,open ? 'open':'closed') } catch { /* Presentation works without persistence. */ } },
  }
}
export function handoverListQuery(query) {
  const result={...query,screen:'list'}
  for(const key of ['handoverId','businessNo','outputId','exceptionId','custodyWorkCenterId'])delete result[key]
  return result
}
export function readableCondition(value) {
  const text=typeof value==='string' ? value : value?.statusLabel || value?.message || '当前条件未通过核验。'
  // Retain the server's Chinese meaning; codes themselves remain in technical details.
  const shown=text.replace(/\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b/g,'（标识见技术详情）')
  return shown || '当前条件未通过核验，请查看技术详情。'
}
