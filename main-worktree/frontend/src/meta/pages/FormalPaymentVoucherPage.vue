<template>
  <main class="formal-payment-voucher-page">
    <header class="page-header">
      <section>
        <p class="eyebrow">V1.13.6.1 正式付款凭证页面原型</p>
        <h1>{{ detail ? '正式付款凭证明细' : '正式付款凭证' }}</h1>
        <p>本页只生成正式付款凭证对象，不执行过账，不写总账，不做付款核销，不生成银行流水。</p>
        <p class="finance-current-module-badge">当前操作模块：正式付款凭证</p>
      </section>
      <nav class="page-tabs finance-flow-nav" aria-label="财务前置流程导航">
        <span class="finance-nav-title">财务前置流程导航</span>
        <router-link class="finance-nav-button" to="/finance/payable-prepares">应付预备</router-link>
        <router-link class="finance-nav-button" to="/finance/payable-checks">应付核对</router-link>
        <router-link class="finance-nav-button" to="/finance/invoice-prepares">发票预备</router-link>
        <router-link class="finance-nav-button" to="/finance/ap-drafts">应付账款草稿</router-link>
        <router-link class="finance-nav-button" to="/finance/payment-drafts">供应商付款草稿</router-link>
        <router-link class="finance-nav-button" to="/finance/payment-prepares">正式付款单预备</router-link>
        <router-link class="finance-nav-button" to="/finance/payment-order-drafts">正式付款单草稿</router-link>
        <router-link class="finance-nav-button" to="/finance/payment-risk-reviews">真实付款风险评审</router-link>
        <router-link class="finance-nav-button" to="/finance/payment-executions">付款执行草稿</router-link>
        <router-link class="finance-nav-button" to="/finance/payment-record-reviews">付款记录复核</router-link>
        <router-link class="finance-nav-button" to="/finance/payment-voucher-drafts">付款凭证草稿</router-link>
        <router-link class="finance-nav-button" to="/finance/payment-voucher-reviews">付款凭证复核</router-link>
        <router-link class="finance-nav-button finance-nav-button-active" to="/finance/formal-payment-vouchers">正式付款凭证<span class="finance-current-tag">当前</span></router-link>
      </nav>
    </header>

    <el-alert v-if="message" :title="message" :type="messageType" show-icon :closable="false" />

    <section v-if="detail" class="operation-shell">
      <section class="plain-flow-guide">
        <strong>正式付款凭证流程：付款凭证复核通过 -> 生成正式付款凭证对象 -> 后续过账前评审</strong>
        <div class="plain-flow-grid">
          <span><b>当前步骤</b>查看正式付款凭证对象。</span>
          <span><b>本页做什么</b>展示来源链、借贷分录、风险检查和操作日志。</span>
          <span><b>下一步做什么</b>后续进入过账前评审，本轮只保留入口提示。</span>
          <span><b>本页不做什么</b>不过账、不写总账、不核销、不生成银行流水。</span>
        </div>
      </section>

      <el-card shadow="never">
        <template #header>
          <div class="card-header">
            <div>
              <h2>{{ detail.formalVoucherNo }}</h2>
              <span>{{ detail.sourceVoucherReviewNo || '-' }} / {{ detail.supplierName || '-' }}</span>
            </div>
            <div class="button-row">
              <el-button @click="router.push('/finance/formal-payment-vouchers')">返回列表</el-button>
              <el-button @click="router.push(`/finance/payment-voucher-review/${detail.sourceVoucherReviewId}`)">查看来源付款凭证复核</el-button>
              <el-button v-if="detail.formalVoucherStatus === 'generated'" type="danger" @click="handleCancel(detail)">取消正式凭证</el-button>
              <el-button v-if="detail.formalVoucherStatus === 'generated'" disabled :title="postingPreReviewButtonTitle(detail)">{{ postingPreReviewButtonText(detail) }}</el-button>
              <el-button v-if="detail.formalVoucherStatus === 'generated'" type="warning" :disabled="!canSimulatePosting(detail)" :title="simulatePostingButtonTitle(detail)" @click="handleSimulatePosting(detail)">模拟过账</el-button>
              <el-button v-if="detail.formalVoucherStatus === 'generated'" type="primary" :disabled="!canEnterFormalPosting(detail)" :title="formalPostingEntryTitle(detail)" @click="handleFormalPostingEntrance(detail)">{{ formalPostingEntryButtonText(detail) }}</el-button>
              <el-button v-if="detail.formalVoucherStatus === 'generated'" type="info" :title="formalPostingPreExecuteTitle(detail)" @click="handleFormalPostingPreExecuteCheck(detail)">预执行检查</el-button>
              <el-button v-if="detail.formalVoucherStatus === 'generated'" type="info" :title="formalPostingLockTitle(detail)" @click="handleFormalPostingLockCheck(detail)">锁定预检查</el-button>
              <el-button v-if="detail.formalVoucherStatus === 'generated'" type="info" :title="formalPostingConfirmTitle(detail)" @click="handleFormalPostingConfirmCheck(detail)">最终确认检查</el-button>
              <el-button type="info" plain @click="copyCurrentVoucherDiagnostic(detail)">复制当前凭证诊断数据</el-button>
              <el-button v-if="detail.formalVoucherStatus === 'generated'" type="info" :title="formalPostingFlowTitle(detail)" @click="handleFormalPostingFlowCheck(detail)">状态机预检查</el-button>
            </div>
          </div>
        </template>
        <div class="boundary-note">当前状态：{{ formalStatusLabel(detail.formalVoucherStatus) }}。正式付款凭证对象仍未过账、未写总账、未核销。</div>
        <div class="app-terminal-step-tip app-step-guide">
          <strong>当前阶段边界：正式凭证对象已形成</strong>
          <span>后续需要单独进入过账前评审；本页不会直接过账、写总账或完成付款核销。</span>
        </div>
        <div class="info-grid">
          <article v-for="item in detailFields" :key="item.label">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </article>
        </div>
      </el-card>

      <el-card shadow="never">
        <template #header><h2>模拟P2P完整业务场景验证设计</h2></template>
        <div class="boundary-note">当前设计状态：模拟 P2P 完整业务链验证模型已建立。本轮只展示采购到付款的模拟链路，不生成真实采购、库存、应付、总账或银行流水数据。</div>
        <div class="posting-review-summary">
          <article>
            <span>场景验证状态</span>
            <strong><el-tag :type="simulationP2PValidationType(simulationP2PScenarioSummary(detail).simulationP2PValidationStatus)">{{ simulationP2PScenarioSummary(detail).simulationP2PValidationStatusText }}</el-tag></strong>
          </article>
          <article>
            <span>是否具备完整链</span>
            <strong>{{ simulationP2PScenarioSummary(detail).simulationP2PValidationReady ? '是，仅表示模拟链完整' : '否，仍有阻断条件' }}</strong>
          </article>
          <article>
            <span>链路阶段数</span>
            <strong>{{ Object.keys(simulationP2PScenarioSummary(detail).simulationP2PFlow).length }}</strong>
          </article>
          <article>
            <span>模拟付款金额</span>
            <strong>{{ simulationP2PScenarioSummary(detail).simulationP2PFlow.payment.paymentAmount }}</strong>
          </article>
        </div>
        <div class="posting-actions">
          <el-button type="primary" plain @click="handleSimulationP2PScenarioCheck(detail)">检查模拟P2P业务链</el-button>
        </div>
        <div class="posting-condition-grid">
          <section>
            <h3>请购</h3>
            <ul>
              <li>requestId：{{ simulationP2PScenarioSummary(detail).simulationP2PFlow.request.requestId }}</li>
              <li>requestStatus：{{ simulationP2PScenarioSummary(detail).simulationP2PFlow.request.requestStatus }}</li>
              <li>requestAmount：{{ simulationP2PScenarioSummary(detail).simulationP2PFlow.request.requestAmount }}</li>
            </ul>
          </section>
          <section>
            <h3>采购订单</h3>
            <ul>
              <li>purchaseOrderNo：{{ simulationP2PScenarioSummary(detail).simulationP2PFlow.purchaseOrder.purchaseOrderNo }}</li>
              <li>supplierId：{{ simulationP2PScenarioSummary(detail).simulationP2PFlow.purchaseOrder.supplierId }}</li>
              <li>orderAmount：{{ simulationP2PScenarioSummary(detail).simulationP2PFlow.purchaseOrder.orderAmount }}</li>
            </ul>
          </section>
          <section>
            <h3>收货</h3>
            <ul>
              <li>receiptNo：{{ simulationP2PScenarioSummary(detail).simulationP2PFlow.receipt.receiptNo }}</li>
              <li>receivedQuantity：{{ simulationP2PScenarioSummary(detail).simulationP2PFlow.receipt.receivedQuantity }}</li>
              <li>receivedAmount：{{ simulationP2PScenarioSummary(detail).simulationP2PFlow.receipt.receivedAmount }}</li>
            </ul>
          </section>
          <section>
            <h3>入库</h3>
            <ul>
              <li>warehouseId：{{ simulationP2PScenarioSummary(detail).simulationP2PFlow.inventory.warehouseId }}</li>
              <li>inventoryAmount：{{ simulationP2PScenarioSummary(detail).simulationP2PFlow.inventory.inventoryAmount }}</li>
            </ul>
          </section>
          <section>
            <h3>应付</h3>
            <ul>
              <li>payableAmount：{{ simulationP2PScenarioSummary(detail).simulationP2PFlow.payable.payableAmount }}</li>
              <li>supplierBalanceImpact：{{ simulationP2PScenarioSummary(detail).simulationP2PFlow.payable.supplierBalanceImpact }}</li>
            </ul>
          </section>
          <section>
            <h3>付款</h3>
            <ul>
              <li>paymentVoucherNo：{{ simulationP2PScenarioSummary(detail).simulationP2PFlow.payment.paymentVoucherNo }}</li>
              <li>paymentAmount：{{ simulationP2PScenarioSummary(detail).simulationP2PFlow.payment.paymentAmount }}</li>
            </ul>
          </section>
          <section>
            <h3>模拟总账</h3>
            <ul>
              <li>simulationLedgerEntries：{{ simulationP2PScenarioSummary(detail).simulationP2PFlow.ledger.simulationLedgerEntries.length }}</li>
              <li>simulationDebitTotal：{{ simulationP2PScenarioSummary(detail).simulationP2PFlow.ledger.simulationDebitTotal }}</li>
              <li>simulationCreditTotal：{{ simulationP2PScenarioSummary(detail).simulationP2PFlow.ledger.simulationCreditTotal }}</li>
            </ul>
          </section>
          <section>
            <h3>模拟报表影响</h3>
            <ul>
              <li v-for="impact in simulationP2PScenarioSummary(detail).simulationP2PFlow.reportImpact" :key="impact.report">{{ impact.report }}：{{ impact.impact }}。</li>
            </ul>
          </section>
        </div>
      </el-card>

      <el-card shadow="never">
        <template #header><h2>多供应商P2P链诊断设计</h2></template>
        <div class="boundary-note">本区只诊断多供应商采购订单在模拟链中的继承与拆分情况，不生成真实应付、真实付款、总账或银行流水。</div>
        <div class="posting-review-summary">
          <article>
            <span>采购订单供应商数量</span>
            <strong>{{ multiSupplierP2PSummary(detail).purchaseOrderSupplierCount }}</strong>
          </article>
          <article>
            <span>模拟应付供应商数量</span>
            <strong>{{ multiSupplierP2PSummary(detail).payableSupplierMapping.length }}</strong>
          </article>
          <article>
            <span>模拟付款供应商数量</span>
            <strong>{{ multiSupplierP2PSummary(detail).paymentSupplierMapping.length }}</strong>
          </article>
          <article>
            <span>供应商链一致性</span>
            <strong><el-tag :type="supplierChainConsistencyType(multiSupplierP2PSummary(detail).supplierChainConsistencyStatus)">{{ multiSupplierP2PSummary(detail).supplierChainConsistencyStatus }}</el-tag></strong>
          </article>
        </div>
        <div class="posting-condition-grid">
          <section>
            <h3>采购订单供应商</h3>
            <ul>
              <li v-for="item in multiSupplierP2PSummary(detail).purchaseOrderSuppliers" :key="item.supplierKey">
                {{ item.displayName }}：采购金额 {{ item.purchaseAmount }}，收货金额 {{ item.receiptAmount }}，入库金额 {{ item.inventoryAmount }}，应付金额 {{ item.payableAmount }}，付款金额 {{ item.paymentAmount }}
              </li>
              <li v-if="!multiSupplierP2PSummary(detail).purchaseOrderSuppliers.length">未读取到采购订单供应商明细。</li>
            </ul>
          </section>
          <section>
            <h3>收货供应商映射</h3>
            <ul>
              <li v-for="item in multiSupplierP2PSummary(detail).receiptSupplierMapping" :key="item.supplierKey">{{ item.displayName }}：{{ item.amount }}</li>
              <li v-if="!multiSupplierP2PSummary(detail).receiptSupplierMapping.length">未形成收货供应商映射。</li>
            </ul>
          </section>
          <section>
            <h3>入库供应商映射</h3>
            <ul>
              <li v-for="item in multiSupplierP2PSummary(detail).inventorySupplierMapping" :key="item.supplierKey">{{ item.displayName }}：{{ item.amount }}</li>
              <li v-if="!multiSupplierP2PSummary(detail).inventorySupplierMapping.length">未形成入库供应商映射。</li>
            </ul>
          </section>
          <section>
            <h3>应付供应商映射</h3>
            <ul>
              <li v-for="item in multiSupplierP2PSummary(detail).payableSupplierMapping" :key="item.supplierKey">{{ item.displayName }}：{{ item.amount }}</li>
              <li v-if="!multiSupplierP2PSummary(detail).payableSupplierMapping.length">未形成应付供应商映射。</li>
            </ul>
          </section>
          <section>
            <h3>付款供应商映射</h3>
            <ul>
              <li v-for="item in multiSupplierP2PSummary(detail).paymentSupplierMapping" :key="item.supplierKey">{{ item.displayName }}：{{ item.amount }}</li>
              <li v-if="!multiSupplierP2PSummary(detail).paymentSupplierMapping.length">未形成付款供应商映射。</li>
            </ul>
          </section>
          <section>
            <h3>模拟总账供应商来源</h3>
            <ul>
              <li v-for="item in multiSupplierP2PSummary(detail).ledgerSupplierMapping" :key="item.supplierKey">{{ item.displayName }}：{{ item.amount }}；来源 {{ item.source }}</li>
              <li v-if="!multiSupplierP2PSummary(detail).ledgerSupplierMapping.length">未形成模拟总账供应商来源。</li>
            </ul>
          </section>
        </div>
        <div class="boundary-note">{{ multiSupplierP2PSummary(detail).supplierChainConsistencyConclusion }}</div>
        <div class="diagnostic-note warning" v-if="multiSupplierP2PSummary(detail).supplierChainConsistencyWarnings.length">
          <strong>诊断提醒</strong>
          <ul>
            <li v-for="warning in multiSupplierP2PSummary(detail).supplierChainConsistencyWarnings" :key="warning">{{ warning }}</li>
          </ul>
        </div>
      </el-card>

      <el-card shadow="never">
        <template #header><h2>多供应商P2P结算模型设计</h2></template>
        <div class="boundary-note">本区只描述未来多供应商采购订单如何拆分为多个应付对象、付款对象和供应商往来，不修改现有业务数据。</div>
        <div class="posting-review-summary">
          <article>
            <span>结算模式</span>
            <strong>{{ multiSupplierSettlementSummary(detail).multiSupplierSettlementSummary.settlementMode }}</strong>
          </article>
          <article>
            <span>供应商数量</span>
            <strong>{{ multiSupplierSettlementSummary(detail).multiSupplierSettlementSummary.supplierCount }}</strong>
          </article>
          <article>
            <span>模型是否就绪</span>
            <strong>{{ multiSupplierSettlementSummary(detail).multiSupplierSettlementReady ? '是，仅表示设计模型就绪' : '否，仍需补齐拆分来源' }}</strong>
          </article>
          <article>
            <span>模型状态</span>
            <strong><el-tag :type="multiSupplierSettlementType(multiSupplierSettlementSummary(detail).multiSupplierSettlementStatus)">{{ multiSupplierSettlementSummary(detail).multiSupplierSettlementStatusText }}</el-tag></strong>
          </article>
        </div>
        <div class="posting-actions">
          <el-button type="primary" plain @click="handleMultiSupplierSettlementCheck(detail)">检查多供应商结算模型</el-button>
        </div>
        <div class="posting-condition-grid">
          <section>
            <h3>供应商拆分模型</h3>
            <ul>
              <li v-for="line in multiSupplierSettlementSummary(detail).supplierSettlementLines" :key="line.supplierId || line.supplierName">
                {{ line.supplierName || line.supplierId }}：采购 {{ line.purchaseAmount }}，收货 {{ line.receiptAmount }}，入库 {{ line.inventoryAmount }}，应付 {{ line.payableAmount }}，付款 {{ line.paymentAmount }}，模拟总账 {{ line.ledgerAmount }}
              </li>
              <li v-if="!multiSupplierSettlementSummary(detail).supplierSettlementLines.length">当前未形成供应商拆分行。</li>
            </ul>
          </section>
          <section>
            <h3>采购金额拆分</h3>
            <ul>
              <li v-for="item in multiSupplierSettlementSummary(detail).purchaseSupplierMapping" :key="item.supplierId || item.supplierName">
                {{ item.purchaseOrderNo }} / {{ item.supplierName || item.supplierId }}：lineAmount {{ item.lineAmount }}，materialCount {{ item.materialCount }}
              </li>
              <li v-if="!multiSupplierSettlementSummary(detail).purchaseSupplierMapping.length">当前未形成采购供应商映射。</li>
            </ul>
          </section>
          <section>
            <h3>应付金额拆分</h3>
            <ul>
              <li v-for="item in multiSupplierSettlementSummary(detail).supplierPayableMapping" :key="item.supplierId || item.supplierName">
                {{ item.supplierName || item.supplierId }}：{{ item.payableAmount }}，{{ item.payableStatus }}
              </li>
            </ul>
          </section>
          <section>
            <h3>付款金额拆分</h3>
            <ul>
              <li v-for="item in multiSupplierSettlementSummary(detail).supplierPaymentMapping" :key="item.supplierId || item.supplierName">
                {{ item.supplierName || item.supplierId }}：{{ item.paymentAmount }}，凭证 {{ item.paymentVoucherNo }}
              </li>
            </ul>
          </section>
          <section>
            <h3>模拟总账拆分</h3>
            <ul>
              <li v-for="item in multiSupplierSettlementSummary(detail).supplierLedgerMapping" :key="item.supplierId || item.supplierName">
                {{ item.supplierName || item.supplierId }}：借 {{ item.debitAccount }}，贷 {{ item.creditAccount }}，金额 {{ item.amount }}
              </li>
            </ul>
          </section>
          <section>
            <h3>模型提醒</h3>
            <ul>
              <li v-for="warning in multiSupplierSettlementSummary(detail).multiSupplierSettlementWarnings" :key="warning">{{ warning }}</li>
              <li v-if="!multiSupplierSettlementSummary(detail).multiSupplierSettlementWarnings.length">暂无模型提醒。</li>
            </ul>
          </section>
        </div>
        <div class="boundary-note">{{ multiSupplierSettlementSummary(detail).multiSupplierSettlementConclusion }}</div>
      </el-card>

      <el-card shadow="never">
        <template #header><h2>多供应商P2P数据验证模型设计</h2></template>
        <div class="boundary-note">本区只验证采购订单维度和供应商维度的数据一致性，不改变采购订单、WMS、QMS、Finance 或付款状态。</div>
        <div class="posting-review-summary">
          <article>
            <span>采购订单验证数</span>
            <strong>{{ p2pDataValidationSummary(detail).purchaseOrderValidation.length }}</strong>
          </article>
          <article>
            <span>供应商验证数</span>
            <strong>{{ p2pDataValidationSummary(detail).supplierValidation.length }}</strong>
          </article>
          <article>
            <span>数据一致性状态</span>
            <strong><el-tag :type="p2pDataValidationType(p2pDataValidationSummary(detail).p2pDataValidation.validationStatus)">{{ p2pDataValidationSummary(detail).p2pDataValidation.validationStatus }}</el-tag></strong>
          </article>
          <article>
            <span>风险提示数</span>
            <strong>{{ p2pDataValidationSummary(detail).p2pDataValidation.riskWarnings.length }}</strong>
          </article>
        </div>
        <div class="posting-actions">
          <el-button type="primary" plain @click="handleP2PDataValidationCheck(detail)">检查多供应商P2P数据验证</el-button>
        </div>
        <div class="posting-condition-grid">
          <section>
            <h3>采购订单维度</h3>
            <ul>
              <li v-for="item in p2pDataValidationSummary(detail).purchaseOrderValidation" :key="item.poNo">
                {{ item.poNo }}：供应商 {{ item.supplierCount }} 个；采购 {{ item.purchaseAmount }}，收货 {{ item.receiptAmount }}，入库 {{ item.inventoryAmount }}，应付 {{ item.payableAmount }}，付款 {{ item.paymentAmount }}，差异 {{ item.difference }}；状态 {{ item.validationStatus }}
              </li>
              <li v-if="!p2pDataValidationSummary(detail).purchaseOrderValidation.length">当前没有可验证的采购订单维度数据。</li>
            </ul>
          </section>
          <section>
            <h3>供应商维度</h3>
            <ul>
              <li v-for="item in p2pDataValidationSummary(detail).supplierValidation" :key="item.supplierId || item.supplierName">
                {{ item.supplierName || item.supplierId }}：订单 {{ item.orderCount }} 个；采购 {{ item.purchaseTotal }}，收货 {{ item.receiptTotal }}，入库 {{ item.inventoryTotal }}，应付 {{ item.payableTotal }}，付款 {{ item.paymentTotal }}，余额 {{ item.balance }}，差异 {{ item.difference }}；状态 {{ item.validationStatus }}
              </li>
              <li v-if="!p2pDataValidationSummary(detail).supplierValidation.length">当前没有可验证的供应商维度数据。</li>
            </ul>
          </section>
          <section>
            <h3>数据一致性检查</h3>
            <ul>
              <li>{{ p2pDataValidationSummary(detail).p2pDataValidation.conclusion }}</li>
              <li v-for="warning in p2pDataValidationSummary(detail).p2pDataValidation.riskWarnings" :key="warning">{{ warning }}</li>
            </ul>
          </section>
        </div>
      </el-card>

      <el-card shadow="never">
        <template #header><h2>过账前评审结果</h2></template>
        <div class="posting-review-summary">
          <article>
            <span>过账前评审状态</span>
            <strong><el-tag :type="postingPreReviewStatusType(detail.postingPreReviewStatus)">{{ postingPreReviewStatusLabel(detail.postingPreReviewStatus) }}</el-tag></strong>
          </article>
          <article>
            <span>风险项数量</span>
            <strong>{{ detail.postingPreReviewRiskCount || 0 }}</strong>
          </article>
          <article>
            <span>阻断项数量</span>
            <strong>{{ detail.postingPreReviewBlockedCount || 0 }}</strong>
          </article>
          <article>
            <span>提醒项数量</span>
            <strong>{{ detail.postingPreReviewWarningCount || 0 }}</strong>
          </article>
          <article>
            <span>是否允许进入后续过账阶段</span>
            <strong>{{ detail.postingPreReviewCanEnterPosting ? '允许进入后续过账阶段' : '不允许进入后续过账阶段' }}</strong>
          </article>
        </div>
        <div class="boundary-note">{{ detail.postingPreReviewConclusion || '过账前评审结果待生成；本页不会执行真实过账、不会写总账、不会核销。' }}</div>
        <el-table :data="detail.postingPreReviewItems || []" border stripe height="360">
          <el-table-column type="index" label="序号" width="70" fixed="left" />
          <el-table-column prop="itemName" label="评审项" min-width="220" />
          <el-table-column prop="result" label="结果" width="120">
            <template #default="{ row }"><el-tag :type="riskItemType(row.level)">{{ riskItemLabel(row.result) }}</el-tag></template>
          </el-table-column>
          <el-table-column prop="message" label="说明" min-width="420" />
          <el-table-column prop="level" label="级别" width="120" fixed="right">
            <template #default="{ row }">{{ riskItemLabel(row.level) }}</template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-card shadow="never">
        <template #header><h2>凭证过账准备状态</h2></template>
        <div class="posting-review-summary">
          <article>
            <span>凭证过账状态</span>
            <strong><el-tag :type="postingReadinessType(detail.postingReadinessStatus)">{{ postingStatusText(detail) }}</el-tag></strong>
          </article>
          <article>
            <span>是否可过账</span>
            <strong>{{ detail.postingReady ? '可进入凭证过账' : '不可过账' }}</strong>
          </article>
          <article>
            <span>阻断原因数量</span>
            <strong>{{ detail.postingBlockedCount || 0 }}</strong>
          </article>
          <article>
            <span>提醒数量</span>
            <strong>{{ detail.postingWarningCount || 0 }}</strong>
          </article>
          <article>
            <span>模拟过账状态</span>
            <strong><el-tag :type="postingActionStatusType(detail.postingActionStatus)">{{ detail.postingActionStatusText || '未模拟' }}</el-tag></strong>
          </article>
          <article>
            <span>模拟过账时间</span>
            <strong>{{ formatDateTime(detail.postingSimulatedAt) }}</strong>
          </article>
        </div>
        <div class="boundary-note">{{ detail.postingReadinessConclusion || '凭证过账准备结果待生成；本页不会写总账、不会核销、不会生成银行流水。' }}</div>
        <div class="boundary-note">{{ detail.postingActionConclusion || '未执行模拟过账；本页不会写总账、不会核销、不会生成银行流水。' }}</div>
        <div class="posting-condition-grid">
          <section>
            <h3>阻断原因</h3>
            <ul>
              <li v-for="reason in detail.postingBlockedReasons || []" :key="reason">{{ reason }}</li>
              <li v-if="!(detail.postingBlockedReasons || []).length">无阻断原因。</li>
            </ul>
          </section>
          <section>
            <h3>提醒项</h3>
            <ul>
              <li v-for="warning in detail.postingWarnings || []" :key="warning">{{ warning }}</li>
              <li v-if="!(detail.postingWarnings || []).length">无提醒项。</li>
            </ul>
          </section>
        </div>
      </el-card>

      <el-card shadow="never">
        <template #header><h2>正式过账前最终设计评审</h2></template>
        <div class="posting-review-summary">
          <article>
            <span>正式过账评审状态</span>
            <strong><el-tag :type="formalPostingStatusType(detail.formalPostingStatus)">{{ detail.formalPostingStatusText || formalPostingStatusLabel(detail.formalPostingStatus) }}</el-tag></strong>
          </article>
          <article>
            <span>未来是否可正式过账</span>
            <strong>{{ detail.formalPostingReady ? '具备未来正式过账条件' : '不可正式过账' }}</strong>
          </article>
          <article>
            <span>正式过账阻断数量</span>
            <strong>{{ detail.formalPostingBlockedCount || 0 }}</strong>
          </article>
          <article>
            <span>正式过账提醒数量</span>
            <strong>{{ detail.formalPostingWarningCount || 0 }}</strong>
          </article>
        </div>
        <div class="boundary-note">{{ detail.formalPostingReviewConclusion || '正式过账前最终设计评审待生成；本轮不执行正式过账、不写总账、不核销、不生成银行流水。' }}</div>
        <h3 class="diagnostic-title">模拟过账与正式过账评审诊断</h3>
        <div :class="['diagnostic-note', diagnosticStatusClass(detail)]">{{ postingDiagnosticConclusion(detail) }}</div>
        <div class="diagnostic-grid">
          <article v-for="item in postingDiagnosticFields" :key="item.label">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </article>
        </div>
        <section class="formal-posting-entry-box">
          <div class="entry-heading">
            <h3>正式过账入口设计说明</h3>
            <el-tag :type="canEnterFormalPosting(detail) ? 'success' : 'danger'">{{ canEnterFormalPosting(detail) ? '入口可用' : '入口禁用' }}</el-tag>
          </div>
          <p>{{ formalPostingEntryTitle(detail) }}</p>
          <div class="posting-condition-grid">
            <section>
              <h3>权限占位检查</h3>
              <ul>
                <li>formalPostingPermissionStatus：placeholder_passed</li>
                <li>formalPostingPermissionText：权限占位通过</li>
                <li>权限体系尚未接入，本轮仅保留正式过账权限占位，不执行真实权限校验。</li>
              </ul>
            </section>
            <section>
              <h3>入口日志占位</h3>
              <ul>
                <li>未来将记录操作人、操作时间、凭证号、金额、过账前状态和过账后状态。</li>
                <li>未来将记录总账写入结果、核销结果、银行流水结果和审计备注。</li>
                <li>本轮只显示设计说明，不写入正式过账日志。</li>
              </ul>
            </section>
          </div>
        </section>
        <div class="posting-condition-grid">
          <section>
            <h3>未来允许正式过账的条件</h3>
            <ul>
              <li>正式付款凭证已生成，过账前评审通过，凭证过账准备状态为可过账。</li>
              <li>模拟过账已完成，且模拟结果没有改变正式过账、总账、核销或银行流水字段。</li>
              <li>总账状态仍为未写总账，核销状态仍为未核销，银行流水状态仍为未生成。</li>
              <li>金额、付款对象、凭证号、来源链完整，会计期间和科目体系具备正式检查入口。</li>
            </ul>
          </section>
          <section>
            <h3>正式过账阻断原因</h3>
            <ul>
              <li v-for="reason in detail.formalPostingBlockedReasons || []" :key="reason">{{ reason }}</li>
              <li v-if="!(detail.formalPostingBlockedReasons || []).length">无正式过账阻断原因。</li>
            </ul>
          </section>
          <section>
            <h3>正式过账提醒项</h3>
            <ul>
              <li v-for="warning in detail.formalPostingWarnings || []" :key="warning">{{ warning }}</li>
              <li v-if="!(detail.formalPostingWarnings || []).length">无正式过账提醒项。</li>
            </ul>
          </section>
          <section>
            <h3>未来字段设计边界</h3>
            <ul>
              <li>formalPostingStatus / formalPostingReady 仅表示未来正式过账入口条件。</li>
              <li>formalPostedAt / formalPostedBy 本轮保持为空，不写正式过账时间和过账人。</li>
              <li>ledgerEntryId / ledgerEntryNo 本轮保持为空，不生成总账分录或正式凭证号。</li>
              <li>formalPostingLogs 本轮仅保留设计结构，不写真实正式过账日志。</li>
            </ul>
          </section>
        </div>
      </el-card>

      <el-card shadow="never">
        <template #header><h2>正式过账预执行检查</h2></template>
        <div class="posting-review-summary">
          <article>
            <span>预执行检查状态</span>
            <strong><el-tag :type="formalPostingPreExecuteType(formalPostingPreExecuteSummary(detail).formalPostingPreExecuteStatus)">{{ formalPostingPreExecuteSummary(detail).formalPostingPreExecuteStatusText }}</el-tag></strong>
          </article>
          <article>
            <span>是否可进入后续正式过账</span>
            <strong>{{ formalPostingPreExecuteSummary(detail).formalPostingPreExecuteReady ? '可进入后续正式过账确认设计' : '不可进入后续正式过账' }}</strong>
          </article>
          <article>
            <span>阻断原因数量</span>
            <strong>{{ formalPostingPreExecuteSummary(detail).formalPostingPreExecuteBlockedReasons.length }}</strong>
          </article>
          <article>
            <span>提醒项数量</span>
            <strong>{{ formalPostingPreExecuteSummary(detail).formalPostingPreExecuteWarnings.length }}</strong>
          </article>
        </div>
        <div class="boundary-note">{{ formalPostingPreExecuteSummary(detail).formalPostingPreExecuteConclusion }}</div>
        <div class="posting-condition-grid">
          <section>
            <h3>阻断原因</h3>
            <ul>
              <li v-for="reason in formalPostingPreExecuteSummary(detail).formalPostingPreExecuteBlockedReasons" :key="reason">{{ reason }}</li>
              <li v-if="!formalPostingPreExecuteSummary(detail).formalPostingPreExecuteBlockedReasons.length">无预执行阻断原因。</li>
            </ul>
          </section>
          <section>
            <h3>提醒项</h3>
            <ul>
              <li v-for="warning in formalPostingPreExecuteSummary(detail).formalPostingPreExecuteWarnings" :key="warning">{{ warning }}</li>
              <li v-if="!formalPostingPreExecuteSummary(detail).formalPostingPreExecuteWarnings.length">无预执行提醒项。</li>
            </ul>
          </section>
          <section>
            <h3>与状态机关系</h3>
            <ul>
              <li>只有状态机建议阶段为“正式过账入口就绪”时，预执行检查才可能通过。</li>
              <li>预执行检查通过或有提醒，仅表示具备未来进入正式过账确认设计的条件。</li>
              <li>本轮不推进状态机，不进入 posted。</li>
            </ul>
          </section>
          <section>
            <h3>本轮边界</h3>
            <ul>
              <li>预执行检查只读，不改变 postingStatus。</li>
              <li>不改变 ledgerStatus，不写总账，不生成总账分录。</li>
              <li>不改变 paymentWriteOffStatus，不做付款核销。</li>
              <li>不写 formalPostedAt / formalPostedBy，不生成 ledgerEntryId / ledgerEntryNo，不生成银行流水，不写正式过账日志。</li>
            </ul>
          </section>
        </div>
      </el-card>

      <el-card shadow="never">
        <template #header><h2>正式过账确认前锁定设计</h2></template>
        <div class="posting-review-summary">
          <article>
            <span>确认前锁定状态</span>
            <strong><el-tag :type="formalPostingLockType(formalPostingLockSummary(detail).formalPostingLockStatus)">{{ formalPostingLockSummary(detail).formalPostingLockStatusText }}</el-tag></strong>
          </article>
          <article>
            <span>是否可进入确认前锁定</span>
            <strong>{{ formalPostingLockSummary(detail).formalPostingLockReady ? '可进入确认前锁定设计' : '不可进入确认前锁定' }}</strong>
          </article>
          <article>
            <span>锁定阻断数量</span>
            <strong>{{ formalPostingLockSummary(detail).formalPostingLockBlockedReasons.length }}</strong>
          </article>
          <article>
            <span>锁定提醒数量</span>
            <strong>{{ formalPostingLockSummary(detail).formalPostingLockWarnings.length }}</strong>
          </article>
        </div>
        <div class="boundary-note">{{ formalPostingLockSummary(detail).formalPostingLockConclusion }}</div>
        <div class="posting-condition-grid">
          <section>
            <h3>锁定阻断原因</h3>
            <ul>
              <li v-for="reason in formalPostingLockSummary(detail).formalPostingLockBlockedReasons" :key="reason">{{ reason }}</li>
              <li v-if="!formalPostingLockSummary(detail).formalPostingLockBlockedReasons.length">无确认前锁定阻断原因。</li>
            </ul>
          </section>
          <section>
            <h3>锁定提醒项</h3>
            <ul>
              <li v-for="warning in formalPostingLockSummary(detail).formalPostingLockWarnings" :key="warning">{{ warning }}</li>
              <li v-if="!formalPostingLockSummary(detail).formalPostingLockWarnings.length">无确认前锁定提醒项。</li>
            </ul>
          </section>
          <section>
            <h3>与预执行检查和状态机关系</h3>
            <ul>
              <li>确认前锁定必须建立在状态机入口就绪和预执行检查无阻断的基础上。</li>
              <li>预执行检查有提醒但无阻断时，锁定状态可显示“锁定有提醒”。</li>
              <li>本轮只展示锁定设计，不真实锁定凭证或会计期间。</li>
            </ul>
          </section>
          <section>
            <h3>本轮边界</h3>
            <ul>
              <li>锁定预检查只读，不改变 postingStatus。</li>
              <li>不改变 ledgerStatus，不写总账，不生成总账分录。</li>
              <li>不改变 paymentWriteOffStatus，不做付款核销。</li>
              <li>不写 formalPostedAt / formalPostedBy，不生成 ledgerEntryId / ledgerEntryNo，不生成银行流水，不写正式过账日志。</li>
              <li>不真实锁定凭证，不真实锁定会计期间，不把状态机推进到 posted。</li>
            </ul>
          </section>
        </div>
      </el-card>

      <el-card shadow="never">
        <template #header><h2>正式过账最终确认设计</h2></template>
        <div class="posting-review-summary">
          <article>
            <span>最终确认状态</span>
            <strong><el-tag :type="formalPostingConfirmType(formalPostingConfirmSummary(detail).formalPostingConfirmStatus)">{{ formalPostingConfirmSummary(detail).formalPostingConfirmStatusText }}</el-tag></strong>
          </article>
          <article>
            <span>是否可进入最终确认</span>
            <strong>{{ formalPostingConfirmSummary(detail).formalPostingConfirmReady ? '可进入最终确认设计' : '不可进入最终确认' }}</strong>
          </article>
          <article>
            <span>最终确认阻断数量</span>
            <strong>{{ formalPostingConfirmSummary(detail).formalPostingConfirmBlockedReasons.length }}</strong>
          </article>
          <article>
            <span>最终确认提醒数量</span>
            <strong>{{ formalPostingConfirmSummary(detail).formalPostingConfirmWarnings.length }}</strong>
          </article>
        </div>
        <div class="boundary-note">{{ formalPostingConfirmSummary(detail).formalPostingConfirmConclusion }}</div>
        <div class="posting-condition-grid">
          <section>
            <h3>最终确认阻断原因</h3>
            <ul>
              <li v-for="reason in formalPostingConfirmSummary(detail).formalPostingConfirmBlockedReasons" :key="reason">{{ reason }}</li>
              <li v-if="!formalPostingConfirmSummary(detail).formalPostingConfirmBlockedReasons.length">无最终确认阻断原因。</li>
            </ul>
          </section>
          <section>
            <h3>最终确认提醒项</h3>
            <ul>
              <li v-for="warning in formalPostingConfirmSummary(detail).formalPostingConfirmWarnings" :key="warning">{{ warning }}</li>
              <li v-if="!formalPostingConfirmSummary(detail).formalPostingConfirmWarnings.length">无最终确认提醒项。</li>
            </ul>
          </section>
          <section>
            <h3>与前置检查关系</h3>
            <ul>
              <li>最终确认必须建立在状态机入口就绪、预执行检查无阻断、确认前锁定无阻断的基础上。</li>
              <li>确认前锁定有提醒但无阻断时，最终确认状态可显示“最终确认有提醒”。</li>
              <li>本轮只展示最终确认设计，不执行正式过账。</li>
            </ul>
          </section>
          <section>
            <h3>本轮边界</h3>
            <ul>
              <li>最终确认检查只读，不改变 postingStatus。</li>
              <li>不改变 ledgerStatus，不写总账，不生成总账分录。</li>
              <li>不改变 paymentWriteOffStatus，不做付款核销。</li>
              <li>不写 formalPostedAt / formalPostedBy，不生成 ledgerEntryId / ledgerEntryNo，不生成银行流水，不写正式过账日志。</li>
              <li>不真实锁定凭证或会计期间，不把状态机推进到 posted。</li>
            </ul>
          </section>
        </div>
      </el-card>

      <el-card shadow="never">
        <template #header><h2>基础验证数据体系设计</h2></template>
        <div class="boundary-note">当前设计状态：只读设计已建立。后续进入真实总账写入前，必须先规划基础验证数据体系。本轮只做设计说明，不新增基础数据、不初始化数据、不覆盖 localStorage。</div>
        <div class="posting-condition-grid">
          <section>
            <h3>设计覆盖数据域</h3>
            <ul>
              <li v-for="domain in seedDataPlanDomains" :key="domain.key">{{ domain.key }}：{{ domain.purpose }}；用于{{ domain.validation }}。</li>
            </ul>
          </section>
          <section>
            <h3>为什么需要基础验证数据</h3>
            <ul>
              <li>真实写总账前，需要验证借贷平衡、总账余额、资金账户余额、银行账户余额。</li>
              <li>后续还需要验证库存数量和金额、供应商往来余额、付款核销和报表结果。</li>
              <li>没有隔离的验证数据体系，真实写账结果无法被稳定复核。</li>
            </ul>
          </section>
          <section>
            <h3>后续建议覆盖范围</h3>
            <ul>
              <li>chartOfAccounts、openingBalances、bankAccounts、suppliers。</li>
              <li>inventoryItems、warehouses、inventoryOpeningBalances、supplierBalances。</li>
              <li>p2pScenarioSamples、reportCheckSamples。</li>
            </ul>
          </section>
          <section>
            <h3>数据隔离策略</h3>
            <ul>
              <li v-for="rule in seedDataPlanIsolationRules" :key="rule">{{ rule }}</li>
            </ul>
          </section>
          <section>
            <h3>后续版本建议</h3>
            <ul>
              <li v-for="item in seedDataPlanNextVersions" :key="item.version">{{ item.version }}：{{ item.name }}。</li>
            </ul>
          </section>
          <section>
            <h3>本轮保护边界</h3>
            <ul>
              <li>本轮不新增基础数据、不初始化基础数据、不写入种子数据。</li>
              <li>不新增会计科目余额、库存期初、资金账户余额或银行账户余额真实数据。</li>
              <li>不覆盖当前 localStorage，不改变当前正式付款凭证测试数据。</li>
              <li>后续基础验证数据必须带 seed / demo / sandbox 标记，并与用户数据隔离。</li>
            </ul>
          </section>
        </div>
      </el-card>

      <el-card shadow="never">
        <template #header><h2>基础验证数据初始化工具设计</h2></template>
        <div class="boundary-note">当前设计状态：初始化工具只读设计已就绪。本轮仅展示未来初始化工具的条件、预览、namespace 和安全边界，不初始化基础数据、不写 localStorage、不覆盖当前正式付款凭证测试数据。</div>
        <div class="posting-review-summary">
          <article>
            <span>工具设计状态</span>
            <strong><el-tag :type="seedDataInitToolType(seedDataInitToolSummary.seedDataInitToolStatus)">{{ seedDataInitToolSummary.seedDataInitToolStatusText }}</el-tag></strong>
          </article>
          <article>
            <span>是否可进入未来工具阶段</span>
            <strong>{{ seedDataInitToolSummary.seedDataInitToolReady ? '是，仅表示设计就绪' : '否，仍有阻断条件' }}</strong>
          </article>
          <article>
            <span>阻断项</span>
            <strong>{{ seedDataInitToolSummary.seedDataInitToolBlockedReasons.length }}</strong>
          </article>
          <article>
            <span>提醒项</span>
            <strong>{{ seedDataInitToolSummary.seedDataInitToolWarnings.length }}</strong>
          </article>
        </div>
        <div class="posting-actions">
          <el-button type="primary" plain @click="handleSeedDataInitToolCheck('conditions')">查看初始化条件</el-button>
          <el-button type="info" plain @click="handleSeedDataInitToolCheck('precheck')">初始化工具预检查</el-button>
          <el-button type="warning" disabled>一键初始化基础验证数据</el-button>
          <el-button type="danger" disabled>一键清除基础验证数据</el-button>
        </div>
        <div class="posting-condition-grid">
          <section>
            <h3>namespace 设计</h3>
            <ul>
              <li v-for="item in seedDataInitToolSummary.seedDataInitNamespaces" :key="item.namespace">{{ item.namespace }}：{{ item.scope }}；{{ item.rule }}。</li>
            </ul>
          </section>
          <section>
            <h3>初始化预览数据域</h3>
            <ul>
              <li v-for="domain in seedDataInitToolSummary.seedDataInitPreviewDomains" :key="domain.key">{{ domain.key }}：{{ domain.action }}；本轮预计数量：{{ domain.plannedCount }}，实际生成：0。</li>
            </ul>
          </section>
          <section>
            <h3>初始化安全规则</h3>
            <ul>
              <li v-for="rule in seedDataInitToolSummary.seedDataInitSafetyRules" :key="rule">{{ rule }}</li>
            </ul>
          </section>
          <section>
            <h3>阻断原因</h3>
            <ul>
              <li v-for="reason in seedDataInitToolSummary.seedDataInitToolBlockedReasons" :key="reason">{{ reason }}</li>
              <li v-if="!seedDataInitToolSummary.seedDataInitToolBlockedReasons.length">无工具设计阻断原因。</li>
            </ul>
          </section>
          <section>
            <h3>提醒项</h3>
            <ul>
              <li v-for="warning in seedDataInitToolSummary.seedDataInitToolWarnings" :key="warning">{{ warning }}</li>
            </ul>
          </section>
          <section>
            <h3>本轮保护边界</h3>
            <ul>
              <li>一键初始化和一键清除按钮本轮禁用，只作为未来工具入口占位。</li>
              <li>可点击按钮只显示只读检查结果，不写 localStorage、不生成基础数据、不清除数据。</li>
              <li>未来清除工具只能清除 seed / demo / sandbox namespace 下的数据，不能删除用户手工数据。</li>
              <li>后续 V1.13.18 再衔接借贷平衡与余额验证器，本轮不做真实验证器。</li>
            </ul>
          </section>
        </div>
      </el-card>

      <el-card shadow="never">
        <template #header><h2>借贷平衡与余额验证器设计</h2></template>
        <div class="boundary-note">当前设计状态：验证器结构已建立。本轮只设计验证规则和展示字段，不读取真实余额、不计算真实余额、不修改余额、不生成财务结果。</div>
        <div class="posting-review-summary">
          <article>
            <span>验证器状态</span>
            <strong><el-tag :type="balanceValidatorType(balanceValidatorSummary.balanceValidatorStatus)">{{ balanceValidatorSummary.balanceValidatorStatusText }}</el-tag></strong>
          </article>
          <article>
            <span>是否具备设计条件</span>
            <strong>{{ balanceValidatorSummary.balanceValidatorReady ? '是，仅表示设计完成' : '否，仍有阻断条件' }}</strong>
          </article>
          <article>
            <span>借贷差额</span>
            <strong>{{ balanceValidatorSummary.balanceDifference }}</strong>
          </article>
          <article>
            <span>是否平衡</span>
            <strong>{{ balanceValidatorSummary.isBalanced ? '设计规则：平衡' : '设计规则：待真实数据验证' }}</strong>
          </article>
        </div>
        <div class="posting-condition-grid">
          <section>
            <h3>借贷平衡验证设计</h3>
            <ul>
              <li>借方合计字段：debitTotal。</li>
              <li>贷方合计字段：creditTotal。</li>
              <li>借贷差额字段：balanceDifference。</li>
              <li>规则：借方合计 = 贷方合计时，isBalanced = true。</li>
              <li>{{ balanceValidatorSummary.balanceConclusion }}</li>
            </ul>
          </section>
          <section>
            <h3>总账余额验证设计</h3>
            <ul>
              <li>状态字段：ledgerBalanceCheckStatus。</li>
              <li>公式：期末余额 = 期初余额 + 借方发生额 - 贷方发生额。</li>
              <li>{{ balanceValidatorSummary.ledgerBalanceConclusion }}</li>
            </ul>
          </section>
          <section>
            <h3>银行余额验证设计</h3>
            <ul>
              <li>状态字段：bankBalanceCheckStatus。</li>
              <li>公式：当前余额 = 期初余额 + 收入 - 支出。</li>
              <li>{{ balanceValidatorSummary.bankBalanceConclusion }}</li>
            </ul>
          </section>
          <section>
            <h3>供应商余额验证设计</h3>
            <ul>
              <li>状态字段：supplierBalanceCheckStatus。</li>
              <li>公式：当前应付余额 = 期初应付 + 新增应付 - 付款金额。</li>
              <li>{{ balanceValidatorSummary.supplierBalanceConclusion }}</li>
            </ul>
          </section>
          <section>
            <h3>库存余额验证设计</h3>
            <ul>
              <li>状态字段：inventoryBalanceCheckStatus。</li>
              <li>数量公式：库存数量 = 期初数量 + 入库数量 - 出库数量。</li>
              <li>金额公式：库存金额 = 期初金额 + 入库金额 - 出库金额。</li>
              <li>{{ balanceValidatorSummary.inventoryBalanceConclusion }}</li>
            </ul>
          </section>
          <section>
            <h3>报表验证设计</h3>
            <ul>
              <li>状态字段：reportCheckStatus。</li>
              <li>未来验证资产负债表、科目余额表、银行余额表、供应商往来表、库存结存表。</li>
              <li>{{ balanceValidatorSummary.reportCheckConclusion }}</li>
            </ul>
          </section>
          <section>
            <h3>验证器提醒项</h3>
            <ul>
              <li v-for="warning in balanceValidatorSummary.balanceValidatorWarnings" :key="warning">{{ warning }}</li>
            </ul>
          </section>
          <section>
            <h3>本轮边界</h3>
            <ul>
              <li>本轮不读取真实余额、不计算真实余额、不修改库存余额、资金余额或供应商余额。</li>
              <li>本轮不写总账、不生成总账分录、不正式过账、不核销、不生成银行流水。</li>
              <li>本轮不初始化基础验证数据，不写 chartOfAccounts、openingBalances、bankAccounts 等基础数据。</li>
              <li>所有验证字段只用于设计诊断，不写入业务状态。</li>
            </ul>
          </section>
        </div>
      </el-card>

      <el-card shadow="never">
        <template #header><h2>真实总账写入前复核设计</h2></template>
        <div class="boundary-note">当前设计状态：真实总账写入前复核器已建立。本轮只定义未来写总账前必须检查的条件，不正式过账、不写总账、不生成总账分录、不核销、不生成银行流水。</div>
        <div class="posting-review-summary">
          <article>
            <span>复核状态</span>
            <strong><el-tag :type="ledgerPostingReviewType(ledgerPostingReviewSummary.ledgerPostingReviewStatus)">{{ ledgerPostingReviewSummary.ledgerPostingReviewStatusText }}</el-tag></strong>
          </article>
          <article>
            <span>是否具备复核条件</span>
            <strong>{{ ledgerPostingReviewSummary.ledgerPostingReviewReady ? '是，仅表示设计通过' : '否，仍有阻断条件' }}</strong>
          </article>
          <article>
            <span>借贷差额</span>
            <strong>{{ ledgerPostingReviewSummary.ledgerPostingDifference }}</strong>
          </article>
          <article>
            <span>是否平衡</span>
            <strong>{{ ledgerPostingReviewSummary.ledgerPostingBalanced ? '设计规则：平衡' : '设计规则：待真实数据验证' }}</strong>
          </article>
        </div>
        <div class="posting-condition-grid">
          <section>
            <h3>财务基础数据检查设计</h3>
            <ul>
              <li>状态字段：financialDataCheckStatus。</li>
              <li>未来检查 chartOfAccounts、period、openingBalances、supplierBalances、bankAccounts。</li>
              <li>{{ ledgerPostingReviewSummary.financialDataCheckConclusion }}</li>
            </ul>
          </section>
          <section>
            <h3>借贷平衡检查设计</h3>
            <ul>
              <li>借方字段：ledgerPostingDebitTotal。</li>
              <li>贷方字段：ledgerPostingCreditTotal。</li>
              <li>差额字段：ledgerPostingDifference。</li>
              <li>规则：借方 = 贷方时 ledgerPostingBalanced = true。</li>
              <li>{{ ledgerPostingReviewSummary.balanceCheckConclusion }}</li>
            </ul>
          </section>
          <section>
            <h3>科目完整性检查设计</h3>
            <ul>
              <li>状态字段：accountCompletenessStatus。</li>
              <li>未来检查借方科目、贷方科目、科目编码、科目方向、科目状态。</li>
              <li>{{ ledgerPostingReviewSummary.accountCompletenessConclusion }}</li>
            </ul>
          </section>
          <section>
            <h3>会计期间检查设计</h3>
            <ul>
              <li>状态字段：periodCheckStatus。</li>
              <li>未来检查会计期间存在、开放、未关闭、日期合法。</li>
              <li>{{ ledgerPostingReviewSummary.periodCheckConclusion }}</li>
            </ul>
          </section>
          <section>
            <h3>权限检查设计</h3>
            <ul>
              <li>状态字段：postingPermissionStatus。</li>
              <li>未来检查操作人权限、审批权限、财务权限、审计权限。</li>
              <li>{{ ledgerPostingReviewSummary.postingPermissionConclusion }}</li>
            </ul>
          </section>
          <section>
            <h3>审计检查设计</h3>
            <ul>
              <li>状态字段：auditCheckStatus。</li>
              <li>未来检查操作记录、来源链、审批链、修改记录、时间记录。</li>
              <li>{{ ledgerPostingReviewSummary.auditCheckConclusion }}</li>
            </ul>
          </section>
          <section>
            <h3>总账写入结构检查设计</h3>
            <ul>
              <li>状态字段：ledgerEntryStructureStatus。</li>
              <li>未来检查凭证编号、会计日期、科目、借贷金额、来源单据、操作人、时间。</li>
              <li>{{ ledgerPostingReviewSummary.ledgerEntryStructureConclusion }}</li>
            </ul>
          </section>
          <section>
            <h3>回滚能力检查设计</h3>
            <ul>
              <li>状态字段：rollbackCapabilityStatus。</li>
              <li>未来检查失败时是否可追踪、可恢复、保留日志、避免重复写入。</li>
              <li>{{ ledgerPostingReviewSummary.rollbackCapabilityConclusion }}</li>
            </ul>
          </section>
          <section>
            <h3>复核提醒项</h3>
            <ul>
              <li v-for="warning in ledgerPostingReviewSummary.ledgerPostingReviewWarnings" :key="warning">{{ warning }}</li>
            </ul>
          </section>
          <section>
            <h3>本轮边界</h3>
            <ul>
              <li>本轮不写总账、不生成总账分录、不生成 ledgerEntryId / ledgerEntryNo。</li>
              <li>本轮不正式过账、不修改 postingStatus、ledgerStatus、paymentWriteOffStatus。</li>
              <li>本轮不写 formalPostedAt / formalPostedBy，不生成正式过账日志。</li>
              <li>本轮不核销、不生成银行流水、不初始化基础数据、不写 localStorage。</li>
            </ul>
          </section>
        </div>
      </el-card>

      <el-card shadow="never">
        <template #header><h2>模拟总账写入设计</h2></template>
        <div class="boundary-note">当前设计状态：模拟总账写入模型已建立。本轮只生成页面内模拟对象和只读诊断，不写真实总账、不生成真实总账凭证、不修改正式财务字段。</div>
        <div class="posting-review-summary">
          <article>
            <span>模拟总账状态</span>
            <strong><el-tag :type="simulationLedgerType(simulationLedgerSummary(detail).simulationLedgerStatus)">{{ simulationLedgerSummary(detail).simulationLedgerStatusText }}</el-tag></strong>
          </article>
          <article>
            <span>模拟借方合计</span>
            <strong>{{ simulationLedgerSummary(detail).simulationDebitTotal }}</strong>
          </article>
          <article>
            <span>模拟贷方合计</span>
            <strong>{{ simulationLedgerSummary(detail).simulationCreditTotal }}</strong>
          </article>
          <article>
            <span>模拟是否平衡</span>
            <strong>{{ simulationLedgerSummary(detail).simulationBalanced ? '平衡' : '不平衡' }}</strong>
          </article>
        </div>
        <div class="posting-actions">
          <el-button type="primary" plain @click="handleSimulationLedgerPreview(detail)">模拟生成总账分录</el-button>
        </div>
        <div class="posting-condition-grid">
          <section>
            <h3>模拟会计分录</h3>
            <ul>
              <li v-for="entry in simulationLedgerSummary(detail).simulationLedgerEntries" :key="entry.entryId">
                {{ entry.entryId }}：{{ entry.direction === 'debit' ? '借' : '贷' }} {{ entry.accountCode }} {{ entry.accountName }} {{ entry.amount }}；来源 {{ entry.sourceVoucherNo }}；场景 {{ entry.scenarioId }}。
              </li>
            </ul>
          </section>
          <section>
            <h3>付款业务模拟规则</h3>
            <ul>
              <li>付款凭证未来模拟分录：借：应付账款；贷：银行存款。</li>
              <li>模拟借贷金额来自当前正式付款凭证金额。</li>
              <li>本轮只展示模拟对象，不写入真实总账。</li>
            </ul>
          </section>
          <section>
            <h3>模拟余额变化</h3>
            <ul>
              <li v-for="change in simulationLedgerSummary(detail).simulationBalanceChanges" :key="change.accountCode">
                {{ change.accountCode }} {{ change.accountName }}：{{ change.directionText }} {{ change.changeAmount }}；模拟期末余额仅为设计占位。
              </li>
            </ul>
          </section>
          <section>
            <h3>模拟报表影响</h3>
            <ul>
              <li v-for="impact in simulationLedgerSummary(detail).simulationReportImpact" :key="impact.report">{{ impact.report }}：{{ impact.impact }}。</li>
            </ul>
          </section>
          <section>
            <h3>模拟提醒项</h3>
            <ul>
              <li v-for="warning in simulationLedgerSummary(detail).simulationLedgerWarnings" :key="warning">{{ warning }}</li>
            </ul>
          </section>
          <section>
            <h3>本轮边界</h3>
            <ul>
              <li>模拟按钮只展示模拟分录结果，不写真实总账。</li>
              <li>不改变 ledgerStatus、postingStatus、paymentWriteOffStatus。</li>
              <li>不写 formalPostedAt / formalPostedBy，不生成真实 ledgerEntryId / ledgerEntryNo。</li>
              <li>不生成银行流水，不执行付款核销，不初始化基础数据，不写 localStorage。</li>
            </ul>
          </section>
        </div>
      </el-card>

      <el-card shadow="never">
        <template #header><h2>模拟总账结果验证设计</h2></template>
        <div class="boundary-note">当前设计状态：模拟总账结果验证器已建立。本轮只验证页面内模拟对象，不写真实总账、不生成真实总账分录、不改变正式财务字段。</div>
        <div class="posting-review-summary">
          <article>
            <span>验证状态</span>
            <strong><el-tag :type="simulationLedgerValidationType(simulationLedgerValidationSummary(detail).simulationLedgerValidationStatus)">{{ simulationLedgerValidationSummary(detail).simulationLedgerValidationStatusText }}</el-tag></strong>
          </article>
          <article>
            <span>验证是否通过</span>
            <strong>{{ simulationLedgerValidationSummary(detail).simulationLedgerValidationReady ? '是，仅表示模拟验证通过' : '否，存在模拟阻断' }}</strong>
          </article>
          <article>
            <span>验证差额</span>
            <strong>{{ simulationLedgerValidationSummary(detail).simulationValidationDifference }}</strong>
          </article>
          <article>
            <span>验证平衡</span>
            <strong>{{ simulationLedgerValidationSummary(detail).simulationValidationBalanced ? '平衡' : '不平衡' }}</strong>
          </article>
        </div>
        <div class="posting-actions">
          <el-button type="primary" plain @click="handleSimulationLedgerValidation(detail)">验证模拟总账结果</el-button>
        </div>
        <div class="posting-condition-grid">
          <section>
            <h3>分录验证</h3>
            <ul>
              <li>状态字段：simulationEntryCheckStatus。</li>
              <li>验证借方、贷方、科目、金额、来源凭证是否存在。</li>
              <li>{{ simulationLedgerValidationSummary(detail).simulationEntryCheckConclusion }}</li>
            </ul>
          </section>
          <section>
            <h3>借贷验证</h3>
            <ul>
              <li>状态字段：simulationDebitCreditCheckStatus。</li>
              <li>规则：simulationDebitTotal 必须等于 simulationCreditTotal。</li>
              <li>{{ simulationLedgerValidationSummary(detail).simulationDebitCreditCheckConclusion }}</li>
            </ul>
          </section>
          <section>
            <h3>科目方向验证</h3>
            <ul>
              <li>状态字段：simulationAccountDirectionCheckStatus。</li>
              <li>规则：应付账款允许付款业务借方变化，银行存款允许资金流出贷方变化。</li>
              <li>{{ simulationLedgerValidationSummary(detail).simulationAccountDirectionCheckConclusion }}</li>
            </ul>
          </section>
          <section>
            <h3>金额一致性验证</h3>
            <ul>
              <li>状态字段：simulationAmountCheckStatus。</li>
              <li>规则：正式付款凭证金额应等于模拟借方和模拟贷方金额。</li>
              <li>{{ simulationLedgerValidationSummary(detail).simulationAmountCheckConclusion }}</li>
            </ul>
          </section>
          <section>
            <h3>模拟余额验证</h3>
            <ul>
              <li>状态字段：simulationBalanceCheckStatus。</li>
              <li>规则：未来验证期初余额 + 模拟发生额 = 模拟期末余额。</li>
              <li>{{ simulationLedgerValidationSummary(detail).simulationBalanceCheckConclusion }}</li>
            </ul>
          </section>
          <section>
            <h3>模拟报表验证</h3>
            <ul>
              <li>状态字段：simulationReportCheckStatus。</li>
              <li>未来验证科目余额表、资产负债表、供应商往来表、银行余额表。</li>
              <li>{{ simulationLedgerValidationSummary(detail).simulationReportCheckConclusion }}</li>
            </ul>
          </section>
          <section>
            <h3>验证提醒项</h3>
            <ul>
              <li v-for="warning in simulationLedgerValidationSummary(detail).simulationLedgerValidationWarnings" :key="warning">{{ warning }}</li>
            </ul>
          </section>
          <section>
            <h3>本轮边界</h3>
            <ul>
              <li>验证按钮只验证模拟对象，不写真实总账。</li>
              <li>不改变 ledgerStatus、postingStatus、paymentWriteOffStatus。</li>
              <li>不执行核销，不生成银行流水，不初始化基础数据，不写 localStorage。</li>
            </ul>
          </section>
        </div>
      </el-card>

      <el-card shadow="never">
        <template #header><h2>模拟总账与基础验证数据关联设计</h2></template>
        <div class="boundary-note">当前设计状态：模拟总账与基础验证数据关联模型已建立。本轮只定义映射关系，不读取真实基础数据、不初始化基础数据、不写 localStorage。</div>
        <div class="posting-review-summary">
          <article>
            <span>数据关联状态</span>
            <strong><el-tag :type="simulationDataMappingType(simulationDataMappingSummary(detail).simulationDataMappingStatus)">{{ simulationDataMappingSummary(detail).simulationDataMappingStatusText }}</el-tag></strong>
          </article>
          <article>
            <span>是否具备映射设计</span>
            <strong>{{ simulationDataMappingSummary(detail).simulationDataMappingReady ? '是，仅表示设计完成' : '否，仍有阻断条件' }}</strong>
          </article>
          <article>
            <span>科目映射数</span>
            <strong>{{ simulationDataMappingSummary(detail).simulationAccountMapping.length }}</strong>
          </article>
          <article>
            <span>报表映射数</span>
            <strong>{{ simulationDataMappingSummary(detail).simulationReportMapping.length }}</strong>
          </article>
        </div>
        <div class="posting-actions">
          <el-button type="primary" plain @click="handleSimulationDataMappingCheck(detail)">检查模拟数据关联</el-button>
        </div>
        <div class="posting-condition-grid">
          <section>
            <h3>科目映射</h3>
            <ul>
              <li v-for="item in simulationDataMappingSummary(detail).simulationAccountMapping" :key="item.accountCode">{{ item.accountCode }} {{ item.accountName }}：{{ item.accountDirection }}；来源 {{ item.sourceType }}。</li>
            </ul>
          </section>
          <section>
            <h3>供应商映射</h3>
            <ul>
              <li>{{ simulationDataMappingSummary(detail).simulationSupplierMapping.supplierId }}：{{ simulationDataMappingSummary(detail).simulationSupplierMapping.supplierName }}；关联 {{ simulationDataMappingSummary(detail).simulationSupplierMapping.supplierBalanceReference }}。</li>
            </ul>
          </section>
          <section>
            <h3>银行账户映射</h3>
            <ul>
              <li>{{ simulationDataMappingSummary(detail).simulationBankMapping.bankAccountId }}：{{ simulationDataMappingSummary(detail).simulationBankMapping.bankAccountName }}；关联 {{ simulationDataMappingSummary(detail).simulationBankMapping.balanceReference }}。</li>
            </ul>
          </section>
          <section>
            <h3>P2P 场景映射</h3>
            <ul>
              <li>{{ simulationDataMappingSummary(detail).simulationScenarioMapping.scenarioId }}：{{ simulationDataMappingSummary(detail).simulationScenarioMapping.scenarioType }}；来源 {{ simulationDataMappingSummary(detail).simulationScenarioMapping.sourceVoucherNo }}。</li>
            </ul>
          </section>
          <section>
            <h3>报表验证映射</h3>
            <ul>
              <li v-for="item in simulationDataMappingSummary(detail).simulationReportMapping" :key="item.report">{{ item.report }}：关联 {{ item.reference }}；{{ item.scope }}。</li>
            </ul>
          </section>
          <section>
            <h3>关联提醒项</h3>
            <ul>
              <li v-for="warning in simulationDataMappingSummary(detail).simulationDataMappingWarnings" :key="warning">{{ warning }}</li>
            </ul>
          </section>
          <section>
            <h3>本轮边界</h3>
            <ul>
              <li>本轮只建立模拟总账与基础验证数据的映射设计。</li>
              <li>不读取真实 chartOfAccounts、supplierBalances、bankAccounts、p2pScenarioSamples、reportCheckSamples。</li>
              <li>不写 localStorage，不初始化基础数据，不改变正式付款凭证状态。</li>
            </ul>
          </section>
        </div>
      </el-card>

      <el-card shadow="never">
        <template #header><h2>模拟P2P完整业务场景验证设计</h2></template>
        <div class="boundary-note">当前设计状态：模拟 P2P 完整业务链验证模型已建立。本轮只展示采购到付款的模拟链路，不生成真实采购、库存、应付、总账或银行流水数据。</div>
        <div class="posting-review-summary">
          <article>
            <span>场景验证状态</span>
            <strong><el-tag :type="simulationP2PValidationType(simulationP2PScenarioSummary(detail).simulationP2PValidationStatus)">{{ simulationP2PScenarioSummary(detail).simulationP2PValidationStatusText }}</el-tag></strong>
          </article>
          <article>
            <span>是否具备完整链</span>
            <strong>{{ simulationP2PScenarioSummary(detail).simulationP2PValidationReady ? '是，仅表示模拟链完整' : '否，仍有阻断条件' }}</strong>
          </article>
          <article>
            <span>链路阶段数</span>
            <strong>{{ Object.keys(simulationP2PScenarioSummary(detail).simulationP2PFlow).length }}</strong>
          </article>
          <article>
            <span>模拟付款金额</span>
            <strong>{{ simulationP2PScenarioSummary(detail).simulationP2PFlow.payment.paymentAmount }}</strong>
          </article>
        </div>
        <div class="posting-actions">
          <el-button type="primary" plain @click="handleSimulationP2PScenarioCheck(detail)">检查模拟P2P业务链</el-button>
        </div>
        <div class="posting-condition-grid">
          <section>
            <h3>请购关联</h3>
            <ul>
              <li>请购编号：{{ simulationP2PScenarioSummary(detail).simulationP2PFlow.request.requestId }}</li>
              <li>请购状态：{{ simulationP2PScenarioSummary(detail).simulationP2PFlow.request.requestStatus }}</li>
              <li>请购金额：{{ simulationP2PScenarioSummary(detail).simulationP2PFlow.request.requestAmount }}</li>
            </ul>
          </section>
          <section>
            <h3>采购订单关联</h3>
            <ul>
              <li>采购订单：{{ simulationP2PScenarioSummary(detail).simulationP2PFlow.purchaseOrder.purchaseOrderNo }}</li>
              <li>供应商：{{ simulationP2PScenarioSummary(detail).simulationP2PFlow.purchaseOrder.supplierId }}</li>
              <li>订单金额：{{ simulationP2PScenarioSummary(detail).simulationP2PFlow.purchaseOrder.orderAmount }}</li>
            </ul>
          </section>
          <section>
            <h3>收货关联</h3>
            <ul>
              <li>收货单：{{ simulationP2PScenarioSummary(detail).simulationP2PFlow.receipt.receiptNo }}</li>
              <li>收货数量：{{ simulationP2PScenarioSummary(detail).simulationP2PFlow.receipt.receivedQuantity }}</li>
              <li>收货金额：{{ simulationP2PScenarioSummary(detail).simulationP2PFlow.receipt.receivedAmount }}</li>
            </ul>
          </section>
          <section>
            <h3>入库关联</h3>
            <ul>
              <li>仓库：{{ simulationP2PScenarioSummary(detail).simulationP2PFlow.inventory.warehouseId }}</li>
              <li>库存影响金额：{{ simulationP2PScenarioSummary(detail).simulationP2PFlow.inventory.inventoryAmount }}</li>
            </ul>
          </section>
          <section>
            <h3>应付关联</h3>
            <ul>
              <li>应付金额：{{ simulationP2PScenarioSummary(detail).simulationP2PFlow.payable.payableAmount }}</li>
              <li>供应商余额影响：{{ simulationP2PScenarioSummary(detail).simulationP2PFlow.payable.supplierBalanceImpact }}</li>
            </ul>
          </section>
          <section>
            <h3>付款关联</h3>
            <ul>
              <li>付款凭证：{{ simulationP2PScenarioSummary(detail).simulationP2PFlow.payment.paymentVoucherNo }}</li>
              <li>付款金额：{{ simulationP2PScenarioSummary(detail).simulationP2PFlow.payment.paymentAmount }}</li>
            </ul>
          </section>
          <section>
            <h3>模拟总账关联</h3>
            <ul>
              <li>模拟借方合计：{{ simulationP2PScenarioSummary(detail).simulationP2PFlow.ledger.simulationDebitTotal }}</li>
              <li>模拟贷方合计：{{ simulationP2PScenarioSummary(detail).simulationP2PFlow.ledger.simulationCreditTotal }}</li>
              <li>模拟分录数：{{ simulationP2PScenarioSummary(detail).simulationP2PFlow.ledger.simulationLedgerEntries.length }}</li>
            </ul>
          </section>
          <section>
            <h3>模拟报表影响</h3>
            <ul>
              <li v-for="impact in simulationP2PScenarioSummary(detail).simulationP2PFlow.reportImpact" :key="impact.report">{{ impact.report }}：{{ impact.impact }}。</li>
            </ul>
          </section>
          <section>
            <h3>验证提醒项</h3>
            <ul>
              <li v-for="warning in simulationP2PScenarioSummary(detail).simulationP2PValidationWarnings" :key="warning">{{ warning }}</li>
            </ul>
          </section>
          <section>
            <h3>本轮边界</h3>
            <ul>
              <li>本轮只设计模拟 P2P 链路，不生成真实请购、采购订单、收货、入库或应付数据。</li>
              <li>不修改供应商余额、库存余额、银行余额，不写真实总账。</li>
              <li>不修改 postingStatus、ledgerStatus、paymentWriteOffStatus，不写 localStorage。</li>
            </ul>
          </section>
        </div>
      </el-card>

      <el-card shadow="never">
        <template #header><h2>过账动作日志</h2></template>
        <div class="posting-review-summary">
          <article>
            <span>当前建议阶段</span>
            <h2 class="diagnostic-title">正式过账状态机草案</h2>
            <strong><el-tag :type="formalPostingFlowType(formalPostingFlowSummary(detail).formalPostingFlowStatus)">{{ formalPostingFlowSummary(detail).formalPostingFlowStatusText }}</el-tag></strong>
          </article>
          <article>
            <span>阶段序号</span>
            <strong>{{ formalPostingFlowSummary(detail).formalPostingFlowStepIndex }}</strong>
          </article>
          <article>
            <span>是否可进入下一阶段</span>
            <strong>{{ formalPostingFlowSummary(detail).formalPostingFlowCanMoveNext ? '是，仅表示入口就绪' : '否，仍有阻断条件' }}</strong>
          </article>
          <article>
            <span>阻断原因数量</span>
            <strong>{{ formalPostingFlowSummary(detail).formalPostingFlowBlockedReasons.length }}</strong>
          </article>
          <article>
            <span>提醒项数量</span>
            <strong>{{ formalPostingFlowSummary(detail).formalPostingFlowWarnings.length }}</strong>
          </article>
        </div>
        <div class="boundary-note">{{ formalPostingFlowSummary(detail).formalPostingFlowConclusion }}</div>
        <div class="posting-condition-grid">
          <section>
            <h3>状态机阶段</h3>
            <ol class="flow-step-list">
              <li v-for="step in formalPostingFlowSummary(detail).formalPostingFlowSteps" :key="step.status" :class="{ active: step.status === formalPostingFlowSummary(detail).formalPostingFlowStatus }">
                <strong>{{ step.text }}</strong>
                <span>{{ step.description }}</span>
              </li>
            </ol>
          </section>
          <section>
            <h3>下一阶段条件</h3>
            <ul>
              <li>正式付款凭证必须为“正式凭证已生成”。</li>
              <li>过账前评审、凭证过账准备、模拟过账、正式过账前最终设计评审均需满足入口条件。</li>
              <li>总账状态必须保持“未写总账”，核销状态必须保持“未核销”，银行流水状态必须保持“未生成”。</li>
              <li>本轮只允许进入“正式过账入口就绪”的展示，不推进到待确认、预执行、锁定或已过账。</li>
            </ul>
          </section>
          <section>
            <h3>阻断原因</h3>
            <ul>
              <li v-for="reason in formalPostingFlowSummary(detail).formalPostingFlowBlockedReasons" :key="reason">{{ reason }}</li>
              <li v-if="!formalPostingFlowSummary(detail).formalPostingFlowBlockedReasons.length">无状态机阻断原因。</li>
            </ul>
          </section>
          <section>
            <h3>提醒项</h3>
            <ul>
              <li v-for="warning in formalPostingFlowSummary(detail).formalPostingFlowWarnings" :key="warning">{{ warning }}</li>
              <li v-if="!formalPostingFlowSummary(detail).formalPostingFlowWarnings.length">无状态机提醒项。</li>
            </ul>
          </section>
          <section>
            <h3>未来字段说明</h3>
            <ul>
              <li v-for="field in formalPostingFlowFutureFields" :key="field">{{ field }}</li>
            </ul>
          </section>
          <section>
            <h3>本轮边界</h3>
            <ul>
              <li>状态机预检查只读，不改变 postingStatus。</li>
              <li>不改变 ledgerStatus，不写总账，不生成总账分录。</li>
              <li>不改变 paymentWriteOffStatus，不做付款核销。</li>
              <li>不写 formalPostedAt / formalPostedBy，不生成 ledgerEntryId / ledgerEntryNo，不生成银行流水。</li>
            </ul>
          </section>
        </div>
      </el-card>

      <el-card shadow="never">
        <template #header><h2>过账动作日志</h2></template>
        <el-table :data="detail.postingActionLogs || []" border stripe height="320">
          <el-table-column type="index" label="序号" width="70" fixed="left" />
          <el-table-column prop="actionTime" label="动作时间" min-width="170" />
          <el-table-column prop="actionType" label="动作类型" width="130" />
          <el-table-column prop="result" label="动作结果" width="150" />
          <el-table-column prop="operator" label="操作人" width="110" />
          <el-table-column prop="amount" label="金额" width="120" />
          <el-table-column prop="beforePostingStatus" label="过账前状态" width="140">
            <template #default="{ row }">{{ postingStatusLabel(row.beforePostingStatus) }}</template>
          </el-table-column>
          <el-table-column prop="afterPostingActionStatus" label="模拟后状态" width="150">
            <template #default="{ row }">{{ postingActionStatusLabel(row.afterPostingActionStatus) }}</template>
          </el-table-column>
          <el-table-column label="财务边界" min-width="260">
            <template #default="{ row }">写总账：{{ row.ledgerWritten ? '是' : '否' }}；核销：{{ row.writeOffCompleted ? '是' : '否' }}；银行流水：{{ row.bankFlowGenerated ? '是' : '否' }}</template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-card shadow="never">
        <template #header><h2>来源追踪</h2></template>
        <div class="source-chain">
          <article v-for="item in sourceChain" :key="item.label">
            <span>{{ item.label }}</span>
            <strong>{{ item.value || '-' }}</strong>
          </article>
        </div>
      </el-card>

      <el-card shadow="never">
        <template #header><h2>借贷分录</h2></template>
        <el-table :data="detail.lines || []" border stripe height="360">
          <el-table-column type="index" label="序号" width="70" fixed="left" />
          <el-table-column prop="direction" label="借贷方向" width="110">
            <template #default="{ row }">{{ row.direction === 'debit' ? '借方' : '贷方' }}</template>
          </el-table-column>
          <el-table-column prop="accountCode" label="科目编码" width="120" />
          <el-table-column prop="accountName" label="科目名称" min-width="150" />
          <el-table-column prop="amount" label="金额" width="130" sortable />
          <el-table-column prop="cashFlowItem" label="现金流量项目" min-width="180" />
          <el-table-column prop="sourcePurchaseOrderNo" label="来源采购订单" min-width="150" />
          <el-table-column prop="sourceReceiveNo" label="来源收货单" min-width="150" />
          <el-table-column prop="sourceInspectionNo" label="来源检验单" min-width="150" />
          <el-table-column prop="sourceInventoryTransactionNo" label="来源库存流水" min-width="160" />
          <el-table-column prop="rootRequestNo" label="原始请购单" min-width="150" />
          <el-table-column prop="remark" label="备注" min-width="260" fixed="right" />
        </el-table>
      </el-card>

      <el-card shadow="never">
        <template #header><h2>风险检查项</h2></template>
        <el-table :data="detail.riskItems || []" border stripe height="360">
          <el-table-column type="index" label="序号" width="70" fixed="left" />
          <el-table-column prop="itemName" label="检查项" min-width="190" />
          <el-table-column prop="result" label="结果" width="120">
            <template #default="{ row }"><el-tag :type="riskItemType(row.level)">{{ riskItemLabel(row.result) }}</el-tag></template>
          </el-table-column>
          <el-table-column prop="message" label="说明" min-width="420" />
          <el-table-column prop="level" label="级别" width="120" fixed="right">
            <template #default="{ row }">{{ riskItemLabel(row.level) }}</template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-card shadow="never">
        <template #header><h2>操作日志</h2></template>
        <div class="source-chain">
          <article v-for="item in detail.operationLogs || []" :key="item.id || item.time || item.action">
            <span>{{ item.time || item.createdAt || '-' }}</span>
            <strong>{{ item.action || item.detail || '-' }}</strong>
          </article>
          <article v-if="!(detail.operationLogs || []).length">
            <span>暂无单据内日志</span>
            <strong>系统操作日志已保留在全局日志中。</strong>
          </article>
        </div>
      </el-card>
    </section>

    <section v-else class="operation-shell">
      <section class="plain-flow-guide">
        <strong>正式付款凭证边界</strong>
        <div class="plain-flow-grid">
          <span><b>来源</b>只允许从“付款凭证复核通过”的记录生成。</span>
          <span><b>生成</b>只生成正式付款凭证对象，不直接过账。</span>
          <span><b>状态</b>生成后为未过账、未写总账、未核销。</span>
          <span><b>后续</b>过账前评审、总账写入、付款核销均为独立阶段。</span>
        </div>
      </section>

      <el-card shadow="never">
        <template #header>
          <div class="card-header">
            <div>
              <h2>来源付款凭证复核区</h2>
              <span>只允许从“复核通过”的付款凭证复核生成正式付款凭证对象。</span>
            </div>
            <div class="button-row">
              <el-button @click="refresh">刷新来源</el-button>
              <el-button @click="router.push('/finance/payment-voucher-reviews')">查看付款凭证复核</el-button>
            </div>
          </div>
        </template>
        <div class="batch-bar">
          <span>已选择 {{ selectedSourceRows.length }} 条</span>
          <span class="batch-action-title">当前模块操作（生成正式凭证对象）</span>
          <span class="batch-action-tip">只生成正式付款凭证对象，不过账、不写总账、不核销。</span>
          <el-button type="primary" size="small" :disabled="!sourceIds.length" @click="handleBatchCreate">批量生成正式付款凭证</el-button>
        </div>
        <BatchResult v-if="sourceBatchResult" :result="sourceBatchResult" :type="batchResultType(sourceBatchResult)" @close="sourceBatchResult = null" />
        <BusinessTableScrollContainer acceptance-id="business-table-scroll-formal-payment-voucher-source" page-id="formal-payment-voucher" table-id="formal-payment-voucher-source" min-width="1900px">
        <el-table ref="sourceTableRef" :data="filteredSources" border stripe height="420" scrollbar-always-on @selection-change="selectedSourceRows = $event">
          <el-table-column type="selection" width="48" fixed="left" class-name="business-table-selection-column" header-class-name="business-table-selection-column" />
          <el-table-column type="index" label="序号" width="70" fixed="left" class-name="pce-fixed-index-column" header-class-name="pce-fixed-index-column" />
          <el-table-column prop="voucherReviewNo" label="付款凭证复核单号" min-width="180" sortable />
          <el-table-column prop="sourceVoucherDraftNo" label="来源付款凭证草稿" min-width="180" />
          <el-table-column prop="supplierName" label="供应商" min-width="150" />
          <el-table-column prop="accountingPeriod" label="会计期间" width="120" />
          <el-table-column prop="debitAmount" label="借方金额" width="130" sortable />
          <el-table-column prop="creditAmount" label="贷方金额" width="130" sortable />
          <el-table-column prop="differenceAmount" label="差异金额" width="130" />
          <el-table-column prop="voucherReviewStatus" label="复核状态" width="130">
            <template #default="{ row }"><el-tag :type="row.voucherReviewStatus === 'passed' ? 'success' : 'info'">{{ row.voucherReviewStatus === 'passed' ? '复核通过' : row.voucherReviewStatus }}</el-tag></template>
          </el-table-column>
          <el-table-column label="正式凭证" width="170">
            <template #default="{ row }"><el-tag :type="row.formalVoucherGenerated ? 'success' : (row.canGenerateFormalVoucher ? 'primary' : 'info')">{{ row.formalVoucherGenerated ? '已生成正式付款凭证' : (row.canGenerateFormalVoucher ? '可生成正式付款凭证' : '暂不可生成') }}</el-tag></template>
          </el-table-column>
          <el-table-column prop="disabledReason" label="限制原因" min-width="280" />
          <el-table-column label="操作" fixed="right" :width="sourceActionColumnWidth" class-name="payment-fixed-action-column" header-class-name="payment-fixed-action-column">
            <template #default="{ row }">
              <div class="app-action-cell">
                <el-button v-if="row.formalVoucherGenerated" class="app-action-button-lg" size="small" @click="router.push(`/finance/formal-payment-voucher/${row.targetFormalVoucherId}`)">查看正式付款凭证</el-button>
                <el-button v-else class="app-action-button-lg app-next-action-button" size="small" type="primary" :disabled="!row.canGenerateFormalVoucher" @click="handleCreate(row)">生成正式付款凭证<span class="app-next-action-badge">下一步</span></el-button>
                <el-button class="app-action-button-lg" size="small" @click="router.push(`/finance/payment-voucher-review/${row.id}`)">查看付款凭证复核</el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
        </BusinessTableScrollContainer>
      </el-card>

      <el-card shadow="never">
        <template #header>
          <div class="card-header">
            <div>
              <h2>正式付款凭证列表</h2>
              <span>正式凭证生成后仍需后续过账前评审，本页不写总账、不做付款核销。</span>
            </div>
            <div class="button-row">
              <el-button @click="quickSearchOpen = !quickSearchOpen">{{ quickSearchOpen ? '收起快速搜索' : '展开快速搜索' }}</el-button>
              <el-button data-acceptance-id="list-advanced-filter-toggle" data-pce-filter-toggle-for="formal-payment-voucher-main" :aria-expanded="String(advancedFilterOpen)" @click="advancedFilterOpen = !advancedFilterOpen">{{ advancedFilterOpen ? '收起高级筛选' : '展开高级筛选' }}</el-button>
              <el-button @click="clearSort">清除排序</el-button>
              <el-button data-acceptance-id="list-clear-filter-button" @click="resetFilters">重置</el-button>
            </div>
          </div>
        </template>

        <section v-if="quickSearchOpen" class="filter-line">
          <label>快速搜索<input v-model="quickSearch" placeholder="正式凭证号 / 来源复核号 / 供应商 / 状态" /></label>
        </section>

        <section v-if="advancedFilterOpen" class="filter-grid advanced-filter-panel" data-acceptance-id="list-advanced-filter-panel" data-pce-filter-for="formal-payment-voucher-main">
          <label>正式凭证号<PceResultFilterSelect v-model="filters.formalVoucherNo" :options="formalVoucherNoOptions" /></label>
          <label>来源付款凭证复核号<PceResultFilterSelect v-model="filters.sourceVoucherReviewNo" :options="sourceReviewNoOptions" /></label>
          <label>供应商<PceResultFilterSelect v-model="filters.supplierName" :options="formalSupplierOptions" /></label>
          <label>凭证日期起<input v-model="filters.voucherStart" type="date" /></label>
          <label>凭证日期止<input v-model="filters.voucherEnd" type="date" /></label>
          <label>会计期间<PceResultFilterSelect v-model="filters.accountingPeriod" :options="formalPeriodOptions" /></label>
          <label>借方金额下限<input v-model="filters.debitMin" type="number" /></label>
          <label>借方金额上限<input v-model="filters.debitMax" type="number" /></label>
          <label>贷方金额下限<input v-model="filters.creditMin" type="number" /></label>
          <label>贷方金额上限<input v-model="filters.creditMax" type="number" /></label>
          <label>正式凭证状态<select v-model="filters.formalVoucherStatus"><option value="">全部</option><option value="generated">正式付款凭证已生成</option><option value="cancelled">已取消</option></select></label>
          <label>过账状态<select v-model="filters.postingStatus"><option value="">全部</option><option value="unposted">未过账</option><option value="posting_ready">可过账</option><option value="posting_blocked">过账阻断</option><option value="posted">已过账</option></select></label>
          <label>总账状态<select v-model="filters.ledgerStatus"><option value="">全部</option><option value="notWritten">未写总账</option></select></label>
          <label>核销状态<select v-model="filters.paymentWriteOffStatus"><option value="">全部</option><option value="notWrittenOff">未核销</option></select></label>
          <label>风险等级<select v-model="filters.riskLevel"><option value="">全部</option><option value="low">低风险</option><option value="warning">有警告</option><option value="blocked">阻断</option></select></label>
          <label>是否已过账<select v-model="filters.posted"><option value="">全部</option><option value="yes">是</option><option value="no">否</option></select></label>
          <label>是否已写总账<select v-model="filters.ledgerWritten"><option value="">全部</option><option value="yes">是</option><option value="no">否</option></select></label>
          <label>是否已核销<select v-model="filters.writtenOff"><option value="">全部</option><option value="yes">是</option><option value="no">否</option></select></label>
        </section>

        <div class="batch-bar">
          <span>已选择 {{ selectedVoucherRows.length }} 条</span>
          <span class="sort-help">{{ sortText }}</span>
          <span class="batch-action-title">当前模块操作（只修改正式凭证对象状态）</span>
          <span class="batch-action-tip">取消正式凭证不会过账、不会写总账、不会核销。</span>
          <el-button size="small" type="danger" :disabled="!voucherIds.length" @click="handleBatchCancel">批量取消正式付款凭证</el-button>
        </div>
        <BatchResult v-if="voucherBatchResult" :result="voucherBatchResult" :type="batchResultType(voucherBatchResult)" @close="voucherBatchResult = null" />

        <BusinessTableScrollContainer acceptance-id="business-table-scroll-formal-payment-voucher-main" page-id="formal-payment-voucher" table-id="formal-payment-voucher-main" min-width="5200px">
        <el-table ref="voucherTableRef" :data="sortedVouchers" border stripe height="520" scrollbar-always-on @selection-change="selectedVoucherRows = $event" @sort-change="handleSortChange">
          <el-table-column type="selection" width="48" fixed="left" class-name="business-table-selection-column" header-class-name="business-table-selection-column" />
          <el-table-column type="index" label="序号" width="70" fixed="left" class-name="pce-fixed-index-column" header-class-name="pce-fixed-index-column" />
          <el-table-column prop="formalVoucherNo" label="正式凭证号" min-width="170" sortable="custom" />
          <el-table-column prop="sourceVoucherReviewNo" label="来源付款凭证复核" min-width="180" sortable="custom" />
          <el-table-column prop="supplierName" label="供应商" min-width="150" sortable="custom" />
          <el-table-column prop="voucherDate" label="凭证日期" width="130" sortable="custom" />
          <el-table-column prop="accountingPeriod" label="会计期间" width="120" />
          <el-table-column prop="debitAmount" label="借方金额" width="130" sortable="custom" />
          <el-table-column prop="creditAmount" label="贷方金额" width="130" sortable="custom" />
          <el-table-column prop="differenceAmount" label="差异金额" width="130" />
          <el-table-column prop="formalVoucherStatus" label="正式凭证状态" width="150">
            <template #default="{ row }"><el-tag :type="formalStatusType(row.formalVoucherStatus)">{{ formalStatusLabel(row.formalVoucherStatus) }}</el-tag></template>
          </el-table-column>
          <el-table-column prop="postingPreReviewStatus" label="过账前评审" width="150">
            <template #default="{ row }"><el-tag :type="postingPreReviewStatusType(row.postingPreReviewStatus)">{{ postingPreReviewStatusLabel(row.postingPreReviewStatus) }}</el-tag></template>
          </el-table-column>
          <el-table-column label="阻断 / 提醒" width="120">
            <template #default="{ row }">{{ row.postingPreReviewBlockedCount || 0 }} / {{ row.postingPreReviewWarningCount || 0 }}</template>
          </el-table-column>
          <el-table-column prop="postingReadinessStatus" label="凭证过账状态" width="150">
            <template #default="{ row }"><el-tag :type="postingReadinessType(row.postingReadinessStatus)">{{ postingStatusText(row) }}</el-tag></template>
          </el-table-column>
          <el-table-column label="可过账" width="100">
            <template #default="{ row }">{{ row.postingReady ? '是' : '否' }}</template>
          </el-table-column>
          <el-table-column label="过账阻断 / 提醒" width="130">
            <template #default="{ row }">{{ row.postingBlockedCount || 0 }} / {{ row.postingWarningCount || 0 }}</template>
          </el-table-column>
          <el-table-column prop="postingActionStatus" label="模拟过账状态" width="140">
            <template #default="{ row }"><el-tag :type="postingActionStatusType(row.postingActionStatus)">{{ row.postingActionStatusText || '未模拟' }}</el-tag></template>
          </el-table-column>
          <el-table-column prop="formalPostingStatus" label="正式过账评审" width="150">
            <template #default="{ row }"><el-tag :type="formalPostingStatusType(row.formalPostingStatus)">{{ row.formalPostingStatusText || formalPostingStatusLabel(row.formalPostingStatus) }}</el-tag></template>
          </el-table-column>
          <el-table-column label="正式过账状态机阶段" width="180">
            <template #default="{ row }"><el-tag :type="formalPostingFlowType(formalPostingFlowSummary(row).formalPostingFlowStatus)">{{ formalPostingFlowSummary(row).formalPostingFlowStatusText }}</el-tag></template>
          </el-table-column>
          <el-table-column label="状态机下一步" width="130">
            <template #default="{ row }">{{ formalPostingFlowSummary(row).formalPostingFlowCanMoveNext ? '入口就绪' : '暂不可进入' }}</template>
          </el-table-column>
          <el-table-column label="预执行检查状态" width="160">
            <template #default="{ row }"><el-tag :type="formalPostingPreExecuteType(formalPostingPreExecuteSummary(row).formalPostingPreExecuteStatus)">{{ formalPostingPreExecuteSummary(row).formalPostingPreExecuteStatusText }}</el-tag></template>
          </el-table-column>
          <el-table-column label="预执行阻断 / 提醒" width="150">
            <template #default="{ row }">{{ formalPostingPreExecuteSummary(row).formalPostingPreExecuteBlockedReasons.length }} / {{ formalPostingPreExecuteSummary(row).formalPostingPreExecuteWarnings.length }}</template>
          </el-table-column>
          <el-table-column label="确认前锁定状态" width="170">
            <template #default="{ row }"><el-tag :type="formalPostingLockType(formalPostingLockSummary(row).formalPostingLockStatus)">{{ formalPostingLockSummary(row).formalPostingLockStatusText }}</el-tag></template>
          </el-table-column>
          <el-table-column label="锁定阻断 / 提醒" width="150">
            <template #default="{ row }">{{ formalPostingLockSummary(row).formalPostingLockBlockedReasons.length }} / {{ formalPostingLockSummary(row).formalPostingLockWarnings.length }}</template>
          </el-table-column>
          <el-table-column label="最终确认状态" width="170">
            <template #default="{ row }"><el-tag :type="formalPostingConfirmType(formalPostingConfirmSummary(row).formalPostingConfirmStatus)">{{ formalPostingConfirmSummary(row).formalPostingConfirmStatusText }}</el-tag></template>
          </el-table-column>
          <el-table-column label="最终确认阻断 / 提醒" width="160">
            <template #default="{ row }">{{ formalPostingConfirmSummary(row).formalPostingConfirmBlockedReasons.length }} / {{ formalPostingConfirmSummary(row).formalPostingConfirmWarnings.length }}</template>
          </el-table-column>
          <el-table-column label="模拟诊断" width="190">
            <template #default="{ row }"><el-tag :type="diagnosticStatusType(row)">{{ postingDiagnosticListLabel(row) }}</el-tag></template>
          </el-table-column>
          <el-table-column label="正式阻断 / 提醒" width="140">
            <template #default="{ row }">{{ row.formalPostingBlockedCount || 0 }} / {{ row.formalPostingWarningCount || 0 }}</template>
          </el-table-column>
          <el-table-column prop="postingStatus" label="过账状态" width="120">
            <template #default="{ row }">{{ postingStatusLabel(row.postingStatus) }}</template>
          </el-table-column>
          <el-table-column prop="ledgerStatus" label="总账状态" width="120">
            <template #default="{ row }">{{ ledgerStatusLabel(row.ledgerStatus) }}</template>
          </el-table-column>
          <el-table-column prop="paymentWriteOffStatus" label="核销状态" width="120">
            <template #default="{ row }">{{ writeOffStatusLabel(row.paymentWriteOffStatus) }}</template>
          </el-table-column>
          <el-table-column prop="riskLevel" label="风险等级" width="120">
            <template #default="{ row }"><el-tag :type="riskLevelType(row.riskLevel)">{{ riskLevelLabel(row.riskLevel) }}</el-tag></template>
          </el-table-column>
          <el-table-column label="操作" fixed="right" :width="voucherActionColumnWidth" class-name="payment-fixed-action-column" header-class-name="payment-fixed-action-column">
            <template #default="{ row }">
              <div class="app-action-cell">
                <el-button class="app-action-button-sm" size="small" @click="router.push(`/finance/formal-payment-voucher/${row.id}`)">查看详情</el-button>
                <el-button v-if="row.formalVoucherStatus === 'generated'" class="app-action-button-md" size="small" type="danger" @click="handleCancel(row)">取消正式凭证</el-button>
                <el-button v-if="row.formalVoucherStatus === 'generated'" class="app-action-button-lg" size="small" disabled :title="postingPreReviewButtonTitle(row)">{{ postingPreReviewButtonText(row) }}</el-button>
                <el-button v-if="row.formalVoucherStatus === 'generated'" class="app-action-button-md" size="small" type="warning" :disabled="!canSimulatePosting(row)" :title="simulatePostingButtonTitle(row)" @click="handleSimulatePosting(row)">模拟过账</el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
        </BusinessTableScrollContainer>
      </el-card>
    </section>
  </main>
</template>

<script setup>
import { computed, defineComponent, h, reactive, ref, watch } from 'vue'
import { ElMessageBox } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import BusinessTableScrollContainer from '../components/BusinessTableScrollContainer.vue'
import PceResultFilterSelect from '../components/PceResultFilterSelect.vue'
import {
  batchCancelFormalVouchers,
  batchCreateFormalVouchersFromVoucherReviews,
  cancelFormalVoucher,
  createFormalVoucherFromVoucherReview,
  getFormalPaymentVoucherById,
  getFormalVoucherRiskLevelLabel,
  getFormalVoucherRiskLevelType,
  getFormalVoucherSourcesFromVoucherReviews,
  getFormalVoucherStatusLabel,
  getFormalVoucherStatusType,
  getLedgerStatusLabel,
  getPaymentWriteOffStatusLabel,
  getPostingStatusLabel,
  listFormalPaymentVouchers,
  simulateFormalVoucherPosting,
} from '../finance/formalPaymentVoucherStore.js'
import { getScmDisplayName, getScmState } from '../scm/scmStore.js'
import { getActionColumnWidthForRows } from '../runtime/tableActionColumnEngine.js'
import { sortRecords } from '../runtime/tableSortEngine.js'

const BatchResult = defineComponent({
  props: { result: { type: Object, required: true }, type: { type: String, default: 'success' } },
  emits: ['close'],
  setup(props, { emit }) {
    return () => h('div', { class: ['batch-result', props.type] }, [
      h('button', { type: 'button', onClick: () => emit('close') }, '关闭'),
      h('strong', props.result.operationName || '批量操作完成'),
      h('span', `已选择：${props.result.total} 条`),
      h('span', `成功：${props.result.successCount} 条`),
      h('span', `已达成：${props.result.alreadyDoneCount} 条`),
      h('span', `失败 / 跳过：${props.result.failedCount} 条`),
      props.result.failedReason?.length ? h('ol', props.result.failedReason.map((reason) => h('li', { key: reason }, reason))) : null,
      h('span', `下一步建议：${props.result.nextSuggestion || '正式凭证对象仍未过账、未写总账、未核销。'}`),
      h('span', '边界说明：本批量结果不代表已过账，不写总账，不做付款核销，不生成银行流水。'),
    ])
  },
})

const route = useRoute()
const router = useRouter()
const sources = ref([])
const vouchers = ref([])
const selectedSourceRows = ref([])
const selectedVoucherRows = ref([])
const sourceTableRef = ref(null)
const voucherTableRef = ref(null)
const sourceBatchResult = ref(null)
const voucherBatchResult = ref(null)
const quickSearchOpen = ref(false)
const advancedFilterOpen = ref(false)
const quickSearch = ref('')
const sortState = ref({ key: '', direction: 'asc' })
const message = ref('')
const messageType = ref('success')
const filters = reactive(defaultFilters())

const FORMAL_POSTING_FLOW_STEPS = [
  { status: 'not_started', text: '未进入正式过账', description: '正式凭证不存在、已取消，或尚未满足正式过账入口条件。' },
  { status: 'entry_ready', text: '正式过账入口就绪', description: '正式凭证已生成，过账前评审、模拟过账和最终设计评审均满足入口条件。' },
  { status: 'confirmation_pending', text: '待正式过账确认', description: '未来状态，本轮只展示，不推进。' },
  { status: 'pre_execute_checked', text: '正式过账预执行已检查', description: '未来状态，本轮只展示，不执行预执行。' },
  { status: 'locked_for_posting', text: '正式过账前锁定', description: '未来状态，本轮不锁定凭证。' },
  { status: 'posted', text: '已正式过账', description: '未来状态，本轮绝不写入 posted。' },
]

const formalPostingFlowFutureFields = [
  'formalPostingFlowStatus：正式过账状态机阶段。',
  'formalPostingFlowStatusText：正式过账状态机中文阶段。',
  'formalPostingFlowStepIndex：状态机阶段序号。',
  'formalPostingFlowSteps：状态机阶段清单。',
  'formalPostingFlowCanMoveNext：是否具备进入下一阶段的条件。',
  'formalPostingFlowBlockedReasons：状态机阻断原因。',
  'formalPostingFlowWarnings：状态机提醒项。',
  'formalPostingFlowConclusion：状态机只读结论。',
]

const FORMAL_POSTING_PERMISSION_PLACEHOLDER_PASSED = true

const seedDataPlanDomains = [
  { key: 'chartOfAccounts', purpose: '会计科目体系', validation: '总账分录借贷科目、资产负债表和科目余额表校验' },
  { key: 'openingBalances', purpose: '期初余额', validation: '借贷平衡、总账余额和报表起点校验' },
  { key: 'bankAccounts', purpose: '资金账户和银行账户', validation: '银行存款余额、付款、银行流水和自动对账校验' },
  { key: 'suppliers', purpose: '供应商主数据', validation: '应付账款、付款核销和供应商往来校验' },
  { key: 'supplierBalances', purpose: '供应商往来期初', validation: '应付未付、预付款、部分付款、已结清和异常挂账校验' },
  { key: 'inventoryItems', purpose: '物料主数据', validation: '库存数量、库存金额和采购入库结存校验' },
  { key: 'warehouses', purpose: '仓库主数据', validation: '原材料仓、半成品仓、成品仓和不良品仓结存校验' },
  { key: 'inventoryOpeningBalances', purpose: '库存期初数量和金额', validation: '采购入库、出库和库存结存校验' },
  { key: 'p2pScenarioSamples', purpose: '采购到付款场景样本链', validation: '请购到正式付款凭证、模拟过账和未来正式过账链路校验' },
  { key: 'reportCheckSamples', purpose: '报表验证样本', validation: '资产负债表、科目余额表、银行余额表、供应商往来表和库存结存表校验' },
]

const seedDataPlanIsolationRules = [
  '所有基础验证数据必须带 seed / demo / sandbox 标记。',
  '初始化工具必须使用单独 namespace，不与用户真实业务数据混合。',
  '后续清除工具只能清除 seed / demo / sandbox 数据，不得删除用户手工数据。',
  '每条验证数据必须能追踪到 scenarioId，报表验证必须说明数据来源。',
  'V1.13.16 只做设计，不生成数据，不写 localStorage。',
]

const seedDataPlanNextVersions = [
  { version: 'V1.13.16', name: '基础验证数据体系设计' },
  { version: 'V1.13.17', name: '基础验证数据初始化工具' },
  { version: 'V1.13.18', name: '借贷平衡与余额验证器' },
  { version: 'V1.13.19', name: '真实总账写入前复核' },
]

const seedDataInitNamespaces = [
  { namespace: 'seed:p2p:v1.13', scope: '采购到付款基础验证种子数据', rule: '只允许未来初始化工具写入带 seed 标记的数据' },
  { namespace: 'demo:p2p:v1.13', scope: '演示链路验证数据', rule: '只服务演示，不与用户正式业务数据混用' },
  { namespace: 'sandbox:p2p:v1.13', scope: '沙箱验证数据', rule: '只用于后续借贷平衡、余额和报表校验' },
]

const seedDataInitPreviewDomains = seedDataPlanDomains.map((domain) => ({
  ...domain,
  action: '未来仅在用户确认后生成隔离验证样本',
  plannedCount: '待 V1.13.17.1 细化',
}))

const seedDataInitSafetyRules = [
  '本轮只做初始化工具设计，不初始化基础数据。',
  '本轮所有按钮不得写 localStorage，不得覆盖或清空 localStorage。',
  '未来初始化数据必须带 namespace、scenarioId、dataMode 和 createdByTool 标记。',
  '未来清除工具只能清除 seed / demo / sandbox 数据，不能删除用户手工或正式业务数据。',
  '未来初始化前必须先预览将写入的数据域、数量、namespace 和影响范围。',
  '未来初始化后必须输出诊断 JSON，并可与借贷平衡与余额验证器衔接。',
  '本轮不写入 chartOfAccounts、openingBalances、bankAccounts、suppliers、supplierBalances、inventoryItems、warehouses、inventoryOpeningBalances、p2pScenarioSamples、reportCheckSamples。',
]

const balanceValidatorDesignChecks = [
  '借贷平衡验证',
  '总账余额验证',
  '银行余额验证',
  '供应商余额验证',
  '库存余额验证',
  '报表数据验证',
]

const ledgerPostingReviewDesignChecks = [
  '财务基础数据检查',
  '借贷平衡检查',
  '科目完整性检查',
  '会计期间检查',
  '权限检查',
  '审计检查',
  '总账写入结构检查',
  '回滚能力检查',
]

const detail = computed(() => route.params.id ? getFormalPaymentVoucherById(route.params.id) : null)
const sourceIds = computed(() => selectedSourceRows.value.map((row) => row.id).filter(Boolean))
const voucherIds = computed(() => selectedVoucherRows.value.map((row) => row.id).filter(Boolean))
const filterSuggestions = computed(() => ({
  formalVoucherNo: uniqueValues(vouchers.value.map((row) => row.formalVoucherNo)),
  sourceVoucherReviewNo: uniqueValues(vouchers.value.map((row) => row.sourceVoucherReviewNo)),
  supplierName: uniqueValues(vouchers.value.map((row) => row.supplierName)),
  accountingPeriod: uniqueValues(vouchers.value.map((row) => row.accountingPeriod)),
}))
const seedDataInitToolSummary = computed(() => buildSeedDataInitToolSummary())
const balanceValidatorSummary = computed(() => buildBalanceValidatorSummary())
const ledgerPostingReviewSummary = computed(() => buildLedgerPostingReviewSummary())
const filteredSources = computed(() => {
  if (!route.query.sourceVoucherReviewId) return sources.value
  return sources.value.filter((row) => String(row.id) === String(route.query.sourceVoucherReviewId))
})
const filteredVouchers = computed(() => vouchers.value.filter((row) => {
  const haystack = [
    row.formalVoucherNo,
    row.sourceVoucherReviewNo,
    row.supplierName,
    row.accountingPeriod,
    formalStatusLabel(row.formalVoucherStatus),
    postingStatusLabel(row.postingStatus),
    ledgerStatusLabel(row.ledgerStatus),
    writeOffStatusLabel(row.paymentWriteOffStatus),
    riskLevelLabel(row.riskLevel),
    postingPreReviewStatusLabel(row.postingPreReviewStatus),
    row.postingPreReviewConclusion,
    postingStatusText(row),
    row.postingActionStatusText,
    row.postingActionConclusion,
    row.postingReadinessConclusion,
    row.formalPostingStatusText,
    row.formalPostingReviewConclusion,
    postingDiagnosticListLabel(row),
    postingDiagnosticConclusion(row),
    formalPostingFlowSummary(row).formalPostingFlowStatusText,
    formalPostingFlowSummary(row).formalPostingFlowConclusion,
    ...(formalPostingFlowSummary(row).formalPostingFlowBlockedReasons || []),
    ...(formalPostingFlowSummary(row).formalPostingFlowWarnings || []),
    formalPostingPreExecuteSummary(row).formalPostingPreExecuteStatusText,
    formalPostingPreExecuteSummary(row).formalPostingPreExecuteConclusion,
    ...(formalPostingPreExecuteSummary(row).formalPostingPreExecuteBlockedReasons || []),
    ...(formalPostingPreExecuteSummary(row).formalPostingPreExecuteWarnings || []),
    formalPostingLockSummary(row).formalPostingLockStatusText,
    formalPostingLockSummary(row).formalPostingLockConclusion,
    ...(formalPostingLockSummary(row).formalPostingLockBlockedReasons || []),
    ...(formalPostingLockSummary(row).formalPostingLockWarnings || []),
    formalPostingConfirmSummary(row).formalPostingConfirmStatusText,
    formalPostingConfirmSummary(row).formalPostingConfirmConclusion,
    ...(formalPostingConfirmSummary(row).formalPostingConfirmBlockedReasons || []),
    ...(formalPostingConfirmSummary(row).formalPostingConfirmWarnings || []),
    ...(row.postingBlockedReasons || []),
    ...(row.postingWarnings || []),
    ...(row.formalPostingBlockedReasons || []),
    ...(row.formalPostingWarnings || []),
  ].join(' ').toLowerCase()
  return (!quickSearch.value || haystack.includes(quickSearch.value.trim().toLowerCase()))
    && includesText(row.formalVoucherNo, filters.formalVoucherNo)
    && includesText(row.sourceVoucherReviewNo, filters.sourceVoucherReviewNo)
    && includesText(row.supplierName, filters.supplierName)
    && inDateRange(row.voucherDate, filters.voucherStart, filters.voucherEnd)
    && includesText(row.accountingPeriod, filters.accountingPeriod)
    && inAmountRange(row.debitAmount, filters.debitMin, filters.debitMax)
    && inAmountRange(row.creditAmount, filters.creditMin, filters.creditMax)
    && (!filters.formalVoucherStatus || row.formalVoucherStatus === filters.formalVoucherStatus)
    && (!filters.postingStatus || row.postingStatus === filters.postingStatus)
    && (!filters.ledgerStatus || row.ledgerStatus === filters.ledgerStatus)
    && (!filters.paymentWriteOffStatus || row.paymentWriteOffStatus === filters.paymentWriteOffStatus)
    && (!filters.riskLevel || row.riskLevel === filters.riskLevel)
    && boolStatus(row.postingStatus === 'posted', filters.posted)
    && boolStatus(row.ledgerStatus === 'written', filters.ledgerWritten)
    && boolStatus(row.paymentWriteOffStatus === 'writtenOff', filters.writtenOff)
}))
const sortColumns = [
  { key: 'formalVoucherNo', sortType: 'string' },
  { key: 'sourceVoucherReviewNo', sortType: 'string' },
  { key: 'supplierName', sortType: 'string' },
  { key: 'voucherDate', sortType: 'date' },
  { key: 'debitAmount', sortType: 'amount' },
  { key: 'creditAmount', sortType: 'amount' },
]
const sortedVouchers = computed(() => sortRecords(filteredVouchers.value, sortState.value, sortColumns))
const sortText = computed(() => sortState.value.key ? `当前排序：${sortState.value.key} / ${sortState.value.direction === 'desc' ? '降序' : '升序'}` : '排序：点击表头可排序，点击清除排序恢复默认顺序。')
const sourceActionColumnWidth = computed(() => getActionColumnWidthForRows(filteredSources.value, sourceActions, ['生成正式付款凭证', '查看正式付款凭证', '查看付款凭证复核']))
const voucherActionColumnWidth = computed(() => getActionColumnWidthForRows(sortedVouchers.value, voucherActions, ['查看详情', '取消正式凭证', '可进入凭证过账', '查看过账条件', '查看正式过账设计', '正式过账入口', '模拟过账']))
const detailFields = computed(() => detail.value ? [
  { label: '正式凭证号', value: detail.value.formalVoucherNo },
  { label: '来源付款凭证复核', value: detail.value.sourceVoucherReviewNo || '-' },
  { label: '供应商', value: detail.value.supplierName || '-' },
  { label: '凭证日期', value: detail.value.voucherDate || '-' },
  { label: '会计期间', value: detail.value.accountingPeriod || '-' },
  { label: '借方金额', value: amountText(detail.value.debitAmount) },
  { label: '贷方金额', value: amountText(detail.value.creditAmount) },
  { label: '差异金额', value: amountText(detail.value.differenceAmount) },
  { label: '正式凭证状态', value: formalStatusLabel(detail.value.formalVoucherStatus) },
  { label: '过账状态', value: postingStatusLabel(detail.value.postingStatus) },
  { label: '总账状态', value: ledgerStatusLabel(detail.value.ledgerStatus) },
  { label: '核销状态', value: writeOffStatusLabel(detail.value.paymentWriteOffStatus) },
  { label: '过账前评审状态', value: postingPreReviewStatusLabel(detail.value.postingPreReviewStatus) },
  { label: '风险项数量', value: detail.value.postingPreReviewRiskCount || 0 },
  { label: '阻断项数量', value: detail.value.postingPreReviewBlockedCount || 0 },
  { label: '提醒项数量', value: detail.value.postingPreReviewWarningCount || 0 },
  { label: '后续过账阶段', value: detail.value.postingPreReviewCanEnterPosting ? '可进入后续过账阶段' : '暂不可进入后续过账阶段' },
  { label: '凭证过账状态', value: postingStatusText(detail.value) },
  { label: '是否可过账', value: detail.value.postingReady ? '可进入凭证过账' : '不可过账' },
  { label: '过账阻断原因数量', value: detail.value.postingBlockedCount || 0 },
  { label: '过账提醒数量', value: detail.value.postingWarningCount || 0 },
  { label: '模拟过账状态', value: detail.value.postingActionStatusText || '未模拟' },
  { label: '模拟过账时间', value: formatDateTime(detail.value.postingSimulatedAt) },
  { label: '正式过账评审状态', value: detail.value.formalPostingStatusText || formalPostingStatusLabel(detail.value.formalPostingStatus) },
  { label: '未来正式过账条件', value: detail.value.formalPostingReady ? '具备未来正式过账条件' : '不可正式过账' },
  { label: '正式过账阻断数量', value: detail.value.formalPostingBlockedCount || 0 },
  { label: '正式过账提醒数量', value: detail.value.formalPostingWarningCount || 0 },
  { label: '正式过账时间', value: formatDateTime(detail.value.formalPostedAt) },
  { label: '总账凭证号', value: detail.value.ledgerEntryNo || '-' },
  { label: '风险等级', value: riskLevelLabel(detail.value.riskLevel) },
  { label: '生成操作人', value: detail.value.generatedBy || '-' },
  { label: '生成时间', value: formatDateTime(detail.value.generatedAt) },
] : [])
const postingDiagnosticFields = computed(() => detail.value ? [
  { label: '凭证 id', value: detail.value.id || '-' },
  { label: '凭证号', value: detail.value.formalVoucherNo || '-' },
  { label: 'postingActionStatus', value: detail.value.postingActionStatus || '-' },
  { label: 'postingActionStatusText', value: detail.value.postingActionStatusText || '-' },
  { label: 'postingSimulated', value: booleanText(detail.value.postingSimulated) },
  { label: 'postingSimulatedAt', value: formatDateTime(detail.value.postingSimulatedAt) },
  { label: 'formalPostingStatus', value: detail.value.formalPostingStatus || '-' },
  { label: 'formalPostingStatusText', value: detail.value.formalPostingStatusText || '-' },
  { label: 'formalPostingReady', value: booleanText(detail.value.formalPostingReady) },
  { label: 'formalPostingBlocked', value: booleanText(detail.value.formalPostingBlocked) },
  { label: 'formalPostingBlockedReasons', value: listText(detail.value.formalPostingBlockedReasons) },
  { label: 'formalPostingWarnings', value: listText(detail.value.formalPostingWarnings) },
  { label: 'formalPostingReviewConclusion', value: detail.value.formalPostingReviewConclusion || '-' },
] : [])
const sourceChain = computed(() => detail.value ? [
  { label: '付款凭证复核', value: detail.value.sourceVoucherReviewNo },
  { label: '付款凭证草稿', value: detail.value.sourceVoucherDraftNo },
  { label: '付款记录复核', value: detail.value.sourcePaymentRecordReviewNo },
  { label: '付款执行草稿', value: detail.value.sourcePaymentExecutionNo },
  { label: '真实付款风险评审', value: detail.value.sourceRiskReviewNo },
  { label: '正式付款单草稿', value: detail.value.sourcePaymentOrderDraftNo },
  { label: '正式付款单预备', value: detail.value.sourcePaymentPrepareNo },
  { label: '供应商付款草稿', value: detail.value.sourcePaymentDraftNo },
  { label: '应付账款草稿', value: detail.value.sourceApDraftNo },
  { label: '发票预备', value: detail.value.sourceInvoicePrepareNo },
  { label: '应付核对', value: detail.value.sourcePayableCheckNo },
  { label: '应付预备', value: detail.value.sourcePayablePrepareNo },
  { label: '库存流水', value: (detail.value.sourceInventoryTransactionNos || []).join('；') },
  { label: '检验单', value: detail.value.sourceInspectionNo },
  { label: '收货单', value: detail.value.sourceReceiveNo },
  { label: '采购订单', value: detail.value.sourcePurchaseOrderNo },
  { label: '原始请购单', value: detail.value.rootRequestNo },
] : [])

function defaultFilters() {
  return {
    formalVoucherNo: '',
    sourceVoucherReviewNo: '',
    supplierName: '',
    voucherStart: '',
    voucherEnd: '',
    accountingPeriod: '',
    debitMin: '',
    debitMax: '',
    creditMin: '',
    creditMax: '',
    formalVoucherStatus: '',
    postingStatus: '',
    ledgerStatus: '',
    paymentWriteOffStatus: '',
    riskLevel: '',
    posted: '',
    ledgerWritten: '',
    writtenOff: '',
  }
}

function refresh() {
  sources.value = getFormalVoucherSourcesFromVoucherReviews()
  vouchers.value = listFormalPaymentVouchers()
}

function notify(text, type = 'success') {
  message.value = text
  messageType.value = type
  window.clearTimeout(notify.timer)
  notify.timer = window.setTimeout(() => { message.value = '' }, 2600)
}

function includesText(value, keyword) {
  return !keyword || String(value || '').toLowerCase().includes(String(keyword).trim().toLowerCase())
}

function inDateRange(value, start, end) {
  if (!start && !end) return true
  if (!value) return false
  return (!start || value >= start) && (!end || value <= end)
}

function inAmountRange(value, min, max) {
  const amount = Number(value || 0)
  return (!min || amount >= Number(min)) && (!max || amount <= Number(max))
}

function boolStatus(value, flag) {
  if (!flag) return true
  return flag === 'yes' ? Boolean(value) : !value
}

function amountText(value) {
  return Number(value || 0).toFixed(2)
}

function formatDateTime(value) {
  if (!value) return '-'
  return String(value).replace('T', ' ').replace(/\.\d{3}Z$/, '').replace(/Z$/, '')
}

function uniqueValues(values = []) {
  return [...new Set(values.map((value) => String(value || '').trim()).filter(Boolean))]
}

function booleanText(value) {
  return value ? 'true' : 'false'
}

function listText(values = []) {
  return Array.isArray(values) && values.length ? values.join('；') : '-'
}

function isPostingSimulationCompleted(row = {}) {
  const actionStatus = String(row.postingActionStatus || '').trim()
  const actionText = String(row.postingActionStatusText || '').trim()
  return actionStatus === 'simulated'
    || row.postingSimulated === true
    || actionText === '已模拟过账'
    || actionText.includes('已模拟过账')
}

function hasSimulationMissingReason(row = {}) {
  return (row.formalPostingBlockedReasons || []).some((reason) => {
    const text = String(reason || '')
    return text.includes('模拟过账尚未完成')
      || text.includes('未完成模拟过账')
      || text.includes('妯℃嫙杩囪处')
  })
}

function hasBankFlow(row = {}) {
  return Boolean(row.bankFlowGenerated || row.bankFlowNo || row.bankTransactionNo || row.bankStatementNo)
}

function hasValidPostingAmount(row = {}) {
  const debitCents = Math.round(Number(row.debitAmount || 0) * 100)
  const creditCents = Math.round(Number(row.creditAmount || 0) * 100)
  const diffCents = Math.round(Number(row.differenceAmount || 0) * 100)
  return debitCents > 0 && creditCents > 0 && debitCents === creditCents && diffCents === 0
}

function hasCompleteFormalPostingSource(row = {}) {
  return Boolean(
    row.sourceVoucherReviewNo
    && row.sourceVoucherDraftNo
    && row.sourcePaymentRecordReviewNo
    && row.sourcePaymentExecutionNo
    && (row.rootRequestNo || row.sourcePurchaseOrderNo)
  )
}

function formalPostingEntryReasons(row = {}) {
  const reasons = []
  if (row.formalVoucherStatus !== 'generated') reasons.push('正式付款凭证状态不是“正式凭证已生成”。')
  if (row.postingStatus !== 'posting_ready') reasons.push('凭证过账准备状态不是“可过账”。')
  if (row.postingReady !== true) reasons.push('postingReady 不是 true。')
  if (row.postingBlocked === true) reasons.push('postingBlocked 仍为 true。')
  if (Number(row.postingPreReviewBlockedCount || 0) > 0 || row.postingPreReviewStatus !== 'passed') reasons.push('过账前评审仍有阻断或未通过。')
  if (!isPostingSimulationCompleted(row)) reasons.push('未完成模拟过账。')
  if (row.formalPostingStatus !== 'ready') reasons.push('正式过账前最终评审不是 ready。')
  if (row.formalPostingReady !== true) reasons.push('formalPostingReady 不是 true。')
  if (row.formalPostingBlocked === true) reasons.push('formalPostingBlocked 仍为 true。')
  if (row.ledgerStatus !== 'notWritten') reasons.push('总账状态不是“未写总账”。')
  if (row.paymentWriteOffStatus !== 'notWrittenOff') reasons.push('核销状态不是“未核销”。')
  if (hasBankFlow(row)) reasons.push('已存在银行流水信息。')
  if (!hasValidPostingAmount(row)) reasons.push('金额异常，借贷金额必须大于 0、借贷平衡且差异为 0。')
  if (!hasCompleteFormalPostingSource(row)) reasons.push('来源链不完整。')
  return reasons
}

function canEnterFormalPosting(row = {}) {
  return formalPostingEntryReasons(row).length === 0
}

function formalPostingEntryButtonText(row = {}) {
  return canEnterFormalPosting(row) ? '正式过账入口' : '查看正式过账条件'
}

function formalPostingEntryTitle(row = {}) {
  const reasons = formalPostingEntryReasons(row)
  if (!reasons.length) return '已满足正式过账入口条件；本轮点击后只显示二次确认与风险提示，不执行正式过账。'
  return `正式过账入口禁用：${reasons.join('；')}`
}

function formalPostingFlowStatusLabel(status) {
  return {
    not_started: '未进入正式过账',
    entry_ready: '正式过账入口就绪',
    confirmation_pending: '待正式过账确认',
    pre_execute_checked: '正式过账预执行已检查',
    locked_for_posting: '正式过账前锁定',
    posted: '已正式过账',
  }[status] || '未进入正式过账'
}

function formalPostingFlowType(status) {
  return {
    not_started: 'info',
    entry_ready: 'success',
    confirmation_pending: 'warning',
    pre_execute_checked: 'warning',
    locked_for_posting: 'warning',
    posted: 'danger',
  }[status] || 'info'
}

function formalPostingFlowSummary(row = {}) {
  const entryReasons = formalPostingEntryReasons(row)
  const isGenerated = row.formalVoucherStatus === 'generated'
  const isEntryReady = isGenerated && entryReasons.length === 0
  const blockedReasons = isEntryReady ? [] : [...entryReasons]
  if (!isGenerated && !blockedReasons.length) {
    blockedReasons.push('正式凭证不存在或已取消，不允许进入正式过账。')
  }
  const status = isEntryReady ? 'entry_ready' : 'not_started'
  const warnings = [
    'confirmation_pending、pre_execute_checked、locked_for_posting、posted 均为未来设计状态，本轮不推进。',
    '状态机预检查只读，不写正式过账日志、不写总账、不核销、不生成银行流水。',
  ]
  return {
    formalPostingFlowStatus: status,
    formalPostingFlowStatusText: formalPostingFlowStatusLabel(status),
    formalPostingFlowStepIndex: isEntryReady ? 1 : 0,
    formalPostingFlowSteps: FORMAL_POSTING_FLOW_STEPS,
    formalPostingFlowCanMoveNext: isEntryReady,
    formalPostingFlowBlockedReasons: [...new Set(blockedReasons)],
    formalPostingFlowWarnings: warnings,
    formalPostingFlowConclusion: isEntryReady
      ? '正式过账入口就绪；本轮只展示状态机草案，不推进到待确认、预执行、锁定或已正式过账。'
      : '尚未满足正式过账入口条件；本轮不推进状态，不写总账、不核销、不生成银行流水。',
  }
}

function formalPostingFlowTitle(row = {}) {
  const summary = formalPostingFlowSummary(row)
  return `${summary.formalPostingFlowStatusText}：${summary.formalPostingFlowConclusion}`
}

function formalPostingPreExecuteStatusLabel(status) {
  return {
    not_checked: '未检查',
    passed: '预执行检查通过',
    blocked: '预执行检查阻断',
    warning: '预执行检查有提醒',
  }[status] || '未检查'
}

function formalPostingPreExecuteType(status) {
  return {
    not_checked: 'info',
    passed: 'success',
    blocked: 'danger',
    warning: 'warning',
  }[status] || 'info'
}

function hasAccountingPeriod(row = {}) {
  return String(row.accountingPeriod || '').trim().length > 0
}

function hasVoucherAccountSubjects(row = {}) {
  return Array.isArray(row.lines)
    && row.lines.length > 0
    && row.lines.every((line) => String(line.accountCode || '').trim() && String(line.accountName || '').trim())
}

function formalPostingPreExecuteSummary(row = {}) {
  const flowSummary = formalPostingFlowSummary(row)
  const blockedReasons = []
  const warnings = []
  const pushBlock = (condition, reason) => { if (condition) blockedReasons.push(reason) }
  const pushWarning = (condition, warning) => { if (condition) warnings.push(warning) }

  pushBlock(!row.id || !row.formalVoucherNo, '正式付款凭证不存在或凭证号缺失。')
  pushBlock(row.formalVoucherStatus !== 'generated', '正式付款凭证状态不是“正式凭证已生成”。')
  pushBlock(row.postingPreReviewStatus !== 'passed' || Number(row.postingPreReviewBlockedCount || 0) > 0, '过账前评审未通过或仍有阻断项。')
  pushBlock(row.postingStatus !== 'posting_ready', '凭证过账准备状态不是“可过账”。')
  pushBlock(row.postingReady !== true, 'postingReady 不是 true。')
  pushBlock(row.postingBlocked === true, 'postingBlocked 仍为 true。')
  pushBlock(!isPostingSimulationCompleted(row), '未完成模拟过账。')
  pushBlock(row.formalPostingStatus !== 'ready', '正式过账前最终评审不是 ready。')
  pushBlock(row.formalPostingReady !== true, 'formalPostingReady 不是 true。')
  pushBlock(row.formalPostingBlocked === true, 'formalPostingBlocked 仍为 true。')
  pushBlock(flowSummary.formalPostingFlowStatus !== 'entry_ready', '正式过账状态机建议阶段不是“正式过账入口就绪”。')
  pushBlock(row.ledgerStatus !== 'notWritten', '总账状态不是“未写总账”。')
  pushBlock(row.paymentWriteOffStatus !== 'notWrittenOff', '核销状态不是“未核销”。')
  pushBlock(hasBankFlow(row), '已存在银行流水信息。')
  pushBlock(!hasValidPostingAmount(row), '金额为空或异常，借贷金额必须大于 0、借贷平衡且差异为 0。')
  pushBlock(!hasCompleteFormalPostingSource(row), '来源链缺失。')
  pushBlock(!String(row.formalVoucherNo || '').trim(), '凭证号缺失。')
  pushBlock(!String(row.supplierName || row.supplierId || '').trim(), '付款对象缺失。')
  pushBlock(row.formalVoucherStatus === 'cancelled', '正式付款凭证已取消。')
  pushBlock(row.postingStatus === 'posted', '当前记录已过账。')
  pushBlock(row.ledgerStatus === 'written', '当前记录已写总账。')
  pushBlock(row.paymentWriteOffStatus === 'writtenOff', '当前记录已核销。')

  pushWarning(!String(row.paymentMethod || '').trim(), '付款方式缺失，当前作为提醒项，正式过账前需补齐或接入正式规则。')
  pushWarning(!String(row.paymentDate || '').trim() && String(row.voucherDate || '').trim(), '付款日期缺失但凭证日期存在，当前作为提醒项。')
  pushWarning(FORMAL_POSTING_PERMISSION_PLACEHOLDER_PASSED, '正式权限体系尚未真实接入，本轮仅做权限占位检查。')
  pushWarning(!hasAccountingPeriod(row), '会计期间字段缺失或仅为占位检查，后续需接入正式期间管理。')
  pushWarning(!hasVoucherAccountSubjects(row), '借贷科目字段缺失或仅为占位检查，后续需接入正式科目体系。')
  pushWarning(true, '银行流水与付款核销均为后续阶段能力，本轮不会生成或执行。')

  const hasBlocks = blockedReasons.length > 0
  const hasWarnings = warnings.length > 0
  const status = hasBlocks ? 'blocked' : (hasWarnings ? 'warning' : 'passed')
  return {
    formalPostingPreExecuteStatus: status,
    formalPostingPreExecuteStatusText: formalPostingPreExecuteStatusLabel(status),
    formalPostingPreExecuteReady: !hasBlocks,
    formalPostingPreExecuteBlocked: hasBlocks,
    formalPostingPreExecuteBlockedReasons: [...new Set(blockedReasons)],
    formalPostingPreExecuteWarnings: [...new Set(warnings)],
    formalPostingPreExecuteConclusion: hasBlocks
      ? `预执行检查阻断：存在 ${blockedReasons.length} 个阻断原因。本轮不正式过账、不写总账、不核销、不生成银行流水。`
      : (hasWarnings
        ? `预执行检查有 ${warnings.length} 个提醒项，但无阻断；仅表示可进入后续正式过账确认设计，本轮不执行正式过账。`
        : '预执行检查通过；仅表示未来可进入正式过账确认设计，本轮不执行正式过账。'),
  }
}

function formalPostingPreExecuteTitle(row = {}) {
  const summary = formalPostingPreExecuteSummary(row)
  return `${summary.formalPostingPreExecuteStatusText}：${summary.formalPostingPreExecuteConclusion}`
}

function formalPostingLockStatusLabel(status) {
  return {
    not_checked: '未检查',
    lock_ready: '可进入确认前锁定',
    blocked: '锁定阻断',
    warning: '锁定有提醒',
  }[status] || '未检查'
}

function formalPostingLockType(status) {
  return {
    not_checked: 'info',
    lock_ready: 'success',
    blocked: 'danger',
    warning: 'warning',
  }[status] || 'info'
}

function formalPostingLockSummary(row = {}) {
  const flowSummary = formalPostingFlowSummary(row)
  const preExecuteSummary = formalPostingPreExecuteSummary(row)
  const blockedReasons = []
  const warnings = []
  const pushBlock = (condition, reason) => { if (condition) blockedReasons.push(reason) }
  const pushWarning = (condition, warning) => { if (condition) warnings.push(warning) }

  pushBlock(!row.id || !row.formalVoucherNo, '正式付款凭证不存在或凭证号缺失。')
  pushBlock(row.formalVoucherStatus !== 'generated', '正式付款凭证状态不是“正式凭证已生成”。')
  pushBlock(row.postingPreReviewStatus !== 'passed' || Number(row.postingPreReviewBlockedCount || 0) > 0, '过账前评审未通过或仍有阻断项。')
  pushBlock(row.postingStatus !== 'posting_ready', '凭证过账准备状态不是“可过账”。')
  pushBlock(row.postingReady !== true, 'postingReady 不是 true。')
  pushBlock(row.postingBlocked === true, 'postingBlocked 仍为 true。')
  pushBlock(!isPostingSimulationCompleted(row), '未完成模拟过账。')
  pushBlock(row.formalPostingStatus !== 'ready', '正式过账前最终评审不是 ready。')
  pushBlock(row.formalPostingReady !== true, 'formalPostingReady 不是 true。')
  pushBlock(row.formalPostingBlocked === true, 'formalPostingBlocked 仍为 true。')
  pushBlock(flowSummary.formalPostingFlowStatus !== 'entry_ready', '正式过账状态机建议阶段不是“正式过账入口就绪”。')
  pushBlock(preExecuteSummary.formalPostingPreExecuteReady !== true, '正式过账预执行检查未就绪。')
  pushBlock(preExecuteSummary.formalPostingPreExecuteBlocked === true, '正式过账预执行检查仍有阻断项。')
  pushBlock(row.ledgerStatus !== 'notWritten', '总账状态不是“未写总账”。')
  pushBlock(row.paymentWriteOffStatus !== 'notWrittenOff', '核销状态不是“未核销”。')
  pushBlock(hasBankFlow(row), '已存在银行流水信息。')
  pushBlock(!hasValidPostingAmount(row), '金额为空或异常。')
  pushBlock(!hasCompleteFormalPostingSource(row), '来源链缺失。')
  pushBlock(!String(row.formalVoucherNo || '').trim(), '凭证号缺失。')
  pushBlock(!String(row.supplierName || row.supplierId || '').trim(), '付款对象缺失。')
  pushBlock(row.formalVoucherStatus === 'cancelled', '正式付款凭证已取消。')
  pushBlock(row.postingStatus === 'posted', '当前记录已过账。')
  pushBlock(row.ledgerStatus === 'written', '当前记录已写总账。')
  pushBlock(row.paymentWriteOffStatus === 'writtenOff', '当前记录已核销。')

  pushWarning(!String(row.paymentMethod || '').trim(), '付款方式缺失，当前作为提醒项，不直接阻断确认前锁定设计。')
  pushWarning(FORMAL_POSTING_PERMISSION_PLACEHOLDER_PASSED, '正式权限体系尚未真实接入，本轮仅做权限占位提醒。')
  pushWarning(!hasAccountingPeriod(row), '会计期间锁定仍为占位，后续需接入正式会计期间管理。')
  pushWarning(!hasVoucherAccountSubjects(row), '科目体系仍为占位，后续需接入正式科目体系。')
  pushWarning(true, '银行流水在后续阶段生成，本轮不生成银行流水。')
  pushWarning(true, '付款核销在后续阶段执行，本轮不执行核销。')
  pushWarning(true, '本轮只是确认前锁定设计，不真实锁定凭证或会计期间。')

  const hasBlocks = blockedReasons.length > 0
  const hasWarnings = warnings.length > 0 || preExecuteSummary.formalPostingPreExecuteStatus === 'warning'
  const status = hasBlocks ? 'blocked' : (hasWarnings ? 'warning' : 'lock_ready')
  return {
    formalPostingLockStatus: status,
    formalPostingLockStatusText: formalPostingLockStatusLabel(status),
    formalPostingLockReady: !hasBlocks,
    formalPostingLockBlocked: hasBlocks,
    formalPostingLockBlockedReasons: [...new Set(blockedReasons)],
    formalPostingLockWarnings: [...new Set(warnings)],
    formalPostingLockConclusion: hasBlocks
      ? `确认前锁定阻断：存在 ${blockedReasons.length} 个阻断原因。本轮不正式过账、不真实锁定凭证或会计期间。`
      : (hasWarnings
        ? `确认前锁定有 ${warnings.length} 个提醒项，但无阻断；仅表示可进入未来确认前锁定设计，本轮不真实锁定。`
        : '可进入确认前锁定设计；仅表示未来可进入正式过账确认前锁定步骤，本轮不真实锁定、不正式过账。'),
  }
}

function formalPostingLockTitle(row = {}) {
  const summary = formalPostingLockSummary(row)
  return `${summary.formalPostingLockStatusText}：${summary.formalPostingLockConclusion}`
}

function formalPostingConfirmStatusLabel(status) {
  return {
    not_checked: '未检查',
    confirm_ready: '可进入最终确认',
    blocked: '最终确认阻断',
    warning: '最终确认有提醒',
  }[status] || '未检查'
}

function formalPostingConfirmType(status) {
  return {
    not_checked: 'info',
    confirm_ready: 'success',
    blocked: 'danger',
    warning: 'warning',
  }[status] || 'info'
}

function formalPostingConfirmSummary(row = {}) {
  const flowSummary = formalPostingFlowSummary(row)
  const preExecuteSummary = formalPostingPreExecuteSummary(row)
  const lockSummary = formalPostingLockSummary(row)
  const blockedReasons = []
  const warnings = []
  const pushBlock = (condition, reason) => { if (condition) blockedReasons.push(reason) }
  const pushWarning = (condition, warning) => { if (condition) warnings.push(warning) }

  pushBlock(!row.id || !row.formalVoucherNo, '正式付款凭证不存在或凭证号缺失。')
  pushBlock(row.formalVoucherStatus !== 'generated', '正式付款凭证状态不是“正式凭证已生成”。')
  pushBlock(row.postingPreReviewStatus !== 'passed' || Number(row.postingPreReviewBlockedCount || 0) > 0, '过账前评审未通过或仍有阻断项。')
  pushBlock(row.postingStatus !== 'posting_ready', '凭证过账准备状态不是“可过账”。')
  pushBlock(row.postingReady !== true, 'postingReady 不是 true。')
  pushBlock(row.postingBlocked === true, 'postingBlocked 仍为 true。')
  pushBlock(!isPostingSimulationCompleted(row), '未完成模拟过账。')
  pushBlock(row.formalPostingStatus !== 'ready', '正式过账前最终评审不是 ready。')
  pushBlock(row.formalPostingReady !== true, 'formalPostingReady 不是 true。')
  pushBlock(row.formalPostingBlocked === true, 'formalPostingBlocked 仍为 true。')
  pushBlock(flowSummary.formalPostingFlowStatus !== 'entry_ready', '正式过账状态机建议阶段不是“正式过账入口就绪”。')
  pushBlock(preExecuteSummary.formalPostingPreExecuteReady !== true, '正式过账预执行检查未就绪。')
  pushBlock(preExecuteSummary.formalPostingPreExecuteBlocked === true, '正式过账预执行检查仍有阻断项。')
  pushBlock(lockSummary.formalPostingLockReady !== true, '正式过账确认前锁定检查未就绪。')
  pushBlock(lockSummary.formalPostingLockBlocked === true, '正式过账确认前锁定检查仍有阻断项。')
  pushBlock(row.ledgerStatus !== 'notWritten', '总账状态不是“未写总账”。')
  pushBlock(row.paymentWriteOffStatus !== 'notWrittenOff', '核销状态不是“未核销”。')
  pushBlock(hasBankFlow(row), '已存在银行流水信息。')
  pushBlock(!hasValidPostingAmount(row), '金额为空或异常。')
  pushBlock(!hasCompleteFormalPostingSource(row), '来源链缺失。')
  pushBlock(!String(row.formalVoucherNo || '').trim(), '凭证号缺失。')
  pushBlock(!String(row.supplierName || row.supplierId || '').trim(), '付款对象缺失。')
  pushBlock(row.formalVoucherStatus === 'cancelled', '正式付款凭证已取消。')
  pushBlock(row.postingStatus === 'posted', '当前记录已过账。')
  pushBlock(row.ledgerStatus === 'written', '当前记录已写总账。')
  pushBlock(row.paymentWriteOffStatus === 'writtenOff', '当前记录已核销。')

  pushWarning(!String(row.paymentMethod || '').trim(), '付款方式缺失，当前作为提醒项，不直接阻断最终确认设计。')
  pushWarning(FORMAL_POSTING_PERMISSION_PLACEHOLDER_PASSED, '正式权限体系尚未真实接入，本轮仅做权限占位提醒。')
  pushWarning(!hasAccountingPeriod(row), '会计期间锁定仍为占位，后续需接入正式会计期间管理。')
  pushWarning(!hasVoucherAccountSubjects(row), '科目体系仍为占位，后续需接入正式科目体系。')
  pushWarning(true, '银行流水在后续阶段生成，本轮不生成银行流水。')
  pushWarning(true, '付款核销在后续阶段执行，本轮不执行核销。')
  pushWarning(true, '本轮只是最终确认设计，不真实正式过账。')
  pushWarning(true, '本轮不写总账，不生成总账分录。')
  pushWarning(true, '后续进入真实总账写入前，必须补充基础验证数据体系。')

  const hasBlocks = blockedReasons.length > 0
  const hasWarnings = warnings.length > 0
    || preExecuteSummary.formalPostingPreExecuteStatus === 'warning'
    || lockSummary.formalPostingLockStatus === 'warning'
  const status = hasBlocks ? 'blocked' : (hasWarnings ? 'warning' : 'confirm_ready')
  return {
    formalPostingConfirmStatus: status,
    formalPostingConfirmStatusText: formalPostingConfirmStatusLabel(status),
    formalPostingConfirmReady: !hasBlocks,
    formalPostingConfirmBlocked: hasBlocks,
    formalPostingConfirmBlockedReasons: [...new Set(blockedReasons)],
    formalPostingConfirmWarnings: [...new Set(warnings)],
    formalPostingConfirmConclusion: hasBlocks
      ? `最终确认阻断：存在 ${blockedReasons.length} 个阻断原因。本轮不正式过账、不写总账、不核销、不生成银行流水。`
      : (hasWarnings
        ? `最终确认有 ${warnings.length} 个提醒项，但无阻断；仅表示可进入未来最终确认设计，本轮不执行正式过账。`
        : '可进入最终确认设计；仅表示未来可进入正式过账最终确认步骤，本轮不执行正式过账、不写总账。'),
  }
}

function formalPostingConfirmTitle(row = {}) {
  const summary = formalPostingConfirmSummary(row)
  return `${summary.formalPostingConfirmStatusText}：${summary.formalPostingConfirmConclusion}`
}

function postingDiagnosticConclusion(row = {}) {
  if (isPostingSimulationCompleted(row) && hasSimulationMissingReason(row)) {
    return '状态不一致：该记录已模拟过账，但正式过账评审仍提示模拟过账尚未完成，请检查正式过账评审判断逻辑。'
  }
  if (isPostingSimulationCompleted(row)) {
    return '当前记录已完成模拟过账，正式过账评审不应再因为“模拟过账尚未完成”而阻断。'
  }
  return '当前记录尚未完成模拟过账，正式过账前最终评审出现“模拟过账尚未完成”属于正常阻断。'
}

function postingDiagnosticListLabel(row = {}) {
  if (isPostingSimulationCompleted(row) && hasSimulationMissingReason(row)) return '已模拟但评审仍提示未模拟，需检查'
  return isPostingSimulationCompleted(row) ? '已模拟' : '未模拟'
}

function diagnosticStatusType(row = {}) {
  if (isPostingSimulationCompleted(row) && hasSimulationMissingReason(row)) return 'danger'
  return isPostingSimulationCompleted(row) ? 'success' : 'info'
}

function diagnosticStatusClass(row = {}) {
  if (isPostingSimulationCompleted(row) && hasSimulationMissingReason(row)) return 'danger'
  return isPostingSimulationCompleted(row) ? 'success' : 'info'
}

function handleOutcome(outcome, successText) {
  if (!outcome?.success) {
    refresh()
    return notify(outcome?.error || '操作失败。', 'warning')
  }
  refresh()
  notify(outcome.alreadyDone ? (outcome.message || '当前状态已达成，无需重复操作。') : successText)
}

function handleCreate(row) {
  const outcome = createFormalVoucherFromVoucherReview(row.id)
  if (!outcome.success) return notify(outcome.error, 'warning')
  refresh()
  router.push(`/finance/formal-payment-voucher/${outcome.formalVoucher.id}`)
}

function handleBatchCreate() { showSourceBatch(batchCreateFormalVouchersFromVoucherReviews(sourceIds.value)) }
function handleBatchCancel() { showVoucherBatch(batchCancelFormalVouchers(voucherIds.value)) }
function handleCancel(row) { handleOutcome(cancelFormalVoucher(row.id), '已取消正式付款凭证对象；仍未过账、未写总账、未核销。') }
function handleSimulatePosting(row) { handleOutcome(simulateFormalVoucherPosting(row.id), '已完成模拟过账；未写总账、未核销、未生成银行流水。') }
async function handleFormalPostingEntrance(row) {
  const reasons = formalPostingEntryReasons(row)
  if (reasons.length) {
    notify(`正式过账入口暂不可用：${reasons.join('；')}`, 'warning')
    return
  }
  try {
    await ElMessageBox.confirm(
      [
        '当前只是正式过账入口设计。',
        '本轮不会正式过账。',
        '本轮不会写总账，也不会生成总账分录。',
        '本轮不会核销，也不会生成银行流水。',
        '确认后仅显示入口占位提示，不改变任何正式财务字段。',
      ].join('\n'),
      '正式过账入口风险提示',
      {
        confirmButtonText: '确认，仅查看入口设计',
        cancelButtonText: '取消',
        type: 'warning',
      },
    )
    notify('已确认正式过账入口设计提示；本轮未正式过账、未写总账、未核销、未生成银行流水。')
  } catch (error) {
    notify('已取消正式过账入口确认；未改变任何正式财务字段。', 'info')
  }
}

function buildSeedDataInitToolSummary() {
  const blockedReasons = []
  const warnings = [
    '本轮只是基础验证数据初始化工具设计，不执行真实初始化。',
    '一键初始化基础验证数据按钮本轮禁用。',
    '一键清除基础验证数据按钮本轮禁用。',
    '后续 V1.13.18 才进入借贷平衡与余额验证器。',
    '未来真实总账写入前必须完成初始化工具稳定检查。',
    '未来初始化数据必须可追踪 scenarioId，并与用户数据隔离。',
  ]

  if (seedDataPlanDomains.length !== 10) blockedReasons.push('基础验证数据域不是 10 类。')
  if (!seedDataPlanIsolationRules.length) blockedReasons.push('缺少 seed / demo / sandbox 隔离策略。')
  if (!seedDataInitNamespaces.length) blockedReasons.push('缺少初始化 namespace 设计。')
  if (!seedDataInitSafetyRules.length) blockedReasons.push('缺少初始化安全规则。')

  const hasBlocks = blockedReasons.length > 0
  const status = hasBlocks ? 'blocked' : (warnings.length ? 'warning' : 'design_ready')
  const statusText = {
    not_ready: '工具未就绪',
    design_ready: '初始化工具设计已就绪',
    blocked: '初始化工具设计阻断',
    warning: '初始化工具设计有提醒',
  }[status]

  return {
    seedDataInitToolStatus: status,
    seedDataInitToolStatusText: statusText,
    seedDataInitToolReady: !hasBlocks,
    seedDataInitToolBlocked: hasBlocks,
    seedDataInitToolBlockedReasons: blockedReasons,
    seedDataInitToolWarnings: warnings,
    seedDataInitToolConclusion: hasBlocks
      ? '初始化工具设计仍有阻断项；本轮不初始化基础数据、不写 localStorage。'
      : '初始化工具设计已具备未来进入工具阶段的条件；本轮仍不初始化基础数据、不写 localStorage、不覆盖当前数据。',
    seedDataInitNamespaces,
    seedDataInitPreviewDomains,
    seedDataInitSafetyRules,
  }
}

function seedDataInitToolType(status) {
  if (status === 'design_ready') return 'success'
  if (status === 'blocked') return 'danger'
  if (status === 'warning') return 'warning'
  return 'info'
}

async function handleSeedDataInitToolCheck(mode = 'precheck') {
  const summary = seedDataInitToolSummary.value
  const lines = [
    `检查类型：${mode === 'conditions' ? '查看初始化条件' : '初始化工具预检查'}`,
    `工具状态：${summary.seedDataInitToolStatusText}`,
    `是否设计就绪：${summary.seedDataInitToolReady ? '是，仅表示未来工具设计就绪' : '否，仍有阻断条件'}`,
    `阻断原因：${summary.seedDataInitToolBlockedReasons.length ? summary.seedDataInitToolBlockedReasons.join('；') : '无'}`,
    `提醒项：${summary.seedDataInitToolWarnings.length ? summary.seedDataInitToolWarnings.join('；') : '无'}`,
    `namespace：${summary.seedDataInitNamespaces.map((item) => item.namespace).join('；')}`,
    `预览数据域：${summary.seedDataInitPreviewDomains.map((item) => item.key).join('；')}`,
    '本次检查只读，不写 localStorage，不生成 chartOfAccounts、openingBalances、bankAccounts、suppliers、supplierBalances、inventoryItems、warehouses、inventoryOpeningBalances、p2pScenarioSamples、reportCheckSamples，不清除任何数据。',
  ]
  await ElMessageBox.alert(lines.join('\n'), '基础验证数据初始化工具设计检查', {
    confirmButtonText: '知道了',
    type: summary.seedDataInitToolBlocked ? 'warning' : 'success',
  })
  notify('已完成初始化工具只读检查；未初始化数据，未写 localStorage，未清除数据。')
}

function buildBalanceValidatorSummary() {
  const blockedReasons = []
  const warnings = [
    '本轮只做验证器设计，不读取真实余额。',
    '本轮不计算真实借贷合计，不生成总账分录。',
    '本轮不修改库存余额、银行余额、供应商余额或报表结果。',
    '未来必须在基础验证数据初始化完成后，才能执行真实验证。',
  ]

  if (balanceValidatorDesignChecks.length !== 6) blockedReasons.push('验证器设计项不完整。')
  if (seedDataPlanDomains.length !== 10) blockedReasons.push('基础验证数据域不完整，无法支撑未来余额验证。')
  if (!seedDataInitToolSummary.value.seedDataInitToolReady) blockedReasons.push('基础验证数据初始化工具设计尚未就绪。')

  const hasBlocks = blockedReasons.length > 0
  const status = hasBlocks ? 'blocked' : (warnings.length ? 'warning' : 'design_ready')
  const statusText = {
    not_ready: '未就绪',
    design_ready: '设计完成',
    warning: '验证有提醒',
    blocked: '验证阻断',
  }[status]

  return {
    balanceValidatorStatus: status,
    balanceValidatorStatusText: statusText,
    balanceValidatorReady: !hasBlocks,
    balanceValidatorBlocked: hasBlocks,
    balanceValidatorWarnings: warnings,
    balanceValidatorBlockedReasons: blockedReasons,
    balanceValidatorConclusion: hasBlocks
      ? '借贷平衡与余额验证器设计仍有阻断项；本轮不执行真实验证。'
      : '借贷平衡与余额验证器设计已建立；本轮仅形成规则、字段和展示，不执行真实验证。',
    debitTotal: 0,
    creditTotal: 0,
    balanceDifference: 0,
    isBalanced: true,
    balanceConclusion: '设计规则：未来以借方合计等于贷方合计作为平衡条件；本轮不读取真实分录。',
    ledgerBalanceCheckStatus: 'design_ready',
    ledgerBalanceConclusion: '设计规则：未来验证期初余额、本期发生额和期末余额；本轮不计算真实总账余额。',
    bankBalanceCheckStatus: 'design_ready',
    bankBalanceDifference: 0,
    bankBalanceConclusion: '设计规则：未来验证银行账户期初余额、收入、支出和当前余额；本轮不读取银行余额。',
    supplierBalanceCheckStatus: 'design_ready',
    supplierBalanceDifference: 0,
    supplierBalanceConclusion: '设计规则：未来验证供应商期初应付、新增应付、付款金额和当前应付余额；本轮不修改供应商余额。',
    inventoryBalanceCheckStatus: 'design_ready',
    inventoryQtyDifference: 0,
    inventoryAmountDifference: 0,
    inventoryBalanceConclusion: '设计规则：未来验证库存数量和库存金额结存；本轮不读取或修改库存余额。',
    reportCheckStatus: 'design_ready',
    reportCheckConclusion: '设计规则：未来验证资产负债表、科目余额表、银行余额表、供应商往来表和库存结存表；本轮不生成报表结果。',
  }
}

function balanceValidatorType(status) {
  if (status === 'design_ready') return 'success'
  if (status === 'blocked') return 'danger'
  if (status === 'warning') return 'warning'
  return 'info'
}

function buildLedgerPostingReviewSummary() {
  const validator = buildBalanceValidatorSummary()
  const blockedReasons = []
  const warnings = [
    '本轮只是未来真实总账写入前复核设计，不执行正式过账。',
    '本轮不写总账、不生成总账分录、不生成 ledgerEntryId / ledgerEntryNo。',
    '权限检查仅为占位设计，未接入正式权限系统。',
    '会计期间检查仅为规则设计，本轮不锁定期间。',
    '回滚能力只定义未来检查项，本轮不写正式过账日志。',
  ]

  if (ledgerPostingReviewDesignChecks.length !== 8) blockedReasons.push('总账写入前复核检查项不完整。')
  if (!validator.balanceValidatorReady) blockedReasons.push('借贷平衡与余额验证器设计尚未就绪。')
  if (!seedDataInitToolSummary.value.seedDataInitToolReady) blockedReasons.push('基础验证数据初始化工具设计尚未就绪。')

  const hasBlocks = blockedReasons.length > 0
  const status = hasBlocks ? 'blocked' : (warnings.length ? 'warning' : 'review_ready')
  const statusText = {
    not_ready: '未就绪',
    review_ready: '复核通过',
    warning: '复核有提醒',
    blocked: '复核阻断',
  }[status]

  return {
    ledgerPostingReviewStatus: status,
    ledgerPostingReviewStatusText: statusText,
    ledgerPostingReviewReady: !hasBlocks,
    ledgerPostingReviewBlocked: hasBlocks,
    ledgerPostingReviewWarnings: warnings,
    ledgerPostingReviewBlockedReasons: blockedReasons,
    ledgerPostingReviewConclusion: hasBlocks
      ? '真实总账写入前复核设计仍有阻断项；本轮不写总账。'
      : '真实总账写入前复核设计已建立；本轮只形成复核条件，不执行正式过账、不写总账。',
    financialDataCheckStatus: 'design_ready',
    financialDataCheckConclusion: '设计规则：未来检查会计科目体系、会计期间、期初余额、供应商往来和银行账户；本轮不读取真实基础数据。',
    ledgerPostingDebitTotal: 0,
    ledgerPostingCreditTotal: 0,
    ledgerPostingDifference: 0,
    ledgerPostingBalanced: true,
    balanceCheckStatus: 'design_ready',
    balanceCheckConclusion: '设计规则：未来正式写入前必须满足借方金额等于贷方金额；本轮不计算真实金额。',
    accountCompletenessStatus: 'design_ready',
    accountCompletenessConclusion: '设计规则：未来总账分录必须具备借方科目、贷方科目、科目编码、科目方向和科目状态。',
    periodCheckStatus: 'design_ready',
    periodCheckConclusion: '设计规则：未来检查会计期间存在、开放、未关闭且日期合法；本轮不锁定会计期间。',
    postingPermissionStatus: 'placeholder',
    postingPermissionConclusion: '设计规则：未来检查操作人、审批、财务和审计权限；本轮仅保留权限占位。',
    auditCheckStatus: 'design_ready',
    auditCheckConclusion: '设计规则：未来检查操作记录、来源链、审批链、修改记录和时间记录。',
    ledgerEntryStructureStatus: 'design_ready',
    ledgerEntryStructureConclusion: '设计规则：未来写入总账必须具备凭证编号、会计日期、科目、借贷金额、来源单据、操作人和时间。',
    rollbackCapabilityStatus: 'design_ready',
    rollbackCapabilityConclusion: '设计规则：未来正式过账失败时必须可追踪、可恢复、保留日志并避免重复写入。',
  }
}

function ledgerPostingReviewType(status) {
  if (status === 'review_ready') return 'success'
  if (status === 'blocked') return 'danger'
  if (status === 'warning') return 'warning'
  return 'info'
}

function simulationAmount(row = {}) {
  const amount = Number(row.totalVoucherAmount ?? row.amount ?? row.payAmount ?? 0)
  if (!Number.isFinite(amount)) return 0
  return Math.round(amount * 100) / 100
}

function buildSimulationLedgerSummary(row = {}) {
  const amount = simulationAmount(row)
  const voucherNo = row?.formalVoucherNo || row?.voucherNo || '未指定正式付款凭证'
  const scenarioId = `SIM-LEDGER-${row?.id || voucherNo}`
  const entries = amount > 0 ? [
    {
      entryId: `${scenarioId}-D`,
      accountCode: '2202',
      accountName: '应付账款',
      direction: 'debit',
      amount,
      sourceVoucherNo: voucherNo,
      scenarioId,
    },
    {
      entryId: `${scenarioId}-C`,
      accountCode: '1002',
      accountName: '银行存款',
      direction: 'credit',
      amount,
      sourceVoucherNo: voucherNo,
      scenarioId,
    },
  ] : []
  const debitTotal = entries.filter((entry) => entry.direction === 'debit').reduce((sum, entry) => sum + entry.amount, 0)
  const creditTotal = entries.filter((entry) => entry.direction === 'credit').reduce((sum, entry) => sum + entry.amount, 0)
  const difference = Math.round((debitTotal - creditTotal) * 100) / 100
  const balanced = entries.length > 0 && difference === 0
  const blockedReasons = []
  const warnings = [
    '本轮只是模拟总账写入设计，不写真实总账。',
    '模拟分录不会生成真实 ledgerEntryId / ledgerEntryNo。',
    '模拟余额变化和报表影响只用于页面展示和诊断 JSON。',
  ]

  if (amount <= 0) blockedReasons.push('当前凭证金额为空或无效，无法形成模拟分录。')

  const status = blockedReasons.length
    ? 'blocked'
    : (balanced ? 'balanced' : 'warning')

  return {
    simulationLedgerStatus: status,
    simulationLedgerStatusText: {
      not_created: '未生成',
      created: '已生成模拟分录',
      balanced: '模拟平衡',
      warning: '模拟有提醒',
      blocked: '模拟阻断',
    }[status],
    simulationLedgerReady: !blockedReasons.length,
    simulationLedgerBlocked: blockedReasons.length > 0,
    simulationLedgerWarnings: warnings,
    simulationLedgerBlockedReasons: blockedReasons,
    simulationLedgerConclusion: blockedReasons.length
      ? '模拟总账写入存在阻断；本轮仍不写真实总账。'
      : '模拟总账写入模型已生成平衡分录；本轮仅模拟，不写真实总账。',
    simulationLedgerEntries: entries,
    simulationDebitTotal: Math.round(debitTotal * 100) / 100,
    simulationCreditTotal: Math.round(creditTotal * 100) / 100,
    simulationDifference: difference,
    simulationBalanced: balanced,
    simulationBalanceChanges: entries.map((entry) => ({
      accountCode: entry.accountCode,
      accountName: entry.accountName,
      direction: entry.direction,
      directionText: entry.direction === 'debit' ? '模拟借方增加' : '模拟贷方减少或资金流出',
      changeAmount: entry.amount,
      sourceVoucherNo: voucherNo,
      scenarioId,
    })),
    simulationReportImpact: [
      { report: '科目余额表', impact: '未来展示应付账款借方发生额和银行存款贷方发生额' },
      { report: '资产负债表', impact: '未来展示负债和货币资金的模拟变化' },
      { report: '供应商往来表', impact: '未来展示供应商应付余额的模拟减少' },
      { report: '银行余额表', impact: '未来展示银行存款模拟支出影响' },
    ],
  }
}

function simulationLedgerSummary(row = {}) {
  return buildSimulationLedgerSummary(row || {})
}

function simulationLedgerType(status) {
  if (status === 'balanced') return 'success'
  if (status === 'blocked') return 'danger'
  if (status === 'warning') return 'warning'
  if (status === 'created') return 'primary'
  return 'info'
}

async function handleSimulationLedgerPreview(row = {}) {
  const summary = simulationLedgerSummary(row)
  const lines = [
    `模拟状态：${summary.simulationLedgerStatusText}`,
    `模拟借方合计：${summary.simulationDebitTotal}`,
    `模拟贷方合计：${summary.simulationCreditTotal}`,
    `模拟差额：${summary.simulationDifference}`,
    `模拟是否平衡：${summary.simulationBalanced ? '是' : '否'}`,
    `模拟分录：${summary.simulationLedgerEntries.map((entry) => `${entry.direction === 'debit' ? '借' : '贷'} ${entry.accountCode} ${entry.accountName} ${entry.amount}`).join('；') || '无'}`,
    `阻断原因：${summary.simulationLedgerBlockedReasons.length ? summary.simulationLedgerBlockedReasons.join('；') : '无'}`,
    '本次按钮只生成页面内模拟结果，不写真实总账，不改变 ledgerStatus / postingStatus / paymentWriteOffStatus，不生成银行流水，不执行核销，不写 localStorage。',
  ]
  await ElMessageBox.alert(lines.join('\n'), '模拟总账写入结果', {
    confirmButtonText: '知道了',
    type: summary.simulationLedgerBlocked ? 'warning' : 'success',
  })
  notify('已生成只读模拟总账结果；未写真实总账，未改变任何正式财务字段。')
}

function buildSimulationLedgerValidationSummary(row = {}) {
  const ledger = buildSimulationLedgerSummary(row)
  const voucherAmount = simulationAmount(row)
  const entries = ledger.simulationLedgerEntries
  const debitEntries = entries.filter((entry) => entry.direction === 'debit')
  const creditEntries = entries.filter((entry) => entry.direction === 'credit')
  const blockedReasons = []
  const warnings = [
    '本轮只验证模拟对象，不写真实总账。',
    '科目方向验证只使用模拟规则，不连接真实科目体系。',
    '余额验证和报表验证只检查模拟影响模型是否存在。',
  ]

  if (!entries.length) blockedReasons.push('模拟分录不存在。')
  if (!debitEntries.length) blockedReasons.push('模拟分录缺少借方。')
  if (!creditEntries.length) blockedReasons.push('模拟分录缺少贷方。')
  if (entries.some((entry) => !entry.accountCode || !entry.accountName)) blockedReasons.push('模拟分录科目信息不完整。')
  if (entries.some((entry) => !(entry.amount > 0))) blockedReasons.push('模拟分录金额无效。')
  if (entries.some((entry) => !entry.sourceVoucherNo)) blockedReasons.push('模拟分录缺少来源凭证号。')
  if (!ledger.simulationBalanced) blockedReasons.push('模拟借贷不平衡。')

  const amountDifference = Math.round((voucherAmount - ledger.simulationDebitTotal) * 100) / 100
  if (amountDifference !== 0) blockedReasons.push('正式付款凭证金额与模拟分录金额不一致。')

  const directionOk = entries.every((entry) => (
    (entry.accountCode === '2202' && entry.direction === 'debit')
    || (entry.accountCode === '1002' && entry.direction === 'credit')
  ))
  if (!directionOk) blockedReasons.push('模拟分录科目方向不符合付款业务规则。')

  if (!ledger.simulationBalanceChanges.length) blockedReasons.push('模拟余额变化模型不存在。')
  if (!ledger.simulationReportImpact.length) blockedReasons.push('模拟报表影响模型不存在。')

  const hasBlocks = blockedReasons.length > 0
  const status = hasBlocks ? 'blocked' : (warnings.length ? 'warning' : 'passed')
  const statusText = {
    not_checked: '未验证',
    passed: '验证通过',
    warning: '验证有提醒',
    blocked: '验证阻断',
  }[status]

  return {
    simulationLedgerValidationStatus: status,
    simulationLedgerValidationStatusText: statusText,
    simulationLedgerValidationReady: !hasBlocks,
    simulationLedgerValidationBlocked: hasBlocks,
    simulationLedgerValidationWarnings: warnings,
    simulationLedgerValidationBlockedReasons: blockedReasons,
    simulationLedgerValidationConclusion: hasBlocks
      ? '模拟总账结果验证存在阻断；本轮仍不写真实总账。'
      : '模拟总账结果验证通过；本轮仅验证模拟对象，不写真实总账。',
    simulationEntryCheckStatus: entries.length && debitEntries.length && creditEntries.length ? 'passed' : 'blocked',
    simulationEntryCheckConclusion: entries.length && debitEntries.length && creditEntries.length
      ? '模拟分录包含借方、贷方、科目、金额和来源凭证。'
      : '模拟分录不完整。',
    simulationDebitCreditCheckStatus: ledger.simulationBalanced ? 'passed' : 'blocked',
    simulationDebitCreditCheckConclusion: ledger.simulationBalanced
      ? '模拟借贷合计一致。'
      : '模拟借贷合计不一致。',
    simulationAccountDirectionCheckStatus: directionOk ? 'passed' : 'blocked',
    simulationAccountDirectionCheckConclusion: directionOk
      ? '模拟科目方向符合付款业务规则。'
      : '模拟科目方向不符合付款业务规则。',
    simulationAmountCheckStatus: amountDifference === 0 ? 'passed' : 'blocked',
    simulationAmountDifference: amountDifference,
    simulationAmountCheckConclusion: amountDifference === 0
      ? '正式付款凭证金额与模拟分录金额一致。'
      : '正式付款凭证金额与模拟分录金额不一致。',
    simulationBalanceCheckStatus: ledger.simulationBalanceChanges.length ? 'passed' : 'blocked',
    simulationBalanceCheckConclusion: ledger.simulationBalanceChanges.length
      ? '模拟余额变化模型存在；本轮不读取真实余额。'
      : '模拟余额变化模型缺失。',
    simulationReportCheckStatus: ledger.simulationReportImpact.length ? 'passed' : 'blocked',
    simulationReportCheckConclusion: ledger.simulationReportImpact.length
      ? '模拟报表影响模型存在；本轮不生成真实报表。'
      : '模拟报表影响模型缺失。',
    simulationValidationDifference: ledger.simulationDifference,
    simulationValidationBalanced: ledger.simulationBalanced && !hasBlocks,
  }
}

function simulationLedgerValidationSummary(row = {}) {
  return buildSimulationLedgerValidationSummary(row || {})
}

function simulationLedgerValidationType(status) {
  if (status === 'passed') return 'success'
  if (status === 'blocked') return 'danger'
  if (status === 'warning') return 'warning'
  return 'info'
}

async function handleSimulationLedgerValidation(row = {}) {
  const summary = simulationLedgerValidationSummary(row)
  const lines = [
    `验证状态：${summary.simulationLedgerValidationStatusText}`,
    `是否通过：${summary.simulationLedgerValidationReady ? '是' : '否'}`,
    `分录验证：${summary.simulationEntryCheckConclusion}`,
    `借贷验证：${summary.simulationDebitCreditCheckConclusion}`,
    `科目方向验证：${summary.simulationAccountDirectionCheckConclusion}`,
    `金额验证：${summary.simulationAmountCheckConclusion}`,
    `余额验证：${summary.simulationBalanceCheckConclusion}`,
    `报表验证：${summary.simulationReportCheckConclusion}`,
    `阻断原因：${summary.simulationLedgerValidationBlockedReasons.length ? summary.simulationLedgerValidationBlockedReasons.join('；') : '无'}`,
    '本次验证只检查模拟对象，不写真实总账，不改变 ledgerStatus / postingStatus / paymentWriteOffStatus，不执行核销，不生成银行流水，不写 localStorage。',
  ]
  await ElMessageBox.alert(lines.join('\n'), '模拟总账结果验证', {
    confirmButtonText: '知道了',
    type: summary.simulationLedgerValidationBlocked ? 'warning' : 'success',
  })
  notify('已完成只读模拟总账结果验证；未写真实总账，未改变任何正式财务字段。')
}

function buildSimulationDataMappingSummary(row = {}) {
  const ledger = buildSimulationLedgerSummary(row)
  const voucherNo = row?.formalVoucherNo || row?.voucherNo || '未指定正式付款凭证'
  const scenarioId = `P2P-SIM-${row?.id || voucherNo}`
  const accountMapping = ledger.simulationLedgerEntries.map((entry) => ({
    accountCode: entry.accountCode,
    accountName: entry.accountName,
    accountDirection: entry.direction,
    sourceType: entry.accountCode === '2202' ? 'chartOfAccounts:应付账款' : 'chartOfAccounts:银行存款',
  }))
  const supplierMapping = {
    supplierId: row?.supplierId || 'SUPPLIER-SIM',
    supplierName: row?.supplierName || '模拟供应商',
    supplierBalanceReference: 'supplierBalances',
  }
  const bankMapping = {
    bankAccountId: row?.companyBankAccountId || 'BANK-SIM',
    bankAccountName: row?.paymentBankName || row?.paymentAccountName || '模拟付款银行账户',
    balanceReference: 'bankAccounts',
  }
  const scenarioMapping = {
    scenarioId,
    scenarioType: 'p2pScenarioSamples',
    sourceVoucherNo: voucherNo,
  }
  const reportMapping = [
    { report: '科目余额表', reference: 'reportCheckSamples.accountBalance', scope: '验证应付账款和银行存款模拟发生额' },
    { report: '资产负债表', reference: 'reportCheckSamples.balanceSheet', scope: '验证负债和货币资金模拟影响' },
    { report: '供应商往来表', reference: 'reportCheckSamples.supplierBalance', scope: '验证供应商应付余额模拟影响' },
    { report: '银行余额表', reference: 'reportCheckSamples.bankBalance', scope: '验证银行账户模拟支出影响' },
  ]
  const blockedReasons = []
  const warnings = [
    '本轮只做映射设计，不读取真实基础验证数据。',
    '科目、供应商、银行、场景和报表映射均为模拟引用。',
    '未来必须在基础验证数据初始化并隔离后，才能做真实映射校验。',
  ]

  if (!accountMapping.length) blockedReasons.push('缺少模拟分录科目映射。')
  if (!supplierMapping.supplierName) blockedReasons.push('缺少供应商映射。')
  if (!bankMapping.bankAccountName) blockedReasons.push('缺少银行账户映射。')
  if (!scenarioMapping.sourceVoucherNo) blockedReasons.push('缺少来源凭证映射。')
  if (!reportMapping.length) blockedReasons.push('缺少报表验证映射。')

  const hasBlocks = blockedReasons.length > 0
  const status = hasBlocks ? 'blocked' : (warnings.length ? 'warning' : 'ready')

  return {
    simulationDataMappingStatus: status,
    simulationDataMappingStatusText: {
      not_ready: '未建立关联',
      ready: '关联设计完成',
      warning: '关联有提醒',
      blocked: '关联阻断',
    }[status],
    simulationDataMappingReady: !hasBlocks,
    simulationDataMappingBlocked: hasBlocks,
    simulationDataMappingWarnings: warnings,
    simulationDataMappingBlockedReasons: blockedReasons,
    simulationDataMappingConclusion: hasBlocks
      ? '模拟总账与基础验证数据关联设计仍有阻断项；本轮不生成基础数据。'
      : '模拟总账与基础验证数据关联设计已建立；本轮只做映射诊断，不读取或写入真实基础数据。',
    simulationDataMapping: {
      account: accountMapping,
      supplier: supplierMapping,
      bank: bankMapping,
      scenario: scenarioMapping,
      report: reportMapping,
    },
    simulationAccountMapping: accountMapping,
    simulationSupplierMapping: supplierMapping,
    simulationBankMapping: bankMapping,
    simulationScenarioMapping: scenarioMapping,
    simulationReportMapping: reportMapping,
  }
}

function simulationDataMappingSummary(row = {}) {
  return buildSimulationDataMappingSummary(row || {})
}

function simulationDataMappingType(status) {
  if (status === 'ready') return 'success'
  if (status === 'blocked') return 'danger'
  if (status === 'warning') return 'warning'
  return 'info'
}

async function handleSimulationDataMappingCheck(row = {}) {
  const summary = simulationDataMappingSummary(row)
  const lines = [
    `关联状态：${summary.simulationDataMappingStatusText}`,
    `是否就绪：${summary.simulationDataMappingReady ? '是，仅表示映射设计完成' : '否，仍有阻断条件'}`,
    `科目映射：${summary.simulationAccountMapping.map((item) => `${item.accountCode} ${item.accountName}`).join('；') || '无'}`,
    `供应商映射：${summary.simulationSupplierMapping.supplierName}`,
    `银行映射：${summary.simulationBankMapping.bankAccountName}`,
    `场景映射：${summary.simulationScenarioMapping.scenarioId}`,
    `报表映射：${summary.simulationReportMapping.map((item) => item.report).join('；')}`,
    `阻断原因：${summary.simulationDataMappingBlockedReasons.length ? summary.simulationDataMappingBlockedReasons.join('；') : '无'}`,
    '本次检查只读，不生成基础数据，不写 localStorage，不改变正式付款凭证状态，不写总账。',
  ]
  await ElMessageBox.alert(lines.join('\n'), '模拟数据关联检查', {
    confirmButtonText: '知道了',
    type: summary.simulationDataMappingBlocked ? 'warning' : 'success',
  })
  notify('已完成只读模拟数据关联检查；未生成基础数据，未写 localStorage。')
}

function buildSimulationP2PScenarioSummary(row = {}) {
  const amount = simulationAmount(row)
  const voucherNo = row?.formalVoucherNo || row?.voucherNo || '未指定正式付款凭证'
  const supplierId = row?.supplierId || 'SUPPLIER-SIM'
  const supplierName = row?.supplierName || '模拟供应商'
  const scenarioId = `P2P-FLOW-${row?.id || voucherNo}`
  const ledger = buildSimulationLedgerSummary(row)
  const mapping = buildSimulationDataMappingSummary(row)
  const flow = {
    request: {
      requestId: row?.sourcePurchaseRequestNo || `PR-SIM-${row?.id || '001'}`,
      requestStatus: '模拟已批准',
      requestAmount: amount,
    },
    purchaseOrder: {
      purchaseOrderNo: row?.sourcePurchaseOrderNo || `PO-SIM-${row?.id || '001'}`,
      supplierId,
      supplierName,
      orderAmount: amount,
    },
    receipt: {
      receiptNo: row?.sourceReceiptNo || `RCV-SIM-${row?.id || '001'}`,
      receivedQuantity: amount > 0 ? 1 : 0,
      receivedAmount: amount,
    },
    inventory: {
      warehouseId: row?.warehouseId || 'WH-SIM',
      inventoryAmount: amount,
    },
    payable: {
      payableAmount: amount,
      supplierBalanceImpact: amount > 0 ? `模拟减少应付 ${amount}` : '无有效应付影响',
    },
    payment: {
      paymentVoucherNo: voucherNo,
      paymentAmount: amount,
    },
    ledger: {
      simulationLedgerEntries: ledger.simulationLedgerEntries,
      simulationDebitTotal: ledger.simulationDebitTotal,
      simulationCreditTotal: ledger.simulationCreditTotal,
    },
    reportImpact: ledger.simulationReportImpact,
    mapping: mapping.simulationDataMapping,
    scenarioId,
  }
  const blockedReasons = []
  const warnings = [
    '本轮只设计完整 P2P 模拟验证链，不生成真实业务数据。',
    '请购、采购订单、收货、入库、应付阶段均为模拟关联，不写入 SCM/WMS/QMS/Finance 数据。',
    '未来需与 p2pScenarioSamples 和 reportCheckSamples 隔离数据衔接后，才能做真实场景验证。',
  ]

  if (amount <= 0) blockedReasons.push('模拟链金额无效。')
  if (!flow.request.requestId) blockedReasons.push('缺少请购关联。')
  if (!flow.purchaseOrder.purchaseOrderNo) blockedReasons.push('缺少采购订单关联。')
  if (!flow.receipt.receiptNo) blockedReasons.push('缺少收货关联。')
  if (!flow.inventory.warehouseId) blockedReasons.push('缺少入库仓库关联。')
  if (!flow.payment.paymentVoucherNo) blockedReasons.push('缺少付款凭证关联。')
  if (!flow.ledger.simulationLedgerEntries.length) blockedReasons.push('缺少模拟总账关联。')
  if (!flow.reportImpact.length) blockedReasons.push('缺少模拟报表影响。')
  if (!(flow.purchaseOrder.orderAmount === flow.receipt.receivedAmount
    && flow.receipt.receivedAmount === flow.payable.payableAmount
    && flow.payable.payableAmount === flow.payment.paymentAmount)) {
    blockedReasons.push('采购、收货、应付、付款金额模型不一致。')
  }

  const hasBlocks = blockedReasons.length > 0
  const status = hasBlocks ? 'blocked' : (warnings.length ? 'warning' : 'passed')

  return {
    simulationP2PValidationStatus: status,
    simulationP2PValidationStatusText: {
      not_checked: '未验证',
      passed: '验证通过',
      warning: '验证有提醒',
      blocked: '验证阻断',
    }[status],
    simulationP2PValidationReady: !hasBlocks,
    simulationP2PValidationBlocked: hasBlocks,
    simulationP2PValidationWarnings: warnings,
    simulationP2PValidationBlockedReasons: blockedReasons,
    simulationP2PValidationConclusion: hasBlocks
      ? '模拟 P2P 完整业务链仍有阻断项；本轮不生成真实业务数据。'
      : '模拟 P2P 完整业务链设计已建立；本轮只做模拟验证，不生成真实业务数据。',
    simulationP2PFlow: flow,
  }
}

function simulationP2PScenarioSummary(row = {}) {
  return buildSimulationP2PScenarioSummary(row || {})
}

function simulationP2PValidationType(status) {
  if (status === 'passed') return 'success'
  if (status === 'blocked') return 'danger'
  if (status === 'warning') return 'warning'
  return 'info'
}

function supplierAmount(value = {}) {
  const amount = Number(value.amount ?? value.totalAmount ?? value.planAmount ?? value.approvedAmount ?? value.orderAmount ?? value.receivedAmount ?? value.payableAmount ?? value.paymentAmount ?? 0)
  if (Number.isFinite(amount) && amount > 0) return Math.round(amount * 100) / 100
  const qty = Number(value.quantity ?? value.orderQuantity ?? value.receivedQuantity ?? 0)
  const price = Number(value.approvedPrice ?? value.planPrice ?? value.price ?? value.unitPrice ?? 0)
  const calculated = qty * price
  return Number.isFinite(calculated) ? Math.round(calculated * 100) / 100 : 0
}

function supplierNameFromLine(line = {}) {
  const supplierId = line.supplierId || line.vendorId || ''
  return line.supplierName || line.vendorName || getScmDisplayName('supplier', supplierId) || supplierId || '未指定供应商'
}

function aggregateSupplierMappings(lines = [], fallbackAmount = 0) {
  const labels = ['供应商A', '供应商B', '供应商C', '供应商D', '供应商E', '供应商F']
  const map = new Map()
  ;(lines || []).forEach((line) => {
    const supplierId = line.supplierId || line.vendorId || ''
    const supplierName = supplierNameFromLine(line)
    const key = supplierId || supplierName
    if (!key) return
    const current = map.get(key) || {
      supplierKey: key,
      supplierId,
      supplierName,
      displayName: supplierName,
      amount: 0,
      purchaseAmount: 0,
      receiptAmount: 0,
      inventoryAmount: 0,
      payableAmount: 0,
      paymentAmount: 0,
    }
    const amount = supplierAmount(line) || Number(fallbackAmount || 0)
    current.amount = Math.round((current.amount + amount) * 100) / 100
    current.purchaseAmount = Math.round((current.purchaseAmount + amount) * 100) / 100
    current.receiptAmount = Math.round((current.receiptAmount + amount) * 100) / 100
    current.inventoryAmount = Math.round((current.inventoryAmount + amount) * 100) / 100
    current.payableAmount = Math.round((current.payableAmount + amount) * 100) / 100
    current.paymentAmount = Math.round((current.paymentAmount + amount) * 100) / 100
    map.set(key, current)
  })
  return [...map.values()].map((item, index) => ({
    ...item,
    supplierLabel: labels[index] || `供应商${index + 1}`,
    displayName: `${labels[index] || `供应商${index + 1}`}：${item.supplierName || item.supplierId || item.supplierKey}`,
  }))
}

function singleSupplierMapping(row = {}, amount = 0) {
  const supplierId = row?.supplierId || ''
  const supplierName = row?.supplierName || getScmDisplayName('supplier', supplierId) || '未指定供应商'
  if (!supplierId && !row?.supplierName) return []
  return aggregateSupplierMappings([{ supplierId, supplierName, amount }], amount)
}

function findPurchaseOrderForVoucher(row = {}) {
  const poNo = row?.sourcePurchaseOrderNo || simulationP2PScenarioSummary(row).simulationP2PFlow.purchaseOrder.purchaseOrderNo || ''
  const scmState = getScmState()
  const order = (scmState.purchaseOrders || []).find((item) => [item.poNo, item.orderNo, item.purchaseOrderNo, item.id].some((value) => String(value || '') === String(poNo || '')))
  const items = order
    ? (scmState.purchaseOrderItems || []).filter((item) => String(item.poId || item.purchaseOrderId || item.sourceOrderId || '') === String(order.id))
    : (scmState.purchaseOrderItems || []).filter((item) => [item.poNo, item.orderNo, item.purchaseOrderNo, item.sourceOrderNo].some((value) => String(value || '') === String(poNo || '')))
  return { poNo, order, items }
}

function buildMultiSupplierP2PSummary(row = {}) {
  const amount = simulationAmount(row)
  const { poNo, items } = findPurchaseOrderForVoucher(row)
  const purchaseOrderSuppliers = aggregateSupplierMappings(items)
  const fallbackPayment = singleSupplierMapping(row, amount)
  const receiptSupplierMapping = purchaseOrderSuppliers.map((item) => ({ ...item, amount: item.receiptAmount }))
  const inventorySupplierMapping = purchaseOrderSuppliers.map((item) => ({ ...item, amount: item.inventoryAmount }))
  const payableSupplierMapping = fallbackPayment.map((item) => ({ ...item, amount: item.payableAmount || amount }))
  const paymentSupplierMapping = fallbackPayment.map((item) => ({ ...item, amount: item.paymentAmount || amount }))
  const ledgerSupplierMapping = fallbackPayment.map((item) => ({ ...item, amount: item.amount || amount, source: '正式付款凭证当前供应商' }))
  const purchaseOrderSupplierCount = purchaseOrderSuppliers.length
  const counts = [purchaseOrderSupplierCount, payableSupplierMapping.length, paymentSupplierMapping.length, ledgerSupplierMapping.length]
  const warnings = []
  if (!poNo) warnings.push('当前正式付款凭证缺少来源采购订单号，无法定位多供应商采购订单。')
  if (!purchaseOrderSupplierCount) warnings.push('未从 SCM 采购订单明细读取到供应商列表，请核对来源订单是否仍在当前浏览器数据中。')
  if (purchaseOrderSupplierCount > 1 && paymentSupplierMapping.length === 1) warnings.push(`${poNo || '当前采购订单'} 采购订单存在 ${purchaseOrderSupplierCount} 个供应商，但模拟付款链只有 1 个付款供应商。`)
  if (purchaseOrderSupplierCount > 1 && payableSupplierMapping.length === 1) warnings.push(`${poNo || '当前采购订单'} 采购订单存在 ${purchaseOrderSupplierCount} 个供应商，但模拟应付链只有 1 个应付供应商。`)
  const sameCount = counts.every((count) => count === purchaseOrderSupplierCount && count > 0)
  const fracture = purchaseOrderSupplierCount > 0 && !sameCount
  const status = fracture ? '供应商链断裂' : (sameCount ? '通过' : '需核对')
  return {
    purchaseOrderNo: poNo,
    purchaseOrderSupplierCount,
    purchaseOrderSuppliers,
    receiptSupplierMapping,
    inventorySupplierMapping,
    payableSupplierMapping,
    paymentSupplierMapping,
    ledgerSupplierMapping,
    supplierChainConsistencyStatus: status,
    supplierChainConsistencyWarnings: warnings,
    supplierChainConsistencyConclusion: fracture
      ? '问题原因定位：当前模拟P2P模型仍以正式付款凭证的单一 supplierId / supplierName 作为应付、付款和模拟总账供应商来源，无法完整继承多供应商采购订单明细。'
      : (sameCount ? '采购订单供应商数量、应付供应商数量、付款供应商数量一致。' : '当前数据不足以判断多供应商链路是否完整，请先确认来源采购订单明细。'),
  }
}

function multiSupplierP2PSummary(row = {}) {
  return buildMultiSupplierP2PSummary(row || {})
}

function supplierChainConsistencyType(status) {
  if (status === '通过') return 'success'
  if (status === '供应商链断裂') return 'danger'
  return 'warning'
}

function buildMultiSupplierSettlementSummary(row = {}) {
  const diagnostic = buildMultiSupplierP2PSummary(row)
  const amount = simulationAmount(row)
  const voucherNo = row?.formalVoucherNo || row?.voucherNo || '未指定付款凭证'
  const sourceLines = diagnostic.purchaseOrderSuppliers.length
    ? diagnostic.purchaseOrderSuppliers
    : singleSupplierMapping(row, amount)
  const supplierSettlementLines = sourceLines.map((item) => ({
    supplierId: item.supplierId || item.supplierKey || '',
    supplierName: item.supplierName || item.displayName || '未指定供应商',
    purchaseAmount: item.purchaseAmount || item.amount || 0,
    receiptAmount: item.receiptAmount || item.amount || 0,
    inventoryAmount: item.inventoryAmount || item.amount || 0,
    payableAmount: item.payableAmount || item.amount || 0,
    paymentAmount: item.paymentAmount || item.amount || 0,
    ledgerAmount: item.paymentAmount || item.payableAmount || item.amount || 0,
  }))
  const purchaseSupplierMapping = supplierSettlementLines.map((line) => ({
    purchaseOrderNo: diagnostic.purchaseOrderNo || row?.sourcePurchaseOrderNo || '',
    supplierId: line.supplierId,
    supplierName: line.supplierName,
    lineAmount: line.purchaseAmount,
    materialCount: line.purchaseAmount > 0 ? 1 : 0,
  }))
  const supplierPayableMapping = supplierSettlementLines.map((line) => ({
    supplierId: line.supplierId,
    supplierName: line.supplierName,
    payableAmount: line.payableAmount,
    payableStatus: '未来按供应商独立形成应付对象',
  }))
  const supplierPaymentMapping = supplierSettlementLines.map((line, index) => ({
    supplierId: line.supplierId,
    supplierName: line.supplierName,
    paymentAmount: line.paymentAmount,
    paymentVoucherNo: `${voucherNo}-S${index + 1}`,
  }))
  const supplierLedgerMapping = supplierSettlementLines.map((line) => ({
    supplierId: line.supplierId,
    supplierName: line.supplierName,
    debitAccount: `2202 应付账款-${line.supplierName || line.supplierId || '供应商'}`,
    creditAccount: '1002 银行存款',
    amount: line.ledgerAmount,
  }))
  const supplierCount = supplierSettlementLines.length
  const settlementMode = supplierCount > 1 ? 'multi_supplier' : 'single_supplier'
  const warnings = [
    '本轮只设计多供应商结算模型，不生成真实应付或真实付款。',
    '未来应以采购订单明细供应商为拆分来源，每个供应商独立形成应付、付款和供应商往来。',
  ]
  if (diagnostic.supplierChainConsistencyStatus === '供应商链断裂') warnings.push('当前诊断已发现供应商链断裂，后续业务需要补齐多供应商拆分生成规则。')
  if (supplierCount <= 1) warnings.push('当前模型仅识别到一个供应商，若来源采购订单实际为多供应商，请继续核对采购订单明细继承。')
  const ready = supplierCount > 0
  const blocked = !ready
  return {
    multiSupplierSettlementStatus: blocked ? 'blocked' : (warnings.length ? 'warning' : 'ready'),
    multiSupplierSettlementStatusText: blocked ? '结算模型阻断' : (warnings.length ? '结算模型有提醒' : '结算模型就绪'),
    multiSupplierSettlementReady: ready,
    multiSupplierSettlementBlocked: blocked,
    multiSupplierSettlementWarnings: warnings,
    multiSupplierSettlementConclusion: ready
      ? `多供应商结算模型已建立：${settlementMode}，供应商数量 ${supplierCount}。本轮只做设计，不写业务数据。`
      : '多供应商结算模型缺少供应商拆分来源，暂不能形成结算设计行。',
    multiSupplierSettlementSummary: {
      settlementMode,
      supplierCount,
      supplierSettlementReady: ready,
      supplierSettlementWarnings: warnings,
    },
    purchaseSupplierMapping,
    supplierSettlementLines,
    supplierPayableMapping,
    supplierPaymentMapping,
    supplierLedgerMapping,
  }
}

function multiSupplierSettlementSummary(row = {}) {
  return buildMultiSupplierSettlementSummary(row || {})
}

function multiSupplierSettlementType(status) {
  if (status === 'ready') return 'success'
  if (status === 'blocked') return 'danger'
  if (status === 'warning') return 'warning'
  return 'info'
}

async function handleMultiSupplierSettlementCheck(row = {}) {
  const summary = multiSupplierSettlementSummary(row)
  const lines = [
    `结算模式：${summary.multiSupplierSettlementSummary.settlementMode}`,
    `供应商数量：${summary.multiSupplierSettlementSummary.supplierCount}`,
    `供应商拆分行：${summary.supplierSettlementLines.map((item) => `${item.supplierName || item.supplierId} 采购${item.purchaseAmount}/应付${item.payableAmount}/付款${item.paymentAmount}`).join('；') || '无'}`,
    `应付拆分：${summary.supplierPayableMapping.map((item) => `${item.supplierName || item.supplierId}:${item.payableAmount}`).join('；') || '无'}`,
    `付款拆分：${summary.supplierPaymentMapping.map((item) => `${item.supplierName || item.supplierId}:${item.paymentAmount}`).join('；') || '无'}`,
    `模拟总账拆分：${summary.supplierLedgerMapping.map((item) => `${item.supplierName || item.supplierId}:${item.amount}`).join('；') || '无'}`,
    `结论：${summary.multiSupplierSettlementConclusion}`,
    '本次检查只读，不修改采购订单、不生成真实应付、不生成真实付款、不写总账、不写 localStorage。',
  ]
  await ElMessageBox.alert(lines.join('\n'), '多供应商结算模型检查', {
    confirmButtonText: '知道了',
    type: summary.multiSupplierSettlementBlocked ? 'warning' : 'success',
  })
  notify('已完成只读多供应商结算模型检查；未修改任何业务数据。')
}

function buildP2PDataValidationSummary(row = {}) {
  const settlement = buildMultiSupplierSettlementSummary(row)
  const supplierDiagnostic = buildMultiSupplierP2PSummary(row)
  const roundAmount = (value) => Math.round(Number(value || 0) * 100) / 100
  const sumAmount = (items, key) => roundAmount((items || []).reduce((total, item) => total + Number(item?.[key] || 0), 0))
  const amountDifference = (values = []) => {
    const nums = values.map((value) => Number(value || 0)).filter((value) => Number.isFinite(value))
    if (!nums.length) return 0
    return roundAmount(Math.max(...nums) - Math.min(...nums))
  }
  const purchaseOrderNo = supplierDiagnostic.purchaseOrderNo || row?.sourcePurchaseOrderNo || settlement.purchaseSupplierMapping?.[0]?.purchaseOrderNo || '未指定采购订单'
  const supplierList = (settlement.purchaseSupplierMapping || []).map((item) => ({
    supplierId: item.supplierId || '',
    supplierName: item.supplierName || item.supplierId || '未指定供应商',
  }))
  const purchaseAmount = sumAmount(settlement.purchaseSupplierMapping, 'lineAmount')
  const receiptAmount = sumAmount(settlement.supplierSettlementLines, 'receiptAmount')
  const inventoryAmount = sumAmount(settlement.supplierSettlementLines, 'inventoryAmount')
  const payableAmount = sumAmount(settlement.supplierPayableMapping, 'payableAmount')
  const paymentAmount = sumAmount(settlement.supplierPaymentMapping, 'paymentAmount')
  const poDifference = amountDifference([purchaseAmount, receiptAmount, inventoryAmount, payableAmount, paymentAmount])
  const purchaseSupplierCount = supplierDiagnostic.purchaseOrderSupplierCount || supplierList.length
  const paymentSupplierCount = (settlement.supplierPaymentMapping || []).length
  const supplierChainRisk = purchaseSupplierCount > 0 && paymentSupplierCount > 0 && purchaseSupplierCount !== paymentSupplierCount
  const purchaseOrderValidation = [{
    poNo: purchaseOrderNo,
    supplierCount: purchaseSupplierCount,
    supplierList,
    purchaseAmount,
    receiptAmount,
    inventoryAmount,
    payableAmount,
    paymentAmount,
    difference: poDifference,
    validationStatus: poDifference > 0.01 ? '金额不一致' : (supplierChainRisk ? '供应商链路风险' : '通过'),
  }]
  const supplierMap = new Map()
  ;(settlement.supplierSettlementLines || []).forEach((line) => {
    const supplierKey = line.supplierId || line.supplierName || 'UNKNOWN_SUPPLIER'
    const current = supplierMap.get(supplierKey) || {
      supplierId: line.supplierId || '',
      supplierName: line.supplierName || '未指定供应商',
      orderCount: 0,
      purchaseTotal: 0,
      receiptTotal: 0,
      inventoryTotal: 0,
      payableTotal: 0,
      paymentTotal: 0,
      balance: 0,
      difference: 0,
      validationStatus: '通过',
    }
    current.orderCount += 1
    current.purchaseTotal = roundAmount(current.purchaseTotal + Number(line.purchaseAmount || 0))
    current.receiptTotal = roundAmount(current.receiptTotal + Number(line.receiptAmount || 0))
    current.inventoryTotal = roundAmount(current.inventoryTotal + Number(line.inventoryAmount || 0))
    current.payableTotal = roundAmount(current.payableTotal + Number(line.payableAmount || 0))
    current.paymentTotal = roundAmount(current.paymentTotal + Number(line.paymentAmount || 0))
    current.balance = roundAmount(current.payableTotal - current.paymentTotal)
    current.difference = amountDifference([
      current.purchaseTotal,
      current.receiptTotal,
      current.inventoryTotal,
      current.payableTotal,
      current.paymentTotal,
    ])
    current.validationStatus = current.difference > 0.01 ? '金额不一致' : '通过'
    supplierMap.set(supplierKey, current)
  })
  const supplierValidation = Array.from(supplierMap.values())
  const riskWarnings = []
  if (supplierChainRisk) {
    riskWarnings.push(`供应商链路风险：采购订单供应商数量 ${purchaseSupplierCount} 与付款供应商数量 ${paymentSupplierCount} 不一致。`)
  }
  if (poDifference > 0.01) {
    riskWarnings.push(`采购订单维度金额不一致：采购、收货、入库、应付、付款最大差额 ${poDifference}。`)
  }
  supplierValidation
    .filter((item) => item.difference > 0.01)
    .forEach((item) => riskWarnings.push(`供应商维度金额不一致：${item.supplierName || item.supplierId} 差额 ${item.difference}。`))
  if (!supplierValidation.length) {
    riskWarnings.push('当前缺少供应商维度验证数据，只能展示验证模型。')
  }
  const validationStatus = riskWarnings.length ? '有风险' : '通过'
  return {
    purchaseOrderValidation,
    supplierValidation,
    p2pDataValidation: {
      validationStatus,
      riskWarnings,
      conclusion: riskWarnings.length
        ? '多供应商P2P数据验证发现风险，本轮只提示问题原因，不修复业务模型。'
        : '采购订单维度与供应商维度金额一致，未发现供应商链路风险。',
    },
  }
}

function p2pDataValidationSummary(row = {}) {
  return buildP2PDataValidationSummary(row || {})
}

function p2pDataValidationType(status) {
  if (status === '通过') return 'success'
  if (status === '有风险') return 'warning'
  return 'info'
}

async function handleP2PDataValidationCheck(row = {}) {
  const summary = p2pDataValidationSummary(row)
  const poLines = summary.purchaseOrderValidation.map((item) => `${item.poNo}：供应商${item.supplierCount}个，采购${item.purchaseAmount}/收货${item.receiptAmount}/入库${item.inventoryAmount}/应付${item.payableAmount}/付款${item.paymentAmount}，差额${item.difference}，状态${item.validationStatus}`)
  const supplierLines = summary.supplierValidation.map((item) => `${item.supplierName || item.supplierId}：订单${item.orderCount}个，采购${item.purchaseTotal}/收货${item.receiptTotal}/入库${item.inventoryTotal}/应付${item.payableTotal}/付款${item.paymentTotal}，差额${item.difference}，状态${item.validationStatus}`)
  const lines = [
    '采购订单维度：',
    poLines.join('\n') || '暂无采购订单维度验证数据。',
    '',
    '供应商维度：',
    supplierLines.join('\n') || '暂无供应商维度验证数据。',
    '',
    `数据一致性检查：${summary.p2pDataValidation.validationStatus}`,
    summary.p2pDataValidation.conclusion,
    ...(summary.p2pDataValidation.riskWarnings.length ? ['', '风险提示：', ...summary.p2pDataValidation.riskWarnings] : []),
    '',
    '本次检查只读，不创建数据、不修改采购订单、不修改付款状态、不写总账、不写 localStorage。',
  ]
  await ElMessageBox.alert(lines.join('\n'), '多供应商P2P数据验证检查', {
    confirmButtonText: '知道了',
    type: summary.p2pDataValidation.validationStatus === '通过' ? 'success' : 'warning',
  })
  notify('已完成只读多供应商P2P数据验证；未修改任何业务数据。')
}

async function handleSimulationP2PScenarioCheck(row = {}) {
  const summary = simulationP2PScenarioSummary(row)
  const flow = summary.simulationP2PFlow
  const lines = [
    `验证状态：${summary.simulationP2PValidationStatusText}`,
    `请购：${flow.request.requestId}，金额 ${flow.request.requestAmount}`,
    `采购订单：${flow.purchaseOrder.purchaseOrderNo}，金额 ${flow.purchaseOrder.orderAmount}`,
    `收货：${flow.receipt.receiptNo}，金额 ${flow.receipt.receivedAmount}`,
    `入库：${flow.inventory.warehouseId}，影响金额 ${flow.inventory.inventoryAmount}`,
    `应付：${flow.payable.payableAmount}，${flow.payable.supplierBalanceImpact}`,
    `付款凭证：${flow.payment.paymentVoucherNo}，金额 ${flow.payment.paymentAmount}`,
    `模拟总账：借方 ${flow.ledger.simulationDebitTotal}，贷方 ${flow.ledger.simulationCreditTotal}`,
    `阻断原因：${summary.simulationP2PValidationBlockedReasons.length ? summary.simulationP2PValidationBlockedReasons.join('；') : '无'}`,
    '本次检查只读，不生成业务数据，不写真实总账，不修改正式付款凭证状态，不写 localStorage。',
  ]
  await ElMessageBox.alert(lines.join('\n'), '模拟P2P业务链检查', {
    confirmButtonText: '知道了',
    type: summary.simulationP2PValidationBlocked ? 'warning' : 'success',
  })
  notify('已完成只读模拟 P2P 业务链检查；未生成业务数据，未写 localStorage。')
}

async function handleFormalPostingFlowCheck(row) {
  const summary = formalPostingFlowSummary(row)
  const lines = [
    `当前建议阶段：${summary.formalPostingFlowStatusText}`,
    `是否可进入下一阶段：${summary.formalPostingFlowCanMoveNext ? '是，仅表示入口就绪' : '否，仍有阻断条件'}`,
    `状态机结论：${summary.formalPostingFlowConclusion}`,
    `阻断原因：${summary.formalPostingFlowBlockedReasons.length ? summary.formalPostingFlowBlockedReasons.join('；') : '无'}`,
    `提醒项：${summary.formalPostingFlowWarnings.join('；')}`,
    '本次预检查只读，不改变 postingStatus、ledgerStatus、paymentWriteOffStatus，不写 formalPostedAt / formalPostedBy，不生成 ledgerEntryId / ledgerEntryNo，不写总账、不核销、不生成银行流水。',
  ]
  await ElMessageBox.alert(lines.join('\n'), '正式过账状态机预检查', {
    confirmButtonText: '知道了',
    type: summary.formalPostingFlowCanMoveNext ? 'success' : 'warning',
  })
  notify('已完成状态机预检查；未改变任何正式财务字段。')
}

async function handleFormalPostingPreExecuteCheck(row) {
  const summary = formalPostingPreExecuteSummary(row)
  const lines = [
    `预执行检查状态：${summary.formalPostingPreExecuteStatusText}`,
    `是否可进入后续正式过账确认设计：${summary.formalPostingPreExecuteReady ? '是' : '否'}`,
    `检查结论：${summary.formalPostingPreExecuteConclusion}`,
    `阻断原因：${summary.formalPostingPreExecuteBlockedReasons.length ? summary.formalPostingPreExecuteBlockedReasons.join('；') : '无'}`,
    `提醒项：${summary.formalPostingPreExecuteWarnings.length ? summary.formalPostingPreExecuteWarnings.join('；') : '无'}`,
    '本次预执行检查只读，不改变 postingStatus、ledgerStatus、paymentWriteOffStatus，不写 formalPostedAt / formalPostedBy，不生成 ledgerEntryId / ledgerEntryNo，不写总账、不核销、不生成银行流水、不写正式过账日志。',
  ]
  await ElMessageBox.alert(lines.join('\n'), '正式过账预执行检查', {
    confirmButtonText: '知道了',
    type: summary.formalPostingPreExecuteBlocked ? 'warning' : 'success',
  })
  notify('已完成预执行检查；未改变任何正式财务字段。')
}

async function handleFormalPostingLockCheck(row) {
  const summary = formalPostingLockSummary(row)
  const lines = [
    `确认前锁定状态：${summary.formalPostingLockStatusText}`,
    `是否可进入确认前锁定设计：${summary.formalPostingLockReady ? '是' : '否'}`,
    `锁定结论：${summary.formalPostingLockConclusion}`,
    `阻断原因：${summary.formalPostingLockBlockedReasons.length ? summary.formalPostingLockBlockedReasons.join('；') : '无'}`,
    `提醒项：${summary.formalPostingLockWarnings.length ? summary.formalPostingLockWarnings.join('；') : '无'}`,
    '本次锁定预检查只读，不改变 postingStatus、ledgerStatus、paymentWriteOffStatus，不写 formalPostedAt / formalPostedBy，不生成 ledgerEntryId / ledgerEntryNo，不写总账、不核销、不生成银行流水、不写正式过账日志、不真实锁定凭证或会计期间。',
  ]
  await ElMessageBox.alert(lines.join('\n'), '正式过账确认前锁定预检查', {
    confirmButtonText: '知道了',
    type: summary.formalPostingLockBlocked ? 'warning' : 'success',
  })
  notify('已完成锁定预检查；未改变任何正式财务字段，未真实锁定凭证或会计期间。')
}

async function handleFormalPostingConfirmCheck(row) {
  const summary = formalPostingConfirmSummary(row)
  const lines = [
    `最终确认状态：${summary.formalPostingConfirmStatusText}`,
    `是否可进入最终确认设计：${summary.formalPostingConfirmReady ? '是' : '否'}`,
    `最终确认结论：${summary.formalPostingConfirmConclusion}`,
    `阻断原因：${summary.formalPostingConfirmBlockedReasons.length ? summary.formalPostingConfirmBlockedReasons.join('；') : '无'}`,
    `提醒项：${summary.formalPostingConfirmWarnings.length ? summary.formalPostingConfirmWarnings.join('；') : '无'}`,
    '本次最终确认检查只读，不改变 postingStatus、ledgerStatus、paymentWriteOffStatus，不写 formalPostedAt / formalPostedBy，不生成 ledgerEntryId / ledgerEntryNo，不写总账、不核销、不生成银行流水、不写正式过账日志、不真实锁定凭证或会计期间。',
  ]
  await ElMessageBox.alert(lines.join('\n'), '正式过账最终确认检查', {
    confirmButtonText: '知道了',
    type: summary.formalPostingConfirmBlocked ? 'warning' : 'success',
  })
  notify('已完成最终确认检查；未执行正式过账，未写总账，未改变任何正式财务字段。')
}

function diagnosticValue(value, fallback = null) {
  if (value === undefined || value === '') return fallback
  return value
}

function diagnosticArray(value) {
  return Array.isArray(value) ? value : []
}

function buildVoucherDiagnosticPayload(row = {}) {
  const flowSummary = formalPostingFlowSummary(row)
  const preExecuteSummary = formalPostingPreExecuteSummary(row)
  const lockSummary = formalPostingLockSummary(row)
  const confirmSummary = formalPostingConfirmSummary(row)
  const initToolSummary = buildSeedDataInitToolSummary()
  const validatorSummary = buildBalanceValidatorSummary()
  const ledgerReviewSummary = buildLedgerPostingReviewSummary()
  const simulationSummary = buildSimulationLedgerSummary(row)
  const simulationValidationSummary = buildSimulationLedgerValidationSummary(row)
  const simulationMappingSummary = buildSimulationDataMappingSummary(row)
  const simulationP2PSummary = buildSimulationP2PScenarioSummary(row)
  const multiSupplierSummary = buildMultiSupplierP2PSummary(row)
  const settlementSummary = buildMultiSupplierSettlementSummary(row)
  const dataValidationSummary = buildP2PDataValidationSummary(row)
  const copiedAt = new Date().toISOString()
  return {
    version: 'V1.13.19',
    type: 'formal-payment-voucher-diagnostic',
    copiedAt,
    voucher: {
      id: diagnosticValue(row.id),
      voucherNo: diagnosticValue(row.formalVoucherNo || row.voucherNo),
      sourceReviewNo: diagnosticValue(row.sourceVoucherReviewNo),
      supplierName: diagnosticValue(row.supplierName),
      amount: diagnosticValue(row.totalVoucherAmount ?? row.amount, 0),
      voucherStatus: diagnosticValue(row.formalVoucherStatus),
      voucherStatusText: diagnosticValue(row.formalVoucherStatusText || formalStatusLabel(row.formalVoucherStatus)),

      postingPreReviewStatus: diagnosticValue(row.postingPreReviewStatus),
      postingPreReviewStatusText: diagnosticValue(row.postingPreReviewStatusText || postingPreReviewStatusLabel(row.postingPreReviewStatus)),
      postingPreReviewBlockedCount: diagnosticValue(row.postingPreReviewBlockedCount, 0),
      postingPreReviewWarningCount: diagnosticValue(row.postingPreReviewWarningCount, 0),
      postingPreReviewConclusion: diagnosticValue(row.postingPreReviewConclusion),

      postingStatus: diagnosticValue(row.postingStatus),
      postingStatusText: diagnosticValue(row.postingStatusText || getPostingStatusLabel(row.postingStatus)),
      postingReady: diagnosticValue(row.postingReady, false),
      postingBlocked: diagnosticValue(row.postingBlocked, false),
      postingBlockedReasons: diagnosticArray(row.postingBlockedReasons),
      postingWarnings: diagnosticArray(row.postingWarnings),

      postingActionStatus: diagnosticValue(row.postingActionStatus),
      postingActionStatusText: diagnosticValue(row.postingActionStatusText),
      postingSimulated: diagnosticValue(row.postingSimulated, false),
      postingSimulatedAt: diagnosticValue(row.postingSimulatedAt),
      postingSimulatedBy: diagnosticValue(row.postingSimulatedBy),
      postingActionConclusion: diagnosticValue(row.postingActionConclusion),

      formalPostingStatus: diagnosticValue(row.formalPostingStatus),
      formalPostingStatusText: diagnosticValue(row.formalPostingStatusText),
      formalPostingReady: diagnosticValue(row.formalPostingReady, false),
      formalPostingBlocked: diagnosticValue(row.formalPostingBlocked, false),
      formalPostingBlockedReasons: diagnosticArray(row.formalPostingBlockedReasons),
      formalPostingWarnings: diagnosticArray(row.formalPostingWarnings),
      formalPostingReviewConclusion: diagnosticValue(row.formalPostingReviewConclusion),

      formalPostingFlowStatus: diagnosticValue(flowSummary.formalPostingFlowStatus),
      formalPostingFlowStatusText: diagnosticValue(flowSummary.formalPostingFlowStatusText),
      formalPostingFlowStepIndex: diagnosticValue(flowSummary.formalPostingFlowStepIndex, 0),
      formalPostingFlowCanMoveNext: diagnosticValue(flowSummary.formalPostingFlowCanMoveNext, false),
      formalPostingFlowBlockedReasons: diagnosticArray(flowSummary.formalPostingFlowBlockedReasons),
      formalPostingFlowWarnings: diagnosticArray(flowSummary.formalPostingFlowWarnings),
      formalPostingFlowConclusion: diagnosticValue(flowSummary.formalPostingFlowConclusion),

      formalPostingPreExecuteStatus: diagnosticValue(preExecuteSummary.formalPostingPreExecuteStatus),
      formalPostingPreExecuteStatusText: diagnosticValue(preExecuteSummary.formalPostingPreExecuteStatusText),
      formalPostingPreExecuteReady: diagnosticValue(preExecuteSummary.formalPostingPreExecuteReady, false),
      formalPostingPreExecuteBlocked: diagnosticValue(preExecuteSummary.formalPostingPreExecuteBlocked, false),
      formalPostingPreExecuteBlockedReasons: diagnosticArray(preExecuteSummary.formalPostingPreExecuteBlockedReasons),
      formalPostingPreExecuteWarnings: diagnosticArray(preExecuteSummary.formalPostingPreExecuteWarnings),
      formalPostingPreExecuteConclusion: diagnosticValue(preExecuteSummary.formalPostingPreExecuteConclusion),

      formalPostingLockStatus: diagnosticValue(lockSummary.formalPostingLockStatus),
      formalPostingLockStatusText: diagnosticValue(lockSummary.formalPostingLockStatusText),
      formalPostingLockReady: diagnosticValue(lockSummary.formalPostingLockReady, false),
      formalPostingLockBlocked: diagnosticValue(lockSummary.formalPostingLockBlocked, false),
      formalPostingLockBlockedReasons: diagnosticArray(lockSummary.formalPostingLockBlockedReasons),
      formalPostingLockWarnings: diagnosticArray(lockSummary.formalPostingLockWarnings),
      formalPostingLockConclusion: diagnosticValue(lockSummary.formalPostingLockConclusion),

      formalPostingConfirmStatus: diagnosticValue(confirmSummary.formalPostingConfirmStatus),
      formalPostingConfirmStatusText: diagnosticValue(confirmSummary.formalPostingConfirmStatusText),
      formalPostingConfirmReady: diagnosticValue(confirmSummary.formalPostingConfirmReady, false),
      formalPostingConfirmBlocked: diagnosticValue(confirmSummary.formalPostingConfirmBlocked, false),
      formalPostingConfirmBlockedReasons: diagnosticArray(confirmSummary.formalPostingConfirmBlockedReasons),
      formalPostingConfirmWarnings: diagnosticArray(confirmSummary.formalPostingConfirmWarnings),
      formalPostingConfirmConclusion: diagnosticValue(confirmSummary.formalPostingConfirmConclusion),

      seedDataPlanStatus: 'designed',
      seedDataPlanStatusText: '基础验证数据体系设计已建立',
      seedDataPlanReady: true,
      seedDataPlanBlocked: false,
      seedDataPlanWarnings: [
        '本轮只做设计，不初始化基础数据。',
        '本轮不写 localStorage，不覆盖用户当前数据。',
        '真实总账写入前必须先完成基础验证数据隔离和验证器设计。',
      ],
      seedDataPlanConclusion: 'V1.13.16 仅建立基础验证数据体系设计，不生成 chartOfAccounts、openingBalances、bankAccounts、inventoryOpeningBalances、supplierBalances 等真实数据。',
      seedDataDomains: seedDataPlanDomains,
      seedDataIsolationRules: seedDataPlanIsolationRules,
      seedDataNextVersions: seedDataPlanNextVersions,
      seedDataInitToolStatus: diagnosticValue(initToolSummary.seedDataInitToolStatus),
      seedDataInitToolStatusText: diagnosticValue(initToolSummary.seedDataInitToolStatusText),
      seedDataInitToolReady: diagnosticValue(initToolSummary.seedDataInitToolReady, false),
      seedDataInitToolBlocked: diagnosticValue(initToolSummary.seedDataInitToolBlocked, false),
      seedDataInitToolBlockedReasons: diagnosticArray(initToolSummary.seedDataInitToolBlockedReasons),
      seedDataInitToolWarnings: diagnosticArray(initToolSummary.seedDataInitToolWarnings),
      seedDataInitToolConclusion: diagnosticValue(initToolSummary.seedDataInitToolConclusion),
      seedDataInitNamespaces: diagnosticArray(initToolSummary.seedDataInitNamespaces),
      seedDataInitPreviewDomains: diagnosticArray(initToolSummary.seedDataInitPreviewDomains),
      seedDataInitSafetyRules: diagnosticArray(initToolSummary.seedDataInitSafetyRules),
      balanceValidatorStatus: diagnosticValue(validatorSummary.balanceValidatorStatus),
      balanceValidatorStatusText: diagnosticValue(validatorSummary.balanceValidatorStatusText),
      balanceValidatorReady: diagnosticValue(validatorSummary.balanceValidatorReady, false),
      balanceValidatorBlocked: diagnosticValue(validatorSummary.balanceValidatorBlocked, false),
      balanceValidatorWarnings: diagnosticArray(validatorSummary.balanceValidatorWarnings),
      balanceValidatorConclusion: diagnosticValue(validatorSummary.balanceValidatorConclusion),
      debitTotal: diagnosticValue(validatorSummary.debitTotal, 0),
      creditTotal: diagnosticValue(validatorSummary.creditTotal, 0),
      balanceDifference: diagnosticValue(validatorSummary.balanceDifference, 0),
      isBalanced: diagnosticValue(validatorSummary.isBalanced, false),
      balanceConclusion: diagnosticValue(validatorSummary.balanceConclusion),
      ledgerBalanceCheckStatus: diagnosticValue(validatorSummary.ledgerBalanceCheckStatus),
      ledgerBalanceConclusion: diagnosticValue(validatorSummary.ledgerBalanceConclusion),
      bankBalanceCheckStatus: diagnosticValue(validatorSummary.bankBalanceCheckStatus),
      bankBalanceDifference: diagnosticValue(validatorSummary.bankBalanceDifference, 0),
      bankBalanceConclusion: diagnosticValue(validatorSummary.bankBalanceConclusion),
      supplierBalanceCheckStatus: diagnosticValue(validatorSummary.supplierBalanceCheckStatus),
      supplierBalanceDifference: diagnosticValue(validatorSummary.supplierBalanceDifference, 0),
      supplierBalanceConclusion: diagnosticValue(validatorSummary.supplierBalanceConclusion),
      inventoryBalanceCheckStatus: diagnosticValue(validatorSummary.inventoryBalanceCheckStatus),
      inventoryQtyDifference: diagnosticValue(validatorSummary.inventoryQtyDifference, 0),
      inventoryAmountDifference: diagnosticValue(validatorSummary.inventoryAmountDifference, 0),
      inventoryBalanceConclusion: diagnosticValue(validatorSummary.inventoryBalanceConclusion),
      reportCheckStatus: diagnosticValue(validatorSummary.reportCheckStatus),
      reportCheckConclusion: diagnosticValue(validatorSummary.reportCheckConclusion),
      ledgerPostingReviewStatus: diagnosticValue(ledgerReviewSummary.ledgerPostingReviewStatus),
      ledgerPostingReviewStatusText: diagnosticValue(ledgerReviewSummary.ledgerPostingReviewStatusText),
      ledgerPostingReviewReady: diagnosticValue(ledgerReviewSummary.ledgerPostingReviewReady, false),
      ledgerPostingReviewBlocked: diagnosticValue(ledgerReviewSummary.ledgerPostingReviewBlocked, false),
      ledgerPostingReviewWarnings: diagnosticArray(ledgerReviewSummary.ledgerPostingReviewWarnings),
      ledgerPostingReviewConclusion: diagnosticValue(ledgerReviewSummary.ledgerPostingReviewConclusion),
      financialDataCheckStatus: diagnosticValue(ledgerReviewSummary.financialDataCheckStatus),
      financialDataCheckConclusion: diagnosticValue(ledgerReviewSummary.financialDataCheckConclusion),
      ledgerPostingDebitTotal: diagnosticValue(ledgerReviewSummary.ledgerPostingDebitTotal, 0),
      ledgerPostingCreditTotal: diagnosticValue(ledgerReviewSummary.ledgerPostingCreditTotal, 0),
      ledgerPostingDifference: diagnosticValue(ledgerReviewSummary.ledgerPostingDifference, 0),
      ledgerPostingBalanced: diagnosticValue(ledgerReviewSummary.ledgerPostingBalanced, false),
      balanceCheckStatus: diagnosticValue(ledgerReviewSummary.balanceCheckStatus),
      balanceCheckConclusion: diagnosticValue(ledgerReviewSummary.balanceCheckConclusion),
      accountCompletenessStatus: diagnosticValue(ledgerReviewSummary.accountCompletenessStatus),
      accountCompletenessConclusion: diagnosticValue(ledgerReviewSummary.accountCompletenessConclusion),
      periodCheckStatus: diagnosticValue(ledgerReviewSummary.periodCheckStatus),
      periodCheckConclusion: diagnosticValue(ledgerReviewSummary.periodCheckConclusion),
      postingPermissionStatus: diagnosticValue(ledgerReviewSummary.postingPermissionStatus),
      postingPermissionConclusion: diagnosticValue(ledgerReviewSummary.postingPermissionConclusion),
      auditCheckStatus: diagnosticValue(ledgerReviewSummary.auditCheckStatus),
      auditCheckConclusion: diagnosticValue(ledgerReviewSummary.auditCheckConclusion),
      ledgerEntryStructureStatus: diagnosticValue(ledgerReviewSummary.ledgerEntryStructureStatus),
      ledgerEntryStructureConclusion: diagnosticValue(ledgerReviewSummary.ledgerEntryStructureConclusion),
      rollbackCapabilityStatus: diagnosticValue(ledgerReviewSummary.rollbackCapabilityStatus),
      rollbackCapabilityConclusion: diagnosticValue(ledgerReviewSummary.rollbackCapabilityConclusion),
      simulationLedgerStatus: diagnosticValue(simulationSummary.simulationLedgerStatus),
      simulationLedgerStatusText: diagnosticValue(simulationSummary.simulationLedgerStatusText),
      simulationLedgerReady: diagnosticValue(simulationSummary.simulationLedgerReady, false),
      simulationLedgerBlocked: diagnosticValue(simulationSummary.simulationLedgerBlocked, false),
      simulationLedgerWarnings: diagnosticArray(simulationSummary.simulationLedgerWarnings),
      simulationLedgerConclusion: diagnosticValue(simulationSummary.simulationLedgerConclusion),
      simulationLedgerEntries: diagnosticArray(simulationSummary.simulationLedgerEntries),
      simulationDebitTotal: diagnosticValue(simulationSummary.simulationDebitTotal, 0),
      simulationCreditTotal: diagnosticValue(simulationSummary.simulationCreditTotal, 0),
      simulationDifference: diagnosticValue(simulationSummary.simulationDifference, 0),
      simulationBalanced: diagnosticValue(simulationSummary.simulationBalanced, false),
      simulationBalanceChanges: diagnosticArray(simulationSummary.simulationBalanceChanges),
      simulationReportImpact: diagnosticArray(simulationSummary.simulationReportImpact),
      simulationLedgerValidationStatus: diagnosticValue(simulationValidationSummary.simulationLedgerValidationStatus),
      simulationLedgerValidationStatusText: diagnosticValue(simulationValidationSummary.simulationLedgerValidationStatusText),
      simulationLedgerValidationReady: diagnosticValue(simulationValidationSummary.simulationLedgerValidationReady, false),
      simulationLedgerValidationBlocked: diagnosticValue(simulationValidationSummary.simulationLedgerValidationBlocked, false),
      simulationLedgerValidationWarnings: diagnosticArray(simulationValidationSummary.simulationLedgerValidationWarnings),
      simulationLedgerValidationConclusion: diagnosticValue(simulationValidationSummary.simulationLedgerValidationConclusion),
      simulationEntryCheckStatus: diagnosticValue(simulationValidationSummary.simulationEntryCheckStatus),
      simulationEntryCheckConclusion: diagnosticValue(simulationValidationSummary.simulationEntryCheckConclusion),
      simulationDebitCreditCheckStatus: diagnosticValue(simulationValidationSummary.simulationDebitCreditCheckStatus),
      simulationDebitCreditCheckConclusion: diagnosticValue(simulationValidationSummary.simulationDebitCreditCheckConclusion),
      simulationAccountDirectionCheckStatus: diagnosticValue(simulationValidationSummary.simulationAccountDirectionCheckStatus),
      simulationAccountDirectionCheckConclusion: diagnosticValue(simulationValidationSummary.simulationAccountDirectionCheckConclusion),
      simulationAmountCheckStatus: diagnosticValue(simulationValidationSummary.simulationAmountCheckStatus),
      simulationAmountDifference: diagnosticValue(simulationValidationSummary.simulationAmountDifference, 0),
      simulationAmountCheckConclusion: diagnosticValue(simulationValidationSummary.simulationAmountCheckConclusion),
      simulationBalanceCheckStatus: diagnosticValue(simulationValidationSummary.simulationBalanceCheckStatus),
      simulationBalanceCheckConclusion: diagnosticValue(simulationValidationSummary.simulationBalanceCheckConclusion),
      simulationReportCheckStatus: diagnosticValue(simulationValidationSummary.simulationReportCheckStatus),
      simulationReportCheckConclusion: diagnosticValue(simulationValidationSummary.simulationReportCheckConclusion),
      simulationValidationDifference: diagnosticValue(simulationValidationSummary.simulationValidationDifference, 0),
      simulationValidationBalanced: diagnosticValue(simulationValidationSummary.simulationValidationBalanced, false),
      simulationDataMappingStatus: diagnosticValue(simulationMappingSummary.simulationDataMappingStatus),
      simulationDataMappingStatusText: diagnosticValue(simulationMappingSummary.simulationDataMappingStatusText),
      simulationDataMappingReady: diagnosticValue(simulationMappingSummary.simulationDataMappingReady, false),
      simulationDataMappingBlocked: diagnosticValue(simulationMappingSummary.simulationDataMappingBlocked, false),
      simulationDataMappingWarnings: diagnosticArray(simulationMappingSummary.simulationDataMappingWarnings),
      simulationDataMappingConclusion: diagnosticValue(simulationMappingSummary.simulationDataMappingConclusion),
      simulationDataMapping: diagnosticValue(simulationMappingSummary.simulationDataMapping),
      simulationAccountMapping: diagnosticArray(simulationMappingSummary.simulationAccountMapping),
      simulationSupplierMapping: diagnosticValue(simulationMappingSummary.simulationSupplierMapping),
      simulationBankMapping: diagnosticValue(simulationMappingSummary.simulationBankMapping),
      simulationScenarioMapping: diagnosticValue(simulationMappingSummary.simulationScenarioMapping),
      simulationReportMapping: diagnosticArray(simulationMappingSummary.simulationReportMapping),
      simulationP2PValidationStatus: diagnosticValue(simulationP2PSummary.simulationP2PValidationStatus),
      simulationP2PValidationStatusText: diagnosticValue(simulationP2PSummary.simulationP2PValidationStatusText),
      simulationP2PValidationReady: diagnosticValue(simulationP2PSummary.simulationP2PValidationReady, false),
      simulationP2PValidationBlocked: diagnosticValue(simulationP2PSummary.simulationP2PValidationBlocked, false),
      simulationP2PValidationWarnings: diagnosticArray(simulationP2PSummary.simulationP2PValidationWarnings),
      simulationP2PValidationBlockedReasons: diagnosticArray(simulationP2PSummary.simulationP2PValidationBlockedReasons),
      simulationP2PValidationConclusion: diagnosticValue(simulationP2PSummary.simulationP2PValidationConclusion),
      simulationP2PFlow: diagnosticValue(simulationP2PSummary.simulationP2PFlow),
      purchaseOrderSupplierCount: diagnosticValue(multiSupplierSummary.purchaseOrderSupplierCount, 0),
      purchaseOrderSuppliers: diagnosticArray(multiSupplierSummary.purchaseOrderSuppliers),
      receiptSupplierMapping: diagnosticArray(multiSupplierSummary.receiptSupplierMapping),
      inventorySupplierMapping: diagnosticArray(multiSupplierSummary.inventorySupplierMapping),
      payableSupplierMapping: diagnosticArray(multiSupplierSummary.payableSupplierMapping),
      paymentSupplierMapping: diagnosticArray(multiSupplierSummary.paymentSupplierMapping),
      ledgerSupplierMapping: diagnosticArray(multiSupplierSummary.ledgerSupplierMapping),
      supplierChainConsistencyStatus: diagnosticValue(multiSupplierSummary.supplierChainConsistencyStatus),
      supplierChainConsistencyWarnings: diagnosticArray(multiSupplierSummary.supplierChainConsistencyWarnings),
      supplierChainConsistencyConclusion: diagnosticValue(multiSupplierSummary.supplierChainConsistencyConclusion),
      multiSupplierSettlementStatus: diagnosticValue(settlementSummary.multiSupplierSettlementStatus),
      multiSupplierSettlementStatusText: diagnosticValue(settlementSummary.multiSupplierSettlementStatusText),
      multiSupplierSettlementReady: diagnosticValue(settlementSummary.multiSupplierSettlementReady, false),
      multiSupplierSettlementBlocked: diagnosticValue(settlementSummary.multiSupplierSettlementBlocked, false),
      multiSupplierSettlementWarnings: diagnosticArray(settlementSummary.multiSupplierSettlementWarnings),
      multiSupplierSettlementConclusion: diagnosticValue(settlementSummary.multiSupplierSettlementConclusion),
      multiSupplierSettlementSummary: diagnosticValue(settlementSummary.multiSupplierSettlementSummary),
      purchaseSupplierMapping: diagnosticArray(settlementSummary.purchaseSupplierMapping),
      supplierSettlementLines: diagnosticArray(settlementSummary.supplierSettlementLines),
      supplierPayableMapping: diagnosticArray(settlementSummary.supplierPayableMapping),
      supplierPaymentMapping: diagnosticArray(settlementSummary.supplierPaymentMapping),
      supplierLedgerMapping: diagnosticArray(settlementSummary.supplierLedgerMapping),
      purchaseOrderValidation: diagnosticArray(dataValidationSummary.purchaseOrderValidation),
      supplierValidation: diagnosticArray(dataValidationSummary.supplierValidation),
      p2pDataValidation: diagnosticValue(dataValidationSummary.p2pDataValidation),

      ledgerStatus: diagnosticValue(row.ledgerStatus),
      ledgerStatusText: diagnosticValue(row.ledgerStatusText || getLedgerStatusLabel(row.ledgerStatus)),
      paymentWriteOffStatus: diagnosticValue(row.paymentWriteOffStatus),
      paymentWriteOffStatusText: diagnosticValue(row.paymentWriteOffStatusText || getPaymentWriteOffStatusLabel(row.paymentWriteOffStatus)),
      formalPostedAt: diagnosticValue(row.formalPostedAt),
      formalPostedBy: diagnosticValue(row.formalPostedBy),
      ledgerEntryId: diagnosticValue(row.ledgerEntryId),
      ledgerEntryNo: diagnosticValue(row.ledgerEntryNo),
      bankFlowStatus: diagnosticValue(row.bankFlowStatus),
      bankFlowNo: diagnosticValue(row.bankFlowNo),

      diagnosticSummary: diagnosticValue(confirmSummary.formalPostingConfirmConclusion || lockSummary.formalPostingLockConclusion || preExecuteSummary.formalPostingPreExecuteConclusion || flowSummary.formalPostingFlowConclusion),
      copiedAt,
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

async function copyCurrentVoucherDiagnostic(row) {
  try {
    const payload = buildVoucherDiagnosticPayload(row)
    await copyTextToClipboard(JSON.stringify(payload, null, 2))
    window.setTimeout(() => notify('已复制当前凭证诊断数据'), 0)
    notify('已复制当前凭证诊断数据')
  } catch (error) {
    window.setTimeout(() => notify('复制失败，请重试。', 'warning'), 0)
    notify('复制当前凭证诊断数据失败，请稍后重试。', 'warning')
  }
}

function showSourceBatch(result) {
  sourceBatchResult.value = result
  selectedSourceRows.value = []
  sourceTableRef.value?.clearSelection?.()
  refresh()
}

function showVoucherBatch(result) {
  voucherBatchResult.value = result
  selectedVoucherRows.value = []
  voucherTableRef.value?.clearSelection?.()
  refresh()
}

function batchResultType(result = {}) {
  if (result.failedCount && !result.successCount && !result.alreadyDoneCount) return 'error'
  if (result.failedCount) return 'warning'
  return 'success'
}

function clearSort() {
  sortState.value = { key: '', direction: 'asc' }
}

function resetFilters() {
  Object.assign(filters, defaultFilters())
  quickSearch.value = ''
}

function handleSortChange({ prop, order }) {
  sortState.value = { key: prop || '', direction: order === 'descending' ? 'desc' : 'asc' }
}

function sourceActions(row = {}) {
  return [
    { label: '查看正式付款凭证', visible: row.formalVoucherGenerated },
    { label: '生成正式付款凭证', visible: !row.formalVoucherGenerated },
    '查看付款凭证复核',
  ]
}

function voucherActions(row = {}) {
  return [
    '查看详情',
    { label: '取消正式凭证', visible: row.formalVoucherStatus === 'generated' },
    { label: postingPreReviewButtonText(row), visible: row.formalVoucherStatus === 'generated' },
    { label: '模拟过账', visible: row.formalVoucherStatus === 'generated' },
    { label: formalPostingEntryButtonText(row), visible: row.formalVoucherStatus === 'generated' },
  ]
}

function formalStatusLabel(status) {
  return getFormalVoucherStatusLabel(status)
}

function formalStatusType(status) {
  return getFormalVoucherStatusType(status)
}

function postingStatusLabel(status) {
  return getPostingStatusLabel(status)
}

function ledgerStatusLabel(status) {
  return getLedgerStatusLabel(status)
}

function writeOffStatusLabel(status) {
  return getPaymentWriteOffStatusLabel(status)
}

function riskLevelLabel(level) {
  return getFormalVoucherRiskLevelLabel(level)
}

function riskLevelType(level) {
  return getFormalVoucherRiskLevelType(level)
}

function postingStatusText(row = {}) {
  return row.postingStatusText || (row.postingReady ? '可过账' : '过账阻断')
}

function postingReadinessType(status) {
  return {
    ready: 'success',
    blocked: 'danger',
  }[status] || 'info'
}

function postingActionStatusLabel(status) {
  return {
    none: '未模拟',
    simulated: '已模拟过账',
    blocked: '模拟过账阻断',
  }[status] || status || '未模拟'
}

function postingActionStatusType(status) {
  return {
    none: 'info',
    simulated: 'success',
    blocked: 'danger',
  }[status] || 'info'
}

function formalPostingStatusLabel(status) {
  return {
    not_started: '未正式过账',
    ready: '可正式过账',
    blocked: '正式过账阻断',
    posted: '已正式过账',
  }[status] || '未正式过账'
}

function formalPostingStatusType(status) {
  return {
    not_started: 'info',
    ready: 'success',
    blocked: 'danger',
    posted: 'success',
  }[status] || 'info'
}

function canSimulatePosting(row = {}) {
  return row.formalVoucherStatus === 'generated'
    && row.postingReady
    && !row.postingBlocked
    && row.postingStatus === 'posting_ready'
    && row.ledgerStatus === 'notWritten'
    && row.paymentWriteOffStatus === 'notWrittenOff'
    && !isPostingSimulationCompleted(row)
}

function simulatePostingButtonTitle(row = {}) {
  if (isPostingSimulationCompleted(row)) return '已模拟过账，不能重复模拟。'
  if (!canSimulatePosting(row)) return '当前记录不满足模拟过账条件；不会写总账、不会核销、不会生成银行流水。'
  return '执行模拟过账；仅记录模拟状态和动作日志，不写总账、不核销、不生成银行流水。'
}

function postingPreReviewStatusLabel(status) {
  return {
    passed: '已通过过账前评审',
    blocked: '过账前评审阻断',
  }[status] || '待过账前评审'
}

function postingPreReviewStatusType(status) {
  return {
    passed: 'success',
    blocked: 'danger',
  }[status] || 'info'
}

function postingPreReviewButtonText(row = {}) {
  if (row.postingBlocked || row.postingReadinessStatus === 'blocked') return '查看过账条件'
  if (row.postingReady || row.postingReadinessStatus === 'ready') return '可进入凭证过账'
  if (row.postingPreReviewBlockedCount > 0 || row.postingPreReviewStatus === 'blocked') return '过账前评审阻断'
  return '查看过账条件'
}

function postingPreReviewButtonTitle(row = {}) {
  if (row.postingBlocked || row.postingReadinessStatus === 'blocked') return '存在过账阻断原因，本轮不允许进入过账动作。'
  if (row.postingReady || row.postingReadinessStatus === 'ready') return '仅表示可进入凭证过账设计阶段，本轮不会真实过账、不会写总账、不会核销。'
  return '本轮仅展示过账条件，不执行真实过账。'
}

function riskItemType(level) {
  return { blocked: 'danger', warning: 'warning', info: 'success' }[level] || 'info'
}

function riskItemLabel(value) {
  return {
    passed: '通过',
    blocked: '阻断',
    warning: '警告',
    info: '提示',
  }[value] || value || '-'
}

watch(() => route.fullPath, refresh, { immediate: true })
</script>

<style scoped>
.formal-payment-voucher-page { display: flex; flex-direction: column; gap: 16px; min-height: 100%; padding: 22px; background: #f5f7fb; color: #172033; }
.page-header, .card-header { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.page-header p { margin: 6px 0 0; color: #475467; line-height: 1.5; }
.eyebrow, .card-header span, .info-grid span, .source-chain span { color: #64748b; font-size: 13px; }
h1, h2 { margin: 0; }
.page-tabs, .button-row, .batch-bar { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.finance-flow-nav { align-items: stretch; border: 1px solid #dbeafe; border-radius: 8px; padding: 10px; background: #f8fbff; }
.finance-nav-title { display: flex; align-items: center; color: #475467; font-size: 13px; font-weight: 700; margin-right: 4px; }
.finance-nav-button { border: 1px solid #bfdbfe; border-radius: 6px; padding: 8px 12px; background: #fff; color: #1d4ed8; font-weight: 700; text-decoration: none; white-space: nowrap; }
.finance-nav-button-active { border-color: #0f766e; background: #0f766e; color: #fff; box-shadow: 0 6px 14px rgba(15, 118, 110, 0.18); }
.finance-current-tag { display: inline-flex; align-items: center; margin-left: 6px; border-radius: 999px; padding: 2px 7px; background: rgba(255, 255, 255, 0.22); color: inherit; font-size: 12px; }
.finance-current-module-badge { display: inline-flex; width: fit-content; border: 1px solid #99f6e4; border-radius: 999px; padding: 5px 10px; background: #ecfdf5; color: #0f766e !important; font-weight: 800; }
.operation-shell { display: flex; flex-direction: column; gap: 16px; }
.plain-flow-guide { display: grid; gap: 10px; border: 1px solid #a7f3d0; border-radius: 8px; padding: 14px; background: #ecfdf5; color: #064e3b; line-height: 1.6; }
.plain-flow-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; }
.plain-flow-grid span { display: grid; gap: 4px; border: 1px solid rgba(6, 78, 59, 0.14); border-radius: 8px; padding: 10px; background: #fff; }
.boundary-note { border: 1px solid #fed7aa; border-radius: 8px; padding: 10px; margin-bottom: 12px; background: #fff7ed; color: #9a3412; font-weight: 700; }
.info-grid, .source-chain, .filter-grid, .posting-review-summary, .diagnostic-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 10px; }
.info-grid article, .source-chain article, .posting-review-summary article, .diagnostic-grid article { border: 1px solid #dbe3ef; border-radius: 8px; padding: 12px; background: #fff; }
.info-grid strong, .source-chain strong, .posting-review-summary strong, .diagnostic-grid strong { display: block; margin-top: 4px; }
.diagnostic-title { margin: 12px 0 8px; font-size: 16px; }
.diagnostic-note { border: 1px solid #cbd5e1; border-radius: 8px; padding: 10px; margin-bottom: 12px; background: #f8fafc; color: #334155; font-weight: 800; }
.diagnostic-note.success { border-color: #86efac; background: #f0fdf4; color: #166534; }
.diagnostic-note.danger { border-color: #fecaca; background: #fef2f2; color: #991b1b; }
.diagnostic-grid strong { word-break: break-word; line-height: 1.5; }
.posting-condition-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 12px; }
.posting-condition-grid section { border: 1px solid #dbe3ef; border-radius: 8px; padding: 12px; background: #fff; }
.posting-condition-grid h3 { margin: 0 0 8px; font-size: 15px; }
.posting-condition-grid ul { margin: 0; padding-left: 18px; line-height: 1.7; color: #334155; }
.flow-step-list { display: grid; gap: 8px; margin: 0; padding-left: 20px; color: #334155; }
.flow-step-list li { border: 1px solid #dbe3ef; border-radius: 8px; padding: 8px 10px; background: #f8fafc; line-height: 1.5; }
.flow-step-list li.active { border-color: #0f766e; background: #ecfdf5; color: #0f766e; }
.flow-step-list strong, .flow-step-list span { display: block; }
.batch-bar { border: 1px solid #dbe3ef; border-radius: 8px; padding: 10px; margin-bottom: 12px; background: #f8fafc; }
.button-row .el-button, .batch-bar .el-button { min-width: 96px; white-space: nowrap; }
.button-row .el-button--primary, .button-row .el-button--success, .button-row .el-button--warning,
.batch-bar .el-button--primary, .batch-bar .el-button--success, .batch-bar .el-button--warning { min-width: 132px; }
.batch-bar .el-button--danger, .button-row .el-button--danger { min-width: 96px; }
.batch-action-title { color: #172033; font-weight: 800; }
.batch-action-tip, .sort-help { color: #64748b; font-size: 13px; }
.app-step-guide { display: grid; gap: 6px; margin: 0 0 12px; line-height: 1.6; }
.app-current-step-tip, .app-terminal-step-tip { display: inline-flex; align-items: center; gap: 6px; border-radius: 999px; padding: 5px 10px; font-size: 13px; font-weight: 800; }
.app-current-step-tip { border: 1px solid #99f6e4; background: #ecfdf5; color: #0f766e; }
.app-terminal-step-tip { border: 1px solid #cbd5e1; background: #f8fafc; color: #475467; }
.app-step-guide.app-current-step-tip, .app-step-guide.app-terminal-step-tip { display: grid; align-items: stretch; border-radius: 8px; padding: 10px 12px; }
.app-next-action-button { border-color: #0f766e !important; background: #0f766e !important; color: #fff !important; box-shadow: 0 8px 16px rgba(15, 118, 110, 0.2); }
.app-next-action-button.is-disabled, .app-next-action-button:disabled { border-color: #94a3b8 !important; background: #94a3b8 !important; box-shadow: none; }
.app-next-action-badge { display: inline-flex; align-items: center; margin-left: 6px; border-radius: 999px; padding: 2px 7px; background: rgba(255, 255, 255, 0.22); color: inherit; font-size: 12px; font-weight: 900; }
.batch-result { position: relative; display: grid; gap: 6px; margin-bottom: 12px; border-radius: 8px; padding: 12px; background: #ecfdf5; color: #065f46; }
.batch-result.warning { background: #fffbeb; color: #92400e; }
.batch-result.error { background: #fef2f2; color: #991b1b; }
.batch-result button { position: absolute; top: 8px; right: 8px; border: 0; background: transparent; color: inherit; cursor: pointer; }
.filter-line, .filter-grid { border: 1px solid #dbe3ef; border-radius: 8px; padding: 12px; margin-bottom: 12px; background: #fff; }
label { display: grid; gap: 6px; color: #334155; font-weight: 700; }
input, select { width: 100%; box-sizing: border-box; border: 1px solid #cbd5e1; border-radius: 6px; padding: 8px 10px; background: #fff; color: #172033; }
@media (max-width: 900px) {
  .page-header { align-items: flex-start; flex-direction: column; }
  .plain-flow-grid { grid-template-columns: 1fr; }
}
</style>
