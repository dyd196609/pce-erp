const processCatalog = {
  purchase: {
    steps: [
      { key: 'draft', label: 'Draft', role: 'Requester' },
      { key: 'submitted', label: 'Submitted', role: 'Procurement Manager' },
      { key: 'approved', label: 'Approved', role: 'Finance Controller' },
    ],
    roles: {
      draft: 'Requester',
      submitted: 'Procurement Manager',
      approved: 'Finance Controller',
    },
    transitions: [
      { action: 'SUBMIT', from: 'draft', to: 'submitted' },
      { action: 'APPROVE', from: 'submitted', to: 'approved' },
    ],
  },
  production: {
    steps: [
      { key: 'planned', label: 'Planned', role: 'Production Planner' },
      { key: 'released', label: 'Released', role: 'Production Lead' },
      { key: 'completed', label: 'Completed', role: 'Quality Manager' },
    ],
    roles: {
      planned: 'Production Planner',
      released: 'Production Lead',
      completed: 'Quality Manager',
    },
    transitions: [
      { action: 'RELEASE', from: 'planned', to: 'released' },
      { action: 'COMPLETE', from: 'released', to: 'completed' },
    ],
  },
}

function resolveProcess(type = 'purchase') {
  return processCatalog[type] || processCatalog.purchase
}

export function getProcessSteps(type = 'purchase') {
  return [...resolveProcess(type).steps]
}

export function assignRoles(type = 'purchase') {
  return { ...resolveProcess(type).roles }
}

export function buildTransitions(type = 'purchase') {
  return [...resolveProcess(type).transitions]
}

export function defineProcess(type = 'purchase') {
  return {
    type,
    steps: getProcessSteps(type),
    roles: assignRoles(type),
    transitions: buildTransitions(type),
  }
}
