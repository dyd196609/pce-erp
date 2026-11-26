"""Controlled configuration over the sole formal resource maintenance chain.

Only explicitly declared measurement corrections and new capacity facts are
allowed. Historical EOR, rules, capacities, resources and routing are preserved.
"""
from copy import deepcopy

from django.db import transaction
from system.models import Company, Process
from .models import EngineeringOperationRequirement
from .operation_requirement_service import _authorize, _executor, _fail, _unit
from .production_foundation_service import ProductionFoundationService

CONTRACT = 'PCE-MANUFACTURING-RESOURCE-CONFIGURATION-V1'
RESOURCE = 'production.master_data.resource.maintain'
CAPACITY = 'production.master_data.capacity.maintain'


class ManufacturingResourceConfigurationService:
    @classmethod
    @transaction.atomic
    def configure(cls, *, user, package, reason):
        if (not isinstance(package, dict) or package.get('contractVersion') != CONTRACT
            or package.get('companyId') != user.company_id or not str(reason).strip()
            or not str(package.get('businessReason', '')).strip()):
            _fail('RESOURCE_PACKAGE_INVALID', '必须提供正式配置合同、公司范围及固定业务依据')
        _executor(user)
        Company.objects.select_for_update().get(pk=user.company_id)
        corrections, capacities = [], []
        for row in package.get('operationCorrections', []):
            _authorize(user, RESOURCE)
            values, expected = row.get('values', {}), row.get('expected', {})
            allowed = {'calculation_basis', 'calculation_uom_id'}
            if set(values) != allowed or set(expected) != allowed:
                _fail('RESOURCE_CORRECTION_SCOPE_INVALID', '受控修正只能同时维护工序核算维度及正式单位')
            operation = Process.objects.select_for_update().filter(pk=row['objectId'], company_id=user.company_id).first()
            if not operation:
                _fail('RESOURCE_CORRECTION_SCOPE_INVALID', '待修正正式工序缺失或跨公司')
            unit = _unit(values['calculation_uom_id'], user.company_id)
            if values['calculation_basis'] != unit.dimension:
                _fail('RESOURCE_CORRECTION_UOM_INVALID', '工序正式单位维度必须与核算维度相同')
            if not all(getattr(operation, key) == value for key, value in expected.items()) and not all(
                getattr(operation, key) == value for key, value in values.items()):
                _fail('RESOURCE_CORRECTION_CONFLICT', '当前工序不符合预期原值或已批准目标值')
            if EngineeringOperationRequirement.objects.filter(operation=operation).exclude(uom=unit).exists():
                _fail('RESOURCE_UNIT_IN_HISTORICAL_EOR', '已有历史EOR使用不同单位；禁止改变其正式工序计量')
            result = ProductionFoundationService.write('operations', user=user,
                payload={**values, 'reason': package['businessReason']}, object_id=operation.pk,
                idempotency_key=row['requestKey'], source_identity={})
            operation.refresh_from_db()
            if any(getattr(operation, key) != value for key, value in values.items()):
                _fail('RESOURCE_CORRECTION_READBACK_FAILED', '工序单位修正未形成正式持久化结果')
            corrections.append(result)
        for row in package.get('capacities', []):
            _authorize(user, CAPACITY)
            payload = deepcopy(row['payload'])
            if payload.get('company_id') != user.company_id:
                _fail('RESOURCE_PACKAGE_INVALID', '新产能必须属于办理人当前公司')
            operation = Process.objects.filter(pk=payload.get('operation_id'), company_id=user.company_id).first()
            unit = _unit(payload.get('uom_id'), user.company_id)
            if not operation or operation.calculation_uom_id != unit.pk:
                _fail('RESOURCE_CORRECTION_UOM_INVALID', '产能单位必须精确等于正式工序核算单位，禁止面积与长度互换')
            payload['reason'] = package['businessReason']
            result = ProductionFoundationService.write('standard-capacities', user=user, payload=payload,
                idempotency_key=row['requestKey'], source_identity=row['sourceIdentity'])
            from .manufacturing_capacity_scope import capacity_usage_scope_proof
            from .models import StandardCapacity
            capacity = StandardCapacity.objects.get(pk=result['row']['id'])
            fields = {name: field for field in capacity._meta.concrete_fields
                      for name in (field.name, field.attname)}
            for key, value in payload.items():
                if key == 'reason':
                    continue
                field = fields.get(key)
                if field is None or getattr(capacity, field.attname) != field.to_python(value):
                    _fail('RESOURCE_CAPACITY_PAYLOAD_CONFLICT', '正式来源身份已有产能与本次配置不一致；禁止覆盖或误认请求成功')
            if capacity_usage_scope_proof(capacity) is None:
                _fail('MANUFACTURING_CAPACITY_SCOPE_INVALID', '新产能必须声明并证明正式EOR用途范围')
            capacities.append(result)
        return {'contractVersion': CONTRACT, 'operationCorrections': corrections, 'capacities': capacities,
            'factSource': 'server', 'businessWriteCount': sum(not r.get('idempotentReplay', False)
                for r in [*corrections, *capacities]), 'auditWriteCount': sum(not r.get('idempotentReplay', False)
                for r in [*corrections, *capacities])}
