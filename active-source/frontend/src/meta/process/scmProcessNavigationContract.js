import { SCM_PURCHASE_PROCESS_CENTER_NODES } from './scmPurchaseProcessCenterRegistryV11428101.js'

export const SCM_PROCESS_NAVIGATION_CONTRACT_VERSION = 'V1.14.2.8.18.10.1'

const FLOW = Object.freeze(SCM_PURCHASE_PROCESS_CENTER_NODES.map(node => Object.freeze({
  nodeCode: node.nodeCode,
  pageCode: node.pageCode,
  pageName: node.nodeName,
  pageUrl: node.pageRoute,
  allowNewTab: node.allowNewTab,
  sequence: node.sequence,
  previousNode: node.previousNode,
  nextNode: node.nextNode,
  acceptanceProfile: node.acceptanceProfile,
})))

const link = (page) => page ? Object.freeze({
  pageCode: page.pageCode,
  label: page.pageName,
  pageUrl: page.pageUrl,
  allowNewTab: page.allowNewTab,
}) : null

const NAVIGATION = Object.freeze(FLOW.map((current, index) => Object.freeze({
  nodeCode: current.nodeCode,
  pageCode: current.pageCode,
  pageUrl: current.pageUrl,
  allowNewTab: current.allowNewTab,
  previousPage: link(FLOW[index - 1]),
  currentPage: link(current),
  nextPage: link(FLOW[index + 1]),
})))

export function listScmProcessNavigation() {
  return NAVIGATION.map((item) => ({ ...item }))
}

export function listScmProcessFlowPages() {
  return FLOW.map((item) => ({ ...item }))
}

export function resolveScmProcessNavigation(pageCodeOrUrl = '') {
  const normalized = String(pageCodeOrUrl || '').split('?')[0]
  const item = NAVIGATION.find((entry) => entry.nodeCode === normalized
    || entry.pageCode === normalized || entry.pageUrl === normalized)
  return item ? { ...item } : null
}
