export const materialModel = [
  {
    id: 'mat-001',
    code: 'MAT-DEMO-001',
    name: 'Demo Material',
    category: 'Raw Material',
    unit: 'pcs',
  },
  {
    id: 'mat-002',
    code: 'MAT-DEMO-002',
    name: 'Assembly Kit',
    category: 'Semi-finished',
    unit: 'set',
  },
  {
    id: 'mat-003',
    code: 'MAT-DEMO-003',
    name: 'Packaging Box',
    category: 'Packaging',
    unit: 'box',
  },
]

export function getMaterialModel() {
  return materialModel
}

