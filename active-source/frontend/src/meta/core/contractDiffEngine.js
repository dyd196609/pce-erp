export function diffContracts(oldContract = {}, newContract = {}) {
  const changes = []

  const oldKeys = Object.keys(oldContract)
  const newKeys = Object.keys(newContract)

  const added = newKeys.filter((key) => !oldKeys.includes(key))
  const removed = oldKeys.filter((key) => !newKeys.includes(key))

  const common = newKeys.filter((key) => oldKeys.includes(key))

  common.forEach((key) => {
    if (JSON.stringify(oldContract[key]) !== JSON.stringify(newContract[key])) {
      changes.push({
        type: 'MODIFIED',
        module: key,
      })
    }
  })

  return {
    added,
    removed,
    modified: changes,
  }
}
