<template>
  <section class="cockpit-shell">
    <aside class="sidebar">
      <section class="brand">
        <strong>ProfitOS</strong>
        <span>{{ t('Enterprise OS') }}</span>
      </section>

      <el-menu
        :default-active="activePath"
        class="cockpit-menu"
        @select="navigateMenu"
      >
        <el-menu-item
          v-for="item in navigation"
          :key="item.key"
          :index="item.path"
        >
          <el-icon>
            <component :is="getIcon(item.icon)" />
          </el-icon>
          <span>{{ t(item.label) }}</span>
        </el-menu-item>
      </el-menu>
    </aside>

    <section class="shell-main">
      <header class="system-bar">
        <section class="system-title">
          <p>{{ t('ProfitOS Cockpit') }}</p>
          <h1>{{ t(currentModule) }}</h1>
        </section>

        <section v-if="showCockpitDiagnostics" class="system-status">
          <el-tag type="success">{{ t('Tenant') }} {{ runtimeState.tenant.id }}</el-tag>
          <el-tag>{{ t('Role') }} {{ runtimeState.role }}</el-tag>
          <el-tag>{{ runtimeState.plan }}</el-tag>
          <el-tag :type="health.errorCount === 0 ? 'success' : 'danger'">
            {{ health.errorCount === 0 ? t('Healthy') : t('Attention') }}
          </el-tag>
          <el-button :icon="View" type="primary" plain @click="toggleTrace">
            {{ t('Trace') }}
          </el-button>
        </section>
      </header>

      <section v-if="showCockpitDiagnostics" class="diagnostics-area">
      <section class="kpi-strip">
        <article>
          <span>{{ t('System Health') }}</span>
          <strong>{{ health.errorCount === 0 ? t('Healthy') : t('Attention') }}</strong>
        </article>
        <article>
          <span>{{ t('Tenant') }}</span>
          <strong>{{ runtimeState.tenant.id }}</strong>
        </article>
        <article>
          <span>{{ t('Plan') }}</span>
          <strong>{{ runtimeState.plan }}</strong>
        </article>
        <article>
          <span>{{ t('OS Entries') }}</span>
          <strong>{{ navigation.length }}</strong>
        </article>
        <article>
          <span>{{ t('Billing Status') }}</span>
          <strong>{{ billing.plan }} / {{ formatCurrency(billing.cost) }}</strong>
        </article>
        <article>
          <span>{{ t('Execution Status') }}</span>
          <strong>{{ cockpitExecution.status }}</strong>
        </article>
        <article>
          <span>{{ t('Risk Status') }}</span>
          <strong>{{ t(reviewControl.controlMode || reviewControl.decision) }}</strong>
        </article>
      </section>

      <section class="orchestration-strip">
        <article>
          <span>{{ t('Process Interaction Heatmap') }}</span>
          <strong>{{ orchestrationDashboard.dependencyGraph.edges.length }} links</strong>
          <p>{{ orchestrationDashboard.dependencyGraph.edges.map((edge) => `${edge.from}->${edge.to}`).join(' / ') }}</p>
        </article>
        <article>
          <span>{{ t('Event Flow Timeline') }}</span>
          <strong>{{ orchestrationDashboard.eventStream.length }} events</strong>
          <p>{{ orchestrationDashboard.eventStream.slice(0, 3).map((event) => event.type).join(' / ') || '-' }}</p>
        </article>
        <article>
          <span>{{ t('Cross Process Dependency View') }}</span>
          <strong>{{ orchestrationDashboard.dependencyGraph.healthy ? t('Healthy') : 'CYCLE' }}</strong>
          <p>{{ orchestrationDashboard.triggers.rules.map((rule) => rule.description).join(' / ') }}</p>
        </article>
      </section>

      <section class="intelligence-strip">
        <article>
          <span>{{ t('Decision Accuracy Index') }}</span>
          <strong>{{ intelligenceDashboard.metrics.decisionAccuracyIndex }}</strong>
          <p>{{ intelligenceDashboard.latest?.decision?.decision || '-' }}</p>
        </article>
        <article>
          <span>{{ t('Strategy Efficiency Score') }}</span>
          <strong>{{ intelligenceDashboard.metrics.strategyEfficiencyScore }}</strong>
          <p>{{ intelligenceDashboard.latest?.strategy?.primary?.type || '-' }}</p>
        </article>
        <article>
          <span>{{ t('Risk Exposure Meter') }}</span>
          <strong>{{ intelligenceDashboard.metrics.riskExposureMeter }}</strong>
          <p>{{ intelligenceDashboard.latest?.risk?.level || '-' }}</p>
        </article>
        <article>
          <span>{{ t('Action Execution Rate') }}</span>
          <strong>{{ intelligenceDashboard.metrics.actionExecutionRate }}</strong>
          <p>{{ intelligenceDashboard.latest?.actionPlan?.steps?.length || 0 }} steps</p>
        </article>
      </section>

      <section class="enterprise-execution-strip">
        <article>
          <span>{{ t('Execution Success Rate') }}</span>
          <strong>{{ enterpriseExecutionDashboard.metrics.executionSuccessRate }}</strong>
          <p>{{ enterpriseExecutionDashboard.latest?.status || '-' }}</p>
        </article>
        <article>
          <span>{{ t('Autopilot Efficiency Index') }}</span>
          <strong>{{ enterpriseExecutionDashboard.metrics.autopilotEfficiencyIndex }}</strong>
          <p>{{ enterpriseExecutionDashboard.latest?.stateUpdates?.workflow?.completion?.status || '-' }}</p>
        </article>
        <article>
          <span>{{ t('Financial Automation Score') }}</span>
          <strong>{{ enterpriseExecutionDashboard.metrics.financialAutomationScore }}</strong>
          <p>{{ enterpriseExecutionDashboard.financialRecords.length }} records</p>
        </article>
        <article>
          <span>{{ t('Cross Process Execution Graph') }}</span>
          <strong>{{ enterpriseExecutionDashboard.metrics.crossModuleExecutionCount }}</strong>
          <p>{{ enterpriseExecutionDashboard.crossModuleExecutionGraph.slice(0, 3).map((edge) => `${edge.from}->${edge.to}`).join(' / ') || '-' }}</p>
        </article>
      </section>

      <section class="enterprise-autopilot-strip">
        <article>
          <span>{{ t('Autopilot Stability Index') }}</span>
          <strong>{{ enterpriseAutopilotDashboard.metrics.autopilotStabilityIndex }}</strong>
          <p>{{ enterpriseAutopilotDashboard.autopilotMode }}</p>
        </article>
        <article>
          <span>{{ t('Continuous Execution Rate') }}</span>
          <strong>{{ enterpriseAutopilotDashboard.metrics.continuousExecutionRate }}</strong>
          <p>{{ enterpriseAutopilotDashboard.continuous.history.length }} cycles</p>
        </article>
        <article>
          <span>{{ t('Self-Repair Success Rate') }}</span>
          <strong>{{ enterpriseAutopilotDashboard.metrics.selfRepairSuccessRate }}</strong>
          <p>{{ enterpriseAutopilotDashboard.repair.latest?.consistency?.state || 'STABLE' }}</p>
        </article>
        <article>
          <span>{{ t('Financial Autonomy Score') }}</span>
          <strong>{{ enterpriseAutopilotDashboard.metrics.financialAutonomyScore }}</strong>
          <p>{{ enterpriseAutopilotDashboard.finance.latest?.settlement?.status || '-' }}</p>
        </article>
      </section>

      <section class="enterprise-evolution-strip">
        <article>
          <span>{{ t('System Evolution Index') }}</span>
          <strong>{{ structuralEvolutionDashboard.metrics.systemEvolutionIndex }}</strong>
          <p>{{ structuralEvolutionDashboard.trace.length }} trace</p>
        </article>
        <article>
          <span>{{ t('Workflow Efficiency Growth') }}</span>
          <strong>{{ structuralEvolutionDashboard.metrics.workflowEfficiencyGrowth }}</strong>
          <p>{{ structuralEvolutionDashboard.latest.workflowChanges?.approvalRestructure?.approvalMode || '-' }}</p>
        </article>
        <article>
          <span>{{ t('Module Stability vs Flexibility Graph') }}</span>
          <strong>{{ structuralEvolutionDashboard.metrics.moduleStabilityFlexibility }}</strong>
          <p>{{ structuralEvolutionDashboard.latest.moduleChanges?.merges?.map((item) => item.group).join(' / ') || '-' }}</p>
        </article>
        <article>
          <span>{{ t('Behavioral Adaptation Score') }}</span>
          <strong>{{ structuralEvolutionDashboard.metrics.behavioralAdaptationScore }}</strong>
          <p>{{ structuralEvolutionDashboard.latest.behaviorChanges?.workflowBehavior?.behaviorMode || '-' }}</p>
        </article>
      </section>

      <section class="enterprise-stability-strip">
        <article>
          <span>{{ t('System Stability Index') }}</span>
          <strong>{{ stabilityBoundaryDashboard.metrics.systemStabilityIndex }}</strong>
          <p>{{ stabilityBoundaryDashboard.latest?.stabilityImpact || '-' }}</p>
        </article>
        <article>
          <span>{{ t('Evolution Risk Score') }}</span>
          <strong>{{ stabilityBoundaryDashboard.metrics.evolutionRiskScore }}</strong>
          <p>{{ stabilityBoundaryDashboard.latest?.safety?.risk?.level || '-' }}</p>
        </article>
        <article>
          <span>{{ t('Drift Level Indicator') }}</span>
          <strong>{{ stabilityBoundaryDashboard.metrics.driftLevel }}</strong>
          <p>{{ stabilityBoundaryDashboard.latest?.safety?.drift?.driftScore ?? 0 }} drift</p>
        </article>
        <article>
          <span>{{ t('Safe Evolution Status') }}</span>
          <strong>{{ stabilityBoundaryDashboard.metrics.safeEvolutionStatus }}</strong>
          <p>{{ stabilityBoundaryDashboard.metrics.allowedEvolutionRate }}%</p>
        </article>
      </section>

      <section class="production-finalization-strip">
        <article>
          <span>{{ t('Production Readiness Score') }}</span>
          <strong>{{ productionFinalizationDashboard.readiness.productionReadinessScore }}</strong>
          <p>{{ productionFinalizationDashboard.readiness.deploymentReady ? 'READY' : 'REVIEW' }}</p>
        </article>
        <article>
          <span>{{ t('System Freeze Status') }}</span>
          <strong>{{ productionFinalizationDashboard.frozen ? 'FROZEN' : 'OPEN' }}</strong>
          <p>{{ productionFinalizationDashboard.allowedChanges ? 'CHANGEABLE' : 'LOCKED' }}</p>
        </article>
        <article>
          <span>{{ t('Module Compliance Index') }}</span>
          <strong>{{ productionFinalizationDashboard.compliance.moduleComplianceIndex }}</strong>
          <p>{{ productionFinalizationDashboard.compliance.compliant ? 'COMPLIANT' : 'REVIEW' }}</p>
        </article>
        <article>
          <span>{{ t('Deployment Safety Level') }}</span>
          <strong>{{ productionFinalizationDashboard.deployment.deploymentSafetyLevel }}</strong>
          <p>{{ productionFinalizationDashboard.deployment.rollback.rollbackProtection }}</p>
        </article>
      </section>

      <section class="commercial-launch-strip">
        <article>
          <span>{{ t('Revenue Stream Monitor') }}</span>
          <strong>{{ formatCurrency(saasLaunchDashboard.billing.metrics.revenueStream) }}</strong>
          <p>{{ saasLaunchDashboard.billing.invoice.status }}</p>
        </article>
        <article>
          <span>{{ t('Tenant Growth Chart') }}</span>
          <strong>{{ saasLaunchDashboard.onboarding.metrics.activeTenants }}</strong>
          <p>{{ saasLaunchDashboard.onboarding.latest?.status || '-' }}</p>
        </article>
        <article>
          <span>{{ t('System Health Index') }}</span>
          <strong>{{ saasLaunchDashboard.monitoring.systemHealthIndex }}</strong>
          <p>{{ saasLaunchDashboard.monitoring.health.status }}</p>
        </article>
        <article>
          <span>{{ t('Deployment Stability Score') }}</span>
          <strong>{{ saasLaunchDashboard.deployment.metrics.deploymentStabilityScore }}</strong>
          <p>{{ saasLaunchDashboard.deployment.latest?.status || 'READY' }}</p>
        </article>
      </section>

      <section class="growth-os-strip">
        <article>
          <span>{{ t('Growth Rate Index') }}</span>
          <strong>{{ growthDashboard.metrics.growthRateIndex }}</strong>
          <p>{{ growthDashboard.growthMode }}</p>
        </article>
        <article>
          <span>{{ t('Funnel Conversion Rate') }}</span>
          <strong>{{ growthDashboard.metrics.funnelConversionRate }}%</strong>
          <p>{{ growthDashboard.acquisition.length }} campaigns</p>
        </article>
        <article>
          <span>{{ t('Retention Curve') }}</span>
          <strong>{{ growthDashboard.metrics.retentionCurve }}</strong>
          <p>DAU {{ growthDashboard.retention.dau }} / MAU {{ growthDashboard.retention.mau }}</p>
        </article>
        <article>
          <span>{{ t('Revenue Expansion Score') }}</span>
          <strong>{{ growthDashboard.metrics.revenueExpansionScore }}</strong>
          <p>{{ growthDashboard.revenueExpansionSnapshot.recommendation.recommendedPlan }}</p>
        </article>
        <article>
          <span>{{ t('Viral Coefficient Meter') }}</span>
          <strong>{{ growthDashboard.metrics.viralCoefficient }}</strong>
          <p>{{ growthDashboard.referral.edges.length }} edges</p>
        </article>
      </section>

      <section class="platform-expansion-strip">
        <article>
          <span>{{ t('Platform Revenue Overview') }}</span>
          <strong>{{ formatCurrency(platformExpansionDashboard.metrics.platformRevenue) }}</strong>
          <p>{{ platformExpansionDashboard.billing.productBills.length }} products</p>
        </article>
        <article>
          <span>{{ t('Product Distribution Heatmap') }}</span>
          <strong>{{ platformExpansionDashboard.metrics.productDistribution }}</strong>
          <p>{{ platformExpansionDashboard.activeProducts.map((product) => product.id).join(' / ') }}</p>
        </article>
        <article>
          <span>{{ t('Cross Product Usage Graph') }}</span>
          <strong>{{ platformExpansionDashboard.metrics.crossProductUsage }}</strong>
          <p>{{ platformExpansionDashboard.dataBridge.flows.map((flow) => `${flow.from}->${flow.to}`).join(' / ') }}</p>
        </article>
        <article>
          <span>{{ t('Marketplace Adoption Index') }}</span>
          <strong>{{ platformExpansionDashboard.metrics.marketplaceAdoptionIndex }}</strong>
          <p>{{ platformExpansionDashboard.marketplaceSnapshot.installed.length }} installed</p>
        </article>
      </section>

      <section class="ecosystem-os-strip">
        <article>
          <span>{{ t('Ecosystem Growth Index') }}</span>
          <strong>{{ ecosystemDashboard.metrics.ecosystemGrowthIndex }}</strong>
          <p>{{ ecosystemDashboard.pluginSystem }}</p>
        </article>
        <article>
          <span>{{ t('Plugin Adoption Rate') }}</span>
          <strong>{{ formatPercent(ecosystemDashboard.metrics.pluginAdoptionRate) }}</strong>
          <p>{{ ecosystemDashboard.installedModules.length }} installed</p>
        </article>
        <article>
          <span>{{ t('Marketplace Revenue Flow') }}</span>
          <strong>{{ formatCurrency(ecosystemDashboard.metrics.marketplaceRevenue) }}</strong>
          <p>{{ ecosystemDashboard.revenueSharing }}</p>
        </article>
        <article>
          <span>{{ t('Developer Activity Heatmap') }}</span>
          <strong>{{ ecosystemDashboard.metrics.developerActivityHeatmap }}</strong>
          <p>{{ Object.keys(ecosystemDashboard.developerActivity).join(' / ') || '-' }}</p>
        </article>
      </section>

      <section class="ecosystem-governance-strip">
        <article>
          <span>{{ t('Ecosystem Stability Index') }}</span>
          <strong>{{ ecosystemGovernanceDashboard.stabilityGovernance.ecosystemStabilityIndex }}</strong>
          <p>{{ ecosystemGovernanceDashboard.stabilityGovernance.balance }}</p>
        </article>
        <article>
          <span>{{ t('Plugin Quality Distribution') }}</span>
          <strong>{{ ecosystemGovernanceDashboard.quality.averageScore }}</strong>
          <p>{{ ecosystemGovernanceDashboard.pluginQuality.map((item) => `${item.pluginId}:${item.riskLevel}`).join(' / ') || '-' }}</p>
        </article>
        <article>
          <span>{{ t('Revenue Fairness Meter') }}</span>
          <strong>{{ ecosystemGovernanceDashboard.revenueGovernance.fairness.fairnessIndex }}</strong>
          <p>{{ ecosystemGovernanceDashboard.revenueGovernance.monopolyControl.antiMonopoly }}</p>
        </article>
        <article>
          <span>{{ t('Security Threat Radar') }}</span>
          <strong>{{ ecosystemGovernanceDashboard.securityGovernance.threatCount }}</strong>
          <p>{{ ecosystemGovernanceDashboard.securityGovernance.status }}</p>
        </article>
      </section>

      <section class="real-data-strip">
        <article>
          <span>{{ t('Real Data Flow Index') }}</span>
          <strong>{{ realDataDashboard.metrics.realDataFlowIndex }}</strong>
          <p>{{ realDataDashboard.database.tables.length }} tables</p>
        </article>
        <article>
          <span>{{ t('API Latency Monitor') }}</span>
          <strong>{{ realDataDashboard.metrics.apiLatency }}ms</strong>
          <p>{{ realDataDashboard.api.metrics.successCount }} ok / {{ realDataDashboard.api.metrics.errorCount }} err</p>
        </article>
        <article>
          <span>{{ t('Data Sync Health Score') }}</span>
          <strong>{{ realDataDashboard.metrics.dataSyncHealthScore }}</strong>
          <p>{{ realDataDashboard.sync.events.length }} sync events</p>
        </article>
      </section>

      <section class="production-runtime-strip">
        <article>
          <span>{{ t('Business Execution Rate') }}</span>
          <strong>{{ productionRuntimeDashboard.metrics.businessExecutionRate }}%</strong>
          <p>{{ productionRuntimeDashboard.business.executions.length }} executions</p>
        </article>
        <article>
          <span>{{ t('Transaction Success Index') }}</span>
          <strong>{{ productionRuntimeDashboard.metrics.transactionSuccessIndex }}%</strong>
          <p>{{ productionRuntimeDashboard.transaction.transactions.length }} transactions</p>
        </article>
        <article>
          <span>{{ t('Cross Module Sync Health') }}</span>
          <strong>{{ productionRuntimeDashboard.metrics.crossModuleSyncHealth }}</strong>
          <p>{{ productionRuntimeDashboard.eventStream.events.length }} events</p>
        </article>
        <article>
          <span>{{ t('Financial Posting Accuracy') }}</span>
          <strong>{{ productionRuntimeDashboard.metrics.financialPostingAccuracy }}%</strong>
          <p>{{ productionRuntimeDashboard.posting.postings.length }} postings</p>
        </article>
      </section>

      <details class="advanced-cockpit">
        <summary>{{ t('Advanced / Debug / Trace') }}</summary>

      <section
        v-if="industryDashboard"
        class="industry-kpi-strip"
      >
        <article>
          <span>{{ t('Industry') }}</span>
          <strong>{{ industryDashboard.industry }}</strong>
        </article>
        <article
          v-for="kpi in industryDashboard.kpis"
          :key="kpi"
        >
          <span>{{ kpi }}</span>
          <strong>{{ industryKpiValue(kpi) }}</strong>
        </article>
      </section>

      <section class="review-strip">
        <article>
          <span>{{ metricLabel('reviewCompliance') }}</span>
          <strong>{{ formatPercent(reviewStatus.complianceRate) }}</strong>
        </article>
        <article>
          <span>{{ metricLabel('featureCompletion') }}</span>
          <strong>{{ formatPercent(reviewStatus.completionRate) }}</strong>
        </article>
        <article class="module-compliance">
          <span>{{ metricLabel('moduleCompliance') }}</span>
          <div>
            <el-tag
              v-for="module in reviewStatus.moduleCompliance"
              :key="module.module"
              :type="module.status === 'PASSED' ? 'success' : 'warning'"
              size="small"
            >
              {{ module.module }} {{ formatPercent(module.complianceRate) }}
            </el-tag>
          </div>
        </article>
        <article>
          <span>{{ metricLabel('organization') }}</span>
          <strong>{{ reviewStatus.organization.departmentCount }} {{ t('Depts') }} / {{ reviewStatus.organization.employees.length }} {{ t('People') }}</strong>
        </article>
      </section>

      <section class="enterprise-review-strip">
        <article>
          <span>{{ metricLabel('erpCompliance') }}</span>
          <strong>{{ formatPercent(getScopeRate('ERP')) }}</strong>
        </article>
        <article>
          <span>{{ metricLabel('scmCompliance') }}</span>
          <strong>{{ formatPercent(getScopeRate('SCM')) }}</strong>
        </article>
        <article>
          <span>{{ metricLabel('mesExecution') }}</span>
          <strong>{{ formatPercent(getScopeRate('MES')) }}</strong>
        </article>
        <article>
          <span>{{ metricLabel('wmsInventory') }}</span>
          <strong>{{ formatPercent(getScopeRate('WMS')) }}</strong>
        </article>
        <article>
          <span>{{ metricLabel('crossSystemIntegrity') }}</span>
          <strong>{{ formatPercent(reviewStatus.systemEvaluation.crossModule.integrityRate) }}</strong>
        </article>
      </section>

      <section class="review-control-strip">
        <article>
          <span>{{ metricLabel('reviewDecision') }}</span>
          <strong>{{ t(reviewControl.controlMode || reviewControl.decision) }}</strong>
        </article>
        <article>
          <span>{{ metricLabel('restrictedModules') }}</span>
          <strong>{{ reviewControl.restrictedModules.length }}</strong>
        </article>
        <article>
          <span>{{ metricLabel('optimization') }}</span>
          <strong>{{ t(reviewControl.loadRebalance?.loadMode || 'READY') }}</strong>
        </article>
        <article>
          <span>{{ metricLabel('systemScore') }}</span>
          <strong>{{ reviewStatus.systemScores.systemHealthScore }}</strong>
        </article>
        <article>
          <span>{{ metricLabel('workflowState') }}</span>
          <strong>{{ t(workflowState) }}</strong>
        </article>
        <article>
          <span>{{ metricLabel('decisionScore') }}</span>
          <strong>{{ cockpitDecision.score }} / {{ cockpitDecision.recommendation }}</strong>
        </article>
        <article>
          <span>{{ metricLabel('executionStatus') }}</span>
          <strong>{{ cockpitExecution.status }}</strong>
        </article>
        <article>
          <span>{{ metricLabel('autonomousStatus') }}</span>
          <strong>{{ cockpitAutonomous.mode }} / L{{ cockpitAutonomous.autonomyLevel }}</strong>
        </article>
      </section>

      <section class="network-strip">
        <article>
          <span>{{ metricLabel('enterpriseGraph') }}</span>
          <strong>{{ networkDashboard.graph.nodes.length }} / {{ networkDashboard.graph.edges.length }}</strong>
        </article>
        <article>
          <span>{{ metricLabel('supplyHeatmap') }}</span>
          <strong>{{ networkDashboard.resourceExchange.inventoryTransfer }}</strong>
        </article>
        <article>
          <span>{{ metricLabel('competition') }}</span>
          <strong>{{ formatPercent(networkDashboard.competition.market[0]?.marketShare || 0) }}</strong>
        </article>
        <article>
          <span>{{ metricLabel('globalOptimization') }}</span>
          <strong>{{ networkDashboard.globalOptimization.networkEfficiency }}</strong>
        </article>
      </section>

      <section class="global-economy-strip">
        <article>
          <span>{{ metricLabel('globalHeatmap') }}</span>
          <strong>{{ globalEconomyDashboard.market.enterprises.length }} {{ t('Markets') }}</strong>
        </article>
        <article>
          <span>{{ metricLabel('economicTrend') }}</span>
          <strong>GDP {{ globalEconomyDashboard.macro.gdpTrend }}%</strong>
        </article>
        <article>
          <span>{{ metricLabel('currencyFlow') }}</span>
          <strong>{{ globalEconomyDashboard.market.currencyFlows.length }} FX</strong>
        </article>
        <article>
          <span>{{ metricLabel('worldSupplyChain') }}</span>
          <strong>{{ globalEconomyDashboard.supplyChain.productionShifting?.targetCountry || 'GLOBAL' }}</strong>
        </article>
      </section>

      <section class="civilization-strip">
        <article>
          <span>{{ metricLabel('civilizationHealth') }}</span>
          <strong>{{ civilizationDashboard.economy.civilizationKpi.civilizationHealthIndex }}/100</strong>
        </article>
        <article>
          <span>{{ metricLabel('societyStability') }}</span>
          <strong>{{ civilizationDashboard.society.stabilityIndex }}/100</strong>
        </article>
        <article>
          <span>{{ metricLabel('populationFlow') }}</span>
          <strong>{{ civilizationDashboard.population.laborAvailability }}</strong>
        </article>
        <article>
          <span>{{ metricLabel('policyImpact') }}</span>
          <strong>{{ civilizationDashboard.governance.stabilityControl }}/100</strong>
        </article>
      </section>

      <section class="human-strip">
        <article>
          <span>{{ metricLabel('humanDecision') }}</span>
          <strong>{{ humanDashboard.cognition.decisionIndex }}/100</strong>
        </article>
        <article>
          <span>{{ metricLabel('emotionalLoad') }}</span>
          <strong>{{ humanDashboard.emotion.emotionalLoad }}</strong>
        </article>
        <article>
          <span>{{ metricLabel('teamBehavior') }}</span>
          <strong>{{ humanDashboard.group.managementPattern }}</strong>
        </article>
        <article>
          <span>{{ metricLabel('humanDelay') }}</span>
          <strong>{{ humanDashboard.workflowImpact.predictedDelay ? t('Attention') : t('Ready') }}</strong>
        </article>
      </section>

      <section class="hybrid-strip">
        <article>
          <span>{{ metricLabel('hybridDecision') }}</span>
          <strong>{{ hybridDashboard.fused.confidence }}/100</strong>
        </article>
        <article>
          <span>{{ metricLabel('agreementRate') }}</span>
          <strong>{{ hybridDashboard.fused.agreement ? '100%' : '0%' }}</strong>
        </article>
        <article>
          <span>{{ metricLabel('trustEvolution') }}</span>
          <strong>H {{ hybridDashboard.trust.humanReliability }} / AI {{ hybridDashboard.trust.aiReliability }}</strong>
        </article>
        <article>
          <span>{{ metricLabel('sharedExecution') }}</span>
          <strong>{{ hybridDashboard.execution.sharedWorkflowState }}</strong>
        </article>
      </section>

      <section class="final-strip">
        <article>
          <span>{{ metricLabel('civilizationUnity') }}</span>
          <strong>{{ finalDashboard.intelligence.civilizationUnityIndex }}/100</strong>
        </article>
        <article>
          <span>{{ metricLabel('systemCoherence') }}</span>
          <strong>{{ finalDashboard.intelligence.systemCoherence }}/100</strong>
        </article>
        <article>
          <span>{{ metricLabel('realityStability') }}</span>
          <strong>{{ finalDashboard.reality.stabilityIndicator }}/100</strong>
        </article>
        <article>
          <span>{{ metricLabel('singleState') }}</span>
          <strong>{{ finalDashboard.unifiedState?.singleState?.decision || 'MONITOR' }}</strong>
        </article>
      </section>

      <section class="convergence-strip">
        <article>
          <span>{{ metricLabel('stabilityScore') }}</span>
          <strong>{{ convergenceDashboard.stabilityScore }}/100</strong>
        </article>
        <article>
          <span>{{ metricLabel('complexityMeter') }}</span>
          <strong>{{ convergenceDashboard.unifiedState?.complexity?.level || 'BOUNDED' }}</strong>
        </article>
        <article>
          <span>{{ metricLabel('conflictHeatmap') }}</span>
          <strong>D{{ convergenceDashboard.unifiedState?.conflictHeatmap?.decision || 0 }} E{{ convergenceDashboard.unifiedState?.conflictHeatmap?.execution || 0 }} H{{ convergenceDashboard.unifiedState?.conflictHeatmap?.humanAi || 0 }}</strong>
        </article>
        <article>
          <span>{{ metricLabel('runtimeGovernance') }}</span>
          <strong>{{ convergenceDashboard.convergenceRules.noNewCoreLayers ? 'LOCKED' : 'OPEN' }}</strong>
        </article>
      </section>

      <section class="freeze-strip">
        <article>
          <span>{{ metricLabel('freezeStatus') }}</span>
          <strong>{{ freezeDashboard.cockpitStatus }}</strong>
        </article>
        <article>
          <span>{{ metricLabel('complexityCeiling') }}</span>
          <strong>{{ freezeDashboard.complexityCap.maxWorkflowDepth }} / {{ freezeDashboard.executionLock.maxRecursionLoop }}</strong>
        </article>
        <article>
          <span>{{ metricLabel('determinismScore') }}</span>
          <strong>{{ freezeDashboard.deterministicRuntime.sameInputSameOutput ? '100%' : '0%' }}</strong>
        </article>
        <article>
          <span>{{ metricLabel('mutability') }}</span>
          <strong>{{ freezeDashboard.systemMutability }}</strong>
        </article>
      </section>

      <section class="product-strip">
        <article>
          <span>{{ metricLabel('productionReadiness') }}</span>
          <strong>{{ productDashboard.readinessScore }}/100</strong>
        </article>
        <article>
          <span>{{ metricLabel('moduleComplianceIndex') }}</span>
          <strong>{{ formatPercent(productDashboard.moduleComplianceIndex) }}</strong>
        </article>
        <article>
          <span>{{ metricLabel('apiStabilityMeter') }}</span>
          <strong>{{ formatPercent(productDashboard.apiStabilityMeter) }}</strong>
        </article>
        <article>
          <span>{{ metricLabel('saasPackage') }}</span>
          <strong>{{ productDashboard.modules.length }} modules</strong>
        </article>
      </section>

      <section class="saas-strip">
        <article>
          <span>{{ metricLabel('revenueDashboard') }}</span>
          <strong>${{ saasDashboard.billing.total }}</strong>
        </article>
        <article>
          <span>{{ metricLabel('tenantUsage') }}</span>
          <strong>{{ saasDashboard.quota.usage.apiCalls }} API</strong>
        </article>
        <article>
          <span>{{ metricLabel('subscriptionStatus') }}</span>
          <strong>{{ saasDashboard.plan }}</strong>
        </article>
        <article>
          <span>{{ metricLabel('moduleAdoption') }}</span>
          <strong>{{ formatPercent(saasDashboard.marketplace.adoption.rate) }}</strong>
        </article>
      </section>

      <section class="launch-strip">
        <article>
          <span>{{ metricLabel('liveRevenue') }}</span>
          <strong>${{ productionDashboard.liveRevenue }}</strong>
        </article>
        <article>
          <span>{{ metricLabel('tenantActivity') }}</span>
          <strong>{{ productionDashboard.activeTenants }} tenants</strong>
        </article>
        <article>
          <span>{{ metricLabel('systemHealthDashboard') }}</span>
          <strong>{{ productionDashboard.status }}</strong>
        </article>
        <article>
          <span>{{ metricLabel('moduleUsageHeatmap') }}</span>
          <strong>{{ productionDashboard.enabledModules }} modules</strong>
        </article>
      </section>

      <section class="growth-strip">
        <article>
          <span>{{ metricLabel('growthRate') }}</span>
          <strong>{{ formatPercent(growthDashboard.growthRate) }}</strong>
        </article>
        <article>
          <span>{{ metricLabel('activationFunnel') }}</span>
          <strong>{{ growthDashboard.activation.completed }}/{{ growthDashboard.activation.total }}</strong>
        </article>
        <article>
          <span>{{ metricLabel('churnRate') }}</span>
          <strong>{{ formatPercent(growthDashboard.churnRate) }}</strong>
        </article>
        <article>
          <span>{{ metricLabel('revenueExpansion') }}</span>
          <strong>${{ growthDashboard.revenue.expansionRevenue }}</strong>
        </article>
      </section>

      <section class="ecosystem-strip">
        <article>
          <span>{{ metricLabel('ecosystemGrowth') }}</span>
          <strong>{{ ecosystemDashboard.metrics.ecosystemGrowthIndex }}/100</strong>
        </article>
        <article>
          <span>{{ metricLabel('pluginAdoption') }}</span>
          <strong>{{ formatPercent(ecosystemDashboard.metrics.pluginAdoptionRate) }}</strong>
        </article>
        <article>
          <span>{{ metricLabel('marketplaceRevenue') }}</span>
          <strong>${{ ecosystemDashboard.metrics.marketplaceRevenue }}</strong>
        </article>
        <article>
          <span>{{ metricLabel('sandboxRuntime') }}</span>
          <strong>{{ ecosystemDashboard.sandboxRuntime }} / {{ ecosystemDashboard.sandboxEvents.length }}</strong>
        </article>
      </section>

      <section class="ecosystem-governance-strip">
        <article>
          <span>{{ metricLabel('ecosystemStability') }}</span>
          <strong>{{ ecosystemGovernanceDashboard.health.pluginStability }}/100</strong>
        </article>
        <article>
          <span>{{ metricLabel('pluginQualityDistribution') }}</span>
          <strong>{{ ecosystemGovernanceDashboard.quality.averageScore }}/100</strong>
        </article>
        <article>
          <span>{{ metricLabel('revenueFairnessMonitor') }}</span>
          <strong>{{ ecosystemGovernanceDashboard.revenueFairness.fairnessIndex }}/100</strong>
        </article>
        <article>
          <span>{{ metricLabel('securityThreatMap') }}</span>
          <strong>{{ ecosystemGovernanceDashboard.security.threatCount }} / {{ ecosystemGovernanceDashboard.decision }}</strong>
        </article>
      </section>

      <section class="ecosystem-autonomy-strip">
        <article>
          <span>{{ metricLabel('ecosystemAutonomy') }}</span>
          <strong>{{ autonomousEcosystemDashboard.metrics.autonomyIndex }}/100</strong>
        </article>
        <article>
          <span>{{ metricLabel('selfHealingRate') }}</span>
          <strong>{{ formatPercent(autonomousEcosystemDashboard.metrics.selfHealingRate) }}</strong>
        </article>
        <article>
          <span>{{ metricLabel('evolutionSpeed') }}</span>
          <strong>{{ autonomousEcosystemDashboard.metrics.evolutionSpeed }} changes</strong>
        </article>
        <article>
          <span>{{ metricLabel('predictionAccuracy') }}</span>
          <strong>{{ formatPercent(autonomousEcosystemDashboard.metrics.predictionAccuracy) }}</strong>
        </article>
      </section>

      <section class="business-autonomy-strip">
        <article>
          <span>{{ metricLabel('autonomousRevenue') }}</span>
          <strong>${{ autonomousBusinessDashboard.metrics.autonomousRevenue }}</strong>
        </article>
        <article>
          <span>{{ metricLabel('pricingAdjustment') }}</span>
          <strong>x{{ autonomousBusinessDashboard.metrics.pricingAdjustment }}</strong>
        </article>
        <article>
          <span>{{ metricLabel('productEvolutionTimeline') }}</span>
          <strong>{{ autonomousBusinessDashboard.metrics.productEvolutionSteps }} steps</strong>
        </article>
        <article>
          <span>{{ metricLabel('marketHeatControl') }}</span>
          <strong>{{ autonomousBusinessDashboard.metrics.marketHeat }} hot</strong>
        </article>
      </section>

      <section class="economy-strip">
        <article>
          <span>{{ metricLabel('economicStability') }}</span>
          <strong>{{ economyDashboard.metrics.economicStability }}/100</strong>
        </article>
        <article>
          <span>{{ metricLabel('pricingVolatility') }}</span>
          <strong>{{ formatPercent(economyDashboard.metrics.pricingVolatility) }}</strong>
        </article>
        <article>
          <span>{{ metricLabel('demandPressure') }}</span>
          <strong>{{ formatPercent(economyDashboard.metrics.demandPressure) }}</strong>
        </article>
        <article>
          <span>{{ metricLabel('profitMaximization') }}</span>
          <strong>{{ economyDashboard.metrics.profitMaximizationScore }}/100</strong>
        </article>
      </section>

      <section class="global-economic-strip-v25">
        <article>
          <span>{{ metricLabel('industryStability') }}</span>
          <strong>{{ globalEconomicSystemDashboard.metrics.industryStability }}/100</strong>
        </article>
        <article>
          <span>{{ metricLabel('crossEnterpriseInfluence') }}</span>
          <strong>{{ globalEconomicSystemDashboard.metrics.crossEnterpriseInfluence }}</strong>
        </article>
        <article>
          <span>{{ metricLabel('globalDemandCurve') }}</span>
          <strong>{{ globalEconomicSystemDashboard.metrics.globalDemand }}</strong>
        </article>
        <article>
          <span>{{ metricLabel('macroProfitEfficiency') }}</span>
          <strong>{{ globalEconomicSystemDashboard.metrics.macroProfitEfficiency }}/100</strong>
        </article>
      </section>

      <section class="world-economic-strip">
        <article>
          <span>{{ metricLabel('globalGdpHeatmap') }}</span>
          <strong>{{ worldEconomicDashboard.metrics.globalGDP }}</strong>
        </article>
        <article>
          <span>{{ metricLabel('currencyFlowMonitor') }}</span>
          <strong>{{ worldEconomicDashboard.metrics.currencyFlowCount }} FX</strong>
        </article>
        <article>
          <span>{{ metricLabel('supplyChainWorldGraph') }}</span>
          <strong>{{ worldEconomicDashboard.metrics.supplyChainNodes }} lanes</strong>
        </article>
        <article>
          <span>{{ metricLabel('macroStabilityIndex') }}</span>
          <strong>{{ worldEconomicDashboard.metrics.macroStability }}/100</strong>
        </article>
      </section>

      <section class="civilization-unified-strip">
        <article>
          <span>{{ metricLabel('civilizationStabilityIndex') }}</span>
          <strong>{{ digitalCivilizationDashboard.metrics.civilizationStability }}/100</strong>
        </article>
        <article>
          <span>{{ metricLabel('crossLayerDependency') }}</span>
          <strong>{{ digitalCivilizationDashboard.metrics.dependencyEdges }}</strong>
        </article>
        <article>
          <span>{{ metricLabel('policyImpactSimulator') }}</span>
          <strong>{{ digitalCivilizationDashboard.metrics.policyImpact }}/100</strong>
        </article>
        <article>
          <span>{{ metricLabel('globalSystemHealth') }}</span>
          <strong>{{ digitalCivilizationDashboard.metrics.globalSystemHealth }}/100</strong>
        </article>
      </section>

      <section class="reality-control-strip">
        <article>
          <span>{{ metricLabel('realityImpact') }}</span>
          <strong>{{ realityDashboard.metrics.realityImpactIndex }}/100</strong>
        </article>
        <article>
          <span>{{ metricLabel('behaviorChangeHeatmap') }}</span>
          <strong>{{ formatPercent(realityDashboard.metrics.behaviorChangeHeat) }}</strong>
        </article>
        <article>
          <span>{{ metricLabel('workflowExecutionInfluence') }}</span>
          <strong>{{ realityDashboard.metrics.workflowInfluenceScore }}/100</strong>
        </article>
        <article>
          <span>{{ metricLabel('realtimeFeedbackMonitor') }}</span>
          <strong>{{ realityDashboard.metrics.realtimeFeedback }}</strong>
        </article>
      </section>

      <section class="autonomous-governance-strip">
        <article>
          <span>{{ metricLabel('governanceEfficiency') }}</span>
          <strong>{{ governanceDashboard.metrics.governanceEfficiencyIndex }}/100</strong>
        </article>
        <article>
          <span>{{ metricLabel('workflowOptimizationScore') }}</span>
          <strong>{{ governanceDashboard.metrics.workflowOptimizationScore }}/100</strong>
        </article>
        <article>
          <span>{{ metricLabel('riskInterventionRate') }}</span>
          <strong>{{ formatPercent(governanceDashboard.metrics.riskInterventionRate) }}</strong>
        </article>
        <article>
          <span>{{ metricLabel('autopilotStability') }}</span>
          <strong>{{ governanceDashboard.metrics.autopilotStability }}/100</strong>
        </article>
      </section>

      <section class="full-autonomy-strip">
        <article>
          <span>{{ metricLabel('enterpriseAutonomyIndex') }}</span>
          <strong>{{ fullAutonomyDashboard.metrics.enterpriseAutonomyIndex }}/100</strong>
        </article>
        <article>
          <span>{{ metricLabel('workflowAutopilotStatus') }}</span>
          <strong>{{ fullAutonomyDashboard.metrics.workflowAutopilotStatus }}</strong>
        </article>
        <article>
          <span>{{ metricLabel('financialExecutionMonitor') }}</span>
          <strong>${{ fullAutonomyDashboard.metrics.financialExecutionValue }}</strong>
        </article>
        <article>
          <span>{{ metricLabel('systemSelfOptimizationRate') }}</span>
          <strong>{{ formatPercent(fullAutonomyDashboard.metrics.systemSelfOptimizationRate) }}</strong>
        </article>
      </section>

      </details>
      </section>

      <section class="workspace">
        <router-view />
      </section>
    </section>

    <aside v-if="traceOpen" class="trace-panel">
      <header>
        <h2>{{ t('Runtime Trace') }}</h2>
        <el-button :icon="Close" circle text @click="toggleTrace" />
      </header>

      <section class="trace-status">
        <div>
          <span>ProfitOS</span>
          <strong>{{ traceState.mode }}</strong>
        </div>
        <div>
          <span>{{ t('System') }}</span>
          <strong>{{ t(traceState.health) }}</strong>
        </div>
      </section>

      <pre>{{ traceOutput }}</pre>
    </aside>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Box,
  Close,
  Cpu,
  DataBoard,
  Monitor,
  Tickets,
  TrendCharts,
  UserFilled,
  View,
} from '@element-plus/icons-vue'
import { calculateBill } from '../billing/billingEngine.js'
import { getSystemHealth } from '../core/monitoringLayer.js'
import { getDemoOrder } from '../demo/demoMode.js'
import { getCockpitNavigation } from '../navigation/cockpitRegistry.js'
import { getLatestIndustryModel } from '../ai/industryModelEngine.js'
import { evaluateDecision } from '../ai/decisionEngine.js'
import { getExecutionHistory, getExecutionStatus } from '../ai/executionEngine.js'
import { getAutonomousHistory, getAutonomousStatus } from '../ai/selfDrivingEngine.js'
import { createDefaultEnterpriseNetwork } from '../network/enterpriseGraphEngine.js'
import { optimizeEnterpriseNetwork } from '../network/globalOptimizationEngine.js'
import { simulateGlobalEconomy } from '../global/globalEconomicBrain.js'
import { simulateCivilization } from '../civilization/civilizationSimulationEngine.js'
import { simulateHumanBehavior } from '../human/humanBehaviorOS.js'
import { hybridDecision } from '../hybrid/hybridDecisionEngine.js'
import { runCivilizationCore } from '../final/unifiedCivilizationCore.js'
import { convergeSystem } from '../convergence/systemConvergenceEngine.js'
import { lockSystem } from '../freeze/systemLockManager.js'
import { standardizeModules } from '../product/moduleStandardizer.js'
import { getAllSchemas } from '../core/schemaRegistry.js'
import { runSaasRuntime } from '../saas/saasRuntime.js'
import { getProductionHealth } from '../saas/monitoring/productionMonitor.js'
import { runGrowthRuntime } from '../growth/growthRuntime.js'
import { runEcosystemRuntime } from '../ecosystem/ecosystemRuntime.js'
import { runEcosystemGovernance } from '../ecosystem/governance/governanceRuntime.js'
import { runAutonomousEcosystem } from '../ecosystem/autonomous/autonomousRuntime.js'
import { runAutonomousBusiness } from '../business/businessAutonomyRuntime.js'
import { computeEconomicState } from '../economy/economicDynamicsEngine.js'
import { runGlobalEconomicSystem } from '../global/globalEconomicRuntime.js'
import { runWorldEconomicSystem } from '../world/worldEconomicRuntime.js'
import { processRealWorldFeedback } from '../reality/realityFeedbackEngine.js'
import { governEnterprise } from '../governance/autonomousGovernanceEngine.js'
import { runAutonomousEnterprise } from '../autonomy/fullBusinessAutopilotEngine.js'
import { getReviewControlState, runReviewControlLoop } from '../review/reviewControlEngine.js'
import { generateReviewStatus } from '../review/reviewExecutionEngine.js'
import { dataGateway } from '../runtime/dataGateway.js'
import { translate } from '../runtime/i18nEngine.js'
import { canAccessModule, canPerformAction, getAccessibleNavigation, hasPlanAccess } from '../runtime/permissionEngine.js'
import { stateManager } from '../runtime/stateManager.js'
import { getOrchestrationSnapshot } from '../orchestration/autoWorkflowConnector.js'
import { getIntelligenceSnapshot } from '../intelligence/decisionEngine.js'
import { getExecutionLayerSnapshot } from '../execution/executionEngine.js'
import { getEnterpriseAutopilotSnapshot } from '../autonomy/businessOrchestrator.js'
import { getStructuralEvolutionSnapshot } from '../evolution/structuralEvolutionEngine.js'
import { getStabilityBoundarySnapshot } from '../stability/evolutionBoundaryController.js'
import { getProductionFinalizationSnapshot } from '../production/systemFreezeManager.js'
import { getTenantOnboardingSnapshot } from '../saas/onboarding/tenantOnboardingEngine.js'
import { getCommercialBillingSnapshot } from '../saas/billing/billingEngine.js'
import { getMonitoringCenterSnapshot } from '../saas/monitoring/productionMonitor.js'
import { getDeploymentPipelineSnapshot } from '../deployment/deploymentPipeline.js'
import { getPlatformRuntimeSnapshot } from '../platform/multiProductRuntimeEngine.js'
import { getApiConnectorSnapshot } from '../data/apiConnector.js'
import { getDatabaseLayerSnapshot } from '../data/databaseLayer.js'
import { getDataSyncSnapshot } from '../data/syncEngine.js'
import { getBusinessRuntimeSnapshot } from '../runtime/businessRuntimeEngine.js'
import { getTransactionRuntimeSnapshot } from '../runtime/transactionEngine.js'
import { getEnterpriseEventStreamSnapshot } from '../runtime/enterpriseEventStream.js'
import { getFinancialPostingSnapshot } from '../runtime/financialPostingEngine.js'
import { runProfitOS } from '../profitOS.js'

const route = useRoute()
const router = useRouter()
const runtimeState = ref(stateManager.snapshot())
const controlTick = ref(0)
const navigation = computed(() => {
  controlTick.value
  return getAccessibleNavigation(getCockpitNavigation(), runtimeState.value)
})
const traceOpen = ref(false)
const health = ref(getSystemHealth())
const traceOutput = ref('')
const traceState = ref({
  mode: 'READY',
  health: 'READY',
})
const reviewStatus = ref(generateReviewStatus())
const reviewControl = ref(getReviewControlState())
const orchestrationDashboard = computed(() => {
  controlTick.value
  return getOrchestrationSnapshot()
})
const intelligenceDashboard = computed(() => {
  controlTick.value
  return getIntelligenceSnapshot()
})
const enterpriseExecutionDashboard = computed(() => {
  controlTick.value
  return getExecutionLayerSnapshot()
})
const enterpriseAutopilotDashboard = computed(() => {
  controlTick.value
  return getEnterpriseAutopilotSnapshot()
})
const structuralEvolutionDashboard = computed(() => {
  controlTick.value
  return getStructuralEvolutionSnapshot()
})
const stabilityBoundaryDashboard = computed(() => {
  controlTick.value
  return getStabilityBoundarySnapshot()
})
const productionFinalizationDashboard = computed(() => {
  controlTick.value
  return getProductionFinalizationSnapshot()
})
const saasLaunchDashboard = computed(() => {
  controlTick.value
  const onboarding = getTenantOnboardingSnapshot()
  return {
    onboarding,
    billing: getCommercialBillingSnapshot({
      tenantId: onboarding.latest?.tenantId || 'commercial_demo',
      plan: onboarding.latest?.tenant?.plan || 'enterprise',
      enabledModules: onboarding.latest?.modules?.enabledModules || [],
    }),
    monitoring: getMonitoringCenterSnapshot(),
    deployment: getDeploymentPipelineSnapshot(),
  }
})
const platformExpansionDashboard = computed(() => {
  controlTick.value
  return getPlatformRuntimeSnapshot()
})
const realDataDashboard = computed(() => {
  controlTick.value
  const api = getApiConnectorSnapshot()
  const database = getDatabaseLayerSnapshot()
  const sync = getDataSyncSnapshot()
  return {
    api,
    database,
    sync,
    metrics: {
      realDataFlowIndex: Math.min(100, 70 + (database.tables.length * 5) + Math.min(sync.events.length, 5) * 3),
      apiLatency: api.metrics.apiLatency,
      dataSyncHealthScore: sync.healthScore,
    },
  }
})
const productionRuntimeDashboard = computed(() => {
  controlTick.value
  const business = getBusinessRuntimeSnapshot()
  const transaction = getTransactionRuntimeSnapshot()
  const eventStream = getEnterpriseEventStreamSnapshot()
  const posting = getFinancialPostingSnapshot()
  return {
    business,
    transaction,
    eventStream,
    posting,
    metrics: {
      businessExecutionRate: business.businessExecutionRate,
      transactionSuccessIndex: transaction.successIndex,
      crossModuleSyncHealth: eventStream.consistency.consistency === 'CONSISTENT' ? 100 : 80,
      financialPostingAccuracy: posting.accuracy,
    },
  }
})
const industryTick = ref(0)
const executionTick = ref(0)
const autonomousTick = ref(0)
const networkTick = ref(0)
const globalTick = ref(0)
const civilizationTick = ref(0)
const humanTick = ref(0)
const hybridTick = ref(0)
const finalTick = ref(0)
const convergenceTick = ref(0)
const freezeTick = ref(0)
const productTick = ref(0)
const saasTick = ref(0)

const order = ref(getDemoOrder())

const result = ref(runProfitOS(
  { goal: 'optimize procurement system' },
  {
    tenantId: runtimeState.value.tenant.id,
    tenantConfig: {
      plan: runtimeState.value.plan,
    },
    data: order.value,
  }
))

const billing = computed(() => calculateBill(
  {
    id: runtimeState.value.tenant.id,
    plan: runtimeState.value.plan,
  },
  {
    requests: 1,
  }
))

const iconMap = {
  Box,
  Cpu,
  DataBoard,
  Monitor,
  Tickets,
  TrendCharts,
  UserFilled,
}

const cockpitMetricSchema = {
  profitKpi: { label: 'Profit KPI' },
  margin: { label: 'Margin' },
  billing: { label: 'Billing' },
  agentStatus: { label: 'Agent Status' },
  reviewCompliance: { label: 'Review Compliance' },
  featureCompletion: { label: 'Feature Completion' },
  moduleCompliance: { label: 'Module Compliance' },
  organization: { label: 'Organization' },
  erpCompliance: { label: 'ERP Compliance' },
  scmCompliance: { label: 'SCM Compliance' },
  mesExecution: { label: 'MES Execution' },
  wmsInventory: { label: 'WMS Inventory' },
  crossSystemIntegrity: { label: 'Cross-System Integrity' },
  reviewDecision: { label: 'Review Decision' },
  restrictedModules: { label: 'Restricted Modules' },
  optimization: { label: 'Optimization' },
  systemScore: { label: 'System Score' },
  workflowState: { label: 'Workflow State' },
  decisionScore: { label: 'Decision Score' },
  executionStatus: { label: 'Execution Status' },
  autonomousStatus: { label: 'Autonomous Status' },
  enterpriseGraph: { label: 'Enterprise Network Graph' },
  supplyHeatmap: { label: 'Supply Chain Heatmap' },
  competition: { label: 'Competition Simulation' },
  globalOptimization: { label: 'Global Optimization' },
  globalHeatmap: { label: 'Global Heatmap' },
  economicTrend: { label: 'Economic Trend Chart' },
  currencyFlow: { label: 'Currency Flow Monitor' },
  worldSupplyChain: { label: 'Supply Chain World Map' },
  civilizationHealth: { label: 'Civilization Health Index' },
  societyStability: { label: 'Society Stability Meter' },
  populationFlow: { label: 'Population Flow Map' },
  policyImpact: { label: 'Policy Impact Simulator' },
  humanDecision: { label: 'Human Decision Index' },
  emotionalLoad: { label: 'Emotional Load Indicator' },
  teamBehavior: { label: 'Team Behavior Map' },
  humanDelay: { label: 'Human Delay Risk' },
  hybridDecision: { label: 'Hybrid Decision Index' },
  agreementRate: { label: 'Human vs AI Agreement Rate' },
  trustEvolution: { label: 'Trust Evolution Chart' },
  sharedExecution: { label: 'Shared Execution Timeline' },
  civilizationUnity: { label: 'Civilization Unity Index' },
  systemCoherence: { label: 'System Coherence Meter' },
  realityStability: { label: 'Reality Stability Indicator' },
  singleState: { label: 'Unified System State' },
  stabilityScore: { label: 'Stability Score' },
  complexityMeter: { label: 'System Complexity Meter' },
  conflictHeatmap: { label: 'Conflict Heatmap' },
  runtimeGovernance: { label: 'Runtime Governance Lock' },
  freezeStatus: { label: 'System Freeze Status' },
  complexityCeiling: { label: 'Complexity Ceiling Meter' },
  determinismScore: { label: 'Execution Determinism Score' },
  mutability: { label: 'System Mutability' },
  productionReadiness: { label: 'System Production Readiness Score' },
  moduleComplianceIndex: { label: 'Module Compliance Index' },
  apiStabilityMeter: { label: 'API Stability Meter' },
  saasPackage: { label: 'SaaS Module Package' },
  revenueDashboard: { label: 'Revenue Dashboard' },
  tenantUsage: { label: 'Tenant Usage Heatmap' },
  subscriptionStatus: { label: 'Subscription Status Panel' },
  moduleAdoption: { label: 'Module Adoption Rate' },
  liveRevenue: { label: 'Live Revenue Stream' },
  tenantActivity: { label: 'Tenant Activity Monitor' },
  systemHealthDashboard: { label: 'System Health Dashboard' },
  moduleUsageHeatmap: { label: 'Module Usage Heatmap' },
  growthRate: { label: 'Growth Rate Panel' },
  activationFunnel: { label: 'User Activation Funnel' },
  churnRate: { label: 'Churn Rate Monitor' },
  revenueExpansion: { label: 'Revenue Expansion Tracker' },
  ecosystemGrowth: { label: 'Ecosystem Growth Index' },
  pluginAdoption: { label: 'Plugin Adoption Rate' },
  marketplaceRevenue: { label: 'Marketplace Revenue Flow' },
  sandboxRuntime: { label: 'Sandbox Runtime' },
  ecosystemStability: { label: 'Ecosystem Stability Index' },
  pluginQualityDistribution: { label: 'Plugin Quality Distribution' },
  revenueFairnessMonitor: { label: 'Revenue Fairness Monitor' },
  securityThreatMap: { label: 'Security Threat Map' },
  ecosystemAutonomy: { label: 'Ecosystem Autonomy Index' },
  selfHealingRate: { label: 'System Self-Healing Rate' },
  evolutionSpeed: { label: 'Evolution Speed Meter' },
  predictionAccuracy: { label: 'Prediction Accuracy Panel' },
  autonomousRevenue: { label: 'Autonomous Revenue Graph' },
  pricingAdjustment: { label: 'Pricing Adjustment Monitor' },
  productEvolutionTimeline: { label: 'Product Evolution Timeline' },
  marketHeatControl: { label: 'Market Heat Control' },
  economicStability: { label: 'Economic Stability Index' },
  pricingVolatility: { label: 'Pricing Volatility Meter' },
  demandPressure: { label: 'Demand Pressure Graph' },
  profitMaximization: { label: 'Profit Maximization Score' },
  industryStability: { label: 'Industry Stability Index' },
  crossEnterpriseInfluence: { label: 'Cross Enterprise Influence Map' },
  globalDemandCurve: { label: 'Global Demand Curve' },
  macroProfitEfficiency: { label: 'Macro Profit Efficiency Score' },
  globalGdpHeatmap: { label: 'Global GDP Heatmap' },
  currencyFlowMonitor: { label: 'Currency Flow Monitor' },
  supplyChainWorldGraph: { label: 'Supply Chain World Graph' },
  macroStabilityIndex: { label: 'Macro Stability Index' },
  civilizationStabilityIndex: { label: 'Civilization Stability Index' },
  crossLayerDependency: { label: 'Cross Layer Dependency Graph' },
  policyImpactSimulator: { label: 'Policy Impact Simulator' },
  globalSystemHealth: { label: 'Global System Health Meter' },
  realityImpact: { label: 'Reality Impact Index' },
  behaviorChangeHeatmap: { label: 'Behavior Change Heatmap' },
  workflowExecutionInfluence: { label: 'Workflow Execution Influence Score' },
  realtimeFeedbackMonitor: { label: 'Real-Time Feedback Monitor' },
  governanceEfficiency: { label: 'Governance Efficiency Index' },
  workflowOptimizationScore: { label: 'Workflow Optimization Score' },
  riskInterventionRate: { label: 'Risk Intervention Rate' },
  autopilotStability: { label: 'Autopilot Stability Meter' },
  enterpriseAutonomyIndex: { label: 'Enterprise Autonomy Index' },
  workflowAutopilotStatus: { label: 'Workflow Autopilot Status' },
  financialExecutionMonitor: { label: 'Financial Execution Monitor' },
  systemSelfOptimizationRate: { label: 'System Self-Optimization Rate' },
}

const activePath = computed(() => {
  if (route.path.startsWith('/purchase/order')) return '/purchase/order'
  return route.path
})
const showCockpitDiagnostics = computed(() => (
  route.path === '/dashboard' || route.path === '/analytics'
))

const currentModule = computed(() => {
  const current = navigation.value.find((item) => item.path === activePath.value)
  return current?.label || 'Dashboard'
})

function normalizeMenuPath(path = '') {
  const value = String(path || '')
  const hashIndex = value.indexOf('#/')
  const withoutHash = hashIndex >= 0 ? value.slice(hashIndex + 1) : value

  return withoutHash.startsWith('/') ? withoutHash : `/${withoutHash}`
}

function navigateMenu(index) {
  const target = normalizeMenuPath(index)

  if (target && target !== route.path) {
    router.push(target)
  }
}

const profitKpi = computed(() => result.value.business.decision)
const workflowState = computed(() => order.value.workflow_state || 'DRAFT')
const agentStatus = computed(() => (
  result.value.agent.execution.results.some((item) => item.status === 'BLOCKED')
    ? 'Review'
    : 'Ready'
))
const canExecute = computed(() => canPerformAction(runtimeState.value.role, 'EXECUTE'))
const cockpitDecision = computed(() => evaluateDecision({
  schema: {
    name: 'purchaseOrder',
    api: {
      module: 'purchaseOrder',
    },
  },
  record: order.value,
  rows: [order.value],
  action: 'APPROVE',
  runtimeState: runtimeState.value,
}))
const cockpitExecution = computed(() => {
  executionTick.value
  const status = getExecutionStatus()
  const history = getExecutionHistory()

  return {
    status: status.status || 'IDLE',
    last: history[history.length - 1],
  }
})
const cockpitAutonomous = computed(() => {
  autonomousTick.value
  const status = getAutonomousStatus()
  const history = getAutonomousHistory()

  return {
    mode: status.mode || 'IDLE',
    autonomyLevel: status.autonomyLevel || 4,
    last: history[history.length - 1],
  }
})
const networkDashboard = computed(() => {
  networkTick.value
  return optimizeEnterpriseNetwork(createDefaultEnterpriseNetwork(), {
    runtimeState: runtimeState.value,
  })
})
const globalEconomyDashboard = computed(() => {
  globalTick.value
  return simulateGlobalEconomy({
    enterprises: createDefaultEnterpriseNetwork(),
    runtimeState: runtimeState.value,
    network: networkDashboard.value,
  })
})
const civilizationDashboard = computed(() => {
  civilizationTick.value
  return simulateCivilization({
    globalEconomy: globalEconomyDashboard.value,
    economy: globalEconomyDashboard.value,
    runtimeState: runtimeState.value,
  })
})
const humanDashboard = computed(() => {
  humanTick.value
  return simulateHumanBehavior({
    civilization: civilizationDashboard.value,
    decision: cockpitDecision.value,
    record: order.value,
    kpiPressure: 62,
    rewardStrength: runtimeState.value.plan === 'enterprise' ? 72 : 55,
  })
})
const hybridDashboard = computed(() => {
  hybridTick.value
  return hybridDecision({
    schema: {
      name: 'purchaseOrder',
      api: {
        module: 'purchaseOrder',
      },
    },
    record: order.value,
    action: 'APPROVE',
    human: humanDashboard.value,
    ai: cockpitDecision.value,
    civilization: civilizationDashboard.value,
    runtimeState: runtimeState.value,
  })
})
const finalDashboard = computed(() => {
  finalTick.value
  return runCivilizationCore({
    schema: {
      name: 'purchaseOrder',
      api: {
        module: 'purchaseOrder',
      },
    },
    record: order.value,
    action: 'APPROVE',
    network: networkDashboard.value,
    globalEconomy: globalEconomyDashboard.value,
    civilization: civilizationDashboard.value,
    human: humanDashboard.value,
    hybrid: hybridDashboard.value,
    runtimeState: runtimeState.value,
  })
})
const convergenceDashboard = computed(() => {
  convergenceTick.value
  return convergeSystem({
    final: finalDashboard.value,
    hybrid: hybridDashboard.value,
    human: humanDashboard.value,
    civilization: civilizationDashboard.value,
    globalEconomy: globalEconomyDashboard.value,
    network: networkDashboard.value,
    decision: cockpitDecision.value,
    executionStatus: cockpitExecution.value,
    autonomousStatus: cockpitAutonomous.value,
  })
})
const freezeDashboard = computed(() => {
  freezeTick.value
  return lockSystem(convergenceDashboard.value)
})
const productDashboard = computed(() => {
  productTick.value
  return standardizeModules(getAllSchemas(), {
    convergence: convergenceDashboard.value,
    environment: 'production',
    runtimeState: runtimeState.value,
  })
})
const saasDashboard = computed(() => {
  saasTick.value
  return runSaasRuntime({
    tenantId: runtimeState.value.tenant.id,
    tenant: runtimeState.value.tenant,
    plan: runtimeState.value.plan,
    role: runtimeState.value.role,
    runtimeState: runtimeState.value,
  })
})
const productionDashboard = computed(() => {
  saasTick.value
  const monitor = getProductionHealth()

  return {
    liveRevenue: saasDashboard.value.billing.total,
    activeTenants: monitor.tenantLoad.activeTenants,
    status: monitor.status,
    enabledModules: saasDashboard.value.marketplace.enabledModules.length,
    monitor,
  }
})
const growthDashboard = computed(() => {
  saasTick.value
  return runGrowthRuntime({
    tenantId: runtimeState.value.tenant.id,
    tenant: runtimeState.value.tenant,
    module: 'dashboard',
    runtimeState: runtimeState.value,
  })
})
const ecosystemDashboard = computed(() => {
  saasTick.value
  return runEcosystemRuntime({
    tenantId: runtimeState.value.tenant.id,
    tenant: runtimeState.value.tenant,
    runtimeState: runtimeState.value,
  })
})
const ecosystemGovernanceDashboard = computed(() => {
  saasTick.value
  return runEcosystemGovernance({
    tenantId: runtimeState.value.tenant.id,
    tenant: runtimeState.value.tenant,
    runtimeState: runtimeState.value,
  })
})
const autonomousEcosystemDashboard = computed(() => {
  saasTick.value
  return runAutonomousEcosystem({
    tenantId: runtimeState.value.tenant.id,
    tenant: runtimeState.value.tenant,
    runtimeState: runtimeState.value,
  })
})
const autonomousBusinessDashboard = computed(() => {
  saasTick.value
  return runAutonomousBusiness({
    tenantId: runtimeState.value.tenant.id,
    tenant: runtimeState.value.tenant,
    plan: runtimeState.value.plan,
    runtimeState: runtimeState.value,
  })
})
const economyDashboard = computed(() => {
  saasTick.value
  return computeEconomicState({
    tenantId: runtimeState.value.tenant.id,
    tenant: runtimeState.value.tenant,
    plan: runtimeState.value.plan,
    runtimeState: runtimeState.value,
    data: order.value,
  })
})
const globalEconomicSystemDashboard = computed(() => {
  saasTick.value
  return runGlobalEconomicSystem({
    runtimeState: runtimeState.value,
  })
})
const worldEconomicDashboard = computed(() => {
  saasTick.value
  return runWorldEconomicSystem({
    runtimeState: runtimeState.value,
  })
})
const digitalCivilizationDashboard = computed(() => {
  saasTick.value
  const globalEconomic = globalEconomicSystemDashboard.value
  const worldEconomic = worldEconomicDashboard.value
  const civilizationStability = Math.round(
    (globalEconomic.metrics.macroProfitEfficiency + worldEconomic.metrics.macroStability) / 2
  )
  const dependencyEdges = globalEconomic.graph.edges.length + worldEconomic.supplyChain.logisticsNetwork.length + 5
  const policyImpact = Math.max(0, Math.min(100, civilizationStability + (worldEconomic.macroShock.crisis.severity > 0.3 ? -8 : 4)))

  return {
    mode: 'V27_DIGITAL_CIVILIZATION_COCKPIT_SUMMARY',
    metrics: {
      civilizationStability,
      dependencyEdges,
      policyImpact,
      globalSystemHealth: Math.round((globalEconomic.metrics.industryStability + worldEconomic.metrics.macroStability) / 2),
    },
  }
})
const realityDashboard = computed(() => {
  saasTick.value
  return processRealWorldFeedback({
    runtimeState: runtimeState.value,
    civilization: digitalCivilizationDashboard.value,
    workflow: {
      states: ['DRAFT', 'SUBMITTED', 'APPROVED', 'CLOSED'],
    },
    record: {
      ...order.value,
      workflow_state: 'SUBMITTED',
      urgency: 'high',
    },
    feedback: {
      urgent: true,
      approvalDelayRate: 0.22,
      workflowBacklog: 8,
      cashPressure: 0.34,
      supplierDelayRate: 0.18,
      paymentDelayDays: 14,
    },
  })
})
const governanceDashboard = computed(() => {
  saasTick.value
  return governEnterprise({
    runtimeState: runtimeState.value,
    reality: realityDashboard.value,
    workflow: {
      states: ['DRAFT', 'SUBMITTED', 'APPROVED', 'CLOSED'],
    },
    record: {
      ...order.value,
      workflow_state: 'SUBMITTED',
      urgency: 'high',
    },
    feedback: {
      urgent: true,
      approvalDelayRate: 0.22,
      workflowBacklog: 8,
      cashPressure: 0.34,
      supplierDelayRate: 0.18,
      paymentDelayDays: 14,
    },
  })
})
const fullAutonomyDashboard = computed(() => {
  saasTick.value
  return runAutonomousEnterprise({
    runtimeState: runtimeState.value,
    reality: realityDashboard.value,
    workflow: {
      stateField: 'workflow_state',
      states: ['DRAFT', 'SUBMITTED', 'APPROVED', 'CLOSED'],
      transitions: [
        { from: 'DRAFT', to: 'SUBMITTED' },
        { from: 'SUBMITTED', to: 'APPROVED' },
        { from: 'APPROVED', to: 'CLOSED' },
      ],
    },
    schema: {
      name: 'purchaseOrder',
      api: {
        module: 'purchaseOrder',
      },
    },
    record: {
      ...order.value,
      workflow_state: 'DRAFT',
      urgency: 'normal',
    },
    feedback: {
      urgent: true,
      workflowBacklog: 9,
      cashPressure: 0.28,
      performanceScore: 84,
    },
  })
})
const industryDashboard = computed(() => {
  industryTick.value
  const model = getLatestIndustryModel()
  if (!model) return null

  return {
    industry: model.industry,
    kpis: model.kpis || [],
  }
})

function t(key) {
  return translate(key)
}

function metricLabel(key) {
  return translate(cockpitMetricSchema[key]?.label || key)
}

function getIcon(name) {
  return iconMap[name] || DataBoard
}

function formatCurrency(value) {
  return `$${Number(value || 0).toLocaleString()}`
}

function formatPercent(value) {
  return `${Math.round(Number(value || 0) * 100)}%`
}

function industryKpiValue(kpi) {
  const values = {
    OEE: '86%',
    Yield: '94%',
    Downtime: '3.2h',
    CashFlow: '$128,000',
    ProfitMargin: '18%',
    'AR Aging': '21d',
    DeliveryTime: '2.4d',
    InventoryTurnover: '7.8x',
    GMV: '$260,000',
    SellThroughRate: '73%',
    StoreMargin: '16%',
    CustomerRetention: '82%',
    LeadConversion: '24%',
    CustomerLTV: '$4,600',
    SupplierOTD: '91%',
    PurchaseCycleTime: '5.5d',
    CostSaving: '8%',
    SystemScore: '88',
  }

  return values[kpi] || 'READY'
}

function getScopeRate(scope) {
  return reviewStatus.value.enterpriseMatrix.scopeScores.find((item) => item.scope === scope)?.complianceRate || 0
}

function runTrace() {
  const traceApi = window.__TRACE__
  const profitOS = traceApi?.profitOS?.run
    ? traceApi.profitOS.run({ goal: 'optimize procurement system' }, { tenantId: runtimeState.value.tenant.id, data: order.value })
    : runProfitOS({ goal: 'optimize procurement system' }, { tenantId: runtimeState.value.tenant.id, data: order.value })

  const systemHealth = traceApi?.system?.health
    ? traceApi.system.health()
    : getSystemHealth()
  const review = traceApi?.review?.status
    ? traceApi.review.status()
    : generateReviewStatus()
  const controlLoop = traceApi?.review?.control
    ? traceApi.review.control()
    : runReviewControlLoop()

  result.value = profitOS
  health.value = systemHealth
  reviewStatus.value = review
  reviewControl.value = controlLoop.control || getReviewControlState()
  controlTick.value += 1
  industryTick.value += 1
  executionTick.value += 1
  autonomousTick.value += 1
  networkTick.value += 1
  globalTick.value += 1
  civilizationTick.value += 1
  humanTick.value += 1
  hybridTick.value += 1
  finalTick.value += 1
  convergenceTick.value += 1
  freezeTick.value += 1
  productTick.value += 1
  saasTick.value += 1
  traceState.value = {
    mode: profitOS.mode,
    health: systemHealth.errorCount === 0 ? 'Healthy' : 'Attention',
  }
  traceOutput.value = JSON.stringify({
    profitOS: {
      mode: profitOS.mode,
      tenant: profitOS.tenant,
    },
    system: systemHealth,
    review: {
      mode: review.mode,
      complianceRate: review.complianceRate,
      completionRate: review.completionRate,
      systemScores: review.systemScores,
      sourceSheets: review.sourceSheets,
    },
    reviewControl: reviewControl.value,
  }, null, 2)

  ensureRouteAccess()
}

function toggleTrace() {
  if (!canExecute.value) {
    traceOutput.value = JSON.stringify({
      error: 'ROLE_ACTION_DENIED',
      role: runtimeState.value.role,
      action: 'EXECUTE',
    }, null, 2)
    traceOpen.value = true
    return
  }

  traceOpen.value = !traceOpen.value
  if (traceOpen.value) runTrace()
}

function ensureRouteAccess() {
  const current = getCockpitNavigation().find((item) => item.path === activePath.value)
  if (current && !hasPlanAccess(runtimeState.value.plan, current.key)) {
    router.replace('/process-center')
  }
}

function orderFromPurchaseRow(row) {
  if (!row) return getDemoOrder()

  return {
    id: row.id,
    revenue: Number(row.quantity || 0) * Number(row.price || 0),
    materialCost: Math.round(Number(row.quantity || 0) * Number(row.price || 0) * 0.4),
    laborCost: Math.round(Number(row.quantity || 0) * Number(row.price || 0) * 0.2),
    overhead: Math.round(Number(row.quantity || 0) * Number(row.price || 0) * 0.1),
  }
}

async function refreshCockpitData() {
  if (!showCockpitDiagnostics.value) return

  const result = await dataGateway.list('purchaseOrder')
  const rows = Array.isArray(result?.data) ? result.data : []
  order.value = orderFromPurchaseRow(rows[0])
}

onMounted(async () => {
  stateManager.subscribe((nextState) => {
    runtimeState.value = nextState
    ensureRouteAccess()
    runTrace()
  })
  ensureRouteAccess()
  await refreshCockpitData()
  runTrace()
})
</script>

<style scoped>
.cockpit-shell {
  display: grid;
  grid-template-columns: 240px 1fr;
  min-height: 100vh;
  background: #eef3f8;
  color: #1f2937;
}

.sidebar {
  min-width: 0;
  background: #111827;
  color: #fff;
}

.brand {
  height: 72px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 0 18px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.brand strong {
  font-size: 20px;
}

.brand span {
  color: #aab5c4;
  font-size: 12px;
}

.cockpit-menu {
  border-right: 0;
  background: transparent;
}

.cockpit-menu :deep(.el-menu-item) {
  color: #d8e0ec;
}

.cockpit-menu :deep(.el-menu-item.is-active),
.cockpit-menu :deep(.el-menu-item:hover) {
  background: #1d4ed8;
  color: #fff;
}

.shell-main {
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.system-bar {
  position: sticky;
  top: 0;
  z-index: 10;
  height: 72px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 0 22px;
  background: #fff;
  border-bottom: 1px solid #dce5f2;
}

.system-title p,
.system-title h1 {
  margin: 0;
}

.system-title p {
  color: #64748b;
  font-size: 12px;
}

.system-title h1 {
  font-size: 22px;
}

.system-status {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.kpi-strip {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 12px;
  padding: 14px 18px;
}

.kpi-strip article {
  min-height: 76px;
  padding: 14px 16px;
  background: #fff;
  border: 1px solid #dce5f2;
  border-radius: 8px;
}

.kpi-strip span {
  display: block;
  color: #64748b;
  margin-bottom: 6px;
}

.kpi-strip strong {
  font-size: 22px;
}

.orchestration-strip,
.intelligence-strip,
.enterprise-execution-strip,
.enterprise-autopilot-strip,
.enterprise-evolution-strip,
.enterprise-stability-strip,
.production-finalization-strip,
.commercial-launch-strip,
.growth-os-strip,
.platform-expansion-strip,
.ecosystem-os-strip,
.ecosystem-governance-strip,
.real-data-strip,
.production-runtime-strip {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
  padding: 0 18px 14px;
}

.orchestration-strip article,
.intelligence-strip article,
.enterprise-execution-strip article,
.enterprise-autopilot-strip article,
.enterprise-evolution-strip article,
.enterprise-stability-strip article,
.production-finalization-strip article,
.commercial-launch-strip article,
.growth-os-strip article,
.platform-expansion-strip article,
.ecosystem-os-strip article,
.ecosystem-governance-strip article,
.real-data-strip article,
.production-runtime-strip article {
  min-height: 86px;
  padding: 14px 16px;
  background: #fff;
  border: 1px solid #dce5f2;
  border-radius: 8px;
}

.orchestration-strip span,
.intelligence-strip span,
.enterprise-execution-strip span,
.enterprise-autopilot-strip span,
.enterprise-evolution-strip span,
.enterprise-stability-strip span,
.production-finalization-strip span,
.commercial-launch-strip span,
.growth-os-strip span,
.platform-expansion-strip span,
.ecosystem-os-strip span,
.ecosystem-governance-strip span,
.real-data-strip span,
.production-runtime-strip span {
  display: block;
  color: #64748b;
  margin-bottom: 6px;
}

.orchestration-strip strong,
.intelligence-strip strong,
.enterprise-execution-strip strong,
.enterprise-autopilot-strip strong,
.enterprise-evolution-strip strong,
.enterprise-stability-strip strong,
.production-finalization-strip strong,
.commercial-launch-strip strong,
.growth-os-strip strong,
.platform-expansion-strip strong,
.ecosystem-os-strip strong,
.ecosystem-governance-strip strong,
.real-data-strip strong,
.production-runtime-strip strong {
  font-size: 20px;
}

.orchestration-strip p,
.intelligence-strip p,
.enterprise-execution-strip p,
.enterprise-autopilot-strip p,
.enterprise-evolution-strip p,
.enterprise-stability-strip p,
.production-finalization-strip p,
.commercial-launch-strip p,
.growth-os-strip p,
.platform-expansion-strip p,
.ecosystem-os-strip p,
.ecosystem-governance-strip p,
.real-data-strip p,
.production-runtime-strip p {
  margin: 6px 0 0;
  color: #64748b;
  font-size: 12px;
  line-height: 1.4;
}

.advanced-cockpit {
  margin: 0 18px 14px;
}

.advanced-cockpit summary {
  cursor: pointer;
  list-style: none;
  padding: 10px 12px;
  color: #475569;
  background: #fff;
  border: 1px solid #dce5f2;
  border-radius: 8px;
  font-weight: 600;
}

.advanced-cockpit summary::-webkit-details-marker {
  display: none;
}

.advanced-cockpit[open] summary {
  margin-bottom: 12px;
}

.industry-kpi-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  padding: 0 18px 14px;
}

.industry-kpi-strip article {
  min-height: 68px;
  padding: 12px 14px;
  background: #fff;
  border: 1px solid #dce5f2;
  border-radius: 8px;
}

.industry-kpi-strip span {
  display: block;
  color: #64748b;
  margin-bottom: 6px;
}

.industry-kpi-strip strong {
  font-size: 20px;
}

.review-strip {
  display: grid;
  grid-template-columns: 1fr 1fr minmax(280px, 2fr) 1.2fr;
  gap: 12px;
  padding: 0 18px 14px;
}

.review-strip article {
  min-height: 72px;
  padding: 14px 16px;
  background: #fff;
  border: 1px solid #dce5f2;
  border-radius: 8px;
}

.review-strip span {
  display: block;
  color: #64748b;
  margin-bottom: 6px;
}

.review-strip strong {
  font-size: 20px;
}

.module-compliance div {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.enterprise-review-strip {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
  padding: 0 18px 14px;
}

.enterprise-review-strip article {
  min-height: 68px;
  padding: 12px 14px;
  background: #fff;
  border: 1px solid #dce5f2;
  border-radius: 8px;
}

.enterprise-review-strip span {
  display: block;
  color: #64748b;
  margin-bottom: 6px;
  font-size: 13px;
}

.enterprise-review-strip strong {
  font-size: 20px;
}

.review-control-strip {
  display: grid;
  grid-template-columns: repeat(8, minmax(0, 1fr));
  gap: 12px;
  padding: 0 18px 14px;
}

.review-control-strip article {
  min-height: 66px;
  padding: 12px 14px;
  background: #fff;
  border: 1px solid #dce5f2;
  border-radius: 8px;
}

.review-control-strip span {
  display: block;
  color: #64748b;
  margin-bottom: 6px;
  font-size: 13px;
}

.review-control-strip strong {
  font-size: 18px;
}

.network-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  padding: 0 18px 14px;
}

.network-strip article {
  min-height: 66px;
  padding: 12px 14px;
  background: #fff;
  border: 1px solid #dce5f2;
  border-radius: 8px;
}

.network-strip span {
  display: block;
  color: #64748b;
  margin-bottom: 6px;
  font-size: 13px;
}

.network-strip strong {
  font-size: 18px;
}

.global-economy-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  padding: 0 18px 14px;
}

.global-economy-strip article {
  min-height: 66px;
  padding: 12px 14px;
  background: #fff;
  border: 1px solid #dce5f2;
  border-radius: 8px;
}

.global-economy-strip span {
  display: block;
  color: #64748b;
  margin-bottom: 6px;
  font-size: 13px;
}

.global-economy-strip strong {
  font-size: 18px;
}

.civilization-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  padding: 0 18px 14px;
}

.civilization-strip article {
  min-height: 66px;
  padding: 12px 14px;
  background: #fff;
  border: 1px solid #dce5f2;
  border-radius: 8px;
}

.civilization-strip span {
  display: block;
  color: #64748b;
  margin-bottom: 6px;
  font-size: 13px;
}

.civilization-strip strong {
  font-size: 18px;
}

.human-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  padding: 0 18px 14px;
}

.human-strip article {
  min-height: 66px;
  padding: 12px 14px;
  background: #fff;
  border: 1px solid #dce5f2;
  border-radius: 8px;
}

.human-strip span {
  display: block;
  color: #64748b;
  margin-bottom: 6px;
  font-size: 13px;
}

.human-strip strong {
  font-size: 18px;
}

.hybrid-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  padding: 0 18px 14px;
}

.hybrid-strip article {
  min-height: 66px;
  padding: 12px 14px;
  background: #fff;
  border: 1px solid #dce5f2;
  border-radius: 8px;
}

.hybrid-strip span {
  display: block;
  color: #64748b;
  margin-bottom: 6px;
  font-size: 13px;
}

.hybrid-strip strong {
  font-size: 18px;
}

.final-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  padding: 0 18px 14px;
}

.final-strip article {
  min-height: 66px;
  padding: 12px 14px;
  background: #fff;
  border: 1px solid #dce5f2;
  border-radius: 8px;
}

.final-strip span {
  display: block;
  color: #64748b;
  margin-bottom: 6px;
  font-size: 13px;
}

.final-strip strong {
  font-size: 18px;
}

.convergence-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  padding: 0 18px 14px;
}

.convergence-strip article {
  min-height: 66px;
  padding: 12px 14px;
  background: #fff;
  border: 1px solid #dce5f2;
  border-radius: 8px;
}

.convergence-strip span {
  display: block;
  color: #64748b;
  margin-bottom: 6px;
  font-size: 13px;
}

.convergence-strip strong {
  font-size: 18px;
}

.freeze-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  padding: 0 18px 14px;
}

.freeze-strip article {
  min-height: 66px;
  padding: 12px 14px;
  background: #fff;
  border: 1px solid #dce5f2;
  border-radius: 8px;
}

.freeze-strip span {
  display: block;
  color: #64748b;
  margin-bottom: 6px;
  font-size: 13px;
}

.freeze-strip strong {
  font-size: 18px;
}

.product-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  padding: 0 18px 14px;
}

.product-strip article {
  min-height: 66px;
  padding: 12px 14px;
  background: #fff;
  border: 1px solid #dce5f2;
  border-radius: 8px;
}

.product-strip span {
  display: block;
  color: #64748b;
  margin-bottom: 6px;
  font-size: 13px;
}

.product-strip strong {
  font-size: 18px;
}

.saas-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  padding: 0 18px 14px;
}

.saas-strip article {
  min-height: 66px;
  padding: 12px 14px;
  background: #fff;
  border: 1px solid #dce5f2;
  border-radius: 8px;
}

.saas-strip span {
  display: block;
  color: #64748b;
  margin-bottom: 6px;
  font-size: 13px;
}

.saas-strip strong {
  font-size: 18px;
}

.launch-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  padding: 0 18px 14px;
}

.launch-strip article {
  min-height: 66px;
  padding: 12px 14px;
  background: #fff;
  border: 1px solid #dce5f2;
  border-radius: 8px;
}

.launch-strip span {
  display: block;
  color: #64748b;
  margin-bottom: 6px;
  font-size: 13px;
}

.launch-strip strong {
  font-size: 18px;
}

.growth-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  padding: 0 18px 14px;
}

.growth-strip article {
  min-height: 66px;
  padding: 12px 14px;
  background: #fff;
  border: 1px solid #dce5f2;
  border-radius: 8px;
}

.growth-strip span {
  display: block;
  color: #64748b;
  margin-bottom: 6px;
  font-size: 13px;
}

.growth-strip strong {
  font-size: 18px;
}

.ecosystem-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  padding: 0 18px 14px;
}

.ecosystem-strip article {
  min-height: 66px;
  padding: 12px 14px;
  background: #fff;
  border: 1px solid #dce5f2;
  border-radius: 8px;
}

.ecosystem-strip span {
  display: block;
  color: #64748b;
  margin-bottom: 6px;
  font-size: 13px;
}

.ecosystem-strip strong {
  font-size: 18px;
}

.ecosystem-governance-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  padding: 0 18px 14px;
}

.ecosystem-governance-strip article {
  min-height: 66px;
  padding: 12px 14px;
  background: #fff;
  border: 1px solid #dce5f2;
  border-radius: 8px;
}

.ecosystem-governance-strip span {
  display: block;
  color: #64748b;
  margin-bottom: 6px;
  font-size: 13px;
}

.ecosystem-governance-strip strong {
  font-size: 18px;
}

.ecosystem-autonomy-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  padding: 0 18px 14px;
}

.ecosystem-autonomy-strip article {
  min-height: 66px;
  padding: 12px 14px;
  background: #fff;
  border: 1px solid #dce5f2;
  border-radius: 8px;
}

.ecosystem-autonomy-strip span {
  display: block;
  color: #64748b;
  margin-bottom: 6px;
  font-size: 13px;
}

.ecosystem-autonomy-strip strong {
  font-size: 18px;
}

.business-autonomy-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  padding: 0 18px 14px;
}

.business-autonomy-strip article {
  min-height: 66px;
  padding: 12px 14px;
  background: #fff;
  border: 1px solid #dce5f2;
  border-radius: 8px;
}

.business-autonomy-strip span {
  display: block;
  color: #64748b;
  margin-bottom: 6px;
  font-size: 13px;
}

.business-autonomy-strip strong {
  font-size: 18px;
}

.economy-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  padding: 0 18px 14px;
}

.economy-strip article {
  min-height: 66px;
  padding: 12px 14px;
  background: #fff;
  border: 1px solid #dce5f2;
  border-radius: 8px;
}

.economy-strip span {
  display: block;
  color: #64748b;
  margin-bottom: 6px;
  font-size: 13px;
}

.economy-strip strong {
  font-size: 18px;
}

.global-economic-strip-v25 {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  padding: 0 18px 14px;
}

.global-economic-strip-v25 article {
  min-height: 66px;
  padding: 12px 14px;
  background: #fff;
  border: 1px solid #dce5f2;
  border-radius: 8px;
}

.global-economic-strip-v25 span {
  display: block;
  color: #64748b;
  margin-bottom: 6px;
  font-size: 13px;
}

.global-economic-strip-v25 strong {
  font-size: 18px;
}

.world-economic-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  padding: 0 18px 14px;
}

.world-economic-strip article {
  min-height: 66px;
  padding: 12px 14px;
  background: #fff;
  border: 1px solid #dce5f2;
  border-radius: 8px;
}

.world-economic-strip span {
  display: block;
  color: #64748b;
  margin-bottom: 6px;
  font-size: 13px;
}

.world-economic-strip strong {
  font-size: 18px;
}

.civilization-unified-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  padding: 0 18px 14px;
}

.civilization-unified-strip article {
  min-height: 66px;
  padding: 12px 14px;
  background: #fff;
  border: 1px solid #dce5f2;
  border-radius: 8px;
}

.civilization-unified-strip span {
  display: block;
  color: #64748b;
  margin-bottom: 6px;
  font-size: 13px;
}

.civilization-unified-strip strong {
  font-size: 18px;
}

.reality-control-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  padding: 0 18px 14px;
}

.reality-control-strip article {
  min-height: 66px;
  padding: 12px 14px;
  background: #fff;
  border: 1px solid #dce5f2;
  border-radius: 8px;
}

.reality-control-strip span {
  display: block;
  color: #64748b;
  margin-bottom: 6px;
  font-size: 13px;
}

.reality-control-strip strong {
  font-size: 18px;
}

.autonomous-governance-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  padding: 0 18px 14px;
}

.autonomous-governance-strip article {
  min-height: 66px;
  padding: 12px 14px;
  background: #fff;
  border: 1px solid #dce5f2;
  border-radius: 8px;
}

.autonomous-governance-strip span {
  display: block;
  color: #64748b;
  margin-bottom: 6px;
  font-size: 13px;
}

.autonomous-governance-strip strong {
  font-size: 18px;
}

.full-autonomy-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  padding: 0 18px 14px;
}

.full-autonomy-strip article {
  min-height: 66px;
  padding: 12px 14px;
  background: #fff;
  border: 1px solid #dce5f2;
  border-radius: 8px;
}

.full-autonomy-strip span {
  display: block;
  color: #64748b;
  margin-bottom: 6px;
  font-size: 13px;
}

.full-autonomy-strip strong {
  font-size: 18px;
}

.workspace {
  min-width: 0;
  flex: 1;
  overflow: auto;
  padding: 0 18px 18px;
}

.trace-panel {
  position: fixed;
  top: 0;
  right: 0;
  z-index: 30;
  width: min(420px, 100vw);
  height: 100vh;
  padding: 18px;
  background: #fff;
  border-left: 1px solid #dce5f2;
  box-shadow: -12px 0 30px rgba(15, 23, 42, 0.14);
}

.trace-panel header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.trace-panel h2 {
  margin: 0;
}

.trace-status {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin: 18px 0;
}

.trace-status div {
  padding: 12px;
  background: #f4f7fb;
  border-radius: 8px;
}

.trace-status span {
  display: block;
  color: #64748b;
  margin-bottom: 6px;
}

.trace-panel pre {
  max-height: calc(100vh - 180px);
  overflow: auto;
  padding: 12px;
  background: #0f172a;
  color: #e5edf6;
  border-radius: 8px;
}

@media (max-width: 980px) {
  .cockpit-shell {
    grid-template-columns: 1fr;
  }

  .sidebar {
    position: static;
  }

  .kpi-strip {
    grid-template-columns: 1fr 1fr;
  }

  .industry-kpi-strip {
    grid-template-columns: 1fr 1fr;
  }

  .review-strip {
    grid-template-columns: 1fr 1fr;
  }

  .enterprise-review-strip {
    grid-template-columns: 1fr 1fr;
  }

  .review-control-strip {
    grid-template-columns: 1fr 1fr;
  }

  .network-strip {
    grid-template-columns: 1fr 1fr;
  }

  .global-economy-strip {
    grid-template-columns: 1fr 1fr;
  }

  .civilization-strip {
    grid-template-columns: 1fr 1fr;
  }

  .human-strip {
    grid-template-columns: 1fr 1fr;
  }

  .hybrid-strip {
    grid-template-columns: 1fr 1fr;
  }

  .final-strip {
    grid-template-columns: 1fr 1fr;
  }

  .convergence-strip {
    grid-template-columns: 1fr 1fr;
  }

  .freeze-strip {
    grid-template-columns: 1fr 1fr;
  }

  .product-strip {
    grid-template-columns: 1fr 1fr;
  }

  .saas-strip {
    grid-template-columns: 1fr 1fr;
  }

  .launch-strip {
    grid-template-columns: 1fr 1fr;
  }

  .growth-strip {
    grid-template-columns: 1fr 1fr;
  }

  .ecosystem-strip {
    grid-template-columns: 1fr 1fr;
  }

  .ecosystem-governance-strip {
    grid-template-columns: 1fr 1fr;
  }

  .ecosystem-autonomy-strip {
    grid-template-columns: 1fr 1fr;
  }

  .business-autonomy-strip {
    grid-template-columns: 1fr 1fr;
  }

  .economy-strip {
    grid-template-columns: 1fr 1fr;
  }

  .global-economic-strip-v25 {
    grid-template-columns: 1fr 1fr;
  }

  .world-economic-strip {
    grid-template-columns: 1fr 1fr;
  }

  .civilization-unified-strip {
    grid-template-columns: 1fr 1fr;
  }

  .reality-control-strip {
    grid-template-columns: 1fr 1fr;
  }

  .autonomous-governance-strip {
    grid-template-columns: 1fr 1fr;
  }

  .full-autonomy-strip {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 640px) {
  .system-bar {
    height: auto;
    align-items: flex-start;
    flex-direction: column;
    padding: 14px;
  }

  .kpi-strip {
    grid-template-columns: 1fr;
  }

  .industry-kpi-strip {
    grid-template-columns: 1fr;
  }

  .review-strip {
    grid-template-columns: 1fr;
  }

  .enterprise-review-strip {
    grid-template-columns: 1fr;
  }

  .review-control-strip {
    grid-template-columns: 1fr;
  }

  .network-strip {
    grid-template-columns: 1fr;
  }

  .global-economy-strip {
    grid-template-columns: 1fr;
  }

  .civilization-strip {
    grid-template-columns: 1fr;
  }

  .human-strip {
    grid-template-columns: 1fr;
  }

  .hybrid-strip {
    grid-template-columns: 1fr;
  }

  .final-strip {
    grid-template-columns: 1fr;
  }

  .convergence-strip {
    grid-template-columns: 1fr;
  }

  .freeze-strip {
    grid-template-columns: 1fr;
  }

  .product-strip {
    grid-template-columns: 1fr;
  }

  .saas-strip {
    grid-template-columns: 1fr;
  }

  .launch-strip {
    grid-template-columns: 1fr;
  }

  .growth-strip {
    grid-template-columns: 1fr;
  }

  .ecosystem-strip {
    grid-template-columns: 1fr;
  }

  .ecosystem-governance-strip {
    grid-template-columns: 1fr;
  }

  .ecosystem-autonomy-strip {
    grid-template-columns: 1fr;
  }

  .business-autonomy-strip {
    grid-template-columns: 1fr;
  }

  .economy-strip {
    grid-template-columns: 1fr;
  }

  .global-economic-strip-v25 {
    grid-template-columns: 1fr;
  }

  .world-economic-strip {
    grid-template-columns: 1fr;
  }

  .civilization-unified-strip {
    grid-template-columns: 1fr;
  }

  .reality-control-strip {
    grid-template-columns: 1fr;
  }

  .autonomous-governance-strip {
    grid-template-columns: 1fr;
  }

  .full-autonomy-strip {
    grid-template-columns: 1fr;
  }
}
</style>
