"""Read-only saved-record presentation. Never resolve latest design or recalculate."""
from hashlib import sha256
import json

CONTRACT = 'PDE-SAVED-CALCULATION-CONTEXT-V1'


def _hash(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), default=str).encode()).hexdigest()


def project_saved_context(calculation, snapshots):
    """Only persisted record inputs/results and its exact frozen baseline items."""
    trace = calculation.get('trace') or {}
    baseline = trace.get('baselineReference') or {}
    source = trace.get('sourceReference') or {}
    objects = trace.get('objectInputSnapshot') or []
    context = {'contractVersion': CONTRACT, 'factSource': 'server', 'readStatus': 'loaded',
        'statusLabel': '已保存核算冻结资料', 'calculationId': calculation['id'],
        'calculationNo': calculation['calculationNo'], 'calculationRevision': calculation['revision'],
        'companyId': calculation['companyId'], 'salesOrderItemId': calculation['salesOrderItemId'],
        'orderEngineeringInstanceId': calculation['orderEngineeringInstanceId'],
        'orderNo': baseline.get('orderNo'), 'baselineId': baseline.get('id'),
        'baselineNo': baseline.get('baselineNo'), 'sourceRecordId': calculation['sourceRecordId'],
        'sourceVersion': source.get('sourceVersion'), 'sourceNo': source.get('sourceNo'),
        'businessWriteSideEffectCount': 0, 'rows': [],
        'materialStatusLabel': '已生成' if calculation.get('materialRequirements') else '本次核算未生成',
        'operationStatusLabel': '已生成' if calculation.get('operationRequirements') else '本次核算未生成'}
    if not objects:
        # Older records keep their original input/trace contract. Do not invent a
        # baseline or substitute a current/Excel design for an absent snapshot.
        context.update(readStatus='unavailable', statusLabel='历史记录未冻结对象级页面资料；原核算输入与结果仍可查看')
        return context
    if trace.get('salesOrderItemId') != calculation['salesOrderItemId'] or trace.get('orderEngineeringInstanceId') != calculation['orderEngineeringInstanceId']:
        raise ValueError('SAVED_CONTEXT_RECORD_SCOPE_MISMATCH')
    if source.get('id') != calculation['sourceRecordId'] or not baseline.get('id'):
        raise ValueError('SAVED_CONTEXT_SOURCE_BASELINE_REQUIRED')
    by_id = {item['id']: item for item in snapshots}
    for obj in objects:
        inp = obj.get('input') or {}; identity = inp.get('sourceIdentity') or {}
        item = by_id.get(obj.get('baselineItemId'))
        if not item or any(item.get(k) != v for k, v in {
            'companyId': calculation['companyId'], 'baselineId': baseline['id'],
            'salesOrderId': baseline.get('orderId'), 'sourceRecordId': calculation['sourceRecordId'],
            'designItemId': obj.get('designItemId'), 'contentHash': obj.get('contentHash')}.items()):
            raise ValueError('SAVED_CONTEXT_FROZEN_ITEM_MISMATCH')
        snap = item['snapshot']
        if _hash(snap) != item['contentHash'] or inp.get('baselineContentHash') != item['contentHash']:
            raise ValueError('SAVED_CONTEXT_CONTENT_HASH_MISMATCH')
        design = snap.get('designItem') or {}; revision = snap.get('revision') or {}
        frozen_source = snap.get('source') or {}; data = revision.get('designData') or {}
        native = identity.get('type') == 'NATIVE_DESIGN_REVISION'
        if inp.get('sourceRecordId') != calculation['sourceRecordId']:
            raise ValueError('SAVED_CONTEXT_INPUT_SOURCE_MISMATCH')
        if native and any(identity.get(k) != v for k, v in {
            'companyId': calculation['companyId'], 'salesOrderId': baseline.get('orderId'),
            'salesOrderItemId': calculation['salesOrderItemId'], 'sourceRecordId': calculation['sourceRecordId'],
            'designItemId': obj['designItemId'], 'designRevisionId': revision.get('id'),
            'designRevision': inp.get('revision'), 'baselineId': baseline['id'], 'baselineItemId': item['id']}.items()):
            raise ValueError('SAVED_CONTEXT_NATIVE_IDENTITY_MISMATCH')
        if revision and (revision.get('revision') != inp.get('revision') or item.get('designRevisionId') != revision.get('id')):
            raise ValueError('SAVED_CONTEXT_REVISION_MISMATCH')
        if native and (any(inp.get(k) != revision.get(k) for k in ('designLength', 'designWidth', 'designThickness', 'designUomId', 'paintProcessTypeId'))
                or inp.get('physicalQuantity') != design.get('physicalQuantity')
                or inp.get('physicalUom') != design.get('physicalUom')
                or _hash(inp.get('nativeCalculationInputs')) != _hash(data.get('calculationInputs'))):
            raise ValueError('SAVED_CONTEXT_FROZEN_INPUT_MISMATCH')
        if frozen_source.get('sourceVersion') != obj.get('sourceVersion') or frozen_source.get('recordId') != calculation['sourceRecordId']:
            raise ValueError('SAVED_CONTEXT_FROZEN_SOURCE_MISMATCH')
        raw = frozen_source.get('rawValue') or {}; contract = inp.get('nativeCalculationInputs') or {}
        units = contract.get('unitProofs', {}).get('units', {})
        uom = units.get(str(inp.get('designUomId')), {}).get('code')
        if not native: uom = raw.get('designUomLabel')  # never guess a missing frozen unit
        dimensions = []
        def dimension(key, label, value, unit):
            if value not in (None, ''): dimensions.append({'key': key, 'label': label, 'value': str(value), 'unit': unit or '单位未冻结'})
        basis = contract.get('dimensionBasis')
        dimension('inputHeight', '门洞输入高' if basis == 'OPENING' else '设计输入高／长', inp.get('designLength'), uom)
        dimension('inputWidth', '门洞输入宽' if basis == 'OPENING' else '设计输入宽', inp.get('designWidth'), uom)
        dimension('actualThickness', '实际厚度' if native else '设计厚度', inp.get('designThickness'), uom)
        depth = contract.get('casingDepth') or {}
        dimension('inputCasingDepth', '门套深度输入', depth.get('value'), units.get(str(depth.get('uomId')), {}).get('code'))
        output_labels = {'N': '门套计算高', 'O': '门套计算宽', 'P': '门套计算深', 'R': '门扇计算高', 'S': '门扇计算宽'}
        for result in trace.get('resultSnapshot') or []:
            if result.get('sourceKey') == obj.get('sourceKey') and result.get('canonicalField') in output_labels:
                dimension('result'+result['canonicalField'], output_labels[result['canonicalField']], (result.get('value') or {}).get('decimal'), result.get('unit'))
        sheet, row_number = inp.get('sourceSheet'), inp.get('sourceRow')
        if not native and (not sheet or row_number in (None, '')):
            raise ValueError('SAVED_CONTEXT_IMPORTED_LOCATOR_REQUIRED')
        branch = {'PAINTED': '有漆', 'PAINT_FREE': '免漆'}.get(contract.get('paintBranch'))
        paint_id = inp.get('paintProcessTypeId')
        paint = inp.get('paintProcess') or (f'{branch}；冻结油漆工艺ID {paint_id}（名称未冻结）' if branch and paint_id else '冻结资料未提供涂装')
        missing = [label for label, value in [('正式材料身份', inp.get('materialId')), ('封边方式', inp.get('edgeMethod')), ('见光条件', inp.get('visibleCondition')), ('颜色／版号', inp.get('finishOrColor')), ('五金', data.get('hardware')), ('玻璃', data.get('glass'))] if value in (None, '')]
        row = {'id': item['id'], 'baselineItemId': item['id'], 'designItemId': obj['designItemId'],
            'designItemNo': obj.get('designItemNo'), 'itemName': design.get('itemName'),
            'salesOrderItemId': calculation['salesOrderItemId'], 'orderLineLabel': f"订单行ID {calculation['salesOrderItemId']}",
            'orderNo': baseline.get('orderNo'), 'sourceRecordId': calculation['sourceRecordId'],
            'sourceVersion': obj.get('sourceVersion'), 'sourceKey': obj.get('sourceKey'),
            'sourceType': identity.get('type') or 'EXCEL_SOURCE_ROW', 'sourceSheet': sheet, 'sourceRow': row_number,
            'sourceLocationLabel': '不适用／原生设计来源' if native else f'{sheet} 第{row_number}行',
            'sourceCellLabel': '不适用／原生设计来源' if native else '按原导入单元格追溯',
            'revision': inp.get('revision'), 'designRevisionId': revision.get('id'), 'inputAuthority': '已保存核算冻结基线项',
            'productCategoryId': inp.get('productCategoryId'), 'productCategoryName': raw.get('product') or f"冻结分类ID {inp.get('productCategoryId')}" if inp.get('productCategoryId') else '分类未冻结',
            'product': raw.get('product') or design.get('itemName'), 'component': design.get('itemName'),
            'space': design.get('space'), 'installationPosition': design.get('installationPosition'),
            'physicalQuantity': inp.get('physicalQuantity'), 'physicalUom': inp.get('physicalUom'),
            'physicalUomName': inp.get('physicalUom'), 'physicalUomMatchStatus': 'FROZEN',
            'quantity': inp.get('physicalQuantity'), 'unit': inp.get('physicalUom'), 'unitStatusLabel': '冻结数量／单位',
            'dimensionSemantics': dimensions, 'designUom': uom, 'paintProcess': paint,
            'structureLabel': {'SINGLE_LEAF': '单开门', 'SINGLE_CASING': '单面套'}.get(contract.get('structure'), '结构未冻结'),
            'edgeMethod': inp.get('edgeMethod'), 'edgeMode': inp.get('edgeMethod'), 'visibleCondition': inp.get('visibleCondition'),
            'colorVersion': inp.get('finishOrColor'), 'materialId': inp.get('materialId'),
            'materialStatusLabel': '冻结正式材料ID '+str(inp['materialId']) if inp.get('materialId') else '未绑定正式材料；不影响查看已保存工程净量',
            'processConfigurationLabel': inp.get('processConfigurationCode') or '工艺配置未冻结',
            'processingNote': data.get('configurationNotes'), 'hardware': data.get('hardware'), 'glass': data.get('glass'),
            'remainingConfirmations': missing, 'designGaps': missing, 'missingCalculationFields': [],
            'calculationStatusLabel': '已保存输入；非当前候选校验', 'savedFrozen': True,
            'provenanceLabel': (contract.get('provenance') or {}).get('classification') or '按冻结来源追溯'}
        context['rows'].append(row)
    return context


def saved_context_from_record(calculation, payload):
    """Fetch exact immutable references; no latest revision or current master lookup."""
    from .models import OrderEngineeringBaselineItem
    objects = (payload.get('trace') or {}).get('objectInputSnapshot') or []
    items = OrderEngineeringBaselineItem.objects.filter(pk__in=[o.get('baselineItemId') for o in objects],
        baseline__company_id=calculation.company_id,
        design_item__sales_order_item_id=calculation.sales_order_item_id).select_related('baseline')
    reference = (payload.get('trace') or {}).get('baselineReference') or {}
    if any(i.baseline.snapshot_hash != reference.get('snapshotHash') for i in items):
        return {'contractVersion': CONTRACT, 'factSource': 'server', 'readStatus': 'read_failed',
            'statusLabel': '已保存核算基线指纹不一致', 'errorCode': 'SAVED_CONTEXT_BASELINE_HASH_MISMATCH',
            'rows': [], 'calculationId': calculation.pk, 'businessWriteSideEffectCount': 0}
    snapshots = [{'id': i.pk, 'companyId': i.baseline.company_id, 'salesOrderId': i.baseline.sales_order_id,
        'baselineId': i.baseline_id, 'sourceRecordId': i.source_record_id, 'designItemId': i.design_item_id,
        'designRevisionId': i.design_revision_id, 'contentHash': i.content_hash, 'snapshot': i.content_snapshot} for i in items]
    try:
        return project_saved_context(payload, snapshots)
    except ValueError as exc:
        return {'contractVersion': CONTRACT, 'factSource': 'server', 'readStatus': 'read_failed',
            'statusLabel': '已保存核算冻结资料校验失败', 'errorCode': str(exc), 'rows': [],
            'calculationId': calculation.pk, 'businessWriteSideEffectCount': 0}
