import { generateERP } from '../ai/aiErpGenerator'
import { runPlatformV13 } from '../kernel/metaKernelV13'
import { publishERPApp } from '../market/erpMarketV19'

// AI → ERP → Market
export const aiToMarket = async (prompt) => {
  // 1. AI生成ERP
  const erp = await generateERP(prompt)

  // 2. 运行系统
  const instance = runPlatformV13({
    meta: erp.meta,
    action: { action: 'init' },
    row: {},
    user: { id: 1 },
  })

  // 3. 发布到应用市场
  const app = publishERPApp({
    name: prompt,
    meta: erp.meta,
    bpm: erp.workflow,
    price: 99,
  })

  return {
    instance,
    app,
  }
}
