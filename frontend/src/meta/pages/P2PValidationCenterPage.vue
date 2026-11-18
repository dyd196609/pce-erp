<template>
  <main class="p2p-validation-center-page">
    <header class="page-header">
      <section>
        <p class="eyebrow">V1.13.29.2.2 P2P业务数据验证与闭环中心</p>
        <h1>P2P业务数据验证与闭环中心</h1>
        <p>当前页面同时包含 P2P业务数据一致性验证、风险确认、风险处理、风险关闭和历史风险追踪。本页只做只读验证和闭环状态展示，不反向修改采购、仓储、质检、应付、付款、总账、核销或银行流水。</p>
        <p>风险闭环用于数据问题确认和处理记录，不替代正式业务审批流程。</p>
        <p class="finance-current-module-badge">当前模块：P2P业务数据验证与闭环中心</p>
      </section>
      <nav class="page-tabs finance-flow-nav" aria-label="P2P验证中心导航">
        <router-link class="finance-nav-button" to="/analytics">返回分析中心</router-link>
        <router-link class="finance-nav-button" to="/business-trace">企业业务追踪中心</router-link>
        <router-link class="finance-nav-button finance-nav-button-active" to="/finance/p2p-validation-center">P2P验证中心<span class="finance-current-tag">当前</span></router-link>
      </nav>
    </header>

    <el-alert v-if="message" :title="message" :type="messageType" show-icon :closable="false" />

    <section class="operation-shell">
      <section class="plain-flow-guide">
        <strong>验证中心边界</strong>
        <div class="plain-flow-grid">
          <span><b>只读验证</b>只读取已存在的正式付款凭证和P2P链路字段，形成一致性验证视图。</span>
          <span><b>不改业务</b>不修改 SCM、WMS、QMS、Finance 应付付款和正式付款凭证数据。</span>
          <span><b>不写财务</b>不写总账，不生成 ledgerEntryId / ledgerEntryNo，不核销，不生成银行流水。</span>
          <span><b>不写存储</b>不初始化基础数据，不写入或覆盖业务测试数据。</span>
          <span><b>内置闭环</b>当前页面包含 P2P业务数据一致性验证、P2P风险确认、P2P风险处理、P2P风险关闭和历史风险追踪；风险闭环是本页面内置能力，不是独立业务执行页面。</span>
        </div>
      </section>

      <section class="plain-flow-guide">
        <strong>P2P风险管理流程</strong>
        <div class="risk-management-flow">
          <article>
            <span>1. 风险分析发现</span>
            <strong>{{ p2pRiskAnalysis.riskCount }}</strong>
            <small>原始只读分析结果，可能包含同一问题的多个影响项。</small>
          </article>
          <article>
            <span>2. 生成风险事件</span>
            <strong>{{ riskEventCenter.riskEventCount }}</strong>
            <small>按来源单据、断点、风险类型归并后的管理对象。</small>
          </article>
          <article>
            <span>3. 进入风险闭环</span>
            <strong>{{ riskLifecycleSummary.currentCount + riskLifecycleSummary.historyCount }}</strong>
            <small>风险事件进入生命周期视图，不改变业务数据。</small>
          </article>
          <article>
            <span>4. 当前待处理</span>
            <strong>{{ riskLifecycleSummary.currentCount }}</strong>
            <small>包含 open / confirmed / processing / resolved。</small>
          </article>
          <article>
            <span>5. 历史风险</span>
            <strong>{{ riskLifecycleSummary.historyCount }}</strong>
            <small>包含 closed / ignored，可追溯但不再进入当前处理。</small>
          </article>
        </div>
      </section>

      <el-card shadow="never">
        <template #header>
          <div class="card-header">
            <div>
              <h2>P2P风险分析中心</h2>
              <span>{{ p2pRiskAnalysis.riskConclusion }}</span>
            </div>
            <el-tag :type="p2pRiskAnalysis.criticalCount ? 'danger' : (p2pRiskAnalysis.warningCount ? 'warning' : 'success')">{{ p2pRiskAnalysis.riskCount ? '发现风险' : '未发现风险' }}</el-tag>
          </div>
        </template>
        <div class="overview-grid">
          <article>
            <span>风险事件数量</span>
            <strong>{{ riskEventCenter.riskEventCount }}</strong>
            <small>归并后的风险事件，不等同于原始风险条数。</small>
          </article>
          <article>
            <span>风险影响数量</span>
            <strong>{{ riskEventCenter.impactCount }}</strong>
            <small>同一风险事件下可能有多个影响项。</small>
          </article>
          <article>
            <span>重复风险数量</span>
            <strong>{{ riskEventCenter.duplicateRiskCount }}</strong>
            <small>已被归并的重复影响，不放大事件数。</small>
          </article>
          <article>
            <span>风险分析数量</span>
            <strong>{{ p2pRiskAnalysis.riskCount }}</strong>
            <small>原始风险分析发现数量，尚未按事件归并。</small>
          </article>
          <article>
            <span>严重风险</span>
            <strong>{{ p2pRiskAnalysis.criticalCount }}</strong>
            <small>需要责任部门处理的原始风险。</small>
          </article>
          <article>
            <span>提醒风险</span>
            <strong>{{ p2pRiskAnalysis.warningCount }}</strong>
            <small>需要确认或属于设计提醒的原始风险。</small>
          </article>
          <article>
            <span>涉及模块</span>
            <strong>{{ p2pRiskAnalysis.involvedModuleCount }}</strong>
            <small>风险分析涉及的业务模块范围。</small>
          </article>
          <article>
            <span>数据断点</span>
            <strong>{{ p2pRiskAnalysis.dataBreakCount }}</strong>
            <small>识别到业务链路断点的位置数。</small>
          </article>
          <article>
            <span>库存风险</span>
            <strong>{{ p2pRiskAnalysis.inventoryRisks.length }}</strong>
            <small>库存链只读验证发现的风险项。</small>
          </article>
        </div>
        <el-table :data="p2pRiskAnalysis.riskItems" border stripe height="360">
          <el-table-column type="index" label="序号" width="70" fixed="left" />
          <el-table-column prop="riskType" label="风险类型" min-width="160" :formatter="displayCellText" />
          <el-table-column prop="sourceNo" label="来源单据" min-width="170" :formatter="displayCellText" />
          <el-table-column prop="module" label="业务模块" min-width="130" :formatter="displayCellText" />
          <el-table-column prop="level" label="风险等级" width="110">
            <template #default="{ row }"><el-tag :type="riskLevelType(row.level)">{{ decodeDisplayText(row.level) }}</el-tag></template>
          </el-table-column>
          <el-table-column prop="breakPoint" label="断点位置" min-width="130" :formatter="displayCellText" />
          <el-table-column prop="reason" label="风险原因" min-width="260" :formatter="displayCellText" />
          <el-table-column prop="suggestion" label="建议方向" min-width="260" fixed="right" :formatter="displayCellText" />
        </el-table>
        <h3 class="subsection-title">重点采购订单风险分析</h3>
        <el-table :data="p2pRiskAnalysis.purchaseOrderRiskDimension" border stripe height="260">
          <el-table-column prop="poNo" label="采购订单" min-width="170" />
          <el-table-column prop="purchaseSupplierCount" label="采购供应商" width="110" />
          <el-table-column prop="paymentSupplierCount" label="付款供应商" width="110" />
          <el-table-column prop="purchaseAmount" label="采购金额" width="120" />
          <el-table-column prop="paymentAmount" label="付款金额" width="120" />
          <el-table-column prop="riskStatus" label="风险状态" width="150" :formatter="displayCellText" />
          <el-table-column prop="conclusion" label="结论" min-width="320" :formatter="displayCellText" />
        </el-table>
      </el-card>

      <el-card shadow="never">
        <template #header>
          <div class="card-header">
            <div>
              <h2>P2P风险闭环中心</h2>
              <span>风险事件进入生命周期管理后，只展示确认、处理、解决、关闭状态；本页不创建任务、不自动修复业务。</span>
            </div>
            <el-tag type="info">只读闭环视图</el-tag>
          </div>
        </template>
        <section class="closure-flow">
          <span
            v-for="step in activeLifecycleFlow.steps"
            :key="step.key"
            :class="['flow-step', `flow-step-${step.state}`]"
          >
            {{ step.label }}<b v-if="step.state === 'completed'">已完成</b><b v-if="step.state === 'current'">当前</b>
          </span>
        </section>
        <section class="lifecycle-current-card">
          <article>
            <span>风险编号</span>
            <strong>{{ activeLifecycleFlow.riskId }}</strong>
          </article>
          <article>
            <span>来源单据</span>
            <strong>{{ activeLifecycleFlow.sourceDocument }}</strong>
          </article>
          <article>
            <span>风险类型</span>
            <strong>{{ activeLifecycleFlow.riskType }}</strong>
          </article>
          <article>
            <span>当前状态</span>
            <strong>{{ activeLifecycleFlow.currentStatusText }}</strong>
          </article>
          <article>
            <span>责任模块</span>
            <strong>{{ activeLifecycleFlow.responsibleModule }}</strong>
          </article>
          <article>
            <span>责任角色</span>
            <strong>{{ activeLifecycleFlow.responsibleRole }}</strong>
          </article>
          <router-link class="finance-nav-button" :to="traceRouteFor(activeLifecycleFlow.raw)">查看链路</router-link>
        </section>
        <div class="overview-grid">
          <article>
            <span>严重风险 / 必须处理</span>
            <strong>{{ p2pRiskClosureCenter.criticalActionCount }}</strong>
          </article>
          <article>
            <span>待人工确认</span>
            <strong>{{ p2pRiskClosureCenter.confirmRequiredCount }}</strong>
          </article>
          <article>
            <span>设计提醒</span>
            <strong>{{ p2pRiskClosureCenter.designReminderCount }}</strong>
          </article>
          <article>
            <span>已通过</span>
            <strong>{{ p2pRiskClosureCenter.normalCount }}</strong>
          </article>
        </div>
        <div class="overview-grid">
          <article>
            <span>风险事件总数</span>
            <strong>{{ riskEventCenter.riskEventCount }}</strong>
            <small>全部风险事件数量，包含当前和历史。</small>
          </article>
          <article>
            <span>当前风险数量</span>
            <strong>{{ riskLifecycleSummary.currentCount }}</strong>
            <small>open / confirmed / processing / resolved。</small>
          </article>
          <article>
            <span>处理中数量</span>
            <strong>{{ riskLifecycleSummary.processingCount }}</strong>
            <small>仅统计 processing 状态风险。</small>
          </article>
          <article>
            <span>已关闭风险数量</span>
            <strong>{{ riskLifecycleSummary.closedCount }}</strong>
            <small>仅统计 closed 状态风险。</small>
          </article>
          <article>
            <span>历史风险数量</span>
            <strong>{{ riskLifecycleSummary.historyCount }}</strong>
            <small>closed + ignored，可查看但不进入当前处理。</small>
          </article>
        </div>
        <section class="filter-row">
          <el-select v-model="lifecycleViewFilter" placeholder="生命周期筛选">
            <el-option label="全部风险" value="all" />
            <el-option label="当前风险" value="current" />
            <el-option label="待确认" value="open" />
            <el-option label="处理中" value="processing" />
            <el-option label="已解决" value="resolved" />
            <el-option label="已关闭" value="closed" />
            <el-option label="历史风险" value="history" />
          </el-select>
          <el-select v-model="riskTypeFilter" clearable placeholder="风险类型筛选">
            <el-option label="多供应商链断裂" value="多供应商链断裂" />
            <el-option label="多供应商付款拆分提醒" value="多供应商付款拆分提醒" />
            <el-option label="库存链异常" value="库存链异常" />
            <el-option label="金额异常" value="金额异常" />
            <el-option label="付款异常" value="付款异常" />
            <el-option label="报表异常" value="报表异常" />
          </el-select>
          <el-select v-model="riskCauseFilter" clearable placeholder="原因分类筛选">
            <el-option label="系统逻辑问题" value="system_issue" />
            <el-option label="人工操作问题" value="operation_issue" />
            <el-option label="测试数据问题" value="test_data_issue" />
            <el-option label="流程设计问题" value="process_design_issue" />
            <el-option label="待确认" value="unknown" />
          </el-select>
          <el-select v-model="responsibleModuleFilter" clearable placeholder="责任模块筛选">
            <el-option label="SCM" value="SCM" />
            <el-option label="WMS" value="WMS" />
            <el-option label="QMS" value="QMS" />
            <el-option label="Finance" value="Finance" />
            <el-option label="Architecture" value="Architecture" />
          </el-select>
          <el-tag type="info">当前风险展示 {{ filteredRiskEvents.length }} / {{ riskLifecycleSummary.currentCount }} 个风险事件</el-tag>
        </section>
        <h3 class="subsection-title">当前风险列表</h3>
        <el-table :data="filteredRiskEvents" border stripe height="420">
          <el-table-column type="expand">
            <template #default="{ row }">
              <el-table :data="row.impacts" border size="small">
                <el-table-column prop="impactType" label="影响类型" min-width="160" :formatter="displayCellText" />
                <el-table-column prop="impactDescription" label="影响内容" min-width="320" :formatter="displayCellText" />
              </el-table>
            </template>
          </el-table-column>
          <el-table-column prop="riskId" label="风险编号" min-width="150" fixed="left" :formatter="displayCellText" />
          <el-table-column prop="riskActionLevelText" label="风险等级颜色" min-width="150">
            <template #default="{ row }">
              <el-tag :type="row.riskColor">{{ decodeDisplayText(row.riskActionLevelText) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="responsibleAction" label="是否需要处理" min-width="130" :formatter="displayCellText" />
          <el-table-column prop="riskLevel" label="风险等级" width="110" :formatter="displayCellText" />
          <el-table-column prop="riskType" label="风险类型" min-width="160" :formatter="displayCellText" />
          <el-table-column prop="sourceDocument" label="来源单据" min-width="170" :formatter="displayCellText" />
          <el-table-column prop="sourceModule" label="影响模块" min-width="130" :formatter="displayCellText" />
          <el-table-column prop="breakPoint" label="断点位置" min-width="120" :formatter="displayCellText" />
          <el-table-column label="判断依据" min-width="260">
            <template #default="{ row }">
              {{ decodeDisplayText(row.riskEvidence?.reason || row.inventoryChainDecision?.reason || '按风险事件规则识别') }}
            </template>
          </el-table-column>
          <el-table-column prop="riskCauseTypeText" label="原因分类" min-width="150" :formatter="displayCellText" />
          <el-table-column prop="responsibleModule" label="责任模块" min-width="150" :formatter="displayCellText" />
          <el-table-column prop="responsibleRole" label="责任角色" min-width="150" :formatter="displayCellText" />
          <el-table-column prop="suggestedAction" label="处理建议" min-width="260" :formatter="displayCellText" />
          <el-table-column label="业务链定位" min-width="130">
            <template #default="{ row }">
              <router-link class="trace-link" :to="traceRouteFor(row)">查看链路</router-link>
            </template>
          </el-table-column>
          <el-table-column label="处理历史" min-width="140">
            <template #default="{ row }">
              <el-button size="small" @click="showRiskHistory(row)">查看处理历史</el-button>
            </template>
          </el-table-column>
          <el-table-column prop="confirmStatusText" label="确认状态" width="120" :formatter="displayCellText" />
          <el-table-column prop="processStatusText" label="处理状态" width="120" :formatter="displayCellText" />
          <el-table-column label="闭环操作" min-width="330">
            <template #default="{ row }">
              <template v-if="!isHistoryRisk(row)">
                <el-button
                  size="small"
                  :disabled="!canConfirmRiskEvent(row)"
                  @click="confirmRiskEvent(row)"
                >
                  确认风险
                </el-button>
                <el-button
                  size="small"
                  :disabled="!canStartProcessingRiskEvent(row)"
                  @click="startProcessingRiskEvent(row)"
                >
                  开始处理
                </el-button>
                <el-button
                  size="small"
                  :disabled="!canResolveRiskEvent(row)"
                  @click="resolveRiskEvent(row)"
                >
                  标记解决
                </el-button>
                <el-button
                  size="small"
                  :disabled="!canCloseRiskEvent(row)"
                  @click="closeRiskEvent(row)"
                >
                  关闭风险
                </el-button>
              </template>
              <el-tag v-else type="info">历史风险，仅可查看</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="closureStatusText" label="关闭状态" width="120" fixed="right" :formatter="displayCellText" />
        </el-table>
        <h3 class="subsection-title">历史风险区域</h3>
        <el-table :data="historyRiskEvents" border stripe height="240">
          <el-table-column prop="riskId" label="风险编号" min-width="150" fixed="left" :formatter="displayCellText" />
          <el-table-column prop="riskType" label="风险类型" min-width="180" :formatter="displayCellText" />
          <el-table-column prop="sourceDocument" label="来源单据" min-width="170" :formatter="displayCellText" />
          <el-table-column prop="breakPoint" label="断点位置" min-width="120" :formatter="displayCellText" />
          <el-table-column prop="closureStatusText" label="关闭状态" width="120" :formatter="displayCellText" />
          <el-table-column label="业务链定位" min-width="130">
            <template #default="{ row }">
              <router-link class="trace-link" :to="traceRouteFor(row)">查看链路</router-link>
            </template>
          </el-table-column>
          <el-table-column label="处理历史" min-width="140">
            <template #default="{ row }">
              <el-button size="small" @click="showRiskHistory(row)">查看处理历史</el-button>
            </template>
          </el-table-column>
        </el-table>
        <h3 class="subsection-title">风险确认记录</h3>
        <el-table :data="riskLifecycleSummary.riskConfirmHistory" border stripe height="220">
          <el-table-column prop="riskId" label="风险编号" min-width="150" :formatter="displayCellText" />
          <el-table-column prop="sourceDocument" label="来源单据" min-width="170" :formatter="displayCellText" />
          <el-table-column prop="beforeStatus" label="原状态" width="120" :formatter="displayCellText" />
          <el-table-column prop="afterStatus" label="新状态" width="120" :formatter="displayCellText" />
          <el-table-column prop="confirmPerson" label="确认人" min-width="140" :formatter="displayCellText" />
          <el-table-column prop="confirmTime" label="确认时间" min-width="190" :formatter="displayCellText" />
          <el-table-column prop="confirmRemark" label="确认说明" min-width="320" :formatter="displayCellText" />
        </el-table>
        <h3 class="subsection-title">风险处理记录</h3>
        <el-table :data="riskLifecycleSummary.riskProcessHistory" border stripe height="220">
          <el-table-column prop="riskId" label="风险编号" min-width="150" :formatter="displayCellText" />
          <el-table-column prop="sourceDocument" label="来源单据" min-width="170" :formatter="displayCellText" />
          <el-table-column label="状态变化" min-width="160">
            <template #default="{ row }">{{ decodeDisplayText(row.beforeStatus) }} → {{ decodeDisplayText(row.afterStatus) }}</template>
          </el-table-column>
          <el-table-column prop="actionType" label="处理动作" min-width="130" :formatter="displayCellText" />
          <el-table-column prop="operator" label="处理人" min-width="140" :formatter="displayCellText" />
          <el-table-column prop="operatorRole" label="角色" min-width="160" :formatter="displayCellText" />
          <el-table-column prop="time" label="时间" min-width="190" :formatter="displayCellText" />
          <el-table-column prop="processRemark" label="处理说明" min-width="320" :formatter="displayCellText" />
        </el-table>
        <h3 class="subsection-title">风险关闭历史</h3>
        <el-table :data="riskLifecycleSummary.riskClosureHistory" border stripe height="220">
          <el-table-column prop="riskId" label="风险编号" min-width="150" :formatter="displayCellText" />
          <el-table-column prop="beforeStatus" label="关闭前状态" width="120" :formatter="displayCellText" />
          <el-table-column prop="afterStatus" label="关闭后状态" width="120" :formatter="displayCellText" />
          <el-table-column prop="reason" label="流转原因" min-width="320" :formatter="displayCellText" />
          <el-table-column prop="operator" label="操作人" min-width="140" :formatter="displayCellText" />
          <el-table-column prop="time" label="流转时间" min-width="190" :formatter="displayCellText" />
        </el-table>
      </el-card>

      <el-card v-if="false" shadow="never">
        <template #header>
          <div class="card-header">
            <div>
              <h2>P2P风险报告与问题闭环</h2>
              <span>风险中心只负责分类和闭环设计，不自动确认原因，不自动修复业务。</span>
            </div>
            <el-tag type="info">只读闭环设计</el-tag>
          </div>
        </template>
        <el-table :data="p2pRiskReport" border stripe height="360">
          <el-table-column prop="riskId" label="风险编号" min-width="150" fixed="left" />
          <el-table-column prop="riskType" label="风险类型" min-width="160" />
          <el-table-column prop="sourceDocument" label="来源单据" min-width="170" />
          <el-table-column prop="sourceModule" label="影响模块" min-width="130" />
          <el-table-column prop="riskCauseTypeText" label="原因分类" min-width="150" :formatter="displayCellText" />
          <el-table-column prop="breakPoint" label="断点位置" min-width="120" :formatter="displayCellText" />
          <el-table-column prop="resolutionSuggestion" label="建议处理" min-width="280" />
          <el-table-column prop="closureStatusText" label="关闭状态" width="120" fixed="right" />
        </el-table>
      </el-card>

      <el-card v-if="false" shadow="never">
        <template #header>
          <div class="card-header">
            <div>
              <h2>P2P风险责任确认</h2>
              <span>风险发现 -> 原因确认 -> 责任归属 -> 处理跟踪 -> 关闭验证。本轮仅展示模型，不创建任务。</span>
            </div>
            <el-tag type="info">责任占位设计</el-tag>
          </div>
        </template>
        <el-table :data="p2pRiskResponsibility" border stripe height="360">
          <el-table-column prop="riskId" label="风险编号" min-width="150" fixed="left" />
          <el-table-column prop="riskType" label="风险类型" min-width="160" />
          <el-table-column prop="sourceDocument" label="来源单据" min-width="170" />
          <el-table-column prop="riskCauseTypeText" label="原因分类" min-width="150" :formatter="displayCellText" />
          <el-table-column prop="responsibleModule" label="责任模块" min-width="150" />
          <el-table-column prop="responsibleRole" label="责任角色" min-width="150" />
          <el-table-column prop="confirmStatusText" label="确认状态" width="120" />
          <el-table-column prop="suggestedAction" label="处理建议" min-width="260" />
          <el-table-column prop="closureStatusText" label="关闭状态" width="120" fixed="right" />
        </el-table>
      </el-card>

      <el-card shadow="never">
        <template #header>
          <div class="card-header">
            <div>
              <h2>验证总览</h2>
              <span>{{ centerConclusion }}</span>
            </div>
            <div class="button-row">
              <el-button @click="refresh">刷新验证视图</el-button>
              <el-button type="primary" plain @click="copyDiagnostic">复制诊断数据</el-button>
            </div>
          </div>
        </template>
        <div class="overview-grid">
          <article>
            <span>总验证数量</span>
            <strong>{{ validationModules.length }}</strong>
          </article>
          <article>
            <span>通过数量</span>
            <strong>{{ passedCount }}</strong>
          </article>
          <article>
            <span>风险数量</span>
            <strong>{{ riskSummary.riskCount }}</strong>
          </article>
          <article>
            <span>严重风险</span>
            <strong>{{ riskSummary.criticalCount }}</strong>
          </article>
          <article>
            <span>提醒数量</span>
            <strong>{{ riskSummary.warningCount }}</strong>
          </article>
          <article>
            <span>中心状态</span>
            <strong><el-tag :type="centerStatusType">{{ centerStatusText }}</el-tag></strong>
          </article>
        </div>
      </el-card>

      <el-card shadow="never">
        <template #header><h2>风险汇总</h2></template>
        <el-table :data="riskSummary.riskItems" border stripe height="320">
          <el-table-column type="index" label="序号" width="70" fixed="left" />
          <el-table-column prop="type" label="风险类型" min-width="160" :formatter="displayCellText" />
          <el-table-column prop="level" label="级别" width="120">
            <template #default="{ row }"><el-tag :type="riskLevelType(row.level)">{{ decodeDisplayText(row.level) }}</el-tag></template>
          </el-table-column>
          <el-table-column prop="module" label="来源模块" min-width="160" :formatter="displayCellText" />
          <el-table-column prop="message" label="说明" min-width="420" :formatter="displayCellText" />
        </el-table>
      </el-card>

      <el-card shadow="never">
        <template #header>
          <div class="card-header">
            <div>
              <h2>P2P库存链一致性验证</h2>
              <span>{{ inventoryChainValidation.inventoryChainValidationConclusion }}</span>
            </div>
            <el-tag :type="moduleStatusType(inventoryChainValidation.inventoryChainValidationStatus)">{{ displayValidationStatus(inventoryChainValidation.inventoryChainValidationStatus) }}</el-tag>
          </div>
        </template>
        <div class="boundary-note">本模块只验证采购 -> 收货 -> 检验 -> 入库 -> 库存流水链路，不修复库存业务，不生成真实库存，不修改库存数量。</div>
        <div class="overview-grid">
          <article>
            <span>采购到收货检查</span>
              <strong>{{ displayValidationStatus(inventoryChainValidation.purchaseReceiptCheckStatus) }}</strong>
          </article>
          <article>
            <span>检验到入库检查</span>
              <strong>{{ displayValidationStatus(inventoryChainValidation.inspectionInventoryCheckStatus) }}</strong>
          </article>
          <article>
            <span>入库检查</span>
              <strong>{{ displayValidationStatus(inventoryChainValidation.warehouseEntryCheckStatus) }}</strong>
          </article>
          <article>
            <span>库存流水检查</span>
              <strong>{{ displayValidationStatus(inventoryChainValidation.inventoryLedgerCheckStatus) }}</strong>
          </article>
          <article>
            <span>缺少库存流水</span>
            <strong>{{ inventoryChainValidation.inventoryRiskSummary.missingInventoryLedgerCount }}</strong>
          </article>
          <article>
            <span>风险总数</span>
            <strong>{{ inventoryChainValidation.inventoryRiskSummary.riskCount }}</strong>
          </article>
        </div>
        <el-table :data="inventoryChainValidation.inventoryChainValidationItems" border stripe height="360">
          <el-table-column type="expand">
            <template #default="{ row }">
              <el-table :data="row.inventoryTransactionDetails || []" border size="small">
                <el-table-column prop="transactionNo" label="库存流水编号" min-width="180" :formatter="displayCellText" />
                <el-table-column prop="transactionType" label="流水类型" min-width="180" :formatter="displayCellText" />
                <el-table-column prop="sourceInspectionNo" label="来源检验单" min-width="170" :formatter="displayCellText" />
                <el-table-column prop="sourceReceiptNo" label="来源收货单" min-width="170" :formatter="displayCellText" />
                <el-table-column prop="sourcePurchaseOrderNo" label="来源采购订单" min-width="180" :formatter="displayCellText" />
              </el-table>
            </template>
          </el-table-column>
          <el-table-column type="index" label="序号" width="70" fixed="left" />
          <el-table-column prop="purchaseOrderNo" label="采购订单" min-width="170" :formatter="displayCellText" />
          <el-table-column prop="receiveNo" label="收货单" min-width="150" />
          <el-table-column prop="inspectionNo" label="检验单" min-width="150" :formatter="displayCellText" />
          <el-table-column prop="warehouseEntryNo" label="入库引用" min-width="160" :formatter="displayCellText" />
          <el-table-column prop="inventoryTransactionCount" label="库存流水数量" width="130" />
          <el-table-column prop="inventoryTransactionText" label="库存流水" min-width="180" :formatter="displayCellText" />
          <el-table-column prop="inventoryRuleMatch" label="入库完成规则" min-width="210" :formatter="displayCellText" />
          <el-table-column label="判断依据" min-width="260">
            <template #default="{ row }">
              {{ decodeDisplayText(row.inventoryChainDecision?.reason || row.riskEvidence?.reason || '待确认') }}
            </template>
          </el-table-column>
          <el-table-column prop="amountTraceable" label="金额可追溯" width="120">
            <template #default="{ row }"><el-tag :type="row.amountTraceable ? 'success' : 'warning'">{{ row.amountTraceable ? '是' : '否' }}</el-tag></template>
          </el-table-column>
          <el-table-column prop="riskText" label="风险" min-width="280" fixed="right" :formatter="displayCellText" />
        </el-table>
      </el-card>

      <section class="module-grid">
        <el-card v-for="module in validationModules" :key="module.key" shadow="never" class="module-card">
          <template #header>
            <div class="module-card-header">
              <h2>{{ displayValidationModule(module.key) }}</h2>
              <el-tag :type="moduleStatusType(module.status)">{{ displayValidationStatus(module.status) }}</el-tag>
            </div>
          </template>
          <p class="module-desc">{{ decodeDisplayText(module.description) }}</p>
          <div class="module-result">
            <article v-for="item in module.metrics" :key="item.label">
              <span>{{ decodeDisplayText(item.label) }}</span>
              <strong>{{ decodeDisplayText(item.value) }}</strong>
            </article>
          </div>
          <ul class="module-warnings">
            <li v-for="warning in module.warnings" :key="warning">{{ decodeDisplayText(warning) }}</li>
            <li v-if="!module.warnings.length">当前未发现该模块的设计级风险。</li>
          </ul>
        </el-card>
      </section>
    </section>
  </main>
</template>

<script setup>
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { listFormalPaymentVouchers } from '../finance/formalPaymentVoucherStore.js'
import { getScmState } from '../scm/scmStore.js'
import { getWmsState } from '../wms/wmsStore.js'
import { getPurchaseReceiveState } from '../wms/purchaseReceiveStore.js'
import { getQmsState } from '../qms/qmsStore.js'
import { getP2PRiskLifecycleState, transitionP2PRiskLifecycle } from '../p2p/p2pRiskLifecycleStore.js'
import {
  decodeDisplayText,
  displayCellText,
  displayCauseType,
  displayLifecycleStatus,
  displayValidationModule,
  displayValidationStatus,
} from '../p2p/p2pDisplayDictionary.js'
import { normalizeDiagnosticEvidence, normalizeRiskEvent, normalizeTraceTarget } from '../p2p/p2pEvidenceNormalizer.js'
import { resolveP2PNodeStatus, resolveP2PTraceNodeStatuses } from './p2pTraceResolver.js'

const message = ref('')
const messageType = ref('success')
const vouchers = ref(listFormalPaymentVouchers())
const scmSnapshot = ref(getScmState())
const wmsSnapshot = ref(getWmsState())
const purchaseReceiveSnapshot = ref(getPurchaseReceiveState())
const qmsSnapshot = ref(getQmsState())
const riskTypeFilter = ref('')
const riskCauseFilter = ref('')
const responsibleModuleFilter = ref('')
const lifecycleViewFilter = ref('current')
const riskLifecycleState = ref(getP2PRiskLifecycleState())

const riskClosureOverrides = computed(() => {
  const records = riskLifecycleState.value.records || {}
  return Object.fromEntries(Object.entries(records).map(([riskEventId, record]) => {
    const history = Array.isArray(record.riskHistory) ? record.riskHistory : []
    const latest = history[history.length - 1] || {}
    return [riskEventId, {
      closureStatus: record.closureStatus || 'open',
      confirmStatus: record.confirmStatus || 'pending',
      processStatus: record.processStatus || 'not_started',
      reason: latest.reason || '',
    }]
  }))
})

const riskLifecycleHistory = computed(() => riskLifecycleState.value.riskLifecycleHistory || [])
const riskClosureHistory = computed(() => riskLifecycleHistory.value
  .filter((item) => item.afterStatus === 'closed')
  .map((item) => ({
    riskId: item.riskEventId,
    beforeStatus: item.beforeStatus,
    afterStatus: item.afterStatus,
    reason: item.reason,
    operator: item.operator,
    time: item.time,
  })))
const riskConfirmHistory = computed(() => riskLifecycleHistory.value
  .filter((item) => item.action === 'confirm')
  .map((item) => ({
    riskId: item.riskEventId,
    sourceDocument: item.sourceDocument,
    beforeStatus: item.beforeStatus,
    afterStatus: item.afterStatus,
    confirmType: item.reason?.includes('姝ｅ父涓氬姟妯″紡') ? 'normal_business_mode' : 'risk_confirmed',
    confirmPerson: item.operator,
    confirmTime: item.time,
    confirmRemark: item.reason,
  })))
const riskProcessHistory = computed(() => riskLifecycleHistory.value
  .filter((item) => ['start_processing', 'resolve', 'close'].includes(item.action))
  .map((item) => ({
    riskId: item.riskEventId,
    sourceDocument: item.sourceDocument,
    beforeStatus: item.beforeStatus,
    afterStatus: item.afterStatus,
    actionType: {
      start_processing: '开始处理',
      resolve: '标记解决',
      close: '关闭风险',
    }[item.action] || item.action,
    operator: item.operator,
    operatorRole: 'P2P风险处理占位角色',
    processRemark: item.reason,
    time: item.time,
  })))

function traceRouteFor(row = {}) {
  const traceTarget = row.traceTarget || {}
  return {
    path: '/finance/p2p-trace/' + encodeURIComponent(row.riskEventId || row.riskId || 'unknown'),
    query: {
      sourceDocument: row.sourceDocument || traceTarget.purchaseOrder || '',
      riskType: row.riskType || '',
      riskLevel: row.riskLevel || '',
      sourceModule: row.sourceModule || '',
      breakPoint: row.breakPoint || traceTarget.breakPoint || '',
        riskDescription: (row.impacts || []).map((impact) => impact.impactDescription).filter(Boolean).join('；'),
      riskEvidence: row.riskEvidence ? JSON.stringify(row.riskEvidence) : '',
      inventoryRuleMatch: row.inventoryRuleMatch || '',
      inventoryChainDecision: row.inventoryChainDecision ? JSON.stringify(row.inventoryChainDecision) : '',
      traceResolverEvidence: row.traceResolverEvidence ? JSON.stringify(row.traceResolverEvidence) : '',
      p2pNodeStatuses: row.p2pNodeStatuses?.length ? JSON.stringify(row.p2pNodeStatuses) : '',
      purchaseOrder: traceTarget.purchaseOrder || row.sourceDocument || '',
      receipt: traceTarget.receipt || '',
      inspection: traceTarget.inspection || '',
      warehouseEntry: traceTarget.warehouseEntry || '',
      inventoryTransaction: traceTarget.inventoryTransaction || '',
      payable: traceTarget.payable || '',
      paymentVoucher: traceTarget.paymentVoucher || '',
    },
  }
}

function notify(text, type = 'success') {
  message.value = text
  messageType.value = type
  ElMessage({ message: text, type })
}

function refresh() {
  vouchers.value = listFormalPaymentVouchers()
  scmSnapshot.value = getScmState()
  wmsSnapshot.value = getWmsState()
  purchaseReceiveSnapshot.value = getPurchaseReceiveState()
  qmsSnapshot.value = getQmsState()
  notify('已刷新只读验证视图，未修改任何业务数据。')
}

function amount(value) {
  const number = Number(value || 0)
  if (!Number.isFinite(number)) return 0
  return Math.round(number * 100) / 100
}

function uniqueCount(items = []) {
  return new Set(items.filter((item) => String(item || '').trim())).size
}

function uniqueTextList(items = []) {
  return Array.from(new Set((items || []).map((item) => String(item || '').trim()).filter(Boolean)))
}

function voucherAmount(voucher = {}) {
  return amount(voucher.totalVoucherAmount || voucher.amount || voucher.debitAmount || voucher.creditAmount)
}

function lineAmount(voucher = {}) {
  return amount((voucher.lines || []).reduce((total, line) => total + amount(line.amount), 0))
}

function hasText(value) {
  return String(value || '').trim().length > 0
}

function buildModule(key, title, description, metrics, warnings = [], criticalWarnings = []) {
  const status = criticalWarnings.length ? 'blocked' : (warnings.length ? 'warning' : 'passed')
  return {
    key,
    title,
    description,
    status,
      statusText: status === 'passed' ? '通过' : (status === 'blocked' ? '验证阻断' : '验证有提醒'),
    metrics,
    warnings: [...criticalWarnings, ...warnings],
    criticalWarnings,
  }
}

function firstInventoryNo(voucher = {}) {
  const nos = voucher.sourceInventoryTransactionNos || []
  if (Array.isArray(nos)) return nos[0] || ''
  return String(nos || '').split(/[锛?]/).map((item) => item.trim()).filter(Boolean)[0] || ''
}

function inventoryNoList(voucher = {}) {
  const nos = voucher.sourceInventoryTransactionNos || []
  if (Array.isArray(nos)) return nos.filter(Boolean)
  return String(nos || '').split(/[锛?]/).map((item) => item.trim()).filter(Boolean)
}

const PURCHASE_INBOUND_TRANSACTION_TYPES = [
  'purchaseInspectionIn',
  'concessionIn',
  'purchaseIn',
  '采购检验合格入库',
  '采购让步接收入库',
  '采购入库',
]

function inventoryTransactionType(record = {}) {
  return record.transactionType || record.type || record.businessType || record.transactionTypeText || record.remark || ''
}

function isPurchaseInboundTransaction(record = {}) {
  const text = String(inventoryTransactionType(record) || '')
  return PURCHASE_INBOUND_TRANSACTION_TYPES.some((type) => text.includes(type))
}

function inventoryTransactionRecords(nos = []) {
  const transactions = wmsSnapshot.value?.inventoryTransactions || []
  return nos.map((no) => {
    const textNo = String(no || '')
    return transactions.find((item) => [item.id, item.transactionNo, item.no].map((value) => String(value || '')).includes(textNo)) || {
      id: textNo,
      transactionNo: textNo,
      transactionType: '',
    }
  }).filter((item) => hasText(item.transactionNo || item.id))
}

function recordNo(record = {}, keys = []) {
  return keys.map((key) => record[key]).find((value) => hasText(value)) || ''
}

function matchesAny(value, candidates = []) {
  const text = String(value || '')
  return hasText(text) && candidates.some((candidate) => String(candidate || '') === text)
}

function resolveP2PTrace(sourceDocument = '', voucher = {}) {
  const purchaseOrderNo = sourceDocument || voucher.sourcePurchaseOrderNo || ''
  const purchaseOrder = (scmSnapshot.value?.purchaseOrders || []).find((item) => matchesAny(recordNo(item, ['poNo', 'purchaseOrderNo', 'orderNo']), [purchaseOrderNo]))
    || (hasText(purchaseOrderNo) ? { poNo: purchaseOrderNo } : null)
  const receipts = (purchaseReceiveSnapshot.value?.purchaseReceives || []).filter((item) => matchesAny(item.sourcePurchaseOrderNo || item.sourceOrderNo || item.poNo, [purchaseOrderNo]))
  if (hasText(voucher.sourceReceiveNo) && !receipts.some((item) => item.receiveNo === voucher.sourceReceiveNo)) receipts.push({ receiveNo: voucher.sourceReceiveNo, sourcePurchaseOrderNo: purchaseOrderNo })
  const receiptNos = receipts.map((item) => item.receiveNo).filter(Boolean)
  const inspections = (qmsSnapshot.value?.incomingInspections || []).filter((item) => {
    return matchesAny(item.sourcePurchaseOrderNo || item.sourceOrderNo, [purchaseOrderNo])
      || matchesAny(item.sourceReceiveNo, receiptNos)
      || matchesAny(item.inspectionNo, [voucher.sourceInspectionNo])
  })
  if (hasText(voucher.sourceInspectionNo) && !inspections.some((item) => item.inspectionNo === voucher.sourceInspectionNo)) {
    inspections.push({ inspectionNo: voucher.sourceInspectionNo, sourceReceiveNo: voucher.sourceReceiveNo, sourcePurchaseOrderNo: purchaseOrderNo })
  }
  const inspectionNos = inspections.map((item) => item.inspectionNo).filter(Boolean)
  const transactions = wmsSnapshot.value?.inventoryTransactions || []
  let matchedInventoryTransactions = transactions.filter((item) => matchesAny(item.sourceInspectionNo, inspectionNos))
  let resolverSource = matchedInventoryTransactions.length ? 'inspection' : ''
  let resolverSourceNo = inspectionNos[0] || ''
  if (!matchedInventoryTransactions.length) {
    matchedInventoryTransactions = transactions.filter((item) => matchesAny(item.sourceReceiveNo, receiptNos))
    resolverSource = matchedInventoryTransactions.length ? 'receipt' : ''
    resolverSourceNo = receiptNos[0] || ''
  }
  if (!matchedInventoryTransactions.length) {
    matchedInventoryTransactions = transactions.filter((item) => matchesAny(item.sourcePurchaseOrderNo || item.sourceOrderNo, [purchaseOrderNo]))
    resolverSource = matchedInventoryTransactions.length ? 'purchaseOrder' : ''
    resolverSourceNo = purchaseOrderNo
  }
  const voucherTransactions = inventoryTransactionRecords(inventoryNoList(voucher))
  voucherTransactions.forEach((transaction) => {
    const no = transaction.transactionNo || transaction.id
    if (!matchedInventoryTransactions.some((item) => (item.transactionNo || item.id) === no)) matchedInventoryTransactions.push(transaction)
  })
  if (!resolverSource && voucherTransactions.length) {
    resolverSource = 'paymentVoucher'
    resolverSourceNo = voucher.formalVoucherNo || voucher.voucherNo || ''
  }
  return {
    purchaseOrder,
    receipt: receipts[0] || null,
    inspection: inspections[0] || null,
    warehouseEntry: voucher.sourceWarehouseEntryNo || voucher.sourceInventoryEntryNo || '',
    inventoryTransactions: matchedInventoryTransactions,
    payable: voucher.sourceApDraftNo || voucher.sourcePayableCheckNo || voucher.sourcePayablePrepareNo || '',
    paymentVoucher: voucher.formalVoucherNo || voucher.voucherNo || '',
    traceResolverEvidence: {
      source: resolverSource || 'missing',
      sourceNo: resolverSourceNo || '',
      matchedInventoryTransaction: matchedInventoryTransactions.map((item) => item.transactionNo || item.id).filter(Boolean),
        decision: matchedInventoryTransactions.length ? '库存流水存在' : '未发现库存流水',
    },
  }
}

function buildInventoryChainDecision({ purchaseOrderNo, warehouseEntryNo, inventoryTransactionNos, inventoryTransactions, traceResolverEvidence }) {
  const warehouseNodeStatus = resolveP2PNodeStatus('warehouseEntry', {
    purchaseOrderNo,
    warehouseEntryNo,
    inventoryTransactionNos,
    inventoryTransactions,
  })
  const inventoryNodeStatus = resolveP2PNodeStatus('inventoryTransaction', {
    inventoryTransactionNos,
    inventoryTransactions,
  })
  const inboundTransactions = (inventoryTransactions || []).filter((item) => {
    const hasSourcePurchaseOrder = hasText(item.sourcePurchaseOrderNo || item.sourceOrderNo || purchaseOrderNo)
    return hasSourcePurchaseOrder && isPurchaseInboundTransaction(item)
  })
  if (warehouseNodeStatus.status === 'normal') {
    return {
      status: 'passed',
      reason: warehouseNodeStatus.evidence,
      source: warehouseNodeStatus.source,
      inventoryRuleMatch: warehouseNodeStatus.source === 'warehouseEntry' ? 'warehouseEntry' : (traceResolverEvidence?.source ? 'traceResolver:' + traceResolverEvidence.source : 'inventoryTransactionExists'),
      evidence: [warehouseNodeStatus.sourceNo].filter(Boolean),
      nodeStatus: {
        warehouseEntry: warehouseNodeStatus,
        inventoryTransaction: inventoryNodeStatus,
      },
    }
  }
  if (hasText(warehouseEntryNo)) {
    return {
      status: 'passed',
      reason: '发现独立入库单，判定入库完成。',
      source: 'warehouseEntry',
      inventoryRuleMatch: 'warehouseEntry',
      evidence: ['入库单 ' + warehouseEntryNo],
    }
  }
  if (inboundTransactions.length) {
    const first = inboundTransactions[0]
    return {
      status: 'passed',
      reason: '发现采购检验合格或让步接收入库库存流水，判定入库完成。',
      source: 'inventoryTransaction',
      inventoryRuleMatch: 'purchaseInboundInventoryTransaction',
      evidence: [
        '库存流水 ' + (first.transactionNo || first.id),
        '类型 ' + (inventoryTransactionType(first) || '采购入库类'),
      ],
    }
  }
  if ((inventoryTransactionNos || []).length) {
    return {
      status: 'passed',
      reason: '发现库存流水，按统一P2P追踪解析判定入库完成。',
      source: 'inventoryTransaction',
      inventoryRuleMatch: traceResolverEvidence?.source ? 'traceResolver:' + traceResolverEvidence.source : 'inventoryTransactionExists',
      evidence: ['库存流水 ' + (inventoryTransactionNos || []).join('、')],
    }
  }
  return {
    status: 'blocked',
    reason: '未发现独立入库单，也未发现可代表入库完成的采购入库类库存流水。',
    source: 'missing',
    inventoryRuleMatch: 'missingWarehouseEntryAndInventoryTransaction',
    evidence: ['未发现入库单', '未发现库存流水'],
  }
}

function buildInventoryChainValidation(list = []) {
  const items = (list || []).map((voucher) => {
    const resolvedTrace = resolveP2PTrace(voucher.sourcePurchaseOrderNo || '', voucher)
    const purchaseOrderNo = recordNo(resolvedTrace.purchaseOrder || {}, ['poNo', 'purchaseOrderNo', 'orderNo']) || voucher.sourcePurchaseOrderNo || ''
    const receiveNo = recordNo(resolvedTrace.receipt || {}, ['receiveNo', 'sourceReceiveNo']) || voucher.sourceReceiveNo || ''
    const inspectionNo = recordNo(resolvedTrace.inspection || {}, ['inspectionNo', 'sourceInspectionNo']) || voucher.sourceInspectionNo || ''
    const inventoryTransactions = resolvedTrace.inventoryTransactions || []
    const inventoryTransactionNos = uniqueTextList(inventoryTransactions.map((item) => item.transactionNo || item.id))
    const inventoryTransactionDetails = inventoryTransactionNos.map((no) => {
      const transaction = inventoryTransactions.find((item) => (item.transactionNo || item.id) === no) || {}
      return {
        transactionNo: no,
        transactionType: inventoryTransactionType(transaction) || '采购入库类库存流水',
        sourceInspectionNo: transaction.sourceInspectionNo || inspectionNo || '',
        sourceReceiptNo: transaction.sourceReceiptNo || receiveNo || '',
        sourcePurchaseOrderNo: transaction.sourcePurchaseOrderNo || purchaseOrderNo || '',
      }
    })
    const warehouseEntryNo = resolvedTrace.warehouseEntry || ''
    const inventoryChainDecision = buildInventoryChainDecision({
      purchaseOrderNo,
      warehouseEntryNo,
      inventoryTransactionNos,
      inventoryTransactions,
      traceResolverEvidence: resolvedTrace.traceResolverEvidence,
    })
    const p2pNodeStatuses = resolveP2PTraceNodeStatuses({
      purchaseOrderNo,
      receiveNo,
      inspectionNo,
      warehouseEntryNo,
      inventoryTransactionNos,
      inventoryTransactions,
      payable: resolvedTrace.payable,
      paymentVoucher: resolvedTrace.paymentVoucher,
    })
    const amountTraceable = voucherAmount(voucher) > 0
    const risks = []
    if (hasText(purchaseOrderNo) && !hasText(receiveNo)) risks.push('采购有，收货无')
    if (hasText(receiveNo) && !hasText(inspectionNo)) risks.push('收货有，检验无')
    if (hasText(inspectionNo) && inventoryChainDecision.status === 'blocked') risks.push('检验有，入库无')
    if (hasText(inspectionNo) && inventoryChainDecision.status === 'warning') risks.push('库存流水类型待确认')
    if (hasText(warehouseEntryNo) && !inventoryTransactionNos.length) risks.push('入库有，库存流水无')
    if (!inventoryTransactionNos.length) risks.push('库存金额无法追踪')
    if (!amountTraceable) risks.push('金额是否可追溯：否')
    return {
      voucherId: voucher.id || '',
      formalVoucherNo: voucher.formalVoucherNo || voucher.voucherNo || '',
      purchaseOrderNo: purchaseOrderNo || '-',
      receiveNo: receiveNo || '-',
      inspectionNo: inspectionNo || '-',
      warehouseEntryNo: warehouseEntryNo || '-',
      inventoryTransactionNos,
      inventoryTransactionCount: inventoryTransactionNos.length,
      inventoryTransactionDetails,
      inventoryTransactionText: inventoryTransactionNos.join('、') || '-',
      inventoryTransactionTypes: inventoryTransactions.map((item) => inventoryTransactionType(item)).filter(Boolean),
      inventoryRuleMatch: inventoryChainDecision.inventoryRuleMatch,
      inventoryChainDecision,
      p2pNodeStatuses,
      traceResolverEvidence: resolvedTrace.traceResolverEvidence,
      traceTarget: {
        purchaseOrder: purchaseOrderNo,
        receipt: receiveNo,
        inspection: inspectionNo,
        warehouseEntry: warehouseEntryNo,
          inventoryTransaction: inventoryTransactionNos.join('、'),
        payable: resolvedTrace.payable,
        paymentVoucher: resolvedTrace.paymentVoucher,
      },
      riskEvidence: {
        status: inventoryChainDecision.status,
        basis: inventoryChainDecision.evidence,
        source: inventoryChainDecision.source,
        matchedRule: inventoryChainDecision.inventoryRuleMatch,
        reason: inventoryChainDecision.reason,
      },
      amount: voucherAmount(voucher),
      amountTraceable,
      riskTypes: Array.from(new Set(risks)),
        riskText: risks.length ? Array.from(new Set(risks)).join('；') : '通过',
    }
  })
  const countRisk = (riskType) => items.filter((item) => item.riskTypes.includes(riskType)).length
  const countRiskByText = (...parts) => items.filter((item) => item.riskTypes.some((riskType) => parts.every((part) => riskType.includes(part)))).length
  const missingReceiptCount = countRisk('采购有，收货无')
  const missingInspectionCount = countRisk('收货有，检验无')
  const missingWarehouseEntryCount = countRiskByText('检验', '入库无')
  const unconfirmedInventoryTransactionTypeCount = countRisk('库存流水类型待确认')
  const missingInventoryLedgerCount = items.filter((item) => !item.inventoryTransactionNos.length).length
  const untraceableAmountCount = items.filter((item) => !item.amountTraceable || item.riskTypes.includes('库存金额无法追踪')).length
  const riskCount = items.reduce((total, item) => total + item.riskTypes.length, 0)
  const status = riskCount ? 'blocked' : 'passed'
  return {
    inventoryChainValidationStatus: status,
    inventoryChainValidationConclusion: riskCount
      ? '库存链一致性验证发现 ' + riskCount + ' 个风险点，本轮只提示，不修复库存业务。'
      : '采购、收货、检验、入库、库存流水链路当前未发现设计级断点。',
    purchaseReceiptCheckStatus: missingReceiptCount ? '采购有，收货无' : '通过',
    inspectionInventoryCheckStatus: missingInspectionCount || missingWarehouseEntryCount ? '存在检验/入库断点' : '通过',
    warehouseEntryCheckStatus: missingWarehouseEntryCount ? '检验有，入库无' : '通过',
    inventoryLedgerCheckStatus: missingInventoryLedgerCount ? '入库有，库存流水无' : '通过',
    inventoryChainValidationItems: items,
    inventoryRiskSummary: {
      riskCount,
      missingReceiptCount,
      missingInspectionCount,
      missingWarehouseEntryCount,
      unconfirmedInventoryTransactionTypeCount,
      missingInventoryLedgerCount,
      untraceableAmountCount,
      riskTypes: [
        { type: '采购有，收货无', count: missingReceiptCount },
        { type: '收货有，检验无', count: missingInspectionCount },
        { type: '检验有，入库无', count: missingWarehouseEntryCount },
        { type: '库存流水类型待确认', count: unconfirmedInventoryTransactionTypeCount },
        { type: '入库有，库存流水无', count: missingInventoryLedgerCount },
        { type: '库存金额无法追踪', count: untraceableAmountCount },
      ],
    },
  }
}

const inventoryChainValidation = computed(() => buildInventoryChainValidation(vouchers.value || []))

function purchaseLineAmount(line = {}) {
  return amount(line.planAmount ?? line.amount ?? line.approvedAmount ?? (amount(line.quantity) * amount(line.price || line.planPrice || line.approvedPrice)))
}

function purchaseOrderNo(order = {}) {
  return order.poNo || order.purchaseOrderNo || order.orderNo || ''
}

function supplierNameOf(record = {}) {
  return record.supplierName || record.supplierId || '鏈寚瀹氫緵搴斿晢'
}

function groupByPurchaseOrder(list = []) {
  const groups = new Map()
  ;(list || []).forEach((voucher) => {
    const poNo = voucher.sourcePurchaseOrderNo || '未指定采购订单'
    const current = groups.get(poNo) || []
    current.push(voucher)
    groups.set(poNo, current)
  })
  return groups
}

function buildRiskTracePath(sourceNo, path, breakPoint, reason) {
  return { sourceNo, path, breakPoint, reason }
}

function buildP2PRiskAnalysis(list = [], scm = {}, inventorySummary = {}) {
  let riskItems = []
  let riskTracePaths = []
  const purchaseOrders = scm.purchaseOrders || []
  const purchaseItems = scm.purchaseOrderItems || []
  const voucherGroups = groupByPurchaseOrder(list)
  const targetPoNos = ['PO2026070314534951', 'PO2026070605510641']
  const poNos = Array.from(new Set([
    ...targetPoNos,
    ...purchaseOrders.map(purchaseOrderNo).filter(Boolean),
      ...Array.from(voucherGroups.keys()).filter((item) => item !== '未指定采购订单'),
  ]))

  const pushRisk = (risk) => {
    riskItems.push({
      level: '提醒',
      suggestion: '验证中心只定位风险，后续由对应业务模块评估修复方案。',
      ...risk,
    })
    if (risk.tracePath) riskTracePaths.push(risk.tracePath)
  }

  const purchaseOrderRisks = poNos.map((poNo) => {
    const order = purchaseOrders.find((item) => purchaseOrderNo(item) === poNo) || {}
    const lines = purchaseItems.filter((line) => String(line.poId || line.purchaseOrderId || line.sourceOrderId || '') === String(order.id || ''))
    const vouchersForPo = voucherGroups.get(poNo) || []
    const headerAmount = amount(order.totalAmount ?? order.planAmount ?? order.amount ?? vouchersForPo.reduce((total, item) => total + voucherAmount(item), 0))
    const detailAmount = amount(lines.reduce((total, line) => total + purchaseLineAmount(line), 0))
    const supplierSet = new Set([
      ...lines.map((line) => line.supplierId || line.supplierName).filter(Boolean),
      order.supplierId || order.supplierName || '',
    ].filter(Boolean))
    const risks = []
    if (!hasText(poNo) || poNo === '未指定采购订单') risks.push('订单头缺失')
    if (!supplierSet.size) risks.push('供应商缺失')
    if (!lines.length && hasText(order.id)) risks.push('鏄庣粏缂哄け')
    if (lines.length && Math.abs(headerAmount - detailAmount) > 0.01) risks.push('金额不一致')
    risks.forEach((reason) => pushRisk({
      riskType: reason,
      sourceNo: poNo,
      module: '采购订单',
      level: reason === '金额不一致' ? '严重' : '提醒',
      breakPoint: '采购订单',
      reason,
      tracePath: buildRiskTracePath(poNo, ['采购订单', '订单明细', '供应商', '金额'], '采购订单', reason),
    }))
    return {
      poNo,
      supplierCount: supplierSet.size,
      supplierList: Array.from(supplierSet),
      headerAmount,
      detailAmount,
      riskStatus: risks.length ? '有风险' : '通过',
      risks,
    }
  })

  const supplierMap = new Map()
  purchaseItems.forEach((line) => {
    const supplierKey = line.supplierId || line.supplierName || 'UNKNOWN_SUPPLIER'
    const current = supplierMap.get(supplierKey) || {
      supplierId: line.supplierId || '',
      supplierName: supplierNameOf(line),
      orderCount: 0,
      purchaseAmount: 0,
      receiptAmount: 0,
      inventoryAmount: 0,
      payableAmount: 0,
      paymentAmount: 0,
      difference: 0,
      riskStatus: '閫氳繃',
    }
    current.orderCount += 1
    current.purchaseAmount = amount(current.purchaseAmount + purchaseLineAmount(line))
    supplierMap.set(supplierKey, current)
  })
  list.forEach((voucher) => {
    const supplierKey = voucher.supplierId || voucher.supplierName || 'UNKNOWN_SUPPLIER'
    const current = supplierMap.get(supplierKey) || {
      supplierId: voucher.supplierId || '',
      supplierName: supplierNameOf(voucher),
      orderCount: 0,
      purchaseAmount: 0,
      receiptAmount: 0,
      inventoryAmount: 0,
      payableAmount: 0,
      paymentAmount: 0,
      difference: 0,
      riskStatus: '閫氳繃',
    }
    const value = voucherAmount(voucher)
    if (hasText(voucher.sourceReceiveNo)) current.receiptAmount = amount(current.receiptAmount + value)
    if ((voucher.sourceInventoryTransactionNos || []).length) current.inventoryAmount = amount(current.inventoryAmount + value)
    if (hasText(voucher.sourceApDraftNo || voucher.sourcePayableCheckNo || voucher.sourcePayablePrepareNo)) current.payableAmount = amount(current.payableAmount + value)
    if (hasText(voucher.sourcePaymentExecutionNo || voucher.sourcePaymentRecordReviewNo)) current.paymentAmount = amount(current.paymentAmount + value)
    supplierMap.set(supplierKey, current)
  })
  const supplierRisks = Array.from(supplierMap.values()).map((supplier) => {
    const values = [supplier.purchaseAmount, supplier.receiptAmount, supplier.inventoryAmount, supplier.payableAmount, supplier.paymentAmount]
    supplier.difference = amount(Math.max(...values) - Math.min(...values))
    supplier.riskStatus = supplier.difference > 0.01 ? '有风险' : '通过'
    if (supplier.riskStatus !== '通过') {
      pushRisk({
        riskType: '金额不一致',
        sourceNo: supplier.supplierName,
        module: '供应商',
        level: '严重',
        breakPoint: '供应商金额链',
        reason: '供应商采购/收货/入库/应付/付款金额最大差额 ' + supplier.difference,
        tracePath: buildRiskTracePath(supplier.supplierName, ['采购', '收货', '入库', '应付', '付款'], '供应商金额链', '金额不一致'),
      })
    }
    return supplier
  })

  riskItems = riskItems.filter((risk) => {
    const text = [risk.riskType, risk.breakPoint, risk.reason].filter(Boolean).join(' ')
    return !(text.includes('供应商金额链') || text.includes('最大差额'))
  })
  riskTracePaths = riskTracePaths.filter((trace) => {
    const text = [trace.breakPoint, trace.reason].filter(Boolean).join(' ')
    return !(text.includes('供应商金额链') || text.includes('最大差额'))
  })
  supplierRisks.forEach((supplier) => {
    const overPaymentAmount = amount(supplier.paymentAmount - supplier.payableAmount)
    const missingPaymentOwner = supplier.paymentAmount > 0 && (!hasText(supplier.supplierId) && !hasText(supplier.supplierName))
    supplier.difference = overPaymentAmount > 0.01 ? overPaymentAmount : 0
    supplier.riskStatus = supplier.difference > 0.01 || missingPaymentOwner ? '有风险' : '通过'
    if (supplier.difference > 0.01 || missingPaymentOwner) {
      pushRisk({
        riskType: supplier.difference > 0.01 ? '付款超出应付' : '付款对象缺失',
        sourceNo: supplier.supplierName,
        module: '供应商',
        level: '严重',
        breakPoint: supplier.difference > 0.01 ? '付款金额' : '付款对象',
        reason: supplier.difference > 0.01
          ? '应付 ' + supplier.payableAmount + '，付款 ' + supplier.paymentAmount + '，付款超出应付 ' + supplier.difference
          : '存在付款金额，但付款对象供应商不存在。',
        suggestion: '按业务阶段核对剩余应付；部分付款不是风险，付款超出应付或付款对象缺失才需要责任部门处理。',
        tracePath: buildRiskTracePath(supplier.supplierName, ['采购', '收货', '检验', '入库', '应付', '付款', '剩余应付'], supplier.difference > 0.01 ? '付款金额' : '付款对象', '付款阶段异常'),
      })
    }
  })

  const purchaseOrderRiskDimension = poNos.map((poNo) => {
    const order = purchaseOrders.find((item) => purchaseOrderNo(item) === poNo) || {}
    const lines = purchaseItems.filter((line) => String(line.poId || line.purchaseOrderId || line.sourceOrderId || '') === String(order.id || ''))
    const vouchersForPo = voucherGroups.get(poNo) || []
    const purchaseSupplierCount = uniqueCount([
      ...lines.map((line) => line.supplierId || line.supplierName),
      order.supplierId || order.supplierName,
    ])
    const paymentSupplierCount = uniqueCount(vouchersForPo.map((item) => item.supplierId || item.supplierName))
    const purchaseAmount = amount(lines.reduce((total, line) => total + purchaseLineAmount(line), 0))
    const paymentAmount = amount(vouchersForPo.reduce((total, voucher) => total + voucherAmount(voucher), 0))
    const tracesForPo = vouchersForPo.map((voucher) => resolveP2PTrace(poNo, voucher))
    const nodeStatusesForPo = tracesForPo.length
      ? resolveP2PTraceNodeStatuses({
          purchaseOrderNo: poNo,
          receiveNo: tracesForPo.map((trace) => recordNo(trace.receipt || {}, ['receiveNo', 'sourceReceiveNo'])).filter(Boolean).join('、'),
          inspectionNo: tracesForPo.map((trace) => recordNo(trace.inspection || {}, ['inspectionNo', 'sourceInspectionNo'])).filter(Boolean).join('、'),
          inventoryTransaction: tracesForPo.flatMap((trace) => trace.inventoryTransactions || []).map((item) => item.transactionNo || item.id).filter(Boolean).join('、'),
          payable: vouchersForPo.map((item) => item.sourceApDraftNo || item.sourcePayableCheckNo || item.sourcePayablePrepareNo).filter(Boolean).join('、'),
          paymentVoucher: vouchersForPo.map((item) => item.formalVoucherNo || item.voucherNo || item.sourcePaymentExecutionNo || item.sourcePaymentRecordReviewNo).filter(Boolean).join('、'),
        })
      : []
    const payableNodeNormal = nodeStatusesForPo.some((item) => item.node === 'payable' && item.status === 'normal')
    const paymentNodeNormal = nodeStatusesForPo.some((item) => item.node === 'payment' && item.status === 'normal')
    const hasBreak = purchaseSupplierCount > 1 && paymentSupplierCount > 0 && purchaseSupplierCount !== paymentSupplierCount
    const isSettlementModelReminder = hasBreak && payableNodeNormal && paymentNodeNormal
    if (hasBreak) {
      pushRisk({
        riskType: isSettlementModelReminder ? '多供应商付款拆分提醒' : '供应商链断裂',
        sourceNo: poNo,
        module: '采购订单维度',
        level: isSettlementModelReminder ? '提醒' : '严重',
        breakPoint: '付款',
        reason: isSettlementModelReminder
          ? '采购供应商 ' + purchaseSupplierCount + ' 个，付款供应商 ' + paymentSupplierCount + ' 个；应付链和付款链均存在，按多供应商付款拆分提醒处理，不判定为业务链断裂。'
          : '采购供应商 ' + purchaseSupplierCount + ' 个，付款供应商 ' + paymentSupplierCount + ' 个，且未确认完整应付/付款链，存在多供应商结算链断裂风险。',
        suggestion: isSettlementModelReminder
          ? '后续评估多供应商分批付款、部分付款与结算拆分模型；本轮只读提示，不修改业务。'
          : '后续应评估多供应商结算拆分模型，并先核对统一追踪链中的应付与付款节点。',
        settlementModelReminder: isSettlementModelReminder,
        p2pNodeStatuses: nodeStatusesForPo,
        tracePath: buildRiskTracePath(poNo, ['采购订单', '收货', '入库', '应付', '付款'], '付款', isSettlementModelReminder ? '多供应商付款拆分提醒' : '多供应商结算链断裂'),
      })
    }
    return {
      poNo,
      purchaseSupplierCount,
      paymentSupplierCount,
      purchaseAmount,
      paymentAmount,
      suppliers: Array.from(new Set(lines.map((line) => line.supplierName || line.supplierId).filter(Boolean))),
      settlementModelReminder: isSettlementModelReminder,
      p2pNodeStatuses: nodeStatusesForPo,
      riskStatus: hasBreak ? (isSettlementModelReminder ? '多供应商付款拆分提醒' : '多供应商结算链断裂') : '通过',
      conclusion: hasBreak
        ? (isSettlementModelReminder ? '应付链和付款链正常，当前属于多供应商付款拆分提醒，不作为业务链断裂。' : '采购供应商数量与付款供应商数量不一致，且统一链路未确认完整。')
        : '当前未发现供应商数量断裂。',
    }
  })

  const inventoryRisks = (inventorySummary.inventoryChainValidationItems || [])
    .filter((item) => item.riskTypes?.length)
    .flatMap((item) => item.riskTypes.map((riskType) => {
      const breakPoint = riskType.includes('库存流水') ? '库存流水'
        : riskType.includes('入库') ? '入库'
          : riskType.includes('检验') ? '检验'
            : riskType.includes('收货') ? '收货'
              : '库存金额'
      const risk = {
        riskType: riskType.includes('类型待确认') ? '库存链待确认' : (riskType.includes('引用') ? '引用缺失' : (riskType.includes('金额') ? '成本链断裂' : '业务节点缺失')),
        sourceNo: item.purchaseOrderNo,
        module: '库存链',
        level: riskType.includes('类型待确认') ? '提醒' : '严重',
        breakPoint,
        reason: riskType,
        suggestion: '只读定位库存链断点，后续由 WMS/QMS/SCM 评估修复。',
        riskEvidence: item.riskEvidence,
        inventoryRuleMatch: item.inventoryRuleMatch,
        inventoryChainDecision: item.inventoryChainDecision,
        traceResolverEvidence: item.traceResolverEvidence,
        traceTarget: item.traceTarget,
          tracePath: buildRiskTracePath(item.purchaseOrderNo, ['采购订单', '收货', '检验', '入库', '库存流水'], breakPoint, riskType),
      }
      pushRisk(risk)
      return risk
    }))

  const paymentRisks = list
    .filter((voucher) => !hasText(voucher.sourcePaymentExecutionNo || voucher.sourcePaymentRecordReviewNo))
    .map((voucher) => {
      const risk = {
        riskType: '付款链异常',
        sourceNo: voucher.formalVoucherNo || voucher.sourcePurchaseOrderNo || '-',
        module: '付款',
        level: '提醒',
        breakPoint: '付款记录',
        reason: '缺少付款执行或付款记录复核来源。',
        suggestion: '检查付款执行草稿和付款记录复核来源链。',
        tracePath: buildRiskTracePath(voucher.formalVoucherNo || voucher.sourcePurchaseOrderNo || '-', ['应付', '付款', '付款记录'], '付款记录', '付款链异常'),
      }
      pushRisk(risk)
      return risk
    })

  const reportRisks = [{
    riskType: '报表验证风险',
    sourceNo: '报表验证',
    module: '报表',
    level: '提醒',
    breakPoint: '报表验证',
    reason: '总账未真实写入，报表验证仍为模拟阶段。',
    suggestion: '等待真实总账写入前复核和基础验证数据体系完成后再做正式报表验证。',
  }]

  const involvedModuleCount = uniqueCount(riskItems.map((item) => item.module))
  const criticalCount = riskItems.filter((item) => item.level === '严重').length
  const warningCount = riskItems.filter((item) => item.level !== '严重').length + reportRisks.length
  return {
    riskCount: riskItems.length + reportRisks.length,
    criticalCount,
    warningCount,
    involvedModuleCount,
    dataBreakCount: riskTracePaths.length,
    purchaseOrderRisks,
    supplierRisks,
    purchaseOrderRiskDimension,
    inventoryRisks,
    paymentRisks,
    reportRisks,
    riskItems: [...riskItems, ...reportRisks],
    riskTracePaths,
    riskConclusion: riskItems.length
      ? 'P2P风险分析发现 ' + riskItems.length + ' 个业务数据风险，本轮只定位不修复。'
      : 'P2P风险分析当前未发现严重业务数据断点。',
  }
}

const p2pRiskAnalysis = computed(() => buildP2PRiskAnalysis(vouchers.value || [], scmSnapshot.value || {}, inventoryChainValidation.value))

function riskCauseTypeText(type) {
  return displayCauseType(type)
}

function closureStatusText(status) {
  return displayLifecycleStatus(status)
}

function allP2PNodesNormal(nodes = []) {
  return Array.isArray(nodes) && nodes.length > 0 && nodes.every((node) => node.status === 'normal')
}

function canCloseRiskEvent(item = {}) {
  return item.closureStatus === 'resolved'
}

function isNormalBusinessModeRisk(item = {}) {
  return (item.riskType === '多供应商付款拆分提醒' || item.riskType === '澶氫緵搴斿晢浠樻鎷嗗垎鎻愰啋')
    && item.settlementModelReminder
    && allP2PNodesNormal(item.p2pNodeStatuses)
}

function canConfirmRiskEvent(item = {}) {
  return item.closureStatus === 'open'
}

function canStartProcessingRiskEvent(item = {}) {
  return item.closureStatus === 'confirmed'
}

function canResolveRiskEvent(item = {}) {
  return item.closureStatus === 'processing'
}

function isHistoryRisk(item = {}) {
  return ['closed', 'ignored'].includes(item.closureStatus)
}

function showRiskHistory(row = {}) {
  const riskId = row.riskId || row.riskEventId
  const historyItems = riskLifecycleHistory.value.filter((item) => item.riskEventId === riskId)
  if (!historyItems.length) {
    notify('当前风险暂无处理历史。', 'info')
    return
  }
  const historyText = historyItems
    .map(function formatHistoryItem(item) {
      return (item.beforeStatus || 'open') + ' -> ' + (item.afterStatus || 'open')
    })
    .join('；')
  notify('处理历史：' + historyText, 'info')
}

function applyClosureOverride(item = {}) {
  const override = riskClosureOverrides.value[item.riskId] || riskClosureOverrides.value[item.riskEventId]
  if (!override) {
    return {
      ...item,
      processStatus: processStatusFor(item.closureStatus),
      processStatusText: processStatusText(processStatusFor(item.closureStatus)),
    }
  }
  const closureStatus = override.closureStatus
  return {
    ...item,
    closureStatus,
    closureStatusText: closureStatusText(closureStatus),
    confirmStatus: override.confirmStatus || item.confirmStatus,
    confirmStatusText: override.confirmStatus ? confirmStatusText(override.confirmStatus) : item.confirmStatusText,
    processStatus: override.processStatus || processStatusFor(closureStatus),
    processStatusText: processStatusText(override.processStatus || processStatusFor(closureStatus)),
    reason: override.reason,
  }
}

function transitionRiskEvent(row = {}, afterStatus = 'open', reason = '', action = 'status_transition') {
  const riskId = row.riskId || row.riskEventId
  const beforeStatus = row.closureStatus || 'open'
  riskLifecycleState.value = transitionP2PRiskLifecycle({
    riskEventId: riskId,
    sourceDocument: row.sourceDocument || row.traceTarget?.purchaseOrder || '',
    beforeStatus,
    afterStatus,
    action,
    operator: '本地演示操作人',
    reason,
  })
}

function appendRiskConfirmHistory(row = {}, afterStatus = 'confirmed', confirmRemark = '') {
  return { row, afterStatus, confirmRemark }
}

function appendRiskProcessHistory(row = {}, afterStatus = 'processing', actionType = '', processRemark = '') {
  return { row, afterStatus, actionType, processRemark }
}

function confirmRiskEvent(row = {}) {
  if (!canConfirmRiskEvent(row)) {
    notify('当前风险事件不处于待处理状态，不能重复确认。', 'warning')
    return
  }
  const reason = isNormalBusinessModeRisk(row)
    ? '多供应商付款拆分提醒已确认属于正常业务模式，P2P节点全部正常。'
    : '风险已人工确认，进入后续处理判断。'
  transitionRiskEvent(row, 'confirmed', reason, 'confirm')
  notify('风险已确认。')
}

function startProcessingRiskEvent(row = {}) {
  if (!canStartProcessingRiskEvent(row)) {
    notify('当前风险事件不满足开始处理条件。', 'warning')
    return
  }
  const remark = '风险已进入处理中，本轮仅记录页面内状态流转。'
  transitionRiskEvent(row, 'processing', remark, 'start_processing')
  notify('风险已标记为处理中。')
}

function resolveRiskEvent(row = {}) {
  if (!canResolveRiskEvent(row)) {
    notify('当前风险事件不处于处理中，不能标记解决。', 'warning')
    return
  }
  const remark = '风险已标记解决，等待关闭验证。'
  transitionRiskEvent(row, 'resolved', remark, 'resolve')
  notify('风险已标记解决。')
}

function closeRiskEvent(row = {}) {
  if (!canCloseRiskEvent(row)) {
    notify('关闭风险需要先解决，或已确认属于正常业务模式。', 'warning')
    return
  }
  const reason = isNormalBusinessModeRisk(row)
    ? '正常业务模式已确认，关闭多供应商付款拆分提醒。'
    : '风险已解决并完成关闭验证。'
  transitionRiskEvent(row, 'closed', reason, 'close')
  notify('风险已关闭；当前风险列表将隐藏，历史风险保留。')
}

function confirmStatusText(status) {
  return displayLifecycleStatus(status)
}

function processStatusFor(closureStatus = 'open') {
  return {
    open: 'not_started',
    confirmed: 'not_started',
    processing: 'processing',
    resolved: 'resolved',
    closed: 'closed',
    ignored: 'closed',
  }[closureStatus] || 'not_started'
}

function processStatusText(status = 'not_started') {
  return displayLifecycleStatus(status)
}

function classifyRiskCause(risk = {}) {
  const text = [risk.riskType, risk.reason, risk.module].filter(Boolean).join(' ')
  if (text.includes('供应商链') || text.includes('多供应商')) return 'process_design_issue'
  if (text.includes('库存') || text.includes('入库') || text.includes('检验') || text.includes('收货')) return 'unknown'
  if (text.includes('报表')) return 'process_design_issue'
  if (text.includes('付款链')) return 'unknown'
  if (text.includes('金额')) return 'unknown'
  return 'unknown'
}

function resolutionSuggestionFor(causeType) {
  return {
    system_issue: '建议开发检查业务逻辑。',
    operation_issue: '建议补充业务操作。',
    test_data_issue: '建议重新生成测试链。',
    process_design_issue: '建议架构评估。',
    unknown: '需要人工确认：可能是仓库未操作、系统未生成或测试数据跳过。',
  }[causeType] || '需要人工确认后再决定处理方向。'
}

function responsibleModuleFor(risk = {}, causeType = '') {
  const text = [risk.riskType, risk.riskDescription, risk.reason, risk.sourceModule, risk.module].filter(Boolean).join(' ')
  if (causeType === 'process_design_issue' && (text.includes('多供应商') || text.includes('供应商链') || text.includes('结算'))) return 'SCM + Finance'
  if (text.includes('库存') || text.includes('入库') || text.includes('检验') || text.includes('收货')) return 'WMS/QMS'
  if (text.includes('付款') || text.includes('应付')) return 'Finance'
  if (causeType === 'test_data_issue') return 'TestData'
  if (causeType === 'system_issue') return 'ERP'
  if (causeType === 'process_design_issue') return 'Architecture'
  return risk.sourceModule || risk.module || 'ERP'
}

function responsibleRoleFor(moduleText = '') {
  if (moduleText.includes('SCM') && moduleText.includes('Finance')) return '采购负责人 / 财务负责人'
  if (moduleText.includes('WMS') || moduleText.includes('QMS')) return '仓库主管 / 质检负责人'
  if (moduleText.includes('Finance')) return '财务负责人'
  if (moduleText.includes('TestData')) return '测试数据负责人'
  if (moduleText.includes('Architecture')) return '业务架构负责人'
  return '待分配'
}

function buildP2PRiskReport(analysis = {}) {
  return (analysis.riskItems || []).map((risk, index) => {
    const riskCauseType = classifyRiskCause(risk)
    const isReportDesignRisk = risk.riskType === '报表验证风险' || risk.module === '报表'
    const closureStatus = isReportDesignRisk ? 'ignored' : 'open'
    return {
      riskId: 'P2P-RISK-' + String(index + 1).padStart(4, '0'),
      riskType: risk.riskType || '数据一致性风险',
      riskLevel: risk.level || '提醒',
      sourceModule: risk.module || '',
      sourceDocument: risk.sourceNo || '',
      breakPoint: risk.breakPoint || '',
      riskDescription: risk.reason || '',
      riskEvidence: risk.riskEvidence || null,
      inventoryRuleMatch: risk.inventoryRuleMatch || '',
      inventoryChainDecision: risk.inventoryChainDecision || null,
      traceResolverEvidence: risk.traceResolverEvidence || null,
      traceTarget: risk.traceTarget || null,
      settlementModelReminder: risk.settlementModelReminder || false,
      p2pNodeStatuses: risk.p2pNodeStatuses || [],
      possibleCause: riskCauseTypeText(riskCauseType),
      responsibleModule: risk.module || '',
      suggestedAction: risk.suggestion || resolutionSuggestionFor(riskCauseType),
      riskCauseType,
      riskCauseTypeText: riskCauseTypeText(riskCauseType),
      resolutionSuggestion: resolutionSuggestionFor(riskCauseType),
      closureStatus,
      closureStatusText: closureStatusText(closureStatus),
    }
  })
}

const p2pRiskReport = computed(() => buildP2PRiskReport(p2pRiskAnalysis.value))

function buildP2PRiskResponsibility(report = []) {
  return (report || []).map((item) => {
    const responsibleModule = responsibleModuleFor(item, item.riskCauseType)
    const confirmStatus = 'pending'
    return {
      riskId: item.riskId,
      riskType: item.riskType,
      riskLevel: item.riskLevel,
      sourceDocument: item.sourceDocument,
      riskDescription: item.riskDescription,
      riskCauseType: item.riskCauseType,
      riskCauseTypeText: item.riskCauseTypeText,
      riskCauseDetail: item.riskCauseType === 'unknown'
        ? '需要人工确认：仓库未操作、系统未生成、测试数据跳过或流程设计遗漏。'
        : item.possibleCause,
      responsibleModule,
      responsibleRole: responsibleRoleFor(responsibleModule),
      responsiblePerson: '待分配',
      confirmStatus,
      confirmStatusText: confirmStatusText(confirmStatus),
      confirmRemark: '本轮只做责任确认模型，不进行真实确认和派单。',
      suggestedAction: item.resolutionSuggestion,
      closureStatus: item.closureStatus,
      closureStatusText: item.closureStatusText,
    }
  })
}

const p2pRiskResponsibility = computed(() => buildP2PRiskResponsibility(p2pRiskReport.value))

function normalizeRiskType(item = {}) {
  const text = [item.riskType, item.riskDescription, item.sourceModule, item.breakPoint].filter(Boolean).join(' ')
  if (text.includes('多供应商付款拆分提醒')) return '多供应商付款拆分提醒'
  if (text.includes('多供应商') || text.includes('供应商链') || text.includes('结算')) return '多供应商链断裂'
  if (text.includes('库存') || text.includes('入库') || text.includes('检验') || text.includes('收货')) return '库存链异常'
  if (text.includes('金额') || text.includes('借贷')) return '金额异常'
  if (text.includes('付款') || text.includes('应付')) return '付款异常'
  if (text.includes('报表') || text.includes('总账')) return '报表异常'
  return item.riskType || '数据一致性风险'
}

function includesAny(text = '', keys = []) {
  return keys.some((key) => text.includes(key))
}

function displayRiskType(item = {}) {
  const text = [item.riskType, item.riskDescription, item.sourceModule, item.breakPoint].filter(Boolean).join(' ')
  if (includesAny(text, ['多供应商付款拆分提醒'])) return '多供应商付款拆分提醒'
  if (includesAny(text, ['多供应商', '供应商链', '结算'])) return '多供应商链断裂'
  if (includesAny(text, ['库存', '入库', '检验', '收货'])) return '库存链异常'
  if (includesAny(text, ['金额', '借贷', '付款超出应付'])) return '金额异常'
  if (includesAny(text, ['付款', '应付', '付款对象缺失'])) return '付款异常'
  if (includesAny(text, ['报表', '总账'])) return '报表异常'
  return item.riskType || normalizeRiskType(item) || '数据一致性风险'
}

function buildRiskActionInfo(item = {}, riskType = '', responsibleModule = '') {
  const text = [riskType, item.riskDescription, item.breakPoint, item.riskCauseType, item.sourceModule].filter(Boolean).join(' ')
  const isSettlementReminder = item.settlementModelReminder || text.includes('多供应商付款拆分提醒')
  const isCritical = !isSettlementReminder && includesAny(text, ['多供应商链断裂', '库存流水缺失', '付款超出应付', '付款对象缺失', '已确认断裂'])
  const isDesign = includesAny(text, ['报表异常', '总账未真实写入', '设计', '报表验证风险'])
  if (isCritical) {
    return {
      riskActionLevel: 'critical',
      riskActionLevelText: '严重风险 / 需要责任部门处理',
      riskActionRequired: true,
      riskColor: 'danger',
      confirmRequired: false,
      responsibleAction: '必须处理',
      riskOwnerRequired: {
        module: responsibleModule || '待确认',
        role: responsibleRoleFor(responsibleModule || ''),
      },
    }
  }
  if (isDesign) {
    return {
      riskActionLevel: 'info',
      riskActionLevelText: '设计提醒',
      riskActionRequired: false,
      riskColor: 'info',
      confirmRequired: false,
      responsibleAction: '设计提醒',
      riskOwnerRequired: {
        module: responsibleModule || 'Architecture',
        role: responsibleRoleFor(responsibleModule || 'Architecture'),
      },
    }
  }
  return {
    riskActionLevel: 'warning',
    riskActionLevelText: '待确认',
    riskActionRequired: false,
    riskColor: 'warning',
    confirmRequired: true,
    responsibleAction: '人工确认',
    riskOwnerRequired: {
      module: responsibleModule || '待确认',
      role: responsibleRoleFor(responsibleModule || ''),
    },
  }
}

function buildP2PRiskClosureCenter(report = [], responsibility = []) {
  const responsibilityMap = new Map((responsibility || []).map((item) => [item.riskId, item]))
  const riskItems = (report || []).map((item) => {
    const owner = responsibilityMap.get(item.riskId) || {}
    const riskType = displayRiskType(item)
    const responsibleModule = owner.responsibleModule || item.responsibleModule || ''
    const actionInfo = buildRiskActionInfo(item, riskType, responsibleModule)
    return {
      riskId: item.riskId,
      riskLevel: item.riskLevel,
      riskType,
      sourceDocument: item.sourceDocument,
      sourceModule: item.sourceModule,
      breakPoint: item.breakPoint,
      riskDescription: item.riskDescription,
      riskEvidence: item.riskEvidence || null,
      inventoryRuleMatch: item.inventoryRuleMatch || '',
      inventoryChainDecision: item.inventoryChainDecision || null,
      traceResolverEvidence: item.traceResolverEvidence || null,
      traceTarget: item.traceTarget || null,
      settlementModelReminder: item.settlementModelReminder || false,
      p2pNodeStatuses: item.p2pNodeStatuses || [],
      riskCauseType: item.riskCauseType,
      riskCauseTypeText: item.riskCauseTypeText,
      responsibleModule,
      responsibleRole: owner.responsibleRole || '',
      suggestedAction: owner.suggestedAction || item.resolutionSuggestion || item.suggestedAction || '',
      confirmStatus: owner.confirmStatus || 'pending',
      confirmStatusText: owner.confirmStatusText || confirmStatusText('pending'),
      confirmRemark: owner.confirmRemark || '',
      closureStatus: owner.closureStatus || item.closureStatus || 'open',
      closureStatusText: owner.closureStatusText || item.closureStatusText || closureStatusText('open'),
      processStatus: processStatusFor(owner.closureStatus || item.closureStatus || 'open'),
      processStatusText: processStatusText(processStatusFor(owner.closureStatus || item.closureStatus || 'open')),
      ...actionInfo,
    }
  })
  return {
    riskCount: riskItems.length,
      criticalCount: riskItems.filter((item) => item.riskLevel === '严重').length,
      warningCount: riskItems.filter((item) => item.riskLevel !== '严重').length,
    openCount: riskItems.filter((item) => item.closureStatus === 'open').length,
    resolvedCount: riskItems.filter((item) => item.closureStatus === 'resolved').length,
    criticalActionCount: riskItems.filter((item) => item.riskActionLevel === 'critical').length,
    confirmRequiredCount: riskItems.filter((item) => item.riskActionLevel === 'warning').length,
    designReminderCount: riskItems.filter((item) => item.riskActionLevel === 'info').length,
    normalCount: riskItems.filter((item) => item.riskActionLevel === 'normal').length,
    riskItems,
  }
}

const p2pRiskClosureCenter = computed(() => buildP2PRiskClosureCenter(p2pRiskReport.value, p2pRiskResponsibility.value))

function normalizeRiskEventBreakPoint(item = {}) {
  const text = [item.riskType, item.breakPoint, item.riskDescription].filter(Boolean).join(' ')
  if (item.riskType === '库存链异常' && includesAny(text, ['库存金额', '无法追踪', '入库'])) return '入库'
  if (item.riskType === '库存链异常' && includesAny(text, ['库存流水'])) return '库存流水'
  return item.breakPoint || '未指定断点'
}

function buildTraceTarget(item = {}, breakPoint = '') {
  const sourceDocument = item.sourceDocument || item.sourceNo || ''
  const resolvedTrace = resolveP2PTrace(sourceDocument, {})
  const inventoryTransactionNos = (resolvedTrace.inventoryTransactions || []).map((transaction) => transaction.transactionNo || transaction.id).filter(Boolean)
  return normalizeTraceTarget({
    purchaseOrder: recordNo(resolvedTrace.purchaseOrder || {}, ['poNo', 'purchaseOrderNo', 'orderNo']) || sourceDocument,
    receipt: recordNo(resolvedTrace.receipt || {}, ['receiveNo', 'sourceReceiveNo']) || item.sourceReceiveNo || item.receiptNo || '',
    inspection: recordNo(resolvedTrace.inspection || {}, ['inspectionNo', 'sourceInspectionNo']) || item.sourceInspectionNo || item.inspectionNo || '',
    warehouseEntry: resolvedTrace.warehouseEntry || item.sourceWarehouseEntryNo || item.warehouseEntryNo || '',
    inventoryTransaction: inventoryTransactionNos.join('、') || item.sourceInventoryTransactionNo || item.inventoryTransactionNo || '',
    payable: resolvedTrace.payable || item.sourcePayableNo || item.sourceApDraftNo || item.payableNo || '',
    paymentVoucher: resolvedTrace.paymentVoucher || item.sourcePaymentVoucherNo || item.paymentVoucherNo || item.sourceDocument || '',
    breakPoint,
    riskType: item.riskType || '',
    riskDescription: item.riskDescription || '',
  })
}

function buildRiskEventCenter(closureCenter = {}) {
  const eventMap = new Map()
  let beforeImpactCount = 0
  ;(closureCenter.riskItems || []).forEach((item) => {
    const breakPoint = normalizeRiskEventBreakPoint(item)
    const key = [item.sourceDocument || '-', breakPoint, item.riskType || '-'].join('::')
    const defaultTraceEvidence = resolveP2PTrace(item.sourceDocument || item.sourceNo || '', {}).traceResolverEvidence
    const current = eventMap.get(key) || {
      riskEventId: 'P2P-EVENT-' + String(eventMap.size + 1).padStart(4, '0'),
      riskId: 'P2P-EVENT-' + String(eventMap.size + 1).padStart(4, '0'),
      riskType: item.riskType,
      riskLevel: item.riskLevel,
      sourceDocument: item.sourceDocument,
      sourceModule: item.sourceModule,
      breakPoint,
      riskEvidence: item.riskEvidence || null,
      inventoryRuleMatch: item.inventoryRuleMatch || '',
      inventoryChainDecision: item.inventoryChainDecision || null,
      traceResolverEvidence: item.traceResolverEvidence || defaultTraceEvidence || null,
      causeType: item.riskCauseType,
      riskCauseType: item.riskCauseType,
      riskCauseTypeText: item.riskCauseTypeText,
      responsibleModule: item.responsibleModule,
      responsibleRole: item.responsibleRole,
      suggestedAction: item.suggestedAction,
      confirmStatus: item.confirmStatus,
      confirmStatusText: item.confirmStatusText,
      closureStatus: item.closureStatus,
      closureStatusText: item.closureStatusText,
      riskActionLevel: item.riskActionLevel,
      riskActionLevelText: item.riskActionLevelText,
      riskActionRequired: item.riskActionRequired,
      riskColor: item.riskColor,
      confirmRequired: item.confirmRequired,
      responsibleAction: item.responsibleAction,
      riskOwnerRequired: item.riskOwnerRequired,
      settlementModelReminder: item.settlementModelReminder || false,
      p2pNodeStatuses: item.p2pNodeStatuses || [],
      traceTarget: normalizeTraceTarget({ ...buildTraceTarget(item, breakPoint), ...(item.traceTarget || {}) }),
      impacts: [],
    }
    beforeImpactCount += 1
    current.impacts.push({
      impactType: item.breakPoint || item.riskType || '风险影响',
      impactDescription: item.riskDescription || item.suggestedAction || '风险影响待确认',
    })
    current.impactCount = current.impacts.length
    eventMap.set(key, current)
  })
  const riskEvents = Array.from(eventMap.values()).map((event) => {
    const impactMap = new Map()
    ;(event.impacts || []).forEach((impact) => {
      const key = (impact.impactType || '') + '::' + (impact.impactDescription || '')
      if (!impactMap.has(key)) impactMap.set(key, impact)
    })
    const impacts = Array.from(impactMap.values())
    return normalizeRiskEvent({
      ...event,
      impacts,
      impactCount: impacts.length,
    })
  })
  const impactCount = riskEvents.reduce((total, event) => total + event.impacts.length, 0)
  const removedDuplicateImpactCount = Math.max(beforeImpactCount - impactCount, 0)
  return {
    riskEventCount: riskEvents.length,
    impactCount,
    duplicateRiskCount: Math.max(impactCount - riskEvents.length, 0),
    riskEventImpactValidation: {
      eventCount: riskEvents.length,
      beforeImpactCount,
      afterImpactCount: impactCount,
      removedDuplicateImpactCount,
    },
    riskEvents,
  }
}

const riskEventCenter = computed(() => buildRiskEventCenter(p2pRiskClosureCenter.value))

const lifecycleRiskEvents = computed(() => riskEventCenter.value.riskEvents.map((item) => applyClosureOverride(item)))

const riskLifecycleSummary = computed(() => {
  const events = lifecycleRiskEvents.value
  const isClosedForDisplay = (item) => ['closed', 'ignored'].includes(item.closureStatus) || item.processStatus === 'closed'
  const closedEvents = events.filter((item) => item.closureStatus === 'closed' || item.processStatus === 'closed')
  const historyEvents = events.filter((item) => isClosedForDisplay(item))
  const processingEvents = events.filter((item) => item.closureStatus === 'processing')
  const currentEvents = events.filter((item) => !isClosedForDisplay(item))
  return {
    currentCount: currentEvents.length,
    processingCount: processingEvents.length,
    closedCount: closedEvents.length,
    historyCount: historyEvents.length,
    riskLifecycleHistory: riskLifecycleHistory.value,
    riskClosureHistory: riskClosureHistory.value,
    riskConfirmHistory: riskConfirmHistory.value,
    riskProcessHistory: riskProcessHistory.value,
  }
})

const filteredP2PRiskClosureItems = computed(() => p2pRiskClosureCenter.value.riskItems.filter((item) => {
  const riskTypeMatched = !riskTypeFilter.value || decodeDisplayText(item.riskType) === riskTypeFilter.value
  const causeMatched = !riskCauseFilter.value || item.riskCauseType === riskCauseFilter.value
  const moduleMatched = !responsibleModuleFilter.value || (item.responsibleModule || '').includes(responsibleModuleFilter.value)
  return riskTypeMatched && causeMatched && moduleMatched
}))

const filteredRiskEvents = computed(() => lifecycleRiskEvents.value.filter((item) => {
  const riskTypeMatched = !riskTypeFilter.value || decodeDisplayText(item.riskType) === riskTypeFilter.value
  const causeMatched = !riskCauseFilter.value || item.causeType === riskCauseFilter.value
  const moduleMatched = !responsibleModuleFilter.value || (item.responsibleModule || '').includes(responsibleModuleFilter.value)
  const status = item.closureStatus || 'open'
  const isHistory = ['closed', 'ignored'].includes(status) || item.processStatus === 'closed'
  const lifecycleMatched = lifecycleViewFilter.value === 'all'
    ? !isHistory
    : lifecycleViewFilter.value === 'history'
    ? false
    : lifecycleViewFilter.value === 'closed'
      ? false
      : lifecycleViewFilter.value === 'processing'
        ? status === 'processing'
        : lifecycleViewFilter.value === 'resolved'
          ? status === 'resolved'
          : lifecycleViewFilter.value === 'open'
            ? status === 'open'
            : !isHistory
  return riskTypeMatched && causeMatched && moduleMatched && lifecycleMatched
}))

const historyRiskEvents = computed(() => lifecycleRiskEvents.value.filter((item) => {
  const status = item.closureStatus || 'open'
  return ['closed', 'ignored'].includes(status) || item.processStatus === 'closed'
}))

const lifecycleFlowSteps = [
  { key: 'open', label: '风险发现' },
  { key: 'confirmed', label: '风险确认' },
  { key: 'start_processing', label: '开始处理' },
  { key: 'processing', label: '处理中' },
  { key: 'resolved', label: '标记解决' },
  { key: 'closed', label: '关闭验证' },
]

function lifecycleStepIndex(status = 'open') {
  return {
    open: 0,
    confirmed: 1,
    processing: 3,
    resolved: 4,
    closed: 5,
    ignored: 5,
  }[status] ?? 0
}

const activeLifecycleFlow = computed(() => {
  const active = filteredRiskEvents.value[0] || lifecycleRiskEvents.value[0] || {}
  const currentIndex = lifecycleStepIndex(active.closureStatus || 'open')
  const steps = lifecycleFlowSteps.map((step, index) => ({
    ...step,
    state: index < currentIndex ? 'completed' : (index === currentIndex ? 'current' : 'pending'),
  }))
  return {
    raw: active,
    riskId: decodeDisplayText(active.riskId || active.riskEventId, '待选择'),
    sourceDocument: decodeDisplayText(active.sourceDocument || active.traceTarget?.purchaseOrder, '待选择'),
    riskType: decodeDisplayText(active.riskType, '待选择'),
    currentStatusText: decodeDisplayText(active.closureStatusText || closureStatusText(active.closureStatus || 'open'), '待处理'),
    responsibleModule: decodeDisplayText(active.responsibleModule, '待确认'),
    responsibleRole: decodeDisplayText(active.responsibleRole, '待分配'),
    steps,
  }
})

const riskEventCenterView = computed(() => ({
  eventCount: riskEventCenter.value.riskEventCount,
  impactCount: riskEventCenter.value.impactCount,
  duplicateCount: riskEventCenter.value.duplicateRiskCount,
  displayEvents: filteredRiskEvents.value,
}))

const p2pRiskScoreFoundation = computed(() => {
  const events = riskEventCenter.value.riskEvents || []
  return {
    eventCount: riskEventCenter.value.riskEventCount,
    impactCount: riskEventCenter.value.impactCount,
    duplicateCount: riskEventCenter.value.duplicateRiskCount,
    criticalEventCount: events.filter((item) => item.riskActionLevel === 'critical').length,
    warningEventCount: events.filter((item) => item.riskActionLevel === 'warning').length,
    designReminderCount: events.filter((item) => item.riskActionLevel === 'info').length,
    eventWeightRule: '一个业务断点只计算一个风险事件，后续评分以风险事件作为主计数口径。',
    impactWeightRule: '同一风险事件下的多个影响项只作为影响范围说明，不重复放大风险事件数量。',
    severityRule: {
      critical: '必须处理，后续评分权重最高。',
      warning: '需要人工确认，后续评分按待确认风险处理。',
      info: '设计提醒，后续评分作为能力缺口或观察项处理。',
    },
    ownerRule: 'riskOwnerRequired 仅作为责任归属和评分维度预留，本轮不派单、不写状态。',
  }
})

const validationModules = computed(() => {
  const list = vouchers.value || []
  const supplierNames = list.map((item) => item.supplierName)
  const purchaseOrders = list.map((item) => item.sourcePurchaseOrderNo)
  const receipts = list.map((item) => item.sourceReceiveNo)
  const inspections = list.map((item) => item.sourceInspectionNo)
  const payableRefs = list.map((item) => item.sourceApDraftNo || item.sourcePayableCheckNo || item.sourcePayablePrepareNo)
  const paymentRefs = list.map((item) => item.sourcePaymentExecutionNo || item.sourcePaymentRecordReviewNo)
  const ledgerBalancedCount = list.filter((item) => amount(item.debitAmount) === amount(item.creditAmount)).length
  const totalVoucherAmount = amount(list.reduce((total, item) => total + voucherAmount(item), 0))
  const totalLineAmount = amount(list.reduce((total, item) => total + lineAmount(item), 0))

  return [
    buildModule('purchase', '采购订单一致性验证', '验证采购订单金额、供应商数量和订单明细金额是否具备可追溯基础。', [
      { label: '正式付款凭证数', value: list.length },
      { label: '采购订单数量', value: uniqueCount(purchaseOrders) },
      { label: '供应商数量', value: uniqueCount(supplierNames) },
      { label: '凭证金额合计', value: totalVoucherAmount },
    ], [], list.some((item) => !hasText(item.sourcePurchaseOrderNo)) ? ['存在缺少来源采购订单号的正式付款凭证。'] : []),
    buildModule('supplier', '供应商一致性验证', '验证供应商多个订单累计金额是否能按供应商维度归集。', [
      { label: '供应商数量', value: uniqueCount(supplierNames) },
      { label: '缺少供应商记录', value: list.filter((item) => !hasText(item.supplierName)).length },
      { label: '付款凭证金额', value: totalVoucherAmount },
    ], list.length && uniqueCount(supplierNames) <= 1 ? ['当前只识别到一个供应商；如果来源采购订单实际为多供应商，需要继续核对供应商链路。'] : [], list.some((item) => !hasText(item.supplierName)) ? ['存在缺少供应商名称的正式付款凭证。'] : []),
    buildModule('receipt', '收货一致性验证', '验证采购订单到收货数量、收货金额的引用是否存在。', [
      { label: '收货单数量', value: uniqueCount(receipts) },
      { label: '缺少收货引用', value: list.filter((item) => !hasText(item.sourceReceiveNo)).length },
    ], [], list.some((item) => !hasText(item.sourceReceiveNo)) ? ['存在缺少来源收货单号的正式付款凭证。'] : []),
    buildModule('inspection', '检验一致性验证', '验证收货、检验、合格数量之间是否具备来源引用。', [
      { label: '检验单数量', value: uniqueCount(inspections) },
      { label: '缺少检验引用', value: list.filter((item) => !hasText(item.sourceInspectionNo)).length },
    ], [], list.some((item) => !hasText(item.sourceInspectionNo)) ? ['存在缺少来源检验单号的正式付款凭证。'] : []),
    buildModule('inventoryChain', '库存链一致性验证', '验证采购订单 -> 收货单 -> 检验单 -> 入库单 -> 库存流水链路是否连续。', [
      { label: '验证凭证数', value: inventoryChainValidation.value.inventoryChainValidationItems.length },
      { label: '缺少库存流水', value: inventoryChainValidation.value.inventoryRiskSummary.missingInventoryLedgerCount },
      { label: '链路风险总数', value: inventoryChainValidation.value.inventoryRiskSummary.riskCount },
    ], inventoryChainValidation.value.inventoryRiskSummary.riskTypes.filter((item) => item.count > 0).map((item) => item.type + '：' + item.count + ' 条'), inventoryChainValidation.value.inventoryRiskSummary.riskCount ? ['库存链一致性验证发现 ' + inventoryChainValidation.value.inventoryRiskSummary.riskCount + ' 个风险点。'] : []),
    buildModule('inventory', '入库一致性验证', '验证收货、入库、库存影响之间是否具备库存流水引用。', [
      { label: '库存流水数量', value: uniqueCount(inventoryChainValidation.value.inventoryChainValidationItems.flatMap((item) => item.inventoryTransactionNos || [])) },
      { label: '缺少库存流水', value: inventoryChainValidation.value.inventoryRiskSummary.missingInventoryLedgerCount },
    ], [], inventoryChainValidation.value.inventoryRiskSummary.missingInventoryLedgerCount ? ['存在缺少库存流水来源的正式付款凭证。'] : []),
    buildModule('payable', '应付一致性验证', '验证采购、收货、应付之间的来源链是否具备应付引用。', [
      { label: '应付来源数量', value: uniqueCount(payableRefs) },
      { label: '缺少应付引用', value: list.filter((item) => !hasText(item.sourceApDraftNo || item.sourcePayableCheckNo || item.sourcePayablePrepareNo)).length },
    ], [], list.some((item) => !hasText(item.sourceApDraftNo || item.sourcePayableCheckNo || item.sourcePayablePrepareNo)) ? ['存在缺少应付来源的正式付款凭证。'] : []),
    buildModule('payment', '付款一致性验证', '验证应付、付款、付款记录之间是否具备付款执行引用。', [
      { label: '付款执行/记录数量', value: uniqueCount(paymentRefs) },
      { label: '缺少付款记录', value: list.filter((item) => !hasText(item.sourcePaymentExecutionNo || item.sourcePaymentRecordReviewNo)).length },
    ], [], list.some((item) => !hasText(item.sourcePaymentExecutionNo || item.sourcePaymentRecordReviewNo)) ? ['存在缺少付款执行或付款记录复核来源的正式付款凭证。'] : []),
    buildModule('ledger', '模拟总账一致性验证', '验证付款到模拟分录、借贷平衡之间是否具备一致性。', [
      { label: '借贷平衡凭证数', value: ledgerBalancedCount },
      { label: '凭证数', value: list.length },
      { label: '分录金额合计', value: totalLineAmount },
    ], [], list.some((item) => amount(item.debitAmount) !== amount(item.creditAmount)) ? ['存在借贷金额不一致的正式付款凭证。'] : []),
    buildModule('report', '报表一致性验证', '验证科目余额表、资产负债表、供应商往来表、库存结存表、银行余额表的未来验证入口。', [
      { label: '报表验证对象', value: '5类' },
      { label: '当前真实写入', value: '未写总账' },
      { label: '当前核销状态', value: '未核销' },
    ], ['报表一致性仍是设计级验证，需要等待真实总账写入前复核和基础验证数据后再执行真实报表校验。']),
  ]
})

const riskSummary = computed(() => {
  const riskItems = []
  validationModules.value.forEach((module) => {
    module.warnings.forEach((warning) => {
      riskItems.push({
        type: warning.includes('供应商') ? '供应商链断裂'
          : warning.includes('金额') || warning.includes('借贷') ? '金额不一致'
            : warning.includes('收货') ? '收货缺失'
              : warning.includes('库存') ? '入库缺失'
                : warning.includes('应付') ? '应付缺失'
                  : warning.includes('付款') ? '付款异常'
                  : warning.includes('总账') || warning.includes('报表') ? '总账模拟异常'
                      : '数据一致性提醒',
        level: module.criticalWarnings.includes(warning) ? '严重' : '提醒',
        module: module.title,
        message: warning,
      })
    })
  })
  return {
    riskCount: riskItems.length,
    criticalCount: riskItems.filter((item) => item.level === '严重').length,
    warningCount: riskItems.filter((item) => item.level === '提醒').length,
    riskItems,
  }
})

const passedCount = computed(() => validationModules.value.filter((item) => item.status === 'passed').length)
const centerStatus = computed(() => riskSummary.value.criticalCount ? 'blocked' : (riskSummary.value.warningCount ? 'warning' : 'passed'))
const centerStatusText = computed(() => centerStatus.value === 'passed' ? '验证通过' : (centerStatus.value === 'blocked' ? '验证阻断' : '验证有提醒'))
const centerStatusType = computed(() => moduleStatusType(centerStatus.value))
const centerConclusion = computed(() => {
  if (centerStatus.value === 'passed') return 'P2P验证中心当前未发现设计级风险。'
  if (centerStatus.value === 'blocked') return 'P2P验证中心发现严重数据链路风险，本轮只提示，不反向修改业务。'
  return 'P2P验证中心发现提醒项，本轮只做只读验证设计。'
})

function moduleStatusType(status) {
  if (status === 'passed') return 'success'
  if (status === 'blocked') return 'danger'
  if (status === 'warning') return 'warning'
  return 'info'
}

function riskLevelType(level) {
  return decodeDisplayText(level) === '严重' ? 'danger' : 'warning'
}

function decodeDiagnosticPayload(value) {
  if (Array.isArray(value)) return value.map((item) => decodeDiagnosticPayload(item))
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, decodeDiagnosticPayload(item)]))
  }
  if (typeof value === 'string') return decodeDisplayText(value, '')
  return value
}

function buildDiagnosticPayload() {
  return {
    version: 'V1.13.24',
    type: 'p2p-validation-center-diagnostic',
    copiedAt: new Date().toISOString(),
    p2pValidationCenterStatus: centerStatus.value,
    p2pValidationCenterConclusion: centerConclusion.value,
    p2pValidationModules: validationModules.value,
    p2pValidationRiskSummary: riskSummary.value,
    p2pRiskAnalysis: p2pRiskAnalysis.value,
    p2pRiskReport: p2pRiskReport.value,
    p2pRiskResponsibility: p2pRiskResponsibility.value,
    p2pRiskClosureCenter: p2pRiskClosureCenter.value,
    riskEventCenter: riskEventCenter.value,
    p2pRiskLifecycle: riskLifecycleSummary.value,
    riskClosureHistory: riskClosureHistory.value,
    riskConfirmHistory: riskConfirmHistory.value,
    riskProcessHistory: riskProcessHistory.value,
    riskEventImpactValidation: riskEventCenter.value.riskEventImpactValidation,
    riskEventCenterView: riskEventCenterView.value,
    p2pRiskScoreFoundation: p2pRiskScoreFoundation.value,
    riskEvidence: p2pRiskReport.value.map((item) => ({
      riskId: item.riskId,
      sourceDocument: item.sourceDocument,
      riskEvidence: item.riskEvidence,
    })),
    inventoryRuleMatch: inventoryChainValidation.value.inventoryChainValidationItems.map((item) => ({
      purchaseOrderNo: item.purchaseOrderNo,
      inventoryRuleMatch: item.inventoryRuleMatch,
    })),
    inventoryChainDecision: inventoryChainValidation.value.inventoryChainValidationItems.map((item) => ({
      purchaseOrderNo: item.purchaseOrderNo,
      inventoryChainDecision: item.inventoryChainDecision,
    })),
    traceResolverEvidence: inventoryChainValidation.value.inventoryChainValidationItems.map((item) => ({
      purchaseOrderNo: item.purchaseOrderNo,
      traceResolverEvidence: item.traceResolverEvidence,
    })),
    p2pNodeStatuses: inventoryChainValidation.value.inventoryChainValidationItems.map((item) => ({
      purchaseOrderNo: item.purchaseOrderNo,
      p2pNodeStatuses: item.p2pNodeStatuses,
    })),
    riskActionLevel: p2pRiskClosureCenter.value.riskItems.map((item) => ({
      riskId: item.riskId,
      riskActionLevel: item.riskActionLevel,
      riskActionLevelText: item.riskActionLevelText,
      responsibleAction: item.responsibleAction,
    })),
    riskColor: p2pRiskClosureCenter.value.riskItems.map((item) => ({
      riskId: item.riskId,
      riskColor: item.riskColor,
    })),
    riskOwnerRequired: p2pRiskClosureCenter.value.riskItems.map((item) => ({
      riskId: item.riskId,
      riskOwnerRequired: item.riskOwnerRequired,
    })),
    confirmRequired: p2pRiskClosureCenter.value.riskItems.map((item) => ({
      riskId: item.riskId,
      confirmRequired: item.confirmRequired,
    })),
    riskCauseType: p2pRiskReport.value.map((item) => ({
      riskId: item.riskId,
      riskCauseType: item.riskCauseType,
      riskCauseTypeText: item.riskCauseTypeText,
    })),
    responsibleModule: p2pRiskResponsibility.value.map((item) => ({
      riskId: item.riskId,
      responsibleModule: item.responsibleModule,
    })),
    responsibleRole: p2pRiskResponsibility.value.map((item) => ({
      riskId: item.riskId,
      responsibleRole: item.responsibleRole,
    })),
    confirmStatus: p2pRiskResponsibility.value.map((item) => ({
      riskId: item.riskId,
      confirmStatus: item.confirmStatus,
      confirmStatusText: item.confirmStatusText,
    })),
    confirmRemark: p2pRiskResponsibility.value.map((item) => ({
      riskId: item.riskId,
      confirmRemark: item.confirmRemark,
    })),
    resolutionSuggestion: p2pRiskReport.value.map((item) => ({
      riskId: item.riskId,
      resolutionSuggestion: item.resolutionSuggestion,
    })),
    closureStatus: p2pRiskReport.value.map((item) => ({
      riskId: item.riskId,
      closureStatus: item.closureStatus,
      closureStatusText: item.closureStatusText,
    })),
    inventoryChainValidationStatus: inventoryChainValidation.value.inventoryChainValidationStatus,
    inventoryChainValidationConclusion: inventoryChainValidation.value.inventoryChainValidationConclusion,
    inventoryChainValidationItems: inventoryChainValidation.value.inventoryChainValidationItems,
    inventoryChainRiskSummary: inventoryChainValidation.value.inventoryRiskSummary,
    purchaseReceiptCheckStatus: inventoryChainValidation.value.purchaseReceiptCheckStatus,
    inspectionInventoryCheckStatus: inventoryChainValidation.value.inspectionInventoryCheckStatus,
    warehouseEntryCheckStatus: inventoryChainValidation.value.warehouseEntryCheckStatus,
    inventoryLedgerCheckStatus: inventoryChainValidation.value.inventoryLedgerCheckStatus,
    financeFieldProtection: {
      postingStatusChanged: false,
      ledgerStatusChanged: false,
      paymentWriteOffStatusChanged: false,
      ledgerEntryGenerated: false,
      bankFlowGenerated: false,
      localStorageWrittenByValidationCenter: false,
    },
  }
}

async function copyTextToClipboard(text) {
  if (navigator?.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text)
      return
    } catch (error) {
      // Continue to textarea fallback.
    }
  }
  const textarea = document.createElement('textarea')
  textarea.value = text
  textarea.setAttribute('readonly', 'readonly')
  textarea.style.position = 'fixed'
  textarea.style.left = '-9999px'
  document.body.appendChild(textarea)
  textarea.select()
  const copied = document.execCommand('copy')
  document.body.removeChild(textarea)
  if (!copied) throw new Error('copy failed')
}

async function copyDiagnostic() {
  try {
    await copyTextToClipboard(JSON.stringify(decodeDiagnosticPayload(normalizeDiagnosticEvidence(buildDiagnosticPayload())), null, 2))
      notify('已复制P2P验证中心诊断数据。')
    } catch (error) {
      notify('复制失败，请重试。', 'warning')
  }
}
</script>

<style scoped>
.p2p-validation-center-page {
  padding: 24px;
  color: #1f2937;
}

.page-header,
.card-header,
.module-card-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.eyebrow {
  margin: 0 0 8px;
  color: #2563eb;
  font-weight: 700;
}

.page-header h1,
.card-header h2,
.module-card h2 {
  margin: 0;
}

.page-tabs,
.button-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.filter-row,
.closure-flow {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  margin-bottom: 12px;
}

.closure-flow span {
  padding: 8px 12px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  background: #f9fafb;
  color: #6b7280;
  font-weight: 600;
}

.closure-flow .flow-step {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.closure-flow .flow-step-completed {
  border-color: #bbf7d0;
  background: #f0fdf4;
  color: #166534;
}

.closure-flow .flow-step-current {
  border-color: #93c5fd;
  background: #eff6ff;
  color: #1d4ed8;
}

.closure-flow .flow-step-pending {
  border-color: #e5e7eb;
  background: #f9fafb;
  color: #6b7280;
}

.lifecycle-current-card {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 10px;
  align-items: stretch;
  margin-bottom: 12px;
}

.lifecycle-current-card article {
  padding: 10px 12px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  background: #fff;
}

.lifecycle-current-card span {
  display: block;
  color: #6b7280;
  font-size: 13px;
}

.lifecycle-current-card strong {
  display: block;
  margin-top: 5px;
  overflow-wrap: anywhere;
}

.finance-nav-button {
  padding: 8px 12px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  color: #374151;
  text-decoration: none;
  background: #fff;
}

.finance-nav-button-active {
  border-color: #2563eb;
  color: #1d4ed8;
}

.trace-link {
  color: #2563eb;
  font-weight: 700;
  text-decoration: none;
}

.trace-link:hover {
  text-decoration: underline;
}

.finance-current-tag {
  margin-left: 6px;
  font-size: 12px;
}

.finance-current-module-badge,
.boundary-note {
  padding: 10px 12px;
  border-radius: 6px;
  background: #eff6ff;
  color: #1e40af;
}

.operation-shell {
  display: grid;
  gap: 16px;
  margin-top: 16px;
}

.plain-flow-guide {
  padding: 16px;
  border: 1px solid #dbeafe;
  border-radius: 8px;
  background: #f8fbff;
}

.plain-flow-grid,
.risk-management-flow,
.overview-grid,
.module-result {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
  margin-top: 12px;
}

.plain-flow-grid span,
.risk-management-flow article,
.overview-grid article,
.module-result article {
  padding: 12px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  background: #fff;
}

.risk-management-flow span,
.overview-grid span,
.module-result span {
  display: block;
  color: #6b7280;
  font-size: 13px;
}

.risk-management-flow strong,
.overview-grid strong,
.module-result strong {
  display: block;
  margin-top: 6px;
}

.risk-management-flow small,
.overview-grid small {
  display: block;
  margin-top: 6px;
  color: #6b7280;
  font-size: 12px;
  line-height: 1.45;
}

.module-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 16px;
}

.module-card {
  min-height: 260px;
}

.module-desc {
  color: #4b5563;
}

.module-warnings {
  margin: 12px 0 0;
  padding-left: 18px;
  color: #374151;
}
</style>


