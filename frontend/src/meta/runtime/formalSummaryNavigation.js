function asText(value) {
  return value === null || value === undefined ? '' : String(value)
}

function uniqueExactOrderSummary(summaries, orderNo) {
  if (!orderNo) return null
  const matches = summaries.filter(summary => {
    const linkedOrders = Array.isArray(summary?.linkedOrders) ? summary.linkedOrders : []
    return linkedOrders.length === 1 && asText(linkedOrders[0]?.orderNo) === orderNo
  })
  return matches.length === 1 ? matches[0] : null
}

export function buildFormalSummaryReturnContext({ summary, line, engineeringVersion = '', scrollTop = 0, tableScrollLeft = 0 } = {}) {
  if (!summary?.sourceRecordId || !line?.salesOrderItemId) return null
  return {
    sourceRecordId: asText(summary.sourceRecordId),
    orderNo: asText(line.orderNo || summary.orderNo),
    salesOrderItemId: Number(line.salesOrderItemId),
    engineeringVersion: asText(engineeringVersion || summary.sourceVersion),
    lineCount: Number(summary.linkedOrders?.[0]?.lineCount || 0),
    scrollTop: Number(scrollTop || 0),
    tableScrollLeft: Number(tableScrollLeft || 0),
  }
}

export function resolveFormalSummaryReturnTarget({ context, routeQuery = {}, summaries = [], selectedLine } = {}) {
  const sourceRecordId = asText(context?.sourceRecordId || routeQuery.returnSourceRecord || selectedLine?.sourceRecordId)
  const orderNo = asText(context?.orderNo || routeQuery.returnOrderNo || selectedLine?.orderNo)
  let summary = sourceRecordId
    ? summaries.find(row => asText(row?.sourceRecordId) === sourceRecordId)
    : null
  if (!summary) summary = uniqueExactOrderSummary(summaries, orderNo)
  if (!summary) return null

  const linkedOrders = Array.isArray(summary.linkedOrders) ? summary.linkedOrders : []
  if (orderNo && !linkedOrders.some(row => asText(row?.orderNo) === orderNo)) return null

  return {
    sourceRecordId: asText(summary.sourceRecordId),
    orderNo,
    engineeringVersion: asText(context?.engineeringVersion || routeQuery.returnEngineeringVersion || summary.sourceVersion),
    lineCount: Number(context?.lineCount || routeQuery.returnLineCount || linkedOrders[0]?.lineCount || 0),
    scrollTop: Number(context?.scrollTop || 0),
    tableScrollLeft: Number(context?.tableScrollLeft || 0),
    summary,
  }
}


