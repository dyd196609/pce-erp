// ======================================
// Meta Runtime V17 - BPM State Machine
// ======================================

const transitions = {
  DRAFT: ['SUBMITTED'],
  SUBMITTED: ['APPROVED', 'REJECTED'],
  APPROVED: ['EXECUTED'],
  REJECTED: [],
  EXECUTED: ['CLOSED'],
  CLOSED: [],
}

// 状态流转
export const moveState = (current, action) => {
  const nextStates = transitions[current] || []
  if (!nextStates.includes(action)) {
    throw new Error(`非法状态流转: ${current} → ${action}`)
  }
  return action
}
