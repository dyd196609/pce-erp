const t = (value) => value

export const enterpriseOperationModel = {
  workCenter: {
    pendingTasks: [
      {
        id: 'todo-purchase-plan',
        title: t('\u91c7\u8d2d\u8ba1\u5212\u5f85\u63d0\u4ea4'),
        process: t('\u91c7\u8d2d\u6d41\u7a0b'),
        owner: t('\u91c7\u8d2d\u4e13\u5458'),
        due: t('\u4eca\u5929'),
        status: t('\u5f85\u5904\u7406'),
      },
      {
        id: 'todo-warehouse-check',
        title: t('\u5165\u5e93\u5355\u5f85\u786e\u8ba4'),
        process: t('\u4ed3\u50a8\u6d41\u7a0b'),
        owner: t('\u4ed3\u5e93\u4e3b\u7ba1'),
        due: t('\u4eca\u5929'),
        status: t('\u5f85\u5904\u7406'),
      },
      {
        id: 'todo-production-order',
        title: t('\u751f\u4ea7\u5de5\u5355\u5f85\u4e0b\u8fbe'),
        process: t('\u751f\u4ea7\u6d41\u7a0b'),
        owner: t('\u751f\u4ea7\u4e3b\u7ba1'),
        due: t('\u660e\u5929'),
        status: t('\u5f85\u5904\u7406'),
      },
    ],
    approvals: [
      {
        id: 'approval-purchase-order',
        title: t('\u91c7\u8d2d\u8ba2\u5355\u5ba1\u6279'),
        applicant: t('\u674e\u96f7'),
        amount: '$18,600',
        status: t('\u5f85\u5ba1\u6279'),
      },
      {
        id: 'approval-finance-settlement',
        title: t('\u8d22\u52a1\u7ed3\u7b97\u5ba1\u6279'),
        applicant: t('\u738b\u654f'),
        amount: '$42,300',
        status: t('\u5f85\u5ba1\u6279'),
      },
    ],
    executionTasks: [
      {
        id: 'exec-receive',
        title: t('\u6267\u884c\u5165\u5e93\u9a8c\u6536'),
        process: t('\u4ed3\u50a8\u6d41\u7a0b'),
        owner: t('\u4ed3\u5e93\u64cd\u4f5c\u5458'),
        status: t('\u53ef\u6267\u884c'),
      },
      {
        id: 'exec-shipping',
        title: t('\u6267\u884c\u53d1\u8d27\u590d\u6838'),
        process: t('\u53d1\u8d27\u6d41\u7a0b'),
        owner: t('\u7269\u6d41\u4e13\u5458'),
        status: t('\u53ef\u6267\u884c'),
      },
    ],
    workflows: [
      { id: 'wf-purchase', name: t('\u91c7\u8d2d\u6d41\u7a0b'), currentStep: t('\u90e8\u95e8\u5ba1\u6279'), progress: '60%' },
      { id: 'wf-production', name: t('\u751f\u4ea7\u6d41\u7a0b'), currentStep: t('\u5de5\u5355\u4e0b\u8fbe'), progress: '45%' },
      { id: 'wf-finance', name: t('\u8d22\u52a1\u7ed3\u7b97\u6d41\u7a0b'), currentStep: t('\u51ed\u8bc1\u590d\u6838'), progress: '75%' },
    ],
    quickActions: [
      t('\u65b0\u5efa\u91c7\u8d2d\u8ba1\u5212'),
      t('\u65b0\u5efa\u91c7\u8d2d\u8ba2\u5355'),
      t('\u65b0\u5efa\u5165\u5e93\u5355'),
      t('\u65b0\u5efa\u751f\u4ea7\u5de5\u5355'),
      t('\u65b0\u5efa\u53d1\u8d27\u5355'),
    ],
  },
  processCenter: {
    planning: [
      { id: 'planning-demand', name: t('\u8ba1\u5212\u6d41\u7a0b'), status: t('\u9700\u6c42\u6c47\u603b'), owner: t('\u8ba1\u5212\u7ecf\u7406'), pending: 6 },
    ],
    purchase: [
      { id: 'purchase-order', name: t('\u91c7\u8d2d\u6d41\u7a0b'), status: t('\u5f85\u5ba1\u6279'), owner: t('\u91c7\u8d2d\u7ecf\u7406'), pending: 8 },
    ],
    warehouse: [
      { id: 'warehouse-inbound', name: t('\u4ed3\u50a8\u6d41\u7a0b'), status: t('\u5f85\u5165\u5e93'), owner: t('\u4ed3\u5e93\u4e3b\u7ba1'), pending: 5 },
    ],
    production: [
      { id: 'production-workorder', name: t('\u751f\u4ea7\u6d41\u7a0b'), status: t('\u6267\u884c\u4e2d'), owner: t('\u751f\u4ea7\u4e3b\u7ba1'), pending: 9 },
    ],
    quality: [
      { id: 'quality-inspection', name: t('\u54c1\u63a7\u6d41\u7a0b'), status: t('\u5f85\u68c0\u9a8c'), owner: t('\u8d28\u91cf\u7ecf\u7406'), pending: 4 },
    ],
    shipping: [
      { id: 'shipping-delivery', name: t('\u53d1\u8d27\u6d41\u7a0b'), status: t('\u5f85\u590d\u6838'), owner: t('\u7269\u6d41\u4e3b\u7ba1'), pending: 7 },
    ],
    finance: [
      { id: 'finance-settlement', name: t('\u8d22\u52a1\u7ed3\u7b97\u6d41\u7a0b'), status: t('\u5f85\u7ed3\u7b97'), owner: t('\u8d22\u52a1\u4e3b\u7ba1'), pending: 3 },
    ],
    performance: [
      { id: 'performance-benefit', name: t('\u7ee9\u6548\u4e0e\u6548\u76ca\u6d41\u7a0b'), status: t('\u5206\u6790\u4e2d'), owner: t('\u8fd0\u8425\u7ecf\u7406'), pending: 2 },
    ],
  },
  organization: {
    company: {
      name: 'PalmCloud Enterprise',
      legalEntity: 'PalmCloud Manufacturing Co.',
      businessUnit: t('\u4f01\u4e1a\u8fd0\u8425\u4e2d\u5fc3'),
    },
    departments: [
      { id: 'dept-procurement', name: t('\u91c7\u8d2d\u90e8'), owner: t('\u91c7\u8d2d\u7ecf\u7406'), people: 18, processOwner: t('\u91c7\u8d2d\u6d41\u7a0b') },
      { id: 'dept-production', name: t('\u751f\u4ea7\u90e8'), owner: t('\u751f\u4ea7\u4e3b\u7ba1'), people: 42, processOwner: t('\u751f\u4ea7\u6d41\u7a0b') },
      { id: 'dept-warehouse', name: t('\u4ed3\u50a8\u90e8'), owner: t('\u4ed3\u5e93\u4e3b\u7ba1'), people: 20, processOwner: t('\u4ed3\u50a8\u6d41\u7a0b') },
      { id: 'dept-finance', name: t('\u8d22\u52a1\u90e8'), owner: t('\u8d22\u52a1\u4e3b\u7ba1'), people: 12, processOwner: t('\u8d22\u52a1\u7ed3\u7b97\u6d41\u7a0b') },
    ],
    roles: [
      { id: 'role-procurement-manager', name: t('\u91c7\u8d2d\u7ecf\u7406'), responsibility: t('\u91c7\u8d2d\u5ba1\u6279\u4e0e\u4f9b\u5e94\u5546\u534f\u540c') },
      { id: 'role-production-lead', name: t('\u751f\u4ea7\u4e3b\u7ba1'), responsibility: t('\u5de5\u5355\u4e0b\u8fbe\u4e0e\u4ea7\u80fd\u534f\u8c03') },
      { id: 'role-finance-controller', name: t('\u8d22\u52a1\u4e3b\u7ba1'), responsibility: t('\u7ed3\u7b97\u5ba1\u6279\u4e0e\u8d44\u91d1\u590d\u6838') },
    ],
    users: [
      { id: 'user-001', name: t('\u674e\u96f7'), department: t('\u91c7\u8d2d\u90e8'), role: t('\u91c7\u8d2d\u7ecf\u7406') },
      { id: 'user-002', name: t('\u738b\u654f'), department: t('\u8d22\u52a1\u90e8'), role: t('\u8d22\u52a1\u4e3b\u7ba1') },
      { id: 'user-003', name: t('\u5f20\u5de5'), department: t('\u751f\u4ea7\u90e8'), role: t('\u751f\u4ea7\u4e3b\u7ba1') },
    ],
    permissions: [
      { id: 'perm-purchase-approve', name: t('\u91c7\u8d2d\u5ba1\u6279'), role: t('\u91c7\u8d2d\u7ecf\u7406'), scope: t('\u90e8\u95e8\u91c7\u8d2d') },
      { id: 'perm-finance-settle', name: t('\u8d22\u52a1\u7ed3\u7b97'), role: t('\u8d22\u52a1\u4e3b\u7ba1'), scope: t('\u7ed3\u7b97\u5355\u636e') },
      { id: 'perm-workorder-release', name: t('\u5de5\u5355\u4e0b\u8fbe'), role: t('\u751f\u4ea7\u4e3b\u7ba1'), scope: t('\u751f\u4ea7\u5de5\u5355') },
    ],
  },
}

export const processGroups = [
  { key: 'planning', title: t('\u8ba1\u5212\u6d41\u7a0b') },
  { key: 'purchase', title: t('\u91c7\u8d2d\u6d41\u7a0b') },
  { key: 'warehouse', title: t('\u4ed3\u50a8\u6d41\u7a0b') },
  { key: 'production', title: t('\u751f\u4ea7\u6d41\u7a0b') },
  { key: 'quality', title: t('\u54c1\u63a7\u6d41\u7a0b') },
  { key: 'shipping', title: t('\u53d1\u8d27\u6d41\u7a0b') },
  { key: 'finance', title: t('\u8d22\u52a1\u7ed3\u7b97\u6d41\u7a0b') },
  { key: 'performance', title: t('\u7ee9\u6548\u4e0e\u6548\u76ca\u6d41\u7a0b') },
]

export function getEnterpriseOperationModel() {
  return enterpriseOperationModel
}
