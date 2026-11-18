export const p2pDisplayDictionary = {
  riskType: {
    多供应商付款拆分提醒: '多供应商付款拆分提醒',
    多供应商链断裂: '多供应商链断裂',
    供应商链断裂: '供应商链断裂',
    库存链异常: '库存链异常',
    库存链待确认: '库存链待确认',
    引用缺失: '引用缺失',
    成本链断裂: '成本链断裂',
    业务节点缺失: '业务节点缺失',
    金额不一致: '金额不一致',
    金额异常: '金额异常',
    付款异常: '付款异常',
    付款链异常: '付款链异常',
    付款超出应付: '付款超出应付',
    付款对象缺失: '付款对象缺失',
    报表异常: '报表异常',
    报表验证风险: '报表验证风险',
    数据一致性风险: '数据一致性风险',
    数据一致性提醒: '数据一致性提醒',
  },
  causeType: {
    system_issue: '系统逻辑问题',
    operation_issue: '人工操作问题',
    test_data_issue: '测试数据问题',
    process_design_issue: '流程设计问题',
    unknown: '待确认',
  },
  lifecycleStatus: {
    open: '待处理',
    pending: '待确认',
    confirmed: '已确认',
    processing: '处理中',
    resolved: '已解决',
    closed: '已关闭',
    ignored: '已忽略',
    rejected: '不成立',
    not_started: '未开始',
  },
  validationModule: {
    purchase: '采购订单一致性验证',
    supplier: '供应商一致性验证',
    receipt: '收货一致性验证',
    inspection: '检验一致性验证',
    inventoryChain: '库存链一致性验证',
    inventory: '入库一致性验证',
    payable: '应付一致性验证',
    payment: '付款一致性验证',
    ledger: '模拟总账一致性验证',
    report: '报表一致性验证',
  },
  validationStatus: {
    passed: '验证通过',
    warning: '验证有提醒',
    blocked: '验证阻断',
    not_checked: '未验证',
    normal: '正常',
    missing: '缺失',
    abnormal: '异常',
  },
  riskLevel: {
    严重: '严重',
    提醒: '提醒',
    critical: '严重',
    warning: '提醒',
    info: '设计提醒',
    normal: '正常',
  },
  module: {
    SCM: 'SCM',
    WMS: 'WMS',
    QMS: 'QMS',
    Finance: 'Finance',
    Architecture: 'Architecture',
    ERP: 'ERP',
    TestData: 'TestData',
    采购订单维度: '采购订单维度',
    供应商: '供应商',
    库存链: '库存链',
    付款: '付款',
    报表: '报表',
  },
  mojibake: {
    '澶氫緵搴斿晢浠樻鎷嗗垎鎻愰啋': '多供应商付款拆分提醒',
    '渚涘簲鍟嗛摼鏂': '供应商链断裂',
    '閲囪喘璁㈠崟缁村害': '采购订单维度',
    '鎻愰啋': '提醒',
    '涓ラ噸': '严重',
    '浠樻': '付款',
    '閲戦寮傚父': '金额异常',
    '浠樻寮傚父': '付款异常',
    '鎶ヨ〃寮傚父': '报表异常',
    '绯荤粺闂': '系统逻辑问题',
    '浜哄伐鎿嶄綔闂': '人工操作问题',
    '娴嬭瘯鏁版嵁闂': '测试数据问题',
    '娴佺▼璁捐闂': '流程设计问题',
    '鍘熷洜鍒嗙被': '原因分类',
    '鏂偣浣嶇疆': '断点位置',
    '椋庨櫓': '风险',
    '椋庨櫓绫诲瀷': '风险类型',
    '椋庨櫓绛夌骇': '风险等级',
    '鏉ユ簮鍗曟嵁': '来源单据',
    '褰卞搷妯″潡': '影响模块',
    '璐ｄ换妯″潡': '责任模块',
    '璐ｄ换瑙掕壊': '责任角色',
    '澶勭悊寤鸿': '处理建议',
    '搴撳瓨娴佹按': '库存流水',
    '妫€楠屽崟': '检验单',
    '鍏ュ簱': '入库',
    '鏃堕棿': '时间',
    '瑙掕壊': '角色',
    '鏀惰揣缂哄け': '收货缺失',
    '鍏ュ簱缂哄け': '入库缺失',
    '搴斾粯缂哄け': '应付缺失',
    '鎬昏处妯℃嫙寮傚父': '总账模拟异常',
  },
}

const mojibakePattern = /[�]|浠樻|鎻愰啋|閲囪喘|缁村害|澶氫緵|寒|塞|涓|椋|楠|閾|寰|绛|鏌|璐|搴|渚|浠|鎶|妯|鐞|鏁|鍏|閲|姝|瀛|彂/

function flattenDictionary() {
  return new Map(Object.values(p2pDisplayDictionary).flatMap((group) => Object.entries(group)))
}

const displayTextMap = flattenDictionary()

export function decodeDisplayText(value, fallback = '-') {
  if (value === null || value === undefined) return fallback
  const text = String(value).trim()
  if (!text) return fallback
  if (displayTextMap.has(text)) return displayTextMap.get(text)

  let decoded = text
  displayTextMap.forEach((to, from) => {
    decoded = decoded.split(from).join(to)
  })
  if (decoded !== text) return decoded

  return mojibakePattern.test(text) ? fallback : text
}

export function displayCellText(row, column, cellValue) {
  return decodeDisplayText(cellValue)
}

export function displayRiskType(value) {
  return decodeDisplayText(p2pDisplayDictionary.riskType[value] || value, '数据一致性风险')
}

export function displayCauseType(value) {
  return decodeDisplayText(p2pDisplayDictionary.causeType[value] || value, '待确认')
}

export function displayLifecycleStatus(value) {
  return decodeDisplayText(p2pDisplayDictionary.lifecycleStatus[value] || value, '待处理')
}

export function displayValidationModule(value) {
  return decodeDisplayText(p2pDisplayDictionary.validationModule[value] || value, '验证模块')
}

export function displayValidationStatus(value) {
  return decodeDisplayText(p2pDisplayDictionary.validationStatus[value] || value, '待确认')
}
