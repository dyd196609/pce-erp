import { applyI18n } from './i18nEngine.js'
import { translate } from './i18nEngine.js'

function buildLayout(schema) {
  return {
    pageType: schema.pageType || 'list',
    title: schema.title,
    sections: ['filters', 'table', 'actions'],
  }
}

function buildComponents(schema, runtimeResult = {}) {
  const workflow = runtimeResult.workflow
  const evolution = runtimeResult.evolution

  return {
    table: {
      columns: evolution?.ui?.ui?.list?.columns || schema?.ui?.list?.columns || [],
      emptyText: schema.labels?.noData,
      loadingText: schema.labels?.loading,
      actionsColumn: schema.labels?.actionsColumn,
    },
    filters: {
      columns: (schema?.ui?.list?.columns || []).filter((column) => column.filter),
    },
    workflow: {
      title: translate('Current Workflow State'),
      actionsTitle: translate('Available Workflow Actions'),
      badge: workflow
        ? {
            state: workflow.currentState,
            label: translate(workflow.currentState),
          }
        : null,
      graph: workflow?.uiGraph || null,
      availableTransitions: workflow?.availableTransitions || [],
      blockedTransitions: workflow?.blockedTransitions || [],
    },
    cockpit: {
      layout: evolution?.ui?.cockpitLayout || ['profit-kpi', 'system-health', 'review-control', 'workflow-status'],
      industry: runtimeResult.industry || schema.industry || null,
      kpis: schema.kpis || [],
    },
  }
}

function buildActions(schema, runtimeResult = {}) {
  const workflow = runtimeResult.workflow
  const actions = schema?.ui?.list?.actions || []

  if (!workflow) return actions

  const filtered = actions.filter((action) => {
    if (action.type !== 'workflow' && !action.workflowAction) return true
    return workflow.availableActions.includes(action.workflowAction || action.key)
  })

  const order = runtimeResult.evolution?.ui?.reorderedActions || []
  if (order.length === 0) return filtered

  return [...filtered].sort((a, b) => {
    const aIndex = order.indexOf(a.key || a.action || a.event || a.workflowAction)
    const bIndex = order.indexOf(b.key || b.action || b.event || b.workflowAction)
    return (aIndex === -1 ? Number.MAX_SAFE_INTEGER : aIndex) - (bIndex === -1 ? Number.MAX_SAFE_INTEGER : bIndex)
  })
}

export function generateUI(schema = {}, runtimeResult = {}, locale = 'zh-CN') {
  const translatedSchema = applyI18n(schema, locale)
  const actions = buildActions(translatedSchema, runtimeResult)

  return {
    layout: buildLayout(translatedSchema),
    components: buildComponents(translatedSchema, runtimeResult),
    actions,
    labels: translatedSchema.labels,
    liveSync: runtimeResult.liveSync === true,
    schemaVersion: runtimeResult.evolution?.schema?.toVersion || runtimeResult.workflowRuntime?.version || 0,
    evolutionMode: runtimeResult.evolutionMode,
    industryMode: runtimeResult.industryMode,
    autoIndustryAdaptation: runtimeResult.autoIndustryAdaptation === true,
    digitalTwinMode: runtimeResult.digitalTwinMode,
    simulationEnabled: runtimeResult.simulationEnabled === true,
    predictionLayer: runtimeResult.predictionLayer,
    digitalTwin: runtimeResult.digitalTwin,
    decisionMode: runtimeResult.decisionMode,
    decisionLayer: runtimeResult.decisionLayer,
    autoApprovalEnabled: runtimeResult.autoApprovalEnabled === true,
    decision: runtimeResult.decision,
    executionMode: runtimeResult.executionMode,
    autoExecutionEnabled: runtimeResult.autoExecutionEnabled,
    executionLayer: runtimeResult.executionLayer,
    executionStatus: runtimeResult.executionStatus,
    autonomousMode: runtimeResult.autonomousMode,
    selfDriving: runtimeResult.selfDriving,
    systemAutonomyLevel: runtimeResult.systemAutonomyLevel,
    autonomousStatus: runtimeResult.autonomousStatus,
    networkMode: runtimeResult.networkMode,
    multiEnterpriseMode: runtimeResult.multiEnterpriseMode,
    globalOptimization: runtimeResult.globalOptimization,
    network: runtimeResult.network,
    globalMode: runtimeResult.globalMode,
    macroEconomySimulation: runtimeResult.macroEconomySimulation,
    crossCountryERP: runtimeResult.crossCountryERP,
    globalEconomy: runtimeResult.globalEconomy,
    civilizationMode: runtimeResult.civilizationMode,
    societySimulation: runtimeResult.societySimulation,
    governanceAI: runtimeResult.governanceAI,
    civilization: runtimeResult.civilization,
    humanMode: runtimeResult.humanMode,
    cognitiveSimulation: runtimeResult.cognitiveSimulation,
    emotionModel: runtimeResult.emotionModel,
    human: runtimeResult.human,
    hybridMode: runtimeResult.hybridMode,
    sharedCognition: runtimeResult.sharedCognition,
    trustEngine: runtimeResult.trustEngine,
    hybrid: runtimeResult.hybrid,
    finalMode: runtimeResult.finalMode,
    unifiedSystem: runtimeResult.unifiedSystem,
    realityControl: runtimeResult.realityControl,
    final: runtimeResult.final,
    convergenceMode: runtimeResult.convergenceMode,
    systemStabilityLayer: runtimeResult.systemStabilityLayer,
    convergence: runtimeResult.convergence,
    freezeMode: runtimeResult.freezeMode,
    productionLock: runtimeResult.productionLock,
    systemMutability: runtimeResult.systemMutability,
    freeze: runtimeResult.freeze,
    productionMode: runtimeResult.productionMode,
    onboardingEnabled: runtimeResult.onboardingEnabled,
    opsControl: runtimeResult.opsControl,
    apiStrictMode: runtimeResult.apiStrictMode,
    moduleStandardization: runtimeResult.moduleStandardization,
    product: runtimeResult.product,
    saasMode: runtimeResult.saasMode,
    tenantIsolation: runtimeResult.tenantIsolation,
    billingEngine: runtimeResult.billingEngine,
    quotaManager: runtimeResult.quotaManager,
    saas: runtimeResult.saas,
    growthMode: runtimeResult.growthMode,
    acquisitionTracking: runtimeResult.acquisitionTracking,
    retentionTracking: runtimeResult.retentionTracking,
    revenueTracking: runtimeResult.revenueTracking,
    referralTracking: runtimeResult.referralTracking,
    growth: runtimeResult.growth,
    selfBindingMode: runtimeResult.selfBindingMode,
    platformAutonomy: runtimeResult.platformAutonomy,
    selfBinding: runtimeResult.selfBinding,
    feedbackLoop: runtimeResult.feedbackLoop,
    schemaVersioning: runtimeResult.schemaVersioning,
    evolution: runtimeResult.evolution,
    designerMode: runtimeResult.mode === 'DESIGN',
    schema: {
      ...translatedSchema,
      ui: {
        ...(translatedSchema.ui || {}),
        list: {
          ...(translatedSchema?.ui?.list || {}),
          actions,
        },
      },
    },
    runtime: runtimeResult,
  }
}
