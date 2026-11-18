export const PDE_VERSION_RULESET_VERSION = 'PCE-PDE-VERSION-GOVERNANCE-V101'

export const pdeVersionRules = Object.freeze([
  Object.freeze({ ruleId: 'PDE-VERSION-001', title: '产品必须有版本' }),
  Object.freeze({ ruleId: 'PDE-VERSION-002', title: 'BOM必须有版本' }),
  Object.freeze({ ruleId: 'PDE-VERSION-003', title: 'Routing必须有版本' }),
  Object.freeze({ ruleId: 'PDE-VERSION-004', title: '工程资料必须关联版本' }),
  Object.freeze({ ruleId: 'PDE-VERSION-005', title: '失效版本不能作为生产输入' }),
  Object.freeze({ ruleId: 'PDE-VERSION-006', title: 'ECN必须记录前后版本关系' }),
])

function result(ruleId, passed, evidence) {
  return {
    ruleId,
    title: pdeVersionRules.find(rule => rule.ruleId === ruleId)?.title || '',
    status: passed ? 'PASS' : 'FAIL',
    evidence,
  }
}

export function evaluatePdeVersionRules({ modelSource, canary, relationships }) {
  const codes = new Set(relationships.map(item => item.relationshipCode))
  return [
    result(
      'PDE-VERSION-001',
      /class ProductVersion[\s\S]*product\s*=\s*models\.ForeignKey/.test(modelSource)
        && canary.products.every(product => (
          canary.productVersions.some(version => version.productCode === product.productCode)
        )),
      { productCount: canary.products.length, versionCount: canary.productVersions.length },
    ),
    result(
      'PDE-VERSION-002',
      codes.has('PDE_PRODUCT_VERSION_BOM_VERSION')
        && /class BOMVersion[\s\S]*product_version\s*=\s*models\.ForeignKey/.test(modelSource)
        && canary.bomVersions.every(version => version.productVersionNo),
      { bomVersionCount: canary.bomVersions.length },
    ),
    result(
      'PDE-VERSION-003',
      codes.has('PDE_PRODUCT_VERSION_ROUTING_VERSION')
        && /class RoutingVersion[\s\S]*product_version\s*=\s*models\.ForeignKey/.test(modelSource)
        && canary.routingVersions.every(version => version.productVersionNo),
      { routingVersionCount: canary.routingVersions.length },
    ),
    result(
      'PDE-VERSION-004',
      codes.has('PDE_PRODUCT_VERSION_DOCUMENT_VERSION')
        && /class EngineeringDocumentVersion[\s\S]*product_version\s*=\s*models\.ForeignKey/.test(modelSource)
        && /class EngineeringDocumentVersion[\s\S]*related_bom\s*=\s*models\.ForeignKey/.test(modelSource)
        && /class EngineeringDocumentVersion[\s\S]*related_routing\s*=\s*models\.ForeignKey/.test(modelSource)
        && canary.engineeringDocumentVersions.every(version => (
          version.productVersionNo && version.bomVersionNo && version.routingVersionNo
        )),
      { engineeringDocumentVersionCount: canary.engineeringDocumentVersions.length },
    ),
    result(
      'PDE-VERSION-005',
      /class EffectiveDateControl[\s\S]*def clean\(self\)/.test(modelSource)
        && /!= "released"/.test(modelSource)
        && canary.effectiveDateChecks.every(check => (
          check.selectedStatus === 'released' && check.obsoleteSelected === false
        )),
      { effectiveDateChecks: canary.effectiveDateChecks },
    ),
    result(
      'PDE-VERSION-006',
      codes.has('PDE_ECN_BEFORE_VERSION')
        && codes.has('PDE_ECN_AFTER_VERSION')
        && /class EngineeringChangeNotice[\s\S]*before_version\s*=\s*models\.ForeignKey/.test(modelSource)
        && /class EngineeringChangeNotice[\s\S]*after_version\s*=\s*models\.ForeignKey/.test(modelSource)
        && canary.ecns.every(ecn => (
          ecn.beforeVersionNo && ecn.afterVersionNo
          && ecn.beforeVersionNo !== ecn.afterVersionNo
        )),
      { ecnCount: canary.ecns.length },
    ),
  ]
}

