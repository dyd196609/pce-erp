// ======================================
// Transaction Engine V23
// 企业交易系统
// ======================================

const transactions = []

/**
 * 创建交易
 */
export const createTransaction = (from, to, type, value) => {
  const tx = {
    id: 'tx_' + Date.now(),
    from,
    to,
    type,
    value,
    status: 'PENDING',
  }

  transactions.push(tx)

  return tx
}

/**
 * 执行交易
 */
export const executeTransaction = (txId) => {
  const tx = transactions.find((t) => t.id === txId)

  if (tx) {
    tx.status = 'DONE'
  }

  return tx
}

/**
 * 获取交易列表
 */
export const getTransactions = () => transactions
