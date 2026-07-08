export function diffExecution(before, after) {
  const diff = []

  const beforeKeys = Object.keys(before || {})
  const afterKeys = Object.keys(after || {})

  const added = afterKeys.filter((key) => !beforeKeys.includes(key))
  const removed = beforeKeys.filter((key) => !afterKeys.includes(key))
  const common = beforeKeys.filter((key) => afterKeys.includes(key))

  for (const key of common) {
    if (JSON.stringify(before[key]) !== JSON.stringify(after[key])) {
      diff.push({
        type: 'MODIFIED',
        field: key,
        before: before[key],
        after: after[key],
      })
    }
  }

  return {
    added,
    removed,
    modified: diff,
  }
}
