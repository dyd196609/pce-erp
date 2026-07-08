import { getApiTemplate } from '@/meta/core/apiResolver'

// =============================
// 全自动 CRUD 引擎（核心层）
// =============================

export const buildCRUD = (meta) => {
  return {
    table: buildTable(meta),
    form: buildForm(meta),
    api: buildAPI(meta),
  }
}

// -----------------------------
// Table 自动生成
// -----------------------------
const buildTable = (meta) => {
  return meta.fields
    .filter((f) => f.inTable)
    .map((f) => ({
      prop: f.name,
      label: f.label,
      type: f.type || 'text',
      width: f.width || 120,
      tagMap: f.tagMap || null,
    }))
}

// -----------------------------
// Form 自动生成
// -----------------------------
const buildForm = (meta) => {
  return meta.fields
    .filter((f) => f.inForm)
    .map((f) => ({
      prop: f.name,
      label: f.label,
      type: f.formType || 'input',
      required: f.required || false,
      options: f.options || [],
    }))
}

// -----------------------------
// API 自动生成
// -----------------------------
const buildAPI = (meta) => {
  const module = meta?.api?.module || meta?.module

  return {
    list: getApiTemplate(module, 'list'),
    create: getApiTemplate(module, 'create'),
    update: getApiTemplate(module, 'update'),
    delete: getApiTemplate(module, 'delete'),
    detail: getApiTemplate(module, 'detail'),
  }
}
