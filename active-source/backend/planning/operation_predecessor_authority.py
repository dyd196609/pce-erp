"""Internal, read-only completion authority for the explicit work-order DAG.

This is not a completion endpoint or a new authority. It reuses the existing
completion verifier without borrowing the successor's page permissions. A
request-local path/cache bounds recursive historical start verification.
"""
from pde.routing_read_context import routing_read_phase
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from decimal import Decimal, InvalidOperation
import sys
from django.db import connection

from .services import PlanningBusinessError
from .mes_test_source_bridge import _fail, _hash

CONTRACT = 'PCE-OPERATION-PREDECESSOR-AUTHORITY-V1'
TYPED_CONTRACT = 'PCE-OPERATION-PREDECESSOR-AUTHORITY-V2'
_context = ContextVar('operation_predecessor_authority', default=None)
_historical_proof_only = ContextVar('operation_predecessor_historical_proof_only', default=False)


@contextmanager
def verification_context():
    current = _context.get()
    token = None
    if current is None:
        current = {'active': [], 'completed': {}, 'rollbackGeneration': 0}
        token = _context.set(current)
    # Only a proven clean savepoint rollback preserves the read epoch. Unknown
    # boundaries and any attempted mutation remain conservative invalidations.
    savepoints = {}
    mutation_generation = 0
    def observe_rollback(execute, sql, params, many, sql_context):
        nonlocal mutation_generation
        statement = sql.strip().rstrip(';')
        import re
        match = re.fullmatch(r'(SAVEPOINT|RELEASE SAVEPOINT|ROLLBACK TO SAVEPOINT) (.+)', statement, re.I)
        physical = connection.connection
        if connection.vendor == 'sqlite' and match and match[1].upper() == 'SAVEPOINT':
            result = execute(sql, params, many, sql_context)
            savepoints[match[2]] = (physical, physical.total_changes, mutation_generation)
            return result
        rollback = statement.upper().startswith('ROLLBACK')
        baseline = savepoints.get(match[2]) if match and rollback else None
        clean = bool(baseline and baseline == (physical, physical.total_changes, mutation_generation))
        if not match and not rollback and not statement.upper().startswith(('SELECT ', 'EXPLAIN ', 'BEGIN', 'COMMIT')) and statement.upper() != 'PRAGMA DATA_VERSION':
            mutation_generation += 1
        try:
            result = execute(sql, params, many, sql_context)
        except BaseException:
            clean = False
            raise
        finally:
            if rollback and not clean:
                current['rollbackGeneration'] += 1
                from pde.routing_read_context import _current
                cache = _current.get()
                if cache is not None:
                    for key in list(cache):
                        if isinstance(key, tuple) and key and key[0] in ('mes_test_source_context', 'test_work_order_fresh'):
                            cache.pop(key, None)
            if match and match[1].upper() == 'RELEASE SAVEPOINT':
                savepoints.pop(match[2], None)
        return result
    try:
        if token is None:yield current
        else:
            with connection.execute_wrapper(observe_rollback):yield current
    finally:
        if token is not None:
            _context.reset(token)


def _proof_cache_epoch(context):
    """Only reuse proofs from this exact physical SQLite read/write epoch."""
    if connection.vendor!='sqlite':return None
    connection.ensure_connection()
    with connection.cursor() as cursor:
        cursor.execute('PRAGMA data_version');external_version=cursor.fetchone()[0]
    outer=id(connection.atomic_blocks[0]) if connection.in_atomic_block and connection.atomic_blocks else None
    epoch=(id(connection.connection),connection.connection.total_changes,external_version,
        outer,current_rollback_generation(context))
    previous=context.get('predecessorProofEpoch')
    if previous!=epoch:
        if previous is not None and context['active']:
            _fail('OPERATION_PREDECESSOR_READ_CHANGED','前序正式证明核验期间发生变化，请重新只读核查；未复用过期证明。')
        context['completed']={};context['predecessorProofEpoch']=epoch
    return epoch

def current_rollback_generation(context=None):
    return (context or _context.get() or {}).get('rollbackGeneration',0)


def _graph(task):
    """Iterative cycle and exact edge validation, never sequence+1 inference."""
    from pde.capacity_evidence_read_scope import evidence_cache
    from pde.operation_requirement_service import _read_once

    def read_operations():
        return tuple(task.work_order.operations.select_related('effective_step').order_by('sequence', 'pk'))

    # Reuse the persisted rows. Validate membership and each current task's edges below.
    cache = evidence_cache(task.company_id)
    operations = _read_once(cache, ('predecessor_operation_rows', task.company_id, task.work_order_id),
        read_operations)
    by_sequence = {op.sequence: op for op in operations}
    if (task.company_id != task.work_order.company_id or len(by_sequence) != len(operations)
            or task.source_operation_id not in {op.pk for op in operations}):
        return by_sequence, '前序公司、工单或工序身份不一致。'
    colors = {}
    stack = [(task.source_operation.sequence, False)]
    while stack:
        sequence, leaving = stack.pop()
        if leaving:
            colors[sequence] = 2
            continue
        if colors.get(sequence) == 1:
            return by_sequence, '正式路线前序依赖存在循环，不能开工。'
        if colors.get(sequence) == 2:
            continue
        operation = by_sequence.get(sequence)
        if operation is None:
            return by_sequence, '正式路线前序对象缺失，不能开工。'
        frozen = operation.source_snapshot.get('predecessorSequences')
        step = operation.effective_step
        if (not isinstance(frozen, list) or any(type(value) is not int or value <= 0 for value in frozen)
                or len(frozen) != len(set(frozen)) or sequence in frozen
                or not step.is_active or step.routing_version_id != operation.effective_routing_version_id
                or step.operation_id != operation.operation_id or step.predecessor_sequences != frozen):
            return by_sequence, '正式路线前序关系、有效步骤或冻结版本不一致。'
        colors[sequence] = 1
        stack.append((sequence, True))
        stack.extend((previous, False) for previous in reversed(frozen))
    return by_sequence, None


def _completion(previous, successor, context):
    from .workshop_task_models import ProductionWorkshopTask
    from .operation_start_models import ProductionOperationStart
    from system.models import User
    # Import only after both services have initialized. Never call completion
    # list/qualification or require the successor to review its predecessor.
    from . import operation_completion_service as completion

    continued=None
    if not _historical_proof_only.get():
        from .operation_continuation_service import execution_mode as continuation_mode
        continued=continuation_mode(previous,successor.created_by)
    if previous.source_snapshot.get('frozenStep', {}).get('applicability', {}).get('result') == 'NOT_APPLICABLE' and continued is None:
        return _exemption(previous, successor, context)
    nonquantified = bool(getattr(previous,'work_order_id',None) and ProductionWorkshopTask.objects.filter(
        source_operation_id=previous.pk,execution_mode='NON_QUANTIFIED_REQUIRED').exists())
    if previous.dependency_only and not nonquantified and not (continued and continued['ready']):
        if continued is not None:
            name = previous.source_snapshot.get('operationName') or previous.operation.name
            issues = continued['blockingReasons'] or ['当前执行依据待核。']
            _fail('OPERATION_PREDECESSOR_CONTINUATION_PENDING', f'前序「{name}」为当前必做。' + '；'.join(issues))
        result = previous.source_snapshot.get('frozenStep', {}).get('applicability', {}).get('result')
        label = {'NOT_APPLICABLE': '前序为不适用步骤，尚无可供执行链核验的正式免执行证明。',
            'PENDING': '前序适用性尚待正式确认，不能跳过。'}.get(result,
            '前序为依赖或不可统计节点，尚无适用的正式经过完成证明。')
        _fail('OPERATION_PREDECESSOR_NON_QUANTIFIED', label)
    try:
        amount=continued['referenceWorkload']['quantity'] if continued and continued['ready'] else previous.workload_quantity
        quantity_valid = Decimal(amount).is_finite() and Decimal(amount) > 0
    except (InvalidOperation, TypeError, ValueError):
        quantity_valid = False
    if not nonquantified and (not quantity_valid or not (continued['referenceWorkload']['uomId'] if continued and continued['ready'] else previous.workload_uom_id)):
        _fail('OPERATION_PREDECESSOR_NON_QUANTIFIED', '前序无合法可统计作业量及单位，不能伪造数量或跳过完成证明。')
    tasks = list(ProductionWorkshopTask.objects.filter(source_operation_id=previous.pk).select_related(
        'work_order__production_plan', 'source_operation__effective_step', 'source_operation__work_center__workshop',
        'workshop', 'work_center'))
    task = tasks[0] if len(tasks) == 1 else None
    if (not task or task.company_id != successor.company_id or task.work_order_id != successor.work_order_id
            or task.source_operation_id != previous.pk or task.status != 'dispatched'):
        if continued is not None:
            name = previous.source_snapshot.get('operationName') or previous.operation.name
            _fail('OPERATION_PREDECESSOR_TASK_UNPROVEN', f'前序「{name}」为当前必做，尚无本工单正式获派任务。')
        _fail('OPERATION_PREDECESSOR_TASK_UNPROVEN', '前序正式完成事实缺失：没有同公司同工单的正式获派任务。')
    epoch=_proof_cache_epoch(context)
    key = (task.company_id, task.work_order_id, task.pk, _historical_proof_only.get(),epoch)
    if key in context['active']:
        _fail('OPERATION_PREDECESSOR_CYCLE', '正式前序完成证明出现循环引用，不能开工。')
    # The business DAG is data-sized; this extra interpreter limit is a
    # fail-closed technical guard, not a maximum process count or a skip rule.
    if len(context['active']) >= max(1, (sys.getrecursionlimit() - 100) // 16):
        _fail('OPERATION_PREDECESSOR_DEPTH_LIMIT', '前序证明链超过当前安全核验深度，不能跳过核验开工。')
    if epoch is not None and key in context['completed']:
        return deepcopy(context['completed'][key])
    start = ProductionOperationStart.objects.filter(task_id=task.pk).only('started_by_id').first()
    actor = User.objects.only('id', 'company_id', 'username', 'is_active', 'is_superuser').filter(pk=start.started_by_id).first() if start else None
    if not actor or actor.company_id != task.company_id:
        _fail('OPERATION_PREDECESSOR_TASK_UNPROVEN', '前序正式完成事实缺失：开工本人及公司来源无法核实。')
    context['active'].append(key)
    try:
        from .operation_completion_v3_authority import validated_bundle
        bundle = validated_bundle(task, actor)
        fact = completion._history(task, bundle)
        if not bundle['ready']:
            _fail('OPERATION_PREDECESSOR_SOURCE_UNPROVEN', '前序正式完成来源未通过当前核验：' + '；'.join(bundle['issues']))
        if (not fact or fact['statusCode'] != 'completed'
                or fact['stateMachineConsistent'] is not True or fact['projectionVersion'] != 2
                or not fact['approvalDecisionId']):
            if continued is not None:
                name = previous.source_snapshot.get('operationName') or previous.operation.name
                _fail('OPERATION_PREDECESSOR_COMPLETION_REQUIRED', f'前序「{name}」为当前必做，尚无生产跟单员独立审核生效的完工依据。')
            _fail('OPERATION_PREDECESSOR_COMPLETION_REQUIRED', '前序正式完成事实缺失：必须经生产跟单员独立审核生效，报齐或待审核不能替代。')
        if not nonquantified and not _historical_proof_only.get():
            from .operation_completion_v3_authority import current_production_status
            current_production=current_production_status(task,actor,fact)
            if not current_production['currentAdmissionReady']:
                _fail('OPERATION_PREDECESSOR_CURRENT_PRODUCTION_BLOCKED',
                    '前序历史独审证明仍保留；当前生产事实未通过：'+'；'.join(current_production['blockingIssues']))
        proof = {'contractVersion': CONTRACT, 'companyId': task.company_id, 'workOrderId': task.work_order_id,
            'operationId': previous.pk, 'sequence': previous.sequence, 'taskId': task.pk, 'taskVersion': task.version,
            'rootStepId': previous.root_step_id, 'effectiveStepId': previous.effective_step_id,
            'rootRoutingVersionId': previous.root_routing_version_id, 'effectiveRoutingVersionId': previous.effective_routing_version_id,
            'operationSnapshotHash': previous.snapshot_hash, 'taskSourceSnapshotHash': task.source_snapshot_hash,
            'completionSourceSnapshotHash': fact['sourceSnapshotHash'], 'completionProjectionVersion': fact['projectionVersion'],
            'workflowInstanceId': fact['workflowInstanceId'], 'workflowVersion': fact['workflowVersion'],
            'approvalTaskId': fact['approvalTaskId'], 'approvalTaskVersion': fact['approvalTaskVersion'],
            'approvalDecisionId': fact['approvalDecisionId'], 'requestAuditReference': fact['requestAuditReference'],
            'approvalAuditReference': fact['approvalAuditReference'], 'completedAtLabel': fact['completedAtLabel'],
            'completionTimeBasis': 'APPROVAL_AUDIT_EFFECTIVE_TIME', 'statusLabel': fact['statusLabel'], 'completed': True}
        if nonquantified:
            confirmation=bundle.get('executionConfirmation')
            if not confirmation or bundle['snapshot'].get('quantityApplicable') is not False:
                _fail('OPERATION_PREDECESSOR_EXECUTION_REQUIRED','不可统计前序缺少正式实际经过及独立审核完成证明。')
            proof.update(contractVersion=TYPED_CONTRACT,proofType='FORMAL_NON_QUANTITATIVE_COMPLETION',
                executionMode='NON_QUANTIFIED_REQUIRED',quantityApplicable=False,actualExecution=True,
                executionConfirmation=deepcopy(confirmation),modeSourceHash=bundle['snapshot']['modeSourceHash'])
        elif fact.get('completionProtocolVersion')==3:
            proof.update(completionProtocolVersion=3,completionGenerationId=fact['generationId'],
                completionGenerationSequence=fact['generationSequence'],completionGenerationVersion=fact['generationVersion'])
        if _proof_cache_epoch(context)!=epoch:
            _fail('OPERATION_PREDECESSOR_READ_CHANGED','前序证明读取已变化，未保存过期核验结果。')
        if epoch is not None:context['completed'][key] = proof
        return deepcopy(proof)
    finally:
        context['active'].pop()


def _exemption(previous, successor, context):
    """Exclusion satisfies this node only; all of its predecessors still count."""
    from .operation_exemption_authority import read_operation_exemption
    from system.models import User
    if previous.work_order_id != successor.work_order_id or previous.work_order.company_id != successor.company_id:
        _fail('OPERATION_PREDECESSOR_SCOPE_INVALID', '免执行前序必须属于同公司同工单。')
    epoch=_proof_cache_epoch(context)
    key = ('EXEMPTION', successor.company_id, successor.work_order_id, previous.pk, _historical_proof_only.get(),epoch)
    if key in context['active']:
        _fail('OPERATION_PREDECESSOR_CYCLE', '免执行前序证明存在循环，不能跳过核验。')
    if len(context['active']) >= max(1, (sys.getrecursionlimit() - 100) // 16):
        _fail('OPERATION_PREDECESSOR_DEPTH_LIMIT', '前序证明链超过当前安全核验深度，不能跳过核验开工。')
    if epoch is not None and key in context['completed']:
        return deepcopy(context['completed'][key])
    actor = User.objects.only('id', 'company_id', 'username', 'is_active', 'is_superuser').filter(
        pk=successor.assignment_snapshot.get('userId'), company_id=successor.company_id, is_active=True).first()
    certificate = read_operation_exemption(previous, actor=actor)
    by_sequence, route_issue = _graph(successor)
    if route_issue:
        _fail('OPERATION_PREDECESSOR_SOURCE_UNPROVEN', route_issue)
    context['active'].append(key)
    try:
        ancestors = []
        for sequence in previous.source_snapshot['predecessorSequences']:
            ancestor = by_sequence.get(sequence)
            if ancestor is None:
                _fail('OPERATION_PREDECESSOR_SOURCE_UNPROVEN', '免执行步骤的必需上游工序缺失，不能跳过。')
            ancestors.append(_completion(ancestor, successor, context))
        proof = {**certificate, 'requiredPredecessorProofs': ancestors,
            'predecessorChainHash': _hash({'exemptionProofHash': certificate['proofHash'], 'ancestors': ancestors}),
            'prerequisiteSatisfied': True, 'completed': False}
        if _proof_cache_epoch(context)!=epoch:
            _fail('OPERATION_PREDECESSOR_READ_CHANGED','免执行证明读取已变化，未保存过期核验结果。')
        if epoch is not None:context['completed'][key] = proof
        return deepcopy(proof)
    finally:
        context['active'].pop()


@routing_read_phase("predecessor")
def predecessor_facts(task):
    with verification_context() as context:
        by_sequence, route_issue = _graph(task)
        frozen = task.source_operation.source_snapshot.get('predecessorSequences')
        items = []
        for sequence in frozen if isinstance(frozen, list) else []:
            previous = by_sequence.get(sequence) if type(sequence) is int else None
            item = {'operationId': previous.pk if previous else None, 'sequence': sequence,
                'operationName': previous.source_snapshot.get('operationName') if previous else None,
                'completed': False, 'formalCompletionFact': None, 'statusLabel': route_issue or '正式前序身份缺失或无效'}
            if previous and not route_issue:
                try:
                    proof = _completion(previous, task, context)
                    if proof.get('proofType') == 'FORMAL_EXEMPTION':
                        item.update(completed=False, prerequisiteSatisfied=True, formalExemptionFact=proof,
                            proofType='FORMAL_EXEMPTION', actualExecution=False,
                            statusLabel='前序正式不适用，免执行来源及其全部必需上游已核实')
                    else:
                        item.update(completed=True, formalCompletionFact=proof, statusLabel='前序正式审核完工已生效')
                        if proof.get('proofType')=='FORMAL_NON_QUANTITATIVE_COMPLETION':
                            item.update(proofType=proof['proofType'],actualExecution=True,
                                statusLabel='前序实际经过及生产跟单独立审核完工已核实')
                except PlanningBusinessError as error:
                    item.update(statusLabel=error.message, reasonCode=error.code)
            items.append(item)
        typed = any('formalExemptionFact' in item or item.get('proofType')=='FORMAL_NON_QUANTITATIVE_COMPLETION' for item in items)
        satisfied = lambda item: item.get('prerequisiteSatisfied', item['completed'])
        ready = bool(not route_issue and all(satisfied(item) for item in items))
        label = route_issue or ('正式路线无前序，可继续核对开工资格' if not items else
            ('全部必需前序的正式执行或免执行证明已核实，可继续核对本人开工资格' if typed else
             '全部必需前序正式审核完工已生效，可继续核对本人开工资格') if ready else
            '；'.join(item['statusLabel'] for item in items if not satisfied(item)))
        return {'ready': ready, 'statusLabel': label, 'items': items, 'authority': 'FORMAL_ROUTE_AND_COMPLETION',
            'contractVersion': TYPED_CONTRACT if typed else CONTRACT, 'routeRelationshipConsistent': route_issue is None,
            'completionAuthorityAvailable': True, 'plannedDatesUsedAsCompletion': False}


def _historical_items_match(frozen_items, current_items):
    """Compare exact reverified proofs, allowing the original V1 time rendering.

    Historical starts froze the old Chinese second-resolution display. The
    current reader emits an offset-aware ISO label for the same audited instant.
    Only regenerate that legacy label from the reverified current proof; do not
    drop timestamps, versions, identities, hashes, decisions or audit references.
    The enclosing start audit still verifies the original frozen JSON verbatim.
    """
    if frozen_items == current_items:
        return True
    if not isinstance(frozen_items, list) or not isinstance(current_items, list) or len(frozen_items) != len(current_items):
        return False
    from datetime import datetime
    comparable = deepcopy(current_items)
    for frozen, current in zip(frozen_items, comparable):
        if not isinstance(frozen, dict) or not isinstance(current, dict):
            return False
        old = frozen.get('formalCompletionFact')
        proof = current.get('formalCompletionFact')
        if (isinstance(old, dict) and isinstance(proof, dict)
                and old.get('contractVersion') == proof.get('contractVersion') == CONTRACT
                and old.get('completionTimeBasis') == proof.get('completionTimeBasis') == 'APPROVAL_AUDIT_EFFECTIVE_TIME'
                and old.get('completedAtLabel') != proof.get('completedAtLabel')):
            try:
                instant = datetime.fromisoformat(proof['completedAtLabel'])
                if instant.utcoffset() is None:
                    return False
                legacy = instant.strftime('%Y年%m月%d日 %H:%M:%S')
            except (ValueError, TypeError, KeyError):
                return False
            if old.get('completedAtLabel') != legacy:
                return False
            proof['completedAtLabel'] = legacy
    return frozen_items == comparable


@routing_read_phase("predecessor")
def frozen_predecessors_valid(task, frozen):
    sequences = task.source_operation.source_snapshot.get('predecessorSequences')
    # Preserve the exact, already accepted no-predecessor record semantics.
    if sequences == []:
        return frozen.get('items') == []
    if frozen.get('contractVersion') not in (CONTRACT, TYPED_CONTRACT) or frozen.get('completionAuthorityAvailable') is not True:
        return False
    # Original starts retain the verified historical approval they consumed.
    # Later production corrections affect a NEW start's admission, rather than
    # rewriting that old start or its frozen qualification. The historical
    # producers, original decisions/audits and exact DAG are still reverified.
    token=_historical_proof_only.set(True)
    try:current = predecessor_facts(task)
    finally:_historical_proof_only.reset(token)
    return bool(current['ready'] and frozen.get('contractVersion') == current['contractVersion']
        and _historical_items_match(frozen.get('items'), current['items']))
