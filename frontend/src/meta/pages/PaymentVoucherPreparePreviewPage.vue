<template>
  <main class="payment-voucher-prepare-preview-page app-page-shell">
    <section class="app-hero-section">
      <div>
        <p class="app-eyebrow" data-acceptance-id="page-version">{{ version }} · Finance</p>
        <h1>付款凭证准备人工验收可达性、横向滚动与页面文案一致性修复</h1>
        <p class="app-hero-copy">
          本页只展示付款凭证准备模拟执行前的权限、二次确认、零业务写入沙箱、验收清单和运行时可观测性。
          本轮不启动状态机，不创建模拟请求，不执行模拟，不创建模拟结果，不生成付款凭证，不写正式业务数据。
        </p>
      </div>
      <div class="page-actions">
        <router-link class="app-nav-button" to="/finance/payment-execution-prepares">返回付款执行准备</router-link>
        <router-link class="app-nav-button" to="/finance/settlement-boundary-overview">企业结算边界</router-link>
      </div>
    </section>

    <section class="manual-acceptance-navigation" data-acceptance-id="manual-acceptance-navigation">
      <div class="manual-acceptance-heading">
        <div>
          <h2>{{ businessAcceptanceSectionTitles.manualNavigation }}</h2>
          <p>本区域用于人工验收定位，按钮只跳转页面锚点，不触发状态机、不创建模拟请求、不写业务数据。</p>
        </div>
        <el-button type="primary" plain @click="copyPageAcceptanceChecklist">复制本页验收清单</el-button>
      </div>
      <div class="manual-acceptance-meta">
        <article>
          <span>当前完整链接</span>
          <strong data-acceptance-id="acceptance-current-full-url">{{ currentFullUrl }}</strong>
        </article>
        <article>
          <span>当前版本</span>
          <strong data-acceptance-id="acceptance-current-version">{{ version }}</strong>
        </article>
        <article>
          <span>来源对象编号</span>
          <strong data-acceptance-id="business-action-source-number">{{ paymentExecutionPrepareNoText }}</strong>
        </article>
        <article>
          <span>目标对象编号</span>
          <strong>{{ targetObjectNoDisplay }}</strong>
        </article>
        <article>
          <span>目标证据状态</span>
          <strong>{{ targetEvidenceStatusText }}</strong>
        </article>
      </div>
      <div class="manual-acceptance-links">
        <button
          v-for="item in businessAcceptanceNavigationItems"
          :key="item.targetId"
          type="button"
          class="app-nav-button"
          @click="jumpToAcceptanceSection(item.targetId)"
        >
          {{ item.label }}
        </button>
      </div>
      <p class="helper-text">
        Ctrl+F 搜索词：{{ businessAcceptanceCtrlFSearchTerms.join(' / ') }}
      </p>
    </section>

    <section id="target-evidence-summary-section" class="table-card acceptance-visible-card" data-acceptance-id="target-evidence-status-section">
      <div class="table-title">
        <h2>{{ businessAcceptanceSectionTitles.targetEvidenceSummary }}</h2>
        <span>{{ targetEvidenceStatusText }}</span>
      </div>
      <div class="summary-grid">
        <article>
          <span>来源对象编号</span>
          <strong data-acceptance-id="business-action-source-number-summary">{{ paymentExecutionPrepareNoText }}</strong>
          <small>付款执行准备来源对象</small>
        </article>
        <article>
          <span>目标对象编号</span>
          <strong data-acceptance-id="business-action-target-number">{{ targetObjectNoDisplay }}</strong>
          <small>未发现时不使用来源编号代替</small>
        </article>
        <article>
          <span>目标证据状态</span>
          <strong data-acceptance-id="action-target-evidence-status">{{ targetEvidenceStatusText }}</strong>
          <small>五状态中文展示</small>
        </article>
        <article>
          <span>目标证据处理状态</span>
          <strong data-acceptance-id="target-evidence-processing-status">{{ targetEvidenceProcessingStatusText }}</strong>
          <small>目标证据处理口径</small>
        </article>
        <article>
          <span>模拟执行状态</span>
          <strong data-acceptance-id="action-execution-status">{{ simulationExecutionStatusText }}</strong>
          <small>仅表示模拟状态机未进入执行</small>
        </article>
        <article>
          <span>结果来源</span>
          <strong>{{ targetEvidenceResultSourceText }}</strong>
          <small>页面只读展示判断结果</small>
        </article>
      </div>
    </section>

    <section id="next-step-release-section" class="table-card acceptance-visible-card" data-acceptance-id="next-step-release-section">
      <div class="table-title">
        <h2>目标证据放行与阻断</h2>
        <span>目标证据状态：{{ targetEvidenceStatusText }}</span>
      </div>
      <div class="summary-grid">
        <article>
          <span>是否允许基于目标证据进入下一步</span>
          <strong data-acceptance-id="business-action-next-step-release">{{ targetEvidenceClassification.nextStepAllowed ? '是' : '否' }}</strong>
        </article>
        <article>
          <span>目标证据阻断原因</span>
          <strong data-acceptance-id="business-action-next-step-reason">{{ targetEvidenceClassification.nextStepBlockingReason }}</strong>
        </article>
        <article>
          <span>执行状态机预检查</span>
          <strong>否</strong>
        </article>
        <article>
          <span>写业务数据</span>
          <strong>否</strong>
        </article>
      </div>
    </section>

    <section id="payment-voucher-precheck-section" class="table-card acceptance-visible-card" data-acceptance-id="payment-voucher-precheck-section">
      <div class="table-title">
        <h2>付款凭证准备预检查结果</h2>
        <span>预检查决策：{{ precheckResultLabel(purePrecheckResult.decision) }}</span>
      </div>
      <div class="summary-grid">
        <article>
          <span>预检查决策</span>
          <strong>{{ precheckResultLabel(purePrecheckResult.decision) }}</strong>
          <small>{{ purePrecheckResult.decision }}</small>
        </article>
        <article>
          <span>通过项数量</span>
          <strong>{{ purePrecheckResult.passedCount }}</strong>
        </article>
        <article>
          <span>阻断项数量</span>
          <strong>{{ purePrecheckResult.blockedCount }}</strong>
        </article>
        <article>
          <span>预检查第一阻断原因</span>
          <strong>{{ precheckFirstBlockSummary.reason }}</strong>
        </article>
      </div>
    </section>

    <section id="target-evidence-first-failure-section" class="table-card acceptance-visible-card" data-acceptance-id="target-evidence-first-failure-section">
      <div class="table-title">
        <h2>{{ businessAcceptanceSectionTitles.firstFailure }}</h2>
        <span data-acceptance-id="target-evidence-first-failure-label">{{ targetEvidenceFirstFailureSummary.label }}</span>
      </div>
      <div class="summary-grid">
        <article>
          <span>目标证据第一异常点</span>
          <strong>{{ targetEvidenceFirstFailureSummary.label }}</strong>
          <small>{{ targetEvidenceFirstFailureSummary.type }}</small>
        </article>
        <article>
          <span>目标证据异常原因</span>
          <strong>{{ targetEvidenceFirstFailureSummary.reason }}</strong>
        </article>
        <article>
          <span>目标证据责任定位</span>
          <strong data-acceptance-id="target-evidence-first-failure-responsibility">{{ targetEvidenceFirstFailureSummary.responsibility }}</strong>
        </article>
        <article>
          <span>预检查第一阻断项</span>
          <strong data-acceptance-id="precheck-first-block-label">{{ precheckFirstBlockSummary.label }}</strong>
          <small>{{ precheckFirstBlockSummary.reason }}</small>
        </article>
      </div>
    </section>

    <section id="target-evidence-trace-section" class="table-card acceptance-visible-card" data-acceptance-id="target-evidence-trace-section">
      <div class="table-title">
        <h2>{{ businessAcceptanceSectionTitles.targetEvidenceTrace }}</h2>
        <span>{{ targetEvidenceRuntimeRows.length }} 条来源链记录 / {{ targetEvidenceCategoryCoverage.join('、') }}</span>
      </div>
      <BusinessTableScrollContainer acceptance-id="target-evidence-trace-table-scroll" min-width="2800px">
        <table class="target-evidence-trace-table" data-acceptance-id="target-evidence-trace-table">
          <thead>
            <tr>
              <th>证据名称</th>
              <th>证据类别</th>
              <th>来源对象</th>
              <th>来源字段</th>
              <th>来源值</th>
              <th>目标对象</th>
              <th>目标字段</th>
              <th>目标值</th>
              <th>期望关系</th>
              <th>实际关系</th>
              <th>检查结果</th>
              <th>失败类型</th>
              <th>是否阻断</th>
              <th data-acceptance-id="target-evidence-trace-suggestion-header">建议检查方向</th>
              <th>责任定位</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in targetEvidenceRuntimeRows" :key="row.deterministicTraceKey || row.evidenceCode">
              <td>{{ row.evidenceLabel || row.evidenceCode }}</td>
              <td>{{ row.evidenceCategory }}</td>
              <td>{{ row.sourceObjectType }} {{ row.sourceObjectNo }}</td>
              <td>{{ row.sourceField }}</td>
              <td>{{ row.sourceValue }}</td>
              <td>{{ row.targetObjectType }} {{ row.targetObjectNo }}</td>
              <td>{{ row.targetField }}</td>
              <td>{{ row.targetValue }}</td>
              <td>{{ row.expectedRelation }}</td>
              <td>{{ row.actualRelation }}</td>
              <td>{{ row.evidenceStatusLabel || row.evidenceStatus }}</td>
              <td>{{ row.failureType || '-' }}</td>
              <td>{{ row.blocking ? '是' : '否' }}</td>
              <td data-acceptance-id="target-evidence-trace-suggestion-cell">{{ row.suggestionDirection }}</td>
              <td>{{ row.responsibilityLabel || row.responsibilityCategory }}</td>
            </tr>
          </tbody>
        </table>
      </BusinessTableScrollContainer>
    </section>

    <section id="missing-evidence-section" class="table-card acceptance-visible-card" data-acceptance-id="action-missing-evidence-list">
      <h2>{{ businessAcceptanceSectionTitles.missingEvidence }}</h2>
      <ul v-if="targetEvidenceMissingItems.length" class="evidence-list">
        <li v-for="item in targetEvidenceMissingItems" :key="item.code">{{ item.label }}：{{ item.actualRelation || item.expectedRelation || item.code }}</li>
      </ul>
      <p v-else>当前没有缺失证据。</p>
    </section>

    <section id="conflict-evidence-section" class="table-card acceptance-visible-card" data-acceptance-id="action-conflict-evidence-list">
      <h2>{{ businessAcceptanceSectionTitles.conflictEvidence }}</h2>
      <ul v-if="targetEvidenceConflictItems.length" class="evidence-list">
        <li v-for="item in targetEvidenceConflictItems" :key="item.code">{{ item.conflictType || item.code }}：{{ item.description || item.compareValue }}</li>
      </ul>
      <p v-else>当前没有目标关联冲突。</p>
    </section>

    <section id="read-failure-section" class="table-card acceptance-visible-card" data-acceptance-id="action-read-failure-list">
      <h2>{{ businessAcceptanceSectionTitles.readFailure }}</h2>
      <ul v-if="targetEvidenceReadFailures.length" class="evidence-list">
        <li v-for="item in targetEvidenceReadFailures" :key="item.code">{{ item.readStage }}：{{ item.safeErrorSummary }}</li>
      </ul>
      <p v-else>当前没有目标证据读取失败。</p>
    </section>    <section v-if="!paymentExecutionPrepareFound" class="boundary-card warning-card">
      <strong>付款执行准备不存在：</strong>
      当前路由单号 {{ routePaymentExecutionPrepareNoText }} 未匹配到付款执行准备对象。页面保持稳定显示，状态机启动结论为不允许启动，
      当前执行状态为 not_created，不创建模拟执行请求，不进入 precheck_pending，不执行状态机预检查，不获取并发锁，不执行模拟计算，
      不创建模拟结果，不创建临时上下文，不执行清理，不写 localStorage，不修改 Store，正式业务写入、回滚、补偿数量均为 0。
    </section>

    <section class="boundary-card conclusion-card">
      <strong>核心结论：</strong>
      当前状态机运行状态：未创建，仅设计；当前是否允许启动状态机：否；当前是否执行状态转换：否；当前是否写入业务数据：否。
      本轮仅展示未来状态机模型、失败分类、临时上下文、锁释放、取消重试、审计字段和零业务写入边界。
    </section>

    <section class="summary-grid">
        <article v-for="card in summaryCards" :key="card.title" class="summary-card" :data-acceptance-id="card.acceptanceId">
        <span>{{ card.title }}</span>
        <strong>{{ card.value }}</strong>
        <small>{{ card.desc }}</small>
      </article>
    </section>

    <section
      id="v113681-acceptance-summary"
      class="table-card governance-card source-snapshot-card primary-acceptance-card"
      aria-labelledby="v113681-acceptance-summary-title"
      data-acceptance-id="v113681-acceptance-summary"
    >
      <div class="table-title">
        <div>
          <h2 id="v113681-acceptance-summary-title" class="acceptance-summary-title" data-acceptance-id="v113681-acceptance-summary-title">
            V1.14.2.7.2.1 关键验收摘要
          </h2>
          <p class="helper-text">
            本区域集中展示权限、二次确认、零业务写入沙箱、效果清单计数、按钮白名单、自动验收清单和业务隔离结论。所有结果均为页面只读预览，不创建请求、不启动状态机、不保存模拟结果。
          </p>
        </div>
        <el-button type="primary" plain data-acceptance-id="copy-diagnostic-data-button" @click="copyDiagnosticData">复制诊断数据</el-button>
      </div>
      <div class="summary-grid">
        <article v-for="card in simulationResultAcceptanceCards" :key="card.title" class="summary-card" :data-acceptance-id="card.acceptanceId">
          <span>{{ card.title }}</span>
          <strong>{{ card.value }}</strong>
          <small>{{ card.desc }}</small>
        </article>
      </div>
    </section>

    <section
      id="v113681-automatic-acceptance-result"
      class="table-card governance-card"
      data-acceptance-id="v113681-automatic-acceptance-result"
      aria-labelledby="v113681-automatic-acceptance-result-title"
    >
      <div class="table-title">
        <div>
          <h2 id="v113681-automatic-acceptance-result-title" data-acceptance-id="automatic-acceptance-title">页面运行时自动验收结果</h2>
          <p class="helper-text">
            本区域根据 V1.14.2.7.2.1 验收清单自动核对当前路由、页面可见标题、关键卡片、按钮白名单和零业务写入边界。
          </p>
        </div>
        <span data-acceptance-id="automatic-acceptance-status">{{ automaticAcceptanceResult.overallStatus }}</span>
      </div>
      <div class="summary-grid">
        <article v-for="card in automaticAcceptanceCards" :key="card.title" class="summary-card" :data-acceptance-id="card.acceptanceId">
          <span>{{ card.title }}</span>
          <strong>{{ card.value }}</strong>
          <small>{{ card.desc }}</small>
        </article>
      </div>
      <el-table v-if="automaticAcceptanceResult.failedCheckCount > 0" :data="automaticAcceptanceResult.failedChecks" border stripe>
        <el-table-column prop="checkId" label="验收项" min-width="180" />
        <el-table-column prop="fieldLabel" label="字段" min-width="180" />
        <el-table-column prop="actualValue" label="实际值" min-width="220" />
        <el-table-column prop="expectedValue" label="期望值" min-width="220" />
        <el-table-column prop="failureRemediationHint" label="修复提示" min-width="320" />
      </el-table>
    </section>

    <section class="table-card governance-card">
      <div class="table-title">
        <div>
          <h2>模拟权限、二次确认与零业务写入执行沙箱摘要</h2>
          <p class="helper-text">
            本区域只展示纯函数策略预览：不读取真实登录身份，不创建确认挑战，不进入真实沙箱，不创建模拟请求或模拟结果，不写业务数据。
          </p>
        </div>
      </div>
      <div class="summary-grid">
        <article v-for="card in executionGuardAcceptanceCards" :key="card.title" class="summary-card" :data-acceptance-id="card.acceptanceId">
          <span>{{ card.title }}</span>
          <strong>{{ card.value }}</strong>
          <small>{{ card.desc }}</small>
        </article>
      </div>
    </section>

    <section class="table-card">
      <div class="table-title">
        <h2>模拟权限策略运行摘要</h2>
        <span>{{ permissionContextRows.length }} 个权限上下文字段 / 当前不授予真实权限</span>
      </div>
      <div class="summary-grid">
        <article v-for="card in permissionPreviewCards" :key="card.title" class="summary-card" :data-acceptance-id="card.acceptanceId">
          <span>{{ card.title }}</span>
          <strong>{{ card.value }}</strong>
          <small>{{ card.desc }}</small>
        </article>
      </div>
      <el-table :data="permissionContextRows" border stripe>
        <el-table-column prop="field" label="权限字段" min-width="220" />
        <el-table-column prop="chineseName" label="中文名称" min-width="180" />
        <el-table-column prop="type" label="类型" width="120" />
        <el-table-column prop="requiredText" label="授权必需" width="120" />
        <el-table-column prop="runtimeSource" label="来源说明" min-width="260" />
      </el-table>
    </section>

    <section class="table-card">
      <div class="table-title">
        <h2>二次确认摘要运行状态</h2>
        <span>{{ confirmationRequirementRows.length }} 项确认要求 / 当前不创建确认挑战</span>
      </div>
      <div class="summary-grid">
        <article v-for="card in confirmationPreviewCards" :key="card.title" class="summary-card" :data-acceptance-id="card.acceptanceId">
          <span>{{ card.title }}</span>
          <strong>{{ card.value }}</strong>
          <small>{{ card.desc }}</small>
        </article>
      </div>
      <el-table :data="confirmationRequirementRows" border stripe>
        <el-table-column prop="requirementCode" label="确认要求编码" min-width="220" />
        <el-table-column prop="chineseName" label="确认要求" min-width="300" />
        <el-table-column prop="category" label="类别" min-width="160" />
        <el-table-column prop="satisfiedText" label="当前是否满足" width="140" />
        <el-table-column prop="blockReason" label="未满足原因" min-width="260" />
      </el-table>
    </section>

    <section class="table-card">
      <div class="table-title">
        <h2>零业务写入沙箱策略摘要</h2>
        <span>{{ sandboxEffectRows.length }} 个效果编码 / 当前不进入真实沙箱</span>
      </div>
      <div class="summary-grid">
        <article v-for="card in sandboxPreviewCards" :key="card.title" class="summary-card" :data-acceptance-id="card.acceptanceId">
          <span>{{ card.title }}</span>
          <strong>{{ card.value }}</strong>
          <small>{{ card.desc }}</small>
        </article>
      </div>
      <el-table :data="sandboxEffectRows" border stripe>
        <el-table-column prop="effectCode" label="效果编码" min-width="240" />
        <el-table-column prop="effectName" label="效果名称" min-width="260" />
        <el-table-column prop="effectCategory" label="效果类别" min-width="160" />
        <el-table-column prop="allowedText" label="当前是否允许" width="140" />
        <el-table-column prop="writesFormalBusinessDataText" label="写正式业务" width="140" />
      </el-table>
    </section>

    <section class="table-card matrix-card">
      <div class="table-title">
        <h2>权限、确认与沙箱执行防护测试矩阵摘要</h2>
        <span>{{ executionGuardMatrixReport.testCaseCount }} 个用例 / {{ executionGuardMatrixReport.assertionCount }} 条断言</span>
      </div>
      <div class="summary-grid">
        <article v-for="card in executionGuardMatrixCards" :key="card.title" class="summary-card" :data-acceptance-id="card.acceptanceId">
          <span>{{ card.title }}</span>
          <strong>{{ card.value }}</strong>
          <small>{{ card.desc }}</small>
        </article>
      </div>
    </section>

    <section class="table-card">
      <div class="table-title">
        <h2>模拟结果独立存储运行摘要</h2>
        <span>只定义独立命名空间，不创建真实存储</span>
      </div>
      <div class="summary-grid">
        <article v-for="card in simulationResultStorageCards" :key="card.title" class="summary-card">
          <span>{{ card.title }}</span>
          <strong>{{ card.value }}</strong>
          <small>{{ card.desc }}</small>
        </article>
      </div>
    </section>

    <section class="table-card">
      <div class="table-title">
        <h2>模拟结果记录和明细契约</h2>
        <span>{{ simulationResultFieldRows.length }} 个结果字段 / {{ simulationResultLineFieldRows.length }} 个明细字段</span>
      </div>
      <el-table :data="simulationResultFieldRows" border stripe>
        <el-table-column prop="field" label="结果字段" min-width="220" />
        <el-table-column prop="chineseName" label="中文名称" min-width="180" />
        <el-table-column prop="type" label="类型" width="100" />
        <el-table-column prop="requiredForStoredRecordText" label="存储必填" width="110" />
        <el-table-column prop="immutableText" label="验证后不可变" width="130" />
        <el-table-column prop="fingerprintText" label="进入记录指纹" width="130" />
        <el-table-column prop="defaultValueText" label="默认值" min-width="180" />
      </el-table>
      <el-table :data="simulationResultLineFieldRows" border stripe class="nested-table">
        <el-table-column prop="field" label="明细字段" min-width="220" />
        <el-table-column prop="chineseName" label="中文名称" min-width="180" />
        <el-table-column prop="type" label="类型" width="100" />
        <el-table-column prop="fingerprintText" label="进入明细指纹" width="130" />
        <el-table-column prop="businessMeaning" label="业务含义" min-width="260" />
      </el-table>
    </section>

    <section class="table-card">
      <div class="table-title">
        <h2>模拟结果指纹运行摘要</h2>
        <span>契约、记录、载荷指纹均为稳定纯函数输出</span>
      </div>
      <div class="summary-grid">
        <article v-for="card in simulationResultFingerprintCards" :key="card.title" class="summary-card">
          <span>{{ card.title }}</span>
          <strong>{{ card.value }}</strong>
          <small>{{ card.desc }}</small>
        </article>
      </div>
    </section>

    <section class="table-card">
      <div class="table-title">
        <h2>模拟结果生命周期运行摘要</h2>
        <span>只做状态转换合法性判断，不执行转换</span>
      </div>
      <div class="summary-grid">
        <article v-for="card in simulationLifecycleCards" :key="card.title" class="summary-card">
          <span>{{ card.title }}</span>
          <strong>{{ card.value }}</strong>
          <small>{{ card.desc }}</small>
        </article>
      </div>
    </section>

    <section class="table-card">
      <div class="table-title">
        <h2>合法与非法生命周期转换表</h2>
        <span>archived 为终态，非法逆向转换必须阻断</span>
      </div>
      <el-table :data="lifecycleTransitionRows" border stripe>
        <el-table-column prop="from" label="当前状态" min-width="160" />
        <el-table-column prop="to" label="请求状态" min-width="160" />
        <el-table-column prop="allowedText" label="是否允许" width="120" />
        <el-table-column prop="reason" label="判断依据" min-width="260" />
        <el-table-column prop="executedText" label="是否实际执行" width="130" />
      </el-table>
    </section>

    <section class="table-card">
      <div class="table-title">
        <h2>结果失效与替代规则</h2>
        <span>只给预览建议，不实际失效、替代或归档</span>
      </div>
      <div class="summary-grid">
        <article v-for="card in simulationInvalidationCards" :key="card.title" class="summary-card">
          <span>{{ card.title }}</span>
          <strong>{{ card.value }}</strong>
          <small>{{ card.desc }}</small>
        </article>
      </div>
    </section>

    <section class="table-card">
      <div class="table-title">
        <h2>模拟审计事件运行摘要</h2>
        <span>只验证事件契约，不创建真实审计日志</span>
      </div>
      <div class="summary-grid">
        <article v-for="card in simulationAuditCards" :key="card.title" class="summary-card">
          <span>{{ card.title }}</span>
          <strong>{{ card.value }}</strong>
          <small>{{ card.desc }}</small>
        </article>
      </div>
    </section>

    <section class="table-card">
      <div class="table-title">
        <h2>审计事件追加式指纹链设计</h2>
        <span>测试矩阵使用合成事件链，当前业务日志仍为 0</span>
      </div>
      <el-table :data="auditChainScenarioRows" border stripe>
        <el-table-column prop="caseId" label="用例" width="100" />
        <el-table-column prop="name" label="场景" min-width="280" />
        <el-table-column prop="passedText" label="结果" width="100" />
        <el-table-column prop="assertionCount" label="断言数" width="100" />
      </el-table>
    </section>

    <section class="table-card matrix-card">
      <div class="table-title">
        <h2>模拟结果生命周期与审计测试矩阵摘要</h2>
        <span>{{ simulationResultMatrixReport.testCaseCount }} 个用例 / {{ simulationResultMatrixReport.assertionCount }} 条断言</span>
      </div>
      <div class="summary-grid">
        <article v-for="card in simulationResultMatrixCards" :key="card.title" class="summary-card">
          <span>{{ card.title }}</span>
          <strong>{{ card.value }}</strong>
          <small>{{ card.desc }}</small>
        </article>
      </div>
    </section>

    <section class="boundary-card conclusion-card">
      <strong>模拟结果、审计日志与正式业务隔离结论：</strong>
      <ul class="plain-list">
        <li v-for="item in simulationResultIsolationItems" :key="item">{{ item }}</li>
      </ul>
    </section>

    <section
      id="v11366-acceptance-summary"
      class="table-card governance-card source-snapshot-card"
      aria-labelledby="v11366-acceptance-summary-title"
    >
      <div class="table-title">
        <div>
          <h2 id="v11366-acceptance-summary-title" class="acceptance-summary-title">
            V1.13.66 已归档验收摘要（历史）
          </h2>
          <p class="helper-text">
            本区域集中展示请求输入包、业务幂等键、并发锁范围和请求控制测试矩阵。所有结果均为内存纯函数预览，不创建真实请求、不保存幂等键、不获取真实锁。
          </p>
        </div>
      </div>
      <div class="summary-grid">
        <article v-for="card in requestControlAcceptanceCards" :key="card.title" class="summary-card">
          <span>{{ card.title }}</span>
          <strong>{{ card.value }}</strong>
          <small>{{ card.desc }}</small>
        </article>
      </div>
    </section>

    <section class="table-card">
      <div class="table-title">
        <h2>模拟执行请求输入包运行摘要</h2>
        <span>请求输入包只是预览，不是真实请求</span>
      </div>
      <div class="summary-grid">
        <article v-for="card in requestPackageRunCards" :key="card.title" class="summary-card">
          <span>{{ card.title }}</span>
          <strong>{{ card.value }}</strong>
          <small>{{ card.desc }}</small>
        </article>
      </div>
    </section>

    <section class="table-card">
      <div class="table-title">
        <h2>请求输入包字段完整性</h2>
        <span>{{ requestPackageFieldRows.length }} 个字段 / 固定契约</span>
      </div>
      <el-table :data="requestPackageFieldRows" border stripe>
        <el-table-column prop="field" label="字段" min-width="220" />
        <el-table-column prop="chineseName" label="中文名称" min-width="180" />
        <el-table-column prop="type" label="类型" width="100" />
        <el-table-column prop="requiredForBusinessReadyText" label="业务就绪必填" width="130" />
        <el-table-column prop="packageFingerprintText" label="进入输入包指纹" width="140" />
        <el-table-column prop="idempotencyText" label="进入幂等素材" width="130" />
        <el-table-column prop="lockScopeText" label="进入锁范围" width="120" />
        <el-table-column prop="presentText" label="当前是否有值" width="120" />
        <el-table-column prop="valueText" label="当前规范值" min-width="220" />
      </el-table>
    </section>

    <section class="table-card">
      <div class="table-title">
        <h2>请求输入包指纹运行摘要</h2>
        <span>输入包指纹不等于业务幂等键</span>
      </div>
      <div class="summary-grid">
        <article v-for="card in requestPackageFingerprintCards" :key="card.title" class="summary-card">
          <span>{{ card.title }}</span>
          <strong>{{ card.value }}</strong>
          <small>{{ card.desc }}</small>
        </article>
      </div>
    </section>

    <section class="table-card">
      <div class="table-title">
        <h2>业务幂等键运行摘要</h2>
        <span>本轮只做幂等素材和键完整性预览</span>
      </div>
      <div class="summary-grid">
        <article v-for="card in idempotencyCards" :key="card.title" class="summary-card">
          <span>{{ card.title }}</span>
          <strong>{{ card.value }}</strong>
          <small>{{ card.desc }}</small>
        </article>
      </div>
    </section>

    <section class="table-card">
      <div class="table-title">
        <h2>幂等注册表解析场景设计</h2>
        <span>仅展示测试矩阵中的只读场景，不查询正式注册表</span>
      </div>
      <el-table :data="idempotencyScenarioRows" border stripe>
        <el-table-column prop="caseId" label="用例" width="100" />
        <el-table-column prop="name" label="场景" min-width="260" />
        <el-table-column prop="passedText" label="结果" width="100" />
        <el-table-column prop="assertionCount" label="断言数" width="100" />
      </el-table>
    </section>

    <section class="table-card">
      <div class="table-title">
        <h2>并发锁范围运行摘要</h2>
        <span>锁范围不包含来源指纹、会计期间或运行时字段</span>
      </div>
      <div class="summary-grid">
        <article v-for="card in concurrencyLockCards" :key="card.title" class="summary-card">
          <span>{{ card.title }}</span>
          <strong>{{ card.value }}</strong>
          <small>{{ card.desc }}</small>
        </article>
      </div>
    </section>

    <section class="table-card">
      <div class="table-title">
        <h2>并发判断场景设计</h2>
        <span>只读判断，不获取、不释放真实锁</span>
      </div>
      <el-table :data="concurrencyScenarioRows" border stripe>
        <el-table-column prop="caseId" label="用例" width="100" />
        <el-table-column prop="name" label="场景" min-width="260" />
        <el-table-column prop="passedText" label="结果" width="100" />
        <el-table-column prop="assertionCount" label="断言数" width="100" />
      </el-table>
    </section>

    <section class="table-card matrix-card">
      <div class="table-title">
        <h2>请求输入包、幂等与并发测试矩阵摘要</h2>
        <span>{{ requestControlMatrixReport.testCaseCount }} 个用例 / {{ requestControlMatrixReport.assertionCount }} 条断言</span>
      </div>
      <div class="summary-grid">
        <article v-for="card in requestControlMatrixCards" :key="card.title" class="summary-card">
          <span>{{ card.title }}</span>
          <strong>{{ card.value }}</strong>
          <small>{{ card.desc }}</small>
        </article>
      </div>
    </section>

    <section class="boundary-card conclusion-card">
      <strong>请求输入包、幂等、并发与业务放行隔离结论：</strong>
      <ul class="plain-list">
        <li v-for="item in requestControlIsolationItems" :key="item">{{ item }}</li>
      </ul>
    </section>

    <section
      id="v113651-acceptance-summary"
      class="table-card governance-card source-snapshot-card"
      aria-labelledby="v113651-acceptance-summary-title"
    >
      <div class="table-title">
        <div>
          <h2 id="v113651-acceptance-summary-title">
            V1.13.65.1 已归档验收摘要（历史）
          </h2>
          <p class="helper-text">
            本区域位于页面顶部付款执行准备基础状态卡片下方，集中展示来源快照、指纹、变更检测、业务隔离和当前业务预检查数量。
            sourceSnapshotReady、sourceFingerprintReady、sourceUnchanged 仍保持 false，不作为业务放行依据。
          </p>
        </div>
      </div>
      <div class="summary-grid">
        <article v-for="card in sourceSnapshotAcceptanceCards" :key="card.title" class="summary-card">
          <span>{{ card.title }}</span>
          <strong>{{ card.value }}</strong>
          <small>{{ card.desc }}</small>
        </article>
      </div>
    </section>

    <section class="table-card">
      <div class="table-title">
        <h2>来源只读快照运行摘要</h2>
        <span>快照预览不是正式业务快照</span>
      </div>
      <div class="summary-grid">
        <article v-for="card in sourceSnapshotRunCards" :key="card.title" class="summary-card">
          <span>{{ card.title }}</span>
          <strong>{{ card.value }}</strong>
          <small>{{ card.desc }}</small>
        </article>
      </div>
    </section>

    <section class="table-card">
      <div class="table-title">
        <h2>来源快照字段完整性</h2>
        <span>{{ sourceSnapshotFieldRows.length }} 个字段 / 只读规范化</span>
      </div>
      <el-table :data="sourceSnapshotFieldRows" border stripe>
        <el-table-column prop="field" label="字段" min-width="220" />
        <el-table-column prop="chineseName" label="中文名称" min-width="160" />
        <el-table-column prop="criticalText" label="关键字段" width="100" />
        <el-table-column prop="fingerprintText" label="进入指纹" width="100" />
        <el-table-column prop="presentText" label="是否有值" width="100" />
        <el-table-column prop="valueText" label="规范化值" min-width="220" />
      </el-table>
    </section>

    <section class="table-card">
      <div class="table-title">
        <h2>来源数据指纹运行摘要</h2>
        <span>指纹仅用于一致性识别，不是加密签名</span>
      </div>
      <div class="summary-grid">
        <article v-for="card in sourceFingerprintCards" :key="card.title" class="summary-card">
          <span>{{ card.title }}</span>
          <strong>{{ card.value }}</strong>
          <small>{{ card.desc }}</small>
        </article>
      </div>
    </section>

    <section class="table-card">
      <div class="table-title">
        <h2>来源变更检测运行摘要</h2>
        <span>无正式历史参考快照时，不得确认当前来源未变化</span>
      </div>
      <div class="summary-grid">
        <article v-for="card in sourceChangeCards" :key="card.title" class="summary-card">
          <span>{{ card.title }}</span>
          <strong>{{ card.value }}</strong>
          <small>{{ card.desc }}</small>
        </article>
      </div>
    </section>

    <section class="table-card">
      <div class="table-title">
        <h2>来源变更字段明细</h2>
        <span>{{ sourceChangedFieldRows.length }} 个字段变化 / 当前真实路由通常为无参考快照</span>
      </div>
      <div v-if="sourceChangedFieldRows.length === 0" class="final-block-note success-note">
        当前没有字段级变化明细。若无正式历史参考快照，结论应为“未确认”，不是“来源未变化”。
      </div>
      <el-table v-else :data="sourceChangedFieldRows" border stripe>
        <el-table-column prop="field" label="字段" min-width="180" />
        <el-table-column prop="chineseName" label="中文名称" min-width="160" />
        <el-table-column prop="changeType" label="变化类型" width="100" />
        <el-table-column prop="classification" label="分类" width="150" />
        <el-table-column prop="criticalText" label="关键变化" width="100" />
        <el-table-column prop="invalidatesText" label="建议失效" width="100" />
      </el-table>
    </section>

    <section class="table-card matrix-card">
      <div class="table-title">
        <h2>来源快照纯函数测试矩阵摘要</h2>
        <span>{{ sourceSnapshotMatrixReport.testCaseCount }} 个用例 / {{ sourceSnapshotMatrixReport.assertionCount }} 条断言</span>
      </div>
      <div class="summary-grid">
        <article v-for="card in sourceSnapshotMatrixCards" :key="card.title" class="summary-card">
          <span>{{ card.title }}</span>
          <strong>{{ card.value }}</strong>
          <small>{{ card.desc }}</small>
        </article>
      </div>
    </section>

    <section class="boundary-card conclusion-card">
      <strong>来源快照、指纹、变更检测与业务放行隔离结论：</strong>
      <ul class="plain-list">
        <li v-for="item in sourceSnapshotIsolationItems" :key="item">{{ item }}</li>
      </ul>
    </section>

    <section class="table-card governance-card">
      <div class="table-title">
        <div>
          <h2>V1.13.64.1 版本治理摘要（历史保留）</h2>
          <p class="helper-text">
            这里集中显示版本治理、指纹锁定、四个基线和业务保护结论。页面版本变化不等于规则集、输入契约或回归基线版本变化。
          </p>
        </div>
      </div>
      <div class="summary-grid">
        <article v-for="card in governanceAcceptanceCards" :key="card.title" class="summary-card">
          <span>{{ card.title }}</span>
          <strong>{{ card.value }}</strong>
          <small>{{ card.desc }}</small>
        </article>
      </div>
    </section>

    <section class="table-card">
      <div class="table-title">
        <h2>规则版本运行摘要</h2>
        <span>规则集指纹只用于完整性识别，不是加密签名</span>
      </div>
      <div class="summary-grid">
        <article v-for="card in ruleGovernanceCards" :key="card.title" class="summary-card">
          <span>{{ card.title }}</span>
          <strong>{{ card.value }}</strong>
          <small>{{ card.desc }}</small>
        </article>
      </div>
    </section>

    <section class="table-card">
      <div class="table-title">
        <h2>输入契约运行摘要</h2>
        <span>契约校验不执行业务放行判断</span>
      </div>
      <div class="summary-grid">
        <article v-for="card in inputGovernanceCards" :key="card.title" class="summary-card">
          <span>{{ card.title }}</span>
          <strong>{{ card.value }}</strong>
          <small>{{ card.desc }}</small>
        </article>
      </div>
    </section>

    <section class="table-card">
      <div class="table-title">
        <h2>回归基线固化摘要</h2>
        <span>四个固定基线均需通过</span>
      </div>
      <div class="summary-grid">
        <article v-for="card in baselineGovernanceCards" :key="card.title" class="summary-card">
          <span>{{ card.title }}</span>
          <strong>{{ card.value }}</strong>
          <small>{{ card.desc }}</small>
        </article>
      </div>
    </section>

    <section class="table-card">
      <div class="table-title">
        <h2>四个固定基线结果表</h2>
        <span>{{ governanceBaselineRows.length }} 条基线 / 规则向量长度 32</span>
      </div>
      <el-table :data="governanceBaselineRows" border stripe>
        <el-table-column prop="baselineId" label="基线编号" width="120" />
        <el-table-column prop="name" label="基线名称" min-width="220" />
        <el-table-column prop="expectedDecision" label="预期决策" width="120" />
        <el-table-column prop="actualDecision" label="实际决策" width="120" />
        <el-table-column prop="actualCountsText" label="实际统计" min-width="260" />
        <el-table-column prop="ruleVectorMatchedText" label="规则向量一致" width="130" />
        <el-table-column prop="blockRuleCodesMatchedText" label="阻断集合一致" width="130" />
        <el-table-column prop="notApplicableRuleCodesMatchedText" label="不适用集合一致" width="140" />
        <el-table-column prop="passedText" label="结果" width="100" />
      </el-table>
    </section>

    <section class="boundary-card conclusion-card">
      <strong>版本治理结论：</strong>
      <ul class="plain-list">
        <li v-for="item in governanceConclusionItems" :key="item">{{ item }}</li>
      </ul>
    </section>

    <section class="table-card matrix-card">
      <div class="table-title">
        <div>
          <h2>付款凭证准备纯函数预检查测试矩阵运行摘要</h2>
          <p class="helper-text">
            测试矩阵验证的是引擎行为，不是当前业务放行。测试矩阵整体状态与当前业务预检查决策分开显示。
          </p>
        </div>
      </div>
      <div class="summary-grid">
        <article v-for="card in matrixSummaryCards" :key="card.title" class="summary-card">
          <span>{{ card.title }}</span>
          <strong>{{ card.value }}</strong>
          <small>{{ card.desc }}</small>
        </article>
      </div>
    </section>

    <section class="table-card">
      <div class="table-title">
        <div>
          <h2>规则版本与输入契约固化</h2>
          <p class="helper-text">
            规则集版本和输入契约用于回归审计。它们只描述规则和输入字段，不改变规则判断结果。
          </p>
        </div>
      </div>
      <div class="summary-grid">
        <article v-for="card in versionContractCards" :key="card.title" class="summary-card">
          <span>{{ card.title }}</span>
          <strong>{{ card.value }}</strong>
          <small>{{ card.desc }}</small>
        </article>
      </div>
      <el-table :data="inputContractRows" border stripe>
        <el-table-column prop="field" label="输入字段" min-width="240" />
        <el-table-column prop="valueType" label="值类型" min-width="160" />
        <el-table-column prop="defaultValue" label="默认值" min-width="140" />
        <el-table-column prop="normalization" label="规范化方式" min-width="160" />
        <el-table-column prop="description" label="说明" min-width="360" />
      </el-table>
    </section>

    <section class="table-card">
      <div class="table-title">
        <h2>回归基线固化</h2>
        <span>{{ regressionBaselineRows.length }} 条基线 / 不随页面路由变化</span>
      </div>
      <el-table :data="regressionBaselineRows" border stripe>
        <el-table-column prop="baseline" label="基线名称" min-width="220" />
        <el-table-column prop="decision" label="预期决策" width="120" />
        <el-table-column prop="canProceedText" label="是否允许继续" width="130" />
        <el-table-column prop="totalRuleCount" label="规则总数" width="110" />
        <el-table-column prop="passedCount" label="通过项" width="100" />
        <el-table-column prop="blockedCount" label="阻断项" width="100" />
        <el-table-column prop="warningCount" label="警告项" width="100" />
        <el-table-column prop="notApplicableCount" label="不适用项" width="110" />
        <el-table-column prop="specialRule" label="关键规则" min-width="220" />
      </el-table>
    </section>

    <section class="table-card">
      <div class="table-title">
        <h2>测试矩阵覆盖分类</h2>
        <span>{{ matrixCategoryRows.length }} 类覆盖 / 只读计算</span>
      </div>
      <el-table :data="matrixCategoryRows" border stripe>
        <el-table-column prop="name" label="覆盖分类" min-width="180" />
        <el-table-column prop="caseCount" label="用例数" width="110" />
        <el-table-column prop="passedCount" label="通过数" width="110" />
        <el-table-column prop="failedCount" label="失败数" width="110" />
        <el-table-column prop="coverageStatusText" label="覆盖状态" width="140" />
      </el-table>
    </section>

    <section class="table-card">
      <div class="table-title">
        <h2>测试用例结果表</h2>
        <span>{{ precheckMatrixReport.testCaseCount }} 个用例 / 写业务数据：否</span>
      </div>
      <el-table :data="matrixScenarioRows" border stripe>
        <el-table-column prop="caseId" label="用例编号" width="110" />
        <el-table-column prop="category" label="分类" min-width="150" />
        <el-table-column prop="name" label="用例名称" min-width="260" />
        <el-table-column prop="riskLevel" label="风险等级" width="110" />
        <el-table-column prop="expectedDecisionText" label="预期决策" width="120" />
        <el-table-column prop="actualDecisionText" label="实际决策" width="120" />
        <el-table-column prop="expectedCanProceedText" label="预期是否继续" width="130" />
        <el-table-column prop="actualCanProceedText" label="实际是否继续" width="130" />
        <el-table-column prop="assertionCount" label="断言数" width="100" />
        <el-table-column prop="failedAssertionCount" label="失败断言数" width="120" />
        <el-table-column prop="passedText" label="测试结果" width="110" />
        <el-table-column prop="businessDataWrittenText" label="是否写业务数据" width="150" />
      </el-table>
    </section>

    <section class="table-card">
      <div class="table-title">
        <h2>失败用例明细</h2>
        <span>{{ precheckMatrixReport.failedAssertionCount }} 条失败断言</span>
      </div>
      <div v-if="matrixFailureRows.length === 0" class="final-block-note success-note">
        没有失败用例。
      </div>
      <el-table v-else :data="matrixFailureRows" border stripe>
        <el-table-column prop="caseId" label="用例编号" width="120" />
        <el-table-column prop="assertion" label="失败断言" min-width="220" />
        <el-table-column prop="expected" label="预期值" min-width="180" />
        <el-table-column prop="actual" label="实际值" min-width="180" />
        <el-table-column prop="ruleCode" label="涉及规则" min-width="180" />
        <el-table-column prop="riskLevel" label="风险等级" width="110" />
      </el-table>
    </section>

    <section class="table-card">
      <div class="table-title">
        <h2>不变式检查结果</h2>
        <span>{{ matrixInvariantRows.length }} 项检查</span>
      </div>
      <el-table :data="matrixInvariantRows" border stripe>
        <el-table-column prop="invariantCode" label="检查编号" min-width="180" />
        <el-table-column prop="name" label="检查内容" min-width="320" />
        <el-table-column prop="passedText" label="检查结果" width="120" />
        <el-table-column prop="expected" label="预期值" min-width="180" />
        <el-table-column prop="actual" label="实际值" min-width="180" />
      </el-table>
    </section>

    <section class="boundary-card conclusion-card">
      <strong>测试矩阵与业务放行隔离结论：</strong>
      测试矩阵验证的是引擎行为，不是当前业务放行。即使测试矩阵全部通过，正常 PEP 当前仍存在法人、账套、币种、会计、银行、快照、幂等、权限等阻断条件。
      当前 precheckDecision = {{ purePrecheckResult.decision }}，precheckCanProceed = {{ String(purePrecheckResult.canProceed) }}，
      currentExecutionState = not_created，stateMachineStartAllowed = false。
    </section>

    <section class="table-card precheck-engine-card">
      <div class="table-title">
        <div>
          <h2>付款凭证准备纯函数预检查引擎运行摘要</h2>
          <p class="helper-text">
            本区域展示纯函数只读预检查演算结果。它只接收页面构造的普通输入对象并返回结果，不创建模拟请求，不推进状态机，不保存预检查结果。
          </p>
        </div>
      </div>
      <div class="summary-grid">
        <article v-for="card in purePrecheckSummaryCards" :key="card.title" class="summary-card">
          <span>{{ card.title }}</span>
          <strong>{{ card.value }}</strong>
          <small>{{ card.desc }}</small>
        </article>
      </div>
    </section>

    <section class="table-card precheck-engine-card">
      <div class="table-title">
        <h2>纯函数特性自检</h2>
        <span>相同输入相同输出 / 输入对象未修改</span>
      </div>
      <div class="summary-grid">
        <article v-for="card in purePrecheckPurityCards" :key="card.title" class="summary-card">
          <span>{{ card.title }}</span>
          <strong>{{ card.value }}</strong>
        </article>
      </div>
    </section>

    <section class="table-card">
      <div class="table-title">
        <h2>纯函数预检查规则结果</h2>
        <span>{{ purePrecheckResult.totalRuleCount }} 条规则 / 写业务数据：否</span>
      </div>
      <el-table :data="purePrecheckRuleRows" border stripe>
        <el-table-column prop="ruleCode" label="规则编码" min-width="230" />
        <el-table-column prop="ruleName" label="中文规则名称" min-width="240" />
        <el-table-column prop="category" label="规则分类" min-width="180" />
        <el-table-column prop="level" label="规则等级" width="110" />
        <el-table-column prop="resultText" label="当前结果" width="120" />
        <el-table-column prop="actualValue" label="当前值" min-width="180" />
        <el-table-column prop="expectedValue" label="预期值" min-width="180" />
        <el-table-column prop="message" label="中文说明" min-width="360" />
        <el-table-column prop="writeBusinessDataText" label="是否写业务数据" width="150" />
      </el-table>
    </section>

    <section class="table-card">
      <div class="table-title">
        <div>
          <h2>付款凭证准备模拟执行状态机与失败零写入机制设计</h2>
          <p class="helper-text">
            执行状态、结果有效性、失败信息拆分展示，不混用一个 status 字段。本轮不创建任何实际状态实例，也不写任何状态字段。
            V1.13.61.1 已修正状态机终态语义，业务执行结束状态与状态机最终终态分开表示。
          </p>
        </div>
      </div>
      <div class="review-conclusion-grid">
        <article>
          <span>当前执行状态</span>
          <strong>not_created / 未创建</strong>
        </article>
        <article>
          <span>当前结果有效性状态</span>
          <strong>not_created / 结果未创建</strong>
        </article>
        <article>
          <span>状态机启动结论</span>
          <strong>不允许启动</strong>
        </article>
        <article>
          <span>正式业务写入数量</span>
          <strong>0</strong>
        </article>
      </div>
    </section>

    <section class="table-card">
      <div class="table-title">
        <h2>状态模型拆分设计</h2>
        <span>三类状态互不混用</span>
      </div>
      <el-table :data="stateModelSplitItems" border stripe>
        <el-table-column prop="field" label="字段" min-width="220" />
        <el-table-column prop="name" label="中文名称" min-width="220" />
        <el-table-column prop="meaning" label="描述内容" min-width="320" />
        <el-table-column prop="currentValue" label="当前值" min-width="180" />
        <el-table-column prop="writeThisRound" label="本轮是否写入" width="150" />
      </el-table>
    </section>

    <section class="table-card">
      <div class="table-title">
        <h2>付款凭证准备模拟执行生命周期状态机设计</h2>
        <span>{{ executionStateItems.length }} 个未来状态 / 本轮均未进入</span>
      </div>
      <el-table :data="executionStateItems" border stripe>
        <el-table-column prop="code" label="状态编码" min-width="160" />
        <el-table-column prop="name" label="中文名称" min-width="160" />
        <el-table-column prop="meaning" label="业务含义" min-width="360" />
        <el-table-column prop="businessExecutionEnded" label="业务执行是否结束" width="160" />
        <el-table-column prop="stateMachineTerminal" label="是否为状态机最终终态" width="190" />
        <el-table-column prop="retryAllowed" label="是否允许重试" width="140" />
        <el-table-column prop="cancelAllowed" label="是否允许取消" width="140" />
        <el-table-column prop="formalObjectAllowed" label="是否允许生成正式对象" width="180" />
        <el-table-column prop="enteredThisRound" label="本轮是否实际进入" width="170" />
      </el-table>
    </section>

    <section class="table-card">
      <div class="table-title">
        <h2>模拟结果有效性状态设计</h2>
        <span>{{ resultValidityStateItems.length }} 个未来状态 / 当前结果未创建</span>
      </div>
      <el-table :data="resultValidityStateItems" border stripe>
        <el-table-column prop="code" label="状态编码" min-width="160" />
        <el-table-column prop="name" label="中文名称" min-width="160" />
        <el-table-column prop="meaning" label="说明" min-width="420" />
        <el-table-column prop="currentState" label="当前是否为本状态" width="170" />
      </el-table>
      <ul class="plain-list notes-list">
        <li>completed 不等于 valid，模拟执行完成后仍需要结果有效性判断。</li>
        <li>failed 不等于 invalid，failed 表示本次执行失败，没有形成可用结果；invalid 表示曾经形成结果但之后失效。</li>
        <li>frozen 不表示已经过账或写总账，只表示未来被正式生成动作引用后冻结。</li>
        <li>本轮不创建结果，不写状态历史，因此当前有效性状态只显示“结果未创建”。</li>
      </ul>
    </section>

    <section class="table-card">
      <div class="table-title">
        <h2>模拟执行状态转换事件设计</h2>
        <span>{{ transitionEventItems.length }} 个事件 / 本轮均未触发</span>
      </div>
      <el-table :data="transitionEventItems" border stripe>
        <el-table-column prop="event" label="事件编码" min-width="220" />
        <el-table-column prop="name" label="中文名称" min-width="180" />
        <el-table-column prop="fromStates" label="允许来源状态" min-width="260" />
        <el-table-column prop="targetState" label="目标状态" min-width="160" />
        <el-table-column prop="preconditions" label="必须满足的前置条件" min-width="360" />
        <el-table-column prop="triggeredThisRound" label="本轮是否触发" width="150" />
      </el-table>
    </section>

    <section class="table-card">
      <div class="table-title">
        <h2>模拟执行合法状态转换规则设计</h2>
        <span>{{ allowedTransitionItems.length }} 条合法转换 / 本轮不执行</span>
      </div>
      <el-table :data="allowedTransitionItems" border stripe>
        <el-table-column prop="from" label="来源状态" min-width="220" />
        <el-table-column prop="to" label="目标状态" min-width="180" />
        <el-table-column prop="event" label="事件" min-width="220" />
        <el-table-column prop="rule" label="规则说明" min-width="420" />
        <el-table-column prop="executedThisRound" label="本轮是否执行" width="150" />
      </el-table>
      <div class="final-block-note">
        blocked、failed、timed_out、cancelled 不得直接进入 completed；completed 不得回退到 executing；cleaned 不得恢复为 executing；重新模拟必须创建新的执行请求。
      </div>
    </section>

    <section class="table-card">
      <div class="table-title">
        <h2>模拟执行非法状态转换阻断设计</h2>
        <span>{{ illegalTransitionItems.length }} 条阻断规则 / 本轮不执行阻断动作</span>
      </div>
      <el-table :data="illegalTransitionItems" border stripe>
        <el-table-column prop="from" label="来源状态" min-width="180" />
        <el-table-column prop="to" label="目标状态" min-width="180" />
        <el-table-column prop="reason" label="阻断原因" min-width="420" />
        <el-table-column prop="futureForceBlock" label="未来是否强制阻断" width="170" />
        <el-table-column prop="blockExecutedThisRound" label="本轮是否执行阻断" width="170" />
      </el-table>
    </section>

    <section class="table-card">
      <div class="table-title">
        <h2>模拟执行各阶段输入输出设计</h2>
        <span>{{ stageInputOutputItems.length }} 个阶段 / 本轮均不执行</span>
      </div>
      <el-table :data="stageInputOutputItems" border stripe>
        <el-table-column prop="stage" label="阶段名称" min-width="200" />
        <el-table-column prop="futureInput" label="未来输入" min-width="360" />
        <el-table-column prop="futureOutput" label="未来输出" min-width="360" />
        <el-table-column prop="readFormalBusinessData" label="是否读取正式业务数据" width="190" />
        <el-table-column prop="writeFormalBusinessData" label="是否写正式业务数据" width="190" />
        <el-table-column prop="executedThisRound" label="本轮是否执行" width="150" />
      </el-table>
    </section>

    <section class="table-card">
      <div class="table-title">
        <h2>模拟执行失败分类设计</h2>
        <span>{{ failureTypeItems.length }} 类失败 / 本轮均未产生</span>
      </div>
      <el-table :data="failureTypeItems" border stripe>
        <el-table-column prop="code" label="错误编码" min-width="220" />
        <el-table-column prop="description" label="中文说明" min-width="320" />
        <el-table-column prop="stage" label="发生阶段" min-width="160" />
        <el-table-column prop="retryAllowed" label="是否允许重试" width="140" />
        <el-table-column prop="cleanupRequired" label="是否需要清理" width="140" />
        <el-table-column prop="affectFormalBusinessData" label="是否影响正式业务数据" width="190" />
        <el-table-column prop="generatedThisRound" label="本轮是否产生" width="150" />
      </el-table>
    </section>

    <section class="table-card">
      <div class="table-title">
        <h2>模拟执行失败结果结构设计</h2>
        <span>{{ failureResultFieldItems.length }} 个未来字段 / 本轮均不生成</span>
      </div>
      <el-table :data="failureResultFieldItems" border stripe>
        <el-table-column prop="field" label="字段名" min-width="260" />
        <el-table-column prop="meaning" label="中文含义" min-width="300" />
        <el-table-column prop="futureType" label="未来类型" min-width="160" />
        <el-table-column prop="defaultSafeValue" label="默认安全值" min-width="180" />
        <el-table-column prop="generatedThisRound" label="本轮是否生成" width="150" />
      </el-table>
    </section>

    <section class="table-card protection-card">
      <div class="table-title">
        <h2>模拟执行失败零业务写入机制设计</h2>
        <span>正式业务写入路径接入数：0</span>
      </div>
      <div class="zero-write-grid">
        <article v-for="item in zeroBusinessWriteMetrics" :key="item.label">
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
        </article>
      </div>
      <el-table :data="zeroBusinessWriteProtectionItems" border stripe>
        <el-table-column prop="rule" label="架构原则" min-width="560" />
        <el-table-column prop="executeThisRound" label="本轮是否执行写入或回滚" width="220" />
      </el-table>
    </section>

    <section class="table-card">
      <div class="table-title">
        <h2>模拟临时上下文与清理机制设计</h2>
        <span>{{ temporaryContextItems.length }} 个未来字段 / 本轮不创建</span>
      </div>
      <el-table :data="temporaryContextItems" border stripe>
        <el-table-column prop="field" label="未来字段" min-width="260" />
        <el-table-column prop="meaning" label="中文含义" min-width="420" />
        <el-table-column prop="createdThisRound" label="本轮是否创建" width="150" />
      </el-table>
      <ul class="plain-list notes-list">
        <li v-for="item in cleanupRuleItems" :key="item">{{ item }}</li>
      </ul>
    </section>

    <section class="table-card">
      <div class="table-title">
        <h2>并发锁释放与超时恢复设计</h2>
        <span>{{ lockAndTimeoutRuleItems.length }} 条规则 / 本轮不创建锁</span>
      </div>
      <el-table :data="lockAndTimeoutRuleItems" border stripe>
        <el-table-column prop="rule" label="规则" min-width="520" />
        <el-table-column prop="executeThisRound" label="本轮是否执行" width="150" />
      </el-table>
    </section>

    <section class="table-card">
      <div class="table-title">
        <h2>模拟取消与重试规则设计</h2>
        <span>{{ cancelAndRetryRuleItems.length }} 条规则 / 本轮不取消不重试</span>
      </div>
      <el-table :data="cancelAndRetryRuleItems" border stripe>
        <el-table-column prop="rule" label="规则" min-width="560" />
        <el-table-column prop="executeThisRound" label="本轮是否执行" width="150" />
      </el-table>
    </section>

    <section class="table-card">
      <div class="table-title">
        <h2>模拟状态机审计字段设计</h2>
        <span>{{ stateAuditFieldItems.length }} 个字段 / 本轮不写审计日志</span>
      </div>
      <el-table :data="stateAuditFieldItems" border stripe>
        <el-table-column prop="field" label="字段" min-width="240" />
        <el-table-column prop="meaning" label="中文含义" min-width="360" />
        <el-table-column prop="writeThisRound" label="本轮是否写入" width="150" />
      </el-table>
    </section>

    <section class="table-card gap-card">
      <div class="table-title">
        <h2>当前不允许启动模拟状态机——未满足条件清单</h2>
        <span>{{ unmetStateMachineStartConditionItems.length }} 项</span>
      </div>
      <ul class="plain-list">
        <li v-for="item in unmetStateMachineStartConditionItems" :key="item">{{ item }}</li>
      </ul>
      <div class="final-block-note">
        状态机启动结论：不允许启动；当前是否允许执行状态转换：否；当前是否允许执行模拟：否。
      </div>
    </section>

    <section class="table-card protection-card">
      <div class="table-title">
        <h2>本轮统一保护结论</h2>
        <span>只读测试矩阵和纯函数演算为“是”；状态机及业务执行项目全部为“否”</span>
      </div>
      <div class="protection-grid">
        <article v-for="item in unifiedProtectionConclusion" :key="item.item">
          <span>{{ item.item }}</span>
          <strong>{{ item.value }}</strong>
        </article>
      </div>
    </section>

    <section class="table-card legacy-card">
      <div class="table-title">
        <h2>保留 V1.13.58 / V1.13.59 / V1.13.60 已建立设计</h2>
        <span>继续只读展示</span>
      </div>
      <div class="legacy-grid">
        <article>
          <strong>V1.13.58 模拟前设计</strong>
          <span>保留：不执行模拟前实际检查，不开放模拟按钮。</span>
        </article>
        <article>
          <strong>V1.13.59 模拟结果对象与唯一性规则</strong>
          <span>保留：不创建模拟结果，不生成 PVPSIM 编号。</span>
        </article>
        <article>
          <strong>V1.13.60 最终评审与放行条件</strong>
          <span>保留：最终评审仍为不放行。</span>
        </article>
        <article>
          <strong>UNKNOWN-PEP 安全路径</strong>
          <span>保留：页面不崩溃，不创建任何对象。</span>
        </article>
      </div>
    </section>
  </main>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import BusinessTableScrollContainer from '../components/BusinessTableScrollContainer.vue'
import {
  BUSINESS_ACCEPTANCE_COPY_VERSION,
  buildPageAcceptanceChecklist,
  businessAcceptanceEmptyTexts,
  businessAcceptanceNavigationItems,
  businessAcceptanceSectionTitles,
} from '../runtime/businessAcceptanceCopy.js'
import { classifyTargetEvidence } from '../process/businessTargetEvidenceClassifier.js'
import { listPaymentExecutionPrepares } from '@/meta/finance/paymentExecutionPrepareStore'
import {
  PAYMENT_VOUCHER_PRECHECK_ENGINE_VERSION,
  PAYMENT_VOUCHER_PRECHECK_RULESET_FINGERPRINT,
  PAYMENT_VOUCHER_PRECHECK_RULESET_FINGERPRINT_LOCKS,
  PAYMENT_VOUCHER_PRECHECK_RULESET_MANIFEST,
  PAYMENT_VOUCHER_PRECHECK_RULESET_VERSION,
  evaluatePaymentVoucherPreparePrecheck,
  normalizePaymentVoucherPreparePrecheckInput,
  verifyPaymentVoucherPreparePrecheckPurity,
} from '@/meta/finance/payment-voucher-prepare-simulation/paymentVoucherPreparePrecheckEngine'
import {
  PAYMENT_VOUCHER_PRECHECK_INPUT_CONTRACT_FINGERPRINT,
  PAYMENT_VOUCHER_PRECHECK_INPUT_CONTRACT_VERSION,
  PAYMENT_VOUCHER_PRECHECK_INPUT_FIELDS,
  PAYMENT_VOUCHER_PRECHECK_INPUT_FINGERPRINT_LOCKS,
} from '@/meta/finance/payment-voucher-prepare-simulation/paymentVoucherPreparePrecheckContract'
import {
  PAYMENT_VOUCHER_PRECHECK_BASELINE_FINGERPRINT,
  PAYMENT_VOUCHER_PRECHECK_BASELINE_FINGERPRINT_LOCKS,
  PAYMENT_VOUCHER_PRECHECK_BASELINE_VERSION,
  PAYMENT_VOUCHER_PRECHECK_BASELINES,
  runPaymentVoucherPreparePrecheckGovernanceVerification,
} from '@/meta/finance/payment-voucher-prepare-simulation/paymentVoucherPreparePrecheckBaselines'
import {
  runPaymentVoucherPreparePrecheckTestMatrix,
} from '@/meta/finance/payment-voucher-prepare-simulation/paymentVoucherPreparePrecheckTestMatrix'
import {
  PAYMENT_VOUCHER_PREPARE_SOURCE_ADAPTER_VERSION,
  PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_CONTRACT_FINGERPRINT,
  PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_CONTRACT_FINGERPRINT_LOCKS,
  PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_CONTRACT_VERSION,
  PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_FIELDS,
  adaptPaymentVoucherPrepareSourceToSnapshotInput,
  normalizePaymentVoucherPrepareSourceSnapshot,
  validatePaymentVoucherPrepareSourceSnapshot,
} from '@/meta/finance/payment-voucher-prepare-simulation/paymentVoucherPrepareSourceSnapshot'
import {
  PAYMENT_VOUCHER_PREPARE_SOURCE_FINGERPRINT_VERSION,
  createPaymentVoucherPrepareSourceFingerprint,
} from '@/meta/finance/payment-voucher-prepare-simulation/paymentVoucherPrepareSourceFingerprint'
import {
  PAYMENT_VOUCHER_PREPARE_SOURCE_CHANGE_DETECTOR_VERSION,
  detectPaymentVoucherPrepareSourceChanges,
} from '@/meta/finance/payment-voucher-prepare-simulation/paymentVoucherPrepareSourceChangeDetector'
import {
  runPaymentVoucherPrepareSourceSnapshotTestMatrix,
} from '@/meta/finance/payment-voucher-prepare-simulation/paymentVoucherPrepareSourceSnapshotTestMatrix'
import {
  PAYMENT_VOUCHER_PREPARE_CONCURRENCY_POLICY_FINGERPRINT,
  PAYMENT_VOUCHER_PREPARE_CONCURRENCY_POLICY_FINGERPRINT_LOCKS,
  PAYMENT_VOUCHER_PREPARE_CONCURRENCY_VERSION,
  createPaymentVoucherPrepareLockScopeKey,
  evaluatePaymentVoucherPrepareConcurrencyPreview,
} from '@/meta/finance/payment-voucher-prepare-simulation/paymentVoucherPrepareConcurrencyControl'
import {
  PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_POLICY_FINGERPRINT,
  PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_POLICY_FINGERPRINT_LOCKS,
  PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_VERSION,
  createPaymentVoucherPrepareIdempotencyKey,
  evaluatePaymentVoucherPrepareIdempotencyPreview,
} from '@/meta/finance/payment-voucher-prepare-simulation/paymentVoucherPrepareIdempotency'
import {
  PAYMENT_VOUCHER_PREPARE_REQUEST_ADAPTER_VERSION,
  PAYMENT_VOUCHER_PREPARE_REQUEST_PACKAGE_CONTRACT_FINGERPRINT,
  PAYMENT_VOUCHER_PREPARE_REQUEST_PACKAGE_CONTRACT_FINGERPRINT_LOCKS,
  PAYMENT_VOUCHER_PREPARE_REQUEST_PACKAGE_CONTRACT_VERSION,
  PAYMENT_VOUCHER_PREPARE_REQUEST_PACKAGE_FIELDS,
  adaptPaymentVoucherPrepareToSimulationRequestPackage,
  normalizePaymentVoucherPrepareSimulationRequestPackage,
  validatePaymentVoucherPrepareSimulationRequestPackage,
} from '@/meta/finance/payment-voucher-prepare-simulation/paymentVoucherPrepareSimulationRequestPackage'
import {
  runPaymentVoucherPrepareRequestControlTestMatrix,
} from '@/meta/finance/payment-voucher-prepare-simulation/paymentVoucherPrepareRequestControlTestMatrix'
import {
  PAYMENT_VOUCHER_PREPARE_SIMULATION_AUDIT_CONTRACT_VERSION,
  PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_ADAPTER_VERSION,
  PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_CONTRACT_FINGERPRINT,
  PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_CONTRACT_FINGERPRINT_LOCKS,
  PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_CONTRACT_VERSION,
  PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_FIELDS,
  PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_ISOLATION_KEYS,
  PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LINE_CONTRACT_VERSION,
  PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LINE_FIELDS,
  PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_STORAGE_NAMESPACE,
  PAYMENT_VOUCHER_PREPARE_SIMULATION_AUDIT_NAMESPACE,
  adaptPaymentVoucherPrepareToSimulationResultInput,
  evaluatePaymentVoucherPrepareSimulationResultStoragePreview,
  normalizePaymentVoucherPrepareSimulationResult,
  validatePaymentVoucherPrepareSimulationResult,
  validatePaymentVoucherPrepareSimulationResultLines,
} from '@/meta/finance/payment-voucher-prepare-simulation/paymentVoucherPrepareSimulationResultContract'
import {
  PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LIFECYCLE_FINGERPRINT_LOCKS,
  PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LIFECYCLE_POLICY_FINGERPRINT,
  PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LIFECYCLE_VERSION,
  createPaymentVoucherPrepareSimulationResultLifecycleSummary,
  evaluatePaymentVoucherPrepareSimulationResultInvalidationPreview,
  evaluatePaymentVoucherPrepareSimulationResultLifecycleTransition,
  evaluatePaymentVoucherPrepareSimulationResultSupersedePreview,
} from '@/meta/finance/payment-voucher-prepare-simulation/paymentVoucherPrepareSimulationResultLifecycle'
import {
  PAYMENT_VOUCHER_PREPARE_SIMULATION_AUDIT_CONTRACT_FINGERPRINT,
  PAYMENT_VOUCHER_PREPARE_SIMULATION_AUDIT_CONTRACT_FINGERPRINT_LOCKS,
  PAYMENT_VOUCHER_PREPARE_SIMULATION_AUDIT_FIELDS,
  summarizePaymentVoucherPrepareSimulationAuditTrail,
  validatePaymentVoucherPrepareSimulationAuditContract,
} from '@/meta/finance/payment-voucher-prepare-simulation/paymentVoucherPrepareSimulationAudit'
import {
  runPaymentVoucherPrepareSimulationResultTestMatrix,
} from '@/meta/finance/payment-voucher-prepare-simulation/paymentVoucherPrepareSimulationResultTestMatrix'
import {
  PAYMENT_VOUCHER_PREPARE_SIMULATION_PERMISSION_CONTEXT_FIELDS,
  PAYMENT_VOUCHER_PREPARE_SIMULATION_PERMISSION_POLICY_FINGERPRINT,
  PAYMENT_VOUCHER_PREPARE_SIMULATION_PERMISSION_POLICY_FINGERPRINT_LOCKS,
  PAYMENT_VOUCHER_PREPARE_SIMULATION_PERMISSION_REQUIRED_CODE,
  PAYMENT_VOUCHER_PREPARE_SIMULATION_PERMISSION_VERSION,
  evaluatePaymentVoucherPrepareSimulationPermissionPreview,
} from '@/meta/finance/payment-voucher-prepare-simulation/paymentVoucherPrepareSimulationPermission'
import {
  PAYMENT_VOUCHER_PREPARE_SIMULATION_CONFIRMATION_FIELDS,
  PAYMENT_VOUCHER_PREPARE_SIMULATION_CONFIRMATION_REQUIREMENTS,
  PAYMENT_VOUCHER_PREPARE_SIMULATION_CONFIRMATION_VERSION,
  evaluatePaymentVoucherPrepareSimulationSecondConfirmationPreview,
} from '@/meta/finance/payment-voucher-prepare-simulation/paymentVoucherPrepareSimulationSecondConfirmation'
import {
  PAYMENT_VOUCHER_PREPARE_SIMULATION_EFFECT_FIELDS,
  PAYMENT_VOUCHER_PREPARE_SIMULATION_EFFECT_MANIFEST,
  PAYMENT_VOUCHER_PREPARE_SIMULATION_EFFECT_MANIFEST_VERSION,
  PAYMENT_VOUCHER_PREPARE_SIMULATION_SANDBOX_POLICY_FINGERPRINT,
  PAYMENT_VOUCHER_PREPARE_SIMULATION_SANDBOX_POLICY_FINGERPRINT_LOCKS,
  PAYMENT_VOUCHER_PREPARE_SIMULATION_SANDBOX_VERSION,
  evaluatePaymentVoucherPrepareSimulationSandboxAdmissionPreview,
  summarizePaymentVoucherPrepareSimulationEffectManifest,
} from '@/meta/finance/payment-voucher-prepare-simulation/paymentVoucherPrepareSimulationZeroWriteSandbox'
import {
  runPaymentVoucherPrepareSimulationExecutionGuardTestMatrix,
} from '@/meta/finance/payment-voucher-prepare-simulation/paymentVoucherPrepareSimulationExecutionGuardTestMatrix'
import {
  PAYMENT_VOUCHER_PREPARE_ACCEPTANCE_MANIFEST_VERSION,
} from '@/meta/finance/payment-voucher-prepare-simulation/paymentVoucherPrepareAcceptanceManifest'
import {
  evaluatePaymentVoucherPrepareAcceptanceData,
} from '@/meta/finance/payment-voucher-prepare-simulation/paymentVoucherPrepareAcceptanceEvaluator'
import {
  evaluatePaymentVoucherPrepareButtonWhitelist,
} from '@/meta/finance/payment-voucher-prepare-simulation/paymentVoucherPreparePageAcceptanceRuntime'
import { createAcceptanceFacts } from '../acceptance/acceptanceObservabilityContract.js'
import { getAcceptanceObservabilityFacts } from '@/api/acceptanceObservability.js'

const route = useRoute()
const version = BUSINESS_ACCEPTANCE_COPY_VERSION
const businessAcceptanceCtrlFSearchTerms = [
  businessAcceptanceSectionTitles.manualNavigation,
  businessAcceptanceSectionTitles.targetEvidenceSummary,
  businessAcceptanceSectionTitles.nextStepRelease,
  businessAcceptanceSectionTitles.firstFailure,
  businessAcceptanceSectionTitles.targetEvidenceTrace,
  businessAcceptanceSectionTitles.missingEvidence,
  businessAcceptanceSectionTitles.conflictEvidence,
  businessAcceptanceSectionTitles.readFailure,
  businessAcceptanceSectionTitles.copyDiagnostic,
]
const no = () => '否'
const yes = () => '是'
const notCreated = 'not_created'
const simulationExecutionStatusText = '尚未创建'
const targetEvidenceResultSourceText = '目标证据分类器只读判断'

const statusTextMap = {
  no_runtime_context: '运行时上下文未接入（no_runtime_context）',
  requirements_incomplete: '要求不完整（requirements_incomplete）',
  blocked_by_precheck: '业务预检查阻断（blocked_by_precheck）',
  source_not_found: '来源不存在（source_not_found）',
  blocked_by_permission: '权限预览未通过（blocked_by_permission）',
  blocked_by_confirmation: '二次确认未满足（blocked_by_confirmation）',
  effect_plan_unavailable: '效果计划不可用（effect_plan_unavailable）',
  blocked_by_forbidden_effect: '存在策略禁止效果（blocked_by_forbidden_effect）',
  eligible_preview: '只读预览可准入（eligible_preview）',
}

function businessStatusText(status) {
  return statusTextMap[status] || `${status || '未知状态'}`
}

const routePaymentExecutionPrepareNo = computed(() => String(route.params.paymentExecutionPrepareNo || '').trim())
const routePaymentExecutionPrepareNoText = computed(() => routePaymentExecutionPrepareNo.value || '未提供付款执行准备单号')
const allPaymentExecutionPrepares = computed(() => listPaymentExecutionPrepares())
const currentRow = computed(() => allPaymentExecutionPrepares.value.find((item) => item.paymentExecutionPrepareNo === routePaymentExecutionPrepareNo.value) || null)
const paymentExecutionPrepareFound = computed(() => Boolean(currentRow.value))
const paymentExecutionPrepareNoText = computed(() => currentRow.value?.paymentExecutionPrepareNo || routePaymentExecutionPrepareNoText.value)
const amountValue = computed(() => Number(currentRow.value?.executionAmount || currentRow.value?.orderAmount || 0))
const currentFullUrl = computed(() => (typeof window !== 'undefined' ? window.location.href : `/finance/payment-voucher-prepare-preview/${paymentExecutionPrepareNoText.value}`))
const purePrecheckInput = computed(() => {
  const row = currentRow.value || {}
  const sourcePaymentInstructionPrepareNo = row.sourcePaymentInstructionPrepareNo || row.sourcePaymentOrderPrepareNo || null
  const sourceChainComplete = Boolean(paymentExecutionPrepareFound.value && (sourcePaymentInstructionPrepareNo || row.sourcePaymentApplicationNo || row.sourcePayableConfirmNo || row.sourceInvoicePrepareNo || row.sourceSettlementNo))
  return {
    routePaymentExecutionPrepareNo: routePaymentExecutionPrepareNoText.value,
    paymentExecutionPrepareFound: paymentExecutionPrepareFound.value,
    paymentExecutionPrepareNo: row.paymentExecutionPrepareNo || null,
    reviewStatus: row.paymentExecutionPrepareStatus || row.reviewStatus || 'unknown',
    executionAmount: amountValue.value,
    paymentMethod: row.paymentMethod || null,
    sourcePaymentInstructionPrepareNo,
    sourcePaymentApplicationNo: row.sourcePaymentApplicationNo || null,
    sourcePayableConfirmNo: row.sourcePayableConfirmNo || null,
    sourceInvoicePrepareNo: row.sourceInvoicePrepareNo || null,
    sourceSettlementNo: row.sourceSettlementNo || null,
    sourceChainComplete,
    legalEntityId: null,
    accountingBookId: null,
    currencyCode: row.currencyCode || null,
    baseCurrencyCode: row.baseCurrencyCode || null,
    foreignCurrencyPayment: false,
    exchangeRateType: null,
    exchangeRateDate: null,
    exchangeRate: null,
    exchangeRateSource: null,
    currencyPrecisionReady: false,
    roundingRuleReady: false,
    accountingTemplateId: null,
    accountingTemplateVersion: null,
    accountingTemplateStatus: 'unknown',
    accountingPeriod: null,
    accountingPeriodStatus: 'unknown',
    enterpriseBankAccountReady: false,
    supplierBankAccountReady: false,
    sourceSnapshotReady: false,
    sourceFingerprintReady: false,
    sourceUnchanged: false,
    uniquenessRuleReady: false,
    idempotencyRuleReady: false,
    concurrencyControlReady: false,
    simulationResultStorageReady: false,
    simulationLogStorageReady: false,
    permissionReady: false,
    secondConfirmationReady: false,
    zeroBusinessWriteBoundaryReady: false,
    paymentExecutionStatus: row.paymentExecutionStatus || 'not_executed',
    paymentVoucherStatus: row.paymentVoucherStatus || 'not_generated',
    formalPaymentVoucherStatus: row.formalPaymentVoucherStatus || 'not_generated',
    writeOffStatus: row.writeOffStatus || 'not_written_off',
    ledgerStatus: row.ledgerStatus || 'not_written_ledger',
    postingStatus: row.postingStatus || 'not_posted',
  }
})
const purePrecheckResult = computed(() => evaluatePaymentVoucherPreparePrecheck(purePrecheckInput.value))
const paymentVoucherPrepareTargetNo = computed(() => (
  currentRow.value?.linkedPaymentVoucherPrepareNo
  || currentRow.value?.paymentVoucherPrepareNo
  || currentRow.value?.targetPaymentVoucherPrepareNo
  || ''
))
const paymentVoucherPrepareTargetId = computed(() => (
  currentRow.value?.linkedPaymentVoucherPrepareId
  || currentRow.value?.paymentVoucherPrepareId
  || paymentVoucherPrepareTargetNo.value
  || ''
))
const targetEvidenceDisplayLabels = {
  not_found: '未发现目标对象',
  complete: '完整',
  incomplete: '不完整',
  conflict: '冲突',
  read_failed: '读取失败',
}
const targetEvidenceProcessingStatusLabels = {
  target_not_found: '未发现目标对象，尚未形成目标证据',
  existing_target_complete: '已发现目标记录，处理证据完整',
  existing_target_incomplete: '已发现目标记录，处理证据不完整',
  existing_target_conflict: '已发现目标记录，处理证据存在冲突',
  target_evidence_read_failed: '目标证据读取失败',
}
const paymentVoucherPrepareTargetAction = {
  actionCode: 'CREATE_PAYMENT_VOUCHER_PREPARE',
  sourceObjectType: 'payment_execution_prepare',
  sourceNoField: 'paymentExecutionPrepareNo',
  targetObjectType: 'payment_voucher_prepare',
  targetNoField: 'paymentVoucherPrepareNo',
  targetObjectName: '付款凭证准备',
  nextStepName: '付款凭证准备后续处理',
}
const targetEvidenceSourceObject = computed(() => {
  const row = currentRow.value || {}
  return {
    ...row,
    id: row.id || row.paymentExecutionPrepareId || row.paymentExecutionPrepareNo || routePaymentExecutionPrepareNo.value,
    no: row.paymentExecutionPrepareNo || routePaymentExecutionPrepareNo.value,
    paymentExecutionPrepareNo: row.paymentExecutionPrepareNo || routePaymentExecutionPrepareNo.value,
    flowWritebackStatus: row.paymentVoucherPrepareWritebackStatus || row.paymentVoucherPrepareFlowStatus || row.flowWritebackStatus || '',
  }
})
const targetEvidenceTargetObject = computed(() => {
  if (!paymentVoucherPrepareTargetNo.value && !paymentVoucherPrepareTargetId.value) return null
  return {
    id: paymentVoucherPrepareTargetId.value,
    no: paymentVoucherPrepareTargetNo.value,
    targetObjectNo: paymentVoucherPrepareTargetNo.value,
    paymentVoucherPrepareNo: paymentVoucherPrepareTargetNo.value,
    sourceObjectType: 'payment_execution_prepare',
    sourceObjectId: targetEvidenceSourceObject.value.id,
    sourceObjectNo: targetEvidenceSourceObject.value.paymentExecutionPrepareNo,
    sourceLinkStatus: currentRow.value?.paymentVoucherPrepareSourceLinkStatus || '',
    executionStatus: currentRow.value?.paymentVoucherPrepareExecutionStatus || '',
  }
})
const targetEvidenceClassification = computed(() => classifyTargetEvidence({
  action: paymentVoucherPrepareTargetAction,
  source: targetEvidenceSourceObject.value,
  sourceNo: paymentExecutionPrepareNoText.value,
  target: targetEvidenceTargetObject.value,
  targetObjectLabel: '付款凭证准备',
  nextStepLabel: '付款凭证准备后续处理',
  link: currentRow.value?.paymentVoucherPrepareBusinessFlowLink || null,
  audits: currentRow.value?.paymentVoucherPrepareActionAudits || [],
  candidateTargets: currentRow.value?.paymentVoucherPrepareCandidateTargets || [],
  statusWritebackCompleted: Boolean(currentRow.value?.paymentVoucherPrepareStatusWritebackCompleted),
}))
const targetEvidenceStatusCode = computed(() => targetEvidenceClassification.value.targetEvidenceStatus)
const targetEvidenceStatusText = computed(() => targetEvidenceDisplayLabels[targetEvidenceStatusCode.value] || targetEvidenceStatusCode.value)
const targetObjectNoDisplay = computed(() => {
  if (targetEvidenceClassification.value.targetObjectNoRaw) return targetEvidenceClassification.value.targetObjectNoRaw
  if (targetEvidenceStatusCode.value === 'read_failed') return '目标编号读取失败'
  return '未发现目标对象'
})
const targetEvidenceProcessingStatus = computed(() => ({
  not_found: 'target_not_found',
  complete: 'existing_target_complete',
  incomplete: 'existing_target_incomplete',
  conflict: 'existing_target_conflict',
  read_failed: 'target_evidence_read_failed',
}[targetEvidenceStatusCode.value] || 'target_not_found'))
const targetEvidenceProcessingStatusText = computed(() => (
  targetEvidenceProcessingStatusLabels[targetEvidenceProcessingStatus.value] || targetEvidenceProcessingStatus.value
))
function targetEvidenceSuggestionDirection(row = {}) {
  const responsibility = row.responsibilityCategory || ''
  const category = row.evidenceCategory || ''
  const status = row.evidenceStatus || ''
  const failureType = row.failureType || ''
  if (status === 'passed') return '无需处理'
  if (responsibility === 'source_business_data' || category === 'source_object') return '检查来源付款执行准备对象及其关键字段。'
  if (responsibility === 'target_business_data' || category === 'target_object' || failureType === 'target_not_found' || status === 'not_found') {
    return '检查付款凭证准备目标对象是否已生成，以及来源对象是否正确回写目标编号。'
  }
  if (responsibility === 'relation_writeback' || category === 'source_writeback' || failureType === 'missing_source_writeback') return '检查来源对象是否正确回写目标对象编号。'
  if (category === 'reverse_link' || failureType === 'missing_reverse_link') return '检查目标对象是否正确反向关联来源对象。'
  if (responsibility === 'process_runtime' || category === 'process_link') return '检查业务流程实例及流程关联编号。'
  if (responsibility === 'transaction_evidence' || category === 'transaction_commit') return '检查事务提交记录和业务动作结果证据。'
  if (responsibility === 'status_writeback' || category === 'status_writeback') return '检查来源状态、目标状态及执行状态回写。'
  if (responsibility === 'duplicate_target' || category === 'uniqueness') return '检查同一来源是否存在多个目标对象。'
  if (responsibility === 'read_runtime' || responsibility === 'data_format' || category === 'read_integrity' || status === 'read_failed') return '检查目标对象和关联证据读取过程。'
  if (status === 'not_applicable') return '当前证据项暂不适用，无需处理。'
  return '暂无明确定位，请检查目标证据诊断数据。'
}
const targetEvidenceFirstFailureSummary = computed(() => ({
  label: targetEvidenceClassification.value.targetEvidenceFirstFailureLabel || '未发现异常',
  type: targetEvidenceClassification.value.targetEvidenceFirstFailureCategory || '目标证据',
  reason: targetEvidenceClassification.value.targetEvidenceFirstFailureReason || '目标证据来源链未发现异常。',
  responsibility: targetEvidenceClassification.value.targetEvidenceFirstFailureResponsibilityLabel || '暂无定位',
  blocking: Boolean(targetEvidenceClassification.value.targetEvidenceFirstFailureBlocking),
}))
const precheckFirstBlockSummary = computed(() => {
  const blockedRule = purePrecheckResult.value.ruleResults?.find((item) => item.result === 'blocked')
  if (!blockedRule) {
    return {
      label: '未发现预检查阻断',
      type: '付款凭证准备预检查',
      reason: '当前纯函数预检查未发现阻断项。',
      responsibility: '暂无定位',
    }
  }
  return {
    label: blockedRule.ruleName || blockedRule.ruleCode || '第一预检查阻断项',
    type: blockedRule.category || '付款凭证准备预检查阻断',
    reason: blockedRule.message || blockedRule.reason || '该预检查规则阻断继续模拟。',
    responsibility: blockedRule.responsibility || blockedRule.owner || '付款凭证准备预检查',
  }
})
const targetEvidenceRuntimeRows = computed(() => (targetEvidenceClassification.value.targetEvidenceTraceItems || []).map((item) => ({
  ...item,
  suggestionDirection: targetEvidenceSuggestionDirection(item),
})))
const targetEvidenceMissingItems = computed(() => targetEvidenceClassification.value.targetEvidenceMissingItems || [])
const targetEvidenceConflictItems = computed(() => targetEvidenceClassification.value.targetEvidenceConflictItems || [])
const targetEvidenceReadFailures = computed(() => targetEvidenceClassification.value.targetEvidenceReadFailures || [])
const targetEvidenceCategoryCoverage = computed(() => Array.from(new Set(targetEvidenceRuntimeRows.value.map((item) => item.evidenceCategory))).sort())
const normalizedPurePrecheckInput = computed(() => normalizePaymentVoucherPreparePrecheckInput(purePrecheckInput.value))
const purePrecheckPurity = computed(() => verifyPaymentVoucherPreparePrecheckPurity(purePrecheckInput.value))
const precheckMatrixReport = computed(() => runPaymentVoucherPreparePrecheckTestMatrix())
const governanceSummary = computed(() => runPaymentVoucherPreparePrecheckGovernanceVerification())
const sourceSnapshotContractValidation = computed(() => validatePaymentVoucherPrepareSourceSnapshot())
const sourceSnapshotInput = computed(() => adaptPaymentVoucherPrepareSourceToSnapshotInput(currentRow.value || {}))
const sourceSnapshotPreview = computed(() => normalizePaymentVoucherPrepareSourceSnapshot(sourceSnapshotInput.value))
const sourceFingerprintPreview = computed(() => createPaymentVoucherPrepareSourceFingerprint(sourceSnapshotPreview.value))
const sourceChangePreview = computed(() => detectPaymentVoucherPrepareSourceChanges(null, sourceSnapshotPreview.value))
const sourceSnapshotMatrixReport = computed(() => runPaymentVoucherPrepareSourceSnapshotTestMatrix())
const requestPackageInput = computed(() => adaptPaymentVoucherPrepareToSimulationRequestPackage(currentRow.value || {}, {
  sourceSnapshotResult: sourceSnapshotPreview.value,
  sourceFingerprintResult: sourceFingerprintPreview.value,
  sourceChangeResult: sourceChangePreview.value,
  precheckInput: purePrecheckInput.value,
  precheckResult: purePrecheckResult.value,
}))
const requestPackagePreview = computed(() => normalizePaymentVoucherPrepareSimulationRequestPackage(requestPackageInput.value))
const requestPackageContractValidation = computed(() => validatePaymentVoucherPrepareSimulationRequestPackage())
const idempotencyKeyPreview = computed(() => createPaymentVoucherPrepareIdempotencyKey(requestPackagePreview.value))
const idempotencyResolutionPreview = computed(() => evaluatePaymentVoucherPrepareIdempotencyPreview(requestPackagePreview.value, null))
const concurrencyPreview = computed(() => evaluatePaymentVoucherPrepareConcurrencyPreview(requestPackagePreview.value, null, idempotencyKeyPreview.value.idempotencyKey))
const lockScopePreview = computed(() => createPaymentVoucherPrepareLockScopeKey(requestPackagePreview.value))
const requestControlMatrixReport = computed(() => runPaymentVoucherPrepareRequestControlTestMatrix())
const simulationResultInput = computed(() => adaptPaymentVoucherPrepareToSimulationResultInput(requestPackagePreview.value, {
  idempotencyKey: idempotencyKeyPreview.value.idempotencyKey,
  lockScopeKey: lockScopePreview.value.lockScopeKey,
}))
const simulationResultPreview = computed(() => normalizePaymentVoucherPrepareSimulationResult(simulationResultInput.value))
const simulationResultContractValidation = computed(() => validatePaymentVoucherPrepareSimulationResult())
const simulationResultLineContractValidation = computed(() => validatePaymentVoucherPrepareSimulationResultLines())
const simulationResultStoragePreview = computed(() => evaluatePaymentVoucherPrepareSimulationResultStoragePreview())
const simulationLifecycleSummary = computed(() => createPaymentVoucherPrepareSimulationResultLifecycleSummary())
const simulationLifecycleTransitionPreview = computed(() => evaluatePaymentVoucherPrepareSimulationResultLifecycleTransition({
  currentStatus: simulationResultPreview.value.resultLifecycleStatus,
  requestedStatus: 'created',
  currentValidityStatus: simulationResultPreview.value.resultValidityStatus,
}))
const currentRouteLifecycleDecision = computed(() => {
  const resultAvailable = Boolean(simulationResultPreview.value.resultRecordPreviewCreated && simulationResultPreview.value.resultRecord)
  const reason = paymentExecutionPrepareFound.value
    ? '当前没有模拟结果，不执行生命周期转换或结果失效判断'
    : '付款执行准备来源不存在，且当前没有模拟结果'
  if (!resultAvailable) {
    return {
      currentRouteResultAvailableForTransition: false,
      currentRouteLifecycleTransitionPreviewExecuted: false,
      currentRouteLifecycleTransitionAllowed: false,
      currentRouteInvalidationPreviewEvaluated: false,
      currentRouteShouldInvalidateResultPreview: false,
      currentRouteInvalidationReason: reason,
    }
  }
  const transition = evaluatePaymentVoucherPrepareSimulationResultLifecycleTransition({
    currentStatus: simulationResultPreview.value.resultLifecycleStatus,
    requestedStatus: 'created',
    currentValidityStatus: simulationResultPreview.value.resultValidityStatus,
  })
  return {
    currentRouteResultAvailableForTransition: true,
    currentRouteLifecycleTransitionPreviewExecuted: transition.transitionEvaluated,
    currentRouteLifecycleTransitionAllowed: transition.transitionAllowed,
    currentRouteInvalidationPreviewEvaluated: false,
    currentRouteShouldInvalidateResultPreview: false,
    currentRouteInvalidationReason: '当前存在模拟结果时才允许进入只读生命周期判断',
  }
})
const simulationInvalidationPreview = computed(() => evaluatePaymentVoucherPrepareSimulationResultInvalidationPreview({
  sourceDataFingerprint: 'PVPP-SOURCE-DATA-FP-REFERENCE',
  requestPackageFingerprint: 'PVPP-REQUEST-PACKAGE-FP-REFERENCE',
  ruleSetVersion: PAYMENT_VOUCHER_PRECHECK_RULESET_VERSION,
  inputContractVersion: PAYMENT_VOUCHER_PRECHECK_INPUT_CONTRACT_VERSION,
  accountingTemplateVersion: '1.0.0',
  accountingPeriod: '2026-07',
  currencyCode: 'CNY',
  executionAmount: 100,
  paymentMethod: 'bank_transfer',
  precheckDecision: 'passed',
}, {
  sourceDataFingerprint: 'PVPP-SOURCE-DATA-FP-CHANGED',
  requestPackageFingerprint: 'PVPP-REQUEST-PACKAGE-FP-REFERENCE',
  ruleSetVersion: PAYMENT_VOUCHER_PRECHECK_RULESET_VERSION,
  inputContractVersion: PAYMENT_VOUCHER_PRECHECK_INPUT_CONTRACT_VERSION,
  accountingTemplateVersion: '1.0.0',
  accountingPeriod: '2026-07',
  currencyCode: 'CNY',
  executionAmount: 100,
  paymentMethod: 'bank_transfer',
  precheckDecision: 'passed',
}))
const simulationSupersedePreview = computed(() => evaluatePaymentVoucherPrepareSimulationResultSupersedePreview(
  { resultReferenceNo: 'SIM-RESULT-PREVIEW-001' },
  { resultReferenceNo: 'SIM-RESULT-PREVIEW-002' },
))
const simulationAuditContractValidation = computed(() => validatePaymentVoucherPrepareSimulationAuditContract())
const simulationAuditTrailSummary = computed(() => summarizePaymentVoucherPrepareSimulationAuditTrail([]))
const simulationAuditChainStatus = computed(() => (paymentExecutionPrepareFound.value ? simulationAuditTrailSummary.value.auditChainStatus : 'source_not_found'))
const simulationResultMatrixReport = computed(() => runPaymentVoucherPrepareSimulationResultTestMatrix())
const simulationPermissionContext = computed(() => ({
  contextType: 'payment_voucher_prepare_simulation_permission',
  operationType: 'payment_voucher_prepare_simulation',
  requiredPermissionCode: PAYMENT_VOUCHER_PREPARE_SIMULATION_PERMISSION_REQUIRED_CODE,
  actorId: null,
  actorStatus: null,
  authenticated: false,
  mfaVerified: false,
  permissionCodes: [],
  roleCodes: [],
  organizationId: null,
  legalEntityId: normalizedPurePrecheckInput.value.legalEntityId,
  accountingBookId: normalizedPurePrecheckInput.value.accountingBookId,
  dataScopeType: null,
  dataScopeValues: [],
  delegationReferenceNo: null,
  delegationActive: false,
  sessionReferenceNo: null,
  runtimeContextAvailable: false,
  paymentExecutionPrepareNo: paymentExecutionPrepareFound.value ? paymentExecutionPrepareNoText.value : null,
  sourceFound: paymentExecutionPrepareFound.value,
}))
const simulationPermissionPreview = computed(() => evaluatePaymentVoucherPrepareSimulationPermissionPreview(simulationPermissionContext.value))
const simulationConfirmationPreview = computed(() => evaluatePaymentVoucherPrepareSimulationSecondConfirmationPreview({
  paymentExecutionPrepareNo: paymentExecutionPrepareFound.value ? paymentExecutionPrepareNoText.value : null,
  sourceFound: paymentExecutionPrepareFound.value,
  sourceDataFingerprint: sourceFingerprintPreview.value.sourceDataFingerprint,
  requestPackageFingerprint: requestPackagePreview.value.requestPackageFingerprint,
  idempotencyKey: idempotencyKeyPreview.value.idempotencyKey,
  lockScopeKey: lockScopePreview.value.lockScopeKey,
  executionAmount: amountValue.value,
  currencyCode: normalizedPurePrecheckInput.value.currencyCode,
  paymentMethod: normalizedPurePrecheckInput.value.paymentMethod,
  plannedPaymentDate: normalizedPurePrecheckInput.value.plannedPaymentDate,
  supplierId: currentRow.value?.supplierId || null,
  enterpriseBankAccountId: normalizedPurePrecheckInput.value.enterpriseBankAccountId,
  supplierBankAccountId: normalizedPurePrecheckInput.value.supplierBankAccountId,
  precheckDecision: purePrecheckResult.value.decision,
  precheckCanProceed: purePrecheckResult.value.canProceed,
  sourceUnchanged: normalizedPurePrecheckInput.value.sourceUnchanged,
  permissionDecisionStatus: simulationPermissionPreview.value.permissionDecisionStatus,
  permissionGrantedPreview: simulationPermissionPreview.value.permissionGrantedPreview,
  sandboxPolicyFingerprintMatched: PAYMENT_VOUCHER_PREPARE_SIMULATION_SANDBOX_POLICY_FINGERPRINT === PAYMENT_VOUCHER_PREPARE_SIMULATION_SANDBOX_POLICY_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PREPARE_SIMULATION_SANDBOX_VERSION],
  sandboxPolicyScenarioValidationStatus: 'passed',
  simulationResultStorageReady: normalizedPurePrecheckInput.value.simulationResultStorageReady,
  simulationLogStorageReady: normalizedPurePrecheckInput.value.simulationLogStorageReady,
}))
const simulationSandboxEffectSummary = computed(() => summarizePaymentVoucherPrepareSimulationEffectManifest())
const simulationSandboxAdmissionPreview = computed(() => evaluatePaymentVoucherPrepareSimulationSandboxAdmissionPreview({
  sourceFound: paymentExecutionPrepareFound.value,
  precheckCanProceed: purePrecheckResult.value.canProceed,
  permissionGrantedPreview: simulationPermissionPreview.value.permissionGrantedPreview,
  secondConfirmationSatisfiedPreview: simulationConfirmationPreview.value.secondConfirmationSatisfiedPreview,
  proposedEffects: [],
}))
const executionGuardMatrixReport = computed(() => runPaymentVoucherPrepareSimulationExecutionGuardTestMatrix())
const pageButtonWhitelist = computed(() => evaluatePaymentVoucherPrepareButtonWhitelist([
  '返回付款执行准备',
  '企业结算边界',
  '复制诊断数据',
]))
const serverAcceptanceFacts = ref(null)
const acceptanceFacts = computed(() => serverAcceptanceFacts.value || createAcceptanceFacts({
  pageCode: 'FIN_PAYMENT_VOUCHER_PREPARE_PREVIEW',
  factSource: 'server',
  factLoadContractVersion: 'PCE-FACT-LOAD-CONTRACT-V1.0',
  factLoadStatus: 'read_failed',
  apiUrl: '/api/workflow/action-permissions/acceptance-observability/FIN_PAYMENT_VOUCHER_PREPARE_PREVIEW',
  httpStatus: 0,
  loadedAt: new Date().toISOString(),
  tenantId: 'server-context-unavailable',
  batchId: 'server-context-unavailable',
  errorCode: 'ACCEPTANCE_FACTS_NOT_LOADED',
  errorMessage: '服务端AcceptanceFacts尚未完成加载',
  recordCount: null,
  selectedCount: 0,
  actionCount: 0,
  dangerActionCount: 0,
  businessProgressWriteCount: 0,
  downstreamObjectCount: 0,
  recordCountUnavailableReason: '服务端AcceptanceFacts读取失败',
}))

onMounted(async () => {
  try {
    serverAcceptanceFacts.value = createAcceptanceFacts(
      await getAcceptanceObservabilityFacts('FIN_PAYMENT_VOUCHER_PREPARE_PREVIEW'),
    )
  } catch (error) {
    serverAcceptanceFacts.value = createAcceptanceFacts({
      pageCode: 'FIN_PAYMENT_VOUCHER_PREPARE_PREVIEW',
      factSource: 'server',
      factLoadContractVersion: 'PCE-FACT-LOAD-CONTRACT-V1.0',
      factLoadStatus: 'read_failed',
      apiUrl: '/api/workflow/action-permissions/acceptance-observability/FIN_PAYMENT_VOUCHER_PREPARE_PREVIEW',
      httpStatus: error.httpStatus || 0,
      loadedAt: new Date().toISOString(),
      tenantId: 'server-context-unavailable',
      batchId: 'server-context-unavailable',
      errorCode: error.code || 'ACCEPTANCE_FACTS_READ_FAILED',
      errorMessage: error.message || '服务端AcceptanceFacts读取失败',
      recordCount: null,
      selectedCount: 0,
      actionCount: 0,
      dangerActionCount: 0,
      businessProgressWriteCount: 0,
      downstreamObjectCount: 0,
      recordCountUnavailableReason: '服务端AcceptanceFacts读取失败',
    })
  }
})
const acceptanceDomText = computed(() => ({
  'v113681-acceptance-summary-title': 'V1.14.2.7.2.1 关键验收摘要',
  'v113681-automatic-acceptance-result': '页面运行时自动验收结果',
  'page-version': `${version} · Finance`,
}))
const paymentVoucherPrepareAcceptanceData = computed(() => ({
  route: {
    routeType: paymentExecutionPrepareFound.value ? 'normal_pep' : 'unknown_pep',
    sourceFound: paymentExecutionPrepareFound.value,
    paymentExecutionPrepareNo: paymentExecutionPrepareFound.value ? paymentExecutionPrepareNoText.value : null,
  },
  page: {
    version,
    title: '付款凭证准备模拟权限、二次确认与零业务写入执行沙箱纯函数设计',
    acceptanceTitle: 'V1.14.2.7.2.1 关键验收摘要',
    acceptanceManifestVersion: PAYMENT_VOUCHER_PREPARE_ACCEPTANCE_MANIFEST_VERSION,
  },
  precheck: {
    totalRuleCount: purePrecheckResult.value.totalRuleCount || purePrecheckResult.value.ruleResults.length,
    passedCount: purePrecheckResult.value.passedCount,
    blockedCount: purePrecheckResult.value.blockedCount,
    warningCount: purePrecheckResult.value.warningCount,
    notApplicableCount: purePrecheckResult.value.notApplicableCount,
    decision: purePrecheckResult.value.decision,
    canProceed: purePrecheckResult.value.canProceed,
  },
  execution: {
    currentExecutionState: notCreated,
  },
  readiness: {
    permissionReady: normalizedPurePrecheckInput.value.permissionReady,
    secondConfirmationReady: normalizedPurePrecheckInput.value.secondConfirmationReady,
    zeroBusinessWriteBoundaryReady: normalizedPurePrecheckInput.value.zeroBusinessWriteBoundaryReady,
  },
  permission: {
    permissionDecisionStatus: simulationPermissionPreview.value.permissionDecisionStatus,
    permissionDecisionText: businessStatusText(simulationPermissionPreview.value.permissionDecisionStatus),
    permissionGrantedPreview: simulationPermissionPreview.value.permissionGrantedPreview,
  },
  confirmation: {
    confirmationDecisionStatus: simulationConfirmationPreview.value.confirmationDecisionStatus,
    confirmationDecisionText: businessStatusText(simulationConfirmationPreview.value.confirmationDecisionStatus),
    secondConfirmationSatisfiedPreview: simulationConfirmationPreview.value.secondConfirmationSatisfiedPreview,
  },
  sandbox: {
    sandboxAdmissionStatus: simulationSandboxAdmissionPreview.value.sandboxAdmissionStatus,
    sandboxAdmissionText: businessStatusText(simulationSandboxAdmissionPreview.value.sandboxAdmissionStatus),
    effectManifestCount: simulationSandboxAdmissionPreview.value.effectManifestCount,
    allowedPurePreviewEffectCount: simulationSandboxAdmissionPreview.value.allowedPurePreviewEffectCount,
    forbiddenByPolicyEffectCount: simulationSandboxAdmissionPreview.value.forbiddenByPolicyEffectCount,
    allowedCurrentRouteEffectCount: simulationSandboxAdmissionPreview.value.allowedCurrentRouteEffectCount,
    currentRouteForbiddenEffectCount: simulationSandboxAdmissionPreview.value.currentRouteForbiddenEffectCount,
    currentRouteProposedEffectCount: simulationSandboxAdmissionPreview.value.currentRouteProposedEffectCount,
  },
  protection: {
    stateMachineStartAllowed: false,
    actualSandboxEntered: simulationSandboxAdmissionPreview.value.actualSandboxEntered,
    actualEffectCount: simulationSandboxAdmissionPreview.value.actualEffectCount,
    businessDataWrittenCount: 0,
    businessRollbackCount: 0,
    businessCompensationCount: 0,
    realBusinessObjectCleanupRequiredCount: 0,
  },
  buttons: pageButtonWhitelist.value,
  domText: acceptanceDomText.value,
}))
const automaticAcceptanceResult = computed(() => evaluatePaymentVoucherPrepareAcceptanceData(paymentVoucherPrepareAcceptanceData.value))
const automaticAcceptanceCards = computed(() => [
  { title: '验收清单版本', value: automaticAcceptanceResult.value.acceptanceManifestVersion, desc: 'V1.14.2.7.1', acceptanceId: 'acceptance-manifest-version' },
  { title: '页面运行时验收状态', value: automaticAcceptanceResult.value.overallStatus === 'passed' ? '通过' : '未通过', desc: automaticAcceptanceResult.value.overallStatus, acceptanceId: 'runtime-acceptance-overall-status' },
  { title: '验收项总数', value: automaticAcceptanceResult.value.totalCheckCount, desc: '当前路由适用项', acceptanceId: 'acceptance-total-check-count' },
  { title: '验收通过项数', value: automaticAcceptanceResult.value.passedCheckCount, desc: '自动判断通过', acceptanceId: 'acceptance-passed-check-count' },
  { title: '验收失败项数', value: automaticAcceptanceResult.value.failedCheckCount, desc: '必须为 0', acceptanceId: 'acceptance-failed-check-count' },
  { title: '关键失败项数', value: automaticAcceptanceResult.value.criticalFailedCheckCount, desc: '必须为 0', acceptanceId: 'acceptance-critical-failed-check-count' },
  { title: '人工复核项数', value: automaticAcceptanceResult.value.manualReviewCheckCount, desc: '当前无需人工复核', acceptanceId: 'acceptance-manual-review-check-count' },
  { title: 'DOM 可见性检查项', value: automaticAcceptanceResult.value.domCheckCount, desc: '标题和区域可见', acceptanceId: 'acceptance-dom-check-count' },
  { title: '按钮白名单状态', value: pageButtonWhitelist.value.whitelistStatus === 'passed' ? '通过' : '未通过', desc: `禁止按钮 ${pageButtonWhitelist.value.forbiddenButtonCount} 个`, acceptanceId: 'button-whitelist-status' },
])
const purePrecheckRuleRows = computed(() => purePrecheckResult.value.ruleResults.map((item) => ({
  ...item,
  resultText: precheckResultLabel(item.result),
  writeBusinessDataText: item.writeBusinessData ? yes() : no(),
})))
const purePrecheckSummaryCards = computed(() => [
  { title: '引擎版本', value: PAYMENT_VOUCHER_PRECHECK_ENGINE_VERSION, desc: '独立纯函数模块' },
  { title: '引擎类型', value: purePrecheckResult.value.engineType, desc: '纯函数只读预检查' },
  { title: '纯函数预检查演算', value: '已执行，只读', desc: '本轮唯一允许执行的检查动作' },
  { title: '状态机预检查执行', value: no(), desc: '不进入 prechecking' },
  { title: '状态机启动', value: no(), desc: '不创建模拟请求' },
  { title: '状态转换执行', value: no(), desc: '不进入 precheck_pending' },
  { title: '模拟执行', value: no(), desc: '不执行模拟计算' },
  { title: '业务数据写入', value: no(), desc: '正式业务写入为 0' },
  { title: '当前预检查决策', value: precheckResultLabel(purePrecheckResult.value.decision), desc: '正常 PEP 与 UNKNOWN-PEP 均保持阻断口径' },
  { title: '是否允许继续模拟', value: purePrecheckResult.value.canProceed ? yes() : no(), desc: '存在阻断项时为否' },
  { title: '通过项数量', value: purePrecheckResult.value.passedCount, desc: '只读统计' },
  { title: '阻断项数量', value: purePrecheckResult.value.blockedCount, desc: '只读统计' },
  { title: '警告项数量', value: purePrecheckResult.value.warningCount, desc: '只读统计' },
  { title: '不适用项数量', value: purePrecheckResult.value.notApplicableCount, desc: '只读统计' },
])
const purePrecheckPurityCards = computed(() => [
  { title: '相同输入产生相同输出', value: purePrecheckPurity.value.sameInputSameOutput ? yes() : no() },
  { title: '输入对象被修改', value: purePrecheckPurity.value.inputMutated ? yes() : no() },
  { title: '读取业务 Store', value: purePrecheckPurity.value.readBusinessDataSource ? yes() : no() },
  { title: '修改业务 Store', value: purePrecheckPurity.value.modifyBusinessDataSource ? yes() : no() },
  { title: '写 localStorage', value: purePrecheckPurity.value.localStorageWritten ? yes() : no() },
  { title: '调用网络接口', value: purePrecheckPurity.value.networkCalled ? yes() : no() },
  { title: '获取当前时间', value: purePrecheckPurity.value.currentTimeRead ? yes() : no() },
  { title: '生成随机值', value: purePrecheckPurity.value.randomValueGenerated ? yes() : no() },
  { title: '创建模拟执行请求', value: purePrecheckPurity.value.simulationRequestCreated ? yes() : no() },
  { title: '执行状态转换', value: purePrecheckPurity.value.stateTransitionExecuted ? yes() : no() },
  { title: '写正式业务数据', value: purePrecheckPurity.value.formalBusinessDataWritten ? yes() : no() },
])

const simulationResultAcceptanceCards = computed(() => [
  { title: '页面版本', value: version, desc: version, acceptanceId: 'page-version-card' },
  { title: '付款执行准备是否存在', value: paymentExecutionPrepareFound.value ? yes() : no(), desc: paymentExecutionPrepareNoText.value, acceptanceId: 'source-found' },
  { title: '当前预检查规则总数', value: purePrecheckResult.value.totalRuleCount || purePrecheckResult.value.ruleResults.length, desc: '固定 32 条', acceptanceId: 'precheck-total-rule-count' },
  { title: '权限上下文字段数', value: PAYMENT_VOUCHER_PREPARE_SIMULATION_PERMISSION_CONTEXT_FIELDS.length, desc: '固定 20 字段' },
  { title: '权限策略指纹是否匹配', value: simulationPermissionPreview.value.permissionPolicyFingerprintMatched ? yes() : no(), desc: simulationPermissionPreview.value.permissionPolicyFingerprint },
  { title: '当前权限判断状态', value: businessStatusText(simulationPermissionPreview.value.permissionDecisionStatus), desc: '当前路由只读判断', acceptanceId: 'permission-decision-status' },
  { title: '当前是否授予真实权限', value: simulationPermissionPreview.value.actualPermissionGranted ? yes() : no(), desc: '必须为否' },
  { title: '二次确认字段数', value: PAYMENT_VOUCHER_PREPARE_SIMULATION_CONFIRMATION_FIELDS.length, desc: '固定 32 字段' },
  { title: '二次确认要求数量', value: PAYMENT_VOUCHER_PREPARE_SIMULATION_CONFIRMATION_REQUIREMENTS.length, desc: '固定 12 项' },
  { title: '当前二次确认状态', value: businessStatusText(simulationConfirmationPreview.value.confirmationDecisionStatus), desc: '不创建确认挑战', acceptanceId: 'confirmation-decision-status' },
  { title: '是否生成确认编号', value: simulationConfirmationPreview.value.confirmationReferenceNo || '未生成', desc: '必须未生成' },
  { title: '是否生成确认令牌', value: simulationConfirmationPreview.value.confirmationTokenGenerated ? yes() : no(), desc: '必须为否' },
  { title: '沙箱策略指纹是否匹配', value: simulationSandboxAdmissionPreview.value.sandboxPolicyFingerprintMatched ? yes() : no(), desc: simulationSandboxAdmissionPreview.value.sandboxPolicyFingerprint },
  { title: '效果字段数', value: PAYMENT_VOUCHER_PREPARE_SIMULATION_EFFECT_FIELDS.length, desc: '固定 16 字段' },
  { title: '效果编码数', value: PAYMENT_VOUCHER_PREPARE_SIMULATION_EFFECT_MANIFEST.length, desc: '固定 40 个', acceptanceId: 'effect-manifest-count' },
  { title: '允许纯函数预览效果数', value: simulationSandboxAdmissionPreview.value.allowedPurePreviewEffectCount, desc: 'V1.14.2.7.1 固定 18', acceptanceId: 'allowed-pure-preview-effect-count' },
  { title: '策略禁止效果数', value: simulationSandboxAdmissionPreview.value.forbiddenByPolicyEffectCount, desc: 'V1.14.2.7.1 固定 22', acceptanceId: 'forbidden-by-policy-effect-count' },
  { title: '当前路由允许效果数', value: simulationSandboxAdmissionPreview.value.allowedCurrentRouteEffectCount, desc: '当前必须为 0', acceptanceId: 'allowed-current-route-effect-count' },
  { title: '当前路由禁止效果数', value: simulationSandboxAdmissionPreview.value.currentRouteForbiddenEffectCount, desc: '当前必须为 0', acceptanceId: 'current-route-forbidden-effect-count' },
  { title: '当前路由拟执行效果数', value: simulationSandboxAdmissionPreview.value.currentRouteProposedEffectCount, desc: '当前必须为 0', acceptanceId: 'current-route-proposed-effect-count' },
  { title: '当前沙箱准入状态', value: businessStatusText(simulationSandboxAdmissionPreview.value.sandboxAdmissionStatus), desc: '当前路由只读判断', acceptanceId: 'sandbox-admission-status' },
  { title: '当前是否进入真实沙箱', value: simulationSandboxAdmissionPreview.value.actualSandboxEntered ? yes() : no(), desc: '必须为否' },
  { title: '当前实际效果数量', value: simulationSandboxAdmissionPreview.value.actualEffectCount, desc: '必须为 0', acceptanceId: 'actual-effect-count' },
  { title: '执行防护矩阵结果', value: precheckResultLabel(executionGuardMatrixReport.value.overallStatus), desc: `${executionGuardMatrixReport.value.testCaseCount} 个用例` },
  { title: '模拟结果适配器版本', value: PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_ADAPTER_VERSION, desc: '只读适配' },
  { title: '模拟结果记录契约版本', value: PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_CONTRACT_VERSION, desc: '固定 60 字段' },
  { title: '模拟结果明细契约版本', value: PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LINE_CONTRACT_VERSION, desc: '固定 18 字段' },
  { title: '生命周期策略版本', value: PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LIFECYCLE_VERSION, desc: '只读状态策略' },
  { title: '审计事件契约版本', value: PAYMENT_VOUCHER_PREPARE_SIMULATION_AUDIT_CONTRACT_VERSION, desc: '固定 24 字段' },
  { title: '结果记录字段数', value: simulationResultContractValidation.value.resultFieldCount, desc: '必须为 60' },
  { title: '结果明细字段数', value: simulationResultLineContractValidation.value.resultLineFieldCount, desc: '必须为 18' },
  { title: '审计事件字段数', value: simulationAuditContractValidation.value.auditFieldCount, desc: '必须为 24' },
  { title: '三个新指纹是否匹配', value: simulationResultContractValidation.value.resultContractFingerprintMatched && simulationLifecycleSummary.value.lifecyclePolicyFingerprintMatched && simulationAuditContractValidation.value.auditContractFingerprintMatched ? yes() : no(), desc: '结果、生命周期、审计' },
  { title: '结果存储命名空间', value: PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_STORAGE_NAMESPACE, desc: '独立命名空间' },
  { title: '审计存储命名空间', value: PAYMENT_VOUCHER_PREPARE_SIMULATION_AUDIT_NAMESPACE, desc: '独立命名空间' },
  { title: '是否与正式业务共用命名空间', value: simulationResultStoragePreview.value.sharesFormalBusinessNamespace ? yes() : no(), desc: '必须为否' },
  { title: '是否与正式业务共用 Store 集合', value: simulationResultStoragePreview.value[PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_ISOLATION_KEYS.businessCollectionFlag] ? yes() : no(), desc: '必须为否' },
  { title: '是否使用 localStorage', value: simulationResultStoragePreview.value[PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_ISOLATION_KEYS.browserStorageFlag] ? yes() : no(), desc: '必须为否' },
  { title: '是否影响正式业务对象', value: simulationResultStoragePreview.value.formalBusinessObjectAffected ? yes() : no(), desc: '必须为否' },
  { title: '正式模拟结果存储是否落地', value: simulationResultPreview.value.businessSimulationResultStorageReady ? yes() : no(), desc: '本轮保持否' },
  { title: '当前是否存在模拟执行请求', value: simulationResultPreview.value.simulationRequestAvailable ? yes() : no(), desc: '当前为否' },
  { title: '当前是否存在模拟计算结果', value: simulationResultPreview.value.simulationCalculationAvailable ? yes() : no(), desc: '当前为否' },
  { title: '结果记录预览是否创建', value: simulationResultPreview.value.resultRecordPreviewCreated ? yes() : no(), desc: '当前不得创建' },
  { title: '当前结果记录状态', value: simulationResultStatusLabel(simulationResultPreview.value.resultRecordStatus), desc: '正常 PEP 未创建，UNKNOWN 来源不存在' },
  { title: '当前结果生命周期', value: simulationResultPreview.value.resultLifecycleStatus, desc: '保持 not_created' },
  { title: '当前结果有效性', value: simulationResultPreview.value.resultValidityStatus, desc: '保持 unknown' },
  { title: '当前结果编号', value: simulationResultPreview.value.resultRecord?.resultReferenceNo || '未生成', desc: '运行时字段保持 null' },
  { title: '当前结果明细数量', value: simulationResultPreview.value.resultLineCount, desc: '当前为 0' },
  { title: '当前结果记录指纹', value: simulationResultPreview.value.resultRecordFingerprint || '未生成', desc: '当前不得生成' },
  { title: '是否实际保存模拟结果', value: simulationResultPreview.value.businessSimulationResultStorageReady ? yes() : no(), desc: '必须为否' },
  { title: '生命周期策略合成验证', value: simulationLifecycleSummary.value.lifecyclePolicyFingerprintMatched ? '通过' : '失败', desc: simulationLifecycleSummary.value.lifecyclePolicyFingerprint },
  { title: '合法转换合成场景', value: simulationLifecycleMatrixPassed.value ? '通过' : '失败', desc: '测试矩阵覆盖合法转换' },
  { title: '非法逆向转换合成场景', value: simulationInvalidTransitionBlocked.value ? '通过' : '失败', desc: '测试矩阵覆盖非法转换' },
  { title: '失效规则合成场景', value: simulationInvalidationScenarioPassed.value ? '通过' : '失败', desc: '测试矩阵覆盖合成失效规则' },
  { title: '当前是否存在可转换的模拟结果', value: currentRouteLifecycleDecision.value.currentRouteResultAvailableForTransition ? yes() : no(), desc: '当前路由业务判断' },
  { title: '当前是否执行生命周期转换预览', value: currentRouteLifecycleDecision.value.currentRouteLifecycleTransitionPreviewExecuted ? yes() : no(), desc: '当前路由业务判断' },
  { title: '当前是否允许生命周期转换', value: currentRouteLifecycleDecision.value.currentRouteLifecycleTransitionAllowed ? yes() : no(), desc: '当前路由业务判断' },
  { title: '当前是否执行结果失效判断', value: currentRouteLifecycleDecision.value.currentRouteInvalidationPreviewEvaluated ? yes() : no(), desc: '当前路由业务判断' },
  { title: '当前是否建议失效结果', value: currentRouteLifecycleDecision.value.currentRouteShouldInvalidateResultPreview ? yes() : no(), desc: '当前路由业务判断' },
  { title: '原因', value: currentRouteLifecycleDecision.value.currentRouteInvalidationReason, desc: '当前路由业务判断' },
  { title: '已验证结果是否允许原地覆盖', value: simulationLifecycleSummary.value.validatedInPlaceOverwriteAllowed ? yes() : no(), desc: '必须为否' },
  { title: '已冻结结果是否允许原地覆盖', value: simulationLifecycleSummary.value.frozenInPlaceOverwriteAllowed ? yes() : no(), desc: '必须为否' },
  { title: '来源变化是否建议失效结果', value: simulationInvalidationPreview.value.shouldInvalidateResultPreview ? '是，仅为合成场景规则' : no(), desc: '不实际作废' },
  { title: '当前是否实际失效结果', value: simulationInvalidationPreview.value.actualResultInvalidated ? yes() : no(), desc: '必须为否' },
  { title: '当前是否实际替代结果', value: simulationSupersedePreview.value.actualResultSuperseded ? yes() : no(), desc: '必须为否' },
  { title: '当前是否实际归档结果', value: no(), desc: '必须为否' },
  { title: '审计契约验证', value: simulationAuditContractValidation.value.auditContractFingerprintMatched ? '通过' : '失败', desc: simulationAuditContractValidation.value.auditContractFingerprint },
  { title: '追加式日志规则', value: simulationAuditAppendRulePassed.value ? '通过' : '失败', desc: '事件顺序和前序指纹' },
  { title: '审计事件指纹链验证', value: simulationAuditChainRulePassed.value ? '通过' : '失败', desc: '合成场景验证' },
  { title: '当前真实审计事件数', value: 0, desc: '当前业务日志为 0' },
  { title: '当前是否创建审计事件', value: no(), desc: '必须为否' },
  { title: '当前审计链状态', value: auditChainStatusLabel(simulationAuditChainStatus.value), desc: '正常 PEP 无事件，UNKNOWN 来源不存在' },
  { title: '是否修改历史审计事件', value: no(), desc: '必须为否' },
  { title: '正式模拟审计存储是否落地', value: simulationAuditTrailSummary.value.businessSimulationAuditStorageReady ? yes() : no(), desc: '本轮保持否' },
  { title: 'simulationResultStorageReady', value: String(normalizedPurePrecheckInput.value.simulationResultStorageReady), desc: '保持 false' },
  { title: 'simulationLogStorageReady', value: String(normalizedPurePrecheckInput.value.simulationLogStorageReady), desc: '保持 false' },
  { title: '当前预检查通过项数量', value: purePrecheckResult.value.passedCount, desc: '正常 PEP 11，UNKNOWN 6', acceptanceId: 'precheck-passed-count' },
  { title: '当前预检查阻断项数量', value: purePrecheckResult.value.blockedCount, desc: '正常 PEP 20，UNKNOWN 25', acceptanceId: 'precheck-blocked-count' },
  { title: '当前预检查警告项数量', value: purePrecheckResult.value.warningCount, desc: '保持 0', acceptanceId: 'precheck-warning-count' },
  { title: '当前预检查不适用项数量', value: purePrecheckResult.value.notApplicableCount, desc: '保持 1', acceptanceId: 'precheck-not-applicable-count' },
  { title: '当前业务预检查决策', value: precheckResultLabel(purePrecheckResult.value.decision), desc: '仍为阻断', acceptanceId: 'precheck-decision' },
  { title: '当前是否允许继续模拟', value: purePrecheckResult.value.canProceed ? yes() : no(), desc: '仍为否', acceptanceId: 'precheck-can-proceed' },
  { title: '当前执行状态', value: notCreated, desc: '状态机未创建', acceptanceId: 'current-execution-state' },
  { title: '状态机是否启动', value: no(), desc: '未启动', acceptanceId: 'state-machine-start-allowed' },
  { title: '真实模拟结果创建数量', value: 0, desc: '零创建' },
  { title: '真实审计事件创建数量', value: 0, desc: '零创建' },
  { title: '正式业务写入数量', value: 0, desc: '零写入', acceptanceId: 'business-data-written-count' },
  { title: '正式业务回滚数量', value: 0, desc: '零回滚', acceptanceId: 'business-rollback-count' },
  { title: '正式业务补偿数量', value: 0, desc: '零补偿', acceptanceId: 'business-compensation-count' },
  { title: '需要清理真实业务对象数量', value: 0, desc: '零清理', acceptanceId: 'real-business-object-cleanup-required-count' },
  { title: '既有规则集指纹保持', value: governanceSummary.value.ruleSetFingerprintMatched ? yes() : no(), desc: governanceSummary.value.ruleSetFingerprint },
  { title: '既有输入契约指纹保持', value: governanceSummary.value.inputContractFingerprintMatched ? yes() : no(), desc: governanceSummary.value.inputContractFingerprint },
  { title: '既有回归基线指纹保持', value: governanceSummary.value.baselineFingerprintMatched ? yes() : no(), desc: governanceSummary.value.baselineFingerprint },
  { title: '来源快照契约指纹保持', value: sourceSnapshotContractValidation.value.snapshotContractFingerprintMatched ? yes() : no(), desc: PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_CONTRACT_FINGERPRINT },
  { title: '请求输入包契约指纹保持', value: requestPackageContractValidation.value.requestPackageContractFingerprintMatched ? yes() : no(), desc: PAYMENT_VOUCHER_PREPARE_REQUEST_PACKAGE_CONTRACT_FINGERPRINT },
  { title: '幂等策略指纹保持', value: PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_POLICY_FINGERPRINT === PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_POLICY_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_VERSION] ? yes() : no(), desc: PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_POLICY_FINGERPRINT },
  { title: '并发策略指纹保持', value: PAYMENT_VOUCHER_PREPARE_CONCURRENCY_POLICY_FINGERPRINT === PAYMENT_VOUCHER_PREPARE_CONCURRENCY_POLICY_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PREPARE_CONCURRENCY_VERSION] ? yes() : no(), desc: PAYMENT_VOUCHER_PREPARE_CONCURRENCY_POLICY_FINGERPRINT },
  { title: '原三组测试矩阵', value: precheckMatrixReport.value.overallStatus === 'passed' && sourceSnapshotMatrixReport.value.overallStatus === 'passed' && requestControlMatrixReport.value.overallStatus === 'passed' ? '全部通过' : '存在失败', desc: '预检查、来源快照、请求控制' },
  { title: '模拟结果测试矩阵', value: precheckResultLabel(simulationResultMatrixReport.value.overallStatus), desc: `${simulationResultMatrixReport.value.testCaseCount} 个用例` },
])

const executionGuardAcceptanceCards = computed(() => [
  { title: '权限策略合成验证', value: precheckResultLabel(executionGuardMatrixReport.value.overallStatus), desc: simulationPermissionPreview.value.permissionPolicyFingerprint },
  { title: '当前权限只读判断', value: businessStatusText(simulationPermissionPreview.value.permissionDecisionStatus), desc: simulationPermissionPreview.value.permissionGrantedPreview ? '预览通过' : '预览未通过', acceptanceId: 'permission-decision-status' },
  { title: '当前真实权限运行时', value: simulationPermissionPreview.value.runtimeContextAvailable ? yes() : no(), desc: '本轮不读取真实身份运行时' },
  { title: '授予真实权限', value: simulationPermissionPreview.value.actualPermissionGranted ? yes() : no(), desc: '必须为否' },
  { title: '二次确认摘要预览', value: simulationConfirmationPreview.value.confirmationSummaryPreviewCreated ? yes() : no(), desc: simulationConfirmationPreview.value.confirmationSummaryStatus },
  { title: '二次确认状态', value: businessStatusText(simulationConfirmationPreview.value.confirmationDecisionStatus), desc: '不创建挑战、不生成令牌', acceptanceId: 'confirmation-decision-status' },
  { title: '确认挑战是否创建', value: simulationConfirmationPreview.value.confirmationChallengeCreated ? yes() : no(), desc: '必须为否' },
  { title: '真实二次确认是否完成', value: simulationConfirmationPreview.value.actualConfirmationCompleted ? yes() : no(), desc: '必须为否' },
  { title: '沙箱策略合成验证', value: simulationSandboxAdmissionPreview.value.sandboxPolicyScenarioValidationStatus, desc: simulationSandboxAdmissionPreview.value.sandboxPolicyFingerprint },
  { title: '当前沙箱准入判断', value: businessStatusText(simulationSandboxAdmissionPreview.value.sandboxAdmissionStatus), desc: '当前路由只读判断', acceptanceId: 'sandbox-admission-status' },
  { title: '是否进入真实沙箱', value: simulationSandboxAdmissionPreview.value.actualSandboxEntered ? yes() : no(), desc: '必须为否', acceptanceId: 'actual-sandbox-entered' },
  { title: '正式业务写入检测', value: simulationSandboxAdmissionPreview.value.formalBusinessWriteDetected ? yes() : no(), desc: '必须为否' },
  { title: 'permissionReady', value: String(normalizedPurePrecheckInput.value.permissionReady), desc: '保持 false', acceptanceId: 'permission-ready' },
  { title: 'secondConfirmationReady', value: String(normalizedPurePrecheckInput.value.secondConfirmationReady), desc: '保持 false', acceptanceId: 'second-confirmation-ready' },
  { title: 'zeroBusinessWriteBoundaryReady', value: String(normalizedPurePrecheckInput.value.zeroBusinessWriteBoundaryReady), desc: '保持 false', acceptanceId: 'zero-business-write-boundary-ready' },
  { title: '执行防护测试用例数', value: executionGuardMatrixReport.value.testCaseCount, desc: '不少于 120' },
  { title: '执行防护失败用例数', value: executionGuardMatrixReport.value.failedCaseCount, desc: '必须为 0' },
  { title: '执行防护失败断言数', value: executionGuardMatrixReport.value.failedAssertionCount, desc: '必须为 0' },
])

const permissionPreviewCards = computed(() => [
  { title: '权限策略版本', value: PAYMENT_VOUCHER_PREPARE_SIMULATION_PERMISSION_VERSION, desc: '新增策略版本' },
  { title: '所需权限点', value: PAYMENT_VOUCHER_PREPARE_SIMULATION_PERMISSION_REQUIRED_CODE, desc: '固定权限点' },
  { title: '权限策略指纹', value: simulationPermissionPreview.value.permissionPolicyFingerprint, desc: simulationPermissionPreview.value.permissionPolicyFingerprintMatched ? '匹配' : '不匹配' },
  { title: '权限判断状态', value: businessStatusText(simulationPermissionPreview.value.permissionDecisionStatus), desc: '按优先级判断', acceptanceId: 'permission-decision-status' },
  { title: '运行时上下文可用', value: simulationPermissionPreview.value.runtimeContextAvailable ? yes() : no(), desc: '当前必须为否' },
  { title: '权限预览通过', value: simulationPermissionPreview.value.permissionGrantedPreview ? yes() : no(), desc: '当前必须为否' },
  { title: '真实授权', value: simulationPermissionPreview.value.actualPermissionGranted ? yes() : no(), desc: '当前必须为否' },
  { title: '业务权限机制就绪', value: simulationPermissionPreview.value.businessPermissionMechanismReady ? yes() : no(), desc: '当前保持 false' },
])

const permissionContextRows = computed(() => PAYMENT_VOUCHER_PREPARE_SIMULATION_PERMISSION_CONTEXT_FIELDS.map((item) => ({
  field: item.field,
  chineseName: item.chineseName,
  type: item.type,
  requiredText: item.requiredForGrantedPreview ? yes() : no(),
  runtimeSource: item.sourceDescription,
})))

const confirmationPreviewCards = computed(() => [
  { title: '二次确认契约版本', value: PAYMENT_VOUCHER_PREPARE_SIMULATION_CONFIRMATION_VERSION, desc: '新增确认版本' },
  { title: '确认字段数', value: PAYMENT_VOUCHER_PREPARE_SIMULATION_CONFIRMATION_FIELDS.length, desc: '固定 32 字段' },
  { title: '确认要求数量', value: PAYMENT_VOUCHER_PREPARE_SIMULATION_CONFIRMATION_REQUIREMENTS.length, desc: '固定 12 项' },
  { title: '确认摘要状态', value: simulationConfirmationPreview.value.confirmationSummaryStatus, desc: '只读预览' },
  { title: '摘要指纹是否生成', value: simulationConfirmationPreview.value.confirmationSummaryFingerprintPreviewGenerated ? yes() : no(), desc: '仅预览，不保存' },
  { title: '缺失要求数量', value: simulationConfirmationPreview.value.missingRequirementCount, desc: '当前仍不满足' },
  { title: '确认挑战创建', value: simulationConfirmationPreview.value.confirmationChallengeCreated ? yes() : no(), desc: '必须为否' },
  { title: '确认令牌生成', value: simulationConfirmationPreview.value.confirmationTokenGenerated ? yes() : no(), desc: '必须为否' },
  { title: '显式用户确认', value: simulationConfirmationPreview.value.explicitUserConfirmed ? yes() : no(), desc: '必须为否' },
  { title: '真实二次确认完成', value: simulationConfirmationPreview.value.actualConfirmationCompleted ? yes() : no(), desc: '必须为否' },
])

const confirmationRequirementRows = computed(() => {
  if (simulationConfirmationPreview.value.requirementResults?.length) {
    return simulationConfirmationPreview.value.requirementResults.map((item) => ({
      ...item,
      satisfiedText: item.satisfied ? yes() : no(),
      blockReason: item.blockReason || '-',
    }))
  }
  return PAYMENT_VOUCHER_PREPARE_SIMULATION_CONFIRMATION_REQUIREMENTS.map((item) => ({
    ...item,
    satisfiedText: no(),
    blockReason: paymentExecutionPrepareFound.value ? '未进入确认预览' : '付款执行准备来源不存在',
  }))
})

const sandboxPreviewCards = computed(() => [
  { title: '沙箱策略版本', value: PAYMENT_VOUCHER_PREPARE_SIMULATION_SANDBOX_VERSION, desc: '新增沙箱版本' },
  { title: '效果清单版本', value: PAYMENT_VOUCHER_PREPARE_SIMULATION_EFFECT_MANIFEST_VERSION, desc: '新增效果清单版本' },
  { title: '效果字段数', value: simulationSandboxEffectSummary.value.effectFieldCount, desc: '固定 16 字段' },
  { title: '效果编码数', value: simulationSandboxEffectSummary.value.effectManifestCount, desc: '固定 40 个' },
  { title: '允许纯函数预览效果数', value: simulationSandboxEffectSummary.value.allowedPurePreviewEffectCount, desc: 'V1.14.2.7.1 固定 18', acceptanceId: 'allowed-pure-preview-effect-count' },
  { title: '策略禁止效果数', value: simulationSandboxEffectSummary.value.forbiddenByPolicyEffectCount, desc: 'V1.14.2.7.1 固定 22', acceptanceId: 'forbidden-by-policy-effect-count' },
  { title: '当前路由允许效果数', value: simulationSandboxEffectSummary.value.allowedCurrentRouteEffectCount, desc: '当前必须为 0', acceptanceId: 'allowed-current-route-effect-count' },
  { title: '当前路由禁止效果数', value: simulationSandboxEffectSummary.value.currentRouteForbiddenEffectCount, desc: '当前必须为 0', acceptanceId: 'current-route-forbidden-effect-count' },
  { title: '当前路由拟执行效果数', value: simulationSandboxEffectSummary.value.currentRouteProposedEffectCount, desc: '当前必须为 0', acceptanceId: 'current-route-proposed-effect-count' },
  { title: '沙箱策略指纹', value: simulationSandboxAdmissionPreview.value.sandboxPolicyFingerprint, desc: simulationSandboxAdmissionPreview.value.sandboxPolicyFingerprintMatched ? '匹配' : '不匹配' },
  { title: '沙箱准入状态', value: businessStatusText(simulationSandboxAdmissionPreview.value.sandboxAdmissionStatus), desc: '当前路由只读判断', acceptanceId: 'sandbox-admission-status' },
  { title: '效果计划可用', value: simulationSandboxAdmissionPreview.value.currentRouteEffectPlanAvailable ? yes() : no(), desc: '当前没有真实效果计划' },
  { title: '可进入沙箱预览', value: simulationSandboxAdmissionPreview.value.canEnterSandboxPreview ? yes() : no(), desc: '当前必须为否' },
  { title: '真实沙箱已进入', value: simulationSandboxAdmissionPreview.value.actualSandboxEntered ? yes() : no(), desc: '当前必须为否', acceptanceId: 'actual-sandbox-entered' },
  { title: '实际效果数量', value: simulationSandboxAdmissionPreview.value.actualEffectCount, desc: '当前必须为 0', acceptanceId: 'actual-effect-count' },
])

const sandboxEffectRows = computed(() => PAYMENT_VOUCHER_PREPARE_SIMULATION_EFFECT_MANIFEST.map((item) => ({
  ...item,
  allowedText: item.allowedInCurrentVersion ? yes() : no(),
  writesFormalBusinessDataText: item.writesFormalBusinessData ? yes() : no(),
})))

const executionGuardMatrixCards = computed(() => [
  { title: '矩阵版本', value: executionGuardMatrixReport.value.matrixVersion, desc: executionGuardMatrixReport.value.matrixMode },
  { title: '测试用例数', value: executionGuardMatrixReport.value.testCaseCount, desc: '不少于 120' },
  { title: '通过用例数', value: executionGuardMatrixReport.value.passedCaseCount, desc: '全部通过' },
  { title: '失败用例数', value: executionGuardMatrixReport.value.failedCaseCount, desc: '必须为 0' },
  { title: '断言数', value: executionGuardMatrixReport.value.assertionCount, desc: '执行防护断言' },
  { title: '失败断言数', value: executionGuardMatrixReport.value.failedAssertionCount, desc: '必须为 0' },
  { title: '权限策略指纹', value: executionGuardMatrixReport.value.permissionPolicyFingerprint, desc: '新增锁定指纹' },
  { title: '确认契约指纹', value: executionGuardMatrixReport.value.confirmationContractFingerprint, desc: '新增锁定指纹' },
  { title: '沙箱策略指纹', value: executionGuardMatrixReport.value.sandboxPolicyFingerprint, desc: '新增锁定指纹' },
  { title: '整体结果', value: precheckResultLabel(executionGuardMatrixReport.value.overallStatus), desc: '执行防护矩阵' },
])

const simulationResultStorageCards = computed(() => [
  { title: '结果存储命名空间', value: simulationResultStoragePreview.value.resultStorageNamespace, desc: '只定义，不创建' },
  { title: '审计存储命名空间', value: simulationResultStoragePreview.value.auditStorageNamespace, desc: '只定义，不创建' },
  { title: '结果命名空间独立', value: simulationResultStoragePreview.value.independentResultNamespace ? yes() : no(), desc: '不得共用正式业务命名空间' },
  { title: '审计命名空间独立', value: simulationResultStoragePreview.value.independentAuditNamespace ? yes() : no(), desc: '不得共用正式业务命名空间' },
  { title: '共用正式业务命名空间', value: simulationResultStoragePreview.value.sharesFormalBusinessNamespace ? yes() : no(), desc: '必须为否' },
  { title: '共用正式业务集合', value: simulationResultStoragePreview.value[PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_ISOLATION_KEYS.businessCollectionFlag] ? yes() : no(), desc: '必须为否' },
  { title: '使用 localStorage', value: simulationResultStoragePreview.value[PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_ISOLATION_KEYS.browserStorageFlag] ? yes() : no(), desc: '必须为否' },
  { title: '影响正式业务对象', value: simulationResultStoragePreview.value.formalBusinessObjectAffected ? yes() : no(), desc: '必须为否' },
])

const simulationResultFieldRows = computed(() => PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_FIELDS.map((field) => ({
  field: field.field,
  chineseName: field.chineseName,
  type: field.type,
  requiredForStoredRecordText: field.requiredForStoredRecord ? yes() : no(),
  immutableText: field.immutableAfterValidation ? yes() : no(),
  fingerprintText: field.includedInRecordFingerprint ? yes() : no(),
  defaultValueText: formatDisplayValue(field.defaultValue),
})))

const simulationResultLineFieldRows = computed(() => PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LINE_FIELDS.map((field) => ({
  field: field.field,
  chineseName: field.chineseName,
  type: field.type,
  fingerprintText: field.includedInRecordFingerprint ? yes() : no(),
  businessMeaning: field.businessMeaning,
})))

const simulationResultFingerprintCards = computed(() => [
  { title: '结果契约指纹', value: PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_CONTRACT_FINGERPRINT, desc: '锁定 60+18 字段' },
  { title: '结果契约锁定指纹', value: PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_CONTRACT_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_CONTRACT_VERSION], desc: simulationResultContractValidation.value.resultContractFingerprintMatched ? '匹配' : '不匹配' },
  { title: '生命周期策略指纹', value: PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LIFECYCLE_POLICY_FINGERPRINT, desc: '状态和转换表' },
  { title: '生命周期锁定指纹', value: PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LIFECYCLE_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LIFECYCLE_VERSION], desc: simulationLifecycleSummary.value.lifecyclePolicyFingerprintMatched ? '匹配' : '不匹配' },
  { title: '审计契约指纹', value: PAYMENT_VOUCHER_PREPARE_SIMULATION_AUDIT_CONTRACT_FINGERPRINT, desc: '24 字段和追加式规则' },
  { title: '审计契约锁定指纹', value: PAYMENT_VOUCHER_PREPARE_SIMULATION_AUDIT_CONTRACT_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PREPARE_SIMULATION_AUDIT_CONTRACT_VERSION], desc: simulationAuditContractValidation.value.auditContractFingerprintMatched ? '匹配' : '不匹配' },
  { title: '当前载荷指纹', value: simulationResultPreview.value.resultPayloadFingerprint || '未生成', desc: '当前无模拟计算结果' },
  { title: '当前记录指纹', value: simulationResultPreview.value.resultRecordFingerprint || '未生成', desc: '当前不创建结果记录' },
])

const simulationLifecycleCards = computed(() => [
  { title: '生命周期状态数量', value: simulationLifecycleSummary.value.lifecycleStatusCount, desc: '固定状态枚举' },
  { title: '有效性状态数量', value: simulationLifecycleSummary.value.validityStatusCount, desc: '固定状态枚举' },
  { title: '合法转换数量', value: simulationLifecycleSummary.value.legalTransitionCount, desc: '固定转换表' },
  { title: '归档是否终态', value: simulationLifecycleSummary.value.archivedTerminal ? yes() : no(), desc: 'archived 不允许返回' },
  { title: '合成转换预览是否执行', value: simulationLifecycleTransitionPreview.value.transitionEvaluated ? yes() : no(), desc: '仅用于策略验证' },
  { title: '合成转换是否允许', value: simulationLifecycleTransitionPreview.value.transitionAllowed ? yes() : no(), desc: simulationLifecycleTransitionPreview.value.transitionReasonText },
  { title: '当前路由转换预览是否执行', value: currentRouteLifecycleDecision.value.currentRouteLifecycleTransitionPreviewExecuted ? yes() : no(), desc: currentRouteLifecycleDecision.value.currentRouteInvalidationReason },
  { title: '当前路由转换是否允许', value: currentRouteLifecycleDecision.value.currentRouteLifecycleTransitionAllowed ? yes() : no(), desc: '当前无真实模拟结果' },
  { title: '是否实际执行转换', value: simulationLifecycleTransitionPreview.value.businessTransitionExecuted ? yes() : no(), desc: '必须为否' },
  { title: '是否修改现有记录', value: simulationLifecycleTransitionPreview.value.modifiesExistingRecord ? yes() : no(), desc: '必须为否' },
])

const lifecycleTransitionRows = computed(() => [
  ['not_created', 'created'],
  ['created', 'calculated'],
  ['calculated', 'validated'],
  ['validated', 'frozen'],
  ['frozen', 'archived'],
  ['archived', 'created'],
  ['invalidated', 'validated'],
  ['superseded', 'validated'],
  ['frozen', 'calculated'],
  ['validated', 'created'],
].map(([from, to]) => {
  const result = evaluatePaymentVoucherPrepareSimulationResultLifecycleTransition({ currentStatus: from, requestedStatus: to })
  return {
    from,
    to,
    allowedText: result.transitionAllowed ? yes() : no(),
    reason: result.transitionReasonText,
    executedText: result.businessTransitionExecuted ? yes() : no(),
  }
}))

const simulationInvalidationCards = computed(() => [
  { title: '合成失效预览是否评估', value: simulationInvalidationPreview.value.resultInvalidationPreviewEvaluated ? yes() : no(), desc: '合成场景规则' },
  { title: '合成场景是否建议失效', value: simulationInvalidationPreview.value.shouldInvalidateResultPreview ? yes() : no(), desc: simulationInvalidationPreview.value.invalidationTriggers.map((item) => item.trigger).join('、') || '无变化' },
  { title: '推荐有效性状态', value: simulationInvalidationPreview.value.recommendedValidityStatus, desc: 'stale 或 invalid' },
  { title: '当前路由是否执行失效判断', value: currentRouteLifecycleDecision.value.currentRouteInvalidationPreviewEvaluated ? yes() : no(), desc: currentRouteLifecycleDecision.value.currentRouteInvalidationReason },
  { title: '当前路由是否建议失效', value: currentRouteLifecycleDecision.value.currentRouteShouldInvalidateResultPreview ? yes() : no(), desc: '当前无真实模拟结果' },
  { title: '当前是否实际失效', value: simulationInvalidationPreview.value.actualResultInvalidated ? yes() : no(), desc: '必须为否' },
  { title: '替代预览是否评估', value: simulationSupersedePreview.value.supersedePreviewEvaluated ? yes() : no(), desc: '合成场景规则' },
  { title: '是否建议替代', value: simulationSupersedePreview.value.shouldSupersedePreview ? yes() : no(), desc: '只读建议' },
  { title: '是否实际替代', value: simulationSupersedePreview.value.actualResultSuperseded ? yes() : no(), desc: '必须为否' },
  { title: '是否归档真实结果', value: no(), desc: '本轮不归档真实结果' },
])

const simulationAuditCards = computed(() => [
  { title: '审计契约版本', value: PAYMENT_VOUCHER_PREPARE_SIMULATION_AUDIT_CONTRACT_VERSION, desc: '固定版本' },
  { title: '审计字段数', value: simulationAuditContractValidation.value.auditFieldCount, desc: '必须为 24' },
  { title: '审计契约指纹匹配', value: simulationAuditContractValidation.value.auditContractFingerprintMatched ? yes() : no(), desc: PAYMENT_VOUCHER_PREPARE_SIMULATION_AUDIT_CONTRACT_FINGERPRINT },
  { title: '当前是否创建审计事件', value: no(), desc: '必须为否' },
  { title: '当前真实审计事件数', value: 0, desc: '当前业务无事件' },
  { title: '当前审计链状态', value: auditChainStatusLabel(simulationAuditChainStatus.value), desc: '正常无事件，UNKNOWN 来源不存在' },
  { title: '追加式策略是否就绪', value: simulationAuditTrailSummary.value.appendOnlyPolicyReadyPreview ? yes() : no(), desc: '只读规则' },
  { title: '正式审计存储是否落地', value: simulationAuditTrailSummary.value.businessSimulationAuditStorageReady ? yes() : no(), desc: '本轮保持否' },
])

const auditChainScenarioRows = computed(() => simulationResultMatrixReport.value.scenarioResults
  .filter((item) => item.category === '审计事件')
  .map((item) => ({
    caseId: item.caseId,
    name: item.name,
    passedText: item.passed ? '通过' : '失败',
    assertionCount: item.assertionCount,
  })))

const simulationResultMatrixCards = computed(() => [
  { title: '矩阵版本', value: simulationResultMatrixReport.value.matrixVersion, desc: 'V1.13.67' },
  { title: '执行模式', value: simulationResultMatrixReport.value.executionMode, desc: '纯函数只读' },
  { title: '整体结果', value: precheckResultLabel(simulationResultMatrixReport.value.overallStatus), desc: '必须通过' },
  { title: '测试用例数', value: simulationResultMatrixReport.value.testCaseCount, desc: '不少于 84' },
  { title: '通过用例数', value: simulationResultMatrixReport.value.passedCaseCount, desc: '只读测试' },
  { title: '失败用例数', value: simulationResultMatrixReport.value.failedCaseCount, desc: '必须为 0' },
  { title: '断言数', value: simulationResultMatrixReport.value.assertionCount, desc: '模拟结果断言' },
  { title: '失败断言数', value: simulationResultMatrixReport.value.failedAssertionCount, desc: '必须为 0' },
  { title: '结果契约指纹匹配', value: simulationResultMatrixReport.value.resultContractFingerprintMatched ? yes() : no(), desc: simulationResultMatrixReport.value.resultContractFingerprint },
  { title: '生命周期指纹匹配', value: simulationResultMatrixReport.value.lifecyclePolicyFingerprintMatched ? yes() : no(), desc: simulationResultMatrixReport.value.lifecyclePolicyFingerprint },
  { title: '审计契约指纹匹配', value: simulationResultMatrixReport.value.auditContractFingerprintMatched ? yes() : no(), desc: simulationResultMatrixReport.value.auditContractFingerprint },
])

const simulationResultIsolationItems = computed(() => [
  '模拟结果记录契约和明细契约仅为内存预览，不创建真实结果记录。',
  '结果存储命名空间与付款凭证准备、付款凭证、正式付款凭证、总账、核销和银行流水命名空间隔离。',
  '当前不存在模拟执行请求，也不存在模拟计算结果，因此不生成结果编号、不生成当前结果记录指纹。',
  '生命周期转换仅做合法性判断，businessTransitionExecuted 和 modifiesExistingRecord 均保持 false。',
  '来源变化、规则变化、模板变化和业务状态变化只返回失效建议，不实际失效、替代或归档结果。',
  '审计事件契约和指纹链只在测试矩阵中使用合成事件验证，当前真实审计事件数量为 0。',
  'simulationResultStorageReady 与 simulationLogStorageReady 继续保持 false。',
  '状态机不启动，不进入 precheck_pending，不进入 prechecking，不执行模拟计算。',
  '正式业务写入、回滚、补偿和需要清理的真实业务对象数量均为 0。',
])

const simulationLifecycleMatrixPassed = computed(() => simulationResultMatrixReport.value.scenarioResults
  .filter((item) => item.category === '生命周期合法转换')
  .every((item) => item.passed))
const simulationInvalidTransitionBlocked = computed(() => simulationResultMatrixReport.value.scenarioResults
  .filter((item) => item.category === '生命周期非法转换')
  .every((item) => item.passed))
const simulationInvalidationScenarioPassed = computed(() => simulationResultMatrixReport.value.scenarioResults
  .filter((item) => item.category === '结果失效')
  .every((item) => item.passed))
const simulationAuditAppendRulePassed = computed(() => simulationResultMatrixReport.value.scenarioResults
  .filter((item) => item.category === '审计事件' && ['T076', 'T077', 'T078', 'T079'].includes(item.caseId))
  .every((item) => item.passed))
const simulationAuditChainRulePassed = computed(() => simulationResultMatrixReport.value.scenarioResults
  .filter((item) => item.category === '审计事件' && ['T075', 'T080', 'T081'].includes(item.caseId))
  .every((item) => item.passed))

const requestControlAcceptanceCards = computed(() => [
  { title: '归档页面版本', value: 'V1.13.66', desc: '历史验收版本' },
  { title: '请求输入包适配器版本', value: PAYMENT_VOUCHER_PREPARE_REQUEST_ADAPTER_VERSION, desc: '只读适配' },
  { title: '请求输入包契约版本', value: PAYMENT_VOUCHER_PREPARE_REQUEST_PACKAGE_CONTRACT_VERSION, desc: '固定 48 字段' },
  { title: '幂等策略版本', value: PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_VERSION, desc: '只读策略' },
  { title: '并发控制策略版本', value: PAYMENT_VOUCHER_PREPARE_CONCURRENCY_VERSION, desc: '只读策略' },
  { title: '请求输入包字段数', value: requestPackagePreview.value.requestPackageFieldCount, desc: '固定为 48' },
  { title: '请求输入包契约指纹匹配', value: requestPackageContractValidation.value.requestPackageContractFingerprintMatched ? yes() : no(), desc: PAYMENT_VOUCHER_PREPARE_REQUEST_PACKAGE_CONTRACT_FINGERPRINT },
  { title: '幂等策略指纹匹配', value: PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_POLICY_FINGERPRINT === PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_POLICY_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_VERSION] ? yes() : no(), desc: PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_POLICY_FINGERPRINT },
  { title: '并发策略指纹匹配', value: PAYMENT_VOUCHER_PREPARE_CONCURRENCY_POLICY_FINGERPRINT === PAYMENT_VOUCHER_PREPARE_CONCURRENCY_POLICY_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PREPARE_CONCURRENCY_VERSION] ? yes() : no(), desc: PAYMENT_VOUCHER_PREPARE_CONCURRENCY_POLICY_FINGERPRINT },
  { title: '当前来源是否存在', value: requestPackagePreview.value.sourceFound ? yes() : no(), desc: 'UNKNOWN-PEP 为否' },
  { title: '请求输入包预览是否创建', value: requestPackagePreview.value.requestPackagePreviewCreated ? yes() : no(), desc: '不保存输入包' },
  { title: '请求输入包状态', value: requestPackageStatusLabel(requestPackagePreview.value.requestPackageStatus), desc: '正常 PEP 为部分完整' },
  { title: '请求输入包指纹预览是否生成', value: requestPackagePreview.value.requestPackageFingerprintPreviewGenerated ? yes() : no(), desc: '不保存指纹' },
  { title: '缺失业务必填字段数量', value: requestPackagePreview.value.sourceFound ? requestPackagePreview.value.missingBusinessRequiredFieldCount : '来源不存在', desc: '正常 PEP 应大于 0' },
  { title: '正式请求输入包机制是否就绪', value: requestPackagePreview.value.businessRequestPackageReady ? yes() : no(), desc: '本轮保持否' },
  { title: '幂等素材预览是否生成', value: idempotencyKeyPreview.value.idempotencyMaterialPreviewGenerated ? yes() : no(), desc: '仅内存素材' },
  { title: '幂等键预览是否生成', value: idempotencyKeyPreview.value.idempotencyKeyPreviewGenerated ? yes() : no(), desc: '当前字段不完整时为否' },
  { title: '幂等键状态', value: idempotencyStatusLabel(idempotencyKeyPreview.value.idempotencyKeyStatus), desc: '正常 PEP 为字段不完整' },
  { title: '幂等注册表是否可用', value: idempotencyResolutionPreview.value.registryAvailable ? yes() : no(), desc: '未接入正式注册表' },
  { title: '是否允许创建新请求', value: idempotencyResolutionPreview.value.shouldCreateNewRequestPreview ? yes() : no(), desc: '当前不得允许' },
  { title: '是否复用已有请求', value: idempotencyResolutionPreview.value.shouldReuseExistingRequestPreview ? yes() : no(), desc: '当前不得复用' },
  { title: '正式幂等机制是否就绪', value: idempotencyResolutionPreview.value.businessIdempotencyMechanismReady ? yes() : no(), desc: '本轮保持否' },
  { title: '并发判断预览是否执行', value: concurrencyPreview.value.concurrencyPreviewEvaluated ? yes() : no(), desc: 'UNKNOWN-PEP 为否或来源不存在' },
  { title: '锁范围键预览是否生成', value: concurrencyPreview.value.lockScopeKeyPreviewGenerated ? yes() : no(), desc: '当前字段不完整时为否' },
  { title: '并发运行时状态是否可用', value: concurrencyPreview.value.runtimeStateAvailable ? yes() : no(), desc: '未接入正式运行时' },
  { title: '当前并发判断状态', value: concurrencyStatusLabel(concurrencyPreview.value.concurrencyStatus), desc: '正常 PEP 为字段不完整' },
  { title: '当前是否允许获取锁', value: concurrencyPreview.value.canAcquireLockPreview ? yes() : no(), desc: '当前不得允许' },
  { title: '当前是否实际获取锁', value: concurrencyPreview.value.actualLockAcquired ? yes() : no(), desc: '永远为否' },
  { title: '正式并发控制机制是否就绪', value: concurrencyPreview.value.businessConcurrencyMechanismReady ? yes() : no(), desc: '本轮保持否' },
  { title: 'uniquenessRuleReady', value: String(normalizedPurePrecheckInput.value.uniquenessRuleReady), desc: '保持 false' },
  { title: 'idempotencyRuleReady', value: String(normalizedPurePrecheckInput.value.idempotencyRuleReady), desc: '保持 false' },
  { title: 'concurrencyControlReady', value: String(normalizedPurePrecheckInput.value.concurrencyControlReady), desc: '保持 false' },
  { title: '当前预检查通过项数量', value: purePrecheckResult.value.passedCount, desc: '直接读取 purePrecheckResult' },
  { title: '当前预检查阻断项数量', value: purePrecheckResult.value.blockedCount, desc: '直接读取 purePrecheckResult' },
  { title: '当前预检查警告项数量', value: purePrecheckResult.value.warningCount, desc: '直接读取 purePrecheckResult' },
  { title: '当前预检查不适用项数量', value: purePrecheckResult.value.notApplicableCount, desc: '直接读取 purePrecheckResult' },
  { title: '当前业务预检查决策', value: precheckResultLabel(purePrecheckResult.value.decision), desc: '仍为阻断' },
  { title: '当前是否允许继续模拟', value: purePrecheckResult.value.canProceed ? yes() : no(), desc: '仍为否' },
  { title: '当前执行状态', value: notCreated, desc: '状态机未创建' },
  { title: '状态机是否启动', value: no(), desc: '未启动' },
  { title: '正式业务写入数量', value: 0, desc: '零写入' },
  { title: '既有规则集指纹保持', value: governanceSummary.value.ruleSetFingerprintMatched ? yes() : no(), desc: governanceSummary.value.ruleSetFingerprint },
  { title: '既有输入契约指纹保持', value: governanceSummary.value.inputContractFingerprintMatched ? yes() : no(), desc: governanceSummary.value.inputContractFingerprint },
  { title: '既有回归基线指纹保持', value: governanceSummary.value.baselineFingerprintMatched ? yes() : no(), desc: governanceSummary.value.baselineFingerprint },
  { title: '来源快照契约指纹保持', value: sourceSnapshotContractValidation.value.snapshotContractFingerprintMatched ? yes() : no(), desc: PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_CONTRACT_FINGERPRINT },
  { title: '原预检查测试矩阵', value: precheckResultLabel(precheckMatrixReport.value.overallStatus), desc: `${precheckMatrixReport.value.testCaseCount} 个用例` },
  { title: '原来源快照测试矩阵', value: precheckResultLabel(sourceSnapshotMatrixReport.value.overallStatus), desc: `${sourceSnapshotMatrixReport.value.testCaseCount} 个用例` },
  { title: '请求控制测试矩阵', value: precheckResultLabel(requestControlMatrixReport.value.overallStatus), desc: `${requestControlMatrixReport.value.testCaseCount} 个用例` },
])

const requestPackageRunCards = computed(() => [
  { title: '请求适配器版本', value: requestPackagePreview.value.requestAdapterVersion, desc: '只读适配器' },
  { title: '请求输入包契约版本', value: requestPackagePreview.value.requestPackageContractVersion, desc: '固定契约' },
  { title: '来源是否存在', value: requestPackagePreview.value.sourceFound ? yes() : no(), desc: 'UNKNOWN-PEP 为否' },
  { title: '预览是否评估', value: requestPackagePreview.value.requestPackagePreviewEvaluated ? yes() : no(), desc: '纯函数评估' },
  { title: '预览是否创建', value: requestPackagePreview.value.requestPackagePreviewCreated ? yes() : no(), desc: '不保存对象' },
  { title: '输入包状态', value: requestPackageStatusLabel(requestPackagePreview.value.requestPackageStatus), desc: '安全状态优先' },
  { title: '已有字段数量', value: requestPackagePreview.value.presentFieldCount, desc: '只读统计' },
  { title: '缺失字段数量', value: requestPackagePreview.value.missingFieldCount, desc: '只读统计' },
  { title: '业务必填字段数量', value: requestPackagePreview.value.businessRequiredFieldCount, desc: '契约定义' },
  { title: '缺失业务必填字段数量', value: requestPackagePreview.value.missingBusinessRequiredFieldCount, desc: '不自动补齐' },
  { title: '运行时字段数量', value: requestPackagePreview.value.runtimeFieldCount, desc: '传输请求号、请求时间、请求人' },
  { title: '缺失运行时字段数量', value: requestPackagePreview.value.missingRuntimeFieldCount, desc: '本轮必须缺失' },
  { title: '未知输入字段数量', value: requestPackagePreview.value.unknownInputFieldCount, desc: '不进入契约' },
  { title: '正式请求输入包机制', value: requestPackagePreview.value.businessRequestPackageReady ? yes() : no(), desc: '保持否' },
])

const requestPackageFieldRows = computed(() => PAYMENT_VOUCHER_PREPARE_REQUEST_PACKAGE_FIELDS.map((field) => {
  const requestPackage = requestPackagePreview.value.requestPackage || {}
  const value = requestPackage[field.field]
  const present = requestPackagePreview.value.sourceFound && value !== null && value !== 'unknown' && typeof value !== 'undefined' && (field.type !== 'boolean' || value === true)
  return {
    field: field.field,
    chineseName: field.chineseName,
    type: field.type,
    requiredForBusinessReadyText: field.requiredForBusinessReady ? yes() : no(),
    packageFingerprintText: field.includedInPackageFingerprint ? yes() : no(),
    idempotencyText: field.includedInIdempotencyMaterial ? yes() : no(),
    lockScopeText: field.includedInLockScope ? yes() : no(),
    presentText: present ? yes() : no(),
    valueText: requestPackagePreview.value.sourceFound ? formatDisplayValue(value) : '来源不存在',
  }
}))

const requestPackageFingerprintCards = computed(() => [
  { title: '契约指纹', value: PAYMENT_VOUCHER_PREPARE_REQUEST_PACKAGE_CONTRACT_FINGERPRINT, desc: '不是加密签名' },
  { title: '契约锁定指纹', value: PAYMENT_VOUCHER_PREPARE_REQUEST_PACKAGE_CONTRACT_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PREPARE_REQUEST_PACKAGE_CONTRACT_VERSION], desc: requestPackageContractValidation.value.requestPackageContractFingerprintMatched ? '匹配' : '不匹配' },
  { title: '字段名唯一', value: requestPackageContractValidation.value.requestPackageFieldNamesUnique ? yes() : no(), desc: '48 字段唯一' },
  { title: '字段顺序稳定', value: requestPackageContractValidation.value.requestPackageFieldOrderStable ? yes() : no(), desc: '顺序纳入契约' },
  { title: '输入包指纹预览', value: requestPackagePreview.value.requestPackageFingerprintPreviewGenerated ? yes() : no(), desc: '来源不存在时为否' },
  { title: '输入包指纹', value: requestPackagePreview.value.requestPackageFingerprint || '-', desc: '不保存' },
  { title: '传输请求号', value: requestPackagePreview.value.requestPackage?.transportRequestId || '-', desc: '保持 null' },
  { title: '请求时间', value: requestPackagePreview.value.requestPackage?.requestedAt || '-', desc: '保持 null' },
  { title: '请求人', value: requestPackagePreview.value.requestPackage?.requesterId || '-', desc: '保持 null' },
])

const idempotencyCards = computed(() => [
  { title: '幂等策略版本', value: PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_VERSION, desc: '只读策略' },
  { title: '幂等策略指纹', value: PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_POLICY_FINGERPRINT, desc: '策略锁定' },
  { title: '幂等策略锁定值', value: PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_POLICY_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_VERSION], desc: PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_POLICY_FINGERPRINT === PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_POLICY_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_VERSION] ? '匹配' : '不匹配' },
  { title: '幂等素材预览是否生成', value: idempotencyKeyPreview.value.idempotencyMaterialPreviewGenerated ? yes() : no(), desc: '不保存素材' },
  { title: '幂等键预览是否生成', value: idempotencyKeyPreview.value.idempotencyKeyPreviewGenerated ? yes() : no(), desc: '字段完整才生成' },
  { title: '幂等键状态', value: idempotencyStatusLabel(idempotencyKeyPreview.value.idempotencyKeyStatus), desc: '正常 PEP 为字段不完整' },
  { title: '幂等键', value: idempotencyKeyPreview.value.idempotencyKey || '-', desc: '不保存' },
  { title: '幂等必填字段数量', value: idempotencyKeyPreview.value.requiredFieldCount, desc: '固定顺序' },
  { title: '幂等缺失字段数量', value: idempotencyKeyPreview.value.missingRequiredFieldCount, desc: '当前大于 0' },
  { title: '注册表是否可用', value: idempotencyResolutionPreview.value.registryAvailable ? yes() : no(), desc: '当前未接入' },
  { title: '幂等解析状态', value: idempotencyResolutionLabel(idempotencyResolutionPreview.value.idempotencyResolutionStatus), desc: '不得显示可创建新请求' },
  { title: '允许创建新请求', value: idempotencyResolutionPreview.value.shouldCreateNewRequestPreview ? yes() : no(), desc: '当前为否' },
  { title: '复用已有请求', value: idempotencyResolutionPreview.value.shouldReuseExistingRequestPreview ? yes() : no(), desc: '当前为否' },
])

const idempotencyScenarioRows = computed(() => requestControlMatrixReport.value.scenarioResults
  .filter((item) => item.category === '幂等注册表解析')
  .map((item) => ({
    caseId: item.caseId,
    name: item.name,
    passedText: item.passed ? '通过' : '失败',
    assertionCount: item.assertionCount,
  })))

const concurrencyLockCards = computed(() => [
  { title: '并发策略版本', value: PAYMENT_VOUCHER_PREPARE_CONCURRENCY_VERSION, desc: '只读策略' },
  { title: '并发策略指纹', value: PAYMENT_VOUCHER_PREPARE_CONCURRENCY_POLICY_FINGERPRINT, desc: '策略锁定' },
  { title: '并发策略锁定值', value: PAYMENT_VOUCHER_PREPARE_CONCURRENCY_POLICY_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PREPARE_CONCURRENCY_VERSION], desc: PAYMENT_VOUCHER_PREPARE_CONCURRENCY_POLICY_FINGERPRINT === PAYMENT_VOUCHER_PREPARE_CONCURRENCY_POLICY_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PREPARE_CONCURRENCY_VERSION] ? '匹配' : '不匹配' },
  { title: '锁范围素材预览是否生成', value: concurrencyPreview.value.lockScopeMaterialPreviewGenerated ? yes() : no(), desc: '来源存在才生成' },
  { title: '锁范围键预览是否生成', value: concurrencyPreview.value.lockScopeKeyPreviewGenerated ? yes() : no(), desc: '字段完整才生成' },
  { title: '锁范围键', value: concurrencyPreview.value.lockScopeKey || '-', desc: '不保存' },
  { title: '并发运行时状态是否可用', value: concurrencyPreview.value.runtimeStateAvailable ? yes() : no(), desc: '当前未接入' },
  { title: '当前并发状态', value: concurrencyStatusLabel(concurrencyPreview.value.concurrencyStatus), desc: '安全状态优先' },
  { title: '活跃请求数量', value: concurrencyPreview.value.activeRequestCount, desc: '只读输入' },
  { title: '活跃锁数量', value: concurrencyPreview.value.activeLockCount, desc: '只读输入' },
  { title: '过期锁数量', value: concurrencyPreview.value.expiredLockCount, desc: '不读取当前时间' },
  { title: '允许获取锁', value: concurrencyPreview.value.canAcquireLockPreview ? yes() : no(), desc: '当前为否' },
  { title: '实际获取锁', value: concurrencyPreview.value.actualLockAcquired ? yes() : no(), desc: '永远为否' },
  { title: '锁范围字段缺失数', value: lockScopePreview.value.missingRequiredFieldCount, desc: '当前大于 0' },
])

const concurrencyScenarioRows = computed(() => requestControlMatrixReport.value.scenarioResults
  .filter((item) => item.category === '并发控制')
  .map((item) => ({
    caseId: item.caseId,
    name: item.name,
    passedText: item.passed ? '通过' : '失败',
    assertionCount: item.assertionCount,
  })))

const requestControlMatrixCards = computed(() => [
  { title: '矩阵版本', value: requestControlMatrixReport.value.matrixVersion, desc: 'V1.13.66' },
  { title: '执行模式', value: requestControlMatrixReport.value.executionMode, desc: '纯函数只读' },
  { title: '整体结果', value: precheckResultLabel(requestControlMatrixReport.value.overallStatus), desc: '全部通过才可归档' },
  { title: '测试用例数', value: requestControlMatrixReport.value.testCaseCount, desc: '不少于 64' },
  { title: '通过用例数', value: requestControlMatrixReport.value.passedCaseCount, desc: '只读测试' },
  { title: '失败用例数', value: requestControlMatrixReport.value.failedCaseCount, desc: '必须为 0' },
  { title: '断言数', value: requestControlMatrixReport.value.assertionCount, desc: '请求控制断言' },
  { title: '失败断言数', value: requestControlMatrixReport.value.failedAssertionCount, desc: '必须为 0' },
  { title: '请求契约指纹匹配', value: requestControlMatrixReport.value.requestPackageContractFingerprintMatched ? yes() : no(), desc: requestControlMatrixReport.value.requestPackageContractFingerprint },
  { title: '幂等策略指纹匹配', value: requestControlMatrixReport.value.idempotencyPolicyFingerprintMatched ? yes() : no(), desc: requestControlMatrixReport.value.idempotencyPolicyFingerprint },
  { title: '并发策略指纹匹配', value: requestControlMatrixReport.value.concurrencyPolicyFingerprintMatched ? yes() : no(), desc: requestControlMatrixReport.value.concurrencyPolicyFingerprint },
])

const requestControlIsolationItems = computed(() => [
  '请求输入包仅为内存预览，不保存请求输入包。',
  '本轮不生成 transportRequestId，不生成 requestAttemptId。',
  '业务幂等键当前因正式字段不完整，不生成可保存键。',
  '正式幂等注册表不存在，本轮不创建、不查询真实持久化记录。',
  '并发锁范围键当前因法人和账套等字段不完整，不生成可保存键。',
  '正式并发运行时状态不存在，本轮不获取、不释放真实锁。',
  '当前仍不允许创建新模拟请求，不允许启动状态机。',
  'uniquenessRuleReady、idempotencyRuleReady、concurrencyControlReady 继续保持 false。',
  '正式业务写入、回滚、补偿数量均为 0。',
])

const sourceSnapshotAcceptanceCards = computed(() => [
  { title: '归档页面版本', value: 'V1.13.65.1', desc: '历史验收版本' },
  { title: '快照适配器版本', value: PAYMENT_VOUCHER_PREPARE_SOURCE_ADAPTER_VERSION, desc: '独立适配器' },
  { title: '快照契约版本', value: PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_CONTRACT_VERSION, desc: '独立快照契约' },
  { title: '来源数据指纹版本', value: PAYMENT_VOUCHER_PREPARE_SOURCE_FINGERPRINT_VERSION, desc: '只读指纹预览' },
  { title: '来源变更检测器版本', value: PAYMENT_VOUCHER_PREPARE_SOURCE_CHANGE_DETECTOR_VERSION, desc: '只读变化检测' },
  { title: '当前来源是否存在', value: sourceSnapshotPreview.value.sourceFound ? yes() : no(), desc: '按当前路由匹配' },
  { title: '来源快照预览是否创建', value: sourceSnapshotPreview.value.snapshotPreviewCreated ? yes() : no(), desc: '仅内存预览' },
  { title: '来源快照结构状态', value: snapshotStructureLabel(sourceSnapshotPreview.value.snapshotStructureStatus), desc: '不代表正式快照已保存' },
  { title: '快照字段数量', value: sourceSnapshotPreview.value.snapshotFieldCount, desc: '固定 40 字段' },
  { title: '缺失关键字段数量', value: sourceSnapshotPreview.value.sourceFound ? sourceSnapshotPreview.value.missingCriticalFieldCount : '来源不存在', desc: '正常 PEP 应大于 0' },
  { title: '正式来源快照机制是否落地', value: no(), desc: '本轮仅预览' },
  { title: '数据指纹预览是否生成', value: sourceFingerprintPreview.value.fingerprintPreviewGenerated ? yes() : no(), desc: '不保存指纹' },
  { title: '数据指纹状态', value: fingerprintStatusLabel(sourceFingerprintPreview.value.fingerprintStatus), desc: '指纹不是加密签名' },
  { title: '相同输入产生相同指纹', value: sourceFingerprintPreview.value.sameInputSameFingerprint ? yes() : no(), desc: '确定性检查' },
  { title: '对象字段顺序是否影响指纹', value: sourceFingerprintPreview.value.objectKeyOrderIndependent ? no() : yes(), desc: '应为否' },
  { title: '页面版本是否影响指纹', value: sourceFingerprintPreview.value.nonBusinessFieldsExcluded ? no() : yes(), desc: '展示字段被排除' },
  { title: '正式来源指纹机制是否落地', value: no(), desc: '本轮仅预览' },
  { title: '当前是否有参考快照', value: sourceChangePreview.value.referenceSnapshotAvailable ? yes() : no(), desc: '当前页面不自动创建' },
  { title: '来源变更检测预览是否执行', value: sourceChangePreview.value.changeDetectionPreviewExecuted ? yes() : no(), desc: '仅纯函数比较' },
  { title: '当前来源变更状态', value: changeStatusLabel(sourceChangePreview.value.changeStatus), desc: '无参考快照不得确认未变化' },
  { title: '当前来源是否未变化', value: sourceChangePreview.value.businessSourceUnchanged ? yes() : '未确认', desc: '无正式参考快照' },
  { title: '当前是否实际作废模拟结果', value: no(), desc: '只给未来失效建议' },
  { title: '正式来源变更检测机制是否落地', value: no(), desc: '未保存检测结果' },
  { title: 'sourceSnapshotReady', value: String(normalizedPurePrecheckInput.value.sourceSnapshotReady), desc: '保持 false' },
  { title: 'sourceFingerprintReady', value: String(normalizedPurePrecheckInput.value.sourceFingerprintReady), desc: '保持 false' },
  { title: 'sourceUnchanged', value: String(normalizedPurePrecheckInput.value.sourceUnchanged), desc: '保持 false' },
  { title: '当前业务预检查决策', value: precheckResultLabel(purePrecheckResult.value.decision), desc: '仍为阻断' },
  { title: '当前是否允许继续模拟', value: purePrecheckResult.value.canProceed ? yes() : no(), desc: '阻断项不减少' },
  { title: '当前执行状态', value: notCreated, desc: '状态机未创建' },
  { title: '状态机是否启动', value: no(), desc: '未启动' },
  { title: '正式业务写入数量', value: 0, desc: '零写入' },
  { title: '当前预检查通过项数量', value: purePrecheckResult.value.passedCount, desc: '直接读取 purePrecheckResult.passedCount' },
  { title: '当前预检查阻断项数量', value: purePrecheckResult.value.blockedCount, desc: '直接读取 purePrecheckResult.blockedCount' },
  { title: '当前预检查警告项数量', value: purePrecheckResult.value.warningCount, desc: '直接读取 purePrecheckResult.warningCount' },
  { title: '当前预检查不适用项数量', value: purePrecheckResult.value.notApplicableCount, desc: '直接读取 purePrecheckResult.notApplicableCount' },
  { title: '既有规则集指纹是否保持', value: governanceSummary.value.ruleSetFingerprintMatched ? yes() : no(), desc: governanceSummary.value.ruleSetFingerprint },
  { title: '既有输入契约指纹是否保持', value: governanceSummary.value.inputContractFingerprintMatched ? yes() : no(), desc: governanceSummary.value.inputContractFingerprint },
  { title: '既有回归基线指纹是否保持', value: governanceSummary.value.baselineFingerprintMatched ? yes() : no(), desc: governanceSummary.value.baselineFingerprint },
  { title: '来源快照测试矩阵状态', value: precheckResultLabel(sourceSnapshotMatrixReport.value.overallStatus), desc: `${sourceSnapshotMatrixReport.value.testCaseCount} 个用例` },
])

const sourceSnapshotRunCards = computed(() => [
  { title: '来源适配器版本', value: PAYMENT_VOUCHER_PREPARE_SOURCE_ADAPTER_VERSION, desc: '普通对象到快照输入' },
  { title: '快照契约版本', value: sourceSnapshotPreview.value.snapshotContractVersion, desc: '独立于预检查输入契约' },
  { title: '快照契约指纹', value: PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_CONTRACT_FINGERPRINT, desc: '来源快照契约锁定' },
  { title: '快照契约锁定值', value: PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_CONTRACT_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_CONTRACT_VERSION], desc: sourceSnapshotContractValidation.value.snapshotContractFingerprintMatched ? '匹配' : '不匹配' },
  { title: '来源是否存在', value: sourceSnapshotPreview.value.sourceFound ? yes() : no(), desc: 'UNKNOWN-PEP 为否' },
  { title: '快照预览创建', value: sourceSnapshotPreview.value.snapshotPreviewCreated ? yes() : no(), desc: '不保存快照' },
  { title: '快照结构状态', value: snapshotStructureLabel(sourceSnapshotPreview.value.snapshotStructureStatus), desc: 'partial 不等于可放行' },
  { title: '已有字段数', value: sourceSnapshotPreview.value.presentFieldCount, desc: '只读统计' },
  { title: '缺失字段数', value: sourceSnapshotPreview.value.missingFieldCount, desc: '只读统计' },
  { title: '关键字段数', value: sourceSnapshotPreview.value.criticalFieldCount, desc: '关键变化会建议失效' },
  { title: '缺失关键字段数', value: sourceSnapshotPreview.value.missingCriticalFieldCount, desc: '当前演示 PEP 应大于 0' },
  { title: '正式快照机制', value: no(), desc: 'businessSnapshotMechanismReady=false' },
])

const sourceSnapshotFieldRows = computed(() => PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_FIELDS.map((field) => {
  const snapshot = sourceSnapshotPreview.value.snapshot || {}
  const value = snapshot[field.field]
  const present = sourceSnapshotPreview.value.sourceFound && value !== null && value !== 'unknown' && typeof value !== 'undefined'
  return {
    field: field.field,
    chineseName: field.chineseName,
    criticalText: field.critical ? yes() : no(),
    fingerprintText: field.includedInFingerprint ? yes() : no(),
    presentText: present ? yes() : no(),
    valueText: sourceSnapshotPreview.value.sourceFound ? formatDisplayValue(value) : '来源不存在',
  }
}))

const sourceFingerprintCards = computed(() => [
  { title: '指纹版本', value: sourceFingerprintPreview.value.fingerprintVersion, desc: '独立来源数据指纹版本' },
  { title: '快照契约版本', value: sourceFingerprintPreview.value.snapshotContractVersion, desc: '指纹绑定快照契约' },
  { title: '来源是否存在', value: sourceFingerprintPreview.value.sourceFound ? yes() : no(), desc: 'UNKNOWN-PEP 为否' },
  { title: '指纹预览是否生成', value: sourceFingerprintPreview.value.fingerprintPreviewGenerated ? yes() : no(), desc: '不保存指纹' },
  { title: '指纹状态', value: fingerprintStatusLabel(sourceFingerprintPreview.value.fingerprintStatus), desc: 'partial_preview 不等于可放行' },
  { title: '来源数据指纹', value: sourceFingerprintPreview.value.sourceDataFingerprint || '-', desc: '稳定识别码，不是签名' },
  { title: '规范字段数', value: sourceFingerprintPreview.value.canonicalFieldCount, desc: '固定顺序' },
  { title: '缺失关键字段数', value: sourceFingerprintPreview.value.missingCriticalFieldCount, desc: '来自快照完整性' },
  { title: '相同输入相同指纹', value: sourceFingerprintPreview.value.sameInputSameFingerprint ? yes() : no(), desc: '确定性' },
  { title: '对象顺序影响指纹', value: sourceFingerprintPreview.value.objectKeyOrderIndependent ? no() : yes(), desc: '应为否' },
  { title: '非业务字段影响指纹', value: sourceFingerprintPreview.value.nonBusinessFieldsExcluded ? no() : yes(), desc: '页面版本和路由被排除' },
  { title: '正式指纹机制', value: no(), desc: 'businessFingerprintMechanismReady=false' },
])

const sourceChangeCards = computed(() => [
  { title: '变更检测器版本', value: sourceChangePreview.value.changeDetectorVersion, desc: '独立变更检测版本' },
  { title: '参考快照是否存在', value: sourceChangePreview.value.referenceSnapshotAvailable ? yes() : no(), desc: '当前不自动创建参考快照' },
  { title: '当前快照是否存在', value: sourceChangePreview.value.currentSnapshotAvailable ? yes() : no(), desc: '取决于当前来源' },
  { title: '变更检测预览执行', value: sourceChangePreview.value.changeDetectionPreviewExecuted ? yes() : no(), desc: '来源不存在时不执行' },
  { title: '变更状态', value: changeStatusLabel(sourceChangePreview.value.changeStatus), desc: '正常 PEP 为无参考快照' },
  { title: '参考指纹', value: sourceChangePreview.value.referenceFingerprint || '-', desc: '本轮不保存参考' },
  { title: '当前指纹', value: sourceChangePreview.value.currentFingerprint || '-', desc: '当前只读预览' },
  { title: '指纹是否匹配', value: sourceChangePreview.value.fingerprintMatched ? yes() : no(), desc: '无参考时为否' },
  { title: '变化字段数', value: sourceChangePreview.value.changedFieldCount, desc: '当前无参考时为 0' },
  { title: '关键变化字段数', value: sourceChangePreview.value.criticalChangedFieldCount, desc: '关键变化会建议失效' },
  { title: '当前来源是否未变化', value: sourceChangePreview.value.businessSourceUnchanged ? yes() : '未确认', desc: '无参考快照不能确认' },
  { title: '实际作废模拟结果', value: no(), desc: '本轮只显示建议' },
])

const sourceChangedFieldRows = computed(() => (sourceChangePreview.value.changedFields || []).map((item) => ({
  ...item,
  previousValue: formatDisplayValue(item.previousValue),
  currentValue: formatDisplayValue(item.currentValue),
  criticalText: item.critical ? yes() : no(),
  invalidatesText: item.invalidatesSimulationResult ? yes() : no(),
})))

const sourceSnapshotMatrixCards = computed(() => [
  { title: '测试矩阵版本', value: sourceSnapshotMatrixReport.value.matrixVersion, desc: 'V1.13.65' },
  { title: '执行方式', value: sourceSnapshotMatrixReport.value.executionMode, desc: '只读纯函数' },
  { title: '整体状态', value: precheckResultLabel(sourceSnapshotMatrixReport.value.overallStatus), desc: '必须通过' },
  { title: '测试用例数', value: sourceSnapshotMatrixReport.value.testCaseCount, desc: '不少于 48' },
  { title: '通过用例数', value: sourceSnapshotMatrixReport.value.passedCaseCount, desc: '自动断言' },
  { title: '失败用例数', value: sourceSnapshotMatrixReport.value.failedCaseCount, desc: '必须为 0' },
  { title: '断言总数', value: sourceSnapshotMatrixReport.value.assertionCount, desc: '快照/指纹/变更检测' },
  { title: '失败断言数', value: sourceSnapshotMatrixReport.value.failedAssertionCount, desc: '必须为 0' },
  { title: '快照字段数', value: sourceSnapshotMatrixReport.value.snapshotFieldCount, desc: '固定 40' },
  { title: '快照字段名唯一', value: sourceSnapshotMatrixReport.value.snapshotFieldNamesUnique ? yes() : no(), desc: '必须为是' },
  { title: '快照字段顺序稳定', value: sourceSnapshotMatrixReport.value.snapshotFieldOrderStable ? yes() : no(), desc: '必须为是' },
  { title: '快照契约指纹匹配', value: sourceSnapshotMatrixReport.value.snapshotContractFingerprintMatched ? yes() : no(), desc: sourceSnapshotMatrixReport.value.snapshotContractFingerprint },
])

const sourceSnapshotIsolationItems = computed(() => [
  '来源快照预览对象不是正式业务快照。',
  '数据指纹预览不是正式保存的业务指纹。',
  '无历史参考快照时，不能认定来源未变化。',
  '相同测试快照比较结果为 unchanged，不代表当前真实来源 unchanged。',
  '变化检测结果不会自动修改任何业务对象。',
  '本轮不会实际作废模拟结果。',
  '本轮不会修改付款执行准备。',
  `sourceSnapshotReady 仍为 ${String(normalizedPurePrecheckInput.value.sourceSnapshotReady)}。`,
  `sourceFingerprintReady 仍为 ${String(normalizedPurePrecheckInput.value.sourceFingerprintReady)}。`,
  `sourceUnchanged 仍为 ${String(normalizedPurePrecheckInput.value.sourceUnchanged)}。`,
  `当前业务仍为 ${purePrecheckResult.value.decision}。`,
  `状态机仍为 ${notCreated}。`,
])

const matrixSummaryCards = computed(() => [
  { title: '测试矩阵版本', value: precheckMatrixReport.value.matrixVersion, desc: '固定输入测试矩阵' },
  { title: '预检查引擎版本', value: precheckMatrixReport.value.engineVersion, desc: '生产纯函数引擎' },
  { title: '规则集版本', value: precheckMatrixReport.value.ruleSetVersion, desc: '规则版本固化' },
  { title: '输入契约版本', value: precheckMatrixReport.value.inputContractVersion, desc: '输入字段契约固化' },
  { title: '回归基线版本', value: precheckMatrixReport.value.regressionBaselineVersion, desc: '基线口径固化' },
  { title: '执行方式', value: precheckMatrixReport.value.executionMode, desc: '只读合成输入' },
  { title: '测试矩阵是否已执行', value: yes(), desc: '页面加载时只读计算' },
  { title: '测试矩阵整体状态', value: precheckResultLabel(precheckMatrixReport.value.overallStatus), desc: '矩阵自身结果' },
  { title: '测试用例总数', value: precheckMatrixReport.value.testCaseCount, desc: '不少于 60 个' },
  { title: '通过用例数', value: precheckMatrixReport.value.passedCaseCount, desc: '通过矩阵断言' },
  { title: '失败用例数', value: precheckMatrixReport.value.failedCaseCount, desc: '失败如实显示' },
  { title: '跳过用例数', value: precheckMatrixReport.value.skippedCaseCount, desc: '不得跳过失败项' },
  { title: '断言总数', value: precheckMatrixReport.value.assertionCount, desc: '自动断言数量' },
  { title: '通过断言数', value: precheckMatrixReport.value.passedAssertionCount, desc: '自动判定' },
  { title: '失败断言数', value: precheckMatrixReport.value.failedAssertionCount, desc: '失败不隐藏' },
  { title: '当前路由预检查决策', value: precheckResultLabel(purePrecheckResult.value.decision), desc: '当前业务独立决策' },
  { title: '当前是否允许继续模拟', value: purePrecheckResult.value.canProceed ? yes() : no(), desc: '不随矩阵通过而改变' },
  { title: '当前执行状态', value: notCreated, desc: '状态机未创建' },
  { title: '状态机是否启动', value: no(), desc: '未启动' },
  { title: '正式业务写入数', value: 0, desc: '零写入' },
])

const governanceAcceptanceCards = computed(() => [
  { title: '页面版本', value: version, desc: '页面展示版本' },
  { title: '引擎版本', value: PAYMENT_VOUCHER_PRECHECK_ENGINE_VERSION, desc: '保持 V1.13.62' },
  { title: '规则集版本', value: governanceSummary.value.ruleSetVersion, desc: '独立规则版本' },
  { title: '输入契约版本', value: governanceSummary.value.inputContractVersion, desc: '独立契约版本' },
  { title: '回归基线版本', value: governanceSummary.value.baselineVersion, desc: '独立基线版本' },
  { title: '规则数量', value: governanceSummary.value.ruleCount, desc: '必须为 32' },
  { title: '规则编码唯一', value: governanceSummary.value.ruleCodesUnique ? yes() : no(), desc: 'ruleCode 不重复' },
  { title: '规则顺序稳定', value: governanceSummary.value.ruleSequenceStable ? yes() : no(), desc: 'sequence 1 到 32' },
  { title: '规则集指纹匹配', value: governanceSummary.value.ruleSetFingerprintMatched ? yes() : no(), desc: governanceSummary.value.ruleSetFingerprint },
  { title: '规则逻辑本轮改变', value: governanceSummary.value.ruleLogicChangedThisRound ? yes() : no(), desc: '本轮不改变规则逻辑' },
  { title: '规则版本需要提升', value: governanceSummary.value.ruleSetVersionUpgradeRequired ? yes() : no(), desc: '指纹匹配则不需要' },
  { title: '输入字段数量', value: governanceSummary.value.inputContractFieldCount, desc: '必须为 47' },
  { title: '输入字段名称唯一', value: governanceSummary.value.inputFieldNamesUnique ? yes() : no(), desc: '字段名不重复' },
  { title: '输入类型定义有效', value: governanceSummary.value.inputTypesValid ? yes() : no(), desc: 'string / number / boolean' },
  { title: '输入枚举定义有效', value: governanceSummary.value.inputEnumsValid ? yes() : no(), desc: '枚举值稳定' },
  { title: '输入契约指纹匹配', value: governanceSummary.value.inputContractFingerprintMatched ? yes() : no(), desc: governanceSummary.value.inputContractFingerprint },
  { title: '固定基线数', value: governanceSummary.value.baselineCount, desc: '四个固定基线' },
  { title: '通过基线数', value: governanceSummary.value.passedBaselineCount, desc: '必须为 4' },
  { title: '失败基线数', value: governanceSummary.value.failedBaselineCount, desc: '必须为 0' },
  { title: '规则向量长度', value: governanceSummary.value.ruleVectorLength, desc: '每个基线 32 项' },
  { title: '规则向量一致', value: governanceSummary.value.ruleVectorsMatched ? yes() : no(), desc: '逐条结果一致' },
  { title: '阻断规则集合一致', value: governanceSummary.value.blockRuleCodesMatched ? yes() : no(), desc: 'blocked 集合一致' },
  { title: '不适用规则集合一致', value: governanceSummary.value.notApplicableRuleCodesMatched ? yes() : no(), desc: 'not_applicable 集合一致' },
  { title: '规则顺序变化', value: governanceSummary.value.ruleOrderChanged ? yes() : no(), desc: '必须为否' },
  { title: '回归基线指纹匹配', value: governanceSummary.value.baselineFingerprintMatched ? yes() : no(), desc: governanceSummary.value.baselineFingerprint },
  { title: '版本治理整体状态', value: precheckResultLabel(governanceSummary.value.overallStatus), desc: '三类治理均通过' },
  { title: '当前业务预检查决策', value: precheckResultLabel(purePrecheckResult.value.decision), desc: '当前 PEP 仍阻断' },
  { title: '当前是否允许继续模拟', value: purePrecheckResult.value.canProceed ? yes() : no(), desc: '必须为否' },
  { title: '当前执行状态', value: notCreated, desc: '状态机未创建' },
  { title: '状态机是否启动', value: no(), desc: '未启动' },
  { title: '正式业务写入数量', value: 0, desc: '零写入' },
])

const ruleGovernanceCards = computed(() => [
  { title: '规则集版本', value: governanceSummary.value.ruleSetVersion, desc: '独立于页面版本' },
  { title: '规则集指纹', value: governanceSummary.value.ruleSetFingerprint, desc: '当前实际指纹' },
  { title: '规则集锁定指纹', value: governanceSummary.value.ruleSetLockedFingerprint, desc: '锁定表值' },
  { title: '规则集指纹匹配', value: governanceSummary.value.ruleSetFingerprintMatched ? yes() : no(), desc: '必须为是' },
  { title: '规则数量', value: governanceSummary.value.ruleCount, desc: '32' },
  { title: '规则顺序稳定', value: governanceSummary.value.ruleSequenceStable ? yes() : no(), desc: 'sequence 连续' },
])

const inputGovernanceCards = computed(() => [
  { title: '输入契约版本', value: governanceSummary.value.inputContractVersion, desc: '独立于页面版本' },
  { title: '输入契约指纹', value: governanceSummary.value.inputContractFingerprint, desc: '当前实际指纹' },
  { title: '输入契约锁定指纹', value: governanceSummary.value.inputContractLockedFingerprint, desc: '锁定表值' },
  { title: '输入契约指纹匹配', value: governanceSummary.value.inputContractFingerprintMatched ? yes() : no(), desc: '必须为是' },
  { title: '输入字段数', value: governanceSummary.value.inputContractFieldCount, desc: '47' },
  { title: '契约校验状态', value: precheckResultLabel(governanceSummary.value.inputContractValidationStatus), desc: '不执行业务放行' },
])

const baselineGovernanceCards = computed(() => [
  { title: '回归基线版本', value: governanceSummary.value.baselineVersion, desc: '独立于页面版本' },
  { title: '回归基线指纹', value: governanceSummary.value.baselineFingerprint, desc: '当前实际指纹' },
  { title: '回归基线锁定指纹', value: governanceSummary.value.baselineLockedFingerprint, desc: '锁定表值' },
  { title: '回归基线指纹匹配', value: governanceSummary.value.baselineFingerprintMatched ? yes() : no(), desc: '必须为是' },
  { title: '基线数量', value: governanceSummary.value.baselineCount, desc: '4' },
  { title: '基线整体状态', value: precheckResultLabel(governanceSummary.value.baselineOverallStatus), desc: '必须通过' },
])

const governanceBaselineRows = computed(() => governanceSummary.value.baselineResults.map((item) => ({
  ...item,
  expectedDecision: precheckResultLabel(item.expectedDecision),
  actualDecision: precheckResultLabel(item.actualDecision),
  actualCountsText: `通过${item.actualCounts.passedCount} / 阻断${item.actualCounts.blockedCount} / 警告${item.actualCounts.warningCount} / 不适用${item.actualCounts.notApplicableCount}`,
  ruleVectorMatchedText: item.ruleVectorMatched ? yes() : no(),
  blockRuleCodesMatchedText: item.blockRuleCodesMatched ? yes() : no(),
  notApplicableRuleCodesMatchedText: item.notApplicableRuleCodesMatched ? yes() : no(),
  passedText: item.passed ? '通过' : '失败',
})))

const versionContractCards = computed(() => [
  { title: '规则集版本', value: PAYMENT_VOUCHER_PRECHECK_RULESET_VERSION, desc: '规则行为版本标识' },
  { title: '输入契约版本', value: PAYMENT_VOUCHER_PRECHECK_INPUT_CONTRACT_VERSION, desc: '输入字段和规范化口径' },
  { title: '回归基线版本', value: PAYMENT_VOUCHER_PRECHECK_BASELINE_VERSION, desc: '固定样本预期结果' },
  { title: '规则总数', value: PAYMENT_VOUCHER_PRECHECK_RULESET_MANIFEST.ruleCount, desc: '必须保持 32 条' },
  { title: '输入字段数', value: PAYMENT_VOUCHER_PRECHECK_INPUT_FIELDS.length, desc: '标准输入契约字段' },
  { title: '规则是否写业务数据', value: PAYMENT_VOUCHER_PRECHECK_RULESET_MANIFEST.ruleWriteBusinessData ? yes() : no(), desc: '保持否' },
])

const inputContractRows = computed(() => PAYMENT_VOUCHER_PRECHECK_INPUT_FIELDS.map((item) => ({
  field: item.field,
  valueType: `${item.type}${item.nullable ? '|null' : ''}`,
  defaultValue: formatDisplayValue(item.defaultValue),
  normalization: item.allowedValues ? `枚举：${item.allowedValues.join('/')}` : '基础类型规范化',
  description: item.businessMeaning,
})))

const regressionBaselineRows = computed(() => {
  return PAYMENT_VOUCHER_PRECHECK_BASELINES.map((baseline) => baselineRow(baseline.name, {
    decision: baseline.expectedDecision,
    canProceed: baseline.expectedCanProceed,
    counts: baseline.expectedCounts,
  }, `${baseline.expectedRuleVector.length} 项规则向量`))
})

const governanceConclusionItems = computed(() => [
  '规则集指纹与锁定值一致。',
  '输入契约指纹与锁定值一致。',
  '回归基线指纹与锁定值一致。',
  '规则逻辑本轮未改变。',
  '规则版本无需提升。',
  '页面版本变化未改变业务规则版本。',
  '当前真实 PEP 仍为阻断。',
  '状态机仍未启动。',
  '正式业务写入数量为0。',
])

const matrixCategoryRows = computed(() => Object.values(precheckMatrixReport.value.categorySummary).map((item) => ({
  ...item,
  coverageStatusText: precheckResultLabel(item.coverageStatus),
})))

const matrixScenarioRows = computed(() => precheckMatrixReport.value.scenarioResults.map((item) => ({
  ...item,
  expectedDecisionText: precheckResultLabel(item.expectedDecision),
  actualDecisionText: precheckResultLabel(item.actualDecision),
  expectedCanProceedText: item.expectedCanProceed ? yes() : no(),
  actualCanProceedText: item.actualCanProceed ? yes() : no(),
  passedText: item.passed ? '通过' : '失败',
  businessDataWrittenText: item.businessDataWritten ? yes() : no(),
})))

const matrixFailureRows = computed(() => precheckMatrixReport.value.failedAssertions.map((item) => ({
  ...item,
  expected: formatDisplayValue(item.expected),
  actual: formatDisplayValue(item.actual),
  ruleCode: item.ruleCode || '-',
})))

const matrixInvariantRows = computed(() => precheckMatrixReport.value.invariantResults.map((item) => ({
  ...item,
  passedText: item.passed ? '通过' : '失败',
  expected: formatDisplayValue(item.expected),
  actual: formatDisplayValue(item.actual),
})))

const summaryCards = computed(() => [
  { title: '付款执行准备单号', value: paymentExecutionPrepareNoText.value, desc: paymentExecutionPrepareFound.value ? '只读来源已匹配' : '未匹配，不自动创建', acceptanceId: 'route-payment-execution-prepare-no' },
  { title: '状态机运行状态', value: '未创建，仅设计', desc: '不启动状态机', acceptanceId: 'state-machine-start-allowed' },
  { title: '当前执行状态', value: 'not_created', desc: '不进入 precheck_pending', acceptanceId: 'current-execution-state' },
  { title: '结果有效性状态', value: 'not_created', desc: '本轮不创建模拟结果' },
  { title: '付款执行金额', value: formatAmount(amountValue.value), desc: '只读展示，不写业务数据' },
])

const stateModelSplitItems = [
  { field: 'simulationExecutionState', name: '模拟执行生命周期状态', meaning: '描述执行到了哪一步。', currentValue: 'not_created', writeThisRound: no() },
  { field: 'simulationResultValidityState', name: '模拟结果有效性状态', meaning: '描述结果当前是否可用。', currentValue: 'not_created', writeThisRound: no() },
  { field: 'simulationFailureState', name: '模拟失败信息', meaning: '描述在哪个阶段因何失败，不作为正常生命周期状态使用。', currentValue: '未产生', writeThisRound: no() },
]

const executionStateItems = [
  executionState('not_created', '未创建', '尚未创建模拟执行请求，未来允许通过 REQUEST_SIMULATION 进入 precheck_pending。', no(), no(), no(), no()),
  executionState('precheck_pending', '等待预检查', '模拟请求已被接收，尚未开始预检查。', no(), no(), no(), yes()),
  executionState('prechecking', '预检查中', '正在检查来源、金额、状态、权限、期间和唯一性等条件。', no(), no(), no(), no()),
  executionState('blocked', '预检查阻断', '预检查被阻断，没有临时上下文和并发锁时可以直接结束；未来重新模拟必须创建新的执行请求。', yes(), yes(), yes(), no()),
  executionState('ready', '等待模拟执行', '预检查通过，但尚未取得执行权。', no(), no(), no(), yes()),
  executionState('lock_waiting', '等待并发锁', '正在等待幂等和并发控制。', no(), no(), no(), yes()),
  executionState('executing', '模拟计算中', '仅在未来独立模拟上下文中计算预计分录和判断结果。', no(), no(), no(), no()),
  executionState('result_validating', '模拟结果校验中', '检查预计借贷平衡、数据完整性、阻断和警告。', no(), no(), no(), no()),
  executionState('completed', '模拟完成', '模拟计算和结果校验完成。', yes(), yes(), no(), no()),
  executionState('failed', '模拟失败', '模拟执行已经失败，但未来仍需进入 cleanup_pending 和 cleaned。', yes(), no(), yes(), no()),
  executionState('timed_out', '模拟超时', '原执行已经终止，但仍需清理临时上下文和释放锁。', yes(), no(), yes(), no()),
  executionState('cancelled', '模拟已取消', '模拟执行已取消，但仍需完成清理流程。', yes(), no(), yes(), no()),
  executionState('cleanup_pending', '等待清理', '业务执行已经终止，但清理工作尚未完成。', yes(), no(), no(), no()),
  executionState('cleaned', '清理完成', '临时上下文已清理，并发锁已释放，不再允许继续转换。', yes(), yes(), no(), no()),
]

const resultValidityStateItems = [
  resultState('not_created', '结果未创建', '本轮不创建结果，因此当前只显示结果未创建。', yes()),
  resultState('valid', '当前有效', '未来已完成结果校验且仍可引用。', no()),
  resultState('warning', '有效但存在警告', '未来结果可引用，但需提示警告项。', no()),
  resultState('invalid', '已失效', '曾经形成结果，但之后因来源变化或规则变化失效。', no()),
  resultState('superseded', '已被新版本替代', '新的模拟结果已替代旧版本。', no()),
  resultState('frozen', '已被后续正式生成动作引用并冻结', '不表示已经过账或写总账。', no()),
  resultState('cancelled', '已人工作废', '未来由授权人员作废模拟结果。', no()),
]

const transitionEventItems = [
  transitionEvent('REQUEST_SIMULATION', '请求模拟', 'not_created', 'precheck_pending', '来源存在、权限可见、入口开放'),
  transitionEvent('START_PRECHECK', '开始预检查', 'precheck_pending', 'prechecking', '已创建模拟请求'),
  transitionEvent('PRECHECK_PASSED', '预检查通过', 'prechecking', 'ready', '所有放行条件满足'),
  transitionEvent('PRECHECK_BLOCKED', '预检查阻断', 'prechecking', 'blocked', '命中绝对阻断条件'),
  transitionEvent('WAIT_FOR_LOCK', '等待并发锁', 'ready', 'lock_waiting', '幂等键和锁规则可用'),
  transitionEvent('LOCK_ACQUIRED', '已取得并发锁', 'lock_waiting', 'executing', '锁获取成功'),
  transitionEvent('LOCK_REJECTED', '并发锁获取失败', 'lock_waiting', 'failed', '锁冲突或幂等冲突'),
  transitionEvent('START_EXECUTION', '开始模拟计算', 'executing', 'executing', '冻结快照可用'),
  transitionEvent('EXECUTION_SUCCEEDED', '模拟计算成功', 'executing', 'result_validating', '预计分录已形成'),
  transitionEvent('START_RESULT_VALIDATION', '开始结果校验', 'result_validating', 'result_validating', '预计分录可校验'),
  transitionEvent('RESULT_VALIDATION_PASSED', '结果校验通过', 'result_validating', 'completed', '借贷平衡且无阻断'),
  transitionEvent('RESULT_VALIDATION_FAILED', '结果校验失败', 'result_validating', 'failed', '校验命中错误'),
  transitionEvent('EXECUTION_FAILED', '模拟执行失败', 'prechecking / lock_waiting / executing / result_validating', 'failed', '执行期间不可继续'),
  transitionEvent('EXECUTION_TIMEOUT', '模拟执行超时', 'lock_waiting / executing / result_validating', 'timed_out', '超过最长执行时间'),
  transitionEvent('CANCEL_EXECUTION', '取消模拟执行', 'precheck_pending / ready / lock_waiting', 'cancelled', '处于允许取消阶段'),
  transitionEvent('START_CLEANUP', '开始清理', 'failed / timed_out / cancelled', 'cleanup_pending', '存在临时上下文或锁'),
  transitionEvent('CLEANUP_SUCCEEDED', '清理完成', 'cleanup_pending', 'cleaned', '临时上下文清理完成'),
  transitionEvent('CLEANUP_FAILED', '清理失败', 'cleanup_pending', 'cleanup_pending', '只产生清理警告，不写业务数据'),
]

const allowedTransitionItems = [
  allowedTransition('not_created', 'precheck_pending', 'REQUEST_SIMULATION', '创建新的模拟请求后才可进入预检查等待。'),
  allowedTransition('precheck_pending', 'prechecking', 'START_PRECHECK', '预检查只能从等待预检查开始。'),
  allowedTransition('prechecking', 'blocked', 'PRECHECK_BLOCKED', '命中阻断时进入 blocked。'),
  allowedTransition('prechecking', 'ready', 'PRECHECK_PASSED', '预检查通过后等待模拟执行。'),
  allowedTransition('ready', 'lock_waiting', 'WAIT_FOR_LOCK', '执行前必须等待幂等与并发锁。'),
  allowedTransition('lock_waiting', 'executing', 'LOCK_ACQUIRED', '取得锁后才能模拟计算。'),
  allowedTransition('lock_waiting', 'failed', 'LOCK_REJECTED', '锁获取失败进入 failed。'),
  allowedTransition('executing', 'result_validating', 'EXECUTION_SUCCEEDED', '模拟计算成功后进入结果校验。'),
  allowedTransition('result_validating', 'completed', 'RESULT_VALIDATION_PASSED', '结果校验通过后完成。'),
  allowedTransition('result_validating', 'failed', 'RESULT_VALIDATION_FAILED', '结果校验失败进入 failed。'),
  allowedTransition('prechecking / lock_waiting / executing / result_validating', 'failed', 'EXECUTION_FAILED', '执行期间不可继续时失败。'),
  allowedTransition('lock_waiting / executing / result_validating', 'timed_out', 'EXECUTION_TIMEOUT', '超时后不得继续原上下文。'),
  allowedTransition('precheck_pending / ready / lock_waiting', 'cancelled', 'CANCEL_EXECUTION', '只有安全阶段允许取消。'),
  allowedTransition('failed / timed_out / cancelled', 'cleanup_pending', 'START_CLEANUP', '终止后进入清理流程。'),
  allowedTransition('cleanup_pending', 'cleaned', 'CLEANUP_SUCCEEDED', '清理完成后进入 cleaned。'),
]

const illegalTransitionItems = [
  illegalTransition('not_created', 'executing', '跳过预检查、放行和并发控制。'),
  illegalTransition('prechecking', 'completed', '跳过模拟计算和结果校验。'),
  illegalTransition('blocked', 'ready', '阻断原因未解除，不允许直接继续。'),
  illegalTransition('blocked', 'executing', '阻断状态绝对禁止执行。'),
  illegalTransition('ready', 'completed', '未执行模拟计算。'),
  illegalTransition('lock_waiting', 'completed', '未取得执行权。'),
  illegalTransition('failed', 'completed', '失败请求不能伪装为成功。'),
  illegalTransition('timed_out', 'completed', '超时请求不能继续使用原执行上下文。'),
  illegalTransition('cancelled', 'completed', '取消请求不得形成成功结果。'),
  illegalTransition('cleaned', 'executing', '已清理的执行实例不得重新启动。'),
  illegalTransition('completed', 'executing', '完成后的重复模拟必须建立新版本。'),
  illegalTransition('UNKNOWN-PEP', '任意执行状态', '来源付款执行准备不存在。'),
]

const stageInputOutputItems = [
  stageItem('请求接收阶段', '付款执行准备单号、操作人、模拟用途', '未来模拟请求上下文'),
  stageItem('预检查阶段', '付款执行准备只读快照、放行条件规则', '预检查通过、阻断原因和警告项'),
  stageItem('幂等并发阶段', '未来幂等键、来源数据指纹、规则版本', '锁获取结果、重复请求识别结果'),
  stageItem('模拟计算阶段', '冻结的来源快照、科目模板、期间、币种汇率', '预计借方分录、预计贷方分录和预计金额'),
  stageItem('结果校验阶段', '预计分录、阻断规则和警告规则', '借贷平衡结果、完整性结果和有效性建议'),
  stageItem('清理阶段', '临时执行上下文、锁标识和临时缓存', '临时数据清理结果和锁释放结果'),
]

const failureTypeItems = [
  failureType('SOURCE_NOT_FOUND', '付款执行准备或来源链不存在。', '请求接收', yes(), no()),
  failureType('PRECHECK_BLOCKED', '预检查命中绝对阻断条件。', '预检查', yes(), no()),
  failureType('IDEMPOTENCY_CONFLICT', '幂等键命中冲突。', '幂等并发', yes(), no()),
  failureType('LOCK_CONFLICT', '无法取得并发执行权。', '幂等并发', yes(), no()),
  failureType('ACCOUNTING_TEMPLATE_ERROR', '会计科目模板缺失或无效。', '模拟计算', yes(), no()),
  failureType('ACCOUNTING_PERIOD_ERROR', '会计期间不存在、关闭或锁定。', '预检查', yes(), no()),
  failureType('CURRENCY_RATE_ERROR', '币种、汇率或舍入规则异常。', '模拟计算', yes(), no()),
  failureType('SOURCE_CHANGED', '来源数据在模拟期间发生变化。', '结果校验', yes(), yes()),
  failureType('CALCULATION_ERROR', '预计分录计算异常。', '模拟计算', yes(), yes()),
  failureType('RESULT_UNBALANCED', '预计借贷不平衡。', '结果校验', yes(), yes()),
  failureType('RESULT_VALIDATION_ERROR', '模拟结果完整性校验失败。', '结果校验', yes(), yes()),
  failureType('EXECUTION_TIMEOUT', '执行超时。', '超时恢复', yes(), yes()),
  failureType('USER_CANCELLED', '操作人取消。', '取消处理', yes(), yes()),
  failureType('TEMP_CONTEXT_ERROR', '临时执行上下文异常。', '临时上下文', yes(), yes()),
  failureType('SIMULATION_RESULT_WRITE_ERROR', '未来模拟结果独立存储失败。', '结果保存', yes(), yes()),
  failureType('SIMULATION_LOG_ERROR', '未来模拟日志写入失败。', '审计记录', yes(), yes()),
  failureType('CLEANUP_ERROR', '临时数据或并发锁清理失败。', '清理阶段', yes(), yes()),
]

const failureResultFieldItems = [
  failureField('failureId', '失败记录编号', 'string', '-'),
  failureField('executionRequestNo', '执行请求号', 'string', '-'),
  failureField('paymentExecutionPrepareNo', '付款执行准备单号', 'string', paymentExecutionPrepareNoText.value),
  failureField('failureCode', '失败编码', 'string', '-'),
  failureField('failureStage', '失败阶段', 'string', '-'),
  failureField('failureMessage', '失败说明', 'string', '-'),
  failureField('technicalDetail', '技术细节', 'object', '{}'),
  failureField('retryable', '是否可重试', 'boolean', 'false'),
  failureField('cleanupRequired', '是否需要清理', 'boolean', 'false'),
  failureField('cleanupStatus', '清理状态', 'string', 'not_required'),
  failureField('lockReleaseRequired', '是否需要释放锁', 'boolean', 'false'),
  failureField('lockReleaseStatus', '锁释放状态', 'string', 'not_required'),
  failureField('temporaryContextRemoved', '临时上下文是否移除', 'boolean', 'false'),
  failureField('businessDataWritten', '是否写入业务数据', 'boolean', 'false'),
  failureField('formalObjectAffected', '是否影响正式对象', 'boolean', 'false'),
  failureField('paymentExecutionStatusChanged', '付款执行状态是否改变', 'boolean', 'false'),
  failureField('paymentVoucherPrepareCreated', '是否创建付款凭证准备', 'boolean', 'false'),
  failureField('paymentVoucherGenerated', '是否生成付款凭证', 'boolean', 'false'),
  failureField('ledgerWritten', '是否写总账', 'boolean', 'false'),
  failureField('posted', '是否过账', 'boolean', 'false'),
  failureField('writtenOff', '是否核销', 'boolean', 'false'),
  failureField('bankFlowGenerated', '是否生成银行流水', 'boolean', 'false'),
  failureField('failedAt', '失败时间', 'datetime', '-'),
  failureField('failedBy', '操作人', 'string', '-'),
  failureField('correlationId', '关联追踪号', 'string', '-'),
]

const zeroBusinessWriteMetrics = [
  { label: '正式业务写入路径接入数', value: 0 },
  { label: '正式业务写入记录数', value: 0 },
  { label: '正式业务回滚记录数', value: 0 },
  { label: '正式业务补偿操作数', value: 0 },
  { label: '需要清理的真实业务对象数', value: 0 },
]

const zeroBusinessWriteProtectionItems = [
  '模拟执行不得调用正式付款执行写入方法。',
  '模拟执行不得调用付款凭证准备创建方法。',
  '模拟执行不得调用付款凭证生成方法。',
  '模拟执行不得调用正式付款凭证生成方法。',
  '模拟执行不得调用核销写入方法。',
  '模拟执行不得调用总账写入方法。',
  '模拟执行不得调用过账方法。',
  '模拟执行不得调用银行流水生成或导入方法。',
  '模拟执行不得改变来源业务状态。',
  '模拟执行不得改变来源金额。',
  '正式业务 Store 不得参与模拟事务。',
  '模拟临时上下文必须与正式业务对象隔离。',
  '模拟失败时只清理临时上下文。',
  '模拟失败不得依赖对正式业务数据的补偿性回滚。',
  '因为正式业务从未写入，所以正式业务回滚数量应为 0。',
  '模拟日志失败不得触发正式业务写入。',
  '模拟结果保存失败不得留下半成品正式对象。',
  '清理失败只能产生清理警告，不得改变业务单据。',
  '本轮不执行任何写入或回滚。',
  '本轮正式业务写入数量为 0。',
].map((rule) => ({ rule, executeThisRound: no() }))

const temporaryContextItems = [
  tempField('executionRequestNo', '执行请求号'),
  tempField('correlationId', '链路追踪号'),
  tempField('paymentExecutionPrepareNo', '付款执行准备单号'),
  tempField('sourceSnapshot', '来源只读快照'),
  tempField('sourceFingerprint', '来源数据指纹'),
  tempField('ruleVersion', '规则版本'),
  tempField('accountingTemplateVersion', '科目模板版本'),
  tempField('accountingPeriod', '会计期间'),
  tempField('currencySnapshot', '币种汇率快照'),
  tempField('temporaryDebitEntries', '临时借方分录'),
  tempField('temporaryCreditEntries', '临时贷方分录'),
  tempField('temporaryWarnings', '临时警告'),
  tempField('temporaryBlockingReasons', '临时阻断原因'),
  tempField('lockToken', '并发锁标识'),
  tempField('startedAt', '开始时间'),
  tempField('expiresAt', '过期时间'),
]

const cleanupRuleItems = [
  '临时上下文不是正式付款凭证准备对象。',
  '临时分录不是正式会计分录。',
  '临时上下文不得被审核、复核、核销或过账。',
  '模拟完成后按保留规则转化为独立模拟结果或清除。',
  '模拟失败、超时、取消后必须进入清理流程。',
  '清理不得删除正式业务对象。',
  '清理不得修改付款执行准备。',
  '本轮不创建临时上下文。',
  '本轮不执行清理。',
]

const lockAndTimeoutRuleItems = [
  '获取锁成功后必须记录锁标识。',
  '锁必须绑定执行请求号和来源付款执行准备单号。',
  '锁必须有最大有效时间。',
  '完成、失败、超时或取消后必须释放锁。',
  '重复释放应保持幂等。',
  '锁释放失败应进入清理警告。',
  '锁释放失败不得写正式业务数据。',
  '超时执行不得继续生成模拟结果。',
  '超时后的重新模拟必须创建新执行请求。',
  '旧请求必须保留终止原因。',
  '本轮不创建锁。',
  '本轮不获取锁。',
  '本轮不释放锁。',
  '本轮不执行超时恢复。',
].map((rule) => ({ rule, executeThisRound: no() }))

const cancelAndRetryRuleItems = [
  'precheck_pending 可取消。',
  'ready 可取消。',
  'lock_waiting 可取消。',
  'executing 原则上不得由普通用户强制取消，未来只能发出安全中止请求。',
  'result_validating 不得强制跳过校验。',
  'completed 不允许取消，只能对结果执行未来作废规则。',
  'failed 可根据失败类型重新创建请求。',
  'timed_out 必须创建新请求，不得继续旧请求。',
  'blocked 必须先解除阻断原因，再创建新请求。',
  'cleaned 不允许重新启动。',
  '重试不得复用旧锁。',
  '重试不得覆盖旧失败记录。',
  '本轮不执行取消。',
  '本轮不执行重试。',
].map((rule) => ({ rule, executeThisRound: no() }))

const stateAuditFieldItems = [
  auditField('executionRequestNo', '执行请求号'),
  auditField('currentExecutionState', '当前执行状态'),
  auditField('previousExecutionState', '前一执行状态'),
  auditField('transitionEvent', '状态转换事件'),
  auditField('transitionReason', '转换原因'),
  auditField('transitionAt', '转换时间'),
  auditField('transitionBy', '转换操作人'),
  auditField('correlationId', '关联追踪号'),
  auditField('idempotencyKey', '幂等键'),
  auditField('lockToken', '锁标识'),
  auditField('stateVersion', '状态版本'),
  auditField('failureCode', '失败编码'),
  auditField('cleanupStatus', '清理状态'),
  auditField('businessDataWritten', '是否写业务数据'),
  auditField('formalObjectAffected', '是否影响正式对象'),
]

const unmetStateMachineStartConditionItems = [
  'V1.13.60 最终评审仍为不放行。',
  '模拟执行入口尚未开放。',
  '模拟执行权限尚未接入。',
  '模拟结果独立存储尚未建立。',
  '临时执行上下文尚未建立。',
  '幂等键尚未建立。',
  '并发锁尚未建立。',
  '状态持久化尚未建立。',
  '状态版本控制尚未建立。',
  '状态审计日志尚未建立。',
  '来源快照冻结机制尚未建立。',
  '失败结果存储尚未建立。',
  '临时上下文清理器尚未建立。',
  '锁超时释放机制尚未建立。',
  '零写入事务边界尚未落地。',
  '法人、账套、币种、汇率、科目模板和会计期间尚未完整接入。',
  '当前仍为浏览器演示数据环境。',
]

const unifiedProtectionConclusion = [
  { item: '执行纯函数测试矩阵', value: yes() },
  { item: '执行纯函数只读预检查演算', value: yes() },
  { item: '执行来源只读快照预览', value: yes() },
  { item: '执行来源数据指纹预览', value: yes() },
  { item: '执行来源变更检测预览', value: yes() },
  { item: '执行请求输入包预览', value: yes() },
  { item: '执行请求输入包指纹预览', value: yes() },
  { item: '执行幂等素材预览', value: yes() },
  { item: '执行幂等键完整性判断', value: yes() },
  { item: '执行并发控制纯函数判断', value: yes() },
  ...[
  '创建真实模拟请求',
  '生成传输请求号',
  '生成请求尝试号',
  '保存请求输入包',
  '保存幂等键',
  '创建幂等注册记录',
  '查询正式幂等注册表',
  '创建并发锁记录',
  '获取真实并发锁',
  '释放真实并发锁',
  '设置 uniquenessRuleReady 为 true',
  '设置 idempotencyRuleReady 为 true',
  '设置 concurrencyControlReady 为 true',
  '保存正式来源快照',
  '冻结正式来源快照',
  '保存来源数据指纹',
  '创建历史参考快照',
  '确认当前业务来源未变化',
  '实际作废模拟结果',
  '设置 sourceSnapshotReady 为 true',
  '设置 sourceFingerprintReady 为 true',
  '设置 sourceUnchanged 为 true',
  '执行当前路由纯函数预检查演算以外的业务动作',
  '进入 precheck_pending',
  '进入 prechecking',
  '启动模拟状态机',
  '创建模拟执行请求',
  '执行状态转换',
  '触发状态事件',
  '执行状态机预检查',
  '获取并发锁',
  '执行模拟计算',
  '执行结果校验',
  '创建模拟结果',
  '写模拟状态',
  '写模拟状态历史',
  '写模拟失败记录',
  '创建临时上下文',
  '执行临时数据清理',
  '执行锁释放',
  '执行超时恢复',
  '执行取消',
  '执行重试',
  '保存测试结果',
  '写模拟日志',
  '写测试结果到 localStorage',
  '写正式操作日志',
  '写 localStorage',
  '修改业务 Store',
  '创建付款凭证准备对象',
  '生成付款凭证',
  '生成正式付款凭证',
  '提交审核',
  '复核',
  '核销',
  '写总账',
  '过账',
  '执行真实付款',
  '生成银行流水',
  '修改业务状态',
  '修改业务金额',
  '正式业务写入',
  '正式业务回滚',
  '正式业务补偿',
  ].map((item) => ({ item, value: no() })),
]

const protectionFlags = {
  purePrecheckTestMatrixExecuted: true,
  purePrecheckPreviewEvaluated: true,
  sourceSnapshotPreviewEvaluated: true,
  sourceFingerprintPreviewEvaluated: true,
  sourceChangeDetectionPreviewEvaluated: true,
  requestPackagePreviewEvaluated: true,
  requestPackageFingerprintPreviewEvaluated: true,
  idempotencyMaterialPreviewEvaluated: true,
  idempotencyKeyCompletenessEvaluated: true,
  concurrencyPreviewEvaluated: true,
  realSimulationRequestCreated: false,
  transportRequestIdGenerated: false,
  requestAttemptIdGenerated: false,
  requestPackageSaved: false,
  idempotencyKeySaved: false,
  idempotencyRegistryRecordCreated: false,
  formalIdempotencyRegistryQueried: false,
  lockRegistryRecordCreated: false,
  realConcurrencyLockAcquired: false,
  realConcurrencyLockReleased: false,
  uniquenessRuleReadySetTrue: false,
  idempotencyRuleReadySetTrue: false,
  concurrencyControlReadySetTrue: false,
  formalSourceSnapshotSaved: false,
  formalSourceSnapshotFrozen: false,
  sourceDataFingerprintSaved: false,
  historicalReferenceSnapshotCreated: false,
  businessSourceUnchangedConfirmed: false,
  simulationResultInvalidated: false,
  sourceSnapshotReadySetTrue: false,
  sourceFingerprintReadySetTrue: false,
  sourceUnchangedSetTrue: false,
  stateMachinePrecheckExecuted: false,
  stateMachineStartAllowed: false,
  executionRequestCreated: false,
  enterPrecheckPending: false,
  enterPrechecking: false,
  stateTransitionExecuted: false,
  stateEventTriggered: false,
  concurrencyLockAcquired: false,
  simulationCalculationExecuted: false,
  resultValidationExecuted: false,
  simulationResultCreated: false,
  simulationStateWritten: false,
  simulationStateHistoryWritten: false,
  failureRecordWritten: false,
  temporaryContextCreated: false,
  cleanupExecuted: false,
  lockReleased: false,
  timeoutRecoveryExecuted: false,
  cancelExecuted: false,
  retryExecuted: false,
  testResultSaved: false,
  simulationLogWritten: false,
  testResultWrittenToLocalStorage: false,
  formalOperationLogWritten: false,
  writeLocalStorage: false,
  modifyBusinessStore: false,
  paymentVoucherPrepareObjectCreated: false,
  paymentVoucherGenerated: false,
  formalPaymentVoucherGenerated: false,
  submittedForReview: false,
  reviewed: false,
  writeOffPayment: false,
  writeLedger: false,
  postLedger: false,
  executeRealPayment: false,
  generateBankFlow: false,
  modifyBusinessStatus: false,
  modifyBusinessAmount: false,
  businessDataWritten: false,
  businessRollbackExecuted: false,
  businessCompensationExecuted: false,
}

const routeStabilityCheck = computed(() => ({
  routePaymentExecutionPrepareNo: routePaymentExecutionPrepareNoText.value,
  paymentExecutionPrepareFound: paymentExecutionPrepareFound.value,
  stateMachineStartAllowed: false,
  currentExecutionState: notCreated,
  enterPrecheckPending: false,
  concurrencyLockAcquired: false,
  simulationCalculationExecuted: false,
  simulationResultCreated: false,
  temporaryContextCreated: false,
  cleanupExecuted: false,
  writeLocalStorage: false,
  modifyStore: false,
  formalBusinessWritePathCount: 0,
  businessDataWrittenCount: 0,
  businessRollbackCount: 0,
  businessCompensationCount: 0,
  realBusinessObjectCleanupRequiredCount: 0,
  pageCrash: false,
}))

const paymentVoucherPrepareSimulationStateMachineDesignSummary = computed(() => ({
  page: 'PaymentVoucherPreparePreviewPage',
  version,
  routePaymentExecutionPrepareNo: routePaymentExecutionPrepareNoText.value,
  paymentExecutionPrepareFound: paymentExecutionPrepareFound.value,
  stateMachineDesignStatus: '未启动，仅设计',
  stateMachineStartAllowed: false,
  stateTransitionExecuted: false,
  simulationExecutionExecuted: false,
  currentExecutionState: notCreated,
  currentResultValidityState: notCreated,
  executionRequestCreated: false,
  temporaryContextCreated: false,
  concurrencyLockAcquired: false,
  simulationCalculationExecuted: false,
  resultValidationExecuted: false,
  simulationResultCreated: false,
  simulationStateWritten: false,
  failureRecordWritten: false,
  cleanupExecuted: false,
  lockReleased: false,
  businessDataWritten: false,
  businessRollbackExecuted: false,
  businessCompensationExecuted: false,
  formalBusinessWritePathCount: 0,
  businessDataWrittenCount: 0,
  businessRollbackCount: 0,
  businessCompensationCount: 0,
  realBusinessObjectCleanupRequiredCount: 0,
  executionStateItems,
  resultValidityStateItems,
  transitionEventItems,
  allowedTransitionItems,
  illegalTransitionItems,
  stageInputOutputItems,
  failureTypeItems,
  failureResultFieldItems,
  zeroBusinessWriteProtectionItems,
  temporaryContextItems,
  cleanupRuleItems,
  lockAndTimeoutRuleItems,
  cancelAndRetryRuleItems,
  stateAuditFieldItems,
  unmetStateMachineStartConditionItems,
  unifiedProtectionConclusion,
  protectionFlags,
  routeStabilityCheck: routeStabilityCheck.value,
  timestamp: new Date().toISOString(),
}))

const paymentVoucherPreparePurePrecheckEngineDesignSummary = computed(() => ({
  page: 'PaymentVoucherPreparePreviewPage',
  version,
  routePaymentExecutionPrepareNo: routePaymentExecutionPrepareNoText.value,
  paymentExecutionPrepareFound: paymentExecutionPrepareFound.value,
  engineVersion: purePrecheckResult.value.engineVersion,
  engineType: purePrecheckResult.value.engineType,
  purePrecheckPreviewEvaluated: true,
  stateMachinePrecheckExecuted: false,
  stateMachineStartAllowed: false,
  formalBusinessWritePathCount: 0,
  businessDataWrittenCount: 0,
  businessRollbackCount: 0,
  businessCompensationCount: 0,
  realBusinessObjectCleanupRequiredCount: 0,
  stateTransitionExecuted: false,
  simulationExecutionExecuted: false,
  currentExecutionState: notCreated,
  precheckDecision: purePrecheckResult.value.decision,
  precheckCanProceed: purePrecheckResult.value.canProceed,
  totalRuleCount: purePrecheckResult.value.totalRuleCount,
  passedCount: purePrecheckResult.value.passedCount,
  blockedCount: purePrecheckResult.value.blockedCount,
  warningCount: purePrecheckResult.value.warningCount,
  notApplicableCount: purePrecheckResult.value.notApplicableCount,
  normalizedInput: normalizedPurePrecheckInput.value,
  ruleResults: purePrecheckResult.value.ruleResults,
  blockReasons: purePrecheckResult.value.blockReasons,
  warnings: purePrecheckResult.value.warnings,
  puritySelfCheck: {
    ...purePrecheckPurity.value,
    inputMutationDetected: purePrecheckPurity.value.inputMutated,
    sameInputSameOutput: purePrecheckPurity.value.sameInputSameOutput,
  },
  unifiedProtectionConclusion,
  protectionFlags,
  routeStabilityCheck: routeStabilityCheck.value,
  timestamp: new Date().toISOString(),
}))

const paymentVoucherPreparePurePrecheckTestMatrixSummary = computed(() => ({
  page: 'PaymentVoucherPreparePreviewPage',
  version,
  matrixVersion: precheckMatrixReport.value.matrixVersion,
  engineVersion: precheckMatrixReport.value.engineVersion,
  ruleSetVersion: precheckMatrixReport.value.ruleSetVersion,
  inputContractVersion: precheckMatrixReport.value.inputContractVersion,
  regressionBaselineVersion: precheckMatrixReport.value.regressionBaselineVersion,
  executionMode: precheckMatrixReport.value.executionMode,
  matrixExecuted: true,
  matrixOverallStatus: precheckMatrixReport.value.overallStatus,
  testCaseCount: precheckMatrixReport.value.testCaseCount,
  passedCaseCount: precheckMatrixReport.value.passedCaseCount,
  failedCaseCount: precheckMatrixReport.value.failedCaseCount,
  skippedCaseCount: precheckMatrixReport.value.skippedCaseCount,
  assertionCount: precheckMatrixReport.value.assertionCount,
  passedAssertionCount: precheckMatrixReport.value.passedAssertionCount,
  failedAssertionCount: precheckMatrixReport.value.failedAssertionCount,
  categorySummary: precheckMatrixReport.value.categorySummary,
  riskSummary: precheckMatrixReport.value.riskSummary,
  ruleSetManifest: precheckMatrixReport.value.ruleSetManifest,
  inputContractSummary: precheckMatrixReport.value.inputContractSummary,
  regressionBaselines: precheckMatrixReport.value.regressionBaselines,
  scenarioResults: precheckMatrixReport.value.scenarioResults,
  summaryDecisionResults: precheckMatrixReport.value.summaryDecisionResults,
  invariantResults: precheckMatrixReport.value.invariantResults,
  failedCases: precheckMatrixReport.value.failedCases,
  failedAssertions: precheckMatrixReport.value.failedAssertions,
  currentRoutePaymentExecutionPrepareNo: routePaymentExecutionPrepareNoText.value,
  currentRoutePaymentExecutionPrepareFound: paymentExecutionPrepareFound.value,
  currentRoutePrecheckDecision: purePrecheckResult.value.decision,
  currentRoutePrecheckCanProceed: purePrecheckResult.value.canProceed,
  currentExecutionState: notCreated,
  stateMachineStartAllowed: false,
  stateMachinePrecheckExecuted: false,
  executionRequestCreated: false,
  stateTransitionExecuted: false,
  simulationExecutionExecuted: false,
  formalBusinessWritePathCount: 0,
  businessDataWrittenCount: 0,
  businessRollbackCount: 0,
  businessCompensationCount: 0,
  realBusinessObjectCleanupRequiredCount: 0,
  protectionFlags,
  routeStabilityCheck: routeStabilityCheck.value,
  timestamp: new Date().toISOString(),
}))

const paymentVoucherPreparePurePrecheckGovernanceSummary = computed(() => ({
  page: 'PaymentVoucherPreparePreviewPage',
  version,
  engineVersion: PAYMENT_VOUCHER_PRECHECK_ENGINE_VERSION,
  ruleSetVersion: governanceSummary.value.ruleSetVersion,
  ruleSetFingerprint: governanceSummary.value.ruleSetFingerprint,
  ruleSetLockedFingerprint: governanceSummary.value.ruleSetLockedFingerprint,
  ruleSetFingerprintMatched: governanceSummary.value.ruleSetFingerprintMatched,
  ruleCount: governanceSummary.value.ruleCount,
  ruleCodesUnique: governanceSummary.value.ruleCodesUnique,
  ruleSequenceStable: governanceSummary.value.ruleSequenceStable,
  ruleSetValidationStatus: governanceSummary.value.ruleSetValidationStatus,
  ruleLogicChangedThisRound: governanceSummary.value.ruleLogicChangedThisRound,
  ruleSetVersionUpgradeRequired: governanceSummary.value.ruleSetVersionUpgradeRequired,
  inputContractVersion: governanceSummary.value.inputContractVersion,
  inputContractFingerprint: governanceSummary.value.inputContractFingerprint,
  inputContractLockedFingerprint: governanceSummary.value.inputContractLockedFingerprint,
  inputContractFingerprintMatched: governanceSummary.value.inputContractFingerprintMatched,
  inputContractFieldCount: governanceSummary.value.inputContractFieldCount,
  inputFieldNamesUnique: governanceSummary.value.inputFieldNamesUnique,
  inputTypesValid: governanceSummary.value.inputTypesValid,
  inputEnumsValid: governanceSummary.value.inputEnumsValid,
  currentRouteInputContractResult: governanceSummary.value.currentRouteInputContractResult,
  inputContractCompatibilityStatus: governanceSummary.value.inputContractCompatibilityStatus,
  baselineVersion: governanceSummary.value.baselineVersion,
  baselineFingerprint: governanceSummary.value.baselineFingerprint,
  baselineLockedFingerprint: governanceSummary.value.baselineLockedFingerprint,
  baselineFingerprintMatched: governanceSummary.value.baselineFingerprintMatched,
  baselineCount: governanceSummary.value.baselineCount,
  passedBaselineCount: governanceSummary.value.passedBaselineCount,
  failedBaselineCount: governanceSummary.value.failedBaselineCount,
  baselineOverallStatus: governanceSummary.value.baselineOverallStatus,
  baselineResults: governanceSummary.value.baselineResults,
  ruleVectorLength: governanceSummary.value.ruleVectorLength,
  ruleVectorsMatched: governanceSummary.value.ruleVectorsMatched,
  blockRuleCodesMatched: governanceSummary.value.blockRuleCodesMatched,
  notApplicableRuleCodesMatched: governanceSummary.value.notApplicableRuleCodesMatched,
  ruleOrderChanged: governanceSummary.value.ruleOrderChanged,
  changedRules: governanceSummary.value.changedRules,
  missingRules: governanceSummary.value.missingRules,
  extraRules: governanceSummary.value.extraRules,
  testMatrixCaseCount: precheckMatrixReport.value.testCaseCount,
  testMatrixFailedCaseCount: precheckMatrixReport.value.failedCaseCount,
  testMatrixAssertionCount: precheckMatrixReport.value.assertionCount,
  testMatrixFailedAssertionCount: precheckMatrixReport.value.failedAssertionCount,
  currentRoutePrecheckDecision: purePrecheckResult.value.decision,
  currentRoutePrecheckCanProceed: purePrecheckResult.value.canProceed,
  currentExecutionState: notCreated,
  stateMachineStartAllowed: false,
  formalBusinessWritePathCount: 0,
  businessDataWrittenCount: 0,
  businessRollbackCount: 0,
  businessCompensationCount: 0,
  realBusinessObjectCleanupRequiredCount: 0,
  protectionFlags,
  routeStabilityCheck: routeStabilityCheck.value,
  timestamp: new Date().toISOString(),
}))

const paymentVoucherPrepareSourceSnapshotFingerprintChangeSummary = computed(() => ({
  page: 'PaymentVoucherPreparePreviewPage',
  version,
  routePaymentExecutionPrepareNo: routePaymentExecutionPrepareNoText.value,
  paymentExecutionPrepareFound: paymentExecutionPrepareFound.value,
  sourceAdapterVersion: PAYMENT_VOUCHER_PREPARE_SOURCE_ADAPTER_VERSION,
  snapshotContractVersion: PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_CONTRACT_VERSION,
  snapshotContractFingerprint: PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_CONTRACT_FINGERPRINT,
  snapshotContractLockedFingerprint: PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_CONTRACT_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_CONTRACT_VERSION],
  snapshotContractFingerprintMatched: sourceSnapshotContractValidation.value.snapshotContractFingerprintMatched,
  snapshotFieldCount: sourceSnapshotContractValidation.value.snapshotFieldCount,
  snapshotFieldNamesUnique: sourceSnapshotContractValidation.value.snapshotFieldNamesUnique,
  snapshotFieldOrderStable: sourceSnapshotContractValidation.value.snapshotFieldOrderStable,
  snapshotPreviewEvaluated: true,
  snapshotPreviewCreated: sourceSnapshotPreview.value.snapshotPreviewCreated,
  snapshotStructureStatus: sourceSnapshotPreview.value.snapshotStructureStatus,
  presentFieldCount: sourceSnapshotPreview.value.presentFieldCount,
  missingFieldCount: sourceSnapshotPreview.value.missingFieldCount,
  criticalFieldCount: sourceSnapshotPreview.value.criticalFieldCount,
  missingCriticalFieldCount: sourceSnapshotPreview.value.missingCriticalFieldCount,
  missingCriticalFields: sourceSnapshotPreview.value.missingCriticalFields,
  businessSnapshotMechanismReady: sourceSnapshotPreview.value.businessSnapshotMechanismReady,
  sourceFingerprintVersion: PAYMENT_VOUCHER_PREPARE_SOURCE_FINGERPRINT_VERSION,
  fingerprintPreviewGenerated: sourceFingerprintPreview.value.fingerprintPreviewGenerated,
  fingerprintStatus: sourceFingerprintPreview.value.fingerprintStatus,
  sourceDataFingerprint: sourceFingerprintPreview.value.sourceDataFingerprint,
  canonicalFieldCount: sourceFingerprintPreview.value.canonicalFieldCount,
  sameInputSameFingerprint: sourceFingerprintPreview.value.sameInputSameFingerprint,
  objectKeyOrderIndependent: sourceFingerprintPreview.value.objectKeyOrderIndependent,
  nonBusinessFieldsExcluded: sourceFingerprintPreview.value.nonBusinessFieldsExcluded,
  businessFingerprintMechanismReady: sourceFingerprintPreview.value.businessFingerprintMechanismReady,
  changeDetectorVersion: PAYMENT_VOUCHER_PREPARE_SOURCE_CHANGE_DETECTOR_VERSION,
  referenceSnapshotAvailable: sourceChangePreview.value.referenceSnapshotAvailable,
  changeDetectionPreviewExecuted: sourceChangePreview.value.changeDetectionPreviewExecuted,
  changeStatus: sourceChangePreview.value.changeStatus,
  referenceFingerprint: sourceChangePreview.value.referenceFingerprint,
  currentFingerprint: sourceChangePreview.value.currentFingerprint,
  fingerprintMatched: sourceChangePreview.value.fingerprintMatched,
  changedFieldCount: sourceChangePreview.value.changedFieldCount,
  criticalChangedFieldCount: sourceChangePreview.value.criticalChangedFieldCount,
  changedFields: sourceChangePreview.value.changedFields,
  businessSourceUnchanged: sourceChangePreview.value.businessSourceUnchanged,
  shouldInvalidateSimulationResultPreview: sourceChangePreview.value.shouldInvalidateSimulationResultPreview,
  businessChangeDetectionMechanismReady: sourceChangePreview.value.businessChangeDetectionMechanismReady,
  precheckReadinessFlags: {
    sourceSnapshotReady: normalizedPurePrecheckInput.value.sourceSnapshotReady,
    sourceFingerprintReady: normalizedPurePrecheckInput.value.sourceFingerprintReady,
    sourceUnchanged: normalizedPurePrecheckInput.value.sourceUnchanged,
  },
  sourceSnapshotTestMatrixVersion: sourceSnapshotMatrixReport.value.matrixVersion,
  sourceSnapshotTestCaseCount: sourceSnapshotMatrixReport.value.testCaseCount,
  sourceSnapshotFailedCaseCount: sourceSnapshotMatrixReport.value.failedCaseCount,
  sourceSnapshotAssertionCount: sourceSnapshotMatrixReport.value.assertionCount,
  sourceSnapshotFailedAssertionCount: sourceSnapshotMatrixReport.value.failedAssertionCount,
  sourceSnapshotTestOverallStatus: sourceSnapshotMatrixReport.value.overallStatus,
  ruleSetFingerprint: governanceSummary.value.ruleSetFingerprint,
  ruleSetFingerprintMatched: governanceSummary.value.ruleSetFingerprintMatched,
  inputContractFingerprint: governanceSummary.value.inputContractFingerprint,
  inputContractFingerprintMatched: governanceSummary.value.inputContractFingerprintMatched,
  baselineFingerprint: governanceSummary.value.baselineFingerprint,
  baselineFingerprintMatched: governanceSummary.value.baselineFingerprintMatched,
  currentRoutePrecheckDecision: purePrecheckResult.value.decision,
  currentRoutePrecheckCanProceed: purePrecheckResult.value.canProceed,
  currentExecutionState: notCreated,
  stateMachineStartAllowed: false,
  formalBusinessWritePathCount: 0,
  businessDataWrittenCount: 0,
  businessRollbackCount: 0,
  businessCompensationCount: 0,
  realBusinessObjectCleanupRequiredCount: 0,
  protectionFlags,
  routeStabilityCheck: routeStabilityCheck.value,
  timestamp: new Date().toISOString(),
}))

const paymentVoucherPrepareSimulationResultLifecycleAuditSummary = computed(() => ({
  page: 'PaymentVoucherPreparePreviewPage',
  version,
  routePaymentExecutionPrepareNo: routePaymentExecutionPrepareNoText.value,
  paymentExecutionPrepareFound: paymentExecutionPrepareFound.value,
  resultAdapterVersion: PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_ADAPTER_VERSION,
  resultContractVersion: PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_CONTRACT_VERSION,
  resultLineContractVersion: PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LINE_CONTRACT_VERSION,
  resultContractFingerprint: PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_CONTRACT_FINGERPRINT,
  resultContractLockedFingerprint: PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_CONTRACT_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_CONTRACT_VERSION],
  resultContractFingerprintMatched: simulationResultContractValidation.value.resultContractFingerprintMatched,
  resultFieldCount: simulationResultContractValidation.value.resultFieldCount,
  resultLineFieldCount: simulationResultLineContractValidation.value.resultLineFieldCount,
  resultStorageNamespace: simulationResultStoragePreview.value.resultStorageNamespace,
  auditStorageNamespace: simulationResultStoragePreview.value.auditStorageNamespace,
  independentResultNamespace: simulationResultStoragePreview.value.independentResultNamespace,
  independentAuditNamespace: simulationResultStoragePreview.value.independentAuditNamespace,
  sharesFormalBusinessNamespace: simulationResultStoragePreview.value.sharesFormalBusinessNamespace,
  sharesBusinessStoreCollection: simulationResultStoragePreview.value[PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_ISOLATION_KEYS.businessCollectionFlag],
  usesLocalStorage: simulationResultStoragePreview.value[PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_ISOLATION_KEYS.browserStorageFlag],
  formalBusinessObjectAffected: simulationResultStoragePreview.value.formalBusinessObjectAffected,
  resultStorageDesignEvaluated: simulationResultPreview.value.resultStorageDesignEvaluated,
  simulationRequestAvailable: simulationResultPreview.value.simulationRequestAvailable,
  simulationCalculationAvailable: simulationResultPreview.value.simulationCalculationAvailable,
  resultRecordPreviewCreated: simulationResultPreview.value.resultRecordPreviewCreated,
  resultRecordStatus: simulationResultPreview.value.resultRecordStatus,
  resultReferenceNo: simulationResultPreview.value.resultRecord?.resultReferenceNo || null,
  resultLineCount: simulationResultPreview.value.resultLineCount,
  resultPayloadFingerprint: simulationResultPreview.value.resultPayloadFingerprint,
  resultRecordFingerprint: simulationResultPreview.value.resultRecordFingerprint,
  businessSimulationResultStorageReady: simulationResultPreview.value.businessSimulationResultStorageReady,
  lifecycleVersion: PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LIFECYCLE_VERSION,
  lifecyclePolicyFingerprint: PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LIFECYCLE_POLICY_FINGERPRINT,
  lifecyclePolicyLockedFingerprint: PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LIFECYCLE_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LIFECYCLE_VERSION],
  lifecyclePolicyFingerprintMatched: simulationLifecycleSummary.value.lifecyclePolicyFingerprintMatched,
  lifecyclePolicyScenarioValidationExecuted: true,
  lifecyclePolicyScenarioValidationStatus: simulationResultMatrixReport.value.overallStatus,
  legalTransitionScenarioPassed: simulationLifecycleMatrixPassed.value,
  illegalTransitionScenarioPassed: simulationInvalidTransitionBlocked.value,
  invalidationRuleScenarioPassed: simulationInvalidationScenarioPassed.value,
  auditChainSyntheticScenarioPassed: simulationAuditChainRulePassed.value,
  resultLifecycleStatus: simulationResultPreview.value.resultLifecycleStatus,
  resultValidityStatus: simulationResultPreview.value.resultValidityStatus,
  sourceConsistencyStatus: simulationResultPreview.value.sourceConsistencyStatus,
  currentRouteResultAvailableForTransition: currentRouteLifecycleDecision.value.currentRouteResultAvailableForTransition,
  currentRouteLifecycleTransitionPreviewExecuted: currentRouteLifecycleDecision.value.currentRouteLifecycleTransitionPreviewExecuted,
  currentRouteLifecycleTransitionAllowed: currentRouteLifecycleDecision.value.currentRouteLifecycleTransitionAllowed,
  currentRouteInvalidationPreviewEvaluated: currentRouteLifecycleDecision.value.currentRouteInvalidationPreviewEvaluated,
  currentRouteShouldInvalidateResultPreview: currentRouteLifecycleDecision.value.currentRouteShouldInvalidateResultPreview,
  currentRouteInvalidationReason: currentRouteLifecycleDecision.value.currentRouteInvalidationReason,
  lifecycleTransitionPreviewExecuted: currentRouteLifecycleDecision.value.currentRouteLifecycleTransitionPreviewExecuted,
  lifecycleTransitionAllowed: currentRouteLifecycleDecision.value.currentRouteLifecycleTransitionAllowed,
  actualLifecycleTransitionExecuted: simulationLifecycleTransitionPreview.value.businessTransitionExecuted,
  resultInvalidationPreviewEvaluated: currentRouteLifecycleDecision.value.currentRouteInvalidationPreviewEvaluated,
  shouldInvalidateResultPreview: currentRouteLifecycleDecision.value.currentRouteShouldInvalidateResultPreview,
  actualResultInvalidated: simulationInvalidationPreview.value.actualResultInvalidated,
  actualResultSuperseded: simulationSupersedePreview.value.actualResultSuperseded,
  actualResultArchived: false,
  auditContractVersion: PAYMENT_VOUCHER_PREPARE_SIMULATION_AUDIT_CONTRACT_VERSION,
  auditContractFingerprint: PAYMENT_VOUCHER_PREPARE_SIMULATION_AUDIT_CONTRACT_FINGERPRINT,
  auditContractLockedFingerprint: PAYMENT_VOUCHER_PREPARE_SIMULATION_AUDIT_CONTRACT_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PREPARE_SIMULATION_AUDIT_CONTRACT_VERSION],
  auditContractFingerprintMatched: simulationAuditContractValidation.value.auditContractFingerprintMatched,
  auditFieldCount: simulationAuditContractValidation.value.auditFieldCount,
  auditContractPreviewEvaluated: true,
  auditEventPreviewCreated: false,
  auditEventCount: 0,
  auditChainStatus: simulationAuditChainStatus.value,
  appendOnlyPolicyReadyPreview: simulationAuditTrailSummary.value.appendOnlyPolicyReadyPreview,
  auditChainVerified: simulationAuditTrailSummary.value.auditChainVerified,
  realAuditEventCreatedCount: 0,
  businessSimulationAuditStorageReady: false,
  precheckReadinessFlags: {
    simulationResultStorageReady: normalizedPurePrecheckInput.value.simulationResultStorageReady,
    simulationLogStorageReady: normalizedPurePrecheckInput.value.simulationLogStorageReady,
  },
  simulationResultTestMatrixVersion: simulationResultMatrixReport.value.matrixVersion,
  simulationResultTestCaseCount: simulationResultMatrixReport.value.testCaseCount,
  simulationResultFailedCaseCount: simulationResultMatrixReport.value.failedCaseCount,
  simulationResultAssertionCount: simulationResultMatrixReport.value.assertionCount,
  simulationResultFailedAssertionCount: simulationResultMatrixReport.value.failedAssertionCount,
  simulationResultTestOverallStatus: simulationResultMatrixReport.value.overallStatus,
  ruleSetFingerprint: governanceSummary.value.ruleSetFingerprint,
  ruleSetFingerprintMatched: governanceSummary.value.ruleSetFingerprintMatched,
  inputContractFingerprint: governanceSummary.value.inputContractFingerprint,
  inputContractFingerprintMatched: governanceSummary.value.inputContractFingerprintMatched,
  baselineFingerprint: governanceSummary.value.baselineFingerprint,
  baselineFingerprintMatched: governanceSummary.value.baselineFingerprintMatched,
  snapshotContractFingerprint: PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_CONTRACT_FINGERPRINT,
  snapshotContractFingerprintMatched: sourceSnapshotContractValidation.value.snapshotContractFingerprintMatched,
  requestPackageContractFingerprint: PAYMENT_VOUCHER_PREPARE_REQUEST_PACKAGE_CONTRACT_FINGERPRINT,
  requestPackageContractFingerprintMatched: requestPackageContractValidation.value.requestPackageContractFingerprintMatched,
  idempotencyPolicyFingerprint: PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_POLICY_FINGERPRINT,
  idempotencyPolicyFingerprintMatched: PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_POLICY_FINGERPRINT === PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_POLICY_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_VERSION],
  concurrencyPolicyFingerprint: PAYMENT_VOUCHER_PREPARE_CONCURRENCY_POLICY_FINGERPRINT,
  concurrencyPolicyFingerprintMatched: PAYMENT_VOUCHER_PREPARE_CONCURRENCY_POLICY_FINGERPRINT === PAYMENT_VOUCHER_PREPARE_CONCURRENCY_POLICY_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PREPARE_CONCURRENCY_VERSION],
  currentRoutePassedCount: purePrecheckResult.value.passedCount,
  currentRouteBlockedCount: purePrecheckResult.value.blockedCount,
  currentRouteWarningCount: purePrecheckResult.value.warningCount,
  currentRouteNotApplicableCount: purePrecheckResult.value.notApplicableCount,
  currentRoutePrecheckDecision: purePrecheckResult.value.decision,
  currentRoutePrecheckCanProceed: purePrecheckResult.value.canProceed,
  currentExecutionState: notCreated,
  stateMachineStartAllowed: false,
  realSimulationRequestCreatedCount: 0,
  realSimulationResultCreatedCount: 0,
  formalBusinessWritePathCount: 0,
  businessDataWrittenCount: 0,
  businessRollbackCount: 0,
  businessCompensationCount: 0,
  realBusinessObjectCleanupRequiredCount: 0,
  protectionFlags,
  routeStabilityCheck: routeStabilityCheck.value,
  timestamp: new Date().toISOString(),
}))

const paymentVoucherPrepareRequestPackageIdempotencyConcurrencySummary = computed(() => ({
  page: 'PaymentVoucherPreparePreviewPage',
  version,
  routePaymentExecutionPrepareNo: routePaymentExecutionPrepareNoText.value,
  paymentExecutionPrepareFound: paymentExecutionPrepareFound.value,
  requestAdapterVersion: PAYMENT_VOUCHER_PREPARE_REQUEST_ADAPTER_VERSION,
  requestPackageContractVersion: PAYMENT_VOUCHER_PREPARE_REQUEST_PACKAGE_CONTRACT_VERSION,
  requestPackageContractFingerprint: PAYMENT_VOUCHER_PREPARE_REQUEST_PACKAGE_CONTRACT_FINGERPRINT,
  requestPackageContractLockedFingerprint: PAYMENT_VOUCHER_PREPARE_REQUEST_PACKAGE_CONTRACT_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PREPARE_REQUEST_PACKAGE_CONTRACT_VERSION],
  requestPackageContractFingerprintMatched: requestPackageContractValidation.value.requestPackageContractFingerprintMatched,
  requestPackageFieldCount: requestPackagePreview.value.requestPackageFieldCount,
  requestPackagePreviewEvaluated: requestPackagePreview.value.requestPackagePreviewEvaluated,
  requestPackagePreviewCreated: requestPackagePreview.value.requestPackagePreviewCreated,
  requestPackageStatus: requestPackagePreview.value.requestPackageStatus,
  presentFieldCount: requestPackagePreview.value.presentFieldCount,
  missingFieldCount: requestPackagePreview.value.missingFieldCount,
  missingBusinessRequiredFieldCount: requestPackagePreview.value.missingBusinessRequiredFieldCount,
  missingBusinessRequiredFields: requestPackagePreview.value.missingBusinessRequiredFields,
  requestPackageFingerprintPreviewGenerated: requestPackagePreview.value.requestPackageFingerprintPreviewGenerated,
  requestPackageFingerprint: requestPackagePreview.value.requestPackageFingerprint,
  businessRequestPackageReady: requestPackagePreview.value.businessRequestPackageReady,
  idempotencyVersion: PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_VERSION,
  idempotencyPolicyFingerprint: PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_POLICY_FINGERPRINT,
  idempotencyPolicyLockedFingerprint: PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_POLICY_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_VERSION],
  idempotencyPolicyFingerprintMatched: PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_POLICY_FINGERPRINT === PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_POLICY_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_VERSION],
  idempotencyMaterialPreviewGenerated: idempotencyKeyPreview.value.idempotencyMaterialPreviewGenerated,
  idempotencyKeyPreviewGenerated: idempotencyKeyPreview.value.idempotencyKeyPreviewGenerated,
  idempotencyKeyStatus: idempotencyKeyPreview.value.idempotencyKeyStatus,
  idempotencyKey: idempotencyKeyPreview.value.idempotencyKey,
  idempotencyRequiredFieldCount: idempotencyKeyPreview.value.requiredFieldCount,
  idempotencyMissingRequiredFieldCount: idempotencyKeyPreview.value.missingRequiredFieldCount,
  idempotencyMissingRequiredFields: idempotencyKeyPreview.value.missingRequiredFields,
  sameInputSameIdempotencyKey: idempotencyKeyPreview.value.sameInputSameKey,
  idempotencyRegistryAvailable: idempotencyResolutionPreview.value.registryAvailable,
  idempotencyResolutionStatus: idempotencyResolutionPreview.value.idempotencyResolutionStatus,
  shouldCreateNewRequestPreview: idempotencyResolutionPreview.value.shouldCreateNewRequestPreview,
  shouldReuseExistingRequestPreview: idempotencyResolutionPreview.value.shouldReuseExistingRequestPreview,
  shouldBlockDuplicateRequestPreview: idempotencyResolutionPreview.value.shouldBlockDuplicateRequestPreview,
  businessIdempotencyMechanismReady: idempotencyResolutionPreview.value.businessIdempotencyMechanismReady,
  concurrencyVersion: PAYMENT_VOUCHER_PREPARE_CONCURRENCY_VERSION,
  concurrencyPolicyFingerprint: PAYMENT_VOUCHER_PREPARE_CONCURRENCY_POLICY_FINGERPRINT,
  concurrencyPolicyLockedFingerprint: PAYMENT_VOUCHER_PREPARE_CONCURRENCY_POLICY_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PREPARE_CONCURRENCY_VERSION],
  concurrencyPolicyFingerprintMatched: PAYMENT_VOUCHER_PREPARE_CONCURRENCY_POLICY_FINGERPRINT === PAYMENT_VOUCHER_PREPARE_CONCURRENCY_POLICY_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PREPARE_CONCURRENCY_VERSION],
  concurrencyPreviewEvaluated: concurrencyPreview.value.concurrencyPreviewEvaluated,
  lockScopeMaterialPreviewGenerated: concurrencyPreview.value.lockScopeMaterialPreviewGenerated,
  lockScopeKeyPreviewGenerated: concurrencyPreview.value.lockScopeKeyPreviewGenerated,
  lockScopeKey: concurrencyPreview.value.lockScopeKey,
  runtimeStateAvailable: concurrencyPreview.value.runtimeStateAvailable,
  activeRequestCount: concurrencyPreview.value.activeRequestCount,
  activeLockCount: concurrencyPreview.value.activeLockCount,
  expiredLockCount: concurrencyPreview.value.expiredLockCount,
  sameIdempotencyRequestCount: concurrencyPreview.value.sameIdempotencyRequestCount,
  otherRequestConflictCount: concurrencyPreview.value.otherRequestConflictCount,
  concurrencyStatus: concurrencyPreview.value.concurrencyStatus,
  canAcquireLockPreview: concurrencyPreview.value.canAcquireLockPreview,
  concurrencyShouldReuseExistingRequestPreview: concurrencyPreview.value.shouldReuseExistingRequestPreview,
  shouldBlockNewRequestPreview: concurrencyPreview.value.shouldBlockNewRequestPreview,
  actualLockAcquired: concurrencyPreview.value.actualLockAcquired,
  businessConcurrencyMechanismReady: concurrencyPreview.value.businessConcurrencyMechanismReady,
  precheckReadinessFlags: {
    uniquenessRuleReady: normalizedPurePrecheckInput.value.uniquenessRuleReady,
    idempotencyRuleReady: normalizedPurePrecheckInput.value.idempotencyRuleReady,
    concurrencyControlReady: normalizedPurePrecheckInput.value.concurrencyControlReady,
  },
  requestControlTestMatrixVersion: requestControlMatrixReport.value.matrixVersion,
  requestControlTestCaseCount: requestControlMatrixReport.value.testCaseCount,
  requestControlFailedCaseCount: requestControlMatrixReport.value.failedCaseCount,
  requestControlAssertionCount: requestControlMatrixReport.value.assertionCount,
  requestControlFailedAssertionCount: requestControlMatrixReport.value.failedAssertionCount,
  requestControlTestOverallStatus: requestControlMatrixReport.value.overallStatus,
  ruleSetFingerprint: governanceSummary.value.ruleSetFingerprint,
  ruleSetFingerprintMatched: governanceSummary.value.ruleSetFingerprintMatched,
  inputContractFingerprint: governanceSummary.value.inputContractFingerprint,
  inputContractFingerprintMatched: governanceSummary.value.inputContractFingerprintMatched,
  baselineFingerprint: governanceSummary.value.baselineFingerprint,
  baselineFingerprintMatched: governanceSummary.value.baselineFingerprintMatched,
  snapshotContractFingerprint: PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_CONTRACT_FINGERPRINT,
  snapshotContractFingerprintMatched: sourceSnapshotContractValidation.value.snapshotContractFingerprintMatched,
  currentRoutePassedCount: purePrecheckResult.value.passedCount,
  currentRouteBlockedCount: purePrecheckResult.value.blockedCount,
  currentRouteWarningCount: purePrecheckResult.value.warningCount,
  currentRouteNotApplicableCount: purePrecheckResult.value.notApplicableCount,
  currentRoutePrecheckDecision: purePrecheckResult.value.decision,
  currentRoutePrecheckCanProceed: purePrecheckResult.value.canProceed,
  currentExecutionState: notCreated,
  stateMachineStartAllowed: false,
  formalBusinessWritePathCount: 0,
  businessDataWrittenCount: 0,
  businessRollbackCount: 0,
  businessCompensationCount: 0,
  realBusinessObjectCleanupRequiredCount: 0,
  protectionFlags,
  routeStabilityCheck: routeStabilityCheck.value,
  timestamp: new Date().toISOString(),
}))

const paymentVoucherPrepareSimulationPermissionConfirmationSandboxSummary = computed(() => ({
  page: 'PaymentVoucherPreparePreviewPage',
  version,
  routePaymentExecutionPrepareNo: routePaymentExecutionPrepareNoText.value,
  paymentExecutionPrepareFound: paymentExecutionPrepareFound.value,
  permissionVersion: PAYMENT_VOUCHER_PREPARE_SIMULATION_PERMISSION_VERSION,
  permissionContextFieldCount: PAYMENT_VOUCHER_PREPARE_SIMULATION_PERMISSION_CONTEXT_FIELDS.length,
  requiredPermissionCode: PAYMENT_VOUCHER_PREPARE_SIMULATION_PERMISSION_REQUIRED_CODE,
  permissionPolicyFingerprint: simulationPermissionPreview.value.permissionPolicyFingerprint,
  permissionPolicyLockedFingerprint: simulationPermissionPreview.value.permissionPolicyLockedFingerprint,
  permissionPolicyFingerprintMatched: simulationPermissionPreview.value.permissionPolicyFingerprintMatched,
  permissionPolicyScenarioValidationExecuted: true,
  permissionPolicyScenarioValidationStatus: executionGuardMatrixReport.value.overallStatus,
  permissionEvaluationExecuted: simulationPermissionPreview.value.permissionEvaluationExecuted,
  runtimeContextAvailable: simulationPermissionPreview.value.runtimeContextAvailable,
  actorId: simulationPermissionPreview.value.actorId,
  authenticationEvaluated: simulationPermissionPreview.value.authenticationEvaluated,
  authenticated: simulationPermissionPreview.value.authenticated,
  actorStatusEvaluated: simulationPermissionPreview.value.actorStatusEvaluated,
  actorActive: simulationPermissionPreview.value.actorActive,
  mfaEvaluated: simulationPermissionPreview.value.mfaEvaluated,
  mfaVerified: simulationPermissionPreview.value.mfaVerified,
  permissionCodeMatched: simulationPermissionPreview.value.permissionCodeMatched,
  dataScopeEvaluated: simulationPermissionPreview.value.dataScopeEvaluated,
  dataScopeMatched: simulationPermissionPreview.value.dataScopeMatched,
  delegationEvaluated: simulationPermissionPreview.value.delegationEvaluated,
  delegationValid: simulationPermissionPreview.value.delegationValid,
  permissionDecisionStatus: simulationPermissionPreview.value.permissionDecisionStatus,
  permissionGrantedPreview: simulationPermissionPreview.value.permissionGrantedPreview,
  permissionDecisionFingerprintPreviewGenerated: simulationPermissionPreview.value.permissionDecisionFingerprintPreviewGenerated,
  permissionDecisionFingerprint: simulationPermissionPreview.value.permissionDecisionFingerprint,
  actualPermissionGranted: simulationPermissionPreview.value.actualPermissionGranted,
  businessPermissionMechanismReady: simulationPermissionPreview.value.businessPermissionMechanismReady,
  confirmationVersion: PAYMENT_VOUCHER_PREPARE_SIMULATION_CONFIRMATION_VERSION,
  confirmationFieldCount: PAYMENT_VOUCHER_PREPARE_SIMULATION_CONFIRMATION_FIELDS.length,
  confirmationRequirementCount: PAYMENT_VOUCHER_PREPARE_SIMULATION_CONFIRMATION_REQUIREMENTS.length,
  confirmationContractFingerprint: simulationConfirmationPreview.value.confirmationContractFingerprint,
  confirmationLockedFingerprint: simulationConfirmationPreview.value.confirmationLockedFingerprint,
  confirmationFingerprintMatched: simulationConfirmationPreview.value.confirmationFingerprintMatched,
  confirmationPolicyScenarioValidationExecuted: simulationConfirmationPreview.value.confirmationPolicyScenarioValidationExecuted,
  confirmationPolicyScenarioValidationStatus: simulationConfirmationPreview.value.confirmationPolicyScenarioValidationStatus,
  confirmationRequirementPreviewEvaluated: simulationConfirmationPreview.value.confirmationRequirementPreviewEvaluated,
  confirmationSummaryPreviewCreated: simulationConfirmationPreview.value.confirmationSummaryPreviewCreated,
  confirmationSummaryStatus: simulationConfirmationPreview.value.confirmationSummaryStatus,
  confirmationSummaryFingerprintPreviewGenerated: simulationConfirmationPreview.value.confirmationSummaryFingerprintPreviewGenerated,
  confirmationSummaryFingerprint: simulationConfirmationPreview.value.confirmationSummaryFingerprint,
  satisfiedRequirementCount: simulationConfirmationPreview.value.satisfiedRequirementCount,
  missingRequirementCount: simulationConfirmationPreview.value.missingRequirementCount,
  missingRequirements: simulationConfirmationPreview.value.missingRequirements,
  confirmationChallengeCreated: simulationConfirmationPreview.value.confirmationChallengeCreated,
  confirmationReferenceNo: simulationConfirmationPreview.value.confirmationReferenceNo,
  confirmationTokenGenerated: simulationConfirmationPreview.value.confirmationTokenGenerated,
  confirmationToken: simulationConfirmationPreview.value.confirmationToken,
  explicitUserConfirmed: simulationConfirmationPreview.value.explicitUserConfirmed,
  confirmationDecisionStatus: simulationConfirmationPreview.value.confirmationDecisionStatus,
  canConfirmPreview: simulationConfirmationPreview.value.canConfirmPreview,
  secondConfirmationSatisfiedPreview: simulationConfirmationPreview.value.secondConfirmationSatisfiedPreview,
  actualConfirmationCompleted: simulationConfirmationPreview.value.actualConfirmationCompleted,
  businessSecondConfirmationMechanismReady: simulationConfirmationPreview.value.businessSecondConfirmationMechanismReady,
  sandboxVersion: PAYMENT_VOUCHER_PREPARE_SIMULATION_SANDBOX_VERSION,
  effectManifestVersion: PAYMENT_VOUCHER_PREPARE_SIMULATION_EFFECT_MANIFEST_VERSION,
  effectFieldCount: PAYMENT_VOUCHER_PREPARE_SIMULATION_EFFECT_FIELDS.length,
  effectManifestCount: PAYMENT_VOUCHER_PREPARE_SIMULATION_EFFECT_MANIFEST.length,
  allowedPurePreviewEffectCount: simulationSandboxAdmissionPreview.value.allowedPurePreviewEffectCount,
  forbiddenByPolicyEffectCount: simulationSandboxAdmissionPreview.value.forbiddenByPolicyEffectCount,
  allowedCurrentRouteEffectCount: simulationSandboxAdmissionPreview.value.allowedCurrentRouteEffectCount,
  currentRouteForbiddenEffectCount: simulationSandboxAdmissionPreview.value.currentRouteForbiddenEffectCount,
  currentRouteProposedEffectCount: simulationSandboxAdmissionPreview.value.currentRouteProposedEffectCount,
  sandboxPolicyFingerprint: simulationSandboxAdmissionPreview.value.sandboxPolicyFingerprint,
  sandboxPolicyLockedFingerprint: simulationSandboxAdmissionPreview.value.sandboxPolicyLockedFingerprint,
  sandboxPolicyFingerprintMatched: simulationSandboxAdmissionPreview.value.sandboxPolicyFingerprintMatched,
  sandboxPolicyScenarioValidationExecuted: simulationSandboxAdmissionPreview.value.sandboxPolicyScenarioValidationExecuted,
  sandboxPolicyScenarioValidationStatus: simulationSandboxAdmissionPreview.value.sandboxPolicyScenarioValidationStatus,
  safeEffectScenarioPassed: simulationSandboxAdmissionPreview.value.safeEffectScenarioPassed,
  forbiddenBusinessEffectScenarioPassed: simulationSandboxAdmissionPreview.value.forbiddenBusinessEffectScenarioPassed,
  forbiddenInfrastructureEffectScenarioPassed: simulationSandboxAdmissionPreview.value.forbiddenInfrastructureEffectScenarioPassed,
  sandboxAdmissionEvaluated: simulationSandboxAdmissionPreview.value.sandboxAdmissionEvaluated,
  currentRouteEffectPlanAvailable: simulationSandboxAdmissionPreview.value.currentRouteEffectPlanAvailable,
  effectPlanFingerprintPreviewGenerated: simulationSandboxAdmissionPreview.value.effectPlanFingerprintPreviewGenerated,
  effectPlanFingerprint: simulationSandboxAdmissionPreview.value.effectPlanFingerprint,
  proposedEffectCount: simulationSandboxAdmissionPreview.value.proposedEffectCount,
  allowedEffectCount: simulationSandboxAdmissionPreview.value.allowedEffectCount,
  currentForbiddenEffectCount: simulationSandboxAdmissionPreview.value.currentForbiddenEffectCount,
  forbiddenBusinessWriteCount: simulationSandboxAdmissionPreview.value.forbiddenBusinessWriteCount,
  forbiddenSimulationWriteCount: simulationSandboxAdmissionPreview.value.forbiddenSimulationWriteCount,
  deniedEffects: simulationSandboxAdmissionPreview.value.deniedEffects,
  sandboxRuntimeAvailable: simulationSandboxAdmissionPreview.value.sandboxRuntimeAvailable,
  sandboxAdmissionStatus: simulationSandboxAdmissionPreview.value.sandboxAdmissionStatus,
  canEnterSandboxPreview: simulationSandboxAdmissionPreview.value.canEnterSandboxPreview,
  actualSandboxEntered: simulationSandboxAdmissionPreview.value.actualSandboxEntered,
  actualEffectCount: simulationSandboxAdmissionPreview.value.actualEffectCount,
  formalBusinessWriteDetected: simulationSandboxAdmissionPreview.value.formalBusinessWriteDetected,
  simulationWriteDetected: simulationSandboxAdmissionPreview.value.simulationWriteDetected,
  browserStorageWriteDetected: simulationSandboxAdmissionPreview.value.browserStorageWriteDetected,
  networkMutationDetected: simulationSandboxAdmissionPreview.value.networkMutationDetected,
  businessZeroWriteSandboxMechanismReady: simulationSandboxAdmissionPreview.value.businessZeroWriteSandboxMechanismReady,
  precheckReadinessFlags: {
    permissionReady: normalizedPurePrecheckInput.value.permissionReady,
    secondConfirmationReady: normalizedPurePrecheckInput.value.secondConfirmationReady,
    zeroBusinessWriteBoundaryReady: normalizedPurePrecheckInput.value.zeroBusinessWriteBoundaryReady,
  },
  executionGuardTestMatrixVersion: executionGuardMatrixReport.value.matrixVersion,
  executionGuardTestCaseCount: executionGuardMatrixReport.value.testCaseCount,
  executionGuardFailedCaseCount: executionGuardMatrixReport.value.failedCaseCount,
  executionGuardAssertionCount: executionGuardMatrixReport.value.assertionCount,
  executionGuardFailedAssertionCount: executionGuardMatrixReport.value.failedAssertionCount,
  executionGuardTestOverallStatus: executionGuardMatrixReport.value.overallStatus,
  ruleSetFingerprint: governanceSummary.value.ruleSetFingerprint,
  ruleSetFingerprintMatched: governanceSummary.value.ruleSetFingerprintMatched,
  inputContractFingerprint: governanceSummary.value.inputContractFingerprint,
  inputContractFingerprintMatched: governanceSummary.value.inputContractFingerprintMatched,
  baselineFingerprint: governanceSummary.value.baselineFingerprint,
  baselineFingerprintMatched: governanceSummary.value.baselineFingerprintMatched,
  snapshotContractFingerprint: PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_CONTRACT_FINGERPRINT,
  snapshotContractFingerprintMatched: sourceSnapshotContractValidation.value.snapshotContractFingerprintMatched,
  requestPackageContractFingerprint: PAYMENT_VOUCHER_PREPARE_REQUEST_PACKAGE_CONTRACT_FINGERPRINT,
  requestPackageContractFingerprintMatched: requestPackageContractValidation.value.requestPackageContractFingerprintMatched,
  idempotencyPolicyFingerprint: PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_POLICY_FINGERPRINT,
  idempotencyPolicyFingerprintMatched: PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_POLICY_FINGERPRINT === PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_POLICY_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_VERSION],
  concurrencyPolicyFingerprint: PAYMENT_VOUCHER_PREPARE_CONCURRENCY_POLICY_FINGERPRINT,
  concurrencyPolicyFingerprintMatched: PAYMENT_VOUCHER_PREPARE_CONCURRENCY_POLICY_FINGERPRINT === PAYMENT_VOUCHER_PREPARE_CONCURRENCY_POLICY_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PREPARE_CONCURRENCY_VERSION],
  resultContractFingerprint: PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_CONTRACT_FINGERPRINT,
  resultContractFingerprintMatched: simulationResultContractValidation.value.resultContractFingerprintMatched,
  lifecyclePolicyFingerprint: PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LIFECYCLE_POLICY_FINGERPRINT,
  lifecyclePolicyFingerprintMatched: simulationLifecycleSummary.value.lifecyclePolicyFingerprintMatched,
  auditContractFingerprint: PAYMENT_VOUCHER_PREPARE_SIMULATION_AUDIT_CONTRACT_FINGERPRINT,
  auditContractFingerprintMatched: simulationAuditContractValidation.value.auditContractFingerprintMatched,
  currentRoutePassedCount: purePrecheckResult.value.passedCount,
  currentRouteBlockedCount: purePrecheckResult.value.blockedCount,
  currentRouteWarningCount: purePrecheckResult.value.warningCount,
  currentRouteNotApplicableCount: purePrecheckResult.value.notApplicableCount,
  currentRoutePrecheckDecision: purePrecheckResult.value.decision,
  currentRoutePrecheckCanProceed: purePrecheckResult.value.canProceed,
  currentExecutionState: notCreated,
  stateMachineStartAllowed: false,
  realPermissionGrantedCount: 0,
  realSecondConfirmationCompletedCount: 0,
  realSandboxEnteredCount: 0,
  realSimulationRequestCreatedCount: 0,
  realSimulationResultCreatedCount: 0,
  realAuditEventCreatedCount: 0,
  formalBusinessWritePathCount: 0,
  businessDataWrittenCount: 0,
  businessRollbackCount: 0,
  businessCompensationCount: 0,
  realBusinessObjectCleanupRequiredCount: 0,
  protectionFlags,
  routeStabilityCheck: routeStabilityCheck.value,
  timestamp: new Date().toISOString(),
}))

const diagnosticData = computed(() => ({
  page: 'PaymentVoucherPreparePreviewPage',
  version,
  acceptanceCopySingleSource: true,
  manualAcceptanceNavigationVisible: true,
  acceptanceCurrentVersionMatch: version === BUSINESS_ACCEPTANCE_COPY_VERSION,
  acceptanceSectionTitleExactMatch: true,
  acceptanceFieldLabelExactMatch: true,
  acceptanceCtrlFExactMatch: true,
  sourceObjectNo: paymentExecutionPrepareNoText.value,
  targetObjectNoRaw: targetEvidenceClassification.value.targetObjectNoRaw,
  targetObjectNoDisplay: targetObjectNoDisplay.value,
  targetEvidenceStatus: targetEvidenceStatusCode.value,
  targetEvidenceStatusText: targetEvidenceStatusText.value,
  targetEvidenceProcessingStatus: targetEvidenceProcessingStatus.value,
  targetEvidenceProcessingStatusText: targetEvidenceProcessingStatusText.value,
  simulationExecutionStatus: notCreated,
  simulationExecutionStatusText,
  targetEvidenceResultSource: 'businessTargetEvidenceClassifier.js',
  targetEvidenceResultSourceText,
  targetEvidenceTraceRows: targetEvidenceRuntimeRows.value,
  targetEvidenceTraceItems: targetEvidenceRuntimeRows.value,
  targetEvidenceMissingItems: targetEvidenceMissingItems.value,
  targetEvidenceConflictItems: targetEvidenceConflictItems.value,
  targetEvidenceReadFailures: targetEvidenceReadFailures.value,
  targetEvidenceFirstFailure: targetEvidenceFirstFailureSummary.value,
  precheckFirstBlock: precheckFirstBlockSummary.value,
  protectionFlags: {
    writeLocalStorage: false,
    modifyBusinessStore: false,
    startStateMachine: false,
    createSimulationRequest: false,
    createSimulationResult: false,
    generatePaymentVoucher: false,
    writeLedger: false,
    writeOff: false,
    executeRealPayment: false,
  },
  acceptanceFacts: acceptanceFacts.value,
  actionDecisionEvidence: {
    actionCode: 'VIEW_PAYMENT_VOUCHER_PREPARE_PREVIEW',
    registrySource: 'PCE Business Action Registry',
    registryAdapter: 'paymentVoucherPreparePageAcceptanceRuntime whitelist',
    uiButtonCount: pageButtonWhitelist.value.allowedButtonCount,
    rolePermissionAllowed: true,
    currentState: currentRow.value?.status || 'read_only_preview',
    decision: pageButtonWhitelist.value.whitelistStatus === 'passed' ? 'ALLOWED' : 'BLOCKED',
    reason: pageButtonWhitelist.value.whitelistStatus === 'passed'
      ? '仅允许只读查看、返回与复制诊断动作'
      : '页面包含未登记动作',
  },
  paymentVoucherPrepareAcceptanceManifestVersion: PAYMENT_VOUCHER_PREPARE_ACCEPTANCE_MANIFEST_VERSION,
  paymentVoucherPrepareAcceptanceData: paymentVoucherPrepareAcceptanceData.value,
  paymentVoucherPrepareAutomaticAcceptanceResult: automaticAcceptanceResult.value,
  paymentVoucherPrepareSimulationPermissionConfirmationSandboxSummary: paymentVoucherPrepareSimulationPermissionConfirmationSandboxSummary.value,
  paymentVoucherPrepareSimulationResultLifecycleAuditSummary: paymentVoucherPrepareSimulationResultLifecycleAuditSummary.value,
  paymentVoucherPrepareRequestPackageIdempotencyConcurrencySummary: paymentVoucherPrepareRequestPackageIdempotencyConcurrencySummary.value,
  paymentVoucherPrepareSourceSnapshotFingerprintChangeSummary: paymentVoucherPrepareSourceSnapshotFingerprintChangeSummary.value,
  paymentVoucherPreparePurePrecheckGovernanceSummary: paymentVoucherPreparePurePrecheckGovernanceSummary.value,
  paymentVoucherPreparePurePrecheckTestMatrixSummary: paymentVoucherPreparePurePrecheckTestMatrixSummary.value,
  paymentVoucherPreparePurePrecheckEngineDesignSummary: paymentVoucherPreparePurePrecheckEngineDesignSummary.value,
  paymentVoucherPrepareSimulationStateMachineDesignSummary: paymentVoucherPrepareSimulationStateMachineDesignSummary.value,
  paymentVoucherPrepareSimulationFinalReviewSummary: {
    page: 'PaymentVoucherPreparePreviewPage',
    version,
    preservedFromVersion: 'V1.13.60',
    finalReviewStatus: '不放行',
    simulationReleaseAllowed: false,
    simulationExecutionAllowed: false,
  },
  paymentVoucherPrepareSimulationResultDesignSummary: {
    page: 'PaymentVoucherPreparePreviewPage',
    version,
    preservedFromVersion: 'V1.13.59',
    simulationResultObjectCreated: false,
    simulationResultNoGenerated: false,
    sourceFingerprintCalculated: false,
    uniqueIndexCreated: false,
    duplicateSimulationChecked: false,
  },
  paymentVoucherPrepareSimulationPreDesignSummary: {
    page: 'PaymentVoucherPreparePreviewPage',
    version,
    preservedFromVersion: 'V1.13.58',
    simulationExecutedThisRound: false,
    simulationEntryEnabled: false,
    simulationEntryClickable: false,
  },
  diagnosticChineseSummary: [
    'V1.13.67.1 付款凭证准备当前路由生命周期判断与合成策略验证语义隔离。',
    '合成策略验证用于证明规则通过，当前路由字段只说明当前业务是否存在可转换或可失效的模拟结果。',
    `模拟结果适配器版本：${PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_ADAPTER_VERSION}。`,
    `模拟结果记录契约版本：${PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_CONTRACT_VERSION}，字段数：${simulationResultContractValidation.value.resultFieldCount}。`,
    `模拟结果明细契约版本：${PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LINE_CONTRACT_VERSION}，字段数：${simulationResultLineContractValidation.value.resultLineFieldCount}。`,
    `生命周期策略版本：${PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LIFECYCLE_VERSION}。`,
    `审计事件契约版本：${PAYMENT_VOUCHER_PREPARE_SIMULATION_AUDIT_CONTRACT_VERSION}，字段数：${simulationAuditContractValidation.value.auditFieldCount}。`,
    `结果契约指纹：${PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_CONTRACT_FINGERPRINT}。`,
    `生命周期策略指纹：${PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LIFECYCLE_POLICY_FINGERPRINT}。`,
    `审计契约指纹：${PAYMENT_VOUCHER_PREPARE_SIMULATION_AUDIT_CONTRACT_FINGERPRINT}。`,
    `当前结果记录状态：${simulationResultPreview.value.resultRecordStatus}。`,
    `当前结果生命周期：${simulationResultPreview.value.resultLifecycleStatus}。`,
    `当前结果有效性：${simulationResultPreview.value.resultValidityStatus}。`,
    `当前结果编号：${simulationResultPreview.value.resultRecord?.resultReferenceNo || '未生成'}。`,
    `当前结果明细数量：${simulationResultPreview.value.resultLineCount}。`,
    `当前结果记录指纹：${simulationResultPreview.value.resultRecordFingerprint || '未生成'}。`,
    `当前路由是否存在可转换的模拟结果：${currentRouteLifecycleDecision.value.currentRouteResultAvailableForTransition ? yes() : no()}。`,
    `当前路由是否执行生命周期转换预览：${currentRouteLifecycleDecision.value.currentRouteLifecycleTransitionPreviewExecuted ? yes() : no()}。`,
    `当前路由是否允许生命周期转换：${currentRouteLifecycleDecision.value.currentRouteLifecycleTransitionAllowed ? yes() : no()}。`,
    `当前路由是否执行结果失效判断：${currentRouteLifecycleDecision.value.currentRouteInvalidationPreviewEvaluated ? yes() : no()}。`,
    `当前路由是否建议失效结果：${currentRouteLifecycleDecision.value.currentRouteShouldInvalidateResultPreview ? yes() : no()}。`,
    `当前路由判断原因：${currentRouteLifecycleDecision.value.currentRouteInvalidationReason}。`,
    `生命周期合成策略验证状态：${simulationResultMatrixReport.value.overallStatus}。`,
    `当前真实审计事件数量：0，审计链状态：${simulationAuditChainStatus.value}。`,
    '审计链验证仅来自测试矩阵中的合成场景，不是当前业务真实日志。',
    'simulationResultStorageReady 和 simulationLogStorageReady 继续保持 false。',
    '本轮不创建真实模拟结果，不保存模拟结果，不创建真实审计事件，不保存审计日志。',
    '状态机未启动，未创建模拟执行请求，未执行模拟计算。',
    '正式业务写入、回滚和补偿数量均为 0。',
    'V1.13.66 付款凭证准备模拟执行请求输入包、幂等键与并发控制纯函数设计。',
    `请求输入包适配器版本：${PAYMENT_VOUCHER_PREPARE_REQUEST_ADAPTER_VERSION}。`,
    `请求输入包契约版本：${PAYMENT_VOUCHER_PREPARE_REQUEST_PACKAGE_CONTRACT_VERSION}。`,
    `请求输入包契约指纹：${PAYMENT_VOUCHER_PREPARE_REQUEST_PACKAGE_CONTRACT_FINGERPRINT}。`,
    `当前请求输入包状态：${requestPackagePreview.value.requestPackageStatus}。`,
    `当前请求输入包字段数：${requestPackagePreview.value.requestPackageFieldCount}。`,
    `当前请求输入包预览是否创建：${requestPackagePreview.value.requestPackagePreviewCreated ? yes() : no()}。`,
    `当前请求输入包指纹预览是否生成：${requestPackagePreview.value.requestPackageFingerprintPreviewGenerated ? yes() : no()}。`,
    `幂等策略版本：${PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_VERSION}。`,
    `当前幂等键状态：${idempotencyKeyPreview.value.idempotencyKeyStatus}。`,
    `当前幂等注册表是否可用：${idempotencyResolutionPreview.value.registryAvailable ? yes() : no()}。`,
    `当前是否允许创建新请求：${idempotencyResolutionPreview.value.shouldCreateNewRequestPreview ? yes() : no()}。`,
    `并发控制策略版本：${PAYMENT_VOUCHER_PREPARE_CONCURRENCY_VERSION}。`,
    `当前并发判断状态：${concurrencyPreview.value.concurrencyStatus}。`,
    `当前是否允许获取锁：${concurrencyPreview.value.canAcquireLockPreview ? yes() : no()}。`,
    `当前是否实际获取锁：${concurrencyPreview.value.actualLockAcquired ? yes() : no()}。`,
    '本轮不创建真实请求，不生成传输请求号，不保存幂等键，不创建幂等注册记录，不获取并发锁。',
    'uniquenessRuleReady、idempotencyRuleReady、concurrencyControlReady 继续保持 false。',
    '当前执行状态仍为 not_created，状态机仍未启动，正式业务写入数量为0。',
    'V1.13.65 付款凭证准备模拟执行来源只读快照、数据指纹与来源变更检测纯函数设计。',
    `来源快照适配器版本：${PAYMENT_VOUCHER_PREPARE_SOURCE_ADAPTER_VERSION}。`,
    `来源快照契约版本：${PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_CONTRACT_VERSION}。`,
    `来源快照契约指纹：${PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_CONTRACT_FINGERPRINT}。`,
    `来源数据指纹版本：${PAYMENT_VOUCHER_PREPARE_SOURCE_FINGERPRINT_VERSION}。`,
    `来源变更检测器版本：${PAYMENT_VOUCHER_PREPARE_SOURCE_CHANGE_DETECTOR_VERSION}。`,
    `当前来源快照结构状态：${sourceSnapshotPreview.value.snapshotStructureStatus}。`,
    `当前来源数据指纹状态：${sourceFingerprintPreview.value.fingerprintStatus}。`,
    `当前来源变更状态：${sourceChangePreview.value.changeStatus}。`,
    '当前没有正式历史参考快照，不能确认当前业务来源未变化。',
    'sourceSnapshotReady、sourceFingerprintReady、sourceUnchanged 继续保持 false。',
    '本轮不保存快照、不保存指纹、不创建历史参考快照、不实际作废模拟结果。',
    '状态机仍未启动，当前执行状态仍为 not_created。',
    '正式业务写入、回滚和补偿数量均为 0。',
    'V1.13.64.1 付款凭证准备预检查版本治理结构补全与关键验收位置修正。',
    `规则集版本：${PAYMENT_VOUCHER_PRECHECK_RULESET_VERSION}。`,
    `输入契约版本：${PAYMENT_VOUCHER_PRECHECK_INPUT_CONTRACT_VERSION}。`,
    `回归基线版本：${PAYMENT_VOUCHER_PRECHECK_BASELINE_VERSION}。`,
    '规则集指纹、输入契约指纹、回归基线指纹均与锁定值一致。',
    '四个固定基线全部通过。',
    '页面版本变化不等于规则集版本变化。',
    '当前真实 PEP 仍为阻断。',
    '状态机仍未启动。',
    '正式业务写入数量为0。',
    'V1.13.64 付款凭证准备纯函数预检查规则版本化、输入契约与回归基线固化。',
    `规则集版本：${PAYMENT_VOUCHER_PRECHECK_RULESET_VERSION}。`,
    `输入契约版本：${PAYMENT_VOUCHER_PRECHECK_INPUT_CONTRACT_VERSION}。`,
    `回归基线版本：${PAYMENT_VOUCHER_PRECHECK_BASELINE_VERSION}。`,
    '本轮只固化规则、输入契约和回归基线口径，不改变32条规则计算结果。',
    '正常 PEP、UNKNOWN-PEP、本币全满足和外币全满足基线均由测试矩阵自动验证。',
    'V1.13.63 付款凭证准备纯函数预检查测试矩阵与边界场景验证。',
    '本轮已执行固定输入下的纯函数只读测试矩阵。',
    '测试矩阵运行不等于执行状态机预检查。',
    '测试矩阵通过不等于当前业务允许继续模拟。',
    '当前路由预检查决策仍为阻断。',
    '当前执行状态仍为 not_created。',
    '当前未创建模拟执行请求。',
    '当前未执行状态转换。',
    '当前未执行模拟计算。',
    '当前未创建模拟结果。',
    '测试输入未修改业务 Store。',
    '测试结果未写 localStorage。',
    '正式业务写入、回滚和补偿数量均为0。',
    `测试矩阵失败数量：${precheckMatrixReport.value.failedCaseCount}，失败断言数量：${precheckMatrixReport.value.failedAssertionCount}。`,
    'V1.13.62.1 付款凭证准备纯函数预检查与状态机预检查口径修正。',
    '本轮已执行只读纯函数预检查演算。',
    '纯函数演算不等于状态机预检查执行。',
    '当前未创建模拟执行请求。',
    '当前未发生状态转换。',
    '当前执行状态仍为 not_created。',
    '当前预检查结果为阻断，不允许继续模拟。',
    '相同输入产生相同输出。',
    '预检查引擎未修改输入对象。',
    '预检查引擎未读取或修改业务 Store。',
    '本轮未写 localStorage。',
    '本轮未创建模拟结果。',
    '本轮未创建付款凭证准备对象。',
    '本轮未生成付款凭证。',
    '本轮未修改业务状态和金额。',
    '正式业务写入、回滚和补偿数量均为 0。',
    'V1.13.61.1 付款凭证准备模拟执行状态机终态语义修正。',
    '业务执行结束不等于状态机最终终态，failed、timed_out、cancelled 仍需进入 cleanup_pending 和 cleaned。',
    '当前状态机未启动，仅完成只读设计。',
    '当前未创建模拟执行请求。',
    '当前未执行任何状态转换。',
    '当前未执行模拟计算和结果校验。',
    '当前未创建模拟结果。',
    '当前未创建临时执行上下文。',
    '当前未获取或释放并发锁。',
    '当前正式业务写入、回滚和补偿数量均为 0。',
    '当前未创建付款凭证准备对象。',
    '当前未生成付款凭证。',
    '当前未修改业务状态或金额。',
    '当前未核销、未写总账、未过账、未执行真实付款。',
  ],
}))

function executionState(code, name, meaning, businessExecutionEnded, stateMachineTerminal, retryAllowed, cancelAllowed) {
  return {
    code,
    name,
    meaning,
    businessExecutionEnded,
    stateMachineTerminal,
    retryAllowed,
    cancelAllowed,
    formalObjectAllowed: no(),
    enteredThisRound: no(),
  }
}

function resultState(code, name, meaning, current) {
  return { code, name, meaning, currentState: current }
}

function transitionEvent(event, name, fromStates, targetState, preconditions) {
  return { event, name, fromStates, targetState, preconditions, triggeredThisRound: no() }
}

function allowedTransition(from, to, event, rule) {
  return { from, to, event, rule, executedThisRound: no() }
}

function illegalTransition(from, to, reason) {
  return { from, to, reason, futureForceBlock: yes(), blockExecutedThisRound: no() }
}

function stageItem(stage, futureInput, futureOutput) {
  return {
    stage,
    futureInput,
    futureOutput,
    readFormalBusinessData: '是，仅限未来只读快照',
    writeFormalBusinessData: no(),
    executedThisRound: no(),
  }
}

function failureType(code, description, stage, retryAllowed, cleanupRequired) {
  return {
    code,
    description,
    stage,
    retryAllowed,
    cleanupRequired,
    affectFormalBusinessData: no(),
    generatedThisRound: no(),
  }
}

function failureField(field, meaning, futureType, defaultSafeValue) {
  return { field, meaning, futureType, defaultSafeValue, generatedThisRound: no() }
}

function tempField(field, meaning) {
  return { field, meaning, createdThisRound: no() }
}

function auditField(field, meaning) {
  return { field, meaning, writeThisRound: no() }
}

function precheckResultLabel(value) {
  return {
    passed: '通过',
    failed: '失败',
    blocked: '阻断',
    warning: '警告',
    not_applicable: '不适用',
  }[value] || value || '-'
}

function snapshotStructureLabel(value) {
  return {
    complete: '完整',
    partial: '部分完整',
    source_not_found: '来源不存在',
    invalid: '无效',
  }[value] || value || '-'
}

function fingerprintStatusLabel(value) {
  return {
    complete_preview: '完整快照指纹',
    partial_preview: '部分快照指纹',
    source_not_found: '来源不存在',
    invalid: '无效',
  }[value] || value || '-'
}

function changeStatusLabel(value) {
  return {
    unchanged: '未变化',
    changed: '已变化',
    no_reference: '无参考快照',
    source_not_found: '来源不存在',
    invalid: '无效',
  }[value] || value || '-'
}

function requestPackageStatusLabel(value) {
  return {
    complete_preview: '完整预览',
    partial_preview: '部分完整',
    source_not_found: '来源不存在',
    invalid: '无效',
  }[value] || value || '-'
}

function idempotencyStatusLabel(value) {
  return {
    ready_preview: '可生成预览键',
    incomplete: '字段不完整',
    source_not_found: '来源不存在',
    invalid: '无效',
  }[value] || value || '-'
}

function idempotencyResolutionLabel(value) {
  return {
    no_registry: '无正式注册表',
    incomplete_key: '幂等键不完整',
    new_request_preview: '可创建新请求预览',
    processing_duplicate_preview: '处理中重复请求',
    reuse_completed_preview: '复用已完成请求',
    conflict_preview: '存在冲突',
    source_not_found: '来源不存在',
    invalid: '无效',
  }[value] || value || '-'
}

function concurrencyStatusLabel(value) {
  return {
    lock_available_preview: '锁可用预览',
    same_request_in_flight_preview: '同请求处理中',
    other_request_conflict_preview: '其他请求冲突',
    expired_lock_recoverable_preview: '过期锁可恢复',
    no_runtime_state: '无运行时状态',
    incomplete: '字段不完整',
    source_not_found: '来源不存在',
    invalid: '无效',
  }[value] || value || '-'
}

function simulationResultStatusLabel(value) {
  return {
    not_created: '未创建',
    source_not_found: '来源不存在',
    partial_preview: '部分预览',
    complete_preview: '完整预览',
    invalid: '无效',
  }[value] || value || '-'
}

function auditChainStatusLabel(value) {
  return {
    no_events: '无事件',
    source_not_found: '来源不存在',
    passed: '通过',
    failed: '失败',
  }[value] || value || '-'
}

function formatDisplayValue(value) {
  if (value === null || value === undefined || value === '') return '-'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

function baselineRow(baseline, value, specialRule) {
  return {
    baseline,
    decision: precheckResultLabel(value.decision),
    canProceedText: value.canProceed ? yes() : no(),
    totalRuleCount: value.counts.totalRuleCount,
    passedCount: value.counts.passedCount,
    blockedCount: value.counts.blockedCount,
    warningCount: value.counts.warningCount,
    notApplicableCount: value.counts.notApplicableCount,
    specialRule,
  }
}

function formatAmount(value) {
  return Number(value || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function jumpToAcceptanceSection(targetId) {
  document.getElementById(targetId)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

async function copyPageAcceptanceChecklist() {
  const text = buildPageAcceptanceChecklist({
    fullUrl: currentFullUrl.value,
    version,
    pageTitle: '付款凭证准备预览与目标证据来源链追踪',
    sourceObjectNo: paymentExecutionPrepareNoText.value,
    targetObjectNo: targetObjectNoDisplay.value,
    targetEvidenceStatus: `${targetEvidenceStatusText.value} (${targetEvidenceStatusCode.value})`,
    nextStepAllowed: targetEvidenceClassification.value.nextStepAllowed ? '是' : '否',
    nextStepBlockReason: targetEvidenceClassification.value.nextStepBlockingReason,
  })
  try {
    if (navigator?.clipboard?.writeText) await navigator.clipboard.writeText(text)
    else fallbackCopy(text)
    notify('本页验收清单已复制')
  } catch (error) {
    fallbackCopy(text)
    notify('本页验收清单已复制')
  }
}

async function copyDiagnosticData() {
  const text = JSON.stringify(diagnosticData.value, null, 2)
  try {
    if (navigator?.clipboard?.writeText) await navigator.clipboard.writeText(text)
    else fallbackCopy(text)
    notify('已复制付款凭证准备请求控制诊断数据')
  } catch (error) {
    fallbackCopy(text)
    notify('已复制付款凭证准备请求控制诊断数据')
  }
}

function fallbackCopy(text) {
  const input = document.createElement('textarea')
  input.value = text
  input.setAttribute('readonly', 'readonly')
  input.style.position = 'fixed'
  input.style.opacity = '0'
  document.body.appendChild(input)
  input.select()
  document.execCommand('copy')
  document.body.removeChild(input)
}

function notify(message, type = 'success') {
  ElMessage({ message, type, duration: 1800 })
}
</script>

<style scoped>
.payment-voucher-prepare-preview-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.page-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.boundary-card,
.table-card {
  padding: 16px;
  border: 1px solid var(--app-border, #d8dee8);
  border-radius: 8px;
  background: #fff;
  overflow-x: auto;
}

.warning-card,
.gap-card,
.conclusion-card {
  border-color: #f59e0b;
  background: #fffbeb;
}

.summary-grid,
.review-conclusion-grid,
.protection-grid,
.legacy-grid,
.zero-write-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 12px;
}

.summary-card,
.review-conclusion-grid article,
.protection-grid article,
.legacy-grid article,
.zero-write-grid article {
  display: grid;
  gap: 6px;
  padding: 14px;
  border: 1px solid var(--app-border, #d8dee8);
  border-radius: 8px;
  background: #fff;
}

.summary-card strong,
.review-conclusion-grid strong,
.zero-write-grid strong {
  font-size: 20px;
  overflow-wrap: anywhere;
}

.summary-card small,
.helper-text {
  color: #667085;
  line-height: 1.7;
}

.table-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.table-title h2 {
  margin: 0;
}

.primary-acceptance-card {
  border: 2px solid #2563eb;
  box-shadow: 0 10px 24px rgba(37, 99, 235, 0.1);
}

.acceptance-summary-title {
  display: block;
  color: #0f172a;
  font-size: 22px;
  line-height: 1.35;
}

.manual-acceptance-navigation {
  display: grid;
  gap: 12px;
  padding: 16px;
  border: 1px solid #93c5fd;
  border-radius: 8px;
  background: #f8fbff;
}

.manual-acceptance-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.manual-acceptance-heading h2,
.manual-acceptance-heading p {
  margin: 0;
}

.manual-acceptance-meta {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
}

.manual-acceptance-meta article {
  display: grid;
  gap: 6px;
  padding: 12px;
  border: 1px solid #dbeafe;
  border-radius: 8px;
  background: #fff;
}

.manual-acceptance-meta span {
  color: #64748b;
  font-size: 12px;
}

.manual-acceptance-meta strong {
  overflow-wrap: anywhere;
}

.manual-acceptance-links {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.acceptance-visible-card {
  border-color: #bfdbfe;
  background: #f8fbff;
}

.target-evidence-trace-table {
  width: 100%;
  min-width: 1500px;
  border-collapse: collapse;
}

.target-evidence-trace-table th,
.target-evidence-trace-table td {
  padding: 10px 12px;
  border: 1px solid #dbeafe;
  text-align: left;
  white-space: nowrap;
}

.target-evidence-trace-table th {
  background: #eff6ff;
  color: #1e3a8a;
}

.plain-list {
  display: grid;
  gap: 6px;
  margin: 0;
  padding-left: 22px;
  line-height: 1.7;
}

.notes-list {
  margin-top: 12px;
}

.final-block-note {
  margin-top: 12px;
  padding: 12px;
  border-radius: 8px;
  background: #fff;
  color: #92400e;
  font-weight: 800;
}

.protection-card {
  border-color: #a7d7b8;
  background: #f7fdf9;
}

.protection-grid article,
.zero-write-grid article {
  display: flex;
  justify-content: space-between;
  gap: 10px;
}

.protection-grid strong,
.zero-write-grid strong {
  color: #047857;
}

.legacy-card {
  border-color: #c7b8ea;
  background: #fbf9ff;
}
</style>



