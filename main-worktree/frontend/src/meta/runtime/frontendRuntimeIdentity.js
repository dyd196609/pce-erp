export const frontendRuntimeIdentity = Object.freeze({
  contract: 'PCE-FRONTEND-RUNTIME-IDENTITY-V1',
  buildRuntimeId: typeof __PCE_BUILD_RUNTIME_ID__ !== 'undefined' ? __PCE_BUILD_RUNTIME_ID__ : 'development-uninjected',
  sourceTreeId: typeof __PCE_SOURCE_TREE_ID__ !== 'undefined' ? __PCE_SOURCE_TREE_ID__ : 'working-tree-uninjected',
  bundleTimestamp: typeof __PCE_BUNDLE_TIMESTAMP__ !== 'undefined' ? __PCE_BUNDLE_TIMESTAMP__ : 'unknown',
  routerRegistryHash: typeof __PCE_ROUTER_HASH__ !== 'undefined' ? __PCE_ROUTER_HASH__ : 'unknown',
  moduleRegistryHash: typeof __PCE_MODULE_REGISTRY_HASH__ !== 'undefined' ? __PCE_MODULE_REGISTRY_HASH__ : 'unknown',
  pageComponentHash: typeof __PCE_PAGE_COMPONENT_HASH__ !== 'undefined' ? __PCE_PAGE_COMPONENT_HASH__ : 'unknown',
})

if (typeof window !== 'undefined') window.__PCE_FRONTEND_RUNTIME_IDENTITY__ = frontendRuntimeIdentity

export function assertServedFrontendIdentity(expected = {}) {
  const mismatches = Object.entries(expected)
    .filter(([key, value]) => value !== undefined && frontendRuntimeIdentity[key] !== value)
    .map(([key, value]) => `${key}: served=${frontendRuntimeIdentity[key]} expected=${value}`)
  if (mismatches.length) throw new Error(`TESTED FRONTEND != SERVED FRONTEND: ${mismatches.join('; ')}`)
  return frontendRuntimeIdentity
}
