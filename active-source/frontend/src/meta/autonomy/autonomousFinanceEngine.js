function currency(value) {
  return Math.round(Number(value || 0))
}

function getInvoices(context = {}) {
  return context.invoices || [
    { id: 'INV-1001', vendor: 'core_supplier', amount: 48000, dueDays: 2, status: 'RECEIVED' },
    { id: 'INV-1002', vendor: 'logistics_partner', amount: 26000, dueDays: 7, status: 'VALIDATED' },
    { id: 'INV-1003', vendor: 'cloud_runtime', amount: 12000, dueDays: 14, status: 'SCHEDULED' },
  ]
}

export function processInvoices(context = {}) {
  const invoices = getInvoices(context)

  return {
    mode: 'V30_INVOICE_PROCESSING',
    processed: invoices.map((invoice) => ({
      ...invoice,
      validation: invoice.amount > 100000 ? 'POLICY_REVIEW' : 'AUTO_VALIDATED',
      accrualStatus: 'POSTED',
    })),
    exceptionCount: invoices.filter((invoice) => invoice.amount > 100000).length,
  }
}

export function simulatePaymentExecution(context = {}) {
  const invoiceProcessing = context.invoiceProcessing || processInvoices(context)
  const payments = invoiceProcessing.processed
    .filter((invoice) => invoice.validation === 'AUTO_VALIDATED')
    .map((invoice) => ({
      paymentId: `PAY-${invoice.id}`,
      vendor: invoice.vendor,
      amount: invoice.amount,
      rail: invoice.amount > 30000 ? 'BANK_TRANSFER' : 'AUTOPAY',
      status: invoice.dueDays <= 7 ? 'EXECUTED' : 'SCHEDULED',
    }))

  return {
    mode: 'V30_PAYMENT_EXECUTION_SIMULATION',
    noHumanApprovalRequired: true,
    payments,
    totalExecuted: currency(payments
      .filter((payment) => payment.status === 'EXECUTED')
      .reduce((sum, payment) => sum + payment.amount, 0)),
  }
}

export function automateCashflow(context = {}) {
  const paymentExecution = context.paymentExecution || simulatePaymentExecution(context)
  const openingCash = currency(context.cash?.opening || context.cashBalance || 360000)
  const receivables = currency(context.cash?.receivables || 220000)
  const scheduledPayments = currency(paymentExecution.payments.reduce((sum, payment) => sum + payment.amount, 0))
  const projectedCash = openingCash + receivables - scheduledPayments

  return {
    mode: 'V30_CASHFLOW_AUTOMATION',
    openingCash,
    receivables,
    scheduledPayments,
    projectedCash,
    runwayDays: Math.max(1, Math.round(projectedCash / 7200)),
    automation: projectedCash > 120000 ? 'SELF_BALANCING' : 'LIQUIDITY_PROTECTION',
  }
}

export function optimizeFinance(context = {}) {
  const cashflow = context.cashflow || automateCashflow(context)
  const savingsRate = cashflow.projectedCash > 250000 ? 0.07 : 0.04

  return {
    mode: 'V30_FINANCIAL_OPTIMIZATION',
    strategy: cashflow.automation === 'SELF_BALANCING' ? 'EARLY_PAY_DISCOUNT_CAPTURE' : 'PAYMENT_TERM_EXTENSION',
    savingsRate,
    optimizedCash: currency(cashflow.projectedCash * (1 + savingsRate)),
    risk: cashflow.runwayDays < 21 ? 'WATCH' : 'LOW',
  }
}

export function executeFinancialOps(context = {}) {
  const invoiceProcessing = processInvoices(context)
  const paymentExecution = simulatePaymentExecution({
    ...context,
    invoiceProcessing,
  })
  const cashflow = automateCashflow({
    ...context,
    paymentExecution,
  })
  const optimization = optimizeFinance({
    ...context,
    cashflow,
  })

  return {
    mode: 'V30_AUTONOMOUS_FINANCE_ENGINE',
    invoiceProcessing,
    paymentExecution,
    cashflow,
    optimization,
    financialExecution: paymentExecution.totalExecuted > 0 ? 'ACTIVE' : 'SCHEDULED',
    metrics: {
      invoiceAutomationRate: invoiceProcessing.processed.length
        ? (invoiceProcessing.processed.length - invoiceProcessing.exceptionCount) / invoiceProcessing.processed.length
        : 1,
      paymentExecutionValue: paymentExecution.totalExecuted,
      cashflowRunwayDays: cashflow.runwayDays,
      financialOptimizationGain: optimization.optimizedCash - cashflow.projectedCash,
    },
  }
}
