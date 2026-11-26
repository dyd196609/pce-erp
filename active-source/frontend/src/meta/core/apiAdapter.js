export function adaptResponse(res) {
  if (!res) {
    return {
      success: false,
      data: null,
      error: 'empty response',
      meta: {},
    }
  }

  if (
    typeof res.success === 'boolean'
    && Object.prototype.hasOwnProperty.call(res, 'data')
    && Object.prototype.hasOwnProperty.call(res, 'error')
    && res.meta
  ) {
    return res
  }

  const data = res?.data ?? res

  return {
    success: true,
    data,
    error: null,
    meta: {
      status: res?.status,
      statusText: res?.statusText,
    },
  }
}
