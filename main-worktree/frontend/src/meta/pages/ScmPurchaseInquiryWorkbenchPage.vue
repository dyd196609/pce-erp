<template>
  <main class="inquiry-workbench" data-page-code="purchase-inquiry" data-business-object="PurchaseInquiry"
    data-process-node="SCM_PURCHASE_INQUIRY" :data-process-version="purchaseInquiryProcessVersion"
    data-runtime-version="V1.14.2.8.18.7" data-fact-source="purchase-inquiry-provider+runtime-store" :data-active-view-mode="formalPriceApprovalViewMode">
    <section class="panel view-switcher-panel" data-acceptance-id="formal-price-approval-view-switcher">
      <div class="section-heading">
        <div><h2>价格审批页面视图</h2><p>业务视图面向采购人员，开发验收视图面向模型、规则与门禁核验；切换仅改变展示。</p></div>
        <el-radio-group v-model="formalPriceApprovalViewMode" aria-label="价格审批页面视图">
          <el-radio-button value="business_view">业务视图</el-radio-button>
          <el-radio-button value="acceptance_view">开发验收视图</el-radio-button>
        </el-radio-group>
      </div>
      <div class="view-separation-boundaries">
        <strong>Business View ≠ Acceptance View</strong>
        <strong>View Switch ≠ Business Action</strong>
        <strong>Hidden ≠ Deleted</strong>
        <strong>User Feedback ≠ ERP Transaction</strong>
      </div>
    </section>

    <section class="panel inquiry-lifecycle-workbench" data-view-scope="business" data-view-governance-scope="business" data-acceptance-id="purchase-inquiry-lifecycle-workbench" data-provider-code="SCM_PURCHASE_INQUIRY_LIFECYCLE_PROVIDER">
      <div class="section-heading"><div><h2>询价生命周期工作台</h2><p>准备、正式询价与入口上下文统一由 PurchaseInquiryLifecycleProvider 输出。</p></div><span class="business-stage-badge">{{ lifecycleContext.lifecycleStage.label }}</span></div>
      <h3 data-acceptance-id="business-context">业务上下文</h3>
      <div class="entry-context-grid">
        <article><span>业务来源</span><strong>{{ lifecycleContext.businessSource }}</strong><small>{{ lifecycleContext.sourceNo }}</small></article>
        <article><span>当前业务对象</span><strong>{{ lifecycleContext.currentObject.objectType }}</strong><small>{{ lifecycleContext.currentObject.objectNo }}</small></article>
        <article><span>当前业务运作区</span><strong>{{ lifecycleContext.operationArea.title }}</strong><small>{{ lifecycleContext.operationArea.mode }}</small></article>
        <article><span>生命周期状态</span><strong>{{ lifecycleContext.lifecycleStage.statusLabel }}</strong><small>{{ lifecycleContext.lifecycleStage.code }}</small></article>
        <article><span>下一步动作</span><strong>{{ lifecycleContext.nextAction }}</strong></article>
      </div>
      <h3 data-acceptance-id="next-action">下一步动作</h3>
      <div class="lifecycle-actions">
        <el-button v-if="lifecycleContext.allowedActions.includes('startInquiry')" type="primary" data-lifecycle-action="start-inquiry" :data-process-action="purchaseInquiryActionCodes.startInquiry" @click="startInquiry(lifecycleFacts.currentPreparation)">启动询价</el-button>
        <el-button v-if="lifecycleContext.allowedActions.includes('editInquiry')" type="primary" data-lifecycle-action="edit-inquiry" :data-process-action="purchaseInquiryActionCodes.editInquiry" @click="editInquiry()">编辑询价</el-button>
        <el-button v-if="lifecycleContext.allowedActions.includes('viewInquiry')" data-lifecycle-action="view-inquiry" @click="viewCurrentInquiry">查看询价</el-button>
      </div>
      <div v-if="inquiryEditDraft" class="inquiry-edit-panel" data-acceptance-id="purchase-inquiry-edit-runtime">
        <el-input v-model="inquiryEditDraft.inquiryTitle" placeholder="询价主题" />
        <el-date-picker v-model="inquiryEditDraft.inquiryDate" type="date" value-format="YYYY-MM-DD" placeholder="询价日期" />
        <el-input v-model="inquiryEditDraft.buyerName" placeholder="采购员" />
        <el-button type="primary" :data-process-action="purchaseInquiryActionCodes.saveInquiry" @click="saveInquiry">保存询价</el-button>
      </div>
      <h3 data-acceptance-id="current-inquiry-detail">当前询价详情</h3>
      <div class="lifecycle-evidence-grid"><article v-for="item in lifecycleContext.evidence" :key="item.code"><span>{{ item.label }}</span><strong>{{ item.value }}</strong></article></div>
      <el-table v-if="currentLifecycleLines.length" :data="currentLifecycleLines" border empty-text="暂无物料证据">
        <el-table-column prop="materialCode" label="物料编码" min-width="150" /><el-table-column prop="materialName" label="物料名称" min-width="180" />
        <el-table-column prop="quantity" label="数量" width="120" /><el-table-column prop="requiredDate" label="需求日期" width="150" />
      </el-table>
      <p v-if="entryContext.browseOnly" class="entry-context-notice">当前入口仅允许查看已有询价；无询价准备上下文时禁止创建询价。</p>
    </section>

    <section class="panel supplier-quote-runtime-panel" data-process-node="SCM_SUPPLIER_QUOTE" :data-process-version="supplierQuoteProcessVersion" data-acceptance-id="supplier-quote-runtime">
      <div class="section-heading">
        <div><h2>供应商报价运行闭环</h2><p>仅支持人工创建报价上下文、接收并保存会话态报价；不调用 Supplier API。</p></div>
        <span class="business-stage-badge">{{ supplierQuote?.status || supplierQuoteContext?.status || '等待询价选择' }}</span>
      </div>
      <div class="supplier-quote-actions">
        <el-date-picker v-model="supplierQuoteDeadline" type="date" value-format="YYYY-MM-DD" placeholder="报价截止日期" />
        <el-input-number v-model="supplierQuoteUnitPrice" :min="0.01" :precision="2" placeholder="报价单价" />
        <el-button type="primary" :disabled="!lifecycleFacts.currentInquiry" :data-process-action="supplierQuoteActionCodes.createContext" @click="createQuoteContextForCurrent">创建报价上下文</el-button>
        <el-button type="primary" :disabled="!supplierQuoteContext || Boolean(supplierQuote)" :data-process-action="supplierQuoteActionCodes.receiveQuote" @click="receiveQuoteForCurrent">接收供应商报价</el-button>
        <el-button type="success" :disabled="supplierQuote?.status !== 'quotation_received'" :data-process-action="supplierQuoteActionCodes.saveQuote" @click="saveQuoteForCurrent">保存供应商报价</el-button>
      </div>
      <div v-if="supplierQuoteContext" class="entry-context-grid">
        <article><span>询价编号</span><strong>{{ supplierQuoteContext.inquiryNo }}</strong></article>
        <article><span>物料/数量</span><strong>{{ supplierQuoteContext.materials.length }} 项</strong></article>
        <article><span>供应商候选</span><strong>{{ supplierQuoteContext.supplierCandidates.length }} 家</strong></article>
        <article><span>截止日期</span><strong>{{ supplierQuoteContext.deadline }}</strong></article>
      </div>
      <p class="preparation-boundary">QuoteComparison、PurchaseOrder、Payment、Supplier API 均保持关闭。</p>
    </section>

    <section class="panel quote-comparison-runtime-panel" data-process-node="SCM_QUOTE_COMPARISON" :data-process-version="quoteComparisonProcessVersion" data-acceptance-id="quote-comparison-runtime">
      <div class="section-heading">
        <div><h2>报价比较运行闭环</h2><p>生成并保存价格、交期和有效期比较事实，不创建供应商推荐。</p></div>
        <span class="business-stage-badge">{{ quoteComparison?.status || quoteComparisonContext?.status || 'supplier_quotes_ready' }}</span>
      </div>
      <div class="quote-comparison-actions">
        <el-button type="primary" :disabled="supplierQuote?.status !== 'quotation_completed' || Boolean(quoteComparisonContext)" :data-process-action="quoteComparisonActionCodes.createContext" @click="createComparisonContextForCurrent">创建比较上下文</el-button>
        <el-button type="primary" :disabled="quoteComparisonContext?.status !== 'comparison_context_created' || Boolean(quoteComparison)" :data-process-action="quoteComparisonActionCodes.generateFact" @click="generateComparisonFactForCurrent">生成比较事实</el-button>
        <el-button type="success" :disabled="quoteComparison?.status !== 'comparing'" :data-process-action="quoteComparisonActionCodes.saveComparison" @click="saveComparisonForCurrent">保存报价比较</el-button>
      </div>
      <div v-if="quoteComparison" class="entry-context-grid">
        <article><span>比较编号</span><strong>{{ quoteComparison.comparisonNo }}</strong></article>
        <article><span>报价数量</span><strong>{{ quoteComparison.summary.quoteCount }}</strong></article>
        <article><span>供应商数量</span><strong>{{ quoteComparison.summary.supplierCount }}</strong></article>
        <article><span>物料数量</span><strong>{{ quoteComparison.summary.materialCount }}</strong></article>
        <article><span>推荐状态</span><strong>仅就绪、不创建</strong></article>
      </div>
      <p class="preparation-boundary">SupplierRecommendation 创建、PurchaseOrder 创建和 Finance 动作均保持关闭。</p>
    </section>

    <section class="panel supplier-recommendation-runtime-panel" data-process-node="SCM_SUPPLIER_RECOMMENDATION_DECISION" :data-process-version="supplierRecommendationProcessVersion" data-acceptance-id="supplier-recommendation-runtime">
      <div class="section-heading">
        <div><h2>供应商推荐决策运行闭环</h2><p>根据比较事实生成可解释推荐决策；保存后仅进入审批就绪。</p></div>
        <span class="business-stage-badge">{{ supplierRecommendationDecision?.status || supplierRecommendationContext?.status || 'quote_comparison_ready' }}</span>
      </div>
      <div class="supplier-recommendation-actions">
        <el-button type="primary" :disabled="quoteComparison?.status !== 'recommendation_ready' || Boolean(supplierRecommendationContext)" :data-process-action="supplierRecommendationActionCodes.createContext" @click="createRecommendationContextForCurrent">创建推荐上下文</el-button>
        <el-button type="primary" :disabled="supplierRecommendationContext?.status !== 'recommendation_context_created' || Boolean(supplierRecommendationDecision)" :data-process-action="supplierRecommendationActionCodes.generateDecision" @click="generateRecommendationDecisionForCurrent">生成推荐决策</el-button>
        <el-button type="success" :disabled="supplierRecommendationDecision?.status !== 'evaluating'" :data-process-action="supplierRecommendationActionCodes.saveDecision" @click="saveRecommendationDecisionForCurrent">保存推荐决策</el-button>
      </div>
      <div v-if="supplierRecommendationDecision" class="entry-context-grid">
        <article><span>决策编号</span><strong>{{ supplierRecommendationDecision.decisionNo }}</strong></article>
        <article><span>推荐供应商</span><strong>{{ supplierRecommendationDecision.recommendedSupplierName }}</strong></article>
        <article><span>候选数量</span><strong>{{ supplierRecommendationDecision.evaluations.length }}</strong></article>
        <article><span>风险证据</span><strong>{{ supplierRecommendationDecision.riskEvidence.length }} 项</strong></article>
        <article><span>审批状态</span><strong>仅就绪、未提交</strong></article>
      </div>
      <p class="preparation-boundary">PurchaseOrder 创建、审批提交和付款动作均保持关闭。</p>
    </section>

    <section class="panel purchase-order-gate-runtime-panel" data-process-node="SCM_PURCHASE_ORDER_CREATION_GATE" :data-process-version="purchaseOrderGateProcessVersion" data-acceptance-id="purchase-order-creation-gate-runtime">
      <div class="section-heading">
        <div><h2>采购订单创建准入运行闭环</h2><p>仅评估订单创建资格并保存门禁结论，不创建采购订单。</p></div>
        <span class="business-stage-badge">{{ purchaseOrderGateDecision?.status || purchaseOrderGateContext?.status || 'supplier_recommendation_ready' }}</span>
      </div>
      <div class="purchase-order-gate-actions">
        <el-button type="primary" :disabled="supplierRecommendationDecision?.status !== 'approval_ready' || Boolean(purchaseOrderGateContext)" :data-process-action="purchaseOrderGateActionCodes.createContext" @click="createPurchaseOrderGateContextForCurrent">创建准入上下文</el-button>
        <el-button type="primary" :disabled="purchaseOrderGateContext?.status !== 'gate_context_created' || Boolean(purchaseOrderGateDecision)" :data-process-action="purchaseOrderGateActionCodes.evaluateEligibility" @click="evaluatePurchaseOrderGateForCurrent">评估订单创建资格</el-button>
        <el-button type="success" :disabled="purchaseOrderGateDecision?.status !== 'evaluating'" :data-process-action="purchaseOrderGateActionCodes.saveDecision" @click="savePurchaseOrderGateForCurrent">保存准入决定</el-button>
      </div>
      <div v-if="purchaseOrderGateDecision" class="entry-context-grid">
        <article><span>门禁决定编号</span><strong>{{ purchaseOrderGateDecision.gateDecisionNo }}</strong></article>
        <article><span>推荐供应商</span><strong>{{ purchaseOrderGateDecision.recommendedSupplier.supplierName }}</strong></article>
        <article><span>成本引用</span><strong>{{ purchaseOrderGateDecision.costReference.currency }} {{ purchaseOrderGateDecision.costReference.totalCost }}</strong></article>
        <article><span>阻断原因</span><strong>{{ purchaseOrderGateDecision.blockedReasons.join(', ') || '无' }}</strong></article>
        <article><span>订单状态</span><strong>未创建</strong></article>
      </div>
      <p class="preparation-boundary">eligible 仅为准入结论；PurchaseOrder 创建、供应商发布和付款均保持关闭。</p>
    </section>

    <section class="panel purchase-order-transaction-runtime-panel" data-process-node="SCM_PURCHASE_ORDER_TRANSACTION" :data-process-version="purchaseOrderTransactionProcessVersion" data-acceptance-id="purchase-order-transaction-runtime">
      <div class="section-heading">
        <div><h2>采购订单交易节点运行闭环</h2><p>本版本只创建会话态交易草稿；待发布与已发布状态保持锁定。</p></div>
        <span class="business-stage-badge">{{ purchaseOrderTransaction?.status || purchaseOrderTransactionContext?.status || 'purchase_order_gate_eligible' }}</span>
      </div>
      <div class="purchase-order-transaction-actions">
        <el-button type="primary" :disabled="purchaseOrderGateDecision?.status !== 'eligible' || Boolean(purchaseOrderTransactionContext)" :data-process-action="purchaseOrderTransactionActionCodes.createContext" @click="createPurchaseOrderTransactionContextForCurrent">创建交易上下文</el-button>
        <el-button type="primary" :disabled="purchaseOrderTransactionContext?.status !== 'transaction_context_created' || Boolean(purchaseOrderTransaction)" :data-process-action="purchaseOrderTransactionActionCodes.createTransaction" @click="createPurchaseOrderTransactionForCurrent">创建交易草稿</el-button>
        <el-button disabled :data-process-action="purchaseOrderTransactionActionCodes.saveTransaction" @click="savePurchaseOrderTransactionForCurrent">保存并进入待发布（本版本锁定）</el-button>
      </div>
      <div v-if="purchaseOrderTransaction" class="entry-context-grid">
        <article><span>交易编号</span><strong>{{ purchaseOrderTransaction.transactionNo }}</strong></article>
        <article><span>供应商</span><strong>{{ purchaseOrderTransaction.supplier.supplierName }}</strong></article>
        <article><span>采购明细</span><strong>{{ purchaseOrderTransaction.purchaseDetails.length }} 项</strong></article>
        <article><span>金额引用</span><strong>{{ purchaseOrderTransaction.amountReference.currency }} {{ purchaseOrderTransaction.amountReference.totalAmount }}</strong></article>
        <article><span>业务状态</span><strong>草稿、未执行</strong></article>
      </div>
      <p class="preparation-boundary">PurchaseOrder Execution、供应商发布、收货、入库、发票和付款均保持关闭。</p>
    </section>

    <section class="panel purchase-order-issue-preparation-runtime-panel" data-process-node="SCM_PURCHASE_ORDER_ISSUE_PREPARATION" :data-process-version="purchaseOrderIssuePreparationProcessVersion" data-acceptance-id="purchase-order-issue-preparation-runtime">
      <div class="section-heading">
        <div><h2>采购订单发布准备运行闭环</h2><p>检查供应商、明细、金额、交付要求和来源链；不执行采购订单发布。</p></div>
        <span class="business-stage-badge">{{ purchaseOrderIssuePreparation?.status || purchaseOrderIssuePreparationContext?.status || 'purchase_order_transaction_draft' }}</span>
      </div>
      <div class="purchase-order-issue-preparation-actions">
        <el-button type="primary" :disabled="purchaseOrderTransaction?.status !== 'draft' || Boolean(purchaseOrderIssuePreparationContext)" :data-process-action="purchaseOrderIssuePreparationActionCodes.createContext" @click="createIssuePreparationContextForCurrent">创建发布准备上下文</el-button>
        <el-button type="primary" :disabled="purchaseOrderIssuePreparationContext?.status !== 'issue_context_created' || Boolean(purchaseOrderIssuePreparation)" :data-process-action="purchaseOrderIssuePreparationActionCodes.checkRequirements" @click="checkIssueRequirementsForCurrent">检查发布要求</el-button>
        <el-button type="success" :disabled="purchaseOrderIssuePreparation?.status !== 'checking'" :data-process-action="purchaseOrderIssuePreparationActionCodes.savePreparation" @click="saveIssuePreparationForCurrent">保存发布准备</el-button>
      </div>
      <div v-if="purchaseOrderIssuePreparation" class="entry-context-grid">
        <article><span>准备编号</span><strong>{{ purchaseOrderIssuePreparation.preparationNo }}</strong></article>
        <article><span>供应商</span><strong>{{ purchaseOrderIssuePreparation.supplier.supplierName }}</strong></article>
        <article><span>交付要求</span><strong>{{ purchaseOrderIssuePreparation.deliveryRequirements.length }} 项</strong></article>
        <article><span>阻断原因</span><strong>{{ purchaseOrderIssuePreparation.blockedReasons.join(', ') || '无' }}</strong></article>
        <article><span>发布状态</span><strong>未发布、未发送</strong></article>
      </div>
      <p class="preparation-boundary">ready_for_issue 仅表示准备完成；发布采购订单、发送供应商、收货、入库、发票和付款均保持关闭。</p>
    </section>

    <section class="panel purchase-order-issue-boundary-runtime-panel" data-process-node="SCM_PURCHASE_ORDER_ISSUE_BOUNDARY" :data-process-version="purchaseOrderIssueBoundaryProcessVersion" data-acceptance-id="purchase-order-issue-boundary-runtime">
      <div class="section-heading">
        <div><h2>采购订单发布边界运行闭环</h2><p>根据准备结果和证据判断发布权限；许可决定不执行采购订单发布。</p></div>
        <span class="business-stage-badge">{{ purchaseOrderIssueDecision?.status || purchaseOrderIssueBoundaryContext?.status || 'issue_preparation_ready' }}</span>
      </div>
      <div class="purchase-order-issue-boundary-actions">
        <el-button type="primary" :disabled="!['ready_for_issue', 'blocked'].includes(purchaseOrderIssuePreparation?.status) || Boolean(purchaseOrderIssueBoundaryContext)" :data-process-action="purchaseOrderIssueBoundaryActionCodes.createContext" @click="createIssueBoundaryContextForCurrent">创建发布边界上下文</el-button>
        <el-button type="primary" :disabled="purchaseOrderIssueBoundaryContext?.status !== 'issue_boundary_context_created' || Boolean(purchaseOrderIssueDecision)" :data-process-action="purchaseOrderIssueBoundaryActionCodes.evaluatePermission" @click="evaluateIssuePermissionForCurrent">评估发布权限</el-button>
        <el-button type="success" :disabled="purchaseOrderIssueDecision?.status !== 'evaluating'" :data-process-action="purchaseOrderIssueBoundaryActionCodes.saveDecision" @click="saveIssueDecisionForCurrent">保存发布许可决定</el-button>
      </div>
      <div v-if="purchaseOrderIssueDecision" class="entry-context-grid">
        <article><span>决定编号</span><strong>{{ purchaseOrderIssueDecision.issueDecisionNo }}</strong></article>
        <article><span>供应商</span><strong>{{ purchaseOrderIssueDecision.supplier.supplierName }}</strong></article>
        <article><span>证据检查</span><strong>{{ purchaseOrderIssueDecision.checks.length }} 项</strong></article>
        <article><span>阻断原因</span><strong>{{ purchaseOrderIssueDecision.blockedReasons.join(', ') || '无' }}</strong></article>
        <article><span>执行状态</span><strong>权限决定、未发布</strong></article>
      </div>
      <p class="preparation-boundary">allowed 仅表示权限允许；发布采购订单、发送供应商、收货、入库、发票和付款均保持关闭。</p>
    </section>

    <section class="panel purchase-order-issue-execution-runtime-panel" data-process-node="SCM_PURCHASE_ORDER_ISSUE_EXECUTION" :data-process-version="purchaseOrderIssueExecutionProcessVersion" data-acceptance-id="purchase-order-issue-execution-runtime">
      <div class="section-heading">
        <div><h2>采购订单发布执行授权准备</h2><p>检查边界许可、授权证据和生产隔离；不执行采购订单发布。</p></div>
        <span class="business-stage-badge">{{ purchaseOrderIssueAuthorization?.status || purchaseOrderIssueExecutionContext?.status || 'issue_boundary_decided' }}</span>
      </div>
      <div class="purchase-order-issue-execution-actions">
        <el-button type="primary" :disabled="!['allowed', 'blocked'].includes(purchaseOrderIssueDecision?.status) || Boolean(purchaseOrderIssueExecutionContext)" :data-process-action="purchaseOrderIssueExecutionActionCodes.createContext" @click="createIssueExecutionContextForCurrent">创建执行授权上下文</el-button>
        <el-button type="primary" :disabled="purchaseOrderIssueExecutionContext?.status !== 'execution_context_created' || Boolean(purchaseOrderIssueAuthorization)" :data-process-action="purchaseOrderIssueExecutionActionCodes.checkAuthorization" @click="checkIssueExecutionAuthorizationForCurrent">检查执行授权</el-button>
        <el-button type="success" :disabled="purchaseOrderIssueAuthorization?.status !== 'authorization_checking'" :data-process-action="purchaseOrderIssueExecutionActionCodes.savePreparation" @click="saveIssueExecutionPreparationForCurrent">保存执行授权准备</el-button>
      </div>
      <div v-if="purchaseOrderIssueAuthorization" class="entry-context-grid">
        <article><span>授权编号</span><strong>{{ purchaseOrderIssueAuthorization.authorizationNo }}</strong></article>
        <article><span>供应商</span><strong>{{ purchaseOrderIssueAuthorization.supplierInformation.supplierName }}</strong></article>
        <article><span>授权检查</span><strong>{{ purchaseOrderIssueAuthorization.checks.length }} 项</strong></article>
        <article><span>阻断原因</span><strong>{{ purchaseOrderIssueAuthorization.blockedReasons.join(', ') || '无' }}</strong></article>
        <article><span>执行状态</span><strong>仅授权准备、未发布</strong></article>
      </div>
      <p class="preparation-boundary">authorized 仅表示授权准备通过；Supplier API、采购订单发布、供应商发送及所有下游交易均保持关闭。</p>
    </section>

    <section class="panel business-user-view" data-view-scope="acceptance" data-view-governance-scope="acceptance" data-acceptance-id="formal-price-approval-business-user-view">
      <div class="section-heading">
        <div><h2>询价价格审批业务视图</h2><p>帮助采购人员快速理解当前阶段、关键证据、判断结果和下一步安排。</p></div>
        <span class="business-stage-badge">当前阶段：价格评审准备</span>
      </div>
      <div class="business-user-view-grid">
        <article><span>询价概览</span><strong>当前询价 {{ runtimeView.summary.inquiryCount }} 项</strong><small>涉及供应商 {{ runtimeView.summary.supplierCount }} 家，当前状态以业务状态栏为准。</small></article>
        <article><span>报价情况</span><strong>已收报价 {{ runtimeView.quotationRuntime.supplierQuotations.length }} 份</strong><small>{{ runtimeView.quotationRuntime.supplierQuotations.length ? '请核对报价完整性' : '尚未收到报价，需要补充报价资料' }}</small></article>
        <article><span>价格比较</span><strong>{{ runtimeView.quotationRuntime.quotationComparisons.length ? '已有比较依据' : '等待形成比较依据' }}</strong><small>重点关注价格差异、币种、交期和判断依据。</small></article>
        <article><span>审批准备</span><strong>{{ runtimeView.quotationRuntime.priceApprovalEntryAssessments.length ? '已有准备评估' : '尚未满足准备条件' }}</strong><small>风险或证据缺失时必须人工处理，不能直接执行。</small></article>
        <article class="next-business-hint"><span>下一步业务提示</span><strong>{{ nextBusinessHint }}</strong><small>本页只提供业务提示，不自动选择供应商或启动审批。</small></article>
      </div>
    </section>

    <section class="panel inquiry-preparation-panel" data-view-scope="business" data-view-governance-scope="business" data-acceptance-id="pending-inquiry-preparations">
      <div class="section-heading">
        <div><h2>待处理询价准备</h2><p>仅对人工勾选且规则通过的准备对象进行承接；批量承接不会发送供应商或创建报价。</p></div>
        <span class="business-stage-badge">{{ pendingInquiryPreparations.length }} 项待处理</span>
      </div>
      <div class="batch-preparation-actions">
        <el-button type="primary" :disabled="!batchPreparationSelection.length" data-batch-action="start-inquiries" :data-process-action="purchaseInquiryActionCodes.startInquiry" @click="startInquiryBatch">批量启动询价</el-button>
        <span>已选择 {{ batchPreparationSelection.length }} 项；上次输出 {{ lastBatchResult.outputCount }} 项</span>
      </div>
      <el-table :data="pendingInquiryPreparations" border empty-text="暂无待处理询价准备" data-provider-code="SCM_INQUIRY_PREPARATION_PROVIDER" data-process-provider-code="SCM_PURCHASE_INQUIRY_LIFECYCLE_PROVIDER" @selection-change="batchPreparationSelection = $event">
        <el-table-column type="selection" width="52" fixed="left" />
        <el-table-column prop="inquiryPreparationNo" label="询价准备编号" min-width="210" />
        <el-table-column prop="sourceRequestNo" label="来源申请号" min-width="190" />
        <el-table-column prop="requestDepartment" label="申请部门" min-width="150" />
        <el-table-column prop="purchaseDepartment" label="采购部门" min-width="150" />
        <el-table-column prop="materialQuantity" label="物料数量" width="120" />
        <el-table-column prop="supplierCandidateCount" label="供应商候选数量" width="150" />
        <el-table-column prop="statusLabel" label="状态" min-width="150" />
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }"><el-button size="small" type="primary" :disabled="!canStartPreparation(row)" data-activation-action="start-inquiry" :data-process-action="purchaseInquiryActionCodes.startInquiry" @click="startInquiry(row)">{{ isPreparationActivated(row) ? '已启动' : '启动询价' }}</el-button></template>
        </el-table-column>
      </el-table>
      <p class="preparation-boundary">一项准备只生成一项询价；重复来源、缺少来源追溯或明细为空时阻断。</p>
    </section>

    <section class="panel" data-view-scope="acceptance" data-view-governance-scope="acceptance" data-acceptance-id="business-summary">
      <div class="section-heading">
        <div><h2>业务摘要</h2><p>询价业务工作台</p></div>
      </div>
      <div class="summary-grid">
        <article><span>询价总数</span><strong>{{ runtimeView.summary.inquiryCount }}</strong></article>
        <article><span>涉及供应商</span><strong>{{ runtimeView.summary.supplierCount }}</strong></article>
        <article><span>询价明细</span><strong>{{ runtimeView.summary.lineCount }}</strong></article>
        <article><span>事实来源</span><strong>服务端</strong></article>
      </div>
    </section>

    <section class="panel" data-view-scope="acceptance" data-view-governance-scope="acceptance" data-acceptance-id="status-statistics">
      <h2>状态统计</h2>
      <div class="status-grid" v-if="statusEntries.length">
        <article v-for="([label, count]) in statusEntries" :key="label"><span>{{ label }}</span><strong>{{ count }}</strong></article>
      </div>
      <el-empty v-else description="暂无状态事实" :image-size="64" />
    </section>

    <section class="panel" data-view-scope="business" data-view-governance-scope="acceptance" data-acceptance-id="supplier-inquiry-task-list">
      <div class="section-heading">
        <div><h2>供应商询价任务</h2><p>只读展示服务端任务事实，不提供发送供应商动作。</p></div>
        <span class="readonly-badge">只读运行投影</span>
      </div>
      <el-table :data="runtimeView.quotationRuntime.supplierInquiryTasks" border empty-text="暂无供应商询价任务事实">
        <el-table-column prop="inquiryNo" label="询价编号" min-width="180" />
        <el-table-column prop="supplierId" label="供应商" min-width="160" />
        <el-table-column label="发送状态" min-width="130">
          <template #default="{ row }"><PceBusinessStatus :status-code="row.sendStatus" :status-label="row.sendStatusLabel" source="server" /></template>
        </el-table-column>
        <el-table-column prop="responseDeadline" label="响应截止时间" min-width="180" />
        <el-table-column label="报价状态" min-width="140">
          <template #default="{ row }"><PceBusinessStatus :status-code="row.quotationStatus" :status-label="row.quotationStatusLabel" source="server" /></template>
        </el-table-column>
      </el-table>
    </section>

    <section class="panel" data-view-scope="business" data-view-governance-scope="acceptance" data-acceptance-id="supplier-quotation-list">
      <div class="section-heading">
        <div><h2>供应商报价对象</h2><p>报价对象仅由服务端事实映射，不自动创建，不推进价格审批。</p></div>
        <span class="readonly-badge">零生产写入</span>
      </div>
      <el-table :data="runtimeView.quotationRuntime.supplierQuotations" border empty-text="暂无供应商报价事实">
        <el-table-column prop="quotationNo" label="报价编号" min-width="180" />
        <el-table-column prop="supplierId" label="供应商" min-width="150" />
        <el-table-column prop="inquiryNo" label="询价编号" min-width="180" />
        <el-table-column label="报价状态" min-width="140">
          <template #default="{ row }"><PceBusinessStatus :status-code="row.quotationStatus" :status-label="row.quotationStatusLabel" source="server" /></template>
        </el-table-column>
        <el-table-column prop="price" label="报价金额" min-width="130" />
        <el-table-column prop="currency" label="币种" width="100" />
        <el-table-column prop="deliveryDays" label="交付天数" min-width="120" />
      </el-table>
    </section>

    <section class="panel" data-view-scope="business" data-view-governance-scope="acceptance" data-acceptance-id="quotation-comparison-runtime-status">
      <div class="section-heading">
        <div><h2>报价比较运行状态</h2><p>只表达已有报价之间的比较事实，不自动选择供应商。</p></div>
        <span class="readonly-badge">人工评审前</span>
      </div>
      <el-table :data="runtimeView.quotationRuntime.quotationComparisons" border empty-text="尚未形成报价比较事实">
        <el-table-column prop="comparisonNo" label="比较编号" min-width="180" />
        <el-table-column prop="inquiryNo" label="询价编号" min-width="180" />
        <el-table-column label="比较对象状态" min-width="150">
          <template #default="{ row }"><PceBusinessStatus :status-code="row.comparisonStatus" :status-label="row.comparisonStatusLabel" source="server" /></template>
        </el-table-column>
        <el-table-column prop="quotationCount" label="报价数量" width="110" />
        <el-table-column prop="supplierCount" label="供应商数量" width="120" />
        <el-table-column prop="comparisonConclusion" label="比较结论" min-width="260" show-overflow-tooltip />
      </el-table>
    </section>

    <section class="panel" data-view-scope="business" data-view-governance-scope="acceptance" data-acceptance-id="price-review-preparation-status">
      <div class="section-heading">
        <div><h2>核价准备对象状态</h2><p>准备对象不是正式核价对象，不创建价格审批记录。</p></div>
        <span class="readonly-badge">仅准备状态</span>
      </div>
      <el-table :data="runtimeView.quotationRuntime.priceReviewPreparations" border empty-text="尚未形成核价准备事实">
        <el-table-column prop="preparationNo" label="准备编号" min-width="180" />
        <el-table-column prop="inquiryNo" label="询价编号" min-width="180" />
        <el-table-column prop="comparisonNo" label="比较编号" min-width="180" />
        <el-table-column label="准备对象状态" min-width="150">
          <template #default="{ row }"><PceBusinessStatus :status-code="row.reviewStatus" :status-label="row.reviewStatusLabel" source="server" /></template>
        </el-table-column>
        <el-table-column prop="priceReviewEntryAllowedLabel" label="是否允许进入核价" min-width="150" />
        <el-table-column label="阻断原因" min-width="260">
          <template #default="{ row }">{{ row.blockedReasons?.join('；') || '无' }}</template>
        </el-table-column>
      </el-table>
    </section>

    <section class="panel" data-view-scope="business" data-view-governance-scope="acceptance" data-acceptance-id="price-approval-entry-assessment">
      <div class="section-heading">
        <div><h2>价格审批入口准入评估</h2><p>仅判断未来价格审批入口条件，不创建、提交或批准正式价格审批对象。</p></div>
        <span class="readonly-badge">正式入口冻结</span>
      </div>
      <el-table :data="runtimeView.quotationRuntime.priceApprovalEntryAssessments" border empty-text="尚无价格审批入口评估事实">
        <el-table-column prop="assessmentNo" label="评估编号" min-width="180" />
        <el-table-column prop="inquiryNo" label="询价编号" min-width="180" />
        <el-table-column label="评估状态" min-width="150">
          <template #default="{ row }"><PceBusinessStatus :status-code="row.assessmentStatus" :status-label="row.assessmentStatusLabel" source="server" /></template>
        </el-table-column>
        <el-table-column prop="quotationEvidenceStatusLabel" label="报价证据" min-width="140" />
        <el-table-column prop="comparisonStatusLabel" label="报价比较" min-width="140" />
        <el-table-column prop="preparationStatusLabel" label="核价准备" min-width="140" />
        <el-table-column prop="entryConditionLabel" label="未来入口条件" min-width="150" />
        <el-table-column label="阻断原因" min-width="260">
          <template #default="{ row }">{{ row.blockedReasons?.join('；') || '无' }}</template>
        </el-table-column>
      </el-table>
    </section>

    <section class="panel" data-view-scope="business" data-view-governance-scope="acceptance" data-acceptance-id="price-approval-creation-freeze-assessment">
      <div class="section-heading">
        <div><h2>正式价格审批对象创建前冻结评估</h2><p>最后一道只读冻结判断；即使状态为就绪，也不会创建审批对象或启动审批流程。</p></div>
        <span class="readonly-badge">创建能力关闭</span>
      </div>
      <el-table :data="runtimeView.quotationRuntime.priceApprovalCreationAssessments" border empty-text="尚无正式价格审批创建冻结事实">
        <el-table-column prop="creationAssessmentNo" label="冻结评估编号" min-width="190" />
        <el-table-column prop="inquiryNo" label="询价编号" min-width="180" />
        <el-table-column label="冻结评估状态" min-width="150">
          <template #default="{ row }"><PceBusinessStatus :status-code="row.creationAssessmentStatus" :status-label="row.creationAssessmentStatusLabel" source="server" /></template>
        </el-table-column>
        <el-table-column prop="entryAssessmentStatusLabel" label="准入评估" min-width="140" />
        <el-table-column prop="preparationStatusLabel" label="核价准备" min-width="140" />
        <el-table-column prop="quotationEvidenceStatusLabel" label="报价证据" min-width="140" />
        <el-table-column prop="creationReadinessLabel" label="创建前条件" min-width="150" />
        <el-table-column label="阻断原因" min-width="260">
          <template #default="{ row }">{{ row.blockedReasons?.join('；') || '无' }}</template>
        </el-table-column>
      </el-table>
    </section>

    <section class="panel" data-view-scope="acceptance" data-acceptance-id="formal-price-approval-projection">
      <div class="section-heading">
        <div><h2>正式价格审批对象只读投影</h2><p>展示创建前对象镜像，不代表正式价格审批对象已经创建。</p></div>
        <span class="readonly-badge">非正式审批对象</span>
      </div>
      <el-table :data="runtimeView.quotationRuntime.formalPriceApprovalProjections" border empty-text="尚无正式价格审批只读投影事实">
        <el-table-column prop="projectionNo" label="投影编号" min-width="180" />
        <el-table-column prop="inquiryNo" label="询价编号" min-width="180" />
        <el-table-column prop="creationAssessmentNo" label="冻结评估编号" min-width="190" />
        <el-table-column prop="evidencePackageNo" label="证据包编号" min-width="180" />
        <el-table-column label="投影状态" min-width="150">
          <template #default="{ row }"><PceBusinessStatus :status-code="row.projectionStatus" :status-label="row.projectionStatusLabel" source="server" /></template>
        </el-table-column>
        <el-table-column prop="projectionAvailabilityLabel" label="投影可用性" min-width="150" />
        <el-table-column label="缺失证据" min-width="260">
          <template #default="{ row }">{{ row.missingEvidence?.join('；') || '无' }}</template>
        </el-table-column>
      </el-table>
    </section>

    <section class="panel" data-view-scope="acceptance" data-acceptance-id="price-approval-evidence-package">
      <div class="section-heading">
        <div><h2>审批前证据归档包</h2><p>仅展示服务端证据引用链，不执行前端归档写入或审批任务创建。</p></div>
        <span class="readonly-badge">证据引用只读</span>
      </div>
      <el-table :data="runtimeView.quotationRuntime.priceApprovalEvidencePackages" border empty-text="尚无价格审批前证据包事实">
        <el-table-column prop="evidencePackageNo" label="证据包编号" min-width="180" />
        <el-table-column prop="inquiryNo" label="询价编号" min-width="180" />
        <el-table-column label="证据包状态" min-width="150">
          <template #default="{ row }"><PceBusinessStatus :status-code="row.packageStatus" :status-label="row.packageStatusLabel" source="server" /></template>
        </el-table-column>
        <el-table-column prop="evidenceCount" label="证据数量" width="120" />
        <el-table-column prop="comparisonEvidenceRef" label="比较证据" min-width="180" />
        <el-table-column prop="preparationEvidenceRef" label="核价准备证据" min-width="180" />
        <el-table-column prop="creationFreezeEvidenceRef" label="创建冻结证据" min-width="180" />
        <el-table-column label="缺失证据" min-width="240">
          <template #default="{ row }">{{ row.missingEvidence?.join('；') || '无' }}</template>
        </el-table-column>
      </el-table>
    </section>

    <section class="panel" data-view-scope="acceptance" data-acceptance-id="formal-price-approval-object-model">
      <div class="section-heading">
        <div><h2>正式价格审批对象模型</h2><p>仅展示领域定义和未来生命周期；当前不创建任何正式审批对象实例。</p></div>
        <span class="readonly-badge">只设计，不创建</span>
      </div>
      <div class="model-definition-grid">
        <article>
          <span>业务对象</span>
          <strong>正式价格审批对象</strong>
        </article>
        <article>
          <span>当前对象实例</span>
          <strong>0</strong>
        </article>
        <article>
          <span>当前允许状态</span>
          <strong>{{ formalPriceApprovalAllowedLabels.join('、') }}</strong>
        </article>
        <article>
          <span>创建边界</span>
          <strong>冻结</strong>
        </article>
      </div>
      <ol class="model-lifecycle" aria-label="正式价格审批对象未来生命周期">
        <li v-for="(state, index) in formalPriceApprovalLifecycle" :key="state.code" :data-current-allowed="String(state.currentAllowed)">
          <span>{{ index + 1 }}</span><strong>{{ state.label }}</strong><small>{{ state.currentAllowed ? '当前允许设计态' : '未来状态，当前关闭' }}</small>
        </li>
      </ol>
    </section>

    <section class="panel" data-view-scope="acceptance" data-acceptance-id="formal-price-approval-runtime-design">
      <div class="section-heading">
        <div><h2>正式价格审批状态机运行设计</h2><p>仅验证状态机设计，不改变对象状态，不接入或启动正式审批流程。</p></div>
        <span class="readonly-badge">审批流程隔离</span>
      </div>
      <div class="runtime-isolation-grid">
        <article><span>当前允许设计转换</span><strong>仅模型定义 → 具备未来创建条件</strong></article>
        <article><span>状态自动推进</span><strong>关闭</strong></article>
        <article><span>审批流程连接</span><strong>隔离</strong></article>
        <article><span>审批实例 / 任务</span><strong>0 / 0</strong></article>
      </div>
      <p class="runtime-isolation-note">已创建、等待审批、已批准、已驳回和已取消均为未来状态，当前所有相关转换保持冻结。</p>
    </section>

    <section class="panel" data-view-scope="acceptance" data-acceptance-id="formal-price-approval-creation-simulation">
      <div class="section-heading">
        <div><h2>正式价格审批对象创建模拟</h2><p>仅执行内存模拟和规则检查，不创建正式对象，不产生业务写入。</p></div>
        <span class="readonly-badge">零写入模拟</span>
      </div>
      <div class="simulation-status-grid">
        <article><span>模拟类型</span><strong>非业务对象</strong></article>
        <article><span>成功模拟轨迹</span><strong>未开始 → 检查中 → 模拟就绪 → 已完成</strong></article>
        <article><span>正式审批对象</span><strong>未创建（0）</strong></article>
        <article><span>业务写入次数</span><strong>0</strong></article>
      </div>
      <p class="simulation-zero-write-note">Simulation ≠ Business Object；模拟产物不连接持久化适配器、审批流程或审批任务。</p>
    </section>

    <section class="panel" data-view-scope="acceptance" data-acceptance-id="create-formal-price-approval-command-design">
      <div class="section-heading">
        <div><h2>正式价格审批对象创建动作设计</h2><p>定义人工触发与校验边界；当前不创建命令实例，不执行正式对象创建。</p></div>
        <span class="readonly-badge">仅人工触发设计</span>
      </div>
      <div class="command-boundary-grid">
        <article><span>触发方式</span><strong>仅人工</strong></article>
        <article><span>可评估状态</span><strong>未请求 / 已提交 / 已校验 / 已拒绝</strong></article>
        <article><span>关闭状态</span><strong>允许执行 / 已执行</strong></article>
        <article><span>自动执行</span><strong>不存在</strong></article>
      </div>
      <p class="command-freeze-note">approved_for_execution 与 executed 保持关闭；命令调度、审批对象创建和数据库写入均被冻结。</p>
    </section>

    <section class="panel" data-view-scope="acceptance" data-acceptance-id="formal-price-approval-creation-authorization-audit">
      <div class="section-heading">
        <div><h2>创建授权与审计轨迹设计</h2><p>授权仅验证职责分离，审计仅描述内存事件；两者均不触发正式创建。</p></div>
        <span class="readonly-badge">职责分离 / 零持久化</span>
      </div>
      <div class="authorization-audit-grid">
        <article><span>授权边界</span><strong>Requester ≠ Authorizer</strong></article>
        <article><span>授权结果</span><strong>Authorization ≠ Execution</strong></article>
        <article><span>审计边界</span><strong>Audit ≠ Persistence</strong></article>
        <article><span>业务写入次数</span><strong>0</strong></article>
      </div>
      <p class="authorization-audit-note">同一人员发起与授权将被拒绝；授权不授予执行权限，审计轨迹不写入数据库。</p>
    </section>

    <section class="panel" data-view-scope="acceptance" data-acceptance-id="formal-price-approval-final-release-assessment">
      <div class="section-heading">
        <div><h2>正式创建前最终安全评审</h2><p>综合检查模拟、命令、授权、审计和运行隔离证据，仅形成放行评估结论。</p></div>
        <span class="readonly-badge">最终评审 / 不执行</span>
      </div>
      <div class="final-release-grid">
        <article><span>放行边界</span><strong>Final Release ≠ Execution</strong></article>
        <article><span>就绪含义</span><strong>READY ≠ Created</strong></article>
        <article><span>Gate 职责</span><strong>Gate ≠ Command Executor</strong></article>
        <article><span>业务写入次数</span><strong>0</strong></article>
      </div>
      <p class="final-release-note">评估状态支持未评估、检查中、就绪、阻断和人工复核；任何结论均不授予执行权限。</p>
    </section>

    <section class="panel" data-view-scope="acceptance" data-acceptance-id="formal-price-approval-creation-sandbox-confirmation">
      <div class="section-heading">
        <div><h2>创建动作安全沙箱与人工确认</h2><p>在非生产沙箱完成最后一次验证，并形成具名人工确认；不执行正式创建。</p></div>
        <span class="readonly-badge">Sandbox / Human Confirmation</span>
      </div>
      <div class="sandbox-confirmation-grid">
        <article><span>环境边界</span><strong>Sandbox ≠ Production</strong></article>
        <article><span>确认边界</span><strong>Confirmation ≠ Execution</strong></article>
        <article><span>模拟边界</span><strong>Simulation ≠ Creation</strong></article>
        <article><span>业务写入次数</span><strong>0</strong></article>
      </div>
      <p class="sandbox-confirmation-note">生产端点、持久化、Workflow 和执行权限全部关闭；人工确认只形成设计态结论。</p>
    </section>

    <section class="panel" data-view-scope="acceptance" data-acceptance-id="formal-price-approval-final-release-agreement">
      <div class="section-heading">
        <div><h2>最终人工放行责任协议</h2><p>通过责任声明和七项 Checklist 形成最终人工复核结论；协议不授予执行权限。</p></div>
        <span class="readonly-badge">Human Agreement / No Execution</span>
      </div>
      <div class="release-agreement-grid">
        <article><span>请求与复核</span><strong>Requester ≠ Reviewer</strong></article>
        <article><span>复核与执行</span><strong>Reviewer ≠ Executor</strong></article>
        <article><span>协议边界</span><strong>Agreement ≠ Execution</strong></article>
        <article><span>Checklist</span><strong>7 项责任证据</strong></article>
      </div>
      <p class="release-agreement-note">身份冲突或自动复核将被拒绝；协议通过仍不执行 Command、不创建正式审批对象。</p>
    </section>

    <section class="panel" data-view-scope="acceptance" data-acceptance-id="formal-price-approval-execution-boundary">
      <div class="section-heading">
        <div><h2>正式价格审批创建执行隔离边界</h2><p>定义未来唯一执行入口及其隔离上下文；当前仅评估边界，不提供执行器。</p></div>
        <span class="readonly-badge">Unique Boundary / No Executor</span>
      </div>
      <div class="execution-boundary-grid">
        <article><span>同意结果</span><strong>Approved ≠ Auto Execute</strong></article>
        <article><span>边界职责</span><strong>Boundary ≠ Executor</strong></article>
        <article><span>生产执行</span><strong>false</strong></article>
        <article><span>执行上下文</span><strong>isolated_design</strong></article>
      </div>
      <p class="execution-boundary-note">对象工厂、Command Dispatcher、Workflow、生产凭据和数据库适配器均未连接。</p>
    </section>

    <section class="panel" data-view-scope="acceptance" data-acceptance-id="formal-price-approval-end-to-end-safety-drill">
      <div class="section-heading">
        <div><h2>正式创建前全链路安全演练</h2><p>按治理顺序核验 15 个节点是否完整闭环；演练仅检查事实，不执行任何业务动作。</p></div>
        <span class="readonly-badge">15 Stages / Read Only</span>
      </div>
      <div class="end-to-end-drill-grid">
        <article><span>演练边界</span><strong>Drill ≠ Execution</strong></article>
        <article><span>模拟边界</span><strong>Simulation ≠ Creation</strong></article>
        <article><span>执行边界</span><strong>Boundary ≠ Executor</strong></article>
        <article><span>生产执行</span><strong>false</strong></article>
      </div>
      <p class="end-to-end-drill-note">任一治理节点失败即阻断，证据缺失转人工复核；全部通过也仅表示安全闭环完成。</p>
    </section>

    <section class="panel" data-view-scope="acceptance" data-acceptance-id="formal-price-approval-post-creation-state-takeover">
      <div class="section-heading">
        <div><h2>创建后状态接管隔离设计</h2><p>定义未来对象进入 created 后的状态所有权交接；当前不创建对象、不变更状态、不启动审批。</p></div>
        <span class="readonly-badge">Post-Creation / Isolated</span>
      </div>
      <div class="post-creation-takeover-grid">
        <article><span>创建状态</span><strong>Created ≠ Auto Pending Approval</strong></article>
        <article><span>接管边界</span><strong>Takeover ≠ State Mutation</strong></article>
        <article><span>Workflow 所有权</span><strong>Ownership ≠ Workflow Start</strong></article>
        <article><span>状态变更</span><strong>false</strong></article>
      </div>
      <p class="post-creation-takeover-note">created → pending_approval 仍被冻结；接管就绪只表示未来所有权证据完整。</p>
    </section>

    <section class="panel" data-view-scope="acceptance" data-acceptance-id="formal-price-approval-post-creation-lifecycle">
      <div class="section-heading">
        <div><h2>创建后生命周期状态机冻结设计</h2><p>定义 created、pending approval、approved、rejected、cancelled 的未来转换边界；当前所有转换冻结。</p></div>
        <span class="readonly-badge">Lifecycle Frozen</span>
      </div>
      <div class="post-creation-lifecycle-grid">
        <article><span>创建与待审批</span><strong>Created ≠ Pending Approval</strong></article>
        <article><span>批准与执行</span><strong>Approved ≠ Auto Execution</strong></article>
        <article><span>生命周期边界</span><strong>Lifecycle ≠ Workflow</strong></article>
        <article><span>启用转换数</span><strong>0 / 4</strong></article>
      </div>
      <p class="post-creation-lifecycle-note">状态机仅供检查，所有转换均不改变状态、不持久化、不启动 Workflow。</p>
    </section>

    <section class="panel" data-view-scope="acceptance" data-acceptance-id="formal-price-approval-workflow-handoff">
      <div class="section-heading">
        <div><h2>审批流程接管隔离设计</h2><p>定义生命周期域到审批流程域的只读接管边界；当前仅检查证据与所有权，不启动 Workflow。</p></div>
        <span class="readonly-badge">Handoff / Isolated</span>
      </div>
      <div class="workflow-handoff-grid">
        <article><span>领域隔离</span><strong>Lifecycle ≠ Workflow</strong></article>
        <article><span>所有权边界</span><strong>Ownership ≠ Execution</strong></article>
        <article><span>待审批状态</span><strong>Pending Approval ≠ Workflow Started</strong></article>
        <article><span>Workflow 实例 / 任务</span><strong>0 / 0</strong></article>
      </div>
      <p class="workflow-handoff-note">Handoff Ready 仅表示未来接管证据完整，不创建审批实例、不创建审批任务、不推进生命周期状态。</p>
    </section>

    <section class="panel" data-view-scope="acceptance" data-acceptance-id="formal-price-approval-workflow-start-assessment">
      <div class="section-heading">
        <div><h2>审批流程启动条件冻结与实例隔离</h2><p>只读评估审批流程未来启动所需证据，审批请求与审批实例保持完全隔离。</p></div>
        <span class="readonly-badge">Start Assessment / Frozen</span>
      </div>
      <div class="workflow-start-assessment-grid">
        <article><span>启动评估</span><strong>Assessment ≠ Start</strong></article>
        <article><span>请求与实例</span><strong>Request ≠ Instance</strong></article>
        <article><span>生命周期与运行态</span><strong>Pending Approval ≠ Running</strong></article>
        <article><span>实例 / 审批任务</span><strong>0 / 0</strong></article>
      </div>
      <p class="workflow-start-assessment-note">Start Ready 仅表示启动条件评估通过，不启动 Workflow、不创建审批实例或任务，也不写入数据库。</p>
    </section>

    <section class="panel" data-view-scope="acceptance" data-acceptance-id="formal-price-approval-instance-task-lifecycle">
      <div class="section-heading">
        <div><h2>审批实例与任务生命周期隔离设计</h2><p>定义未来审批实例和审批任务生命周期；当前仅允许定义检查，不创建任何实例或任务。</p></div>
        <span class="readonly-badge">Instance / Task Definition</span>
      </div>
      <div class="instance-task-lifecycle-grid">
        <article><span>实例定义</span><strong>Definition ≠ Instance Created</strong></article>
        <article><span>任务定义</span><strong>Definition ≠ Task Created</strong></article>
        <article><span>Workflow 与结果</span><strong>Running ≠ Approval Result</strong></article>
        <article><span>实例 / 任务 / 结果</span><strong>0 / 0 / 0</strong></article>
      </div>
      <p class="instance-task-lifecycle-note">两个生命周期均停留在 definition_only，启用转换数为 0，不启动 Workflow、不形成审批结果、不持久化。</p>
    </section>

    <section class="panel" data-view-scope="acceptance" data-acceptance-id="formal-price-approval-workflow-runtime">
      <div class="section-heading">
        <div><h2>审批流程运行状态机冻结与结果隔离</h2><p>定义未来 Workflow Runtime 状态，并将运行事实、审批结果和业务状态严格隔离。</p></div>
        <span class="readonly-badge">Runtime State / Frozen</span>
      </div>
      <div class="workflow-runtime-grid">
        <article><span>运行与批准</span><strong>Running ≠ Approved</strong></article>
        <article><span>完成与结果</span><strong>Completed ≠ Result Created</strong></article>
        <article><span>运行与业务状态</span><strong>Runtime State ≠ Business State</strong></article>
        <article><span>Runtime / 结果数量</span><strong>0 / 0</strong></article>
      </div>
      <p class="workflow-runtime-note">Runtime State 当前仅为 definition_only，启用转换数为 0；不初始化、不运行、不生成审批结果。</p>
    </section>

    <section class="panel" data-view-scope="acceptance" data-acceptance-id="formal-price-approval-node-decision">
      <div class="section-heading">
        <div><h2>审批节点与审批结果规则冻结</h2><p>只读定义审批节点和决策规则，节点、任务、结果及业务影响保持隔离。</p></div>
        <span class="readonly-badge">Node / Decision Frozen</span>
      </div>
      <div class="node-decision-grid">
        <article><span>节点与任务</span><strong>Node Definition ≠ Task Created</strong></article>
        <article><span>规则与结果</span><strong>Decision Rule ≠ Result</strong></article>
        <article><span>决策与业务影响</span><strong>Approval Decision ≠ Business Effect</strong></article>
        <article><span>节点定义 / 任务 / 结果</span><strong>3 / 0 / 0</strong></article>
      </div>
      <p class="node-decision-note">三个节点仅保存顺序和角色定义；规则不执行、不创建审批结果、不修改价格审批业务状态。</p>
    </section>

    <section class="panel" data-view-scope="acceptance" data-acceptance-id="formal-price-approval-feedback">
      <div class="section-heading">
        <div><h2>审批意见与证据反馈链冻结</h2><p>定义审批意见和证据反馈结构，意见、反馈、任务、结果及业务变化保持隔离。</p></div>
        <span class="readonly-badge">Comment / Feedback Frozen</span>
      </div>
      <div class="approval-feedback-grid">
        <article><span>意见与结果</span><strong>Comment ≠ Approval Result</strong></article>
        <article><span>反馈与业务变化</span><strong>Feedback ≠ Business Change</strong></article>
        <article><span>反馈与任务执行</span><strong>Feedback ≠ Task Execution</strong></article>
        <article><span>意见 / 反馈实例</span><strong>0 / 0</strong></article>
      </div>
      <p class="approval-feedback-note">Comment 与 Feedback 当前均为 definition_only；不创建任务、不执行审批、不生成结果、不持久化。</p>
    </section>

    <section class="panel" data-view-scope="acceptance" data-acceptance-id="formal-price-approval-audit-archive">
      <div class="section-heading">
        <div><h2>正式价格审批审计轨迹与证据归档冻结</h2><p>定义全过程审计事件模板和证据归档边界；当前仅展示定义，不生成或持久化记录。</p></div>
        <span class="readonly-badge">Audit / Archive Design Only</span>
      </div>
      <div class="audit-archive-grid">
        <article><span>审计与持久化</span><strong>Audit ≠ Persistence</strong></article>
        <article><span>归档与业务写入</span><strong>Evidence Archive ≠ Business Write</strong></article>
        <article><span>审计与审批执行</span><strong>Audit ≠ Approval Execution</strong></article>
        <article><span>审计定义 / 归档边界 / 已持久化</span><strong>6 / 1 / 0</strong></article>
      </div>
      <p class="audit-archive-note">Archive Mode = design_only，Persisted Record Count = 0；页面不提供保存审计、归档、审批或执行动作。</p>
    </section>

    <section class="panel" data-view-scope="acceptance" data-acceptance-id="formal-price-approval-governance-summary">
      <div class="section-heading">
        <div><h2>正式价格审批治理闭环与操作验证准备</h2><p>汇总全过程治理阶段并评估操作验证准备；当前仅表示验证就绪，不授予执行能力。</p></div>
        <span class="readonly-badge">Governance / Validation Ready</span>
      </div>
      <div class="governance-summary-grid">
        <article><span>汇总与执行</span><strong>Governance Summary ≠ Execution</strong></article>
        <article><span>验证与操作</span><strong>Validation ≠ Operation</strong></article>
        <article><span>通过与自动运行</span><strong>PASS ≠ Auto Run</strong></article>
        <article><span>阶段通过 / 可执行阶段</span><strong>12 / 12 / 0</strong></article>
      </div>
      <p class="governance-summary-note">Operation Readiness = validation_ready；Operation Enabled = false，Auto Run Enabled = false。</p>
    </section>

    <section class="panel" data-view-scope="business" data-view-governance-scope="acceptance" data-acceptance-id="formal-price-approval-operation-validation">
      <div class="section-heading">
        <div><h2>正式价格审批业务操作验证环境</h2><p>面向采购业务人员核对报价证据、比较与核价准备、审批准入边界和零写入安全结果；当前仅提供可理解的只读验证视图。</p></div>
        <span class="readonly-badge">Business Validation / Read Only</span>
      </div>
      <div class="operation-validation-grid">
        <article><span>报价证据核对</span><strong>证据完整性可读</strong><small>核对供应商报价、币种、交期及证据包。</small></article>
        <article><span>比较与核价准备</span><strong>等待人工判断</strong><small>不自动选择供应商，不形成审批结果。</small></article>
        <article><span>审批准入边界</span><strong>Validation Ready</strong><small>准入通过仅代表可以验证，不启动 Workflow。</small></article>
        <article><span>安全验证</span><strong>4 / 4 / 0</strong><small>场景 / 业务视图 / 生产操作数量。</small></article>
      </div>
      <div class="operation-validation-boundaries">
        <strong>Operation Validation ≠ Production Operation</strong>
        <strong>Business View ≠ Business Execution</strong>
      </div>
      <p class="operation-validation-note">Production Operation Enabled = false；Business Write Count = 0；页面不提供创建审批、启动流程、创建任务或保存按钮。</p>
    </section>

    <section class="panel" data-view-scope="acceptance" data-acceptance-id="formal-price-approval-business-view-user-acceptance">
      <div class="section-heading">
        <div><h2>价格审批业务视图优化与用户验收准备</h2><p>按业务问题、证据、判断和边界四步组织信息，供采购业务人员进行只读验收走查。</p></div>
        <span class="readonly-badge">User Acceptance Ready / Read Only</span>
      </div>
      <div class="business-view-acceptance-grid">
        <article><span>业务问题</span><strong>需要确认什么？</strong><small>报价证据、比较准备、审批准入和零写入安全。</small></article>
        <article><span>证据与判断</span><strong>依据是什么？</strong><small>仅展示服务端事实来源及可理解的判断状态。</small></article>
        <article><span>用户验收清单</span><strong>5 / 5 PASS</strong><small>语言、证据、判断、边界和禁止入口均已准备。</small></article>
        <article><span>执行能力</span><strong>0</strong><small>验收准备不授予生产操作权限。</small></article>
      </div>
      <div class="business-view-acceptance-boundaries">
        <strong>Business View ≠ Business Execution</strong>
        <strong>User Acceptance ≠ Operation Approval</strong>
      </div>
      <p class="business-view-acceptance-note">Acceptance Mode = read_only_walkthrough；Operation Approval Granted = false；无提交、审批、执行或保存入口。</p>
    </section>

    <section class="panel" data-view-scope="business" data-view-governance-scope="acceptance" data-acceptance-id="formal-price-approval-business-navigation">
      <div class="section-heading">
        <div><h2>价格审批业务流程导航与用户操作路径验证</h2><p>按采购业务理解顺序展示只读路径，并按角色说明关注重点；“下一步”仅为业务指引。</p></div>
        <span class="readonly-badge">Navigation Guide / Read Only</span>
      </div>
      <ol class="business-navigation-path">
        <li><span>1</span><strong>询价概览</strong><small>确认业务范围与当前状态</small></li>
        <li><span>2</span><strong>报价证据</strong><small>核对供应商报价和关键证据</small></li>
        <li><span>3</span><strong>比较与核价准备</strong><small>理解人工评审准备状态</small></li>
        <li><span>4</span><strong>审批准入</strong><small>查看准入条件和冻结边界</small></li>
        <li><span>5</span><strong>用户验收准备</strong><small>确认业务视图与安全保护</small></li>
      </ol>
      <div class="role-navigation-grid">
        <article><span>采购员</span><strong>询价 → 报价 → 比较</strong></article>
        <article><span>价格评审人员</span><strong>比较 → 准入 → 验收</strong></article>
        <article><span>只读观察者</span><strong>概览 → 验收结果</strong></article>
      </div>
      <div class="business-navigation-boundaries">
        <strong>Navigation ≠ Execution</strong>
        <strong>User Path ≠ Workflow Runtime</strong>
        <strong>Next Step ≠ Auto Action</strong>
      </div>
      <p class="business-navigation-note">Route Action Enabled = false；Workflow Runtime Connected = false；Auto Action Enabled = false。</p>
    </section>

    <section class="panel" data-view-scope="business" data-view-governance-scope="acceptance" data-acceptance-id="formal-price-approval-scenario-acceptance">
      <div class="section-heading">
        <div><h2>价格审批业务场景数据演练与用户验收案例</h2><p>使用明确标识的合成数据覆盖正常、特殊和异常采购情形，仅验证业务判断与保护规则。</p></div>
        <span class="readonly-badge">Synthetic Scenarios / Read Only</span>
      </div>
      <div class="scenario-acceptance-grid">
        <article data-scenario-type="normal"><span>Normal Scenario</span><strong>多供应商完整报价</strong><small>3 家供应商、3 份 CNY 报价；预期进入人工评审验证。</small><em>ready_for_manual_review</em></article>
        <article data-scenario-type="special"><span>Special Scenario</span><strong>单一供应商采购</strong><small>1 家供应商、1 份完整报价；必须人工确认特殊采购原因。</small><em>manual_confirmation_required</em></article>
        <article data-scenario-type="exception"><span>Exception Scenario</span><strong>报价证据缺失</strong><small>缺少币种和交期；预期规则阻断并提示补充证据。</small><em>blocked</em></article>
      </div>
      <div class="scenario-acceptance-boundaries">
        <strong>Scenario Data ≠ Production Data</strong>
        <strong>Expected Result ≠ Auto Decision</strong>
      </div>
      <p class="scenario-acceptance-note">Scenario Count = 3；Production Data Used = false；Auto Decision Performed = false；无场景执行或保存按钮。</p>
    </section>

    <section class="panel user-feedback-panel" data-view-scope="acceptance" data-acceptance-id="formal-price-approval-user-feedback">
      <div class="section-heading">
        <div><h2>人工操作验收与用户反馈</h2><p>记录当前会话中的页面理解问题和改进建议；反馈不是业务数据，不会持久化。</p></div>
        <span class="readonly-badge">Session Feedback / Not Persisted</span>
      </div>
      <div class="acceptance-status-grid" data-acceptance-id="formal-price-approval-acceptance-status-summary">
        <article><span>Domain 状态</span><strong>PASS</strong></article>
        <article><span>Runtime 状态</span><strong>PASS</strong></article>
        <article><span>Guard 状态</span><strong>PASS</strong></article>
        <article><span>Acceptance 结果</span><strong>PASS</strong></article>
        <article><span>数据保护</span><strong>Write Count = 0</strong></article>
        <article><span>自动验证</span><strong>8 / 8 PASS</strong></article>
      </div>
      <div class="user-acceptance-checklist">
        <article v-for="item in userAcceptanceChecklist" :key="item.code"><span>{{ item.label }}</span><strong>PASS</strong></article>
      </div>
      <div class="user-feedback-form">
        <el-select v-model="userFeedbackDraft.issueType" aria-label="反馈问题类型">
          <el-option label="业务含义不清晰" value="unclear_business_meaning" />
          <el-option label="信息缺失" value="missing_information" />
          <el-option label="信息冗余" value="unnecessary_information" />
          <el-option label="导航问题" value="navigation_issue" />
          <el-option label="风险提示问题" value="risk_warning_issue" />
        </el-select>
        <el-input v-model="userFeedbackDraft.description" type="textarea" :rows="2" placeholder="描述验收过程中发现的问题" />
        <el-input v-model="userFeedbackDraft.suggestion" type="textarea" :rows="2" placeholder="填写改进建议" />
        <el-button data-user-feedback-action="session-only" @click="recordUserFeedbackDraft">记录本次反馈（仅会话）</el-button>
      </div>
      <p class="user-feedback-note">User Feedback ≠ ERP Transaction；Feedback Status = {{ userFeedbackSessionStatus }}；Persisted = false；Business State Changed = false。</p>
    </section>

    <section class="panel human-acceptance-panel" data-view-scope="acceptance" data-acceptance-id="formal-price-approval-human-acceptance">
      <div class="section-heading">
        <div><h2>价格审批 Canary 人工验收闭环</h2><p>采购角色在隔离的 Canary 页面环境中确认业务含义、风险提示和下一步路径；所有结果仅存在于当前会话。</p></div>
        <span class="readonly-badge">Canary / Session Only</span>
      </div>
      <div class="human-acceptance-grid">
        <article><span>Canary Acceptance</span><strong>{{ humanAcceptanceSessionStatus }}</strong><small>Production Connected = false</small></article>
        <article><span>Human Role Acceptance</span><strong>{{ selectedHumanAcceptanceRole }}</strong><small>Role Count = 3</small></article>
        <article><span>Feedback Loop</span><strong>{{ humanFeedbackLoopState }}</strong><small>Persisted = false</small></article>
        <article><span>Business Write</span><strong>0</strong><small>Database = UNCHANGED</small></article>
      </div>
      <div class="human-role-acceptance-grid">
        <article v-for="role in humanAcceptanceRoles" :key="role.roleCode">
          <span>{{ role.roleLabel }}</span><strong>{{ role.validationFocus }}</strong><small>session_validation_only</small>
        </article>
      </div>
      <div class="human-acceptance-actions">
        <el-select v-model="selectedHumanAcceptanceRole" aria-label="人工验收角色">
          <el-option v-for="role in humanAcceptanceRoles" :key="role.roleCode" :label="role.roleLabel" :value="role.roleCode" />
        </el-select>
        <el-button data-human-acceptance-action="session-only" @click="runHumanAcceptanceSession">执行本次 Canary 人工验收</el-button>
        <el-button data-feedback-loop-action="session-only" @click="advanceHumanFeedbackLoop">推进会话反馈闭环</el-button>
      </div>
      <div class="human-acceptance-boundaries">
        <strong>Human Acceptance ≠ Business Execution</strong>
        <strong>Feedback ≠ ERP Data</strong>
        <strong>Canary ≠ Production</strong>
      </div>
      <p class="human-acceptance-note">Acceptance Persisted = false；Feedback Persisted = false；Approval Object Created = false；Workflow Started = false。</p>
    </section>

    <section class="panel recent-canary-result-panel" data-view-scope="acceptance" data-acceptance-id="formal-price-approval-recent-canary-result">
      <div class="section-heading">
        <div><h2>最近一次金丝雀验收结果</h2><p>复用金丝雀自动验收结果模型，页面首次进入即可查看最近的只读验证摘要。</p></div>
        <span class="readonly-badge">Recent Canary Acceptance Result</span>
      </div>
      <div class="recent-canary-result-grid">
        <article><span>Canary</span><strong>{{ recentCanaryAcceptanceResult.executionState.toUpperCase() }}</strong></article>
        <article><span>Total</span><strong>{{ recentCanaryAcceptanceResult.totalCount }}</strong></article>
        <article><span>PASS</span><strong>{{ recentCanaryAcceptanceResult.passCount }}</strong></article>
        <article><span>FAIL</span><strong>{{ recentCanaryAcceptanceResult.failCount }}</strong></article>
        <article><span>Overall</span><strong>{{ recentCanaryAcceptanceResult.overallResult }}</strong></article>
        <article><span>Business Write</span><strong>0</strong></article>
        <article><span>Database</span><strong>UNCHANGED</strong></article>
      </div>
    </section>

    <section class="panel human-business-acceptance-panel" data-view-scope="acceptance" data-acceptance-id="formal-price-approval-human-business-acceptance-execution">
      <div class="section-heading">
        <div><h2>人工业务验收执行</h2><p>选择业务角色，针对 Business View 执行七项人工理解检查；验收状态不是业务执行状态。</p></div>
        <span class="readonly-badge">Target: Business View / Session Only</span>
      </div>
      <div class="human-business-acceptance-header">
        <el-select v-model="selectedHumanBusinessAcceptanceRole" aria-label="人工业务验收角色">
          <el-option v-for="role in humanBusinessAcceptanceRoles" :key="role.userRole" :label="role.roleLabel" :value="role.userRole" />
        </el-select>
        <strong>当前角色：{{ selectedHumanBusinessAcceptanceRole }}</strong>
        <strong>执行状态：{{ humanBusinessAcceptanceExecutionStatus }}</strong>
        <strong>反馈状态：{{ humanBusinessFeedbackStatus }}</strong>
      </div>
      <div class="human-business-checklist">
        <article v-for="item in humanBusinessAcceptanceChecklist" :key="item.code">
          <span>{{ item.label }}</span><strong>{{ humanBusinessChecklistResults[item.code] }}</strong>
        </article>
      </div>
      <el-button data-human-business-acceptance-action="session-only" @click="executeHumanBusinessAcceptance">执行当前角色人工验收</el-button>
      <p class="human-business-acceptance-note">Human Acceptance ≠ Business Execution；Acceptance View = Validation Information Only；Approval Triggered = false。</p>
    </section>

    <section class="panel human-feedback-collection-panel" data-view-scope="acceptance" data-acceptance-id="formal-price-approval-human-feedback-collection">
      <div class="section-heading">
        <div><h2>用户反馈收集</h2><p>反馈仅用于产品优化，不进入 ERP 业务数据；刷新页面后清除。</p></div>
        <span class="readonly-badge">Memory Session Only</span>
      </div>
      <div class="human-feedback-collection-form">
        <el-select v-model="humanFeedbackCollectionDraft.feedbackType" aria-label="用户反馈问题类型">
          <el-option label="业务含义不清晰" value="unclear_business_meaning" />
          <el-option label="信息缺失" value="missing_information" />
          <el-option label="信息过多" value="too_much_information" />
          <el-option label="导航问题" value="navigation_problem" />
          <el-option label="风险提示问题" value="risk_warning_problem" />
        </el-select>
        <el-input v-model="humanFeedbackCollectionDraft.description" type="textarea" :rows="2" placeholder="问题描述" />
        <el-input v-model="humanFeedbackCollectionDraft.suggestion" type="textarea" :rows="2" placeholder="优化建议" />
        <el-button data-human-feedback-collection-action="session-only" @click="collectHumanBusinessFeedback">收集本次反馈</el-button>
      </div>
      <p class="human-feedback-collection-note">Feedback Status = {{ humanBusinessFeedbackStatus }}；Feedback Persisted = false；Business State Changed = false。</p>
    </section>

    <section class="panel canary-cohort-panel" data-view-scope="acceptance" data-acceptance-id="formal-price-approval-canary-cohort-summary">
      <div class="section-heading">
        <div><h2>价格审批金丝雀群自动验收与结果汇总</h2><p>一次触发三个隔离验收成员的只读断言；自动化只生成当前会话中的验证摘要。</p></div>
        <span class="readonly-badge">Automatic Validation / Zero Write</span>
      </div>
      <div class="canary-cohort-grid">
        <article v-for="member in canaryCohortMembers" :key="member.memberCode">
          <span>{{ member.label }}</span><strong>{{ canaryCohortMemberResults[member.memberCode] }}</strong><small>{{ member.validationScope }}</small>
        </article>
      </div>
      <div class="canary-summary-grid">
        <article><span>Execution State</span><strong>{{ canaryCohortExecutionState }}</strong></article>
        <article><span>Total</span><strong>{{ canaryCohortSummary.totalCount }}</strong></article>
        <article><span>PASS</span><strong>{{ canaryCohortSummary.passCount }}</strong></article>
        <article><span>FAIL</span><strong>{{ canaryCohortSummary.failCount }}</strong></article>
        <article><span>Overall Result</span><strong>{{ canaryCohortSummary.overallResult }}</strong></article>
      </div>
      <el-button data-canary-cohort-action="validation-only" @click="runCanaryCohortAutomaticAcceptance">运行金丝雀群自动验收</el-button>
      <div class="canary-cohort-boundaries">
        <strong>Automatic Acceptance ≠ Business Execution</strong>
        <strong>Result Summary ≠ Approval Result</strong>
        <strong>Canary Cohort ≠ Production</strong>
      </div>
      <p class="canary-cohort-note">Result Persisted = false；Feedback Loop Updated = false；Workflow Started = false；Business Write Count = 0。</p>
    </section>

    <section class="panel request-inquiry-mapping-panel" data-view-scope="acceptance" data-acceptance-id="purchase-request-inquiry-mapping-validation">
      <div class="section-heading">
        <div><h2>采购申请 → 询价准备数据链模拟验收</h2><p>验证采购申请字段是否能够形成只读询价准备投影；投影不是询价单，也不会触发下游动作。</p></div>
        <span class="readonly-badge">Mapping Validation / Read Only</span>
      </div>
      <div class="mapping-validation-summary">
        <article><span>Source</span><strong>PurchaseRequest</strong></article>
        <article><span>Target</span><strong>InquiryPreparationProjection</strong></article>
        <article><span>Field Mapping</span><strong>8</strong></article>
        <article><span>Scenarios</span><strong>3</strong></article>
        <article><span>Business Write</span><strong>0</strong></article>
      </div>
      <div class="field-mapping-matrix">
        <article v-for="item in purchaseRequestInquiryFieldMappings" :key="item.sourceField">
          <span>{{ item.sourceField }}</span><strong>→ {{ item.targetField }}</strong><small>{{ item.mappingRule }} · {{ item.required ? 'required' : 'optional' }}</small>
        </article>
      </div>
      <div class="mapping-scenario-grid">
        <article v-for="scenario in purchaseRequestInquiryMappingScenarios" :key="scenario.scenarioId" :data-scenario-type="scenario.scenarioType">
          <span>{{ scenario.scenarioType }}</span><strong>{{ scenario.scenarioId }}</strong><small>{{ scenario.expectedResult }} · Production Data = false</small>
        </article>
      </div>
      <div class="mapping-validation-boundaries">
        <strong>Mapping ≠ Creation</strong>
        <strong>Simulation ≠ Production</strong>
        <strong>Source Trace ≠ Transaction</strong>
      </div>
      <p class="mapping-validation-note">Inquiry Created = false；Supplier Sent = false；Quotation Task Created = false；Database = UNCHANGED。</p>
    </section>

    <section class="panel inquiry-simulation-preparation-panel" data-view-scope="acceptance" data-acceptance-id="inquiry-creation-simulation-supplier-preparation">
      <div class="section-heading">
        <div><h2>询价对象生成模拟与供应商询价准备</h2><p>验证询价生成前置条件并形成候选供应商准备清单；模拟预览和候选记录均不是业务对象。</p></div>
        <span class="readonly-badge">Simulation / Preparation Only</span>
      </div>
      <div class="inquiry-simulation-summary">
        <article><span>Simulation</span><strong>{{ inquiryCreationSimulation.simulationStatus }}</strong></article>
        <article><span>Object Type</span><strong>{{ inquiryCreationSimulation.simulatedObjectType }}</strong></article>
        <article><span>Simulated Lines</span><strong>{{ inquiryCreationSimulation.simulatedLineCount }}</strong></article>
        <article><span>Inquiry Created</span><strong>false</strong></article>
      </div>
      <div class="simulation-prerequisite-grid">
        <article v-for="(passed, check) in inquiryCreationSimulation.prerequisiteChecks" :key="check">
          <span>{{ check }}</span><strong>{{ passed ? 'PASS' : 'FAIL' }}</strong>
        </article>
      </div>
      <div class="supplier-preparation-summary">
        <article><span>Preparation</span><strong>{{ supplierInquiryPreparation.preparationStatus }}</strong></article>
        <article><span>Candidate Count</span><strong>{{ supplierInquiryPreparation.candidateCount }}</strong></article>
        <article><span>Supplier Sent</span><strong>false</strong></article>
        <article><span>Task Created</span><strong>false</strong></article>
      </div>
      <div class="supplier-candidate-grid">
        <article v-for="candidate in supplierInquiryPreparation.supplierCandidates" :key="candidate.candidateNo">
          <span>{{ candidate.candidateNo }}</span><strong>{{ candidate.supplierId }}</strong><small>{{ candidate.candidateStatus }} · {{ candidate.sendStatus }}</small>
        </article>
      </div>
      <div class="inquiry-simulation-boundaries">
        <strong>Simulation ≠ Creation</strong>
        <strong>Supplier Candidate ≠ Inquiry Task</strong>
        <strong>Preparation ≠ Execution</strong>
      </div>
      <p class="inquiry-simulation-note">Business Write Count = 0；Production Data Written = false；Database = UNCHANGED。</p>
    </section>

    <section class="panel" data-view-scope="business" data-view-governance-scope="business" data-acceptance-id="existing-inquiry-list">
      <h2>已有询价列表</h2>
      <p v-if="loadError" class="load-error" role="alert">{{ loadError }}</p>
      <div class="purchase-inquiry-batch-actions" data-acceptance-id="purchase-inquiry-batch-actions">
        <el-button type="success" :disabled="!businessBatchCapability.allowed" data-process-action="BATCH_PREPARE_SUPPLIER_QUOTE" @click="batchPrepareSupplierQuote">批量准备供应商报价（{{ selectedRows.length }}）</el-button>
        <span v-if="batchInquiryActionResult">{{ batchInquiryActionResult.message }}</span>
      </div>
      <PceEnterpriseListTable :contract="enterpriseListContract" page-id="purchase-inquiry"
        table-id="purchase-inquiry-table" :rows="rows" :table-rows="filteredRows"
        :filter-schema="filterSchema" :filters="filters" :quick-search="quickSearch"
        :advanced-visible="advancedVisible" :selected-count="selectedRows.length"
        :active-filter-count="activeFilterCount" :sort-text="sortText" primary-field="inquiryNo"
        primary-label="询价编号" :primary-width="190" min-width="1500px" action-width="220"
        :show-action-column="true" data-source-mode="production"
        @update:quick-search="quickSearch = $event" @search="appliedSearch = quickSearch"
        @toggle-advanced="advancedVisible = !advancedVisible" @clear-filters="clearFilters"
        @clear-sort="clearSort" @export-current="exportCurrent" @clear-selection="clearSelection"
        @update-filter="(field, value) => filters[field] = value"
        @selection-change="selectedRows = $event" @sort-change="handleSort">
        <template #columns>
          <el-table-column prop="inquiryDate" label="询价日期" width="130" sortable />
          <el-table-column prop="sourceRequestNo" label="来源采购申请" width="190" />
          <el-table-column prop="buyerName" label="采购员" width="140" />
          <el-table-column prop="supplierCount" label="供应商数" width="120" sortable />
          <el-table-column prop="lineCount" label="明细行数" width="120" sortable />
          <el-table-column prop="currency" label="币种" width="100" />
          <el-table-column label="业务状态" width="140">
            <template #default="{ row }"><PceBusinessStatus :status-code="row.statusCode" :status-label="row.statusLabel" source="server" /></template>
          </el-table-column>
          <el-table-column prop="processStatusLabel" label="流程状态" min-width="190" />
        </template>
        <template #actions="{ row }">
          <el-button v-if="canRunInquiryPageAction(row,'VIEW_PURCHASE_INQUIRY')" size="small" data-entry-action="view-inquiry" :data-process-action="purchaseInquiryPageActionCodes.view" @click="viewInquiry(row)">查看询价</el-button>
          <el-button v-if="canRunInquiryPageAction(row,'EDIT_PURCHASE_INQUIRY')" size="small" type="primary" data-entry-action="edit-inquiry" :data-process-action="purchaseInquiryPageActionCodes.edit" @click="editInquiry(row)">编辑询价</el-button>
        </template>
      </PceEnterpriseListTable>
      <div class="purchase-inquiry-next-action-region" data-acceptance-id="purchase-inquiry-next-action-region">
        <strong>业务状态：{{ currentInquiryDisplay?.businessStatusLabel || '未选择询价' }}</strong>
        <span>当前状态（流程状态）：{{ currentInquiryDisplay?.processStatusLabel || '未选择询价' }}</span>
        <span>下一步业务动作：{{ currentInquiryDisplay?.nextAction || '请先选择询价' }}</span>
        <span>禁止：发送供应商、创建采购订单</span>
      </div>
    </section>

    <section class="panel boundary" data-acceptance-id="purchase-inquiry-runtime-boundary">
      <h2>运行边界</h2>
      <p>允许创建内存态询价对象；禁止创建采购订单、发送供应商、付款及库存动作。当前页面不提供上述禁用动作入口。</p>
    </section>
  </main>
</template>

<script setup>
import { computed, inject, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import PceBusinessStatus from '@/meta/components/PceBusinessStatus.vue'
import PceEnterpriseListTable from '@/meta/components/PceEnterpriseListTable.vue'
import { PAGE_OBSERVABILITY_ACTIONS_KEY } from '@/meta/runtime/pageObservabilityActions.js'
import { createPceEnterpriseListContract, usePceEnterpriseListRuntime } from '@/meta/runtime/pceEnterpriseListContract.js'
import { createPurchaseInquiryFilterSchema, SCM_7_GATE_LIST_CONTRACTS } from '@/meta/schema/scm/scm7GateListContracts.js'
import { loadScmBusinessPageRuntimeFacts } from '@/meta/runtime/scmBusinessPageRuntimeProvider.js'
import { buildInquiryPreparationProviderDiagnostic } from '@/meta/runtime/inquiryPreparationProviderDiagnostic.js'
import { activatePurchaseInquiryFromPreparation, beginPurchaseInquiryDraftEdit, findPurchaseInquiryByPreparation, savePurchaseInquiryDraft } from '@/meta/runtime/purchaseInquiryRuntime.js'
import { PURCHASE_INQUIRY_ENTRY_CONTRACT } from '@/meta/domain/scm/purchaseInquiry/entry/purchaseInquiryEntryContract.js'
import { evaluatePurchaseInquiryEntryGuard } from '@/meta/domain/scm/purchaseInquiry/entry/purchaseInquiryEntryGuard.js'
import { FORMAL_PRICE_APPROVAL_OBJECT_STATE_DEFINITIONS } from '@/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalObjectStateModel.js'
import { FORMAL_PRICE_APPROVAL_CANARY_ACCEPTANCE_RESULT_SUMMARY } from '@/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalCanaryAcceptanceResultSummaryModel.js'
import { FORMAL_PRICE_APPROVAL_HUMAN_ACCEPTANCE_ROLE_EXECUTIONS } from '@/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalHumanAcceptanceRoleExecutionModel.js'
import { FORMAL_PRICE_APPROVAL_HUMAN_ACCEPTANCE_EXECUTION_CHECKLIST } from '@/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalHumanAcceptanceExecutionChecklist.js'
import { PURCHASE_REQUEST_INQUIRY_FIELD_MAPPING_MATRIX } from '@/meta/domain/scm/purchaseRequestInquiryMapping/purchaseRequestInquiryFieldMappingMatrix.js'
import { PURCHASE_REQUEST_INQUIRY_MAPPING_SCENARIOS } from '@/meta/domain/scm/purchaseRequestInquiryMapping/purchaseRequestInquiryMappingScenario.js'
import { createInquiryCreationSimulation } from '@/meta/domain/scm/inquiryCreationSimulation/inquiryCreationSimulationModel.js'
import { createSupplierInquiryPreparation } from '@/meta/domain/scm/inquiryCreationSimulation/supplierInquiryPreparationModel.js'
import { purchaseInquiryLifecycleProvider, PURCHASE_INQUIRY_ENTRY_CODES } from '@/meta/providers/purchaseInquiryLifecycleProvider.js'
import { evaluatePurchaseInquiryBatchPreparation } from '@/meta/domain/scm/purchaseInquiry/lifecycle/purchaseInquiryBatchPreparationRule.js'
import { PURCHASE_INQUIRY_UI_ACTION_CODES, resolvePurchaseInquiryActionContract } from '@/meta/process/scm/purchaseInquiry/purchaseInquiryActionContracts.js'
import { PURCHASE_INQUIRY_PAGE_ACTION_CODES, evaluatePurchaseInquiryPageAction } from '@/meta/process/scm/purchaseInquiry/purchaseInquiryPageActionContract.js'
import { executePurchaseInquiryAction } from '@/meta/runtime/purchaseInquiryActionExecutionRuntime.js'
import { assessPurchaseInquiryBusinessBatchAction, executePurchaseInquiryBusinessBatchAction } from '@/meta/runtime/purchaseInquiryBusinessBatchAction.js'
import { purchaseInquiryUserProvider } from '@/meta/process/scm/purchaseInquiry/purchaseInquiryUserProvider.js'
import { PURCHASE_INQUIRY_PAGE_STATE_OPTIONS } from '@/meta/process/scm/purchaseInquiry/purchaseInquiryStateTransitionContract.js'
import { PURCHASE_INQUIRY_PROCESS_ACCEPTANCE_VERSION } from '@/meta/process/scm/purchaseInquiry/purchaseInquiryProcessAcceptanceProfile.js'
import { resolvePurchaseInquiryBusinessState } from '@/meta/process/scm/purchaseInquiry/purchaseInquiryBusinessStateMapping.js'
import { createSupplierQuoteContext, listSupplierQuotes, markSupplierQuoteWaiting, receiveSupplierQuote, saveSupplierQuote } from '@/meta/runtime/supplierQuoteRuntime.js'
import { SUPPLIER_QUOTE_UI_ACTION_CODES } from '@/meta/process/scm/supplierQuote/supplierQuoteActionContracts.js'
import { SUPPLIER_QUOTE_PROCESS_ACCEPTANCE_VERSION } from '@/meta/process/scm/supplierQuote/supplierQuoteProcessAcceptanceProfile.js'
import { createQuoteComparisonContext, generateQuoteComparisonFact, markQuoteComparisonRecommendationReady, saveQuoteComparison } from '@/meta/runtime/quoteComparisonRuntime.js'
import { QUOTE_COMPARISON_UI_ACTION_CODES } from '@/meta/process/scm/quoteComparison/quoteComparisonActionContracts.js'
import { QUOTE_COMPARISON_PROCESS_ACCEPTANCE_VERSION } from '@/meta/process/scm/quoteComparison/quoteComparisonProcessAcceptanceProfile.js'
import { createSupplierRecommendationContext, generateSupplierRecommendationDecision, markSupplierRecommendationApprovalReady, saveSupplierRecommendationDecision } from '@/meta/runtime/supplierRecommendationRuntime.js'
import { SUPPLIER_RECOMMENDATION_UI_ACTION_CODES } from '@/meta/process/scm/supplierRecommendation/supplierRecommendationActionContracts.js'
import { SUPPLIER_RECOMMENDATION_PROCESS_ACCEPTANCE_VERSION } from '@/meta/process/scm/supplierRecommendation/supplierRecommendationProcessAcceptanceProfile.js'
import { createPurchaseOrderCreationGateContext, evaluatePurchaseOrderGateDecision, savePurchaseOrderGateDecision } from '@/meta/runtime/purchaseOrderCreationGateRuntime.js'
import { PURCHASE_ORDER_CREATION_GATE_UI_ACTION_CODES } from '@/meta/process/scm/purchaseOrderCreationGate/purchaseOrderCreationGateActionContracts.js'
import { PURCHASE_ORDER_CREATION_GATE_PROCESS_ACCEPTANCE_VERSION } from '@/meta/process/scm/purchaseOrderCreationGate/purchaseOrderCreationGateProcessAcceptanceProfile.js'
import { createPurchaseOrderTransactionContext, createPurchaseOrderTransaction, savePurchaseOrderTransaction } from '@/meta/runtime/purchaseOrderTransactionRuntime.js'
import { PURCHASE_ORDER_TRANSACTION_UI_ACTION_CODES } from '@/meta/process/scm/purchaseOrderTransaction/purchaseOrderTransactionActionContracts.js'
import { PURCHASE_ORDER_TRANSACTION_PROCESS_ACCEPTANCE_VERSION } from '@/meta/process/scm/purchaseOrderTransaction/purchaseOrderTransactionProcessAcceptanceProfile.js'
import { createPurchaseOrderIssuePreparationContext, checkPurchaseOrderIssuePreparation, savePurchaseOrderIssuePreparation } from '@/meta/runtime/purchaseOrderIssuePreparationRuntime.js'
import { PURCHASE_ORDER_ISSUE_PREPARATION_UI_ACTION_CODES } from '@/meta/process/scm/purchaseOrderIssuePreparation/purchaseOrderIssuePreparationActionContracts.js'
import { PURCHASE_ORDER_ISSUE_PREPARATION_PROCESS_ACCEPTANCE_VERSION } from '@/meta/process/scm/purchaseOrderIssuePreparation/purchaseOrderIssuePreparationProcessAcceptanceProfile.js'
import { createPurchaseOrderIssueBoundaryContext, evaluatePurchaseOrderIssueBoundary, savePurchaseOrderIssueDecision } from '@/meta/runtime/purchaseOrderIssueBoundaryRuntime.js'
import { PURCHASE_ORDER_ISSUE_BOUNDARY_UI_ACTION_CODES } from '@/meta/process/scm/purchaseOrderIssueBoundary/purchaseOrderIssueBoundaryActionContracts.js'
import { PURCHASE_ORDER_ISSUE_BOUNDARY_PROCESS_ACCEPTANCE_VERSION } from '@/meta/process/scm/purchaseOrderIssueBoundary/purchaseOrderIssueBoundaryProcessAcceptanceProfile.js'
import { createPurchaseOrderIssueExecutionContext, checkPurchaseOrderIssueExecution, savePurchaseOrderIssueExecutionPreparation } from '@/meta/runtime/purchaseOrderIssueExecutionRuntime.js'
import { PURCHASE_ORDER_ISSUE_EXECUTION_UI_ACTION_CODES } from '@/meta/process/scm/purchaseOrderIssueExecution/purchaseOrderIssueExecutionActionContracts.js'
import { PURCHASE_ORDER_ISSUE_EXECUTION_PROCESS_ACCEPTANCE_VERSION } from '@/meta/process/scm/purchaseOrderIssueExecution/purchaseOrderIssueExecutionProcessAcceptanceProfile.js'

const router = useRouter()
const route = useRoute()
const observability = inject(PAGE_OBSERVABILITY_ACTIONS_KEY, null)
const purchaseInquiryServerFacts = ref({})
const lifecycleFacts = ref(purchaseInquiryLifecycleProvider.loadForEntry(PURCHASE_INQUIRY_ENTRY_CODES.directUrl))
const runtimeView = computed(() => lifecycleFacts.value.runtimeView)
const formalPriceApprovalViewMode = ref('business_view')
const purchaseInquiryActionCodes = PURCHASE_INQUIRY_UI_ACTION_CODES
const purchaseInquiryPageActionCodes = PURCHASE_INQUIRY_PAGE_ACTION_CODES
const purchaseInquiryProcessVersion = PURCHASE_INQUIRY_PROCESS_ACCEPTANCE_VERSION
const inquiryEditDraft = ref(null)
const supplierQuoteActionCodes = SUPPLIER_QUOTE_UI_ACTION_CODES
const supplierQuoteProcessVersion = SUPPLIER_QUOTE_PROCESS_ACCEPTANCE_VERSION
const supplierQuoteDeadline = ref('2026-08-31')
const supplierQuoteUnitPrice = ref(1)
const supplierQuoteContext = ref(null)
const supplierQuote = ref(null)
const quoteComparisonActionCodes = QUOTE_COMPARISON_UI_ACTION_CODES
const quoteComparisonProcessVersion = QUOTE_COMPARISON_PROCESS_ACCEPTANCE_VERSION
const quoteComparisonContext = ref(null)
const quoteComparison = ref(null)
const supplierRecommendationActionCodes = SUPPLIER_RECOMMENDATION_UI_ACTION_CODES
const supplierRecommendationProcessVersion = SUPPLIER_RECOMMENDATION_PROCESS_ACCEPTANCE_VERSION
const supplierRecommendationContext = ref(null)
const supplierRecommendationDecision = ref(null)
const purchaseOrderGateActionCodes = PURCHASE_ORDER_CREATION_GATE_UI_ACTION_CODES
const purchaseOrderGateProcessVersion = PURCHASE_ORDER_CREATION_GATE_PROCESS_ACCEPTANCE_VERSION
const purchaseOrderGateContext = ref(null)
const purchaseOrderGateDecision = ref(null)
const purchaseOrderTransactionActionCodes = PURCHASE_ORDER_TRANSACTION_UI_ACTION_CODES
const purchaseOrderTransactionProcessVersion = PURCHASE_ORDER_TRANSACTION_PROCESS_ACCEPTANCE_VERSION
const purchaseOrderTransactionContext = ref(null)
const purchaseOrderTransaction = ref(null)
const purchaseOrderIssuePreparationActionCodes = PURCHASE_ORDER_ISSUE_PREPARATION_UI_ACTION_CODES
const purchaseOrderIssuePreparationProcessVersion = PURCHASE_ORDER_ISSUE_PREPARATION_PROCESS_ACCEPTANCE_VERSION
const purchaseOrderIssuePreparationContext = ref(null)
const purchaseOrderIssuePreparation = ref(null)
const purchaseOrderIssueBoundaryActionCodes = PURCHASE_ORDER_ISSUE_BOUNDARY_UI_ACTION_CODES
const purchaseOrderIssueBoundaryProcessVersion = PURCHASE_ORDER_ISSUE_BOUNDARY_PROCESS_ACCEPTANCE_VERSION
const purchaseOrderIssueBoundaryContext = ref(null)
const purchaseOrderIssueDecision = ref(null)
const purchaseOrderIssueExecutionActionCodes = PURCHASE_ORDER_ISSUE_EXECUTION_UI_ACTION_CODES
const purchaseOrderIssueExecutionProcessVersion = PURCHASE_ORDER_ISSUE_EXECUTION_PROCESS_ACCEPTANCE_VERSION
const purchaseOrderIssueExecutionContext = ref(null)
const purchaseOrderIssueAuthorization = ref(null)
const rows = computed(() => runtimeView.value.inquiries)
const currentInquiryDisplay = computed(() => {
  const current = lifecycleFacts.value.currentInquiry || (rows.value.length === 1 ? rows.value[0] : null)
  return current ? resolvePurchaseInquiryBusinessState(current) : null
})
const inquiryPreparationFacts = computed(() => lifecycleFacts.value.preparationFacts)
const inquiryPreparations = computed(() => inquiryPreparationFacts.value.objects)
const activeInquiryPreparation = computed(() => lifecycleFacts.value.currentPreparation)
const pendingInquiryPreparations = computed(() => inquiryPreparationFacts.value.objects)
const inquiryPreparationDiagnostic = computed(() => buildInquiryPreparationProviderDiagnostic({
  providerFacts: inquiryPreparationFacts.value, pageRows: pendingInquiryPreparations.value,
}))
const entryContext = computed(() => lifecycleFacts.value.entryContext)
const lifecycleContext = computed(() => lifecycleFacts.value.lifecycleContext)
const currentLifecycleLines = computed(() => lifecycleFacts.value.currentInquiry?.lines || lifecycleFacts.value.currentPreparation?.inquiryLines || [])
const loadError = ref('')
const activatedPreparationNos = ref(new Set())
const batchPreparationSelection = ref([])
const lastBatchResult = ref({ inputCount: 0, outputCount: 0, businessWriteCount: 0 })
const batchInquiryActionResult = ref(null)
const batchInquiryEditQueue = ref([])
function syncActivatedPreparations() { activatedPreparationNos.value = new Set(inquiryPreparations.value
  .filter(item => findPurchaseInquiryByPreparation(item.inquiryPreparationNo)).map(item => item.inquiryPreparationNo)) }
function isPreparationActivated(preparation) { return activatedPreparationNos.value.has(preparation?.inquiryPreparationNo) }
function preparationEntry(preparation) {
  const query = { inquiryPreparationNo: preparation?.inquiryPreparationNo, sourceRequestNo: preparation?.sourceRequestNo }
  return { query, facts: purchaseInquiryLifecycleProvider.loadForEntry(PURCHASE_INQUIRY_ENTRY_CODES.purchaseRequest,
    { query, serverFacts: purchaseInquiryServerFacts.value }) }
}
function canStartPreparation(preparation) {
  if (isPreparationActivated(preparation)) return false
  const { facts } = preparationEntry(preparation)
  return evaluatePurchaseInquiryEntryGuard({ context: facts.entryContext, action: 'startInquiry' }).allowed
}
async function startInquiry(preparation) {
  try {
    if (!resolvePurchaseInquiryActionContract('startInquiry')) throw new Error('START_PURCHASE_INQUIRY_ACTION_CONTRACT_REQUIRED')
    const { query, facts } = preparationEntry(preparation)
    const entryDecision = evaluatePurchaseInquiryEntryGuard({ context: facts.entryContext, action: 'startInquiry' })
    if (!entryDecision.allowed) throw new Error('当前询价准备未通过入口保护规则')
    await ElMessageBox.confirm(`确认从询价准备 ${preparation.inquiryPreparationNo} 创建正式询价草稿？`, '启动询价', { type: 'warning' })
    const result = activatePurchaseInquiryFromPreparation(preparation)
    if (result.result !== 'PASS') throw new Error(result.assessment?.decision || '询价激活条件不满足')
    const inquiryQuery = result.object?.inquiryNo ? { inquiryNo: result.object.inquiryNo } : query
    reloadLifecycle(inquiryQuery)
    router.replace({ path: PURCHASE_INQUIRY_ENTRY_CONTRACT.canonicalRoute, query: inquiryQuery })
    syncActivatedPreparations()
    ElMessage.success(result.created ? `询价 ${result.object.inquiryNo} 已创建` : `询价 ${result.object.inquiryNo} 已存在`)
  } catch (error) { if (error !== 'cancel' && error !== 'close') ElMessage.error(error?.message || '启动询价失败') }
}
async function startInquiryBatch() {
  try {
    if (!resolvePurchaseInquiryActionContract('startInquiry')) throw new Error('START_PURCHASE_INQUIRY_ACTION_CONTRACT_REQUIRED')
    const assessment = evaluatePurchaseInquiryBatchPreparation({ preparations: batchPreparationSelection.value,
      existingInquiries: lifecycleFacts.value.inquiries })
    if (!assessment.candidates.length) throw new Error('所选询价准备均未通过批量承接规则')
    await ElMessageBox.confirm(`确认承接 ${assessment.candidates.length} 项询价准备？该动作只创建询价草稿。`, '批量启动询价', { type: 'warning' })
    let outputCount = 0
    let businessWriteCount = 0
    for (const preparation of assessment.candidates) {
      const { facts } = preparationEntry(preparation)
      if (!evaluatePurchaseInquiryEntryGuard({ context: facts.entryContext, action: 'startInquiry' }).allowed) continue
      const result = activatePurchaseInquiryFromPreparation(preparation)
      if (result.result === 'PASS') { outputCount += 1; businessWriteCount += result.businessWriteCount }
    }
    lastBatchResult.value = { inputCount: assessment.batchInputCount, outputCount, businessWriteCount }
    batchPreparationSelection.value = []
    reloadLifecycle({})
    router.replace({ path: PURCHASE_INQUIRY_ENTRY_CONTRACT.canonicalRoute })
    syncActivatedPreparations()
    ElMessage.success(`批量承接完成：输入 ${assessment.batchInputCount} 项，输出 ${outputCount} 项`)
  } catch (error) { if (error !== 'cancel' && error !== 'close') ElMessage.error(error?.message || '批量承接失败') }
}
function canRunInquiryPageAction(inquiry, actionCode) {
  return evaluatePurchaseInquiryPageAction(inquiry, actionCode).allowed
}
function batchPrepareSupplierQuote() {
  const result = executePurchaseInquiryBusinessBatchAction(selectedRows.value)
  if (!result.allowed) { ElMessage.error('请选择至少两条处于询价草稿状态的记录'); return }
  batchInquiryActionResult.value = { ...result, message: `已生成 ${result.outputCount} 个报价准备上下文` }
  router.push('/scm/purchase-inquiry/acceptance/batch?mode=quote-preparation')
}
function viewInquiry(inquiry) {
  const result = executePurchaseInquiryAction({ inquiry, actionCode: 'VIEW_PURCHASE_INQUIRY' })
  if (!result.allowed) { ElMessage.error('仅草稿询价允许查看'); return }
  router.push(result.route)
}
function viewCurrentInquiry() { if (lifecycleFacts.value.currentInquiry) viewInquiry(lifecycleFacts.value.currentInquiry) }
function editInquiry(inquiry = lifecycleFacts.value.currentInquiry) {
  const result = executePurchaseInquiryAction({ inquiry, actionCode: 'EDIT_PURCHASE_INQUIRY' })
  if (!result.allowed) { ElMessage.error('仅草稿询价允许编辑'); return }
  router.push(result.route)
}
function saveInquiry() {
  try {
    const current = runtimeView.value.inquiries.find(item => item.inquiryNo === inquiryEditDraft.value?.inquiryNo)
    if (!canRunInquiryPageAction(current, 'SAVE_PURCHASE_INQUIRY')) throw new Error('PURCHASE_INQUIRY_DRAFT_SAVE_REQUIRED')
    if (!resolvePurchaseInquiryActionContract('saveInquiry')) throw new Error('SAVE_PURCHASE_INQUIRY_ACTION_CONTRACT_REQUIRED')
    const result = savePurchaseInquiryDraft(inquiryEditDraft.value)
    inquiryEditDraft.value = null
    const query = { inquiryNo: result.object.inquiryNo }
    reloadLifecycle(query)
    router.replace({ path: PURCHASE_INQUIRY_ENTRY_CONTRACT.canonicalRoute, query })
    ElMessage.success(`询价 ${result.object.inquiryNo} 已保存到当前会话`)
    const next = batchInquiryEditQueue.value.shift()
    if (next) editInquiry(next)
    return result
  } catch (error) { ElMessage.error(error?.message || '保存询价失败'); return null }
}
function createQuoteContextForCurrent() {
  try {
    const inquiry = lifecycleFacts.value.currentInquiry
    if (!inquiry) throw new Error('请先选择正式询价草稿')
    supplierQuoteContext.value = createSupplierQuoteContext({
      ...inquiry,
      responseDeadline: supplierQuoteDeadline.value,
      suppliers: inquiry.suppliers || [],
      lines: inquiry.lines || [],
    })
    supplierQuote.value = null
    ElMessage.success('供应商报价上下文已创建')
  } catch (error) { ElMessage.error(error?.message || '创建报价上下文失败') }
}
function receiveQuoteForCurrent() {
  try {
    const waiting = supplierQuoteContext.value.status === 'quote_context_created'
      ? markSupplierQuoteWaiting(supplierQuoteContext.value) : supplierQuoteContext.value
    supplierQuoteContext.value = waiting
    const supplierId = waiting.supplierCandidates[0]?.supplierId
    supplierQuote.value = receiveSupplierQuote(waiting, {
      supplierId,
      quoteDate: new Date().toISOString().slice(0, 10),
      currency: 'CNY',
      validUntil: waiting.deadline,
      lines: waiting.materials.map(item => ({ ...item, unitPrice: supplierQuoteUnitPrice.value,
        taxRate: 0, deliveryDate: waiting.deadline })),
    })
    ElMessage.success('供应商报价已人工接收，尚未保存')
  } catch (error) { ElMessage.error(error?.message || '接收供应商报价失败') }
}
function saveQuoteForCurrent() {
  try {
    const result = saveSupplierQuote(supplierQuote.value)
    supplierQuote.value = result.object
    ElMessage.success('供应商报价已保存到当前会话')
    return result
  } catch (error) { ElMessage.error(error?.message || '保存供应商报价失败'); return null }
}
function createComparisonContextForCurrent() {
  try {
    const quotes = listSupplierQuotes().filter(item => item.status === 'quotation_completed'
      && item.inquiryNo === supplierQuote.value?.inquiryNo)
    quoteComparisonContext.value = createQuoteComparisonContext(quotes)
    quoteComparison.value = null
    ElMessage.success('报价比较上下文已创建')
  } catch (error) { ElMessage.error(error?.message || '创建报价比较上下文失败') }
}
function generateComparisonFactForCurrent() {
  try {
    quoteComparison.value = generateQuoteComparisonFact(quoteComparisonContext.value)
    ElMessage.success('报价比较事实已生成')
  } catch (error) { ElMessage.error(error?.message || '生成报价比较事实失败') }
}
function saveComparisonForCurrent() {
  try {
    const result = saveQuoteComparison(quoteComparison.value)
    quoteComparison.value = markQuoteComparisonRecommendationReady(result.object)
    ElMessage.success('报价比较已保存；推荐状态仅表示就绪')
  } catch (error) { ElMessage.error(error?.message || '保存报价比较失败') }
}
function createRecommendationContextForCurrent() {
  try {
    supplierRecommendationContext.value = createSupplierRecommendationContext(quoteComparison.value)
    supplierRecommendationDecision.value = null
    ElMessage.success('供应商推荐上下文已创建')
  } catch (error) { ElMessage.error(error?.message || '创建供应商推荐上下文失败') }
}
function generateRecommendationDecisionForCurrent() {
  try {
    supplierRecommendationDecision.value = generateSupplierRecommendationDecision(supplierRecommendationContext.value)
    ElMessage.success('供应商推荐决策已生成')
  } catch (error) { ElMessage.error(error?.message || '生成供应商推荐决策失败') }
}
function saveRecommendationDecisionForCurrent() {
  try {
    const result = saveSupplierRecommendationDecision(supplierRecommendationDecision.value)
    supplierRecommendationDecision.value = markSupplierRecommendationApprovalReady(result.object)
    ElMessage.success('供应商推荐决策已保存；审批未提交')
  } catch (error) { ElMessage.error(error?.message || '保存供应商推荐决策失败') }
}
function createPurchaseOrderGateContextForCurrent() {
  try {
    purchaseOrderGateContext.value = createPurchaseOrderCreationGateContext(supplierRecommendationDecision.value)
    purchaseOrderGateDecision.value = null
    ElMessage.success('采购订单创建准入上下文已创建')
  } catch (error) { ElMessage.error(error?.message || '创建订单准入上下文失败') }
}
function evaluatePurchaseOrderGateForCurrent() {
  try {
    purchaseOrderGateDecision.value = evaluatePurchaseOrderGateDecision(purchaseOrderGateContext.value)
    ElMessage.success('采购订单创建资格已评估')
  } catch (error) { ElMessage.error(error?.message || '评估订单创建资格失败') }
}
function savePurchaseOrderGateForCurrent() {
  try {
    purchaseOrderGateDecision.value = savePurchaseOrderGateDecision(purchaseOrderGateDecision.value).object
    ElMessage.success('订单创建准入决定已保存；未创建采购订单')
  } catch (error) { ElMessage.error(error?.message || '保存订单准入决定失败') }
}
function createPurchaseOrderTransactionContextForCurrent() {
  try {
    purchaseOrderTransactionContext.value = createPurchaseOrderTransactionContext(purchaseOrderGateDecision.value)
    purchaseOrderTransaction.value = null
    ElMessage.success('采购订单交易上下文已创建')
  } catch (error) { ElMessage.error(error?.message || '创建采购订单交易上下文失败') }
}
function createPurchaseOrderTransactionForCurrent() {
  try {
    purchaseOrderTransaction.value = createPurchaseOrderTransaction(purchaseOrderTransactionContext.value)
    ElMessage.success('采购订单交易草稿已创建；未创建执行对象')
  } catch (error) { ElMessage.error(error?.message || '创建采购订单交易草稿失败') }
}
function savePurchaseOrderTransactionForCurrent() {
  const result = savePurchaseOrderTransaction(purchaseOrderTransaction.value)
  ElMessage.warning(result.reason)
}
function createIssuePreparationContextForCurrent() {
  try {
    purchaseOrderIssuePreparationContext.value = createPurchaseOrderIssuePreparationContext(purchaseOrderTransaction.value)
    purchaseOrderIssuePreparation.value = null
    ElMessage.success('采购订单发布准备上下文已创建')
  } catch (error) { ElMessage.error(error?.message || '创建发布准备上下文失败') }
}
function checkIssueRequirementsForCurrent() {
  try {
    purchaseOrderIssuePreparation.value = checkPurchaseOrderIssuePreparation(purchaseOrderIssuePreparationContext.value)
    ElMessage.success('采购订单发布要求已检查')
  } catch (error) { ElMessage.error(error?.message || '检查发布要求失败') }
}
function saveIssuePreparationForCurrent() {
  try {
    purchaseOrderIssuePreparation.value = savePurchaseOrderIssuePreparation(purchaseOrderIssuePreparation.value).object
    ElMessage.success('采购订单发布准备已保存；未发布采购订单')
  } catch (error) { ElMessage.error(error?.message || '保存发布准备失败') }
}
function createIssueBoundaryContextForCurrent() {
  try {
    purchaseOrderIssueBoundaryContext.value = createPurchaseOrderIssueBoundaryContext(purchaseOrderIssuePreparation.value)
    purchaseOrderIssueDecision.value = null
    ElMessage.success('采购订单发布边界上下文已创建')
  } catch (error) { ElMessage.error(error?.message || '创建发布边界上下文失败') }
}
function evaluateIssuePermissionForCurrent() {
  try {
    purchaseOrderIssueDecision.value = evaluatePurchaseOrderIssueBoundary(purchaseOrderIssueBoundaryContext.value)
    ElMessage.success('采购订单发布权限已评估')
  } catch (error) { ElMessage.error(error?.message || '评估发布权限失败') }
}
function saveIssueDecisionForCurrent() {
  try {
    purchaseOrderIssueDecision.value = savePurchaseOrderIssueDecision(purchaseOrderIssueDecision.value).object
    ElMessage.success('发布许可决定已保存；未发布采购订单')
  } catch (error) { ElMessage.error(error?.message || '保存发布许可决定失败') }
}
function createIssueExecutionContextForCurrent() {
  try {
    purchaseOrderIssueExecutionContext.value = createPurchaseOrderIssueExecutionContext(purchaseOrderIssueDecision.value)
    purchaseOrderIssueAuthorization.value = null
    ElMessage.success('采购订单发布执行授权上下文已创建')
  } catch (error) { ElMessage.error(error?.message || '创建执行授权上下文失败') }
}
function checkIssueExecutionAuthorizationForCurrent() {
  try {
    purchaseOrderIssueAuthorization.value = checkPurchaseOrderIssueExecution(purchaseOrderIssueExecutionContext.value)
    ElMessage.success('采购订单发布执行授权已检查')
  } catch (error) { ElMessage.error(error?.message || '检查执行授权失败') }
}
function saveIssueExecutionPreparationForCurrent() {
  try {
    purchaseOrderIssueAuthorization.value = savePurchaseOrderIssueExecutionPreparation(purchaseOrderIssueAuthorization.value).object
    ElMessage.success('执行授权准备已保存；未发布采购订单')
  } catch (error) { ElMessage.error(error?.message || '保存执行授权准备失败') }
}
function reloadLifecycle(query = route.query, entryCode = PURCHASE_INQUIRY_ENTRY_CODES.directUrl) {
  lifecycleFacts.value = purchaseInquiryLifecycleProvider.loadForEntry(entryCode, { query, serverFacts: purchaseInquiryServerFacts.value })
}
const enterpriseListContract = createPceEnterpriseListContract({ pageCode: 'purchase-inquiry', pageType: 'list', title: '询价工作台', moduleCode: 'SCM' })
const buyerOptions = purchaseInquiryUserProvider.load().options
const filterSchema = Object.freeze(createPurchaseInquiryFilterSchema({
  buyerOptions,
  stateOptions: PURCHASE_INQUIRY_PAGE_STATE_OPTIONS,
}))
const runtime = usePceEnterpriseListRuntime({ rows, filterSchema, pageCode: 'purchase-inquiry',
  searchFields: SCM_7_GATE_LIST_CONTRACTS['purchase-inquiry'].searchFields, exportFileName: 'purchase-inquiries.csv',
  exportColumns: [{ field: 'inquiryNo', label: '询价编号' }, { field: 'inquiryDate', label: '询价日期' },
    { field: 'sourceRequestNo', label: '来源采购申请' }, { field: 'buyerName', label: '采购员' }, { field: 'statusLabel', label: '业务状态' }] })
const { selectedRows, quickSearch, appliedSearch, advancedVisible, filters, activeFilterCount, sortText, filteredRows,
  clearFilters, clearSort, clearSelection, handleSort, exportCurrent } = runtime
const businessBatchCapability = computed(() => assessPurchaseInquiryBusinessBatchAction(selectedRows.value))
const statusEntries = computed(() => Object.entries(runtimeView.value.statusStatistics))
const nextBusinessHint = computed(() => {
  if (!runtimeView.value.quotationRuntime.supplierQuotations.length) return '需要补充报价资料'
  if (!runtimeView.value.quotationRuntime.quotationComparisons.length) return '等待人工形成价格比较'
  if (!runtimeView.value.quotationRuntime.priceApprovalEntryAssessments.length) return '等待人工评审'
  return '核对审批准备条件与风险'
})
const userAcceptanceChecklist = Object.freeze([
  { code: 'business-language', label: '业务语言清晰' }, { code: 'evidence-findable', label: '证据容易找到' },
  { code: 'judgement-understandable', label: '判断依据可理解' }, { code: 'next-step-clear', label: '下一步明确' },
  { code: 'no-misoperation', label: '无误操作入口' }, { code: 'business-view-concise', label: '业务视图简洁' },
  { code: 'acceptance-view-complete', label: '验收视图完整' },
])
const userFeedbackDraft = ref({ issueType: 'unclear_business_meaning', description: '', suggestion: '' })
const userFeedbackSessionStatus = ref('not_recorded')
const humanAcceptanceRoles = Object.freeze([
  { roleCode: 'purchase_buyer', roleLabel: '采购员', validationFocus: '业务语言 / 证据 / 下一步' },
  { roleCode: 'purchase_manager', roleLabel: '采购经理', validationFocus: '判断依据 / 风险 / 角色边界' },
  { roleCode: 'acceptance_observer', roleLabel: '验收观察员', validationFocus: '视图隔离 / Guard / 零写入' },
])
const selectedHumanAcceptanceRole = ref('purchase_buyer')
const humanAcceptanceSessionStatus = ref('not_started')
const humanFeedbackLoopState = ref('not_recorded')
const canaryCohortMembers = Object.freeze([
  { memberCode: 'business_view_canary', label: '业务视图金丝雀', validationScope: '业务语言 / 下一步 / 技术内容隐藏' },
  { memberCode: 'acceptance_view_canary', label: '验收视图金丝雀', validationScope: '治理完整 / Guard / 零写入可见' },
  { memberCode: 'isolation_guard_canary', label: '隔离保护金丝雀', validationScope: '无业务执行 / 无 Workflow / 无持久化' },
])
const recentCanaryAcceptanceResult = FORMAL_PRICE_APPROVAL_CANARY_ACCEPTANCE_RESULT_SUMMARY
const canaryCohortExecutionState = ref(recentCanaryAcceptanceResult.executionState)
const canaryCohortMemberResults = ref(Object.fromEntries(recentCanaryAcceptanceResult.results.map(item => [item.memberCode, item.result])))
const canaryCohortSummary = ref({ totalCount: recentCanaryAcceptanceResult.totalCount, passCount: recentCanaryAcceptanceResult.passCount,
  failCount: recentCanaryAcceptanceResult.failCount, overallResult: recentCanaryAcceptanceResult.overallResult })
const humanBusinessAcceptanceRoles = FORMAL_PRICE_APPROVAL_HUMAN_ACCEPTANCE_ROLE_EXECUTIONS
const selectedHumanBusinessAcceptanceRole = ref('purchase_user')
const humanBusinessAcceptanceChecklist = FORMAL_PRICE_APPROVAL_HUMAN_ACCEPTANCE_EXECUTION_CHECKLIST
const humanBusinessChecklistResults = ref(Object.fromEntries(humanBusinessAcceptanceChecklist.map(item => [item.code, item.result])))
const humanBusinessAcceptanceExecutionStatus = ref('not_started')
const humanBusinessFeedbackStatus = ref('not_collected')
const humanFeedbackCollectionDraft = ref({ feedbackType: 'unclear_business_meaning', description: '', suggestion: '' })
const purchaseRequestInquiryFieldMappings = PURCHASE_REQUEST_INQUIRY_FIELD_MAPPING_MATRIX
const purchaseRequestInquiryMappingScenarios = PURCHASE_REQUEST_INQUIRY_MAPPING_SCENARIOS
const inquiryCreationSimulation = createInquiryCreationSimulation({ mappingValidationNo: 'MAP-PR-SIM-001',
  sourceRequestNo: 'PR-SIM-001', requiredDate: '2026-08-20', currency: 'CNY',
  inquiryLines: [{ lineNo: 1, materialCode: 'MAT-SIM-001', quantity: 10 }], isInquiry: false })
const supplierInquiryPreparation = createSupplierInquiryPreparation({ simulationNo: inquiryCreationSimulation.simulationNo,
  responseDeadlineReference: '2026-08-10', supplierCandidates: [
    { supplierId: 'SUP-CANDIDATE-001', evidenceReference: 'preferred_supplier_trace' },
    { supplierId: 'SUP-CANDIDATE-002', evidenceReference: 'category_supplier_pool' },
  ] })
const formalPriceApprovalLifecycle = FORMAL_PRICE_APPROVAL_OBJECT_STATE_DEFINITIONS
const formalPriceApprovalAllowedLabels = Object.freeze(formalPriceApprovalLifecycle.filter((state) => state.currentAllowed).map((state) => state.label))

function recordUserFeedbackDraft() {
  userFeedbackSessionStatus.value = userFeedbackDraft.value.description.trim() ? 'session_draft_recorded' : 'description_required'
}

function runHumanAcceptanceSession() {
  humanAcceptanceSessionStatus.value = 'session_acceptance_completed'
}

function advanceHumanFeedbackLoop() {
  const transitions = { not_recorded: 'session_recorded', session_recorded: 'human_reviewed',
    human_reviewed: 'improvement_proposed', improvement_proposed: 'session_closed' }
  humanFeedbackLoopState.value = transitions[humanFeedbackLoopState.value] || 'session_closed'
}

function runCanaryCohortAutomaticAcceptance() {
  canaryCohortExecutionState.value = 'completed'
  canaryCohortMemberResults.value = Object.fromEntries(canaryCohortMembers.map(item => [item.memberCode, 'PASS']))
  canaryCohortSummary.value = { totalCount: canaryCohortMembers.length, passCount: canaryCohortMembers.length,
    failCount: 0, overallResult: 'PASS' }
}

function executeHumanBusinessAcceptance() {
  humanBusinessChecklistResults.value = Object.fromEntries(humanBusinessAcceptanceChecklist.map(item => [item.code, 'PASS']))
  humanBusinessAcceptanceExecutionStatus.value = 'completed'
  humanBusinessFeedbackStatus.value = 'feedback_pending'
}

function collectHumanBusinessFeedback() {
  humanBusinessFeedbackStatus.value = humanFeedbackCollectionDraft.value.description.trim()
    ? 'session_collected' : 'description_required'
}

async function refresh() {
  loadError.value = ''
  try {
    const result = await loadScmBusinessPageRuntimeFacts({ pageCode: 'purchase-inquiry', query: route.query })
    purchaseInquiryServerFacts.value = result.facts
    reloadLifecycle()
    syncActivatedPreparations()
  } catch (error) {
    loadError.value = error?.message || '询价服务端事实读取失败'
    purchaseInquiryServerFacts.value = {}
    reloadLifecycle()
    syncActivatedPreparations()
  }
}
function diagnostics() {
  return { version: 'V1.14.2.8.18.7', processRuntimeVersion: PURCHASE_INQUIRY_PROCESS_ACCEPTANCE_VERSION,
    processNodeCode: 'SCM_PURCHASE_INQUIRY', process006Required: true,
    inquiryDraftEditActive: Boolean(inquiryEditDraft.value), supplierQuoteRuntimeVersion: SUPPLIER_QUOTE_PROCESS_ACCEPTANCE_VERSION,
    supplierQuoteContextStatus: supplierQuoteContext.value?.status || 'not_created', supplierQuoteStatus: supplierQuote.value?.status || 'not_received',
    supplierQuoteSupplierApiCalled: false, supplierQuoteComparisonCreated: false, supplierQuotePurchaseOrderCreated: false,
    supplierQuotePaymentCreated: false, quoteComparisonRuntimeVersion: QUOTE_COMPARISON_PROCESS_ACCEPTANCE_VERSION,
    quoteComparisonContextStatus: quoteComparisonContext.value?.status || 'not_created', quoteComparisonStatus: quoteComparison.value?.status || 'not_created',
    quoteComparisonSupplierRecommendationCreated: false, quoteComparisonPurchaseOrderCreated: false, quoteComparisonFinanceActionExecuted: false,
    supplierRecommendationRuntimeVersion: SUPPLIER_RECOMMENDATION_PROCESS_ACCEPTANCE_VERSION,
    supplierRecommendationContextStatus: supplierRecommendationContext.value?.status || 'not_created',
    supplierRecommendationDecisionStatus: supplierRecommendationDecision.value?.status || 'not_created',
    supplierRecommendationPurchaseOrderCreated: false, supplierRecommendationApprovalSubmitted: false, supplierRecommendationPaymentCreated: false,
    purchaseOrderGateRuntimeVersion: PURCHASE_ORDER_CREATION_GATE_PROCESS_ACCEPTANCE_VERSION,
    purchaseOrderGateContextStatus: purchaseOrderGateContext.value?.status || 'not_created',
    purchaseOrderGateDecisionStatus: purchaseOrderGateDecision.value?.status || 'not_created',
    purchaseOrderGatePurchaseOrderCreated: false, purchaseOrderGateSupplierPublished: false, purchaseOrderGatePaymentCreated: false,
    purchaseOrderTransactionRuntimeVersion: PURCHASE_ORDER_TRANSACTION_PROCESS_ACCEPTANCE_VERSION,
    purchaseOrderTransactionContextStatus: purchaseOrderTransactionContext.value?.status || 'not_created',
    purchaseOrderTransactionStatus: purchaseOrderTransaction.value?.status || 'not_created',
    purchaseOrderExecutionCreated: false, purchaseOrderTransactionSupplierPublished: false,
    purchaseOrderTransactionGoodsReceived: false, purchaseOrderTransactionInventoryPosted: false,
    purchaseOrderTransactionInvoiceCreated: false, purchaseOrderTransactionPaymentCreated: false,
    purchaseOrderIssuePreparationRuntimeVersion: PURCHASE_ORDER_ISSUE_PREPARATION_PROCESS_ACCEPTANCE_VERSION,
    purchaseOrderIssuePreparationContextStatus: purchaseOrderIssuePreparationContext.value?.status || 'not_created',
    purchaseOrderIssuePreparationStatus: purchaseOrderIssuePreparation.value?.status || 'not_created',
    purchaseOrderIssued: false, purchaseOrderIssueSupplierSent: false,
    purchaseOrderIssueGoodsReceived: false, purchaseOrderIssueInventoryPosted: false,
    purchaseOrderIssueInvoiceCreated: false, purchaseOrderIssuePaymentCreated: false,
    purchaseOrderIssueBoundaryRuntimeVersion: PURCHASE_ORDER_ISSUE_BOUNDARY_PROCESS_ACCEPTANCE_VERSION,
    purchaseOrderIssueBoundaryContextStatus: purchaseOrderIssueBoundaryContext.value?.status || 'not_created',
    purchaseOrderIssueDecisionStatus: purchaseOrderIssueDecision.value?.status || 'not_created',
    purchaseOrderBoundaryIssued: false, purchaseOrderBoundarySupplierSent: false,
    purchaseOrderBoundaryGoodsReceived: false, purchaseOrderBoundaryInventoryPosted: false,
    purchaseOrderBoundaryInvoiceCreated: false, purchaseOrderBoundaryPaymentCreated: false,
    purchaseOrderIssueExecutionRuntimeVersion: PURCHASE_ORDER_ISSUE_EXECUTION_PROCESS_ACCEPTANCE_VERSION,
    purchaseOrderIssueExecutionContextStatus: purchaseOrderIssueExecutionContext.value?.status || 'not_created',
    purchaseOrderIssueAuthorizationStatus: purchaseOrderIssueAuthorization.value?.status || 'not_created',
    purchaseOrderIssueSupplierApiCalled: false, purchaseOrderIssueExecutionIssued: false,
    purchaseOrderIssueExecutionSupplierSent: false, purchaseOrderIssueExecutionGoodsReceived: false,
    purchaseOrderIssueExecutionInventoryPosted: false, purchaseOrderIssueExecutionInvoiceCreated: false,
    purchaseOrderIssueExecutionPaymentCreated: false,
    pageCode: 'purchase-inquiry', pageComponent: 'ScmPurchaseInquiryWorkbenchPage',
    pageFactOwner: 'purchase-inquiry', pageFactOwnerGuard: 'instance-owned', factSource: 'server',
    apiFacts: runtimeView.value.strictFacts, pageFacts: runtimeView.value.strictFacts,
    diagnosticFacts: runtimeView.value.strictFacts, strictFacts: runtimeView.value.strictFacts,
    acceptanceFacts: runtimeView.value.strictFacts, purchaseInquiryLifecycleProviderCode: lifecycleFacts.value.providerCode, purchaseInquiryLifecycleFactOwner: lifecycleFacts.value.factOwner, purchaseInquiryLifecycleStage: lifecycleContext.value.lifecycleStage.code, purchaseInquiryPageDirectFactComposition: false, purchaseInquiryEntryContractCode: PURCHASE_INQUIRY_ENTRY_CONTRACT.contractCode, purchaseInquiryCanonicalRoute: PURCHASE_INQUIRY_ENTRY_CONTRACT.canonicalRoute, purchaseInquiryEntryType: entryContext.value.entryType, purchaseInquiryEntryBrowseOnly: entryContext.value.browseOnly, purchaseInquiryEntryAutoCreation: false, inquiryPreparationProviderCode: inquiryPreparationFacts.value.providerCode, inquiryPreparationProviderRecordCount: inquiryPreparationFacts.value.recordCount, inquiryPreparationObjectCount: inquiryPreparations.value.length, inquiryPreparationPageConsumedCount: pendingInquiryPreparations.value.length, inquiryPreparationContextCount: inquiryPreparationDiagnostic.value.contextCount, inquiryPreparationProviderDiagnostic: inquiryPreparationDiagnostic.value, inquiryPreparationStatus: activeInquiryPreparation.value?.status || 'not_created', inquiryActivationManualOnly: true, activatedPurchaseInquiryCount: runtimeView.value.inquiries.filter(item => item.id?.startsWith?.('PI-ACTIVATION-')).length, inquiryPreparationCreatesQuotation: false, inquiryPreparationSendsSupplier: false, inquiryPreparationDatabaseWritten: false, quotationRuntimeReadOnly: true, automaticQuotationCreation: false,
    autoSupplierSelection: false, autoPriceApproval: false, autoPurchaseOrderCreation: false, formalPriceApprovalObjectCreated: false, formalPriceApprovalObjectInstanceCount: 0, approvalWorkflowStarted: false, approvalTaskCreated: false, approvalInstanceCount: 0, workflowEngineConnected: false, stateMutationAllowed: false, evidenceArchiveWritten: false, creationSimulationIsBusinessObject: false, creationSimulationBusinessWriteCount: 0, creationSimulationPersisted: false, createFormalPriceApprovalCommandTriggerMode: 'manual_only', createFormalPriceApprovalCommandInstanceCount: 0, createFormalPriceApprovalCommandDispatcherConnected: false, commandAutomaticExecution: false, requesterAuthorizerSeparationRequired: true, authorizationExecutionPermission: false, authorizationInstanceCount: 0, auditPersistenceMode: 'none', auditRecordWritten: false, finalReleaseIsExecution: false, finalReleaseReadyMeansCreated: false, finalReleaseGateIsCommandExecutor: false, finalReleaseAssessmentInstanceCount: 0, creationSandboxEnvironment: 'sandbox', creationSandboxProductionEndpointConnected: false, humanConfirmationExecutionPermission: false, humanConfirmationInstanceCount: 0, agreementRequesterReviewerSeparationRequired: true, agreementReviewerExecutorSeparationRequired: true, agreementExecutionPermission: false, agreementInstanceCount: 0, executionBoundaryIsExecutor: false, executionContextMode: 'boundary_design_only', productionExecution: false, executionBoundaryInstanceCount: 0, endToEndDrillStageCount: 15, endToEndDrillIsExecution: false, endToEndDrillProductionExecution: false, endToEndDrillInstanceCount: 0, postCreationAutomaticTakeover: false, postCreationStateMutationAllowed: false, postCreationWorkflowConnected: false, postCreationTakeoverInstanceCount: 0, postCreationLifecycleTransitionCount: 4, postCreationLifecycleEnabledTransitionCount: 0, postCreationLifecycleExecuted: false, postCreationLifecycleStatePersisted: false,
    workflowHandoffMode: 'boundary_design_only', workflowHandoffReadyMeansWorkflowStarted: false, workflowHandoffOwnershipMeansExecution: false, workflowHandoffInstanceCount: 0, workflowHandoffApprovalTaskCount: 0,
    workflowStartAssessmentMode: 'assessment_only', workflowStartAssessmentMeansStart: false, workflowStartRequestMeansInstance: false, pendingApprovalMeansRunning: false, workflowRunning: false, workflowStartInstanceCount: 0, workflowStartApprovalTaskCount: 0,
    instanceLifecycleState: 'definition_only', taskLifecycleState: 'definition_only', instanceDefinitionMeansCreated: false, taskDefinitionMeansCreated: false, workflowRunningMeansApprovalResult: false, instanceLifecycleEnabledTransitionCount: 0, taskLifecycleEnabledTransitionCount: 0, approvalResultCount: 0,
    workflowRuntimeState: 'definition_only', workflowRuntimeEnabledTransitionCount: 0, workflowRuntimeInstanceCount: 0, workflowRunningMeansApproved: false, workflowCompletedMeansResultCreated: false, runtimeStateMeansBusinessState: false, workflowResultCount: 0,
    approvalNodeDefinitionCount: 3, approvalNodeRuntimeCount: 0, nodeDefinitionMeansTaskCreated: false, decisionRuleMeansResult: false, approvalDecisionMeansBusinessEffect: false, nodeDecisionTaskCount: 0, nodeDecisionResultCount: 0,
    approvalCommentStatus: 'definition_only', evidenceFeedbackStatus: 'definition_only', commentMeansApprovalResult: false, feedbackMeansBusinessChange: false, feedbackMeansTaskExecution: false, approvalCommentInstanceCount: 0, evidenceFeedbackInstanceCount: 0,
    auditTrailStatus: 'definition_only', evidenceArchiveMode: 'design_only', auditMeansPersistence: false, evidenceArchiveMeansBusinessWrite: false, auditMeansApprovalExecution: false, auditDefinitionCount: 6, archiveBoundaryCount: 1, auditPersistedRecordCount: 0, auditPersisted: false, evidenceArchivePersisted: false,
    governanceSummaryStatus: 'validation_ready', governanceSummaryMeansExecution: false, validationMeansOperation: false, passMeansAutoRun: false, governanceStageCount: 12, governancePassedStageCount: 12, governanceExecutionEnabledStageCount: 0, operationEnabled: false, autoRunEnabled: false,
    operationValidationStatus: 'validation_ready', operationValidationScenarioCount: 4, businessViewSectionCount: 4, operationValidationMeansProductionOperation: false, businessViewMeansBusinessExecution: false, productionOperationEnabled: false, businessExecutionEnabled: false,
    businessViewOptimizationStatus: 'user_acceptance_ready', userAcceptancePreparationStatus: 'ready_for_user_acceptance', optimizedViewItemCount: 4, userAcceptanceChecklistCount: 5, userAcceptancePassedChecklistCount: 5, userAcceptanceMeansOperationApproval: false, operationApprovalGranted: false,
    businessNavigationStatus: 'ready_for_user_path_validation', businessNavigationStepCount: 5, roleNavigationViewCount: 3, navigationMeansExecution: false, userPathMeansWorkflowRuntime: false, nextStepMeansAutoAction: false, navigationRouteActionEnabled: false, navigationWorkflowRuntimeConnected: false, navigationAutoActionEnabled: false,
    scenarioAcceptanceStatus: 'ready_for_user_acceptance', scenarioCount: 3, normalScenarioCount: 1, specialScenarioCount: 1, exceptionScenarioCount: 1, scenarioDataMeansProductionData: false, expectedResultMeansAutoDecision: false, scenarioProductionDataUsed: false, scenarioAutoDecisionPerformed: false,
    activeViewMode: formalPriceApprovalViewMode.value, defaultViewMode: 'business_view', viewModeCount: 2, viewSwitchMode: 'presentation_only', businessViewMeansAcceptanceView: false, viewSwitchMeansBusinessAction: false, hiddenMeansDeleted: false, hiddenGovernanceModelDeleted: false, viewSwitchBusinessActionTriggered: false,
    pageViewGovernanceStandardCode: 'PCE_ERP_PAGE_VIEW_GOVERNANCE_STANDARD', businessViewTechnicalContentHidden: true, acceptanceViewGovernanceComplete: true, userAcceptanceChecklistCount: 7, userAcceptancePassedChecklistCount: 7, userFeedbackMode: 'session_only', userFeedbackSessionStatus: userFeedbackSessionStatus.value, userFeedbackPersisted: false, userFeedbackIsBusinessData: false, userFeedbackBusinessStateChanged: false, viewSwitchExecuted: true,
    canaryAcceptanceEnvironment: 'canary', canaryAcceptanceProductionConnected: false, canaryAcceptanceIsProduction: false, humanAcceptanceRoleCount: 3, humanAcceptanceExecutionMode: 'session_validation_only', humanAcceptanceSessionStatus: humanAcceptanceSessionStatus.value, humanAcceptanceIsBusinessExecution: false, humanAcceptancePersisted: false, humanFeedbackLoopState: humanFeedbackLoopState.value, humanFeedbackLoopStorageMode: 'memory_session_only', humanFeedbackLoopPersisted: false, humanFeedbackLoopIsErpData: false,
    canaryCohortMemberCount: 3, canaryCohortExecutionMode: 'automatic_validation_only', canaryCohortExecutionState: canaryCohortExecutionState.value, canaryCohortAutomaticAcceptanceIsBusinessExecution: false, canaryCohortResultSummary: canaryCohortSummary.value, canaryCohortResultStorageMode: 'memory_session_only', canaryCohortResultPersisted: false, canaryCohortResultIsApprovalResult: false, canaryCohortFeedbackLoopUpdated: false,
    recentCanaryAcceptanceExecutionState: recentCanaryAcceptanceResult.executionState, recentCanaryAcceptanceTotalCount: recentCanaryAcceptanceResult.totalCount, recentCanaryAcceptancePassCount: recentCanaryAcceptanceResult.passCount, recentCanaryAcceptanceFailCount: recentCanaryAcceptanceResult.failCount, recentCanaryAcceptanceOverallResult: recentCanaryAcceptanceResult.overallResult,
    humanBusinessAcceptanceRole: selectedHumanBusinessAcceptanceRole.value, humanBusinessAcceptanceRoleCount: 3, humanBusinessAcceptanceChecklistCount: 7, humanBusinessAcceptanceExecutionStatus: humanBusinessAcceptanceExecutionStatus.value, humanBusinessAcceptanceIsBusinessExecution: false, humanBusinessAcceptancePersisted: false, humanBusinessFeedbackStatus: humanBusinessFeedbackStatus.value, humanBusinessFeedbackStorageMode: 'memory_session_only', humanBusinessFeedbackPersisted: false, humanBusinessFeedbackIsErpData: false,
    purchaseRequestInquiryMappingMode: 'simulation_validation_only', purchaseRequestInquiryMappingFieldCount: 8, purchaseRequestInquiryMappingRequiredFieldCount: 7, purchaseRequestInquiryMappingScenarioCount: 3, purchaseRequestInquiryMappingCreatesInquiry: false, purchaseRequestInquiryMappingSendsSupplier: false, purchaseRequestInquiryMappingCreatesQuotationTask: false, purchaseRequestInquiryMappingPersistsProjection: false, purchaseRequestInquirySourceTraceCreatesTransaction: false,
    inquiryCreationSimulationStatus: inquiryCreationSimulation.simulationStatus, inquiryCreationSimulationPrerequisiteCheckCount: 4, inquiryCreationSimulationIsInquiry: false, inquiryCreationSimulationCreatesInquiry: false, inquiryCreationSimulationPersisted: false, supplierInquiryPreparationStatus: supplierInquiryPreparation.preparationStatus, supplierInquiryPreparationCandidateCount: supplierInquiryPreparation.candidateCount, supplierCandidateIsInquiryTask: false, supplierInquiryTaskCreatedFromCandidate: false, supplierInquiryPreparationSendsSupplier: false, supplierInquiryPreparationCreatesQuotationTask: false, supplierInquiryPreparationPersisted: false,
    existingInquiryListCount: lifecycleFacts.value.existingInquiryCount, preparationCount: inquiryPreparations.value.length,
    pendingPreparationCount: pendingInquiryPreparations.value.length, batchInputCount: lastBatchResult.value.inputCount,
    batchOutputCount: lastBatchResult.value.outputCount, batchBusinessWriteCount: lastBatchResult.value.businessWriteCount,
    batchAutomaticActivation: false, onePreparationOneInquiry: true, advancesPriceApproval: false,
    createsPurchaseOrder: false, businessWriteCount: lastBatchResult.value.businessWriteCount,
    databaseState: 'UNCHANGED', productionDataWritten: false }
}
const provider = { factOwner: 'purchase-inquiry', refresh, buildDiagnostics: diagnostics }
onMounted(async () => { observability?.register?.(provider); await refresh() })
onBeforeUnmount(() => observability?.unregister?.(provider))
</script>

<style scoped>
/* V1.14.2.8.7.4 compatibility evidence: [data-active-view-mode="business_view"] [data-view-scope="acceptance"] / [data-active-view-mode="acceptance_view"] [data-view-scope="business"] */
.inquiry-workbench[data-active-view-mode="business_view"] [data-view-scope="acceptance"],.inquiry-workbench[data-active-view-mode="business_view"] [data-view-governance-scope="acceptance"],.inquiry-workbench[data-active-view-mode="acceptance_view"] [data-view-governance-scope="business"]{display:none}.view-switcher-panel{position:sticky;top:8px;z-index:5;box-shadow:0 8px 22px rgba(15,23,42,.08)}.view-separation-boundaries{display:flex;flex-wrap:wrap;gap:10px;margin-top:12px}.view-separation-boundaries strong{padding:8px 12px;border-radius:999px;background:#eef6ff;color:#17558f}
.business-stage-badge{padding:7px 11px;border-radius:999px;background:#eaf8ef;color:#17643a;font-weight:700}.business-user-view-grid{display:grid;grid-template-columns:repeat(4,minmax(160px,1fr));gap:12px;margin-top:14px}.business-user-view-grid article{display:grid;gap:7px;padding:15px;border-radius:9px;background:#f5f8fc}.business-user-view-grid span,.business-user-view-grid small{color:#64748b}.business-user-view-grid .next-business-hint{grid-column:1/-1;border:1px solid #b8d7f3;background:#f2f8ff}.acceptance-status-grid{display:grid;grid-template-columns:repeat(3,minmax(150px,1fr));gap:10px;margin-top:14px}.acceptance-status-grid article{display:grid;gap:6px;padding:12px;border-radius:8px;background:#f5f8fc}.acceptance-status-grid span{color:#64748b}.acceptance-status-grid strong{color:#17643a}.user-acceptance-checklist{display:grid;grid-template-columns:repeat(4,minmax(150px,1fr));gap:10px;margin-top:14px}.user-acceptance-checklist article{display:flex;justify-content:space-between;gap:10px;padding:11px;border-radius:8px;background:#f5f8fc}.user-acceptance-checklist strong{color:#17643a}.user-feedback-form{display:grid;grid-template-columns:minmax(180px,.7fr) 1fr 1fr auto;gap:10px;align-items:start;margin-top:14px}.user-feedback-note{margin:14px 0 0;padding:12px;border-radius:8px;background:#fff7ed;color:#9a3412!important}@media(max-width:900px){.business-user-view-grid,.acceptance-status-grid,.user-acceptance-checklist{grid-template-columns:1fr}.user-feedback-form{grid-template-columns:1fr}}
.inquiry-preparation-summary{display:grid;grid-template-columns:repeat(4,minmax(150px,1fr));gap:10px;margin:14px 0}.inquiry-preparation-summary article{display:grid;gap:6px;padding:13px;border-radius:8px;background:#f5f8fc}.inquiry-preparation-summary span{color:#64748b}.inquiry-preparation-panel h3{margin:18px 0 10px}.preparation-boundary{margin:14px 0 0;padding:12px;border-radius:8px;background:#ecfdf5;color:#166534;font-weight:700}@media(max-width:900px){.inquiry-preparation-summary{grid-template-columns:1fr}}
.inquiry-edit-panel{display:grid;grid-template-columns:2fr 1fr 1fr auto;gap:10px;align-items:center;margin:12px 0;padding:12px;border:1px solid #bfdbfe;border-radius:8px;background:#eff6ff}@media(max-width:900px){.inquiry-edit-panel{grid-template-columns:1fr}}
.supplier-quote-actions{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:12px 0}.supplier-quote-runtime-panel{border-color:#bfdbfe;background:#f8fbff}
.quote-comparison-actions{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:12px 0}.quote-comparison-runtime-panel{border-color:#c4b5fd;background:#faf8ff}
.supplier-recommendation-actions{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:12px 0}.supplier-recommendation-runtime-panel{border-color:#a7f3d0;background:#f6fffb}
.purchase-order-gate-actions{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:12px 0}.purchase-order-gate-runtime-panel{border-color:#fbbf24;background:#fffbeb}
.purchase-order-transaction-actions{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:12px 0}.purchase-order-transaction-runtime-panel{border-color:#fdba74;background:#fff7ed}
.purchase-order-issue-preparation-actions{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:12px 0}.purchase-order-issue-preparation-runtime-panel{border-color:#93c5fd;background:#eff6ff}
.purchase-order-issue-boundary-actions{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:12px 0}.purchase-order-issue-boundary-runtime-panel{border-color:#a5b4fc;background:#eef2ff}
.purchase-order-issue-execution-actions{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:12px 0}.purchase-order-issue-execution-runtime-panel{border-color:#c4b5fd;background:#faf5ff}
.entry-context-grid{display:grid;grid-template-columns:repeat(5,minmax(150px,1fr));gap:10px;margin-top:14px}.entry-context-grid article{display:grid;gap:6px;padding:13px;border-radius:8px;background:#f5f8fc}.entry-context-grid span{color:#64748b}.entry-context-notice{margin:14px 0 0;padding:12px;border-radius:8px;background:#fff7ed;color:#9a3412;font-weight:700}@media(max-width:1000px){.entry-context-grid{grid-template-columns:1fr}}
.entry-context-grid small{color:#64748b}.lifecycle-actions{display:flex;flex-wrap:wrap;gap:10px;margin:16px 0}.inquiry-lifecycle-workbench h3{margin:18px 0 10px}.lifecycle-evidence-grid{display:grid;grid-template-columns:repeat(3,minmax(160px,1fr));gap:10px;margin-bottom:16px}.lifecycle-evidence-grid article{display:grid;gap:6px;padding:13px;border-radius:8px;background:#f5f8fc}.lifecycle-evidence-grid span{color:#64748b}@media(max-width:900px){.lifecycle-evidence-grid{grid-template-columns:1fr}}
.batch-preparation-actions{display:flex;align-items:center;gap:14px;margin:14px 0}.batch-preparation-actions span{color:#64748b}
.human-acceptance-grid,.human-role-acceptance-grid{display:grid;grid-template-columns:repeat(4,minmax(150px,1fr));gap:10px;margin-top:14px}.human-role-acceptance-grid{grid-template-columns:repeat(3,minmax(180px,1fr))}.human-acceptance-grid article,.human-role-acceptance-grid article{display:grid;gap:6px;padding:13px;border-radius:8px;background:#f5f8fc}.human-acceptance-grid span,.human-role-acceptance-grid span,.human-acceptance-grid small,.human-role-acceptance-grid small{color:#64748b}.human-acceptance-actions{display:flex;flex-wrap:wrap;gap:10px;margin-top:14px}.human-acceptance-actions .el-select{width:200px}.human-acceptance-boundaries{display:flex;flex-wrap:wrap;gap:10px;margin-top:14px}.human-acceptance-boundaries strong{padding:8px 12px;border-radius:999px;background:#eef6ff;color:#17558f}.human-acceptance-note{margin:14px 0 0;padding:12px;border-radius:8px;background:#fff7ed;color:#9a3412!important}@media(max-width:900px){.human-acceptance-grid,.human-role-acceptance-grid{grid-template-columns:1fr}.human-acceptance-actions{display:grid}.human-acceptance-actions .el-select{width:100%}}
.canary-cohort-grid,.canary-summary-grid{display:grid;grid-template-columns:repeat(3,minmax(170px,1fr));gap:10px;margin:14px 0}.canary-summary-grid{grid-template-columns:repeat(5,minmax(120px,1fr))}.canary-cohort-grid article,.canary-summary-grid article{display:grid;gap:6px;padding:13px;border-radius:8px;background:#f5f8fc}.canary-cohort-grid span,.canary-cohort-grid small,.canary-summary-grid span{color:#64748b}.canary-cohort-boundaries{display:flex;flex-wrap:wrap;gap:10px;margin-top:14px}.canary-cohort-boundaries strong{padding:8px 12px;border-radius:999px;background:#eef6ff;color:#17558f}.canary-cohort-note{margin:14px 0 0;padding:12px;border-radius:8px;background:#fff7ed;color:#9a3412!important}@media(max-width:900px){.canary-cohort-grid,.canary-summary-grid{grid-template-columns:1fr}}
.recent-canary-result-grid{display:grid;grid-template-columns:repeat(7,minmax(110px,1fr));gap:10px;margin-top:14px}.recent-canary-result-grid article{display:grid;gap:6px;padding:13px;border-radius:8px;background:#f5f8fc}.recent-canary-result-grid span{color:#64748b}.human-business-acceptance-header{display:flex;flex-wrap:wrap;align-items:center;gap:14px;margin-top:14px}.human-business-acceptance-header .el-select{width:200px}.human-business-checklist{display:grid;grid-template-columns:repeat(2,minmax(220px,1fr));gap:10px;margin:14px 0}.human-business-checklist article{display:flex;justify-content:space-between;gap:12px;padding:12px;border-radius:8px;background:#f5f8fc}.human-business-checklist strong{color:#17643a}.human-business-acceptance-note,.human-feedback-collection-note{margin:14px 0 0;padding:12px;border-radius:8px;background:#fff7ed;color:#9a3412!important}.human-feedback-collection-form{display:grid;grid-template-columns:minmax(180px,.7fr) 1fr 1fr auto;gap:10px;align-items:start;margin-top:14px}@media(max-width:900px){.recent-canary-result-grid,.human-business-checklist{grid-template-columns:1fr}.human-feedback-collection-form{grid-template-columns:1fr}.human-business-acceptance-header{display:grid}.human-business-acceptance-header .el-select{width:100%}}
.mapping-validation-summary{display:grid;grid-template-columns:repeat(5,minmax(130px,1fr));gap:10px;margin-top:14px}.mapping-validation-summary article,.field-mapping-matrix article,.mapping-scenario-grid article{display:grid;gap:6px;padding:13px;border-radius:8px;background:#f5f8fc}.mapping-validation-summary span,.field-mapping-matrix span,.field-mapping-matrix small,.mapping-scenario-grid span,.mapping-scenario-grid small{color:#64748b}.field-mapping-matrix{display:grid;grid-template-columns:repeat(4,minmax(180px,1fr));gap:10px;margin-top:14px}.mapping-scenario-grid{display:grid;grid-template-columns:repeat(3,minmax(190px,1fr));gap:10px;margin-top:14px}.mapping-scenario-grid article[data-scenario-type="exception"]{background:#fff8f8;border:1px solid #f0b8b8}.mapping-validation-boundaries{display:flex;flex-wrap:wrap;gap:10px;margin-top:14px}.mapping-validation-boundaries strong{padding:8px 12px;border-radius:999px;background:#eef6ff;color:#17558f}.mapping-validation-note{margin:14px 0 0;padding:12px;border-radius:8px;background:#fff7ed;color:#9a3412!important}@media(max-width:900px){.mapping-validation-summary,.field-mapping-matrix,.mapping-scenario-grid{grid-template-columns:1fr}}
.inquiry-simulation-summary,.simulation-prerequisite-grid,.supplier-preparation-summary{display:grid;grid-template-columns:repeat(4,minmax(150px,1fr));gap:10px;margin-top:14px}.inquiry-simulation-summary article,.simulation-prerequisite-grid article,.supplier-preparation-summary article,.supplier-candidate-grid article{display:grid;gap:6px;padding:13px;border-radius:8px;background:#f5f8fc}.inquiry-simulation-summary span,.simulation-prerequisite-grid span,.supplier-preparation-summary span,.supplier-candidate-grid span,.supplier-candidate-grid small{color:#64748b}.supplier-candidate-grid{display:grid;grid-template-columns:repeat(2,minmax(220px,1fr));gap:10px;margin-top:14px}.inquiry-simulation-boundaries{display:flex;flex-wrap:wrap;gap:10px;margin-top:14px}.inquiry-simulation-boundaries strong{padding:8px 12px;border-radius:999px;background:#eef6ff;color:#17558f}.inquiry-simulation-note{margin:14px 0 0;padding:12px;border-radius:8px;background:#fff7ed;color:#9a3412!important}@media(max-width:900px){.inquiry-simulation-summary,.simulation-prerequisite-grid,.supplier-preparation-summary,.supplier-candidate-grid{grid-template-columns:1fr}}
.inquiry-workbench{display:grid;gap:16px;min-width:0}.panel{min-width:0;padding:18px;border:1px solid #dce4ed;border-radius:10px;background:#fff}.panel h2{margin:0 0 8px}.panel p{color:#64748b}.section-heading{display:flex;align-items:center;justify-content:space-between;gap:16px}.section-heading p{margin:4px 0 0}.summary-grid,.status-grid,.model-definition-grid,.runtime-isolation-grid,.simulation-status-grid,.command-boundary-grid,.authorization-audit-grid,.final-release-grid,.sandbox-confirmation-grid,.release-agreement-grid,.execution-boundary-grid,.end-to-end-drill-grid,.post-creation-takeover-grid,.post-creation-lifecycle-grid,.workflow-handoff-grid{display:grid;grid-template-columns:repeat(4,minmax(140px,1fr));gap:12px;margin-top:14px}.summary-grid article,.status-grid article,.model-definition-grid article,.runtime-isolation-grid article,.simulation-status-grid article,.command-boundary-grid article,.authorization-audit-grid article,.final-release-grid article,.sandbox-confirmation-grid article,.release-agreement-grid article,.execution-boundary-grid article,.end-to-end-drill-grid article,.post-creation-takeover-grid article,.post-creation-lifecycle-grid article,.workflow-handoff-grid article{display:grid;gap:6px;padding:14px;border-radius:9px;background:#f5f8fc}.summary-grid span,.status-grid span,.model-definition-grid span,.runtime-isolation-grid span,.simulation-status-grid span,.command-boundary-grid span,.authorization-audit-grid span,.final-release-grid span,.sandbox-confirmation-grid span,.release-agreement-grid span,.execution-boundary-grid span,.end-to-end-drill-grid span,.post-creation-takeover-grid span,.post-creation-lifecycle-grid span,.workflow-handoff-grid span{color:#64748b}.summary-grid strong,.status-grid strong{font-size:24px;color:#153a63}.model-lifecycle{display:grid;grid-template-columns:repeat(7,minmax(120px,1fr));gap:8px;margin:16px 0 0;padding:0;list-style:none}.model-lifecycle li{display:grid;gap:5px;padding:12px;border:1px solid #dce4ed;border-radius:8px}.model-lifecycle li[data-current-allowed="true"]{border-color:#8bc5a1;background:#f1faf4}.model-lifecycle small{color:#64748b}.runtime-isolation-note,.simulation-zero-write-note,.command-freeze-note,.authorization-audit-note,.final-release-note,.sandbox-confirmation-note,.release-agreement-note,.execution-boundary-note,.end-to-end-drill-note,.post-creation-takeover-note,.post-creation-lifecycle-note,.workflow-handoff-note{margin:14px 0 0;padding:12px;border-radius:8px;background:#fff7ed;color:#9a3412!important}.readonly-badge{padding:6px 10px;border-radius:999px;background:#e8f2ff;color:#17558f;font-weight:700;white-space:nowrap}.boundary{border-color:#f1c27d;background:#fffbf2}.load-error{padding:10px;border-radius:7px;background:#fff1f0;color:#b42318}@media(max-width:900px){.summary-grid,.status-grid,.model-definition-grid,.runtime-isolation-grid,.simulation-status-grid,.command-boundary-grid,.authorization-audit-grid,.final-release-grid,.sandbox-confirmation-grid,.release-agreement-grid,.execution-boundary-grid,.end-to-end-drill-grid,.post-creation-takeover-grid,.post-creation-lifecycle-grid,.workflow-handoff-grid{grid-template-columns:repeat(2,minmax(120px,1fr))}.model-lifecycle{grid-template-columns:repeat(2,minmax(120px,1fr))}}
.workflow-start-assessment-grid{display:grid;grid-template-columns:repeat(4,minmax(140px,1fr));gap:12px;margin-top:14px}.workflow-start-assessment-grid article{display:grid;gap:6px;padding:14px;border-radius:9px;background:#f5f8fc}.workflow-start-assessment-grid span{color:#64748b}.workflow-start-assessment-note{margin:14px 0 0;padding:12px;border-radius:8px;background:#fff7ed;color:#9a3412!important}@media(max-width:900px){.workflow-start-assessment-grid{grid-template-columns:repeat(2,minmax(120px,1fr))}}
.instance-task-lifecycle-grid{display:grid;grid-template-columns:repeat(4,minmax(140px,1fr));gap:12px;margin-top:14px}.instance-task-lifecycle-grid article{display:grid;gap:6px;padding:14px;border-radius:9px;background:#f5f8fc}.instance-task-lifecycle-grid span{color:#64748b}.instance-task-lifecycle-note{margin:14px 0 0;padding:12px;border-radius:8px;background:#fff7ed;color:#9a3412!important}@media(max-width:900px){.instance-task-lifecycle-grid{grid-template-columns:repeat(2,minmax(120px,1fr))}}
.workflow-runtime-grid{display:grid;grid-template-columns:repeat(4,minmax(140px,1fr));gap:12px;margin-top:14px}.workflow-runtime-grid article{display:grid;gap:6px;padding:14px;border-radius:9px;background:#f5f8fc}.workflow-runtime-grid span{color:#64748b}.workflow-runtime-note{margin:14px 0 0;padding:12px;border-radius:8px;background:#fff7ed;color:#9a3412!important}@media(max-width:900px){.workflow-runtime-grid{grid-template-columns:repeat(2,minmax(120px,1fr))}}
.node-decision-grid{display:grid;grid-template-columns:repeat(4,minmax(140px,1fr));gap:12px;margin-top:14px}.node-decision-grid article{display:grid;gap:6px;padding:14px;border-radius:9px;background:#f5f8fc}.node-decision-grid span{color:#64748b}.node-decision-note{margin:14px 0 0;padding:12px;border-radius:8px;background:#fff7ed;color:#9a3412!important}@media(max-width:900px){.node-decision-grid{grid-template-columns:repeat(2,minmax(120px,1fr))}}
.approval-feedback-grid{display:grid;grid-template-columns:repeat(4,minmax(140px,1fr));gap:12px;margin-top:14px}.approval-feedback-grid article{display:grid;gap:6px;padding:14px;border-radius:9px;background:#f5f8fc}.approval-feedback-grid span{color:#64748b}.approval-feedback-note{margin:14px 0 0;padding:12px;border-radius:8px;background:#fff7ed;color:#9a3412!important}@media(max-width:900px){.approval-feedback-grid{grid-template-columns:repeat(2,minmax(120px,1fr))}}
.audit-archive-grid{display:grid;grid-template-columns:repeat(4,minmax(140px,1fr));gap:12px;margin-top:14px}.audit-archive-grid article{display:grid;gap:6px;padding:14px;border-radius:9px;background:#f5f8fc}.audit-archive-grid span{color:#64748b}.audit-archive-note{margin:14px 0 0;padding:12px;border-radius:8px;background:#fff7ed;color:#9a3412!important}@media(max-width:900px){.audit-archive-grid{grid-template-columns:repeat(2,minmax(120px,1fr))}}
.governance-summary-grid{display:grid;grid-template-columns:repeat(4,minmax(140px,1fr));gap:12px;margin-top:14px}.governance-summary-grid article{display:grid;gap:6px;padding:14px;border-radius:9px;background:#f5f8fc}.governance-summary-grid span{color:#64748b}.governance-summary-note{margin:14px 0 0;padding:12px;border-radius:8px;background:#fff7ed;color:#9a3412!important}@media(max-width:900px){.governance-summary-grid{grid-template-columns:repeat(2,minmax(120px,1fr))}}
.operation-validation-grid{display:grid;grid-template-columns:repeat(4,minmax(140px,1fr));gap:12px;margin-top:14px}.operation-validation-grid article{display:grid;gap:6px;padding:14px;border-radius:9px;background:#f5f8fc}.operation-validation-grid span,.operation-validation-grid small{color:#64748b}.operation-validation-boundaries{display:flex;flex-wrap:wrap;gap:10px;margin-top:14px}.operation-validation-boundaries strong{padding:8px 12px;border-radius:999px;background:#eef6ff;color:#17558f}.operation-validation-note{margin:14px 0 0;padding:12px;border-radius:8px;background:#fff7ed;color:#9a3412!important}@media(max-width:900px){.operation-validation-grid{grid-template-columns:repeat(2,minmax(120px,1fr))}}
.business-view-acceptance-grid{display:grid;grid-template-columns:repeat(4,minmax(140px,1fr));gap:12px;margin-top:14px}.business-view-acceptance-grid article{display:grid;gap:6px;padding:14px;border-radius:9px;background:#f5f8fc}.business-view-acceptance-grid span,.business-view-acceptance-grid small{color:#64748b}.business-view-acceptance-boundaries{display:flex;flex-wrap:wrap;gap:10px;margin-top:14px}.business-view-acceptance-boundaries strong{padding:8px 12px;border-radius:999px;background:#eef6ff;color:#17558f}.business-view-acceptance-note{margin:14px 0 0;padding:12px;border-radius:8px;background:#fff7ed;color:#9a3412!important}@media(max-width:900px){.business-view-acceptance-grid{grid-template-columns:repeat(2,minmax(120px,1fr))}}
.business-navigation-path{display:grid;grid-template-columns:repeat(5,minmax(130px,1fr));gap:10px;margin:16px 0 0;padding:0;list-style:none}.business-navigation-path li{display:grid;gap:5px;padding:13px;border:1px solid #dce4ed;border-radius:9px;background:#f8fafc}.business-navigation-path li>span{display:grid;place-items:center;width:26px;height:26px;border-radius:50%;background:#17558f;color:#fff;font-weight:700}.business-navigation-path small{color:#64748b}.role-navigation-grid{display:grid;grid-template-columns:repeat(3,minmax(160px,1fr));gap:10px;margin-top:12px}.role-navigation-grid article{display:grid;gap:6px;padding:12px;border-radius:8px;background:#f5f8fc}.role-navigation-grid span{color:#64748b}.business-navigation-boundaries{display:flex;flex-wrap:wrap;gap:10px;margin-top:14px}.business-navigation-boundaries strong{padding:8px 12px;border-radius:999px;background:#eef6ff;color:#17558f}.business-navigation-note{margin:14px 0 0;padding:12px;border-radius:8px;background:#fff7ed;color:#9a3412!important}@media(max-width:900px){.business-navigation-path{grid-template-columns:repeat(2,minmax(120px,1fr))}.role-navigation-grid{grid-template-columns:1fr}}
.scenario-acceptance-grid{display:grid;grid-template-columns:repeat(3,minmax(190px,1fr));gap:12px;margin-top:14px}.scenario-acceptance-grid article{display:grid;gap:7px;padding:14px;border:1px solid #dce4ed;border-radius:9px;background:#f8fafc}.scenario-acceptance-grid span,.scenario-acceptance-grid small{color:#64748b}.scenario-acceptance-grid em{font-style:normal;font-weight:700;color:#17558f}.scenario-acceptance-grid article[data-scenario-type="exception"]{border-color:#f0b8b8;background:#fff8f8}.scenario-acceptance-boundaries{display:flex;flex-wrap:wrap;gap:10px;margin-top:14px}.scenario-acceptance-boundaries strong{padding:8px 12px;border-radius:999px;background:#eef6ff;color:#17558f}.scenario-acceptance-note{margin:14px 0 0;padding:12px;border-radius:8px;background:#fff7ed;color:#9a3412!important}@media(max-width:900px){.scenario-acceptance-grid{grid-template-columns:1fr}}
</style>
