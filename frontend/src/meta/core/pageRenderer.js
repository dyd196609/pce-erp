import { computed, h, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElButton, ElDatePicker, ElInput, ElOption, ElPagination, ElSelect, ElTable, ElTableColumn } from 'element-plus'
import { dataGateway } from '@/meta/runtime/dataGateway'
import { trace } from '@/meta/core/runtimeTracer'
import { PAGE_STATE } from '@/meta/specs/pageExecutionContract.v1'
import { translate } from '@/meta/runtime/i18nEngine'
import { UIControlRuntimeKernel } from '@/meta/runtime/uiControlRuntimeKernel'
import BPMDesigner from '@/meta/bpm/BPMDesigner.vue'
import { registerGeneratedERP, registerGeneratedIndustryERP } from '@/meta/generator/erpGeneratorEngine'
import { evaluateDecision } from '@/meta/ai/decisionEngine'
import { executeDecision, getExecutionHistory, getExecutionStatus } from '@/meta/ai/executionEngine'
import { getAutonomousHistory, getAutonomousStatus, runAutonomousCycle, stopAutonomousLoop } from '@/meta/ai/selfDrivingEngine'
import { simulateEnterpriseState } from '@/meta/digitalTwin/enterpriseDigitalTwinEngine'
import { createDefaultEnterpriseNetwork } from '@/meta/network/enterpriseGraphEngine'
import { optimizeEnterpriseNetwork } from '@/meta/network/globalOptimizationEngine'
import { simulateGlobalEconomy } from '@/meta/global/globalEconomicBrain'
import { simulateCivilization } from '@/meta/civilization/civilizationSimulationEngine'
import { simulateHumanBehavior } from '@/meta/human/humanBehaviorOS'
import { hybridDecision } from '@/meta/hybrid/hybridDecisionEngine'
import { runCivilizationCore } from '@/meta/final/unifiedCivilizationCore'
import { convergeSystem } from '@/meta/convergence/systemConvergenceEngine'
import { lockSystem } from '@/meta/freeze/systemLockManager'
import { standardizeModule } from '@/meta/product/moduleStandardizer'
import { runSaasRuntime } from '@/meta/saas/saasRuntime'
import { onboardTenant } from '@/meta/saas/onboarding/userOnboardingEngine'
import { getProductionHealth } from '@/meta/saas/monitoring/productionMonitor'
import { getOpsState } from '@/meta/saas/ops/opsControlCenter'
import { runGrowthRuntime } from '@/meta/growth/growthRuntime'
import { trackSubscriptionUpgrade } from '@/meta/growth/revenueEngine'
import { trackReferral } from '@/meta/growth/referralEngine'
import { buildModuleHub } from '@/meta/platform/moduleHub'
import { stateManager } from '@/meta/runtime/stateManager'
import { initRuntimeSystem } from '@/meta/runtime/runtimeBootstrap'
import { createUIState, getUIState } from '@/meta/ui/uiStateManager'
import { getOrchestrationSnapshot } from '@/meta/orchestration/autoWorkflowConnector'
import { getIntelligenceSnapshot } from '@/meta/intelligence/decisionEngine'
import { getExecutionLayerSnapshot } from '@/meta/execution/executionEngine'
import { getEnterpriseAutopilotSnapshot } from '@/meta/autonomy/businessOrchestrator'
import { getStructuralEvolutionSnapshot } from '@/meta/evolution/structuralEvolutionEngine'
import { getStabilityBoundarySnapshot } from '@/meta/stability/evolutionBoundaryController'
import { getProductionFinalizationSnapshot } from '@/meta/production/systemFreezeManager'
import { getTenantOnboardingSnapshot } from '@/meta/saas/onboarding/tenantOnboardingEngine'
import { getCommercialBillingSnapshot } from '@/meta/saas/billing/billingEngine'
import { getMonitoringCenterSnapshot } from '@/meta/saas/monitoring/productionMonitor'
import { getDeploymentPipelineSnapshot } from '@/meta/deployment/deploymentPipeline'
import { getPlatformRuntimeSnapshot } from '@/meta/platform/multiProductRuntimeEngine'
import { getApiConnectorSnapshot } from '@/meta/data/apiConnector'
import { getDatabaseLayerSnapshot } from '@/meta/data/databaseLayer'
import { getDataSyncSnapshot } from '@/meta/data/syncEngine'
import { getBusinessRuntimeSnapshot } from '@/meta/runtime/businessRuntimeEngine'
import { getTransactionRuntimeSnapshot } from '@/meta/runtime/transactionEngine'
import { getEnterpriseEventStreamSnapshot } from '@/meta/runtime/enterpriseEventStream'
import { getFinancialPostingSnapshot } from '@/meta/runtime/financialPostingEngine'
import {
  recordBlocking,
  recordClick,
  recordModuleAccess,
  recordRuntimeError,
  recordWorkflowCompletion,
} from '@/meta/ai/runtimeFeedbackCollector'

function getColumnKey(column) {
  return column?.key || column?.prop || column?.field
}

function getFilterType(column) {
  if (!column?.filter) return null
  if (column.filterType) return column.filterType
  if (typeof column.filter === 'string') return column.filter
  return 'text'
}

function getActionKey(action) {
  return action?.key || action?.action || action?.name || action?.event
}

function getButtonType(action) {
  const key = getActionKey(action)

  if (action?.buttonType) return action.buttonType
  if (key === 'edit') return 'warning'
  if (key === 'delete') return 'danger'

  return 'primary'
}

function getRowValue(row, prop) {
  return safeDisplay(row?.[prop])
}

function safeDisplay(value) {
  if (value === undefined || value === null || value === '') return '-'
  return String(value)
}

function normalizeText(value) {
  return String(value ?? '').trim().toLowerCase()
}

function getFilterableColumns(schema) {
  return getListColumns(schema).filter((column) => {
    return column.type !== 'index' && getFilterType(column) && getColumnKey(column)
  })
}

function getModuleName(schema = {}) {
  return schema?.api?.module || schema?.name || schema?.key || 'module'
}

function getSchemaTitle(schema = {}) {
  return translate(schema?.meta?.title || schema?.labels?.title || schema?.label || schema?.name || 'Module')
}

function getListColumns(schema = {}) {
  const schemaColumns = schema?.ui?.list?.columns || schema?.columns || schema?.fields || []
  const normalized = Array.isArray(schemaColumns)
    ? schemaColumns
        .map((column) => (typeof column === 'string' ? { key: column, label: translate(column) } : column))
        .filter(Boolean)
    : []
  const hasIndex = normalized.some((column) => column?.type === 'index')
  const businessColumns = normalized.filter((column) => column?.type !== 'actions')

  if (businessColumns.length === 0) {
    return [
      { key: 'index', label: translate('Index'), type: 'index', width: 70 },
      { key: 'id', label: 'ID', minWidth: 100 },
      { key: 'name', label: translate('Name'), minWidth: 160 },
      { key: 'status', label: translate('Status'), filter: true, filterType: 'select', minWidth: 120 },
    ]
  }

  return hasIndex
    ? businessColumns
    : [{ key: 'index', label: translate('Index'), type: 'index', width: 70 }, ...businessColumns]
}

function getFieldColumns(schema = {}) {
  const fields = schema?.fields || schema?.ui?.form?.fields || schema?.ui?.list?.columns || schema?.columns || []
  const normalized = Array.isArray(fields)
    ? fields
        .map((field) => (typeof field === 'string' ? { key: field, label: translate(field) } : field))
        .filter((field) => field && field.type !== 'index' && field.type !== 'actions' && getColumnKey(field))
    : []

  return normalized.length > 0
    ? normalized
    : getListColumns(schema).filter((column) => column.type !== 'index' && getColumnKey(column))
}

function getDefaultActions(schema = {}) {
  const base = getModuleBasePath(schema)
  return [
    { key: 'detail', label: translate('Detail'), type: 'route', to: `${base}/:id` },
    { key: 'edit', label: translate('Edit'), type: 'route', to: `${base}/:id/edit`, buttonType: 'warning' },
  ]
}

function getListActions(schema = {}, runtime = null) {
  const actions = runtime?.ui?.actions || runtime?.uiControl?.actions || schema?.ui?.list?.actions || []
  const normalized = Array.isArray(actions) ? actions.filter(Boolean) : []
  const keys = new Set(normalized.map(getActionKey))
  const defaults = getDefaultActions(schema).filter((action) => !keys.has(action.key))

  return [...normalized, ...defaults]
}

function getModuleBasePath(schema = {}) {
  const route = schema?.route || schema?.meta?.route
  if (route) return String(route).replace(/\/:id(?:\/edit)?$/, '')

  const moduleName = getModuleName(schema)
  if (moduleName === 'purchaseOrder') return '/purchase/order'
  return `/${moduleName}`
}

function getSelectOptions(rows, prop) {
  const values = rows.map((row) => row?.[prop]).filter((value) => value !== undefined && value !== null && value !== '')

  return [...new Set(values)].map((value) => ({
    label: String(value),
    value,
  }))
}

function rowMatchesFilter(row, column, value) {
  if (value === undefined || value === null || value === '') return true

  const prop = getColumnKey(column)
  const filterType = getFilterType(column)
  const rowValue = row?.[prop]

  if (filterType === 'select') {
    return rowValue === value
  }

  if (filterType === 'date') {
    return String(rowValue ?? '').startsWith(String(value))
  }

  return normalizeText(rowValue).includes(normalizeText(value))
}

function filterRows(rows, schema, filters) {
  const filterableColumns = getFilterableColumns(schema)

  return rows.filter((row) =>
    filterableColumns.every((column) => rowMatchesFilter(row, column, filters[getColumnKey(column)]))
  )
}

function resolveRoutePath(template, row) {
  if (!template) return ''

  return template.replace(':id', encodeURIComponent(row?.id ?? ''))
}

function runAction(action, row, handlers) {
  const key = getActionKey(action)

  if (action?.type === 'route') {
    handlers.goRoute(resolveRoutePath(action.to, row))
    return
  }

  if (action?.type === 'event') {
    handlers.handleEvent(action.event || key, row)
    return
  }

  if (action?.type === 'workflow') {
    handlers.handleWorkflowAction(action, row)
    return
  }

  if (key === 'detail' || key === 'view') {
    handlers.goRoute(`${handlers.basePath || ''}/${encodeURIComponent(row?.id ?? '')}`)
    return
  }

  if (key === 'edit') {
    handlers.goRoute(`${handlers.basePath || ''}/${encodeURIComponent(row?.id ?? '')}/edit`)
    return
  }

  handlers.handleEvent(key, row)
}

function renderActions(actions, row, handlers) {
  return actions.map((action) =>
    h(
      ElButton,
      {
        size: 'small',
        type: getButtonType(action),
        'data-action': getActionKey(action),
        'data-row-id': row?.id,
        disabled: false,
        onClick: () => {
          if (handlers.canRunAction && !handlers.canRunAction(action, row)) return
          runAction(action, row, handlers)
        },
      },
      () => translate(action.label || action.key)
    )
  )
}

function renderFilterControl(column, filters, rows) {
  const prop = getColumnKey(column)
  const filterType = getFilterType(column)
  const commonProps = {
    modelValue: filters.value[prop] ?? '',
    clearable: true,
    placeholder: column.label,
    'onUpdate:modelValue': (value) => {
      filters.value = {
        ...filters.value,
        [prop]: value,
      }
    },
  }

  if (filterType === 'select') {
    const options = getSelectOptions(rows.value, prop)

    return h(
      ElSelect,
      {
        ...commonProps,
        filterable: true,
        style: 'width: 160px',
      },
      () =>
        options.map((option) =>
          h(ElOption, {
            key: option.label,
            label: option.label,
            value: option.value,
          })
        )
    )
  }

  if (filterType === 'date') {
    return h(ElDatePicker, {
      ...commonProps,
      type: 'date',
      valueFormat: 'YYYY-MM-DD',
      style: 'width: 160px',
    })
  }

  return h(ElInput, {
    ...commonProps,
    style: 'width: 160px',
  })
}

function renderFilterBar({ schema, filters, rows, keyword, status, onSearch, onReset }) {
  const columns = getFilterableColumns(schema)

  return h('section', {
    class: 'meta-list-filters',
    style: 'display: flex; flex-wrap: wrap; align-items: center; gap: 8px; padding: 12px; margin-bottom: 12px; background: #fff; border: 1px solid #dce5f2; border-radius: 8px',
  }, [
    h(ElInput, {
      modelValue: keyword.value,
      clearable: true,
      placeholder: translate('Keyword'),
      style: 'width: 220px',
      'onUpdate:modelValue': (value) => {
        keyword.value = value
      },
    }),
    h(ElSelect, {
      modelValue: status.value,
      clearable: true,
      placeholder: translate('Status'),
      style: 'width: 160px',
      'onUpdate:modelValue': (value) => {
        status.value = value
      },
    }, () => getSelectOptions(rows.value, 'status').concat(getSelectOptions(rows.value, 'workflow_state')).map((option) =>
      h(ElOption, {
        key: `${option.label}-${option.value}`,
        label: translate(option.label),
        value: option.value,
      })
    )),
    ...columns.map((column) => renderFilterControl(column, filters, rows)),
    h(ElButton, { onClick: onReset }, () => translate('Reset')),
    h(ElButton, { type: 'primary', onClick: onSearch }, () => translate('Search')),
  ])
}

function renderColumns(schema, handlers, runtime) {
  const rawColumns = getListColumns({
    ...schema,
    ui: {
      ...(schema?.ui || {}),
      list: {
        ...(schema?.ui?.list || {}),
        columns: runtime?.ui?.components?.table?.columns || runtime?.uiControl?.columns || getListColumns(schema),
      },
    },
  })
  const actions = getListActions(schema, runtime)

  const columns = rawColumns.map((column) => {
    const prop = getColumnKey(column)

    if (column.type === 'index') {
      return h(ElTableColumn, {
        type: 'index',
        label: column.label,
        width: column.width || 70,
      })
    }

    return h(ElTableColumn, {
      label: translate(column.label || prop),
      prop,
      sortable: column.sortable === true,
      minWidth: column.minWidth || column.width || 120,
      formatter: (row) => getRowValue(row, prop),
    })
  })

  columns.push(
    h(
      ElTableColumn,
      {
        label: translate(runtime?.ui?.components?.table?.actionsColumn || 'Actions'),
        width: 170,
        fixed: 'right',
      },
      {
        default: ({ row }) =>
          h(
            'div',
            {
              style: 'display: flex; gap: 8px',
            },
            renderActions(actions, row, handlers)
          ),
      }
    )
  )

  return columns
}

function renderBlockedView(runtime) {
  const labels = runtime?.ui?.labels || {}

  return h(
    'div',
    {
      class: 'meta-list-blocked',
      style: 'padding: 24px; background: #fff; border: 1px solid #fca5a5; border-radius: 8px; color: #991b1b',
    },
    [
      h('h3', { style: 'margin: 0 0 8px' }, labels.blockedTitle),
      h('p', { style: 'margin: 0 0 8px' }, runtime?.reason || labels.blockedMessage),
      h('p', { style: 'margin: 0' }, `${translate('Control Mode')}: ${translate(runtime?.controlMode || PAGE_STATE.BLOCKED)}`),
    ]
  )
}

function renderSimulationPanel(simulation) {
  if (!simulation) return null

  const trend = simulation.kpiForecast?.trendCurve || []
  const risk = simulation.riskProfile || {}
  const decision = simulation.decisionOutcome || {}
  const workflow = simulation.workflowSimulation || {}

  return h(
    'div',
    {
      class: 'meta-simulation-panel',
      style: 'display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; padding: 12px 14px; background: #fff; border: 1px solid #dce5f2; border-radius: 8px; margin-bottom: 12px',
    },
    [
      h('div', [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 4px' }, 'Predicted Outcome'),
        h('strong', decision.predictedOutcome || 'READY'),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, `Impact: ${Math.round((decision.impactScore || 0) * 100)}%`),
      ]),
      h('div', [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 4px' }, 'Risk Level'),
        h('strong', risk.riskLevel || 'LOW'),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, `Supply: ${risk.supplyChainRisk || 'LOW'}`),
      ]),
      h('div', [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 4px' }, 'Workflow Simulation'),
        h('strong', workflow.workflowBottleneck || 'none'),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, `Failure: ${Math.round((workflow.transitionFailureRisk || 0) * 100)}%`),
      ]),
      h('div', [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 4px' }, '7-day KPI Forecast'),
        h('strong', trend.map((point) => point.executionScore).join(' 閳?')),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, `Anomalies: ${simulation.kpiForecast?.anomalies?.length || 0}`),
      ]),
    ]
  )
}

function renderDecisionPanel(decision) {
  if (!decision) return null

  const riskType = decision.risk?.level === 'HIGH'
    ? '#b91c1c'
    : decision.risk?.level === 'MEDIUM'
      ? '#b45309'
      : '#166534'

  return h(
    'div',
    {
      class: 'meta-decision-panel',
      style: 'display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; padding: 12px 14px; background: #fff; border: 1px solid #dce5f2; border-radius: 8px; margin-bottom: 12px',
    },
    [
      h('div', [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 4px' }, 'Decision Score'),
        h('strong', { style: 'font-size: 22px' }, String(decision.score)),
      ]),
      h('div', [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 4px' }, 'Suggested Action'),
        h('strong', { style: 'font-size: 18px' }, decision.recommendation),
      ]),
      h('div', [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 4px' }, 'Risk Badge'),
        h('strong', { style: `font-size: 18px; color: ${riskType}` }, decision.risk?.level || 'LOW'),
      ]),
      h('div', [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 4px' }, 'Auto Approval'),
        h('strong', { style: 'font-size: 18px' }, decision.autoApproval?.executed ? 'AUTO_APPROVED' : 'GATED'),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, decision.policy?.reason || ''),
      ]),
    ]
  )
}

function renderExecutionPanel(status, history = []) {
  if (!status) return null

  return h(
    'div',
    {
      class: 'meta-execution-panel',
      style: 'display: grid; grid-template-columns: 1fr 2fr; gap: 12px; padding: 12px 14px; background: #fff; border: 1px solid #dce5f2; border-radius: 8px; margin-bottom: 12px',
    },
    [
      h('div', [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 4px' }, 'Execution Status'),
        h('strong', { style: 'font-size: 18px' }, status.status || 'IDLE'),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, status.last?.reason || status.last?.mode || 'READY'),
      ]),
      h('div', [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 4px' }, 'Live Action Feed'),
        h(
          'div',
          { style: 'display: flex; flex-wrap: wrap; gap: 6px' },
          history.slice(-4).map((item, index) =>
            h('span', {
              key: `${item.timestamp}-${index}`,
              style: 'padding: 4px 8px; border-radius: 999px; background: #eef2ff; color: #3730a3; font-size: 12px',
            }, `${item.status}${item.actions?.length ? ` 璺?${item.actions.map((action) => action.type).join('/')}` : ''}`)
          )
        ),
      ]),
    ]
  )
}

function renderAutonomousPanel(cycle, status, history = []) {
  if (!cycle && !status) return null

  const optimization = cycle?.optimization

  return h(
    'div',
    {
      class: 'meta-autonomous-panel',
      style: 'display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; padding: 12px 14px; background: #fff; border: 1px solid #dce5f2; border-radius: 8px; margin-bottom: 12px',
    },
    [
      h('div', [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 4px' }, 'Self-Driving Status'),
        h('strong', status?.mode || 'IDLE'),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, `Autonomy Level ${status?.autonomyLevel || 4}`),
      ]),
      h('div', [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 4px' }, 'Auto Workflow'),
        h('strong', cycle?.state?.workflow?.currentState || 'READY'),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, cycle?.state?.workflow?.bottleneck || 'none'),
      ]),
      h('div', [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 4px' }, 'System Evolution'),
        h('strong', optimization?.controlPolicy?.autonomousAdjustment || 'MONITOR'),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, `Score +${optimization?.systemScoreDelta || 0}`),
      ]),
      h('div', [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 4px' }, 'Autonomous Feed'),
        h('strong', `${history.length} cycles`),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, history.slice(-2).map((item) => item.execution?.status).join(' 閳?') || 'READY'),
      ]),
    ]
  )
}

function renderNetworkPanel(network) {
  if (!network) return null

  return h(
    'div',
    {
      class: 'meta-network-panel',
      style: 'display: grid; grid-template-columns: 1.2fr 1fr 1fr; gap: 12px; padding: 12px 14px; background: #fff; border: 1px solid #dce5f2; border-radius: 8px; margin-bottom: 12px',
    },
    [
      h('div', [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 4px' }, 'Enterprise Network Graph'),
        h('strong', `${network.graph.nodes.length} nodes / ${network.graph.edges.length} edges`),
        h('div', { style: 'display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px' }, network.graph.nodes.map((node) =>
          h('span', {
            key: node.id,
            style: 'padding: 4px 8px; border-radius: 999px; background: #eff6ff; color: #1d4ed8; font-size: 12px',
          }, `${node.name} 璺?${node.role}`)
        )),
      ]),
      h('div', [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 4px' }, 'Supply Chain Heatmap'),
        h('strong', `${network.resourceExchange.inventoryTransfer} units`),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, `Cash: ${network.resourceExchange.cashFlow}`),
      ]),
      h('div', [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 4px' }, 'Global Optimization'),
        h('strong', `${network.globalOptimization.networkEfficiency}/100`),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, `Balance: ${Math.round(network.globalOptimization.supplyDemandBalance)}`),
      ]),
    ]
  )
}

function renderGlobalEconomyPanel(globalEconomy) {
  if (!globalEconomy) return null

  const market = globalEconomy.market || {}
  const macro = globalEconomy.macro || {}
  const supplyChain = globalEconomy.supplyChain || {}
  const policy = globalEconomy.policy || {}

  return h(
    'div',
    {
      class: 'meta-global-economy-panel',
      style: 'display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; padding: 12px 14px; background: #fff; border: 1px solid #dce5f2; border-radius: 8px; margin-bottom: 12px',
    },
    [
      h('div', [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 4px' }, 'Global Heatmap'),
        h('strong', `${market.enterprises?.length || 0} markets`),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, `Balance: ${Math.round((market.demandSupplyBalance || 0) * 100)}%`),
      ]),
      h('div', [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 4px' }, 'Economic Trend Chart'),
        h('strong', `GDP ${macro.gdpTrend || 0}%`),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, `Inflation: ${Math.round((macro.inflationPressure || 0) * 100)}%`),
      ]),
      h('div', [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 4px' }, 'Currency Flow Monitor'),
        h('strong', `${market.currencyFlows?.length || 0} FX lanes`),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, market.currencyFlows?.slice(0, 2).map((flow) => `${flow.fromCurrency}->${flow.toCurrency}`).join(' / ') || 'READY'),
      ]),
      h('div', [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 4px' }, 'Supply Chain World Map'),
        h('strong', supplyChain.productionShifting?.targetCountry || 'GLOBAL'),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, policy.pricingPolicies?.[0] || 'Policy ready'),
      ]),
    ]
  )
}

function renderCivilizationPanel(civilization) {
  if (!civilization) return null

  const kpi = civilization.economy?.civilizationKpi || {}
  const governance = civilization.governance || {}
  const population = civilization.population || {}
  const society = civilization.society || {}

  return h(
    'div',
    {
      class: 'meta-civilization-panel',
      style: 'display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; padding: 12px 14px; background: #fff; border: 1px solid #dce5f2; border-radius: 8px; margin-bottom: 12px',
    },
    [
      h('div', [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 4px' }, 'Civilization Dashboard'),
        h('strong', `${kpi.civilizationHealthIndex || 0}/100`),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, `Stability: ${kpi.societyStability || 0}`),
      ]),
      h('div', [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 4px' }, 'Population Flow Map'),
        h('strong', population.laborAvailability || 'STABLE'),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, `Pressure: ${population.migrationPressure || 0}`),
      ]),
      h('div', [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 4px' }, 'Society Structure Graph'),
        h('strong', society.employmentStructure?.dominantSector || 'general'),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, `Cities: ${society.cityDevelopment?.length || 0}`),
      ]),
      h('div', [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 4px' }, 'Governance Impact Panel'),
        h('strong', governance.policySimulation?.recommendedPolicy || 'READY'),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, `Control: ${governance.stabilityControl || 0}`),
      ]),
    ]
  )
}

function renderHumanBehaviorPanel(human) {
  if (!human) return null

  return h(
    'div',
    {
      class: 'meta-human-panel',
      style: 'display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; padding: 12px 14px; background: #fff; border: 1px solid #dce5f2; border-radius: 8px; margin-bottom: 12px',
    },
    [
      h('div', [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 4px' }, 'Human Behavior Dashboard'),
        h('strong', `${human.cognition.decisionIndex}/100`),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, human.cognition.predictedDecision),
      ]),
      h('div', [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 4px' }, 'Cognitive Decision Panel'),
        h('strong', `${human.cognition.approveLikelihood}% approve`),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, `Delay: ${human.cognition.delayLikelihood}%`),
      ]),
      h('div', [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 4px' }, 'Emotion Flow Map'),
        h('strong', human.emotion.emotionalLoad),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, `Stress ${human.emotion.stressLevel} / Fatigue ${human.emotion.fatigue}`),
      ]),
      h('div', [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 4px' }, 'Incentive Heatmap'),
        h('strong', human.incentive.behaviorShift),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, `Team KPI ${human.group.kpiImpact}`),
      ]),
    ]
  )
}

function renderHybridDecisionPanel(hybrid) {
  if (!hybrid) return null

  return h(
    'div',
    {
      class: 'meta-hybrid-panel',
      style: 'display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; padding: 12px 14px; background: #fff; border: 1px solid #dce5f2; border-radius: 8px; margin-bottom: 12px',
    },
    [
      h('div', [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 4px' }, 'Human-AI Collaboration Panel'),
        h('strong', hybrid.fused.decision),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, `Confidence ${hybrid.fused.confidence}`),
      ]),
      h('div', [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 4px' }, 'Decision Conflict Resolver'),
        h('strong', hybrid.conflict.detected ? 'CONFLICT' : 'AGREED'),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, hybrid.conflict.resolver),
      ]),
      h('div', [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 4px' }, 'Trust Score Dashboard'),
        h('strong', `H ${hybrid.trust.humanReliability} / AI ${hybrid.trust.aiReliability}`),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, `Weights ${hybrid.trust.humanWeight}/${hybrid.trust.aiWeight}`),
      ]),
      h('div', [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 4px' }, 'Shared Execution Timeline'),
        h('strong', hybrid.execution.sharedWorkflowState),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, hybrid.execution.timeline.map((item) => `${item.actor}:${item.status}`).join(' / ')),
      ]),
    ]
  )
}

function renderFinalCivilizationPanel(final) {
  if (!final) return null

  return h(
    'div',
    {
      class: 'meta-final-panel',
      style: 'display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; padding: 12px 14px; background: #fff; border: 1px solid #dce5f2; border-radius: 8px; margin-bottom: 12px',
    },
    [
      h('div', [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 4px' }, 'FINAL CIVILIZATION DASHBOARD'),
        h('strong', `${final.intelligence.civilizationUnityIndex}/100`),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, final.intelligence.intelligenceLevel),
      ]),
      h('div', [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 4px' }, 'Unified System Graph'),
        h('strong', final.unifiedState?.identity || 'SAFE_RUNTIME'),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, final.unifiedState?.singleState?.decision || 'MONITOR'),
      ]),
      h('div', [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 4px' }, 'Reality Control Panel'),
        h('strong', `${final.reality.stabilityIndicator}/100`),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, final.reality.systemInefficiencyDetected ? 'CORRECTION_ACTIVE' : 'STABLE'),
      ]),
      h('div', [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 4px' }, 'System Self-State View'),
        h('strong', final.policy.autoKpiRecalibration),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, final.policy.autoPermissionAdaptation),
      ]),
    ]
  )
}

function renderConvergencePanel(convergence) {
  if (!convergence) return null

  const state = convergence.unifiedState || {}
  const complexity = state.complexity || {}
  const heatmap = state.conflictHeatmap || {}

  return h(
    'div',
    {
      class: 'meta-convergence-panel',
      style: 'display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; padding: 12px 14px; background: #fff; border: 1px solid #dce5f2; border-radius: 8px; margin-bottom: 12px',
    },
    [
      h('div', [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 4px' }, 'System Convergence Dashboard'),
        h('strong', `${convergence.stabilityScore}/100`),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, state.mode || 'CONFLICT_RESOLVED_RUNTIME'),
      ]),
      h('div', [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 4px' }, 'Stability Index Panel'),
        h('strong', state.unifiedState?.runtimeModel || 'SINGLE_AGENT_STRUCTURE'),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, `Loops ${state.executionControl?.activeLoops || 1}`),
      ]),
      h('div', [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 4px' }, 'Complexity Map'),
        h('strong', complexity.level || 'BOUNDED'),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, `Score ${complexity.score || 0}`),
      ]),
      h('div', [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 4px' }, 'Conflict Heatmap'),
        h('strong', `D${heatmap.decision || 0} E${heatmap.execution || 0} H${heatmap.humanAi || 0}`),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, convergence.convergenceRules?.noNewCoreLayers ? 'NO_NEW_CORE_LAYERS' : 'OPEN'),
      ]),
    ]
  )
}

function renderProductionLockPanel(freeze) {
  if (!freeze) return null

  return h(
    'div',
    {
      class: 'meta-production-lock-panel',
      style: 'display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; padding: 12px 14px; background: #fff; border: 1px solid #dce5f2; border-radius: 8px; margin-bottom: 12px',
    },
    [
      h('div', [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 4px' }, 'Production Lock Dashboard'),
        h('strong', freeze.cockpitStatus),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, `${freeze.status} / ${freeze.mode}`),
      ]),
      h('div', [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 4px' }, 'System Stability Monitor'),
        h('strong', freeze.productionReady ? 'READY' : 'REVIEW'),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, `Mutability ${freeze.systemMutability}`),
      ]),
      h('div', [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 4px' }, 'Deterministic Runtime Panel'),
        h('strong', freeze.deterministicRuntime.runtimeSignature),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, freeze.deterministicRuntime.sameInputSameOutput ? 'same input = same output' : 'unstable'),
      ]),
      h('div', [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 4px' }, 'Complexity Ceiling Meter'),
        h('strong', `${freeze.complexityCap.score}/100`),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, `Loop ${freeze.executionLock.activeLoops}/${freeze.executionLock.maxRecursionLoop}`),
      ]),
    ]
  )
}

function renderProductizationPanel(product) {
  if (!product) return null

  return h(
    'div',
    {
      class: 'meta-product-panel',
      style: 'display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; padding: 12px 14px; background: #fff; border: 1px solid #dce5f2; border-radius: 8px; margin-bottom: 12px',
    },
    [
      h('div', [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 4px' }, 'Production SaaS Dashboard'),
        h('strong', product.moduleName),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, product.mode),
      ]),
      h('div', [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 4px' }, 'Module Registry Panel'),
        h('strong', product.compliance.productionFrozen ? 'FROZEN' : 'REVIEW'),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, product.deployment.environment),
      ]),
      h('div', [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 4px' }, 'API Contract Viewer'),
        h('strong', product.api.stable ? 'STABLE' : 'INCOMPLETE'),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, product.api.module),
      ]),
      h('div', [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 4px' }, 'SaaS Package'),
        h('strong', product.package.bundleFormat),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, product.permission.unifiedPermissionModel.canExecute ? 'EXECUTE_READY' : 'GATED'),
      ]),
    ]
  )
}

function renderSaasPanel(saas) {
  if (!saas) return null

  return h(
    'div',
    {
      class: 'meta-saas-panel',
      style: 'display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; padding: 12px 14px; background: #fff; border: 1px solid #dce5f2; border-radius: 8px; margin-bottom: 12px',
    },
    [
      h('div', [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 4px' }, 'SaaS Tenant Dashboard'),
        h('strong', saas.isolation.tenantId),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, saas.isolation.dataScope.dataScope),
      ]),
      h('div', [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 4px' }, 'Billing Overview Panel'),
        h('strong', `${saas.billing.plan} / $${saas.billing.total}`),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, `${saas.billing.usage.apiCalls} API`),
      ]),
      h('div', [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 4px' }, 'Module Marketplace UI'),
        h('strong', `${saas.marketplace.enabledModules.length}/${saas.marketplace.availableModules.length}`),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, `Adoption ${Math.round(saas.marketplace.adoption.rate * 100)}%`),
      ]),
      h('div', [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 4px' }, 'Quota Usage Monitor'),
        h('strong', `${saas.quota.remaining.apiCalls} API left`),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, `AI ${saas.quota.remaining.aiDecisions}`),
      ]),
    ]
  )
}

function renderProductionLaunchPanel(data) {
  if (!data) return null

  const monitor = data.monitor || getProductionHealth()
  const ops = data.ops || getOpsState()
  const launch = data.launch
  const saas = data.saas

  return h(
    'div',
    {
      class: 'meta-launch-panel',
      style: 'display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; padding: 12px 14px; background: #fff; border: 1px solid #dce5f2; border-radius: 8px; margin-bottom: 12px',
    },
    [
      h('div', [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 4px' }, 'SaaS Signup Dashboard'),
        h('strong', launch?.tenant?.id || 'READY'),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, launch?.status || 'WAITING'),
      ]),
      h('div', [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 4px' }, 'Billing Live Meter'),
        h('strong', `${saas?.billing?.plan || 'free'} / $${saas?.billing?.total || 0}`),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, `API ${saas?.billing?.usage?.apiCalls || 0} / AI ${saas?.billing?.usage?.aiDecisions || 0}`),
      ]),
      h('div', [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 4px' }, 'Production Monitoring Panel'),
        h('strong', monitor.status),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, `avg ${monitor.latency.average}ms / failures ${Math.round((monitor.failureRate || 0) * 100)}%`),
      ]),
      h('div', [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 4px' }, 'Ops Warning Overlay'),
        h('strong', `circuits ${Object.keys(ops.circuitBreakers || {}).length}`),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, `disabled modules ${Object.keys(ops.disabledModules || {}).length}`),
      ]),
    ]
  )
}

function renderGrowthPanel(growth) {
  if (!growth) return null

  return h(
    'div',
    {
      class: 'meta-growth-panel',
      style: 'display: grid; gap: 12px; padding: 12px 14px; background: #fff; border: 1px solid #dce5f2; border-radius: 8px; margin-bottom: 12px',
    },
    [
      h('div', { style: 'display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 10px' }, [
        h('div', { style: 'padding: 10px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px' }, [
          h('span', { style: 'display: block; color: #64748b; margin-bottom: 4px' }, translate('Growth Dashboard')),
          h('strong', `${growth.metrics?.growthRateIndex ?? 0}`),
          h('p', { style: 'margin: 6px 0 0; color: #64748b' }, `${growth.growthMode}`),
        ]),
        h('div', { style: 'padding: 10px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px' }, [
          h('span', { style: 'display: block; color: #64748b; margin-bottom: 4px' }, translate('Acquisition Funnel View')),
          h('strong', `${growth.acquisition.length} campaigns`),
          h('p', { style: 'margin: 6px 0 0; color: #64748b' }, `${growth.metrics?.funnelConversionRate ?? 0}% conversion`),
        ]),
        h('div', { style: 'padding: 10px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px' }, [
          h('span', { style: 'display: block; color: #64748b; margin-bottom: 4px' }, translate('Activation Flow Panel')),
          h('strong', `${growth.activation.completed}/${growth.activation.total}`),
          h('p', { style: 'margin: 6px 0 0; color: #64748b' }, `${growth.activation.activationScore}% activated`),
        ]),
        h('div', { style: 'padding: 10px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px' }, [
          h('span', { style: 'display: block; color: #64748b; margin-bottom: 4px' }, translate('Retention Heatmap')),
          h('strong', `DAU ${growth.retention.dau} / WAU ${growth.retention.wau}`),
          h('p', { style: 'margin: 6px 0 0; color: #64748b' }, `${growth.retention.churnPrediction} churn`),
        ]),
        h('div', { style: 'padding: 10px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px' }, [
          h('span', { style: 'display: block; color: #64748b; margin-bottom: 4px' }, translate('Revenue Expansion Tracker')),
          h('strong', `$${growth.revenue.expansionRevenue}`),
          h('p', { style: 'margin: 6px 0 0; color: #64748b' }, growth.revenueExpansionSnapshot?.recommendation?.recommendedPlan || '-'),
        ]),
        h('div', { style: 'padding: 10px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px' }, [
          h('span', { style: 'display: block; color: #64748b; margin-bottom: 4px' }, translate('Viral Growth Network Graph')),
          h('strong', `${growth.referral.nodes.length} nodes`),
          h('p', { style: 'margin: 6px 0 0; color: #64748b' }, `${growth.metrics?.viralCoefficient ?? 0} coefficient`),
        ]),
      ]),
    ]
  )
}

function renderModuleHubPanel(hub) {
  if (!hub) return null

  return h(
    'div',
    {
      class: 'meta-module-hub-panel',
      style: 'display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; padding: 12px 14px; background: #fff; border: 1px solid #dce5f2; border-radius: 8px; margin-bottom: 12px',
    },
    [
      h('div', [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 4px' }, 'Module Hub'),
        h('strong', `${hub.modules.length} modules`),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, hub.modules.map((item) => item.key).join(', ')),
      ]),
      h('div', [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 4px' }, 'Generated Menu'),
        h('strong', `${hub.menu.length} items`),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, hub.menu.map((item) => item.path).join(' / ')),
      ]),
      h('div', [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 4px' }, 'Generated Routes'),
        h('strong', `${hub.routes.length} routes`),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, hub.routes.map((item) => item.path).join(' / ')),
      ]),
      h('div', [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 4px' }, 'Generated Pages'),
        h('strong', `${hub.pages.length} pages`),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, 'schema -> UI -> workflow -> actions'),
      ]),
    ]
  )
}

function renderWorkflowPanel(runtime, handlers, record = {}) {
  const workflow = runtime?.workflow

  if (!workflow) return null
  const graph = runtime?.ui?.components?.workflow?.graph
  const firstAction = workflow.availableActions[0]
  const graphNodes = graph?.nodes || []
  const transitions = workflow.availableTransitions || []
  const blockedTransitions = workflow.blockedTransitions || []

  return h('div', {
    class: 'meta-workflow-panel',
    style: 'display: grid; gap: 12px; padding: 12px 14px; background: #fff; border: 1px solid #dce5f2; border-radius: 8px; margin-bottom: 12px',
  }, [
    h('div', { style: 'display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap' }, [
      h('div', [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 4px' }, translate('Workflow Status Panel')),
        h('strong', { style: 'font-size: 18px; margin-right: 12px' }, translate(workflow.currentState)),
      ]),
      h('div', { style: 'display: flex; align-items: center; gap: 8px; flex-wrap: wrap' }, [
        h('span', { style: 'color: #64748b' }, translate('Available Workflow Actions')),
        ...workflow.availableActions.map((action) =>
          h(ElButton, {
            size: 'small',
            type: 'primary',
            disabled: runtime.controlMode === PAGE_STATE.BLOCKED,
            onClick: () => handlers.handleWorkflowAction({
              key: action,
              label: translate(action),
              type: 'workflow',
              workflowAction: action,
            }, record),
          }, () => translate(action))
        ),
      ]),
    ]),
    h('section', [
      h('span', { style: 'display: block; color: #64748b; margin-bottom: 6px' }, translate('Business Process Tracker')),
      h('div', {
        class: 'meta-workflow-graph',
        style: 'display: flex; align-items: center; gap: 6px; flex-wrap: wrap',
      }, graphNodes.flatMap((node, index) => {
        const nodeStyle = [
          'padding: 4px 9px',
          'border-radius: 999px',
          'border: 1px solid #cbd5e1',
          node.current ? 'background: #1d4ed8; color: #fff; border-color: #1d4ed8' : '',
          node.next ? 'background: #e0f2fe; color: #075985; border-color: #38bdf8; cursor: pointer' : '',
        ].filter(Boolean).join('; ')
        const nodeElement = h('button', {
          type: 'button',
          style: nodeStyle,
          disabled: !node.next || runtime.controlMode === PAGE_STATE.BLOCKED,
          onClick: () => {
            if (!node.next || !firstAction) return
            handlers.handleWorkflowAction({
              key: firstAction,
              label: translate(firstAction),
              type: 'workflow',
              workflowAction: firstAction,
            }, record)
          },
        }, translate(node.id))

        if (index === graphNodes.length - 1) return [nodeElement]
        return [nodeElement, h('span', { style: 'color: #94a3b8' }, '->')]
      })),
    ]),
    h('section', {
      style: 'display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 10px',
    }, [
      h('div', { style: 'padding: 10px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px' }, [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 6px' }, translate('State Transition Viewer')),
        h('strong', transitions.length ? transitions.map((item) => `${translate(item.from)} -> ${translate(item.to)}`).join(' / ') : '-'),
      ]),
      h('div', { style: 'padding: 10px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px' }, [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 6px' }, translate('Blocked Transitions')),
        h('strong', blockedTransitions.length ? String(blockedTransitions.length) : '-'),
      ]),
    ]),
  ])
}

function renderSecondaryDashboardPanel(children = []) {
  const panels = children.filter(Boolean)
  if (!panels.length) return null

  return h('details', {
    class: 'meta-secondary-dashboard-panel',
    style: 'margin-top: 12px; border: 1px solid #dce5f2; border-radius: 8px; background: #fff',
  }, [
    h('summary', {
      style: 'cursor: pointer; padding: 12px 14px; color: #334155; font-weight: 700; user-select: none',
    }, 'Dashboard / Analytics / AI Panels'),
    h('div', {
      style: 'display: grid; gap: 12px; padding: 0 12px 12px',
    }, panels),
  ])
}

function renderOrchestrationPanel(snapshot = getOrchestrationSnapshot()) {
  const graph = snapshot.dependencyGraph || { nodes: [], edges: [] }
  const events = snapshot.eventStream || []
  const triggerDashboard = snapshot.triggers || { rules: [], history: [] }

  return h('section', {
    class: 'meta-orchestration-panel',
    style: 'display: grid; gap: 12px; padding: 12px 14px; background: #fff; border: 1px solid #dce5f2; border-radius: 8px; margin-bottom: 12px',
  }, [
    h('div', { style: 'display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap' }, [
      h('div', [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 4px' }, translate('Cross-Module Flow Graph')),
        h('strong', `${graph.nodes.length} modules / ${graph.edges.length} links`),
      ]),
      h('div', [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 4px' }, translate('Event Stream Monitor')),
        h('strong', `${events.length} events`),
      ]),
      h('div', [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 4px' }, translate('Business Trigger Dashboard')),
        h('strong', `${triggerDashboard.rules.length} rules / ${triggerDashboard.history.length} hits`),
      ]),
    ]),
    h('div', { style: 'display: flex; gap: 6px; flex-wrap: wrap' }, graph.edges.map((edge) =>
      h('span', {
        style: 'padding: 4px 8px; border-radius: 999px; background: #eef2ff; color: #3730a3; font-size: 12px',
      }, `${edge.from} -> ${edge.to}`)
    )),
    h('div', { style: 'display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 10px' }, [
      h('div', { style: 'padding: 10px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px' }, [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 6px' }, translate('Latest Events')),
        h('strong', events.slice(0, 3).map((event) => event.type).join(' / ') || '-'),
      ]),
      h('div', { style: 'padding: 10px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px' }, [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 6px' }, translate('Circular Trigger Check')),
        h('strong', graph.healthy ? translate('Healthy') : `${graph.circularTriggers.length} cycles`),
      ]),
    ]),
  ])
}

function renderIntelligencePanel(snapshot = getIntelligenceSnapshot()) {
  const latest = snapshot.latest || {}
  const metrics = snapshot.metrics || {}
  const decision = latest.decision || {}
  const strategy = latest.strategy || {}
  const risk = latest.risk || {}
  const actionPlan = latest.actionPlan || { steps: [] }
  const steps = actionPlan.steps || []

  return h('section', {
    class: 'meta-intelligence-panel',
    style: 'display: grid; gap: 12px; padding: 12px 14px; background: #fff; border: 1px solid #dce5f2; border-radius: 8px; margin-bottom: 12px',
  }, [
    h('div', { style: 'display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 10px' }, [
      h('div', { style: 'padding: 10px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px' }, [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 6px' }, translate('Decision Intelligence Dashboard')),
        h('strong', decision.decision || '-'),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, `${translate('Decision Accuracy Index')}: ${metrics.decisionAccuracyIndex ?? 0}`),
      ]),
      h('div', { style: 'padding: 10px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px' }, [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 6px' }, translate('Strategy Flow Panel')),
        h('strong', strategy.primary?.type || '-'),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, strategy.primary?.objective || '-'),
      ]),
      h('div', { style: 'padding: 10px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px' }, [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 6px' }, translate('Risk Analysis View')),
        h('strong', `${risk.level || '-'} / ${risk.score ?? 0}`),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, `${translate('Risk Exposure Meter')}: ${metrics.riskExposureMeter ?? 0}`),
      ]),
      h('div', { style: 'padding: 10px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px' }, [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 6px' }, translate('Action Plan Timeline')),
        h('strong', `${steps.length} steps / ${actionPlan.executable ? 'READY' : 'REVIEW'}`),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, steps.map((step) => `${step.module}.${step.action}`).join(' / ') || '-'),
      ]),
    ]),
  ])
}

function renderEnterpriseExecutionPanel(snapshot = getExecutionLayerSnapshot()) {
  const latest = snapshot.latest || {}
  const metrics = snapshot.metrics || {}
  const actions = latest.executionResult?.actions || []
  const workflow = latest.stateUpdates?.workflow || {}
  const financialRecords = snapshot.financialRecords || []

  return h('section', {
    class: 'meta-execution-panel',
    style: 'display: grid; gap: 12px; padding: 12px 14px; background: #fff; border: 1px solid #dce5f2; border-radius: 8px; margin-bottom: 12px',
  }, [
    h('div', { style: 'display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 10px' }, [
      h('div', { style: 'padding: 10px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px' }, [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 6px' }, translate('Execution Control Dashboard')),
        h('strong', latest.status || '-'),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, `${translate('Execution Success Rate')}: ${metrics.executionSuccessRate ?? 0}`),
      ]),
      h('div', { style: 'padding: 10px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px' }, [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 6px' }, translate('Auto Execution Flow View')),
        h('strong', `${workflow.completion?.completedSteps || actions.length} steps`),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, actions.map((action) => `${action.module}.${action.action}`).join(' / ') || '-'),
      ]),
      h('div', { style: 'padding: 10px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px' }, [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 6px' }, translate('Business Action Timeline')),
        h('strong', `${snapshot.history?.length || 0} executions`),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, actions.slice(0, 3).map((action) => action.executionStatus).join(' / ') || '-'),
      ]),
      h('div', { style: 'padding: 10px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px' }, [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 6px' }, translate('Financial Automation Score')),
        h('strong', metrics.financialAutomationScore ?? 0),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, `${financialRecords.length} records`),
      ]),
    ]),
  ])
}

function renderEnterpriseAutopilotPanel(snapshot = getEnterpriseAutopilotSnapshot()) {
  const metrics = snapshot.metrics || {}
  const latest = snapshot.latest || {}
  const continuous = snapshot.continuous || { history: [] }
  const repair = snapshot.repair || {}
  const finance = snapshot.finance || {}

  return h('section', {
    class: 'meta-autopilot-panel',
    style: 'display: grid; gap: 12px; padding: 12px 14px; background: #fff; border: 1px solid #dce5f2; border-radius: 8px; margin-bottom: 12px',
  }, [
    h('div', { style: 'display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 10px' }, [
      h('div', { style: 'padding: 10px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px' }, [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 6px' }, translate('Enterprise Autopilot Dashboard')),
        h('strong', snapshot.autopilotMode || '-'),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, `${translate('Autopilot Stability Index')}: ${metrics.autopilotStabilityIndex ?? 0}`),
      ]),
      h('div', { style: 'padding: 10px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px' }, [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 6px' }, translate('Continuous Execution Monitor')),
        h('strong', `${continuous.history?.length || 0} cycles`),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, `${translate('Continuous Execution Rate')}: ${metrics.continuousExecutionRate ?? 0}`),
      ]),
      h('div', { style: 'padding: 10px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px' }, [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 6px' }, translate('Self-Repair Status Panel')),
        h('strong', repair.latest?.consistency?.state || 'STABLE'),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, `${translate('Self-Repair Success Rate')}: ${metrics.selfRepairSuccessRate ?? 0}`),
      ]),
      h('div', { style: 'padding: 10px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px' }, [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 6px' }, translate('Financial Autonomy View')),
        h('strong', finance.latest?.reconciliation?.status || 'READY'),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, `${translate('Financial Autonomy Score')}: ${metrics.financialAutonomyScore ?? 0}`),
      ]),
    ]),
    latest.optimization
      ? h('p', { style: 'margin: 0; color: #64748b' }, `${latest.optimization.recommendation || '-'} / ${latest.zeroHumanOperation || snapshot.zeroHumanOperation}`)
      : null,
  ])
}

function renderStructuralEvolutionPanel(snapshot = getStructuralEvolutionSnapshot()) {
  const latest = snapshot.latest || {}
  const metrics = snapshot.metrics || {}
  const moduleChanges = latest.moduleChanges || { splits: [], merges: [], responsibilities: [] }
  const workflowChanges = latest.workflowChanges || {}
  const performance = latest.performance || {}
  const behavior = latest.behaviorChanges || {}

  return h('section', {
    class: 'meta-evolution-panel',
    style: 'display: grid; gap: 12px; padding: 12px 14px; background: #fff; border: 1px solid #dce5f2; border-radius: 8px; margin-bottom: 12px',
  }, [
    h('div', { style: 'display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 10px' }, [
      h('div', { style: 'padding: 10px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px' }, [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 6px' }, translate('System Evolution Dashboard')),
        h('strong', `${metrics.systemEvolutionIndex ?? 0}`),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, `${snapshot.structuralEvolution || '-'} / ${snapshot.trace?.length || 0} trace`),
      ]),
      h('div', { style: 'padding: 10px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px' }, [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 6px' }, translate('Workflow Mutation View')),
        h('strong', workflowChanges.approvalRestructure?.approvalMode || '-'),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, workflowChanges.pathOptimization?.changes?.join(' / ') || '-'),
      ]),
      h('div', { style: 'padding: 10px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px' }, [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 6px' }, translate('Module Recomposition Graph')),
        h('strong', `${moduleChanges.splits.length} splits / ${moduleChanges.merges.length} merges`),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, moduleChanges.merges.map((item) => item.proposal).join(' / ') || '-'),
      ]),
      h('div', { style: 'padding: 10px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px' }, [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 6px' }, translate('Performance Evolution Panel')),
        h('strong', performance.proposals?.[0] || '-'),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, `${translate('Behavioral Adaptation Score')}: ${metrics.behavioralAdaptationScore ?? 0}`),
      ]),
    ]),
    h('p', { style: 'margin: 0; color: #64748b' }, behavior.interactionOptimization?.changes?.join(' / ') || '-'),
  ])
}

function renderStabilityConvergencePanel(snapshot = getStabilityBoundarySnapshot()) {
  const latest = snapshot.latest || {}
  const metrics = snapshot.metrics || {}
  const safety = latest.safety || {}
  const risk = safety.risk || {}
  const drift = safety.drift || {}
  const stability = safety.stability || {}

  return h('section', {
    class: 'meta-stability-panel',
    style: 'display: grid; gap: 12px; padding: 12px 14px; background: #fff; border: 1px solid #dce5f2; border-radius: 8px; margin-bottom: 12px',
  }, [
    h('div', { style: 'display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 10px' }, [
      h('div', { style: 'padding: 10px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px' }, [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 6px' }, translate('Stability Dashboard')),
        h('strong', `${metrics.systemStabilityIndex ?? 100}`),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, stability.impact || '-'),
      ]),
      h('div', { style: 'padding: 10px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px' }, [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 6px' }, translate('Evolution Risk Panel')),
        h('strong', `${metrics.evolutionRiskScore ?? 0}`),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, risk.level || '-'),
      ]),
      h('div', { style: 'padding: 10px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px' }, [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 6px' }, translate('System Drift Monitor')),
        h('strong', metrics.driftLevel || '-'),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, `${drift.complexityGrowth?.complexity ?? 0} complexity`),
      ]),
      h('div', { style: 'padding: 10px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px' }, [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 6px' }, translate('Safe Evolution Gate View')),
        h('strong', metrics.safeEvolutionStatus || '-'),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, `${translate('Allowed Evolution Rate')}: ${metrics.allowedEvolutionRate ?? 0}`),
      ]),
    ]),
  ])
}

function renderProductionFinalizationPanel(snapshot = getProductionFinalizationSnapshot()) {
  const readiness = snapshot.readiness || {}
  const compliance = snapshot.compliance || {}
  const deployment = snapshot.deployment || {}
  const freeze = snapshot.runtimeLock || {}
  const modules = compliance.modules || []

  return h('section', {
    class: 'meta-production-finalization-panel',
    style: 'display: grid; gap: 12px; padding: 12px 14px; background: #fff; border: 1px solid #dce5f2; border-radius: 8px; margin-bottom: 12px',
  }, [
    h('div', { style: 'display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 10px' }, [
      h('div', { style: 'padding: 10px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px' }, [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 6px' }, translate('Production Finalization Dashboard')),
        h('strong', `${readiness.productionReadinessScore ?? 0}`),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, snapshot.productionFinalizationMode || '-'),
      ]),
      h('div', { style: 'padding: 10px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px' }, [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 6px' }, translate('System Freeze Status Panel')),
        h('strong', snapshot.frozen ? 'FROZEN' : 'OPEN'),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, freeze.productionSafetyMode || '-'),
      ]),
      h('div', { style: 'padding: 10px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px' }, [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 6px' }, translate('Deployment Readiness View')),
        h('strong', deployment.deploymentSafetyLevel || '-'),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, readiness.deploymentReady ? 'READY' : 'REVIEW'),
      ]),
      h('div', { style: 'padding: 10px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px' }, [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 6px' }, translate('Module Compliance Report')),
        h('strong', `${compliance.moduleComplianceIndex ?? 0}`),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, modules.map((item) => `${item.module}:${item.score}`).join(' / ') || '-'),
      ]),
    ]),
  ])
}

function renderSaasLaunchPanel(runtime = {}) {
  const onboarding = runtime.tenantOnboarding || getTenantOnboardingSnapshot().latest || {}
  const billing = runtime.commercialBilling || getCommercialBillingSnapshot({ tenantId: onboarding.tenantId })
  const monitoring = runtime.commercialMonitoring || getMonitoringCenterSnapshot()
  const deployment = runtime.deploymentPipeline || getDeploymentPipelineSnapshot()
  const tenantMetrics = getTenantOnboardingSnapshot().metrics || {}

  return h('section', {
    class: 'meta-saas-launch-panel',
    style: 'display: grid; gap: 12px; padding: 12px 14px; background: #fff; border: 1px solid #dce5f2; border-radius: 8px; margin-bottom: 12px',
  }, [
    h('div', { style: 'display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 10px' }, [
      h('div', { style: 'padding: 10px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px' }, [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 6px' }, translate('SaaS Launch Dashboard')),
        h('strong', runtime.commercialMode || 'LIVE'),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, `${translate('Deployment Stability Score')}: ${deployment.metrics?.deploymentStabilityScore ?? deployment.deploymentStabilityScore ?? 0}`),
      ]),
      h('div', { style: 'padding: 10px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px' }, [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 6px' }, translate('Tenant Management Panel')),
        h('strong', onboarding.tenantId || '-'),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, `${tenantMetrics.activeTenants || 0} tenants`),
      ]),
      h('div', { style: 'padding: 10px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px' }, [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 6px' }, translate('Billing Overview')),
        h('strong', billing.invoice?.status || '-'),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, `${translate('Revenue Stream Monitor')}: ${billing.metrics?.revenueStream ?? 0}`),
      ]),
      h('div', { style: 'padding: 10px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px' }, [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 6px' }, translate('Deployment Status View')),
        h('strong', deployment.latest?.status || deployment.status || '-'),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, deployment.latest?.production?.status || '-'),
      ]),
      h('div', { style: 'padding: 10px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px' }, [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 6px' }, translate('Monitoring Center')),
        h('strong', `${monitoring.systemHealthIndex ?? 100}`),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, monitoring.health?.status || '-'),
      ]),
    ]),
  ])
}

function renderPlatformExpansionPanel(runtime = {}) {
  const platform = runtime.platformRuntime || getPlatformRuntimeSnapshot()
  const products = platform.activeProducts || []
  const modules = platform.sharedModules?.modules || []
  const flows = platform.dataBridge?.flows || []

  return h('section', {
    class: 'meta-platform-expansion-panel',
    style: 'display: grid; gap: 12px; padding: 12px 14px; background: #fff; border: 1px solid #dce5f2; border-radius: 8px; margin-bottom: 12px',
  }, [
    h('div', { style: 'display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 10px' }, [
      h('div', { style: 'padding: 10px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px' }, [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 6px' }, translate('Platform Overview Dashboard')),
        h('strong', `${platform.metrics?.platformRevenue ?? 0}`),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, `${products.length} products`),
      ]),
      h('div', { style: 'padding: 10px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px' }, [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 6px' }, translate('Multi-Product Control Center')),
        h('strong', platform.multiProductRuntime || '-'),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, products.map((product) => product.name).join(' / ') || '-'),
      ]),
      h('div', { style: 'padding: 10px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px' }, [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 6px' }, translate('Shared Module Registry View')),
        h('strong', `${modules.length} modules`),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, modules.slice(0, 4).map((module) => `${module.key} v${module.version}`).join(' / ') || '-'),
      ]),
      h('div', { style: 'padding: 10px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px' }, [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 6px' }, translate('Cross Product Data Flow Map')),
        h('strong', `${flows.length} flows`),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, flows.map((flow) => `${flow.from}->${flow.to}`).join(' / ') || '-'),
      ]),
    ]),
  ])
}

function renderEcosystemPanel(ecosystem) {
  if (!ecosystem) return null

  const plugins = ecosystem.plugins || []
  const marketplaceModules = ecosystem.marketplaceModules || []
  const sandboxEvents = ecosystem.sandboxEvents || []
  const revenue = ecosystem.revenueSharingSnapshot || ecosystem.revenue || {}

  return h('section', {
    class: 'meta-ecosystem-panel',
    style: 'display: grid; gap: 12px; padding: 12px 14px; background: #fff; border: 1px solid #dce5f2; border-radius: 8px; margin-bottom: 12px',
  }, [
    h('div', { style: 'display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 10px' }, [
      h('div', { style: 'padding: 10px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px' }, [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 6px' }, translate('Ecosystem Dashboard')),
        h('strong', `${ecosystem.metrics?.ecosystemGrowthIndex ?? 0}`),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, ecosystem.ecosystemMode || '-'),
      ]),
      h('div', { style: 'padding: 10px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px' }, [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 6px' }, translate('Developer Console')),
        h('strong', `${plugins.length} plugins`),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, Object.keys(ecosystem.developerActivity || {}).join(' / ') || '-'),
      ]),
      h('div', { style: 'padding: 10px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px' }, [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 6px' }, translate('Plugin Marketplace View')),
        h('strong', `${marketplaceModules.length} modules`),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, `${Math.round((ecosystem.metrics?.pluginAdoptionRate || 0) * 100)}% adoption`),
      ]),
      h('div', { style: 'padding: 10px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px' }, [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 6px' }, translate('Sandbox Runtime Monitor')),
        h('strong', `${sandboxEvents.length} runs`),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, revenue.revenueSharing || revenue.mode || '-'),
      ]),
    ]),
  ])
}

function renderEcosystemGovernancePanel(governance) {
  if (!governance) return null

  const quality = governance.pluginQuality || governance.quality?.ranking || []
  const stability = governance.stabilityGovernance || {}
  const revenue = governance.revenueGovernance || {}
  const security = governance.securityGovernance || governance.security || {}

  return h('section', {
    class: 'meta-ecosystem-governance-panel',
    style: 'display: grid; gap: 12px; padding: 12px 14px; background: #fff; border: 1px solid #dce5f2; border-radius: 8px; margin-bottom: 12px',
  }, [
    h('div', { style: 'display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 10px' }, [
      h('div', { style: 'padding: 10px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px' }, [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 6px' }, translate('Ecosystem Governance Dashboard')),
        h('strong', governance.decision || '-'),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, governance.governanceMode || '-'),
      ]),
      h('div', { style: 'padding: 10px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px' }, [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 6px' }, translate('Plugin Quality Heatmap')),
        h('strong', `${governance.quality?.averageScore ?? 100}`),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, quality.map((item) => `${item.pluginId}:${item.score}`).join(' / ') || '-'),
      ]),
      h('div', { style: 'padding: 10px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px' }, [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 6px' }, translate('Stability Control Panel')),
        h('strong', `${stability.ecosystemStabilityIndex ?? governance.health?.pluginStability ?? 100}`),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, stability.balance || '-'),
      ]),
      h('div', { style: 'padding: 10px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px' }, [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 6px' }, translate('Revenue Fairness View')),
        h('strong', `${revenue.fairness?.fairnessIndex ?? governance.revenueFairness?.fairnessIndex ?? 100}`),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, `${security.threatCount || 0} threats`),
      ]),
    ]),
  ])
}

function renderRealDataPanel(runtime = {}) {
  const realData = runtime.realData || {}
  const api = realData.apiConnector || getApiConnectorSnapshot()
  const database = realData.databaseLayer || getDatabaseLayerSnapshot()
  const sync = realData.dataSync || getDataSyncSnapshot()

  return h('section', {
    class: 'meta-real-data-panel',
    style: 'display: grid; gap: 12px; padding: 12px 14px; background: #fff; border: 1px solid #dce5f2; border-radius: 8px; margin-bottom: 12px',
  }, [
    h('div', { style: 'display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 10px' }, [
      h('div', { style: 'padding: 10px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px' }, [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 6px' }, translate('Real Data Dashboard')),
        h('strong', runtime.realDataMode || realData.realDataMode || 'ON'),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, `${database.tables?.length || 0} tables`),
      ]),
      h('div', { style: 'padding: 10px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px' }, [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 6px' }, translate('API Live Monitor')),
        h('strong', `${api.metrics?.apiLatency ?? 0}ms`),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, `${api.metrics?.successCount || 0} ok / ${api.metrics?.errorCount || 0} err`),
      ]),
      h('div', { style: 'padding: 10px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px' }, [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 6px' }, translate('Database Sync Status Panel')),
        h('strong', `${sync.healthScore ?? 90}`),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, `${sync.events?.length || 0} sync events`),
      ]),
    ]),
  ])
}

function renderProductionRuntimePanel(runtime = {}) {
  const productionRuntime = runtime.productionRuntimeState || {}
  const business = productionRuntime.runtime || getBusinessRuntimeSnapshot()
  const transaction = productionRuntime.transaction || getTransactionRuntimeSnapshot()
  const eventStream = productionRuntime.eventStream || getEnterpriseEventStreamSnapshot()
  const posting = productionRuntime.financialPosting || getFinancialPostingSnapshot()

  return h('section', {
    class: 'meta-production-runtime-panel',
    style: 'display: grid; gap: 12px; padding: 12px 14px; background: #fff; border: 1px solid #dce5f2; border-radius: 8px; margin-bottom: 12px',
  }, [
    h('div', { style: 'display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 10px' }, [
      h('div', { style: 'padding: 10px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px' }, [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 6px' }, translate('Live Business Execution Dashboard')),
        h('strong', `${business.businessExecutionRate ?? 100}%`),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, `${business.executions?.length || 0} executions`),
      ]),
      h('div', { style: 'padding: 10px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px' }, [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 6px' }, translate('Transaction Flow Monitor')),
        h('strong', `${transaction.successIndex ?? 100}%`),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, `${transaction.transactions?.length || 0} transactions`),
      ]),
      h('div', { style: 'padding: 10px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px' }, [
        h('span', { style: 'display: block; color: #64748b; margin-bottom: 6px' }, translate('Enterprise Event Stream View')),
        h('strong', eventStream.consistency?.consistency || 'CONSISTENT'),
        h('p', { style: 'margin: 6px 0 0; color: #64748b' }, `${eventStream.events?.length || 0} events / ${posting.postings?.length || 0} postings`),
      ]),
    ]),
  ])
}

function buildRuntime(schema, record = {}, mode = 'RUNTIME') {
  try {
    return UIControlRuntimeKernel(schema || {}, record || {}, {
      mode: mode === 'RUNTIME' || mode === 'LIVE' ? 'RUN' : mode,
      runtimeState: stateManager.snapshot(),
    })
  } catch (error) {
    return buildEmptySafeRuntime(schema, error)
  }
}

function buildEmptySafeRuntime(schema = {}, error = null) {
  const system = initRuntimeSystem()
  const safeSchema = schema || {
    ui: {
      list: {
        columns: [],
        actions: [],
      },
    },
  }

  return {
    ...system,
    mode: 'SAFE_MODE',
    controlMode: PAGE_STATE.NORMAL,
    safeMode: true,
    runtimeError: error?.message || String(error || ''),
    pageContract: {
      schema: safeSchema,
    },
    ui: {
      schema: safeSchema,
      actions: [],
      labels: {
        noData: 'Runtime safe mode',
        blockedTitle: 'Runtime safe mode',
      },
      components: {
        workflow: {
          actionsTitle: 'Workflow',
        },
      },
    },
    uiControl: {
      columns: safeSchema?.ui?.list?.columns || [],
      actions: safeSchema?.ui?.list?.actions || [],
      allowedActions: [],
    },
    workflow: {
      availableActions: [],
      nextStates: [],
    },
    saas: {
      featureAccess: {
        simulation: false,
        aiFeatures: false,
      },
    },
  }
}

function renderEmptySafeView(runtime = {}) {
  return h('div', {
    class: 'meta-list-empty',
    style: 'padding: 16px; background: #fff; border: 1px solid #dce5f2; border-radius: 8px; color: #475569',
  }, [
    h('strong', translate('No Data')),
    h('p', { style: 'margin: 6px 0 0' }, runtime.runtimeError || translate('No Data')),
  ])
}

function renderLoadingView() {
  return h('section', {
    class: 'meta-list-loading',
    style: 'display: grid; gap: 12px; padding: 16px; background: #fff; border: 1px solid #dce5f2; border-radius: 8px',
  }, [
    h('strong', translate('Loading')),
    h('div', { style: 'height: 14px; width: 40%; background: #e5edf6; border-radius: 8px' }),
    h('div', { style: 'height: 14px; width: 72%; background: #eef3f8; border-radius: 8px' }),
    h('div', { style: 'height: 14px; width: 56%; background: #eef3f8; border-radius: 8px' }),
  ])
}

function renderEmptyView({ onCreate } = {}) {
  return h('section', {
    class: 'meta-list-empty',
    style: 'padding: 18px; background: #fff; border: 1px solid #dce5f2; border-radius: 8px; display: flex; align-items: center; justify-content: space-between; gap: 12px',
  }, [
    h('div', [
      h('strong', 'No Data Available'),
      h('p', { style: 'margin: 6px 0 0; color: #64748b' }, translate('No Data')),
    ]),
    h(ElButton, { type: 'primary', onClick: onCreate }, () => translate('Create')),
  ])
}

function renderErrorView({ message, onRetry } = {}) {
  return h('section', {
    class: 'meta-list-error',
    style: 'padding: 18px; background: #fff; border: 1px solid #fecaca; border-radius: 8px; color: #991b1b; display: flex; align-items: center; justify-content: space-between; gap: 12px',
  }, [
    h('div', [
      h('strong', translate('Error')),
      h('p', { style: 'margin: 6px 0 0' }, message || translate('Error')),
    ]),
    h(ElButton, { type: 'danger', plain: true, onClick: onRetry }, () => translate('Retry')),
  ])
}

function renderWorkflowTimeline(record = {}) {
  const current = record.workflow_state || record.status || 'DRAFT'
  const steps = ['DRAFT', 'ACTIVE', 'CLOSED']

  return h('section', {
    style: 'padding: 16px; background: #fff; border: 1px solid #dce5f2; border-radius: 8px',
  }, [
    h('strong', translate('Workflow Status')),
    h('div', { style: 'display: flex; gap: 8px; flex-wrap: wrap; margin-top: 12px' }, steps.map((step) =>
      h('span', {
        style: `padding: 6px 10px; border-radius: 999px; background: ${step === current ? '#dbeafe' : '#f1f5f9'}; color: ${step === current ? '#1d4ed8' : '#64748b'}; font-size: 12px`,
      }, translate(step))
    )),
  ])
}

function renderInfoSection(title, columns, record, formState, isEdit) {
  const safeColumns = columns.length > 0 ? columns : [{ key: 'id', label: 'ID' }]

  return h('section', {
    style: 'display: grid; gap: 12px; padding: 16px; background: #fff; border: 1px solid #dce5f2; border-radius: 8px; margin-bottom: 12px',
  }, [
    h('strong', translate(title)),
    h('div', {
      style: 'display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px',
    }, safeColumns.map((column) => {
      const key = getColumnKey(column)
      const value = isEdit ? formState.value[key] : record?.[key]

      return h('label', { style: 'display: grid; gap: 6px; color: #475569' }, [
        h('span', { style: 'font-size: 12px; color: #64748b' }, translate(column.label || key)),
        isEdit
          ? h(ElInput, {
              modelValue: value ?? '',
              placeholder: translate(column.label || key),
              disabled: key === 'id',
              'onUpdate:modelValue': (nextValue) => {
                formState.value = {
                  ...formState.value,
                  [key]: nextValue,
                }
              },
            })
          : h('strong', { style: 'min-height: 32px; color: #111827' }, safeDisplay(value)),
      ])
    })),
  ])
}

function renderDetailPage({ schema = {}, record = {}, mode = 'detail', listPath = '/', router, formState, validationMessage, saveError, onSave }) {
  const columns = getFieldColumns(schema)
  const title = getSchemaTitle(schema)
  const isEdit = mode === 'edit'
  const summaryColumns = columns.slice(0, 4)
  const basicColumns = columns.slice(0, Math.ceil(columns.length / 2))
  const businessColumns = columns.slice(Math.ceil(columns.length / 2))
  const recordId = record?.id ?? formState?.value?.id ?? ''

  return h('div', { class: 'meta-list-page meta-detail-page' }, [
    h('div', {
      style: 'display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 12px',
    }, [
      h('div', [
        h(ElButton, { size: 'small', onClick: () => router.push(listPath || '/') }, () => translate('Back')),
        h('h3', { style: 'margin: 10px 0 0' }, `${title} ${isEdit ? translate('Edit') : translate('Detail')}`),
        h('p', { style: 'margin: 4px 0 0; color: #64748b' }, `${translate('Current Path')} / ${listPath}/${safeDisplay(recordId)}`),
      ]),
      h('div', { style: 'display: flex; gap: 8px; flex-wrap: wrap' }, [
        !isEdit && recordId
          ? h(ElButton, {
              size: 'small',
              type: 'primary',
              onClick: () => router.push(`${listPath}/${recordId}/edit`),
            }, () => translate('Edit'))
          : null,
      ]),
    ]),
    h('section', {
      style: 'display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-bottom: 12px',
    }, summaryColumns.map((column) => {
      const key = getColumnKey(column)
      const value = record?.[key] ?? ''

      return h('article', {
        style: 'min-height: 72px; padding: 14px; background: #fff; border: 1px solid #dce5f2; border-radius: 8px',
      }, [
        h('span', { style: 'font-size: 12px; color: #64748b' }, translate(column.label || key)),
        h('strong', { style: 'display: block; margin-top: 8px; color: #111827' }, safeDisplay(value)),
      ])
    })),
    renderInfoSection('Basic Info', basicColumns, record, formState, isEdit),
    renderInfoSection('Business Info', businessColumns, record, formState, isEdit),
    renderWorkflowTimeline(record),
    h('section', {
      style: 'display: grid; gap: 10px; padding: 16px; background: #fff; border: 1px solid #dce5f2; border-radius: 8px; margin-bottom: 12px',
    }, [
      h('strong', translate('Action Panel')),
      isEdit
        ? h('p', { style: `margin: 0; color: ${saveError.value ? '#b91c1c' : '#64748b'}` }, saveError.value || validationMessage.value || translate('Validation Passed'))
        : null,
      h('div', { style: 'display: flex; gap: 8px; justify-content: flex-end' }, [
        isEdit ? h(ElButton, { onClick: () => router.push(`${listPath}/${recordId}`) }, () => translate('Cancel')) : null,
        isEdit ? h(ElButton, { type: 'primary', onClick: onSave }, () => translate('Save')) : null,
        !isEdit ? h(ElButton, { onClick: () => router.push(listPath || '/') }, () => translate('Back')) : null,
      ]),
    ]),
  ])
}

export function createListPage(schema, route) {
  return {
    name: 'MetaListPage',

    setup() {
      const router = useRouter()
      const currentRoute = useRoute()
      const tableData = ref([])
      const filters = ref({})
      const keyword = ref('')
      const statusFilter = ref('')
      const page = ref(1)
      const pageSize = ref(10)
      const loading = ref(true)
      const error = ref(null)
      const formState = ref({})
      const validationMessage = ref('')
      const saveError = ref('')
      const runtimeSchema = ref(schema)
      const pageMode = ref('RUNTIME')
      const runtime = ref(buildRuntime(runtimeSchema.value, {}, pageMode.value))
      const generatorError = ref('')
      const generatedResult = ref(null)
      const simulationPreview = ref(null)
      const decisionPreview = ref(null)
      const executionStatus = ref(getExecutionStatus())
      const executionLog = ref(getExecutionHistory())
      const autonomousCycle = ref(null)
      const autonomousStatus = ref(getAutonomousStatus())
      const autonomousHistory = ref(getAutonomousHistory())
      const autonomousTimer = ref(null)
      const networkResult = ref(null)
      const globalEconomyResult = ref(null)
      const civilizationResult = ref(null)
      const humanResult = ref(null)
      const hybridResult = ref(null)
      const finalResult = ref(null)
      const convergenceResult = ref(null)
      const freezeResult = ref(null)
      const productResult = ref(null)
      const saasResult = ref(null)
      const launchResult = ref(null)
      const productionMonitor = ref(getProductionHealth())
      const opsState = ref(getOpsState())
      const growthResult = ref(null)
      const moduleHubResult = ref(buildModuleHub())
      const industryInput = ref('制造业ERP')
      const generatorInput = ref(JSON.stringify({
        name: 'purchaseGenerated',
        route: '/purchase/generated',
        meta: {
          title: '采购生成模块',
        },
        api: {
          module: 'purchaseGenerated',
        },
        ui: {
          list: {
            columns: [
              { key: 'index', label: '序号', type: 'index' },
              { key: 'name', label: '采购名称', sortable: true, filter: true, filterType: 'text' },
              { key: 'workflow_state', label: '流程状态', sortable: true, filter: true, filterType: 'select' },
            ],
            actions: [
              { key: 'detail', label: '详情', type: 'route', to: '/purchase/generated/:id' },
            ],
          },
        },
      }, null, 2))
      const controlledSchema = computed(() => runtime.value?.ui?.schema || runtimeSchema.value || {})
      const routePattern = String(route || '')
      const isDetailRoute = computed(() => routePattern.includes('/:id'))
      const isEditRoute = computed(() => routePattern.endsWith('/:id/edit') || currentRoute.path.endsWith('/edit'))
      const listPath = computed(() => routePattern
        ? routePattern.replace('/:id/edit', '').replace('/:id', '')
        : currentRoute.path.replace(/\/[^/]+(?:\/edit)?$/, ''))
      const isEnterpriseOperationPage = computed(() =>
        ['/work-center', '/process-center', '/organization'].includes(currentRoute.path)
      )

      const displayData = computed(() => {
        const locallyFiltered = filterRows(tableData.value, controlledSchema.value, filters.value)
        return locallyFiltered.filter((row) => {
          const matchesKeyword = !keyword.value || Object.values(row || {}).some((value) =>
            normalizeText(value).includes(normalizeText(keyword.value))
          )
          const matchesStatus = !statusFilter.value
            || row?.status === statusFilter.value
            || row?.workflow_state === statusFilter.value

          return matchesKeyword && matchesStatus
        })
      })
      const pagedData = computed(() => {
        const start = (page.value - 1) * pageSize.value
        return displayData.value.slice(start, start + pageSize.value)
      })
      const pageStateData = computed(() => (isDetailRoute.value ? tableData.value : displayData.value))
      const uiState = computed(() => createUIState({
        loading: loading.value,
        error: error.value ? error.value?.message || String(error.value) : null,
        data: pageStateData.value,
      }))

      const refreshRuntime = () => {
        runtime.value = buildRuntime(runtimeSchema.value, tableData.value[0] || {}, pageMode.value)
        trace('page:controlMode', {
          controlMode: runtime.value.controlMode,
          pageContract: runtime.value.pageContract,
          mode: runtime.value.mode,
        })
        console.log('[PAGE CONTROL MODE]', runtime.value.controlMode)
        return runtime.value
      }

      const canRunAction = (action, row = {}) => {
        if (!['RUNTIME', 'LIVE', 'SIMULATION'].includes(pageMode.value)) return false

        const nextRuntime = buildRuntime(runtimeSchema.value, row, pageMode.value)
        const key = getActionKey(action)
        const uiActionAllowed = nextRuntime.ui.actions.some((item) => getActionKey(item) === key)

        return nextRuntime.controlMode !== PAGE_STATE.BLOCKED && nextRuntime.uiControl.allowedActions.includes(key) && uiActionAllowed
      }

      const handleWorkflowAction = async (action, row = {}) => {
        if (!['RUNTIME', 'LIVE', 'SIMULATION'].includes(pageMode.value)) return
        if (runtime.value.controlMode === PAGE_STATE.BLOCKED) return

        const rowRuntime = buildRuntime(runtimeSchema.value, row, pageMode.value)
        const workflowAction = action.workflowAction || action.key

        if (!(rowRuntime.workflow?.availableActions || []).includes(workflowAction)) return

        if (pageMode.value === 'SIMULATION') {
          simulationPreview.value = simulateEnterpriseState({
            schema: runtimeSchema.value,
            record: row,
            rows: tableData.value,
            action: workflowAction,
          })
          decisionPreview.value = evaluateDecision({
            schema: runtimeSchema.value,
            record: row,
            rows: tableData.value,
            action: workflowAction,
          })
          trace('digitalTwin:simulate', simulationPreview.value)
          trace('decision:evaluate', decisionPreview.value)
          return
        }

        const workflowResult = await dataGateway.executeState(workflowAction, {
          module: runtimeSchema.value?.api?.module || runtimeSchema.value?.name,
          id: row.id,
          data: row,
        })

        if (workflowResult?.error) {
          error.value = workflowResult.error
          return
        }

        const workflowRecord = workflowResult?.data?.data?.record || workflowResult?.data?.record || workflowResult?.data?.data || null
        if (workflowRecord) {
          tableData.value = tableData.value.map((item) => (item === row || item.id === row.id ? { ...workflowRecord } : item))
          runtime.value = buildRuntime(runtimeSchema.value, workflowRecord, pageMode.value)
          recordWorkflowCompletion({
            module: runtimeSchema.value?.api?.module || runtimeSchema.value?.name,
            action: workflowAction,
            from: row.workflow_state,
            to: workflowRecord.workflow_state,
            completed: true,
          })
          trace('workflow:businessProcess', {
            action: workflowAction,
            rowId: row.id,
            workflow: workflowResult?.data?.data?.workflow || workflowResult?.data?.workflow,
          })
          return
        }

        const nextState = rowRuntime.workflow?.nextStates?.[0]
        if (nextState) {
          const field = runtimeSchema.value?.workflow?.stateField || 'workflow_state'
          const previousState = row[field]
          const execution = executeDecision({
            schema: runtimeSchema.value,
            record: row,
            rows: tableData.value,
            action: workflowAction,
            nextState,
            manualConfirm: true,
          })
          executionStatus.value = getExecutionStatus()
          executionLog.value = [...getExecutionHistory()]
          trace('execution:run', execution)

          if (!execution.executed) return

          const nextRow = execution.result?.record || {
            ...row,
            [field]: nextState,
          }
          tableData.value = tableData.value.map((item) => (item === row || item.id === row.id ? { ...nextRow } : item))
          runtime.value = buildRuntime(runtimeSchema.value, row, pageMode.value)
          recordWorkflowCompletion({
            module: runtimeSchema.value?.api?.module || runtimeSchema.value?.name,
            action: workflowAction,
            from: previousState,
            to: nextState,
            completed: true,
          })
          trace('workflow:action', {
            action: workflowAction,
            nextState,
            rowId: row.id,
          })
        }
      }

      const handlers = {
        basePath: listPath.value,
        goRoute(path) {
          if (!['RUNTIME', 'LIVE'].includes(pageMode.value)) return
          if (runtime.value.controlMode === PAGE_STATE.BLOCKED) return
          if (path) router.push(path)
        },
        handleEvent(event, row) {
          if (!['RUNTIME', 'LIVE', 'SIMULATION'].includes(pageMode.value)) return
          if (runtime.value.controlMode === PAGE_STATE.BLOCKED) return
          if (pageMode.value === 'SIMULATION') {
            simulationPreview.value = simulateEnterpriseState({
              schema: runtimeSchema.value,
              record: row,
              rows: tableData.value,
              action: event,
            })
            decisionPreview.value = evaluateDecision({
              schema: runtimeSchema.value,
              record: row,
              rows: tableData.value,
              action: event,
            })
            trace('digitalTwin:simulate', simulationPreview.value)
            trace('decision:evaluate', decisionPreview.value)
            return
          }
          recordClick({
            module: runtimeSchema.value?.api?.module || runtimeSchema.value?.name,
            action: event,
          })
          console.log(`[${String(event).toUpperCase()}]`, row)
        },
        handleWorkflowAction,
        canRunAction,
      }

      const load = async () => {
        const start = Date.now()
        const module = runtimeSchema.value?.api?.module

        refreshRuntime()
        recordModuleAccess(module, router.currentRoute.value.fullPath)
        trace('render:start', { schema: runtimeSchema.value })

        if (runtime.value.controlMode === PAGE_STATE.BLOCKED) {
          recordBlocking({
            module,
            controlMode: runtime.value.controlMode,
            reason: runtime.value.reason,
          })
          trace('render:blocked', {
            schema,
            controlMode: runtime.value.controlMode,
          })
          return
        }

        try {
          loading.value = true
          error.value = null
          const state = isDetailRoute.value
            ? await dataGateway.detailState(module, currentRoute.params.id)
            : await dataGateway.listState(module, filters.value)
          const data = state?.data
          if (state?.error) {
            throw new Error(state.error)
          }

          tableData.value = isDetailRoute.value
            ? (data ? [data] : [])
            : (Array.isArray(data) ? data : [])
          if (isDetailRoute.value) {
            formState.value = { ...(tableData.value[0] || {}) }
            validationMessage.value = translate('Validation Passed')
            saveError.value = ''
          }
          page.value = 1

          trace('render:table', { rows: tableData.value.length })
        } catch (e) {
          error.value = e
          tableData.value = []
          recordRuntimeError({
            module,
            message: e?.message || String(e),
          })
          trace('render:error', {
            message: e?.message || String(e),
          })
        } finally {
          loading.value = false
          trace('render:done', {
            cost: Date.now() - start,
          })
        }
      }

      const search = () => {
        page.value = 1
      }

      const resetSearch = () => {
        filters.value = {}
        keyword.value = ''
        statusFilter.value = ''
        page.value = 1
      }

      const refreshList = () => {
        load()
      }

      const saveDetail = async () => {
        const module = getModuleName(runtimeSchema.value)
        const id = currentRoute.params.id
        saveError.value = ''
        validationMessage.value = translate('Saving')
        const result = await dataGateway.executeState('update', {
          module,
          id,
          data: formState.value,
        })

        if (result?.error) {
          saveError.value = result.error
          validationMessage.value = ''
          return
        }

        validationMessage.value = translate('Saved')
        router.push(`${listPath.value}/${id}`)
      }

      const runLocalAutonomousCycle = () => {
        const row = tableData.value[0] || {}
        autonomousCycle.value = runAutonomousCycle({
          schema: runtimeSchema.value,
          record: row,
          rows: tableData.value,
        })
        autonomousStatus.value = getAutonomousStatus()
        autonomousHistory.value = [...getAutonomousHistory()]
        executionStatus.value = getExecutionStatus()
        executionLog.value = [...getExecutionHistory()]

        if (autonomousCycle.value.execution?.executed) {
          const nextRecord = autonomousCycle.value.execution.result?.record
          if (nextRecord) {
            tableData.value = tableData.value.map((item) => (item === row || item.id === row.id ? { ...nextRecord } : item))
          }
        }

        trace('autonomous:cycle', autonomousCycle.value)
        refreshRuntime()
      }

      onMounted(() => {
        console.log('[META PAGE MOUNTED]', schema)
        load()
      })

      watch(() => currentRoute.fullPath, () => {
        load()
      })

      onBeforeUnmount(() => {
        if (autonomousTimer.value) {
          clearInterval(autonomousTimer.value)
          autonomousTimer.value = null
        }
        stopAutonomousLoop()
      })

      const switchMode = (mode) => {
        pageMode.value = mode
        if (autonomousTimer.value && mode !== 'AUTONOMOUS') {
          clearInterval(autonomousTimer.value)
          autonomousTimer.value = null
          stopAutonomousLoop()
          autonomousStatus.value = getAutonomousStatus()
        }
        if (mode === 'SIMULATION') {
          simulationPreview.value = simulateEnterpriseState({
            schema: runtimeSchema.value,
            record: tableData.value[0] || {},
            rows: tableData.value,
            action: 'simulate',
          })
          decisionPreview.value = evaluateDecision({
            schema: runtimeSchema.value,
            record: tableData.value[0] || {},
            rows: tableData.value,
            action: 'simulate',
          })
        }
        if (mode === 'AUTONOMOUS') {
          runLocalAutonomousCycle()
          autonomousTimer.value = setInterval(runLocalAutonomousCycle, 5000)
        }
        if (mode === 'NETWORK') {
          networkResult.value = optimizeEnterpriseNetwork(createDefaultEnterpriseNetwork())
          trace('network:optimize', networkResult.value)
        }
        if (mode === 'GLOBAL') {
          globalEconomyResult.value = simulateGlobalEconomy({
            enterprises: createDefaultEnterpriseNetwork(),
            runtimeState: runtime.value,
          })
          trace('global:economy', globalEconomyResult.value)
        }
        if (mode === 'CIVILIZATION') {
          const economy = simulateGlobalEconomy({
            enterprises: createDefaultEnterpriseNetwork(),
            runtimeState: runtime.value,
          })
          civilizationResult.value = simulateCivilization({
            globalEconomy: economy,
            economy,
            runtimeState: runtime.value,
          })
          trace('civilization:simulate', civilizationResult.value)
        }
        if (mode === 'HUMAN') {
          const economy = simulateGlobalEconomy({
            enterprises: createDefaultEnterpriseNetwork(),
            runtimeState: runtime.value,
          })
          const civilization = simulateCivilization({
            globalEconomy: economy,
            economy,
            runtimeState: runtime.value,
          })
          humanResult.value = simulateHumanBehavior({
            civilization,
            decision: decisionPreview.value || runtime.value.decision,
            record: tableData.value[0] || {},
          })
          trace('human:simulate', humanResult.value)
        }
        if (mode === 'HYBRID') {
          const economy = simulateGlobalEconomy({
            enterprises: createDefaultEnterpriseNetwork(),
            runtimeState: runtime.value,
          })
          const civilization = simulateCivilization({
            globalEconomy: economy,
            economy,
            runtimeState: runtime.value,
          })
          const human = simulateHumanBehavior({
            civilization,
            decision: decisionPreview.value || runtime.value.decision,
            record: tableData.value[0] || {},
          })
          hybridResult.value = hybridDecision({
            schema: runtimeSchema.value,
            record: tableData.value[0] || {},
            rows: tableData.value,
            action: 'simulate',
            human,
            civilization,
            ai: decisionPreview.value || runtime.value.decision,
            runtimeState: runtime.value,
          })
          trace('hybrid:decision', hybridResult.value)
        }
        if (mode === 'FINAL') {
          finalResult.value = runCivilizationCore({
            schema: runtimeSchema.value,
            record: tableData.value[0] || {},
            rows: tableData.value,
            action: 'simulate',
            runtimeState: runtime.value,
            network: networkResult.value,
            globalEconomy: globalEconomyResult.value,
            civilization: civilizationResult.value,
            human: humanResult.value,
            hybrid: hybridResult.value,
          })
          trace('final:civilization', finalResult.value)
        }
        if (mode === 'CONVERGENCE') {
          convergenceResult.value = convergeSystem({
            final: finalResult.value,
            hybrid: hybridResult.value,
            human: humanResult.value,
            civilization: civilizationResult.value,
            globalEconomy: globalEconomyResult.value,
            network: networkResult.value,
            decision: decisionPreview.value || runtime.value.decision,
            executionStatus: executionStatus.value,
            autonomousStatus: autonomousStatus.value,
            workflow: runtime.value.workflow,
          })
          trace('convergence:system', convergenceResult.value)
        }
        if (mode === 'LOCK') {
          freezeResult.value = lockSystem(convergenceResult.value || runtime.value.convergence)
          trace('freeze:lock', freezeResult.value)
        }
        if (mode === 'PRODUCT') {
          productResult.value = standardizeModule(runtimeSchema.value, {
            convergence: convergenceResult.value || runtime.value.convergence,
            runtimeState: runtime.value,
            environment: 'production',
          })
          trace('product:standardize', productResult.value)
        }
        if (mode === 'SAAS') {
          const state = stateManager.snapshot()
          saasResult.value = runSaasRuntime({
            tenantId: state.tenant.id,
            tenant: state.tenant,
            plan: state.plan,
            role: state.role,
            module: runtimeSchema.value?.api?.module || runtimeSchema.value?.name,
            runtimeState: state,
          })
          trace('saas:runtime', saasResult.value)
        }
        if (mode === 'LAUNCH') {
          const state = stateManager.snapshot()
          launchResult.value = onboardTenant({
            tenantId: `${state.tenant.id}_launch`,
            companyName: `${state.tenant.name || state.tenant.id} Launch`,
            email: 'launch@profitos.local',
            plan: state.plan,
          })
          saasResult.value = runSaasRuntime({
            tenantId: launchResult.value.tenant.id,
            tenant: launchResult.value.tenant,
            plan: launchResult.value.tenant.plan,
            role: state.role,
            module: runtimeSchema.value?.api?.module || runtimeSchema.value?.name,
            runtimeState: {
              ...state,
              tenant: launchResult.value.tenant,
              plan: launchResult.value.tenant.plan,
            },
          })
          productionMonitor.value = getProductionHealth()
          opsState.value = getOpsState()
          trace('saas:launch', launchResult.value)
        }
        if (mode === 'GROWTH') {
          const state = stateManager.snapshot()
          trackSubscriptionUpgrade({
            tenantId: state.tenant.id,
            fromPlan: state.plan === 'enterprise' ? 'pro' : 'basic',
            toPlan: state.plan,
          })
          trackReferral({
            fromTenant: state.tenant.id,
            toTenant: `${state.tenant.id}_invite`,
            template: 'purchase_workflow_template',
          })
          growthResult.value = runGrowthRuntime({
            tenantId: state.tenant.id,
            tenant: state.tenant,
            module: runtimeSchema.value?.api?.module || runtimeSchema.value?.name,
            runtimeState: state,
            trackAcquisition: {
              source: 'module_page',
              campaign: 'growth_mode',
              converted: true,
            },
            activationStep: 'first module usage',
            retentionActivity: {
              module: runtimeSchema.value?.api?.module || runtimeSchema.value?.name || 'dashboard',
              workflow: 'growth_panel',
            },
          })
          trace('growth:runtime', growthResult.value)
        }
        if (mode === 'PLATFORM') {
          moduleHubResult.value = buildModuleHub()
          trace('platform:moduleHub', moduleHubResult.value)
        }
        executionStatus.value = getExecutionStatus()
        executionLog.value = [...getExecutionHistory()]
        refreshRuntime()
      }

      const saveDesignerSchema = (nextSchema) => {
        runtimeSchema.value = nextSchema
        refreshRuntime()
      }

      const generateModuleFromInput = () => {
        try {
          generatorError.value = ''
          const nextSchema = JSON.parse(generatorInput.value)
          generatedResult.value = registerGeneratedERP(nextSchema)
          runtimeSchema.value = generatedResult.value.schema
          pageMode.value = 'RUNTIME'
          refreshRuntime()
        } catch (e) {
          generatorError.value = e?.message || String(e)
        }
      }

      const generateIndustryFromInput = () => {
        try {
          generatorError.value = ''
          generatedResult.value = registerGeneratedIndustryERP(industryInput.value)
          runtimeSchema.value = generatedResult.value.schema
          pageMode.value = 'RUNTIME'
          refreshRuntime()
        } catch (e) {
          generatorError.value = e?.message || String(e)
        }
      }

      return () => {
        if (!schema) {
          return renderLoadingView()
        }

        if (!runtime.value || !runtime.value.unifiedState) {
          return renderEmptySafeView(runtime.value)
        }

        const pageRenderState = getUIState({
          loading: loading.value,
          error: error.value ? error.value?.message || String(error.value) : null,
          data: pageStateData.value,
        })

        if (runtime.value.controlMode === PAGE_STATE.BLOCKED) {
          if (isDetailRoute.value) {
            const safeRecord = {
              id: currentRoute.params.id,
              ...(tableData.value[0] || {}),
            }

            return h('div', { class: 'meta-list-page meta-detail-page' }, [
              renderBlockedView(runtime.value),
              renderDetailPage({
                schema: controlledSchema.value,
                record: safeRecord,
                mode: isEditRoute.value ? 'edit' : 'detail',
                listPath: listPath.value,
                router,
                formState,
                validationMessage,
                saveError,
                onSave: saveDetail,
              }),
            ])
          }

          return h('div', { class: 'meta-list-page' }, [
            h('section', {
              class: 'meta-page-header',
              style: 'display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; margin-bottom: 12px',
            }, [
              h('div', [
                h('h2', { style: 'margin: 0; font-size: 22px; color: #0f172a' }, getSchemaTitle(controlledSchema.value)),
                h('p', { style: 'margin: 6px 0 0; color: #64748b' }, `${translate('Current Path')} / ${currentRoute.path}`),
              ]),
              h('span', {
                style: 'padding: 5px 10px; border-radius: 999px; background: #fef2f2; color: #b91c1c; font-size: 12px; white-space: nowrap',
              }, translate(runtime.value?.controlMode || PAGE_STATE.BLOCKED)),
            ]),
            renderFilterBar({
              schema: controlledSchema.value,
              filters,
              rows: tableData,
              keyword,
              status: statusFilter,
              onSearch: search,
              onReset: resetSearch,
            }),
            h('section', {
              class: 'meta-list-toolbar',
              style: 'display: flex; justify-content: space-between; align-items: center; gap: 8px; margin-bottom: 12px; flex-wrap: wrap',
            }, [
              h('div', { style: 'display: flex; gap: 8px; flex-wrap: wrap' }, [
                h(ElButton, { type: 'primary', disabled: true }, () => translate('Create')),
                h(ElButton, { disabled: true }, () => translate('Batch Actions')),
              ]),
              h('div', { style: 'display: flex; gap: 8px; flex-wrap: wrap' }, [
                h(ElButton, { onClick: refreshList }, () => translate('Refresh')),
                h(ElButton, { disabled: true }, () => translate('Export')),
              ]),
            ]),
            renderBlockedView(runtime.value),
            h(ElTable, {
              data: [],
              style: 'width: 100%; margin-top: 12px',
              emptyText: translate('No Data'),
            }, () => renderColumns(controlledSchema.value, handlers, runtime.value)),
            h('section', {
              class: 'meta-list-pagination',
              style: 'display: flex; justify-content: flex-end; padding: 12px 0',
            }, [
              h(ElPagination, {
                currentPage: 1,
                pageSize: pageSize.value,
                total: 0,
                pageSizes: [10, 20, 50],
                layout: 'total, sizes, prev, pager, next',
              }),
            ]),
          ])
        }

        if (pageRenderState === 'LOADING') {
          return renderLoadingView()
        }

        if (pageRenderState === 'ERROR') {
          return renderErrorView({
            message: uiState.value.error,
            onRetry: load,
          })
        }

        const workflowRecord = tableData.value[0] || {}
        const workflowRuntime = buildRuntime(runtimeSchema.value, workflowRecord, pageMode.value)
        const featureAccess = workflowRuntime.saas?.featureAccess || {}
        const canUseSimulation = featureAccess.simulation !== false
        const canUseAi = featureAccess.aiFeatures === true

        if (isDetailRoute.value) {
          if (pageRenderState === 'EMPTY') {
            return renderEmptyView({
              onCreate: () => handlers.handleEvent('create', {}),
            })
          }

          return renderDetailPage({
            schema: controlledSchema.value,
            record: workflowRecord,
            mode: isEditRoute.value ? 'edit' : 'detail',
            listPath: listPath.value,
            router,
            formState,
            validationMessage,
            saveError,
            onSave: saveDetail,
          })
        }

        if (pageMode.value === 'INDUSTRY_GENERATE') {
          return h('div', { class: 'meta-list-page meta-list-industry-generate' }, [
            h('div', { style: 'display: flex; justify-content: flex-end; gap: 8px; margin-bottom: 12px; flex-wrap: wrap' }, [
              h(ElButton, { size: 'small', type: 'primary', onClick: () => switchMode('RUNTIME') }, () => 'RUNTIME MODE'),
              h(ElButton, { size: 'small', type: 'primary', plain: true, onClick: () => switchMode('DESIGN') }, () => 'DESIGN MODE'),
              h(ElButton, { size: 'small', type: 'primary', plain: true, onClick: () => switchMode('GENERATE') }, () => 'GENERATE MODE'),
              h(ElButton, { size: 'small', disabled: true }, () => 'INDUSTRY GENERATE MODE'),
            ]),
            h('div', {
              style: 'padding: 16px; background: #fff; border: 1px solid #dce5f2; border-radius: 8px',
            }, [
              h('h3', { style: 'margin: 0 0 12px' }, 'AI Industry ERP Generator'),
              h(ElInput, {
                modelValue: industryInput.value,
                placeholder: '閸掑爼鈧姳绗烢RP / 閻椻晜绁RP / 鐠愩垹濮烢RP',
                'onUpdate:modelValue': (value) => {
                  industryInput.value = value
                },
              }),
              h('div', { style: 'display: flex; align-items: center; gap: 12px; margin-top: 12px' }, [
                h(ElButton, { size: 'small', type: 'primary', onClick: generateIndustryFromInput }, () => 'Generate Industry ERP'),
                generatorError.value
                  ? h('span', { style: 'color: #b91c1c' }, generatorError.value)
                  : null,
              ]),
              generatedResult.value
                ? h('div', { style: 'margin-top: 12px; color: #166534' }, [
                    h('div', `Industry: ${generatedResult.value.industryModel?.industry || 'schema'}`),
                    h('div', `KPI: ${(generatedResult.value.industryModel?.kpis || generatedResult.value.schema?.kpis || []).join(', ')}`),
                    h('div', `Modules: ${generatedResult.value.modules.map((item) => item.name).join(', ')}`),
                  ])
                : null,
            ]),
          ])
        }

        if (pageMode.value === 'GENERATE') {
          return h('div', { class: 'meta-list-page meta-list-generate' }, [
            h('div', { style: 'display: flex; justify-content: flex-end; gap: 8px; margin-bottom: 12px; flex-wrap: wrap' }, [
              h(ElButton, { size: 'small', type: 'primary', onClick: () => switchMode('RUNTIME') }, () => 'RUNTIME MODE'),
              h(ElButton, { size: 'small', type: 'primary', plain: true, onClick: () => switchMode('DESIGN') }, () => 'DESIGN MODE'),
              h(ElButton, { size: 'small', disabled: true }, () => 'GENERATE MODE'),
              h(ElButton, { size: 'small', type: 'primary', plain: true, onClick: () => switchMode('INDUSTRY_GENERATE') }, () => 'INDUSTRY GENERATE MODE'),
            ]),
            h('div', {
              style: 'padding: 16px; background: #fff; border: 1px solid #dce5f2; border-radius: 8px',
            }, [
              h('h3', { style: 'margin: 0 0 12px' }, 'Schema Driven ERP Generator'),
              h('textarea', {
                value: generatorInput.value,
                spellcheck: false,
                style: 'width: 100%; min-height: 320px; padding: 12px; border: 1px solid #cbd5e1; border-radius: 6px; font-family: Consolas, monospace; font-size: 13px',
                onInput: (event) => {
                  generatorInput.value = event.target.value
                },
              }),
              h('div', { style: 'display: flex; align-items: center; gap: 12px; margin-top: 12px' }, [
                h(ElButton, { size: 'small', type: 'primary', onClick: generateModuleFromInput }, () => 'Generate ERP Module'),
                generatorError.value
                  ? h('span', { style: 'color: #b91c1c' }, generatorError.value)
                  : null,
              ]),
              generatedResult.value
                ? h('div', { style: 'margin-top: 12px; color: #166534' }, `Generated: ${generatedResult.value.modules.map((item) => item.name).join(', ')}`)
                : null,
            ]),
          ])
        }

        if (pageMode.value === 'DESIGN') {
          return h('div', { class: 'meta-list-page meta-list-design' }, [
            h('div', { style: 'display: flex; justify-content: flex-end; gap: 8px; margin-bottom: 12px; flex-wrap: wrap' }, [
              h(ElButton, { size: 'small', type: 'primary', onClick: () => switchMode('RUNTIME') }, () => 'RUNTIME MODE'),
              h(ElButton, { size: 'small', disabled: true }, () => 'DESIGN MODE'),
              h(ElButton, { size: 'small', type: 'primary', plain: true, onClick: () => switchMode('GENERATE') }, () => 'GENERATE MODE'),
              h(ElButton, { size: 'small', type: 'primary', plain: true, onClick: () => switchMode('INDUSTRY_GENERATE') }, () => 'INDUSTRY GENERATE MODE'),
            ]),
            h(BPMDesigner, {
              schema: runtimeSchema.value,
              disabled: runtime.value.controlMode === PAGE_STATE.BLOCKED,
              onSave: saveDesignerSchema,
              onUpdate: saveDesignerSchema,
            }),
          ])
        }

        return h('div', { class: 'meta-list-page' }, [
          h('section', {
            class: 'meta-page-header',
            style: 'display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; margin-bottom: 12px',
          }, [
            h('div', [
              h('h2', { style: 'margin: 0; font-size: 22px; color: #0f172a' }, getSchemaTitle(controlledSchema.value)),
              h('p', { style: 'margin: 6px 0 0; color: #64748b' }, `${translate('Current Path')} / ${currentRoute.path}`),
            ]),
            h('span', {
              style: 'padding: 5px 10px; border-radius: 999px; background: #ecfdf5; color: #047857; font-size: 12px; white-space: nowrap',
            }, translate(runtime.value?.controlMode || 'NORMAL')),
          ]),
          renderFilterBar({
            schema: controlledSchema.value,
            filters,
            rows: tableData,
            keyword,
            status: statusFilter,
            onSearch: search,
            onReset: resetSearch,
          }),
          h('section', {
            class: 'meta-list-toolbar',
            style: 'display: flex; justify-content: space-between; align-items: center; gap: 8px; margin-bottom: 12px; flex-wrap: wrap',
          }, [
            h('div', { style: 'display: flex; gap: 8px; flex-wrap: wrap' }, [
              h(ElButton, { type: 'primary', onClick: () => handlers.handleEvent('create', {}) }, () => translate('Create')),
              h(ElButton, { disabled: true }, () => translate('Batch Actions')),
            ]),
            h('div', { style: 'display: flex; gap: 8px; flex-wrap: wrap' }, [
              h(ElButton, { onClick: refreshList }, () => translate('Refresh')),
              h(ElButton, { disabled: true }, () => translate('Export')),
            ]),
          ]),
          pageRenderState === 'EMPTY'
            ? renderEmptyView({
                onCreate: () => handlers.handleEvent('create', {}),
              })
            : null,
          ['SUCCESS', 'EMPTY'].includes(pageRenderState)
            ? h(
                ElTable,
                {
                  data: pagedData.value,
                  style: 'width: 100%',
                  emptyText: translate('No Data'),
                },
                () => renderColumns(controlledSchema.value, handlers, runtime.value)
              )
            : null,
          ['SUCCESS', 'EMPTY'].includes(pageRenderState)
            ? h('section', {
                class: 'meta-list-pagination',
                style: 'display: flex; justify-content: flex-end; padding: 12px 0',
              }, [
                h(ElPagination, {
                  currentPage: page.value,
                  pageSize: pageSize.value,
                  total: displayData.value.length,
                  pageSizes: [10, 20, 50],
                  layout: 'total, sizes, prev, pager, next',
                  'onUpdate:currentPage': (value) => {
                    page.value = value
                  },
                  'onUpdate:pageSize': (value) => {
                    pageSize.value = value
                    page.value = 1
                  },
                }),
              ])
            : null,
          renderWorkflowPanel(workflowRuntime, handlers, workflowRecord),
          isEnterpriseOperationPage.value ? null : renderSecondaryDashboardPanel([
            h('div', { style: 'display: flex; justify-content: flex-end; gap: 8px; flex-wrap: wrap' }, [
              h(ElButton, { size: 'small', disabled: pageMode.value === 'RUNTIME', onClick: () => switchMode('RUNTIME') }, () => 'LIVE MODE'),
              canUseSimulation ? h(ElButton, { size: 'small', type: pageMode.value === 'SIMULATION' ? 'primary' : 'default', plain: pageMode.value !== 'SIMULATION', onClick: () => switchMode('SIMULATION') }, () => 'SIMULATION MODE') : null,
              h(ElButton, { size: 'small', type: pageMode.value === 'AUTONOMOUS' ? 'primary' : 'default', plain: pageMode.value !== 'AUTONOMOUS', onClick: () => switchMode('AUTONOMOUS') }, () => 'AUTONOMOUS MODE'),
              h(ElButton, { size: 'small', type: pageMode.value === 'NETWORK' ? 'primary' : 'default', plain: pageMode.value !== 'NETWORK', onClick: () => switchMode('NETWORK') }, () => 'NETWORK MODE'),
              h(ElButton, { size: 'small', type: pageMode.value === 'GLOBAL' ? 'primary' : 'default', plain: pageMode.value !== 'GLOBAL', onClick: () => switchMode('GLOBAL') }, () => 'GLOBAL MODE'),
              h(ElButton, { size: 'small', type: pageMode.value === 'CIVILIZATION' ? 'primary' : 'default', plain: pageMode.value !== 'CIVILIZATION', onClick: () => switchMode('CIVILIZATION') }, () => 'CIVILIZATION MODE'),
              h(ElButton, { size: 'small', type: pageMode.value === 'HUMAN' ? 'primary' : 'default', plain: pageMode.value !== 'HUMAN', onClick: () => switchMode('HUMAN') }, () => 'HUMAN MODE'),
              canUseAi ? h(ElButton, { size: 'small', type: pageMode.value === 'HYBRID' ? 'primary' : 'default', plain: pageMode.value !== 'HYBRID', onClick: () => switchMode('HYBRID') }, () => 'HYBRID MODE') : null,
              h(ElButton, { size: 'small', type: pageMode.value === 'FINAL' ? 'primary' : 'default', plain: pageMode.value !== 'FINAL', onClick: () => switchMode('FINAL') }, () => 'FINAL MODE'),
              h(ElButton, { size: 'small', type: pageMode.value === 'CONVERGENCE' ? 'primary' : 'default', plain: pageMode.value !== 'CONVERGENCE', onClick: () => switchMode('CONVERGENCE') }, () => 'CONVERGENCE MODE'),
              h(ElButton, { size: 'small', type: pageMode.value === 'LOCK' ? 'primary' : 'default', plain: pageMode.value !== 'LOCK', onClick: () => switchMode('LOCK') }, () => 'LOCK MODE'),
              h(ElButton, { size: 'small', type: pageMode.value === 'PRODUCT' ? 'primary' : 'default', plain: pageMode.value !== 'PRODUCT', onClick: () => switchMode('PRODUCT') }, () => 'PRODUCT MODE'),
              h(ElButton, { size: 'small', type: pageMode.value === 'SAAS' ? 'primary' : 'default', plain: pageMode.value !== 'SAAS', onClick: () => switchMode('SAAS') }, () => 'SAAS MODE'),
              h(ElButton, { size: 'small', type: pageMode.value === 'LAUNCH' ? 'primary' : 'default', plain: pageMode.value !== 'LAUNCH', onClick: () => switchMode('LAUNCH') }, () => 'LAUNCH MODE'),
              h(ElButton, { size: 'small', type: pageMode.value === 'GROWTH' ? 'primary' : 'default', plain: pageMode.value !== 'GROWTH', onClick: () => switchMode('GROWTH') }, () => 'GROWTH MODE'),
              h(ElButton, { size: 'small', type: pageMode.value === 'PLATFORM' ? 'primary' : 'default', plain: pageMode.value !== 'PLATFORM', onClick: () => switchMode('PLATFORM') }, () => 'PLATFORM MODE'),
              h(ElButton, { size: 'small', type: 'primary', plain: true, onClick: () => switchMode('DESIGN') }, () => 'DESIGN MODE'),
              h(ElButton, { size: 'small', type: 'primary', plain: true, onClick: () => switchMode('GENERATE') }, () => 'GENERATE MODE'),
              h(ElButton, { size: 'small', type: 'primary', plain: true, onClick: () => switchMode('INDUSTRY_GENERATE') }, () => 'INDUSTRY GENERATE MODE'),
            ]),
            renderDecisionPanel(pageMode.value === 'SIMULATION' ? decisionPreview.value || workflowRuntime.decision : workflowRuntime.decision),
            renderExecutionPanel(executionStatus.value || workflowRuntime.executionStatus, executionLog.value),
            renderAutonomousPanel(pageMode.value === 'AUTONOMOUS' ? autonomousCycle.value : workflowRuntime.autonomousStatus?.last, autonomousStatus.value || workflowRuntime.autonomousStatus, autonomousHistory.value),
            renderNetworkPanel(pageMode.value === 'NETWORK' ? networkResult.value || workflowRuntime.network : null),
            renderGlobalEconomyPanel(pageMode.value === 'GLOBAL' ? globalEconomyResult.value || workflowRuntime.globalEconomy : null),
            renderCivilizationPanel(pageMode.value === 'CIVILIZATION' ? civilizationResult.value || workflowRuntime.civilization : null),
            renderHumanBehaviorPanel(pageMode.value === 'HUMAN' ? humanResult.value || workflowRuntime.human : null),
            renderHybridDecisionPanel(pageMode.value === 'HYBRID' ? hybridResult.value || workflowRuntime.hybrid : null),
            renderFinalCivilizationPanel(pageMode.value === 'FINAL' ? finalResult.value || workflowRuntime.final : null),
            renderConvergencePanel(pageMode.value === 'CONVERGENCE' ? convergenceResult.value || workflowRuntime.convergence : null),
            renderProductionLockPanel(pageMode.value === 'LOCK' ? freezeResult.value || workflowRuntime.freeze : null),
            renderProductizationPanel(pageMode.value === 'PRODUCT' ? productResult.value || workflowRuntime.product : null),
            renderSaasPanel(pageMode.value === 'SAAS' ? saasResult.value || workflowRuntime.saas : null),
            renderProductionLaunchPanel(pageMode.value === 'LAUNCH' ? {
              launch: launchResult.value,
              saas: saasResult.value || workflowRuntime.saas,
              monitor: productionMonitor.value,
              ops: opsState.value,
            } : null),
            renderGrowthPanel(growthResult.value || workflowRuntime.growth),
            renderModuleHubPanel(pageMode.value === 'PLATFORM' ? moduleHubResult.value : null),
            renderSimulationPanel(pageMode.value === 'SIMULATION' ? simulationPreview.value || workflowRuntime.digitalTwin : null),
            renderOrchestrationPanel(workflowRuntime.orchestration || getOrchestrationSnapshot()),
            renderIntelligencePanel(workflowRuntime.intelligence || workflowRuntime.orchestration?.intelligence || getIntelligenceSnapshot()),
            renderEnterpriseExecutionPanel(workflowRuntime.enterpriseExecution || workflowRuntime.orchestration?.execution || getExecutionLayerSnapshot()),
            renderEnterpriseAutopilotPanel(workflowRuntime.enterpriseAutopilot || getEnterpriseAutopilotSnapshot()),
            renderStructuralEvolutionPanel(workflowRuntime.evolutionSnapshot || getStructuralEvolutionSnapshot()),
            renderStabilityConvergencePanel(workflowRuntime.stabilityBoundary || workflowRuntime.evolutionSnapshot?.stability || getStabilityBoundarySnapshot()),
            renderProductionFinalizationPanel(workflowRuntime.productionFinalization || getProductionFinalizationSnapshot()),
            renderSaasLaunchPanel(workflowRuntime),
            renderPlatformExpansionPanel(workflowRuntime),
            renderEcosystemPanel(workflowRuntime.ecosystem),
            renderEcosystemGovernancePanel(workflowRuntime.ecosystemGovernance),
            renderRealDataPanel(workflowRuntime),
            renderProductionRuntimePanel(workflowRuntime),
          ]),
        ])
      }
    },
  }
}
