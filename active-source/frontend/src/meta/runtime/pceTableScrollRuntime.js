export const PCE_TABLE_SCROLL_RUNTIME_VERSION = 'V1.14.2.8.18.14.1'

export const LIST_WIDTH_POLICY = Object.freeze({
  normal: Object.freeze({ code: 'normal', minWidth: 1200 }),
  wide: Object.freeze({ code: 'wide', minWidth: 1600 }),
  'ultra-wide': Object.freeze({ code: 'ultra-wide', minWidth: 1800 }),
})

function pixels(value = 0) {
  if (typeof value === 'number') return value
  const normalized = String(value).trim()
  if (normalized === '100%') return 0
  const match = normalized.match(/^(\d+(?:\.\d+)?)px$/)
  if (!match) throw new Error('PCE_TABLE_SCROLL_MIN_WIDTH_INVALID')
  return Number(match[1])
}

export function resolveListWidthPolicy({ widthPolicy = 'wide', requestedMinWidth = 0 } = {}) {
  const policy = LIST_WIDTH_POLICY[widthPolicy]
  if (!policy) throw new Error(`PCE_LIST_WIDTH_POLICY_INVALID:${widthPolicy}`)
  const requested = pixels(requestedMinWidth || 0)
  const minWidth = Math.max(policy.minWidth, requested)
  return Object.freeze({ ...policy, requestedMinWidth: requested, resolvedMinWidth: minWidth,
    cssMinWidth: `${minWidth}px` })
}

export function measureHorizontalScroll(container, { pageElement = globalThis.document?.documentElement,
  getStyle = globalThis.getComputedStyle } = {}) {
  if (!container || typeof getStyle !== 'function') throw new Error('PCE_TABLE_SCROLL_ELEMENT_REQUIRED')
  const scrollTarget = container.querySelector?.('.el-table__body-wrapper .el-scrollbar__wrap') || container
  const style = getStyle(scrollTarget)
  const rect = scrollTarget.getBoundingClientRect()
  const scrollWidth = Number(scrollTarget.scrollWidth || 0)
  const clientWidth = Number(scrollTarget.clientWidth || 0)
  const overflowRequired = scrollWidth > clientWidth
  const overflowEnabled = ['auto', 'scroll'].includes(style.overflowX)
  const regionVisible = rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden'
  const pageScrollWidth = Number(pageElement?.scrollWidth || 0)
  const pageClientWidth = Number(pageElement?.clientWidth || 0)
  const noPageOverflow = !pageElement || pageScrollWidth <= pageClientWidth
  const scrollbar = container.querySelector?.('.el-scrollbar__bar.is-horizontal')
  const scrollbarHeight = Number(scrollbar?.getBoundingClientRect?.().height || 0)
  const horizontalScrollVisible = overflowRequired && overflowEnabled && regionVisible && scrollbarHeight > 0
  return Object.freeze({ scrollWidth, clientWidth, overflowX: style.overflowX,
    overflowRequired, overflowEnabled, regionVisible, horizontalScrollVisible,
    scrollbarHeight, pageScrollWidth, pageClientWidth, noPageOverflow,
    scrollTarget: scrollTarget === container ? 'table-container' : 'element-plus-body-scrollbar',
    stickyColumnsInsideContainer: Boolean(container.querySelector?.('.pce-fixed-primary-no-column, .payment-fixed-action-column')) })
}

export function createPceTableScrollRuntime(options = {}) {
  const width = resolveListWidthPolicy(options)
  return Object.freeze({ runtimeVersion: PCE_TABLE_SCROLL_RUNTIME_VERSION,
    contractCode: 'TABLE-SCROLL-RUNTIME-001', horizontalScrollOwner: 'element-plus-native',
    pageOverflowX: 'hidden', cardOverflowX: 'hidden', tableOverflowX: 'hidden', width })
}
