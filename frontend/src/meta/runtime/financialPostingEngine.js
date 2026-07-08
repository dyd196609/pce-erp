import { writeDatabase } from '../data/databaseLayer.js'
import { emitBusinessEvent } from './enterpriseEventStream.js'

const postings = []

function amountFromRecord(record = {}) {
  const quantity = Number(record.quantity || 0)
  const price = Number(record.price || record.cost || 0)
  return Number(record.amount || record.balance || quantity * price || 0)
}

export function postJournalEntry(record = {}, context = {}) {
  const amount = amountFromRecord(record)
  const journal = {
    id: `JE-${Date.now()}-${postings.length}`,
    accountId: record.accountId || `ACC-${record.supplierId || record.customerId || 'RUNTIME'}`,
    accountName: record.accountName || 'Runtime Posting',
    debit: amount,
    credit: 0,
    balance: amount,
    transactionDate: new Date().toISOString().slice(0, 10),
    currency: record.currency || 'USD',
    costCenter: record.costCenter || record.module || 'Enterprise Runtime',
    workflow_state: 'posted',
    sourceTransactionId: context.transactionId,
  }

  const data = writeDatabase('finance', journal, context)
  const posting = { ...journal, status: 'POSTED', data }
  postings.unshift(posting)
  if (postings.length > 100) postings.length = 100
  emitBusinessEvent({
    type: 'finance.posted',
    module: 'finance',
    payload: posting,
    correlationId: context.transactionId,
  })

  return posting
}

export function updateAccountBalance(entry = {}, context = {}) {
  return writeDatabase('finance', {
    ...entry,
    balance: Number(entry.balance || 0),
    workflow_state: entry.workflow_state || 'settled',
  }, context)
}

export function syncFinanceModule(entry = {}, context = {}) {
  return {
    module: 'finance',
    synced: true,
    data: updateAccountBalance(entry, context),
    timestamp: Date.now(),
  }
}

export function getFinancialPostingSnapshot() {
  return {
    financialPosting: 'ACTIVE',
    postings: [...postings],
    accuracy: postings.every((posting) => Number.isFinite(Number(posting.balance))) ? 100 : 80,
  }
}
