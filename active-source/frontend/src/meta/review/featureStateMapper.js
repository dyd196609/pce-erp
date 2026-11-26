export const featureStateMap = {
  '未开发': {
    state: 'NOT_STARTED',
    label: 'Not Started',
    progress: 0,
    completed: false,
    passed: false,
  },
  '开发中': {
    state: 'IN_PROGRESS',
    label: 'In Progress',
    progress: 40,
    completed: false,
    passed: false,
  },
  '开发完成': {
    state: 'COMPLETED',
    label: 'Completed',
    progress: 80,
    completed: true,
    passed: false,
  },
  '通过': {
    state: 'PASSED',
    label: 'Passed',
    progress: 100,
    completed: true,
    passed: true,
  },
  '不通过': {
    state: 'FAILED',
    label: 'Failed',
    progress: 100,
    completed: true,
    passed: false,
  },
}

export function mapFeatureState(status = '未开发') {
  return featureStateMap[status] || {
    state: 'UNKNOWN',
    label: 'Unknown',
    progress: 0,
    completed: false,
    passed: false,
  }
}

export function normalizeFeatureState(status) {
  return {
    source: status,
    ...mapFeatureState(status),
  }
}

