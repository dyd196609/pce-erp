export function createLatestRequestGate() {
  let sequence = 0
  return {
    begin() {
      sequence += 1
      return sequence
    },
    isCurrent(token) {
      return token === sequence
    },
    current() {
      return sequence
    },
  }
}
