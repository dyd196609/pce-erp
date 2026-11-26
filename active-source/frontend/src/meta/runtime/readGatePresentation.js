// Presentation of READ-GATE-REPAIR-20261116-R1; no scope/permission inference.
import {createReadFailedFactLoad} from './pceFactLoadContract.js'
export function readGateFailure(response, error, apiUrl) {
  const source = response?.success === false ? response : error?.response || error
  const original = source?.factLoadFacts || source?.data?.factLoadFacts || {}
  const httpStatus = Number(original.httpStatus || source?.meta?.status || source?.status || 0)
  const errorCode = source?.error?.code || original.errorCode || 'READ_CONTRACT_INVALID'
  const errorMessage = source?.error?.message || original.errorMessage || error?.message || '原服务未返回有效事实'
  const failure = createReadFailedFactLoad({...original, apiUrl: original.apiUrl || apiUrl, httpStatus, errorCode, errorMessage})
  return {...failure, factSource:'server', recordCount:null, passed:false,
    statusLabel: ({401:'未登录或会话已失效',403:'无此读取资格',404:'未找到当前可读记录',409:'来源归属待核',500:'读取失败'})[httpStatus] || '读取失败'}
}
export function replaceReadGateFacts(target, value) {
  for (const key of Object.keys(target)) delete target[key]
  Object.assign(target, value)
}
export function scmReadGateData(response, rawCanary = false) {
  if (!rawCanary && response?.success !== true) throw new Error(response?.error?.message || '原服务读取未成功')
  const data = rawCanary ? response : response.data
  if (data?.factSource !== 'server' || !Array.isArray(data.objects) || !Number.isSafeInteger(data.recordCount) || data.recordCount < 0) throw new Error('原服务事实或授权数量合同不完整')
  if (data.status === 'schema_not_deployed') throw new Error('服务端结构未部署，数量未知')
  return data
}
