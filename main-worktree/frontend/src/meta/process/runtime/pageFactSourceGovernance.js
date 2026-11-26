export const SCM_PAGE_FACT_SOURCE_CHAIN = Object.freeze([
  'Page', 'ProcessProvider', 'RuntimeContext', 'BusinessObject',
])

export function validatePageFactSourceGovernance(definition = {}) {
  const valid = Boolean(definition.pageCode)
    && Boolean(definition.providerCode)
    && definition.runtimeContext === true
    && definition.businessObject === true
    && definition.directUrlComposition === false
    && definition.directLocalStateComposition === false
    && definition.directTemporaryArrayComposition === false
    && definition.directPageCacheComposition === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid, chain: SCM_PAGE_FACT_SOURCE_CHAIN })
}

export function validateMultiEntryProviderConsistency(entryFacts = []) {
  const providerCodes = new Set(entryFacts.map(item => item.providerCode))
  const snapshotIds = new Set(entryFacts.map(item => item.factSnapshotId))
  const objectSets = new Set(entryFacts.map(item => item.preparations
    .map(preparation => preparation.inquiryPreparationNo).sort().join('|')))
  const valid = entryFacts.length === 3 && providerCodes.size === 1
    && providerCodes.has('SCM_PURCHASE_INQUIRY_LIFECYCLE_PROVIDER')
    && snapshotIds.size === 1 && objectSets.size === 1
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid,
    entryCount: entryFacts.length, providerCode: [...providerCodes][0] || '', snapshotId: [...snapshotIds][0] || '' })
}

