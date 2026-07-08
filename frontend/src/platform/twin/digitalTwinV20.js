/**
 * ============================
 * Meta Runtime V20 - Digital Twin
 * 企业数字孪生系统
 * ============================
 */

const twinState = new Map()

export const updateTwin = (id, state) => {
  twinState.set(id, {
    ...state,
    timestamp: Date.now(),
  })
}

export const getTwin = (id) => {
  return twinState.get(id)
}

export const simulate = (id, action) => {
  const current = twinState.get(id)

  return {
    before: current,
    action,
    after: {
      ...current,
      simulated: true,
    },
  }
}
