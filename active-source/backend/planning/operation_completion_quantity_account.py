"""One production authority adapter; logistics never changes whole-proof Hash."""
from copy import deepcopy
from decimal import Decimal
import re
from .mes_test_source_bridge import _fail, _hash


def native_context(task, actor):
    from .operation_output_authority import task_context
    return task_context(task,actor)


def production_snapshot(task, actor=None, *, context=None):
    from .operation_output_authority import production_snapshot as native
    value=native(task, actor=actor,context=context)
    if (not isinstance(value,dict) or type(value.get('revision')) is not int or value['revision'] < 0
            or not isinstance(value.get('payload'),dict)
            or value.get('hash') != _hash(value['payload'])
            or value['payload'].get('companyId') != task.company_id
            or value['payload'].get('taskId') != task.pk
            or value['payload'].get('taskVersion') != task.version
            or value['payload'].get('sourceSnapshotHash') != task.source_snapshot_hash
            or not isinstance(value.get('blockingIssues'),list)):
        _fail('COMPLETION_PRODUCTION_FACTS_INVALID','当前正式生产账户或来源绑定未通过核验。')
    if task.execution_mode!='QUANTIFIED':
        if (value.get('wholeProductionQuantity') is not None or value.get('planQuantity') is not None
                or value.get('wholeProductionCoversPlan') is not False):
            _fail('COMPLETION_PRODUCTION_FACTS_INVALID','不可统计任务不能生成计划量或有效产量。')
        return {**deepcopy(value),'quantityApplicable':False,'P':None,'R':None,'E':None}
    if (any(not isinstance(value.get(k),str) or not re.fullmatch(r'(0|[1-9][0-9]*)(\.[0-9]+)?',value[k])
                for k in ('wholeProductionQuantity','planQuantity'))
            or type(value.get('wholeProductionCoversPlan')) is not bool
            or Decimal(value['planQuantity'])!=Decimal(task.workload_quantity)
            or Decimal(value['planQuantity'])<=0
            or value['wholeProductionCoversPlan']!=(Decimal(value['wholeProductionQuantity'])>=Decimal(value['planQuantity']))):
        _fail('COMPLETION_PRODUCTION_FACTS_INVALID','当前正式生产账户或来源绑定未通过核验。')
    return {**deepcopy(value),'quantityApplicable':True}


def production_issues(snapshot):
    if snapshot.get('quantityApplicable') is False:return []
    result=list(snapshot['blockingIssues'])
    if snapshot['wholeProductionCoversPlan'] is not True:
        result.append('当前有效整体生产数量未覆盖原正式计划；已确认产量更正不能由历史报齐记录抵消。')
    if snapshot['payload'].get('unresolvedProductionExceptions'):
        result.append('存在未确认的补充报工或生产真实性更正，不能申请或审核本次整体完工。')
    return list(dict.fromkeys(result))


def verify_frozen_production(task, snapshot, *, context=None):
    from .operation_output_authority import verify_production_snapshot
    return verify_production_snapshot(task, snapshot,context=context)


def quantity_account(task, actor=None, *, context=None,whole_proof=None):
    from .operation_output_authority import read_task_quantity_account
    return read_task_quantity_account(task, actor=actor,context=context,whole_proof=whole_proof)


def has_new_production(snapshot):
    body=snapshot['payload']
    return bool(body.get('supplementalEvidence') or body.get('productionCorrections')
        or body.get('unresolvedProductionExceptions'))


def combined_source(bundle, production):
    snapshot={'baseSourceSnapshot':deepcopy(bundle['snapshot']),
        'baseSourceSnapshotHash':bundle['snapshotHash'],
        'productionSnapshot':deepcopy(production)}
    return snapshot, _hash(snapshot)
