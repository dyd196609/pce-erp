// =====================================
// ERP终极统一架构：Meta Platform Core
// =====================================

import { generateTable } from '@/meta/crud/crudGenerator'
import { generateForm } from '@/meta/crud/formGenerator'
import { runWorkflow } from '@/domain/workflow/bpmRuntime'
import { executeAction } from '@/meta/crud/actionEngine'

// =========================
// 平台运行入口
// =========================
export const createMetaPlatform = (meta) => {
  return {
    renderTable: (data) => generateTable(meta)(data),
    renderForm: (model) => generateForm(meta)(model),

    executeWorkflow: (workflow, context) => runWorkflow(workflow, context),

    executeAction: (action, row, ctx) => executeAction(action, row, ctx),

    meta,
  }
}
