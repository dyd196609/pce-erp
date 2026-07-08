import { resolveControlAuthority } from './controlAuthorityEngine.js'

let currentState = {
  mode: 'STABLE',
  authority: 'EXECUTION',
}

export function evaluateSystemState(context = {}) {
  const decision = resolveControlAuthority(context)
  let mode = 'STABLE'

  switch (decision.authority) {
    case 'GOVERNANCE':
      mode = 'PROTECTED'
      break

    case 'SELF_HEALING':
      mode = 'RECOVERY'
      break

    case 'EXECUTION':
      mode = 'NORMAL'
      break
  }

  currentState = {
    mode,
    authority: decision.authority,
    metrics: decision,
  }

  return currentState
}

export function getSystemState() {
  return currentState
}
