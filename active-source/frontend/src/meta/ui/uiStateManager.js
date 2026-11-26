export function getUIState({ loading, error, data } = {}) {
  if (loading) return 'LOADING'
  if (error) return 'ERROR'
  if (!data || data.length === 0) return 'EMPTY'

  return 'SUCCESS'
}

export function createUIState(payload = {}) {
  return {
    loading: payload.loading === true,
    error: payload.error || null,
    data: payload.data ?? null,
    state: getUIState(payload),
  }
}
