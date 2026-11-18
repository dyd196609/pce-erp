// Only the2 adapted PlanningCenter tables: compact actions remain scrollable while resizing.
export function planningRightActionFixed(compact,viewportWidth) {
 const measured=Number.isFinite(viewportWidth)&&viewportWidth>0
 return compact&&measured?false:'right'
}
