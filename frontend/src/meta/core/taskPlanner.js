export function planTasks(goalObj) {
  const tasks = []

  if (goalObj.type === 'PROCUREMENT') {
    tasks.push(
      { step: 'fetch_purchase_data' },
      { step: 'validate_contracts' },
      { step: 'generate_order_list' },
      { step: 'trigger_workflow' }
    )
  }

  if (goalObj.type === 'INVENTORY') {
    tasks.push(
      { step: 'scan_stock' },
      { step: 'detect_low_stock' },
      { step: 'create_replenishment_plan' }
    )
  }

  if (goalObj.type === 'FINANCE') {
    tasks.push(
      { step: 'scan_finance_data' },
      { step: 'validate_finance_contracts' },
      { step: 'generate_finance_summary' }
    )
  }

  if (tasks.length === 0) {
    tasks.push({ step: 'analyze_goal' }, { step: 'validate_contracts' }, { step: 'generate_summary' })
  }

  return {
    goal: goalObj.goal,
    type: goalObj.type,
    tasks,
  }
}
