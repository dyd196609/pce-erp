function unique(values) {
  return Array.from(new Set(values.filter((item) => item !== undefined && item !== null && String(item).trim()).map((item) => String(item).trim())))
}

export function buildFieldSuggestions(records = [], fieldName = '') {
  return unique(records.map((record) => record?.[fieldName])).slice(0, 200)
}

export function buildMultiFieldSuggestions(records = [], fieldNames = []) {
  return unique(records.flatMap((record) => fieldNames.map((field) => record?.[field]))).slice(0, 300)
}

export function filterSuggestions(keyword = '', suggestions = []) {
  const text = String(keyword || '').trim().toLowerCase()
  const rows = !text ? suggestions : suggestions.filter((item) => String(item).toLowerCase().includes(text))
  return rows.slice(0, 20).map((item) => ({ value: item, label: item }))
}

export function createSuggestionOptions(records = [], fieldName = '', keyword = '') {
  return filterSuggestions(keyword, buildFieldSuggestions(records, fieldName))
}
