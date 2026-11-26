import { enterpriseMasterDataApi } from '@/api/enterpriseMasterData'
import { stateManager } from '@/meta/runtime/stateManager'
import {
  MATERIAL_RUNTIME_STATUS,
  createMaterialMasterRuntimeEngine,
} from './materialMasterRuntimeEngine.js'
import { getTabAuthToken } from '@/meta/runtime/tabAuthenticationContext.js'

const engine = createMaterialMasterRuntimeEngine({
  fetchFacts: () => enterpriseMasterDataApi.facts('materials'),
})

function currentContext(detail = {}) {
  const session = stateManager.getSession()
  const tenant = stateManager.getTenant()
  const token = getTabAuthToken()
  const backendAuthenticated = detail.authenticated !== undefined
    ? detail.authenticated
    : Boolean(session.backendAuthenticated || token)
  return {
    authenticated: Boolean(backendAuthenticated),
    mode: session.demoMode && !backendAuthenticated ? 'demo' : 'enterprise',
    tenantId: tenant.id || '',
    principalId: detail.principalId || session.backendUserId || token.slice(-24),
  }
}

export async function loadMaterialMasterRuntime({ force = false } = {}) {
  return engine.load({ force, context: currentContext() })
}

export function getMaterialMasterRuntimeModels() {
  return engine.models()
}

export function getMaterialMasterRuntimeState() {
  return engine.state()
}

export function initializeMaterialMasterRuntimeLifecycle({ onError } = {}) {
  const handleChange = (event) => {
    const context = currentContext(event?.detail || {})
    engine.load({ force: true, context }).catch((error) => onError?.(error))
  }
  if (typeof window !== 'undefined') {
    window.addEventListener('pce:authentication-changed', handleChange)
  }
  return {
    preload: () => engine.load({ context: currentContext() }),
    dispose: () => window?.removeEventListener('pce:authentication-changed', handleChange),
  }
}

export function getMaterialMasterRuntimeOptions() {
  return getMaterialMasterRuntimeModels().map((model) => ({
    id: model.id,
    code: model.materialCode,
    name: model.materialName,
    type: '物料',
    status: model.status,
    sourceModule: 'MaterialMasterRuntime',
    raw: model,
  }))
}

export function findMaterialMasterRuntimeByCode(code) {
  const value = String(code || '')
  return getMaterialMasterRuntimeModels().find((model) => String(model.materialCode) === value) || null
}

export function hasMaterialMasterRuntimeId(id) {
  return getMaterialMasterRuntimeModels().some((model) => String(model.id) === String(id))
}

export { MATERIAL_RUNTIME_STATUS }
