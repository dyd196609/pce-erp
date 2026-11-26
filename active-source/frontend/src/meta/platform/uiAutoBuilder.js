import { generateUI } from '../runtime/uiGeneratorEngine.js'
import { UIControlRuntimeKernel } from '../runtime/uiControlRuntimeKernel.js'

export function buildMenuItem(module) {
  return {
    key: module.key,
    label: module.label || module.name || module.key,
    path: module.route,
    icon: module.icon || 'DataBoard',
    generated: module.generated === true,
    domain: module.domain || module.key,
  }
}

export function buildRouteItem(module) {
  return {
    key: module.key,
    path: module.route,
    schema: module.schema,
    module,
  }
}

export function buildPage(module) {
  const schema = module.schema || {}
  const runtime = UIControlRuntimeKernel(schema, {
    workflow_state: schema.workflow?.states?.[0] || 'DRAFT',
  })

  return {
    key: module.key,
    route: module.route,
    schema,
    ui: generateUI(schema, runtime),
    actions: runtime.ui?.actions || schema?.ui?.list?.actions || [],
    workflow: runtime.workflow,
  }
}

export function buildUIFromSchema(schema) {
  const runtime = UIControlRuntimeKernel(schema, {
    workflow_state: schema.workflow?.states?.[0] || 'DRAFT',
  })

  return generateUI(schema, runtime)
}
