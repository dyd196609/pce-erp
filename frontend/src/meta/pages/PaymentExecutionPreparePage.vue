<template>
  <main class="payment-execution-prepare-page app-page-shell">
    <section class="app-hero-section">
      <div>
        <p class="app-eyebrow">{{ VERSION }} · Finance</p>
        <h1>{{ pageName.pageTitle }}</h1>
        <p class="app-hero-copy">
          本页承接已复核且可签发的付款指令准备，形成后续付款执行前的准备对象。
          本页不是真实付款页面，不向银行付款，不生成银行流水，不生成付款凭证，不生成正式付款凭证，不核销，不写总账。
        </p>
      </div>
      <div class="page-actions">
        <router-link class="app-nav-button" to="/finance/payment-order-prepares">付款指令准备</router-link>
        <router-link class="app-nav-button" to="/finance/payment-executions">付款执行草稿</router-link>
        <router-link class="app-nav-button" to="/analytics">返回分析中心</router-link>
      </div>
    </section>

    <section class="manual-acceptance-navigation" data-acceptance-id="manual-acceptance-navigation">
      <div class="manual-acceptance-heading">
        <div>
          <h2>{{ businessAcceptanceSectionTitles.manualNavigation }}</h2>
          <p>本区域用于人工验收定位，按钮只跳转页面锚点，不触发付款、不生成凭证、不写总账。</p>
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
          <strong data-acceptance-id="acceptance-current-version">{{ VERSION }}</strong>
        </article>
        <article>
          <span>当前样本 PEP</span>
          <strong>{{ bankFlowPreviewEntryNo || '当前没有可供人工验收的真实 PEP 样本' }}</strong>
        </article>
        <article>
          <span>付款凭证准备预览链接</span>
          <strong>{{ paymentVoucherPreviewUrlText }}</strong>
        </article>
      </div>
      <div class="manual-acceptance-links">
        <button type="button" class="app-nav-button" @click="jumpToAcceptanceSection('payment-execution-prepare-list-section')">
          {{ businessAcceptanceSectionTitles.paymentExecutionPrepareList }}
        </button>
        <el-button type="primary" plain @click="router.push(`/finance/payment-voucher-prepare-preview/${manualAcceptancePepNo}`)">
          查看付款凭证准备预览
        </el-button>
      </div>
      <p class="helper-text">
        Ctrl+F 搜索词：{{ businessAcceptanceSectionTitles.manualNavigation }} / {{ businessAcceptanceSectionTitles.paymentExecutionPrepareList }} / 查看付款凭证准备预览
      </p>
    </section>

    <section class="table-card manual-final-review-card" data-acceptance-id="manual-final-review-three-items">
      <div class="table-title">
        <div>
          <h2>人工最终复核三项</h2>
          <p class="helper-text">本轮人工复核只保留三项：列表入口可用、表格滚动正常、目标证据语义正确。</p>
        </div>
        <span>无需再逐项核对长表格或诊断 JSON</span>
      </div>
      <div class="summary-grid">
        <article>
          <span>列表入口可用</span>
          <strong>待人工确认</strong>
          <small>页面能进入并显示付款执行准备列表</small>
        </article>
        <article>
          <span>表格滚动正常</span>
          <strong>待人工确认</strong>
          <small>单一横向滚动容器，可到达最右侧并返回</small>
        </article>
        <article>
          <span>目标证据语义正确</span>
          <strong>待人工确认</strong>
          <small>PEP 是来源对象，目标对象由预览页读取真实目标编号</small>
        </article>
      </div>
    </section>

    <section class="boundary-card">
      <strong>保护边界：</strong>
      本页只写付款执行准备对象，并允许在付款指令准备中回写付款执行准备关联编号和 issued_for_execution 状态。
      issued_for_execution 只代表签发到执行准备，不代表已付款。本页不修改采购、结算、发票、应付、付款申请、付款指令来源金额，
      不生成银行流水、付款凭证、正式付款凭证，不核销、不写总账，不改 postingStatus / ledgerStatus / paymentWriteOffStatus。
    </section>

    <section class="summary-grid">
      <article v-for="card in summaryCards" :key="card.title" class="summary-card">
        <span>{{ card.title }}</span>
        <strong>{{ card.value }}</strong>
        <small>{{ card.desc }}</small>
      </article>
    </section>

    <section class="table-card bank-flow-preview-entry-card">
      <div class="table-title">
        <div>
          <h2>银行流水导入校验预览</h2>
          <p class="helper-text">只读预览，不上传文件，不读取 Excel / CSV，不导入银行流水。</p>
        </div>
        <router-link
          v-if="bankFlowPreviewEntryNo"
          class="app-nav-button primary"
          :to="`/finance/bank-flow-import-validation-preview/${bankFlowPreviewEntryNo}`"
        >
          查看银行流水导入校验预览
        </router-link>
        <span v-else class="entry-missing-text">当前记录缺少付款执行准备单号，无法打开银行流水导入校验预览。</span>
      </div>
      <el-alert
        title="只读预览，不导入银行流水"
        description="本入口仅用于查看银行流水只读对象的数据来源适配、导入字段校验预览、重复拦截预览和保护结论，不新增导入按钮，不创建导入批次，不生成银行流水。"
        type="info"
        show-icon
        :closable="false"
      />
    </section>

    <section class="table-card bank-account-design-entry-card">
      <div class="table-title">
        <div>
          <h2>银行账户档案前置设计</h2>
          <p class="helper-text">
            只读设计，不录入真实银行账号，不影响付款，不生成银行流水。用于查看企业银行账户档案与供应商银行档案的未来字段、状态、校验和审计规则。
          </p>
        </div>
        <router-link class="app-nav-button primary" to="/finance/bank-account-master-design">
          查看银行账户档案前置设计
        </router-link>
      </div>
      <el-alert
        title="只读设计，不录入真实银行账号"
        description="本入口不新增银行账户、不新增供应商银行账号、不编辑、不保存、不删除、不上传银行文件、不导入银行流水、不生成银行流水。"
        type="info"
        show-icon
        :closable="false"
      />
    </section>

    <section class="table-card settlement-boundary-entry-card">
      <div class="table-title">
        <div>
          <h2>企业结算类型边界总览</h2>
          <p class="helper-text">
            只读边界说明，不新增结算业务，不改变付款状态。当前阶段只锁定应付结算链路，不展开应收、工资、费用、税费等结算类型。
          </p>
        </div>
        <router-link class="app-nav-button primary" to="/finance/settlement-boundary-overview">
          查看企业结算边界总览
        </router-link>
      </div>
      <el-alert
        title="只读边界说明，不新增结算业务"
        description="本入口仅用于查看企业结算类型总览、当前应付结算范围和后续扩展边界，不新增统一结算中心，不修改付款执行准备状态。"
        type="info"
        show-icon
        :closable="false"
      />
    </section>

    <section class="table-card payment-voucher-preview-entry-card">
      <div class="table-title">
        <div>
          <h2>付款凭证准备只读预览</h2>
          <p class="helper-text">
            只读预览，生成入口默认关闭；用于查看付款凭证准备模拟执行状态机与失败零写入机制设计，不启动状态机，不创建模拟请求，不执行模拟，不创建模拟结果，不生成付款凭证准备对象，不生成付款凭证，不写总账，不核销。
          </p>
        </div>
        <router-link
          v-if="bankFlowPreviewEntryNo"
          class="app-nav-button primary"
          :to="`/finance/payment-voucher-prepare-preview/${bankFlowPreviewEntryNo}`"
        >
          查看付款凭证准备模拟执行状态机与失败零写入机制设计
        </router-link>
        <span v-else class="entry-missing-text">当前记录缺少付款执行准备单号，无法打开付款凭证准备只读预览。</span>
      </div>
      <el-alert
        title="只读预览，生成入口默认关闭"
        description="本入口仅用于查看付款凭证准备模拟执行状态机、失败分类、零业务写入机制和保护边界，不启动状态机，不执行状态转换，不执行模拟，不创建模拟结果，不新增凭证准备对象，不提交审核，不复核，不写总账，不核销。"
        type="info"
        show-icon
        :closable="false"
      />
    </section>

    <section v-if="showDevelopmentDebugTools" class="table-card dev-debug-shell">
      <el-collapse v-model="debugCollapseActive">
        <el-collapse-item name="debug">
          <template #title>
            <strong>开发调试区</strong>
            <span class="debug-title-note">本区域仅用于开发阶段本地演示数据验证，不属于正式付款业务功能；上线前应隐藏或移除。</span>
          </template>

    <section class="table-card demo-chain-card">
      <div class="table-title">
        <h2>演示链路数据管理</h2>
        <span>只管理本地准备层演示对象，不修改源头业务数据</span>
      </div>
      <p class="helper-text">
        本区域用于用户端演示链路重建。可基于现有供应商结算来源候选生成最小验证链路，也可清理准备层演示对象后重新生成。
        清理和生成均不会修改采购订单、收货、检验、库存流水、应付预备来源数据，不会真实付款，不会生成银行流水、付款凭证、正式付款凭证，不核销、不写总账。
      </p>
      <div class="source-diagnostic-grid">
        <article>
          <span>当前付款执行准备数</span>
          <strong>{{ paymentExecutionListRows.length }}</strong>
        </article>
        <article>
          <span>当前付款指令准备来源数</span>
          <strong>{{ sourceRows.length }}</strong>
        </article>
        <article>
          <span>当前供应商结算来源候选数</span>
          <strong>{{ supplierSettlementSourceRows.length }}</strong>
        </article>
        <article>
          <span>当前是否需要导入源头数据</span>
          <strong>{{ sourceDataAdvice.needImportSourceData ? '需要' : '不需要' }}</strong>
        </article>
        <article>
          <span>当前是否可以基于来源候选生成最小链路</span>
          <strong>{{ canGenerateFromSupplierSource ? '可以' : '不可以' }}</strong>
        </article>
        <article>
          <span>当前准备层数据是否可清理</span>
          <strong>{{ demoChainDataSummary.canClear ? '可以清理' : '暂无可清理准备层数据' }}</strong>
        </article>
        <article>
          <span>是否已生成最小演示链路</span>
          <strong>{{ currentChainNos.paymentExecutionPrepareNo ? '已生成' : '未生成' }}</strong>
        </article>
        <article>
          <span>最近一次生成的链路单号</span>
          <strong>{{ latestChainNoText }}</strong>
        </article>
      </div>
      <el-alert
        class="source-warning"
        :title="demoChainManagementAdvice"
        :type="sourceDataAdvice.needImportSourceData ? 'warning' : 'success'"
        show-icon
        :closable="false"
      />
      <div v-if="minimumChainResult" class="source-diagnostic-grid chain-result-grid">
        <article>
          <span>供应商结算单号</span>
          <strong>{{ minimumChainResult.settlementNo || '-' }}</strong>
        </article>
        <article>
          <span>采购发票准备单号</span>
          <strong>{{ minimumChainResult.invoicePrepareNo || '-' }}</strong>
        </article>
        <article>
          <span>应付确认准备单号</span>
          <strong>{{ minimumChainResult.payableConfirmNo || '-' }}</strong>
        </article>
        <article>
          <span>付款申请准备单号</span>
          <strong>{{ minimumChainResult.paymentApplicationNo || '-' }}</strong>
        </article>
        <article>
          <span>付款指令准备单号</span>
          <strong>{{ minimumChainResult.paymentOrderPrepareNo || '-' }}</strong>
        </article>
        <article>
          <span>付款执行准备单号</span>
          <strong>{{ minimumChainResult.paymentExecutionPrepareNo || '-' }}</strong>
        </article>
      </div>
      <div class="toolbar-buttons demo-chain-actions">
        <el-button
          type="success"
          :disabled="!canGenerateFromSupplierSource"
          :loading="minimumChainGenerating"
          @click="generateMinimumValidationChain"
        >
          基于现有来源生成最小验证链路
        </el-button>
        <el-button
          type="danger"
          plain
          :disabled="!demoChainDataSummary.canClear"
          @click="clearDemoPrepareLayerData"
        >
          清理准备层演示数据
        </el-button>
      </div>
    </section>

        </el-collapse-item>
      </el-collapse>
    </section>

    <section class="table-card formal-entry-card">
      <div class="table-title">
        <div>
          <h2>付款执行正式入口设计</h2>
          <p class="helper-text">本区域只设计正式付款执行入口的最终保护层和预览能力。当前版本未开启真实付款执行，任何按钮均不会触发真实付款。</p>
        </div>
        <span>真实付款功能是否开启：否</span>
      </div>
      <el-alert
        title="当前版本未开启真实付款执行。正式付款执行能力将在后续版本单独开发；本轮任何按钮均不会触发真实付款。"
        type="warning"
        show-icon
        :closable="false"
        class="source-warning"
      />
      <el-table :data="filteredRows" border stripe class="global-sort-arrow">
        <el-table-column prop="paymentExecutionPrepareNo" label="付款执行准备单号" min-width="180" />
        <el-table-column label="执行前检查" min-width="140">
          <template #default="{ row }">{{ preExecutionCheckStatusLabel(row.preExecutionCheckStatus) }}</template>
        </el-table-column>
        <el-table-column label="执行模拟状态" min-width="150">
          <template #default="{ row }">{{ paymentExecutionSimulationStatusLabel(row.paymentExecutionSimulationStatus) }}</template>
        </el-table-column>
        <el-table-column label="正式入口状态" min-width="150">
          <template #default="{ row }">{{ formalExecutionEntryStatusLabel(row.formalExecutionEntryStatus) }}</template>
        </el-table-column>
        <el-table-column label="是否允许入口预览" min-width="150">
          <template #default="{ row }">{{ row.formalExecutionEntryReady ? '允许预览' : '不允许' }}</template>
        </el-table-column>
        <el-table-column label="阻断原因" min-width="260">
          <template #default="{ row }">{{ listText(row.formalExecutionEntryBlockReasons) || '-' }}</template>
        </el-table-column>
        <el-table-column label="警告信息" min-width="220">
          <template #default="{ row }">{{ listText(row.formalExecutionEntryWarnings) || '-' }}</template>
        </el-table-column>
        <el-table-column label="真实付款功能" min-width="140">
          <template #default="{ row }">{{ row.actualPaymentExecutionEnabled ? '已开启' : '否' }}</template>
        </el-table-column>
        <el-table-column label="当前保护结论" min-width="340">
          <template #default="{ row }">
            真实付款：否 / 银行流水：{{ statusLabel(row.bankFlowStatus) }} / 付款凭证：{{ statusLabel(row.paymentVoucherStatus) }} / 核销：{{ statusLabel(row.writeOffStatus) }} / 总账：{{ statusLabel(row.ledgerStatus) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" min-width="250" fixed="right">
          <template #default="{ row }">
            <div class="row-actions">
              <el-button size="small" type="primary" plain @click="runFormalEntryCheck(row)">运行正式入口检查</el-button>
              <el-button size="small" type="success" plain :disabled="!row.formalExecutionEntryReady" @click="openFormalEntryPreview(row)">
                {{ row.formalExecutionEntryBlocked ? '正式付款入口预览被阻断' : '正式付款执行入口预览' }}
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <section class="table-card final-review-card">
      <div class="table-title">
        <div>
          <h2>真实付款前最终评审</h2>
          <p class="helper-text">本区域用于确认未来开发真实付款功能前的必要条件、风险边界、数据依赖和后续影响。本轮仍不执行付款。</p>
        </div>
        <span>真实付款功能是否开启：否</span>
      </div>
      <el-alert
        title="最终评审结论：不建议下一版本直接执行真实付款。建议先完成真实付款状态机、银行流水边界、付款凭证准备、核销前置和总账写入前置设计。"
        type="warning"
        show-icon
        :closable="false"
        class="source-warning"
      />
      <div class="final-review-conclusion">
        <strong>当前不建议直接付款。</strong>
        <span>真实付款功能仍未开启；当前仅完成付款前评审，不执行付款。</span>
      </div>
      <div class="final-review-focus-grid">
        <article>
          <h3>真实付款后续影响</h3>
          <p>真实付款后可能影响付款执行状态、银行流水、付款凭证、正式付款凭证、核销、总账、供应商账龄、资金预测、P2P 验证中心和业务追踪链路。</p>
          <strong>本轮不触发以上影响。</strong>
        </article>
        <article>
          <h3>风险清单</h3>
          <p>必须关注误付款、重复付款、收款方错误、收款银行账户错误、付款金额错误、未审批付款、银行流水重复生成、未核销、总账重复写入等风险。</p>
          <strong>本轮只评审风险，不执行付款。</strong>
        </article>
        <article>
          <h3>演示数据不能用于真实付款</h3>
          <p>当前链路是开发阶段演示数据，不能作为真实付款依据；正式付款前必须接入正式数据库、权限、审计和付款安全机制。</p>
          <strong>演示数据不可用于真实付款。</strong>
        </article>
      </div>
      <div class="source-diagnostic-grid">
        <article>
          <span>评审状态</span>
          <strong>{{ finalPaymentExecutionReviewSummary.reviewReady ? '评审已形成' : '待评审' }}</strong>
        </article>
        <article>
          <span>当前付款执行准备对象</span>
          <strong>{{ finalPaymentExecutionReviewSummary.reviewItems.hasPaymentExecutionPrepare ? '已存在' : '不存在' }}</strong>
        </article>
        <article>
          <span>安全检查</span>
          <strong>{{ finalPaymentExecutionReviewSummary.reviewItems.preExecutionChecked ? '已完成' : '未完成' }}</strong>
        </article>
        <article>
          <span>付款执行模拟</span>
          <strong>{{ finalPaymentExecutionReviewSummary.reviewItems.simulationCompleted ? '已完成' : '未完成' }}</strong>
        </article>
        <article>
          <span>正式入口预览</span>
          <strong>{{ finalPaymentExecutionReviewSummary.reviewItems.formalPreviewOpened ? '已确认预览' : (finalPaymentExecutionReviewSummary.reviewItems.formalPreviewReady ? '可预览' : '不可预览') }}</strong>
        </article>
        <article>
          <span>真实付款功能</span>
          <strong>{{ finalPaymentExecutionReviewSummary.actualPaymentStillDisabled ? '仍关闭' : '已开启' }}</strong>
        </article>
        <article>
          <span>是否建议直接付款</span>
          <strong>{{ finalPaymentExecutionReviewSummary.recommendDirectPayment ? '是' : '否' }}</strong>
        </article>
        <article>
          <span>是否建议进入真实付款开发</span>
          <strong>{{ finalPaymentExecutionReviewSummary.canStartRealPaymentDevelopment ? '可进入前置设计评估' : '暂不建议' }}</strong>
        </article>
      </div>
      <div class="review-panel-grid">
        <article>
          <h3>最终评审结论</h3>
          <ul>
            <li>当前不建议直接付款。</li>
            <li>真实付款功能仍未开启。</li>
            <li>当前仅完成付款前最终评审，不执行付款。</li>
            <li>仍未生成银行流水、付款凭证、正式付款凭证，仍未核销、未写总账。</li>
          </ul>
        </article>
        <article>
          <h3>真实付款前置条件</h3>
          <ul>
            <li v-for="item in finalPaymentExecutionReviewSummary.prerequisiteItems" :key="item">{{ item }}</li>
          </ul>
        </article>
        <article>
          <h3>真实付款后续影响</h3>
          <ul>
            <li v-for="item in finalPaymentExecutionReviewSummary.futureImpactItems" :key="item">{{ item }}</li>
          </ul>
        </article>
        <article>
          <h3>风险清单</h3>
          <ul>
            <li v-for="item in finalPaymentExecutionReviewSummary.riskItems" :key="item">{{ item }}</li>
          </ul>
        </article>
        <article>
          <h3>演示数据边界</h3>
          <div class="demo-chain-nos">
            <span>供应商结算单号：{{ finalPaymentExecutionReviewSummary.demoChainNos.settlementNo }}</span>
            <span>采购发票准备单号：{{ finalPaymentExecutionReviewSummary.demoChainNos.invoicePrepareNo }}</span>
            <span>应付确认准备单号：{{ finalPaymentExecutionReviewSummary.demoChainNos.payableConfirmNo }}</span>
            <span>付款申请准备单号：{{ finalPaymentExecutionReviewSummary.demoChainNos.paymentApplicationNo }}</span>
            <span>付款指令准备单号：{{ finalPaymentExecutionReviewSummary.demoChainNos.paymentOrderPrepareNo }}</span>
            <span>付款执行准备单号：{{ finalPaymentExecutionReviewSummary.demoChainNos.paymentExecutionPrepareNo }}</span>
          </div>
          <ul>
            <li v-for="item in finalPaymentExecutionReviewSummary.demoDataBoundaryItems" :key="item">{{ item }}</li>
          </ul>
        </article>
      </div>
    </section>

    <section class="table-card state-impact-card">
      <div class="table-title">
        <div>
          <h2>真实付款状态影响设计</h2>
          <p class="helper-text">本区域只设计未来真实付款发生后的状态影响和后续模块边界。本轮不执行真实付款，不生成银行流水、付款凭证、正式付款凭证，不核销、不写总账、不过账。</p>
        </div>
        <span>本轮是否真实付款：否</span>
      </div>
      <el-alert
        title="当前结论：本轮不执行真实付款，只预览未来真实付款后的状态影响；当前付款执行状态仍为未执行，真实付款功能仍未开启。"
        type="warning"
        show-icon
        :closable="false"
        class="source-warning"
      />
      <div class="source-diagnostic-grid">
        <article>
          <span>状态影响设计状态</span>
          <strong>{{ realPaymentStateImpactDesignSummary.impactDesignStatus }}</strong>
        </article>
        <article>
          <span>当前付款执行状态</span>
          <strong>未执行</strong>
        </article>
        <article>
          <span>真实付款功能</span>
          <strong>仍未开启</strong>
        </article>
        <article>
          <span>本轮是否变更真实状态</span>
          <strong>否</strong>
        </article>
      </div>
      <div class="state-impact-grid">
        <article v-for="item in realPaymentStateImpactDesignSummary.stateTransitionItems" :key="item.key">
          <h3>{{ item.name }}</h3>
          <p><span>当前状态：</span>{{ item.currentStatus }}</p>
          <p><span>未来可能状态：</span>{{ item.futureStatus }}</p>
          <strong>本轮是否变更：{{ item.changedThisRound ? '是' : '否' }}</strong>
        </article>
      </div>
      <div class="review-panel-grid state-impact-panels">
        <article>
          <h3>后续模块边界清单</h3>
          <ul>
            <li v-for="item in realPaymentStateImpactDesignSummary.downstreamModuleItems" :key="item.module">
              {{ item.module }}：{{ item.futureImpact }}；本轮是否写入：{{ item.writeThisRound ? '是' : '否' }}
            </li>
          </ul>
        </article>
        <article>
          <h3>正确状态推进链路</h3>
          <ol>
            <li v-for="item in realPaymentStateImpactDesignSummary.stateFlow" :key="item">{{ item }}</li>
          </ol>
          <p class="helper-text">本轮只设计这条链路，不执行这条链路。</p>
        </article>
        <article>
          <h3>禁止自动推进事项</h3>
          <ul>
            <li v-for="item in realPaymentStateImpactDesignSummary.blockedAutoActions" :key="item">{{ item }}</li>
          </ul>
        </article>
      </div>
    </section>

    <section class="table-card bank-flow-boundary-card">
      <div class="table-title">
        <div>
          <h2>银行流水生成 / 导入边界设计</h2>
          <p class="helper-text">
            本区域只设计未来真实付款后银行流水进入系统的来源方式、状态边界、匹配规则、异常场景和后续模块影响。
            本轮不生成银行流水、不导入银行流水、不关联银行流水、不执行银行流水匹配。
          </p>
        </div>
        <span>银行流水状态：未生成</span>
      </div>
      <el-alert
        title="当前结论：本轮不生成银行流水，不导入银行流水，不关联银行流水；当前银行流水状态仍为未生成，真实付款功能仍未开启。"
        type="warning"
        show-icon
        :closable="false"
        class="source-warning"
      />
      <div class="source-diagnostic-grid">
        <article>
          <span>边界设计状态</span>
          <strong>{{ bankFlowBoundaryDesignSummary.boundaryDesignStatus }}</strong>
        </article>
        <article>
          <span>当前银行流水状态</span>
          <strong>未生成</strong>
        </article>
        <article>
          <span>本轮是否生成银行流水</span>
          <strong>否</strong>
        </article>
        <article>
          <span>本轮是否导入银行流水</span>
          <strong>否</strong>
        </article>
        <article>
          <span>本轮是否关联银行流水</span>
          <strong>否</strong>
        </article>
        <article>
          <span>本轮是否执行银行流水匹配</span>
          <strong>否</strong>
        </article>
      </div>
      <div class="review-panel-grid bank-flow-panels">
        <article>
          <h3>当前保护状态</h3>
          <ul>
            <li>未真实付款。</li>
            <li>未生成银行流水。</li>
            <li>未导入银行流水。</li>
            <li>未关联银行流水。</li>
            <li>未生成付款凭证、未生成正式付款凭证。</li>
            <li>未核销、未写总账、未过账。</li>
          </ul>
        </article>
        <article>
          <h3>银行流水未来状态边界</h3>
          <ul>
            <li v-for="item in bankFlowBoundaryDesignSummary.statusPreviewItems" :key="item.status">
              {{ item.status }}：{{ item.description }}；本轮是否变化：{{ item.changedThisRound ? '是' : '否' }}
            </li>
          </ul>
        </article>
      </div>
      <div class="state-impact-grid bank-flow-source-grid">
        <article v-for="item in bankFlowBoundaryDesignSummary.sourceModeItems" :key="item.mode">
          <h3>{{ item.mode }}</h3>
          <p><span>说明：</span>{{ item.description }}</p>
          <p><span>边界：</span>{{ item.boundary }}</p>
          <strong>本轮是否执行：{{ item.executedThisRound ? '是' : '否' }}</strong>
        </article>
      </div>
      <div class="review-panel-grid bank-flow-panels">
        <article>
          <h3>银行流水与后续模块边界</h3>
          <ul>
            <li v-for="item in bankFlowBoundaryDesignSummary.downstreamBoundaryItems" :key="item.module">
              {{ item.module }}：{{ item.futureImpact }}；本轮是否写入：{{ item.writeThisRound ? '是' : '否' }}
            </li>
          </ul>
        </article>
        <article>
          <h3>银行流水匹配规则设计</h3>
          <ul>
            <li v-for="item in bankFlowBoundaryDesignSummary.matchRuleItems" :key="item">{{ item }}</li>
          </ul>
          <p class="helper-text">本轮只设计匹配规则，不执行匹配、不确认匹配、不核销。</p>
        </article>
        <article>
          <h3>银行流水异常场景</h3>
          <ul>
            <li v-for="item in bankFlowBoundaryDesignSummary.exceptionScenarioItems" :key="item">{{ item }}</li>
          </ul>
          <p class="helper-text">本轮只设计异常场景，不处理真实异常、不生成异常业务单据。</p>
        </article>
        <article>
          <h3>禁止自动推进事项</h3>
          <ul>
            <li v-for="item in bankFlowBoundaryDesignSummary.autoActionBlockedItems" :key="item">{{ item }}</li>
          </ul>
        </article>
        <article>
          <h3>正确边界链路</h3>
          <ol>
            <li v-for="item in bankFlowBoundaryDesignSummary.correctFlowItems" :key="item">{{ item }}</li>
          </ol>
          <p class="helper-text">本轮只设计这条链路，不执行这条链路。</p>
        </article>
      </div>
    </section>

    <section class="table-card bank-flow-object-card">
      <div class="table-title">
        <div>
          <h2>银行流水真实对象与导入校验设计</h2>
          <p class="helper-text">
            本区域只设计未来正式银行流水对象的数据结构、导入文件字段、校验规则、重复拦截、导入后状态和错误提示。
            本轮不新增正式银行流水对象，不新增导入按钮，不导入银行流水文件，不读取 Excel / CSV。
          </p>
        </div>
        <span>真实银行流水对象：未创建</span>
      </div>
      <el-alert
        title="当前结论：本轮不新增正式银行流水对象，不新增银行流水导入按钮，不导入银行流水文件，不读取 Excel / CSV，不创建导入批次。"
        type="warning"
        show-icon
        :closable="false"
        class="source-warning"
      />
      <div class="source-diagnostic-grid">
        <article>
          <span>对象设计状态</span>
          <strong>{{ bankFlowObjectImportDesignSummary.objectDesignStatus }}</strong>
        </article>
        <article>
          <span>本轮是否新增正式银行流水对象</span>
          <strong>否</strong>
        </article>
        <article>
          <span>本轮是否新增导入按钮</span>
          <strong>否</strong>
        </article>
        <article>
          <span>本轮是否导入银行流水文件</span>
          <strong>否</strong>
        </article>
        <article>
          <span>本轮是否读取 Excel / CSV</span>
          <strong>否</strong>
        </article>
        <article>
          <span>本轮是否创建导入批次</span>
          <strong>否</strong>
        </article>
      </div>
      <div class="review-panel-grid bank-flow-object-panels">
        <article>
          <h3>当前保护状态</h3>
          <ul>
            <li>仍未真实付款。</li>
            <li>仍未生成银行流水。</li>
            <li>仍未导入银行流水。</li>
            <li>仍未关联银行流水。</li>
            <li>仍未生成付款凭证、未核销、未写总账。</li>
          </ul>
        </article>
        <article>
          <h3>银行流水真实对象边界</h3>
          <ul>
            <li v-for="item in bankFlowObjectImportDesignSummary.objectBoundaryItems" :key="item">{{ item }}</li>
          </ul>
        </article>
      </div>
      <div class="state-impact-grid bank-flow-object-grid">
        <article v-for="item in bankFlowObjectImportDesignSummary.objectFieldItems" :key="item.field">
          <h3>{{ item.field }}</h3>
          <p><span>字段含义：</span>{{ item.meaning }}</p>
          <p><span>是否必填：</span>{{ item.required }}</p>
          <p><span>来源：</span>{{ item.source }}</p>
          <strong>本轮是否写入真实对象：{{ item.writeThisRound ? '是' : '否' }}</strong>
        </article>
      </div>
      <div class="review-panel-grid bank-flow-object-panels">
        <article>
          <h3>银行流水导入文件字段设计</h3>
          <ul>
            <li v-for="item in bankFlowObjectImportDesignSummary.importTemplateItems" :key="item.column">
              {{ item.column }}：{{ item.required }}；{{ item.validationRule }}；本轮是否导入：{{ item.importedThisRound ? '是' : '否' }}
            </li>
          </ul>
        </article>
        <article>
          <h3>导入校验规则设计</h3>
          <ul>
            <li v-for="item in bankFlowObjectImportDesignSummary.validationRuleItems" :key="item">{{ item }}</li>
          </ul>
          <p class="helper-text">本轮只设计校验规则，不执行导入校验，不读取银行文件。</p>
        </article>
        <article>
          <h3>重复流水拦截规则设计</h3>
          <ul>
            <li v-for="item in bankFlowObjectImportDesignSummary.duplicateBlockRuleItems" :key="item">{{ item }}</li>
          </ul>
          <p class="helper-text">本轮只设计重复拦截，不执行重复判断，不写入重复记录。</p>
        </article>
        <article>
          <h3>导入后状态设计</h3>
          <ol>
            <li v-for="item in bankFlowObjectImportDesignSummary.importStatusFlowItems" :key="item">{{ item }}</li>
          </ol>
          <p class="helper-text">本轮不导入、不校验、不进入待匹配、不自动匹配、不人工确认、不核销。</p>
        </article>
        <article>
          <h3>导入错误提示设计</h3>
          <ul>
            <li v-for="item in bankFlowObjectImportDesignSummary.importErrorItems" :key="item">{{ item }}</li>
          </ul>
          <p class="helper-text">本轮只设计错误提示，不触发真实错误，不生成错误日志。</p>
        </article>
      </div>
    </section>

    <section class="table-card bank-flow-readonly-preview-card">
      <div class="table-title">
        <div>
          <h2>银行流水只读对象与导入校验预览</h2>
          <p class="helper-text">
            本区域只生成只读预览对象、导入校验结果预览、重复拦截预览、导入错误清单预览、导入后状态预览和审计日志预览。
            本轮不新增正式银行流水对象，不上传文件，不读取 Excel / CSV，不创建导入批次。
          </p>
        </div>
        <span>只读预览：已生成</span>
      </div>
      <el-alert
        title="当前结论：本轮只生成只读预览；不新增正式银行流水对象，不新增导入按钮，不上传文件，不读取 Excel / CSV，不进入待匹配，不核销、不写总账。"
        type="warning"
        show-icon
        :closable="false"
        class="source-warning"
      />
      <div class="validation-conclusion-card">
        <h3>本轮统一验收结论</h3>
        <div class="validation-conclusion-grid">
          <span>本轮是否新增正式银行流水对象：<strong>否</strong></span>
          <span>本轮是否新增银行流水导入按钮：<strong>否</strong></span>
          <span>本轮是否上传文件：<strong>否</strong></span>
          <span>本轮是否读取 Excel：<strong>否</strong></span>
          <span>本轮是否读取 CSV：<strong>否</strong></span>
          <span>本轮是否创建导入批次：<strong>否</strong></span>
          <span>本轮是否执行导入校验：<strong>否</strong></span>
          <span>本轮是否执行重复拦截：<strong>否</strong></span>
          <span>本轮是否进入待匹配：<strong>否</strong></span>
          <span>本轮是否自动匹配：<strong>否</strong></span>
          <span>本轮是否人工确认匹配：<strong>否</strong></span>
          <span>本轮是否写正式审计日志：<strong>否</strong></span>
          <span>本轮是否关联付款执行单：<strong>否</strong></span>
          <span>本轮是否核销：<strong>否</strong></span>
          <span>本轮是否写总账：<strong>否</strong></span>
          <span>本轮是否过账：<strong>否</strong></span>
        </div>
      </div>
      <div class="source-diagnostic-grid">
        <article>
          <span>只读预览状态</span>
          <strong>{{ bankFlowReadonlyObjectPreviewSummary.readonlyPreviewStatus }}</strong>
        </article>
        <article>
          <span>本轮是否新增正式银行流水对象</span>
          <strong>否</strong>
        </article>
        <article>
          <span>本轮是否上传文件</span>
          <strong>否</strong>
        </article>
        <article>
          <span>本轮是否读取 Excel / CSV</span>
          <strong>否</strong>
        </article>
        <article>
          <span>本轮是否创建导入批次</span>
          <strong>否</strong>
        </article>
        <article>
          <span>本轮是否进入待匹配</span>
          <strong>否</strong>
        </article>
      </div>
      <div class="review-panel-grid bank-flow-readonly-panels">
        <article>
          <h3>当前结论</h3>
          <ul>
            <li>本轮只生成只读预览。</li>
            <li>本轮不新增正式银行流水对象。</li>
            <li>本轮不新增银行流水导入按钮。</li>
            <li>本轮不上传文件。</li>
            <li>本轮不读取 Excel / CSV。</li>
            <li>本轮不创建导入批次、不进入待匹配、不关联付款执行单。</li>
            <li>本轮不核销、不写总账。</li>
          </ul>
        </article>
        <article>
          <h3>银行流水只读对象预览</h3>
          <ul>
            <li v-for="item in bankFlowReadonlyObjectPreviewSummary.readonlyPreviewObject" :key="item.field">
              {{ item.field }}：{{ item.value }}；本轮是否写入正式银行流水对象：{{ item.writeFormalObjectThisRound ? '是' : '否' }}
            </li>
          </ul>
          <p class="helper-text">本小节统一结论：以上字段仅为只读预览，本轮均不写入正式银行流水对象。</p>
        </article>
      </div>
      <div class="review-panel-grid bank-flow-readonly-panels">
        <article>
          <h3>导入校验结果预览</h3>
          <ul>
            <li v-for="item in bankFlowReadonlyObjectPreviewSummary.validationPreviewItems" :key="item.item">
              {{ item.item }}：{{ item.previewResult }}；本轮是否执行校验：{{ item.executedThisRound ? '是' : '否' }}
            </li>
          </ul>
          <p class="helper-text">本小节统一结论：以上校验项仅为预览，本轮均不执行导入校验。</p>
        </article>
        <article>
          <h3>重复流水拦截预览</h3>
          <ul>
            <li v-for="item in bankFlowReadonlyObjectPreviewSummary.duplicateBlockPreviewItems" :key="item.rule">
              {{ item.rule }}：{{ item.previewResult }}；本轮是否执行拦截：{{ item.executedThisRound ? '是' : '否' }}
            </li>
          </ul>
          <p class="helper-text">本小节统一结论：以上拦截规则仅为预览，本轮均不执行重复拦截。</p>
        </article>
        <article>
          <h3>导入错误清单预览</h3>
          <ul>
            <li v-for="item in bankFlowReadonlyObjectPreviewSummary.errorPreviewItems" :key="item.errorType">
              {{ item.errorType }}：当前是否触发：{{ item.triggeredThisRound ? '是' : '否' }}；原因：{{ item.reason }}
            </li>
          </ul>
          <p class="helper-text">本小节统一结论：以上错误类型仅为预览，本轮均未触发真实错误。</p>
        </article>
        <article>
          <h3>导入后状态预览</h3>
          <ol>
            <li v-for="item in bankFlowReadonlyObjectPreviewSummary.importStatusPreviewItems" :key="item.status">
              {{ item.status }}：{{ item.description }}；本轮是否进入该状态：{{ item.enteredThisRound ? '是' : '否' }}
            </li>
          </ol>
          <p class="helper-text">本小节统一结论：以上状态仅为未来状态预览，本轮均不进入任何导入后状态。</p>
        </article>
        <article>
          <h3>审计日志预览</h3>
          <ul>
            <li v-for="item in bankFlowReadonlyObjectPreviewSummary.auditLogPreviewItems" :key="item">
              {{ item }}；本轮是否写入审计日志：否
            </li>
          </ul>
          <p class="helper-text">本小节统一结论：以上审计项仅为设计预览，本轮均不写正式审计日志。</p>
        </article>
      </div>
    </section>

    <section id="payment-execution-source-calibration-section" class="table-card" data-acceptance-id="payment-execution-source-calibration-section">
      <div class="table-title">
        <h2>付款指令准备来源校准</h2>
        <span>来源 {{ sourceRows.length }} 条 / 可生成 {{ readySourceRows.length }} 条 / 已签发 {{ issuedSourceRows.length }} 条</span>
      </div>
      <p class="helper-text">
        本区域直接读取付款指令准备来源，用于校准用户端真实数据可见性。若存在已复核、可签发的来源，可在此生成付款执行准备；若已生成，则只显示关联单号。
        本表是来源校准表，不是付款执行准备主业务列表；付款执行准备数量、当前结果和执行准备金额只以下方“付款执行准备列表”为准。
      </p>
      <el-alert
        v-if="paymentExecutionListRows.length"
        class="source-warning"
        :title="sourceDataAdvice.message"
        type="success"
        show-icon
        :closable="false"
      />
      <div class="source-diagnostic-grid">
        <article>
          <span>读取模块名称</span>
          <strong>{{ sourceDiagnostics.sourceStoreName }}</strong>
        </article>
        <article>
          <span>本地存储 key</span>
          <strong>{{ sourceDiagnostics.sourceLocalStorageKey }}</strong>
        </article>
        <article>
          <span>付款指令准备来源数</span>
          <strong>{{ sourceDiagnostics.sourcePaymentOrderPrepareCount }}</strong>
        </article>
        <article>
          <span>可签发付款指令数</span>
          <strong>{{ sourceDiagnostics.readyToIssueCount }}</strong>
        </article>
        <article>
          <span>已签发到执行准备数</span>
          <strong>{{ sourceDiagnostics.issuedForExecutionCount }}</strong>
        </article>
        <article>
          <span>已生成执行准备</span>
          <strong>{{ sourceDiagnostics.generatedExecutionPrepareCount }}</strong>
        </article>
        <article>
          <span>可生成付款执行准备数</span>
          <strong>{{ readySourceRows.length }}</strong>
        </article>
        <article>
          <span>来源样本单号</span>
          <strong>{{ sourceDiagnostics.sourceSampleNos.join('、') || '-' }}</strong>
        </article>
      </div>
      <el-alert
        v-if="sourceDiagnostics.sourceReadWarnings.length"
        class="source-warning"
        :title="sourceDiagnostics.sourceReadWarnings.join('；')"
        type="warning"
        show-icon
        :closable="false"
      />
      <section v-if="minimumChainGuideVisible" class="minimum-chain-guide">
        <div class="guide-heading">
          <div>
            <h3>用户端最小链路重跑向导</h3>
            <p>当前浏览器没有足够的付款指令准备来源数据时，请按下面步骤在同一浏览器会话中重新跑一条最小链路。</p>
          </div>
          <el-tag type="warning">只生成准备对象，不真实付款</el-tag>
        </div>
        <div class="guide-warning">
          {{ sourceDataAdvice.message }}
        </div>
        <div class="source-diagnostic-grid">
          <article>
            <span>当前不能生成原因</span>
            <strong>{{ cannotGenerateReason }}</strong>
          </article>
          <article>
            <span>下一步操作建议</span>
            <strong>{{ nextOperationAdvice }}</strong>
          </article>
          <article>
            <span>是否需要导入源头数据</span>
            <strong>{{ sourceDataAdvice.needImportSourceData ? '需要先导入或生成源头演示数据' : '当前不需要导入源头数据' }}</strong>
          </article>
          <article>
            <span>源头数据建议操作</span>
            <strong>{{ sourceDataAdvice.action }}</strong>
          </article>
        </div>
        <ol class="minimum-chain-steps">
          <li v-for="step in minimumChainGuideSteps" :key="step.title">
            <strong>{{ step.title }}</strong>
            <span>{{ step.description }}</span>
            <a :href="step.url">{{ step.url }}</a>
          </li>
        </ol>
        <p class="helper-text">
          当当前浏览器没有付款指令准备来源，但存在供应商结算来源候选时，可基于现有来源生成一条本地最小验证链路。
          本操作不凭空造采购订单、收货、检验或库存流水，也不会生成实际付款、银行流水、付款凭证、正式付款凭证、核销或总账。
        </p>
        <div v-if="minimumChainAutoGenerateVisible" class="minimum-chain-action">
          <el-button type="success" :loading="minimumChainGenerating" @click="generateMinimumValidationChain">
            基于现有来源生成最小验证链路
          </el-button>
          <span>
            当前浏览器没有付款指令准备来源，但存在供应商结算来源候选。可基于现有来源候选生成一条本地最小验证链路，用于验证供应商结算到付款执行准备的页面衔接。
          </span>
        </div>
      </section>
      <section v-if="minimumChainResult" class="minimum-chain-result">
        <h3>最小验证链路生成结果</h3>
        <div class="source-diagnostic-grid">
          <article>
            <span>供应商结算单号</span>
            <strong>{{ minimumChainResult.settlementNo || '-' }}</strong>
          </article>
          <article>
            <span>采购发票准备单号</span>
            <strong>{{ minimumChainResult.invoicePrepareNo || '-' }}</strong>
          </article>
          <article>
            <span>应付确认准备单号</span>
            <strong>{{ minimumChainResult.payableConfirmNo || '-' }}</strong>
          </article>
          <article>
            <span>付款申请准备单号</span>
            <strong>{{ minimumChainResult.paymentApplicationNo || '-' }}</strong>
          </article>
          <article>
            <span>付款指令准备单号</span>
            <strong>{{ minimumChainResult.paymentOrderPrepareNo || '-' }}</strong>
          </article>
          <article>
            <span>付款执行准备单号</span>
            <strong>{{ minimumChainResult.paymentExecutionPrepareNo || '-' }}</strong>
          </article>
        </div>
        <p class="helper-text">
          本结果只代表准备对象链路已生成；付款执行准备不是付款，已复核不代表已付款，已签发不代表已付款。
        </p>
      </section>
      <el-table :data="visibleSourceRows" border stripe class="global-sort-arrow source-table">
        <el-table-column prop="paymentOrderPrepareNo" label="付款指令准备单号" min-width="180" />
        <el-table-column prop="sourcePaymentApplicationNo" label="来源付款申请单号" min-width="170" />
        <el-table-column prop="supplierName" label="供应商" min-width="140" />
        <el-table-column prop="purchaseOrderNo" label="采购订单号" min-width="150" />
        <el-table-column prop="orderAmount" label="指令金额" min-width="120">
          <template #default="{ row }">{{ formatAmount(row.orderAmount) }}</template>
        </el-table-column>
        <el-table-column prop="paymentOrderStatus" label="付款指令准备状态" min-width="150">
          <template #default="{ row }">{{ sourcePaymentOrderStatusLabel(row.paymentOrderStatus) }}</template>
        </el-table-column>
        <el-table-column prop="paymentInstructionStatus" label="指令状态" min-width="140">
          <template #default="{ row }">{{ sourcePaymentInstructionStatusLabel(row.paymentInstructionStatus) }}</template>
        </el-table-column>
        <el-table-column prop="linkedPaymentExecutionPrepareNo" label="关联付款执行准备单号（来源校准）" min-width="220">
          <template #default="{ row }">{{ row.linkedPaymentExecutionPrepareNo || '-' }}</template>
        </el-table-column>
        <el-table-column label="来源状态" min-width="160">
          <template #default="{ row }">
            <el-tag :type="row.canCreatePaymentExecutionPrepare ? 'success' : row.paymentExecutionPrepareGenerated ? 'warning' : 'info'">
              {{ row.paymentExecutionPrepareGenerated ? '已生成付款执行准备' : row.canCreatePaymentExecutionPrepare ? '可生成付款执行准备' : row.paymentExecutionPrepareBlockReason || '不可生成' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" min-width="190" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.canCreatePaymentExecutionPrepare"
              size="small"
              type="success"
              plain
              @click="generateFromSource(row)"
            >
              生成付款执行准备
            </el-button>
            <span v-else>{{ row.paymentExecutionPrepareGenerated ? '查看下方列表' : row.paymentExecutionPrepareBlockReason || '-' }}</span>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <section class="table-card pre-execution-card">
      <div class="table-title">
        <div>
          <h2>付款执行前安全检查</h2>
          <p class="helper-text">本区域只检查付款执行入口是否具备预览条件，不执行付款、不生成银行流水、不生成付款凭证、不生成正式付款凭证、不核销、不写总账。</p>
        </div>
        <el-button type="primary" plain @click="runCurrentResultPreExecutionChecks">运行当前结果安全检查</el-button>
      </div>
      <div class="source-diagnostic-grid">
        <article>
          <span>已检查</span>
          <strong>{{ preExecutionCheckSummary.checkedCount }}</strong>
        </article>
        <article>
          <span>允许进入执行入口</span>
          <strong>{{ preExecutionCheckSummary.readyCount }}</strong>
        </article>
        <article>
          <span>被阻断</span>
          <strong>{{ preExecutionCheckSummary.blockedCount }}</strong>
        </article>
        <article>
          <span>提醒项</span>
          <strong>{{ preExecutionCheckSummary.warningCount }}</strong>
        </article>
      </div>
      <el-table :data="preExecutionCheckRows" border stripe class="global-sort-arrow">
        <el-table-column prop="paymentExecutionPrepareNo" label="付款执行准备单号" min-width="180" />
        <el-table-column prop="sourcePaymentOrderPrepareNo" label="来源付款指令" min-width="180" />
        <el-table-column prop="sourcePaymentApplicationNo" label="来源付款申请" min-width="180" />
        <el-table-column prop="supplierName" label="供应商" min-width="150" />
        <el-table-column label="金额" min-width="120">
          <template #default="{ row }">{{ formatAmount(row.executionAmount) }}</template>
        </el-table-column>
        <el-table-column label="方式" min-width="120">
          <template #default="{ row }">{{ paymentMethodLabel(row.paymentMethod) }}</template>
        </el-table-column>
        <el-table-column label="准备状态" min-width="120">
          <template #default="{ row }">{{ prepareStatusLabel(row.paymentExecutionPrepareStatus) }}</template>
        </el-table-column>
        <el-table-column label="执行状态" min-width="120">
          <template #default="{ row }">{{ statusLabel(row.paymentExecutionStatus) }}</template>
        </el-table-column>
        <el-table-column label="银行流水" min-width="120">
          <template #default="{ row }">{{ statusLabel(row.bankFlowStatus) }}</template>
        </el-table-column>
        <el-table-column label="付款凭证" min-width="120">
          <template #default="{ row }">{{ statusLabel(row.paymentVoucherStatus) }}</template>
        </el-table-column>
        <el-table-column label="正式付款凭证" min-width="140">
          <template #default="{ row }">{{ statusLabel(row.formalPaymentVoucherStatus) }}</template>
        </el-table-column>
        <el-table-column label="核销/总账/过账" min-width="220">
          <template #default="{ row }">{{ statusLabel(row.writeOffStatus) }} / {{ statusLabel(row.ledgerStatus) }} / {{ statusLabel(row.postingStatus) }}</template>
        </el-table-column>
        <el-table-column label="检查状态" min-width="130">
          <template #default="{ row }">{{ preExecutionCheckStatusLabel(row.preExecutionCheckStatus) }}</template>
        </el-table-column>
        <el-table-column label="风险状态" min-width="130">
          <template #default="{ row }">{{ preExecutionRiskStatusLabel(row.preExecutionRiskStatus) }}</template>
        </el-table-column>
        <el-table-column label="是否允许入口" min-width="130">
          <template #default="{ row }">{{ row.preExecutionReady ? '允许预览' : '不允许' }}</template>
        </el-table-column>
        <el-table-column label="阻断原因 / 警告" min-width="280">
          <template #default="{ row }">{{ listText(row.preExecutionBlockReasons) || listText(row.preExecutionWarnings) || '-' }}</template>
        </el-table-column>
        <el-table-column label="操作" min-width="220" fixed="right">
          <template #default="{ row }">
            <div class="row-actions">
              <el-button size="small" type="primary" plain @click="runPreExecutionCheck(row)">运行安全检查</el-button>
              <el-button size="small" type="success" plain :disabled="!row.preExecutionReady" @click="openEntryPreview(row)">
                {{ row.preExecutionBlocked ? '付款执行被阻断' : '付款执行入口预览' }}
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <section class="table-card simulation-card">
      <div class="table-title">
        <div>
          <h2>付款执行模拟结果</h2>
          <p class="helper-text">本区域只模拟付款执行状态流向。模拟通过不代表已付款，不生成银行流水、付款凭证、正式付款凭证，不核销、不写总账、不改变真实付款执行状态。</p>
        </div>
        <span>已模拟：{{ paymentExecutionSimulationSummary.simulationCount }} 条 / 模拟通过：{{ paymentExecutionSimulationSummary.simulatedReadyCount }} 条</span>
      </div>
      <el-table :data="filteredRows" border stripe class="global-sort-arrow">
        <el-table-column prop="paymentExecutionPrepareNo" label="付款执行准备单号" min-width="180" />
        <el-table-column label="模拟状态" min-width="140">
          <template #default="{ row }">{{ paymentExecutionSimulationStatusLabel(row.paymentExecutionSimulationStatus) }}</template>
        </el-table-column>
        <el-table-column label="是否已模拟" min-width="120">
          <template #default="{ row }">{{ row.paymentExecutionSimulated ? '已模拟' : '未模拟' }}</template>
        </el-table-column>
        <el-table-column prop="paymentExecutionSimulatedAt" label="模拟时间" min-width="180" />
        <el-table-column prop="paymentExecutionSimulatedBy" label="模拟操作人" min-width="140" />
        <el-table-column label="模拟结果" min-width="260">
          <template #default="{ row }">{{ row.paymentExecutionSimulationResult || '-' }}</template>
        </el-table-column>
        <el-table-column label="模拟警告" min-width="220">
          <template #default="{ row }">{{ listText(row.paymentExecutionSimulationWarnings) || '-' }}</template>
        </el-table-column>
        <el-table-column label="模拟阻断原因" min-width="240">
          <template #default="{ row }">{{ listText(row.paymentExecutionSimulationBlockReasons) || '-' }}</template>
        </el-table-column>
        <el-table-column label="真实状态保护" min-width="320">
          <template #default="{ row }">
            付款：{{ statusLabel(row.paymentExecutionStatus) }} / 银行流水：{{ statusLabel(row.bankFlowStatus) }} / 付款凭证：{{ statusLabel(row.paymentVoucherStatus) }} / 核销：{{ statusLabel(row.writeOffStatus) }} / 总账：{{ statusLabel(row.ledgerStatus) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" min-width="180" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" plain :disabled="!canRunPaymentExecutionSimulation(row)" @click="confirmRunPaymentExecutionSimulation(row)">
              模拟付款执行
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <section id="payment-execution-prepare-list-section" class="table-card" data-acceptance-id="payment-execution-prepare-list-section">
      <div class="table-title">
        <h2 data-acceptance-id="page-internal-subject-title">{{ pageName.pageTitle }}</h2>
        <span data-acceptance-id="business-flow-selected-count">当前结果：{{ filteredRows.length }} 条 / 全部付款执行准备：{{ paymentExecutionListRows.length }} 条 / 已选择 {{ selectedRows.length }} 条</span>
      </div>
      <StandardListToolbar
        page-id="payment-execution-prepare"
        table-id="payment-execution-prepare-list"
        v-model:quick-search="quickSearch"
        :advanced-visible="advancedFilterVisible"
        :result-count="filteredRows.length"
        :selected-count="selectedRows.length"
        :active-filter-count="activeFilterCount"
        :sort-text="currentSortText"
        :export-disabled="filteredRows.length === 0"
        @search="clearSelection"
        @toggle-advanced="advancedFilterVisible = !advancedFilterVisible"
        @clear-filters="clearFilters"
        @clear-sort="clearSort"
        @export-current="exportCurrentResults"
        @clear-selection="clearSelection"
      >
        <template #batch-action>
          <span>当前合法批量操作：需逐条完成执行前复核</span>
        </template>
      </StandardListToolbar>
      <div v-show="advancedFilterVisible" class="filter-grid advanced-filter-panel" data-acceptance-id="list-advanced-filter-panel" data-pce-filter-for="payment-execution-prepare-list">
        <PceResultFilterSelect v-model="filterState.paymentExecutionPrepareNo" :rows="paymentExecutionListRows" :fields="['paymentExecutionPrepareNo']" />
        <PceResultFilterSelect v-model="filterState.sourcePaymentOrderPrepareNo" :rows="paymentExecutionListRows" :fields="['sourcePaymentOrderPrepareNo']" />
        <PceResultFilterSelect v-model="filterState.sourcePaymentApplicationNo" :rows="paymentExecutionListRows" :fields="['sourcePaymentApplicationNo']" />
        <PceResultFilterSelect v-model="filterState.sourcePayableConfirmNo" :rows="paymentExecutionListRows" :fields="['sourcePayableConfirmNo']" />
        <PceResultFilterSelect v-model="filterState.supplier" :rows="paymentExecutionListRows" :fields="['supplier']" />
        <PceResultFilterSelect v-model="filterState.purchaseOrderNo" :rows="paymentExecutionListRows" :fields="['purchaseOrderNo']" />
        <PceResultFilterSelect v-model="filterState.invoiceNo" :rows="paymentExecutionListRows" :fields="['invoiceNo']" />
        <el-select v-model="filterState.paymentExecutionPrepareStatus" clearable placeholder="执行准备状态">
          <el-option v-for="item in prepareStatusOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <el-select v-model="filterState.paymentExecutionStatus" clearable placeholder="执行状态">
          <el-option label="未执行" value="not_executed" />
        </el-select>
        <el-date-picker v-model="filterState.dateRange" type="daterange" start-placeholder="开始日期" end-placeholder="结束日期" value-format="YYYY-MM-DD" />
      </div>
      <el-alert
        v-if="consistencyWarning"
        class="source-warning"
        :title="consistencyWarning"
        type="error"
        show-icon
        :closable="false"
      />
      <el-empty
        v-if="!filteredRows.length"
        description="当前浏览器还没有付款执行准备真实记录。请先按上方最小链路重跑向导生成准备对象。"
      />
      <BusinessTableScrollContainer class="pce-baseline-table-shell payment-execution-table-shell" acceptance-id="business-table-scroll-payment-execution-prepare-list" page-id="payment-execution-prepare" table-id="payment-execution-prepare-list">
      <el-table ref="paymentExecutionPrepareTableRef" :data="filteredRows" border stripe height="560" class="global-sort-arrow payment-execution-prepare-main-table" @selection-change="handleSelectionChange">
        <el-table-column
          type="selection"
          width="48"
          fixed="left"
          class-name="payment-fixed-selection-column"
          label-class-name="payment-fixed-selection-column"
          header-class-name="payment-fixed-selection-column"
        />
        <el-table-column type="index" label="序号" width="64" fixed="left" class-name="payment-fixed-index-column" label-class-name="payment-fixed-index-column" header-class-name="payment-fixed-index-column" />
        <el-table-column label="付款执行准备编号" min-width="190" fixed="left" class-name="payment-fixed-no-column" label-class-name="payment-fixed-no-column">
          <template #default="{ row }">{{ row.paymentExecutionPrepareNo || '-' }}</template>
        </el-table-column>
        <el-table-column label="目标对象编号" min-width="180">
          <template #default="{ row }">{{ row.linkedPaymentVoucherPrepareNo || row.paymentVoucherPrepareNo || '未发现目标对象' }}</template>
        </el-table-column>
        <el-table-column label="当前执行状态" min-width="160">
          <template #default="{ row }">{{ statusLabel(row.paymentExecutionStatus) }}</template>
        </el-table-column>
        <el-table-column v-for="column in scrollableTableColumns" :key="column.key" :prop="column.key" :min-width="column.width">
          <template #header>
            <button class="sortable-header" type="button" @click="toggleSort(column.key)">{{ column.label }} {{ sortMark(column.key) }}</button>
          </template>
          <template #default="{ row }">
            <el-tag v-if="column.key === 'paymentExecutionPrepareStatus'" :type="prepareStatusType(row.paymentExecutionPrepareStatus)">
              {{ prepareStatusLabel(row.paymentExecutionPrepareStatus) }}
            </el-tag>
            <span v-else>{{ formatCell(row, column.key) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" fixed="right" width="760" class-name="payment-fixed-action-column" header-class-name="payment-fixed-action-column" label-class-name="payment-fixed-action-column">
          <template #default="{ row }">
            <div class="row-actions">
              <el-button
                size="small"
                type="primary"
                plain
                :disabled="!row.paymentExecutionPrepareNo"
                data-acceptance-id="payment-voucher-prepare-preview-action"
                @click="openPaymentVoucherPreparePreview(row)"
              >
                查看付款凭证准备预览
              </el-button>
              <el-button size="small" @click="router.push('/finance/payment-order-prepares')">查看来源付款指令</el-button>
              <el-button size="small" plain @click="router.push('/finance/payment-applications')">查看来源付款申请</el-button>
              <el-button size="small" type="primary" plain @click="recalculate(row)">重算金额</el-button>
              <el-button size="small" @click="openEdit(row)">编辑准备信息</el-button>
              <el-button size="small" type="warning" plain @click="markWaiting(row)">标记待复核</el-button>
              <el-button size="small" type="success" @click="review(row)">执行准备复核通过</el-button>
              <el-button size="small" type="primary" plain @click="runPreExecutionCheck(row)">运行安全检查</el-button>
              <el-button size="small" type="success" plain :disabled="!row.preExecutionReady" @click="openEntryPreview(row)">
                {{ row.preExecutionBlocked ? '付款执行被阻断' : '付款执行入口预览' }}
              </el-button>
              <el-button size="small" type="primary" plain :disabled="!canRunPaymentExecutionSimulation(row)" @click="confirmRunPaymentExecutionSimulation(row)">模拟付款执行</el-button>
              <el-button size="small" type="primary" plain @click="runFormalEntryCheck(row)">正式入口检查</el-button>
              <el-button size="small" type="success" plain :disabled="!row.formalExecutionEntryReady" @click="openFormalEntryPreview(row)">
                {{ row.formalExecutionEntryBlocked ? '正式付款入口预览被阻断' : '正式付款执行入口预览' }}
              </el-button>
              <el-button
                size="small"
                type="primary"
                plain
                :disabled="!row.paymentExecutionPrepareNo"
                @click="openBankFlowImportValidationPreview(row)"
              >
                查看银行流水导入校验预览
              </el-button>
              <span v-if="!row.paymentExecutionPrepareNo" class="row-missing-tip">
                当前记录缺少付款执行准备单号，无法打开银行流水导入校验预览。
              </span>
              <el-button size="small" type="danger" plain @click="block(row)">阻断</el-button>
              <el-button size="small" type="info" @click="close(row)">关闭</el-button>
              <el-button size="small" plain @click="viewLogs(row)">日志</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
      </BusinessTableScrollContainer>
    </section>

    <el-dialog v-model="editVisible" title="编辑付款执行准备" width="660px">
      <el-form label-width="140px">
        <el-form-item label="执行准备金额">
          <el-input-number v-model="editForm.executionAmount" :precision="2" :min="0" />
        </el-form-item>
        <el-form-item label="付款方式">
          <el-select v-model="editForm.paymentMethod">
            <el-option label="银行转账" value="bank_transfer" />
            <el-option label="承兑汇票" value="bank_acceptance" />
            <el-option label="现金" value="cash" />
          </el-select>
        </el-form-item>
        <el-form-item label="计划付款日期">
          <el-date-picker v-model="editForm.plannedPaymentDate" type="date" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item label="付款优先级">
          <el-select v-model="editForm.paymentPriority">
            <el-option label="普通" value="normal" />
            <el-option label="高" value="high" />
            <el-option label="紧急" value="urgent" />
          </el-select>
        </el-form-item>
        <el-form-item label="付款用途">
          <el-input v-model="editForm.paymentPurpose" />
        </el-form-item>
        <el-form-item label="收款方">
          <el-input v-model="editForm.payeeName" />
        </el-form-item>
        <el-form-item label="收款银行">
          <el-input v-model="editForm.payeeBankName" />
        </el-form-item>
        <el-form-item label="收款账号">
          <el-input v-model="editForm.payeeBankAccount" />
        </el-form-item>
        <el-form-item label="付款账户名">
          <el-input v-model="editForm.payerAccountName" />
        </el-form-item>
        <el-form-item label="付款银行">
          <el-input v-model="editForm.payerBankName" />
        </el-form-item>
        <el-form-item label="付款账号">
          <el-input v-model="editForm.payerBankAccount" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="editForm.remark" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" @click="saveEdit">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="preExecutionPreviewVisible" title="付款执行入口预览" width="720px">
      <el-alert
        title="本弹窗仅用于查看付款执行入口信息。本轮点击确认不会执行付款，不会生成银行流水、付款凭证、正式付款凭证，不会核销，不会写总账。"
        type="warning"
        show-icon
        :closable="false"
      />
      <div v-if="preExecutionPreviewRow" class="preview-grid">
        <article>
          <span>付款执行准备单号</span>
          <strong>{{ preExecutionPreviewRow.paymentExecutionPrepareNo }}</strong>
        </article>
        <article>
          <span>供应商</span>
          <strong>{{ preExecutionPreviewRow.supplierName || '-' }}</strong>
        </article>
        <article>
          <span>执行准备金额</span>
          <strong>{{ formatAmount(preExecutionPreviewRow.executionAmount) }}</strong>
        </article>
        <article>
          <span>付款方式</span>
          <strong>{{ paymentMethodLabel(preExecutionPreviewRow.paymentMethod) }}</strong>
        </article>
        <article>
          <span>来源付款申请单号</span>
          <strong>{{ preExecutionPreviewRow.sourcePaymentApplicationNo || '-' }}</strong>
        </article>
        <article>
          <span>来源付款指令准备单号</span>
          <strong>{{ preExecutionPreviewRow.sourcePaymentOrderPrepareNo || '-' }}</strong>
        </article>
      </div>
      <template #footer>
        <el-button @click="preExecutionPreviewVisible = false">关闭</el-button>
        <el-button type="primary" @click="confirmEntryPreviewNoExecution">我已了解，本轮不执行付款</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="formalEntryPreviewVisible" title="正式付款执行入口预览" width="760px">
      <el-alert
        title="本轮只是正式付款执行入口预览。点击确认不会付款，不会生成银行流水、付款凭证、正式付款凭证，不会核销，不会写总账。真实付款功能当前强制关闭。"
        type="warning"
        show-icon
        :closable="false"
      />
      <div v-if="formalEntryPreviewRow" class="preview-grid">
        <article>
          <span>付款执行准备单号</span>
          <strong>{{ formalEntryPreviewRow.paymentExecutionPrepareNo }}</strong>
        </article>
        <article>
          <span>供应商</span>
          <strong>{{ formalEntryPreviewRow.supplierName || '-' }}</strong>
        </article>
        <article>
          <span>执行准备金额</span>
          <strong>{{ formatAmount(formalEntryPreviewRow.executionAmount) }}</strong>
        </article>
        <article>
          <span>付款方式</span>
          <strong>{{ paymentMethodLabel(formalEntryPreviewRow.paymentMethod) }}</strong>
        </article>
        <article>
          <span>收款方</span>
          <strong>{{ formalEntryPreviewRow.payeeName || '-' }}</strong>
        </article>
        <article>
          <span>来源付款指令准备单号</span>
          <strong>{{ formalEntryPreviewRow.sourcePaymentOrderPrepareNo || '-' }}</strong>
        </article>
        <article>
          <span>来源付款申请单号</span>
          <strong>{{ formalEntryPreviewRow.sourcePaymentApplicationNo || '-' }}</strong>
        </article>
        <article>
          <span>真实付款功能是否开启</span>
          <strong>{{ formalEntryPreviewRow.actualPaymentExecutionEnabled ? '是' : '否' }}</strong>
        </article>
        <article>
          <span>模拟状态</span>
          <strong>{{ paymentExecutionSimulationStatusLabel(formalEntryPreviewRow.paymentExecutionSimulationStatus) }}</strong>
        </article>
        <article class="preview-wide">
          <span>模拟提醒</span>
          <strong>{{ listText(formalEntryPreviewRow.formalExecutionEntryWarnings || formalEntryPreviewRow.paymentExecutionSimulationWarnings) || '-' }}</strong>
        </article>
      </div>
      <template #footer>
        <el-button @click="formalEntryPreviewVisible = false">关闭</el-button>
        <el-button type="primary" @click="confirmFormalEntryPreviewNoExecution">我已了解，本轮仍不执行付款</el-button>
      </template>
    </el-dialog>
  </main>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import PceResultFilterSelect from '../components/PceResultFilterSelect.vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { resolvePageNameConsumption } from '../governance/pageNameConsumer.js'
import BusinessTableScrollContainer from '../components/BusinessTableScrollContainer.vue'
import StandardListToolbar from '../components/StandardListToolbar.vue'
import {
  BUSINESS_ACCEPTANCE_COPY_VERSION,
  buildPageAcceptanceChecklist,
  businessAcceptanceSectionTitles,
} from '../runtime/businessAcceptanceCopy.js'
import {
  confirmAccountPayable,
  createPayableConfirmFromInvoicePrepare,
  getAccountPayableConfirmState,
  markPayableConfirmWaiting,
  saveAccountPayableConfirmState,
} from '../finance/accountPayableConfirmStore.js'
import {
  approvePaymentApplication,
  createPaymentApplicationFromPayableConfirm,
  getPaymentApplicationState,
  markPaymentApplicationWaitingSubmit,
  savePaymentApplicationState,
  submitPaymentApplication,
} from '../finance/paymentApplicationStore.js'
import {
  createPaymentOrderPrepareFromPaymentApplication,
  getPaymentInstructionPrepareState,
  markPaymentOrderPrepareWaitingReview,
  reviewPaymentOrderPrepare,
  savePaymentInstructionPrepareState,
} from '../finance/paymentInstructionPrepareStore.js'
import {
  createInvoicePrepareFromSupplierSettlement,
  getInvoicePrepareState,
  inputPurchaseInvoiceInfo,
  markPurchaseInvoiceChecked,
  markPurchaseInvoiceReceived,
  saveInvoicePrepareState,
} from '../finance/invoicePrepareStore.js'
import {
  blockPaymentExecutionPrepare,
  confirmFormalExecutionEntryPreviewNoExecution,
  closePaymentExecutionPrepare,
  confirmPaymentExecutionEntryPreviewNoExecution,
  createPaymentExecutionPrepareFromPaymentOrderPrepare,
  getFormalExecutionEntryDecision,
  getPaymentExecutionPrepareSourcesFromPaymentOrderPrepares,
  listPaymentExecutionPrepares,
  markPaymentExecutionPrepareWaitingReview,
  openFormalExecutionEntryPreview,
  openPaymentExecutionEntryPreview,
  recalculatePaymentExecutionPrepareAmount,
  reviewPaymentExecutionPrepare,
  runPaymentExecutionSimulation,
  runFormalExecutionEntryCheck,
  runPaymentExecutionPreExecutionCheck,
  savePaymentExecutionPrepareState,
  updatePaymentExecutionPrepareInfo,
} from '../finance/paymentExecutionPrepareStore.js'
import {
  buildSupplierSettlementSourceRows,
  confirmSupplierSettlementDifference,
  confirmSupplierSettlementReconciliation,
  createSupplierSettlementDraft,
  getSupplierSettlementState,
  listSupplierSettlements,
  saveSupplierSettlementState,
  selectSupplierSettlementDifferenceType,
} from '../scm/supplierSettlementStore.js'

const VERSION = BUSINESS_ACCEPTANCE_COPY_VERSION
const DEMO_CHAIN_VERSION = 'V1.13.39.10'
const DEMO_CHAIN_PURPOSE = '本地浏览器最小验证链路'
const router = useRouter()
const pageName = resolvePageNameConsumption({ pageCode: 'payment-execution-prepare', route: '/finance/payment-execution-prepares' })
const debugCollapseActive = ref([])
const showDevelopmentDebugTools = import.meta.env.DEV
const rows = ref(listPaymentExecutionPrepares())
const sourceRows = ref(getPaymentExecutionPrepareSourcesFromPaymentOrderPrepares())
const supplierSettlementSourceRows = ref(buildSupplierSettlementSourceRows())
const paymentExecutionPrepareTableRef = ref(null)
const selectedRows = ref([])
const quickSearch = ref('')
const advancedFilterVisible = ref(false)
const minimumChainGenerating = ref(false)
const minimumChainResult = ref(null)
const sortState = reactive({ key: '', direction: '' })
const filterState = reactive({
  paymentExecutionPrepareNo: '',
  sourcePaymentOrderPrepareNo: '',
  sourcePaymentApplicationNo: '',
  sourcePayableConfirmNo: '',
  supplier: '',
  purchaseOrderNo: '',
  invoiceNo: '',
  paymentExecutionPrepareStatus: '',
  paymentExecutionStatus: '',
  dateRange: [],
})

const editVisible = ref(false)
const editTargetId = ref('')
const preExecutionPreviewVisible = ref(false)
const preExecutionPreviewRow = ref(null)
const formalEntryPreviewVisible = ref(false)
const formalEntryPreviewRow = ref(null)
const editForm = reactive({
  executionAmount: 0,
  paymentMethod: 'bank_transfer',
  plannedPaymentDate: '',
  paymentPriority: 'normal',
  paymentPurpose: '',
  payeeName: '',
  payeeBankName: '',
  payeeBankAccount: '',
  payerAccountName: '',
  payerBankName: '',
  payerBankAccount: '',
  remark: '',
})

const prepareStatusOptions = [
  { value: 'draft', label: '草稿' },
  { value: 'waiting_execution_review', label: '待执行复核' },
  { value: 'reviewed', label: '已复核' },
  { value: 'blocked', label: '阻断' },
  { value: 'closed', label: '已关闭' },
]

const tableColumns = [
  { key: 'paymentExecutionPrepareNo', label: '付款执行准备单号', width: 180 },
  { key: 'sourcePaymentOrderPrepareNo', label: '来源付款指令准备单号', width: 190 },
  { key: 'sourcePaymentApplicationNo', label: '来源付款申请单号', width: 180 },
  { key: 'sourcePayableConfirmNo', label: '来源应付确认单号', width: 180 },
  { key: 'sourceInvoicePrepareNo', label: '来源发票准备单号', width: 180 },
  { key: 'sourceSettlementNo', label: '来源结算单号', width: 170 },
  { key: 'supplierName', label: '供应商', width: 160 },
  { key: 'purchaseOrderNo', label: '采购订单号', width: 160 },
  { key: 'invoiceNo', label: '发票号码', width: 150 },
  { key: 'orderAmount', label: '指令金额', width: 120 },
  { key: 'executionAmount', label: '执行准备金额', width: 140 },
  { key: 'paymentMethod', label: '付款方式', width: 130 },
  { key: 'plannedPaymentDate', label: '计划付款日期', width: 140 },
  { key: 'paymentPriority', label: '付款优先级', width: 130 },
  { key: 'payeeName', label: '收款方', width: 150 },
  { key: 'payeeBankName', label: '收款银行', width: 160 },
  { key: 'paymentExecutionPrepareStatus', label: '执行准备状态', width: 140 },
  { key: 'paymentExecutionStatus', label: '执行状态', width: 140 },
  { key: 'bankFlowStatus', label: '银行流水状态', width: 140 },
  { key: 'paymentVoucherStatus', label: '付款凭证状态', width: 140 },
  { key: 'formalPaymentVoucherStatus', label: '正式付款凭证状态', width: 150 },
  { key: 'writeOffStatus', label: '核销状态', width: 140 },
  { key: 'ledgerStatus', label: '总账状态', width: 140 },
  { key: 'postingStatus', label: '过账状态', width: 130 },
  { key: 'executionRiskStatus', label: '风险检查状态', width: 140 },
  { key: 'preExecutionCheckStatus', label: '执行前检查状态', width: 150 },
  { key: 'preExecutionRiskStatus', label: '执行前风险状态', width: 150 },
  { key: 'preExecutionReady', label: '允许进入执行入口', width: 160 },
  { key: 'preExecutionBlockReasons', label: '执行阻断原因', width: 220 },
  { key: 'preExecutionWarnings', label: '执行警告信息', width: 220 },
  { key: 'paymentExecutionSimulationStatus', label: '付款执行模拟状态', width: 160 },
  { key: 'paymentExecutionSimulated', label: '是否已模拟付款执行', width: 170 },
  { key: 'paymentExecutionSimulationResult', label: '付款执行模拟结果', width: 240 },
  { key: 'paymentExecutionSimulationWarnings', label: '付款执行模拟警告', width: 220 },
  { key: 'paymentExecutionSimulationBlockReasons', label: '付款执行模拟阻断原因', width: 240 },
  { key: 'formalExecutionEntryStatus', label: '正式付款入口预览状态', width: 180 },
  { key: 'formalExecutionEntryReady', label: '允许进入入口预览', width: 180 },
  { key: 'formalExecutionEntryBlockReasons', label: '入口预览阻断原因', width: 240 },
  { key: 'actualPaymentExecutionEnabled', label: '真实付款功能是否开启', width: 180 },
  { key: 'finalPaymentExecutionReviewStatus', label: '真实付款前最终评审状态', width: 200 },
  { key: 'recommendDirectPayment', label: '是否建议直接付款', width: 160 },
  { key: 'canStartRealPaymentDevelopment', label: '是否建议进入真实付款开发', width: 220 },
  { key: 'isDemoChain', label: '演示数据标识', width: 140 },
  { key: 'demoDataUsableForRealPayment', label: '演示数据是否可用于真实付款', width: 220 },
  { key: 'realPaymentImpactDesignStatus', label: '真实付款状态影响设计状态', width: 220 },
  { key: 'paymentExecutionStatusChangedThisRound', label: '付款执行状态本轮是否改变', width: 200 },
  { key: 'bankFlowStatusChangedThisRound', label: '银行流水状态本轮是否改变', width: 200 },
  { key: 'paymentVoucherStatusChangedThisRound', label: '付款凭证状态本轮是否改变', width: 200 },
  { key: 'writeOffStatusChangedThisRound', label: '核销状态本轮是否改变', width: 180 },
  { key: 'ledgerStatusChangedThisRound', label: '总账状态本轮是否改变', width: 180 },
  { key: 'downstreamModulesWrittenThisRound', label: '后续模块是否本轮写入', width: 190 },
  { key: 'bankFlowBoundaryDesignStatus', label: '银行流水生成导入边界设计状态', width: 240 },
  { key: 'bankFlowGeneratedThisRound', label: '本轮是否生成银行流水', width: 190 },
  { key: 'bankFlowImportedThisRound', label: '本轮是否导入银行流水', width: 190 },
  { key: 'bankFlowLinkedThisRound', label: '本轮是否关联银行流水', width: 190 },
  { key: 'bankFlowMatchedThisRound', label: '本轮是否执行银行流水匹配', width: 220 },
  { key: 'bankFlowMatchConfirmedThisRound', label: '本轮是否确认银行流水匹配', width: 220 },
  { key: 'bankFlowStatusChangedThisRoundForBoundary', label: '银行流水状态本轮是否改变', width: 210 },
  { key: 'bankFlowDownstreamWrittenThisRound', label: '后续模块是否本轮写入', width: 190 },
  { key: 'bankFlowObjectDesignStatus', label: '银行流水真实对象设计状态', width: 230 },
  { key: 'bankFlowFormalObjectCreatedThisRound', label: '本轮是否新增正式银行流水对象', width: 240 },
  { key: 'bankFlowImportButtonAddedThisRound', label: '本轮是否新增银行流水导入按钮', width: 240 },
  { key: 'bankFlowFileImportedThisRound', label: '本轮是否导入银行流水文件', width: 220 },
  { key: 'bankFlowExcelReadThisRound', label: '本轮是否读取 Excel', width: 170 },
  { key: 'bankFlowCsvReadThisRound', label: '本轮是否读取 CSV', width: 170 },
  { key: 'bankFlowImportBatchCreatedThisRound', label: '本轮是否创建导入批次', width: 210 },
  { key: 'bankFlowImportValidationExecutedThisRound', label: '本轮是否执行导入校验', width: 220 },
  { key: 'bankFlowEnteredPendingMatchThisRound', label: '本轮是否进入待匹配', width: 200 },
  { key: 'bankFlowReadonlyPreviewStatus', label: '银行流水只读对象预览状态', width: 220 },
  { key: 'bankFlowFileUploadedThisRound', label: '本轮是否上传文件', width: 170 },
  { key: 'bankFlowDuplicateBlockExecutedThisRound', label: '本轮是否执行重复拦截', width: 220 },
  { key: 'bankFlowAutoMatchedThisRound', label: '本轮是否自动匹配', width: 180 },
  { key: 'bankFlowManualMatchConfirmedThisRound', label: '本轮是否人工确认匹配', width: 220 },
  { key: 'bankFlowFormalAuditLogWrittenThisRound', label: '本轮是否写正式审计日志', width: 220 },
  { key: 'bankFlowReadonlyPreviewGenerated', label: '本轮是否生成只读预览', width: 200 },
  { key: 'createdAt', label: '创建时间', width: 180 },
  { key: 'remark', label: '备注', width: 220 },
]

const paymentExecutionPrepareExportColumns = tableColumns.map(({ key, label }) => ({ key, label }))
const sortableColumns = tableColumns.map((item) => item.key)
const scrollableTableColumns = tableColumns.filter((item) => item.key !== 'paymentExecutionPrepareNo')
const paymentExecutionListRows = computed(() => buildPaymentExecutionDisplayRows(rows.value, sourceRows.value).map(applyFormalEntryPreviewDecision))
const filteredRows = computed(() => sortRows(paymentExecutionListRows.value.filter(matchFilters), sortState))
const activeFilterCount = computed(() => {
  const advancedCount = Object.entries(filterState).filter(([key, value]) => key === 'dateRange'
    ? Array.isArray(value) && value.length === 2
    : String(value || '').trim()).length
  return advancedCount + (quickSearch.value.trim() ? 1 : 0)
})
const currentChainNos = computed(() => {
  const row = filteredRows.value[0] || paymentExecutionListRows.value[0] || {}
  return {
    settlementNo: minimumChainResult.value?.settlementNo || row.sourceSettlementNo || '',
    invoicePrepareNo: minimumChainResult.value?.invoicePrepareNo || row.sourceInvoicePrepareNo || '',
    payableConfirmNo: minimumChainResult.value?.payableConfirmNo || row.sourcePayableConfirmNo || '',
    paymentApplicationNo: minimumChainResult.value?.paymentApplicationNo || row.sourcePaymentApplicationNo || '',
    paymentOrderPrepareNo: minimumChainResult.value?.paymentOrderPrepareNo || row.sourcePaymentOrderPrepareNo || '',
    paymentExecutionPrepareNo: minimumChainResult.value?.paymentExecutionPrepareNo || row.paymentExecutionPrepareNo || '',
  }
})
const bankFlowPreviewEntryNo = computed(() => (
  filteredRows.value[0]?.paymentExecutionPrepareNo
    || paymentExecutionListRows.value[0]?.paymentExecutionPrepareNo
    || currentChainNos.value.paymentExecutionPrepareNo
    || ''
))
const manualAcceptancePepNo = computed(() => bankFlowPreviewEntryNo.value || 'PEP2026071311191257')
const currentFullUrl = computed(() => (typeof window !== 'undefined' ? window.location.href : '/finance/payment-execution-prepares'))
const paymentVoucherPreviewUrlText = computed(() => (
  `http://localhost:5173/#/finance/payment-voucher-prepare-preview/${manualAcceptancePepNo.value}`
))
const canGenerateFromSupplierSource = computed(() => supplierSettlementSourceRows.value.length > 0)
const readySourceRows = computed(() => sourceRows.value.filter((item) => item.canCreatePaymentExecutionPrepare))
const issuedSourceRows = computed(() => sourceRows.value.filter((item) => item.paymentInstructionStatus === 'issued_for_execution' || item.paymentExecutionPrepareGenerated))
const minimumChainGuideVisible = computed(() => !paymentExecutionListRows.value.length && !sourceRows.value.length)
const minimumChainAutoGenerateVisible = computed(() => canGenerateFromSupplierSource.value)
const demoChainDataSummary = computed(() => {
  const supplierSettlementCount = getSupplierSettlementState().supplierSettlements.filter((item) => item.isDemoChain).length
  const invoicePrepareCount = getInvoicePrepareState().invoicePrepares.filter((item) => item.isDemoChain).length
  const payableConfirmCount = getAccountPayableConfirmState().accountPayableConfirms.filter((item) => item.isDemoChain).length
  const paymentApplicationCount = getPaymentApplicationState().paymentApplications.filter((item) => item.isDemoChain).length
  const paymentOrderPrepareCount = getPaymentInstructionPrepareState().paymentOrderPrepares.filter((item) => item.isDemoChain).length
  const paymentExecutionPrepareCount = rows.value.filter((item) => item.isDemoChain).length
  const totalPrepareLayerCount = supplierSettlementCount
    + invoicePrepareCount
    + payableConfirmCount
    + paymentApplicationCount
    + paymentOrderPrepareCount
    + paymentExecutionPrepareCount
  return {
    supplierSettlementCount,
    invoicePrepareCount,
    payableConfirmCount,
    paymentApplicationCount,
    paymentOrderPrepareCount,
    paymentExecutionPrepareCount,
    totalPrepareLayerCount,
    canClear: totalPrepareLayerCount > 0,
  }
})
const latestChainNoText = computed(() => {
  const nos = currentChainNos.value
  return [
    nos.settlementNo,
    nos.invoicePrepareNo,
    nos.payableConfirmNo,
    nos.paymentApplicationNo,
    nos.paymentOrderPrepareNo,
    nos.paymentExecutionPrepareNo,
  ].filter(Boolean).join(' → ') || '-'
})
const demoChainManagementAdvice = computed(() => {
  if (supplierSettlementSourceRows.value.length > 0) {
    return '当前不需要导入源头数据，可以基于现有来源候选生成最小验证链路。'
  }
  return '当前缺少源头数据，需要先导入或生成采购到货、检验入库、应付预备相关演示数据。'
})
const summaryCount = computed(() => paymentExecutionListRows.value.length)
const filteredAmountTotal = computed(() => round(filteredRows.value.reduce((sum, item) => sum + amountValue(item), 0)))
const allExecutionAmountTotal = computed(() => round(paymentExecutionListRows.value.reduce((sum, item) => sum + amountValue(item), 0)))
const listAndSummaryConsistent = computed(() => summaryCount.value === paymentExecutionListRows.value.length)
const amountSummaryConsistent = computed(() => summaryCards.value.find((item) => item.title === '执行准备金额')?.rawValue === filteredAmountTotal.value)
const consistencyWarning = computed(() => {
  if (filteredRows.value.length && !summaryCount.value) return '付款执行准备列表与汇总统计不一致，请检查统计口径。'
  if (filteredRows.value.length && filteredAmountTotal.value <= 0) return '付款执行准备列表与汇总统计不一致，请检查统计口径。'
  if (!listAndSummaryConsistent.value) return '付款执行准备列表与汇总统计不一致，请检查统计口径。'
  if (!amountSummaryConsistent.value) return '付款执行准备列表与汇总统计不一致，请检查统计口径。'
  return ''
})
const cannotGenerateReason = computed(() => {
  if (paymentExecutionListRows.value.length) return '已存在付款执行准备记录，可继续查看、导出、复制诊断数据。'
  if (!sourceRows.value.length) return '当前浏览器没有付款指令准备来源数据，付款执行准备页无法直接生成真实记录。'
  if (!readySourceRows.value.length && !sourceDiagnostics.value.generatedExecutionPrepareCount) return '已读取到付款指令准备来源，但没有处于可签发付款指令的记录。'
  if (!filteredRows.value.length) return '当前筛选条件下没有付款执行准备记录。'
  return '当前来源数据可见，请检查筛选条件或下方列表。'
})
const nextOperationAdvice = computed(() => {
  if (paymentExecutionListRows.value.length) return '已存在付款执行准备记录，可继续查看、导出当前结果或复制诊断数据。'
  if (readySourceRows.value.length) return '在付款指令准备来源校准表中点击生成付款执行准备。'
  return '请在同一浏览器中从供应商结算页面开始，按最小链路步骤生成到付款执行准备。'
})
const sourceDataAdvice = computed(() => {
  const hasSettlementSource = supplierSettlementSourceRows.value.length > 0
  if (paymentExecutionListRows.value.length) {
    return {
      needImportSourceData: false,
      message: '已存在付款执行准备记录，可继续查看、导出和复制诊断数据。',
      action: '无需导入源头数据，也无需重新跑最小链路。',
    }
  }
  if (sourceRows.value.length) {
    return {
      needImportSourceData: false,
      message: '已读取到付款指令准备来源数据；如果仍无法生成，请先检查来源状态是否为可签发付款指令。',
      action: '先打开付款指令准备页面复核通过并生成付款执行准备。',
    }
  }
  if (hasSettlementSource) {
    return {
      needImportSourceData: false,
      message: '当前不需要导入源头数据，可从供应商结算来源候选开始重跑最小链路。',
      action: '打开供应商结算页面，从来源候选生成结算草稿并逐步推进到付款执行准备。',
    }
  }
  return {
    needImportSourceData: true,
    message: '当前缺少供应商结算来源候选，也没有付款指令准备来源数据。',
    action: '需要先导入或生成采购到货、入库、应付预备相关演示数据，再从供应商结算开始重跑。',
  }
})
const minimumChainGuideSteps = [
  {
    title: '第一步：生成供应商结算草稿',
    url: 'http://localhost:5173/#/scm/supplier-settlements',
    description: '从来源候选生成供应商结算草稿。',
  },
  {
    title: '第二步：确认差异并生成采购发票准备',
    url: 'http://localhost:5173/#/scm/supplier-settlements',
    description: '确认差异、确认对账，然后生成采购发票准备。',
  },
  {
    title: '第三步：采购发票准备推进到应付确认准备',
    url: 'http://localhost:5173/#/finance/purchase-invoice-prepares',
    description: '录入发票信息、标记已收票、核对通过，生成应付确认准备。',
  },
  {
    title: '第四步：应付确认准备生成付款申请准备',
    url: 'http://localhost:5173/#/finance/account-payable-confirms',
    description: '标记待确认、确认应付，生成付款申请准备。',
  },
  {
    title: '第五步：付款申请准备生成付款指令准备',
    url: 'http://localhost:5173/#/finance/payment-applications',
    description: '标记待提交、提交付款申请、审批通过，生成付款指令准备。',
  },
  {
    title: '第六步：付款指令准备生成付款执行准备',
    url: 'http://localhost:5173/#/finance/payment-order-prepares',
    description: '标记待复核、复核通过，生成付款执行准备。',
  },
  {
    title: '第七步：回到付款执行准备页验收真实记录',
    url: 'http://localhost:5173/#/finance/payment-execution-prepares',
    description: '确认付款执行准备数、当前结果数和执行准备金额均不是 0。',
  },
]
const sourceDiagnostics = computed(() => {
  const sourceReadWarnings = []
  const readyToIssueCount = sourceRows.value.filter((item) => item.paymentInstructionStatus === 'ready_to_issue').length
  const issuedForExecutionCount = sourceRows.value.filter((item) => item.paymentInstructionStatus === 'issued_for_execution').length
  const generatedExecutionPrepareCount = sourceRows.value.filter((item) => item.paymentExecutionPrepareGenerated || item.linkedPaymentExecutionPrepareNo).length
  if (paymentExecutionListRows.value.length) {
    // 已有付款执行准备主列表记录时不再提示缺少来源，避免误导用户重跑链路。
  } else if (!sourceRows.value.length) {
    sourceReadWarnings.push('当前浏览器没有付款指令准备来源数据，请从供应商结算开始重新跑一条最小链路。')
  } else if (!readyToIssueCount && !issuedForExecutionCount && !generatedExecutionPrepareCount) {
    sourceReadWarnings.push('已读取到付款指令准备记录，但状态不是 ready_to_issue / issued_for_execution，且未关联付款执行准备。')
  } else if (!readySourceRows.value.length && !generatedExecutionPrepareCount) {
    sourceReadWarnings.push('已读取到付款指令准备记录，但当前没有满足生成付款执行准备条件的来源。')
  }
  return {
    sourceStoreName: 'paymentInstructionPrepareStore',
    sourceLocalStorageKey: 'payment-instruction-prepare-state-v1',
    sourcePaymentOrderPrepareCount: sourceRows.value.length,
    readyToIssueCount,
    issuedForExecutionCount,
    generatedExecutionPrepareCount,
    sourceReadWarnings,
    sourceSampleNos: sourceRows.value.map((item) => item.paymentOrderPrepareNo).filter(Boolean).slice(0, 10),
  }
})
const visibleSourceRows = computed(() => sourceRows.value.filter((item) => (
  item.canCreatePaymentExecutionPrepare
  || item.paymentExecutionPrepareGenerated
  || item.paymentInstructionStatus === 'issued_for_execution'
  || item.paymentInstructionStatus === 'ready_to_issue'
)).slice(0, 12))

const summaryCards = computed(() => {
  const all = paymentExecutionListRows.value
  const countBy = (key, value) => all.filter((item) => item[key] === value).length
  const amountTotal = filteredAmountTotal.value
  return [
    { title: '付款执行准备数', value: all.length, rawValue: all.length, desc: '仅为执行前准备对象' },
    { title: '草稿数', value: countBy('paymentExecutionPrepareStatus', 'draft'), desc: '未进入执行复核' },
    { title: '待执行复核', value: countBy('paymentExecutionPrepareStatus', 'waiting_execution_review'), desc: '等待人工复核' },
    { title: '已复核', value: countBy('paymentExecutionPrepareStatus', 'reviewed'), desc: '仍未真实付款' },
    { title: '阻断数', value: countBy('paymentExecutionPrepareStatus', 'blocked'), desc: '执行准备异常' },
    { title: '已关闭', value: countBy('paymentExecutionPrepareStatus', 'closed'), desc: '不再流转' },
    { title: '未执行付款', value: countBy('paymentExecutionStatus', 'not_executed'), desc: '保护状态' },
    { title: '执行准备金额', value: formatAmount(amountTotal), rawValue: amountTotal, desc: '当前结果金额合计' },
  ]
})

const preExecutionCheckRows = computed(() => filteredRows.value)
const preExecutionCheckSummary = computed(() => {
  const all = paymentExecutionListRows.value
  const checkedItems = all.filter((item) => ['checked', 'blocked'].includes(item.preExecutionCheckStatus))
  const readyItems = all.filter((item) => item.preExecutionReady)
  const blockedItems = all.filter((item) => item.preExecutionBlocked)
  const warningItems = all.filter((item) => item.preExecutionRiskStatus === 'warning')
  const checkedTimes = checkedItems.map((item) => item.preExecutionCheckedAt).filter(Boolean).sort()
  const reasonMap = {}
  blockedItems.flatMap((item) => item.preExecutionBlockReasons || []).forEach((reason) => {
    reasonMap[reason] = (reasonMap[reason] || 0) + 1
  })
  return {
    checkedCount: checkedItems.length,
    readyCount: readyItems.length,
    blockedCount: blockedItems.length,
    warningCount: warningItems.length,
    latestCheckAt: checkedTimes[checkedTimes.length - 1] || '',
    readyPaymentExecutionPrepareNos: readyItems.map((item) => item.paymentExecutionPrepareNo).filter(Boolean),
    blockedPaymentExecutionPrepareNos: blockedItems.map((item) => item.paymentExecutionPrepareNo).filter(Boolean),
    blockReasonSummary: Object.entries(reasonMap).map(([reason, count]) => ({ reason, count })),
  }
})
const paymentExecutionSimulationSummary = computed(() => {
  const all = paymentExecutionListRows.value
  const simulatedItems = all.filter((item) => item.paymentExecutionSimulationStatus && item.paymentExecutionSimulationStatus !== 'not_simulated')
  const readyItems = all.filter((item) => item.paymentExecutionSimulationStatus === 'simulated_ready')
  const warningItems = all.filter((item) => item.paymentExecutionSimulationStatus === 'simulated_warning')
  const blockedItems = all.filter((item) => item.paymentExecutionSimulationStatus === 'simulated_blocked')
  const simulatedTimes = simulatedItems.map((item) => item.paymentExecutionSimulatedAt).filter(Boolean).sort()
  return {
    simulationCount: simulatedItems.length,
    simulatedReadyCount: readyItems.length,
    simulatedWarningCount: warningItems.length,
    simulatedBlockedCount: blockedItems.length,
    latestSimulationAt: simulatedTimes[simulatedTimes.length - 1] || '',
    simulatedPaymentExecutionPrepareNos: simulatedItems.map((item) => item.paymentExecutionPrepareNo).filter(Boolean),
    blockedPaymentExecutionPrepareNos: blockedItems.map((item) => item.paymentExecutionPrepareNo).filter(Boolean),
  }
})
const formalExecutionEntrySummary = computed(() => {
  const all = paymentExecutionListRows.value
  const readyItems = all.filter((item) => item.formalExecutionEntryReady)
  const blockedItems = all.filter((item) => item.formalExecutionEntryBlocked)
  const previewItems = all.filter((item) => Number(item.formalExecutionEntryPreviewCount || 0) > 0)
  const checkTimes = all.map((item) => item.formalExecutionEntryReviewedAt).filter(Boolean).sort()
  const reasonMap = {}
  blockedItems.flatMap((item) => item.formalExecutionEntryBlockReasons || []).forEach((reason) => {
    reasonMap[reason] = (reasonMap[reason] || 0) + 1
  })
  return {
    previewReadyCount: readyItems.length,
    previewBlockedCount: blockedItems.length,
    entryReadyCount: readyItems.length,
    entryBlockedCount: blockedItems.length,
    entryPreviewCount: previewItems.reduce((sum, item) => sum + Number(item.formalExecutionEntryPreviewCount || 0), 0),
    actualPaymentExecutionEnabled: false,
    latestEntryCheckAt: checkTimes[checkTimes.length - 1] || '',
    readyPaymentExecutionPrepareNos: readyItems.map((item) => item.paymentExecutionPrepareNo).filter(Boolean),
    blockedPaymentExecutionPrepareNos: blockedItems.map((item) => item.paymentExecutionPrepareNo).filter(Boolean),
    blockReasonSummary: Object.entries(reasonMap).map(([reason, count]) => ({ reason, count })),
  }
})

const finalPaymentExecutionReviewSummary = computed(() => {
  const all = paymentExecutionListRows.value
  const chainNos = currentChainNos.value
  const demoChainNos = {
    settlementNo: chainNos.settlementNo || 'SET2026071311191160',
    invoicePrepareNo: chainNos.invoicePrepareNo || 'IP2026071311191146',
    payableConfirmNo: chainNos.payableConfirmNo || 'APC2026071311191255',
    paymentApplicationNo: chainNos.paymentApplicationNo || 'PAP2026071311191246',
    paymentOrderPrepareNo: chainNos.paymentOrderPrepareNo || 'POP2026071311191284',
    paymentExecutionPrepareNo: chainNos.paymentExecutionPrepareNo || 'PEP2026071311191257',
  }
  const hasPrepare = all.length > 0
  const preExecutionChecked = all.some((item) => item.preExecutionReady && !item.preExecutionBlocked)
  const simulationCompleted = all.some((item) => ['simulated_ready', 'simulated_warning'].includes(item.paymentExecutionSimulationStatus))
  const formalPreviewReady = all.some((item) => item.formalExecutionEntryReady)
  const formalPreviewOpened = all.some((item) => Number(item.formalExecutionEntryPreviewCount || 0) > 0 || item.formalExecutionEntryStatus === 'reviewed_only')
  const stillNotPaid = all.every((item) => item.paymentExecutionStatus === 'not_executed')
  const noBankFlow = all.every((item) => item.bankFlowStatus === 'not_generated')
  const noPaymentVoucher = all.every((item) => item.paymentVoucherStatus === 'not_generated')
  const noFormalPaymentVoucher = all.every((item) => item.formalPaymentVoucherStatus === 'not_generated')
  const noWriteOff = all.every((item) => item.writeOffStatus === 'not_written_off')
  const noLedger = all.every((item) => item.ledgerStatus === 'not_written_ledger')
  const noPosting = all.every((item) => item.postingStatus === 'not_posted')
  const hasDemoData = all.some((item) => item.isDemoChain || item.readonlyRecovered)
  const reviewItems = {
    hasPaymentExecutionPrepare: hasPrepare,
    preExecutionChecked,
    simulationCompleted,
    formalPreviewReady,
    formalPreviewOpened,
    actualPaymentStillDisabled: true,
    stillNotPaid,
    noBankFlow,
    noPaymentVoucher,
    noFormalPaymentVoucher,
    noWriteOff,
    noLedger,
    noPosting,
    demoDataIdentified: hasDemoData,
    canEvaluateRealPaymentDevelopment: hasPrepare && preExecutionChecked && simulationCompleted && formalPreviewReady,
  }
  const prerequisiteItems = [
    '付款执行准备必须已复核。',
    '付款执行前安全检查必须通过。',
    '付款执行模拟必须完成。',
    '正式付款入口预览必须完成确认。',
    '付款金额必须大于 0。',
    '付款方式、收款方和收款银行信息必须完整。',
    '来源付款申请、应付确认、采购发票准备和供应商结算必须可追溯。',
    '当前必须仍未付款、未生成银行流水、未生成付款凭证、未核销、未写总账、未过账。',
    '演示链路数据不得作为真实付款依据。',
  ]
  const futureImpactItems = [
    '付款执行状态可能从未执行变为已执行。',
    '银行流水可能生成、导入或关联。',
    '付款凭证准备与正式付款凭证可能进入后续流程。',
    '付款核销、总账写入、过账状态和供应商账龄可能发生变化。',
    'P2P验证中心、业务追踪链路和财务报表数据可能受到影响。',
    '操作日志和审计记录必须完整保留。',
  ]
  const riskItems = [
    '误付款或重复付款风险。',
    '收款方、收款银行账户或付款金额错误风险。',
    '未审批付款风险。',
    '付款后未生成凭证或重复生成凭证风险。',
    '银行流水、核销、总账重复写入风险。',
    '演示数据与正式数据混用风险。',
    '浏览器本地数据与企业正式数据库不一致风险。',
  ]
  const demoDataBoundaryItems = [
    '当前本地样本链路仅用于开发阶段页面验证。',
    '当前链路是开发阶段演示数据。',
    '演示链路不得作为真实付款依据。',
    '演示数据不能用于真实付款。',
    '正式付款前必须接入正式数据库、权限、审计和付款安全机制。',
    '真实付款开发前必须区分演示数据和正式业务数据。',
    '开发调试区必须保持默认折叠。',
    '清理演示数据只能清理 isDemoChain = true 的准备层对象。',
    '不得清理采购订单、收货、检验、库存流水和应付预备源数据。',
  ]
  return {
    reviewReady: hasPrepare,
    reviewBlocked: true,
    reviewItems,
    prerequisiteItems,
    riskItems,
    futureImpactItems,
    actualPaymentStillDisabled: true,
    demoDataWarning: hasDemoData ? '当前存在演示或只读恢复链路，不能作为真实付款依据。' : '当前未识别演示链路标识，真实付款前仍需正式数据源复核。',
    demoChainNos,
    demoDataBoundaryItems,
    recommendDirectPayment: false,
    canStartRealPaymentDevelopment: hasPrepare && preExecutionChecked && simulationCompleted,
    recommendedNextStep: '不建议直接付款；建议先做真实付款状态影响、银行流水边界、付款凭证准备、核销前置和总账写入前置设计。',
  }
})

const realPaymentStateImpactDesignSummary = computed(() => {
  const stateTransitionItems = [
    {
      key: 'paymentExecutionStatus',
      name: '付款执行状态',
      currentStatus: '未执行',
      futureStatus: '未来真实付款后可能变为已执行。',
      changedThisRound: false,
    },
    {
      key: 'bankFlowStatus',
      name: '银行流水状态',
      currentStatus: '未生成',
      futureStatus: '未来可能进入待生成、已生成、已导入或已关联。',
      changedThisRound: false,
    },
    {
      key: 'paymentVoucherStatus',
      name: '付款凭证状态',
      currentStatus: '未生成',
      futureStatus: '未来可能进入待生成或已生成。',
      changedThisRound: false,
    },
    {
      key: 'formalPaymentVoucherStatus',
      name: '正式付款凭证状态',
      currentStatus: '未生成',
      futureStatus: '未来必须在付款凭证准备和复核后再进入正式凭证流程。',
      changedThisRound: false,
    },
    {
      key: 'writeOffStatus',
      name: '核销状态',
      currentStatus: '未核销',
      futureStatus: '未来必须在付款完成、银行流水和应付匹配后再进入核销。',
      changedThisRound: false,
    },
    {
      key: 'ledgerStatus',
      name: '总账状态',
      currentStatus: '未写总账',
      futureStatus: '未来必须在凭证复核和过账前置检查后再写总账。',
      changedThisRound: false,
    },
    {
      key: 'postingStatus',
      name: '过账状态',
      currentStatus: '未过账',
      futureStatus: '未来必须在正式凭证、会计期间、科目体系、凭证平衡全部满足后再过账。',
      changedThisRound: false,
    },
  ]
  const downstreamModuleItems = [
    ['付款执行准备模块', '未来可能记录真实付款执行结果。'],
    ['银行流水模块', '未来可能生成、导入或关联银行流水。'],
    ['付款凭证准备模块', '未来可能生成付款凭证准备。'],
    ['正式付款凭证模块', '未来可能在复核后形成正式付款凭证。'],
    ['应付核销模块', '未来可能进行付款与应付匹配核销。'],
    ['总账模块', '未来可能在凭证复核和过账前置检查后写入总账。'],
    ['供应商账龄模块', '未来可能更新供应商账龄。'],
    ['应付账龄模块', '未来可能更新应付账龄。'],
    ['资金预测模块', '未来可能更新资金预测。'],
    ['P2P业务验证中心', '未来可能更新付款链路验证状态。'],
    ['企业业务追踪中心', '未来可能更新业务追踪链路状态。'],
    ['财务报表模块', '未来可能影响报表数据。'],
    ['审计日志模块', '未来必须记录真实付款审计轨迹。'],
  ].map(([module, futureImpact]) => ({
    module,
    futureImpact,
    writeThisRound: false,
  }))
  const blockedAutoActions = [
    '不能自动生成正式付款凭证。',
    '不能自动核销。',
    '不能自动写总账。',
    '不能自动过账。',
    '不能自动改变采购订单状态。',
    '不能自动改变收货状态。',
    '不能自动改变检验状态。',
    '不能自动改变库存流水。',
  ]
  const stateFlow = [
    '真实付款执行',
    '银行流水生成或导入',
    '付款凭证准备',
    '付款凭证复核',
    '正式付款凭证',
    '核销前置检查',
    '付款核销',
    '总账前置检查',
    '总账写入',
    '过账',
  ]
  return {
    impactDesigned: true,
    impactDesignStatus: '已形成状态影响设计，本轮不执行真实付款',
    stateTransitionItems,
    downstreamModuleItems,
    stateFlow,
    protectionFlags: {
      actualPayment: false,
      generateBankFlow: false,
      generatePaymentVoucher: false,
      generateFormalPaymentVoucher: false,
      writeOffPayment: false,
      writeLedger: false,
      posting: false,
      changePaymentExecutionStatus: false,
    },
    blockedAutoActions,
    recommendedNextStep: '建议下一阶段继续设计银行流水生成/导入边界、付款凭证准备、核销前置和总账写入前置，不建议直接真实付款。',
  }
})

const bankFlowBoundaryDesignSummary = computed(() => {
  const sourceModeItems = [
    {
      mode: '方式一：系统生成银行流水候选',
      description: '未来真实付款执行完成后，系统可以根据付款执行结果生成银行流水候选记录。',
      boundary: '必须有真实付款执行结果、付款时间、付款金额、付款账户、收款账户、银行交易号或付款回执号。',
      executedThisRound: false,
    },
    {
      mode: '方式二：银行流水文件导入',
      description: '未来可以从银行下载流水文件后导入系统。',
      boundary: '必须有正式银行流水文件、银行账号、交易日期、交易金额、交易方向、对方户名和银行流水号。',
      executedThisRound: false,
    },
    {
      mode: '方式三：银企直联接口回传',
      description: '未来如果接入银企直联，银行可以回传付款结果和流水信息。',
      boundary: '必须有银行接口、接口权限、接口签名、回传流水号、交易状态和审计日志。',
      executedThisRound: false,
    },
    {
      mode: '方式四：人工关联已有银行流水',
      description: '未来如果银行流水已存在，可以由人工把付款执行单与银行流水进行关联。',
      boundary: '必须有匹配规则、人工确认、关联日志、反关联机制和权限控制。',
      executedThisRound: false,
    },
  ]
  const statusPreviewItems = [
    ['待生成', '未来可作为真实付款后的银行流水候选前置状态。'],
    ['已生成候选流水', '未来系统生成候选记录后进入该状态。'],
    ['已导入银行流水', '未来银行流水文件导入后进入该状态。'],
    ['已关联银行流水', '未来人工或规则确认关联后进入该状态。'],
    ['匹配待确认', '未来流水与付款执行单初步匹配后等待人工确认。'],
    ['匹配已确认', '未来人工确认匹配后进入该状态。'],
    ['匹配异常', '未来金额、账户、日期或流水号不一致时进入该状态。'],
    ['已撤销关联', '未来人工撤销银行流水与付款执行单关联后进入该状态。'],
  ].map(([status, description]) => ({
    status,
    description,
    changedThisRound: false,
  }))
  const downstreamBoundaryItems = [
    ['付款执行准备模块', '未来可能回写银行流水关联状态。'],
    ['银行流水模块', '未来可能保存生成、导入、回传或关联的银行流水。'],
    ['付款凭证准备模块', '未来可能依据已确认银行流水生成付款凭证准备。'],
    ['付款核销模块', '未来可能基于付款执行、银行流水和应付进行核销。'],
    ['总账模块', '未来可能在凭证复核后写入总账。'],
    ['供应商账龄模块', '未来可能更新供应商账龄。'],
    ['应付账龄模块', '未来可能更新应付账龄。'],
    ['资金预测模块', '未来可能更新资金预测和实际付款现金流。'],
    ['P2P业务验证中心', '未来可能更新付款链路验证状态。'],
    ['企业业务追踪中心', '未来可能更新业务追踪链路状态。'],
    ['审计日志模块', '未来必须记录银行流水生成、导入、关联、撤销和匹配确认轨迹。'],
  ].map(([module, futureImpact]) => ({
    module,
    futureImpact,
    writeThisRound: false,
  }))
  const matchRuleItems = [
    '付款金额是否一致。',
    '付款日期是否在允许差异范围内。',
    '付款账户是否一致。',
    '收款方名称是否一致。',
    '收款银行账号是否一致。',
    '银行流水号是否唯一。',
    '银行交易方向是否为付款方向。',
    '是否已被其他付款单关联。',
    '是否存在部分付款。',
    '是否存在手续费或银行扣款差异。',
  ]
  const exceptionScenarioItems = [
    '银行流水金额与付款执行金额不一致。',
    '银行流水日期与计划付款日期不一致。',
    '收款方名称不一致。',
    '银行账号不一致。',
    '银行流水重复导入。',
    '一条银行流水关联多个付款单。',
    '一个付款单对应多条银行流水。',
    '银行流水已撤销或冲正。',
    '银行接口回传失败。',
    '银行流水缺少银行交易号。',
  ]
  const autoActionBlockedItems = [
    '不能自动认定付款成功。',
    '不能自动生成付款凭证。',
    '不能自动生成正式付款凭证。',
    '不能自动核销。',
    '不能自动写总账。',
    '不能自动过账。',
    '不能自动改变采购订单状态。',
    '不能自动改变收货状态。',
    '不能自动改变检验状态。',
    '不能自动改变库存流水。',
    '不能自动冲销或关闭应付。',
    '不能自动修改付款金额。',
  ]
  const correctFlowItems = [
    '真实付款执行',
    '银行流水生成 / 导入 / 回传',
    '银行流水与付款执行单匹配',
    '人工确认匹配',
    '付款凭证准备',
    '付款凭证复核',
    '正式付款凭证',
    '核销前置检查',
    '付款核销',
    '总账前置检查',
    '总账写入',
    '过账',
  ]
  return {
    boundaryDesigned: true,
    boundaryDesignStatus: '已形成银行流水生成 / 导入边界设计，本轮不生成、不导入、不关联银行流水',
    sourceModeItems,
    statusPreviewItems,
    matchRuleItems,
    exceptionScenarioItems,
    downstreamBoundaryItems,
    autoActionBlockedItems,
    correctFlowItems,
    protectionFlags: {
      actualPayment: false,
      generateBankFlow: false,
      importBankFlow: false,
      linkBankFlow: false,
      executeBankFlowMatch: false,
      confirmBankFlowMatch: false,
      generatePaymentVoucher: false,
      generateFormalPaymentVoucher: false,
      writeOffPayment: false,
      writeLedger: false,
      posting: false,
      changePaymentExecutionStatus: false,
      changeBankFlowStatus: false,
    },
    recommendedNextStep: '建议下一阶段继续设计银行流水真实对象、导入校验、匹配确认、撤销关联和审计日志，不建议直接生成银行流水或直接核销。',
  }
})

const bankFlowObjectImportDesignSummary = computed(() => {
  const objectFieldItems = [
    ['银行流水唯一标识', '系统内部银行流水唯一编号。', '是', '系统生成'],
    ['银行流水号', '银行提供的交易流水号。', '是', '银行文件、银企直联或人工录入'],
    ['银行交易号 / 回单号', '银行交易确认号或回单编号。', '建议必填', '银行回单、接口回传或流水文件'],
    ['银行账号', '企业付款账户。', '是', '银行流水文件或企业银行账户档案'],
    ['交易日期', '银行实际记账日期。', '是', '银行流水'],
    ['交易时间', '银行实际交易时间。', '建议必填', '银行流水'],
    ['交易方向', '付款、收款、退款、冲正。', '是', '银行流水'],
    ['交易金额', '银行实际发生金额。', '是', '银行流水'],
    ['币种', '人民币或外币币种。', '是', '银行流水或默认币种'],
    ['对方户名', '收款方名称。', '是', '银行流水'],
    ['对方账号', '收款方银行账号。', '是', '银行流水'],
    ['对方开户行', '收款方开户银行。', '建议必填', '银行流水或供应商银行档案'],
    ['摘要 / 用途', '银行交易摘要或付款用途。', '建议必填', '银行流水或付款指令'],
    ['来源方式', '系统生成候选、文件导入、银企直联回传、人工关联。', '是', '导入或生成方式'],
    ['匹配状态', '未匹配、待确认、已匹配、匹配异常、已撤销。', '是', '系统匹配流程'],
    ['关联付款执行准备单号', '关联的付款执行准备单。', '匹配后必填', '匹配或人工关联'],
    ['导入批次号', '银行流水文件导入批次。', '文件导入时必填', '系统生成'],
    ['导入人', '执行导入操作的人。', '文件导入时必填', '当前用户'],
    ['导入时间', '流水导入系统时间。', '文件导入时必填', '系统时间'],
    ['审计日志', '生成、导入、匹配、确认、撤销、反关联日志。', '是', '系统审计'],
  ].map(([field, meaning, required, source]) => ({
    field,
    meaning,
    required,
    source,
    writeThisRound: false,
  }))
  const importTemplateItems = [
    ['银行流水号', '必填', '不能为空且同一银行账号下应唯一。'],
    ['银行交易号 / 回单号', '建议必填', '如果提供则必须唯一。'],
    ['银行账号', '必填', '必须属于企业已登记银行账户。'],
    ['交易日期', '必填', '必须为有效日期。'],
    ['交易时间', '建议必填', '必须为有效时间或允许为空。'],
    ['交易方向', '必填', '必须为付款、收款、退款或冲正。'],
    ['交易金额', '必填', '必须为大于 0 的有效数字。'],
    ['币种', '必填', '必须为有效币种。'],
    ['对方户名', '必填', '不能为空。'],
    ['对方账号', '必填', '不能为空。'],
    ['对方开户行', '建议必填', '允许为空但需提示补充。'],
    ['摘要 / 用途', '建议必填', '允许为空但需提示补充。'],
    ['交易状态', '建议必填', '必须为成功、失败、冲正或撤销等有效状态。'],
    ['手续费金额', '可选', '必须为有效数字。'],
    ['银行备注', '可选', '允许为空但需保留原始文本。'],
  ].map(([column, required, validationRule]) => ({
    column,
    required,
    validationRule,
    importedThisRound: false,
  }))
  const validationRuleItems = [
    '文件格式是否正确。',
    '必填列是否存在。',
    '必填列是否为空。',
    '银行账号是否属于企业已登记账户。',
    '交易日期格式是否正确。',
    '交易金额是否为有效数字。',
    '交易金额是否大于 0。',
    '交易方向是否有效。',
    '银行流水号是否为空。',
    '银行流水号是否重复。',
    '银行交易号 / 回单号是否重复。',
    '对方户名是否为空。',
    '对方账号是否为空。',
    '币种是否有效。',
    '同一导入批次内是否存在重复流水。',
    '当前系统中是否已存在相同流水。',
    '是否存在冲正或撤销标识。',
    '是否存在金额方向不一致。',
    '是否存在异常字符。',
    '是否满足权限和审计要求。',
  ]
  const duplicateBlockRuleItems = [
    '银行流水号 + 银行账号 + 交易日期 + 金额完全一致时拦截。',
    '银行交易号 / 回单号完全一致时拦截。',
    '同一银行账号、同一日期、同一金额、同一对方账号疑似重复时提示人工复核。',
    '同一导入批次内重复时拦截。',
    '已关联付款执行单的流水再次导入时拦截。',
    '已撤销关联流水再次导入时必须人工复核。',
    '冲正流水不能直接覆盖原流水。',
    '手续费流水不能误判为付款流水。',
  ]
  const importStatusFlowItems = [
    '导入待校验',
    '校验通过',
    '校验失败',
    '待匹配',
    '自动匹配候选',
    '人工确认匹配',
    '已匹配',
    '匹配异常',
    '已撤销匹配',
    '已作废',
  ]
  const importErrorItems = [
    '缺少必填字段。',
    '银行账号未登记。',
    '银行流水号重复。',
    '银行交易号重复。',
    '交易金额格式错误。',
    '交易金额小于或等于 0。',
    '交易方向无效。',
    '交易日期格式错误。',
    '对方户名为空。',
    '对方账号为空。',
    '币种无效。',
    '同一批次内存在重复。',
    '系统中已存在相同流水。',
    '文件格式不支持。',
    '当前用户无导入权限。',
    '导入批次创建失败。',
    '审计日志写入失败。',
  ]
  const objectBoundaryItems = [
    '本轮不新增正式银行流水对象。',
    '本轮不新增银行流水正式列表。',
    '本轮不新增银行流水导入按钮。',
    '本轮不新增可执行上传控件。',
    '本轮不导入 Excel。',
    '本轮不导入 CSV。',
    '本轮不读取本地银行文件。',
    '本轮不创建导入批次。',
    '本轮不生成银行流水号。',
    '本轮不关联付款执行单。',
    '本轮不改变银行流水状态。',
    '本轮不改变付款执行状态。',
    '本轮不核销。',
    '本轮不写总账。',
  ]
  return {
    objectDesigned: true,
    objectDesignStatus: '已形成银行流水真实对象与导入校验设计，本轮不创建真实对象、不导入文件',
    objectFieldItems,
    importTemplateItems,
    validationRuleItems,
    duplicateBlockRuleItems,
    importStatusFlowItems,
    importErrorItems,
    objectBoundaryItems,
    protectionFlags: {
      actualPayment: false,
      createFormalBankFlowObject: false,
      addBankFlowImportButton: false,
      importBankFlowFile: false,
      readExcel: false,
      readCsv: false,
      createImportBatch: false,
      executeImportValidation: false,
      enterPendingMatch: false,
      generateBankFlow: false,
      linkBankFlow: false,
      generatePaymentVoucher: false,
      writeOffPayment: false,
      writeLedger: false,
      posting: false,
    },
    recommendedNextStep: '建议下一阶段先设计银行流水只读对象、导入校验预览和重复拦截预览，再决定是否开发正式导入页面。',
  }
})

const bankFlowReadonlyObjectPreviewSummary = computed(() => {
  const row = filteredRows.value[0] || paymentExecutionListRows.value[0] || {}
  const executionPrepareNo = row.paymentExecutionPrepareNo || currentChainNos.value.paymentExecutionPrepareNo || 'PEP2026071311191257'
  const readonlyPreviewObject = [
    ['预览对象编号', `PREVIEW-BF-${executionPrepareNo}`],
    ['预览来源', '只读预览'],
    ['付款执行准备单号', executionPrepareNo],
    ['付款金额', formatAmount(row.executionAmount || row.orderAmount || 0)],
    ['付款方式', paymentMethodLabel(row.paymentMethod)],
    ['收款方', row.payeeName || '-'],
    ['收款银行', row.payeeBankName || '-'],
    ['计划付款日期', row.plannedPaymentDate || '-'],
    ['银行流水号', '未生成'],
    ['银行交易号 / 回单号', '未生成'],
    ['银行账号', '未读取'],
    ['交易日期', '未读取'],
    ['交易方向', '未读取'],
    ['交易金额', '未读取'],
    ['币种', '未读取'],
    ['匹配状态', '未进入匹配'],
    ['导入批次号', '未创建'],
    ['导入人', '未导入'],
    ['导入时间', '未导入'],
    ['审计状态', '仅预览，未写审计'],
  ].map(([field, value]) => ({
    field,
    value,
    writeFormalObjectThisRound: false,
  }))
  const validationPreviewItems = [
    ['文件是否存在', '未上传文件'],
    ['文件格式是否正确', '未校验'],
    ['是否读取 Excel', '否'],
    ['是否读取 CSV', '否'],
    ['必填列是否完整', '未校验'],
    ['必填值是否为空', '未校验'],
    ['银行账号是否登记', '未校验'],
    ['交易日期格式是否正确', '未校验'],
    ['交易金额是否有效', '未校验'],
    ['交易方向是否有效', '未校验'],
    ['银行流水号是否重复', '未校验'],
    ['银行交易号 / 回单号是否重复', '未校验'],
    ['对方户名是否为空', '未校验'],
    ['对方账号是否为空', '未校验'],
    ['币种是否有效', '未校验'],
    ['是否有导入权限', '未校验'],
    ['是否满足审计要求', '未校验'],
  ].map(([item, previewResult]) => ({
    item,
    previewResult,
    executedThisRound: false,
  }))
  const duplicateBlockPreviewItems = [
    '银行流水号 + 银行账号 + 交易日期 + 金额完全一致。',
    '银行交易号 / 回单号完全一致。',
    '同一银行账号、同一日期、同一金额、同一对方账号疑似重复。',
    '同一导入批次内重复。',
    '已关联付款执行单的流水再次导入。',
    '已撤销关联流水再次导入。',
    '冲正流水覆盖原流水。',
    '手续费流水误判为付款流水。',
  ].map((rule) => ({
    rule,
    previewResult: '未导入文件，暂不判断。',
    executedThisRound: false,
  }))
  const errorPreviewItems = [
    '缺少必填字段。',
    '银行账号未登记。',
    '银行流水号重复。',
    '银行交易号重复。',
    '交易金额格式错误。',
    '交易金额小于或等于 0。',
    '交易方向无效。',
    '交易日期格式错误。',
    '对方户名为空。',
    '对方账号为空。',
    '币种无效。',
    '同一批次内存在重复。',
    '系统中已存在相同流水。',
    '文件格式不支持。',
    '当前用户无导入权限。',
    '导入批次创建失败。',
    '审计日志写入失败。',
  ].map((errorType) => ({
    errorType,
    triggeredThisRound: false,
    reason: '本轮未导入文件，仅做错误预览。',
  }))
  const importStatusPreviewItems = [
    ['导入待校验', '未来上传并创建导入批次后进入。'],
    ['校验通过', '未来校验全部通过后进入。'],
    ['校验失败', '未来文件、字段或权限校验失败后进入。'],
    ['待匹配', '未来校验通过后等待匹配付款执行单。'],
    ['自动匹配候选', '未来规则初步命中后进入。'],
    ['人工确认匹配', '未来人工复核并确认匹配。'],
    ['已匹配', '未来匹配确认后进入。'],
    ['匹配异常', '未来金额、日期、账号等不一致时进入。'],
    ['已撤销匹配', '未来撤销已确认匹配后进入。'],
    ['已作废', '未来流水确认无效后进入。'],
  ].map(([status, description]) => ({
    status,
    description,
    enteredThisRound: false,
  }))
  const auditLogPreviewItems = [
    '银行流水对象生成日志',
    '银行流水文件导入日志',
    '导入批次创建日志',
    '导入校验日志',
    '重复拦截日志',
    '匹配候选生成日志',
    '人工确认匹配日志',
    '撤销匹配日志',
    '作废流水日志',
    '权限校验日志',
  ]
  return {
    readonlyPreviewGenerated: true,
    readonlyPreviewStatus: '已生成银行流水只读对象与导入校验预览，本轮不写正式银行流水',
    readonlyPreviewObject,
    validationPreviewItems,
    duplicateBlockPreviewItems,
    errorPreviewItems,
    importStatusPreviewItems,
    auditLogPreviewItems,
    protectionFlags: {
      actualPayment: false,
      createFormalBankFlowObject: false,
      addBankFlowImportButton: false,
      uploadFile: false,
      readExcel: false,
      readCsv: false,
      createImportBatch: false,
      executeImportValidation: false,
      executeDuplicateBlock: false,
      enterPendingMatch: false,
      autoMatch: false,
      manualMatchConfirm: false,
      writeFormalAuditLog: false,
      linkPaymentExecutionPrepare: false,
      writeOffPayment: false,
      writeLedger: false,
      posting: false,
    },
    recommendedNextStep: '建议下一阶段先开发银行流水只读对象的数据来源适配和导入校验预览页面，仍不要直接导入真实银行文件。',
  }
})

const diagnosticData = computed(() => ({
  page: 'PaymentExecutionPreparePage',
  version: VERSION,
  acceptanceCopySingleSource: true,
  manualAcceptanceNavigationVisible: true,
  acceptanceCurrentVersionMatch: VERSION === BUSINESS_ACCEPTANCE_COPY_VERSION,
  acceptanceRealUrlGenerated: Boolean(manualAcceptancePepNo.value),
  noAcceptancePlaceholderUrl: Boolean(manualAcceptancePepNo.value),
  paymentVoucherPreparePreviewUrl: paymentVoucherPreviewUrlText.value,
  sortArrowStyle: 'no-tail-bold-arrow',
  sortArrowShape: 'upright-triangle',
  horizontalScrollStyle: 'visible-button-thumb-drag-scroll',
  paymentExecutionPrepareCount: paymentExecutionListRows.value.length,
  paymentExecutionListRowsCount: paymentExecutionListRows.value.length,
  displayRowsCount: paymentExecutionListRows.value.length,
  executionRowsCount: paymentExecutionListRows.value.length,
  filteredCount: filteredRows.value.length,
  currentResultCount: filteredRows.value.length,
  summaryCards: summaryCards.value,
  filterState: { ...filterState },
  sortState: { ...sortState },
  selectedCount: selectedRows.value.length,
  draftCount: paymentExecutionListRows.value.filter((item) => item.paymentExecutionPrepareStatus === 'draft').length,
  waitingExecutionReviewCount: paymentExecutionListRows.value.filter((item) => item.paymentExecutionPrepareStatus === 'waiting_execution_review').length,
  reviewedCount: paymentExecutionListRows.value.filter((item) => item.paymentExecutionPrepareStatus === 'reviewed').length,
  blockedCount: paymentExecutionListRows.value.filter((item) => item.paymentExecutionPrepareStatus === 'blocked').length,
  closedCount: paymentExecutionListRows.value.filter((item) => item.paymentExecutionPrepareStatus === 'closed').length,
  listSummaryConsistency: {
    listRecordCount: filteredRows.value.length,
    summaryPaymentExecutionPrepareCount: summaryCount.value,
    listAndSummaryConsistent: listAndSummaryConsistent.value,
    amountSummaryConsistent: amountSummaryConsistent.value,
    currentResultExecutionAmountTotal: filteredAmountTotal.value,
    allExecutionAmountTotal: allExecutionAmountTotal.value,
    warning: consistencyWarning.value || '',
  },
  sourcePaymentOrderPrepareSummary: {
    sourceCount: sourceRows.value.length,
    readySourceCount: readySourceRows.value.length,
    issuedSourceCount: issuedSourceRows.value.length,
    generatedSourceCount: sourceRows.value.filter((item) => item.paymentExecutionPrepareGenerated || item.linkedPaymentExecutionPrepareNo).length,
    visibleSourceCount: visibleSourceRows.value.length,
    sourcePaymentOrderPrepareNos: sourceRows.value.map((item) => item.paymentOrderPrepareNo).filter(Boolean),
    linkedPaymentExecutionPrepareNos: sourceRows.value.map((item) => item.linkedPaymentExecutionPrepareNo).filter(Boolean),
  },
  sourceStoreName: sourceDiagnostics.value.sourceStoreName,
  sourceLocalStorageKey: sourceDiagnostics.value.sourceLocalStorageKey,
  sourcePaymentOrderPrepareCount: sourceDiagnostics.value.sourcePaymentOrderPrepareCount,
  readyToIssueCount: sourceDiagnostics.value.readyToIssueCount,
  issuedForExecutionCount: sourceDiagnostics.value.issuedForExecutionCount,
  generatedExecutionPrepareCount: sourceDiagnostics.value.generatedExecutionPrepareCount,
  supplierSettlementSourceCandidateCount: supplierSettlementSourceRows.value.length,
  demoChainSummary: {
    demoChainCount: demoChainDataSummary.value.totalPrepareLayerCount,
    latestDemoChainNos: currentChainNos.value,
    canClearDemoChain: demoChainDataSummary.value.canClear,
    isDevelopmentOnlyTool: true,
  },
  demoChainDataManagement: {
    paymentExecutionPrepareCount: paymentExecutionListRows.value.length,
    paymentOrderPrepareSourceCount: sourceRows.value.length,
    supplierSettlementSourceCandidateCount: supplierSettlementSourceRows.value.length,
    needImportSourceData: sourceDataAdvice.value.needImportSourceData,
    canGenerateFromSupplierSource: canGenerateFromSupplierSource.value,
    canClearPrepareLayerData: demoChainDataSummary.value.canClear,
    latestChainNos: currentChainNos.value,
    lastGeneratedChainResult: minimumChainResult.value,
    managementAdvice: demoChainManagementAdvice.value,
  },
  preExecutionCheckSummary: preExecutionCheckSummary.value,
  paymentExecutionSimulationSummary: paymentExecutionSimulationSummary.value,
  formalExecutionEntrySummary: formalExecutionEntrySummary.value,
  finalPaymentExecutionReviewSummary: finalPaymentExecutionReviewSummary.value,
  realPaymentStateImpactDesignSummary: realPaymentStateImpactDesignSummary.value,
  bankFlowBoundaryDesignSummary: bankFlowBoundaryDesignSummary.value,
  bankFlowObjectImportDesignSummary: bankFlowObjectImportDesignSummary.value,
  bankFlowReadonlyObjectPreviewSummary: bankFlowReadonlyObjectPreviewSummary.value,
  sourceReadWarnings: sourceDiagnostics.value.sourceReadWarnings,
  sourceSampleNos: sourceDiagnostics.value.sourceSampleNos,
  minimumChainGuideVisible: minimumChainGuideVisible.value,
  minimumChainAutoGenerateVisible: minimumChainAutoGenerateVisible.value,
  minimumChainGuideSteps,
  minimumChainResult: minimumChainResult.value,
  cannotGenerateReason: cannotGenerateReason.value,
  nextOperationAdvice: nextOperationAdvice.value,
  sourceDataAdvice: sourceDataAdvice.value,
  diagnosticChineseSummary: {
    '付款执行准备数': paymentExecutionListRows.value.length,
    '当前结果数': filteredRows.value.length,
    '付款执行准备列表记录数': filteredRows.value.length,
    '执行准备金额合计': filteredAmountTotal.value,
    '供应商结算单号': currentChainNos.value.settlementNo,
    '采购发票准备单号': currentChainNos.value.invoicePrepareNo,
    '应付确认准备单号': currentChainNos.value.payableConfirmNo,
    '付款申请准备单号': currentChainNos.value.paymentApplicationNo,
    '付款指令准备单号': currentChainNos.value.paymentOrderPrepareNo,
    '付款执行准备单号': currentChainNos.value.paymentExecutionPrepareNo,
    '汇总付款执行准备数': summaryCount.value,
    '列表与汇总是否一致': listAndSummaryConsistent.value ? '一致' : '不一致',
    '金额汇总是否一致': amountSummaryConsistent.value ? '一致' : '不一致',
    '付款指令准备来源数': sourceDiagnostics.value.sourcePaymentOrderPrepareCount,
    '可签发付款指令数': sourceDiagnostics.value.readyToIssueCount,
    '已签发到执行准备数': sourceDiagnostics.value.issuedForExecutionCount,
    '已生成付款执行准备数': sourceDiagnostics.value.generatedExecutionPrepareCount,
    '可生成付款执行准备数': readySourceRows.value.length,
    '当前结果执行准备金额合计': filteredAmountTotal.value,
    '全部执行准备金额合计': allExecutionAmountTotal.value,
    '供应商结算来源候选数': supplierSettlementSourceRows.value.length,
    '是否可以基于来源候选生成': canGenerateFromSupplierSource.value ? '可以' : '不可以',
    '是否已生成最小演示链路': currentChainNos.value.paymentExecutionPrepareNo ? '已生成' : '未生成',
    '写入范围': '只写付款执行准备对象的执行前检查、模拟、正式入口设计字段和相关日志；开发调试区仅可写或清理本地准备层演示对象。',
    '保护结论': '不执行付款、不生成银行流水、不生成付款凭证、不生成正式付款凭证、不核销、不写总账。',
    '当前不能生成原因': cannotGenerateReason.value,
    '下一步建议': nextOperationAdvice.value,
    '是否需要导入源头数据': sourceDataAdvice.value.needImportSourceData ? '需要' : '不需要',
    '源头数据建议操作': sourceDataAdvice.value.action,
    '付款执行前检查状态': preExecutionCheckSummary.value.checkedCount ? '已检查' : '未检查',
    '允许进入付款执行入口数': preExecutionCheckSummary.value.readyCount,
    '被阻断付款执行数': preExecutionCheckSummary.value.blockedCount,
    '阻断原因': preExecutionCheckSummary.value.blockReasonSummary.map((item) => `${item.reason}（${item.count}）`).join('；') || '无',
    '本轮是否执行付款': '否',
    '本轮是否生成银行流水': '否',
    '本轮是否生成付款凭证': '否',
    '本轮是否生成正式付款凭证': '否',
    '本轮是否核销': '否',
    '本轮是否写总账': '否',
    '付款执行模拟状态': paymentExecutionSimulationSummary.value.simulationCount ? '已模拟' : '未模拟',
    '已模拟付款执行数': paymentExecutionSimulationSummary.value.simulationCount,
    '模拟通过数': paymentExecutionSimulationSummary.value.simulatedReadyCount,
    '模拟警告数': paymentExecutionSimulationSummary.value.simulatedWarningCount,
    '模拟阻断数': paymentExecutionSimulationSummary.value.simulatedBlockedCount,
    '正式付款执行入口预览状态': formalExecutionEntrySummary.value.previewReadyCount ? '可预览，真实付款关闭' : '不可预览或已阻断',
    '允许进入正式付款入口预览数': formalExecutionEntrySummary.value.previewReadyCount,
    '被阻断正式付款入口预览数': formalExecutionEntrySummary.value.previewBlockedCount,
    '真实付款功能是否开启': '否',
    '真实付款前最终评审状态': finalPaymentExecutionReviewSummary.value.reviewReady ? '已形成评审，仍不付款' : '待评审',
    '真实付款功能是否仍关闭': finalPaymentExecutionReviewSummary.value.actualPaymentStillDisabled ? '是' : '否',
    '是否建议直接付款': finalPaymentExecutionReviewSummary.value.recommendDirectPayment ? '是' : '否',
    '是否建议进入真实付款开发': finalPaymentExecutionReviewSummary.value.canStartRealPaymentDevelopment ? '可以进入前置设计评估' : '暂不建议',
    '当前是否演示数据': finalPaymentExecutionReviewSummary.value.reviewItems.demoDataIdentified ? '是' : '否',
    '演示数据是否可用于真实付款': '否',
    '最终评审建议下一步': finalPaymentExecutionReviewSummary.value.recommendedNextStep,
    '真实付款状态影响设计状态': realPaymentStateImpactDesignSummary.value.impactDesignStatus,
    '本轮是否真实付款': '否',
    '本轮是否生成银行流水': '否',
    '本轮是否生成付款凭证': '否',
    '本轮是否生成正式付款凭证': '否',
    '本轮是否核销': '否',
    '本轮是否写总账': '否',
    '本轮是否过账': '否',
    '付款执行状态是否本轮改变': '否',
    '银行流水状态是否本轮改变': '否',
    '付款凭证状态是否本轮改变': '否',
    '核销状态是否本轮改变': '否',
    '总账状态是否本轮改变': '否',
    '状态影响设计建议下一步': realPaymentStateImpactDesignSummary.value.recommendedNextStep,
    '银行流水生成导入边界设计状态': bankFlowBoundaryDesignSummary.value.boundaryDesignStatus,
    '本轮是否导入银行流水': '否',
    '本轮是否关联银行流水': '否',
    '本轮是否执行银行流水匹配': '否',
    '本轮是否确认银行流水匹配': '否',
    '银行流水边界设计建议下一步': bankFlowBoundaryDesignSummary.value.recommendedNextStep,
    '银行流水真实对象与导入校验设计状态': bankFlowObjectImportDesignSummary.value.objectDesignStatus,
    '本轮是否新增正式银行流水对象': '否',
    '本轮是否新增银行流水导入按钮': '否',
    '本轮是否导入银行流水文件': '否',
    '本轮是否读取 Excel': '否',
    '本轮是否读取 CSV': '否',
    '本轮是否创建导入批次': '否',
    '本轮是否生成银行流水号': '否',
    '本轮是否关联付款执行单': '否',
    '本轮是否执行导入校验': '否',
    '本轮是否进入待匹配': '否',
    '银行流水对象导入设计建议下一步': bankFlowObjectImportDesignSummary.value.recommendedNextStep,
    '银行流水只读对象与导入校验预览状态': bankFlowReadonlyObjectPreviewSummary.value.readonlyPreviewStatus,
    '银行流水只读预览统一验收结论': '全部为否，除“本轮是否生成只读预览”为是',
    '本轮是否新增正式银行流水对象': '否',
    '本轮是否新增银行流水导入按钮': '否',
    '本轮是否上传文件': '否',
    '本轮是否读取 Excel': '否',
    '本轮是否读取 CSV': '否',
    '本轮是否创建导入批次': '否',
    '本轮是否执行导入校验': '否',
    '本轮是否执行重复拦截': '否',
    '本轮是否进入待匹配': '否',
    '本轮是否自动匹配': '否',
    '本轮是否人工确认匹配': '否',
    '本轮是否写正式审计日志': '否',
    '本轮是否关联付款执行单': '否',
    '本轮是否核销': '否',
    '本轮是否写总账': '否',
    '本轮是否过账': '否',
    '本轮是否生成只读预览': bankFlowReadonlyObjectPreviewSummary.value.readonlyPreviewGenerated ? '是' : '否',
    '银行流水只读预览建议下一步': bankFlowReadonlyObjectPreviewSummary.value.recommendedNextStep,
  },
  paymentExecutionAmountSummary: {
    orderAmountTotal: round(paymentExecutionListRows.value.reduce((sum, item) => sum + Number(item.orderAmount || 0), 0)),
    executionAmountTotal: allExecutionAmountTotal.value,
    filteredExecutionAmountTotal: filteredAmountTotal.value,
    overOrderCount: paymentExecutionListRows.value.filter((item) => amountValue(item) > Number(item.orderAmount || 0)).length,
  },
  exportFieldNames: paymentExecutionPrepareExportColumns.map((column) => column.label),
  exportEnabled: true,
  sortableColumns,
  sortArrowStyle: 'no-tail-bold-arrow',
  sortArrowShape: 'upright-triangle',
  protectionFlags: {
    modifyPurchaseOrder: false,
    modifyReceipt: false,
    modifyInspection: false,
    modifyInventory: false,
    modifySettlement: false,
    modifyInvoicePrepare: false,
    modifyPayableConfirm: false,
    modifyPaymentApplication: false,
    modifyPaymentOrderPrepareSourceAmount: false,
    executePayment: false,
    generatePaymentVoucher: false,
    generateFormalPaymentVoucher: false,
    writeLedger: false,
    writeOffPayment: false,
    generateBankFlow: false,
    importBankFlow: false,
    linkBankFlow: false,
    executeBankFlowMatch: false,
    confirmBankFlowMatch: false,
    createFormalBankFlowObject: false,
    addBankFlowImportButton: false,
    importBankFlowFile: false,
    readExcel: false,
    readCsv: false,
    createImportBatch: false,
    executeImportValidation: false,
    enterPendingMatch: false,
    uploadFile: false,
    executeDuplicateBlock: false,
    autoMatch: false,
    manualMatchConfirm: false,
    writeFormalAuditLog: false,
    linkPaymentExecutionPrepare: false,
  },
  writeBusinessDataScope: 'only_payment_execution_prepare_pre_execution_check_simulation_formal_entry_fields_and_demo_prepare_layer_tools',
  timestamp: new Date().toISOString(),
}))

const currentSortText = computed(() => {
  if (!sortState.key) return '当前排序：默认顺序'
  const label = tableColumns.find((item) => item.key === sortState.key)?.label || sortState.key
  return '当前排序：' + label + ' / ' + (sortState.direction === 'desc' ? '降序' : '升序')
})

function refreshRows() {
  rows.value = listPaymentExecutionPrepares()
  sourceRows.value = getPaymentExecutionPrepareSourcesFromPaymentOrderPrepares()
  supplierSettlementSourceRows.value = buildSupplierSettlementSourceRows()
}

async function generateMinimumValidationChain() {
  if (!canGenerateFromSupplierSource.value) {
    notify('当前不满足基于现有来源生成最小验证链路的条件。', 'warning')
    return
  }
  await ElMessageBox.confirm(
    [
      '本操作只在当前浏览器中生成以下准备对象：供应商结算草稿、采购发票准备、应付确认准备、付款申请准备、付款指令准备、付款执行准备。',
      '本操作不会修改采购订单、收货、检验、库存，不会执行付款，不会生成银行流水、付款凭证、正式付款凭证，不会核销，不会写总账。',
      '确认后将基于现有供应商结算来源候选生成一条本地最小验证链路。',
    ].join('\n\n'),
    '确认生成本地最小验证链路',
    {
      confirmButtonText: '确认生成',
      cancelButtonText: '取消',
      type: 'warning',
    },
  )

  minimumChainGenerating.value = true
  try {
    const source = supplierSettlementSourceRows.value[0]
    if (!source) throw new Error('没有可用的供应商结算来源候选。')

    const settlementOutcome = createSupplierSettlementDraft(source, 'minimum-chain-user')
    const settlement = settlementOutcome.settlement
    if (!settlement) throw new Error(settlementOutcome.message || '供应商结算草稿生成失败。')
    if (!settlementOutcome.success && !settlementOutcome.existed) throw new Error(settlementOutcome.message || '供应商结算草稿生成失败。')
    const differenceType = settlement.differenceAmount > 0
      ? 'manual_pending'
      : settlement.reconciliationStatus === 'source_missing'
        ? 'source_missing'
        : 'none'
    ensureSuccess(selectSupplierSettlementDifferenceType(settlement.id, differenceType, '本地最小验证链路：确认差异原因。'), '选择供应商结算差异原因')
    ensureSuccess(confirmSupplierSettlementDifference(settlement.id, '本地最小验证链路：确认差异，仅用于页面衔接验证。'), '确认供应商结算差异')
    ensureSuccess(confirmSupplierSettlementReconciliation(settlement.id, '本地最小验证链路：确认对账，不付款、不核销、不写总账。'), '确认供应商结算对账')

    const invoiceOutcome = createInvoicePrepareFromSupplierSettlement(settlement.id, 'minimum-chain-user')
    ensureSuccess(invoiceOutcome, '生成采购发票准备')
    const invoicePrepare = invoiceOutcome.invoicePrepare
    const invoiceAmount = amountValue(invoicePrepare) || Number(invoicePrepare?.settlementAmount || settlement.settlementAmount || 0)
    ensureSuccess(inputPurchaseInvoiceInfo(invoiceOutcome.invoicePrepareId, {
      invoiceNo: `INV-MIN-${Date.now()}`,
      invoiceDate: todayText(),
      invoiceAmount,
      taxRate: 0,
      taxAmount: 0,
      totalInvoiceAmount: invoiceAmount,
      invoicePrepareRemark: '本地最小验证链路发票信息；不生成正式发票。',
    }, 'minimum-chain-user'), '录入采购发票准备信息')
    ensureSuccess(markPurchaseInvoiceReceived(invoiceOutcome.invoicePrepareId, 'minimum-chain-user'), '标记已收票')
    ensureSuccess(markPurchaseInvoiceChecked(invoiceOutcome.invoicePrepareId, 'minimum-chain-user'), '发票核对通过')

    const payableOutcome = createPayableConfirmFromInvoicePrepare(invoiceOutcome.invoicePrepareId, 'minimum-chain-user')
    ensureSuccess(payableOutcome, '生成应付确认准备')
    ensureSuccess(markPayableConfirmWaiting(payableOutcome.payableConfirmId, 'minimum-chain-user'), '标记应付待确认')
    ensureSuccess(confirmAccountPayable(payableOutcome.payableConfirmId, 'minimum-chain-user'), '确认应付')

    const applicationOutcome = createPaymentApplicationFromPayableConfirm(payableOutcome.payableConfirmId, 'minimum-chain-user')
    ensureSuccess(applicationOutcome, '生成付款申请准备')
    ensureSuccess(markPaymentApplicationWaitingSubmit(applicationOutcome.paymentApplicationId, 'minimum-chain-user'), '标记付款申请待提交')
    ensureSuccess(submitPaymentApplication(applicationOutcome.paymentApplicationId, 'minimum-chain-user'), '提交付款申请')
    ensureSuccess(approvePaymentApplication(applicationOutcome.paymentApplicationId, 'minimum-chain-user'), '审批通过付款申请')

    const orderOutcome = createPaymentOrderPrepareFromPaymentApplication(applicationOutcome.paymentApplicationId, 'minimum-chain-user')
    ensureSuccess(orderOutcome, '生成付款指令准备')
    ensureSuccess(markPaymentOrderPrepareWaitingReview(orderOutcome.paymentOrderPrepareId, 'minimum-chain-user'), '标记付款指令待复核')
    ensureSuccess(reviewPaymentOrderPrepare(orderOutcome.paymentOrderPrepareId, 'minimum-chain-user'), '复核通过付款指令')

    const executionOutcome = createPaymentExecutionPrepareFromPaymentOrderPrepare(orderOutcome.paymentOrderPrepareId, 'minimum-chain-user')
    ensureSuccess(executionOutcome, '生成付款执行准备')
    ensureSuccess(markPaymentExecutionPrepareWaitingReview(executionOutcome.paymentExecutionPrepareId, 'minimum-chain-user'), '标记付款执行准备待复核')
    ensureSuccess(reviewPaymentExecutionPrepare(executionOutcome.paymentExecutionPrepareId, 'minimum-chain-user'), '复核通过付款执行准备')

    const demoGeneratedAt = new Date().toISOString()
    markDemoChainRecords({
      settlementId: settlement.id,
      settlementNo: settlement.settlementNo,
      invoicePrepareId: invoiceOutcome.invoicePrepareId,
      invoicePrepareNo: invoiceOutcome.invoicePrepareNo,
      payableConfirmId: payableOutcome.payableConfirmId,
      payableConfirmNo: payableOutcome.payableConfirmNo,
      paymentApplicationId: applicationOutcome.paymentApplicationId,
      paymentApplicationNo: applicationOutcome.paymentApplicationNo,
      paymentOrderPrepareId: orderOutcome.paymentOrderPrepareId,
      paymentOrderPrepareNo: orderOutcome.paymentOrderPrepareNo,
      paymentExecutionPrepareId: executionOutcome.paymentExecutionPrepareId,
      paymentExecutionPrepareNo: executionOutcome.paymentExecutionPrepareNo,
    }, demoGeneratedAt)

    minimumChainResult.value = {
      settlementNo: settlement.settlementNo,
      invoicePrepareNo: invoiceOutcome.invoicePrepareNo,
      payableConfirmNo: payableOutcome.payableConfirmNo,
      paymentApplicationNo: applicationOutcome.paymentApplicationNo,
      paymentOrderPrepareNo: orderOutcome.paymentOrderPrepareNo,
      paymentExecutionPrepareNo: executionOutcome.paymentExecutionPrepareNo,
    }
    refreshRows()
    notify('已生成本地最小验证链路；仍未真实付款、未生成银行流水、未生成凭证、未核销、未写总账。')
  } catch (error) {
    notify(error?.message || '最小验证链路生成失败。', 'warning')
  } finally {
    minimumChainGenerating.value = false
  }
}

async function clearDemoPrepareLayerData() {
  await ElMessageBox.confirm(
    [
      '本操作只清理以下本地演示数据：',
      '供应商结算对象、采购发票准备对象、应付确认准备对象、付款申请准备对象、付款指令准备对象、付款执行准备对象。',
      '本操作不会清理采购订单、收货记录、检验记录、库存流水、应付预备源数据、业务追踪数据、P2P验证数据。',
      '本操作不会真实付款，不会生成银行流水，不会生成付款凭证，不会生成正式付款凭证，不会核销，不会写总账。',
      '确认清理后，可以基于现有来源候选重新生成最小验证链路。',
    ].join('\n\n'),
    '确认清理准备层演示数据',
    {
      confirmButtonText: '确认清理',
      cancelButtonText: '取消',
      type: 'warning',
    },
  )
  saveSupplierSettlementState({
    supplierSettlements: getSupplierSettlementState().supplierSettlements.filter((item) => !item.isDemoChain),
  })
  saveInvoicePrepareState({
    invoicePrepares: getInvoicePrepareState().invoicePrepares.filter((item) => !item.isDemoChain),
  })
  saveAccountPayableConfirmState({
    accountPayableConfirms: getAccountPayableConfirmState().accountPayableConfirms.filter((item) => !item.isDemoChain),
  })
  savePaymentApplicationState({
    paymentApplications: getPaymentApplicationState().paymentApplications.filter((item) => !item.isDemoChain),
  })
  savePaymentInstructionPrepareState({
    paymentOrderPrepares: getPaymentInstructionPrepareState().paymentOrderPrepares.filter((item) => !item.isDemoChain),
  })
  savePaymentExecutionPrepareState({
    paymentExecutionPrepares: listPaymentExecutionPrepares().filter((item) => !item.isDemoChain),
  })
  minimumChainResult.value = null
  selectedRows.value = []
  clearSort()
  refreshRows()
  notify('准备层演示数据已清理，可以重新生成最小验证链路。')
}

function ensureSuccess(outcome, label) {
  if (!outcome?.success) {
    throw new Error(`${label}失败：${outcome?.error || outcome?.message || '未知原因'}`)
  }
  return outcome
}

function todayText() {
  return new Date().toISOString().slice(0, 10)
}

function demoMeta(generatedAt = new Date().toISOString()) {
  return {
    isDemoChain: true,
    demoChainVersion: DEMO_CHAIN_VERSION,
    demoChainGeneratedAt: generatedAt,
    demoChainPurpose: DEMO_CHAIN_PURPOSE,
  }
}

function markDemoChainRecords(chain = {}, generatedAt = new Date().toISOString()) {
  const meta = demoMeta(generatedAt)
  const match = (item, idKey, noKey, idValue, noValue) => (
    (idValue && String(item[idKey] || '') === String(idValue))
    || (noValue && String(item[noKey] || '') === String(noValue))
  )
  saveSupplierSettlementState({
    supplierSettlements: getSupplierSettlementState().supplierSettlements.map((item) => (
      match(item, 'id', 'settlementNo', chain.settlementId, chain.settlementNo) ? { ...item, ...meta } : item
    )),
  })
  saveInvoicePrepareState({
    invoicePrepares: getInvoicePrepareState().invoicePrepares.map((item) => (
      match(item, 'id', 'invoicePrepareNo', chain.invoicePrepareId, chain.invoicePrepareNo) ? { ...item, ...meta } : item
    )),
  })
  saveAccountPayableConfirmState({
    accountPayableConfirms: getAccountPayableConfirmState().accountPayableConfirms.map((item) => (
      match(item, 'id', 'payableConfirmNo', chain.payableConfirmId, chain.payableConfirmNo) ? { ...item, ...meta } : item
    )),
  })
  savePaymentApplicationState({
    paymentApplications: getPaymentApplicationState().paymentApplications.map((item) => (
      match(item, 'id', 'paymentApplicationNo', chain.paymentApplicationId, chain.paymentApplicationNo) ? { ...item, ...meta } : item
    )),
  })
  savePaymentInstructionPrepareState({
    paymentOrderPrepares: getPaymentInstructionPrepareState().paymentOrderPrepares.map((item) => (
      match(item, 'id', 'paymentOrderPrepareNo', chain.paymentOrderPrepareId, chain.paymentOrderPrepareNo) ? { ...item, ...meta } : item
    )),
  })
  savePaymentExecutionPrepareState({
    paymentExecutionPrepares: listPaymentExecutionPrepares().map((item) => (
      match(item, 'id', 'paymentExecutionPrepareNo', chain.paymentExecutionPrepareId, chain.paymentExecutionPrepareNo) ? { ...item, ...meta } : item
    )),
  })
}

function markVisibleChainAsDemo() {
  const chain = currentChainNos.value
  if (!chain.paymentExecutionPrepareNo) return
  markDemoChainRecords({
    settlementNo: chain.settlementNo,
    invoicePrepareNo: chain.invoicePrepareNo,
    payableConfirmNo: chain.payableConfirmNo,
    paymentApplicationNo: chain.paymentApplicationNo,
    paymentOrderPrepareNo: chain.paymentOrderPrepareNo,
    paymentExecutionPrepareNo: chain.paymentExecutionPrepareNo,
  })
  refreshRows()
}

function buildPaymentExecutionDisplayRows(baseRows = [], sources = []) {
  const normalized = baseRows.map((item) => ({ ...item, displaySource: 'paymentExecutionPrepareStore' }))
  const existedNos = new Set(normalized.map((item) => item.paymentExecutionPrepareNo).filter(Boolean))
  const recovered = sources
    .filter((item) => item.linkedPaymentExecutionPrepareNo && !existedNos.has(item.linkedPaymentExecutionPrepareNo))
    .map((item) => ({
      id: item.linkedPaymentExecutionPrepareId || `readonly-${item.linkedPaymentExecutionPrepareNo}`,
      paymentExecutionPrepareNo: item.linkedPaymentExecutionPrepareNo,
      sourcePaymentOrderPrepareId: item.id || '',
      sourcePaymentOrderPrepareNo: item.paymentOrderPrepareNo || '',
      sourcePaymentApplicationNo: item.sourcePaymentApplicationNo || '',
      sourcePayableConfirmNo: item.sourcePayableConfirmNo || '',
      sourceInvoicePrepareNo: item.sourceInvoicePrepareNo || '',
      sourceSettlementNo: item.sourceSettlementNo || '',
      supplierId: item.supplierId || '',
      supplierName: item.supplierName || '',
      purchaseOrderNo: item.purchaseOrderNo || '',
      invoiceNo: item.invoiceNo || '',
      orderAmount: amountValue(item),
      executionAmount: amountValue(item),
      currency: item.currency || 'CNY',
      paymentMethod: item.paymentMethod || 'bank_transfer',
      plannedPaymentDate: item.plannedPaymentDate || '',
      paymentPriority: item.paymentPriority || 'normal',
      paymentPurpose: item.paymentPurpose || '付款指令签发后的付款执行准备',
      payeeName: item.payeeName || item.supplierName || '',
      payeeBankName: item.payeeBankName || '',
      payeeBankAccount: item.payeeBankAccount || '',
      payerAccountName: item.payerAccountName || '',
      payerBankName: item.payerBankName || '',
      payerBankAccount: item.payerBankAccount || '',
      paymentExecutionPrepareStatus: item.paymentExecutionPrepareStatus || 'reviewed',
      paymentExecutionStatus: item.paymentExecutionStatus || 'not_executed',
      bankFlowStatus: item.bankFlowStatus || 'not_generated',
      paymentVoucherStatus: item.paymentVoucherStatus || 'not_generated',
      formalPaymentVoucherStatus: item.formalPaymentVoucherStatus || 'not_generated',
      writeOffStatus: item.writeOffStatus || 'not_written_off',
      ledgerStatus: item.ledgerStatus || 'not_written_ledger',
      postingStatus: item.postingStatus || 'not_posted',
      executionRiskStatus: item.executionRiskStatus || 'not_checked',
      preExecutionCheckStatus: item.preExecutionCheckStatus || 'not_checked',
      preExecutionRiskStatus: item.preExecutionRiskStatus || 'warning',
      preExecutionReady: Boolean(item.preExecutionReady),
      preExecutionBlocked: Boolean(item.preExecutionBlocked),
      preExecutionBlockReasons: Array.isArray(item.preExecutionBlockReasons) ? item.preExecutionBlockReasons : [],
      preExecutionWarnings: Array.isArray(item.preExecutionWarnings) ? item.preExecutionWarnings : [],
      paymentExecutionSimulationStatus: item.paymentExecutionSimulationStatus || 'not_simulated',
      paymentExecutionSimulated: Boolean(item.paymentExecutionSimulated),
      paymentExecutionSimulatedAt: item.paymentExecutionSimulatedAt || '',
      paymentExecutionSimulatedBy: item.paymentExecutionSimulatedBy || '',
      paymentExecutionSimulationResult: item.paymentExecutionSimulationResult || '',
      paymentExecutionSimulationWarnings: Array.isArray(item.paymentExecutionSimulationWarnings) ? item.paymentExecutionSimulationWarnings : [],
      paymentExecutionSimulationBlockReasons: Array.isArray(item.paymentExecutionSimulationBlockReasons) ? item.paymentExecutionSimulationBlockReasons : [],
      paymentExecutionSimulationLogs: Array.isArray(item.paymentExecutionSimulationLogs) ? item.paymentExecutionSimulationLogs : [],
      formalExecutionEntryStatus: item.formalExecutionEntryStatus || 'not_ready',
      formalExecutionEntryReady: Boolean(item.formalExecutionEntryReady),
      formalExecutionEntryBlocked: Boolean(item.formalExecutionEntryBlocked),
      formalExecutionEntryBlockReasons: Array.isArray(item.formalExecutionEntryBlockReasons) ? item.formalExecutionEntryBlockReasons : [],
      formalExecutionEntryWarnings: Array.isArray(item.formalExecutionEntryWarnings) ? item.formalExecutionEntryWarnings : [],
      formalExecutionEntryReviewedAt: item.formalExecutionEntryReviewedAt || '',
      formalExecutionEntryReviewedBy: item.formalExecutionEntryReviewedBy || '',
      formalExecutionEntryPreviewCount: Number(item.formalExecutionEntryPreviewCount || 0),
      formalExecutionEntryLogs: Array.isArray(item.formalExecutionEntryLogs) ? item.formalExecutionEntryLogs : [],
      actualPaymentExecutionEnabled: false,
      createdAt: item.paymentExecutionPrepareGeneratedAt || item.updatedAt || item.createdAt || '',
      remark: '由付款指令准备来源关联只读恢复显示；不写入付款执行准备 store。',
      displaySource: 'paymentOrderPrepareLinkedReadonly',
      readonlyRecovered: true,
      isRecoveredFromLinkedSource: true,
      recoveredSource: 'paymentInstructionPrepareStore',
    }))
  return [...normalized, ...recovered]
}

function applyFormalEntryPreviewDecision(row = {}) {
  const decision = getFormalExecutionEntryDecision(row)
  const wasPreviewConfirmed = row.formalExecutionEntryStatus === 'reviewed_only'
  return {
    ...row,
    ...decision,
    formalExecutionEntryStatus: wasPreviewConfirmed && decision.formalExecutionEntryReady ? 'reviewed_only' : decision.formalExecutionEntryStatus,
    formalExecutionEntryPreviewCount: Number(row.formalExecutionEntryPreviewCount || 0),
    formalExecutionEntryReviewedAt: row.formalExecutionEntryReviewedAt || '',
    formalExecutionEntryReviewedBy: row.formalExecutionEntryReviewedBy || '',
    formalExecutionEntryLogs: Array.isArray(row.formalExecutionEntryLogs) ? row.formalExecutionEntryLogs : [],
    actualPaymentExecutionEnabled: false,
    finalPaymentExecutionReviewStatus: '已评审，仍不付款',
    recommendDirectPayment: false,
    canStartRealPaymentDevelopment: Boolean(row.paymentExecutionPrepareNo && row.preExecutionReady && ['simulated_ready', 'simulated_warning'].includes(row.paymentExecutionSimulationStatus)),
    demoDataUsableForRealPayment: false,
    realPaymentImpactDesignStatus: '已形成状态影响设计，本轮不执行真实付款',
    paymentExecutionStatusChangedThisRound: false,
    bankFlowStatusChangedThisRound: false,
    paymentVoucherStatusChangedThisRound: false,
    writeOffStatusChangedThisRound: false,
    ledgerStatusChangedThisRound: false,
    downstreamModulesWrittenThisRound: false,
    bankFlowBoundaryDesignStatus: '已形成银行流水生成 / 导入边界设计，本轮不生成、不导入、不关联银行流水',
    bankFlowGeneratedThisRound: false,
    bankFlowImportedThisRound: false,
    bankFlowLinkedThisRound: false,
    bankFlowMatchedThisRound: false,
    bankFlowMatchConfirmedThisRound: false,
    bankFlowStatusChangedThisRoundForBoundary: false,
    bankFlowDownstreamWrittenThisRound: false,
    bankFlowObjectDesignStatus: '已形成银行流水真实对象与导入校验设计，本轮不创建真实对象、不导入文件',
    bankFlowFormalObjectCreatedThisRound: false,
    bankFlowImportButtonAddedThisRound: false,
    bankFlowFileImportedThisRound: false,
    bankFlowExcelReadThisRound: false,
    bankFlowCsvReadThisRound: false,
    bankFlowImportBatchCreatedThisRound: false,
    bankFlowImportValidationExecutedThisRound: false,
    bankFlowEnteredPendingMatchThisRound: false,
    bankFlowReadonlyPreviewStatus: '已生成只读预览，本轮不写正式银行流水',
    bankFlowFileUploadedThisRound: false,
    bankFlowDuplicateBlockExecutedThisRound: false,
    bankFlowAutoMatchedThisRound: false,
    bankFlowManualMatchConfirmedThisRound: false,
    bankFlowFormalAuditLogWrittenThisRound: false,
    bankFlowReadonlyPreviewGenerated: true,
  }
}

function handleSelectionChange(selection) {
  selectedRows.value = selection || []
}

function clearSelection() {
  paymentExecutionPrepareTableRef.value?.clearSelection?.()
  selectedRows.value = []
}

function clearFilters() {
  quickSearch.value = ''
  Object.keys(filterState).forEach((key) => {
    filterState[key] = key === 'dateRange' ? [] : ''
  })
  clearSelection()
}

function matchFilters(row) {
  const q = quickSearch.value.trim().toLowerCase()
  if (q && ![
    row.paymentExecutionPrepareNo,
    row.sourcePaymentOrderPrepareNo,
    row.sourcePaymentApplicationNo,
    row.sourcePayableConfirmNo,
    row.supplierName,
    row.supplierId,
    row.purchaseOrderNo,
    row.invoiceNo,
    prepareStatusLabel(row.paymentExecutionPrepareStatus),
    statusLabel(row.paymentExecutionStatus),
  ].join(' ').toLowerCase().includes(q)) return false
  const fields = [
    ['paymentExecutionPrepareNo', [row.paymentExecutionPrepareNo]],
    ['sourcePaymentOrderPrepareNo', [row.sourcePaymentOrderPrepareNo]],
    ['sourcePaymentApplicationNo', [row.sourcePaymentApplicationNo]],
    ['sourcePayableConfirmNo', [row.sourcePayableConfirmNo]],
    ['supplier', [row.supplierName, row.supplierId]],
    ['purchaseOrderNo', [row.purchaseOrderNo]],
    ['invoiceNo', [row.invoiceNo]],
  ]
  const keywordMatched = fields.every(([key, values]) => {
    const keyword = String(filterState[key] || '').trim().toLowerCase()
    if (!keyword) return true
    return values.some((value) => String(value || '').toLowerCase().includes(keyword))
  })
  if (!keywordMatched) return false
  if (filterState.paymentExecutionPrepareStatus && row.paymentExecutionPrepareStatus !== filterState.paymentExecutionPrepareStatus) return false
  if (filterState.paymentExecutionStatus && row.paymentExecutionStatus !== filterState.paymentExecutionStatus) return false
  if (Array.isArray(filterState.dateRange) && filterState.dateRange.length === 2 && row.createdAt) {
    const date = String(row.createdAt).slice(0, 10)
    if (date < filterState.dateRange[0] || date > filterState.dateRange[1]) return false
  }
  return true
}

function toggleSort(key) {
  if (sortState.key !== key) {
    sortState.key = key
    sortState.direction = 'asc'
    return
  }
  if (sortState.direction === 'asc') {
    sortState.direction = 'desc'
    return
  }
  clearSort()
}

function clearSort() {
  sortState.key = ''
  sortState.direction = ''
  clearSelection()
}

function sortMark(key) {
  if (sortState.key !== key) return '▲▼'
  return sortState.direction === 'desc' ? '▼' : '▲'
}

function sortRows(list, state) {
  if (!state.key || !state.direction) return list
  const direction = state.direction === 'desc' ? -1 : 1
  return [...list].sort((a, b) => compareValue(a[state.key], b[state.key]) * direction)
}

function compareValue(a, b) {
  const leftNumber = Number(a)
  const rightNumber = Number(b)
  if (Number.isFinite(leftNumber) && Number.isFinite(rightNumber)) return leftNumber - rightNumber
  return String(a || '').localeCompare(String(b || ''), 'zh-Hans-CN')
}

function amountValue(item = {}) {
  const candidates = [item.executionAmount, item.orderAmount, item.amount, item.prepareAmount, item.approvedAmount]
  for (const value of candidates) {
    const number = Number(value)
    if (Number.isFinite(number) && number > 0) return number
  }
  return 0
}

function recalculate(row) {
  const outcome = recalculatePaymentExecutionPrepareAmount(row.id)
  if (!outcome.success) return notify(outcome.error, 'warning')
  refreshRows()
  notify('已重算付款执行准备金额')
}

function openEdit(row) {
  editTargetId.value = row.id
  editForm.executionAmount = Number(row.executionAmount || 0)
  editForm.paymentMethod = row.paymentMethod || 'bank_transfer'
  editForm.plannedPaymentDate = row.plannedPaymentDate || ''
  editForm.paymentPriority = row.paymentPriority || 'normal'
  editForm.paymentPurpose = row.paymentPurpose || ''
  editForm.payeeName = row.payeeName || ''
  editForm.payeeBankName = row.payeeBankName || ''
  editForm.payeeBankAccount = row.payeeBankAccount || ''
  editForm.payerAccountName = row.payerAccountName || ''
  editForm.payerBankName = row.payerBankName || ''
  editForm.payerBankAccount = row.payerBankAccount || ''
  editForm.remark = row.remark || ''
  editVisible.value = true
}

function saveEdit() {
  const outcome = updatePaymentExecutionPrepareInfo(editTargetId.value, { ...editForm })
  if (!outcome.success) return notify(outcome.error, 'warning')
  editVisible.value = false
  refreshRows()
  notify('已保存付款执行准备信息')
}

function markWaiting(row) {
  const outcome = markPaymentExecutionPrepareWaitingReview(row.id)
  if (!outcome.success) return notify(outcome.error, 'warning')
  refreshRows()
  notify('已标记付款执行准备待复核')
}

function review(row) {
  const outcome = reviewPaymentExecutionPrepare(row.id)
  if (!outcome.success) return notify(outcome.error, 'warning')
  refreshRows()
  notify('已复核通过；仍未真实付款')
}

function runPreExecutionCheck(row) {
  const outcome = runPaymentExecutionPreExecutionCheck(row.id)
  if (!outcome.success) return notify(outcome.error, 'warning')
  refreshRows()
  notify(outcome.decision?.preExecutionReady ? '付款执行前安全检查通过；仍未执行付款' : '付款执行前安全检查已阻断', outcome.decision?.preExecutionReady ? 'success' : 'warning')
}

function runCurrentResultPreExecutionChecks() {
  filteredRows.value.forEach((row) => {
    if (!row.readonlyRecovered) runPaymentExecutionPreExecutionCheck(row.id)
  })
  refreshRows()
  notify('已完成当前结果付款执行前安全检查；仍未执行付款')
}

function openEntryPreview(row) {
  const outcome = openPaymentExecutionEntryPreview(row.id)
  refreshRows()
  if (!outcome.success) return notify(outcome.error || '付款执行入口预览被阻断。', 'warning')
  preExecutionPreviewRow.value = outcome.paymentExecutionPrepare
  preExecutionPreviewVisible.value = true
}

function confirmEntryPreviewNoExecution() {
  if (preExecutionPreviewRow.value?.id) {
    confirmPaymentExecutionEntryPreviewNoExecution(preExecutionPreviewRow.value.id)
  }
  preExecutionPreviewVisible.value = false
  refreshRows()
  notify('已确认本轮仅预览入口，不执行付款')
}

function canRunPaymentExecutionSimulation(row = {}) {
  return Boolean(
    row.preExecutionReady
    && !row.preExecutionBlocked
    && row.paymentExecutionPrepareStatus === 'reviewed'
    && row.paymentExecutionStatus === 'not_executed'
    && row.bankFlowStatus === 'not_generated'
    && row.paymentVoucherStatus === 'not_generated'
    && row.formalPaymentVoucherStatus === 'not_generated'
    && row.writeOffStatus === 'not_written_off'
    && row.ledgerStatus === 'not_written_ledger'
    && row.postingStatus === 'not_posted'
    && Number(row.executionAmount || 0) > 0
    && !row.readonlyRecovered
  )
}

async function confirmRunPaymentExecutionSimulation(row) {
  if (!canRunPaymentExecutionSimulation(row)) {
    notify(paymentExecutionSimulationDisabledReason(row), 'warning')
    return
  }
  await ElMessageBox.confirm(
    [
      '本操作只是模拟付款执行。',
      '不会真实付款。',
      '不会生成银行流水。',
      '不会生成付款凭证。',
      '不会生成正式付款凭证。',
      '不会核销。',
      '不会写总账。',
      '不会改变真实付款执行状态。',
      '确认后只写付款执行准备对象中的模拟字段和模拟日志。',
    ].join('\n\n'),
    '确认模拟付款执行',
    {
      confirmButtonText: '确认模拟，不执行付款',
      cancelButtonText: '取消',
      type: 'warning',
    },
  )
  const outcome = runPaymentExecutionSimulation(row.id)
  if (!outcome.success) return notify(outcome.error, 'warning')
  refreshRows()
  notify(outcome.decision?.paymentExecutionSimulationStatus === 'simulated_blocked' ? '付款执行模拟被阻断' : '付款执行模拟已完成；未真实付款', outcome.decision?.paymentExecutionSimulationStatus === 'simulated_blocked' ? 'warning' : 'success')
}

function paymentExecutionSimulationDisabledReason(row = {}) {
  if (row.readonlyRecovered) return '只读恢复记录不能写入模拟字段。'
  if (!row.preExecutionReady) return '付款执行前安全检查未通过，不能模拟付款执行。'
  if (row.preExecutionBlocked) return '付款执行前安全检查已阻断，不能模拟付款执行。'
  if (row.paymentExecutionPrepareStatus !== 'reviewed') return '付款执行准备尚未复核通过，不能模拟付款执行。'
  if (row.paymentExecutionStatus !== 'not_executed') return '真实付款执行状态不是未执行，不能模拟付款执行。'
  if (row.bankFlowStatus !== 'not_generated') return '银行流水状态不是未生成，不能模拟付款执行。'
  if (row.paymentVoucherStatus !== 'not_generated') return '付款凭证状态不是未生成，不能模拟付款执行。'
  if (row.formalPaymentVoucherStatus !== 'not_generated') return '正式付款凭证状态不是未生成，不能模拟付款执行。'
  if (row.writeOffStatus !== 'not_written_off') return '核销状态不是未核销，不能模拟付款执行。'
  if (row.ledgerStatus !== 'not_written_ledger') return '总账状态不是未写总账，不能模拟付款执行。'
  if (row.postingStatus !== 'not_posted') return '过账状态不是未过账，不能模拟付款执行。'
  if (Number(row.executionAmount || 0) <= 0) return '执行准备金额为空或为 0，不能模拟付款执行。'
  return '当前记录不满足付款执行模拟条件。'
}

function runFormalEntryCheck(row) {
  if (row.readonlyRecovered) return notify('只读恢复记录不能写入正式入口字段。', 'warning')
  const outcome = runFormalExecutionEntryCheck(row.id)
  if (!outcome.success) return notify(outcome.error, 'warning')
  refreshRows()
  notify(outcome.decision?.formalExecutionEntryReady ? '正式付款执行入口预览已允许；真实付款功能仍关闭' : '正式付款执行入口预览已阻断', outcome.decision?.formalExecutionEntryReady ? 'success' : 'warning')
}

function openFormalEntryPreview(row) {
  const outcome = openFormalExecutionEntryPreview(row.id)
  refreshRows()
  if (!outcome.success) return notify(outcome.error || '正式付款执行入口预览被阻断。', 'warning')
  formalEntryPreviewRow.value = outcome.paymentExecutionPrepare
  formalEntryPreviewVisible.value = true
}

function openBankFlowImportValidationPreview(row) {
  if (!row?.paymentExecutionPrepareNo) {
    return notify('当前记录缺少付款执行准备单号，无法打开银行流水导入校验预览。', 'warning')
  }
  router.push(`/finance/bank-flow-import-validation-preview/${row.paymentExecutionPrepareNo}`)
}

function openPaymentVoucherPreparePreview(row) {
  if (!row?.paymentExecutionPrepareNo) {
    return notify('当前记录缺少付款执行准备单号，无法打开付款凭证准备预览。', 'warning')
  }
  router.push(`/finance/payment-voucher-prepare-preview/${row.paymentExecutionPrepareNo}`)
}

function jumpToAcceptanceSection(targetId) {
  document.getElementById(targetId)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function confirmFormalEntryPreviewNoExecution() {
  if (formalEntryPreviewRow.value?.id) {
    confirmFormalExecutionEntryPreviewNoExecution(formalEntryPreviewRow.value.id)
  }
  formalEntryPreviewVisible.value = false
  refreshRows()
  notify('已确认本轮仅预览正式付款执行入口，不执行付款')
}

function generateFromSource(row) {
  const outcome = createPaymentExecutionPrepareFromPaymentOrderPrepare(row.id)
  if (!outcome.success) return notify(outcome.error, 'warning')
  refreshRows()
  notify('已生成付款执行准备 ' + outcome.paymentExecutionPrepareNo + '；仍未真实付款')
}

function block(row) {
  const outcome = blockPaymentExecutionPrepare(row.id)
  if (!outcome.success) return notify(outcome.error, 'warning')
  refreshRows()
  notify('已阻断付款执行准备', 'warning')
}

function close(row) {
  const outcome = closePaymentExecutionPrepare(row.id)
  if (!outcome.success) return notify(outcome.error, 'warning')
  refreshRows()
  notify('已关闭付款执行准备')
}

async function viewLogs(row) {
  const logs = [
    ...(row.logs || []),
    ...(row.preExecutionLogs || []),
    ...(row.paymentExecutionSimulationLogs || []),
    ...(row.formalExecutionEntryLogs || []),
  ]
  const message = logs.length
    ? logs.map((item) => {
      const before = item.beforeStatus ?? item.beforeSimulationStatus ?? '-'
      const after = item.afterStatus ?? item.afterSimulationStatus ?? '-'
      return `${item.time || '-'} / ${item.action || '-'} / ${before} -> ${after} / ${item.remark || '-'}`
    }).join('\n')
    : '暂无付款执行准备日志'
  await ElMessageBox.alert(message, '付款执行准备日志', { confirmButtonText: '关闭' })
}

function prepareStatusLabel(status) {
  return {
    draft: '草稿',
    waiting_execution_review: '待执行复核',
    reviewed: '已复核',
    blocked: '阻断',
    closed: '已关闭',
  }[status] || status || '-'
}

function sourcePaymentOrderStatusLabel(status) {
  return {
    draft: '草稿',
    waiting_review: '待复核',
    reviewed: '已复核',
    blocked: '阻断',
    closed: '已关闭',
  }[status] || status || '-'
}

function sourcePaymentInstructionStatusLabel(status) {
  return {
    not_issued: '未签发',
    ready_to_issue: '可签发付款指令',
    issued_for_execution: '已签发到执行准备',
    blocked: '阻断',
  }[status] || status || '-'
}

function prepareStatusType(status) {
  return {
    draft: 'info',
    waiting_execution_review: 'warning',
    reviewed: 'success',
    blocked: 'danger',
    closed: 'info',
  }[status] || 'info'
}

function paymentMethodLabel(value) {
  return {
    bank_transfer: '银行转账',
    bank_acceptance: '承兑汇票',
    cash: '现金',
  }[value] || value || '-'
}

function paymentPriorityLabel(value) {
  return {
    normal: '普通',
    high: '高',
    urgent: '紧急',
  }[value] || value || '-'
}

function statusLabel(value) {
  return {
    not_executed: '未执行',
    not_generated: '未生成',
    not_written_off: '未核销',
    not_written_ledger: '未写总账',
    not_posted: '未过账',
    not_checked: '未检查',
    blocked: '阻断',
  }[value] || value || '-'
}

function preExecutionCheckStatusLabel(value) {
  return {
    not_checked: '未检查',
    checked: '已检查',
    blocked: '已阻断',
  }[value] || value || '-'
}

function preExecutionRiskStatusLabel(value) {
  return {
    normal: '正常',
    warning: '提醒',
    blocked: '阻断',
  }[value] || value || '-'
}

function paymentExecutionSimulationStatusLabel(value) {
  return {
    not_simulated: '未模拟',
    simulated_ready: '模拟通过',
    simulated_warning: '模拟警告',
    simulated_blocked: '模拟阻断',
  }[value] || value || '-'
}

function formalExecutionEntryStatusLabel(value) {
  return {
    not_ready: '未就绪',
    preview_ready: '可预览，真实付款关闭',
    entry_ready: '允许预览',
    blocked: '已阻断',
    reviewed_only: '仅预览确认',
  }[value] || value || '-'
}

function listText(value) {
  return Array.isArray(value) ? value.filter(Boolean).join('；') : value || ''
}

function formatCell(row, key) {
  const value = row[key]
  if (['orderAmount', 'executionAmount'].includes(key)) return formatAmount(value)
  if (key === 'paymentMethod') return paymentMethodLabel(value)
  if (key === 'paymentPriority') return paymentPriorityLabel(value)
  if (['paymentExecutionStatus', 'bankFlowStatus', 'paymentVoucherStatus', 'formalPaymentVoucherStatus', 'writeOffStatus', 'ledgerStatus', 'postingStatus', 'executionRiskStatus'].includes(key)) return statusLabel(value)
  if (key === 'preExecutionCheckStatus') return preExecutionCheckStatusLabel(value)
  if (key === 'preExecutionRiskStatus') return preExecutionRiskStatusLabel(value)
  if (key === 'preExecutionReady') return row.preExecutionReady ? '允许进入付款执行入口预览' : '不允许进入付款执行入口'
  if (['preExecutionBlockReasons', 'preExecutionWarnings'].includes(key)) return listText(value) || '-'
  if (key === 'paymentExecutionSimulationStatus') return paymentExecutionSimulationStatusLabel(value)
  if (key === 'paymentExecutionSimulated') return row.paymentExecutionSimulated ? '已模拟' : '未模拟'
  if (['paymentExecutionSimulationWarnings', 'paymentExecutionSimulationBlockReasons'].includes(key)) return listText(value) || '-'
  if (key === 'formalExecutionEntryStatus') return formalExecutionEntryStatusLabel(value)
  if (key === 'formalExecutionEntryReady') return row.formalExecutionEntryReady ? '允许进入正式付款入口预览' : '不允许进入正式付款入口预览'
  if (key === 'actualPaymentExecutionEnabled') return row.actualPaymentExecutionEnabled ? '是' : '否'
  if (key === 'formalExecutionEntryBlockReasons') return listText(value) || '-'
  if (key === 'recommendDirectPayment') return row.recommendDirectPayment ? '是' : '否'
  if (key === 'canStartRealPaymentDevelopment') return row.canStartRealPaymentDevelopment ? '可以进入前置设计评估' : '暂不建议'
  if (key === 'isDemoChain') return row.isDemoChain ? '是' : '否'
  if (key === 'demoDataUsableForRealPayment') return row.demoDataUsableForRealPayment ? '是' : '否'
  if ([
    'paymentExecutionStatusChangedThisRound',
    'bankFlowStatusChangedThisRound',
    'paymentVoucherStatusChangedThisRound',
    'writeOffStatusChangedThisRound',
    'ledgerStatusChangedThisRound',
    'downstreamModulesWrittenThisRound',
    'bankFlowGeneratedThisRound',
    'bankFlowImportedThisRound',
    'bankFlowLinkedThisRound',
    'bankFlowMatchedThisRound',
    'bankFlowMatchConfirmedThisRound',
    'bankFlowStatusChangedThisRoundForBoundary',
    'bankFlowDownstreamWrittenThisRound',
    'bankFlowFormalObjectCreatedThisRound',
    'bankFlowImportButtonAddedThisRound',
    'bankFlowFileImportedThisRound',
    'bankFlowExcelReadThisRound',
    'bankFlowCsvReadThisRound',
    'bankFlowImportBatchCreatedThisRound',
    'bankFlowImportValidationExecutedThisRound',
    'bankFlowEnteredPendingMatchThisRound',
    'bankFlowFileUploadedThisRound',
    'bankFlowDuplicateBlockExecutedThisRound',
    'bankFlowAutoMatchedThisRound',
    'bankFlowManualMatchConfirmedThisRound',
    'bankFlowFormalAuditLogWrittenThisRound',
    'bankFlowReadonlyPreviewGenerated',
  ].includes(key)) return row[key] ? '是' : '否'
  return value || '-'
}

function formatAmount(value) {
  return Number(value || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function round(value) {
  return Math.round(Number(value || 0) * 100) / 100
}

function exportCurrentResults() {
  const csv = [
    paymentExecutionPrepareExportColumns.map((column) => column.label),
    ...filteredRows.value.map((row) => paymentExecutionPrepareExportColumns.map((column) => formatExportCell(row, column.key))),
  ].map((line) => line.map((value) => `"${String(value ?? '').replace(/"/g, '""')}"`).join(',')).join('\n')
  const blob = new Blob([`\uFEFF${csv}`], { type: 'text/csv;charset=utf-8;' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = `payment-execution-prepares-${new Date().toISOString().slice(0, 10).replace(/-/g, '')}.csv`
  link.click()
  URL.revokeObjectURL(link.href)
}

function formatExportCell(row, key) {
  if (key === 'paymentExecutionPrepareStatus') return prepareStatusLabel(row[key])
  return formatCell(row, key)
}

async function copyDiagnosticData() {
  const text = JSON.stringify(diagnosticData.value, null, 2)
  try {
    if (navigator?.clipboard?.writeText) await navigator.clipboard.writeText(text)
    else fallbackCopy(text)
    notify('已复制付款执行准备诊断数据')
  } catch (error) {
    fallbackCopy(text)
    notify('已复制付款执行准备诊断数据')
  }
}

async function copyPageAcceptanceChecklist() {
  const text = buildPageAcceptanceChecklist({
    fullUrl: currentFullUrl.value,
    version: VERSION,
    pageTitle: '付款执行准备',
    sourceObjectNo: '付款执行准备列表',
    targetObjectNo: '目标对象编号由付款凭证准备预览页读取，不使用 PEP 来源号替代',
    targetEvidenceStatus: '人工最终复核三项：列表入口可用、表格滚动正常、目标证据语义正确',
    nextStepAllowed: '否',
    nextStepBlockReason: '本页仅用于人工验收和付款前准备展示，不执行真实付款。',
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

markVisibleChainAsDemo()
</script>

<style scoped>
.payment-execution-prepare-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
  min-width: 0;
  max-width: 100%;
}

.page-actions,
.toolbar-buttons,
.row-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.boundary-card,
.toolbar-card,
.table-card {
  padding: 16px;
  border: 1px solid var(--app-border, #d8dee8);
  border-radius: 8px;
  background: #fff;
  min-width: 0;
  max-width: 100%;
  overflow-x: hidden;
  box-sizing: border-box;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 12px;
}

.summary-card {
  padding: 14px;
  border: 1px solid var(--app-border, #d8dee8);
  border-radius: 8px;
  background: #fff;
  display: grid;
  gap: 6px;
}

.summary-card strong {
  font-size: 22px;
}

.summary-card small {
  color: #667085;
}

:deep(.payment-execution-prepare-main-table .el-table-fixed-column--left),
:deep(.payment-execution-prepare-main-table .el-table-fixed-column--right),
:deep(.payment-execution-prepare-main-table .el-table__cell.is-left),
:deep(.payment-execution-prepare-main-table .el-table__cell.is-right) {
  background: #fff;
  z-index: 4;
}

:deep(.payment-execution-prepare-main-table .el-table__header .el-table-fixed-column--left),
:deep(.payment-execution-prepare-main-table .el-table__header .el-table-fixed-column--right),
:deep(.payment-execution-prepare-main-table th.el-table__cell.is-left),
:deep(.payment-execution-prepare-main-table th.el-table__cell.is-right) {
  background: #f8fafc;
  z-index: 5;
}

:deep(.payment-execution-prepare-main-table .payment-fixed-no-column) {
  box-shadow: 8px 0 12px -12px rgba(15, 23, 42, 0.45);
}

:deep(.payment-execution-prepare-main-table .payment-fixed-action-column) {
  box-shadow: -8px 0 12px -12px rgba(15, 23, 42, 0.45);
}

.toolbar-title,
.table-title {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  margin-bottom: 12px;
}

.filter-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 10px;
  margin-bottom: 12px;
}

.helper-text {
  margin: 0 0 12px;
  color: #667085;
  line-height: 1.7;
}

.source-diagnostic-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 10px;
  margin-bottom: 12px;
}

.source-diagnostic-grid article {
  display: grid;
  gap: 4px;
  padding: 12px;
  border: 1px solid var(--app-border, #d8dee8);
  border-radius: 8px;
  background: #f8fafc;
}

.source-diagnostic-grid span {
  color: #667085;
  font-size: 12px;
}

.source-diagnostic-grid strong {
  overflow-wrap: anywhere;
}

.source-warning {
  margin-bottom: 12px;
}

.dev-debug-shell {
  border-color: #f3c969;
  background: #fffaf0;
}

.debug-title-note {
  margin-left: 12px;
  color: #92400e;
  font-size: 12px;
  font-weight: 600;
}

.entry-missing-text,
.row-missing-tip {
  color: #b45309;
  font-size: 12px;
  font-weight: 600;
}

.minimum-chain-guide {
  display: grid;
  gap: 12px;
  padding: 14px;
  margin-bottom: 12px;
  border: 1px solid #f3c969;
  border-radius: 8px;
  background: #fff8e6;
}

.guide-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.guide-heading h3,
.guide-heading p {
  margin: 0;
}

.guide-warning {
  padding: 10px 12px;
  border-radius: 8px;
  background: #fff;
  color: #92400e;
  font-weight: 700;
}

.minimum-chain-steps {
  display: grid;
  gap: 10px;
  margin: 0;
  padding-left: 22px;
}

.minimum-chain-steps li {
  line-height: 1.7;
}

.minimum-chain-steps span,
.minimum-chain-steps a {
  display: block;
}

.minimum-chain-steps a {
  color: #1d4ed8;
  overflow-wrap: anywhere;
}

.source-table {
  min-width: 1280px;
}

.pre-execution-card {
  border-color: #b7d4ff;
  background: #f8fbff;
}

.simulation-card {
  border-color: #c6d7b9;
  background: #fbfdf7;
}

.formal-entry-card {
  border-color: #f5c2c7;
  background: #fff8f8;
}

.final-review-card {
  border-color: #f59e0b;
  background: #fffaf0;
}

.state-impact-card {
  border-color: #93c5fd;
  background: #f8fbff;
}

.bank-flow-boundary-card {
  border-color: #8cc9dd;
  background: #f5fcff;
}

.bank-flow-object-card {
  border-color: #a7d7b8;
  background: #f7fdf9;
}

.bank-flow-readonly-preview-card {
  border-color: #c7b8ea;
  background: #fbf9ff;
}

.validation-conclusion-card {
  display: grid;
  gap: 12px;
  padding: 14px;
  margin-bottom: 12px;
  border: 1px solid #a78bfa;
  border-radius: 8px;
  background: #f5f3ff;
}

.validation-conclusion-card h3 {
  margin: 0;
  color: #5b21b6;
  font-size: 16px;
}

.validation-conclusion-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 8px;
}

.validation-conclusion-grid span {
  padding: 8px 10px;
  border-radius: 6px;
  background: #fff;
  color: #344054;
}

.validation-conclusion-grid strong {
  color: #5b21b6;
}

.state-impact-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 12px;
  margin-bottom: 12px;
}

.state-impact-grid article {
  display: grid;
  gap: 8px;
  padding: 14px;
  border: 1px solid #bfdbfe;
  border-radius: 8px;
  background: #fff;
}

.state-impact-grid h3,
.state-impact-grid p {
  margin: 0;
}

.state-impact-grid h3 {
  color: #1d4ed8;
  font-size: 16px;
}

.state-impact-grid span {
  color: #667085;
  font-weight: 700;
}

.state-impact-grid strong {
  color: #1d4ed8;
}

.state-impact-panels article {
  border-color: #bfdbfe;
}

.bank-flow-source-grid article,
.bank-flow-panels article,
.bank-flow-object-grid article,
.bank-flow-object-panels article,
.bank-flow-readonly-panels article {
  border-color: #8cc9dd;
  background: #fff;
}

.review-panel-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 12px;
}

.final-review-focus-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 12px;
  margin-bottom: 12px;
}

.final-review-focus-grid article {
  display: grid;
  gap: 8px;
  padding: 14px;
  border: 1px solid #f59e0b;
  border-radius: 8px;
  background: #fffbeb;
}

.final-review-focus-grid h3,
.final-review-focus-grid p {
  margin: 0;
}

.final-review-focus-grid h3 {
  color: #92400e;
  font-size: 16px;
}

.final-review-focus-grid strong {
  color: #b45309;
}

.review-panel-grid article {
  padding: 14px;
  border: 1px solid #fed7aa;
  border-radius: 8px;
  background: #fff;
}

.review-panel-grid h3 {
  margin: 0 0 10px;
  font-size: 15px;
}

.review-panel-grid ul {
  display: grid;
  gap: 6px;
  margin: 0;
  padding-left: 18px;
  line-height: 1.6;
}

.preview-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
  margin-top: 14px;
}

.preview-grid article {
  display: grid;
  gap: 4px;
  padding: 12px;
  border: 1px solid var(--app-border, #d8dee8);
  border-radius: 8px;
  background: #fff;
}

.preview-grid span {
  color: #667085;
  font-size: 12px;
}

.sortable-header {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border: 0;
  background: transparent;
  padding: 0;
  font: inherit;
  font-weight: 700;
  color: inherit;
  cursor: pointer;
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
</style>







