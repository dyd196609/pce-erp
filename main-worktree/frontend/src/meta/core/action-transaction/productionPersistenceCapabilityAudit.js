export const productionPersistenceCapabilityAudit = [
  ['supportsAtomicTransaction', 'src/meta/runtime/transactionEngine.js', 'commitChanges', '逐步骤调用 writeDatabase；无数据库事务边界'],
  ['supportsUniqueIdempotencyKey', '', '', '未发现持久化 idempotencyKey 唯一约束'],
  ['supportsUniqueSourceKey', '', '', '未发现采购对账 sourceKey 唯一目标约束'],
  ['supportsUniqueDocumentNumber', '', '', '未发现正式单据编号唯一索引或服务'],
  ['supportsDurableSourceLock', '', '', '未发现跨进程持久来源锁'],
  ['supportsCommitOutcomeRecovery', '', '', '未发现提交结果不确定恢复接口'],
  ['supportsAtomicAuditWrite', 'src/meta/runtime/transactionEngine.js', 'commitChanges', '审计未与业务对象建立原子提交证明'],
  ['supportsServerSideAuthorization', 'src/api/request.js', 'axios client', '仅存在客户端请求封装，无服务端授权能力证明'],
].map(([capability, implementationFile, implementationFunction, limitation]) => ({
  capability, supported: false, implementationFile, implementationFunction,
  evidence: implementationFile ? `${implementationFile}#${implementationFunction}` : 'repository audit: no qualifying implementation found', limitation,
}))

export function auditProductionPersistenceCapabilities() {
  return {
    capabilities: productionPersistenceCapabilityAudit,
    productionTransactionCapabilityGate: false,
    productionFormalExecutionEnabled: false,
    allHardCapabilitiesSupported: false,
  }
}
