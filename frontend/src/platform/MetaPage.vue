<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElAlert } from 'element-plus'
import { createListPage } from '@/meta/core/pageRenderer'
import { assertV3Schema, normalizeSchema } from '@/meta/core/schemaNormalizer'
import { runAutonomousEnterprise } from '@/meta/autonomy/autonomousEnterpriseCore'
import { getProductDeliverySnapshot } from '@/meta/product/productDelivery'
import { standardizeModuleForProduction } from '@/meta/product/moduleStandardizationCore'
import { defineProcess } from '@/meta/process/processDefinitionEngine'
import { runWorkflow, validateTransition } from '@/meta/process/workflowStateEngine'
import { trackTaskExecution } from '@/meta/process/taskEngine'
import { buildProcessRoutingMap } from '@/meta/process/processRouterEngine'
import { visualizeProcessHistory } from '@/meta/process/executionTimelineEngine'
import { runExecutionLoop } from '@/meta/execution/enterpriseExecutionLoop'
import { optimizeProcess } from '@/meta/optimization/processOptimizationEngine'
import { optimizeCost } from '@/meta/optimization/costOptimizationEngine'
import { allocateResources } from '@/meta/optimization/resourceAllocationAI'
import { analyzePerformance } from '@/meta/optimization/performanceAnalysisEngine'
import { optimizeEnterprise } from '@/meta/intelligence/globalOptimizationAI'
import { predictAction } from '@/meta/prediction/predictiveEngine'
import { autoDecide } from '@/meta/decision/decisionAutomationEngine'
import { runAutonomousERP } from '@/meta/autonomy/autonomousExecutionEngine'

const props = defineProps({
  schema: {
    type: Object,
    required: true,
  },
})

const router = useRouter()

const normalizedSchema = computed(() => normalizeSchema(props.schema))
const schemaStatus = computed(() => assertV3Schema(normalizedSchema.value))
const Page = computed(() =>
  schemaStatus.value.valid ? createListPage(normalizedSchema.value, router) : null
)
const autonomousEnterprise = computed(() =>
  runAutonomousEnterprise({
    schema: normalizedSchema.value,
    goal: 'unmanned_enterprise_operation',
  })
)
const standardizedModule = computed(() => standardizeModuleForProduction(normalizedSchema.value))
const productDelivery = computed(() => getProductDeliverySnapshot([standardizedModule.value]))
const processDefinition = computed(() => defineProcess('purchase'))
const processWorkflow = computed(() => runWorkflow('purchase', ['SUBMIT', 'APPROVE']))
const processTasks = computed(() => trackTaskExecution('purchase', processDefinition.value.steps))
const processRoutingMap = computed(() => buildProcessRoutingMap('purchase'))
const processTimeline = computed(() => visualizeProcessHistory('purchase', ['SUBMIT', 'APPROVE']))
const invalidTransitionCheck = computed(() => validateTransition('purchase', 'draft', 'APPROVE'))
const executionClosedLoop = computed(() => runExecutionLoop(processDefinition.value))
const processOptimization = computed(() => optimizeProcess(executionClosedLoop.value))
const costOptimization = computed(() => optimizeCost(executionClosedLoop.value))
const resourceAllocation = computed(() => allocateResources(executionClosedLoop.value))
const performanceAnalysis = computed(() => analyzePerformance(executionClosedLoop.value))
const globalOptimization = computed(() => optimizeEnterprise({
  executionClosedLoop: executionClosedLoop.value,
  optimizationRuntime: {
    process: processOptimization.value,
    cost: costOptimization.value,
    resources: resourceAllocation.value,
    performance: performanceAnalysis.value,
  },
}))
const predictiveDecision = computed(() => predictAction({
  schema: normalizedSchema.value,
  executionClosedLoop: executionClosedLoop.value,
  optimizationRuntime: {
    process: processOptimization.value,
    cost: costOptimization.value,
    resources: resourceAllocation.value,
    performance: performanceAnalysis.value,
  },
  intelligenceOptimizationRuntime: globalOptimization.value,
}))
const automatedDecision = computed(() => autoDecide({
  schema: normalizedSchema.value,
  executionClosedLoop: executionClosedLoop.value,
  optimizationRuntime: {
    process: processOptimization.value,
    cost: costOptimization.value,
    resources: resourceAllocation.value,
    performance: performanceAnalysis.value,
  },
  intelligenceOptimizationRuntime: globalOptimization.value,
  predictionRuntime: predictiveDecision.value,
}))
const autonomousERP = computed(() => runAutonomousERP({
  schema: normalizedSchema.value,
  executionClosedLoop: executionClosedLoop.value,
  optimizationRuntime: {
    process: processOptimization.value,
    cost: costOptimization.value,
    resources: resourceAllocation.value,
    performance: performanceAnalysis.value,
  },
  intelligenceOptimizationRuntime: globalOptimization.value,
  predictionRuntime: predictiveDecision.value,
  decisionAutomationRuntime: automatedDecision.value,
}))
</script>

<template>
  <div v-if="Page" class="meta-page-shell">
    <component :is="Page" />

    <details class="meta-secondary-panels">
      <summary>Dashboard / Analytics / Runtime Panels</summary>

    <section class="autonomous-dashboard">
      <header class="autonomous-dashboard__header">
        <div>
          <p class="autonomous-dashboard__eyebrow">V30 Autonomous Enterprise OS</p>
          <h2>Autonomous Enterprise Dashboard</h2>
        </div>
        <strong>{{ autonomousEnterprise.fullAutonomyMode }}</strong>
      </header>

      <div class="autonomous-dashboard__grid">
        <article>
          <span>Zero Human Layer</span>
          <strong>{{ autonomousEnterprise.zeroHumanLayer }}</strong>
          <p>{{ autonomousEnterprise.execution.zeroHuman.controlPrinciple }}</p>
        </article>

        <article>
          <span>Continuous Runtime Monitor</span>
          <strong>{{ autonomousEnterprise.continuousRuntime }}</strong>
          <p>{{ autonomousEnterprise.execution.continuousRuntime.infiniteBusinessLoop }}</p>
        </article>

        <article>
          <span>Self-Healing Status Panel</span>
          <strong>{{ autonomousEnterprise.selfHealing }}</strong>
          <p>{{ autonomousEnterprise.healing.consistency.state }}</p>
        </article>

        <article>
          <span>Financial Autopilot View</span>
          <strong>{{ autonomousEnterprise.execution.financialAutopilot.financialAutopilot }}</strong>
          <p>{{ autonomousEnterprise.execution.financialAutopilot.accounting.accrualStatus }}</p>
        </article>
      </div>
    </section>

    <section class="product-dashboard">
      <header class="product-dashboard__header">
        <div>
          <p class="product-dashboard__eyebrow">Product Engineering Delivery Phase</p>
          <h2>Product Overview Dashboard</h2>
        </div>
        <strong>{{ productDelivery.productizationMode }}</strong>
      </header>

      <div class="product-dashboard__metrics">
        <article>
          <span>Architecture Frozen</span>
          <strong>{{ productDelivery.architectureFrozen ? 'TRUE' : 'FALSE' }}</strong>
        </article>
        <article>
          <span>Delivery Ready</span>
          <strong>{{ productDelivery.deliveryReady ? 'TRUE' : 'FALSE' }}</strong>
        </article>
        <article>
          <span>API Contract</span>
          <strong>{{ productDelivery.apiContract.strict ? 'STRICT' : 'OPEN' }}</strong>
        </article>
        <article>
          <span>Module Standard</span>
          <strong>{{ productDelivery.moduleStandard.keys.length }} KEYS</strong>
        </article>
      </div>
    </section>

    <section class="product-dashboard">
      <header class="product-dashboard__header">
        <div>
          <p class="product-dashboard__eyebrow">Module Catalog View</p>
          <h2>{{ standardizedModule.moduleName }}</h2>
        </div>
        <strong>STANDARDIZED</strong>
      </header>

      <div class="module-catalog">
        <article v-for="key in productDelivery.moduleStandard.keys" :key="key">
          <span>{{ key }}</span>
          <strong>{{ standardizedModule[key] ? 'READY' : 'EMPTY' }}</strong>
        </article>
      </div>
    </section>

    <section class="product-dashboard">
      <header class="product-dashboard__header">
        <div>
          <p class="product-dashboard__eyebrow">System Architecture Viewer</p>
          <h2>Enterprise SaaS Four-Layer Architecture</h2>
        </div>
        <strong>FROZEN</strong>
      </header>

      <div class="architecture-viewer">
        <article v-for="layer in productDelivery.architecture.layers" :key="layer.key">
          <span>{{ layer.name }}</span>
          <p>{{ layer.responsibility }}</p>
        </article>
      </div>
    </section>

    <section class="product-dashboard">
      <header class="product-dashboard__header">
        <div>
          <p class="product-dashboard__eyebrow">Deployment Status Panel</p>
          <h2>dev / staging / production</h2>
        </div>
        <strong>SUPPORTED</strong>
      </header>

      <div class="deployment-panel">
        <article v-for="environment in productDelivery.deployment.environments" :key="environment.key">
          <span>{{ environment.name }}</span>
          <strong>{{ environment.status }}</strong>
          <p>{{ environment.runtimeMode }} / {{ environment.target }}</p>
        </article>
      </div>
    </section>

    <section class="process-dashboard">
      <header class="product-dashboard__header">
        <div>
          <p class="product-dashboard__eyebrow">Process Execution Dashboard</p>
          <h2>Purchase Process Runtime</h2>
        </div>
        <strong>{{ processWorkflow.currentState }}</strong>
      </header>

      <div class="process-grid">
        <article>
          <span>Process Mode</span>
          <strong>ACTIVE</strong>
          <p>{{ processDefinition.steps.length }} steps / {{ processDefinition.transitions.length }} transitions</p>
        </article>
        <article>
          <span>Workflow Engine</span>
          <strong>ENABLED</strong>
          <p>{{ processWorkflow.history.map((item) => `${item.from}->${item.to}`).join(' / ') }}</p>
        </article>
        <article>
          <span>Task Engine</span>
          <strong>ACTIVE</strong>
          <p>{{ processTasks.length }} role tasks assigned and completed</p>
        </article>
        <article>
          <span>Process Routing</span>
          <strong>ON</strong>
          <p>{{ processRoutingMap.map((item) => `${item.fromRole}->${item.toRole}`).join(' / ') }}</p>
        </article>
      </div>
    </section>

    <section class="process-dashboard">
      <header class="product-dashboard__header">
        <div>
          <p class="product-dashboard__eyebrow">Workflow State Viewer</p>
          <h2>draft -> submitted -> approved</h2>
        </div>
        <strong>{{ invalidTransitionCheck.blocked ? 'INVALID BLOCKED' : 'OPEN' }}</strong>
      </header>

      <div class="process-grid">
        <article v-for="step in processDefinition.steps" :key="step.key">
          <span>{{ step.label }}</span>
          <strong>{{ step.role }}</strong>
          <p>{{ processWorkflow.currentState === step.key ? 'CURRENT' : 'AVAILABLE' }}</p>
        </article>
        <article>
          <span>Illegal Jump</span>
          <strong>{{ invalidTransitionCheck.reason }}</strong>
          <p>draft cannot jump directly to approved.</p>
        </article>
      </div>
    </section>

    <section class="process-dashboard">
      <header class="product-dashboard__header">
        <div>
          <p class="product-dashboard__eyebrow">Task Assignment Panel</p>
          <h2>Role-driven execution</h2>
        </div>
        <strong>{{ processTasks.length }} TASKS</strong>
      </header>

      <div class="process-grid">
        <article v-for="item in processTasks" :key="item.assigned.id">
          <span>{{ item.assigned.step }}</span>
          <strong>{{ item.assigned.role }}</strong>
          <p>{{ item.completion.task.status }} / {{ item.validation.valid ? 'VALID' : item.validation.reason }}</p>
        </article>
      </div>
    </section>

    <section class="process-dashboard">
      <header class="product-dashboard__header">
        <div>
          <p class="product-dashboard__eyebrow">Execution Timeline View</p>
          <h2>{{ processTimeline.graph }}</h2>
        </div>
        <strong>{{ processTimeline.blocked ? 'BLOCKED' : 'COMPLETED' }}</strong>
      </header>

      <div class="timeline-list">
        <article v-for="item in processTimeline.timeline" :key="item.id">
          <span>{{ item.timestamp }}</span>
          <strong>{{ item.action }} / {{ item.role }}</strong>
          <p>{{ item.from }} -> {{ item.to }} / {{ item.status }}</p>
        </article>
      </div>
    </section>

    <section class="process-dashboard">
      <header class="product-dashboard__header">
        <div>
          <p class="product-dashboard__eyebrow">Execution Loop Dashboard</p>
          <h2>Workflow -> Task -> State -> Timeline -> Data</h2>
        </div>
        <strong>{{ executionClosedLoop.closedLoopMode }}</strong>
      </header>

      <div class="process-grid">
        <article>
          <span>Execution Loop</span>
          <strong>{{ executionClosedLoop.executionLoop }}</strong>
          <p>{{ executionClosedLoop.completed ? 'No process breakpoints' : executionClosedLoop.breakpoints.join(' / ') }}</p>
        </article>
        <article>
          <span>Process Execution</span>
          <strong>{{ executionClosedLoop.processExecution }}</strong>
          <p>{{ executionClosedLoop.execution.transaction.mode }}</p>
        </article>
        <article>
          <span>Data Landing</span>
          <strong>{{ executionClosedLoop.dataLanded ? 'COMMITTED' : 'BLOCKED' }}</strong>
          <p>{{ executionClosedLoop.persistence.id }}</p>
        </article>
        <article>
          <span>State Consistency</span>
          <strong>{{ executionClosedLoop.state.consistent ? 'CONSISTENT' : 'REVIEW' }}</strong>
          <p>{{ executionClosedLoop.state.currentState }}</p>
        </article>
      </div>
    </section>

    <section class="process-dashboard">
      <header class="product-dashboard__header">
        <div>
          <p class="product-dashboard__eyebrow">End-to-End Process View</p>
          <h2>Purchase execution closed loop</h2>
        </div>
        <strong>{{ executionClosedLoop.completed ? 'COMPLETED' : 'BLOCKED' }}</strong>
      </header>

      <div class="process-grid">
        <article>
          <span>Workflow</span>
          <strong>{{ executionClosedLoop.workflow.currentState }}</strong>
          <p>{{ executionClosedLoop.workflow.consistency.reason || 'strict validation passed' }}</p>
        </article>
        <article>
          <span>Tasks</span>
          <strong>{{ executionClosedLoop.tasks.length }}</strong>
          <p>{{ executionClosedLoop.tasks.every((item) => item.confirmation.confirmed) ? 'all confirmed' : 'pending' }}</p>
        </article>
        <article>
          <span>Cross-module Execution</span>
          <strong>{{ executionClosedLoop.execution.crossModuleExecution.status }}</strong>
          <p>{{ executionClosedLoop.execution.crossModuleExecution.modules.join(' / ') }}</p>
        </article>
        <article>
          <span>Transaction Safety</span>
          <strong>{{ executionClosedLoop.execution.transaction.safe ? 'SAFE' : 'BLOCKED' }}</strong>
          <p>{{ executionClosedLoop.execution.transaction.rollbackProtection }}</p>
        </article>
      </div>
    </section>

    <section class="process-dashboard">
      <header class="product-dashboard__header">
        <div>
          <p class="product-dashboard__eyebrow">Business Flow Replay Panel</p>
          <h2>{{ executionClosedLoop.timeline.graph }}</h2>
        </div>
        <strong>{{ executionClosedLoop.timeline.performance.totalDurationMs }}ms</strong>
      </header>

      <div class="timeline-list">
        <article v-for="item in executionClosedLoop.timeline.replay" :key="`${item.replayOrder}-${item.action}`">
          <span>#{{ item.replayOrder }} {{ item.action }}</span>
          <strong>{{ item.replayStatus }}</strong>
          <p>{{ item.from }} -> {{ item.to }} / {{ item.role }}</p>
        </article>
      </div>
    </section>

    <section class="process-dashboard">
      <header class="product-dashboard__header">
        <div>
          <p class="product-dashboard__eyebrow">Optimization Dashboard</p>
          <h2>Self-optimizing ERP runtime</h2>
        </div>
        <strong>{{ processOptimization.optimizationMode }}</strong>
      </header>

      <div class="process-grid">
        <article>
          <span>Process Optimization</span>
          <strong>{{ processOptimization.processOptimization }}</strong>
          <p>{{ processOptimization.optimizedFlow.reducedSteps }} step reduced</p>
        </article>
        <article>
          <span>Efficiency Gain</span>
          <strong>+{{ processOptimization.efficiencyGain.gain }}</strong>
          <p>{{ processOptimization.efficiencyGain.before }} -> {{ processOptimization.efficiencyGain.after }}</p>
        </article>
        <article>
          <span>Cost Optimization</span>
          <strong>{{ costOptimization.costOptimization }}</strong>
          <p>${{ costOptimization.totalSaving.toLocaleString() }} saving</p>
        </article>
        <article>
          <span>Resource AI</span>
          <strong>{{ resourceAllocation.resourceAI }}</strong>
          <p>{{ resourceAllocation.workloadDistribution.recommendation }}</p>
        </article>
      </div>
    </section>

    <section class="process-dashboard">
      <header class="product-dashboard__header">
        <div>
          <p class="product-dashboard__eyebrow">Process Efficiency View</p>
          <h2>Workflow speed and score</h2>
        </div>
        <strong>{{ performanceAnalysis.processEfficiency.grade }}</strong>
      </header>

      <div class="process-grid">
        <article>
          <span>Efficiency Score</span>
          <strong>{{ performanceAnalysis.processEfficiency.score }}/100</strong>
          <p>{{ performanceAnalysis.workflowSpeed.completedSteps }} completed steps</p>
        </article>
        <article>
          <span>Total Duration</span>
          <strong>{{ performanceAnalysis.workflowSpeed.totalDurationMs }}ms</strong>
          <p>{{ performanceAnalysis.workflowSpeed.averageStepDurationMs }}ms average</p>
        </article>
        <article v-for="department in performanceAnalysis.departmentPerformance" :key="department.role">
          <span>{{ department.role }}</span>
          <strong>{{ Math.round(department.completionRate * 100) }}%</strong>
          <p>{{ department.performance }}</p>
        </article>
      </div>
    </section>

    <section class="process-dashboard">
      <header class="product-dashboard__header">
        <div>
          <p class="product-dashboard__eyebrow">Cost Analysis Panel</p>
          <h2>Procurement / inventory / production</h2>
        </div>
        <strong>${{ costOptimization.totalSaving.toLocaleString() }}</strong>
      </header>

      <div class="process-grid">
        <article>
          <span>Procurement Cost</span>
          <strong>${{ costOptimization.procurement.saving.toLocaleString() }}</strong>
          <p>{{ costOptimization.procurement.recommendation }}</p>
        </article>
        <article>
          <span>Inventory Cost</span>
          <strong>${{ costOptimization.inventory.saving.toLocaleString() }}</strong>
          <p>{{ costOptimization.inventory.recommendation }}</p>
        </article>
        <article>
          <span>Production Cost</span>
          <strong>${{ costOptimization.production.saving.toLocaleString() }}</strong>
          <p>{{ costOptimization.production.recommendation }}</p>
        </article>
        <article>
          <span>Saving Rate</span>
          <strong>{{ Math.round(costOptimization.savingRate * 100) }}%</strong>
          <p>Estimated closed-loop cost improvement.</p>
        </article>
      </div>
    </section>

    <section class="process-dashboard">
      <header class="product-dashboard__header">
        <div>
          <p class="product-dashboard__eyebrow">Bottleneck Heatmap</p>
          <h2>Slow workflows / blocked processes / inefficient roles</h2>
        </div>
        <strong>{{ processOptimization.bottlenecks.length }} ITEMS</strong>
      </header>

      <div class="process-grid">
        <article v-for="item in processOptimization.bottlenecks" :key="`${item.type}-${item.step}-${item.role}`">
          <span>{{ item.type }}</span>
          <strong>{{ item.severity }}</strong>
          <p>{{ item.step }} / {{ item.role }} / {{ item.recommendation }}</p>
        </article>
      </div>
    </section>

    <section class="process-dashboard">
      <header class="product-dashboard__header">
        <div>
          <p class="product-dashboard__eyebrow">Resource Allocation View</p>
          <h2>Human and system resource AI</h2>
        </div>
        <strong>{{ resourceAllocation.workloadDistribution.balanced ? 'BALANCED' : 'REBALANCE' }}</strong>
      </header>

      <div class="process-grid">
        <article v-for="resource in resourceAllocation.humanResources" :key="resource.role">
          <span>{{ resource.role }}</span>
          <strong>{{ resource.allocation }}</strong>
          <p>{{ resource.recommendation }}</p>
        </article>
        <article>
          <span>System Resources</span>
          <strong>{{ resourceAllocation.systemResources.workflowWorkers }} workers</strong>
          <p>{{ resourceAllocation.systemResources.recommendation }}</p>
        </article>
      </div>
    </section>

    <section class="process-dashboard">
      <header class="product-dashboard__header">
        <div>
          <p class="product-dashboard__eyebrow">Global Optimization Dashboard</p>
          <h2>Enterprise intelligence optimization</h2>
        </div>
        <strong>{{ globalOptimization.globalOptimizationAI }}</strong>
      </header>

      <div class="process-grid">
        <article>
          <span>Intelligence Optimization</span>
          <strong>{{ globalOptimization.intelligenceOptimizationMode }}</strong>
          <p>{{ globalOptimization.globalPlan.target }}</p>
        </article>
        <article>
          <span>Expected Efficiency</span>
          <strong>{{ globalOptimization.globalPlan.expectedEfficiencyScore }}/100</strong>
          <p>{{ globalOptimization.predictedImprovements.futurePerformance.horizon }}</p>
        </article>
        <article>
          <span>Expected Cost Saving</span>
          <strong>${{ globalOptimization.globalPlan.expectedCostSaving.toLocaleString() }}</strong>
          <p>{{ globalOptimization.costOptimization.intelligence.procurementStrategy.executionPath }}</p>
        </article>
        <article>
          <span>Predicted Improvements</span>
          <strong>{{ globalOptimization.predictedImprovements.predictiveOptimization }}</strong>
          <p>{{ globalOptimization.predictedImprovements.proactiveImprovements.length }} proactive actions</p>
        </article>
      </div>
    </section>

    <section class="process-dashboard">
      <header class="product-dashboard__header">
        <div>
          <p class="product-dashboard__eyebrow">Adaptive Process Flow View</p>
          <h2>{{ globalOptimization.processOptimization.adaptiveFlow.dynamicPath.join(' -> ') }}</h2>
        </div>
        <strong>{{ globalOptimization.adaptiveProcess }}</strong>
      </header>

      <div class="process-grid">
        <article>
          <span>Restructure Mode</span>
          <strong>{{ globalOptimization.processOptimization.adaptiveFlow.restructureMode }}</strong>
          <p>{{ globalOptimization.processOptimization.adaptiveFlow.pathPolicy }}</p>
        </article>
        <article>
          <span>Removed Steps</span>
          <strong>{{ globalOptimization.processOptimization.adaptiveFlow.removed.removedSteps }}</strong>
          <p>{{ globalOptimization.processOptimization.optimizedFlow.recommendation }}</p>
        </article>
      </div>
    </section>

    <section class="process-dashboard">
      <header class="product-dashboard__header">
        <div>
          <p class="product-dashboard__eyebrow">Cost Intelligence Panel</p>
          <h2>Cheapest execution path</h2>
        </div>
        <strong>{{ globalOptimization.costOptimization.intelligence.costIntelligence }}</strong>
      </header>

      <div class="process-grid">
        <article>
          <span>Selected Path</span>
          <strong>{{ globalOptimization.costOptimization.intelligence.cheapestExecutionPath.selected.path }}</strong>
          <p>${{ globalOptimization.costOptimization.intelligence.cheapestExecutionPath.selected.cost.toLocaleString() }}</p>
        </article>
        <article>
          <span>Dynamic Saving</span>
          <strong>${{ globalOptimization.costOptimization.intelligence.operationalCost.dynamicSaving.toLocaleString() }}</strong>
          <p>{{ globalOptimization.costOptimization.intelligence.procurementStrategy.recommendation }}</p>
        </article>
      </div>
    </section>

    <section class="process-dashboard">
      <header class="product-dashboard__header">
        <div>
          <p class="product-dashboard__eyebrow">Resource AI Allocation Map</p>
          <h2>Dynamic workload balancing</h2>
        </div>
        <strong>{{ globalOptimization.resourceOptimization.intelligence.resourceIntelligence }}</strong>
      </header>

      <div class="process-grid">
        <article v-for="resource in globalOptimization.resourceOptimization.intelligence.dynamicAllocation" :key="resource.role">
          <span>{{ resource.role }}</span>
          <strong>{{ resource.dynamicAllocation }}</strong>
          <p>{{ resource.allocation }} / {{ resource.confidence }} confidence</p>
        </article>
      </div>
    </section>

    <section class="process-dashboard">
      <header class="product-dashboard__header">
        <div>
          <p class="product-dashboard__eyebrow">Predictive Bottleneck Viewer</p>
          <h2>Before they occur</h2>
        </div>
        <strong>{{ globalOptimization.predictiveOptimization }}</strong>
      </header>

      <div class="process-grid">
        <article v-for="prediction in globalOptimization.predictedImprovements.predictedBottlenecks" :key="prediction.id">
          <span>{{ prediction.step }}</span>
          <strong>{{ Math.round(prediction.probability * 100) }}%</strong>
          <p>{{ prediction.role }} / {{ prediction.proactiveAction }}</p>
        </article>
      </div>
    </section>

    <section class="process-dashboard">
      <header class="product-dashboard__header">
        <div>
          <p class="product-dashboard__eyebrow">Predictive Decision Panel</p>
          <h2>Pre-action decision preview</h2>
        </div>
        <strong>{{ predictiveDecision.decisionPreview }}</strong>
      </header>

      <div class="process-grid">
        <article>
          <span>Prediction Mode</span>
          <strong>{{ predictiveDecision.predictionMode }}</strong>
          <p>{{ predictiveDecision.predictiveEngine }}</p>
        </article>
        <article>
          <span>Approval Forecast</span>
          <strong>{{ predictiveDecision.approvalProbability.probabilityScore }}%</strong>
          <p>{{ predictiveDecision.approvalProbability.forecast }}</p>
        </article>
        <article>
          <span>Cost Impact</span>
          <strong>${{ Math.abs(predictiveDecision.costImpact.totalImpact).toLocaleString() }}</strong>
          <p>{{ predictiveDecision.costImpact.impactDirection }}</p>
        </article>
        <article>
          <span>Risk Level</span>
          <strong>{{ predictiveDecision.riskLevel.level }}</strong>
          <p>{{ predictiveDecision.riskLevel.score }}/100 risk score</p>
        </article>
      </div>
    </section>

    <section class="process-dashboard">
      <header class="product-dashboard__header">
        <div>
          <p class="product-dashboard__eyebrow">Approval Forecast View</p>
          <h2>{{ predictiveDecision.approvalProbability.forecast }}</h2>
        </div>
        <strong>{{ predictiveDecision.approvalProbability.probabilityScore }}%</strong>
      </header>

      <div class="process-grid">
        <article>
          <span>Workflow Consistency</span>
          <strong>{{ predictiveDecision.approvalProbability.factors.workflowConsistency ? 'CONSISTENT' : 'REVIEW' }}</strong>
          <p>State machine signal before approval submission</p>
        </article>
        <article>
          <span>Task Completion Signal</span>
          <strong>{{ Math.round(predictiveDecision.approvalProbability.factors.taskCompletionRate * 100) }}%</strong>
          <p>Completed role tasks included in approval forecast</p>
        </article>
      </div>
    </section>

    <section class="process-dashboard">
      <header class="product-dashboard__header">
        <div>
          <p class="product-dashboard__eyebrow">Cost Impact Preview</p>
          <h2>{{ predictiveDecision.costImpact.impactDirection }}</h2>
        </div>
        <strong>${{ predictiveDecision.costImpact.predictedTotal.toLocaleString() }}</strong>
      </header>

      <div class="process-grid">
        <article>
          <span>Procurement</span>
          <strong>${{ predictiveDecision.costImpact.procurement.predictedCost.toLocaleString() }}</strong>
          <p>${{ predictiveDecision.costImpact.procurement.expectedSaving.toLocaleString() }} expected saving</p>
        </article>
        <article>
          <span>Production</span>
          <strong>${{ predictiveDecision.costImpact.production.predictedCost.toLocaleString() }}</strong>
          <p>${{ predictiveDecision.costImpact.production.expectedSaving.toLocaleString() }} expected saving</p>
        </article>
        <article>
          <span>Inventory</span>
          <strong>${{ predictiveDecision.costImpact.inventory.predictedCost.toLocaleString() }}</strong>
          <p>${{ predictiveDecision.costImpact.inventory.expectedSaving.toLocaleString() }} expected saving</p>
        </article>
      </div>
    </section>

    <section class="process-dashboard">
      <header class="product-dashboard__header">
        <div>
          <p class="product-dashboard__eyebrow">Risk Prediction Dashboard</p>
          <h2>{{ predictiveDecision.riskLevel.level }}</h2>
        </div>
        <strong>{{ predictiveDecision.executionTime.etaLabel }}</strong>
      </header>

      <div class="process-grid">
        <article>
          <span>Workflow Risk</span>
          <strong>{{ predictiveDecision.riskLevel.workflow.level }}</strong>
          <p>{{ predictiveDecision.riskLevel.workflow.signal }}</p>
        </article>
        <article>
          <span>Financial Risk</span>
          <strong>{{ predictiveDecision.riskLevel.financial.level }}</strong>
          <p>{{ predictiveDecision.riskLevel.financial.signal }}</p>
        </article>
        <article>
          <span>Supply Chain Risk</span>
          <strong>{{ predictiveDecision.riskLevel.supplyChain.level }}</strong>
          <p>{{ predictiveDecision.riskLevel.supplyChain.signal }}</p>
        </article>
      </div>
    </section>

    <section class="process-dashboard">
      <header class="product-dashboard__header">
        <div>
          <p class="product-dashboard__eyebrow">Decision Automation Dashboard</p>
          <h2>Semi-autonomous ERP decision runtime</h2>
        </div>
        <strong>{{ automatedDecision.autoDecision }}</strong>
      </header>

      <div class="process-grid">
        <article>
          <span>Decision Mode</span>
          <strong>{{ automatedDecision.decisionMode }}</strong>
          <p>{{ automatedDecision.autoExecution }}</p>
        </article>
        <article>
          <span>Policy Decision</span>
          <strong>{{ automatedDecision.policyDecision }}</strong>
          <p>{{ automatedDecision.policyDecisionResult.enforcement }}</p>
        </article>
        <article>
          <span>Risk Control</span>
          <strong>{{ automatedDecision.riskDecisionControl }}</strong>
          <p>{{ automatedDecision.riskDecision.action }}</p>
        </article>
        <article>
          <span>Decision Trace</span>
          <strong>{{ automatedDecision.trace.length }} STEPS</strong>
          <p>{{ automatedDecision.trace.join(' / ') }}</p>
        </article>
      </div>
    </section>

    <section class="process-dashboard">
      <header class="product-dashboard__header">
        <div>
          <p class="product-dashboard__eyebrow">Auto Approval Monitor</p>
          <h2>{{ automatedDecision.approvalDecision.action }}</h2>
        </div>
        <strong>{{ automatedDecision.approvalDecision.autoApproval }}</strong>
      </header>

      <div class="process-grid">
        <article>
          <span>Approval Path</span>
          <strong>{{ automatedDecision.approvalDecision.approvalPath }}</strong>
          <p>{{ automatedDecision.approvalDecision.reason }}</p>
        </article>
        <article>
          <span>Probability</span>
          <strong>{{ automatedDecision.approvalDecision.probabilityScore }}%</strong>
          <p>{{ automatedDecision.approvalDecision.riskLevel }} risk</p>
        </article>
      </div>
    </section>

    <section class="process-dashboard">
      <header class="product-dashboard__header">
        <div>
          <p class="product-dashboard__eyebrow">Business Routing View</p>
          <h2>{{ automatedDecision.businessDecision.selectedBusinessPath }}</h2>
        </div>
        <strong>{{ automatedDecision.businessDecision.businessRoutingAI }}</strong>
      </header>

      <div class="process-grid">
        <article>
          <span>Workflow Path</span>
          <strong>{{ automatedDecision.workflowDecision.selectedPath.join(' -> ') }}</strong>
          <p>{{ automatedDecision.workflowDecision.pathStrategy }}</p>
        </article>
        <article>
          <span>Cost Path</span>
          <strong>{{ automatedDecision.businessDecision.cost.costPath }}</strong>
          <p>${{ Math.abs(automatedDecision.businessDecision.cost.expectedImpact).toLocaleString() }} impact</p>
        </article>
        <article>
          <span>Resource Decision</span>
          <strong>{{ automatedDecision.resourceDecision.allocationMode }}</strong>
          <p>{{ automatedDecision.resourceDecision.recommendation }}</p>
        </article>
      </div>
    </section>

    <section class="process-dashboard">
      <header class="product-dashboard__header">
        <div>
          <p class="product-dashboard__eyebrow">Risk Decision Panel</p>
          <h2>{{ automatedDecision.riskDecision.executionPath }}</h2>
        </div>
        <strong>{{ automatedDecision.riskDecision.action }}</strong>
      </header>

      <div class="process-grid">
        <article>
          <span>Risk Controller</span>
          <strong>{{ automatedDecision.riskDecision.riskDecisionControl }}</strong>
          <p>{{ automatedDecision.riskDecision.reason }}</p>
        </article>
        <article>
          <span>Execution Rule</span>
          <strong>{{ automatedDecision.policyDecisionResult.canAutoExecute ? 'AUTO_EXECUTE' : 'CONTROLLED_REVIEW' }}</strong>
          <p>{{ automatedDecision.policyDecisionResult.policy }}</p>
        </article>
      </div>
    </section>

    <section class="process-dashboard">
      <header class="product-dashboard__header">
        <div>
          <p class="product-dashboard__eyebrow">Full Autonomy Dashboard</p>
          <h2>Unattended enterprise operating system</h2>
        </div>
        <strong>{{ autonomousERP.fullAutonomyMode }}</strong>
      </header>

      <div class="process-grid">
        <article>
          <span>Auto Execution</span>
          <strong>{{ autonomousERP.autoExecution }}</strong>
          <p>{{ autonomousERP.execution.executionMode }}</p>
        </article>
        <article>
          <span>Zero Approval</span>
          <strong>{{ autonomousERP.zeroApproval }}</strong>
          <p>{{ autonomousERP.execution.zeroApproval.manualApproval }}</p>
        </article>
        <article>
          <span>Continuous Loop</span>
          <strong>{{ autonomousERP.continuousLoop }}</strong>
          <p>{{ autonomousERP.loop.businessCycle.cyclePolicy }}</p>
        </article>
        <article>
          <span>Unattended Mode</span>
          <strong>{{ autonomousERP.unattendedMode }}</strong>
          <p>{{ autonomousERP.execution.executionTrace.join(' / ') }}</p>
        </article>
      </div>
    </section>

    <section class="process-dashboard">
      <header class="product-dashboard__header">
        <div>
          <p class="product-dashboard__eyebrow">Execution Loop Monitor</p>
          <h2>Continuous ERP loop</h2>
        </div>
        <strong>{{ autonomousERP.loop.continuousLoop }}</strong>
      </header>

      <div class="process-grid">
        <article v-for="cycle in autonomousERP.loop.infiniteERP.cycles" :key="cycle.cycle">
          <span>Cycle #{{ cycle.cycle }}</span>
          <strong>{{ cycle.status }}</strong>
          <p>{{ cycle.workflowExecution }} / {{ cycle.eventProcessing }}</p>
        </article>
        <article>
          <span>Workflow Restart</span>
          <strong>{{ autonomousERP.loop.workflowRestart.autoWorkflowRestart }}</strong>
          <p>{{ autonomousERP.loop.workflowRestart.restartReason }}</p>
        </article>
      </div>
    </section>

    <section class="process-dashboard">
      <header class="product-dashboard__header">
        <div>
          <p class="product-dashboard__eyebrow">Self Healing Status Panel</p>
          <h2>Failure detection, rollback, repair</h2>
        </div>
        <strong>{{ autonomousERP.healing.selfHealing }}</strong>
      </header>

      <div class="process-grid">
        <article>
          <span>Failure Detection</span>
          <strong>{{ autonomousERP.healing.detectFailure.failureDetected ? 'DETECTED' : 'CLEAR' }}</strong>
          <p>{{ autonomousERP.healing.detectFailure.autonomousExecutionState }}</p>
        </article>
        <article>
          <span>Rollback</span>
          <strong>{{ autonomousERP.healing.rollback.rollbackTransaction }}</strong>
          <p>{{ autonomousERP.healing.rollback.reason }}</p>
        </article>
        <article>
          <span>Workflow Repair</span>
          <strong>{{ autonomousERP.healing.workflowState.repairWorkflowState }}</strong>
          <p>{{ autonomousERP.healing.consistency.consistent ? 'State consistent' : 'Repair required' }}</p>
        </article>
      </div>
    </section>
    </details>
  </div>
  <el-alert
    v-else
    :closable="false"
    show-icon
    type="error"
    title="V3 schema invalid"
    :description="schemaStatus.errors.join('; ')"
  />
</template>

<style scoped>
.meta-page-shell {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.meta-secondary-panels {
  border: 1px solid #d9e2ec;
  border-radius: 8px;
  background: #fff;
}

.meta-secondary-panels summary {
  cursor: pointer;
  padding: 12px 14px;
  color: #334155;
  font-weight: 700;
  user-select: none;
}

.meta-secondary-panels > section {
  margin: 0 14px 14px;
}

.autonomous-dashboard {
  border: 1px solid #d9e2ec;
  border-radius: 8px;
  background: #fff;
  padding: 16px;
}

.autonomous-dashboard__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.autonomous-dashboard__header h2 {
  margin: 0;
  color: #172033;
  font-size: 18px;
}

.autonomous-dashboard__header strong {
  color: #0f7b5f;
  font-size: 16px;
}

.autonomous-dashboard__eyebrow {
  margin: 0 0 4px;
  color: #667085;
  font-size: 12px;
}

.autonomous-dashboard__grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.autonomous-dashboard__grid article {
  min-height: 112px;
  border: 1px solid #e4e7ec;
  border-radius: 8px;
  padding: 12px;
  background: #f8fafc;
}

.autonomous-dashboard__grid span {
  display: block;
  color: #667085;
  font-size: 12px;
  line-height: 1.4;
}

.autonomous-dashboard__grid strong {
  display: block;
  margin: 8px 0;
  color: #101828;
  font-size: 16px;
}

.autonomous-dashboard__grid p {
  margin: 0;
  color: #475467;
  font-size: 13px;
  line-height: 1.5;
}

.product-dashboard {
  border: 1px solid #d9e2ec;
  border-radius: 8px;
  background: #fff;
  padding: 16px;
}

.process-dashboard {
  border: 1px solid #d9e2ec;
  border-radius: 8px;
  background: #fff;
  padding: 16px;
}

.product-dashboard__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.product-dashboard__header h2 {
  margin: 0;
  color: #172033;
  font-size: 18px;
}

.product-dashboard__header strong {
  color: #245bdb;
  font-size: 14px;
}

.product-dashboard__eyebrow {
  margin: 0 0 4px;
  color: #667085;
  font-size: 12px;
}

.product-dashboard__metrics,
.module-catalog,
.deployment-panel,
.process-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.architecture-viewer {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.product-dashboard article,
.process-dashboard article {
  min-height: 88px;
  border: 1px solid #e4e7ec;
  border-radius: 8px;
  padding: 12px;
  background: #f8fafc;
}

.product-dashboard article span,
.process-dashboard article span {
  display: block;
  color: #667085;
  font-size: 12px;
  line-height: 1.4;
}

.product-dashboard article strong,
.process-dashboard article strong {
  display: block;
  margin: 8px 0 0;
  color: #101828;
  font-size: 15px;
}

.product-dashboard article p,
.process-dashboard article p {
  margin: 8px 0 0;
  color: #475467;
  font-size: 13px;
  line-height: 1.5;
}

.timeline-list {
  display: grid;
  gap: 10px;
}

.timeline-list article {
  min-height: 76px;
}

@media (max-width: 960px) {
  .autonomous-dashboard__grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .product-dashboard__metrics,
  .module-catalog,
  .deployment-panel,
  .process-grid,
  .architecture-viewer {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 560px) {
  .autonomous-dashboard__header {
    align-items: flex-start;
    flex-direction: column;
  }

  .product-dashboard__header {
    align-items: flex-start;
    flex-direction: column;
  }

  .autonomous-dashboard__grid,
  .product-dashboard__metrics,
  .module-catalog,
  .deployment-panel,
  .process-grid,
  .architecture-viewer {
    grid-template-columns: 1fr;
  }
}
</style>
