"""Date projection after native MES validation; never part of proof snapshots."""
from .mes_test_source_bridge import execution_timezone
from .workshop_task_time import task_datetime_label


def task_date_facts(task, start, *, report_dates=None, completion=None):
    """Keep the frozen plan, occurrence and recording times distinct.

    This receives already verified objects. It performs no qualification and
    supplies no substitute date when a historical fact is absent. Completion's
    existing completedAtLabel is review effectiveness, not physical work end.
    """
    operation = task.source_snapshot.get('operation', {})
    zone = execution_timezone(task)
    facts = {
        'contractVersion': 'PCE-MES-TASK-DATE-FACTS-V1',
        'taskId': task.pk, 'workOrderId': task.work_order_id,
        'businessTimezone': zone,
        'plannedStartAt': operation.get('start'),
        'plannedCompletionAt': operation.get('end'),
        'planSource': 'task.source_snapshot.operation',
        'actualStartAt': start.started_at.isoformat() if start else None,
        'actualStartAtLabel': task_datetime_label(start.started_at, zone) if start else None,
        'startRecordedAt': start.created_at.isoformat() if start else None,
        'startRecordedAtLabel': task_datetime_label(start.created_at, zone) if start else None,
        'completionReviewEffectiveAtLabel': (
            completion.get('completedAtLabel') if completion and completion.get('statusCode') == 'completed' else None),
        'completionTimeMeaning': '原独立审核生效时点；不代表另行采集的现场物理完工时间',
        'physicalCompletionTimeSupported': False,
        'physicalCompletionAt': None,
    }
    if report_dates is not None:
        facts['reportEvents'] = [{
            'reportId': row['reportId'],
            'reportedAt': row['reportedAt'].isoformat(),
            'reportedAtLabel': task_datetime_label(row['reportedAt'], zone),
            'recordedAt': row['recordedAt'].isoformat(),
            'recordedAtLabel': task_datetime_label(row['recordedAt'], zone),
        } for row in report_dates]
    return facts
